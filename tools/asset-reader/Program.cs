using System.Text.Json;
using ValveResourceFormat;
using ValveResourceFormat.ResourceTypes;
using SkiaSharp;
using System.Xml.Linq;
using System.Globalization;
if(args.Length!=1) throw new ArgumentException("job manifest required");
var jobs=JsonSerializer.Deserialize<List<Job>>(File.ReadAllText(args[0])) ?? throw new InvalidDataException("jobs");
if(jobs.Count>1000)throw new InvalidDataException("too many jobs");
var results=new List<object>();
foreach(var job in jobs){
 try{
 if(File.Exists(job.output))throw new IOException("Refuse overwrite");
 using var resource=new Resource();resource.Read(job.input);
 if(job.mode=="png"){
  var texture=resource.DataBlock as Texture ?? throw new InvalidDataException("not texture");
  if(texture.Width>2048 || texture.Height>2048 || texture.Depth>1)throw new InvalidDataException("icon dimensions");
  using var bitmap=texture.GenerateBitmap();using var image=SKImage.FromBitmap(bitmap);using var encoded=image.Encode(SKEncodedImageFormat.Png,100);File.WriteAllBytes(job.output,encoded.ToArray());
 }else if(job.mode=="svg-png"){
  var svg=XElement.Parse(resource.DataBlock?.ToString() ?? throw new InvalidDataException("no SVG"));
  if(svg.Name.LocalName!="svg" || svg.Descendants().Any(x=>x.Name.LocalName!="path"))throw new InvalidDataException("unsupported SVG structure");
  var box=((string?)svg.Attribute("viewBox") ?? throw new InvalidDataException("viewBox")).Split(' ',StringSplitOptions.RemoveEmptyEntries).Select(v=>float.Parse(v,CultureInfo.InvariantCulture)).ToArray();
  if(box.Length!=4 || box[2]<=0 || box[3]<=0)throw new InvalidDataException("viewBox");
  using var bitmap=new SKBitmap(new SKImageInfo(256,256,SKColorType.Rgba8888,SKAlphaType.Premul));using var canvas=new SKCanvas(bitmap);canvas.Clear(SKColors.Transparent);
  var scale=Math.Min(256/box[2],256/box[3]);canvas.Translate((256-box[2]*scale)/2,(256-box[3]*scale)/2);canvas.Scale(scale);canvas.Translate(-box[0],-box[1]);
  foreach(var element in svg.Elements()){
   if(element.Attributes().Any(x=>x.Name.LocalName is not ("d" or "fill" or "fill-rule" or "clip-rule" or "fill-opacity")))throw new InvalidDataException("unsupported SVG attribute");
   using var path=SKPath.ParseSvgPathData((string?)element.Attribute("d") ?? throw new InvalidDataException("path"));
   path.FillType=(string?)element.Attribute("fill-rule")=="evenodd"?SKPathFillType.EvenOdd:SKPathFillType.Winding;
   if(!SKColor.TryParse((string?)element.Attribute("fill"),out var color))throw new InvalidDataException("fill");
   var alpha=float.Parse((string?)element.Attribute("fill-opacity") ?? "1",CultureInfo.InvariantCulture);if(alpha<0||alpha>1)throw new InvalidDataException("opacity");
   using var paint=new SKPaint{IsAntialias=true,Color=color.WithAlpha((byte)Math.Round(alpha*255)),Style=SKPaintStyle.Fill};canvas.DrawPath(path,paint);
  }
  using var image=SKImage.FromBitmap(bitmap);using var encoded=image.Encode(SKEncodedImageFormat.Png,100);File.WriteAllBytes(job.output,encoded.ToArray());
 }else if(job.mode=="text"){
  File.WriteAllText(job.output,resource.DataBlock?.ToString() ?? throw new InvalidDataException("no block"),new System.Text.UTF8Encoding(false));
 }else throw new InvalidDataException("mode");
 results.Add(new {output=job.output,ok=true});
 }catch(Exception e){results.Add(new {output=job.output,ok=false,error=e.GetType().Name});}
}
Console.WriteLine(JsonSerializer.Serialize(new {completed=jobs.Count,results}));
record Job(string input,string output,string mode);
