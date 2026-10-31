"""Live-only receipt cursor. Route, roster, freshness and native clock are mandatory.

No network or game control. Producer JSON is local and contains no private TV URL.
This adapter is separate from the hash-bound replay index.
"""
import collections,hashlib,math,re,copy
from urllib.parse import urlsplit
from native_session import lobby_line
from bridge_buffs import BridgeTimeline
from money_hud import MoneyTimeline
from economy_hud import EconomyTimeline,EconomyCursor

class LiveEffectSource:
 def __init__(self):
  self.final_snapshot=None;self.final_clock=None;self.final_native_clock=None;self.phase='waiting';self.route=None;self.session=None;self.generation=None;self.previous=None;self.last_stamp=None
  self.economy_cursor=EconomyCursor();self.economy_cache=None;self.economy_key=None
  self.cursor=0;self.pending={};self.stable_after=0;self.metrics=collections.Counter();self.bound=False;self.bridge_cache=None;self.bridge_key=None;self.decisions=collections.deque(maxlen=2000)
 def reset(self):
  self.final_snapshot=None;self.final_clock=None;self.final_native_clock=None
  self.phase='waiting';self.economy_cursor=EconomyCursor();self.economy_cache=None;self.economy_key=None
  self.session=None;self.generation=None;self.previous=None;self.last_stamp=None;self.cursor=0;self.pending.clear();self.bound=False;self.bridge_cache=None;self.bridge_key=None
 def observe_log(self,line):
  if self.final_snapshot is not None and '[Client] Disconnecting from server:' in line and not lobby_line(line):return
  if lobby_line(line) or any(x in line for x in ('[Demo] Requesting playback of ','[Client] Disconnecting from server:','CHostStateMgr::QueueNewRequest(')):
   self.route=None;self.reset();self.metrics['unbound']+=1
  found=re.search(r"\[Client\].*creating client connection to '([^']+)'",line)
  if found:
   try:u=urlsplit(found[1])
   except ValueError:
    self.route=None;self.reset();self.metrics['invalid_route']+=1;return
   valid=u.scheme in ('http','https') and u.hostname and u.hostname.endswith('.steamcontent.com') and re.fullmatch(r'/tv/[^/]+',u.path) and not u.query and not u.fragment and not u.username and not u.password
   self.route=hashlib.sha256(found[1].encode()).hexdigest() if valid else None
   self.reset();self.metrics['route_bound' if valid else 'invalid_route']+=1
 def advance(self,snapshot,clock,heroes,stamp,wall,postgame=False):
  def reject(reason):
   self.reset();self.metrics[reason]+=1;return []
  if snapshot is None and self.final_snapshot is not None and self.route==self.final_snapshot.get('route_sha256'):snapshot=self.final_snapshot
  if not self.route or not isinstance(snapshot,dict) or snapshot.get('schema')!=1 or snapshot.get('route_sha256')!=self.route:return reject('route_rejected')
  if self.final_snapshot is not None:
   f=self.final_snapshot
   if snapshot.get('session')!=f['session'] or snapshot.get('generation')!=f['generation'] or snapshot.get('roster')!=f['roster'] or len(heroes)!=12 or set(heroes)!={p['hero'] for p in f['roster']} or type(clock) is not int or clock<self.final_native_clock:return reject('final_scope_changed')
   self.phase='ended';self.bound=True;self.previous=clock;self.last_stamp=stamp;return []
  # Native broadcast fragments are spaced3s apart in the verified sync.
  # Allow6s receive age; native-clock and per-event age guards still apply.
  updated=snapshot.get('updated_at');stream_clock=snapshot.get('game_seconds')
  ending=snapshot.get('state')=='ended' and snapshot.get('game_state')==11
  if not isinstance(updated,(int,float)) or not math.isfinite(updated) or not ending and not 0<=wall-updated<=6:return reject('stale_producer')
  if not isinstance(clock,int) or isinstance(clock,bool) or clock<0 or not isinstance(stream_clock,(int,float)) or not math.isfinite(stream_clock):return reject('invalid_clock')
  if not ending and not -2<=stream_clock-clock<=20:return reject('clock_mismatch')
  phase=snapshot.get('state')
  if phase not in ('ready','paused','baselining','ended'):return reject('producer_not_ready')
  if phase=='ended' and snapshot.get('game_state')!=11:return reject('unconfirmed_end')
  roster=snapshot.get('roster',[])
  try:
   owners={p['handle']:p['hero'] for p in roster};expected={p['hero'] for p in roster}
   if len(roster)!=12 or len(owners)!=12 or len(expected)!=12 or len(heroes)!=12 or set(heroes)!=expected or any(not isinstance(p['handle'],int) or p['handle']<=0 or not isinstance(p['hero'],int) or p['hero']<=0 or p['team'] not in (2,3) for p in roster) or sum(p['team']==2 for p in roster)!=6:raise ValueError()
   session=snapshot['session'];generation=snapshot['generation']
   if not isinstance(session,str) or not re.fullmatch(r'[0-9a-f]{32}',session) or not isinstance(generation,int) or generation<0:raise ValueError()
   events=snapshot.get('events',[])
   if len(events)>512:raise ValueError()
   prior=0
   for e in events:
    if not isinstance(e['sequence'],int) or e['sequence']<=prior or e['generation']!=generation or owners.get(e['parent'])!=e['hero'] or not isinstance(e['serial'],int) or e['serial']<0 or e['polarity'] not in ('buff','debuff') or not isinstance(e['seconds'],(int,float)) or not math.isfinite(e['seconds']) or e['seconds']<0 or not isinstance(e['path'],str) or not e['path'] or not isinstance(e['effect'],str):raise ValueError()
    prior=e['sequence']
  except (KeyError,TypeError,ValueError):return reject('invalid_snapshot')
  if phase=='ended':
   # Producer can finish ahead of the delayed spectator. Continue exact historical
   # samples until the native UI also confirms postgame; never borrow future money.
   if not -2<=stream_clock-clock<=120 or self.previous is not None and clock<self.previous:return reject('end_clock_mismatch')
   target=math.floor(stream_clock) if postgame is True else clock
   try:rows=MoneyTimeline(snapshot.get('money'),{p['hero']:p['team'] for p in roster},max_samples=90).at(target,heroes)
   except (ValueError,KeyError,TypeError):return reject('end_money_invalid')
   if len(rows)!=12:return reject('end_money_missing')
   if postgame is True:
    self.final_snapshot=copy.deepcopy(snapshot);self.final_clock=target;self.final_native_clock=clock
   self.phase='ended' if postgame is True else 'finishing';self.session=session;self.generation=generation;self.previous=clock;self.last_stamp=stamp;self.bound=True;self.pending.clear();return []
  if phase!='ready':
   self.reset();self.phase=phase;self.session=session;self.generation=generation;self.previous=clock;self.last_stamp=stamp;self.bound=True
   self.metrics['static_'+phase]+=1;return []
  reset=self.phase!='ready' or (session,generation)!=(self.session,self.generation) or self.previous is None or clock<self.previous or clock-self.previous>2 or self.last_stamp is None or not 0<=stamp-self.last_stamp<=2
  if reset:
   self.reset();self.session=session;self.generation=generation;self.stable_after=stamp+2
   self.cursor=max((e['sequence'] for e in events),default=0)
   self.pending={e['sequence']:e for e in events if e['seconds']>=clock+1}
   self.metrics['baselines']+=1
   for e in events:
    if e['seconds']<clock+1:self.decisions.append({'session':session,'generation':generation,'sequence':e['sequence'],'clock':clock,'reason':'baseline_existing'})
  else:
   for e in events:
    if e['sequence']>self.cursor:self.pending[e['sequence']]=e
   self.cursor=max(self.cursor,max((e['sequence'] for e in events),default=0))
  self.phase='ready';self.bound=True;self.previous=clock;self.last_stamp=stamp;fresh=[]
  for seq,event in list(self.pending.items()):
   if event['seconds']>=clock+1:continue
   del self.pending[seq]
   if stamp<self.stable_after:
    self.metrics['guarded']+=1;self.decisions.append({'session':session,'generation':generation,'sequence':seq,'clock':clock,'reason':'initial_guard'});continue
   if clock-math.floor(event['seconds'])>1:
    self.metrics['stale_application']+=1;self.decisions.append({'session':session,'generation':generation,'sequence':seq,'clock':clock,'reason':'late_application'});continue
   fresh.append(event);self.decisions.append({'session':session,'generation':generation,'sequence':seq,'clock':clock,'reason':'forwarded_to_hud'})
  if len(self.pending)>512:return reject('pending_overflow')
  self.metrics['receipts']+=len(fresh)
  return fresh

 def economy_advance(self,snapshot,clock,heroes,stamp):
  if not self.bound or self.phase!='ready' or not isinstance(snapshot,dict):self.economy_cursor.reset();return []
  data=snapshot.get('economy');key=(self.session,self.generation,snapshot.get('updated_at'))
  try:
   if key!=self.economy_key:
    self.economy_cache=EconomyTimeline(data,{p['hero']:p['team'] for p in snapshot['roster']},max_events=512);self.economy_key=key
    owners={p['handle']:p['hero'] for p in snapshot['roster']}
    if any(owners.get(e['parent'])!=e['hero'] for e in self.economy_cache.events):raise ValueError('economy pawn mismatch')
   return self.economy_cursor.advance(self.economy_cache,clock,stamp,(self.session,self.generation,(data or {}).get('generation')))
  except (ValueError,KeyError,TypeError):self.economy_cursor.reset();self.metrics['economy_rejected']+=1;return []

 def money_at(self,snapshot,clock,heroes):
  if self.final_snapshot is not None:snapshot=self.final_snapshot;clock=self.final_clock
  if not self.bound or not isinstance(snapshot,dict):return []
  try:return MoneyTimeline(snapshot.get('money'),{p['hero']:p['team'] for p in snapshot['roster']},max_samples=90).at(clock,heroes)
  except (ValueError,KeyError,TypeError):return []

 def bridge_at(self,snapshot,clock,heroes):
  # advance() has already verified current route/session/roster/freshness/clock.
  if self.final_snapshot is not None:snapshot=self.final_snapshot;clock=self.final_clock
  if not self.bound or not isinstance(snapshot,dict):return []
  data=snapshot.get('bridge')
  if not isinstance(data,dict) or data.get('state')!='ready':return []
  key=(self.session,self.generation,snapshot.get('updated_at'))
  try:
   if key!=self.bridge_key:
    self.bridge_cache=BridgeTimeline(data,{p['handle']:p['hero'] for p in snapshot['roster']},max_updates=128);self.bridge_key=key
   return self.bridge_cache.at(clock)
  except (ValueError,KeyError,TypeError):
   self.bridge_cache=None;self.bridge_key=None;self.metrics['bridge_rejected']+=1;return []
