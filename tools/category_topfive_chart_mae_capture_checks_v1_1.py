"""Four new fictional persistence checks; original V1 cases remain unchanged."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfl_lab import category_topfive_chart_mae_future_v1_1 as adapter
from tools.category_topfive_chart_mae_future_checks_v1 import fixture, capture


class CaptureChecks(unittest.TestCase):
    def setUp(self):
        self.model, self.query, self.binding, self.calls = fixture()
        self.binding['adapter_version'] = adapter.VERSION
        self.candidate = adapter.predict_chart_candidates(self.model, self.query,
            binding=self.binding, trusted_binding=deepcopy(self.binding),
            trusted_model_sha256='a' * 64)[0]
        self.receipt = capture(self.candidate)
        self.receipt.update(state='FROZEN_AND_READ_BACK', horizon='player_game',
            persistence_completed_at='2099-10-31T16:02:00+00:00',
            readback_completed_at='2099-10-31T16:31:00+00:00')

    def finalize(self, receipt):
        return adapter.captured_chart_point(self.candidate, trusted_binding=self.binding,
            capture_receipt=receipt, trusted_capture_receipt=deepcopy(receipt))

    def test_valid_timed_capture_preserves_mean_and_allows_later_readback(self):
        view = self.finalize(self.receipt)
        self.assertEqual(view['expected_mean'], self.candidate['mean'])
        self.assertEqual(view['selected_projection'], self.candidate['median'])
        self.assertEqual(view['capture_state'], 'FROZEN_AND_READ_BACK')
        self.assertEqual(view['persistence_completed_at'], self.receipt['persistence_completed_at'])
        self.assertEqual(view['readback_completed_at'], self.receipt['readback_completed_at'])
        self.assertGreater(self.receipt['readback_completed_at'], self.receipt['issue_deadline_utc'])
        self.assertEqual(self.calls, [(1, False)])

    def test_persistence_at_deadline_rejected(self):
        self.receipt['persistence_completed_at'] = self.receipt['issue_deadline_utc']
        with self.assertRaises(ValueError): self.finalize(self.receipt)

    def test_malformed_or_unreadback_receipt_rejected(self):
        variants = [dict(state='FROZEN'), dict(readback_completed_at=None),
                    dict(persistence_completed_at='2099-10-31T16:02:00'),
                    dict(readback_completed_at='2099-10-31T16:00:00+00:00')]
        for change in variants:
            with self.subTest(change=change):
                receipt = deepcopy(self.receipt); receipt.update(change)
                with self.assertRaises(ValueError): self.finalize(receipt)

    def test_wrong_horizon_rejected(self):
        self.receipt['horizon'] = 'FICTIONAL-T90'
        with self.assertRaises(ValueError): self.finalize(self.receipt)


if __name__ == '__main__':
    unittest.main()
