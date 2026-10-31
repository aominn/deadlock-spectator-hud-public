import unittest,tempfile,struct,zlib,hashlib,sys,json,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from local_assets import GameArchive,PreparationError,member,splice,verify_tree,prepare

class LocalAssetSafety(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('SPEC_TEST_ARTIFACT_DIR'));self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def archive(self,body=b'known bytes',version=1,pre=b'',arch=32767,offset=0,length=None,crc=None,duplicate=False):
  entry=struct.pack('<IHHIIH',zlib.crc32(pre+body) if crc is None else crc,len(pre),arch,offset,len(body) if length is None else length,65535)+pre
  tree=b'vtex_c\0panorama/images/hud\0icon\0'+entry+(b'icon\0'+entry if duplicate else b'')+b'\0\0\0';head=struct.pack('<III',0x55aa1234,version,len(tree))+(b'\0'*16 if version==2 else b'');(self.root/'pak01_dir.vpk').write_bytes(head+tree+body);return 'panorama/images/hud/icon.vtex_c'
 def test_v1_preload_and_embedded_payload(self):
  name=self.archive(pre=b'prefix');self.assertEqual(GameArchive(self.root).read(name,hashlib.sha256(b'prefixknown bytes').hexdigest()),b'prefixknown bytes')
 def test_v2_header_offset(self):
  name=self.archive(version=2);self.assertEqual(GameArchive(self.root).read(name,hashlib.sha256(b'known bytes').hexdigest()),b'known bytes')
 def test_external_archive(self):
  name=self.archive(arch=1);(self.root/'pak01_001.vpk').write_bytes(b'known bytes');self.assertEqual(GameArchive(self.root).read(name,hashlib.sha256(b'known bytes').hexdigest()),b'known bytes')
 def test_unknown_game_update_is_refused(self):
  name=self.archive();before=(self.root/'pak01_dir.vpk').read_bytes()
  with self.assertRaisesRegex(PreparationError,'Untested'):GameArchive(self.root).read(name,'0'*64)
  self.assertEqual((self.root/'pak01_dir.vpk').read_bytes(),before)
 def test_resource_crc_corruption(self):
  name=self.archive(crc=123)
  with self.assertRaisesRegex(PreparationError,'CRC'):GameArchive(self.root).read(name,'0'*64)
 def test_out_of_bounds(self):
  name=self.archive(length=100)
  with self.assertRaisesRegex(PreparationError,'bounds'):GameArchive(self.root).read(name,'0'*64)
 def test_duplicate_entries(self):
  self.archive(duplicate=True)
  with self.assertRaisesRegex(PreparationError,'Duplicate'):GameArchive(self.root)
 def test_truncated_header(self):
  (self.root/'pak01_dir.vpk').write_bytes(b'bad')
  with self.assertRaisesRegex(PreparationError,'truncated'):GameArchive(self.root)
 def test_bad_signature(self):
  self.archive();f=self.root/'pak01_dir.vpk';f.write_bytes(b'bad!'+f.read_bytes()[4:])
  with self.assertRaisesRegex(PreparationError,'header'):GameArchive(self.root)
 def test_missing_or_out_of_scope_resource(self):
  self.archive();a=GameArchive(self.root)
  for path in ['scripts/config.vdata_c','panorama/images/no.vtex_c','panorama/images/../../secret.vtex_c']:
   with self.subTest(path=path),self.assertRaises(PreparationError):a.read(path,'0'*64)
 def test_windows_member_paths(self):
  for name in ['../file','C:/x','//host/x','a\\b','a//b','a/CON','a/file.','a/fi\nle','/absolute','a/stream:x']:
   with self.subTest(name=name),self.assertRaises(PreparationError):member(name)
  self.assertEqual(member('engine/icons/file.png'),'engine/icons/file.png')
 def test_splice_does_not_need_original_text_in_recipe(self):self.assertEqual(splice(b'original body',[{'copy':[0,8]},{'text':'new'},{'copy':[9,4]}]),b'originalnewbody')
 def test_splice_invalid_ranges_and_operations(self):
  for ops in [[{'copy':[-1,2]}],[{'copy':[0,9]}],[{'copy':[True,1]}],[{'file':'secret'}],[{'text':123}]]:
   with self.subTest(ops=ops),self.assertRaises(PreparationError):splice(b'abc',ops)
 def test_tampered_template_refused(self):
  (self.root/'file.txt').write_bytes(b'changed')
  with self.assertRaisesRegex(PreparationError,'changed'):verify_tree(self.root,{'file.txt':hashlib.sha256(b'known').hexdigest()})
 def test_extra_file_refused(self):
  (self.root/'secret.txt').write_text('unknown')
  with self.assertRaisesRegex(PreparationError,'Unexpected'):verify_tree(self.root,{})
 def test_existing_output_not_overwritten(self):
  recipe=self.root/'recipe.json';recipe.write_text(json.dumps({'schema':1,'resources':{'x':{}}}));out=self.root/'out';out.mkdir();marker=out/'keep';marker.write_text('user')
  with self.assertRaisesRegex(PreparationError,'new folder'):prepare(self.root/'game',recipe,self.root/'template',self.root/'reader.dll',out)
  self.assertEqual(marker.read_text(),'user')
 def test_invalid_recipe_no_output(self):
  recipe=self.root/'recipe.json';recipe.write_text('{"schema":999}');out=self.root/'output'
  with self.assertRaisesRegex(PreparationError,'recipe'):prepare(self.root/'game',recipe,self.root/'template',self.root/'reader.dll',out)
  self.assertFalse(out.exists())
 def test_output_inside_game_refused(self):
  game=self.root/'game';game.mkdir();recipe=self.root/'recipe.json';recipe.write_text(json.dumps({'schema':1,'resources':{'x':{}}}));out=game/'output'
  with self.assertRaisesRegex(PreparationError,'separate'):prepare(game,recipe,self.root/'template',self.root/'reader.dll',out)
  self.assertFalse(out.exists())

 def prepare_fixture(self):
  name=self.archive();game=self.root/'game';game.mkdir();(self.root/'pak01_dir.vpk').rename(game/'pak01_dir.vpk');template=self.root/'template';template.mkdir();reader=self.root/'reader';reader.mkdir();exe=reader/'reader.dll';exe.write_bytes(b'fixed test decoder');key='0'*20;recipe={'schema':1,'resources':{key:{'asset':name,'sha256':hashlib.sha256(b'known bytes').hexdigest(),'mode':'png','decoded_sha256':hashlib.sha256(b'expected').hexdigest()}},'outputs':[],'template_sha256':{},'reader_files':{'reader.dll':hashlib.sha256(exe.read_bytes()).hexdigest()},'reader_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()};rf=self.root/'recipe.json';rf.write_text(json.dumps(recipe));return game,rf,template,exe,self.root/'generated'
 def test_decoder_failure_removes_temporary_output(self):
  from types import SimpleNamespace
  args=self.prepare_fixture();before=(args[0]/'pak01_dir.vpk').read_bytes()
  with patch('local_assets.subprocess.run',return_value=SimpleNamespace(returncode=1,stderr='test failure')),self.assertRaisesRegex(PreparationError,'decoder failed'):prepare(*args)
  self.assertFalse(args[-1].exists());self.assertFalse(list(self.root.glob('.hud-assets-*')));self.assertEqual((args[0]/'pak01_dir.vpk').read_bytes(),before)
 def test_incorrect_decoding_is_not_committed(self):
  from types import SimpleNamespace
  args=self.prepare_fixture()
  def bad_decoder(command,**kwargs):
   for row in json.loads(Path(command[-1]).read_text()):Path(row['output']).write_bytes(b'incorrect')
   return SimpleNamespace(returncode=0,stderr='')
  with patch('local_assets.subprocess.run',side_effect=bad_decoder),self.assertRaisesRegex(PreparationError,'Decoded resource differs'):prepare(*args)
  self.assertFalse(args[-1].exists());self.assertFalse(list(self.root.glob('.hud-assets-*')))
 def test_game_update_fails_before_decoder_and_output(self):
  args=self.prepare_fixture();rf=args[1];v=json.loads(rf.read_text());next(iter(v['resources'].values()))['sha256']='f'*64;rf.write_text(json.dumps(v))
  with patch('local_assets.subprocess.run') as runner,self.assertRaisesRegex(PreparationError,'Untested'):prepare(*args)
  runner.assert_not_called();self.assertFalse(args[-1].exists());self.assertFalse(list(self.root.glob('.hud-assets-*')))

if __name__=='__main__':unittest.main()
