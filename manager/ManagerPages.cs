using System.Text;
using System.Windows.Forms;

internal sealed partial class ManagerForm
{
    readonly TableLayoutPanel shell = new() { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3 };
    readonly Panel pages = new() { Dock = DockStyle.Fill, BackColor = SystemColors.Window };
    readonly List<(Button Button, Control Page)> navigation = new();
    readonly Action?[] resetSettings = new Action?[3];
    Func<int>? readDisplayEdits;
    Func<HudKeys>? readKeyEdits;
    Func<(string Json, int Flags)>? readTeamEdits;
    string? savedTeamSnapshot;
    FlowLayoutPanel settingsActions = null!;
    bool teamBanPickerOpen;
    Button saveSettings = null!;
    readonly Label versionLabel = new() { AutoSize = true, ForeColor = SystemColors.GrayText };
    readonly Label settingsNotice = new() { AutoSize = true };
    readonly TabControl settingsTabs = new() { Dock = DockStyle.Fill, Multiline = true, Padding = new Point(12, 5) };
    Control homePage = null!, settingsPage = null!;
    Control homeHints = null!, folderSettings = null!;
    bool folderSettingsOpen;
    Panel setupWrite = null!, helpWrite = null!;
    Button primaryButton = null!, modeButton = null!, folderButton = null!;
    Button? legacyRestore;
    string launchPath = "launch", modePath = "";
    Action? cancelKeys;

    void BuildWindow()
    {
        shell.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        shell.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        shell.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        shell.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        Controls.Add(shell);

        var entries = Row();
        entries.Padding = new Padding(14, 6, 6, 6);
        entries.Margin = Padding.Empty;
        shell.Controls.Add(entries, 0, 0);
        pages.Margin = Padding.Empty;
        shell.Controls.Add(pages, 0, 1);
        homePage = BuildHome();
        settingsPage = BuildSettings();
        AddNavigation(L("ホーム", "Home"), homePage);
        AddNavigation(L("設定", "Settings"), settingsPage);
        AddNavigation(L("ヘルプ", "Help"), BuildHelp());

        var footer = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, Padding = new Padding(14, 5, 12, 6), Margin = Padding.Empty };
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        footer.Controls.Add(output, 0, 0);
        footer.Controls.Add(versionLabel, 1, 0);
        footer.SizeChanged += (_, _) => WrapLabel(output, footer, 40 + versionLabel.Width);
        shell.Controls.Add(footer, 0, 2);
        ShowPage(homePage);
        UpdateKeySummary();

