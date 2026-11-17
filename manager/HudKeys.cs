using System.Text.Json;
using System.Text.Json.Serialization;

internal sealed record HudKey(int Code, int Modifiers)
{
    public static HudKey DrawingDefault => new(0x77, 0);
    public static HudKey DamageDefault => new(0x78, 6);
    public static HudKey GraphDefault => new(0x79, 6);

    [JsonIgnore]
    public bool IsValid =>
        Modifiers is >= 0 and <= 7 &&
        (Code is >= 0x30 and <= 0x39 or >= 0x41 and <= 0x5A or >= 0x60 and <= 0x69
            or >= 0x70 and <= 0x87 or 0x20 or >= 0x21 and <= 0x28 or 0x2D or 0x2E
            or 0xBA or 0xBB or 0xBC or 0xBD or 0xBE or 0xBF or 0xC0 or 0xDB or 0xDC or 0xDD or 0xDE or 0xE2)
        && Code != 0x7B && !(Code == 0x73 && (Modifiers & 1) != 0);

    public string Display =>
        ((Modifiers & 2) != 0 ? "Ctrl+" : "") +
        ((Modifiers & 4) != 0 ? "Shift+" : "") +
        ((Modifiers & 1) != 0 ? "Alt+" : "") +
        (Code switch
        {
            >= 0x30 and <= 0x39 or >= 0x41 and <= 0x5A => ((char)Code).ToString(),
            >= 0x60 and <= 0x69 => $"Num{Code - 0x60}",
            >= 0x70 and <= 0x87 => $"F{Code - 0x6F}",
            _ => ((Keys)Code).ToString()
        });
}

internal sealed record HudKeys(HudKey Drawing, HudKey Damage, HudKey Graph, bool DrawingEnabled)
{
    static string PathFor(string home) => Path.Combine(home, "hotkeys.json");
    static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    public static HudKeys Defaults => new(HudKey.DrawingDefault, HudKey.DamageDefault, HudKey.GraphDefault, false);
    [JsonIgnore]
    public bool IsValid => Drawing?.IsValid == true && Damage?.IsValid == true && Graph?.IsValid == true
        && Drawing != Damage && Drawing != Graph && Damage != Graph;

    public static HudKeys Load(string home)
    {
        try
        {
            var path = PathFor(home);
            if (!File.Exists(path)) return Defaults;
            var saved = JsonSerializer.Deserialize<HudKeys>(File.ReadAllText(path), Json);
            return saved?.IsValid == true ? saved : Defaults;
        }
        catch (JsonException) { return Defaults; }
    }

    public void Save(string home)
    {
        if (!IsValid) throw new InvalidOperationException();
        Directory.CreateDirectory(home);
        string path = PathFor(home), temp = path + "." + Guid.NewGuid().ToString("N");
        try
        {
            File.WriteAllText(temp, JsonSerializer.Serialize(this, Json));
            File.Move(temp, path, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }
}

internal sealed class KeyCapture : TextBox
{
    public HudKey Binding { get; private set; }
    readonly Action<bool> feedback;
    public KeyCapture(HudKey binding, Action<bool> feedback)
    {
        Binding = binding;
        this.feedback = feedback;
        ReadOnly = true;
        ShortcutsEnabled = false;
        Width = 175;
        ShowBinding(binding);
    }

    public void ShowBinding(HudKey binding) { Binding = binding; Text = binding.Display; }
    protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
    {
        var code = keyData & Keys.KeyCode;
        if (code == Keys.Tab || code is Keys.ShiftKey or Keys.ControlKey or Keys.Menu)
            return base.ProcessCmdKey(ref msg, keyData);
        var binding = new HudKey((int)code, (keyData.HasFlag(Keys.Control) ? 2 : 0) +
            (keyData.HasFlag(Keys.Shift) ? 4 : 0) + (keyData.HasFlag(Keys.Alt) ? 1 : 0));
        if (binding.IsValid) ShowBinding(binding);
        feedback(binding.IsValid);
        return true;
    }
}
