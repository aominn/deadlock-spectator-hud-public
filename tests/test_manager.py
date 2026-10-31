from pathlib import Path
import hashlib,json,sys,tempfile,unittest,zipfile,io,types,subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import manager_core as c

def fixture_bundle(root,version='0.1.0',extra=None):
 root.mkdir(parents=True,exist_ok=True);files={'HudManager.exe':b'fixture manager','engine/service.py':b'fixture service\nWINDOW_OWNER_PROTOCOL=1','engine/manager_cli.py':b'fixture cli','runtime/python/pythonw.exe':b'fixture Python','runtime/python/python.exe':b'fixture Python CLI','engine/fonts/NotoSansJP-Bold.ttf':b'fixture font','runtime/node/node.exe':b'fixture Node','mod/pak01_dir.vpk':b'fixture VPK '+version.encode()};files.update(extra or {})
 for n,data in files.items():f=root/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
 (root/'release.json').write_text(json.dumps({'schema':1,'platform':'win-x64','manager_protocol':1,'game_compatibility':{'pgi_versions':['fixture-pgi']},'version':version,'repository':'aominn/deadlock-spectator-hud','files':{n:c.sha(b) for n,b in files.items()}}),encoding='utf-8');return root

def fixture_game(root):
 g=root/'SteamLibrary/steamapps/common/Deadlock/game/citadel';g.mkdir(parents=True);exe=g.parent/'bin/win64/deadlock.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture game')
 raw=b'"GameInfo"\r\n{\r\nPGIVersion fixture-pgi\r\nFileSystem\r\n{\r\nSearchPaths\r\n{\r\n\tGame\t\t citadel\r\n\tGame core\r\n}\r\n}\r\n}\r\n';(g/'gameinfo.gi').write_bytes(raw);return g,raw

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd());self.root=Path(self.tmp.name);self.g,self.original=fixture_game(self.root);self.bundle=fixture_bundle(self.root/'bundle');self.m=c.Manager(self.root/'state',self.bundle,busy=lambda:[]);self.m.setup(self.g)
 def tearDown(self):self.tmp.cleanup()
 def test_mount_restore_exact(self):
  other=self.g/'addons/other/pak01_dir.vpk';other.parent.mkdir(parents=True);other.write_bytes(b'other mod');self.m.enable();self.assertTrue((self.g/'addons/deadlock_spectator_hud/pak01_dir.vpk').exists());self.assertIn(c.BEGIN.encode(),(self.g/'gameinfo.gi').read_bytes());self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original);self.assertEqual(other.read_bytes(),b'other mod');self.assertFalse(self.m.config()['enabled'])
 @unittest.skipUnless(sys.platform=='win32','Windows case-insensitive filesystem')
 def test_case_only_game_path_change_restores_exact(self):
  self.m.enable();conf=self.m.config();conf['game']=str(self.g).swapcase();c.save(self.m.config_file,conf);self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original);self.assertFalse((self.m.home/'mount.json').exists())
 def test_existing_mod_paths_preserved(self):
  raw=self.original.replace(b'\tGame\t\t citadel',b'\tMod citadel\r\n\tWrite citadel\r\n\tGame other/path\r\n\tGame\t\t citadel');(self.g/'gameinfo.gi').write_bytes(raw);self.m.enable();text=(self.g/'gameinfo.gi').read_text();self.assertEqual(text.count('Mod citadel'),1);self.assertIn('other/path',text);self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),raw)
 def test_foreign_addon_refused(self):
  f=self.g/'addons/deadlock_spectator_hud/pak01_dir.vpk';f.parent.mkdir(parents=True);f.write_bytes(b'foreign')
  with self.assertRaises(c.Refused):self.m.enable()
  self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original)
 def test_bootstrap_change_refused(self):
  f=self.m.home/'HudManager.exe';f.write_bytes(b'unrelated executable')
  with self.assertRaises(c.Refused):self.m.setup(self.g)
  self.assertEqual(f.read_bytes(),b'unrelated executable')
 def test_unsupported_game_version_no_change(self):
  f=self.g/'gameinfo.gi';new=self.original.replace(b'fixture-pgi',b'future-game');f.write_bytes(new)
  with self.assertRaises(c.Refused):self.m.enable()
  self.assertEqual(f.read_bytes(),new);self.assertFalse((self.m.home/'mount.json').exists())
 def test_unknown_package_protocol_refused(self):
  b=Path(self.m.config()['bundle']);f=b/'release.json';m=c.read_json(f);m['manager_protocol']=99;c.save(f,m)
  with self.assertRaises(c.Refused):self.m.enable()
 def test_generated_retention_preserves_other_files(self):
  d=self.root/'logs';d.mkdir()
  for i in range(5):(d/('game-'+str(i)+'.log')).write_bytes(b'x'*10)
  (d/'notes.log').write_bytes(b'user notes');self.assertEqual(c.trim_generated(d,r'game-\d+\.log',3,1024),2);self.assertEqual((d/'notes.log').read_bytes(),b'user notes');self.assertEqual(len(list(d.glob('game-*.log'))),3)
 def test_running_game_refused(self):
  self.m.busy=lambda:['deadlock.exe']
  with self.assertRaises(c.Refused):self.m.enable()
  self.assertFalse((self.m.home/'mount.json').exists())
 def test_foreign_edit_no_partial_restore(self):
  self.m.enable();f=self.g/'gameinfo.gi';f.write_bytes(f.read_bytes()+b'// external edit\r\n');addon=self.g/'addons/deadlock_spectator_hud/pak01_dir.vpk'
  with self.assertRaises(c.Refused):self.m.normal()
  self.assertTrue(addon.exists());self.assertIn(b'external edit',f.read_bytes())
 def test_incomplete_mount_not_reported_enabled(self):
  self.m.enable();(self.g/'addons/deadlock_spectator_hud/pak01_dir.vpk').unlink()
  with self.assertRaises(c.Refused):self.m.enable()
  self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original)
 def test_enabled_repeat_keeps_original_recovery_record(self):
  self.m.enable();journal=(self.m.home/'mount.json').read_bytes();mounted=(self.g/'gameinfo.gi').read_bytes()
  self.m.enable();self.assertEqual((self.m.home/'mount.json').read_bytes(),journal);self.assertEqual((self.g/'gameinfo.gi').read_bytes(),mounted)
  self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original)
 def test_disabled_config_with_mounted_files_recovers_then_reenables(self):
  self.m.enable();conf=self.m.config();conf['enabled']=False;c.save(self.m.config_file,conf)
  self.assertTrue(self.m.status()['needs_recovery']);journal=(self.m.home/'mount.json').read_bytes();mounted=(self.g/'gameinfo.gi').read_bytes()
  with self.assertRaises(c.Refused):self.m.enable()
  self.assertEqual((self.m.home/'mount.json').read_bytes(),journal);self.assertEqual((self.g/'gameinfo.gi').read_bytes(),mounted)
  self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original);self.assertFalse(self.m.status()['needs_recovery'])
  self.m.enable();self.assertTrue(self.m.config()['enabled']);self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original)
 def test_setup_cannot_replace_pending_game(self):
  self.m.enable();before=self.m.config();other,_=fixture_game(self.root/'another')
  with self.assertRaises(c.Refused):self.m.setup(other)
  self.assertEqual(self.m.config(),before)
 def test_crashed_service_does_not_prevent_normal(self):
  self.m.enable();c.save(self.m.home/'service.json',{'pid':123,'state':'watching'})
  with patch.object(c,'pid_active',lambda p:False):self.m.normal()
  self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original)
 def test_prewrite_permission_failure_recovers_without_touching_original(self):
  original_atomic=c.atomic
  def fail(path,data):
   if Path(path)==self.g/'gameinfo.gi':raise PermissionError('fixture permission denied')
   original_atomic(path,data)
  with patch.object(c,'atomic',fail):
   with self.assertRaises(PermissionError):self.m.enable()
   self.m.normal()
  self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original);self.assertFalse((self.m.home/'mount.json').exists())
 def test_partial_enable_recovers(self):
  original_atomic=c.atomic
  def fail(path,data):
   if Path(path).name=='pak01_dir.vpk':raise OSError('simulated interrupted addon write')
   original_atomic(path,data)
  with patch.object(c,'atomic',fail):
   with self.assertRaises(OSError):self.m.enable()
  self.assertIn(c.BEGIN.encode(),(self.g/'gameinfo.gi').read_bytes());self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original)
 def test_journal_target_tamper_refused(self):
  self.m.enable();f=self.m.home/'mount.json';row=c.read_json(f);row['operations'][0]['path']=str(self.root/'outside.txt');c.save(f,row)
  with self.assertRaises(c.Refused):self.m.normal()
 def test_tampered_payload_refused(self):
  b=Path(self.m.config()['bundle']);(b/'mod/pak01_dir.vpk').write_bytes(b'changed')
  with self.assertRaises(c.Refused):self.m.enable()
 def make_zip(self,bundle,name='update.zip'):
  z=self.root/name
  with zipfile.ZipFile(z,'w') as out:
   for f in bundle.rglob('*'):
    if f.is_file():out.write(f,f.relative_to(bundle).as_posix())
  return z
 def test_update_and_rollback(self):
  self.m.enable();b=fixture_bundle(self.root/'bundle2','0.2.0');z=self.make_zip(b);r=c.apply_zip(self.m,z,c.sha(z.read_bytes()));self.assertEqual(r['version'],'0.2.0');self.assertTrue(self.m.config()['enabled']);self.assertEqual((self.g/'addons/deadlock_spectator_hud/pak01_dir.vpk').read_bytes(),b'fixture VPK 0.2.0');c.rollback(self.m);self.assertEqual(self.m.config()['version'],'0.1.0');self.m.normal();self.assertEqual((self.g/'gameinfo.gi').read_bytes(),self.original)
 def test_update_hash_refused_before_changes(self):
  self.m.enable();z=self.make_zip(self.bundle)
  with self.assertRaises(c.Refused):c.apply_zip(self.m,z,'0'*64)
  self.assertTrue(self.m.config()['enabled'])
 def test_update_traversal_refused(self):
  z=self.root/'bad.zip'
  with zipfile.ZipFile(z,'w') as f:f.writestr('../outside.txt',b'bad');f.writestr('release.json','{}')
  with self.assertRaises(c.Refused):c.apply_zip(self.m,z,c.sha(z.read_bytes()))
  self.assertFalse((self.root/'outside.txt').exists())
 def test_case_duplicate_refused(self):
  z=self.root/'duplicate.zip'
  with zipfile.ZipFile(z,'w') as f:f.writestr('a.txt',b'a');f.writestr('A.txt',b'b');f.writestr('release.json','{}')
  with self.assertRaises(c.Refused):c.apply_zip(self.m,z,c.sha(z.read_bytes()))
 def test_autostart_removed_cleanup_own_only(self):
  command='"'+str(self.m.home/'HudManager.exe')+'" --tray';values={c.APP_ID:command};reg=types.SimpleNamespace(HKEY_CURRENT_USER=1,KEY_QUERY_VALUE=1,KEY_SET_VALUE=2)
  class Key:
   def __enter__(self):return self
   def __exit__(self,*a):pass
  reg.OpenKey=lambda *a:Key()
  reg.QueryValueEx=lambda k,n:(values[n],1)
  reg.DeleteValue=lambda k,n:values.pop(n)
  with patch.dict(sys.modules,{'winreg':reg}):
   self.m.autostart(False);self.assertNotIn(c.APP_ID,values);self.assertFalse(self.m.config()['autostart'])
   values[c.APP_ID]='another app';self.m.autostart(False);self.assertEqual(values[c.APP_ID],'another app')
   with self.assertRaises(c.Refused):self.m.autostart(True)
 def test_service_requires_window_and_passes_owner(self):
  self.m.enable()
  with patch.object(c.subprocess,'Popen') as popen:
   with self.assertRaises(c.Refused):self.m.start_service()
   popen.assert_not_called()
   self.m.owner_pid=12345;self.m.start_service();self.assertEqual(popen.call_args.args[0][-2:],['--owner-pid','12345'])
 def test_old_companion_not_started_under_new_window(self):
  self.m.enable();self.m.owner_pid=12345;active=Path(self.m.config()['bundle']);f=active/'engine/service.py';f.write_bytes(b'old fixture service')
  manifest=c.read_json(active/'release.json');manifest['files']['engine/service.py']=c.sha(f.read_bytes());c.save(active/'release.json',manifest)
  self.assertFalse(self.m.status()['window_owned'])
  with patch.object(c.subprocess,'Popen') as popen:
   with self.assertRaisesRegex(c.Refused,'初回セットアップ'):self.m.start_service()
   popen.assert_not_called()
 def test_stop_waits_for_process_even_after_stopped_status(self):
  c.save(self.m.home/'service.json',{'state':'stopped','pid':123})
  with patch.object(c,'pid_active',side_effect=[True,False]),patch.object(c.time,'sleep') as sleep:self.m.stop_service();sleep.assert_called_once()
 def test_window_owner_handle_not_pid_polling(self):
  from service import WindowOwner
  class Fn:
   def __init__(self,returns):self.returns=iter(returns);self.calls=[]
   def __call__(self,*args):self.calls.append(args);return next(self.returns)
  kernel=types.SimpleNamespace(OpenProcess=Fn([99]),WaitForSingleObject=Fn([258,0]),CloseHandle=Fn([1]))
  with patch.object(c.ctypes,'WinDLL',return_value=kernel):
   owner=WindowOwner(123);self.assertTrue(owner.alive());self.assertFalse(owner.alive());owner.close();owner.close();self.assertEqual(kernel.CloseHandle.calls,[(99,)])
  for pid in [None,0,-1,True]:
   with self.assertRaises(ValueError):WindowOwner(pid)
 def test_service_owner_exit_closes_parsers_http_and_owner(self):
  import service
  from unittest.mock import MagicMock
  kernel=MagicMock();kernel.CreateMutexW.return_value=77
  owner=MagicMock();owner.alive.side_effect=[True,True,False]
  manager=MagicMock();manager.config.return_value={'enabled':True,'game':str(self.g),'log':str(self.m.home/'game.log')}
  config=dict(manager.config.return_value,bundle=str(self.bundle))
  bridge=types.ModuleType('effect_bridge');bridge.State=lambda:types.SimpleNamespace(stop=False);bridge.S=bridge.State();bridge.ThreadingHTTPServer=MagicMock();bridge.H=object();bridge.watch=MagicMock();bridge.REPLAY_WINDOWS={};bridge.LIVE_WINDOWS={}
  server=bridge.ThreadingHTTPServer.return_value
  with patch.dict(service.os.environ,{}),patch.dict(sys.modules,{'effect_bridge':bridge}),patch.object(service.ctypes,'WinDLL',return_value=kernel),patch.object(service.ctypes,'get_last_error',return_value=0),patch.object(service,'WindowOwner',return_value=owner),patch.object(service,'Manager',return_value=manager),patch.object(service,'read_json',return_value=config),patch.object(service,'process_names',return_value=['deadlock.exe']),patch.object(service.threading,'Thread'),patch.object(service.time,'sleep'),patch('auto_replay_source.AutoReplaySource') as replay,patch('auto_live_source.AutoLiveEffectSource') as live:
   service.main(self.m.home,123)
  replay.return_value.close.assert_called_once();live.return_value.close.assert_called_once();server.shutdown.assert_called_once();server.server_close.assert_called_once();owner.close.assert_called_once()
  self.assertEqual(c.read_json(self.m.home/'service.json')['state'],'stopped')

 def test_gui_close_uses_serialized_stop_not_tray(self):
  source=(Path(__file__).resolve().parents[1]/'manager/Program.cs').read_text(encoding='utf-8')
  for token in ['NotifyIcon','trayOnly','Hide();','startup.Checked']:self.assertNotIn(token,source)
  self.assertIn('if (closeRequested) await FinishClose();',source)
  self.assertIn('await Run("stop-service"); exiting = true; Close();',source)
  self.assertIn('values["owner_pid"] = Environment.ProcessId',source)

 def test_tool_launch_only_adds_transient_process_arguments(self):
  f=self.root/'Steam/userdata/123/config/localconfig.vdf';f.parent.mkdir(parents=True);original=b'User Steam launch options remain untouched';f.write_bytes(original)
  with patch.object(c.subprocess,'Popen',return_value=types.SimpleNamespace(pid=123)) as popen:self.m.launch()
  args=popen.call_args.args[0];self.assertEqual(args[1:],['-steam','-console','-con_logfile',self.m.config()['log']]);self.assertEqual(f.read_bytes(),original);self.assertFalse((self.m.home/'steam-launch.json').exists())
 def test_tool_launch_starts_companion_for_enabled_hud(self):
  self.m.enable()
  with patch.object(self.m,'start_service') as companion,patch.object(c.subprocess,'Popen',return_value=types.SimpleNamespace(pid=123)) as popen:self.m.launch()
  companion.assert_called_once();self.assertIn('-con_logfile',popen.call_args.args[0])
 def test_removed_steam_writers_not_available(self):
  self.assertFalse(hasattr(self.m,'configure_steam'));self.assertFalse(hasattr(self.m,'restore_steam'));self.assertFalse(hasattr(c,'vdf_set'))
 def test_removed_steam_cli_actions_do_not_touch_settings(self):
  f=self.root/'Steam/userdata/123/config/localconfig.vdf';f.parent.mkdir(parents=True);original=b'preserve manual settings';f.write_bytes(original);before=self.m.config();script=Path(c.__file__).with_name('manager_cli.py')
  for action in ['configure-steam','restore-steam']:
   x=subprocess.run([sys.executable,'-I',str(script),'--home',str(self.m.home),'--bundle',str(self.bundle),'--request',json.dumps({'action':action,'steam':str(self.root/'Steam'),'account':'123'})],capture_output=True,encoding='utf-8',timeout=10);self.assertNotEqual(x.returncode,0);self.assertFalse(json.loads(x.stdout)['ok'])
  self.assertEqual(f.read_bytes(),original);self.assertEqual(self.m.config(),before)
 def test_discovery_reads_library_but_not_user_accounts(self):
  steam=self.g.parents[4];acf=steam/'steamapps/appmanifest_1422450.acf';acf.write_text('"AppState" { "installdir" "Deadlock" }');sensitive=steam/'config/loginusers.vdf';sensitive.parent.mkdir();sensitive.write_bytes(b'not a valid VDF; must not read account data');reg=types.SimpleNamespace(HKEY_CURRENT_USER=1)
  class Key:
   def __enter__(self):return self
   def __exit__(self,*a):pass
  reg.OpenKey=lambda *args:Key();reg.QueryValueEx=lambda *args:(str(steam),1)
  with patch.dict(sys.modules,{'winreg':reg}):out=c.discover()
  self.assertEqual(set(out),{'games'});self.assertEqual(out['games'],[str(self.g)]);self.assertEqual(sensitive.read_bytes(),b'not a valid VDF; must not read account data')
 def test_gui_has_no_shortcut_creator_or_steam_account_panel(self):
  source=(Path(c.__file__).resolve().parents[1]/'manager/Program.cs').read_text(encoding='utf-8');self.assertNotIn('MakeShortcut',source);self.assertNotIn('WScript.Shell',source);self.assertNotIn('DesktopDirectory',source);self.assertNotIn('SteamAccountChoice',source);self.assertNotIn('configure-steam',source)

if __name__=='__main__':unittest.main(verbosity=2)
