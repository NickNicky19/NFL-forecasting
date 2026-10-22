"""Bounded report replay from frozen trial rows. Never refits a model."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .evaluation import paired_week_interval,summarize


def _development_support(rows,good):
    """Order-independent compact support binding, computed during the group read."""
    keys=["season","game_id","player_id","target"]
    supported=rows.loc[good,keys+["actual"]].copy()
    # Normalize numerical outcomes so an integer and its equal float match.
    supported["actual"]=pd.to_numeric(supported["actual"],errors="raise").astype("float64")
    for name in ["game_id","player_id","target"]:supported[name]=supported[name].astype("string")
    supported["season"]=pd.to_numeric(supported["season"],errors="raise").astype("int64")
    hashed=pd.util.hash_pandas_object(supported,index=False).to_numpy(dtype="uint64")
    hashed.sort()
    return {"seasons":sorted(int(y) for y in rows.season.unique()),"scored_rows":len(supported),
            "duplicate_keys":int(rows.duplicated(keys,keep=False).sum()),
            "missing_keys":int(rows[keys].isna().any(axis=1).sum()),
            "scored_key_actual_sha256":hashlib.sha256(hashed.astype("<u8",copy=False).tobytes()).hexdigest(),
            "digest_semantics":"SHA256 of sorted pandas row hashes over season/game/player/target/float64 actual; not source authentication"}


def _development_eligibility(dev,methods,seasons):
    by_method={s["method"]:s for s in dev}
    methods=sorted(set(methods)|{"recent"})
    checks=[];pending=False;unfair=False
    baseline=by_method.get("recent",{}).get("development_support")
    for method in methods:
        support=by_method.get(method,{}).get("development_support")
        if support is None or support["seasons"]!=seasons:
            state="DEVELOPMENT_PENDING";pending=True
        elif support["duplicate_keys"] or support["missing_keys"]:
            state="INELIGIBLE_COVERAGE";unfair=True
        elif baseline is None or baseline["seasons"]!=seasons:
            state="DEVELOPMENT_PENDING";pending=True
        elif (baseline["duplicate_keys"] or baseline["missing_keys"] or
              support["scored_rows"]!=baseline["scored_rows"] or
              support["scored_key_actual_sha256"]!=baseline["scored_key_actual_sha256"]):
            state="INELIGIBLE_COVERAGE";unfair=True
        else:state="ELIGIBLE"
        checks.append({"method":method,"state":state,"available_seasons":support["seasons"] if support else []})
    return {"state":"DEVELOPMENT_PENDING" if pending else "INELIGIBLE_COVERAGE" if unfair else "ELIGIBLE",
            "planned_development_seasons":seasons,"development_eligibility":checks}


def finish_reports(output:Path):
    started=time.monotonic();output=Path(output)
    trials=json.loads((output/"trials.json").read_text())
    manifest_path=output/"manifest.json"
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    registration=manifest.get("registration",{})
    planned_seasons=sorted(set(registration.get("seasons",{}).get("development") or [2022,2023]))
    registered_methods=manifest.get("methods") or registration.get("candidate_families")
    combinations=sorted({(r["target"],r["method"]) for r in trials if r["state"]=="EVALUATED"})
    summaries=[];subgroups=[]
    for target,method in combinations:
        files=sorted(output.glob(f"????-{target}-{method}.parquet"))
        if not files:continue
        data=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
        for split,g in data.groupby("split"):
            summary={"split":split,"target":target,"method":method,**summarize(g)}
            summary["historical_scope"]="all supplied skill player-game rows; regular+postseason; no selected lines"
            good=g.participation_state.eq("played") & g.actual.notna() & g["mean"].notna()
            if split=="development":summary["development_support"]=_development_support(g,good)
            summaries.append(summary)
            work=g.copy();work["scored"]=good.astype(int);work["missing_stat"]=g.participation_state.eq("played")&g.actual.isna()
            work["dnp"]=g.participation_state.eq("DNP");work["unknown"]=g.participation_state.eq("unknown")
            work["fallback_used"]=g.fallback.fillna("").ne("")
            error=(g["mean"]-g.actual).where(good)
            work["ae"]=error.abs();work["se"]=error**2;work["error"]=error
            for dim in ["position","player_id","team","opponent"]:
                stats=work.groupby(dim,dropna=False).agg(population_rows=("scored","size"),scored_rows=("scored","sum"),mae=("ae","mean"),mse=("se","mean"),bias=("error","mean"),dnp=("dnp","sum"),unknown=("unknown","sum"),played_missing_statistic=("missing_stat","sum"),fallback_rows=("fallback_used","sum")).reset_index().rename(columns={dim:"value"})
                stats["rmse"]=np.sqrt(stats.pop("mse"));stats["dimension"]=dim
                stats["split"]=split;stats["target"]=target;stats["method"]=method
                stats["interpretation"]="exploratory_unshrunk; no tiny subgroup selection"
                subgroups.append(stats)
    (output/"summary.json").write_text(json.dumps(summaries,indent=2,allow_nan=False))
    if subgroups:pd.concat(subgroups,ignore_index=True).to_csv(output/"subgroups.csv",index=False)
    selected=[];paired=[];coherence=[]
    targets=sorted({s["target"] for s in summaries}|{r["target"] for r in trials})
    for target in targets:
        primary="brier" if target=="anytime_td" else "mae"
        def loss(s):return s.get("bernoulli",{}).get("brier") if primary=="brier" else s.get("mae")
        development=[s for s in summaries if s["split"]=="development" and s["target"]==target and s["method"] not in ["raw_sleeper","pinned_website"]]
        dev=[s for s in development if loss(s) is not None]
        if development and not any(s["supported_played_outcomes"] for s in development):
            selected.append({"target":target,"state":"NO_SUPPORTED_COMPARISON"});continue
        methods=registered_methods or {r["method"] for r in trials if r["target"]==target}
        methods=[m for m in methods if m not in ["raw_sleeper","pinned_website"]]
        eligibility=_development_eligibility(development,methods,planned_seasons)
        if eligibility["state"]!="ELIGIBLE":
            selected.append({"target":target,**eligibility});continue
        if not dev:selected.append({"target":target,"state":"NO_SUPPORTED_COMPARISON"});continue
        eligibility_details={k:v for k,v in eligibility.items() if k!="state"}
        chosen=min(dev,key=lambda s:(loss(s),s["method"]))["method"]
        base=next((s for s in summaries if s["split"]=="validation" and s["target"]==target and s["method"]=="recent"),None)
        candidate=next((s for s in summaries if s["split"]=="validation" and s["target"]==target and s["method"]==chosen),None)
        if base is None or candidate is None or loss(base) is None or loss(candidate) is None:
            selected.append({"target":target,"development_selected_method":chosen,"state":"VALIDATION_PENDING_OR_NOT_RUN",**eligibility_details});continue
        interval_rows=pd.concat([pd.read_parquet(p) for m in {"recent",chosen} for p in output.glob(f"2024-{target}-{m}.parquet")],ignore_index=True)
        interval=paired_week_interval(interval_rows,"recent",chosen)
        paired.append({"target":target,"method":chosen,**interval})
        relative=(loss(base)-loss(candidate))/loss(base) if loss(base)>0 else None
        selected.append({"target":target,"development_selected_method":chosen,"primary_metric":primary,"validation_recent":loss(base),"validation_candidate":loss(candidate),"relative_primary_gain":relative,"validation_recent_bias":base.get("bias"),"validation_candidate_bias":candidate.get("bias"),"bias_gate":abs(candidate.get("bias",0))<=abs(base.get("bias",0)),"coverage_unchanged":candidate["scored_rows"]==base["scored_rows"],"paired_n":interval["paired_n"],"weeks":interval["weeks"],"state":"EXPLORATORY_HISTORICAL_ONLY_CONFIRMATION_PENDING",**eligibility_details})
    for method in sorted({m for _,m in combinations}):
        a=output/f"2024-pass_att-{method}.parquet";b=output/f"2024-pass_cmp-{method}.parquet"
        if a.exists() and b.exists():
            keys=["game_id","player_id"]
            att=pd.read_parquet(a);cmp=pd.read_parquet(b)
            joined=att[keys+["mean","actual","participation_state"]].merge(cmp[keys+["mean","actual"]],on=keys,suffixes=("_att","_cmp"),validate="one_to_one")
            scored=joined.participation_state.eq("played")&joined.actual_att.notna()&joined.actual_cmp.notna()&joined.mean_att.notna()&joined.mean_cmp.notna()
            bad=(joined.mean_cmp>joined.mean_att+1e-10)&scored
            coherence.append({"method":method,"paired_scored_rows":int(scored.sum()),"completion_mean_exceeds_attempts":int(bad.sum()),"maximum_excess":float((joined.mean_cmp-joined.mean_att)[bad].max()) if bad.any() else 0,"joint_integration_state":"FAILED" if bad.any() else "NO_VIOLATION_IN_THIS_COHORT"})
    for name,obj in [("selected.json",selected),("paired.json",paired),("coherence.json",coherence)]:
        (output/name).write_text(json.dumps(obj,indent=2,allow_nan=False))
    rows=output/"rows.parquet"
    report={"trials":len(trials),"failed":sum(r["state"]=="FAILED" for r in trials),"rows_sha256":hashlib.file_digest(rows.open("rb"),"sha256").hexdigest() if rows.exists() else None,"reporting_seconds":time.monotonic()-started,"promoted":[],"confirmation":"PENDING_FUTURE_OUTCOMES","report_replay":"from unchanged trial rows; no fits repeated","warnings":"inspect trial warnings/logs; distributions are not established calibrated","historical_scope":"current-vintage; development2022-23,validation2024; includes postseason; allskill + separate role subgroups"}
    (output/"campaign.json").write_text(json.dumps(report,indent=2))
    return report
