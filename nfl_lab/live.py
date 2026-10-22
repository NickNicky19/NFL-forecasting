"""Bounded public pregame intake. No odds access, LLM calls, or website writes."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .state import append_outcomes, capture, digest, now_utc, records, source_tree_digest, utc

TEAMS={"WSH":"WAS","LA":"LAR","SD":"LAC","OAK":"LV"}
SKILL={"QB","RB","WR","TE","FB"}


def fetch(cache,name,url,day=None):
    from .data import _download
    stamp=day or now_utc().date().isoformat()
    raw=Path(cache)/"raw"/"live"/stamp;raw.mkdir(parents=True,exist_ok=True)
    receipt=_download(raw,name+".json",url)
    return json.loads((raw/(name+".json")).read_text()),receipt


def schedule_games(doc):
    if doc.get("season",{}).get("type")!=2:raise ValueError("not an NFL regular-season schedule")
    games=[]
    for event in doc.get("events",[]):
        comps=event.get("competitions",[])
        if len(comps)!=1:raise ValueError("ambiguous competition")
        comp=comps[0];sides=comp.get("competitors",[])
        if len(sides)!=2:raise ValueError("ambiguous teams")
        teams={c["homeAway"]:TEAMS.get(c["team"]["abbreviation"],c["team"]["abbreviation"]) for c in sides}
        games.append({"game_id":"espn:"+str(event["id"]),"kickoff_utc":utc(event["date"]).isoformat(),
                      "home":teams["home"],"away":teams["away"],"final":comp.get("status",{}).get("type",{}).get("completed") is True,
                      "status":comp.get("status",{}).get("type",{}).get("name")})
    if len({g["game_id"] for g in games})!=len(games):raise ValueError("duplicate schedule identity")
    return games


def future_population(players,games,season,week):
    by_team={}
    for g in games:
        for own,opp in [("home","away"),("away","home")]:by_team[g[own]]={**g,"team":g[own],"opponent":g[opp],"is_home":own=="home"}
    rows=[]
    for sid,p in players.items():
        team=TEAMS.get(p.get("team"),p.get("team"));pos=p.get("position")
        if team not in by_team or pos not in SKILL or p.get("active") is False:continue
        g=by_team[team]
        # An unlinked player retains a stable, explicit namespace and pooled fallback.
        pid=p.get("gsis_id") or "sleeper:"+sid
        rows.append({"season":int(season),"week":int(week),"game_id":g["game_id"],"player_id":pid,
                     "sleeper_id":str(sid),"player_name":p.get("full_name") or p.get("last_name") or pid,
                     "position":pos,"team":team,"opponent":g["opponent"],"is_home":g["is_home"],
                     "kickoff_utc":g["kickoff_utc"],"outcome_available_utc":pd.NaT,"participation_state":"unknown",
                     "injury_status_observed":p.get("injury_status"),"population_eligibility":"current_active_flag_skill_roster; not game-day eligibility proof"})
    frame=pd.DataFrame(rows)
    if frame.empty:return frame
    if frame.duplicated(["player_id","game_id"]).any():raise ValueError("ambiguous player identity")
    return frame


def daily(root:Path,cache:Path,state:Path,seasons:list[int],methods=None):
    from .data import TARGETS, acquire_history,load_history
    from .features import build_features
    from .models import fit_predict
    began=now_utc();methods=methods or ["recent","pooled","workload"]
    status,status_receipt=fetch(cache,"state","https://api.sleeper.app/v1/state/nfl")
    if status.get("season_type")!="regular":return {"state":"OFFSEASON_NO_ISSUANCE"}
    year,week=int(status["season"]),int(status["week"])
    if not 1<=week<=18:raise ValueError("unsupported regular-season week")
    players,player_receipt=fetch(cache,"players","https://api.sleeper.app/v1/players/nfl")
    board,board_receipt=fetch(cache,f"schedule-{year}-{week}",f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}&dates={year}")
    if board.get("week",{}).get("number")!=week or board.get("season",{}).get("year")!=year:raise ValueError("provider schedule period mismatch")
    games=schedule_games(board)
    if not games:raise ValueError("empty schedule population")
    acquisition=acquire_history(cache,seasons)
    history=load_history(cache,seasons)
    live=future_population(players,games,year,week)
    for target in list(TARGETS)+["rec_tgt","rush_td","rec_td"]:live[target]=np.nan
    live["cutoff_utc"]=began.isoformat()
    live["outcome_available_utc"]=pd.to_datetime(live.kickoff_utc,utc=True)+pd.Timedelta(days=7)
    if "cutoff_utc" not in history:history["cutoff_utc"]=history.kickoff_utc
    # Source history uses GSIS, allowing exact matches and explicit unlinked cold starts.
    joined=pd.concat([history,live],ignore_index=True)
    features=build_features(joined)
    test=features.loc[features.game_id.astype(str).str.startswith("espn:")].copy()
    train=features.loc[~features.game_id.astype(str).str.startswith("espn:")].copy()
    available=pd.to_datetime(train.outcome_available_utc,utc=True,errors="coerce")
    train=train.loc[available<began]
    hashes={"state":status_receipt["sha256"],"players":player_receipt["sha256"],"schedule":board_receipt["sha256"],
            "history":digest({r["name"]:r.get("sha256") for r in acquisition["sources"]})}
    input_sha=digest(hashes);code_sha=source_tree_digest(root);out=[];abstentions=[]
    for target in TARGETS:
        for method in methods:
            pred=fit_predict(train,test,target,method)
            for ix,p in pred.iterrows():
                r=test.loc[ix]
                if pd.isna(p["mean"]):abstentions.append({"target":target,"method":method,"reason":str(p.fallback)});continue
                row={"player_id":str(r.player_id),"game_id":str(r.game_id),"team":str(r.team),"opponent":str(r.opponent),
                     "season":year,"week":week,"position":str(r.position),"target":target,
                     "model_id":"lab-v1-"+method,"model_state":"UNQUALIFIED_SHADOW","model_config_sha256":digest(pred.attrs),
                     "scoring_id":"website-offensive-ppr-c8120e3" if target=="fantasy_ppr" else "nfl-full-game-v1",
                     "kickoff_utc":str(r.kickoff_utc),"input_sha256":input_sha,"code_sha256":code_sha,
                     "source_hashes":hashes,"source_timestamp":None,"mean":float(p["mean"]),
                     "prediction_functional":"conditional_played_mean","family":str(p.family),
                     "scale":float(p.scale) if pd.notna(p.scale) else None,"p_participation":float(p.p_participation) if pd.notna(p.p_participation) else None,
                     "fallback":str(p.fallback) if pd.notna(p.fallback) else None,
                     "population_eligibility":"current_active_flag_skill_roster; not game-day proof"}
                out.append(row)
    result=capture(state,out)
    # Archived provider projections are privately cached, never published as a raw feed.
    _,projection_receipt=fetch(cache,f"projections-{year}-{week}",f"https://api.sleeper.app/projections/nfl/{year}/{week}?season_type=regular")
    grade=grade_saved(state,cache,players)
    report={"started_at":began.isoformat(),"completed_at":now_utc().isoformat(),"season":year,"week":week,
            "schedule_games":len(games),"population_rows":len(test),"capture":result,"grading":grade,
            "abstentions":pd.Series([r["target"]+":"+r["reason"] for r in abstentions],dtype=str).value_counts().to_dict(),
            "provider_projection_private_cache_sha256":projection_receipt["sha256"],"future_confirmation":"PENDING",
            "baseline_comparison":"raw provider cached privately; paired score requires exact saved player/game/cutoff binding",
            "recording_scope":"new lab shadow; not rec-half-adjustment-v1"}
    (Path(root)/"runs").mkdir(exist_ok=True)
    (Path(root)/"runs"/"daily.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    return report


def grade_saved(state,cache,players):
    from .scoring import ppr_points
    # Optional exact scoring function is integrated after category-owner acceptance.
    opportunities={}
    for batch in records(state,"forecasts"):
        for r in batch["rows"]:opportunities[(r["player_id"],r["game_id"],r["target"])]=r
    periods=sorted({(r["season"],r["week"]) for r in opportunities.values()})
    identity={p.get("gsis_id") or "sleeper:"+str(sid):str(sid) for sid,p in players.items()}
    obs=[];checked=0
    for season,week in periods:
        if all(utc(r["kickoff_utc"])>=now_utc() for r in opportunities.values() if (r["season"],r["week"])==(season,week)):continue
        board,br=fetch(cache,f"grade-schedule-{season}-{week}",f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}&dates={season}")
        finals={g["game_id"]:g for g in schedule_games(board) if g["final"] and utc(g["kickoff_utc"])<now_utc()}
        stats,sr=fetch(cache,f"stats-{season}-{week}",f"https://api.sleeper.app/stats/nfl/{season}/{week}?season_type=regular")
        entries={str(s["player_id"]):s for s in stats} if isinstance(stats,list) else stats
        for key,r in opportunities.items():
            if (r["season"],r["week"])!=(season,week) or r["game_id"] not in finals:continue
            if utc(finals[r["game_id"]]["kickoff_utc"])!=utc(r["kickoff_utc"]):continue
            checked+=1;s=entries.get(identity.get(r["player_id"]));st=s.get("stats",{}) if isinstance(s,dict) else {}
            # A missing record never establishes DNP; current roster is not past participation evidence.
            played=st.get("gp")==1 or (isinstance(st.get("off_snp"),(int,float)) and st["off_snp"]>0)
            target=r["target"];value=None
            if played:
                if target=="rush_rec_yd" and all(k in st and st[k] is not None for k in ["rush_yd","rec_yd"]):value=st["rush_yd"]+st["rec_yd"]
                elif target=="anytime_td" and all(k in st and st[k] is not None for k in ["rush_td","rec_td"]):value=int(st["rush_td"]+st["rec_td"]>=1)
                elif target=="fantasy_ppr":value=ppr_points(st) # incomplete components remain unresolved
                elif target in st:value=st[target]
            obs.append({"player_id":r["player_id"],"game_id":r["game_id"],"target":target,"actual":value,
                        "participation_state":"played" if played else "unknown","source":"sleeper-stats-nfl",
                        "source_sha256":sr["sha256"],"status_sha256":br["sha256"],"source_timestamp":None,
                        "observed_at":sr["retrieved_utc"],"finality":"independent ESPN completed flag; full-week proof not asserted"})
    result=append_outcomes(state,obs)
    return {**result,"opportunities_checked":checked,"pending_outcomes":len(opportunities)-checked,
            "corrections":"append-only; conflicting unknown-publication-clock values quarantined"}
