#!/usr/bin/env python3
"""Review completed ATT aggregate arithmetic without NFL rows or scorer calls."""
from pathlib import Path
from decimal import Decimal
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import platform
import resource
import time

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/abc-championship/category-decision-release-01"
RESULT = REPORT / "B_ATT_ALIAS_RESULTS_V2.json.gz"
OUT = REPORT / "B_ATT_ALIAS_AGGREGATE_INDEPENDENT_RECEIPT_V1.json"
EXPECTED = "0dc195065ad35a0aabd3e0dec89514ca3ba6a857e9327c25078d04f59280eafb"
TOL = Decimal("1e-12")
counts = Counter()


def check(ok, name):
    counts[name] += 1
    if not ok:
        raise AssertionError(name)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def decode(b):
    def bad(s):
        raise ValueError("Non-finite JSON: " + s)
    return json.loads(b, parse_float=Decimal, parse_constant=bad)


def n(x):
    return 0 if x is None else x


def close(x, y, label):
    check(x is None and y is None or x is not None and y is not None and
          abs(Decimal(x) - Decimal(y)) <= TOL * max(1, abs(Decimal(x)), abs(Decimal(y))), label)


def interval(x, label):
    check(isinstance(x, list) and len(x) == 2 and -1 <= x[0] <= x[1] <= 1, label)


