#!/usr/bin/env python3
"""Independent arithmetic review of published aggregate CSVs only.

Never reads a private score, source archive, fitted model or native namespace;
never reruns inference, grading, bootstrapping or the author's exporter.
"""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import platform
import resource
import time

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/abc-championship/category-decision-release-01"
PUBLIC = REPORT / "point-pairs-public-v1"
RECEIPT = REPORT / "PUBLIC_AGGREGATE_INDEPENDENT_RECEIPT_V1.json"
EMPTY = hashlib.sha256(b"[]\n").hexdigest()
SOURCE = "913bf6cc8a8e32c9985501e7cf59fbd5e334eede89a04a7904cae7a80bcc94e5"
TOL = Decimal("1e-12")
checks = Counter()
largest_error = Decimal(0)
start_cpu = time.process_time()
start_wall = time.monotonic()


def ensure(test, label):
    checks[label] += 1
    if not test:
        raise AssertionError(label)


def reject_constant(s):
    raise ValueError("non-finite JSON token: " + s)


def decode(s):
    return json.loads(s, parse_float=Decimal, parse_constant=reject_constant)


def n(x):
    # Empty own-side counts mean no applicable side, not an observed zero.
    # Zero is used only as the additive identity in a stated partition check.
    return 0 if x is None else x


def near(a, b, label):
    global largest_error
    if a is None or b is None:
        ensure(a is None and b is None, label)
        return
    err = abs(Decimal(a) - Decimal(b))
    largest_error = max(largest_error, err)
    ensure(err <= TOL * max(Decimal(1), abs(Decimal(a)), abs(Decimal(b))), label)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def is_sha(s):
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        ensure(len(header) == len(set(header)), "unique CSV headers")
        rows = list(reader)
    return header, rows


LITERAL = {
    "candidate_id", "category", "evidence_tier", "source_panel", "view",
    "week_view", "left", "right", "probability_confidence", "fallback_interpretation",
}


def typed(row):
    return {k: (v if k in LITERAL or k.endswith("_sha256") else
                None if v == "" else decode(v)) for k, v in row.items()}


def interval(x, bounds, label):
    ensure(isinstance(x, list) and len(x) == 2, label + " shape")
    ensure(all(isinstance(v, (int, Decimal)) and Decimal(v).is_finite() for v in x), label + " finite")
    ensure(x[0] <= x[1], label + " ordered")
    if bounds:
        ensure(bounds[0] <= x[0] <= x[1] <= bounds[1], label + " bounds")


