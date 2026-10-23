"""Fictional-only zero-support contracts; no NFL values or source readers."""
import builtins
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import raw_orphan_zero_audit as subject
from nfl_lab.raw_orphan_context import RAW, partition_context
from nfl_lab import ftn_zero_join as original

DIGEST = "f" * 64
PRIMITIVE_DIGEST = "e" * 64


def identity(number):
    return f"99-{number:07d}"  # Explicitly fictional identifiers.


def fictional():
    raw = []
    for i in range(67):
        team, opponent = ("BAL", "KC") if i % 2 else ("KC", "BAL")
        raw.append({"game_id": original.GAME, "season": 2024, "week": 1, "season_type": "REG",
            "player_id": identity(500+i) if i < 5 else identity(i+1) if i < 66 else None,
            "team": team, "opponent_team": opponent, "position": ("QB", "RB", "WR", "TE")[i%4] if i<66 else None,
            **{name: 0 for name in subject.PRIMITIVES}})
    offered = [{"season": 2024, "week": 1, "game_id": original.GAME, "player_id": r["player_id"],
        "position": r["position"], "team": r["team"], "opponent": r["opponent_team"]} for r in raw[:31]]
    accepted = [{**r, "official_physical_event": False, "participation_state": "unknown",
        "participation_evidence": "no_game_specific_participation_contract"} for r in offered]
    return raw, offered, {identity(i) for i in range(1,93)}, accepted


def structure(raw, offered, witnesses):
    return partition_context([{key:r[key] for key in RAW} for r in raw], offered, witnesses,
        raw_projection_sha256=DIGEST)


def run(raw, offered, witnesses, accepted, prior=None):
    records, union, coverage = structure(raw, offered, witnesses) if prior is None else prior
    return subject.audit_zero_candidates(raw, offered, witnesses, accepted,
        projection_sha256=PRIMITIVE_DIGEST, structural_projection_sha256=DIGEST,
        structural_records=records, structural_union=union, structural_coverage=coverage)


def selected(args, position="RB"):
    raw, offered, witnesses, accepted = args
    q=next(row for row in offered if row["position"] == position and row["player_id"] in witnesses)
    r=next(row for row in raw if row["player_id"] == q["player_id"])
    h=next(row for row in accepted if row["player_id"] == q["player_id"])
    return r,q,h


def target(rows, player, category):
    return next(row for row in rows if row["player_id"] == player and row["target"] == category)


