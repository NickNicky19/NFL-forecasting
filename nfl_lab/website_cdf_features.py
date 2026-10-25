"""Strict, local query adapter for the original saved website opportunities.

This module does not load target outcomes, fit models, or fetch inputs.  Its
player windows call the same builder as historical training.  Saved sparse
field omission is unknown, including display zeros manufactured by the site.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from nfl_lab.cdf_engine import assert_clock_contract
from nfl_lab.data import TARGETS
from nfl_lab.features import PLAYER_STATS, TEAM_STATS, build_features

VERSION = "website-query-features-v1-20261023"
KEYS = ["season", "week", "game_id", "player_id"]
CATEGORY_MAP = {**{t: t for t in TARGETS if t != "fantasy_ppr"}, "fpts": "fantasy_ppr"}
COUNT_FIELDS = {"pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec",
                "rush_td", "rec_td", "rec_tgt", "offense_snaps"}
SIGNED_FIELDS = {"pass_yd", "rush_yd", "rec_yd", "rush_rec_yd"}
INPUT_NAMES = ("original_baseline", "exact_original_board", "saved_calendar", "history_and_final_status")
DEFAULT_PROTOCOL = Path("/workspace/website-methods-research/protocol.json")
DEFAULT_OUTPUT = Path("/workspace/website-methods-research/resumed/website-cdf-20261023")
HISTORICAL_FEATURES = Path("/workspace/NFL-forecasting/data/processed/features.parquet")
HISTORICAL_FEATURES_SHA256 = "ff7a14bac024958f32cbf367e83f6d70e4f86572f461ca6ebd33a9207d04d297"
IDENTITY_COHORT = Path("/workspace/NFL-forecasting/runs/archive-lab-week6-v1-2026-10-22/20261022T174651696787/archive-cohort.parquet")
IDENTITY_COHORT_SHA256 = "29b8039e4267ecdef163bb33bf4db4f50f688b68d76e7d469c8e93c8d00ae284"
REFERENCE_BUILDER = Path("/workspace/website-reference/pull/build.py")
REFERENCE_BUILDER_SHA256 = "75bf99c55b5f2561a60a120c82db368ad3b996a8a64e9ab08828b586a9314419"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def document(path: Path):
    body = path.read_bytes()
    if path.suffix == ".gz":
        body = gzip.decompress(body)
    value = json.loads(body)
    if "payload" in value:
        if hashlib.sha256(canonical(value["payload"])).hexdigest() != value["payload_sha256"]:
            raise ValueError("envelope payload hash mismatch")
        return value["payload"]
    return value


def stamp(value) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.tz_convert("UTC")


def supported(value, field: str) -> float:
    """Validate explicit source support; never turn absent values into zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return np.nan
    if field in COUNT_FIELDS and (value < 0 or value != math.floor(value)):
        return np.nan
    if field in SIGNED_FIELDS and value != math.floor(value):
        return np.nan
    return float(value)


