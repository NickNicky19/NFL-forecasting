"""Validate a frozen identity revision and reuse the qualified feature builder.

No file loader, clock, writer, fitting, prediction or publication lives here.
The caller authenticates private file bytes and records actual derivation time.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from . import operational_sources, query_identity
from .data import TARGETS

VERSION = "canonical-feature-input-v1"
EVIDENCE = "VERSIONED_METADATA_RECONSTRUCTION_NOT_ISSUED"
VALIDATION_ATTR = "canonical_query_validation"
STATES = query_identity.RESOLVED | frozenset({"unverified_gsis_not_in_registry",
    "unresolved_invalid_sleeper_text", "unresolved_ambiguous_registry_binding",
    "unresolved_no_exact_sleeper_binding", "unresolved_unregistered_ascii_space_gsis", "unresolved_identity_text"})
RECEIPT_KEYS = frozenset({"schema_version", "adapter_version", "identity_source_sha256", "input_query_sha256",
    "registry_metadata_sha256", "output_query_sha256", "input_rows", "output_rows", "dropped_rows",
    "changed_player_ids", "registry_verified_or_resolved_rows", "unresolved_or_unverified_rows",
    "resolution_state_counts", "registry", "evidence"})
REGISTRY_KEYS = frozenset({"rows", "identical_duplicate_rows", "valid_gsis_ids", "usable_exact_sleeper_bindings",
    "unusable_rows", "quarantined_rows", "conflicted_gsis_ids", "conflicted_sleeper_ids", "quarantined_sleeper_ids"})
IDENTITY_EVIDENCE = "METADATA_IDENTITY_ONLY; no history availability, feature, forecast, issuance or accuracy claim"
TIME_COLUMNS = ("kickoff_utc", "cutoff_utc", "outcome_available_utc")


def _hash(value):
    if not isinstance(value, str) or query_identity.SHA256.fullmatch(value) is None:
        raise ValueError("exact lowercase SHA256 required")


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer count required")


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("unknown or missing canonical schema fields")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _same_frame(left, right, message):
    try:
        pd.testing.assert_frame_equal(left, right, check_exact=True)
    except AssertionError as error:
        raise ValueError(message) from error


def _state_contract(original, canonical, state):
    if not isinstance(canonical, str) or not canonical or canonical.isspace() or not isinstance(state, str) or state not in STATES:
        raise ValueError("invalid canonical identity or resolution state")
    gsis = query_identity.GSIS
    if state == "resolved_source_exact_sleeper":
        if not original.startswith("sleeper:") or query_identity.SLEEPER.fullmatch(original[8:]) is None or gsis.fullmatch(canonical) is None:
            raise ValueError("invalid exact Sleeper resolution shape")
    elif state == "resolved_registry_ascii_space_gsis":
        if original == canonical or original.strip(" ") != canonical or gsis.fullmatch(canonical) is None:
            raise ValueError("invalid registered ASCII-space resolution")
    elif canonical != original:
        raise ValueError("unresolved/unchanged identity was modified")
    if state in {"verified_registry_gsis", "unverified_gsis_not_in_registry"} and gsis.fullmatch(original) is None:
        raise ValueError("invalid unchanged GSIS identity")
    if state in {"unresolved_ambiguous_registry_binding", "unresolved_no_exact_sleeper_binding"}:
        if not original.startswith("sleeper:") or query_identity.SLEEPER.fullmatch(original[8:]) is None:
            raise ValueError("invalid unresolved Sleeper identity")


def validate_canonical_query(payload, original_query, *, expected_identity_sha256):
    """Reconstruct the accepted private envelope and verify its metadata binding.

    File SHA256 authentication belongs to the caller. No registry, feature or
    source values are loaded or inferred to repair an inconsistent document.
    """
    _hash(expected_identity_sha256)
    _keys(payload, {"evidence_lane", "columns", "index", "rows", "receipt"})
    if payload["evidence_lane"] != EVIDENCE:
        raise ValueError("canonical query must remain a nonissued metadata reconstruction")
    if not isinstance(original_query, pd.DataFrame) or not original_query.columns.is_unique or set(original_query) != query_identity.QUERY_COLUMNS:
        raise ValueError("original query requires exactly eleven metadata columns")
    for name in ("player_id", "game_id"):
        if any(not isinstance(v, str) or not v or v.isspace() for v in original_query[name]):
            raise ValueError("original identity requires nonempty exact text")
    if not original_query.participation_state.eq("unknown").all():
        raise ValueError("original participation must remain unknown")
    if original_query.duplicated(["player_id", "game_id"]).any():
        raise ValueError("duplicate original player-game opportunities")
    columns = list(original_query.columns) + list(query_identity.OUTPUT_COLUMNS)
    if payload["columns"] != columns or not isinstance(payload["index"], list) or not isinstance(payload["rows"], list):
        raise ValueError("canonical column/order/index schema mismatch")
    if len(payload["rows"]) != len(original_query) or len(payload["index"]) != len(original_query):
        raise ValueError("canonical row/index count mismatch")
    for row in payload["rows"]:
        _keys(row, columns)
    frame = pd.DataFrame(payload["rows"], columns=columns, index=payload["index"])
    frame.index.names = original_query.index.names
    try:
        pd.testing.assert_index_equal(frame.index, original_query.index, exact="equiv")
    except AssertionError as error:
        raise ValueError("canonical index/order mismatch") from error
    frame.index = original_query.index.copy()
    context = [name for name in original_query if name != "player_id"]
    _same_frame(frame[context], original_query[context], "canonical original context/dtypes changed")
    if frame.player_id.dtype != original_query.player_id.dtype:
        raise ValueError("canonical identity dtype changed")
    _same_frame(frame[["original_player_id"]].rename(columns={"original_player_id": "player_id"}),
                original_query[["player_id"]], "canonical original aliases changed")
    if not frame.identity_source_sha256.eq(expected_identity_sha256).all() or not frame.identity_adapter_version.eq(query_identity.VERSION).all():
        raise ValueError("canonical identity source/version mismatch")
    if any(str(frame[name].dtype) != "object" for name in query_identity.OUTPUT_COLUMNS):
        raise ValueError("canonical provenance must retain accepted object-string dtypes")
    for old, new, state in zip(original_query.player_id, frame.player_id, frame.identity_resolution_state):
        _state_contract(old, new, state)
    if frame.duplicated(["player_id", "game_id"]).any():
        raise ValueError("canonical same-game identity collision")
    receipt = payload["receipt"]
    _keys(receipt, RECEIPT_KEYS)
    if (receipt["schema_version"] != "query-identity-resolution-receipt-v1"
            or receipt["adapter_version"] != query_identity.VERSION or receipt["evidence"] != IDENTITY_EVIDENCE
            or receipt["identity_source_sha256"] != expected_identity_sha256):
        raise ValueError("canonical receipt identity/schema mismatch")
    for name in ("identity_source_sha256", "input_query_sha256", "registry_metadata_sha256", "output_query_sha256"):
        _hash(receipt[name])
    if receipt["input_query_sha256"] != query_identity._frame_hash(original_query) or receipt["output_query_sha256"] != query_identity._frame_hash(frame):
        raise ValueError("canonical receipt frame hash mismatch")
    counts = dict(sorted(Counter(frame.identity_resolution_state).items()))
    if not isinstance(receipt["resolution_state_counts"], dict) or set(receipt["resolution_state_counts"]) - STATES:
        raise ValueError("invalid canonical resolution count schema")
    for value in receipt["resolution_state_counts"].values():
        _count(value)
    if receipt["resolution_state_counts"] != counts:
        raise ValueError("canonical resolution state counts mismatch")
    expected = {"input_rows": len(original_query), "output_rows": len(frame), "dropped_rows": 0,
        "changed_player_ids": int(original_query.player_id.ne(frame.player_id).sum()),
        "registry_verified_or_resolved_rows": int(frame.identity_resolution_state.isin(query_identity.RESOLVED).sum()),
        "unresolved_or_unverified_rows": int((~frame.identity_resolution_state.isin(query_identity.RESOLVED)).sum())}
    for name, value in expected.items():
        _count(receipt[name])
        if receipt[name] != value:
            raise ValueError("canonical receipt aggregate count mismatch")
    _keys(receipt["registry"], REGISTRY_KEYS)
    for value in receipt["registry"].values():
        _count(value)
    if any(value > receipt["registry"]["rows"] for value in receipt["registry"].values()):
        raise ValueError("canonical registry count exceeds row population")
    frame.attrs[VALIDATION_ATTR] = {"adapter_version": VERSION, "identity_source_sha256": expected_identity_sha256,
        "input_query_sha256": receipt["input_query_sha256"], "canonical_query_sha256": receipt["output_query_sha256"],
        "identity_receipt_sha256": _digest(receipt)}
    return frame


def _utc(values, name):
    try:
        return pd.to_datetime(values, utc=True, errors="raise")
    except (TypeError, ValueError) as error:
        raise ValueError("invalid canonical feature clock: " + name) from error


def build_canonical_features(history, canonical_query, *, policy):
    """Call the unchanged qualified builder once, then validate its result.

    The deterministic aggregate receipt has no row values, execution clock or
    issuance claim. The caller binds actual code/file hashes and execution time.
    """
    if not isinstance(canonical_query, pd.DataFrame) or not canonical_query.columns.is_unique:
        raise ValueError("validated canonical query dataframe required")
    if not isinstance(policy, dict):
        raise ValueError("caller must supply the already loaded operational policy mapping")
    provenance = canonical_query.attrs.get(VALIDATION_ATTR)
    _keys(provenance, {"adapter_version", "identity_source_sha256", "input_query_sha256", "canonical_query_sha256", "identity_receipt_sha256"})
    if provenance["adapter_version"] != VERSION or set(canonical_query) != query_identity.QUERY_COLUMNS | set(query_identity.OUTPUT_COLUMNS):
        raise ValueError("canonical validation provenance/schema mismatch")
    for name in set(provenance) - {"adapter_version"}:
        _hash(provenance[name])
    if query_identity._frame_hash(canonical_query) != provenance["canonical_query_sha256"]:
        raise ValueError("validated canonical query changed before feature calculation")
    clocks = {name: _utc(canonical_query[name], name) for name in TIME_COLUMNS}
    if any(values.isna().any() for values in clocks.values()) or (clocks["cutoff_utc"] > clocks["kickoff_utc"]).any():
        raise ValueError("canonical cutoff/kickoff/availability clocks required")
    if not clocks["outcome_available_utc"].eq(clocks["kickoff_utc"] + pd.Timedelta(days=7)).all():
        raise ValueError("canonical query availability placeholder must equal kickoff plus seven days")
    # Pass copies to preserve caller-owned attrs/frames even if a guard fails.
    source_manifest = deepcopy(history.attrs.get("operational_manifest", {}))
    for name in ("policy_sha256", "snapshot_sha256", "training_view_sha256"):
        _hash(source_manifest.get(name))
    result = operational_sources.build_operational_features(history.copy(deep=True), policy=policy,
                                                           queries=canonical_query.copy(deep=True))
    if not result.columns.is_unique or len(result) != len(canonical_query):
        raise ValueError("qualified feature rows/schema changed")
    try:
        pd.testing.assert_index_equal(result.index, canonical_query.index, exact=True)
    except AssertionError as error:
        raise ValueError("qualified feature index/order changed") from error
    for name in canonical_query:
        if name in TIME_COLUMNS:
            if not _utc(result[name], name).equals(clocks[name]):
                raise ValueError("qualified canonical context clock changed")
        else:
            _same_frame(result[[name]], canonical_query[[name]], "qualified canonical context/provenance changed")
    if set(TARGETS) - set(result) or not result[list(TARGETS)].isna().all().all() or not result.participation_state.eq("unknown").all():
        raise ValueError("query labels must remain null and participation unknown")
    if ("f_player_play_rate8" not in result or not result.f_player_play_rate8.isna().all()
            or "participation_probability_state" not in result
            or not result.participation_probability_state.eq("unavailable_incomplete_nonappearance_denominator").all()):
        raise ValueError("query participation probability must remain unavailable")
    feature_columns = [name for name in result if name.startswith("f_")]
    if len(feature_columns) != 97:
        raise ValueError("exactly 97 frozen feature columns required")
    for name in feature_columns:
        if not is_numeric_dtype(result[name].dtype) or np.isinf(result[name].to_numpy(dtype=float, na_value=np.nan)).any():
            raise ValueError("qualified features must be numeric finite-or-missing values")
    source_clock = _utc(result["feature_max_source_available_utc"], "feature source")
    assumed = _utc(result["feature_max_assumed_history_available_utc"], "assumed history")
    if source_clock.isna().any() or (source_clock > clocks["cutoff_utc"]).any() or (assumed.notna() & (assumed >= clocks["cutoff_utc"])).any():
        raise ValueError("qualified feature availability exceeds cutoff")
    if (result.f_player_games_prior.gt(0) & assumed.isna()).any():
        raise ValueError("nonempty history requires an assumed source clock")
    manifest = result.attrs.get("operational_manifest", {})
    for name in ("policy_sha256", "snapshot_sha256", "training_view_sha256"):
        _hash(source_manifest.get(name))
        if manifest.get(name) != source_manifest[name]:
            raise ValueError("qualified feature source lineage changed")
    lineage = {"schema_version": "canonical-feature-input-receipt-v1", "adapter_version": VERSION,
        "identity_adapter_version": query_identity.VERSION, **deepcopy(provenance),
        "query_rows": len(result), "query_games": int(result.game_id.nunique()), "feature_columns": len(feature_columns),
        "feature_frame_sha256": query_identity._frame_hash(result),
        "feature_values_sha256": query_identity._frame_hash(result[feature_columns]),
        "canonical_context_sha256": query_identity._frame_hash(result[list(canonical_query)]),
        "policy_sha256": source_manifest["policy_sha256"], "snapshot_sha256": source_manifest["snapshot_sha256"],
        "training_view_sha256": source_manifest["training_view_sha256"],
        "source_manifest_sha256": _digest(source_manifest), "operational_feature_view_sha256": manifest.get("feature_view_sha256"),
        "feature_builder_calls": 1, "target_labels": "all twelve null", "participation": "unknown; probability unavailable",
        "evidence_lane": EVIDENCE,
        "timing": "UTC-normalized metadata clocks; reconstructed assumed history strictly before cutoff; caller records actual derivation and persistence clocks; no issuance claim"}
    _hash(lineage["operational_feature_view_sha256"])
    return result, lineage
