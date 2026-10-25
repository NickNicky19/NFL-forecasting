"""Fictional source metadata and counts only; no NFL values or filter runs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from nfl_lab.dynamic_opportunity_history import LANE, build_offer_windows, build_recorded_proxy_panel
from nfl_lab.state import digest, utc


def fixture(task="rush_att"):
    binding = {"availability_lane": LANE, "statistics_lag_days": 7, "season_type": "REG",
               "source_policy_sha256": "1" * 64, "source_manifest_sha256": "2" * 64,
               "calendar_sha256": "3" * 64, "qualification_policy_sha256": "4" * 64,
               "membership_manifest_sha256": "6" * 64, "qualified_history_sha256": "8" * 64,
               "statistics_sha256_by_season": {"2026": "5" * 64}, "calendar_inventory_complete": True}
    calendar = []; credits = []; members = []; players = []
    first = datetime(2026, 8, 1, 17, tzinfo=timezone.utc)
    for index in range(11):
        game_id = f"fictional-game-{index + 1}"
        kickoff = (first + timedelta(days=8 * index)).isoformat()
        for own, other in (("FICTIONAL_A", "FICTIONAL_B"), ("FICTIONAL_B", "FICTIONAL_A")):
            calendar.append({"game_id": game_id, "season": 2026, "week": index + 1, "season_type": "REG",
                             "team": own, "opponent": other, "kickoff_utc": kickoff})
        if index == 10: continue
        for ordinal, (pid, count, support) in enumerate((("fictional-player", 1, "explicit_official_count"),
                    ("fictional-quarterback", 2, "explicit_official_count"), (None, 3, "explicit_official_count"),
                    ("fictional-missing-field", None, "missing"))):
            credits.append({"source_row_id": f"{game_id}-row-{ordinal}", "source_body_sha256": "5" * 64,
                            "season": 2026, "week": index + 1, "season_type": "REG", "team": "FICTIONAL_A",
                            "player_id": pid, "task": task, "count_support": support, "count": count})
        members.append({"player_id": "fictional-player", "game_id": game_id, "team": "FICTIONAL_A",
                        "membership_state": "qualified_same_spell", "spell_id": "fictional-spell",
                        "membership_manifest_sha256": "6" * 64})
        players.append({"player_id": "fictional-player", "game_id": game_id, "team": "FICTIONAL_A", "season": 2026,
                        "opponent": "FICTIONAL_B", "kickoff_utc": kickoff, "task": task,
                        "source_qualified": True, "participation_state": "played", "count": 1, "count_support": "explicit_value"})
    final = calendar[-2]
    offer = {**final, "offer_id": "fictional-original-offer", "player_id": "fictional-player", "position": "RB",
             "cutoff_utc": (utc(final["kickoff_utc"]) - timedelta(hours=1)).isoformat(), "task": task,
             "f_team_rush_att_mean3": 10.5, "baseline_reference": {"file_sha256": "7" * 64, "row_key": "fictional-row"},
             "spell": {"state": "qualified", "membership_manifest_sha256": "6" * 64, "spell_id": "fictional-spell",
                       "player_id": "fictional-player", "team": "FICTIONAL_A", "season": 2026,
                       "boundary": "season_start", "started_utc": "2026-01-01T00:00:00+00:00"}}
    binding["calendar_rows_sha256"] = digest(calendar)
    return binding, calendar, credits, members, players, offer


class NoCountRead(dict):
    def get(self, key, *args):
        if key in ("count", "count_support"): raise AssertionError("post-cutoff primitive accessed")
        return super().get(key, *args)


class DynamicHistoryTests(unittest.TestCase):
    def setUp(self):
        self.b, self.c, self.r, self.m, self.p, self.o = fixture()

    def panel(self, task=None, rows=None):
        return build_recorded_proxy_panel(self.c, self.r if rows is None else rows, task=task or self.o["task"],
                    source_binding=self.b, asof_utc=self.o["cutoff_utc"], requested_player_ids=["fictional-player"])

    def window(self, offers=None, panel=None):
        return build_offer_windows([self.o] if offers is None else offers, self.c, self.m, self.p,
                    self.panel() if panel is None else panel, task=self.o["task"], source_binding=self.b)

    def test_01_all_position_recorded_proxy_is_explicitly_partial(self):
        group = self.panel()["groups"][0]
        self.assertEqual(group["count"], 6)
        self.assertEqual((group["row_count"], group["explicit_count_rows"], group["missing_count_rows"]), (4, 3, 1))
        self.assertEqual((group["orphan_player_rows"], group["orphan_player_credit_sum"]), (1, 3))
        self.assertEqual(group["outside_requested_player_credit_sum"], 2)
        self.assertFalse(group["all_nfl_credits_complete"])

    def test_02_empty_and_all_missing_are_unavailable_not_zero(self):
        for rows in ([], [{**r, "count_support": "missing", "count": None} for r in self.r]):
            with self.subTest(empty=not rows):
                group = self.panel(rows=rows)["groups"][0]
                self.assertIsNone(group["count"])
                self.assertEqual(group["state"], "UNAVAILABLE")

    def test_03_at_least_one_explicit_zero_is_a_supported_proxy_zero(self):
        rows = [{**self.r[0], "count": 0}]
        self.assertEqual(self.panel(rows=rows)["groups"][0]["count"], 0)

    def test_04_invalid_noninteger_negative_or_boolean_counts_block_proxy(self):
        for invalid in (-1, .5, True, float("inf")):
            with self.subTest(value=invalid):
                group = self.panel(rows=[{**self.r[0], "count": invalid}])["groups"][0]
                self.assertIsNone(group["count"])
                self.assertEqual(group["invalid_count_rows"], 1)

    def test_05_duplicate_rows_never_choose_a_convenient_copy(self):
        rows = [deepcopy(self.r[0]), {**self.r[0], "source_row_id": "distinct-physical-row"}]
        self.assertEqual(self.panel(rows=rows)["groups"][0]["duplicate_rows"], 1)
        self.assertIsNone(self.panel(rows=rows)["groups"][0]["count"])
        rows = [deepcopy(self.r[0]), {**self.r[0], "team": "FICTIONAL_B", "player_id": "fictional-other-side"}]
        groups = self.panel(rows=rows)["groups"][:2]
        self.assertTrue(all(g["duplicate_rows"] == 1 and g["count"] is None for g in groups))

    def test_06_unmapped_source_identity_stays_an_orphan_receipt(self):
        row = {**self.r[0], "team": "UNMAPPED_TEAM"}
        panel = self.panel(rows=[row])
        self.assertEqual(panel["unassigned_rows"][0]["reason"], "unmapped_team_game")
        self.assertTrue(all(g["count"] is None for g in panel["groups"]))
        for versions, source_hash in (({}, None), ({"2025": "5" * 64}, None), ({"2026": "5" * 64}, None),
                                      ({"2026": "5" * 64}, "not-a-sha256")):
            with self.subTest(versions=versions, source_hash=source_hash):
                b = {**self.b, "statistics_sha256_by_season": versions}
                r = {**self.r[0]}; r.pop("source_body_sha256")
                if source_hash is not None: r["source_body_sha256"] = source_hash
                with self.assertRaises(ValueError):
                    build_recorded_proxy_panel(self.c, [r], task="rush_att", source_binding=b,
                                               asof_utc=self.o["cutoff_utc"])

    def test_07_not_yet_available_credit_values_are_not_accessed(self):
        future = {**self.r[0], "week": 11, "source_row_id": "fictional-future-pointer"}
        panel = self.panel(rows=[NoCountRead(future)])
        self.assertEqual(panel["groups"][-2]["reason"], "source_not_available")

    def test_08_latest_eight_slots_keep_unknown_DNP_and_missing(self):
        self.p[-2]["participation_state"] = "unknown"
        self.p[-3]["participation_state"] = "DNP"
        self.p[-4]["count"] = None
        result = self.window()["results"][0]
        self.assertEqual(result["state"], "READY_CORE_REQUEST")
        self.assertEqual([s["game_id"] for s in result["history"]], [f"fictional-game-{i}" for i in range(3, 11)])
        states = {s["state"] for s in result["slot_audit"]}
        self.assertTrue({"unknown_participation_no_observation", "confirmed_DNP_no_observation", "missing_player_count_no_observation"} <= states)

    def test_09_post_cutoff_player_counts_are_masked_without_access(self):
        self.o["cutoff_utc"] = (utc(self.p[-1]["kickoff_utc"]) + timedelta(days=7)).isoformat()
        self.p[-1] = NoCountRead(self.p[-1])
        result = self.window()["results"][0]
        self.assertEqual(result["history"][-1]["participation_state"], "unknown")
        self.assertIsNone(result["history"][-1]["player_count"])

    def test_10_verified_team_spell_reset_prevents_older_team_history(self):
        boundary = self.p[-3]["kickoff_utc"]
        self.o["spell"].update(boundary="verified_team_change", started_utc=boundary, spell_id="fictional-new-spell")
        for member in self.m[-3:]: member["spell_id"] = "fictional-new-spell"
        result = self.window()["results"][0]
        self.assertEqual(len(result["history"]), 3)
        self.assertEqual(result["core_query"]["window_origin"], "start_of_season_or_spell")

    def test_11_ambiguous_membership_blocks_fixed_window_without_older_search(self):
        self.m[-2]["membership_state"] = "unknown"
        result = self.window()["results"][0]
        self.assertEqual((result["state"], len(result["history"])), ("BASELINE_FALLBACK_REQUIRED", 8))
        self.assertIn("ambiguous_membership", result["reason"])
        self.o["spell"].update(boundary="season_start", started_utc=self.p[-2]["kickoff_utc"])
        self.assertIn("cannot hide earlier slots", self.window()["results"][0]["reason"])

    def test_12_frozen_seven_day_source_clock_cannot_be_replaced(self):
        self.b["availability_lane"] = "original_local_capture_before_cutoff"
        with self.assertRaises(ValueError): self.panel()
        self.b["availability_lane"] = LANE
        self.c[0]["available_utc"] = self.c[0]["kickoff_utc"]
        with self.assertRaises(ValueError): self.panel()
        b, calendar, rows, _, _, offer = fixture()
        calendar.extend([{**calendar[0], "team": "FICTIONAL_C", "opponent": "FICTIONAL_D"},
                         {**calendar[1], "team": "FICTIONAL_D", "opponent": "FICTIONAL_C"}])
        b["calendar_rows_sha256"] = digest(calendar)
        with self.assertRaisesRegex(ValueError, "exactly two calendar sides"):
            build_recorded_proxy_panel(calendar, rows, task="rush_att", source_binding=b, asof_utc=offer["cutoff_utc"])

    def test_13_all_original_offers_include_nonmodeled_sparse_and_cold(self):
        other = deepcopy(self.o); other.update(offer_id="fictional-nonmodeled", position="QB")
        cold = deepcopy(self.o); cold["offer_id"] = "fictional-cold"
        cold["spell"].update(boundary="verified_cold_start", started_utc=cold["cutoff_utc"])
        sparse = deepcopy(self.o); sparse["offer_id"] = "fictional-unlinked"; sparse.pop("spell")
        offers = [self.o, other, cold, sparse]
        packet = self.window(offers)
        self.assertEqual(packet["original_offers"], 4)
        self.assertEqual([r["offer"] for r in packet["results"]], offers)
        self.assertEqual(packet["results"][1]["state"], "BASELINE_FALLBACK_REQUIRED")
        self.assertEqual(packet["results"][2]["history"], [])
        self.assertEqual(packet["results"][3]["state"], "BASELINE_FALLBACK_REQUIRED")

    def test_14_player_exceeds_proxy_is_not_clipped(self):
        self.p[-1]["count"] = 7
        result = self.window()["results"][0]
        self.assertEqual(result["state"], "BASELINE_FALLBACK_REQUIRED")
        self.assertEqual(result["history"][-1]["player_count"], 7)
        self.assertEqual(result["history"][-1]["team_count"], 6)
        self.p[-1]["count"] = 1
        self.p[-1]["week"] = 99
        self.assertIn("player/calendar identity mismatch", self.window()["results"][0]["reason"])
        self.p[-1].pop("week")
        self.o["week"] = 99
        self.assertIn("query/calendar identity mismatch", self.window()["results"][0]["reason"])

    def test_15_supported_played_zero_remains_distinct_from_missing(self):
        self.p[-1]["count"] = 0
        result = self.window()["results"][0]
        self.assertEqual(result["slot_audit"][-1]["state"], "supported_played_zero")
        self.p[-1]["count_support"] = "unqualified_missing"
        self.assertEqual(self.window()["results"][0]["slot_audit"][-1]["state"], "missing_player_count_no_observation")

    def test_16_original_carry_volume_is_unchanged_including_zero(self):
        for volume in (10.5, 0):
            self.o["f_team_rush_att_mean3"] = volume
            result = self.window()["results"][0]
            self.assertEqual((result["volume"], result["volume_supported"]), (volume, True))
        self.o["f_team_rush_att_mean3"] = None
        self.assertEqual(self.window()["results"][0]["state"], "BASELINE_FALLBACK_REQUIRED")

    def test_17_target_volume_is_named_proxy_not_attempt_normalization(self):
        self.b, self.c, self.r, self.m, self.p, self.o = fixture("rec_tgt")
        self.o["f_team_pass_att_mean3"] = 999
        for row in self.r:
            if row["week"] == 10: row.update(count_support="missing", count=None)
        result = self.window()["results"][0]
        self.assertEqual(result["volume"], 6)
        self.assertEqual((result["volume_audit"]["selected_slots"], result["volume_audit"]["supported_slots"], result["volume_audit"]["missing_slots"]), (3, 2, 1))
        self.assertFalse(result["volume_audit"]["normalized_to_attempts"])

    def test_18_static_control_reuses_exact_information_without_forecast(self):
        original = deepcopy(self.o); result = self.window()["results"][0]
        static = result["static_control_request"]
        self.assertEqual(static["history_sha256"], digest(result["history"]))
        self.assertEqual(static["volume"], result["volume"])
        self.assertFalse(static["new_fit"])
        self.assertEqual(static["numeric_distribution"], "NONE")
        self.assertEqual(self.o, original)
        self.assertFalse(self.window()["joint_allocation"])
        with self.assertRaises(ValueError): self.window([self.o, self.o])
