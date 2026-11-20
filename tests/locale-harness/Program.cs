using System.Drawing;using System.Globalization;using System.Reflection;using System.Text.Json;using System.Windows.Forms;
internal static class LocaleHarness{
 [STAThread]static void Main(string[] args){
  var request=Path.Combine(AppContext.BaseDirectory,"preview.json");if(args.Length==0&&File.Exists(request)){var q=JsonSerializer.Deserialize<Dictionary<string,string>>(File.ReadAllText(request))!;args=new[]{"--preview",q["culture"],q["bundle"]};}
  if(args.Length>0&&args[0]=="--snapshot"){Snapshot(args[1],args[2],args[3]);return;}
  if(args.Length>0&&args[0]=="--preview"){
   CultureInfo.CurrentUICulture=CultureInfo.GetCultureInfo(args[1]);ApplicationConfiguration.Initialize();using var signal=new EventWaitHandle(false,EventResetMode.AutoReset);Application.Run(new ManagerForm(args[2],signal));return;
  }
  int checks=CheckProfileSelection();var before=CultureInfo.CurrentUICulture;var format=CultureInfo.CurrentCulture;
  try{var rows=(Dictionary<string,string>)typeof(Ui).GetField("English",BindingFlags.NonPublic|BindingFlags.Static)!.GetValue(null)!;
   foreach (var resolution in new[] { new Size(1280, 720), new Size(1920, 1080), new Size(2560, 1440), new Size(3840, 2160) })
   foreach (int dpi in new[] { 96, 120, 144, 192 })
   {
    var work = new Rectangle(-resolution.Width, 0, resolution.Width, resolution.Height - 48);
    var desired = new Rectangle(20, -20, 760 * dpi / 96, 595 * dpi / 96);
    var fitted = ManagerForm.FitWindowBounds(desired, work);
    if (!work.Contains(fitted) || fitted.Size != new Size(Math.Min(desired.Width, work.Width), Math.Min(desired.Height, work.Height)))
     throw new Exception("Manager exceeds the monitor work area.");
    checks++;
   }
   foreach(var locale in new[]{"ja-JP","en-US","de-DE","zh-CN","fr-FR"}){
    CultureInfo.CurrentUICulture=CultureInfo.GetCultureInfo(locale);CultureInfo.CurrentCulture=CultureInfo.GetCultureInfo(locale=="ja-JP"?"en-US":"ja-JP");
    if(Ui.Japanese!=(locale=="ja-JP"))throw new Exception("Display language rule");checks++;
    foreach(var row in rows){if(Ui.T(row.Key)!=(locale=="ja-JP"?row.Key:row.Value))throw new Exception("Translation mismatch");checks++;}
    using(var bar=new InkToolbar(new InkModel(),()=>{},()=>{},()=>{})){
     using var image=new Bitmap(1,1);
     using var graphics=Graphics.FromImage(image);
     foreach(var (size,dpi) in new[]{(new Size(1920,1080),96),(new Size(3840,2160),288)}){
      bar.FitToGame(size,dpi);
      var scale=InkToolbar.LayoutScale(size,dpi);
      using var font=new Font(Ui.Japanese?"Yu Gothic UI":"Segoe UI",(int)Math.Round(14*scale),GraphicsUnit.Pixel);
      foreach(var button in bar.Controls[0].Controls.OfType<Button>().Where(x=>x.AccessibleName?.EndsWith("px")==true)){
       var labelWidth=button.Width-(int)Math.Round(33*button.Height/34f);
       if(graphics.MeasureString(button.Text,font).Width>labelWidth)throw new Exception("Width caption clipped: "+button.Text);checks++;
      }
     }
    }

   }
   Console.WriteLine(JsonSerializer.Serialize(new{passed=true,checks,scope="production manager and drawing display dictionary;Windows UI culture,independent of formatting culture"}));
  }finally{CultureInfo.CurrentUICulture=before;CultureInfo.CurrentCulture=format;}
 }
 static int CheckProfileSelection()
 {
  var temp = Directory.CreateTempSubdirectory("SpectatorHud-profile-");
  try
  {
   string current = Path.Combine(temp.FullName, "DeadlockSpectatorHUD");
   string legacy = Path.Combine(temp.FullName, "Aominn", "DeadlockSpectatorHUD");
   void Expect(string path, string prefix)
   {
    if(Program.SelectProfile(temp.FullName) != (path, prefix))
     throw new Exception("Unexpected settings folder or window identity.");
   }

   Expect(current, "DeadlockSpectatorHUD");
   Directory.CreateDirectory(legacy);
   Expect(current, "DeadlockSpectatorHUD");

   File.WriteAllText(Path.Combine(legacy, "hotkeys.json"), "old keys");
   Expect(legacy, "AominnDeadlockHud");

   Directory.CreateDirectory(current);
   File.WriteAllText(Path.Combine(current, "config.json"), "{}");
   Expect(current, "DeadlockSpectatorHUD");

   string record = Path.Combine(legacy, "mount.json");
   File.WriteAllText(record, "old recovery record");
   Expect(legacy, "AominnDeadlockHud");
   if(File.ReadAllText(record) != "old recovery record" || File.ReadAllText(Path.Combine(legacy, "hotkeys.json")) != "old keys")
    throw new Exception("Profile selection rewrote a legacy file.");

   File.Delete(record);
   File.WriteAllText(Path.Combine(legacy, "focus-fps.json"), "old FPS record");
   Expect(legacy, "AominnDeadlockHud");
   return 6;
  }
  finally { temp.Delete(recursive: true); }
 }

