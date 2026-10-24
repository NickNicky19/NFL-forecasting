"""Fictional context contracts only: no NFL rows, parquet reads or labels."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import raw_orphan_context as subject

DIGEST = "f" * 64


def identity(number):
    return f"99-{number:07d}"  # Deliberately fictional identifiers.


def fictional():
    raw = []
    for i in range(67):
        team, opponent = ("BAL", "KC") if i % 2 else ("KC", "BAL")
        raw.append(dict(game_id=subject.GAME, season=2024, week=1, season_type="REG",
            player_id=identity(i + 1) if i < 66 else None, team=team, opponent_team=opponent,
            position=None if i == 0 else "RB"))
    offered = [{"season": 2024, "week": 1, "game_id": subject.GAME,
        "player_id": identity(i + 1), "position": "RB", "team": row["team"],
        "opponent": row["opponent_team"]} for i, row in enumerate(raw[:31])]
    witnesses = {identity(i) for i in range(1, 93)}
    return raw, offered, witnesses


def run(raw, offered, witnesses):
    return subject.partition_context(raw, offered, witnesses, raw_projection_sha256=DIGEST)


class PartitionChecks(unittest.TestCase):
    def test_complete_inventory_and_orphan_are_retained(self):
        raw, offered, witnesses = fictional(); records, union, report = run(raw, offered, witnesses)
        self.assertEqual(len(records), 67); self.assertEqual(len(union), 92)
        self.assertEqual(report["identified_raw_records"], 66)
        self.assertEqual(report["missing_identity_raw_records"], 1)
        self.assertEqual(report["conservative_union_plus_orphan_units"], 93)
        self.assertIsNone(records[-1]["player_id"])
        self.assertEqual(records[-1]["identity_state"], "QUARANTINED_MISSING_PLAYER_ID")
        self.assertFalse(records[-1]["eligible_for_identified_context_view"])
        self.assertTrue(report["inventory_reconciles"])

    def test_every_raw_field_and_order_remain_unchanged(self):
        raw, offered, witnesses = fictional(); records, _, _ = run(raw, offered, witnesses)
        self.assertEqual([{name: row[name] for name in subject.RAW} for row in records], raw)
        self.assertEqual([row["record_ordinal"] for row in records], list(range(67)))

    def test_record_locators_are_projection_local_not_player_ids(self):
        records, _, _ = run(*fictional())
        self.assertEqual(len({r["record_locator"] for r in records}), 67)
        self.assertEqual(records[-1]["record_locator"], DIGEST + ":66")
        self.assertFalse(subject._identity(records[-1]["record_locator"]))

    def test_missing_position_and_missing_id_can_be_different_records(self):
        records, _, report = run(*fictional())
        self.assertTrue(records[0]["position_missing"])
        self.assertFalse(records[-1]["position_missing"])
        self.assertEqual(report["raw_identity_and_position_both_missing_records"], 0)
        self.assertIsNone(records[0]["position"])  # Offered RB never backfills it.

    def test_missing_position_and_missing_id_can_share_a_record(self):
        raw, offered, witnesses = fictional(); raw[0]["position"] = "RB"; raw[-1]["position"] = None
        records, _, report = run(raw, offered, witnesses)
        self.assertTrue(records[-1]["position_missing"])
        self.assertEqual(report["raw_identity_and_position_both_missing_records"], 1)

    def test_duplicate_groups_keep_all_records_without_selecting_one(self):
        raw, offered, witnesses = fictional(); raw[1]["player_id"] = raw[0]["player_id"]
        records, union, report = run(raw, offered, witnesses)
        self.assertEqual(len(records), 67); self.assertEqual(report["duplicate_raw_id_groups"], 1)
        self.assertEqual(report["duplicate_raw_records"], 2)
        self.assertTrue(all(r["identity_state"] == "AMBIGUOUS_DUPLICATE_RAW_ID" for r in records[:2]))
        self.assertTrue(all(not r["eligible_for_identified_context_view"] for r in records[:2]))
        self.assertEqual(next(r for r in union if r["player_id"] == identity(1))["raw_record_count"], 2)

    def test_full_outer_union_keeps_raw_offered_witness_unmatched_records(self):
        raw, offered, witnesses = fictional(); raw[0]["player_id"] = identity(500)
        offered[-1]["player_id"] = identity(600)
        records, union, report = run(raw, offered, witnesses)
        known = {r["player_id"] for r in union}
        self.assertTrue(witnesses <= known)
        self.assertIn(identity(500), known); self.assertIn(identity(600), known)
        self.assertEqual(len(known), 94); self.assertEqual(len(records), 67)
        self.assertEqual(report["conservative_union_plus_orphan_units"], 95)

    def test_orphan_cannot_fill_a_known_players_missing_raw_match(self):
        raw, offered, witnesses = fictional(); raw[0]["player_id"] = identity(500)
        records, union, _ = run(raw, offered, witnesses)
        known = next(r for r in union if r["player_id"] == identity(1))
        self.assertTrue(known["offered"] and known["positive_ftn_witness"])
        self.assertFalse(known["identified_raw_match"])
        self.assertIsNone(records[-1]["player_id"])

    def test_outside_primary_positions_are_not_removed(self):
        raw, offered, witnesses = fictional(); raw[5]["position"] = "K"
        records, _, report = run(raw, offered, witnesses)
        self.assertEqual(records[5]["position"], "K"); self.assertEqual(report["raw_planned_records"], 67)

    def test_identified_raw_offered_team_conflict_is_quarantined_not_repaired(self):
        raw, offered, witnesses = fictional(); raw[0]["team"], raw[0]["opponent_team"] = "BAL", "KC"
        records, union, report = run(raw, offered, witnesses)
        self.assertEqual(records[0]["identity_state"], "QUARANTINED_RAW_OFFERED_TEAM_CONFLICT")
        self.assertTrue(records[0]["offered_team_context_conflict"])
        self.assertFalse(records[0]["eligible_for_identified_context_view"])
        self.assertEqual(report["raw_offered_team_context_conflict_records"], 1)
        self.assertTrue(next(r for r in union if r["player_id"] == identity(1))["raw_offered_team_context_conflict"])
        self.assertFalse(next(r for r in union if r["player_id"] == identity(1))["identified_context_view_match"])
        self.assertEqual(len(records), 67)

    def test_offered_missing_position_stays_unknown(self):
        raw, offered, witnesses = fictional(); offered[0]["position"] = None
        _, _, report = run(raw, offered, witnesses)
        self.assertEqual(report["offered_position_missing_records"], 1)

    def test_public_counts_never_include_identifiers_or_raw_rows(self):
        _, _, report = run(*fictional())
        self.assertIsNone(re.search(r"[0-9]{2}-[0-9]{7}", json.dumps(report)))
        self.assertNotIn("player_id", report); self.assertNotIn("records", report)

    def test_inputs_are_not_mutated(self):
        args = fictional(); before = copy.deepcopy(args); run(*args)
        self.assertEqual(args, before)

    def test_nonnull_malformed_ids_are_rejected_without_repair(self):
        for value in (" 99-0000001", "not-an-id", 1, ""):
            raw, offered, witnesses = fictional(); raw[0]["player_id"] = value
            with self.assertRaises(ValueError): run(raw, offered, witnesses)

    def test_other_required_context_is_still_strict(self):
        for field, value in (("season", None), ("season", 2023), ("week", 2),
                ("season_type", None), ("season_type", "POST"), ("team", "OTHER"),
                ("opponent_team", "OTHER"), ("game_id", "other-game")):
            raw, offered, witnesses = fictional(); raw[0][field] = value
            with self.assertRaises(ValueError): run(raw, offered, witnesses)

    def test_no_extra_primitive_column_can_enter(self):
        raw, offered, witnesses = fictional(); raw[0]["rushing_yards"] = 0
        with self.assertRaises(ValueError): run(raw, offered, witnesses)

    def test_complete_fixed_counts_and_all_witnesses_are_required(self):
        raw, offered, witnesses = fictional()
        for args in ((raw[:-1], offered, witnesses), (raw, offered[:-1], witnesses),
                     (raw, offered, set(sorted(witnesses)[:-1])), (raw * 4, offered, witnesses)):
            with self.assertRaises(ValueError): run(*args)

    def test_ambiguous_or_missing_offered_identity_cannot_be_repaired(self):
        for value in (None, identity(2)):
            raw, offered, witnesses = fictional(); offered[0]["player_id"] = value
            with self.assertRaises(ValueError): run(raw, offered, witnesses)

    def test_orphans_are_charged_beyond_known_union_cap(self):
        known = {identity(i) for i in range(200)}
        self.assertEqual(len(subject._union(known, set(), set(), 0)), 200)
        with self.assertRaises(ValueError): subject._union(known, set(), set(), 1)


class GateChecks(unittest.TestCase):
    def test_unbound_config_refuses_before_any_source_reader_import(self):
        with tempfile.TemporaryDirectory(prefix="fictional-raw-orphan-") as folder:
            path = Path(folder) / "unbound.json"; body = b'{"state":"UNBOUND_TEMPLATE"}'
            path.write_bytes(body)
            with self.assertRaises(ValueError): subject.run_prerequisite(path, hashlib.sha256(body).hexdigest())
        self.assertNotIn("nfl_lab.ftn_zero_join", sys.modules)

    def test_duplicate_json_keys_are_not_accepted(self):
        with tempfile.TemporaryDirectory(prefix="fictional-raw-orphan-") as folder:
            path = Path(folder) / "duplicate.json"; body = b'{"state":"x","state":"y"}'
            path.write_bytes(body)
            with self.assertRaisesRegex(ValueError, "duplicate"): subject._load_spec(path, hashlib.sha256(body).hexdigest())

    def test_new_wrapper_keeps_fail_closed_known_pid_and_light_parent_guards(self):
        path = Path(__file__).resolve().parents[1] / "tools/raw_orphan_context_execute_v1.py"
        spec = importlib.util.spec_from_file_location("fictional_orphan_guard", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with patch.object(module, "process_usage", side_effect=RuntimeError("fictional missing required RSS")):
            with self.assertRaises(RuntimeError): module.required_usage([{"pid": 999999, "start_ticks": 1}])
        with patch.dict(sys.modules, {"pandas": object()}):
            with self.assertRaises(RuntimeError): module.require_light_supervisor()
        self.assertEqual(module.LIMITS["RSS_stop_bytes"], 251658240)
        self.assertEqual(module.LIMITS["combined_CPU_stop_seconds"], 54)


if __name__ == "__main__":
    unittest.main()
