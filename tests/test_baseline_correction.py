"""Fictional software checks; these fixtures contain no NFL observations."""
import json
import unittest

import numpy as np
import pandas as pd

from nfl_lab.baseline_correction import (BaselineCorrection, CorrectionDesign,
    METHODS, baseline_support, context_features, smooth_objective)


def category(target='pass_att', support='count'):
    return dict(target=target, state='READY', support=support, primary_roles=['QB'])


def fixture(target='pass_att', outcomes=(4, 4, 4, 4)):
    return pd.DataFrame(dict(season=[2022] * 4, position=['QB'] * 4,
        participation_state=['played'] * 4, **{target: list(outcomes)},
        f_player_pass_att_mean3=[2., 3., 4., 5.],
        f_player_pass_att_mean8=[3., 3., 3., 3.],
        f_player_games_prior=[0., 1., 2., 3.], f_team_pass_att_mean3=[30.] * 4))


class CorrectionContract(unittest.TestCase):
    def test_analytic_gradient(self):
        X = np.array([[1., -1.], [1., .5], [1., 1.]])
        beta = np.array([.05, -.1])
        for support, base, y in [('count', np.log([2., 3., 4.]), np.array([0., 2., 5.])),
                                 ('bernoulli', np.array([-1., 0., 1.]), np.array([0., 1., 1.]))]:
            _, gradient = smooth_objective(beta, X, base, y, support)
            for j in range(2):
                delta = np.eye(2)[j] * 1e-6
                a = smooth_objective(beta + delta, X, base, y, support)[0]
                b = smooth_objective(beta - delta, X, base, y, support)[0]
                self.assertAlmostEqual(gradient[j], (a-b)/2e-6, places=6)

    def test_count_mean_shrunk_correction(self):
        frame = fixture()
        model = BaselineCorrection.fit(frame, np.full(4, 2.), category(), METHODS[0], query_year=2023)
        point, _ = model.predict(frame, np.full(4, 2.))
        self.assertTrue(((point > 2) & (point < 4)).all())
        self.assertEqual(model.audit['fitted_rows'], 4)

    def test_binary_logit_and_boundaries(self):
        frame = fixture('anytime_td', (1, 1, 1, 0))
        frame['f_player_rush_att_mean3'] = 2.
        frame['f_player_rush_att_mean8'] = 2.
        frame['f_player_rec_tgt_mean3'] = 2.
        frame['f_player_rec_tgt_mean8'] = 2.
        frame['f_team_offense_plays_mean3'] = 60.
        c = category('anytime_td', 'bernoulli')
        model = BaselineCorrection.fit(frame, np.full(4, .2), c, METHODS[0], query_year=2023)
        p, _ = model.predict(frame, np.full(4, .2))
        self.assertTrue(((p > .2) & (p < .75)).all())
        p, reason = model.predict(frame, np.array([0., 1., -.1, np.nan]))
        np.testing.assert_array_equal(p[:2], [0., 1.])
        self.assertTrue(np.isnan(p[2:]).all())
        self.assertTrue((reason[:2] == 'exact_boundary_baseline_retained').all())

    def test_signed_yards_and_quantile_fit(self):
        frame = fixture('pass_yd', (-2, 0, 5, 10))
        model = BaselineCorrection.fit(frame, np.full(4, -10.),
            category('pass_yd', 'signed_integer'), METHODS[0], query_year=2023)
        p, _ = model.predict(frame, np.full(4, -10.))
        self.assertTrue(np.isfinite(p).all())
        self.assertTrue((p > -10).all())
        self.assertEqual(model.audit['optimizer'], 'fixed_quantile_highs')

    def test_unknown_missing_and_invalid_are_excluded_from_fit(self):
        frame = fixture(outcomes=(0, 2, .5, np.nan))
        frame.loc[1, 'participation_state'] = 'unknown'
        m = BaselineCorrection.fit(frame, np.full(4, 2.), category(), METHODS[0], query_year=2023)
        self.assertEqual(m.audit['fitted_rows'], 1)
        self.assertEqual(m.audit['excluded_training_rows'], 3)

    def test_future_training_rejected(self):
        frame = fixture()
        frame.loc[0, 'season'] = 2023
        with self.assertRaises(ValueError):
            BaselineCorrection.fit(frame, np.ones(4), category(), METHODS[0], query_year=2023)
        with self.assertRaises(ValueError):
            BaselineCorrection.fit(fixture(), np.ones(4), category(), METHODS[0], query_year=2022)

    def test_earlier_only_preprocessing_and_missing_flags(self):
        frame = fixture()
        frame['f_player_pass_att_mean8'] = np.nan
        design = CorrectionDesign.fit(frame, METHODS[1], 'pass_att')
        old = json.dumps(design.manifest(), sort_keys=True)
        later = frame.copy()
        later['f_player_games_prior'] = 9999.
        X = design.transform(later)
        self.assertEqual(X.shape, (4, 7))
        self.assertTrue(np.isfinite(X).all())
        self.assertTrue((X[:, 4] == 1).all())
        self.assertEqual(json.dumps(design.manifest(), sort_keys=True), old)

    def test_combined_opportunity_requires_both_components(self):
        frame = fixture()
        frame['f_player_rush_att_mean3'] = 2.
        frame['f_player_rush_att_mean8'] = 1.
        frame['f_player_rec_tgt_mean3'] = np.nan
        frame['f_player_rec_tgt_mean8'] = 3.
        frame['f_team_offense_plays_mean3'] = 60.
        self.assertTrue(np.isnan(context_features(frame, 'rush_rec_yd')[:, 0]).all())

    def test_exact_zero_update_and_reference_support(self):
        frame = fixture()
        frame.loc[1, 'position'] = 'WR'
        d = CorrectionDesign.fit(frame, METHODS[0], 'pass_att')
        m = BaselineCorrection(category(), METHODS[0], d, np.zeros(1), {})
        p, reasons = m.predict(frame, np.array([1.23456789, 2., 0., -1.]))
        np.testing.assert_array_equal(p[:3], [1.23456789, 2., 0.])
        self.assertTrue(np.isnan(p[3]))
        self.assertEqual(reasons[1], 'nonprimary_incumbent_reference')
        self.assertTrue(baseline_support([-100.], 'signed_integer')[0])

    def test_parameter_roundtrip_and_corruption_rejected(self):
        frame = fixture()
        m = BaselineCorrection.fit(frame, np.full(4, 2.), category(), METHODS[1], query_year=2023)
        value = json.loads(json.dumps(m.manifest()))
        restored = BaselineCorrection.from_manifest(value)
        np.testing.assert_array_equal(m.predict(frame, np.full(4, 2.))[0], restored.predict(frame, np.full(4, 2.))[0])
        value['design']['scale'][0] = 0.
        with self.assertRaises(ValueError):
            BaselineCorrection.from_manifest(value)


if __name__ == '__main__':
    unittest.main()
