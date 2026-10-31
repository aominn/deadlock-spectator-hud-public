using System.Diagnostics;
using System.Drawing;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Windows.Forms;

internal static class Program
{
    internal static bool RestartRequested;
    internal static readonly string Home = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Aominn", "DeadlockSpectatorHUD");
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        try
        {
            string root = AppContext.BaseDirectory;
            var configPath = Path.Combine(Home, "config.json");
            var config = File.Exists(configPath) ? JsonNode.Parse(File.ReadAllText(configPath)) : null;
            string? active = config?["bundle"]?.GetValue<string>();
            bool bootstrap = !File.Exists(Path.Combine(root, "release.json"));
            string? incoming = bootstrap ? null : JsonNode.Parse(File.ReadAllText(Path.Combine(root, "release.json")))?["version"]?.GetValue<string>();
            bool olderPackage = Version.TryParse(incoming, out var offered) && Version.TryParse(config?["version"]?.GetValue<string>(), out var installed) && offered < installed;
            bool oldInstalledVersion = Path.GetFullPath(root).StartsWith(Path.Combine(Home, "versions") + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
                && active != null && !Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar).Equals(Path.GetFullPath(active).TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase);
            if (bootstrap || oldInstalledVersion || olderPackage)
            {
                if (active == null) throw new Exception(Ui.T("初回セットアップを配布フォルダーから実行してください。"));
                var pi = new ProcessStartInfo(Path.Combine(active, "HudManager.exe")) { UseShellExecute = false, WorkingDirectory = active };
                foreach (var arg in args) pi.ArgumentList.Add(arg);
                Process.Start(pi); return;
            }
            using var signal = new EventWaitHandle(false, EventResetMode.AutoReset, @"Local\AominnDeadlockHudShow");
            using var mutex = new Mutex(true, @"Local\AominnDeadlockHudManager", out bool first);
            if (!first) { signal.Set(); return; }
            Application.Run(new ManagerForm(root, signal));
        }
        catch (Exception e) { MessageBox.Show(e.Message, Ui.T("観戦HUD"), MessageBoxButtons.OK, MessageBoxIcon.Error); }
        if (RestartRequested) Process.Start(new ProcessStartInfo(Path.Combine(Home, "HudManager.exe")) { UseShellExecute = false, WorkingDirectory = Home });
    }
}

