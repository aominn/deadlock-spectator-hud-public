from pathlib import Path
import unittest,sys,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from live_effect_source import LiveEffectSource
class PausedMoneyTests(unittest.TestCase):
 def source(self):
  s=LiveEffectSource();s.route='a'*64
  snapshot={'schema':1,'route_sha256':s.route,'session':'b'*32,'generation':1,'state':'ready','updated_at':1000,'game_seconds':10,'roster':[dict(handle=100+i,hero=i+1,team=2 if i<6 else 3) for i in range(12)],'events':[],'money':{'schema':1,'supported':True,'columns':['hero','team','total','wallet'],'updates':[dict(second=10,rows=[[i+1,2 if i<6 else 3,4000,800] for i in range(12)])]}}
  return s,snapshot
 def test_pause_static_money_and_silent_receipts(self):
  s,d=self.source();heroes=list(range(1,13));d['state']='paused';self.assertEqual(s.advance(d,10,heroes,1,1000,postgame=True),[]);self.assertTrue(s.bound);self.assertEqual(s.phase,'paused');self.assertEqual(len(s.money_at(d,10,heroes)),12);self.assertEqual(s.economy_advance(d,10,heroes,1),[])
  for stamp in (20,60,120):
   d['updated_at']=1000+stamp;self.assertEqual(s.advance(d,10,heroes,stamp,1000+stamp),[]);self.assertEqual(len(s.money_at(d,10,heroes)),12)
  d['state']='baselining';s.advance(d,10,heroes,121,1120);self.assertTrue(s.bound);self.assertEqual(len(s.money_at(d,10,heroes)),12)
  d['state']='ready';s.advance(d,10,heroes,122,1120);self.assertEqual(s.phase,'ready');self.assertGreater(s.stable_after,122)
 def test_pause_does_not_bypass_route_roster_or_freshness(self):
  for change in ('route','roster','stale','clock','state'):
   s,d=self.source();d['state']='paused'
   if change=='route':d['route_sha256']='c'*64
   elif change=='roster':d['roster'][0]['hero']=2
   elif change=='stale':d['updated_at']=990
   elif change=='clock':d['game_seconds']=100
   else:d['state']='error'
   self.assertEqual(s.advance(d,10,list(range(1,13)),1,1000),[]);self.assertFalse(s.bound,change);self.assertEqual(s.money_at(d,10,list(range(1,13))),[])
 def test_disconnection_clears_pause_binding(self):
  s,d=self.source();d['state']='paused';s.advance(d,10,list(range(1,13)),1,1000);s.observe_log('[Client] Disconnecting from server:');self.assertFalse(s.bound);self.assertEqual(s.money_at(d,10,list(range(1,13))),[])
 def test_confirmed_end_keeps_static_money_but_never_receipts(self):
  s,d=self.source();d.update(state='ended',game_state=11)
  self.assertEqual(s.advance(d,10,list(range(1,13)),1,1000,postgame=True),[]);self.assertEqual(s.phase,'ended');self.assertTrue(s.bound);self.assertEqual(len(s.money_at(d,10,list(range(1,13)))),12);self.assertEqual(s.economy_advance(d,10,list(range(1,13)),1),[])
  s,d=self.source();d['state']='ended';s.advance(d,10,list(range(1,13)),1,1000);self.assertFalse(s.bound,'a stopped/error producer is not proof of match end')
 def test_final_data_survives_age_and_clock_but_clears_on_new_scope(self):
  s,d=self.source();heroes=list(range(1,13));d.update(state='ended',game_state=11)
  s.advance(d,10,heroes,1,1000,postgame=True);self.assertEqual(s.phase,'ended')
  s.advance(d,75,heroes,100,5000);self.assertTrue(s.bound);self.assertEqual(len(s.money_at(d,75,heroes)),12)
  s.advance(None,75,heroes,101,5001);self.assertEqual(len(s.money_at(None,75,heroes)),12)
  s.observe_log('[Client] Disconnecting from server: broadcast completed');self.assertTrue(s.bound)
  s.observe_log('Loading map "dl_hideout"');self.assertFalse(s.bound);self.assertIsNone(s.final_snapshot)
  s,d=self.source();d.update(state='ended',game_state=11);s.advance(d,10,heroes,1,1000,postgame=True)
  changed=copy.deepcopy(d);changed['session']='c'*32;s.advance(changed,10,heroes,2,1001);self.assertFalse(s.bound)
  s,d=self.source();d.update(state='ended',game_state=11);s.advance(d,10,heroes,1,1000,postgame=True);s.advance(d,9,heroes,2,1001);self.assertFalse(s.bound,'rewind cannot borrow final data')
  s,d=self.source();d.update(state='ended',game_state=11);s.advance(d,10,heroes,1,1000,postgame=True);d['money']['updates'][0]['rows'][0][3]=1;self.assertEqual(s.money_at(d,10,heroes)[0]['wallet'],800,'retained data is a copy')
if __name__=='__main__':unittest.main()
