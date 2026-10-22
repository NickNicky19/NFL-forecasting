"""Finite JSON fitted-model artifacts and local replay/rollback.

No pickle, executable payload, raw training rows, or training-time data access is
needed by replay. Input qualification is an explicit caller attestation, not a
claim that a checksum independently establishes the truth/timing of a source.
"""
from __future__ import annotations

from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import tempfile
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import expit


ARTIFACT_SCHEMA = "nfl-model-artifact-v1"
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024


class ArtifactError(ValueError):
    """An artifact or its input contract cannot be safely replayed."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def _code_hashes() -> dict[str, str]:
    root = Path(__file__).parent
    return {name: sha256((root / name).read_bytes()).hexdigest() for name in ("models.py", "model_artifacts.py")}


def _environment() -> dict:
    packages = ("numpy", "pandas", "scipy", "scikit-learn", "threadpoolctl")
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "requirements_lock": [f"{name}=={version(name)}" for name in packages]}


def _atomic_json(path: Path, value: Any, *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _canonical(value) + b"\n"
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".artifact-", delete=False) as stream:
            temporary = stream.name
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # Linking is atomic and refuses to replace an existing artifact.
            os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def estimator_state(model) -> dict:
    """Extract learned parameters, including full trees, without raw rows."""
    name = type(model).__name__
    if name == "ExtraTreesRegressor":
        trees = []
        for estimator in model.estimators_:
            tree = estimator.tree_
            trees.append({"left": tree.children_left.tolist(), "right": tree.children_right.tolist(),
                          "feature": tree.feature.tolist(), "threshold": tree.threshold.tolist(),
                          "value": tree.value[:, 0, 0].tolist()})
        return {"kind": "trees", "estimator": name, "trees": trees, "input_dtype": "float32"}
    if name not in {"Ridge", "LogisticRegression", "PoissonRegressor"}:
        raise ArtifactError(f"unsupported fitted estimator: {name}")
    return {"kind": "linear", "estimator": name,
            "coefficient": np.asarray(model.coef_, dtype=float).reshape(-1).tolist(),
            "intercept": float(np.asarray(model.intercept_).reshape(-1)[0]),
            "link": "logistic" if name == "LogisticRegression" else "exp" if name == "PoissonRegressor" else "identity"}


def _nodes(state: dict):
    yield state
    for value in state.values():
        if isinstance(value, dict):
            yield from _nodes(value)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    yield from _nodes(child)


def _validate_learned_state(payload: dict) -> None:
    """Bound the data-only inference graph and reject malformed learned state."""
    from .models import METHODS, MODEL_VERSION, TARGETS
    if payload["target"] not in TARGETS or payload["method"] not in METHODS:
        raise ArtifactError("unregistered artifact target or method")
    if payload["model_version"] != MODEL_VERSION:
        raise ArtifactError("unsupported fitted model version")
    for name in ("target", "method", "model_version"):
        if payload["config"][name] != payload[name]:
            raise ArtifactError("artifact configuration identity mismatch")
    for node in _nodes(payload["inference"]):
        if node.get("kind") != "ml":
            continue
        design = node["design"]
        categorical = design["categorical_levels"]
        if set(design["categorical_order"]) != set(categorical) or len(design["categorical_order"]) != len(categorical):
            raise ArtifactError("invalid categorical feature order")
        for name in design["feature_columns"]:
            if design["numeric_scales"][name] <= 0:
                raise ArtifactError("nonpositive fitted feature scale")
        width = 2 * len(design["feature_columns"]) + sum(len(levels) for levels in categorical.values())
        if not 1 <= width <= 4096:
            raise ArtifactError("fitted feature width exceeds the inference budget")
        status = node["fit_status"]
        if status != "fitted":
            if status not in {"insufficient_supported_training_or_features", "single_binary_class_position_prior", "failed_with_recorded_fallback"} or "estimator" in node:
                raise ArtifactError("invalid unfitted fallback state")
            continue
        estimator = node["estimator"]
        if estimator["kind"] == "linear":
            if len(estimator["coefficient"]) != width or estimator["link"] not in {"identity", "logistic", "exp"}:
                raise ArtifactError("invalid learned linear state")
            continue
        if estimator["kind"] != "trees" or len(estimator["trees"]) != 24:
            raise ArtifactError("invalid learned tree ensemble")
        for tree in estimator["trees"]:
            n = len(tree["left"])
            if not 1 <= n <= 127 or any(len(tree[key]) != n for key in ("right", "feature", "threshold", "value")):
                raise ArtifactError("invalid learned tree node arrays")
            for i, (left, right, feature) in enumerate(zip(tree["left"], tree["right"], tree["feature"])):
                if left == right == -1:
                    continue
                if not isinstance(left, int) or not isinstance(right, int) or not isinstance(feature, int) or not i < left < n or not i < right < n or not 0 <= feature < width:
                    raise ArtifactError("invalid/cyclic learned tree edge")


def export_artifact(path: str | Path, inference: dict, participation: dict, audit: dict, fixture: pd.DataFrame) -> dict:
    """Create an immutable fitted artifact; exporting does not refit or select."""
    from .models import METHODS, MODEL_VERSION, RIDGE_ALPHA, SEED, TARGETS
    identity = {"player_id", "game_id", "position", "team", "opponent", "kickoff_utc"}
    required = set(identity)
    required.update(name for name in ("f_player_play_rate8", "f_player_known_participation_n8") if name in fixture)
    missing_summary = []
    for node in _nodes(inference):
        if node.get("kind") == "recent":
            required.update(node["required_summary_columns"])
            if not node["qualified_summary_columns_present"]:
                missing_summary.extend(node["required_summary_columns"])
        if node.get("kind") == "ml":
            required.update(node["design"]["feature_columns"])
            required.update(node["design"]["categorical_levels"])
        if node.get("kind") == "team_share":
            target = node["target"]
            required.update((f"f_team_{target}_mean3", f"f_player_{target}_mean3", f"f_player_{target}_n3"))
        if node.get("kind") == "pooled_rate":
            den = node["denominator"]
            required.update((f"f_player_{den}_mean3", f"f_player_{den}_n3"))
            required.add(node["feature"] or f"f_player_{node['numerator']}_mean3")
    # Optional absent efficiency/team features deliberately produce the same
    # numerical fallback on replay; only columns present in the fixture bind
    # their source schema. Recent histories are stricter: no hidden history scan.
    required = {name for name in required if name in fixture or name in missing_summary or name in identity}
    missing_identity = sorted(identity - set(fixture))
    config = {"model_version": MODEL_VERSION, "target": audit["target"], "method": audit["method"],
              "registered_methods": list(METHODS), "registered_targets": list(TARGETS),
              "seed": SEED, "ridge_alpha": RIDGE_ALPHA, "ensemble_weights": [.5, .25, .25]}
    payload = {"schema": ARTIFACT_SCHEMA, "model_version": MODEL_VERSION, "target": audit["target"],
               "method": audit["method"], "inference": inference, "participation": participation,
               "distribution": audit.get("distribution_fit"), "training_audit": audit,
               "config": config, "config_sha256": _digest(config), "code_sha256": _code_hashes(),
               "environment": _environment(), "contains_raw_training_rows": False,
               "source_schema": {"required_columns": sorted(required), "numeric_columns": sorted(name for name in required if name.startswith("f_")),
                                 "qualification": "source_qualified and availability_verified true; input_sha256 binds caller's feature manifest",
                                 "missing_values": "NaN supported; absent required columns or nonnumeric/infinite values rejected"},
               "replayable": not missing_summary and not missing_identity,
               "replay_limitation": "missing qualified summaries used legacy training-history fallback" if missing_summary else f"missing source identity columns: {missing_identity}" if missing_identity else None,
               "evidence_state": "IMPLEMENTED_UNQUALIFIED_SHADOW; no promotion or forecasting gain implied"}
    repository_config = Path(__file__).resolve().parents[1] / "config" / "research.json"
    if repository_config.is_file():
        payload["research_registration_sha256"] = sha256(repository_config.read_bytes()).hexdigest()
    wrapper = {"artifact": payload, "sha256": _digest(payload)}
    _atomic_json(Path(path), wrapper, replace=False)
    return wrapper


def load_artifact(path: str | Path, *, check_environment: bool = True) -> dict:
    """Verify integrity, code/config and environment before numeric inference."""
    try:
        path = Path(path)
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ArtifactError("artifact exceeds the bounded inference payload size")
        wrapper = json.loads(path.read_text())
        payload = wrapper["artifact"]
        if wrapper["sha256"] != _digest(payload):
            raise ArtifactError("artifact checksum mismatch")
        if payload["schema"] != ARTIFACT_SCHEMA:
            raise ArtifactError("unsupported artifact schema")
        if payload["config_sha256"] != _digest(payload["config"]):
            raise ArtifactError("artifact configuration checksum mismatch")
        if payload["code_sha256"] != _code_hashes():
            raise ArtifactError("artifact code hash differs from installed inference code")
        if check_environment and payload["environment"] != _environment():
            raise ArtifactError("artifact environment differs from its recorded lock")
        if payload["contains_raw_training_rows"] is not False:
            raise ArtifactError("invalid artifact training-data contract")
        if not payload["replayable"]:
            raise ArtifactError(payload["replay_limitation"])
        _validate_learned_state(payload)
        return wrapper
    except ArtifactError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
        raise ArtifactError(f"invalid artifact structure: {error}") from error


def _validate_inputs(test: pd.DataFrame, payload: dict, manifest: dict) -> None:
    if manifest.get("source_qualified") is not True or manifest.get("availability_verified") is not True:
        raise ArtifactError("replay requires caller-qualified source and feature availability")
    input_hash = manifest.get("input_sha256", "")
    if not isinstance(input_hash, str) or len(input_hash) != 64 or any(c not in "0123456789abcdef" for c in input_hash.lower()):
        raise ArtifactError("input manifest must bind a SHA256 digest")
    schema = payload["source_schema"]
    missing = set(schema["required_columns"]) - set(test.columns)
    if missing:
        raise ArtifactError(f"missing required source columns: {sorted(missing)}")
    for name in ("player_id", "game_id"):
        if test[name].isna().any() or test[name].astype(str).str.strip().eq("").any():
            raise ArtifactError(f"missing source identity: {name}")
    for name in schema["numeric_columns"]:
        values = test[name]
        if not pd.api.types.is_numeric_dtype(values.dtype):
            raise ArtifactError(f"source feature must be numeric: {name}")
        if np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).any():
            raise ArtifactError(f"infinite source feature: {name}")
    if "kickoff_utc" in test:
        kickoff = pd.to_datetime(test["kickoff_utc"], utc=True, errors="coerce")
        if kickoff.isna().any():
            raise ArtifactError("missing/invalid kickoff clock")
        if "cutoff_utc" in test:
            cutoff = pd.to_datetime(test["cutoff_utc"], utc=True, errors="coerce")
            if cutoff.isna().any() or (cutoff > kickoff).any():
                raise ArtifactError("invalid source cutoff or cutoff after kickoff")


def _position_values(test: pd.DataFrame, lookup: dict, default: float) -> np.ndarray:
    from .models import _strings
    return np.array([lookup.get(str(p), default) for p in _strings(test, "position")])


def _recent(node: dict, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    from .models import COUNT_TARGETS, _numeric, _strings
    target, window = node["target"], node["window"]
    prior = _position_values(test, {p: value["mean"] for p, value in node["position_priors"].items()}, node["global_prior"]["mean"])
    mean, count = _numeric(test, f"f_player_{target}_mean{window}"), _numeric(test, f"f_player_{target}_n{window}")
    valid = np.isfinite(mean) & np.isfinite(count) & (count > 0) & (count <= window) & (count == np.floor(count))
    if target in COUNT_TARGETS or target == "targets":
        valid &= mean >= 0
    elif target == "anytime_td":
        valid &= (mean >= 0) & (mean <= 1)
    mean, count = np.where(valid, mean, np.nan), np.where(valid, count, 0)
    strength = 3.0 if window == 3 else 5.0
    prediction = np.where(valid, (np.nan_to_num(mean) * count + strength * prior) / (count + strength), prior)
    reason = np.where(valid, "", "position_prior").astype(object)
    unknown = ~np.isin(_strings(test, "position"), list(node["position_priors"]))
    reason = np.where(~valid & unknown, "global_prior_unknown_position", reason)
    return prediction, reason


def _rate(node: dict, test: pd.DataFrame) -> np.ndarray:
    from .models import _numeric
    if node["kind"] == "unavailable":
        return np.full(len(test), np.nan)
    den = node["denominator"]
    prior = _position_values(test, node["position_rates"], node["global_rate"])
    exposure = _numeric(test, f"f_player_{den}_mean3")
    rate = _numeric(test, node["feature"]) if node["feature"] else np.full(len(test), np.nan)
    if node["feature"] is None:
        numerator = _numeric(test, f"f_player_{node['numerator']}_mean3")
        rate = np.divide(numerator, exposure, out=rate, where=np.isfinite(exposure) & (exposure > 0))
    n = _numeric(test, f"f_player_{den}_n3")
    exposure = np.where(np.isfinite(n), exposure * np.minimum(n, 3), np.nan)
    valid = np.isfinite(rate) & np.isfinite(exposure) & (exposure > 0)
    if node["bounded"]:
        valid &= (rate >= 0) & (rate <= 1)
    result = np.where(valid, (np.nan_to_num(rate) * np.nan_to_num(exposure) + 30 * prior) / (np.nan_to_num(exposure) + 30), prior)
    return np.clip(result, 0, 1) if node["bounded"] else result


def _transform(design: dict, test: pd.DataFrame) -> np.ndarray:
    from .models import _numeric, _strings
    parts = []
    for name in design["feature_columns"]:
        values = _numeric(test, name)
        missing = ~np.isfinite(values)
        standardized = (np.where(missing, design["numeric_medians"][name], values) - design["numeric_medians"][name]) / design["numeric_scales"][name]
        parts.extend([np.clip(standardized, -8, 8), missing.astype(float)])
    for name in design["categorical_order"]:
        values = design["categorical_levels"][name]
        observed = _strings(test, name)
        parts.extend([(observed == value).astype(float) for value in values])
    return np.column_stack(parts) if parts else np.empty((len(test), 0))


def _estimator_predict(state: dict, x: np.ndarray) -> np.ndarray:
    if state["kind"] == "linear":
        linear = x @ np.asarray(state["coefficient"]) + state["intercept"]
        return expit(linear) if state["link"] == "logistic" else np.exp(linear) if state["link"] == "exp" else linear
    if state["kind"] != "trees":
        raise ArtifactError("unsupported learned estimator state")
    # sklearn tree prediction first converts the design to float32.
    x = x.astype(np.float32)
    summed = np.zeros(len(x))
    for tree in state["trees"]:
        leaf = np.zeros(len(x), dtype=int)
        left, right = np.asarray(tree["left"]), np.asarray(tree["right"])
        feature, threshold = np.asarray(tree["feature"]), np.asarray(tree["threshold"])
        active = left[leaf] != -1
        while active.any():
            rows = np.flatnonzero(active)
            nodes = leaf[rows]
            go_left = x[rows, feature[nodes]] <= threshold[nodes]
            leaf[rows] = np.where(go_left, left[nodes], right[nodes])
            active = left[leaf] != -1
        summed += np.asarray(tree["value"])[leaf]
    return summed / len(state["trees"])


def _candidate(node: dict, test: pd.DataFrame) -> np.ndarray:
    from .models import _numeric
    kind = node["kind"]
    if kind == "unavailable":
        return np.full(len(test), np.nan)
    if kind == "exposure_rate":
        return _point(node["exposure"], test)[0] * _rate(node["rate"], test)
    if kind == "mean_sum":
        return sum(_point(component, test)[0] for component in node["components"])
    if kind != "team_share":
        raise ArtifactError("unsupported workload state")
    target = node["target"]
    volume = _numeric(test, f"f_team_{target}_mean3")
    player = _numeric(test, f"f_player_{target}_mean3")
    n = _numeric(test, f"f_player_{target}_n3")
    prior = _position_values(test, node["position_shares"], node["global_share"])
    share = np.divide(player, volume, out=np.full(len(test), np.nan), where=volume > 0)
    weight = np.where(np.isfinite(n), np.minimum(n, 3) / (np.minimum(n, 3) + 3), 0)
    share = np.where(np.isfinite(share), weight * share + (1 - weight) * prior, prior)
    return volume * np.clip(share, 0, 1)


def _point(node: dict, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    from .models import COUNT_TARGETS, _archived, _numeric
    kind = node["kind"]
    if kind == "unavailable":
        return np.full(len(test), np.nan), np.full(len(test), "no_supported_played_training_outcomes", dtype=object)
    if kind == "archived":
        return _archived(test, node["target"], node["method"])
    if kind == "recent":
        return _recent(node, test)
    if kind == "ensemble":
        results = [_point(component, test) for component in node["components"]]
        mean = sum(weight * result[0] for weight, result in zip(node["weights"], results))
        reasons = np.array([";".join(sorted({str(r) for r in row if r})) for row in zip(*(result[1] for result in results))], dtype=object)
        return mean, reasons
    baseline, reason = _point(node["baseline"], test)
    if kind == "workload":
        candidate = _candidate(node["candidate"], test)
        valid = np.isfinite(candidate)
        return np.where(valid, candidate, baseline), np.where(valid, "", "missing_workload_inputs:" + reason.astype(str)).astype(object)
    if kind != "ml":
        raise ArtifactError("unsupported model inference state")
    status = node["fit_status"]
    if status != "fitted":
        if status == "single_binary_class_position_prior":
            return baseline, np.full(len(test), "single_binary_class", dtype=object)
        prefix = "insufficient_fit:" if status == "insufficient_supported_training_or_features" else "fit_failed:"
        return baseline, prefix + reason
    prediction = _estimator_predict(node["estimator"], _transform(node["design"], test))
    if node["target"] == "anytime_td":
        prediction = np.clip(prediction, 0, 1)
    elif node["target"] in COUNT_TARGETS:
        prediction = np.clip(prediction, *node["count_mean_bounds"])
    valid = np.isfinite(prediction)
    prediction = np.where(valid, prediction, baseline)
    fallback = np.where(valid, "", "nonfinite_fit:" + reason.astype(str)).astype(object)
    numeric = node["design"]["feature_columns"]
    if numeric:
        missing = ~np.column_stack([np.isfinite(_numeric(test, name)) for name in numeric]).any(axis=1)
        prediction = np.where(missing, baseline, prediction)
        fallback = np.where(missing, "all_numeric_features_missing:" + reason.astype(str), fallback)
    return prediction, fallback


def _participation(node: dict, test: pd.DataFrame) -> np.ndarray:
    from .models import _numeric
    if node["kind"] == "unavailable":
        return np.full(len(test), np.nan)
    prior = _position_values(test, node["position_rates"], node["global_rate"])
    rate, count = _numeric(test, "f_player_play_rate8"), _numeric(test, "f_player_known_participation_n8")
    valid = np.isfinite(rate) & np.isfinite(count) & (rate >= 0) & (rate <= 1) & (count > 0)
    count = np.where(valid, np.minimum(count, 8), 0)
    return (np.where(valid, rate, 0) * count + 8 * prior) / (count + 8)


def predict_artifact(path: str | Path, test: pd.DataFrame, *, input_manifest: dict) -> pd.DataFrame:
    """Replay frozen parameters on source-qualified features; never fit anything."""
    from .models import COUNT_TARGETS, _family, _quantiles
    wrapper = load_artifact(path)
    payload = wrapper["artifact"]
    _validate_inputs(test, payload, input_manifest)
    mean, reason = _point(payload["inference"], test)
    target = payload["target"]
    if target == "anytime_td":
        mean = np.clip(mean, 0, 1)
        scale = np.sqrt(mean * (1 - mean))
    else:
        if target in COUNT_TARGETS:
            mean = np.maximum(mean, 0)
        scale = np.full(len(test), np.nan)
        distribution = payload["distribution"]
        if distribution:
            dispersion = _position_values(test, distribution["position_dispersion"], distribution["global_dispersion"])
            variance = mean + dispersion * mean ** 2 if target in COUNT_TARGETS else dispersion
            scale = np.sqrt(np.maximum(variance, 0))
    p10, p50, p90 = _quantiles(mean, scale, target)
    result = pd.DataFrame({"mean": mean, "scale": scale, "family": _family(target), "p10": p10, "p50": p50, "p90": p90,
                           "p_participation": _participation(payload["participation"], test), "fallback": reason}, index=test.index)
    result.attrs.update(payload["training_audit"])
    result.attrs.update(artifact_sha256=wrapper["sha256"], replay_input_sha256=input_manifest["input_sha256"],
                        replay_mode="frozen parameters; no training rows or refit")
    return result


def activate_artifact(pointer_path: str | Path, artifact_path: str | Path) -> None:
    """Set a local lab consumer pointer and retain one verified rollback target."""
    artifact = load_artifact(artifact_path)
    pointer = Path(pointer_path)
    previous = None
    if pointer.exists():
        current = json.loads(pointer.read_text())["active"]
        if load_artifact(current["path"])["sha256"] != current["sha256"]:
            raise ArtifactError("current artifact changed; refusing pointer update")
        previous = current
    active = {"path": str(Path(artifact_path).resolve()), "sha256": artifact["sha256"]}
    _atomic_json(pointer, {"schema": "nfl-local-artifact-pointer-v1", "active": active, "previous": previous}, replace=True)


def rollback_artifact(pointer_path: str | Path) -> None:
    """Swap a local pointer back only after verifying the prior immutable file."""
    pointer = Path(pointer_path)
    state = json.loads(pointer.read_text())
    previous = state.get("previous")
    if not previous:
        raise ArtifactError("no recorded rollback artifact")
    if load_artifact(previous["path"])["sha256"] != previous["sha256"]:
        raise ArtifactError("rollback artifact checksum changed")
    state["active"], state["previous"] = previous, state["active"]
    _atomic_json(pointer, state, replace=True)


def predict_active_artifact(pointer_path: str | Path, test: pd.DataFrame, *, input_manifest: dict) -> pd.DataFrame:
    state = json.loads(Path(pointer_path).read_text())
    active = state["active"]
    if load_artifact(active["path"])["sha256"] != active["sha256"]:
        raise ArtifactError("active artifact checksum changed")
    return predict_artifact(active["path"], test, input_manifest=input_manifest)


def main(argv: list[str] | None = None) -> int:
    """Replay a fitted JSON artifact against a caller-qualified parquet file."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact")
    parser.add_argument("features_parquet")
    parser.add_argument("input_manifest_json")
    parser.add_argument("output_json")
    args = parser.parse_args(argv)
    features = pd.read_parquet(args.features_parquet)
    manifest = json.loads(Path(args.input_manifest_json).read_text())
    predictions = predict_artifact(args.artifact, features, input_manifest=manifest)
    _atomic_json(Path(args.output_json), {"artifact_sha256": predictions.attrs["artifact_sha256"],
                                        "input_sha256": manifest["input_sha256"],
                                        "predictions": json.loads(predictions.reset_index().to_json(orient="records"))}, replace=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
