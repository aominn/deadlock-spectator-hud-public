using System.Drawing;using System.Text.Json;using System.Windows.Forms;using System.Reflection;
internal static class Harness {
 [STAThread] static void Main(string[] args) {
  ApplicationConfiguration.Initialize();
  if(args.Contains("--transport")){Transport(args[^1]);return;}
  if(args.Contains("--selftest")){SelfTest();return;}
  bool live=args.Contains("--live-controller"); string artifacts=live?args[^1]:(args.FirstOrDefault(x=>!x.StartsWith("--"))??Path.Combine(AppContext.BaseDirectory,"artifacts"));Directory.CreateDirectory(artifacts);
  using var form=new Form{Text="観戦描画テスト（合成・ゲームではありません）",ClientSize=new Size(1280,720),StartPosition=FormStartPosition.CenterScreen,BackColor=Color.FromArgb(29,33,33),KeyPreview=true};
  var rect=new RectangleF(.74f,.58f,.23f,.37f);DrawingController? controller=null;int clicks=0;
  var clickTarget=new Button{Text="ゲーム側UI操作確認",Location=new Point(30,110),Size=new Size(210,38)};clickTarget.Click+=(_,_)=>{clicks++;clickTarget.Text="操作確認 "+clicks;};form.Controls.Add(clickTarget);
  if(live)form.Text="実ゲーム描画コントローラ検証";
  form.Paint+=(_,e)=>{using var font=new Font("Yu Gothic UI",18);e.Graphics.DrawString("合成入力テスト：Ctrl+Shift+Dで表示切替 / 描く・観戦へで操作切替",font,Brushes.White,30,40);using var map=new SolidBrush(Color.FromArgb(47,58,54));e.Graphics.FillRectangle(map,rect.X*1280,rect.Y*720,rect.Width*1280,rect.Height*720);e.Graphics.DrawString("ミニマップ",font,Brushes.White,960,460);};
  form.Shown+=(_,_)=>{controller=live?new DrawingController(message=>File.AppendAllText(Path.Combine(artifacts,"events.txt"),message+"\n")):new DrawingController(message=>File.AppendAllText(Path.Combine(artifacts,"events.txt"),message+"\n"),h=>h==form.Handle,()=>Task.FromResult<DrawingContext?>(new DrawingContext("harness-session",rect)));if(live)typeof(DrawingController).GetField("sequence",BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(controller,DateTime.UtcNow.Ticks);controller.Configure(true,args.Contains("--f8")?"F8":"Ctrl+Shift+D");};
  using var timer=new System.Windows.Forms.Timer{Interval=300};timer.Tick+=(_,_)=>{if(controller==null)return;var model=(InkModel)typeof(DrawingController).GetField("model",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(controller)!;var canvas=typeof(DrawingController).GetField("canvas",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(controller);File.WriteAllText(Path.Combine(artifacts,"state.json"),JsonSerializer.Serialize(new{synthetic=!live,drawing=canvas!=null,toolbar=typeof(DrawingController).GetField("toolbar",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(controller)!=null,clicks,strokes=model.Strokes.Count,points=model.Strokes.Sum(s=>s.Points.Count),width=model.Width,color=model.ColorName,space=model.Space,revision=model.Revision}));};timer.Start();form.FormClosed+=(_,_)=>controller?.Dispose();Application.Run(form);
 }
 static void Transport(string route){using var http=new System.Net.Http.HttpClient(new System.Net.Http.HttpClientHandler{UseProxy=false});var context=System.Text.Json.Nodes.JsonNode.Parse(http.GetStringAsync(route).GetAwaiter().GetResult())!;using var body=DrawingController.EncodeSnapshot(new{epoch=context["epoch"]!.GetValue<string>(),sequence=0,drawing=true,strokes=new[]{new{space="screen",tool="pen",color="cyan",width=3,points=new[]{new[]{.2,.2},new[]{.6,.5}}}}});var length=body.Headers.ContentLength;using var result=http.PostAsync(route,body).GetAwaiter().GetResult();if((int)result.StatusCode!=204)throw new Exception("Production sender refused: "+result.StatusCode);Console.WriteLine(JsonSerializer.Serialize(new{passed=true,content_length=length,response=(int)result.StatusCode,scope="production C# sender to Python loopback reader"}));}
 static void SelfTest(){int checks=0;void Check(bool value){if(!value)throw new Exception("Drawing model test "+checks);checks++;}
  using(var body=DrawingController.EncodeSnapshot(new{test=true})){Check(body.Headers.ContentLength>0);Check(body.Headers.ContentType!.MediaType=="application/json");}
  var now=DateTime.UtcNow;Check(DrawingController.KeepContextOnFailure(now,now.AddMilliseconds(2999)));Check(!DrawingController.KeepContextOnFailure(now,now.AddMilliseconds(3001)));Check(!DrawingController.KeepContextOnFailure(now,now.AddMilliseconds(-1)));
  Check(DrawingController.SameMap(new RectangleF(.7f,.6f,.2f,.3f),new RectangleF(.7001f,.6f,.2f,.3f)));Check(!DrawingController.SameMap(new RectangleF(.7f,.6f,.2f,.3f),null));
  var model=new InkModel();RectangleF map=new(.7f,.6f,.25f,.35f);model.Begin(new(.1f,.1f),map);model.Move(new(.5f,.5f),map);model.End();Check(model.Strokes.Count==1&&model.Strokes[0].Points.Count==2);
  model.Space="map";model.Begin(new(.1f,.1f),map);Check(model.Strokes.Count==1);model.Begin(new(.8f,.7f),map);model.Move(new(1.2f,1.4f),map);model.End();Check(model.Strokes[1].Points[^1]==new PointF(1,1));model.Undo();Check(model.Strokes.Count==1);
  model.Tool="arrow";model.Space="screen";model.Begin(new(.2f,.2f),map);for(int i=0;i<100;i++)model.Move(new(i/100f,.7f),map);model.End();Check(model.Strokes[^1].Points.Count==2);
  using var im=new Bitmap(1920,1080);using(var g=Graphics.FromImage(im))model.Paint(g,im.Size,map);Check(im.GetPixel(384,216).A>0);
  model.Clear();for(int i=0;i<300;i++){model.Begin(new(.1f,.1f),map);model.End();}Check(model.Strokes.Count==InkModel.MaxStrokes);
  model.Tool="pen";model.Clear();model.Begin(new(.1f,.1f),map);for(int i=0;i<10000;i++)model.Move(new(i%2==0?.2f:.8f,.5f),map);model.End();Check(model.Strokes.Sum(s=>s.Points.Count)==InkModel.MaxPoints);model.Begin(new(.3f,.4f),map);Check(model.Strokes.Sum(s=>s.Points.Count)<=InkModel.MaxPoints);
  model.Clear();Check(!model.InStroke&&model.Strokes.Count==0);
  Check(InkModel.Widths.SequenceEqual(new[]{3,8}));
  var heights=new List<int>();foreach(int width in InkModel.Widths){model.Clear();model.Width=width;model.Begin(new(.2f,.5f),map);model.Move(new(.7f,.5f),map);model.End();using var image=new Bitmap(1920,1080);using(var g=Graphics.FromImage(image))model.Paint(g,image.Size,map);heights.Add(Enumerable.Range(0,1080).Count(y=>image.GetPixel(800,y).A>0));}Check(heights[1]-heights[0]>=4);
  using(var controller=new DrawingController(_=>{},_=>true,()=>Task.FromResult<DrawingContext?>(new("unit",map)))){
   var ink=(InkModel)typeof(DrawingController).GetField("model",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(controller)!;ink.Begin(new(.2f,.2f),map);ink.Move(new(.5f,.5f),map);
   typeof(DrawingController).GetField("inkEpoch",BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(controller,"unit");
   typeof(DrawingController).GetMethod("PauseDrawing",BindingFlags.Instance|BindingFlags.NonPublic,null,new[]{typeof(bool)},null)!.Invoke(controller,new object[]{false});Check(ink.Strokes.Count==1&&!ink.InStroke);
   typeof(DrawingController).GetMethod("End",BindingFlags.Instance|BindingFlags.NonPublic,null,new[]{typeof(bool),typeof(string)},null)!.Invoke(controller,new object?[]{false,null});Check(ink.Strokes.Count==0);
  }
  using(var controller=new DrawingController(_=>{},_=>true,()=>Task.FromResult<DrawingContext?>(new("unit",map)))){
   using var surface=new InkCanvas(new Rectangle(0,0,1280,720),model,()=>map,()=>{});var bar=new InkToolbar(model,()=>{},()=>{},()=>{});bar.Owner=surface;
   typeof(DrawingController).GetField("canvas",BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(controller,surface);typeof(DrawingController).GetField("toolbar",BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(controller,bar);
   typeof(DrawingController).GetMethod("PauseDrawing",BindingFlags.Instance|BindingFlags.NonPublic,null,new[]{typeof(bool)},null)!.Invoke(controller,new object[]{false});Check(!bar.IsDisposed&&bar.Owner==null);Check(surface.IsDisposed);
  }
Console.WriteLine(JsonSerializer.Serialize(new{passed=true,checks,scope="production C# ink model,not actual game",limits=new{strokes=InkModel.MaxStrokes,points=InkModel.MaxPoints}}));
 }
}