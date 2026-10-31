"""Replay-only receipt cursor. Inert until an exact native playback confirmation.

The bridge activates this only with explicit replay index/file arguments. It never controls the game.
The caller must apply the existing two-slot, two-second notification policy.
"""
from pathlib import Path
import bisect,collections,hashlib,json,math,re
from bridge_buffs import BridgeTimeline
from money_hud import MoneyTimeline
from economy_hud import EconomyTimeline,EconomyCursor

class ReplayEffectSource:
 def __init__(self,index):
  if index.get('schema')!=2 or not index.get('success'):raise ValueError('unverified index')
  self.base_guardians=index.get('base_guardians');self.match=str(index.get('match',''))
  if not re.fullmatch(r'\d{6,12}',self.match):raise ValueError('match')
  self.digest=index.get('source_sha256','')
  if not re.fullmatch(r'[0-9a-f]{64}',self.digest):raise ValueError('digest')
  roster=index.get('roster',[])
  if len(roster)!=12:raise ValueError('roster count')
  self.owners={p['parent'] if 'parent' in p else p['handle']:p['hero'] for p in roster}
  self.heroes={p['hero'] for p in roster}
  if len(self.owners)!=12 or len(self.heroes)!=12:raise ValueError('ambiguous roster')
  self.events=sorted(index.get('events',[]),key=lambda e:e['seconds']);seen=set()
  for event in self.events:
   if self.owners.get(event['parent'])!=event['hero']:raise ValueError('owner mismatch')
   key=(event['parent'],event['serial'])
   if key in seen:raise ValueError('duplicate application')
   seen.add(key)
   if not isinstance(event['seconds'],(int,float)) or not math.isfinite(event['seconds']) or event['seconds']<0:raise ValueError('clock')
   if event.get('polarity') not in ('buff','debuff'):raise ValueError('polarity')
  self.economy=EconomyTimeline(index.get('economy'),{p['hero']:p.get('team') for p in roster});self.economy_cursor=EconomyCursor()
  if any(self.owners.get(e['parent'])!=e['hero'] for e in self.economy.events):raise ValueError('economy pawn mismatch')
  self.bridge=BridgeTimeline(index.get('bridge'),self.owners)
  try:self.money=MoneyTimeline(index.get('money'),{p['hero']:p.get('team') for p in roster})
  except (ValueError,KeyError,TypeError):self.money=MoneyTimeline(None,self.heroes)
  self.times=[math.floor(e['seconds']) for e in self.events]
  self.bound=False;self.previous=None;self.cursor=0;self.stable_after=0;self.last_stamp=None;self.metrics=collections.Counter()

 def economy_advance(self,clock,heroes,stamp):
  if not self.bound or len(heroes)!=12 or set(heroes)!=self.heroes:self.economy_cursor.reset();return []
  return self.economy_cursor.advance(self.economy,clock,stamp,self.digest)

 def money_at(self,clock,heroes):
  return self.money.at(clock,heroes) if self.bound else []

 def bridge_at(self,clock,heroes):
  if not self.bound or set(heroes)!=self.heroes or len(heroes)!=12:return []
  return self.bridge.at(clock)

 @classmethod
 def from_files(cls,index_path,replay_path):
  index=json.loads(Path(index_path).read_text(encoding='utf-8'))
  obj=cls(index);replay=Path(replay_path)
  if replay.name!=obj.match+'.dem':raise ValueError('replay filename mismatch')
  before=replay.stat();digest=hashlib.sha256()
  with replay.open('rb') as stream:
   for chunk in iter(lambda:stream.read(2*1024*1024),b''):digest.update(chunk)
  after=replay.stat()
  if digest.hexdigest()!=obj.digest or before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise ValueError('replay content mismatch')
  return obj

 def reset_cursor(self):
  self.economy_cursor.reset()
  self.previous=None;self.cursor=0;self.stable_after=0;self.last_stamp=None

 def observe_log(self,line):
  # Loading/disconnecting always disables the old match before another can bind.
  if '[Demo] Requesting playback of ' in line or '[Client] Disconnecting from server:' in line or 'CHostStateMgr::QueueNewRequest(' in line:
   self.bound=False;self.reset_cursor();self.metrics['unbound']+=1
  if '[Demo] Demo Skipping:' in line:self.reset_cursor();self.metrics['seek_log']+=1
  match=re.search(r"\[Demo\] playing demo from '(?:replays[/\\])?(\d+)\.dem'",line)
  if match:
   self.bound=match[1]==self.match;self.reset_cursor();self.metrics['bound' if self.bound else 'wrong_match']+=1
  return self.bound

 def advance(self,clock,heroes,stamp):
  """Return each application once, at display-clock second precision.

  Seek/load/roster mismatch/long heartbeat gap establishes a silent baseline.
  Same serial refreshes were suppressed by the extractor. Clock pause returns
  no repeats. Duration -1 is never interpreted as an effect expiry countdown.
  """
  if not self.bound or set(heroes)!=self.heroes or len(heroes)!=12:
   self.reset_cursor();self.metrics['scope_rejected']+=1;return []
  if not isinstance(clock,int) or clock<0 or not isinstance(stamp,(int,float)) or not math.isfinite(stamp):raise ValueError('clock/stamp')
  reset=self.previous is None or clock<self.previous or clock-self.previous>2 or (self.last_stamp is not None and (stamp<self.last_stamp or stamp-self.last_stamp>2))
  self.last_stamp=stamp
  end=bisect.bisect_right(self.times,clock)
  if reset:
   self.previous=clock;self.cursor=end;self.stable_after=stamp+2;self.metrics['baselines']+=1;return []
  start=self.cursor;self.cursor=end;self.previous=clock
  if stamp<self.stable_after:self.metrics['guarded']+=end-start;return []
  result=self.events[start:end];self.metrics['receipts']+=len(result);return result
