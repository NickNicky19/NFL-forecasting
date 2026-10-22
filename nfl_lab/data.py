"""One cached, provenance-bearing nflverse history adapter.

Historical files are CURRENT-VINTAGE RECONSTRUCTIONS, never authentic pregame
snapshots. A seven day assumed outcome publication lag is conservative research
policy, not evidence of the provider's historical publication time. Raw files
and derived row-level tables stay in ignored local storage.
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
           "rush_att", "rec", "rec_yd", "rush_rec_yd", "fantasy_ppr", "anytime_td")
STAT_MAP = {"passing_yards": "pass_yd", "passing_tds": "pass_td",
            "completions": "pass_cmp", "attempts": "pass_att", "interceptions": "pass_int",
            "rushing_yards": "rush_yd", "carries": "rush_att", "receptions": "rec",
            "receiving_yards": "rec_yd", "targets": "rec_tgt", "rushing_tds": "rush_td",
            "receiving_tds": "rec_td"}
POSITIONS = {"QB", "RB", "FB", "WR", "TE"}
BASE = "https://github.com/nflverse/nflverse-data/releases/download"
VINTAGE = "current-vintage historical reconstruction; original pregame availability unverified"
MAX_BYTES = 50 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(raw: Path, name: str, url: str, *, optional: bool = False) -> dict:
    """Bounded HTTP, atomic writes, integrity-checked reuse, no credentials."""
    path = raw / name
    metadata = raw / (name + ".receipt.json")
    if path.exists() and metadata.exists():
        receipt = json.loads(metadata.read_text())
        if receipt.get("sha256") == _sha(path) and receipt.get("url") == url:
            return {**receipt, "cache_reused": True}
    error = None
    for attempt in range(3):
        temporary = raw / (name + ".partial")
        try:
            with requests.get(url, stream=True, timeout=(10, 60)) as response:
                response.raise_for_status()
                if int(response.headers.get("Content-Length", 0)) > MAX_BYTES:
                    raise ValueError("source exceeds 50 MiB limit")
                count = 0
                with temporary.open("wb") as out:
                    for chunk in response.iter_content(1024 * 256):
                        count += len(chunk)
                        if count > MAX_BYTES:
                            raise ValueError("source exceeds 50 MiB limit")
                        out.write(chunk)
                temporary.replace(path)
                receipt = {"name": name, "url": url, "bytes": count, "sha256": _sha(path),
                           "retrieved_utc": _utc_now(), "http_last_modified": response.headers.get("Last-Modified"),
                           "etag": response.headers.get("ETag"), "cache_reused": False,
                           "original_publication_utc": None, "status": "acquired",
                           "vintage": VINTAGE, "raw_redistribution": "not authorized by this lab"}
                metadata.write_text(json.dumps(receipt, indent=2) + "\n")
                return receipt
        except (requests.RequestException, ValueError, OSError) as exc:
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
            temporary.unlink(missing_ok=True)
            if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (400, 401, 403, 404):
                break
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    result = {"name": name, "url": url, "status": "unavailable", "error": error, "checked_utc": _utc_now()}
    metadata.write_text(json.dumps(result, indent=2) + "\n")
    if optional:
        return result
    raise RuntimeError(f"Required NFL source unavailable: {result}")


def acquire_history(cache: Path, seasons: list[int]) -> dict:
    """Acquire once into ``cache/raw``; return source hashes, rights and clocks."""
    started = time.monotonic()
    cache = Path(cache)
    raw = cache / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    seasons = sorted(set(int(y) for y in seasons))
    if not seasons or any(y < 2012 or y > datetime.now().year for y in seasons):
        raise ValueError("seasons must be supported NFL years, 2012 through current year")
    jobs = [
        ("schedules.csv", "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv", False),
        ("players.parquet", f"{BASE}/players/players.parquet", False),
        ("nflverse_LICENSE.md", "https://raw.githubusercontent.com/nflverse/nflverse-data/main/LICENSE.md", False),
        ("ngs_release.json", "https://api.github.com/repos/nflverse/nflverse-data/releases/tags/nextgen_stats", True),
    ]
    for year in seasons:
        jobs += [(f"stats_player_week_{year}.parquet", f"{BASE}/stats_player/stats_player_week_{year}.parquet", False),
                 (f"roster_weekly_{year}.parquet", f"{BASE}/weekly_rosters/roster_weekly_{year}.parquet", False),
                 (f"snap_counts_{year}.parquet", f"{BASE}/snap_counts/snap_counts_{year}.parquet", True)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(pool.map(lambda x: _download(raw, x[0], x[1], optional=x[2]), jobs))
    ngs = next(r for r in receipts if r["name"] == "ngs_release.json")
    ngs_assets = []
    if ngs["status"] == "acquired":
        ngs_assets = [a["name"] for a in json.loads((raw / "ngs_release.json").read_text()).get("assets", [])
                      if a["name"].endswith(".csv.gz") and any(f"_{y}_" in a["name"] for y in seasons)]
    receipt = {"adapter_version": "nflverse-history-v1", "seasons": seasons,
               "created_utc": _utc_now(), "elapsed_seconds": round(time.monotonic() - started, 3),
               "vintage": VINTAGE, "availability_policy": "outcome_available_utc=kickoff+7 days (assumed, not authenticated)",
               "rights": {"hosting_repository_license": "CC-BY-4.0", "license_source": "nflverse_LICENSE.md",
                          "upstream_caveat": "PFR snap counts, NFL NGS and other upstream material retain their own rights; hosting license is not a blanket upstream grant",
                          "publication_policy": "raw sources and row-level source-derived tables are local ignored artifacts; review derived exports"},
               "sources": receipts,
               "source_transition": "legacy player_stats/player_stats_2025.parquet returned HTTP 404; using stats_player/stats_player_week_YYYY.parquet for all seasons with explicit schema crosswalk",
               "optional_groups": {
                   "snaps": "used where gsis/PFR crosswalk exists; absent rows do not establish DNP",
                   "ngs": {"state": "available_not_feature_enabled" if ngs_assets else "unavailable", "assets": ngs_assets,
                           "missing_assets": [f"ngs_{year}_{kind}.csv.gz" for year in seasons for kind in ("passing", "receiving", "rushing")
                                              if f"ngs_{year}_{kind}.csv.gz" not in ngs_assets]},
                   "news_injuries_routes_tracking_weather_forecasts": "unavailable with authenticated historic pregame clocks; not used",
                   "venue_rest": "schedule home/away and days since previous team game; no realized weather used"}}
    (raw / "acquisition.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def _require(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"{name} schema missing {sorted(missing)}")


def fetch_cached_json(cache: Path, name: str, url: str) -> tuple[object, dict]:
    """Shared bounded JSON cache for a named immutable/day-specific capture.

    Caller includes its capture date/id in ``name`` when a refreshed snapshot is
    required. Existing named snapshots are immutable unless their hash fails.
    """
    if not name or Path(name).name != name or not name.endswith(".json"):
        raise ValueError("name must be a simple .json filename without directories")
    raw = Path(cache) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    receipt = _download(raw, name, url)
    return json.loads((raw / name).read_text()), receipt


def load_identity(cache: Path) -> pd.DataFrame:
    """Exact source GSIS/PFR/Sleeper bindings; never infer IDs from names."""
    raw = Path(cache) / "raw"
    players = pd.read_parquet(raw / "players.parquet", columns=["gsis_id", "pfr_id", "display_name"])
    players = players.rename(columns={"gsis_id": "player_id", "display_name": "player_name"})
    mappings = []
    for path in sorted(raw.glob("roster_weekly_*.parquet")):
        roster = pd.read_parquet(path, columns=["gsis_id", "sleeper_id", "season", "week"])
        mappings.append(roster.rename(columns={"gsis_id": "player_id"}))
    if mappings:
        mapping = pd.concat(mappings).dropna(subset=["player_id", "sleeper_id"])
        # Historical source errors can affect both directions. Quarantine all
        # participants in an ambiguous binding, preserving candidates/evidence.
        bad_players = set(mapping.groupby("player_id").sleeper_id.nunique().loc[lambda s: s > 1].index)
        bad_sleepers = set(mapping.groupby("sleeper_id").player_id.nunique().loc[lambda s: s > 1].index)
        bad_players.update(mapping.loc[mapping.sleeper_id.isin(bad_sleepers), "player_id"])
        candidates = mapping.groupby("player_id").sleeper_id.agg(lambda s: "|".join(sorted(set(str(x) for x in s))))
        mapping = mapping.sort_values(["season", "week"]).drop_duplicates("player_id", keep="last")
        mapping["sleeper_id_candidates"] = mapping.player_id.map(candidates)
        mapping["identity_status"] = np.where(mapping.player_id.isin(bad_players), "ambiguous_source_binding", "source_exact_binding")
        mapping.loc[mapping.player_id.isin(bad_players), "sleeper_id"] = None
        players = players.merge(mapping[["player_id", "sleeper_id", "identity_status", "sleeper_id_candidates"]], on="player_id", how="outer", validate="one_to_one")
        players["identity_status"] = players.identity_status.fillna("no_sleeper_binding")
    else:
        players["sleeper_id"] = None
        players["identity_status"] = "no_sleeper_binding"
        players["sleeper_id_candidates"] = None
    return players


def _team(series: pd.Series) -> pd.Series:
    return series.replace({"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"})


def _schedule(raw: Path, seasons: list[int]) -> pd.DataFrame:
    games = pd.read_csv(raw / "schedules.csv")
    _require(games, {"game_id", "season", "week", "gameday", "gametime", "away_team", "home_team"}, "schedules")
    games = games[games.season.isin(seasons)].copy()
    local = pd.to_datetime(games.gameday + " " + games.gametime, errors="coerce")
    games["kickoff_utc"] = local.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    sides = []
    for own, other, home in (("home_team", "away_team", True), ("away_team", "home_team", False)):
        side = games[["season", "week", "game_id", "kickoff_utc", own, other]].rename(columns={own: "team", other: "opponent"})
        side["team"] = _team(side.team)
        side["opponent"] = _team(side.opponent)
        side["is_home"] = home
        sides.append(side)
    schedule = pd.concat(sides, ignore_index=True)
    if schedule.duplicated(["season", "week", "team"]).any():
        raise ValueError("schedule season/week/team is not unique")
    return schedule


def load_history(cache: Path, seasons: list[int]) -> pd.DataFrame:
    """Offline roster-complete history; never replace unobserved statistics by 0.

    Population: weekly ACT/INA offensive skill rosters, plus observed statistical
    or snap participants. Reserve/practice-squad-only records are not presumed
    game-eligible. INA explicitly identifies DNP; missing box scores do not.
    """
    started = time.monotonic()
    cache = Path(cache)
    raw = cache / "raw"
    seasons = sorted(set(int(y) for y in seasons))
    schedule = _schedule(raw, seasons)
    players = pd.read_parquet(raw / "players.parquet", columns=["gsis_id", "pfr_id"])
    players = players.dropna(subset=["pfr_id", "gsis_id"]).drop_duplicates("pfr_id")
    tables = []
    for year in seasons:
        stat_path = raw / f"stats_player_week_{year}.parquet"
        if not stat_path.exists():
            stat_path = raw / f"player_stats_{year}.parquet"  # retained older-schema inputs and fixtures
        stats = pd.read_parquet(stat_path)
        stats = stats.rename(columns={"team": "recent_team", "passing_interceptions": "interceptions"})
        _require(stats, {"player_id", "season", "week", "position", "recent_team", *STAT_MAP}, "player_stats")
        stats = stats.rename(columns={**STAT_MAP, "recent_team": "team", "player_display_name": "player_name"})
        # Older files include a separate abbreviated player_name; use display name.
        if stats.columns.duplicated().any():
            stats = stats.loc[:, ~stats.columns.duplicated(keep="last")]
        stats["team"] = _team(stats.team)
        keys = ["season", "week", "team", "player_id"]
        team_stats = stats.groupby(["season", "week", "team"], as_index=False)[["pass_yd", "rush_yd", "pass_att", "rush_att", "rec_yd"]].sum(min_count=1)
        team_stats = team_stats.rename(columns={col: "team_stat_" + col for col in ["pass_yd", "rush_yd", "pass_att", "rush_att", "rec_yd"]})
        stats = stats[stats.position.isin(POSITIONS)].copy()
        if stats.duplicated(keys).any():
            raise ValueError(f"duplicate weekly player stats in {year}")
        stats["stats_observed"] = True
        stats = stats[keys + ["player_name", "position", "stats_observed"] + list(STAT_MAP.values())]

        rosters = pd.read_parquet(raw / f"roster_weekly_{year}.parquet")
        _require(rosters, {"season", "week", "team", "gsis_id", "position", "status", "full_name"}, "weekly_rosters")
        rosters = rosters[rosters.position.isin(POSITIONS) & rosters.status.isin(["ACT", "INA"])].copy()
        rosters = rosters.rename(columns={"gsis_id": "player_id", "full_name": "player_name", "status": "roster_status"})
        rosters["team"] = _team(rosters.team)
        rosters = rosters.dropna(subset=["player_id"]).drop_duplicates(keys)
        roster_cols = keys + ["player_name", "position", "roster_status"]
        merged = rosters[roster_cols].merge(stats, on=keys, how="outer", suffixes=("", "_stat"), validate="one_to_one")
        for col in ["player_name", "position"]:
            merged[col] = merged[col + "_stat"].combine_first(merged[col])
        merged = merged.drop(columns=["player_name_stat", "position_stat"])
        merged = merged.merge(schedule, on=["season", "week", "team"], how="inner", validate="many_to_one")

        snap_path = raw / f"snap_counts_{year}.parquet"
        if snap_path.exists():
            snaps = pd.read_parquet(snap_path)
            _require(snaps, {"pfr_player_id", "game_id", "team", "position", "offense_snaps", "defense_snaps", "st_snaps"}, "snap_counts")
            snaps = snaps[snaps.position.isin(POSITIONS)].copy()
            snaps["team"] = _team(snaps.team)
            snaps = snaps.merge(players.rename(columns={"pfr_id": "pfr_player_id", "gsis_id": "player_id"}), on="pfr_player_id", how="inner", validate="many_to_one")
            snapkeys = ["game_id", "team", "player_id"]
            snaps = snaps.drop_duplicates(snapkeys)
            # Preserve snap-only participants even if no eligible roster/stat row.
            extra = snaps.merge(merged[snapkeys], on=snapkeys, how="left", indicator=True)
            extra = extra[(extra._merge == "left_only") & (extra[["offense_snaps", "defense_snaps", "st_snaps"]].sum(axis=1) > 0)]
            if not extra.empty:
                extra = extra[["game_id", "team", "player_id", "player", "position"]].rename(columns={"player": "player_name"})
                extra = extra.merge(schedule, on=["game_id", "team"], validate="many_to_one")
                merged = pd.concat([merged, extra], ignore_index=True)
            merged = merged.merge(snaps[snapkeys + ["offense_snaps", "defense_snaps", "st_snaps"]], on=snapkeys, how="left", validate="one_to_one")
        else:
            for col in ["offense_snaps", "defense_snaps", "st_snaps"]:
                merged[col] = np.nan
        observed = merged.stats_observed.eq(True)
        snapped = merged[["offense_snaps", "defense_snaps", "st_snaps"]].sum(axis=1, min_count=1).gt(0)
        merged["participation_state"] = np.select([observed | snapped, merged.roster_status.eq("INA")], ["played", "DNP"], default="unknown")
        merged["participation_evidence"] = np.select([observed, snapped, merged.roster_status.eq("INA")], ["weekly_stat_event", "positive_snap_count", "explicit_weekly_inactive"], default="no_positive_or_inactive_evidence")
        merged["stats_observed"] = observed
        merged = merged.merge(team_stats, on=["season", "week", "team"], how="left", validate="many_to_one")
        merged["rush_rec_yd"] = merged[["rush_yd", "rec_yd"]].sum(axis=1, min_count=2)
        td_known = merged[["rush_td", "rec_td"]].notna().all(axis=1)
        merged["anytime_td"] = np.where(td_known, (merged.rush_td + merged.rec_td > 0).astype(float), np.nan)
        merged["fantasy_ppr"] = np.nan
        merged["fantasy_ppr_missing_reason"] = "incomplete_nflverse_to_pinned_sleeper_crosswalk"
        merged["outcome_available_utc"] = merged.kickoff_utc + pd.Timedelta(days=7)
        merged["historical_publication_utc"] = pd.NaT
        merged["history_vintage"] = VINTAGE
        tables.append(merged)
    history = pd.concat(tables, ignore_index=True).sort_values(["kickoff_utc", "game_id", "player_id"]).reset_index(drop=True)
    if history.duplicated(["game_id", "player_id"]).any():
        raise ValueError("ambiguous player/game identity after source joins")
    if history.kickoff_utc.isna().any():
        raise ValueError("missing kickoff prevents chronological features")
    processed = cache / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    history.to_parquet(processed / "history.parquet", index=False)
    profile = {"rows": len(history), "seasons": seasons, "elapsed_seconds": round(time.monotonic() - started, 3),
               "participation": history.participation_state.value_counts().to_dict(),
               "missing_by_target": {t: int(history[t].isna().sum()) for t in TARGETS},
               "stats_missing_played": int((history.participation_state.eq("played") & ~history.stats_observed).sum()),
               "sha256": _sha(processed / "history.parquet"), "vintage": VINTAGE}
    (processed / "history_profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    history.attrs["profile"] = profile
    return history
