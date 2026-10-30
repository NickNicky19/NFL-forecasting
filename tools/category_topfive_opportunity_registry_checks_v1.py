"""Bounded fictional registry checks; no NFL data, models or network."""
from pathlib import Path
import copy
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfl_lab.category_topfive_opportunity_registry import VERSION, SCORE_NAMES, score, validate, leaderboard


def fixture():
    methods = [{'method_id': 'm:a', 'original_id': 'original-a', 'family': 'fictionalCDF', 'procedure_version': '1', 'algorithm': 'fictional', 'formula': 'fixture', 'outputs': [{'output_id': 'median', 'functional': 'median'}, {'output_id': 'mean', 'functional': 'mean'}, {'output_id': 'law', 'functional': 'distribution', 'primary_score': 'log_loss'}], 'code': [], 'feature_policy': 'earlier-only', 'training_rule': 'frozen', 'aliases': []}]
    experiments = [{'experiment_id': 'e:a', 'request_id': 'owner-fixture', 'method_ids': ['m:a'], 'hypothesis': 'fictional', 'history_policy': 'frozen', 'sources': [], 'population': {}, 'cutoff': 'earlier-only', 'budget': {}, 'status': 'COMPLETED', 'registration': {'record': 'fixture/protocol'}, 'owner': 'fixture'}]
    runs = [{'run_record_id': 'r:a@1', 'run_id': 'r:a', 'run_version': 1, 'supersedes_run_record_id': None, 'experiment_id': 'e:a', 'original_id': 'original-run', 'status': 'COMPLETED', 'origin': 'IMPORTED', 'start': {'record': None}, 'finish': {'record': 'fixture/completion'}, 'resources': {}, 'software_checks': [], 'evidence': {'original_record': 'fixture/source'}, 'publication_subject': 'r:a'}]
    result = {'result_id': 'y:a', 'run_id': 'r:a', 'method_id': 'm:a', 'output_id': 'median', 'comparison': {'target': 'rec_tgt', 'season': 2026, 'weeks': [1, 2], 'population_id': 'same-receivers', 'outcome_version': 'provider-v1', 'horizon_id': 'frozen', 'source_policy_id': 'policy-v1', 'fallback_policy_id': 'prior-v1', 'evidence_kind': 'reconstruction', 'comparison_set_id': 'fixture'}, 'scores': {n: score(2.0) if n == 'MAE' else score() for n in SCORE_NAMES}, 'coverage': {'planned': 10, 'scored': 8, 'games': 2, 'weeks': 2}, 'evidence_label': 'REPORTED_NOT_REPRODUCED', 'validity': 'VALID', 'missingness': {}, 'comparator': {}, 'uncertainty': {}, 'adverse': [], 'private_evidence': {'state': 'REDACTED'}, 'readiness': 'NOT_OPERATIONALLY_ADMITTED', 'source_record': 'fixture/source'}
    pubs = [{'publication_id': 'p:1', 'subjects': ['y:a', 'y:b', 'y:c'], 'state': 'PUBLICATION_COMPLETE', 'commit': 'a'*40, 'readback_record': 'fixture/readback'}]
    return {'schema_version': VERSION, 'methods': methods, 'experiments': experiments, 'runs': runs, 'results': [result], 'publications': pubs}


