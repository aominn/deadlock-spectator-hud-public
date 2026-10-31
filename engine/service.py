"""Single-user companion; starts parsers only while the selected game is running."""
from pathlib import Path
import argparse,ctypes,os,sys,threading,time
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from manager_core import Manager,read_json,save,sha,process_names,trim_generated

class WindowOwner:
 """Keep one process handle, so PID reuse cannot extend the window lifetime."""
 def __init__(self,pid):
  if not isinstance(pid,int) or isinstance(pid,bool) or not 0<pid<2**32:raise ValueError('管理ウィンドウが必要です。')
  from ctypes import wintypes as wt
  self.k=ctypes.WinDLL('kernel32',use_last_error=True)
  self.k.OpenProcess.restype=wt.HANDLE;self.k.OpenProcess.argtypes=[wt.DWORD,wt.BOOL,wt.DWORD]
  self.k.WaitForSingleObject.argtypes=[wt.HANDLE,wt.DWORD];self.k.WaitForSingleObject.restype=wt.DWORD
  self.k.CloseHandle.argtypes=[wt.HANDLE]
  self.handle=self.k.OpenProcess(0x100000,False,pid)
  if not self.handle:raise RuntimeError('管理ウィンドウを確認できません。')
 def alive(self):return bool(self.handle) and self.k.WaitForSingleObject(self.handle,0)==258
 def close(self):
  if self.handle:self.k.CloseHandle(self.handle);self.handle=None

def write_status(home,row):
 # A busy diagnostic file must not stop parsers or the loopback renderer.
 try:save(Path(home)/'service.json',row);return True
 except PermissionError:return False

WINDOW_OWNER_PROTOCOL=1

def main(home,owner_pid):
 home=Path(home).resolve();started=time.time();runtime=home/'runtime';runtime.mkdir(parents=True,exist_ok=True)
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateMutexW.restype=ctypes.c_void_p;k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 mutex=k.CreateMutexW(None,False,'Local\\DeadlockSpectatorHUD-'+sha(str(home).encode())[:16])
 if not mutex:raise RuntimeError('補助アプリの排他を取得できません。')
 if ctypes.get_last_error()==183:k.CloseHandle(mutex);return
 bridge=None;server=None;thread=None;watcher=None;live=None;replay=None;had_game=False;owner=None
 def status(state,message):write_status(home,{'pid':os.getpid(),'state':state,'message':message,'started_at':started,'at':time.time()})
 def finish_session():
  nonlocal watcher,live,replay,had_game
  if bridge is not None:bridge.S.stop=True
  if live:live.close();live=None
  if replay:replay.close();replay=None
  if watcher:watcher.join(timeout=2);watcher=None
  if bridge is not None:bridge.LIVE=None;bridge.REPLAY=None;bridge.S=bridge.State()
  had_game=False
 try:
  owner=WindowOwner(owner_pid)
  if not owner.alive():return
  config=read_json(home/'config.json');bundle=Path(config['bundle']);m=Manager(home,bundle);manifest=m.verify();os.environ['SPEC_HUD_STATE']=str(runtime);os.environ['SPEC_HUD_GAME']=config['game']
  import effect_bridge as bridge_module
  bridge=bridge_module
  from auto_replay_source import AutoReplaySource
  from auto_live_source import AutoLiveEffectSource
  server=bridge.ThreadingHTTPServer(('127.0.0.1',49647),bridge.H);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();status('waiting','ゲームの起動を待機中')
  while True:
   c=m.config();stop=read_json(home/'stop-service.json') if (home/'stop-service.json').exists() else {}
   if not owner.alive() or not c.get('enabled') or stop.get('at',0)>=started:break
   running='deadlock.exe' in process_names()
   if running and not had_game:
    m.require_compatible(c['game'],bundle,manifest)
    bridge.S=bridge.State();node=bundle/'runtime/node/node.exe';parser=bundle/'parser';signature=sha((bundle/'release.json').read_bytes())
    replay=AutoReplaySource(Path(c['game'])/'replays',home/'cache',node,parser/'extract-replay-effects.mjs',signature,status_path=runtime/'auto-replay-status.json');live=AutoLiveEffectSource(Path(c['log']),runtime,node,parser/'live-receipt-producer.mjs');bridge.REPLAY=replay;bridge.LIVE=live;bridge.REPLAY_SESSION=None;bridge.REPLAY_WINDOWS.clear();bridge.LIVE_WINDOWS.clear()
    watcher=threading.Thread(target=bridge.watch,args=(Path(c['log']),),daemon=True);watcher.start();had_game=True
   if not running and had_game:
    finish_session();log=Path(c['log'])
    if log.exists() and log.stat().st_size>16*1024*1024:log.rename(log.with_name('game-'+str(time.time_ns())+'.log'))
    trim_generated(home/'logs',r'game-\d+\.log',3,768*1024**2)
    trim_generated(home/'cache',r'(?:\d{6,12}-[0-9a-f]{16}-[0-9a-f]{16}(?:-invalid-[0-9a-f]{32})?|\.parse-\d+-[0-9a-f]{32})\.json',200,256*1024**2)
    trim_generated(runtime,r'live-[0-9a-f]{12}-\d+-[0-9a-f]{12}\.json',4,8*1024**2)
   if had_game and bridge.S.stop:raise RuntimeError('ログ取得を停止しました。診断を確認して補助アプリを起動し直してください。')
   if had_game:
    signal=getattr(bridge.S,'session_signal',None) or {};kind=signal.get('kind')
    if live and live.bound:status('watching','ライブ通知を取得中')
    elif replay and replay.bound:status('watching','リプレイ通知を表示中')
    elif replay and replay.status().get('state')=='loading':status('watching','リプレイを解析中')
    elif live and getattr(live,'route',None):status('watching','ライブ観戦の接続を準備中')
    elif kind=='lobby':status('waiting','ロビーで待機中')
    elif kind=='practice':status('waiting','練習モードで待機中')
    elif kind in ('replay','spectator'):status('waiting','観戦・リプレイの接続を確認中')
    else:status('waiting','観戦・リプレイの開始を待機中')
   else:status('waiting','ゲームの起動を待機中')
   time.sleep(1)
  finish_session();status('stopped','補助アプリを停止しました。')
 except Exception as e:
  finish_session();status('error',type(e).__name__+': '+str(e)[:500])
 finally:
  if server:server.shutdown();server.server_close()
  if owner:owner.close()
  k.CloseHandle(mutex)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--home',required=True);a.add_argument('--owner-pid',type=int,required=True);args=a.parse_args();main(args.home,args.owner_pid)
