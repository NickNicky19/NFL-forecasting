"""Separately authorized v2 memory correction; reuses completed v1 source QA.

The command writes aggregate metadata only. Normalized rows stay in memory;
private CAS writes belong to the root's separately reviewed storage allocation.
"""
from __future__ import annotations

import argparse
import gc
import io
import json
from pathlib import Path
import resource
import signal
import time

import pyarrow as pa
import pyarrow.parquet as pq

from .historical_market_archive import aggregate_qualification, inspect_zip, normalize_annual

VERSION = "historical-market-source-qualification-memory-v2"


def _timeout(_signum, _frame):
    raise TimeoutError("v2 wall budget exhausted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+")
    parser.add_argument("--previous", required=True, help="Immutable completed v1 source-check receipt, including its RSS failure")
    parser.add_argument("--report", required=True, help="NEW aggregate receipt; cannot overwrite the v1 failure")
    args = parser.parse_args()
    if Path(args.previous).resolve() == Path(args.report).resolve() or Path(args.report).exists():
        raise ValueError("v2 receipt must be a new path")
    previous_bytes = Path(args.previous).read_bytes()
    previous = json.loads(previous_bytes)
    if previous["state"] != "QUALIFICATION_RESOURCE_CEILING_EXCEEDED":
        raise ValueError("v2 applies only to the preserved v1 memory failure")
    authenticated = {r["zip_sha256"]: r for r in previous["seasons"]}
    if len(args.archives) != len(authenticated) or len(authenticated) != 4:
        raise ValueError("v2 scope requires exactly the same four original ZIP identities")
    # Hard limits preserve the separately registered v2 budget. Native threading
    # is disabled by the caller and Parquet decoding explicitly uses one thread.
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(90)
    started, cpu = time.monotonic(), time.process_time()
    report = {"version": VERSION, "prior_attempt_state": previous["state"],
              "prior_aggregate_receipt_sha256": __import__("hashlib").sha256(previous_bytes).hexdigest(),
              "v1_source_assertions_reused": ["all_original_payload_manifest_hashes", "all_source_schemas", "all_convenience_filter_values_and_ordinals", "all_original_coverage_statistics"],
              "seasons": [], "private_row_writes": 0, "fits": 0, "scores": 0, "HTTP": 0,
              "excluded_seasons": [2025], "requested_model": "gpt-6.1-sol", "requested_effort": "xhigh", "actual_backend": "UNATTESTED"}
    seen = set()
    try:
        for path in args.archives:
            archive, original_bytes, receipt = inspect_zip(path, verify_manifest=False)
            if receipt["zip_sha256"] not in authenticated or receipt["zip_sha256"] in seen:
                raise ValueError("new or repeated ZIP outside v2 scope")
            prior = authenticated[receipt["zip_sha256"]]
            for key in ["season", "zip_bytes", "original_sha256", "original_bytes", "original_rows", "schema"]:
                if receipt[key] != prior[key]:
                    raise ValueError("immutable v1 source identity changed")
            seen.add(receipt["zip_sha256"])
            table = pq.ParquetFile(io.BytesIO(original_bytes)).read(use_threads=False)
            rows, excluded = normalize_annual(table, source_sha256=receipt["original_sha256"], source_member=receipt["original_member"])
            summary = aggregate_qualification(rows, excluded)
            if summary["normalized_rows"] != prior["normalized_rows"] or summary["duplicate_status"] != prior["duplicate_status"]:
                raise ValueError("normalizer behavior changed beyond memory lifecycle correction")
            report["seasons"].append({"season": receipt["season"], "zip_sha256": receipt["zip_sha256"],
                                       "original_sha256": receipt["original_sha256"],
                                       "normalized_rows": len(rows), "excluded_row_references": len(excluded),
                                       "normalizer_behavior_matches_v1": True,
                                       "RSS_peak_bytes_so_far": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024})
            archive.close()
            del archive, original_bytes, table, rows, excluded, summary, receipt
            gc.collect()
            pa.default_memory_pool().release_unused()
        report["state"] = "COMPLETED_MEMORY_LIFECYCLE_CHECK"
    except BaseException as error:
        report["state"] = "FAILED_OR_INTERRUPTED"
        # Exception text is deliberately omitted: some parsers include raw row
        # values in errors. Class and stage are sufficient for this receipt.
        report["error_class"] = type(error).__name__
    finally:
        signal.alarm(0)
        report["resources"] = {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started,
                                 "RSS_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        if report["resources"]["RSS_peak_bytes"] > 512 * 1024 ** 2:
            report["state"] = "FAILED_RSS_CEILING_EXCEEDED"
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report))
    if report["state"] != "COMPLETED_MEMORY_LIFECYCLE_CHECK":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
