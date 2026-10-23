"""Descriptive comparisons against literal original website opportunities.

No bootstrap or selection is performed. Missing points remain missing, and a
recorded numeric point never acquires a probability distribution or mean claim.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .cdf_engine import KEYS, numeric, valid_support
from .cdf_evaluation import summarize

OPPORTUNITY_KEYS = KEYS + ["target"]


def normalize_keys(frame):
    result = frame.copy()
    if missing := set(KEYS) - set(result):
        raise ValueError("missing identity fields: " + repr(sorted(missing)))
    if result[KEYS].isna().any(axis=None):
        raise ValueError("null player-game identity")
    for name in ["season", "week"]:
        values = pd.to_numeric(result[name], errors="raise")
        if not np.isfinite(values).all() or not (values == np.floor(values)).all():
            raise ValueError("invalid season/week identity")
        result[name] = values.astype(int)
    for name in ["game_id", "player_id"]:
        result[name] = result[name].astype(str)
    return result


def target_query(query, opportunities, target):
    """Select by original offers only; outcomes never enter this operation."""
    query, opportunities = normalize_keys(query), normalize_keys(opportunities)
    if query.duplicated(KEYS).any() or opportunities.duplicated(OPPORTUNITY_KEYS).any():
        raise ValueError("duplicate query/opportunity identity")
    offers = opportunities.loc[opportunities.target.eq(target)].copy()
    order = offers[KEYS].merge(query, on=KEYS, how="left", validate="one_to_one", indicator=True)
    if not order._merge.eq("both").all():
        raise ValueError("original offer lacks query features")
    order = order.drop(columns="_merge")
    for name in ["position", "team", "opponent", "kickoff_utc", "cutoff_utc"]:
        if name not in order:
            raise ValueError("query lacks original binding field: " + name)
        if name in offers:
            left, right = order[name], offers[name].reset_index(drop=True)
            if name.endswith("_utc"):
                left = pd.to_datetime(left, utc=True, errors="coerce")
                right = pd.to_datetime(right, utc=True, errors="coerce")
            if not left.reset_index(drop=True).eq(right).all():
                raise ValueError("original offer/query context mismatch: " + name)
    return order.reset_index(drop=True), offers.reset_index(drop=True)


def bind_outcomes(query, outcomes, category):
    """Require the audited original outcome population, including unresolved rows."""
    query, outcomes = normalize_keys(query), normalize_keys(outcomes)
    required = {"target", "actual", "participation_state", "outcome_state"}
    if missing := required - set(outcomes):
        raise ValueError("qualified outcomes lack fields: " + repr(sorted(missing)))
    if outcomes.duplicated(OPPORTUNITY_KEYS).any():
        raise ValueError("duplicate qualified outcome")
    selected = outcomes.loc[outcomes.target.eq(category["target"])].copy()
    coverage = query[KEYS].merge(selected[KEYS], on=KEYS, how="outer", validate="one_to_one", indicator=True)
    if not coverage._merge.eq("both").all():
        raise ValueError("qualified outcome population differs from original offers")
    # An outer merge may sort keys even with sort=False. Bind through a left
    # merge only after the exact key-set check, preserving original offer order.
    binding = query[KEYS].merge(selected, on=KEYS, how="left", sort=False, validate="one_to_one")
    if not binding.participation_state.isin(["played", "DNP", "unknown"]).all():
        raise ValueError("unqualified participation state")
    for name in ["position", "team", "opponent", "kickoff_utc", "cutoff_utc"]:
        if name in binding:
            left, right = query[name], binding[name]
            if name.endswith("_utc"):
                left = pd.to_datetime(left, utc=True, errors="coerce")
                right = pd.to_datetime(right, utc=True, errors="coerce")
            if not left.reset_index(drop=True).eq(right.reset_index(drop=True)).all():
                raise ValueError("qualified outcome context mismatch: " + name)
    result = query.copy()
    actual = numeric(binding, "actual").copy()
    if "quarantined" in binding:
        if binding.quarantined.isna().any() or not binding.quarantined.isin([True, False]).all():
            raise ValueError("quarantine flag must be explicit boolean")
        actual[binding.quarantined.astype(bool).to_numpy()] = np.nan
    result[category["target"]] = actual
    result["participation_state"] = binding.participation_state.to_numpy()
    for name in binding.columns:
        if name not in KEYS:
            result["qualified_" + name] = binding[name].to_numpy()
    for name in ["rush_yd", "rec_yd", "rush_td", "rec_td"]:
        if name in binding and name != category["target"]:
            result[name] = numeric(binding, name)
    if category["target"] in {"rush_rec_yd", "anytime_td"}:
        from .cdf_engine import assert_composite_contract
        assert_composite_contract(result, category)
    return result


def point_metrics(prediction, actual):
    error = np.asarray(prediction) - np.asarray(actual)
    absolute = np.abs(error)
    return {"rows": len(error), "mae": float(absolute.mean()) if len(error) else None,
            "rmse": float(np.sqrt(np.mean(error ** 2))) if len(error) else None,
            "bias_prediction_minus_actual": float(error.mean()) if len(error) else None,
            "absolute_error_p90": float(np.quantile(absolute, .90)) if len(error) else None,
            "absolute_error_p95": float(np.quantile(absolute, .95)) if len(error) else None,
            "absolute_error_max": float(absolute.max()) if len(error) else None,
            "fraction_absolute_error_ge5": float(np.mean(absolute >= 5)) if len(error) else None,
            "fraction_absolute_error_ge50": float(np.mean(absolute >= 50)) if len(error) else None}


def literal_controls(offers, scored, category):
    """Keep recorded values; only genuine Bernoulli probabilities define a law."""
    if not offers[KEYS].reset_index(drop=True).equals(scored[KEYS].reset_index(drop=True)):
        raise ValueError("literal control order/identity differs from scored original offers")
    controls = []
    binary = category["support"] == "bernoulli"
    actual = numeric(scored, "actual")
    supported = scored.participation_state.eq("played").to_numpy() & valid_support(actual, category["support"])
    for method in ["website", "raw", "simple"]:
        field = method + ("_probability" if binary else "_point")
        point = numeric(offers, field)
        if binary and (np.isfinite(point) & ((point < 0) | (point > 1))).any():
            raise ValueError("literal probability outside [0,1]: " + field)
        row = scored[[c for c in KEYS + ["target", "position", "team", "opponent", "actual", "participation_state", "outcome_state", "primary_role"] if c in scored]].copy()
        row["method"], row["point"], row["source_field"] = method, point, field
        row["probability"] = point if binary else np.nan
        row["log_score"] = np.nan
        row["brier"] = np.nan
        if binary:
            good = supported & np.isfinite(point)
            with np.errstate(divide="ignore", invalid="ignore"):
                row.loc[good, "log_score"] = -np.where(actual[good] == 1, np.log(point[good]), np.log1p(-point[good]))
            row.loc[good, "brier"] = (point[good] - actual[good]) ** 2
        controls.append(row)
    return pd.concat(controls, ignore_index=True)


def paired_rows(candidate, control, category, *, role_subset=False, candidate_point=None):
    """Return all offers with an explicit common scoring mask and paired losses."""
    binary = category["support"] == "bernoulli"
    point_name = candidate_point or ("mean" if binary else "median")
    fields = ["actual", "participation_state", "outcome_state", "primary_role", "fallback", point_name]
    coverage = candidate[KEYS].merge(control[KEYS], on=KEYS, how="outer", validate="one_to_one", indicator=True)
    if not coverage._merge.eq("both").all():
        raise ValueError("candidate/control original population differs")
    joined = candidate[KEYS + fields].merge(control[KEYS + ["actual", "participation_state", "point"]],
        on=KEYS, how="left", sort=False, validate="one_to_one", suffixes=("", "_control"))
    if not np.allclose(numeric(joined, "actual"), numeric(joined, "actual_control"), equal_nan=True, atol=0, rtol=0):
        raise ValueError("candidate/control outcomes differ")
    if not joined.participation_state.eq(joined.participation_state_control).all():
        raise ValueError("candidate/control participation differs")
    a, b, y = numeric(joined, point_name), numeric(joined, "point"), numeric(joined, "actual")
    observed = joined.participation_state.eq("played").to_numpy() & valid_support(y, category["support"])
    mask = observed & np.isfinite(a) & np.isfinite(b)
    if role_subset:
        mask &= joined.primary_role.to_numpy()
    joined["paired_eligible"] = mask
    joined["candidate_point"], joined["literal_control_point"] = a, b
    joined["candidate_loss"], joined["control_loss"], joined["delta_candidate_minus_control"] = np.nan, np.nan, np.nan
    loss_a = (a[mask] - y[mask]) ** 2 if binary else np.abs(a[mask] - y[mask])
    loss_b = (b[mask] - y[mask]) ** 2 if binary else np.abs(b[mask] - y[mask])
    joined.loc[mask, "candidate_loss"] = loss_a
    joined.loc[mask, "control_loss"] = loss_b
    joined.loc[mask, "delta_candidate_minus_control"] = loss_a - loss_b
    baseline = float(loss_b.mean()) if mask.any() else None
    candidate_loss = float(loss_a.mean()) if mask.any() else None
    report = {"population": "prior_primary_roles" if role_subset else "all_original_offered",
        "offered_rows": len(joined), "supported_played_rows": int(observed.sum()), "paired_rows": int(mask.sum()),
        "candidate_missing_rows": int((observed & ~np.isfinite(a)).sum()), "control_missing_rows": int((observed & ~np.isfinite(b)).sum()),
        "candidate_point": point_name, "primary_loss": "brier" if binary else "mae",
        "candidate_loss": candidate_loss, "control_loss": baseline,
        "delta_candidate_minus_control": float((loss_a - loss_b).mean()) if mask.any() else None,
        "improvement_pct": 100 * (baseline - candidate_loss) / baseline if baseline not in (None, 0) else None,
        "candidate_point_metrics": point_metrics(a[mask], y[mask]), "control_literal_point_metrics": point_metrics(b[mask], y[mask]),
        "games": int(joined.loc[mask, "game_id"].nunique()), "weeks": len(joined.loc[mask, ["season", "week"]].drop_duplicates()),
        "interval": None, "uncertainty": "one exposed week; descriptive paired rows only; no significance or qualification"}
    return report, joined


def report_target(candidate, controls, category):
    report = {"target": category["target"], "candidate_summary": summarize(candidate, category["support"]),
              "paired": [], "subgroups": [], "control_summaries": []}
    deltas = []
    for method, control in controls.groupby("method", sort=True):
        for role_subset in [False, True]:
            value, rows = paired_rows(candidate, control, category, role_subset=role_subset)
            value.update(comparator=method, status="primary" if method == "website" and not role_subset else "secondary")
            report["paired"].append(value)
            rows["comparator"], rows["population"] = method, value["population"]
            deltas.append(rows)
        if category["support"] != "bernoulli":
            value, _ = paired_rows(candidate, control, category, candidate_point="mean")
            report["paired"].append(dict(value, comparator=method, status="secondary_same_law_mean"))
        actual, point = numeric(control, "actual"), numeric(control, "point")
        good = control.participation_state.eq("played").to_numpy() & valid_support(actual, category["support"]) & np.isfinite(point)
        entry = {"method": method, "offered_rows": len(control), "missing_points": int((~np.isfinite(point)).sum()),
                 "literal_point": point_metrics(point[good], actual[good])}
        if category["support"] == "bernoulli":
            logs = numeric(control, "log_score")[good]
            entry.update(brier=float(np.mean((point[good] - actual[good]) ** 2)) if good.any() else None,
                log_loss=float(logs.mean()) if len(logs) and np.isfinite(logs).all() else None,
                infinite_log_losses=int(np.isposinf(logs).sum()), log_loss_state="infinite" if np.isposinf(logs).any() else "finite" if len(logs) else "unavailable")
        report["control_summaries"].append(entry)
    for dimension in ["position", "team", "opponent", "fallback", "history_state", "outcome_state"]:
        if dimension in candidate:
            for value, part in candidate.groupby(dimension, dropna=False):
                report["subgroups"].append({"dimension": dimension, "value": str(value), **summarize(part, category["support"])})
    return report, pd.concat(deltas, ignore_index=True)


def ensemble_frozen_rows(candidate, offers, category):
    """The single predeclared .5/.5 point/probability blend; no fitting."""
    if not candidate[KEYS].reset_index(drop=True).equals(offers[KEYS].reset_index(drop=True)):
        raise ValueError("ensemble original offer order differs from frozen CDF")
    fields = KEYS + ["target", "team", "opponent", "position", "kickoff_utc", "cutoff_utc",
                     "primary_role", "history_state", "fallback", "evidence"]
    result = candidate[[c for c in fields if c in candidate]].copy()
    binary = category["support"] == "bernoulli"
    site = numeric(offers, "website_probability" if binary else "website_point")
    primary = numeric(candidate, "mean" if binary else "median")
    mean = numeric(candidate, "mean")
    if binary and (np.isfinite(site) & ((site < 0) | (site > 1))).any():
        raise ValueError("literal website event probability outside [0,1]")
    result["method"] = "website_equalweight_" + candidate.method.iloc[0].removeprefix("leaf_cdf_") if len(candidate) else "website_equalweight"
    result["literal_website_value"] = site
    result["pure_cdf_primary_value"], result["pure_cdf_mean"] = primary, mean
    result["ensemble_point"] = np.where(np.isfinite(site) & np.isfinite(primary), .5 * site + .5 * primary, np.nan)
    result["ensemble_mean_point"] = np.where(np.isfinite(site) & np.isfinite(mean), .5 * site + .5 * mean, np.nan)
    result["abstention"] = np.where(~np.isfinite(site), "missing_literal_website", np.where(~np.isfinite(primary), "missing_pure_cdf", ""))
    result["point_semantics"] = "genuine_bernoulli_probability" if binary else "fixed_equalweight_point_heuristic_not_law_mean_or_median"
    result["distribution"] = "bernoulli" if binary else "none_point_heuristic"
    result["actual"], result["participation_state"] = np.nan, "unread"
    return result


def score_ensemble(frozen, scored_cdf, category):
    if not frozen[KEYS].reset_index(drop=True).equals(scored_cdf[KEYS].reset_index(drop=True)):
        raise ValueError("ensemble/CDF scoring identities differ")
    result = frozen.copy()
    for name in scored_cdf:
        if name in {"actual", "participation_state", "outcome_state"} or name.startswith("qualified_"):
            result[name] = scored_cdf[name].to_numpy()
    result["brier"], result["log_score"] = np.nan, np.nan
    if category["support"] == "bernoulli":
        actual, probability = numeric(result, "actual"), numeric(result, "ensemble_point")
        good = result.participation_state.eq("played").to_numpy() & valid_support(actual, "bernoulli") & np.isfinite(probability)
        if (np.isfinite(probability) & ((probability < 0) | (probability > 1))).any():
            raise ValueError("ensemble probability outside [0,1]")
        result.loc[good, "brier"] = (probability[good] - actual[good]) ** 2
        with np.errstate(divide="ignore", invalid="ignore"):
            result.loc[good, "log_score"] = -np.where(actual[good] == 1, np.log(probability[good]), np.log1p(-probability[good]))
    return result


def report_ensemble(candidate, controls, category):
    report = {"target": category["target"], "method_family": "website_equalweight", "paired": [], "subgroups": [],
              "point_semantics": "genuine_bernoulli_probability" if category["support"] == "bernoulli" else "fixed point heuristic; neither law median nor law mean; no numeric probability law or CRPS"}
    deltas = []
    for method, control in controls.groupby("method", sort=True):
        for role_subset in [False, True]:
            value, rows = paired_rows(candidate, control, category, role_subset=role_subset, candidate_point="ensemble_point")
            value.update(comparator=method, status="primary" if method == "website" and not role_subset else "secondary")
            report["paired"].append(value)
            rows["comparator"], rows["population"] = method, value["population"]
            deltas.append(rows)
        if category["support"] != "bernoulli":
            value, _ = paired_rows(candidate, control, category, candidate_point="ensemble_mean_point")
            report["paired"].append(dict(value, comparator=method, status="secondary_mean_point_blend"))
    for dimension in ["position", "team", "opponent", "fallback", "history_state", "outcome_state", "abstention"]:
        if dimension in candidate:
            for value, group in candidate.groupby(dimension, dropna=False):
                actual, point = numeric(group, "actual"), numeric(group, "ensemble_point")
                good = group.participation_state.eq("played").to_numpy() & valid_support(actual, category["support"]) & np.isfinite(point)
                report["subgroups"].append({"dimension": dimension, "value": str(value), "offered_rows": len(group),
                    "point_metrics": point_metrics(point[good], actual[good])})
    if category["support"] == "bernoulli":
        brier, log = numeric(candidate, "brier"), numeric(candidate, "log_score")
        good = np.isfinite(brier)
        report["bernoulli_law"] = {"scored_rows": int(good.sum()), "brier": float(brier[good].mean()) if good.any() else None,
            "log_loss": float(log[good].mean()) if good.any() and np.isfinite(log[good]).all() else None,
            "infinite_log_losses": int(np.isposinf(log[good]).sum()),
            "log_loss_state": "infinite" if np.isposinf(log[good]).any() else "finite" if good.any() else "unavailable"}
    return report, pd.concat(deltas, ignore_index=True)
