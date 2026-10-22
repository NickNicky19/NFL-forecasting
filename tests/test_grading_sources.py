import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab.grading_sources import cached_nflverse_outcome, load_cached_grading_context


PLAYER = "00-0030001"


def fixtures():
    row = {"player_id": PLAYER, "game_id": "2026_06_A_B", "season": 2026, "week": 6,
           "team": "A", "opponent": "B", "is_home": False, "kickoff_utc": pd.Timestamp("2026-10-18T17:00:00Z"),
           "participation_state": "played", "participation_evidence": "weekly_stat_event", "stats_observed": True,
           "rec": 0.0, "rec_yd": 0.0, "rush_yd": -2.0, "rush_rec_yd": -2.0,
           "anytime_td": 0.0, "fantasy_ppr": np.nan}
    context = {"history": pd.DataFrame([row]), "identity": pd.DataFrame([
        {"player_id": PLAYER, "sleeper_id": "123", "identity_status": "source_exact_binding"}]),
        "receipts": {"stats_player_week_2026.parquet": {"sha256": "a" * 64,
            "retrieved_utc": "2026-10-20T12:00:00Z", "status": "acquired"}}, "verified_utc": "2026-10-22T12:00:00Z"}
    forecast = {"player_id": PLAYER, "sleeper_id": "123", "game_id": "espn:999", "season": 2026,
                "week": 6, "team": "A", "opponent": "B", "kickoff_utc": "2026-10-18T17:00:00Z", "target": "rec"}
    game = {"game_id": "espn:999", "kickoff_utc": "2026-10-18T17:00:00Z", "home": "B", "away": "A", "final": True}
    return context, forecast, game


def test_exact_provider_tuple_accepts_recorded_played_zero_and_preserves_ids():
    context, forecast, game = fixtures()
    row = cached_nflverse_outcome(context, forecast, game, {"sha256": "status-hash"})
    assert row["actual"] == 0 and row["participation_state"] == "played"
    assert row["game_id"] == "espn:999" and row["canonical_game_id"] == "2026_06_A_B"
    assert row["player_id"] == PLAYER and row["canonical_player_id"] == PLAYER
    assert row["source_timestamp"] is None and row["status_sha256"] == "status-hash"
    assert row["observed_at"] == "2026-10-20T12:00:00Z"
    assert "unknown_provider_publication_order" in row["correction_order"]


def test_missing_dnp_and_snap_only_never_become_zero():
    context, forecast, game = fixtures()
    context["history"].loc[0, "rec"] = np.nan
    assert cached_nflverse_outcome(context, forecast, game)["actual"] is None
    context["history"].loc[0, "rec"] = 0.0
    context["history"].loc[0, "participation_state"] = "DNP"
    row = cached_nflverse_outcome(context, forecast, game)
    assert row["actual"] is None and row["participation_state"] == "DNP"
    context["history"].loc[0, "participation_state"] = "played"
    context["history"].loc[0, "stats_observed"] = False
    assert cached_nflverse_outcome(context, forecast, game)["gap_reason"] == "played_but_statistics_missing"


def test_frozen_sleeper_namespace_requires_unique_authenticated_exact_binding():
    context, forecast, game = fixtures()
    forecast["player_id"] = "sleeper:123"
    row = cached_nflverse_outcome(context, forecast, game)
    assert row["actual"] == 0 and row["player_id"] == "sleeper:123" and row["canonical_player_id"] == PLAYER
    context["identity"].loc[0, "identity_status"] = "ambiguous_source_binding"
    assert cached_nflverse_outcome(context, forecast, game)["actual"] is None
    context["identity"].loc[0, "identity_status"] = "source_exact_binding"
    context["identity"] = pd.concat([context["identity"], context["identity"]], ignore_index=True)
    assert cached_nflverse_outcome(context, forecast, game)["actual"] is None
    forecast["sleeper_id"] = "different"
    assert cached_nflverse_outcome(context, forecast, game)["gap_reason"] == "conflicting_frozen_sleeper_identity"


def test_conflicting_frozen_provider_ids_never_choose_a_provider():
    context,forecast,game=fixtures()
    context['identity'].loc[0,'player_id']='00-0099999'
    assert cached_nflverse_outcome(context,forecast,game)['gap_reason']=='conflicting_frozen_gsis_sleeper_binding'
    context,forecast,game=fixtures()
    forecast.update(player_id='sleeper:123',identity_binding='conflicting_identity_cold_start')
    assert cached_nflverse_outcome(context,forecast,game)['gap_reason']=='conflicting_frozen_provider_identity'


@pytest.mark.parametrize("change", [
    {"final": False}, {"final": "true"}, {"game_id": "espn:different"},
    {"kickoff_utc": "2026-10-18T18:00:00Z"}, {"home": "OTHER"}, {"home": "A", "away": "B"}, {"week": 7}])
def test_completion_provider_id_period_and_schedule_mismatches_fail_closed(change):
    context, forecast, game = fixtures()
    assert cached_nflverse_outcome(context, forecast, {**game, **change})["actual"] is None