class ZeroSupportChecks(unittest.TestCase):
    def test_complete_67_97_plus_orphan_all_twelve_reconcile(self):
        inventory,rows,orphans,report=run(*fictional())
        self.assertEqual((len(inventory),len(rows),len(orphans)),(67,97*12,12))
        self.assertEqual(report["coverage"]["conservative_union_plus_orphan_units"],98)
        self.assertEqual(set(report["targets"]),set(original.TARGETS))
        self.assertTrue(all(r["all_known_player_opportunities"]==97 and r["original_offered_opportunities"]==31
            and r["unidentified_raw_record_opportunities"]==1 for r in report["targets"].values()))

    def test_every_original_raw_value_and_record_order_is_preserved(self):
        args=fictional();inventory,_,_,_=run(*args)
        self.assertEqual([{key:r[key] for key in RAW+subject.PRIMITIVES} for r in inventory],args[0])
        self.assertEqual([r["record_ordinal"] for r in inventory],list(range(67)))

    def test_orphan_nonzero_primitives_never_supply_a_player_value(self):
        args=fictional();args[0][-1].update({key:987 for key in subject.PRIMITIVES})
        inventory,rows,orphans,_=run(*args)
        self.assertIsNone(inventory[-1]["player_id"])
        self.assertTrue(all(not r["candidate_new_support"] and not r["known_zero"] for r in orphans))
        self.assertEqual(len({r["player_id"] for r in rows}),97)

    def test_duplicates_are_ambiguous_with_no_row_choice(self):
        args=fictional();r,q,_=selected(args);second=next(x for x in args[0] if x is not r and x["player_id"] in args[2])
        second["player_id"]=r["player_id"];second["carries"]=77
        inventory,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertEqual(t["raw_record_count"],2);self.assertEqual(t["target_state"],"AMBIGUOUS_RAW_ROWS")
        self.assertFalse(t["known_zero"] or t["candidate_new_support"])
        self.assertEqual(len(inventory),67)

    def test_raw_offered_conflict_cannot_use_its_primitive(self):
        args=fictional();r,q,_=selected(args);r["team"],r["opponent_team"]=("KC","BAL") if r["team"]=="BAL" else ("BAL","KC")
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertEqual(t["target_state"],"QUARANTINED_RAW_OFFERED_TEAM_CONFLICT")
        self.assertFalse(t["structurally_usable_raw"] or t["known_zero"] or t["candidate_new_support"])

    def test_offered_accepted_context_conflict_blocks_new_support(self):
        args=fictional();r,q,h=selected(args);h["position"]="WR"
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertTrue(t["known_zero"] and t["offered_accepted_context_conflict"])
        self.assertFalse(t["candidate_new_support"])

    def test_missing_raw_match_is_not_zero_and_orphan_cannot_fill_it(self):
        args=fictional();args[1][0]["player_id"]=identity(2);args[3][0]["player_id"]=identity(2)
        _,rows,orphans,_=run(*args);t=target(rows,identity(2),"pass_att")
        self.assertEqual(t["target_state"],"NO_RAW_STAT_ROW");self.assertFalse(t["known_zero"])
        self.assertEqual(len(orphans),12)

    def test_witness_absence_is_not_DNP_or_new_zero_support(self):
        args=fictional();_,q,_=selected(args);args[2].remove(q["player_id"]);args[2].add(identity(999))
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertTrue(t["known_zero"]);self.assertFalse(t["candidate_new_support"])
        self.assertIn("NO_POSITIVE_FTN_WITNESS",t["unresolved_reasons"])
        self.assertNotIn("DNP",t["qualification_state"])

    def test_authentic_played_zero_candidate_requires_old_unknown(self):
        args=fictional();_,q,_=selected(args);_,rows,_,_=run(*args)
        t=target(rows,q["player_id"],"rush_att")
        self.assertEqual(t["qualification_state"],"CANDIDATE_NEW_ZERO_SUPPORT")
        self.assertEqual(t["old_support"],"OLD_UNKNOWN");self.assertTrue(t["known_zero"])

    def test_existing_played_zero_is_not_counted_as_new_support(self):
        args=fictional();_,q,h=selected(args);h.update(official_physical_event=True,participation_state="played",
            participation_evidence="positive_official_nfl_physical_event")
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertTrue(t["already_supported_zero"]);self.assertFalse(t["candidate_new_support"])

    def test_inconsistent_support_metadata_stays_unresolved(self):
        args=fictional();_,q,h=selected(args);h["participation_state"]="played"
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertEqual(t["old_support"],"UNRESOLVED");self.assertFalse(t["candidate_new_support"])

    def test_missing_accepted_metadata_does_not_invent_support(self):
        args=fictional();_,q,h=selected(args);args[3].remove(h)
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertTrue(t["offered_accepted_context_conflict"]);self.assertEqual(t["old_support"],"UNRESOLVED")
        self.assertFalse(t["candidate_new_support"])

    def test_null_target_is_missing_not_zero(self):
        args=fictional();r,q,_=selected(args);r["carries"]=None
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertEqual(t["target_state"],"MISSING_COMPONENT");self.assertFalse(t["known_zero"])

    def test_invalid_counts_keep_original_nonnegative_integer_support(self):
        args=fictional();r,q,_=selected(args);r["carries"]=-1.5
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertEqual(t["target_state"],"INVALID_COMPONENT");self.assertFalse(t["known_zero"])

    def test_boolean_count_is_invalid(self):
        args=fictional();r,q,_=selected(args);r["carries"]=False
        _,rows,_,_=run(*args);self.assertEqual(target(rows,q["player_id"],"rush_att")["target_state"],"INVALID_COMPONENT")

    def test_nan_is_missing_and_infinity_is_invalid(self):
        for value,state in ((float("nan"),"MISSING_COMPONENT"),(float("inf"),"INVALID_COMPONENT")):
            args=fictional();r,q,_=selected(args);r["carries"]=value
            _,rows,_,_=run(*args);self.assertEqual(target(rows,q["player_id"],"rush_att")["target_state"],state)

    def test_signed_yardage_stays_legal(self):
        args=fictional();r,q,_=selected(args);r["rushing_yards"]=-7
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_yd")
        self.assertEqual(t["target_state"],"KNOWN_NONZERO");self.assertFalse(t["known_zero"])

    def test_combined_signed_cancellation_is_separate_derived_zero(self):
        args=fictional();r,q,_=selected(args);r.update(rushing_yards=-7,receiving_yards=7)
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_rec_yd")
        self.assertEqual(t["target_state"],"KNOWN_DERIVED_ZERO");self.assertEqual(t["zero_kind"],"SIGNED_CANCELLATION")
        self.assertTrue(t["candidate_new_support"])

    def test_combined_missing_component_is_not_zero(self):
        args=fictional();r,q,_=selected(args);r["receiving_yards"]=None
        _,rows,_,_=run(*args);self.assertEqual(target(rows,q["player_id"],"rush_rec_yd")["target_state"],"MISSING_COMPONENT")

    def test_anytime_event_uses_only_rush_or_receive_counts(self):
        args=fictional();r,q,_=selected(args);r["passing_tds"]=5
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"anytime_td")
        self.assertTrue(t["known_zero"]);self.assertEqual(t["zero_kind"],"BOTH_COMPONENTS_ZERO")

    def test_anytime_positive_and_invalid_counts_are_not_zero(self):
        for value,state in ((1,"KNOWN_DERIVED_NONZERO"),(-1,"INVALID_COMPONENT")):
            args=fictional();r,q,_=selected(args);r["receiving_tds"]=value
            _,rows,_,_=run(*args);t=target(rows,q["player_id"],"anytime_td")
            self.assertEqual(t["target_state"],state);self.assertFalse(t["known_zero"])

    def test_exact_PPR_blocked_for_every_known_player_and_orphan(self):
        _,rows,orphans,report=run(*fictional());packet=[r for r in rows+orphans if r["target"]=="fantasy_ppr"]
        self.assertEqual(len(packet),98);self.assertTrue(all(r["target_state"]=="BLOCKED_EXACT_PPR" for r in packet))
        self.assertTrue(all(not r["candidate_new_support"] and not r["known_zero"] for r in packet))

    def test_all_original_population_roles_are_preserved(self):
        args=fictional();_,rows,_,_=run(*args)
        for q in args[1]:
            for category,(_,roles,_) in original.TARGETS.items():
                t=target(rows,q["player_id"],category)
                self.assertEqual(t["population"]=="PRIMARY_OFFERED",q["position"] in roles)

    def test_unknown_offered_position_is_not_backfilled(self):
        args=fictional();_,q,h=selected(args);q["position"]=None;h["position"]=None
        _,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertEqual(t["population"],"OFFERED_UNKNOWN_POSITION");self.assertFalse(t["candidate_new_support"])

    def test_missing_raw_position_remains_separate_and_not_copied(self):
        args=fictional();r,q,_=selected(args);r["position"]=None
        inventory,rows,_,_=run(*args);t=target(rows,q["player_id"],"rush_att")
        self.assertIsNone(next(x for x in inventory if x["player_id"]==q["player_id"])["position"])
        self.assertTrue(t["candidate_new_support"])

    def test_no_input_is_mutated(self):
        args=fictional();before=copy.deepcopy(args);run(*args);self.assertEqual(args,before)

    def test_public_aggregate_contains_only_counts_and_no_identifiers(self):
        _,_,_,report=run(*fictional());body=json.dumps(report)
        self.assertNotIn(identity(500),body);self.assertNotIn('"player_id"',body)
        self.assertEqual(report["zeros_applied"],0);self.assertFalse(report["accepted_history_source_policy_or_forecasts_changed"])

    def test_original_strict_helper_still_rejects_missing_identity(self):
        import pandas as pd
        with self.assertRaises(original.JoinNotReady):original._context(pd.DataFrame(fictional()[0]),True)

    def test_original_arithmetic_functions_are_called_directly(self):
        with patch.object(original,"_target",wraps=original._target) as arithmetic, \
                patch.object(original,"_old_support",wraps=original._old_support) as support:
            run(*fictional())
        self.assertEqual(arithmetic.call_count,97*12);self.assertEqual(support.call_count,97)
        self.assertTrue(all(call.args[0] is None or call.args[0]["player_id"] is not None for call in arithmetic.call_args_list))

    def test_original_structural_inventory_is_required_without_filters(self):
        args=fictional();prior=structure(*args[:3]);prior[0][0]["team"]="OTHER"
        with self.assertRaisesRegex(ValueError,"structural"):run(*args,prior=prior)

    def test_union_and_coverage_cannot_be_replaced_with_complete_cases(self):
        args=fictional();prior=structure(*args[:3]);prior[1].pop()
        with self.assertRaisesRegex(ValueError,"structural"):run(*args,prior=prior)

    def test_malformed_nonnull_identity_or_context_still_fails(self):
        for key,value in (("player_id","not-an-id"),("season",2023),("opponent_team","OTHER")):
            args=fictional();args[0][0][key]=value
            with self.assertRaises(ValueError):run(*args)

    def test_extra_primitive_or_missing_original_primitive_fails(self):
        args=fictional();args[0][0]["unapproved"]=0
        with self.assertRaises(ValueError):run(*args)

    def test_duplicate_accepted_identity_is_not_selected(self):
        args=fictional();args[3].append(copy.deepcopy(args[3][0]))
        with self.assertRaisesRegex(ValueError,"ambiguous"):run(*args)


