"""Exact root/reviewer gated single invocation for the new yardage recipe."""
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
        raise ValueError("exact sealed new-study plan hash required")
    plan = json.loads(raw)
    expected_go = {"state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": args.sha256,
                   "scope": "ONE_NEXT_NFL_CHECKPOINT_LAD_V1", "previous_managed_writer_closed": True}
    if (json.loads(Path(args.go).read_bytes()) != expected_go or plan["state"] != "ROOT_AND_REVIEWER_SEALED"
            or plan["execution_authorized"] is not True or plan["excluded_seasons"] != [2025]
            or plan["training_seasons"] != [2023]):
        raise ValueError("exact independent root/reviewer GO required before NFL decode or fitting")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    resource.setrlimit(resource.RLIMIT_CPU, (180, 181))
    from nfl_lab.historical_market_comparison import Budget, authenticate, binding, clean, require
    budget = Budget(plan["resources"])
    stop_event = threading.Event()
    class BudgetStop(BaseException):
        pass
    def stop(signum, frame):
        signal.setitimer(signal.ITIMER_REAL, 0)
        raise BudgetStop("finite LAD CPU/wall/RSS cap stopped the consumed invocation")
    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGUSR1, stop)
    signal.signal(signal.SIGXCPU, stop)
    signal.setitimer(signal.ITIMER_REAL, 230)
    def watch():
        while not stop_event.wait(.1):
            try:
                budget.check()
            except BaseException:
                os.kill(os.getpid(), signal.SIGUSR1)
                return
    threading.Thread(target=watch, daemon=True).start()
    native_root = Path(plan["native_control_root"])
    require(not native_root.exists(), "one fresh invocation; preserve earlier attempts")
    native_root.mkdir(parents=True)
    native_bytes = 0
    def encode(value):
        return (json.dumps(clean(value), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    def native_write(name, value):
        nonlocal native_bytes
        body = encode(value)
        require(native_bytes + len(body) <= plan["resources"]["native_control_bytes_cap"], "bounded new native controls exhausted")
        path = native_root / name
        with path.open("xb") as stream:
            stream.write(body)
        native_bytes += len(body)
        return binding(path)
    native_write("CONSUMED.json", {"state": "ONE_NEW_LAD_STUDY_INVOCATION_CONSUMED", "plan_sha256": args.sha256,
                 "original144_meta_fits_remain_consumed": True, "automatic_retries": 0})
    storage = None
    written, write_attempts, retained_charged = {}, 0, 113
    pending = {}
    def frame_bytes(frame):
        buffer = io.BytesIO()
        frame = frame.copy()
        frame.attrs.clear()
        frame.to_parquet(buffer, index=False, compression="zstd")
        return buffer.getvalue()
    def inner_ref(name, body):
        return {"member": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    def capsule_write(name, members):
        nonlocal write_attempts, retained_charged
        require(storage is not None, "root accounting wrapper must own every private write")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            for member, body in sorted(members.items()):
                archive.writestr(member, body)
        body = buffer.getvalue()
        caps = plan["resources"]
        require(write_attempts < caps["maximum_managed_write_attempts_including_failure"], "two managed attempts exhausted")
        require(len(body) <= caps["per_capsule_bytes_cap"], "four-MiB capsule cap exhausted before write")
        require(retained_charged + len(body) <= caps["retained_private_bytes_cap"], "new retained-byte cap exhausted")
        require(retained_charged + 2 * len(body) <= caps["peak_private_bytes_cap"], "new staged peak-byte cap exhausted")
        write_attempts += 1
        retained_charged += len(body)  # charge surviving staging/blobs on failure
        path = Path(plan["output"]) / name
        storage.write_bytes(path, body)
        storage.validate_reference(path)
        container = binding(path)
        require(authenticate(container).read_bytes() == body, "managed capsule readback differs")
        with zipfile.ZipFile(path) as archive:
            require(set(archive.namelist()) == set(members), "managed capsule member set differs")
            for member, expected in members.items():
                require(archive.read(member) == expected, "managed capsule member readback differs")
        written[name] = container
        budget.check()
        return {member: {"container": container, **inner_ref(member, value)} for member, value in members.items()}
    try:
        for ref in plan["implementation_bindings"]:
            authenticate(ref)
        for ref in plan["input_binding"].values():
            authenticate(ref)
        storage_spec = plan["storage"]
        def load_helper(name, ref):
            module_spec = importlib.util.spec_from_file_location(name, authenticate(ref))
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            return module
        old_helper = load_helper("exact_original_market_storage_helper", storage_spec["original_helper"])
        helper = load_helper("exact_new_checkpoint_storage_wrapper", storage_spec["helper"])
        # The new helper changes complete metadata accounting only. All CAS,
        # immutable publication, quota and lock primitives remain inherited.
        base = old_helper.load_frozen(str(authenticate(storage_spec["forward_implementation"])), storage_spec["legacy_library_root"])
        old_cls = old_helper.build_storage_class(base)
        next_metadata_policy = json.loads(authenticate(storage_spec["metadata_descriptor"]).read_bytes())
        next_cls = helper.build_storage_class(old_cls, next_metadata_policy)
        storage = next_cls(storage_spec["legacy_cache"], json.loads(authenticate(storage_spec["market_policy"]).read_bytes()),
                           json.loads(authenticate(storage_spec["legacy_policy"]).read_bytes()),
                           json.loads(authenticate(storage_spec["prior_policy"]).read_bytes()))
        output = Path(plan["output"])
        require(output == storage.live_root / "research" / "next-nfl-checkpoint-lad-v1", "exact separate research destination required")
        require(not output.exists(), "one fresh private result destination required")
        storage.register_root(output)
        from nfl_lab.next_checkpoint_lad import VERSION, fit_forecasts, score_forecasts
        require(plan["version"] == VERSION, "new-study version changed")
        def progress(index, record):
            phase = "STARTED" if record["state"] == "FIT_ATTEMPT_STARTED" else "TERMINAL"
            native_write(f"FIT_{index:02d}_{phase}.json", record)
        forecasts, records = fit_forecasts(plan, budget, progress)
        pending = {"YARDAGE_FORECASTS.parquet": frame_bytes(forecasts), "PARAMETERS.json": encode(records)}
        pending["GLOBAL_FREEZE.json"] = encode({"state": "ALL_NEW_POINTS_AND_PARAMETERS_FROZEN_BEFORE_OUTER_SCORE_READ",
            "version": VERSION, "plan_sha256": args.sha256, "training_seasons": [2023], "evaluation_seasons": [2024, 2026],
            "members": [inner_ref(n, b) for n, b in pending.items()], "outer_outcomes_opened": 0,
            "earlier_exposure": "Both outer seasons already exposed by original study; this is timing-unverified exploratory continuation",
            "resources": budget.receipt()})
        forecast_refs = capsule_write("FORECASTS_FROZEN.zip", pending)
        native_write("FORECAST_READBACK.json", {"state": "EXACT_NEW_FORECAST_READBACK_PASS", "members": forecast_refs})
        pending = {}
        report, scored = score_forecasts(plan, forecasts, budget)
        pending = {"MATCHED_YARDAGE_SCORES.parquet": frame_bytes(scored), "REPORT.json": encode(report)}
        pending["COMPLETE.json"] = encode({"state": "EXPOSED_ARCHIVE_LAD_COMPARISON_COMPLETE", "forecasts": forecast_refs,
            "fit_attempts": len(records), "certified_fits": sum(r["state"] == "FIT_CERTIFIED" for r in records),
            "fallback_fits": sum(r["state"] != "FIT_CERTIFIED" for r in records), "resources": budget.receipt()})
        score_refs = capsule_write("SCORES_COMPLETE.zip", pending)
        pending = {}
        terminal = {"state": "COMPLETE_EXPOSED_ARCHIVE_LAD_COMPARISON", "plan_sha256": args.sha256,
            "bindings": written, "forecasts": forecast_refs, "scores": score_refs, "resources": budget.receipt(),
            "managed_write_attempts": write_attempts, "retained_charged_bytes": retained_charged,
            "native_control_bytes_before_terminal": native_bytes, "new_live_use": False, "offhost_restoration": "UNPROVEN"}
        native_write("COMPLETE_NATIVE.json", terminal)
        print(json.dumps(clean(terminal), sort_keys=True))
    except BaseException as error:
        # Preserve failures; no replacement invocation, fit search, or refunded
        # write slot. Metadata survives even if both managed attempts are spent.
        failure = {"state": "FAILED_NEW_LAD_STUDY_INVOCATION_RETAINED", "error_type": type(error).__name__, "error": str(error),
                   "plan_sha256": args.sha256, "resources": budget.receipt(), "managed_write_attempts": write_attempts,
                   "retained_charged_bytes": retained_charged, "bindings": written}
        native_write("FAILED_NATIVE.json", failure)
        if storage is not None and write_attempts < 2 and pending:
            try:
                pending["FAILURE.json"] = encode(failure)
                capsule_write("FAILED_PRESERVED.zip", pending)
            except BaseException as retention_error:
                native_write("FAILED_RETENTION.json", {"state": "FAILED_CAPSULE_RETENTION_ATTEMPT_CHARGED", "error": str(retention_error),
                             "managed_write_attempts": write_attempts, "retained_charged_bytes": retained_charged})
        raise
    finally:
        stop_event.set()
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    main()
