"""One explicitly authorized, frozen two-base anytime-TD calibration wave.

No base estimator is refitted. Shared imports include estimator definitions.
The local shared Parquet loader,
exact identity contract and existing cluster bootstrap evaluator are reused.
Default invocation fails before row decoding unless a hash-bound root GO and
registered execution manifest are supplied. No preparation run opens NFL rows.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

START_WALL=time.monotonic()
for _thread_variable in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT","ARROW_IO_THREADS"):
    os.environ[_thread_variable]="2"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_anytime_calibration_startup import guarded_threads, libc_identity, StartupGuardError

# Keep the direct CLI stdlib-only until GO, offline/no-child guards and the
# mapped-libc resolver are established. The exact runtime contract is checked
# against the shared calibration module when it is imported under that guard.
VERSION="anytime-calibration-v1-20261025"
BASES=("fresh_cdf","catboost_medium")
METHODS=("intercept","platt","beta","isotonic")
KEYS=["season","week","game_id","player_id"]
CONTEXT=KEYS+["team","opponent","position","kickoff_utc","cutoff_utc"]


def load_runtime():
    global np,pd,Calibrator,align_context,binary_losses,paired,probabilities,summary,numeric,valid_support
    if "Calibrator" in globals():return
    import numpy as np
    import pandas as pd
    from nfl_lab import anytime_calibration as calibration
    from nfl_lab.cdf_engine import numeric,valid_support
    if (calibration.VERSION,calibration.BASES,calibration.METHODS,calibration.CONTEXT)!=(VERSION,BASES,METHODS,CONTEXT):
        raise StartupGuardError("calibration runtime contract differs")
    Calibrator,align_context,binary_losses,paired,probabilities,summary=(getattr(calibration,name) for name in
        ["Calibrator","align_context","binary_losses","paired","probabilities","summary"])

SOURCE_MANIFEST = "582f34f9c53c98c07a103ca3176f1d08333cb6351cd93cadcfbaf20a67e420d7"
APPROVED_FEATURES = "375dc79b4427db68504553736006af799ef98de880bd69ccb6f95285780a605f"
CATEGORY_CONTRACT = "9154f113d75b8b6af3cbc21e0c407e7af4b79b29e53a288d487a2dc868473de4"
YEARS = (2022, 2023, 2024)
ROLES = ("RB", "WR", "TE")
LIMITS = dict(CPU_seconds=120, wall_seconds=180, RSS_bytes=2147483648,
              address_space_bytes=8589934592, threads=2, retained_bytes=16777216,
              calibrator_calls=16, base_fits=0, HTTP=0)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_binding(value):
    path = Path(value["path"])
    if (not path.is_absolute() or not path.is_file() or any(p.is_symlink() for p in [path,*path.parents])
            or path.stat().st_size != value["bytes"] or sha(path) != value["sha256"]):
        raise ValueError("immutable source/code binding mismatch")
    return path


def clean(value):
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return {"numeric_state":"positive_infinity" if value > 0 else "negative_infinity" if value < 0 else "missing"}
    return value


def freeze_member(value, proof):
    """Authenticate the exact relative body in its immutable parent receipt."""
    path, parent = verify_binding(value), verify_binding(proof)
    receipt = json.loads(parent.read_text())
    try: relative = path.relative_to(parent.parent).as_posix()
    except ValueError as error: raise ValueError("source body outside parent freeze") from error
    if receipt.get("bindings",{}).get(relative) != value["sha256"]:
        raise ValueError("source body hash absent from parent freeze")
    return relative


def verify(manifest_path, expected_sha, go_path, go_sha):
    manifest_path, go_path = Path(manifest_path), Path(go_path)
    if sha(manifest_path) != expected_sha or sha(go_path) != go_sha:
        raise ValueError("manifest/GO SHA256 mismatch")
    manifest, go = json.loads(manifest_path.read_text()), json.loads(go_path.read_text())
    registration = json.loads(verify_binding(manifest["registration"]).read_text())
    if (go.get("state") != "ROOT_GO_SINGLE_ANYTIME_CALIBRATION" or go.get("manifest_sha256") != expected_sha
            or go.get("registration_sha256") != manifest["registration"]["sha256"]
            or registration.get("registration_id") != VERSION
            or registration.get("state") != "PRESPECIFIED_BEFORE_NEW_CALIBRATION_SCORES"
            or registration.get("resources") != LIMITS
            or registration.get("methods") != list(METHODS) or registration.get("bases") != list(BASES)
            or registration.get("horizons") != [{"calibration_years":[2022],"evaluation_year":2023},{"calibration_years":[2022,2023],"evaluation_year":2024}]
            or registration.get("automatic_retries") != 0 or registration.get("parameter_search") != 0):
        raise ValueError("registered single calibration GO required before NFL row decoding")
    for item in manifest["code"].values(): verify_binding(item)
    bound_paths = {str(Path(item["path"]).resolve()) for item in manifest["code"].values()}
    module = Path(__file__).resolve().parents[1] / "nfl_lab/anytime_calibration.py"
    startup = Path(__file__).resolve().parent / "check_anytime_calibration_startup.py"
    helper = Path(__file__).resolve().parent / "ngboost_law_software_v1.py"
    if (str(Path(__file__).resolve()) not in bound_paths or str(module) not in bound_paths
            or str(startup) not in bound_paths or str(helper) not in bound_paths):
        raise ValueError("exact runner/calibrator sources not frozen")
    if (verify_binding(manifest["thread_helper"])!=helper
            or manifest["thread_helper"]["sha256"]!="5ccfe3076530db21f92e3bf5abdb8f746f864aa9f95d3fad09dcccd2ec6cbe81"
            or manifest["libc"]["sha256"]!="9792e3cbb541c8f44c7acf5f14f4022ea62998ecc787d326bed4d8b6547dfd92"):
        raise ValueError("accepted thread helper/libc binding changed")
    libc_identity(manifest["libc"])
    equivalence = json.loads(verify_binding(manifest["approved_feature_equivalence"]).read_text())
    if (equivalence.get("feature_columns") != 97 or equivalence.get("all_values_exact") is not True
            or equivalence.get("source_identity_unchanged") is not True
            or equivalence.get("participation_probability") != "unavailable"):
        raise ValueError("approved97-feature unavailable play-rate source proof required")
    if set(manifest["contexts"]) != {str(year) for year in YEARS} or set(manifest["bases"]) != set(BASES):
        raise ValueError("exact three forecast years and two fixed bases required")
    for item in manifest["contexts"].values(): verify_binding(item)
    for name, base in manifest["bases"].items():
        if (base["source_manifest_sha256"] != SOURCE_MANIFEST
                or base["approved_features_sha256"] != APPROVED_FEATURES
                or base["category_contract_sha256"] != CATEGORY_CONTRACT
                or base["out_of_fit_training_max_year"] != {str(year):year-1 for year in YEARS}
                or set(base["years"]) != {str(year) for year in YEARS}
                or base["probability_column"] not in {"mean","probability"}):
            raise ValueError("unqualified fixed out-of-fit base source")
        if not {"forecast_freeze","scored_freeze","registration","execution_freeze"} <= set(base["proofs"]):
            raise ValueError("base registration, execution and forecast-freeze proofs required")
        for item in base["proofs"].values(): verify_binding(item)
        for year,packet in base["years"].items():
            forecast=freeze_member(packet["forecast"],base["proofs"]["forecast_freeze"])
            labels=freeze_member(packet["labels"],base["proofs"]["scored_freeze"])
            expected_forecast=f"{year}/anytime_td/leaf_cdf-forecast.parquet" if name=="fresh_cdf" else f"private/cells/{year}/anytime_td/direct_catboost_medium/forecast-frozen.parquet"
            expected_labels=f"{year}/anytime_td/leaf_cdf-scored.parquet" if name=="fresh_cdf" else f"private/scored/{year}/anytime_td/direct_catboost_medium.parquet"
            if (forecast,labels)!=(expected_forecast,expected_labels):raise ValueError("fixed anytime base source path differs")
            if name=="fresh_cdf" and freeze_member(manifest["contexts"][year],base["proofs"]["forecast_freeze"])!=f"{year}/anytime_td/query.parquet":
                raise ValueError("V2 anytime context not frozen with its base")
    return manifest, registration


class Run:
    def __init__(self, manifest, registration, manifest_sha, *, start=None, cpu_origin=None):
        load_runtime()
        self.m, self.registration, self.manifest_sha = manifest, registration, manifest_sha
        self.out = Path(manifest["output"])
        self.out.mkdir(mode=0o700, exist_ok=False)
        self.start = time.monotonic() if start is None else start
        self.cpu = time.process_time() if cpu_origin is None else cpu_origin
        self.calls, self.bindings, self.frames, self.contexts, self.labels = 0, {}, {}, {}, {}
        self.predictions = {}
        self.year_freezes = set()
        self.global_frozen = False

    def usage(self):
        return dict(CPU_seconds=time.process_time()-self.cpu, wall_seconds=time.monotonic()-self.start,
                    RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                    calibrator_calls=self.calls, base_fits=0, HTTP=0)

    def check(self):
        value = self.usage()
        if value["CPU_seconds"] >= 115 or value["wall_seconds"] >= 175 or value["RSS_bytes"] > LIMITS["RSS_bytes"] or self.calls > 16:
            raise RuntimeError("new finite calibration allocation exhausted")

    def save(self, relative, value, *, terminal=False):
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value,pd.DataFrame):
            buffer=io.BytesIO(); value.to_parquet(buffer,index=False,compression="zstd"); data=buffer.getvalue()
        else: data=(json.dumps(clean(value),indent=2,allow_nan=False)+"\n").encode()
        used=sum(p.stat().st_size for p in self.out.rglob("*") if p.is_file())
        # Full16MiB includes the external outer receipt. Keep its64KiB reserve
        # even for terminal writes; ordinary writes also reserve64KiB internally.
        ceiling=LIMITS["retained_bytes"]-65536-(0 if terminal else 65536)
        if used+len(data)>ceiling or (terminal and len(data)>65536): raise RuntimeError("calibration retention cap exhausted")
        with path.open("xb") as stream:
            os.chmod(path,0o600);stream.write(data);stream.flush();os.fsync(stream.fileno())
        descriptor=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
        self.bindings[relative]=sha(path)

    def load_forecasts(self):
        # The approved V2 context supplies availability metadata, never actualY.
        for year in YEARS:
            context=pd.read_parquet(verify_binding(self.m["contexts"][str(year)]),columns=CONTEXT+["outcome_available_utc"],use_threads=False)
            if not context.position.isin(ROLES).all() or not context.season.eq(year).all(): raise ValueError("wrong primary-role/year context")
            if context[KEYS].isna().any(axis=None) or context.duplicated(KEYS).any(): raise ValueError("invalid offered identity")
            if (pd.to_datetime(context.cutoff_utc,utc=True)>pd.to_datetime(context.kickoff_utc,utc=True)).any(): raise ValueError("query after kickoff")
            self.contexts[year]=context.reset_index(drop=True)
            for name in BASES:
                base=self.m["bases"][name]; packet=base["years"][str(year)]; col=base["probability_column"]
                value=pd.read_parquet(verify_binding(packet["forecast"]),columns=list(dict.fromkeys(CONTEXT+[col,"fallback"])),use_threads=False)
                # Original complete archives include other categories' roles;
                # the registered anytime category scope is RB/WR/TE only.
                value=value.loc[value.position.isin(ROLES)].copy()
                value=align_context(context,value)
                value["probability"]=probabilities(numeric(value,col));value["base_fallback"]=value.fallback.fillna("")
                self.frames[name,year]=value[CONTEXT+["probability","base_fallback"]].copy()
            self.check()

    def load_labels(self, year):
        if year >= 2023 and year not in self.year_freezes and not self.global_frozen:
            raise ValueError("labels cannot open before same-year candidate freeze")
        if year in self.labels:return self.labels[year]
        paired_labels=[]
        for name in BASES:
            binding=self.m["bases"][name]["years"][str(year)]["labels"]
            value=pd.read_parquet(verify_binding(binding),columns=CONTEXT+["actual","participation_state"],use_threads=False)
            value=value.loc[value.position.isin(ROLES)].copy();value=align_context(self.contexts[year],value)
            if not value.participation_state.isin(["played","DNP","unknown"]).all(): raise ValueError("invalid participation state")
            paired_labels.append(value)
        a,b=paired_labels
        if not a.participation_state.equals(b.participation_state) or not np.allclose(numeric(a,"actual"),numeric(b,"actual"),equal_nan=True,atol=0,rtol=0):
            raise ValueError("base outcome/participation source conflict")
        self.labels[year]=a[["actual","participation_state"]]
        return self.labels[year]

    def forecast(self, name, year, probability, reason=""):
        frame=self.frames[name,year].copy()
        frame["probability"]=probability
        frame["calibration_fallback"]=np.where(np.isnan(probability),"unsupported_base_probability",reason)
        return frame

    def run(self):
        self.load_forecasts()
        for evaluation_year in (2023,2024):
            cutoff=pd.to_datetime(self.contexts[evaluation_year].cutoff_utc,utc=True).min()
            ys=[];masks=[]
            train_years=list(range(2022,evaluation_year))
            for year in train_years:
                label=self.load_labels(year); actual=numeric(label,"actual")
                available=pd.to_datetime(self.contexts[year].outcome_available_utc,utc=True,errors="coerce")
                mask=label.participation_state.eq("played").to_numpy() & valid_support(actual,"bernoulli") & available.notna().to_numpy() & (available<cutoff).to_numpy()
                ys.append(actual);masks.append(mask)
            y=np.concatenate(ys);eligible=np.concatenate(masks)
            pooled=float((y[eligible].sum()+1)/(eligible.sum()+2))
            reference=self.frames[BASES[0],evaluation_year].copy();reference["probability"]=pooled
            reference["base_fallback"]="";reference["calibration_fallback"]=""
            self.predictions["pooled",evaluation_year]=reference
            self.save(f"{evaluation_year}/pooled-forecast.parquet",reference)
            self.save(f"{evaluation_year}/pooled-control.json",dict(probability=pooled,eligible_rows=int(eligible.sum()),training_years=train_years,prior="Beta(1,1)",cutoff_utc=cutoff.isoformat()))
            for name in BASES:
                base=self.forecast(name,evaluation_year,self.frames[name,evaluation_year].probability.to_numpy())
                self.predictions[name,evaluation_year]=base
                self.save(f"{evaluation_year}/{name}-base-forecast.parquet",base)
                p=np.concatenate([numeric(self.frames[name,year],"probability") for year in train_years])
                for method in METHODS:
                    self.check();self.calls+=1
                    prefix=f"{evaluation_year}/{name}/{method}"
                    self.save(prefix+"/attempt.json",dict(state="ATTEMPT_CONSUMED_BEFORE_FIT",number=self.calls,training_years=train_years,eligible_rows=int(eligible.sum()),cutoff_utc=cutoff.isoformat()))
                    model=Calibrator.fit(p[eligible],y[eligible],method)
                    self.save(prefix+"/calibrator.json",model.manifest())
                    prediction=self.forecast(name,evaluation_year,model.predict(numeric(base,"probability")),model.audit["reason"])
                    key=name+"__"+method;self.predictions[key,evaluation_year]=prediction
                    self.save(prefix+"/forecast.parquet",prediction);self.check()
            self.save(f"{evaluation_year}/forecast-freeze.json",dict(state="ALL_EIGHT_CALIBRATORS_AND_FORECASTS_FROZEN",bindings=dict(self.bindings),training_labels_opened=sorted(self.labels),evaluation_score_calls=0))
            self.year_freezes.add(evaluation_year)
        self.save("forecast-freeze.json",dict(state="ALL16_CALIBRATORS_AND_PREDICTIONS_FROZEN",bindings=dict(self.bindings),evaluation_score_calls=0,usage=self.usage()))
        for relative,digest in self.bindings.items():
            if sha(self.out/relative)!=digest:raise ValueError("frozen model/forecast changed before evaluation score")
        self.global_frozen=True
        scored={}
        for (method,year),value in self.predictions.items():
            label=self.load_labels(year);value=value.copy();value["actual"]=label.actual;value["participation_state"]=label.participation_state
            scored.setdefault(method,[]).append(value)
            self.save(f"scored/{year}/{method}.parquet",value)
        pooled={name:pd.concat(values,ignore_index=True) for name,values in scored.items()}
        comparisons=[];summaries={}
        for period in [2023,2024,"2023+2024"]:
            panel={name:value if isinstance(period,str) else value.loc[value.season.eq(period)].reset_index(drop=True) for name,value in pooled.items()}
            summaries[str(period)]={name:summary(value) for name,value in panel.items()}
            for base in BASES:
                for method in METHODS:
                    candidate=base+"__"+method
                    for control in [base,BASES[1] if base==BASES[0] else BASES[0],"pooled"]:
                        for metric in ["Brier","log_loss"]:
                            comparisons.append(dict(period=period,candidate=candidate,control=control,**paired(panel[candidate],panel[control],metric)))
            self.check()
        self.save("aggregate.json",dict(registration=VERSION,summary=summaries,comparisons=comparisons,
            interpretation="Prespecified exposed historical calibration diagnostics; no fresh confirmation, scientific qualification or production selection",usage=self.usage()))
        self.save("completion.json",dict(state="COMPLETED",bindings=dict(self.bindings),usage=self.usage(),manifest_sha256=self.manifest_sha),terminal=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("manifest");parser.add_argument("sha256");parser.add_argument("go");parser.add_argument("go_sha256");args=parser.parse_args()
    def offline(event,_args):
        if event.startswith("socket."):raise StartupGuardError("calibration forbids network")
        if event in {"subprocess.Popen","os.system","os.fork","os.forkpty","os.posix_spawn","os.exec","pty.spawn"}:
            raise StartupGuardError("calibration forbids child/process creation")
    sys.addaudithook(offline)
    manifest,registration=verify(args.manifest,args.sha256,args.go,args.go_sha256)
    class ResourceDeadline(BaseException): pass
    def deadline(*_):raise ResourceDeadline("calibration hard resource deadline")
    for sig in [signal.SIGTERM,signal.SIGALRM,signal.SIGXCPU]:signal.signal(sig,deadline)
    signal.alarm(175);resource.setrlimit(resource.RLIMIT_CPU,(115,120));resource.setrlimit(resource.RLIMIT_AS,(8589934592,8589934592))
    run=None
    try:
        import threadpoolctl
        with guarded_threads(threadpoolctl,manifest["libc"],manifest["thread_helper"]) as mapped_libc:
            run=Run(manifest,registration,args.sha256,start=START_WALL,cpu_origin=0.)
            run.save("startup-libc-proof.json",mapped_libc)
            with threadpoolctl.threadpool_limits(limits=2):run.run()
    except BaseException as error:
        if run is not None:
            run.save("terminal-failure.json",dict(state="FAILED_RETAINED",reason=type(error).__name__,detail=str(error)[:600],usage=run.usage(),bindings=run.bindings),terminal=True)
        raise
    finally:signal.alarm(0)


if __name__=="__main__":main()
