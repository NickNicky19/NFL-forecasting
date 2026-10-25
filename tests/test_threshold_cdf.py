"""Fictional engineering fixtures only; no NFL fits or forecasting evidence."""
import copy
import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from nfl_lab.cdf_engine import MixtureBatch, SupportPrior, valid_support
from nfl_lab.threshold_cdf import (
    CLASSIFIER_PARAMETERS, STABLE_MIXTURE_VERSION, THRESHOLD_GRIDS, VERSION,
    StableMixtureBatch, ThresholdCDFModel,
)


def fictional(target="pass_att", support="count", n=160):
    rng = np.random.default_rng(911)
    signal = rng.uniform(0, 1, n)
    labels = np.floor(35 * signal).astype(float)
    if support == "signed_integer":
        labels = np.floor(65 * signal - 15)
    elif support == "bernoulli":
        labels = (signal > .65).astype(float)
    frame = pd.DataFrame({
        "season": 2020, "week": np.arange(n) // 8 + 1,
        "game_id": [f"fictional-game-{i}" for i in range(n)],
        "player_id": [f"fictional-player-{i % 8}" for i in range(n)],
        "position": "QB", "participation_state": "played", target: labels,
        "f_history": signal, "f_sparse": np.where(signal > .5, signal, np.nan),
        "f_player_games_prior": 5.,
    })
    category = {"target": target, "state": "READY", "support": support,
                "modeled_roles": ["QB"], "primary_roles": ["QB"],
                "panels": {"base": ["f_history"], "context": ["f_history", "f_sparse"]}}
    test = frame.iloc[:9].copy()
    test["season"] = 2022
    return frame, test, category


def summarize(model, frame, **kwargs):
    rows = []
    for positions, law, reasons in model.predict_batches(frame, **kwargs):
        for j, position in enumerate(positions):
            rows.append({"position": position, "fallback": reasons[j],
                         "mean": np.nan if law is None else law.mean[j],
                         "median": np.nan if law is None else law.median[j],
                         "cdf0": np.nan if law is None else law.cdf(0)[j],
                         "log0": np.nan if law is None else law.logpmf(0)[j]})
    return pd.DataFrame(rows).sort_values("position").reset_index(drop=True)


def test_fixed_registered_grids_and_exact_classifier_budget():
    assert THRESHOLD_GRIDS == {
        "pass_yd": (-25, 0, 50, 100, 150, 200, 250, 300, 350, 400, 500),
        "pass_td": (0, 1, 2, 3, 4), "pass_cmp": (0, 5, 10, 15, 20, 25, 30, 35),
        "pass_att": (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50),
        "pass_int": (0, 1, 2, 3), "rush_yd": (-10, 0, 10, 25, 50, 75, 100, 150, 200),
        "rush_att": (0, 2, 5, 10, 15, 20, 25, 30), "rec": (0, 1, 2, 3, 4, 5, 7, 10, 15),
        "rec_yd": (-10, 0, 10, 25, 50, 75, 100, 150, 200),
        "rush_rec_yd": (-10, 0, 20, 40, 60, 80, 100, 150, 200, 250),
    }
    assert CLASSIFIER_PARAMETERS == dict(max_iter=60, max_leaf_nodes=15, min_samples_leaf=40,
                                         l2_regularization=10., learning_rate=.05,
                                         early_stopping=False, random_state=1911)


@pytest.mark.parametrize("support,labels,atoms,weights,grid", [
    ("count", [0, 1, 4], [0, 3, 8], [[.2, .5, .3]], np.arange(0, 1500)),
    ("signed_integer", [-4, 0, 8], [-7, 0, 13], [[.2, .5, .3]], np.arange(-2000, 2001)),
    ("bernoulli", [0, 0, 1], [0, 1], [[.7, .3]], np.array([0, 1])),
])
def test_stable_law_mass_moments_crps_support_and_infinite_endpoints(support, labels, atoms, weights, grid):
    law = StableMixtureBatch(atoms, weights, SupportPrior.fit(labels, support))
    pmf = np.array([np.exp(law.logpmf(k))[0] for k in grid])
    assert pmf.sum() == pytest.approx(1., abs=2e-13)
    assert pmf @ grid == pytest.approx(law.mean[0], abs=1e-10)
    cdf = np.array([law.cdf(k)[0] for k in grid])
    assert (np.diff(cdf) >= 0).all()
    assert ((cdf >= 0) & (cdf <= 1)).all()
    y = atoms[0]
    assert law.crps(y)[0] == pytest.approx(np.sum((cdf - (y <= grid)) ** 2), abs=2e-10)
    assert law.cdf(-np.inf)[0] == 0.
    assert law.cdf(np.inf)[0] == 1.
    assert law.cumulative[0, -1] == 1.
    assert np.isneginf(law.logpmf(np.inf)).all()
    assert np.isneginf(law.logpmf(-np.inf)).all()
    assert np.isneginf(law.logpmf(.5)).all()
    if support != "signed_integer":
        assert law.cdf(-1)[0] == 0.
        assert np.isneginf(law.logpmf(-1)).all()
    if support == "bernoulli":
        assert law.cdf(1)[0] == 1.
        assert np.isneginf(law.logpmf(2)).all()


