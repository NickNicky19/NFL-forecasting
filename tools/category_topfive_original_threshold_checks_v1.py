"""Bounded fictional cases through exact current website numerical functions.

No football forecasts, fits, network, file publication or venue settlement.
The website source root must be an existing read-only checkout whose pinned
Git blobs match; unneeded top-level producer imports are not executed.
"""
from __future__ import annotations

import argparse
import ast
import collections
import copy
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time
import types

VERSION = "original-threshold-real-functions-fictional-cases-v1"
HEAD = "1ec93e068a91abd51c990937d1019e4a831694b4"
PINS = {
    "pull/build.py": "13a09f2a3e02e1819432860ee98417cf445cad99",
    "pull/grade.py": "452a19ae4a76dada46ec19d68d2f7349769208d1",
    "pull/scoring.py": "5a6386ee77b142b7a3404cad5712f88403a39416",
    "tools/weekly_adaptive_overlay.py": "480b4eded50de581d478ba8e11c2ccb4986820fa",
}
RANKING_BLOB = "1f5d3d458bedcb7eaffe52c95c0bce4ff3380e26"
APP_BLOB = "af0b7cd838938e554e15c461929026310cd3cd8c"


def sha(body):
    return hashlib.sha256(body).hexdigest()


def blob(body):
    return hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()


def exact_functions(body, names, namespace):
    tree = ast.parse(body.decode())
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    if {n.name for n in selected} != set(names):
        raise ValueError("Exact function set unavailable")
    exec(compile(ast.Module(body=selected, type_ignores=[]), "<exact-current-website-functions>", "exec"), namespace)
    return {n.name: sha(ast.get_source_segment(body.decode(), n).encode()) for n in selected}


