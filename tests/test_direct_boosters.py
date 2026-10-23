"""Mocked engineering checks only; no NFL data or native booster fits."""
from io import BytesIO
import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from nfl_lab import direct_boosters as db
from test_cdf_engine import fictional


class FakeNative:
    classes_ = np.array([0., 1.])

    def __init__(self, support="count", params=None):
        self.support, self.params = support, params
        self.x = self.y = None

    def fit(self, x, y):
        self.x, self.y = x.copy(), y.copy()
        return self

    def predict(self, x, **kwargs):
        self.predict_kwargs = kwargs
        return np.full(len(x), -3.25 if self.support == "signed_integer" else 2.5)

    def predict_proba(self, x):
        return np.tile([.7, .3], (len(x), 1))


@pytest.fixture(autouse=True)
def mock_optional_packages(monkeypatch):
    monkeypatch.setattr(db, "installed_version", lambda library: "fictional-1")
    monkeypatch.setattr(db, "native_estimator", lambda library, support, params: FakeNative(support, params))


def fitted(support="count", library="xgboost", complexity="small", transform=None):
    train, query, category = fictional()
    if support == "signed_integer":
        train["pass_att"] = -train.pass_att
    elif support == "bernoulli":
        train["pass_att"] = np.arange(len(train)) % 3 == 0
    category = dict(category, support=support)
    if transform:
        train, query, category = transform(train, query, category)
    calls = []
    model = db.DirectBoosterModel.fit(train, category, "base", library=library,
        complexity=complexity, expected_version="fictional-1", fit_gate=calls.append)
    return model, train, query, calls


@pytest.mark.parametrize("library", db.LIBRARIES)
@pytest.mark.parametrize("complexity", db.COMPLEXITIES)
@pytest.mark.parametrize("support,metric", [("count", "MSE"), ("signed_integer", "MAE"), ("bernoulli", "Brier")])
def test_exact_objective_products_and_no_invented_numeric_law(library, complexity, support, metric):
    model, _, query, gates = fitted(support, library, complexity)
    assert len(gates) == 1 and model.audit["fit_state"] == "FITTED"
    assert model.estimator.estimator.params == db.parameters(library, complexity, support)
    rows = db.prediction_rows(model, query)
    assert rows.primary_metric.eq(metric).all()
    assert rows.method.eq("direct_" + library + "_" + complexity).all()
    assert rows.package_version.eq("fictional-1").all()
    assert rows.point.eq(.3 if support == "bernoulli" else -3.25 if support == "signed_integer" else 2.5).all()
    assert rows.participation_state.eq("unread").all() and rows.actual.isna().all()
    assert not {"mean", "median", "cdf", "variance", "crps", "p10", "p90"} & set(rows)
    if support == "bernoulli":
        assert rows.distribution.eq("bernoulli").all() and rows.probability.eq(.3).all()
    else:
        assert rows.distribution.eq("none_point_heuristic").all() and rows.probability.isna().all()
    if library == "catboost" and support == "count":
        assert model.estimator.estimator.predict_kwargs == {"prediction_type": "Exponent"}


def test_fixed_settings_are_cpu_only_and_no_eval_year_selection():
    for library in db.LIBRARIES:
        small = db.parameters(library, "small", "count")
        medium = db.parameters(library, "medium", "count")
        assert not {"early_stopping_rounds", "eval_set", "callbacks"} & set(small)
        if library == "catboost":
            assert (small["iterations"], medium["iterations"], small["depth"], medium["depth"]) == (64, 128, 3, 5)
            assert small["task_type"] == "CPU" and small["thread_count"] == 2
            assert small["allow_writing_files"] is False and small["use_best_model"] is False
        else:
            assert (small["n_estimators"], medium["n_estimators"], small["max_depth"], medium["max_depth"]) == (64, 128, 3, 5)
            assert small["n_jobs"] == 2
        assert small["learning_rate"] == .05