def player_stats(log: dict | None, record: dict | None) -> tuple[dict, dict]:
    """Prefer explicit original-board fields, then explicit reconstructed fields.

    The display log's ``s`` array and prop ``values`` are deliberately unused:
    the pinned builder substitutes zero for missing sparse fields in both.
    ``st`` preserves signed nonzero statistics.  The verification cache cannot
    recover source-trimmed zeros either, so omissions remain NaN there as well.
    """
    out = {name: np.nan for name in PLAYER_STATS}
    trail = {}
    original = log.get("st", {}) if log else {}
    reconstructed = record.get("stats", {}) if record else {}
    for field in set(PLAYER_STATS) - {"fantasy_ppr", "rush_rec_yd", "anytime_td"}:
        source_field = "off_snp" if field == "offense_snaps" else field
        value = log.get("snp") if log and field == "offense_snaps" else original.get(source_field)
        qualified = supported(value, field)
        lane = "original_board_log"
        if not math.isfinite(qualified):
            qualified = supported(reconstructed.get(source_field), field)
            lane = "later_download_reconstructed_history"
        out[field] = qualified
        if math.isfinite(qualified):
            trail[field] = {"lane": lane, "field": "log.snp" if lane == "original_board_log" and field == "offense_snaps"
                            else ("log.st." if lane == "original_board_log" else "weeks.stats.") + source_field}
    # Preserve pairwise support; a positive component does not establish an
    # absent other component as zero, even for a touchdown indicator.
    if all(math.isfinite(out[k]) for k in ("rush_yd", "rec_yd")):
        out["rush_rec_yd"] = out["rush_yd"] + out["rec_yd"]
        trail["rush_rec_yd"] = {"derived_from": ["rush_yd", "rec_yd"]}
    if all(math.isfinite(out[k]) for k in ("rush_td", "rec_td")):
        out["anytime_td"] = float(out["rush_td"] + out["rec_td"] > 0)
        trail["anytime_td"] = {"derived_from": ["rush_td", "rec_td"]}
    if math.isfinite(out["pass_cmp"]) and math.isfinite(out["pass_att"]) and out["pass_cmp"] > out["pass_att"]:
        out["pass_cmp"] = out["pass_att"] = np.nan
        trail.pop("pass_cmp", None)
        trail.pop("pass_att", None)
    return out, trail


def _game_for(schedule: list[dict], week: int, team: str) -> dict | None:
    matches = [g for g in schedule if int(g["w"]) == week and team in (g["home"], g["away"])]
    if len(matches) > 1:
        raise ValueError("ambiguous team/week schedule")
    return matches[0] if matches else None


def _opponent(game: dict, team: str) -> str:
    if team not in (game["home"], game["away"]):
        raise ValueError("team not scheduled")
    return game["away"] if team == game["home"] else game["home"]


def _past_log_game(schedule: list[dict], week: int, opponent: str) -> tuple[dict, str]:
    game = _game_for(schedule, week, opponent)
    if game is None:
        raise ValueError("original log opponent on calendar bye")
    return game, _opponent(game, opponent)


def _empty_stats() -> dict:
    return {**{field: np.nan for field in PLAYER_STATS},
            **{"team_stat_" + field: np.nan for field in TEAM_STATS}}