def equivalent(a, b, label):
    if isinstance(a, dict):
        ensure(isinstance(b, dict) and set(a) == set(b), label + " keys")
        for k in a:
            equivalent(a[k], b[k], label + "." + k)
    elif isinstance(a, list):
        ensure(isinstance(b, list) and len(a) == len(b), label + " length")
        for i, (v, w) in enumerate(zip(a, b)):
            equivalent(v, w, label + "." + str(i))
    elif isinstance(a, (int, Decimal)) and not isinstance(a, bool):
        near(a, b, label)
    else:
        ensure(a == b, label)


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (55, 60))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    manifest_bytes = (PUBLIC / "MANIFEST_V1.json").read_bytes()
    manifest = decode(manifest_bytes)
    ensure(manifest["source"]["compressed_sha256"] == SOURCE, "source score binding")
    ensure(manifest["summary_rows"] == 1782 and manifest["paired_rows"] == 768,
           "expected projection row counts")
    ensure(manifest["old_annual_and_weekly_parity_checks"] == 474, "runtime oracle-count binding")
    ensure(all(v == 0 for v in manifest["source_counts"].values()), "source reports zero new predictive work")
    files = manifest["files"]
    ensure(len(files) == 38, "38 CSV shards")
    _, index = read_csv(PUBLIC / "INDEX.csv")
    ensure([{**x, "rows": int(x["rows"]), "bytes": int(x["bytes"])} for x in index] == files,
           "INDEX exact manifest projection")
    ensure(len(list(PUBLIC.iterdir())) == 41, "41-file published projection")
    summaries, pairs, headers = [], [], {}
    for f in files:
        ensure(Path(f["path"]).name == f["path"], "relative CSV shard names")
        b = (PUBLIC / f["path"]).read_bytes()
        ensure(len(b) == f["bytes"] and sha(b) == f["sha256"], "CSV bytes and SHA256")
        ensure(len(b) <= 61440, "CSV size cap")
        ensure(b"/tmp/" not in b and b"/workspace/" not in b, "no private local locator in CSV")
        header, raw = read_csv(PUBLIC / f["path"])
        ensure(len(raw) == f["rows"], "CSV shard row count")
        kind = "own" if f["path"].startswith("OWN_RECORDS_") else "pairs"
        if kind not in headers:
            headers[kind] = header
        ensure(header == headers[kind], "consistent headers per CSV product")
        (summaries if kind == "own" else pairs).extend(map(typed, raw))
    ensure(len(summaries) == 1782 and len(pairs) == 768, "all 2550 aggregate rows read")
    own = {}
    groups = defaultdict(dict)
    for r in summaries:
        key = (r["category"], r["candidate_id"], r["view"], r["week_view"])
        ensure(key not in own, "unique own-record identity")
        own[key] = r
        groups[key[:3]][key[3]] = r
        for field in ("eligible_mask_sha256", "decided_mask_sha256"):
            ensure(is_sha(r[field]), "own mask digest shape")
        ensure(r["requested_weeks"] == list(range(1, 9)), "requested W1-8 retained")
        ensure(set(r["actual_scored_weeks"]) <= set(range(1, 6)), "actual scored weeks W1-5 only")
        ensure(r["source_panel"] == "ANNUAL_NAMED_NJ", "annual source panel isolation")
        ensure(r["probability_confidence"] == "N/A_POINT_ONLY;NO_INFERRED_PROBABILITY_OR_EV", "point-only own type")
        for side in ("over", "under", "combined"):
            w, l, d, s = [r[side + "_" + k] for k in ("wins", "losses", "decided", "selected")]
            ensure(d == n(w) + n(l) and 0 <= d <= s, "own W+L=decided<=selected")
            near(r[side + "_rate"], Decimal(n(w)) / d if d else None, "own decided-rate arithmetic")
        for metric in ("wins", "losses", "decided", "selected"):
            ensure(n(r["over_" + metric]) + n(r["under_" + metric]) == n(r["combined_" + metric]), "own side partition")
        ensure(sum(r["states"].values()) == r["eligible"], "states partition eligible")
        ensure(r["states"].get("WIN", 0) == n(r["combined_wins"]) and r["states"].get("LOSS", 0) == n(r["combined_losses"]), "state wins/losses match record")
        ensure(r["unavailable"] == r["states"].get("UNAVAILABLE_FORECAST", 0), "unavailability explicit state")
        ensure(r["abstentions"] == r["states"].get("ABSTAIN", 0), "abstention explicit state")
        ensure(r["available"] == r["eligible"] - r["unavailable"], "available partition")
        ensure(r["combined_selected"] == r["available"] - r["abstentions"], "selected partition")
        near(r["coverage"], Decimal(r["combined_selected"]) / r["eligible"] if r["eligible"] else None, "coverage arithmetic")
        ensure(sum(r["fallback_states"].values()) == r["eligible"], "recorded fallback states partition")
        ensure(sum(r["unavailable_reasons"].values()) == r["unavailable"], "unavailable reasons partition")
        nu = r["numerical"]
        ensure(sum(nu["learned_or_fallback_states"].values()) == nu["scored"], "numerical fallback states partition")
        ensure(0 <= nu["scored"] <= r["eligible"], "numerical count bounds")
        metrics = ("MAE", "MSE", "absolute_error_p90", "bias", "max_absolute_error")
        if nu["scored"]:
            ensure(all(isinstance(nu[k], (Decimal, int)) and Decimal(nu[k]).is_finite() for k in metrics), "finite numerical metrics")
            mae, mse, bias, mx, p90 = [nu[k] for k in ("MAE", "MSE", "bias", "max_absolute_error", "absolute_error_p90")]
            ensure(0 <= abs(bias) <= mae + TOL and 0 <= p90 <= mx + TOL and mae <= mx + TOL, "numerical error inequalities")
            ensure(mae * mae <= mse + TOL and mse <= mx * mx + TOL, "MSE error inequalities")
        else:
            ensure(all(nu[k] is None for k in metrics), "no numerical outcomes means N/A")
        u = r["uncertainty"]
        if r["combined_decided"]:
            interval([u["low"], u["high"]], (0, 1), "own uncertainty")
            ensure(u["week_clusters"] == len(r["actual_scored_weeks"]), "own uncertainty week metadata")
        else:
            ensure(u["low"] is None and u["high"] is None, "empty uncertainty N/A")
        if r["week_view"] in ("6", "7", "8"):
            ensure(r["eligible"] == 0 and r["combined_rate"] is None and r["decided_mask_sha256"] == EMPTY, "W6-8 explicit empty annual rows")
    ensure(len(groups) == 198, "99 products by two population views")
    additive = [side + "_" + metric for side in ("over", "under", "combined") for metric in ("wins", "losses", "decided", "selected")] + ["eligible", "available", "unavailable", "abstentions", "games", "player_games"]
    for group in groups.values():
        ensure(set(group) == {"ALL", *map(str, range(1, 9))}, "each product has cumulative plus eight weekly views")
        annual = group["ALL"]
        weeks = [group[str(i)] for i in range(1, 9)]
        for f in additive:
            ensure(sum(n(w[f]) for w in weeks) == n(annual[f]), "weekly-to-cumulative count reconciliation")
        for f in ("states", "fallback_states", "unavailable_reasons"):
            total = Counter()
            for w in weeks:
                total.update(w[f])
            ensure(dict(total) == annual[f], "weekly-to-cumulative state reconciliation")
        count = sum(w["numerical"]["scored"] for w in weeks)
        ensure(count == annual["numerical"]["scored"], "weekly numerical count reconciliation")
        if count:
            for f in ("MAE", "MSE", "bias"):
                near(sum(w["numerical"][f] * w["numerical"]["scored"] for w in weeks if w["numerical"]["scored"]) / count,
                     annual["numerical"][f], "weighted weekly numerical reconciliation")
            near(max(w["numerical"]["max_absolute_error"] for w in weeks if w["numerical"]["scored"]), annual["numerical"]["max_absolute_error"], "maximum error weekly reconciliation")
    categories = sorted({r["category"] for r in summaries})
    views = sorted({r["view"] for r in summaries})
    ensure(len(categories) == 10 and len(views) == 2, "ten annual categories and two views")
    for cat in categories:
        for view in views:
            for week in ("ALL", *map(str, range(1, 9))):
                o = own[(cat, "ALWAYS_OVER", view, week)]
                u = own[(cat, "ALWAYS_UNDER", view, week)]
                ensure(o["eligible_mask_sha256"] == u["eligible_mask_sha256"] and o["decided_mask_sha256"] == u["decided_mask_sha256"], "constant controls identical masks")
                ensure(o["combined_decided"] == u["combined_decided"] and n(o["combined_wins"]) + n(u["combined_wins"]) == o["combined_decided"], "opposite constant controls reconcile")
    pair_lookup = {}
    for r in pairs:
        key = (r["category"], r["view"], r["left"], r["right"])
        ensure(key not in pair_lookup, "unique pair identity")
        pair_lookup[key] = r
        left = own[(r["category"], r["left"], r["view"], "ALL")]
        right = own[(r["category"], r["right"], r["view"], "ALL")]
        count, lw, rw, dis = [r[k] for k in ("common_decided", "left_wins", "right_wins", "side_disagreements")]
        ensure(0 <= count <= min(left["combined_decided"], right["combined_decided"]), "paired count within own populations")
        ensure(0 <= lw <= min(count, n(left["combined_wins"])) and 0 <= rw <= min(count, n(right["combined_wins"])), "paired wins bounds")
        near(r["accuracy_change"], Decimal(lw - rw) / count if count else None, "paired accuracy difference")
        ensure(abs(lw - rw) <= dis <= count, "paired disagreement bounds")
        cells_twice = [dis + lw - rw, dis - lw + rw, lw + rw - dis, 2 * count - lw - rw - dis]
        ensure(all(v >= 0 and v % 2 == 0 for v in cells_twice), "paired feasible win/loss agreement table")
        for field in ("decided_mask_sha256", "numerical_mask_sha256", "law_mask_sha256"):
            ensure(is_sha(r[field]), "pair mask digest shape")
        for side, own_row in (("left", left), ("right", right)):
            if count == own_row["combined_decided"]:
                ensure(r["decided_mask_sha256"] == own_row["decided_mask_sha256"] and r[side + "_wins"] == n(own_row["combined_wins"]), "full-common-mask identity and own wins")
        if left["decided_mask_sha256"] == right["decided_mask_sha256"]:
            ensure(count == left["combined_decided"] == right["combined_decided"], "identical own masks retain full common counts")
        ensure(r["common_law_events"] == 0 and r["law_mask_sha256"] == EMPTY and all(r[k] is None for k in ("Brier_change", "Brier_game_interval95", "Brier_week_interval95")), "no inferred probability scores")
        cn = r["common_numerical"]
        ensure(0 <= cn <= min(left["numerical"]["scored"], right["numerical"]["scored"]), "paired numerical count bounds")
        if cn:
            interval(r["MAE_game_interval95"], None, "paired numerical game uncertainty")
            interval(r["MAE_week_interval95"], None, "paired numerical week uncertainty")
            if cn == left["numerical"]["scored"] == right["numerical"]["scored"]:
                near(r["MAE_change"], left["numerical"]["MAE"] - right["numerical"]["MAE"], "complete paired numerical difference")
        else:
            ensure(r["MAE_change"] is None and r["MAE_game_interval95"] is None and r["MAE_week_interval95"] is None and r["numerical_mask_sha256"] == EMPTY, "no paired numerical data means N/A")
        if count:
            interval(r["game_interval95"], (-1, 1), "paired game uncertainty")
            interval(r["week_interval95"], (-1, 1), "paired week uncertainty")
            ensure(0 < r["game_clusters"] <= min(left["games"], right["games"]) and 0 < r["week_clusters"] <= 5, "paired cluster metadata bounds")
    oracles = 0
    for p in manifest["source_original_point_products"]:
        ensure(len(p["weekly_aggregate_oracle"]) == 5, "five original weekly source oracles")
        for week, oracle in [("ALL", p["annual_aggregate_oracle"]), *p["weekly_aggregate_oracle"].items()]:
            row = own[(p["category"], p["candidate_id"], "ORIGINAL_QUERY_INTERSECTION", week)]
            for side in ("OVER", "UNDER", "COMBINED"):
                for k in ("wins", "losses", "decided"):
                    ensure(n(row[side.lower() + "_" + k]) == n(oracle[side][k]), "public original annual/weekly oracle parity")
            oracles += 1
    ensure(oracles == 474, "all 474 public oracle views checked")
    for r in summaries:
        if r["view"] == "ORIGINAL_QUERY_INTERSECTION":
            full = own[(r["category"], r["candidate_id"], "FULL_ELIGIBLE_ANNUAL_BOARD", r["week_view"])]
            ensure(r["eligible"] <= full["eligible"] and r["combined_decided"] <= full["combined_decided"], "original-query subset count bounds")
            if r["eligible_mask_sha256"] == full["eligible_mask_sha256"]:
                ensure(r["eligible"] == full["eligible"], "equal eligible digest implies equal aggregate count")
            if r["decided_mask_sha256"] == full["decided_mask_sha256"]:
                ensure(r["combined_decided"] == full["combined_decided"], "equal decided digest implies equal aggregate count")
    headline_path = REPORT / "A_POINT_PAIR_HEADLINES_COMPACT_V1.json"
    headline_bytes = headline_path.read_bytes()
    headlines = decode(headline_bytes)
    ensure(headlines["source_score_sha256"] == SOURCE, "headline source SHA binding")
    ensure(len(headlines["panels"]) == 10, "ten headline categories")
    headline_rows = Counter()
    for panel in headlines["panels"]:
        for label, records in panel.items():
            if label == "category":
                continue
            for item in records:
                headline_rows[label] += 1
                if "candidate_id" in item:
                    row = own[(panel["category"], item["candidate_id"], headlines["view"], "ALL")]
                    for key, value in item.items():
                        if key in ("OVER", "UNDER", "COMBINED"):
                            equivalent(value, {k: row[key.lower() + "_" + k] for k in value}, "headline own side projection")
                        else:
                            equivalent(value, row[key], "headline own field projection")
                else:
                    row = pair_lookup[(panel["category"], headlines["view"], item["left"], item["right"])]
                    for key, value in item.items():
                        equivalent(value, row[key], "headline named-pair projection")
        # Verify raw maxima/minima only within the stated own populations.
        catrows = [r for r in summaries if r["category"] == panel["category"] and r["view"] == headlines["view"] and r["week_view"] == "ALL" and not r["candidate_id"].startswith("ALWAYS_")]
        for side, label in (("over", "raw_Over_maxima_own_samples"), ("under", "raw_Under_maxima_own_samples")):
            supported = [r for r in catrows if r[side + "_decided"]]
            best = max(r[side + "_rate"] for r in supported)
            for item in panel[label]:
                near(item[side.upper()]["rate"], best, "headline raw-side maximum within own samples")
        nums = [r for r in catrows if r["numerical"]["scored"]]
        bestmae = min(r["numerical"]["MAE"] for r in nums)
        for item in panel["own_population_numerical_leaders"]:
            near(item["numerical"]["MAE"], bestmae, "headline own-population minimum MAE")
    output = {
        "id": "PUBLIC_AGGREGATE_INDEPENDENT_RECEIPT_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS_PUBLIC_AGGREGATE_ARITHMETIC_AND_PROJECTION",
        "reviewer": "/root/decision_peer_receipts",
        "independence": "Independent Python stdlib CSV/Decimal arithmetic; no author exporter/common scorer invocation.",
        "source_score_sha256": SOURCE,
        "public_manifest": {"path": str((PUBLIC / "MANIFEST_V1.json").relative_to(ROOT)), "bytes": len(manifest_bytes), "sha256": sha(manifest_bytes)},
        "public_headlines": {"path": str(headline_path.relative_to(ROOT)), "bytes": len(headline_bytes), "sha256": sha(headline_bytes)},
        "verification_code": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha(Path(__file__).read_bytes())},
        "counts": {"summary_rows": len(summaries), "paired_rows": len(pairs), "csv_shards": len(files), "original_products": 79, "public_original_annual_weekly_oracle_views": oracles, "category_views": len(groups), "empty_W6_W7_W8_summaries": sum(r["week_view"] in ("6", "7", "8") for r in summaries), "headline_records": dict(headline_rows)},
        "checks": dict(sorted(checks.items())),
        "largest_absolute_decimal_comparison_error": str(largest_error),
        "relative_and_absolute_tolerance": str(TOL),
        "environment": {"python": platform.python_version(), "library": "Python stdlib only", "CPU_seconds": time.process_time() - start_cpu, "wall_seconds": time.monotonic() - start_wall, "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024, "hard_CPU_seconds": 60, "memory_bytes": 512 * 1024 * 1024},
        "checked_scope": ["All CSV hashes, byte counts, row counts, index projections and product headers", "Each own-side W/L/decided/rate and side/weekly/cumulative/coverage/state partition", "Each numerical metric's finite/range inequalities and weighted weekly arithmetic", "All 768 named pairs: feasible agreement/disagreement table, differences, common-count bounds, mask digest consistency and CI metadata bounds", "All 474 public retained original annual and weekly aggregate oracles", "All compact headline candidate and pair fields against exact CSV records; own-sample raw side maxima and minimum MAE"],
        "not_checked": ["No private forecast/source/offer rows, source clocks, fitted models, original roster membership or native storage read", "No raw-member identity/hash reconstruction: published digests checked for format and cross-projection consistency only", "No independent regrading, fit/inference reproduction, bootstrap resampling or confidence-interval coverage validation", "No direct source-gzip decoded/byte parity check: private source SHA and decoded hash are published bindings, while CSV hashes were independently read", "No proof of strongest cross-session incumbent, replacement superiority, new offered-line weeks, current issuance, website admission or served use"],
        "semantic_limits": ["Annual source is timing-unverified actual lines from 2026 W1-5, seven-day current-vintage reconstruction, exposed development; W6-8 empty rows do not qualify those weeks", "FULL_ELIGIBLE_ANNUAL_BOARD and ORIGINAL_QUERY_INTERSECTION remain distinct; reconstructed expected query universe is not authenticated pregame roster", "Unknown participation remains explicit; blank and None fallback states are unspecified, not learned-only evidence", "Point-direction/numerical exports do not imply probability, confidence, EV or Top Picks; Brier fields correctly remain N/A", "Raw side maxima are different selected subsets and are not a combined router; named-pair contrasts retain each pair's common mask", "Runtime 474-parity receipt is supplemented by independent public-oracle arithmetic, not private row parity"],
        "new_fits": 0, "new_inference": 0, "new_grading": 0, "native_reads": 0, "native_writes": 0,
    }
    ensure(not RECEIPT.exists(), "append-only new review receipt")
    RECEIPT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": output["verdict"], "receipt": str(RECEIPT.relative_to(ROOT)), "bytes": RECEIPT.stat().st_size, "sha256": sha(RECEIPT.read_bytes()), "checks": sum(checks.values()), "counts": output["counts"], "largest_error": str(largest_error)}))


if __name__ == "__main__":
    main()
