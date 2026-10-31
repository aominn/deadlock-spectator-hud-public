"""Validated bridge-buff timelines and stable two-slot presentation."""
from pathlib import Path
import bisect,json,math
RULES={r['type']:r for r in json.loads((Path(__file__).resolve().parent.parent/'parser/data/bridge-buffs.json').read_text(encoding='utf-8'))['rules']}
class BridgeTimeline:
 def __init__(self,data,owners,max_updates=20000):
  self.times=[];self.rows=[]
  if data is None:return
  if not isinstance(data,dict) or data.get('schema')!=1:raise ValueError('bridge schema')
  updates=data.get('updates',[])
  if not isinstance(updates,list) or len(updates)>max_updates:raise ValueError('bridge updates')
  prior=-1
  for update in updates:
   at=update['seconds'];rows=update['rows'];seen=set()
   if isinstance(at,bool) or not isinstance(at,(int,float)) or not math.isfinite(at) or at<prior or at<0 or not isinstance(rows,list) or len(rows)>48:raise ValueError('bridge clock/rows')
   clean=[]
   for row in rows:
    hero,parent,serial,kind=row['hero'],row['parent'],row['serial'],row['type'];applied,expires=row['applied'],row['expires']
    if owners.get(parent)!=hero or kind not in RULES or not isinstance(serial,int) or isinstance(serial,bool) or serial<0 or (hero,kind) in seen:raise ValueError('bridge identity')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (applied,expires)) or applied<0 or applied>at+.25 or not 0<expires-applied<=600 or expires<=at:raise ValueError('bridge duration')
    seen.add((hero,kind));clean.append(dict(hero=hero,parent=parent,serial=serial,type=kind,applied=applied,expires=expires))
   self.times.append(at);self.rows.append(clean);prior=at
 def at(self,clock):
  i=bisect.bisect_right(self.times,clock)-1
  return [dict(r) for r in self.rows[i] if r['applied']<=clock<r['expires']] if i>=0 else []

class BridgeView:
 def __init__(self):self.clear()
 def clear(self):self.heroes={};self.last=None
 def update(self,rows,stamp,clock=0):
  if self.last is not None and not 0<=stamp-self.last<=2:self.clear()
  self.last=stamp;by_hero={}
  for row in rows:by_hero.setdefault(str(row['hero']),{})[row['type']]=row
  out=[]
  for hero in set(by_hero)|set(self.heroes):
   active=by_hero.get(hero,{});slots=self.heroes.setdefault(hero,[None,None])
   for i,slot in enumerate(slots):
    if not slot:continue
    if slot['type'] in active:
     if slot['gone'] is not None:slot['entered']=stamp
     slot['gone']=None;slot['row']=active[slot['type']]
    elif slot['gone'] is None:slot['gone']=stamp
    if slot['gone'] is not None and stamp-slot['gone']>=.18:slots[i]=None
   held={s['type'] for s in slots if s}
   pending=sorted((r for kind,r in active.items() if kind not in held),key=lambda r:(r['applied'],r['type']))
   for row in pending:
    if None not in slots:break
    i=slots.index(None);slots[i]={'type':row['type'],'entered':stamp,'gone':None,'row':row}
   overflow=max(0,len(active)-sum(s is not None and s['type'] in active for s in slots))
   for i,slot in enumerate(slots):
    if slot:
     opacity=min(1,max(0,(stamp-slot['entered'])/.2)) if slot['gone'] is None else max(0,1-(stamp-slot['gone'])/.18)
     row=slot['row'];fraction=max(0,min(1,(row['expires']-clock)/(row['expires']-row['applied'])))
     out.append({'fraction':fraction,'hero':hero,'slot':i,'type':slot['type'],'opacity':opacity,'overflow':overflow if i==1 else 0})
   if slots==[None,None] and not active:del self.heroes[hero]
  return out

def bridge_geometry(player,slot,canvas_width=1920):
 center=float(player['pos']['x'])+float(player.get('width',140))/2
 offset=(-32-21*slot) if center<canvas_width/2 else (12+21*slot)
 return round(center+offset),int(player['pos']['y'])+125,20,20
