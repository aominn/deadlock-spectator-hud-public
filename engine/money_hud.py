"""Exact-roster, native-clock money display. Missing data leaves native total visible."""
import bisect,math,re,os,io,functools
from pathlib import Path
class MoneyTimeline:
 def __init__(self,data,heroes,max_samples=21601):
  self.extra=data or {};self.updates=[];self.times=[];self.heroes=set(heroes);self.teams=heroes if isinstance(heroes,dict) else None
  if data is None:return
  if not isinstance(data,dict) or data.get('schema')!=1 or data.get('columns')!=['hero','team','total','wallet'] or data.get('supported') is not True:raise ValueError('money schema')
  rows=data.get('updates');last=-1
  if not isinstance(rows,list) or len(rows)>max_samples:raise ValueError('money bound')
  for update in rows:
   second=update['second'];values=update['rows']
   if type(second) is not int or second<0 or second<=last or not isinstance(values,list) or len(values) not in (0,12):raise ValueError('money clock/rows')
   if values:
    if any(not isinstance(v,list) or len(v)!=4 or any(type(n) is not int for n in v) or v[0]<=0 or v[1] not in (2,3) or not 0<=v[3]<=v[2]<=10000000 for v in values):raise ValueError('money value')
    if self.teams and any(self.teams.get(v[0])!=v[1] for v in values):raise ValueError('money team')
    if len({v[0] for v in values})!=12 or {v[0] for v in values}!=self.heroes or sum(v[1]==2 for v in values)!=6:raise ValueError('money roster')
   self.updates.append(update);self.times.append(second);last=second
 def at(self,clock,heroes):
  if type(clock) is not int or len(heroes)!=12 or len(set(heroes))!=12 or set(heroes)!=self.heroes:return []
  index=bisect.bisect_right(self.times,clock)-1
  if index<0 or clock-self.times[index]>1:return []
  return self.extra_at(self.extra,clock,[dict(hero=v[0],team=v[1],total=v[2],wallet=v[3]) for v in self.updates[index]['rows']])

 def extra_at(self,data,clock,values):
  if not hasattr(self,'_identity_cache'):
   self._identity_cache=True;self._kda_times=[];self._kda_rows=[];self._sale_times=[];self._sale_rows=[]
   try:
    kd=data.get('kda_updates',[]);last=-1;times=[];records=[]
    if not isinstance(kd,list) or len(kd)>21601:raise ValueError()
    for u in kd:
     t=u['second'];rows=u['rows']
     if type(t) is not int or t<=last or not isinstance(rows,list) or len(rows) not in (0,12):raise ValueError()
     last=t
     if rows and (any(not isinstance(v,list) or len(v)!=5 or any(type(x) is not int for x in v) or v[1] not in (2,3) or any(not 0<=x<=1000 for x in v[2:]) for v in rows) or {v[0] for v in rows}!=self.heroes or len({v[0] for v in rows})!=12 or sum(v[1]==2 for v in rows)!=6 or (self.teams and any(self.teams.get(v[0])!=v[1] for v in rows))):raise ValueError()
     times.append(t);records.append({v[0]:v[2:] for v in rows})
    self._kda_times=times;self._kda_rows=records
   except (ValueError,KeyError,TypeError):pass
   try:
    d=data.get('sales');events=(d or {}).get('events',[]);seq=-1;last=-1;times=[];records=[];seen=set()
    if not d or d.get('schema')!=1 or d.get('supported') is not True:events=[]
    if not isinstance(events,list) or len(events)>20000:raise ValueError()
    for e in events:
     t=e['seconds'];h=e['hero']
     if type(t) not in (int,float) or not math.isfinite(t) or t<last or type(h) is not int or h not in self.heroes or (self.teams and self.teams.get(h)!=e['team']) or e.get('verified_sell') is not True or type(e.get('ability')) is not int or not 0<e['ability']<=4294967295 or type(e.get('sequence')) is not int or e['sequence']<=seq or e.get('generation')!=d.get('generation') or not isinstance(e.get('id'),str) or len(e['id'])>80 or e['id'] in seen:raise ValueError()
     seq=e['sequence'];last=t;seen.add(e['id']);times.append(math.ceil(t));records.append(e)
    self._sale_times=times;self._sale_rows=records
   except (ValueError,KeyError,TypeError):pass
  i=bisect.bisect_right(self._kda_times,clock)-1
  current=self._kda_rows[i] if i>=0 and clock-self._kda_times[i]<=1 else {}
  start=bisect.bisect_left(self._sale_times,clock-1);end=bisect.bisect_right(self._sale_times,clock);recent={}
  for e in self._sale_rows[start:end]:recent.setdefault(e['hero'],[]).append(e)
  for v in values:
   if v['hero'] in current:v['kda']=current[v['hero']]
   if v['hero'] in recent:v['sales']=recent[v['hero']]
  return values


def compact(value):
 return str(value) if value<1000 else ('%.1f'%(value/1000)).rstrip('0').rstrip('.')+'k'
