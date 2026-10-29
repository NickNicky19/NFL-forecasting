"""Five missing, exposed-development count-point comparisons; no model fitting.

Four original cached laws are projected to their saved mean/lower median. One
retained attempt law is restored under a separately versioned current runtime.
All point/control vectors are durably frozen before evaluation-label decoding.
This procedure makes no probability, original-runtime reproduction or live claim.
"""
from __future__ import annotations
import argparse
import gzip
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

VERSION = "next-nfl-count-median-completion-v1"
KEYS = ["season", "week", "game_id", "player_id"]
CONTEXT = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
CELLS = [(2025, "pass_att"), (2025, "pass_int"), (2026, "pass_td"),
         (2026, "pass_att"), (2026, "pass_int")]
METHODS = ["CDF_LOWER_MEDIAN", "CDF_LAW_MEAN_POINT", "RECENT3_POINT_CDF_MEAN_FALLBACK",
           "RECENT8_POINT_CDF_MEAN_FALLBACK"]
MIB = 1024 ** 2


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def binding(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}


def read(ref):
    path = Path(ref["path"])
    if (not path.is_absolute() or path.resolve() != path
            or any(p.is_symlink() for p in (path, *path.parents)) or ref["bytes"] > 16 * MIB):
        raise ValueError("bounded canonical original reference required")
    before = path.stat()
    body = path.read_bytes()
    after = path.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or len(body) != ref["bytes"] or sha(body) != ref["sha256"]):
        raise ValueError("pinned reference changed: " + str(path))
    return body


def module(ref, name, package=None):
    read(ref)
    spec = importlib.util.spec_from_file_location(name, ref["path"])
    result = importlib.util.module_from_spec(spec)
    if package:
        result.__package__ = package
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def capsule(items):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, body in sorted(items.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 28, 0, 0, 0))
            archive.writestr(info, body)
    return stream.getvalue()


def frame_bytes(frame):
    stream = io.BytesIO()
    frame = frame.copy()
    frame.attrs.clear()
    frame.to_parquet(stream, index=False, compression="zstd")
    return stream.getvalue()


def bootstrap(pins):
    import ctypes
    for ref in pins.values():
        read(ref)
    import threadpoolctl
    if Path(threadpoolctl.__file__).resolve() != Path(pins["threadpoolctl"]["path"]):
        raise ValueError("pinned threadpoolctl origin required")
    libc = Path(pins["libc"]["path"])
    mapped = {str(Path(line.split()[5]).resolve()) for line in Path("/proc/self/maps").read_text().splitlines()
              if len(line.split()) == 6 and line.split()[5].startswith("/")}
    if str(libc) not in mapped or not hasattr(os, "RTLD_NOLOAD"):
        raise ValueError("pinned libc must already be mapped")
    handle = ctypes.CDLL(str(libc), mode=os.RTLD_NOLOAD)
    cache = threadpoolctl.ThreadpoolController._system_libraries
    if cache.get("libc") is not None and cache["libc"]._handle != handle._handle:
        raise ValueError("unexpected preexisting libc handle")
    cache["libc"] = handle
    return {"state": "PINNED_ALREADY_MAPPED_LIBC_CACHED", "children": 0}


