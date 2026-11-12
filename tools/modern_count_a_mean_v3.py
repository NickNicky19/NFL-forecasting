"""Four retained-model mean-fallback reconstructions; never refit old artifacts."""
from __future__ import annotations

import argparse
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
import threading
import time
import zipfile
from datetime import datetime

VERSION = "modern-count-A-prior-mean-v3-technical-20261027"
RECIPE = "count-a-prior-mean-fallback-v2-20261025"
MIB = 1024 ** 2
CAPS = {"CPU": 60, "wall": 90, "main_CPU": 28, "main_wall": 48,
        "preparation_CPU": 10, "preparation_wall": 10, "metadata_CPU": 10, "metadata_wall": 20,
        "private_complete_peak_bytes": 8 * MIB, "RSS_bytes": 512 * MIB,
        "native_numerical_threads": 2, "startup_threads": 1,
        "model_loads": 4, "legacy_prediction_calls": 8, "new_vectors": 4,
        "fits": 0, "new_priors": 0, "HTTP": 0, "retries": 0, "scoring_passes": 1}
KEYS = ["season", "week", "game_id", "player_id"]
CONTEXT = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
FORBIDDEN = {"actual", "outcome_state", "pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int",
             "rush_yd", "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td"}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def capsule(members):
    """One immutable write; member bytes and hashes remain separately explicit."""
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, body in members.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 27, 0, 0, 0))
            archive.writestr(info, body)
    return result.getvalue()


def bootstrap_module(ref, name):
    path = Path(ref["path"]); body = path.read_bytes()
    if path.resolve() != path or len(body) != ref["bytes"] or sha(body) != ref["sha256"]:
        raise ValueError("exact existing harness required")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def correct_fallbacks(np, old_point, reasons, roles, priors, global_prior):
    """Existing mean-v2 arithmetic on already-authenticated legacy predictions."""
    result = np.array(old_point, dtype=np.float64, copy=True)
    reasons = np.asarray(reasons, dtype=str); roles = np.asarray(roles, dtype=str)
    if result.shape != reasons.shape or roles.shape != reasons.shape:
        raise ValueError("complete vector shapes required")
    for index in np.flatnonzero(reasons != ""):
        prior = priors.get(str(roles[index]), global_prior)
        if prior is None:
            if np.isfinite(result[index]): raise ValueError("numeric fallback without stored prior")
            continue
        if (prior.support != "count" or not np.isfinite(prior.q) or not 0 <= prior.q < 1
                or type(prior.n) is not int or prior.n <= 0 or not np.isfinite(prior.mean) or prior.mean < 0):
            raise ValueError("valid actually-trained count prior required")
        if not np.isfinite(result[index]): raise ValueError("stored supported prior did not produce original fallback")
        result[index] = prior.mean
    warm = reasons == ""
    if not np.array_equal(result[warm].view(np.uint64), np.asarray(old_point, dtype=np.float64)[warm].view(np.uint64)):
        raise AssertionError("warm forecast bits changed")
    if np.isinf(result).any() or (result[np.isfinite(result)] < 0).any():
        raise ValueError("invalid corrected count mean")
    return result


