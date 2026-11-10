"""Four fixed Leaf-CDF fits on A's retained 2026 RB queries; offline only.

This executable freezes forecasts/laws before any new score. It reuses accepted
source/audit/profile evidence and performs no deployment, collection or grading.
Every fit slot is consumed before fitting and a returned model is saved first.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
VERSION = "PROFILE-INCREMENT-TO-RELEASE-01-A-v2"
KEY = ["season", "week", "game_id", "player_id"]
CTX = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
ARMS = ["RB_ONLY_LEAF_BASE", "R1_RB_ONLY_LEAF_SUPPORT", "R2_RB_ONLY_LEAF_PLAYER_OFFENSE", "R3_RB_ONLY_LEAF_DEFENSE"]
STATE = dict(phase="NOT_STARTED", fits_attempted=0, fits_returned=0, fit_CPU_seconds=0., artifacts=[], models={}, forecast_parts=[])


def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def ref_bytes(ref):
    path = Path(ref["path"])
    body = path.read_bytes()
    if len(body) != ref["bytes"] or sha(body) != ref["sha256"]:
        raise ValueError("bound metadata/source changed: " + path.name)
    return body


def local_module(name, relative_path):
    """Load exact registered local code despite frozen-library sys.path edits."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def safe(ref):
    return {k: v for k, v in ref.items() if k not in {"path", "relative_path", "native_root"}}


def authorize(args):
    raw = args.protocol.read_bytes()
    if sha(raw) != args.protocol_sha256:
        raise ValueError("exact root protocol digest required")
    plan = json.loads(raw)
    go = json.loads(ref_bytes(dict(path=str(args.root_go), bytes=args.root_go.stat().st_size,
                                 sha256=args.root_go_sha256)))
    if (plan.get("version") != VERSION or plan.get("state") != "ROOT_REGISTERED_EXECUTION_GO"
            or go.get("state") != "ROOT_AND_INDEPENDENT_GO"
            or go.get("registered_by") != "/root" or go.get("protocol_sha256") != args.protocol_sha256):
        raise ValueError("root and independent GO for these exact bytes required")
    if plan.get("arms") != ARMS or plan.get("maximum_new_fits") != 4 or plan.get("seasons") != [2026]:
        raise ValueError("finite 2026 four-fit recipe changed")
    expected = dict(CPU_seconds=2000, wall_seconds=3600, RSS_bytes=3 * 1024**3,
                    threads=2, first_model_max_bytes=3 * 1024**2,
                    failure_reserve_bytes=2 * 1024**2)
    if plan.get("resources") != expected:
        raise ValueError("exact finite execution envelope required")
    for path, expected_hash in plan["code_sha256"].items():
        if sha((ROOT / path).read_bytes()) != expected_hash:
            raise ValueError("registered source changed: " + path)
    for path, expected_hash in plan["source_configuration_sha256"].items():
        if sha((ROOT / path).read_bytes()) != expected_hash:
            raise ValueError("registered source configuration changed: " + path)
    publication = json.loads(ref_bytes(dict(path=str(args.publication_receipt),
        bytes=args.publication_receipt.stat().st_size, sha256=args.publication_receipt_sha256)))
    if publication.get("state") != "PUBLICATION_COMPLETE":
        raise ValueError("actual pre-execution publication/readback required")
    STATE["plan_raw"] = raw
    return plan


