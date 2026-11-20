using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using System.Windows.Forms;

internal sealed record DrawingContext(string Epoch, RectangleF? Map, bool Active = true);
internal sealed class DrawingController : IDisposable
{
    const string Route = "http://127.0.0.1:49647/drawing-state?token=spec-debuff-local-8a71";
    readonly HttpClient http = new(new HttpClientHandler { UseProxy = false }) { Timeout = TimeSpan.FromSeconds(1) };
    readonly System.Windows.Forms.Timer timer = new() { Interval = 16 };
    readonly HotkeyWindow hotkey;
    readonly Func<IntPtr, bool> targetCheck;
    readonly Func<Task<DrawingContext?>>? contextReader;
    readonly Func<IntPtr> foregroundWindow;
    readonly Action<IntPtr> activateWindow;
    readonly Action<string> status;
    readonly InkModel model = new();
    DrawingContext? context;
    string? inkEpoch;
    PointF? toolbarAnchor;
    InkCanvas? canvas;
    InkToolbar? toolbar;
    IntPtr target;
    bool enabled, registered, polling, uploading, disposed, hotkeyFailure;
    HudKey key = HudKey.DrawingDefault;
    long sequence, incarnation, uploadedRevision = -1;
    DateTime checkedAt = DateTime.MinValue, contextSucceededAt = DateTime.MinValue, uploadSucceededAt = DateTime.MinValue, uploadedAt = DateTime.MinValue;
    Rectangle lastBounds;
    public DrawingController(Action<string> status, Func<IntPtr, bool>? targetCheck = null,
        Func<Task<DrawingContext?>>? contextReader = null, Func<IntPtr>? foregroundWindow = null, Action<IntPtr>? activateWindow = null)
    {
        this.status = status; this.targetCheck = targetCheck ?? IsDeadlock; this.contextReader = contextReader;
        this.foregroundWindow = foregroundWindow ?? Native.GetForegroundWindow;
        this.activateWindow = activateWindow ?? (window => Native.SetForegroundWindow(window));
        hotkey = new HotkeyWindow(id => { if (id == 51) ToggleToolbar(); else if (id == 52) PauseDrawing(); }); timer.Tick += async (_, _) => await Tick(); timer.Start();
    }
    public void Configure(bool enabled, HudKey key)
    {
        if (this.key != key) { Unregister(); this.key = key; hotkeyFailure = false; }
        if (!this.enabled && enabled) hotkeyFailure = false;
        this.enabled = enabled;
        if (!enabled) { End(); Unregister(); }
    }
    async Task Tick()
    {
        if (disposed) return;
        if (!enabled) return;
        var foreground = Native.GetForegroundWindow();
        bool ours = Owns(foreground);
        if (!ours && !targetCheck(foreground)) { HideToolbar(false); Unregister(); }
        if (DateTime.UtcNow - checkedAt > TimeSpan.FromMilliseconds(150) && !polling)
        {
            polling = true; checkedAt = DateTime.UtcNow;
            try
            {
                var next = contextReader != null ? await contextReader() : await ReadContext();
                if (disposed || !enabled) return;
                if (next == null) End(true, Ui.T("観戦画面の切替を確認し、線を消去しました。"));
                else if (inkEpoch != null && next != null && next.Epoch != inkEpoch) End(true, Ui.T("試合や時刻の切替を確認し、描画を終了しました。"));
                else if (next != null && !next.Active) HideToolbar(false);
                context = next; contextSucceededAt = DateTime.UtcNow;
            }
            catch { if (!KeepContextOnFailure(contextSucceededAt, DateTime.UtcNow)) { HideToolbar(false); context = context is null ? null : context with { Active = false }; } }
            finally { polling = false; }
        }
        if (context == null || !context.Active) { Unregister(); return; }
        foreground = Native.GetForegroundWindow();
        ours = Owns(foreground);
        if (!ours && !targetCheck(foreground)) { HideToolbar(false); Unregister(); if (model.Revision != uploadedRevision && inkEpoch != null) await Upload(true); return; }
        if (!registered && !hotkeyFailure)
        {
            registered = Native.RegisterHotKey(hotkey.Handle, 51, 0x4000u | (uint)key.Modifiers, (uint)key.Code);
            if (!registered) { hotkeyFailure = true; status(Ui.T("描画キーを登録できません（Windows ") + Marshal.GetLastWin32Error() + Ui.T("）。別のキーを選ぶか、描画をいったん切り替えてください。")); }
        }
        if (toolbar != null)
        {
            if (Native.IsIconic(target) || !Native.ClientBounds(target, out var bounds)) { HideToolbar(); return; }
            MoveToGame(bounds);
        }
        if (canvas == null) { if (model.Revision != uploadedRevision && inkEpoch != null) await Upload(true); return; }
        canvas.Present(model, context.Map);
        if (model.Revision != uploadedRevision && DateTime.UtcNow - uploadedAt > TimeSpan.FromMilliseconds(50)) await Upload(true);
    }
    async Task<DrawingContext?> ReadContext()
    {
        var data = JsonNode.Parse(await http.GetStringAsync(Route));
        if (data?["epoch"]?.GetValue<string>() is not string epoch) return null;
        bool active = data["active"]?.GetValue<bool>() == true;
        if (!active) return data["retained"]?.GetValue<bool>() == true ? new(epoch, context?.Map, false) : null;
        RectangleF? map = null;
        if (data["viewport"]?["map"] is JsonArray values && values.Count == 4)
            map = new(values[0]!.GetValue<float>(), values[1]!.GetValue<float>(), values[2]!.GetValue<float>(), values[3]!.GetValue<float>());
        return new(epoch, map);
    }
    bool Owns(IntPtr window) => window == canvas?.Handle || window == toolbar?.Handle;
    bool CanUseContext() => enabled && context?.Active == true && DateTime.UtcNow - contextSucceededAt <= TimeSpan.FromSeconds(3);
    void ToggleToolbar()
    {
        if (toolbar != null)
        {
            if (canvas == null) ToggleDrawing();
            else HideToolbar();
            return;
        }
        var foreground = Native.GetForegroundWindow();
        if (!CanUseContext() || !targetCheck(foreground) || !Native.ClientBounds(foreground, out var bounds)) return;
        target = foreground; lastBounds = bounds;
        toolbar = new InkToolbar(model, ToggleDrawing, PauseDrawing, HideToolbar);
        int dpi = Native.WindowDpi(target);
        toolbar.FitToGame(bounds.Size, dpi);
        toolbar.Location = ToolbarLocation(bounds, toolbar.Size, toolbarAnchor, dpi);
        toolbar.Show();
        toolbar.BringToFront(); toolbar.Activate();
        ToggleDrawing();
    }
    void ToggleDrawing()
    {
        if (canvas != null) { PauseDrawing(); return; }
        if (toolbar == null || !CanUseContext() || !Native.IsWindow(target) || Native.IsIconic(target) || !targetCheck(target) || !Native.ClientBounds(target, out var bounds)) return;
        var foreground = Native.GetForegroundWindow();
        if (!Owns(foreground) && foreground != target) return;
        MoveToGame(bounds); if (inkEpoch != context!.Epoch) model.Clear(); inkEpoch = context.Epoch; incarnation++; uploadedRevision = -1; uploadSucceededAt = DateTime.UtcNow;
        Native.RegisterHotKey(hotkey.Handle, 52, 0x4000, 0x1B);
        canvas = new InkCanvas(bounds, model, () => context?.Map, PauseDrawing);
        canvas.Show(); canvas.Present(model, context.Map); toolbar.Owner = canvas; toolbar.SetDrawing(true);
        canvas.Activate(); toolbar.BringToFront(); status(Ui.T("描き込み中。「ゲーム操作へ」またはEscで戻れます。割り当てたキーでツールバーを隠せます。"));
        _ = Upload(true);
    }
    void MoveToGame(Rectangle bounds)
    {
        if (toolbar == null) return;
        int dpi = Native.WindowDpi(target);
        var anchor = ToolbarAnchor(lastBounds, toolbar.Bounds);
        if (!toolbar.FitToGame(bounds.Size, dpi) && bounds == lastBounds) return;
        if (bounds != lastBounds) canvas?.SetGameBounds(bounds);
        lastBounds = bounds;
        toolbar.Location = ToolbarLocation(bounds, toolbar.Size, anchor, dpi);
    }