def validate(plan, harness):
    if (plan["version"] != VERSION or plan["state"] != "ROOT_AND_REVIEWER_SEALED"
            or plan["review"] != "PREEXEC_PASS" or plan["resources"] != CAPS
            or plan["root_registration"].get("registered_by") != "/root"
            or plan["root_registration"].get("previous_managed_writer_closed") is not True
            or plan["recipe"] != RECIPE):
        raise ValueError("exact reviewed finite registration and writer closure required")
    if {(m["year"], m["target"]) for m in plan["members"]} != {(y, t) for y in (2025, 2026) for t in ("rush_att", "rec")} or len(plan["members"]) != 4:
        raise ValueError("exact four complete retained members required")
    reservation = json.loads(harness.read(plan["reservation"]))
    if (reservation["private_destination"] != plan["allocation_parent"] or reservation["budget_bytes_including_peaks"] != 8 * MIB
            or reservation["parent_policy_sha256"] != plan["forward_policy"]["sha256"]
            or reservation["reserved_compute_CPU_wall_seconds"] != [60, 90]
            or reservation["proposed_phase_caps_CPU_wall"] != {"main": [40, 60], "last_metadata": [10, 20], "preparation": [10, 10]}
            or reservation["maximum_legacy_prediction_replays"] != 8 or reservation["maximum_new_complete_forecast_vectors"] != 4):
        raise ValueError("actual reservation fields or inclusive finite phases differ")
    technical = json.loads(harness.read(plan["technical_continuation"]))
    if (technical["original_whole_CPU_wall_cap"] != [60, 90] or technical["new_main_CPU_wall_cap"] != [28, 48]
            or technical["original_failed_CPU_wall"] != [11.968, 11.894]
            or technical["new_technical_reload_replay_allowance"] != {"model_loads": 4, "top_level_predict_calls": 8}
            or technical["original_calls_caps_preserved"] != {"model_loads": 4, "top_level_predict_calls": 8}
            or technical["original_actual_model_loads_and_top_level_predict_attempts"] != [1, 1]
            or technical["original_complete_vectors_and_scoring_passes"] != [0, 0]
            or technical["cumulative_including_original_failed_attempt"] != {"distinct_models": 4, "model_loads": 5, "new_completed_vectors": 4, "scoring_passes": 1, "top_level_predict_attempts": 9}
            or technical["inclusive_oldplusnew_max_CPU_wall"] != [59.968, 89.894]
            or technical["same_allocation_parent"] != plan["allocation_parent"] or technical["inclusive_bytes_cap"] != 8388608
            or plan["output"] != str(Path(plan["allocation_parent"]) / technical["fresh_subdirectory"])
            or technical["original_reservation_sha256"] != plan["reservation"]["sha256"]
            or technical["original_worker_sha256"] != plan["preserved_failed_v2"]["WORKER.py.txt"]["sha256"]
            or technical["original_sealed_sha256"] != plan["preserved_failed_v2"]["SEALED_PLAN.json.txt"]["sha256"]
            or technical["accepted_libc"] != plan["technical_bootstrap"]["libc"]
            or any(technical["accepted_threadpoolctl"][k] != plan["technical_bootstrap"]["threadpoolctl"][k] for k in ("bytes", "sha256"))
            or 11.968 + CAPS["main_CPU"] + 10 + 10 > 60 or 11.894 + CAPS["main_wall"] + 10 + 20 > 90):
        raise ValueError("exact one technical continuation/cumulative accounting required")
    for ref in plan["preserved_failed_v2"].values(): harness.read(ref)
    harness.read(technical["original_consumed"]); harness.read(technical["original_native"])
    harness.read(plan["worker"])
    if plan["worker"]["path"] != str(Path(__file__).resolve()): raise ValueError("exact worker path required")
    harness.read(plan["existing_recipe_source"])
    original = json.loads(harness.read(plan["original_forecast_freeze"]))
    scored = json.loads(harness.read(plan["original_scored_freeze"]))
    if original["state"] != "GLOBAL_FORECASTS_FROZEN" or scored["forecast_freeze"] != plan["original_forecast_freeze"]:
        raise ValueError("actual original freeze chain differs")
    parent = json.loads(harness.read(plan["runtime_parent"]))
    runtime = json.loads(harness.read(parent["accepted_runtime_binding"]["runtime_manifest"]))
    accepted = {r["path"]: r for r in runtime["runtime_dependencies"].values()}
    for ref in plan["technical_bootstrap"].values():
        if ref["path"] not in accepted or any(accepted[ref["path"]][k] != ref[k] for k in ("path", "bytes", "sha256")):
            raise ValueError("technical cache bootstrap is not the exact accepted runtime binding")
        harness.read(ref)
    library = Path(parent["frozen_library_root"]) / "nfl_lab"
    for member in plan["members"]:
        manifest = json.loads(harness.read(member["artifact"]))
        if (manifest["family"] != "count_A" or manifest["method_id"] != "COUNT_A" or manifest["model"] != member["model"]
                or manifest["category"] != member["category"] or manifest["features"] != member["features"]
                or manifest["category"]["target"] != member["target"] or manifest["category"]["support"] != "count"
                or not datetime.fromisoformat(manifest["training_max_available_utc"]) < datetime.fromisoformat(manifest["training_cutoff_utc"])
                or FORBIDDEN & set(manifest["features"])):
            raise ValueError("actual manifest/category/model/feature chronology differs")
        for name in ("role_boosting.py", "cdf_engine.py", "median_boosting.py"):
            if sha((library / name).read_bytes()) != manifest["code_pins"][name]:
                raise ValueError("retained model/prior core source differs from exact runtime")
        slot = next(s for s in original["slots"] if (s["year"], s["target"], s["method_id"]) == (member["year"], member["target"], "COUNT_A"))
        cdf_slot = next(s for s in original["slots"] if (s["year"], s["target"], s["method_id"]) == (member["year"], member["target"], "LAB_CDF"))
        if slot["state"] != "FROZEN" or slot["artifact"] != member["artifact"] or cdf_slot["state"] != "MEMBER_BLOCKED_RETAINED":
            raise ValueError("original retained member/control state differs")
        for name, freeze in (("query", original), ("forecast", original), ("outcome", scored)):
            ref = member[name]; relative = str(Path(ref["path"]).relative_to(plan["original_output"]))
            if freeze["bindings"].get(relative) != ref["sha256"]:
                raise ValueError("actual frozen complete row reference differs")
    return {"state": "METADATA_GATES_VALID", "NFL_or_model_values_decoded": 0, "actual_reservation_fields": "PASS"}


