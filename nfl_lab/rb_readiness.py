"""Offline prerequisite audit for the original, zero-inclusive 2023 RB pilot.

This is source qualification, not a model or a revised participant definition.
Positive snaps may confirm playing; they never fill an absent carry count.
Only aggregate evidence is returned, so private player rows stay in the cache.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .data import _sha

AUDIT_VERSION = "original-rb-2023-gate-v1"
ORIGINAL_FEATURES_SHA256 = "ff7a14bac024958f32cbf367e83f6d70e4f86572f461ca6ebd33a9207d04d297"
ORIGINAL_STATS_SHA256 = "ac776fbd7c9fefdb4069b72304f4c5fa05ae417acd49f6e4e27be14b9d7a4bbc"
# Physical-action counts, excluding penalty-only evidence and mere row presence.
ACTION_FIELDS = (
    "carries", "attempts", "targets", "receptions", "sacks_suffered",
    "passing_2pt_conversions", "rushing_2pt_conversions", "receiving_2pt_conversions",
    "special_teams_tds", "def_tackles_solo", "def_tackles_with_assist",
    "def_tackle_assists", "def_tackles_for_loss", "def_fumbles_forced", "def_sacks",
    "def_qb_hits", "def_interceptions", "def_pass_defended", "def_tds", "def_fumbles",
    "def_safeties", "def_punt_blocks", "def_pat_blocks", "def_fg_blocks",
    "def_2pt_atts", "def_2pt_made", "fumble_recovery_own", "fumble_recovery_opp",
    "fumble_recovery_tds", "fumbles_total", "punt_returns", "kickoff_returns",
    "fg_att", "pat_att", "pt_att",
)
SNAP_FIELDS = ("offense_snaps", "defense_snaps", "st_snaps")


def classify_evidence(panel: pd.DataFrame) -> pd.DataFrame:
    """Retain the roster denominator and distinguish all carry/playing states."""
    if not {"carries", *ACTION_FIELDS, *SNAP_FIELDS}.issubset(panel):
        raise ValueError("original RB evidence schema incomplete")
    result = panel.copy()
    result["action_supported"] = panel[list(ACTION_FIELDS)].gt(0).any(axis=1)
    result["snap_supported"] = panel[list(SNAP_FIELDS)].gt(0).any(axis=1)
    result["played_supported"] = result.action_supported | result.snap_supported
    carries = panel.carries
    valid = carries.notna() & carries.ge(0) & carries.mod(1).eq(0)
    result["carry_state"] = "unknown"
    result.loc[valid & carries.eq(0), "carry_state"] = "explicit_zero"
    result.loc[valid & carries.gt(0), "carry_state"] = "explicit_positive"
    result.loc[carries.notna() & ~valid, "carry_state"] = "invalid"
    return result


def _counts(panel: pd.DataFrame) -> dict:
    played = panel.played_supported
    return {
        "roster_game_listings": len(panel), "unique_players": int(panel.gsis_id.nunique()),
        "action_supported_appearances": int(panel.action_supported.sum()),
        "positive_snap_appearances": int(panel.snap_supported.sum()),
        "supported_appearances": int(played.sum()),
        "supported_positive_carries": int((played & panel.carry_state.eq("explicit_positive")).sum()),
        "supported_played_zero": int((played & panel.carry_state.eq("explicit_zero")).sum()),
        "played_carries_unknown": int((played & panel.carry_state.eq("unknown")).sum()),
        "participation_unknown": int((~played).sum()),
        "explicit_zero_participation_unknown": int((~played & panel.carry_state.eq("explicit_zero")).sum()),
        "absent_stat_row": int(panel.stats_join.eq("left_only").sum()),
        "invalid_carries": int(panel.carry_state.eq("invalid").sum()),
        "roster_status_counts": {str(k): int(v) for k, v in panel.status.value_counts().items()},
    }


def audit_original_rb_gate(cache: Path) -> dict:
    """Reproduce the original frame from verified, existing files; never fetch."""
    cache = Path(cache)
    raw = cache / "raw"
    names = ["stats_player_week_2023.parquet", "roster_weekly_2023.parquet",
             "snap_counts_2023.parquet", "players.parquet", "schedules.csv"]
    sources = {}
    for name in names:
        path = raw / name
        receipt = json.loads(path.with_name(name + ".receipt.json").read_text())
        if receipt.get("sha256") != _sha(path) or receipt.get("status") not in {"acquired", "stale_cache"}:
            raise ValueError(f"cached source integrity failure: {name}")
        sources[name] = receipt
    if sources[names[0]]["sha256"] != ORIGINAL_STATS_SHA256:
        raise ValueError("2023 statistics differ from original protocol artifact")
    roster = pd.read_parquet(raw / names[1])
    roster = roster[roster.game_type.eq("REG") & roster.depth_chart_position.eq("RB")]
    stats = pd.read_parquet(raw / names[0])
    stats = stats[stats.season_type.eq("REG")].rename(columns={"player_id": "gsis_id", "opponent_team": "stats_opponent"})
    schedule = pd.read_csv(raw / "schedules.csv")
    schedule = schedule[schedule.season.eq(2023) & schedule.game_type.eq("REG")]
    team_games = pd.concat([
        schedule.assign(team=schedule.home_team, opponent=schedule.away_team),
        schedule.assign(team=schedule.away_team, opponent=schedule.home_team),
    ])[['season', 'week', 'game_id', 'team', 'opponent']]
    panel = roster.merge(team_games, on=["season", "week", "team"], validate="many_to_one")
    panel = panel.merge(stats, on=["season", "week", "game_id", "team", "gsis_id"],
                        how="left", indicator="stats_join", suffixes=("", "_stat"), validate="one_to_one")
    snaps = pd.read_parquet(raw / names[2])
    snaps = snaps[snaps.game_type.eq("REG") & snaps.pfr_player_id.notna()].rename(columns={"pfr_player_id": "pfr_id"})
    # Missing IDs must never match one another. Historical roster IDs control;
    # the current player registry never supplies a historical position label.
    panel = panel.merge(snaps[["game_id", "team", "pfr_id", *SNAP_FIELDS]],
                        on=["game_id", "team", "pfr_id"], how="left", validate="many_to_one")
    panel = classify_evidence(panel)
    feature_path = cache / "processed" / "features.parquet"
    if _sha(feature_path) != ORIGINAL_FEATURES_SHA256:
        raise ValueError("original normalized features hash mismatch; mutated history is not substituted")
    features = pd.read_parquet(feature_path)
    normalized = features[features.season.eq(2023) & features.position.eq("RB")]
    return {
        "audit": AUDIT_VERSION, "gate": "NOT_READY", "models_or_scores_run": False,
        "original_historical_role": "weekly depth_chart_position == RB; REG2023",
        "games": len(schedule), "team_games": len(team_games),
        "all_fine_rb": _counts(panel), "active_fine_rb": _counts(panel[panel.status.eq("ACT")]),
        "new_snap_supported_appearances": int((panel.snap_supported & ~panel.action_supported).sum()),
        "stats_opponent_conflicts": int((panel.stats_opponent.notna() & panel.stats_opponent.ne(panel.opponent)).sum()),
        "confirmed_game_specific_dnp": 0,
        "dnp_basis": "weekly INA remains roster status; no complete game-specific all-phase appearance/DNP contract",
        "full_participant_population_supported": False,
        "absent_carry_zero_convention_supported": False,
        "missing_prerequisite": "complete permitted all-phase appearance/nonappearance ledger plus official carry-zero contract for absent stat rows",
        "2017_2018_expansion": "not acquired; original five-prior-year study remains blocked at2023gate",
        "original_normalized_comparison": {
            "sha256": ORIGINAL_FEATURES_SHA256, "broader_rb_rows": len(normalized),
            "participation_states": {str(k): int(v) for k, v in normalized.participation_state.value_counts().items()},
            "played_missing_carries": int((normalized.participation_state.eq("played") & normalized.rush_att.isna()).sum()),
            "certifies_original_gate": False,
        },
        "sources": sources,
        "rights": "existing cached PFRsnap audit only; unresolved upstream AI/ML permission is not training clearance; no raw redistribution",
        "clocks": "current-vintage reconstruction; original publication/local historical availability unknown",
    }
