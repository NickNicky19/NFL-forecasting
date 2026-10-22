from decimal import Decimal
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nfl_lab.scoring import (PPR_COMPONENTS, anytime_td_outcome, anytime_td_probability,
                             ppr_points, score_ppr, stat_value)
from nfl_lab.skill import (combine_mean_predictions, rb_team_share_workload,
                           independent_combined_yard_predictions,
                           sample_joint_components, signed_workload_efficiency,
                           summarize_joint_components)


def complete(**changes):
    result = dict.fromkeys(PPR_COMPONENTS, 0.)
    result.update(changes)
    return result


def test_pinned_ppr_rare_components_fractional_and_defensive_exception():
    row = complete(pass_yd=12.5, pass_td=.25, pass_int=1, pass_2pt=1,
                   rush_yd=-3, rush_td=1, rush_2pt=1, rec=2.5, rec_yd=12,
                   rec_td=1, rec_2pt=1, fum_lost=1, st_td=1, st_fum_rec=1,
                   st_ff=1, fum_rec_td=1, idp_blk_kick=1)
    assert ppr_points(row) == 35.9
    row["idp_fum_rec"] = 1
    assert ppr_points(row) == 29.9


@pytest.mark.parametrize("field", PPR_COMPONENTS)
def test_each_missing_component_abstains_even_if_provider_total_exists(field):
    row = complete(pts_ppr=24, fantasy_points_ppr=24)
    del row[field]
    result = score_ppr(row)
    assert result.value is None
    assert result.missing == (field,)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "1", -1])
def test_invalid_count_is_not_zero(value):
    assert ppr_points(complete(rec=value)) is None


def test_missing_combined_component_not_zero_and_signed_yards_survive():
    assert stat_value("rush_rec_yd", {"rush_yd": -2, "rec_yd": 0}) == -2
    assert stat_value("rush_rec_yd", {"rush_yd": 2}) is None


def test_td_event_excludes_passing_and_return_td_and_distinguishes_dnp():
    row = complete(pass_td=3, st_td=1, fum_rec_td=1)
    assert anytime_td_outcome(row) == 0
    assert anytime_td_outcome({"rush_td": 0}) is None
    assert anytime_td_outcome({"rush_td": 1}) == 1
    assert anytime_td_outcome({"rush_td": .1, "rec_td": 0}) is None
    assert anytime_td_outcome(row, participation="unknown") is None
    assert anytime_td_outcome(row, participation="dnp") is None
    assert anytime_td_outcome(row, participation="dnp", population="all_player") == 0
    assert anytime_td_probability(.3, .2, p_participation=.8, population="all_player") == pytest.approx(.8 * (1-np.exp(-.5)))
    assert ppr_points(complete(rec=Decimal(".25"))) == .25


def test_rb_new_share_and_signed_efficiency_have_explicit_cold_start():
    estimate = rb_team_share_workload(25, [10, 5], [20, 20], prior_share=.2,
                                      prior_team_opportunities=10)
    assert estimate.mean == pytest.approx(25 * 17 / 50)
    cold = rb_team_share_workload(20, [], [], prior_share=.2, prior_team_opportunities=10)
    assert cold.mean == 4 and cold.fallback == "cold_start_declared_prior"
    assert rb_team_share_workload(20, [], [], prior_share=.2,
                                  prior_team_opportunities=10, position="QB").mean is None
    signed = signed_workload_efficiency(4, [-10, -5], [2, 1],
                                       prior_efficiency=0, prior_opportunities=0)
    assert signed.mean == -20
    missing = signed_workload_efficiency(4, [None], [1],
                                        prior_efficiency=3, prior_opportunities=10)
    assert missing.mean == 12 and missing.fallback


def test_combined_means_add_and_quantiles_are_not_summed():
    rush = pd.DataFrame({"mean": [10.], "scale": [3.], "p50": [1.],
                         "p_participation": [.8], "fallback": [None]}, index=[7])
    rec = pd.DataFrame({"mean": [20.], "scale": [4.], "p50": [2.],
                        "p_participation": [.8], "fallback": [None]}, index=[7])
    result = combine_mean_predictions(rush, rec)
    assert result.loc[7, "mean"] == 30
    assert result.loc[7, "p50"] == 30
    assert result.loc[7, "scale"] == 5
    rec["p_participation"] = .9
    with pytest.raises(ValueError, match="participation"):
        combine_mean_predictions(rush, rec)
    with pytest.raises(ValueError, match="aligned"):
        combine_mean_predictions(rush, rec.set_axis([8]))


