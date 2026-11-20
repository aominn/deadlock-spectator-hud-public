
using System.Drawing.Imaging;
using System.Text.Json;

internal sealed record TeamHeading(string Name, byte[]? Icon, int[]? Bans = null, int? Size = null, int? BestOf = null, int? Wins = null);

internal sealed partial class ManagerForm
{
    Control BuildTeams()
    {
        var file = Path.Combine(Program.Home, "team-headings.json");
        var catalog = ReadBanHeroes();
        var eligible = catalog.Select(hero => hero.Id).ToHashSet();
        var page = Stack();
        TextLine(page, L("左右は観戦画面での位置です。名前やロゴを指定しない場合はゲーム標準の表示を使います。",
            "Left and right refer to the spectator HUD. Empty names and logos use the game's defaults."));
        var visibility = Row();
        var showNames = new CheckBox { Text = L("チーム名を表示", "Show team names"), AutoSize = true };
        var showIcons = new CheckBox { Text = L("チームロゴを表示", "Show team logos"), AutoSize = true };
        visibility.Controls.AddRange(new Control[] { showNames, showIcons });
        page.Controls.Add(visibility);

        var size = Selection(L("チーム名・ロゴの大きさ", "Team name and logo size"), 150);
        size.Items.AddRange(new object[] { L("小", "Small"), L("標準", "Standard"), L("大", "Large") });
        var format = Selection(L("大会ヘッダー", "Tournament header"), 135);
        format.Items.AddRange(new object[] { L("オフ", "Off"), "BO3", "BO5" });
        var options = Row();
        AddInput(options, size);
        AddInput(options, format);
        var wins = new ComboBox[2];
        var winFields = new Control[2];
        for (int side = 0; side < wins.Length; side++)
        {
            string caption = side == 0 ? L("左の取得本数", "Left wins") : L("右の取得本数", "Right wins");
            wins[side] = Selection(caption, 112);
            winFields[side] = AddInput(options, wins[side]);
        }
        format.SelectedIndexChanged += (_, _) => UpdateSeries();
        page.Controls.Add(options);

        var names = new TextBox[2];
        var icons = new byte[]?[2];
        var bans = new int[2][];
        var imageStatus = new Label[2];
        var banStatus = new Label[2];
        var banButtons = new Button[2];
        var teams = Row();
        var groups = new GroupBox[2];
        var teamPage = ScrollPage(page);
        var content = new Panel { Dock = DockStyle.Fill, BackColor = SystemColors.Window };
        content.Controls.Add(teamPage);
        var picker = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3,
            Padding = new Padding(16, 12, 16, 12), Visible = false };
        picker.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        picker.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        picker.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        picker.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        var pickerTitle = new Label { AutoSize = true, Margin = new Padding(3, 3, 3, 8) };
        picker.Controls.Add(pickerTitle, 0, 0);
        var heroes = new CheckedListBox { Dock = DockStyle.Fill, CheckOnClick = true, IntegralHeight = false,
            AccessibleName = L("BAN候補", "Available heroes for bans") };
        picker.Controls.Add(heroes, 0, 1);
        content.Controls.Add(picker);
        int? activeSide = null;
        var pickerButtons = Row();
        pickerButtons.Controls.Add(ActionButton(L("選択を適用", "Apply selections"), () =>
        {
            if (activeSide is not int side) return Task.CompletedTask;
            bans[side] = heroes.CheckedItems.Cast<BanHero>().Select(hero => hero.Id).ToArray();
            ClosePicker();
            RefreshTeam(side);
            banButtons[side].Focus();
            return Task.CompletedTask;
        }, serialize: false));
        pickerButtons.Controls.Add(ActionButton(L("選択を取り消す", "Cancel selection"), () =>
        {
            var side = activeSide;
            ClosePicker();
            if (side is int previous) banButtons[previous].Focus();
            return Task.CompletedTask;
        }, serialize: false));
        picker.Controls.Add(pickerButtons, 0, 2);
        heroes.KeyDown += (_, e) =>
        {
            if (e.KeyCode != Keys.Escape) return;
            e.Handled = true;
            e.SuppressKeyPress = true;
            var side = activeSide;
            ClosePicker();
            if (side is int previous) banButtons[previous].Focus();
        };
        heroes.ItemCheck += (_, change) =>
        {
            if (change.NewValue == CheckState.Checked && heroes.CheckedItems.Count >= 6)
            {
                change.NewValue = change.CurrentValue;
                output.Text = L("1チームにつき6体まで選べます。", "Select up to six heroes per team.");
            }
        };
        for (int side = 0; side < groups.Length; side++)
        {
            int index = side;
            string label = SideName(side);
            var group = new GroupBox { Text = label, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Margin = new Padding(0, 4, 5, 4) };
            var form = Stack(new Padding(7, 5, 7, 5));
            names[side] = new TextBox { MaxLength = 64, Dock = DockStyle.Top,
                AccessibleName = label + " " + L("チーム名", "team name"), PlaceholderText = L("チーム名", "Team name") };
            form.Controls.Add(InputFrame(names[side]));
            imageStatus[side] = new Label { AutoSize = true };
            var logos = Row();
            logos.Controls.Add(ActionButton(L("ロゴ画像を選ぶ", "Choose logo"), () =>
            {
                using var dialog = new OpenFileDialog { Filter = "PNG / JPEG|*.png;*.jpg;*.jpeg", CheckFileExists = true };
                if (dialog.ShowDialog(this) != DialogResult.OK) return Task.CompletedTask;
                try { icons[index] = LoadTeamIcon(dialog.FileName); RefreshTeam(index); }
                catch (Exception ex) when (ex is ArgumentException or IOException or UnauthorizedAccessException or OutOfMemoryException or System.Runtime.InteropServices.ExternalException)
                {
                    output.Text = L("8MB以下、4096×4096以下のPNGまたはJPEGを選択してください。", "Choose a PNG or JPEG up to 8 MB and 4096×4096 pixels.");
                }
                return Task.CompletedTask;
            }, serialize: false));
            logos.Controls.Add(ActionButton(L("ロゴを解除", "Clear logo"), () => { icons[index] = null; RefreshTeam(index); return Task.CompletedTask; }, serialize: false));
            form.Controls.Add(logos);
            TextLine(form, imageStatus[side]);
            var banRow = Row();
            banButtons[side] = ActionButton(L("BANを選ぶ", "Choose bans"), () => { OpenPicker(index); return Task.CompletedTask; }, serialize: false);
            banButtons[side].Enabled = catalog.Length > 0;
            banButtons[side].AccessibleName = label + " " + banButtons[side].Text;
            banRow.Controls.Add(banButtons[side]);
            banRow.Controls.Add(ActionButton(L("BANをクリア", "Clear bans"), () =>
            {
                bans[index] = Array.Empty<int>();
                if (activeSide is not null) ClosePicker();
                RefreshTeam(index);
                return Task.CompletedTask;
            }, serialize: false));
            form.Controls.Add(banRow);
            banStatus[side] = new Label { AutoSize = true };
            TextLine(form, banStatus[side]);
            group.Controls.Add(form);
            groups[side] = group;
            teams.Controls.Add(group);
        }
        teams.SizeChanged += (_, _) => FitTeams();
        page.Controls.Add(teams);
        FitTeams();
        if (catalog.Length == 0)
            TextLine(page, L("この版のBAN候補を確認できません。画像の再取得や版を確認してください。",
                "The BAN roster is unavailable. Check the installed version and files."));
        Reset();
        readTeamEdits = ReadEdits;
        resetSettings[2] = Reset;
        return content;

