"""At most four synthetic estimator fits; no NFL data or old model inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import time

import joblib
import numpy as np
import pandas as pd

from nfl_lab.role_boosting import RoleCountBoostingModel, prediction_rows
from nfl_lab.website_cdf import environment_receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    rng, ntrain, nquery = np.random.default_rng(1702), 40000, 4000
    names = [f"f_player_fictional_lag{i}" for i in range(38)]
    train = pd.DataFrame(rng.normal(size=(ntrain, len(names))), columns=names)
    train.loc[np.arange(ntrain) % 13 == 0, names[2]] = np.nan
    train["position"] = np.repeat(["QB", "RB", "FB", "WR", "TE"], ntrain // 5)
    train["season"], train["week"] = 2020, np.arange(ntrain) % 18 + 1
    train["game_id"] = [f"fictional-game-{i}" for i in range(ntrain)]
    train["player_id"] = [f"fictional-player-{i % 1000}" for i in range(ntrain)]
    train["team"], train["opponent"] = "FictionalA", "FictionalB"
    train["kickoff_utc"] = pd.Timestamp("2020-09-01", tz="UTC")
    train["cutoff_utc"] = train.kickoff_utc - pd.Timedelta(hours=2)
    train["outcome_available_utc"] = train.kickoff_utc + pd.Timedelta(days=7)
    train["feature_max_source_available_utc"] = train.kickoff_utc - pd.Timedelta(days=1)
    train["participation_state"], train["f_player_games_prior"] = "played", 5.
    active = train.position.isin(["RB", "WR"])
    train["fictional_count"] = np.where(active, rng.poisson(np.exp(.5 * train[names[0]] + 1)), 0)
    train["fictional_event"] = np.where(train.position.eq("RB"), rng.binomial(1, .2, ntrain), 0)
    query = train.iloc[np.arange(0, ntrain, ntrain // nquery)].drop(columns=["fictional_count", "fictional_event"]).reset_index(drop=True)
    query["season"], query["participation_state"] = 2022, "unknown"
    calls, profiles = [], []
    def consume(receipt):
        if len(calls) >= 4:
            raise RuntimeError("fictional profile four-fit budget exhausted")
        calls.append(receipt)
    for target, support, variant, roles in [
        ("fictional_count", "count", "A", ["QB", "RB", "FB", "WR", "TE"]),
        ("fictional_count", "count", "B", ["QB", "RB", "FB", "WR", "TE"]),
        ("fictional_event", "bernoulli", "B", ["RB", "WR", "TE"])]:
        category = dict(target=target, state="READY", support=support, modeled_roles=roles,
            primary_roles=["RB"], panels={"base": names, "context": names})
        began, cpu_began = time.monotonic(), time.process_time()
        model = RoleCountBoostingModel.fit(train, category, variant, before_fit=consume)
        fit_wall, fit_cpu = time.monotonic() - began, time.process_time() - cpu_began
        directory = args.output / f"{target}-{variant}"
        model.save(directory)
        frozen = prediction_rows(model, query)
        frozen.to_parquet(directory / "candidate-frozen.parquet", index=False)
        loaded = joblib.load(directory / "model.joblib")
        np.testing.assert_array_equal(loaded.predict(query)[0], frozen.point.to_numpy())
        profiles.append({"target": target, "support": support, "variant": variant,
            "fit_wall_seconds": fit_wall, "fit_cpu_seconds": fit_cpu,
            "fit_attempts": model.audit["fit_attempts"], "subfits": model.audit["subfits"]})
    report = {"evidence": "fictional engineering only; no NFL inputs, old-model inference or football accuracy",
        "seed": 1702, "train_rows": ntrain, "query_rows": len(query), "numeric_features": len(names),
        "maximum_fictional_estimator_fits": 4, "actual_fictional_estimator_fits": len(calls),
        "wall_seconds": time.monotonic() - start, "cpu_seconds": time.process_time() - cpu,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "output_bytes_before_receipt": sum(p.stat().st_size for p in args.output.rglob("*") if p.is_file()),
        "profiles": profiles, "environment": environment_receipt()}
    (args.output / "profile.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"profiles", "environment"}}, allow_nan=False))


if __name__ == "__main__":
    main()
