"""One separately sealed, zero-fit reporting repair of an immutable failed run.

Only derived scored key dtypes are normalized. All graders, identity/cutoff
checks, losses, intervals and report helpers are the original implementations.
There is no prediction, estimator, model-artifact or campaign restart entrypoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from . import role_boosting_campaign as original
from .cdf_campaign import digest, directory_bytes, proc_usage, terminate_group

VERSION = "role-count-reporting-repair-v1-20261023"
LIMITS = dict(maximum_candidate_fit_attempts=0, maximum_prediction_calls=0,
              report_attempts=1, wall_seconds=600, cpu_seconds=900,
              maximum_threads=2, memory_bytes=1536 * 1024 ** 2,
              combined_private_output_bytes=800 * 1024 ** 2)


def create_json(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def source_snapshot(directory):
    """Hash opaque source bytes without opening model artifacts as objects."""
    root = Path(directory).resolve()
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("source symlinks are not permitted")
        if path.is_file():
            result[str(path.relative_to(root))] = digest(path)
    return result


def verify_source_snapshot(directory, expected):
    if not expected or source_snapshot(directory) != expected:
        raise ValueError("original source file inventory or hashes changed")


def check_seal(path):
    repair = json.loads(Path(path).read_text())
    seal = repair.get("seal", {})
    if (repair.get("state") != "SEALED_ROOT_AND_REVIEWER" or seal.get("integrator") != "/root"
            or not str(seal.get("reviewer", "")).startswith("/root/")
            or seal.get("decision") != "PASS_BOUNDED_REPORTING_REPAIR_ONLY"):
        raise ValueError("root and distinct reviewer reporting repair seal required")
    plan = Path(seal["reviewed_plan_path"])
    if digest(plan) != seal["reviewed_plan_sha256"]:
        raise ValueError("reviewed repair plan bytes changed")
    if {k: v for k, v in repair.items() if k not in {"state", "seal"}} != {
            k: v for k, v in json.loads(plan.read_text()).items() if k != "state"}:
        raise ValueError("sealed repair differs from reviewed repair plan")
    if repair.get("registration_id") != VERSION or repair.get("budgets") != LIMITS:
        raise ValueError("fixed repair registration and zero-fit budgets required")
    if repair.get("new_independent_observations") != 0:
        raise ValueError("repair supplies no new independent observations")
    required_code = {str(Path(__file__).resolve())}
    if not required_code <= {str(Path(b["path"]).resolve()) for b in repair["code_bindings"]}:
        raise ValueError("repair implementation must be sealed")
    for binding in [repair["source_registry"], *repair["code_bindings"]]:
        if digest(binding["path"]) != binding["sha256"]:
            raise ValueError("repair binding changed: " + binding["path"])
    # This original seal check is deliberately unchanged. Run this module from
    # the original bound implementation directory after integrating its new file.
    registry = original.check_seal(repair["source_registry"]["path"])
    source, output = Path(repair["source_run_directory"]).resolve(), Path(repair["output_directory"]).resolve()
    if (not Path(repair["source_run_directory"]).is_absolute()
            or not Path(repair["output_directory"]).is_absolute()
            or source != Path(registry["output_directory"]).resolve()
            or output == source or output.is_relative_to(source) or source.is_relative_to(output)
            or output.name != "REPORT_REPAIR_01"):
        raise ValueError("separate absolute create-only REPORT_REPAIR_01 required")
    verify_source_snapshot(source, repair["source_file_sha256"])
    if digest(source / "registry.json") != repair["source_registry"]["sha256"]:
        raise ValueError("original run registry differs from source seal")
    freeze = json.loads((source / "forecast-freeze.json").read_text())
    if digest(source / "attempts.json") != freeze["attempts_sha256"]:
        raise ValueError("original package statuses changed")
    for relative, sha in freeze["bindings"].items():
        item = source / relative
        if not item.resolve().is_relative_to(source) or digest(item) != sha:
            raise ValueError("original frozen bytes changed: " + relative)
    statuses = json.loads((source / "attempts.json").read_text())
    original.validate_statuses(statuses, freeze)
    completion = json.loads((source / "completion.json").read_text())
    marker = json.loads((source / "score-consumed.json").read_text())
    if (completion.get("state") != "INCOMPLETE_RETAINED_NO_RESTART"
            or completion.get("fit_attempts_consumed") != 136 or freeze.get("fit_attempts") != 136
            or completion.get("score_pass_consumed") is not True
            or completion.get("reporting", {}).get("returncode") != 1
            or completion.get("statuses") != statuses
            or marker.get("score_passes") != 1
            or marker.get("forecast_freeze_sha256") != digest(source / "forecast-freeze.json")
            or sum(s["state"] == "PREDICTION_FROZEN" for s in statuses) != 88
            or list(source.rglob("report.json")) or (source / "role-boosting-report.json").exists()):
        raise ValueError("exact failed consumed original reporting attempt required")
    return repair, registry, statuses


def normalize_scored(frame, *, control_methods=False):
    """Normalize derived KEYS only and prove all other values and bits survive."""
    import numpy as np
    import pandas as pd
    from .cdf_engine import KEYS
    from .website_cdf_evaluation import normalize_keys
    if frame.columns.duplicated().any() or set(KEYS) - set(frame):
        raise ValueError("unique complete identity columns required")
    for name in KEYS:
        if frame[name].map(lambda x: isinstance(x, (bool, np.bool_))).any():
            raise ValueError("boolean identity forbidden")
    for name in ["game_id", "player_id"]:
        if not frame[name].map(lambda x: isinstance(x, str)).all():
            raise ValueError("string game/player identity required")
    # The existing normalizer rejects null, fractional and nonfinite keys.
    result = normalize_keys(frame)
    if result.duplicated(KEYS + (["method"] if control_methods else [])).any():
        raise ValueError("duplicate normalized identity")
    before = [(int(s), int(w), g, p) for s, w, g, p in frame[KEYS].itertuples(index=False, name=None)]
    after = list(result[KEYS].itertuples(index=False, name=None))
    if len(frame) != len(result) or before != after or not frame.index.equals(result.index):
        raise ValueError("normalization changed canonical identity or order")
    other = [c for c in frame if c not in KEYS]
    pd.testing.assert_frame_equal(frame[other], result[other], check_exact=True)
    for name in other:
        if pd.api.types.is_float_dtype(frame[name].dtype):
            if frame[name].to_numpy().tobytes() != result[name].to_numpy().tobytes():
                raise ValueError("normalization changed floating point bits: " + name)
    return result


def normalize_scored_frames(candidate, controls):
    """Reject changed/reordered controls before invoking unchanged report checks."""
    import numpy as np
    from .cdf_engine import KEYS, numeric
    candidate, controls = normalize_scored(candidate), normalize_scored_controls(controls)
    for _, control in controls.groupby("method", sort=True):
        if not candidate[KEYS].reset_index(drop=True).equals(control[KEYS].reset_index(drop=True)):
            raise ValueError("candidate/control canonical identity/order differs")
        if not np.array_equal(numeric(candidate, "actual"), numeric(control, "actual"), equal_nan=True):
            raise ValueError("candidate/control outcomes differ")
        if not candidate.participation_state.reset_index(drop=True).equals(control.participation_state.reset_index(drop=True)):
            raise ValueError("candidate/control participation differs")
    return candidate, controls


def normalize_scored_controls(controls):
    if "method" not in controls or controls.method.isna().any() or controls.empty:
        raise ValueError("nonempty explicit control methods required")
    return normalize_scored(controls, control_methods=True)


def provenance(repair, source):
    return {"repair_registration_id": VERSION, "source_registration_id": original.VERSION,
            "original_state": "INCOMPLETE_RETAINED_NO_RESTART", "original_fit_attempts_consumed": 136,
            "original_score_pass_consumed": True, "original_failed_report_attempts": 1,
            "repair_report_attempts_consumed": 1, "cumulative_report_attempts": 2,
            "new_fits": 0, "new_predictions": 0, "new_independent_observations": 0,
            "source_registry_sha256": repair["source_registry"]["sha256"],
            "source_freeze_sha256": repair["source_file_sha256"]["forecast-freeze.json"],
            "source_failed_completion_sha256": repair["source_file_sha256"]["completion.json"],
            "source_consumed_marker_sha256": repair["source_file_sha256"]["score-consumed.json"],
            "source_directory": str(source), "key_repair": "existing normalize_keys on derived scored frames only"}


def report_only(registry_path, output):
    """Worker: read frozen rows, attach original outcomes, run original reports."""
    import pandas as pd
    from .cdf_engine import KEYS, assert_composite_contract
    from .median_boosting import score_frozen_rows
    from .website_cdf_evaluation import bind_outcomes, literal_controls, normalize_keys
    repair, registry, statuses = check_seal(registry_path)
    source, output = Path(repair["source_run_directory"]), Path(output).resolve()
    if output != Path(repair["output_directory"]).resolve() or not (output / "repair-consumed.json").is_file():
        raise ValueError("sealed consumed repair attempt required")
    marker = json.loads((output / "repair-consumed.json").read_text())
    if marker.get("repair_registry_sha256") != digest(registry_path) or marker.get("report_attempts") != 1:
        raise ValueError("repair consumption binding differs")
    create_json(output / "repair-worker-started.json", {"at": datetime.now(timezone.utc).isoformat(), "new_fits": 0})
    history = pd.read_parquet(registry["inputs"]["training_features"]["path"], filters=[("season", ">=", 2022), ("season", "<=", 2024)])
    outcomes = normalize_keys(pd.read_parquet(registry["inputs"]["outcomes"]["path"]))
    opportunities = normalize_keys(pd.read_parquet(registry["inputs"]["opportunities"]["path"]))
    identity = KEYS + ["target"]
    coverage = opportunities[identity].merge(outcomes[identity], on=identity, how="outer", indicator=True, validate="one_to_one")
    if not coverage._merge.eq("both").all():
        raise ValueError("all original offers including blocked PPR must remain")
    frames, controls_by_cell, slots = {}, {}, []
    compact = list(dict.fromkeys(KEYS + ["point", "actual", "participation_state", "outcome_state", "primary_role", "fallback",
        "position", "season", "team", "opponent", "history_state", "probability", "target"]))
    for status in statuses:
        if status["state"] != "PREDICTION_FROZEN":
            slots.append(dict(status))
            continue
        target, variant, period = status["target"], status["variant"], status["period"]
        category, frozen_directory = registry["categories"][target], source / status["trial"]
        directory = output / status["trial"]
        directory.mkdir(parents=True, exist_ok=False)
        query = pd.read_parquet(frozen_directory / "query.parquet")
        historical = period != "website_week6"
        if historical:
            offered = query[KEYS].merge(history.loc[history.season.eq(int(period))], on=KEYS, how="left", sort=False, validate="one_to_one")
            assert_composite_contract(offered, category)
        else:
            offered = bind_outcomes(query, outcomes, category)
        # Keep original grader identity/dtype checks before any repair.
        scored = score_frozen_rows(offered, pd.read_parquet(frozen_directory / "candidate-frozen.parquet"), category)
        old = score_frozen_rows(offered, pd.read_parquet(frozen_directory / "old-hgb-frozen.parquet"), category)
        old["method"] = "old_hgb"
        controls = [old]
        controls.extend(original.saved_control(binding, offered, category, method, mode=registry["source_packet_mode"],
            audit_directory=directory, panel="base") for method, binding in registry["saved_controls"][target]["base"][period].items())
        source_receipts = [c.attrs["source_comparison"] for c in controls if "source_comparison" in c.attrs]
        if not historical:
            controls.append(literal_controls(pd.read_parquet(frozen_directory / "literal-offers.parquet"), scored, category))
        scored, controls = normalize_scored_frames(scored, pd.concat(controls, ignore_index=True))
        scored.to_parquet(directory / "candidate-scored.parquet", index=False)
        controls.to_parquet(directory / "controls-scored.parquet", index=False)
        frames[target, variant, period] = scored[[c for c in compact if c in scored]].copy()
        control_fields = KEYS + ["actual", "participation_state", "point", "primary_role", "method"]
        controls_by_cell[target, variant, period] = controls[control_fields].copy()
        report, deltas = original.report_cell(scored, controls, category, historical=historical)
        report.update(variant=variant, period=period, source_comparisons=source_receipts)
        if (frozen_directory / "role-prior-frozen.parquet").is_file():
            report["role_prior"] = original.summary(score_frozen_rows(offered, pd.read_parquet(frozen_directory / "role-prior-frozen.parquet"), category), category)
        create_json(directory / "report.json", report)
        deltas.to_parquet(directory / "paired-row-deltas.parquet", index=False)
        slots.append(dict(status, state="SCORED_DESCRIPTIVE", report_sha256=digest(directory / "report.json"),
            primary_comparisons=[v for v in report["paired"] if v["status"] == "primary"]))
    aggregate, primary_slots, ablations, common_diagnostics = [], [], [], []
    for target in original.TARGETS:
        category = registry["categories"][target]
        for variant in original.VARIANTS:
            years = [p for p in original.PERIODS[:-1] if (target, variant, p) in frames]
            primary = None
            if years:
                candidate = pd.concat([frames[target, variant, p] for p in years], ignore_index=True)
                controls = pd.concat([controls_by_cell[target, variant, p] for p in years], ignore_index=True)
                report, _ = original.report_cell(candidate, controls, category, historical=True, pooled=True)
                report.update(variant=variant, compared_complete_years=[int(p) for p in years],
                    excluded_years=[int(p) for p in original.PERIODS[:-1] if p not in years],
                    partial_failure_policy="only complete same annual cells paired; all failures retained")
                aggregate.append(report)
                primary = next(v for v in report["paired"] if v["status"] == "primary")
            blocked = category["state"] != "READY"
            primary_slots.append({"target": target, "variant": variant, "period": "pooled2022-2024",
                "state": "BLOCKED_CATEGORY_CONTRACT" if blocked else "SCORED_DESCRIPTIVE" if len(years) == 3 else "PARTIAL_OR_FAILED_RETAINED",
                "primary": primary, "compared_complete_years": [int(p) for p in years]})
            website = next((s for s in slots if s["target"] == target and s["variant"] == variant and s["period"] == "website_week6"), None)
            primary_slots.append({"target": target, "variant": variant, "period": "website_week6",
                "state": website["state"] if website else "FAILED_RETAINED", "primary": next(iter(website.get("primary_comparisons", [])), None) if website else None})
        if category["state"] != "READY":
            continue
        for period in original.PERIODS:
            if any((target, v, period) not in frames for v in original.VARIANTS):
                continue
            common_diagnostics.extend(dict(value, target=target, period=period) for value in original.common_cohort_reports(
                frames[target, "A", period], frames[target, "B", period], controls_by_cell[target, "A", period], category))
            for subset in [False, True]:
                b, a = frames[target, "B", period], frames[target, "A", period]
                value, _ = original.point_pairs(b, a, category, role_subset=subset)
                value.update(target=target, period=period, comparison="B_minus_A", status="secondary")
                if period != "website_week6":
                    value["intervals"] = [original.interval(b, a, category, subset, c) for c in ["week", "game"]]
                ablations.append(value)
    coherence = original.coherence_audits(frames, output / "coherence")
    repair_provenance = provenance(repair, source)
    create_json(output / "role-boosting-report.json", {"registration_id": original.VERSION,
        "repair_registration_id": VERSION, "repair_provenance": repair_provenance,
        "slots": slots, "primary_slots": primary_slots, "historical_pooled": aggregate,
        "role_loss_ablations": ablations, "common_cohort_diagnostics": common_diagnostics,
        "comparator_availability": {p: {m: "N/A_not_recorded_for_exact_panel" for m in ["website", "raw", "simple"]}
            if p != "website_week6" else {m: "literal_original_offers; exact paired/missing counts in each cell" for m in ["website", "raw", "simple"]} for p in original.PERIODS},
        "coherence": coherence, "planned_packages": 96, "planned_new_model_packages": 48,
        "planned_alias_packages": 40, "blocked_ppr_packages": 8, "blocked_ppr_subfit_slots": 24,
        "primary_contrast_slots": 48, "blocked_ppr_primary_contrasts": 4,
        "maximum_estimator_attempts": 136, "model_design": original.DESIGN, "comparisons": original.COMPARISONS,
        "budgets": original.LIMITS, "repair_budgets": LIMITS, "original_opportunity_rows": len(opportunities),
        "score_passes": 1, "cumulative_report_attempts": 2,
        "source_qualification": registry["source_qualification"], "source_packet_mode": registry["source_packet_mode"],
        "study_source_relation": registry["study_source_relation"],
        "prior_search_and_exposure": registry["prior_search_and_exposure"], "new_qualified_replacements": [],
        "confirmation": "none; all periods exposed; no independent confirmation, prospective or promotion claim"})
    verify_source_snapshot(source, repair["source_file_sha256"])


def run(registry_path, output):
    """Consume the sole new attempt and supervise its finite report-only worker."""
    begin, parent_cpu_begin = time.monotonic(), time.process_time()
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("repair output exists; no second repair attempt")
    repair, _, statuses = check_seal(registry_path)
    if output != Path(repair["output_directory"]).resolve():
        raise ValueError("sealed repair output differs")
    source = Path(repair["source_run_directory"])
    output.mkdir(parents=True, exist_ok=False)
    original.byte_copy({"path": str(registry_path), "sha256": digest(registry_path)}, output / "repair-registry.json")
    create_json(output / "repair-consumed.json", {"at": datetime.now(timezone.utc).isoformat(),
        "repair_registry_sha256": digest(registry_path), "report_attempts": 1, "new_fits": 0, "new_predictions": 0})
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    peak, reason, process, usage = 0, None, None, {}
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2", PYTHONPATH=str(root))
    try:
        with (output / "stdout.log").open("x") as stdout, (output / "stderr.log").open("x") as stderr:
            process = subprocess.Popen([sys.executable, "-m", "nfl_lab.role_boosting_reporting_repair", "_report",
                "--registry", str(Path(registry_path).resolve()), "--output", str(output)],
                cwd=root, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            while process.poll() is None:
                rss, cpu = proc_usage(process.pid)
                # The supervisor need not lead its shell's process group.
                # Measure only this process directly, plus the worker group.
                parent_rss = int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
                parent_cpu = time.process_time() - parent_cpu_begin
                peak = max(peak, rss + parent_rss)
                if rss + parent_rss > LIMITS["memory_bytes"]:
                    reason = "COMBINED_RSS_LIMIT"
                elif time.monotonic() - begin >= LIMITS["wall_seconds"]:
                    reason = "REPAIR_WALL_LIMIT"
                elif cpu + parent_cpu >= LIMITS["cpu_seconds"]:
                    reason = "REPAIR_CPU_LIMIT"
                elif directory_bytes(source) + directory_bytes(output) >= LIMITS["combined_private_output_bytes"]:
                    reason = "COMBINED_PRIVATE_OUTPUT_LIMIT"
                if reason:
                    terminate_group(process)
                    break
                time.sleep(.1)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        usage = {"returncode": process.returncode, "reason": reason, "wall_seconds": time.monotonic() - begin,
                 "cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime + time.process_time() - parent_cpu_begin,
                 "sampled_peak_combined_rss_bytes": peak}
    finally:
        if process is not None and process.poll() is None:
            terminate_group(process)
        unchanged = source_snapshot(source) == repair["source_file_sha256"]
        complete = usage.get("returncode") == 0 and reason is None and unchanged and (output / "role-boosting-report.json").is_file()
        create_json(output / "completion.json", {"registration_id": VERSION,
            "state": "COMPLETED_REPORTING_REPAIR_DESCRIPTIVE" if complete else "INCOMPLETE_REPAIR_RETAINED_NO_RESTART",
            "repair_provenance": provenance(repair, source), "reporting": usage,
            "source_files_unchanged": unchanged, "original_fit_attempts_consumed": 136,
            "new_fit_attempts_consumed": 0, "new_prediction_calls": 0,
            "repair_report_attempts_consumed": 1, "cumulative_report_attempts": 2,
            "source_statuses": statuses, "output_bytes_before_completion": directory_bytes(output),
            "combined_private_output_bytes_before_completion": directory_bytes(source) + directory_bytes(output)})
        if not unchanged:
            raise ValueError("original run changed during repair")
    return json.loads((output / "completion.json").read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "_report"])
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "run":
        result = run(args.registry, args.output)
        print(json.dumps({k: v for k, v in result.items() if k != "source_statuses"}, allow_nan=False))
        if result["state"] != "COMPLETED_REPORTING_REPAIR_DESCRIPTIVE":
            raise SystemExit(1)
    else:
        report_only(args.registry, args.output)


if __name__ == "__main__":
    main()
