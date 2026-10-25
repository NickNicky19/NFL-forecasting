"""Pure recorded-credit proxies and bounded historical slot construction.

Caller authenticates the existing permitted raw/normalized source contracts.
This module does no I/O, source selection, numerical forecast, fit or scoring.
Its totals are recorded-credit proxies, never certified complete NFL totals.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import math
import re

from .dynamic_opportunity_core import Query, Slot, TASK_ROLES, VERSION as CORE_VERSION, paired_count
from .state import digest, utc

VERSION = "dynamic-opportunity-history-v1-20261023"
LANE = "reconstructed_kickoff_plus_7_days"
SHA = re.compile(r"^[0-9a-f]{64}$")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _count(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0 and float(value).is_integer()
    except (OverflowError, ValueError):
        return False


def _source(binding):
    _require(isinstance(binding, dict) and binding.get("availability_lane") == LANE
             and binding.get("statistics_lag_days") == 7
             and binding.get("season_type") == "REG", "unchanged historical seven-day contract required")
    for name in ("source_policy_sha256", "source_manifest_sha256", "calendar_sha256", "calendar_rows_sha256",
                 "membership_manifest_sha256", "qualified_history_sha256", "qualification_policy_sha256"):
        _require(_sha(binding.get(name)), "explicit source/version binding required")
    _require(binding.get("calendar_inventory_complete") is True, "caller-authenticated calendar inventory required")
    versions = binding.get("statistics_sha256_by_season")
    _require(isinstance(versions, dict) and bool(versions)
             and all(isinstance(k, str) and k.isdecimal() and str(int(k)) == k and _sha(v)
                     for k, v in versions.items()), "nonempty explicit statistics source versions required")
    return digest(binding)


def _calendar(rows):
    _require(isinstance(rows, (list, tuple)), "finite explicit calendar required")
    by_period, by_game = {}, {}
    for row in rows:
        _require(isinstance(row, dict) and all(_text(row.get(k)) for k in ("game_id", "team", "opponent")), "calendar identity required")
        _require(type(row.get("season")) is int and type(row.get("week")) is int and 1 <= row["week"] <= 18
                 and row.get("season_type") == "REG" and row["team"] != row["opponent"], "calendar period/team invalid")
        kickoff = utc(row["kickoff_utc"])
        available = kickoff + timedelta(days=7)
        if "available_utc" in row:
            _require(utc(row["available_utc"]) == available, "frozen historical lag changed")
        item = {**{k: row[k] for k in ("game_id", "season", "week", "season_type", "team", "opponent")},
                "kickoff_utc": kickoff.isoformat(), "available_utc": available.isoformat()}
        key, game = (row["season"], row["week"], row["team"]), (row["game_id"], row["team"])
        _require(key not in by_period and game not in by_game, "duplicate/ambiguous calendar slot")
        by_period[key] = item; by_game[game] = item
    side_counts = {}
    for game_id, _ in by_game:
        side_counts[game_id] = side_counts.get(game_id, 0) + 1
    _require(all(n == 2 for n in side_counts.values()), "exactly two calendar sides per game ID required")
    for (_, team), row in by_game.items():
        other = by_game.get((row["game_id"], row["opponent"]))
        _require(other is not None and other["opponent"] == team
                 and all(other[k] == row[k] for k in ("season", "week", "season_type", "kickoff_utc")),
                 "complete reciprocal calendar identity required")
    return by_period, by_game


def build_recorded_proxy_panel(calendar, credit_rows, *, task, source_binding, asof_utc, requested_player_ids=()):
    """Sum explicit official all-position records before role/offer filtering.

    At least one explicit count is required. Missing fields remain counted as
    missing; duplicate/invalid records block the affected proxy. Known-team
    orphan-player records remain separately measured recorded credits, not an
    inferred residual or complete-player allocation. Unmapped rows are retained
    as global coverage counts and cannot be assigned to a convenient team.
    """
    source_sha = _source(source_binding)
    _require(task in TASK_ROLES, "declared workload task required")
    _require(isinstance(credit_rows, (list, tuple)), "finite explicit credit rows required")
    asof = utc(asof_utc); by_period, by_game = _calendar(calendar)
    _require(all(str(g["season"]) in source_binding["statistics_sha256_by_season"] for g in by_game.values()),
             "calendar season has no pinned statistics source")
    _require(digest(calendar) == source_binding["calendar_rows_sha256"], "calendar row inventory binding changed")
    requested = set(requested_player_ids)
    _require(all(_text(p) for p in requested), "explicit requested player identifiers required")
    groups = {}
    for key, game in by_game.items():
        groups[key] = {**game, "task": task, "recorded_sum": 0, "row_count": 0, "explicit_count_rows": 0,
                       "missing_count_rows": 0, "invalid_count_rows": 0, "duplicate_rows": 0,
                       "orphan_player_rows": 0, "orphan_player_credit_sum": 0,
                       "outside_requested_player_credit_sum": 0, "all_nfl_credits_complete": False}
    unassigned = []; seen_rows = {}; seen_players = set()
    for row in credit_rows:
        _require(isinstance(row, dict), "explicit credit-row mapping required")
        _require(row.get("task") == task, "credit task/count field mismatch")
        source_row_id = row.get("source_row_id")
        _require(_text(source_row_id), "immutable physical source-row pointer required")
        _require(row.get("season_type") == "REG", "non-REG source row forbidden")
        season = row.get("season")
        bound_hash = source_binding["statistics_sha256_by_season"].get(str(season))
        _require(_sha(bound_hash) and _sha(row.get("source_body_sha256")) and row["source_body_sha256"] == bound_hash,
                 "credit source hash/version mismatch")
        game = by_period.get((season, row.get("week"), row.get("team")))
        if game is None:
            unassigned.append({"source_row_id": source_row_id, "season": season, "week": row.get("week"), "reason": "unmapped_team_game"})
            continue
        key = (game["game_id"], game["team"]); group = groups[key]
        if utc(game["available_utc"]) >= asof:
            # No primitive value is accessed for an unavailable source slot.
            continue
        _require(row.get("game_id", game["game_id"]) == game["game_id"], "credit/calendar game identity conflict")
        if "available_utc" in row:
            _require(utc(row["available_utc"]) == utc(game["available_utc"]), "credit availability lane changed")
        group["row_count"] += 1
        player = row.get("player_id"); player_key = (*key, player) if _text(player) else None
        if player_key is None: group["orphan_player_rows"] += 1
        previous_key = seen_rows.get(source_row_id)
        duplicate = previous_key is not None or player_key is not None and player_key in seen_players
        seen_rows[source_row_id] = key
        if previous_key is not None and previous_key != key: groups[previous_key]["duplicate_rows"] += 1
        if player_key is not None: seen_players.add(player_key)
        if duplicate: group["duplicate_rows"] += 1
        support, value = row.get("count_support"), row.get("count")
        if support == "missing" or support is None:
            group["missing_count_rows"] += 1
            continue
        if support != "explicit_official_count" or not _count(value):
            group["invalid_count_rows"] += 1
            continue
        value = int(value); group["explicit_count_rows"] += 1; group["recorded_sum"] += value
        if player_key is None:
            group["orphan_player_credit_sum"] += value
        elif player not in requested:
            group["outside_requested_player_credit_sum"] += value
    for group in groups.values():
        available = utc(group["available_utc"]) < asof
        ready = available and group["explicit_count_rows"] > 0 and not group["duplicate_rows"] and not group["invalid_count_rows"]
        group.update(count=group["recorded_sum"] if ready else None,
                     state="RECORDED_PROXY_ONLY" if ready else "UNAVAILABLE",
                     reason="recorded_explicit_count_sum_not_complete_nfl_total" if ready else
                            "source_not_available" if not available else "duplicate_or_invalid_record" if
                            group["duplicate_rows"] or group["invalid_count_rows"] else "empty_or_all_missing_counts")
    return {"schema_version": VERSION + "-proxy-panel", "version": VERSION, "core_version": CORE_VERSION,
            "task": task, "source_binding_sha256": source_sha, "availability_lane": LANE,
            "asof_utc": asof.isoformat(), "calendar_sha256": digest(calendar),
            "requested_player_set_sha256": digest(sorted(requested)),
            "groups": sorted(groups.values(), key=lambda g: (g["kickoff_utc"], g["game_id"], g["team"])),
            "unassigned_rows": unassigned, "all_nfl_credits_complete": False,
            "joint_allocation": False, "participation_probability": "UNAVAILABLE"}


def build_offer_windows(offers, calendar, membership_rows, qualified_player_rows, proxy_panel, *, task, source_binding):
    """Return exactly one pure request/fallback per original offered query.

    ``offer.spell`` is a caller-authenticated derived membership descriptor.
    An unknown boundary cannot become a genuine cold start. Its source proof
    and every selected slot's same-spell membership are checked, not invented.
    No filter/point/static formula is evaluated here.
    """
    source_sha = _source(source_binding); _, games = _calendar(calendar)
    _require(all(str(g["season"]) in source_binding["statistics_sha256_by_season"] for g in games.values()),
             "calendar season has no pinned statistics source")
    _require(digest(calendar) == source_binding["calendar_rows_sha256"], "calendar row inventory binding changed")
    _require(all(isinstance(x, (list, tuple)) for x in (offers, membership_rows, qualified_player_rows)),
             "finite explicit offers/membership/player rows required")
    _require(task in TASK_ROLES and proxy_panel.get("schema_version") == VERSION + "-proxy-panel"
             and proxy_panel.get("task") == task and proxy_panel.get("source_binding_sha256") == source_sha
             and proxy_panel.get("availability_lane") == LANE and proxy_panel.get("calendar_sha256") == digest(calendar),
             "exact proxy/source/calendar binding required")
    proxies = {(g["game_id"], g["team"]): g for g in proxy_panel["groups"]}
    memberships, players = {}, {}
    for source, target in ((membership_rows, memberships), (qualified_player_rows, players)):
        for row in source:
            key = (row["player_id"], row["game_id"], row["team"])
            target.setdefault(key, []).append(row)
    results = []; seen = set()
    for offer in offers:
        _require(_text(offer.get("offer_id")) and offer["offer_id"] not in seen, "unique original offer ID required")
        seen.add(offer["offer_id"])
        result = {"offer": deepcopy(offer), "offer_id": offer["offer_id"], "state": "BASELINE_FALLBACK_REQUIRED",
                  "reason": "", "history": [], "slot_audit": [], "core_query": None, "volume": None,
                  "volume_supported": False, "static_control_request": None,
                  "source_binding_sha256": source_sha, "adapter_version": VERSION, "numeric_distribution": "NONE"}
        results.append(result)
        try:
            _require(offer.get("season_type") == "REG" and offer.get("task", task) == task, "query period/task mismatch")
            cutoff, kickoff = utc(offer["cutoff_utc"]), utc(offer["kickoff_utc"])
            _require(cutoff < kickoff and utc(proxy_panel["asof_utc"]) <= cutoff, "query/proxy cutoff mismatch")
            query_game = games.get((offer["game_id"], offer["team"]))
            _require(query_game is not None and query_game["opponent"] == offer["opponent"]
                     and query_game["season"] == offer["season"] and query_game["week"] == offer["week"]
                     and query_game["season_type"] == offer["season_type"] and utc(query_game["kickoff_utc"]) == kickoff,
                     "query/calendar identity mismatch")
            role = offer["position"]
            _require(role in TASK_ROLES[task], "outside_modeled_role_retained_reference")
            spell = offer.get("spell", {})
            _require(spell.get("state") == "qualified" and _sha(spell.get("membership_manifest_sha256"))
                     and spell["membership_manifest_sha256"] == source_binding["membership_manifest_sha256"]
                     and all(spell.get(k) == offer[k] for k in ("player_id", "team", "season"))
                     and _text(spell.get("spell_id"))
                     and spell.get("boundary") in {"season_start", "verified_team_change", "verified_cold_start"},
                     "ambiguous_membership_or_spell_boundary")
            boundary = utc(spell["started_utc"])
            _require(boundary <= cutoff, "spell starts after cutoff")
            if spell["boundary"] == "season_start":
                starts = [utc(g["kickoff_utc"]) for g in games.values() if g["team"] == offer["team"] and g["season"] == offer["season"]]
                _require(starts and boundary <= min(starts), "season-start boundary cannot hide earlier slots")
            prior_games = sorted((g for g in games.values() if g["team"] == offer["team"]
                                  and g["season"] == offer["season"] and boundary <= utc(g["kickoff_utc"]) < cutoff
                                  and g["game_id"] != offer["game_id"]), key=lambda g: (g["kickoff_utc"], g["game_id"]))
            selected = prior_games[-8:]; ambiguous = False; invalid_pair = False
            for game in selected:
                key = (offer["player_id"], game["game_id"], offer["team"])
                members = memberships.get(key, [])
                member_ok = len(members) == 1 and members[0].get("membership_state") == "qualified_same_spell" and \
                    members[0].get("spell_id") == spell["spell_id"] and members[0].get("membership_manifest_sha256") == spell["membership_manifest_sha256"]
                ambiguous |= not member_ok
                records = players.get(key, []); row = records[0] if len(records) == 1 else {}
                proxy = proxies[(game["game_id"], game["team"])]
                before = utc(game["available_utc"]) < cutoff
                if before and proxy["state"] == "RECORDED_PROXY_ONLY":
                    _require(_count(proxy["count"]), "invalid recorded proxy count support")
                qualified = member_ok and len(records) == 1 and before and row.get("source_qualified") is True
                _require(not row or row.get("season") == game["season"]
                         and row.get("task") == task
                         and ("week" not in row or row["week"] == game["week"])
                         and ("season_type" not in row or row["season_type"] == game["season_type"])
                         and row.get("opponent") == game["opponent"]
                         and utc(row["kickoff_utc"]) == utc(game["kickoff_utc"]), "player/calendar identity mismatch")
                if row and "available_utc" in row:
                    _require(utc(row["available_utc"]) == utc(game["available_utc"]), "player historical availability lane changed")
                participation = row.get("participation_state", "unknown") if qualified else "unknown"
                count_supported = qualified and participation == "played" and (row.get("count_support") == "explicit_value" or (
                    row.get("count_support") == "qualified_sparse_zero" and row.get("count") == 0 and _sha(row.get("zero_semantics_sha256"))))
                c = row.get("count") if qualified and participation == "played" and count_supported else None
                t = proxy["count"] if qualified and proxy["state"] == "RECORDED_PROXY_ONLY" else None
                slot = Slot(offer["player_id"], offer["team"], offer["season"], spell["spell_id"], task, role,
                            game["game_id"], game["kickoff_utc"], game["available_utc"], participation, qualified, c, t)
                ok, reason, _, _ = paired_count(slot)
                invalid_pair |= reason in {"invalid_participation_contract", "invalid_count_support", "player_exceeds_team_count"}
                result["history"].append(slot.manifest())
                result["slot_audit"].append({"game_id": game["game_id"], "state": reason,
                    "member_state": "qualified_same_spell" if member_ok else "ambiguous_or_missing_membership",
                    "source_available_before_cutoff": before, "player_records": len(records),
                    "proxy_state": proxy["state"], "proxy_partial_receipt": proxy})
            _require(not ambiguous, "ambiguous_membership_consumes_fixed_window_fallback")
            _require(not invalid_pair, "invalid_paired_count_requires_baseline_fallback")
            query = Query(offer["player_id"], offer["team"], offer["season"], spell["spell_id"], task, role,
                          offer["game_id"], offer["kickoff_utc"], offer["cutoff_utc"], True,
                          "last_eight_team_games" if len(prior_games) >= 8 else "start_of_season_or_spell")
            result["core_query"] = query.manifest()
            if task == "rush_att":
                volume = offer.get("f_team_rush_att_mean3")
                supported = type(volume) in (int, float) and math.isfinite(volume) and volume >= 0
                volume_audit = {"kind": "unchanged_original_f_team_rush_att_mean3", "value": volume if supported else None,
                                "value_state": "supported" if supported else "missing_or_invalid"}
            else:
                volume_slots = prior_games[-3:]
                valid = [proxies[(g["game_id"], g["team"])]["count"] for g in volume_slots
                         if utc(g["available_utc"]) < cutoff and proxies[(g["game_id"], g["team"])]["state"] == "RECORDED_PROXY_ONLY"]
                supported = bool(valid); volume = math.fsum(valid) / len(valid) if valid else None
                volume_audit = {"kind": "recorded_target_credit_proxy_mean3_finite_slots", "selected_game_ids": [g["game_id"] for g in volume_slots],
                                "selected_slots": len(volume_slots), "supported_slots": len(valid), "missing_slots": len(volume_slots) - len(valid),
                                "all_nfl_credits_complete": False, "normalized_to_attempts": False}
            result.update(volume=volume if supported else None, volume_supported=supported, volume_audit=volume_audit)
            _require(supported, "missing_fixed_volume_requires_baseline_fallback")
            result.update(state="READY_CORE_REQUEST", reason="same_source_conditional_marginal_request_only",
                          static_control_request={"history_sha256": digest(result["history"]), "core_query_sha256": digest(result["core_query"]),
                              "volume": volume, "prior": "EXACT_SAME_TRAINING_PRIOR_REQUIRED", "kappa": "EXACT_SAME_SELECTED_SETTING_REQUIRED",
                              "new_fit": False, "numeric_distribution": "NONE"})
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            result["reason"] = str(exc)
    return {"schema_version": VERSION + "-offer-windows", "adapter_version": VERSION,
            "source_binding_sha256": source_sha, "task": task, "original_offers": len(offers), "results": results,
            "joint_allocation": False, "participation_probability": "UNAVAILABLE", "verified_injury_role_claim": False}
