"""Public earlier-game scheme/pace context; no private plans or weather forecasts.

The unchanged shared schedule/identity adapter binds public PBP to team games.
Current-vintage metadata uses an explicit seven-day reconstruction assumption,
not download time as historical availability. Target outcomes never enter their
own features. This optional group never alters the frozen base feature columns.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .data import BASE, VINTAGE, _schedule, _sha, _team

VERSION = "public-scheme-pace-prior-v1"
PBP_SHA256 = {
    2022: "931121d8897779d7944e2a293e92ed8799c8e5cceef84096ac42339003fedc09",
    2023: "bd3484731408def6b0ec93225bba2bd7b2c65769ca707a2b9444d891abdc6776",
}
PBP_COLUMNS = ["game_id", "season", "play_id", "posteam", "defteam", "play_type",
               "qb_kneel", "qb_spike", "qb_dropback", "shotgun", "no_huddle",
               "qtr", "down", "score_differential", "half_seconds_remaining",
               "yardline_100", "game_seconds_remaining", "drive"]
RATES = ("dropback_rate", "neutral_dropback_rate", "shotgun_rate", "no_huddle_rate",
         "redzone_dropback_rate", "redzone_exposure_rate")
MEANS = ("scrimmage_plays", "clock_runoff_seconds", "neutral_dropback_excess", "scrimmage_plays_excess")
SURFACE_ARTIFICIAL = {"fieldturf", "a_turf", "astroturf", "astroplay", "sportturf", "matrixturf"}
SURFACE_NATURAL = {"grass", "dessograss"}


def schedule_context(cache: Path, seasons: list[int]) -> pd.DataFrame:
    """Reuse the common schedule normalizer; read a narrow metadata whitelist."""
    raw = Path(cache) / "raw"
    schedule = _schedule(raw, seasons)
    fields = ["game_id", "season", "home_team", "away_team", "home_coach", "away_coach",
              "stadium_id", "roof", "surface"]
    available = pd.read_csv(raw / "schedules.csv", nrows=0).columns
    games = pd.read_csv(raw / "schedules.csv", usecols=[c for c in fields if c in available])
    games = games.loc[games.season.isin(seasons)].copy()
    for col in fields:
        if col not in games:
            games[col] = np.nan
    sides = []
    for own, coach in (("home_team", "home_coach"), ("away_team", "away_coach")):
        side = games[["game_id", own, coach, "stadium_id", "roof", "surface"]].rename(columns={own: "team", coach: "coach"})
        side["team"] = _team(side.team)
        sides.append(side)
    metadata = pd.concat(sides, ignore_index=True)
    result = schedule.merge(metadata, on=["game_id", "team"], how="left", validate="one_to_one")
    result["available_utc"] = result.kickoff_utc + pd.Timedelta(days=7)
    result["availability_basis"] = "reconstructed_kickoff_plus_7days"
    return result


def load_public_pbp(cache: Path, seasons: list[int]) -> pd.DataFrame:
    """Read cached, receipt-hash-verified PBP columns only; never acquire here."""
    tables, sources = [], []
    raw = Path(cache) / "raw"
    for season in sorted(set(seasons)):
        if season not in {2022, 2023}:
            raise ValueError("scheme_registration_allows_only_2022_2023_pbp")
        name = f"play_by_play_{season}.parquet"
        path = raw / name
        receipt = json.loads((raw / (name + ".receipt.json")).read_text())
        if (receipt.get("url") != f"{BASE}/pbp/{name}"
                or receipt.get("sha256") != PBP_SHA256[season]
                or receipt.get("sha256") != _sha(path)):
            raise ValueError("pbp_source_identity_or_content_mismatch")
        if path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("pbp_source_exceeds_registered_budget")
        table = pd.read_parquet(path, columns=PBP_COLUMNS)
        if not table.season.eq(season).all():
            raise ValueError("pbp_asset_season_mismatch")
        tables.append(table)
        sources.append({**receipt, "receipt_sha256": _sha(raw / (name + ".receipt.json")),
                        "used_columns": PBP_COLUMNS})
    result = pd.concat(tables, ignore_index=True)
    result.attrs["manifest"] = {
        "adapter": VERSION, "sources": sources,
        "schedules_sha256": _sha(raw / "schedules.csv"),
        "schedules_receipt_sha256": _sha(raw / "schedules.csv.receipt.json"),
        "upstream_license_sha256": _sha(raw / "nflverse_LICENSE.md"),
        "rights": "nflverse public source credit; upstream NFL/other rights separate; lab publishes no raw or player-game source rows",
        "field_dictionary": "https://nflreadr.nflverse.com/articles/dictionary_pbp.html",
        "vintage": VINTAGE,
        "availability": "kickoff+7days reconstruction; original historical publication and revisions unauthenticated",
        "unavailable_inputs": ["authentic historical forecast weather", "routes/personnel/coverage counts", "private gameplans", "authenticated injury/news snapshots"],
    }
    return result


def aggregate_pbp(pbp: pd.DataFrame, schedule: pd.DataFrame) -> pd.DataFrame:
    """Return a complete schedule game/team grid including missing PBP slots."""
    if set(PBP_COLUMNS) - set(pbp):
        raise ValueError("missing_public_pbp_schema")
    if pbp.duplicated(["game_id", "play_id"]).any():
        raise ValueError("duplicate_public_play_identity")
    frame = pbp.copy().sort_values(["game_id", "play_id"])
    for col in ("posteam", "defteam"):
        frame[col] = _team(frame[col])
    numeric = [c for c in PBP_COLUMNS if c not in {"game_id", "posteam", "defteam", "play_type"}]
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    valid = (frame.play_type.isin(["pass", "run"]) & frame.qb_kneel.eq(0) & frame.qb_spike.eq(0)
             & frame.posteam.notna() & frame.defteam.notna())
    neutral = (frame.qtr.between(1, 3) & frame.down.isin([1, 2])
               & frame.score_differential.abs().le(7) & frame.half_seconds_remaining.gt(120))
    yard_known = frame.yardline_100.between(0, 100)
    redzone = yard_known & frame.yardline_100.le(20)
    previous = frame.shift(1)
    adjacent = (valid & valid.shift(1, fill_value=False) & frame.game_id.eq(previous.game_id)
                & frame.posteam.eq(previous.posteam) & frame.drive.eq(previous.drive) & frame.qtr.eq(previous.qtr))
    runoff = previous.game_seconds_remaining - frame.game_seconds_remaining
    runoff = runoff.where(adjacent & runoff.gt(0) & runoff.le(60))
    working = frame.loc[valid, ["game_id", "posteam", "defteam"]].copy()
    working["scrimmage_plays"] = 1.
    working["clock_runoff_seconds"] = runoff.loc[valid]
    for metric, values, selection in (
        ("dropback_rate", frame.qb_dropback, pd.Series(True, index=frame.index)),
        ("neutral_dropback_rate", frame.qb_dropback, neutral),
        ("shotgun_rate", frame.shotgun, pd.Series(True, index=frame.index)),
        ("no_huddle_rate", frame.no_huddle, pd.Series(True, index=frame.index)),
        ("redzone_dropback_rate", frame.qb_dropback, redzone),
        ("redzone_exposure_rate", redzone.astype(float), yard_known),
    ):
        known = values.isin([0, 1]) & selection
        working[metric + "_num"] = values.where(known).loc[valid]
        working[metric + "_den"] = known.astype(float).loc[valid]
    aggregations = {"scrimmage_plays": "sum", "clock_runoff_seconds": "mean"}
    for metric in RATES:
        aggregations[metric + "_num"] = lambda values: values.sum(min_count=1)
        aggregations[metric + "_den"] = "sum"
    grouped = working.groupby(["game_id", "posteam", "defteam"], as_index=False).agg(aggregations)
    # Retain the common schedule grid: missing games consume a prior slot.
    result = schedule.copy().reset_index(drop=True)
    if result.duplicated(["game_id", "team"]).any():
        raise ValueError("duplicate_scheme_schedule_identity")
    observed_identity = grouped[["game_id", "posteam", "defteam"]].rename(columns={"posteam": "team", "defteam": "opponent"})
    binding = observed_identity.merge(result[["game_id", "team", "opponent"]], on=["game_id", "team"], how="left", suffixes=("_pbp", "_schedule"), validate="one_to_one")
    if binding.opponent_schedule.isna().any() or binding.opponent_pbp.ne(binding.opponent_schedule).any():
        raise ValueError("pbp_schedule_team_opponent_mismatch")
    for role, team_col in (("offense", "posteam"), ("defense", "defteam")):
        side = grouped.drop(columns=["defteam" if team_col == "posteam" else "posteam"]).rename(columns={team_col: "team"})
        side = side.rename(columns={col: role + "_" + col for col in side if col not in {"game_id", "team"}})
        result = result.merge(side, on=["game_id", "team"], how="left", validate="one_to_one")
    result.attrs["source_profile"] = {"source_play_rows": len(frame), "competitive_scrimmage_rows": int(valid.sum()),
                                      "source_games": int(frame.game_id.nunique()),
                                      "scheduled_team_games": len(result),
                                      "team_games_missing_pbp": int(result.offense_scrimmage_plays.isna().sum())}
    return result


def _windows(source: pd.DataFrame, query: pd.DataFrame, *, role: str,
             metrics: tuple[str, ...], team_column: str = "team",
             prior_games: int = 3, max_age_days: int = 60) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Exact chronological game slots, pooled rate exposures, strict availability."""
    output = {metric + suffix: np.full(len(query), np.nan if suffix == "_mean3" else 0.)
              for metric in metrics for suffix in ("_mean3", "_n3")}
    maximum = np.full(len(query), np.iinfo(np.int64).min, dtype=np.int64)
    groups = {key: rows.sort_values(["available_utc", "kickoff_utc", "game_id"])
              for key, rows in source.groupby("team", dropna=True, sort=False)}
    cutoff = pd.to_datetime(query.cutoff_utc, utc=True).astype("int64").to_numpy()
    for team, positions in query.groupby(team_column, sort=False, dropna=True).indices.items():
        history = groups.get(team)
        if history is None or history.empty:
            continue
        positions = np.asarray(positions)
        available = pd.to_datetime(history.available_utc, utc=True).astype("int64").to_numpy()
        kicks = pd.to_datetime(history.kickoff_utc, utc=True).astype("int64").to_numpy()
        right = np.searchsorted(available, cutoff[positions], side="left")
        slots = right[:, None] - np.arange(1, prior_games + 1)[None, :]
        valid = slots >= 0
        safe = np.maximum(slots, 0)
        eligible = (valid & (available[safe] < cutoff[positions, None])
                    & (available[safe] != np.iinfo(np.int64).min)
                    & (kicks[safe] < cutoff[positions, None])
                    & (cutoff[positions, None] - kicks[safe] <= pd.Timedelta(days=max_age_days).value))
        used = np.zeros(eligible.shape, dtype=bool)
        for metric in metrics:
            column = role + "_" + metric
            if metric in RATES:
                numerator = history[column + "_num"].to_numpy(dtype=float)[safe]
                denominator = history[column + "_den"].to_numpy(dtype=float)[safe]
                known = eligible & np.isfinite(numerator) & np.isfinite(denominator) & (denominator > 0)
                numerators = np.where(known, numerator, 0).sum(axis=1)
                denominators = np.where(known, denominator, 0).sum(axis=1)
                value = np.divide(numerators, denominators, out=np.full(len(positions), np.nan), where=denominators > 0)
            else:
                values = history[column].to_numpy(dtype=float)[safe]
                known = eligible & np.isfinite(values)
                count = known.sum(axis=1)
                value = np.divide(np.where(known, values, 0).sum(axis=1), count,
                                  out=np.full(len(positions), np.nan), where=count > 0)
            output[metric + "_mean3"][positions] = value
            output[metric + "_n3"][positions] = known.sum(axis=1)
            used |= known
        maximum[positions] = np.where(used, available[safe], np.iinfo(np.int64).min).max(axis=1)
    return output, maximum


