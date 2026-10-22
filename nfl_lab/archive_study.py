"""Preregistered, exposed Week 6 lab-versus-original-baseline comparison.

Uses existing source caches, feature/model/scoring engines and immutable archive
authentication. No source acquisition, official forecast state or website writes.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import warnings

import numpy as np
import pandas as pd

from .archive_replay import replay_baselines
from .data import TARGETS, _schedule, load_identity
from .evaluation import paired_week_interval, summarize
from .experiment import atomic_checkpoint, termination_guard
from .features import build_features
from .live import schedule_games
from .models import fit_predict
from .state import canonical, digest, now_utc, source_tree_digest, utc

KEYS=["season","week","game_id","player_id","target"]
GSIS=re.compile(r"00-\d{7}")


def _sha(path):
    with Path(path).open("rb") as source:return hashlib.file_digest(source,"sha256").hexdigest()


def read_source(path):
    path=Path(path);receipt=json.loads(Path(str(path)+".receipt.json").read_text())
    if receipt.get("sha256")!=_sha(path):raise ValueError(f"cached source hash mismatch: {path.name}")
    return json.loads(path.read_text()),receipt


def archive_population(payload,status,identity,schedule,expected_cutoff):
    """Bind every archive row, retaining unsupported rows and cold-start roles."""
    cutoff=utc(payload["captured_at"])
    if cutoff!=utc(expected_cutoff) or utc(payload["forecast_generated_at"])>cutoff:
        raise ValueError("archive forecast/capture cutoff mismatch")
    games={g["game_id"].removeprefix("espn:"):g for g in schedule_games(status)}
    if status.get("season",{}).get("year")!=2026 or status.get("week",{}).get("number")!=6:
        raise ValueError("archive schedule period mismatch")
    exact=identity.loc[identity.identity_status.eq("source_exact_binding") & identity.sleeper_id.notna()]
    bindings={}
    for sid,group in exact.groupby(exact.sleeper_id.astype(str),sort=False):
        if len(group)==1 and GSIS.fullmatch(str(group.iloc[0].player_id)):bindings[str(sid)]=str(group.iloc[0].player_id)
    contexts=[];cohort=[];context_keys={}
    for i,row in enumerate(payload["rows"]):
        target="fantasy_ppr" if row["category"]=="fpts" else row["category"]
        sid=str(row["player_id"]);game=games.get(str(row["game_id"]))
        record={"archive_row_id":i,"season":int(row["season"]),"week":int(row["week"]),"game_id":str(row["game_id"]),
                "player_id":"sleeper:"+sid,"sleeper_id":sid,"target":target,"team":row["team"],"position":row["position"],
                "kickoff_utc":row["kickoff"],"cutoff_utc":cutoff.isoformat(),"binding_gap":"","context_id":None}
        valid=game and game["final"] and row["team"] in {game["home"],game["away"]}
        valid=valid and (int(row["season"]),int(row["week"]))==(2026,6) and utc(row["kickoff"])==utc(game["kickoff_utc"]) and cutoff<utc(row["kickoff"])
        if not valid:
            record["binding_gap"]="unsupported_game_or_cutoff";cohort.append(record);continue
        opponent=game["away"] if row["team"]==game["home"] else game["home"]
        record["opponent"]=opponent
        matches=schedule.loc[schedule.season.eq(2026)&schedule.week.eq(6)&schedule.team.eq(row["team"])&schedule.opponent.eq(opponent)&pd.to_datetime(schedule.kickoff_utc,utc=True).eq(pd.Timestamp(row["kickoff"]))]
        if len(matches)!=1:
            record["binding_gap"]="nflverse_exact_schedule_tuple_unavailable";cohort.append(record);continue
        pid=bindings.get(sid,"sleeper:"+sid)
        record["canonical_player_id"]=pid
        record["identity_binding"]="exact_current_vintage_sleeper_gsis" if sid in bindings else "unlinked_or_ambiguous_identity_position_prior"
        context_key=(str(matches.iloc[0].game_id),pid)
        metadata=(row["team"],opponent,row["position"],utc(row["kickoff"]))
        if context_key in context_keys:
            index,prior_metadata=context_keys[context_key]
            if metadata!=prior_metadata:raise ValueError("conflicting archive player/game context")
        else:
            index=len(contexts);context_keys[context_key]=(index,metadata)
            context={"season":2026,"week":6,"game_id":context_key[0],"player_id":pid,"team":row["team"],"opponent":opponent,
                     "position":row["position"],"kickoff_utc":row["kickoff"],"cutoff_utc":cutoff.isoformat(),"participation_state":"unknown",
                     "outcome_available_utc":pd.Timestamp(row["kickoff"])+pd.Timedelta(days=7),"is_home":row["team"]==game["home"],"_archive_context_id":index}
            for field in list(TARGETS)+["rec_tgt","rush_td","rec_td","offense_snaps"]:context[field]=np.nan
            contexts.append(context)
        record["context_id"]=index
        if target in {"anytime_td","fantasy_ppr"}:record["binding_gap"]="archive_probability_binding_unavailable" if target=="anytime_td" else "exact_ppr_lab_training_unsupported"
        cohort.append(record)
    frame=pd.DataFrame(cohort)
    if frame.duplicated(KEYS).any():raise ValueError("duplicate archived player/game/target")
    return frame,pd.DataFrame(contexts)


def prepare_features(history,contexts,cutoff):
    """Source labels precede the fixed archive cutoff; test targets are blank."""
    cutoff=pd.Timestamp(cutoff)
    keep=(pd.to_datetime(history.kickoff_utc,utc=True)<cutoff)&((history.season<2026)|(history.season.eq(2026)&history.week.le(5)))
    history=history.loc[keep].copy()
    if history.empty:raise ValueError("no earlier supported history")
    history=history.drop(columns=[c for c in history if c.startswith("f_") or c in {"feature_max_source_available_utc","cutoff_utc"}],errors="ignore")
    history["_archive_context_id"]=np.nan
    contexts=contexts.copy()
    for field in list(TARGETS)+["rec_tgt","rush_td","rec_td","offense_snaps"]:contexts[field]=np.nan
    contexts["participation_state"]="unknown"
    joined=pd.concat([history,contexts],ignore_index=True)
    features=build_features(joined)
    test=features.loc[features._archive_context_id.notna()].copy()
    test.index=test._archive_context_id.astype(int)
    train=features.loc[features._archive_context_id.isna()&pd.to_datetime(features.outcome_available_utc,utc=True).lt(cutoff)].copy()
    if not (pd.to_datetime(train.outcome_available_utc,utc=True)<cutoff).all():raise ValueError("future training label")
    latest=pd.to_datetime(test.feature_max_source_available_utc,utc=True)
    if (latest.notna()&latest.ge(cutoff)).any():raise ValueError("future feature source")
    return train,test


def paired_comparison(rows,baseline,challenger,replicates=500):
    """Same actual support, paired week limit and descriptive game bootstrap."""
    good=rows.participation_state.eq("played")&rows.actual.notna()&rows["mean"].notna()
    a=rows.loc[good&rows.method.eq(baseline),KEYS+["actual","mean"]]
    b=rows.loc[good&rows.method.eq(challenger),KEYS+["actual","mean"]]
    joined=a.merge(b,on=KEYS,suffixes=("_base","_lab"),validate="one_to_one")
    if not np.array_equal(joined.actual_base.to_numpy(),joined.actual_lab.to_numpy()):raise ValueError("paired actual mismatch")
    result={"baseline":baseline,"challenger":challenger,"paired_rows":len(joined),"week_uncertainty":paired_week_interval(rows,baseline,challenger),
            "delta_definition":"lab MAE minus baseline MAE; negative favors lab","game_interval_interpretation":"descriptive one-exposed-week bootstrap; no promotion/inference across weeks"}
    if joined.empty:return result
    joined["delta"]=(joined.mean_lab-joined.actual_lab).abs()-(joined.mean_base-joined.actual_base).abs()
    group=joined.groupby("game_id").delta.agg(["sum","count"])
    result.update(mae_delta=float(joined.delta.mean()),games=len(group))
    if len(group)>1:
        rng=np.random.default_rng(20261022);indices=rng.integers(0,len(group),size=(replicates,len(group)))
        means=group["sum"].to_numpy()[indices].sum(axis=1)/group["count"].to_numpy()[indices].sum(axis=1)
        result["descriptive_game_cluster_95pct_interval"]=np.quantile(means,[.025,.975]).tolist()
    for label,suffix in [("baseline","base"),("lab","lab")]:
        error=joined[f"mean_{suffix}"]-joined[f"actual_{suffix}"]
        result[label+"_matched_metrics"]={"mae":float(error.abs().mean()),"rmse":float(np.sqrt(np.mean(error**2))),"bias":float(error.mean())}
    return result


def run(root,cache):
    root,cache=Path(root),Path(cache)
    config_path=root/"config/archive-lab-comparison-v1.json";config=json.loads(config_path.read_text())
    # Forward-only budget guard: a completed registration is replayed from its
    # saved rows, never refitted merely because the entry point is invoked again.
    assert_unused_registration(root,config["registration_id"])
    output=root/"runs"/config["registration_id"]/now_utc().strftime("%Y%m%dT%H%M%S%f")
    output.mkdir(parents=True,exist_ok=False);atomic_checkpoint(output/"registration.json",config)
    started=time.monotonic();trials=[];issued=[];fits=0
    report={"registration":config,"output":str(output),"state":"STARTED","promoted":[]}
    with termination_guard():
        try:
            if _sha(root/config["method_selection_source"]["path"])!=config["method_selection_source"]["sha256"]:raise ValueError("frozen selected-method source changed")
            receipt=cache/"raw/recovery/baseline-receipt.json.gz"
            if _sha(receipt)!=config["archive"]["receipt_sha256"]:raise ValueError("archive receipt mismatch")
            doc=json.loads(gzip.decompress(receipt.read_bytes()));payload=doc["payload"]
            if digest(payload)!=doc["payload_sha256"]:raise ValueError("archive payload mismatch")
            stats,stats_receipt=read_source(cache/"raw/live/2026-10-22/archive-stats-2026-6.json")
            status,status_receipt=read_source(cache/"raw/live/2026-10-22/archive-schedule-2026-6.json")
            baseline_report=replay_baselines(receipt,stats,status,output/"baseline",stats_receipt=stats_receipt,status_receipt=status_receipt)
            baselines=pd.read_parquet(output/"baseline/baseline-rows.parquet")
            baselines["algorithm"]=baselines.method
            earlier_path=cache/"processed/features.parquet";current_path=cache/"processed/history.parquet"
            sources={"historic_feature_frame":_sha(earlier_path),"current_history_frame":_sha(current_path),"original_receipt":_sha(receipt),
                     "stats":stats_receipt["sha256"],"status":status_receipt["sha256"]}
            old=pd.read_parquet(earlier_path,filters=[("season","<",2026)])
            old=old.drop(columns=[c for c in old if c.startswith("f_") or c=="feature_max_source_available_utc"])
            current=pd.read_parquet(current_path,filters=[("season","==",2026),("week","<=",5)])
            if _sha(earlier_path)!=sources["historic_feature_frame"] or _sha(current_path)!=sources["current_history_frame"]:raise ValueError("shared source changed during read")
            history=pd.concat([old,current],ignore_index=True)
            identity_sources=[cache/"raw/players.parquet",cache/"raw/schedules.csv"]+sorted((cache/"raw").glob("roster_weekly_*.parquet"))
            sources["identity_and_schedule"]={p.name:_sha(p) for p in identity_sources}
            for path in identity_sources:
                source_receipt=json.loads(Path(str(path)+".receipt.json").read_text())
                if source_receipt.get("sha256")!=sources["identity_and_schedule"][path.name]:raise ValueError("identity/schedule source receipt mismatch")
            identity=load_identity(cache);schedule=_schedule(cache/"raw",[2026])
            if any(_sha(p)!=sources["identity_and_schedule"][p.name] for p in identity_sources):raise ValueError("identity/schedule changed during read")
            cohort,contexts=archive_population(payload,status,identity,schedule,config["archive"]["common_forecast_cutoff_utc"])
            cohort.to_parquet(output/"archive-cohort.parquet",index=False)
            train,test=prepare_features(history,contexts,config["archive"]["common_forecast_cutoff_utc"])
            manifest={"registration_sha256":digest(config),"source_tree_sha256":source_tree_digest(root),"sources":sources,"train_rows":len(train),"test_player_games":len(test),
                      "max_training_available_utc":str(pd.to_datetime(train.outcome_available_utc,utc=True).max()),"feature_cutoff_utc":config["archive"]["common_forecast_cutoff_utc"],
                      "identity_binding_counts":cohort.identity_binding.fillna("not_bound").value_counts().to_dict(),"availability":"current-vintage; assumed kickoff+7d; local original pregame baselines only, no authenticated remote publication"}
            atomic_checkpoint(output/"manifest.json",manifest)
            actuals=baselines.loc[baselines.method.eq("pinned_website"),KEYS+["actual","participation_state"]]
            facts=cohort.merge(actuals,on=KEYS,how="left",validate="one_to_one")
            facts["participation_state"]=facts.participation_state.fillna("unknown")
            for target,selected in config["selected_methods"].items():
                population=facts.loc[facts.target.eq(target)].copy()
                valid=population.context_id.notna()&population.binding_gap.eq("")
                context_ids=population.loc[valid,"context_id"].astype(int)
                for label,method in [("lab_recent","recent"),("lab_pooled","pooled"),("lab_selected",selected)]:
                    row=population.copy();row["method"]=label;row["algorithm"]=method
                    for name in ["mean","scale","p10","p50","p90","p_participation"]:row[name]=np.nan
                    row["family"]=None;row["fallback"]=row.binding_gap
                    if fits>=config["budgets"]["maximum_fits"] or time.monotonic()-started>=config["budgets"]["maximum_fit_seconds"]-30:
                        trial={"target":target,"method":label,"algorithm":method,"state":"NOT_RUN_BUDGET_EXHAUSTED"};row["fallback"]="study_budget_exhausted"
                    elif not len(context_ids):
                        trial={"target":target,"method":label,"algorithm":method,"state":"NO_QUALIFIED_CONTEXT"}
                    else:
                        began=time.monotonic();fits+=1
                        try:
                            with warnings.catch_warnings(record=True) as captured:
                                warnings.simplefilter("always");pred=fit_predict(train,test.loc[context_ids],target,method)
                            for name in ["mean","scale","family","p10","p50","p90","p_participation","fallback"]:row.loc[valid,name]=pred[name].to_numpy()
                            cold=row.identity_binding.eq("unlinked_or_ambiguous_identity_position_prior")&valid
                            row.loc[cold,"fallback"]="identity_cold_start;"+row.loc[cold,"fallback"].astype(str)
                            trial={"target":target,"method":label,"algorithm":method,"state":"EVALUATED","seconds":time.monotonic()-began,"parameters":pred.attrs,"warnings":[str(w.message) for w in captured]}
                        except Exception as error:
                            trial={"target":target,"method":label,"algorithm":method,"state":"FAILED","error":repr(error)};row["fallback"]="recorded_fit_failure"
                    trial["score"]=summarize(row,include_distribution=False)
                    row.to_parquet(output/f"{target}-{label}.parquet",index=False);issued.append(row);trials.append(trial)
                    atomic_checkpoint(output/"trials.json",trials)
            # Unsupported original markets remain in coverage and abstention rows.
            for target,reason in config["unsupported"].items():
                for label in ["lab_recent","lab_pooled","lab_selected"]:
                    row=facts.loc[facts.target.eq(target)].copy();row["method"]=label;row["algorithm"]="unsupported"
                    for name in ["mean","scale","p10","p50","p90","p_participation"]:row[name]=np.nan
                    row["family"]=None;row["fallback"]=reason;issued.append(row)
            rows=pd.concat([baselines]+issued,ignore_index=True);rows.to_parquet(output/"rows.parquet",index=False)
            scores=[{"target":target,"method":method,**summarize(group,include_distribution=False)} for (target,method),group in rows.groupby(["target","method"])]
            comparisons=[];common_scores=[]
            for target in config["selected_methods"]:
                group=rows.loc[rows.target.eq(target)]
                for baseline in ["raw_sleeper","pinned_website"]:
                    for lab in ["lab_recent","lab_pooled","lab_selected"]:
                        comparisons.append({"target":target,**paired_comparison(group,baseline,lab,config["budgets"]["bootstrap_replicates"])})
                pivot=group.pivot(index=KEYS,columns="method",values="mean")
                complete=pivot.index[pivot[["raw_sleeper","pinned_website","lab_recent","lab_pooled","lab_selected"]].notna().all(axis=1)]
                common=group.set_index(KEYS).loc[complete].reset_index()
                common_scores.extend({"target":target,"method":method,**summarize(g,include_distribution=False)} for method,g in common.groupby("method"))
            report.update(state="COMPLETED",manifest=manifest,baseline_replay=baseline_report,elapsed_seconds=time.monotonic()-started,fits_attempted=fits,
                          archive_rows=len(cohort),binding_gaps=cohort.binding_gap.value_counts(dropna=False).to_dict(),trials=[{k:v for k,v in t.items() if k!="parameters"} for t in trials],
                          population_scores=scores,five_method_common_scores=common_scores,paired_comparisons=comparisons,
                          evidence="one already-exposed week; reconstructed availability; no production/scientific qualification or pooled-YPA reproduction",frozen_rec_experiment="untouched")
            atomic_checkpoint(output/"report.json",report)
            return report,output
        except BaseException as error:
            report.update(state="FAILED_OR_INTERRUPTED",error=repr(error),elapsed_seconds=time.monotonic()-started,fits_attempted=fits,trials=trials)
            atomic_checkpoint(output/"failure.json",report);raise


def assert_unused_registration(root,registration_id):
    root=Path(root)
    candidates=list((root/"runs"/registration_id).glob("*/report.json"))
    candidates.extend((root/"reports").glob("*/report.json"))
    for path in candidates:
        saved=json.loads(path.read_text())
        if saved.get("registration",{}).get("registration_id")==registration_id and saved.get("state")=="COMPLETED":
            raise ValueError("registered archive fit budget already consumed; replay existing saved rows")


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--root",type=Path,default=Path.cwd());parser.add_argument("--cache",type=Path,required=True)
    args=parser.parse_args();report,output=run(args.root,args.cache)
    print(json.dumps({"output":str(output),"state":report["state"],"fits_attempted":report["fits_attempted"],"elapsed_seconds":report["elapsed_seconds"]},indent=2))
