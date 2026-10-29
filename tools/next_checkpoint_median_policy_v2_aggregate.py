"""Root-sealed MAE projection decisions from an already-scored cohort aggregate.

This script never reads private comparison rows, models, forecast vectors or NFL
source values. It does not refit or recompute forecast errors from outcomes.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib
import io
import json
import math
import resource
import sys
import time

CAPS={"invocations":1,"CPU_seconds":12,"wall_seconds":30,"RSS_bytes":268435456,
    "NFL_value_decodes":0,"fits":0,"model_loads":0,"forecast_inference":0,"HTTP":0,"CAS_writes":0,
    "compressed_input_bytes_max":2097152,"uncompressed_aggregate_bytes_max":16777216,
    "aggregate_records_max":20000,"full_numeric_decisions_max":11,"output_bytes_max":65536}


def sha(body):return hashlib.sha256(body).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument("--plan",required=True);p.add_argument("--sha256",required=True);p.add_argument("--go",required=True)
    args=p.parse_args();raw=Path(args.plan).read_bytes();assert sha(raw)==args.sha256
    plan=json.loads(raw);go=json.loads(Path(args.go).read_bytes())
    assert plan["state"]=="ROOT_AND_REVIEWER_SEALED" and plan["review"]=="PASS" and plan["execution_authorized"] is True
    assert plan["resources"]==CAPS and go=={"state":"GO","root":"/root","review":"PASS","scope":"ONE_V2_POINT_AGGREGATE_DECISION","plan_sha256":args.sha256}
    assert sys.flags.dont_write_bytecode and sys.version_info[:3]==(3,12,14)
    def auth(ref):
        path=Path(ref["path"]);assert path.is_absolute() and path.resolve()==path and not path.is_symlink()
        body=path.read_bytes();assert len(body)==ref["bytes"] and sha(body)==ref["sha256"];return body
    for ref in plan["source_bindings"]:auth(ref)
    start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(12,13));resource.setrlimit(resource.RLIMIT_AS,(268435456,268435456))
    def audit(event,arguments):
        if event.startswith("socket.") or event in ("subprocess.Popen","os.system","os.fork","os.forkpty","os.posix_spawn","os.posix_spawnp"):
            raise RuntimeError("offline child-free safe-aggregate decision only")
    sys.addaudithook(audit)
    out=Path(plan["output_root"]);assert not out.exists();out.mkdir(parents=True);written=0
    def write(name,value):
        nonlocal written
        body=(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode();assert written+len(body)<=65536
        with (out/name).open("xb") as stream:stream.write(body)
        written+=len(body)
    write("CONSUMED.json",{"state":"ONE_SAFE_AGGREGATE_POLICY_DECISION_CONSUMED","plan_sha256":args.sha256,"new_NFL_fits_forecasts_rows_scored_models_HTTP_CAS":0,"automatic_retries":0})
    try:
        compressed=auth(plan["inputs"]["cohort_safe_aggregate"]);assert len(compressed)<=2097152
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as z:expanded=z.read(16777217)
        assert len(expanded)<=16777216
        cohort=json.loads(expanded);study=json.loads(auth(plan["inputs"]["executed_cohort_plan"]))
        consumed=json.loads(auth(plan["inputs"]["cohort_consumed"]))
        complete=json.loads(auth(plan["inputs"]["cohort_complete"]))
        qa=json.loads(auth(plan["inputs"]["cohort_independent_QA"]))
        assert cohort["state"]=="TOP_PLAYER_CACHED_COMPARISONS_COMPLETE" and cohort["version"]=="top-player-cached-v1-20261028"
        assert cohort["new_predictive_fits"]==cohort["new_model_inference"]==0
        assert consumed["plan_sha256"]==plan["inputs"]["executed_cohort_plan"]["sha256"]
        assert complete["state"]==cohort["state"] and complete["safe_output"]["sha256"]==sha(compressed)
        assert complete["managed_writer"]=="CLOSED"
        assert complete["grade"]==cohort["grade"] and complete["membership_freeze"]==cohort["membership_freeze"]
        assert complete["safe_output"]["uncompressed_sha256"]==sha(expanded) and complete["safe_output"]["uncompressed_bytes"]==len(expanded)
        assert qa["state"]=="PASS" and qa["source_safe_aggregate_sha256"]==sha(compressed)
        assert qa["grade_sha256"]==cohort["grade"]["sha256"]
        assert qa["membership_freeze_sha256"]==cohort["membership_freeze"]["sha256"]
        assert len(cohort["records"])<=20000
        root=Path(plan["worktree"]);sys.path.insert(0,str(root));engine=importlib.import_module("nfl_lab.next_checkpoint_median_policy_v2")
        current=plan["current_display_contracts"];admission=plan["operational_admission"]
        allfull=[r for r in cohort["records"] if r["position"]=="ALL_ORIGINAL_PRIMARY_ROLES" and r["group"]=="full" and r["period"]=="2026_W1_6"]
        assert len({(r["target"],r["method"]) for r in allfull})==len(allfull)
        decisions=[];probability_records=[]
        for target in study["categories"]:
            selected=[r for r in allfull if r["target"]==target]
            assert selected
            if target=="anytime_td":
                probability_records=selected;continue
            registered="nick-chart-ppr-v1" if target=="chart_ppr" else target
            cfg=study["categories"][target]
            expected={"offered_rows":cfg["expected_queries"],"scored_rows":cfg["expected_supported"],"games":93,"weeks":6}
            common={"target":registered,"scoring_target":registered,"season":2026,"season_type":"REG","weeks":[1,2,3,4,5,6],
                "role_population":cfg["roles"],"horizon_contract":"original retained source cutoffs; original unknown chart clocks stay unknown",
                "source_availability_policy":"original exposed current-vintage seven-day reconstruction unchanged",
                "comparison_receipt_sha256":plan["inputs"]["cohort_independent_QA"]["sha256"]}
            rows=[]
            for r in selected:
                m=r["metrics"];method=r["method"];kind=r["product"]
                if kind=="median":
                    product="point_median"
                    functional="full_cdf_lower_median" if method in ("CDF_MEDIAN","LEAF_CDF_CHART_MEDIAN_V1","ROLE_LAW_CHART_MEDIAN_V1") else "median_objective_point"
                elif kind=="median_objective_point":product,functional="point_median","median_objective_point"
                elif kind=="mean":product,functional="point_mean","expected_mean"
                elif kind=="mean_objective_point":product,functional="point_mean","valid_mean_objective_point"
                else:raise ValueError("unregistered source point product: "+kind)
                gates=admission.get(registered,{}).get(method,{name:False for name in engine.REQUIRED_GATES})
                assert set(gates)==set(engine.REQUIRED_GATES)
                rows.append({"method_id":method,"product":product,"functional":functional,"mean_eligible":product=="point_mean",
                    "MAE_2026":m["MAE"],"coverage":{"offered_rows":m["planned"],"scored_rows":m["scored"],"games":m["games"],"weeks":m["weeks"]},
                    "comparison_identity":common,"scoring_target":registered,"score_source_receipt_sha256":sha(compressed),
                    "declared_fallback_included":True,"operational_gates":gates,
                    "diagnostics":{"MSE_2026":m["MSE"],"RMSE_2026":m["RMSE"],"bias":m["bias"],"p90_AE":m["p90_AE"],"p95_AE":m["p95_AE"],
                        "strict_within":m["strict_within"],"inclusive_within":m["inclusive_within"],"tolerance":m["tolerance"],
                        "outcome_states":m["outcome_states"],"played_missing":m["played_missing"],"played_zero":m["played_zero"],
                        "fallback_planned":m["fallback_planned"],"fallback_scored":m["fallback_scored"],"original_forecast_clock_unknown":m["original_forecast_clock_unknown"],
                        "absolute_error_sum":m["absolute_error_sum"],"players":m["players"],
                        "query_population_is_not_book_offers":m["actual_prop_offered_population"],
                        "authentic_offer_side_or_close_and_correct":m["authentic_offer_side_or_close_and_correct"],
                        "2025_and_older":"Separate frozen original ledger panels, not averaged into2026loss or automaticveto",
                        "uncertainty":"Original cohort paired game/week intervals remain linked in pinned aggregate; per-position intervals are not silently pooled",
                        "SITE_R0_gain":"UNAVAILABLE_NO_MATCHING_HISTORICAL_WEBSITE_FORECASTS"}})
            request={"policy_version":engine.VERSION,"target":registered,"scoring_target":registered,"product":engine.PRODUCT,"primary":"MAE",
                "comparison_identity":common,"expected_coverage":expected,"current_display":current[registered],"candidates":rows}
            decisions.append(engine.choose_numeric_projection(request))
        assert len(decisions)==11 and probability_records
        elapsed=time.monotonic()-start;used=time.process_time()-cpu;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        assert elapsed<=30 and used<=12 and rss<=268435456
        result={"version":"stat-point-mae-v2-safe-cohort-decisions-v1","state":"EXPOSED_AGGREGATE_POLICY_DECISIONS_COMPLETE_NOT_ACTIVATED",
            "plan_sha256":args.sha256,"policy_version":engine.VERSION,"source_safe_aggregate":plan["inputs"]["cohort_safe_aggregate"],
            "source_plan":plan["inputs"]["executed_cohort_plan"],"independent_source_QA":plan["inputs"]["cohort_independent_QA"],
            "full_population_only":True,"subgroups_not_used_to_choose_global_model":True,"decisions":decisions,
            "coverage_semantics":"The legacy engine field offered_rows is the original generic query count here, not an authenticated sportsbook offer pool. No market lines, prices, selection returns or bookmaker coverage are inferred.",
            "current_display_semantics":"Live contracts/versions are recorded context; laboratory controls are not authentic historical current-website rows. In particular LIVE_SELECTED_COUNT_A_DECLARED_MEAN is distinct from cached corrected COUNT_A_MEAN; fallback-recipe equivalence is unverified.",
            "anytime_probability_stream":{"state":"NOT_CHANGED_BY_NUMERIC_POINT_POLICY","current_method":"TD_EQUAL_CDF_CAT","source_records":probability_records},
            "new_NFL_fits_models_queries_forecasts_rows_scored_HTTP_CAS":0,"live_activation":False,"actual_backend":"UNATTESTED",
            "resources":{"CPU_seconds":used,"wall_seconds":elapsed,"RSS_bytes":rss},
            "limits":["Source cohort is an exposed current-vintage reconstruction, not an authenticated historical SITE comparison",
                "Ranks and this initializer are development-informed, not untouched confirmation or evidence of an absolute best forecaster",
                "2025/older, genuineWeek7 and offered-market panels remain separate; no loss transfer",
                "Only current correctly typed operational admission gates can authorize an active candidate; retained owner still activates"]}
        write("DECISIONS.json",result);print(json.dumps({"state":result["state"],"decisions":len(decisions),"CPU_seconds":used,"wall_seconds":elapsed,"RSS_bytes":rss}))
    except BaseException as error:
        write("FAILED.json",{"state":"FAILED_SAFE_AGGREGATE_DECISION_PRESERVED","type":type(error).__name__,"error":str(error),"CPU_seconds":time.process_time()-cpu,
            "wall_seconds":time.monotonic()-start,"new_NFL_fits_models_forecasts_rows_scored_HTTP_CAS":0,"automatic_retries":0});raise


if __name__=="__main__":main()
