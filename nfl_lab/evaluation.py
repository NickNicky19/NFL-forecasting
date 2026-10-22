"""Chronological comparisons. Historical current-vintage scores are descriptive."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def probability_scores(y, mean, scale, family):
    """Proper scores for a declared conditional distribution; no probability clipping."""
    y, m, s = map(lambda a: np.asarray(a, dtype=float), (y, mean, scale))
    if family == "bernoulli":
        if np.any((m < 0) | (m > 1) | ~np.isin(y, [0, 1])):
            raise ValueError("invalid Bernoulli evidence")
        mass = np.where(y == 1, m, 1-m)
        with np.errstate(divide="ignore"):
            loss = -np.log(mass)
        return {"brier": float(np.mean((m-y)**2)),
                "log_score": float(np.mean(loss)) if np.isfinite(loss).all() else None,
                "infinite_log_losses": int(np.isinf(loss).sum()),
                "crps": float(np.mean((m-y)**2))}
    if np.any(s <= 0) or not np.isfinite(s).all():
        raise ValueError("invalid distribution standard deviation")
    if family == "normal":
        z = (y-m)/s
        crps = s*(z*(2*stats.norm.cdf(z)-1)+2*stats.norm.pdf(z)-1/np.sqrt(np.pi))
        log = -stats.norm.logpdf(y, loc=m, scale=s)
        low, high = stats.norm.ppf(.1, loc=m, scale=s), stats.norm.ppf(.9, loc=m, scale=s)
        return {"crps": float(crps.mean()), "log_score": float(log.mean()),
                "interval_80_coverage": float(np.mean((y >= low) & (y <= high))),
                "lower_tail_frequency": float(np.mean(y < low)),
                "upper_tail_frequency": float(np.mean(y > high)), "push_mass": 0.0,
                "push_mass_semantics": "continuous_distribution_only; integer-yard discretization not supplied"}
    if family != "negbin" or np.any(y < 0) or np.any(y != np.floor(y)) or np.any(m < 0):
        raise ValueError("unsupported count distribution")
    vari = np.maximum(s*s, m)
    over = vari > m+1e-8
    r = np.where(over, np.maximum(m*m/np.maximum(vari-m, 1e-12), 1e-12), 1)
    p = r/(r+m)
    def cdf(k):
        return np.where(over, stats.nbinom.cdf(k, r, p), stats.poisson.cdf(k, m))
    log = -np.where(over, stats.nbinom.logpmf(y, r, p), stats.poisson.logpmf(y, m))
    # Discrete CRPS = sum over integer thresholds of squared CDF error.
    upper = np.maximum(np.ceil(y), np.where(over, stats.nbinom.ppf(1-1e-8,r,p),stats.poisson.ppf(1-1e-8,m)))
    cap = int(np.max(upper)) if len(upper) else 0
    if cap > 10000:
        raise ValueError("count distribution exceeds numerical budget")
    crps = np.zeros_like(y)
    for k in range(cap+1):
        crps += (cdf(k)-(y <= k))**2
    lo = np.where(over, stats.nbinom.ppf(.1,r,p),stats.poisson.ppf(.1,m))
    hi = np.where(over, stats.nbinom.ppf(.9,r,p),stats.poisson.ppf(.9,m))
    return {"crps": float(crps.mean()), "log_score": float(log.mean()) if np.isfinite(log).all() else None,
            "infinite_log_losses": int(np.isinf(log).sum()), "interval_80_coverage": float(np.mean((y>=lo)&(y<=hi))),
            "lower_tail_frequency": float(np.mean(y<lo)), "upper_tail_frequency": float(np.mean(y>hi)),
            "crps_tail_truncation_cdf": 1e-8,
            "push_mass": None, "push_mass_semantics": "requires an actually recorded integer line"}


def summarize(rows: pd.DataFrame) -> dict:
    observed = rows["participation_state"].eq("played") & pd.to_numeric(rows["actual"],errors="coerce").notna()
    scored = rows.loc[observed & pd.to_numeric(rows["mean"], errors="coerce").notna()]
    out = {"population_rows": len(rows), "supported_played_outcomes": int(observed.sum()),
           "scored_rows": len(scored), "dnp": int(rows.participation_state.eq("DNP").sum()),
           "unknown_participation": int(rows.participation_state.eq("unknown").sum()),
           "played_missing_statistic": int((rows.participation_state.eq("played") & ~observed).sum()),
           "fallback_rows": int(rows.fallback.notna().sum()), "selected_line_performance": "unavailable_no_recorded_offers"}
    if len(scored):
        e = scored["mean"].astype(float)-scored.actual.astype(float)
        out.update(mae=float(e.abs().mean()),rmse=float(np.sqrt(np.mean(e*e))),bias=float(e.mean()),
                   p95_absolute_error=float(e.abs().quantile(.95)),
                   unique_games=int(scored.game_id.nunique()),unique_players=int(scored.player_id.nunique()),
                   unique_weeks=int(scored[["season","week"]].drop_duplicates().shape[0]),
                   played_zero_rows=int(scored.actual.eq(0).sum()))
        # Only actual distributions qualify; archived points do not inherit one.
        dist = scored.loc[scored.scale.notna() & scored.family.notna()]
        for family, group in dist.groupby("family"):
            out[family] = probability_scores(group.actual,group["mean"],group.scale,family)
        if len(scored) and scored.family.eq("bernoulli").all():
            out["calibration"] = []
            for b in range(10):
                g=scored.loc[(scored["mean"]>=b/10)&((scored["mean"]<(b+1)/10) if b<9 else (scored["mean"]<=1))]
                out["calibration"].append({"lower":b/10,"n":len(g),"mean_probability":float(g["mean"].mean()) if len(g) else None,"event_rate":float(g.actual.mean()) if len(g) else None})
    known=rows.participation_state.isin(["played","DNP"]) & rows.p_participation.notna()
    if known.any():
        y=rows.loc[known,"participation_state"].eq("played").astype(float)
        out["participation_brier"] = float(np.mean((rows.loc[known,"p_participation"]-y)**2))
        out["participation_n"] = int(known.sum())
    return out


def paired_week_interval(rows: pd.DataFrame, baseline: str, challenger: str, seed=20261022, replicates=500):
    keys=["season","week","game_id","player_id","target"]
    good=rows.loc[rows.participation_state.eq("played") & rows.actual.notna() & rows["mean"].notna()]
    a=good.loc[good.method.eq(baseline),keys+["mean","actual"]]
    b=good.loc[good.method.eq(challenger),keys+["mean","actual"]]
    m=a.merge(b,on=keys,suffixes=("_a","_b"),validate="one_to_one")
    if not np.allclose(m.actual_a,m.actual_b): raise ValueError("paired outcome mismatch")
    m["delta"]=(m.mean_b-m.actual_b).abs()-(m.mean_a-m.actual_a).abs()
    g=m.groupby(["season","week"]).delta.agg(["sum","count"])
    out={"paired_n":len(m),"weeks":len(g),"mae_delta":float(m.delta.mean()) if len(m) else None,
         "interpretation":"historical_reconstruction_exploratory; no independent confirmation",
         "simultaneous_confidence":1-.05/12}
    if len(g)<8:
        return dict(out,interval=None,reason="fewer_than_8_week_clusters")
    rng=np.random.default_rng(seed)
    ix=rng.integers(0,len(g),size=(replicates,len(g)))
    sums=g["sum"].to_numpy()[ix].sum(axis=1);counts=g["count"].to_numpy()[ix].sum(axis=1)
    q=.05/12/2
    out["interval"]=np.quantile(sums/counts,[q,1-q]).tolist()
    out["multiplicity_limit"]="12_targets_only; configuration search remains exploratory; no promotion"
    return out


def campaign(features: pd.DataFrame, output: Path, config: dict, methods=None, seasons=None):
    from .models import fit_predict
    output.mkdir(parents=True,exist_ok=True)
    start=time.monotonic(); metadata=[]; allrows=[]; budget=config["budgets"]["max_training_seconds"]
    methods=methods or config["candidate_families"]
    if len(methods)>config["budgets"]["candidate_configurations_per_category"]: raise ValueError("search budget exceeded")
    seasons=seasons or [2022,2023,2024]
    for season in seasons:
        test=features.loc[features.season.eq(season)]
        if test.empty: continue
        first=pd.to_datetime(test.kickoff_utc,utc=True).min()
        train=features.loc[(features.season<season)&(pd.to_datetime(features.kickoff_utc,utc=True)<first)]
        if "outcome_available_utc" in train:
            train=train.loc[pd.to_datetime(train.outcome_available_utc,utc=True)<first]
        for target in config["targets"]:
            for method in methods:
                if time.monotonic()-start>=budget:
                    metadata.append({"season":season,"target":target,"method":method,"state":"NOT_RUN_BUDGET_EXHAUSTED"});continue
                began=time.monotonic()
                try:
                    pred=fit_predict(train,test,target,method)
                    r=test[["season","week","game_id","player_id","team","opponent","position","kickoff_utc","participation_state"]].copy()
                    r["actual"]=test[target];r["target"]=target;r["method"]=method
                    for col in ["mean","scale","family","p10","p50","p90","p_participation","fallback"]:r[col]=pred[col]
                    r["split"]="validation" if season in config["seasons"]["validation"] else "development"
                    r["evidence"]="current_vintage_historical_reconstruction"
                    path=output/f"{season}-{target}-{method}.parquet";r.to_parquet(path,index=False)
                    allrows.append(r)
                    metadata.append({"season":season,"target":target,"method":method,"state":"EVALUATED","seconds":time.monotonic()-began,"parameters":pred.attrs,"score":summarize(r)})
                except Exception as exc:
                    metadata.append({"season":season,"target":target,"method":method,"state":"FAILED","seconds":time.monotonic()-began,"error":str(exc),"traceback":traceback.format_exc()})
                (output/"trials.json").write_text(json.dumps(metadata,indent=2,default=str,allow_nan=False))
    if allrows:
        rows=pd.concat(allrows,ignore_index=True)
        rows.to_parquet(output/"rows.parquet",index=False)
        summaries=[];groups=[];paired=[]
        for (split,target,method),g in rows.groupby(["split","target","method"]):
            summaries.append({"split":split,"target":target,"method":method,**summarize(g)})
            for dimension in ["position","player_id","team","opponent"]:
                for value,sub in g.groupby(dimension):
                    groups.append({"split":split,"target":target,"method":method,"dimension":dimension,"value":value,"interpretation":"exploratory_unshrunk_no_selection",**summarize(sub)})
        for (split,target),g in rows.groupby(["split","target"]):
            for method in methods:
                if method!="recent": paired.append({"split":split,"target":target,"method":method,**paired_week_interval(g,"recent",method)})
        (output/"summary.json").write_text(json.dumps(summaries,indent=2,allow_nan=False))
        (output/"subgroups.json").write_text(json.dumps(groups,allow_nan=False))
        (output/"paired.json").write_text(json.dumps(paired,indent=2,allow_nan=False))
    report={"registration":config["registration_id"],"elapsed_seconds":time.monotonic()-start,"trials":len(metadata),"failed":sum(x["state"]=="FAILED" for x in metadata),"confirmation":"PENDING_FUTURE_OUTCOMES","promoted":[],"historical_exposure":"2022-2024 now exposed;2025 already exposed; no historical confirmation claim"}
    (output/"campaign.json").write_text(json.dumps(report,indent=2))
    return report