def runtime(plan):
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[variable] = "2"
    budget = plan["resources"]
    # Conservative hard enforcement of the existing1200CPU training ceiling:
    # include all source/accounting overhead rather than allowing one fit to
    # overrun a stop-between-fits counter. Registered outer maximum is2000.
    resource.setrlimit(resource.RLIMIT_CPU, (1100, 1200))
    resource.setrlimit(resource.RLIMIT_AS, (budget["RSS_bytes"],) * 2)
    def exhausted(signum, _frame):
        if signum == signal.SIGXCPU:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise TimeoutError("finite profile increment runtime; failure retention reserved")
    signal.signal(signal.SIGXCPU, exhausted)
    signal.signal(signal.SIGALRM, exhausted)
    signal.signal(signal.SIGTERM, exhausted)
    signal.alarm(budget["wall_seconds"] - 120)
    def offline(event, _args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("zero-network retained-source increment")
    sys.addaudithook(offline)
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(2)
    pa.set_io_thread_count(1)
    pa.set_memory_pool(pa.system_memory_pool())
    return np, pd


def mixed_utc(series, pd):
    """Parse each retained aware clock, preserving mixed ISO separator formats."""
    values = series.map(lambda v: pd.Timestamp(v) if pd.notna(v) else pd.NaT)
    if any(pd.notna(v) and v.tzinfo is None for v in values):
        raise ValueError("naive historical clock cannot be authenticated")
    return pd.to_datetime(values, utc=True)


def identity(row):
    return {k: int(getattr(row, k)) if k in {"season", "week"} else str(getattr(row, k)) for k in KEY + CTX}


def run(plan, public_receipt):
    start, cpu = time.monotonic(), time.process_time()
    np, pd = runtime(plan)
    import joblib
    from threadpoolctl import threadpool_limits
    from nfl_lab import cdf_engine as cdf, player_context_rush_efficiency_v1 as core
    increment = local_module("nfl_lab.profile_increment_a_v2", "nfl_lab/profile_increment_a_v2.py")
    guard = local_module("nfl_lab.profile_increment_a_storage_v2", "nfl_lab/profile_increment_a_storage_v2.py")
    old = local_module("tools.player_context_completion_efficiency_v1", "tools/player_context_completion_efficiency_v1.py")
    carry = local_module("tools.abc_a_dynamic_carry_wave_v1", "tools/abc_a_dynamic_carry_wave_v1.py")
    increment.verify_partition()
    if cdf.TREE_PARAMETERS != dict(n_estimators=32, criterion="squared_error", max_depth=8,
        min_samples_leaf=30, max_features=1.0, bootstrap=False, random_state=1701, n_jobs=2) or cdf.PRIOR_WEIGHT != .05:
        raise ValueError("strong fixed Leaf-CDF recipe changed")
    store = guard.ProfileIncrementStore(ROOT, plan["allocation"]["path"], plan["allocation"]["sha256"], root_go=guard.GO)
    STATE.update(store=store, phase="ADMISSION")
    def put(name, body, failure=False):
        ref = store.put(name, body, failure=failure)
        STATE["artifacts"].append(ref)
        return ref
    def save_model(name, model, failure=False):
        STATE["pending_model_object"] = model
        stream = io.BytesIO()
        joblib.dump(model, stream, compress=("xz", 3))
        STATE["pending_model_bytes"] = stream.getvalue()
        ref = put(name, stream.getvalue(), failure=failure)
        store.read(name, ref["sha256"])
        STATE.pop("pending_model_bytes", None)
        STATE.pop("pending_model_object", None)
        return ref
    try:
        recovery = plan.get("saved_pilot_resume", {})
        if (recovery.get("previous_fits_attempted") != 1 or recovery.get("previous_fits_returned") != 1
                or recovery.get("remaining_new_fits") != 3 or recovery.get("attempt_id") != "SAVED_PILOT_REMAINING_THREE_V5"):
            raise ValueError("exact one-returned-pilot/three-remaining root acknowledgment required")
        expected_model = "MODEL_2026_RB_ONLY_LEAF_BASE.joblib"
        if ({p.name for p in store.destination.glob("MODEL*")} != {expected_model}
                or {p.name for p in store.destination.glob("FIT_*_CONSUMED.json")} != {"FIT_1_CONSUMED.json"}):
            raise ValueError("saved pilot resume requires exactly one consumed/returned model")
        saved_refs = {ref["id"]: ref for ref in recovery["artifacts"]}
        required_saved = {expected_model, "FIT_1_CONSUMED.json", "PILOT_RESOURCE_RECEIPT.json",
            "BASIC_PROFILES_AND_COHORTS_2026.json.gz", "UNAVAILABLE_PROFILES_2026_W8.json.gz",
            "QUERY_PROFILE_INPUTS_2026.parquet", "SOURCE_AND_PROFILE_BINDING.json",
            "ALL32_RUSHING_DEFENSE_SNAPSHOTS_2026.json.gz", "FAILURE_PRIVATE_BOUNDARY_V4.json"}
        if required_saved-set(saved_refs):
            raise ValueError("complete immutable saved-source/pilot bindings required")
        saved_bodies = {name: store.read(name,saved_refs[name]["sha256"]) for name in sorted(required_saved)}
        if any(len(saved_bodies[name]) != saved_refs[name]["bytes"] for name in required_saved):
            raise ValueError("saved pilot/source readback size changed")
        if (saved_refs[expected_model]["sha256"] != "774abed507ffe585b5414ba5d153ea2c8fb9af96bad863d5d08fff68e41a85be"
                or saved_refs[expected_model]["bytes"] != 686740):
            raise ValueError("exact returned original pilot is required, never refit")
        event = json.loads(saved_bodies["FIT_1_CONSUMED.json"])
        if event["arm"] != ARMS[0] or event["attempt"] != 1:
            raise ValueError("original first fit consumption differs")
        prior_failure = json.loads(saved_bodies["FAILURE_PRIVATE_BOUNDARY_V4.json"])
        if (prior_failure["fits_attempted"] != 1 or prior_failure["fits_returned"] != 1
                or abs(prior_failure["model_fit_CPU_seconds"]-recovery["previous_fit_CPU_seconds"]) > 1e-9):
            raise ValueError("previous consumed fit/CPU evidence differs")
        STATE.update(fits_attempted=1, fits_returned=1, fit_CPU_seconds=recovery["previous_fit_CPU_seconds"])
        STATE["models"][ARMS[0]] = saved_refs[expected_model]
        STATE["artifacts"].extend(saved_refs[name] for name in sorted(required_saved))
        put("CONSUMED_SAVED_PILOT_RESUME_V5.json", enc(dict(version=VERSION, UTC=now(),
            state="EXPLICIT_ROOT_RESUME_SAVED_PILOT_NO_REFIT", previous_fits_attempted=1,
            previous_fits_returned=1, remaining_new_fits=3, original_model=saved_refs[expected_model], no_automatic_retry=True)))
        put("PRIVATE_EXECUTION_PLAN_SAVED_PILOT_RESUME_V5.json", STATE.pop("plan_raw"))
        data = old.load_inputs(pd)
        audit = old.audited_feature_binding(data)
        put("REUSED_AUDIT_BINDING.json", enc(audit))
        # Existing 196-tendency profiles are retained, not rebuilt merely for
        # presentation. Reference authentication uses native prior readback.
        profile_ref = plan["existing_profiles_2026"]
        profile_path = store.prior.forward_root / "research" / guard.OLD_VERSION / profile_ref["id"]
        store.prior.validate_reference(profile_path, profile_ref["sha256"])
        if profile_path.stat().st_size != profile_ref["bytes"]:
            raise ValueError("existing profile artifact changed")
        reused_profile_binding = safe(profile_ref)
        source_context = core.EfficiencyContext(data["frames"], data["history"])
        q = data["queries"][2026].copy()
        w8, w8_census, unavailable = old.week8_queries(data, pd, build_features=True)
        q = pd.concat([q, w8], ignore_index=True)
        for col in ("kickoff_utc", "cutoff_utc"):
            q[col] = mixed_utc(q[col], pd)
        if not q.position.eq("RB").all() or q.duplicated(KEY).any() or not q.participation_state.eq("unknown").all():
            raise ValueError("full RB query identity/outcome separation changed")
        if plan.get("historical_boundary_contract") != "HISTORICAL_AT_KICKOFF_RECONSTRUCTION":
            raise ValueError("explicit source-matched historical boundary contract required")
        if (q.cutoff_utc > q.kickoff_utc).any():
            raise ValueError("post-kickoff query cannot enter eligible historical inference")
        tied = q.cutoff_utc.eq(q.kickoff_utc)
        if (tied & ~q.week.between(1,7)).any() or (q.week.eq(8) & q.cutoff_utc.ge(q.kickoff_utc)).any():
            raise ValueError("captured W8 must remain strictly before kickoff")
        if int(tied.sum()) != 1244 or int((~tied).sum()) != 120:
            raise ValueError("bound original query-clock census changed")
        q["query_clock_contract"] = np.where(tied, "HISTORICAL_AT_KICKOFF_RECONSTRUCTION", "CAPTURED_PRE_KICKOFF_BOARD_RECONSTRUCTION")
        q["query_evidence_tier"] = np.where(tied,
            "ASOF_AT_KICKOFF_RECONSTRUCTION_NOT_ISSUED_SOURCE_ROW_CONDITIONAL",
            "ORIGINAL_BOARD_MEMBERSHIP_WITH_LATER_MODEL_RECONSTRUCTION_NOT_ORIGINAL_MODEL_ISSUANCE")
        # Drop all target labels before augmentation/inference. Upcoming queries
        # deliberately have no known outcome-availability clock.
        for label in ("rush_yd", "rush_att", "actual", "prediction", "point"):
            if label in q:
                q[label] = np.nan
        q["outcome_available_utc"] = pd.NaT
        train = increment.rb_training_population(data["train"])
        fitcut = pd.Timestamp("2026-09-01", tz="UTC")
        train = train.loc[train.season.lt(2026) & (mixed_utc(train.outcome_available_utc, pd) < fitcut)].copy().reset_index(drop=True)
        if train.empty or mixed_utc(train.outcome_available_utc, pd).isna().any():
            raise ValueError("explicit unknown/empty historical training labels")
        STATE["phase"] = "EARLIER_PROFILE_TRANSFORM"
        augmented, _ = source_context.augment(train, rich=False)
        if not train.position.eq("RB").all():
            raise ValueError("non-RB rows entered prior or design fitting")
        # Saved PCE inputs are restored, never recomputed for these queries.
        # Only original30 base fields are joined/reconstructed under the already
        # audited source adapter because the earlier PCE-only file omitted them.
        saved_query = pd.read_parquet(io.BytesIO(saved_bodies["QUERY_PROFILE_INPUTS_2026.parquet"]))
        for col in ("kickoff_utc", "cutoff_utc", "feature_max_source_available_utc"):
            saved_query[col] = mixed_utc(saved_query[col], pd)
        if saved_query.duplicated(KEY).any() or len(saved_query) != len(q):
            raise ValueError("saved query PCE identity census changed")
        base_columns = data["category"]["panels"]["base"]
        base_query = q[KEY+CTX+base_columns+["feature_max_source_available_utc", "query_clock_contract", "query_evidence_tier", "participation_state"]].copy()
        base_query.rename(columns={"feature_max_source_available_utc":"base_feature_clock"},inplace=True)
        qaug = base_query.merge(saved_query, on=KEY+CTX, how="inner", validate="one_to_one", sort=False)
        if len(qaug) != len(q) or not set(core.EFFICIENCY_FEATURES) <= set(qaug):
            raise ValueError("original base/saved PCE exact context join incomplete")
        base_clock = mixed_utc(qaug.base_feature_clock,pd)
        union_clock = mixed_utc(qaug.feature_max_source_available_utc,pd)
        if ((base_clock.notna() & union_clock.isna()) | (base_clock > union_clock)
                | (union_clock.notna() & (union_clock >= qaug.cutoff_utc))).any():
            raise ValueError("saved union clock does not cover original base/saved PCE inputs")
        source_binding = json.loads(saved_bodies["SOURCE_AND_PROFILE_BINDING.json"])
        if (source_binding["audit"] != audit or source_binding["query_rows"] != len(qaug)
                or source_binding["RB_training_rows"] != len(augmented)
                or source_binding["pbp"] != [safe(r) for r in data["pbp_refs"]]):
            raise ValueError("saved source/profile binding differs from exact current retained sources")
        base_buffer = io.BytesIO()
        base_query.to_parquet(base_buffer,index=False)
        base_ref = put("QUERY_BASE_INPUTS_RECOVERED_V5.parquet",base_buffer.getvalue())
        joined_buffer = io.BytesIO()
        qaug[KEY+CTX+base_columns+list(core.EFFICIENCY_FEATURES)].to_parquet(joined_buffer,index=False)
        put("QUERY_RECOVERY_BINDING_V5.json",enc(dict(original_base=base_ref,
            saved_PCE=saved_refs["QUERY_PROFILE_INPUTS_2026.parquet"],
            joined_predictor_matrix_sha256=sha(joined_buffer.getvalue()), rows=len(qaug),
            original_base_columns=base_columns, PCE_columns=core.EFFICIENCY_FEATURES,
            saved_basic=saved_refs["BASIC_PROFILES_AND_COHORTS_2026.json.gz"],
            saved_defense=saved_refs["ALL32_RUSHING_DEFENSE_SNAPSHOTS_2026.json.gz"],
            new_query_profiles=0, new_defense_snapshots=0, target_outcomes_to_inference=False,
            reconstruction="exact cached W1-7 original30 plus same audited W8 original30 builder; saved142PCE joined by exact identities and clocks")))
        all_rows = []
        query_tiers = {tuple(getattr(r,k) for k in KEY): (r.query_clock_contract,r.query_evidence_tier) for r in qaug.itertuples()}
        for index, arm in enumerate(ARMS):
            category = increment.arm_category(data["category"], "R" + str(index), modeled_roles=["RB"])
            if STATE["fit_CPU_seconds"] >= 1200:
                raise ValueError("unchanged existing1200CPU cumulative model-training allowance exhausted")
            if index == 0:
                STATE["phase"] = "RESTORE_SAVED_PILOT_NO_REFIT"
                model = joblib.load(io.BytesIO(saved_bodies[expected_model]))
                if (not isinstance(model,cdf.LeafCDFModel) or model.audit.get("fit_state") != "FITTED"
                        or model.design.names != category["panels"]["base"]
                        or model.category["modeled_roles"] != ["RB"]
                        or model.audit["training_rows"] != len(augmented)):
                    raise ValueError("trusted returned pilot model/feature/training contract differs")
            else:
                # Reserve only the next finite returned state, not3*3MiB.
                store.reserve(plan["resources"]["first_model_max_bytes"])
                STATE["fits_attempted"] += 1
                STATE["phase"] = "FIT_" + arm
                put(f"FIT_{index + 1}_CONSUMED.json", enc(dict(arm=arm, UTC=now(), attempt=STATE["fits_attempted"], no_retry=True)))
                fit_cpu, fit_wall = time.process_time(), time.monotonic()
                try:
                    with threadpool_limits(limits=2):
                        model = cdf.LeafCDFModel.fit(augmented, category, "base")
                finally:
                    STATE["fit_CPU_seconds"] += time.process_time()-fit_cpu
                STATE["fits_returned"] += 1
                STATE["pending_model_object"] = model
                model_ref = save_model("MODEL_2026_" + arm + ".joblib", model)
                STATE["models"][arm] = model_ref
                if STATE["fit_CPU_seconds"] > 1200:
                    raise ValueError("returned model retained; unchanged1200CPU cumulative training allowance exceeded, no additional fits")
            STATE["phase"] = "INFERENCE_" + arm
            rows = carry.cdf_forecasts(model, qaug.reset_index(drop=True), arm, np)
            for row in rows:
                contract, tier = query_tiers[tuple(row[k] for k in KEY)]
                row.update(target="rush_yd", point_semantics="EXACT_EMPIRICAL_LAW_MEAN_AND_LOWER_MEDIAN_SEPARATE_PRODUCTS",
                    query_clock_contract=contract, query_evidence_tier=tier,
                    conditioning="CONDITIONAL_ON_PLAYED", original_issued_UTC=None,
                    probability_admission="UNVALIDATED_EXACT_LAW_NOT_CALIBRATED_CONFIDENCE",
                    reconstruction="CURRENT_VINTAGE_SEVEN_DAY_POLICY_EXPOSED_HISTORY")
            forecast_ref = put("FORECAST_2026_" + arm + ".json.gz", gzip.compress(enc(rows), mtime=0))
            STATE["forecast_parts"].append(dict(forecast_ref, arm=arm, rows=len(rows)))
            all_rows.extend(rows)
            del rows, model
        part_manifest = dict(format="IMMUTABLE_ORDERED_PART_MANIFEST_V1", version=VERSION,
            arm_order=ARMS, parts=STATE["forecast_parts"], rows=len(all_rows),
            logical_combined_sha256=sha(enc(all_rows)),
            logical_codec="JSON_sorted_keys_compact_allow_nan_false_newline; concatenate decoded part arrays in arm_order")
        frozen = put("ALL_FORECAST_PART_MANIFEST_BEFORE_LABELS_V1.json.gz", gzip.compress(enc(part_manifest), mtime=0))
        receipt = dict(version=VERSION, state="FROZEN_FORECASTS_COMPLETE_UNSCORED", UTC=now(),
            fits_attempted=STATE["fits_attempted"], fits_returned=STATE["fits_returned"], models=STATE["models"],
            new_fits_in_this_resume=3, restored_models_without_refit=1,
            forecasts=frozen, forecast_rows=len(all_rows), query_rows=len(qaug), artifacts=STATE["artifacts"],
            forecasts_format="IMMUTABLE_ORDERED_PART_MANIFEST_V1",
            products=["mean", "lower_median", "exact_line_conditional_Under_Push_Over_from_retained_law"],
            source_and_profile_binding=source_binding, actual_weeks=sorted(map(int, qaug.week.unique())),
            scoring_state="NOT_SCORED_REUSE_PINNED_C_EVALUATOR_IN_SEPARATE_OWNER_STAGE",
            resources=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start,
                model_fit_CPU_seconds=STATE["fit_CPU_seconds"], model_training_CPU_cap=1200,
                effective_global_hard_CPU_seconds=1200, registered_outer_CPU_maximum=2000,
                RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024), storage=store.checkpoint(),
            counts=dict(source_HTTP=0, new_original_issuances=0, production_writes=0, scoring=0))
        put("EXECUTION_RECEIPT.json", enc(receipt))
        public_receipt.parent.mkdir(parents=True, exist_ok=True)
        with public_receipt.open("xb") as handle:
            handle.write(enc(receipt)); handle.flush(); os.fsync(handle.fileno())
        print(enc(receipt).decode(), flush=True)
    except BaseException as error:
        failure = dict(version=VERSION, state="FAILED_RETAINED_NO_AUTOMATIC_REFIT", UTC=now(),
            phase=STATE["phase"], fits_attempted=STATE["fits_attempted"], fits_returned=STATE["fits_returned"],
            model_fit_CPU_seconds=STATE["fit_CPU_seconds"], model_training_CPU_cap=1200,
            effective_global_hard_CPU_seconds=1200, registered_outer_CPU_maximum=2000,
            error_type=type(error).__name__, error_sha256=sha(str(error).encode()), artifacts=STATE["artifacts"])
        if STATE.get("pending_model_object") is not None:
            try:
                save_model("RETURNED_PENDING_MODEL_FAILURE.joblib", STATE["pending_model_object"], failure=True)
            except BaseException as retention_error:
                failure["returned_model_retention_error_type"] = type(retention_error).__name__
        try:
            put("FAILURE_PRIVATE_PILOT_RESUME_V5.json", enc(dict(failure, traceback=traceback.format_exc())), failure=True)
        finally:
            print(enc(failure).decode(), flush=True)
        raise
    finally:
        signal.alarm(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--root-go", type=Path, required=True)
    parser.add_argument("--root-go-sha256", required=True)
    parser.add_argument("--publication-receipt", type=Path, required=True)
    parser.add_argument("--publication-receipt-sha256", required=True)
    parser.add_argument("--public-receipt", type=Path, required=True)
    args = parser.parse_args()
    plan = authorize(args)
    run(plan, args.public_receipt)


if __name__ == "__main__":
    main()
