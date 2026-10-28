"""Complete one previously unnormalized season with bounded serialization.

V3's failed run and completed 2026/2024 vectors stay intact. Each fresh process
handles only one of 2023 or 2022, writes one two-member capsule and one receipt,
and never fits, scores, collects sources or changes source-selection semantics.
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

from .historical_market_archive import aggregate_qualification, bind_canonical_games, normalize_parquet_bytes
from .historical_market_normalize_v3 import _pair_coverage, _schedule, pinned

VERSION = "historical-market-source-normalization-v4"


def parquet_batches(frame):
    """Infer schema columnwise, then expand provenance strings only 8192 at once."""
    schema = pa.Schema.from_pandas(frame, preserve_index=False)
    sink = io.BytesIO()
    with pq.ParquetWriter(sink, schema, compression="zstd", compression_level=3) as writer:
        for offset in range(0, len(frame), 8192):
            table = pa.Table.from_pandas(frame.iloc[offset:offset + 8192], schema=schema, preserve_index=False)
            writer.write_table(table)
            del table
    return sink.getvalue()


def stop(*_args):
    raise TimeoutError("finite one-season V4 normalization budget exhausted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--go", required=True)
    parser.add_argument("--season", required=True, type=int, choices=[2023, 2022])
    args = parser.parse_args()
    body = Path(args.plan).read_bytes()
    if hashlib.sha256(body).hexdigest() != args.sha256:
        raise ValueError("exact root one-season normalization plan required")
    plan = json.loads(body)
    if (json.loads(Path(args.go).read_bytes()) != {"state": "GO", "root": "/root", "plan_sha256": args.sha256}
            or plan["version"] != VERSION or plan["state"] != "SEALED_ROOT_GO" or plan["excluded_seasons"] != [2025]
            or plan["season"] != args.season):
        raise ValueError("V4 root GO required for this one uncompleted season")
    budget = plan["resources"]
    if (budget["CPU_seconds"] != 60 or budget["wall_seconds"] != 90 or budget["RSS_bytes"] != 536870912
            or budget["batch_rows"] != 8192 or budget["max_output_bytes"] != 8 * 1024**2
            or any(budget[k] != 0 for k in ["fits", "scores", "HTTP"])):
        raise ValueError("unchanged finite V4 limits required")
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGXCPU, stop)
    signal.alarm(90)
    started, cpu = time.monotonic(), time.process_time()
    for ref in plan["pins"].values():
        pinned(ref)
    helper_ref = plan["pins"]["storage_helper"]
    spec = importlib.util.spec_from_file_location("historical_market_approved_storage_v4", helper_ref["path"])
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    base = helper.load_frozen(plan["pins"]["forward_helper"]["path"], plan["legacy_library_root"])
    policy = json.loads(pinned(plan["pins"]["market_policy"]))
    prior_policy = json.loads(pinned(plan["pins"]["prior_forward_policy"]))
    legacy_policy = json.loads(pinned(plan["pins"]["legacy_policy"]))
    if not (Path(policy["store_policy"]["storage"]["forward_root"]) / "state/historical-market-outer-policy.json").is_file():
        raise ValueError("root-initialized private allocation required")
    store = helper.build_storage_class(base)(plan["legacy_cache"], policy, legacy_policy, prior_policy)
    output = store.feature_root / f"historical-market-no2025-v1/source-normalization-v4-{args.season}.zip"
    receipt_path = store.live_root / f"research/historical-market-no2025-v1/SOURCE_NORMALIZATION_V4_{args.season}.json"
    if output.exists() or receipt_path.exists() or Path(plan["aggregate_report"]).exists():
        raise ValueError("this one-season V4 normalization was already attempted")
    prior = json.loads(pinned(plan["pins"]["source_checks_v1"]))
    prior = next(item for item in prior["seasons"] if item["season"] == args.season)
    source = plan["source"]
    if source["season"] != args.season or source["sha256"] != prior["original_sha256"]:
        raise ValueError("V4 original source binding changed")
    report = {"version": VERSION, "season": args.season, "plan_sha256": args.sha256,
              "prior_failures_preserved": ["source-qualification-v1", "source-memory-v2", "source-normalization-v3"],
              "previously_completed_seasons_not_reprocessed": [2026, 2024], "excluded_seasons": [2025],
              "fits": 0, "scores": 0, "HTTP": 0, "requested_model": "gpt-6.1-sol", "requested_effort": "xhigh", "actual_backend": "UNATTESTED"}
    capsule_buffer = io.BytesIO()
    capsule = zipfile.ZipFile(capsule_buffer, mode="w", compression=zipfile.ZIP_STORED)
    pointers = []
    try:
        body = pinned(source)
        rows, excluded = normalize_parquet_bytes(body, source_sha256=source["sha256"], source_member=prior["original_member"], batch_size=8192)
        del body
        if len(rows) != prior["normalized_rows"] or rows.duplicate_status.value_counts().to_dict() != prior["duplicate_status"]:
            raise ValueError("V4 source normalization changed frozen source semantics")
        roster_body = pinned(plan["roster"])
        roster = pq.ParquetFile(io.BytesIO(roster_body)).read(columns=["season", "week", "gsis_id", "team", "position"], use_threads=False).to_pandas()
        del roster_body
        roster = roster.rename(columns={"gsis_id": "player_id"})
        roster.team = roster.team.replace({"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"})
        schedule = _schedule(pinned(plan["schedule"]))
        schedule = schedule.loc[schedule.season.eq(args.season) & schedule.week.isin(rows.week.unique())].copy()
        joined = bind_canonical_games(rows, roster, schedule)
        del rows, roster, schedule
        gc.collect()
        pa.default_memory_pool().release_unused()
        summary = aggregate_qualification(joined, excluded)
        summary["canonical_game_rows"] = int(joined.game_id.notna().sum())
        summary["canonical_games"] = int(joined.game_id.nunique())
        summary["same_line_vs_exact_clock_pair_coverage"] = _pair_coverage(joined)
        report["coverage"] = summary
        for kind, frame in [("offers", joined), ("excluded", excluded)]:
            encoded = parquet_batches(frame)
            if sum(p["bytes"] for p in pointers) + len(encoded) + 4096 > budget["max_output_bytes"]:
                raise ValueError("per-season V4 output envelope exhausted")
            member = f"{kind}_{args.season}.parquet"
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            capsule.writestr(info, encoded)
            pointers.append({"kind": kind, "season": args.season, "rows": len(frame), "zip_member": member,
                             "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()})
            del encoded
        del joined, excluded, frame
        gc.collect()
        pa.default_memory_pool().release_unused()
        report["state"] = "COMPLETED_ONE_SEASON_CANONICAL_EXPLORATORY_NORMALIZATION"
    except BaseException as error:
        report["state"] = "FAILED_OR_INTERRUPTED"
        report["error_class"] = type(error).__name__
    finally:
        capsule.close()
        body = capsule_buffer.getvalue()
        if len(body) > budget["max_output_bytes"]:
            raise ValueError("V4 capsule envelope exceeded")
        store.write_bytes(output, body)
        capsule_ref = store.validate_reference(output)
        if Path(capsule_ref["path"]).read_bytes() != body:
            raise ValueError("V4 capsule immutable readback differs")
        for pointer in pointers:
            pointer["zip_container"] = capsule_ref
        report["capsule_reference"] = capsule_ref
        report["source_references"] = pointers
        report["private_capsule_bytes"] = len(body)
        del body, capsule_buffer
        report["resources_before_final_receipt_write"] = {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                                                          "RSS_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        if report["resources_before_final_receipt_write"]["RSS_peak_bytes"] > budget["RSS_bytes"]:
            report["state"] = "FAILED_RSS_CEILING_EXCEEDED"
        store.write_bytes(receipt_path, base.legacy._encoded(report))
        report["private_receipt_reference"] = store.validate_reference(receipt_path)
        report["resources"] = {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                                 "RSS_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        if report["resources"]["RSS_peak_bytes"] > budget["RSS_bytes"]:
            report["state"] = "FAILED_RSS_CEILING_EXCEEDED"
        signal.alarm(0)
        Path(plan["aggregate_report"]).parent.mkdir(parents=True, exist_ok=True)
        Path(plan["aggregate_report"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"state": report["state"], "season": args.season, "resources": report["resources"],
                          "capsule_reference": capsule_ref, "private_receipt_reference": report["private_receipt_reference"],
                          "normalized_rows": report.get("coverage", {}).get("normalized_rows"),
                          "exact_clock_eligible_pair_counts": report.get("coverage", {}).get("same_line_vs_exact_clock_pair_coverage")}))
    if report["state"] != "COMPLETED_ONE_SEASON_CANONICAL_EXPLORATORY_NORMALIZATION":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