def test_cumulative_endpoint_reconstruction_is_shared_and_rejects_invalid_mass():
    prior = SupportPrior.fit([0, 2], "count")
    weights = np.full((1, 1000), .001)
    incumbent = MixtureBatch(np.arange(1000), weights, prior)
    assert incumbent.cdf(np.inf)[0] > 1.  # Fictional reproduction of binary64 accumulation.
    stable = StableMixtureBatch.from_batch(incumbent)
    expected_cumulative = np.cumsum(weights, axis=1)
    expected_cumulative /= expected_cumulative[:, -1:]
    np.testing.assert_array_equal(stable.cumulative, expected_cumulative)
    np.testing.assert_array_equal(stable.weights, np.diff(expected_cumulative, axis=1, prepend=0.))
    assert stable.cdf(np.inf)[0] == 1.
    assert stable.cdf(10**6)[0] == 1.
    assert stable.version == STABLE_MIXTURE_VERSION
    for bad in [[[.3, .8]], [[-.1, 1.1]], [[np.nan, 1.]]]:
        with pytest.raises(ValueError):
            StableMixtureBatch([0, 1], bad, prior)
    with pytest.raises(ValueError, match="NaN"):
        stable.cdf(np.nan)
    with pytest.raises(ValueError, match="full-support"):
        StableMixtureBatch([0], [[1]], SupportPrior("count", q=1.))


@pytest.mark.parametrize("support,labels,value", [
    ("count", [0, 0], 10**9), ("signed_integer", [-2, 0], -10**9),
])
def test_legal_full_tails_retain_finite_logmass_and_lower_inverse_quantiles(support, labels, value):
    law = StableMixtureBatch([0], [[1]], SupportPrior.fit(labels, support))
    assert np.isfinite(law.logpmf(value)).all()
    assert law.logpmf(value)[0] < -10**6
    assert np.isneginf(law.logpmf(.25)).all()
    for p in [1e-8, .1, .5, .9, 1 - 1e-8]:
        q = law.quantile(p)
        assert valid_support(q, support).all()
        assert (law.cdf(q) >= p).all()
        assert (law.cdf(q - 1) < p).all()


@pytest.mark.parametrize("target,support", [("pass_att", "count"), ("rush_yd", "signed_integer")])
def test_single_constrained_classifier_and_training_only_within_bin_law(target, support):
    train, test, category = fictional(target, support)
    model = ThresholdCDFModel.fit(train, category, "context")
    assert model.audit["fit_state"] == "FITTED"
    assert model.audit["classifier_count"] == 1
    assert model.audit["expanded_training_rows"] == len(train) * len(model.thresholds)
    assert model.classifier.monotonic_cst == [0] * (model.design.transform(train).shape[1]) + [1]
    assert model.audit["feature_names"][-1] == "__cdf_threshold"
    assert model.classifier.n_iter_ == 60
    assert model.audit["threads"] == 2
    probability = model.threshold_probabilities(test)
    assert (np.diff(probability, axis=1) >= 0).all()
    bins = np.searchsorted(model.thresholds, train[target], side="left")
    for slot, histogram in enumerate(model.bin_histograms):
        labels = train[target].to_numpy()[bins == slot]
        if len(labels):
            atoms, counts = np.unique(labels, return_counts=True)
            expected = np.zeros(len(model.support))
            expected[np.searchsorted(model.support, atoms)] = counts / counts.sum()
        else:
            representative = (0 if support == "count" else model.thresholds[0]) if slot == 0 else model.thresholds[slot - 1] + 1
            expected = (model.support == representative).astype(float)
        np.testing.assert_array_equal(histogram, expected)
    assert valid_support(model.support, support).all()
    for positions, law, reasons in model.predict_batches(test, batch_size=4):
        assert not reasons.any()
        raw_mass = np.diff(probability[positions], axis=1, prepend=0., append=1.)
        np.testing.assert_allclose(law.weights, raw_mass @ model.bin_histograms, atol=2e-15, rtol=0)
        for j, threshold in enumerate(model.thresholds):
            empirical_cdf = np.sum(law.weights[:, model.support <= threshold], axis=1)
            np.testing.assert_allclose(empirical_cdf, probability[positions, j], atol=2e-15, rtol=0)
        assert not np.allclose(law.mean, law.median)
        assert law.b == .05
    assert model.audit["version"] == VERSION
    assert "calibration_unestablished" in model.audit["probability_semantics"]
    json.dumps(model.audit, allow_nan=False)


