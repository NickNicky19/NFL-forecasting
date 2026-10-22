"""One preregistered, finite exposed-2023 public-scheme feature ablation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import warnings

import numpy as np
import pandas as pd

from .evaluation import paired_week_interval, summarize
from .models import fit_predict
from .scheme_context import (aggregate_pbp, load_public_pbp, merge_scheme_asof,
                             opponent_adjusted_history, schedule_context)
from .state import digest, now_utc, source_tree_digest


def _sha(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _dump(path: Path, document: dict | list) -> None:
    path.write_text(json.dumps(document, indent=2, default=str, allow_nan=False) + "\n")


def _validate_population(baseline: pd.DataFrame, current: pd.DataFrame) -> None:
    keys = ["season", "week", "game_id", "player_id"]
    if len(baseline) != len(current):
        raise ValueError("scheme_ablation_changed_baseline_population")
    columns = keys + ["actual", "team", "opponent", "position", "kickoff_utc", "participation_state"]
    paired = baseline[columns].merge(current[columns], on=keys, how="outer", suffixes=("_base", "_new"), validate="one_to_one", indicator=True)
    if not paired._merge.eq("both").all() or not np.allclose(paired.actual_base, paired.actual_new, equal_nan=True):
        raise ValueError("scheme_ablation_changed_outcome_or_identity")
    for field in ("team", "opponent", "position", "kickoff_utc", "participation_state"):
        if not paired[field + "_base"].equals(paired[field + "_new"]):
            raise ValueError("scheme_ablation_changed_metadata:" + field)


def run(root: Path, cache: Path, baseline_root: Path | None = None) -> tuple[dict, Path]:
    root, cache = Path(root), Path(cache)
    baseline_root = root if baseline_root is None else Path(baseline_root)
    # The public receipt survives fresh checkouts that lack ignored run markers.
    if (root / "reports/public-scheme-study/execution.json").exists():
        raise ValueError("scheme_registered_fit_budget_already_attempted")
    registration_path = root / "config/scheme-study.json"
    config = json.loads(registration_path.read_text())
    committed = subprocess.run(["git", "show", "HEAD:config/scheme-study.json"], cwd=root,
                               check=True, capture_output=True).stdout
    if committed != registration_path.read_bytes():
        raise ValueError("scheme_registration_must_be_committed_before_fits")
    if (config["development_season"] != 2023 or config["training_seasons"] != [2019, 2020, 2021, 2022]
            or len(config["targets"]) != 11 or config["budgets"]["new_fits_total"] != 11
            or config["budgets"]["fit_seconds"] > 300 or config["budgets"]["threads"] != 2):
        raise ValueError("scheme_registration_outside_authorized_budget")
    feature_path = cache / "processed/features.parquet"
    checksum = _sha(feature_path)
    if checksum != config["base_features_sha256"]:
        raise ValueError("frozen_base97_feature_hash_changed")
    campaign = root / "runs" / config["registration_id"]
    if (campaign / "fit-budget-consumed.json").exists():
        raise ValueError("scheme_registered_fit_budget_already_attempted")
    output = campaign / now_utc().strftime("%Y%m%dT%H%M%S%f")
    output.mkdir(parents=True, exist_ok=False)
    _dump(output / "registration.json", config)
    # A parquet filter prevents opening 2024/2025/new2026 outcome rows.
    features = pd.read_parquet(feature_path, filters=[("season", "<=", 2023)])
    pbp = load_public_pbp(cache, config["source_pbp_seasons"])
    schedule = schedule_context(cache, config["training_seasons"] + [2023])
    games = opponent_adjusted_history(aggregate_pbp(pbp, schedule))
    augmented = merge_scheme_asof(features, games)
    pd.testing.assert_frame_equal(features[list(features)], augmented[list(features)])
    base_columns = [c for c in features if c.startswith("f_")]
    new_columns = [c for c in augmented if c.startswith("f_scheme_")]
    if len(base_columns) != 97 or len(new_columns) != 47:
        raise ValueError("registered_feature_group_width_changed")
    test = augmented.loc[augmented.season.eq(2023)]
    first = pd.to_datetime(test.kickoff_utc, utc=True).min()
    train = augmented.loc[augmented.season.isin(config["training_seasons"])
                          & (pd.to_datetime(augmented.outcome_available_utc, utc=True) < first)]
    baselines, bindings = {}, []
    for target in config["targets"]:
        path = baseline_root / "runs/lab-v1-2026-10-22" / f"2023-{target}-ridge.parquet"
        baselines[target] = pd.read_parquet(path)
        probe = test[["season", "week", "game_id", "player_id", "team", "opponent", "position", "kickoff_utc", "participation_state"]].copy()
        probe["actual"] = test[target]
        _validate_population(baselines[target], probe)
        bindings.append({"target": target, "filename": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)})
    coverage = {}
    for season in config["training_seasons"] + [2023]:
        group = augmented.loc[augmented.season.eq(season)]
        coverage[str(season)] = {"population_rows": len(group),
            "offense_style_supported_rows": int(group.f_scheme_offense_dropback_rate_mean3.notna().sum()),
            "opponent_defense_supported_rows": int(group.f_scheme_defense_dropback_rate_mean3.notna().sum()),
            "rest_supported_rows": int(group.f_scheme_rest_days.notna().sum()),
            "coach_change_supported_rows": int(group.f_scheme_coach_change_prior.notna().sum()),
            "historical_venue_roof_supported_rows": int(group.f_scheme_venue_roof_closed_mean3.notna().sum()),
            "feature_missing_rows": {column: int(group[column].isna().sum()) for column in new_columns}}
    manifest = {"registration_sha256": digest(config), "base_features_sha256": checksum,
        "source_tree_sha256": source_tree_digest(root), "base_columns": base_columns,
        "new_columns": new_columns, "base_columns_changed": False, "base_population_changed": False,
        "model_source_sha256": _sha(root / "nfl_lab/models.py"),
        "adapter_source_sha256": _sha(root / "nfl_lab/scheme_context.py"),
        "study_source_sha256": _sha(root / "nfl_lab/scheme_study.py"),
        "source_inputs": pbp.attrs["manifest"], "source_profile": games.attrs.get("source_profile"),
        "feature_manifest": augmented.attrs["scheme_context"], "coverage": coverage,
        "baseline_bindings": bindings, "train_population": len(train), "test_population": len(test),
        "read_seasons": sorted(features.season.unique().astype(int).tolist()),
        "execution": {"max_threads": 2, "new_fits_limit": 11, "fit_seconds_limit": 300,
                      "coordinator_reported_worker": "gpt-6.1-sol/xhigh", "basis": "parent task configuration; no external model-certification claim"}}
    _dump(output / "manifest.json", manifest)
    # One durable budget marker prevents a restart from silently adding fits.
    with (campaign / "fit-budget-consumed.json").open("x") as marker:
        json.dump({"output": output.name, "registration_sha256": digest(config),
                   "started_at": now_utc().isoformat(), "new_fits_limit": 11}, marker)
    started = time.monotonic()
    results = []
    for target in config["targets"]:
        if time.monotonic() - started >= config["budgets"]["fit_seconds"]:
            results.append({"target": target, "state": "NOT_RUN_BUDGET_EXHAUSTED"})
            _dump(output / "trials.json", results)
            continue
        target_started = time.monotonic()
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                prediction = fit_predict(train, test, target, "ridge")
            current = test[["season", "week", "game_id", "player_id", "team", "opponent", "position", "kickoff_utc", "participation_state"]].copy()
            current["actual"] = test[target]
            current["target"] = target
            current["method"] = "ridge_plus_public_scheme_v1"
            for column in ("mean", "scale", "family", "p10", "p50", "p90", "p_participation", "fallback"):
                current[column] = prediction[column]
            baseline = baselines[target]
            _validate_population(baseline, current)
            current.to_parquet(output / f"{target}-rows.parquet", index=False)
            scores = {"base": summarize(baseline), "plus_public_scheme": summarize(current)}
            metric = "brier" if target == "anytime_td" else "mae"
            primary = lambda score: score.get("bernoulli", {}).get("brier") if metric == "brier" else score.get("mae")
            base_loss, new_loss = primary(scores["base"]), primary(scores["plus_public_scheme"])
            paired = paired_week_interval(pd.concat([baseline, current], ignore_index=True), "ridge", "ridge_plus_public_scheme_v1", replicates=500)
            results.append({"target": target, "state": "EVALUATED_EXPOSED_DEVELOPMENT_ONLY",
                "primary_metric": metric, "base_loss": base_loss, "scheme_loss": new_loss,
                "relative_gain": (base_loss-new_loss)/base_loss if base_loss and new_loss is not None else None,
                "scores": scores, "paired_week_uncertainty": paired, "fitted_parameters": prediction.attrs,
                "new_rows_sha256": _sha(output / f"{target}-rows.parquet"),
                "elapsed_seconds": time.monotonic()-target_started,
                "warnings": [str(item.message) for item in captured]})
        except Exception as exc:
            results.append({"target": target, "state": "FAILED_RETAINED_NOT_REFIT", "error": repr(exc),
                            "elapsed_seconds": time.monotonic()-target_started})
        _dump(output / "trials.json", results)
    report = {"registration": config, "manifest": manifest, "results": results,
        "elapsed_fit_loop_seconds": time.monotonic()-started,
        "promotion": [], "new_prospective_activation": False,
        "future_confirmation": "not read; no2024/2025/2026 outcome evaluation",
        "interpretation": "already exposed2023 only; one fixed feature-group increment; failures/regressions and missingness preserved; no private scheme claim"}
    _dump(output / "report.json", report)
    return report, output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path)
    arguments = parser.parse_args()
    report, output = run(Path.cwd(), arguments.cache, arguments.baseline_root)
    print(json.dumps({"output": str(output), "elapsed_fit_loop_seconds": report["elapsed_fit_loop_seconds"],
        "results": [{key: row.get(key) for key in ("target", "state", "base_loss", "scheme_loss", "relative_gain")} for row in report["results"]]}, indent=2))
