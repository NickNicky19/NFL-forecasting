"""One evaluator for frozen empirical-CDF candidate and exact saved control rows."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .cdf_engine import KEYS, numeric, valid_support


def _observed(rows, support):
    return rows.participation_state.eq("played").to_numpy() & valid_support(numeric(rows, "actual"), support)


def summarize(rows: pd.DataFrame, support: str) -> dict:
    actual = numeric(rows, "actual")
    valid = _observed(rows, support)
    out = {"population_rows": len(rows), "supported_played_outcomes": int(valid.sum()),
           "outcome_states": rows.outcome_state.value_counts(dropna=False).to_dict(),
           "fallback_rows": int(rows.fallback.fillna("").ne("").sum()),
           "fallback_reasons": rows.fallback.fillna("").value_counts(dropna=False).to_dict(),
           "primary_role_rows": int(rows.primary_role.sum()),
           "selected_line_performance": "UNAVAILABLE_NO_RECORDED_OFFERS",
           "evidence": "exposed_historical_reconstruction; no independent confirmation"}
    scored_any = valid & np.isfinite(numeric(rows, "mean"))
    scored_rows = rows.loc[scored_any]
    out.update(distinct_scored_players=int(scored_rows.player_id.nunique()),
               distinct_scored_games=int(scored_rows.game_id.nunique()),
               distinct_scored_season_weeks=len(scored_rows[["season", "week"]].drop_duplicates()),
               supported_played_zero_rows=int((valid & (actual == 0)).sum()))
    for point in ["mean", "median"]:
        if point not in rows:
            continue
        prediction = numeric(rows, point)
        good = valid & np.isfinite(prediction)
        e = prediction[good] - actual[good]
        out[point] = {"scored_rows": int(good.sum()), "mae": float(np.abs(e).mean()) if len(e) else None,
                      "rmse": float(np.sqrt(np.mean(e ** 2))) if len(e) else None,
                      "bias_prediction_minus_outcome": float(e.mean()) if len(e) else None,
                      "p95_absolute_error": float(np.quantile(np.abs(e), .95)) if len(e) else None}
        if support == "bernoulli" and point == "mean":
            out[point]["brier"] = float(np.mean(e ** 2)) if len(e) else None
            log = numeric(rows, "log_score")[good]
            out[point]["natural_log_loss"] = float(log.mean()) if len(log) and np.isfinite(log).all() else None
            out[point]["infinite_log_losses"] = int(np.isposinf(log).sum())
            out[point]["log_loss_status"] = "infinite" if np.isposinf(log).any() else "finite" if len(log) and np.isfinite(log).all() else "unavailable"
    distribution = valid & np.isfinite(numeric(rows, "crps"))
    if distribution.any():
        group = rows.loc[distribution]
        y = numeric(group, "actual")
        lo, hi = numeric(group, "p10"), numeric(group, "p90")
        log = numeric(group, "log_score")
        out["distribution"] = {"scored_rows": len(group), "crps": float(group.crps.mean()),
            "log_score": float(log.mean()) if np.isfinite(log).all() else None,
            "infinite_log_losses": int(np.isinf(log).sum()), "interval_80_coverage": float(np.mean((y >= lo) & (y <= hi))),
            "below_p10_frequency": float(np.mean(y < lo)), "above_p90_frequency": float(np.mean(y > hi)),
            "interval_semantics": "discrete lower quantiles; overcoverage can occur",
            "pit_bracket_mean_lower": float(group.cdf_actual_below.mean()),
            "pit_bracket_mean_upper": float(group.cdf_actual.mean()),
            "calibration_claim": "none; valid probability law does not establish calibration"}
        # Key-stable randomized PIT is a descriptive diagnostic, not a fitted correction.
        uniforms = []
        for key in group[KEYS + ["target", "method"]].itertuples(index=False, name=None):
            value = int.from_bytes(hashlib.blake2b(repr((1701, key)).encode(), digest_size=8).digest(), "big")
            uniforms.append((value + .5) / 2**64)
        pit = group.cdf_actual_below.to_numpy() + np.asarray(uniforms) * (group.cdf_actual.to_numpy() - group.cdf_actual_below.to_numpy())
        out["distribution"]["randomized_pit_bins"] = np.histogram(pit, bins=np.linspace(0, 1, 11))[0].tolist()
        if support == "bernoulli":
            p = numeric(group, "mean")
            out["distribution"]["brier"] = float(np.mean((p-y)**2))
            out["distribution"]["reliability"] = []
            for b in range(10):
                good = (p >= b/10) & ((p < (b+1)/10) if b < 9 else (p <= 1))
                out["distribution"]["reliability"].append({"lower": b/10, "n": int(good.sum()),
                    "mean_probability": float(p[good].mean()) if good.any() else None,
                    "event_rate": float(y[good].mean()) if good.any() else None})
    return out


def bind_saved_control(saved: pd.DataFrame, offered: pd.DataFrame, category: dict, method: str) -> pd.DataFrame:
    """Keep exact saved points; reject identity/state/outcome mismatches."""
    if saved.duplicated(KEYS).any() or offered.duplicated(KEYS).any():
        raise ValueError("duplicate control/offered identity")
    if not saved.method.eq(method).all() or not saved.target.eq(category["target"]).all():
        raise ValueError("saved control method/target mismatch")
    required = ["team", "opponent", "position", "kickoff_utc"]
    if missing := set(required) - set(saved):
        raise ValueError("original saved control binding fields missing: " + repr(sorted(missing)))
    binding = offered[KEYS + required + ["cutoff_utc"]].merge(saved[KEYS + required + (["cutoff_utc"] if "cutoff_utc" in saved else [])],
        on=KEYS, how="outer", suffixes=("_cache", "_saved"), indicator=True, validate="one_to_one")
    if not binding._merge.eq("both").all():
        raise ValueError("saved control identity coverage differs")
    for field in required + (["cutoff_utc"] if "cutoff_utc" in saved else []):
        left, right = binding[field + "_cache"], binding[field + "_saved"]
        if field.endswith("_utc"):
            left = pd.to_datetime(left, utc=True, errors="coerce")
            right = pd.to_datetime(right, utc=True, errors="coerce")
        if not left.eq(right).all():
            raise ValueError("saved control context mismatch: " + field)
    check = offered[KEYS + [category["target"], "participation_state"]].merge(
        saved[KEYS + ["actual", "participation_state"]], on=KEYS, how="outer", suffixes=("_cache", "_saved"), indicator=True, validate="one_to_one")
    if not check._merge.eq("both").all():
        raise ValueError("saved control coverage differs from retained offered population")
    if not check.participation_state_cache.eq(check.participation_state_saved).all():
        raise ValueError("saved control participation mismatch")
    if not np.allclose(numeric(check, category["target"]), numeric(check, "actual"), equal_nan=True, rtol=0, atol=0):
        raise ValueError("saved control outcome mismatch")
    result = saved.drop(columns=["median"], errors="ignore").copy()
    result["control_cutoff_binding"] = "exact_recorded_cutoff" if "cutoff_utc" in saved else "unrecorded_in_saved_control; original_clock_not_reconstructed_or_authenticated"
    result["primary_role"] = result.position.isin(category["primary_roles"])
    history = offered[KEYS + ["f_player_games_prior"]] if "f_player_games_prior" in offered else offered[KEYS].assign(f_player_games_prior=np.nan)
    history = result[KEYS].merge(history, on=KEYS, how="left", validate="one_to_one")
    count = numeric(history, "f_player_games_prior")
    result["history_state"] = np.where(~np.isfinite(count) | (count <= 0), "cold_or_unknown", "warm")
    if category["target"] == "rush_rec_yd":
        components = result[KEYS].merge(offered[KEYS + ["rush_yd", "rec_yd"]], on=KEYS, how="left", validate="one_to_one")
        result["source_rush_yd"] = numeric(components, "rush_yd")
        result["source_rec_yd"] = numeric(components, "rec_yd")
    actual = numeric(result, "actual")
    played = result.participation_state.eq("played").to_numpy()
    valid = valid_support(actual, category["support"])
    result["outcome_state"] = np.where(~played, result.participation_state,
                              np.where(~np.isfinite(actual), "played_missing_statistic",
                              np.where(~valid, "played_invalid_support", np.where(actual == 0, "played_zero", "played_nonzero"))))
    # Old mean-only points do not acquire a new median or distribution.
    for column in ["crps", "log_score", "cdf_actual_below", "cdf_actual", "brier"]:
        result[column] = np.nan
    if category["support"] == "bernoulli":
        # A saved Bernoulli probability defines its event law uniquely. No
        # count-to-event conversion, clipping or new count law is introduced.
        if "family" not in saved or not saved.family.eq("bernoulli").all():
            raise ValueError("saved binary probability semantics unqualified")
        probability = numeric(result, "mean")
        if (np.isfinite(probability) & ((probability < 0) | (probability > 1))).any():
            raise ValueError("saved binary probability outside [0,1]")
        observed = played & valid & np.isfinite(probability)
        with np.errstate(divide="ignore", invalid="ignore"):
            logs = -np.where(actual[observed] == 1, np.log(probability[observed]), np.log1p(-probability[observed]))
        result.loc[observed, "log_score"] = logs
        result.loc[observed, "brier"] = (probability[observed]-actual[observed])**2
    return result


def paired_interval(candidate: pd.DataFrame, control: pd.DataFrame, support: str, *, cluster: str, primary_roles_only=True, replicates=500):
    if cluster not in {"week", "game"} or replicates != 500:
        raise ValueError("unregistered uncertainty configuration")
    candidate = candidate.loc[candidate.primary_role] if primary_roles_only else candidate
    control = control.loc[control.primary_role] if primary_roles_only else control
    candidate_years = sorted(int(y) for y in candidate.season.unique())
    control_years = sorted(int(y) for y in control.season.unique())
    common_years = sorted(set(candidate_years) & set(control_years))
    candidate = candidate.loc[candidate.season.isin(common_years)]
    control = control.loc[control.season.isin(common_years)]
    joined = candidate[KEYS + ["actual", "participation_state", "mean", "median"]].merge(
        control[KEYS + ["actual", "participation_state", "mean"]], on=KEYS, suffixes=("_candidate", "_control"), how="outer", indicator=True, validate="one_to_one")
    if not joined._merge.eq("both").all():
        raise ValueError("paired population does not match")
    if not np.allclose(joined.actual_candidate, joined.actual_control, equal_nan=True, rtol=0, atol=0):
        raise ValueError("paired outcomes differ")
    if not joined.participation_state_candidate.eq(joined.participation_state_control).all():
        raise ValueError("paired participation differs")
    y = numeric(joined, "actual_candidate")
    point = numeric(joined, "mean_candidate" if support == "bernoulli" else "median")
    baseline = numeric(joined, "mean_control")
    good = joined.participation_state_candidate.eq("played").to_numpy() & valid_support(y, support) & np.isfinite(point) & np.isfinite(baseline)
    joined = joined.loc[good].copy()
    error_a, error_b = point[good]-y[good], baseline[good]-y[good]
    joined["delta"] = error_a**2-error_b**2 if support == "bernoulli" else np.abs(error_a)-np.abs(error_b)
    grouped = joined.groupby(["season", "week"] if cluster == "week" else ["season", "game_id"]).delta.agg(["sum", "count"])
    out = {"paired_rows": len(joined), "clusters": len(grouped), "cluster": cluster,
           "candidate_years": candidate_years, "control_years": control_years, "compared_complete_years": common_years,
           "excluded_unpaired_years": sorted(set(candidate_years) ^ set(control_years)),
           "partial_failure_policy": "only complete common annual cells paired; all attempt failures/population summaries retained; no surviving-panel selection",
           "primary_roles_only": primary_roles_only, "primary_loss": "brier" if support == "bernoulli" else "median_mae",
           "mean_delta_candidate_minus_control": float(joined.delta.mean()) if len(joined) else None,
           "interval": None, "replicates": replicates, "seed": 1701 if cluster == "week" else 1702,
           "monte_carlo_tail_probability_se": float(np.sqrt(.025*.975/replicates)),
           "monte_carlo_error_semantics": "binomial SE of nominal .025 tail fraction only; interval endpoint uncertainty in target units is not established",
           "interval_semantics": "nominal95% unadjusted descriptive percentile; no familywise coverage, selection, confirmation or promotion claim; full adaptive search exposed"}
    if len(grouped) < 8:
        out["reason"] = "fewer_than_8_clusters"
        return out
    rng = np.random.default_rng(out["seed"])
    indices = rng.integers(0, len(grouped), size=(replicates, len(grouped)))
    draws = grouped["sum"].to_numpy()[indices].sum(axis=1) / grouped["count"].to_numpy()[indices].sum(axis=1)
    out["interval"] = np.quantile(draws, [.025, .975]).tolist()
    return out


def report_tables(rows: pd.DataFrame, category: dict):
    summaries, groups, paired, ablations, distribution_comparisons = [], [], [], [], []
    for method, data in rows.groupby("method", sort=True):
        for population, subset in [("all_offered", data), ("primary_roles", data.loc[data.primary_role])]:
            summaries.append({"method": method, "population": population, **summarize(subset, category["support"])})
        work = data.copy()
        actual = numeric(work, "actual")
        supported = _observed(work, category["support"])
        work["outcome_sign"] = np.where(~supported, "unscored", np.where(actual < 0, "negative", np.where(actual == 0, "zero", "positive")))
        dimensions = ["position", "season", "period", "outcome_state", "outcome_sign", "fallback", "player_id", "team", "opponent"]
        if "history_state" in work:
            dimensions.append("history_state")
        if category["target"] == "rush_rec_yd":
            rush, rec = numeric(work, "source_rush_yd"), numeric(work, "source_rec_yd")
            work["component_sign"] = np.where(~supported, "unscored", np.where((rush < 0) | (rec < 0), "either_component_negative", "neither_component_negative"))
            dimensions.append("component_sign")
        work["period"] = work.season_type.astype(str) if "season_type" in work else np.where(numeric(work, "week") > np.where(numeric(work, "season") >= 2021, 18, 17), "postseason", "regular")
        for dimension in dimensions:
            for value, subset in work.groupby(dimension, dropna=False):
                groups.append({"method": method, "dimension": dimension, "value": str(value), **summarize(subset, category["support"])})
    for method in ["leaf_cdf_base", "leaf_cdf_context"]:
        candidate = rows.loc[rows.method.eq(method)]
        if candidate.empty:
            continue
        for comparator in ["pooled", "recent"]:
            control = rows.loc[rows.method.eq(comparator)]
            if control.empty:
                continue
            for cluster in ["week", "game"]:
                paired.append({"method": method, "comparator": comparator,
                    "status": "primary" if comparator == "pooled" else "secondary",
                    **paired_interval(candidate, control, category["support"], cluster=cluster)})
    base = rows.loc[rows.method.eq("leaf_cdf_base")]
    context = rows.loc[rows.method.eq("leaf_cdf_context")]
    if len(base) and len(context):
        control = base.copy()
        if category["support"] != "bernoulli":
            control["mean"] = control["median"]
        for cluster in ["week", "game"]:
            ablations.append({"contrast": "context_minus_base", "status": "secondary",
                **paired_interval(context, control, category["support"], cluster=cluster)})
    role_prior = rows.loc[rows.method.eq("role_prior")]
    if len(role_prior):
        for method in ["leaf_cdf_base", "leaf_cdf_context"]:
            candidate = rows.loc[rows.method.eq(method)]
            if candidate.empty:
                continue
            for metric in ["crps", "log_score"]:
                for cluster in ["week", "game"]:
                    distribution_comparisons.append({"method": method, "comparator": "role_prior", "metric": metric,
                        **paired_distribution_interval(candidate, role_prior, metric, cluster=cluster)})
    return {"target": category["target"], "summary": summaries, "subgroups": groups, "paired": paired,
            "feature_ablations": ablations, "distribution_vs_role_prior": distribution_comparisons,
            "interpretation": "all exposed; no independent confirmation; no selected winner; no joint coherence or financial claim"}


def paired_distribution_interval(candidate, control, metric, *, cluster):
    if metric not in {"crps", "log_score"} or cluster not in {"week", "game"}:
        raise ValueError("unregistered distribution diagnostic")
    a, b = candidate.loc[candidate.primary_role], control.loc[control.primary_role]
    candidate_years = sorted(int(y) for y in a.season.unique())
    control_years = sorted(int(y) for y in b.season.unique())
    common_years = sorted(set(candidate_years) & set(control_years))
    a, b = a.loc[a.season.isin(common_years)], b.loc[b.season.isin(common_years)]
    joined = a[KEYS + ["actual", metric]].merge(b[KEYS + ["actual", metric]], on=KEYS, how="outer", suffixes=("_a", "_b"), indicator=True, validate="one_to_one")
    if not joined._merge.eq("both").all() or not np.allclose(joined.actual_a, joined.actual_b, equal_nan=True, atol=0, rtol=0):
        raise ValueError("distribution comparison identity/outcome mismatch")
    x, y = numeric(joined, metric+"_a"), numeric(joined, metric+"_b")
    good = np.isfinite(x) & np.isfinite(y)
    joined = joined.loc[good].copy()
    joined["delta"] = x[good]-y[good]
    grouped = joined.groupby(["season", "week"] if cluster == "week" else ["season", "game_id"]).delta.agg(["sum", "count"])
    out = {"paired_rows": len(joined), "clusters": len(grouped), "cluster": cluster,
           "candidate_years": candidate_years, "control_years": control_years, "compared_complete_years": common_years,
           "excluded_unpaired_years": sorted(set(candidate_years) ^ set(control_years)),
           "mean_delta_candidate_minus_control": float(joined.delta.mean()) if len(joined) else None,
           "interval": None, "replicates": 500, "seed": 1701 if cluster == "week" else 1702,
           "monte_carlo_tail_probability_se": float(np.sqrt(.025*.975/500)),
           "monte_carlo_error_semantics": "binomial SE of nominal .025 tail fraction only; interval endpoint uncertainty in target units is not established",
           "status": "secondary_distribution_diagnostic", "interval_semantics": "nominal95% unadjusted descriptive; no familywise coverage or calibration claim"}
    if len(grouped) < 8:
        out["reason"] = "fewer_than_8_clusters"
        return out
    rng = np.random.default_rng(out["seed"])
    indices = rng.integers(0, len(grouped), size=(500, len(grouped)))
    draws = grouped["sum"].to_numpy()[indices].sum(axis=1)/grouped["count"].to_numpy()[indices].sum(axis=1)
    out["interval"] = np.quantile(draws, [.025, .975]).tolist()
    return out
