"""Pure reports for the fixed, exposed, source-matched base benchmark.

Existing evaluators supply scores and exact pairs. This adapter adds explicit
slot coverage and the separately registered whole-cluster resampling protocol.
It performs no I/O, fitting, inference, source acquisition or promotion.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from .cdf_engine import KEYS, numeric, valid_support
from .cdf_evaluation import summarize as cdf_summary
from .models import TARGETS
from .role_boosting_campaign import point_pairs, summary as point_summary

VERSION = "source-matched-reporting-v1"
YEARS = (2022, 2023, 2024)
METHODS = ("leaf_cdf", "median_hgb", "count_A", "role_B", "recent", "pooled")
LAW_METHODS = ("leaf_cdf", "role_prior")
CONTRASTS = tuple(("leaf_cdf", other) for other in METHODS[1:]) + tuple(
    (candidate, reference) for candidate in ("median_hgb", "count_A", "role_B") for reference in ("recent", "pooled"))
CONTEXT = ("position", "team", "opponent", "kickoff_utc", "cutoff_utc")
LAW_FIELDS = ("p10", "p90", "variance", "crps", "log_score", "cdf_actual_below", "cdf_actual")
LOSS_COLUMNS = [*KEYS, "target", "year", "candidate_method", "comparator", "metric", "cutoff_utc", "kickoff_utc",
    "primary_role", "paired_eligible", "primary_paired_eligible", "candidate_loss", "control_loss", "delta_candidate_minus_control"]
EXPOSURE = "All 2022-2024 exposed development reconstruction; nominal descriptive diagnostics; no independent confirmation or promotion"


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return {"state": "positive_infinity" if value > 0 else "negative_infinity"}
        return float(value)
    return value


def _unit(target, support):
    return "fantasy points" if target == "fantasy_ppr" else "probability" if support == "bernoulli" else "yards" if target.endswith("_yd") else "events"


def _fixed_bootstrap(replicates, seed):
    if type(replicates) is not int or replicates != 500 or type(seed) is not int or seed != 1703:
        raise ValueError("fixed 500 PCG64 replicates and seed 1703 required")


def _validate(rows, categories, replicates, seed):
    _fixed_bootstrap(replicates, seed)
    if not isinstance(categories, dict) or set(categories) != set(TARGETS):
        raise ValueError("all twelve frozen category contracts required")
    if categories["fantasy_ppr"].get("state") == "READY" or any(categories[t].get("state") != "READY" for t in TARGETS if t != "fantasy_ppr"):
        raise ValueError("eleven supported categories and blocked exact PPR required")
    for target in TARGETS:
        if target != "fantasy_ppr" and (categories[target].get("support") not in {"signed_integer", "count", "bernoulli"}
                or not categories[target].get("primary_roles")):
            raise ValueError("all supported category support/role contracts required")
    if not isinstance(rows, pd.DataFrame) or not rows.columns.is_unique:
        raise ValueError("scored dataframe with unique columns required")
    required = {*KEYS, *CONTEXT, "year", "target", "method", "point", "probability", "mean", "median", "actual",
        "participation_state", "outcome_state", "primary_role", "fallback", "history_state", *LAW_FIELDS}
    if required - set(rows):
        raise ValueError("missing normalized scored-row fields: " + repr(sorted(required - set(rows))))
    if rows.target.eq("fantasy_ppr").any() or not rows.target.isin(TARGETS).all() or not rows.method.isin((*METHODS, "role_prior")).all():
        raise ValueError("unregistered target/method or forbidden exact PPR scored rows")
    if rows[KEYS].isna().any(axis=None) or rows.duplicated(["target", "method", *KEYS]).any():
        raise ValueError("null or duplicate scored player-game-method identity")
    for name in ("season", "year", "week"):
        values = numeric(rows, name)
        if not np.isfinite(values).all() or not (values == np.floor(values)).all():
            raise ValueError("integer year/season/week metadata required")
    if not rows.year.eq(rows.season).all() or not rows.season.isin(YEARS).all():
        raise ValueError("only fixed 2022-2024 evaluation years permitted")
    if not rows.participation_state.isin(["played", "DNP", "unknown"]).all() or len(rows) and (not is_bool_dtype(rows.primary_role.dtype) or rows.primary_role.isna().any()):
        raise ValueError("qualified participation and frozen boolean role mask required")
    for name in ("point", "probability", "mean", "median", "actual", *LAW_FIELDS):
        if len(rows) and not is_numeric_dtype(rows[name].dtype):
            raise ValueError("numeric scored fields required: " + name)
        if name != "log_score" and np.isinf(numeric(rows, name)).any():
            raise ValueError("infinite points/outcomes/finite-law fields forbidden")
    if np.isneginf(numeric(rows, "log_score")).any() or (numeric(rows, "log_score") < 0).any():
        raise ValueError("log loss must be nonnegative, missing or positive infinity")
    # Only clock columns are replaced; other input arrays remain read-only.
    result = rows.copy(deep=False)
    for name in ("cutoff_utc", "kickoff_utc"):
        result[name] = pd.to_datetime(result[name], utc=True, errors="raise")
        if result[name].isna().any():
            raise ValueError("qualified context clocks required")
    if result.cutoff_utc.gt(result.kickoff_utc).any():
        raise ValueError("cutoff cannot follow kickoff")
    for target, part in result.groupby("target", sort=False):
        category = categories[target]
        support = category.get("support")
        if support not in {"signed_integer", "count", "bernoulli"} or not category.get("primary_roles"):
            raise ValueError("fixed supported category/primary role contract required")
        if not part.primary_role.eq(part.position.isin(category["primary_roles"])).all():
            raise ValueError("primary-role mask differs from frozen category contract")
        point, probability = numeric(part, "point"), numeric(part, "probability")
        if support == "bernoulli":
            if ((np.isfinite(point) & ((point < 0) | (point > 1))).any()
                    or not np.allclose(point, probability, rtol=0, atol=0, equal_nan=True)):
                raise ValueError("genuine unchanged Bernoulli probability required")
        elif np.isfinite(probability).any() or support == "count" and (point < 0).any():
            raise ValueError("numeric points cannot acquire probabilities or negative count values")
        law = part.loc[part.method.isin(LAW_METHODS)]
        expected = numeric(law, "mean" if support == "bernoulli" else "median")
        if not np.allclose(numeric(law, "point"), expected, rtol=0, atol=0, equal_nan=True):
            raise ValueError("CDF point must retain its actual lower median or event probability")
        scored = np.isfinite(numeric(law, "crps"))
        below, at = numeric(law, "cdf_actual_below"), numeric(law, "cdf_actual")
        if (scored & (~np.isfinite(below) | ~np.isfinite(at) | (below < 0) | (at > 1) | (below > at))).any():
            raise ValueError("invalid scored CDF bracket")
        if (numeric(law, "crps") < 0).any() or (numeric(law, "variance") < 0).any() or (numeric(law, "p10") > numeric(law, "p90")).any():
            raise ValueError("invalid CDF loss/variance/quantile support")
        for name in ("median", "p10", "p90"):
            values = numeric(law, name)
            if (np.isfinite(values) & ~valid_support(values, support)).any():
                raise ValueError("CDF lower quantiles must retain exact label support")
    return result


def _slots(part, category, *, blocked=False):
    metadata = category.get("benchmark_slots", [])
    explicit = {}
    for record in metadata:
        if not isinstance(record, dict) or set(record) - {"year", "method", "state", "reason"} or not {"year", "method", "state"} <= set(record):
            raise ValueError("invalid benchmark slot metadata")
        key = (record["year"], record["method"])
        if key in explicit or type(key[0]) is not int or key[0] not in YEARS or key[1] not in METHODS or not isinstance(record["state"], str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", record["state"]) is None:
            raise ValueError("duplicate or unregistered benchmark slot")
        if blocked and not record["state"].startswith("BLOCKED"):
            raise ValueError("exact PPR slot cannot claim model completion or execution")
        explicit[key] = record
    output = []
    for year in YEARS:
        for method in METHODS:
            n = int((part.year.eq(year) & part.method.eq(method)).sum())
            record = explicit.get((year, method), {})
            state = "BLOCKED_EXACT_PPR" if blocked else record.get("state", "COMPLETED" if n else "MISSING_OR_UNRUN")
            if not blocked and (state == "COMPLETED") != bool(n):
                raise ValueError("completed slot state and scored-row presence differ")
            output.append({"year": year, "method": method, "state": state, "offered_rows": n,
                           "failure_detail_available": bool(record.get("reason"))})
    return output


def _bootstrap(losses, mask, cluster, replicates, seed):
    selected = losses.loc[mask]
    delta = numeric(selected, "delta_candidate_minus_control")
    keys = ["season", "week"] if cluster == "week" else ["season", "game_id"]
    out = {"cluster": cluster, "paired_rows": len(selected), "clusters": 0, "state": "N/A", "interval": None,
        "replicates": replicates, "seed": seed, "generator": "PCG64", "percentile_method": "linear", "level": .95,
        "semantics": "whole-cluster paired sums/counts; nominal descriptive exposed-sample interval; no IID row resampling or qualification"}
    out["clusters"] = len(selected[keys].drop_duplicates())
    if not np.isfinite(delta).all():
        out["reason"] = "nonfinite_or_undefined_paired_log_loss_delta"
        return out
    grouped = selected.groupby(keys, sort=True).delta_candidate_minus_control.agg(["sum", "count"])
    out["clusters"] = len(grouped)
    if len(grouped) < 8:
        out["reason"] = "fewer_than_8_clusters"
        return out
    generator = np.random.Generator(np.random.PCG64(seed))
    indices = generator.integers(0, len(grouped), size=(replicates, len(grouped)))
    draws = grouped["sum"].to_numpy()[indices].sum(axis=1) / grouped["count"].to_numpy()[indices].sum(axis=1)
    out.update(state="DESCRIPTIVE", interval=np.quantile(draws, [.025, .975], method="linear").tolist())
    return out


def _aligned(a, b):
    joined = a[KEYS + list(CONTEXT)].merge(b[KEYS + list(CONTEXT)], on=KEYS, how="outer", indicator=True,
                                         suffixes=("_a", "_b"), validate="one_to_one")
    if not joined._merge.eq("both").all():
        raise ValueError("completed comparison offered key populations differ")
    for name in CONTEXT:
        if not joined[name + "_a"].eq(joined[name + "_b"]).all():
            raise ValueError("paired context/cutoff mismatch: " + name)


def _compact(pairs, a, target, candidate, comparator, metric, dtypes):
    context = a[KEYS + ["cutoff_utc", "kickoff_utc"]]
    out = pairs[KEYS + ["primary_role", "paired_eligible", "candidate_loss", "control_loss", "delta_candidate_minus_control"]].merge(
        context, on=KEYS, how="left", sort=False, validate="one_to_one")
    out["target"], out["year"], out["candidate_method"], out["comparator"], out["metric"] = target, out.season, candidate, comparator, metric
    out["primary_paired_eligible"] = out.paired_eligible & out.primary_role
    for name, dtype in dtypes.items():
        out[name] = out[name].astype(dtype)
    return out[LOSS_COLUMNS]


def _summary(part, category, method):
    out = point_summary(part, category)
    point = numeric(part, "point")
    observed = part.participation_state.eq("played").to_numpy() & valid_support(numeric(part, "actual"), category["support"])
    out.update(fallback_rows=int(part.fallback.fillna("").ne("").sum()),
        fallback_reasons=part.fallback.fillna("").value_counts(dropna=False).to_dict(),
        history_states=part.history_state.value_counts(dropna=False).to_dict(),
        position_rows=part.position.value_counts(dropna=False).to_dict(),
        supported_played_zero_rows=int((observed & (numeric(part, "actual") == 0)).sum()),
        supported_played_negative_rows=int((observed & (numeric(part, "actual") < 0)).sum()),
        paired_score_semantics="conditional on supported played outcomes; all offered coverage retained")
    if method in LAW_METHODS:
        out["cdf_law"] = cdf_summary(part, category["support"])
        mean = numeric(part, "mean")
        good = observed & np.isfinite(mean)
        out["cdf_mean_mse"] = float(np.mean((mean[good] - numeric(part, "actual")[good]) ** 2)) if good.any() else None
        mass = numeric(part, "cdf_actual") - numeric(part, "cdf_actual_below")
        good_mass = observed & np.isfinite(mass)
        zeros = good_mass & (numeric(part, "actual") == 0)
        out["observed_atom_mass"] = {"rows": int(good_mass.sum()), "mean_mass_at_observed_outcome": float(mass[good_mass].mean()) if good_mass.any() else None,
            "observed_zero_rows": int(zeros.sum()), "mean_mass_at_zero_on_observed_zero_rows": float(mass[zeros].mean()) if zeros.any() else None,
            "all_query_zero_probability_calibration": "N/A; frozen rows do not contain zero CDF for every query",
            "selected_line_push_mass": "N/A; no historical recorded line offers"}
    return out


def reporting_header(*, replicates=500, seed=1703):
    """Return fresh aggregate metadata for either whole or target-local use."""
    _fixed_bootstrap(replicates, seed)
    return {"schema_version": VERSION, "evidence": EXPOSURE, "years": list(YEARS), "methods": list(METHODS),
        "planned_slots": 216, "supported_slots": 198, "blocked_exact_ppr_slots": 18,
        "historical_SITE": "N/A; no regenerated historical SITE forecasts", "historical_raw_Sleeper": "N/A; no recorded compatible historical forecasts",
        "bootstrap": {"replicates": replicates, "seed": seed, "generator": "PCG64", "percentile_method": "linear", "minimum_clusters": 8}, "targets": {}}


def build_target_report(scored_rows, categories, *, target, replicates=500, seed=1703):
    """Run the same evaluator with one target's rows resident in memory.

    Full frozen category metadata is required; sibling execution statuses are
    irrelevant to this target and are neither validated against nor returned
    with its local rows. Root combines returned items under reporting_header().
    """
    if target not in TARGETS or not isinstance(scored_rows, pd.DataFrame) or "target" not in scored_rows or not scored_rows.target.eq(target).all():
        raise ValueError("target-local reporting requires only the named target's rows")
    if not isinstance(categories, dict) or set(categories) != set(TARGETS):
        raise ValueError("all twelve frozen category contracts required")
    local_categories = {name: dict(category, benchmark_slots=[]) if name != target else category for name, category in categories.items()}
    report, losses = build_reports(scored_rows, local_categories, replicates=replicates, seed=seed)
    return report["targets"][target], losses


def build_reports(scored_rows, categories, *, replicates=500, seed=1703):
    """Return JSON-safe aggregates and one private annual paired-loss copy.

    Missing package rows remain N/A slots. Pooled contrasts use complete common
    annual cells and retain excluded years. Units and targets are never pooled.
    """
    rows = _validate(scored_rows, categories, replicates, seed)
    loss_dtypes = {name: pd.CategoricalDtype(categories=rows[name].unique()) for name in ("game_id", "player_id")}
    loss_dtypes.update({"target": pd.CategoricalDtype(categories=TARGETS),
        "candidate_method": pd.CategoricalDtype(categories=METHODS),
        "comparator": pd.CategoricalDtype(categories=(*METHODS, "role_prior")),
        "metric": pd.CategoricalDtype(categories=("mae", "brier", "crps", "log_score")),
        "season": "int16", "year": "int16"})
    report = reporting_header(replicates=replicates, seed=seed)
    private = []
    for target in TARGETS:
        category = {**categories[target], "target": target}
        part = rows.loc[rows.target.eq(target)]
        blocked = target == "fantasy_ppr"
        item = {"state": "BLOCKED_EXACT_PPR" if blocked else "EXPOSED_DEVELOPMENT_DIAGNOSTIC", "support": category.get("support"),
            "unit": _unit(target, category.get("support")), "slots": _slots(part, category, blocked=blocked),
            "summaries": [], "point_comparisons": [], "distribution_comparisons": []}
        report["targets"][target] = item
        if blocked or part.empty:
            continue
        for period in (*map(str, YEARS), "pooled2022-2024"):
            period_rows = part if period.startswith("pooled") else part.loc[part.year.eq(int(period))]
            for method in (*METHODS, "role_prior"):
                selected = period_rows.loc[period_rows.method.eq(method)]
                for primary in (True, False):
                    data = selected.loc[selected.primary_role] if primary else selected
                    cell = {"period": period, "method": method, "population": "primary_roles" if primary else "all_offered",
                            "state": "COMPLETED" if len(selected) else "N/A_MISSING_SLOT",
                            "included_years": sorted(int(y) for y in selected.year.unique()),
                            "excluded_years": sorted(set(YEARS if period.startswith("pooled") else [int(period)]) - set(selected.year))}
                    if len(selected) and cell["excluded_years"]:
                        cell["state"] = "PARTIAL_COMPLETED_YEARS"
                    if len(selected):
                        cell.update(_summary(data, category, method))
                    item["summaries"].append(cell)
            for candidate, comparator in (*CONTRASTS, ("leaf_cdf", "role_prior")):
                a = period_rows.loc[period_rows.method.eq(candidate)]
                b = period_rows.loc[period_rows.method.eq(comparator)]
                common = sorted(set(a.year) & set(b.year))
                a, b = a.loc[a.year.isin(common)], b.loc[b.year.isin(common)]
                metrics = ("crps", "log_score") if comparator == "role_prior" else ("brier" if category["support"] == "bernoulli" else "mae",)
                container = item["distribution_comparisons"] if comparator == "role_prior" else item["point_comparisons"]
                if not common:
                    for metric in metrics:
                        for primary in (True, False):
                            container.append({"period": period, "candidate": candidate, "comparator": comparator, "metric": metric,
                                "population": "primary_roles" if primary else "all_offered", "state": "N/A_MISSING_SLOT",
                                "included_years": [], "excluded_years": list(YEARS) if period.startswith("pooled") else [int(period)]})
                    continue
                _aligned(a, b)
                for metric in metrics:
                    for primary in (True, False):
                        paired, pairs = point_pairs(a, b, category, role_subset=primary)
                        paired.update(period=period, candidate=candidate, comparator=comparator, metric=metric,
                            population="primary_roles" if primary else "all_offered", state="COMPLETED", included_years=[int(y) for y in common],
                            excluded_years=sorted(set(YEARS if period.startswith("pooled") else [int(period)]) - set(common)), uncertainty=EXPOSURE)
                        if paired["excluded_years"]:
                            paired["state"] = "PARTIAL_COMMON_COMPLETED_YEARS"
                        if comparator == "role_prior":
                            scores = a[KEYS + [metric]].merge(b[KEYS + [metric]], on=KEYS, suffixes=("_a", "_b"), validate="one_to_one")
                            pairs = pairs.merge(scores, on=KEYS, how="left", sort=False, validate="one_to_one")
                            x, y = numeric(pairs, metric + "_a"), numeric(pairs, metric + "_b")
                            good = pairs.participation_state.eq("played").to_numpy() & valid_support(numeric(pairs, "actual"), category["support"])
                            good &= ~np.isnan(x) & ~np.isnan(y)
                            if primary:
                                good &= pairs.primary_role.to_numpy()
                            pairs["paired_eligible"] = good
                            pairs["candidate_loss"], pairs["control_loss"] = np.where(good, x, np.nan), np.where(good, y, np.nan)
                            with np.errstate(invalid="ignore"):
                                pairs["delta_candidate_minus_control"] = np.where(good, x - y, np.nan)
                            delta = numeric(pairs.loc[good], "delta_candidate_minus_control")
                            paired = {k: v for k, v in paired.items() if k not in {"candidate_point_metrics", "control_literal_point_metrics", "paired_binary", "candidate_point", "primary_loss", "candidate_loss", "control_loss", "improvement_pct", "delta_candidate_minus_control"}}
                            finite = np.isfinite(delta).all()
                            paired.update(paired_rows=int(good.sum()), primary_loss=metric, delta_candidate_minus_control=float(delta.mean()) if len(delta) and finite else None,
                                candidate_loss=float(x[good].mean()) if good.any() else None, control_loss=float(y[good].mean()) if good.any() else None,
                                loss_state="finite" if finite else "nonfinite_or_undefined_log_loss",
                                infinite_candidate_losses=int(np.isposinf(x[good]).sum()), infinite_control_losses=int(np.isposinf(y[good]).sum()),
                                undefined_delta_rows=int(np.isnan(delta).sum()))
                        paired.pop("interval", None)
                        paired["intervals"] = [_bootstrap(pairs, pairs.paired_eligible, cluster, replicates, seed) for cluster in ("week", "game")]
                        container.append(paired)
                        if not primary and not period.startswith("pooled"):
                            private.append(_compact(pairs, a, target, candidate, comparator, metric, loss_dtypes))
    losses = pd.concat(private, ignore_index=True) if private else pd.DataFrame(columns=LOSS_COLUMNS)
    return _json_safe(report), losses