        static ComboBox Selection(string caption, int width)
        {
            var input = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDownList, DrawMode = DrawMode.OwnerDrawFixed,
                AccessibleName = caption, Width = width
            };
            void FitItems() => input.ItemHeight = input.LogicalToDeviceUnits(26);
            input.HandleCreated += (_, _) => FitItems();
            input.DpiChangedAfterParent += (_, _) => FitItems();
            input.DrawItem += (_, e) =>
            {
                if (e.Index < 0) return;
                e.DrawBackground();
                var bounds = e.Bounds;
                bounds.X += input.LogicalToDeviceUnits(4);
                bounds.Width -= input.LogicalToDeviceUnits(4);
                TextRenderer.DrawText(e.Graphics, input.GetItemText(input.Items[e.Index]), e.Font ?? input.Font,
                    bounds, e.ForeColor, TextFormatFlags.SingleLine | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix);
                e.DrawFocusRectangle();
            };
            return input;
        }

        static Control AddInput(FlowLayoutPanel row, ComboBox input)
        {
            var field = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown, WrapContents = false,
                AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Margin = new Padding(0, 0, 18, 3)
            };
            field.Controls.Add(new Label { Text = input.AccessibleName, AutoSize = true, Margin = new Padding(0, 3, 0, 2) });
            int inputWidth = input.Width;
            var frame = InputFrame(input);
            int width = inputWidth + frame.Padding.Horizontal;
            frame.Dock = DockStyle.None;
            frame.Width = width;
            frame.MinimumSize = frame.MaximumSize = new Size(width, 0);
            field.Controls.Add(frame);
            row.Controls.Add(field);
            return field;
        }

        void UpdateSeries()
        {
            bool enabled = format.SelectedIndex > 0;
            foreach (var field in winFields) field.Visible = enabled;
            int maximum = enabled ? format.SelectedIndex + 1 : 3;
            foreach (var input in wins)
            {
                int value = Math.Clamp(input.SelectedIndex, 0, maximum);
                input.Items.Clear();
                for (int count = 0; count <= maximum; count++) input.Items.Add(count);
                input.SelectedIndex = value;
            }
        }

        void FitTeams()
        {
            if (teams.Width <= 0) return;
            int minimum = LogicalToDeviceUnits(265);
            int available = teams.ClientSize.Width;
            int width = available >= 2 * minimum ? available / 2 - groups[0].Margin.Horizontal - 2 :
                available - groups[0].Margin.Horizontal - 2;
            foreach (var group in groups)
            {
                if (width <= 0 || group.MaximumSize.Width == width) continue;
                group.MinimumSize = new Size(width, 0);
                group.MaximumSize = new Size(width, 0);
            }
        }

        void OpenPicker(int side)
        {
            activeSide = side;
            pickerTitle.Text = SideName(side) + " · " + L("BAN候補（最大6体）", "Available bans (up to six)");
            heroes.BeginUpdate();
            try
            {
                heroes.Items.Clear();
                foreach (var hero in catalog.Where(hero => !bans[1 - side].Contains(hero.Id)))
                    heroes.Items.Add(hero, bans[side].Contains(hero.Id));
            }
            finally { heroes.EndUpdate(); }
            teamBanPickerOpen = true;
            settingsActions.Visible = false;
            teamPage.Visible = false;
            picker.Visible = true;
            picker.BringToFront();
            heroes.Focus();
        }

        void ClosePicker()
        {
            picker.Visible = false;
            teamPage.Visible = true;
            activeSide = null;
            teamBanPickerOpen = false;
            if (settingsTabs.SelectedIndex == 2) settingsActions.Visible = true;
        }

        void RefreshTeam(int side)
        {
            imageStatus[side].Text = icons[side] is null ? L("標準アイコン", "Default icon") : L("ロゴ画像を設定済み", "Custom logo selected");
            var chosen = catalog.Where(hero => bans[side].Contains(hero.Id)).Select(hero => hero.Name).ToArray();
            banStatus[side].Text = chosen.Length == 0 ? L("BANの指定なし", "No bans selected")
                : string.Join(L("、", ", "), chosen);
        }

        void Reset()
        {
            var saved = LoadTeamSettings(file);
            int flags = ReadRosterFlags();
            showNames.Checked = (flags & 4) != 0;
            showIcons.Checked = (flags & 8) != 0;
            size.SelectedIndex = saved[0].Size is >= 0 and <= 2 ? saved[0].Size.GetValueOrDefault() : 1;
            format.SelectedIndex = saved[0].BestOf switch { 3 => 1, 5 => 2, _ => 0 };
            UpdateSeries();
            ClosePicker();
            for (int side = 0; side < groups.Length; side++)
            {
                names[side].Text = saved[side].Name;
                icons[side] = saved[side].Icon;
                bans[side] = saved[side].Bans?.Where(id => catalog.Length == 0 || eligible.Contains(id)).Distinct().Take(6).ToArray() ?? Array.Empty<int>();
                wins[side].SelectedIndex = Math.Clamp(saved[side].Wins ?? 0, 0, wins[side].Items.Count - 1);
                RefreshTeam(side);
            }
            savedTeamSnapshot = ReadTeamJson();
        }

        (string Json, int Flags) ReadEdits()
        {
            if (format.SelectedIndex > 0 && wins.All(input => input.SelectedIndex == input.Items.Count - 1))
                throw new InvalidOperationException(L("両チームを勝利に必要な本数に設定できません。", "Both teams cannot have the wins needed to take the series."));
            if (activeSide is not null)
                throw new InvalidOperationException(L("BANの選択を適用するか、取り消してから保存してください。", "Apply or cancel the BAN selection before saving."));
            return (ReadTeamJson(), (showNames.Checked ? 4 : 0) | (showIcons.Checked ? 8 : 0));
        }

        string ReadTeamJson()
        {
            int bestOf = format.SelectedIndex == 0 ? 0 : 2 * format.SelectedIndex + 1;
            var teams = names.Select((name, side) => new TeamHeading(name.Text.Trim(), icons[side], bans[side],
                size.SelectedIndex, side == 0 ? bestOf : null, wins[side].SelectedIndex)).ToArray();
            return JsonSerializer.Serialize(teams);
        }
    }

    static string SideName(int side) => side == 0 ? L("左チーム", "Left team") : L("右チーム", "Right team");

    static TeamHeading[] LoadTeamSettings(string path)
    {
        try
        {
            var file = new FileInfo(path);
            if (file.Exists && file.Length <= 256 * 1024 &&
                JsonSerializer.Deserialize<TeamHeading[]>(File.ReadAllText(path)) is { Length: 2 } loaded &&
                loaded.All(team => team is not null && team.Name is { Length: <= 64 } &&
                    (team.Icon is null || team.Icon.Length <= 64 * 1024)))
                return loaded;
        }
        catch (JsonException) { }
        return new[] { new TeamHeading("", null), new TeamHeading("", null) };
    }

    sealed record BanHero(int Id, string Name)
    {
        public override string ToString() => Name;
    }

    BanHero[] ReadBanHeroes()
    {
        string path = Path.Combine(bundle, "engine", "ban-heroes.json");
        if (!File.Exists(path)) return Array.Empty<BanHero>();
        using var catalog = JsonDocument.Parse(File.ReadAllText(path));
        return catalog.RootElement.EnumerateObject()
            .Select(hero => new BanHero(int.Parse(hero.Name), hero.Value.GetProperty(Ui.Japanese ? "ja" : "en").GetString()!))
            .OrderBy(hero => hero.Name, StringComparer.CurrentCulture).ToArray();
    }

    static byte[] LoadTeamIcon(string filename)
    {
        if (new FileInfo(filename).Length > 8 * 1024 * 1024) throw new ArgumentException("Image file is too large.");
        using var input = Image.FromFile(filename);
        if (input.Width > 4096 || input.Height > 4096 ||
            (input.RawFormat.Guid != ImageFormat.Png.Guid && input.RawFormat.Guid != ImageFormat.Jpeg.Guid))
            throw new ArgumentException("Image format or dimensions are unsupported.");
        const int size = 96;
        double scale = (double)size / Math.Max(input.Width, input.Height);
        int width = Math.Max(1, (int)Math.Round(input.Width * scale));
        int height = Math.Max(1, (int)Math.Round(input.Height * scale));
        using var output = new Bitmap(size, size, PixelFormat.Format32bppArgb);
        using (var graphics = Graphics.FromImage(output))
        {
            graphics.Clear(Color.Transparent);
            graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
            graphics.DrawImage(input, (size - width) / 2, (size - height) / 2, width, height);
        }
        using var png = new MemoryStream();
        output.Save(png, ImageFormat.Png);
        return png.ToArray();
    }
}
