from pathlib import Path
import sys,tempfile,json,unittest,time,types
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from native_session import mode_signal,lobby_line,resume_log
TV="[Client] CL: CCreateGameClientJob creating client connection to 'https://relay.steamcontent.com/tv/fixture'"
DEMO="[Demo] playing demo from 'replays/124885053.dem'"
FLAGS={'spec':False,'replay':False,'hideout':False,'practice':False,'teamSpectator':False}
def ui(kind,at=1000,seq=1):
 f=dict(FLAGS)
 if kind=='lobby':f.update(hideout=True,practice=True)
 if kind=='replay':f.update(spec=True,replay=True,teamSpectator=True)
 if kind=='spectator':f.update(spec=True,teamSpectator=True)
 if kind=='practice':f['practice']=True
 return '[PanoramaScript] [SpecSessionState] '+json.dumps({'v':1,'id':'111-222','seq':seq,'at':at*1000,'flags':f})
class Tests(unittest.TestCase):
 def test_observed_native_states_and_hideout_priority(self):
  for k in ['lobby','replay','spectator','practice','other']:self.assertEqual(mode_signal(ui(k),wall=1000)['kind'],k)
 def test_old_or_invalid_native_signals_not_used_for_restore(self):
  self.assertIsNone(mode_signal(ui('replay',at=900),wall=1000))
  self.assertIsNone(mode_signal(ui('replay'),wall=1000,not_before=1000.1))
  self.assertIsNone(mode_signal('[SpecSessionState] {}',wall=1000))
  self.assertIsNone(mode_signal(ui('replay').replace('true','1'),wall=1000))
 def test_map_name_not_shared_game_state7_is_lobby_evidence(self):
  self.assertTrue(lobby_line('10/29 18:00:01 Loading map "dl_hideout"'))
  self.assertFalse(lobby_line('ChangeGameState: GameInProgress (7)'))
 def restore(self,text,not_before=None):
  with tempfile.TemporaryDirectory(dir=Path.cwd()) as d:
   p=Path(d)/'game.log';p.write_text(text,encoding='utf-8');return resume_log(p,wall=1000,not_before=not_before)
 def test_restore_only_current_matching_start_and_not_notices(self):
  for k,start in [('spectator',TV),('replay',DEMO)]:
   seed,pos,partial,meta=self.restore(start+'\n[SpecEconomyReceipt] old-notice\n'+ui(k)+'\n')
   self.assertEqual(len(seed),2);self.assertEqual(meta['reason'],'restored');self.assertNotIn('old-notice',''.join(seed));self.assertEqual(partial,b'')
 def test_no_restore_in_lobby_or_after_exit_or_mismatched_mode(self):
  for text in [TV+'\nLoading map "dl_hideout"\n'+ui('lobby')+'\n',DEMO+'\n[Client] Disconnecting from server: exit\n'+ui('replay')+'\n',DEMO+'\n'+ui('spectator')+'\n']:
   self.assertNotEqual(self.restore(text)[3]['reason'],'restored')
 def test_wait_for_signal_after_helper_started_and_keep_partial_line(self):
  text=TV+'\n'+ui('spectator',999)+'\npartial'
  seed,pos,partial,meta=self.restore(text,not_before=999.5);self.assertFalse(seed);self.assertEqual(partial,b'partial');self.assertEqual(meta['reason'],'waiting-for-current-ui')
 def test_expand_bounded_window_for_longer_session(self):
  text=TV+'\n'+('x'*4096+'\n')*1030+ui('spectator')+'\n'
  seed,pos,partial,meta=self.restore(text);self.assertEqual(meta['reason'],'restored');self.assertGreater(meta['bytes_read'],4*1024**2)
 def test_new_normal_connection_cannot_restore_stale_tv(self):
  text=TV+"\n[Client] creating client connection to '=[A:1:1234]:0'\n"+ui('spectator')+'\n';self.assertNotEqual(self.restore(text)[3]['reason'],'restored')
 def test_native_lobby_only_cancels_after_session_confirmed(self):
  import effect_bridge as b
  live=types.SimpleNamespace(route=None,bound=False,observe_log=Mock(),reset=Mock());replay=types.SimpleNamespace(target='124885053',bound=False,automatic=True,observe_log=Mock(),reset_cursor=Mock())
  with tempfile.TemporaryDirectory(dir=Path.cwd()) as d,patch.object(b,'LIVE',live),patch.object(b,'REPLAY',replay),patch.object(b,'STATE',Path(d)):
   state=b.State();state.line(DEMO);calls=replay.observe_log.call_count
   state.line(ui('lobby',at=time.time(),seq=1));self.assertEqual(replay.observe_log.call_count,calls,'old lobby flag during loading is tolerated')
   state.line(ui('replay',at=time.time(),seq=2));self.assertTrue(state.native_confirmed)
   state.line(ui('lobby',at=time.time(),seq=3));self.assertFalse(state.native_confirmed);self.assertIn('native lobby confirmed',replay.observe_log.call_args.args[0])
   again=replay.observe_log.call_count;state.line(ui('lobby',at=time.time(),seq=3));self.assertEqual(replay.observe_log.call_count,again)
 def test_silent_or_old_heartbeat_does_not_cancel_active_session(self):
  import effect_bridge as b
  live=types.SimpleNamespace(route='a'*64,bound=True,observe_log=Mock(),reset=Mock())
  with patch.object(b,'LIVE',live),patch.object(b,'REPLAY',None):
   state=b.State();state.native_confirmed=True;state.line(ui('spectator',at=1));self.assertTrue(state.native_confirmed);self.assertEqual(live.route,'a'*64)
