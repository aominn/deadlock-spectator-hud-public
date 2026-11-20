using System.Diagnostics;
using System.Drawing;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Windows.Forms;

internal static class Program
{
    const string ProductFolder = "DeadlockSpectatorHUD";
    internal const string PublicRepository = "aominn/deadlock-spectator-hud-public";
    internal static bool RestartRequested;
    static readonly (string Home, string InstancePrefix) Profile = SelectProfile(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData));
    internal static string Home => Profile.Home;

    internal static (string Home, string InstancePrefix) SelectProfile(string localAppData)
    {
        string current = Path.Combine(localAppData, ProductFolder);
        string legacy = Path.Combine(localAppData, "Aominn", ProductFolder);
        string[] stateFiles = ["config.json", "hotkeys.json", "team-headings.json", "roster-display", "mount.json", "focus-fps.json"];
        bool legacyRecovery = File.Exists(Path.Combine(legacy, "mount.json")) || File.Exists(Path.Combine(legacy, "focus-fps.json"));
        // An older install can still hold the absolute paths needed to restore the game.
        if (legacyRecovery || (!HasState(current) && HasState(legacy)))
            return (legacy, "AominnDeadlockHud");
        return (current, ProductFolder);

        bool HasState(string path) => stateFiles.Any(name => File.Exists(Path.Combine(path, name)));
    }

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
            using var signal = new EventWaitHandle(false, EventResetMode.AutoReset, $@"Local\{Profile.InstancePrefix}Show");
            using var mutex = new Mutex(true, $@"Local\{Profile.InstancePrefix}Manager", out bool first);
            if (!first) { signal.Set(); return; }
            Application.Run(new ManagerForm(root, signal));
        }
        catch (Exception e) { MessageBox.Show(e.Message, Ui.T("観戦HUD"), MessageBoxButtons.OK, MessageBoxIcon.Error); }
        if (RestartRequested) Process.Start(new ProcessStartInfo(Path.Combine(Home, "HudManager.exe")) { UseShellExecute = false, WorkingDirectory = Home });
    }
}

internal sealed partial class ManagerForm : Form
{

    readonly string bundle;
    readonly EventWaitHandle showSignal;
    readonly TextBox game = new() { Dock = DockStyle.Fill, AccessibleName = Ui.T(@"Deadlockのフォルダー（game\citadel）") };
    readonly Label state = new() { AutoSize = true };
    readonly Label details = new() { AutoSize = true };
    readonly Label keySummary = new() { AutoSize = true };
    readonly Label output = new() { AutoSize = true, AccessibleName = L("操作結果", "Action result") };
    readonly System.Windows.Forms.Timer timer;
    readonly DrawingController drawing;
    HudKeys keys;
    bool busy, exiting, closeRequested, stopping, startupComplete;

    public ManagerForm(string root, EventWaitHandle signal)
    {
        bundle = root;
        showSignal = signal;
        keys = HudKeys.Load(Program.Home);
        drawing = new DrawingController(message => { if (!IsDisposed) output.Text = message; });
        ConfigureFormDpi(this);
        Text = Ui.T("Deadlock 観戦HUD");
        ClientSize = new Size(880, 640);
        StartPosition = FormStartPosition.CenterScreen;
        BuildWindow();

        FormClosing += async (_, e) =>
        {
            if (exiting) return;
            e.Cancel = true;
            closeRequested = true;
            if (!busy && !stopping) await FinishClose();
        };
        timer = new System.Windows.Forms.Timer { Interval = 2000 };
        timer.Tick += async (_, _) =>
        {
            if (showSignal.WaitOne(0)) Open();
            if (!busy && Visible)
            {
                try { await RefreshStatus(); }
                catch { details.Text = L("状態を読み込めません。ヘルプから確認してください。", "Could not read status. See Help."); }
            }
        };
        Shown += async (_, _) => await Guard(async () =>
        {
            output.Text = Ui.T("起動の準備をしています。しばらくお待ちください。");
            await RefreshStatus();
            var update = await Run("startup", silent: true);
            if (update["updated"]?.GetValue<bool>() == true) { Program.RestartRequested = true; Close(); return; }
            if (string.IsNullOrEmpty(game.Text)) game.Text = update["game"]?.GetValue<string>() ?? "";
            startupComplete = true;
            await RefreshStatus();
            output.Text = "";
        });
        timer.Start();
        FormClosed += (_, _) => { drawing.Dispose(); timer.Dispose(); };
    }


