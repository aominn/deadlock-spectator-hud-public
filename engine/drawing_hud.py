"""Bounded session-local telestration. No game input, disk history or remote transport."""
import io,math,time,uuid
from PIL import Image,ImageDraw
COLORS={'white':(250,249,242,255),'cyan':(100,221,246,255),'red':(255,111,102,255),'yellow':(255,213,92,255)}
MAX_STROKES=128
MAX_POINTS=4096

def number(x):return type(x) in (int,float) and math.isfinite(x)
def rectangle(value):
 if not isinstance(value,list) or len(value)!=4 or not all(number(x) for x in value):raise ValueError('map rect')
 x,y,w,h=value
 if not 0<=x<=1 or not 0<=y<=1 or not 0<w<=1 or not 0<h<=1 or x+w>1.001 or y+h>1.001:raise ValueError('map bounds')
 return list(value)

class DrawingStore:
 def __init__(self):
  self.epoch=uuid.uuid4().hex;self.context=None;self.at=0;self.sequence=-1;self.strokes=[];self.drawing=False;self.revision=0;self.cache=None;self.session=None;self.clock=None
 def clear(self):
  self.epoch=uuid.uuid4().hex;self.context=None;self.at=0;self.sequence=-1;self.strokes=[];self.drawing=False;self.revision+=1;self.cache=None;self.session=None;self.clock=None
 def eligible(self,signal,stamp=None,wall=None):
  stamp=time.monotonic() if stamp is None else stamp;wall=time.time() if wall is None else wall
  return bool(self.context and stamp-self.at<=3 and signal and signal.get('kind') in ('replay','spectator') and signal.get('id')==self.session and -5<=wall-signal.get('at',0)<=4)
 def update_context(self,data,signal,stamp=None,wall=None):
  stamp=time.monotonic() if stamp is None else stamp;wall=time.time() if wall is None else wall
  if signal and (signal.get('kind') not in ('replay','spectator') or self.session is not None and signal.get('id')!=self.session):self.clear()
  if not signal or signal.get('kind') not in ('replay','spectator') or not -5<=wall-signal.get('at',0)<=4:raise ValueError('spectator context unavailable')
  w,h=data.get('width'),data.get('height');clock=data.get('clock')
  if not number(w) or not number(h) or not 640<=w<=7680 or not 360<=h<=4320 or type(clock) is not int or not 0<=clock<=86400:raise ValueError('drawing viewport')
  rect=rectangle(data['map']) if data.get('map') is not None else None
  if self.context and (self.session!=signal['id'] or self.clock is not None and (clock<self.clock or clock-self.clock>max(3,stamp-self.at+2))):self.clear()
  self.session=signal['id'];self.clock=clock;self.context={'width':w,'height':h,'map':rect};self.at=stamp
 def status(self,signal,stamp=None,wall=None):
  active=self.eligible(signal,stamp,wall)
  if signal and (signal.get('kind') not in ('replay','spectator') or self.session is not None and signal.get('id')!=self.session):self.clear()
  return {'active':active,'retained':bool(self.strokes),'epoch':self.epoch,'drawing':self.drawing,'revision':self.revision,'viewport':self.context if active else None,'max_strokes':MAX_STROKES,'max_points':MAX_POINTS}
 def replace(self,data,signal,stamp=None,wall=None):
  if data.get('epoch')!=self.epoch or data.get('drawing') is not False and not self.eligible(signal,stamp,wall):raise ValueError('drawing session changed')
  seq=data.get('sequence');active=data.get('drawing');rows=data.get('strokes')
  if type(seq) is not int or seq<=self.sequence or type(active) is not bool or not isinstance(rows,list) or len(rows)>MAX_STROKES:raise ValueError('drawing sequence or limit')
  clean=[];count=0
  for row in rows:
   if not isinstance(row,dict) or row.get('space') not in ('screen','map') or row.get('tool') not in ('pen','arrow') or row.get('color') not in COLORS or row.get('width') not in (3,5,8):raise ValueError('drawing style')
   if row['space']=='map' and self.context['map'] is None:raise ValueError('minimap unavailable')
   points=row.get('points');count+=len(points) if isinstance(points,list) else MAX_POINTS+1
   if not isinstance(points,list) or not 1<=len(points)<=MAX_POINTS or count>MAX_POINTS:raise ValueError('drawing points limit')
   if any(not isinstance(pt,list) or len(pt)!=2 or not all(number(v) and 0<=v<=1 for v in pt) for pt in points):raise ValueError('drawing point')
   if row['tool']=='arrow' and len(points)>2:raise ValueError('arrow endpoints')
   clean.append({k:row[k] for k in ('space','tool','color','width','points')})
  self.sequence=seq;self.drawing=active;self.strokes=clean if active else [];self.revision+=1;self.cache=None
 def png(self):
  context=self.context
  if not context or not self.strokes:return self.transparent()
  scale=min(1,1920/context['width'],1080/context['height']);w=max(1,round(context['width']*scale));h=max(1,round(context['height']*scale));key=(self.revision,w,h,tuple(context['map'] or []))
  if self.cache and self.cache[0]==key:return self.cache[1]
  im=Image.new('RGBA',(w,h));d=ImageDraw.Draw(im)
  for row in self.strokes:
   rect=[0,0,1,1] if row['space']=='screen' else context['map']
   if rect is None:continue
   x,y,rw,rh=rect;points=[((x+px*rw)*w,(y+py*rh)*h) for px,py in row['points']];width=max(2,round(row['width']*w/1920));color=COLORS[row['color']]
   for thick,c in [(width+2,(10,13,15,190)),(width,color)]:
    if len(points)>1:d.line(points,fill=c,width=thick,joint='curve')
    radius=thick/2
    for px,py in (points if row['tool']=='pen' else [points[0]]):d.ellipse((px-radius,py-radius,px+radius,py+radius),fill=c)
    if row['tool']=='arrow' and len(points)==2:
     (sx,sy),(ex,ey)=points;angle=math.atan2(ey-sy,ex-sx);length=max(10,10*w/1920)
     if math.hypot(ex-sx,ey-sy)>length:
      d.line([(ex-length*math.cos(angle-.5),ey-length*math.sin(angle-.5)),(ex,ey),(ex-length*math.cos(angle+.5),ey-length*math.sin(angle+.5))],fill=c,width=thick,joint='curve')
  stream=io.BytesIO();im.save(stream,format='PNG',compress_level=1);body=stream.getvalue();self.cache=(key,body);return body
 @staticmethod
 def transparent():
  stream=io.BytesIO();Image.new('RGBA',(1,1)).save(stream,format='PNG');return stream.getvalue()
