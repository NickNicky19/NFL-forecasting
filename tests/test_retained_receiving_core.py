"""Synthetic cases only: no actual NFL forecasts, outcomes or validation scores."""
import copy
import unittest
from decimal import Decimal
from nfl_lab.retained.receiving_yards_core_draft import evaluate_core


def fixture():
    c = dict(player_id='fictional-player', game_id='fictional-future', team='A', opponent='B',
             season=2000, week=7, period='full_game_with_ot', cutoff_at='2000-10-22T12:00:00Z',
             kickoff_at='2000-10-22T17:00:00Z', projection_observed_at='2000-10-22T11:00:00Z',
             website_yards=40.5, projected_targets=6.0, projection_source_ref='fictional-projection')
    h=[]
    for week, day, targets, yards in [(6,15,10,100),(5,8,2,10),(4,1,8,50)]:
        h.append(dict(player_id=c['player_id'], game_id=f'fictional-{week}', team='A', opponent='B',
                      season=2000,week=week,period=c['period'], ended_at=f'2000-10-{day:02}T20:00:00Z',
                      stats_observed_at=f'2000-10-{day:02}T22:00:00Z',participation='played',
                      targets=targets,yards=yards,source_ref=f'fictional-source-{week}'))
    return c,h


class CoreTests(unittest.TestCase):
    def test_pooled_not_mean_of_ratios(self):
        c,h=fixture(); self.assertEqual(evaluate_core(c,h).value,Decimal('48'))
    def test_fractional_target_projection(self):
        c,h=fixture(); c['projected_targets']=Decimal('6.25'); self.assertEqual(evaluate_core(c,h).value,Decimal('50'))
    def test_supported_zero_projection(self):
        c,h=fixture(); c['projected_targets']=0; self.assertEqual(evaluate_core(c,h).value,0)
    def test_negative_yards_allowed(self):
        c,h=fixture()
        for r in h:r['yards']=-10
        self.assertEqual(evaluate_core(c,h).value,Decimal('-9'))
    def test_zero_target_prior_with_yards_not_silently_zeroed(self):
        c,h=fixture();h[0]['targets']=0; self.assertEqual(evaluate_core(c,h).value,Decimal('96'))
    def test_zero_denominator_uses_unchanged_signed_baseline(self):
        c,h=fixture();c['website_yards']=-2.5
        for r in h:r['targets']=0
        r=evaluate_core(c,h);self.assertEqual(r.value,Decimal('-2.5'));self.assertEqual(r.state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_no_input_mutation(self):
        c,h=fixture();before=copy.deepcopy((c,h));evaluate_core(c,h);self.assertEqual((c,h),before)
    def test_wrong_player(self):self._history_failure('player_id','other')
    def test_wrong_team(self):self._history_failure('team','C')
    def test_wrong_period(self):self._history_failure('period','first_half')
    def test_wrong_season(self):self._history_failure('season',1999)
    def test_target_week_history(self):self._history_failure('week',7)
    def test_target_game_history(self):self._history_failure('game_id','fictional-future')
    def test_duplicate_game(self):
        c,h=fixture();h[1]['game_id']=h[0]['game_id'];self.assertEqual(evaluate_core(c,h).state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_wrong_order(self):
        c,h=fixture();h.reverse();self.assertEqual(evaluate_core(c,h).state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_unknown_participation(self):self._history_failure('participation','unknown')
    def test_dnp_not_a_selected_appearance(self):self._history_failure('participation','dnp')
    def test_null_targets(self):self._history_failure('targets',None)
    def test_boolean_targets(self):self._history_failure('targets',True)
    def test_negative_targets(self):self._history_failure('targets',-1)
    def test_fractional_historical_targets(self):self._history_failure('targets',2.5)
    def test_missing_yards(self):
        c,h=fixture();del h[0]['yards'];self.assertEqual(evaluate_core(c,h).state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_null_yards(self):self._history_failure('yards',None)
    def test_nan_yards(self):self._history_failure('yards',float('nan'))
    def test_fractional_historical_yards(self):self._history_failure('yards',0.5)
    def test_missing_source_ref(self):self._history_failure('source_ref','')
    def test_missing_opponent(self):self._history_failure('opponent','')
    def test_naive_historical_time(self):self._history_failure('ended_at','2000-10-15T20:00:00')
    def test_future_historical_availability(self):self._history_failure('stats_observed_at','2000-10-22T12:00:01Z')
    def test_stats_before_game_ended(self):self._history_failure('stats_observed_at','2000-10-15T19:00:00Z')
    def test_short_history(self):
        c,h=fixture();self.assertEqual(evaluate_core(c,h[:2]).state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_extra_history_not_searched(self):
        c,h=fixture();self.assertEqual(evaluate_core(c,h+h[:1]).state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_null_target_projection(self):
        c,h=fixture();c['projected_targets']=None;self.assertEqual(evaluate_core(c,h).state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_string_projection_rejected(self):
        c,h=fixture();c['projected_targets']='6';self.assertEqual(evaluate_core(c,h).state,'UNCHANGED_WEBSITE_FALLBACK')
    def test_no_baseline_no_invented_fallback(self):self._context_abstain('website_yards',None)
    def test_no_target_identity(self):self._context_abstain('game_id','')
    def test_naive_cutoff(self):self._context_abstain('cutoff_at','2000-10-22T12:00:00')
    def test_cutoff_at_kickoff(self):self._context_abstain('cutoff_at','2000-10-22T17:00:00Z')
    def test_late_original_projection(self):self._context_abstain('projection_observed_at','2000-10-22T12:00:01Z')
    def test_timezone_equivalence(self):
        c,h=fixture();c['cutoff_at']='2000-10-22T07:00:00-05:00';self.assertEqual(evaluate_core(c,h).value,48)
    def test_evidence_label_does_not_claim_source_qualification(self):
        c,h=fixture();r=evaluate_core(c,h);self.assertIn('NOT_SOURCE_QUALIFIED',r.evidence_tier)
    def _history_failure(self,k,v):
        c,h=fixture();h[0][k]=v;r=evaluate_core(c,h);self.assertEqual(r.state,'UNCHANGED_WEBSITE_FALLBACK');self.assertEqual(r.value,Decimal('40.5'))
    def _context_abstain(self,k,v):
        c,h=fixture();c[k]=v;r=evaluate_core(c,h);self.assertEqual(r.state,'ABSTAIN');self.assertIsNone(r.value)

if __name__ == '__main__': unittest.main(verbosity=2)
