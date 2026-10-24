"""Eight new fictional replay timing/compatibility methods; no old test imports."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from nfl_lab.dynamic_opportunity_history import LANE, build_offer_windows as strict_v1_windows
from nfl_lab.dynamic_opportunity_history_replay_v2 import (
    REPLAY_LANE, VERSION, build_historical_offer_windows, build_recorded_proxy_panel,
)
from nfl_lab.state import digest, utc


def fixture(task="rush_att"):
    binding = {"availability_lane": LANE, "statistics_lag_days": 7, "season_type": "REG",
               "source_policy_sha256": "1" * 64, "source_manifest_sha256": "2" * 64,
               "calendar_sha256": "3" * 64, "qualification_policy_sha256": "4" * 64,
               "membership_manifest_sha256": "6" * 64, "qualified_history_sha256": "8" * 64,
               "statistics_sha256_by_season": {"2026": "5" * 64}, "calendar_inventory_complete": True}
    calendar = []; credits = []; members = []; players = []
    first = datetime(2026, 8, 1, 17, tzinfo=timezone.utc)
    for index in range(3):
        game_id = f"fictional-replay-game-{index + 1}"; kickoff = (first + timedelta(days=8 * index)).isoformat()
        for team, opponent in (("FICTIONAL_A", "FICTIONAL_B"), ("FICTIONAL_B", "FICTIONAL_A")):
            calendar.append({"game_id": game_id, "season": 2026, "week": index + 1, "season_type": "REG",
                             "team": team, "opponent": opponent, "kickoff_utc": kickoff})
        if index == 2: continue
        for ordinal, (pid, count) in enumerate((("fictional-player", 1), ("fictional-other", 3))):
            credits.append({"source_row_id": f"{game_id}-row-{ordinal}", "source_body_sha256": "5" * 64,
                            "season": 2026, "week": index + 1, "season_type": "REG", "team": "FICTIONAL_A",
                            "player_id": pid, "task": task, "count_support": "explicit_official_count", "count": count})
        members.append({"player_id": "fictional-player", "game_id": game_id, "team": "FICTIONAL_A",
                        "membership_state": "qualified_same_spell", "spell_id": "fictional-spell",
                        "membership_manifest_sha256": "6" * 64})
        players.append({"player_id": "fictional-player", "game_id": game_id, "team": "FICTIONAL_A", "season": 2026,
                        "week": index + 1, "season_type": "REG", "opponent": "FICTIONAL_B", "kickoff_utc": kickoff, "task": task,
                        "source_qualified": True, "participation_state": "played", "count": 1, "count_support": "explicit_value"})
    offer = {**calendar[-2], "offer_id": "fictional-replay-offer", "player_id": "fictional-player", "position": "RB",
             "cutoff_utc": calendar[-2]["kickoff_utc"], "task": task, "f_team_rush_att_mean3": 9,
             "baseline_reference": {"file_sha256": "7" * 64, "row_key": "fictional-source-row"},
             "spell": {"state": "qualified", "membership_manifest_sha256": "6" * 64, "spell_id": "fictional-spell",
                       "player_id": "fictional-player", "team": "FICTIONAL_A", "season": 2026,
                       "boundary": "season_start", "started_utc": "2026-01-01T00:00:00+00:00"}}
    binding["calendar_rows_sha256"] = digest(calendar)
    policy = {"schema_version": VERSION + "-policy", "execution_lane": REPLAY_LANE,
              "source_policy_sha256": binding["source_policy_sha256"],
              "query_cutoff_rule": "cutoff_utc_at_or_before_kickoff_utc",
              "source_availability_rule": "kickoff_plus_7_days_strictly_before_cutoff_utc",
              "original_clocks": "PRESERVE_NO_EDITS_OR_EPSILON", "prospective_issuance": "FORBIDDEN"}
    return binding, calendar, credits, members, players, offer, policy


class HistoricalReplayTests(unittest.TestCase):
    def setUp(self):
        self.b, self.c, self.r, self.m, self.p, self.o, self.policy = fixture()

    def panel(self):
        return build_recorded_proxy_panel(self.c, self.r, task=self.o["task"], source_binding=self.b,
                    asof_utc=self.o["cutoff_utc"], requested_player_ids=["fictional-player"])

    def run_window(self, offers=None, policy=None):
        return build_historical_offer_windows([self.o] if offers is None else offers, self.c, self.m, self.p, self.panel(),
                    task=self.o["task"], source_binding=self.b, replay_policy=self.policy if policy is None else policy)

    def test_01_equal_kickoff_is_explicit_replay_without_clock_edit(self):
        original = deepcopy(self.o); packet = self.run_window(); row = packet["results"][0]
        self.assertEqual(row["state"], "READY_CORE_REQUEST")
        self.assertEqual(row["core_query"]["cutoff_utc"], original["cutoff_utc"])
        self.assertEqual(row["core_query"]["kickoff_utc"], original["kickoff_utc"])
        self.assertEqual((packet["evidence_lane"], packet["query_clock_edits"]), (REPLAY_LANE, 0))
        self.assertEqual(self.o, original)
        old = strict_v1_windows([self.o], self.c, self.m, self.p, self.panel(), task="rush_att", source_binding=self.b)
        self.assertEqual(old["results"][0]["state"], "BASELINE_FALLBACK_REQUIRED")

    def test_02_earlier_cutoff_works_but_after_kickoff_falls_back(self):
        kickoff = self.o["kickoff_utc"]
        self.o["cutoff_utc"] = (utc(kickoff) - timedelta(hours=1)).isoformat()
        self.assertEqual(self.run_window()["results"][0]["state"], "READY_CORE_REQUEST")
        self.o["cutoff_utc"] = (utc(kickoff) + timedelta(seconds=1)).isoformat()
        self.assertEqual(self.run_window()["results"][0]["state"], "BASELINE_FALLBACK_REQUIRED")

    def test_03_no_implicit_or_prospective_replay_policy_is_accepted(self):
        for field, value in (("execution_lane", "PROSPECTIVE"), ("prospective_issuance", "ALLOWED"),
                             ("original_clocks", "SUBTRACT_EPSILON"), ("query_cutoff_rule", "always_allow")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_window(policy={**self.policy, field: value})
        with self.assertRaises(ValueError): self.run_window(policy={})
        with self.assertRaises(ValueError):
            build_historical_offer_windows([self.o], self.c, self.m, self.p, self.panel(), task="rush_att",
                                           source_binding=self.b, replay_policy=None)

    def test_04_source_availability_remains_strict_at_equal_query_clock(self):
        selected = "fictional-replay-game-2"
        history_kickoff = (utc(self.o["cutoff_utc"]) - timedelta(days=7)).isoformat()
        for game in self.c:
            if game["game_id"] == selected: game["kickoff_utc"] = history_kickoff
        self.p[-1]["kickoff_utc"] = history_kickoff
        self.b["calendar_rows_sha256"] = digest(self.c)
        row = self.run_window()["results"][0]
        self.assertEqual(len(row["history"]), 2)
        self.assertFalse(row["slot_audit"][-1]["source_available_before_cutoff"])
        self.assertIsNone(row["history"][-1]["player_count"])
        self.assertIsNone(row["history"][-1]["team_count"])

    def test_05_ambiguous_membership_and_nonmodeled_offers_still_fall_back(self):
        self.m[-1]["membership_state"] = "unknown"
        nonmodeled = deepcopy(self.o); nonmodeled.update(offer_id="fictional-QB-offer", position="QB")
        offers = [self.o, nonmodeled]; packet = self.run_window(offers)
        self.assertEqual(packet["original_offers"], 2)
        self.assertEqual([r["offer"] for r in packet["results"]], offers)
        self.assertTrue(all(r["state"] == "BASELINE_FALLBACK_REQUIRED" and r["evidence_lane"] == REPLAY_LANE for r in packet["results"]))
        self.assertEqual(len(packet["results"][0]["history"]), 2)

    def test_06_policy_and_original_source_lane_are_compatible_exactly(self):
        with self.assertRaises(ValueError): self.run_window(policy={**self.policy, "source_policy_sha256": "f" * 64})
        self.b["availability_lane"] = "original_local_capture_before_cutoff"
        with self.assertRaises(ValueError): self.run_window()

    def test_07_earlier_cutoff_keeps_same_slots_volume_and_static_information(self):
        self.o["cutoff_utc"] = (utc(self.o["kickoff_utc"]) - timedelta(hours=1)).isoformat()
        old = strict_v1_windows([self.o], self.c, self.m, self.p, self.panel(), task="rush_att", source_binding=self.b)["results"][0]
        new = self.run_window()["results"][0]
        for field in ("offer", "history", "slot_audit", "core_query", "volume", "volume_supported", "static_control_request"):
            self.assertEqual(new[field], old[field])

    def test_08_other_identity_guards_and_no_forecast_claim_are_preserved(self):
        row = self.run_window()["results"][0]
        self.assertEqual(row["historical_replay_policy_sha256"], digest(self.policy))
        self.assertEqual(row["forecast_timing_claim"], "AFTER_GAME_RECONSTRUCTION_NOT_ORIGINAL_ISSUANCE")
        self.assertEqual(row["numeric_distribution"], "NONE")
        self.o["week"] = 99
        self.assertEqual(self.run_window()["results"][0]["state"], "BASELINE_FALLBACK_REQUIRED")
