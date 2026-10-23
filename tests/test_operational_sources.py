"""Fictional only: permitted-source schema, temporal and isolation acceptance."""
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab import data, operational_sources as source


ASOF = "2026-10-23T12:00:00Z"
PERIODS = {2026: [1, 2, 3, 4, 5]}


@pytest.fixture(autouse=True)
def fictional_current_clock(monkeypatch):
    monkeypatch.setattr(source, "_actual_now", lambda: pd.Timestamp("2027-02-01T12:00Z"))


def policy_fixture():
    return {"policy_id": source.POLICY_ID,
            "sources": {kind: {"name": name, "url": url,
                        **({"columns": source.SCHEDULE_COLUMNS} if kind == "schedules" else {})}
                        for kind, (name, url) in source.SOURCE_SPECS.items()},
            "history": {"season_type": "REG", "statistics_lag_days": 7,
                        "parquet_predicates": {"statistics_season_type": "season_type == REG", "roster_season_type": "game_type == REG"}},
            "namespaces": {"private_retention_bytes": 64 * 1024 * 1024}}


def source_fixture(directory):
    raw = directory / "raw"
    raw.mkdir(parents=True)
    games, stats, roster = [], [], []
    players = ["played-zero", "negative", "zero-only", "missing", "inactive", "window"]
    for week in range(1, 9):
        date = pd.Timestamp("2026-09-06") + pd.Timedelta(days=7 * (week - 1))
        games.append({"game_id": f"2026_{week:02d}_A_B", "season": 2026, "week": week,
                      "game_type": "REG", "gameday": str(date.date()), "gametime": "13:00",
                      "home_team": "B", "away_team": "A", "home_score": 999999})
        for player in players:
            roster.append({"season": 2026, "week": week, "game_type": "REG", "team": "A", "gsis_id": player,
                           "position": "RB", "status": "INA" if player == "inactive" else "ACT",
                           "full_name": player, "sleeper_id": str(players.index(player) + 1)})
            if player in {"missing", "inactive"} or (player == "window" and week in {2, 4, 5}):
                continue
            row = {"season": 2026, "week": week, "season_type": "REG", "team": "A", "player_id": player,
                   "player_display_name": player, "position": "RB", **{key: 0.0 for key in data.STAT_MAP}}
            if player == "played-zero":
                row["targets"] = 1.0  # Independent playing evidence supports the explicit carry zero.
            elif player == "negative":
                row["rushing_yards"] = -3.0
            elif player == "window":
                row.update(carries=1.0, rushing_yards=float(week * 10))
            if week >= 6:
                row["rushing_yards"] = 987654321.0  # Protected values must never decode.
            stats.append(row)
    # POST and future rows cannot become REG evidence.
    stats.append({**stats[0], "season_type": "POST", "week": 1, "rushing_yards": 888888.0})
    roster.append({**roster[0], "game_type": "POST", "week": 1})
    pd.DataFrame(games).to_csv(raw / "schedules.csv", index=False)
    pd.DataFrame({"gsis_id": players, "display_name": players, "pfr_id": ["forbidden-value"] * len(players)}).to_parquet(raw / "players.parquet")
    pd.DataFrame(stats).to_parquet(raw / "stats_player_week_2026.parquet")
    pd.DataFrame(roster).to_parquet(raw / "roster_weekly_2026.parquet")
    (raw / "nflverse_LICENSE.md").write_text("Fictional license fixture. No real source bytes.\n")
    for name, spec in source._names([2026]).items():
        (raw / (name + ".receipt.json")).write_text(json.dumps({"name": name, "url": spec["url"],
             "sha256": data._sha(raw / name), "status": "acquired", "retrieved_utc": "2026-10-22T09:00:00Z"}))
    # This old cache artifact must not be requested, inspected or copied.
    (raw / "snap_counts_2026.parquet").write_bytes(b"POISON: forbidden legacy source")
    return directory


@pytest.fixture
def packet(tmp_path):
    old = source_fixture(tmp_path / "old-cache")
    policy = policy_fixture()
    manifest = source.acquire_operational_history(tmp_path / "new-cache", [2026], policy, ASOF,
                                                source_cache=old, allowed_periods=PERIODS)
    return tmp_path / "new-cache", old, policy, manifest


def load(packet):
    cache, _, policy, _ = packet
    return source.load_operational_history(cache, [2026], policy, ASOF, allowed_periods=PERIODS)


