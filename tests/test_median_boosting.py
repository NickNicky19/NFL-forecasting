"""Fictional engineering checks; these contain no football accuracy evidence."""
import joblib
import numpy as np
import pandas as pd
import pytest

from nfl_lab.median_boosting import (DESIGN, PARAMETERS, MedianBoostingModel,
    equalweight_rows, prediction_rows, prior_point, score_frozen_rows)
from test_cdf_engine import fictional


def test_point_model_is_fixed_mae_objective_and_replays_without_numeric_law(tmp_path):
    train, query, category = fictional()
    model = MedianBoostingModel.fit(train, category, "context")
    assert model.estimator.loss == "absolute_error"
    assert all(model.estimator.get_params()[k] == v for k, v in PARAMETERS.items())
    assert model.audit["fitted_iterations"] == 150
    frozen = prediction_rows(model, query)
    assert not {"mean", "median", "p10", "p90", "crps", "variance"} & set(frozen)
    assert frozen.distribution.eq("none_point_heuristic").all()
    assert frozen.probability.isna().all()
    assert np.isfinite(frozen.point).all() and frozen.point.ge(0).all()
    model.save(tmp_path / "model")
    restored = joblib.load(tmp_path / "model/model.joblib")
    pd.testing.assert_frame_equal(frozen, prediction_rows(restored, query))
    assert restored.training_binding.equals(model.training_binding)
    assert restored.prior_training_binding.equals(model.prior_training_binding)


def test_training_only_transform_and_no_query_label_or_participation_access():
    train, query, category = fictional()
    train.loc[:20, "f_player_pass_att_mean3"] = np.nan
    model = MedianBoostingModel.fit(train, category, "base")
    expected = train.f_player_pass_att_mean3.median()
    assert model.design.medians[0] == expected
    frozen = prediction_rows(model, query)
    query["pass_att"], query["participation_state"] = 999999, "DNP"
    pd.testing.assert_frame_equal(frozen, prediction_rows(model, query))
    assert model.design.medians[0] == expected and model.design.roles == ["QB"]


def test_fallbacks_use_inherited_trained_prior_median_and_global_prior():
    train, query, category = fictional()
    train.loc[train.index[-20:], "position"] = "WR"
    model = MedianBoostingModel.fit(train, category, "base")
    query.loc[query.index[:3], "position"] = ["WR", "UNSEEN", "QB"]
    query.loc[query.index[2], "f_player_games_prior"] = 0
    result = prediction_rows(model, query)
    assert list(result.fallback[:3]) == ["nonmodeled_role_prior", "global_prior_unknown_role", "cold_start_role_prior"]
    assert result.point.iloc[0] == prior_point(model.priors["WR"])
    assert result.point.iloc[1] == prior_point(model.global_prior)
    assert result.point.iloc[2] == prior_point(model.priors["QB"])
    cold = prediction_rows(model, query.iloc[3:].drop(columns="f_player_games_prior"))
    assert cold.fallback.eq("cold_start_role_prior").all()
    assert len(model.training_binding) == 160 and len(model.prior_training_binding) == 180


def test_empty_insufficient_and_single_class_training_are_explicit():
    train, query, category = fictional()
    empty = MedianBoostingModel.fit(train.assign(pass_att=np.nan), category, "base")
    rows = prediction_rows(empty, query)
    assert rows.point.isna().all() and rows.fallback.eq("no_supported_played_training_outcomes").all()
    small = MedianBoostingModel.fit(train.iloc[:30], category, "base")
    assert small.audit["fit_state"] == "INSUFFICIENT_MODELED_TRAINING"
    assert prediction_rows(small, query).fallback.eq("insufficient_modeled_training_role_prior").all()
    category = dict(category, target="event", support="bernoulli")
    binary = MedianBoostingModel.fit(train.assign(event=0), category, "base")
    assert binary.audit["fit_state"] == "SINGLE_CLASS_BINARY_ROLE_PRIOR"
    result = prediction_rows(binary, query)
    assert result.fallback.eq("single_class_binary_role_prior").all()
    assert result.point.eq(1 / (len(train) + 2)).all()


