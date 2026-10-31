from pathlib import Path
import sys,json,tempfile,unittest,types
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import manager_core as core,asset_install,service
from test_manager import fixture_bundle,fixture_game
class UpdateGateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd());self.root=Path(self.tmp.name);self.game,self.original=fixture_game(self.root);self.bundle=fixture_bundle(self.root/'bundle');self.m=core.Manager(self.root/'state',self.bundle,busy=lambda:[]);self.m.setup(self.game)
 def tearDown(self):self.tmp.cleanup()
 def test_unknown_native_update_refuses_initial_enable_without_writes(self):
  before=self.m.config()
  with patch.object(self.m,'verify',return_value={'prepared_assets':{'schema':1}}),patch.object(asset_install,'compatible',return_value=False),self.assertRaisesRegex(core.Refused,'標準UI'):
   self.m.enable()
  self.assertEqual(self.m.config(),before);self.assertEqual((self.game/'gameinfo.gi').read_bytes(),self.original);self.assertFalse((self.m.home/'mount.json').exists())
 def test_enabled_native_update_refuses_reenable_companion_and_launch(self):
  self.m.enable();self.m.owner_pid=123;before=self.m.config();gi=(self.game/'gameinfo.gi').read_bytes();addon=(self.game/'addons/deadlock_spectator_hud/pak01_dir.vpk').read_bytes()
  for action in [self.m.enable,self.m.start_service,self.m.launch]:
   with self.subTest(action=action.__name__),patch.object(self.m,'verify',return_value={'prepared_assets':{'schema':1}}),patch.object(asset_install,'compatible',return_value=False) as check,patch.object(core.subprocess,'Popen') as spawn:
    with self.assertRaisesRegex(core.Refused,'標準UI'):action()
    check.assert_called_once();spawn.assert_not_called()
   self.assertEqual(self.m.config(),before);self.assertEqual((self.game/'gameinfo.gi').read_bytes(),gi);self.assertEqual((self.game/'addons/deadlock_spectator_hud/pak01_dir.vpk').read_bytes(),addon)
  self.m.normal();self.assertEqual((self.game/'gameinfo.gi').read_bytes(),self.original)
 def test_normal_game_launch_remains_available_after_game_update(self):
  f=self.game/'gameinfo.gi';f.write_bytes(self.original.replace(b'fixture-pgi',b'new-game'))
  with patch.object(self.m,'require_compatible') as gate,patch.object(core.subprocess,'Popen',return_value=types.SimpleNamespace(pid=42)) as spawn:
   self.m.launch();gate.assert_not_called();spawn.assert_called_once()
 def test_waiting_companion_checks_new_game_before_starting_parsers(self):
  kernel=MagicMock();kernel.CreateMutexW.return_value=77;owner=MagicMock();owner.alive.return_value=True;manager=MagicMock();manager.config.return_value={'enabled':True,'game':str(self.game),'log':str(self.root/'game.log')};manager.require_compatible.side_effect=core.Refused('標準UIが更新されています。');config=dict(manager.config.return_value,bundle=str(self.bundle))
  bridge=types.ModuleType('effect_bridge');bridge.State=lambda:types.SimpleNamespace(stop=False);bridge.S=bridge.State();bridge.ThreadingHTTPServer=MagicMock();bridge.H=object();bridge.watch=MagicMock();bridge.REPLAY_WINDOWS={};bridge.LIVE_WINDOWS={};server=bridge.ThreadingHTTPServer.return_value
  with patch.dict(sys.modules,{'effect_bridge':bridge}),patch.object(service.ctypes,'WinDLL',return_value=kernel),patch.object(service.ctypes,'get_last_error',return_value=0),patch.object(service,'WindowOwner',return_value=owner),patch.object(service,'Manager',return_value=manager),patch.object(service,'read_json',return_value=config),patch.object(service,'process_names',return_value=['deadlock.exe']),patch.object(service.threading,'Thread'),patch('auto_replay_source.AutoReplaySource') as replay,patch('auto_live_source.AutoLiveEffectSource') as live:
   service.main(self.m.home,123)
  manager.require_compatible.assert_called_once();replay.assert_not_called();live.assert_not_called();server.shutdown.assert_called_once();server.server_close.assert_called_once();self.assertEqual(core.read_json(self.m.home/'service.json')['state'],'error')
if __name__=='__main__':unittest.main()