def test_empty_bins_have_predeclared_representatives_including_count_zero_and_signed_low_tail():
    for target, support, zero_or_low in [("pass_int", "count", 0), ("pass_yd", "signed_integer", -25)]:
        train, test, category = fictional(target, support)
        train[target] = 2
        model = ThresholdCDFModel.fit(train, category, "base")
        assert model.support[0] == zero_or_low
        assert model.support[-1] == model.thresholds[-1] + 1
        assert model.audit["empty_bin_representatives"]["0"] == zero_or_low
        assert valid_support(model.support, support).all()
        assert np.isfinite(summarize(model, test)[["mean", "median", "log0"]]).all(axis=None)


def test_label_eligibility_and_genuine_played_zero_remain_in_prior_and_model_bindings():
    train, _, category = fictional()
    train.loc[0, "pass_att"] = 0
    train.loc[1, "participation_state"] = "DNP"
    train.loc[2, "participation_state"] = "unknown"
    train.loc[3, "pass_att"] = np.nan
    train.loc[4, "pass_att"] = -1
    train.loc[5, "pass_att"] = 1.5
    model = ThresholdCDFModel.fit(train, category, "base")
    assert model.audit["supported_played_training_rows"] == len(train) - 5
    assert model.audit["played_missing_outcome"] == 1
    assert model.audit["played_invalid_support"] == 2
    assert model.training_binding.loc[0, "pass_att"] == 0
    assert not set(range(1, 6)) & set(model.training_binding.index)
    assert model.audit["training_bin_counts"][0] == (model.training_binding.pass_att == 0).sum()


def test_cold_nonmodeled_unseen_and_missing_history_use_exact_prior_law():
    train, test, category = fictional()
    train.loc[train.index[-20:], "position"] = "WR"
    model = ThresholdCDFModel.fit(train, category, "base")
    test.loc[test.index[0], "position"] = "WR"
    test.loc[test.index[1], "position"] = "UNSEEN"
    test.loc[test.index[2:5], "f_player_games_prior"] = [0., .5, np.nan]
    result = summarize(model, test)
    assert result.fallback.tolist()[:5] == ["nonmodeled_role_prior", "global_prior_unknown_role",
                                           "cold_start_role_prior", "cold_start_role_prior", "cold_start_role_prior"]
    for positions, law, reasons in model.predict_batches(test):
        if not reasons.any():
            continue
        assert law.b == 1.
        np.testing.assert_allclose(law.mean, law.prior.mean)
        for value in [0, 1, 50]:
            np.testing.assert_array_equal(law.cdf(value), np.full(len(positions), law.prior.cdf(value)))
            np.testing.assert_array_equal(law.logpmf(value), np.full(len(positions), law.prior.logpmf(value)))
    assert len(model.prior_training_binding) == len(train)
    assert len(model.training_binding) == len(train) - 20
    assert SupportPrior.fit(model.prior_training_binding.pass_att, "count") == model.global_prior
    for role, group in model.prior_training_binding.groupby("position"):
        assert SupportPrior.fit(group.pass_att, "count") == model.priors[role]
    missing = summarize(model, test.iloc[5:].drop(columns="f_player_games_prior"))
    assert missing.fallback.eq("cold_start_role_prior").all()
    assert missing["mean"].eq(model.priors["QB"].mean).all()
    control = summarize(model, test, prior_only=True)
    assert control.fallback.iloc[0] == "role_prior_control"
    assert control.fallback.iloc[1] == "global_prior_unknown_role"


def test_no_fit_prior_and_no_supported_labels_abstention_have_distinct_states():
    train, test, category = fictional(n=50)
    model = ThresholdCDFModel.fit(train, category, "base")
    result = summarize(model, test)
    assert model.classifier is None
    assert result.fallback.eq("insufficient_modeled_training_role_prior").all()
    assert result["mean"].eq(model.priors["QB"].mean).all()
    assert not result["mean"].eq(result["median"]).all()
    train["pass_att"] = np.nan
    model = ThresholdCDFModel.fit(train, category, "base")
    result = summarize(model, test)
    assert model.audit["fit_state"] == "NO_SUPPORTED_TRAINING_LABELS"
    assert result.fallback.eq("no_supported_played_training_outcomes").all()
    assert result[["mean", "median"]].isna().all(axis=None)


