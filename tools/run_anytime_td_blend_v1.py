"""Inert blend adapter; stdlib until exact new review/GO and guarded startup."""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

VERSION="anytime-td-blend-v1-20261025"
START=time.monotonic()
RESOURCES=dict(CPU_seconds=60,wall_seconds=90,RSS_bytes=536870912,address_space_bytes=8589934592,
    threads=2,retained_bytes=2097152,weight_fit_attempts=2,base_fits=0,calibrator_calls=0,
    model_loads=0,base_inference_calls=0,HTTP=0,automatic_retries=0)


def sha(path):
    with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()


def pin(binding):
    path=Path(binding["path"])
    if (not path.is_file() or any(p.is_symlink() for p in (path,*path.parents))
            or path.stat().st_size!=binding["bytes"] or sha(path)!=binding["sha256"]):
        raise ValueError("changed exact metadata/source binding")
    return path


def module(binding,name):
    spec=importlib.util.spec_from_file_location(name,pin(binding))
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    return value


def verify(path,digest,go_path,go_digest):
    if sha(path)!=digest or sha(go_path)!=go_digest:raise ValueError("execution/GO changed")
    m=json.loads(Path(path).read_text());go=json.loads(Path(go_path).read_text())
    s=json.loads(pin(m["registration"]).read_text())
    if (s["registration_id"]!=VERSION or s["state"]!="PRESPECIFIED_BEFORE_NEW_BLEND_SCORES" or s["resources"]!=RESOURCES
            or s["bases"]!=["fresh_cdf","catboost_medium"]
            or s["arms"]!=["fixed_half","shrunk_brier"] or s["learned_weight"]["alpha"]!=.001
            or s["fixed_half"]!={"wCDF":.5,"wCat":.5} or s["controls"]!=["fresh_cdf","catboost_medium","pooled"]
            or s["horizons"]!=[{"training_years":[2022],"evaluation_year":2023},{"training_years":[2022,2023],"evaluation_year":2024}]
            or go.get("state")!="ROOT_GO_SINGLE_ANYTIME_TD_BLEND" or go.get("manifest_sha256")!=digest
            or go.get("registration_sha256")!=m["registration"]["sha256"]
            or go.get("actual_invocations")!=1 or go.get("automatic_retries")!=0
            or go.get("seal",{}).get("integrator")!="/root"):
        raise ValueError("exact new blend registration/root GO required before inputs")
    review=json.loads(pin(go["independent_review"]).read_text())
    if review.get("state")!="PASS_EXACT_ANYTIME_TD_BLEND_PREEXEC" or review.get("manifest_sha256")!=digest:
        raise ValueError("exact independent blend review required")
    for binding in m["code"].values():pin(binding)
    if m["parent_execution"]["sha256"]!="12b6de9ddddf5c83b53f3fc9e99b761d6a8a248860d9620b9d1f6d368e727edd":
        raise ValueError("exact accepted parent calibration execution required")
    parent_metadata=json.loads(pin(m["parent_execution"]).read_text())
    if (m["shared_runner"]!=parent_metadata["worker"]["script"] or m["thread_helper"]!=parent_metadata["thread_helper"]
            or m["libc"]!=parent_metadata["libc"] or m["parent_GO"]["path"]!=parent_metadata["root_go_path"]):
        raise ValueError("accepted original reader/startup/source lineage changed")
    if m["environment"]!=parent_metadata["environment"]:
        raise ValueError("accepted environment metadata changed")
    for name,version in m["environment"]["packages"].items():
        if importlib.metadata.version(name)!=version:raise ValueError("runtime package version changed")
    common=module(m["shared_runner"],"_accepted_original_anytime_calibration")
    parent,_=common.verify(m["parent_execution"]["path"],m["parent_execution"]["sha256"],
                           m["parent_GO"]["path"],m["parent_GO"]["sha256"])
    return m,s,parent,common