def test_training_only_imputation_and_no_query_labels_participation_reads():
    def change(train, query, category):
        train.loc[:20, "f_player_pass_att_mean3"] = np.nan
        return train, query, category
    model, train, query, _ = fitted(transform=change)
    assert model.design.medians[0] == train.f_player_pass_att_mean3.median()
    assert model.design.roles == ["QB"]
    before = db.prediction_rows(model, query)
    query["pass_att"], query["participation_state"] = 999999, "DNP"
    query["outcome_state"] = "invented"
    pd.testing.assert_frame_equal(before, db.prediction_rows(model, query))
    pd.testing.assert_frame_equal(before, db.prediction_rows(model, query.drop(columns=["pass_att", "participation_state", "outcome_state"])))


def test_supported_zeros_invalid_missing_and_unknown_are_distinct():
    def change(train, query, category):
        train.loc[:4, "pass_att"] = [0., np.nan, -1., 1.5, 4.]
        train.loc[4, "participation_state"] = "unknown"
        return train, query, category
    model, train, _, _ = fitted(transform=change)
    assert model.audit["supported_played_training_rows"] == len(train) - 4
    assert model.audit["played_missing_outcome"] == 1
    assert model.audit["played_invalid_support"] == 2
    assert 0. in model.estimator.estimator.y
    assert len(model.prior_training_binding) == len(train) - 4


def test_count_fallbacks_are_prior_means_including_unknown_and_new_roles():
    def change(train, query, category):
        train.loc[train.index[-20:], "position"] = "WR"
        query.loc[query.index[:4], "position"] = ["QB", "WR", "TE", "QB"]
        query.loc[query.index[3], "f_player_games_prior"] = 0
        return train, query, category
    model, _, query, _ = fitted(transform=change)
    rows = db.prediction_rows(model, query)
    assert rows.fallback.iloc[:4].tolist() == ["", "nonmodeled_role_prior", "global_prior_unknown_role", "cold_start_role_prior"]
    assert rows.point.iloc[1] == model.priors["WR"].mean
    assert rows.point.iloc[2] == model.global_prior.mean
    assert rows.point.iloc[3] == model.priors["QB"].mean
    assert db.prediction_rows(model, query, prior_only=True).point.iloc[0] == model.priors["QB"].mean
    assert db.prediction_rows(model, query.drop(columns="f_player_games_prior")).fallback.iloc[0] == "cold_start_role_prior"


@pytest.mark.parametrize("kind,state,reason", [
    ("empty", "NO_SUPPORTED_TRAINING_LABELS", "no_supported_played_training_outcomes"),
    ("small", "INSUFFICIENT_MODELED_TRAINING", "insufficient_modeled_training_role_prior"),
    ("zeros", "ALL_ZERO_COUNT_ROLE_PRIOR", "all_zero_count_role_prior"),
    ("binary", "SINGLE_CLASS_BINARY_ROLE_PRIOR", "single_class_binary_role_prior")])
def test_no_estimator_for_empty_small_allzero_or_singleclass(kind, state, reason):
    train, query, category = fictional()
    if kind == "empty":
        train["pass_att"] = np.nan
    elif kind == "small":
        train = train.iloc[:30]
    else:
        train["pass_att"] = 0
    if kind == "binary":
        category = dict(category, support="bernoulli")
    gates = []
    model = db.DirectBoosterModel.fit(train, category, "base", library="catboost", complexity="small",
                                     expected_version="fictional-1", fit_gate=gates.append)
    assert gates == [] and model.estimator is None and model.audit["fit_state"] == state
    rows = db.prediction_rows(model, query)
    assert rows.fallback.eq(reason).all()
    assert rows.point.isna().all() if kind == "empty" else np.isfinite(rows.point).all()
    if kind == "zeros":
        assert rows.point.eq(model.priors["QB"].mean).all()


def test_fit_gate_consumed_before_construction_and_failure_stops(monkeypatch):
    train, _, category = fictional()
    events = []
    def gate(slot):
        events.append(slot)
        raise RuntimeError("budget exhausted")
    monkeypatch.setattr(db, "native_estimator", lambda *args: pytest.fail("constructed after failed gate"))
    with pytest.raises(RuntimeError, match="exhausted"):
        db.DirectBoosterModel.fit(train, category, "base", library="xgboost", complexity="small",
                                 expected_version="fictional-1", fit_gate=gate)
    assert len(events) == 1


