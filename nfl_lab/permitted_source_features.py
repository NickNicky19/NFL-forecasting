"""Rebuild private research inputs without PFR rows, participation or features.

The shared normalizer and feature builder remain unchanged. A private raw
whitelist makes snap files unavailable. Explicit NFL physical events qualify
playing; all other roster/stat rows remain present with unknown participation.
This module performs no acquisition, fitting, prediction or scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, features, website_cdf_features as original
from .rb_readiness import ACTION_FIELDS, SNAP_FIELDS

VERSION = "permitted-nfl-source-features-v1-20261023"
OUTPUT = Path("/workspace/website-methods-research/resumed/median-boosting-20261023/permitted-source")
SOURCE_CACHE = Path("/workspace/NFL-forecasting/data")
PRIOR_FILTER = [("season", "==", 2026), ("week", ">=", 1), ("week", "<=", 5), ("season_type", "==", "REG")]
ROSTER_FILTER = [("season", "==", 2026), ("week", ">=", 1), ("week", "<=", 5), ("game_type", "==", "REG")]
SCHEDULE_COLUMNS = ["game_id", "season", "week", "gameday", "gametime", "away_team", "home_team"]
SIGNED_ACTION_FIELDS = (
    "passing_yards", "rushing_yards", "receiving_yards", "sack_yards_lost",
    "kickoff_return_yards", "punt_return_yards", "misc_yards", "def_interception_yards",
    "fumble_recovery_yards_own", "fumble_recovery_yards_opp", "pt_yards",
)
PHYSICAL_COUNT_FIELDS = ACTION_FIELDS
PHYSICAL_EVENT_SEMANTICS = {
    "counts": "positive finite official action credits: attempts, targets/catches, carries, sacks suffered, two-point conversions, tackles/defensive actions, returns, kicking/punting attempts, fumbles and recoveries",
    "signed_production": "finite nonzero official yardage in passing/rushing/receiving, sacks suffered, returns, recoveries, interceptions, punting or misc play production; negative production is physical evidence",
    "excluded": "penalties and penalty yards, row existence, zero-only statistics, roster ACT/INA and current player position never establish game participation",
    "limit": "sufficient positive evidence only; absence never certifies DNP or a complete participant population",
}


def physical_event_evidence(stats: pd.DataFrame) -> pd.Series:
    """Positive physical counts or nonzero signed production; never penalties."""
    count_fields = [c for c in PHYSICAL_COUNT_FIELDS if c in stats]
    yard_fields = [c for c in SIGNED_ACTION_FIELDS if c in stats]
    if not count_fields or not yard_fields:
        raise ValueError("official physical-event schema missing")
    counts = stats[count_fields].apply(pd.to_numeric, errors="coerce")
    yards = stats[yard_fields].apply(pd.to_numeric, errors="coerce")
    return ((counts.gt(0) & np.isfinite(counts)).any(axis=1)
            | (yards.ne(0) & np.isfinite(yards)).any(axis=1))


def qualify_history(history: pd.DataFrame, raw_stats: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Preserve every row, but unsupported playing cannot train or fill windows."""
    keys = ["season", "week", "team", "player_id"]
    if raw_stats.duplicated(keys).any():
        raise ValueError("duplicate raw player/team/week")
    proof = raw_stats[keys].copy()
    proof["team"] = data._team(proof.team)
    proof["official_physical_event"] = physical_event_evidence(raw_stats).to_numpy()
    out = history.merge(proof, on=keys, how="left", validate="one_to_one")
    if len(out) != len(history):
        raise ValueError("source qualification changed roster/stat denominator")
    played = out.official_physical_event.eq(True)
    out["participation_state"] = np.where(played, "played", "unknown")
    out["participation_evidence"] = np.where(played, "positive_official_nfl_physical_event", "no_game_specific_participation_contract")
    fields = list(dict.fromkeys([*data.STAT_MAP.values(), "rush_rec_yd", "anytime_td", "fantasy_ppr"]))
    unsupported_explicit = {c: int((~played & out[c].notna()).sum()) for c in fields if c in out}
    # Raw explicit values remain in the hash-bound raw files. The feature/fit
    # view only supports conditional-on-playing outcomes with separate proof.
    out.loc[~played, [c for c in fields if c in out]] = np.nan
    for field in SNAP_FIELDS:
        if field in out and out[field].notna().any():
            raise ValueError("forbidden snap source reached clean normalizer")
        out[field] = np.nan
    out["fantasy_ppr"] = np.nan
    out["source_policy"] = VERSION
    out.attrs.clear()
    return out, {"rows": len(out), "played_official_physical_event": int(played.sum()),
                 "unknown_participation": int((~played).sum()), "confirmed_dnp": 0,
                 "roster_status_counts": out.roster_status.value_counts(dropna=False).to_dict(),
                 "explicit_values_masked_without_participation": unsupported_explicit,
                 "zero_policy": "raw explicit zeros retained privately; conditional feature/fit values require separate positive official physical evidence",
                 "unknown_slots": "all ACT/INA eligible roster and official-stat rows retained; unknown rows consume original rolling slots"}


