"""Qualify fresh daily identity metadata before the existing feature builder.

The accepted resolver supplies exact provider and Sleeper candidate identities.
This caller retains existing conflict abstention and first captured identities.
No source loader, model, clock, capture or publication is implemented here.
"""
from collections import Counter
import hashlib
from pathlib import Path

import pandas as pd

from . import query_identity
from .state import digest

VERSION = "hosted-reference-identity-v1"
PROVENANCE = (*query_identity.OUTPUT_COLUMNS, "canonical_identity_adapter_version")
CONTEXT = frozenset({"sleeper_id", "identity_binding", "player_name", "is_home",
    "injury_status_observed", "population_eligibility"})


def code_hashes():
    """Bind the reused resolver and state guard alongside this thin caller."""
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
            ("hosted_reference_adapter.py", "query_identity.py", "reference_runtime.py")}


def adapt_live_identities(population, registry, *, identity_sha256, frozen_by_game_sleeper):
    """Return a new full population and aggregate-only identity lineage.

    Input comes from unchanged future_population with no crosswalk dictionary.
    Its already frozen IDs remain locked. Only unfrozen metadata enters the
    accepted resolver; provider and explicit Sleeper views retain exact context.
    """
    required = query_identity.QUERY_COLUMNS | {"sleeper_id", "identity_binding"}
    if (not isinstance(population, pd.DataFrame) or not population.columns.is_unique
            or not population.index.is_unique or not required <= set(population)
            or not set(population) <= query_identity.QUERY_COLUMNS | CONTEXT):
        raise ValueError("fresh live metadata with unique row index required")
    if not population.identity_binding.isin({"sleeper_gsis", "unlinked_cold_start", "frozen_first_sleeper_binding"}).all():
        raise ValueError("live population must precede crosswalk candidate selection")
    if any(not isinstance(sid, str) or not sid or sid.isspace() for sid in population.sleeper_id):
        raise ValueError("Sleeper aliases require nonempty exact text")
    if (not population.participation_state.eq("unknown").all()
            or any(not isinstance(value, str) or not value or value.isspace()
                   for field in ("player_id", "game_id") for value in population[field])):
        raise ValueError("live metadata requires exact identities and unknown participation")
    selected_registry = registry[["player_id", "sleeper_id", "identity_status"]].copy()
    metadata = population[[name for name in population if name in query_identity.QUERY_COLUMNS]].copy()
    locked = []
    for row in population.itertuples():
        key = (row.game_id, row.sleeper_id)
        if key in frozen_by_game_sleeper:
            frozen = frozen_by_game_sleeper[key]
            if not isinstance(frozen, str) or not frozen or frozen.isspace() or row.player_id != frozen:
                raise ValueError("first frozen live identity changed before adapter")
            locked.append(True)
        else:
            if row.identity_binding == "frozen_first_sleeper_binding":
                raise ValueError("frozen identity requires its original explicit binding")
            locked.append(False)
    unlocked = pd.Series([not value for value in locked], index=population.index)
    provider_query = metadata.loc[unlocked].copy()
    sleeper_query = provider_query.copy()
    sleeper_query["player_id"] = "sleeper:" + population.loc[unlocked, "sleeper_id"]
    provider, provider_receipt = query_identity.resolve_query_identities(provider_query, selected_registry,
        identity_sha256=identity_sha256)
    sleeper, sleeper_receipt = query_identity.resolve_query_identities(sleeper_query, selected_registry,
        identity_sha256=identity_sha256)
    output = population.copy(deep=True)
    output["original_player_id"] = population.player_id.copy(deep=True)
    output["identity_resolution_state"] = "frozen_first_identity"
    output["identity_source_sha256"] = identity_sha256
    output["identity_adapter_version"] = VERSION
    output["canonical_identity_adapter_version"] = query_identity.VERSION
    for index in provider.index:
        direct = population.at[index, "identity_binding"] == "sleeper_gsis"
        provider_id, source_id = provider.at[index, "player_id"], sleeper.at[index, "player_id"]
        source_state = sleeper.at[index, "identity_resolution_state"]
        conflict = (source_state == "unresolved_ambiguous_registry_binding" or
            (direct and source_state == "resolved_source_exact_sleeper" and provider_id != source_id))
        if conflict:
            output.at[index, "player_id"] = "sleeper:" + population.at[index, "sleeper_id"]
            output.at[index, "identity_binding"] = "conflicting_identity_cold_start"
            output.at[index, "identity_resolution_state"] = "unresolved_live_provider_registry_conflict"
        elif direct:
            output.at[index, "player_id"] = provider_id
            output.at[index, "identity_resolution_state"] = provider.at[index, "identity_resolution_state"]
        else:
            output.at[index, "player_id"] = source_id
            output.at[index, "identity_binding"] = "nflverse_exact_id_crosswalk" if source_state == "resolved_source_exact_sleeper" else "unlinked_cold_start"
            output.at[index, "identity_resolution_state"] = source_state
    # The first captured identity wins after every new candidate decision.
    for index in output.index:
        key = (output.at[index, "game_id"], output.at[index, "sleeper_id"])
        if key in frozen_by_game_sleeper:
            output.at[index, "player_id"] = frozen_by_game_sleeper[key]
            output.at[index, "identity_binding"] = "frozen_first_sleeper_binding"
    if output.duplicated(["player_id", "game_id"]).any():
        raise ValueError("canonical same-game live identity collision; no rows selected or dropped")
    receipt = {"schema_version": "hosted-reference-identity-receipt-v1", "adapter_version": VERSION,
        "canonical_adapter_version": query_identity.VERSION, "identity_source_sha256": identity_sha256,
        "input_rows": len(population), "output_rows": len(output), "dropped_rows": 0,
        "frozen_identity_rows": sum(locked), "changed_player_ids": int(population.player_id.ne(output.player_id).sum()),
        "resolution_state_counts": dict(sorted(Counter(output.identity_resolution_state).items())),
        "provider_candidates": provider_receipt, "sleeper_candidates": sleeper_receipt,
        "input_metadata_sha256": query_identity._frame_hash(metadata),
        "output_metadata_sha256": query_identity._frame_hash(output),
        "scope": "Live metadata identity only; capture clocks, participation proof and accuracy remain separately qualified"}
    receipt["receipt_sha256"] = digest(receipt)
    return output, receipt
