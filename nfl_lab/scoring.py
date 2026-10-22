"""Pinned offensive Sleeper PPR arithmetic with explicit missing outcomes.

Weights and the defensive-fumble exception reproduce the pinned website. Unlike
its presentation helper, an absent component is never interpreted as zero.
Only a source adapter with an established sparse-zero convention may add zeros.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from numbers import Real
from typing import Any, Mapping

SCORING_VERSION = "pinned-site-offensive-ppr-31672c10-v1"
PINNED_SCORING_SHA256 = "31672c10d526d591db8951157b0ecd669b4d02b412a75deec337618bff18dab2"
PPR = {
    "pass_yd": .04, "pass_td": 4, "pass_int": -1, "pass_2pt": 2,
    "rush_yd": .1, "rush_td": 6, "rush_2pt": 2,
    "rec": 1, "rec_yd": .1, "rec_td": 6, "rec_2pt": 2,
    "fum_lost": -2, "st_td": 6, "st_fum_rec": 1, "st_ff": 1,
    "fum_rec_td": 6, "idp_blk_kick": 2,
}
PPR_COMPONENTS = tuple(PPR) + ("idp_fum_rec",)
SIGNED_COMPONENTS = frozenset({"pass_yd", "rush_yd", "rec_yd"})


@dataclass(frozen=True)
class ScoringResult:
    value: float | None
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()
    version: str = SCORING_VERSION


def _valid_number(value: Any, *, signed: bool = False) -> bool:
    try:
        return (not isinstance(value, bool) and isinstance(value, (Real, Decimal))
                and math.isfinite(float(value)) and (signed or value >= 0))
    except (ValueError, TypeError, OverflowError):
        return False


def score_ppr(stats: Mapping[str, Any]) -> ScoringResult:
    """Return the exact pinned score, or its missing/invalid component names.

    All components, including known zero rare events and ``idp_fum_rec``, must
    be explicit. Fractional forecasts and signed yardage are supported. Generic
    ``fantasy_points_ppr``/``pts_ppr`` provider totals are never substituted.
    """
    missing = tuple(k for k in PPR_COMPONENTS if stats.get(k) is None)
    invalid = tuple(k for k in PPR_COMPONENTS if stats.get(k) is not None
                    and not _valid_number(stats[k], signed=k in SIGNED_COMPONENTS))
    if missing or invalid:
        return ScoringResult(None, missing, invalid)
    total = sum(weight * float(stats[key]) for key, weight in PPR.items())
    if stats["idp_fum_rec"]:
        total -= PPR["fum_rec_td"] * float(stats["fum_rec_td"])
    if not math.isfinite(total):
        return ScoringResult(None, invalid=("nonfinite_total",))
    return ScoringResult(round(total, 2))


def ppr_points(stats: Mapping[str, Any]) -> float | None:
    return score_ppr(stats).value


def rushing_receiving_td_count(stats: Mapping[str, Any]) -> float | None:
    values = [stats.get("rush_td"), stats.get("rec_td")]
    if not all(_valid_number(value) for value in values):
        return None
    return sum(float(value) for value in values)


def anytime_td_outcome(stats: Mapping[str, Any], *, participation: str = "played",
                       population: str = "conditional_on_playing") -> int | None:
    """At least one rushing/receiving TD; passing/return TDs are excluded.

    DNP is a known zero only for the declared all-player population. It remains
    outside a conditional-on-playing outcome/settlement population. Unknown
    participation is never inferred from missing box scores. A known positive
    component establishes the event even if the other component is missing.
    """
    if population not in {"conditional_on_playing", "all_player"}:
        raise ValueError("unknown_population")
    if participation.lower() == "dnp":
        return 0 if population == "all_player" else None
    if participation != "played":
        return None
    values = [stats.get("rush_td"), stats.get("rec_td")]
    if any(value is not None and (not _valid_number(value) or not float(value).is_integer())
           for value in values):
        return None
    if any(_valid_number(value) and value > 0 for value in values):
        return 1
    return 0 if all(_valid_number(value) for value in values) else None


def anytime_td_probability(rush_td_mean: float, rec_td_mean: float, *,
                           p_participation: float = 1.,
                           population: str = "conditional_on_playing") -> float:
    """A new Poisson control, with conditional and all-player scopes explicit."""
    if not all(_valid_number(x) for x in (rush_td_mean, rec_td_mean)):
        raise ValueError("invalid_td_mean")
    if not _valid_number(p_participation) or p_participation > 1:
        raise ValueError("invalid_participation_probability")
    conditional = -math.expm1(-(float(rush_td_mean) + float(rec_td_mean)))
    if population == "conditional_on_playing":
        return conditional
    if population == "all_player":
        return float(p_participation) * conditional
    raise ValueError("unknown_population")


def stat_value(key: str, stats: Mapping[str, Any]) -> float | None:
    if key in {"fantasy_ppr", "fpts"}:
        return ppr_points(stats)
    if key == "anytime_td":
        return anytime_td_outcome(stats)
    if key == "rush_rec_yd":
        values = [stats.get("rush_yd"), stats.get("rec_yd")]
        return sum(float(x) for x in values) if all(_valid_number(x, signed=True) for x in values) else None
    value = stats.get(key)
    return float(value) if _valid_number(value, signed=key in SIGNED_COMPONENTS) else None