def test_invalid_gsis_ambiguous_games_and_snapshot_clocks_fail_closed():
    context, forecast, game = fixtures()
    assert cached_nflverse_outcome(context, {**forecast, "player_id": "Player Name"}, game)["gap_reason"] == "invalid_canonical_gsis"
    duplicate = context["history"].copy()
    duplicate["game_id"] = "different-canonical-game"
    context["history"] = pd.concat([context["history"], duplicate], ignore_index=True)
    assert cached_nflverse_outcome(context, forecast, game)["actual"] is None
    context, forecast, game = fixtures()
    context["receipts"]["stats_player_week_2026.parquet"]["retrieved_utc"] = "2026-10-18T16:00:00Z"
    assert cached_nflverse_outcome(context, forecast, game)["actual"] is None
    context["receipts"]["stats_player_week_2026.parquet"]["retrieved_utc"] = "2026-10-23T16:00:00Z"
    assert cached_nflverse_outcome(context, forecast, game)["actual"] is None


def test_signed_yards_combined_components_ppr_and_invalid_counts():
    context, forecast, game = fixtures()
    assert cached_nflverse_outcome(context, {**forecast, "target": "rush_yd"}, game)["actual"] == -2.0
    assert cached_nflverse_outcome(context, {**forecast, "target": "rush_rec_yd"}, game)["actual"] == -2.0
    context["history"].loc[0, "rec_yd"] = np.nan
    assert cached_nflverse_outcome(context, {**forecast, "target": "rush_rec_yd"}, game)["actual"] is None
    assert cached_nflverse_outcome(context, {**forecast, "target": "fantasy_ppr"}, game)["actual"] is None
    context["history"].loc[0, "rec"] = 0.5
    assert cached_nflverse_outcome(context, forecast, game)["gap_reason"] == "invalid_count_outcome"


def test_context_verifies_all_cached_receipts_before_offline_shared_loaders(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    names = ["schedules.csv", "players.parquet", "stats_player_week_2026.parquet", "roster_weekly_2026.parquet"]
    for name in names:
        body = b"fixture bytes for " + name.encode()
        (raw / name).write_bytes(body)
        (raw / (name + ".receipt.json")).write_text(json.dumps({"sha256": hashlib.sha256(body).hexdigest(),
            "retrieved_utc": "2026-10-20T12:00:00Z", "status": "acquired"}))
    calls = []
    monkeypatch.setattr("nfl_lab.grading_sources.load_history", lambda *args: calls.append("history") or fixtures()[0]["history"])
    monkeypatch.setattr("nfl_lab.grading_sources.load_identity", lambda *args: calls.append("identity") or fixtures()[0]["identity"])
    context = load_cached_grading_context(tmp_path, [2026])
    assert calls == ["history", "identity"] and len(context["receipts"]) == 4
    (raw / "stats_player_week_2026.parquet").write_bytes(b"tampered")
    calls.clear()
    with pytest.raises(ValueError, match="integrity failure"):
        load_cached_grading_context(tmp_path, [2026])
    assert calls == []


def test_cached_and_uncached_match_and_repeated_queries_build_once(monkeypatch):
    import nfl_lab.grading_sources as module
    context, forecast, game = fixtures()
    original = module._build_grading_lookups
    builds = []
    def counted(context):
        builds.append(True)
        return original(context)
    monkeypatch.setattr(module, "_build_grading_lookups", counted)
    for target in ["rec", "rec_yd", "rush_yd", "rush_rec_yd", "anytime_td", "fantasy_ppr"]:
        cached = cached_nflverse_outcome(context, {**forecast, "target": target}, game)
        assert cached == cached_nflverse_outcome(context, {**forecast, "target": target}, game)
    assert len(builds) == 1
    for target in ["rec", "rec_yd", "rush_yd", "rush_rec_yd", "anytime_td", "fantasy_ppr"]:
        assert cached_nflverse_outcome(context, {**forecast, "target": target}, game) == cached_nflverse_outcome(
            context, {**forecast, "target": target}, game, use_lookup_cache=False)


def test_duplicate_player_rows_and_replaced_identity_frames_invalidate_cache():
    context, forecast, game = fixtures()
    assert cached_nflverse_outcome(context, forecast, game)["actual"] == 0
    context["history"] = pd.concat([context["history"], context["history"]], ignore_index=True)
    cached = cached_nflverse_outcome(context, forecast, game)
    assert cached["gap_reason"] == "missing_or_ambiguous_player_game"
    assert cached == cached_nflverse_outcome(context, forecast, game, use_lookup_cache=False)
    context, forecast, game = fixtures()
    forecast["player_id"] = "sleeper:123"
    assert cached_nflverse_outcome(context, forecast, game)["actual"] == 0
    context["identity"] = pd.concat([context["identity"], context["identity"]], ignore_index=True)
    cached = cached_nflverse_outcome(context, forecast, game)
    assert cached["actual"] is None
    assert cached == cached_nflverse_outcome(context, forecast, game, use_lookup_cache=False)
