from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import effect_bridge as bridge
from spectator_stats import panel_png

REPLAY = ('replay','same-replay','fixture',None)
LIVE = ('spectator','same-live',None,'fixture')
ROSTER = [{'hero':str(i),'name':'Hero '+str(i),'pos':{'x':i*140}} for i in range(1,13)]

def names():
    return tuple((row['hero'],row['name']) for row in ROSTER)

def damage(clock):
    return tuple((hero,2 if hero<7 else 3,hero+clock,1000+clock) for hero in range(1,13))

def history(clock):
    return ((0,0),(clock-1,300),(clock,500))

class Snapshot(unittest.TestCase):
    def setUp(self):
        self.state = bridge.State()
        self.scope = REPLAY
        for target, name, value in (
            (bridge,'S',self.state),
            (bridge,'stats_scope',lambda:self.scope),
            (bridge,'REPLAY',SimpleNamespace(bound=True,stats_at=lambda clock,heroes:(damage(clock),history(clock)),reset_cursor=lambda:None)),
            (bridge,'LIVE',None),
        ):
            mock=patch.object(target,name,value)
            mock.start()
            self.addCleanup(mock.stop)
        self.state.roster = ROSTER
        self.advance(305)

    def advance(self, clock):
        self.state.last_clock=clock
        self.state.last_http=time.monotonic()

    def request_image(self):
        minute,second=divmod(self.state.last_clock,60)
        return bridge.stats_image({'clock':[f'{minute}:{second:02d}']})

    def keys(self,*actions):
        self.state.stats_panels.poll(self.scope,actions)

    def test_damage_freeze_new_value_when_reopened(self):
        self.keys('damage')
        with patch.object(bridge,'panel_png',wraps=panel_png) as renderer:
            original=self.request_image()
            expected=tuple(row[:3] for row in damage(305))
            self.assertEqual(renderer.call_args.args[:6],('damage',expected,names(),(),305,True))
            self.advance(317)
            self.assertIs(self.request_image(),original)
            self.assertEqual(renderer.call_count,1)
            self.assertIsNone(bridge.stats_image({'clock':['5:16']}))
        self.keys('damage')
        self.assertEqual(self.request_image(),panel_png(None,(),(),(),0,True))
        self.keys('damage')
        self.assertNotEqual(self.request_image(),original)

    def test_graph_freeze_seek_and_switch(self):
        self.keys('graph')
        first=self.request_image()
        self.advance(330)
        self.assertIs(self.request_image(),first)
        self.state.reset()
        self.advance(160)
        with patch.object(time,'monotonic',return_value=self.state.stable_after-0.01):
            self.assertEqual(self.request_image(),panel_png('graph',(),(),(),0,True))
        self.state.stable_after=0
        self.assertNotEqual(self.request_image(),first)
        self.keys('damage')
        self.assertNotEqual(self.request_image(),first)

    def test_live_waiting_then_freeze_while_data_advances(self):
        self.scope=LIVE
        with patch.object(bridge,'LIVE',SimpleNamespace(bound=True)):
            self.keys('damage')
            self.assertEqual(self.request_image(),panel_png('damage',(),(),(),0,True))
            self.state.live_stats_rows=damage(305)
            first=self.request_image()
            self.state.live_stats_rows=damage(306)
            self.advance(306)
            self.assertIs(self.request_image(),first)
            self.state.live_stats.history={304:250,306:950}
            self.keys('graph')
            new=self.request_image()
            self.state.live_stats.history[307]=1250
            self.advance(307)
            self.assertIs(self.request_image(),new)
            self.keys('graph','graph')
            self.assertNotEqual(self.request_image(),new)

    def test_old_image_is_scoped_and_stale_clock_hides(self):
        self.keys('damage')
        first=self.request_image()
        self.scope=None
        self.assertEqual(self.request_image(),panel_png(None,(),(),(),0,True))
        self.keys()
        self.scope=('replay','new-replay','other',None)
        self.keys()
        self.assertEqual(self.request_image(),panel_png(None,(),(),(),0,True))
        self.advance(453)
        self.keys('damage')
        self.assertNotEqual(self.request_image(),first)
        self.state.last_http-=3
        self.assertEqual(self.request_image(),panel_png(None,(),(),(),0,True))

    def test_time_label_localized_on_ready_panels(self):
        labels=[]
        with patch('spectator_stats.label',side_effect=lambda *args,**kwargs:labels.append(args[2])):
            for ja in (True,False):
                for kind in ('damage','graph'):
                    panel_png.__wrapped__(kind,damage(305),names(),history(305),305,ja)
        self.assertEqual(labels.count('5:05時点'),2)
        self.assertEqual(labels.count('At 5:05'),2)
