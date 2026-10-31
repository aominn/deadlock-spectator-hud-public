from pathlib import Path
import unittest,sys,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from economy_hud import EconomyTimeline,EconomyCursor,EconomyView,native_receipt_owner

def event(seq=1,second=5,**extra):return {'id':str(seq),'sequence':seq,'generation':0,'tick':second*64,'seconds':second,'hero':10,'team':2,'parent':100,'cause':'kill','delta':546,'new_value':1000,'source':11,**extra}
def timeline(rows):return EconomyTimeline({'schema':1,'supported':True,'identity_verified':True,'events':rows},{10:2})
class EconomyTests(unittest.TestCase):
 def test_seek_pause_gap_scope(self):
  t=timeline([event(1,5),event(2,6),event(3,15)]);c=EconomyCursor()
  self.assertEqual(c.advance(t,2,0,'a'),[]);self.assertEqual(c.advance(t,3,1,'a'),[]);self.assertEqual(c.advance(t,4,2,'a'),[])
  self.assertEqual(len(c.advance(t,5,3,'a')),1);self.assertEqual(c.advance(t,5,3.1,'a'),[]);self.assertEqual(len(c.advance(t,6,4,'a')),1)
  self.assertEqual(c.advance(t,4,5,'a'),[]);self.assertEqual(c.advance(t,5,6,'a'),[]);self.assertEqual(c.advance(t,15,7,'a'),[]);self.assertEqual(c.advance(t,15,8,'other'),[])
 def test_fractional_currency_never_precedes_event(self):
  t=timeline([event(1,5,seconds=5.6875)]);c=EconomyCursor()
  for clock,stamp in [(2,100),(3,101),(4,102),(5,103)]:self.assertEqual(c.advance(t,clock,stamp,'a'),[])
  self.assertEqual(len(c.advance(t,6,104,'a')),1)
 def test_native_receipt_scope_not_rounded_wallet(self):
  players=[dict(hero=i+1,pos=dict(x=i*140,y=54),width=140,money=dict(total='19k',rect=[i*140+50,150,40,20],dead=False)) for i in range(12)]
  self.assertTrue(native_receipt_owner(players,'1','19k'));self.assertFalse(native_receipt_owner(players,'1','18k'));self.assertFalse(native_receipt_owner(players,'99','19k'));self.assertFalse(native_receipt_owner(players[:11],'1','19k'))
  players[0]['money']['total']='—';self.assertFalse(native_receipt_owner(players,'1','—'))
 def test_float_visibility_boundary(self):
  v=EconomyView();v.push([event()],104);self.assertIsNotNone(v.at(10,104));self.assertIsNone(v.at(10,106.2))
 def test_invalid_sources_duplicate_team(self):
  for rows in [[event(source=0)],[event(delta=-546)],[event(team=3)],[event(),event()],[event(seconds=float('nan'))]]:
   with self.assertRaises(ValueError):timeline(rows)
 def test_aggregate_queue_dedup_and_expire(self):
  v=EconomyView();v.push([event(),event(2,5,delta=128,source=38)],10);self.assertEqual(v.at(10,10)['amount'],674)
  v.push([event(3,6,delta=165,cause='urn',source=33)],11);self.assertEqual(v.at(10,11)['cause'],'kill')
  v.push([event(4,7,delta=165,cause='urn',source=33)],12);self.assertEqual(v.pending['10'][0]['amount'],330)
  v.push([event(4,7,delta=165,cause='urn',source=33)],12);self.assertEqual(v.pending['10'][0]['amount'],330)
  self.assertEqual(v.at(10,12.3)['cause'],'urn');self.assertIsNone(v.at(10,14.6));v.clear();self.assertIsNone(v.at(10,12))
 def test_wait_is_bounded_and_old_rows_do_not_replay(self):
  v=EconomyView();v.push([event()],10)
  for n in range(2,9):v.push([event(n,cause='urn' if n%2 else 'building',delta=n)],10+n*.01)
  self.assertEqual(len(v.pending['10']),4);self.assertTrue(any(x.get('decision')=='queue_limit' for x in v.audit))
  self.assertIsNone(v.at(10,14));self.assertNotIn('10',v.pending)
  self.assertTrue(any(x.get('decision')=='queue_expired' for x in v.audit))
 def test_continuous_same_cause_does_not_hold_lane_forever(self):
  v=EconomyView();v.push([event()],10)
  for n in range(2,7):v.push([event(n)],10+n*.5)
  self.assertLessEqual(v.at(10,13)['until'],13.4);self.assertIsNone(v.at(10,13.5))
if __name__=='__main__':unittest.main()