def test_predicates_precede_decoding_and_only_identity_metadata_read(tmp_path, monkeypatch):
    old = source_fixture(tmp_path / "old")
    original = pd.read_parquet
    observed = []

    def audited(path, *args, **kwargs):
        path = Path(path)
        if path.parent.name == "sources" and "2026.parquet" in path.name:
            assert kwargs["filters"]
            filters = kwargs["filters"][0]
            assert ("week", "in", [1, 2, 3, 4, 5]) in filters
            column = "season_type" if path.name.startswith("stats") else "game_type"
            assert (column, "==", "REG") in filters
            observed.append(path.name)
        if path.parent.name == "sources" and path.name == "players.parquet":
            assert kwargs["columns"] == ["gsis_id", "display_name"]
        assert "snap_counts" not in path.name
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", audited)
    monkeypatch.setattr(data, "_download", lambda *a, **k: pytest.fail("cache adoption made HTTP"))
    manifest = source.acquire_operational_history(tmp_path / "new", [2026], policy_fixture(), ASOF,
                                                source_cache=old, allowed_periods=PERIODS)
    assert set(observed) == {"stats_player_week_2026.parquet", "roster_weekly_2026.parquet"}
    raw = Path(manifest["namespace"]) / "raw"
    assert "home_score" not in pd.read_csv(raw / "schedules.csv")
    assert not any(path.is_symlink() for path in Path(manifest["namespace"]).rglob("*"))
    assert not list(raw.glob("*.receipt.json"))


def test_played_zero_signed_yards_missing_inactive_unknown_and_ppr(packet):
    history = load(packet)
    rows = history[history.week.eq(1)].set_index("player_id")
    assert rows.loc["played-zero", "participation_state"] == "played"
    assert rows.loc["played-zero", "rush_att"] == 0
    assert rows.loc["negative", "rush_yd"] == -3
    for player in ["zero-only", "missing", "inactive"]:
        assert rows.loc[player, "participation_state"] == "unknown"
        assert pd.isna(rows.loc[player, "rush_att"])
    assert history.fantasy_ppr.isna().all()
    assert history.offense_snaps.isna().all()
    assert not history.participation_state.eq("DNP").any()
    assert history.week.max() == 5


def test_features_keep_unknown_window_slots_and_block_probability(packet):
    history = load(packet)
    query = pd.DataFrame([{"season": 2026, "week": 8, "player_id": "window", "game_id": "future",
                           "team": "A", "opponent": "B", "position": "RB", "kickoff_utc": "2026-10-25T17:00Z",
                           "cutoff_utc": ASOF, "rush_yd": 999999}])
    out = source.build_operational_features(history, policy=packet[2], queries=query)
    assert len(out) == 1
    assert out.iloc[0].f_player_games_prior == 5
    assert out.iloc[0].f_player_rush_yd_n3 == 1
    assert out.iloc[0].f_player_rush_yd_mean3 == 30
    assert pd.isna(out.iloc[0].rush_yd)
    assert pd.isna(out.iloc[0].f_player_play_rate8)
    assert out.iloc[0].f_player_offense_snaps_n3 == 0
    assert pd.isna(out.iloc[0].f_player_offense_snaps_mean3)
    assert out.iloc[0].feature_max_source_available_utc < pd.Timestamp(ASOF)
    query["cutoff_utc"] = "2026-10-20T10:00Z"
    with pytest.raises(ValueError, match="asof exceeds"):
        source.build_operational_features(history, policy=packet[2], queries=query)


def test_exact_hash_binding_rejects_mutated_qualified_history(packet):
    history = load(packet)
    history.loc[0, "rush_yd"] = 999
    with pytest.raises(ValueError, match="training view changed"):
        source.build_operational_features(history, policy=packet[2])


def test_restart_is_immutable_and_original_cache_stays_unchanged(packet, monkeypatch):
    cache, old, policy, manifest = packet
    before = {path.name: data._sha(path) for path in (old / "raw").iterdir()}
    monkeypatch.setattr(data, "_download", lambda *a, **k: pytest.fail("restart made HTTP"))
    restarted = source.acquire_operational_history(cache, [2026], policy, ASOF,
                                                 source_cache=old, allowed_periods=PERIODS)
    assert restarted == manifest
    assert before == {path.name: data._sha(path) for path in (old / "raw").iterdir()}
    assert restarted["training_view_sha256"] == data._sha(Path(manifest["namespace"]) / "processed/history.parquet")
    assert "snap_counts_2026.parquet" not in restarted["source_receipts"]


def test_changed_or_forbidden_snapshot_fails_closed(packet):
    raw = Path(packet[3]["namespace"]) / "raw"
    (raw / "snap_counts_2026.parquet").write_bytes(b"forbidden")
    with pytest.raises(ValueError, match="forbidden/unexpected"):
        load(packet)


