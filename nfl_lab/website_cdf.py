"""Opt-in, bounded original-website CDF reconstruction; no service integration.

All prediction trials precede the sole scoring phase. Create-only output and
consumed-attempt records prevent a failed process from silently restarting.
This module never appends the integrator's canonical execution ledger.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from .cdf_campaign import digest, directory_bytes, event, proc_usage, terminate_group, write_json

VERSION = "website-direct-leaf-cdf-v1-20261023"
TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
           "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td")
LIMITS = dict(maximum_candidate_fit_attempts=22, maximum_threads=2,
              campaign_wall_seconds=1200, campaign_cpu_seconds=1800,
              per_trial_wall_seconds=60, per_trial_cpu_seconds=90,
              memory_bytes=2 * 1024 ** 3, private_output_bytes=512 * 1024 ** 2,
              reporting_wall_reserve_seconds=120, bootstrap_replicates=0, score_passes=1)
ORIGINAL_HASHES = {"original_baseline": "de8531889cbbc39591f390824c0d61e166a93a8a075331eb523ee2bbaa24db80",
                   "original_board": "1d29f93450ad682c0d647fa46321ea4920ac3bc8568331394c6423549ea7939b"}
ENSEMBLE_DESIGN = {"weight_website": .5, "weight_cdf": .5,
    "numeric_primary": "0.5 * literal website point + 0.5 * same-law CDF median",
    "numeric_secondary": "0.5 * literal website point + 0.5 * same-law CDF mean",
    "numeric_semantics": "point heuristic; no mean/median/distribution/CRPS claim",
    "binary": "0.5 * genuine website event probability + 0.5 * same-law CDF probability; Bernoulli Brier/logloss",
    "missing_website": "abstain and retain original offer", "tuning": "none; single fixed weight; no added fits",
    "primary_contrast_slots": 48, "pure_supported_slots": 22, "ensemble_supported_slots": 22, "blocked_ppr_slots": 4}


def check_seal(path):
    registry = json.loads(Path(path).read_text())
    if registry.get("state") != "SEALED_ROOT_AND_REVIEWER":
        raise ValueError("root and separate reviewer seal required")
    seal = registry.get("seal", {})
    if seal.get("integrator") != "/root" or not str(seal.get("reviewer", "")).startswith("/root/"):
        raise ValueError("distinct actual integrator/reviewer identity required")
    if seal.get("decision") != "PASS_BOUNDED_EXPOSED_RESEARCH_ONLY":
        raise ValueError("explicit bounded website study preclear required")
    plan = Path(seal["reviewed_plan_path"])
    if digest(plan) != seal["reviewed_plan_sha256"]:
        raise ValueError("reviewed plan bytes changed")
    payload = {k: v for k, v in registry.items() if k not in ("state", "seal")}
    reviewed = {k: v for k, v in json.loads(plan.read_text()).items() if k != "state"}
    if payload != reviewed:
        raise ValueError("sealed payload differs from reviewed plan")
    if registry.get("registration_id") != VERSION or set(registry["categories"]) != set(TARGETS):
        raise ValueError("wrong fixed website study/target slots")
    if registry["budgets"] != LIMITS:
        raise ValueError("fixed resource/fit/scoring budget changed")
    if registry.get("ensemble_design") != ENSEMBLE_DESIGN:
        raise ValueError("fixed equalweight ensemble predeclaration required")
    if not Path(registry["output_directory"]).is_absolute():
        raise ValueError("absolute create-only output directory must be sealed")
    required_inputs = {"training_features", "query_features", "opportunities", "outcomes"}
    if set(registry["inputs"]) != required_inputs:
        raise ValueError("exact separate training/query/opportunity/outcome inputs required")
    bindings = [registry["prior_registry"], *registry["inputs"].values(),
                *registry["source_bindings"].values(), *registry["code_bindings"], *registry["prerequisite_bindings"]]
    for binding in bindings:
        if digest(binding["path"]) != binding["sha256"]:
            raise ValueError("sealed bytes changed: " + binding["path"])
    bound_code = {str(Path(x["path"]).resolve()) for x in registry["code_bindings"]}
    required_code = {str(Path(__file__).with_name(name).resolve()) for name in
                     ["website_cdf.py", "website_cdf_evaluation.py", "cdf_engine.py", "cdf_campaign.py", "cdf_evaluation.py"]}
    if not required_code <= bound_code:
        raise ValueError("all runner/imported code must be sealed")
    for name, expected in ORIGINAL_HASHES.items():
        if registry["source_bindings"].get(name, {}).get("sha256") != expected:
            raise ValueError("original website comparator source changed: " + name)
    prior = json.loads(Path(registry["prior_registry"]["path"]).read_text())
    if registry["categories"] != prior["categories"]:
        raise ValueError("prior target/role/panel contracts changed")
    if registry["inputs"]["training_features"]["sha256"] != prior["source"]["sha256"]:
        raise ValueError("prior retained training features changed")
    expected_engine = next(x["sha256"] for x in prior["code_bindings"] if Path(x["path"]).name == "cdf_engine.py")
    if digest(Path(__file__).with_name("cdf_engine.py")) != expected_engine:
        raise ValueError("registered empirical CDF engine changed")
    if registry["categories"]["fantasy_ppr"]["state"] == "READY":
        raise ValueError("PPR remains blocked")
    if sum(c["state"] == "READY" for c in registry["categories"].values()) != 11:
        raise ValueError("exactly eleven supported targets required")
    return registry


def training_split(frame, query):
    """Explicit 2019–25 label gate before the earliest original W6 cutoff."""
    import pandas as pd
    from .cdf_engine import assert_clock_contract
    from .website_cdf_evaluation import normalize_keys
    frame, query = normalize_keys(frame), normalize_keys(query)
    assert_clock_contract(frame)
    assert_clock_contract(query)
    if query.empty or not query.season.eq(2026).all() or not query.week.eq(6).all():
        raise ValueError("only original 2026 Week 6 query permitted")
    cutoff = pd.to_datetime(query.cutoff_utc, utc=True).min()
    kickoff = pd.to_datetime(frame.kickoff_utc, utc=True)
    available = pd.to_datetime(frame.outcome_available_utc, utc=True, errors="coerce")
    mask = frame.season.between(2019, 2025) & (kickoff < cutoff) & available.notna() & (available < cutoff)
    train = frame.loc[mask].sort_values(["kickoff_utc", "game_id", "player_id"], kind="stable").copy()
    return train, {"earliest_original_week6_cutoff": cutoff.isoformat(), "source_rows": len(frame),
        "eligible_training_rows": len(train), "excluded_rows": int((~mask).sum()),
        "training_seasons": sorted(int(x) for x in train.season.unique()),
        "availability_policy": "supplied historical kickoff+7d assumption; publication/correction vintage unverified"}


def prediction_trial(registry_path, directory, target, panel):
    import numpy as np
    import pandas as pd
    from .cdf_engine import LeafCDFModel, assert_composite_contract, prediction_rows
    from .website_cdf_evaluation import ensemble_frozen_rows, target_query

    registry = check_seal(registry_path)
    directory = Path(directory).resolve()
    expected_directory = Path(registry["output_directory"]).resolve() / "trials" / target / panel
    if directory != expected_directory:
        raise ValueError("trial differs from sealed create-only campaign directory")
    if not (directory / "attempt-consumed.json").is_file():
        raise ValueError("parent must consume an attempt before child starts")
    if (directory / "events.jsonl").exists():
        raise FileExistsError("prediction trial already started; no retry")
    log = directory / "events.jsonl"
    event(log, "PREDICTION_TRIAL_STARTED", target=target, panel=panel)
    category = registry["categories"][target]
    paths = registry["inputs"]
    # Outcomes input is hash-bound by the seal, but its values are not loaded.
    features = pd.read_parquet(paths["training_features"]["path"], filters=[("season", ">=", 2019), ("season", "<=", 2025)])
    query_all = pd.read_parquet(paths["query_features"]["path"])
    offers_all = pd.read_parquet(paths["opportunities"]["path"])
    query, offers = target_query(query_all, offers_all, target)
    train, audit = training_split(features, query_all)
    assert_composite_contract(train, category)
    # Persist full query/preprocessing provenance without reading target outcomes.
    query.to_parquet(directory / "query.parquet", index=False)
    offers.to_parquet(directory / "literal-offers.parquet", index=False)
    write_json(directory / "training-gate.json", audit)
    event(log, "FIT_CONSUMED", target=target, panel=panel, **audit)
    model = LeafCDFModel.fit(train, category, panel)
    manifest = model.save(directory / "model")
    event(log, "MODEL_FROZEN", artifact_sha256=manifest["sha256"], manifest_sha256=digest(directory / "model/manifest.json"))
    leaves = model.forest.apply(model.design.transform(query)).astype(np.int32) if model.forest is not None else np.empty((len(query), 0), dtype=np.int32)
    np.savez_compressed(directory / "query-leaves.npz", leaf_ids=leaves)
    for prior_only, name in [(False, "candidate"), (True, "role-prior")]:
        frozen = prediction_rows(model, query, prior_only=prior_only, score=False)
        frozen["evidence"] = "new_postgame_original_website_week6_reconstruction"
        destination = directory / (name + "-frozen.parquet")
        frozen.to_parquet(destination, index=False)
        event(log, "FORECAST_FROZEN", method=name, rows=len(frozen), sha256=digest(destination),
              interpretation="calculated after exposed games; freeze establishes calculation order only")
    ensemble = ensemble_frozen_rows(pd.read_parquet(directory / "candidate-frozen.parquet"), offers, category)
    ensemble.to_parquet(directory / "ensemble-frozen.parquet", index=False)
    event(log, "FORECAST_FROZEN", method="website_equalweight", rows=len(ensemble), sha256=digest(directory / "ensemble-frozen.parquet"),
          numeric_semantics="point heuristic, no numerical distribution claim", prefit_design=ENSEMBLE_DESIGN)
    bindings = {str(p.relative_to(directory)): digest(p) for p in directory.rglob("*")
                if p.is_file() and p.name not in {"events.jsonl", "stdout.log", "stderr.log"}}
    write_json(directory / "prediction-manifest.json", {"target": target, "panel": panel, "bindings": bindings, "fit_attempts": 1, "score_passes": 0})
    event(log, "PREDICTION_TRIAL_COMPLETED", manifest_sha256=digest(directory / "prediction-manifest.json"))


def score_report(registry_path, output):
    import joblib
    import numpy as np
    import pandas as pd
    from .cdf_engine import score_frozen_rows
    from .cdf_evaluation import summarize
    from .website_cdf_evaluation import (bind_outcomes, literal_controls, normalize_keys,
                                          report_ensemble, report_target, score_ensemble)

    registry, output = check_seal(registry_path), Path(output)
    if output.resolve() != Path(registry["output_directory"]).resolve():
        raise ValueError("score output differs from sealed create-only campaign directory")
    freeze_path = output / "forecast-freeze.json"
    if not freeze_path.is_file() or (output / "score-consumed.json").exists():
        raise ValueError("global forecast freeze required; one score pass only")
    freeze = json.loads(freeze_path.read_text())
    if digest(output / "attempts.json") != freeze["attempts_sha256"]:
        raise ValueError("attempt status bytes changed after global forecast freeze")
    for relative, expected in freeze["bindings"].items():
        if digest(output / relative) != expected:
            raise ValueError("frozen prediction/model bytes changed: " + relative)
    with (output / "score-consumed.json").open("x") as handle:
        json.dump({"at": datetime.now(timezone.utc).isoformat(), "forecast_freeze_sha256": digest(freeze_path), "score_passes": 1}, handle, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    event(output / "events.jsonl", "SCORE_PASS_CONSUMED", forecast_freeze_sha256=digest(freeze_path))
    outcomes = normalize_keys(pd.read_parquet(registry["inputs"]["outcomes"]["path"]))
    opportunities = normalize_keys(pd.read_parquet(registry["inputs"]["opportunities"]["path"]))
    identity = ["season", "week", "game_id", "player_id", "target"]
    coverage = opportunities[identity].merge(outcomes[identity], on=identity, how="outer", indicator=True, validate="one_to_one")
    if not coverage._merge.eq("both").all():
        raise ValueError("all original outcomes, including blocked/unresolved, must be retained")
    statuses = json.loads((output / "attempts.json").read_text())
    slots = []
    for status in statuses:
        slot = dict(status)
        if status["state"] != "PREDICTION_FROZEN":
            for family in ["pure_cdf", "website_equalweight"]:
                slots.append(dict(slot, method_family=family))
            continue
        directory = output / status["trial"]
        category = registry["categories"][status["target"]]
        query = pd.read_parquet(directory / "query.parquet")
        query = bind_outcomes(query, outcomes, category)
        model = joblib.load(directory / "model/model.joblib")
        scored = score_frozen_rows(model, query, pd.read_parquet(directory / "candidate-frozen.parquet"))
        scored["outcome_state"] = query.qualified_outcome_state.to_numpy()
        for name in query.columns:
            if name.startswith("qualified_"):
                scored[name] = query[name].to_numpy()
        scored.to_parquet(directory / "candidate-scored.parquet", index=False)
        prior = score_frozen_rows(model, query, pd.read_parquet(directory / "role-prior-frozen.parquet"), prior_only=True)
        prior["outcome_state"] = query.qualified_outcome_state.to_numpy()
        for name in query.columns:
            if name.startswith("qualified_"):
                prior[name] = query[name].to_numpy()
        prior.to_parquet(directory / "role-prior-scored.parquet", index=False)
        offers = pd.read_parquet(directory / "literal-offers.parquet")
        controls = literal_controls(offers, scored, category)
        controls.to_parquet(directory / "literal-controls-scored.parquet", index=False)
        report, deltas = report_target(scored, controls, category)
        report["method_family"] = "pure_cdf"
        report["role_prior_summary"] = summarize(prior, category["support"])
        report["distribution_vs_role_prior"] = []
        for metric in ["crps", "log_score"]:
            a, b = scored[metric].to_numpy(), prior[metric].to_numpy()
            good = np.isfinite(a) & np.isfinite(b)
            report["distribution_vs_role_prior"].append({"metric": metric, "paired_rows": int(good.sum()),
                "delta_candidate_minus_prior": float(np.mean(a[good] - b[good])) if good.any() else None,
                "interval": None, "status": "secondary_same_law_distribution_diagnostic"})
        deltas.to_parquet(directory / "paired-row-deltas.parquet", index=False)
        write_json(directory / "report.json", report)
        primary = next(x for x in report["paired"] if x["status"] == "primary")
        slot.update(state="SCORED_DESCRIPTIVE", report_sha256=digest(directory / "report.json"), primary=primary, method_family="pure_cdf")
        slots.append(slot)
        ensemble = score_ensemble(pd.read_parquet(directory / "ensemble-frozen.parquet"), scored, category)
        ensemble.to_parquet(directory / "ensemble-scored.parquet", index=False)
        ensemble_report, ensemble_deltas = report_ensemble(ensemble, controls, category)
        write_json(directory / "ensemble-report.json", ensemble_report)
        ensemble_deltas.to_parquet(directory / "ensemble-paired-row-deltas.parquet", index=False)
        ensemble_primary = next(x for x in ensemble_report["paired"] if x["status"] == "primary")
        slots.append(dict(status, state="SCORED_DESCRIPTIVE", method_family="website_equalweight",
            report_sha256=digest(directory / "ensemble-report.json"), primary=ensemble_primary))
    write_json(output / "website-cdf-report.json", {"registration_id": VERSION, "slots": slots,
        "original_offered_rows": len(opportunities), "original_outcome_states": outcomes.outcome_state.value_counts(dropna=False).to_dict(),
        "evidence": "new reconstruction after exposed original2026Week6; candidate not original runner or prospective",
        "source_qualification": registry["source_qualification"], "prior_search_and_exposure": registry["prior_search_and_exposure"],
        "budget": LIMITS, "ensemble_design": ENSEMBLE_DESIGN, "primary_contrast_slots": 48, "supported_fit_slots": 22, "blocked_ppr_slots": 4,
        "uncertainty": "one exposed week/13 games; no intervals, significance, winner selection, qualification or promotion",
        "new_qualified_replacements": [], "score_passes": 1})
    event(output / "events.jsonl", "SCORE_REPORT_COMPLETED", report_sha256=digest(output / "website-cdf-report.json"))


def environment_receipt():
    names = ["numpy", "pandas", "scipy", "scikit-learn", "pyarrow", "joblib", "threadpoolctl"]
    return {"python": sys.version, "executable": sys.executable,
            "packages": {name: importlib.metadata.version(name) for name in names},
            "threads": 2, "runtime_agent_configuration": "not independently observable by runner; see sealed actual agent configuration"}


def monitored_process(arguments, output, directory, *, remaining_wall, remaining_cpu, per_trial=True):
    """Monitor actual process-group RSS/CPU; no virtual-address-space limit."""
    begin = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    reason, peak = None, 0
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
               MKL_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2", PYTHONPATH=str(root))
    with (directory / "stdout.log").open("x") as stdout, (directory / "stderr.log").open("x") as stderr:
        process = subprocess.Popen([sys.executable, "-m", "nfl_lab.website_cdf", *arguments], cwd=root,
            env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        while process.poll() is None:
            rss, cpu = proc_usage(process.pid)
            peak = max(peak, rss)
            elapsed = time.monotonic() - begin
            if rss > LIMITS["memory_bytes"]:
                reason = "RSS_LIMIT"
            elif elapsed >= remaining_wall:
                reason = "CAMPAIGN_WALL_LIMIT"
            elif cpu >= remaining_cpu:
                reason = "CAMPAIGN_CPU_LIMIT"
            elif per_trial and elapsed > LIMITS["per_trial_wall_seconds"]:
                reason = "TRIAL_WALL_LIMIT"
            elif per_trial and cpu > LIMITS["per_trial_cpu_seconds"]:
                reason = "TRIAL_CPU_LIMIT"
            elif directory_bytes(output) >= LIMITS["private_output_bytes"]:
                reason = "OUTPUT_LIMIT"
            if reason:
                terminate_group(process)
                break
            time.sleep(.1)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"returncode": process.returncode, "reason": reason, "wall_seconds": time.monotonic() - begin,
            "cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
            "sampled_peak_process_group_rss_bytes": peak}


def run(registry_path, output):
    registry_path, output = Path(registry_path).resolve(), Path(output).resolve()
    # Existing directories are always retained, even when the supplied seal is bad.
    if output.exists():
        raise FileExistsError("output exists; campaign restart prohibited")
    registry = check_seal(registry_path)
    if output != Path(registry["output_directory"]).resolve():
        raise ValueError("output differs from sealed create-only campaign directory")
    output.mkdir(parents=True, exist_ok=False)
    began, parent_cpu = time.monotonic(), time.process_time()
    cpu_used, attempts, statuses = 0., 0, []
    log = output / "events.jsonl"
    write_json(output / "registry.json", registry)
    write_json(output / "environment.json", environment_receipt())
    event(log, "CAMPAIGN_STARTED", registry_sha256=digest(registry_path), limits=LIMITS)
    for target in TARGETS:
        for panel in ["base", "context"]:
            relative = f"trials/{target}/{panel}"
            status = {"target": target, "panel": panel, "trial": relative}
            remaining_wall = LIMITS["campaign_wall_seconds"] - (time.monotonic() - began)
            remaining_cpu = LIMITS["campaign_cpu_seconds"] - cpu_used - (time.process_time() - parent_cpu)
            if registry["categories"][target]["state"] != "READY":
                status["state"] = "BLOCKED_CATEGORY_CONTRACT"
            elif remaining_wall <= LIMITS["reporting_wall_reserve_seconds"] or remaining_cpu <= 0:
                status["state"] = "SKIPPED_CAMPAIGN_BUDGET"
            elif attempts >= LIMITS["maximum_candidate_fit_attempts"]:
                status["state"] = "SKIPPED_FIT_BUDGET"
            elif directory_bytes(output) >= LIMITS["private_output_bytes"]:
                status["state"] = "SKIPPED_OUTPUT_BUDGET"
            if "state" not in status:
                attempts += 1
                directory = output / relative
                directory.mkdir(parents=True, exist_ok=False)
                write_json(directory / "attempt-consumed.json", {"attempt": attempts, **status})
                event(log, "ATTEMPT_CONSUMED", attempt=attempts, **status)
                usage = monitored_process(["predict-trial", str(registry_path), str(directory), target, panel], output, directory,
                    remaining_wall=remaining_wall - LIMITS["reporting_wall_reserve_seconds"], remaining_cpu=remaining_cpu)
                cpu_used += usage["cpu_seconds"]
                frozen = usage["returncode"] == 0 and (directory / "prediction-manifest.json").is_file()
                status.update(usage, state="PREDICTION_FROZEN" if frozen else "FAILED_CONSUMED")
            statuses.append(status)
            event(log, status["state"], **{k: v for k, v in status.items() if k != "state"})
            write_json(output / "attempts.json", statuses)
    bindings = {}
    for status in statuses:
        if status["state"] == "PREDICTION_FROZEN":
            directory = output / status["trial"]
            manifest = json.loads((directory / "prediction-manifest.json").read_text())
            for relative, expected in manifest["bindings"].items():
                bindings[str((directory / relative).relative_to(output))] = expected
            bindings[str((directory / "prediction-manifest.json").relative_to(output))] = digest(directory / "prediction-manifest.json")
    write_json(output / "forecast-freeze.json", {"bindings": bindings, "attempts_sha256": digest(output / "attempts.json"),
        "fit_attempts": attempts, "score_passes": 0, "evidence": "postgame calculation-order freeze only"})
    event(log, "ALL_FORECASTS_FROZEN", forecast_freeze_sha256=digest(output / "forecast-freeze.json"), fit_attempts=attempts)
    remaining_wall = LIMITS["campaign_wall_seconds"] - (time.monotonic() - began)
    remaining_cpu = LIMITS["campaign_cpu_seconds"] - cpu_used - (time.process_time() - parent_cpu)
    reporting = output / "reporting"
    reporting.mkdir(exist_ok=False)
    if remaining_wall > 0 and remaining_cpu > 0 and directory_bytes(output) < LIMITS["private_output_bytes"]:
        usage = monitored_process(["score-report", str(registry_path), str(output)], output, reporting,
            remaining_wall=remaining_wall, remaining_cpu=remaining_cpu, per_trial=False)
        cpu_used += usage["cpu_seconds"]
    else:
        usage = {"reason": "CAMPAIGN_BUDGET_BEFORE_SCORE", "returncode": None}
    completed = usage["returncode"] == 0 and (output / "website-cdf-report.json").is_file()
    write_json(output / "completion.json", {"state": "COMPLETED_DESCRIPTIVE" if completed else "INCOMPLETE_RETAINED_NO_RESTART",
        "fit_attempts_consumed": attempts, "score_pass_consumed": (output / "score-consumed.json").exists(),
        "statuses": statuses, "reporting": usage, "wall_seconds": time.monotonic() - began,
        "cpu_seconds": cpu_used + time.process_time() - parent_cpu,
        "output_bytes_before_completion": directory_bytes(output)})
    event(log, "CAMPAIGN_FINISHED", completed=completed, completion_sha256=digest(output / "completion.json"))
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["run", "score-report"]:
        p = sub.add_parser(command)
        p.add_argument("registry")
        p.add_argument("output")
    p = sub.add_parser("predict-trial")
    p.add_argument("registry")
    p.add_argument("output")
    p.add_argument("target", choices=TARGETS)
    p.add_argument("panel", choices=["base", "context"])
    args = parser.parse_args()
    if args.command == "run":
        if not run(args.registry, args.output):
            raise SystemExit(1)
    elif args.command == "predict-trial":
        prediction_trial(args.registry, args.output, args.target, args.panel)
    else:
        score_report(args.registry, args.output)


if __name__ == "__main__":
    main()
