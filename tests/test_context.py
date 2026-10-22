import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab.context import (BASE, NGS_METRICS, load_ngs, load_public_news,
                            merge_ngs_asof, normalize_observations, observations_asof)


PLAYER = "00-0030001"
OTHER = "00-0030002"


def history_rows():
    rows = []
    for week in range(1, 6):
        kickoff = pd.Timestamp("2023-09-01", tz="UTC") + pd.Timedelta(days=week * 8)
        rows.append({"player_id": PLAYER, "game_id": f"game-{week}", "season": 2023, "week": week,
                     "team": "A", "opponent": "B", "kickoff_utc": kickoff,
                     "outcome_available_utc": kickoff + pd.Timedelta(days=7),
                     "f_existing_base": float(week), "rec_yd": float(week * 10)})
    return pd.DataFrame(rows)


def ngs_rows():
    h = history_rows()
    d = h[["player_id", "game_id", "team", "kickoff_utc"]].copy()
    d["available_utc"] = d.kickoff_utc + pd.Timedelta(days=7)
    d["availability_basis"] = "reconstructed_7day_lag"
    d["receiving_avg_separation"] = [1.0, 2.0, np.nan, 4.0, 5.0]
    d["published_utc"] = pd.NaT
    d["updated_utc"] = pd.NaT
    return d


def test_ngs_no_current_future_or_order_leakage_and_base_unchanged():
    h, ngs = history_rows(), ngs_rows()
    a = merge_ngs_asof(h, ngs)
    changed = ngs.copy()
    changed.loc[changed.game_id.isin(["game-4", "game-5"]), "receiving_avg_separation"] = 999.0
    b = merge_ngs_asof(h, changed.sample(frac=1, random_state=7))
    cols = [c for c in a if c.startswith("f_ngs_")]
    pd.testing.assert_frame_equal(a.loc[:3, cols], b.loc[:3, cols])
    pd.testing.assert_series_equal(a.f_existing_base, h.f_existing_base)
    pd.testing.assert_series_equal(a.rec_yd, h.rec_yd)
    # A missing third game consumes a slot: last three are 2, missing, 4.
    assert a.iloc[4].f_ngs_receiving_avg_separation_mean3 == 3
    assert a.iloc[4].f_ngs_receiving_avg_separation_n3 == 2
    assert np.isnan(a.iloc[0].f_ngs_receiving_avg_separation_mean3)
    good = a.ngs_feature_max_available_utc.notna()
    assert (a.loc[good, "ngs_feature_max_available_utc"] < h.loc[good, "kickoff_utc"]).all()


def test_ngs_late_publication_and_updates_enforce_cutoff():
    h, ngs = history_rows(), ngs_rows()
    ngs["published_utc"] = pd.to_datetime(ngs.published_utc, utc=True)
    ngs.loc[0, "published_utc"] = h.iloc[1].kickoff_utc + pd.Timedelta(hours=1)
    a = merge_ngs_asof(h, ngs)
    assert a.iloc[1].f_ngs_receiving_avg_separation_n3 == 0
    assert a.iloc[2].f_ngs_receiving_avg_separation_n3 == 2
    ngs["updated_utc"] = pd.to_datetime(ngs.updated_utc, utc=True)
    ngs.loc[1, "updated_utc"] = h.iloc[2].kickoff_utc
    b = merge_ngs_asof(h, ngs)
    # Equality to cutoff is ineligible.
    assert b.iloc[2].f_ngs_receiving_avg_separation_n3 == 1