def test_transformed_body_and_original_receipts_have_distinct_bindings(packet):
    manifest = packet[3]
    subset = json.loads((Path(manifest["namespace"]) / "subset-manifest.json").read_text())
    name = "stats_player_week_2026.parquet"
    assert subset["files"][name]["sha256"] != manifest["source_receipts"][name]["sha256"]
    (Path(manifest["namespace"]) / "raw" / name).write_bytes(b"mutated derived view")
    with pytest.raises(ValueError, match="derived artifact changed"):
        load(packet)


def test_latest_cache_lookup_is_readonly_and_explicit(packet):
    cache, _, policy, manifest = packet
    with pytest.raises(FileNotFoundError, match="exact permitted"):
        source.load_operational_history(cache, [2026], policy, "2026-10-24T12:00Z", allowed_periods=PERIODS)
    later = source.load_operational_history(cache, [2026], policy, "2026-10-24T12:00Z", allowed_periods=PERIODS, latest=True)
    assert later.attrs["operational_manifest"]["snapshot_sha256"] == manifest["snapshot_sha256"]
    with pytest.raises(FileNotFoundError):
        source.resolve_operational_snapshot(cache, [2026], policy, "2026-10-21T12:00Z", allowed_periods=PERIODS)
    unrestricted = source.resolve_operational_snapshot(cache, [2026], policy, "2026-10-24T12:00Z")
    assert unrestricted["effective_periods"] == {"2026": [1, 2, 3, 4, 5]}


def test_full_week_gate_is_strict_and_cannot_expand_caps(tmp_path):
    old = source_fixture(tmp_path / "old")
    schedule_path = old / "raw/schedules.csv"
    schedule = pd.read_csv(schedule_path)
    schedule = pd.concat([schedule, pd.DataFrame([{**schedule.iloc[4].to_dict(), "game_id": "late-game",
                          "home_team": "D", "away_team": "C", "gameday": "2026-10-18", "gametime": "20:00"}])])
    schedule.to_csv(schedule_path, index=False)
    receipt_path = old / "raw/schedules.csv.receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["sha256"] = data._sha(schedule_path)
    receipt_path.write_text(json.dumps(receipt))
    manifest = source.acquire_operational_history(tmp_path / "new", [2026], policy_fixture(), ASOF,
                                                source_cache=old, allowed_periods={2026: list(range(1, 9))})
    assert 5 not in manifest["effective_periods"]["2026"]
    assert manifest["effective_periods"]["2026"] == [1, 2, 3, 4, 6]


def test_identity_read_is_exact_filtered_and_pfr_values_not_read(packet):
    identity = source.load_operational_identity(packet[0], [2026], packet[2], ASOF, allowed_periods=PERIODS)
    assert identity.identity_status.eq("source_exact_binding").all()
    assert identity.pfr_id.isna().all()
    assert identity.set_index("player_id").loc["window", "sleeper_id"] == "6"


def test_policy_schema_and_normalized_policy_tamper_fail():
    policy = source.load_source_policy(policy_fixture())
    altered = copy.deepcopy(policy)
    altered["scope"] = "mutated after freeze"
    with pytest.raises(ValueError, match="policy body changed"):
        source.load_source_policy(altered)
    altered = policy_fixture()
    altered["sources"]["statistics"]["url"] = "https://example.org/not-permitted"
    with pytest.raises(ValueError, match="URL/name changed"):
        source.load_source_policy(altered)
    with pytest.raises(ValueError, match="explicit timezone"):
        source._request([2026], policy, "2026-10-23", PERIODS)
    with pytest.raises(ValueError, match="actual current UTC"):
        source._request([2028], policy, "2028-10-23T12:00Z", None)


def test_live_receipt_clock_cannot_be_hidden_by_earlier_asof(packet):
    history = load(packet)
    manifest = copy.deepcopy(history.attrs["operational_manifest"])
    name = "players.parquet"
    manifest["source_receipts"][name]["retrieved_utc"] = "2026-10-24T10:00Z"
    history.attrs["operational_manifest"] = manifest
    query = pd.DataFrame([{"player_id": "window", "game_id": "future", "team": "A", "opponent": "B",
                           "kickoff_utc": "2026-10-25T17:00Z", "cutoff_utc": ASOF}])
    with pytest.raises(ValueError, match="receipt observed after"):
        source.build_operational_features(history, policy=packet[2], queries=query)