    static void ConfigureFormDpi(Form form)
    {
        // Start each window from the design font, independent of the owner's current DPI.
        form.Font = new Font(Ui.Japanese ? "Yu Gothic UI" : "Segoe UI", 10);
        form.AutoScaleMode = AutoScaleMode.Dpi;
        form.AutoScaleDimensions = new SizeF(96, 96);
        void FitWorkArea()
        {
            if (form.IsDisposed || form.WindowState != FormWindowState.Normal) return;
            Rectangle area = Screen.FromControl(form).WorkingArea;
            form.Bounds = FitWindowBounds(form.Bounds, area);
        }
        form.Shown += (_, _) => FitWorkArea();
        form.DpiChanged += (_, _) => form.BeginInvoke(FitWorkArea);
    }

    internal static Rectangle FitWindowBounds(Rectangle window, Rectangle area)
    {
        int width = Math.Min(window.Width, area.Width);
        int height = Math.Min(window.Height, area.Height);
        return new(Math.Clamp(window.X, area.Left, area.Right - width),
            Math.Clamp(window.Y, area.Top, area.Bottom - height), width, height);
    }

    void Open() { Show(); WindowState = FormWindowState.Normal; Activate(); }
    JsonNode? Config() { var p = Path.Combine(Program.Home, "config.json"); return File.Exists(p) ? JsonNode.Parse(File.ReadAllText(p)) : null; }
    async Task Guard(Func<Task> f)
    {
        if (busy) return; busy = true; shell.Enabled = false;
        try { await f(); }
        catch (Exception e) { output.Text = e.Message; }
        finally { busy = false; if (!IsDisposed) { shell.Enabled = true; if (closeRequested) await FinishClose(); } }
    }
    async Task FinishClose()
    {
        if (stopping || exiting) return;
        drawing.Configure(false, keys.Drawing);
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
            if (result["assets"] is JsonObject assets) output.Text += Ui.T("\r\n画像：ゲームから ") + assets["current"] + Ui.T(" ／ 旧画像 ") + assets["previous"] + Ui.T(" ／ 画像なし ") + assets["missing"];
            if (action == "verify") output.Text += Ui.T("\r\n版：") + result["version"]?.GetValue<string>() + Ui.T("　検証ファイル数：") + result["files"]?.ToString();
        }
        return result;
    }
    async Task RestoreLegacyFocus()
    {
        var result = await Run("launch", new() { ["focus"] = "restore" });
        await RefreshStatus();
        if (result["game_pid"]?.GetValue<int>() is int pid && result["focus"]?.GetValue<string>() is "enable" or "restore")
            _ = CheckFocusAfterExit(pid, "restore");
        else if (result["focus"]?.GetValue<string>() is "restored" or "different")
            ShowFocusResult(result["focus"]!.GetValue<string>(), "restore");
    }

    async Task CheckFocusAfterExit(int pid, string mode)
    {
        try
        {
            try
            {
                using var process = Process.GetProcessById(pid);
                await process.WaitForExitAsync();
            }
            catch (ArgumentException) { }
            if (IsDisposed || closeRequested || busy) return;
            await Guard(async () =>
            {
                var result = await Run("focus-status", silent: true);
                await RefreshStatus();
                ShowFocusResult(result["state"]?.GetValue<string>(), mode);
            });
        }
        catch (Exception)
        {
            if (!IsDisposed && !closeRequested)
                output.Text = L("FPS設定の結果は未確認です。「設定」→「画面への描き込み」から復元できます。", "The FPS setting has not been verified. You can restore it under Settings → Drawing on screen.");
        }
    }

    void ShowFocusResult(string? state, string mode)
    {
        if (state == "restored")
            output.Text = L("FPS設定が元の値に戻っていることを確認しました。", "The original FPS setting was verified.");
        else if (state == "different")
            output.Text = L("FPS設定は別の値になっています。現在の値を保持しました。", "The FPS setting has a different value. The current value was kept.");
        else if (state == "pending" && mode == "restore")
            output.Text = L("FPS設定がまだ0です。復元操作を再試行するか、READMEの手順を使ってください。", "The FPS setting is still 0. Retry the restore action or follow the README.");
    }

    static string ServiceLabel(string? value) => value switch { "waiting" => Ui.T("ゲーム起動待機"), "watching" => Ui.T("観戦・リプレイ待機中"), "stopped" => Ui.T("停止"), "error" => Ui.T("要確認"), _ => Ui.T("準備中") };
    Task RefreshStatus()
    {
        var config = Config() ?? new JsonObject();
        var servicePath = Path.Combine(Program.Home, "service.json");
        var service = File.Exists(servicePath) ? JsonNode.Parse(File.ReadAllText(servicePath)) : null;
        bool enabled = config["enabled"]?.GetValue<bool>() == true;
        bool prepared = config["version"] is not null && config["game"] is not null;
        bool recover = !enabled && File.Exists(Path.Combine(Program.Home, "mount.json"));
        bool running = GameRunning();
        string headline = recover ? L("通常モードへの復旧が必要です", "Normal mode recovery needed")
            : !prepared ? L("初回セットアップが必要です", "Setup required")
            : enabled ? Ui.T("HUD有効") : Ui.T("通常モード");
        string serviceMessage = ServiceLabel(service?["state"]?.GetValue<string>());
        string description = running
            ? L("ゲーム起動中。モードを変更するときはゲームを終了してください。", "Game running. Close the game to change modes.")
            : recover ? L("ゲームを起動する前に通常モードへ戻します。", "Restore normal mode before launching.")
            : !prepared ? L("Deadlockの場所を確認し、表示に使う素材を準備します。", "Choose the Deadlock folder and prepare the HUD assets.")
            : enabled ? serviceMessage + L("。通常プレイの前に通常モードへ戻してください。", ". Restore normal mode before playing.")
            : L("標準の表示で起動します。観戦用の表示は「HUDを有効にする」から使えます。", "The game launches with its standard display. Enable the HUD before spectating.");
        state.Text = headline;
        details.Text = description;
        versionLabel.Text = config["version"]?.GetValue<string>() is string version ? L("バージョン ", "Version ") + version : "";
        primaryButton.Visible = prepared || recover;
        primaryButton.Text = recover ? Ui.T("通常モードへ戻す") : Ui.T("ゲームを起動");
        primaryButton.Enabled = startupComplete && !running;
        modeButton.Text = enabled ? Ui.T("通常モードへ戻す") : Ui.T("HUDを有効にする");
        modeButton.Visible = prepared && !recover;
        modeButton.Enabled = startupComplete && !running;
        folderButton.Visible = prepared && !recover;
        folderButton.Enabled = startupComplete && !running;
        folderButton.Text = folderSettingsOpen ? L("フォルダー設定を閉じる", "Close folder settings")
            : L("ゲームフォルダーを変更", "Change game folder");
        folderSettings.Visible = !recover && (!prepared || folderSettingsOpen);
        helpWrite.Enabled = startupComplete && !running;
        setupWrite.Enabled = startupComplete && !running;
        saveSettings.Enabled = startupComplete && !running;
        launchPath = recover ? "normal" : "launch";
        modePath = enabled ? "normal" : "enable";
        UpdateSettingsNotice(running);
        UpdateLegacyButton(running);
        homeHints.Visible = prepared && !recover;
        drawing.Configure(keys.DrawingEnabled && enabled, keys.Drawing);
        return Task.CompletedTask;
    }

    Task OpenReleases()
    {
        string repo = Config()?["repository"]?.GetValue<string>() ?? Program.PublicRepository;
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
        folderSettingsOpen = false;
        await RefreshStatus();
        ShowPage(homePage);
    }
    static string L(string ja, string en) => Ui.Japanese ? ja : en;

    void UpdateKeySummary() => keySummary.Text = keys.DrawingEnabled
        ? L($"描き込み {keys.Drawing.Display}", $"Draw {keys.Drawing.Display}")
            + $"  /  {L("与ダメージ", "Damage Dealt")} {keys.Damage.Display}  /  {L("ソウル差", "Soul Lead")} {keys.Graph.Display}"
        : L($"与ダメージ {keys.Damage.Display}  /  ソウル差 {keys.Graph.Display}",
            $"Damage Dealt {keys.Damage.Display}  /  Soul Lead {keys.Graph.Display}");

    static bool GameRunning()
    {
        var games = Process.GetProcessesByName("deadlock");
        foreach (var game in games) game.Dispose();
        return games.Length != 0;
    }
}
