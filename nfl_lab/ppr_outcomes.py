"""Keep the full planned PPR panel while qualifying each source observation.

This adapter does not establish a new NFLverse/Sleeper credit bridge.  It joins
canonical identities exactly, requires independently recorded participation,
and delegates scoring to the existing strict component adapters.  In
particular, a source's fantasy total is never a substitute for components.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import math
from numbers import Real
import re
from typing import Mapping, Sequence

from .ppr_sources import nflverse_components, sleeper_components
from .scoring import SCORING_VERSION

IDENTITY_FIELDS = ("player_id", "game_id", "team", "opponent", "season", "week", "season_type")
OFFENSIVE_ROLES = frozenset({"QB", "RB", "FB", "WR", "TE"})
ADAPTER_VERSION = "strict-planned-ppr-outcomes-v1"


def _identity(row: Mapping) -> tuple:
    def invalid(value):
        if value is None or str(value).strip() in {"", "<NA>", "NaT"}:
            return True
        if isinstance(value, Real):
            return isinstance(value, bool) or not math.isfinite(float(value))
        return not isinstance(value, str)

    missing = [key for key in IDENTITY_FIELDS if invalid(row.get(key))]
    if missing:
        raise ValueError(f"PPR identity missing {missing}")
    # The shared identity registry owns aliases and namespace conversion.
    # Converting values to text permits JSON integer/string season fields;
    # it never guesses a game, team, player or period binding.
    return tuple(str(row[key]) for key in IDENTITY_FIELDS)


def _positive(value) -> bool:
    return (isinstance(value, Real) and not isinstance(value, bool)
            and math.isfinite(float(value)) and value > 0 and float(value).is_integer())


def _participation(observation: Mapping) -> tuple[str, str]:
    """A missing/zero row does not establish either participation or DNP."""
    stats = observation.get("stats", {})
    snaps = observation.get("snaps", {})
    source_gp = _positive(stats.get("gp")) and stats["gp"] == 1
    positive_snaps = any(_positive(snaps.get(key)) for key in ("offense_snaps", "defense_snaps", "st_snaps"))
    inactive = (observation.get("roster_status") == "INA"
                and observation.get("participation_evidence") == "explicit_weekly_inactive")
    if inactive and (source_gp or positive_snaps):
        return "conflicting", "inactive_and_positive_participation_evidence"
    if source_gp:
        return "played", "explicit_source_gp"
    if positive_snaps:
        return "played", "positive_snap_count"
    if inactive:
        return "DNP", "explicit_weekly_inactive"
    return "unknown", "no_independent_positive_participation_evidence"


def _receipt(receipt: Mapping) -> dict:
    if receipt.get("status") not in {"acquired", "stale_cache"}:
        raise ValueError("PPR source requires an acquired source receipt")
    if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("sha256", ""))):
        raise ValueError("PPR source receipt requires SHA256")
    if not receipt.get("url"):
        raise ValueError("PPR source receipt requires source URL")
    try:
        retrieved = datetime.fromisoformat(receipt["retrieved_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("PPR source receipt requires retrieval clock") from exc
    if retrieved.utcoffset() is None:
        raise ValueError("PPR source retrieval clock must include timezone")
    return dict(receipt)


def qualify_ppr_panel(planned: Sequence[Mapping], observations: Sequence[Mapping], *,
                      source_kind: str, source_receipt: Mapping) -> dict:
    """Qualify an exact, conditional-on-playing label for every planned row.

    ``observations`` contain canonical identity fields, an independently
    sourced ``position``, raw ``stats``, and optional explicit ``snaps``. The
    caller must verify the receipt against the cached bytes and bind any snap
    join through the shared identity registry. The receipt identifies current
    source vintage; its retrieval clock never proves historical availability.

    Missing observations, unknown participation and unsupported component
    credits remain abstentions. No outcome or usage threshold selects rows.
    This function never mutates the planned panel or either raw source.
    """
    adapters = {"nflverse": nflverse_components, "sleeper": sleeper_components}
    if source_kind not in adapters:
        raise ValueError("unsupported PPR source kind")
    receipt = _receipt(source_receipt)
    lookup = {}
    for observed in observations:
        key = _identity(observed)
        if key in lookup:
            raise ValueError("duplicate PPR source identity")
        lookup[key] = observed
    seen, rows = set(), []
    for planned_row in planned:
        key = _identity(planned_row)
        if key in seen:
            raise ValueError("duplicate planned PPR identity")
        seen.add(key)
        observed = lookup.get(key)
        result = {field: planned_row[field] for field in IDENTITY_FIELDS}
        result.update(position=planned_row.get("position"), exact_ppr=None,
                      qualified_exact=False, participation_state="unknown",
                      source_sha256=receipt["sha256"], missing_components=[], invalid_components=[])
        if planned_row.get("position") not in OFFENSIVE_ROLES:
            result["qualification"] = "planned_position_outside_offensive_scope"
        elif observed is None:
            result["qualification"] = "missing_source_observation"
        elif observed.get("position") not in OFFENSIVE_ROLES:
            result["qualification"] = "source_position_unqualified"
        else:
            participation, basis = _participation(observed)
            bundle = adapters[source_kind](observed.get("stats", {}))
            result.update(participation_state=participation, participation_evidence=basis,
                          components=bundle["components"], component_coverage=bundle["coverage"],
                          missing_components=bundle["missing_components"],
                          invalid_components=bundle["invalid_components"])
            if participation == "DNP":
                result["qualification"] = "known_dnp_outside_conditional_population"
            elif participation == "conflicting":
                result["qualification"] = "participation_evidence_conflict"
            elif participation != "played":
                result["qualification"] = "participation_unknown"
            elif bundle["invalid_components"]:
                result["qualification"] = "invalid_components"
            elif not bundle["qualified_exact"]:
                result["qualification"] = "component_contract_incomplete"
            else:
                result.update(qualification="qualified_explicit_components", qualified_exact=True,
                              exact_ppr=bundle["exact_ppr"])
        rows.append(result)
    return {"adapter": ADAPTER_VERSION, "scoring_id": SCORING_VERSION,
            "population": "all_planned_offensive_opportunities_conditional_on_playing",
            "planned_rows": len(rows), "qualified_exact_rows": sum(row["qualified_exact"] for row in rows),
            "qualification_counts": dict(Counter(row["qualification"] for row in rows)),
            "unmatched_source_rows": len(set(lookup) - seen), "rows": rows, "source_receipt": receipt,
            "zero_policy": "only explicit source components; zero snapshots and omitted fields do not prove DNP",
            "availability": "current-vintage reconstruction; no historical publication clock inferred from retrieval",
            "receipt_boundary": "caller verifies source bytes and independent snap/identity provenance before invoking"}
