"""Fictional engineering checks only; no real football outcomes or forecasts."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from nfl_lab.cdf_engine import (
    LeafCDFModel, MixtureBatch, SupportPrior, chronological_split,
    prediction_rows, valid_support, validate_category,
)


def fictional(n=180):
    rng = np.random.default_rng(34)
    kickoff = pd.date_range("2020-01-01", periods=n, freq="1D", tz="UTC")
    frame = pd.DataFrame({"season": 2020, "week": np.arange(n) // 10 + 1,
        "game_id": [f"fictional-game-{i}" for i in range(n)],
        "player_id": [f"fictional-player-{i % 6}" for i in range(n)],
        "team": "fictional-A", "opponent": "fictional-B", "position": "QB",
        "kickoff_utc": kickoff, "cutoff_utc": kickoff - pd.Timedelta(hours=2),
        "outcome_available_utc": kickoff + pd.Timedelta(days=7),
        "feature_max_source_available_utc": kickoff - pd.Timedelta(days=1),
        "participation_state": "played", "pass_att": rng.integers(0, 41, n),
        "f_player_pass_att_mean3": rng.uniform(0, 40, n),
        "f_player_pass_att_n3": 3., "f_player_games_prior": 5.,
        "f_opp_pass_att_allowed_mean3": rng.uniform(15, 40, n)})
    test = frame.iloc[:12].copy()
    test["season"] = 2022
    test["kickoff_utc"] += pd.Timedelta(days=800)
    test["cutoff_utc"] += pd.Timedelta(days=800)
    test["feature_max_source_available_utc"] += pd.Timedelta(days=800)
    category = {"target": "pass_att", "state": "READY", "support": "count",
                "modeled_roles": ["QB"], "primary_roles": ["QB"],
                "outcome_contract": {"definition": "fictional integer attempts"},
                "panels": {"base": ["f_player_pass_att_mean3", "f_player_pass_att_n3"],
                           "context": ["f_player_pass_att_mean3", "f_player_pass_att_n3", "f_opp_pass_att_allowed_mean3"]}}
    return frame, test, category


@pytest.mark.parametrize("support,labels,grid", [
    ("count", [0, 1, 4, 0, 2], np.arange(0, 1000)),
    ("signed_integer", [-7, -2, 0, 4, 10], np.arange(-2000, 2001)),
    ("bernoulli", [0, 0, 1], np.array([0, 1]))])
def test_prior_closed_moments_and_pair_moment_against_finite_sums(support, labels, grid):
    prior = SupportPrior.fit(labels, support)
    p = np.exp(prior.logpmf(grid))
    assert p.sum() == pytest.approx(1., abs=1e-13)
    assert p @ grid == pytest.approx(prior.mean, abs=1e-11)
    assert p @ ((grid-prior.mean)**2) == pytest.approx(prior.variance, abs=1e-9)
    thresholds = np.array([-20, -1, 0, 1, 30])
    brute = np.sum(p[:, None] * np.abs(grid[:, None] - thresholds), axis=0)
    np.testing.assert_allclose(prior.absolute_moment(thresholds), brute, atol=1e-11)
    cdf = np.cumsum(p)
    # Exact identity E|P-P'|=2 sum_k F(k)(1-F(k)); negligible fictional-grid tails.
    assert prior.pair_absolute_moment == pytest.approx(2*np.sum(cdf*(1-cdf)), abs=1e-10)


@pytest.mark.parametrize("support,labels,atoms,weights,y,grid", [
    ("count", [0, 1, 5], [0, 3, 12], [[.1, .6, .3]], [2], np.arange(0, 1000)),
    ("signed_integer", [-2, 0, 8], [-8, 0, 13], [[.4, .4, .2]], [-3], np.arange(-3000, 3001)),
    ("bernoulli", [0, 0, 1], [0, 1], [[.6, .4]], [1], np.arange(0, 2))])
def test_mixture_crps_matches_full_lattice_cdf_identity(support, labels, atoms, weights, y, grid):
    law = MixtureBatch(atoms, weights, SupportPrior.fit(labels, support))
    brute = sum(float(((law.cdf(k) - (y[0] <= k))**2)[0]) for k in grid)
    assert law.crps(y)[0] == pytest.approx(brute, abs=2e-10)
    pmf = np.array([np.exp(law.logpmf(k))[0] for k in grid])
    assert pmf.sum() == pytest.approx(1., abs=1e-12)
    assert pmf @ grid == pytest.approx(law.mean[0], abs=1e-10)


def test_extreme_logmass_is_finite_without_mass_floor_or_clipping():
    for support, labels, value in [("count", [0, 0], 10**9), ("signed_integer", [-2, 0], -10**9)]:
        prior = SupportPrior.fit(labels, support)
        law = MixtureBatch([0], [[1.]], prior)
        assert np.isfinite(law.logpmf(value)).all()
        assert law.logpmf(value)[0] < -10**6


@pytest.mark.parametrize("support,labels,atoms", [("count", [1000, 2000], [0, 3000]), ("signed_integer", [-2000, 1000], [-3000, 3000]), ("bernoulli", [0, 1], [0, 1])])
def test_full_support_quantiles_are_lower_inverse_without_tail_clipping(support, labels, atoms):
    law = MixtureBatch(atoms, [[.4, .6]], SupportPrior.fit(labels, support))
    for p in [1e-7, .1, .5, .9, 1-1e-7]:
        q = law.quantile(p)
        assert (law.cdf(q) >= p).all()
        assert (law.cdf(q-1) < p).all()
        assert valid_support(q, support).all()


def test_empirical_histogram_uses_whole_training_labels_and_repeatable_model(tmp_path):
    train, test, category = fictional()
    model = LeafCDFModel.fit(train, category, "base")
    x = model.design.transform(train)
    leaves = model.forest.apply(x)
    for j, tree in enumerate(model.forest.estimators_):
        for leaf in np.unique(leaves[:, j]):
            expected = np.bincount(np.searchsorted(model.support, train.pass_att.to_numpy()[leaves[:, j] == leaf]), minlength=len(model.support))
            np.testing.assert_allclose(model.leaf_histograms[j][leaf].toarray()[0], expected/expected.sum())
    original = prediction_rows(model, test, score=True)
    assert np.isfinite(original[["mean", "median", "crps", "log_score"]]).all(axis=None)
    assert (original["median"] == np.floor(original["median"])).all()
    assert not np.allclose(original["mean"], original["median"])
    model.save(tmp_path/"artifact")
    restored = joblib.load(tmp_path/"artifact"/"model.joblib")
    pd.testing.assert_frame_equal(original, prediction_rows(restored, test, score=True))
    assert restored.training_binding.equals(model.training_binding)
    np.testing.assert_array_equal(restored.training_leaf_ids, leaves)
    json.dumps(model.audit, allow_nan=False)


def test_forecast_does_not_read_test_labels_or_test_participation():
    train, test, category = fictional()
    model = LeafCDFModel.fit(train, category, "context")
    original = prediction_rows(model, test, score=False)
    test["pass_att"] = 999999
    test["participation_state"] = "DNP"
    pd.testing.assert_frame_equal(original, prediction_rows(model, test, score=False))


def test_dnp_unknown_missing_invalid_and_played_zero_stay_distinct():
    train, test, category = fictional()
    train.loc[:9, "participation_state"] = "DNP"
    train.loc[10:19, "participation_state"] = "unknown"
    train.loc[20:24, "pass_att"] = np.nan
    train.loc[25:29, "pass_att"] = -1
    model = LeafCDFModel.fit(train, category, "base")
    assert model.audit["supported_played_training_rows"] == len(train)-30
    test["pass_att"] = [0, 1, np.nan, -1, 1.5, 0, 0, 0, 0, 0, 0, 0]
    test.loc[test.index[5], "participation_state"] = "DNP"
    test.loc[test.index[6], "participation_state"] = "unknown"
    result = prediction_rows(model, test, score=True)
    assert list(result.outcome_state[:7]) == ["played_zero", "played_nonzero", "played_missing_statistic", "played_invalid_support", "played_invalid_support", "DNP", "unknown"]
    assert result.crps.iloc[2:7].isna().all()
    assert np.isfinite(result.crps.iloc[0])


def test_nonmodeled_cold_and_unknown_roles_retained_as_explicit_prior():
    train, test, category = fictional()
    train.loc[train.index[-20:], "position"] = "WR"
    model = LeafCDFModel.fit(train, category, "base")
    test.loc[test.index[0], "position"] = "WR"
    test.loc[test.index[1], "position"] = "UNSEEN"
    test.loc[test.index[2], "f_player_games_prior"] = 0
    result = prediction_rows(model, test, score=True)
    assert len(result) == len(test)
    assert list(result.fallback[:3]) == ["nonmodeled_role_prior", "global_prior_unknown_role", "cold_start_role_prior"]
    assert result["mean"].iloc[0] == pytest.approx(model.priors["WR"].mean)
    assert result["mean"].iloc[1] == pytest.approx(model.global_prior.mean)
    assert len(model.prior_training_binding) == len(train)
    assert len(model.training_binding) == len(train)-20
    assert SupportPrior.fit(model.prior_training_binding.pass_att, "count") == model.global_prior
    for role, group in model.prior_training_binding.groupby("position"):
        assert SupportPrior.fit(group.pass_att, "count") == model.priors[role]


def test_whole_missing_history_field_uses_cold_prior():
    train, test, category = fictional()
    model = LeafCDFModel.fit(train, category, "base")
    rows = prediction_rows(model, test.drop(columns="f_player_games_prior"))
    assert rows.fallback.eq("cold_start_role_prior").all()
    assert rows["mean"].eq(model.priors["QB"].mean).all()


def test_missing_source_clock_is_only_permitted_for_cold_history():
    from nfl_lab.cdf_engine import assert_clock_contract
    _, test, _ = fictional()
    test["feature_max_source_available_utc"] = pd.NaT
    with pytest.raises(ValueError, match="warm history"):
        assert_clock_contract(test)
    test["f_player_games_prior"] = 0
    assert_clock_contract(test)


def test_chronology_removes_future_and_unknown_available_labels_and_rejects_feature_leak():
    train, test, _ = fictional()
    train.loc[0, "outcome_available_utc"] = test.cutoff_utc.min()
    train.loc[1, "outcome_available_utc"] = pd.NaT
    combined = pd.concat([train, test], ignore_index=True)
    old, future = chronological_split(combined, 2022)
    assert len(old) == len(train)-2
    assert len(future) == len(test)
    combined.loc[0, "feature_max_source_available_utc"] = combined.loc[0, "cutoff_utc"]
    with pytest.raises(ValueError, match="strictly earlier"):
        chronological_split(combined, 2022)


def test_blocked_ppr_and_obvious_label_features_rejected():
    _, _, category = fictional()
    category["state"] = "BLOCKED_LABEL_CONTRACT"
    with pytest.raises(ValueError, match="blocked"):
        validate_category(category)
    category["state"] = "READY"
    category["panels"]["base"] = ["f_actual_mean3"]
    category["panels"]["context"] = ["f_actual_mean3"]
    with pytest.raises(ValueError, match="unqualified"):
        validate_category(category)


def test_empty_supported_training_abstains_and_no_fake_zero_distribution():
    train, test, category = fictional()
    train["pass_att"] = np.nan
    model = LeafCDFModel.fit(train, category, "base")
    result = prediction_rows(model, test, score=True)
    assert result[["mean", "median", "crps", "log_score"]].isna().all(axis=None)
    assert result.fallback.eq("no_supported_played_training_outcomes").all()
