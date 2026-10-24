"""Bounded campaign orchestration and one immutable terminal aggregate receipt."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import time
import uuid

from .state import records, save
from .operational_io import operational_io
from .operational_storage import OperationalStorage


class ExperimentTerminated(SystemExit):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(128 + signum)


def atomic_checkpoint(path, value):
    """Replace a small/local checkpoint; immutable state is saved only at exit."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".checkpoint-", delete=False, mode="w") as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, default=str, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def termination_guard():
    """Convert the hosted timeout's SIGTERM into an unwindable termination."""
    installed = threading.current_thread() is threading.main_thread()
    previous = signal.getsignal(signal.SIGTERM) if installed else None
    def terminate(signum, frame):
        raise ExperimentTerminated(signum)
    if installed:
        signal.signal(signal.SIGTERM, terminate)
    try:
        yield
    finally:
        if installed:
            signal.signal(signal.SIGTERM, previous)


def _receipt(config, attempt, result, error, execution_id):
    document = {"schema_version": "lab-training-run-v1", "registration": config,
                "execution_id": execution_id,
                "state": "INTERRUPTED" if isinstance(error, ExperimentTerminated) else "FAILED" if error else "COMPLETED",
                "result": result, "trials": [],
                "row_level_outputs": "local ignored only; never included in immutable aggregate receipt",
                "receipt_policy": "one terminal aggregate per execution; per-trial checkpoints are local"}
    if error is not None:
        document["error"] = {"type": type(error).__name__, "message": str(error)}
        if isinstance(error, ExperimentTerminated):
            document["error"]["signal"] = error.signum
    if attempt is not None:
        document["attempt_output"] = str(attempt)
        for name in ("manifest", "trials", "campaign", "progress", "selected", "paired", "coherence", "summary"):
            path = attempt / (name + ".json")
            if path.exists():
                try:
                    document[name] = json.loads(path.read_text())
                except (OSError, ValueError) as read_error:
                    document.setdefault("checkpoint_read_errors", []).append({"name": name, "error": type(read_error).__name__})
        if not document["trials"]:
            for path in sorted((attempt / "trial-checkpoints").glob("*.json")):
                try:
                    document["trials"].append(json.loads(path.read_text()))
                except (OSError, ValueError) as read_error:
                    document.setdefault("checkpoint_read_errors", []).append({"name": path.name, "error": type(read_error).__name__})
    return document


def run_experiment(root, cache, state, config, methods=None, *, source_policy=None):
    """Run once, preserve a terminal receipt on failure/termination, then reraise."""
    if source_policy is not None:
        return run_reference_learning(root, cache, state, source_policy, methods)
    import pandas as pd
    from .evaluation import campaign
    root, cache, state = map(Path, (root, cache, state))
    attempt = None
    result = None
    execution_id = uuid.uuid4().hex
    terminal_saved = False
    def started(path):
        nonlocal attempt
        attempt = path
    with termination_guard():
        try:
            path = cache / "processed/features.parquet"
            if not path.exists():
                raise RuntimeError("run acquire first")
            features = pd.read_parquet(path)
            with path.open("rb") as source:
                features.attrs["feature_file_sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
            manifest_path = cache / "processed/feature_manifests" / (features.attrs["feature_file_sha256"] + ".json")
            features.attrs["source_snapshot_binding"] = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"state": "legacy feature checksum captured; prematched acquisition snapshot absent; no fabricated source binding"}
            result = campaign(features, root / "runs" / config["registration_id"], config, methods, attempt_callback=started)
            save(state, "training", _receipt(config, attempt, result, None, execution_id))
            terminal_saved = True
            return result
        except BaseException as error:
            if not terminal_saved:
                try:
                    # A signal may arrive after the immutable save committed
                    # but before its success flag was assigned. First receipt
                    # for this execution remains authoritative.
                    committed=any(r.get("execution_id")==execution_id for r in records(state,"training"))
                    if not committed:
                        save(state, "training", _receipt(config, attempt, result, error, execution_id))
                except BaseException as preservation_error:
                    error.add_note(f"Terminal receipt preservation also failed: {preservation_error}")
            raise


def acquire_operational_features(cache, seasons, policy, asof, *, state=None):
    """Persist a new isolated feature snapshot and a small replaceable pointer."""
    from .operational_sources import load_source_policy
    policy = load_source_policy(policy)
    storage = OperationalStorage(cache, policy, state=state)
    with operational_io(storage):
        return _acquire_operational_features(cache, seasons, policy, asof, state=state, storage=storage)


