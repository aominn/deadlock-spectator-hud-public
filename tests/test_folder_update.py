from pathlib import Path
import sys,unittest,json,tempfile,copy
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_manager import fixture_bundle,fixture_game
from manager_core import Manager,Refused,read_json,save
from asset_install import adopt_bundle
class FolderUpdate(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.game,self.original=fixture_game(self.root);self.old=fixture_bundle(self.root/'old','0.4.8');self.m=Manager(self.root/'home',self.old,busy=lambda:[]);self.m.setup(self.game);self.cfg=self.m.config();self.new=fixture_bundle(self.root/'new','0.4.9')
 def tearDown(self):self.temp.cleanup()
 def incoming(self):return Manager(self.m.home,self.new,busy=lambda:[])
 def test_new_folder_updates_preserving_config_and_rollback(self):
  c=self.m.config();c['custom_setting']='preserved';save(self.m.config_file,c);m=self.incoming();self.assertTrue(adopt_bundle(m)['updated']);self.assertEqual(m.config()['version'],'0.4.9');self.assertEqual(m.config()['custom_setting'],'preserved');self.assertEqual(m.config()['previous_bundle'],self.cfg['bundle']);self.assertEqual((self.game/'gameinfo.gi').read_bytes(),self.original)
 def test_active_update_reenables_with_previous_target(self):
  self.m.enable();m=self.incoming();adopt_bundle(m);self.assertTrue(m.config()['enabled']);self.assertEqual(m.config()['previous_bundle'],self.cfg['bundle']);m.normal();self.assertEqual((self.game/'gameinfo.gi').read_bytes(),self.original)
 def test_same_version_is_noop(self):
  m=Manager(self.m.home,self.old,busy=lambda:[]);self.assertFalse(adopt_bundle(m)['updated']);self.assertEqual(m.config(),self.cfg)
 def test_older_folder_never_downgrades(self):
  old=fixture_bundle(self.root/'older','0.4.7');m=Manager(self.m.home,old,busy=lambda:[]);self.assertFalse(adopt_bundle(m)['updated']);self.assertEqual(m.config(),self.cfg)
 def test_game_running_does_not_change_anything(self):
  m=self.incoming();m.busy=lambda:['deadlock.exe']
  with self.assertRaises(Refused):adopt_bundle(m)
  self.assertEqual(m.config(),self.cfg);self.assertEqual((self.game/'gameinfo.gi').read_bytes(),self.original)
 def test_invalid_folder_keeps_existing_version(self):
  (self.new/'mod/pak01_dir.vpk').write_bytes(b'changed')
  with self.assertRaises(Refused):adopt_bundle(self.incoming())
  self.assertEqual(self.m.config(),self.cfg)
 def test_setup_failure_restores_old_active_version(self):
  self.m.enable();before=self.m.config();original_setup=Manager.setup
  def setup(manager,game):
   if manager.bundle==self.new:raise Refused('simulated')
   return original_setup(manager,game)
  with patch.object(Manager,'setup',setup),self.assertRaises(Refused):adopt_bundle(self.incoming())
  self.assertEqual(self.m.config(),before);self.m.normal()
 def test_first_launch_does_not_skip_setup(self):
  m=Manager(self.root/'fresh-home',self.new,busy=lambda:[]);self.assertFalse(adopt_bundle(m)['updated']);self.assertFalse(m.config().get('bundle'))
if __name__=='__main__':unittest.main()
