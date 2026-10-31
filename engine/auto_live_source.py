"""Start one live parser only for the native spectator TV route; no login or game input."""
from pathlib import Path
import collections,json,os,subprocess,threading,time,uuid
from live_effect_source import LiveEffectSource

class AutoLiveEffectSource(LiveEffectSource):
 automatic=True
 def __init__(self,log,runtime,node,producer,runner=None):
  super().__init__();self.log=Path(log);self.runtime=Path(runtime);self.runtime.mkdir(parents=True,exist_ok=True)
  self.node=Path(node);self.producer=Path(producer);self.runner=runner or self._run
  self.lock=threading.RLock();self.wake=threading.Event();self.stop=threading.Event();self.cancel=threading.Event()
  self.job=None;self.epoch=0;self.instance=uuid.uuid4().hex[:12];self.output=None;self.info={'state':'waiting','message':'ライブ観戦待機中'}
  self.worker=threading.Thread(target=self._work,name='native-live-parser',daemon=True);self.worker.start()
 def _status(self,state,message):
  self.info={'state':state,'message':message,'epoch':self.epoch,'route_sha256':self.route,'at':time.time()}
  try:
   tmp=self.runtime/'auto-live-status.pending';tmp.write_text(json.dumps(self.info,ensure_ascii=False),encoding='utf-8');os.replace(tmp,self.runtime/'auto-live-status.json')
  except OSError:pass
 def status(self):
  with self.lock:
   if self.bound and self.phase=='ended':
    if self.info['state']!='ended':self._status('ended','試合終了：確認済みの金額を保持')
   elif self.bound and self.phase=='paused' and self.info['state'] not in ('error','stopped'):
    if self.info['state']!='paused':self._status('paused','ポーズ中：確認済みの金額を保持')
   elif self.bound and self.info['state'] not in ('error','stopped') and self.info['state']!='ready':self._status('ready','ライブ通知の準備完了')
   elif not self.bound and self.info['state'] in ('ready','paused'):self._status('loading','観戦配信の同期を待機中…')
   return dict(self.info)
 def observe_log(self,line):
  with self.lock:
   old=self.route;super().observe_log(line)
   reconnect=self.route is not None and 'creating client connection to ' in line
   if old!=self.route or reconnect:
    self.epoch+=1;self.cancel.set();self.cancel=threading.Event();self.job=None;self.output=None
    if self.route:
     self.output=self.runtime/('live-'+self.instance+'-'+str(self.epoch)+'-'+self.route[:12]+'.json')
     self.job=(self.epoch,self.route,self.output,self.cancel);self._status('loading','ライブ配信を準備中…');self.wake.set()
    else:self._status('waiting','ライブ観戦待機中')
 def snapshot(self):
  with self.lock:path=self.output;route=self.route
  if path is None or route is None:return None
  try:
   if path.stat().st_size>1024*1024:return None
   row=json.loads(path.read_text(encoding='utf-8'))
   if row.get('route_sha256')!=route:return None
   return row
  except (OSError,ValueError,TypeError):return None
 def _work(self):
  while not self.stop.is_set():
   self.wake.wait(.2);self.wake.clear()
   with self.lock:job=self.job;self.job=None
   if job is None:continue
   epoch,route,path,cancel=job
   try:code=self.runner(job)
   except Exception:code=-1
   with self.lock:
    if epoch==self.epoch and not cancel.is_set():
     self.metrics['producer_stops']+=1
     self._status('stopped' if code==0 else 'error','ライブ配信の取得を終了しました。' if code==0 else 'ライブ配信を取得できませんでした。観戦に入り直してください。')
 def _run(self,job):
  epoch,route,path,cancel=job;flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
  # A session ends with the game, disconnect, match switch, server stop/error,
  # or6hours. Per180s network/byte budgets remain enforced by the producer.
  proc=subprocess.Popen([str(self.node),str(self.producer),str(self.log),str(path),'21600','--follow',route],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
  self.metrics['producer_starts']+=1
  try:
   while proc.poll() is None:
    if cancel.wait(.1) or self.stop.is_set():return -2
   return proc.returncode
  finally:
   if proc.poll() is None:
    proc.terminate()
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
 def close(self):
  self.stop.set()
  with self.lock:self.cancel.set();self.job=None
  self.wake.set();self.worker.join(timeout=8)
