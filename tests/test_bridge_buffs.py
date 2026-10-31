from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from bridge_buffs import BridgeTimeline,BridgeView,bridge_geometry,RULES
class BridgeTests(unittest.TestCase):
 def row(self,kind='gun',applied=10,expires=170):return dict(hero=78,parent=9404490,serial=1,type=kind,applied=applied,expires=expires)
 def timeline(self,updates):return BridgeTimeline(dict(schema=1,updates=updates),{9404490:78})
 def test_dual_independent_lifetimes_and_seek(self):
  t=self.timeline([dict(seconds=10,rows=[self.row()]),dict(seconds=20,rows=[self.row(),self.row('survival',20,180)]),dict(seconds=170,rows=[self.row('survival',20,180)]),dict(seconds=180,rows=[])])
  for clock,kinds in [(9,[]),(10,['gun']),(20,['gun','survival']),(170,['survival']),(180,[]),(25,['gun','survival'])]:self.assertEqual([r['type'] for r in t.at(clock)],kinds)
 def test_bad_identity_duration_clock_and_duplicates(self):
  for change in [dict(parent=1),dict(hero=1),dict(type='unknown'),dict(applied=11),dict(expires=10),dict(expires=1000),dict(serial=True)]:
   row=self.row();row.update(change)
   with self.assertRaises(ValueError):self.timeline([dict(seconds=10,rows=[row])])
  with self.assertRaises(ValueError):self.timeline([dict(seconds=10,rows=[self.row(),self.row()])])
  with self.assertRaises(ValueError):self.timeline([dict(seconds=11,rows=[]),dict(seconds=10,rows=[])])
 def test_stable_two_slots_and_smooth_exit(self):
  v=BridgeView();rows=[self.row(),self.row('survival',20,180)];v.update(rows,1);self.assertEqual([x['opacity'] for x in v.update(rows,1.3)],[1,1])
  fading=v.update(rows[1:],1.4);self.assertEqual([(x['slot'],x['type']) for x in fading],[(0,'gun'),(1,'survival')])
  fade=v.update(rows[1:],1.49);self.assertTrue(0<fade[0]['opacity']<1)
  self.assertEqual([(x['slot'],x['type']) for x in v.update(rows[1:],1.6)],[(1,'survival')])
  v.update([],1.7);self.assertEqual(v.update([],1.9),[])
 def test_long_gap_clears_and_overflow_is_bounded(self):
  v=BridgeView();rows=[self.row(k) for k in RULES];v.update(rows,1);out=v.update(rows,1.3)
  self.assertEqual(len(out),2);self.assertEqual(sum(x['overflow'] for x in out),2)
  self.assertEqual(v.update([],4),[])
 def test_geometry_native_group_and_receipts(self):
  def hit(a,b):return a[0]<b[0]+b[2] and b[0]<a[0]+a[2] and a[1]<b[1]+b[3] and b[1]<a[1]+a[3]
  for width in (1920,2560):
   centers=[70+i*140 for i in range(6)]+[width-70-i*140 for i in range(6)]
   for center in centers:
    p=dict(pos=dict(x=center-70,y=46),width=140);boxes=[bridge_geometry(p,i,width) for i in (0,1)]
    self.assertFalse(hit(*boxes))
    for x,y,w,h in boxes:
     self.assertEqual((y,w,h),(171,20,20));self.assertFalse(hit((x,y,w,h),(center-10,171,20,20)))
     for other in centers:
      notice=(other+45 if other<width/2 else other-83,46,38,142)
      self.assertFalse(hit((x,y,w,h),notice))
      self.assertFalse(hit((x,y,w,h),(other-67,208,134,58)))
     self.assertTrue(x+w<center if center<width/2 else x>center)
 def test_independent_remaining_rings_and_pause(self):
  v=BridgeView();rows=[self.row(),self.row('survival',20,180)]
  first=v.update(rows,1,90);self.assertEqual([x['fraction'] for x in first],[.5,.5625])
  self.assertEqual([x['fraction'] for x in v.update(rows,1.2,90)],[.5,.5625])
  self.assertEqual([x['fraction'] for x in v.update(rows,1.4,170)],[0,.0625])
  rows[1]['expires']=160;self.assertAlmostEqual(v.update(rows[1:],1.5,150)[1]['fraction'],10/140)
 def test_ring_texture_is_white_and_bounded(self):
  import effect_bridge as b
  import PIL.ImageChops
  for kind in RULES:
   full=b.bridge_icon(kind,160);half=b.bridge_icon(kind,80);empty=b.bridge_icon(kind,0)
   self.assertEqual(full.size,(20,20));self.assertIsNotNone(PIL.ImageChops.difference(full,empty).getbbox())
   self.assertNotEqual(full.tobytes(),half.tobytes());self.assertNotEqual(half.tobytes(),empty.tobytes())
   self.assertTrue(any(r>220 and g>220 and bl>220 and al>150 for r,g,bl,al in (full.getpixel((x,y)) for y in range(20) for x in range(20))))
 def test_production_renderer_fraction_geometry_and_clear(self):
  import effect_bridge as b
  from unittest.mock import patch
  from PIL import Image
  st=b.State();st.roster=[dict(hero=78,pos=dict(x=142,y=46),width=140)];st.bridge_rows=[self.row(),self.row('survival',20,180)];st.stable_after=0;st.native_at=1
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:1):b.render_bridge_icons(Image.new('RGBA',(1920,420)),90)
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:1.3):
   records=b.render_bridge_icons(Image.new('RGBA',(1920,420)),90);self.assertEqual([x['fraction'] for x in records],[.5,.5625]);self.assertEqual([x['rect'][0] for x in records],[180,159])
  st.bridge_rows=st.bridge_rows[1:]
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:1.4):b.render_bridge_icons(Image.new('RGBA',(1920,420)),170)
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:1.7):
   records=b.render_bridge_icons(Image.new('RGBA',(1920,420)),170);self.assertEqual([(x['slot'],x['rect'][0]) for x in records],[(1,159)])
  st.bridge_rows=None
  with patch.object(b,'S',st),patch.object(b.time,'monotonic',lambda:1.8):self.assertEqual(b.render_bridge_icons(Image.new('RGBA',(1920,420)),170),[])
if __name__=='__main__':unittest.main()
