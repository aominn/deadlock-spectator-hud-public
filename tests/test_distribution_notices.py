import hashlib,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_local_release import verify_distribution_files,verify_notices
class DistributionNotices(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('SPEC_TEST_ARTIFACT_DIR'));self.root=Path(self.temp.name)
  index=json.loads((ROOT/'licenses/THIRD-PARTY-INDEX.json').read_text(encoding='utf-8'))
  for n in set(index['notice_sha256'])|{'LICENSE','THIRD_PARTY_NOTICES.txt','licenses/THIRD-PARTY-INDEX.json',index['font']['file']}:
   f=self.root/n;f.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,f)
 def tearDown(self):self.temp.cleanup()
 def test_complete_reviewed_notices_pass(self):self.assertTrue(verify_notices(self.root)['components'])
 def test_root_mit_is_required(self):
  (self.root/'LICENSE').unlink()
  with self.assertRaisesRegex(ValueError,'Missing distribution notice'):verify_notices(self.root)
 def test_guide_is_required(self):
  (self.root/'THIRD_PARTY_NOTICES.txt').unlink()
  with self.assertRaisesRegex(ValueError,'Missing distribution notice'):verify_notices(self.root)
 def test_dependency_notice_cannot_be_replaced(self):
  (self.root/'licenses/Node-LICENSE.txt').write_text('different',encoding='utf-8')
  with self.assertRaisesRegex(ValueError,'Distribution notice changed'):verify_notices(self.root)
 def test_font_change_requires_notice_review(self):
  (self.root/'engine/fonts/NotoSansJP-Bold.ttf').write_bytes(b'different')
  with self.assertRaisesRegex(ValueError,'Font does not match'):verify_notices(self.root)
class DistributionFiles(unittest.TestCase):
 def test_regular_runtime_and_notices_allowed(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);runtime=root/'runtime'/'python';runtime.mkdir(parents=True)
   (runtime/'python314.zip').touch()
   (root/'release.json').touch()
   (root/'LICENSE').touch()
   verify_distribution_files(root)
 def test_personal_state_logs_and_development_artifacts_rejected(self):
  for name in ('docs/.ENV.local','docs/logs/session.txt','runtime/hosts.yml','engine/hotkeys.json',
               'HudManager.pdb','sample.dem.bz2','asset-preparation/game.vpk'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
    root=Path(directory);path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
    with self.assertRaisesRegex(ValueError,'Unexpected local file in distribution'):
     verify_distribution_files(root)

if __name__=='__main__':unittest.main()
