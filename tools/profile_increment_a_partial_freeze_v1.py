"""Freeze exactly the three returned native arms; defense remains unexecuted.

No fit, model deserialization, predictive inference, label read or scoring. An
explicit published root GO is required before any forecast array is decoded.
"""
from __future__ import annotations
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
VERSION = "PROFILE-INCREMENT-TO-RELEASE-01-A-v2"
WORKER = "A::PROFILE-INCREMENT-v2-named-three-arm-freeze-v1"
ARMS = ["RB_ONLY_LEAF_BASE", "R1_RB_ONLY_LEAF_SUPPORT", "R2_RB_ONLY_LEAF_PLAYER_OFFENSE"]
PENDING = ["R3_RB_ONLY_LEAF_DEFENSE"]
KEY = ["season", "week", "game_id", "player_id"]
FAILURE = dict(id="FAILURE_PRIVATE_PILOT_RESUME_V5.json", bytes=3799,
    sha256="ca3a7dc0f99d533e0239bee39f336ed9ae3a4eda743f28f6cf142d9744214340")
FAILURE_UTC = "2026-11-10T13:07:58.895163+00:00"
MANIFEST_ID = "PARTIAL_R0_R2_FORECAST_PART_MANIFEST_BEFORE_LABELS_V1.json.gz"
RECEIPT_ID = "PARTIAL_R0_R2_EXECUTION_RECEIPT_V1.json"
PHASE = "NOT_STARTED"

def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()

def sha(body):
    return hashlib.sha256(body).hexdigest()

def check(value, message):
    if not value:
        raise ValueError(message)

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value

def identity(row):
    return int(row["season"]), int(row["week"]), str(row["game_id"]), str(row["player_id"])

