"""Registered zero-fit Week 6 outcome-source coverage variant.

Reads saved predictions without changing them. Candidate observations use the
shared cached grading adapter; disagreeing providers never acquire precedence.
No fitting, acquisition, forecast-state writes or model selection occurs here.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .archive_study import KEYS, _sha, paired_comparison, read_source
from .evaluation import summarize
from .experiment import atomic_checkpoint, termination_guard
from .grading_sources import COUNTS, cached_nflverse_outcome, load_cached_grading_context
from .live import schedule_games
from .state import digest, now_utc, source_tree_digest, utc

PREDICTION_COLUMNS=["mean","scale","family","p10","p50","p90","p_participation","fallback","algorithm"]


def _number(value,target):
    if value is None or pd.isna(value):return None,False
    try:value=float(value)
    except (TypeError,ValueError):return None,True
    if not np.isfinite(value) or (target in COUNTS and (value<0 or not value.is_integer())):return None,True
    return value,False


def resolve_sources(target,sleeper_actual,sleeper_state,nflverse):
    """Resolve supported content only; unknown publication clocks cannot order it."""
    original,bad_original=_number(sleeper_actual,target)
    supplemental,bad_supplemental=_number(nflverse.get("actual"),target)
    ns=nflverse.get("participation_state","unknown")
    ss=sleeper_state if sleeper_state in {"played","DNP"} else "unknown"
    ns=ns if ns in {"played","DNP"} else "unknown"
    result={"actual":None,"participation_state":ss if ss!="unknown" else ns,"resolution":"unresolved_missing_sources",
            "quarantined":False,"sleeper_actual":original,"sleeper_participation_state":ss,
            "nflverse_actual":supplemental,"nflverse_participation_state":ns,
            "nflverse_gap":nflverse.get("gap_reason"),"nflverse_supplement_status":nflverse.get("supplement_status")}
    if ss!="unknown" and ns!="unknown" and ss!=ns:
        return {**result,"participation_state":"unknown","resolution":"quarantined_participation_conflict","quarantined":True}
    if bad_original or bad_supplemental or (original is not None and ss!="played"):
        return {**result,"resolution":"quarantined_invalid_source_outcome","quarantined":True}
    supported=nflverse.get("supplement_status")=="supported" and ns=="played" and supplemental is not None
    if original is not None and supported and original!=supplemental:
        return {**result,"resolution":"quarantined_numeric_conflict","quarantined":True}
    if original is not None:
        return {**result,"actual":original,"participation_state":"played",
                "resolution":"dual_source_agreement" if supported else "sleeper_supported_nflverse_gap"}
    if supported:
        return {**result,"actual":supplemental,"participation_state":"played","resolution":"expanded_nflverse_supported"}
    return result


def frozen_facts(rows,cohort,targets,methods,period):
    """One frozen source fact per archive opportunity; validate every saved method."""
    if rows.duplicated(KEYS+["method"]).any() or cohort.duplicated(KEYS).any():raise ValueError("duplicate frozen archive keys")
    if not (rows.season.eq(period["season"])&rows.week.eq(period["week"])).all():raise ValueError("frozen period mismatch")
    numeric=rows.loc[rows.target.isin(targets)].copy()
    for target in targets:
        group=numeric.loc[numeric.target.eq(target)]
        if set(group.method)!=set(methods):raise ValueError("missing or unexpected frozen method")
        populations=[set(map(tuple,g[KEYS].to_numpy())) for _,g in group.groupby("method")]
        if any(keys!=populations[0] for keys in populations[1:]):raise ValueError("unequal frozen method population")
    facts=numeric.loc[numeric.method.eq("pinned_website"),KEYS+["actual","participation_state"]].copy()
    for method in methods:
        check=numeric.loc[numeric.method.eq(method),KEYS+["actual","participation_state"]].merge(facts,on=KEYS,validate="one_to_one",suffixes=("_method","_fact"))
        same=check.actual_method.eq(check.actual_fact)|(check.actual_method.isna()&check.actual_fact.isna())
        if not (same&check.participation_state_method.eq(check.participation_state_fact)).all():raise ValueError("inconsistent frozen source facts")
    facts=facts.merge(cohort,on=KEYS,validate="one_to_one",how="left",indicator=True)
    if not facts._merge.eq("both").all() or not len(facts):raise ValueError("missing frozen cohort identity")
    facts=facts.drop(columns="_merge")
    if not (pd.to_datetime(facts.cutoff_utc,utc=True)<pd.to_datetime(facts.kickoff_utc,utc=True)).all():raise ValueError("archive cutoff does not precede kickoff")
    return facts


def apply_outcomes(rows,outcomes):
    """Create a separately named outcome variant while preserving every prediction."""
    updates=outcomes.set_index(KEYS)
    variant=rows.copy();variant["original_actual"]=rows.actual;variant["original_participation_state"]=rows.participation_state
    index=pd.MultiIndex.from_frame(rows[KEYS]);numeric=index.isin(updates.index)
    ordered=updates.reindex(index[numeric])
    variant.loc[numeric,"actual"]=ordered.actual.to_numpy()
    variant.loc[numeric,"participation_state"]=ordered.participation_state.to_numpy()
    variant["source_resolution"]="unsupported_unchanged"
    variant.loc[numeric,"source_resolution"]=ordered.resolution.to_numpy()
    pd.testing.assert_frame_equal(variant[KEYS+["method"]+PREDICTION_COLUMNS],rows[KEYS+["method"]+PREDICTION_COLUMNS])
    return variant


def coverage_report(rows,outcomes,config):
    scores=[];comparisons=[];common_scores=[];coverage=[]
    for target in config["targets"]:
        group=rows.loc[rows.target.eq(target)]
        scores.extend({"target":target,"method":method,**summarize(g,include_distribution=False)} for method,g in group.groupby("method"))
        for baseline in ["raw_sleeper","pinned_website"]:
            for lab in ["lab_recent","lab_pooled","lab_selected"]:
                comparisons.append({"target":target,**paired_comparison(group,baseline,lab,config["budgets"]["bootstrap_replicates"])})
        pivot=group.pivot(index=KEYS,columns="method",values="mean")
        complete=pivot.index[pivot[config["methods"]].notna().all(axis=1)]
        common=group.set_index(KEYS).loc[complete].reset_index()
        common_scores.extend({"target":target,"method":method,**summarize(g,include_distribution=False)} for method,g in common.groupby("method"))
        g=outcomes.loc[outcomes.target.eq(target)]
        original=g.sleeper_participation_state.eq("played")&g.sleeper_actual.notna()
        resolved=g.participation_state.eq("played")&g.actual.notna()
        coverage.append({"target":target,"archive_opportunities":len(g),"original_supported_outcomes":int(original.sum()),"resolved_supported_outcomes":int(resolved.sum()),
                         "expanded_outcomes":int(g.resolution.eq("expanded_nflverse_supported").sum()),"original_supported_quarantined":int((original&g.quarantined).sum()),
                         "resolved_explicit_zeros":int((resolved&g.actual.eq(0)).sum()),"expanded_explicit_zeros":int((g.resolution.eq("expanded_nflverse_supported")&g.actual.eq(0)).sum()),
                         "resolutions":g.resolution.value_counts().to_dict(),"nflverse_gaps":g.nflverse_gap.fillna("supported").value_counts().to_dict()})
    return {"population_scores":scores,"five_method_common_scores":common_scores,"paired_comparisons":comparisons,"source_coverage":coverage}


def run(root,cache,frozen_attempt):
    root,cache,frozen_attempt=map(Path,(root,cache,frozen_attempt))
    config=json.loads((root/"config/archive-source-coverage-v1.json").read_text())
    if config["budgets"]["new_fits"]!=0:raise ValueError("coverage variant must have zero fit budget")
    execution=json.loads((root/"reports/archive-lab-week6-v1/execution.json").read_text())
    bindings={name:execution["artifact_sha256"][name] for name in ["rows.parquet","archive-cohort.parquet","trials.json","report.json"]}
    if bindings["rows.parquet"]!=config["frozen_predictions"]["rows_sha256"] or bindings["report.json"]!=config["frozen_predictions"]["original_report_sha256"]:raise ValueError("registration versus original execution hash mismatch")
    for name,expected in bindings.items():
        if _sha(frozen_attempt/name)!=expected:raise ValueError("frozen artifact hash mismatch: "+name)
    if _sha(root/"reports/archive-lab-week6-v1/report.json")!=bindings["report.json"]:raise ValueError("public original report changed")
    output=root/"runs"/config["registration_id"]/now_utc().strftime("%Y%m%dT%H%M%S%f")
    output.mkdir(parents=True,exist_ok=False);atomic_checkpoint(output/"registration.json",config)
    started=time.monotonic()
    report={"registration":config,"state":"STARTED","new_fits":0,"prediction_changes":0,"promoted":[],"original_artifacts":bindings}
    def bounded():
        if time.monotonic()-started>config["budgets"]["evaluation_seconds"]:raise TimeoutError("registered zero-fit evaluation budget exhausted")
    with termination_guard():
        try:
            rows=pd.read_parquet(frozen_attempt/"rows.parquet");cohort=pd.read_parquet(frozen_attempt/"archive-cohort.parquet")
            facts=frozen_facts(rows,cohort,config["targets"],config["methods"],config["period"])
            # Common loader materializes processed history. Isolate those writes
            # from the read-only shared cache while reusing its verified raw bytes.
            view=output/"cache-view";view.mkdir();(view/"raw").symlink_to((cache/"raw").resolve(),target_is_directory=True)
            context=load_cached_grading_context(view,[config["period"]["season"]])
            context["history"]=context["history"].loc[context["history"].week.eq(config["period"]["week"])].copy()
            stat_name=f"stats_player_week_{config['period']['season']}.parquet"
            if context["receipts"][stat_name]["sha256"]!=config["sources"]["statistics_sha256"]:raise ValueError("registered NFLverse statistics hash changed")
            status,status_receipt=read_source(cache/"raw/live/2026-10-22/archive-schedule-2026-6.json")
            if status_receipt["sha256"]!=config["sources"]["status_sha256"]:raise ValueError("registered independent status hash changed")
            if status.get("season",{}).get("year")!=config["period"]["season"] or status.get("week",{}).get("number")!=config["period"]["week"]:raise ValueError("independent schedule period mismatch")
            games={g["game_id"]:g for g in schedule_games(status)}
            manifest={"registration_sha256":digest(config),"code_sha256":source_tree_digest(root),"frozen_predictions":bindings,
                      "source_receipts":context["receipts"],"status_receipt":status_receipt,"private_cache_view":True,
                      "queried_period":config["period"],"original_source_actuals":"unchanged frozen rows; missing fields remain missing",
                      "source_order":"both provider publication clocks unknown; no correction order or winner",
                      "vintage":"current reconstructed NFLverse vintage; original historical availability unverified",
                      "cold_context_deviation":"original selected 9 numeric context-inference rows retained; no qualification"}
            atomic_checkpoint(output/"manifest.json",manifest);bounded()
            resolved=[]
            for fact in facts.to_dict("records"):
                bounded();provider_game="espn:"+str(fact["game_id"]).removeprefix("espn:")
                forecast={**fact,"game_id":provider_game}
                # The saved Sleeper identity requires an exact current crosswalk;
                # an originally exact GSIS binding must agree as well.
                candidate=cached_nflverse_outcome(context,forecast,games.get(provider_game,{}),status_receipt)
                frozen_pid=fact.get("canonical_player_id")
                if candidate.get("canonical_player_id") and isinstance(frozen_pid,str) and frozen_pid.startswith("00-") and candidate["canonical_player_id"]!=frozen_pid:
                    candidate={**candidate,"actual":None,"supplement_status":"unsupported","gap_reason":"conflicting_frozen_canonical_identity","participation_state":"unknown"}
                value=resolve_sources(fact["target"],fact["actual"],fact["participation_state"],candidate)
                resolved.append({**{key:fact[key] for key in KEYS},**value,"nflverse_source_sha256":candidate.get("source_sha256"),
                                 "nflverse_canonical_player_id":candidate.get("canonical_player_id"),"nflverse_canonical_game_id":candidate.get("canonical_game_id"),
                                 "nflverse_identity_binding":candidate.get("identity_binding"),"source_publication_order":"unknown; conflicts quarantined"})
            outcomes=pd.DataFrame(resolved);variant=apply_outcomes(rows,outcomes)
            outcomes.to_parquet(output/"outcomes.parquet",index=False);variant.to_parquet(output/"rows.parquet",index=False)
            report.update(coverage_report(variant,outcomes,config));bounded()
            for name,expected in bindings.items():
                if _sha(frozen_attempt/name)!=expected:raise ValueError("original artifact changed during zero-fit evaluation")
            if _sha(root/"reports/archive-lab-week6-v1/report.json")!=bindings["report.json"]:raise ValueError("original public report changed")
            report.update(state="COMPLETED",elapsed_seconds=time.monotonic()-started,archive_rows=len(cohort),numeric_category_rows=len(outcomes),
                          frozen_prediction_rows=len(rows),variant_rows=len(variant),original_artifacts_unchanged=True,
                          artifacts={name:_sha(output/name) for name in ["manifest.json","outcomes.parquet","rows.parquet"]},
                          manifest=manifest,evidence="one exposed week; source-coverage variant, no new inference, selection, reproduction or promotion; original cold-context deviation retained",
                          unsupported={"fantasy_ppr":"exact lab outcome unsupported; original rows unchanged","anytime_td":"archive probabilities unbound; original abstentions unchanged"})
            atomic_checkpoint(output/"report.json",report);return report,output
        except BaseException as error:
            report.update(state="FAILED_OR_INTERRUPTED",error=repr(error),elapsed_seconds=time.monotonic()-started)
            atomic_checkpoint(output/"failure.json",report);raise


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path.cwd());parser.add_argument("--cache",type=Path,required=True);parser.add_argument("--frozen-attempt",type=Path,required=True)
    args=parser.parse_args();report,output=run(args.root,args.cache,args.frozen_attempt)
    print(json.dumps({"state":report["state"],"output":str(output),"new_fits":report["new_fits"],"elapsed_seconds":report["elapsed_seconds"]},indent=2))
