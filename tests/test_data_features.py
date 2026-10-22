import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab.data import STAT_MAP, TARGETS, _download, _require, fetch_cached_json, load_history
from nfl_lab.features import build_features


def history_fixture():
    rows = []
    for week, value in enumerate([10.0, 20.0, np.nan, 40.0, 50.0], 1):
        date = pd.Timestamp("2023-09-01", tz="UTC") + pd.Timedelta(days=8 * week)
        for player, team, opponent, amount in [("p", "A", "B", value), ("q", "B", "A", value * 2)]:
            row = {"season": 2023, "week": week, "game_id": f"g{week}", "player_id": player,
                   "player_name": player, "position": "RB", "team": team, "opponent": opponent,
                   "kickoff_utc": date, "participation_state": "unknown" if week == 3 else "played"}
            row.update({target: amount for target in TARGETS})
            row.update({"rec_tgt": amount / 2, "rush_td": 0.0, "rec_td": 0.0})
            rows.append(row)
    return pd.DataFrame(rows)


def test_current_and_future_outcomes_do_not_change_any_prior_feature():
    history = history_fixture()
    initial = build_features(history)
    altered = history.copy()
    altered.loc[altered.week.ge(4), list(TARGETS) + ["rec_tgt"]] = 99999.0
    rebuilt = build_features(altered)
    columns = [c for c in initial if c.startswith("f_")]
    pd.testing.assert_frame_equal(initial.loc[initial.week.le(4), columns], rebuilt.loc[rebuilt.week.le(4), columns])
    assert (initial.feature_max_source_available_utc.dropna() < initial.cutoff_utc[initial.feature_max_source_available_utc.notna()]).all()


def test_unknown_games_consume_window_and_missing_values_are_not_zero():
    featured = build_features(history_fixture())
    row = featured[(featured.week == 5) & (featured.player_id == "p")].iloc[0]
    # Last three eligible observations: 20, missing, 40. The missing week is not skipped.
    assert row.f_player_rush_yd_mean3 == 30
    assert row.f_player_rush_yd_n3 == 2
    assert row.f_player_games_prior == 4
    assert row.f_player_known_participation_n8 == 3


def test_conservative_lag_and_explicit_earlier_cutoff():
    h = history_fixture().iloc[:4].copy()
    h.loc[h.week.eq(2), "kickoff_utc"] = h.loc[h.week.eq(1), "kickoff_utc"].iloc[0] + pd.Timedelta(days=6)
    f = build_features(h)
    assert f.loc[f.week.eq(2), "f_player_games_prior"].eq(0).all()
    h.loc[h.week.eq(2), "kickoff_utc"] += pd.Timedelta(days=2)
    h["cutoff_utc"] = h.kickoff_utc - pd.Timedelta(days=2)
    assert build_features(h).loc[h.week.eq(2), "f_player_games_prior"].eq(0).all()


def test_cold_start_zero_exposure_and_signed_yards():
    h = history_fixture()
    h.loc[h.week.eq(1), "rush_yd"] = -3
    h.loc[h.week.eq(1), "rush_att"] = 0
    f = build_features(h)
    assert f.loc[f.week.eq(1), "f_player_rush_yd_mean3"].isna().all()
    assert f.loc[f.week.eq(1), "f_player_rush_yd_n3"].eq(0).all()
    assert f.loc[f.week.eq(2), "f_player_rush_yd_mean3"].eq(-3).all()
    assert f.loc[f.week.eq(2), "f_player_rush_ypa3"].isna().all()


def test_missing_outcomes_and_original_index_preserved():
    h = history_fixture().set_index(pd.Index(range(100, 110)))
    f = build_features(h)
    pd.testing.assert_series_equal(h.rush_yd, f.rush_yd)
    pd.testing.assert_series_equal(h.participation_state, f.participation_state)
    assert f.index.equals(h.index)


def test_append_future_rows_with_partial_optional_clocks():
    h = history_fixture()
    h["outcome_available_utc"] = h.kickoff_utc + pd.Timedelta(days=7)
    future = h.iloc[[0]].copy()
    future["game_id"] = "future"
    future["kickoff_utc"] = h.kickoff_utc.max() + pd.Timedelta(days=10)
    future["cutoff_utc"] = future.kickoff_utc - pd.Timedelta(days=1)
    future["outcome_available_utc"] = pd.NaT
    future[list(TARGETS)] = np.nan
    future["participation_state"] = "unknown"
    appended = pd.concat([h, future], ignore_index=True)
    f = build_features(appended)
    assert f.iloc[-1].f_player_rush_yd_mean3 == 45
    assert f.iloc[-1].cutoff_utc == future.cutoff_utc.iloc[0]


