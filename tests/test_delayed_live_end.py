from pathlib import Path
import unittest,sys,copy,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from live_effect_source import LiveEffectSource
class DelayedEndTests(unittest.TestCase):
 def data(self):
  s=LiveEffectSource();s.route='a'*64
  d=dict(schema=1,route_sha256=s.route,session='b'*32,generation=20,state='ended',game_state=11,updated_at=1000,game_seconds=109.25,roster=[dict(handle=100+i,hero=i+1,team=2 if i<6 else 3) for i in range(12)],events=[],money=dict(schema=1,supported=True,columns=['hero','team','total','wallet'],updates=[dict(second=t,rows=[[i+1,2 if i<6 else 3,4000+t,800+t] for i in range(12)]) for t in range(80,110)]))
  return s,d,list(range(1,13))
 def test_early_end_keeps_historical_then_freezes_final(self):
  s,d,h=self.data()
  for t in range(84,101):
   self.assertEqual(s.advance(d,t,h,t,2000),[]);self.assertTrue(s.bound);self.assertEqual(s.phase,'finishing');self.assertIsNone(s.final_snapshot);self.assertEqual(s.money_at(d,t,h)[0]['wallet'],800+t)
  s.advance(d,101,h,101,2000,postgame=True);self.assertEqual(s.phase,'ended');self.assertEqual(s.final_clock,109);self.assertEqual(s.final_native_clock,101)
  for t in (101,102,150):
   s.advance(None,t,h,t,9000);self.assertEqual(s.money_at(None,t,h)[0]['wallet'],909)
  s.advance(None,100,h,151,9001);self.assertFalse(s.bound)
 def test_end_does_not_bypass_scope_or_missing_samples(self):
  for change in ('route','roster','state','money','future'):
   s,d,h=self.data()
   if change=='route':d['route_sha256']='c'*64
   if change=='roster':d['roster'][0]['hero']=2
   if change=='state':d['game_state']=8
   if change=='money':d['money']['updates']=[]
   if change=='future':d['game_seconds']=500
   s.advance(d,84,h,1,2000);self.assertFalse(s.bound,change)
 def test_ended_never_forwards_effects_or_economy(self):
  s,d,h=self.data();s.advance(d,84,h,1,1000);self.assertEqual(s.economy_advance(d,84,h,1),[])
  s.observe_log('Loading map "dl_hideout"');self.assertFalse(s.bound)
if __name__=='__main__':unittest.main()