class RegistryChecks(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(fixture())['results'], 1)

    def test_duplicate_id(self):
        r = fixture(); r['methods'] *= 2
        with self.assertRaises(ValueError): validate(r)

    def test_required_metadata(self):
        r = fixture(); del r['experiments'][0]['history_policy']
        with self.assertRaises(ValueError): validate(r)

    def test_missing_run(self):
        r = fixture(); r['results'][0]['run_id'] = 'missing'
        with self.assertRaises(ValueError): validate(r)

    def test_unregistered_method_for_run(self):
        r = fixture(); r['experiments'][0]['method_ids'] = []
        with self.assertRaises(ValueError): validate(r)

    def test_missing_score_reason(self):
        r = fixture(); r['results'][0]['scores']['MSE']['reason'] = ''
        with self.assertRaises(ValueError): validate(r)

    def test_raw_nan(self):
        r = fixture(); r['results'][0]['scores']['MAE']['value'] = float('nan')
        with self.assertRaises(ValueError): validate(r)

    def test_infinity_retained(self):
        r = fixture(); a = r['results'][0]; a['output_id'] = 'law'; a['scores']['log_loss'] = score(float('inf'), 'Impossible event remains in the paired population')
        z = leaderboard(r)['panels']; self.assertEqual(z[0]['top_up_to5'][0]['loss_state'], 'POSITIVE_INFINITY')

    def test_nonfinite_null_and_reason(self):
        r = fixture(); r['results'][0]['scores']['log_loss'] = {'state': 'POSITIVE_INFINITY', 'value': 0, 'reason': 'bad'}
        with self.assertRaises(ValueError): validate(r)

    def test_denominator(self):
        r = fixture(); r['results'][0]['coverage']['scored'] = 0
        with self.assertRaises(ValueError): validate(r)

    def test_different_population_rejected(self):
        r = fixture(); b = copy.deepcopy(r['results'][0]); b['result_id'] = 'y:b'; b['coverage']['scored'] = 7; r['results'].append(b)
        with self.assertRaises(ValueError): validate(r)

    def test_different_years_separate(self):
        r = fixture(); b = copy.deepcopy(r['results'][0]); b['result_id'] = 'y:b'; b['comparison']['season'] = 2025; r['results'].append(b)
        self.assertEqual(len(leaderboard(r)['panels']), 2)

    def test_two_outputs_one_procedure(self):
        r = fixture(); b = copy.deepcopy(r['results'][0]); b['result_id'] = 'y:b'; b['output_id'] = 'mean'; b['scores']['MAE'] = score(1.5); b['scores']['MSE'] = score(4); r['results'].append(b)
        panels = leaderboard(r)['panels']; point = next(p for p in panels if p['objective'] == 'point_MAE'); mean = next(p for p in panels if p['objective'] == 'expected_mean_MSE')
        self.assertEqual(point['distinct_procedures'], 1); self.assertEqual(point['top_up_to5'][0]['functional'], 'mean'); self.assertEqual(mean['top_up_to5'][0]['loss'], 4)

    def test_unavailable_not_zero(self):
        r = fixture(); r['results'][0]['scores']['MAE'] = score(None, 'No forecast')
        self.assertEqual(leaderboard(r)['panels'], [])

    def test_private_location(self):
        r = fixture(); r['results'][0]['source_record'] = '/workspace/private/file'
        with self.assertRaises(ValueError): validate(r)

    def test_restricted_rows(self):
        r = fixture(); r['results'][0]['player_id'] = 'forbidden'
        with self.assertRaises(ValueError): validate(r)

    def test_secret(self):
        r = fixture(); r['results'][0]['source_record'] = 'ghp_'+'a'*30
        with self.assertRaises(ValueError): validate(r)

    def test_invalidated_visible_not_ranked(self):
        r = fixture(); r['results'][0]['validity'] = 'INVALIDATED'
        self.assertEqual(len(r['results']), 1); self.assertEqual(leaderboard(r)['panels'], [])

    def test_correction_append(self):
        r = fixture(); b = copy.deepcopy(r['results'][0]); b.update(result_id='y:b', supersedes_result_id='y:a', correction_reason='Evaluator repair'); b['scores']['MAE'] = score(3); r['results'].append(b)
        self.assertEqual(leaderboard(r)['panels'][0]['top_up_to5'][0]['loss'], 3); self.assertEqual(len(r['results']), 2)

    def test_publication_pending(self):
        r = fixture(); r['publications'][0]['state'] = 'PUBLICATION_PENDING'
        self.assertEqual(leaderboard(r)['panels'], [])

    def test_publication_proof(self):
        r = fixture(); r['publications'][0]['readback_record'] = None
        with self.assertRaises(ValueError): validate(r)

    def test_launched_requires_start(self):
        r = fixture(); r['runs'][0]['origin'] = 'EXECUTED_HERE'
        with self.assertRaises(ValueError): validate(r)

    def test_terminal_requires_finish(self):
        r = fixture(); r['runs'][0]['origin'] = 'EXECUTED_HERE'; r['runs'][0]['start']['record'] = 'fixture/start'; r['runs'][0]['finish']['record'] = None
        with self.assertRaises(ValueError): validate(r)

    def test_append_run_versions(self):
        r = fixture(); a = r['runs'][0]; a.update(origin='EXECUTED_HERE', status='RUNNING', start={'record': 'fixture/start'}, finish={'record': None}); b = copy.deepcopy(a); b.update(run_record_id='r:a@2', run_version=2, supersedes_run_record_id='r:a@1', status='COMPLETED', finish={'record': 'fixture/finish'}); r['runs'].append(b)
        self.assertEqual(validate(r)['runs'], 1)

    def test_broken_run_version(self):
        r = fixture(); r['runs'][0]['run_version'] = 2
        with self.assertRaises(ValueError): validate(r)

    def test_nonfocus_result(self):
        r = fixture(); r['results'][0]['comparison']['target'] = 'pass_cmp'
        with self.assertRaises(ValueError): validate(r)

    def test_infinite_zero_denominator(self):
        r = fixture(); a = r['results'][0]; a['scores'] = {n: score() for n in SCORE_NAMES}; a['scores']['log_loss'] = score(float('inf'), 'Impossible event'); a['coverage']['scored'] = 0
        with self.assertRaises(ValueError): validate(r)

    def test_private_dictionary_key(self):
        r = fixture(); r['results'][0]['private_evidence']['/workspace/private'] = 'hidden'
        with self.assertRaises(ValueError): validate(r)

    def test_credential_dictionary_key(self):
        r = fixture(); r['results'][0]['private_evidence']['ODDS_API_KEY'] = 'fake_fixture_value'
        with self.assertRaises(ValueError): validate(r)

    def test_self_correction(self):
        r = fixture(); r['results'][0].update(supersedes_result_id='y:a', correction_reason='bad')
        with self.assertRaises(ValueError): validate(r)

    def test_cyclic_correction(self):
        r = fixture(); b = copy.deepcopy(r['results'][0]); b.update(result_id='y:b', supersedes_result_id='y:a', correction_reason='cycle'); r['results'][0].update(supersedes_result_id='y:b', correction_reason='cycle'); r['results'].append(b)
        with self.assertRaises(ValueError): validate(r)

    def test_changed_output_correction(self):
        r = fixture(); b = copy.deepcopy(r['results'][0]); b.update(result_id='y:b', output_id='mean', supersedes_result_id='y:a', correction_reason='changedproduct'); r['results'].append(b)
        with self.assertRaises(ValueError): validate(r)

    def test_invalid_coverage(self):
        r = fixture(); r['results'][0]['coverage']['scored'] = 11
        with self.assertRaises(ValueError): validate(r)

    def test_invalid_publication_commit(self):
        r = fixture(); r['publications'][0]['commit'] = 'main'
        with self.assertRaises(ValueError): validate(r)

    def test_missing_functional(self):
        r = fixture(); del r['methods'][0]['outputs'][0]['functional']
        with self.assertRaises(ValueError): validate(r)

    def test_probability_not_MAE(self):
        r = fixture(); r['methods'][0]['outputs'][0].update(functional='probability', primary_score='MAE')
        with self.assertRaises(ValueError): validate(r)

    def grouped_fixture(self):
        r = fixture()
        b = copy.deepcopy(r['methods'][0]); b.update(method_id='m:b', original_id='original-b')
        for m in (r['methods'][0], b): m.update(shortlist_group='related-fixture', shortlist_group_reason='Same family parameter controls; no padding')
        r['methods'].append(b); r['experiments'][0]['method_ids'].append('m:b')
        y = copy.deepcopy(r['results'][0]); y.update(result_id='y:b', method_id='m:b'); y['scores']['MAE'] = score(3.)
        r['results'].append(y)
        return r

    def test_group_requires_reason(self):
        r = fixture(); r['methods'][0]['shortlist_group'] = 'related'
        with self.assertRaises(ValueError): validate(r)

    def test_group_preserves_losing_members(self):
        r = self.grouped_fixture(); p = leaderboard(r)['panels'][0]
        self.assertEqual(p['distinct_procedures'], 2); self.assertEqual(p['shortlist_groups'], 1)
        self.assertEqual(p['top_up_to5'][0]['grouped_method_ids'], ['m:a', 'm:b'])
        self.assertEqual(p['top_up_to5'][0]['grouped_results'][1]['loss'], 3.)

    def test_group_does_not_mix_seasons(self):
        r = self.grouped_fixture(); r['results'][1]['comparison']['season'] = 2025
        self.assertEqual(len(leaderboard(r)['panels']), 2)

    def test_group_does_not_mix_population(self):
        r = self.grouped_fixture(); r['results'][1]['comparison']['population_id'] = 'other'
        self.assertEqual(len(leaderboard(r)['panels']), 2)

    def test_group_selects_lower_loss(self):
        r = self.grouped_fixture(); r['results'][1]['scores']['MAE'] = score(1.)
        self.assertEqual(leaderboard(r)['panels'][0]['top_up_to5'][0]['method_id'], 'm:b')

    def test_group_tie_stable_id(self):
        r = self.grouped_fixture(); r['results'][1]['scores']['MAE'] = score(2.)
        r['results'].reverse(); self.assertEqual(leaderboard(r)['panels'][0]['top_up_to5'][0]['method_id'], 'm:a')

    def test_group_respects_panel_admission(self):
        r = self.grouped_fixture()
        for m in r['methods']: m['shortlist_group_panels'] = ['other-panel']
        self.assertEqual(leaderboard(r)['panels'][0]['shortlist_groups'], 2)

    def test_group_panel_string_rejected(self):
        r = self.grouped_fixture(); r['methods'][0]['shortlist_group_panels'] = 'fixture'
        with self.assertRaises(ValueError): validate(r)

    def test_unstarted_cancellation_keeps_missing_start(self):
        r = fixture(); r['results'] = []; a = r['runs'][0]
        a.update(origin='EXECUTED_HERE', status='CANCELED', start={'record': None, 'reason': 'Never launched'}, finish={'record': 'fixture/cancellation', 'reason': 'Registration alias corrected before execution'})
        self.assertEqual(validate(r)['runs'], 1)

    def test_unstarted_cancellation_needs_reason(self):
        r = fixture(); r['results'] = []; a = r['runs'][0]
        a.update(origin='EXECUTED_HERE', status='CANCELED', start={'record': None}, finish={'record': 'fixture/cancellation'})
        with self.assertRaises(ValueError): validate(r)

    def test_unstarted_cancellation_cannot_score(self):
        r = fixture(); a = r['runs'][0]
        a.update(origin='EXECUTED_HERE', status='CANCELED', start={'record': None}, finish={'record': 'fixture/cancellation', 'reason': 'Not launched'})
        with self.assertRaises(ValueError): validate(r)


if __name__ == '__main__':
    unittest.main(verbosity=2)
