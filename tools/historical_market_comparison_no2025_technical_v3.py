"""Technical V3: unique original football inputs, then unchanged-law fanout."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import time
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    raw = Path(args.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError("exact sealed plan hash required")
    plan = json.loads(raw)
    root_go = json.loads(Path(args.go).read_bytes())
    expected = {"state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": args.sha256,
        "scope": "ONE_HISTORICAL_MARKET_COMPARISON_NO2025_TECHNICAL_V3", "previous_managed_writer_closed": True}
    if root_go != expected or plan["state"] != "ROOT_AND_REVIEWER_SEALED" or plan["execution_authorized"] is not True:
        raise ValueError("exact independent root/reviewer GO required before NFL decode")
    if plan["excluded_seasons"] != [2025] or plan["calibration_training_seasons"] != [2022, 2023]:
        raise ValueError("no2025/earlier-calibration scientific contract changed")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    from nfl_lab.historical_market_comparison import (Budget, authenticate, binding, clean,
        pair_and_canonicalize, forecast_football, load_labels, calibrate, paper_lists, score, require, read_capsule_member)
    from nfl_lab.historical_market_queries_v3 import VERSION, reuse_context_abstentions, preflight_queries, forecast_unique
    require(plan["version"] == VERSION, "wrong comparison version")
    for ref in plan["implementation_bindings"]:
        authenticate(ref)
    outer_control_bytes = 113  # conservatively charge the new ownership marker
    def outer_write(path, body):
        nonlocal outer_control_bytes
        require(outer_control_bytes + len(body) <= 64 * 1024, "technical V3 native control reserve64KiB exhausted")
        outer_control_bytes += len(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(body)
    consume_path = Path(plan["outer_consumption_receipt"])
    outer_write(consume_path, (json.dumps({"state": "ONE_TECHNICAL_V3_ATTEMPT_CONSUMED", "version": VERSION,
        "plan_sha256": args.sha256, "V1_V2_failures_preserved": True, "automatic_retries": 0}, sort_keys=True) + "\n").encode())
    budget = Budget(plan["resources"])
    resource.setrlimit(resource.RLIMIT_CPU, (int(plan["resources"]["CPU_seconds"]), int(plan["resources"]["CPU_seconds"]) + 1))
    finished = threading.Event()
    class BudgetStop(BaseException):
        pass
    def stop(signum, frame):
        signal.setitimer(signal.ITIMER_REAL, 0)
        raise BudgetStop("finite comparison CPU/wall/RSS watchdog stopped worker; consumed attempt retained")
    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGUSR1, stop)
    signal.signal(signal.SIGXCPU, stop)
    signal.setitimer(signal.ITIMER_REAL, plan["resources"]["wall_seconds"] - 10)
    def watch():
        while not finished.wait(.1):
            try:
                budget.check()
            except BaseException:
                os.kill(os.getpid(), signal.SIGUSR1)
                return
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    import pandas as pd
    import pyarrow.dataset as ds
    source_complete = json.loads(authenticate(plan["source_capture_complete"]).read_bytes())
    require(source_complete["state"] == plan["source_capture_complete_state"], "source capture must finish before new comparison writer")
    helper_path = authenticate(plan["storage"]["helper"])
    spec = importlib.util.spec_from_file_location("pinned_historical_market_storage_helper", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    base = helper.load_frozen(str(authenticate(plan["storage"]["forward_implementation"])), plan["storage"]["legacy_library_root"])
    market_policy = json.loads(authenticate(plan["storage"]["market_policy"]).read_bytes())
    legacy_policy = json.loads(authenticate(plan["storage"]["legacy_policy"]).read_bytes())
    prior_policy = json.loads(authenticate(plan["storage"]["prior_policy"]).read_bytes())
    storage = helper.build_storage_class(base)(plan["storage"]["legacy_cache"], market_policy, legacy_policy, prior_policy)
    output = Path(plan["output"])
    require(output == storage.live_root / "research" / "historical-market-comparison-no2025-technical-v3", "exact separately versioned technical destination required")
    require(not output.exists(), "one fresh invocation; old failed attempts cannot be retried")
    output = storage.register_root(output)
    written = {}
    write_attempts = 0
    attempted_retained_bytes = plan["prior_consumption"]["retained_named_bytes"] + plan["prior_consumption"]["ownership_metadata_bytes"] + 113
    def private_write(name, body):
        nonlocal write_attempts, attempted_retained_bytes
        require(write_attempts < 2, "two remaining managed write attempts consumed; outer failure metadata only")
        retained = attempted_retained_bytes
        require(retained + len(body) <= plan["resources"]["retained_new_private_bytes_cap"], "new retained-byte cap before write")
        require(retained + 2 * len(body) <= plan["resources"]["peak_new_private_bytes_cap"], "new staging-byte cap before write")
        # Charge BEFORE the writer: a blob/temporary can survive a failed alias
        # publication or validation. Recovery never resets this byte envelope.
        write_attempts += 1
        attempted_retained_bytes += len(body)
        storage.write_bytes(output / name, body)
        storage.validate_reference(output / name)
        written[name] = binding(output / name)
        return written[name]
    def json_bytes(value):
        return (json.dumps(clean(value), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    def member_ref(name, body):
        return {"member": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    def frame_bytes(frame):
        value = frame.copy()
        value.attrs.clear()
        buffer = io.BytesIO()
        value.to_parquet(buffer, index=False, compression="zstd")
        return buffer.getvalue()
    def capsule_write(name, members):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            for member, body in sorted(members.items()):
                archive.writestr(member, body)
        container = private_write(name, buffer.getvalue())
        with zipfile.ZipFile(authenticate(container)) as archive:
            require(set(archive.namelist()) == set(members), "capsule member set differs on readback")
            for member, body in members.items():
                restored = archive.read(member)
                require(restored == body, "capsule member bytes differ on readback")
        return {member: {"container": container, **member_ref(member, body)} for member, body in members.items()}
    pending_members = {}
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        cached_body = read_capsule_member(plan["cached_canonical_offers"])
        offers = pq.read_table(pa.BufferReader(cached_body)).to_pandas()
        require(len(offers) == 99388 and not offers.season.eq(2025).any(), "cached V1 whole offered vector differs")
        require(not offers.duplicated(["season", "week", "game_id", "player_id", "target", "book_id"]).any(), "normalized source files overlap")
        budget.check("canonical_offers", len(offers))
        pending_members["ALL_CANONICAL_OFFERED_POOL.parquet"] = cached_body
        abstention_body = read_capsule_member(plan["cached_context_abstentions"])
        abstentions = pq.read_table(pa.BufferReader(abstention_body)).to_pandas()
        context_body = read_capsule_member(plan["cached_context_admission"])
        context_admission = json.loads(context_body)
        require(context_admission["state"] == "ROW_ABSTENTION_ONLY_ORIGINAL_QUERIES_UNCHANGED", "cached context qualification state differs")
        compatible = reuse_context_abstentions(offers, abstentions)
        context_audits = context_admission["coverage"]
        pending_members["STRICT_CONTEXT_ABSTENTIONS.parquet"] = abstention_body
        pending_members["CONTEXT_ADMISSION.json"] = context_body
        queries, preflight_records, feature_audits = preflight_queries(plan, compatible, budget)
        preflight_body = json_bytes({"state": "ALL_REAL_UNIQUE_QUERY_CLOCK_IDENTITY_PREFLIGHT_PASS_NO_INFERENCE",
            "records": preflight_records, "evaluation_loss_or_calibration_labels_opened": 0,
            "permitted_feature_history": "same original earlier source outcomes under strict cutoffs; no2025",
            "model_loads_predictions_law_queries_in_preflight": 0, "resources": budget.receipt()})
        outer_write(Path(plan["outer_preflight_receipt"]), preflight_body)
        pending_members["REAL_QUERY_PREFLIGHT.json"] = preflight_body
        football, inference_audits = forecast_unique(plan, compatible, budget, queries, preflight_records)
        feature_audits += inference_audits
        pending_members["F_THRESHOLD_FORECASTS.parquet"] = frame_bytes(football)
        pending_members["F_THRESHOLD_FREEZE.json"] = json_bytes({"state": "FOOTBALL_LAW_PRODUCTS_HASHED_BEFORE_EARLIER_CALIBRATION_LABELS",
            "forecasts": member_ref("F_THRESHOLD_FORECASTS.parquet", pending_members["F_THRESHOLD_FORECASTS.parquet"]),
            "no2025_rows": True, "cached_market_pool": plan["cached_canonical_offers"], "context_audits": context_audits,
            "feature_audits": feature_audits, "resources": budget.receipt()})
        train_labels = load_labels(plan, [2022, 2023])
        calibrated, models = calibrate(plan, football, train_labels, budget)
        pending_members["CALIBRATORS.json"] = json_bytes({"training_seasons": [2022, 2023], "parameters": models,
            "evaluation_labels_or_tuning": 0, "offering_book_excluded_throughout_each_panel": True})
        evaluated = calibrated.loc[calibrated.season.isin([2024, 2026])].reset_index(drop=True)
        pending_members["EVALUATION_FORECASTS.parquet"] = frame_bytes(evaluated)
        lists = paper_lists(evaluated)
        pending_members["PAPER_LISTS_FROZEN.parquet"] = frame_bytes(lists)
        pending_members["GLOBAL_FORECAST_FREEZE.json"] = json_bytes({"state": "ALL_FORECASTS_PARAMETERS_AND_PAPER_LISTS_FROZEN_BEFORE_EVALUATION_GRADING",
            "members": [member_ref(n, b) for n, b in pending_members.items()], "calibration_years": [2022, 2023], "evaluation_years": [2024, 2026],
            "2026_history_disclosure": "earlier2026 outcomes used only behind strict individual feature cutoffs; none used for calibration or selection",
            "actual_book_settlement": "UNQUALIFIED_EXPLORATORY_ASSUMED_PROTOCOL", "resources": budget.receipt()})
        pending_members["SCORE_CONSUMED.json"] = json_bytes({"global_freeze": member_ref("GLOBAL_FORECAST_FREEZE.json", pending_members["GLOBAL_FORECAST_FREEZE.json"]), "grading_phases": 1})
        forecast_refs = capsule_write("FORECASTS_FROZEN.zip", pending_members)
        freeze = forecast_refs["GLOBAL_FORECAST_FREEZE.json"]
        pending_members = {}
        evaluation_labels = load_labels(plan, [2024, 2026])
        report, matched, paper_grade = score(plan, evaluated, evaluation_labels, lists, budget)
        pending_members["MATCHED_SCORES.parquet"] = frame_bytes(matched)
        pending_members["PAPER_ASSUMED_SETTLEMENT.parquet"] = frame_bytes(paper_grade)
        pending_members["REPORT.json"] = json_bytes({"state": "COMPLETE_EXPLORATORY_COMPARISON", "report": report, "resources": budget.receipt(),
            "global_forecast_freeze": freeze, "context_abstention_coverage": context_audits,
            "prior_consumption": plan["prior_consumption"], "new_base_CDF_fits": 0, "live_changes": 0})
        pending_members["COMPLETE.json"] = json_bytes({"state": "COMPARISON_PRODUCTS_READY_PENDING_SECOND_CAS_WRITE_AND_FINAL_NATIVE_RESOURCE_GATE",
            "global_forecast_freeze": freeze, "prior_consumption": plan["prior_consumption"], "resources_before_final_write": budget.receipt()})
        score_refs = capsule_write("SCORES_COMPLETE.zip", pending_members)
        pending_members = {}
        budget.check()
        terminal_path = Path(plan["outer_terminal_receipt"])
        outer_write(terminal_path, json_bytes({"state": "COMPLETE_EXPLORATORY_COMPARISON_TECHNICAL_V3", "bindings": dict(written),
            "forecasts": forecast_refs, "scores": score_refs, "resources": budget.receipt(), "managed_write_attempts": write_attempts,
            "cumulative_retained_bytes_including_V1_V2_failures": attempted_retained_bytes, "V1_V2_failures_preserved": True}))
        budget.check()
        print(json.dumps({"state": "COMPLETE_EXPLORATORY_COMPARISON_TECHNICAL_V3", "report": score_refs["REPORT.json"], "terminal_receipt": str(terminal_path)}))
    except BaseException as error:
        finished.set()
        remaining_wall = plan["resources"]["wall_seconds"] - (time.monotonic() - budget.start)
        # The phase retains a hard wall deadline during recovery. The CPU hard
        # limit remains241s after the240s soft signal; it is never disabled.
        signal.signal(signal.SIGALRM, lambda *unused: os._exit(124))
        signal.setitimer(signal.ITIMER_REAL, max(.001, remaining_wall))
        outer = {"state": "FAILED_NO_RETRY", "exception_type": type(error).__name__, "resources": budget.receipt(),
            "managed_write_attempts": write_attempts, "attempted_retained_bytes_including_failed_writes": attempted_retained_bytes,
            "completed_artifacts": dict(written), "old_failures_and_budgets_preserved": True,
            "raw_values_or_exception_message_in_outer_receipt": False}
        outer_path = Path(plan["outer_failure_receipt"])
        outer_write(outer_path, json_bytes(outer))
        # Slow immutable publication is attempted only inside the original
        # remaining resource envelope and unused write slots. Otherwise this
        # native metadata receipt preserves consumption without a fifth write.
        remaining_cpu = plan["resources"]["CPU_seconds"] - (time.process_time() - budget.cpu_start)
        if write_attempts < 2 and remaining_wall > 60 and remaining_cpu > 30:
            pending_members["FAILED.json"] = json_bytes({**outer, "message_private": str(error)[:1000]})
            try:
                capsule_write("FAILED_PRESERVED.zip", pending_members)
            except BaseException:
                pass
        print(json.dumps({"state": "FAILED_NO_RETRY", "outer_receipt": str(outer_path), "exception_type": type(error).__name__}))
        raise SystemExit(1) from None
    finally:
        finished.set()
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    main()
