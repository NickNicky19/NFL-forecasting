"""Strict aggregate-only reference content review and independent replay math.

This module neither fits a model nor publishes files. A checksum proves a byte
binding, not source timing, upstream rights, or calibrated forecast quality.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re

from .model_artifacts import ArtifactError, MAX_ARTIFACT_BYTES, _code_hashes, _environment
from .models import COUNT_TARGETS, METHODS, MODEL_VERSION, RIDGE_ALPHA, SEED, TARGETS
from .operational_models import CODE_FILES, PARTICIPATION, VERSION, code_hashes


REVIEW_SCHEMA = "derived-reference-content-review-v2"
PUBLICATION_SCHEMA = "operational-publication-review-v2"
POSITIONS = frozenset({"QB", "RB", "FB", "WR", "TE", "K", "P", "LS", "OL", "OT", "OG", "C", "G", "T",
                       "DL", "DE", "DT", "NT", "LB", "ILB", "OLB", "MLB", "DB", "CB", "S", "FS", "SS", "<unknown>"})
IDENTITY_COLUMNS = {"player_id", "game_id", "position", "team", "opponent", "kickoff_utc"}
AUDIT_TEXT = {
    "conditional_on": "played", "scale_semantics": "conditional standard deviation",
    "count_support": "nonnegative integers",
    "historical_method_status": "new reconstruction; no claim to reproduce missing original runners",
    "feature_time_requirement": "caller-qualified pregame/lagged f_ features; prefix does not authenticate timing",
}
TIME_CONTRACT = "earlier train kickoff and supplied label availability; caller verifies original source clocks and lag"
QUALIFICATION = "source_qualified and availability_verified true; input_sha256 binds caller's feature manifest"
MISSING_VALUES = "NaN supported; absent required columns or nonnumeric/infinite values rejected"
EVIDENCE = "IMPLEMENTED_UNQUALIFIED_SHADOW; no promotion or forecasting gain implied"


def _fail(message):
    raise ArtifactError("reference content: " + message)


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        _fail("unknown or missing schema fields")


def _hash(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail("invalid SHA256")


def _number(value, *, minimum=None, maximum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail("nonfinite or nonnumeric parameter")
    if integer and (not isinstance(value, int) or value < 0):
        _fail("invalid count")
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        _fail("parameter outside supported range")


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail("duplicate JSON key")
        result[key] = value
    return result


def _read(path):
    path = Path(path)
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file():
        _fail("artifact must be a regular file without symlink components")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        _fail("artifact size exceeds bound")
    body = path.read_bytes()
    try:
        wrapper = json.loads(body, object_pairs_hook=_pairs,
                             parse_constant=lambda value: _fail("nonfinite JSON"))
    except ArtifactError:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ArtifactError("reference content: invalid JSON") from error
    return body, wrapper


def _prior(value, target):
    _keys(value, {"mean", "variance", "n"})
    _number(value["n"], minimum=1, maximum=120000, integer=True)
    _number(value["mean"], minimum=0 if target in COUNT_TARGETS or target == "anytime_td" else None,
            maximum=1 if target == "anytime_td" else None)
    _number(value["variance"], minimum=0)


def _position_map(value):
    if not isinstance(value, dict) or not value or set(value) - POSITIONS:
        _fail("unsupported position aggregate keys")


def _validate(wrapper, *, target=None, method=None, binding=None):
    _keys(wrapper, {"artifact", "sha256"})
    p = wrapper["artifact"]
    _keys(p, {"schema", "model_version", "target", "method", "inference", "participation", "distribution",
              "training_audit", "config", "config_sha256", "code_sha256", "environment", "contains_raw_training_rows",
              "source_schema", "replayable", "replay_limitation", "evidence_state", "operational_source_binding"},
          {"research_registration_sha256"})
    _hash(wrapper["sha256"])
    if wrapper["sha256"] != _digest(p):
        _fail("artifact checksum mismatch")
    t, m = p["target"], p["method"]
    if t not in TARGETS or t == "fantasy_ppr" or m not in {"recent", "pooled"}:
        _fail("unsupported target or method")
    if target is not None and t != target or method is not None and m != method:
        _fail("artifact target/method mismatch")
    if (p["schema"] != "nfl-model-artifact-v1" or p["model_version"] != MODEL_VERSION
            or p["contains_raw_training_rows"] is not False or p["replayable"] is not True
            or p["replay_limitation"] is not None or p["evidence_state"] != EVIDENCE):
        _fail("artifact identity or replay contract mismatch")
    config = {"model_version": MODEL_VERSION, "target": t, "method": m, "registered_methods": list(METHODS),
              "registered_targets": list(TARGETS), "seed": SEED, "ridge_alpha": RIDGE_ALPHA,
              "ensemble_weights": [.5, .25, .25]}
    if p["config"] != config or p["config_sha256"] != _digest(config):
        _fail("configuration mismatch")
    if p["code_sha256"] != _code_hashes() or p["environment"] != _environment():
        _fail("code/environment mismatch")
    if "research_registration_sha256" in p:
        _hash(p["research_registration_sha256"])
    b = p["operational_source_binding"]
    _keys(b, {"version", "policy_sha256", "source_manifest_sha256", "snapshot_sha256", "training_view_sha256",
              "code_sha256", "input_sha256", "training_features_sha256", "query_sha256"})
    if b["version"] != VERSION or set(b["code_sha256"]) != set(CODE_FILES) or b["code_sha256"] != code_hashes():
        _fail("operational code/version binding mismatch")
    for name in set(b) - {"version", "code_sha256"}:
        _hash(b[name])
    if binding is not None and b != binding:
        _fail("source/input/query binding mismatch")
    if p["participation"] != {"kind": "unavailable"}:
        _fail("participation must be unavailable")
    audit = p["training_audit"]
    required = {"model_version", "target", "method", "seed", "temporal_training", "supported_played_training_rows",
                "excluded_unsupported_or_not_played_rows", "participation", "fallback_rows", "abstention_rows", *AUDIT_TEXT}
    _keys(audit, required, {"position_priors", "global_prior", "distribution_fit"})
    if any(audit[k] != v for k, v in {**AUDIT_TEXT, "model_version": MODEL_VERSION, "target": t,
                                      "method": m, "seed": SEED, "participation": PARTICIPATION}.items()):
        _fail("audit identity/text mismatch")
    for name in ("supported_played_training_rows", "excluded_unsupported_or_not_played_rows", "fallback_rows", "abstention_rows"):
        _number(audit[name], integer=True)
    temporal = audit["temporal_training"]
    _keys(temporal, {"input_rows", "removed_future_or_unknown_time_rows", "time_contract"},
          {"label_availability_checked", "fit_before_utc", "bounded_rows_removed"})
    if temporal["time_contract"] != TIME_CONTRACT:
        _fail("temporal audit text mismatch")
    for name in ("input_rows", "removed_future_or_unknown_time_rows", "bounded_rows_removed"):
        if name in temporal:
            _number(temporal[name], integer=True)
    if "label_availability_checked" in temporal and type(temporal["label_availability_checked"]) is not bool:
        _fail("invalid label availability marker")
    if "fit_before_utc" in temporal:
        clock = temporal["fit_before_utc"]
        if not isinstance(clock, str) or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)", clock) is None:
            _fail("invalid fit cutoff clock")
        try:
            datetime.fromisoformat(clock.replace("Z", "+00:00"))
        except ValueError:
            _fail("invalid fit cutoff clock")
    remaining = temporal["input_rows"] - temporal["removed_future_or_unknown_time_rows"] - temporal.get("bounded_rows_removed", 0)
    if remaining != audit["supported_played_training_rows"] + audit["excluded_unsupported_or_not_played_rows"]:
        _fail("training count reconciliation mismatch")
    node = p["inference"]
    supported = audit["supported_played_training_rows"]
    window = 3 if m == "recent" else 8
    summary = [f"f_player_{t}_mean{window}", f"f_player_{t}_n{window}"]
    if supported:
        _keys(node, {"kind", "target", "window", "global_prior", "position_priors", "required_summary_columns", "qualified_summary_columns_present"})
        if (node["kind"] != "recent" or node["target"] != t or type(node["window"]) is not int
                or node["window"] != window or node["required_summary_columns"] != summary
                or node["qualified_summary_columns_present"] is not True):
            _fail("reference parameter graph mismatch")
        _prior(node["global_prior"], t)
        _position_map(node["position_priors"])
        for value in node["position_priors"].values():
            _prior(value, t)
        if (node["global_prior"]["n"] != supported or sum(v["n"] for v in node["position_priors"].values()) != supported
                or audit.get("global_prior") != node["global_prior"] or audit.get("position_priors") != node["position_priors"]):
            _fail("prior support/audit mismatch")
    elif node != {"kind": "unavailable"} or set(audit) & {"global_prior", "position_priors", "distribution_fit"}:
        _fail("unsupported outcomes must abstain")
    dist = p["distribution"]
    if not supported or t == "anytime_td":
        if dist is not None or "distribution_fit" in audit:
            _fail("unexpected distribution parameters")
    else:
        _keys(dist, {"dispersion_kind", "global_dispersion", "position_dispersion", "fit_population"})
        if (dist["dispersion_kind"] != ("NB2_alpha" if t in COUNT_TARGETS else "normal_residual_variance")
                or dist["fit_population"] != "training fitted residuals; calibration not established"
                or audit.get("distribution_fit") != dist):
            _fail("distribution schema/audit mismatch")
        lower = 0 if t in COUNT_TARGETS else 1e-6
        upper = 10 if t in COUNT_TARGETS else None
        _number(dist["global_dispersion"], minimum=lower, maximum=upper)
        _position_map(dist["position_dispersion"])
        if set(dist["position_dispersion"]) != set(node["position_priors"]):
            _fail("dispersion position support mismatch")
        for value in dist["position_dispersion"].values():
            _number(value, minimum=lower, maximum=upper)
    schema = p["source_schema"]
    _keys(schema, {"required_columns", "numeric_columns", "qualification", "missing_values"})
    allowed = IDENTITY_COLUMNS | set(summary) | {"f_player_play_rate8", "f_player_known_participation_n8"}
    columns = schema["required_columns"]
    if (not isinstance(columns, list) or any(not isinstance(c, str) for c in columns)
            or columns != sorted(set(columns)) or set(columns) - allowed or not IDENTITY_COLUMNS <= set(columns)
            or supported and not set(summary) <= set(columns)
            or schema["numeric_columns"] != sorted(c for c in columns if c.startswith("f_"))
            or schema["qualification"] != QUALIFICATION or schema["missing_values"] != MISSING_VALUES):
        _fail("source schema contains unapproved fields")
    return p


def _review(path, *, target=None, method=None, binding=None):
    body, wrapper = _read(path)
    try:
        p = _validate(wrapper, target=target, method=method, binding=binding)
    except ArtifactError:
        raise
    except (TypeError, KeyError, ValueError, OverflowError, RecursionError) as error:
        raise ArtifactError("reference content: malformed schema") from error
    return body, wrapper, p


def review_reference_artifact(path, *, target=None, method=None, binding=None):
    """Review exact known aggregate schemas; return no query or training rows."""
    body, wrapper, p = _review(path, target=target, method=method, binding=binding)
    return {"schema": REVIEW_SCHEMA, "file_sha256": sha256(body).hexdigest(), "artifact_sha256": wrapper["sha256"],
            "target": p["target"], "method": p["method"], "aggregate_only": True,
            "supported_played_training_rows": p["training_audit"]["supported_played_training_rows"],
            "participation": "unavailable", "policy_sha256": p["operational_source_binding"]["policy_sha256"]}


def independent_reference(path, query):
    """Compute all eight outputs from serialized aggregate math, never labels."""
    import numpy as np
    import pandas as pd
    from scipy.stats import bernoulli, nbinom, norm, poisson

    _, _, p = _review(path)
    target, node = p["target"], p["inference"]
    family = "bernoulli" if target == "anytime_td" else "negbin" if target in COUNT_TARGETS else "normal"
    rows = []
    for _, row in query.iterrows():
        mean = scale = float("nan")
        reason = "no_supported_played_training_outcomes"
        position = "<unknown>" if pd.isna(row.get("position")) else str(row.get("position"))
        if node["kind"] == "recent":
            window = node["window"]
            prior = node["position_priors"].get(position, node["global_prior"])["mean"]
            value = pd.to_numeric(row.get(f"f_player_{target}_mean{window}"), errors="coerce")
            count = pd.to_numeric(row.get(f"f_player_{target}_n{window}"), errors="coerce")
            valid = (pd.notna(value) and pd.notna(count) and math.isfinite(value) and math.isfinite(count)
                     and 0 < count <= window and count == math.floor(count))
            if valid and target in COUNT_TARGETS:
                valid = value >= 0
            if valid and target == "anytime_td":
                valid = 0 <= value <= 1
            strength = 3 if window == 3 else 5
            mean = (value * count + strength * prior) / (count + strength) if valid else prior
            reason = "" if valid else "position_prior" if position in node["position_priors"] else "global_prior_unknown_position"
            if target == "anytime_td":
                mean = min(1., max(0., mean))
            elif target in COUNT_TARGETS:
                mean = max(0., mean)
            if target == "anytime_td":
                scale = math.sqrt(mean * (1 - mean))
            elif p["distribution"] is not None:
                dist = p["distribution"]
                dispersion = dist["position_dispersion"].get(position, dist["global_dispersion"])
                scale = math.sqrt(max(0., mean + dispersion * mean * mean if target in COUNT_TARGETS else dispersion))
        quantiles = []
        for q in (.1, .5, .9):
            if target == "anytime_td":
                quantile = bernoulli.ppf(q, mean)
            elif target not in COUNT_TARGETS:
                quantile = norm.ppf(q, loc=mean, scale=scale)
            elif not math.isfinite(mean) or not math.isfinite(scale):
                quantile = float("nan")
            elif mean == 0:
                quantile = 0.
            elif scale * scale > mean + 1e-10:
                shape = mean * mean / (scale * scale - mean)
                quantile = nbinom.ppf(q, shape, shape / (shape + mean))
            else:
                quantile = poisson.ppf(q, mean)
            quantiles.append(quantile)
        rows.append([mean, scale, family, *quantiles, np.nan, reason])
    return pd.DataFrame(rows, columns=["mean", "scale", "family", "p10", "p50", "p90", "p_participation", "fallback"], index=query.index)


def build_publication_manifest(state, reviewed_files, *, policy_sha256, review_state):
    """Build an exact allowlist after explicit content acceptance; never write.

    The caller's ACCEPTED state records their content review under existing lab
    authorization. Software schema checks do not invent a private source grant.
    """
    _hash(policy_sha256)
    if review_state != "ACCEPTED" or not isinstance(reviewed_files, dict) or not reviewed_files:
        _fail("explicit accepted nonempty content review required")
    root = Path(state)
    files = {}
    for name, expected in sorted(reviewed_files.items()):
        if not isinstance(name, str):
            _fail("invalid publication path")
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or relative.as_posix() != name or "\\" in name
                or any(part in {".", ".."} for part in relative.parts)):
            _fail("unsafe publication path")
        _hash(expected)
        review = review_reference_artifact(root / name)
        if review["file_sha256"] != expected or review["policy_sha256"] != policy_sha256:
            _fail("publication reviewed hash/policy mismatch")
        files[name] = expected
    return {"schema_version": PUBLICATION_SCHEMA, "review_state": "ACCEPTED", "policy_sha256": policy_sha256, "files": files}
