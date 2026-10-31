from pathlib import Path
import sys,unittest,json,ast,re,io
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from display_language import language,message
import effect_bridge as b
from PIL import Image
class DisplayLanguageTests(unittest.TestCase):
 def test_locale_rule(self):
  for value in ['ja','ja-JP','ja_JP','japanese']:self.assertEqual(language(value),'ja')
  for value in ['en','en-GB','de-DE','zh-CN','unknown','']:self.assertEqual(language(value),'en')
 def test_backend_user_messages_have_english_translation(self):
  root=Path(__file__).resolve().parents[1]
  for filename in ['engine/manager_core.py','engine/asset_install.py','engine/manager_cli.py']:
   for node in ast.walk(ast.parse((root/filename).read_text(encoding='utf-8'))):
    if isinstance(node,ast.Constant) and isinstance(node.value,str) and re.search('[ぁ-んァ-ヶ一-龥]',node.value):
     with self.subTest(text=node.value):
      self.assertEqual(message(node.value,'ja'),node.value);translated=message(node.value,'en');self.assertNotRegex(translated,'[ぁ-んァ-ヶ一-龥]');self.assertNotIn('could not be completed',translated,'a known message needs a specific translation')
 def test_identifiers_paths_and_unknown_english_stay_unchanged(self):
  for value in ['upgrade_close_range','steamapps/common/Deadlock','File not found: data.json']:self.assertEqual(message(value,'en'),value)
 def test_sale_language_has_separate_cache(self):
  ability=next(k for k,v in b.CAT['sale_items'].items() if v['name']=='クローズクォーター');ja=b.sale_texture(ability,'ja');en=b.sale_texture(ability,'en');self.assertEqual(ja.size,en.size);self.assertNotEqual(ja.tobytes(),en.tobytes());self.assertIs(b.sale_texture(ability,'en'),en)
 def test_game_language_does_not_follow_manager_locale(self):
  s=b.State();heroes=sorted(set(b.CAT['heroes'].values()))[1:13];data={'time':'0:00','language':'en','players':[{'hero':str(h),'pos':{'x':i*140,'y':54}} for i,h in enumerate(heroes)]};s.context(data);self.assertEqual(s.language,'en');s.context({**data,'language':'ja'});self.assertEqual(s.language,'ja')
 def test_english_and_localized_central_statuses(self):
  for value in [{'label':'Stunned'},{'label':'Étourdi','status_key':'stunned'}]:
   row={**value,'polarity':'debuff','presentation':'visible-label'};events=b.resolve_observed([row]);self.assertEqual(events[0]['modifier'],'stunned')
  self.assertEqual(b.resolve_observed([{'label':'Étourdi','status_key':'unknown','polarity':'debuff','presentation':'visible-label'}]),[])
 def test_english_base_caption_preserves_geometry(self):
  from base_guardian_hud import draw_guardian_rows
  rows=[{'team':2,'lane':4,'entity':1,'fraction':.5}];a=Image.new('RGBA',(1920,116));z=a.copy();draw_guardian_rows(a,rows,b.font_at,origin_y=0,language='ja');draw_guardian_rows(z,rows,b.font_at,origin_y=0,language='en');self.assertEqual(a.getbbox(),z.getbbox());self.assertNotEqual(a.tobytes(),z.tobytes());self.assertEqual(z.getpixel((16+3,40))[3],255)
if __name__=='__main__':unittest.main()
