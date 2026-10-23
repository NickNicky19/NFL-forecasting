"""One frozen, nonissued reference acceptance; no acquisition or accuracy scoring.

Only this opt-in runner is new. Frozen source, feature, model and quota helpers
retain their original behavior. Fresh replay is read only and deliberately does
not construct OperationalStorage: a new storage scan would reread source blobs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time
from unittest.mock import patch

COLUMNS = ("mean", "scale", "family", "p10", "p50", "p90", "p_participation", "fallback")
NUMERIC = ("mean", "scale", "p10", "p50", "p90", "p_participation")
REGISTRATION = "permitted-reference-runtime-v2-20261023"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


class StateBoundStorage:
    """Add the separate logical state ceiling to the existing global writer."""

    def __init__(self, storage, state, limit=200 * 1024 * 1024):
        self.storage = storage
        self.state = Path(state).absolute()
        self.limit = min(int(limit), 200 * 1024 * 1024)

    def __getattr__(self, name):
        return getattr(self.storage, name)

    def write_bytes(self, path, body, *, replace=False):
        path, body = Path(path).absolute(), bytes(body)
        with self.storage.transaction():
            if path == self.state or self.state in path.parents:
                incoming = len(body)
                if path.exists():
                    try:
                        self.storage.validate_reference(path, expected_sha256=hashlib.sha256(body).hexdigest())
                    except (ValueError, OSError):
                        pass
                    else:
                        incoming = 0
                retained = sum(p.stat().st_size for p in self.state.rglob("*") if p.is_file())
                if retained + incoming > self.limit:
                    from .operational_storage import StorageQuotaError
                    raise StorageQuotaError("exact serialized state model/temp peak exceeds 200MiB; evidence retained")
            return self.storage.write_bytes(path, body, replace=replace)

    def atomic_json(self, path, value, *, replace=False):
        self.write_bytes(path, _json(value), replace=replace)


class _Budget:
    def __init__(self, config):
        self.budgets = config["budgets"]
        self.started = time.monotonic()
        self.cpu_started = self.cpu()
        self.rows = 0
        self.returned_rows = 0
        self.fits = 0

    @staticmethod
    def cpu():
        return sum(resource.getrusage(which).ru_utime + resource.getrusage(which).ru_stime
                   for which in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN))

    def usage(self):
        return {"wall_seconds": time.monotonic() - self.started,
                "CPU_seconds": self.cpu() - self.cpu_started,
                "RSS_accounting": "maximum single-process high-water; outer supervisor enforces combined process tree",
                "max_RSS_bytes": 1024 * max(resource.getrusage(which).ru_maxrss
                    for which in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN)),
                "reference_parameter_fits": self.fits,
                "estimator_fits": 0, "query_forecast_route_budget_charges": self.rows,
                "successfully_returned_query_row_incidences": self.returned_rows}

    def produced(self, rows):
        self.returned_rows += rows

    def check(self, *, rows=0, fit=False):
        self.rows += rows
        self.fits += int(fit)
        used = self.usage()
        b = self.budgets
        if (used["wall_seconds"] > b["max_wall_seconds"] - b["reporting_reserve_seconds"]
                or used["CPU_seconds"] > b["max_CPU_seconds"]
                or used["max_RSS_bytes"] > b["max_RSS_bytes"]
                or self.rows > b["max_model_prediction_row_incidences"]
                or self.fits > b["max_reference_parameter_fits"]):
            raise RuntimeError("frozen cumulative runtime budget exhausted; consumed slots retained")


@contextmanager
def _deadline(seconds):
    def expired(signum, frame):
        raise TimeoutError("frozen reference package wall deadline exceeded")
    previous = signal.signal(signal.SIGALRM, expired)
    old = signal.setitimer(signal.ITIMER_REAL, max(.001, seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def _no_fits(*, core=True):
    from contextlib import ExitStack
    from . import models
    def forbidden(*args, **kwargs):
        raise AssertionError("fitting is forbidden in this acceptance phase")
    with ExitStack() as stack:
        if core:
            stack.enter_context(patch.object(models, "fit_predict", forbidden))
        for cls in (models.LogisticRegression, models.Ridge, models.PoissonRegressor, models.ExtraTreesRegressor):
            stack.enter_context(patch.object(cls, "fit", forbidden))
        yield


def _same(expected, actual):
    import numpy as np
    if list(expected.columns) != list(COLUMNS) or list(actual.columns) != list(COLUMNS):
        raise ValueError("forecast schema changed")
    if len(expected) != len(actual) or not expected.index.equals(actual.index):
        raise ValueError("forecast row/order/index changed")
    for name in NUMERIC:
        if not np.allclose(expected[name].to_numpy(dtype=float), actual[name].to_numpy(dtype=float),
                           rtol=1e-10, atol=1e-9, equal_nan=True):
            raise ValueError("reference replay numeric mismatch: " + name)
    for name in ("family", "fallback"):
        if expected[name].tolist() != actual[name].tolist():
            raise ValueError("reference replay string mismatch: " + name)
    if not expected.p_participation.isna().all() or not actual.p_participation.isna().all():
        raise ValueError("participation probability must remain unavailable")


def _validate_output(frame, target):
    """Check supported distribution outputs; this does not claim calibration."""
    import numpy as np
    from .models import COUNT_TARGETS
    values = frame[["mean", "scale", "p10", "p50", "p90"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, 1] < 0).any():
        raise ValueError("supported reference must emit finite parameters and nonnegative scale")
    if ((values[:, 2] > values[:, 3]) | (values[:, 3] > values[:, 4])).any():
        raise ValueError("reference quantile ordering invalid")
    quantiles = values[:, 2:]
    if target in COUNT_TARGETS:
        if ((values[:, 0] < 0).any() or (quantiles < 0).any()
                or (quantiles != np.floor(quantiles)).any()
                or (values[:, 1] ** 2 < values[:, 0] - 1e-9).any()):
            raise ValueError("count reference output support/variance invalid")
    if target == "anytime_td":
        mean, scale = values[:, 0], values[:, 1]
        if ((mean < 0).any() or (mean > 1).any() or not np.isin(quantiles, [0, 1]).all()
                or not np.allclose(scale ** 2, mean * (1 - mean), rtol=1e-10, atol=1e-9)):
            raise ValueError("Bernoulli reference output support/variance invalid")


def _read_spec(spec):
    path = Path(spec["path"])
    if path.is_symlink() or not path.is_file() or path.stat().st_size != spec["bytes"] or _sha(path) != spec["sha256"]:
        raise ValueError("frozen input size/hash mismatch: " + path.name)
    return path


def _review(path, target, method, binding):
    from .reference_contract import review_reference_artifact
    return review_reference_artifact(path, target=target, method=method, binding=binding)


def _fresh_child(context_path):
    """No storage construction, writes, source values, training or fitting."""
    import pandas as pd
    from . import operational_models as operational, operational_sources as sources, experiment, state
    from .model_artifacts import predict_artifact
    import importlib.util
    import sysconfig
    context_path = Path(context_path).resolve()
    context = json.loads(context_path.read_text())
    protected = [Path(p).resolve() for p in context["forbidden_roots"]]
    allowed_data = {context_path, Path(context["query_path"]).resolve(),
                    *(Path(p["artifact_path"]).resolve() for p in context["packages"])}
    code_root = Path(__file__).resolve().parent
    source_code = {p.resolve() for p in code_root.glob("*.py") if p.is_file()}
    allowed_code = source_code | {Path(importlib.util.cache_from_source(str(p))).resolve() for p in source_code}
    python_paths = sysconfig.get_paths()
    runtime_roots = {Path(python_paths[name]).resolve() for name in
                     ("stdlib", "platstdlib", "purelib", "platlib") if Path(python_paths[name]).is_dir()}
    # Use the interpreter compiled zoneinfo locations. PYTHONTZPATH cannot
    # expand trusted reads into an arbitrary workspace data directory.
    zoneinfo_paths = (sysconfig.get_config_var("TZPATH") or "").split(os.pathsep)
    runtime_roots.update(Path(p).resolve() for p in zoneinfo_paths if p and Path(p).is_dir())
    def audit(event, arguments):
        if event.startswith("socket."):
            raise AssertionError("fresh replay network access is forbidden")
        if event != "open" or isinstance(arguments[0], int):
            return
        path, mode, flags = arguments[:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise AssertionError("fresh replay is read only")
        if isinstance(path, (str, bytes, os.PathLike)):
            resolved = Path(os.fsdecode(path)).resolve()
            if any(resolved == root or root in resolved.parents for root in protected):
                raise AssertionError("fresh replay cannot read source or training values")
            if (resolved not in allowed_data and resolved not in allowed_code
                    and not any(resolved == root or root in resolved.parents for root in runtime_roots)):
                raise AssertionError("fresh replay read outside exact data and trusted runtime allowlist")
    sys.addaudithook(audit)
    def forbidden(*args, **kwargs):
        raise AssertionError("fresh replay cannot load source/training values")
    for name in ("acquire_operational_history", "load_operational_history", "load_operational_identity", "build_operational_features", "resolve_operational_snapshot"):
        setattr(sources, name, forbidden)
    experiment.load_operational_features = forbidden
    state.records = forbidden
    state.resolved_outcomes = forbidden
    query_path = Path(context["query_path"])
    if _sha(query_path) != context["query_file_sha256"]:
        raise ValueError("fresh query file changed")
    query = pd.read_parquet(query_path)
    if operational.frame_hash(query) != context["binding"]["query_sha256"]:
        raise ValueError("fresh query value binding changed")
    original_parquet = pd.read_parquet
    def query_only(path, *args, **kwargs):
        if Path(path).resolve() != query_path.resolve():
            raise AssertionError("fresh parquet read outside frozen query")
        return original_parquet(path, *args, **kwargs)
    pd.read_parquet = query_only
    pd.read_csv = forbidden
    binding = context["binding"]
    if binding["version"] != operational.VERSION or binding["code_sha256"] != operational.code_hashes():
        raise ValueError("fresh operational version/code binding mismatch")
    with _no_fits():
        for package in context["packages"]:
            artifact = Path(package["artifact_path"])
            if _sha(artifact) != package["artifact_file_sha256"]:
                raise ValueError("fresh artifact file changed")
            _review(artifact, package["target"], package["method"], binding)
            cpu_start = _Budget.cpu()
            with _deadline(context["max_package_wall_seconds"]):
                prediction = predict_artifact(artifact, query, input_manifest={"source_qualified": True,
                    "availability_verified": True, "input_sha256": binding["input_sha256"]})
            if _Budget.cpu() - cpu_start > context["max_package_CPU_seconds"]:
                raise RuntimeError("fresh package CPU budget exceeded")
            clean = prediction.astype(object).where(pd.notna(prediction), None)
            print(json.dumps({"target": package["target"], "method": package["method"],
                "columns": list(prediction), "index": prediction.index.tolist(), "rows": clean.values.tolist()},
                allow_nan=False, separators=(",", ":")), flush=True)
    return 0


def _fresh(context, storage, output, budget):
    """Drain both pipes continuously; each bounded chunk is quota persisted."""
    limit = int(budget.budgets["fresh_stdout_max_bytes"])
    process = subprocess.Popen([sys.executable, "-B", "-m", "nfl_lab.reference_runtime", "--fresh-context", str(context)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    selector = selectors.DefaultSelector()
    collected = {"stdout": bytearray(), "stderr": bytearray()}
    counts = {"stdout": 0, "stderr": 0}
    for name in collected:
        pipe = getattr(process, name)
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ, name)
    total = 0
    try:
        while selector.get_map():
            budget.check()
            for key, events in selector.select(timeout=.25):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                total += len(chunk)
                if total > limit:
                    raise RuntimeError("fresh child output exceeded frozen byte cap")
                name = key.data
                storage.write_bytes(output / "fresh-log" / f"{name}-{counts[name]:06d}.bin", chunk)
                counts[name] += 1
                collected[name].extend(chunk)
        if process.wait(timeout=1):
            raise RuntimeError("fresh child failed: " + bytes(collected["stderr"])[-1000:].decode(errors="replace"))
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        for name in collected:
            getattr(process, name).close()
    return [json.loads(line) for line in bytes(collected["stdout"]).splitlines()]


def run_acceptance(config, *, config_sha256):
    """Execute exactly the frozen acceptance once; all returned probes are private."""
    import numpy as np
    import pandas as pd
    from threadpoolctl import threadpool_limits
    from . import operational_models as operational, operational_sources as sources
    from .models import COUNT_TARGETS, TARGETS, _support
    from .operational_io import operational_io
    from .operational_storage import OperationalStorage
    from .state import digest
    from .reference_contract import independent_reference
    config_path = Path(config)
    if _sha(config_path) != config_sha256:
        raise ValueError("runtime registration hash mismatch")
    spec = json.loads(config_path.read_text())
    if spec["registration_id"] != REGISTRATION or spec["targets"] != list(TARGETS) or spec["methods"] != ["recent", "pooled"]:
        raise ValueError("fixed twelve target/two method registration required")
    if set(spec["blocked"]) != {"fantasy_ppr"}:
        raise ValueError("exact PPR must remain explicitly blocked")
    pinned = {name: _read_spec(value) for name, value in spec["inputs"].items()}
    policy = sources.load_source_policy(_read_spec(spec["source_policy"]))
    if policy["_policy_sha256"] != spec["source_policy"]["sha256"]:
        raise ValueError("source policy byte binding changed")
    base = OperationalStorage(spec["cache"], policy, state=spec["state"])
    output = base.register_root(spec["output"])
    storage = StateBoundStorage(base, spec["state"], spec["budgets"]["max_state_logical_bytes"])
    consumed = output / "CONSUMED.json"
    if consumed.exists():
        raise RuntimeError("registered runtime invocation already consumed; replay-only repair requires separate freeze")
    budget = _Budget(spec)
    packages, phases, negatives = [], [], []
    storage.atomic_json(consumed, {"registration_sha256": config_sha256, "generated_at": _now(),
        "state": "CONSUMED", "evidence": "NONISSUED_RUNTIME_PROBE", "inputs": spec["inputs"],
        "code_sha256": {**operational.code_hashes(), "reference_runtime.py": _sha(Path(__file__)),
                         "reference_contract.py": _sha(Path(__file__).with_name("reference_contract.py"))}})
    try:
        with threadpool_limits(limits=spec["budgets"]["threads"]), operational_io(storage):
            manifest = json.loads(pinned["source_manifest"].read_text())
            verified = sources._verify(pinned["source_manifest"].parent, storage=base)
            if manifest["snapshot_sha256"] != spec["expected"]["source_snapshot_sha256"] or verified["manifest_sha256"] != spec["inputs"]["source_manifest"]["sha256"]:
                raise ValueError("exact operational source snapshot changed")
            train_all = pd.read_parquet(pinned["training_features"])
            query = pd.read_parquet(pinned["query_features"])
            if len(train_all) != spec["expected"]["training_rows"] or len(query) != spec["expected"]["query_rows"] or query.game_id.nunique() != spec["expected"]["query_games"]:
                raise ValueError("frozen row/game population changed")
            if sum(name.startswith("f_") for name in query.columns) != spec["expected"]["feature_columns"]:
                raise ValueError("frozen feature schema changed")
            if not query[list(TARGETS)].isna().all().all() or not query.participation_state.eq("unknown").all():
                raise ValueError("query contains labels or known participation")
            cutoff = pd.Timestamp(spec["asof_utc"])
            if cutoff.tzinfo is None or cutoff > pd.Timestamp.now(tz="UTC"):
                raise ValueError("feature cutoff must be explicit past UTC")
            available = pd.to_datetime(train_all.outcome_available_utc, utc=True, errors="coerce")
            kickoffs = pd.to_datetime(train_all.kickoff_utc, utc=True, errors="coerce")
            train = train_all.loc[(available < cutoff) & (kickoffs < cutoff)].copy()
            if train.empty:
                raise ValueError("no earlier eligible training rows")
            if not pd.to_datetime(query.cutoff_utc, utc=True).eq(cutoff).all():
                raise ValueError("query cutoff differs from frozen feature cutoff")
            for target in TARGETS:
                if target == "fantasy_ppr":
                    continue
                labels = pd.to_numeric(train[target], errors="coerce").to_numpy(float)
                if not (train.participation_state.eq("played").to_numpy() & _support(labels, target)).any():
                    raise ValueError("registered package has no supported training labels: " + target)
            input_sha = digest({"registration_sha256": config_sha256, "inputs": spec["inputs"],
                "training_features_sha256": operational.frame_hash(train), "query_sha256": operational.frame_hash(query)})
            binding = operational.model_binding(policy, verified, train, query, input_sha)
            binding_sha = digest(binding)
            storage.atomic_json(output / "binding.json", binding)
            query_saved = query.copy()
            query_saved.attrs.clear()
            query_path = output / "private" / "query.parquet"
            storage.write_dataframe(query_saved, query_path, index=True)
            if operational.frame_hash(pd.read_parquet(query_path)) != binding["query_sha256"]:
                raise ValueError("retained query serialization changed its exact values/schema/order")
            storage.atomic_json(output / "slots.json", [{"target": target, "method": method,
                "state": "BLOCKED" if target in spec["blocked"] else "REGISTERED",
                "reason": spec["blocked"].get(target)} for target in TARGETS for method in spec["methods"]])
            for target in TARGETS:
                if target in spec["blocked"]:
                    continue
                for method in spec["methods"]:
                    budget.check(rows=len(query), fit=True)
                    key = target + "-" + method
                    artifact = Path(spec["state"]) / "models" / operational.VERSION / "runtime" / binding_sha / (key + ".json")
                    if artifact.exists():
                        raise RuntimeError("first-fit artifact already exists; consumed package cannot refit")
                    storage.atomic_json(output / "consumed-packages" / (key + ".json"),
                        {"target": target, "method": method, "generated_at": _now(), "state": "FIT_CONSUMED", "binding_sha256": binding_sha})
                    cpu_start = budget.cpu()
                    with _deadline(spec["budgets"]["max_package_wall_seconds"]), _no_fits(core=False):
                        prediction = operational.fit_operational_reference(train, query, target, method,
                            artifact_path=artifact, binding=binding, storage=storage)
                    budget.produced(len(query))
                    if budget.cpu() - cpu_start > spec["budgets"]["max_package_CPU_seconds"]:
                        raise RuntimeError("package CPU budget exceeded")
                    prediction_path = output / "private" / "first-fit" / (key + ".parquet")
                    saved = prediction.copy()
                    saved.attrs.clear()
                    storage.write_dataframe(saved, prediction_path, index=True)
                    _same(prediction, pd.read_parquet(prediction_path))
                    _validate_output(prediction, target)
                    review = _review(artifact, target, method, binding)
                    window = 3 if method == "recent" else 8
                    count = pd.to_numeric(query[f"f_player_{target}_n{window}"], errors="coerce")
                    summary = pd.to_numeric(query[f"f_player_{target}_mean{window}"], errors="coerce")
                    valid = count.between(1, window) & count.mod(1).eq(0) & np.isfinite(summary)
                    if target in COUNT_TARGETS:
                        valid &= summary.ge(0)
                    elif target == "anytime_td":
                        valid &= summary.between(0, 1)
                    coverage = {"warm": int((valid & count.eq(window)).sum()),
                        "sparse": int((valid & count.lt(window)).sum()), "cold_or_missing": int((~valid).sum())}
                    fallback_counts = {str(name): int(number) for name, number in prediction.fallback.fillna("<missing>").value_counts().items()}
                    record = {"target": target, "method": method, "artifact_path": str(artifact),
                        "query_coverage": coverage, "fallback_counts": fallback_counts,
                        "artifact_file_sha256": _sha(artifact), "prediction_path": str(prediction_path),
                        "prediction_file_sha256": _sha(prediction_path), "query_sha256": binding["query_sha256"],
                        "binding_sha256": binding_sha, "content_review": review}
                    packages.append(record)
                    storage.atomic_json(output / "packages" / (key + ".json"), record)
            phases.append("first_fit")
            def replay_phase(phase):
                with _no_fits():
                    for package in packages:
                        budget.check(rows=len(query))
                        target, method = package["target"], package["method"]
                        artifact = Path(package["artifact_path"])
                        storage.atomic_json(output / "consumed-predictions" / (phase + "-" + target + "-" + method + ".json"),
                            {"generated_at": _now(), "phase": phase, "target": target, "method": method, "rows": len(query)})
                        cpu_start = budget.cpu()
                        _review(artifact, target, method, binding)
                        if operational.frame_hash(query) != binding["query_sha256"]:
                            raise ValueError("exact query binding changed before reference comparison")
                        with _deadline(spec["budgets"]["max_package_wall_seconds"]):
                            if phase == "same_process_replay":
                                replay = operational.predict_operational_artifact(artifact, query, binding=binding, storage=storage)
                            elif phase == "existing_artifact_reuse":
                                replay = operational.fit_operational_reference(train, query, target, method,
                                    artifact_path=artifact, binding=binding, storage=storage)
                            else:
                                replay = independent_reference(artifact, query)
                        budget.produced(len(query))
                        _same(pd.read_parquet(package["prediction_path"]), replay)
                        _validate_output(replay, target)
                        if budget.cpu() - cpu_start > spec["budgets"]["max_package_CPU_seconds"]:
                            raise RuntimeError("replay package CPU budget exceeded")
                        budget.check()
                phases.append(phase)
                storage.atomic_json(output / "phases" / (phase + ".json"), {"generated_at": _now(), "state": "PASSED", "packages": len(packages), "rows": len(query)})
            replay_phase("same_process_replay")
            replay_phase("existing_artifact_reuse")
            context = {"query_path": str(query_path), "query_file_sha256": _sha(query_path), "binding": binding,
                "packages": packages, "max_package_wall_seconds": spec["budgets"]["max_package_wall_seconds"],
                "max_package_CPU_seconds": spec["budgets"]["max_package_CPU_seconds"], "forbidden_roots":
                    [str(Path(spec["cache"])), str(pinned["training_features"]), str(pinned["source_manifest"].parent),
                     str(pinned["accepted_summary"]), str(pinned["query_metadata"]),
                     str(Path(spec["state"]) / "outcomes"), str(Path(spec["state"]) / "forecasts"),
                     str(Path(spec["state"]) / "grading")] +
                    [package["prediction_path"] for package in packages]}
            context_path = output / "fresh-context.json"
            storage.atomic_json(context_path, context)
            budget.check(rows=len(query) * len(packages))
            storage.atomic_json(output / "consumed-predictions" / "fresh_process_replay.json",
                {"generated_at": _now(), "phase": "fresh_process_replay", "packages": len(packages), "rows": len(query) * len(packages)})
            fresh = _fresh(context_path, storage, output, budget)
            budget.produced(sum(len(record["rows"]) for record in fresh))
            if len(fresh) != len(packages):
                raise ValueError("fresh replay package population changed")
            for package, record in zip(packages, fresh):
                if (package["target"], package["method"]) != (record["target"], record["method"]):
                    raise ValueError("fresh replay package identity changed")
                replay = pd.DataFrame(record["rows"], columns=record["columns"], index=pd.Index(record["index"]))
                _same(pd.read_parquet(package["prediction_path"]), replay)
                _validate_output(replay, package["target"])
            phases.append("fresh_process_replay")
            storage.atomic_json(output / "phases" / "fresh_process_replay.json", {"generated_at": _now(), "state": "PASSED", "packages": len(packages)})
            replay_phase("independent_reference")
            first = packages[0]
            artifact = Path(first["artifact_path"])
            with _no_fits():
                for negative in ("changed_query", "changed_source_binding", "corrupt_wrapper", "wrong_target_method"):
                    budget.check(rows=len(query))
                    storage.atomic_json(output / "consumed-predictions" / (negative + ".json"),
                        {"generated_at": _now(), "phase": negative, "rows": len(query)})
                    try:
                        if negative == "changed_query":
                            changed = query.copy()
                            feature = next(name for name in changed if name.startswith("f_") and pd.api.types.is_numeric_dtype(changed[name]))
                            changed.loc[changed.index[0], feature] = 987654.0
                            operational.predict_operational_artifact(artifact, changed, binding=binding, storage=storage)
                        elif negative == "changed_source_binding":
                            changed_binding = {**binding, "snapshot_sha256": "0" * 64}
                            operational.predict_operational_artifact(artifact, query, binding=changed_binding, storage=storage)
                        elif negative == "corrupt_wrapper":
                            corrupt = json.loads(artifact.read_text())
                            corrupt["artifact"]["inference"]["global_prior"]["mean"] = "not-numeric"
                            corrupt["sha256"] = digest(corrupt["artifact"])
                            corrupt_path = output / "private" / "corrupt-reference.json"
                            storage.atomic_json(corrupt_path, corrupt)
                            _review(corrupt_path, first["target"], first["method"], binding)
                            operational.predict_operational_artifact(corrupt_path, query, binding=binding, storage=storage)
                        else:
                            operational.fit_operational_reference(train, query, "pass_td", "pooled",
                                artifact_path=artifact, binding=binding, storage=storage)
                    except (ValueError, TypeError, KeyError, OverflowError) as error:
                        negatives.append({"case": negative, "state": "EXPECTED_REJECTION", "exception": type(error).__name__})
                    else:
                        budget.produced(len(query))
                        raise ValueError("fixed negative was accepted: " + negative)
                budget.check(rows=len(query))
                storage.atomic_json(output / "consumed-predictions" / "technical_recovery.json",
                    {"generated_at": _now(), "phase": "technical_recovery", "rows": len(query)})
                recovered = operational.predict_operational_artifact(artifact, query, binding=binding, storage=storage)
                budget.produced(len(query))
                _same(pd.read_parquet(first["prediction_path"]), recovered)
            storage.atomic_json(output / "negative-checks.json", {"generated_at": _now(), "checks": negatives, "original_replay": "PASSED"})
            budget.check()
            result = {"state": "NONISSUED_REFERENCE_ACCEPTANCE_PASSED", "generated_at": _now(),
                "registration_sha256": config_sha256, "feature_cutoff_utc": spec["asof_utc"],
                "package_count": len(packages), "blocked_slots": 2, "query_rows": len(query),
                "query_coverage": [{"target": p["target"], "method": p["method"], "coverage": p["query_coverage"],
                    "fallback_counts": p["fallback_counts"]} for p in packages],
                "operational_data_state": "ALL_HISTORY_UNAVAILABLE_OPERATIONAL_DATA_LIMIT" if all(
                    p["query_coverage"]["cold_or_missing"] == len(query) for p in packages) else "REPORTED_QUERY_HISTORY_COVERAGE",
                "query_sha256": binding["query_sha256"], "binding_sha256": binding_sha,
                "training_rows_before_filter": len(train_all), "training_rows": len(train),
                "phases": phases, "negative_checks": negatives, "usage": budget.usage(), "storage": base.snapshot(),
                "query_forecast_budget_accounting": "route charges include four rejected attempts; successful returned rows count five 22-package passes plus recovery; internal training fitted/residual arrays are parameter work",
                "supported_training_rows_by_package": [{"target": p["target"], "method": p["method"],
                    "rows": p["content_review"].get("supported_played_training_rows")} for p in packages],
                "new_accuracy_scores": 0, "new_HTTP_attempts": 0, "promotion": "NONE", "publication": "PENDING_SEPARATE_CONTENT_ACCEPTANCE"}
            storage.atomic_json(output / "result.json", result)
            return result
    except BaseException as error:
        failure = {"state": "FAILED", "generated_at": _now(), "registration_sha256": config_sha256,
            "completed_packages": len(packages), "completed_phases": phases, "usage": budget.usage(),
            "exception": type(error).__name__, "message": str(error)[:1000]}
        try:
            storage.atomic_json(output / "FAILURE.json", failure)
        except Exception as marker_error:
            raise RuntimeError("acceptance failed and failure evidence could not be persisted: " + str(marker_error)) from error
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--config-sha256")
    parser.add_argument("--fresh-context", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.fresh_context:
        return _fresh_child(args.fresh_context)
    if not args.config or not args.config_sha256:
        parser.error("--config and --config-sha256 are required")
    result = run_acceptance(args.config, config_sha256=args.config_sha256)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