def _acquire_operational_features(cache, seasons, policy, asof, *, state, storage):
    from .operational_sources import (load_source_policy, acquire_operational_history,
                                      load_operational_history, build_operational_features)
    from .operational_models import source_binding, frame_hash, check_operational_storage
    from .state import digest
    policy = load_source_policy(policy)
    check_operational_storage(cache, policy, state=state)
    acquisition = acquire_operational_history(cache, seasons, policy, asof, state=state, storage=storage)
    check_operational_storage(cache, policy, state=state)
    history = load_operational_history(cache, seasons, policy, asof)
    features = build_operational_features(history, policy=policy).reset_index(drop=True)
    manifest = history.attrs["operational_manifest"]
    binding = source_binding(policy, manifest)
    directory = Path(cache) / "processed/operational-source-v2" / policy["_policy_sha256"]
    directory.mkdir(parents=True, exist_ok=True)
    import io
    body = io.BytesIO()
    features.to_parquet(body, index=False)
    encoded = body.getvalue()
    feature_sha = hashlib.sha256(encoded).hexdigest()
    snapshot = directory / "snapshots" / feature_sha
    destination = snapshot / "features.parquet"
    if not destination.exists():
        storage.write_bytes(destination, encoded, replace=False)
    storage.validate_reference(destination, expected_sha256=feature_sha)
    document = {"schema_version": "operational-feature-snapshot-v2", "feature_sha256": feature_sha,
                "feature_values_sha256": frame_hash(features), "source_binding": binding,
                "operational_manifest": manifest, "seasons": sorted(set(seasons)),
                "asof_utc": str(asof), "rows": len(features)}
    manifest_path = snapshot / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != document:
            raise ValueError("immutable operational feature manifest collision")
    else:
        storage.atomic_json(manifest_path, document, replace=False)
    with storage.capture_writes(roots=[directory / "current.json"]):
        storage.atomic_json(directory / "current.json", {"feature_sha256": feature_sha,
                          "manifest_sha256": digest(document)}, replace=True)
    check_operational_storage(cache, policy, state=state)
    return {"rows": len(features), "source_receipt": acquisition,
            "feature_sha256": feature_sha, "source_binding": binding,
            "feature_columns": [column for column in features if column.startswith("f_")]}


def load_operational_features(cache, policy):
    import pandas as pd
    from .operational_sources import load_source_policy
    from .operational_models import source_binding, frame_hash
    from .state import digest
    policy = load_source_policy(policy)
    directory = Path(cache) / "processed/operational-source-v2" / policy["_policy_sha256"]
    storage = OperationalStorage(cache, policy)
    storage.validate_reference(directory / "current.json")
    pointer = json.loads((directory / "current.json").read_text())
    feature_sha = pointer["feature_sha256"]
    if not isinstance(feature_sha, str) or len(feature_sha) != 64 or any(c not in "0123456789abcdef" for c in feature_sha):
        raise ValueError("invalid operational feature snapshot identity")
    snapshot = directory / "snapshots" / feature_sha
    storage.validate_reference(snapshot / "manifest.json")
    document = json.loads((snapshot / "manifest.json").read_text())
    if document.get("schema_version") != "operational-feature-snapshot-v2":
        raise ValueError("v2 operational feature snapshot required")
    if digest(document) != pointer["manifest_sha256"] or document["feature_sha256"] != feature_sha:
        raise ValueError("operational feature manifest integrity failure")
    binding = source_binding(policy, document["operational_manifest"])
    if binding != document["source_binding"]:
        raise ValueError("operational feature policy/source/code binding mismatch")
    feature_path = snapshot / "features.parquet"
    storage.validate_reference(feature_path, expected_sha256=feature_sha)
    if hashlib.sha256(feature_path.read_bytes()).hexdigest() != feature_sha:
        raise ValueError("operational feature bytes changed")
    features = pd.read_parquet(feature_path)
    if frame_hash(features) != document["feature_values_sha256"]:
        raise ValueError("operational feature values changed")
    features.attrs["operational_manifest"] = document["operational_manifest"]
    return features, document


def run_reference_learning(root, cache, state, policy, methods=None):
    """Refresh at most 22 fixed references. This path has no accuracy scoring."""
    from .operational_sources import load_source_policy
    policy = load_source_policy(policy)
    storage = OperationalStorage(cache, policy, state=state)
    with operational_io(storage, run_root=Path(root) / "runs"):
        return _run_reference_learning(root, cache, state, policy, methods, storage=storage)


