from pathlib import Path
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import effect_bridge as b
class StackedReceipts(unittest.TestCase):
 def test_admission_beyond_four_expiry_and_oldest_order(self):
  clock=[10.0]
  with patch.object(b.time,'monotonic',lambda:clock[0]):
   s=b.State();s.stable_after=0
   def feed(rows):
    s.native_at=s.last_http=clock[0];s.current='hero';s.rows=rows;s.finish()
   rows=[{'source':'native_status','modifier':'effect'+str(i),'effect':'スタン','polarity':'debuff'} for i in range(8)]
   feed([]);feed(rows[:4]);clock[0]=11;feed(rows)
   active=s.notifications['hero'];self.assertEqual(len(active),8);self.assertEqual(sorted(v['lane'] for v in active.values()),[0,0,1,1,2,2,3,3])
   order=sorted(active.values(),key=lambda e:(e['started'],e['order']));self.assertTrue(all(v['started']==11 for v in order[4:]))
   s.expire('hero',13);self.assertEqual(len(active),4);self.assertTrue(all(v['until']==14 for v in active.values()));s.expire('hero',14);self.assertFalse(active)
 def test_same_four_slot_envelope_with_purchase_obstacles(self):
  for total in (1,4,5,8,16,64):
   events=[{'started':i*.01,'until':3+i*.01,'order':i,'lane':i%4} for i in range(total)]
   for boxes in ([],[(100,150,134,58),(100,212,134,58)]):
    layout=b.receipt_layout(events,100,46,38,boxes,stamp=2)
    for event,depth,top,count,front,opacity in layout:
     self.assertGreaterEqual(top,46);self.assertLessEqual(top+34,200)
     self.assertFalse(any(100<ox+ow and ox<138 and top<oy+oh and oy<top+34 for ox,oy,ow,oh in boxes))
     self.assertGreaterEqual(opacity,0);self.assertLessEqual(opacity,1)
    self.assertEqual([x[0]['order'] for x in layout],sorted(x[0]['order'] for x in layout))
    if total>4 or not boxes:self.assertEqual(len(layout),total)
    self.assertEqual(sum(x[4] for x in layout),len(layout) if total<=4 else 1);self.assertTrue(layout[-1][4])
 def test_four_normal_slots_and_five_switch_to_overlap(self):
  events=[{'started':0.,'until':3.,'order':i,'lane':i%4} for i in range(5)]
  four=b.receipt_layout(events[:4],100,46,38,[],stamp=1)
  self.assertEqual([e[2] for e in four],[46,82,118,154]);self.assertTrue(all(e[5]==1 for e in four))
  five=b.receipt_layout(events,100,46,38,[],stamp=1)
  self.assertEqual([e[0]['order'] for e in five],list(range(5)));self.assertTrue(five[-1][4]);self.assertTrue(any(z[2]<x[2]+34 for x,z in zip(five,five[1:])))
 def test_four_exit_fades_in_place_with_three_second_boundary(self):
  event={'started':0.,'until':3.,'order':1,'lane':0}
  steady=b.receipt_layout([event],100,46,38,[],stamp=2.5)[0];fading=b.receipt_layout([event],100,46,38,[],stamp=2.9)[0]
  self.assertEqual(fading[2],steady[2]);self.assertLess(fading[5],steady[5]);self.assertEqual(b.receipt_layout([event],100,46,38,[],stamp=3),[])
 def test_five_returns_to_four_nonoverlapping_slots(self):
  events=[{'started':0.,'until':1. if i==0 else 3.,'order':i,'lane':i%4} for i in range(5)]
  four=b.receipt_layout(events,100,46,38,[],stamp=1.1)
  self.assertEqual(len(four),4);self.assertEqual(sorted(e[2] for e in four),[46,82,118,154])
 def test_cached_texture_remains_unfaded_and_unmodified(self):
  b.receipt_texture.cache_clear();row,_,_=b.receipt_texture('native_status','stunned','スタン','debuff');copy=row.copy();copy.putalpha(0)
  again,_,_=b.receipt_texture('native_status','stunned','スタン','debuff');self.assertIs(again,row);self.assertGreater(again.getpixel((5,2))[3],200);self.assertEqual(b.receipt_texture.cache_info().hits,1)
 def test_bounded_backlog_keeps_newest(self):
  with patch.object(b.time,'monotonic',lambda:10.0):
   s=b.State();s.stable_after=0;s.native_at=s.last_http=10;s.current='hero';s.rows=[];s.finish();s.current='hero';s.rows=[{'source':'native_status','modifier':str(i),'effect':'スタン','polarity':'debuff'} for i in range(70)];s.finish()
   active=s.notifications['hero'];self.assertEqual(len(active),64);self.assertEqual(max(v['order'] for v in active.values()),70);self.assertEqual(min(v['order'] for v in active.values()),7)
 def test_live_and_replay_admit_more_than_four(self):
  old=b.S
  try:
   for scope in ('live-broadcast','replay-index'):
    with patch.object(b.time,'monotonic',lambda:10.0):
     b.S=b.State();b.S.stable_after=0;b.S.native_at=b.S.last_http=10;b.S.roster=[{'hero':'6'}];b.apply_events([],{},scope,'fixture');windows={}
     events=[{'hero':6,'path':'fixture/modifier'+str(i),'effect':'スタン','polarity':'debuff','serial':i,'seconds':1} for i in range(9)]

     with patch.dict(b.DISPLAY_POLICY,{e['path']:{'effect':e['effect'],'polarity':e['polarity']} for e in events}):
      b.apply_events(events,windows,scope,'fixture');self.assertEqual(len(b.S.notifications['6']),9)
  finally:b.S=old
if __name__=='__main__':unittest.main()
