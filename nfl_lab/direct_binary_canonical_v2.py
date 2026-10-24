"""Strict native-dtype complement validation; the event probability is unchanged.

This is a new software version, never a mutation of the original failed screen.
There is no estimator fit or outcome loading here.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, fields

import numpy as np

from .direct_boosters import DirectBoosterModel, NativeOutput, prediction_rows as parent_rows

VERSION = "direct-xgboost-binary-canonical-v2-20261023"


def canonical_binary_vector(native, classes):
    """Validate the exact rounded complement, then use the scalar event p."""
    raw = np.asarray(native)
    labels = np.asarray(classes)
    if raw.dtype not in (np.dtype("float32"), np.dtype("float64")):
        raise ValueError("native binary probabilities require float32/64")
    if labels.shape != (2,) or set(labels.tolist()) != {0, 1}:
        raise ValueError("exact binary class identities required")
    if raw.ndim != 2 or raw.shape[1] != 2 or not np.isfinite(raw).all():
        raise ValueError("invalid native binary shape/nonfinite values")
    if ((raw < 0) | (raw > 1)).any():
        raise ValueError("native probability outside [0,1]")
    event = list(labels).index(1)
    other = 1 - event
    native_complement = np.ones_like(raw[:, event]) - raw[:, event]
    if not np.array_equal(raw[:, other], native_complement):
        raise ValueError("native non-event probability is not its exact dtype complement")
    result = raw.astype(np.float64)
    result[:, other] = 1. - result[:, event]
    if not np.allclose(result.sum(axis=1), 1., rtol=0, atol=1e-12):
        raise ValueError("canonical probability is outside simplex")
    return result


@dataclass
class CanonicalXGBBinaryOutput(NativeOutput):
    def predict_proba(self, x):
        if self.library != "xgboost" or self.support != "bernoulli":
            raise ValueError("canonical repair is only for XGBoost binary outputs")
        native = self.estimator.predict_proba(x)
        result = canonical_binary_vector(native, self.classes_)
        if result.shape != (len(x), 2):
            raise ValueError("native binary row count differs")
        return result


class CanonicalDerivedModel(DirectBoosterModel):
    @classmethod
    def fit(cls, *args, **kwargs):
        raise RuntimeError("binary derivative has no new fit API")

    def save(self, *args, **kwargs):
        raise ValueError("binary derivative requires its own versioned parent-binding manifest; inherited save forbidden")


def derive_model(parent):
    """Copy the wrapper/audit; share the unchanged fitted native estimator."""
    if (type(parent) is not DirectBoosterModel or parent.library != "xgboost"
            or parent.category.get("support") != "bernoulli" or parent.category.get("target") != "anytime_td"
            or type(parent.estimator) is not NativeOutput or parent.estimator.library != "xgboost"
            or parent.estimator.support != "bernoulli" or parent.audit.get("fit_state") != "FITTED"):
        raise ValueError("frozen fitted XGBoost anytime model required")
    result = CanonicalDerivedModel(**{field.name: getattr(parent, field.name) for field in fields(parent)})
    result.audit = copy.deepcopy(parent.audit)
    result.audit["parent_version"] = result.audit["version"]
    result.audit["version"] = VERSION
    result.audit["binary_output"] = "Exact native-dtype complement checked; only non-event component canonicalized; event p bits unchanged"
    result.estimator = CanonicalXGBBinaryOutput(parent.estimator.estimator, "xgboost", "bernoulli")
    return result


def prediction_rows(model, frame):
    if not isinstance(model.estimator, CanonicalXGBBinaryOutput) or model.audit.get("version") != VERSION:
        raise ValueError("separately derived binary version required")
    rows = parent_rows(model, frame)
    rows["model_version"] = VERSION
    rows["method"] = "direct_xgboost_binary_canonical_v2_" + model.complexity
    return rows