def _run_reference_learning(root, cache, state, policy, methods, *, storage):
    import numpy as np
    import pandas as pd
    from .models import TARGETS, _support
    from .operational_sources import load_source_policy
    from .operational_models import (VERSION, methods_for_policy, frame_hash, model_binding,
                                      fit_operational_reference, predict_operational_artifact, check_operational_storage)
    from .reference_runtime import StateBoundStorage
    from .state import digest, utc
    policy = load_source_policy(policy)
    methods = methods_for_policy(methods)
    execution_id = uuid.uuid4().hex
    started = time.monotonic()
    packages = []
    error = None
    result = None
    with termination_guard():
        try:
            check_operational_storage(cache, policy, state=state)
            features, document = load_operational_features(cache, policy)
            asof = utc(document["asof_utc"])
            available = pd.to_datetime(features.outcome_available_utc, utc=True, errors="coerce")
            kickoffs = pd.to_datetime(features.kickoff_utc, utc=True, errors="coerce")
            train = features.loc[(available < asof) & (kickoffs < asof)].copy()
            if train.empty:
                raise ValueError("no earlier qualified operational training rows")
            # A private schema probe exports fixed parameters; it is never an
            # issued forecast or a held-out accuracy observation.
            query = train.sort_values("kickoff_utc").groupby("position", dropna=False).tail(1).copy().reset_index(drop=True)
            query["game_id"] = ["reference-probe:" + str(index) for index in query.index]
            query["kickoff_utc"] = pd.Timestamp(asof) + pd.Timedelta(days=1)
            query["cutoff_utc"] = asof
            query["outcome_available_utc"] = pd.NaT
            query["participation_state"] = "unknown"
            for target in TARGETS:
                query[target] = np.nan
            input_sha = digest({"feature_sha256": document["feature_sha256"],
                                "source_binding": document["source_binding"], "query_sha256": frame_hash(query)})
            binding = model_binding(policy, document["operational_manifest"], train, query, input_sha)
            model_storage = StateBoundStorage(storage, state)
            namespace = digest(binding)
            budget = policy["operational_routing"]["weekly_reference_budget"]
            limit = min(22, int(budget["max_supported_packages"]))
            wall_limit = min(1200, float(budget["max_wall_seconds"]))
            for target in TARGETS:
                if target == "fantasy_ppr" or target not in train:
                    continue
                labels = pd.to_numeric(train[target], errors="coerce").to_numpy(float)
                supported = train.participation_state.eq("played").to_numpy() & _support(labels, target)
                if not supported.any():
                    continue
                for method in methods:
                    if len(packages) >= limit or time.monotonic() - started >= wall_limit:
                        raise RuntimeError("fixed reference package/wall budget exhausted")
                    artifact = Path(state) / "models" / VERSION / "weekly" / namespace / f"{target}-{method}.json"
                    pred = fit_operational_reference(train, query, target, method, artifact_path=artifact, binding=binding, storage=model_storage)
                    check_operational_storage(cache, policy, state=state)
                    replay = predict_operational_artifact(artifact, query, binding=binding, storage=model_storage)
                    for column in ("mean", "scale", "p10", "p50", "p90", "p_participation"):
                        if not np.allclose(pred[column], replay[column], rtol=1e-10, atol=1e-9, equal_nan=True):
                            raise ValueError("fixed reference artifact replay mismatch")
                    if pred.fallback.fillna("").tolist() != replay.fallback.fillna("").tolist():
                        raise ValueError("fixed reference artifact fallback mismatch")
                    packages.append({"target": target, "method": method,
                                     "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()})
            result = {"state": "FIXED_REFERENCE_REFRESH_COMPLETED", "packages": packages,
                      "package_count": len(packages), "input_sha256": input_sha,
                      "binding_sha256": namespace, "source_binding": document["source_binding"],
                      "new_hyperparameter_searches": 0, "new_accuracy_scores": 0,
                      "promotion": "NONE", "evidence_lane": "current-vintage reconstruction; no confirmation samples"}
            return result
        except BaseException as caught:
            error = caught
            raise
        finally:
            save(state, "training", {"schema_version": "operational-reference-refresh-v2", "execution_id": execution_id,
                 "policy_sha256": policy["_policy_sha256"], "state": "INTERRUPTED" if isinstance(error, ExperimentTerminated) else "FAILED" if error else "COMPLETED",
                 "result": result, "packages": packages, "wall_seconds": time.monotonic() - started,
                 "error": {"type": type(error).__name__, "message": str(error)[:500]} if error else None,
                 "public_content": "aggregate identities only; private fitted weights and source/player rows excluded"})