@pytest.mark.parametrize("change", ["version", "gate", "library", "complexity", "panel", "blocked"])
def test_unregistered_or_incompatible_contracts_fail_before_estimator(change, monkeypatch):
    train, _, category = fictional()
    args = dict(library="lightgbm", complexity="small", expected_version="fictional-1", fit_gate=lambda slot: None)
    panel = "base"
    if change == "version": args["expected_version"] = "other"
    if change == "gate": args["fit_gate"] = None
    if change == "library": args["library"] = "other"
    if change == "complexity": args["complexity"] = "unlimited"
    if change == "panel": panel = "other"
    if change == "blocked": category = dict(category, state="BLOCKED")
    monkeypatch.setattr(db, "native_estimator", lambda *args: pytest.fail("invalid contract constructed estimator"))
    with pytest.raises(ValueError):
        db.DirectBoosterModel.fit(train, category, panel, **args)


@pytest.mark.parametrize("value,match", [(-.01, "negative"), (np.nan, "nonfinite"), (np.inf, "nonfinite")])
def test_invalid_count_native_output_is_rejected_before_old_floor(value, match):
    model, _, query, _ = fitted()
    model.estimator.estimator.predict = lambda x: np.full(len(x), value)
    with pytest.raises(ValueError, match=match):
        db.prediction_rows(model, query)


def test_wrong_shape_and_invalid_probability_fail_without_clipping():
    model, _, query, _ = fitted()
    model.estimator.estimator.predict = lambda x: np.ones((len(x), 1))
    with pytest.raises(ValueError, match="shape"):
        model.predict(query)
    model, _, query, _ = fitted("bernoulli")
    for values in [[-.01, 1.01], [.2, .2], [np.nan, .5]]:
        model.estimator.estimator.predict_proba = lambda x: np.tile(values, (len(x), 1))
        with pytest.raises(ValueError, match="simplex|nonfinite"):
            model.predict(query)


def test_scoring_preserves_zero_missing_unknown_and_boundary_losses():
    model, _, query, _ = fitted("bernoulli")
    frozen = db.prediction_rows(model, query)
    query["pass_att"] = 1.
    query.loc[query.index[:3], "pass_att"] = [0., np.nan, 0.]
    query.loc[query.index[2], "participation_state"] = "unknown"
    frozen["point"], frozen["probability"] = 0., 0.
    scored = db.score_frozen_rows(query, frozen, model.category)
    assert scored.outcome_state.iloc[:3].tolist() == ["played_zero", "played_missing_statistic", "unknown"]
    assert scored.brier.iloc[0] == 0. and scored.brier.iloc[1:3].isna().all()
    assert np.isposinf(scored.log_score.iloc[3:]).all()
    with pytest.raises(ValueError, match="identity"):
        db.score_frozen_rows(query.iloc[::-1], frozen, model.category)


def test_model_artifacts_use_only_supplied_storage_and_replay(tmp_path):
    model, _, query, _ = fitted()
    class MemoryStorage:
        def __init__(self): self.bodies = {}
        def write_bytes(self, path, body): self.bodies[path] = body
    storage = MemoryStorage()
    with pytest.raises(ValueError, match="quota"):
        model.save(tmp_path / "without-storage")
    assert not (tmp_path / "without-storage").exists()
    target = tmp_path / "private-model"
    manifest = model.save(target, storage=storage)
    assert not target.exists()
    body = storage.bodies[target / "model.joblib"]
    assert manifest["sha256"] == hashlib.sha256(body).hexdigest()
    assert json.loads(storage.bodies[target / "manifest.json"])["bytes"] == len(body)
    restored = joblib.load(BytesIO(body))
    pd.testing.assert_frame_equal(db.prediction_rows(model, query), db.prediction_rows(restored, query))
    pd.testing.assert_frame_equal(model.training_binding, restored.training_binding)
