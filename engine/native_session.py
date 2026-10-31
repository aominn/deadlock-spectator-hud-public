"""Native HUD mode signals and bounded, current-session-only log restoration."""
from pathlib import Path
from urllib.parse import urlsplit
import json,re,time,math
PREFIX=re.compile(r'^\d\d/\d\d \d\d:\d\d:\d\d ')
MARK='[SpecSessionState]'
FIELDS=('spec','replay','hideout','practice','teamSpectator')
def mode_signal(line,wall=None,not_before=None):
 if MARK not in line:return None
 payload=line.split(MARK,1)[1]
 if len(payload)>2000:return None
 try:
  row=json.loads(payload);f=row['flags'];at=row['at']/1000
  if row.get('v')!=1 or not isinstance(row.get('id'),str) or not re.fullmatch(r'[0-9-]{1,80}',row['id']):return None
  if type(row.get('seq')) is not int or row['seq']<0 or not isinstance(f,dict) or any(type(f.get(k)) is not bool for k in FIELDS):return None
  wall=time.time() if wall is None else wall
  if not math.isfinite(at) or not -5<=wall-at<=30 or not_before is not None and at<not_before:return None
  kind='lobby' if f['hideout'] else 'replay' if f['replay'] else 'spectator' if f['spec'] or f['teamSpectator'] else 'practice' if f['practice'] else 'other'
  return {'kind':kind,'id':row['id'],'seq':row['seq'],'at':at,'flags':{k:f[k] for k in FIELDS},'source':'native-ui'}
 except (ValueError,TypeError,KeyError,OverflowError):return None

def lobby_line(line):
 line=PREFIX.sub('',line)
 return bool(re.match(r'^Loading map "dl_hideout"',line) or re.match(r'^\[HostStateManager\].*QueueNewRequest\( Loading \(dl_hideout\)',line))

def session_candidate(lines):
 candidate=None
 for line in lines:
  line=PREFIX.sub('',line)
  if lobby_line(line) or '[Client] Disconnecting from server:' in line or 'CHostStateMgr::QueueNewRequest(' in line:candidate=None
  demo=re.search(r"\[Demo\] playing demo from '(?:replays[/\\])?(\d{6,12})\.dem'",line)
  if demo:candidate=('replay',line);continue
  connection=re.search(r"\[Client\].*creating client connection to '([^']+)'",line)
  if not connection:continue
  target=connection[1]
  try:
   u=urlsplit(target)
   tv=u.scheme in ('http','https') and u.hostname and u.hostname.endswith('.steamcontent.com') and re.fullmatch(r'/tv/[^/]+',u.path) and not u.query and not u.fragment and not u.username and not u.password
  except ValueError:tv=False
  if tv:candidate=('spectator',line)
  elif target=='loopback' or target.startswith(('127.','localhost','[::1]')):
   if candidate and candidate[0]=='spectator':candidate=None
  else:candidate=None
 return candidate

def resume_log(path,wall=None,not_before=None):
 """Return only a matching start record + fresh native signal, never old notices.
 A new helper waits for a signal emitted after it started; old game logs alone
 cannot start a job. No heartbeat timeout is applied to an already active job.
 """
 path=Path(path);wall=time.time() if wall is None else wall
 for limit in (4*1024**2,16*1024**2):
  try:
   with path.open('rb') as f:
    size=f.seek(0,2);start=max(0,size-limit);f.seek(start);data=f.read(limit);end=f.tell()
  except FileNotFoundError:return [],0,b'',{'reason':'missing-log'}
  pieces=data.split(b'\n');partial=pieces.pop()
  if start and pieces:pieces.pop(0)
  lines=[x.decode('utf-8',errors='replace').rstrip('\r') for x in pieces];latest=None;native_line=None
  for line in reversed(lines):
   signal=mode_signal(line,wall,not_before)
   if signal:latest=signal;native_line=line;break
  if latest is None:return [],end,partial,{'reason':'waiting-for-current-ui'}
  meta={'reason':'native-waiting','kind':latest['kind'],'id':latest['id'],'seq':latest['seq'],'bytes_read':len(data)}
  if latest['kind'] not in ('replay','spectator'):return [native_line],end,partial,meta
  candidate=session_candidate(lines)
  if candidate and candidate[0]==latest['kind']:
   meta['reason']='restored';return [candidate[1],native_line],end,partial,meta
  if start==0 or limit==16*1024**2:meta['reason']='start-not-confirmed';return [native_line],end,partial,meta
 return [],0,b'',{'reason':'unavailable'}
