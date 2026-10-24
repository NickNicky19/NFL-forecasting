"""Pure fictional arithmetic/mocked inference; no native fit or NFL input."""
import numpy as np
import pytest

from nfl_lab import direct_boosters as direct
from nfl_lab.direct_binary_canonical_v2 import canonical_binary_vector, derive_model, prediction_rows
from test_cdf_engine import fictional


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
@pytest.mark.parametrize("labels", [[0, 1], [1, 0]])
def test_canonical_vector_retains_event_bits_and_strict_dtype_complement(dtype, labels):
    p = np.array([0., .2, .3, .9, 1.], dtype=dtype)
    raw = np.column_stack([1-p, p])
    if labels == [1, 0]: raw = raw[:, ::-1]
    original = raw.copy()
    result = canonical_binary_vector(raw, labels)
    event = labels.index(1)
    np.testing.assert_array_equal(result[:, event], p.astype(float))
    np.testing.assert_array_equal(result[:, 1-event], 1.-p.astype(float))
    np.testing.assert_array_equal(raw, original)
    assert result.sum(axis=1).tolist() == [1.]*len(p)


def test_float32_failure_reproduced_without_any_model_or_nfl_values():
    p = np.array([.2], dtype=np.float32)
    raw = np.column_stack([1-p, p])
    assert not np.allclose(raw.astype(float).sum(axis=1), 1., rtol=0, atol=1e-12)
    result = canonical_binary_vector(raw, [0, 1])
    assert result[0, 1] == float(p[0]) and result.sum() == 1.


@pytest.mark.parametrize("raw,classes", [
    ([[.2, .2]], [0, 1]), ([[1.01, -.01]], [0, 1]), ([[np.nan, .2]], [0, 1]),
    ([[np.inf, .2]], [0, 1]), ([[.8, .2]], [1, 2]), ([[.8, .2]], [0, 0]),
    ([[1, 0]], [0, 1]), ([.8, .2], [0, 1]), ([[.8, .2, .0]], [0, 1])])
def test_invalid_native_vectors_are_rejected_without_tolerance_or_clipping(raw, classes):
    with pytest.raises(ValueError): canonical_binary_vector(np.array(raw), classes)


def test_derived_model_keeps_estimator_and_bindings_and_original_failure(monkeypatch):
    train, query, category = fictional()
    category = dict(category, target="anytime_td", support="bernoulli")
    train["anytime_td"] = (np.arange(len(train)) % 3 == 0).astype(float)
    train["rush_td"], train["rec_td"] = train.anytime_td, 0.
    class Native:
        classes_ = np.array([0, 1])
        def fit(self, x, y): return self
        def predict_proba(self, x):
            p = np.full(len(x), .2, dtype=np.float32)
            return np.column_stack([1-p, p])
    monkeypatch.setattr(direct, "installed_version", lambda library: "fictional")
    monkeypatch.setattr(direct, "native_estimator", lambda *args: Native())
    parent = direct.DirectBoosterModel.fit(train, category, "base", library="xgboost", complexity="small",
        expected_version="fictional", fit_gate=lambda attempt: None)
    with pytest.raises(ValueError, match="simplex"): direct.prediction_rows(parent, query)
    derived = derive_model(parent)
    assert parent.audit["version"] == direct.VERSION
    assert derived.estimator.estimator is parent.estimator.estimator
    assert derived.training_binding is parent.training_binding and derived.design is parent.design
    rows = prediction_rows(derived, query.drop(columns="participation_state"))
    assert rows.point.eq(float(np.float32(.2))).all()
    assert rows.method.eq("direct_xgboost_binary_canonical_v2_small").all()
    with pytest.raises(ValueError, match="simplex"): direct.prediction_rows(parent, query)


def test_boundary_event_probabilities_stay_exact_without_logloss_clipping():
    raw = np.array([[1., 0.], [0., 1.]], dtype=np.float32)
    result = canonical_binary_vector(raw, [0, 1])
    with np.errstate(divide="ignore"):
        contrary_losses = -np.log([result[0, 1], result[1, 0]])
    assert np.isposinf(contrary_losses).all()


def test_one_ulp_native_complement_difference_is_rejected():
    p = np.array([.2], dtype=np.float32)
    raw = np.column_stack([1-p, p])
    raw[0, 0] = np.nextafter(raw[0, 0], np.float32(0.))
    with pytest.raises(ValueError, match="exact dtype complement"):
        canonical_binary_vector(raw, [0, 1])


def test_derivative_has_no_fit_or_inherited_save_api(tmp_path):
    from nfl_lab.direct_binary_canonical_v2 import CanonicalDerivedModel
    with pytest.raises(RuntimeError, match="no new fit"):
        CanonicalDerivedModel.fit()
    _, _, category = fictional()
    model = CanonicalDerivedModel(category, "base")
    with pytest.raises(ValueError, match="inherited save forbidden"):
        model.save(tmp_path / "unversioned")
    assert not (tmp_path / "unversioned").exists()


@pytest.mark.parametrize("field,value", [("library", "lightgbm"), ("support", "count")])
def test_wrapper_metadata_disagreement_is_rejected(field, value):
    _, _, category = fictional()
    category = dict(category, target="anytime_td", support="bernoulli")
    parent = direct.DirectBoosterModel(category, "base", library="xgboost")
    parent.audit = {"fit_state": "FITTED", "version": direct.VERSION}
    parent.estimator = direct.NativeOutput(None, "xgboost", "bernoulli")
    setattr(parent.estimator, field, value)
    with pytest.raises(ValueError, match="fitted XGBoost"):
        derive_model(parent)
