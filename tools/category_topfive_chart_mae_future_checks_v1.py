"""Twelve fictional adapter checks. No NFL sources, pickle or forest inference."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from nfl_lab import category_topfive_chart_mae_future_v1 as adapter
from nfl_lab import next_checkpoint_chart_cdf_inference as chart


def fixture():
    prior = chart.engine.SupportPrior('signed_integer', center=-100, q=.6)
    category = {'target': 'chart_lattice_002_v1', 'support': 'signed_integer',
                'panels': {'base': chart.FEATURES}, 'modeled_roles': chart.ROLES}
    model = chart.engine.LeafCDFModel(category, 'base', None,
        SimpleNamespace(estimators_=[None] * 32), np.array([-200., -100., 100.]),
        priors={'RB': prior}, global_prior=prior)
    calls = []

    def predict_batches(subset, *, batch_size, prior_only):
        calls.append((len(subset), prior_only))
        law = chart.engine.MixtureBatch([-200, -100, 100],
            np.tile([.05, .8, .15], (len(subset), 1)), prior, prior_weight=1 if prior_only else .05)
        yield np.arange(len(subset)), law, [''] * len(subset)
    model.predict_batches = predict_batches
    row = {'season': 2099, 'week': 1, 'game_id': 'FICTIONAL-GAME', 'player_id': 'FICTIONAL-PLAYER',
        'team': 'FIC', 'opponent': 'TST', 'position': 'RB',
        'cutoff_utc': '2099-10-31T16:00:00+00:00', 'kickoff_utc': '2099-10-31T18:00:00+00:00',
        'feature_max_source_available_utc': '2099-10-31T15:00:00+00:00',
        **{name: 1. for name in chart.FEATURES}}
    binding = {'adapter_version': adapter.VERSION, 'target': adapter.TARGET,
        'model_sha256': 'a' * 64, 'procedure_sha256': 'b' * 64, 'source_policy_sha256': 'c' * 64,
        'feature_schema_sha256': adapter.feature_schema_sha256(), 'source_availability_policy': 'FICTIONAL_EXPLICIT_CLOCK'}
    return model, pd.DataFrame([row]), binding, calls


def capture(candidate):
    binding = candidate['binding']
    return {'candidate_sha256': candidate['candidate_sha256'], 'identity': deepcopy(candidate['identity']),
        'target': adapter.TARGET, 'information_cutoff_utc': candidate['cutoff_utc'],
        'kickoff_utc': candidate['kickoff_utc'], 'issued_at': '2099-10-31T16:01:00+00:00',
        'issue_deadline_utc': '2099-10-31T16:30:00+00:00', 'horizon': 'FICTIONAL-T90',
        'capture_receipt_sha256': 'd' * 64,
        **{k: binding[k] for k in ['model_sha256', 'procedure_sha256', 'source_policy_sha256']}}


class Checks(unittest.TestCase):
    def setUp(self):
        self.model, self.query, self.binding, self.calls = fixture()

    def predict(self):
        return adapter.predict_chart_candidates(self.model, self.query, binding=self.binding,
            trusted_binding=deepcopy(self.binding), trusted_model_sha256='a' * 64)[0]

    def finalize(self, candidate, receipt=None, trusted=None):
        receipt = capture(candidate) if receipt is None else receipt
        return adapter.captured_chart_point(candidate, trusted_binding=self.binding,
            capture_receipt=receipt, trusted_capture_receipt=deepcopy(receipt) if trusted is None else trusted)

    def test_actual_law_bracket_scale_and_preserved_mean(self):
        c = self.predict(); v = self.finalize(c)
        self.assertEqual(c['median'], -2.)
        self.assertNotEqual(c['mean'], c['median'])
        self.assertEqual(v['expected_mean'], c['mean'])
        self.assertEqual(v['selected_projection'], c['median'])
        self.assertLess(c['functional_proof']['cdf_below'], .5)
        self.assertGreaterEqual(c['functional_proof']['cdf_at'], .5)
        self.assertEqual(self.calls, [(1, False)])
        self.assertFalse(v['new_probability_or_EV_claim'])

    def test_wrong_restored_model_hash_before_prediction(self):
        with self.assertRaises(ValueError):
            adapter.predict_chart_candidates(self.model, self.query, binding=self.binding,
                trusted_binding=self.binding, trusted_model_sha256='0' * 64)
        self.assertEqual(self.calls, [])

    def test_wrong_independent_source_binding_before_prediction(self):
        wrong = deepcopy(self.binding); wrong['source_policy_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            adapter.predict_chart_candidates(self.model, self.query, binding=wrong,
                trusted_binding=self.binding, trusted_model_sha256='a' * 64)
        self.assertEqual(self.calls, [])

    def test_equal_source_cutoff_rejected_before_prediction(self):
        self.query.loc[0, 'feature_max_source_available_utc'] = self.query.loc[0, 'cutoff_utc']
        with self.assertRaises(ValueError): self.predict()
        self.assertEqual(self.calls, [])

    def test_late_information_cutoff_rejected(self):
        self.query.loc[0, 'cutoff_utc'] = '2099-10-31T19:00:00+00:00'
        with self.assertRaises(ValueError): self.predict()
        self.assertEqual(self.calls, [])

    def test_cold_prior_identity_and_chart_scale_preserved(self):
        self.query.loc[0, 'f_player_games_prior'] = 0
        c = self.predict(); v = self.finalize(c)
        self.assertEqual(c['median'], -2.)
        self.assertEqual(c['mean'], -2.)
        self.assertTrue(v['fallback'])
        self.assertEqual(v['original_contract_version'], chart.VERSION)
        self.assertEqual(v['scoring_target'], adapter.TARGET)
        self.assertEqual(self.calls, [(1, True)])

    def test_unknown_clock_forces_real_prior_fallback(self):
        self.query.loc[0, 'feature_max_source_available_utc'] = None
        v = self.finalize(self.predict())
        self.assertEqual(v['fallback_reason'], 'unknown_feature_clock_position_prior')
        self.assertEqual(self.calls, [(1, True)])

    def test_tampered_bracket_cannot_invent_capture(self):
        c = self.predict(); c['functional_proof']['cdf_below'] = .5
        with self.assertRaises(ValueError): self.finalize(c)

    def test_capture_identity_mismatch_rejected(self):
        c = self.predict(); receipt = capture(c); trusted = deepcopy(receipt)
        receipt['identity']['player_id'] = 'DIFFERENT-FICTIONAL-PLAYER'
        with self.assertRaises(ValueError): self.finalize(c, receipt, trusted)

    def test_late_issuance_rejected_after_capture_binding(self):
        c = self.predict(); receipt = capture(c); receipt['issued_at'] = receipt['issue_deadline_utc']
        with self.assertRaises(ValueError): self.finalize(c, receipt)

    def test_missing_durable_capture_hash_rejected(self):
        c = self.predict(); receipt = capture(c); receipt['capture_receipt_sha256'] = ''
        with self.assertRaises(ValueError): self.finalize(c, receipt)

    def test_old_ppr_contract_cannot_be_relabeled(self):
        self.binding['target'] = 'fantasy_ppr'
        with self.assertRaises(ValueError): self.predict()
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
