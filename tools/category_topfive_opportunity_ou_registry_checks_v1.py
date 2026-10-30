"""One fictional mutation suite for public O/U linkage and denominator checks."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfl_lab.category_topfive_opportunity_ou_registry import validate, generated
from nfl_lab.category_topfive_opportunity_registry import load

ROOT = Path(__file__).resolve().parents[1]/'reports/opportunity-four'


class Checks(unittest.TestCase):
    def setUp(self):
        self.a = json.loads((ROOT/'over-under/OVER_UNDER_RESULTS.json').read_bytes())
        self.p = json.loads((ROOT/'over-under/OVER_UNDER_POLICY_REGISTRY.json').read_bytes())
        self.i = json.loads((ROOT/'over-under/RESULT_INDEX.json').read_bytes())
        self.r = load(ROOT)

    def check(self):
        return validate(self.a, self.p, self.i, self.r)

    def test_actual_public_links(self):
        self.assertEqual(self.check()['season_summaries'], 180)

    def test_missing_run(self):
        self.i['run_id'] = 'not-launched'
        with self.assertRaises(ValueError): self.check()

    def test_run_not_complete(self):
        next(r for r in reversed(self.r['runs']) if r['run_id'] == self.i['run_id'])['status'] = 'RUNNING'
        with self.assertRaises(ValueError): self.check()

    def test_wrong_experiment(self):
        self.i['experiment_id'] = 'unregistered'
        with self.assertRaises(ValueError): self.check()

    def test_timing_upgrade(self):
        self.i['evidence_tier'] = 'AUTHENTIC_PREGAME'
        with self.assertRaises(ValueError): self.check()

    def test_missing_side_policy(self):
        self.p['rules'] = []
        with self.assertRaises(ValueError): self.check()

    def test_duplicate_summary(self):
        self.a['summaries'].append(copy.deepcopy(self.a['summaries'][0]))
        with self.assertRaises(ValueError): self.check()

    def test_wrong_count(self):
        self.a['summaries'][0]['statistical_status_counts']['CORRECT'] += 1
        with self.assertRaises(ValueError): self.check()

    def test_fake_book_win(self):
        self.a['summaries'][0]['book_settlement_counts']['WIN'] = 1
        self.a['summaries'][0]['book_settlement_counts']['UNRESOLVED'] -= 1
        with self.assertRaises(ValueError): self.check()

    def test_fake_target_offer(self):
        self.a['summaries'][0]['target'] = 'rec_tgt'
        with self.assertRaises(ValueError): self.check()

    def test_null_not_zero_error(self):
        self.a['summaries'][0]['point_MAE'] = 0
        with self.assertRaises(ValueError): self.check()

    def test_infinite_logloss_keeps_denominator(self):
        x = next(r for r in self.a['summaries'] if r['Brier_rows'] > 0)['log_loss_decisive']
        x.update(state='POSITIVE_INFINITY', value=None, impossible_events=1)
        self.check()
        x['denominator'] = 0
        with self.assertRaises(ValueError): self.check()

    def test_missing_week(self):
        self.a['weekly']['rows'].pop()
        with self.assertRaises(ValueError): self.check()

    def test_paper_upgrade(self):
        self.a['original_paper_exploratory'][0]['actual_book_settlement'] = 'QUALIFIED'
        with self.assertRaises(ValueError): self.check()

    def test_rank_population_mismatch(self):
        next(r for r in self.a['summaries'] if r['pool'] == 'P1_COMMON_ORIGINAL_OFFER_RULE' and r['point_MAE'] is not None)['point_rows'] += 1
        with self.assertRaises(ValueError): generated(self.a)

    def test_private_extension_content(self):
        self.a['limitations'].append('/workspace/private/forbidden')
        with self.assertRaises(ValueError): self.check()

    def test_restricted_key(self):
        self.i['player_id'] = 'fictional'
        with self.assertRaises(ValueError): self.check()

    def test_side_book_win(self):
        self.a['summaries'][0]['by_selected_side']['over']['book_settlement_counts']['WIN'] = 1
        self.a['summaries'][0]['by_selected_side']['over']['book_settlement_counts']['UNRESOLVED'] -= 1
        with self.assertRaises(ValueError): self.check()

    def test_extra_side(self):
        self.a['summaries'][0]['by_selected_side']['fictional'] = {}
        with self.assertRaises(ValueError): self.check()

    def test_supported_population_mismatch(self):
        self.a['summaries'][0]['supported_statistic_rows'] = 0
        with self.assertRaises(ValueError): self.check()

    def test_binary_brier_outside_support(self):
        next(r for r in self.a['summaries'] if r['Brier_decisive'] is not None)['Brier_decisive'] = 1.01
        with self.assertRaises(ValueError): self.check()

    def test_boolean_log_loss(self):
        next(r for r in self.a['summaries'] if r['log_loss_decisive']['state'] == 'FINITE')['log_loss_decisive']['value'] = True
        with self.assertRaises(ValueError): self.check()

    def test_empty_generated_panel(self):
        self.a['summaries'] = []
        leaders, _ = generated(self.a)
        self.assertEqual(leaders['panels'][0]['rows'], 0)

    def test_weekly_bad_denominator(self):
        self.a['weekly']['rows'][0][6] += 1
        with self.assertRaises(ValueError): self.check()

    def test_duplicate_weekly(self):
        self.a['weekly']['rows'][1] = list(self.a['weekly']['rows'][0])
        with self.assertRaises(ValueError): self.check()

    def test_duplicate_paired(self):
        self.a['paired_contrasts'][1] = copy.deepcopy(self.a['paired_contrasts'][0])
        with self.assertRaises(ValueError): self.check()

    def test_proper_score_population_mismatch(self):
        next(r for r in self.a['summaries'] if r['Brier_rows'] > 0)['log_loss_decisive']['denominator'] -= 1
        with self.assertRaises(ValueError): self.check()

    def test_wrong_weekly_width(self):
        self.a['weekly']['rows'][0].append(1)
        with self.assertRaises(ValueError): self.check()

    def test_weekly_probability_without_supported_labels(self):
        x = next(r for r in self.a['weekly']['rows'] if r[13] > 0)
        x[6:11] = [0, 0, 0, 0, x[5]]
        with self.assertRaises(ValueError): self.check()

    def test_paired_clusters_exceed_rows(self):
        self.a['paired_contrasts'][0]['game']['paired_rows'] = 0
        with self.assertRaises(ValueError): self.check()


if __name__ == '__main__':
    unittest.main()
