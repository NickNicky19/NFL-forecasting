"""Model contract checks; synthetic cases are not football validation evidence."""

import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab.models import (
    COUNT_TARGETS, METHODS, TARGETS, coherent_completion_samples, fit_predict,
)


def histories(n=100):
    rng = np.random.default_rng(82)
    attempts = rng.integers(15, 46, n)
    completions = rng.binomial(attempts, .65)
    frame = pd.DataFrame({
        "season": 2021, "week": np.arange(n) // 4 + 1,
        "game_id": [f"game-{i}" for i in range(n)],
        "player_id": [f"player-{i % 4}" for i in range(n)],
        "position": "QB", "team": "A", "opponent": ["B", "C"] * (n // 2),
        "kickoff_utc": pd.date_range("2021-01-01", periods=n, freq="7D", tz="UTC"),
        "participation_state": "played", "pass_att": attempts,
        "pass_cmp": completions, "pass_yd": attempts * 7 + rng.normal(0, 15, n),
        "pass_td": rng.poisson(1.5, n), "pass_int": rng.poisson(.7, n),
        "rush_att": rng.integers(1, 9, n), "rush_yd": rng.normal(18, 14, n),
        "targets": rng.integers(0, 6, n), "rec": rng.integers(0, 5, n),
        "rec_yd": rng.normal(8, 15, n), "fantasy_ppr": rng.normal(12, 8, n),
        "anytime_td": rng.binomial(1, .2, n),
        "f_player_games_prior": 8, "f_player_play_rate8": .9,
        "f_player_known_participation_n8": 8,
        "f_team_pass_att_mean3": 34.0, "f_team_rush_att_mean3": 25.0,
        "f_opp_pass_yd_allowed_mean3": np.linspace(150, 300, n),
    })
    frame["rush_rec_yd"] = frame["rush_yd"] + frame["rec_yd"]
    for target in TARGETS + ("targets",):
        frame[f"f_player_{target}_mean3"] = frame.groupby("player_id")[target].transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
        frame[f"f_player_{target}_n3"] = frame.groupby("player_id")[target].transform(lambda s: s.shift().rolling(3, min_periods=1).count())
        frame[f"f_player_{target}_mean8"] = frame.groupby("player_id")[target].transform(lambda s: s.shift().rolling(8, min_periods=1).mean())
        frame[f"f_player_{target}_n8"] = frame.groupby("player_id")[target].transform(lambda s: s.shift().rolling(8, min_periods=1).count())
    for feature, num, den in (
        ("pass_ypa3", "pass_yd", "pass_att"), ("comp_rate3", "pass_cmp", "pass_att"),
        ("rush_ypa3", "rush_yd", "rush_att"), ("rec_ypt3", "rec_yd", "targets"),
        ("rec_catch_rate3", "rec", "targets"),
    ):
        frame[f"f_player_{feature}"] = frame[f"f_player_{num}_mean3"] / frame[f"f_player_{den}_mean3"].replace(0, np.nan)
    train = frame.iloc[:-10].copy()
    test = frame.iloc[-10:].copy()
    test.index = [f"forecast-{i}" for i in range(len(test))]
    return train, test


@pytest.mark.parametrize("method", METHODS)
def test_registered_methods_and_index_contract(method):
    train, test = histories()
    result = fit_predict(train, test, "pass_yd", method)
    assert result.index.equals(test.index)
    assert list(result) == ["mean", "scale", "family", "p10", "p50", "p90", "p_participation", "fallback"]
    json.dumps(result.attrs, allow_nan=False)
    if method in {"raw_sleeper", "pinned_website"}:
        assert result["mean"].isna().all()
    else:
        assert np.isfinite(result["mean"]).all()


@pytest.mark.parametrize("target", sorted(COUNT_TARGETS))
def test_counts_have_integer_quantiles_and_poisson_or_overdispersed_variance(target):
    train, test = histories()
    result = fit_predict(train, test, target, "distributional")
    quantiles = result[["p10", "p50", "p90"]].to_numpy()
    assert np.isfinite(quantiles).all()
    assert (quantiles >= 0).all()
    assert (quantiles == np.floor(quantiles)).all()
    assert (result["scale"] ** 2 >= result["mean"] - 1e-10).all()
    assert (result["p10"] <= result["p50"]).all()
    assert (result["p50"] <= result["p90"]).all()


def test_signed_yards_supported_and_new_player_uses_position_prior():
    train, test = histories()
    train["rush_yd"] = -8.0
    test["player_id"] = "new-player"
    test["f_player_rush_yd_n3"] = 0
    result = fit_predict(train, test, "rush_yd", "recent")
    assert (result["mean"] == -8).all()
    assert (result["p10"] < 0).all()
    assert (result["fallback"] == "position_prior").all()


def test_explicit_unknown_window_does_not_skip_to_older_supported_appearances():
    train, test = histories()
    test["f_player_pass_yd_mean3"] = np.nan
    test["f_player_pass_yd_n3"] = 0
    result = fit_predict(train, test, "pass_yd", "recent")
    np.testing.assert_allclose(result["mean"], train["pass_yd"].mean())
    assert (result["fallback"] == "position_prior").all()


def test_receiving_workload_uses_canonical_rec_tgt_alias():
    train, test = histories()
    train = train.rename(columns={"targets": "rec_tgt"})
    test = test.rename(columns={"targets": "rec_tgt"})
    result = fit_predict(train, test, "rec_yd", "workload")
    assert np.isfinite(result["mean"]).all()
    assert (result["fallback"] == "").all()


def test_no_supported_ppr_outcome_abstains_instead_of_provider_substitution():
    train, test = histories()
    train["fantasy_ppr"] = np.nan
    train["fantasy_points_ppr"] = 25
    result = fit_predict(train, test, "fantasy_ppr", "ridge")
    assert result[["mean", "scale", "p10", "p50", "p90"]].isna().all().all()
    assert (result["fallback"] == "no_supported_played_training_outcomes").all()


def test_dnp_unknown_missing_and_invalid_counts_not_treated_as_zero():
    train, test = histories()
    train.loc[train.index[:20], "participation_state"] = "DNP"
    train.loc[train.index[20:30], "participation_state"] = "unknown"
    train.loc[train.index[30:35], "pass_att"] = np.nan
    train.loc[train.index[35:40], "pass_att"] = -1
    train.loc[train.index[40:45], "pass_att"] = 1.5
    result = fit_predict(train, test, "pass_att", "recent")
    assert result.attrs["supported_played_training_rows"] == len(train) - 45
    assert result.attrs["participation"]["DNP_rows"] == 20
    assert result["p_participation"].between(0, 1).all()


def test_test_labels_and_participation_never_change_predictions():
    train, test = histories()
    original = fit_predict(train, test, "pass_att", "ridge")
    mutated = test.copy()
    for target in TARGETS:
        mutated[target] = 999999
    mutated["participation_state"] = "DNP"
    changed = fit_predict(train, mutated, "pass_att", "ridge")
    pd.testing.assert_frame_equal(original, changed)


def test_future_train_labels_removed_and_target_feature_columns_rejected():
    train, test = histories()
    original = fit_predict(train, test, "pass_yd", "ridge")
    train["f_future_pass_yd_mean3"] = 10**8
    test["f_future_pass_yd_mean3"] = 10**8
    train["f_pass_yd"] = train["pass_yd"]
    test["f_pass_yd"] = test["pass_yd"]
    train["f_outcome_mean3"] = train["pass_yd"]
    test["f_outcome_mean3"] = test["pass_yd"]
    future = train.iloc[-1:].copy()
    future["kickoff_utc"] = test["kickoff_utc"].max() + pd.Timedelta(days=7)
    future["pass_yd"] = 10**9
    train = pd.concat([train, future], ignore_index=True)
    changed = fit_predict(train, test, "pass_yd", "ridge")
    np.testing.assert_allclose(original["mean"], changed["mean"])
    assert changed.attrs["temporal_training"]["removed_future_or_unknown_time_rows"] == 1
    assert set(changed.attrs["fitted_model"]["rejected_feature_columns"]) == {"f_future_pass_yd_mean3", "f_pass_yd", "f_outcome_mean3"}


def test_preprocessing_and_coefficients_fit_on_training_only():
    train, test = histories()
    original = fit_predict(train, test, "pass_yd", "ridge")
    test["f_opp_pass_yd_allowed_mean3"] = 10**10
    changed = fit_predict(train, test, "pass_yd", "ridge")
    for field in ("numeric_medians", "numeric_scales", "coefficients", "intercept"):
        assert original.attrs["fitted_model"][field] == changed.attrs["fitted_model"][field]


def test_labels_not_available_at_forecast_cutoff_are_excluded():
    train, test = histories()
    test["cutoff_utc"] = test["kickoff_utc"].min() - pd.Timedelta(days=2)
    train["outcome_available_utc"] = train["kickoff_utc"] + pd.Timedelta(days=7)
    train.loc[train.index[-1], "outcome_available_utc"] = test["kickoff_utc"].max()
    result = fit_predict(train, test, "pass_yd", "recent")
    assert result.attrs["temporal_training"]["label_availability_checked"] is True
    assert result.attrs["supported_played_training_rows"] == len(train) - 1


@pytest.mark.parametrize("group", ["opponent", "workload", "team"])
def test_ablations_remove_declared_feature_groups(group):
    train, test = histories()
    result = fit_predict(train, test, "pass_yd", f"ridge_without_{group}")
    manifest = result.attrs["fitted_model"]
    assert group not in manifest["feature_groups"].values()
    if group in {"opponent", "team"}:
        assert group not in manifest["categorical_levels"]


def test_missing_all_numeric_features_uses_recorded_fallback():
    train, test = histories()
    for column in test:
        if column.startswith("f_"):
            test[column] = np.nan
    result = fit_predict(train, test, "pass_att", "ridge")
    assert result["mean"].notna().all()
    assert result["fallback"].str.startswith("all_numeric_features_missing:").all()


def test_zero_counts_are_valid_and_no_distribution_is_fabricated_from_raw_points():
    train, test = histories()
    train["pass_td"] = 0
    test["f_player_pass_td_mean3"] = 0
    result = fit_predict(train, test, "pass_td", "recent")
    assert (result[["mean", "scale", "p10", "p50", "p90"]] == 0).all().all()
    prefix = "baseline_raw_sleeper"
    test[f"{prefix}_pass_att"] = 31.5
    test[f"{prefix}_cutoff_verified"] = True
    test[f"{prefix}_forecast_utc"] = test["kickoff_utc"] - pd.Timedelta(hours=1)
    test[f"{prefix}_source_sha256"] = "a" * 64
    raw = fit_predict(train, test, "pass_att", "raw_sleeper")
    assert (raw["mean"] == 31.5).all()
    assert raw[["scale", "p10", "p50", "p90"]].isna().all().all()
    test[f"{prefix}_forecast_utc"] = test["kickoff_utc"]
    assert fit_predict(train, test, "pass_att", "raw_sleeper")["mean"].isna().all()


def test_binary_probability_distribution_and_separate_participation():
    train, test = histories()
    test["participation_state"] = "DNP"  # A target outcome is not an input.
    result = fit_predict(train, test, "anytime_td", "distributional")
    assert (result["family"] == "bernoulli").all()
    assert result["mean"].between(0, 1).all()
    np.testing.assert_allclose(result["scale"] ** 2, result["mean"] * (1 - result["mean"]))
    assert set(np.unique(result[["p10", "p50", "p90"]])) <= {0, 1}
    assert (result["p_participation"] > 0).all()


def test_coherent_completion_samples_and_invalid_inputs():
    attempts = np.arange(100)
    completions = coherent_completion_samples(attempts, .65)
    assert (completions >= 0).all()
    assert (completions <= attempts).all()
    np.testing.assert_array_equal(completions, coherent_completion_samples(attempts, .65))
    with pytest.raises(ValueError):
        coherent_completion_samples(np.array([2.5]), .65)
    with pytest.raises(ValueError):
        coherent_completion_samples(attempts, 1.1)


def test_unregistered_candidate_rejected():
    train, test = histories()
    with pytest.raises(ValueError, match="unregistered"):
        fit_predict(train, test, "pass_yd", "posthoc_winner")
