"""Bounded annual training and immutable export for actual future queries.

This is not an accuracy study and issues no forecasts. Frozen historical
query artifacts and original scientific studies are unchanged.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import resource
import signal
import sys
import time


@contextmanager
def cooperative_fit_deadline(seconds):
    """Python alarm; native code may defer it. Whole process has a hard timeout."""
    previous = signal.getitimer(signal.ITIMER_REAL)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    begun = time.monotonic()
    try:
        yield
    finally:
        left = previous[0] - (time.monotonic() - begun)
        signal.setitimer(signal.ITIMER_REAL, max(.001, left) if previous[0] else 0)


def regular_game_ids(schedule):
    """Authenticate period by schedule identity, never by an absent stat field."""
    required = {"season", "game_id", "game_type"}
    if not required <= set(schedule) or schedule.game_id.isna().any() or schedule.duplicated(["game_id"]).any():
        raise ValueError("unambiguous schedule period identities required")
    selected = schedule.loc[schedule.season.between(2019, 2025) & schedule.game_type.eq("REG")]
    if selected.empty:
        raise ValueError("no supported regular-season games")
    return selected.game_id.tolist()


def category_contracts(document):
    return {t: dict(c, target=t) for t, c in document["categories"].items() if c["state"] == "READY"}


def training_columns(categories, identity):
    return list(dict.fromkeys(identity + ["participation_state", "outcome_available_utc",
        "feature_max_source_available_utc", "f_player_games_prior", "rush_td", "rec_td"]
        + list(categories) + [f for c in categories.values() for f in c["panels"]["base"]]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    raw = args.plan.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.plan_sha256:
        raise ValueError("exact root training plan required")
    plan = json.loads(raw)
    if plan["state"] != "FROZEN_ROOT_REVIEWER_SEALED":
        raise ValueError("prepared plan is not execution authority")
    caps = plan["budgets"]
    started, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (caps["CPU_seconds"], caps["CPU_seconds"]))
    def expired(*unused):
        raise TimeoutError("frozen fit or whole training deadline")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, caps["wall_seconds"])
    def no_network(event, unused):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("zero network training")
    sys.addaudithook(no_network)
    root = Path(__file__).resolve().parents[1]
    for name, expected in plan["code_pins"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError("training source changed: " + name)
    import pandas as pd
    from threadpoolctl import threadpool_limits
    sys.path.insert(0, str(root))
    from nfl_lab import weekly_future_inference as w
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.owned_reference_batch import validate_owned_references
    policy_raw = Path(plan["source_policy"]["path"]).read_bytes()
    if hashlib.sha256(policy_raw).hexdigest() != plan["source_policy"]["sha256"]:
        raise ValueError("source policy changed")
    storage = OperationalStorage(plan["cache"], json.loads(policy_raw), state=plan["state_root"])
    output = storage.register_root(plan["output"])
    if (output / "CONSUMED.json").exists():
        raise ValueError("single training invocation already consumed")
    observed_entry = storage.snapshot()["physical_bytes"]
    physical_at_entry = plan.get("retention_physical_anchor", observed_entry)
    if type(physical_at_entry) is not int or not 0 < physical_at_entry <= observed_entry:
        raise ValueError("retained continuation anchor invalid")
    storage.atomic_json(output / "CONSUMED.json", dict(plan_sha256=args.plan_sha256, started_at=w.now_utc().isoformat(),
                                                     physical_at_entry=physical_at_entry))
    refs = [plan["features"], plan["source_manifest"], plan["schedule"]]
    validate_owned_references(storage, {b["path"]: b["sha256"] for b in refs})
    restored_at = w.now_utc().isoformat()
    storage.atomic_json(output / "SOURCE_READBACK.json", dict(actual_local_restore_completed_at=restored_at,
        original_sources=refs, upstream_publication="NOT_INFERRED", semantics="Authenticated current local readback; original retrieval vintages retained"))
    category_body = Path(plan["categories"]["path"]).read_bytes()
    if hashlib.sha256(category_body).hexdigest() != plan["categories"]["sha256"]:
        raise ValueError("category contract changed")
    categories = category_contracts(json.loads(category_body))
    for category in categories.values():
        w.cdf.validate_category(category)
    columns = training_columns(categories, w.IDENTITY)
    schedule = pd.read_csv(plan["schedule"]["path"], usecols=["season", "game_id", "game_type"])
    allowed_games = regular_game_ids(schedule)
    frame = pd.read_parquet(plan["features"]["path"], columns=columns,
                           filters=[("season", ">=", 2019), ("season", "<=", 2025), ("game_id", "in", allowed_games)])
    # Existing accepted REG source view; no new source or participation repair.
    if not (frame.season.between(2019, 2025) & frame.game_id.isin(allowed_games)).all():
        raise ValueError("Parquet returned rows outside supported regular-season identities")
    train = frame.copy()
    del frame
    cutoff = pd.Timestamp(plan["training_cutoff_utc"])
    good_clock = pd.to_datetime(train.outcome_available_utc, utc=True, errors="coerce")
    train = train.loc[good_clock.notna() & (good_clock < cutoff)].copy()
    if not len(train):
        raise ValueError("no qualified earlier training rows")
    w.cdf.assert_clock_contract(train)
    for job in plan["jobs"]:
        w.cdf.assert_composite_contract(train, categories[job["target"]])
    slots, attempts, model_bytes = [], 0, 0
    def fit_gate(info):
        nonlocal attempts
        if attempts >= caps["fit_attempts"]:
            raise RuntimeError("finite fit allocation exhausted")
        attempts += 1
        storage.atomic_json(output / f"attempt-{attempts:02}.json", dict(info, charged=True, at=w.now_utc().isoformat()))
    def check():
        if (time.process_time()-cpu >= caps["CPU_seconds"]-20 or time.monotonic()-started >= caps["wall_seconds"]-20
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 >= caps["RSS_bytes"]):
            raise RuntimeError("training resource ceiling; preserve completed slots")
    def export_one(model, category, job):
        # The original storage flock makes the additional study admission
        # atomic with its writes. Failed bodies remain charged on the next call.
        with storage.transaction():
            retained_delta = storage.snapshot()["physical_bytes"] - physical_at_entry
            if retained_delta < 0:
                raise RuntimeError("retained evidence disappeared")
            fixture = pd.concat([train.head(2), train.loc[train.position.isin(category["modeled_roles"])
                & train.f_player_games_prior.gt(0)].tail(2)]).drop_duplicates(w.cdf.KEYS)
            ref = w.export_trained_artifact(output / job["target"] / job["family"], model,
                family=job["family"], method_id=job["method_id"], training_frame=train,
                training_cutoff_utc=plan["training_cutoff_utc"], source_contract=plan["source_contract"],
                training_sources=refs, replay_fixture=fixture, storage=storage,
                maximum_serialized_bytes=caps["model_bytes"]-retained_delta)
            if storage.snapshot()["physical_bytes"] - physical_at_entry > caps["model_bytes"]:
                raise RuntimeError("retained training allocation exceeded; preserve failed body")
            return ref
    fatal = None
    try:
        with threadpool_limits(limits=2):
            for job in plan["jobs"]:
                check()
                category = categories[job["target"]]
                slot = dict(job, state="STARTED")
                slots.append(slot)
                try:
                    with cooperative_fit_deadline(min(caps["per_fit_cooperative_wall_seconds"], caps["wall_seconds"]-20-(time.monotonic()-started))):
                        model = w.fit_future_model(train, category, job["family"],
                            training_cutoff_utc=plan["training_cutoff_utc"], fit_gate=fit_gate,
                            training_source_capture_completed_at=restored_at,
                            expected_native_version=plan["catboost_version"] if job["family"] == "catboost_medium" else None)
                    check()
                    ref = export_one(model, category, job)
                    manifest = json.loads(Path(ref["path"]).read_text())
                    model_bytes += ref["bytes"] + manifest["model"]["bytes"]
                    slot.update(state="FUTURE_ARTIFACT_EXPORTED", artifact=ref,
                                model_bytes=manifest["model"]["bytes"], fit_receipt=manifest["fit_receipt"])
                    del model
                    print(json.dumps(dict(target=job["target"], family=job["family"], state=slot["state"],
                                          charged_attempts=attempts, model_bytes=model_bytes)), flush=True)
                except (TimeoutError, ValueError, RuntimeError) as error:
                    slot.update(state="FAILED_RETAINED", error_type=type(error).__name__, error=str(error)[:300])
                    if time.monotonic()-started >= caps["wall_seconds"]-20:
                        raise
                storage.atomic_json(output / f"slot-{len(slots):02}.json", slot)
                if storage.snapshot()["physical_bytes"] - physical_at_entry > caps["model_bytes"]:
                    raise RuntimeError("all-retained training allocation exceeded; preserve failures")
                check()
        # Reload in a separate process is a later runtime acceptance check.
    except Exception as error:
        fatal = dict(error_type=type(error).__name__, error=str(error)[:300])
    exported = sum(s["state"] == "FUTURE_ARTIFACT_EXPORTED" for s in slots)
    run_state = ("FAILED_RETAINED" if fatal else "COMPLETED" if exported == len(plan["jobs"])
                 else "COMPLETED_WITH_SLOT_FAILURES")
    result = dict(schema_version=plan["schema_version"], state=run_state, plan_sha256=args.plan_sha256, slots=slots,
                  charged_fit_attempts=attempts, retained_model_bytes=model_bytes, fatal=fatal,
                  CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started,
                  RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                  retained_all_bytes_before_terminal=storage.snapshot()["physical_bytes"]-physical_at_entry,
                  HTTP=0, forecasts_issued=0, accuracy_scores=0, scientific_qualification=False,
                  exact_PPR="BLOCKED_LABEL_CONTRACT", source_contract=plan["source_contract"])
    with storage.transaction():
        encoded = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
        if storage.snapshot()["physical_bytes"]-physical_at_entry+len(encoded) > caps["model_bytes"]:
            raise RuntimeError("terminal receipt exceeds all-retained allocation")
        storage.write_bytes(output / "FINISHED.json", encoded)
    signal.setitimer(signal.ITIMER_REAL, 0)
    print(json.dumps(dict(state=run_state, fits=attempts,
                         exported=exported,
                         CPU_seconds=result["CPU_seconds"], wall_seconds=result["wall_seconds"],
                         model_bytes=model_bytes, fatal=fatal)))
    return 0 if run_state == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