def make_run(common,blend):
    np,pd=common.np,common.pd
    class BlendRun(common.Run):
        def usage(self):
            return dict(CPU_seconds=time.process_time()-self.cpu,wall_seconds=time.monotonic()-self.start,
                RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                weight_fit_attempts=self.calls,base_fits=0,calibrator_calls=0,model_loads=0,base_inference_calls=0,HTTP=0)

        def check(self):
            u=self.usage()
            if u["CPU_seconds"]>=50 or u["wall_seconds"]>=80 or u["RSS_bytes"]>=520093696 or self.calls>2:
                raise RuntimeError("blend resource finalization reserve reached")

        def save(self,relative,value,*,terminal=False):
            # Delegate exclusive serialization/fsync/hash freezing to the same
            # accepted writer, with a stricter new2MiB preflight including both reserves.
            if isinstance(value,pd.DataFrame):
                buffer=common.io.BytesIO();value.to_parquet(buffer,index=False,compression="zstd");size=len(buffer.getvalue())
            else:size=len((json.dumps(common.clean(value),indent=2,allow_nan=False)+"\n").encode())
            used=sum(p.stat().st_size for p in self.out.rglob("*") if p.is_file())
            if used+size>2097152-65536-(0 if terminal else 65536) or terminal and size>65536:
                raise RuntimeError("blend2MiB retention reserve reached")
            return super().save(relative,value,terminal=terminal)

        def describe(self,rows):
            result=common.summary(rows)
            p,y=common.numeric(rows,"probability"),common.numeric(rows,"actual")
            good=rows.participation_state.eq("played").to_numpy() & common.valid_support(y,"bernoulli") & np.isfinite(p)
            error=p[good]-y[good]
            result.update(bias=float(error.mean()) if len(error) else None,
                          p95_absolute_error=float(np.quantile(np.abs(error),.95)) if len(error) else None)
            return result

        def contrast(self,a,b):
            b=common.align_context(a,b)
            if (not a.participation_state.reset_index(drop=True).equals(b.participation_state)
                    or not np.array_equal(common.numeric(a,"actual"),common.numeric(b,"actual"),equal_nan=True)):
                raise ValueError("blend paired outcome/participation mismatch")
            if not np.array_equal(np.isfinite(common.numeric(a,"probability")),np.isfinite(common.numeric(b,"probability"))):
                return dict(state="UNAVAILABLE",reason="forecast masks differ; intersection forbidden",
                    offered=len(a),all_offered_forecast_masks_equal=False,
                    candidate_forecasted=int(np.isfinite(common.numeric(a,"probability")).sum()),
                    control_forecasted=int(np.isfinite(common.numeric(b,"probability")).sum()))
            return dict(state="COMPLETED",all_offered_forecast_masks_equal=True,offered=len(a),
                Brier=common.paired(a,b,"Brier"),NLL=common.paired(a,b,"log_loss"))

        def run(self):
            self.save("CONSUMED.json",dict(state="SINGLE_BLEND_INVOCATION_CONSUMED",weight_fit_attempts=0,old_calibrations_refunded=False))
            self.load_forecasts()  # Exact original reader and identity/clock guard.
            coverage={}
            for year in common.YEARS:
                a,b=blend.components(common.numeric(self.frames["fresh_cdf",year],"probability"),
                                     common.numeric(self.frames["catboost_medium",year],"probability"))
                coverage[str(year)]=dict(offered=len(a),component_masks_equal=True,
                    both_available=int(np.isfinite(a).sum()),both_unavailable=int((~np.isfinite(a)).sum()),
                    cdf_base_fallback_offered=int(self.frames["fresh_cdf",year].base_fallback.ne("").sum()),
                    cat_base_fallback_offered=int(self.frames["catboost_medium",year].base_fallback.ne("").sum()))
            self.save("component-coverage-admission.json",coverage)
            self.save("factor-input-references.json",dict(contexts=self.m["contexts"],bases=self.m["bases"],
                ordering="ordinal is exact immutable context row order; original component files retain their fallback reasons",
                outcome="played-conditional rushing OR receiving touchdown"))
            for year in (2023,2024):
                cutoff=pd.to_datetime(self.contexts[year].cutoff_utc,utc=True).min()
                train=list(range(2022,year));ys=[];masks=[];clocks=[]
                for earlier in train:
                    label=self.load_labels(earlier);actual=common.numeric(label,"actual")
                    available=pd.to_datetime(self.contexts[earlier].outcome_available_utc,utc=True,errors="coerce")
                    masks.append(label.participation_state.eq("played").to_numpy() & common.valid_support(actual,"bernoulli")
                                 & available.notna().to_numpy() & (available<cutoff).to_numpy())
                    ys.append(actual)
                    clocks.append(dict(year=earlier,eligible_rows=int(masks[-1].sum()),
                        unknown_availability_rows=int(available.isna().sum()),
                        latest_eligible_availability=available.loc[masks[-1]].max().isoformat() if masks[-1].any() else None,
                        required_strictly_before=cutoff.isoformat()))
                y=np.concatenate(ys);eligible=np.concatenate(masks)
                rate=float((y[eligible].sum()+1)/(eligible.sum()+2))
                for base in common.BASES:
                    self.predictions[base,year]=self.forecast(base,year,common.numeric(self.frames[base,year],"probability"))
                reference=self.frames["fresh_cdf",year].copy();reference["probability"]=rate
                reference["base_fallback"]="";reference["calibration_fallback"]=""
                self.predictions["pooled",year]=reference
                a=np.concatenate([common.numeric(self.frames["fresh_cdf",earlier],"probability") for earlier in train])
                b=np.concatenate([common.numeric(self.frames["catboost_medium",earlier],"probability") for earlier in train])
                self.calls+=1
                self.save(f"{year}/weight-attempt.json",dict(state="ATTEMPT_CONSUMED_BEFORE_WEIGHT_FIT",number=self.calls,
                    training_years=train,eligible_rows=int(eligible.sum()),first_evaluation_cutoff=cutoff.isoformat()))
                weight=blend.Weight.fit(a[eligible],b[eligible],y[eligible])
                self.save(f"{year}/parameters.json",dict(learned=weight.manifest(),fixed_wCDF=.5,
                    pooled=rate,pooled_prior="Beta(1,1)",pooled_eligible_rows=int(eligible.sum()),training_years=train,
                    first_evaluation_cutoff=cutoff.isoformat(),training_clock_audit=clocks))
                cdf=common.numeric(self.frames["fresh_cdf",year],"probability")
                cat=common.numeric(self.frames["catboost_medium",year],"probability")
                for arm,w,reason in [("fixed_half",.5,""),("shrunk_brier",weight.wCDF,weight.audit["reason"])]:
                    value=self.forecast("fresh_cdf",year,blend.mixture(cdf,cat,w),reason)
                    value["base_fallback"]=np.where(self.frames["fresh_cdf",year].base_fallback.ne("") |
                        self.frames["catboost_medium",year].base_fallback.ne(""),"component_base_fallback","")
                    self.predictions[arm,year]=value
                    factor=pd.DataFrame(dict(ordinal=np.arange(len(value),dtype=np.int32),
                        probability=value.probability.to_numpy(),forecast_available=np.isfinite(value.probability.to_numpy()),
                        calibration_fallback=value.calibration_fallback.to_numpy()))
                    self.save(f"{year}/{arm}-probability-factor.parquet",factor)
                self.save(f"{year}/forecast-freeze.json",dict(state="BOTH_ARMS_WEIGHT_AND_FORECASTS_FROZEN",
                    bindings=dict(self.bindings),training_labels_opened=sorted(self.labels),evaluation_score_calls=0))
                self.year_freezes.add(year);self.check()
            self.save("forecast-freeze.json",dict(state="ALL_TWO_WEIGHTS_FOUR_FORECASTS_FROZEN",bindings=dict(self.bindings),training_labels_opened=sorted(self.labels),evaluation_score_calls=0))
            for relative,digest in self.bindings.items():
                if common.sha(self.out/relative)!=digest:raise ValueError("blend freeze changed before scoring")
            self.global_frozen=True;scored={}
            for (name,year),value in self.predictions.items():
                labels=self.load_labels(year);value=value.copy();value["actual"]=labels.actual
                value["participation_state"]=labels.participation_state;scored.setdefault(name,[]).append(value)
            pooled={name:pd.concat(values,ignore_index=True) for name,values in scored.items()}
            summaries={};comparisons=[]
            for period in [2023,2024,"2023+2024"]:
                panel={name:value if isinstance(period,str) else value.loc[value.season.eq(period)].reset_index(drop=True) for name,value in pooled.items()}
                # Pair authorization precedes every paired loss call; a differing
                # mask produces a complete unavailable cell, never an intersection.
                for arm in blend.ARMS:
                    for control in ["fresh_cdf","catboost_medium","pooled"]:
                        comparisons.append(dict(period=period,candidate=arm,control=control,**self.contrast(panel[arm],panel[control])))
                summaries[str(period)]={name:self.describe(value) for name,value in panel.items()};self.check()
            advances={}
            for arm in blend.ARMS:
                s=summaries["2023+2024"][arm];controls=[summaries["2023+2024"][c] for c in ["fresh_cdf","catboost_medium","pooled"]]
                complete=all(row["state"]=="COMPLETED" for row in comparisons if row["candidate"]==arm)
                advances[arm]=bool(complete and s["Brier"] is not None and s["log_loss_state"]=="finite"
                    and all(s["Brier"]<c["Brier"] for c in controls[:2])
                    and all(abs(s["bias"])<=abs(c["bias"]) and s["forecasted"]>=c["forecasted"] and s["scored"]>=c["scored"]
                        and (c["log_loss_state"]=="positive_infinity" or c["log_loss"] is not None and s["log_loss"]<=c["log_loss"]) for c in controls))
            if len(comparisons)!=18 or sum(isinstance(row["period"],str) for row in comparisons)!=6:
                raise RuntimeError("registered6pooled/12annual contrast inventory changed")
            self.save("aggregate.json",dict(registration=VERSION,summary=summaries,comparisons=comparisons,
                pooled_primary_contrasts=6,annual_primary_contrasts=12,descriptive_advance_only=advances,
                component_coverage=coverage,NLL_policy="Unclipped shared evaluator; positive infinity/undefined extended deltas retained explicitly",
                interpretation="All2022-2024exposed; no confirmation/SITE/R0/scientific qualification/nomination/automatic selection/deployment",
                usage=self.usage()))
            self.save("completion.json",dict(state="COMPLETED",bindings=dict(self.bindings),usage=self.usage(),manifest_sha256=self.manifest_sha),terminal=True)
    return BlendRun


