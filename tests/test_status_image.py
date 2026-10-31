from pathlib import Path
import sys,unittest,io,time
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
class StatusTests(unittest.TestCase):
 def test_loading_visible_and_ready_transparent(self):
  class Source:
   automatic=True;route='route'
   def status(self):return dict(state=self.state,message='リプレイを解析中…')
  s=Source();s.state='loading';state=b.State();state.last_http=10
  with patch.object(b,'S',state),patch.object(b,'LIVE',s),patch.object(b.time,'monotonic',lambda:11):
   im=Image.open(io.BytesIO(b.status_image())).convert('RGBA');self.assertEqual(im.size,(240,40));self.assertIsNotNone(im.getbbox());s.state='ready';self.assertIsNone(Image.open(io.BytesIO(b.status_image())).getbbox())
  with patch.object(b,'S',state),patch.object(b,'LIVE',s),patch.object(b.time,'monotonic',lambda:99):self.assertIsNone(Image.open(io.BytesIO(b.status_image())).getbbox())
if __name__=='__main__':unittest.main()
