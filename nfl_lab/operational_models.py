"""Source-bound reference artifacts for the opt-in operational source policy.

Core model code stays frozen. A provisional core artifact is sanitized before
the final immutable artifact exists; this panel cannot estimate participation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from .state import digest

VERSION = "permitted-operational-reference-v2"
METHODS = ("recent", "pooled")
PARTICIPATION = {"state": "unavailable", "reason": "positive-event panel has no complete DNP/nonappearance denominator"}
CODE_FILES = ("data.py", "features.py", "permitted_source_features.py", "rb_readiness.py", "operational_sources.py",
              "operational_models.py", "models.py", "model_artifacts.py", "live.py", "experiment.py",
              "cli.py", "grading_sources.py", "scoring.py", "operational_storage.py", "operational_io.py")


def code_hashes():
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in CODE_FILES}


def methods_for_policy(methods=None):
    selected = list(dict.fromkeys(methods if methods is not None else METHODS))
    if not selected or any(method not in METHODS for method in selected):
        raise ValueError("operational source policy permits only recent/pooled references")
    return selected


def frame_hash(frame):
    return digest({"columns": list(frame.columns), "dtypes": [str(dtype) for dtype in frame.dtypes],
                   "rows_sha256": hashlib.sha256(pd.util.hash_pandas_object(frame, index=True).values.tobytes()).hexdigest()})


def check_operational_storage(cache, policy, *, state=None, reserve_bytes=0):
    """Diagnostic snapshot; reservations occur inside every storage write."""
    from .operational_storage import OperationalStorage
    storage = OperationalStorage(cache, policy, state=state)
    size = storage.snapshot()["physical_bytes"]
    limit = min(512 * 1024 * 1024, int(policy.get("namespaces", {}).get("private_retention_bytes", 512 * 1024 * 1024)))
    if limit <= 0 or size + reserve_bytes > limit:
        raise RuntimeError("combined operational source/features/model retention cap; no evidence removed")
    return size


def source_binding(policy, manifest):
    from .operational_sources import VERSION as SOURCE_VERSION
    if manifest.get("adapter_version") != SOURCE_VERSION:
        raise ValueError("v2 operational source manifest required; v1 replay requires its Git pin")
    policy_sha = policy.get("_policy_sha256")
    if not policy_sha or manifest.get("policy_sha256") != policy_sha:
        raise ValueError("operational source policy binding mismatch")
    for key in ("snapshot_sha256", "training_view_sha256"):
        value = manifest.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"operational manifest missing valid {key}")
    if not manifest.get("namespace"):
        raise ValueError("operational source namespace missing")
    return {"version": VERSION, "policy_sha256": policy_sha,
            "source_manifest_sha256": digest(manifest), "snapshot_sha256": manifest["snapshot_sha256"],
            "training_view_sha256": manifest["training_view_sha256"], "code_sha256": code_hashes()}


def model_binding(policy, manifest, train, query, input_sha256):
    if not isinstance(input_sha256, str) or len(input_sha256) != 64:
        raise ValueError("operational input SHA256 required")
    return {**source_binding(policy, manifest), "input_sha256": input_sha256,
            "training_features_sha256": frame_hash(train), "query_sha256": frame_hash(query)}


def predict_operational_artifact(path, query, *, binding, storage):
    from .model_artifacts import ArtifactError, load_artifact, predict_artifact
    storage.validate_reference(path)
    artifact = load_artifact(path)["artifact"]
    if binding.get("version") != VERSION:
        raise ArtifactError("v2 operational reference binding required")
    if binding.get("code_sha256") != code_hashes():
        raise ArtifactError("operational adapter code binding mismatch")
    if binding.get("query_sha256") != frame_hash(query):
        raise ArtifactError("operational query binding mismatch")
    if artifact.get("operational_source_binding") != binding:
        raise ArtifactError("operational policy/source/training/input binding mismatch")
    if artifact.get("participation") != {"kind": "unavailable"} or artifact["training_audit"].get("participation") != PARTICIPATION:
        raise ArtifactError("operational participation contract mismatch")
    return predict_artifact(path, query, input_manifest={"source_qualified": True,
        "availability_verified": True, "input_sha256": binding["input_sha256"]})


def fit_operational_reference(train, query, target, method, *, artifact_path, binding, storage):
    from . import model_artifacts
    from .model_artifacts import load_artifact, ArtifactError
    from .models import fit_predict
    methods_for_policy([method])
    if target == "fantasy_ppr":
        raise ValueError("exact PPR labels remain blocked")
    if binding.get("training_features_sha256") != frame_hash(train) or binding.get("query_sha256") != frame_hash(query):
        raise ValueError("operational training/query hash mismatch")
    if binding.get("code_sha256") != code_hashes():
        raise ValueError("operational adapter code binding mismatch")
    if binding.get("version") != VERSION:
        raise ValueError("v2 operational reference binding required")
    destination = Path(artifact_path)
    if destination.exists() or destination.is_symlink():
        storage.validate_reference(destination)
        existing = load_artifact(destination)["artifact"]
        if existing["target"] != target or existing["method"] != method:
            raise ArtifactError("operational artifact target/method mismatch")
        return predict_operational_artifact(destination, query, binding=binding, storage=storage)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".operational-fit-", dir=destination.parent) as temporary:
        provisional = Path(temporary) / "core.json"
        # The core serializer uses NamedTemporaryFile, so Path capture alone
        # cannot enforce its peak. Override only within this reference wrapper.
        from .operational_io import operational_io
        with operational_io(storage), patch.object(model_artifacts, "_atomic_json", storage.atomic_json):
            result = fit_predict(train, query, target, method, artifact_path=provisional)
        wrapper = json.loads(provisional.read_text())
        payload = wrapper["artifact"]
        payload["participation"] = {"kind": "unavailable"}
        payload["training_audit"]["participation"] = PARTICIPATION.copy()
        payload["operational_source_binding"] = binding
        wrapper["sha256"] = digest(payload)
        storage.atomic_json(destination, wrapper, replace=False)
    result["p_participation"] = np.nan
    result.attrs["participation"] = PARTICIPATION.copy()
    result.attrs["operational_source_binding"] = binding
    return result