def test_ngs_stale_missing_identity_duplicate_and_reconstruction_labels():
    h, ngs = history_rows(), ngs_rows()
    h.loc[4, "kickoff_utc"] += pd.Timedelta(days=100)
    h.loc[4, "outcome_available_utc"] = h.loc[4, "kickoff_utc"] + pd.Timedelta(days=7)
    ngs = ngs.iloc[:4]
    a = merge_ngs_asof(h, ngs)
    assert a.iloc[4].f_ngs_receiving_avg_separation_n3 == 0
    invalid = ngs.copy()
    invalid.loc[0, "player_id"] = "player name"
    with pytest.raises(ValueError, match="GSIS"):
        merge_ngs_asof(h, invalid)
    invalid = ngs.copy()
    invalid.loc[0, "team"] = "OTHER"
    with pytest.raises(ValueError, match="binding conflict"):
        merge_ngs_asof(h, invalid)
    with pytest.raises(ValueError, match="duplicate"):
        merge_ngs_asof(h, pd.concat([ngs, ngs.iloc[[0]]], ignore_index=True))
    with pytest.raises(ValueError, match="explicitly labeled"):
        merge_ngs_asof(h, ngs.drop(columns="availability_basis"))


def test_ngs_seven_day_floor_and_exact_player_match():
    h, ngs = history_rows(), ngs_rows()
    h.loc[1, "cutoff_utc"] = h.loc[0, "kickoff_utc"] + pd.Timedelta(days=6)
    ngs.loc[0, "available_utc"] = ngs.loc[0, "kickoff_utc"] + pd.Timedelta(hours=1)
    assert merge_ngs_asof(h, ngs).iloc[1].f_ngs_receiving_avg_separation_n3 == 0
    ngs["player_id"] = OTHER
    assert merge_ngs_asof(history_rows(), ngs).f_ngs_receiving_avg_separation_n3.eq(0).all()