    internal static PointF ToolbarAnchor(Rectangle game, Rectangle tool)
    {
        return new(
            Math.Clamp((tool.Left - game.Left) / (float)Math.Max(1, game.Width - tool.Width), 0, 1),
            Math.Clamp((tool.Top - game.Top) / (float)Math.Max(1, game.Height - tool.Height), 0, 1));
    }

    internal static Point ToolbarLocation(Rectangle game, Size tool, PointF? anchor, int dpi)
    {
        int horizontal = Math.Max(0, game.Width - tool.Width);
        int vertical = Math.Max(0, game.Height - tool.Height);
        int x = anchor is { } relative ? (int)Math.Round(horizontal * relative.X) : horizontal / 2;
        int y = anchor is { } saved ? (int)Math.Round(vertical * saved.Y) : vertical - 24 * dpi / 96;
        return new(game.Left + Math.Clamp(x, 0, horizontal), game.Top + Math.Clamp(y, 0, vertical));
    }

    async Task Upload(bool drawing, string? epoch = null)
    {
        if (contextReader != null) { uploadedRevision = model.Revision; return; }
        if (uploading || disposed) return;
        var scope = epoch ?? context?.Epoch; if (scope == null) return;
        uploading = true; uploadedAt = DateTime.UtcNow; long revision = model.Revision;
        var payload = new { epoch = scope, sequence = sequence++, drawing, strokes = drawing ? model.Payload() : Array.Empty<object>() };
        try
        {
            using var content = EncodeSnapshot(payload);
            using var result = await http.PostAsync(Route, content);
            if (!result.IsSuccessStatusCode && drawing && ((int)result.StatusCode < 500 || !KeepContextOnFailure(uploadSucceededAt, DateTime.UtcNow))) { HideToolbar(false); context = context is null ? null : context with { Active = false }; }
            if (result.IsSuccessStatusCode) { uploadedRevision = revision; if (drawing) uploadSucceededAt = DateTime.UtcNow; }
        }
        catch { if (drawing && !KeepContextOnFailure(uploadSucceededAt, DateTime.UtcNow)) { HideToolbar(false); context = context is null ? null : context with { Active = false }; } }
        finally { uploading = false; }
    }
    // Explicit byte length keeps the local bounded HTTP reader and .NET sender interoperable.
    internal static HttpContent EncodeSnapshot(object payload) => new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
    internal static bool SameMap(RectangleF? left, RectangleF? right) => left == null || right == null ? left == right : Math.Abs(left.Value.X - right.Value.X) <= .001f && Math.Abs(left.Value.Y - right.Value.Y) <= .001f && Math.Abs(left.Value.Width - right.Value.Width) <= .001f && Math.Abs(left.Value.Height - right.Value.Height) <= .001f;
    internal static bool KeepContextOnFailure(DateTime lastSuccess, DateTime now) => now >= lastSuccess && now - lastSuccess <= TimeSpan.FromSeconds(3);
    void ReturnGameFocus()
    {
        if (!Owns(foregroundWindow()) || !Native.IsWindow(target) || Native.IsIconic(target) || !targetCheck(target)) return;
        // Request focus while an overlay still owns it, before Windows picks another window when the overlay closes.
        activateWindow(target);
    }
    void End() => End(true);
    void PauseDrawing() => PauseDrawing(true);
    void PauseDrawing(bool restoreFocus)
    {
        model.End();
        if (restoreFocus) ReturnGameFocus();
        if (canvas == null) return;
        Native.UnregisterHotKey(hotkey.Handle, 52);
        var old = canvas;
        if (toolbar != null) toolbar.Owner = null; // Keep the toolbar alive when its drawing surface closes.
        canvas = null; old.Dispose(); toolbar?.SetDrawing(false);
        status(Ui.T("ゲーム操作に戻りました。線は残ります。割り当てたキーまたは「描く」で再開できます。"));
    }
    void HideToolbar() => HideToolbar(true);
    void HideToolbar(bool restoreFocus)
    {
        if (restoreFocus) ReturnGameFocus();
        PauseDrawing(false);
        if (toolbar != null)
        {
            toolbarAnchor = ToolbarAnchor(lastBounds, toolbar.Bounds);
            var old = toolbar; toolbar = null; old.Dispose();
        }
    }
    void End(bool restoreFocus = true, string? reason = null)
    {
        var scope = inkEpoch; long ended = ++incarnation;
        HideToolbar(restoreFocus); model.Clear(); inkEpoch = null;
        if (scope != null && contextReader == null) _ = ClearAfterUpload(scope, ended);
        if (scope != null) status(reason ?? Ui.T("線を消去しました。"));
    }
    async Task ClearAfterUpload(string scope, long ended)
    {
        for (int n = 0; uploading && n < 60 && !disposed; n++) await Task.Delay(20);
        if (!disposed && incarnation == ended) await Upload(false, scope);
    }
    void Unregister() { if (registered) { Native.UnregisterHotKey(hotkey.Handle, 51); registered = false; } }
    static bool IsDeadlock(IntPtr handle)
    {
        if (handle == IntPtr.Zero) return false;
        Native.GetWindowThreadProcessId(handle, out uint pid);
        try { using var process = Process.GetProcessById((int)pid); return process.ProcessName.Equals("deadlock", StringComparison.OrdinalIgnoreCase); }
        catch { return false; }
    }
    public void Dispose()
    {
        if (disposed) return;
        End(false); Unregister(); disposed = true; timer.Dispose(); hotkey.DestroyHandle(); http.Dispose();
    }
    sealed class HotkeyWindow : NativeWindow
    {
        readonly Action<int> action;
        public HotkeyWindow(Action<int> action) { this.action = action; CreateHandle(new CreateParams()); }
        protected override void WndProc(ref Message m) { if (m.Msg == 0x312) action(m.WParam.ToInt32()); base.WndProc(ref m); }
    }
}