class ExecutionChecks(unittest.TestCase):
    def test_unbound_registration_denies_before_reader_imports(self):
        original_import=builtins.__import__
        def controlled(name,*args,**kwargs):
            if name in ("ftn_zero_join","operational_storage","owned_reference_batch"):
                raise AssertionError("source import before bound denial")
            return original_import(name,*args,**kwargs)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"fictional-unbound.json";body=b'{"state":"UNBOUND_TEMPLATE"}';path.write_bytes(body)
            with patch("builtins.__import__",side_effect=controlled), self.assertRaises(ValueError):
                subject.run_audit(path,hashlib.sha256(body).hexdigest())

    def test_duplicate_registration_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"fictional.json";body=b'{"state":"x","state":"y"}';path.write_bytes(body)
            with self.assertRaisesRegex(ValueError,"duplicate"):subject._load_spec(path,hashlib.sha256(body).hexdigest())

    def test_sequential_guard_keeps_fail_closed_RSS_and_light_parent(self):
        path=Path(__file__).resolve().parents[1]/"tools/raw_orphan_zero_audit_execute_v2.py"
        spec=importlib.util.spec_from_file_location("fictional_zero_guard",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch.object(module,"process_usage",side_effect=RuntimeError("fictional missing PID")):
            with self.assertRaises(RuntimeError):module.required_usage([{"pid":999999,"start_ticks":1}])
        import sys
        with patch.dict(sys.modules,{"pandas":object()}),self.assertRaises(RuntimeError):module.require_light_supervisor()
        self.assertEqual(module.LIMITS["RSS_stop_bytes"],251658240)
        self.assertEqual(module.LIMITS["combined_CPU_stop_seconds"],54)


if __name__=="__main__":unittest.main()