def validate(plan, *, sealed):
    if (plan["version"] != VERSION or [(x["year"], x["target"]) for x in plan["cells"]] != CELLS
            or plan["resources"] != {"CPU_seconds": 120, "wall_seconds": 180, "RSS_bytes": 768 * MIB,
                "retained_private_bytes_cap": 4 * MIB, "peak_private_bytes_cap": 8 * MIB,
                "native_control_bytes_cap": 256 * 1024, "maximum_managed_write_attempts_including_failure": 2,
                "model_loads": 1, "fixture_replays": 1, "law_query_rows": 515,
                "cached_extractions": 4, "fits": 0, "new_priors": 0, "HTTP_calls": 0,
                "automatic_retries": 0, "startup_threads": 1, "native_numerical_threads": 2,
                "bootstrap_replicates": 500, "bootstrap_seed": 1703}
            or plan["label_freeze_rule"] != "ALL_FIVE_COMPLETE_POINT_VECTORS_READ_BACK_BEFORE_LABEL_DECODE"):
        raise ValueError("exact finite five-cell registration required")
    if sealed and (plan["state"] != "ROOT_AND_REVIEWER_SEALED" or plan["review"] != "PREEXEC_PASS"
            or plan["execution_authorized"] is not True or plan["root_registration"] != {
                "registered_by": "/root", "previous_managed_writer_closed": True}):
        raise ValueError("separate root/reviewer seal required")
    if Path(plan["worker"]["path"]).resolve() != Path(__file__).resolve():
        raise ValueError("exact current worker identity required")
    for ref in [plan["worker"], plan["original_API"], plan["law_helper"],
                *plan["implementation_bindings"], *plan["storage"].values()]:
        if isinstance(ref, dict) and "path" in ref:
            read(ref)
    for ref in [*plan["inputs"].values(), *plan["cached_forecasts"].values(),
                *plan["library_source_bindings"]]:
        read(ref)  # byte authentication only; no Parquet/model/label decode
    return {"state": "METADATA_VALIDATED", "NFL_value_decodes": 0, "model_loads": 0, "fits": 0}


def validate_go(document, plan_hash):
    if document != {"state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": plan_hash,
                    "scope": "ONE_COUNT_MEDIAN_COMPLETION", "previous_managed_writer_closed": True}:
        raise ValueError("exact independent root GO required before any NFL value decoding")


