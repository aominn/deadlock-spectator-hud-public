"""Native-confirmed local replay selection; one bounded parser worker, no game input."""
from pathlib import Path
import collections,hashlib,json,os,re,subprocess,threading,time,uuid
from replay_effect_source import ReplayEffectSource
from native_session import lobby_line

PLAYING=re.compile(r"\[Demo\] playing demo from '(?:replays[/\\])?(\d{6,12})\.dem'")
def remote_connection(line):
 found=re.search(r"\[Client\].*creating client connection to '([^']+)'",line)
 if not found:return False
 target=found[1].lower()
 # Demo playback can use an internal loopback connection; keep that session.
 if target=='loopback' or target.startswith(('loopback:', 'localhost:', '127.', '[::1]:')):return False
 return bool(re.match(r"https?://|=?\[a:\d+:\d+\]|(?:\d{1,3}\.){3}\d{1,3}:\d+|\[[0-9a-f:]+\]:\d+",target))

class Cancelled(Exception):pass

def digest_file(path,cancel=None):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(2*1024*1024),b''):
   if cancel is not None and cancel.is_set():raise Cancelled()
   h.update(block)
 return h.hexdigest()

class AutoReplaySource:
 automatic=True
 def __init__(self,replays,cache,node,extractor,signature,runner=None,status_path=None):
  self.replays=Path(replays).resolve();self.cache=Path(cache).resolve();self.cache.mkdir(parents=True,exist_ok=True)
  self.node=Path(node);self.extractor=Path(extractor);self.signature=signature
  self.runner=runner or self._run_parser;self.status_path=Path(status_path) if status_path else None
  self.lock=threading.RLock();self.wake=threading.Event();self.stop=threading.Event();self.cancel=threading.Event()
  self.generation=0;self.target=None;self.confirmation='';self.active=None;self.pending=None;self.job=None;self.metrics=collections.Counter()
  self.info={'state':'waiting','match':None,'message':'リプレイ待機中'}
  self.worker=threading.Thread(target=self._work,name='local-replay-index',daemon=True);self.worker.start()
 @property
 def bound(self):
  with self.lock:return bool(self.active and self.active.bound and self.target==self.active.match)
 @property
 def match(self):
  with self.lock:return self.target
 @property
 def heroes(self):
  with self.lock:return self.active.heroes if self.active else set()
 @property
 def session_key(self):
  with self.lock:return (self.generation,self.target,self.active.digest if self.bound else None)
 def status(self):
  with self.lock:return dict(self.info)
 def _status(self,state,message,match=None):
  self.info={'state':state,'message':message,'match':match,'at':time.time(),'generation':self.generation,'metrics':dict(self.metrics)}
  if self.status_path:
   try:
    self.status_path.parent.mkdir(parents=True,exist_ok=True)
    tmp=self.status_path.with_suffix('.pending');tmp.write_text(json.dumps(self.info,ensure_ascii=False),encoding='utf-8');os.replace(tmp,self.status_path)
   except OSError:pass
 def _clear(self):
  self.generation+=1;self.cancel.set();self.cancel=threading.Event();self.target=None;self.active=None;self.pending=None;self.job=None
 def observe_log(self,line):
  with self.lock:
   if lobby_line(line) or any(x in line for x in ['[Demo] Requesting playback of ','[Client] Disconnecting from server:','CHostStateMgr::QueueNewRequest(']) or remote_connection(line):
    self._clear();self._status('waiting','リプレイ待機中')
   match=PLAYING.search(line)
   if match:
    self._clear();self.target=match[1];self.confirmation=line
    self.job=(self.generation,self.target,self.cancel);self.metrics['requested']+=1
    self._status('loading','リプレイを解析中…',self.target);self.wake.set()
   elif self.active:self.active.observe_log(line)
   return self.bound
 def reset_cursor(self):
  with self.lock:
   if self.active:self.active.reset_cursor()
 def poll(self):
  with self.lock:
   if self.pending:
    generation,source=self.pending;self.pending=None
    if generation==self.generation and self.target==source.match:
     source.observe_log(self.confirmation)
     if source.bound:self.active=source;self._status('ready','通知の準備完了',source.match)
   return self.bound
 def advance(self,clock,heroes,stamp):
  with self.lock:return self.active.advance(clock,heroes,stamp) if self.bound else []
 def economy_advance(self,clock,heroes,stamp):
  with self.lock:return self.active.economy_advance(clock,heroes,stamp) if self.bound else []
 def money_at(self,clock,heroes):
  with self.lock:return self.active.money_at(clock,heroes) if self.bound else []
 @property
 def base_guardians(self):
  with self.lock:return self.active.base_guardians if self.bound else None
 def bridge_at(self,clock,heroes):
  with self.lock:return self.active.bridge_at(clock,heroes) if self.bound else []
 def _work(self):
  while not self.stop.is_set():
   self.wake.wait(.2);self.wake.clear()
   with self.lock:job=self.job;self.job=None
   if job is None:continue
   generation,match,cancel=job
   try:source=self._load(match,generation,cancel)
   except Cancelled:
    with self.lock:self.metrics['cancelled']+=1
    continue
   except Exception as error:
    with self.lock:
     if generation==self.generation:
      self.metrics['errors']+=1;self._status('error','通知の解析に失敗しました。起動ログを確認してください。',match)
      self.info['error_type']=type(error).__name__
      if self.status_path:
       try:self.status_path.with_name('replay-error.txt').write_text(type(error).__name__+': '+str(error)[:2000],encoding='utf-8')
       except OSError:pass
    continue
   with self.lock:
    if generation==self.generation and not cancel.is_set():self.pending=(generation,source)
 def _load(self,match,generation,cancel):
  path=(self.replays/(match+'.dem')).resolve()
  if path.parent!=self.replays or path.is_symlink():raise ValueError('replay path')
  before=path.stat()
  if not 0<before.st_size<=2*1024**3:raise ValueError('replay size')
  sha=digest_file(path,cancel)
  target=self.cache/(match+'-'+sha[:16]+'-'+self.signature[:16]+'.json')
  if target.exists():
   try:
    if target.stat().st_size>16*1024**2:raise ValueError('index size')
    source=ReplayEffectSource.from_files(target,path)
    if source.match!=match:raise ValueError('cache match')
    with self.lock:self.metrics['cache_hits']+=1
    return source
   except (ValueError,OSError,KeyError,TypeError):
    # Invalid cache is recoverably renamed, never trusted or overwritten blindly.
    target.rename(target.with_name(target.stem+'-invalid-'+uuid.uuid4().hex+'.json'))
  output=self.cache/('.parse-'+str(generation)+'-'+uuid.uuid4().hex+'.json')
  try:
   self.runner(match,path,output,cancel)
   if cancel.is_set():raise Cancelled()
   after=path.stat()
   if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('replay changed')
   if output.stat().st_size>16*1024**2:raise ValueError('index size')
   source=ReplayEffectSource.from_files(output,path)
   if source.match!=match or source.digest!=sha:raise ValueError('parser source mismatch')
   os.replace(output,target)
   with self.lock:self.metrics['parsed']+=1
   return source
  finally:
   if output.exists():output.unlink() # own unique scratch, validated parent=self.cache
 def _run_parser(self,match,path,output,cancel):
  flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
  proc=subprocess.Popen([str(self.node),str(self.extractor),match,str(path),str(output)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
  start=time.monotonic()
  try:
   while True:
    if cancel.is_set() or self.stop.is_set():raise Cancelled()
    if time.monotonic()-start>75:raise TimeoutError('parser deadline')
    try:out,err=proc.communicate(timeout=.2);break
    except subprocess.TimeoutExpired:pass
   if proc.returncode:raise RuntimeError('parser failed: '+err.decode('utf-8',errors='replace')[-1500:])
  finally:
   if proc.poll() is None:
    proc.terminate()
    try:proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:proc.kill();proc.communicate(timeout=2)
 def close(self):
  self.stop.set()
  with self.lock:self.cancel.set()
  self.wake.set();self.worker.join(timeout=4)
