from pathlib import Path
import argparse,json,os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from manager_core import Manager,Refused,apply_zip,rollback,discover
from display_language import language,message
LANGUAGE="ja"

def main():
 global LANGUAGE
 ap=argparse.ArgumentParser();ap.add_argument('--home',required=True);ap.add_argument('--bundle',required=True);ap.add_argument('--request',required=True);args=ap.parse_args();home=Path(args.home);home.mkdir(parents=True,exist_ok=True)
 import msvcrt
 with (home/'manager.lock').open('a+b') as lock:
  lock.seek(0)
  if lock.read(1)==b'':lock.write(b'0');lock.flush()
  lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:raise Refused('別の設定操作が実行中です。少し待ってください。')
  try:
   q=json.loads(args.request);LANGUAGE=language(q.get('language','ja'));action=q.get('action');m=Manager(home,args.bundle);m.owner_pid=q.get('owner_pid')
   if action=='status':v=m.status()
   elif action=='discover':v=discover()
   elif action=='startup':
    from manager_startup import startup
    v=startup(m)
   elif action=='adopt':
    from asset_install import adopt_bundle
    v=adopt_bundle(m)
   elif action=='setup':v=m.setup(q['game'])
   elif action=='refresh-assets':
    from asset_install import refresh_assets
    v=refresh_assets(m)
   elif action=='enable':v=m.enable();m.start_service()
   elif action=='normal':v=m.normal()
   elif action=='start-service':v=m.start_service()
   elif action=='stop-service':m.stop_service();v={'message':'補助アプリの停止を要求しました。'}
   elif action=='autostart':v=m.autostart(q.get('enabled') is True)
   elif action=='launch':v=m.launch()
   elif action=='update':v=apply_zip(m,q['package'],q['sha256'])
   elif action=='rollback':v=rollback(m)
   elif action=='verify':
    root=Path(m.config().get('bundle',str(m.bundle)));v=m.verify(root)
    from asset_install import asset_summary
    v={'version':v['version'],'files':len(v['files']),'assets':asset_summary(root,v),'message':'同梱ファイルの整合性は正常です。'}
   else:raise Refused('対応していない操作です。')
   if isinstance(v,dict) and isinstance(v.get('message'),str):v['message']=message(v['message'],LANGUAGE)
   print(json.dumps({'ok':True,'result':v},ensure_ascii=False))
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
 try:main()
 except Exception as e:print(json.dumps({'ok':False,'error':message(str(e),LANGUAGE),'type':type(e).__name__},ensure_ascii=False));sys.exit(1)