def test_binary_classifier_is_genuine_probability_and_extreme_losses_are_not_clipped():
    train, query, category = fictional()
    category = dict(category, target="event", support="bernoulli")
    train["event"] = (np.arange(len(train)) % 3 == 0).astype(int)
    model = MedianBoostingModel.fit(train, category, "base")
    assert model.estimator.loss == "log_loss"
    frozen = prediction_rows(model, query)
    direct = model.estimator.predict_proba(model.design.transform(query))[:, list(model.estimator.classes_).index(1.)]
    np.testing.assert_array_equal(frozen.probability, direct)
    query["event"] = 1
    frozen["point"], frozen["probability"] = 0., 0.
    scored = score_frozen_rows(query, frozen, category)
    assert np.isposinf(scored.log_score).all() and scored.brier.eq(1).all()
    frozen["point"] = -1e-10
    with pytest.raises(ValueError, match="outside"):
        score_frozen_rows(query, frozen, category)


@pytest.mark.parametrize("support,expected", [("count", 0.), ("signed_integer", -3.25)])
def test_predeclared_count_floor_preserves_fractional_points_and_signed_negatives(support, expected):
    train, query, category = fictional()
    category = dict(category, support=support)
    if support == "signed_integer":
        train["pass_att"] = -train.pass_att
    model = MedianBoostingModel.fit(train, category, "base")
    class FixedEstimator:
        def predict(self, x):
            return np.full(len(x), -3.25)
    model.estimator = FixedEstimator()
    result = prediction_rows(model, query)
    assert result.point.eq(expected).all()
    if support == "count":
        class FractionalEstimator:
            def predict(self, x):
                return np.full(len(x), 2.125)
        model.estimator = FractionalEstimator()
        assert prediction_rows(model, query).point.eq(2.125).all()


def test_missing_invalid_dnp_unknown_and_played_zero_do_not_become_zero_outcomes():
    train, query, category = fictional()
    train.loc[:9, "participation_state"] = "DNP"
    train.loc[10:19, "participation_state"] = "unknown"
    train.loc[20:24, "pass_att"] = np.nan
    train.loc[25:29, "pass_att"] = -1
    model = MedianBoostingModel.fit(train, category, "base")
    assert model.audit["supported_played_training_rows"] == len(train) - 30
    query["pass_att"] = [0, 1, np.nan, -1, 1.5, 0, 0, 0, 0, 0, 0, 0]
    query.loc[query.index[5:7], "participation_state"] = ["DNP", "unknown"]
    frozen = prediction_rows(model, query)
    scored = score_frozen_rows(query, frozen, category)
    assert list(scored.outcome_state[:7]) == ["played_zero", "played_nonzero", "played_missing_statistic", "played_invalid_support", "played_invalid_support", "DNP", "unknown"]
    assert scored.absolute_error.iloc[2:7].isna().all()
    pd.testing.assert_series_equal(scored.point, frozen.point)
    with pytest.raises(ValueError, match="identity"):
        score_frozen_rows(query.iloc[::-1], frozen, category)


def test_only_fixed_website_blend_and_missing_site_abstains():
    train, query, category = fictional()
    frozen = prediction_rows(MedianBoostingModel.fit(train, category, "base"), query)
    offers = frozen.copy()
    offers["website_point"] = 4.
    offers.loc[offers.index[0], "website_point"] = np.nan
    blend = equalweight_rows(frozen, offers, category)
    assert np.isnan(blend.point.iloc[0])
    np.testing.assert_allclose(blend.point.iloc[1:], .5 * frozen.point.iloc[1:] + 2.)
    assert blend.point_semantics.eq("fixed_equalweight_point_heuristic_not_law_mean_or_median").all()
    assert blend.probability.isna().all()
    assert DESIGN["count_transform"].startswith("max(0")


def test_blocked_category_and_label_features_rejected():
    train, _, category = fictional()
    with pytest.raises(ValueError, match="blocked"):
        MedianBoostingModel.fit(train, dict(category, state="BLOCKED_LABEL_CONTRACT"), "base")
    category["panels"] = {"base": ["f_actual"], "context": ["f_actual"]}
    with pytest.raises(ValueError, match="unqualified"):
        MedianBoostingModel.fit(train, category, "base")
