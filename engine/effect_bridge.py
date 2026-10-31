"""Read-only native effect snapshots -> loopback transparent HUD PNG. No input automation."""
from pathlib import Path
from http.server import ThreadingHTTPServer as _ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
import io,json,re,time,threading,os,argparse,collections,functools,math,base64
from PIL import Image,ImageDraw,ImageFont
from native_session import mode_signal,lobby_line,resume_log
ROOT=Path(__file__).resolve().parent
STATE=Path(os.environ.get('SPEC_HUD_STATE',str(ROOT))).resolve();STATE.mkdir(parents=True,exist_ok=True)
CAT=json.loads((ROOT/'effect-catalog.json').read_text(encoding='utf-8'))
DISPLAY_IDENTITIES=json.loads((ROOT/'display-identities.json').read_text(encoding='utf-8'))
DISPLAY_POLICY=json.loads((ROOT/'effect-policy.json').read_text(encoding='utf-8'))['modifiers']
HEADER=re.compile(r'Client Modifiers \[entity (\d+) \(player\)\]:')
ENTRY=re.compile(r'^\s*\[(\d+)\]\s+([^\s]+)\s+\(([^)]+)\)(?:\s+\(([-+\d.eE]+)\))?\s*$')
ENTITY=re.compile(r"'player'\s*:\s*'(hero_[\w]+)'\s*\(entindex (\d+)\)")
PREFIX=re.compile(r'^\d\d/\d\d \d\d:\d\d:\d\d ')
TOKEN='spec-debuff-local-8a71'
VISIBLE_LANES=4
MAX_NOTICES=64
ICON_MAP=json.loads((ROOT/'icon-map.json').read_text(encoding='utf-8'))
WORLD_REPORTS={};WORLD_SAVED=0
REPLAY=None;REPLAY_WINDOWS={};REPLAY_SESSION=None
LIVE=None;LIVE_PATH=None;LIVE_WINDOWS={}
from money_hud import money_records,game_fonts,glyph_png,native_matches
from economy_hud import EconomyView,economy_glyph_png,native_receipt_owner
from live_effect_source import LiveEffectSource
from replay_effect_source import ReplayEffectSource
from base_guardian_hud import GuardianView,draw_guardian_rows,TowerGrid
from drawing_hud import DrawingStore
from bridge_buffs import BridgeView,RULES as BRIDGE_RULES,bridge_geometry
WORLD_CAT=json.loads((ROOT/'world-effect-catalog.json').read_text(encoding='utf-8'))['classes']
def MARKER_IN_LINE(line):
 return any(x in line for x in ('CHostStateMgr::QueueNewRequest(', '[Client] Disconnecting from server:', '[Demo] playing demo from ', 'creating client connection to '))

