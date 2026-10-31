from pathlib import Path
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
class NoticeTiming(unittest.TestCase):
 def test_native_receipt_lifetime(self):
  clock=[10.0]
  with patch.object(b.time,'monotonic',lambda:clock[0]):
   s=b.State();s.stable_after=0;s.native_at=10;s.last_http=10;s.current='hero';s.rows=[];s.finish()
   s.current='hero';s.rows=[{'source':'native_status','modifier':'stunned','effect':'スタン','polarity':'debuff'}];s.finish()
   notice=s.notifications['hero']['native_status/stunned'];self.assertEqual(notice['until'],13)
   s.expire('hero',12.99);self.assertTrue(s.notifications['hero']);s.expire('hero',13);self.assertFalse(s.notifications['hero'])
 def test_explicit_live_replay_window_uses_same_duration(self):
  with patch.object(b.time,'monotonic',lambda:20.0):
   saved=b.S
   try:
    b.S=b.State();b.S.roster=[];windows={}
    b.apply_events([{'hero':6,'path':'modifier_citadel_stunned','effect':'スタン','polarity':'debuff','serial':1,'seconds':1}],windows,'live-broadcast','live')
    self.assertEqual(next(iter(windows['6'].values()))[0],23)
   finally:b.S=saved
 def test_icon_only_compact_background(self):
  tag,_,_=b.paint_receipt({'source':'native_status','modifier':'stunned','effect':'スタン','polarity':'debuff'})
  self.assertEqual(tag.size,(38,34));self.assertEqual(tag.getpixel((5,2)),(24,25,24,210));self.assertEqual(tag.getpixel((37,0))[3],0)
if __name__=='__main__':unittest.main()