def test_opponent_adjustment_has_no_future_dependency():
    h = history_fixture()
    a = build_features(h)
    h.loc[h.week.eq(5), "pass_yd"] *= 10
    b = build_features(h)
    cols = [c for c in a if "adjusted" in c]
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_schema_and_duplicate_id_fail_closed():
    with pytest.raises(ValueError, match="schema missing"):
        _require(pd.DataFrame({"x": []}), {"player_id"}, "source")
    h = history_fixture()
    with pytest.raises(ValueError, match="duplicate player/game"):
        build_features(pd.concat([h, h.iloc[:1]], ignore_index=True))
    h["cutoff_utc"] = h.kickoff_utc + pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match="cutoff"):
        build_features(h)


def test_roster_missingness_and_explicit_dnp_source_adapter(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame([{"season": 2023, "week": 1, "game_id": "2023_01_A_B", "gameday": "2023-09-10",
                   "gametime": "13:00", "home_team": "B", "away_team": "A"}]).to_csv(raw / "schedules.csv", index=False)
    pd.DataFrame({"gsis_id": ["zero", "missing", "inactive", "snap"], "pfr_id": ["z", "m", "i", "s"]}).to_parquet(raw / "players.parquet")
    roster = pd.DataFrame([{"season": 2023, "week": 1, "team": "A", "gsis_id": p,
                            "full_name": p, "position": "WR", "status": status}
                           for p, status in [("zero", "ACT"), ("missing", "ACT"), ("inactive", "INA"), ("snap", "ACT")]])
    roster.to_parquet(raw / "roster_weekly_2023.parquet")
    stats = {"season": 2023, "week": 1, "recent_team": "A", "player_id": "zero",
             "player_display_name": "zero", "position": "WR", **{k: 0.0 for k in STAT_MAP}}
    pd.DataFrame([stats]).to_parquet(raw / "player_stats_2023.parquet")
    pd.DataFrame([{"game_id": "2023_01_A_B", "pfr_player_id": "s", "player": "snap", "team": "A", "position": "WR",
                   "offense_snaps": 5.0, "defense_snaps": 0.0, "st_snaps": 0.0}]).to_parquet(raw / "snap_counts_2023.parquet")
    h = load_history(tmp_path, [2023]).set_index("player_id")
    assert h.loc["zero", "participation_state"] == "played"
    assert h.loc["zero", "rec"] == 0
    assert h.loc["missing", "participation_state"] == "unknown"
    assert np.isnan(h.loc["missing", "rec"])
    assert h.loc["inactive", "participation_state"] == "DNP"
    assert np.isnan(h.loc["inactive", "rec"])
    assert h.loc["snap", "participation_state"] == "played"
    assert np.isnan(h.loc["snap", "rec"])
    assert h.fantasy_ppr.isna().all()
    modern = pd.read_parquet(raw / "player_stats_2023.parquet").rename(columns={"recent_team": "team", "interceptions": "passing_interceptions"})
    modern.to_parquet(raw / "stats_player_week_2023.parquet")
    current = load_history(tmp_path, [2023]).set_index("player_id")
    pd.testing.assert_series_equal(current.pass_int, h.pass_int)


def test_source_cache_restart_uses_hash_without_network(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    path = raw / "snapshot.json"
    path.write_text('{"ok":true}')
    import hashlib
    receipt = {"url": "https://example.org/snapshot", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "retrieved_utc": "2023-01-01T00:00:00Z", "status": "acquired"}
    (raw / "snapshot.json.receipt.json").write_text(json.dumps(receipt))
    def unavailable(*args, **kwargs):
        raise AssertionError("cache restart unexpectedly touched network")
    monkeypatch.setattr("nfl_lab.data.requests.get", unavailable)
    decoded, actual = fetch_cached_json(tmp_path, "snapshot.json", receipt["url"])
    assert decoded == {"ok": True}
    assert actual["cache_reused"] is True
    assert actual["retrieved_utc"] == receipt["retrieved_utc"]
    with pytest.raises(ValueError, match="filename"):
        fetch_cached_json(tmp_path, "../escape.json", receipt["url"])
