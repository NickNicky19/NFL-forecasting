"""Source-qualified PPR components without invented sparse zeros.

The NFLverse adapter supplies compatible explicit common components only. Six
rare credit bridges remain unqualified. Event coverage is audited separately;
NFL football events are not silently relabeled as Sleeper IDP/ST credits.
"""
from __future__ import annotations

import json
import math
from numbers import Real
from pathlib import Path

import pandas as pd

from .data import _sha
from .scoring import PPR_COMPONENTS, SCORING_VERSION, SIGNED_COMPONENTS, score_ppr

NFL_FIELDS = {
    "pass_yd": "passing_yards", "pass_td": "passing_tds", "pass_int": "passing_interceptions",
    "pass_2pt": "passing_2pt_conversions", "rush_yd": "rushing_yards", "rush_td": "rushing_tds",
    "rush_2pt": "rushing_2pt_conversions", "rec": "receptions", "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds", "rec_2pt": "receiving_2pt_conversions", "fum_lost": "fumbles_lost_total",
}
RARE_GAPS = {
    "st_td": {"candidates": ["special_teams_tds"], "reason": "Sleeper special-teams player credit equivalence not fully qualified"},
    "st_fum_rec": {"candidates": ["PBP special_teams_play and fumble_recovery_*_player_id"],
                   "reason": "NFL phase/recovery events do not authenticate Sleeper special-teams recovery credit"},
    "st_ff": {"candidates": ["PBP special_teams_play and forced_fumble_player_*_player_id"],
              "reason": "NFL phase/forced-fumble events do not authenticate Sleeper special-teams forced-fumble credit"},
    "fum_rec_td": {"candidates": ["fumble_recovery_tds"],
                   "reason": "recovery TD must be paired with Sleeper idp_fum_rec for the nonlinear exception"},
    "idp_blk_kick": {"candidates": ["def_punt_blocks", "def_fg_blocks", "def_pat_blocks", "PBP blocked_player_id"],
                     "reason": "NFL blocked-kick attributions are not a qualified Sleeper IDP credit crosswalk"},
    "idp_fum_rec": {"candidates": ["fumble_recovery_opp", "PBP recovery teams/players"],
                    "reason": "opponent recovery is not an authenticated Sleeper defensive-credit flag; phase and possession credit unresolved"},
}


def _explicit_value(value, component):
    if value is None or (isinstance(value, Real) and math.isnan(float(value))):
        return None, "missing"
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        return None, "invalid"
    value = float(value)
    if component not in SIGNED_COMPONENTS and (value < 0 or not value.is_integer()):
        return None, "invalid"
    return value, "explicit"


def _bundle(components: dict, coverage: dict, source: str) -> dict:
    scored = score_ppr(components)
    return {"adapter": "ppr-component-coverage-v1", "source": source,
            "components": components, "coverage": coverage,
            "exact_ppr": scored.value, "qualified_exact": scored.value is not None,
            "missing_components": list(scored.missing),
            "invalid_components": [key for key, value in coverage.items() if value["status"] == "invalid"],
            "scoring_id": SCORING_VERSION, "zero_policy": "explicit numeric source values only; omitted/null fields remain unknown"}


def nflverse_components(stats: dict) -> dict:
    """Read twelve compatible explicit NFL components; retain six rare gaps.

    Fumbles use the modern all-phase ``fumbles_lost_total`` field. The old
    sack/rush/receiving sum can omit special-teams fumbles and is not substituted.
    Generic provider fantasy totals never become an exact pinned score.
    """
    values, coverage = {}, {}
    for component in PPR_COMPONENTS:
        source_field = NFL_FIELDS.get(component)
        if source_field is None:
            values[component] = None
            coverage[component] = {"status": "unqualified_credit_bridge", **RARE_GAPS[component]}
        else:
            values[component], status = _explicit_value(stats.get(source_field), component)
            coverage[component] = {"status": status, "source_field": source_field}
    return _bundle(values, coverage, "nflverse-stats-player-week")


def sleeper_components(stats: dict) -> dict:
    """Accept only explicit observed components; no inferred API sparse zeros."""
    values, coverage = {}, {}
    for component in PPR_COMPONENTS:
        values[component], status = _explicit_value(stats.get(component), component)
        coverage[component] = {"status": status, "source_field": component}
    return _bundle(values, coverage, "sleeper-explicit-components")


def _component_counts(records: list[dict], adapter) -> dict:
    counts = {k: {"explicit": 0, "explicit_zero": 0, "explicit_nonzero": 0,
                  "missing": 0, "invalid": 0, "unqualified_credit_bridge": 0} for k in PPR_COMPONENTS}
    exact = 0
    for record in records:
        result = adapter(record)
        exact += result["qualified_exact"]
        for component in PPR_COMPONENTS:
            status = result["coverage"][component]["status"]
            counts[component][status] += 1
            if status == "explicit":
                counts[component]["explicit_zero" if result["components"][component] == 0 else "explicit_nonzero"] += 1
    return {"rows": len(records), "all18_explicit_qualified_rows": exact, "components": counts}


