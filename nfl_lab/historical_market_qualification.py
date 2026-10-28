"""Finite, aggregate-only archive QA; never writes raw or normalized rows."""
from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
from pathlib import Path
import resource
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .historical_market_archive import (
    ALLOWED_SEASONS, MARKETS, SOURCE_COLUMNS, aggregate_qualification,
    inspect_zip, normalize_annual,
)


def qualify(path):
    archive, body, receipt = inspect_zip(path)
    original = pq.read_table(io.BytesIO(body))
    rows, excluded = normalize_annual(original, source_sha256=receipt["original_sha256"],
                                      source_member=receipt["original_member"])
    result = {**receipt, **aggregate_qualification(rows, excluded)}
    # Verify the convenience filter against actual originals, including every
    # original value and ordinal. Numeric Arrow representation changes are benign.
    season = receipt["season"]
    prefix = f"NFL_Prop_History_{season}/"
    subset = pq.read_table(io.BytesIO(archive.read(prefix + f"requested_subset/ten_markets_recorded_QB_WR_RB_TE_UNVALIDATED_{season}.parquet"))).to_pandas()
    expected_rows = rows.loc[rows.target.ne("pass_int") & rows.source_position.isin(["QB", "WR", "RB", "TE"])]
    refs = subset.source_record_number.to_numpy(dtype=np.int64)
    expected = expected_rows.source_row_number.to_numpy(dtype=np.int64)
    offsets = [offset for offset in (0, 1) if np.array_equal(refs - offset, expected)]
    if len(offsets) != 1:
        raise ValueError("convenience subset filter or original row references mismatch")
    recovered = original.take(pa.array(refs - offsets[0])).to_pandas()
    mismatches = {}
    for col in SOURCE_COLUMNS:
        left, right = recovered[col], subset[col]
        unequal = ~(left.eq(right) | (left.isna() & right.isna()))
        if unequal.any():
            mismatches[col] = int(unequal.sum())
    if mismatches:
        raise ValueError("convenience subset values differ from original")
    result["convenience_filter_verified"] = {"rows": len(subset), "source_reference_base": offsets[0],
                                                "original_value_mismatches": mismatches, "position_filter_is_not_identity_validation": True}
    all_markets = original.select(["bet_type", "period"]).to_pandas(strings_to_categorical=True)
    result["all_original_market_rows"] = {str(k): int(v) for k, v in all_markets.bet_type.value_counts().items()}
    result["all_original_period_rows"] = {str(k): int(v) for k, v in all_markets.period.value_counts().items()}
    ou = rows.loc[rows.target.ne("anytime_td") & rows.side.isin(["over", "under"])]
    pair_key = ["season", "week", "source_event_id", "source_player_id", "target", "period", "book_id", "line"]
    result["same_line_side_pairs"] = {}
    for target, group in ou.groupby("target", sort=True):
        # This is identity coverage, not a simultaneous-price or timing claim.
        count = group.groupby(pair_key, dropna=False, observed=True).side.nunique()
        named = group.loc[group.book_kind.eq("named")]
        named_count = named.groupby(pair_key, dropna=False, observed=True).side.nunique()
        result["same_line_side_pairs"][target] = {"all_groups": len(count), "all_both_sides": int(count.eq(2).sum()),
                                                 "named_groups": len(named_count), "named_both_sides": int(named_count.eq(2).sum())}
    result["original_interception_rows_by_period"] = {str(k): int(v) for k, v in all_markets.loc[all_markets.bet_type.eq("passing_interceptions"), "period"].value_counts().items()}
    result["source_unknown_clock_and_settlement_fields"] = ["book_quote_timestamp", "kickoff", "is_live", "line_status", "settlement_rule_version"]
    if season == 2022:
        csv_member = prefix + "originals/xsportsbook/NFL_2022_Player_Prop_Results_original.csv"
        csv_body = archive.read(csv_member)
        # Deliberately never read W/L, result, ROI, margin or realized game stats.
        csv = pd.read_csv(io.BytesIO(csv_body), usecols=["Game_Id", "Player.id", "Player", "Betting Event", "Team", "Opp", "POS", "Week", "O-Line", "O-Odds", "U-Line", "U-Odds"], dtype=str)
        for col in csv:
            csv[col] = csv[col].str.strip()
        o, u = pd.to_numeric(csv["O-Odds"], errors="coerce"), pd.to_numeric(csv["U-Odds"], errors="coerce")
        ints = csv["Betting Event"].str.contains("interception", case=False, na=False)
        identities = csv.groupby("Player.id", dropna=False).Player.nunique()
        invalid_o = ~((o.le(-100) | o.ge(100)) & np.isfinite(o))
        invalid_u = ~((u.le(-100) | u.ge(100)) & np.isfinite(u))
        result["xsportsbook_original"] = {"sha256": hashlib.sha256(csv_body).hexdigest(), "bytes": len(csv_body), "rows": len(csv),
                                            "markets": csv["Betting Event"].value_counts().to_dict(),
                                            "interception_rows_by_position": csv.loc[ints, "POS"].value_counts(dropna=False).to_dict(),
                                            "source_player_ids_with_multiple_names": int(identities.gt(1).sum()),
                                            "invalid_over_prices": int(invalid_o.sum()), "invalid_under_prices": int(invalid_u.sum()),
                                            "absolute_price_at_least_10000_rows": int((o.abs().ge(10000) | u.abs().ge(10000)).sum()),
                                            "different_ou_threshold_rows": int(pd.to_numeric(csv["O-Line"], errors="coerce").ne(pd.to_numeric(csv["U-Line"], errors="coerce")).sum()),
                                            "canonical_identity": "BLOCKED_COLLIDING_SOURCE_IDS_REQUIRE_INDEPENDENT_CROSSWALK",
                                            "timing": "NO_ORIGINAL_QUOTE_OR_COLLECTION_CLOCK", "used_for_features_or_outcomes": False}
    archive.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+")
    parser.add_argument("--report", required=True, help="Aggregate JSON only; never a raw/private row export")
    args = parser.parse_args()
    # This process cannot consume a fit, score or network request. Hard CPU and
    # resource observations supplement the root's finite qualification contract.
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    started, cpu = time.monotonic(), time.process_time()
    results = []
    report = {"schema_version": "historical-market-no2025-qualification-v1", "seasons": results,
              "excluded_seasons": [2025], "private_row_writes": 0, "fits": 0, "scores": 0, "HTTP": 0}
    for path in args.archives:
        if time.monotonic() - started >= 180:
            raise TimeoutError("qualification wall budget consumed")
        results.append(qualify(path))
        gc.collect()
    report["resources"] = {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                             "RSS_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    if report["resources"]["RSS_peak_bytes"] > 512 * 1024 ** 2:
        report["state"] = "QUALIFICATION_RESOURCE_CEILING_EXCEEDED"
    else:
        report["state"] = "SOURCE_METADATA_QUALIFIED_TIMING_UNVERIFIED"
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"state": report["state"], "resources": report["resources"],
                      "seasons": [{"season": r["season"], "rows": r["original_rows"], "target_rows": r["normalized_rows"],
                                   "interceptions": r["market_coverage"].get("pass_int"), "named_both_sides": sum(p["named_both_sides"] for p in r["same_line_side_pairs"].values())} for r in results]}))


if __name__ == "__main__":
    main()