def native_matches(text,total):
 if not isinstance(text,str):return False
 m=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)([kKmM]?)',text.replace(',','').strip())
 if not m:return False
 scale={'':1,'k':1000,'m':1000000}[m[2].lower()];precision=len(m[1].partition('.')[2]);value=float(m[1])*scale
 return abs(value-total)<=scale/(10**precision)/2+5

def native_money_owner(players,hero,total):
 # Validate the current native owner and Label. Source money is separately bound
 # to this match,12heroes and native second; the native total is preserved verbatim.
 if not isinstance(total,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?[kKmM]?',total.replace(',','').strip()):return False
 if len(players)!=12 or len({str(p.get('hero')) for p in players})!=12:return False
 candidates=[p for p in players if str(p.get('hero'))==str(hero)]
 if len(candidates)!=1:return False
 p=candidates[0];meta=p.get('money')
 if not isinstance(meta,dict) or meta.get('total')!=total or type(meta.get('dead')) is not bool:return False
 rect=meta.get('rect')
 if not isinstance(rect,list) or len(rect)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in rect):return False
 try:
  x,y,w,h=rect;center=float(p['pos']['x'])+float(p.get('width',140))/2
  return 0<w<=100 and 0<h<=40 and abs(x+w/2-center)<=30 and 70<=y-float(p['pos']['y'])<=130 and x>=0 and x+w<=7680
 except (KeyError,TypeError,ValueError):return False

def money_records(rows,players,canvas_width,frozen=False):
 if len(rows)!=12 or len(players)!=12 or len({str(p['hero']) for p in players})!=12 or {str(p['hero']) for p in players}!={str(r['hero']) for r in rows}:return []
 byhero={str(r['hero']):r for r in rows};records=[]
 for player in players:
  row=byhero[str(player['hero'])];meta=player.get('money')
  if not isinstance(meta,dict) or not native_money_owner(players,player['hero'],meta.get('total')):continue
  if any(type(row.get(k)) is not int for k in ('hero','team','total','wallet')) or row['team'] not in (2,3) or not 0<=row['wallet']<=row['total']<=10000000:continue
  rect=meta.get('rect');dead=meta.get('dead')
  if not isinstance(rect,list) or len(rect)!=4 or type(dead) is not bool or any(type(n) not in (int,float) or not math.isfinite(n) for n in rect):continue
  x,y,w,h=rect;center=float(player['pos']['x'])+float(player.get('width',140))/2
  if not 0<w<=100 or not 0<h<=40 or abs(x+w/2-center)>30 or not 70<=y-float(player['pos']['y'])<=130 or x<0 or x+w>canvas_width:continue
  records.append({**row,'hero':str(row['hero']),'native_total':meta['total'],'text':(compact(row['total']) if frozen else meta['total'])+'/'+compact(row['wallet']),'rect':rect,'dead':dead,'presentation':'native-container-glyph'})
 return records

def game_fonts():
 # Read the user's installed fonts in place. Never redistribute Valve font data.
 root=Path(os.environ.get('SPEC_HUD_GAME',''))/'panorama/fonts'
 bold=root/'valveoracle-semibold.ttf';regular=root/'valveoracle-medium.ttf'
 if not all(f.is_file() and 0<f.stat().st_size<4*1024*1024 for f in (bold,regular)):raise ValueError('native money font unavailable')
 return str(bold.resolve()),str(regular.resolve())

@functools.lru_cache(maxsize=512)
def glyph_png(total,wallet,bold,regular,tone='light',native_total=None):
 from PIL import Image,ImageDraw,ImageFont
 # Native .SoulsValue is15px with12px demoted k suffix. Supersample only glyphs;
 # background, team tint, death opacity, corners, rejuv border remain native UI.
 if tone not in ('dark','light'):raise ValueError('native money tone')
 if native_total is not None and (not isinstance(native_total,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?[kKmM]?',native_total.replace(',','').strip())):raise ValueError('native money label')
 color=(18,21,15,255) if tone=='dark' else (255,239,215,255)
 scale=4;canvas=Image.new('RGBA',(78*scale,20*scale));ink=ImageDraw.Draw(canvas)
 for size in (15,14,13):
  num=ImageFont.truetype(bold,size*scale);small=ImageFont.truetype(regular,12*scale);parts=[]
  for i,value in enumerate((total,wallet)):
   if i:parts.append(('/',num))
   label=native_total.replace(',','').strip() if i==0 and native_total is not None else compact(value)
   suffix=label[-1:].lower() in ('k','m')
   parts.append((label[:-1] if suffix else label,num))
   if suffix:parts.append((label[-1:],small))
  width=sum(ink.textlength(text,font=font) for text,font in parts)
  if width<=76*scale:break
 else:raise ValueError('money text width')
 x=(78*scale-width)/2
 for text,font in parts:
  ink.text((x,16*scale),text,font=font,fill=color,anchor='ls');x+=ink.textlength(text,font=font)
 canvas=canvas.resize((78,20),Image.Resampling.LANCZOS);out=io.BytesIO();canvas.save(out,format='PNG');return out.getvalue()
