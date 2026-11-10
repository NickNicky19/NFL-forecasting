"""Independent read-only verification of the retained A/C reception replay.

This reconstructs the existing declared decisions; it creates no new policy,
forecast, fit, private artifact, or shared evaluator. Invoke only after the
owner supplies the exact completed public result digest.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime
from decimal import Decimal
import hashlib
import json
import lzma
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "reports/abc-championship/player-context-acceptance-01"
ALLOCATION = "f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26"
VERSION = "PLAYER-CONTEXT-ACCEPTANCE-01-A-peer-overlap-v1"
PREFIX = "C::PLAYER-CONTEXT-MATCHUP-01::v1.1::"
PRODUCTS = [[m, p] for m in ["P1", "P2"] for p in ["mean", "median"]]
EXPECTED_COLUMNS = [
    "game", "player", "week", "original_line_exact_text", "actual", "appearance",
    "opportunity", "source_panel", "source_sha256", "source_quote_time",
    "quote_timing_status", "points", "fallbacks", "unavailability_reasons",
    "C_query_horizon_UTC", "selected_sides", "statistical_grades",
]


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in [int, float] and math.isfinite(value)


def same(left, right, path="root", allow_extra=False):
    """Compare independent counts/contracts exactly and floats within rounding."""
    if isinstance(right, dict):
        checked(isinstance(left, dict), "object type mismatch: " + path)
        if not allow_extra:
            checked(set(left) == set(right), "object keys mismatch: " + path)
        for key, value in right.items():
            checked(key in left, "missing aggregate field: " + path + "." + key)
            same(left[key], value, path + "." + key)
    elif isinstance(right, list):
        checked(isinstance(left, list) and len(left) == len(right), "list mismatch: " + path)
        for i, (a, b) in enumerate(zip(left, right)):
            same(a, b, path + "." + str(i))
    elif type(right) is float:
        checked(number(left) and math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12),
                "numeric aggregate mismatch: " + path)
    else:
        checked(type(left) is type(right) and left == right, "aggregate mismatch: " + path)


def side(point, line):
    if point is None:
        return None
    checked(number(point), "nonfinite or invalid retained point")
    point = Decimal(str(point))
    return "OVER" if point > line else "UNDER" if point < line else "ABSTAIN"


def grade(selected, appearance, actual, line):
    if selected is None:
        return "UNAVAILABLE_FORECAST"
    if selected == "ABSTAIN":
        return "ABSTAIN"
    checked(selected in ["OVER", "UNDER"], "invalid selected side")
    if appearance != "PLAYED":
        return {"DNP": "DNP", "PENDING": "PENDING", "UNKNOWN": "UNKNOWN_PARTICIPATION"}[appearance]
    if actual is None:
        return "MISSING_ACTUAL"
    actual = Decimal(str(actual))
    if actual == line:
        return "PUSH"
    return "WIN" if (actual > line and selected == "OVER") or (actual < line and selected == "UNDER") else "LOSS"


def aggregate(rows):
    result = {}
    for selected in ["OVER", "UNDER", "COMBINED"]:
        rr = [r for r in rows if r["side"] in ["OVER", "UNDER"]] if selected == "COMBINED" else [r for r in rows if r["side"] == selected]
        wins = sum(r["status"] == "WIN" for r in rr)
        losses = sum(r["status"] == "LOSS" for r in rr)
        decided = wins + losses
        result[selected] = dict(selected=len(rr), wins=wins if decided else None,
                                losses=losses if decided else None, decided=decided,
                                rate=wins / decided if decided else None)
    result.update(eligible=len(rows), unavailable=sum(r["side"] is None for r in rows),
                  abstentions=sum(r["side"] == "ABSTAIN" for r in rows),
                  states=dict(Counter(r["status"] for r in rows)),
                  games=len({r["game"] for r in rows}),
                  player_games=len({(r["game"], r["player"]) for r in rows}),
                  weeks=sorted({r["week"] for r in rows}),
                  coverage=result["COMBINED"]["selected"] / len(rows) if rows else None)
    return result


def numerical(rows):
    errors = [r["point"] - r["actual"] for r in rows if r["point"] is not None and r["actual"] is not None]
    return dict(scored=len(errors), MAE=math.fsum(abs(e) for e in errors) / len(errors) if errors else None,
                MSE=math.fsum(e * e for e in errors) / len(errors) if errors else None,
                bias=math.fsum(errors) / len(errors) if errors else None,
                max_absolute_error=max(map(abs, errors)) if errors else None)


def comparison(left, right, np):
    right_by_key = {r["opportunity"]: r for r in right}
    checked(len(right_by_key) == len(right), "duplicate paired opportunity")
    pp = [(a, right_by_key[a["opportunity"]]) for a in left
          if a["opportunity"] in right_by_key and a["status"] in ["WIN", "LOSS"]
          and right_by_key[a["opportunity"]]["status"] in ["WIN", "LOSS"]]
    groups = defaultdict(list)
    for a, b in pp:
        checked((a["game"], a["player"], a["line"], a["actual"]) ==
                (b["game"], b["player"], b["line"], b["actual"]), "paired contract mismatch")
        groups[a["game"]].append(int(a["status"] == "WIN") - int(b["status"] == "WIN"))
    interval = None
    if groups:
        game_keys = sorted(groups)
        game_n = np.array([len(groups[g]) for g in game_keys])
        game_diff = np.array([sum(groups[g]) for g in game_keys])
        rng = np.random.default_rng(20261110)
        sampled = rng.integers(0, len(game_keys), (500, len(game_keys)))
        draws = game_diff[sampled].sum(axis=1) / game_n[sampled].sum(axis=1)
        interval = list(map(float, np.quantile(draws, [.025, .975])))
    return dict(common_decided=len(pp), left_wins=sum(a["status"] == "WIN" for a, b in pp),
                right_wins=sum(b["status"] == "WIN" for a, b in pp),
                win_change=sum(int(a["status"] == "WIN") - int(b["status"] == "WIN") for a, b in pp),
                side_disagreements=sum(a["side"] != b["side"] for a, b in pp),
                game_clusters=len(groups), week_clusters=len({a["week"] for a, b in pp}),
                paired_accuracy_change_interval95=interval,
                common_mask_sha256=digest(encoded(sorted(a["opportunity"] for a, b in pp))))


def run(args):
    started, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (120, 125))
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("independent review wall cap")))
    signal.alarm(180)
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[name] = "1"
    import numpy as np
    from tools.category_topfive_matched12_storage_v1 import open_store, GO

    result_path = OUT / "C_POINTS_ON_A_REC_BOARD_V1.json"
    public_raw = result_path.read_bytes()
    checked(digest(public_raw) == args.result_sha256, "completed public receipt hash mismatch")
    public = json.loads(public_raw)
    checked(public["state"] == "OWNER_LOCAL_ZERO_REFIT_REPLAY_DURABLE_READBACK", "complete public receipt required")
    checked(public["version"] == VERSION, "unexpected retained replay version")
    store, _ = open_store(ROOT, allocation_sha256=ALLOCATION, root_go=GO, readonly=True)
    private = public["private_scorecard"]
    path = store.forward_root / "research" / VERSION / "RELATIONAL_SCORECARD.json.xz"
    body = path.read_bytes()
    checked(len(body) == private["bytes"] and digest(body) == private["sha256"], "retained scorecard binding mismatch")
    decoded = json.loads(lzma.decompress(body))
    manifest, retained = decoded["manifest"], decoded["rows"]
    checked(manifest["version"] == VERSION and manifest["protocol_sha256"] == public["protocol_sha256"], "manifest protocol mismatch")
    checked(manifest["row_columns"] == EXPECTED_COLUMNS and manifest["products"] == PRODUCTS, "retained table schema mismatch")
    checked(manifest["point_types"] == {"mean": "POISSONREGRESSOR_CONDITIONAL_EXPECTED_MEAN",
                                         "median": "LOWER_MEDIAN_OF_SAME_POISSON_LAW"}, "point-product type mismatch")
    checked(manifest["C_points_sha256"] == public["sources"]["C_points"] and
            manifest["C_feature_export_sha256"] == public["sources"]["C_features"] and
            manifest["A_offers_sha256"] == public["sources"]["A_offers"] and
            manifest["A_outcomes_sha256"] == public["sources"]["A_outcomes"], "source manifest mismatch")
    checked("NOT authenticated" in manifest["clocks"] and "TIMING_UNVERIFIED" in manifest["evidence"], "diagnostic clock limitations absent")
    checked(len(retained) == private["unique_offers"] and len(retained) * 4 == private["product_grade_rows"], "retained opportunity count mismatch")
    keys, identities, expanded = set(), set(), []
    representative = {}
    for values in retained:
        checked(len(values) == len(EXPECTED_COLUMNS), "relational row width mismatch")
        rr = dict(zip(EXPECTED_COLUMNS, values))
        checked(rr["opportunity"] and rr["opportunity"] not in keys, "missing/duplicate primary opportunity")
        checked((rr["game"], rr["player"]) not in identities, "duplicate player-game outcome")
        keys.add(rr["opportunity"]); identities.add((rr["game"], rr["player"]))
        checked(rr["appearance"] in ["PLAYED", "UNKNOWN", "DNP", "PENDING"], "unregistered appearance")
        checked(type(rr["week"]) is int and 1 <= rr["week"] <= 7, "unexpected scored period")
        line = Decimal(rr["original_line_exact_text"])
        checked(line.is_finite(), "nonfinite original line")
        actual = rr["actual"]
        if actual is not None:
            checked(rr["appearance"] == "PLAYED" and number(actual) and actual >= 0 and actual % 1 == 0,
                    "unsupported reception actual")
        outcome_state = "KNOWN_ACTUAL" if actual is not None else "MISSING_ACTUAL" if rr["appearance"] == "PLAYED" else "UNKNOWN_PARTICIPATION" if rr["appearance"] == "UNKNOWN" else rr["appearance"]
        for field in ["points", "fallbacks", "unavailability_reasons", "C_query_horizon_UTC", "selected_sides", "statistical_grades"]:
            checked(len(rr[field]) == 4, "product-array width mismatch")
        for i, (method, product) in enumerate(PRODUCTS):
            point, reason, fallback = rr["points"][i], rr["unavailability_reasons"][i], rr["fallbacks"][i]
            checked(point is None or (number(point) and point >= 0), "unsupported saved point")
            checked(point is None or product != "median" or point % 1 == 0, "noninteger count-law median")
            checked((point is None) == (reason is not None), "forecast missing-state mismatch")
            checked(reason in [None, "POSITION_CONTRACT_MISMATCH", "MISSING_C_CANONICAL_PLAYER_GAME", "C_POINT_UNAVAILABLE"], "unsupported missing-state reason")
            checked(type(fallback) is bool or fallback is None, "invalid fallback state")
            selected = side(point, line)
            status = grade(selected, rr["appearance"], actual, line)
            checked(selected == rr["selected_sides"][i] and status == rr["statistical_grades"][i], "retained decision or grade mismatch")
            row = dict(game=rr["game"], player=rr["player"], week=rr["week"], opportunity=rr["opportunity"],
                       source=rr["source_panel"], point=point, actual=actual, appearance=rr["appearance"],
                       line=line, side=selected, status=status, method=PREFIX + method, product=product,
                       reason=reason, fallback=fallback, outcome_state=outcome_state)
            expanded.append(row)
            if status in ["WIN", "LOSS", "UNKNOWN_PARTICIPATION", "UNAVAILABLE_FORECAST"] and status not in representative:
                representative[status] = dict(case_sha256=digest(encoded([rr["opportunity"], method, product])), status=status,
                                               exact_threshold_recalculated=True, retained_replay_side_matched=True,
                                               original_historical_recommendation_claim=False,
                                               decision_type="RETROSPECTIVE_DECLARED_POINT_RULE_REPLAY")
    checked(len(expanded) == private["product_grade_rows"], "expanded grade row count mismatch")
    source_counts = Counter(dict(zip(EXPECTED_COLUMNS, r))["source_panel"] for r in retained)
    same(public["coverage"], dict(outer_A_WRTE_offers=len(retained), outer_A_games=len({r["game"] for r in expanded}),
                                 outer_A_weeks=sorted({r["week"] for r in expanded}), source_panels=dict(source_counts),
                                 unavailable_product_rows_reasons=dict(Counter(r["reason"] for r in expanded if r["reason"]))), allow_extra=True)
    expected_score_keys = {(PREFIX + method, product, source, week) for method, product in PRODUCTS
                           for source in ["ALL"] + sorted(source_counts) for week in ["ALL"] + list(range(1, 8))}
    actual_score_keys = [(s["procedure_id"], s["product"], s["source_panel"], s["week_view"]) for s in public["scores"]]
    checked(len(actual_score_keys) == len(expected_score_keys) and set(actual_score_keys) == expected_score_keys,
            "incomplete or repeated source/week score grid")
    checked_scores = 0
    for summary in public["scores"]:
        rr = [r for r in expanded if r["method"] == summary["procedure_id"] and r["product"] == summary["product"]
              and (summary["source_panel"] == "ALL" or r["source"] == summary["source_panel"])
              and (summary["week_view"] == "ALL" or r["week"] == summary["week_view"])]
        same(summary, aggregate(rr), allow_extra=True)
        same(summary["numerical_on_same_offered_rows"], numerical(rr))
        same(summary, dict(fallback_outputs=sum(r["fallback"] is True for r in rr), learned_outputs=sum(r["fallback"] is False for r in rr),
                           unavailable_reasons=dict(Counter(r["reason"] for r in rr if r["reason"])),
                           outer_outcome_states_independent_of_forecast=dict(Counter(r["outcome_state"] for r in rr)),
                           forecast_availability_by_outer_outcome=[dict(forecast_available=a, outcome_state=s, rows=n) for (a, s), n in sorted(Counter((r["point"] is not None, r["outcome_state"]) for r in rr).items())]), allow_extra=True)
        scored_weeks = sorted({r["week"] for r in rr if r["status"] in ["WIN", "LOSS", "PUSH"]})
        same(summary, dict(actual_scored_weeks=scored_weeks, five_distinct_scored_week_floor=len(scored_weeks) >= 5,
                           qualification="DURATION_FLOOR_ONLY_NOT_ADMISSION" if len(scored_weeks) >= 5 else "BELOW_FIVE_WEEK_FLOOR"), allow_extra=True)
        for forced in ["OVER", "UNDER"]:
            controls = [dict(r, side=forced, status=grade(forced, r["appearance"], r["actual"], r["line"])) for r in rr]
            same(summary["constants"][forced], aggregate(controls), allow_extra=True)
        checked_scores += 1
    checked(len(public["scores"]) == 4 * (1 + len(source_counts)) * 8, "incomplete source/week score grid")
    expected_pair_keys = {(PREFIX + method, "ALWAYS_" + forced, product) for method, product in PRODUCTS for forced in ["OVER", "UNDER"]}
    expected_pair_keys.update((PREFIX + "P2", PREFIX + "P1", product) for product in ["mean", "median"])
    actual_pair_keys = [(s["left"], s["right"], s["product"]) for s in public["paired"]]
    checked(len(actual_pair_keys) == len(expected_pair_keys) and set(actual_pair_keys) == expected_pair_keys,
            "incomplete or repeated pairwise grid")
    checked_pairs = 0
    for summary in public["paired"]:
        left = [r for r in expanded if r["method"] == summary["left"] and r["product"] == summary["product"]]
        if summary["right"].startswith("ALWAYS_"):
            forced = summary["right"].removeprefix("ALWAYS_")
            checked(forced in ["OVER", "UNDER"], "invalid constant control")
            right = [dict(r, side=forced, status=grade(forced, r["appearance"], r["actual"], r["line"])) for r in left]
        else:
            right = [r for r in expanded if r["method"] == summary["right"] and r["product"] == summary["product"]]
        same(summary, comparison(left, right, np), allow_extra=True)
        checked_pairs += 1
    checked(checked_pairs == 10, "incomplete required pairwise grid")
    checked(all(s in representative for s in ["WIN", "LOSS", "UNKNOWN_PARTICIPATION"]), "required representative status absent")
    result = dict(id="PLAYER-CONTEXT-ACCEPTANCE-01-A-PEER-INDEPENDENT-REGRADE-v1", state="PASS_INDEPENDENT_RETAINED_REPLAY",
                  recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), verifier_sha256=digest(Path(__file__).read_bytes()),
                  public_result_sha256=args.result_sha256, private_scorecard_sha256=private["sha256"], private_scorecard_bytes=len(body),
                  unique_offers=len(retained), independent_product_grades=len(expanded), checked_summary_cells=checked_scores,
                  checked_constant_summary_cells=checked_scores * 2, checked_pairwise_cells=checked_pairs,
                  representative_cases=list(representative.values()), quote_timing_states=dict(Counter(dict(zip(EXPECTED_COLUMNS, r))["quote_timing_status"] for r in retained)),
                  full_coverage=dict(eligible=len(retained), games=len({r["game"] for r in expanded}), weeks=sorted({r["week"] for r in expanded})),
                  new_fits=0, new_inference=0, new_forecasts=0, private_writes=0, production_writes=0,
                  actual=dict(CPU_seconds=time.process_time() - cpu, wall_seconds=time.monotonic() - started,
                              RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
                  limitations=["No author common.status/summary invocation; independent Decimal/statistical and aggregate calculation.",
                               "Retained relational rows suffice for grade parity, not independent raw source label qualification or new inference.",
                               "Outside-WRTE exclusions and C-only no-offer counts require source universes not present in this relational package; not independently certified here.",
                               "Per-cell author uncertainty not reproduced; ten registered paired game-bootstrap intervals independently reproduced.",
                               "Quote timing and historical source availability remain unverified/reconstructed. No original issuance, venue settlement, probability/EV, Top Picks or primary admission claim."])
    output = OUT / "INDEPENDENT_C_POINT_A_REC_REPLAY_V1.json"
    with output.open("xb") as stream:
        stream.write(encoded(result)); stream.flush(); os.fsync(stream.fileno())
    signal.alarm(0)
    print(json.dumps({k: result[k] for k in ["state", "unique_offers", "independent_product_grades", "checked_summary_cells", "checked_pairwise_cells"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-sha256", required=True)
    try:
        run(parser.parse_args())
    except BaseException as error:
        # Deliberately exclude exception text/tracebacks and private evidence.
        signal.alarm(0)
        print(json.dumps(dict(state="INDEPENDENT_REVIEW_FAILED", error_type=type(error).__name__)))
        raise SystemExit(1) from None
