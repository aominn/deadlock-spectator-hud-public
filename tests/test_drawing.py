from pathlib import Path
import sys,unittest,time,io,threading,http.client,json
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from drawing_hud import DrawingStore,MAX_STROKES,MAX_POINTS
import effect_bridge as b
class DrawingTests(unittest.TestCase):
 def setUp(self):
  self.d=DrawingStore();self.signal={'id':'123','kind':'replay','at':100};self.view={'width':1920,'height':1080,'clock':20,'map':[.75,.6,.2,.35]};self.d.update_context(self.view,self.signal,stamp=1,wall=100)
 def payload(self,**changes):
  row={'epoch':self.d.epoch,'sequence':0,'drawing':True,'strokes':[{'space':'screen','tool':'pen','color':'cyan','width':3,'points':[[.1,.2],[.5,.4]]}]};row.update(changes);return row
 def test_no_context_and_normal_modes(self):
  self.assertFalse(DrawingStore().status(self.signal,1,100)['active'])
  for kind in ['lobby','practice','other']:
   with self.assertRaises(ValueError):self.d.update_context(self.view,{**self.signal,'kind':kind},1,100)
 def test_pause_stable_and_seek_new_epoch(self):
  old=self.d.epoch;self.d.replace(self.payload(),self.signal,1,100);self.d.update_context(self.view,self.signal,stamp=2,wall=100);self.assertEqual(old,self.d.epoch);self.assertEqual(len(self.d.strokes),1)
  self.d.update_context({**self.view,'clock':19},self.signal,stamp=2.1,wall=100);self.assertNotEqual(old,self.d.epoch);self.assertFalse(self.d.strokes)
 def test_identity_freshness_and_rejection(self):
  old=self.payload();self.d.replace(old,self.signal,1,100)
  self.assertFalse(self.d.status(self.signal,5,100)['active']);self.assertTrue(self.d.strokes);self.assertTrue(self.d.status(self.signal,5,100)['retained'])
  self.d.update_context(self.view,{**self.signal,'id':'456'},6,100)
  with self.assertRaises(ValueError):self.d.replace(old,{**self.signal,'id':'456'},6,100)
  with self.assertRaises(ValueError):self.d.update_context(self.view,self.signal,6,110)
 def test_background_resume_preserves_paused_or_running_ink(self):
  for clock in [20,40]:
   self.setUp();epoch=self.d.epoch;self.d.replace(self.payload(),self.signal,1,100)
   self.assertFalse(self.d.status({**self.signal,'at':90},20,120)['active'])
   with self.assertRaises(ValueError):self.d.update_context(self.view,{**self.signal,'at':90},20,120)
   self.assertEqual(epoch,self.d.epoch);self.assertEqual(len(self.d.strokes),1)
   self.d.update_context({**self.view,'clock':clock},{**self.signal,'at':120},21,120)
   self.assertEqual(epoch,self.d.epoch);self.assertEqual(len(self.d.strokes),1)
 def test_background_seek_and_normal_still_clear(self):
  for clock in [19,80]:
   self.setUp();epoch=self.d.epoch;self.d.replace(self.payload(),self.signal,1,100)
   self.d.update_context({**self.view,'clock':clock},{**self.signal,'at':120},21,120)
   self.assertNotEqual(epoch,self.d.epoch);self.assertFalse(self.d.strokes)
  self.setUp();self.d.replace(self.payload(),self.signal,1,100);self.d.status({**self.signal,'kind':'lobby'},2,100);self.assertFalse(self.d.strokes)
 def test_explicit_clear_works_while_context_stale(self):
  self.d.replace(self.payload(),self.signal,1,100)
  with self.assertRaises(ValueError):self.d.replace(self.payload(sequence=1),self.signal,20,120)
  self.d.replace(self.payload(sequence=1,drawing=False,strokes=[]),self.signal,20,120);self.assertFalse(self.d.strokes)
 def test_visible_thickness_and_old_style_compatibility(self):
  boxes=[]
  for seq,width in enumerate([3,8,5]):
   row={**self.payload()['strokes'][0],'width':width,'points':[[.2,.5],[.7,.5]]}
   self.d.replace(self.payload(sequence=seq,strokes=[row]),self.signal,1,100);box=Image.open(io.BytesIO(self.d.png())).getbbox();boxes.append(box[3]-box[1])
  self.assertGreaterEqual(boxes[1]-boxes[0],4);self.assertGreater(boxes[2],boxes[0])
 def test_monotonic_replace_clear_restart(self):
  self.d.replace(self.payload(),self.signal,1,100)
  with self.assertRaises(ValueError):self.d.replace(self.payload(),self.signal,1,100)
  self.d.replace(self.payload(sequence=1,drawing=False),self.signal,1,100);self.assertFalse(self.d.strokes)
  self.d.replace(self.payload(sequence=2),self.signal,1,100);self.assertEqual(len(self.d.strokes),1)
 def test_invalid_atomic_and_limits(self):
  self.d.replace(self.payload(),self.signal,1,100)
  for mutation in [{'points':[[float('nan'),.5]]},{'points':[[1.1,.3]]},{'color':'evil'},{'space':'world'},{'width':100},{'tool':'arrow','points':[[0,0],[.5,.5],[1,1]]},{'points':[[0,0]]*(MAX_POINTS+1)}]:
   row={**self.payload()['strokes'][0],**mutation}
   with self.assertRaises(ValueError):self.d.replace(self.payload(sequence=1,strokes=[row]),self.signal,1,100)
   self.assertEqual(self.d.sequence,0);self.assertEqual(len(self.d.strokes),1)
  with self.assertRaises(ValueError):self.d.replace(self.payload(sequence=1,strokes=self.payload()['strokes']*(MAX_STROKES+1)),self.signal,1,100)
 def test_png_map_anchor_resize_and_cache(self):
  row={**self.payload()['strokes'][0],'space':'map','points':[[.1,.1],[.8,.8]]};self.d.replace(self.payload(strokes=[row]),self.signal,1,100)
  data=self.d.png();self.assertIs(data,self.d.png());im=Image.open(io.BytesIO(data));box=im.getbbox();self.assertGreater(box[0],1920*.75);self.assertGreater(box[1],1080*.6)
  self.d.update_context({**self.view,'map':[.1,.1,.3,.3]},self.signal,1.2,100);im2=Image.open(io.BytesIO(self.d.png()));self.assertLess(im2.getbbox()[0],1920*.2)
  self.d.replace(self.payload(sequence=1,drawing=False),self.signal,1.2,100);self.assertIsNone(Image.open(io.BytesIO(self.d.png())).getbbox())
 def test_money_resync_does_not_clear_ink_but_session_exit_does(self):
  state=b.State();state.session_signal={'id':'123','kind':'replay','at':time.time()};state.drawing.update_context(self.view,state.session_signal);state.drawing.replace(self.payload(epoch=state.drawing.epoch),state.session_signal);epoch=state.drawing.epoch
  state.reset();self.assertEqual(state.drawing.epoch,epoch);self.assertEqual(len(state.drawing.strokes),1)
  state.line('[Client] Disconnecting from server: test');self.assertNotEqual(state.drawing.epoch,epoch);self.assertFalse(state.drawing.strokes)
 def test_render_allocation_bounded_for_tall_viewport(self):
  self.d.update_context({**self.view,'width':640,'height':4320},self.signal,1,100);self.d.replace(self.payload(),self.signal,1,100);im=Image.open(io.BytesIO(self.d.png()));self.assertLessEqual(im.width,1920);self.assertLessEqual(im.height,1080)
 def test_http_roundtrip_and_origin_block(self):
  state=b.State();state.session_signal={'id':'123','kind':'replay','at':time.time()};state.drawing.update_context(self.view,state.session_signal)
  server=b.ThreadingHTTPServer(('127.0.0.1',0),b.H);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
  def request(method,path,body=None,headers=None):
   conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
   try:conn.request(method,path,body,headers or {});res=conn.getresponse();return res.status,res.read()
   finally:conn.close()
  try:
   with patch.object(b,'S',state):
    path='/drawing-state?token='+b.TOKEN;code,body=request('GET',path);self.assertEqual(code,200);epoch=json.loads(body)['epoch'];row=self.payload(epoch=epoch)
    self.assertEqual(request('POST',path,json.dumps(row),{'Content-Type':'application/json'})[0],204)
    self.assertEqual(request('POST',path,json.dumps(row),{'Content-Type':'application/json','Origin':'https://example.com'})[0],404)
    self.assertEqual(request('POST',path,json.dumps(row),{'Content-Type':'text/plain'})[0],400)
    # An oversized incomplete upload may be reset by Windows before the error body arrives.
    try:self.assertEqual(request('POST',path,'x',{'Content-Type':'application/json','Content-Length':str(300000)})[0],400)
    except ConnectionResetError:pass
    code,body=request('GET','/ink.png?token='+b.TOKEN+'&context='+__import__('urllib.parse',fromlist=['quote']).quote(json.dumps(self.view)));self.assertEqual(code,200);self.assertIsNotNone(Image.open(io.BytesIO(body)).getbbox())
  finally:server.shutdown();server.server_close();t.join(3)
if __name__=='__main__':unittest.main()