NODE = r'''
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const S={data:{season:2026,week:8,execution_model:{model:'sleeper-matchup-classic-fg-identity-v1'}},lines:{},games:{}};
const ctx=vm.createContext({S,Date,Number,JSON,Math,Object,Array,globalThis:{}});
vm.runInContext(input.source,ctx,{timeout:1000});
const result=[];
for(const c of input.cases){
 const p={id:'fictional-player',game_id:'fictional-game',team:'AAA',espn_id:'999999999'};
 const g={id:p.game_id,state:'post',detail:'Final',home:'AAA',away:'BBB',kickoff:'2026-11-01T18:00:00Z'};
 S.games={[p.game_id]:g};
 S.propEvents={[p.game_id]:{season:2026,week:8,gid:p.game_id,kickoff:g.kickoff,source:'ESPN_EVENT_BOXSCORE',final:true,
  players:{[p.id]:{team:p.team,espn_id:p.espn_id,played:true,dnp:false,conflict:false,stats:{[c.key]:c.actual}}}}};
 const prop={key:c.key,line:c.line,adj:c.point,line_from:'dk'};
 const selected=ctx.selectedPropGap(p,prop);
 const graded=ctx.propStatus(p,c.key,c.line,c.direction);
 if(selected?.value!==c.point||selected?.lean!==c.direction||graded?.v!==c.actual||graded?.res!==c.expected)throw Error('Browser case '+c.case_id);
 result.push({case_id:c.case_id,value:selected.value,lean:selected.lean,result:graded.res});
}
const p={id:'fictional-player',game_id:'fictional-game',team:'AAA',espn_id:'999999999'};
const g=S.games[p.game_id];
const saved={schema_version:'mypicks-player-game-v1',pid:p.id,gid:p.game_id,season:2026,week:8,team:p.team,espn_id:p.espn_id,
 kickoff:g.kickoff,period:'full_game_including_overtime',stat_source:'ESPN_EVENT_BOXSCORE'};
const unsupported=ctx.propStatus(p,'fpts',1.5,'over',saved);
if(unsupported?.res!=='unresolved')throw Error('Saved fantasy scoring falsely admitted');
S.propEvents[p.game_id].players[p.id]={team:p.team,espn_id:p.espn_id,played:false,dnp:true,conflict:false,stats:{}};
if(ctx.propStatus(p,'rec',4.5,'over')?.res!=='dnp')throw Error('DNP changed to zero');
S.propEvents[p.game_id].players[p.id]={team:p.team,espn_id:p.espn_id,played:false,dnp:false,conflict:false,stats:{}};
if(ctx.propStatus(p,'rec',4.5,'over')?.res!=='unresolved')throw Error('Unknown participation changed to zero');
process.stdout.write(JSON.stringify({cases:result,saved_fantasy_consumer:unsupported.res,dnp_distinct_from_unknown:true}));
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--website-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    args = parser.parse_args()
    out = args.report_root
    out.mkdir(exist_ok=True, parents=True)
    target = out / "THRESHOLD_REAL_PATH_RESULTS_V1.json"
    if target.exists():
        raise ValueError("Immutable first-attempt result already exists")
    started, cpu = time.monotonic(), time.process_time()
    receipt = {"version": VERSION, "website_head": HEAD, "fictional_cases_only": True,
               "NFL_fits_model_inference_forecasts_capture_deployments": 0,
               "HTTP_GETs_this_execution": 0, "prior_source_HTTP_GETs": 2,
               "source_paths_public_relative_only": True, "state": "STARTED"}
    (out / "STARTED_V1.json").write_text(json.dumps(receipt, indent=2) + "\n")
    try:
        sources = {}
        pins = []
        for name, pin in PINS.items():
            body = (args.website_root / name).read_bytes()
            if blob(body) != pin:
                raise ValueError("Current source mismatch: " + name)
            sources[name] = body
            pins.append({"path": name, "git_blob": pin, "bytes": len(body), "sha256": sha(body)})
        # Actual scoring module; import-time content is constants/functions only.
        scoring = types.ModuleType("fictional_fixture_current_scoring")
        exec(compile(sources["pull/scoring.py"], "<exact-current-scoring>", "exec"), scoring.__dict__)
        env = {"scoring": scoring, "statistics": statistics, "Counter": collections.Counter,
               "math": math, "GRADING_VERSION": "statistical-v3-identity-20261025"}
        build_hashes = exact_functions(sources["pull/build.py"], {"player_props", "apply_book"}, env)
        grade_hashes = exact_functions(sources["pull/grade.py"], {"_number", "played", "participation", "result",
                                      "tally", "_bound_stats", "_prop_result", "grade_week"}, env)
        overlay = types.ModuleType("weekly_adaptive_overlay")
        exec(compile(sources["tools/weekly_adaptive_overlay.py"], "<exact-current-overlay>", "exec"), overlay.__dict__)
        sys.modules["weekly_adaptive_overlay"] = overlay
        rank_body = (out / "CURRENT_RANKING_SOURCE.py").read_bytes()
        if blob(rank_body) != RANKING_BLOB:
            raise ValueError("Current ranking source mismatch")
        ranking = types.ModuleType("fictional_fixture_current_rankings")
        exec(compile(rank_body, "<exact-current-rankings>", "exec"), ranking.__dict__)
        pins.append({"path": "tools/weekly_selected_rankings.py", "git_blob": RANKING_BLOB,
                     "bytes": len(rank_body), "sha256": sha(rank_body)})

        class IdentityMatchup:
            def factor(self, *unused):
                return 1.0, 0

        def forecast(key, point, line):
            pos = "QB" if key.startswith("pass_") else "RB"
            props = env["player_props"]({"pos": pos}, {key: point}, [], 2026, "BBB", IdentityMatchup())
            prop = next(p for p in props if p["key"] == key)
            env["apply_book"]([prop], {key: {"close": line, "open": line}})
            if prop["adj"] != point:
                raise AssertionError("Unexpected count rounding")
            return prop

        cases = []
        for key, line, actuals, over, under in [
            ("pass_td", 1.5, [0, 1, 2, 3], 1.88, 1.12),
            ("rec", 4.5, [4, 5], 5.1, 3.9),
            ("pass_cmp", 19.5, [19, 20], 20.5, 18.5),
            ("pass_att", 29.5, [29, 30], 31.0, 28.0),
            ("rec", 5.0, [5], 5.6, 4.4),
            ("rush_yd", -1.5, [-3, -1], 3.5, -6.0),
        ]:
            for direction, point in [("over", over), ("under", under)]:
                for actual in actuals:
                    expected = "push" if actual == line else "hit" if (actual > line if direction == "over" else actual < line) else "miss"
                    cases.append(dict(case_id=f"{key}:{line}:{direction}:{actual}", key=key, line=line,
                                      point=point, direction=direction, actual=actual, expected=expected))
        python_results = []
        for case in cases:
            prop = forecast(case["key"], case["point"], case["line"])
            if prop["lean"] != case["direction"]:
                raise AssertionError("Original producer chose different lean")
            player = dict(id="fictional-player", name="Fictional Fixture", game_id="fictional-game", team="AAA", opp="BBB",
                          pos="QB" if case["key"].startswith("pass_") else "RB", props=[prop], proj_ppr=20.0,
                          games_this_season=6, snap_share=1.0, injury=None)
            game = dict(id="fictional-game", home="AAA", away="BBB", state="pre", kickoff="2026-11-01T18:00:00Z")
            board = dict(season=2026, week=8, players=[player], games=[game])
            board_hash = overlay.digest(board)
            doc = dict(schema_version=overlay.VERSION, registration_id="weekly-adaptive-release-v1", state="DISABLED_USE_R0",
                       season=2026, week=8, canonical_board_sha256=board_hash, display_board_sha256=board_hash,
                       board_contract_sha256=overlay.digest(overlay.board_contract(board)), prepared_at="2026-10-30T20:00:00Z",
                       packaged_at="2026-10-30T20:00:00Z", website_source_sha=HEAD,
                       publication_review_sha256="0" * 64, rows=[], frozen_rows=[], fallback_counts={})
            prepared = ranking.prepare(board, board_hash, doc, overlay.digest(doc), now="2026-10-30T20:00:01Z", website_source_sha=HEAD)
            items = prepared["picks"][case["direction"]]
            # Signed low lines intentionally fail the existing Top Picks min-line gate.
            expect_top_pick = case["key"] != "rush_yd"
            if bool(items) != expect_top_pick:
                raise AssertionError("Actual Top Picks eligibility changed")
            if items and (items[0]["adj"] != case["point"] or items[0]["direction"] != case["direction"]):
                raise AssertionError("Writer rounded or changed selected point")
            stats = {player["id"]: dict(team="AAA", opp="BBB", stats={"gp": 1, case["key"]: case["actual"]})}
            archive = dict(season=2026, week=8, players=[player], games=[game], picks=prepared["picks"])
            graded = env["grade_week"](archive, stats, None)
            category = graded["leans"]["by_category"][case["key"]]
            if category[case["expected"]] != 1:
                raise AssertionError("Saved original lean grade mismatch")
            if items and graded["top_" + case["direction"]]["picks"][0]["result"] != case["expected"]:
                raise AssertionError("Saved original Top Pick grade mismatch")
            python_results.append(dict(case, producer_lean=prop["lean"], stored_point=prop["adj"],
                                       actual_top_pick_eligible=expect_top_pick, original_lean_grader=case["expected"],
                                       top_pick_grader=case["expected"] if items else "NOT_ELIGIBLE_MINIMUM_LINE"))

        app = (out / "CURRENT_BROWSER_FUNCTIONS.js").read_text()
        browser = subprocess.run(["node", "--max-old-space-size=128", "-e", NODE],
                                 input=json.dumps(dict(source=app, cases=cases)), text=True,
                                 capture_output=True, timeout=15, check=True)
        browser_result = json.loads(browser.stdout)
        from nfl_lab.next_checkpoint_chart_ppr import WEIGHTS, score_observed
        from nfl_lab.cdf_engine import SupportPrior, valid_support
        chart = {k: 0 for k in WEIGHTS}
        chart.update(pass_yd=1, rush_yd=-3, rec=1, rec_yd=12)
        scored = score_observed(chart)
        if scored.value is None or not math.isclose(scored.value, 1.94) or float(scored.value).is_integer():
            raise AssertionError("Chart scoring coerced onto count lattice")
        chart_checks = [dict(side=side, actual=scored.value, line=line, result=env["result"](side, scored.value, line))
                        for side, line in [("over", 1.5), ("under", 2.0), ("over", scored.value)]]
        if [x["result"] for x in chart_checks] != ["hit", "hit", "push"]:
            raise AssertionError("Fractional chart threshold arithmetic changed")
        # An explicit fictional geometric PRIOR, not a Poisson or a law inferred from 1.88.
        law = SupportPrior(support="count", q=.6, n=0)
        probability_checks = []
        last = 1.0
        for line in [0.5, 1.5, 2.0, 2.5, 4.5, 19.5]:
            over = float(1 - law.cdf(math.floor(line)))
            under = float(law.cdf(math.ceil(line) - 1))
            push = float(math.exp(float(law.logpmf(line)))) if float(line).is_integer() else 0.0
            if not math.isclose(over + under + push, 1.0, abs_tol=1e-12) or over > last + 1e-12:
                raise AssertionError("Threshold probabilities incoherent")
            last = over
            probability_checks.append(dict(line=line, p_over=over, p_under=under, p_push=push))
        if valid_support([1.88], "count").any() or not valid_support([-3], "signed_integer").all():
            raise AssertionError("Outcome support contract changed")
        unchanged = env["_prop_result"]({"key": "rec", "line": 4.5}, "over", {"stats": {}})
        if unchanged != (None, "unresolved"):
            raise AssertionError("Missing participation became zero")
        receipt.update(state="PASS_SUPPORTED_NUMERICAL_PATHS_CHART_LIVE_PATH_BLOCKED",
                       source_pins=pins, app_full_git_blob=APP_BLOB, app_functions_sha256=sha(app.encode()),
                       actual_source_functions={"producer": build_hashes, "grader": grade_hashes,
                                                "writer": ["prepare", "effective", "eligible", "validate_item"],
                                                "browser": ["selectedPropGap", "propStatus", "propValue"]},
                       python_cases=python_results, browser_cases=browser_result,
                       chart={"scoring_version": "nick-chart-ppr-v1", "components": chart, "score": scored.value,
                              "generic_numeric_grader_cases": chart_checks,
                              "full_chart_live_path": "BLOCKED_NOT_ADMITTED; current saved-fpts consumer deliberately unresolved. No legacy scorer relabeling.",
                              "scope": "Chart scorer and generic numeric grader only; no chart producer/catalog/consumer admission claimed."},
                       probability_arithmetic={"law": "Explicit fictional count SupportPrior(q=0.6), conditional on played; not fitted or inferred from a point forecast.",
                                               "cases": probability_checks, "count_support_rejects_1_88": True,
                                               "probability_accuracy_or_market_settlement_test": False},
                       confirmed_threshold_grading_defects=[],
                       limitations=["Fictional numerical fixtures, not NFL accuracy evidence or venue settlement.",
                                    "All-source publication and private restoration checks are outside these fixtures.",
                                    "Original reference fallback and real selected-gap browser functions exercised; future typed MAE admission is separate.",
                                    "A count mean of 1.88 remains 1.88; it is neither a count outcome nor an Over probability.",
                                    "Chart-specific saved-pick live path remains unsupported until the owner integrates its exact contract."],
                       CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started,
                       max_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
        if receipt["CPU_seconds"] > 45 or receipt["wall_seconds"] > 90 or receipt["max_RSS_bytes"] > 536870912:
            raise ValueError("Software budget exceeded")
        encoded = (json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        retained = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) + Path(__file__).stat().st_size
        if retained + len(encoded) > 65536:
            raise ValueError("Retained metadata budget exceeded before result write")
        target.write_bytes(encoded)
        print(json.dumps({"state":receipt["state"], "python_cases":len(python_results),
                          "browser_cases":len(browser_result["cases"]), "chart_numeric_cases":len(chart_checks),
                          "probability_fixture_cases":len(probability_checks), "CPU_seconds":receipt["CPU_seconds"],
                          "wall_seconds":receipt["wall_seconds"], "NFL_fits_forecasts_capture":0}))
    except BaseException as exc:
        receipt.update(state="FAILED_RETAINED", error_type=type(exc).__name__, error=str(exc),
                       CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started)
        (out / "FAILURE_V1.json").write_text(json.dumps(receipt, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
