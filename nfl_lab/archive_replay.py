"""New descriptive baseline replay; never reconstructs the missing challenger."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .evaluation import summarize
from .live import schedule_games
from .scoring import stat_value
from .state import canonical,utc

BASELINE_SHA="de8531889cbbc39591f390824c0d61e166a93a8a075331eb523ee2bbaa24db80"


def replay_baselines(receipt_path:Path,stats_doc,status_doc,output:Path,*,stats_receipt:dict,status_receipt:dict):
    raw=Path(receipt_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASELINE_SHA:raise ValueError("original baseline receipt digest mismatch")
    doc=json.loads(gzip.decompress(raw));payload=doc["payload"]
    if hashlib.sha256(canonical(payload)).hexdigest()!=doc["payload_sha256"]:raise ValueError("payload digest mismatch")
    periods={(int(r["season"]),int(r["week"])) for r in payload["rows"]}
    if len(periods)!=1:raise ValueError("mixed archived periods")
    year,week=next(iter(periods))
    if status_doc.get("season",{}).get("year")!=year or status_doc.get("week",{}).get("number")!=week:raise ValueError("archived status period mismatch")
    for receipt in [stats_receipt,status_receipt]:
        if not receipt.get("sha256") or not receipt.get("url") or not receipt.get("retrieved_utc"):raise ValueError("source receipt required")
    finals={g["game_id"].removeprefix("espn:"):g for g in schedule_games(status_doc) if g["final"]}
    entries={str(s["player_id"]):s for s in stats_doc} if isinstance(stats_doc,list) else stats_doc
    rows=[];excluded={}
    for r in payload["rows"]:
        target="fantasy_ppr" if r["category"]=="fpts" else r["category"]
        # Saved TD expectations are not probabilities. Original probability
        # requires its full board binding, which is not supplied by this receipt.
        if target=="anytime_td":excluded["td_probability_binding_unavailable"]=excluded.get("td_probability_binding_unavailable",0)+1;continue
        g=finals.get(str(r["game_id"]));s=entries.get(str(r["player_id"]));st=s.get("stats",{}) if isinstance(s,dict) else {}
        if isinstance(s,dict):
            if s.get("season") is not None and int(s["season"])!=year:raise ValueError("archived statistic season mismatch")
            if s.get("week") is not None and int(s["week"])!=week:raise ValueError("archived statistic week mismatch")
            source_team=s.get("team") or (s.get("player") or {}).get("team")
            if source_team and source_team!=r["team"]:st={}
        valid=g and utc(g["kickoff_utc"])==utc(r["kickoff"]) and r["team"] in {g["home"],g["away"]}
        valid=valid and utc(payload["forecast_generated_at"])<=utc(payload["captured_at"])<utc(r["kickoff"])
        if not valid:excluded["unsupported_game_or_cutoff"]=excluded.get("unsupported_game_or_cutoff",0)+1;continue
        played=st.get("gp")==1 or (isinstance(st.get("off_snp"),(float,int)) and st["off_snp"]>0)
        actual=stat_value(target,st) if played else None
        if target in ["pass_cmp","pass_att","pass_td","pass_int","rush_att","rec"] and actual is not None and not float(actual).is_integer():actual=None
        for method,key in [("raw_sleeper","raw_projection"),("pinned_website","adjusted_projection")]:
            value=r.get(key)
            rows.append({"season":r["season"],"week":r["week"],"game_id":str(r["game_id"]),"player_id":"sleeper:"+str(r["player_id"]),"team":r["team"],"opponent":g["away"] if r["team"]==g["home"] else g["home"],"position":r["position"],"target":target,"method":method,"actual":actual,"mean":float(value) if isinstance(value,(float,int)) and not isinstance(value,bool) else np.nan,"scale":np.nan,"family":None,"p_participation":np.nan,"participation_state":"played" if played else "unknown","fallback":"" if value is not None else "original_point_unavailable"})
    frame=pd.DataFrame(rows);output.mkdir(parents=True,exist_ok=True)
    frame.to_parquet(output/"baseline-rows.parquet",index=False)
    scores=[]
    for (target,method),g in frame.groupby(["target","method"]):scores.append({"target":target,"method":method,**summarize(g)})
    paired=[]
    keys=["game_id","player_id","target"]
    left=frame.loc[frame.method.eq("raw_sleeper"),keys+["mean"]].rename(columns={"mean":"raw_mean"})
    right=frame.loc[frame.method.eq("pinned_website"),keys+["mean"]].rename(columns={"mean":"website_mean"})
    common=left.merge(right,on=keys,validate="one_to_one").dropna(subset=["raw_mean","website_mean"])[keys]
    matched=frame.merge(common,on=keys,validate="many_to_one")
    for (target,method),g in matched.groupby(["target","method"]):paired.append({"target":target,"method":method,**summarize(g)})
    report={"study":"new-baseline-replay-v1","baseline_receipt_sha256":BASELINE_SHA,"statistics_source":stats_receipt,"statistics_decoded_document_sha256":hashlib.sha256(canonical(stats_doc)).hexdigest(),"status_source":status_receipt,"status_decoded_document_sha256":hashlib.sha256(canonical(status_doc)).hexdigest(),"evidence":"original locally recorded pregame baseline; remote publication and provider source timestamp unverified; current-vintage outcomes reconstructed now","missing_original_pooled_ypa_challenger":"NOT_REPRODUCED","frozen_rec_experiment":"not recorded, modified, or scored by this replay","exclusions":excluded,"scores":scores,"matched_population_scores":paired,"promoted":[]}
    (output/"baseline-summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    return report
