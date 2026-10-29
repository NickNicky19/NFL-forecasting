"""Prepared future-query seam for the frozen ordered CDF, without replay changes.

The retained producer authenticates model/source bytes and current catalog first.
This pure adapter neither acquires history nor fits/loads models nor issues or
persists forecasts. A successful call is not operational admission or capture.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

import numpy as np
import pandas as pd

from . import ordered_recent_v1 as ordered

VERSION = "ordered-cdf-future-query-adapter-v1"
KEYS = ("season", "week", "game_id", "player_id")
CONTEXT = ("team", "opponent", "position", "kickoff_utc", "cutoff_utc")
HISTORY = ("player_id", "game_id", "kickoff_utc", "outcome_available_utc",
           "participation_state", "rush_att", "rec", "rec_tgt")
FORBIDDEN = frozenset({"actual", "outcome", "participation_state", "pass_yd", "pass_td",
    "pass_cmp", "pass_att", "pass_int", "rush_yd", "rush_att", "rec", "rec_tgt", "rec_yd",
    "rush_rec_yd", "anytime_td", "nick-chart-ppr-v1"})
BINDING_KEYS = frozenset({"adapter_version", "ordered_feature_version", "target",
    "model_sha256", "procedure_sha256", "source_policy_sha256", "feature_schema_sha256",
    "source_availability_policy", "base_features"})


def feature_schema_sha256(target, base_features):
    schema = {"target": target, "base_features": list(base_features),
              "ordered_features": ordered.columns(target), "ordered_feature_version": ordered.VERSION}
    return hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _clock(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("known timezone-aware clock required; never invent availability")
    return stamp.tz_convert("UTC")


def validate_binding(binding, *, trusted_binding):
    """Expected binding must originate in the retained owner's admitted catalog."""
    if binding != trusted_binding or set(binding) != BINDING_KEYS:
        raise ValueError("exact independently trusted source/model/procedure binding required")
    if (binding["adapter_version"] != VERSION or binding["ordered_feature_version"] != ordered.VERSION
            or binding["target"] not in ("rush_att", "rec")):
        raise ValueError("frozen ordered target/feature/adapter identity differs")
    for name in ("model_sha256", "procedure_sha256", "source_policy_sha256", "feature_schema_sha256"):
        if not _hash(binding[name]):
            raise ValueError("complete authentic binding identities required")
    features = binding["base_features"]
    if (not isinstance(features, list) or not features or len(features) != len(set(features))
            or any(not isinstance(name, str) or not name.startswith("f_") for name in features)
            or set(features) & set(ordered.ALL_COLUMNS)):
        raise ValueError("exact unchanged base features required")
    if binding["feature_schema_sha256"] != feature_schema_sha256(binding["target"], features):
        raise ValueError("exact base-plus-ordered feature schema hash differs")
    if not isinstance(binding["source_availability_policy"], str) or not binding["source_availability_policy"]:
        raise ValueError("truthful named source-availability policy required")


@dataclass(frozen=True)
class PreparedQuery:
    frame: pd.DataFrame
    prior_only: tuple[bool, ...]
    prior_reasons: tuple[str, ...]
    binding: dict
    frame_sha256: str


def _frame_hash(frame):
    header = json.dumps([(str(c), str(frame[c].dtype)) for c in frame], separators=(",", ":")).encode()
    return hashlib.sha256(header + pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes()).hexdigest()