 static void PrepareControls(Control control){_ = control.Handle;control.PerformLayout();foreach(Control child in control.Controls)PrepareControls(child);}
 static void Snapshot(string culture,string bundle,string directory){
  CultureInfo.CurrentUICulture=CultureInfo.GetCultureInfo(culture);ApplicationConfiguration.Initialize();Directory.CreateDirectory(directory);using var signal=new EventWaitHandle(false,EventResetMode.AutoReset);
  using(var form=new ManagerForm(bundle,signal)){
   form.CreateControl();typeof(ManagerForm).GetMethod("RefreshStatus",BindingFlags.NonPublic|BindingFlags.Instance)!.Invoke(form,null);form.PerformLayout();PrepareControls(form);
   using var image=new Bitmap(form.Width,form.Height);form.DrawToBitmap(image,new Rectangle(Point.Empty,image.Size));image.Save(Path.Combine(directory,"manager-"+culture+".png"));
   var rows=new List<object>();void Read(Control parent){foreach(Control child in parent.Controls){rows.Add(new{text=child.Text,type=child.GetType().Name,bounds=new[]{child.Left,child.Top,child.Width,child.Height},parent=new[]{parent.ClientSize.Width,parent.ClientSize.Height}});Read(child);}}Read(form);File.WriteAllText(Path.Combine(directory,"manager-"+culture+".json"),JsonSerializer.Serialize(new{synthetic=true,scope="production WinForms layout rendered without showing the window or firing startup operations",culture,controls=rows}));
  }
  using(var bar=new InkToolbar(new InkModel(),()=>{},()=>{},()=>{})){
   bar.SetDrawing(true);bar.CreateControl();bar.PerformLayout();bar.Size=bar.GetPreferredSize(Size.Empty);bar.PerformLayout();PrepareControls(bar);using var image=new Bitmap(Math.Max(1,bar.Width),Math.Max(1,bar.Height));bar.DrawToBitmap(image,new Rectangle(Point.Empty,image.Size));image.Save(Path.Combine(directory,"drawing-"+culture+".png"));
  }
  Console.WriteLine(JsonSerializer.Serialize(new{passed=true,synthetic=true,culture,directory}));
 }

}
