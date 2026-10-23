"""Fictional source qualification and temporal checks, without model fitting."""
import numpy as np
import pandas as pd
import pytest

from nfl_lab import data, features
from nfl_lab.permitted_source_features import physical_event_evidence, qualify_history, query_features
from nfl_lab.rb_readiness import ACTION_FIELDS, SNAP_FIELDS, classify_evidence


def raw_row(player, *, carries=0, yards=0, penalties=0):
    return {**{c: 0. for c in ACTION_FIELDS}, "season": 2026, "week": 1, "team": "A",
            "player_id": player, "carries": carries, "rushing_yards": yards, "penalties": penalties}


def normalized_row(player, *, state="played", yards=0, status="ACT", week=1):
    kickoff = pd.Timestamp("2026-09-13T17:00Z") + pd.Timedelta(days=7 * (week - 1))
    row = {"season": 2026, "week": week, "game_id": f"2026-g{week}", "player_id": player,
           "team": "A", "opponent": "B", "position": "RB", "roster_status": status,
           "kickoff_utc": kickoff, "outcome_available_utc": kickoff + pd.Timedelta(days=7),
           "is_home": True, "participation_state": state, "stats_observed": True}
    row.update({c: 0. for c in data.STAT_MAP.values()})
    row.update({c: np.nan for c in SNAP_FIELDS})
    row.update({"rush_yd": yards, "rush_rec_yd": yards, "anytime_td": 0., "fantasy_ppr": np.nan})
    row.update({"team_stat_" + c: 20. for c in features.TEAM_STATS})
    return row


def test_penalties_all_zero_and_inactive_do_not_establish_participation():
    raw = pd.DataFrame([raw_row("positive", carries=1), raw_row("negative-yard", yards=-1),
                        raw_row("penalty", penalties=1), raw_row("zero")])
    assert physical_event_evidence(raw).tolist() == [True, True, False, False]
    history = pd.DataFrame([normalized_row(pid, status="INA" if pid == "zero" else "ACT") for pid in raw.player_id])
    out, proof = qualify_history(history, raw)
    assert len(out) == 4
    assert out.participation_state.tolist() == ["played", "played", "unknown", "unknown"]
    assert out.rush_att.iloc[:2].eq(0).all()  # separately supported played zeros
    assert out.rush_att.iloc[2:].isna().all()
    assert proof["confirmed_dnp"] == 0


def test_absent_stat_row_and_snap_values_cannot_become_supported_zero():
    history = pd.DataFrame([normalized_row("absent")])
    raw = pd.DataFrame([raw_row("other", carries=2)])
    out, _ = qualify_history(history, raw)
    assert out.iloc[0].participation_state == "unknown"
    assert pd.isna(out.iloc[0].rush_att)
    history["offense_snaps"] = 1
    with pytest.raises(ValueError, match="forbidden snap"):
        qualify_history(history, raw)


def test_original_rb_gate_preserves_snap_playing_with_missing_carries():
    row = {c: np.nan for c in (*ACTION_FIELDS, *SNAP_FIELDS)}
    row["st_snaps"] = 3
    result = classify_evidence(pd.DataFrame([row])).iloc[0]
    assert result.played_supported
    assert result.carry_state == "unknown"


def test_clean_query_unknown_slots_seven_day_lag_and_cold_identity():
    history = pd.DataFrame([normalized_row("00-0000001", week=w, yards=y) for w, y in [(1, 10), (2, 999), (3, 30)]])
    history.loc[1, "participation_state"] = "unknown"
    history.loc[1, list(data.STAT_MAP.values())] = np.nan
    history.loc[1, "rush_rec_yd"] = np.nan
    history.loc[1, "anytime_td"] = np.nan
    queries = pd.DataFrame([{"season": 2026, "week": 6, "game_id": "original-id", "player_id": "sleeper:1",
        "canonical_player_id": canonical, "team": "A", "opponent": "B", "position": "RB", "is_home": True,
        "kickoff_utc": pd.Timestamp("2026-10-18T17:00Z"), "cutoff_utc": pd.Timestamp("2026-10-18T10:00Z"),
        "outcome_available_utc": pd.Timestamp("2026-10-25T17:00Z"),
        "original_board_generated_at": pd.Timestamp("2026-10-18T09:00Z"),
        "calendar_generated_at": pd.Timestamp("2026-10-17T09:00Z")}
        for canonical in ["00-0000001"]])
    result = query_features(history, queries).iloc[0]
    assert result.f_player_games_prior == 3
    assert result.f_player_rush_yd_n3 == 2
    assert result.f_player_rush_yd_mean3 == 20
    assert result.f_player_offense_snaps_n3 == 0
    assert pd.isna(result.f_player_offense_snaps_mean3)
    queries["canonical_player_id"] = None
    assert query_features(history, queries).iloc[0].f_player_games_prior == 0
    history.loc[0, "week"] = 6
    with pytest.raises(ValueError, match="future/target"):
        query_features(history, queries)
