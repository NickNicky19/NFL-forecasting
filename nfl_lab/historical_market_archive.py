"""Private archive ingestion and outcome-blind identity qualification.

No extraction, network, feature construction, outcome grading or persistence is
performed here. Callers own the approved private destination and its accounting.
The annual originals are authoritative; convenience subsets never add evidence.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

VERSION = "historical-market-archive-no2025-v1"
ALLOWED_SEASONS = frozenset({2022, 2023, 2024, 2026})
MARKETS = {
    "passing_yards": "pass_yd", "passing_tds": "pass_td",
    "completions": "pass_cmp", "attempts": "pass_att",
    "passing_interceptions": "pass_int", "rushing_yards": "rush_yd",
    "rushing_attempts": "rush_att", "receptions": "rec",
    "receiving_yards": "rec_yd", "rushing_receiving_yards": "rush_rec_yd",
    "anytime_touchdown_scorer": "anytime_td",
}
BOOKS = {15: ("CONSENSUS", "consensus"), 30: ("OPEN", "synthetic_open"),
         68: ("DraftKings NJ", "named"), 69: ("FanDuel NJ", "named"),
         79: ("bet365 NJ", "named")}
SOURCE_COLUMNS = (
    "bet_type", "event_id", "book_id", "action_network_player_id", "line_type",
    "period", "side", "value", "odds", "team", "join_name", "position",
    "position_group", "total_bets_on_event", "season", "week", "last_updated",
    "open_inferred", "open_source_book_id", "player_id",
)
OFFER_KEY = ["season", "week", "source_event_id", "source_player_id", "target",
             "period", "book_id", "side", "line"]
QUOTE_METADATA = ["american_odds", "player_id", "source_team", "source_position",
                  "source_collection_naive", "open_inferred", "open_source_book_id", "line_type"]
ROSTER_COLUMNS = {"season", "week", "player_id", "team", "position"}
SCHEDULE_COLUMNS = {"season", "week", "game_id", "team", "opponent", "kickoff_utc", "is_home"}
GSIS = re.compile(r"00-[0-9]{7}", re.ASCII)


def _counts(series):
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).items()}


def _reason(frame, mask, reason):
    """Append a code without discarding any earlier rejection."""
    mask = pd.Series(mask, index=frame.index).fillna(True)
    prior = frame.loc[mask, "rejection_reasons"]
    frame.loc[mask, "rejection_reasons"] = prior.where(prior.eq(""), prior + ";") + reason


def inspect_zip(path, *, verify_manifest=True):
    """Read one supplied ZIP in memory; return bytes plus aggregate provenance.

    ZIP paths and member names are never used as extraction destinations. Notes
    are read in full but source audit example rows are not returned or logged.
    """
    body = Path(path).read_bytes()
    archive = zipfile.ZipFile(io.BytesIO(body))
    prefixes = {name.split("/")[0] for name in archive.namelist()}
    if len(prefixes) != 1:
        raise ValueError("archive must have one season directory")
    prefix = prefixes.pop() + "/"
    match = re.fullmatch(r"NFL_Prop_History_(\d{4})/", prefix)
    if match is None or int(match[1]) not in ALLOWED_SEASONS:
        raise ValueError("excluded or unsupported archive season")
    season = int(match[1])
    manifest = json.loads(archive.read(prefix + "audit/file_manifest.json"))
    verified = []
    if verify_manifest:
        for item in manifest:
            payload = archive.read(prefix + item["file"])
            if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError("archive payload manifest mismatch")
            verified.append(item["file"])
    # Read all supplied textual notes/audits without reproducing private examples.
    note_hashes = {}
    for name in archive.namelist():
        if name.endswith((".txt", ".json")):
            payload = archive.read(name)
            payload.decode("utf-8-sig")
            note_hashes[name.removeprefix(prefix)] = hashlib.sha256(payload).hexdigest()
    original_member = prefix + f"originals/odds_data_pump/{season}.parquet"
    original = archive.read(original_member)
    receipt = {"version": VERSION, "season": season, "zip_name": Path(path).name,
               "zip_bytes": len(body), "zip_sha256": hashlib.sha256(body).hexdigest(),
               "member_bytes": {i.filename.removeprefix(prefix): i.file_size for i in archive.infolist()},
               "manifest_verified": verify_manifest, "verified_payloads": verified,
               "notes_and_audits_read_sha256": note_hashes,
               "original_member": original_member, "original_bytes": len(original),
               "original_sha256": hashlib.sha256(original).hexdigest(),
               "schema": str(pq.ParquetFile(io.BytesIO(original)).schema_arrow.remove_metadata()),
               "original_rows": pq.ParquetFile(io.BytesIO(original)).metadata.num_rows}
    return archive, original, receipt


def normalize_annual(table, *, source_sha256, source_member):
    """Return full-event eleven-market rows and references for every other row.

    No position filter is applied. Every input ordinal is represented either in
    rows or excluded; both retain its exact original row reference. Missing and
    malformed identities remain rejected rows. Source result columns are absent
    from the strict input contract, and collection clocks never qualify timing.
    """
    if set(table.column_names) != set(SOURCE_COLUMNS):
        raise ValueError("annual source schema changed")
    seasons = set(table["season"].to_pylist())
    if not seasons or not seasons <= ALLOWED_SEASONS:
        raise ValueError("2025 and unsupported seasons are excluded before normalization")
    if re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
        raise ValueError("exact source SHA256 required")
    target = pc.fill_null(pc.is_in(table["bet_type"], value_set=pa.array(list(MARKETS))), False)
    event = pc.fill_null(pc.equal(table["period"], "event"), False)
    keep = pc.and_(target, event)
    ordinal = pa.array(np.arange(len(table), dtype=np.int64))
    excluded_mask = pc.invert(keep)
    excluded = pd.DataFrame({
        "source_row_number": pc.filter(ordinal, excluded_mask).to_numpy(),
        "rejection_reasons": pd.Categorical.from_codes(
            pc.filter(target, excluded_mask).to_numpy().astype(np.int8),
            categories=["unsupported_market", "unsupported_period"]).remove_unused_categories(),
    })
    excluded["source_sha256"] = source_sha256
    excluded["source_member"] = source_member
    selected = table if pc.all(keep).as_py() else table.filter(keep)
    # Arrow category conversion keeps the largest annual source below the
    # qualification memory ceiling while retaining source string values exactly.
    frame = selected.to_pandas(strings_to_categorical=True)
    frame = frame.rename(columns={"event_id": "source_event_id", "action_network_player_id": "source_player_id",
                                  "value": "line", "odds": "american_odds", "team": "source_team",
                                  "position": "source_position", "last_updated": "source_collection_naive"})
    frame["source_row_number"] = pc.filter(ordinal, keep).to_numpy()
    frame["source_sha256"] = source_sha256
    frame["source_member"] = source_member
    frame["target"] = frame.bet_type.astype(object).map(MARKETS)
    frame["book_name"] = frame.book_id.map({k: v[0] for k, v in BOOKS.items()})
    frame["book_kind"] = frame.book_id.map({k: v[1] for k, v in BOOKS.items()}).fillna("unknown")
    frame["timing_lane"] = "timing-unverified exploratory"
    frame["timing_reason"] = "collection_clock_timezone_unverified_no_book_quote_clock"
    frame["identity_status"] = "source_gsis_unverified_historical_context"
    frame["rejection_reasons"] = ""
    valid_player = frame.player_id.astype(object).map(lambda v: isinstance(v, str) and GSIS.fullmatch(v) is not None)
    frame.loc[~valid_player, "identity_status"] = "missing_or_malformed_source_gsis"
    _reason(frame, ~valid_player, "missing_or_malformed_source_gsis")
    valid_source_player = frame.source_player_id.astype(object).map(lambda v: isinstance(v, str) and re.fullmatch(r"[0-9]+", v, re.ASCII) is not None)
    _reason(frame, ~valid_source_player, "missing_or_malformed_source_player")
    event_id = pd.to_numeric(frame.source_event_id, errors="coerce")
    valid_event = np.isfinite(event_id) & event_id.gt(0) & event_id.eq(np.floor(event_id))
    _reason(frame, ~valid_event, "missing_or_malformed_source_event")
    _reason(frame, ~np.isfinite(frame.line.to_numpy(dtype=float)), "missing_or_nonfinite_line")
    odds = pd.to_numeric(frame.american_odds, errors="coerce")
    valid_odds = np.isfinite(odds) & ((odds <= -100) | (odds >= 100)) & odds.eq(np.floor(odds))
    frame["american_odds_valid"] = valid_odds
    _reason(frame, ~valid_odds, "invalid_american_odds")
    _reason(frame, ~frame.book_kind.eq("named"), "not_individual_sportsbook")
    atd = frame.target.eq("anytime_td")
    side_ok = (atd & frame.side.eq("noside") & frame.line.eq(0)) | (~atd & frame.side.isin(["over", "under"]))
    _reason(frame, ~side_ok, "unsupported_side_or_atd_encoding")
    frame["event_semantics"] = np.where(atd, "at_least_one_rushing_or_receiving_td_source_rule_unverified", "ordinary_over_under_source_rule_unverified")
    frame["duplicate_status"] = "unique"
    frame["duplicate_group"] = pd.NA
    # The identity excludes metadata versions and collection clocks deliberately.
    # Exact semantic repetitions keep the first immutable source ordinal. Any
    # conflicting quote/identity version quarantines every member of that key.
    duplicated = frame.duplicated(OFFER_KEY, keep=False)
    for key, group in frame.loc[duplicated].groupby(OFFER_KEY, sort=False, dropna=False, observed=True):
        fingerprint = hashlib.sha256(json.dumps([None if pd.isna(v) else str(v) for v in key], separators=(",", ":")).encode()).hexdigest()
        frame.loc[group.index, "duplicate_group"] = fingerprint
        if len(group[QUOTE_METADATA].drop_duplicates()) == 1:
            ordered = group.sort_values("source_row_number", kind="stable").index
            frame.loc[ordered[0], "duplicate_status"] = "exact_duplicate_representative"
            frame.loc[ordered[1:], "duplicate_status"] = "exact_duplicate_rejected"
            _reason(frame, frame.index.isin(ordered[1:]), "exact_duplicate_not_independent")
        else:
            frame.loc[group.index, "duplicate_status"] = "conflicting_versions_quarantined"
            _reason(frame, frame.index.isin(group.index), "conflicting_duplicate_versions")
    if len(frame) + len(excluded) != len(table):
        raise AssertionError("original row accounting failed")
    frame["source_eligible_exploratory"] = frame.rejection_reasons.eq("")
    frame["cutoff_qualified"] = False
    frame.attrs["adapter_version"] = VERSION
    return frame, excluded


def normalize_parquet_bytes(body, *, source_sha256, source_member, batch_size=32768):
    """Normalize an original without retaining its full decoded Arrow table.

    Every batch is checked for excluded seasons before filtering. Only supported
    full-event rows are retained for global duplicate resolution, while every
    other ordinal remains in the excluded reference frame. Global deduplication
    therefore remains identical across arbitrary Parquet row-group boundaries.
    """
    if not isinstance(batch_size, int) or not 1 <= batch_size <= 32768:
        raise ValueError("batch_size must be an integer between 1 and 32768")
    if hashlib.sha256(body).hexdigest() != source_sha256:
        raise ValueError("original Parquet bytes do not match authenticated SHA256")
    parquet = pq.ParquetFile(io.BytesIO(body))
    if set(parquet.schema_arrow.names) != set(SOURCE_COLUMNS):
        raise ValueError("annual source schema changed")
    selected_batches, selected_ordinals, excluded_ordinals, excluded_reasons = [], [], [], []
    offset = 0
    for batch in parquet.iter_batches(batch_size=batch_size, use_threads=False):
        table = pa.Table.from_batches([batch])
        seasons = set(pc.unique(table["season"]).to_pylist())
        if not seasons or not seasons <= ALLOWED_SEASONS:
            raise ValueError("2025 and unsupported seasons are excluded before normalization")
        target = pc.fill_null(pc.is_in(table["bet_type"], value_set=pa.array(list(MARKETS))), False)
        event = pc.fill_null(pc.equal(table["period"], "event"), False)
        keep = pc.and_(target, event)
        ordinal = pa.array(np.arange(offset, offset + len(table), dtype=np.int64))
        if pc.any(keep).as_py():
            selected_batches.extend(table.filter(keep).to_batches())
            selected_ordinals.append(pc.filter(ordinal, keep).to_numpy())
        excluded_mask = pc.invert(keep)
        if pc.any(excluded_mask).as_py():
            excluded_ordinals.append(pc.filter(ordinal, excluded_mask).to_numpy())
            excluded_reasons.append(pc.filter(target, excluded_mask).to_numpy().astype(np.int8))
        offset += len(table)
    selected = pa.Table.from_batches(selected_batches, schema=parquet.schema_arrow)
    if not len(selected):
        raise ValueError("original contains no supported full-event rows")
    # Immutable original order is preserved by filtering, so duplicate selection
    # sees the same relative order as normalize_annual on the complete original.
    rows, impossible_exclusions = normalize_annual(selected, source_sha256=source_sha256, source_member=source_member)
    if len(impossible_exclusions):
        raise AssertionError("streaming selection unexpectedly rejected a retained row")
    rows["source_row_number"] = np.concatenate(selected_ordinals)
    reason_codes = np.concatenate(excluded_reasons) if excluded_reasons else np.array([], dtype=np.int8)
    excluded = pd.DataFrame({"source_row_number": np.concatenate(excluded_ordinals) if excluded_ordinals else np.array([], dtype=np.int64),
                             "rejection_reasons": pd.Categorical.from_codes(reason_codes,
                                 categories=["unsupported_market", "unsupported_period"]).remove_unused_categories()})
    excluded["source_sha256"] = source_sha256
    excluded["source_member"] = source_member
    if offset != parquet.metadata.num_rows or len(rows) + len(excluded) != offset:
        raise AssertionError("streaming original row accounting failed")
    return rows, excluded


def bind_canonical_games(rows, roster, schedule):
    """Bind exact source GSIS through historical roster and schedule metadata.

    Missing GSIS is never guessed from names or current team/position. Historical
    source metadata disagreement remains diagnostic. An event mapping to two
    canonical games quarantines the entire source event, including good-looking
    rows. No statistic, participation result or outcome is accepted by this API.
    """
    if set(roster) != ROSTER_COLUMNS or set(schedule) != SCHEDULE_COLUMNS:
        raise ValueError("join requires only the registered roster/schedule metadata columns")
    if any(not set(frame.season.unique()) <= ALLOWED_SEASONS for frame in (rows, roster, schedule)):
        raise ValueError("join metadata includes excluded season")
    if rows[["source_sha256", "source_row_number"]].duplicated().any():
        raise ValueError("repeated immutable source row")
    keys = ["season", "week", "player_id"]
    roster = roster.loc[roster.player_id.map(lambda v: isinstance(v, str) and GSIS.fullmatch(v) is not None)].drop_duplicates().copy()
    ambiguous = roster.duplicated(keys, keep=False)
    roster_good = roster.loc[~ambiguous].rename(columns={"position": "position"})
    schedule = schedule.drop_duplicates().copy()
    if schedule.kickoff_utc.isna().any() or any(pd.Timestamp(value).tzinfo is None for value in schedule.kickoff_utc):
        raise ValueError("schedule kickoff requires authenticated timezone-aware metadata")
    schedule_key = ["season", "week", "team"]
    if schedule.duplicated(schedule_key).any():
        raise ValueError("ambiguous team/week schedule metadata")
    context = roster_good.merge(schedule, on=schedule_key, how="inner", validate="many_to_one")
    output = rows.merge(context, on=keys, how="left", validate="many_to_one", sort=False)
    _reason(output, output.game_id.isna(), "missing_unique_historical_roster_schedule_binding")
    linked = output.game_id.notna()
    output.loc[linked, "identity_status"] = "source_gsis_exact_historical_roster_schedule"
    event_key = ["season", "week", "source_event_id"]
    game_counts = output.loc[linked].groupby(event_key, dropna=False).game_id.nunique()
    bad_events = game_counts[game_counts.gt(1)].index
    event_index = pd.MultiIndex.from_frame(output[event_key])
    _reason(output, event_index.isin(bad_events), "source_event_conflicts_with_canonical_games")
    output["source_team_disagrees_with_historical_roster"] = linked & output.source_team.astype(object).ne(output.team)
    output["source_position_disagrees_with_historical_roster"] = linked & output.source_position.astype(object).ne(output.position)
    output["source_eligible_exploratory"] = output.rejection_reasons.eq("")
    output["cutoff_qualified"] = False
    return output


def aggregate_qualification(rows, excluded):
    """Safe aggregate metadata; contains no source player names or raw offers."""
    def category(group):
        return {"rows": len(group), "events": int(group.source_event_id.nunique()),
                "source_player_ids": int(group.source_player_id.nunique()),
                "source_gsis_present_rows": int(group.player_id.notna().sum()),
                "named_book_rows": int(group.book_kind.eq("named").sum()),
                "valid_named_book_rows": int((group.book_kind.eq("named") & group.american_odds_valid).sum()),
                "outside_convenience_positions_rows": int((~group.source_position.isin(["QB", "RB", "WR", "TE"])).sum()),
                "exploratory_eligible_rows": int(group.source_eligible_exploratory.sum())}
    return {"adapter_version": VERSION, "normalized_rows": len(rows), "excluded_row_references": len(excluded),
            "original_row_accounting": len(rows) + len(excluded),
            "market_coverage": {k: category(g) for k, g in rows.groupby("target", sort=True)},
            "missing_market": ["fantasy_ppr"], "books": _counts(rows.book_name),
            "weeks": sorted(map(int, rows.week.unique())), "sides": _counts(rows.side),
            "positions": _counts(rows.source_position), "identity_status": _counts(rows.identity_status),
            "duplicate_status": _counts(rows.duplicate_status),
            "rejection_reason_counts": dict(sorted(Counter(code for text in rows.rejection_reasons for code in text.split(";") if code).items())),
            "excluded_reason_counts": _counts(excluded.rejection_reasons),
            "source_collection_min_naive": str(rows.source_collection_naive.min()),
            "source_collection_max_naive": str(rows.source_collection_naive.max()),
            "cutoff_qualified_rows": 0, "source_quote_timing": "NOT_VERIFIED",
            "settlement_rules": "NOT_VERIFIED; no source result fields used", "fits": 0, "scores": 0, "HTTP": 0}