internal sealed class ManagerForm : Form
{
    string bundle;
    readonly EventWaitHandle showSignal;
    readonly TextBox game = new() { Dock = DockStyle.Fill, AccessibleName = Ui.T(@"Deadlockのフォルダー（game\citadel）") };
    readonly Label state = new() { AutoSize = true, Font = new Font("Yu Gothic UI", 16, FontStyle.Bold) };
    readonly Label details = new() { AutoSize = true, MaximumSize = new Size(690, 0) };
    readonly TextBox output = new() { Dock = DockStyle.Fill, ReadOnly = true, Multiline = true, ScrollBars = ScrollBars.Vertical };
    readonly System.Windows.Forms.Timer timer;
    readonly DrawingController drawing;
    readonly CheckBox drawingEnabled = new() { Text = Ui.T("線を描く（観戦・リプレイ中のみ）"), AutoSize = true };
    readonly ComboBox drawingKey = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 138 };
    bool busy, exiting, closeRequested, stopping;
    readonly List<Control> actions = new();

    public ManagerForm(string root, EventWaitHandle signal)
    {
        bundle = root; showSignal = signal;
        drawing = new DrawingController(message => { if (!IsDisposed) output.Text = message; });
        Text = Ui.T("Deadlock 観戦HUD"); ClientSize = new Size(760, 550); MinimumSize = new Size(700, 530);
        Font = new Font(Ui.Japanese ? "Yu Gothic UI" : "Segoe UI", 10); StartPosition = FormStartPosition.CenterScreen;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(22), ColumnCount = 1, RowCount = 10 };
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize)); layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        for (int i = 2; i < 9; i++) layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); Controls.Add(layout);
        layout.Controls.Add(state); layout.Controls.Add(details);
        layout.Controls.Add(new Label { Text = Ui.T("Deadlockのフォルダー（末尾の citadel まで選択）\r\n例：...\\Steam\\steamapps\\common\\Deadlock\\game\\citadel"), AutoSize = true, Margin = new Padding(0, 18, 0, 4) });
        var pathRow = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2 }; pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, Ui.Japanese ? 82 : 96));
        pathRow.Controls.Add(game); var browse = Button(Ui.T("参照"), () => { using var f = new FolderBrowserDialog { Description = Ui.T(@"Deadlock\game\citadel を選択してください（gameinfo.gi があるフォルダー）"), ShowNewFolderButton = false, UseDescriptionForTitle = true, SelectedPath = Directory.Exists(game.Text) ? game.Text : "" }; if (f.ShowDialog() == DialogResult.OK) game.Text = f.SelectedPath; return Task.CompletedTask; }); pathRow.Controls.Add(browse); layout.Controls.Add(pathRow);
        var primary = Row(); primary.Controls.Add(Button(Ui.T("準備する"), Prepare)); primary.Controls.Add(Button(Ui.T("HUDを有効にする"), async () => { await Run("enable"); await RefreshStatus(); })); primary.Controls.Add(Button(Ui.T("通常モードへ戻す"), async () => { await Run("normal"); await RefreshStatus(); })); primary.Controls.Add(Button(Ui.T("ゲームを起動"), async () => { await Run("launch"); })); layout.Controls.Add(primary);
        layout.Controls.Add(new Label { Text = Ui.T("観戦中はこの画面を開いておいてください。×で終了、最小化中は動作します。"), AutoSize = true });
        layout.Controls.Add(new Label { Text = Ui.T("使い方：フォルダーを選び「準備する」→「HUDを有効にする」→「ゲームを起動」。"), AutoSize = true, MaximumSize = new Size(690, 0), Margin = new Padding(0, 6, 0, 4) });
        var updates = Row(); updates.Controls.Add(Button(Ui.T("最新版をダウンロード"), OpenReleases)); updates.Controls.Add(Button(Ui.T("困ったとき"), ShowHelp, guarded: false)); layout.Controls.Add(updates);
        var ink = Row(); drawingKey.Items.AddRange(new[] { "F8", "F9", "F10", "Ctrl+Shift+D" }); drawingKey.SelectedIndex = 0;
        void ConfigureDrawing() { drawing.Configure(drawingEnabled.Checked && Config()?["enabled"]?.GetValue<bool>() == true, drawingKey.SelectedItem?.ToString() ?? "F8"); }
        drawingEnabled.CheckedChanged += (_, _) => ConfigureDrawing(); drawingKey.SelectedIndexChanged += (_, _) => ConfigureDrawing();
        ink.Controls.Add(drawingEnabled); ink.Controls.Add(drawingKey); ink.Controls.Add(new Label { Text = Ui.T("選んだキーで表示切替／「描く・観戦へ」で操作切替"), AutoSize = true, Padding = new Padding(0, 5, 0, 0) }); layout.Controls.Add(ink);
        layout.Controls.Add(output);
        FormClosing += async (_, e) =>
        {
            if (exiting) return;
            e.Cancel = true; closeRequested = true;
            if (!busy && !stopping) await FinishClose();
        };
        timer = new System.Windows.Forms.Timer { Interval = 3000 }; timer.Tick += async (_, _) => { if (showSignal.WaitOne(0)) Open(); if (!busy && Visible) { try { await RefreshStatus(); } catch { details.Text = Ui.T("状態を読み込めません。「困ったとき」から確認してください。"); } } }; timer.Start();
        Shown += async (_, _) => { await Guard(async () => {
            await RefreshStatus();
            output.Text = Ui.T("起動の準備をしています。しばらくお待ちください。");
            var update = await Run("startup", silent: true);
            if (update["updated"]?.GetValue<bool>() == true) { Program.RestartRequested = true; Close(); return; }
            if (string.IsNullOrEmpty(game.Text)) game.Text = update["game"]?.GetValue<string>() ?? "";
            await RefreshStatus();
            output.Text = Ui.T("更新するときは、ゲームとこの画面を終了してから、最新版を展開し、新しいHudManager.exeを開いてください。");
        }); };
        FormClosed += (_, _) => { drawing.Dispose(); timer.Dispose(); };
    }
    FlowLayoutPanel Row() => new() { Dock = DockStyle.Top, AutoSize = true, WrapContents = true, Margin = new Padding(0, 8, 0, 4) };
    Button Button(string text, Func<Task> f, bool guarded = true)
    {
        var b = new Button { Text = text, AutoSize = true, Padding = new Padding(8, 4, 8, 4), Margin = new Padding(0, 2, 7, 4) };
        actions.Add(b); b.Click += async (_, _) => {
            if (guarded) await Guard(f);
            else if (!busy) { try { await f(); } catch (Exception e) { MessageBox.Show(this, e.Message, Ui.T("観戦HUD")); } }
        }; return b;
    }
    void Open() { Show(); WindowState = FormWindowState.Normal; Activate(); }
    JsonNode? Config() { var p = Path.Combine(Program.Home, "config.json"); return File.Exists(p) ? JsonNode.Parse(File.ReadAllText(p)) : null; }
    async Task Guard(Func<Task> f)
    {
        if (busy) return; busy = true; foreach (var c in actions.Where(c => !c.IsDisposed)) c.Enabled = false;
        try { await f(); }
        catch (Exception e) { output.Text = e.Message; if (Visible) MessageBox.Show(this, e.Message, Ui.T("観戦HUD"), MessageBoxButtons.OK, MessageBoxIcon.Information);  }
        finally { busy = false; if (!IsDisposed) { foreach (var c in actions.Where(c => !c.IsDisposed)) c.Enabled = true; if (closeRequested) await FinishClose(); } }
    }
    async Task FinishClose()
    {
        if (stopping || exiting) return;
        drawing.Configure(false, drawingKey.SelectedItem?.ToString() ?? "F8");
        stopping = true; timer.Stop(); Enabled = false;
        output.Text = Ui.T("補助アプリと解析を終了しています。");
        try { await Run("stop-service"); exiting = true; Close(); }
        catch (Exception e)
        {
            Program.RestartRequested = false; closeRequested = false;
            output.Text = Ui.T("終了を確認できませんでした。もう一度×で閉じてください。\r\n") + e.Message;
            MessageBox.Show(this, output.Text, Ui.T("観戦HUD"), MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        finally { if (!IsDisposed) { stopping = false; Enabled = true; if (!exiting) timer.Start(); } }
    }
    async Task<JsonNode> Run(string action, JsonObject? values = null, bool silent = false)
    {
        values ??= new(); values["action"] = action; values["owner_pid"] = Environment.ProcessId; values["language"] = Ui.Language;
        string use = bundle; // Keep the displayed UI and its control protocol on the same version; the backend reads active config.
        var pi = new ProcessStartInfo(Path.Combine(use, "runtime", "python", "python.exe")) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true, StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8, WorkingDirectory = use };
        foreach (var arg in new[] { "-I", Path.Combine(use, "engine", "manager_cli.py"), "--home", Program.Home, "--bundle", use, "--request", values.ToJsonString() }) pi.ArgumentList.Add(arg);
        using var proc = Process.Start(pi) ?? throw new Exception(Ui.T("補助ツールを起動できません。")); var outTask = proc.StandardOutput.ReadToEndAsync(); var errTask = proc.StandardError.ReadToEndAsync(); await proc.WaitForExitAsync(); string text = await outTask; string err = await errTask;
        JsonNode? row; try { row = JsonNode.Parse(text); } catch { throw new Exception(Ui.T("補助ツールから結果を受け取れません。\r\n") + err[..Math.Min(err.Length, 800)]); }
        if (row?["ok"]?.GetValue<bool>() != true) throw new Exception(row?["error"]?.GetValue<string>() ?? Ui.T("操作に失敗しました。"));
        var result = row["result"]!;
        if (!silent && action is not "status" and not "discover")
        {
            output.Text = result["message"]?.GetValue<string>() ?? Ui.T("操作が完了しました。");
            if (result["assets"] is JsonObject assets) output.AppendText(Ui.T("\r\n画像：ゲームから ") + assets["current"] + Ui.T(" ／ 旧画像 ") + assets["previous"] + Ui.T(" ／ 画像なし ") + assets["missing"]);
            if (action == "verify") output.AppendText(Ui.T("\r\n版：") + result["version"]?.GetValue<string>() + Ui.T("　検証ファイル数：") + result["files"]?.ToString());
        }
        return result;
    }
    static string ServiceLabel(string? value) => value switch { "waiting" => Ui.T("ゲーム起動待機"), "watching" => Ui.T("観戦・リプレイ待機中"), "stopped" => Ui.T("停止"), "error" => Ui.T("要確認"), _ => Ui.T("準備中") };
    Task RefreshStatus()
    {
        var c = Config() ?? new JsonObject();
        var sp = Path.Combine(Program.Home, "service.json");
        var service = File.Exists(sp) ? JsonNode.Parse(File.ReadAllText(sp)) : null;
        string headline = c["enabled"]?.GetValue<bool>() == true ? Ui.T("HUD有効") : (File.Exists(Path.Combine(Program.Home, "mount.json")) ? Ui.T("復旧待ち（通常モードへ戻してください）") : Ui.T("通常モード"));
        string serviceMessage = ServiceLabel(service?["state"]?.GetValue<string>());
        string description = Ui.T("バージョン：") + (c["version"]?.GetValue<string>() ?? Ui.T("準備前")) + (c["enabled"]?.GetValue<bool>() == true ? "　" + serviceMessage : Ui.T("　ゲームは通常の表示です。"));
        drawing.Configure(drawingEnabled.Checked && c["enabled"]?.GetValue<bool>() == true, drawingKey.SelectedItem?.ToString() ?? "F8");
        if (state.Text != headline) state.Text = headline;
        if (details.Text != description) details.Text = description;
        return Task.CompletedTask;
    }
    Task OpenReleases()
    {
        string repo = Config()?["repository"]?.GetValue<string>() ?? "aominn/deadlock-spectator-hud-public";
        if (!Regex.IsMatch(repo, @"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")) throw new Exception(Ui.T("GitHubの公開先設定が不正です。"));
        Process.Start(new ProcessStartInfo("https://github.com/" + repo + "/releases") { UseShellExecute = true }); return Task.CompletedTask;
    }
    async Task Prepare()
    {
        var result = await Run("adopt", silent: true);
        if (result["updated"]?.GetValue<bool>() == true) { Program.RestartRequested = true; Close(); return; }
        output.Text = Ui.T("ゲームから表示に使う画像を準備しています。しばらくお待ちください。");
        var config = Config();
        bool sameGame = config?["game"]?.GetValue<string>() is string path && Path.GetFullPath(path).TrimEnd('\\').Equals(Path.GetFullPath(game.Text).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase);
        if (sameGame && config?["bundle"] != null) await Run("refresh-assets");
        else await Run("setup", new() { ["game"] = game.Text });
        await RefreshStatus();
    }
    Task ShowHelp()
    {
        using var dialog = new Form { Text = Ui.T("困ったとき"), ClientSize = new Size(580, 180), StartPosition = FormStartPosition.CenterParent, Font = Font, MaximizeBox = false, MinimizeBox = false };
        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(16), WrapContents = true };
        panel.Controls.Add(new Label { Text = Ui.T("ゲームを終了してから操作してください。\r\n通常の表示へ戻す場合は、メイン画面の「通常モードへ戻す」を使います。"), AutoSize = true, MaximumSize = new Size(540, 0), Margin = new Padding(0, 0, 0, 12) });
        panel.SetFlowBreak(panel.Controls[0], true);
        panel.Controls.Add(Button(Ui.T("ファイルを確認"), async () => { await Run("verify"); }));
        panel.Controls.Add(Button(Ui.T("画像を読み直す"), async () => { await Run("refresh-assets"); await RefreshStatus(); }));
        panel.Controls.Add(Button(Ui.T("前の版へ戻す"), async () => { await Run("rollback"); Program.RestartRequested = true; dialog.Close(); Close(); }));
        dialog.Controls.Add(panel); dialog.ShowDialog(this); return Task.CompletedTask;
    }
}
