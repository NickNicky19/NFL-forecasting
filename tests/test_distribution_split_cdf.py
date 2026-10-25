"""Generated fictional software checks only; no NFL rows or accuracy claims."""
import copy
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from nfl_lab.cdf_engine import LeafCDFModel, TREE_PARAMETERS, valid_support
from nfl_lab.distribution_split_cdf import (
    DistributionSplitCDFModel, VERSION, cdf_split_response, threshold_weights,
)
from nfl_lab.threshold_cdf import THRESHOLD_GRIDS


def fictional(target="pass_att", support="count", n=180):
    signal = np.arange(n) % 6
    labels = ((np.arange(n) * 7) % 13).astype(float)
    if support == "signed_integer":
        labels -= 6
    train = pd.DataFrame({
        "season": 2020, "week": np.arange(n) // 12 + 1,
        "game_id": ["fictional-game-" + str(i) for i in range(n)],
        "player_id": ["fictional-player-" + str(i % 9) for i in range(n)],
        "position": "QB", "participation_state": "played", target: labels,
        "f_signal": signal.astype(float), "f_sparse": np.where(signal > 2, signal, np.nan),
        "f_all_missing": np.nan, "f_player_games_prior": 5.,
    })
    category = {"target": target, "state": "READY", "support": support,
                "modeled_roles": ["QB"], "primary_roles": ["QB"],
                "panels": {"base": ["f_signal", "f_all_missing"],
                           "context": ["f_signal", "f_all_missing", "f_sparse"]}}
    return train, train.iloc[:8].copy(), category


def summarize(model, query):
    result = np.empty((len(query), 4))
    reasons = np.empty(len(query), dtype=object)
    for indices, law, fallback in model.predict_batches(query, batch_size=3):
        reasons[indices] = fallback
        if law is None:
            result[indices] = np.nan
        else:
            result[indices] = np.column_stack([law.mean, law.quantile(.5), law.cdf(0), law.logpmf(0)])
    return result, reasons


def test_trapezoid_weight_endpoints_interiors_and_normalization():
    np.testing.assert_allclose(threshold_weights([0, 2, 6]), [1/6, 1/2, 1/3], rtol=0, atol=1e-16)
    for grid in THRESHOLD_GRIDS.values():
        assert np.all(threshold_weights(grid) > 0)
        assert threshold_weights(grid).sum() == pytest.approx(1.)
    for bad in ([], [1], [2, 1], [1, 1], [0, np.nan], [[0, 1]]):
        with pytest.raises(ValueError):
            threshold_weights(bad)


def test_embedding_separates_same_mean_different_spread_and_rejects_invalid_labels():
    wide = np.tile([-6., 6.], 60)
    narrow = np.zeros(120)
    assert wide.mean() == narrow.mean()
    assert not np.allclose(cdf_split_response(wide, [-10, 0, 10]).mean(axis=0),
                           cdf_split_response(narrow, [-10, 0, 10]).mean(axis=0))
    for bad in ([.5], [np.nan], [np.inf], [[0, 1]]):
        with pytest.raises(ValueError):
            cdf_split_response(bad, [0, 1])


def test_distribution_response_has_positive_split_gain_for_equal_means():
    train, query, category = fictional("rush_yd", "signed_integer", 240)
    train["f_signal"] = np.repeat([0., 1.], 120)
    train["rush_yd"] = np.r_[np.tile([-6., 6.], 60), np.zeros(120)]
    mean_model = LeafCDFModel.fit(train, category, "base")
    model = DistributionSplitCDFModel.fit(train, category, "base")
    def root_gain(estimator):
        tree = estimator.tree_
        left, right = tree.children_left[0], tree.children_right[0]
        if left == -1:
            return 0.
        return tree.impurity[0] - sum(tree.weighted_n_node_samples[j] * tree.impurity[j]
                                     for j in (left, right)) / tree.weighted_n_node_samples[0]
    # sklearn may retain a zero-improvement partition. Compare its objective
    # directly: equal means give zero numeric gain, while the CDF gain is positive.
    assert all(abs(root_gain(tree)) < 1e-12 for tree in mean_model.forest.estimators_)
    assert all(root_gain(tree) > 1e-8 for tree in model.forest.estimators_)
    assert model.forest.n_outputs_ == len(THRESHOLD_GRIDS["rush_yd"])
    assert model.forest.get_params() == mean_model.forest.get_params()
    query["f_signal"] = np.resize([0., 1.], len(query))
    values, reasons = summarize(model, query)
    assert not reasons.any()
    assert not np.allclose(values[::2, 2], values[1::2, 2])