internal sealed class InkCanvas : Form
{
    readonly InkModel model; readonly Func<RectangleF?> map; readonly Action finish;
    long painted = -1;
    RectangleF? paintedMap;
    public InkCanvas(Rectangle bounds, InkModel model, Func<RectangleF?> map, Action finish)
    {
        this.model = model; this.map = map; this.finish = finish;
        FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = true; TopMost = true; StartPosition = FormStartPosition.Manual; Bounds = bounds; KeyPreview = true; Cursor = Cursors.Cross;
        Text = Ui.T("観戦HUD 描画");
        FormClosing += (_, e) => { e.Cancel = true; if (!IsDisposed) BeginInvoke(finish); };
        MouseDown += (_, e) => { if (e.Button == MouseButtons.Right) model.Undo(); else if (e.Button == MouseButtons.Left) { Capture = true; model.Begin(Normal(e.Location), map()); } };
        MouseMove += (_, e) => { if (Capture) model.Move(Normal(e.Location), map()); };
        MouseUp += (_, e) => { if (e.Button == MouseButtons.Left) { model.End(); Capture = false; } };
        MouseCaptureChanged += (_, _) => { if (!Capture) model.End(); };
        KeyDown += (_, e) => { if (e.KeyCode == Keys.Escape) { e.Handled = true; finish(); } else if (e.Control && e.KeyCode == Keys.Z) { e.Handled = true; model.Undo(); } };
    }
    PointF Normal(Point p) => new(p.X / (float)ClientSize.Width, p.Y / (float)ClientSize.Height);
    public void SetGameBounds(Rectangle bounds)
    {
        model.End();
        Capture = false;
        Bounds = bounds;
        painted = -1;
    }
    protected override CreateParams CreateParams { get { var p = base.CreateParams; p.ExStyle |= 0x80000; return p; } }
    public void Present(InkModel model, RectangleF? map)
    {
        if (IsDisposed || !Visible || (painted == model.Revision &&
            (DrawingController.SameMap(paintedMap, map) || !model.Strokes.Any(stroke => stroke.Space == "map")))) return;
        using var bitmap = new Bitmap(ClientSize.Width, ClientSize.Height, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bitmap)) { g.Clear(Color.FromArgb(1, 0, 0, 0)); model.Paint(g, bitmap.Size, map); }
        Native.Present(Handle, bitmap, Location);
        painted = model.Revision; paintedMap = map;
    }
}
internal sealed class InkToolbar : Form
{
    readonly ToolTip tips = new();
    readonly Button mode;
    readonly FlowLayoutPanel row;
    readonly List<(Control Control, int Width)> sizes = new();
    Font? toolbarFont;
    Font DrawingFont => toolbarFont ?? Font;
    float scale;
    bool drawing;
    public InkToolbar(InkModel model, Action toggle, Action pause, Action close)
    {
        AutoScaleMode = AutoScaleMode.None;
        Text = Ui.T("描画ツール"); Font = new Font(Ui.Japanese ? "Yu Gothic UI" : "Segoe UI", 9); FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = true; TopMost = true; StartPosition = FormStartPosition.Manual; KeyPreview = true;
        BackColor = Color.FromArgb(30, 31, 29); ForeColor = Color.FromArgb(232, 228, 215); Padding = new Padding(1);
        Paint += (_, e) => { using var pen = new Pen(Color.FromArgb(90, 87, 75)); e.Graphics.DrawRectangle(pen, 0, 0, Width - 1, Height - 1); };
        FormClosing += (_, e) => { e.Cancel = true; if (!IsDisposed) BeginInvoke(close); };
        row = new FlowLayoutPanel { Margin = Padding.Empty, WrapContents = false, Dock = DockStyle.Fill };
        Controls.Add(row);
        void AddControl(Control control, int width)
        {
            sizes.Add((control, width));
            row.Controls.Add(control);
        }
        var grip = new InkChoice("⋮⋮", () => false, null, null, () => DrawingFont) { Cursor = Cursors.SizeAll };
        grip.MouseDown += (_, e) => { if (e.Button == MouseButtons.Left) { Native.ReleaseCapture(); Native.SendMessage(Handle, 0xA1, new IntPtr(2), IntPtr.Zero); } }; AddControl(grip, 24); tips.SetToolTip(grip, Ui.T("ドラッグで移動"));
        ComboBox Choose(string[] names, int selected, int width, Action<int> change)
        {
            var box = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = width, FlatStyle = FlatStyle.Flat, BackColor = BackColor, ForeColor = ForeColor, DrawMode = DrawMode.OwnerDrawFixed, ItemHeight = 19, Margin = new Padding(1, 1, 2, 0) };
            box.Items.AddRange(names); box.SelectedIndex = selected;
            box.DrawItem += (_, e) => { if (e.Index < 0) return; using var brush = new SolidBrush((e.State & DrawItemState.Selected) != 0 ? Color.FromArgb(58, 57, 49) : BackColor); e.Graphics.FillRectangle(brush, e.Bounds); DrawLabel(e.Graphics, names[e.Index], DrawingFont, new RectangleF(e.Bounds.X + 3 * scale, e.Bounds.Y, e.Bounds.Width - 3 * scale, e.Bounds.Height), ForeColor, StringAlignment.Near); };
            box.SelectedIndexChanged += (_, _) => { model.End(); change(box.SelectedIndex); }; AddControl(box, width); return box;
        }
        model.End(); model.Space = "screen";
        Choose(new[] { Ui.T("ペン"), Ui.T("矢印") }, model.Tool == "arrow" ? 1 : 0, 86, i => model.Tool = i == 1 ? "arrow" : "pen");
        var choices = new List<Button>();
        foreach (string color in new[] { "white", "cyan", "red", "yellow" })
        {
            var button = new InkChoice("", () => model.ColorName == color, color, null, () => DrawingFont) { AccessibleName = color };
            button.Click += (_, _) => { model.End(); model.ColorName = color; foreach (var b in choices) b.Invalidate(); }; choices.Add(button); AddControl(button, 30); tips.SetToolTip(button, color switch { "cyan" => Ui.T("水色"), "red" => Ui.T("赤"), "yellow" => Ui.T("黄"), _ => Ui.T("白") });
        }
        foreach (int width in InkModel.Widths)
        {
            var button = new InkChoice(width == 3 ? Ui.T("細") : Ui.T("太"), () => model.Width == width, null, width, () => DrawingFont) { AccessibleName = width == 3 ? Ui.T("細い線 3px") : Ui.T("太い線 8px") };
            button.Click += (_, _) => { model.End(); model.Width = width; foreach (var b in choices) b.Invalidate(); }; choices.Add(button); AddControl(button, Ui.Japanese ? 62 : 86); tips.SetToolTip(button, Ui.T("これから描く線の太さを変更"));
        }
        void Add(string text, string tip, Action action, int width) { var button = new InkChoice(text, () => false, null, null, () => DrawingFont); button.Click += (_, _) => action(); AddControl(button, width); tips.SetToolTip(button, tip); }
        Add(Ui.T("戻す"), Ui.T("1本戻す（右クリック / Ctrl+Z）"), model.Undo, 54); Add(Ui.T("消去"), Ui.T("描いた線をすべて消す"), model.Clear, 54);
        mode = new InkChoice(Ui.T("描く"), () => drawing, null, null, () => DrawingFont); mode.Click += (_, _) => toggle(); AddControl(mode, Ui.Japanese ? 100 : 110); tips.SetToolTip(mode, Ui.T("Escまたは「ゲーム操作へ」で、線を残してゲーム操作へ戻ります。「描く」で再開します。"));
        KeyDown += (_, e) => { if (e.KeyCode == Keys.Escape) { e.Handled = true; pause(); } };
    }
    internal static float LayoutScale(Size game, int dpi) =>
        Math.Max(1f, Math.Min(Math.Max(dpi / 96f, game.Height / 1080f), Math.Min(game.Width / 620f, game.Height / 400f)));

    internal bool FitToGame(Size game, int dpi)
    {
        float next = LayoutScale(game, dpi);
        if (Math.Abs(next - scale) < .005f) return false;
        scale = next;
        int Px(int units) => (int)Math.Round(units * scale);
        var previousFont = toolbarFont;
        toolbarFont = new Font(Ui.Japanese ? "Yu Gothic UI" : "Segoe UI", Px(14), GraphicsUnit.Pixel);
        row.SuspendLayout();
        try
        {
            Padding = new Padding(Px(1));
            row.Padding = new Padding(Px(5));
            foreach (var (control, width) in sizes)
            {
                control.Margin = new Padding(Px(1));
                control.Width = Px(width);
                if (control is ComboBox box) box.ItemHeight = Px(30);
                else control.Height = Px(34);
            }
            ClientSize = new Size(
                sizes.Sum(item => item.Control.Width + item.Control.Margin.Horizontal) + row.Padding.Horizontal + Padding.Horizontal,
                sizes.Max(item => item.Control.Height + item.Control.Margin.Vertical) + row.Padding.Vertical + Padding.Vertical);
        }
        finally { row.ResumeLayout(true); }
        previousFont?.Dispose();
        Invalidate(true);
        return true;
    }

    public void SetDrawing(bool value) { drawing = value; mode.Text = value ? Ui.T("ゲーム操作へ") : Ui.T("描く"); mode.Invalidate(); }
    protected override bool ShowWithoutActivation => true;
    protected override void Dispose(bool disposing) { if (disposing) tips.Dispose(); base.Dispose(disposing); if (disposing) toolbarFont?.Dispose(); }
    static void DrawLabel(Graphics graphics, string text, Font font, RectangleF bounds, Color color, StringAlignment alignment)
    {
        using var brush = new SolidBrush(color);
        using var format = new StringFormat { Alignment = alignment, LineAlignment = StringAlignment.Center,
            FormatFlags = StringFormatFlags.NoWrap };
        graphics.DrawString(text, font, brush, bounds, format);
    }

    sealed class InkChoice : Button
    {
        readonly Func<bool> selected; readonly string? color; readonly int? line; readonly Func<Font> drawingFont;
        public InkChoice(string text, Func<bool> selected, string? color, int? line, Func<Font> drawingFont)
        { Text = text; this.selected = selected; this.color = color; this.line = line; this.drawingFont = drawingFont; Height = 24; Margin = new Padding(1, 1, 1, 1); FlatStyle = FlatStyle.Flat; Cursor = Cursors.Hand; SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.AllPaintingInWmPaint, true); }
        protected override void OnPaint(PaintEventArgs e)
        {
            bool active = selected(); e.Graphics.Clear(active ? Color.FromArgb(64, 62, 51) : Color.FromArgb(35, 36, 33));
            if (active || Focused) { using var border = new Pen(active ? Color.FromArgb(202, 189, 146) : Color.FromArgb(101, 99, 86)); e.Graphics.DrawRectangle(border, 0, 0, Width - 1, Height - 1); }
            int DpiPixels(int pixels) => (int)Math.Round(pixels * Height / 34f);
            if (color != null)
            {
                int inset = DpiPixels(5);
                using var ink = new SolidBrush(InkModel.InkColor(color));
                e.Graphics.FillRectangle(ink, inset, inset, Width - 2 * inset, Height - 2 * inset);
            }
            else if (line != null)
            {
                int labelX = DpiPixels(33);
                using var pen = new Pen(Color.FromArgb(232, 228, 215), DpiPixels(line.Value));
                e.Graphics.DrawLine(pen, DpiPixels(7), Height / 2, DpiPixels(30), Height / 2);
                DrawLabel(e.Graphics, Text, drawingFont(), new Rectangle(labelX, 0, Width - labelX, Height), ForeColor, StringAlignment.Center);
            }
            else DrawLabel(e.Graphics, Text, drawingFont(), ClientRectangle, ForeColor, StringAlignment.Center);
        }
    }
}
internal static class Native
{
    [StructLayout(LayoutKind.Sequential)] internal struct Point { public int X, Y; public Point(int x, int y) { X = x; Y = y; } }
    [StructLayout(LayoutKind.Sequential)] internal struct Rect { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] struct Size { public int Width, Height; public Size(int w, int h) { Width = w; Height = h; } }
    [StructLayout(LayoutKind.Sequential, Pack = 1)] struct Blend { public byte Op, Flags, Alpha, Format; }
    [DllImport("user32.dll")] internal static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] internal static extern bool ReleaseCapture();
    [DllImport("user32.dll")] internal static extern IntPtr SendMessage(IntPtr handle, uint message, IntPtr wparam, IntPtr lparam);
    [DllImport("user32.dll")] internal static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] internal static extern bool IsWindow(IntPtr handle);
    [DllImport("user32.dll")] internal static extern bool IsIconic(IntPtr handle);
    [DllImport("user32.dll")] internal static extern uint GetWindowThreadProcessId(IntPtr handle, out uint pid);
    [DllImport("user32.dll")] static extern uint GetDpiForWindow(IntPtr handle);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr handle, out Rect rect);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr handle, ref Point point);
    [DllImport("user32.dll", SetLastError = true)] internal static extern bool RegisterHotKey(IntPtr handle, int id, uint modifiers, uint key);
    [DllImport("user32.dll")] internal static extern bool UnregisterHotKey(IntPtr handle, int id);
    [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr handle);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr handle, IntPtr dc);
    [DllImport("gdi32.dll")] static extern IntPtr CreateCompatibleDC(IntPtr dc);
    [DllImport("gdi32.dll")] static extern bool DeleteDC(IntPtr dc);
    [DllImport("gdi32.dll")] static extern IntPtr SelectObject(IntPtr dc, IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);
    [DllImport("user32.dll", SetLastError = true)] static extern bool UpdateLayeredWindow(IntPtr handle, IntPtr dstDc, ref Point dst, ref Size size, IntPtr srcDc, ref Point src, uint key, ref Blend blend, uint flags);
    internal static bool ClientBounds(IntPtr handle, out Rectangle bounds)
    {
        bounds = Rectangle.Empty;
        if (!GetClientRect(handle, out var r)) return false;
        var origin = new Point(r.Left, r.Top);
        var edge = new Point(r.Right, r.Bottom);
        if (!ClientToScreen(handle, ref origin) || !ClientToScreen(handle, ref edge) ||
            edge.X - origin.X < 640 || edge.Y - origin.Y < 360) return false;
        bounds = Rectangle.FromLTRB(origin.X, origin.Y, edge.X, edge.Y);
        return true;
    }
    internal static int WindowDpi(IntPtr handle) => Math.Max(96, (int)GetDpiForWindow(handle));
    internal static void Present(IntPtr handle, Bitmap bitmap, System.Drawing.Point location)
    {
        var screen = GetDC(IntPtr.Zero); var dc = CreateCompatibleDC(screen); IntPtr image = IntPtr.Zero, old = IntPtr.Zero;
        try
        {
            image = bitmap.GetHbitmap(Color.FromArgb(0)); old = SelectObject(dc, image);
            var point = new Point(location.X, location.Y); var size = new Size(bitmap.Width, bitmap.Height); var source = new Point(0, 0); var blend = new Blend { Alpha = 255, Format = 1 };
            if (!UpdateLayeredWindow(handle, screen, ref point, ref size, dc, ref source, 0, ref blend, 2)) throw new System.ComponentModel.Win32Exception();
        }
        finally { if (old != IntPtr.Zero) SelectObject(dc, old); if (image != IntPtr.Zero) DeleteObject(image); DeleteDC(dc); ReleaseDC(IntPtr.Zero, screen); }
    }
}
