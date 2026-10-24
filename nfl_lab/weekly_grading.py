"""Weekly identity/provenance projection around the unchanged live resolver.

No source, fitting, capture or grading runs on import. This module collects no
statistics itself and never orders corrections by local arrival time.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import state

VERSION="weekly-grading-v1"
TARGETS={"pass_yd","pass_td","pass_cmp","pass_att","pass_int","rush_yd","rush_att","rec","rec_yd","rush_rec_yd","anytime_td"}
COUNTS={"pass_td","pass_cmp","pass_att","pass_int","rush_att","rec"}
METADATA=("season","week","game_id","player_id","sleeper_id","position","team","opponent","kickoff_utc","cutoff_utc")


def require(condition,message):
    if not condition:raise ValueError(message)


def binding(path):
    p=Path(path);return dict(path=str(p.absolute()),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def validate_collector_rows(rows):
    require(isinstance(rows,list) and 0<len(rows)<=18000,"finite complete opportunity metadata required")
    seen=set();ids={};result=[]
    for r in rows:
        require(not {"mean","point","forecast_value","actual","loss","label"}&set(r),"numeric forecasts/outcomes are not grading opportunities")
        require(r.get("schema_version")==VERSION+"-opportunity" and r["target"] in TARGETS,"versioned eleven-target opportunity required; PPR blocked")
        require(re.fullmatch(r"00-\d{7}",r["player_id"]) and re.fullmatch(r"[1-9]\d*",r["sleeper_id"])
            and r["game_id"]=="espn:"+r["website_game_id"] and re.fullmatch(r"[1-9]\d*",r["website_game_id"]),"exact frozen GSIS/Sleeper/ESPN identities required")
        require(r["offered_id"]==state.digest(dict(season=r["season"],week=r["week"],game_id=r["original_game_id"],player_id=r["player_id"],category=r["target"])),"original canonical offered identity differs")
        b=r["bridge"]
        require(b["identity_binding_sha256"]==state.digest({k:v for k,v in b.items() if k!="identity_binding_sha256"})
            and r["identity_binding_sha256"]==b["identity_binding_sha256"]
            and all(b[k]==v for k,v in {"gsis_id":r["player_id"],"gsis_game_id":r["original_game_id"],"sleeper_id":r["sleeper_id"],
                "website_game_id":r["website_game_id"],"team":r["team"],"opponent":r["opponent"]}.items())
            and state.utc(b["kickoff_utc"])==state.utc(r["kickoff_utc"]),"frozen complete bridge metadata differs")
        require(type(r["season"]) is int and type(r["week"]) is int and 1<=r["week"]<=18
            and state.utc(r["cutoff_utc"])<state.utc(r["kickoff_utc"]) and r["team"]!=r["opponent"],"frozen period/context/cutoff required")
        key=(r["player_id"],r["game_id"],r["target"])
        require(key not in seen,"duplicate grading opportunity; never last-write-wins");seen.add(key)
        sid=(r["game_id"],r["sleeper_id"])
        require(sid not in ids or ids[sid]==r["player_id"],"conflicting frozen provider identity")
        ids[sid]=r["player_id"];result.append(dict(r))
    return result


def opportunity_rows(queries,bridge_document,role_catalog):
    """Project all original modeled-role offers, independent of predictions."""
    require(set(role_catalog)==TARGETS,"all eleven original role contracts required; PPR excluded")
    bridges={};sleepers={}
    for b in bridge_document["identities"]:
        require(b["identity_binding_sha256"]==state.digest({k:v for k,v in b.items() if k!="identity_binding_sha256"}),"frozen bridge digest differs")
        key=(b["gsis_game_id"],b["gsis_id"])
        require(key not in bridges,"duplicate frozen bridge identity")
        require((b["gsis_game_id"],b["sleeper_id"]) not in sleepers,"ambiguous frozen Sleeper identity")
        bridges[key]=b;sleepers[(b["gsis_game_id"],b["sleeper_id"])]=b["gsis_id"]
    result=[];seen=set()
    for original in queries:
        r={k:original[k] for k in METADATA}  # Never inspect optional forecast/target/roster-status columns.
        key=(r["game_id"],r["player_id"])
        require(key not in seen,"duplicate original query identity");seen.add(key)
        b=bridges.get(key)
        require(b is not None and all(b[k]==v for k,v in {"sleeper_id":r["sleeper_id"],"team":r["team"],"opponent":r["opponent"]}.items())
            and state.utc(b["kickoff_utc"])==state.utc(r["kickoff_utc"]),"query/bridge exact context differs; no name match")
        for target,roles in role_catalog.items():
            require(set(roles)=={"modeled_roles","primary_roles"} and set(roles["primary_roles"])<=set(roles["modeled_roles"]),"original role contract required")
            if r["position"] not in roles["modeled_roles"]:continue
            identity=dict(season=r["season"],week=r["week"],game_id=r["game_id"],player_id=r["player_id"],category=target)
            result.append(dict(r,schema_version=VERSION+"-opportunity",game_id="espn:"+b["website_game_id"],original_game_id=r["game_id"],
                website_game_id=b["website_game_id"],target=target,offered_id=state.digest(identity),
                identity_binding="frozen_exact_weekly_query_bridge",identity_binding_sha256=b["identity_binding_sha256"],
                bridge=b,
                primary_role=r["position"] in roles["primary_roles"]))
    return validate_collector_rows(result)


def stream_root(root,stream):
    require(set(stream)=={"schema_version","stream_id","stream_kind","horizon_version"}
        and stream["schema_version"]==VERSION+"-stream" and stream["stream_kind"] in {"initial_manual","primary_daily"}
        and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}",stream["stream_id"])
        and isinstance(stream["horizon_version"],str) and stream["horizon_version"],"explicit isolated grading stream required")
    return Path(root)/VERSION/stream["stream_id"]


def _source_records(collector_root):
    grouped={}
    for observation in state.records(collector_root,"outcomes"):
        path=Path(collector_root)/"outcomes"/(state.digest(observation)+".json.gz")
        key=(observation["player_id"],observation["game_id"],observation["target"])
        grouped.setdefault(key,[]).append(dict(observation=observation,reference=binding(path)))
    return grouped


def _stored_versions(root):
    completions={r["snapshot_id"]:r for r in state.records(root,"weekly_completions")}
    latest={}
    for snapshot in state.records(root,"weekly_versions"):
        sid=state.digest(snapshot)
        if sid not in completions:raise ValueError("unfinished grading snapshot retained; explicit recovery required")
        for row in snapshot["rows"]:
            projected=dict(row,snapshot_id=sid,available_at=completions[sid]["persisted_completed_at"],actual_known_at=completions[sid]["persisted_completed_at"])
            if row["offered_id"] not in latest or projected["revision"]>latest[row["offered_id"]]["revision"]:latest[row["offered_id"]]=projected
    return latest


def append_resolved(root,stream,opportunities,*,clock=state.now_utc):
    """Existing resolver is authoritative; local time never resolves a conflict."""
    collector=Path(root)/"collector";resolved=state.resolved_outcomes(collector);sources=_source_records(collector)
    previous=_stored_versions(root);changed=[]
    for offered in opportunities:
        key=(offered["player_id"],offered["game_id"],offered["target"]);out=resolved.get(key,{"state":"unknown","actual":None})
        participation="played" if out["state"] in {"played","played_corrected"} else "DNP" if out["state"]=="DNP" else "unknown"
        actual=out["actual"] if participation=="played" else None
        if actual is not None:
            require((offered["target"] not in COUNTS or actual>=0 and float(actual).is_integer())
                and (offered["target"]!="anytime_td" or actual in (0,1)),"resolver outcome outside registered support")
        refs=sorted((x["reference"] for x in sources.get(key,[])),key=lambda r:r["sha256"])
        fingerprint=state.digest(dict(resolution_state=out["state"],actual=actual,participation_state=participation,
            source_observation_content=[{k:r[k] for k in ("bytes","sha256")} for r in refs]))
        old=previous.get(offered["offered_id"])
        if old and old["resolution_fingerprint"]==fingerprint:continue
        changed.append(dict(offered_id=offered["offered_id"],season=offered["season"],week=offered["week"],game_id=offered["original_game_id"],
            player_id=offered["player_id"],category=offered["target"],participation_state=participation,actual=actual,
            primary_role=offered["primary_role"],query_position=offered["position"],team=offered["team"],opponent=offered["opponent"],kickoff_utc=offered["kickoff_utc"],
            revision=old["revision"]+1 if old else 1,resolution_state=out["state"],resolution_fingerprint=fingerprint,
            outcome_state=out["state"] if out["state"].startswith("unresolved") else "DNP" if participation=="DNP" else
                "unknown" if participation=="unknown" else "played_missing_or_unsupported_statistic" if actual is None else "played_zero" if actual==0 else "played_nonzero",
            source_observation_refs=refs,source_body_sha256s=sorted({x["observation"]["source_sha256"] for x in sources.get(key,[])}),
            source_status_sha256s=sorted({x["observation"]["status_sha256"] for x in sources.get(key,[]) if x["observation"].get("status_sha256")}),
            upstream_publication_utc=None,stream_id=stream["stream_id"],stream_kind=stream["stream_kind"],horizon_version=stream["horizon_version"]))
    if changed:
        snapshot=dict(schema_version=VERSION+"-versions",stream=stream,prepared_at=clock().isoformat(),rows=changed)
        sid=state.save(root,"weekly_versions",snapshot)
        completed=clock().isoformat()  # Actual new immutable resolved-body completion, never upstream publication.
        state.save(root,"weekly_completions",dict(schema_version=VERSION+"-completion",snapshot_id=sid,persisted_completed_at=completed))
    return list(_stored_versions(root).values()),len(changed)


def complete_weeks(finality,frozen_schedule,decisions,*,grade_completed_at):
    """One final game cannot establish the full registered week."""
    evidence={(f["season"],f["week"]):f for f in finality};ready=[];pending=[]
    for decision in decisions:
        key=(decision["season"],decision["week"]);expected=[r for r in frozen_schedule if (r["season"],r["week"])==key]
        require(expected and len({r["website_game_id"] for r in expected})==len(expected),"complete unambiguous frozen week schedule required")
        proof=evidence.get(key);games=proof["games"] if proof else []
        ids={g["game_id"] for g in games};want={"espn:"+r["website_game_id"] for r in expected}
        valid=bool(proof) and len(games)==len(ids) and ids==want and all(g["final"] is True for g in games)
        if valid:
            observed=state.utc(proof["observed_at"])
            valid=observed<=state.utc(grade_completed_at) and all(state.utc(g["kickoff_utc"])<observed for g in games)
            by={g["game_id"]:g for g in games}
            valid=valid and all(state.utc(by["espn:"+r["website_game_id"]]["kickoff_utc"])==state.utc(r["kickoff_utc"])
                and {by["espn:"+r["website_game_id"]]["home"],by["espn:"+r["website_game_id"]]["away"]}=={r["home"],r["away"]} for r in expected)
        if valid:
            ready.append(dict(decision,completed_at=proof["observed_at"],grade_completed_at=grade_completed_at,
                finality="OBSERVED_ALL_FROZEN_WEEK_GAMES_FINAL; actual final-publication times unknown",scheduled_games=len(expected),
                status_source_sha256=proof["status_source_sha256"],all_games_final=True))
        else:pending.append(dict(decision,state="PENDING_FULL_WEEK_FINALITY",grade_completed_at=None))
    return ready,pending


def grade_weekly(root,cache,queries,bridge,role_catalog,stream,frozen_schedule,decisions,*,source_policy,storage=None,clock=state.now_utc):
    from . import live
    from .operational_storage import OperationalStorage
    from .operational_sources import load_source_policy
    from .operational_io import operational_io
    policy=load_source_policy(source_policy);store=storage or OperationalStorage(cache,policy,state=root)
    destination=stream_root(root,stream);opportunities=opportunity_rows(queries,bridge,role_catalog)
    with operational_io(store):
        store.register_root(destination)
        # Bind the stream forever; changing horizon/identity population needs a new explicit stream.
        registration=dict(schema_version=VERSION+"-stream-binding",stream=stream,role_catalog_sha256=state.digest(role_catalog))
        old=list(state.records(destination,"weekly_stream"))
        require(not old or old==[registration],"stream binding changed; no merged horizons or population reset")
        if not old:state.save(destination,"weekly_stream",registration)
        bound={r["offered_id"]:r for batch in state.records(destination,"weekly_opportunities") for r in batch["rows"]}
        additions=[]
        for row in opportunities:
            require(row["offered_id"] not in bound or bound[row["offered_id"]]==row,"frozen opportunity changed; no reissuance or last-write-wins")
            if row["offered_id"] not in bound:additions.append(row);bound[row["offered_id"]]=row
        if additions:state.save(destination,"weekly_opportunities",dict(rows=additions))
        contexts=list(state.records(destination,"weekly_contexts"));schedule_by={};decision_by={}
        for context in [*contexts,dict(schedule=frozen_schedule,decisions=decisions)]:
            for r in context["schedule"]:
                key=(r["season"],r["week"],r["website_game_id"])
                require(key not in schedule_by or schedule_by[key]==r,"frozen whole-week schedule changed")
                schedule_by[key]=r
            for r in context["decisions"]:
                require(r["category"] in TARGETS and r["evidence_lane"]=="original_pregame","genuine original weekly decision required")
                key=(r["season"],r["week"],r["category"])
                require(key not in decision_by or decision_by[key]==r,"original weekly choice changed")
                decision_by[key]=r
        context=dict(schedule=frozen_schedule,decisions=decisions)
        if context not in contexts:state.save(destination,"weekly_contexts",context)
        opportunities=validate_collector_rows(list(bound.values()))
        collected=live.grade_opportunity_rows(destination/"collector",cache,{},opportunities,source_policy=policy)
        state.save(destination,"weekly_finality_evidence",dict(weekly_finality=collected["weekly_finality"]))
        outcomes,changed=append_resolved(destination,stream,opportunities,clock=clock)
        grading_clock=clock().isoformat()
        weeks,pending=complete_weeks(collected["weekly_finality"],list(schedule_by.values()),list(decision_by.values()),grade_completed_at=grading_clock)
        prior_weeks={}
        for saved in state.records(destination,"weekly_ready"):
            key=(saved["season"],saved["week"],saved["category"])
            if key not in prior_weeks or saved["revision"]>prior_weeks[key]["revision"]:prior_weeks[key]=saved
        for index,week in enumerate(weeks):
            key=(week["season"],week["week"],week["category"])
            versions=sorted((r["offered_id"],r["revision"]) for r in outcomes if (r["season"],r["week"],r["category"])==key)
            fingerprint=state.digest(dict(decision=decision_by[key],outcome_versions=versions,scheduled_games=week["scheduled_games"],all_games_final=True))
            old=prior_weeks.get(key)
            if old and old["grading_fingerprint"]==fingerprint:weeks[index]=old
            else:
                week.update(grading_fingerprint=fingerprint,revision=old["revision"]+1 if old else 1)
                state.save(destination,"weekly_ready",week)
        report=dict(schema_version=VERSION,stream=stream,collector=collected,outcomes=outcomes,
            panel_outcomes=[r for r in outcomes if r["primary_role"]],weeks=weeks,pending_weeks=pending,
            new_revisions=changed,actual_grading_completed_at=grading_clock,forecasts_captured=0,fits=0,scores=0,
            source_policy_sha256=policy["_policy_sha256"],whole_week_evidence_only=bool(weeks) and not pending)
        # No unchanged row revision/availability is rewritten. Finality receipts are append-only.
        retained={k:v for k,v in report.items() if k not in {"outcomes","panel_outcomes"}}
        retained.update(outcome_rows=len(outcomes),outcome_snapshot_ids=sorted({r["snapshot_id"] for r in outcomes}),
            outcome_storage="Append-only weekly_versions/completions; full row cache is not rewritten")
        state.save(destination,"weekly_grading_receipts",retained)
        return report


def validate_grading_policy(plan,source_policy,store):
    """Bind declaration, supplied policy and the actual active CLI scope."""
    from .operational_sources import load_source_policy
    expected=plan.get("source_policy_sha256")
    require(isinstance(expected,str) and re.fullmatch(r"[0-9a-f]{64}",expected),"sealed source-policy SHA256 required")
    require(store is not None and isinstance(getattr(store,"weekly_grading_policy",None),dict),"actual active grading policy binding required")
    supplied=load_source_policy(source_policy)
    actual=load_source_policy(store.weekly_grading_policy)
    require(expected==supplied.get("_policy_sha256")==actual.get("_policy_sha256")
        and supplied.get("_canonical_policy_sha256")==actual.get("_canonical_policy_sha256"),"sealed/supplied/active source-policy mismatch")
    return supplied


def grading_decisions(choices,freeze,queries,role_catalog,*,decision_ref,freeze_ref,bridge_ref):
    """Explicit original formats only; this projects context, never a new choice."""
    require(isinstance(choices,dict) and isinstance(freeze,dict),"typed original decision/terminal metadata required")
    schema=choices.get("schema_version")
    if schema=="weekly-generic-future-producer-v1-weekly-choice":
        require(freeze["schema_version"]=="weekly-generic-future-producer-v1"
            and freeze.get("decision")==decision_ref,"generic original decision/terminal binding differs")
        return [r["decision"] for r in choices["selections"]]
    require(schema=="weekly-private-selected-policy-v1-decision"
        and freeze["schema_version"]=="weekly-current-inference-capture-v1","unsupported original grading decision format")
    from .weekly_private_selected import CHOICES,SLATE,CUTOFF
    fields={"schema_version","policy_id","policy_state","code_pins_sha256","materialization_started_at","startup_choice_at",
        "shared_feature_persist_completed_at","startup_policy_registered_at","startup_policy","parent_capture","identity_bridge",
        "categories","R0","historical_LAB_CDF_losses","outcome_loss_score_reads","scientifically_qualified",
        "actual_website_board_membership","public_export_authorized","website_activation","private_only"}
    require(set(choices)==fields and choices["parent_capture"]==freeze_ref and choices["identity_bridge"]==bridge_ref
        and choices["startup_policy"]==freeze["startup_policy"] and choices["policy_id"]=="P2"
        and choices["policy_state"]=="STARTUP_NO_COMPARABLE_LIVE_R0_EVIDENCE" and set(choices["categories"])==TARGETS,
        "exact initial decision format/provenance required")
    require(choices["startup_choice_at"]==freeze["weekly_decision_cutoff_utc"]
        and choices["startup_policy_registered_at"]==freeze["startup_policy_registered_at"]
        and state.utc(choices["startup_policy_registered_at"])<=state.utc(choices["startup_choice_at"])
        <=state.utc(freeze["actual_completed_at"])<=state.utc(choices["materialization_started_at"])
        and freeze["input_cutoff_utc"]==CUTOFF
        and all((q["season"],q["week"])==(2026,7) and state.utc(q["cutoff_utc"])==state.utc(CUTOFF) for q in queries),
        "initial original period/cutoff/choice clocks differ")
    first=min(state.utc(q["kickoff_utc"]) for q in queries)
    require(state.utc(choices["startup_choice_at"])<first and state.utc(CUTOFF)<first,"initial authenticated remaining-game horizon differs")
    digest=state.digest(choices);result=[]
    for target,c in choices["categories"].items():
        expected={"LAB_CDF":.5,"CATBOOST_MEDIUM":.5} if CHOICES[target]=="TD_EQUAL_CDF_CAT" else {CHOICES[target]:1.}
        support="bernoulli" if target=="anytime_td" else "count" if target in COUNTS else "signed_integer"
        require(set(c)=={"method_id","model_version","procedure_version","members","primary_roles","support","product"}
            and c["support"]==support and c["product"]=={"count":"point_mean","signed_integer":"point_median","bernoulli":"binary_probability"}[support]
            and c["method_id"]==CHOICES[target] and c["primary_roles"]==role_catalog[target]["primary_roles"]
            and len(c["members"])==len(expected) and {m["method_id"]:m["weight"] for m in c["members"]}==expected,
            "initial original category/member/role identity differs")
        require(all(set(m)=={"method_id","weight","model_version","procedure_version","forecast_body","original_persist_completed_at","projection"}
            and type(m["weight"]) in (int,float) and state.utc(m["original_persist_completed_at"])<=state.utc(freeze["actual_completed_at"])
            for m in c["members"]),"exact original member lineage required")
        result.append(dict(category=target,season=2026,week=7,slate_id=SLATE,horizon="player_game",evidence_lane="original_pregame",
            weekly_decision_cutoff_utc=choices["startup_choice_at"],slate_first_kickoff_utc=first.isoformat(),
            original_decision_sha256=digest,original_decision_binding=decision_ref,
            original_choice_format=schema,original_selected_method_id=c["method_id"],original_selected_members=c["members"],
            original_selected_model_version=c["model_version"],original_selected_procedure_version=c["procedure_version"],
            original_materialization_started_at=choices["materialization_started_at"],
            original_startup_policy_registered_at=choices["startup_policy_registered_at"],
            original_shared_feature_persist_completed_at=choices["shared_feature_persist_completed_at"],
            original_input_cutoff_utc=freeze["input_cutoff_utc"],
            horizon_basis="EXACT_REGISTERED_INITIAL_FORMAT; first kickoff from authenticated original remaining queries"))
    return result


def grade_from_plan(plan_path,plan_sha256,root,cache,*,source_policy):
    """Opt-in existing CLI hook; all transports stay in live._grade_saved."""
    import json
    import resource
    import signal
    from .operational_io import active_storage
    from .owned_reference_batch import validate_owned_references
    body=Path(plan_path).read_bytes()
    require(hashlib.sha256(body).hexdigest()==plan_sha256,"exact grading plan required")
    plan=json.loads(body)
    require(plan["schema_version"]==VERSION+"-plan" and plan["state"]=="FROZEN_ROOT_REVIEWER_SEALED"
        and plan.get("execution_authorized") is True and plan["review"]=={"status":"PREEXEC_PASS","integrator":"/root"},"grading preparation is not execution authority")
    require(plan["budgets"]==dict(CPU_seconds=120,wall_seconds=180,address_space_bytes=1073741824,maximum_queries=1000,
        maximum_opportunities=18000,maximum_REG_periods=18,fits=0,capture=0,retries=0),"exact finite grading allocation required")
    store=active_storage();bound_policy=validate_grading_policy(plan,source_policy,store)
    code_root=Path(__file__).resolve().parents[1]
    import sys
    sys.path.insert(0,str(code_root))  # Same trusted checkout, including under isolated -m execution.
    from tools.weekly_current_query import pin
    for name,expected in plan["code_pins"].items():pin(dict(path=str(code_root/name),sha256=expected))
    resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824))
    def expired(*args):raise TimeoutError("finite grading wall allocation exhausted")
    previous=signal.signal(signal.SIGALRM,expired);signal.alarm(180)
    try:
        refs=plan["inputs"]
        validate_owned_references(store,{refs[k]["path"]:refs[k]["sha256"] for k in ("queries","bridge","schedule","decisions","original_freeze")})
        pin(refs["role_catalog"])
        import pandas as pd
        queries=pd.read_parquet(refs["queries"]["path"],columns=list(METADATA)).to_dict("records")
        require(0<len(queries)<=1000,"complete bounded frozen query cohort required")
        bridge=json.loads(Path(refs["bridge"]["path"]).read_text())
        require(all(b["query_source_sha256"]==refs["queries"]["sha256"] and b["schedule_source_sha256"]==refs["schedule"]["sha256"] for b in bridge["identities"]),"original query/schedule bridge source hashes differ")
        freeze=json.loads(Path(refs["original_freeze"]["path"]).read_text())
        require(freeze["schema_version"] in {"weekly-generic-future-producer-v1","weekly-current-inference-capture-v1"}
            and state.utc(freeze["actual_completed_at"])<=state.now_utc(),"authentic actual original capture/failure metadata required")
        require(all(state.utc(freeze["actual_completed_at"])<state.utc(r["cutoff_utc"]) for r in queries),"original metadata freeze was not actually before input cutoffs")
        roles=json.loads(Path(refs["role_catalog"]["path"]).read_text());roles=roles.get("categories",roles)
        roles={t:{k:roles[t][k] for k in ("modeled_roles","primary_roles")} for t in TARGETS}
        choices=json.loads(Path(refs["decisions"]["path"]).read_text())
        decisions=grading_decisions(choices,freeze,queries,roles,decision_ref=refs["decisions"],
            freeze_ref=refs["original_freeze"],bridge_ref=refs["bridge"])
        periods={(r["season"],r["week"]) for r in queries};require(len(periods)<=18 and len({s for s,w in periods})==1,"one bounded registered NFL season required")
        schedule=pd.read_csv(refs["schedule"]["path"],usecols=["season","week","game_type","game_id","gameday","gametime","home_team","away_team","espn"])
        schedule=schedule.loc[[r.game_type=="REG" and (r.season,r.week) in periods for r in schedule.itertuples()]].copy()
        local=pd.to_datetime(schedule.gameday.astype(str)+" "+schedule.gametime.astype(str),errors="coerce")
        schedule["kickoff_utc"]=local.dt.tz_localize("America/New_York",ambiguous="NaT",nonexistent="NaT").dt.tz_convert("UTC")
        from .weekly_current_query import _sleeper
        from .data import _team
        schedule["home_team"]=_team(schedule.home_team);schedule["away_team"]=_team(schedule.away_team)
        frozen=[dict(season=int(r.season),week=int(r.week),website_game_id=_sleeper(r.espn),kickoff_utc=r.kickoff_utc.isoformat(),home=r.home_team,away=r.away_team) for r in schedule.itertuples()]
        require(all(r["website_game_id"] for r in frozen),"full actual schedule ESPN identity required")
        result=grade_weekly(root,cache,queries,bridge,roles,plan["stream"],frozen,decisions,source_policy=bound_policy,storage=store)
        return dict(schema_version=VERSION,stream_id=plan["stream"]["stream_id"],outcome_rows=len(result["outcomes"]),new_revisions=result["new_revisions"],
            primary_outcome_rows=len(result["panel_outcomes"]),
            ready_week_categories=len(result["weeks"]),pending_week_categories=len(result["pending_weeks"]),forecasts_captured=0,fits=0,scores=0)
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,previous)
