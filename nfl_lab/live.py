"""Bounded public pregame intake. No odds access, LLM calls, or website writes."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .state import append_outcomes, capture, digest, now_utc, records, save, source_tree_digest, utc

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


def future_population(players,games,season,week,*,identity_by_sleeper=None,frozen_by_game_sleeper=None):
    by_team={}
    for g in games:
        for own,opp in [("home","away"),("away","home")]:by_team[g[own]]={**g,"team":g[own],"opponent":g[opp],"is_home":own=="home"}
    rows=[]
    for sid,p in players.items():
        team=TEAMS.get(p.get("team"),p.get("team"));pos=p.get("position")
        if team not in by_team or pos not in SKILL or p.get("active") is False:continue
        g=by_team[team]
        # An unlinked player retains a stable, explicit namespace and pooled fallback.
        direct=p.get("gsis_id");crosswalk=(identity_by_sleeper or {}).get(str(sid))
        pid=direct or crosswalk or "sleeper:"+sid
        binding="sleeper_gsis" if direct else "nflverse_exact_id_crosswalk" if crosswalk else "unlinked_cold_start"
        if direct and crosswalk and direct!=crosswalk:pid="sleeper:"+sid;binding="conflicting_identity_cold_start"
        frozen=(frozen_by_game_sleeper or {}).get((g["game_id"],str(sid)))
        if frozen:pid=frozen;binding="frozen_first_sleeper_binding"
        rows.append({"season":int(season),"week":int(week),"game_id":g["game_id"],"player_id":pid,
                     "sleeper_id":str(sid),"identity_binding":binding,"player_name":p.get("full_name") or p.get("last_name") or pid,
                     "position":pos,"team":team,"opponent":g["opponent"],"is_home":g["is_home"],
                     "kickoff_utc":g["kickoff_utc"],"outcome_available_utc":pd.NaT,"participation_state":"unknown",
                     "injury_status_observed":p.get("injury_status"),"population_eligibility":"current_active_flag_skill_roster; not game-day eligibility proof"})
    frame=pd.DataFrame(rows)
    if frame.empty:return frame
    if frame.duplicated(["player_id","game_id"]).any():raise ValueError("ambiguous player identity")
    return frame


def daily(root:Path,cache:Path,state:Path,seasons:list[int],methods=None,*,source_policy=None):
    """A permitted-source failure abstains from issuance and retains grading."""
    if source_policy is None:
        return _daily(root,cache,state,seasons,methods)
    prior_rows=sum(len(batch["rows"]) for batch in records(state,"forecasts"))
    try:
        from .operational_sources import load_source_policy
        policy=load_source_policy(source_policy)
        return _daily(root,cache,state,seasons,methods,source_policy=policy)
    except Exception as error:
        # No legacy history retry and no partial forecast capture on this path.
        try:
            grading=grade_only(state,cache,source_policy=source_policy)["grading"]
        except Exception as grading_error:
            grading={"state":"GRADING_FAILED", "error":type(grading_error).__name__+": "+str(grading_error)[:500]}
        captured_rows=sum(len(batch["rows"]) for batch in records(state,"forecasts"))-prior_rows
        report={"state":"PERMITTED_OPERATION_FAILED_AFTER_ISSUANCE" if captured_rows else "PERMITTED_SOURCE_ISSUANCE_ABSTAINED", "error":type(error).__name__+": "+str(error)[:500],
                "grading":grading,"observed_at":now_utc().isoformat(),"new_forecasts":captured_rows}
        save(state,"health",report)
        return report


def _daily(root:Path,cache:Path,state:Path,seasons:list[int],methods=None,*,source_policy=None):
    from .data import TARGETS, acquire_history,load_history
    from .data import load_identity
    from .features import build_features
    from .models import fit_predict
    from .scoring import SCORING_VERSION
    began=now_utc();methods=methods or ["recent","pooled"]
    if source_policy is not None:
        from .operational_models import methods_for_policy
        methods=methods_for_policy(methods)
    selected={}
    selected_path=Path(root)/"reports/initial-campaign/selected.json"
    if source_policy is None and selected_path.exists():
        selected={r["target"]:r["development_selected_method"] for r in json.loads(selected_path.read_text()) if r.get("development_selected_method")}
    initial_code_sha=source_tree_digest(root)
    status,status_receipt=fetch(cache,"state","https://api.sleeper.app/v1/state/nfl")
    if status.get("season_type")!="regular":
        players,_=fetch(cache,"players","https://api.sleeper.app/v1/players/nfl")
        return {"state":"OFFSEASON_GRADING_ONLY","grading":grade_saved(state,cache,players,**({"source_policy":source_policy} if source_policy is not None else {}))}
    year,week=int(status["season"]),int(status["week"])
    if not 1<=week<=18:raise ValueError("unsupported regular-season week")
    players,player_receipt=fetch(cache,"players","https://api.sleeper.app/v1/players/nfl")
    board,board_receipt=fetch(cache,f"schedule-{year}-{week}",f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}&dates={year}")
    if board.get("week",{}).get("number")!=week or board.get("season",{}).get("year")!=year:raise ValueError("provider schedule period mismatch")
    games=schedule_games(board)
    if not games:raise ValueError("empty schedule population")
    history_limit=None
    if source_policy is not None:
        from .operational_sources import acquire_operational_history,load_operational_history
        from .operational_models import check_operational_storage
        check_operational_storage(cache,source_policy,state=state)
        history_asof=now_utc()
        active_seasons=sorted(set(seasons+[year]))
        acquisition=acquire_operational_history(cache,active_seasons,source_policy,history_asof)
        check_operational_storage(cache,source_policy,state=state)
        history=load_operational_history(cache,active_seasons,source_policy,history_asof)
    else:
        try:
            active_seasons=sorted(set(seasons+[year]))
            acquisition=acquire_history(cache,active_seasons,active_season=year)
            history=load_history(cache,active_seasons)
        except (RuntimeError,ValueError,OSError) as exc:
            # An unavailable current season does not block supported pooled forecasts.
            history_limit="current-season unavailable: "+str(exc)[:500]
            acquisition=acquire_history(cache,seasons)
            history=load_history(cache,seasons)
    stale_sources=acquisition.get("stale_sources",[])
    if stale_sources:history_limit={"fallback":history_limit,"stale_sources":stale_sources}
    website_prepared=None;website_intake={"state":"NOT_ATTEMPTED"}
    try:
        from .website_baselines import prepare_website_snapshot
        website_prepared=prepare_website_snapshot(root,cache,games,year,week)
        website_intake=website_prepared["report"]
    except (OSError,RuntimeError,ValueError,KeyError,TypeError) as exc:
        website_intake={"state":"OPTIONAL_BASELINE_UNAVAILABLE","reason":type(exc).__name__+": "+str(exc)[:300]}
    feature_cutoff=now_utc() # all source responses used here were received by this clock
    if source_policy is None:
        history=history.loc[pd.to_datetime(history.kickoff_utc,utc=True)<feature_cutoff].copy()
    future_games=[g for g in games if utc(g["kickoff_utc"])>feature_cutoff]
    missed_games=[g["game_id"] for g in games if utc(g["kickoff_utc"])<=feature_cutoff]
    if not future_games:
        grade=grade_saved(state,cache,players,**({"source_policy":source_policy} if source_policy is not None else {}))
        report={"state":"GRADING_ONLY_NO_FUTURE_GAMES","grading":grade,"missed_started_games":missed_games,"history_limit":history_limit}
        save(state,"health",{**report,"observed_at":now_utc().isoformat()})
        return report
    if source_policy is not None:
        from .operational_sources import load_operational_identity
        registry=load_operational_identity(cache,active_seasons,source_policy,history_asof)
    else:
        registry=load_identity(cache)
    exact=registry.loc[registry.identity_status.eq("source_exact_binding") & registry.sleeper_id.notna()]
    mapping={str(r.sleeper_id):str(r.player_id) for r in exact.itertuples()}
    frozen={}
    for batch in records(state,"forecasts"):
        for r in batch["rows"]:
            if r.get("sleeper_id"):
                key=(r["game_id"],r["sleeper_id"])
                if key in frozen and frozen[key]!=r["player_id"]:raise ValueError("conflicting frozen canonical identities")
                frozen[key]=r["player_id"]
    live=future_population(players,future_games,year,week,identity_by_sleeper=mapping,frozen_by_game_sleeper=frozen)
    if live.empty:raise ValueError("no eligible future roster population")
    for target in list(TARGETS)+["rec_tgt","rush_td","rec_td"]:live[target]=np.nan
    live["cutoff_utc"]=feature_cutoff.isoformat()
    live["outcome_available_utc"]=pd.to_datetime(live.kickoff_utc,utc=True)+pd.Timedelta(days=7)
    if source_policy is None and "cutoff_utc" not in history:history["cutoff_utc"]=history.kickoff_utc
    # Source history uses GSIS, allowing exact matches and explicit unlinked cold starts.
    if source_policy is not None:
        from .operational_sources import build_operational_features
        operational_manifest=history.attrs["operational_manifest"]
        training_features=build_operational_features(history,policy=source_policy)
        query_features=build_operational_features(history,policy=source_policy,queries=live)
        features=pd.concat([training_features,query_features],ignore_index=True)
    else:
        joined=pd.concat([history,live],ignore_index=True)
        features=build_features(joined)
    test=features.loc[features.game_id.astype(str).str.startswith("espn:")].copy()
    train=features.loc[~features.game_id.astype(str).str.startswith("espn:")].copy()
    available=pd.to_datetime(train.outcome_available_utc,utc=True,errors="coerce")
    train=train.loc[available<feature_cutoff]
    hashes={"state":status_receipt["sha256"],"players":player_receipt["sha256"],"schedule":board_receipt["sha256"],
            "history":digest({r["name"]:r.get("sha256") for r in acquisition["sources"]}) if source_policy is None else operational_manifest["snapshot_sha256"]}
    if source_policy is not None:
        from .operational_models import source_binding,model_binding,fit_operational_reference,predict_operational_artifact,VERSION
        source_contract=source_binding(source_policy,operational_manifest)
        operational_model_version=digest({"policy_sha256":source_contract["policy_sha256"],"code_sha256":source_contract["code_sha256"]})
        hashes.update(source_policy=source_policy["_policy_sha256"],training_view=operational_manifest["training_view_sha256"],
                      operational_binding=digest(source_contract))
    feature_columns=[c for c in test if c.startswith("f_")]+["player_id","game_id","team","opponent","cutoff_utc"]
    feature_sha=hashlib.sha256(pd.util.hash_pandas_object(test[feature_columns],index=True).values.tobytes()).hexdigest()
    input_sha=digest({"sources":hashes,"feature_cutoff":feature_cutoff.isoformat(),"feature_values_sha256":feature_sha});code_sha=initial_code_sha;out=[];abstentions=[]
    input_manifest_sha=save(state,"input_manifests",{"schema_version":"lab-input-manifest-v1","input_sha256":input_sha,
        "feature_cutoff_utc":feature_cutoff.isoformat(),"feature_values_sha256":feature_sha,"code_sha256":code_sha,
        "source_hashes":hashes,"history_acquisition":acquisition,"live_receipts":{"state":status_receipt,"players":player_receipt,"schedule":board_receipt},
        "feature_columns":feature_columns,"schedule_population":games,"population_rows":len(test),
        **({"operational_manifest":operational_manifest} if source_policy is not None else {}),
        "timing_scope":"current responses observed before featurecutoff; historical windows reconstructed; provider publication clocks unknown",
        "scope":"this intake only; no retroactive binding to existing frozen forecasts"})
    existing={tuple(r[k] for k in ["player_id","game_id","target","model_id"]) for batch in records(state,"forecasts") for r in batch["rows"]}
    already_frozen=0;artifact_replays=0
    for target in TARGETS:
        if source_policy is not None and target=="fantasy_ppr":
            abstentions.append({"target":target,"method":"all","reason":"exact_ppr_label_contract_unavailable"});continue
        target_methods=list(dict.fromkeys(methods+([selected[target]] if target in selected else [])))
        for method in target_methods:
            model_id="lab-v1.1-"+method if source_policy is None else VERSION+"-"+operational_model_version[:16]+"-"+method
            needed=np.array([(str(r.player_id),str(r.game_id),target,model_id) not in existing for r in test.itertuples()],dtype=bool)
            already_frozen+=int((~needed).sum())
            if not needed.any():continue
            forecast_test=test.loc[needed]
            artifact=Path(state)/"models"/input_sha/f"{target}-{method}.json" if source_policy is None else Path(state)/"models"/VERSION/hashes["operational_binding"]/input_sha/f"{target}-{method}.json"
            if sum(p.stat().st_size for p in Path(state).rglob("*") if p.is_file())>195*1024*1024:raise RuntimeError("derived state nearing200MiB cap; no evidence removed")
            if source_policy is not None:
                binding=model_binding(source_policy,operational_manifest,train,forecast_test,input_sha)
                pred=fit_operational_reference(train,forecast_test,target,method,artifact_path=artifact,binding=binding)
                check_operational_storage(cache,source_policy,state=state)
                replay=predict_operational_artifact(artifact,forecast_test,binding=binding)
            else:
                pred=fit_predict(train,forecast_test,target,method,artifact_path=artifact)
                from .model_artifacts import predict_artifact
                replay=predict_artifact(artifact,forecast_test,input_manifest={"source_qualified":True,"availability_verified":True,"input_sha256":input_sha,
                          "qualification_scope":"current source responses observed before feature_cutoff; historical source clocks remain reconstructed"})
            for col in ["mean","scale","p10","p50","p90","p_participation"]:
                if not np.allclose(pred[col].to_numpy(float),replay[col].to_numpy(float),rtol=1e-10,atol=1e-9,equal_nan=True):raise ValueError(f"real input artifact replay mismatch:{target}/{method}/{col}")
            if pred.fallback.fillna("").tolist()!=replay.fallback.fillna("").tolist():raise ValueError("real input artifact fallback replay mismatch")
            artifact_replays+=1
            artifact_sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
            for ix,p in pred.iterrows():
                r=test.loc[ix]
                if pd.isna(p["mean"]):abstentions.append({"target":target,"method":method,"reason":str(p.fallback)});continue
                row={"player_id":str(r.player_id),"sleeper_id":str(r.sleeper_id),"identity_binding":str(r.identity_binding),"game_id":str(r.game_id),"team":str(r.team),"opponent":str(r.opponent),
                     "season":year,"week":week,"position":str(r.position),"target":target,"period":"full_game",
                     "model_id":model_id,"model_state":"UNQUALIFIED_SHADOW","model_config_sha256":digest(pred.attrs),
                     "fitted_artifact_sha256":artifact_sha,"fitted_artifact_path":str(artifact.relative_to(state)),
                     "scoring_id":SCORING_VERSION if target=="fantasy_ppr" else "nfl-full-game-v1",
                     "kickoff_utc":utc(r.kickoff_utc).isoformat(),"input_sha256":input_sha,"code_sha256":code_sha,
                     "source_hashes":hashes,"source_timestamp":None,"mean":float(p["mean"]),
                     "feature_cutoff_utc":feature_cutoff.isoformat(),"feature_values_sha256":feature_sha,
                     "input_manifest_sha256":input_manifest_sha,
                     "prediction_functional":"conditional_played_mean","family":str(p.family),
                     "scale":float(p.scale) if pd.notna(p.scale) else None,"p_participation":float(p.p_participation) if pd.notna(p.p_participation) else None,
                     "fallback":str(p.fallback) if pd.notna(p.fallback) else None,
                     "population_eligibility":"current_active_flag_skill_roster; not game-day proof","code_integrity":"pre_post_source_digest_required",
                     "coherence_scope":"conditional scalar marginal; cross-target joint integration not established"}
                if source_policy is not None:
                    row.update(operational_source_binding=binding,participation_probability_status="unavailable_positive_event_panel")
                out.append(row)
    if source_tree_digest(root)!=initial_code_sha:raise RuntimeError("source changed during live calculation; no forecast issuance")
    result=capture(state,out)
    if website_prepared is not None:
        try:
            from .website_baselines import capture_website_bindings
            website_intake=capture_website_bindings(state,website_prepared,result["batch"])
        except (OSError,RuntimeError,ValueError,KeyError,TypeError) as exc:
            website_intake={"state":"OPTIONAL_BASELINE_BINDING_FAILED","reason":type(exc).__name__+": "+str(exc)[:300]}
    # Archived provider projections are privately cached, never published as a raw feed.
    _,projection_receipt=fetch(cache,f"projections-{year}-{week}",f"https://api.sleeper.app/projections/nfl/{year}/{week}?season_type=regular")
    grade=grade_saved(state,cache,players,**({"source_policy":source_policy} if source_policy is not None else {}))
    report={"started_at":began.isoformat(),"completed_at":now_utc().isoformat(),"season":year,"week":week,
            "schedule_games":len(games),"population_rows":len(test),"capture":result,"grading":grade,
            "history_limit":history_limit,"missed_started_games":missed_games,
            "already_frozen_opportunities":already_frozen,"real_input_artifact_replays_passed":artifact_replays,
            "feature_cutoff_utc":feature_cutoff.isoformat(),"feature_values_sha256":feature_sha,
            "abstentions":pd.Series([r["target"]+":"+r["reason"] for r in abstentions],dtype=str).value_counts().to_dict(),
            "provider_projection_private_cache_sha256":projection_receipt["sha256"],"future_confirmation":"PENDING",
            "website_comparator_intake":website_intake,
            "baseline_comparison":"raw provider cached privately; paired score requires exact saved player/game/cutoff binding",
            "recording_scope":"new lab shadow; not rec-half-adjustment-v1"}
    (Path(root)/"runs").mkdir(exist_ok=True)
    (Path(root)/"runs"/"daily.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    save(state,"health",{**report,"observed_at":now_utc().isoformat()})
    return report


def grade_only(state,cache,*,source_policy=None):
    """Delayed/offseason operation: grade saved games, never issue forecasts."""
    player_limit=None
    try:
        players,_=fetch(cache,"players","https://api.sleeper.app/v1/players/nfl")
    except (OSError,RuntimeError,ValueError) as exc:
        # Existing frozen Sleeper IDs remain usable; no name lookup is invented.
        players={};player_limit=type(exc).__name__+": "+str(exc)[:300]
    result={"state":"GRADING_ONLY_NO_PREGAME_ISSUANCE","grading":grade_saved(state,cache,players,**({"source_policy":source_policy} if source_policy is not None else {})),
            "player_source_limit":player_limit,"observed_at":now_utc().isoformat()}
    save(state,"health",result)
    return result


def grade_saved(state,cache,players,*,source_policy=None):
    from .scoring import stat_value
    from .grading_sources import load_cached_grading_context,cached_nflverse_outcome
    opportunities={};identity_conflicts=set();frozen_ids_by_sleeper={}
    for batch in records(state,"forecasts"):
        for r in batch["rows"]:
            opportunities[(r["player_id"],r["game_id"],r["target"])]=r
            if r.get("identity_binding")=="conflicting_identity_cold_start":identity_conflicts.add((r["player_id"],r["game_id"]))
            if r.get("sleeper_id"):
                frozen_ids_by_sleeper.setdefault((r["game_id"],r["sleeper_id"]),set()).add(r["player_id"])
    for (game_id,_),ids in frozen_ids_by_sleeper.items():
        if len(ids)>1:identity_conflicts.update((pid,game_id) for pid in ids)
    opportunities={k:({**r,"identity_binding":"conflicting_identity_cold_start"} if (r["player_id"],r["game_id"]) in identity_conflicts else r) for k,r in opportunities.items()}
    periods=sorted({(r["season"],r["week"]) for r in opportunities.values()})
    candidates={}
    for sid,p in players.items():candidates.setdefault(p.get("gsis_id") or "sleeper:"+str(sid),set()).add(str(sid))
    identity={pid:next(iter(ids)) for pid,ids in candidates.items() if len(ids)==1}
    obs=[];checked=0;context=None;supplement_limit=None;supplement_gaps={};supplement_supported=0
    for season,week in periods:
        if all(utc(r["kickoff_utc"])>=now_utc() for r in opportunities.values() if (r["season"],r["week"])==(season,week)):continue
        board,br=fetch(cache,f"grade-schedule-{season}-{week}",f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={week}&dates={season}")
        if board.get("week",{}).get("number")!=week or board.get("season",{}).get("year")!=season:raise ValueError("grade schedule period mismatch")
        finals={g["game_id"]:g for g in schedule_games(board) if g["final"] and utc(g["kickoff_utc"])<now_utc()}
        if finals and context is None and supplement_limit is None:
            try:
                if source_policy is not None:
                    from .grading_sources import load_permitted_grading_context
                    context=load_permitted_grading_context(cache,sorted({s for s,_ in periods}),source_policy,now_utc())
                else:
                    context=load_cached_grading_context(cache,sorted({s for s,_ in periods}))
            except (OSError,RuntimeError,ValueError,KeyError) as exc:supplement_limit=type(exc).__name__+": "+str(exc)[:500]
        stats,sr=fetch(cache,f"stats-{season}-{week}",f"https://api.sleeper.app/stats/nfl/{season}/{week}?season_type=regular")
        entries={str(s["player_id"]):s for s in stats} if isinstance(stats,list) else stats
        for key,r in opportunities.items():
            if (r["season"],r["week"])!=(season,week) or r["game_id"] not in finals:continue
            if utc(finals[r["game_id"]]["kickoff_utc"])!=utc(r["kickoff_utc"]):continue
            game=finals[r["game_id"]]
            if {game["home"],game["away"]}!={r["team"],r["opponent"]}:continue
            checked+=1;s=entries.get(r.get("sleeper_id") or identity.get(r["player_id"]));st=s.get("stats",{}) if isinstance(s,dict) else {}
            if isinstance(s,dict):
                if s.get("season") is not None and int(s["season"])!=season:raise ValueError("statistics season mismatch")
                if s.get("week") is not None and int(s["week"])!=week:raise ValueError("statistics week mismatch")
                recorded_team=s.get("team") or (s.get("player") or {}).get("team")
                if recorded_team and TEAMS.get(recorded_team,recorded_team)!=r["team"]:st={}
            # A missing record never establishes DNP; current roster is not past participation evidence.
            played=st.get("gp")==1 or (isinstance(st.get("off_snp"),(int,float)) and st["off_snp"]>0)
            target=r["target"];value=None
            if played:
                value=stat_value(target,st)
                if target in ["pass_cmp","pass_att","pass_td","pass_int","rush_att","rec"] and value is not None and not float(value).is_integer():value=None
            obs.append({"player_id":r["player_id"],"game_id":r["game_id"],"target":target,"actual":value,
                        "participation_state":"played" if played else "unknown","source":"sleeper-stats-nfl",
                        "source_sha256":sr["sha256"],"status_sha256":br["sha256"],"source_timestamp":None,
                        "observed_at":sr["retrieved_utc"],"finality":"independent ESPN completed flag; full-week proof not asserted"})
            if r.get("identity_binding")=="conflicting_identity_cold_start":
                obs[-1].update(actual=None,participation_state="unknown",identity_quarantined=True,
                               identity_gap="conflicting_frozen_provider_identity")
            if context is not None:
                supplemental=cached_nflverse_outcome(context,r,{**game,"season":season,"week":week},br)
                if supplemental.get("supplement_status")=="supported":supplement_supported+=1
                else:
                    reason=supplemental.get("gap_reason","unknown")
                    supplement_gaps[reason]=supplement_gaps.get(reason,0)+1
                    if reason in {"conflicting_frozen_provider_identity","conflicting_frozen_gsis_sleeper_binding"}:
                        # Preserve the raw receipt privately; an unbound value
                        # must not grade a different canonical player.
                        obs[-1].update(actual=None,participation_state="unknown",identity_quarantined=True,
                                       identity_gap=reason,identity_registry_sha256=digest({k:v["sha256"] for k,v in context["receipts"].items()}))
                # Unsupported bindings do not create unproven observations.
                # Valid missing/DNP observations remain explicit, without zeros.
                if supplemental.get("source_sha256") and supplemental.get("observed_at"):
                    obs.append(supplemental)
    result=append_outcomes(state,obs)
    from .state import resolved_outcomes
    resolved=resolved_outcomes(state);coverage={"supported_played":0,"known_DNP":0,"missing_played_statistic":0,"unknown_or_unobserved":0,"conflicts":0}
    for key in opportunities:
        outcome=resolved.get(key,{"state":"unknown","actual":None})
        if outcome["state"] in ["played","played_corrected"]:
            coverage["supported_played" if outcome.get("actual") is not None else "missing_played_statistic"]+=1
        elif outcome["state"]=="DNP":coverage["known_DNP"]+=1
        elif outcome["state"].startswith("unresolved"):coverage["conflicts"]+=1
        else:coverage["unknown_or_unobserved"]+=1
    pending=len(opportunities)-coverage["supported_played"]-coverage["known_DNP"]
    return {**result,"opportunities_checked":checked,"pending_outcomes":pending,
            "pending_final_game_opportunities":len(opportunities)-checked,"outcome_coverage":coverage,
            "nflverse_supported":supplement_supported,"nflverse_gaps":supplement_gaps,"nflverse_limit":supplement_limit,
            "corrections":"append-only; conflicting unknown-publication-clock values quarantined"}
