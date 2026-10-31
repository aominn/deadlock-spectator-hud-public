from pathlib import Path
import sys,unittest,tempfile,os,io,json,base64
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'));sys.path.insert(0,str(Path(__file__).resolve().parent))
from PIL import Image
import asset_prepare as a,asset_install as install,manager_core as core
from test_manager import fixture_bundle,fixture_game

def png(color='red',size=(8,8),fmt='PNG'):
 im=Image.new('RGB',size,color);out=io.BytesIO();im.save(out,format=fmt);return out.getvalue()

class ImagePolicy(unittest.TestCase):
 def setUp(self):self.current=png();self.previous=png('blue')
 def test_new_picture_wins_even_when_content_changed(self):self.assertEqual(a.choose_image(self.current,self.previous),(self.current,'current'))
 def test_old_picture_when_current_missing(self):self.assertEqual(a.choose_image(None,self.previous),(self.previous,'previous'))
 def test_none_when_both_missing(self):self.assertEqual(a.choose_image(None,None),(None,'missing'))
 def test_decoder_bad_result_uses_old(self):self.assertEqual(a.choose_image(b'bad PNG',self.previous),(self.previous,'previous'))
 def test_unreadable_old_picture_is_ignored(self):self.assertEqual(a.choose_image(None,b'bad PNG'),(None,'missing'))
 def test_wrong_image_format_uses_old(self):self.assertEqual(a.choose_image(png(fmt='JPEG'),self.previous),(self.previous,'previous'))
 def test_large_new_image_uses_old(self):self.assertEqual(a.choose_image(png(size=(2049,1)),self.previous),(self.previous,'previous'))
 def test_resize_new_image(self):
  body,state=a.choose_image(self.current,None,(24,24));self.assertEqual(state,'current');self.assertEqual(Image.open(io.BytesIO(body)).size,(24,24))
 def test_old_must_have_right_target_size(self):self.assertEqual(a.choose_image(None,self.previous,(24,24)),(None,'missing'))
 def test_old_same_target_size_is_preserved(self):
  body=png(size=(24,24));self.assertEqual(a.choose_image(None,body,(24,24)),(body,'previous'))

class Lifecycle(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('SPEC_TEST_ARTIFACT_DIR'));self.root=Path(self.tmp.name);self.game,self.original=fixture_game(self.root);self.b=fixture_bundle(self.root/'old','0.2.0');self.manager=core.Manager(self.root/'home',self.b,busy=lambda:[]);self.manager.setup(self.game);self.old=Path(self.manager.config()['bundle'])
 def tearDown(self):self.manager.normal();self.tmp.cleanup()
 def test_old_image_must_match_saved_manifest(self):
  image=self.old/'engine/icons/test.png';image.parent.mkdir();image.write_bytes(png());m=core.read_json(self.old/'release.json');m['files']['engine/icons/test.png']=core.sha(image.read_bytes());core.save(self.old/'release.json',m);old=a.PreviousImages(self.old);self.assertEqual(old.read('engine/icons/test.png'),png());image.write_bytes(png('blue'));self.assertIsNone(old.read('engine/icons/test.png'))
 def test_sale_fallback_bound_to_same_source(self):
  file=self.old/'engine/effect-catalog.json';file.write_text(json.dumps({'sale_items':{'42':{'source':'item_a','icon_png':base64.b64encode(png(size=(24,24))).decode()}}}));m=core.read_json(self.old/'release.json');m['files']['engine/effect-catalog.json']=core.sha(file.read_bytes());core.save(self.old/'release.json',m);old=a.PreviousImages(self.old);self.assertIsNotNone(old.sale('42','item_a'));self.assertIsNone(old.sale('42','different_item'))
 def test_legacy_without_catalog_still_can_reuse_icon(self):
  image=self.old/'engine/icons/test.png';image.parent.mkdir();image.write_bytes(png());m=core.read_json(self.old/'release.json');m['files']['engine/icons/test.png']=core.sha(image.read_bytes());core.save(self.old/'release.json',m);self.assertEqual(a.PreviousImages(self.old).read('engine/icons/test.png'),png())
 def test_failed_update_keeps_disabled_previous_configuration(self):
  original=self.manager.config();new=fixture_bundle(self.root/'new','0.2.1')
  with patch.object(core.Manager,'setup',side_effect=core.Refused('test setup failure')),self.assertRaises(core.Refused):install.install_ready(self.manager,new,self.game,self.old,original)
  self.assertEqual(self.manager.config(),original);self.assertEqual((self.game/'gameinfo.gi').read_bytes(),self.original)
 def test_failed_update_reenables_previous_active_hud(self):
  self.manager.enable();original=self.manager.config();before=(self.game/'addons/deadlock_spectator_hud/pak01_dir.vpk').read_bytes();new=fixture_bundle(self.root/'new','0.2.1')
  with patch.object(core.Manager,'setup',side_effect=core.Refused('test setup failure')),self.assertRaises(core.Refused):install.install_ready(self.manager,new,self.game,self.old,original)
  self.assertEqual(self.manager.config()['bundle'],str(self.old));self.assertTrue(self.manager.config()['enabled']);self.assertEqual((self.game/'addons/deadlock_spectator_hud/pak01_dir.vpk').read_bytes(),before)
 def test_enable_failure_restores_previous_mount_and_config(self):
  self.manager.enable();original=self.manager.config();new=fixture_bundle(self.root/'new','0.2.1');original_enable=core.Manager.enable
  def fail_after_mount(manager):
   result=original_enable(manager)
   if manager.config()['version']=='0.2.1':raise core.Refused('test post-mount failure')
   return result
  with patch.object(core.Manager,'enable',fail_after_mount),self.assertRaises(core.Refused):install.install_ready(self.manager,new,self.game,self.old,original)
  self.assertEqual(self.manager.config()['bundle'],str(self.old));self.assertEqual(self.manager.config()['version'],'0.2.0');self.assertTrue(self.manager.config()['enabled']);self.assertTrue((self.manager.home/'mount.json').exists())
 def test_same_result_refresh_preserves_prior_rollback_target(self):
  c=self.manager.config();c['previous_bundle']='preserved older bundle';core.save(self.manager.config_file,c);install.install_ready(self.manager,self.old,self.game,self.old,c);self.assertEqual(self.manager.config()['previous_bundle'],'preserved older bundle')
 def test_template_cannot_include_prebuilt_game_assets(self):
  required=['engine/asset_prepare.py','engine/asset_install.py',install.PROFILE['recipe'],install.PROFILE['reader'],install.PROFILE['template']+'/engine/effect-catalog.json',install.PROFILE['template']+'/tools/build_mod.py',install.PROFILE['template']+'/mod-src/panorama_writer.py'];m={'asset_preparation':install.PROFILE,'files':{n:'0'*64 for n in required}};install.require_profile(m);m['files']['engine/icons/game.png']='0'*64
  with self.assertRaises(core.Refused):install.require_profile(m)
 def test_unknown_asset_profile_refused(self):
  with self.assertRaises(core.Refused):install.require_profile({'asset_preparation':{'schema':999},'files':{}})
 def test_original_game_kept_when_recipe_unavailable(self):
  m=core.read_json(self.old/'release.json');m['prepared_assets']={'schema':1,'source':'source-release.json','report':'asset-report.json'};core.save(self.old/'release.json',m)
  with self.assertRaises(core.Refused):self.manager.enable()
  self.assertEqual((self.game/'gameinfo.gi').read_bytes(),self.original)

if __name__=='__main__':unittest.main()
