"""Finite deterministic fictional profile of the two fixed estimator APIs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np
import pandas as pd

from nfl_lab.median_boosting import MedianBoostingModel, prediction_rows, score_frozen_rows
from nfl_lab.website_cdf import environment_receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    rng, ntrain, ntest, nfeatures = np.random.default_rng(1702), 40000, 10000, 100
    names = [f"f_player_fictional_lag{i}" for i in range(nfeatures)]
    frames = []
    for n, year in [(ntrain, 2020), (ntest, 2022)]:
        frame = pd.DataFrame(rng.normal(size=(n, nfeatures)), columns=names)
        # Deterministic missing-feature pattern exercises training imputation.
        frame.loc[np.arange(n) % 13 == 0, names[3]] = np.nan
        frame["season"], frame["week"] = year, np.arange(n) % 18 + 1
        frame["game_id"] = [f"fictional-{year}-{i}" for i in range(n)]
        frame["player_id"] = [f"fictional-player-{i % 1000}" for i in range(n)]
        frame["team"], frame["opponent"], frame["position"] = "FictionalA", "FictionalB", "QB"
        frame["kickoff_utc"] = pd.Timestamp(f"{year}-09-01", tz="UTC")
        frame["cutoff_utc"] = frame.kickoff_utc - pd.Timedelta(hours=2)
        frame["outcome_available_utc"] = frame.kickoff_utc + pd.Timedelta(days=7)
        frame["feature_max_source_available_utc"] = frame.kickoff_utc - pd.Timedelta(days=1)
        frame["participation_state"], frame["f_player_games_prior"] = "played", 5.
        frame["fictional_yards"] = np.rint(80 + 25 * frame[names[0]] + rng.normal(0, 150, n))
        frame["fictional_event"] = rng.binomial(1, .2, n)
        frames.append(frame)
    train, query = frames
    profiles = []
    for target, support in [("fictional_yards", "signed_integer"), ("fictional_event", "bernoulli")]:
        category = {"target": target, "state": "READY", "support": support,
            "modeled_roles": ["QB"], "primary_roles": ["QB"], "panels": {"base": names, "context": names}}
        began, cpu_began = time.monotonic(), time.process_time()
        model = MedianBoostingModel.fit(train, category, "base")
        fit = {"wall_seconds": time.monotonic() - began, "cpu_seconds": time.process_time() - cpu_began}
        began = time.monotonic()
        model.save(args.output / target)
        frozen = prediction_rows(model, query)
        frozen.to_parquet(args.output / (target + "-frozen.parquet"), index=False)
        scored = score_frozen_rows(query, frozen, category)
        scored.to_parquet(args.output / (target + "-scored.parquet"), index=False)
        profiles.append({"support": support, "fit": fit, "artifact_prediction_score_wall_seconds": time.monotonic() - began,
            "fitted_iterations": model.audit["fitted_iterations"], "numeric_input_features": len(model.design.names),
            "transformed_features": 2 * len(model.design.names) + len(model.design.roles)})
    report = {"evidence": "fictional engineering only; no NFL data, forecasts or football scores",
        "seed": 1702, "train_rows": ntrain, "test_rows": ntest, "numeric_features": nfeatures,
        "wall_seconds": time.monotonic() - start, "cpu_seconds": time.process_time() - cpu,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "output_bytes_before_receipt": sum(p.stat().st_size for p in args.output.rglob("*") if p.is_file()),
        "profiles": profiles, "environment": environment_receipt()}
    (args.output / "profile.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
