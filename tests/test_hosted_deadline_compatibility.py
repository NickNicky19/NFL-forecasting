"""Fictional timer compatibility only: no HTTP, credentials, NFL or models."""
import hashlib
from pathlib import Path
import signal
import time
import unittest

from nfl_lab import private_draft_store as store


class HostedDeadlineCompatibility(unittest.TestCase):
    def setUp(self):
        self.started = time.monotonic()
        self.original_timer = signal.getitimer(signal.ITIMER_REAL)
        self.original_handler = signal.getsignal(signal.SIGALRM)
        signal.setitimer(signal.ITIMER_REAL, 0)

    def tearDown(self):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.original_handler)
        remaining, interval = self.original_timer
        if remaining:
            remaining = max(.001, remaining - (time.monotonic() - self.started))
        signal.setitimer(signal.ITIMER_REAL, remaining, interval)

    def test_frozen_transport_is_unchanged(self):
        body = Path(store.__file__).read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),
            'b159c47b1c77321f8a46935db33a7c2289d5a625c493223958fd00fb3f92950f')

    def test_old_custom_handler_rejects_before_transport(self):
        signal.signal(signal.SIGALRM, lambda *_: None)
        signal.setitimer(signal.ITIMER_REAL, 1200)
        entered = False
        with self.assertRaisesRegex(store.StoreError, '^WALL_GUARD_REQUIRED$'):
            with store.exchange_deadline(True):
                entered = True
        self.assertFalse(entered)

    def test_default_hard_alarm_preserves_whole_and_exchange_bounds(self):
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.setitimer(signal.ITIMER_REAL, 1200)
        with store.exchange_deadline(True):
            remaining, interval = signal.getitimer(signal.ITIMER_REAL)
            self.assertGreater(remaining, 0)
            self.assertLessEqual(remaining, 20)
            self.assertEqual(interval, 0)
            self.assertEqual(signal.getsignal(signal.SIGALRM), signal.SIG_DFL)
        remaining, interval = signal.getitimer(signal.ITIMER_REAL)
        self.assertGreater(remaining, 1190)
        self.assertLessEqual(remaining, 1200)
        self.assertEqual(interval, 0)


if __name__ == '__main__':
    unittest.main()