def test_january_active_season_and_missing_schema(tmp_path):
    policy = source.load_source_policy(policy_fixture())
    assert source._request([2026], policy, "2027-01-10T12:00Z", None)["seasons"] == [2026]
    with pytest.raises(ValueError, match="active NFL season"):
        source._request([2027], policy, "2027-01-10T12:00Z", None)
    old = source_fixture(tmp_path / "old")
    path = old / "raw/stats_player_week_2026.parquet"
    stats = pd.read_parquet(path).drop(columns="season_type")
    stats.to_parquet(path, index=False)
    receipt_path = path.with_name(path.name + ".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    receipt["sha256"] = data._sha(path)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="schema incomplete"):
        source.acquire_operational_history(tmp_path / "new", [2026], policy, ASOF,
                                           source_cache=old, allowed_periods=PERIODS)
    assert list((tmp_path / "new").rglob("FAILURE.json"))


def test_symlink_adoption_and_retention_fail_closed(tmp_path):
    old = source_fixture(tmp_path / "old")
    alias = tmp_path / "old-alias"
    alias.symlink_to(old, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        source.acquire_operational_history(tmp_path / "new", [2026], policy_fixture(), ASOF,
                                           source_cache=alias, allowed_periods=PERIODS)
    policy = policy_fixture()
    policy["namespaces"]["private_retention_bytes"] = 1
    with pytest.raises(ValueError, match="retention budget"):
        source.acquire_operational_history(tmp_path / "small", [2026], policy, ASOF,
                                           source_cache=old, allowed_periods=PERIODS)


@pytest.mark.parametrize("invalid_count", [-1.0, 0.5, np.inf, "unsupported"])
def test_invalid_counts_fail_closed_without_clipping_signed_yards(tmp_path, invalid_count):
    old = source_fixture(tmp_path / "old")
    path = old / "raw/stats_player_week_2026.parquet"
    frame = pd.read_parquet(path)
    if isinstance(invalid_count, str):
        frame["carries"] = frame.carries.astype(str)
    frame.loc[0, "carries"] = invalid_count
    frame.to_parquet(path, index=False)
    receipt_path = path.with_name(path.name + ".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    receipt["sha256"] = data._sha(path)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="invalid supported official statistic"):
        source.acquire_operational_history(tmp_path / "new", [2026], policy_fixture(), ASOF,
                                           source_cache=old, allowed_periods=PERIODS)


def test_zero_only_team_cannot_supply_observed_team_priors(tmp_path):
    old = source_fixture(tmp_path / "old")
    path = old / "raw/stats_player_week_2026.parquet"
    frame = pd.read_parquet(path)
    frame.loc[frame.week.eq(1), list(data.STAT_MAP)] = 0.0
    frame.to_parquet(path, index=False)
    receipt_path = path.with_name(path.name + ".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    receipt["sha256"] = data._sha(path)
    receipt_path.write_text(json.dumps(receipt))
    policy = policy_fixture()
    cache = tmp_path / "new"
    source.acquire_operational_history(cache, [2026], policy, ASOF, source_cache=old, allowed_periods=PERIODS)
    history = source.load_operational_history(cache, [2026], policy, ASOF, allowed_periods=PERIODS)
    assert history.loc[history.week.eq(1), ["team_stat_" + col for col in source.features.TEAM_STATS]].isna().all().all()


def test_grade_latest_accepts_larger_verified_season_panel(tmp_path):
    old = source_fixture(tmp_path / "old")
    raw = old / "raw"
    for kind in ["stats_player_week", "roster_weekly"]:
        frame = pd.read_parquet(raw / f"{kind}_2026.parquet")
        frame["season"] = 2025
        frame.to_parquet(raw / f"{kind}_2025.parquet", index=False)
    schedule = pd.read_csv(raw / "schedules.csv")
    earlier = schedule.copy()
    earlier["season"] = 2025
    earlier["game_id"] = earlier.game_id.str.replace("2026", "2025")
    earlier["gameday"] = earlier.gameday.str.replace("2026", "2025")
    pd.concat([earlier, schedule]).to_csv(raw / "schedules.csv", index=False)
    for name, spec in source._names([2025, 2026]).items():
        (raw / (name + ".receipt.json")).write_text(json.dumps({"name": name, "url": spec["url"],
             "sha256": data._sha(raw / name), "status": "acquired", "retrieved_utc": "2026-10-22T09:00:00Z"}))
    policy = policy_fixture()
    cache = tmp_path / "new"
    manifest = source.acquire_operational_history(cache, [2025, 2026], policy, ASOF, source_cache=old,
                                                allowed_periods={2025: list(range(1, 9)), **PERIODS})
    context = source.load_operational_history(cache, [2026], policy, "2026-10-24T12:00Z", latest=True)
    assert context.attrs["operational_manifest"]["snapshot_sha256"] == manifest["snapshot_sha256"]
    assert set(context.season) == {2025, 2026}
    with pytest.raises(FileNotFoundError):
        source.resolve_operational_snapshot(cache, [2026], policy, "2026-10-24T12:00Z", allowed_periods={2026: [1, 2]})
