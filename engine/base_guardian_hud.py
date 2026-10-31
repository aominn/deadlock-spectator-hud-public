"""Individual base guardians; independent damage retention and compact lane columns."""
import bisect,math,re,os,functools
from pathlib import Path
LANE_SLOTS={1:0,4:1,3:2,6:2}
LANE_NAMES={1:"ヨーク",3:"グリニッジ",4:"ブロードウェイ",6:"パープル"}
class TowerGrid:
 """Small native layout receipt; unknown/stale layouts never guess a base column."""
 def __init__(self):self.clear()
 def clear(self):self.at=None;self.clock=None;self.counts={}
 def update(self,data,stamp):
  try:
   if not isinstance(data,dict) or data.get('schema')!=2 or data.get('columns')!=5:return False
   clock=data['clock'];bars=data['bars']
   if not isinstance(clock,str) or not re.fullmatch(r'\d{1,3}:[0-5]\d',clock) or not isinstance(bars,list) or len(bars)>18:return False
   counts={};seen=set()
   for bar in bars:
    if not isinstance(bar,dict):return False
    if bar.get('group')!='tower':continue
    team={'team_friendly_container':2,'team_enemy_container':3}.get(bar.get('team'));slot=bar.get('slot');kind=bar.get('kind')
    if team is None or type(slot) is not int or slot not in (0,1,2) or kind not in ('guardian','walker') or (team,slot,kind) in seen:return False
    seen.add((team,slot,kind));counts[team,slot]=counts.get((team,slot),0)+1
   minute,second=map(int,clock.split(':'));self.clock=minute*60+second;self.at=stamp;self.counts=counts;return True
  except (ValueError,TypeError,KeyError):return False
 def columns(self,clock,stamp):
  if self.at is None or clock is None or not 0<=stamp-self.at<2 or abs(clock-self.clock)>2:return None
  return dict(self.counts)

class GuardianView:
 def __init__(self):self.clear()
 def clear(self):self.prior={};self.hits={};self.maxima={};self.identities={}
 def sample(self,data,clock,wall,scope):
  if not isinstance(data,dict) or data.get('schema')!=3 or data.get('supported') is not True or data.get('expected_per_lane')!=2 or data.get('columns')!=['team','lane','entity','hp','max']:return []
  updates=data.get('updates',[])
  if not isinstance(updates,list) or len(updates)>21601:return []
  try:
   times=[u['second'] for u in updates]
   if any(type(t) is not int or t<0 for t in times) or any(a>=b for a,b in zip(times,times[1:])):return []
   i=bisect.bisect_right(times,clock)-1
   if i<0 or not 0<=clock-times[i]<=1:return []
   rows=updates[i]['rows']
   if len(rows)>16 or any(not isinstance(v,list) or len(v)!=5 for v in rows) or len({v[2] for v in rows})!=len(rows):return []
   if any(any(type(n) is not int for n in v) or v[0] not in (2,3) or v[1] not in LANE_NAMES or v[2]<0 or not 0<=v[3]<=v[4]<=10000000 or v[4]<=0 for v in rows):return []
   if any(sum(v[0:2]==u[0:2] for u in rows)>2 for v in rows):return []
  except (ValueError,TypeError,KeyError,IndexError):return []
  if self.identities.get('scope')!=scope:self.clear();self.identities['scope']=scope
  out=[];present=set()
  for team,lane,entity,hp,maximum in sorted(rows,key=lambda v:v[2]):
   key=(scope,team,lane,entity);present.add(key);old=self.prior.get(key)
   lane_key=(team,lane);ids=self.identities.setdefault(lane_key,[])
   if entity not in ids:ids.append(entity)
   if old is not None and (clock<old[2] or clock-old[2]>2 or self.maxima.get(key)!=maximum):self.hits.pop(key,None);old=None
   if old is not None and hp<old[0]:self.hits[key]=wall
   self.prior[key]=(hp,maximum,clock);self.maxima[key]=maximum
   if hp>0 and key in self.hits and 0<=wall-self.hits[key]<5:out.append({'team':team,'lane':lane,'entity':entity,'ordinal':ids.index(entity)+1,'hp':hp,'max':maximum,'fraction':hp/maximum})
  for row in out:row['ordinal']=self.identities[row['team'],row['lane']].index(row['entity'])+1
  for key in list(self.prior):
   if key not in present:self.prior.pop(key,None);self.hits.pop(key,None);self.maxima.pop(key,None)
  return out


