
using System.Drawing.Imaging;
using System.Text.Json;

internal sealed record TeamHeading(string Name, byte[]? Icon, int[]? Bans = null, int? Size = null, int? BestOf = null, int? Wins = null);

internal sealed partial class ManagerForm
{
    Task ShowTeamSettings()
    {
        var closeGame = L("チーム設定を変更する前にゲームを終了してください。", "Close the game before changing team settings.");
        if (GameRunning()) throw new InvalidOperationException(closeGame);

        var path = Path.Combine(Program.Home, "team-headings.json");
        var saved = new[] { new TeamHeading("", null), new TeamHeading("", null) };
        try
        {
            var file = new FileInfo(path);
            if (file.Exists && file.Length <= 256 * 1024 &&
                JsonSerializer.Deserialize<TeamHeading[]>(File.ReadAllText(path)) is { Length: 2 } loaded &&
                loaded.All(team => team is not null && team.Name is { Length: <= 64 } &&
                    (team.Icon is null || team.Icon.Length <= 64 * 1024)))
                saved = loaded;
        }
        catch (JsonException) { }

        using var dialog = new Form
        {
            Text = L("チーム設定", "Team settings"), ClientSize = new Size(550, 508),
            StartPosition = FormStartPosition.CenterParent, Font = Font,
            FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false
        };
        var layout = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown,
            WrapContents = false, Padding = new Padding(16), AutoScroll = true
        };
        dialog.Controls.Add(layout);
        layout.Controls.Add(new Label
        {
            Text = L("画面上部の左右に表示する名前と画像です。未指定の項目はゲーム標準です。表示する項目は「表示設定」で選びます。",
                     "Set names and icons for the left and right teams. Empty fields use the game defaults. Choose which fields to show in Display settings."),
            AutoSize = true, MaximumSize = new Size(505, 0)
        });
        var sizeRow = Row();
        var size = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 145 };
        size.Items.AddRange(new object[] { L("小", "Small"), L("標準", "Standard"), L("大", "Large") });
        size.SelectedIndex = saved[0].Size is >= 0 and <= 2 ? saved[0].Size.GetValueOrDefault() : 1;
        sizeRow.Controls.Add(new Label { Text = L("チーム名・アイコンの大きさ", "Team name and icon size"), AutoSize = true, Margin = new Padding(2, 6, 8, 0) });
        sizeRow.Controls.Add(size);
        layout.Controls.Add(sizeRow);
        var series = Row();
        var format = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 125,
            AccessibleName = L("大会ヘッダー", "Tournament header") };
        format.Items.AddRange(new object[] { L("オフ", "Off"), "BO3", "BO5" });
        format.SelectedIndex = saved[0].BestOf switch { 3 => 1, 5 => 2, _ => 0 };
        series.Controls.Add(new Label { Text = format.AccessibleName, AutoSize = true, Margin = new Padding(2, 6, 8, 0) });
        series.Controls.Add(format);
        layout.Controls.Add(series);
        var score = Row();
        var wins = new NumericUpDown[2];
        for (int side = 0; side < wins.Length; side++)
        {
            string caption = side == 0 ? L("左の取得本数", "Left wins") : L("右の取得本数", "Right wins");
            wins[side] = new NumericUpDown { Width = 48, Maximum = 3, AccessibleName = caption,
                Value = Math.Clamp(saved[side].Wins ?? 0, 0, 3) };
            score.Controls.Add(new Label { Text = caption, AutoSize = true, Margin = new Padding(2, 6, 6, 0) });
            score.Controls.Add(wins[side]);
        }
        void RefreshSeries()
        {
            score.Enabled = format.SelectedIndex != 0;
            if (!score.Enabled) return;
            foreach (var input in wins) input.Maximum = format.SelectedIndex + 1;
        }
        format.SelectedIndexChanged += (_, _) => RefreshSeries();
        RefreshSeries();
        layout.Controls.Add(score);
        var names = new TextBox[2];
        var icons = saved.Select(team => team.Icon).ToArray();
        var catalog = ReadBanHeroes();
        var eligibleBans = catalog.Select(hero => hero.Id).ToHashSet();
        var bans = saved.Select(team => team.Bans?.Where(eligibleBans.Contains).Distinct().Take(6).ToArray() ?? Array.Empty<int>()).ToArray();
        for (int side = 0; side < 2; side++)
        {
            int index = side;
            var group = new GroupBox
            {
                Text = side == 0 ? L("左チーム", "Left team") : L("右チーム", "Right team"),
                Size = new Size(505, 126)
            };
            var name = new TextBox { Text = saved[side].Name, MaxLength = 64, Width = 455,
                Location = new Point(10, 23), AccessibleName = group.Text + " " + L("チーム名", "team name"),
                PlaceholderText = L("ゲーム標準のチーム名", "Default team name") };
            group.Controls.Add(name);
            names[side] = name;
            var select = new Button { Text = L("画像を選ぶ", "Choose image"), AutoSize = true, Location = new Point(10, 54) };
            var clear = new Button { Text = L("標準に戻す", "Use default"), AutoSize = true, Location = new Point(126, 54) };
            var status = new Label { AutoSize = true, Location = new Point(242, 59) };
            void RefreshIcon() => status.Text = icons[index] is null ? L("標準アイコン", "Default icon") : L("画像を設定済み", "Custom image selected");
            RefreshIcon();
            select.Click += (_, _) =>
            {
                using var picker = new OpenFileDialog { Filter = "PNG / JPEG|*.png;*.jpg;*.jpeg", CheckFileExists = true };
                if (picker.ShowDialog(dialog) != DialogResult.OK) return;
                try
                {
                    icons[index] = LoadTeamIcon(picker.FileName);
                    RefreshIcon();
                }
                catch (Exception ex) when (ex is ArgumentException or IOException or UnauthorizedAccessException or OutOfMemoryException or System.Runtime.InteropServices.ExternalException)
                {
                    MessageBox.Show(dialog, L("8MB以下、4096×4096以下のPNGまたはJPEGを選択してください。",
                        "Choose a PNG or JPEG up to 8 MB and 4096×4096 pixels."), dialog.Text);
                }
            };
            clear.Click += (_, _) => { icons[index] = null; RefreshIcon(); };
            group.Controls.Add(select);
            group.Controls.Add(clear);
            group.Controls.Add(status);
            var chooseBans = new Button { Text = L("BANを選ぶ", "Choose bans"), AutoSize = true, Location = new Point(10, 86), Enabled = catalog.Length > 0 };
            var clearBans = new Button { Text = L("BANをクリア", "Clear bans"), AutoSize = true, Location = new Point(126, 86) };
            var banStatus = new Label { AutoSize = true, Location = new Point(242, 91) };
            void RefreshBans() => banStatus.Text = L($"{bans[index].Length}体を設定", $"{bans[index].Length} selected");
            RefreshBans();
            chooseBans.Click += (_, _) =>
            {
                var other = bans[1 - index];
                if (PickBans(dialog, catalog.Where(hero => !other.Contains(hero.Id)).ToArray(), bans[index]) is { } selected)
                    bans[index] = selected;
                RefreshBans();
            };
            clearBans.Click += (_, _) => { bans[index] = Array.Empty<int>(); RefreshBans(); };
            group.Controls.Add(chooseBans);
            group.Controls.Add(clearBans);
            group.Controls.Add(banStatus);
            layout.Controls.Add(group);
        }
        var buttons = Row();
        var save = new Button { Text = L("保存", "Save"), AutoSize = true, DialogResult = DialogResult.OK };
        var cancel = new Button { Text = L("キャンセル", "Cancel"), AutoSize = true, DialogResult = DialogResult.Cancel };
        buttons.Controls.Add(save);
        save.Click += (_, _) =>
        {
            if (format.SelectedIndex == 0 || !wins.All(input => input.Value == input.Maximum)) return;
            dialog.DialogResult = DialogResult.None;
            MessageBox.Show(dialog, L("両チームを勝利に必要な本数に設定することはできません。",
                "Both teams cannot reach the winning score."), dialog.Text);
        };
        buttons.Controls.Add(cancel);
        layout.Controls.Add(buttons);
        dialog.AcceptButton = save;
        dialog.CancelButton = cancel;
        if (dialog.ShowDialog(this) != DialogResult.OK) return Task.CompletedTask;
        if (GameRunning()) throw new InvalidOperationException(closeGame);

        int bestOf = format.SelectedIndex == 0 ? 0 : 2 * format.SelectedIndex + 1;
        var settings = names.Select((name, index) => new TeamHeading(name.Text.Trim(), icons[index], bans[index],
            size.SelectedIndex, index == 0 ? bestOf : null, (int)wins[index].Value)).ToArray();
        Directory.CreateDirectory(Program.Home);
        var temp = path + "." + Guid.NewGuid().ToString("N");
        try
        {
            File.WriteAllText(temp, JsonSerializer.Serialize(settings));
            File.Move(temp, path, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
        return Task.CompletedTask;
    }

    sealed record BanHero(int Id, string Name)
    {
        public override string ToString() => Name;
    }

    BanHero[] ReadBanHeroes()
    {
        using var catalog = JsonDocument.Parse(File.ReadAllText(Path.Combine(bundle, "engine", "ban-heroes.json")));
        return catalog.RootElement.EnumerateObject()
            .Select(hero => new BanHero(int.Parse(hero.Name), hero.Value.GetProperty(Ui.Japanese ? "ja" : "en").GetString()!))
            .OrderBy(hero => hero.Name, StringComparer.CurrentCulture).ToArray();
    }

    int[]? PickBans(Form owner, BanHero[] catalog, int[] chosen)
    {
        using var picker = new Form
        {
            Text = L("このチームがBANしたヒーロー", "Heroes banned by this team"),
            ClientSize = new Size(345, 420), StartPosition = FormStartPosition.CenterParent, Font = Font,
            FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false
        };
        var heroes = new CheckedListBox { Dock = DockStyle.Fill, CheckOnClick = true, IntegralHeight = false };
        foreach (var hero in catalog) heroes.Items.Add(hero, chosen.Contains(hero.Id));
        heroes.ItemCheck += (_, change) =>
        {
            if (change.NewValue == CheckState.Checked && heroes.CheckedItems.Count >= 6)
                change.NewValue = change.CurrentValue;
        };
        var hint = new Label { Text = L("最大6体。相手側で選択済みのヒーローは除きます。", "Up to 6. Heroes selected by the other side are omitted."), Dock = DockStyle.Top, Height = 32 };
        var buttons = Row();
        buttons.Dock = DockStyle.Bottom;
        var apply = new Button { Text = L("適用", "Apply"), AutoSize = true, DialogResult = DialogResult.OK };
        var cancel = new Button { Text = L("キャンセル", "Cancel"), AutoSize = true, DialogResult = DialogResult.Cancel };
        buttons.Controls.Add(apply);
        buttons.Controls.Add(cancel);
        picker.Controls.Add(heroes);
        picker.Controls.Add(hint);
        picker.Controls.Add(buttons);
        picker.AcceptButton = apply;
        picker.CancelButton = cancel;
        return picker.ShowDialog(owner) == DialogResult.OK
            ? heroes.CheckedItems.Cast<BanHero>().Select(hero => hero.Id).ToArray() : null;
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
