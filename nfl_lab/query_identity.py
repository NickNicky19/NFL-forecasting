"""Pure metadata identity versioning; no files, history, features or forecasts.

The caller verifies the registry's exact private file bytes before passing its
three selected columns and SHA256. This adapter never infers identity from a
name, numeric conversion, historical appearance or provider availability.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import re

import pandas as pd
from pandas.api.types import is_scalar

VERSION = "source-qualified-query-identity-v1"
QUERY_COLUMNS = frozenset({"cutoff_utc", "game_id", "kickoff_utc", "opponent", "outcome_available_utc",
    "participation_state", "player_id", "position", "season", "team", "week"})
REGISTRY_COLUMNS = frozenset({"player_id", "sleeper_id", "identity_status"})
OUTPUT_COLUMNS = ("original_player_id", "identity_resolution_state", "identity_source_sha256", "identity_adapter_version")
STATUSES = frozenset({"source_exact_binding", "ambiguous_source_binding", "no_sleeper_binding"})
GSIS = re.compile(r"00-[0-9]{7}", flags=re.ASCII)
SLEEPER = re.compile(r"[0-9]+", flags=re.ASCII)
SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
RESOLVED = frozenset({"verified_registry_gsis", "resolved_registry_ascii_space_gsis", "resolved_source_exact_sleeper"})


def _text(value, field, *, nullable=False):
    if isinstance(value, str):
        return value
    if is_scalar(value) and pd.isna(value) and nullable:
        return None
    raise ValueError(field + " requires exact text" + (" or a missing value" if nullable else ""))


def _frame_hash(frame):
    payload = {"columns": list(frame.columns), "dtypes": [str(dtype) for dtype in frame.dtypes],
        "index_names": [None if name is None else str(name) for name in frame.index.names],
        "index_dtype": str(frame.index.dtype),
        "rows_sha256": hashlib.sha256(pd.util.hash_pandas_object(frame, index=True).values.tobytes()).hexdigest()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _registry(registry):
    if not isinstance(registry, pd.DataFrame) or not registry.columns.is_unique or set(registry) != REGISTRY_COLUMNS:
        raise ValueError("identity registry requires exactly player_id, sleeper_id, identity_status")
    by_player, by_sleeper = defaultdict(set), defaultdict(set)
    valid_players, exact_pairs, bad_players, bad_sleepers = set(), set(), set(), set()
    normalized, unusable = [], set()
    for ordinal, row in enumerate(registry.itertuples(index=False, name=None)):
        values = dict(zip(registry.columns, row))
        player = _text(values["player_id"], "registry player_id", nullable=True)
        sleeper = _text(values["sleeper_id"], "registry sleeper_id", nullable=True)
        status = _text(values["identity_status"], "registry identity_status")
        if status not in STATUSES:
            raise ValueError("unregistered identity status")
        player_ok = player is not None and GSIS.fullmatch(player) is not None
        sleeper_ok = sleeper is not None and SLEEPER.fullmatch(sleeper) is not None
        normalized.append((player, sleeper, status, player_ok, sleeper_ok))
        if player_ok:
            valid_players.add(player)
        if player_ok and sleeper_ok:
            by_player[player].add(sleeper)
            by_sleeper[sleeper].add(player)
        if player_ok and sleeper_ok and status == "source_exact_binding":
            exact_pairs.add((player, sleeper))
        else:
            # Even falsely source-exact rows with missing/malformed IDs cannot
            # lend their surviving alias to a different otherwise valid row.
            unusable.add(ordinal)
            if player_ok:
                bad_players.add(player)
            if sleeper_ok:
                bad_sleepers.add(sleeper)
    conflicted_players = {player for player, candidates in by_player.items() if len(candidates) > 1}
    conflicted_sleepers = {sleeper for sleeper, candidates in by_sleeper.items() if len(candidates) > 1}
    bad_players.update(conflicted_players)
    bad_sleepers.update(conflicted_sleepers)
    for player in bad_players:
        bad_sleepers.update(by_player.get(player, set()))
    mappings = {sleeper: player for player, sleeper in exact_pairs
                if player not in bad_players and sleeper not in bad_sleepers}
    quarantined = {i for i, (player, sleeper, status, player_ok, sleeper_ok) in enumerate(normalized)
                   if i in unusable or player in bad_players or sleeper in bad_sleepers}
    summary = {"rows": len(registry), "identical_duplicate_rows": len(normalized) - len(set(normalized)),
        "valid_gsis_ids": len(valid_players), "usable_exact_sleeper_bindings": len(mappings),
        "unusable_rows": len(unusable), "quarantined_rows": len(quarantined),
        "conflicted_gsis_ids": len(conflicted_players), "conflicted_sleeper_ids": len(conflicted_sleepers),
        "quarantined_sleeper_ids": len(bad_sleepers)}
    return valid_players, mappings, bad_sleepers, summary


def resolve_query_identities(query, registry, *, identity_sha256):
    """Return ``(new_query, aggregate_receipt)`` without modifying either input.

    ``player_id`` is the canonical ID when qualified; unresolved IDs keep their
    original text. The original alias and three provenance columns are appended.
    All remaining columns, their order/dtypes, and the index are preserved.
    Registry duplicates are harmless; inconsistent relations quarantine only
    their affected Sleeper aliases. Query or canonical same-game collisions fail
    the entire transformation, without dropping or selecting opportunities.
    """
    if not isinstance(identity_sha256, str) or SHA256.fullmatch(identity_sha256) is None:
        raise ValueError("identity_sha256 must be exact lowercase SHA256 text")
    if not isinstance(query, pd.DataFrame) or not query.columns.is_unique:
        raise ValueError("query metadata requires a dataframe with unique columns")
    if set(query) & set(OUTPUT_COLUMNS):
        raise ValueError("query already contains reserved identity output columns")
    if set(query) != QUERY_COLUMNS:
        raise ValueError("query requires exactly the eleven metadata columns; statistics/targets are forbidden")
    players = [_text(value, "query player_id") for value in query.player_id]
    games = [_text(value, "query game_id") for value in query.game_id]
    if any(not player or player.isspace() for player in players):
        raise ValueError("query player_id must be nonempty exact text")
    if any(not game or game.isspace() for game in games):
        raise ValueError("query game_id must be nonempty exact text")
    if not all(isinstance(value, str) and value == "unknown" for value in query.participation_state):
        raise ValueError("metadata query participation must remain unknown")
    if len(set(zip(players, games))) != len(query):
        raise ValueError("duplicate input player-game opportunities")
    valid_players, mappings, quarantined_sleepers, registry_summary = _registry(registry)
    canonical, states = [], []
    for player in players:
        result = player
        if GSIS.fullmatch(player):
            state = "verified_registry_gsis" if player in valid_players else "unverified_gsis_not_in_registry"
        elif player.startswith("sleeper:"):
            sleeper = player[len("sleeper:"):]
            if SLEEPER.fullmatch(sleeper) is None:
                state = "unresolved_invalid_sleeper_text"
            elif sleeper in quarantined_sleepers:
                state = "unresolved_ambiguous_registry_binding"
            elif sleeper in mappings:
                result = mappings[sleeper]
                state = "resolved_source_exact_sleeper"
            else:
                state = "unresolved_no_exact_sleeper_binding"
        else:
            trimmed = player.strip(" ")
            if trimmed != player and GSIS.fullmatch(trimmed) and trimmed in valid_players:
                result = trimmed
                state = "resolved_registry_ascii_space_gsis"
            elif trimmed != player and GSIS.fullmatch(trimmed):
                state = "unresolved_unregistered_ascii_space_gsis"
            else:
                state = "unresolved_identity_text"
        canonical.append(result)
        states.append(state)
    if len(set(zip(canonical, games))) != len(query):
        raise ValueError("canonical same-game identity collision; no opportunity selected or dropped")
    output = query.copy(deep=True)
    canonical_series = pd.Series(canonical, index=query.index, dtype=query.player_id.dtype)
    if canonical_series.tolist() != canonical:
        raise ValueError("original player_id dtype cannot retain resolved identity text")
    output["player_id"] = canonical_series
    output["original_player_id"] = query.player_id.copy(deep=True)
    output["identity_resolution_state"] = states
    output["identity_source_sha256"] = identity_sha256
    output["identity_adapter_version"] = VERSION
    counts = dict(sorted(Counter(states).items()))
    receipt = {"schema_version": "query-identity-resolution-receipt-v1", "adapter_version": VERSION,
        "identity_source_sha256": identity_sha256, "input_query_sha256": _frame_hash(query),
        "registry_metadata_sha256": _frame_hash(registry), "output_query_sha256": _frame_hash(output),
        "input_rows": len(query), "output_rows": len(output), "dropped_rows": 0,
        "changed_player_ids": sum(old != new for old, new in zip(players, canonical)),
        "registry_verified_or_resolved_rows": sum(counts.get(state, 0) for state in RESOLVED),
        "unresolved_or_unverified_rows": sum(state not in RESOLVED for state in states),
        "resolution_state_counts": counts, "registry": registry_summary,
        "evidence": "METADATA_IDENTITY_ONLY; no history availability, feature, forecast, issuance or accuracy claim"}
    return output, receipt
