"""Finish only the frozen R3 defense arm; reuse three retained model/law parts.

One fit, one fitted-model inference path, no source acquisition or grader.
The new allocation preserves the original primary16 and completion8 limits.
"""
from __future__ import annotations
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
VERSION="PROFILE-INCREMENT-TO-RELEASE-01-A-v2-def-remainder-v1"
PRIMARY="PROFILE-INCREMENT-TO-RELEASE-01-A-v2"
KEY=["season","week","game_id","player_id"]
CTX=["team","opponent","position","kickoff_utc","cutoff_utc"]
ARMS=["RB_ONLY_LEAF_BASE","R1_RB_ONLY_LEAF_SUPPORT","R2_RB_ONLY_LEAF_PLAYER_OFFENSE","R3_RB_ONLY_LEAF_DEFENSE"]
STATE=dict(phase="NOT_STARTED",new_fits_attempted=0,new_fits_returned=0,artifacts=[])

def enc(value):return(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def local(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def read_ref(ref):
    body=Path(ref["path"]).read_bytes()
    if len(body)!=ref["bytes"]or sha(body)!=ref["sha256"]:raise ValueError("bound registration metadata changed")
    return body

def authorize(args):
    raw=args.protocol.read_bytes()
    if sha(raw)!=args.protocol_sha256:raise ValueError("exact supplemental protocol hash required")
    plan=json.loads(raw);go=json.loads(read_ref(dict(path=str(args.root_go),bytes=args.root_go.stat().st_size,sha256=args.root_go_sha256)))
    if (plan.get("version")!=VERSION or plan.get("state")!="ROOT_REGISTERED_EXECUTION_GO"
            or plan.get("maximum_new_fits")!=1 or plan.get("remaining_global_fit_slot")!=4
            or go.get("state")!="ROOT_AND_INDEPENDENT_GO" or go.get("registered_by")!="/root"
            or go.get("protocol_sha256")!=args.protocol_sha256):raise ValueError("exact root/independent one-fit completion GO required")
    expected=dict(CPU_seconds=600,wall_seconds=1800,RSS_bytes=3*1024**3,threads=2,model_reservation_bytes=3*1024**2,failure_reserve_bytes=2*1024**2)
    if plan.get("resources")!=expected:raise ValueError("finite one-arm runtime envelope differs")
    for path,expected_hash in plan["code_sha256"].items():
        if sha((ROOT/path).read_bytes())!=expected_hash:raise ValueError("executing supplemental code changed")
    for path,expected_hash in plan["source_configuration_sha256"].items():
        if sha((ROOT/path).read_bytes())!=expected_hash:raise ValueError("retained source configuration changed")
    publication=json.loads(read_ref(dict(path=str(args.publication_receipt),bytes=args.publication_receipt.stat().st_size,sha256=args.publication_receipt_sha256)))
    if publication.get("state")!="PUBLICATION_COMPLETE":raise ValueError("actual pre-execution publication/readback required")
    STATE["plan_raw"]=raw
    return plan

def runtime(plan):
    for key in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"]:os.environ[key]="2"
    resource.setrlimit(resource.RLIMIT_CPU,(540,600));resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2)
    def exhausted(signum,_frame):
        if signum==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
        raise TimeoutError("finite one-arm completion; failure retention reserved")
    for sig in [signal.SIGXCPU,signal.SIGALRM,signal.SIGTERM]:signal.signal(sig,exhausted)
    signal.alarm(1680)
    def offline(event,_args):
        if event in {"socket.connect","socket.connect_ex","socket.getaddrinfo"}:raise RuntimeError("offline retained-source completion")
    sys.addaudithook(offline)
    import numpy as np,pandas as pd,pyarrow as pa
    pa.set_cpu_count(2);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
    return np,pd

def run(plan,public_receipt):
    start,cpu=time.monotonic(),time.process_time();np,pd=runtime(plan)
    import joblib
    from threadpoolctl import threadpool_limits
    from nfl_lab import cdf_engine as cdf,player_context_rush_efficiency_v1 as core
    increment=local("nfl_lab.profile_increment_a_v2","nfl_lab/profile_increment_a_v2.py")
    guard=local("nfl_lab.profile_increment_a_def_remainder_storage_v1","nfl_lab/profile_increment_a_def_remainder_storage_v1.py")
    old=local("tools.player_context_completion_efficiency_v1","tools/player_context_completion_efficiency_v1.py")
    primary_runner=local("tools.profile_increment_a_run_v2","tools/profile_increment_a_run_v2.py")
    carry=local("tools.abc_a_dynamic_carry_wave_v1","tools/abc_a_dynamic_carry_wave_v1.py")
    if cdf.TREE_PARAMETERS!=dict(n_estimators=32,criterion="squared_error",max_depth=8,min_samples_leaf=30,max_features=1.0,bootstrap=False,random_state=1701,n_jobs=2)or cdf.PRIOR_WEIGHT!=.05:
        raise ValueError("frozen one-family recipe changed")
    store=guard.RemainderStore(ROOT,plan["allocation"]["path"],plan["allocation"]["sha256"],root_go=guard.GO)
    STATE["store"]=store
    def put(name,body,failure=False):
        ref=store.put(name,body,failure=failure);STATE["artifacts"].append(ref);return ref
    try:
        refs={ref["id"]:ref for ref in plan["retained_primary_artifacts"]}
        models=["MODEL_2026_"+arm+".joblib" for arm in ARMS[:3]]
        parts=["FORECAST_2026_"+arm+".json.gz" for arm in ARMS[:3]]
        required=set(models+parts+["FIT_1_CONSUMED.json","FIT_2_CONSUMED.json","FIT_3_CONSUMED.json",
            "QUERY_BASE_INPUTS_RECOVERED_V5.parquet","QUERY_PROFILE_INPUTS_2026.parquet",
            "SOURCE_AND_PROFILE_BINDING.json","BASIC_PROFILES_AND_COHORTS_2026.json.gz",
            "ALL32_RUSHING_DEFENSE_SNAPSHOTS_2026.json.gz","UNAVAILABLE_PROFILES_2026_W8.json.gz",
            "FAILURE_PRIVATE_PILOT_RESUME_V5.json"])
        if required-set(refs):raise ValueError("exact three-model/three-part/source bindings incomplete")
        if {p.name for p in store.primary.glob("MODEL*")}!=set(models)or(store.primary/"FIT_4_CONSUMED.json").exists():
            raise ValueError("original global fit state is not exactly three completed models")
        if (store.destination/"FIT_4_CONSUMED.json").exists()or list(store.destination.glob("MODEL*")):
            raise ValueError("supplement fit already consumed; no automatic retry")
        bodies=store.read_many([dict(refs[name],namespace="PRIMARY")for name in sorted(required)])
        if any(len(bodies[name])!=refs[name]["bytes"]for name in required):raise ValueError("retained primary artifact size differs")
        previous_failure=json.loads(bodies["FAILURE_PRIVATE_PILOT_RESUME_V5.json"])
        if previous_failure["fits_attempted"]!=3 or previous_failure["fits_returned"]!=3:raise ValueError("three consumed fit receipts required")
        prior_fit_cpu=previous_failure["model_fit_CPU_seconds"]
        if abs(prior_fit_cpu-plan["previous_model_fit_CPU_seconds"])>1e-9:raise ValueError("consumed prior model CPU differs")
        original_rows=[];part_refs=[]
        for arm,name in zip(ARMS[:3],parts):
            rr=json.loads(gzip.decompress(bodies[name]))
            if len(rr)!=1364 or any(r["arm"]!=arm for r in rr):raise ValueError("saved complete law-part scope differs")
            original_rows.extend(rr);part_refs.append(dict(refs[name],namespace="PRIMARY",arm=arm,rows=len(rr)))
        for index in [1,2,3]:
            event=json.loads(bodies[f"FIT_{index}_CONSUMED.json"])
            if event["attempt"]!=index or event["arm"]!=ARMS[index-1]:raise ValueError("preserved fit slot identity differs")
        put("CONSUMED_REMAINDER_EXECUTION.json",enc(dict(version=VERSION,UTC=now(),previous_fits_attempted=3,
            previous_fits_returned=3,remaining_new_fits=1,global_fit_slot=4,old_model_inference=0,old_model_refits=0)))
        put("PRIVATE_REMAINDER_PROTOCOL.json",STATE.pop("plan_raw"))
        STATE["phase"]="RESTORE_BASE_AND_SAVED_PROFILE_INPUTS"
        qbase=pd.read_parquet(io.BytesIO(bodies["QUERY_BASE_INPUTS_RECOVERED_V5.parquet"]))
        qpce=pd.read_parquet(io.BytesIO(bodies["QUERY_PROFILE_INPUTS_2026.parquet"]))
        for frame in [qbase,qpce]:
            for col in ["kickoff_utc","cutoff_utc"]:frame[col]=primary_runner.mixed_utc(frame[col],pd)
        q= qbase.merge(qpce,on=KEY+CTX,how="inner",validate="one_to_one",sort=False)
        if len(q)!=1364 or not q.position.eq("RB").all()or q.duplicated(KEY).any():raise ValueError("saved full query join differs")
        if (q.cutoff_utc>q.kickoff_utc).any()or(q.week.eq(8)&q.cutoff_utc.ge(q.kickoff_utc)).any():raise ValueError("saved query boundary scope differs")
        q.feature_max_source_available_utc=primary_runner.mixed_utc(q.feature_max_source_available_utc,pd)
        if (q.feature_max_source_available_utc>=q.cutoff_utc).any():raise ValueError("saved source is not strictly earlier")
        if any(c in q and q[c].notna().any()for c in ["actual","rush_yd","rush_att"]):raise ValueError("target labels entered saved query inference")
        data=old.load_inputs(pd);audit=old.audited_feature_binding(data)
        source_binding=json.loads(bodies["SOURCE_AND_PROFILE_BINDING.json"])
        if source_binding["audit"]!=audit or source_binding["pbp"]!=[old.safe(r)for r in data["pbp_refs"]]:raise ValueError("exact retained source/audit binding differs")
        train=increment.rb_training_population(data["train"])
        train=train.loc[train.season.lt(2026)&(primary_runner.mixed_utc(train.outcome_available_utc,pd)<pd.Timestamp("2026-09-01",tz="UTC"))].copy().reset_index(drop=True)
        if len(train)!=source_binding["RB_training_rows"]:raise ValueError("training admission differs")
        context=core.EfficiencyContext(data["frames"],data["history"])
        STATE["phase"]="REBUILD_TRAINING_FEATURES_ONLY"
        augmented,_=context.augment(train,rich=False)
        category=increment.arm_category(data["category"],"R3",modeled_roles=["RB"])
        store.reserve(plan["resources"]["model_reservation_bytes"])
        STATE["phase"]="FIT_GLOBAL_SLOT_4_R3";STATE["new_fits_attempted"]=1
        put("FIT_4_CONSUMED.json",enc(dict(arm=ARMS[3],attempt=4,UTC=now(),supplement_attempt=1,no_retry=True)))
        fit_cpu=time.process_time()
        try:
            with threadpool_limits(limits=2):model=cdf.LeafCDFModel.fit(augmented,category,"base")
        finally:STATE["new_fit_CPU_seconds"]=time.process_time()-fit_cpu
        STATE["new_fits_returned"]=1;STATE["pending_model"]=model
        buffer=io.BytesIO();joblib.dump(model,buffer,compress=("xz",3));STATE["pending_model_bytes"]=buffer.getvalue()
        model_ref=put("MODEL_2026_"+ARMS[3]+".joblib",buffer.getvalue());store.read(model_ref["id"],model_ref["sha256"],namespace="DEF_REMAINDER")
        STATE.pop("pending_model",None);STATE.pop("pending_model_bytes",None)
        if prior_fit_cpu+STATE["new_fit_CPU_seconds"]>1200:raise ValueError("returned state retained; unchanged cumulative1200CPU model limit exceeded")
        STATE["phase"]="INFER_ONLY_R3"
        rows=carry.cdf_forecasts(model,q.reset_index(drop=True),ARMS[3],np)
        tiers={tuple(getattr(r,k)for k in KEY):(r.query_clock_contract,r.query_evidence_tier)for r in q.itertuples()}
        for row in rows:
            contract,tier=tiers[tuple(row[k]for k in KEY)]
            row.update(target="rush_yd",point_semantics="EXACT_EMPIRICAL_LAW_MEAN_AND_LOWER_MEDIAN_SEPARATE_PRODUCTS",
                query_clock_contract=contract,query_evidence_tier=tier,conditioning="CONDITIONAL_ON_PLAYED",original_issued_UTC=None,
                probability_admission="UNVALIDATED_EXACT_LAW_NOT_CALIBRATED_CONFIDENCE",reconstruction="CURRENT_VINTAGE_SEVEN_DAY_POLICY_EXPOSED_HISTORY")
        forecast=put("FORECAST_2026_"+ARMS[3]+".json.gz",gzip.compress(enc(rows),mtime=0))
        part_refs.append(dict(forecast,arm=ARMS[3],rows=len(rows)));original_rows.extend(rows)
        manifest=dict(format="IMMUTABLE_ORDERED_PART_MANIFEST_V1",version=PRIMARY,arm_order=ARMS,parts=part_refs,
            rows=len(original_rows),logical_combined_sha256=sha(enc(original_rows)),namespace_contract="PRIMARY_AND_DEF_REMAINDER_NATIVE_V1",
            logical_codec="JSON_sorted_keys_compact_allow_nan_false_newline; concatenate decoded part arrays in arm_order")
        frozen=put("ALL_FORECAST_PART_MANIFEST_BEFORE_LABELS_COMPLETE_V1.json.gz",gzip.compress(enc(manifest),mtime=0))
        all_refs=[dict(refs[name],namespace="PRIMARY")for name in sorted(required)]+STATE["artifacts"]
        receipt=dict(version=PRIMARY,supplement_version=VERSION,state="FROZEN_FORECASTS_COMPLETE_UNSCORED",UTC=now(),
            fits_attempted=4,fits_returned=4,new_fits_this_supplement=1,reused_models_without_refit_or_inference=3,
            models={**{a:dict(refs[n],namespace="PRIMARY")for a,n in zip(ARMS[:3],models)},ARMS[3]:model_ref},
            forecasts=frozen,forecasts_format=manifest["format"],forecast_rows=len(original_rows),query_rows=len(q),
            artifacts=all_refs,source_and_profile_binding=source_binding,actual_weeks=sorted(map(int,q.week.unique())),
            scoring_state="NOT_SCORED_PINNED_C_EVALUATOR_SEPARATE_STAGE",storage=store.checkpoint(),
            resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,
                previous_model_fit_CPU_seconds=prior_fit_cpu,new_model_fit_CPU_seconds=STATE["new_fit_CPU_seconds"],
                cumulative_model_fit_CPU_seconds=prior_fit_cpu+STATE["new_fit_CPU_seconds"],RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
            counts=dict(new_fits=1,new_fitted_model_inference_arms=1,old_model_loads=0,old_model_inference=0,
                query_profile_rebuilds=0,defense_snapshot_rebuilds=0,source_HTTP=0,production_writes=0))
        put("COMPLETE_EXECUTION_RECEIPT.json",enc(receipt))
        with public_receipt.open("xb")as handle:handle.write(enc(receipt));handle.flush();os.fsync(handle.fileno())
        print(enc(receipt).decode(),flush=True)
    except BaseException as error:
        failure=dict(version=VERSION,state="FAILED_REMAINDER_RETAINED_NO_AUTOMATIC_REFIT",UTC=now(),phase=STATE["phase"],
            new_fits_attempted=STATE["new_fits_attempted"],new_fits_returned=STATE["new_fits_returned"],
            previous_model_fit_CPU_seconds=plan["previous_model_fit_CPU_seconds"],new_model_fit_CPU_seconds=STATE.get("new_fit_CPU_seconds",0.),
            CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,
            error_type=type(error).__name__,error_sha256=sha(str(error).encode()),artifacts=STATE["artifacts"])
        if STATE.get("pending_model")is not None:
            try:
                if STATE.get("pending_model_bytes")is None:
                    pending=io.BytesIO();joblib.dump(STATE["pending_model"],pending,compress=("xz",3));STATE["pending_model_bytes"]=pending.getvalue()
                put("RETURNED_R3_MODEL_FAILURE.joblib",STATE["pending_model_bytes"],failure=True)
            except BaseException as retained_error:failure["returned_model_retention_error_type"]=type(retained_error).__name__
        try:put("FAILURE_REMAINDER_PRIVATE.json",enc(dict(failure,traceback=traceback.format_exc())),failure=True)
        finally:print(enc(failure).decode(),flush=True)
        raise
    finally:signal.alarm(0)

def main():
    parser=argparse.ArgumentParser()
    for name in ["protocol","root-go","publication-receipt","public-receipt"]:parser.add_argument("--"+name,type=Path,required=True)
    for name in ["protocol-sha256","root-go-sha256","publication-receipt-sha256"]:parser.add_argument("--"+name,required=True)
    args=parser.parse_args();run(authorize(args),args.public_receipt)

if __name__=="__main__":main()