@pytest.mark.parametrize("target,support", [("pass_att", "count"), ("rush_yd", "signed_integer")])
def test_leaf_histograms_keep_actual_labels_and_shared_design_priors(target, support):
    train, query, category = fictional(target, support)
    model = DistributionSplitCDFModel.fit(train, category, "context")
    incumbent = LeafCDFModel.fit(train, category, "context")
    assert model.design == incumbent.design
    assert model.global_prior == incumbent.global_prior and model.priors == incumbent.priors
    pd.testing.assert_frame_equal(model.training_binding, incumbent.training_binding)
    pd.testing.assert_frame_equal(model.prior_training_binding, incumbent.prior_training_binding)
    np.testing.assert_array_equal(model.support, np.unique(train[target]))
    assert 0 in model.support
    assert valid_support(model.support, support).all()
    if support == "signed_integer":
        assert (model.support < 0).any()
    for j, tree in enumerate(model.forest.estimators_):
        leaves = model.training_leaf_ids[:, j]
        for leaf in np.unique(leaves):
            counts = np.bincount(np.searchsorted(model.support, train[target].to_numpy()[leaves == leaf]), minlength=len(model.support))
            np.testing.assert_allclose(model.leaf_histograms[j][leaf].toarray()[0], counts/counts.sum(), rtol=0, atol=0)
    assert model.audit["tree_parameters"] == TREE_PARAMETERS
    assert model.audit["prior_weight"] == .05
    assert model.audit["split_thresholds"] == list(THRESHOLD_GRIDS[target])
    assert "not_exact_DRF_or_MMD" in model.audit["method_identity"]
    json.dumps(model.audit, allow_nan=False)


def test_unknown_dnp_missing_invalid_and_played_zero_labels_remain_distinct():
    train, query, category = fictional()
    train.loc[0, "participation_state"] = "unknown"
    train.loc[1, "participation_state"] = "DNP"
    train.loc[2, "pass_att"] = np.nan
    train.loc[3, "pass_att"] = -1
    train.loc[4, "pass_att"] = 1.5
    model = DistributionSplitCDFModel.fit(train, category, "base")
    assert model.audit["supported_played_training_rows"] == len(train)-5
    assert model.audit["played_missing_outcome"] == 1
    assert model.audit["played_invalid_support"] == 2
    assert model.training_binding.pass_att.eq(0).any()
    assert len(model.prior_training_binding) == len(train)-5


def test_cold_nonmodeled_unseen_role_fallbacks_and_query_labels_unread():
    train, query, category = fictional()
    train.loc[train.index[-20:], "position"] = "WR"
    model = DistributionSplitCDFModel.fit(train, category, "base")
    query.loc[query.index[0], "f_player_games_prior"] = 0
    query.loc[query.index[1], "position"] = "WR"
    query.loc[query.index[2], "position"] = "UNSEEN"
    first, reasons = summarize(model, query)
    assert list(reasons[:3]) == ["cold_start_role_prior", "nonmodeled_role_prior", "global_prior_unknown_role"]
    assert first[0, 0] == model.priors["QB"].mean
    assert first[1, 0] == model.priors["WR"].mean
    assert first[2, 0] == model.global_prior.mean
    query["pass_att"] = "DO_NOT_READ_QUERY_OUTCOME"
    query["participation_state"] = "DNP"
    again, again_reasons = summarize(model, query)
    np.testing.assert_array_equal(first, again)
    np.testing.assert_array_equal(reasons, again_reasons)
    _, missing_reasons = summarize(model, query.drop(columns="f_player_games_prior"))
    assert missing_reasons[0] == "cold_start_role_prior"