def test_native_bernoulli_event_probability_is_mean_and_never_a_count_law():
    train, test, category = fictional("anytime_td", "bernoulli")
    model = ThresholdCDFModel.fit(train, category, "context")
    assert model.audit["procedure"] == "native_binary_event"
    assert model.audit["expanded_training_rows"] == len(train)
    assert model.thresholds.size == 0
    assert model.bin_histograms is None
    assert model.classifier.monotonic_cst == [0] * model.design.transform(train).shape[1]
    raw = model.classifier.predict_proba(model.design.transform(test))[:, 1]
    np.testing.assert_array_equal(model.threshold_probabilities(test)[:, 0], raw)
    for positions, law, _ in model.predict_batches(test):
        np.testing.assert_allclose(law.mean, .95 * raw[positions] + .05 * model.priors["QB"].p, atol=2e-16)
        np.testing.assert_allclose(np.exp(law.logpmf(1)), law.mean)
        np.testing.assert_allclose(law.cdf(0), 1 - law.mean)
        np.testing.assert_allclose(law.variance, law.mean * (1 - law.mean))
        assert law.prior.support == "bernoulli"
        assert np.isneginf(law.logpmf(2)).all()
    assert "calibration_unestablished" in model.audit["probability_semantics"]


@pytest.mark.parametrize("label", [0, 1])
def test_native_binary_single_training_class_keeps_event_semantics(label):
    train, test, category = fictional("anytime_td", "bernoulli")
    train["anytime_td"] = label
    model = ThresholdCDFModel.fit(train, category, "base")
    assert (model.threshold_probabilities(test) == label).all()
    for _, law, _ in model.predict_batches(test):
        np.testing.assert_allclose(law.mean, .95 * label + .05 * model.priors["QB"].p)
        assert (law.mean > 0).all() and (law.mean < 1).all()


def test_inference_ignores_test_labels_participation_and_missing_features_use_fixed_design():
    train, test, category = fictional()
    model = ThresholdCDFModel.fit(train, category, "context")
    original = summarize(model, test)
    test["pass_att"] = -999999
    test["participation_state"] = "DNP"
    pd.testing.assert_frame_equal(original, summarize(model, test))
    missing = test.drop(columns=["f_sparse", "f_history"])
    x = model.design.transform(missing)
    assert np.isfinite(x).all()
    assert (x[:, 1] == 1).all() and (x[:, 3] == 1).all()
    assert np.isfinite(summarize(model, missing)["mean"]).all()


def test_serialization_refit_and_batch_partition_replay_are_deterministic(tmp_path):
    train, test, category = fictional()
    model = ThresholdCDFModel.fit(train, category, "context")
    original = summarize(model, test, batch_size=3)
    manifest = model.save(tmp_path / "artifact")
    artifact = tmp_path / "artifact" / "model.joblib"
    assert manifest["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    restored = joblib.load(artifact)
    pd.testing.assert_frame_equal(original, summarize(restored, test, batch_size=128))
    pd.testing.assert_frame_equal(original, summarize(ThresholdCDFModel.fit(train, category, "context"), test))
    pd.testing.assert_frame_equal(restored.training_binding, model.training_binding)
    assert json.loads((tmp_path / "artifact" / "manifest.json").read_text())["law_arithmetic_version"] == STABLE_MIXTURE_VERSION
    assert restored.audit == model.audit


def test_blocked_category_unregistered_target_and_label_feature_are_rejected():
    train, _, category = fictional()
    blocked = copy.deepcopy(category)
    blocked["state"] = "BLOCKED_LABEL_CONTRACT"
    with pytest.raises(ValueError, match="blocked"):
        ThresholdCDFModel.fit(train, blocked, "base")
    unregistered = copy.deepcopy(category)
    unregistered["target"] = "made_up_count"
    with pytest.raises(ValueError, match="registered threshold"):
        ThresholdCDFModel.fit(train, unregistered, "base")
    leaking = copy.deepcopy(category)
    leaking["panels"] = {"base": ["f_actual"], "context": ["f_actual"]}
    with pytest.raises(ValueError, match="unqualified"):
        ThresholdCDFModel.fit(train, leaking, "base")
