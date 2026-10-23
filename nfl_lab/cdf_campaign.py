"""Bounded, explicitly invoked research campaign; never a default or scheduler.

The parent records attempts before starting isolated trial processes, monitors
RSS/wall/CPU/output limits, and preserves every failure. Historical forecast
freezes establish calculation order only, never pregame issuance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def event(path, action, **values):
    record = {"at": datetime.now(timezone.utc).isoformat(), "event": action, **values}
    with Path(path).open("a") as handle:
        handle.write(json.dumps(record, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def proc_usage(pid):
    """Linux process-group RSS and CPU; read-only, no credential inspection."""
    rss, cpu = 0, 0.
    ticks = os.sysconf("SC_CLK_TCK")
    pages = os.sysconf("SC_PAGE_SIZE")
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            # The command name can contain spaces or parentheses.
            values = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            if int(values[2]) != pid:  # process-group ID (field 5)
                continue
            cpu += (int(values[11]) + int(values[12])) / ticks
            rss += int(values[21]) * pages
        except (OSError, ValueError, IndexError):
            continue
    return rss, cpu


def directory_bytes(path):
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def check_seal(registry_path):
    registry = json.loads(Path(registry_path).read_text())
    if registry.get("state") != "SEALED_ROOT_AND_REVIEWER":
        raise ValueError("root and separate reviewer seal required")
    seal = registry.get("seal", {})
    if seal.get("reviewer") != "/root/campaign_reviewer" or seal.get("integrator") != "/root":
        raise ValueError("actual separate reviewer/integrator identity missing")
    plan = Path(seal["reviewed_plan_path"])
    if digest(plan) != seal["reviewed_plan_sha256"]:
        raise ValueError("reviewed plan bytes changed")
    reviewed = json.loads(plan.read_text())
    content = {k: v for k, v in registry.items() if k not in ("state", "seal")}
    if content != {k: v for k, v in reviewed.items() if k != "state"}:
        raise ValueError("sealed payload differs from reviewed plan")
    for binding in registry["code_bindings"] + registry["prerequisite_bindings"]:
        if digest(binding["path"]) != binding["sha256"]:
            raise ValueError("sealed code/prerequisite bytes changed: " + binding["path"])
    return registry


def terminate_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)
    except ProcessLookupError:
        pass


def child_trial(registry_path, output, target, panel, season):
    import numpy as np
    import pandas as pd
    from .cdf_engine import (LeafCDFModel, assert_composite_contract,
                             chronological_split, prediction_rows, score_frozen_rows)
    from .cdf_evaluation import bind_saved_control

    start, cpu_start = time.monotonic(), time.process_time()
    registry = check_seal(registry_path)
    category = registry["categories"][target]
    source = registry["source"]
    if digest(source["path"]) != source["sha256"]:
        raise ValueError("feature source bytes changed")
    features = pd.read_parquet(source["path"], filters=[("season", "<=", max(registry["seasons"]))])
    assert_composite_contract(features, category)
    train, test = chronological_split(features, season)
    trial = Path(output)
    log = trial / "events.jsonl"
    event(log, "SOURCE_AND_CLOCK_CHECKED", training_offered=len(train), evaluation_offered=len(test))
    # Audit/import exact saved controls before model fitting; do not refit them.
    for method in ("pooled", "recent"):
        control = registry["controls"][target][str(season)][method]
        if digest(control["path"]) != control["sha256"]:
            raise ValueError("saved control bytes changed")
        bound = bind_saved_control(pd.read_parquet(control["path"]), test, category, method)
        bound.to_parquet(trial / (method + ".parquet"), index=False)
    event(log, "FIT_CONSUMED", target=target, panel=panel, season=season)
    model = LeafCDFModel.fit(train, category, panel)
    manifest = model.save(trial / "model")
    event(log, "MODEL_FROZEN", manifest_sha256=digest(trial / "model/manifest.json"), artifact_sha256=manifest["sha256"])
    # Reconstructible query assignments, without any label-based selection.
    if model.forest is not None:
        query_leaves = model.forest.apply(model.design.transform(test)).astype(np.int32)
    else:
        query_leaves = np.empty((len(test), 0), dtype=np.int32)
    np.savez_compressed(trial / "query-leaves.npz", leaf_ids=query_leaves)
    methods = [(False, "candidate")]
    if panel == "base":
        methods.append((True, "role_prior"))
    for prior_only, name in methods:
        frozen = prediction_rows(model, test, prior_only=prior_only, score=False)
        freeze = trial / (name + "-frozen.parquet")
        frozen.to_parquet(freeze, index=False)
        event(log, "FORECAST_FROZEN", method=name, rows=len(frozen), sha256=digest(freeze),
              timing="calculated now after historical games; no prospective or source-as-of claim")
    # All forecast bytes and model state precede this one scoring phase.
    event(log, "SCORE_PASS_CONSUMED")
    for prior_only, name in methods:
        freeze = trial / (name + "-frozen.parquet")
        scored = score_frozen_rows(model, test, pd.read_parquet(freeze), prior_only=prior_only)
        scored.to_parquet(trial / (name + "-scored.parquet"), index=False)
    bindings = {str(p.relative_to(trial)): digest(p) for p in trial.rglob("*") if p.is_file() and p.name != "events.jsonl"}
    write_json(trial / "result-manifest.json", {"target": target, "panel": panel, "season": season,
        "state": "COMPLETED", "fit_attempts": 1, "score_phases": 1, "bindings": bindings,
        "wall_seconds": time.monotonic()-start, "cpu_seconds": time.process_time()-cpu_start,
        "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024})
    event(log, "COMPLETED", result_manifest_sha256=digest(trial / "result-manifest.json"))


def aggregate(registry, output, statuses):
    import pandas as pd
    from .cdf_evaluation import report_tables

    root = Path(output)
    summaries = {}
    marginal_points = {}
    for target, category in registry["categories"].items():
        if category["state"] != "READY":
            summaries[target] = {"state": category["state"], "fit_attempts": 0, "reason": category.get("blocking_reason", category.get("notes", []))}
            continue
        parts = []
        controls = {}
        for status in statuses:
            if status["target"] != target or status["state"] != "COMPLETED":
                continue
            directory = root / status["trial"]
            for filename in ("candidate-scored.parquet", "role_prior-scored.parquet", "pooled.parquet", "recent.parquet"):
                path = directory / filename
                if path.is_file():
                    data = pd.read_parquet(path)
                    if filename in ("pooled.parquet", "recent.parquet"):
                        key = (status["season"], filename)
                        if key in controls:
                            if not controls[key].equals(data):
                                raise ValueError("control copies differ across fixed panels")
                            continue
                        controls[key] = data
                    parts.append(data)
        if not parts:
            summaries[target] = {"state": "NO_COMPLETED_TRIALS", "attempts": [x for x in statuses if x["target"] == target]}
            continue
        rows = pd.concat(parts, ignore_index=True)
        if rows.duplicated(["season", "week", "game_id", "player_id", "method"]).any():
            raise ValueError("duplicate aggregate player-game-method rows")
        destination = root / "results" / target
        destination.mkdir(parents=True, exist_ok=False)
        rows.to_parquet(destination / "rows.parquet", index=False)
        marginal_points[target] = rows.loc[rows.method.isin(["leaf_cdf_base", "leaf_cdf_context"]),
            ["season", "week", "game_id", "player_id", "method", "mean", "median"]].copy()
        report = report_tables(rows, category)
        report["attempt_statuses"] = [x for x in statuses if x["target"] == target]
        report["incomplete_cell_policy"] = "Every fixed cell retained; paired results require matching saved control years. Failed cells do not justify selecting surviving panels."
        write_json(destination / "report.json", report)
        summaries[target] = {"state": "EXPOSED_EXPLORATORY_UNQUALIFIED", "report_sha256": digest(destination / "report.json"),
                             "rows_sha256": digest(destination / "rows.parquet"), "summary": report["summary"], "paired": report["paired"]}
    coherence = {"interpretation": "Technical audit of aligned marginal means, not a joint-law validation; violations retained without post-hoc repair.", "checks": []}
    join_keys = ["season", "week", "game_id", "player_id", "method"]
    for smaller, larger in [("pass_cmp", "pass_att"), ("pass_td", "pass_cmp"), ("pass_int", "pass_att")]:
        if smaller not in marginal_points or larger not in marginal_points:
            coherence["checks"].append({"smaller": smaller, "larger": larger, "state": "MISSING_FORECAST_CATEGORY"})
            continue
        matched = marginal_points[smaller].merge(marginal_points[larger], on=join_keys, validate="one_to_one", suffixes=("_smaller", "_larger"))
        valid = matched.mean_smaller.notna() & matched.mean_larger.notna()
        violations = matched.loc[valid & (matched.mean_smaller > matched.mean_larger)]
        violations.to_parquet(root / f"coherence-{smaller}-gt-{larger}.parquet", index=False)
        coherence["checks"].append({"smaller": smaller, "larger": larger, "aligned_finite_means": int(valid.sum()),
            "violations": len(violations), "maximum_excess": float((violations.mean_smaller-violations.mean_larger).max()) if len(violations) else 0.})
    if all(t in marginal_points for t in ["rush_yd", "rec_yd", "rush_rec_yd"]):
        combined = marginal_points["rush_rec_yd"].rename(columns={"mean": "direct_mean", "median": "direct_median"})
        for target in ("rush_yd", "rec_yd"):
            combined = combined.merge(marginal_points[target].rename(columns={"mean": target+"_mean", "median": target+"_median"}), on=join_keys, validate="one_to_one")
        gap = combined.direct_mean-combined.rush_yd_mean-combined.rec_yd_mean
        coherence["combined_mean_accounting"] = {"aligned_rows": len(combined), "finite_rows": int(gap.notna().sum()),
            "mean_absolute_gap": float(gap.abs().mean()), "maximum_absolute_gap": float(gap.abs().max()),
            "semantics": "Expected compatible components add, but independently fitted predictions need not. Direct combined target scored separately; no inherited gain or independent-component law claim. Medians/quantiles not forced additive."}
        combined.assign(direct_minus_component_mean_sum=gap).to_parquet(root / "combined-mean-accounting.parquet", index=False)
    write_json(root / "coherence-audit.json", coherence)
    write_json(root / "campaign-report.json", {"registration_id": registry["registration_id"],
        "evidence": "exposed current-vintage historical reconstruction, all primary/secondary comparisons retained",
        "website_comparators": "Unavailable for historical2022-24; no historical Sleeper or website values invented",
        "categories": summaries, "attempts": statuses, "coherence": coherence, "new_qualified_replacements": [],
        "confirmation": "none; untouched later observations required under candidate-specific rules"})


def run(registry_path, output):
    registry_path, output = Path(registry_path).resolve(), Path(output).resolve()
    registry = json.loads(registry_path.read_text())
    if registry["state"] != "SEALED_ROOT_AND_REVIEWER":
        raise ValueError("root and separate reviewer seal required")
    output.mkdir(parents=True, exist_ok=False)
    registry = check_seal(registry_path)
    log = output / "events.jsonl"
    write_json(output / "registry.json", registry)
    budget = registry["budgets"]
    start = time.monotonic()
    parent_cpu_start = time.process_time()
    cpu_used = 0.
    statuses = []
    attempts = 0
    event(log, "CAMPAIGN_STARTED", registry_sha256=digest(registry_path), budgets=budget)
    for target, category in registry["categories"].items():
        for panel in ("base", "context"):
            for year in registry["seasons"]:
                relative = f"trials/{target}/{panel}/{year}"
                status = {"target": target, "panel": panel, "season": year, "trial": relative}
                remaining_wall = budget["campaign_wall_seconds"]-(time.monotonic()-start)
                if category["state"] != "READY":
                    status["state"] = "BLOCKED_CATEGORY_CONTRACT"
                elif remaining_wall <= budget["reporting_wall_reserve_seconds"] or cpu_used + time.process_time()-parent_cpu_start >= budget["campaign_cpu_seconds"]:
                    status["state"] = "SKIPPED_CAMPAIGN_BUDGET"
                elif attempts >= budget["maximum_candidate_fit_attempts"]:
                    status["state"] = "SKIPPED_FIT_BUDGET"
                elif directory_bytes(output) >= budget["private_output_bytes"]:
                    status["state"] = "SKIPPED_OUTPUT_BUDGET"
                if "state" in status:
                    statuses.append(status)
                    event(log, status["state"], **{k: v for k, v in status.items() if k != "state"})
                    continue
                attempts += 1
                trial = output / relative
                trial.mkdir(parents=True, exist_ok=False)
                event(log, "ATTEMPT_STARTED", attempt=attempts, **status)
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2")
                before_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
                trial_start = time.monotonic()
                max_rss = 0
                last_size_check = 0.
                reason = None
                with (trial / "stdout.log").open("w") as stdout, (trial / "stderr.log").open("w") as stderr:
                    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
                    process = subprocess.Popen([sys.executable, "-m", "nfl_lab.cdf_campaign", "trial", str(registry_path), str(trial), target, panel, str(year)], env=env, cwd=Path(__file__).resolve().parent.parent, stdout=stdout, stderr=stderr, start_new_session=True)
                    while process.poll() is None:
                        rss, cpu = proc_usage(process.pid)
                        max_rss = max(max_rss, rss)
                        elapsed = time.monotonic()-trial_start
                        total_elapsed = time.monotonic()-start
                        if rss > budget["memory_bytes"]:
                            reason = "RSS_LIMIT"
                        elif elapsed > budget["per_trial_wall_seconds"]:
                            reason = "TRIAL_WALL_LIMIT"
                        elif cpu > budget["per_trial_cpu_seconds"]:
                            reason = "TRIAL_CPU_LIMIT"
                        elif total_elapsed >= budget["campaign_wall_seconds"]-budget["reporting_wall_reserve_seconds"]:
                            reason = "CAMPAIGN_WALL_RESERVE"
                        elif cpu_used+cpu+time.process_time()-parent_cpu_start >= budget["campaign_cpu_seconds"]:
                            reason = "CAMPAIGN_CPU_LIMIT"
                        if elapsed-last_size_check >= 1:
                            last_size_check = elapsed
                            if directory_bytes(output) > budget["private_output_bytes"]:
                                reason = "OUTPUT_LIMIT"
                        if reason:
                            terminate_group(process)
                            break
                        time.sleep(.1)
                after_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
                trial_cpu = after_cpu.ru_utime+after_cpu.ru_stime-before_cpu.ru_utime-before_cpu.ru_stime
                cpu_used += trial_cpu
                complete = process.returncode == 0 and (trial / "result-manifest.json").is_file()
                status.update(state="COMPLETED" if complete else "FAILED_CONSUMED", reason=reason,
                    returncode=process.returncode, wall_seconds=time.monotonic()-trial_start,
                    cpu_seconds=trial_cpu, sampled_peak_group_rss_bytes=max_rss)
                statuses.append(status)
                event(log, status["state"], **{k: v for k, v in status.items() if k != "state"})
                write_json(output / "attempts.json", statuses)
    event(log, "AGGREGATION_STARTED", fit_attempts=attempts, child_cpu_seconds=cpu_used)
    remaining_wall = max(0., budget["campaign_wall_seconds"]-(time.monotonic()-start))
    remaining_cpu = max(0., budget["campaign_cpu_seconds"]-cpu_used-(time.process_time()-parent_cpu_start))
    aggregation_reason = None
    aggregation_cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    aggregation_peak_rss = 0
    with (output / "aggregation.stdout.log").open("w") as stdout, (output / "aggregation.stderr.log").open("w") as stderr:
        process = subprocess.Popen([sys.executable, "-m", "nfl_lab.cdf_campaign", "aggregate", str(registry_path), str(output)],
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2", PYTHONPATH=str(Path(__file__).resolve().parent.parent)), cwd=Path(__file__).resolve().parent.parent,
            stdout=stdout, stderr=stderr, start_new_session=True)
        aggregation_start = time.monotonic()
        while process.poll() is None:
            rss, cpu = proc_usage(process.pid)
            aggregation_peak_rss = max(aggregation_peak_rss, rss)
            if time.monotonic()-aggregation_start >= remaining_wall:
                aggregation_reason = "CAMPAIGN_WALL_LIMIT"
            elif cpu >= remaining_cpu:
                aggregation_reason = "CAMPAIGN_CPU_LIMIT"
            elif rss > budget["memory_bytes"]:
                aggregation_reason = "AGGREGATION_RSS_LIMIT"
            elif directory_bytes(output) > budget["private_output_bytes"]:
                aggregation_reason = "OUTPUT_LIMIT"
            if aggregation_reason:
                terminate_group(process)
                break
            time.sleep(.1)
    if process.returncode != 0:
        event(log, "AGGREGATION_FAILED_CONSUMED", reason=aggregation_reason, returncode=process.returncode,
              retained_attempts=attempts, policy="preserve all trial rows; no fits or predictions repeated")
        return
    aggregation_cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    aggregation_cpu = (aggregation_cpu_after.ru_utime+aggregation_cpu_after.ru_stime-
                       aggregation_cpu_before.ru_utime-aggregation_cpu_before.ru_stime)
    event(log, "CAMPAIGN_FINISHED", fit_attempts=attempts, completed=sum(x["state"] == "COMPLETED" for x in statuses),
          wall_seconds=time.monotonic()-start, trial_child_cpu_seconds=cpu_used,
          parent_cpu_seconds=time.process_time()-parent_cpu_start, aggregation_cpu_seconds=aggregation_cpu,
          aggregation_sampled_peak_rss_bytes=aggregation_peak_rss, output_bytes=directory_bytes(output),
          report_sha256=digest(output / "campaign-report.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["run", "trial", "aggregate"])
    parser.add_argument("registry")
    parser.add_argument("output")
    parser.add_argument("target", nargs="?")
    parser.add_argument("panel", nargs="?")
    parser.add_argument("season", nargs="?", type=int)
    args = parser.parse_args()
    if args.mode == "run":
        run(args.registry, args.output)
    elif args.mode == "aggregate":
        registry = check_seal(args.registry)
        statuses = json.loads((Path(args.output)/"attempts.json").read_text())
        aggregate(registry, args.output, statuses)
    else:
        child_trial(args.registry, args.output, args.target, args.panel, args.season)


if __name__ == "__main__":
    main()