def opponent_adjusted_history(games: pd.DataFrame) -> pd.DataFrame:
    """Adjust each historical exposure against that game's earlier opponent."""
    result = games.copy()
    query = result.copy()
    query["cutoff_utc"] = query.kickoff_utc
    for role, opposite in (("offense", "defense"), ("defense", "offense")):
        expected, _ = _windows(result, query, role=opposite,
                                metrics=("neutral_dropback_rate", "scrimmage_plays"), team_column="opponent")
        denominator = result[role + "_neutral_dropback_rate_den"]
        rate = result[role + "_neutral_dropback_rate_num"].div(denominator.where(denominator > 0))
        result[role + "_neutral_dropback_excess"] = rate - expected["neutral_dropback_rate_mean3"]
        result[role + "_scrimmage_plays_excess"] = result[role + "_scrimmage_plays"] - expected["scrimmage_plays_mean3"]
    result.attrs = games.attrs.copy()
    return result


def merge_scheme_asof(features: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Append one registered optional group; retain all input rows and values."""
    keys = {"game_id", "player_id", "team", "opponent", "kickoff_utc"}
    if keys - set(features) or {"game_id", "team", "kickoff_utc", "available_utc", "coach", "stadium_id", "roof", "surface"} - set(games):
        raise ValueError("scheme_identity_schema_missing")
    if features.duplicated(["game_id", "player_id"]).any() or games.duplicated(["game_id", "team"]).any():
        raise ValueError("duplicate_scheme_identity")
    index = features.index.copy()
    out = features.copy().reset_index(drop=True)
    cutoff = pd.to_datetime(out.get("cutoff_utc", out.kickoff_utc), utc=True)
    kickoff = pd.to_datetime(out.kickoff_utc, utc=True)
    if cutoff.isna().any() or (cutoff > kickoff).any():
        raise ValueError("scheme_cutoff_after_kickoff_or_unknown")
    query = out[["game_id", "team", "opponent", "kickoff_utc"]].copy()
    query["cutoff_utc"] = cutoff
    source = games.copy()
    source["kickoff_utc"] = pd.to_datetime(source.kickoff_utc, utc=True)
    source["available_utc"] = pd.to_datetime(source.available_utc, utc=True)
    floor = source.kickoff_utc + pd.Timedelta(days=7)
    if (source.available_utc < floor).any():
        raise ValueError("scheme_source_availability_precedes_seven_day_floor")
    if source.available_utc.isna().any() or source.kickoff_utc.isna().any():
        raise ValueError("scheme_source_unknown_clock")
    binding = query.merge(source[["game_id", "team", "opponent", "kickoff_utc", "stadium_id"]],
                          on=["game_id", "team"], how="left", suffixes=("_target", "_source"), validate="many_to_one")
    found = binding.kickoff_utc_source.notna()
    if ((found & binding.kickoff_utc_target.ne(binding.kickoff_utc_source))
            | (found & binding.opponent_target.ne(binding.opponent_source))).any():
        raise ValueError("scheme_schedule_target_identity_mismatch")
    additions = {}
    max_source = np.full(len(out), np.iinfo(np.int64).min, dtype=np.int64)
    for role, lookup in (("offense", "team"), ("defense", "opponent")):
        values, maximum = _windows(source, query, role=role, metrics=RATES + MEANS, team_column=lookup)
        additions.update({f"f_scheme_{role}_{key}": value for key, value in values.items()})
        max_source = np.maximum(max_source, maximum)
    # Rest uses strictly earlier schedule dates, not their realised statistics.
    rest = np.full(len(out), np.nan)
    coach_change = np.full(len(out), np.nan)
    coach_n = np.zeros(len(out))
    cutoff_ns = cutoff.astype("int64").to_numpy()
    for team, positions in query.groupby("team", sort=False).indices.items():
        positions = np.asarray(positions)
        history = source.loc[source.team.eq(team)].sort_values("kickoff_utc")
        if history.empty:
            continue
        kicks = history.kickoff_utc.astype("int64").to_numpy()
        earlier = np.searchsorted(kicks, cutoff_ns[positions], side="left") - 1
        supported = earlier >= 0
        safe = np.maximum(earlier, 0)
        rest[positions[supported]] = (kickoff.astype("int64").to_numpy()[positions[supported]] - kicks[safe[supported]]) / pd.Timedelta(days=1).value
        coach_history = history.sort_values(["available_utc", "kickoff_utc"])
        available = coach_history.available_utc.astype("int64").to_numpy()
        coach_kicks = coach_history.kickoff_utc.astype("int64").to_numpy()
        right = np.searchsorted(available, cutoff_ns[positions], side="left")
        slots = right[:, None] - np.arange(1, 4)[None, :]
        safe = np.maximum(slots, 0)
        age_ok = cutoff_ns[positions, None] - coach_kicks[safe] <= pd.Timedelta(days=60).value
        coaches = coach_history.coach.replace(r"^\s*$", np.nan, regex=True).to_numpy()[safe]
        known = ((slots >= 0) & age_ok & pd.notna(coaches)
                 & (available[safe] < cutoff_ns[positions, None]))
        coach_n[positions] = known.sum(axis=1)
        pair = known[:, 0] & known[:, 1]
        coach_change[positions[pair]] = (coaches[pair, 0] != coaches[pair, 1]).astype(float)
        coach_used = np.where(known, available[safe], np.iinfo(np.int64).min).max(axis=1)
        max_source[positions] = np.maximum(max_source[positions], coach_used)
    additions["f_scheme_rest_days"] = rest
    additions["f_scheme_coach_change_prior"] = coach_change
    additions["f_scheme_coach_known_n3"] = coach_n
    # Upcoming venue identity is schedule context; only old same-venue roof and
    # surface observations supply numerical values. No target realised field.
    venue = source.drop_duplicates("game_id").copy()
    venue["team"] = venue.stadium_id
    roof = venue.roof.astype("string").str.lower()
    surface = venue.surface.astype("string").str.lower()
    venue["venue_roof_closed"] = np.where(roof.isin(["dome", "closed"]), 1., np.where(roof.isin(["outdoors", "open"]), 0., np.nan))
    venue["venue_artificial"] = np.where(surface.isin(SURFACE_ARTIFICIAL), 1., np.where(surface.isin(SURFACE_NATURAL), 0., np.nan))
    venue_query = query.copy()
    venue_query["team"] = binding.stadium_id.to_numpy()
    values, maximum = _windows(venue, venue_query, role="venue", metrics=("roof_closed", "artificial"))
    additions.update({"f_scheme_venue_" + key: value for key, value in values.items()})
    max_source = np.maximum(max_source, maximum)
    extra = pd.DataFrame(additions, index=out.index)
    if set(extra) & set(out):
        raise ValueError("scheme_feature_group_already_present")
    result = pd.concat([out, extra], axis=1)
    result["scheme_feature_max_source_available_utc"] = pd.to_datetime(max_source, utc=True)
    populated = result.scheme_feature_max_source_available_utc.notna()
    if (result.loc[populated, "scheme_feature_max_source_available_utc"].to_numpy() >= cutoff[populated].to_numpy()).any():
        raise ValueError("scheme_prior_feature_cutoff_violation")
    result.index = index
    result.attrs = features.attrs.copy()
    result.attrs["scheme_context"] = {"version": VERSION, "feature_columns": list(extra),
        "base_features_changed": False, "source_profile": games.attrs.get("source_profile"),
        "availability": "reconstructed kickoff+7d; strict earlier cutoff; exact3 game slots; maxage60days",
        "roof_surface": "earlier same-venue observations only; not a forecast of target roof/weather",
        "coach": "lagged observed change only; no target coach plan", "rest": "strictly prior schedule kickoff dates only"}
    return result
