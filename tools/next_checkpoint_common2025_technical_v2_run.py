"""Separately registered2025 common-learner history comparison.

All55 opportunities are durably charged before any training-label decode.
Complete forecasts/models are frozen and read back before outer scoring.
Original2026 fit slots, controls and adverse results remain unchanged.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.metadata
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

VERSION = "next-nfl-common2025-technical-v2-20261028"
KEYS = ["season", "week", "game_id", "player_id"]
CONTEXT = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
MIB = 1024 ** 2
METHODS = {"CURRENT_ONLY": "CDF_H1_CURRENT_SEASON_TRAINING",
    "PRIOR_PLUS_CURRENT": "CDF_H2_PRIOR_PLUS_CURRENT_TRAINING",
    "TIME_WEIGHTED": "CDF_H3_TIME_WEIGHTED_FIXED365_TRAINING",
    "HISTORICAL_RELATION_CURRENT_STATE": "CDF_H4_HISTORICAL_RELATION_CURRENT_STATE"}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def bind(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}


def authenticated(ref):
    path = Path(ref["path"])
    if path.resolve() != path or bind(path) != {k: ref[k] for k in ["path", "bytes", "sha256"]}:
        raise ValueError("exact canonical immutable reference differs")
    return path


def module(ref, name):
    path = authenticated(ref)
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def capsule(members):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    return out.getvalue()


def frame_bytes(frame):
    out = io.BytesIO()
    frame = frame.copy()
    frame.attrs.clear()
    frame.to_parquet(out, index=False, compression="zstd")
    return out.getvalue()


def bootstrap_threadpool(pins):
    """Authenticate and cache only the libc already mapped by this process.

    This is the explicit RTLD_NOLOAD repair used by the earlier accepted
    worker; it does not permit threadpoolctl to run ldconfig or other children.
    No RuntimeGuard replay/reproduction is claimed by this new study.
    """
    import ctypes
    import threadpoolctl
    libc = authenticated(pins["libc"])
    controller_source = authenticated(pins["threadpoolctl"])
    if Path(threadpoolctl.__file__).resolve() != controller_source:
        raise ValueError("pinned threadpoolctl origin changed")
    mapped = {str(Path(parts[5]).resolve()) for line in Path("/proc/self/maps").read_text().splitlines()
              if len(parts := line.split()) == 6 and parts[5].startswith("/")}
    if str(libc) not in mapped or not hasattr(os, "RTLD_NOLOAD"):
        raise ValueError("exact pinned libc must already be mapped")
    handle = ctypes.CDLL(str(libc), mode=os.RTLD_NOLOAD)
    cache = threadpoolctl.ThreadpoolController._system_libraries
    previous = cache.get("libc")
    if previous is not None and previous._handle != handle._handle:
        raise ValueError("unexpected existing libc handle")
    cache["libc"] = handle
    return {"state": "PINNED_ALREADY_MAPPED_LIBC_CACHED", "RTLD_NOLOAD": True,
            "libc": pins["libc"], "threadpoolctl": pins["threadpoolctl"],
            "new_fits": 0, "child_calls": 0, "socket_calls": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    raw = Path(args.plan).read_bytes()
    if sha(raw) != args.sha256:
        raise ValueError("exact root sealed2025 plan required")
    plan = json.loads(raw)
    if (plan["version"] != VERSION or plan["state"] != "ROOT_AND_REVIEWER_SEALED"
            or plan["execution_authorized"] is not True or json.loads(Path(args.go).read_bytes()) != {
                "state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": args.sha256,
                "scope": "ONE_NEXT_NFL_COMMON2025_TECHNICAL_V2", "previous_managed_writer_closed": True}):
        raise ValueError("separate root/reviewer GO required before numerical work")
    sys.dont_write_bytecode = True
    for variable in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "ARROW_NUM_THREADS"]:
        os.environ[variable] = "1"
    started, cpu = time.monotonic(), time.process_time()
    caps = plan["resources"]
    resource.setrlimit(resource.RLIMIT_CPU, (caps["CPU_seconds"], caps["CPU_seconds"] + 1))
    class BudgetStop(BaseException):
        pass
    def absolute_stop(*unused):
        os._exit(124)
    def stop(*unused):
        # Failure retention shares the original absolute deadline. It cannot
        # silently obtain another full wall allocation after the soft stop.
        signal.signal(signal.SIGALRM, absolute_stop)
        signal.setitimer(signal.ITIMER_REAL, max(.001, caps["wall_seconds"] - (time.monotonic() - started)))
        raise BudgetStop("new2025 finite allocation consumed")
    for sig in [signal.SIGALRM, signal.SIGXCPU, signal.SIGUSR1]:
        signal.signal(sig, stop)
    signal.setitimer(signal.ITIMER_REAL, caps["wall_seconds"] - 10)
    done = threading.Event()
    def check():
        if (time.monotonic() - started >= caps["wall_seconds"] - 10
                or time.process_time() - cpu >= caps["CPU_seconds"] - 2
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > caps["RSS_bytes"]):
            raise BudgetStop("CPU/wall/RSS cap exhausted")
    def watch():
        while not done.wait(.1):
            try:
                check()
            except BaseException:
                os.kill(os.getpid(), signal.SIGUSR1)
                return
    threading.Thread(target=watch, daemon=True).start()
    def deny(event, unused):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}:
            raise ValueError("offline child-free2025 numerical invocation required")
    sys.addaudithook(deny)
    native = Path(plan["native_control_root"])
    if native.exists():
        raise ValueError("fresh one-invocation namespace required")
    native.mkdir(parents=True)
    native_size = writes = forests = trees = priors = fit_entries = returned_forests = 0
    charged = plan["preserved_v1_private_charged_bytes"]
    storage = None
    retained, pending, audits = {}, {}, []
    def receipt():
        return {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "forest_fit_attempts": forests, "tree_estimators": trees, "support_prior_formations": priors,
                "actual_forest_fit_entries": fit_entries, "returned_forest_fits": returned_forests,
                "HTTP_calls": 0, "model_loads": 0, "automatic_retries": 0}
    def native_write(name, value):
        nonlocal native_size
        body = encoded(value)
        if native_size + len(body) > caps["native_control_bytes_cap"]:
            raise ValueError("native metadata allocation exhausted")
        with (native / name).open("xb") as stream:
            stream.write(body)
        native_size += len(body)
    native_write("CONSUMED.json", {"state": "ONE_NEW2025_INVOCATION_CONSUMED", "plan_sha256": args.sha256,
                 "old2026_and_prior_budgets_unchanged": True, "automatic_retries": 0})
    def save(name, members, limit):
        nonlocal writes, charged
        body = capsule(members)
        if (storage is None or writes >= caps["maximum_managed_write_attempts_including_failure"]
                or len(body) > limit or charged + len(body) + 113 > caps["retained_private_bytes_cap"]
                or charged + 2 * len(body) + 113 > caps["peak_private_bytes_cap"]):
            raise ValueError("complete/staging retention allocation exhausted")
        writes += 1
        charged += len(body)
        path = Path(plan["output"]) / name
        storage.write_bytes(path, body)
        storage.validate_reference(path)
        if path.read_bytes() != body:
            raise ValueError("managed exact capsule readback mismatch")
        with zipfile.ZipFile(path) as archive:
            if set(archive.namelist()) != set(members):
                raise ValueError("managed member set mismatch")
            for member, expected in members.items():
                if archive.read(member) != expected:
                    raise ValueError("managed inner readback mismatch")
        retained[name] = bind(path)
        native_write(name.replace(".zip", "_READBACK.json"), {"binding": retained[name], "bytes_exact": True,
                     "members": {n: {"bytes": len(v), "sha256": sha(v)} for n, v in members.items()}})
        check()
        return retained[name]
    try:
        bootstrap = bootstrap_threadpool(plan["technical_bootstrap"])
        fixture = json.loads(authenticated(plan["bootstrap_fixture"]).read_bytes())
        if (fixture["state"] != "PINNED_THREADPOOL_CHILD_FREE_BOOTSTRAP_PASS"
                or fixture["runner_sha256"] != plan["implementation_bindings"][0]["sha256"]
                or fixture["NFL_values"] != 0 or fixture["fits"] != 0 or fixture["attempted_child_calls"] != 0):
            raise ValueError("exact bounded child-free startup acceptance required")
        for ref in [*plan["implementation_bindings"], *plan["inputs"].values()]:
            authenticated(ref)
        snap_admission = json.loads(authenticated(plan["snap_source_admission"]).read_bytes())
        if (snap_admission["state"] != "PASS_EXCLUDED_SNAP_CHANNELS_UNAVAILABLE"
                or snap_admission["outcome_column_decodes"] != 0 or snap_admission["fits"] != 0
                or any(item["source_sha256"] != plan["inputs"][name]["sha256"]
                       for name, item in snap_admission["sources"].items())
                or any(column["disallowed_values"] != 0 for item in snap_admission["sources"].values()
                       for column in item["columns"].values())):
            raise ValueError("exact no-excluded-snap-value source admission required")
        if (str(Path(sys.executable).resolve()) != plan["python_binary"]["path"]
                or sha(Path(sys.executable).read_bytes()) != plan["python_binary"]["sha256"]
                or sys.version != plan["python_version"]):
            raise ValueError("newstudy pinned Python runtime changed")
        for key, version in plan["environment_versions"].items():
            if importlib.metadata.version(key) != version:
                raise ValueError("scientific version changed: " + key)
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        import joblib
        from sklearn.ensemble import ExtraTreesRegressor
        from nfl_lab import cdf_engine
        from nfl_lab.source_matched_reporting import _bootstrap
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        harness = module(plan["shared_harness"], "new2025_unchanged_harness")
        module(plan["prior_recipe"], "pass_att_four_families_v1")
        module(plan["prior_loader"], "pass_att_four_families_loader_v1")
        kernels = module(plan["fit_wrapper"], "pass_att_common_learner_v1")
        loader_module = module(plan["loader"], "new2025_full38_loader")
        slots = [slot for slot in kernels.opportunities() if slot["year"] == 2025]
        if slots != plan["fold_opportunities"] or len(slots) != 55 or list(kernels.FEATURES) != plan["features"]:
            raise ValueError("fixed55 opportunities/full38 changed")
        spec = plan["storage"]
        original_store = module(spec["original_helper"], "new2025_original_market_storage")
        wrapper = module(spec["helper"], "new2025_metadata_accounting")
        frozen_store = original_store.load_frozen(str(authenticated(spec["forward_implementation"])), spec["legacy_library_root"])
        cls = wrapper.build_storage_class(original_store.build_storage_class(frozen_store),
                                          json.loads(authenticated(spec["metadata_descriptor"]).read_bytes()))
        storage = cls(spec["legacy_cache"], json.loads(authenticated(spec["market_policy"]).read_bytes()),
                      json.loads(authenticated(spec["legacy_policy"]).read_bytes()), json.loads(authenticated(spec["prior_policy"]).read_bytes()))
        output = Path(plan["output"])
        if output != storage.live_root / "research" / "next-nfl-common2025-technical-v2" or output.exists():
            raise ValueError("fresh approved namespace required")
        storage.register_root(output)
        with storage.transaction():
            storage._require(caps["peak_private_bytes_cap"])
        save("ALL_OPPORTUNITIES_CONSUMED.zip", {"CONSUMED.json": encoded({
            "state": "ALL55_NEW2025_SLOTS_RESERVED_BEFORE_TRAINING_LABEL_DECODE",
            "slots": slots, "plan_sha256": args.sha256, "maximum_forest_fits": 55, "maximum_trees": 1760,
            "old2026_allocations_not_refunded": True, "all55_consumed_even_if_later_failure": True,
            "preserved_v1": plan["preserved_v1"], "new_explicit_technical_budget": True,
            "bootstrap": bootstrap})}, MIB)
        loader = loader_module.CommonLearnerInputs(plan, harness=harness, pa=pa, pq=pq, pd=pd,
                                                   clock_check=cdf_engine.assert_clock_contract)
        query = loader.query(2025)
        frozen = loader.original_cdf_2025()
        original = query[KEYS + CONTEXT].merge(frozen[KEYS + CONTEXT + ["mean", "fallback"]], on=KEYS + CONTEXT,
                    how="left", sort=False, validate="one_to_one")
        if len(original) != 1359 or not np.isfinite(original["mean"].to_numpy(float)).all():
            raise ValueError("complete authentic2025 control mismatch")
        reference = original["mean"].to_numpy(float)
        model_members, forecast_rows, attempted = {}, [], []
        pending = model_members
        def fitted(slot, cutoff):
            nonlocal forests, trees, priors, fit_entries, returned_forests
            if slot["id"] in attempted or slot not in slots:
                raise ValueError("reused/undeclared slot")
            attempted.append(slot["id"])
            train = loader.eligible_training(2025, cutoff, slot["policy"])
            weights = kernels.training_weights(train, fit_cutoff=cutoff, policy=slot["policy"])
            called = False
            def consume_forest(*, maximum_trees):
                nonlocal forests, trees, called
                if called or maximum_trees != 32 or forests >= 55 or trees + 32 > 1760:
                    raise ValueError("forest/tree budget exhausted")
                called = True
                forests += 1
                trees += 32
            # Observe entry to the original sklearn method without replacing
            # it or changing the numerical algorithm. Charged callbacks may
            # precede an actual fit, as the preserved V1 failure demonstrated.
            if sys.getprofile() is not None:
                raise ValueError("unregistered Python profiling callback")
            fit_code = ExtraTreesRegressor.fit.__code__
            def profile(frame, event, arg):
                nonlocal fit_entries
                if event == "call" and frame.f_code is fit_code:
                    estimator = frame.f_locals.get("estimator", frame.f_locals.get("self"))
                    if isinstance(estimator, ExtraTreesRegressor):
                        fit_entries += 1
            sys.setprofile(profile)
            try:
                model = kernels.fit(train, plan["category"], weights, consume_forest=consume_forest)
            finally:
                sys.setprofile(None)
            returned_forests += int(model.forest is not None)
            priors += int(model.global_prior is not None)
            record = {"slot": slot, "cutoff_utc": cutoff.isoformat(), "audit": model.audit,
                "maximum_training_label_available_utc": train.outcome_available_utc.max().isoformat() if len(train) else None}
            if slot["policy"] == kernels.POLICIES[0] and slot["week"] == 1 and (len(train) or called or model.global_prior is not None):
                raise ValueError("first CURRENT_ONLY must have no eligible labels")
            slim = copy.copy(model)
            slim.training_binding = slim.prior_training_binding = slim.training_leaf_ids = None
            out = io.BytesIO()
            joblib.dump(slim, out, compress=3)
            model_members[slot["id"] + "/MODEL.joblib"] = out.getvalue()
            training = train[KEYS + ["position", "kickoff_utc", "cutoff_utc", "outcome_available_utc",
                "feature_max_source_available_utc", "participation_state", "pass_att"]].copy()
            training["sample_weight"] = weights
            model_members[slot["id"] + "/TRAINING_BINDING.parquet"] = frame_bytes(training)
            record["model_sha256"] = sha(model_members[slot["id"] + "/MODEL.joblib"])
            record["training_sha256"] = sha(model_members[slot["id"] + "/TRAINING_BINDING.parquet"])
            audits.append(record)
            model_members[slot["id"] + "/FIT_AUDIT.json"] = encoded(record)
            if sum(map(len, model_members.values())) > caps["forecast_model_capsule_bytes_cap"] - 2 * MIB:
                raise ValueError("complete model cap exhausted; no evidence discarded")
            check()
            return model
        initial = next(s for s in slots if s["policy"] == kernels.POLICIES[0] and s["week"] == 1)
        initial_current = fitted(initial, query.cutoff_utc.min())
        annual = fitted(next(s for s in slots if s["annual"]), query.cutoff_utc.min())
        for week in range(1, 19):
            indices = np.flatnonzero(query.week.eq(week).to_numpy())
            view = query.iloc[indices].reset_index(drop=True)
            if not len(view):
                raise ValueError("registered week absent")
            models = {kernels.POLICIES[3]: annual}
            for policy in kernels.POLICIES[:3]:
                slot = next(s for s in slots if s["week"] == week and s["policy"] == policy and not s["annual"])
                models[policy] = initial_current if week == 1 and policy == kernels.POLICIES[0] else fitted(slot, view.cutoff_utc.min())
            for policy, model in models.items():
                point = np.full(len(view), np.nan)
                fallback = np.full(len(view), "", dtype=object)
                for cutoff, positions in view.groupby("cutoff_utc", sort=False).indices.items():
                    positions = np.asarray(positions)
                    values, reasons = kernels.point_forecasts(model, view.iloc[positions].copy(), policy=policy,
                                                               reference=reference[indices][positions])
                    point[positions], fallback[positions] = values, reasons
                row = view[KEYS + CONTEXT].copy()
                row["method"], row["point"], row["fallback"] = METHODS[policy], point, fallback
                row["modeled_training_rows"] = model.audit["supported_played_training_rows"]
                forecast_rows.append(row)
        if set(attempted) != {s["id"] for s in slots}:
            raise ValueError("all55 opportunities not accounted")
        forecasts = pd.concat(forecast_rows, ignore_index=True)
        recorded_at_utc = pd.Timestamp.now(tz="UTC").isoformat()
        model_members["FORECASTS.parquet"] = frame_bytes(forecasts)
        model_members["MANIFEST.json"] = encoded({"state": "ALL2025_MODELS_AND_FORECASTS_FROZEN_BEFORE_COMPLETE_OUTER_LABEL_DECODE",
            "version": VERSION, "plan_sha256": args.sha256, "complete_outer_label_decodes": 0,
            "earlier_eligible_training_labels_used": True, "opportunities_consumed": 55,
            "forecast_rows": len(forecasts), "offered_unique_rows": len(query), "fit_audits": audits,
            "resources": receipt(), "recorded_at_utc": recorded_at_utc,
            "forecast_sha256": sha(model_members["FORECASTS.parquet"])})
        pending = model_members
        freeze = save("FORECAST_MODELS_FROZEN.zip", pending, caps["forecast_model_capsule_bytes_cap"])
        pending = {}
        model_members = {}
        annual = initial_current = None
        labels = loader.labels(2025, allow_evaluation=True)
        base = labels[KEYS + CONTEXT + ["actual", "participation_state", "label_reason"]].copy()
        if not base[KEYS + CONTEXT].equals(original[KEYS + CONTEXT]):
            raise ValueError("authentic control vector order/context differs from scoring label population")
        merged = base.merge(forecasts, on=KEYS + CONTEXT, how="inner", validate="one_to_many", sort=False)
        control = base.copy()
        control["method"] = "FROZEN_CDF_MEAN"
        control["point"], control["fallback"], control["modeled_training_rows"] = reference, original.fallback.fillna(""), -1
        scored = pd.concat([merged, control], ignore_index=True)
        def metrics(frame):
            y, p = frame.actual.to_numpy(float), frame.point.to_numpy(float)
            good = frame.participation_state.eq("played").to_numpy() & np.isfinite(y) & (y >= 0) & (y == np.floor(y))
            delta = p[good] - y[good]
            absolute = np.abs(delta)
            return {"offered": len(frame), "scored": int(good.sum()), "games": int(frame.loc[good].game_id.nunique()),
                "weeks": int(frame.loc[good].week.nunique()), "played_zero": int((good & (y == 0)).sum()),
                "participation": frame.participation_state.value_counts(dropna=False).to_dict(),
                "played_missing": int((frame.participation_state.eq("played").to_numpy() & ~np.isfinite(y)).sum()),
                "played_invalid": int((frame.participation_state.eq("played").to_numpy() & np.isfinite(y) & ~good).sum()),
                "fallback_offered": int(frame.fallback.ne("").sum()),
                "fallback_scored": int((good & frame.fallback.ne("").to_numpy()).sum()),
                "MAE": float(absolute.mean()), "MSE": float(np.mean(delta ** 2)),
                "RMSE": float(np.sqrt(np.mean(delta ** 2))), "bias": float(delta.mean()),
                "p90_abs": float(np.quantile(absolute, .9, method="linear")),
                "p95_abs": float(np.quantile(absolute, .95, method="linear")), "maximum_abs": float(absolute.max()),
                "error_lt1": float((absolute < 1).mean()), "error_le1": float((absolute <= 1).mean())}
        by_method = {method: frame.reset_index(drop=True) for method, frame in scored.groupby("method", sort=False)}
        for method, frame in by_method.items():
            if len(frame) != 1359 or frame.duplicated(KEYS).any() or not np.isfinite(frame.point.to_numpy(float)).all():
                raise ValueError("same full offered population required")
        summaries = {method: metrics(frame) for method, frame in by_method.items()}
        pairs = []
        contrasts = [(METHODS[p], "FROZEN_CDF_MEAN") for p in kernels.POLICIES]
        contrasts += [(METHODS[p], METHODS[kernels.POLICIES[3]]) for p in kernels.POLICIES[:3]]
        for candidate, comparator in contrasts:
            frame, other = by_method[candidate], by_method[comparator]
            aligned = frame[KEYS + CONTEXT + ["point", "actual", "participation_state", "modeled_training_rows"]].merge(
                other[KEYS + CONTEXT + ["point"]], on=KEYS + CONTEXT, validate="one_to_one",
                suffixes=("_candidate", "_control"))
            y = aligned.actual.to_numpy(float)
            good = aligned.participation_state.eq("played").to_numpy() & np.isfinite(y) & (y >= 0) & (y == np.floor(y))
            aligned["delta_candidate_minus_control"] = (aligned.point_candidate - y) ** 2 - (aligned.point_control - y) ** 2
            warm = good & aligned.modeled_training_rows.ge(60).to_numpy()
            pairs.append({"candidate": candidate, "comparator": comparator, "n": int(good.sum()),
                "MSE_delta_candidate_minus_control": float(aligned.loc[good, "delta_candidate_minus_control"].mean()),
                "relative_improvement_percent": 100 * (summaries[comparator]["MSE"] - summaries[candidate]["MSE"]) / summaries[comparator]["MSE"],
                "adequately_trained_n": int(warm.sum()),
                "adequately_trained_delta_MSE": float(aligned.loc[warm, "delta_candidate_minus_control"].mean()) if warm.any() else None,
                "intervals": [_bootstrap(aligned, good, c, 500, 1703) for c in ["game", "week"]],
                "weekly": [{"week": int(w), "n": int((good & aligned.week.eq(w)).sum()),
                    "MSE_delta": float(aligned.loc[good & aligned.week.eq(w), "delta_candidate_minus_control"].mean())}
                    for w in range(1, 19)]})
        report = {"state": "NEW2025_COMMON_LEARNER_FOUR_HISTORY_COMPARISON_COMPLETE", "version": VERSION,
            "plan_sha256": args.sha256, "forecast_freeze": freeze, "new_fits": forests, "new_trees": trees,
            "new_opportunities_consumed": 55, "source_seasons": "2019-2024 historical cache plus earlier-only2025 labels",
            "evaluation_season": 2025, "weeks": list(range(1, 19)), "summaries": summaries, "paired": pairs,
            "fit_audits": audits, "scientific_evidence_lane": "exposed current-vintage historical reconstruction; old7day assumption preserved",
            "current_role_addition": "NOT_RUN; full38 prior-only state; no verified injury/teammate facts",
            "product": "conditional_on_played_expected_count_mean", "primary_metric": "MSE",
            "website_comparison": "UNAVAILABLE_AUTHENTIC_SAME_CUTOFF_SITE_R0", "new_live_use": False,
            "scope": "fixedlearner/representation, fixed365daydecay, not tunedhalf-life/historyoptimization",
            "selection_multiplicity": "four procedures/seven contrasts; nominal descriptive intervals, not qualification",
            "resources_before_final_persistence": receipt()}
        readable = scored.copy()
        label = readable.actual.to_numpy(float)
        supported = (readable.participation_state.eq("played").to_numpy() & np.isfinite(label)
                     & (label >= 0) & (label == np.floor(label)))
        readable["prediction_mean_attempts"] = readable.point
        readable["actual_attempts"] = readable.actual
        readable["signed_error_attempts"] = np.where(supported, readable.point - readable.actual, np.nan)
        readable["absolute_error_attempts"] = readable.signed_error_attempts.abs()
        readable["squared_error_attempts2"] = readable.signed_error_attempts ** 2
        readable["target"], readable["procedure_version"] = "pass_att", VERSION
        readable["recorded_at_utc"] = recorded_at_utc
        readable["evidence_lane"] = "current-vintage historical reconstruction"
        readable["probabilities_prices"] = "UNAVAILABLE_NOT_CREATED_BY_MEAN_POINT"
        readable["error_state"] = np.select([supported, readable.participation_state.eq("DNP"),
            readable.participation_state.eq("unknown"), readable.participation_state.eq("played") & ~np.isfinite(label)],
            ["SUPPORTED_PLAYED_ERROR", "DNP", "UNKNOWN_PARTICIPATION", "PLAYED_MISSING"],
            default="PLAYED_INVALID")
        pending = {"REPORT.json": encoded(report), "SCORED_ROWS.parquet": frame_bytes(scored),
                   "SCORED_ROWS.csv": readable.to_csv(index=False, na_rep="").encode()}
        score = save("SCORES_COMPLETE.zip", pending, caps["score_capsule_bytes_cap"])
        pending = {}
        native_write("COMPLETE.json", {"state": report["state"], "bindings": retained, "resources": receipt(),
            "managed_write_attempts": writes, "retained_private_charged_bytes": charged + 113,
            "offhost_restore": "UNPROVEN", "new_live_use": False})
        print(json.dumps({"state": report["state"], "forecasts": freeze, "score": score, "resources": receipt()}))
    except BaseException as error:
        failure = {"state": "FAILED_NEW2025_INVOCATION_PRESERVED", "error_type": type(error).__name__,
            "error": str(error), "plan_sha256": args.sha256, "resources": receipt(), "bindings": retained,
            "managed_write_attempts": writes, "retained_charged_bytes": charged}
        native_write("FAILED.json", failure)
        if storage is not None and writes < caps["maximum_managed_write_attempts_including_failure"] and pending:
            try:
                pending["FAILURE.json"] = encoded(failure)
                save("FAILED_PRESERVED.zip", pending, caps["forecast_model_capsule_bytes_cap"])
            except BaseException as recovery:
                native_write("FAILED_RETENTION.json", {"error": str(recovery), "resources": receipt(), "write_attempts": writes})
        native_write("FAILURE_FINALIZER_COMPLETE.json", {"state": "V2_FAILURE_FINALIZER_FINISHED",
            "resources": receipt(), "bindings": retained, "managed_write_attempts": writes,
            "retained_private_charged_bytes_including_v1": charged + 113,
            "old_v1_budget_and_failure": "PRESERVED_NO_REFUND"})
        raise
    finally:
        done.set()
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    main()
