import unittest,tempfile,sys,os,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from identity_catalog import build_catalog,resolve_item,localization_tokens
from build_local_release import runtime_sources
class IdentityPreparation(unittest.TestCase):
 def setUp(self):
  self.assets={'items':{'旧名':'s2r://item.vtex'},'abilities':{'87':[{'name':'ヒル治療','image':'s2r://leech.vtex'}]}}
  self.items={'sale_items':{'123':{'source':'upgrade_test','name':'旧名'}}};self.locales={'ja':{'upgrade_test':'新名'},'en':{'upgrade_test':'New Name'}}
 def test_identity_separate_from_language_and_existing_image(self):
  c=build_catalog(self.items,self.assets,self.locales);ja=resolve_item(c,'ja','新名');en=resolve_item(c,'en',' NEW NAME ')
  self.assertIs(ja,en);self.assertEqual(en['id'],'123');self.assertEqual(en['internal'],'upgrade_test');self.assertEqual(en['image'],'s2r://item.vtex');self.assertEqual(en['image_basis'],'existing-name-map');self.assertEqual(c['abilities']['87:1']['hero'],'87')
 def test_duplicate_display_names_are_not_guessed(self):
  self.items['sale_items']['456']={'source':'upgrade_other','name':'旧名'};self.locales['en']['upgrade_other']='New Name';c=build_catalog(self.items,self.assets,self.locales)
  self.assertIsNone(resolve_item(c,'en','New Name'));self.assertEqual(c['conflicts']['en']['new name'],['123','456']);self.assertIsNotNone(resolve_item(c,'ja','新名'))
 def test_unknown_language_name_and_near_match_stay_unknown(self):
  c=build_catalog(self.items,self.assets,self.locales)
  for lang,name in [('fr','New Name'),('en','NewName'),('en','New Names'),('en','unknown')]:self.assertIsNone(resolve_item(c,lang,name))
 def test_missing_translation_or_icon_preserves_identity(self):
  self.assets['items']={};c=build_catalog(self.items,self.assets,{'en':{}});self.assertEqual(c['items']['123']['names'],{});self.assertIsNone(c['items']['123']['image']);self.assertIsNone(resolve_item(c,'en','旧名'))
 def test_conflicting_images_are_not_chosen(self):
  self.assets['items']['新名']='s2r://different.vtex';self.assertIsNone(build_catalog(self.items,self.assets,self.locales)['items']['123']['image'])
 def test_unsafe_internal_name_and_invalid_ids_refused(self):
  for identity,internal in [('0','upgrade_test'),('4294967296','upgrade_test'),('123','../upgrade_test')]:
   with self.subTest(identity=identity,internal=internal),self.assertRaises(ValueError):build_catalog({'sale_items':{identity:{'source':internal}}},self.assets,self.locales)
 def test_localization_exact_tokens_not_search_or_descriptions(self):
  s='"upgrade_test" "Name"\n"upgrade_test_search" "Name Alias"\n"other" "Ignored"';self.assertEqual(localization_tokens(s),{'upgrade_test':'Name'})
  with self.assertRaises(ValueError):localization_tokens('"upgrade_test" "Name"\n"upgrade_test" "Other"')
 def test_current_catalog_builds_without_mutation(self):
  root=Path(__file__).resolve().parents[1];s=(root/'mod-src/asset-map.js').read_text(encoding='utf-8');assets=json.loads(s[s.index('{'):s.rindex('}')+1]);cat=json.loads((root/'engine/effect-catalog.json').read_text(encoding='utf-8'));before=json.dumps(cat,sort_keys=True);c=build_catalog(cat,assets,{'en':{},'ja':{}});self.assertEqual(len(c['items']),len(cat['sale_items']));self.assertEqual(json.dumps(cat,sort_keys=True),before);self.assertEqual(len(c['abilities']),sum(map(len,assets['abilities'].values())))
class RuntimeSourceInventory(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('SPEC_TEST_ARTIFACT_DIR'));self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def put(self,name):f=self.root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('test',encoding='utf-8')
 def test_current_source_added_removed_not_inherited_from_old_bundle(self):
  for n in ['engine/new_module.py','engine/effect-policy.json','parser/new-parser.mjs','parser/data/rules.json','engine/icons/native.png','parser/node_modules/dependency/index.js','engine/effect-catalog.json','engine/__pycache__/a.pyc']:self.put(n)
  self.assertEqual(set(runtime_sources(self.root)),{'engine/new_module.py','engine/effect-policy.json','parser/new-parser.mjs','parser/data/rules.json'});(self.root/'engine/new_module.py').unlink();self.assertNotIn('engine/new_module.py',runtime_sources(self.root))
 def test_unexpected_runtime_material_is_refused(self):
  self.put('engine/private.log')
  with self.assertRaisesRegex(ValueError,'Unexpected runtime source'):runtime_sources(self.root)
if __name__=='__main__':unittest.main()