class State:
 def __init__(self):
  self.language="ja";self.drawing=DrawingStore();self.tower_grid=TowerGrid();self.guardian_view=GuardianView();self.guardian_rows=[];self.kda_hold={};self.sale_ready=False;self.sale_seen=collections.deque(maxlen=2000);self.sale_active={};self.economy_view=EconomyView();self.money_rows=[];self.bridge_view=BridgeView();self.bridge_rows=None;self.notice_order=0;self.feeds={};self.camera_owner=None;self.camera_since=0;self.camera_at=0;self.entities={};self.snapshots={};self.observed={};self.notifications={};self.last_notice={};self.history=collections.deque(maxlen=3000);self.history_saved=None;self.record_saved=None;self.metrics=collections.Counter();self.suppressed=collections.deque(maxlen=1000);self.status_saved=0
  self.session_signal=None;self.native_confirmed=False;self.native_sequence=None
  self.current=None;self.rows=[];self.last_http=0;self.last_clock=None;self.postgame=False;self.stable_after=0;self.frames=0;self.samples=0;self.roster=[];self.lock=threading.RLock();self.last_cfg=None;self.last_heartbeat=None;self.native_at=0;self.stop=False
 def reset(self):
  self.postgame=False
  self.tower_grid.clear();self.guardian_view.clear();self.guardian_rows=[];self.kda_hold.clear();self.sale_ready=False;self.sale_seen.clear();self.sale_active.clear();self.economy_view.clear();self.money_rows=[];self.bridge_view.clear();self.bridge_rows=None;self.live_bridge_rows=[]
  if REPLAY is not None:REPLAY.reset_cursor();REPLAY_WINDOWS.clear()
  if LIVE is not None:LIVE.reset();LIVE_WINDOWS.clear()
  self.feeds.clear();self.camera_owner=None;self.camera_since=0;self.camera_at=0;self.snapshots.clear();self.entities.clear();self.observed.clear();self.notifications.clear();self.last_notice.clear();self.current=None;self.rows=[];self.stable_after=time.monotonic()+2;self.metrics['scope_or_seek_resets']+=1;WORLD_REPORTS.clear()
 def expire(self,entity,stamp):
  notices=self.notifications.get(entity,{})
  for key in list(notices):
   if notices[key]['until']<=stamp:del notices[key];self.metrics['expired']+=1
 def finish(self):
  if self.current is not None:
   stamp=time.monotonic();entity=self.current;rows={x['source']+'/'+x['modifier']:x for x in self.rows};prior=self.observed.get(entity);old=self.snapshots.get(entity)
   if old and stamp-old[0]>3:prior=None;self.metrics['stale_baselines']+=1
   self.expire(entity,stamp)
   if prior is None:self.metrics['initial_baselines']+=1
   elif stamp>=self.stable_after and stamp-self.native_at<2 and stamp-self.last_http<2:
    for key in sorted(rows.keys()-prior,key=lambda k:(-rows[k].get('priority',100 if any(x in rows[k]['effect'] for x in ['スタン','睡眠','武装解除','サイレンス','移動不能']) else (30 if rows[k]['polarity']=='buff' else 60)),k)):
     row=rows[key];self.metrics['new_receipts']+=1
     if stamp-self.last_notice.get((entity,key),-100000)<2:
      self.metrics['coalesced']+=1;self.suppressed.append({'at':time.time(),'clock':self.last_heartbeat,'hero':entity,'key':key,'reason':'rapid_reapply_coalesced'});continue
     severity=row.get('priority',100 if any(x in row['effect'] for x in ['スタン','睡眠','武装解除','サイレンス','移動不能']) else (30 if row['polarity']=='buff' else (40 if row['modifier']=='unidentified_debuff' else 60)))
     event={**row,'priority':severity,'started':stamp,'until':stamp+NOTICE_SECONDS,'clock':self.last_heartbeat};active=self.notifications.setdefault(entity,{})
     if len(active)>=MAX_NOTICES:
      oldest=min(active,key=lambda k:(active[k]['started'],active[k].get('order',0)))
      self.suppressed.append({'at':time.time(),'clock':self.last_heartbeat,'hero':entity,'key':oldest,'reason':'bounded_oldest_receipt_evicted'});del active[oldest];self.metrics['oldest_evicted']+=1
     self.notice_order+=1;event['order']=self.notice_order
     event['lane']=min(range(VISIBLE_LANES),key=lambda lane:(sum(v.get('lane',0)==lane for v in active.values()),max((v.get('order',0) for v in active.values() if v.get('lane',0)==lane),default=-1),lane))
     active[key]=event;self.last_notice[(entity,key)]=stamp;self.metrics['admitted']+=1
     self.history.append({'observed_at':time.time(),'observation_clock':self.last_heartbeat,'entity':entity,'hero_name':self.entities.get(entity),'source':row['source'],'modifier':row['modifier'],'polarity':row['polarity'],'effect':row['effect'],'source_scope':row.get('source_scope','world-panel'),'replay_match':row.get('replay_match'),'cause_label':row.get('cause_label',''),'application_sequence':row.get('application_sequence'),'serial':row.get('serial'),'meaning':'newly observed visible status; not authoritative application timestamp'})
   else:self.metrics['guarded_samples']+=1
   self.observed[entity]=set(rows);self.snapshots[entity]=(stamp,list(rows.values()),self.last_heartbeat);self.samples+=1
  self.current=None;self.rows=[]
 def line(self,line):
  line=PREFIX.sub('',line)
  signal=mode_signal(line)
  if signal:
   key=(signal['id'],signal['seq'])
   if self.native_sequence and key[0]==self.native_sequence[0] and key[1]<=self.native_sequence[1]:return
   self.native_sequence=key
   if signal['kind'] not in ('replay','spectator') or self.session_signal and (signal.get('id'),signal['kind'])!=(self.session_signal.get('id'),self.session_signal.get('kind')):self.drawing.clear()
   if signal['kind']=='lobby' and self.native_confirmed:
    for source in (LIVE,REPLAY):
     if source is not None:source.observe_log('[Client] Disconnecting from server: native lobby confirmed')
    self.native_confirmed=False;self.reset()
   elif signal['kind']=='spectator' and LIVE is not None and LIVE.route or signal['kind']=='replay' and REPLAY is not None and getattr(REPLAY,'target',None):self.native_confirmed=True
   self.session_signal=signal
   pending=STATE/'session-mode.pending';pending.write_text(json.dumps(signal,ensure_ascii=False),encoding='utf-8');os.replace(pending,STATE/'session-mode.json')
   return
  if MARKER_IN_LINE(line):self.native_confirmed=False;self.drawing.clear()
  if lobby_line(line):self.session_signal={'kind':'lobby','source':'native-map','at':time.time()}
  if LIVE is not None:
   old=LIVE.route;LIVE.observe_log(line)
   if old!=LIVE.route:self.reset()
  if REPLAY is not None:
   old=REPLAY.bound;REPLAY.observe_log(line)
   if old!=REPLAY.bound or '[Demo] Demo Skipping:' in line:self.reset()
  if '[SpecTowerLayout]' in line:
   try:self.tower_grid.update(json.loads(line.split('[SpecTowerLayout]',1)[1]),time.monotonic())
   except (ValueError,KeyError,TypeError):pass
   return
  if '[SpecEconomyReceipt]' in line:
   try:accept_bag(json.loads(line.split('[SpecEconomyReceipt]',1)[1]))
   except (ValueError,KeyError,TypeError):pass
   return
  if '[SpecDebuffHeartbeat]' in line:
   try:self.last_heartbeat=json.loads(line.split('[SpecDebuffHeartbeat]',1)[1])['time'];self.native_at=time.monotonic()
   except (ValueError,KeyError):pass
  if ((REPLAY is not None and (REPLAY.bound or getattr(REPLAY,'automatic',False))) or (LIVE is not None and LIVE.bound)) and ('[SpecObservedModifiers]' in line or '[SpecUnitStatus]' in line):return
  if '[SpecObservedModifiers]' in line:
   try:accept_observed(json.loads(line.split('[SpecObservedModifiers]',1)[1]))
   except (ValueError,KeyError,TypeError):pass
   return
  if '[SpecUnitStatus]' in line:
   try:accept_world(json.loads(line.split('[SpecUnitStatus]',1)[1]))
   except (ValueError,KeyError,TypeError):pass
   return
 def snapshot_line(self,line):
  # Historical offline parser, exercised by tests only; live watcher never calls it.
  line=PREFIX.sub('',line)
  m=ENTITY.search(line)
  if m:self.entities[int(m[2])]=m[1];return
  h=HEADER.search(line)
  if h:self.finish();self.current=int(h[1]);return
  if 'Found 0 matches.' in line:self.finish();return
  m=ENTRY.match(line)
  if m and self.current is not None and len(self.rows)<128:
   item=CAT['modifiers'].get(m[2])
   if item and 'intrinsic' not in m[3]:self.rows.append({**item,'serial':int(m[1])})
 def context(self,data):
  clock=data.get('time','');m=re.fullmatch(r'(\d+):(\d\d)',clock)
  if not m or int(m[2])>=60:raise ValueError('clock')
  now=int(m[1])*60+int(m[2]);players=data.get('players',[])
  if len(players)!=12:raise ValueError('roster count')
  if len({str(p['hero']) for p in players})!=12:raise ValueError('ambiguous heroes')
  valid_heroes={str(x) for x in CAT['heroes'].values()}
  for p in players:
   if str(p['hero']) not in valid_heroes:raise ValueError('hero')
   if not all(isinstance(p['pos'].get(k),(int,float)) and 0<=p['pos'][k]<10000 for k in ('x','y')):raise ValueError('position')
  if self.last_clock is None or now<self.last_clock or (now-self.last_clock>2 or time.monotonic()-self.last_http>2) and not confirmed_final() or self.roster and {str(p['hero']) for p in players}!={str(p['hero']) for p in self.roster}:self.reset()
  self.language='ja' if data.get('language','ja')=='ja' else 'en';self.postgame=data.get('postgame') is True;self.last_clock=now;self.last_http=time.monotonic();self.roster=players;return now
 def visible(self,hero,now):
  stamp=time.monotonic()
  if stamp<self.stable_after or stamp-self.native_at>3:return []
  matches=[entity for entity,name in self.entities.items() if str(CAT['heroes'].get(name))==str(hero)]
  if len(matches)!=1:return []
  self.expire(matches[0],stamp);notices=self.notifications.get(matches[0],{})
  return sorted(notices.values(),key=lambda x:(x['started'],x.get('order',0)))[:MAX_NOTICES]
S=State()
@functools.lru_cache(maxsize=12)
def font_at(size):return ImageFont.truetype(str(ROOT/'fonts/NotoSansJP-Bold.ttf'),size)
def icon_name(event):
 if event.get('source')=='native_status':return ICON_MAP['statuses'].get(event.get('modifier'))
 return ICON_MAP['sources'].get(event.get('source')) or ICON_MAP['statuses'].get({'サイレンス':'silence_proc','睡眠':'sleep_proc','武装解除':'disarm_proc','スタン':'stunned','パリースタン':'stunned'}.get(event.get('effect')))
@functools.lru_cache(maxsize=128)
def icon_image(name,size=18):
 if not name or Path(name).name!=name:return None
 try:
  with Image.open(ROOT/'icons'/name) as source:return source.convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)
 except (OSError,ValueError):return None