@functools.lru_cache(maxsize=512)
def _building_caption(text,font_path,size,width,height,color,shadow,centered=True):
 # Match the native label boxes, without the heavy glyph outline of the old PNG.
 from PIL import Image,ImageDraw,ImageFont
 factor=3;im=Image.new('RGBA',(width*factor,height*factor));ink=ImageDraw.Draw(im)
 face=ImageFont.truetype(font_path,max(1,size*factor))
 box=ink.textbbox((0,0),text,font=face);x=((im.width-(box[2]-box[0]))/2 if centered else 0)-box[0];y=(im.height-(box[3]-box[1]))/2-box[1]
 if shadow:ink.text((x,y+factor),text,font=face,fill=(0,0,0,200))
 ink.text((x,y),text,font=face,fill=color)
 return im.resize((width,height),Image.Resampling.LANCZOS)

def _building_font(font_at,size,bold,language="ja"):
 # Fonts remain on the user's PC. The regular lane caption must not inherit bold.
 filename=('tetsubingothic.otf' if bold else 'notosansjp-regular.ttf') if language=='ja' else ('valveoracle-semibold.ttf' if bold else 'valveoracle-medium.ttf')
 path=Path(os.environ.get('SPEC_HUD_GAME',''))/'panorama/fonts'/filename
 if path.is_file() and 0<path.stat().st_size<16*1024*1024:return str(path)
 return str(font_at(size).path)


def draw_guardian_rows(image,rows,font_at,icon=None,origin_y=292,columns=None,language="ja"):
 # Same walker geometry; each visible individual consumes one compact column.
 from PIL import ImageDraw,Image
 ink=ImageDraw.Draw(image)
 offsets={}
 for row in sorted(rows,key=lambda row:(row['team'],LANE_SLOTS.get(row['lane'],3),row.get('ordinal',1),row.get('entity',0))):
  slot=LANE_SLOTS.get(row['lane'])
  if slot is None or len({other['lane'] for other in rows if other['team']==row['team'] and LANE_SLOTS.get(other['lane'])==slot})!=1:continue
  left=row['team']==2;scale=min(1,image.width/1920);key=(row['team'],slot);column=(columns or {}).get(key,0)+offsets.get(key,0)
  if column>=5:continue
  offsets[key]=offsets.get(key,0)+1
  w=round(220*scale);h=round(34*scale);x=16+round(228*scale*column) if left else image.width-16-w-round(228*scale*column);y=origin_y+round(40*scale*slot);content=x+round(40*scale)
  ink.rounded_rectangle((x,y,x+w-1,y+h-1),radius=max(1,round(2*scale)),fill=(16,19,13,238),outline=(75,73,63,255))
  fill_width=max(0,round((w-round(44*scale))*row['fraction']))
  if fill_width:image.alpha_composite(Image.new('RGBA',(fill_width,max(1,h-2)),(212,134,11,204) if left else (77,117,195,204)),(content,y+1))
  if icon is not None:image.alpha_composite(icon.convert('RGBA').resize((max(1,round(26*scale)),max(1,round(26*scale))),Image.Resampling.LANCZOS),(x+round(4*scale),y+round(4*scale)))
  caption_width=w-round(44*scale)
  lane=LANE_NAMES[row['lane']] if language=='ja' else {1:'York',3:'Greenwich',4:'Broadway',6:'Purple'}[row['lane']]
  title='ベースガーディアン' if language=='ja' else 'Base Guardian'
  for text,size,top,height,bold,color in [(lane,10,5,10,False,(201,197,185,255)),(title+' '+str(math.floor(row['fraction']*100+.5))+'%',14,14,18,True,(255,239,215,255))]:
   size=max(1,round(size*scale));caption=_building_caption(text,_building_font(font_at,size,bold,language),size,caption_width,max(1,round(height*scale)),color,bold,bold)
   image.alpha_composite(caption,(content,y+round(top*scale)))
