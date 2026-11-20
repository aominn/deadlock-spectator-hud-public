import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from midboss_timer import MidbossTimeline
import effect_bridge


class MidbossTimerTests(unittest.TestCase):
    def test_exact_clock_and_safe_lookup_after_seek(self):
        timer = MidbossTimeline({'schema': 1, 'updates': [[0, 0], [2137, 2556.75], [2438, 0]]})
        self.assertEqual(timer.remaining(2298), 259)
        self.assertEqual(timer.remaining(2298), 259)
        self.assertIsNone(timer.remaining(2136))
        self.assertEqual(timer.remaining(2137), 420)
        self.assertIsNone(timer.remaining(2438))
        self.assertIsNone(timer.remaining(2500))

    def test_live_sample_does_not_predict_earlier_frames(self):
        timer = MidbossTimeline({'schema': 1, 'updates': [[2298, 2556.75]]})
        self.assertIsNone(timer.remaining(2297))
        self.assertEqual(timer.remaining(2298), 259)
        self.assertEqual(timer.remaining(2556), 1)
        self.assertIsNone(timer.remaining(2557))

    def test_legacy_invalid_or_ambiguous_data_is_inert(self):
        for data in (None, {'schema': 2, 'updates': [[1, 20]]},
                     {'schema': 1, 'updates': [[1, 20], [1, 23]]},
                     {'schema': 1, 'updates': [[1, float('nan')]]},
                     {'schema': 1, 'updates': [[1, 10000]]},
                     {'schema': 1, 'updates': [[True, 23]]}):
            with self.subTest(data=data):
                self.assertIsNone(MidbossTimeline(data).remaining(10))

    def test_overlay_requires_current_native_clock_and_source(self):
        stamp = 200
        state = SimpleNamespace(lock=effect_bridge.threading.RLock(), last_clock=2298,
                                last_http=stamp, native_confirmed=True, postgame=False,
                                midboss_remaining=259)
        ready = SimpleNamespace(bound=True)
        call = effect_bridge.midboss_image
        blank = effect_bridge.midboss_png(None)
        with (patch.object(effect_bridge, 'S', state),
              patch.object(effect_bridge, 'REPLAY', ready),
              patch.object(effect_bridge, 'LIVE', None),
              patch.object(effect_bridge.time, 'monotonic', return_value=stamp),
              patch.object(effect_bridge, 'stats_scope', return_value=('replay',))):
            self.assertEqual(call({'clock': ['2298']}), effect_bridge.midboss_png(259))
            self.assertEqual(call({'clock': ['2297']}), blank)
            self.assertEqual(call({'clock': ['2298', '2298']}), blank)
            ready.bound = False
            self.assertEqual(call({'clock': ['2298']}), blank)
            ready.bound = True
            state.native_confirmed = False
            self.assertEqual(call({'clock': ['2298']}), blank)
