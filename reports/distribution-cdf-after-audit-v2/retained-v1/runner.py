"""One finite, private, chronological NFL comparison; no production writes.

The public registration contains no private cache locators. An independently
frozen execution manifest binds those locators, source files and every module.
Original study artifacts and budgets are never reused as a new allocation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from threadpoolctl import threadpool_limits

from nfl_lab import cdf_engine as cdf
from nfl_lab.features import build_features, FEATURE_VERSION
from nfl_lab.role_boosting import RoleCountBoostingModel
from nfl_lab.threshold_cdf import ThresholdCDFModel, StableMixtureBatch, THRESHOLD_GRIDS

VERSION = "threshold-cdf-after-audit-v1-20261025"
METHODS = ("threshold_cdf", "leaf_cdf", "role_prior", "count_A_mean_v2")
META = cdf.KEYS + ["team", "opponent", "position", "kickoff_utc", "cutoff_utc",
    "outcome_available_utc", "feature_max_source_available_utc"]
PREDICTIONS = ["mean", "median", "p10", "p90", "variance", "mass_zero"]
SCORES = ["crps", "log_score", "brier", "cdf_actual_below", "cdf_actual"]


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.ndarray,)):
        return clean(x.tolist())
    if isinstance(x, np.generic):
        return clean(x.item())
    if isinstance(x, float) and not np.isfinite(x):
        return {"numeric_state": "positive_infinity" if x > 0 else "negative_infinity" if x < 0 else "missing"}
    return x


def count_mean(model, query):
    """Separate expected-mean adapter; never modify frozen model.predict()."""
    point, reasons = model.predict(query)
    point = np.asarray(point).copy()
    for i in np.flatnonzero(reasons != ""):
        prior = model.priors.get(str(query.iloc[i].position), model.global_prior)
        if prior is not None:
            if prior.support != "count" or not np.isfinite(prior.mean) or prior.mean < 0:
                raise ValueError("invalid supported count mean prior")
            point[i] = prior.mean
    return point, reasons


def laws(model, query, *, prior_only=False):
    for idx, law, reason in model.predict_batches(query, batch_size=128, prior_only=prior_only):
        if law is not None:
            law = StableMixtureBatch(law.support, law.weights, law.prior, prior_weight=law.b)
        yield idx, law, reason


def infer(model, query, *, count=False, prior_only=False, label=None):
    result = query[META].copy().reset_index(drop=True)
    for name in PREDICTIONS + SCORES:
        result[name] = np.nan
    result["fallback"] = "no_supported_played_training_outcomes"
    if count:
        result["mean"], result["fallback"] = count_mean(model, query)
        return result
    for idx, law, reason in laws(model, query, prior_only=prior_only):
        result.loc[idx, "fallback"] = reason
        if law is None:
            continue
        for name, vals in [("mean", law.mean), ("median", law.quantile(.5)),
                ("p10", law.quantile(.1)), ("p90", law.quantile(.9)),
                ("variance", law.variance), ("mass_zero", np.exp(law.logpmf(np.zeros(len(idx)))) )]:
            result.loc[idx, name] = vals
        if label is not None:
            actual = cdf.numeric(label.iloc[idx], "actual")
            good = label.iloc[idx].participation_state.eq("played").to_numpy() & cdf.valid_support(actual, model.category["support"])
            if good.any():
                selected = idx[good]
                scored = StableMixtureBatch(law.support, law.weights[good], law.prior, prior_weight=law.b)
                y = actual[good]
                values = {"crps": scored.crps(y), "log_score": -scored.logpmf(y),
                    "cdf_actual_below": scored.cdf(y-1), "cdf_actual": scored.cdf(y)}
                if model.category["support"] == "bernoulli":
                    values["brier"] = (scored.mean-y)**2
                for name, vals in values.items():
                    result.loc[selected, name] = vals
    return result


def loss_summary(rows, support):
    actual = cdf.numeric(rows, "actual")
    valid = rows.participation_state.eq("played").to_numpy() & cdf.valid_support(actual, support)
    out = {"offered_rows": len(rows), "supported_played": int(valid.sum()),
        "unknown_participation": int(rows.participation_state.eq("unknown").sum()),
        "DNP": int(rows.participation_state.eq("DNP").sum()),
        "played_missing_stat": int((rows.participation_state.eq("played") & ~np.isfinite(actual)).sum()),
        "played_invalid_stat": int((rows.participation_state.eq("played") & np.isfinite(actual) & ~cdf.valid_support(actual,support)).sum()),
        "played_zero": int((valid & (actual==0)).sum()),
        "fallback_offered": int(rows.fallback.ne("").sum()),
        "forecasted": int(np.isfinite(rows["mean"]).sum()),
        "games": rows.loc[valid,"game_id"].nunique(),
        "weeks": len(rows.loc[valid,["season","week"]].drop_duplicates()),
        "players": rows.loc[valid,"player_id"].nunique()}
    for point in ["mean", "median"]:
        good = valid & np.isfinite(rows[point])
        error = rows.loc[good,point].to_numpy()-actual[good]
        out[point] = {"n": int(good.sum()), "MAE": float(np.abs(error).mean()) if len(error) else None,
            "MSE": float((error**2).mean()) if len(error) else None,
            "RMSE": float(np.sqrt((error**2).mean())) if len(error) else None,
            "bias": float(error.mean()) if len(error) else None,
            "p95_absolute_error": float(np.quantile(np.abs(error),.95)) if len(error) else None}
    good = valid & np.isfinite(rows.crps)
    if good.any():
        g=rows.loc[good]; y=actual[good]; lo=g.p10.to_numpy(); hi=g.p90.to_numpy()
        log=g.log_score.to_numpy()
        out["distribution"]={"n":len(g),"CRPS":float(g.crps.mean()),
            "Brier":float(g.brier.mean()) if support=="bernoulli" else None,
            "log_score":float(log.mean()) if np.isfinite(log).all() else None,
            "positive_infinite_log_losses":int(np.isposinf(log).sum()),
            "log_score_state":"infinite" if np.isposinf(log).any() else "finite",
            "coverage80":float(np.mean((y>=lo)&(y<=hi))),"width80":float(np.mean(hi-lo)),
            "interval_score80":float(np.mean(hi-lo+10*np.maximum(lo-y,0)+10*np.maximum(y-hi,0))),
            "mean_zero_mass":float(g.mass_zero.mean()),"below10":float(np.mean(y<lo)),"above90":float(np.mean(y>hi))}
        if support=="bernoulli":
            bins=[]
            for i in range(10):
                mask=(g["mean"]>=i/10)&((g["mean"]<(i+1)/10) if i<9 else (g["mean"]<=1))
                q=g.loc[mask]
                bins.append({"lo":i/10,"hi":(i+1)/10,"n":len(q),"p":q["mean"].mean() if len(q) else None,"event_rate":q.actual.mean() if len(q) else None})
            out["reliability_fixed_tenths"]=bins
    return clean(out)


def paired(a, b, metric, support, point="mean"):
    if not a[cdf.KEYS].equals(b[cdf.KEYS]) or not a.participation_state.equals(b.participation_state) or not np.allclose(a.actual,b.actual,equal_nan=True,atol=0,rtol=0):
        raise ValueError("paired population or outcome mismatch")
    valid=a.participation_state.eq("played").to_numpy() & cdf.valid_support(cdf.numeric(a,"actual"),support)
    if metric in ("MAE","MSE"):
        x=np.abs(a[point].to_numpy()-a.actual.to_numpy());y=np.abs(b[point].to_numpy()-b.actual.to_numpy())
        if metric=="MSE":x=x*x;y=y*y
    else:x=a[metric].to_numpy();y=b[metric].to_numpy()
    good=valid & ~np.isnan(x) & ~np.isnan(y)
    if np.isneginf(x[good]).any() or np.isneginf(y[good]).any():raise ValueError("negative infinite loss")
    p=a.loc[good,cdf.KEYS].copy(); x=x[good];y=y[good]
    out={"metric":metric,"point":point if metric in ("MAE","MSE") else None,"n":len(p),"games":p.game_id.nunique(),"weeks":len(p[["season","week"]].drop_duplicates()),"candidate_loss":float(x.mean()) if len(x) else None,"control_loss":float(y.mean()) if len(y) else None,"candidate_infinite":int(np.isposinf(x).sum()),"control_infinite":int(np.isposinf(y).sum()),"intervals":{}}
    if not len(x) or np.isinf(x).any() or np.isinf(y).any():
        out.update(delta=None,relative_gain_pct=None,state="undefined_both_infinite" if np.isposinf(x).any() and np.isposinf(y).any() else "positive_infinity" if np.isposinf(x).any() else "negative_infinity" if np.isposinf(y).any() else "unavailable");return clean(out)
    d=x-y;out.update(delta=float(d.mean()),relative_gain_pct=float(100*(y.mean()-x.mean())/y.mean()) if y.mean()!=0 else None,state="finite")
    p["delta"]=d
    for kind,keys,seed in [("week",["season","week"],1911),("game",["season","game_id"],1912)]:
        group=p.groupby(keys).delta.agg(["sum","count"])
        if len(group)<8:out["intervals"][kind]=None;continue
        draw=np.random.Generator(np.random.PCG64(seed)).integers(0,len(group),(500,len(group)))
        samples=group["sum"].to_numpy()[draw].sum(axis=1)/group["count"].to_numpy()[draw].sum(axis=1)
        out["intervals"][kind] = np.quantile(samples,[.025,.975],method="linear").tolist()
    return clean(out)


class Run:
    def __init__(self, manifest, manifest_sha):
        if sha(manifest)!=manifest_sha:raise ValueError("execution manifest mismatch")
        self.m=json.loads(Path(manifest).read_text());self.s=json.loads(Path(self.m["registration"]["path"]).read_text())
        for binding in [self.m["registration"],*self.m["inputs"].values(),*self.m["code"].values()]:
            p=Path(binding["path"])
            if p.is_symlink() or not p.is_file() or sha(p)!=binding["sha256"]:raise ValueError("changed input/code binding")
        if self.s["registration_id"]!=VERSION:raise ValueError("wrong registration")
        self.out=Path(self.m["output"]);self.out.mkdir(mode=0o700,exist_ok=False)
        self.start=time.monotonic();self.cpu=time.process_time();self.fits=0;self.query_rows=0;self.expanded=0;self.bindings={};self.slots=[]
        self.limits=self.s["resources"]

    def check(self, *, fit=False, rows=0, expanded=0, final=False):
        self.fits+=int(fit);self.query_rows+=rows;self.expanded+=expanded
        reserve=0 if final else self.limits["finalization_reserve_seconds"]
        if self.fits>84 or self.query_rows>self.limits["maximum_forecast_or_score_query_rows"] or self.expanded>self.limits["maximum_expanded_fit_rows"] or time.monotonic()-self.start>self.limits["maximum_wall_seconds"]-reserve or time.process_time()-self.cpu>self.limits["maximum_CPU_seconds"]-reserve or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>self.limits["maximum_RSS_bytes"]:raise RuntimeError("finite wave budget exhausted")

    def save(self, relative, value):
        path=self.out/relative;path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():raise ValueError("immutable output already exists")
        if isinstance(value,pd.DataFrame):
            value=value.copy();value.attrs.clear();buffer=io.BytesIO();value.to_parquet(buffer,index=False,compression="zstd");body=buffer.getvalue()
        elif relative.endswith(".joblib"):
            buffer=io.BytesIO();joblib.dump(value,buffer,compress=3);body=buffer.getvalue()
        else:body=(json.dumps(clean(value),indent=2,allow_nan=False)+"\n").encode()
        terminal=relative=="terminal-failure.json"
        ceiling=self.limits["maximum_new_retained_bytes"]-65536-(0 if terminal else 262144)
        if (terminal and len(body)>262144) or sum(x.stat().st_size for x in self.out.rglob("*") if x.is_file())+len(body)>ceiling:raise RuntimeError("private retention budget exhausted before write")
        with path.open("xb") as f:
            os.chmod(path,0o600);f.write(body);f.flush();os.fsync(f.fileno())
        if sha(path)!=hashlib.sha256(body).hexdigest():raise ValueError("durable artifact readback mismatch")
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.bindings[relative]=sha(path)

    def usage(self):
        return {"CPU_seconds":time.process_time()-self.cpu,"wall_seconds":time.monotonic()-self.start,"RSS_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,"fit_calls":self.fits,"expanded_fit_rows":self.expanded,"query_rows":self.query_rows,"retained_bytes":sum(x.stat().st_size for x in self.out.rglob("*") if x.is_file())}

    def run(self):
        history=self.m["inputs"]["history"]
        source_manifest=json.loads(Path(self.m["inputs"]["source_manifest"]["path"]).read_text())
        if source_manifest["artifact_sha256s"]["processed/history.parquet"]!=history["sha256"]:raise ValueError("unqualified history source")
        if self.m["inputs"]["source_manifest"]["sha256"]!=self.s["source_manifest_sha256"] or self.m["inputs"]["categories"]["sha256"]!=self.s["category_contract_sha256"] or self.m["inputs"]["source_policy"]["sha256"]!=source_manifest["policy_sha256"]:raise ValueError("source/policy/category identity mismatch before decode")
        categories=json.loads(Path(self.m["inputs"]["categories"]["path"]).read_text())["categories"]
        if categories["fantasy_ppr"]["state"]=="READY":raise ValueError("PPR must remain blocked")
        table=ds.dataset(history["path"],format="parquet")
        columns=[c for c in table.schema.names if c not in ("fantasy_ppr","fantasy_ppr_missing_reason") and not c.startswith("f_")]
        predicate=(ds.field("season")>=2019)&(ds.field("season")<=2024)
        for kind in ["season_type","game_type"]:
            if kind in columns:predicate &= ds.field(kind)=="REG"
        raw=table.to_table(columns=columns,filter=predicate).to_pandas()
        if not raw.season.between(2019,2024).all():raise ValueError("protected season decoded")
        schedule_binding=self.m["inputs"]["schedule"]
        if source_manifest["artifact_sha256s"]["raw/schedules.csv"]!=schedule_binding["sha256"]:raise ValueError("schedule source mismatch")
        schedule=pd.read_csv(schedule_binding["path"],usecols=["game_id","season","week","game_type"])
        regular=schedule.loc[schedule.season.between(2019,2024)&schedule.game_type.eq("REG"),["season","week","game_id"]].drop_duplicates()
        offered=raw[["season","week","game_id"]].drop_duplicates().merge(regular,on=["season","week","game_id"],how="left",indicator=True,validate="one_to_one")
        if not offered._merge.eq("both").all():raise ValueError("nonregular or unknown scheduled game")
        frame=build_features(raw);cdf.assert_clock_contract(frame)
        for target,cat in categories.items():
            if cat["state"]=="READY":cdf.assert_composite_contract(frame,{**cat,"target":target})
        history_n=cdf.numeric(frame,"f_player_games_prior")
        if not (np.isfinite(history_n).all() and (history_n==np.floor(history_n)).all() and (history_n>=0).all()):raise ValueError("history games must be nonnegative integers")
        self.save("corrected-features.parquet",frame)
        self.save("feature-preparation.json",{"version":FEATURE_VERSION,"rows":len(frame),"seasons":sorted(frame.season.unique()),"profile":frame.attrs.get("feature_profile"),"participation":raw.participation_state.value_counts().to_dict(),"source_availability_lane":"current vintage reconstructed kickoff+7d, not genuine historical publication"})
        frames={};catalog=[]
        for year in self.s["years"]:
            train,test=cdf.chronological_split(frame,year)
            for target,cat in categories.items():
                if cat["state"]!="READY":continue
                category={**cat,"target":target};testrole=test.loc[test.position.isin(cat["primary_roles"])].copy().reset_index(drop=True)
                query=testrole[[c for c in frame if c in META or c.startswith("f_")]].copy()
                if target in query or "participation_state" in query:raise AssertionError("query contains label/participation")
                prefix=f"{year}/{target}";self.save(prefix+"/query.parquet",query);frames[(year,target)]=(query,testrole)
                for method in ["leaf_cdf","threshold_cdf"]+(["count_A_mean_v2"] if cat["support"]=="count" else []):
                    modeled=train.participation_state.eq("played").to_numpy() & train.position.isin(cat["modeled_roles"]).to_numpy() & cdf.valid_support(cdf.numeric(train,target),cat["support"])
                    self.check(fit=True,expanded=int(modeled.sum())*len(THRESHOLD_GRIDS.get(target,[0])) if method=="threshold_cdf" else 0)
                    slot={"year":year,"target":target,"method":method,"started_at":now(),"state":"ATTEMPTED"};self.slots.append(slot)
                    self.save(prefix+f"/{method}-attempt-consumed.json",{**slot,"state":"ATTEMPT_CONSUMED_BEFORE_FIT","usage":self.usage(),"automatic_retries":0})
                    try:
                        if method=="leaf_cdf":model=cdf.LeafCDFModel.fit(train,category,"base")
                        elif method=="threshold_cdf":model=ThresholdCDFModel.fit(train,category,"base")
                        else:model=RoleCountBoostingModel.fit(train,category,"A")
                        self.save(prefix+f"/{method}.joblib",model)
                        self.save(prefix+f"/{method}-audit.json",{"fitted_model_audit":model.audit,"effective_inference_procedure":method,"feature_version":FEATURE_VERSION,"count_fallback_version":"count-a-prior-mean-fallback-v2-20261025" if method=="count_A_mean_v2" else None,"law_version":StableMixtureBatch.version if method!="count_A_mean_v2" else None})
                        self.check(rows=len(query));prediction=infer(model,query,count=method=="count_A_mean_v2")
                        self.save(prefix+f"/{method}-forecast.parquet",prediction)
                        catalog.append({**slot,"state":"FROZEN","prefix":prefix})
                        if method=="leaf_cdf":
                            self.check(rows=len(query));self.save(prefix+"/role_prior-forecast.parquet",infer(model,query,prior_only=True))
                            catalog.append({"year":year,"target":target,"method":"role_prior","state":"FROZEN","prefix":prefix})
                        slot.update(state="FROZEN",completed_at=now())
                    except Exception as error:
                        slot.update(state="FAILED_RETAINED",exception=type(error).__name__,reason=str(error)[:500],completed_at=now());self.save(prefix+f"/{method}-failure.json",slot)
                    print(json.dumps({"year":year,"target":target,"method":method,"state":slot["state"],"usage":self.usage()}),flush=True)
        self.save("forecast-freeze.json",{"frozen_at":now(),"bindings":dict(self.bindings),"slots":self.slots,"catalog":catalog,"usage":self.usage()})
        scores={};summary={};coverage=[];weekly_coverage=[];strata=[]
        for entry in catalog:
            year,target,method,prefix=(entry[k] for k in ("year","target","method","prefix"));query,label=frames[(year,target)];self.check(rows=len(query))
            for relative in [prefix+"/query.parquet",prefix+f"/{method}-forecast.parquet"]:
                if sha(self.out/relative)!=self.bindings[relative]:raise ValueError("frozen query/forecast bytes changed")
            path=self.out/(prefix+f"/{'leaf_cdf' if method=='role_prior' else method}.joblib")
            if sha(path)!=self.bindings[str(path.relative_to(self.out))]:raise ValueError("model artifact changed before score")
            model=joblib.load(path)
            actual=label[[*cdf.KEYS,"participation_state",target]].rename(columns={target:"actual"}).reset_index(drop=True)
            value=infer(model,query,count=method=="count_A_mean_v2",prior_only=method=="role_prior",label=actual)
            frozen=pd.read_parquet(self.out/(prefix+f"/{method}-forecast.parquet"))
            if not value[META].equals(frozen[META]) or not np.array_equal(value[PREDICTIONS].to_numpy(),frozen[PREDICTIONS].to_numpy(),equal_nan=True) or not value.fallback.equals(frozen.fallback):raise ValueError("forecast/score replay differs")
            value["actual"]=actual.actual;value["participation_state"]=actual.participation_state
            self.save(prefix+f"/{method}-scored.parquet",value)
            scores.setdefault((target,method),[]).append(value)
            coverage.append({"year":year,"target":target,"method":method,**loss_summary(value,model.category["support"])})
            for week,g in value.groupby("week",sort=True):
                weekly_coverage.append({"year":year,"week":int(week),"target":target,"method":method,**loss_summary(g,model.category["support"])})
        comparisons=[]
        for target,cat in categories.items():
            if cat["state"]!="READY":summary[target]={"state":cat["state"]};continue
            methods={m:pd.concat(scores[(target,m)],ignore_index=True) for m in METHODS if (target,m) in scores}
            summary[target]={"state":"RESEARCH_SCORED" if "threshold_cdf" in methods else "FAILED_OR_UNAVAILABLE","methods":{m:loss_summary(f,cat["support"]) for m,f in methods.items()},"historical_SITE_raw_R0":"UNAVAILABLE"}
            for method,f in methods.items():
                # Private audit rows preserve heterogeneous player/team/opponent/category effects.
                for dimension in ["player_id","team","opponent","week"]:
                    for key,g in f.groupby(dimension,dropna=False):strata.append({"target":target,"method":method,"dimension":dimension,"key":str(key),**loss_summary(g,cat["support"])})
            if "threshold_cdf" not in methods:continue
            for control in ["leaf_cdf","role_prior","count_A_mean_v2"]:
                if control not in methods:continue
                a,b=methods["threshold_cdf"],methods[control]
                # Incomplete target/year pairs are compared only on explicit common annual packets.
                years=sorted(set(a.season)&set(b.season));a=a.loc[a.season.isin(years)].reset_index(drop=True);b=b.loc[b.season.isin(years)].reset_index(drop=True)
                metrics=[("MSE","mean"),("MAE","median")]+([] if control=="count_A_mean_v2" else [("brier" if cat["support"]=="bernoulli" else "crps","mean"),("log_score","mean")])
                for metric,point in metrics:
                    if control=="count_A_mean_v2" and metric=="MAE":continue
                    comparisons.append({"target":target,"candidate":"threshold_cdf","control":control,"years":years,**paired(a,b,metric,cat["support"],point)})
        self.save("aggregate.json",{"registration":VERSION,"source_repairs":[FEATURE_VERSION,"paired-distribution-interval-v2-20261025","count-a-prior-mean-fallback-v2-20261025"],"categories":summary,"comparisons":comparisons,"usage":self.usage(),"decisions":"Research only; no website-relative or prospective qualification; failure/secondary gates must be independently reviewed"})
        self.save("coverage.json",coverage);self.save("coverage-by-week.json",weekly_coverage);self.save("private-strata.json",strata)
        self.save("completion.json",{"state":"COMPLETED_WITH_SLOT_FAILURES" if any(s["state"]!="FROZEN" for s in self.slots) else "COMPLETED","completed_at":now(),"bindings":dict(self.bindings),"usage":self.usage(),"slots":self.slots})


def main():
    def no_network(event,args):
        if event=="socket.connect":raise RuntimeError("study forbids network acquisition")
    sys.addaudithook(no_network)
    p=argparse.ArgumentParser();p.add_argument("manifest");p.add_argument("sha256");args=p.parse_args();run=Run(args.manifest,args.sha256)
    def deadline(*_):raise RuntimeError("finite hard resource deadline")
    signal.signal(signal.SIGTERM,deadline);signal.signal(signal.SIGALRM,deadline);signal.alarm(1450)
    signal.signal(signal.SIGXCPU,deadline);resource.setrlimit(resource.RLIMIT_CPU,(1150,1200));resource.setrlimit(resource.RLIMIT_AS,(8589934592,8589934592))
    try:
        with threadpool_limits(limits=2):run.run()
    except BaseException as error:
        run.save("terminal-failure.json",{"state":"FAILED_RETAINED","at":now(),"exception":type(error).__name__,"reason":str(error)[:800],"usage":run.usage(),"slots":run.slots,"bindings":dict(run.bindings)})
        raise
    finally:signal.alarm(0)


if __name__=="__main__":main()
