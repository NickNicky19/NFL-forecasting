"""Separate2026 retained-PBP source-label continuation through inherited CAS.

No source rows are written outside that CAS.  A consumed native receipt survives
every failure; the one managed write slot includes failed publication attempts.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import time


BASE = Path(__file__).resolve().parents[1]
DESTINATION = Path("/workspace/website-methods-research/resumed/historical-market-forward-v1-20261028/cache/operational-live-v3/research/next-nfl-checkpoint-chart-2026-bridge-v1")
REPORT = BASE / "reports" / "next-nfl-checkpoint-chart-ppr-20261028"
CONTINUATION = "next-checkpoint-chart-2026-retained-PBP-bridge-v1"
CODE = ("nfl_lab/next_checkpoint_chart_ppr.py", "tools/next_checkpoint_chart_ppr_labels.py",
        "tools/next_checkpoint_chart_bridge_run.py", "tools/next_checkpoint_chart_bridge_build.py", "nfl_lab/ppr_outcomes.py",
        "nfl_lab/ppr_sources.py", "nfl_lab/scoring.py")
EXACT_CAPS = {"fits": 0, "forecast_inference": 0, "accuracy_comparisons": 0, "HTTP": 0,
              "retries": 0, "threads": 1, "CPU_seconds": 60, "wall_seconds": 90,
              "RSS_bytes": 512 * 1024**2, "aggregate_metadata_bytes": 256 * 1024,
              "private_label_bytes": 2 * 1024**2, "invocations": 1,
              "maximum_managed_write_attempts_including_failure": 1,
              "retained_private_bytes_cap": 4 * 1024**2,
              "peak_private_bytes_cap": 8 * 1024**2, "native_control_bytes_cap": 64 * 1024}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path
            and not any(p.is_symlink() for p in (path, *path.parents)), "canonical nonsymlink path required")
    return path


def authenticate(ref):
    path = canonical(ref["path"])
    before = path.stat()
    require(before.st_size == ref["bytes"], "implementation/policy size changed")
    body = path.read_bytes()
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            and sha(body) == ref["sha256"], "implementation/policy hash changed")
    return path


def main():
    start_wall, start_cpu = time.monotonic(), time.process_time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    raw = canonical(args.plan).read_bytes()
    require(sha(raw) == args.sha256, "exact root-sealed chart-label plan hash required")
    plan, go = json.loads(raw), json.loads(canonical(args.go).read_bytes())
    require(plan.get("version") == CONTINUATION
            and plan.get("continuation_version") == CONTINUATION
            and plan.get("target") == "nick-chart-ppr-v1"
            and plan.get("state") == "ROOT_AND_INDEPENDENT_SEALED"
            and plan.get("execution_authorized") is True
            and (plan.get("root_registration") or {}).get("registered_by") == "/root"
            and plan.get("independent_review") == "PASS", "root and independent sealed plan required")
    require(go.get("state") == "ROOT_AND_INDEPENDENT_GO" and go.get("plan_sha256") == args.sha256
            and go.get("registered_by") == "/root" and go.get("independent_review") == "PASS"
            and go.get("predictive_fits") == 0
            and go.get("source_native_broad_zero_qualification") == "PASS", "exact root and independent GO required")
    caps = plan["resources"]
    require(all(type(caps.get(k)) is int and caps[k] == v for k, v in EXACT_CAPS.items()), "exact finite chart-label caps required")
    prior_retained_bytes = 0  # Prior packets remain globally charged, never rewritten or refunded.
    require(plan.get("prior_attempts_preserved") is True, "original failures and completed labels remain preserved")
    require(sys.flags.dont_write_bytecode, "invoke Python with -B and PYTHONDONTWRITEBYTECODE=1")
    sys.dont_write_bytecode = True
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "ARROW_NUM_THREADS", "ARROW_IO_THREADS"):
        os.environ[key] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["MALLOC_ARENA_MAX"] = "1"
    require(canonical(plan["output"]) == DESTINATION, "exact separate chart-label CAS destination required")
    native_root = canonical(plan["native_control_root"])
    require(native_root == REPORT / "BRIDGE_BUILD_NATIVE_V1", "exact counted native controls required")
    aggregate_path = canonical(plan["safe_aggregate_path"])
    require(aggregate_path == REPORT / "SAFE_AGGREGATE_BRIDGE_V1.json", "exact counted safe aggregate destination required")
    require(not native_root.exists() and not aggregate_path.exists() and not DESTINATION.exists(),
            "one fresh attempt required; existing failures/outputs remain consumed")
    for relative in CODE:
        require(go.get("code_sha256", {}).get(relative) == sha(canonical(BASE / relative).read_bytes()),
                "GO implementation binding changed: " + relative)

    native_root.mkdir(mode=0o700)
    native_bytes = 0

    def native_write(name, value):
        nonlocal native_bytes
        body = encoded(value)
        require(native_bytes + len(body) <= caps["native_control_bytes_cap"], "native receipt cap exhausted")
        with (native_root / name).open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        native_bytes += len(body)

    native_write("CONSUMED.json", {"state": "ONE_CHART_LABEL_INVOCATION_CONSUMED_BEFORE_SOURCE_DECODE",
        "continuation_version": CONTINUATION, "prior_attempt_remains_consumed": True,
        "prior_retained_private_bytes": prior_retained_bytes,
        "plan_sha256": args.sha256, "predictive_fits": 0, "forecast_inference": 0,
        "automatic_retries": 0, "maximum_managed_write_attempts_including_failure": 1,
        "old_caps_failures_and_consumed_attempts_unchanged": True})
    # Match the existing scientific runners: CPU signal at60s, hard stop61s;
    # early wall/RSS interruption leaves time to retain the consumed failure.
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    stop_event = threading.Event()
    storage, capsule_ref, payload, summary = None, None, None, None
    managed_attempts, retained_charged, private_control_delta = 0, prior_retained_bytes, 0
    phase = "consumed_before_import"

    class BudgetStop(BaseException):
        pass

    class FinalRetentionDeadline(BaseException):
        pass

    def receipt():
        return {"CPU_seconds": time.process_time() - start_cpu, "wall_seconds": time.monotonic() - start_wall,
                "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}

    def check():
        use = receipt()
        require(use["CPU_seconds"] <= caps["CPU_seconds"] and use["wall_seconds"] <= caps["wall_seconds"]
                and use["peak_RSS_bytes"] <= caps["RSS_bytes"], "finite chart-label resource cap exceeded")
        return use

    def stop(signum, frame):
        signal.setitimer(signal.ITIMER_REAL, 0)
        raise BudgetStop("finite chart-label CPU/wall/RSS interruption; invocation remains consumed")

    def final_retention_stop(signum, frame):
        signal.setitimer(signal.ITIMER_REAL, 0)
        # This exception must escape retention unchanged.  No further managed
        # write, scan, lock wait or native fsync is attempted at the deadline.
        raise FinalRetentionDeadline("absolute90s wall deadline ended failure retention; native FAILED receipt remains; no retry")

    def watch():
        while not stop_event.wait(.05):
            use = receipt()
            if (use["peak_RSS_bytes"] > caps["RSS_bytes"] or use["CPU_seconds"] > 57
                    or use["wall_seconds"] > 80):
                os.kill(os.getpid(), signal.SIGUSR1)
                return

    def scan():
        with storage._locked():
            storage._refresh()
            return storage._scan()

    def capsule_write(name, body):
        nonlocal managed_attempts, retained_charged, capsule_ref
        require(storage is not None, "inherited CAS must own every private write")
        require(managed_attempts < 1 and len(body) <= caps["private_label_bytes"], "single <=2MiB managed attempt exhausted")
        require(prior_retained_bytes + private_control_delta + len(body) <= caps["retained_private_bytes_cap"]
                and prior_retained_bytes + private_control_delta + 2 * len(body) <= caps["peak_private_bytes_cap"], "finite retained/peak chart-label cap including original failure exceeded")
        # Charge before entering the inherited writer: partial blobs/staging and
        # alias failures consume the same sole slot, with no retention retry.
        managed_attempts += 1
        retained_charged = prior_retained_bytes + private_control_delta + len(body)
        storage.write_bytes(DESTINATION / name, body)
        ref = storage.validate_reference(DESTINATION / name, sha(body))
        require(ref["bytes"] == len(body) and Path(ref["path"]).read_bytes() == body,
                "exact managed chart-label readback differs")
        capsule_ref = ref
        return ref

    try:
        signal.signal(signal.SIGALRM, stop)
        signal.signal(signal.SIGUSR1, stop)
        signal.signal(signal.SIGXCPU, stop)
        signal.setitimer(signal.ITIMER_REAL, max(.001, 80 - (time.monotonic() - start_wall)))
        threading.Thread(target=watch, daemon=True).start()
        phase = "authenticate_inherited_storage"
        spec = plan["storage"]

        def load(name, ref):
            module_spec = importlib.util.spec_from_file_location(name, authenticate(ref))
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            return module

        old_helper = load("exact_chart_original_market_storage", spec["original_helper"])
        helper = load("exact_chart_next_metadata_storage", spec["helper"])
        # Keep the task package selected when the frozen loader temporarily
        # prepends its legacy library root; both use the same hash-pinned v2
        # storage implementation and shared lock context.
        sys.path.insert(0, str(BASE))
        import nfl_lab
        require(Path(nfl_lab.__file__).resolve() == BASE / "nfl_lab" / "__init__.py",
                "exact chart worktree package required")
        base = old_helper.load_frozen(str(authenticate(spec["forward_implementation"])), spec["legacy_library_root"])
        old_cls = old_helper.build_storage_class(base)
        metadata = json.loads(authenticate(spec["metadata_descriptor"]).read_bytes())
        allocation = metadata["new_finite_suballocations"]["chart_bridge"]
        require(allocation["namespace"] == DESTINATION.name
                and allocation["destination"] == str(DESTINATION)
                and allocation["retained_cap_bytes"] == caps["retained_private_bytes_cap"]
                and allocation["peak_cap_bytes"] == caps["peak_private_bytes_cap"]
                and allocation["maximum_managed_calls_including_failure"] == 1
                and allocation["fits"] == 0
                and all(allocation[k] == caps[k] for k in ("CPU_seconds", "wall_seconds", "RSS_bytes")),
                "exact separately-versioned chart bridge suballocation required")
        next_cls = helper.build_storage_class(old_cls, metadata)
        market_policy = json.loads(authenticate(spec["market_policy"]).read_bytes())
        # Existing initialized controls are a prerequisite.  Opening this lane
        # cannot create a replacement allocation or initialize another store.
        market_root = canonical(market_policy["store_policy"]["storage"]["forward_root"])
        require((market_root / "operational-forward-storage-v3" / "registry.json").is_file()
                and (market_root / "state" / "historical-market-outer-policy.json").is_file(), "preexisting inherited allocation required")
        storage = next_cls(spec["legacy_cache"], market_policy,
                           json.loads(authenticate(spec["legacy_policy"]).read_bytes()),
                           json.loads(authenticate(spec["prior_policy"]).read_bytes()))
        require(DESTINATION == storage.live_root / "research" / "next-nfl-checkpoint-chart-2026-bridge-v1",
                "inherited private research destination differs")
        before = scan()["forward_physical_bytes"]
        storage.register_root(DESTINATION)
        private_control_delta = max(0, scan()["forward_physical_bytes"] - before)
        retained_charged = prior_retained_bytes + private_control_delta
        require(private_control_delta <= 256 * 1024, "new inherited control growth exceeds reserved envelope")
        phase = "build_chart_labels"
        # Authenticate direct and transitive local imports before importing the
        # builder; the existing old scorer participates only as pinned code.
        for relative in CODE:
            require(sha(canonical(BASE / relative).read_bytes()) == go["code_sha256"][relative], "code changed before builder import")
        sys.path.insert(0, str(BASE / "tools"))
        import pyarrow as pa
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        from next_checkpoint_chart_bridge_build import build_result
        payload, summary = build_result(raw, go)
        check()
        require(type(payload) is bytes and payload[:2] == b"\x1f\x8b", "one private gzip capsule required")
        summary_body = encoded(summary)
        require(len(summary_body) <= caps["aggregate_metadata_bytes"], "safe aggregate metadata cap exceeded")
        require(summary["private_capsule_sha256"] == sha(payload)
                and summary["private_capsule_bytes"] == len(payload), "builder capsule/summary binding differs")
        phase = "managed_write_and_exact_readback"
        capsule_write("CHART_LABELS_2026_BRIDGE_COMPLETE.json.gz", payload)
        phase = "safe_aggregate_and_final_resource_check"
        with aggregate_path.open("xb") as stream:
            stream.write(summary_body)
            stream.flush()
            os.fsync(stream.fileno())
        native_write("READBACK.json", {"state": "EXACT_INHERITED_CAS_CHART_LABEL_READBACK_PASS", "capsule": capsule_ref,
            "safe_aggregate": {"path": str(aggregate_path), "bytes": len(summary_body), "sha256": sha(summary_body)}})
        for relative in CODE:
            require(sha(canonical(BASE / relative).read_bytes()) == go["code_sha256"][relative], "code changed during label build")
        scan()  # Count all native/safe metadata and the actual private result.
        use = check()  # Total invocation includes imports, CAS, and readback.
        native_write("COMPLETE.json", {"state": "CHART_LABELS_RECONSTRUCTED_NOT_PREDICTIVELY_EVALUATED",
            "continuation_version": CONTINUATION, "prior_attempt_remains_consumed": True,
            "prior_retained_private_bytes": prior_retained_bytes,
            "plan_sha256": args.sha256, "capsule": capsule_ref, "resources": use,
            "managed_write_attempts": managed_attempts, "retained_charged_bytes": retained_charged,
            "private_control_delta_bytes": private_control_delta, "predictive_fits": 0,
            "forecast_inference": 0, "accuracy_comparisons": 0, "HTTP": 0,
            "actual_model_and_reasoning": "UNATTESTED", "new_live_use": False, "offhost_restoration": "UNPROVEN"})
        check()
        print(json.dumps({"state": "COMPLETE", "native_root": str(native_root), "safe_aggregate": str(aggregate_path),
                          "capsule": capsule_ref, "resources": receipt()}, sort_keys=True))
    except BaseException as error:
        # Retention does not refund CPU/wall, source work, or the sole managed
        # publication attempt.  Replace the early watchdog with the FINAL
        # absolute90s deadline after the initial failure receipt is durable.
        stop_event.set()
        signal.setitimer(signal.ITIMER_REAL, 0)
        failure = {"state": "FAILED_CHART_LABEL_INVOCATION_RETAINED", "phase": phase,
            "continuation_version": CONTINUATION, "prior_attempt_remains_consumed": True,
            "prior_retained_private_bytes": prior_retained_bytes,
            "error_type": type(error).__name__, "error": str(error)[:2048], "plan_sha256": args.sha256,
            "resources": receipt(), "managed_write_attempts": managed_attempts,
            "retained_charged_bytes": retained_charged, "capsule": capsule_ref,
            "predictive_fits": 0, "forecast_inference": 0, "accuracy_comparisons": 0, "HTTP": 0,
            "automatic_retries": 0, "original_attempt_remains_consumed": True,
            "failure_retention_absolute_total_wall_limit_seconds": caps["wall_seconds"],
            "failure_retention_deadline_behavior": "stop without managed retry; retain this native failure receipt"}
        native_write("FAILED.json", failure)
        remaining = caps["wall_seconds"] - (time.monotonic() - start_wall)
        if remaining <= 0:
            raise  # Deadline already spent: skip all failure CAS work.
        signal.signal(signal.SIGALRM, final_retention_stop)
        signal.setitimer(signal.ITIMER_REAL, max(.001, remaining))
        if storage is not None and managed_attempts == 0:
            try:
                failed_payload = payload if payload is not None else gzip.compress(encoded(failure), mtime=0)
                capsule_write("CHART_LABELS_2026_BRIDGE_FAILED.json.gz", failed_payload)
                native_write("FAILED_RETENTION.json", {"state": "FAILED_ATTEMPT_CAPSULE_EXACT_READBACK_PASS",
                    "capsule": capsule_ref, "managed_write_attempts": managed_attempts,
                    "retained_charged_bytes": retained_charged, "resources": receipt()})
            except FinalRetentionDeadline:
                raise  # Never recurse into retention or attempt another fsync.
            except BaseException as retention_error:
                native_write("FAILED_RETENTION.json", {"state": "FAILURE_RETENTION_FAILED_PRESERVED_WITHOUT_RETRY",
                    "error_type": type(retention_error).__name__, "error": str(retention_error)[:2048],
                    "managed_write_attempts": managed_attempts, "retained_charged_bytes": retained_charged})
        raise
    finally:
        stop_event.set()
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    main()
