"""Finite fictional shared-engine resource profile; never loads NFL data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np
import pandas as pd

from nfl_lab.cdf_engine import LeafCDFModel, prediction_rows, score_frozen_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    rng = np.random.default_rng(1701)
    ntrain, ntest, nfeatures = 40000, 10000, 100
    names = [f"f_player_fictional_lag{i}" for i in range(nfeatures)]
    train = pd.DataFrame(rng.normal(size=(ntrain, nfeatures)), columns=names)
    test = pd.DataFrame(rng.normal(size=(ntest, nfeatures)), columns=names)
    for frame, year in [(train, 2020), (test, 2022)]:
        n = len(frame)
        frame["season"], frame["week"] = year, np.arange(n) % 18 + 1
        frame["game_id"] = [f"fictional-{year}-{i}" for i in range(n)]
        frame["player_id"] = [f"fictional-player-{i % 1000}" for i in range(n)]
        frame["team"], frame["opponent"], frame["position"] = "FictionalA", "FictionalB", "QB"
        frame["kickoff_utc"] = pd.Timestamp(f"{year}-09-01", tz="UTC")
        frame["cutoff_utc"] = frame.kickoff_utc - pd.Timedelta(hours=2)
        frame["participation_state"] = "played"
        frame["pass_yd"] = np.rint(80 + 25*frame[names[0]] + rng.normal(0, 150, n))
        frame["f_player_games_prior"] = 5.
    category = {"target": "pass_yd", "state": "READY", "support": "signed_integer",
                "modeled_roles": ["QB"], "primary_roles": ["QB"],
                "outcome_contract": {"definition": "FICTIONAL profile labels"},
                "panels": {"base": names, "context": names}}
    phases = {}
    began = time.monotonic()
    model = LeafCDFModel.fit(train, category, "base")
    phases["fit_seconds"] = time.monotonic()-began
    began = time.monotonic()
    model.save(output/"model")
    phases["artifact_seconds"] = time.monotonic()-began
    began = time.monotonic()
    forecast = prediction_rows(model, test)
    forecast.to_parquet(output/"fictional-forecast.parquet", index=False)
    phases["forecast_seconds"] = time.monotonic()-began
    began = time.monotonic()
    scored = score_frozen_rows(model, test, forecast)
    scored.to_parquet(output/"fictional-scored.parquet", index=False)
    phases["score_seconds"] = time.monotonic()-began
    report = {"evidence": "fictional engineering profile; no football data loaded, forecasts or scientific scores",
              "seed": 1701, "train_rows": ntrain, "test_rows": ntest, "numeric_features": nfeatures,
              "wall_seconds": time.monotonic()-start, "cpu_seconds": time.process_time()-cpu,
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
              "artifact_bytes": sum(path.stat().st_size for path in output.rglob("*") if path.is_file()),
              "phases": phases, "support_size": model.audit["empirical_support_size"],
              "leaf_histogram_nnz": model.audit["leaf_histogram_nnz"]}
    (output/"profile.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
