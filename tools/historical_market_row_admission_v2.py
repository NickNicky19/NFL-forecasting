"""Read-only content admission of retained rows; never relabel failed attempts."""
import argparse
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import time
import zipfile


def check(ok, message):
    if not ok:
        raise ValueError(message)


def pinned(ref):
    p = Path(ref["path"])
    check(p.resolve() == p and not any(q.is_symlink() for q in [p, *p.parents]), "canonical reference required")
    b = p.read_bytes()
    check(len(b) == ref["bytes"] and hashlib.sha256(b).hexdigest() == ref["sha256"], "pinned reference changed")
    if "blob" in ref:
        blob = Path(ref["blob"])
        check(os.path.samestat(p.stat(), blob.stat()) and not p.stat().st_mode & 0o222, "explicit owned CAS alias differs")
        check(blob.name == ref["sha256"] and hashlib.sha256(blob.read_bytes()).hexdigest() == ref["sha256"], "explicit CAS blob differs")
    return b


def stop(*unused):
    raise RuntimeError("finite retained-row admission exhausted")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--sha256", required=True)
    args = ap.parse_args()
    raw = Path(args.plan).read_bytes()
    check(hashlib.sha256(raw).hexdigest() == args.sha256, "exact root input admission plan required")
    p = json.loads(raw)
    check(p["state"] == "ROOT_READONLY_INPUT_ADMISSION_GO" and p["excluded_seasons"] == [2025], "registered no2025 admission required")
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGXCPU, stop)
    signal.alarm(30)
    started, cpu = time.monotonic(), time.process_time()
    import numpy as np
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    import pyarrow as pa
    source_qa = json.loads(pinned(p["original_source_assertions"]))
    originals = {d["season"]: d for d in source_qa["seasons"]}
    accepted, coverage, histories = [], [], []
    for report_ref in p["normalized_reports"]:
        report = json.loads(pinned(report_ref))
        check(report["state"] == report_ref["expected_state"], "source completion/failure status changed")
        check(report["excluded_seasons"] == [2025], "source exclusion mismatch")
        histories.append({"source_report_sha256": report_ref["sha256"], "original_state_preserved": report["state"], "resources": report["resources"]})
        by_year = {}
        for member in report["source_references"]:
            by_year.setdefault(member["season"], {})[member["kind"]] = member
        container = report["capsule_reference"]
        capsule_bytes = pinned(container)
        with zipfile.ZipFile(io.BytesIO(capsule_bytes)) as z:
            check(len(z.namelist()) == len(set(z.namelist())) == 2 * len(by_year), "complete named source members required")
            for year, pair in by_year.items():
                check(year in [2022, 2023, 2024, 2026] and set(pair) == {"offers", "excluded"}, "complete per-source partition required")
                source = originals[year]
                ordinals = []
                eligible_count, games = 0, set()
                for kind in ["offers", "excluded"]:
                    m = pair[kind]
                    check(m["zip_container"] == container, "source member container binding differs")
                    b = z.read(m["zip_member"])
                    check(len(b) == m["bytes"] and hashlib.sha256(b).hexdigest() == m["sha256"], "source member changed")
                    f = pq.ParquetFile(io.BytesIO(b))
                    check(f.metadata.num_rows == m["rows"], "source member rows differ")
                    columns = ["source_row_number", "source_sha256", "source_member"]
                    if kind == "offers":
                        columns += ["season", "period", "source_event_id", "target", "book_id", "rejection_reasons",
                                    "source_eligible_exploratory", "cutoff_qualified", "identity_status", "game_id", "player_id"]
                    table = f.read(columns=columns, use_threads=False)
                    check(pc.all(pc.equal(table["source_sha256"], source["original_sha256"])).as_py(), "original source hash differs")
                    check(pc.all(pc.equal(table["source_member"], source["original_member"])).as_py(), "original source member differs")
                    ordinal = table["source_row_number"].to_numpy()
                    check(np.issubdtype(ordinal.dtype, np.integer) and np.all(np.diff(ordinal) > 0), "immutable original row order differs")
                    ordinals.append(ordinal.copy())
                    if kind == "offers":
                        check(pc.all(pc.equal(table["season"], year)).as_py() and pc.all(pc.equal(table["period"], "event")).as_py(), "wrong season or period")
                        check(not pc.any(table["cutoff_qualified"]).as_py(), "unverified clocks relabelled qualified")
                        eligible = pc.fill_null(table["source_eligible_exploratory"], False)
                        good = table.filter(eligible)
                        check(len(good) == 0 or pc.all(pc.equal(good["rejection_reasons"], "")).as_py(), "rejected source row eligible")
                        check(len(good) == 0 or pc.all(pc.equal(good["identity_status"], "source_gsis_exact_historical_roster_schedule")).as_py(), "unsupported source identity eligible")
                        check(good["game_id"].null_count == 0 and good["player_id"].null_count == 0, "missing canonical identity eligible")
                        check(set(good["book_id"].to_pylist()) <= {68, 69, 79}, "synthetic or consensus book eligible")
                        eligible_count = len(good)
                        games = set(x for x in table["game_id"].to_pylist() if x is not None)
                        accepted.append({"container": container, "member": m["zip_member"], "bytes": m["bytes"], "sha256": m["sha256"], "season": year, "rows": m["rows"]})
                        check(set(table["target"].to_pylist()) <= set(p["targets"]), "unsupported target in normalized rows")
                    del b, table, f
                all_rows = np.sort(np.concatenate(ordinals))
                check(np.array_equal(all_rows, np.arange(source["original_rows"], dtype=np.int64)), "full original row partition missing or duplicated")
                coverage.append({"season": year, "original_rows_accounted": len(all_rows), "offer_rows": pair["offers"]["rows"],
                                 "excluded_rows_preserved": pair["excluded"]["rows"], "canonical_games_including_rejected_context": len(games),
                                 "named_exploratory_eligible_rows": eligible_count, "cutoff_qualified_rows": 0})
                del all_rows, ordinals
        del capsule_bytes
        gc.collect()
        pa.default_memory_pool().release_unused()
    check({r["season"] for r in accepted} == {2022, 2023, 2024, 2026}, "all requested source years required")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    check(rss <= 536870912, "retained-row admission RSS exceeded")
    result = {"state": "RETAINED_EXPLORATORY_ROWS_ADMITTED_WITH_ORIGINAL_RESOURCE_FAILURES_PRESERVED",
              "version": "historical-market-retained-row-admission-v2", "plan_sha256": args.sha256,
              "normalized_market_inputs": accepted, "coverage": sorted(coverage, key=lambda x: x["season"]),
              "source_attempt_history": histories, "excluded_seasons": [2025],
              "original_failed_V3_NOT_RELABELED_PASS": True,
              "checks": ["exact_private_CAS_container_and_member_bytes", "original_source_hash_and_member", "original_row_ordinals_complete_unique_in_order",
                         "all_sources_no2025", "exploratory_identity_and_named_book_gate", "unknown_quote_cutoff_not_qualified"],
              "not_claimed": ["source_quote_time", "actual_book_settlement", "NFL_prediction_accuracy", "offhost_restoration", "live_deployment"],
              "resources": {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - started, "RSS_bytes": rss},
              "fits": 0, "scores": 0, "HTTP": 0, "managed_writes": 0}
    output = Path(p["output"])
    check(not output.exists(), "admission receipt already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    signal.alarm(0)
    print(json.dumps({"state": result["state"], "coverage": result["coverage"], "resources": result["resources"],
                      "receipt_bytes": output.stat().st_size, "receipt_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
