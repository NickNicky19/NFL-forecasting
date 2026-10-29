"""One root-sealed fictional/source-aggregate exercise; no NFL values or model."""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import resource
import sys
import time
from types import SimpleNamespace

CAPS = {"invocations":1,"CPU_seconds":12,"wall_seconds":30,"RSS_bytes":134217728,
    "NFL_value_decodes":0,"fits":0,"model_loads":0,"HTTP":0,"CAS_writes":0,
    "fictional_cases_max":64,"safe_aggregate_decision_cells_max":11,
    "safe_aggregate_procedure_rows_max":192,"output_receipts_bytes_max":65536}


def sha(body): return hashlib.sha256(body).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--plan",required=True)
    parser.add_argument("--sha256",required=True);parser.add_argument("--go",required=True)
    args=parser.parse_args();raw=Path(args.plan).read_bytes();assert sha(raw)==args.sha256
    plan=json.loads(raw);go=json.loads(Path(args.go).read_bytes())
    assert plan["state"]=="ROOT_AND_REVIEWER_SEALED" and plan["execution_authorized"] is True
    assert plan["review"]=="PASS" and plan["resources"]==CAPS
    assert go=={"state":"GO","root":"/root","review":"PASS",
        "scope":"ONE_V2_POINT_SOFTWARE_AND_SAFE_AGGREGATE","plan_sha256":args.sha256}
    assert sys.flags.dont_write_bytecode and sys.version_info[:3]==(3,12,14)
    for item in plan["bindings"]:
        b=Path(item["path"]).read_bytes();assert len(b)==item["bytes"] and sha(b)==item["sha256"]
    start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(12,13))
    resource.setrlimit(resource.RLIMIT_AS,(134217728,134217728))
    blocked={"sockets":0,"children":0}
    def audit(event,arguments):
        if event.startswith("socket."):
            blocked["sockets"]+=1;raise RuntimeError("offline software/aggregate exercise")
        if event in ("subprocess.Popen","os.system","os.fork","os.forkpty","os.posix_spawn","os.posix_spawnp"):
            blocked["children"]+=1;raise RuntimeError("child-free software/aggregate exercise")
    sys.addaudithook(audit)
    out=Path(plan["output_root"]);assert not out.exists();out.mkdir(parents=True)
    written=0
    def write(name,value):
        nonlocal written
        body=(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
        assert written+len(body)<=65536
        with (out/name).open("xb") as stream:stream.write(body)
        written+=len(body)
    write("CONSUMED.json",{"state":"ONE_V2_SOFTWARE_AGGREGATE_INVOCATION_CONSUMED",
        "plan_sha256":args.sha256,"NFL_value_decodes_fits_models_HTTP_CAS":0,"automatic_retries":0})
    progress=[]
    try:
        root=Path(plan["worktree"]);sys.path.insert(0,str(root))
        engine=importlib.import_module("nfl_lab.next_checkpoint_median_policy_v2")
        view=importlib.import_module("nfl_lab.next_checkpoint_median_policy_v2_view")
        assert Path(engine.__file__).resolve()==root/"nfl_lab/next_checkpoint_median_policy_v2.py"
        def check(name,condition):
            assert condition,name;progress.append(name);assert len(progress)<=64
        def rejects(name,fn):
            try:fn()
            except (ValueError,TypeError,KeyError):progress.append(name)
            else:raise AssertionError(name+" incorrectly accepted")
        common=dict(target="pass_att",scoring_target="pass_att",season=2026,season_type="REG",
            weeks=[1,2,3,4,5,6],role_population=["QB"],horizon_contract="fictional",
            source_availability_policy="fictional",comparison_receipt_sha256="a"*64)
        coverage=dict(offered_rows=10,scored_rows=8,games=8,weeks=6)
        def candidate(name,product,functional,mae,mse=3,**extra):
            return dict(method_id=name,product=product,functional=functional,MAE_2026=mae,
                mean_eligible=product=="point_mean",scoring_target="pass_att",comparison_identity=deepcopy(common),
                coverage=deepcopy(coverage),score_source_receipt_sha256="b"*64,
                declared_fallback_included=True,diagnostics={"MSE_2026":mse,"MAE_2025":9,"bias":-20,"p95":80},
                operational_gates={key:True for key in engine.REQUIRED_GATES},**extra)
        base=candidate("BASE_MEAN","point_mean","expected_mean",2,2)
        med=candidate("MEDIAN","point_median","full_cdf_lower_median",1.5,4)
        req=dict(policy_version=engine.VERSION,target="pass_att",scoring_target="pass_att",
            product=engine.PRODUCT,primary="MAE",comparison_identity=common,expected_coverage=coverage,
            current_display={"method_id":"BASE_MEAN","product":"point_mean","functional":"expected_mean","version":"old"},
            candidates=[base,med])
        result=engine.choose_numeric_projection(req)
        check("lower_MAE_median_not_vetoed_by_bias_tails_2025",result["research_leader"]=="MEDIAN")
        check("separate_MSE_mean_leader",result["separate_valid_mean_MSE_leader"]=="BASE_MEAN")
        check("mean_display_contract_not_overwritten",result["actual_prior_display"]["product"]=="point_mean")
        t=deepcopy(req);t["candidates"].append(candidate("BETTER_MEAN","point_mean","expected_mean",1,9))
        z=engine.choose_numeric_projection(t)
        check("lower_MAE_mean_not_hidden_or_renamed",z["research_leader"]=="BETTER_MEAN" and z["research_leader_original_functional"]=="expected_mean")
        check("strict_median_leader_stays_distinct",z["strict_median_MAE_leader"]=="MEDIAN")
        check("MSE_leader_independent_of_MAE_mean",z["separate_valid_mean_MSE_leader"]=="BASE_MEAN")
        t=deepcopy(req);t["candidates"].append(candidate("LEGACY","point_empirical","legacy_mixed_point",1,1))
        z=engine.choose_numeric_projection(t)
        check("legacy_can_win_MAE_under_empirical_contract",z["research_leader"]=="LEGACY" and z["research_leader_original_product"]=="point_empirical")
        check("legacy_does_not_enter_validmean_board",z["separate_valid_mean_MSE_leader"]=="BASE_MEAN")
        t=deepcopy(req);t["candidates"][1]["MAE_2026"]=2
        check("exact_tie_retains_actual_mean_point",engine.choose_numeric_projection(t)["research_leader"]=="BASE_MEAN")
        t=deepcopy(req);t["candidates"][0]["operational_gates"]["consumer_contract"]=False;t["candidates"][1]["operational_gates"]["future_inference"]=False
        z=engine.choose_numeric_projection(t)
        check("readiness_preserves_old_typed_fallback",z["operational_candidate"] is None and z["unchanged_fallback_contract"]["product"]=="point_mean")
        for name,mutation in [
            ("mislabeled_mean",lambda r:r["candidates"][1].update(product="point_mean",functional="expected_mean",mean_eligible=False)),
            ("incompatible_population",lambda r:r["candidates"][1]["comparison_identity"].update(horizon_contract="other")),
            ("missing_offered_rows",lambda r:r["candidates"][1]["coverage"].update(offered_rows=9)),
            ("missing_fallbacks",lambda r:r["candidates"][1].update(declared_fallback_included=False)),
            ("nan_loss",lambda r:r["candidates"][1].update(MAE_2026=float("nan")))]:
            t=deepcopy(req);mutation(t);check(name,engine.choose_numeric_projection(t)["research_leader"]=="BASE_MEAN")
        t=deepcopy(req);t["scoring_target"]="rec_yd"
        rejects("wrong_scoring_target",lambda:engine.choose_numeric_projection(t))
        t=deepcopy(req);t["candidates"].append(deepcopy(t["candidates"][0]))
        rejects("duplicate_procedure",lambda:engine.choose_numeric_projection(t))
        class Law:
            def __init__(self,atoms,support):self.atoms=atoms;self.prior=SimpleNamespace(support=support)
            @property
            def mean(self):return [sum(y*p for y,p in row) for row in self.atoms]
            def quantile(self,q):
                values=[]
                for row in self.atoms:
                    cumulative=0
                    for y,p in row:
                        cumulative+=p
                        if cumulative>=q:values.append(y);break
                return values
            def cdf(self,thresholds):return [sum(p for y,p in row if y<=x) for row,x in zip(self.atoms,thresholds)]
        f=view.full_law_functionals(Law([[(0,.6),(2,.4)],[(1,.8),(3,.2)]],"count"),target="pass_att")
        check("actual_count_lowerquantile_not_defaultmean",f["median"]==[0.,1.] and abs(f["expected_mean"][0]-.8)<1e-12)
        f=view.full_law_functionals(Law([[(-2,.6),(4,.4)]],"signed_integer"),target="rush_yd")
        check("signed_yard_median_preserved",f["median"]==[-2.])
        f=view.full_law_functionals(Law([[(-1,.6),(50,.4)]],"signed_integer"),target="nick-chart-ppr-v1")
        check("signed_chart_scale50",f["median"]==[-.02])
        row=dict(schema_version=view.VERSION,target="pass_att",scoring_target="pass_att",
            selection_product=engine.PRODUCT,selection_metric="MAE",game_id="fictional-game",player_id="fictional-player",horizon="fixture",
            model_version="1"*64,procedure_version="2"*64,source_policy_sha256="3"*64,capture_receipt_sha256="4"*64,
            consumer_contract_version=view.VERSION,information_cutoff_utc="2026-01-01T00:00Z",issued_at="2026-01-01T00:01Z",
            issue_deadline_utc="2026-01-01T00:02Z",kickoff_utc="2026-01-01T00:03Z",feature_max_source_available_utc="2026-01-01T00:00Z",
            forecast_value=0,forecast_product="point_median",prediction_functional="full_cdf_lower_median",separate_expected_mean=.8,
            functional_proof=dict(extractor_version=view.FUNCTIONAL_VERSION,cdf_below=0,cdf_at=.6),fallback=False)
        check("median_consumer_label_and_expectedmean",view.consumer_view(row)["projection_label"]=="Selected median" and view.consumer_view(row)["expected_mean"]==.8)
        t=deepcopy(row);t.update(forecast_product="point_mean",prediction_functional="expected_mean",forecast_value=.8,mean_eligible=True)
        check("mean_can_be_MAE_projection_without_median_label",view.consumer_view(t)["projection_label"]=="Selected mean projection")
        t.update(fallback=True,fallback_reason="prior reference",original_contract_version="old_mean_v1")
        check("truthful_mean_fallback_label",view.consumer_view(t)["projection_label"]=="Mean fallback")
        t=deepcopy(row);t.update(forecast_product="point_empirical",prediction_functional="legacy_mixed_point")
        check("truthful_legacy_projection_label",view.consumer_view(t)["projection_label"]=="Selected empirical point")
        for name,change in [("future_source",{"feature_max_source_available_utc":"2026-01-01T00:01Z"}),
            ("wrong_label_target",{"scoring_target":"rec_yd"}),("bad_source_hash",{"source_policy_sha256":"not-a-hash"}),
            ("late_issue",{"issued_at":"2026-01-01T00:02Z"}),("unknown_warm_source",{"feature_max_source_available_utc":None}),
            ("binary_is_not_point",{"forecast_product":"binary_probability","prediction_functional":"event_probability"})]:
            t=deepcopy(row);t.update(change);rejects(name,lambda t=t:view.consumer_view(t))
        t=deepcopy(row);t["functional_proof"]["cdf_below"]=.5
        rejects("not_lower_median_bracket",lambda:view.consumer_view(t))
        records=[]
        for method,loss in [("A",2.),("B",1.),("R0",3.)]:
            records.append(dict(epoch=engine.VERSION+":future1",horizon="fixture",category="pass_att",product=engine.PRODUCT,primary="MAE",
                genuine_pregame=True,qualified_final_outcome=True,information_cutoff="2026-01-01T00:00Z",issued_at="2026-01-01T00:01Z",
                issue_deadline="2026-01-01T00:02Z",kickoff="2026-01-01T00:03Z",resolved_at="2026-01-01T03:00Z",
                method=method,opportunity_key="one",loss=loss,forecast_product="point_mean",prediction_functional="expected_mean",mean_eligible=True,scoring_target="pass_att"))
        kw=dict(methods=["A","B","R0"],current="A",reference="R0",epoch=engine.VERSION+":future1",horizon="fixture",target="pass_att",decision_at="2026-01-02T00:00Z",expected_resolved_keys=["one"])
        check("new_epoch_future_commonpool",engine.choose_future_numeric(records,**kw)["selected"]=="B")
        check("missing_commoncoverage_retains",engine.choose_future_numeric(records[:2],**kw)["selected"]=="A")
        t=deepcopy(records);t[0]["issued_at"]=t[0]["issue_deadline"]
        rejects("future_equal_deadline_not_timely",lambda:engine.choose_future_numeric(t,**kw))
        bad=dict(kw,epoch="original-P2")
        rejects("old_epoch_not_reused",lambda:engine.choose_future_numeric(records,**bad))
        check("no_probability_EV_claim",view.consumer_view(row)["new_probability_or_EV_claim"] is False)
        elapsed=time.monotonic()-start;used=time.process_time()-cpu;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        assert elapsed<=30 and used<=12 and rss<=134217728 and not any(blocked.values())
        write("SOFTWARE_COMPLETE.json",{"state":"FICTIONAL_V2_POINT_POLICY_AND_CONSUMER_PASS","plan_sha256":args.sha256,
            "cases":progress,"case_count":len(progress),"CPU_seconds":used,"wall_seconds":elapsed,"RSS_bytes":rss,
            "blocked_attempts":blocked,"NFL_value_decodes_fits_models_queries_HTTP_CAS":0,"actual_backend":"UNATTESTED",
            "boundary":"Fictional software checks; no NFL fit, accuracy result, source qualification, pregame capture or live activation"})
        print(json.dumps({"state":"PASS","fictional_cases":len(progress),"CPU_seconds":used,"wall_seconds":elapsed,"RSS_bytes":rss}))
    except BaseException as error:
        write("FAILED.json",{"state":"FAILED_ATTEMPT_RETAINED","type":type(error).__name__,"error":str(error),"completed_cases":progress,
            "CPU_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-start,"NFL_value_decodes_fits_models_HTTP_CAS":0,"automatic_retries":0})
        raise


if __name__=="__main__":main()
