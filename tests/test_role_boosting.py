"""Finite fictional estimator checks; no NFL fixture or inherited inference."""
import joblib
import numpy as np
import pandas as pd
import pytest

from nfl_lab.median_boosting import prior_point
from nfl_lab.role_boosting import RoleCountBoostingModel, package_kind, prediction_rows
from test_cdf_engine import fictional


def role_fixture(support="count"):
    train, query, category = fictional(240)
    train["position"] = np.repeat(["RB", "WR", "FB"], [100, 100, 40])
    train["pass_att"] = np.r_[np.arange(100) % 9, np.zeros(100), np.arange(40) % 3]
    train.loc[train.position.eq("RB"), "f_player_pass_att_mean3"] = 2.
    train.loc[train.position.eq("WR"), "f_player_pass_att_mean3"] = 100.
    query["position"] = ["RB", "WR", "FB", "TE", "unknown", "RB"] * 2
    query.loc[query.index[5], "f_player_games_prior"] = 0
    category = dict(category, support=support, modeled_roles=["RB", "WR", "FB"], primary_roles=["RB"])
    return train, query, category


def test_partition_priors_routing_zero_and_sparse_guards_and_persistence(tmp_path):
    train, query, category = role_fixture()
    consumed = []
    model = RoleCountBoostingModel.fit(train, category, "B", before_fit=consumed.append)
    assert len(consumed) == model.audit["fit_attempts"] == 1
    assert model.estimators["RB"].loss == "poisson"
    assert model.designs["RB"].medians[0] == 2.
    assert model.global_prior.n == 240 and model.priors["WR"].n == 100
    assert {r["role"]: r["state"] for r in model.audit["subfits"]} == {
        "RB": "FITTED", "WR": "ALL_ZERO_COUNT_ROLE_PRIOR", "FB": "INSUFFICIENT_MODELED_TRAINING_ROLE_PRIOR"}
    points, reasons = model.predict(query.drop(columns=["pass_att", "participation_state"]))
    assert np.isfinite(points).all() and (points >= 0).all()
    assert reasons[1] == "all_zero_count_role_prior" and points[1] == prior_point(model.priors["WR"])
    assert reasons[2] == "insufficient_modeled_training_role_prior"
    assert reasons[3] == reasons[4] == "global_prior_unknown_role"
    assert points[3] == prior_point(model.global_prior)
    assert reasons[5] == "cold_start_role_prior"
    frozen = prediction_rows(model, query)
    assert frozen.actual.isna().all() and frozen.participation_state.eq("unread").all()
    assert frozen.distribution.eq("none_point_heuristic").all()
    model.save(tmp_path / "model")
    loaded = joblib.load(tmp_path / "model/model.joblib")
    np.testing.assert_array_equal(loaded.predict(query)[0], points)


def test_pooled_constant_positive_poisson_fits_and_no_alias_refits():
    train, query, category = fictional()
    train["pass_att"] = 5
    model = RoleCountBoostingModel.fit(train, category, "A")
    assert model.audit["fit_attempts"] == 1
    np.testing.assert_allclose(model.predict(query)[0], 5., rtol=1e-6)
    assert prior_point(model.global_prior) != 5.
    with pytest.raises(ValueError, match="never refit"):
        RoleCountBoostingModel.fit(train, category, "B")
    category = dict(category, support="signed_integer")
    assert package_kind(category, "A") == "old_base_alias"
    assert package_kind(category, "B") == "A_alias"


def test_signed_and_binary_guards_preserve_support_without_numeric_laws():
    train, query, category = role_fixture("signed_integer")
    train["pass_att"] = np.r_[-(np.arange(100) % 9), np.full(100, -4), np.zeros(40)]
    model = RoleCountBoostingModel.fit(train, category, "B")
    assert model.audit["fit_attempts"] == 2  # constant signed target still fits
    assert (model.predict(query)[0] < 0).any()
    train, query, category = role_fixture("bernoulli")
    train["pass_att"] = (train.pass_att > 3).astype(float)
    model = RoleCountBoostingModel.fit(train, category, "B")
    assert model.audit["fit_attempts"] == 1
    assert model.audit["subfits"][1]["state"] == "SINGLE_CLASS_BINARY_ROLE_PRIOR"
    frozen = prediction_rows(model, query)
    assert frozen.point.between(0, 1).all() and frozen.distribution.eq("bernoulli").all()


def test_no_supported_labels_and_zero_count_never_call_optimizer():
    train, query, category = role_fixture()
    train["pass_att"] = np.nan
    model = RoleCountBoostingModel.fit(train, category, "B")
    assert model.audit["fit_attempts"] == 0 and np.isnan(model.predict(query)[0]).all()
    train["pass_att"] = 0
    model = RoleCountBoostingModel.fit(train, category, "A")
    assert not model.estimators and model.audit["fit_attempts"] == 0
    assert model.audit["subfits"][0]["state"] == "ALL_ZERO_COUNT_ROLE_PRIOR"


def test_attempt_callback_runs_before_optimizer_and_cannot_silently_retry():
    train, _, category = fictional()
    def reject(_):
        raise RuntimeError("consumed fictional failure")
    with pytest.raises(RuntimeError, match="consumed fictional failure"):
        RoleCountBoostingModel.fit(train, category, "A", before_fit=reject)
