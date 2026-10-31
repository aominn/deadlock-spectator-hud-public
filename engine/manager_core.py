"""Portable HUD lifecycle. No game memory access, broad process termination, or credentials."""
from pathlib import Path,PureWindowsPath
import base64,ctypes,hashlib,json,os,re,shutil,stat,subprocess,sys,time,uuid,zipfile
APP_ID='DeadlockSpectatorHUD';PORT=49647
BEGIN='// DeadlockSpectatorHUD BEGIN';END='// DeadlockSpectatorHUD END'
class Refused(ValueError):pass

def sha(b):return hashlib.sha256(b).hexdigest()
def read_json(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def atomic(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending-'+uuid.uuid4().hex);created=False
 try:
  with tmp.open('xb') as stream:created=True;stream.write(b)
  os.replace(tmp,p)
 finally:
  if created and tmp.exists():
   try:tmp.unlink()
   except OSError:pass
def save(p,v):atomic(p,json.dumps(v,ensure_ascii=False,indent=2).encode('utf-8'))
def safe(p):
 p=Path(p).absolute()
 if '..' in p.parts:raise Refused('親フォルダーを遡るパスは使えません。')
 for q in [p,*p.parents]:
  try:st=q.lstat()
  except FileNotFoundError:continue
  if stat.S_ISLNK(st.st_mode) or getattr(st,'st_file_attributes',0)&1024 or (stat.S_ISREG(st.st_mode) and st.st_nlink>1):raise Refused('リンク先への変更は停止しました。実フォルダーを選んでください。')
 return p

def member(n):
 if not isinstance(n,str) or not n or '\\' in n or ':' in n or PureWindowsPath(n).is_absolute():raise Refused('配布ファイル名が不正です。')
 for x in n.split('/'):
  if x in ('','.','..') or x.endswith((' ','.')) or (os.path.isreserved(x) if hasattr(os.path,'isreserved') else PureWindowsPath(x).is_reserved()) or any(ord(c)<32 or c in '<>"|?*' for c in x):raise Refused('配布ファイルのパスが不正です。')
 return n

def pid_active(pid):
 if not isinstance(pid,int) or not 0<pid<2**32:return False
 from ctypes import wintypes as wt
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.restype=wt.HANDLE;k.OpenProcess.argtypes=[wt.DWORD,wt.BOOL,wt.DWORD];k.GetExitCodeProcess.argtypes=[wt.HANDLE,ctypes.POINTER(wt.DWORD)];k.CloseHandle.argtypes=[wt.HANDLE]
 h=k.OpenProcess(0x1000,False,pid)
 if not h:
  if ctypes.get_last_error() in (87,1168):return False
  raise Refused('補助プロセスの終了を確認できません。')
 try:
  code=wt.DWORD()
  if not k.GetExitCodeProcess(h,ctypes.byref(code)):raise Refused('補助プロセスの状態を確認できません。')
  return code.value==259
 finally:k.CloseHandle(h)

def process_names():
 if os.name!='nt':raise Refused('Windows 10/11 x64用です。')
 from ctypes import wintypes as wt
 class PE(ctypes.Structure):
  _fields_=[('dwSize',wt.DWORD),('cntUsage',wt.DWORD),('th32ProcessID',wt.DWORD),('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wt.DWORD),('cntThreads',wt.DWORD),('th32ParentProcessID',wt.DWORD),('pcPriClassBase',wt.LONG),('dwFlags',wt.DWORD),('szExeFile',wt.WCHAR*260)]
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateToolhelp32Snapshot.restype=wt.HANDLE;k.Process32FirstW.argtypes=[wt.HANDLE,ctypes.POINTER(PE)];k.Process32NextW.argtypes=[wt.HANDLE,ctypes.POINTER(PE)];k.CloseHandle.argtypes=[wt.HANDLE]
 h=k.CreateToolhelp32Snapshot(2,0)
 if h in (None,ctypes.c_void_p(-1).value):raise Refused('実行中のゲームを確認できません。')
 try:
  e=PE();e.dwSize=ctypes.sizeof(e);ok=k.Process32FirstW(h,ctypes.byref(e));out=[]
  if not ok:raise Refused('プロセス一覧を確認できません。')
  while ok:out.append(e.szExeFile.lower());ok=k.Process32NextW(h,ctypes.byref(e))
  return out
 finally:k.CloseHandle(h)

def game_root(value):
 p=safe(value)
 for q in [p,p/'game/citadel',p/'citadel']:
  if (q/'gameinfo.gi').is_file() and (q.parent/'bin/win64/deadlock.exe').is_file():return q
 raise Refused('Deadlockのインストールフォルダーを選んでください。')

class Token:
 def __init__(self,v,a,b):self.v=v;self.a=a;self.b=b

def tokens(s):
 out=[];i=0
 while i<len(s):
  if s[i].isspace() or s[i]=='\ufeff':i+=1;continue
  if s.startswith('//',i):q=s.find('\n',i);i=len(s) if q<0 else q+1;continue
  start=i;c=s[i]
  if c in '{}':out.append(Token(c,i,i+1));i+=1;continue
  if c=='"':
   i+=1;v=''
   while i<len(s) and s[i]!='"':
    if s[i]=='\\' and i+1<len(s) and s[i+1] in ('\\','"'):v+=s[i+1];i+=2
    else:v+=s[i];i+=1
   if i>=len(s):raise Refused('設定ファイルの引用符が閉じていません。')
   i+=1;out.append(Token(v,start,i));continue
  while i<len(s) and not s[i].isspace() and s[i] not in '{}':i+=1
  out.append(Token(s[start:i],start,i))
 return out

def parse_vdf(s):
 ts=tokens(s);pos=0
 def block(nested=False):
  nonlocal pos
  out=[]
  while pos<len(ts):
   if ts[pos].v=='}':
    if not nested:raise Refused('設定形式が不正です。')
    close=ts[pos].a;pos+=1;return out,close
   key=ts[pos];pos+=1
   if key.v=='{' or pos>=len(ts):raise Refused('設定形式が不正です。')
   val=ts[pos];pos+=1
   if val.v=='{':kids,close=block(True);out.append({'key':key,'children':kids,'close':close})
   elif val.v=='}':raise Refused('設定形式が不正です。')
   else:out.append({'key':key,'value':val})
  if nested:raise Refused('設定の括弧が閉じていません。')
  return out,len(s)
 return block()[0]

def unique(nodes,key):
 rows=[n for n in nodes if n['key'].v.casefold()==key.casefold()]
 if len(rows)>1:raise Refused('同じ設定項目が複数あるため停止しました。')
 return rows[0] if rows else None

def vdf_get(s,path):
 nodes=parse_vdf(s);n=None
 for key in path:
  n=unique(nodes,key)
  if n is None:return None
  nodes=n.get('children',[])
 return n.get('value').v if n and 'value' in n else None

def mount_patch(raw):
 s=raw.decode('utf-8-sig');bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
 if BEGIN in s or END in s:raise Refused('既存のHUD設定を先に復旧してください。')
 root=unique(parse_vdf(s),'GameInfo');fs=unique(root.get('children',[]),'FileSystem') if root else None;paths=unique(fs.get('children',[]),'SearchPaths') if fs else None
 if paths is None:raise Refused('SearchPathsを確認できません。')
 games=[n for n in paths['children'] if n['key'].v.lower()=='game' and n.get('value') and n['value'].v.lower()=='citadel']
 if len(games)!=1:raise Refused('標準のcitadel検索パスを一意に確認できません。')
 at=games[0]['key'].a;line=s.rfind('\n',0,at)+1;indent=s[line:at]
 if indent.strip():raise Refused('検索パスの行形式が変わっています。')
 nl='\r\n' if '\r\n' in s else '\n';body=[BEGIN]
 for key in ['Mod','Write']:
  if not any(n['key'].v.lower()==key.lower() for n in paths['children']):body.append(key+'\t\t\tcitadel')
 body+=['Game\t\t\tcitadel/addons/deadlock_spectator_hud',END]
 added=indent+(nl+indent).join(body)+nl
 return bom+(s[:line]+added+s[line:]).encode('utf-8')

class Manager:
 def __init__(self,home,bundle,busy=None):
  self.home=safe(home);self.bundle=safe(bundle);self.home.mkdir(parents=True,exist_ok=True);self.config_file=self.home/'config.json';self.busy=busy or process_names
 def config(self):return read_json(self.config_file) if self.config_file.exists() else {'enabled':False,'autostart':False}
 def idle(self):
  if 'deadlock.exe' in self.busy():raise Refused('Deadlockを終了してから操作してください。ゲーム中のファイルは変更しません。')
 def verify(self,root=None):
  root=safe(root or self.bundle);m=read_json(root/'release.json')
  if m.get('schema')!=1 or m.get('platform')!='win-x64' or m.get('manager_protocol') not in (1,2) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-z0-9.]+)?',m.get('version','')) or not isinstance(m.get('files'),dict):raise Refused('対応する配布形式ではありません。')
  if (m.get('manager_protocol')==2)!=bool(m.get('asset_preparation') or m.get('prepared_assets')):raise Refused('素材準備方式に対応する新版の管理ツールで開いてください。')
  seen=set()
  for n,h in m['files'].items():
   member(n)
   if n.casefold() in seen or not re.fullmatch('[0-9a-f]{64}',h):raise Refused('配布物の一覧が不正です。')
   seen.add(n.casefold());f=safe(root/n)
   if not f.is_file() or sha(f.read_bytes())!=h:raise Refused('配布ファイルの検証に失敗しました：'+n)
  required=['HudManager.exe','engine/service.py','engine/manager_cli.py','runtime/python/pythonw.exe','runtime/python/python.exe','runtime/node/node.exe','engine/fonts/NotoSansJP-Bold.ttf']
  if m.get('asset_preparation'):
   from asset_install import require_profile
   require_profile(m)
  else:required.append('mod/pak01_dir.vpk')
  if m.get('prepared_assets'):
   p=m['prepared_assets']
   if p.get('schema')!=1 or p.get('source')!='source-release.json' or p.get('report')!='asset-report.json' or any(n not in m['files'] for n in ['source-release.json','asset-report.json']):raise Refused('生成素材の記録が不正です。')
  for n in required:
   if n not in m['files']:raise Refused('必要な配布ファイルがありません：'+n)
  return m
 def setup(self,game):
  if (self.home/'mount.json').exists():raise Refused('前のHUD変更の記録があります。先に通常モードへの復旧を行ってください。')
  self.idle();g=game_root(game);m=self.verify();c=self.config()
  if c.get('enabled'):raise Refused('先に通常モードへ戻してからセットアップしてください。')
  if m.get('asset_preparation'):
   from asset_install import prepared_bundle
   with prepared_bundle(self,self.bundle,m,g,previous=c.get('bundle')) as (prepared,report):
    result=Manager(self.home,prepared,busy=self.busy).setup(g);self.bundle=Path(result['bundle']);result['assets']=report['image_counts'];result['message']='環境と画像を用意しました。旧画像や画像なしでも他の機能は継続します。';return result
  key=m['version']+'-'+sha((self.bundle/'release.json').read_bytes())[:12];dst=self.home/'versions'/key
  if not dst.exists():
   stage=self.home/'versions'/('.stage-'+uuid.uuid4().hex);stage.mkdir(parents=True)
   for n in ['release.json',*m['files']]:
    out=stage/member(n);out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.bundle/n,out)
   self.verify(stage);os.replace(stage,dst)
  else:self.verify(dst)
  stable=self.home/'HudManager.exe';c=self.config()
  if c.get('enabled'):raise Refused('先に通常モードへ戻してからセットアップしてください。')
  if stable.exists():
   expected=c.get('bootstrap_sha256')
   if not expected and c.get('bundle'):
    expected=read_json(safe(c['bundle'])/'release.json').get('files',{}).get('HudManager.exe')
   if not expected or sha(stable.read_bytes())!=expected:raise Refused('既存の起動ツールが管理記録と一致しません。上書きしません。')
  else:shutil.copy2(dst/'HudManager.exe',stable)
  c['bootstrap_sha256']=sha(stable.read_bytes())
  c.update({'schema':1,'game':str(g),'bundle':str(dst),'version':m['version'],'log':str(self.home/'logs/game.log'),'repository':m.get('repository',''),'updated_at':time.time()});save(self.config_file,c);self.bundle=dst
  return {'installed':True,'version':m['version'],'game':str(g),'bundle':str(dst),'message':'環境を用意しました。HUDを有効にするとゲームへ適用されます。'}
 def transaction(self,ops,label):
  journal=self.home/'mount.json'
  if journal.exists():raise Refused('前の変更記録があります。通常モードへの復旧を先に行ってください。')
  for op in ops:
   f=safe(op['path']);current=f.read_bytes() if f.exists() else None
   if current!=op['before']:raise Refused('直前に設定が変更されました。上書きせず停止しました。')
  rec={'schema':1,'label':label,'at':time.time(),'done':False,'operations':[{'path':str(safe(o['path'])),'before':base64.b64encode(o['before']).decode() if o['before'] is not None else None,'after':base64.b64encode(o['after']).decode(),'after_sha256':sha(o['after'])} for o in ops]};save(journal,rec)
  for op in ops:atomic(op['path'],op['after'])
  rec['done']=True;save(journal,rec)
 def require_compatible(self,game,bundle,manifest=None):
  # Reuse the same native-resource gate at enable and launch/session boundaries.
  g=game_root(game);b=safe(bundle);manifest=self.verify(b) if manifest is None else manifest
  if manifest.get('prepared_assets'):
   from asset_install import compatible
   if not compatible(b,manifest,g):raise Refused('標準UIが更新されています。対応するHUDへ更新してください。ゲーム設定は変更していません。')
  else:
   pgi=vdf_get((g/'gameinfo.gi').read_text(encoding='utf-8-sig'),['GameInfo','PGIVersion'])
   if not pgi or pgi not in manifest.get('game_compatibility',{}).get('pgi_versions',[]):raise Refused('このゲーム更新版は未検証です。対応するHUDの更新を確認してください。ゲーム設定は変更していません。')
 def enable(self):
  self.idle();c=self.config()
  if not c.get('game'):raise Refused('先に初回セットアップを行ってください。')
  g=game_root(c['game']);b=safe(c['bundle']);manifest=self.verify(b);self.require_compatible(g,b,manifest)
  if c.get('enabled'):
   self.require_mounted();return {'enabled':True,'message':'HUDは有効です。'}
  gi=g/'gameinfo.gi';addon=g/'addons/deadlock_spectator_hud/pak01_dir.vpk'
  if addon.exists():raise Refused('同じ配置先に既存ファイルがあります。上書きせず停止しました。')
  raw=gi.read_bytes()
  self.transaction([{'path':gi,'before':raw,'after':mount_patch(raw)},{'path':addon,'before':None,'after':(b/'mod/pak01_dir.vpk').read_bytes()}],'HUD enable')
  c['enabled']=True;save(self.config_file,c);return {'enabled':True,'message':'HUDを有効にしました。次回のゲーム起動から反映されます。'}
 def check_mount(self):
  c=self.config();g=game_root(c['game']);rec=read_json(self.home/'mount.json')
  allowed={os.path.normcase(str(g/'gameinfo.gi')),os.path.normcase(str(g/'addons/deadlock_spectator_hud/pak01_dir.vpk'))}
  if rec.get('schema')!=1 or len(rec['operations'])!=2 or {os.path.normcase(str(safe(o['path']))) for o in rec['operations']}!=allowed:raise Refused('変更台帳の対象が一致しません。')
  for o in rec['operations']:
   f=safe(o['path']);before=base64.b64decode(o['before'],validate=True) if o['before'] is not None else None;after=base64.b64decode(o['after'],validate=True)
   if sha(after)!=o['after_sha256'] or (f.read_bytes() if f.exists() else None) not in [before,after]:raise Refused('ゲーム更新か他の変更を検出しました。原本で上書きせず停止しました。')
  return rec
 def require_mounted(self):
  rec=self.check_mount()
  for o in rec['operations']:
   f=safe(o['path'])
   if not f.is_file() or sha(f.read_bytes())!=o['after_sha256']:raise Refused('HUDの適用が途中か変更されています。通常モードへ復旧してから有効にしてください。')
  return rec
 def normal(self):
  self.idle();c=self.config();rec=self.check_mount() if (self.home/'mount.json').exists() else None
  # All operations are preflighted before the first restoration write.
  c['enabled']=False;save(self.config_file,c);self.stop_service()
  if rec:
   stamp=str(time.time_ns());history=self.home/'recovery'/stamp;history.mkdir(parents=True)
   for index,o in reversed(list(enumerate(rec['operations']))):
    f=safe(o['path']);before=base64.b64decode(o['before'],validate=True) if o['before'] is not None else None
    if before is None:
     if f.exists():shutil.move(str(f),str(history/(str(index)+'-'+f.name)))
    elif not f.exists() or f.read_bytes()!=before:atomic(f,before)
   shutil.move(str(self.home/'mount.json'),str(history/'mount.json'))
  return {'enabled':False,'message':'通常モードへ戻しました。HUDと解析処理を停止しました。'}
 def stop_service(self):
  save(self.home/'stop-service.json',{'at':time.time()})
  status=self.home/'service.json';deadline=time.monotonic()+20
  while status.exists() and time.monotonic()<deadline:
   row=read_json(status)
   if not pid_active(row.get('pid')):
    save(status,{'state':'stopped','message':'前回の補助プロセスは終了しています。','at':time.time()});break
   time.sleep(.1)
  else:
   if status.exists() and pid_active(read_json(status).get('pid')):
    raise Refused('補助アプリの停止を確認できません。ゲーム設定は保全しています。少し待ってから通常モードへの復帰を再実行してください。')
 def window_service_ready(self):
  f=Path(self.config().get('bundle',str(self.bundle)))/'engine/service.py'
  return f.is_file() and 'WINDOW_OWNER_PROTOCOL=1' in f.read_text(encoding='utf-8-sig')
 def start_service(self):
  owner=getattr(self,'owner_pid',None)
  if not isinstance(owner,int) or isinstance(owner,bool) or not 0<owner<2**32:raise Refused('管理ウィンドウから起動してください。')
  c=self.config()
  if not c.get('enabled'):raise Refused('HUDは通常モードです。先に有効にしてください。')
  b=safe(c['bundle']);manifest=self.verify(b);self.require_compatible(c['game'],b,manifest);self.require_mounted()
  if not self.window_service_ready():raise Refused('この版の初回セットアップを行ってから使用してください。旧版の補助アプリは起動しません。')
  flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
  subprocess.Popen([str(b/'runtime/python/pythonw.exe'),'-I',str(b/'engine/service.py'),'--home',str(self.home),'--owner-pid',str(owner)],cwd=b,creationflags=flags,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  return {'started':True,'message':'補助アプリを起動しました。観戦/リプレイを待機します。'}
 def autostart(self,enabled):
  if enabled:raise Refused('自動起動は廃止しました。管理ウィンドウを開いて使用してください。')
  import winreg
  command='"'+str(self.home/'HudManager.exe')+'" --tray';path=r'Software\Microsoft\Windows\CurrentVersion\Run'
  try:
   with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path,0,winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE) as k:
    try:old=winreg.QueryValueEx(k,APP_ID)[0]
    except FileNotFoundError:old=None
    if old==command:winreg.DeleteValue(k,APP_ID)
  except FileNotFoundError:pass
  c=self.config();c['autostart']=False;save(self.config_file,c);return {'autostart':False}
 def launch(self):
  self.idle();c=self.config()
  if not c.get('game'):raise Refused('先にセットアップしてください。')
  g=game_root(c['game']);exe=g.parent/'bin/win64/deadlock.exe';log=safe(c['log']);log.parent.mkdir(parents=True,exist_ok=True)
  if log.exists() and log.stat().st_size>16*1024*1024:shutil.move(str(log),str(log.with_name('game-'+str(time.time_ns())+'.log')))
  if c.get('enabled'):self.check_mount();self.start_service()
  proc=subprocess.Popen([str(exe),'-steam','-console','-con_logfile',str(log)],cwd=g.parent)
  return {'game_pid':proc.pid,'message':'ゲームを起動しました。'}
 def status(self):
  c=self.config();status=read_json(self.home/'service.json') if (self.home/'service.json').exists() else {'state':'stopped'}
  return {'window_owned':self.window_service_ready(),'version':c.get('version'),'enabled':c.get('enabled',False),'autostart':c.get('autostart',False),'game':c.get('game',''),'bundle':c.get('bundle',str(self.bundle)),'repository':c.get('repository',''),'service':status.get('state'),'service_message':status.get('message',''),'needs_recovery':(self.home/'mount.json').exists() and not c.get('enabled'),'message':'HUD有効' if c.get('enabled') else ('復旧待ち' if (self.home/'mount.json').exists() else '通常モード')}

def discover():
 import winreg
 steam=None
 try:
  with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as k:steam=Path(winreg.QueryValueEx(k,'SteamPath')[0])
 except OSError:pass
 out={'games':[]}
 if steam is None:return out
 libs=[steam];vdf=steam/'steamapps/libraryfolders.vdf'
 if vdf.exists():
  root=unique(parse_vdf(vdf.read_text(encoding='utf-8-sig')),'libraryfolders')
  for n in root.get('children',[]) if root else []:
   if n['key'].v.isdigit():
    row=unique(n.get('children',[]),'path')
    if row and 'value' in row:libs.append(Path(row['value'].v))
 for lib in dict.fromkeys(libs):
  acf=lib/'steamapps/appmanifest_1422450.acf'
  if acf.exists():
   name=vdf_get(acf.read_text(encoding='utf-8-sig'),['AppState','installdir'])
   if name and Path(name).name==name:
    try:out['games'].append(str(game_root(lib/'steamapps/common'/name)))
    except (OSError,Refused):pass
 return out

def apply_zip(manager,package,expected_sha):
 manager.idle();path=safe(package)
 if not re.fullmatch('[0-9a-f]{64}',expected_sha or ''):raise Refused('ReleaseのSHA256を64桁で入力してください。')
 if path.stat().st_size>512*1024**2:raise Refused('更新ZIPが大きすぎます。')
 data=path.read_bytes()
 if sha(data)!=expected_sha:raise Refused('更新ZIPのSHA256が一致しません。')
 import io
 stage=manager.home/'staging'/uuid.uuid4().hex;stage.mkdir(parents=True)
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  infos=z.infolist();names=[];seen=set();total=0
  if len(infos)>10000:raise Refused('更新ZIPのファイル数が上限を超えています。')
  for info in infos:
   name=member(info.filename);fold=name.casefold()
   if fold in seen or info.is_dir() or (info.external_attr>>16)&0o170000==0o120000:raise Refused('更新ZIPに重複名/リンク/ディレクトリーがあります。')
   if info.flag_bits&1 or info.file_size>256*1024**2:raise Refused('暗号化/過大な更新ファイルです。')
   seen.add(fold);names.append(name);total+=info.file_size
  if total>1024**3 or 'release.json' not in names:raise Refused('更新ZIPの容量/形式が不正です。')
  m=json.loads(z.read('release.json').decode('utf-8'))
  if set(names)!=set(m.get('files',{}))|{'release.json'}:raise Refused('更新ZIPに一覧外のファイルがあります。')
  for name in names:
   out=stage/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(name))
 manifest=manager.verify(stage);c=manager.config();previous=c.get('bundle')
 if not c.get('game'):raise Refused('先に初回セットアップを行ってください。')
 from asset_install import prepared_bundle,install_ready
 if manifest.get('asset_preparation'):
  with prepared_bundle(manager,stage,manifest,c['game'],previous=previous) as (prepared,report):
   save(manager.home/'update-pending.json',{'previous':previous,'package_sha256':expected_sha,'at':time.time()});result=install_ready(manager,prepared,c['game'],previous,c);result['assets']=report['image_counts']
 else:
  save(manager.home/'update-pending.json',{'previous':previous,'package_sha256':expected_sha,'at':time.time()});result=install_ready(manager,stage,c['game'],previous,c)
 history=manager.home/'recovery'/str(time.time_ns());history.mkdir(parents=True);shutil.move(str(manager.home/'update-pending.json'),str(history/'update.json'));result['message']='更新を適用しました。ツールを開き直すと新版を使います。';return result

def rollback(manager):
 c=manager.config();previous=c.get('previous_bundle')
 if not previous:raise Refused('戻せる前の版がありません。')
 manager.idle();manager.verify(previous);manager.verify(c['bundle'])
 from asset_install import install_ready
 result=install_ready(manager,previous,c['game'],c['bundle'],c)
 result['message']='前の版へ戻しました。ツールを開き直してください。';return result


def trim_generated(directory,pattern,max_count,max_bytes):
 """Bound only this tool's recognizable derived files; never recurse or remove user files."""
 directory=safe(directory)
 if not directory.exists():return 0
 rows=[safe(f) for f in directory.iterdir() if f.is_file() and re.fullmatch(pattern,f.name)]
 rows.sort(key=lambda f:f.stat().st_mtime_ns);total=sum(f.stat().st_size for f in rows);removed=0
 while rows and (len(rows)>max_count or total>max_bytes):
  f=rows.pop(0);total-=f.stat().st_size;f.unlink();removed+=1
 return removed