def run(args):
    global PHASE
    start, cpu = time.monotonic(), time.process_time()
    raw = args.protocol.read_bytes()
    check(sha(raw) == args.protocol_sha256, "published partial-freeze protocol differs")
    plan = json.loads(raw)
    check(plan.get("worker") == WORKER and plan.get("version") == VERSION
          and plan.get("state") == "ROOT_REGISTERED_PARTIAL_FREEZE_GO"
          and plan.get("registered_by") == "/root", "explicit root partial-freeze GO required")
    check(plan.get("completed_arms") == ARMS and plan.get("pending_arms") == PENDING
          and plan.get("failure_ref") == FAILURE and plan.get("expected_query_rows") == 1364,
          "three-arm metadata/source census differs")
    caps = dict(CPU_seconds=400, wall_seconds=900, RSS_bytes=3*1024**3, private_view_max_bytes=131072)
    check(plan.get("resources") == caps, "finite source/scoring envelope differs")
    for path, digest in plan["code_sha256"].items():
        check(sha((ROOT/path).read_bytes()) == digest, "bound local source differs: "+path)
    check(plan["code_sha256"].get(str(Path(__file__).relative_to(ROOT))) == sha(Path(__file__).read_bytes()),
          "executing freeze worker must be hash bound")
    resource.setrlimit(resource.RLIMIT_CPU, (400, 400))
    resource.setrlimit(resource.RLIMIT_AS, (caps["RSS_bytes"],)*2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("bounded native partial freeze")))
    signal.alarm(900)
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[name] = "1"
    def offline(event, _):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("partial freeze is native saved-byte only")
    sys.addaudithook(offline)
    PHASE = "NATIVE_ADMISSION_AND_TERMINAL_FAILURE_AUTHENTICATION"
    guard = module("nfl_lab.profile_increment_a_storage_v2", "nfl_lab/profile_increment_a_storage_v2.py")
    store = guard.ProfileIncrementStore(ROOT, plan["allocation"]["path"], plan["allocation"]["sha256"], root_go=guard.GO)
    fraw = store.read(FAILURE["id"], FAILURE["sha256"])
    check(len(fraw) == FAILURE["bytes"], "terminal native failure size differs")
    failure = json.loads(fraw)
    check(failure["version"] == VERSION and failure["state"] == "FAILED_RETAINED_NO_AUTOMATIC_REFIT"
          and failure["UTC"] == FAILURE_UTC and failure["fits_attempted"] == failure["fits_returned"] == 3
          and failure["phase"] == "INFERENCE_R2_RB_ONLY_LEAF_PLAYER_OFFENSE"
          and failure["error_sha256"] == "af6935bc282503b3253a8f2d30c066385972d845bc166f9d9882b41496ea0023",
          "actual V5 terminal proof differs; file existence is insufficient")
    check('store.reserve(plan["resources"]["first_model_max_bytes"])' in failure["traceback"]
          and "new retained reservation exhausted before fit/write" in failure["traceback"],
          "R3 resource-reservation failure is not established by the exact terminal proof")
    refs = {r["id"]: r for r in failure["artifacts"]}
    check(len(refs) == len(failure["artifacts"]), "terminal artifact identities ambiguous")
    check(not any("R3_RB_ONLY_LEAF_DEFENSE" in name or name == "FIT_4_CONSUMED.json" for name in refs),
          "pending defense artifact/fit unexpectedly exists in terminal proof")
    for expected in plan["source_artifacts"]:
        check(refs.get(expected["id"]) == expected, "root source artifact differs from actual terminal proof")
    PHASE = "THREE_NATIVE_MODELS_HASH_ONLY_NO_DESERIALIZATION"
    models = {}
    for arm in ARMS:
        ref = refs["MODEL_2026_"+arm+".joblib"]
        body = store.read(ref["id"], ref["sha256"])
        check(len(body) == ref["bytes"], "returned model native size differs")
        models[arm] = dict(ref)
        del body
    PHASE = "THREE_NATIVE_COMPLETE_PARTS_NO_LABELS_OR_SCORES"
    all_rows, part_refs, first_keys = [], [], None
    for arm in ARMS:
        ref = refs["FORECAST_2026_"+arm+".json.gz"]
        body = store.read(ref["id"], ref["sha256"])
        check(len(body) == ref["bytes"], "native forecast-part size differs")
        rows = json.loads(gzip.decompress(body))
        check(isinstance(rows, list) and len(rows) == plan["expected_query_rows"], "complete part query census differs")
        check(all(r["arm"] == arm and r["target"] == "rush_yd" and r["position"] == "RB"
                  and r.get("original_issued_UTC") is None and r.get("conditioning") == "CONDITIONAL_ON_PLAYED"
                  and r.get("reconstruction") == "CURRENT_VINTAGE_SEVEN_DAY_POLICY_EXPOSED_HISTORY" for r in rows),
              "named native part recipe/role/issuance differs")
        keys = [identity(r) for r in rows]
        check(len(set(keys)) == len(keys), "duplicate native forecast player-game")
        check(first_keys is None or keys == first_keys, "completed parts do not preserve the same ordered query population")
        if first_keys is None:
            first_keys = keys
        part_refs.append(dict(ref, arm=arm, rows=len(rows)))
        all_rows.extend(rows)
    recovery_ref = refs["QUERY_RECOVERY_BINDING_V5.json"]
    recovery_raw = store.read(recovery_ref["id"], recovery_ref["sha256"])
    check(len(recovery_raw) == recovery_ref["bytes"], "query recovery metadata size differs")
    recovery = json.loads(recovery_raw)
    check(recovery["rows"] == 1364 and recovery["target_outcomes_to_inference"] is False
          and recovery["new_query_profiles"] == recovery["new_defense_snapshots"] == 0
          and recovery["original_base"] == refs["QUERY_BASE_INPUTS_RECOVERED_V5.parquet"],
          "completed saved-query recovery proof differs")
    binding_ref = refs["SOURCE_AND_PROFILE_BINDING.json"]
    binding_raw = store.read(binding_ref["id"], binding_ref["sha256"])
    check(len(binding_raw) == binding_ref["bytes"], "source/profile binding size differs")
    source_binding = json.loads(binding_raw)
    check(source_binding["query_rows"] == 1364, "original source/profile query census differs")
    logical = sha(enc(all_rows))
    manifest = dict(format="IMMUTABLE_ORDERED_PART_MANIFEST_V1", version=VERSION, arm_order=ARMS,
        parts=part_refs, rows=len(all_rows), logical_combined_sha256=logical,
        logical_codec="JSON_sorted_keys_compact_allow_nan_false_newline; concatenate decoded part arrays in arm_order",
        completed_arms=ARMS, pending_arms=PENDING, pending_state="RESOURCE_PENDING",
        source_terminal_failure=FAILURE, source_fit_protocol_sha256="eab567f278d46faf408c948d6a08abc43b096c078203ceda23e6b1633864e8cf")
    PHASE = "NATIVE_NAMED_THREE_ARM_MANIFEST_PERSISTENCE"
    body = gzip.compress(enc(manifest), mtime=0)
    check(len(body) <= 16384, "small ordered manifest exceeded registered source-only scope")
    frozen = store.put(MANIFEST_ID, body)
    check(store.read(frozen["id"], frozen["sha256"]) == body, "partial manifest native readback differs")
    receipt = dict(version=VERSION, worker=WORKER, state="FROZEN_NAMED_THREE_ARMS_DEFENSE_PENDING",
        UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), protocol_sha256=args.protocol_sha256,
        source_terminal_failure=FAILURE, preserved_failure_UTC=failure["UTC"],
        completed_arms=ARMS, pending_arms=PENDING, pending_state="RESOURCE_PENDING",
        fits_attempted=failure["fits_attempted"], fits_returned=failure["fits_returned"],
        preserved_original_model_fit_CPU_seconds=failure["model_fit_CPU_seconds"],
        new_fits=0, new_model_loads=0, new_inference=0, new_original_issuances=0, new_label_reads=0, new_scores=0,
        models=models, forecasts=frozen, forecasts_format="IMMUTABLE_ORDERED_PART_MANIFEST_V1",
        forecast_rows=len(all_rows), query_rows=1364, forecast_query_weeks=sorted({int(r["week"]) for r in all_rows}),
        query_identity_sha256=sha(enc([list(k) for k in first_keys])), logical_combined_sha256=logical,
        artifacts=failure["artifacts"]+[frozen], source_and_profile_binding=source_binding,
        partial_scope="Exactly saved R0/R1/R2; no R3 fit/forecast or defense-effect result. Original V5 failure remains retained.",
        scoring_state="UNSCORED_REQUIRE_SEPARATE_PUBLISHED_ROOT_GO_AND_PINNED_CANONICAL_EVALUATOR",
        model_verification="Native exact bytes/hash only; no unsafe loading or fresh-fit reproduction claimed.",
        storage=store.checkpoint(), resources=dict(CPU_seconds=time.process_time()-cpu,
            wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    PHASE = "NATIVE_PARTIAL_RECEIPT_PERSISTENCE"
    receipt_body = enc(receipt)
    check(len(receipt_body) <= 32768, "bounded partial metadata receipt exceeded scope")
    private = store.put(RECEIPT_ID, receipt_body)
    check(store.read(private["id"], private["sha256"]) == receipt_body, "partial receipt native readback differs")
    with args.output.open("xb") as f:
        f.write(receipt_body); f.flush(); os.fsync(f.fileno())
    signal.alarm(0)
    print(json.dumps(dict(state=receipt["state"], output=str(args.output), receipt_sha256=sha(receipt_body),
        partial_manifest=frozen, model_hashes_verified=3, forecast_rows=len(all_rows), new_fits=0, new_inference=0, new_scores=0)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--protocol-sha256", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    check(not args.output.exists(), "immutable public partial receipt already exists")
    try:
        run(args)
    except BaseException as error:
        signal.alarm(0)
        failure = dict(worker=WORKER, state="PARTIAL_FREEZE_FAILED_EVIDENCE_PRESERVED", phase=PHASE,
            UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), protocol_sha256=args.protocol_sha256,
            error_type=type(error).__name__, error_sha256=sha(str(error).encode()), automatic_retry=False,
            new_fits=0,new_inference=0,new_scores=0)
        p=args.output.with_name("PARTIAL_FREEZE_FAILURE_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
        with p.open("xb") as f:f.write(enc(failure))
        print(json.dumps(failure))
        raise SystemExit(1) from None

if __name__ == "__main__":
    main()
