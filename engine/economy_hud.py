"""Validated personal currency receipts; independent from wallet deltas and native bag feed."""
import bisect,math,collections,io,functools,re
CAUSES={'kill':1,'urn':1,'urn-deny':1,'building':1,'loss':-1,'soul-bag-pickup':1,'soul-bag-stolen':1}
class EconomyTimeline:
 def __init__(self,data,teams,max_events=20000):
  self.events=[];self.times=[]
  if data is None:return
  if not isinstance(data,dict) or data.get('schema')!=1 or data.get('supported') is not True or data.get('identity_verified') is not True: return
  rows=data.get('events');seen=set();last=-1;seq=-1
  if not isinstance(rows,list) or len(rows)>max_events:raise ValueError('economy bound')
  for e in rows:
   if not isinstance(e,dict) or e.get('hero') not in teams or e.get('team')!=teams[e['hero']] or e.get('cause') not in CAUSES:raise ValueError('economy owner/cause')
   if any(type(e.get(n)) is not int for n in ('hero','team','delta','sequence','parent','generation','new_value','source','tick')):raise ValueError('economy values')
   if not 0<abs(e['delta'])<=10000000 or e['delta']*CAUSES[e['cause']]<=0 or not 0<=e['new_value']<=10000000 or e['parent']<=0:raise ValueError('economy amount')
   t=e.get('seconds');key=e.get('id')
   if type(t) not in (int,float) or not math.isfinite(t) or t<last or t<0 or not isinstance(key,str) or not key or len(key)>80 or key in seen or e['sequence']<=seq:raise ValueError('economy event order')
   expected={'kill':(11,12,38),'urn':(33,),'urn-deny':(23,),'building':(13,),'loss':(9,)}
   if e['source'] not in expected.get(e['cause'],()) or e['generation']!=data.get('generation',0):raise ValueError('economy source')
   self.events.append(e);self.times.append(math.ceil(t));seen.add(key);last=t;seq=e['sequence']
class EconomyCursor:
 def __init__(self):self.reset()
 def reset(self):self.previous=None;self.stamp=None;self.scope=None;self.sequence=-1;self.stable=0
 def advance(self,timeline,clock,stamp,scope):
  if type(clock) is not int or clock<0 or not math.isfinite(stamp):self.reset();return []
  end=bisect.bisect_right(timeline.times,clock)
  reset=self.scope!=scope or self.previous is None or clock<self.previous or clock-self.previous>2 or self.stamp is None or not 0<=stamp-self.stamp<=2
  if reset:
   self.sequence=max((e['sequence'] for e in timeline.events[:end]),default=-1);self.stable=stamp+2
  fresh=[e for e in timeline.events[:end] if e['sequence']>self.sequence];self.sequence=max(self.sequence,max((e['sequence'] for e in timeline.events[:end]),default=-1));self.previous=clock;self.stamp=stamp;self.scope=scope
  return [] if reset or stamp<self.stable else [e for e in fresh if clock-math.ceil(e['seconds'])<=1]
class EconomyView:
 # One receipt lane per hero. Do not replace normal money or accumulate old news.
 DISPLAY_SECONDS=2.2
 MAX_WAIT=3.0
 MAX_PENDING=4
 def __init__(self):self.active={};self.pending={};self.seen=collections.deque(maxlen=2000);self.audit=collections.deque(maxlen=1000)
 def clear(self):self.active.clear();self.pending.clear();self.seen.clear()
 def push(self,events,stamp):
  for e in events:
   identity=str(e['id'])
   if identity in self.seen:continue
   self.seen.append(identity);hero=str(e['hero']);self.at(hero,stamp)
   queue=self.pending.setdefault(hero,[]);old=queue[-1] if queue else self.active.get(hero)
   combine=old and old['cause']==e['cause'] and 0<=stamp-old['last']<=1.2
   if combine:
    old['amount']+=e['delta'];old['last']=stamp
    if old is self.active.get(hero):old['until']=min(stamp+self.DISPLAY_SECONDS,old['started']+3.4)
    self.audit.append({**e,'shown_amount':old['amount'],'decision':'combined'});continue
   row={'hero':hero,'cause':e['cause'],'amount':e['delta'],'last':stamp,'received':stamp,'id':identity}
   if hero not in self.active:row.update(started=stamp,until=stamp+self.DISPLAY_SECONDS);self.active[hero]=row;decision='display'
   else:
    if len(queue)>=self.MAX_PENDING:
     removed=queue.pop(0);self.audit.append({'id':removed['id'],'hero':hero,'decision':'queue_limit'})
    queue.append(row);decision='queued'
   self.audit.append({**e,'shown_amount':row['amount'],'decision':decision})
 def at(self,hero,stamp):
  hero=str(hero);row=self.active.get(hero)
  if row and not row['last']<=stamp<row['until']:self.active.pop(hero,None);row=None
  queue=self.pending.get(hero,[])
  while queue and stamp-queue[0]['received']>self.MAX_WAIT:
   removed=queue.pop(0);self.audit.append({'id':removed['id'],'hero':hero,'decision':'queue_expired'})
  if row is None and queue:
   row=queue.pop(0);row.update(started=stamp,until=stamp+self.DISPLAY_SECONDS);self.active[hero]=row
   self.audit.append({'id':row['id'],'hero':hero,'decision':'dequeued','shown_amount':row['amount']})
  if not queue:self.pending.pop(hero,None)
  return row

def native_receipt_owner(players,hero,total):
 from money_hud import native_money_owner
 return native_money_owner(players,hero,total)

@functools.lru_cache(maxsize=512)
def economy_glyph_png(cause,amount,bold):
 from PIL import Image,ImageDraw,ImageFont
 if cause not in CAUSES or type(amount) is not int or amount*CAUSES[cause]<=0:raise ValueError('economy glyph')
 scale=4;im=Image.new('RGBA',(78*scale,20*scale));d=ImageDraw.Draw(im);color=(128,238,255,255) if amount>0 else (255,116,108,255)
 # Signed amount only; cause is retained for validation, queueing and audit.
 text=('+' if amount>0 else '−')+format(abs(amount),',')
 for size in (18,17,16,15,14,13,12,11,10,9):
  font=ImageFont.truetype(bold,size*scale)
  if d.textlength(text,font=font)<=74*scale:break
 d.text((39*scale,16*scale),text,font=font,fill=color,anchor='ms',stroke_width=scale,stroke_fill=(15,18,14,230))
 im=im.resize((78,20),Image.Resampling.LANCZOS);out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()