@functools.lru_cache(maxsize=128)
def effect_icon_image(name):
 if not name or Path(name).name!=name:return None
 try:
  with Image.open(ROOT/'icons'/name) as source:icon=source.convert('RGBA')
  box=icon.getchannel('A').point(lambda a:255 if a>=16 else 0).getbbox()
  if box is None:return None
  icon=icon.crop(box);icon.thumbnail((24,24),Image.Resampling.LANCZOS)
  canvas=Image.new('RGBA',(24,24));canvas.alpha_composite(icon,((24-icon.width)//2,(24-icon.height)//2));return canvas
 except (OSError,ValueError):return None

FONT=font_at(13)
SMALL=font_at(10)
NOTICE_WIDTH=38
NOTICE_HEIGHT=34
NOTICE_PITCH=36
NOTICE_SPAN=142
CARD_TOP=184

def corner_geometry(player,canvas_width):
 # Expand into the gap, retaining the portrait-facing edge and top alignment.
 cell_width=float(player.get('width',140));center=float(player['pos']['x'])+cell_width/2
 side='left' if center<canvas_width/2 else 'right'
 x=round(center+45 if side=='left' else center-45-NOTICE_WIDTH)
 y=max(0,int(player['pos']['y']))
 return max(0,min(canvas_width-NOTICE_WIDTH,x)),y,NOTICE_WIDTH,side

def card_obstacles(players,canvas_width):
 # Only bounded native card geometry is used. Old clients conservatively reserve
 # both possible cards rather than allowing a receipt to cover an unknown card.
 result=[]
 for player in players:
  boxes=player.get('cards')
  if not isinstance(boxes,list):
   center=float(player['pos']['x'])+float(player.get('width',140))/2
   boxes=[[center-67,float(player['pos']['y'])+CARD_TOP+i*62,134,58] for i in range(2)]
  for box in boxes[:2]:
   if not isinstance(box,(list,tuple)) or len(box)!=4:continue
   if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in box):continue
   x,y,width,height=box
   if 0<=x<canvas_width and 0<=y<400 and 0<width<=160 and 0<height<=80:result.append((x,y,width,height))
 return result

def clear_receipt_top(x,top,width,height,obstacles):
 # Move only downward past intersecting native purchase/ability cards.
 for _ in range(len(obstacles)+1):
  hits=[y+h+6 for cx,y,cw,h in obstacles if x<cx+cw and cx<x+width and top<y+h and y<top+height]
  if not hits:return top
  top=max(hits)
 return top



NOTICE_SECONDS=3.0
FADE_SECONDS=0.7
STACK_ENTER_SECONDS=0.45

def receipt_layout(notices,x,y,width,obstacles,stamp=None):
 stamp=time.monotonic() if stamp is None else stamp
 ordered=sorted((e for e in notices if e['until']>stamp),key=lambda e:(e['started'],e.get('order',0)))
 if len(ordered)<=VISIBLE_LANES:
  placed=[];used=set()
  for event in ordered:
   preferred=int(event.get('lane',0))%VISIBLE_LANES
   lane=preferred if preferred not in used else next(n for n in range(VISIBLE_LANES) if n not in used)
   used.add(lane);top=clear_receipt_top(x,y+lane*NOTICE_PITCH,width,NOTICE_HEIGHT,obstacles)
   if top+NOTICE_HEIGHT>y+NOTICE_SPAN:continue
   opacity=max(0,min(1,(event['until']-stamp)/FADE_SECONDS))
   placed.append((event,lane,top,len(ordered),True,opacity))
  return placed
 # Five or more overlap chronologically inside the same four-slot envelope.
 bottom=y+NOTICE_SPAN
 for ox,oy,ow,oh in obstacles:
  if x<ox+ow and ox<x+width and y<oy+oh and oy<bottom:
   if oy<=y:y=oy+oh+2
   else:bottom=min(bottom,oy-2)
 if bottom-y<50:return []
 anchor=min(y+106,bottom-46);span=max(0,anchor-y-9);placed=[]
 def ease(v):
  v=max(0,min(1,v));return v*v*(3-2*v)
 for i,event in enumerate(ordered):
  arrival=ease(max(0,stamp-event['started'])/STACK_ENTER_SECONDS)
  depth=sum(ease(max(0,stamp-n['started'])/STACK_ENTER_SECONDS) for n in ordered[i+1:])
  leaving=ease((stamp-(event['until']-FADE_SECONDS))/FADE_SECONDS)
  top=round(anchor-min(span,depth*26)+9*(1-arrival)-9*leaving)
  opacity=arrival*(1-leaving)*max(.22,1-.17*depth)
  placed.append((event,len(ordered)-1-i,top,len(ordered),i==len(ordered)-1,opacity))
 return placed

def paint_receipt(event,width=38,height=34):
 # Applied-effect receipt: native cause icon only, with the existing polarity accent.
 icon_file=icon_name(event);icon=effect_icon_image(icon_file)
 row=Image.new('RGBA',(width,height),(0,0,0,0))
 if icon is None:return row,'',None
 ink=ImageDraw.Draw(row);ink.rectangle((3,2,34,30),fill=(24,25,24,210))
 row.alpha_composite(icon,(7,4))
 accent=(155,186,139,255) if event['polarity']=='buff' else (205,139,103,255)
 ink.rectangle((3,2,4,30),fill=accent)
 return row,'',icon_file

def icon_receipts(notices):
 # One native cause icon per polarity; multiple effects of the same source do not
 # consume several lanes. Keep the latest applied receipt and its own expiry.
 unique={}
 for event in sorted(notices,key=lambda e:(e['started'],e.get('order',0))):
  icon=icon_name(event)
  if effect_icon_image(icon) is not None:unique[(icon,event['polarity'])]=event
 return sorted(unique.values(),key=lambda e:(e['started'],e.get('order',0)))

@functools.lru_cache(maxsize=256)
def receipt_texture(source,modifier,effect,polarity):
 row,label,icon=paint_receipt({'source':source,'modifier':modifier,'effect':effect,'polarity':polarity})
 # Keep the native38x34 drawing, without the previous10percent enlargement.
 row=row.resize((NOTICE_WIDTH,NOTICE_HEIGHT),Image.Resampling.LANCZOS)
 row.paste((0,0,0,0),(0,0,1,NOTICE_HEIGHT));row.paste((0,0,0,0),(NOTICE_WIDTH-1,0,NOTICE_WIDTH,NOTICE_HEIGHT));row.paste((0,0,0,0),(0,NOTICE_HEIGHT-1,NOTICE_WIDTH,NOTICE_HEIGHT))
 return row,label,icon

def render_base_guardians(im,clock,origin_y=292):
 data=None;basis=clock;scope='none'
 if REPLAY is not None and REPLAY.bound:
  data=getattr(REPLAY,'base_guardians',None);scope='replay:'+str(getattr(REPLAY,'session_key',''))
 elif LIVE is not None and LIVE.bound:
  snapshot=LIVE.final_snapshot if getattr(LIVE,'final_snapshot',None) is not None else LIVE.snapshot() if callable(getattr(LIVE,'snapshot',None)) else None
  if snapshot:data=snapshot.get('base_guardians');scope=str(LIVE.session)+'/'+str(LIVE.generation);basis=LIVE.final_clock if getattr(LIVE,'final_clock',None) is not None else clock
 rows=S.guardian_view.sample(data,basis,time.monotonic(),scope)
 columns=S.tower_grid.columns(clock,time.monotonic())
 if columns is None:return []
 draw_guardian_rows(im,rows,font_at,icon_image('objective-guardian.png',30),origin_y=origin_y,columns=columns,language=S.language)
 return rows

def confirmed_final():
 return LIVE is not None and LIVE.bound and LIVE.phase=='ended' and getattr(LIVE,'final_snapshot',None) is not None and len(S.roster)==12 and {int(p['hero']) for p in S.roster}=={p['hero'] for p in LIVE.final_snapshot['roster']}

def guardian_image(width):
 # Keep objective HP off the fast notification frame; reuse the 2 Hz status loop.
 with S.lock:
  im=Image.new('RGBA',(max(640,min(7680,int(width))),116));stamp=time.monotonic()
  valid=stamp-S.last_http<2 and stamp-S.native_at<3 and S.last_clock is not None and len(S.roster)==12 and not any(p.get('detail') is True for p in S.roster)
  S.guardian_rows=render_base_guardians(im,S.last_clock,origin_y=0) if valid else []
  out=io.BytesIO();im.save(out,format='PNG',compress_level=1);return out.getvalue()

def status_image():
 im=Image.new('RGBA',(240,40));message=''
 if time.monotonic()-S.last_http<3:
  source=LIVE if LIVE is not None and getattr(LIVE,'automatic',False) and LIVE.route else REPLAY
  if source is not None and callable(getattr(source,'status',None)):
   status=source.status()
   if status.get('state') in ('loading','error','stopped'):
    if S.language=='ja':message='通知：'+status.get('message','')
    elif status['state']=='loading':message='Preparing spectator data…' if source is LIVE else 'Analyzing replay…'
    else:message='Spectator data unavailable. Reopen the match.'
 if message:
  ink=ImageDraw.Draw(im);lines=[];line='';face=font_at(11)
  for ch in message[:100]:
   if ink.textlength(line+ch,font=face)>232:lines.append(line);line=ch
   else:line+=ch
  if line:lines.append(line)
  for i,line in enumerate(lines[:2]):ink.text((120,5+i*15),line,font=face,fill=(244,237,211,235),anchor='mt',stroke_width=1,stroke_fill=(0,0,0,230))
 out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()

def render(data,record=False):
 global REPLAY_SESSION
 with S.lock:
  now=S.context(data)
  if REPLAY is not None and getattr(REPLAY,'automatic',False):
   REPLAY.poll();key=REPLAY.session_key
   if key!=REPLAY_SESSION:S.reset();REPLAY_SESSION=key
  S.money_rows=[]
  if REPLAY is not None and REPLAY.bound:apply_replay(now)
  elif LIVE is not None:apply_live(now)
  S.bridge_rows=None
  heroes=[int(p['hero']) for p in S.roster]
  if REPLAY is not None and REPLAY.bound and callable(getattr(REPLAY,'bridge_at',None)):S.bridge_rows=REPLAY.bridge_at(now,heroes)
  elif LIVE is not None and LIVE.bound:S.bridge_rows=getattr(S,'live_bridge_rows',[])
  w=max(640,min(7680,int(data.get('width',1920))));im=Image.new('RGBA',(w,900 if any(p.get('detail') is True for p in S.roster) else 420),(0,0,0,0));draw=ImageDraw.Draw(im);events=[];obstacles=card_obstacles(S.roster,w)
  for p in S.roster:
   notices=icon_receipts(S.visible(p['hero'],now));x,y,width,side=corner_geometry(p,w)
   stamp=time.monotonic()
   for event,lane,top,stack_count,front,opacity in receipt_layout(notices,x,y,width,obstacles,stamp):
    effect=event['effect'].lstrip('+-−＋ ');height=NOTICE_HEIGHT
    row,display_effect,icon_file=receipt_texture(event['source'],event['modifier'],event['effect'],event['polarity']);row=row.copy()
    if front and stack_count>VISIBLE_LANES:
     count_ink=ImageDraw.Draw(row);count_ink.rectangle((width-12,0,width-2,10),fill=(24,25,24,245));count_ink.text((width-7,5),str(stack_count),font=font_at(8),fill=(242,236,220,255),anchor='mm')
    if opacity<1:row.putalpha(row.getchannel('A').point(lambda a:round(a*opacity)))
    im.alpha_composite(row,(x,top))
    events.append({'hero':str(p['hero']),'source':event['source'],'modifier':event['modifier'],'effect':effect,'display_effect':display_effect,'icon_file':icon_file,'polarity':event['polarity'],'observation_clock':event['clock'],'clock':data['time'],'source_scope':event.get('source_scope','world-panel'),'replay_match':event.get('replay_match'),'cause_label':event.get('cause_label',''),'corner':side+'-inner','lane':lane,'stack_count':stack_count,'front':front,'order':event.get('order',0),'rect':[x,top,width,height],'presentation':'native-effect-icon-only','opacity':round(opacity,3)})
  guardian_rows=S.guardian_rows
  bridge_records=render_bridge_icons(im,now)
  if REPLAY is not None and REPLAY.bound and callable(getattr(REPLAY,'money_at',None)):S.money_rows=REPLAY.money_at(now,heroes)
  money_rows=money_records(S.money_rows,S.roster,w,frozen=confirmed_final()) if time.monotonic()-S.native_at<3 else []
  economy_rows=render_economy(im,obstacles)
  identity_rows=render_identity_notices(im,now)
  S.frames+=1
  # Diagnostic snapshots are bounded and must never interrupt a HUD frame.
  if record and (S.record_saved is None or time.monotonic()-S.record_saved>=.5):
   S.record_saved=time.monotonic()
   try:
    if any(v['kind']=='sale' for v in identity_rows):(STATE/'last-identity-visible.json').write_text(json.dumps({'clock':data['time'],'rows':identity_rows},ensure_ascii=False,indent=2),encoding='utf-8')
    (STATE/'last-frame.json').write_text(json.dumps({'at':time.time(),'clock':data['time'],'events':events,'base_guardians':guardian_rows,'bridge_buffs':bridge_records,'money':money_rows,'economy':list(S.economy_view.audit),'economy_display':economy_rows,'identity_notices':identity_rows,'mode':'3-second animated receipt stack','diagnostic':{'entities':S.entities,'pending':[(k,[(x,v['until']-time.monotonic()) for x,v in d.items()]) for k,d in S.notifications.items() if d],'guard':S.stable_after-time.monotonic(),'native_age':time.monotonic()-S.native_at}},ensure_ascii=False,indent=2),encoding='utf-8')
    if events:
     (STATE/'last-visible.json').write_text(json.dumps({'at':time.time(),'events':events,'mode':'3-second animated receipt stack'},ensure_ascii=False,indent=2),encoding='utf-8')
     if S.frames%4==0:im.save(STATE/'last-visible.png')
    if S.history and S.history[-1]['observed_at']!=S.history_saved:
     S.history_saved=S.history[-1]['observed_at'];(STATE/'runtime-notices.json').write_text(json.dumps(list(S.history),ensure_ascii=False,indent=2),encoding='utf-8')
   except OSError:S.metrics['diagnostic_save_errors']+=1
  if record and time.monotonic()-S.status_saved>1:
   try:
    S.status_saved=time.monotonic();(STATE/'notification-audit.json').write_text(json.dumps({'at':time.time(),'clock':data['time'],'metrics':dict(S.metrics),'suppressed':list(S.suppressed),'live_decisions':list(LIVE.decisions) if LIVE is not None else []},ensure_ascii=False,indent=2),encoding='utf-8')
   except OSError:S.metrics['diagnostic_save_errors']+=1
  out=io.BytesIO();im.save(out,format='PNG',compress_level=1);return out.getvalue()
@functools.lru_cache(maxsize=1024)
def bridge_icon(kind,remaining=160):
 # Draw at4x and downsample so the one-pixel white arc has smooth edges.
 scale=4;row=Image.new('RGBA',(56,56),(0,0,0,0));ink=ImageDraw.Draw(row)
 ink.ellipse((1,1,54,54),fill=(15,16,15,200),outline=(22,23,22,245),width=4)
 with Image.open(ROOT/'icons'/BRIDGE_RULES[kind]['icon']) as source:icon=source.convert('RGBA').resize((48,48),Image.Resampling.LANCZOS)
 row.alpha_composite(icon,(4,4));ink=ImageDraw.Draw(row)
 if remaining>0:ink.arc((1,1,54,54),270-360*max(0,min(160,remaining))/160,270,fill=(248,248,245,255),width=4)
 return row.resize((20,20),Image.Resampling.LANCZOS)

def render_bridge_icons(im,clock):
 stamp=time.monotonic()
 if S.bridge_rows is None or stamp<S.stable_after or stamp-S.native_at>3:S.bridge_view.clear();return []
 players={str(p['hero']):p for p in S.roster};records=[]
 for item in S.bridge_view.update(S.bridge_rows,stamp,clock):
  player=players.get(item['hero'])
  if not player:continue
  x,y,w,h=bridge_geometry(player,item['slot'],im.width)
  if x<0 or x+w>im.width or y<0 or y+h>im.height:continue
  icon=bridge_icon(item['type'],round(item['fraction']*160)).copy()
  if item['overflow']:
   ink=ImageDraw.Draw(icon);ink.rectangle((6,9,21,21),fill=(15,16,15,245));ink.text((15,16),'+'+str(item['overflow']),font=font_at(10),fill='white',anchor='mm')
  if item['opacity']<1:icon.putalpha(icon.getchannel('A').point(lambda a:round(a*item['opacity'])))
  im.alpha_composite(icon,(x,y));records.append({**item,'label':BRIDGE_RULES[item['type']]['label'],'rect':[x,y,w,h],'meaning':'active bridge buff, independent of three-second receipts'})
 return records


@functools.lru_cache(maxsize=256)
def sale_texture(ability,language="ja"):
 item=CAT.get('sale_items',{}).get(str(ability))
 if not item:return None
 icon=None
 if item.get('icon_png'):
  try:
   with Image.open(io.BytesIO(base64.b64decode(item['icon_png'],validate=True))) as image:icon=image.convert('RGBA') if image.size==(24,24) else None
  except (OSError,ValueError):pass
 if icon is None:icon=icon_image(ICON_MAP['sources'].get(item['source']))
 im=Image.new('RGBA',(140,32),(32,34,31,255));ink=ImageDraw.Draw(im);ink.rectangle((0,0,139,31),outline=(85,87,79,255));ink.rectangle((1,1,3,30),fill=item.get('color','#a7a7a0'))
 # Center the whole group with the same8px outer margin as purchase/upgrade cards.
 x=8
 if icon is not None:im.alpha_composite(icon.resize((16,16),Image.Resampling.LANCZOS),(x,8));x+=20
 ink.text((x+10,16),'売却' if language=='ja' else 'Sold',font=font_at(9),fill=(220,168,148,255),anchor='mm');x+=24
 name=item['name'] if language=='ja' else DISPLAY_IDENTITIES['items'].get(str(ability),{}).get('en','Item');face=font_at(11);box=ink.textbbox((0,0),name,font=face);caption=Image.new('RGBA',(max(1,box[2]-box[0]),max(1,box[3]-box[1])));ImageDraw.Draw(caption).text((-box[0],-box[1]),name,font=face,fill=(240,238,230,255));room=132-x
 if caption.width>room:caption=caption.resize((room,caption.height),Image.Resampling.LANCZOS)
 im.alpha_composite(caption,(x+(room-caption.width)//2,(32-caption.height)//2));return im

@functools.lru_cache(maxsize=256)
def kda_texture(values):
 label='K '+str(values[0])+'  D '+str(values[1])+'  A '+str(values[2]);scale=4
 im=Image.new('RGBA',(120*scale,16*scale),(17,19,19,85));ink=ImageDraw.Draw(im)
 try:path,_=game_fonts()
 except (ValueError,OSError):path=str(ROOT/'fonts/NotoSansJP-Bold.ttf')
 for size in (13,12,11):
  face=ImageFont.truetype(path,size*scale)
  if ink.textlength(label,font=face)<=116*scale:break
 ink.text((60*scale,7*scale),label,font=face,fill=(244,241,232,255),anchor='mm',stroke_width=2,stroke_fill=(0,0,0,190))
 return im.resize((120,16),Image.Resampling.LANCZOS)

def render_identity_notices(im,clock):
 stamp=time.monotonic();records=[];rows={str(v['hero']):v for v in S.money_rows};ready=stamp>=S.stable_after and (stamp-S.native_at<3 or confirmed_final())
 if not rows:S.sale_ready=False;S.sale_active.clear()
 baseline=not S.sale_ready;S.sale_ready=bool(rows)
 for p in S.roster:
  hero=str(p['hero']);v=rows.get(hero,{})
  center=float(p['pos']['x'])+float(p.get('width',140))/2;scale=float(p.get('scale',1));base=float(p['pos']['y']);kda=v.get('kda')
  if isinstance(kda,list) and len(kda)==3:S.kda_hold[hero]=kda
  else:kda=S.kda_hold.get(hero)
  if ready and isinstance(kda,list) and len(kda)==3:
   label='K '+str(kda[0])+'  D '+str(kda[1])+'  A '+str(kda[2]);im.alpha_composite(kda_texture(tuple(kda)),(round(center-60),round(base-30)));records.append({'hero':hero,'kind':'kda','text':label,'rect':[round(center-60),round(base-30),120,16]})
  for e in v.get('sales',[]):
   key=str(e['id'])
   if key in S.sale_seen:continue
   S.sale_seen.append(key)
   if baseline or not ready or not sale_texture(e['ability'],S.language):continue
   q=S.sale_active.setdefault(hero,[]);q.append({**e,'until':stamp+4,'started':stamp});q[:]=q[-2:]
  q=S.sale_active.get(hero,[]);q[:]=[e for e in q if e['until']>stamp]
  if not ready:continue
  top=p.get('notice_top',156)
  if type(top) not in (int,float) or not math.isfinite(top) or not 100<=top<=820:continue
  # Use free slots in the same two-row notification space, never cover native purchase cards.
  cards=p.get('cards',[]);slots=[round(base+(top+i*36)*scale) for i in range(2)];free=[y for y in slots if not any(len(c)==4 and y<c[1]+c[3] and c[1]<y+32 for c in cards)];x=round(center-70)
  for e,y in zip(q,free):
   row=sale_texture(e['ability'],S.language).copy();opacity=max(0,min(1,(e['until']-stamp)/.5));row.putalpha(row.getchannel('A').point(lambda a:round(a*opacity)))
   if x<0 or x+140>im.width or y<0 or y+32>im.height:continue
   im.alpha_composite(row,(x,y));records.append({'hero':hero,'kind':'sale','id':e['id'],'ability':e['ability'],'name':CAT['sale_items'][str(e['ability'])]['name'],'rect':[x,y,140,32],'meaning':'explicit native sell=true, no inferred refund'})
 return records


def replay_priority(event):
 if event['path']=='upgrade_glitch/modifier_glitch_debuff':return 110
 if event['path']=='upgrade_unstoppable/modifier_unstoppable':return 100
 if event['effect'] in ('スタン','睡眠','武装解除','サイレンス','移動不能'):return 100
 return 30 if event['polarity']=='buff' else 60

def replay_compounds(fresh):
 def group(e):return (e['hero'],e.get('cause'),e.get('caster_parent'),int(e['seconds']))
 primaries={}
 for e in fresh:
  if not e.get('cause') or e.get('caster_parent') is None:continue
  effect=DISPLAY_POLICY.get(e['path'],{}).get('effect',e['effect'])
  if effect in ('カース','凍結','拘束','パリースタン','変身','吸引'):primaries.setdefault(group(e),set()).add(effect)
 keep=[];suppressed=[]
 for e in fresh:
  effect=DISPLAY_POLICY.get(e['path'],{}).get('effect',e['effect']);primary=primaries.get(group(e),set())
  redundant=(bool(primary & {'変身','吸引'}) and effect in ('スタン','サイレンス','武装解除','移動不能','スロウ')) or ('カース' in primary and effect in ('サイレンス','武装解除')) or (primary & {'凍結','拘束'} and effect=='スロウ')
  interrupt=bool(primary) and e['path'] in ('modifier_citadel_stunned','modifier_citadel_stunned_no_cc_diminish','modifier_citadel_knockdown') and 0<e.get('duration',-1)<=.5
  if redundant or interrupt:suppressed.append(e)
  else:keep.append(e)
 return keep,suppressed

def apply_replay(now):
 stamp=time.monotonic();heroes=[int(p['hero']) for p in S.roster];fresh=REPLAY.advance(now,heroes,stamp)
 if set(heroes)!=REPLAY.heroes or len(heroes)!=12:
  REPLAY_WINDOWS.clear();S.notifications.clear();S.observed.clear();S.snapshots.clear();S.metrics['replay_roster_rejected']+=1;return
 if callable(getattr(REPLAY,'economy_advance',None)):S.economy_view.push(REPLAY.economy_advance(now,heroes,stamp),stamp)
 apply_events(fresh,REPLAY_WINDOWS,'replay-index','replay')

def apply_events(fresh,windows,scope,metric_prefix):
 stamp=time.monotonic()
 admitted=[e for e in fresh if e['path'] in DISPLAY_POLICY]
 S.metrics[metric_prefix+'_outside_display_policy']+=len(fresh)-len(admitted)
 fresh,compound_suppressed=replay_compounds(admitted)
 S.metrics[metric_prefix+'_compound_collapsed']+=len(compound_suppressed)
 for e in compound_suppressed:S.suppressed.append({'at':time.time(),'clock':S.last_heartbeat,'hero':str(e['hero']),'key':e['path'],'serial':e['serial'],'reason':'same_caster_primary_status_notice'})
 names={str(hero):name for name,hero in CAT['heroes'].items()}
 for hero,entries in list(windows.items()):
  for key in list(entries):
   if entries[key][0]<=stamp:del entries[key]
 for event in fresh:
  rule=DISPLAY_POLICY.get(event['path'])
  if rule is None:S.metrics[metric_prefix+'_outside_display_policy']+=1;continue
  event={**event,'effect':rule['effect'],'polarity':rule['polarity']}
  hero=str(event['hero']);path=event['path'];source,_,modifier=path.partition('/')
  if not modifier:
   modifier='disarm_proc' if path=='modifier_citadel_disarmed' else 'stunned'
   source=event.get('cause') if event.get('cause') in ICON_MAP['sources'] else 'native_status'
  else:modifier=modifier.rsplit('/',1)[-1]
  key=source+'/'+modifier;entries=windows.setdefault(hero,{})
  if key in entries:S.metrics[metric_prefix+'_rapid_reapply_coalesced']+=1;continue
  row={'source':source,'modifier':modifier,'effect':event['effect'],'polarity':event['polarity'],'source_scope':scope,'replay_match':getattr(REPLAY,'match',None) if scope=='replay-index' else None,'cause_label':event.get('cause') or '', 'serial':event['serial'],'application_sequence':event.get('sequence'),'priority':replay_priority(event),'basis':'exact parent handle and native subclass hash; matched native clock at second precision'}
  entries[key]=(stamp+NOTICE_SECONDS,row)
  # Explicit applications can recur with a new serial after the previous notice.
  if hero in S.observed:S.observed[hero].discard(key)
 for p in S.roster:
  hero=str(p['hero']);S.entities[hero]=names[hero];S.current=hero;S.rows=[r for until,r in windows.get(hero,{}).values()];S.finish()

def apply_live(now):
 stamp=time.monotonic();was_bound=LIVE.bound;old_generation=(LIVE.session,LIVE.generation)
 try:
  if callable(getattr(LIVE,'snapshot',None)):snapshot=LIVE.snapshot()
  else:
   if LIVE_PATH is None or LIVE_PATH.stat().st_size>1024*1024:raise ValueError('live snapshot size')
   snapshot=json.loads(LIVE_PATH.read_text(encoding='utf-8'))
 except (OSError,ValueError):snapshot=None
 fresh=LIVE.advance(snapshot,now,[int(p['hero']) for p in S.roster],stamp,time.time(),postgame=S.postgame)
 if was_bound!=LIVE.bound or old_generation!=(LIVE.session,LIVE.generation):
  S.economy_view.clear()
  LIVE_WINDOWS.clear();S.notifications.clear();S.observed.clear();S.snapshots.clear();S.feeds.clear();S.entities.clear();S.camera_owner=None
  S.metrics['live_channel_switches']+=1
 S.live_bridge_rows=LIVE.bridge_at(snapshot,now,[int(p['hero']) for p in S.roster]) if LIVE.bound else []
 S.money_rows=LIVE.money_at(snapshot,now,[int(p['hero']) for p in S.roster]) if LIVE.bound and callable(getattr(LIVE,'money_at',None)) else []
 if LIVE.bound:
  S.economy_view.push(LIVE.economy_advance(snapshot,now,[int(p['hero']) for p in S.roster],time.monotonic()),time.monotonic())
  apply_events(fresh,LIVE_WINDOWS,'live-broadcast','live')



def resolve_world(items):
 result={}
 generic={'slowed':'スロウ','immobilized':'移動不能','immobilize_proc':'移動不能','stunned':'スタン','MODIFIER_STATE_STUNNED':'スタン','MODIFIER_STATE_SILENCED':'サイレンス','MODIFIER_STATE_IS_ASLEEP':'睡眠','MODIFIER_STATE_BURNING':'燃焼','bullet_armor_down':'武器耐性低下','bullet_armor_reduction':'武器耐性低下','tech_armor_reduction':'スピリット耐性低下','disarm_proc':'武装解除','silence_proc':'サイレンス','sleep_proc':'睡眠'}
 for item in items:
  if not isinstance(item,dict):continue
  classes=set(x for x in item.get('classes',[]) if isinstance(x,str))
  if 'buildup' in classes:S.metrics['buildup_skipped']+=1;continue
  matches=[WORLD_CAT[x] for x in classes if x in WORLD_CAT]
  meanings={(x['source'],x['modifier']) for x in matches}
  if len(meanings)==1:
   row=dict(matches[0])
   if row.get('runtime_debuff_required'):
    if 'isDebuff' not in classes:S.metrics['unknown_polarity_skipped']+=1;continue
    row['polarity']='debuff'
   if 'isDebuff' in classes and row['polarity']!='debuff':continue
  else:
   known=[generic[x] for x in classes if x in generic]
   if not known or len(set(known))!=1:
    if 'isDebuff' not in classes:S.metrics['unmapped_nonnegative_skipped']+=1;continue
    effect='状態異常';key='unidentified_debuff';S.metrics['generic_unknown_debuff_samples']+=1
   else:
    effect=known[0];key=sorted(x for x in classes if x in generic)[0];key={'MODIFIER_STATE_STUNNED':'stunned','MODIFIER_STATE_SILENCED':'silence_proc','MODIFIER_STATE_IS_ASLEEP':'sleep_proc'}.get(key,key)
   row={'source':'native_status','modifier':key,'name':effect,'effect':effect,'kind':'status','polarity':'debuff','basis':'native status CSS; cause intentionally unspecified'}
  candidates=[v for k,v in DISPLAY_POLICY.items() if k.startswith(row['source']+'/') and k.rsplit('/',1)[-1]==row['modifier']]
  if row['source']=='native_status':
   if row['effect'] not in ('スタン','サイレンス','睡眠','燃焼','スロウ','移動不能','武装解除'):continue
  elif len({(v['effect'],v['polarity']) for v in candidates})==1:row.update(effect=candidates[0]['effect'],polarity=candidates[0]['polarity'])
  else:continue
  result[row['source']+'/'+row['modifier']]=row
 return list(result.values())

def publish_merged(entity,baseline_rows=None):
 if entity not in S.entities:return
 stamp=time.monotonic();rows={}
 for channel,(at,values) in S.feeds.get(entity,{}).items():
  if stamp-at<2.5:
   for row in values:rows[row['source']+'/'+row['modifier']]=row
 if baseline_rows is not None and entity in S.observed:
  S.observed[entity].update(row['source']+'/'+row['modifier'] for row in baseline_rows)
 S.current=entity;S.rows=list(rows.values());S.finish()

def clear_camera():
 old=S.camera_owner
 if old is not None:
  S.feeds.get(old,{}).pop('camera',None)
  active=S.notifications.get(old,{})
  for key in list(active):
   if active[key].get('source_scope')=='observed-player':del active[key]
  publish_merged(old)
 S.camera_owner=None;S.camera_since=0;S.camera_at=0

def resolve_observed(rows):
 # Exact native central labels proven at replay27:47/27:55. Causes are retained,
 # but generic status icons do not invent an item/hero-specific source.
 labels={'スタン状態':('stunned','スタン'),'サイレンス状態':('silence_proc','サイレンス'),'Stunned':('stunned','スタン'),'Silenced':('silence_proc','サイレンス')}
 result={}
 for row in rows[:32]:
  if not isinstance(row,dict):continue
  label=row.get('label');info=labels.get(label)
  if info is None and row.get('status_key') in ('stunned','silence_proc'):info={'stunned':('stunned','スタン'),'silence_proc':('silence_proc','サイレンス')}[row['status_key']]
  if not info or row.get('polarity')!='debuff' or row.get('presentation') not in ('visible-label','active-fancy-name-mirror'):continue
  key,effect=info;result[key]={'source':'native_status','modifier':key,'name':effect,'effect':effect,'kind':'status','polarity':'debuff','source_scope':'observed-player','cause_label':str(row.get('cause_label',''))[:100],'basis':'native active central entry; selected camera owner only','priority':100}
 return list(result.values())

def accept_observed(data):
 stamp=time.monotonic()
 if stamp-S.last_http>=2 or stamp-S.native_at>=2 or len(S.roster)!=12:return
 hero=str(data.get('hero',''));matches=[p for p in S.roster if str(p.get('hero'))==hero]
 if data.get('target_count')!=1 or len(matches)!=1:
  clear_camera();S.metrics['camera_ambiguous_rejected']+=1;return
 def seconds(value):
  m=re.fullmatch(r'(\d+):(\d\d)',str(value));return int(m[1])*60+int(m[2]) if m and int(m[2])<60 else None
 event_time=seconds(data.get('time'));context_time=seconds(S.last_heartbeat)
 if event_time is None or context_time is None or abs(event_time-context_time)>1:
  S.metrics['camera_stale_rejected']+=1;return
 entity=int(hero);names=[k for k,v in CAT['heroes'].items() if str(v)==hero]
 if len(names)!=1:return
 if len([v for v in WORLD_REPORTS.values() if v['owner']==matches[0].get('name') and time.time()-v['at']<2])>1:
  clear_camera();S.metrics['camera_world_owner_conflict']+=1;return
 changed=S.camera_owner!=entity or stamp-S.camera_at>2.5
 if changed:
  clear_camera();S.camera_owner=entity;S.camera_since=stamp;S.metrics['camera_baselines']+=1
 S.camera_at=stamp
 raw=data.get('rows',[])
 if not isinstance(raw,list):return
 rows=resolve_observed(raw);S.entities[entity]=names[0];S.feeds.setdefault(entity,{})['camera']=(stamp,rows)
 guarded=changed or stamp-S.camera_since<2
 publish_merged(entity,rows if guarded else None)
 S.metrics['camera_supported_samples']+=bool(rows)

def accept_world(data):
 global WORLD_SAVED
 stamp=time.monotonic();wall=time.time()
 if stamp-S.last_http>=2 or stamp-S.native_at>=2:return
 unit=str(data.get('unit',''))[:100];owner=str(data.get('owner',''))[:100]
 roster=[p for p in S.roster if p.get('name')==owner]
 if not unit or len(roster)!=1:S.metrics['unmatched_owner_reports']+=1;return
 for k in list(WORLD_REPORTS):
  if wall-WORLD_REPORTS[k]['at']>2:del WORLD_REPORTS[k]
 old=WORLD_REPORTS.get(unit)
 items=data.get('items',[])
 if not isinstance(items,list):return
 WORLD_REPORTS[unit]={'at':wall,'owner':owner,'items':items[:32]}
 entity=int(roster[0]['hero'])
 if len([v for v in WORLD_REPORTS.values() if v['owner']==owner])!=1:
  S.metrics['ambiguous_owner_reports']+=1
  S.observed.pop(entity,None);S.notifications.pop(entity,None);S.entities.pop(entity,None);S.feeds.pop(entity,None);
  if S.camera_owner==entity:clear_camera()
  return
 names=[k for k,v in CAT['heroes'].items() if str(v)==str(entity)]
 if len(names)!=1:return
 S.entities[entity]=names[0];rows=resolve_world(items[:32]);S.feeds.setdefault(entity,{})['world']=(stamp,rows);publish_merged(entity,rows if not old else None)
 if wall-WORLD_SAVED>1:
  WORLD_SAVED=wall
  proof={'clock':S.last_heartbeat,'roster':S.roster,'units':WORLD_REPORTS,'source':'native unit status panels; no diagnostic console polling'}
  (STATE/'unit-probe.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
def accept_bag(data):
 # Native JS has uniquely matched the feed name; recheck current HUD scope/time.
 stamp=time.monotonic();hero=str(data.get('hero',''));amount=data.get('amount');clock=data.get('clock');identity=data.get('id')
 if stamp-S.last_http>2 or stamp-S.native_at>3 or S.last_clock is None:return
 if type(clock) is not int or abs(clock-S.last_clock)>1 or type(amount) is not int or not 0<amount<=10000000:return
 if data.get('cause') not in ('soul-bag-pickup','soul-bag-stolen') or data.get('source')!='native-killer-gold-label' or data.get('personal_income_verified') is not True:return
 if not isinstance(identity,str) or not re.fullmatch(r'bag-\d+',identity):return
 owners=[p for p in S.roster if str(p['hero'])==hero]
 if len(owners)!=1 or not native_receipt_owner(S.roster,hero,str(owners[0].get('money',{}).get('total',''))):return
 S.economy_view.push([{'hero':int(hero),'cause':data['cause'],'delta':amount,'id':'native-'+identity,'seconds':clock,'source_scope':'native-soul-bag'}],stamp)
 S.metrics['native_bag_receipts']+=1

def economy_geometry(player,canvas_width=1920):
 meta=player.get('money')
 if not isinstance(meta,dict):return None
 box=meta.get('rect')
 if not isinstance(box,(list,tuple)) or len(box)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in box):return None
 x,y,width,height=box
 if not 0<width<=100 or not 0<height<=40:return None
 left=round(x+width/2-39);top=round(y-22)
 return (left,top,78,20) if 0<=left and left+78<=canvas_width and 0<=top<380 else None

def render_economy(im,obstacles):
 stamp=time.monotonic();records=[]
 if stamp-S.native_at>=3 or stamp-S.last_http>=2:return records
 for p in S.roster:
  hero=str(p['hero']);row=S.economy_view.at(hero,stamp);meta=p.get('money',{});total=meta.get('total','') if isinstance(meta,dict) else ''
  if not row or not native_receipt_owner(S.roster,hero,str(total)):continue
  rect=economy_geometry(p,im.width)
  if not rect:continue
  x,y,w,h=rect
  if any(x<ox+ow and ox<x+w and y<oy+oh and oy<y+h for ox,oy,ow,oh in obstacles):continue
  try:bold,regular=game_fonts();texture=Image.open(io.BytesIO(economy_glyph_png(row['cause'],row['amount'],bold))).convert('RGBA')
  except (ValueError,OSError):continue
  opacity=max(0,min(1,(stamp-row['started'])/.1,(row['until']-stamp)/.35))
  texture.putalpha(texture.getchannel('A').point(lambda a:round(a*opacity)));im.alpha_composite(texture,(x,y))
  records.append({'hero':hero,'cause':row['cause'],'amount':row['amount'],'rect':list(rect),'opacity':opacity,'id':row['id'],'pending':len(S.economy_view.pending.get(hero,[])),'presentation':'independent-receipt-lane'})
 return records

def money_image(query):
 with S.lock:
  clock=query.get('clock',[''])[0];hero=query.get('hero',[''])[0];total=query.get('total',[''])[0]
  if not re.fullmatch(r'\d{1,3}:\d\d',clock) or S.last_clock is None or clock!=str(S.last_clock//60)+':'+str(S.last_clock%60).zfill(2) or time.monotonic()-S.last_http>2 or time.monotonic()-S.native_at>3:raise ValueError('stale money request')
  rows=money_records(S.money_rows,S.roster,7680,frozen=confirmed_final())
  candidates=[row for row in rows if row['hero']==hero and row['native_total']==total]
  if len(candidates)!=1:raise ValueError('money not available')
  row=candidates[0];bold,regular=game_fonts()
  return glyph_png(row['total'],row['wallet'],bold,regular,query.get('tone',['light'])[0],native_total=None if confirmed_final() else row['native_total'])

class ThreadingHTTPServer(_ThreadingHTTPServer):
 # Native image requests arrive in bursts across twelve player panels.
 request_queue_size=64

class H(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def setup(self):
  super().setup()
  with S.lock:S.metrics['transport_connections']+=1
 def do_GET(self):
  try:
   if len(self.path)>16000:raise ValueError('length')
   p=urlparse(self.path);q=parse_qs(p.query)
   if q.get('token')!=[TOKEN] or p.path not in ('/frame.png','/money.png','/status.png','/guardian.png','/ink.png','/drawing-state'):self.send_error(404);return
   if p.path=='/drawing-state':
    with S.lock:body=json.dumps(S.drawing.status(S.session_signal)).encode('utf-8')
    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
   with S.lock:S.metrics['transport_'+p.path[1:-4]+'_requests']+=1
   if p.path=='/ink.png':
    context=json.loads(q.get('context',['{}'])[0])
    with S.lock:S.drawing.update_context(context,S.session_signal);b=S.drawing.png()
   elif p.path=='/status.png':b=status_image()
   elif p.path=='/guardian.png':b=guardian_image(q.get('width',['1920'])[0])
   elif p.path=='/money.png':b=money_image(q)
   else:
    data=json.loads(q.get('state',['{}'])[0])
    b=render(data,record=True)
   self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Cache-Control','no-store, max-age=0');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
   with S.lock:S.metrics['transport_'+p.path[1:-4]+'_ok']+=1;S.metrics['transport_bytes']+=len(b)
  except (ValueError,KeyError,TypeError):
   with S.lock:S.metrics['transport_rejected']+=1
   self.send_error(400)
  except (ConnectionError,OSError):pass
 def do_POST(self):
  try:
   self.connection.settimeout(2)
   p=urlparse(self.path);q=parse_qs(p.query);length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=256*1024 or self.headers.get('Transfer-Encoding'):raise ValueError('drawing body limit')
   raw=self.rfile.read(length)
   if len(raw)!=length:raise ValueError('drawing body truncated')
   if p.path!='/drawing-state' or q.get('token')!=[TOKEN] or self.headers.get('Origin'):self.send_error(404);return
   if self.headers.get_content_type()!='application/json':raise ValueError('drawing content type')
   body=json.loads(raw)
   if not isinstance(body,dict):raise ValueError('drawing request')
   with S.lock:S.drawing.replace(body,S.session_signal)
   self.send_response(204);self.send_header('Content-Length','0');self.end_headers()
  except (ValueError,KeyError,TypeError):self.send_error(400)
  except (ConnectionError,OSError):pass
 def log_message(self,*a):pass
def watch(log):
 started=time.time();partial=b'';lastbeat=0;resume_key=None
 try:seed,pos,partial,meta=resume_log(log,not_before=started)
 except (OSError,ValueError) as e:
  S.stop=True;(STATE/'bridge-error.txt').write_text(str(e),encoding='utf-8');return
 with S.lock:
  for line in seed:S.line(line)
 while not S.stop:
  try:
   size=log.stat().st_size
   if size<pos:pos=0;partial=b'';S.reset();resume_key=None;started=time.time()
   if size>pos:
    with log.open('rb') as f:f.seek(pos);b=f.read(min(size-pos,2*1024*1024));pos+=len(b)
    lines=(partial+b).split(b'\n');partial=lines.pop()
    with S.lock:
     for line in lines:S.line(line.decode('utf-8',errors='replace').rstrip('\r'))
   with S.lock:
    signal=S.session_signal or {};key=(signal.get('id'),signal.get('kind'))
    can_resume=signal.get('kind') in ('replay','spectator') and signal.get('at',0)>=started and not getattr(LIVE,'route',None) and not getattr(REPLAY,'target',None)
    if signal.get('kind') not in ('replay','spectator'):resume_key=None
   if can_resume and key!=resume_key:
    seed,newpos,newpartial,meta=resume_log(log,not_before=started);resume_key=key
    with S.lock:
     for line in seed:S.line(line)
     if meta.get('reason')=='restored':S.metrics['session_restores']+=1
    pos=newpos;partial=newpartial
   if time.monotonic()-lastbeat>10:
    lastbeat=time.monotonic();(STATE/'bridge-status.json').write_text(json.dumps({'at':time.time(),'frames':S.frames,'samples':S.samples,'entities':len(S.entities),'active':time.monotonic()-S.last_http<2,'log_size':size,'mode':'automatic replay and native spectator broadcast','session_mode':S.session_signal,'session_resume':meta,'live_source':{'bound':LIVE.bound,'metrics':dict(LIVE.metrics)} if LIVE is not None else None}),encoding='utf-8')
   if size>256*1024*1024:raise RuntimeError('Diagnostic log limit reached; collector must be restarted with a new session log.')
  except FileNotFoundError:pass
  except Exception as e:
   S.reset();S.stop=True;(STATE/'bridge-error.txt').write_text(str(e),encoding='utf-8');return
  time.sleep(.05)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--log',required=True);ap.add_argument('--cfg',help=argparse.SUPPRESS);ap.add_argument('--replay-index');ap.add_argument('--replay-file');ap.add_argument('--live-effects');args=ap.parse_args()
 if bool(args.replay_index)!=bool(args.replay_file):ap.error('--replay-index and --replay-file must be supplied together')
 if args.live_effects and args.replay_index:ap.error('Live and replay sources are mutually exclusive')
 if args.live_effects:LIVE=LiveEffectSource();LIVE_PATH=Path(args.live_effects)
 if args.replay_index:REPLAY=ReplayEffectSource.from_files(args.replay_index,args.replay_file)
 threading.Thread(target=watch,args=(Path(args.log),),daemon=True).start()
 print('Read-only effect image bridge: 127.0.0.1:49647',flush=True)
 try:ThreadingHTTPServer(('127.0.0.1',49647),H).serve_forever()
 finally:
  with S.lock:S.stop=True;S.last_http=0
