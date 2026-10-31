"""One outcome-blind, source-pinned all-seven-week preparation invocation.

Historical reconstruction only. It issues no operational forecasts, grades no
outcomes and never claims a current-vintage roster was published before games.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, io, json, resource, signal, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "matched12-primary-preparation-v1"

def sha(raw): return hashlib.sha256(raw).hexdigest()
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def encoded(x): return (json.dumps(x,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n").encode()

def execute(plan, plan_sha, go):
    started, cpu=time.monotonic(),time.process_time()
    if go.get("state")!="ROOT_AND_INDEPENDENT_GO" or go.get("plan_sha256")!=plan_sha:
        raise ValueError("exact reviewed preparation GO required")
    caps=plan["resources"]
    resource.setrlimit(resource.RLIMIT_CPU,(caps["CPU_seconds"],caps["CPU_seconds"]+1))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError("preparation wall cap")))
    signal.alarm(caps["wall_seconds"])
    def offline(event,args):
        if event in {"socket.connect","socket.connect_ex","socket.getaddrinfo"}:raise RuntimeError("offline preparation")
    sys.addaudithook(offline)
    for name, expected in plan["code_pins"].items():
        if sha((ROOT/name).read_bytes())!=expected:raise ValueError("source changed: "+name)
    sys.path.insert(0,str(ROOT))
    import pandas as pd
    from threadpoolctl import threadpool_limits
    from nfl_lab import data,features,cdf_engine,weekly_current_query
    adapter=load("matched12_primary_adapter",ROOT/"tools/category_topfive_matched12_prepare_v1.py")
    helper=load("matched12_primary_storage",ROOT/"tools/category_topfive_matched12_storage_v1.py")
    store,prepared=helper.open_store(ROOT,allocation_sha256=plan["allocation_sha256"],root_go=helper.GO)
    output=store.register_root(store.forward_root/"research"/VERSION)
    marker=output/"CONSUMED.json"
    if marker.exists():raise ValueError("single preparation invocation already consumed")
    store.atomic_json(marker,{"plan_sha256":plan_sha,"started_UTC":pd.Timestamp.now(tz="UTC").isoformat(),"fits":0})
    references={}
    def read(key):
        ref=plan["inputs"][key]
        path=Path(ref["path"])
        owners=(store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy)
        matching=[owner for owner in owners if any(path.is_relative_to(r) for r in owner._roots)]
        if len(matching)!=1:raise ValueError("exact original source owner not identified")
        actual=matching[0].validate_reference(path,ref["sha256"])
        if actual["bytes"]!=ref["bytes"]:raise ValueError("source size changed")
        references[key]={"sha256":actual["sha256"],"bytes":actual["bytes"]}
        return Path(ref["path"])
    try:
        roster=pd.read_parquet(read("roster"),columns=weekly_current_query.ROSTER_COLUMNS)
        schedule=pd.read_csv(read("schedule"),usecols=weekly_current_query.SCHEDULE_COLUMNS)
        authority={"integrator":"/root","numeric_preparation_authorized":True,"adapter_version":adapter.VERSION}
        packet=adapter.roster_queries(roster,schedule,query_builder=weekly_current_query.build_current_queries,
            normalize_team=data._team,authority=authority)
        # Freeze the expected identities before reading any source-stat values.
        def persist(name,frame):
            buf=io.BytesIO();frame.to_parquet(buf,index=False,compression="zstd")
            raw=buf.getvalue();path=output/name
            store.write_bytes(path,raw)
            ref=store.validate_reference(path,sha(raw))
            return {"sha256":ref["sha256"],"bytes":ref["bytes"],"rows":len(frame),"file":name}
        query_ref=persist("EXPECTED_QUERIES.parquet",packet["queries"])
        quarantine_ref=persist("IDENTITY_QUARANTINE.parquet",packet["quarantine"])
        history=[]
        for key in ("history","week6"):
            h=pd.read_parquet(read(key))
            # The library's utc=True conversion must never fabricate a known
            # zone for naive source clocks. Null availability remains unknown.
            for column in ("kickoff_utc","outcome_available_utc"):
                for value in h[column].dropna().unique():
                    if pd.Timestamp(value).tzinfo is None:raise ValueError("naive source clock: "+column)
            history.append(h)
        with threadpool_limits(limits=2):
            built=adapter.historical_features(history,packet,features_module=features,
                assert_clock_contract=cdf_engine.assert_clock_contract,authority=authority)
        f=built["features"]
        if len(f)!=len(packet["queries"]) or f.participation_state.ne("unknown").any():raise ValueError("query population changed")
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>caps["RSS_bytes"]:raise RuntimeError("preparation RSS cap")
        feature_ref=persist("HISTORICAL_FEATURES.parquet",f)
        result={"version":VERSION,"state":"PASS_SOURCE_PREPARATION_ONLY","plan_sha256":plan_sha,
            "original_issue_UTC":None,"generated_UTC":pd.Timestamp.now(tz="UTC").isoformat(),
            "evidence_tier":adapter.EVIDENCE,"source_bindings":references,
            "outputs":{"queries":query_ref,"quarantine":quarantine_ref,"features":feature_ref},
            "query_coverage":packet["coverage"],"feature_coverage":built["coverage"],
            "predictive_fits":0,"model_restorations":0,"forecast_inference_rows":0,"scoring_runs":0,
            "known_7day_assumption":"PRESERVED_EXPLICITLY_UNRESOLVED","f_player_play_rate8":"UNAVAILABLE_NULL",
            "actual":{"CPU_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-started,
                "RSS_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                "scope":"through_preterminal_storage_only"},
            "offhost_restoration":"NOT_VERIFIED","production_mutations":0}
        usage=store.verify_retained_checkpoint()
        if usage["new_peer_physical_bytes"]+2*len(encoded(result))+8192>prepared["allocation"]["wave_retained_limit_bytes"]:
            raise RuntimeError("retained final receipt capacity unavailable")
        store.atomic_json(output/"COMPLETE.json",result)
        store.verify_retained_checkpoint()
        result["invocation_actual"]={"CPU_seconds":time.process_time()-cpu,
            "wall_seconds":time.monotonic()-started,"RSS_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
        signal.alarm(0);return result
    except BaseException as exc:
        store.atomic_json(output/"FAILURE.json",{"version":VERSION,"state":"FAILED_ATTEMPT_PRESERVED",
            "exception_type":type(exc).__name__,"message":str(exc),"plan_sha256":plan_sha,
            "actual_CPU_seconds":time.process_time()-cpu,"actual_wall_seconds":time.monotonic()-started})
        raise

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--plan",type=Path,required=True);ap.add_argument("--go",type=Path,required=True)
    args=ap.parse_args();raw=args.plan.read_bytes()
    print(json.dumps(execute(json.loads(raw),sha(raw),json.loads(args.go.read_bytes())),sort_keys=True,allow_nan=False))
