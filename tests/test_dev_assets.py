import unittest,tempfile,json,hashlib,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_dev_assets import populate,PreparationError

class DevelopmentAssets(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('SPEC_TEST_ARTIFACT_DIR'));self.base=Path(self.tmp.name);self.root=self.base/'source';self.generated=self.base/'generated';(self.root/'tools').mkdir(parents=True);self.generated.mkdir();self.files={}
 def tearDown(self):self.tmp.cleanup()
 def fixture(self,names=('engine/icons/test.png','mod-src/native-base/test.vcss_c','mod-src/citadel_hud_top_bar.xml')):
  for n in names:
   f=self.generated/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(('known '+n).encode());self.files[n]=hashlib.sha256(f.read_bytes()).hexdigest()
  recipe={'expected_vpk_sha256':'reviewed-vpk','outputs':[{'destination':n} for n in names]};(self.root/'tools/local-assets-recipe.json').write_text(json.dumps(recipe));proof={'passed':True,'scope':'local-game-assets','generated_vpk_sha256':'reviewed-vpk','files':self.files};(self.generated/'local-preparation-proof.json').write_text(json.dumps(proof))
 def test_verified_outputs_do_not_overwrite_source_metadata(self):
  self.fixture();(self.root/'engine').mkdir();meta=self.root/'engine/effect-catalog.json';meta.write_bytes(b'owned metadata');result=populate(self.generated,self.root);self.assertEqual(result['copied'],3);self.assertEqual(meta.read_bytes(),b'owned metadata')
  for n in self.files:self.assertEqual((self.root/n).read_bytes(),(self.generated/n).read_bytes())
 def test_tampering_rejected_before_copy(self):
  self.fixture();(self.generated/'engine/icons/test.png').write_bytes(b'tampered')
  with self.assertRaisesRegex(PreparationError,'changed'):populate(self.generated,self.root)
  self.assertFalse((self.root/'engine').exists())
 def test_source_file_destination_refused(self):
  self.fixture(('engine/effect_bridge.py',))
  with self.assertRaisesRegex(PreparationError,'Unexpected'):populate(self.generated,self.root)
  self.assertFalse((self.root/'engine').exists())
 def test_different_generation_rejected(self):
  self.fixture();f=self.generated/'local-preparation-proof.json';d=json.loads(f.read_text());d['generated_vpk_sha256']='old-vpk';f.write_text(json.dumps(d))
  with self.assertRaisesRegex(PreparationError,'match'):populate(self.generated,self.root)

if __name__=='__main__':unittest.main()
