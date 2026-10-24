"""Descriptive threshold arithmetic on explicitly supplied frozen points only.

No models, probability laws, odds, prices, payouts, bootstrap or data loader are
used. The caller binds original offers, thresholds, points and qualified actuals
before one finite measurement invocation. Every supplied offer remains present.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import numbers
import re

import numpy as np
import pandas as pd

VERSION = "recorded-threshold-point-directions-v1-20261023"
KEYS = ["season", "week", "game_id", "player_id", "target"]
SUPPORT = {"pass_yd": "signed_integer", "pass_td": "count", "pass_cmp": "count", "pass_att": "count",
    "pass_int": "count", "rush_yd": "signed_integer", "rush_att": "count", "rec": "count",
    "rec_yd": "signed_integer", "rush_rec_yd": "signed_integer", "fantasy_ppr": "uncertified_ppr",
    "anytime_td": "binary_reference_only"}
REFERENCE_SOURCES = {"dk", "sleeper"}
TIMING_FIELDS = ("line_recorded_at_utc", "forecast_recorded_at_utc", "cutoff_utc", "kickoff_utc",
                 "line_receipt_binding", "forecast_receipt_binding", "source_coverage")
DIRECTIONS = ("under", "equal", "over")
_FORBIDDEN = re.compile(r"(?:^|_)(?:odds|price|prices|payout|payouts|stake|profit|ev)(?:_|$)")
_OUTCOME = re.compile(r"(?:^|_)(?:actual|outcome|label|participation|quarantine|quarantined|future|realized)(?:_|$)")


def _number(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (numbers.Real, str)):
        return np.nan
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return np.nan


def _numeric(frame, name):
    return np.array([_number(v) for v in frame[name]], dtype=float) if name in frame else np.full(len(frame), np.nan)


def _direction(values, line):
    return np.where(values < line, "under", np.where(values > line, "over", "equal"))


def _time_relation(frame, clock, boundary):
    if clock not in frame or boundary not in frame:
        return np.full(len(frame), "unknown", dtype=object)
    a, b = pd.to_datetime(frame[clock], utc=True, errors="coerce", format="mixed"), pd.to_datetime(frame[boundary], utc=True, errors="coerce", format="mixed")
    known = a.notna().to_numpy() & b.notna().to_numpy()
    return np.where(~known, "unknown", np.where((a < b).to_numpy(), "before", np.where((a == b).to_numpy(), "equal", "after")))


def _aggregate(rows, mask=None):
    mask = rows.eligible.to_numpy() if mask is None else np.asarray(mask, dtype=bool)
    selected = rows.loc[mask]
    n = len(selected)
    actual, point = selected.actual.to_numpy(float), selected.point.to_numpy(float)
    predicted, observed = selected.point_direction.to_numpy(), selected.actual_direction.to_numpy()
    correct = predicted == observed
    push = observed == "equal"
    nonpush = ~push
    error = point - actual
    return {"offered_rows": len(rows), "scored_rows": n,
        "games": int(selected.game_id.nunique()), "players": int(selected.player_id.nunique()),
        "weeks": len(selected[["season", "week"]].drop_duplicates()),
        "point_mae": float(np.mean(np.abs(error))) if n else None,
        "point_rmse": float(np.sqrt(np.mean(error ** 2))) if n else None,
        "point_bias_prediction_minus_actual": float(np.mean(error)) if n else None,
        "point_absolute_error_p90": float(np.quantile(np.abs(error), .90, method="linear")) if n else None,
        "point_absolute_error_p95": float(np.quantile(np.abs(error), .95, method="linear")) if n else None,
        "point_absolute_error_max": float(np.abs(error).max()) if n else None,
        "three_way_correct_rows": int(correct.sum()), "three_way_accuracy": float(correct.mean()) if n else None,
        "three_way_misclassification_rate": float((~correct).mean()) if n else None,
        "actual_equal_threshold_rows": int(push.sum()), "actual_equal_threshold_rate": float(push.mean()) if n else None,
        "prediction_equal_threshold_rows": int((predicted == "equal").sum()),
        "nonpush_secondary_rows": int(nonpush.sum()),
        "nonpush_secondary_accuracy": float(correct[nonpush].mean()) if nonpush.any() else None,
        "nonpush_prediction_equal_rows": int(((predicted == "equal") & nonpush).sum()),
        "confusion_three_way": {p: {a: int(((predicted == p) & (observed == a)).sum()) for a in DIRECTIONS} for p in DIRECTIONS},
        "eligibility_states": rows.eligibility_state.value_counts(dropna=False).to_dict(),
        "coverage_count_population": "all original offered rows of this target; scored_rows alone uses the specified common mask",
        "threshold_classes": rows.threshold_class.value_counts(dropna=False).to_dict(),
        "line_source_states": rows.line_source_state.value_counts(dropna=False).to_dict(),
        "participation_states": rows.participation_state.value_counts(dropna=False).to_dict(),
        "quarantine_states": rows.quarantine_state.value_counts(dropna=False).to_dict(),
        "line_clock_vs_cutoff": rows.line_clock_vs_cutoff.value_counts(dropna=False).to_dict(),
        "line_clock_vs_kickoff": rows.line_clock_vs_kickoff.value_counts(dropna=False).to_dict(),
        "forecast_clock_vs_kickoff": rows.forecast_clock_vs_kickoff.value_counts(dropna=False).to_dict(),
        "source_coverage": rows.source_coverage.fillna("unknown").astype(str).value_counts(dropna=False).to_dict() if "source_coverage" in rows else {"unspecified": len(rows)},
        "direction_semantics": "point direction rule only; no calibrated probability, market settlement or return claim",
        "push_semantics": "actual equality reported separately; no assumed settlement; nonpush is secondary",
        "timing_semantics": "literal clocks reported separately; missing clocks remain unknown; descriptive arithmetic is not a contemporaneous forecast claim"}


def _prepare(frame, methods, required):
    if not isinstance(frame, pd.DataFrame) or not isinstance(methods, Mapping) or not 1 <= len(methods) <= 32 or len(frame) > 100000:
        raise ValueError("finite explicit frame and1–32 declared methods required")
    if missing := set(KEYS + required) - set(frame):
        raise ValueError("missing explicit offer/outcome contract: " + repr(sorted(missing)))
    if frame[KEYS].isna().any(axis=None):
        raise ValueError("null player-game-target identity")
    offered = frame.copy()
    for name in ["season", "week"]:
        values = _numeric(offered, name)
        if not (np.isfinite(values) & (values == np.floor(values)) & (values > 0)).all():
            raise ValueError("invalid season/week identity")
        offered[name] = values.astype(int)
    for name in ["game_id", "player_id", "target"]:
        offered[name] = offered[name].astype(str)
    if offered.duplicated(KEYS).any():
        raise ValueError("duplicate player-game-target; snapshots must not inflate the cohort")
    for name, column in methods.items():
        if not isinstance(name, str) or not isinstance(column, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) or _FORBIDDEN.search(name) or _FORBIDDEN.search(column) or _OUTCOME.search(column) or column in SUPPORT or column in KEYS:
            raise ValueError("declared methods must name saved point columns only")
    return offered


def _support_by_method(methods, supported_targets):
    if supported_targets is not None and set(supported_targets) - set(methods):
        raise ValueError("target support declared for an unknown method")
    if supported_targets and any(isinstance(value, (str, bytes)) for value in supported_targets.values()):
        raise ValueError("supported targets must be explicit target-name sequences")
    return {name: set(supported_targets[name]) if supported_targets and name in supported_targets else set(SUPPORT) for name in methods}


def freeze_recorded_directions(frame: pd.DataFrame, methods: Mapping[str, str], *,
                               supported_targets: Mapping[str, Sequence[str]] | None = None,
                               method_metadata: Mapping[str, Mapping[str, str]] | None = None) -> pd.DataFrame:
    """Return ALL offers×methods as a label-free long direction DataFrame.

    Only identity, literal line/source, declared frozen point columns and
    explicit clock/source metadata are selected from the frame. Actual values,
    participation, outcome states and quarantine fields are never accessed.
    ``method_metadata`` maps output metadata names to method-specific input
    columns; it does not supply or infer a missing publication/cutoff clock.
    """
    if not isinstance(frame, pd.DataFrame) or not isinstance(methods, Mapping):
        raise ValueError("explicit frame and declared frozen point methods required")
    # Reject an outcome/financial column declaration before selecting any
    # columns from a frame that might already contain labels.
    for name, column in methods.items():
        if not isinstance(name, str) or not isinstance(column, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) or _FORBIDDEN.search(name) or _FORBIDDEN.search(column) or _OUTCOME.search(column) or column in SUPPORT or column in KEYS:
            raise ValueError("declared methods must name saved point columns only")
    allowed_metadata = set(TIMING_FIELDS) | {"point_source_state", "point_source_path", "point_source_sha256", "native_cutoff_utc", "calculation_completed_at_utc"}
    if method_metadata:
        if set(method_metadata) - set(methods) or any(set(values) - allowed_metadata for values in method_metadata.values()):
            raise ValueError("only explicit declared method metadata columns allowed")
        if any(not isinstance(c, str) or _OUTCOME.search(c) or _FORBIDDEN.search(c) or c in SUPPORT or c in KEYS
               for values in method_metadata.values() for c in values.values()):
            raise ValueError("label or financial columns cannot supply frozen point metadata")
    selected = list(dict.fromkeys(KEYS + ["line", "line_from"] + [c for c in TIMING_FIELDS if c in frame] +
        [c for c in methods.values() if c in frame] + [c for values in (method_metadata or {}).values() for c in values.values() if c in frame]))
    # Select the label-free columns BEFORE _prepare copies any supplied frame.
    if missing := set(KEYS + ["line", "line_from"]) - set(frame):
        raise ValueError("missing explicit label-free offer contract: " + repr(sorted(missing)))
    offered = _prepare(frame[selected], methods, ["line", "line_from"])
    support_by_method = _support_by_method(methods, supported_targets)
    line = _numeric(offered, "line")
    sources = offered.line_from.to_numpy(object)
    reference = np.array([isinstance(v, str) and v in REFERENCE_SOURCES for v in sources])
    ours = np.array([isinstance(v, str) and v == "ours" for v in sources])
    finite_line = np.isfinite(line)
    classes = np.where(finite_line & reference, "reference", np.where(finite_line & ours, "ours", "nonexistent"))
    source_state = np.where(~finite_line, "missing_or_nonfinite_threshold", np.where(reference, "literal_recorded_reference",
        np.where(ours, "model_derived_ours", "unapproved_or_missing_line_source")))
    target_support = offered.target.map(SUPPORT).fillna("unsupported_target").to_numpy()
    base = offered[KEYS + ["line", "line_from"] + [c for c in TIMING_FIELDS if c in offered]].copy()
    base["recorded_line_raw"], base["line"] = offered.line.to_numpy(), line
    base["support"], base["threshold_class"], base["line_source_state"] = target_support, classes, source_state
    output = []
    for method, column in methods.items():
        rows = base.copy()
        for name, source_column in (method_metadata or {}).get(method, {}).items():
            rows[name] = offered[source_column].to_numpy() if source_column in offered else None
        point = _numeric(offered, column)
        valid_point = np.isfinite(point) & ((target_support != "count") | (point >= 0))
        reason = np.full(len(offered), "eligible", dtype=object)
        checks = [(~offered.target.isin(support_by_method[method]).to_numpy(), "method_not_supported_target"),
            (~np.isin(target_support, ["count", "signed_integer"]), "target_not_eligible_numeric_market"),
            (classes != "reference", "no_literal_reference_threshold"), (~np.isfinite(point), "missing_or_nonfinite_point"),
            (~valid_point & np.isfinite(point), "invalid_count_point")]
        for mask, label in reversed(checks):
            reason[mask] = label
        eligible = reason == "eligible"
        rows["method"], rows["point_column"], rows["point"] = method, column, point
        rows["point_raw"] = offered[column].to_numpy() if column in offered else np.nan
        rows["direction_state"], rows["point_direction"] = reason, "unscored"
        rows.loc[eligible, "point_direction"] = _direction(point[eligible], line[eligible])
        rows["line_clock_vs_cutoff"] = _time_relation(rows, "line_recorded_at_utc", "cutoff_utc")
        rows["line_clock_vs_kickoff"] = _time_relation(rows, "line_recorded_at_utc", "kickoff_utc")
        rows["forecast_clock_vs_kickoff"] = _time_relation(rows, "forecast_recorded_at_utc", "kickoff_utc")
        output.append(rows)
    return pd.concat(output, ignore_index=True)


def evaluate_recorded_thresholds(frame: pd.DataFrame, methods: Mapping[str, str], *,
                                common_controls: Mapping[str, Sequence[str]] | Sequence[str] | None = None,
                                supported_targets: Mapping[str, Sequence[str]] | None = None,
                                reference_method: str | None = "website",
                                method_metadata: Mapping[str, Mapping[str, str]] | None = None,
                                frozen_directions: pd.DataFrame | None = None) -> dict:
    """Return private long rows and aggregates without writing external state.

    ``methods`` maps declared method names to exact frozen point columns. A
    missing column is retained as an unscored method. ``supported_targets`` can
    explicitly block a method on selected targets without changing other
    methods' cohorts. Optional common controls define only the specified
    candidate intersections; they never shrink unrelated methods or targets.

    The caller must preregister method/target/contrast counts and input hashes,
    consume its create-only measurement receipt, and preserve this output. This
    pure function is not an execution/restart guard or a new forecasting model.
    Supply the caller's already hashed ``frozen_directions`` to reuse its
    authoritative point directions without a second direction conversion.
    """
    offered = _prepare(frame, methods, ["line", "line_from", "actual", "participation_state"])
    support_by_method = _support_by_method(methods, supported_targets)
    if frozen_directions is None:
        frozen = freeze_recorded_directions(offered, methods, supported_targets=supported_targets, method_metadata=method_metadata)
    else:
        required = set(KEYS + ["method", "point", "line", "line_from", "direction_state", "point_direction", "threshold_class",
            "line_source_state", "line_clock_vs_cutoff", "line_clock_vs_kickoff", "forecast_clock_vs_kickoff"])
        if not isinstance(frozen_directions, pd.DataFrame) or required - set(frozen_directions):
            raise ValueError("complete label-free frozen directions required")
        if any(_OUTCOME.search(c) for c in frozen_directions.columns):
            raise ValueError("frozen directions cannot contain outcome/participation fields")
        frozen = frozen_directions.copy()
        if len(frozen) != len(offered) * len(methods) or set(frozen.method.unique()) != set(methods) or frozen.duplicated(KEYS + ["method"]).any():
            raise ValueError("frozen direction population differs from declared offers/methods")
        for method, column in methods.items():
            saved = frozen.loc[frozen.method.eq(method)].reset_index(drop=True)
            if not saved[KEYS].equals(offered[KEYS].reset_index(drop=True)) or not np.array_equal(saved.point.to_numpy(float), _numeric(offered, column), equal_nan=True) or not np.array_equal(saved.line.to_numpy(float), _numeric(offered, "line"), equal_nan=True):
                raise ValueError("frozen identity/point/literal-line bytes differ")
            if not saved.line_from.fillna("<missing>").equals(offered.line_from.reset_index(drop=True).fillna("<missing>")):
                raise ValueError("frozen literal line source differs")
    if isinstance(common_controls, Mapping):
        common = {name: list(controls) for name, controls in common_controls.items()}
    elif common_controls is not None:
        if isinstance(common_controls, (str, bytes)):
            raise ValueError("common controls must be declared method names")
        controls = list(common_controls)
        common = {name: controls for name in methods if name != reference_method}
    else:
        common = {}
    for name, controls in common.items():
        if name not in methods or not controls or len(controls) != len(set(controls)) or set(controls) - set(methods):
            raise ValueError("invalid declared common-control intersection")
    if reference_method is not None and reference_method not in methods:
        reference_method = None
    actual = _numeric(offered, "actual")
    target_support = offered.target.map(SUPPORT).fillna("unsupported_target").to_numpy()
    valid_actual = np.isfinite(actual) & (actual == np.floor(actual)) & ((target_support != "count") | (actual >= 0))
    quarantine_raw = offered.quarantined.to_numpy(object) if "quarantined" in offered else np.full(len(offered), None, object)
    known_quarantine = np.array([isinstance(v, (bool, np.bool_)) for v in quarantine_raw])
    quarantine = np.array([bool(v) if isinstance(v, (bool, np.bool_)) else False for v in quarantine_raw])
    quarantine_state = np.where(~known_quarantine, "unknown", np.where(quarantine, "quarantined", "clear"))
    state = offered.participation_state.fillna("unknown").astype(str).to_numpy()
    all_rows, by_method = [], {}
    for method, column in methods.items():
        rows = frozen.loc[frozen.method.eq(method)].reset_index(drop=True).copy()
        reason = rows.direction_state.to_numpy(object).copy()
        # Explicit precedence preserves unknown/DNP and quarantine distinctions.
        checks = [(state != "played", "participation_not_played"),
            (~known_quarantine, "quarantine_unknown"), (quarantine, "quarantined"),
            (~np.isfinite(actual), "played_missing_actual"), (~valid_actual & np.isfinite(actual), "played_invalid_actual_support")]
        for mask, label in reversed(checks):
            reason[mask & rows.direction_state.eq("eligible").to_numpy()] = label
        eligible = reason == "eligible"
        rows["actual_raw"], rows["actual"] = offered.actual.to_numpy(), actual
        rows["participation_state"], rows["quarantine_state"] = state, quarantine_state
        rows["eligibility_state"], rows["eligible"] = reason, eligible
        rows["actual_direction"] = "unscored"
        rows.loc[eligible, "actual_direction"] = _direction(actual[eligible], rows.line.to_numpy(float)[eligible])
        rows["direction_correct"] = pd.array([None] * len(rows), dtype="boolean")
        rows.loc[eligible, "direction_correct"] = rows.loc[eligible, "point_direction"].eq(rows.loc[eligible, "actual_direction"]).to_numpy()
        by_method[method] = rows
        all_rows.append(rows)
    targets = list(SUPPORT) + [t for t in offered.target.unique() if t not in SUPPORT]
    summaries = [{"target": target, "method": method, **_aggregate(rows.loc[rows.target.eq(target)])}
        for target in targets for method, rows in by_method.items()]
    comparisons = []
    for kind, declarations in [("pairwise_literal_site", {m: [reference_method] for m in methods if reference_method is not None and m != reference_method}),
                               ("declared_common_controls", common)]:
        for candidate, controls in declarations.items():
            cohort_methods = list(dict.fromkeys([candidate] + controls))
            for target in targets:
                mask = offered.target.eq(target).to_numpy()
                for method in cohort_methods:
                    mask &= by_method[method].eligible.to_numpy()
                target_mask = offered.target.eq(target).to_numpy()
                entries = {method: _aggregate(by_method[method].loc[target_mask], mask[target_mask]) for method in cohort_methods}
                comparisons.append({"target": target, "candidate": candidate, "controls": controls, "cohort": kind,
                    "common_rows": int(mask.sum()), "methods": entries,
                    "cohort_semantics": "identical original offer rows for every named method; unrelated methods never enter this mask"})
    return {"rows": pd.concat(all_rows, ignore_index=True), "summary": {
        "version": VERSION, "original_offered_rows": len(offered), "declared_methods": dict(methods),
        "supported_targets_by_method": {name: sorted(v) for name, v in support_by_method.items()},
        "common_controls": common, "reference_method": reference_method, "method_target_summaries": summaries,
        "comparisons": comparisons, "new_model_fits": 0, "new_model_predictions": 0,
        "direction_conversion_passes_in_this_call": 1 if frozen_directions is None else 0,
        "probabilities_produced": False, "bootstrap_replicates": 0,
        "evidence": "exposed descriptive measurement of frozen point directions only; no contemporaneous, calibrated probability, settlement, EV, qualification or promotion claim"}}


def summarize_recorded_rows(rows: pd.DataFrame) -> dict:
    """Aggregate one declared saved method/target slice using the same metrics.

    The caller chooses its preregistered source/role/team/fallback subset within
    the single outcome phase. This function reads existing qualified rows,
    performs no point conversion or external mutation and adds no model state.
    """
    required = set(KEYS + ["method", "point", "actual", "point_direction", "actual_direction", "eligible", "eligibility_state",
        "threshold_class", "line_source_state", "participation_state", "quarantine_state", "line_clock_vs_cutoff",
        "line_clock_vs_kickoff", "forecast_clock_vs_kickoff"])
    if not isinstance(rows, pd.DataFrame) or required - set(rows):
        raise ValueError("existing qualified recorded-threshold rows required")
    if rows.method.nunique() > 1 or rows.target.nunique() > 1 or rows.duplicated(KEYS + ["method"]).any():
        raise ValueError("summary slice must contain one method/target without duplicate offers")
    if not all(isinstance(v, (bool, np.bool_)) for v in rows.eligible):
        raise ValueError("explicit boolean eligibility required")
    selected = rows.loc[rows.eligible]
    point, actual = selected.point.to_numpy(float), selected.actual.to_numpy(float)
    support = selected.target.map(SUPPORT).to_numpy()
    if not (np.isfinite(point) & np.isfinite(actual) & (actual == np.floor(actual)) & np.isin(support, ["count", "signed_integer"]) &
            ((support != "count") | ((point >= 0) & (actual >= 0)))).all() or not selected.point_direction.isin(DIRECTIONS).all() or not selected.actual_direction.isin(DIRECTIONS).all():
        raise ValueError("eligible saved rows violate numeric support/direction contract")
    return _aggregate(rows)
