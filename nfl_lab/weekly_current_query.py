"""Exact weekly roster offers for the existing permitted future-feature builder.

This module reads no files and performs no acquisition, model fitting or writes.
Current roster membership is not playing/DNP evidence. Conflicts are retained
as quarantined rows, never resolved from names, target values or row order.
"""
from __future__ import annotations

import math
from numbers import Integral, Real
import re

import pandas as pd

from . import data

VERSION = "weekly-current-query-v1"
ROSTER_COLUMNS = ["season", "week", "game_type", "team", "gsis_id", "position", "status", "full_name", "sleeper_id"]
SCHEDULE_COLUMNS = ["game_id", "season", "week", "game_type", "gameday", "gametime", "away_team", "home_team"]


def _stamp(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("explicit timezone-aware query cutoff required")
    return stamp.tz_convert("UTC")


def _sleeper(value):
    if isinstance(value, str):
        return value if re.fullmatch(r"[1-9][0-9]*", value) else None
    if isinstance(value, Integral) and not isinstance(value, bool) and value > 0:
        return str(int(value))
    # Some original parquet schemas represent nullable IDs as binary64. Admit
    # only exactly represented integers, without rounding or name-based repair.
    if isinstance(value, Real) and not isinstance(value, bool):
        if math.isfinite(value) and 0 < value < 2**53 and int(value) == value:
            return str(int(value))
    return None


def _gsis(value):
    return value if isinstance(value, str) and re.fullmatch(r"[0-9]{2}-[0-9]{7}", value) else None


def build_current_queries(roster, schedule, *, season, week, cutoff_utc,
                          maximum_rows=1000, expected_remaining_games=None):
    """One deterministic offer universe; no current outcomes are projected."""
    cutoff = _stamp(cutoff_utc)
    if not 1 <= maximum_rows <= 1000 or not 1 <= int(week) <= 18:
        raise ValueError("finite query/REG week bounds required")
    if (not roster.columns.is_unique or not schedule.columns.is_unique
            or not set(ROSTER_COLUMNS) <= set(roster) or not set(SCHEDULE_COLUMNS) <= set(schedule)):
        raise ValueError("exact roster/schedule metadata schema required")
    # Project before inspecting/copying any optional statistic/outcome columns.
    members = roster.loc[:, ROSTER_COLUMNS]
    members = members.loc[members.season.eq(season) & members.week.eq(week) & members.game_type.eq("REG")
        & members.position.isin(data.POSITIONS)].copy().reset_index(drop=True)
    members["roster_row_ordinal"] = range(len(members))
    games = schedule.loc[:, SCHEDULE_COLUMNS]
    games = games.loc[games.season.eq(season) & games.week.eq(week) & games.game_type.eq("REG")].copy()
    if games.empty or games.game_id.isna().any() or games.duplicated("game_id").any():
        raise ValueError("unambiguous schedule game identities required")
    for column in ("home_team", "away_team"):
        games[column] = data._team(games[column])
        if not games[column].map(lambda value: isinstance(value, str) and bool(value)).all():
            raise ValueError("exact schedule team identities required")
    if games.home_team.eq(games.away_team).any():
        raise ValueError("opposing teams must be distinct")
    local = pd.to_datetime(games.gameday.astype("string") + " " + games.gametime.astype("string"), errors="coerce")
    games["kickoff_utc"] = local.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    if games.kickoff_utc.isna().any():
        raise ValueError("unambiguous scheduled kickoff required")
    remaining = games.loc[games.kickoff_utc.gt(cutoff)].copy()
    if expected_remaining_games is not None and len(remaining) != expected_remaining_games:
        raise ValueError("remaining schedule differs from frozen proposed slate")
    sides = []
    for own, other in (("home_team", "away_team"), ("away_team", "home_team")):
        side = remaining[["game_id", "kickoff_utc", own, other]].rename(columns={own: "team", other: "opponent"})
        sides.append(side)
    team_games = pd.concat(sides, ignore_index=True)
    if team_games.duplicated("team").any():
        raise ValueError("one remaining game per exact team required")

    members["player_id"] = members.gsis_id.map(_gsis)
    members["sleeper_id"] = members.sleeper_id.map(_sleeper)
    members["team"] = data._team(members.team)
    reasons = [[] for _ in range(len(members))]
    predicates = {
        "missing_or_invalid_gsis": members.player_id.isna(),
        "missing_or_invalid_sleeper": members.sleeper_id.isna(),
        "missing_or_invalid_team": ~members.team.map(lambda value: isinstance(value, str) and bool(value)),
        "duplicate_gsis_or_trade_conflict": members.player_id.notna() & members.player_id.duplicated(keep=False),
        "duplicate_or_conflicting_sleeper": members.sleeper_id.notna() & members.sleeper_id.duplicated(keep=False),
    }
    for reason, predicate in predicates.items():
        for index in members.index[predicate]:
            reasons[index].append(reason)
    members["quarantine_reason"] = ["|".join(value) for value in reasons]
    quarantined = members.loc[members.quarantine_reason.ne("")].copy()
    eligible = members.loc[members.quarantine_reason.eq("")].copy()
    offered = eligible.merge(team_games, on="team", how="inner", validate="many_to_one")
    not_remaining = eligible.loc[~eligible.team.isin(team_games.team)].copy()
    offered = offered.rename(columns={"full_name": "player_name", "status": "roster_status"})
    offered = offered.drop(columns=["gsis_id", "game_type", "quarantine_reason"])
    offered["cutoff_utc"] = cutoff
    offered["participation_state"] = "unknown"
    offered["participation_probability_state"] = "unavailable_incomplete_nonappearance_denominator"
    offered["identity_status"] = "source_exact_weekly_gsis_sleeper_team_game_binding"
    offered = offered.sort_values(["game_id", "team", "position", "player_id", "sleeper_id"], kind="stable").reset_index(drop=True)
    if len(offered) > maximum_rows:
        raise ValueError("finite current-query row cap exceeded; never truncate the universe")
    if offered.duplicated(["game_id", "player_id"]).any() or offered.sleeper_id.duplicated().any():
        raise ValueError("offer identity is not unique")
    offered["query_ordinal"] = range(len(offered))
    coverage = dict(schema_version=VERSION, season=int(season), week=int(week), input_cutoff_utc=cutoff.isoformat(),
        schedule_games=len(games), remaining_games=len(remaining), elapsed_games=int(games.kickoff_utc.le(cutoff).sum()),
        retained_weekly_skill_rows=len(members), offered_rows=len(offered), quarantined_rows=len(quarantined),
        no_remaining_game_rows=len(not_remaining), quarantine_reason_counts={name: int(mask.sum()) for name, mask in predicates.items()},
        query_participation="unknown regardless of roster ACT/INA/other status", upstream_publication="NOT_INFERRED",
        evidence_lane="current_vintage_availability_uncertain", retroactive_issuance=False)
    if len(members) != len(offered) + len(quarantined) + len(not_remaining):
        raise ValueError("current-query population accounting differs")
    return dict(queries=offered, quarantine=quarantined, no_remaining_game=not_remaining, coverage=coverage)


def build_shared_features(history, packet, *, policy, source_contract, builder=None):
    """Exactly one existing feature build, reused by every trained model."""
    if builder is None:
        from .weekly_future_inference import build_future_features
        builder = build_future_features
    queries = packet["queries"]
    result = builder(history, queries, policy=policy, source_contract=source_contract)
    if (len(result) != len(queries) or result[["game_id", "player_id"]].reset_index(drop=True).to_dict("records")
            != queries[["game_id", "player_id"]].reset_index(drop=True).to_dict("records")):
        raise ValueError("shared feature build changed the offered identity/order")
    if not result.participation_state.eq("unknown").all():
        raise ValueError("query participation must remain unknown")
    return result