@pytest.mark.parametrize("target,support", [("pass_att", "count"), ("rush_yd", "signed_integer")])
def test_full_predictive_law_has_mass_moments_crps_zero_and_legal_quantiles(target, support):
    train, query, category = fictional(target, support)
    model = DistributionSplitCDFModel.fit(train, category, "base")
    _, law, reasons = next(model.predict_batches(query.iloc[:1]))
    assert not reasons.any() and law.b == .05
    grid = np.arange(0 if support == "count" else -700, 701)
    mass = np.array([np.exp(law.logpmf(k))[0] for k in grid])
    cumulative = np.array([law.cdf(k)[0] for k in grid])
    assert (np.diff(cumulative) >= -1e-15).all()
    assert ((cumulative >= 0) & (cumulative <= 1+1e-12)).all()
    assert mass.sum() == pytest.approx(1., abs=2e-12)
    assert mass @ grid == pytest.approx(law.mean[0], abs=2e-10)
    assert np.isfinite(law.logpmf(0)[0])
    assert law.crps(0)[0] == pytest.approx(np.sum((cumulative-(grid >= 0))**2), abs=2e-10)
    for probability in [.001, .1, .5, .9, .999]:
        q = law.quantile(probability)
        assert valid_support(q, support).all()
        assert (law.cdf(q) >= probability).all()
        assert (law.cdf(q-1) < probability).all()
    if support == "count":
        assert law.cdf(-1)[0] == 0 and np.isneginf(law.logpmf(-1)[0])


def test_repeatability_and_shared_serialization_replay(tmp_path):
    train, query, category = fictional()
    model = DistributionSplitCDFModel.fit(train, category, "context")
    repeated = DistributionSplitCDFModel.fit(train, category, "context")
    np.testing.assert_array_equal(model.training_leaf_ids, repeated.training_leaf_ids)
    first, reasons = summarize(model, query)
    np.testing.assert_array_equal(first, summarize(repeated, query)[0])
    manifest = model.save(tmp_path/"fictional-model")
    assert manifest["version"] == VERSION and manifest["audit"]["version"] == VERSION
    loaded = joblib.load(tmp_path/"fictional-model/model.joblib")
    np.testing.assert_array_equal(first, summarize(loaded, query)[0])
    np.testing.assert_array_equal(reasons, summarize(loaded, query)[1])
    pd.testing.assert_frame_equal(model.training_binding, loaded.training_binding)


def test_no_supported_or_sparse_training_uses_shared_abstention_or_prior():
    train, query, category = fictional()
    train["pass_att"] = np.nan
    model = DistributionSplitCDFModel.fit(train, category, "base")
    values, reasons = summarize(model, query)
    assert np.isnan(values).all() and np.all(reasons == "no_supported_played_training_outcomes")
    train["pass_att"] = 0
    sparse_model = DistributionSplitCDFModel.fit(train.iloc[:30], category, "base")
    values, reasons = summarize(sparse_model, query)
    assert sparse_model.forest is None and np.isfinite(values).all()
    assert np.all(reasons == "insufficient_modeled_training_role_prior")


def test_anytime_alias_and_exact_ppr_never_start_a_new_estimator(monkeypatch):
    import nfl_lab.distribution_split_cdf as module
    def forbidden(*args, **kwargs):
        raise AssertionError("unchanged/blocked category entered estimator construction")
    monkeypatch.setattr(module, "ExtraTreesRegressor", forbidden)
    train, _, category = fictional()
    td = copy.deepcopy(category)
    td.update(target="anytime_td", support="bernoulli")
    with pytest.raises(ValueError, match="UNCHANGED.*zero new fit"):
        DistributionSplitCDFModel.fit(train, td, "base")
    ppr = copy.deepcopy(category)
    ppr.update(target="fantasy_ppr", support="signed_integer")
    with pytest.raises(ValueError, match="PPR.*label-blocked"):
        DistributionSplitCDFModel.fit(train, ppr, "base")
    ppr["state"] = "BLOCKED_LABEL_CONTRACT"
    with pytest.raises(ValueError, match="blocked"):
        DistributionSplitCDFModel.fit(train, ppr, "base")
