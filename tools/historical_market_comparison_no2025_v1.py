"""Execute one exact sealed no-2025 comparison; no network or live publishing."""
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
        "scope": "ONE_HISTORICAL_MARKET_COMPARISON_NO2025_V1", "previous_managed_writer_closed": True}
    if root_go != expected or plan["state"] != "ROOT_AND_REVIEWER_SEALED" or plan["execution_authorized"] is not True:
        raise ValueError("exact independent root/reviewer GO required before NFL decode")
    if plan["excluded_seasons"] != [2025] or plan["calibration_training_seasons"] != [2022, 2023]:
        raise ValueError("no2025/earlier-calibration scientific contract changed")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    from nfl_lab.historical_market_comparison import (VERSION, Budget, authenticate, binding, clean,
        pair_and_canonicalize, forecast_football, load_labels, calibrate, paper_lists, score, require, read_capsule_member)
    require(plan["version"] == VERSION, "wrong comparison version")
    for ref in plan["implementation_bindings"]:
        authenticate(ref)
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
    require(output == storage.live_root / "research" / "historical-market-comparison-no2025-v1", "exact new private allocation destination required")
    require(not output.exists(), "one fresh invocation; old failed attempts cannot be retried")
    output = storage.register_root(output)
    written = {}
    write_attempts, attempted_retained_bytes = 0, 0
    def private_write(name, body):
        nonlocal write_attempts, attempted_retained_bytes
        require(write_attempts < 4, "four managed write attempts consumed; outer failure metadata only")
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
        private_write("CONSUMED.json", json_bytes({"version": VERSION, "plan_sha256": args.sha256, "invocations": 1,
            "automatic_retries": 0, "requested_model": plan["requested_model"], "requested_effort": plan["requested_effort"], "actual_backend": "UNATTESTED"}))
        canonical_frames, market_audits = [], []
        columns = ["season", "week", "game_id", "player_id", "team", "opponent", "position", "kickoff_utc", "is_home",
            "target", "period", "side", "line", "american_odds", "book_id", "book_kind", "source_collection_naive",
            "source_eligible_exploratory", "identity_status", "duplicate_status", "source_row_number", "source_sha256",
            "source_member", "rejection_reasons"]
        for ref in plan["normalized_market_inputs"]:
            # Inner members have real container pointers; no fabricated file
            # aliases and no extracted private Parquet copies are created.
            source_body = read_capsule_member(ref)
            import pyarrow as pa
            import pyarrow.parquet as pq
            for year in [2026, 2024, 2023, 2022]:
                filters = [("season", "=", year)]
                if year == 2026:
                    filters.append(("week", "in", [1, 2, 3, 4, 5]))
                frame = pq.read_table(pa.BufferReader(source_body), columns=columns, filters=filters).to_pandas(strings_to_categorical=True)
                if frame.empty:
                    continue
                require(not frame.season.eq(2025).any(), "excluded source season decoded")
                budget.check("normalized_market_rows", len(frame))
                canonical, audit = pair_and_canonicalize(frame, plan["books"]["offering_book_ids"])
                canonical_frames.append(canonical)
                market_audits.append({"season": year, **audit})
                del frame
                budget.check()
        offers = pd.concat(canonical_frames, ignore_index=True)
        require(not offers.duplicated(["season", "week", "game_id", "player_id", "target", "book_id"]).any(), "normalized source files overlap")
        del canonical_frames
        budget.check("canonical_offers", len(offers))
        pending_members["ALL_CANONICAL_OFFERED_POOL.parquet"] = frame_bytes(offers)
        football, feature_audits = forecast_football(plan, offers, budget)
        pending_members["F_THRESHOLD_FORECASTS.parquet"] = frame_bytes(football)
        pending_members["F_THRESHOLD_FREEZE.json"] = json_bytes({"state": "FOOTBALL_LAW_PRODUCTS_HASHED_BEFORE_EARLIER_CALIBRATION_LABELS",
            "forecasts": member_ref("F_THRESHOLD_FORECASTS.parquet", pending_members["F_THRESHOLD_FORECASTS.parquet"]),
            "no2025_rows": True, "market_audit": market_audits, "feature_audits": feature_audits, "resources": budget.receipt()})
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
            "global_forecast_freeze": freeze, "new_base_CDF_fits": 0, "live_changes": 0})
        score_refs = capsule_write("SCORES_COMPLETE.zip", pending_members)
        pending_members = {}
        budget.check()
        private_write("COMPLETE.json", json_bytes({"state": "COMPLETE_EXPLORATORY_COMPARISON", "bindings": dict(written),
            "forecasts": forecast_refs, "scores": score_refs, "resources": budget.receipt()}))
        budget.check()
        print(json.dumps({"state": "COMPLETE_EXPLORATORY_COMPARISON", "report": score_refs["REPORT.json"], "complete": written["COMPLETE.json"]}))
    except BaseException as error:
        finished.set()
        remaining_wall = plan["resources"]["wall_seconds"] - (time.monotonic() - budget.start)
        # The phase retains a hard wall deadline during recovery. The CPU hard
        # limit remains301s after the300s soft signal; it is never disabled.
        signal.signal(signal.SIGALRM, lambda *unused: os._exit(124))
        signal.setitimer(signal.ITIMER_REAL, max(.001, remaining_wall))
        outer = {"state": "FAILED_NO_RETRY", "exception_type": type(error).__name__, "resources": budget.receipt(),
            "managed_write_attempts": write_attempts, "attempted_retained_bytes_including_failed_writes": attempted_retained_bytes,
            "completed_artifacts": dict(written), "old_failures_and_budgets_preserved": True,
            "raw_values_or_exception_message_in_outer_receipt": False}
        outer_path = Path(plan["outer_failure_receipt"])
        outer_path.parent.mkdir(parents=True, exist_ok=True)
        with outer_path.open("xb") as stream:
            stream.write(json_bytes(outer))
        # Slow immutable publication is attempted only inside the original
        # remaining resource envelope and unused write slots. Otherwise this
        # native metadata receipt preserves consumption without a fifth write.
        remaining_cpu = plan["resources"]["CPU_seconds"] - (time.process_time() - budget.cpu_start)
        if write_attempts < 4 and remaining_wall > 60 and remaining_cpu > 30:
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