def _source_receipt(path: Path) -> dict:
    receipt_path = path.with_name(path.name + ".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("status") not in {"acquired", "stale_cache"} or receipt.get("sha256") != data._sha(path):
        raise ValueError("source body/receipt mismatch: " + path.name)
    return {**receipt, "path": str(path), "receipt_sha256": data._sha(receipt_path)}


def prepare_raw_namespace(source_cache: Path, output: Path) -> tuple[Path, dict]:
    """Whitelist named existing raw files; never copy a processed source table."""
    source_raw = Path(source_cache) / "raw"
    cache = Path(output) / "cache"
    raw = cache / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    allowed = {"players.parquet", "schedules.csv"}
    allowed |= {f"{kind}_{year}.parquet" for kind in ("stats_player_week", "roster_weekly") for year in range(2019, 2027)}
    unexpected = [p.name for p in raw.iterdir() if p.name.removesuffix(".receipt.json") not in allowed]
    if unexpected:
        raise ValueError("private cache contains non-whitelisted file: " + str(unexpected))
    sources = {}
    for name in sorted(allowed):
        path = source_raw / name
        receipt = _source_receipt(path)
        sources[name] = receipt
        dest = raw / name
        if name in {"stats_player_week_2026.parquet", "roster_weekly_2026.parquet"}:
            filters = PRIOR_FILTER if name.startswith("stats") else ROSTER_FILTER
            frame = pd.read_parquet(path, filters=filters)
            if not (frame.season.eq(2026) & frame.week.between(1, 5)).all():
                raise ValueError("2026 subset outside fixed prior window")
            frame.attrs.clear()
            frame.to_parquet(dest, index=False)
            sources[name]["private_subset"] = {"path": str(dest), "sha256": data._sha(dest), "rows": len(frame), "parquet_read_filters": filters}
        elif name == "schedules.csv":
            frame = pd.read_csv(path, usecols=SCHEDULE_COLUMNS)
            frame = frame[frame.season.between(2019, 2025) | (frame.season.eq(2026) & frame.week.between(1, 5))]
            frame.to_csv(dest, index=False)
            sources[name]["private_subset"] = {"path": str(dest), "sha256": data._sha(dest), "columns_read": SCHEDULE_COLUMNS, "rows": len(frame)}
        else:
            if dest.exists() or dest.is_symlink():
                if dest.resolve() != path.resolve():
                    raise ValueError("private source path already bound elsewhere")
            else:
                dest.symlink_to(path)
        # This receipt belongs to the original bytes. Subset hashes and exact
        # transforms live separately in source-proof.json, never impersonating
        # the upstream artifact or its original availability.
        receipt_dest = raw / (name + ".receipt.json")
        original_receipt = path.with_name(name + ".receipt.json")
        if not receipt_dest.exists():
            receipt_dest.symlink_to(original_receipt)
    return cache, sources


def original_query_context(protocol_path: Path = original.DEFAULT_PROTOCOL) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Only original baseline/board/calendar and an identity-only crosswalk."""
    protocol = json.loads(Path(protocol_path).read_text())
    documents, pins = {}, {}
    for name in ("original_baseline", "exact_original_board", "saved_calendar"):
        pin = protocol["inputs"][name]
        path = Path(pin["path"])
        if data._sha(path) != pin["sha256"] or path.stat().st_size != pin["bytes"]:
            raise ValueError("original context input changed: " + name)
        documents[name] = original.document(path)
        pins[name] = pin
    baseline, board, calendar = (documents[n] for n in ("original_baseline", "exact_original_board", "saved_calendar"))
    cutoff = original.stamp(baseline["captured_at"])
    if not max(original.stamp(board["generated_at"]), original.stamp(calendar["generated_at"])) < cutoff:
        raise ValueError("original context clock violation")
    if data._sha(original.IDENTITY_COHORT) != original.IDENTITY_COHORT_SHA256:
        raise ValueError("identity-only original cohort changed")
    identity = pd.read_parquet(original.IDENTITY_COHORT, columns=["player_id", "canonical_player_id", "identity_binding"]).drop_duplicates()
    exact = identity[identity.identity_binding.eq("exact_current_vintage_sleeper_gsis")]
    if exact.player_id.duplicated().any() or exact.canonical_player_id.duplicated().any():
        raise ValueError("ambiguous original identity binding")
    ids = dict(exact[["player_id", "canonical_player_id"]].itertuples(index=False, name=None))
    players = {(str(p["id"]), str(p["game_id"])): p for p in board["players"]}
    games = {str(g["id"]): g for g in calendar["schedule"]}
    selected, opportunities = {}, []
    for receipt in baseline["rows"]:
        sid, gid = str(receipt["player_id"]), str(receipt["game_id"])
        player, game = players[(sid, gid)], games[gid]
        if (receipt["season"], receipt["week"], receipt["position"], receipt["team"]) != (board["season"], board["week"], player["pos"], player["team"]):
            raise ValueError("original identity context mismatch")
        if original.stamp(receipt["kickoff"]) != original.stamp(game["kickoff"]) or not cutoff < original.stamp(game["kickoff"]):
            raise ValueError("original kickoff/cutoff mismatch")
        if original._opponent(game, player["team"]) != player["opp"] or int(game["w"]) != int(board["week"]):
            raise ValueError("original opponent/week mismatch")
        prop = {p["key"]: p for p in player["props"]}[receipt["category"]]
        if (receipt["raw_projection"], receipt["adjusted_projection"]) != (prop.get("proj"), prop.get("adj")):
            raise ValueError("original literal comparator mismatch")
        output_id = "sleeper:" + sid
        selected[(sid, gid)] = {"season": int(board["season"]), "week": int(board["week"]), "game_id": gid,
            "player_id": output_id, "canonical_player_id": ids.get(output_id), "position": player["pos"],
            "team": player["team"], "opponent": player["opp"], "kickoff_utc": original.stamp(game["kickoff"]),
            "cutoff_utc": cutoff, "outcome_available_utc": original.stamp(game["kickoff"]) + pd.Timedelta(days=7),
            "is_home": player["team"] == game["home"], "original_board_generated_at": original.stamp(board["generated_at"]),
            "calendar_generated_at": original.stamp(calendar["generated_at"])}
        opportunities.append({"season": int(board["season"]), "week": int(board["week"]), "game_id": gid, "player_id": output_id,
            "target": original.CATEGORY_MAP[receipt["category"]], "original_category": receipt["category"],
            "website_point": receipt["adjusted_projection"], "raw_point": receipt["raw_projection"],
            "website_probability": prop.get("td_chance") if receipt["category"] == "anytime_td" else None,
            "raw_probability": np.nan, "simple_point": np.nan, "simple_probability": np.nan,
            "comparator_provenance": "hash_bound_original_receipt_and_board",
            "category_state": "BLOCKED_EXACT_PPR_SOURCE_CONTRACT" if receipt["category"] == "fpts" else "QUERY_READY"})
    queries = pd.DataFrame(selected.values())
    offers = pd.DataFrame(opportunities)
    if len(queries) != 396 or len(offers) != 2083 or queries.canonical_player_id.notna().sum() != 393:
        raise ValueError("original 396/2083/393 population changed")
    if offers.duplicated(original.KEYS + ["target"]).any():
        raise ValueError("duplicate original offered category")
    return queries, offers, {"inputs": pins, "identity_only_cohort": {"path": str(original.IDENTITY_COHORT), "sha256": original.IDENTITY_COHORT_SHA256, "columns_read": ["player_id", "canonical_player_id", "identity_binding"]}}


def query_features(history: pd.DataFrame, contexts: pd.DataFrame) -> pd.DataFrame:
    """Recompute all query features from clean raw-derived history only."""
    if not (history.season.between(2019, 2025) | (history.season.eq(2026) & history.week.between(1, 5))).all():
        raise ValueError("future/target history forbidden")
    source = history.copy()
    source["cutoff_utc"] = source.kickoff_utc
    query = contexts.copy()
    query["_output_player_id"] = query.player_id
    query["player_id"] = query.canonical_player_id.fillna(query.player_id)
    query["_query_index"] = np.arange(len(query))
    query["participation_state"] = "unknown"
    for c in features.PLAYER_STATS + ["team_stat_" + c for c in features.TEAM_STATS]:
        query[c] = np.nan
    combined = features.build_features(pd.concat([source, query], ignore_index=True))
    result = combined[combined._query_index.notna()].sort_values("_query_index").copy()
    result["player_id"] = result._output_player_id
    result["feature_max_assumed_history_available_utc"] = result.feature_max_source_available_utc
    result["feature_max_source_available_utc"] = [max([b, c] + ([h] if pd.notna(h) else [])) for b, c, h in zip(
        result.original_board_generated_at, result.calendar_generated_at, result.feature_max_assumed_history_available_utc)]
    result["feature_adapter_version"] = VERSION
    result["identity_binding"] = np.where(result.canonical_player_id.notna(), "exact_current_vintage_sleeper_gsis", "unlinked_cold_role_prior")
    result["evidence_lane"] = "current-vintage exploratory reconstruction; seven-day assumed historical availability; no PFR sources"
    keep = original.KEYS + ["position", "team", "opponent", "kickoff_utc", "cutoff_utc", "outcome_available_utc", "canonical_player_id", "participation_state", "feature_max_source_available_utc", "feature_max_assumed_history_available_utc", "feature_adapter_version", "identity_binding", "evidence_lane", "original_board_generated_at", "calendar_generated_at"]
    keep += [c for c in result if c.startswith("f_")]
    result = result[keep].reset_index(drop=True)
    result.attrs.clear()
    return result


def run(output: Path = OUTPUT, source_cache: Path = SOURCE_CACHE) -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cache, bindings = prepare_raw_namespace(source_cache, output)
    normalized = data.load_history(cache, list(range(2019, 2027)))
    raw = pd.concat([pd.read_parquet(cache / "raw" / f"stats_player_week_{year}.parquet") for year in range(2019, 2027)], ignore_index=True)
    history, qualification = qualify_history(normalized, raw)
    training_history = history[history.season.between(2019, 2025)].copy()
    training_features = features.build_features(training_history)
    training_features.attrs.clear()
    contexts, offers, original_pins = original_query_context()
    query = query_features(history, contexts)
    from .cdf_engine import assert_clock_contract
    assert_clock_contract(query)
    if not query.loc[query.canonical_player_id.isna(), "f_player_games_prior"].eq(0).all():
        raise ValueError("unlinked original players are not cold")
    for frame in (training_features, query):
        if not frame.f_player_offense_snaps_n3.eq(0).all() or not frame.f_player_offense_snaps_n8.eq(0).all():
            raise ValueError("forbidden snap counts reached features")
        if frame.f_player_offense_snaps_mean3.notna().any() or frame.f_player_offense_snaps_mean8.notna().any():
            raise ValueError("forbidden snap means reached features")
    artifacts = {"source_history.parquet": training_history, "features.parquet": training_features,
                 "query-source-history.parquet": history, "query-features.parquet": query, "opportunities.parquet": offers}
    for name, frame in artifacts.items():
        frame.attrs.clear()
        frame.to_parquet(output / name, index=False)
    report = {"version": VERSION, "models_fitted": 0, "predictions_or_scores": 0,
        "source_population_change": "eligible ACT/INA historical roster plus official NFLstat rows; all snap-only records removed, all unresolved participation retained unknown",
        "rights": "public NFLverse NFLstat/roster/player/schedule lineage; existing CC-BY hosting with upstream attribution retained; PFR-specific AI/ML grant not established, all PFRsnap event/participation/feature paths omitted",
        "availability": "current-vintage reconstruction; fixed kickoff+7d assumption; retrieval does not prove original publication",
        "sources": bindings, "original_context": original_pins, "qualification": qualification,
        "training_rows": len(training_history), "training_seasons": sorted(training_history.season.unique().tolist()),
        "training_participation": training_history.participation_state.value_counts().to_dict(),
        "query_source_rows_2026": int(history.season.eq(2026).sum()), "query_prior_weeks": sorted(history.loc[history.season.eq(2026), "week"].unique().tolist()),
        "query_rows": len(query), "all_original_offers": len(offers), "exact_gsis_bindings": int(query.canonical_player_id.notna().sum()),
        "unlinked_cold": int(query.canonical_player_id.isna().sum()), "target_outcomes_read": False,
        "full_team_totals": "unchanged shared loader aggregates all official NFLstat positions before selecting offensive player rows",
        "PPR": "blocked; exact rare components and sparse zero contract unresolved",
        "physical_event_qualification": {"count_fields": list(PHYSICAL_COUNT_FIELDS), "signed_fields": list(SIGNED_ACTION_FIELDS), "semantics": PHYSICAL_EVENT_SEMANTICS},
        "loader_hashes": {Path(m.__file__).name: data._sha(Path(m.__file__)) for m in (data, features)},
        "adapter_sha256": data._sha(Path(__file__)),
        "outputs": {n: {"path": str(output / n), "sha256": data._sha(output / n), "rows": len(f)} for n, f in artifacts.items()}}
    (output / "source-proof.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    return report


if __name__ == "__main__":
    report = run()
    print(json.dumps({k: report[k] for k in ("version", "models_fitted", "training_rows", "query_rows", "all_original_offers", "exact_gsis_bindings", "outputs")}, indent=2))