def main():
    cpu, wall = time.process_time(), time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (25, 30))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    raw = RESULT.read_bytes()
    check(len(raw) == 17143 and sha(raw) == EXPECTED, "completed aggregate exact bytes and hash")
    decoded = gzip.decompress(raw)
    result = decode(decoded)
    check(result["state"] == "COMPLETED_EXACT_ATT_ALIAS_COVERAGE_NO_MODEL_CHANGE", "completed scoped state")
    go_path = REPORT / "B_ATT_ALIAS_ROOT_GO_V1.json"
    go_bytes = go_path.read_bytes()
    go = decode(go_bytes)
    check(sha(go_bytes) == result["root_protocol_sha256"], "actual root GO SHA")
    check(go["state"] == "ROOT_REGISTERED_SCORING_GO", "root GO state")
    oldref = result["old_result"]
    oldraw = (ROOT / oldref["path"]).read_bytes()
    check(len(oldraw) == oldref["bytes"] and sha(oldraw) == oldref["sha256"], "old public aggregate bytes/hash")
    old = decode(oldraw)
    check(result["candidate_ids"] == old["candidate_ids"] and len(result["candidate_ids"]) == 9, "unchanged nine products")
    check(result["counts"] == dict(native_writes=0, new_fits=0, new_model_inference=0, new_source_collection=0, production_writes=0), "no new inference/model/source/production work")
    check(result["newly_observed_games_weeks"] == 0 and result["newly_available_B_point_outputs"] == 12 and result["B_output_products_unchanged"] == 2, "coverage versus new games distinction")
    alias = result["newly_qualified_physical_cases"]
    check(len(alias) == 6 and len({a["case_sha256"] for a in alias}) == 6, "six unique case commitments")
    for a in alias:
        check(a["old_reason"] == "B_TEAM_OPPONENT_CONTRACT_MISMATCH" and a["new_state"] == "IDENTITY_AND_CLOCK_QUALIFIED", "alias-only qualification reason")
        check({"LA", "LAR"} <= set(a["tokens"]) and "LAC" not in a["tokens"] and 1 <= a["week"] <= 5, "alias tokens and weeks")
    rows = result["summaries"]
    pairs = result["paired"]
    check(len(rows) == 324 and len(pairs) == 50, "all aggregate rows present")
    lookup, groups = {}, defaultdict(dict)
    for r in rows:
        k = (r["view"], r["source_panel"], r["candidate_id"], str(r["week_view"]))
        check(k not in lookup, "unique summary identity")
        lookup[k] = r
        groups[k[:3]][k[3]] = r
        check(r["category"] == "pass_att", "ATT-only product")
        for side in ("OVER", "UNDER", "COMBINED"):
            s = r[side]
            check(n(s["wins"]) + n(s["losses"]) == s["decided"] <= s["selected"], "own wins/losses/decided partition")
            close(s["rate"], Decimal(n(s["wins"])) / s["decided"] if s["decided"] else None, "own rate")
        for metric in ("wins", "losses", "decided", "selected"):
            check(n(r["OVER"][metric]) + n(r["UNDER"][metric]) == n(r["COMBINED"][metric]), "own side partition")
        check(sum(r["states"].values()) == r["eligible"] and r["states"].get("WIN", 0) == n(r["COMBINED"]["wins"]) and r["states"].get("LOSS", 0) == n(r["COMBINED"]["losses"]), "states/eligible/WL reconciliation")
        check(sum(r["outer_outcomes"].values()) == r["eligible"], "outer outcomes partition")
        check(sum(x["rows"] for x in r["forecast_outcome_cross_counts"]) == r["eligible"], "forecast/outcome cross-count partition")
        check(r["unavailable"] == r["states"].get("UNAVAILABLE_FORECAST", 0) and sum(r["unavailable_reasons"].values()) == r["unavailable"], "unavailability distinct")
        check(0 <= r["fallback_outputs"] <= r["eligible"], "fallback count bounds")
        close(r["coverage"], Decimal(r["COMBINED"]["selected"]) / r["eligible"] if r["eligible"] else None, "coverage")
        check(set(r["actual_scored_weeks"]) <= set(range(1, 6)), "scored W1-5 only")
        if str(r["week_view"]) in ("6", "7", "8"):
            check(r["eligible"] == 0 and r["COMBINED"]["rate"] is None, "W6-8 empty not additional evidence")
        nu = r["numerical_same_offer_mask"]
        if nu["scored"]:
            check(abs(nu["bias"]) <= nu["MAE"] + TOL and nu["MAE"] ** 2 <= nu["MSE"] + TOL, "numerical inequalities")
        else:
            check(all(nu[x] is None for x in ("MAE", "MSE", "bias")), "unscored numerical metrics N/A")
        u = r["uncertainty"]
        if r["COMBINED"]["decided"]:
            check(0 <= u["low"] <= u["high"] <= 1 and u["week_clusters"] == len(r["actual_scored_weeks"]), "own uncertainty bounds/metadata")
    for g in groups.values():
        check(set(g) == {"ALL", *map(str, range(1, 9))}, "all requested weeks plus cumulative")
        annual = g["ALL"]
        for side in ("OVER", "UNDER", "COMBINED"):
            for metric in ("wins", "losses", "decided", "selected"):
                check(sum(n(g[str(w)][side][metric]) for w in range(1, 9)) == n(annual[side][metric]), "weekly-cumulative side reconciliation")
        for key in ("eligible", "unavailable", "abstentions", "games", "player_games", "fallback_outputs"):
            check(sum(g[str(w)][key] for w in range(1, 9)) == annual[key], "weekly-cumulative population reconciliation")
        for key in ("states", "outer_outcomes", "unavailable_reasons"):
            c = Counter()
            for w in range(1, 9):
                c.update(g[str(w)][key])
            check(dict(c) == annual[key], "weekly-cumulative state reconciliation")
        ct = sum(g[str(w)]["numerical_same_offer_mask"]["scored"] for w in range(1, 9))
        check(ct == annual["numerical_same_offer_mask"]["scored"], "weekly-cumulative numerical population")
        if ct:
            for key in ("MAE", "MSE", "bias"):
                close(sum(g[str(w)]["numerical_same_offer_mask"][key] * g[str(w)]["numerical_same_offer_mask"]["scored"] for w in range(1, 9) if g[str(w)]["numerical_same_offer_mask"]["scored"]) / ct, annual["numerical_same_offer_mask"][key], "weekly weighted numerical metric")
    oldlookup = {(r["view"], r["source_panel"], r["candidate_id"], str(r["week_view"])): r for r in old["scores"]}
    parity = Counter()
    bid = [c for c in result["candidate_ids"] if c.startswith("B-")]
    for r in rows:
        if r["view"] == "ORIGINAL_STRICT_B81":
            oldview, label = "SHARED_B_AVAILABLE", "strict81_summary"
        elif r["candidate_id"] not in bid:
            oldview, label = "FULL_A_BOARD", "unchanged_full87_A_controls"
        else:
            continue
        previous = oldlookup[(oldview, r["source_panel"], r["candidate_id"], str(r["week_view"]))]
        check(set(r) - set(previous) <= {"category"}, "only declared category metadata added")
        for f in r:
            if f != "view" and f in previous:
                check(r[f] == previous[f], "independent exact old summary parity")
        parity[label] += 1
    check(parity == {"strict81_summary": 162, "unchanged_full87_A_controls": 126}, "all requested summary parity cells independently checked")
    pairkeys = set()
    for r in pairs:
        k = (r["view"], r["left"], r["right"])
        check(k not in pairkeys, "unique pair identity")
        pairkeys.add(k)
        left = lookup[(r["view"], "ALL", r["left"], "ALL")]
        right = lookup[(r["view"], "ALL", r["right"], "ALL")]
        ct, lw, rw, dis = [r[x] for x in ("common_decided", "left_wins", "right_wins", "side_disagreements")]
        check(ct <= min(left["COMBINED"]["decided"], right["COMBINED"]["decided"]), "paired common count bounds")
        check(lw - rw == r["win_change"] and abs(lw - rw) <= dis <= ct, "pair win difference/disagreements")
        check(all(x >= 0 and x % 2 == 0 for x in (dis + lw - rw, dis - lw + rw, lw + rw - dis, 2 * ct - lw - rw - dis)), "pair feasible agreement table")
        check(r["common_mask_sha256"] == left["decided_mask_sha256"] == right["decided_mask_sha256"], "full common mask commitments")
        check(lw == left["COMBINED"]["wins"] and rw == right["COMBINED"]["wins"], "pair wins versus exact own population")
        check(r["game_clusters"] == left["games"] == right["games"] and r["week_clusters"] == 5, "pair game/week metadata")
        for key in ("paired_accuracy_change_interval95", "paired_week_block_accuracy_change_interval95"):
            interval(r[key], "pair CI bounds/order")
        if r["view"] == "ORIGINAL_STRICT_B81":
            previous = next(x for x in old["paired_controls"] if x["view"] == "SHARED_B_AVAILABLE" and x["left"] == r["left"] and x["right"] == r["right"])
            for f in r:
                if f != "view":
                    check(r[f] == previous[f], "independent exact old pair parity")
            parity["strict81_pairs"] += 1
    check(parity["strict81_pairs"] == 25, "all original pairs independently checked")
    deltas = []
    for cid in bid:
        full = lookup[("FULL_A_BOARD_ALIAS_QUALIFIED87", "ALL", cid, "ALL")]
        strict = lookup[("ORIGINAL_STRICT_B81", "ALL", cid, "ALL")]
        check(full["eligible"] - strict["eligible"] == 6, "six newly joined eligible outputs per B product")
        delta = {k: full["COMBINED"][k] - strict["COMBINED"][k] for k in ("wins", "losses", "decided", "selected")}
        check(delta["decided"] == delta["selected"] == 6 and delta["wins"] + delta["losses"] == 6, "six-case incremental record")
        deltas.append({"candidate_id": cid, "full87_record": full["COMBINED"], "strict81_record": strict["COMBINED"], "six_case_coverage_delta": delta})
    check(not OUT.exists(), "append-only receipt")
    record = {
        "id": "B_ATT_ALIAS_AGGREGATE_INDEPENDENT_RECEIPT_V1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS_COMPLETED_PUBLIC_AGGREGATE_ARITHMETIC_AND_OLD_PARITY", "reviewer": "/root/decision_peer_receipts",
        "result": {"path": str(RESULT.relative_to(ROOT)), "compressed_bytes": len(raw), "compressed_sha256": sha(raw), "decoded_bytes": len(decoded), "decoded_sha256": sha(decoded)},
        "root_GO_sha256": sha(go_bytes), "old_public_result": oldref,
        "verification_code": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha(Path(__file__).read_bytes())},
        "verified_counts": {"summaries": len(rows), "pairs": len(pairs), **parity, "new_alias_cases": 6, "new_point_outputs": 12, "new_observed_games_or_weeks": 0},
        "checks": dict(counts), "six_case_coverage_deltas": deltas,
        "own_cumulative_records": [{"candidate_id": cid, "record": lookup[("FULL_A_BOARD_ALIAS_QUALIFIED87", "ALL", cid, "ALL")]["COMBINED"]} for cid in result["candidate_ids"]],
        "scientific_interpretation": "Six-case identity join repair extends unchanged B point products. It changes complete-system coverage; it is not a new learned-skill improvement. Mean43/87 and median44/87 do not beat matched Always-Over46/87. Five source weeks are timing-unverified retrospective actual offers, not authenticated issuance, probabilities or Top Picks.",
        "scope_limits": ["Only completed aggregate gzip, old public aggregates, root GO metadata and verifier source were read; no NFL source/offer/forecast rows, models or native namespace read.", "No independent regrading, inference, fitting or bootstrap resampling. CI finite/order/range and exact old parity checked, not interval calibration or raw clusters.", "Case/hash uniqueness and cross-aggregate mask consistency were checked; raw identity/team alias corrections were not independently reconstructed from restricted rows.", "Scorer and source math reviewed separately in B_ATT_ALIAS_PREEXEC_INDEPENDENT_REVIEW_V1; this receipt checks executed aggregate arithmetic and original aggregate parity.", "No C intake/admission, primary release or served website verification inferred."],
        "actual_scoring_resources_from_result": result["resources"], "scoring_cumulative_CPU_seconds": "172.735635990", "scoring_original_CPU_cap": 200,
        "review_resources": {"CPU_seconds": time.process_time() - cpu, "wall_seconds": time.monotonic() - wall, "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024, "python": platform.python_version(), "library": "stdlib only", "CPU_cap_seconds": 30, "memory_cap_bytes": 256 * 1024 * 1024},
        "new_fits": 0, "new_inference": 0, "new_grading": 0, "native_reads": 0, "native_writes": 0,
    }
    OUT.write_text(json.dumps(record, indent=2, sort_keys=True, default=float) + "\n")
    print(json.dumps({"verdict": record["verdict"], "path": str(OUT.relative_to(ROOT)), "bytes": OUT.stat().st_size, "sha256": sha(OUT.read_bytes()), "checks": sum(counts.values()), "parity": dict(parity)}))


if __name__ == "__main__":
    main()
