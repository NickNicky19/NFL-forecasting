"""Offline, exactly bound NFLverse supplementation for completed saved games.

This module returns candidate observations; it never writes forecast/outcome
state, fetches sources, chooses between conflicting providers or infers zeros.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .data import TARGETS, VINTAGE, _sha, _utc_now, load_history, load_identity

GSIS = re.compile(r"^00-\d{7}$")
COUNTS = {"pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec", "anytime_td"}


def _clock(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("grading clocks require an explicit timezone")
    return stamp.tz_convert("UTC")


def _build_grading_lookups(context: dict) -> dict:
    """Index immutable context identities once; values retain source row positions."""
    history, identity = context["history"], context["identity"]
    schedule, players, sleepers = {}, {}, {}
    columns = ["season", "week", "team", "opponent", "player_id", "game_id"]
    clocks = pd.to_datetime(history.kickoff_utc, utc=True).astype("int64").to_numpy()
    for position, row in enumerate(history[columns].itertuples(index=False, name=None)):
        season, week, team, opponent, pid, game_id = row
        key = (season, week, team, opponent, int(clocks[position]))
        if pd.notna(game_id):
            schedule.setdefault(key, set()).add(game_id)
        player_key = key + (pid,)
        players[player_key] = position if player_key not in players else None
    for position, sid in enumerate(identity.sleeper_id):
        if pd.notna(sid):
            sleepers.setdefault(str(sid), []).append(position)
    return {"schedule": schedule, "players": players, "sleepers": sleepers,
            "signature": (id(history), history.shape, id(identity), identity.shape)}


def _grading_lookups(context: dict, use_cache: bool) -> dict:
    signature = (id(context["history"]), context["history"].shape,
                 id(context["identity"]), context["identity"].shape)
    cached = context.get("_grading_lookups")
    if not use_cache or cached is None or cached["signature"] != signature:
        cached = _build_grading_lookups(context)
        if use_cache:
            context["_grading_lookups"] = cached
    return cached


def load_cached_grading_context(cache: Path, seasons: list[int]) -> dict:
    """Verify cached bytes, then use the existing offline shared loaders.

    The shared history loader may materialize ignored processed history, but no
    official grading state is written and no network call is made.
    """
    cache = Path(cache)
    raw = cache / "raw"
    seasons = sorted(set(int(s) for s in seasons))
    if not seasons:
        raise ValueError("completed forecast seasons are required")
    names = {"schedules.csv", "players.parquet"}
    for season in seasons:
        modern = f"stats_player_week_{season}.parquet"
        names.add(modern if (raw / modern).exists() else f"player_stats_{season}.parquet")
        names.add(f"roster_weekly_{season}.parquet")
        if (raw / f"snap_counts_{season}.parquet").exists():
            names.add(f"snap_counts_{season}.parquet")
    # load_identity uses every cached weekly crosswalk, so verify all of them.
    names.update(p.name for p in raw.glob("roster_weekly_*.parquet"))
    receipts = {}
    for name in sorted(names):
        path = raw / name
        metadata = raw / (name + ".receipt.json")
        if not path.exists() or not metadata.exists():
            raise ValueError(f"missing cached grading source/receipt: {name}")
        receipt = json.loads(metadata.read_text())
        if receipt.get("status") not in ("acquired", "stale_cache") or receipt.get("sha256") != _sha(path):
            raise ValueError(f"cached grading source integrity failure: {name}")
        _clock(receipt.get("retrieved_utc"))
        receipts[name] = receipt
    history = load_history(cache, seasons)
    identity = load_identity(cache)
    context = {"history": history, "identity": identity, "receipts": receipts,
               "seasons": seasons, "verified_utc": _utc_now(), "vintage": VINTAGE}
    _grading_lookups(context, True)
    return context


def cached_nflverse_outcome(context: dict, forecast: dict, completed_game: dict,
                           status_receipt: dict | None = None, *, use_lookup_cache: bool = True) -> dict:
    """Return a supplemental value only with exact identity and final-game binding.

    ``completed_game`` uses the caller/provider game ID, kickoff, home/away and
    an independent boolean ``final`` (or ``completed``). Its ID must equal the
    frozen forecast's ID; NFLverse canonical ID is found by the exact schedule
    tuple rather than by substituting one provider ID for another.
    """
    result = {"player_id": forecast.get("player_id"), "game_id": forecast.get("game_id"),
              "target": forecast.get("target"), "actual": None, "participation_state": "unknown",
              "source": "nflverse-cached-player-stats", "source_timestamp": None,
              "status_sha256": (status_receipt or {}).get("sha256"),
              "source_vintage": VINTAGE, "correction_order": "unknown_provider_publication_order; conflicting values require quarantine",
              "finality": "independent caller completed flag; provider final-publication clock unverified"}
    def gap(reason):
        return {**result, "supplement_status": "unsupported", "gap_reason": reason}
    try:
        kickoff = _clock(forecast["kickoff_utc"])
        provider_kickoff = _clock(completed_game["kickoff_utc"])
        now = _clock(context.get("verified_utc", _utc_now()))
    except (KeyError, TypeError, ValueError):
        return gap("invalid_kickoff_or_grading_clock")
    if completed_game.get("final", completed_game.get("completed")) is not True:
        return gap("independent_completed_flag_required")
    if completed_game.get("game_id") != forecast.get("game_id"):
        return gap("completed_provider_game_id_mismatch")
    if kickoff != provider_kickoff or kickoff >= now:
        return gap("kickoff_mismatch_or_not_completed_before_grading_clock")
    if {completed_game.get("home"), completed_game.get("away")} != {forecast.get("team"), forecast.get("opponent")}:
        return gap("completed_schedule_team_mismatch")
    for period_key in ("season", "week"):
        if period_key in completed_game and completed_game[period_key] != forecast.get(period_key):
            return gap("completed_schedule_period_mismatch")
    target = forecast.get("target")
    if target not in TARGETS:
        return gap("unsupported_target")
    lookups = _grading_lookups(context, use_lookup_cache)
    pid = forecast.get("player_id")
    binding = "frozen_exact_gsis"
    if forecast.get("identity_binding")=="conflicting_identity_cold_start":
        return gap("conflicting_frozen_provider_identity")
    if isinstance(pid,str) and GSIS.fullmatch(pid) and forecast.get("sleeper_id") is not None:
        sid=str(forecast["sleeper_id"])
        candidates=context["identity"].iloc[lookups["sleepers"].get(sid,[])]
        exact=candidates[candidates.sleeper_id.astype("string").eq(sid) & candidates.identity_status.eq("source_exact_binding")]
        if len(exact)>1 or (len(exact)==1 and exact.iloc[0].player_id!=pid):
            return gap("conflicting_frozen_gsis_sleeper_binding")
    if isinstance(pid, str) and pid.startswith("sleeper:"):
        sid = pid.split(":", 1)[1]
        if not sid or (forecast.get("sleeper_id") is not None and str(forecast["sleeper_id"]) != sid):
            return gap("conflicting_frozen_sleeper_identity")
        identity = context["identity"]
        positions = lookups["sleepers"].get(sid, [])
        candidates = identity.iloc[positions]
        matches = candidates[candidates.sleeper_id.astype("string").eq(sid) & candidates.identity_status.eq("source_exact_binding")]
        if len(matches) != 1:
            return gap("missing_or_ambiguous_authenticated_sleeper_gsis_binding")
        pid = matches.iloc[0].player_id
        binding = "verified_nflverse_exact_sleeper_gsis_crosswalk"
    if not isinstance(pid, str) or not GSIS.fullmatch(pid):
        return gap("invalid_canonical_gsis")
    history = context["history"]
    try:
        season, week = int(forecast["season"]), int(forecast["week"])
    except (KeyError, TypeError, ValueError):
        return gap("missing_period")
    schedule_key = (season, week, forecast.get("team"), forecast.get("opponent"), kickoff.value)
    game_ids = lookups["schedule"].get(schedule_key, set())
    if len(game_ids) != 1:
        return gap("missing_or_ambiguous_exact_nflverse_schedule_tuple")
    position = lookups["players"].get(schedule_key + (pid,))
    if position is None:
        return gap("missing_or_ambiguous_player_game")
    row = history.iloc[position]
    # Context source identities are immutable; callers replacing frames/adding
    # rows rebuild automatically. Recheck selected source identities as well.
    if (row.season, row.week, row.team, row.opponent, _clock(row.kickoff_utc).value, row.player_id) != schedule_key + (pid,) or row.game_id not in game_ids:
        return gap("cached_source_identity_changed; rebuild_context")
    if pd.notna(row.get("is_home")):
        expected_home = row.team if bool(row.is_home) else row.opponent
        expected_away = row.opponent if bool(row.is_home) else row.team
        if completed_game.get("home") != expected_home or completed_game.get("away") != expected_away:
            return gap("completed_home_away_binding_mismatch")
    result.update({"canonical_game_id": str(next(iter(game_ids))), "canonical_player_id": pid,
                   "identity_binding": binding, "participation_state": row.participation_state,
                   "participation_evidence": row.get("participation_evidence"),
                   "schedule_binding": {"season": season, "week": week, "team": forecast["team"],
                                        "opponent": forecast["opponent"], "kickoff_utc": kickoff.isoformat()}})
    name = f"stats_player_week_{season}.parquet"
    if name not in context["receipts"]:
        name = f"player_stats_{season}.parquet"
    receipt = context["receipts"].get(name)
    if not receipt:
        return gap("statistics_receipt_missing")
    observed = _clock(receipt["retrieved_utc"])
    if observed <= kickoff or observed > now:
        return gap("statistics_snapshot_before_kickoff_or_after_grading_clock")
    result.update({"source_sha256": receipt["sha256"], "observed_at": receipt["retrieved_utc"],
                   "source_stale": bool(receipt.get("stale")), "source_refresh_error": receipt.get("refresh_error"),
                   "source_receipts": {name: {k: r.get(k) for k in ("sha256", "retrieved_utc", "status")}
                                       for name, r in context["receipts"].items()}})
    if row.participation_state != "played":
        return gap("known_DNP_without_imputed_outcome" if row.participation_state == "DNP" else "participation_unknown")
    if not bool(row.get("stats_observed", False)):
        return gap("played_but_statistics_missing")
    if target == "fantasy_ppr":
        return gap("incomplete_nflverse_to_pinned_sleeper_crosswalk")
    value = row.get(target)
    if value is None or pd.isna(value) or not np.isfinite(float(value)):
        return gap("target_statistic_missing")
    value = float(value)
    if target in COUNTS and (value < 0 or not value.is_integer()):
        return gap("invalid_count_outcome")
    if target == "anytime_td" and value not in (0.0, 1.0):
        return gap("invalid_anytime_event")
    if target == "rush_rec_yd" and (pd.isna(row.get("rush_yd")) or pd.isna(row.get("rec_yd"))):
        return gap("combined_components_missing")
    return {**result, "actual": value, "supplement_status": "supported", "gap_reason": None}