def prepare_future_queries(base, history, *, binding, trusted_binding):
    """Append unchanged ordered slots to one already-qualified cutoff group.

    Caller projects history numerics *before* this seam using both strict source
    availability and kickoff. No later numeric rows are accepted even though the
    original feature helper also masks them. Unknown/DNP slots stay nonnumeric.
    Unknown base-feature clocks force the trained prior; they are never filled
    from an assumed publication time. Assumed historical timing retains its name.
    """
    validate_binding(binding, trusted_binding=trusted_binding)
    if not isinstance(base, pd.DataFrame) or not 0 < len(base) <= 4096:
        raise ValueError("bounded nonempty query frame required")
    if not isinstance(history, pd.DataFrame) or len(history) > 500000:
        raise ValueError("bounded already-projected history required")
    required = set(KEYS + CONTEXT) | set(binding["base_features"]) | {"feature_max_source_available_utc"}
    if required - set(base) or set(HISTORY) - set(history):
        raise ValueError("complete unchanged base/query/history schema required")
    if FORBIDDEN & set(base) or set(ordered.ALL_COLUMNS) & set(base):
        raise ValueError("target-game labels or precomputed ordered columns cannot enter query")
    q = base.copy().reset_index(drop=True)
    if q[list(KEYS) + ["team", "opponent", "position"]].isna().any(axis=None) or q.duplicated(list(KEYS)).any():
        raise ValueError("unique complete canonical query identities required")
    cutoff = [_clock(x) for x in q.cutoff_utc]
    kickoff = [_clock(x) for x in q.kickoff_utc]
    if len(set(cutoff)) != 1 or any(c >= k for c, k in zip(cutoff, kickoff)):
        raise ValueError("one strict pre-kickoff cutoff group required")
    limit = cutoff[0]
    h = history.copy()
    if h[["player_id", "game_id"]].isna().any(axis=None) or h.duplicated(["player_id", "game_id"]).any():
        raise ValueError("unique complete prior-game identities required")
    if h.game_id.isin(q.game_id).any():
        raise ValueError("target game cannot be projected into prior history")
    if not h.participation_state.isin(ordered.STATES).all():
        raise ValueError("unknown participation is explicit; unsupported state forbidden")
    for name in ("kickoff_utc", "outcome_available_utc"):
        h[name] = pd.to_datetime([_clock(x) for x in h[name]], utc=True)
    if not ((h.kickoff_utc < h.outcome_available_utc) & (h.outcome_available_utc < limit)
            & (h.kickoff_utc < limit)).all():
        raise ValueError("history must be projected by qualified availability before numeric access")
    prepared = ordered.augment(q, h)
    reasons, effective = [], []
    by_player = {str(p): t.sort_values(["kickoff_utc", "game_id"], kind="stable").tail(4)
                 for p, t in h.groupby("player_id", sort=False)}
    for row in q.to_dict("records"):
        raw = row["feature_max_source_available_utc"]
        source = None if pd.isna(raw) else _clock(raw)
        if source is not None and source >= limit:
            raise ValueError("base source must be strictly before information cutoff")
        played = row.get("f_player_games_prior")
        warm = isinstance(played, (int, float, np.integer, np.floating)) and math.isfinite(played) and played > 0
        reason = ("missing_feature_query_position_prior" if row.get("feature_query_available") is False
                  else "unknown_feature_clock_position_prior" if source is None
                  else "cold_or_unknown_history_position_prior" if not warm else "")
        old = by_player.get(str(row["player_id"]))
        ordered_max = None if old is None or old.empty else old.outcome_available_utc.max()
        clocks = [x for x in (source, ordered_max) if x is not None]
        reasons.append(reason)
        effective.append(None if reason or not clocks else max(clocks))
    prepared["feature_max_source_available_utc"] = effective
    prepared["ordered_future_adapter_version"] = VERSION
    return PreparedQuery(prepared, tuple(bool(x) for x in reasons), tuple(reasons), dict(binding), _frame_hash(prepared))


def predict_prepared_batches(model, prepared, *, trusted_binding, batch_size=128):
    """Yield original complete laws without changing the strict historical API.

    The caller must load the exact trusted model hash through the retained owner
    seam before calling. No hash asserted by an untrusted request authenticates a
    model object. Returned laws still require immutable pre-deadline persistence.
    """
    if not isinstance(prepared, PreparedQuery) or not 0 < batch_size <= 256:
        raise ValueError("prepared bounded future query required")
    validate_binding(prepared.binding, trusted_binding=trusted_binding)
    if (_frame_hash(prepared.frame) != prepared.frame_sha256
            or len(prepared.frame) != len(prepared.prior_only) or len(prepared.frame) != len(prepared.prior_reasons)):
        raise ValueError("prepared future frame changed after validation")
    binding = prepared.binding
    expected = list(binding["base_features"]) + ordered.columns(binding["target"])
    if (model.panel != "context" or model.category["target"] != binding["target"]
            or model.category["support"] != "count" or model.category["panels"]["context"] != expected):
        raise ValueError("actual ordered model target/panel/features differ from catalog")
    seen = set()
    for force_prior in (False, True):
        indices = np.array([i for i, x in enumerate(prepared.prior_only) if x == force_prior], dtype=int)
        if not len(indices):
            continue
        subset = prepared.frame.iloc[indices].reset_index(drop=True)
        for positions, law, original_reasons in model.predict_batches(subset, batch_size=batch_size, prior_only=force_prior):
            positions = np.asarray(positions)
            if (positions.ndim != 1 or not np.issubdtype(positions.dtype, np.integer)
                    or any(x < 0 or x >= len(indices) for x in positions)
                    or len(positions) != len(original_reasons)):
                raise ValueError("model returned invalid future batch positions/reasons")
            mapped = indices[positions]
            if len(set(mapped)) != len(mapped) or any(int(i) in seen for i in mapped):
                raise ValueError("duplicate future inference position")
            seen.update(int(i) for i in mapped)
            reasons = [prepared.prior_reasons[i] or str(reason)
                       for i, reason in zip(mapped, original_reasons)]
            yield mapped, law, reasons
    if seen != set(range(len(prepared.frame))):
        raise ValueError("incomplete future inference population")
