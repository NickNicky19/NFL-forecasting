"""One bounded source normalization, metadata join and approved private CAS write.

Run only with the root's exact sealed v3 plan after reviewed store initialization.
Existing v1 source assertions and both failed memory attempts remain immutable.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import resource
import signal
import time
import zipfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .historical_market_archive import (
    ALLOWED_SEASONS, aggregate_qualification, bind_canonical_games, normalize_parquet_bytes,
)

VERSION = "historical-market-source-normalization-v3"


def pinned(ref):
    if "zip_member" in ref:
        container = pinned(ref["zip_container"])
        with zipfile.ZipFile(io.BytesIO(container)) as archive:
            if archive.namelist().count(ref["zip_member"]) != 1:
                raise ValueError("exact unique original ZIP member required")
            body = archive.read(ref["zip_member"])
        if len(body) != ref["bytes"] or hashlib.sha256(body).hexdigest() != ref["sha256"]:
            raise ValueError("pinned original ZIP member changed")
        return body
    path = Path(ref["path"])
    if path.resolve() != path or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("canonical immutable source path required")
    body = path.read_bytes()
    if len(body) != ref["bytes"] or hashlib.sha256(body).hexdigest() != ref["sha256"]:
        raise ValueError("pinned input changed")
    return body


def _stop(_signum, _frame):
    raise TimeoutError("v3 finite resource budget exhausted")


def _schedule(body):
    # Only metadata columns enter memory. In particular, scores, lines, weather,
    # QB results and game outcomes in the source CSV are never parsed.
    columns = ["game_id", "season", "week", "gameday", "gametime", "away_team", "home_team"]
    selected = []
    for chunk in pd.read_csv(io.BytesIO(body), usecols=columns, chunksize=8192):
        selected.append(chunk.loc[chunk.season.isin(ALLOWED_SEASONS)].copy())
    games = pd.concat(selected, ignore_index=True)
    local = pd.to_datetime(games.gameday + " " + games.gametime, errors="coerce")
    games["kickoff_utc"] = local.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    sides = []
    for own, other, home in [("home_team", "away_team", True), ("away_team", "home_team", False)]:
        side = games[["season", "week", "game_id", "kickoff_utc", own, other]].rename(columns={own: "team", other: "opponent"})
        for column in ["team", "opponent"]:
            side[column] = side[column].replace({"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"})
        side["is_home"] = home
        sides.append(side)
    return pd.concat(sides, ignore_index=True)


def _parquet_body(frame):
    sink = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), sink, compression="zstd", compression_level=3)
    return sink.getvalue()


def _pair_coverage(rows):
    """Same-line identity counts and stricter same-clock comparison support."""
    result = {}
    source_key = ["season", "week", "source_event_id", "source_player_id", "target", "period", "book_id", "line"]
    canonical_key = ["season", "week", "game_id", "player_id", "target", "period", "book_id", "line", "source_collection_naive"]
    ordinary = rows.loc[rows.book_kind.eq("named") & rows.target.ne("anytime_td") & rows.side.isin(["over", "under"])]
    for target, group in ordinary.groupby("target", sort=True):
        source = group.groupby(source_key, dropna=False, observed=True).side.nunique()
        eligible = group.loc[group.source_eligible_exploratory & group.source_collection_naive.notna()
                             & group.identity_status.eq("source_gsis_exact_historical_roster_schedule")]
        pairs = eligible.groupby(canonical_key, dropna=False, observed=True).side.agg(["size", "nunique"])
        result[target] = {"raw_named_same_line_both_side_groups": int(source.eq(2).sum()),
                          "eligible_exact_clock_unique_both_side_groups": int((pairs["size"].eq(2) & pairs["nunique"].eq(2)).sum()),
                          "eligible_exact_clock_ambiguous_groups": int(pairs["size"].gt(pairs["nunique"]).sum()),
                          "eligible_exact_clock_single_side_groups": int(pairs["nunique"].eq(1).sum())}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    plan_bytes = Path(args.plan).read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != args.sha256:
        raise ValueError("exact sealed root v3 plan required")
    plan = json.loads(plan_bytes)
    go = json.loads(Path(args.go).read_bytes())
    if (go != {"state": "GO", "root": "/root", "plan_sha256": args.sha256}
            or plan["version"] != VERSION or plan["state"] != "SEALED_ROOT_GO"
            or plan["excluded_seasons"] != [2025]):
        raise ValueError("root source normalization GO required")
    budget = plan["resources"]
    if (budget["CPU_seconds"] != 90 or budget["wall_seconds"] != 120
            or budget["RSS_bytes"] != 512 * 1024**2 or budget["batch_rows"] not in [8192, 16384]
            or budget["max_output_bytes"] > 40 * 1024**2
            or any(budget[k] != 0 for k in ["fits", "scores", "HTTP"])):
        raise ValueError("unmodified finite v3 contract required")
    resource.setrlimit(resource.RLIMIT_CPU, (90, 91))
    signal.signal(signal.SIGALRM, _stop)
    signal.signal(signal.SIGXCPU, _stop)
    signal.alarm(120)
    started, cpu = time.monotonic(), time.process_time()
    for ref in plan["pins"].values():
        pinned(ref)
    helper_ref = plan["pins"]["storage_helper"]
    spec = importlib.util.spec_from_file_location("historical_market_approved_storage_v3", helper_ref["path"])
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    base = helper.load_frozen(plan["pins"]["forward_helper"]["path"], plan["legacy_library_root"])
    policy = json.loads(pinned(plan["pins"]["market_policy"]))
    prior_policy = json.loads(pinned(plan["pins"]["prior_forward_policy"]))
    legacy_policy = json.loads(pinned(plan["pins"]["legacy_policy"]))
    store_root = Path(policy["store_policy"]["storage"]["forward_root"])
    if not (store_root / "state/historical-market-outer-policy.json").is_file():
        raise ValueError("reviewed root store initialization must already exist")
    store = helper.build_storage_class(base)(plan["legacy_cache"], policy, legacy_policy, prior_policy)
    output = store.feature_root / "historical-market-no2025-v1" / "source-normalization-v3.zip"
    private_receipt = store.live_root / "research/historical-market-no2025-v1/SOURCE_NORMALIZATION_V3.json"
    if output.exists() or private_receipt.exists() or Path(plan["aggregate_report"]).exists():
        raise ValueError("v3 already attempted; preserve it without retry")
    prior = json.loads(pinned(plan["pins"]["source_checks_v1"]))
    prior_sources = {r["season"]: r for r in prior["seasons"]}
    if len(plan["sources"]) != 4 or {r["season"] for r in plan["sources"]} != ALLOWED_SEASONS:
        raise ValueError("v3 requires the same four source seasons")
    schedule = _schedule(pinned(plan["schedule"]))
    source_refs, consumed = [], 0
    capsule_buffer = io.BytesIO()
    capsule = zipfile.ZipFile(capsule_buffer, mode="w", compression=zipfile.ZIP_STORED)
    report = {"version": VERSION, "plan_sha256": args.sha256,
              "source_checks": "V1_HASH_SCHEMA_FILTER_COVERAGE_ASSERTIONS_REUSED; V1_AND_V2_RESOURCE_FAILURES_PRESERVED",
              "seasons": [], "fits": 0, "scores": 0, "HTTP": 0, "excluded_seasons": [2025],
              "requested_model": "gpt-6.1-sol", "requested_effort": "xhigh", "actual_backend": "UNATTESTED"}
    try:
        for source in plan["sources"]:
            season = source["season"]
            if source["sha256"] != prior_sources[season]["original_sha256"]:
                raise ValueError("v3 source differs from authenticated original")
            body = pinned(source)
            rows, excluded = normalize_parquet_bytes(body, source_sha256=source["sha256"],
                                                     source_member=prior_sources[season]["original_member"], batch_size=budget["batch_rows"])
            del body
            if len(rows) != prior_sources[season]["normalized_rows"] or rows.duplicate_status.value_counts().to_dict() != prior_sources[season]["duplicate_status"]:
                raise ValueError("streaming normalization differs from frozen source semantics")
            roster_ref = plan["rosters"][str(season)]
            roster_body = pinned(roster_ref)
            roster = pq.ParquetFile(io.BytesIO(roster_body)).read(columns=["season", "week", "gsis_id", "team", "position"], use_threads=False).to_pandas()
            del roster_body
            roster = roster.rename(columns={"gsis_id": "player_id"})
            roster.team = roster.team.replace({"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"})
            relevant_schedule = schedule.loc[schedule.season.eq(season) & schedule.week.isin(rows.week.unique())].copy()
            joined = bind_canonical_games(rows, roster, relevant_schedule)
            del rows, roster, relevant_schedule
            summary = aggregate_qualification(joined, excluded)
            summary["season"] = season
            summary["canonical_game_rows"] = int(joined.game_id.notna().sum())
            summary["canonical_games"] = int(joined.game_id.nunique())
            summary["source_team_disagreement_rows"] = int(joined.source_team_disagrees_with_historical_roster.sum())
            summary["source_position_disagreement_rows"] = int(joined.source_position_disagrees_with_historical_roster.sum())
            summary["same_line_vs_exact_clock_pair_coverage"] = _pair_coverage(joined)
            for kind, frame in [("offers", joined), ("excluded", excluded)]:
                encoded = _parquet_body(frame)
                if consumed + len(encoded) + 16384 > budget["max_output_bytes"]:
                    raise ValueError("normalized output and rejection byte envelope exhausted")
                member = f"{kind}_{season}.parquet"
                capsule.writestr(member, encoded)
                source_refs.append({"kind": kind, "season": season, "rows": len(frame), "zip_member": member,
                                    "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()})
                consumed += len(encoded)
                del encoded
            report["seasons"].append(summary)
            del joined, excluded, frame
            gc.collect()
            pa.default_memory_pool().release_unused()
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > budget["RSS_bytes"]:
                raise MemoryError("v3 RSS ceiling exceeded")
        report["state"] = "NORMALIZED_CANONICAL_EXPLORATORY_OFFERS_PERSISTED"
    except BaseException as error:
        report["state"] = "FAILED_OR_INTERRUPTED"
        report["error_class"] = type(error).__name__
    finally:
        capsule.close()
        capsule_body = capsule_buffer.getvalue()
        # One immutable capsule keeps the inherited full CAS checks intact while
        # avoiding eight separate writes/scans. A failed partial capsule is also
        # retained with its failure receipt and never presented as complete.
        if len(capsule_body) > budget["max_output_bytes"]:
            report["state"] = "FAILED_OUTPUT_ENVELOPE_EXCEEDED"
        store.write_bytes(output, capsule_body)
        capsule_ref = store.validate_reference(output)
        if Path(capsule_ref["path"]).read_bytes() != capsule_body:
            raise ValueError("normalized capsule CAS body readback differs")
        for ref in source_refs:
            ref["zip_container"] = capsule_ref
        report["capsule_reference"] = capsule_ref
        del capsule_body, capsule_buffer
        report["resources"] = {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                                 "RSS_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        report["private_output_bytes"] = consumed
        report["private_capsule_bytes"] = capsule_ref["bytes"]
        report["source_references"] = source_refs
        if report["resources"]["RSS_peak_bytes"] > budget["RSS_bytes"]:
            report["state"] = "FAILED_RSS_CEILING_EXCEEDED"
        store.write_bytes(private_receipt, base.legacy._encoded(report))
        report["private_receipt_reference"] = store.validate_reference(private_receipt)
        report["resources_before_final_receipt_write"] = report["resources"]
        report["resources"] = {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                                 "RSS_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        signal.alarm(0)
        # Aggregate metadata and opaque references only; no raw offers/player IDs.
        Path(plan["aggregate_report"]).parent.mkdir(parents=True, exist_ok=True)
        Path(plan["aggregate_report"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"state": report["state"], "resources": report["resources"], "private_output_bytes": consumed,
                          "capsule_reference": capsule_ref,
                          "private_receipt_reference": report["private_receipt_reference"],
                          "seasons": [{"season": r["season"], "canonical_game_rows": r["canonical_game_rows"], "canonical_games": r["canonical_games"],
                                       "exploratory_eligible_rows": sum(t["exploratory_eligible_rows"] for t in r["market_coverage"].values())} for r in report["seasons"]]}))
    if report["state"] != "NORMALIZED_CANONICAL_EXPLORATORY_OFFERS_PERSISTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