def fictional(plan):
    """Bounded child-free bootstrap/median dispatch check with invented values."""
    bootstrap(plan["technical_bootstrap"])
    import numpy as np
    helper = module(plan["law_helper"], "count_median_original_helper_fixture")
    class Law:
        mean = np.asarray([1.0, 2.0])
        def quantile(self, p):
            if p != .5:
                raise ValueError("fictional quantile")
            return np.asarray([1.0, 2.0])
        def cdf(self, values):
            return np.where(np.asarray(values) >= [1.0, 2.0], .75, .25)
    law, counter = Law(), {}
    mean, median, calls = helper.full_law_products(np, law, counter)
    if calls != 2 or "cdf" in vars(law) or not np.array_equal(mean, median):
        raise ValueError("fictional median delegation differs")
    expected_go = {"state": "GO", "root": "/root", "independent_review": "PASS", "plan_sha256": "fictional",
                   "scope": "ONE_COUNT_MEDIAN_COMPLETION", "previous_managed_writer_closed": True}
    validate_go(expected_go, "fictional")
    try:
        validate_go({**expected_go, "scope": "WRONG"}, "fictional")
    except ValueError:
        pass
    else:
        raise ValueError("fictional incorrect GO scope was admitted")
    return {"state": "FICTIONAL_STARTUP_AND_MEDIAN_DISPATCH_PASS", "NFL_value_decodes": 0,
            "model_loads": 0, "fits": 0, "managed_writes": 0, "CDF_calls": calls,
            "worker_sha256": plan["worker"]["sha256"], "fixture_origin": "INVENTED_NO_NFL_EVIDENCE"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go")
    parser.add_argument("--fictional-check", action="store_true")
    parser.add_argument("--validate-plan", action="store_true")
    args = parser.parse_args()
    raw = Path(args.plan).read_bytes()
    if sha(raw) != args.sha256:
        raise ValueError("exact plan hash required")
    plan = json.loads(raw)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "ARROW_NUM_THREADS"):
        os.environ[key] = "1"
    sys.dont_write_bytecode = True
    if args.validate_plan:
        print(json.dumps(validate(plan, sealed=False)))
        return 0
    def deny(event, unused):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}:
            raise ValueError("offline child-free point comparison required")
    sys.addaudithook(deny)
    if args.fictional_check:
        validate(plan, sealed=False)
        print(json.dumps(fictional(plan)))
        return 0
    validate(plan, sealed=True)
    if not args.go:
        raise ValueError("separate root GO path required")
    validate_go(json.loads(Path(args.go).read_bytes()), args.sha256)
    started, cpu, done = time.monotonic(), time.process_time(), threading.Event()
    caps = plan["resources"]
    resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
    class Stop(BaseException):
        pass
    def absolute(*unused):
        os._exit(124)
    def stop(*unused):
        signal.signal(signal.SIGALRM, absolute)
        signal.setitimer(signal.ITIMER_REAL, max(.001, 180 - (time.monotonic() - started)))
        raise Stop("finite count median allocation consumed")
    for sig in (signal.SIGALRM, signal.SIGXCPU, signal.SIGUSR1):
        signal.signal(sig, stop)
    signal.setitimer(signal.ITIMER_REAL, 170)
    def check():
        if (time.monotonic() - started >= 170 or time.process_time() - cpu >= 118
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > caps["RSS_bytes"]):
            raise Stop("finite CPU/wall/RSS allocation exhausted")
    def watch():
        while not done.wait(.1):
            try:
                check()
            except BaseException:
                os.kill(os.getpid(), signal.SIGUSR1)
                return
    threading.Thread(target=watch, daemon=True).start()
    native = Path(plan["native_control_root"])
    if native.exists():
        raise ValueError("one-invocation native namespace already consumed")
    native.mkdir(parents=True)
    native_bytes = writes = retained = loads = fixtures = cached = law_rows = law_batches = cdf_calls = 0
    storage = None
    references = {}
    def native_write(name, obj):
        nonlocal native_bytes
        body = encoded(obj)
        if native_bytes + len(body) > caps["native_control_bytes_cap"]:
            raise ValueError("native metadata cap exhausted")
        with (native / name).open("xb") as stream:
            stream.write(body)
        native_bytes += len(body)
    def usage():
        return {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "model_loads": loads, "fixture_replays": fixtures, "cached_extractions": cached,
                "law_query_rows": law_rows, "law_batches": law_batches, "CDF_calls": cdf_calls,
                "managed_write_attempts": writes, "fits": 0, "new_priors": 0, "HTTP_calls": 0,
                "automatic_retries": 0}
    native_write("CONSUMED.json", {"state": "ONE_COUNT_MEDIAN_INVOCATION_CONSUMED", "plan_sha256": args.sha256,
                 "old_budgets_and_failures_unchanged": True, "resources": caps})
    def save(name, members):
        nonlocal writes, retained
        body = capsule(members)
        if (storage is None or writes >= 2 or retained + len(body) + 256 * 1024 > 4 * MIB
                or retained + 2 * len(body) + 256 * 1024 > 8 * MIB):
            raise ValueError("complete retained/peak/CAS-call allocation exhausted")
        writes += 1
        retained += len(body)
        path = Path(plan["output"]) / name
        storage.write_bytes(path, body)
        checked = storage.validate_reference(path)
        if path.read_bytes() != body:
            raise ValueError("durable byte readback differs")
        with zipfile.ZipFile(path) as archive:
            if set(archive.namelist()) != set(members) or any(archive.read(k) != v for k, v in members.items()):
                raise ValueError("durable inner member readback differs")
        references[name] = {k: checked[k] for k in ("path", "bytes", "sha256")}
        native_write(name.replace(".zip", "_READBACK.json"), {
            "binding": references[name], "member_bindings": {k: {"bytes": len(v), "sha256": sha(v)} for k, v in members.items()},
            "bytes_exact": True, "usage": usage()})
        check()
        return references[name]
    failure = None
    try:
        boot = bootstrap(plan["technical_bootstrap"])
        acceptance = json.loads(read(plan["fictional_acceptance"]))
        if acceptance["state"] != "FICTIONAL_STARTUP_AND_MEDIAN_DISPATCH_PASS" or acceptance["worker_sha256"] != plan["worker"]["sha256"]:
            raise ValueError("exact fictional startup receipt required")
        if sys.version != plan["python_version"] or binding(Path(sys.executable).resolve()) != plan["python_binary"]:
            raise ValueError("versioned new runtime Python differs")
        for name, version in plan["environment_versions"].items():
            if importlib.metadata.version(name) != version:
                raise ValueError("versioned numerical dependency differs: " + name)
        sys.path.insert(0, plan["library_root"])
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        import joblib
        from nfl_lab import cdf_engine
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        for ref in plan["library_source_bindings"]:
            read(ref)
        original = module(plan["storage"]["original_helper"], "count_median_original_market_store")
        wrapper = module(plan["storage"]["helper"], "count_median_metadata_accounting")
        sp = plan["storage"]
        base = original.load_frozen(sp["forward_implementation"]["path"], sp["legacy_library_root"])
        cls = wrapper.build_storage_class(original.build_storage_class(base), json.loads(read(sp["metadata_descriptor"])))
        storage = cls(sp["legacy_cache"], json.loads(read(sp["market_policy"])),
                      json.loads(read(sp["legacy_policy"])), json.loads(read(sp["prior_policy"])))
        output = Path(plan["output"])
        if output != storage.live_root / "research" / VERSION or output.exists():
            raise ValueError("fresh approved private namespace required")
        storage.register_root(output)
        with storage.transaction():
            storage._refresh()
            capacity = storage._require(8 * MIB)
        api = module(plan["original_API"], "count_median_original_API", package="nfl_lab")
        helper = module(plan["law_helper"], "count_median_original_law_helper")
        def table(ref, columns, *, filters=None):
            return pq.read_table(pa.BufferReader(read(ref)), columns=columns, filters=filters, use_threads=False).to_pandas()
        def context(frame, year):
            frame = frame.reset_index(drop=True)
            for clock in ("kickoff_utc", "cutoff_utc"):
                frame[clock] = pd.to_datetime(frame[clock], utc=True, errors="raise")
            if (frame[KEYS + CONTEXT].isna().any(axis=None) or frame.duplicated(KEYS).any()
                    or not frame.position.eq("QB").all() or not frame.season.eq(year).all()
                    or not frame.week.between(1, 18 if year == 2025 else 6).all()
                    or frame.cutoff_utc.gt(frame.kickoff_utc).any()):
                raise ValueError("complete QB context/period contract differs")
            return frame
        model_manifest = json.loads(read(plan["inputs"]["artifact_2026_att"]))
        feature_columns = model_manifest["features"]
        query_columns = list(dict.fromkeys(KEYS + CONTEXT + ["feature_max_source_available_utc"] + feature_columns))
        queries = {}
        for year, rows in ((2025, 1359), (2026, 515)):
            query = context(table(plan["inputs"]["query_" + str(year)], query_columns,
                filters=[("season", "=", year), ("position", "=", "QB"), ("week", ">=", 1), ("week", "<=", 18 if year == 2025 else 6)]), year)
            source = pd.to_datetime(query.feature_max_source_available_utc, utc=True, errors="coerce")
            warm = cdf_engine.numeric(query, "f_player_games_prior") > 0
            if len(query) != rows or (source.isna().to_numpy() & warm).any() or (source.notna() & ~source.lt(query.cutoff_utc)).any():
                raise ValueError("original complete query or reconstructed source cutoff differs")
            queries[year] = query
        freeze_manifest = json.loads(read(plan["inputs"]["original_forecast_freeze"]))
        scored_manifest = json.loads(read(plan["inputs"]["original_scored_freeze"]))
        frames, extraction_audits = {}, []
        for cell in plan["cells"]:
            year, target = cell["year"], cell["target"]
            q = queries[year]
            if (year, target) != (2026, "pass_att"):
                ref = plan["cached_forecasts"][str(year) + "/" + target]
                relative = str(Path(ref["path"]).relative_to(plan["original_expansion_root"]))
                if freeze_manifest["bindings"][relative] != ref["sha256"]:
                    raise ValueError("cached original forecast is not in original freeze")
                # Explicit column projection excludes every outcome-derived proper score/CDF field.
                cached += 1
                f = context(table(ref, KEYS + CONTEXT + ["mean", "median", "fallback", "target", "method"],
                    filters=[("position", "=", "QB")]), year)
                if not f.target.eq(target).all() or not f.method.eq("LAB_CDF").all():
                    raise ValueError("cached target/method differs")
                f = q[KEYS + CONTEXT].merge(f, on=KEYS + CONTEXT, how="left", sort=False, validate="one_to_one")
                if len(f) != len(q) or not np.isfinite(f[["mean", "median"]].to_numpy(float)).all():
                    raise ValueError("cached full-population point projection differs")
            else:
                loads += 1
                bundle = joblib.load(io.BytesIO(read(plan["inputs"]["model_2026_att"])))
                model, fixture = bundle["model"], bundle["fixture"]
                if (bundle["base_artifact_sha256"] is not None or len(fixture) > 4
                        or api.model_contract(model, "leaf_cdf_base") != (model_manifest["category"], feature_columns)
                        or model_manifest["code_pins"] != api.code_pins()
                        or api.frame_digest(fixture) != model_manifest["replay_fixture_sha256"]):
                    raise ValueError("retained model/schema/original fixture contract differs")
                fixtures += 1
                bits = api.prediction_bits(model, "leaf_cdf_base", fixture)
                if bits != bundle["expected_bits"] or api.digest(bits) != model_manifest["replay_bits_sha256"]:
                    raise ValueError("original fixture exact bits do not reproduce under the separately versioned runtime")
                if (pd.Timestamp(model_manifest["training_cutoff_utc"]) > q.cutoff_utc.min()
                        or not pd.Timestamp(model_manifest["training_max_available_utc"]) < pd.Timestamp(model_manifest["training_cutoff_utc"])):
                    raise ValueError("retained model training cutoff differs")
                f = q[KEYS + CONTEXT].copy()
                f["mean"], f["median"], f["fallback"] = np.nan, np.nan, ""
                for cutoff, ix in q.groupby("cutoff_utc", sort=False).indices.items():
                    check()
                    ix = np.asarray(ix)
                    selected = q.iloc[ix].copy().reset_index(drop=True)
                    law_rows += len(selected)
                    if law_rows > 515:
                        raise ValueError("law query incidence cap exceeded")
                    for indices, law, fallback in model.predict_batches(selected, batch_size=256):
                        law_batches += 1
                        positions = ix[np.asarray(indices)]
                        f.loc[positions, "fallback"] = fallback
                        if law is None:
                            raise ValueError("retained QB law unexpectedly absent")
                        counter = {}
                        means, medians, calls = helper.full_law_products(np, law, counter)
                        cdf_calls += calls
                        f.loc[positions, "mean"], f.loc[positions, "median"] = means, medians
                with zipfile.ZipFile(io.BytesIO(read(plan["inputs"]["retained_2026_att_mean_freeze"]))) as archive:
                    old = context(pq.read_table(pa.BufferReader(archive.read("FORECASTS.parquet")),
                        columns=KEYS + CONTEXT + ["point", "fallback", "primary_role"], use_threads=False).to_pandas()
                        .loc[lambda d: d.position.eq("QB")], 2026)
                old = q[KEYS + CONTEXT].merge(old, on=KEYS + CONTEXT, how="left", validate="one_to_one", sort=False)
                if (not np.isfinite(f[["mean", "median"]].to_numpy(float)).all()
                        or not np.array_equal(f["mean"].to_numpy(dtype="<f8").view("<u8"), old.point.to_numpy(dtype="<f8").view("<u8"))
                        or not f.fallback.fillna("").equals(old.fallback.fillna(""))):
                    raise ValueError("separately restored query means/fallbacks differ from compatible retained control")
            if (f["mean"].lt(0).any() or f["median"].lt(0).any()
                    or not np.equal(f["median"], np.floor(f["median"])).all()):
                raise ValueError("count point support differs")
            base = q[KEYS + CONTEXT].copy()
            out = []
            for name, column in ((METHODS[0], "median"), (METHODS[1], "mean")):
                arm = base.copy()
                arm["point"], arm["fallback"], arm["method"] = f[column].to_numpy(), f.fallback.fillna("").to_numpy(), name
                out.append(arm)
            for window in (3, 8):
                values = cdf_engine.numeric(q, "f_player_" + target + "_mean" + str(window))
                count = cdf_engine.numeric(q, "f_player_" + target + "_n" + str(window))
                good = np.isfinite(values) & (values >= 0) & (count > 0)
                arm = base.copy()
                arm["point"] = np.where(good, values, f["mean"].to_numpy(float))
                arm["fallback"] = np.where(good, "", "no_supported_recent_history_CDF_mean")
                arm["method"] = METHODS[2 if window == 3 else 3]
                out.append(arm)
            if target == "pass_int":
                arm = base.copy()
                arm["point"], arm["fallback"], arm["method"] = 0., "", "ZERO_INTERCEPTION_POINT_NOT_PROBABILITY"
                out.append(arm)
            combined = pd.concat(out, ignore_index=True)
            combined["target"] = target
            combined["evidence_lane"] = "EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION"
            frames[(year, target)] = combined
            extraction_audits.append({"year": year, "target": target, "offered_rows": len(q),
                "method_rows": len(combined), "provenance": "NEW_RETAINED_LAW_QUERY" if (year,target)==(2026,"pass_att") else "ORIGINAL_CACHED_FORECAST_PROJECTION"})
        all_forecasts = pd.concat(list(frames.values()), ignore_index=True)
        forecast = save("FORECASTS_FROZEN.zip", {"FORECASTS.parquet": frame_bytes(all_forecasts), "MANIFEST.json": encoded({
            "state": "ALL_FIVE_COMPLETE_POINT_VECTORS_READ_BACK_BEFORE_LABEL_DECODE", "plan_sha256": args.sha256,
            "version": VERSION, "label_decodes": 0, "extraction_audits": extraction_audits, "bootstrap": boot,
            "capacity": capacity, "usage": usage(), "old_runtime_reproduction_claim": False})})
        # No outcome value or qualification state is decoded above this durable readback.
        source_2026 = json.loads(gzip.decompress(read(plan["inputs"]["qualified_2026_W1_6"])), parse_int=str, parse_float=str)
        qualified = source_2026["qualification"]["records"]
        graded, result_cells = [], []
        def metrics(frame):
            y = pd.to_numeric(frame.actual, errors="coerce").to_numpy(float)
            p = frame.point.to_numpy(float)
            good = frame.participation_state.eq("played").to_numpy() & np.isfinite(y) & np.isfinite(p)
            e = p[good] - y[good]
            a = np.abs(e)
            return {"offered_rows": len(frame), "scored_rows": int(good.sum()), "games": int(frame.loc[good,"game_id"].nunique()),
                "weeks": int(frame.loc[good,"week"].nunique()), "fallback_rows": int(frame.fallback.fillna("").ne("").sum()),
                "scored_fallback_rows": int((good & frame.fallback.fillna("").ne("").to_numpy()).sum()),
                "participation_states": {str(k): int(v) for k,v in frame.participation_state.value_counts(dropna=False).items()},
                "played_missing_rows": int((frame.participation_state.eq("played") & ~np.isfinite(y)).sum()),
                "played_zero_rows": int((frame.participation_state.eq("played") & (y==0)).sum()),
                "MAE": float(a.mean()) if len(a) else None, "MSE": float((e**2).mean()) if len(a) else None,
                "RMSE": float(np.sqrt((e**2).mean())) if len(a) else None,
                "bias": float(e.mean()) if len(a) else None,
                "p90_absolute_error": float(np.quantile(a,.9)) if len(a) else None,
                "p95_absolute_error": float(np.quantile(a,.95)) if len(a) else None,
                "error_lt_1": float((a<1).mean()) if len(a) else None,
                "error_le_1": float((a<=1).mean()) if len(a) else None}
        def paired(candidate, control, cluster):
            fields = KEYS + ["actual", "participation_state", "point"]
            f = candidate[fields].merge(control[fields], on=KEYS, suffixes=("_c","_b"), validate="one_to_one", how="inner")
            yc = pd.to_numeric(f.actual_c,errors="coerce").to_numpy(float)
            yb = pd.to_numeric(f.actual_b,errors="coerce").to_numpy(float)
            good = f.participation_state_c.eq("played").to_numpy() & f.participation_state_b.eq("played").to_numpy() & np.isfinite(yc) & np.isfinite(yb)
            if not np.array_equal(yc[good], yb[good]):
                raise ValueError("paired outcome values differ")
            f = f.loc[good].copy()
            d = np.abs(f.point_c.to_numpy(float)-yc[good])-np.abs(f.point_b.to_numpy(float)-yb[good])
            f["delta"],f["n"] = d,1
            g=f.groupby(cluster,sort=True)[["delta","n"]].sum()
            interval=None
            if len(g)>=8:
                rng=np.random.default_rng(1703)
                x=g.to_numpy(float); estimates=[]
                for _ in range(500):
                    s=x[rng.integers(0,len(x),len(x))].sum(axis=0)
                    estimates.append(float(s[0]/s[1]))
                interval=[float(x) for x in np.quantile(estimates,[.025,.975])]
            return {"paired_rows":len(f),"cluster":cluster,"clusters":len(g),"candidate_minus_control_MAE":float(d.mean()),
                    "nominal_exposed_development_95pct_interval":interval,"minimum_clusters":8,"replicates":500,"seed":1703}
        for year,target in CELLS:
            q=queries[year]
            source_context_mismatches=0
            if year==2025:
                ref=plan["inputs"]["outcome_2025_"+target]
                relative=str(Path(ref["path"]).relative_to(plan["original_expansion_root"]))
                if (scored_manifest["bindings"].get(relative) or freeze_manifest["bindings"].get(relative))!=ref["sha256"]:
                    raise ValueError("original2025 outcome not bound by original freeze")
                labels=context(table(ref,KEYS+CONTEXT+["participation_state","actual"],filters=[("position","=","QB")]),year)
                labels=q[KEYS+CONTEXT].merge(labels,on=KEYS+CONTEXT,how="left",sort=False,validate="one_to_one")
            else:
                contexts={tuple(row[k] for k in KEYS):row for row in q[KEYS+CONTEXT].to_dict("records")}
                rows,seen=[],set()
                for row in qualified:
                    if row["target"]!=target:
                        continue
                    season,week=int(row["season"]),int(row["week"])
                    if season!=2026 or not 1<=week<=6:
                        raise ValueError("protected or unexpected qualified source period")
                    key=(season,week,row["game_id"],row["player_id"])
                    if key not in contexts:
                        continue
                    if key in seen:
                        raise ValueError("duplicate qualified source target key")
                    seen.add(key)
                    offered=contexts[key]
                    valid=(row["team"]==offered["team"] and row["opponent"]==offered["opponent"]
                           and pd.Timestamp(row["kickoff_utc"])==pd.Timestamp(offered["kickoff_utc"]))
                    source_context_mismatches+=int(not valid)
                    state,actual="unknown",None
                    if valid:
                        state,actual=row["participation_state"],row["actual"]
                        if state not in {"played","unknown"} or (state!="played" and actual is not None):
                            raise ValueError("unsupported qualification state/count pairing")
                        actual=None if actual is None else float(actual)
                    rows.append({**offered,"participation_state":state,"actual":actual})
                for key,row in contexts.items():
                    if key not in seen:
                        rows.append({**row,"participation_state":"unknown","actual":None})
                labels=context(pd.DataFrame(rows),year)
                labels=q[KEYS+CONTEXT].merge(labels,on=KEYS+CONTEXT,how="left",sort=False,validate="one_to_one")
            # Preserve any raw source statistic that lacks independent played
            # evidence, without allowing it to become an evaluated zero.
            labels["retained_source_actual"]=labels.actual.copy()
            raw_numeric=pd.to_numeric(labels.actual,errors="coerce").notna()
            quarantined=raw_numeric & labels.participation_state.ne("played")
            labels["label_qualification"]=np.where(labels.participation_state.eq("played"),
                "independently_played",np.where(quarantined,"raw_count_without_played_evidence_quarantined","unknown_or_nonplayed"))
            labels.loc[labels.participation_state.ne("played"),"actual"]=np.nan
            y=pd.to_numeric(labels.actual,errors="coerce").to_numpy(float)
            numeric=np.isfinite(y)
            if (labels.participation_state.isna().any() or (numeric & ~labels.participation_state.eq("played").to_numpy()).any()
                    or not cdf_engine.valid_support(y[numeric],"count").all()):
                raise ValueError("unsupported participation/label/count support")
            admitted={"offered_rows":len(labels),"scorable_played_numeric":int((numeric & labels.participation_state.eq("played").to_numpy()).sum()),
                "unknown_rows":int(labels.participation_state.eq("unknown").sum()),"raw_numeric_nonplayed_quarantined":int(quarantined.sum()),
                "source_context_mismatches_quarantined":source_context_mismatches,
                "participation_states":{str(k):int(v) for k,v in labels.participation_state.value_counts(dropna=False).items()}}
            expected=next(c["expected_label_population"] for c in plan["cells"] if (c["year"],c["target"])==(year,target))
            if any(admitted[name]!=value for name,value in expected.items()):
                raise ValueError("predeclared full/matched scorable label population differs")
            native_write(str(year)+"_"+target+"_LABEL_ADMISSION.json",{
                "state":"LABEL_POPULATION_ADMITTED_BEFORE_SCORING","forecast_freeze":forecast,"counts":admitted,
                "participation_overrides":0,"raw_unqualified_count_zero_promotions":0})
            full=frames[(year,target)].merge(labels,on=KEYS+CONTEXT,how="left",sort=False,validate="many_to_one")
            bymethod={name:f.copy() for name,f in full.groupby("method",sort=True)}
            summaries={name:metrics(f) for name,f in bymethod.items()}
            for name,f in bymethod.items():
                if len(f)!=len(q):
                    raise ValueError("full-population method coverage differs")
            pairs=[]
            for candidate in bymethod:
                if candidate==METHODS[1]:
                    continue
                base=summaries[METHODS[1]]["MAE"]
                pairs.append({"candidate":candidate,"control":METHODS[1],"primary":"MAE",
                    "signed_improvement_percent":None if base==0 else 100*(base-summaries[candidate]["MAE"])/base,
                    "game":paired(bymethod[candidate],bymethod[METHODS[1]],"game_id"),
                    "week":paired(bymethod[candidate],bymethod[METHODS[1]],"week")})
            weekly={str(int(week)):{name:metrics(f.loc[f.week.eq(week)]) for name,f in bymethod.items()}
                    for week in sorted(q.week.unique())}
            result_cells.append({"year":year,"target":target,"primary":"MAE_POINT_ONLY","summaries":summaries,
                "label_admission":admitted,"paired_against_CDF_mean":pairs,"weekly":weekly,"lowest_observed_MAE_method":min(summaries,key=lambda k:(summaries[k]["MAE"],k)),
                "comparison_scope":"matched original complete QB query; exposed current-vintage reconstruction; not SITE/R0-relative"})
            full["absolute_error"]=np.abs(full.point-pd.to_numeric(full.actual,errors="coerce"))
            graded.append(full)
            check()
        result={"version":VERSION,"state":"COUNT_MEDIAN_COMPARISONS_COMPLETE","forecast_freeze":forecast,
            "cells":result_cells,"usage":usage(),"actual_backend":"UNATTESTED","new_predictive_fits":0,
            "cached_rescoring_cells":4,"retained_model_inference_cells":1,"probability_accuracy_claims":False,
            "old_studies_and_scientific_gates_unchanged":True,"live_deployment":False,
            "limitations":["Exposed development; nominal unadjusted selected-winner uncertainty",
                "Original seven-day historical availability assumption/current-vintage inputs unchanged",
                "Complete query population retains unknowns; unknown participation is not zero",
                "No archived historical SITE/R0 controls; no website-relative improvement claim",
                "Count means are also shown as point controls; mean/median products remain separate",
                "Zero-interception point control is not a zero interception probability"]}
        saved=save("GRADE_COMPLETE.zip",{"RESULT.json":encoded(result),"GRADED_ROWS.parquet":frame_bytes(pd.concat(graded,ignore_index=True))})
        native_write("SUCCESS.json",{"state":result["state"],"forecast_freeze":forecast,"result":saved,"usage":usage()})
        print(json.dumps({"state":result["state"],"forecast_freeze":forecast,"result":saved,"usage":usage()}))
    except BaseException as error:
        failure=error
        record={"state":"COUNT_MEDIAN_COMPARISON_FAILED","type":type(error).__name__,"message":str(error),
                "usage":usage(),"retained":references,"plan_sha256":args.sha256,"automatic_retries":0}
        native_write("FAILURE.json",record)
        if storage is not None and writes<2:
            try:
                save("FAILURE.zip",{"FAILURE.json":encoded(record)})
            except BaseException as secondary:
                native_write("FAILURE_RETENTION_FAILURE.json",{"type":type(secondary).__name__,"message":str(secondary),"usage":usage()})
        print(json.dumps(record))
    finally:
        done.set()
        signal.setitimer(signal.ITIMER_REAL,0)
    return 0 if failure is None else 1


if __name__=="__main__":
    raise SystemExit(main())
