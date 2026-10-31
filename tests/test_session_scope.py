from pathlib import Path
import sys,tempfile,threading,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from live_effect_source import LiveEffectSource
from auto_live_source import AutoLiveEffectSource
from auto_replay_source import AutoReplaySource,Cancelled,remote_connection
TV="[Client] creating client connection to 'https://relay.steamcontent.com/tv/fixture'"
NORMAL="[Client] creating client connection to '=[A:1:12345]:0'"
class Tests(unittest.TestCase):
 def test_live_leaves_tv_for_normal_sdr_or_ip(self):
  for address in ['=[A:1:12345]:0','192.0.2.1:27015','loopback','https://elsewhere.example/ordinary']:
   s=LiveEffectSource();s.observe_log(TV);self.assertIsNotNone(s.route);s.bound=True
   s.observe_log("[Client] creating client connection to '"+address+"'")
   self.assertIsNone(s.route);self.assertFalse(s.bound)
 def test_unrelated_log_and_pause_do_not_clear_live(self):
  s=LiveEffectSource();s.observe_log(TV);route=s.route;s.bound=True
  for line in ['[Client] Waiting for data','[Demo] playback paused','ordinary heartbeat']:s.observe_log(line);self.assertEqual(s.route,route);self.assertTrue(s.bound)
 def test_malformed_address_does_not_stop_log_watcher(self):
  s=LiveEffectSource();s.observe_log(TV);s.observe_log("[Client] creating client connection to 'https://['");self.assertIsNone(s.route)
 def test_live_worker_cancel_and_can_resume(self):
  with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
   started=threading.Event();cancelled=threading.Event()
   def runner(job):
    started.set()
    if job[3].wait(2):cancelled.set()
    return 0
   s=AutoLiveEffectSource(Path(folder)/'log',folder,'node','producer',runner=runner)
   try:
    s.observe_log(NORMAL);self.assertIsNone(s.job);self.assertEqual(s.metrics['producer_starts'],0)
    s.observe_log(TV);self.assertTrue(started.wait(2));s.observe_log(NORMAL);self.assertTrue(cancelled.wait(2));self.assertIsNone(s.route)
    started.clear();s.observe_log(TV);self.assertTrue(started.wait(2));self.assertIsNotNone(s.route)
   finally:s.close()
 def test_replay_cancel_normal_but_preserve_internal_pause_and_resume(self):
  class WaitingReplay(AutoReplaySource):
   def _load(self,match,generation,cancel):
    self.test_started.set();cancel.wait(3)
    if cancel.is_set():raise Cancelled()
    raise RuntimeError('fixture timed out')
  with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
   s=WaitingReplay(folder,Path(folder)/'cache','node','parser','fixture');s.test_started=threading.Event()
   try:
    s.observe_log(NORMAL);self.assertIsNone(s.target)
    demo="[Demo] playing demo from 'replays/12345678.dem'";s.observe_log(demo);self.assertTrue(s.test_started.wait(2));generation=s.generation
    for line in ["[Client] creating client connection to 'loopback'","[Client] creating client connection to '127.0.0.1:27015'",'[Demo] playback paused','quiet waiting']:
     s.observe_log(line);self.assertEqual(s.target,'12345678');self.assertEqual(s.generation,generation);self.assertFalse(s.cancel.is_set())
    old=s.cancel;s.observe_log(NORMAL);self.assertTrue(old.is_set());self.assertIsNone(s.target)
    s.test_started.clear();s.observe_log(demo);self.assertTrue(s.test_started.wait(2));self.assertEqual(s.target,'12345678')
   finally:s.close()
 def test_only_recognized_remote_connections_reset_replay(self):
  for address in ['loopback','localhost:27015','127.0.0.1:27015','[::1]:27015','unknown-internal']:
   self.assertFalse(remote_connection("[Client] creating client connection to '"+address+"'"))
  self.assertTrue(remote_connection(TV));self.assertTrue(remote_connection(NORMAL))