def test_joint_samples_are_reproducible_coherent_and_score_exact_ppr():
    means = complete(pass_att=20, pass_cmp=12, pass_yd=150, pass_td=1,
                     rush_att=8, rush_yd=-4, rec_tgt=5, rec=3, rec_yd=30,
                     rush_td=.3, rec_td=.2)
    history = pd.DataFrame([dict(means, rush_yd=-2, rec_yd=20),
                            dict(means, rush_yd=-5, rec_yd=40),
                            dict(means, rush_yd=-7, rec_yd=30)])
    history["outcome_available_utc"] = "2000-01-01T00:00:00Z"
    samples = sample_joint_components(means, history, draws=1000, seed=14,
                                      p_participation=.7, population="all_player", cutoff_utc="2000-02-01T00:00:00Z")
    repeated = sample_joint_components(means, history, draws=1000, seed=14,
                                       p_participation=.7, population="all_player", cutoff_utc="2000-02-01T00:00:00Z")
    pd.testing.assert_frame_equal(samples, repeated)
    assert (samples.rec <= samples.rec_tgt).all()
    assert (samples.pass_cmp <= samples.pass_att).all()
    assert (samples.rec_td <= samples.rec).all()
    assert (samples.rush_td <= samples.rush_att).all()
    assert (samples.loc[samples.rec == 0, "rec_yd"] == 0).all()
    assert (samples.loc[samples.rush_att == 0, "rush_yd"] == 0).all()
    assert (samples.rush_yd < 0).any()
    # Shared nonparticipation produces a simultaneous zero across components.
    assert (samples.eq(0).all(axis=1)).mean() > .2
    summary = summarize_joint_components(samples)
    assert summary["rush_rec_yd"]["mean"] == pytest.approx(samples.rush_yd.mean() + samples.rec_yd.mean())
    assert summary["fantasy_ppr"]["mean"] == pytest.approx(np.mean([ppr_points(x) for x in samples.to_dict("records")]))
    assert summary["anytime_td"]["mean"] == pytest.approx(((samples.rush_td + samples.rec_td) > 0).mean())


def test_joint_rare_ties_keep_marginal_means_and_no_missing_ppr_invention():
    history = pd.DataFrame({"rush_td": [0, 0, 0], "rec_td": [0, 0, 0]})
    history["outcome_available_utc"] = "2000-01-01T00:00:00Z"
    samples = sample_joint_components({"rush_td": .3, "rec_td": .2}, history,
                                      draws=20000, seed=8, cutoff_utc="2000-02-01T00:00:00Z")
    assert samples.rush_td.mean() == pytest.approx(.3, abs=.02)
    assert "fantasy_ppr" not in summarize_joint_components(samples)


def test_joint_dependence_never_uses_future_or_unknown_availability():
    history = pd.DataFrame({"rush_yd": [1., 3., 5.], "rec_yd": [2., 4., 6.],
                            "outcome_available_utc": ["2000-01-01T00:00:00Z"] * 3})
    means = {"rush_yd": 3., "rec_yd": 4.}
    expected = sample_joint_components(means, history, draws=50,
                                       cutoff_utc="2000-02-01T00:00:00Z")
    future = pd.DataFrame({"rush_yd": [1e9, 1e10], "rec_yd": [-1e9, -1e10],
                           "outcome_available_utc": ["2000-02-01T00:00:00Z", None]})
    actual = sample_joint_components(means, pd.concat([history, future], ignore_index=True), draws=50,
                                     cutoff_utc="2000-02-01T00:00:00Z")
    pd.testing.assert_frame_equal(actual, expected)
    with pytest.raises(ValueError, match="availability_required"):
        sample_joint_components(means, history)


def test_exact_joint_fumble_exception_is_not_scoring_marginal_means():
    rows = pd.DataFrame([complete(fum_rec_td=1, idp_fum_rec=0),
                         complete(fum_rec_td=0, idp_fum_rec=1)])
    assert summarize_joint_components(rows)["fantasy_ppr"]["mean"] == 3
    assert ppr_points(rows.mean().to_dict()) == 0


def test_independent_combined_evaluation_calls_shared_engine_for_all_three_targets(monkeypatch):
    calls = []
    def predict(train, test, target, method):
        calls.append((target, method))
        return pd.DataFrame({"mean": [{"rush_rec_yd": 22, "rush_yd": 8, "rec_yd": 11}[target]],
                             "scale": [3.], "p_participation": [.9], "fallback": [None]}, index=test.index)
    monkeypatch.setitem(sys.modules, "nfl_lab.models", SimpleNamespace(fit_predict=predict))
    test = pd.DataFrame(index=[9])
    result = independent_combined_yard_predictions(pd.DataFrame(), test, "workload")
    assert result.loc[9, "direct_mean"] == 22
    assert result.loc[9, "component_mean"] == 19
    assert calls == [("rush_rec_yd", "workload"), ("rush_yd", "workload"), ("rec_yd", "workload")]
