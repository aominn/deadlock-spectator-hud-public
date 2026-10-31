from pathlib import Path
import sys,unittest,io
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
from PIL import Image
class DiagnosticFrames(unittest.TestCase):
 def data(self):
  heroes=sorted(set(b.CAT['heroes'].values()),key=int)[:12]
  return dict(time='0:01',width=1920,players=[dict(hero=str(h),pos=dict(x=i*140,y=54),width=140,detail=False) for i,h in enumerate(heroes)])
 def test_write_failure_does_not_drop_hud_image(self):
  state=b.State();state.native_at=100
  with patch.object(b,'S',state),patch.object(b,'REPLAY',None),patch.object(b,'LIVE',None),patch.object(b.time,'monotonic',return_value=100),patch.object(Path,'write_text',side_effect=PermissionError('busy')):
   self.assertEqual(Image.open(io.BytesIO(b.render(self.data(),record=True))).size,(1920,420));self.assertGreater(state.metrics['diagnostic_save_errors'],0)
 def test_snapshots_are_at_most_two_per_second(self):
  state=b.State();state.native_at=100
  with patch.object(b,'S',state),patch.object(b,'REPLAY',None),patch.object(b,'LIVE',None),patch.object(b.time,'monotonic',return_value=100) as clock,patch.object(Path,'write_text',return_value=1) as write:
   for now in [100,100.1,100.49,100.5]:clock.return_value=now;b.render(self.data(),record=True)
   frames=[c for c in write.call_args_list if '3-second animated receipt stack' in c.args[0] and 'base_guardians' in c.args[0]];self.assertEqual(len(frames),2)
if __name__=='__main__':unittest.main()
