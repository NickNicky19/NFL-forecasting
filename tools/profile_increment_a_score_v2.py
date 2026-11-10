"""Saved-vector scoring of the named completed Leaf-CDF arms; no inference.

Reuse C's bound status/summary and A's previously reviewed source qualification.
Cached empirical laws are evaluated at exact retained lines. No model loading,
new forecasts, fitting, calibration, source acquisition or production writes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime
import gzip
import hashlib
import importlib
import importlib.util
import io
import json
import lzma
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
VERSION = "A::PROFILE-INCREMENT-TO-RELEASE-01-v2-saved-law-scoring-v1"
ARMS = ["RB_ONLY_LEAF_BASE", "R1_RB_ONLY_LEAF_SUPPORT", "R2_RB_ONLY_LEAF_PLAYER_OFFENSE", "R3_RB_ONLY_LEAF_DEFENSE"]
PRODUCTS = ["MEAN_P1", "MEDIAN_P1", "EXACT_LINE_P2"]
NEW = [a + "::" + p for a in ARMS for p in PRODUCTS]
OLD_NEW = ["D0_UNCHANGED_HGB_MAE", "D1_HGB_RAW_CONDITIONAL_PROFILE", "S0_UNCONDITIONAL_OWN_YPC_FIXED_N", "S1_CONDITIONAL_EFFICIENCY_FIXED_N"]
SAVED = ["SAVED_" + m + "__" + p for m, p in [("CATBOOST_MEDIUM", "median_objective_point"),
    ("EQUAL_CDF_CAT_HGB_POINT", "empirical_point_blend"), ("HGB_MAE_DIRECT", "mae_objective_point"),
    ("LEAF_CDF", "mean"), ("LEAF_CDF", "median"), ("RESPONSE_CDF", "mean"), ("RESPONSE_CDF", "median")]]
CONSTANTS = ["ALWAYS_OVER", "ALWAYS_UNDER"]
PREVALENCE = "EARLIER_RB_ROLE_EXACT_LINE_PREVALENCE_P2"
CANDIDATES = NEW + OLD_NEW + SAVED + CONSTANTS + [PREVALENCE]
COHORTS = ["ALL_ELIGIBLE", "STABLE_NEW_CORE", "DETAILED_PRIORITY", "WORKLOAD_TOP20", "PBP_OWN_SUPPORTED"]
KEY = ["season", "week", "game_id", "player_id"]
PHASE = "NOT_STARTED"


def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def local_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_ref(ref):
    body = Path(ref["path"]).read_bytes()
    check(len(body) == ref["bytes"] and sha(body) == ref["sha256"], "bound source bytes changed")
    return body


def key(row):
    return int(row["season"]), int(row["week"]), str(row["game_id"]), str(row["player_id"])


def law_probabilities(law, line):
    """Exact strict-Under/integer-push/strict-Over from the saved signed law."""
    check(law.get("kind") == "leaf_cdf", "retained law is not an empirical Leaf-CDF")
    support, weights = law["support"], law["weights"]
    check(len(support) == len(weights) and len(support) > 0, "law shape differs")
    check(all(type(x) in [int, float] and math.isfinite(x) and x == math.floor(x) for x in support), "signed law support invalid")
    check(all(a < b for a, b in zip(support, support[1:])), "law support not ordered distinct")
    check(all(type(w) in [int, float] and math.isfinite(w) and w >= 0 for w in weights)
          and abs(math.fsum(weights) - 1) <= 1e-12, "law empirical mass invalid")
    prior, b = law["prior"], law["prior_weight"]
    check(prior["support"] == "signed_integer" and 0 <= b <= 1, "signed prior contract invalid")
    center, q = prior["center"], prior["q"]
    check(type(center) is int and 0 < q < 1 and math.isfinite(line), "prior/line invalid")
    def cdf_at(x):
        n = math.floor(x)
        empirical = math.fsum(w for y, w in zip(support, weights) if y <= n)
        p = q ** (center-n) / (1+q) if n < center else 1-q ** (n-center+1)/(1+q)
        return (1-b)*empirical + b*p
    under = cdf_at(math.ceil(line)-1)
    over = 1-cdf_at(math.floor(line))
    push = cdf_at(line)-cdf_at(line-1) if line == math.floor(line) else 0.
    check(all(math.isfinite(p) and -1e-12 <= p <= 1+1e-12 for p in [under, push, over])
          and abs(under+push+over-1) <= 1e-10, "law probability normalization invalid")
    return dict(p_under=under, p_push=push, p_over=over, conditioning="CONDITIONAL_ON_PLAYED")


def probability_side(probabilities):
    if probabilities is None:
        return None
    return ("OVER" if probabilities["p_over"] > probabilities["p_under"] else
            "UNDER" if probabilities["p_under"] > probabilities["p_over"] else "ABSTAIN")


def probability_scores(rows):
    qualified = [r for r in rows if r.get("p_over") is not None and r["appearance"] == "PLAYED" and r["actual"] is not None]
    decisive = [r for r in qualified if r["actual"] != r["line"]]
    brier, multiclass, logloss, infinite = [], [], [], 0
    for r in qualified:
        actual, line = r["actual"], r["line"]
        p = r["p_over"]
        truth_over = float(actual > line)
        brier.append((p-truth_over)**2)
        truth = [float(actual < line), float(actual == line), float(actual > line)]
        probs = [r["p_under"], r["p_push"], r["p_over"]]
        multiclass.append(math.fsum((x-y)**2 for x, y in zip(probs, truth)))
        assigned = probs[truth.index(1.)]
        if assigned <= 0:
            infinite += 1
        else:
            logloss.append(-math.log(assigned))
    return dict(qualified_law_outcomes=len(qualified), decisive_law_outcomes=len(decisive),
        binary_Over_event_Brier=math.fsum(brier)/len(brier) if brier else None,
        binary_event_contract="I(actual>original_line), conditional_on_played; pushes are eventFalse; not conditional-decisive",
        three_class_Brier_sum=math.fsum(multiclass)/len(multiclass) if multiclass else None,
        three_class_log_loss=math.fsum(logloss)/len(logloss) if logloss and not infinite else None,
        infinite_log_loss_cases=infinite,
        finite_three_class_log_loss_mean=math.fsum(logloss)/len(logloss) if logloss else None,
        selected_probability_not_validated_confidence=True,
        state="SCORED_VALID_CACHED_LAWS" if qualified else "N/A_NO_QUALIFIED_CACHED_LAW_OUTCOME")


def numerical_product(candidate, rows, helper):
    if candidate in CONSTANTS or candidate.endswith("P2"):
        return dict(state="N/A_NO_NUMERICAL_POINT_PRODUCT", intended=len(rows), scored=0,
                    MAE=None, MSE=None, RMSE=None, bias=None)
    return helper.numerical(rows)


def paired_probability(left, right, helper, np):
    lookup = {r["opportunity_key"]: r for r in right}
    pairs = [(r, lookup[r["opportunity_key"]]) for r in left
             if r["opportunity_key"] in lookup and r.get("p_over") is not None
             and lookup[r["opportunity_key"]].get("p_over") is not None
             and r["appearance"] == "PLAYED" and r["actual"] is not None]
    games, weeks = defaultdict(lambda: [0.,0.]), defaultdict(lambda: [0.,0.])
    changes = []
    for a, b in pairs:
        check(a["actual"] == b["actual"] and a["line"] == b["line"] and b["appearance"] == "PLAYED", "paired probability event/outcome differs")
        target = float(a["actual"] > a["line"])
        difference = (a["p_over"]-target)**2-(b["p_over"]-target)**2
        changes.append(difference)
        games[a["game_id"]][0] += difference; games[a["game_id"]][1] += 1
        weeks[(a["season"],a["week"])][0] += difference; weeks[(a["season"],a["week"])][1] += 1
    return dict(common_probability_events=len(pairs), binary_Over_event_Brier_change=math.fsum(changes)/len(changes) if changes else None,
        game_interval95=helper.block_interval(games,np), week_interval95=helper.block_interval(weeks,np),
        event_conditioning="conditional_on_played; strictOver event; pushes eventFalse")


def make_pairs():
    pairs = []
    for product in PRODUCTS:
        c = [a + "::" + product for a in ARMS]
        pairs.extend([[c[1], c[0]], [c[2], c[1]], [c[2], c[0]], [c[3], c[2]], [c[3], c[0]]])
        for candidate in c:
            # Point and probability directions may be compared on the same
            # statistical outcomes; probability quality is never imputed to a point.
            reference_product = "mean" if product in ["MEAN_P1", "EXACT_LINE_P2"] else "median"
            pairs.extend([[candidate, "SAVED_LEAF_CDF__"+reference_product],
                          [candidate, "SAVED_RESPONSE_CDF__"+reference_product],
                          [candidate, "ALWAYS_OVER"], [candidate, "ALWAYS_UNDER"], [candidate, PREVALENCE]])
            if product in ["MEAN_P1", "EXACT_LINE_P2"]:
                pairs.extend([[candidate, "SAVED_LEAF_CDF__median"],
                              [candidate, "SAVED_RESPONSE_CDF__median"]])
    for candidate in [ARMS[-1]+"::MEAN_P1", ARMS[-1]+"::MEDIAN_P1"]:
        pairs.extend([[candidate, old] for old in OLD_NEW])
    return pairs


PAIRS = make_pairs()


def partial_parity(previous, summaries, pairs, source_hashes, core_board, core_broad, completed3_board, completed3_broad):
    """Compare serialized old cells; no prediction, grading or mask selection."""
    check(previous.get("state") == "FROZEN_NAMED_THREE_ARMS_SCORING_COMPLETE_DEFENSE_PENDING"
          and previous.get("completed_arms") == ARMS[:3] and previous.get("pending_arms") == ARMS[3:],
          "bound prior partial result is not the named three-arm panel")
    check(previous["source_sha256"] == source_hashes, "prior partial label/source roster differs")
    check(previous["common_new_core_mask_sha256"] == sha(enc(sorted(completed3_board))),
          "unchanged completed-three-arm core differs from retained partial commitment")
    same_board, same_broad = core_board == completed3_board, core_broad == completed3_broad
    def sk(r):
        return tuple(str(r.get(k)) for k in ["period","cohort","candidate_id","population","source_panel","week_view"])
    def pk(r):
        return tuple(str(r.get(k)) for k in ["period","cohort","source_panel","left","right"])
    sm, pm = {sk(r): r for r in summaries}, {pk(r): r for r in pairs}
    compared_s, compared_p, skipped_s, skipped_p, mismatches = 0, 0, 0, 0, []
    for r in previous["summaries"]:
        if r["candidate_id"].startswith(ARMS[3]+"::"):
            continue
        if r["cohort"] == "STABLE_NEW_CORE" and not (same_broad if r["population"] == "BROAD_QUERIES" else same_board):
            skipped_s += 1
            continue
        compared_s += 1
        if sk(r) not in sm or enc(r) != enc(sm[sk(r)]):
            mismatches.append(["SUMMARY",list(sk(r))])
    for r in previous["paired"]:
        if any(r[k].startswith(ARMS[3]+"::") for k in ["left","right"]):
            continue
        if r["cohort"] == "STABLE_NEW_CORE" and not same_board:
            skipped_p += 1
            continue
        compared_p += 1
        if pk(r) not in pm or enc(r) != enc(pm[pk(r)]):
            mismatches.append(["PAIR",list(pk(r))])
    return dict(state="PASS_UNCHANGED_COMPARABLE_OLD_CELLS" if not mismatches else "DIFFERENCE_REQUIRES_OWNER_REVIEW",
        prior_summary_cells=len(previous["summaries"]), prior_paired_cells=len(previous["paired"]),
        unchanged_summary_cells=compared_s-sum(x[0]=="SUMMARY" for x in mismatches),
        unchanged_paired_cells=compared_p-sum(x[0]=="PAIR" for x in mismatches),
        compared_summary_cells=compared_s, compared_paired_cells=compared_p,
        completed3_vs4_board_mask_same=same_board, completed3_vs4_broad_mask_same=same_broad,
        completed3_board_mask_sha256=sha(enc(sorted(completed3_board))),
        completed4_board_mask_sha256=sha(enc(sorted(core_board))),
        completed3_broad_mask_sha256=sha(enc(sorted(completed3_broad))),
        completed4_broad_mask_sha256=sha(enc(sorted(core_broad))),
        changed_core_cells_kept_separate=dict(summary=skipped_s,paired=skipped_p),
        mismatch_count=len(mismatches), mismatch_keys=mismatches[:20],
        excluded_newly_available_arm=ARMS[3], original_partial_preserved=True,
        scope="New R3 cells are not old-cell parity; changed-core scopes, if any, remain separately identified. No old prediction/grade rewritten.")


def player_diagnostics(board, broad, helper, protocol_sha256):
    """Descriptive aggregation of existing canonical statuses; no new grader."""
    players = sorted({r["player_id"] for rows in broad.values() for r in rows}
                     | {r["player_id"] for rows in board.values() for r in rows})
    panels = [
        ("W1_W7_MIXED_THRESHOLDS", False, lambda r: r["week"] in range(1,8)),
        ("ANNUAL_W1_W5", False, lambda r: r["week"] in range(1,6) and r["source_panel"] == "ANNUAL_NAMED_NJ"),
        ("W8_REFERENCE_ONLY", False, lambda r: r["week"] == 8),
        ("BROAD_NUMERICAL_W1_W7", True, lambda r: r["week"] in range(1,8)),
        ("BROAD_NUMERICAL_W8", True, lambda r: r["week"] == 8),
    ]
    side_columns = ["selected","wins","losses","decided","rate"]
    num_columns = ["scored","MAE","MSE","bias"]
    columns = ["panel","candidate_id","player_id","eligible","unique_games","appearance_counts",
               "canonical_status_counts","own_sides_OVER_UNDER_COMBINED","numerical","numerical_state",
               "fallback_counts","unavailability_reasons"]
    protected_rows, aggregate, paired = [], [], []
    def sides(rows):
        result = {}
        for side in ["OVER","UNDER","COMBINED"]:
            rr = [r for r in rows if r.get("selected_side") in ["OVER","UNDER"]] if side == "COMBINED" else [r for r in rows if r.get("selected_side") == side]
            w, l = sum(r["status"] == "WIN" for r in rr), sum(r["status"] == "LOSS" for r in rr)
            result[side] = dict(selected=len(rr),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l) if w+l else None)
        return result
    def support_bin(n):
        return "0" if n == 0 else "1" if n == 1 else "2" if n == 2 else "3-4" if n <= 4 else "5-7" if n <= 7 else "8+"
    for panel, is_broad, predicate in panels:
        grouped, totals = {}, {}
        for candidate in CANDIDATES:
            rows = [r for r in (broad if is_broad else board)[candidate] if predicate(r)]
            byplayer = defaultdict(list)
            for r in rows:
                byplayer[r["player_id"]].append(r)
            grouped[candidate] = byplayer
            side_views, numeric_views, supports = [], [], Counter()
            for player in players:
                rr = byplayer[player]
                ss = None if is_broad else sides(rr)
                nn = numerical_product(candidate,rr,helper)
                support = nn["scored"] if is_broad else ss["COMBINED"]["decided"]
                supports[support_bin(support)] += 1
                numeric_views.append(nn)
                if ss is not None:
                    side_views.append(ss)
                protected_rows.append([panel,candidate,player,len(rr),len({r["game_id"] for r in rr}),
                    dict(Counter(r["appearance"] for r in rr)), None if is_broad else dict(Counter(r["status"] for r in rr)),
                    None if ss is None else [[ss[s][k] for k in side_columns] for s in ["OVER","UNDER","COMBINED"]],
                    [nn.get(k) for k in num_columns],nn.get("state","POINT_PRODUCT"),
                    dict(Counter(r["fallback_state"] for r in rr)),
                    dict(Counter(r["unavailability_reason"] for r in rr if r["unavailability_reason"]))])
            equal_side = None
            if not is_broad:
                equal_side = {}
                for side in ["OVER","UNDER","COMBINED"]:
                    rates = [s[side]["rate"] for s in side_views if s[side]["decided"]]
                    equal_side[side] = dict(players_with_decisions=len(rates),mean_player_hit_rate=math.fsum(rates)/len(rates) if rates else None)
            equal_numeric = {}
            for metric in ["MAE","MSE","bias"]:
                values = [n[metric] for n in numeric_views if n.get(metric) is not None]
                equal_numeric[metric] = math.fsum(values)/len(values) if values else None
            public = dict(panel=panel,candidate_id=candidate,eligible_players_in_global_declared_universe=len(players),
                players_with_panel_rows=sum(bool(byplayer[p]) for p in players),
                players_with_numerical_scores=sum(n["scored"] > 0 for n in numeric_views),
                support_kind="numerical_scored" if is_broad else "own_combined_decided",support_distribution=dict(supports),
                equal_player_sides=equal_side,opportunity_weighted_sides=None if is_broad else sides(rows),
                equal_player_numerical=equal_numeric,opportunity_weighted_numerical=numerical_product(candidate,rows,helper))
            aggregate.append(public);totals[candidate] = public
        for left, right in PAIRS:
            direction_counts = Counter();numeric_counts = Counter()
            direction_n = direction_delta = numeric_n = 0
            numeric_delta, equal_numeric_delta, equal_direction_delta = [], [], []
            for player in players:
                aa = grouped[left][player];bb = {r["opportunity_key"]: r for r in grouped[right][player]}
                common = [(a,bb[a["opportunity_key"]]) for a in aa if a["opportunity_key"] in bb]
                dd = [] if is_broad else [(a,b) for a,b in common if a["status"] in ["WIN","LOSS"] and b["status"] in ["WIN","LOSS"]]
                if dd:
                    delta = sum(int(a["status"]=="WIN")-int(b["status"]=="WIN") for a,b in dd)
                    direction_counts["left_more_correct" if delta>0 else "right_more_correct" if delta<0 else "tied"] += 1
                    direction_n += len(dd);direction_delta += delta;equal_direction_delta.append(delta/len(dd))
                else:
                    direction_counts["no_common_decisions"] += 1
                ee = []
                for a,b in common:
                    if helper.finite(a.get("point")) and helper.finite(b.get("point")) and a.get("actual") is not None and b.get("actual") is not None:
                        check(a["actual"] == b["actual"], "per-player paired numerical labels differ")
                        ee.append(abs(a["point"]-a["actual"])-abs(b["point"]-b["actual"]))
                if ee:
                    difference = math.fsum(ee)/len(ee)
                    numeric_counts["left_lower_MAE" if difference<0 else "right_lower_MAE" if difference>0 else "tied"] += 1
                    numeric_n += len(ee);numeric_delta.extend(ee);equal_numeric_delta.append(difference)
                else:
                    numeric_counts["no_common_numeric_scores"] += 1
            paired.append(dict(panel=panel,left=left,right=right,global_players=len(players),
                direction_player_counts=dict(direction_counts),common_decided_opportunities=direction_n,
                opportunity_weighted_accuracy_change=direction_delta/direction_n if direction_n else None,
                equal_player_accuracy_change=math.fsum(equal_direction_delta)/len(equal_direction_delta) if equal_direction_delta else None,
                numerical_player_counts=dict(numeric_counts),common_numerical_opportunities=numeric_n,
                opportunity_weighted_MAE_change=math.fsum(numeric_delta)/numeric_n if numeric_n else None,
                equal_player_MAE_change=math.fsum(equal_numeric_delta)/len(equal_numeric_delta) if equal_numeric_delta else None))
    private = dict(schema="A_FULL_FOUR_PER_PLAYER_DESCRIPTIVE_V1",category="rush_yd",role_scope="RB",season=2026,
        protocol_sha256=protocol_sha256,
        columns=columns,side_columns=side_columns,numerical_columns=num_columns,rows=protected_rows,
        player_universe="All canonical players in the already-bound broad/threshold query panels, including zero-support, unknown and unavailable records; source-row-conditioned historical universe remains disclosed.",
        empty_pool="Zero counts with rate null; broad numerical panels have no offered-side record.",
        no_router_or_player_algorithm_selection=True)
    public = dict(state="COMPUTED_FROM_EXISTING_CANONICAL_ROWS",category="rush_yd",role_scope="RB",season=2026,
        panel_definitions=[p[0] for p in panels],
        global_player_count=len(players),protected_record_count=len(protected_rows),summary=aggregate,paired_player_counts=paired,
        weights="Equal-player means use players with scored outcomes; all n0 players remain in support counts/private card. Opportunity-weighted side rates sum wins/decided. No side-percent averaging.",
        inference_limits="Descriptive exposed/repeated-player panels; no new bootstrap, per-player winner/router, scientific gate, NFL observation or product qualification.",
        public_player_ids_or_rows=False)
    return gzip.compress(enc(private),mtime=0),public


def run(args):
    global PHASE
    started, cpu = time.monotonic(), time.process_time()
    raw = args.protocol.read_bytes()
    check(sha(raw) == args.protocol_sha256, "score protocol digest differs")
    plan = json.loads(raw)
    check(plan.get("version") == VERSION and plan.get("state") == "ROOT_REGISTERED_SCORING_GO"
          and plan.get("registered_by") == "/root", "root post-freeze scoring GO required")
    check(plan.get("candidate_ids") == CANDIDATES and plan.get("paired_candidate_ids") == PAIRS
          and plan.get("cohorts") == COHORTS, "finite comparison roster/masks differ")
    completed_arms = plan.get("completed_arms")
    check(completed_arms in [ARMS[:3], ARMS], "exact named three-arm or four-arm freeze required")
    pending_arms = ARMS[len(completed_arms):]
    completed_products = [arm+"::"+product for arm in completed_arms for product in PRODUCTS]
    check(plan.get("pending_arms") == pending_arms and plan.get("stable_core_candidate_ids") == completed_products,
          "completed-product stable core and pending-arm bindings differ")
    allocation_kind = plan.get("allocation_kind", "PRIMARY")
    check(allocation_kind in ["PRIMARY", "DEF_REMAINDER"], "unknown native scoring allocation")
    if allocation_kind == "DEF_REMAINDER":
        check(completed_arms == ARMS and not pending_arms, "defense remainder scoring requires the named full freeze")
    budget = plan["resources"]
    expected_budget = dict(CPU_seconds=400, wall_seconds=900, RSS_bytes=3*1024**3, private_view_max_bytes=131072)
    if plan.get("per_player_diagnostics", False):
        expected_budget["per_player_scorecard_max_bytes"] = 524288
    check(budget == expected_budget, "fixed scoring budget differs")
    for name, expected in plan["code_sha256"].items():
        check(sha((ROOT/name).read_bytes()) == expected, "score executing code changed: "+name)
    for variable in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[variable] = "1"
    resource.setrlimit(resource.RLIMIT_CPU, (400, 400))
    resource.setrlimit(resource.RLIMIT_AS, (budget["RSS_bytes"],)*2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("bounded frozen score wall")))
    signal.alarm(900)
    def offline(event, _args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("offline cached-law score")
    sys.addaudithook(offline)
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1); pa.set_io_thread_count(1); pa.set_memory_pool(pa.system_memory_pool())
    old = local_module("tools.player_context_completion_efficiency_score_v1", "tools/player_context_completion_efficiency_score_v1.py")
    guard_path = ("nfl_lab/profile_increment_a_def_remainder_storage_v1.py" if allocation_kind == "DEF_REMAINDER"
                  else "nfl_lab/profile_increment_a_storage_v2.py")
    check(guard_path in plan["code_sha256"], "selected native storage implementation must be hash bound")
    guard = local_module("nfl_lab.profile_increment_a_active_scoring_storage", guard_path)
    base = local_module("tools.abc_a_dynamic_carry_wave_v1", "tools/abc_a_dynamic_carry_wave_v1.py")
    for name, expected in old.C_PINS.items():
        check(sha((args.c_code_cache/name).read_bytes()) == expected, "pinned canonical C source differs")
    sys.path.insert(0, str(args.c_code_cache))
    common = importlib.import_module("abc_championship_v2")
    PHASE = "NATIVE_FROZEN_READ"
    store = guard.ProfileIncrementStore(ROOT, plan["allocation"]["path"], plan["allocation"]["sha256"], root_go=guard.GO)
    legacy_version = guard.OLD if allocation_kind == "DEF_REMAINDER" else guard.OLD_VERSION
    check(legacy_version == "PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1", "legacy native source namespace differs")
    def native_read(ref):
        if allocation_kind == "DEF_REMAINDER":
            check(ref.get("namespace") in ["PRIMARY", "DEF_REMAINDER"], "exact managed artifact namespace required")
            body = store.read(ref["id"], ref["sha256"], namespace=ref["namespace"])
        else:
            check(ref.get("namespace") in [None, "PRIMARY"], "single primary store cannot read a sibling artifact")
            body = store.read(ref["id"], ref["sha256"])
        check(len(body) == ref["bytes"], "managed member exact size differs")
        return body
    receipt_raw = read_ref(plan["execution_receipt"])
    receipt = json.loads(receipt_raw)
    expected_state = "FROZEN_NAMED_THREE_ARMS_DEFENSE_PENDING" if pending_arms else "FROZEN_FORECASTS_COMPLETE_UNSCORED"
    check(receipt["state"] == expected_state and receipt["version"] == "PROFILE-INCREMENT-TO-RELEASE-01-A-v2", "named completed freeze required")
    check(receipt.get("completed_arms", ARMS) == completed_arms and receipt.get("pending_arms", []) == pending_arms,
          "receipt completed/pending arms differ from the bound scoring protocol")
    if allocation_kind == "DEF_REMAINDER":
        check(receipt.get("supplement_version") == guard.VERSION, "full receipt supplement binding differs")
    check(receipt["forecasts"]["sha256"] == plan["frozen_forecasts_sha256"], "new frozen forecast digest differs")
    frozen = native_read(receipt["forecasts"])
    decoded = json.loads(gzip.decompress(frozen))
    native_bodies = {}
    if receipt.get("forecasts_format") == "IMMUTABLE_ORDERED_PART_MANIFEST_V1":
        check(decoded.get("format") == receipt["forecasts_format"] and decoded.get("arm_order") == completed_arms
              and len(decoded.get("parts", [])) == len(completed_arms), "ordered completed forecast-part format differs")
        if allocation_kind == "DEF_REMAINDER":
            check(decoded.get("namespace_contract") == "PRIMARY_AND_DEF_REMAINDER_NATIVE_V1"
                  and [p.get("namespace") for p in decoded["parts"]] == ["PRIMARY"]*3+["DEF_REMAINDER"],
                  "full ordered source namespace contract differs")
            extra = [next(r for r in receipt["artifacts"] if r["id"] == name) for name in
                     ["BASIC_PROFILES_AND_COHORTS_2026.json.gz", "QUERY_PROFILE_INPUTS_2026.parquet"]]
            # One native transaction still authenticates every exact member and
            # every namespace; it avoids repeating whole-store admission scans.
            native_bodies = store.read_many(decoded["parts"]+extra)
        newrows = []
        for arm, part in zip(completed_arms, decoded["parts"]):
            check(part["arm"] == arm, "forecast-part arm order differs")
            part_body = native_bodies[part["id"]] if part["id"] in native_bodies else native_read(part)
            check(len(part_body) == part["bytes"], "forecast-part exact bytes differ")
            part_rows = json.loads(gzip.decompress(part_body))
            check(len(part_rows) == part["rows"] and all(r["arm"] == arm for r in part_rows), "forecast-part row binding differs")
            newrows.extend(part_rows)
        check(len(newrows) == decoded["rows"] and sha(enc(newrows)) == decoded["logical_combined_sha256"],
              "decoded ordered forecast logical commitment differs")
    else:
        newrows = decoded
    check(len(newrows) == receipt["forecast_rows"], "new frozen row count differs")
    preserved_three_arm_logical = sha(enc([r for r in newrows if r["arm"] in ARMS[:3]]))
    if allocation_kind == "DEF_REMAINDER":
        check(preserved_three_arm_logical == plan["prior_three_arm_logical_sha256"],
              "full manifest changed an already frozen completed-three-arm forecast")
    newmap = {}
    for row in newrows:
        check(row["arm"] in completed_arms and row["target"] == "rush_yd" and row["position"] == "RB", "new frozen recipe/role differs")
        k = row["arm"], key(row)
        check(k not in newmap, "ambiguous new frozen player-game")
        newmap[k] = row
    old_raw = read_ref(plan["old_execution_receipt"])
    old_receipt = json.loads(old_raw)
    old_artifacts = {r["id"]: r for r in old_receipt["artifacts"]}
    old_root = store.prior.forward_root / "research" / legacy_version
    def old_read(ref):
        path = old_root/ref["id"]
        store.prior.validate_reference(path, ref["sha256"])
        body = path.read_bytes()
        check(len(body) == ref["bytes"], "old native artifact size differs")
        return body
    old_frozen = json.loads(gzip.decompress(old_read(old_receipt["forecasts"])))
    oldmap = {}
    for row in old_frozen:
        if row["arm"] not in OLD_NEW+SAVED or row["season"] != 2026:
            continue
        k = row["arm"], key(row)
        check(k not in oldmap, "ambiguous old frozen player-game")
        oldmap[k] = row
    query_ref = old_artifacts["QUERY_IDENTITIES_2026.json.gz"]
    queries = {key(row): row for row in json.loads(gzip.decompress(old_read(query_ref)))}
    _, c, g, _ = base.sources()
    refs = {name: dict(g[selector]) for name, selector in [("A_offers", "offers"), ("A_labels", "qualified_labels"), ("A_saved", "frozen_bundle")]}
    for name, ref in refs.items():
        check(ref["sha256"] == old.PINS[name], "bound original A source selector differs")
    PHASE = "QUALIFIED_LABEL_AND_OFFER_READ"
    with zipfile.ZipFile(io.BytesIO(read_ref(refs["A_offers"]))) as archive:
        offers = pd.read_parquet(io.BytesIO(archive.read(refs["A_offers"]["member"])))
    with zipfile.ZipFile(io.BytesIO(read_ref(refs["A_labels"]))) as archive:
        labels = pd.read_parquet(io.BytesIO(archive.read(refs["A_labels"]["member"])))
    with zipfile.ZipFile(io.BytesIO(read_ref(refs["A_saved"]))) as archive:
        saved_body = archive.read("FORECASTS.parquet")
        check(sha(saved_body) == old.PINS["A_saved_member"], "original saved-control member changed")
        saved_frame = pd.read_parquet(io.BytesIO(saved_body))
    for row in saved_frame.loc[saved_frame.target.eq("rush_yd") & saved_frame.position.eq("RB")].to_dict("records"):
        candidate = "SAVED_"+row["method"]+"__"+row["product"]
        targets = [(candidate,key(row))]
        if candidate == "SAVED_HGB_MAE_DIRECT__mae_objective_point":
            targets.append((OLD_NEW[0],key(row)))
        for target in targets:
            if target in oldmap and "fallback" in row:
                oldmap[target]["fallback"] = None if pd.isna(row["fallback"]) else row["fallback"]
    labelmap = {}
    selected_labels = labels.loc[labels.target.eq("rush_yd") & labels.season.eq(2026) & labels.week.between(1,7)]
    check(not selected_labels.duplicated(KEY).any(), "qualified label identity ambiguous")
    for row in selected_labels.to_dict("records"):
        state = str(row.get("participation_state", "unknown")).lower()
        appearance = "PENDING" if row.get("outcome_state") == "pending" else "DNP" if state == "dnp" else "PLAYED" if state == "played" else "UNKNOWN"
        supported = appearance == "PLAYED" and old.finite(row.get("actual")) and row.get("label_reason") in ["EXPLICIT_REPORTED_ZERO", "EXPLICIT_REPORTED_VALUE"] and bool(row.get("participation_evidence"))
        labelmap[key(row)] = dict(actual=float(row["actual"]) if supported else None, appearance=appearance, presence=row.get("label_reason"))
    # Existing reviewed W8 source restoration is read-only. Authenticate its
    # immutable old artifacts through the existing native owner, not an old
    # CompletionStore constructor whose unamended whole-prior delta differs.
    for path, expected in [(store.outer.forward_root/"research/week8-original-grade-v2-batch-20261102/SOURCES.zip", old.PINS["W8_sources"]),
        (store.outer.forward_root/"research/week8-original-grade-v2-batch-20261102/A_LOCAL_WEEK8_REGRADING_V2_20261103.zip", old.PINS["W8_graded"]),
        (store.outer.forward_root/"research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_WEEK8_MEASUREMENT_OVERLAY_V1.json.gz", old.PINS["W8_overlay"])]:
        store.outer.validate_reference(path, expected)
    w8queries, w8canonical, w8offers, w8meta = old.restore_w8(store, refs, pd)
    for k, row in w8canonical.items():
        labelmap[k] = row["_label"]
    for row in w8queries:
        if row["identity_reason"] is not None:
            queries[key(row)] = row
    cohort_ref = next(r for r in receipt["artifacts"] if r["id"] == "BASIC_PROFILES_AND_COHORTS_2026.json.gz")
    cohort_body = native_bodies[cohort_ref["id"]] if cohort_ref["id"] in native_bodies else native_read(cohort_ref)
    cohort_rows = json.loads(gzip.decompress(cohort_body))
    cohorts = {key(r): r for r in cohort_rows}
    input_ref = next(r for r in receipt["artifacts"] if r["id"] == "QUERY_PROFILE_INPUTS_2026.parquet")
    input_body = native_bodies[input_ref["id"]] if input_ref["id"] in native_bodies else native_read(input_ref)
    qfeatures = pd.read_parquet(io.BytesIO(input_body), columns=KEY+["f_pce_own_supported"])
    support = {key(r): bool(r["f_pce_own_supported"] > 0) for r in qfeatures.to_dict("records")}
    histories, seen_history = [], set()
    for i, ref in enumerate(c["history_sources"]):
        refs["history_"+str(i)] = dict(ref)
        h = pd.read_parquet(io.BytesIO(read_ref(ref)))
        check(h.outcome_available_utc.notna().all(), "explicit unknown historical availability cannot be filled")
        eligible = h.position.eq("RB") & h.participation_state.eq("played") & h.stats_observed.eq(True)
        hh = h.loc[eligible].copy()
        hh["_available"] = hh.outcome_available_utc.map(lambda x: pd.Timestamp(x))
        check(all(x.tzinfo is not None for x in hh._available), "earlier prevalence clocks naive")
        for row in hh.to_dict("records"):
            check(key(row) not in seen_history, "earlier prevalence player-game version ambiguous")
            seen_history.add(key(row))
            if old.finite(row.get("rush_yd")):
                histories.append((row["_available"], str(row["game_id"]), float(row["rush_yd"])))
    source_hashes = {name: ref["sha256"] for name, ref in refs.items()}
    check(source_hashes == plan["source_sha256"], "exact complete scoring-source roster differs")
    offered = []
    aoffers = offers.loc[offers.target.eq("rush_yd") & offers.position.eq("RB") & offers.season.eq(2026) & offers.week.between(1,7)]
    check(not aoffers.duplicated(["opportunity_key"]).any(), "retained primary offer identity ambiguous")
    for row in aoffers.to_dict("records"):
        source = str(row["source_stream"])
        offered.append(dict(query=row, line=float(row["line"]), opportunity=str(row["opportunity_key"]),
            label=labelmap.get(key(row), dict(actual=None, appearance="UNKNOWN", presence="NO_QUALIFIED_LABEL")), source=source,
            tier="ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED" if source in plan["actual_recorded_source_panels"] else "SOURCE_OFFER_STATUS_UNVERIFIED_DIAGNOSTIC"))
    offered.extend(w8offers)
    unknown = dict(actual=None, appearance="UNKNOWN", presence="NO_QUALIFIED_LABEL")
    PHASE = "CACHED_LAW_EXACT_LINE_AND_CANONICAL_STATUS"
    board = {candidate: [] for candidate in CANDIDATES}
    broad = {candidate: [] for candidate in CANDIDATES}
    memberships = []
    def point_and_law(candidate, query, line=None):
        k = key(query)
        if candidate in NEW and candidate.split("::", 1)[0] in pending_arms:
            return None, None, "RESOURCE_PENDING", "UNAVAILABLE_FORECAST"
        if query.get("identity_reason") is not None:
            return None, None, query["identity_reason"], "UNAVAILABLE_FORECAST"
        if candidate in CONSTANTS:
            return None, None, None, "CONSTANT_NOT_NUMERICAL"
        if candidate == PREVALENCE:
            if line is None:
                return None, None, "PREVALENCE_HAS_NO_NUMERICAL_POINT", "NOT_NUMERICAL"
            cut = old.clock(query.get("cutoff_utc"), pd)
            previous = [y for available, event, y in histories if cut is not None and available < cut and event != query["game_id"]]
            if not previous:
                return None, None, "NO_ELIGIBLE_EARLIER_ROLE_LABELS", "UNAVAILABLE_REFERENCE"
            n = len(previous)
            if line == math.floor(line):
                probs = dict(p_under=(sum(y<line for y in previous)+1)/(n+3), p_push=(sum(y==line for y in previous)+1)/(n+3), p_over=(sum(y>line for y in previous)+1)/(n+3))
            else:
                probs = dict(p_under=(sum(y<line for y in previous)+1)/(n+2), p_push=0., p_over=(sum(y>line for y in previous)+1)/(n+2))
            return None, probs, None, "EARLIER_ROLE_PREVALENCE_NOT_LEARNED_MODEL"
        if candidate in NEW:
            arm, product = candidate.split("::")
            row = newmap.get((arm, k))
            why = old.compatible(row, query, pd)
            if why is not None:
                return None, None, why, "UNAVAILABLE_FORECAST"
            point = row["mean"] if product == "MEAN_P1" else row["median"] if product == "MEDIAN_P1" else None
            probs = law_probabilities(row["law"], line) if line is not None else None
            return point, probs, None, old.fallback(row)
        row = oldmap.get((candidate, k))
        why = old.compatible(row, query, pd)
        return (row.get("point") if why is None else None), None, why, old.fallback(row) if row else "UNAVAILABLE_FORECAST"
    for k, query in queries.items():
        label = labelmap.get(k, query.get("_label", unknown))
        for candidate in CANDIDATES:
            point, _, why, fb = point_and_law(candidate, query)
            broad[candidate].append(dict(season=k[0], week=k[1], game_id=k[2], player_id=k[3], opportunity_key=sha(enc(list(k))), point=point,
                actual=label["actual"], appearance=label["appearance"], unavailability_reason=why, fallback_state=fb,
                cohorts=["ALL_ELIGIBLE"] + (["DETAILED_PRIORITY"] if cohorts.get(k, {}).get("detailed_priority") else [])
                    + (["WORKLOAD_TOP20"] if cohorts.get(k, {}).get("top20_workload") else []) + (["PBP_OWN_SUPPORTED"] if support.get(k) else [])))
    for offer in offered:
        query, line, label = offer["query"], offer["line"], offer["label"]
        k = key(query)
        group = ["ALL_ELIGIBLE"] + (["DETAILED_PRIORITY"] if cohorts.get(k, {}).get("detailed_priority") else []) + (["WORKLOAD_TOP20"] if cohorts.get(k, {}).get("top20_workload") else []) + (["PBP_OWN_SUPPORTED"] if support.get(k) else [])
        for candidate in CANDIDATES:
            point, probs, why, fb = point_and_law(candidate, query, line)
            selected = candidate.removeprefix("ALWAYS_") if candidate in CONSTANTS else probability_side(probs) if candidate.endswith("P2") else old.point_side(point, line)
            initial = "UNAVAILABLE_FORECAST" if selected is None else "ABSTAIN" if selected == "ABSTAIN" else "DNP" if label["appearance"] == "DNP" else "PENDING" if label["appearance"] == "PENDING" else "UNKNOWN_PARTICIPATION" if label["appearance"] != "PLAYED" else "MISSING_ACTUAL" if label["actual"] is None else "READY_FOR_CANONICAL_STATUS"
            row = dict(season=k[0], week=k[1], game_id=k[2], player_id=k[3], candidate_id=candidate,
                category="rush_yd", point=point, actual=label["actual"], appearance=label["appearance"], selected_side=selected,
                line=line, comparator="STRICT_OVER_UNDER", status=initial, opportunity_key=offer["opportunity"], source_panel=offer["source"],
                evidence_tier=offer["tier"], fallback_state=fb, unavailability_reason=why, cohorts=group,
                p_under=probs["p_under"] if probs else None, p_push=probs["p_push"] if probs else None, p_over=probs["p_over"] if probs else None)
            row["status"] = common.status(row)
            board[candidate].append(row)
            memberships.append([candidate, offer["opportunity"], point, row["p_under"], row["p_push"], row["p_over"], selected, row["status"], why, fb])
    core_board = set.intersection(*[{r["opportunity_key"] for r in board[c] if r["selected_side"] is not None} for c in completed_products])
    core_broad = set.intersection(*[{r["opportunity_key"] for r in broad[c] if old.finite(r["point"])} for c in completed_products if not c.endswith("P2")])
    first3_products = [a+"::"+p for a in ARMS[:3] for p in PRODUCTS]
    completed3_board = set.intersection(*[{r["opportunity_key"] for r in board[c] if r["selected_side"] is not None} for c in first3_products])
    completed3_broad = set.intersection(*[{r["opportunity_key"] for r in broad[c] if old.finite(r["point"])} for c in first3_products if not c.endswith("P2")])
    for rows in board.values():
        for row in rows:
            if row["opportunity_key"] in core_board:
                row["cohorts"].append("STABLE_NEW_CORE")
    for rows in broad.values():
        for row in rows:
            if row["opportunity_key"] in core_broad:
                row["cohorts"].append("STABLE_NEW_CORE")
    summaries, pairs = [], []
    periods = [("W1_W7", list(range(1,8))), ("W8_REFERENCE_ONLY", [8]), ("W1_W8_PARTIAL_ACTUAL", list(range(1,9)))]
    for period, weeks in periods:
        for cohort in COHORTS:
            for candidate in CANDIDATES:
                candidate_state = "RESOURCE_PENDING" if candidate in NEW and candidate.split("::", 1)[0] in pending_arms else "FROZEN_OR_CONTROL"
                numer = [r for r in broad[candidate] if r["week"] in weeks and cohort in r["cohorts"]]
                summaries.append(dict(period=period, cohort=cohort, candidate_id=candidate, execution_state=candidate_state,
                    population="BROAD_QUERIES", numerical=numerical_product(candidate,numer,old)))
                br = [r for r in board[candidate] if r["week"] in weeks and cohort in r["cohorts"]]
                for panel in ["ALL"] + sorted({r["source_panel"] for r in br}):
                    for week in ["ALL"] + weeks:
                        rr = [r for r in br if (panel == "ALL" or r["source_panel"] == panel) and (week == "ALL" or r["week"] == week)]
                        actual_weeks = sorted({r["week"] for r in rr if r["status"] in ["WIN", "LOSS", "PUSH"] and r["evidence_tier"] == "ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED"})
                        summaries.append(dict(period=period, cohort=cohort, candidate_id=candidate, source_panel=panel, week_view=week,
                            execution_state=candidate_state,
                            population="RETAINED_THRESHOLD_BOARD", **common.summary(rr), numerical=numerical_product(candidate,rr,old), probability=probability_scores(rr),
                            actual_recorded_line_scored_weeks=actual_weeks, five_actual_week_duration_floor=len(actual_weeks)>=5,
                            diagnostic_scored_weeks=sorted({r["week"] for r in rr if r["status"] in ["WIN", "LOSS", "PUSH"]}),
                            evidence_tiers=dict(Counter(r["evidence_tier"] for r in rr)), admission="DURATION_ONLY_NOT_PRIMARY_ADMISSION"))
            for left, right in PAIRS:
                aa = [r for r in board[left] if r["week"] in weeks and cohort in r["cohorts"]]
                bb = [r for r in board[right] if r["week"] in weeks and cohort in r["cohorts"]]
                for panel in ["ALL"] + sorted({r["source_panel"] for r in aa+bb}):
                    a = [r for r in aa if panel == "ALL" or r["source_panel"] == panel]
                    b = [r for r in bb if panel == "ALL" or r["source_panel"] == panel]
                    pairs.append(dict(period=period, cohort=cohort, source_panel=panel, left=left, right=right,
                        execution_state="RESOURCE_PENDING" if any(c in NEW and c.split("::", 1)[0] in pending_arms for c in [left,right]) else "SCORING_EXECUTED",
                        **old.paired(a,b,np), probability=paired_probability(a,b,old,np)))
    prior_partial = None
    if allocation_kind == "DEF_REMAINDER":
        PHASE = "RETAINED_PARTIAL_CELL_AND_MASK_PARITY"
        previous_raw = read_ref(plan["prior_partial_scores"])
        previous = json.loads(gzip.decompress(previous_raw))
        prior_partial = partial_parity(previous,summaries,pairs,source_hashes,core_board,core_broad,completed3_board,completed3_broad)
        prior_partial.update(prior_partial_result=plan["prior_partial_scores"],preserved_three_arm_logical_sha256=preserved_three_arm_logical)
    per_player = None
    if plan.get("per_player_diagnostics", False):
        PHASE = "DESCRIPTIVE_PER_PLAYER_AGGREGATION"
        player_payload, per_player = player_diagnostics(board,broad,old,args.protocol_sha256)
        per_player["compressed_bytes_required"] = len(player_payload)
        per_player["registered_private_cap_bytes"] = budget["per_player_scorecard_max_bytes"]
        if len(player_payload) <= budget["per_player_scorecard_max_bytes"]:
            player_ref = store.put("PROFILE_INCREMENT_PER_PLAYER_FULL_FOUR_V1.json.gz",player_payload)
            check(native_read(player_ref) == player_payload, "protected per-player scorecard readback differs")
            per_player.update(state="RETAINED_PROTECTED_CARD_AND_PUBLIC_AGGREGATES",private_scorecard=player_ref)
        else:
            per_player.update(state="CORE_COMPLETE_PER_PLAYER_CARD_SIZE_REQUIRES_SCOPED_OWNER_ACTION",
                private_scorecard=None,private_export_complete=False)
    view = dict(version=VERSION, protocol_sha256=args.protocol_sha256, execution_receipt_sha256=sha(receipt_raw),
        allocation_kind=allocation_kind,score_scope_version="NAMED_THREE_ARMS_V1" if pending_arms else "FULL_FOUR_ARMS_V1",
        completed_arms=completed_arms, pending_arms=pending_arms, stable_core_candidate_ids=completed_products,
        old_execution_receipt_sha256=sha(old_raw), frozen_forecasts=receipt["forecasts"], old_frozen_forecasts=old_receipt["forecasts"],
        query_reference=query_ref, cohort_reference=cohort_ref, query_profile_input_reference=input_ref, source_refs=refs,
        candidate_ids=CANDIDATES, paired_candidate_ids=PAIRS, cohorts=COHORTS,
        prior_partial_parity=prior_partial,
        per_player_card=per_player.get("private_scorecard") if per_player else None,
        complete_decision_membership_sha256=sha(enc(sorted(memberships))), common_new_core_mask_sha256=sha(enc(sorted(core_board))),
        probability_contract="exact saved empirical/signedprior law at original line; conditionalplayed U/P/O; P2 maxOwnWinProbability, tieABSTAIN; pointviews retained separately",
        prevalence="earlier allRB explicit observed played rushyard labels; exactline categoricalLaplace1; samegameexcluded; no target-label update",
        reconstruction="Lossless manifest of recoverable exact original bytes/code/side policies and membership commitments; no duplicate restricted row archive",
        no_fits_model_loading_or_inference=True)
    payload = lzma.compress(enc(view), preset=6)
    check(len(payload) <= budget["private_view_max_bytes"], "private lossless score view exceeds registered128KiB")
    PHASE = "NATIVE_SCORE_VIEW_PERSISTENCE"
    view_name = "PROFILE_INCREMENT_SCORING_VIEW_PARTIAL_R0_R2_V1.json.xz" if pending_arms else "PROFILE_INCREMENT_SCORING_VIEW_FULL_FOUR_V1.json.xz"
    view_ref = store.put(view_name, payload)
    check(native_read(view_ref) == payload, "score view readback differs")
    result_state = "FROZEN_NAMED_THREE_ARMS_SCORING_COMPLETE_DEFENSE_PENDING" if pending_arms else "FROZEN_POINT_AND_EXACT_LINE_LAW_SCORING_COMPLETE"
    result = dict(version=VERSION, state=result_state, protocol_sha256=args.protocol_sha256,
        allocation_kind=allocation_kind,score_scope_version="NAMED_THREE_ARMS_V1" if pending_arms else "FULL_FOUR_ARMS_V1",
        completed_arms=completed_arms, pending_arms=pending_arms, stable_core_candidate_ids=completed_products,
        pending_candidate_states={arm+"::"+product: "RESOURCE_PENDING" for arm in pending_arms for product in PRODUCTS},
        candidate_ids=CANDIDATES, summaries=summaries, paired=pairs, source_sha256=source_hashes,
        execution_receipt_sha256=sha(receipt_raw), old_execution_receipt_sha256=sha(old_raw), private_scorecard_view=view_ref,
        prior_partial_parity=prior_partial,per_player_diagnostics=per_player,
        W8_source_and_qualification=w8meta, common_new_core_mask_sha256=sha(enc(sorted(core_board))),
        cohort_scope="AllbasicRBrows retained; historicalstat-row-conditioned cohorts lack authenticatedpregameuniverse. Empty priority/top20 is N/A, not success.",
        uncertainty="Nominal game/week block500seed20261110; exposed history, repeatedplayers, multiplicityunadjusted. Probability/cachedlaw postprocessing is not newNFLobservations.",
        limitations=["No2025actualoffers or newhistoricalperiod invented", "W8 saved reference thresholds do not add anactual-offer week",
            "OldbroadroleLeaf vsnewRB-onlybaseline is apopulation/complete-system contrast, notprofileeffect", "Noimpliedprobabilityforpoint-onlystrongcontrols",
            "NoROI,TopPicksqualification,currentpacketorproductionreleaseclaim"],
        counts=dict(new_fits=0, new_model_inference=0, new_source_HTTP=0, production_writes=0), storage=store.checkpoint(),
        resources=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started, RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    with args.output.open("xb") as handle:
        body = enc(result)
        handle.write(gzip.compress(body,mtime=0) if args.output.suffix == ".gz" else body)
        handle.flush(); os.fsync(handle.fileno())
    signal.alarm(0)
    print(json.dumps(dict(state=result["state"], output=str(args.output), private_view=view_ref, new_fits=0, new_inference=0)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--c-code-cache", type=Path, default=Path("/tmp/acceptance-c-review/src"))
    args = parser.parse_args()
    check(not args.output.exists(), "immutable score result already exists")
    try:
        run(args)
    except BaseException as error:
        signal.alarm(0)
        failure = dict(version=VERSION, state="SCORING_FAILED_NO_REFIT_OR_INFERENCE", phase=PHASE,
            error_type=type(error).__name__, protocol_sha256=args.protocol_sha256, new_fits=0, new_inference=0, automatic_retry=False)
        with args.output.with_name("PROFILE_INCREMENT_SCORING_FAILURE_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json").open("xb") as handle:
            handle.write(enc(failure))
        print(json.dumps(failure))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
