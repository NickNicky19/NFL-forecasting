"""Versioned nullable future-placeholder guard for canonical feature input.

The v1 validator and failed v1 feature guard remain unchanged. This module
delegates feature calculation once to the same qualified source implementation.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from . import canonical_feature_inputs as v1
from . import operational_sources, query_identity
from .data import TARGETS

VERSION = "canonical-feature-input-v2"
validate_canonical_query = v1.validate_canonical_query


def build_canonical_features(history, canonical_query, *, policy):
    """Build once while treating missing future availability as a placeholder.

    Only query ``outcome_available_utc`` may be missing. Any supplied value must
    equal kickoff plus seven days. The source builder supplies that same future
    placeholder; it is never evidence of observed outcome availability.
    """
    if not isinstance(canonical_query, pd.DataFrame) or not canonical_query.columns.is_unique:
        raise ValueError("validated canonical query dataframe required")
    if not isinstance(policy, dict):
        raise ValueError("caller must supply the already loaded operational policy mapping")
    provenance = canonical_query.attrs.get(v1.VALIDATION_ATTR)
    v1._keys(provenance, {"adapter_version", "identity_source_sha256", "input_query_sha256", "canonical_query_sha256", "identity_receipt_sha256"})
    if provenance["adapter_version"] != v1.VERSION or set(canonical_query) != query_identity.QUERY_COLUMNS | set(query_identity.OUTPUT_COLUMNS):
        raise ValueError("canonical validation provenance/schema mismatch")
    for name in set(provenance) - {"adapter_version"}:
        v1._hash(provenance[name])
    if query_identity._frame_hash(canonical_query) != provenance["canonical_query_sha256"]:
        raise ValueError("validated canonical query changed before feature calculation")
    clocks = {name: v1._utc(canonical_query[name], name) for name in v1.TIME_COLUMNS}
    if (clocks["kickoff_utc"].isna().any() or clocks["cutoff_utc"].isna().any()
            or (clocks["cutoff_utc"] > clocks["kickoff_utc"]).any()):
        raise ValueError("canonical cutoff/kickoff clocks required")
    expected_future = clocks["kickoff_utc"] + pd.Timedelta(days=7)
    missing_future = canonical_query["outcome_available_utc"].isna()
    if (~missing_future & clocks["outcome_available_utc"].isna()).any():
        raise ValueError("only null future availability placeholders may be missing")
    if (~missing_future & ~clocks["outcome_available_utc"].eq(expected_future)).any():
        raise ValueError("nonnull query availability placeholder must equal kickoff plus seven days")
    source_manifest = deepcopy(history.attrs.get("operational_manifest", {}))
    for name in ("policy_sha256", "snapshot_sha256", "training_view_sha256"):
        v1._hash(source_manifest.get(name))
    result = operational_sources.build_operational_features(history.copy(deep=True), policy=policy,
                                                           queries=canonical_query.copy(deep=True))
    if not result.columns.is_unique or len(result) != len(canonical_query):
        raise ValueError("qualified feature rows/schema changed")
    try:
        pd.testing.assert_index_equal(result.index, canonical_query.index, exact=True)
    except AssertionError as error:
        raise ValueError("qualified feature index/order changed") from error
    for name in canonical_query:
        if name in v1.TIME_COLUMNS:
            expected = expected_future if name == "outcome_available_utc" else clocks[name]
            if not v1._utc(result[name], name).equals(expected):
                raise ValueError("qualified canonical context clock changed")
        else:
            v1._same_frame(result[[name]], canonical_query[[name]], "qualified canonical context/provenance changed")
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
    source_clock = v1._utc(result["feature_max_source_available_utc"], "feature source")
    assumed = v1._utc(result["feature_max_assumed_history_available_utc"], "assumed history")
    if source_clock.isna().any() or (source_clock > clocks["cutoff_utc"]).any() or (assumed.notna() & (assumed >= clocks["cutoff_utc"])).any():
        raise ValueError("qualified feature availability exceeds cutoff")
    if (result.f_player_games_prior.gt(0) & assumed.isna()).any():
        raise ValueError("nonempty history requires an assumed source clock")
    manifest = result.attrs.get("operational_manifest", {})
    for name in ("policy_sha256", "snapshot_sha256", "training_view_sha256"):
        if manifest.get(name) != source_manifest[name]:
            raise ValueError("qualified feature source lineage changed")
    lineage = {**deepcopy(provenance), "schema_version": "canonical-feature-input-receipt-v2",
        "adapter_version": VERSION, "metadata_validator_version": v1.VERSION,
        "identity_adapter_version": query_identity.VERSION,
        "query_rows": len(result), "query_games": int(result.game_id.nunique()), "feature_columns": len(feature_columns),
        "feature_frame_sha256": query_identity._frame_hash(result),
        "feature_values_sha256": query_identity._frame_hash(result[feature_columns]),
        "canonical_context_sha256": query_identity._frame_hash(result[list(canonical_query)]),
        "policy_sha256": source_manifest["policy_sha256"], "snapshot_sha256": source_manifest["snapshot_sha256"],
        "training_view_sha256": source_manifest["training_view_sha256"],
        "source_manifest_sha256": v1._digest(source_manifest), "operational_feature_view_sha256": manifest.get("feature_view_sha256"),
        "feature_builder_calls": 1, "target_labels": "all twelve null", "participation": "unknown; probability unavailable",
        "missing_future_placeholder_rows": int(missing_future.sum()),
        "future_placeholder_rule": "kickoff plus seven days; assumed_not_observed; not an outcome publication receipt",
        "evidence_lane": v1.EVIDENCE,
        "timing": "UTC-normalized metadata clocks; reconstructed assumed history strictly before cutoff; caller records actual derivation and persistence clocks; no issuance claim"}
    v1._hash(lineage["operational_feature_view_sha256"])
    return result, lineage