def audit_pbp_event_coverage(pbp: pd.DataFrame) -> dict:
    """Describe NFL event coverage without asserting a Sleeper credit bridge."""
    required = {"game_id", "play_id", "play_type", "play_deleted", "special_teams_play", "fumble", "fumble_lost",
                "fumble_forced", "fumble_out_of_bounds", "fumble_recovery_1_player_id", "fumble_recovery_2_player_id",
                "forced_fumble_player_1_player_id", "forced_fumble_player_2_player_id", "blocked_player_id",
                "punt_blocked", "field_goal_result", "extra_point_result"}
    if required - set(pbp):
        raise ValueError(f"PBP event schema missing {sorted(required - set(pbp))}")
    if pbp.duplicated(["game_id", "play_id"]).any():
        raise ValueError("duplicate PBP game/play identity")
    eligible = pbp.play_type.notna() & pbp.play_type.ne("no_play") & pbp.play_deleted.eq(0)
    plays = pbp[eligible]
    st = plays.special_teams_play.eq(1)
    blocked = plays.punt_blocked.eq(1) | plays.field_goal_result.eq("blocked") | plays.extra_point_result.eq("blocked")
    lost_without_recoverer = plays.fumble_lost.eq(1) & plays.fumble_recovery_1_player_id.isna()
    flags = ["fumble", "fumble_lost", "fumble_forced", "punt_blocked", "special_teams_play"]
    return {"rows": len(pbp), "games": int(pbp.game_id.nunique()), "nondeleted_nonnullified_rows": len(plays),
            "excluded_administrative_nullified_or_deleted_rows": int((~eligible).sum()),
            "unknown_deletion_status_rows": int(pbp.play_deleted.isna().sum()),
            "missing_flags_on_eligible_rows": {k: int(plays[k].isna().sum()) for k in flags},
            "fumble_plays": int(plays.fumble.eq(1).sum()), "special_teams_fumble_plays": int((st & plays.fumble.eq(1)).sum()),
            "special_teams_forced_fumble_plays": int((st & plays.fumble_forced.eq(1)).sum()),
            "special_teams_forced_fumble_missing_primary_id": int((st & plays.fumble_forced.eq(1) & plays.forced_fumble_player_1_player_id.isna()).sum()),
            "blocked_kick_plays": int(blocked.sum()), "blocked_kicks_missing_player_id": int((blocked & plays.blocked_player_id.isna()).sum()),
            "lost_fumbles_without_recoverer": int(lost_without_recoverer.sum()),
            "lost_fumbles_without_recoverer_out_of_bounds": int((lost_without_recoverer & plays.fumble_out_of_bounds.eq(1)).sum()),
            "source_credit_bridge": "NFL event evidence only; no inferred Sleeper special-teams/IDP credits or sparse zeros",
            "completeness_limit": "a schema and game/play uniqueness check is not independent proof of full authoritative game coverage or provider equivalence"}


def _verified_receipt(path: Path) -> dict:
    metadata = path.with_name(path.name + ".receipt.json")
    if not path.exists() or not metadata.exists():
        raise ValueError(f"cached source/receipt missing: {path.name}")
    receipt = json.loads(metadata.read_text())
    if receipt.get("status") not in ("acquired", "stale_cache") or receipt.get("sha256") != _sha(path):
        raise ValueError(f"cached source integrity failure: {path.name}")
    return receipt


def audit_cached_coverage(cache: Path, *, weekly_season: int = 2023,
                          sleeper_relative: str = "live/2026-10-22/archive-stats-2026-6.json",
                          pbp_season: int = 2023) -> dict:
    """Offline source coverage only; no fits, forecasts, grades or state writes."""
    raw = Path(cache) / "raw"
    weekly_path = raw / f"stats_player_week_{int(weekly_season)}.parquet"
    sleeper_path = raw / sleeper_relative
    if not sleeper_path.resolve().is_relative_to(raw.resolve()):
        raise ValueError("Sleeper audit must use an existing local raw cache path")
    pbp_path = raw / f"play_by_play_{int(pbp_season)}.parquet"
    sources = {p.name: _verified_receipt(p) for p in [weekly_path, sleeper_path, pbp_path]}
    weekly = pd.read_parquet(weekly_path)
    required = {"season", "week", "player_id", "position", *NFL_FIELDS.values()}
    if required - set(weekly):
        raise ValueError(f"NFLverse component schema missing {sorted(required - set(weekly))}")
    if not weekly.season.eq(weekly_season).all():
        raise ValueError("NFLverse cached season mismatch")
    weekly = weekly[weekly.position.isin(["QB", "RB", "FB", "WR", "TE"])]
    payload = json.loads(sleeper_path.read_text())
    entries = payload if isinstance(payload, list) else list(payload.values())
    played = [e.get("stats", {}) for e in entries if (e.get("player") or {}).get("position") in {"QB", "RB", "FB", "WR", "TE"}
              and (e.get("stats", {}).get("gp") == 1 or e.get("stats", {}).get("off_snp", 0) > 0)]
    pbp = pd.read_parquet(pbp_path)
    if "season" in pbp and not pbp.season.eq(pbp_season).all():
        raise ValueError("PBP cached season mismatch")
    return {"adapter": "ppr-component-coverage-v1", "scoring_id": SCORING_VERSION,
            "scope": "source coverage/correctness audit only; no predictive gains, source-zero contract or exact PPR qualification inferred",
            "nflverse_season": weekly_season, "pbp_season": pbp_season,
            "nflverse": _component_counts(weekly.to_dict("records"), nflverse_components),
            "sleeper_played_skill": _component_counts(played, sleeper_components),
            "pbp_events": audit_pbp_event_coverage(pbp), "rare_credit_gaps": RARE_GAPS,
            "sources": sources,
            "vintage": "current-vintage historical reconstruction; authentic original publication/revision clocks unknown",
            "rights": "public permitted acquisition; upstream rights retained; raw and row-level data remain ignored, no redistribution"}
