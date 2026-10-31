from pathlib import Path
import json,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
class EffectPolicy(unittest.TestCase):
 def test_engine_and_parser_use_one_policy_source(self):
  source=(b.ROOT.parent/'parser/extract-replay-effects.mjs').read_text(encoding='utf-8')
  self.assertIn("new URL('../engine/effect-policy.json',import.meta.url)",source)
  self.assertFalse((b.ROOT.parent/'parser/data/effect-policy.json').exists())
 def test_numeric_debuff_and_bookkeeping_never_admitted(self):
  for k in ('upgrade_glitch/modifier_glitch_self_penalty','upgrade_fury_trance/modifier_fury_trance/modifier_citadel_silenced','ability_sleep_dagger/modifier_citadel_sleep_dagger_asleep/modifier_bullet_shred_postsleep'):
   self.assertNotIn(k,b.DISPLAY_POLICY)
  self.assertEqual(b.resolve_world([{'classes':['bullet_armor_reduction','isDebuff']}]),[])
  self.assertEqual(b.resolve_world([{'classes':['unknown','isDebuff']}]),[])
 def test_new_labels_fit_and_have_native_or_generic_icons(self):
  for path,rule in b.DISPLAY_POLICY.items():
   source=path.split('/')[0] if '/' in path else 'native_status';modifier=path.split('/')[-1] if '/' in path else 'stunned'
   row,label,icon=b.paint_receipt(dict(rule,source=source,modifier=modifier))
   self.assertTrue(icon,(path,label));self.assertEqual(row.size,(38,34));self.assertEqual(label,'')
 def test_icon_only_uses_full_area_without_drawing_text(self):
  for polarity in ('buff','debuff'):
   with patch.object(b,'font_at',side_effect=AssertionError('No caption font should be used')):
    row,label,icon=b.paint_receipt({'source':'native_status','modifier':'stunned','effect':'任意の長い効果名','polarity':polarity})
   self.assertEqual(label,'');self.assertTrue(icon)
   native=b.effect_icon_image(icon)
   expected=b.Image.new('RGBA',(38,34));ink=b.ImageDraw.Draw(expected);ink.rectangle((3,2,34,30),fill=(24,25,24,210));expected.alpha_composite(native,(7,4));ink.rectangle((3,2,4,30),fill=(155,186,139,255) if polarity=='buff' else (205,139,103,255))
   self.assertEqual(row.tobytes(),expected.tobytes())
 def test_missing_icon_never_becomes_empty_colored_notification(self):
  row,label,icon=b.paint_receipt({'source':'unknown','modifier':'unknown','effect':'unknown','polarity':'debuff'})
  self.assertIsNone(row.getbbox());self.assertIsNone(icon);self.assertEqual(label,'')
 def test_same_icon_collapses_but_polarity_and_latest_expiry_remain(self):
  one={'source':'native_status','modifier':'stunned','polarity':'debuff','started':1,'until':4,'order':1}
  two={**one,'started':2,'until':5,'order':2};positive={**one,'polarity':'buff','order':3}
  result=b.icon_receipts([one,two,positive]);self.assertEqual(len(result),2);self.assertIn(two,result);self.assertIn(positive,result);self.assertNotIn(one,result)
 def test_forecast_removed_and_new_state_paths_are_present(self):
  self.assertNotIn('upgrade_target_stun/modifier_citadel_delayed_stun',b.DISPLAY_POLICY)
  self.assertEqual(b.DISPLAY_POLICY['ability_magician_animalhexarea/hexarea_modifier/animalhex_curse_modifier']['effect'],'変身')
  self.assertEqual(b.DISPLAY_POLICY['citadel_ability_self_vacuum/modifier_vacuumaura/modifier_vacuumaura_target']['effect'],'吸引')
 def test_compound_requires_same_confirmed_caster(self):
  curse={'hero':6,'path':'upgrade_glitch/modifier_glitch_debuff','effect':'カース','cause':'upgrade_glitch','caster_parent':1000,'seconds':5}
  secondary={**curse,'path':'modifier_citadel_stunned','effect':'スタン','duration':.2}
  unrelated={**secondary,'caster_parent':2000}
  keep,drop=b.replay_compounds([curse,secondary,unrelated]);self.assertEqual(drop,[secondary]);self.assertIn(unrelated,keep)
  keep,drop=b.replay_compounds([{**curse,'caster_parent':None},{**secondary,'caster_parent':None}]);self.assertEqual(len(keep),2)
 def test_direct_event_payload_cannot_bypass_policy(self):
  with patch.object(b,'S',b.State()),patch.object(b.time,'monotonic',lambda:10):
   b.S.roster=[];windows={};b.apply_events([{'hero':6,'path':'unreviewed/defense','effect':'スタン','polarity':'debuff','serial':1,'seconds':1}],windows,'replay-index','fixture');self.assertFalse(windows)
if __name__=='__main__':unittest.main()
