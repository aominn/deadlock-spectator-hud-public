using System.Drawing;
using System.Drawing.Drawing2D;

internal sealed record InkStroke(string Space, string Tool, string Color, int Width, List<PointF> Points);
internal sealed class InkModel
{
    public const int MaxStrokes = 128, MaxPoints = 4096;
    public readonly List<InkStroke> Strokes = new();
    public string Space = "screen", Tool = "pen", ColorName = "white";
    public int Width = 3;
    public static readonly int[] Widths = { 3, 8 };
    public long Revision { get; private set; }
    InkStroke? current;
    public bool InStroke => current != null;
    public void Begin(PointF point, RectangleF? map)
    {
        End(); var rect = Area(Space, map);
        if (rect == null || !rect.Value.Contains(point)) return;
        while (Strokes.Count >= MaxStrokes || Strokes.Sum(s => s.Points.Count) >= MaxPoints) Strokes.RemoveAt(0);
        current = new InkStroke(Space, Tool, ColorName, Width, new List<PointF> { Local(point, rect.Value) });
        Strokes.Add(current); Revision++;
    }
    public void Move(PointF point, RectangleF? map)
    {
        if (current == null) return;
        var rect = Area(current.Space, map); if (rect == null) { End(); return; }
        var local = Local(point, rect.Value);
        if (current.Tool == "arrow") { if (current.Points.Count == 1) current.Points.Add(local); else current.Points[1] = local; Revision++; return; }
        var last = current.Points[^1];
        if (Math.Abs(local.X - last.X) + Math.Abs(local.Y - last.Y) < .0005f) return;
        while (Strokes.Sum(s => s.Points.Count) >= MaxPoints && Strokes.Count > 1) Strokes.RemoveAt(0);
        if (Strokes.Sum(s => s.Points.Count) >= MaxPoints) return;
        current.Points.Add(local); Revision++;
    }
    public void End() => current = null;
    public void Undo() { End(); if (Strokes.Count > 0) { Strokes.RemoveAt(Strokes.Count - 1); Revision++; } }
    public void Clear() { End(); Strokes.Clear(); Revision++; }
    public static RectangleF? Area(string space, RectangleF? map) => space == "screen" ? new RectangleF(0, 0, 1, 1) : map;
    static PointF Local(PointF p, RectangleF r) => new(Math.Clamp((p.X - r.X) / r.Width, 0, 1), Math.Clamp((p.Y - r.Y) / r.Height, 0, 1));
    public static Color InkColor(string name) => name switch { "cyan" => Color.FromArgb(100, 221, 246), "red" => Color.FromArgb(255, 111, 102), "yellow" => Color.FromArgb(255, 213, 92), _ => Color.FromArgb(250, 249, 242) };
    public object[] Payload() => Strokes.Select(s => (object)new { space = s.Space, tool = s.Tool, color = s.Color, width = s.Width, points = s.Points.Select(p => new[] { p.X, p.Y }).ToArray() }).ToArray();
    public void Paint(Graphics graphics, Size size, RectangleF? map)
    {
        graphics.SmoothingMode = SmoothingMode.AntiAlias;
        foreach (var s in Strokes)
        {
            var area = Area(s.Space, map); if (area == null) continue;
            var r = area.Value; var points = s.Points.Select(p => new PointF((r.X + p.X * r.Width) * size.Width, (r.Y + p.Y * r.Height) * size.Height)).ToArray();
            float width = Math.Max(2, s.Width * size.Width / 1920f);
            using var shadow = new Pen(Color.FromArgb(190, 10, 13, 15), width + 2) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round };
            using var ink = new Pen(InkColor(s.Color), width) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round };
            foreach (var pen in new[] { shadow, ink })
            {
                if (points.Length > 1) graphics.DrawLines(pen, points);
                else if (points.Length == 1) { using var brush = new SolidBrush(pen.Color); graphics.FillEllipse(brush, points[0].X - pen.Width / 2, points[0].Y - pen.Width / 2, pen.Width, pen.Width); }
                if (s.Tool == "arrow" && points.Length == 2)
                {
                    var end = points[1]; double angle = Math.Atan2(end.Y - points[0].Y, end.X - points[0].X); float length = Math.Max(10, size.Width * 10 / 1920f);
                    if (MathF.Sqrt(MathF.Pow(end.X - points[0].X, 2) + MathF.Pow(end.Y - points[0].Y, 2)) > length)
                        graphics.DrawLines(pen, new[] { new PointF(end.X - length * (float)Math.Cos(angle - .5), end.Y - length * (float)Math.Sin(angle - .5)), end, new PointF(end.X - length * (float)Math.Cos(angle + .5), end.Y - length * (float)Math.Sin(angle + .5)) });
                }
            }
        }
    }
}