def initialize_pinned_libc_cache(guard, guard_module, pins):
    """RTLD_NOLOAD only: strict child/socket audit remains active throughout."""
    import ctypes
    import threadpoolctl
    libc, ctl = pins["libc"], pins["threadpoolctl"]
    for ref in (libc, ctl):
        guard_module.authenticate(ref)
        accepted = guard.known.get(ref["path"])
        if accepted is None or any(accepted[k] != ref[k] for k in ("path", "bytes", "sha256")):
            raise ValueError("bootstrap source is not bound by accepted RuntimeGuard")
    if str(Path(threadpoolctl.__file__).resolve()) != ctl["path"]:
        raise ValueError("loaded threadpoolctl origin differs")
    mapped = {str(Path(parts[5]).resolve()) for line in Path("/proc/self/maps").read_text().splitlines()
              if len(parts := line.split()) == 6 and parts[5].startswith("/")}
    if libc["path"] not in mapped or not hasattr(os, "RTLD_NOLOAD"):
        raise ValueError("exact accepted libc must already be mapped")
    handle = ctypes.CDLL(libc["path"], mode=os.RTLD_NOLOAD)
    cache = threadpoolctl.ThreadpoolController._system_libraries
    old = cache.get("libc")
    if old is not None and old._handle != handle._handle:
        raise ValueError("unexpected libc cache entry")
    cache["libc"] = handle
    return {"state": "ACCEPTED_ALREADY_MAPPED_LIBC_CACHE_INITIALIZED", "RTLD_NOLOAD": True,
            "libc": libc, "threadpoolctl": ctl, "child_socket_guard_unchanged": True,
            "new_model_or_prediction_calls": 0}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--plan", required=True); parser.add_argument("--sha256", required=True)
    parser.add_argument("--go"); parser.add_argument("--validate-plan", action="store_true")
    args = parser.parse_args(); raw = Path(args.plan).read_bytes()
    if sha(raw) != args.sha256: raise ValueError("exact sealed plan hash required")
    plan = json.loads(raw); harness = bootstrap_module(plan["existing_harness"], "existing_modern_read_harness")
    checked = validate(plan, harness)
    if args.validate_plan: print(json.dumps(checked)); return 0
    if not args.go or json.loads(Path(args.go).read_text()) != {"state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": args.sha256}:
        raise ValueError("separate exact root GO required")
    started, cpu = time.monotonic(), time.process_time(); done = threading.Event()
    calls = loads = vectors = scores = 0; failure = None; result_ref = None
    resource.setrlimit(resource.RLIMIT_CPU, (26, 27)); resource.setrlimit(resource.RLIMIT_AS, (3 * 1024 ** 3, 3 * 1024 ** 3))
    def stop(*unused):
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise RuntimeError("finite main correction allocation exhausted")
    signal.signal(signal.SIGALRM, stop); signal.signal(signal.SIGXCPU, stop); signal.setitimer(signal.ITIMER_REAL, 45)
    def deny(event, unused):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}:
            raise RuntimeError("offline child-free correction required")
    sys.addaudithook(deny)
    def watch():
        while not done.wait(.05):
            if int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") > 480 * MIB:
                os.kill(os.getpid(), signal.SIGALRM); return
    threading.Thread(target=watch, daemon=True).start()
    try:
        parent = json.loads(harness.read(plan["runtime_parent"]))
        guard_module = harness.module(parent["runtime_guard"], "correction_shared_runtime_guard")
        guard = guard_module.RuntimeGuard(parent["accepted_runtime_binding"], {**parent["code_pins"], **plan["code_pins"]},
                                         parent["frozen_library_root"], Path(parent["runtime_guard"]["path"]).parent)
        env = parent["environment"]
        if (sys.version != env["python_version"] or Path(sys.executable).resolve() != Path(env["python_binary"]["path"])
                or sha(Path(sys.executable).read_bytes()) != env["python_binary"]["sha256"]
                or any(os.environ.get(k) != v for k, v in env["required_variables"].items())):
            raise ValueError("exact authenticated startup runtime required")
        harness.read(parent["timeout"]); pp = Path("/proc") / str(os.getppid())
        expected = [parent["timeout"]["path"], "--signal=KILL", "47s", env["python_command"], "-I", "-S", "-B",
                    str(Path(__file__).resolve()), "--plan", args.plan, "--sha256", args.sha256, "--go", args.go]
        if Path(os.readlink(pp / "exe")) != Path(parent["timeout"]["path"]) or (pp / "cmdline").read_bytes().rstrip(b"\0").split(b"\0") != [x.encode() for x in expected]:
            raise ValueError("exact external finite timeout required")
        forecast_freeze = json.loads(harness.read(plan["original_forecast_freeze"]))
        scored_freeze = json.loads(harness.read(plan["original_scored_freeze"]))
        if forecast_freeze["state"] != "GLOBAL_FORECASTS_FROZEN" or scored_freeze["forecast_freeze"] != plan["original_forecast_freeze"]:
            raise ValueError("exact original global freeze chain required")
        for member in plan["members"]:
            for name, freeze in (("query", forecast_freeze), ("forecast", forecast_freeze), ("outcome", scored_freeze)):
                ref = member[name]; relative = str(Path(ref["path"]).relative_to(plan["original_output"]))
                if freeze["bindings"].get(relative) != ref["sha256"]: raise ValueError("original complete row binding missing")
            slot = next(s for s in forecast_freeze["slots"] if (s["year"], s["target"], s["method_id"]) == (member["year"], member["target"], "COUNT_A"))
            if slot["state"] != "FROZEN" or slot["artifact"] != member["artifact"]: raise ValueError("exact retained COUNT_A artifact required")
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        import joblib
        from nfl_lab import weekly_future_inference as existing, cdf_engine
        from nfl_lab.role_boosting import RoleCountBoostingModel
        from nfl_lab.owned_reference_batch import validate_owned_references
        from nfl_lab.evaluation import summarize
        from nfl_lab.source_matched_reporting import _bootstrap
        from nfl_lab.state import digest, now_utc
        pa.set_cpu_count(1); pa.set_io_thread_count(1)
        if existing.COUNT_A_FALLBACK_VERSION != RECIPE: raise ValueError("existing mean-v2 recipe identity differs")
        guard.verify_loaded()
        bootstrap_receipt = initialize_pinned_libc_cache(guard, guard_module, plan["technical_bootstrap"])
        guard.verify_loaded()
        forward = harness.module(plan["forward_helper"], "correction_existing_forward_store")
        store = forward.ForwardOperationalStorage(parent["cache"], json.loads(harness.read(plan["forward_policy"])),
                                                  json.loads(harness.read(parent["source_policy"])), state=parent["state_root"])
        out = Path(plan["output"])
        if out.exists() or out.parent != Path(plan["allocation_parent"]) or out.parent.parent != store.live_root / "research": raise ValueError("fresh one-use technical subdirectory in same allocation required")
        owned = {}
        for member in plan["members"]:
            for name in ("artifact", "model", "query", "forecast", "outcome"):
                ref = member[name]; owned[ref["path"]] = ref["sha256"]
        owned_refs, ownership = validate_owned_references(store.legacy, owned)
        old_bytes = {}
        for path in Path(plan["allocation_parent"]).rglob("*"):
            if path.is_file():
                info = path.stat(); old_bytes[(info.st_dev, info.st_ino)] = info.st_size
        retained = sum(old_bytes.values())
        anchor = store.snapshot()["forward_physical_bytes"] - retained
        def save(name, body):
            nonlocal retained
            if not isinstance(body, bytes): body = encoded(body)
            if len(body) > 3 * MIB or retained + 2 * len(body) + MIB > 8 * MIB: raise RuntimeError("complete retention/staging/reserve envelope exceeded")
            path = out / name; store.write_bytes(path, body); ref = store.validate_reference(path, sha(body))
            if path.read_bytes() != body: raise ValueError("owned byte readback differs")
            retained += len(body); return ref
        save("CONSUMED.json", {"plan_sha256": args.sha256, "maximum_legacy_calls": 8, "new_vectors": 4,
                               "fits": 0, "new_priors": 0, "HTTP": 0, "ownership": ownership, "technical_bootstrap": bootstrap_receipt, "old_failed_actual_loads_top_level_attempts": [1, 1], "new_allowance_loads_top_level_calls": [4, 8]})
        def table(ref, fields): return pq.read_table(pa.BufferReader(harness.read(ref)), columns=fields).to_pandas()
        def admit_call():
            nonlocal calls
            if calls >= 8 or time.process_time() - cpu >= 22 or time.monotonic() - started >= 39:
                raise RuntimeError("finite prediction budget/finalization reserve exhausted")
            calls += 1
        frames, audits = [], []
        for member in plan["members"]:
            manifest = json.loads(harness.read(member["artifact"]))
            if (manifest["family"] != "count_A" or manifest["method_id"] != "COUNT_A" or manifest["model"] != member["model"]
                    or manifest["category"] != member["category"] or manifest["features"] != member["features"]
                    or not pd.Timestamp(manifest["training_max_available_utc"]) < pd.Timestamp(manifest["training_cutoff_utc"])):
                raise ValueError("original artifact recipe/prior chronology mismatch")
            columns = list(dict.fromkeys(KEYS + CONTEXT + ["feature_max_source_available_utc"] + manifest["features"]))
            if FORBIDDEN & set(columns): raise ValueError("target columns in query projection")
            query = table(member["query"], columns)
            old = table(member["forecast"], KEYS + CONTEXT + ["point", "fallback"])
            for field in ("kickoff_utc", "cutoff_utc"):
                query[field] = pd.to_datetime(query[field], utc=True, errors="raise")
                old[field] = pd.to_datetime(old[field], utc=True, errors="raise")
            if (not query[KEYS + CONTEXT].equals(old[KEYS + CONTEXT]) or query.duplicated(KEYS).any()
                    or query[KEYS + CONTEXT].isna().any(axis=None) or not query.season.eq(member["year"]).all()
                    or not query.week.between(1, 6 if member["year"] == 2026 else 18).all()
                    or pd.Timestamp(manifest["training_cutoff_utc"]) > pd.to_datetime(query.cutoff_utc, utc=True).min()):
                raise ValueError("complete query/forecast identity or evaluation/training scope differs")
            source = pd.to_datetime(query.feature_max_source_available_utc, utc=True, errors="coerce")
            cutoff = pd.to_datetime(query.cutoff_utc, utc=True)
            warm = cdf_engine.numeric(query, "f_player_games_prior") > 0
            if (source.isna().to_numpy() & warm).any() or (source.notna() & ~source.lt(cutoff)).any():
                raise ValueError("source feature availability violates original cutoff")
            loads += 1; bundle = joblib.load(io.BytesIO(harness.read(member["model"])))
            model, fixture = bundle["model"], bundle["fixture"]
            if (not isinstance(model, RoleCountBoostingModel) or model.variant != "A" or existing.model_contract(model, "count_A") != (manifest["category"], manifest["features"])
                    or FORBIDDEN & set(fixture.columns) or existing.frame_digest(fixture) != manifest["replay_fixture_sha256"]):
                raise ValueError("retained model class/design/fixture contract mismatch")
            admit_call(); fixture_points, fixture_reasons = model.predict(fixture)
            bits = {"float64_hex": np.asarray(fixture_points, dtype="<f8").tobytes().hex(), "fallback": np.asarray(fixture_reasons, dtype=str).tolist()}
            if bits != bundle["expected_bits"] or digest(bits) != manifest["replay_bits_sha256"]:
                raise ValueError("exact original fixture replay mismatch")
            admit_call(); replay_points, replay_reasons = model.predict(query)
            p = old.point.to_numpy(dtype=np.float64); replay_points = np.asarray(replay_points, dtype=np.float64)
            reasons = np.asarray(replay_reasons, dtype=str)
            if (not np.array_equal(p.view(np.uint64), replay_points.view(np.uint64)) or reasons.tolist() != old.fallback.tolist()
                    or np.isinf(p).any() or (p[np.isfinite(p)] < 0).any()):
                raise ValueError("complete original vector/reason bitwise replay mismatch")
            corrected = correct_fallbacks(np, p, reasons, query.position.to_numpy(str), model.priors, model.global_prior)
            frame = old.copy(); frame["legacy_point"] = p; frame["point"] = corrected
            frame["target"] = member["target"]; frame["recipe"] = RECIPE
            frame["model_manifest_sha256"] = member["artifact"]["sha256"]
            frame["primary_role"] = query.position.isin(manifest["category"]["primary_roles"]).to_numpy()
            frames.append(frame); vectors += 1
            audits.append({"year": member["year"], "target": member["target"], "rows": len(frame),
                           "fixture_and_full_vector_parity": "EXACT_BITS_AND_REASONS", "legacy_calls": 2,
                           "fallback_rows": int((reasons != "").sum()), "changed_rows": int((p.view(np.uint64) != corrected.view(np.uint64)).sum()),
                           "warm_bits_unchanged": True, "stored_training_priors_only": True, "new_prior_fits": 0})
            del model, bundle, fixture, query
        forecast = pd.concat(frames, ignore_index=True); buffer = io.BytesIO()
        forecast.to_parquet(buffer, index=False, compression="zstd")
        forecast_body = buffer.getvalue()
        forecast_member = {"member": "FORECASTS.parquet", "bytes": len(forecast_body), "sha256": sha(forecast_body)}
        freeze_manifest = {"state": "ALL_FOUR_CORRECTED_VECTORS_FROZEN", "plan_sha256": args.sha256,
                    "actual_generated_at": now_utc().isoformat(), "forecast": forecast_member, "audits": audits,
                    "new_vectors": vectors, "legacy_replay_calls": calls, "target_label_columns_decoded": 0,
                    "source_members": plan["members"],
                    "evidence_lane": "new_current_vintage_historical_reconstruction_not_original_issued_vectors"}
        freeze = save("FORECAST_FREEZE.zip", capsule({"FORECASTS.parquet": forecast_body, "MANIFEST.json": encoded(freeze_manifest)}))
        # First target-label decoding occurs below the completed owned freeze.
        summaries, graded = [], []; scores = 1
        for member, frame in zip(plan["members"], frames):
            outcome = table(member["outcome"], KEYS + CONTEXT + ["actual", "participation_state"])
            for field in ("kickoff_utc", "cutoff_utc"):
                outcome[field] = pd.to_datetime(outcome[field], utc=True, errors="raise")
            if not frame[KEYS + CONTEXT].equals(outcome[KEYS + CONTEXT]): raise ValueError("complete outcome context differs")
            frame = frame.copy(); frame["actual"] = outcome.actual; frame["participation_state"] = outcome.participation_state
            y = frame.actual.to_numpy(float); old_p = frame.legacy_point.to_numpy(float); new_p = frame.point.to_numpy(float)
            if (not frame.participation_state.isin(["played", "DNP", "unknown"]).all() or np.isinf(y).any()
                    or (np.isfinite(y) & ~frame.participation_state.eq("played").to_numpy()).any()
                    or (np.isfinite(y) & ((y < 0) | (y != np.floor(y)))).any()):
                raise ValueError("unsupported outcome or participation state")
            played = frame.participation_state.eq("played").to_numpy() & np.isfinite(y)
            eligible = played & np.isfinite(old_p) & np.isfinite(new_p)
            frame["legacy_MSE"] = np.where(eligible, (old_p - y) ** 2, np.nan)
            frame["corrected_MSE"] = np.where(eligible, (new_p - y) ** 2, np.nan)
            frame["delta_candidate_minus_control"] = frame.corrected_MSE - frame.legacy_MSE
            strata = {}
            for name, mask in (("all_offered", np.ones(len(frame), bool)), ("primary_role", frame.primary_role.to_numpy()),
                               ("primary_fallback", frame.primary_role.to_numpy() & frame.fallback.ne("").to_numpy()),
                               ("primary_warm", frame.primary_role.to_numpy() & frame.fallback.eq("").to_numpy())):
                candidate = frame.loc[mask].copy(); legacy = candidate.copy(); legacy["point"] = legacy.legacy_point
                a = summarize(candidate, include_distribution=False, value_column="point")
                b = summarize(legacy, include_distribution=False, value_column="point")
                paired = mask & eligible; old_loss = frame.loc[paired, "legacy_MSE"].mean(); new_loss = frame.loc[paired, "corrected_MSE"].mean()
                strata[name] = {"candidate": a, "legacy": b, "paired_rows": int(paired.sum()),
                                "candidate_MSE": float(new_loss) if paired.any() else None, "legacy_MSE": float(old_loss) if paired.any() else None,
                                "relative_MSE_improvement_percent": float(100 * (old_loss - new_loss) / old_loss) if paired.any() and old_loss != 0 else None,
                                "intervals": [_bootstrap(frame, paired, cluster, 500, 1703) for cluster in ("week", "game")]}
            summaries.append({"year": member["year"], "target": member["target"], "strata": strata,
                              "CDF_control": "N/A_ORIGINAL_MEMBER_BLOCKED", "SITE_raw": "UNAVAILABLE"})
            graded.append(frame)
        grade = pd.concat(graded, ignore_index=True); buffer = io.BytesIO(); grade.to_parquet(buffer, index=False, compression="zstd")
        grade_body = buffer.getvalue()
        grade_member = {"member": "GRADED_ROWS.parquet", "bytes": len(grade_body), "sha256": sha(grade_body)}
        exit_owned, exit_ownership = validate_owned_references(store.legacy, owned)
        if exit_owned != owned_refs: raise ValueError("original owned input references changed during correction")
        guard.verify_files(); runtime = guard.verify_loaded()
        result = {"version": VERSION, "state": "COMPLETE_EXPOSED_FOUR_VECTOR_MEAN_CORRECTION", "recipe": RECIPE,
                  "plan_sha256": args.sha256, "forecast_freeze": freeze, "forecast": forecast_member, "grade": grade_member,
                  "summaries": summaries, "audits": audits, "legacy_prediction_calls": calls, "new_vectors": vectors,
                  "fits": 0, "new_priors": 0, "HTTP": 0, "scoring_passes": scores, "runtime": runtime,
                  "scientifically_qualified": False, "operationally_ready": False, "four_training_windows_tested": False,
                  "old_failures_caps_and_frozen_vectors_unchanged": True, "technical_bootstrap": bootstrap_receipt, "original_failed_CPU_wall": [11.968, 11.894], "cumulative_model_loads": loads + 1, "cumulative_top_level_predict_attempts": calls + 1, "internal_HGB_predict_calls": "UNMEASURED",
                  "original_owned_inputs_unchanged": True, "exit_owned_validation": exit_ownership,
                  "actual_forward_delta_before_result": store.snapshot()["forward_physical_bytes"] - anchor}
        body = capsule({"GRADED_ROWS.parquet": grade_body, "RESULT.json": encoded(result)})
        if result["actual_forward_delta_before_result"] + 2 * len(body) + MIB > 8 * MIB:
            raise RuntimeError("actual global retained growth/peak reserve exceeded")
        result_ref = save("GRADE_COMPLETE.zip", body)
        print(json.dumps({"state": result["state"], "result": result_ref, "forecast_freeze": freeze, "grade_member": grade_member}))
    except BaseException as error:
        failure = {"type": type(error).__name__, "reason": str(error)[:800]}
    finally:
        done.set(); signal.setitimer(signal.ITIMER_REAL, 0)
        print(json.dumps({"failure": failure, "native_CPU": time.process_time() - cpu, "native_wall": time.monotonic() - started,
                          "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024, "model_loads": loads,
                          "legacy_prediction_calls": calls, "cumulative_top_level_predict_attempts": calls + 1, "cumulative_model_loads": loads + 1, "internal_HGB_predict_calls": "UNMEASURED", "new_vectors": vectors, "scoring_passes": scores, "fits": 0, "new_priors": 0, "HTTP": 0}))
    return 0 if failure is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
