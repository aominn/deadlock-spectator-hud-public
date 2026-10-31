using System.Drawing;using System.Globalization;using System.Reflection;using System.Text.Json;using System.Windows.Forms;
internal static class LocaleHarness{
 [STAThread]static void Main(string[] args){
  var request=Path.Combine(AppContext.BaseDirectory,"preview.json");if(args.Length==0&&File.Exists(request)){var q=JsonSerializer.Deserialize<Dictionary<string,string>>(File.ReadAllText(request))!;args=new[]{"--preview",q["culture"],q["bundle"]};}
  if(args.Length>0&&args[0]=="--snapshot"){Snapshot(args[1],args[2],args[3]);return;}
  if(args.Length>0&&args[0]=="--preview"){
   CultureInfo.CurrentUICulture=CultureInfo.GetCultureInfo(args[1]);ApplicationConfiguration.Initialize();using var signal=new EventWaitHandle(false,EventResetMode.AutoReset);Application.Run(new ManagerForm(args[2],signal));return;
  }
  int checks=0;var before=CultureInfo.CurrentUICulture;var format=CultureInfo.CurrentCulture;
  try{var rows=(Dictionary<string,string>)typeof(Ui).GetField("English",BindingFlags.NonPublic|BindingFlags.Static)!.GetValue(null)!;
   foreach(var locale in new[]{"ja-JP","en-US","de-DE","zh-CN","fr-FR"}){
    CultureInfo.CurrentUICulture=CultureInfo.GetCultureInfo(locale);CultureInfo.CurrentCulture=CultureInfo.GetCultureInfo(locale=="ja-JP"?"en-US":"ja-JP");
    if(Ui.Japanese!=(locale=="ja-JP"))throw new Exception("Display language rule");checks++;
    foreach(var row in rows){if(Ui.T(row.Key)!=(locale=="ja-JP"?row.Key:row.Value))throw new Exception("Translation mismatch");checks++;}
    using(var bar=new InkToolbar(new InkModel(),()=>{},()=>{},()=>{})){
     foreach(var button in bar.Controls[0].Controls.OfType<Button>().Where(x=>x.AccessibleName?.EndsWith("px")==true)){
      if(TextRenderer.MeasureText(button.Text,button.Font).Width>button.Width-33)throw new Exception("Width caption clipped: "+button.Text);checks++;
     }
    }

   }
   Console.WriteLine(JsonSerializer.Serialize(new{passed=true,checks,scope="production manager and drawing display dictionary;Windows UI culture,independent of formatting culture"}));
  }finally{CultureInfo.CurrentUICulture=before;CultureInfo.CurrentCulture=format;}
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