def build_query(baseline: dict, board: dict, calendar: dict, history: dict, *,
                old_history: pd.DataFrame | None = None, identity: dict[str, str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Build all original query rows using only saved strictly prior games.

    Historical publication is the same explicit kickoff+7d assumption as
    training.  The original board artifact and reconstructed history clocks are
    retained separately.  Unknown roster slots consume windows; a team change
    with unresolved intervening membership masks player features and uses the
    existing model's cold/unknown role prior.
    """
    cutoff = stamp(baseline["captured_at"])
    board_clock = stamp(board["generated_at"])
    calendar_clock = stamp(calendar["generated_at"])
    reconstructed_clock = stamp(history["inputs_observed_at"])
    if not max(board_clock, calendar_clock, reconstructed_clock) < cutoff:
        raise ValueError("source clock not strictly before query cutoff")
    season, week = int(board["season"]), int(board["week"])
    if (int(calendar["season"]), int(history["season"]), int(history["week"])) != (season, season, week):
        raise ValueError("source season/week mismatch")
    # Only explicit prior-week history is retained.  Target week_data and W6+
    # statuses are never inspected, copied, or used to derive any query field.
    prior = {w: history["weeks"].get(str(w), {}) for w in range(1, week)}
    statuses = {w: history.get("game_status", {}).get(f"{season}_{w:02d}", {}) for w in range(1, week)}
    schedule = [{k: g[k] for k in ("w", "id", "kickoff", "home", "away")} for g in calendar["schedule"]]
    by_game = {str(g["id"]): g for g in schedule}
    if len(by_game) != len(schedule):
        raise ValueError("duplicate schedule identity")
    players = {(str(p["id"]), str(p["game_id"])): p for p in board["players"]}
    if len(players) != len(board["players"]):
        raise ValueError("duplicate original player/game")
    original = baseline["rows"]
    if len({(str(r["player_id"]), str(r["game_id"]), r["category"]) for r in original}) != len(original):
        raise ValueError("duplicate original category opportunity")
    selected = {}
    opportunities = []
    for receipt in original:
        sid, gid = str(receipt["player_id"]), str(receipt["game_id"])
        player = players[(sid, gid)]
        game = by_game[gid]
        if (receipt["season"], receipt["week"], receipt["position"], receipt["team"]) != (season, week, player["pos"], player["team"]):
            raise ValueError("original query identity mismatch")
        if stamp(receipt["kickoff"]) != stamp(game["kickoff"]) or not cutoff < stamp(game["kickoff"]):
            raise ValueError("query kickoff/cutoff mismatch")
        if _opponent(game, player["team"]) != player["opp"] or int(game["w"]) != week:
            raise ValueError("query opponent/week mismatch")
        props = {p["key"]: p for p in player["props"]}
        if len(props) != len(player["props"]):
            raise ValueError("duplicate original category")
        prop = props[receipt["category"]]
        if (receipt["raw_projection"], receipt["adjusted_projection"]) != (prop.get("proj"), prop.get("adj")):
            raise ValueError("literal comparator binding mismatch")
        probability = prop.get("td_chance") if receipt["category"] == "anytime_td" else None
        if probability is not None and (isinstance(probability, bool) or not isinstance(probability, (float, int)) or not 0 <= probability <= 1):
            raise ValueError("invalid literal touchdown probability")
        opportunities.append({"season": season, "week": week, "game_id": gid, "player_id": "sleeper:" + sid,
                              "target": CATEGORY_MAP[receipt["category"]], "original_category": receipt["category"],
                              "website_point": receipt["adjusted_projection"], "raw_point": receipt["raw_projection"],
                              "website_probability": probability, "raw_probability": np.nan,
                              "simple_point": np.nan, "simple_probability": np.nan,
                              "comparator_provenance": "hash_bound_original_receipt_and_board",
                              "probability_provenance": "original_board.props.td_chance" if probability is not None else "unavailable",
                              "category_state": "BLOCKED_EXACT_PPR_SOURCE_CONTRACT" if receipt["category"] == "fpts" else "QUERY_READY"})
        selected[(sid, gid)] = player
    identity = identity or {}
    rows, provenance, metadata = [], [], {}
    if old_history is not None:
        if not old_history.season.between(2019, season - 1).all():
            raise ValueError("historical extension outside pinned training period")
        if (pd.to_datetime(old_history.kickoff_utc, utc=True) >= cutoff).any():
            raise ValueError("nonprior historical extension")
        for record in old_history.to_dict("records"):
            # The exact GSIS mapping has already been resolved once, and is
            # independent of labels.  All old full-team fields are masked.
            record.update({"team_stat_" + field: np.nan for field in TEAM_STATS})
            record["fantasy_ppr"] = np.nan
            record["cutoff_utc"] = record["kickoff_utc"]
            rows.append(record)
    for (sid, gid), player in selected.items():
        logs = {int(entry["w"]): entry for entry in player.get("log", []) if int(entry["w"]) < week}
        if len(logs) != len([x for x in player.get("log", []) if int(x["w"]) < week]):
            raise ValueError("duplicate original log week")
        teams = {player["team"]}
        known_weeks = set()
        absent_weeks = []
        slots = []
        for prior_week in range(1, week):
            log = logs.get(prior_week)
            record = prior[prior_week].get(sid)
            actual_team = record.get("team") if record else None
            if log:
                game, log_team = _past_log_game(schedule, prior_week, log["opp"])
                if actual_team and actual_team != log_team:
                    raise ValueError("original log/history team conflict")
                actual_team = log_team
            elif actual_team:
                game = _game_for(schedule, prior_week, actual_team)
            else:
                # Explicit conservative slot assumption, never called verified
                # continuous membership.  Unknown membership consumes a slot.
                game = _game_for(schedule, prior_week, player["team"])
                absent_weeks.append(prior_week)
            if game is None:
                if log or record:
                    raise ValueError("history statistics during scheduled bye")
                provenance.append({"player_id": "sleeper:" + sid, "week": prior_week,
                                   "slot_state": "scheduled_current_team_bye_no_record", "game_id": None})
                continue
            team = actual_team or player["team"]
            teams.add(team)
            opp = _opponent(game, team)
            kickoff = stamp(game["kickoff"])
            if not kickoff < cutoff:
                raise ValueError("nonprior source game")
            if record and record.get("opp") != opp:
                raise ValueError("prior history opponent mismatch")
            status = statuses[prior_week]
            saved = status.get("games", {}).get(str(game["id"]))
            final_clock = None
            if saved:
                final_clock = stamp(status["collected_at"])
                if stamp(saved["kickoff"]) != kickoff or not kickoff < final_clock < cutoff:
                    raise ValueError("prior final-status identity/clock mismatch")
                if saved.get("completed") is not True or saved.get("state") != "post" or saved.get("detail") not in {"Final", "Final/OT"}:
                    raise ValueError("source game not final")
            stats, trail = player_stats(log, record)
            positive_gp = record and supported(record.get("stats", {}).get("gp"), "rec") > 0
            positive_snap = math.isfinite(stats["offense_snaps"]) and stats["offense_snaps"] > 0
            played = bool(log is not None or positive_gp or positive_snap)
            if played:
                known_weeks.add(prior_week)
            # A missing final status cannot qualify reconstructed source fields.
            if not saved:
                for field, info in list(trail.items()):
                    if info.get("lane") == "later_download_reconstructed_history":
                        stats[field] = np.nan
                        trail.pop(field)
                for composite in ("rush_rec_yd", "anytime_td"):
                    stats[composite] = np.nan
                    trail.pop(composite, None)
            row = {"season": season, "week": prior_week, "game_id": str(game["id"]), "player_id": "sleeper:" + sid,
                   "team": team, "opponent": opp, "position": player["pos"], "kickoff_utc": kickoff,
                   "cutoff_utc": kickoff, "outcome_available_utc": kickoff + pd.Timedelta(days=7),
                   "participation_state": "played" if played else "unknown", "is_home": float(team == game["home"]),
                   **_empty_stats(), **stats}
            rows.append(row)
            eligible = row["outcome_available_utc"] < cutoff
            slots.append({"week": prior_week, "game_id": row["game_id"], "eligible": eligible,
                          "participation": row["participation_state"], "association_known": actual_team is not None})
            provenance.append({"player_id": row["player_id"], "week": prior_week, "game_id": row["game_id"],
                               "team": team, "opponent": opp, "kickoff_utc": kickoff.isoformat(),
                               "assumed_outcome_available_utc": row["outcome_available_utc"].isoformat(),
                               "query_cutoff_utc": cutoff.isoformat(), "eligible_at_query": eligible,
                               "participation_state": row["participation_state"],
                               "slot_state": "source_observed_team" if actual_team else "unverified_current_team_roster_slot",
                               "original_board_generated_at": board_clock.isoformat() if log else None,
                               "history_embedded_observed_at": reconstructed_clock.isoformat() if record else None,
                               "final_status_embedded_observed_at": final_clock.isoformat() if final_clock else None,
                               "supported_fields": json.dumps(trail, sort_keys=True)})
        query_game = by_game[gid]
        rows.append({"season": season, "week": week, "game_id": gid, "player_id": "sleeper:" + sid,
                     "position": player["pos"], "team": player["team"], "opponent": player["opp"],
                     "kickoff_utc": stamp(query_game["kickoff"]), "cutoff_utc": cutoff,
                     "outcome_available_utc": stamp(query_game["kickoff"]) + pd.Timedelta(days=7),
                     "participation_state": "unknown", "is_home": float(player["team"] == query_game["home"]),
                     **_empty_stats()})
        bound = "sleeper:" + sid in identity
        metadata["sleeper:" + sid] = {
            "canonical_player_id": identity.get("sleeper:" + sid),
            "identity_binding": "exact_current_vintage_sleeper_gsis" if bound else "unlinked_or_ambiguous_identity",
            "history_season_floor": 2019 if bound else season, "history_prior_seasons_available": bound,
            "history8_truncated": not bound, "history_observed_played_weeks": len(known_weeks),
            "history_available_slots": sum(x["eligible"] for x in slots),
            "history_unknown_slots": sum(x["eligible"] and x["participation"] == "unknown" for x in slots),
            "history_unverified_roster_slots": sum(x["eligible"] and not x["association_known"] for x in slots),
            "history_prior_teams": json.dumps(sorted(teams)),
            "history_trade_membership_ambiguous": len(teams) > 1 and any(not x["association_known"] and x["eligible"] for x in slots),
            "history_roster_semantics": "observed source association; missing current-team scheduled games consume unknown slots; roster publication unverified",
        }
    # All-position official full-team statistics are unavailable.  Explicit all
    # missing team_stat_* columns prevent build_features' partial-player sum
    # fallback.  Calendar-only rows provide complete schedule rest context.
    for game in schedule:
        if int(game["w"]) > week or stamp(game["kickoff"]) > max(stamp(by_game[g]["kickoff"]) for _, g in selected):
            continue
        for team in (game["home"], game["away"]):
            rows.append({"season": season, "week": int(game["w"]), "game_id": str(game["id"]),
                         "player_id": "schedule-context:" + team, "team": team, "opponent": _opponent(game, team),
                         "position": "unknown", "kickoff_utc": stamp(game["kickoff"]),
                         "cutoff_utc": stamp(game["kickoff"]),
                         "outcome_available_utc": stamp(game["kickoff"]) + pd.Timedelta(days=7),
                         "participation_state": "unknown", "is_home": float(team == game["home"]), **_empty_stats()})
    feature_frame = build_features(pd.DataFrame(rows))
    query = feature_frame.loc[feature_frame.season.eq(season) & feature_frame.week.eq(week)
                              & feature_frame.player_id.str.startswith("sleeper:")].copy()
    # Raw stat columns for the target game are all missing and not exported.
    columns = KEYS + ["position", "team", "opponent", "kickoff_utc", "cutoff_utc", "outcome_available_utc",
                      "participation_state", "feature_max_source_available_utc"]
    columns += [c for c in query if c.startswith("f_")]
    query = query[columns].reset_index(drop=True)
    query = pd.concat([query, pd.DataFrame([metadata[sid] for sid in query.player_id])], axis=1)
    uncertain = query.history_trade_membership_ambiguous
    query.loc[uncertain, [c for c in query if c.startswith("f_player_")]] = np.nan
    # With no qualified full-team source these counts are unknown, not zero.
    query.loc[:, [c for c in query if c.startswith(("f_team_", "f_opp_"))]] = np.nan
    query["feature_max_assumed_history_available_utc"] = query.feature_max_source_available_utc
    # Actual artifact generation is distinct from assumed per-game publication.
    # Both are strictly earlier than the receipt cutoff; postgame download time
    # never becomes a fictitious pregame availability claim.
    query["feature_max_source_available_utc"] = [
        max([board_clock, calendar_clock, reconstructed_clock]
            + ([stamp(value)] if pd.notna(value) else []))
        for value in query.feature_max_assumed_history_available_utc
    ]
    query["original_board_generated_at"] = board_clock
    query["calendar_generated_at"] = calendar_clock
    query["history_embedded_observed_at"] = reconstructed_clock
    query["source_clock_semantics"] = "maximum embedded/assumed source clocks; actual historical public revision time unavailable"
    query["evidence_lane"] = "postgame reconstruction of exposed 2026 W6 using hash-bound pregame board; no prospective claim"
    query["feature_adapter_version"] = VERSION
    if query.duplicated(KEYS).any():
        raise ValueError("duplicate query identity")
    assert_clock_contract(query)
    opportunities_frame = pd.DataFrame(opportunities)
    if len(opportunities_frame) != len(original) or len(query) != len(selected):
        raise ValueError("original opportunity population changed")
    report = {"version": VERSION, "query_players": len(query), "opportunity_rows": len(opportunities_frame),
              "categories": opportunities_frame.groupby(["original_category", "target"]).size().reset_index(name="rows").to_dict("records"),
              "numeric_features": len([c for c in query if c.startswith("f_")]),
              "nonmissing_features": {c: int(query[c].notna().sum()) for c in query if c.startswith("f_")},
              "history_available_slots": query.history_available_slots.value_counts().sort_index().to_dict(),
              "history_unknown_slots": int(query.history_unknown_slots.sum()),
              "history_unverified_roster_slots": int(query.history_unverified_roster_slots.sum()),
              "ambiguous_trade_players_masked": int(uncertain.sum()),
              "window8_truncated_players": int(query.history8_truncated.sum()),
              "exact_identity_bindings": int(query.history_prior_seasons_available.sum()),
              "historical_extension_rows": len(old_history) if old_history is not None else 0,
              "players_with_2019_25_historical_rows": int(old_history.player_id.nunique()) if old_history is not None else 0,
              "all_position_official_team_totals_available": False,
              "unsupported_context": ["2026 official full-team statistical totals", "injuries", "weather", "routes", "historic roster publication", "prior seasons for unlinked identities"],
              "clock_assumption": "same training rule: prior kickoff + 7 days strictly before query cutoff; separate actual artifact clocks retained",
              "source_clock_semantics": "max of original-board generation, calendar generation, reconstructed embedded history observation, and assumed per-game history availability; historical public revision times unavailable",
              "verification_downloaded_at": None,
              "verification_download_timing": "postgame recovered download; authenticated retrieved_at not retained; embedded pregame observation is a reconstruction assumption",
              "week5_availability_effect": "most W5 games excluded by unchanged seven-day lag despite their statistics existing in the pregame original board",
              "zero_policy": "only explicit supported values; sparse omissions and display-substituted zeros remain missing",
              "PPR_state": "blocked; no generic points labels or forecast inputs", "fits": 0, "target_outcomes_loaded": False,
              "evidence_lane": "exposed W6 reconstruction; not original runner reproduction or prospective confirmation"}
    return query, opportunities_frame, pd.DataFrame(provenance), report


def historical_extension() -> tuple[pd.DataFrame, dict[str, str], dict]:
    """Read identity-only cohort fields and original 2019-25 source columns.

    The old archive evaluation rows and their outcomes are never opened.
    Original feature-cache raw columns are used instead of the separately
    mutated history.parquet.  No fuzzy player or name matching is attempted.
    """
    for path, expected in ((HISTORICAL_FEATURES, HISTORICAL_FEATURES_SHA256),
                           (IDENTITY_COHORT, IDENTITY_COHORT_SHA256),
                           (REFERENCE_BUILDER, REFERENCE_BUILDER_SHA256)):
        if sha(path) != expected:
            raise ValueError("pinned historical dependency changed: " + str(path))
    cols = KEYS + ["canonical_player_id", "identity_binding"]
    cohort = pd.read_parquet(IDENTITY_COHORT, columns=cols)
    identity = {}
    for sid, group in cohort.groupby("player_id", sort=False):
        names = group.canonical_player_id.dropna().unique()
        if len(names) == 1 and str(names[0]).startswith("00-") and group.identity_binding.eq("exact_current_vintage_sleeper_gsis").all():
            identity[str(sid)] = str(names[0])
    if len(set(identity.values())) != len(identity):
        raise ValueError("ambiguous many-to-one canonical identity")
    raw_cols = KEYS + ["team", "opponent", "position", "kickoff_utc", "outcome_available_utc",
                       "is_home", "participation_state"] + list(dict.fromkeys(PLAYER_STATS))
    old = pd.read_parquet(HISTORICAL_FEATURES, columns=raw_cols)
    if not old.season.between(2019, 2025).all():
        raise ValueError("historical cache period changed")
    reverse = {canonical: sleeper for sleeper, canonical in identity.items()}
    old = old.loc[old.player_id.isin(reverse)].copy()
    old["player_id"] = old.player_id.map(reverse)
    pins = {"historical_source_cache": {"path": str(HISTORICAL_FEATURES), "sha256": HISTORICAL_FEATURES_SHA256,
                                        "columns": raw_cols, "rows_used": len(old), "seasons": list(range(2019, 2026)),
                                        "clock": "current-vintage historical reconstruction; kickoff+7d assumed"},
            "identity_only_archive_cohort": {"path": str(IDENTITY_COHORT), "sha256": IDENTITY_COHORT_SHA256,
                                             "columns": cols, "exact_bindings": len(identity)},
            "original_website_builder": {"path": str(REFERENCE_BUILDER), "sha256": REFERENCE_BUILDER_SHA256,
                                          "participation_proof": "build_history lines152-164 includes only positive gp/off_snp; row.log line392 uses that history",
                                          "sparse_zero_proof": "trim_stats lines57-67 removes zero; game_log lines275-282 and prop values lines198-203 substitute display zero"}}
    return old, identity, pins


def run(protocol_path: Path = DEFAULT_PROTOCOL, output: Path = DEFAULT_OUTPUT) -> dict:
    protocol = json.loads(protocol_path.read_text())
    docs, pins = {}, {}
    # qualified_saved_outcomes is intentionally never opened.
    for name in INPUT_NAMES:
        pin = protocol["inputs"][name]
        path = Path(pin["path"])
        if path.stat().st_size != pin["bytes"] or sha(path) != pin["sha256"]:
            raise ValueError("pinned input changed: " + name)
        docs[name] = document(path)
        pins[name] = pin
    old, identity, historical_pins = historical_extension()
    query, opportunities, provenance, report = build_query(docs["original_baseline"], docs["exact_original_board"],
                                                         docs["saved_calendar"], docs["history_and_final_status"],
                                                         old_history=old, identity=identity)
    if len(query) != 396 or len(opportunities) != 2083 or set(opportunities.target) != set(TARGETS):
        raise ValueError("exact original 396/2083/all12 population changed")
    output.mkdir(parents=True, exist_ok=True)
    for name in INPUT_NAMES:
        provenance["source_" + name + "_sha256"] = pins[name]["sha256"]
    provenance["source_historical_cache_sha256"] = HISTORICAL_FEATURES_SHA256
    provenance["source_identity_cohort_sha256"] = IDENTITY_COHORT_SHA256
    historical_trail = old[KEYS + ["team", "opponent", "kickoff_utc", "outcome_available_utc", "participation_state"]].copy()
    historical_trail["source_cache_sha256"] = HISTORICAL_FEATURES_SHA256
    historical_trail["source_identity_cohort_sha256"] = IDENTITY_COHORT_SHA256
    historical_trail["slot_state"] = "original_training_cache_exact_identity_reconstruction"
    historical_trail["query_cutoff_utc"] = docs["original_baseline"]["captured_at"]
    query.to_parquet(output / "query-features.parquet", index=False)
    opportunities.to_parquet(output / "opportunities.parquet", index=False)
    provenance.to_parquet(output / "feature-provenance.parquet", index=False)
    historical_trail.to_parquet(output / "historical-feature-provenance.parquet", index=False)
    report["inputs"] = pins
    report["historical_dependencies"] = historical_pins
    report["protocol_sha256"] = sha(protocol_path)
    report["adapter_sha256"] = sha(Path(__file__))
    report["feature_builder_sha256"] = sha(Path(__file__).with_name("features.py"))
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["outputs"] = {name: {"path": str(output / name), "sha256": sha(output / name)}
                         for name in ("query-features.parquet", "opportunities.parquet", "feature-provenance.parquet", "historical-feature-provenance.parquet")}
    (output / "feature-coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.protocol, args.output)
    print(json.dumps({k: result[k] for k in ("version", "query_players", "opportunity_rows", "numeric_features", "fits", "target_outcomes_loaded")}))
