from pathlib import Path
import unittest,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
class CompactNoticeLayout(unittest.TestCase):
 def test_top_alignment_and_four_slot_clearance(self):
  for side,x in [('left',0),('right',1060)]:
   player={'pos':{'x':x,'y':46},'width':140};rx,top,width,actual=b.corner_geometry(player,1920)
   self.assertEqual(actual,side);self.assertEqual((top,width),(46,38));boxes=b.card_obstacles([player],1920);self.assertEqual(boxes[0][1],230)
   notices=[{'started':0,'until':3,'order':i,'lane':i%4} for i in range(4)];rows=b.receipt_layout(notices,rx,top,width,boxes,1)
   self.assertEqual([z[2] for z in rows],[46,82,118,154]);self.assertEqual(rows[-1][2]+b.NOTICE_HEIGHT+42,boxes[0][1])
 def test_stack_animation_never_moves_above_portrait(self):
  for count in [1,4,5,7,16,64]:
   rows=[{'started':0,'until':3,'order':i,'lane':i%4} for i in range(count)]
   for stamp in [0,.01,.2,.45,1,2.3,2.5,2.9,2.99]:
    layout=b.receipt_layout(rows,100,46,38,[],stamp)
    self.assertEqual(len(layout),count)
    self.assertTrue(all(46<=top and top+34<=188 for _,_,top,_,_,_ in layout))
   self.assertEqual(b.receipt_layout(rows,100,46,38,[],3),[])
 def test_production_texture_size_and_icon_clears_accent(self):
  for row in [*b.CAT['modifiers'].values(),*b.DISPLAY_POLICY.values()]:
   for polarity in ['buff','debuff']:
    texture,label,_=b.receipt_texture('native_status','stunned',row['effect'],polarity)
    self.assertEqual(texture.size,(38,34));self.assertEqual(texture.getpixel((37,0))[3],0)
    self.assertEqual(label,'')
    self.assertEqual(texture.getpixel((3,25)),(155,186,139,255) if polarity=='buff' else (205,139,103,255))
if __name__=='__main__':unittest.main()
