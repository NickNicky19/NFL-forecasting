"""Four NEW fictional contracts; no data, model, source or storage route."""
from copy import deepcopy
import unittest

from nfl_lab import conformal_intervals as cqr


def binding():
    out = {key: '1'*64 for key in ('source_policy_sha256', 'qualification_policy_sha256',
        'forecast_freeze_sha256', 'scored_freeze_sha256', 'query_freeze_sha256', 'qualifier_code_sha256')}
    return dict(out, base_method='leaf_cdf', qualifier='nfl_lab.cdf_evaluation._observed',
        base_out_of_sample=True, evidence_lane='EXPOSED_HISTORICAL_RECONSTRUCTION')


def rows(target='rush_att', count=4):
    return [dict(season=2022, week=i+1, game_id=f'fictional-cal-{i}', player_id='fictional-player',
        target=target, method='leaf_cdf', cutoff_utc='2022-08-01T17:00:00+00:00',
        kickoff_utc='2022-08-01T17:00:00+00:00', outcome_available_utc='2022-08-08T17:00:00+00:00',
        participation_state='played', eligible=True, primary_role=True, actual=i,
        p10=0, p90=2, fallback='fictional_original_fallback' if i == 0 else '') for i in range(count)]


def fit(data, target='rush_att'):
    return cqr.fit_radius(data, target=target, calibration_season=2022, evaluation_season=2023,
        evaluation_start_utc='2023-08-01T17:00:00+00:00', binding=binding())


def offers(target='rush_att'):
    return [dict(season=2023, week=1, game_id='fictional-eval', player_id='fictional-player',
        target=target, method='leaf_cdf', cutoff_utc='2023-08-01T17:00:00+00:00',
        kickoff_utc='2023-08-01T17:00:00+00:00', p10=0, p90=2, mean=1.2, median=1,
        primary_role=True, fallback='fictional_saved_fallback')]


class ConformalIntervalContracts(unittest.TestCase):
    def test_01_exact_upper_order_statistic_zero_support_and_insufficient_fallback(self):
        data = rows()
        fitted = fit(data)
        self.assertEqual((fitted['admitted_calibration_rows'], fitted['order_statistic_rank'], fitted['radius']), (4, 4, 1))
        self.assertEqual(fitted['supported_played_zero_rows'], 1)
        self.assertEqual(fitted['admitted_original_fallback_rows'], 1)
        self.assertTrue(fitted['all_input_rows_accounted'])
        small = fit(data[:3])
        self.assertIsNone(small['radius'])
        self.assertEqual(small['state'], 'UNCALIBRATED_FALLBACK_INSUFFICIENT_N')
        result = cqr.apply_radius(offers(), small)[0]
        self.assertEqual((result['interval_lower'], result['interval_upper']), (0, 2))

    def test_02_nonnegative_radius_signed_yards_count_floor_and_unchanged_points(self):
        interior = [{**row, 'p10': -10, 'p90': 10} for row in rows('rush_yd')]
        fitted = fit(interior, 'rush_yd')
        self.assertEqual(fitted['radius'], 0)
        negative = [{**row, 'p10': -4, 'p90': -2, 'actual': -3} for row in rows('rush_yd')]
        negative_fit = fit(negative, 'rush_yd')
        self.assertEqual(negative_fit['negative_outcome_rows'], 4)
        signed = [{**offers('rush_yd')[0], 'p10': -4, 'p90': -2}]
        original = deepcopy(signed)
        result = cqr.apply_radius(signed, negative_fit)[0]
        self.assertEqual((result['interval_lower'], result['interval_upper']), (-4, -2))
        self.assertEqual(signed, original)
        count = cqr.apply_radius(offers(), fit(rows()))[0]
        self.assertEqual((count['interval_lower'], count['interval_upper']), (0, 3))
        self.assertEqual((count['p10'], count['p90'], count['mean'], count['median']), (0, 2, 1.2, 1))
        self.assertEqual(count['fallback'], 'fictional_saved_fallback')

    def test_03_qualifier_clocks_unknown_missing_and_all_planned_rows_preserved(self):
        data = rows()
        extras = [dict(data[0], player_id=f'fictional-extra-{i}') for i in range(5)]
        extras[0].update(participation_state='unknown', eligible=False, actual=None)
        extras[1].update(participation_state='DNP', eligible=False, actual=None)
        extras[2].update(outcome_available_utc='2023-08-01T17:00:00+00:00')
        extras[3].update(outcome_available_utc=None)
        extras[4].update(p10=None)
        fitted = fit(data+extras)
        self.assertEqual((fitted['planned_calibration_rows'], fitted['admitted_calibration_rows']), (9, 4))
        self.assertEqual(sum(fitted['excluded'].values()), 5)
        with self.assertRaisesRegex(ValueError, 'eligible flag differs'):
            fit([{**data[0], 'eligible': False}])  # rejects a positive-only mask that erases zero
        with self.assertRaisesRegex(ValueError, 'fixed numeric target'):
            fit(data, 'fantasy_ppr')
        with self.assertRaisesRegex(ValueError, 'fixed numeric target'):
            fit(data, 'anytime_td')
        with self.assertRaisesRegex(ValueError, 'evaluation outcomes'):
            cqr.apply_radius([{**offers()[0], 'actual': 0}], fitted)
        with self.assertRaisesRegex(ValueError, 'radius not frozen'):
            cqr.apply_radius([{**offers()[0], 'cutoff_utc': '2023-07-31T17:00:00+00:00'}], fitted)
        second_year = [{**row, 'season': 2023, 'cutoff_utc': '2023-08-01T17:00:00+00:00',
            'kickoff_utc': '2023-08-01T17:00:00+00:00', 'outcome_available_utc': '2023-08-08T17:00:00+00:00'}
            for row in data]
        second = cqr.fit_radius(second_year, target='rush_att', calibration_season=2023, evaluation_season=2024,
            evaluation_start_utc='2024-08-01T17:00:00+00:00', binding=binding())
        self.assertEqual((second['calibration_season'], second['evaluation_season'], second['radius']), (2023, 2024, 1))

    def test_04_interval_score_missing_fallback_inversion_and_invalid_support(self):
        self.assertEqual(cqr.interval_losses(5, 1, 3),
            dict(interval_score=22., width=2, covered=0., below=0., above=1.))
        self.assertEqual(cqr.interval_losses(1, 1, 3)['interval_score'], 2)
        fitted = fit(rows())
        issued = cqr.apply_radius([{**offers()[0], 'p10': None}], fitted)
        self.assertEqual(len(issued), 1)
        self.assertIsNone(issued[0]['interval_lower'])
        self.assertEqual(issued[0]['interval_status'], 'ABSTAIN_MISSING_BASE_INTERVAL')
        for change in ({'p10': 3, 'p90': 2}, {'p10': -1}, {'p90': float('inf')}):
            with self.assertRaises(ValueError):
                cqr.apply_radius([{**offers()[0], **change}], fitted)
        with self.assertRaisesRegex(ValueError, 'duplicate calibration'):
            fit([rows()[0], rows()[0]])


if __name__ == '__main__':
    unittest.main()
