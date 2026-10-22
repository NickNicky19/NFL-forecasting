"""No-fit descriptive audit of frozen direct and component combined-yard means.

Reads immutable local campaign rows and emits aggregates only. This module has
no model import, training, candidate selection, prediction or publication call.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

AUDIT_VERSION = "frozen-combined-yard-audit-v1"
KEYS = ["season", "week", "game_id", "player_id"]


def _finite(series: pd.Series) -> pd.Series:
    return pd.Series(np.isfinite(pd.to_numeric(series, errors="coerce")), index=series.index)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    if not len(actual):
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    error = predicted - actual
    return {"n": len(error), "mae": float(np.mean(abs(error))),
            "rmse": float(np.sqrt(np.mean(error ** 2))), "bias": float(error.mean())}


def paired_week_deltas(rows: pd.DataFrame, *, seed: int = 20261022,
                       replicates: int = 500, family_size: int = 12,
                       cluster: str = "week") -> dict[str, Any]:
    """Paired whole-week/game resampling, row-weighted sum-minus-direct deltas."""
    if not 1 <= replicates <= 500 or family_size < 1:
        raise ValueError("bounded_bootstrap_budget_required")
    if cluster not in {"week", "game"}:
        raise ValueError("unsupported_uncertainty_cluster")
    columns = ["season", "week", "actual", "direct_mean", "component_mean"]
    if cluster == "game":
        columns.append("game_id")
    rows = rows[columns].copy()
    direct_error = rows.direct_mean - rows.actual
    component_error = rows.component_mean - rows.actual
    rows = rows.assign(direct_abs=abs(direct_error), component_abs=abs(component_error),
                       direct_sq=direct_error ** 2, component_sq=component_error ** 2,
                       direct_error=direct_error, component_error=component_error, n=1)
    cluster_columns = ["season", "week"] if cluster == "week" else ["season", "game_id"]
    grouped = rows.groupby(cluster_columns)[["direct_abs", "component_abs", "direct_sq",
                                                      "component_sq", "direct_error", "component_error", "n"]].sum()
    result: dict[str, Any] = {"paired_n": len(rows), "cluster_unit": cluster,
                             "clusters": len(grouped),
                             "week_clusters": int(rows[["season", "week"]].drop_duplicates().shape[0]),
                             "replicates": replicates, "seed": seed,
                             "confidence": 1 - .05 / family_size,
                             "family_size": family_size,
                             "delta_direction": "component_sum_minus_direct"}
    if rows.empty:
        result.update(deltas=None, intervals=None, reason="no_supported_paired_rows")
        return result
    direct = _metrics(rows.actual.to_numpy(), rows.direct_mean.to_numpy())
    component = _metrics(rows.actual.to_numpy(), rows.component_mean.to_numpy())
    result["deltas"] = {metric: component[metric] - direct[metric] for metric in ("mae", "rmse", "bias")}
    if len(grouped) < 8:
        result.update(intervals=None, reason=f"fewer_than_8_{cluster}_clusters")
        return result
    generator = np.random.default_rng(seed)
    chosen = generator.integers(0, len(grouped), size=(replicates, len(grouped)))
    values = grouped.to_numpy()[chosen].sum(axis=1)
    count = values[:, -1]
    bootstrap = {"mae": (values[:, 1] - values[:, 0]) / count,
                 "rmse": np.sqrt(values[:, 3] / count) - np.sqrt(values[:, 2] / count),
                 "bias": (values[:, 5] - values[:, 4]) / count}
    q = .05 / family_size / 2
    result["intervals"] = {key: np.quantile(value, [q, 1-q]).tolist() for key, value in bootstrap.items()}
    return result


def audit_method(direct: pd.DataFrame, rushing: pd.DataFrame, receiving: pd.DataFrame,
                 *, method: str, season: int = 2024) -> dict[str, Any]:
    """Retain missing/unmatched/incompatible flags and score only valid pairs."""
    frames = {}
    for name, target, frame in (("direct", "rush_rec_yd", direct), ("rush", "rush_yd", rushing),
                                 ("rec", "rec_yd", receiving)):
        required = set(KEYS + ["target", "method", "actual", "mean", "participation_state",
                                "p_participation", "team", "opponent", "kickoff_utc"])
        if required - set(frame):
            raise ValueError(f"missing_{name}_columns:{sorted(required-set(frame))}")
        if not frame.season.eq(season).all() or not frame.target.eq(target).all() or not frame.method.eq(method).all():
            raise ValueError("wrong_frozen_target_method_or_season")
        if frame.duplicated(KEYS).any():
            raise ValueError("duplicate_frozen_player_game")
        subset = frame.drop(columns=["target", "method"]).copy()
        for field in ("actual", "mean", "p_participation"):
            subset[field] = pd.to_numeric(subset[field], errors="coerce")
        subset[name + "_present"] = True
        frames[name] = subset.rename(columns={key: name + "_" + key for key in subset if key not in KEYS and key != name + "_present"})
    rows = frames["direct"].merge(frames["rush"], on=KEYS, how="outer", validate="one_to_one")
    rows = rows.merge(frames["rec"], on=KEYS, how="outer", validate="one_to_one")
    present = rows[["direct_present", "rush_present", "rec_present"]].eq(True).all(axis=1)
    identity = present.copy()
    for key in ("team", "opponent", "kickoff_utc"):
        identity &= rows["direct_" + key].eq(rows["rush_" + key]) & rows["direct_" + key].eq(rows["rec_" + key])
    states_match = (rows.direct_participation_state.eq(rows.rush_participation_state)
                    & rows.direct_participation_state.eq(rows.rec_participation_state))
    probability_ok = pd.Series(True, index=rows.index)
    for name in ("direct", "rush", "rec"):
        probability = pd.to_numeric(rows[name + "_p_participation"], errors="coerce")
        probability_ok &= _finite(probability) & probability.between(0, 1)
    probability_ok &= np.isclose(rows.direct_p_participation, rows.rush_p_participation, atol=1e-12, rtol=0)
    probability_ok &= np.isclose(rows.direct_p_participation, rows.rec_p_participation, atol=1e-12, rtol=0)
    compatible = present & identity & states_match & probability_ok
    actual_complete = _finite(rows.direct_actual) & _finite(rows.rush_actual) & _finite(rows.rec_actual)
    actual_match = pd.Series(np.isclose(rows.direct_actual, rows.rush_actual + rows.rec_actual,
                                       atol=1e-9, rtol=0), index=rows.index)
    valid_outcomes = compatible & actual_complete & actual_match & rows.direct_participation_state.eq("played")
    direct_finite = _finite(rows.direct_mean)
    component_finite = _finite(rows.rush_mean) & _finite(rows.rec_mean)
    rows["component_mean"] = rows.rush_mean + rows.rec_mean
    structural = compatible & direct_finite & component_finite
    discrepancy = (rows.component_mean - rows.direct_mean).abs()
    paired = valid_outcomes & direct_finite & component_finite
    direct_natural = (rows.direct_present.eq(True) & rows.direct_participation_state.eq("played")
                      & _finite(rows.direct_actual) & direct_finite)
    component_natural = valid_outcomes & component_finite
    def metrics(mask, prediction):
        return _metrics(rows.loc[mask, "direct_actual"].to_numpy(dtype=float), rows.loc[mask, prediction].to_numpy(dtype=float))
    paired_rows = rows.loc[paired, KEYS + ["direct_actual", "direct_mean", "component_mean"]].rename(columns={"direct_actual": "actual"})
    result = {
        "method": method, "season": season, "population": "conditional_on_playing; supplied allskill rows including postseason",
        "population_rows_union": len(rows),
        "source_rows": {key: len(frame) for key, frame in frames.items()},
        "aligned_three_rows": int(present.sum()), "unmatched_rows": int((~present).sum()),
        "identity_incompatible_rows": int((present & ~identity).sum()),
        "participation_state_incompatible_rows": int((present & ~states_match).sum()),
        "participation_probability_incompatible_or_missing_rows": int((present & ~probability_ok).sum()),
        "direct_participation_counts": rows.direct_participation_state.fillna("unmatched").value_counts().to_dict(),
        "complete_source_component_outcomes": int((present & actual_complete).sum()),
        "combined_outcome_component_mismatches": int((present & actual_complete & ~actual_match).sum()),
        "missing_source_component_outcomes": int((present & ~actual_complete).sum()),
        "played_missing_source_component_outcomes": int((present & rows.direct_participation_state.eq("played") & ~actual_complete).sum()),
        "played_supported_compatible_outcomes": int(valid_outcomes.sum()),
        "direct_missing_forecasts": int((present & ~direct_finite).sum()),
        "component_missing_forecasts": int((present & ~component_finite).sum()),
        "fallback_rows": {name: int(rows.get(name + "_fallback", pd.Series("", index=rows.index)).fillna("").ne("").sum())
                          for name in ("direct", "rush", "rec")},
        "paired_scored_rows": int(paired.sum()),
        "paired_unique_games": int(rows.loc[paired, "game_id"].nunique()),
        "paired_unique_weeks": int(rows.loc[paired, ["season", "week"]].drop_duplicates().shape[0]),
        "paired_coverage_of_population": float(paired.mean()) if len(rows) else None,
        "paired_coverage_of_supported_played": float(paired.sum()/valid_outcomes.sum()) if valid_outcomes.any() else None,
        "direct_natural_coverage_metrics": metrics(direct_natural, "direct_mean"),
        "component_natural_coverage_metrics": metrics(component_natural, "component_mean"),
        "paired_direct_metrics": metrics(paired, "direct_mean"),
        "paired_component_sum_metrics": metrics(paired, "component_mean"),
        "mean_coherence": {"supported_compatible_forecast_rows": int(structural.sum()),
                           "discrepancies_gt_1e_9": int((structural & discrepancy.gt(1e-9)).sum()),
                           "discrepancies_gt_1_yard": int((structural & discrepancy.gt(1)).sum()),
                           "mean_absolute_discrepancy": float(discrepancy[structural].mean()) if structural.any() else None,
                           "maximum_absolute_discrepancy": float(discrepancy[structural].max()) if structural.any() else None},
        "paired_week_uncertainty": paired_week_deltas(paired_rows),
        "paired_game_uncertainty": paired_week_deltas(paired_rows, cluster="game"),
    }
    return result


def audit_frozen_campaign(directory: Path, *, season: int = 2024) -> dict[str, Any]:
    methods = sorted(path.name.removeprefix(f"{season}-rush_rec_yd-").removesuffix(".parquet")
                     for path in directory.glob(f"{season}-rush_rec_yd-*.parquet"))
    if not methods:
        raise ValueError("no_frozen_combined_rows")
    files = []
    results = []
    for method in methods:
        frames = []
        for target in ("rush_rec_yd", "rush_yd", "rec_yd"):
            path = directory / f"{season}-{target}-{method}.parquet"
            payload = path.read_bytes()
            files.append({"filename": path.name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
            frames.append(pd.read_parquet(io.BytesIO(payload)))
        results.append(audit_method(*frames, method=method, season=season))
    return {"audit_version": AUDIT_VERSION, "campaign": directory.name, "season": season,
            "evidence": "already_exposed_current_vintage_historical_reconstruction_descriptive_only",
            "operation": "read_frozen_rows_no_fit_no_model_selection_no_promotion",
            "point_functional": "conditional means; means add, quantiles not added",
            "bias_definition": "prediction_minus_actual",
            "intervals": "separate paired whole-season-week and whole-game bootstraps; 500 replicates each; seed20261022; Bonferroni12 simultaneous99.5833% within each cluster analysis; finite-bootstrap tails exploratory; no joint inferential claim across cluster analyses",
            "source_component_check": "Each frozen combined actual checked against frozen rushing actual plus receiving actual; byte pins do not independently authenticate provider values.",
            "source_files": files, "methods": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = audit_frozen_campaign(arguments.campaign)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
