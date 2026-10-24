"""Bounded fictional adapter checks: no real target outcomes or model fits."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from nfl_lab.website_cdf_features import build_query, player_stats, supported


def fictional():
    cutoff = "2026-10-18T10:48:59Z"
    dates = ["2026-09-13T17:00Z", "2026-09-20T17:00Z", "2026-09-27T17:00Z",
             "2026-10-04T17:00Z", "2026-10-11T17:00Z", "2026-10-18T17:00Z"]
    schedule = [{"w": w, "id": f"g{w}", "home": "A", "away": "B", "kickoff": date}
                for w, date in enumerate(dates, 1)]
    logs = [{"w": w, "opp": "B", "snp": 20, "st": {"pass_yd": value, "pass_att": 10}}
            for w, value in [(1, 10), (2, 20), (4, 40), (5, 999)]]
    player = {"id": "1", "game_id": "g6", "pos": "QB", "team": "A", "opp": "B", "log": logs,
              "props": [{"key": "pass_yd", "proj": 30., "adj": 31.}], "actual": 999999}
    baseline = {"captured_at": cutoff, "rows": [{"season": 2026, "week": 6, "player_id": "1", "game_id": "g6",
                 "position": "QB", "team": "A", "kickoff": dates[-1], "category": "pass_yd",
                 "raw_projection": 30., "adjusted_projection": 31.}]}
    board = {"season": 2026, "week": 6, "generated_at": "2026-10-18T10:48:52Z", "players": [player]}
    calendar = {"season": 2026, "generated_at": "2026-10-18T10:18:39Z", "schedule": schedule}
    history = {"season": 2026, "week": 6, "inputs_observed_at": "2026-10-14T00:53:43Z", "weeks": {},
               "game_status": {}, "week_data": {"target_outcomes": 999999}}
    for game in schedule[:-1]:
        w = game["w"]
        history["weeks"][str(w)] = {} if w == 3 else {"1": {"team": "A", "opp": "B", "stats": {"gp": 1}}}
        history["game_status"][f"2026_{w:02d}"] = {
            "collected_at": "2026-10-14T00:54:00Z", "games": {game["id"]: {
                "completed": True, "state": "post", "detail": "Final", "kickoff": game["kickoff"]}}}
    return baseline, board, calendar, history


def test_unknown_slot_consumes_window_week5_lag_and_all_context_missing():
    query, opportunities, trail, report = build_query(*fictional())
    row = query.iloc[0]
    assert row.f_player_pass_yd_mean3 == 30  # 20, unknown, 40
    assert row.f_player_pass_yd_n3 == 2
    assert row.f_player_games_prior == 4
    assert row.f_player_play_rate8 == 1  # unknown slot is not DNP
    assert row.f_player_known_participation_n8 == 3
    assert row.f_rest_days == 7
    assert row.f_is_home == 1
    assert query.filter(regex="^f_(team|opp)_").isna().all(axis=None)
    assert trail.loc[trail.week.eq(5), "eligible_at_query"].eq(False).all()
    assert opportunities.iloc[0].website_point == 31.
    assert opportunities.iloc[0].raw_point == 30.
    assert report["target_outcomes_loaded"] is False


def test_display_zero_and_sparse_missing_remain_unknown_signed_values_valid():
    stats, trail = player_stats({"st": {"rec_yd": -3, "rec_tgt": 2}, "s": [0] * 8, "snp": None}, None)
    assert stats["rec_yd"] == -3
    assert np.isnan(stats["rec"])
    assert np.isnan(stats["rush_rec_yd"])
    assert np.isnan(stats["anytime_td"])
    assert trail["rec_yd"]["lane"] == "original_board_log"
    explicit, _ = player_stats(None, {"stats": {"rush_yd": 0, "rec_yd": -3, "rush_td": 0, "rec_td": 0}})
    assert explicit["rush_rec_yd"] == -3
    assert explicit["anytime_td"] == 0
    for invalid in [True, -1, 2.5, float("inf"), None]:
        assert np.isnan(supported(invalid, "rec_tgt"))


def test_target_outcomes_and_future_status_are_not_feature_inputs():
    inputs = fictional()
    before = build_query(*inputs)[0]
    mutated = deepcopy(inputs)
    mutated[1]["players"][0]["actual"] = -999999
    mutated[3]["weeks"]["6"] = {"1": {"stats": {"pass_yd": 999999}}}
    mutated[3]["game_status"]["2026_06"] = {"target_final": "never examined"}
    mutated[3]["week_data"] = {"actual": "never examined"}
    after = build_query(*mutated)[0]
    pd.testing.assert_frame_equal(before, after)


def test_scheduled_bye_does_not_consume_player_slot():
    inputs = fictional()
    inputs[2]["schedule"] = [g for g in inputs[2]["schedule"] if g["w"] != 3]
    query = build_query(*inputs)[0]
    assert query.iloc[0].f_player_games_prior == 3
    assert query.iloc[0].f_player_pass_yd_mean3 == pytest.approx(70 / 3)


def test_trade_with_unknown_membership_masks_player_features_for_role_prior():
    inputs = fictional()
    # Week 1 is an observed old-team game; week 3 has no team evidence.
    inputs[2]["schedule"][0]["home"] = "C"
    inputs[3]["weeks"]["1"]["1"]["team"] = "C"
    row = build_query(*inputs)[0].iloc[0]
    assert row.history_trade_membership_ambiguous
    assert row.filter(regex="^f_player_").isna().all()


def test_exact_identity_extension_keeps_crossseason_windows_and_no_old_query_rows():
    inputs = fictional()
    kickoff = pd.Timestamp("2025-12-20T17:00Z")
    old = pd.DataFrame([{"season": 2025, "week": 6, "game_id": "old-g6", "player_id": "sleeper:1",
                         "team": "C", "opponent": "D", "position": "QB", "kickoff_utc": kickoff,
                         "outcome_available_utc": kickoff + pd.Timedelta(days=7), "is_home": 1,
                         "participation_state": "played", "pass_yd": 60., "pass_att": 10.}])
    query, _, _, report = build_query(*inputs, old_history=old, identity={"sleeper:1": "00-0000001"})
    assert len(query) == 1 and query.iloc[0].season == 2026
    assert query.iloc[0].f_player_pass_yd_mean8 == 32.5
    assert query.iloc[0].f_player_pass_yd_n8 == 4
    assert query.iloc[0].f_player_games_prior == 5
    assert not query.iloc[0].history8_truncated
    assert report["historical_extension_rows"] == 1


def test_wrong_kickoff_and_late_source_clock_fail_closed():
    inputs = fictional()
    inputs[0]["rows"][0]["kickoff"] = "2026-10-18T18:00Z"
    with pytest.raises(ValueError, match="kickoff/cutoff"):
        build_query(*inputs)
    inputs = fictional()
    inputs[1]["generated_at"] = inputs[0]["captured_at"]
    with pytest.raises(ValueError, match="source clock"):
        build_query(*inputs)
