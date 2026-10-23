"""Fictional support/eligibility regressions, never NFL accuracy evidence."""
import numpy as np
import pandas as pd
import pytest

from nfl_lab.skill import sample_joint_components


@pytest.mark.parametrize("seed", [1, 14, 20261022])
def test_passing_has_one_allocation_and_yards_follow_completions(seed):
    means = {"pass_att": 4., "pass_cmp": 1.2, "pass_td": .8,
             "pass_int": 1.5, "pass_yd": -3.}
    draws = sample_joint_components(means, pd.DataFrame(), draws=10000, seed=seed)
    assert (draws.pass_td <= draws.pass_cmp).all()
    assert (draws.pass_cmp + draws.pass_int <= draws.pass_att).all()
    assert (draws.pass_att.mod(1) == 0).all()
    assert (draws.pass_cmp == 0).any()
    assert draws.loc[draws.pass_cmp == 0, "pass_yd"].eq(0).all()
    assert draws.pass_yd.lt(0).any()
    assert draws.attrs["method"].endswith("new-v2")


@pytest.mark.parametrize("means", [
    {"pass_att": 4., "pass_cmp": 1., "pass_td": 2.},
    {"pass_att": 4., "pass_cmp": 3., "pass_int": 2.},
    {"pass_att": 0., "pass_cmp": 1.},
    {"pass_att": 2., "pass_int": 3.},
])
def test_impossible_passing_means_fail_before_sampling(means):
    with pytest.raises(ValueError, match="passing_.*mean"):
        sample_joint_components(means, pd.DataFrame())


@pytest.mark.parametrize("means", [
    {"pass_cmp": 2.}, {"pass_td": 1., "pass_att": 2.},
    {"pass_yd": 30.}, {"pass_int": .2},
])
def test_missing_passing_exposure_is_not_invented(means):
    with pytest.raises(ValueError, match="exposure_required"):
        sample_joint_components(means, pd.DataFrame())


def test_zero_completion_exposure_and_zero_attempts():
    zero = sample_joint_components({"pass_att": 0., "pass_cmp": 0., "pass_int": 0.,
                                   "pass_td": 0., "pass_yd": 0.}, pd.DataFrame())
    assert zero.eq(0).all().all()
    with pytest.raises(ValueError, match="zero_opportunity"):
        sample_joint_components({"pass_att": 4., "pass_cmp": 0., "pass_yd": 2.}, pd.DataFrame())


def test_allocation_preserves_declared_count_means_in_monte_carlo():
    means = {"pass_att": 4., "pass_cmp": 2.5, "pass_td": .7, "pass_int": .5}
    rows = sample_joint_components(means, pd.DataFrame(), draws=30000, seed=102)
    for name, mean in means.items():
        assert rows[name].mean() == pytest.approx(mean, abs=.04)


def test_only_canonical_played_history_affects_dependence_and_spread():
    history = pd.DataFrame({"rush_yd": [1., 3., 5.], "rec_yd": [2., 4., 6.],
                            "outcome_available_utc": ["2000-01-01T00:00:00Z"] * 3,
                            "participation_state": ["played"] * 3})
    extra = pd.DataFrame({"rush_yd": [1e10, 1e11], "rec_yd": [-1e10, -1e11],
                         "outcome_available_utc": ["2000-01-01T00:00:00Z"] * 2,
                         "participation_state": ["DNP", "unknown"]})
    options = {"cutoff_utc": "2000-02-01T00:00:00Z", "draws": 100, "seed": 2}
    expected = sample_joint_components({"rush_yd": 3., "rec_yd": 4.}, history, **options)
    actual = sample_joint_components({"rush_yd": 3., "rec_yd": 4.},
                                     pd.concat([history, extra], ignore_index=True), **options)
    np.testing.assert_array_equal(actual.to_numpy(), expected.to_numpy())
    assert actual.attrs["complete_history_rows"] == 3
    with pytest.raises(ValueError, match="canonical_joint_participation_required"):
        sample_joint_components({"rush_yd": 3.}, history.drop(columns="participation_state"), **options)
    with pytest.raises(ValueError, match="conflicting_joint_participation"):
        sample_joint_components({"rush_yd": 3.}, history.assign(participation="DNP"), **options)


def test_empty_or_unknown_only_joint_history_reports_fallback():
    history = pd.DataFrame({"rec": [0., 1., 2.], "participation_state": ["unknown"] * 3,
                            "outcome_available_utc": ["2000-01-01T00:00:00Z"] * 3})
    result = sample_joint_components({"rec": 1.}, history,
                                     cutoff_utc="2000-02-01T00:00:00Z")
    assert result.attrs["complete_history_rows"] == 0
    assert result.attrs["fallback"] == "insufficient_complete_joint_history_independent_copula"
