from pathlib import Path
import json,os,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import manager_startup as s
import manager_core as c
from test_manager import fixture_bundle
class Startup(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.m=c.Manager(self.root/'home',fixture_bundle(self.root/'bundle'),busy=lambda:[]);self.calls=[]
 def tearDown(self):self.temp.cleanup()
 def run_start(self,updated=False):
  def clean(_):
   self.calls.append('cleanup');v=self.m.config();v['autostart']=False;c.save(self.m.config_file,v)
  with patch.object(s,'adopt_bundle',side_effect=lambda _:self.calls.append('adopt') or {'updated':updated}),patch.object(self.m,'stop_service',side_effect=lambda:self.calls.append('stop')),patch.object(self.m,'autostart',side_effect=clean),patch.object(self.m,'start_service',side_effect=lambda:self.calls.append('start')),patch.object(s,'discover',side_effect=lambda:self.calls.append('discover') or {'games':['found']}):return s.startup(self.m)
 def test_first_start_and_migration_run_once(self):
  self.assertEqual(self.run_start()['game'],'found');self.assertEqual(self.calls,['adopt','stop','cleanup','discover']);self.calls.clear();self.run_start();self.assertEqual(self.calls,['adopt','stop','discover'])
 def test_existing_game_skips_scan_and_starts_only_if_enabled(self):
  game=self.root/'game';game.mkdir();(game/'gameinfo.gi').write_text('fixture');c.save(self.m.config_file,{'game':str(game),'startup_cleanup':1,'enabled':True,'custom':'preserved'});self.run_start();self.assertEqual(self.calls,['adopt','stop','start']);self.assertEqual(self.m.config()['custom'],'preserved')
 def test_update_returns_before_service_work(self):
  self.assertTrue(self.run_start(True)['updated']);self.assertEqual(self.calls,['adopt'])
 def test_failed_stop_prevents_cleanup_and_restart(self):
  with patch.object(s,'adopt_bundle',return_value={'updated':False}),patch.object(self.m,'stop_service',side_effect=RuntimeError('stop failed')),patch.object(self.m,'start_service') as start,patch.object(self.m,'autostart') as clean:
   with self.assertRaises(RuntimeError):s.startup(self.m)
   start.assert_not_called();clean.assert_not_called()
 def test_verification_still_detects_changes_every_call(self):
  self.m.verify();(self.m.bundle/'engine/service.py').write_text('tampered')
  with self.assertRaises(c.Refused):self.m.verify()
 def test_hardlink_and_parent_traversal_remain_refused(self):
  import stat,types
  with patch.object(Path,'lstat',return_value=types.SimpleNamespace(st_mode=stat.S_IFREG,st_file_attributes=0,st_nlink=2)),self.assertRaises(c.Refused):c.safe(self.root/'linked')
  with self.assertRaises(c.Refused):c.safe(self.root/'..'/'other')
 def test_stat_flags_for_links_remain_refused(self):
  import stat,types
  for mode,attrs in [(stat.S_IFLNK,0),(stat.S_IFDIR,1024),(stat.S_IFREG,1024)]:
   with patch.object(Path,'lstat',return_value=types.SimpleNamespace(st_mode=mode,st_file_attributes=attrs,st_nlink=1)),self.assertRaises(c.Refused):c.safe(self.root/'x')
if __name__=='__main__':unittest.main()
