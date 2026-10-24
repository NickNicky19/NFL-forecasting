"""Root-sealed cached-source regeneration and one current-query feature build.

Preparation is not authority. No execution occurs on import. The only source
route is the genuine operational adapter with an explicit original source_cache.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time


def pin(reference):
    path = Path(reference["path"])
    if not path.is_absolute() or any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("canonical nonsymlink source binding required")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != reference["sha256"] or ("bytes" in reference and path.stat().st_size != reference["bytes"]):
        raise ValueError("frozen source changed")


def study_storage_class(base):
    """Add a finite study cap to the unchanged global quota prewrite gate."""
    class CurrentQueryStorage(base):
        def __init__(self, *args, study_anchor, study_bytes, **kwargs):
            self.study_anchor, self.study_bytes = study_anchor, study_bytes
            super().__init__(*args, **kwargs)

        def _require(self, incoming):
            usage = super()._require(incoming)
            delta = usage["physical_bytes"] - self.study_anchor
            if delta < 0 or delta + incoming > self.study_bytes:
                raise RuntimeError("finite additional retained source/query allocation exhausted")
            return usage
    return CurrentQueryStorage


def memory_limits(caps):
    rss = caps["RSS_bytes"]
    address = caps.get("address_space_bytes", rss)
    if not (0 < rss <= 1073741824 and rss <= address <= 1073741824):
        raise ValueError("physical RSS and virtual address limits must be explicit and bounded")
    return rss, address


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    raw = args.plan.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.plan_sha256:
        raise ValueError("exact frozen current-query plan required")
    plan = json.loads(raw)
    if (plan["state"] != "FROZEN_ROOT_REVIEWER_SEALED" or plan["schema_version"] not in {"weekly-current-query-v1", "weekly-current-query-v2"}
            or plan["review"].get("status") != "PREEXEC_PASS" or plan["review"].get("integrator") != "/root"):
        raise ValueError("prepared current-query plan is not execution authority")
    caps = plan["budgets"]
    if plan["schema_version"] == "weekly-current-query-v2" and (os.environ.get("MALLOC_ARENA_MAX") != "2" or os.environ.get("ARROW_DEFAULT_MEMORY_POOL") != "system"):
        raise ValueError("reviewed system pool and two-arena environment required before imports")
    if caps["HTTP"] != 0 or caps["feature_builds"] != 1 or not 1 <= caps["query_rows"] <= 1000:
        raise ValueError("zero-network single-build finite plan required")
    if (plan["season"] != 2026 or plan["week"] != 7 or plan["input_cutoff_utc"] != "2026-10-24T12:00:00Z"
            or plan["allowed_periods"].get("2026") != [1, 2, 3, 4, 5]):
        raise ValueError("this initial current-query version has a fixed slate and protected history window")
    begun, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (caps["CPU_seconds"], caps["CPU_seconds"]))
    rss_limit, address_limit = memory_limits(caps)
    resource.setrlimit(resource.RLIMIT_AS, (address_limit, address_limit))
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(caps["wall_seconds"])
    def no_network_or_children(event, unused):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "subprocess.Popen",
                "os.system", "os.fork", "os.forkpty", "os.exec", "os.posix_spawn"}:
            raise RuntimeError("current-query network/child route forbidden")
    sys.addaudithook(no_network_or_children)
    root = Path(__file__).resolve().parents[1]
    for name, expected in plan["code_pins"].items():
        pin(dict(path=str(root / name), sha256=expected))
    for key in ("source_policy", "source_manifest", "source_inventory", "roster", "schedule",
                "inherited_environment_attestation", "environment_preflight"):
        pin(plan[key])
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS", "OMP_THREAD_LIMIT", "ARROW_IO_THREADS"):
        os.environ[name] = "2"
    sys.path.insert(0, str(root))
    import pandas as pd
    import pyarrow as pa
    import threadpoolctl
    pa.set_cpu_count(2)
    pa.set_io_thread_count(2)
    if plan["schema_version"] == "weekly-current-query-v2":
        if plan.get("Arrow_memory_pool") != "system":
            raise ValueError("reviewed system allocator required for source continuation")
        pa.set_memory_pool(pa.system_memory_pool())
        if pa.default_memory_pool().backend_name != "system":
            raise ValueError("system Arrow allocator was not applied")
    from nfl_lab import operational_sources as source, weekly_current_query as query, weekly_future_inference as future
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.owned_reference_batch import validate_owned_references
    # Reuse the existing small process-free libc resolver; never invoke its
    # law runner or import estimators through a second resource framework.
    pin(plan["libc"])
    spec = importlib.util.spec_from_file_location("current_query_existing_thread_guard", root / "tools/ngboost_law_software_v1.py")
    thread_guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(thread_guard)
    policy = source.load_source_policy(plan["source_policy"]["path"])
    if policy["_policy_sha256"] != plan["source_contract"]["source_policy_sha256"]:
        raise ValueError("unchanged original source policy required")
    anchor = plan["retention_physical_anchor"]
    if not isinstance(anchor, int) or anchor < 0:
        raise ValueError("root must freeze actual retained-byte anchor")
    storage_type = study_storage_class(OperationalStorage)
    storage = storage_type(plan["cache"], policy, state=plan["state_root"],
        study_anchor=anchor, study_bytes=caps["additional_retained_bytes"])
    with storage.transaction():
        usage = storage.snapshot()["physical_bytes"]
        if usage < anchor:
            raise ValueError("retained evidence disappeared")
        # Original global flock/gate reserves room for the remaining allocation.
        OperationalStorage._require(storage, caps["additional_retained_bytes"] - (usage - anchor))
        output = storage.register_root(plan["output"])
        if (output / "CONSUMED.json").exists():
            raise ValueError("one current-query invocation already consumed")
        storage.atomic_json(output / "CONSUMED.json", dict(invocations=1, retries=0, plan_sha256=args.plan_sha256,
            actual_started_at=future.now_utc().isoformat(), forecasts_issued=0))

    # Never substitute the namespace/raw derived subsets for original sources.
    original = json.loads(Path(plan["source_manifest"]["path"]).read_text())
    inventory = json.loads(Path(plan["source_inventory"]["path"]).read_text())
    wanted = source._names(plan["history_seasons"])
    indexed = {item["name"]: item for item in inventory["sources"]}
    if set(indexed) != set(wanted) or sum(item["bytes"] for item in indexed.values()) > caps["source_input_bytes"]:
        raise ValueError("exact original raw-source inventory required")
    for name in wanted:
        item = indexed[name]
        expected = original["sources"][name]
        path = Path(plan["source_cache"]) / "raw" / name
        if str(path) != item["path"] or item["sha256"] != expected["sha256"] or item["receipt_sha256"] != expected["receipt_sha256"]:
            raise ValueError("original raw source/receipt destination changed")
        pin(dict(path=str(path), bytes=item["bytes"], sha256=expected["sha256"]))
        pin(dict(path=str(path) + ".receipt.json", sha256=expected["receipt_sha256"]))
    validate_owned_references(storage, {plan[key]["path"]: plan[key]["sha256"] for key in ("source_manifest", "roster", "schedule")})
    current_code = source._code_hashes()
    old_mismatches = {name: [expected, current_code[name]] for name, expected in original["code_sha256s"].items()
        if expected != current_code[name]}
    actual_asof = source._actual_now()
    cutoff = query._stamp(plan["input_cutoff_utc"])
    if actual_asof >= cutoff:
        raise ValueError("proposed input cutoff elapsed; new root-frozen slate required")
    manifest = None
    fatal = None
    def check_memory():
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > rss_limit:
            raise MemoryError("physical RSS ceiling exceeded; retained partial evidence remains")
    try:
        check_memory()
        with thread_guard.process_free_threads(threadpoolctl, plan["libc"]), threadpoolctl.threadpool_limits(limits=2):
            manifest = source.acquire_operational_history(Path(plan["cache"]), plan["history_seasons"], policy,
                actual_asof, source_cache=Path(plan["source_cache"]), allowed_periods=plan["allowed_periods"],
                state=Path(plan["state_root"]), storage=storage)
            check_memory()
            history = source.load_operational_history(Path(plan["cache"]), plan["history_seasons"], policy,
                actual_asof, allowed_periods=plan["allowed_periods"])
            check_memory()
            readback_completed = future.now_utc()
            if readback_completed >= cutoff:
                raise ValueError("actual source readback missed fixed input cutoff")
            storage.atomic_json(output / "SOURCE_READBACK.json", dict(actual_execution_asof=actual_asof.isoformat(),
                actual_readback_completed_at=readback_completed.isoformat(), original_retrieval_clocks_preserved=True,
                regenerated_namespace=manifest["namespace"], regenerated_manifest_sha256=manifest["manifest_sha256"],
                historical_availability_rule=plan["source_contract"]["availability_rule"], old_code_mismatches=old_mismatches))
            # Predicates and identity-only columns precede parquet decoding.
            roster = pd.read_parquet(plan["roster"]["path"], columns=query.ROSTER_COLUMNS,
                filters=[[("season", "==", plan["season"]), ("week", "==", plan["week"]), ("game_type", "==", "REG")]])
            schedule = pd.read_csv(plan["schedule"]["path"], usecols=query.SCHEDULE_COLUMNS)
            packet = query.build_current_queries(roster, schedule, season=plan["season"], week=plan["week"],
                cutoff_utc=cutoff, maximum_rows=caps["query_rows"], expected_remaining_games=plan["expected_remaining_games"])
            for name in ("queries", "quarantine", "no_remaining_game"):
                storage.write_dataframe(packet[name], output / (name + ".parquet"), index=False)
            storage.atomic_json(output / "POPULATION.json", packet["coverage"])
            if packet["queries"].empty:
                raise ValueError("no unambiguous current offers; retain quarantine/coverage")
            features = query.build_shared_features(history, packet, policy=policy, source_contract=plan["source_contract"])
            check_memory()
            feature_names = [name for name in features if name.startswith("f_")]
            refs = [future.binding(plan[key]["path"]) for key in ("roster", "schedule")]
            refs += [future.binding(Path(manifest["namespace"]) / name) for name in ("source-manifest.json", "processed/history.parquet")]
            feature_binding, capture_binding = future.persist_feature_capture(output / "features.parquet", features,
                features=feature_names, source_contract=plan["source_contract"], source_bindings=refs, storage=storage)
            completed = future.now_utc()
            check_memory()
            if completed >= cutoff:
                raise ValueError("actual feature persistence missed fixed input cutoff; never backdate")
            storage.atomic_json(output / "QUERY_RESULT.json", dict(state="CURRENT_QUERY_CAPTURED_NOT_ISSUED",
                coverage=packet["coverage"], feature_binding=feature_binding, capture_binding=capture_binding,
                actual_completed_at=completed.isoformat(), feature_builds=1, model_fits_predictions_scores=0,
                all_models_share_one_feature_snapshot=True, source_contract=plan["source_contract"]))
    except Exception as error:
        fatal = dict(type=type(error).__name__, message=str(error)[:500])
    terminal = dict(schema_version=plan["schema_version"], state="FAILED_RETAINED" if fatal else "CURRENT_QUERY_CAPTURED_NOT_ISSUED",
        plan_sha256=args.plan_sha256, fatal=fatal, HTTP=0, model_fits_predictions_scores=0, forecasts_issued=0,
        CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-begun,
        RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        additional_retained_bytes_before_terminal=storage.snapshot()["physical_bytes"]-anchor,
        actual_execution_asof=actual_asof.isoformat(), fixed_input_cutoff=cutoff.isoformat(),
        current_vintage_availability_uncertain=True, upstream_publication="NOT_INFERRED")
    storage.atomic_json(output / "FINISHED.json", terminal)
    print(json.dumps({name: terminal[name] for name in ("state", "HTTP", "CPU_seconds", "wall_seconds", "forecasts_issued")}))
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
