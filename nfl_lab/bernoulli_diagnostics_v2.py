"""A separate analytic diagnostic view of an already frozen Bernoulli p.

No original score, probability, parameter, row or validator is changed. Only
four secondary diagnostic columns of one anytime-TD law frame are derived.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from .cdf_engine import KEYS, numeric, valid_support

VERSION = "canonical-bernoulli-diagnostics-v2"
POLICY_SHA256 = "72fb9c42f9d315b1241e0e6b7e48904427aeb20cfb9b5019f089a71f6541ecb0"
FIELDS = ("cdf_actual_below", "cdf_actual", "crps", "log_score")
METHODS = ("leaf_cdf", "role_prior")


class DiagnosticInputError(ValueError):
    """Rejected input; aggregate-only evidence remains available to the caller."""

    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def _same(left, right):
    return (left == right) | (np.isnan(left) & np.isnan(right))


def _states(values):
    return {"finite": np.isfinite(values), "missing": np.isnan(values),
        "positive_infinity": np.isposinf(values), "negative_infinity": np.isneginf(values)}


def _difference(raw, analytic):
    finite = np.isfinite(raw) & np.isfinite(analytic)
    transitions = {}
    for old_state, old_mask in _states(raw).items():
        for new_state, new_mask in _states(analytic).items():
            count = int((old_mask & new_mask).sum())
            if count:
                transitions[old_state + "_to_" + new_state] = count
    return {"different_rows": int((~_same(raw, analytic)).sum()),
        "different_bits_rows": int((raw.view(np.uint64) != analytic.view(np.uint64)).sum()),
        "finite_pairs": int(finite.sum()),
        "max_abs_difference_finite_pairs": float(np.max(np.abs(raw[finite] - analytic[finite]))) if finite.any() else None,
        "value_state_transitions": transitions}


def _analytic(probability, actual, eligible):
    derived = {name: np.full(len(probability), np.nan) for name in FIELDS}
    p, y = probability[eligible], actual[eligible]
    derived["cdf_actual_below"][eligible] = np.where(y == 0, 0., 1 - p)
    derived["cdf_actual"][eligible] = np.where(y == 0, 1 - p, 1.)
    derived["crps"][eligible] = (p - y) ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        derived["log_score"][eligible] = -np.where(y == 1, np.log(p), np.log1p(-p))
    return derived


def _assert_identities(rows):
    """Exact four-field identities; no atol/rtol, clipping or raw-law calls."""
    probability, actual = numeric(rows, "probability"), numeric(rows, "actual")
    eligible = rows.participation_state.eq("played").to_numpy() & valid_support(actual, "bernoulli") & np.isfinite(probability)
    expected = _analytic(probability, actual, eligible)
    for field in FIELDS:
        if not _same(numeric(rows, field), expected[field]).all():
            raise ValueError("canonical Bernoulli identity differs: " + field)


def _assert_preserved(original, derivative):
    if not original.index.identical(derivative.index) or not original.columns.identical(derivative.columns):
        raise ValueError("frozen index, row order or columns changed")
    for name in original.columns:
        if name in FIELDS:
            continue
        before, after = original[name], derivative[name]
        if before.dtype != after.dtype or not before.equals(after):
            raise ValueError("protected frozen column changed: " + name)
        if isinstance(before.dtype, np.dtype) and before.dtype.kind == "f":
            unsigned = np.dtype("u" + str(before.dtype.itemsize))
            if not np.array_equal(before.to_numpy().view(unsigned), after.to_numpy().view(unsigned)):
                raise ValueError("protected frozen floating bits changed: " + name)


def canonical_bernoulli_diagnostics(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return a copied derivative and aggregate receipt for one frozen law file.

    The caller binds the raw file hash, retains that file and original failure,
    and passes this view through the UNCHANGED strict reporting validator.
    Only FIELDS may change. Point/probability/mean, primary Brier, quantiles,
    variance, every context/state/identity field, index and row order are copied
    unchanged. This function performs no IO, fit, model/law call or new scoring
    pass; it represents the exact Bernoulli identities of already scored p/y.
    """
    if not isinstance(rows, pd.DataFrame) or rows.empty or not rows.columns.is_unique:
        raise ValueError("one nonempty normalized frozen law dataframe required")
    required = {*KEYS, "target", "method", "point", "probability", "mean", "actual", "participation_state", *FIELDS}
    if required - set(rows):
        raise ValueError("required frozen Bernoulli fields missing")
    if not rows.target.eq("anytime_td").all() or rows.method.nunique(dropna=False) != 1 or not rows.method.isin(METHODS).all():
        raise ValueError("one anytime_td leaf_cdf or role_prior file required")
    if rows[KEYS].isna().any(axis=None) or rows.duplicated(KEYS).any():
        raise ValueError("unique nonnull frozen player-game keys required")
    if not rows.participation_state.isin(("played", "DNP", "unknown")).all():
        raise ValueError("qualified frozen participation states required")
    for name in ("point", "probability", "mean", "actual", *FIELDS):
        if not is_numeric_dtype(rows[name].dtype):
            raise ValueError("numeric frozen field required: " + name)
    for name in FIELDS:
        if rows[name].dtype != np.dtype("float64"):
            raise ValueError("normalized float64 diagnostics required: " + name)

    probability, actual = numeric(rows, "probability"), numeric(rows, "actual")
    played = rows.participation_state.eq("played").to_numpy()
    supported = valid_support(actual, "bernoulli")
    observed = played & supported
    eligible = observed & np.isfinite(probability)
    raw = {name: rows[name].to_numpy(copy=True) for name in FIELDS}
    raw_present = np.logical_or.reduce([~np.isnan(raw[name]) for name in FIELDS])
    below, at = raw["cdf_actual_below"], raw["cdf_actual"]
    bad_below = ~np.isfinite(below) | (below < 0) | (below > 1)
    bad_at = ~np.isfinite(at) | (at < 0) | (at > 1)
    bad_order = np.isfinite(below) & np.isfinite(at) & (below > at)
    raw_strict_bad = np.isfinite(raw["crps"]) & (bad_below | bad_at | bad_order)
    receipt = {"version": VERSION, "policy_sha256": POLICY_SHA256, "target": "anytime_td", "method": str(rows.method.iloc[0]),
        "rows": len(rows), "supported_played_outcomes": int(observed.sum()), "analytic_diagnostic_rows": int(eligible.sum()),
        "unknown_participation_rows": int(rows.participation_state.eq("unknown").sum()),
        "known_DNP_rows": int(rows.participation_state.eq("DNP").sum()),
        "played_missing_actual_rows": int((played & np.isnan(actual)).sum()),
        "missing_probability_rows": int(np.isnan(probability).sum()),
        "raw_strict_CDF_bracket_invalid_rows": int(raw_strict_bad.sum()),
        "raw_CDF_invalid_finite_below_rows": int((np.isfinite(below) & ((below < 0) | (below > 1))).sum()),
        "raw_CDF_invalid_finite_at_rows": int((np.isfinite(at) & ((at < 0) | (at > 1))).sum()),
        "raw_CDF_order_invalid_rows": int(bad_order.sum()),
        "raw_CDF_nonfinite_observed_rows": int((eligible & (~np.isfinite(below) | ~np.isfinite(at))).sum()),
        "raw_negative_CRPS_rows": int((raw["crps"] < 0).sum()),
        "raw_invalid_log_score_rows": int((np.isneginf(raw["log_score"]) | (raw["log_score"] < 0)).sum()),
        "raw_unobserved_missingness_conflict_rows": int((~observed & raw_present).sum()),
        "raw_missing_probability_conflict_rows": int((~np.isfinite(probability) & raw_present).sum()),
        "raw_observed_missingness_conflict_rows": int((eligible & (~np.isfinite(below) | ~np.isfinite(at)
            | ~np.isfinite(raw["crps"]) | np.isnan(raw["log_score"]) | np.isneginf(raw["log_score"]))).sum()),
        "invalid_probability_rows": int((np.isinf(probability) | (np.isfinite(probability) & ((probability < 0) | (probability > 1)))).sum()),
        "invalid_actual_rows": int((np.isinf(actual) | (np.isfinite(actual) & ~supported)).sum()),
        "raw_state": "INVALID_V1_CDF_BRACKET" if raw_strict_bad.any() else "NO_V1_CDF_BRACKET_VIOLATION_DETECTED",
        "mutable_fields": list(FIELDS), "probability_clipping": "none", "original_raw_files_and_failures": "retained by caller"}
    def reject(message):
        raise DiagnosticInputError(message, {**receipt, "state": "REJECTED"})
    if receipt["invalid_probability_rows"]:
        reject("frozen Bernoulli probability is infinite or outside [0,1]")
    if not _same(probability, numeric(rows, "point")).all() or not _same(probability, numeric(rows, "mean")).all():
        reject("exact frozen point/probability/mean identity differs")
    for name in ("point", "mean"):
        if not np.array_equal(probability[np.isfinite(probability)].view(np.uint64), numeric(rows, name)[np.isfinite(probability)].view(np.uint64)):
            reject("finite frozen point/probability/mean bits differ")
    if receipt["invalid_actual_rows"]:
        reject("frozen finite/infinite actual violates Bernoulli support")
    if receipt["raw_unobserved_missingness_conflict_rows"] or receipt["raw_missing_probability_conflict_rows"]:
        reject("unobserved or abstaining raw diagnostics must all remain missing")
    if receipt["raw_observed_missingness_conflict_rows"]:
        reject("supported finite-p outcomes require complete already-frozen diagnostics")

    analytic = _analytic(probability, actual, eligible)
    derivative = rows.copy(deep=True)
    for field in FIELDS:
        derivative[field] = analytic[field]
    _assert_identities(derivative)
    _assert_preserved(rows, derivative)
    receipt.update(state="CANONICAL_DIAGNOSTIC_VIEW_ONLY", primary_point_probability_mean_and_other_fields="unchanged",
        field_differences={field: _difference(raw[field], analytic[field]) for field in FIELDS},
        original_strict_validator="unchanged; caller must validate derivative before reporting")
    return derivative, receipt