        void AddNavigation(string caption, Control page)
        {
            var button = ActionButton(caption, () => { ShowPage(page); return Task.CompletedTask; }, serialize: false);
            navigation.Add((button, page));
            entries.Controls.Add(button);
            page.Dock = DockStyle.Fill;
            pages.Controls.Add(page);
        }
    }

    void ShowPage(Control page)
    {
        foreach (var (button, candidate) in navigation)
        {
            bool selected = candidate == page;
            candidate.Visible = selected;
            button.BackColor = selected ? SystemColors.GradientInactiveCaption : SystemColors.Control;
            button.AccessibleDescription = selected ? L("表示中のページ", "Current page") : null;
        }
        page.BringToFront();
        if (page == settingsPage) OpenSelectedSettings();
    }

    Control BuildHome()
    {
        var page = Stack();
        Wrapped(page, state);
        state.Font = new Font(Font.FontFamily, 17, FontStyle.Bold);
        TextLine(page, details);
        var mainActions = Row();
        primaryButton = ActionButton(Ui.T("ゲームを起動"), async () => { await Run(launchPath); await RefreshStatus(); });
        primaryButton.Font = new Font(Font, FontStyle.Bold);
        modeButton = ActionButton(Ui.T("HUDを有効にする"), async () => { await Run(modePath); await RefreshStatus(); });
        folderButton = ActionButton(L("ゲームフォルダーを変更", "Change game folder"), () =>
        {
            folderSettingsOpen = !folderSettingsOpen;
            return RefreshStatus();
        }, serialize: false);
        mainActions.Controls.AddRange(new Control[] { primaryButton, modeButton, folderButton });
        page.Controls.Add(mainActions);
        folderSettings = BuildFolderSettings();
        page.Controls.Add(folderSettings);

        var hints = Stack(new Padding(0, 12, 0, 0));
        Heading(hints, L("観戦中のショートカット", "Spectator shortcuts"));
        TextLine(hints, keySummary);
        TextLine(hints, L("観戦中はこの画面を開いておいてください。最小化中も動作し、×で閉じると補助処理が止まります。",
            "Keep this window open while spectating. You can minimize it. Closing it stops the helper."));
        TextLine(hints, L("通常プレイに戻るには、ゲームを終了して「通常モードへ戻す」を押してください。",
            "Before playing a regular match, exit Deadlock and select Restore normal mode."));
        Heading(hints, L("画面への描き込み", "Draw on screen"));
        TextLine(hints, L("画面への描き込みを使うときは、Deadlockをボーダーレスウィンドウに設定してください。",
            "Set Deadlock to Borderless Window to draw on screen."));
        TextLine(hints, L("描き込み中にゲーム音が途切れる場合は、オーディオ設定の「バックグラウンド状態でもサウンドを再生」をオンにしてください。",
            "If game audio stops while drawing, turn on Play sound in background in Deadlock’s audio settings."));
        homeHints = hints;
        page.Controls.Add(homeHints);
        return ScrollPage(page);
    }

    Control BuildFolderSettings()
    {
        var page = Stack(new Padding(0, 12, 0, 0));
        Heading(page, L("ゲームフォルダー", "Game folder"));
        TextLine(page, L("gameinfo.gi がある Deadlock の citadel フォルダーを指定します。",
            "Choose the Deadlock citadel folder that contains gameinfo.gi."));
        var pathRow = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, RowCount = 1 };
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        var browse = ActionButton(Ui.T("参照"), () =>
        {
            using var picker = new FolderBrowserDialog { Description = Ui.T(@"Deadlock\game\citadel を選択してください（gameinfo.gi があるフォルダー）"),
                ShowNewFolderButton = false, UseDescriptionForTitle = true, SelectedPath = Directory.Exists(game.Text) ? game.Text : "" };
            if (picker.ShowDialog(this) == DialogResult.OK) game.Text = picker.SelectedPath;
            return Task.CompletedTask;
        }, serialize: false);
        pathRow.Controls.Add(InputFrame(game), 0, 0);
        pathRow.Controls.Add(browse, 1, 0);
        page.Controls.Add(pathRow);
        var buttons = Row();
        buttons.Controls.Add(ActionButton(L("素材を準備する", "Prepare assets"), Prepare));
        setupWrite = new Panel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink };
        setupWrite.Controls.Add(buttons);
        page.Controls.Add(setupWrite);
        return page;
    }

    Control BuildSettings()
    {
        var frame = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3, Padding = new Padding(12, 9, 12, 8) };
        frame.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        frame.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        frame.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        frame.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        settingsNotice.Margin = new Padding(2, 2, 0, 4);
        frame.Controls.Add(settingsNotice, 0, 0);
        frame.SizeChanged += (_, _) => WrapLabel(settingsNotice, frame, 36);
        frame.Controls.Add(settingsTabs, 0, 1);
        foreach (string caption in new[] { L("表示", "Display"), L("キー設定", "Key bindings"),
                     L("チーム・大会", "Teams & tournament"), L("画面への描き込み", "Drawing on screen") })
            settingsTabs.TabPages.Add(new TabPage(caption) { BackColor = SystemColors.Window });
        settingsActions = Row();
        settingsActions.Padding = new Padding(4, 0, 0, 0);
        saveSettings = ActionButton(L("3つの設定をまとめて保存", "Save all three settings"), SaveAllSettings);
        saveSettings.AccessibleDescription = L("表示・キー設定・チーム／大会をまとめて保存します。",
            "Saves Display, Key bindings, and Teams & tournament together.");
        saveSettings.Enabled = false;
        settingsActions.Controls.Add(saveSettings);
        settingsActions.Controls.Add(ActionButton(L("このタブの編集を取り消す", "Discard edits in this tab"), () =>
        {
            int selected = settingsTabs.SelectedIndex;
            if (selected >= 0 && selected < resetSettings.Length && resetSettings[selected] is { } reset)
            {
                reset();
                output.Text = L("このタブの編集を取り消しました。", "Edits in this tab were discarded.");
            }
            return Task.CompletedTask;
        }, serialize: false));
        frame.Controls.Add(settingsActions, 0, 2);
        // Use the same design DPI for every page, including pages first opened after a scale change.
        for (int index = 0; index < settingsTabs.TabPages.Count; index++)
            BuildSettingsTab(index);
        settingsTabs.SelectedIndexChanged += (_, _) => OpenSelectedSettings();
        return frame;
    }

    void OpenSelectedSettings()
    {
        int selected = settingsTabs.SelectedIndex;
        if (selected < 0) return;
        settingsActions.Visible = selected < resetSettings.Length && (selected != 2 || !teamBanPickerOpen);
        BuildSettingsTab(selected);
        bool running = GameRunning();
        UpdateSettingsNotice(running);
        saveSettings.Enabled = startupComplete && !running;
        UpdateLegacyButton(running);
    }

    void BuildSettingsTab(int selected)
    {
        var tab = settingsTabs.TabPages[selected];
        if (tab.Controls.Count == 0)
        {
            try
            {
                var content = selected switch { 0 => BuildDisplay(), 1 => BuildKeys(), 2 => BuildTeams(), _ => BuildFocus() };
                content.Dock = DockStyle.Fill;
                tab.Controls.Add(content);
            }
            catch (Exception e) { output.Text = e.Message; }
        }
    }

    void UpdateLegacyButton(bool running)
    {
        if (legacyRestore is null) return;
        legacyRestore.Visible = File.Exists(Path.Combine(Program.Home, "focus-fps.json"));
        legacyRestore.Enabled = startupComplete && !running;
    }

    void UpdateSettingsNotice(bool running)
    {
        settingsNotice.Text = running && settingsTabs.SelectedIndex != 3
            ? L("設定の保存はゲームを終了してから行えます。", "Close the game before saving these settings.") : "";
        settingsNotice.Visible = settingsNotice.Text.Length != 0;
    }

    Control BuildHelp()
    {
        var page = Stack();
        Heading(page, L("使い方と更新", "Guide and updates"));
        var links = Row();
        links.Controls.Add(ActionButton("README", () =>
        {
            string repo = Config()?["repository"]?.GetValue<string>() ?? Program.PublicRepository;
            if (!System.Text.RegularExpressions.Regex.IsMatch(repo, @"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"))
                throw new InvalidOperationException(Ui.T("GitHubの公開先設定が不正です。"));
            string doc = Ui.Japanese ? "README.md" : "README.en.md";
            var uri = $"https://github.com/{repo}/blob/main/{doc}";
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(uri) { UseShellExecute = true });
            return Task.CompletedTask;
        }));
        links.Controls.Add(ActionButton(Ui.T("最新版をダウンロード"), OpenReleases));
        page.Controls.Add(links);
        TextLine(page, L("更新するときはゲームと管理ツールを閉じ、新しいZIPをすべて展開してHudManager.exeを開きます。",
            "To update, close the game and this tool, extract the new ZIP, and open HudManager.exe."));
        Heading(page, L("困ったとき", "Troubleshooting"));
        TextLine(page, L("通常モードには「ホーム」から戻せます。描き込み中のFPS設定は「設定」→「画面への描き込み」にあります。",
            "Restore normal mode from Home. The drawing FPS options are under Settings → Drawing on screen."));
        var commands = Row();
        commands.Controls.Add(ActionButton(Ui.T("ファイルを確認"), async () => { await Run("verify"); }));
        commands.Controls.Add(ActionButton(Ui.T("画像を読み直す"), async () => { await Run("refresh-assets"); await RefreshStatus(); }));
        var confirm = Row();
        confirm.Controls.Add(ActionButton(L("切り替える", "Switch version"), async () =>
        {
            await Run("rollback"); Program.RestartRequested = true; Close();
        }));
        confirm.Controls.Add(ActionButton(L("キャンセル", "Cancel"), () => { confirm.Visible = false; return Task.CompletedTask; }, serialize: false));
        commands.Controls.Add(ActionButton(Ui.T("前の版へ戻す"), () =>
        {
            confirm.Visible = true;
            output.Text = L("前の版へ切り替えると管理ツールが開き直ります。", "The manager will reopen after switching to the previous version.");
            return Task.CompletedTask;
        }, serialize: false));
        helpWrite = new Panel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink };
        var maintenance = Stack(Padding.Empty);
        maintenance.Controls.Add(commands);
        maintenance.Controls.Add(confirm);
        helpWrite.Controls.Add(maintenance);
        page.Controls.Add(helpWrite);
        confirm.Visible = false;
        return ScrollPage(page);
    }

    Control BuildDisplay()
    {
        var page = Stack();
        TextLine(page, L("観戦・リプレイ中に、上部のキャラ欄へ表示する項目です。", "Choose what appears in the hero bar while spectating or watching a replay."));
        var player = Option(page, L("プレイヤー名を表示", "Show player names"));
        var hero = Option(page, L("キャラ名を表示", "Show hero names"));
        var teamLink = Row();
        teamLink.Controls.Add(ActionButton(L("チーム名・ロゴの設定", "Team names and logos"), () =>
        {
            settingsTabs.SelectedIndex = 2;
            return Task.CompletedTask;
        }, serialize: false));
        page.Controls.Add(teamLink);
        void Reset()
        {
            int flags = ReadRosterFlags();
            player.Checked = (flags & 1) != 0;
            hero.Checked = (flags & 2) != 0;
        }
        Reset();
        readDisplayEdits = () => (player.Checked ? 1 : 0) | (hero.Checked ? 2 : 0);
        resetSettings[0] = Reset;
        return ScrollPage(page);
    }

    Control BuildKeys()
    {
        var page = Stack();
        TextLine(page, L("入力欄を選んでキーを押します。Escでキー設定の編集を取り消せます。",
            "Focus a field and press the shortcut you want. Press Esc to undo key edits."));
        var shortcuts = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, Margin = Padding.Empty };
        shortcuts.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        shortcuts.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        KeyCapture Field(string caption, HudKey start)
        {
            int row = shortcuts.RowCount++;
            shortcuts.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            var field = new KeyCapture(start, valid =>
            {
                output.Text = valid ? "" : L("このキーは割り当てられません。", "This key cannot be assigned.");
            }) { AccessibleName = caption };
            var frame = InputFrame(field);
            frame.MaximumSize = new Size(240, 0);
            shortcuts.Controls.Add(new Label { Text = caption, AutoSize = true, Anchor = AnchorStyles.Left,
                Margin = new Padding(0, 3, 12, 3) }, 0, row);
            shortcuts.Controls.Add(frame, 1, row);
            return field;
        }

        var draw = Field(L("画面への描き込み", "Draw on screen"), keys.Drawing);
        var damage = Field(L("与ダメージ", "Damage Dealt"), keys.Damage);
        var graph = Field(L("ソウル差", "Soul Lead"), keys.Graph);
        page.Controls.Add(shortcuts);

        var drawingEnabled = Option(page, Ui.T("描き込みを有効にする（観戦・リプレイ中のみ）"));
        drawingEnabled.Checked = keys.DrawingEnabled;
        var defaults = Row();
        defaults.Controls.Add(ActionButton(L("キーを初期値に戻す", "Reset keys"), () =>
        {
            draw.ShowBinding(HudKey.DrawingDefault);
            damage.ShowBinding(HudKey.DamageDefault);
            graph.ShowBinding(HudKey.GraphDefault);
            return Task.CompletedTask;
        }, serialize: false));
        page.Controls.Add(defaults);
        void Reset()
        {
            draw.ShowBinding(keys.Drawing);
            damage.ShowBinding(keys.Damage);
            graph.ShowBinding(keys.Graph);
            drawingEnabled.Checked = keys.DrawingEnabled;
        }
        cancelKeys = () =>
        {
            Reset();
            output.Text = L("キー設定の編集を取り消しました。", "Key edits canceled.");
        };
        readKeyEdits = () => new HudKeys(draw.Binding, damage.Binding, graph.Binding, drawingEnabled.Checked);
        resetSettings[1] = Reset;
        return ScrollPage(page);
    }

    protected override bool ProcessCmdKey(ref Message msg, Keys keys)
    {
        if (keys == Keys.Escape && settingsPage?.Visible == true && settingsTabs.SelectedIndex == 1 && cancelKeys is { } cancel)
        {
            cancel();
            return true;
        }
        return base.ProcessCmdKey(ref msg, keys);
    }

    const string FocusOn = "engine_no_focus_sleep 0";
    const string FocusDefault = "engine_no_focus_sleep 20";

    Control BuildFocus()
    {
        var page = Stack();
        TextLine(page, L("観戦・リプレイ中に、ペンや矢印で画面に印を付けられます。「キー設定」で「描き込みを有効にする（観戦・リプレイ中のみ）」をオンにして保存し、ゲーム内で割り当てたキー（初期値 F8）を押してください。",
            "Use a pen or arrows to mark the screen while spectating or watching a replay. In Key bindings, select Enable drawing (spectating and replays only), save, and press the assigned key in the game (default: F8)."));
        Heading(page, L("描き込み中にFPSが下がるとき", "If FPS drops while drawing"));
        Command(L("FPS低下を抑えるコマンドをコピー", "Copy command to reduce FPS drops"), FocusOn);
        Command(L("標準に戻すコマンドをコピー", "Copy command to restore default"), FocusDefault);
        TextLine(page, L("コピーしたコマンドはゲーム内コンソールで実行します。隠れ家・観戦・リプレイではEscメニュー右側の「観戦HUD」からも選べます。",
            "Run the copied command in the game console. You can also use Spectator HUD on the right of the Esc menu in the Hideout, spectator sessions, and replays."));
        TextLine(page, L("値が0の間は、ゲームを背面にすると負荷が上がる場合があります。設定はゲーム終了後も残ることがあるため、配信や大会の後は「標準に戻す」（20）を選んでください。",
            "At 0, Deadlock may use more resources in the background. This setting can persist after the game closes, so select Restore default (20) after your stream or event."));
        legacyRestore = ActionButton(L("以前の試作で記録した値を復元して起動", "Launch once to restore the previous trial’s value"), RestoreLegacyFocus);
        var commands = Row();
        commands.Controls.Add(legacyRestore);
        page.Controls.Add(commands);
        legacyRestore.Visible = false;
        return ScrollPage(page);

        void Command(string title, string command)
        {
            var row = Stack(Padding.Empty);
            var value = new TextBox { Text = command, ReadOnly = true,
                AccessibleName = L("コンソールコマンド", "Console command") };
            var frame = InputFrame(value);
            frame.MaximumSize = new Size(335, 0);
            row.Controls.Add(frame);
            var buttons = Row();
            buttons.Controls.Add(ActionButton(title, () =>
            {
                Clipboard.SetText(command);
                output.Text = L("コマンドをコピーしました。", "Command copied.");
                return Task.CompletedTask;
            }, serialize: false));
            row.Controls.Add(buttons);
            page.Controls.Add(row);
        }
    }

    async Task SaveAllSettings()
    {
        if (GameRunning()) throw new InvalidOperationException(L("保存する前にゲームを終了してください。", "Close the game before saving."));

        var nextKeys = readKeyEdits?.Invoke() ?? keys;
        if (!nextKeys.IsValid)
        {
            settingsTabs.SelectedIndex = 1;
            throw new InvalidOperationException(L("各機能に別のキーを割り当ててください。", "Assign a different shortcut to each action."));
        }

        (string Json, int Flags)? teams;
        try { teams = readTeamEdits?.Invoke(); }
        catch (InvalidOperationException)
        {
            settingsTabs.SelectedIndex = 2;
            throw;
        }

        int currentFlags = ReadRosterFlags();
        int nextFlags = (readDisplayEdits?.Invoke() ?? (currentFlags & 3)) | (teams?.Flags ?? (currentFlags & 12));
        var files = new Dictionary<string, string>();
        if (nextFlags != currentFlags)
            files.Add("roster-display", nextFlags.ToString(System.Globalization.CultureInfo.InvariantCulture));
        if (nextKeys != keys)
            files.Add("hotkeys.json", nextKeys.ToJson());
        if (teams is { } team && team.Json != savedTeamSnapshot)
            files.Add("team-headings.json", team.Json);

        if (files.Count == 0)
        {
            output.Text = L("保存する変更はありません。", "No changes to save.");
            return;
        }

        SaveSettingsFiles(files);
        keys = nextKeys;
        if (teams is { } saved) savedTeamSnapshot = saved.Json;
        UpdateKeySummary();
        await RefreshStatus();
        output.Text = L("表示・キー設定・チーム／大会の変更を保存しました。",
            "Changes to Display, Key bindings, and Teams & tournament were saved.");
    }

    int ReadRosterFlags()
    {
        var path = Path.Combine(Program.Home, "roster-display");
        return File.Exists(path) && int.TryParse(File.ReadAllText(path), out int value) && value is >= 0 and <= 15 ? value : 2;
    }

    static void SaveSettingsFiles(Dictionary<string, string> files)
    {
        string suffix = "." + Guid.NewGuid().ToString("N");
        var staged = new List<(string Path, string Temp, string Backup, bool Existed)>();
        int committed = 0;
        bool restored = true;
        try
        {
            Directory.CreateDirectory(Program.Home);
            foreach (var (name, content) in files)
            {
                string path = Path.Combine(Program.Home, name);
                var entry = (Path: path, Temp: path + suffix + ".tmp", Backup: path + suffix + ".bak", Existed: File.Exists(path));
                staged.Add(entry);
                File.WriteAllText(entry.Temp, content, new UTF8Encoding(false));
            }

            foreach (var entry in staged)
            {
                if (entry.Existed)
                    File.Replace(entry.Temp, entry.Path, entry.Backup);
                else
                    File.Move(entry.Temp, entry.Path);
                committed++;
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            for (int index = staged.Count - 1; index >= 0; index--)
            {
                var entry = staged[index];
                try
                {
                    if (entry.Existed && File.Exists(entry.Backup)) File.Move(entry.Backup, entry.Path, true);
                    else if (!entry.Existed && index < committed) File.Delete(entry.Path);
                }
                catch (Exception recovery) when (recovery is IOException or UnauthorizedAccessException) { restored = false; }
            }
            string message = restored
                ? L("設定を保存できませんでした。もう一度お試しください。", "Could not save settings. Try again.")
                : L("設定の一部を元に戻せませんでした。復元用のファイルを残しています。",
                    "Some settings could not be restored. Backup files were kept.");
            throw new IOException(message, ex);
        }
        finally
        {
            foreach (var entry in staged)
            {
                CleanTemporaryFile(entry.Temp);
                if (restored) CleanTemporaryFile(entry.Backup);
            }
        }
    }

    static void CleanTemporaryFile(string path)
    {
        try { File.Delete(path); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { }
    }

    static FlowLayoutPanel Row() => new()
    {
        Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
        WrapContents = true, Margin = new Padding(0, 4, 0, 2)
    };

    static TableLayoutPanel Stack(Padding? padding = null)
    {
        var table = new TableLayoutPanel
        {
            Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            ColumnCount = 1, Margin = Padding.Empty, Padding = padding ?? new Padding(16, 12, 16, 12)
        };
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        return table;
    }

    static Panel ScrollPage(TableLayoutPanel content)
    {
        var page = new Panel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = SystemColors.Window };
        page.Controls.Add(content);
        return page;
    }

    static Panel InputFrame(Control input)
    {
        var frame = new Panel
        {
            Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = SystemColors.ControlDark, Margin = new Padding(0, 3, 6, 3), Padding = new Padding(1)
        };
        if (input is TextBoxBase field)
        {
            field.BorderStyle = BorderStyle.None;
            var surface = new Panel
            {
                Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
                BackColor = field.BackColor
            };
            surface.Controls.Add(field);
            surface.Click += (_, _) => field.Focus();
            field.Enter += (_, _) => frame.BackColor = SystemColors.Highlight;
            field.Leave += (_, _) => frame.BackColor = SystemColors.ControlDark;
            surface.Padding = new Padding(5, 3, 5, 3);
            frame.Controls.Add(surface);
        }
        else frame.Controls.Add(input);
        input.Dock = DockStyle.Top;
        return frame;
    }

    Button ActionButton(string text, Func<Task> action, bool serialize = true)
    {
        var button = new Button
        {
            Text = text, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            FlatStyle = FlatStyle.Flat, BackColor = SystemColors.Control,
            MinimumSize = new Size(0, 34), Padding = new Padding(10, 4, 10, 4), Margin = new Padding(0, 2, 8, 5)
        };
        void FitBorder()
        {
            button.FlatAppearance.BorderColor = SystemColors.ControlDark;
            button.FlatAppearance.BorderSize = Math.Max(1, button.LogicalToDeviceUnits(1));
        }
        button.HandleCreated += (_, _) => FitBorder();
        button.DpiChangedAfterParent += (_, _) => FitBorder();
        button.Click += async (_, _) =>
        {
            if (serialize) await Guard(action);
            else try { await action(); } catch (Exception e) { output.Text = e.Message; }
        };
        return button;
    }

    static CheckBox Option(TableLayoutPanel owner, string text)
    {
        var option = new CheckBox { Text = text, AutoSize = true, Margin = new Padding(0, 4, 0, 3) };
        owner.Controls.Add(option);
        return option;
    }

    static void TextLine(TableLayoutPanel owner, string text) => TextLine(owner, new Label { Text = text, AutoSize = true });

    static void TextLine(TableLayoutPanel owner, Label label)
    {
        label.Margin = new Padding(0, 3, 0, 5);
        Wrapped(owner, label);
    }

    static void Heading(TableLayoutPanel owner, string text)
    {
        var label = new Label { Text = text, AutoSize = true, Margin = new Padding(0, 7, 0, 3) };
        label.Font = new Font(SystemFonts.MessageBoxFont!.FontFamily, 12, FontStyle.Bold);
        Wrapped(owner, label);
    }

    static void Wrapped(TableLayoutPanel owner, Label label)
    {
        // Preferred width follows the scroll area after the native window is laid out.
        label.MaximumSize = new Size(540, 0);
        owner.SizeChanged += (_, _) => WrapLabel(label, owner, owner.Padding.Horizontal + 4);
        owner.Controls.Add(label);
    }

    static void WrapLabel(Label label, Control owner, int margin)
    {
        int width = Math.Max(100, owner.ClientSize.Width - margin);
        if (label.MaximumSize.Width != width) label.MaximumSize = new Size(width, 0);
    }
}
