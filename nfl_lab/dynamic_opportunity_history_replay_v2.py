"""Explicit exposed historical replay window adapter; not live issuance.

Frozen V1 remains strict cutoff<kickoff. This separately versioned entry alone
allows cutoff<=kickoff under an explicit policy, with unchanged original query
clocks, strict seven-day source availability, proxies and slot/fallback rules.
The explicit window body is retained because frozen V1 has no gate parameter;
no runtime source rewriting, monkeypatching or timestamp edits are performed.
"""
from copy import deepcopy
import math

from .dynamic_opportunity_core import Query, Slot, TASK_ROLES, paired_count
from .dynamic_opportunity_history import (
    VERSION as BASE_VERSION, LANE, _source, _calendar, _require, _sha, _text, _count,
    build_recorded_proxy_panel,
)
from .state import digest, utc

VERSION = "dynamic-opportunity-history-replay-v2-20261023"
REPLAY_LANE = "EXPOSED_HISTORICAL_REPLAY"


def validate_replay_policy(policy, *, source_binding):
    _require(isinstance(source_binding, dict) and _sha(source_binding.get("source_policy_sha256")),
             "explicit original source policy binding required")
    expected = {
        "schema_version": VERSION + "-policy",
        "execution_lane": REPLAY_LANE,
        "source_policy_sha256": source_binding["source_policy_sha256"],
        "query_cutoff_rule": "cutoff_utc_at_or_before_kickoff_utc",
        "source_availability_rule": "kickoff_plus_7_days_strictly_before_cutoff_utc",
        "original_clocks": "PRESERVE_NO_EDITS_OR_EPSILON",
        "prospective_issuance": "FORBIDDEN",
    }
    _require(isinstance(policy, dict) and policy == expected, "explicit exposed historical replay policy required")
    return digest(policy)


def build_historical_offer_windows(offers, calendar, membership_rows, qualified_player_rows, proxy_panel, *, task, source_binding, replay_policy):
    """Return exactly one pure request/fallback per original offered query.

    ``offer.spell`` is a caller-authenticated derived membership descriptor.
    An unknown boundary cannot become a genuine cold start. Its source proof
    and every selected slot's same-spell membership are checked, not invented.
    No filter/point/static formula is evaluated here.
    """
    replay_sha = validate_replay_policy(replay_policy, source_binding=source_binding)
    source_sha = _source(source_binding); _, games = _calendar(calendar)
    _require(all(str(g["season"]) in source_binding["statistics_sha256_by_season"] for g in games.values()),
             "calendar season has no pinned statistics source")
    _require(digest(calendar) == source_binding["calendar_rows_sha256"], "calendar row inventory binding changed")
    _require(all(isinstance(x, (list, tuple)) for x in (offers, membership_rows, qualified_player_rows)),
             "finite explicit offers/membership/player rows required")
    _require(task in TASK_ROLES and proxy_panel.get("schema_version") == BASE_VERSION + "-proxy-panel"
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
                  "source_binding_sha256": source_sha, "adapter_version": VERSION, "numeric_distribution": "NONE",
                  "evidence_lane": REPLAY_LANE, "historical_replay_policy_sha256": replay_sha,
                  "forecast_timing_claim": "AFTER_GAME_RECONSTRUCTION_NOT_ORIGINAL_ISSUANCE", "query_clock_edits": 0}
        results.append(result)
        try:
            _require(offer.get("season_type") == "REG" and offer.get("task", task) == task, "query period/task mismatch")
            cutoff, kickoff = utc(offer["cutoff_utc"]), utc(offer["kickoff_utc"])
            _require(cutoff <= kickoff and utc(proxy_panel["asof_utc"]) <= cutoff, "query/proxy cutoff mismatch")
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
            "base_adapter_version": BASE_VERSION, "evidence_lane": REPLAY_LANE, "historical_replay_policy_sha256": replay_sha,
            "forecast_timing_claim": "AFTER_GAME_RECONSTRUCTION_NOT_ORIGINAL_ISSUANCE", "query_clock_edits": 0,
            "joint_allocation": False, "participation_probability": "UNAVAILABLE", "verified_injury_role_claim": False}