def test_source_ngs_week_zero_unknown_ids_unmatched_games_and_schema(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    name = "ngs_2023_receiving.csv.gz"
    asset = {"name": name, "size": 1000, "updated_at": "2024-02-29T00:00:00Z",
             "browser_download_url": f"{BASE}/nextgen_stats/{name}"}
    (raw / "ngs_release.json").write_text(json.dumps({"assets": [asset]}))
    pd.DataFrame({"gsis_id": [PLAYER]}).to_parquet(raw / "players.parquet")
    pd.DataFrame([{"game_id": "game-1", "season": 2023, "week": 1, "gameday": "2023-09-10", "gametime": "13:00",
                   "away_team": "A", "home_team": "B"}]).to_csv(raw / "schedules.csv", index=False)
    base = {"season": 2023, "season_type": "REG", "week": 1, "player_gsis_id": PLAYER,
            "team_abbr": "A", **{m: 1.0 for m in NGS_METRICS['receiving']}}
    pd.DataFrame([base, {**base, "week": 0}, {**base, "week": 2}, {**base, "player_gsis_id": OTHER}]).to_csv(raw / name, index=False)
    monkeypatch.setattr("nfl_lab.context._download", lambda *args, **kwargs: {"name": name, "status": "acquired", "retrieved_utc": "2024-03-01T00:00:00Z"})
    d = load_ngs(tmp_path, [2023])
    assert len(d) == 1 and d.iloc[0].game_id == "game-1"
    coverage = d.attrs["manifest"]["coverage"][0]
    assert coverage["season_aggregates_excluded"] == 1
    assert coverage["invalid_or_unknown_gsis_excluded"] == 1
    assert coverage["unmatched_schedule_excluded"] == 1
    assert d.published_utc.isna().all()
    assert d.availability_basis.eq("reconstructed_7day_lag").all()
    pd.DataFrame([base, base]).to_csv(raw / name, index=False)
    with pytest.raises(ValueError, match="duplicate NGS"):
        load_ngs(tmp_path, [2023])
    pd.DataFrame([base]).drop(columns="avg_separation").to_csv(raw / name, index=False)
    with pytest.raises(ValueError, match="schema missing"):
        load_ngs(tmp_path, [2023])


def observation(**changes):
    return {"source_url": "https://example.org/public-story", "group": "injury", "claim_type": "reported_fact",
            "claim_text": "Synthetic test fixture claim.", "player_id": PLAYER, "team": "A",
            "published_utc": "2023-09-01T10:00:00Z", "updated_utc": "2023-09-01T11:00:00Z",
            "retrieved_utc": "2023-09-01T12:00:00Z", **changes}


def test_observation_clocks_future_stale_unknown_and_exact_claim_preservation():
    rows = [observation(), observation(claim_text="Synthetic unknown publication.", published_utc=None),
            observation(claim_text="Synthetic future retrieval.", retrieved_utc="2023-09-02T00:00:00Z"),
            observation(claim_text="Synthetic future publication.", published_utc="2023-09-03T00:00:00Z"),
            observation(claim_text="Synthetic stale content.", published_utc="2023-08-01T00:00:00Z", updated_utc=None)]
    d = normalize_observations(rows)
    eligible = observations_asof(d, "2023-09-01T13:00:00Z", player_id=PLAYER)
    assert eligible.claim_text.tolist() == [rows[0]["claim_text"]]
    assert d[d.claim_text.eq(rows[1]["claim_text"])].clock_status.iloc[0] == "publication_unknown"
    assert not any(c.startswith("f_") for c in d)
    tampered = d.copy()
    tampered.loc[tampered.claim_text.eq(rows[0]["claim_text"]), "published_utc"] = pd.Timestamp("2023-09-10", tz="UTC")
    assert observations_asof(tampered, "2023-09-01T13:00:00Z").empty


def test_observation_dedup_earliest_snapshot_out_of_order_and_types():
    first = observation()
    duplicate = observation(source_url=first["source_url"] + "?utm_campaign=repeat#fragment", retrieved_utc="2023-09-01T14:00:00Z")
    other = observation(claim_text="Synthetic coach quote.", claim_type="coach_statement", group="scheme")
    model = observation(claim_text="Synthetic explicit hypothesis.", claim_type="model_hypothesis", group="environment")
    a = normalize_observations([duplicate, model, other, first])
    b = normalize_observations([first, other, model, duplicate])
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 3
    fact = a[a.claim_type.eq("reported_fact")].iloc[0]
    assert fact.duplicate_count == 2
    assert fact.retrieved_utc == pd.Timestamp("2023-09-01T12:00:00Z")
    assert len(observations_asof(a, "2023-09-01T13:00:00Z", team="A")) == 3
    assert observations_asof(a, "2023-09-01T12:00:00Z").empty


def test_observation_unknown_retrieval_update_and_id_fail_closed():
    d = normalize_observations([observation(retrieved_utc=None), observation(claim_text="Bad update fixture.", updated_utc="2023-09-01T09:00:00Z")])
    assert observations_asof(d, "2023-09-01T13:00:00Z").empty
    with pytest.raises(ValueError, match="GSIS"):
        normalize_observations([observation(player_id="Unbound Name")])
    with pytest.raises(ValueError, match="timezone"):
        normalize_observations([observation(published_utc="2023-09-01T10:00:00")])
    with pytest.raises(ValueError, match="HTTP"):
        normalize_observations([observation(source_url="file:///private")])


def test_news_adapter_uses_exact_espn_binding_and_preserves_source_clocks(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame({"gsis_id": [PLAYER], "espn_id": ["123"]}).to_parquet(raw / "players.parquet")
    payload = {"articles": [{"id": "article-1", "description": "Synthetic ESPN API fixture description.",
                            "published": "2023-09-01T10:00:00Z", "links": {"web": {"href": "https://www.espn.com/nfl/story/1"}},
                            "categories": [{"type": "athlete", "athlete": {"id": 123}}]}]}
    monkeypatch.setattr("nfl_lab.context.fetch_cached_json", lambda *args: (payload, {"retrieved_utc": "2023-09-01T12:00:00Z"}))
    d = load_public_news(tmp_path)
    assert len(d) == 1 and d.iloc[0].player_id == PLAYER
    assert d.iloc[0].claim_type == "reporter_interpretation"
    assert d.iloc[0].claim_text == payload["articles"][0]["description"]
    assert d.iloc[0].published_utc == pd.Timestamp("2023-09-01T10:00:00Z")
    assert d.iloc[0].updated_utc is pd.NaT