def main():
    parser=argparse.ArgumentParser()
    for field in ["manifest","sha256","go","go_sha256"]:parser.add_argument(field)
    args=parser.parse_args()
    for name in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT","ARROW_IO_THREADS","VECLIB_MAXIMUM_THREADS"]:os.environ[name]="2"
    def guard(event,values):
        if event.startswith("socket.") or event in {"subprocess.Popen","os.system","os.fork","os.forkpty","os.posix_spawn","os.exec","pty.spawn","pickle.find_class"}:
            raise RuntimeError("blend offline/no-child/no-model guard")
        if event=="open" and values and isinstance(values[0],(str,bytes,os.PathLike)) and os.fsdecode(values[0]).endswith((".joblib",".pkl",".pickle",".npy",".npz")):
            raise RuntimeError("blend serialized-model decoding forbidden")
    sys.addaudithook(guard)
    def expired(*_):raise RuntimeError("blend deadline")
    for sig in [signal.SIGTERM,signal.SIGALRM,signal.SIGXCPU]:signal.signal(sig,expired)
    signal.alarm(85);resource.setrlimit(resource.RLIMIT_CPU,(55,60));resource.setrlimit(resource.RLIMIT_AS,(8589934592,8589934592))
    run=None
    try:
        manifest,registration,parent,common=verify(args.manifest,args.sha256,args.go,args.go_sha256)
        import threadpoolctl
        from unittest.mock import patch
        with common.guarded_threads(threadpoolctl,manifest["libc"],manifest["thread_helper"]):
            common.load_runtime();blend=module(manifest["blend_module"],"_frozen_anytime_td_blend")
            def forbidden(*a,**k):raise RuntimeError("old calibrator fitting forbidden in blend wave")
            effective=dict(parent,output=manifest["output"])
            run=make_run(common,blend)(effective,registration,args.sha256,start=START,cpu_origin=0.)
            with threadpoolctl.threadpool_limits(limits=2),patch.object(common.Calibrator,"fit",new=classmethod(forbidden)):
                run.run()
    except BaseException as error:
        if run is not None:run.save("terminal-failure.json",dict(state="FAILED_RETAINED",reason=type(error).__name__,detail=str(error)[:600],usage=run.usage(),bindings=run.bindings),terminal=True)
        raise
    finally:signal.alarm(0)


if __name__=="__main__":main()
