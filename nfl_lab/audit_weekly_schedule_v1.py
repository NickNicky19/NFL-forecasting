"""Existing-cadence, metadata-only weekly dispatch preparation.

No activation on import/preparation. The parent supplies a sealed operational
registration and a pinned callback which REALLY validates readiness, complete
schedule/choice metadata and a durable atomic claim. This module cannot confer
readiness or replace the old safety guard. A successful dispatch is an enqueue,
never a completed capture. The child verifies the completed parent later.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timedelta,timezone
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,HTTPRedirectHandler,build_opener
from zoneinfo import ZoneInfo

from .cadence import decision as cadence

VERSION="audit-weekly-schedule-v1"
MODE="audit-weekly-producer-v1"
REPOSITORY="NickNicky19/NFL-forecasting"
API="https://api.github.com/repos/"+REPOSITORY
WORKFLOW=".github/workflows/lab.yml"
CHICAGO=ZoneInfo("America/Chicago")
CADENCE=dict(timezone="America/Chicago",hour=8,minute_first=36,minute_last=56,existing_UTC_cron="36 13,14 * * *",
    concurrency_group="nfl-lab-single-writer",cancel_in_progress=False)
LIMITS=dict(CPU_seconds=120,wall_seconds=180,address_space_bytes=512 << 20,HTTP_calls=20,dispatches=1,retries=0,
    schedule_rows=512,root_bytes=16 << 10,model_decodes=0,fits=0,outcome_reads=0,publication=0)
POLICY=dict(history_lag_seconds=7*86400,source_window_seconds=1200,kickoff_buffer_seconds=300,minimum_execution_seconds=120)
PIN_PATHS=("nfl_lab/audit_weekly_schedule_v1.py","tools/audit_weekly_schedule_v1.py","tests/test_audit_weekly_schedule_v1.py",
    "nfl_lab/cadence.py","tools/hosted_safety_guard.py",WORKFLOW)
BINDINGS={"source_sha","source_pins","operational_registration_sha256","readiness_proof_sha256","scheduled_parent","schedule_plan",
    "schedule_plan_sha256","dispatch_claim_id","issued_at_utc","expires_at_utc","maximum_new_fits"}
REG_KEYS={"schema_version","approved","state","repository","workflow","cadence","limits","capture_policy",
    "parent_source_sha","parent_job_id","actors","producer_branch","producer_source_sha","producer_source_pins",
    "helper_sha256","builder","readiness_proof_sha256","root_template","root_bindings","root_lifetime_seconds"}
CALLBACK_KEYS={"schema_version","ready","registration_sha256","parent_sha256","plan_sha256","readiness_proof_sha256",
    "schedule_metadata_verified","choice_evidence","claim","root_go"}


class ScheduleError(ValueError):pass


def require(value,code):
    if not value:raise ScheduleError(code)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def digest(value):return sha(canonical(value))
def utc(value):
    result=value if isinstance(value,datetime) else datetime.fromisoformat(value.replace("Z","+00:00"))
    require(result.tzinfo is not None,"AWARE_SCHEDULE_CLOCK_REQUIRED");return result.astimezone(timezone.utc)
def now():return datetime.now(timezone.utc)
def hashed(value):return type(value) is str and re.fullmatch("[a-f0-9]{64}",value) is not None
def source(value):return type(value) is str and re.fullmatch("[a-f0-9]{40}",value) is not None
def actor_matches(value,expected):return type(value) is dict and value.get("login")==expected["login"] and type(value.get("id")) is int and value["id"]==expected["id"]


def read(path,cap=512 << 10):
    path=Path(path)
    require(not any(p.is_symlink() for p in (path,*path.parents)),"SCHEDULE_LOCAL_SYMLINK_FORBIDDEN")
    with path.open("rb") as stream:body=stream.read(cap+1)
    require(len(body)<=cap,"BOUNDED_SCHEDULE_METADATA_FILE");return body


def decode(body):
    def pairs(items):
        result={}
        for key,value in items:require(key not in result,"DUPLICATE_SCHEDULE_JSON_KEY");result[key]=value
        return result
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ScheduleError("NONFINITE_SCHEDULE_METADATA")))


def write_once(path,value):
    body=canonical(value);path=Path(path)
    require(not any(p.is_symlink() for p in (path,*path.parents)),"SCHEDULE_LOCAL_SYMLINK_FORBIDDEN")
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(parent)
    finally:os.close(parent)
    return dict(bytes=len(body),sha256=sha(body))


def pins(root):return {name:sha(read(Path(root)/name,2 << 20)) for name in PIN_PATHS}


def capture_policy(policy):
    require(type(policy) is dict and set(policy)==set(POLICY) and policy["history_lag_seconds"]==604800
        and all(type(v) is int for v in policy.values()) and 60<=policy["minimum_execution_seconds"]<=policy["source_window_seconds"]<=3600
        and 60<=policy["kickoff_buffer_seconds"]<=3600,"FINITE_PREGAME_SEVEN_DAY_HISTORY_POLICY")
    return policy


def root_metadata(value):
    def visit(v,depth):
        require(depth<=12,"FINITE_ROOT_METADATA_DEPTH")
        if type(v) is dict:
            require(len(v)<=256 and all(type(k) is str for k in v),"BOUNDED_ROOT_METADATA_OBJECT")
            require(not {"authorization","github_token","token","access_token","password","private_key","content_b64","model_bytes","forecast_rows","outcomes","players"}&{k.lower() for k in v},
                "ROOT_METADATA_ONLY_NO_SECRETS_OR_PRIVATE_BODIES")
            for item in v.values():visit(item,depth+1)
        elif type(v) is list:
            require(len(v)<=256,"BOUNDED_ROOT_METADATA_LIST")
            for item in v:visit(item,depth+1)
        else:require(v is None or type(v) in (str,int,float,bool),"JSON_ROOT_METADATA_VALUES_ONLY")
    visit(value,0);require(len(canonical(value))<=LIMITS["root_bytes"],"FINITE_REGISTERED_ROOT_METADATA")


def template(root):
    return dict(schema_version=VERSION+"-registration",approved=False,state="BLOCKED_REAL_READINESS_AND_PARENT_REGISTRATION_REQUIRED",
        repository=REPOSITORY,workflow=WORKFLOW,cadence=dict(CADENCE),limits=dict(LIMITS),capture_policy=dict(POLICY),
        parent_source_sha=None,parent_job_id=None,actors={},producer_branch=None,producer_source_sha=None,producer_source_pins={},
        helper_sha256=pins(root),builder=dict(path=None,callable=None,sha256=None),readiness_proof_sha256=None,
        root_template=None,root_bindings={key:None for key in sorted(BINDINGS)},root_lifetime_seconds=3600)


def registration(p,root):
    require(type(p) is dict and set(p)==REG_KEYS and p["schema_version"]==VERSION+"-registration" and p["approved"] is True
        and p["state"]=="OWNER_SEALED_OPERATIONAL_READY" and p["repository"]==REPOSITORY and p["workflow"]==WORKFLOW
        and p["cadence"]==CADENCE and p["limits"]==LIMITS and p["helper_sha256"]==pins(root),"SEALED_REAL_OPERATIONAL_REGISTRATION_REQUIRED")
    require(source(p["parent_source_sha"]) and source(p["producer_source_sha"]) and type(p["parent_job_id"]) is str
        and re.fullmatch("[A-Za-z0-9_-]{1,100}",p["parent_job_id"]) and type(p["producer_branch"]) is str
        and re.fullmatch("[A-Za-z0-9][A-Za-z0-9._/-]{0,159}",p["producer_branch"])
        and all(part not in {"",".",".."} and not part.endswith(".lock") for part in p["producer_branch"].split("/")),"EXACT_REGISTERED_PARENT_AND_PRODUCER_SOURCE")
    require(type(p["actors"]) is dict and p["actors"] and set(p["actors"])<={"schedule","workflow_dispatch"},"EXPLICIT_REGISTERED_SCHEDULER_ACTORS")
    for actor in p["actors"].values():
        require(type(actor) is dict and set(actor)=={"login","id"} and type(actor["login"]) is str and re.fullmatch(r"[A-Za-z0-9_-]+(?:\[bot\])?",actor["login"])
            and type(actor["id"]) is int and actor["id"]>0,"CLOSED_SCHEDULER_ACTOR_POLICY")
    capture_policy(p["capture_policy"])
    b=p["builder"]
    require(type(b) is dict and set(b)=={"path","callable","sha256"} and type(b["path"]) is str
        and re.fullmatch(r"(?:tools|nfl_lab)/[A-Za-z0-9_]+\.py",b["path"]) and hashed(b["sha256"])
        and re.fullmatch("[A-Za-z][A-Za-z0-9_]{0,95}",str(b["callable"])) and sha(read(Path(root)/b["path"],2 << 20))==b["sha256"],
        "PINNED_PARENT_METADATA_CALLBACK_REQUIRED")
    require(type(p["producer_source_pins"]) is dict and p["producer_source_pins"] and len(p["producer_source_pins"])<=128
        and all(type(k) is str and not Path(k).is_absolute() and ".." not in Path(k).parts and hashed(v) for k,v in p["producer_source_pins"].items())
        and hashed(p["readiness_proof_sha256"]) and type(p["root_template"]) is dict and 0<len(canonical(p["root_template"]))<=LIMITS["root_bytes"]
        and type(p["root_lifetime_seconds"]) is int and 180<=p["root_lifetime_seconds"]<=3600,"REGISTERED_SOURCE_PINS_READINESS_AND_FINITE_ROOT_TEMPLATE")
    paths=p["root_bindings"]
    require(type(paths) is dict and set(paths)==BINDINGS and all(type(v) is list and 1<=len(v)<=8
        and all(type(part) is str and re.fullmatch("[A-Za-z][A-Za-z0-9_]{0,95}",part) for part in v) for v in paths.values()),"CLOSED_PARENT_ROOT_BINDING_PATHS")
    tuples=[tuple(v) for v in paths.values()]
    require(len(set(tuples))==len(tuples) and not any(a!=b and a==b[:len(a)] for a in tuples for b in tuples),"NONOVERLAPPING_ROOT_BINDING_PATHS")
    for path in paths.values():get_path(p["root_template"],path)
    root_metadata(p["root_template"])
    return p


def schedule_rows(rows):
    require(type(rows) is list and 0<len(rows)<=LIMITS["schedule_rows"],"BOUNDED_FULL_SCHEDULE_METADATA_REQUIRED")
    result=[];seen=set()
    for row in rows:
        require(type(row) is dict and not {"actual","label","loss","outcome","home_score","away_score","result","forecast_value"}&set(row),
            "SCHEDULE_METADATA_ONLY_NO_OUTCOMES")
        item={key:row[key] for key in ("season","week","game_type","game_id","kickoff_utc")}
        require(type(item["season"]) is int and 2000<=item["season"]<=2200 and type(item["week"]) is int
            and 1<=item["week"]<=22 and item["game_type"] in {"REG","POST","PRE"} and type(item["game_id"]) is str
            and 0<len(item["game_id"])<=100 and item["game_id"] not in seen,"UNIQUE_TYPED_FULL_SCHEDULE_METADATA")
        seen.add(item["game_id"]);item["kickoff_utc"]=utc(item["kickoff_utc"]).isoformat();result.append(item)
    return sorted(result,key=lambda r:(r["kickoff_utc"],r["game_id"]))


def plan(rows,*,season,week,at,event="schedule",policy=None):
    """Timing proposal only. Caller supplies/authenticates the FULL schedule."""
    at=utc(at);policy=capture_policy(dict(POLICY if policy is None else policy));rows=schedule_rows(rows)
    require(event in {"schedule","workflow_dispatch"},"REGISTERED_SCHEDULE_OR_EXPLICIT_MANUAL_EVENT_ONLY")
    games=[r for r in rows if (r["season"],r["week"],r["game_type"])==(season,week,"REG")]
    require(games and type(week) is int and 1<=week<=18,"FULL_REQUESTED_REGULAR_WEEK_SCHEDULE_REQUIRED")
    first=min(utc(g["kickoff_utc"]) for g in games);deadline=first-timedelta(hours=6)
    gate=cadence(event,"daily",at)  # Existing DST gate only; never Sunday's fit mode.
    future=[];elapsed=[];blocked=[];cutoffs={}
    for game in games:
        kickoff=utc(game["kickoff_utc"]);gid=game["game_id"]
        if kickoff<=at:elapsed.append(gid);continue
        future.append(gid);cutoff=min(at+timedelta(seconds=policy["source_window_seconds"]),kickoff-timedelta(seconds=policy["kickoff_buffer_seconds"]))
        if cutoff-at<timedelta(seconds=policy["minimum_execution_seconds"]):blocked.append(gid)
        else:cutoffs[gid]=cutoff.isoformat()
    state="TIMING_CANDIDATE_REQUIRES_AUTHENTICATED_READINESS"
    if not gate["due"]:state="MISSED_SCHEDULE_WINDOW_NOT_BACKFILLED"
    elif not future:state="NO_FUTURE_GAMES"
    elif blocked:state="FUTURE_GAME_TOO_CLOSE_NO_SILENT_OMISSION"
    elif at>=deadline:state="MISSED_WEEKLY_DEADLINE_EXISTING_PREDEADLINE_CHOICE_REQUIRED"
    return dict(schema_version=VERSION+"-plan",state=state,planned_at_utc=at.isoformat(),observed_chicago=at.astimezone(CHICAGO).isoformat(),
        event=event,mode=MODE,season=season,week=week,schedule_sha256=digest(rows),full_week_games=len(games),
        first_full_week_kickoff_utc=first.isoformat(),weekly_decision_deadline_utc=deadline.isoformat(),
        future_game_ids=future,elapsed_game_ids=elapsed,blocked_future_game_ids=blocked,source_cutoffs_utc=cutoffs,
        history_information_before_utc=(at-timedelta(seconds=policy["history_lag_seconds"])).isoformat(),history_lag_seconds=604800,
        history_purpose="EARLIER_REG_WEEKS_WITH_GENUINE_AVAILABILITY_AND_SEVEN_DAY_LAG_NOT_CURRENT_OUTCOMES",
        horizon="INITIAL_OR_CONTINUATION_PLAYER_GAME_CAPTURE_NOT_REGISTERED_EXACT_HORIZON",maximum_new_fits=0,
        schedule_completeness="REQUIRES_PARENT_AUTHENTICATION_OF_FULL_SUPPLIED_METADATA",execution_authorized=False)


def horizon_proposal(rows,*,season,week):
    rows=schedule_rows(rows);events=[]
    for row in rows:
        if (row["season"],row["week"],row["game_type"])!=(season,week,"REG"):continue
        kickoff=utc(row["kickoff_utc"])
        for horizon,seconds in (("T24",86400),("T6",21600),("T90",5400)):
            target=kickoff-timedelta(seconds=seconds);local=target.astimezone(CHICAGO)
            daily=local.replace(hour=8,minute=36,second=0,microsecond=0)
            events.append(dict(game_id=row["game_id"],horizon=horizon,desired_capture_utc=target.isoformat(),desired_chicago=local.isoformat(),
                same_day_daily_tick_utc=daily.astimezone(timezone.utc).isoformat(),daily_tick_offset_seconds=int((daily-target).total_seconds())))
    require(events and len(events)<=48,"FINITE_FULL_WEEK_HORIZON_PROPOSAL")
    return dict(schema_version=VERSION+"-horizon-proposal",state="POLICY_REGISTRATION_REQUIRED_NO_ACTIVATION",events=events,
        existing_workflow=WORKFLOW,existing_concurrency_group=CADENCE["concurrency_group"],additional_cron_activated=False,
        daily_cadence_guarantees_T24_T6_T90=False,claim_policy="ACTUAL_CAPTURE_CLOCK_AND_REGISTERED_HORIZON_WINDOW_REQUIRED; NO BACKFILL",
        initial_player_game_capture_is_exact_horizon=False)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Client:
    """Bounded automatic-token metadata transport; exactly one dispatch POST."""
    def __init__(self,token,*,transport=None):
        require(type(token) is str and token.startswith("ghs_"),"AUTOMATIC_ACTIONS_TOKEN_ONLY")
        self._token=token;self.transport=transport;self.allowed=set();self.calls=0;self.post_attempted=False
    def allow(self,url):
        require(url.startswith(API+"/") and not any(c in url.lower() for c in ("\n","\r","#","..","%2e","\\")),"EXACT_REPOSITORY_METADATA_ROUTE")
        relative=url[len(API)+1:]
        require(re.fullmatch(r"actions/runs/[1-9][0-9]{0,19}(?:/jobs\?per_page=100&page=1|/artifacts\?per_page=100&page=1)?",relative)
            or re.fullmatch(r"check-runs/[1-9][0-9]{0,19}",relative)
            or re.fullmatch(r"contents/(?:\.github/|nfl_lab/|tools/|config/|schemas/)[A-Za-z0-9_./-]+\?ref=[a-f0-9]{40}",relative)
            or re.fullmatch(r"git/ref/heads/[A-Za-z0-9_./%-]+",relative)
            or relative=="actions/workflows/lab.yml/dispatches","METADATA_ONLY_SCHEDULE_API_ROUTES")
        self.allowed.add(url);return url
    def request(self,url,*,body=None):
        require(url in self.allowed and self.calls<LIMITS["HTTP_calls"],"BOUNDED_ALLOWED_SCHEDULE_API")
        if body is not None:
            require(url==API+"/actions/workflows/lab.yml/dispatches" and not self.post_attempted,"ONE_SCHEDULE_DISPATCH_NO_RETRY")
            self.post_attempted=True
        self.calls+=1
        req=Request(url,data=body,method="POST" if body is not None else "GET",headers={"Authorization":"Bearer "+self._token,
            "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
        if self.transport:response=self.transport(req,20)
        else:
            try:response=build_opener(NoRedirect()).open(req,timeout=20)
            except HTTPError as error:response=error
        with response:
            status=response.status;headers={k.lower():v for k,v in response.headers.items()};raw=response.read((256 << 10)+1)
        require(len(raw)<=256 << 10,"SCHEDULE_API_METADATA_BOUND")
        if body is None:require(status==200 and "retry-after" not in headers and headers.get("x-ratelimit-remaining")!="0","SCHEDULE_METADATA_HTTP_GUARD")
        return status,raw
    def get(self,url):return decode(self.request(self.allow(url))[1])


def get_path(value,path):
    for part in path:require(type(value) is dict and part in value,"REGISTERED_ROOT_BINDING_PATH_REQUIRED");value=value[part]
    return value


def put_path(value,path,replacement):
    target=value
    for part in path[:-1]:target=target[part]
    target[path[-1]]=deepcopy(replacement)


def actual_parent(api,p,env,root):
    require(env.get("GITHUB_ACTIONS")=="true" and env.get("CI")=="true" and env.get("GITHUB_REPOSITORY")==REPOSITORY
        and env.get("GITHUB_RUN_ATTEMPT")=="1" and env.get("GITHUB_EVENT_NAME") in p["actors"]
        and env.get("GITHUB_SHA")==env.get("GITHUB_WORKFLOW_SHA")==p["parent_source_sha"]
        and env.get("GITHUB_JOB")==p["parent_job_id"],"GENUINE_REGISTERED_CURRENT_SCHEDULER_JOB")
    actor=p["actors"][env["GITHUB_EVENT_NAME"]]
    require(env.get("GITHUB_ACTOR")==actor["login"] and env.get("GITHUB_ACTOR_ID")==str(actor["id"]),"REGISTERED_ACTUAL_SCHEDULER_ACTOR")
    require(subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()==p["parent_source_sha"]
        and subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",".github","nfl_lab","tools","config","schemas","requirements.lock"],cwd=root,text=True)=="",
        "CLEAN_EXACT_SCHEDULER_SOURCE")
    run_id=env.get("GITHUB_RUN_ID","");require(re.fullmatch("[1-9][0-9]{0,19}",run_id),"ACTUAL_SCHEDULER_RUN_ID")
    base=API+"/actions/runs/"+run_id;run=api.get(base);jobs=api.get(base+"/jobs?per_page=100&page=1")
    require(run.get("id")==int(run_id) and run.get("head_sha")==p["parent_source_sha"] and run.get("event")==env["GITHUB_EVENT_NAME"]
        and run.get("run_attempt")==1 and run.get("status")=="in_progress" and run.get("conclusion") is None
        and run.get("path")==WORKFLOW and run.get("repository",{}).get("full_name")==run.get("head_repository",{}).get("full_name")==REPOSITORY
        and actor_matches(run.get("actor"),actor) and env.get("GITHUB_WORKFLOW_REF")==REPOSITORY+"/"+WORKFLOW+"@refs/heads/"+run["head_branch"],
        "ACTUAL_CURRENT_SCHEDULER_API_RUN_SOURCE_EVENT_ACTOR")
    require(type(jobs.get("jobs")) is list and jobs.get("total_count")==len(jobs["jobs"])<=100,"COMPLETE_CURRENT_SCHEDULER_JOB_LIST")
    found=[j for j in jobs["jobs"] if j.get("name")==p["parent_job_id"] and j.get("run_id")==int(run_id)
        and j.get("head_sha")==p["parent_source_sha"] and j.get("status")=="in_progress"]
    require(len(found)==1 and type(found[0].get("id")) is int and found[0]["id"]>0,"EXACT_CURRENT_SCHEDULER_API_JOB")
    local=read(Path(root)/WORKFLOW,256 << 10)
    doc=api.get(API+"/contents/"+WORKFLOW+"?ref="+p["parent_source_sha"])
    require(doc.get("type")=="file" and doc.get("path")==WORKFLOW and doc.get("encoding")=="base64"
        and base64.b64decode(doc["content"].replace("\n",""),validate=True)==local,"ACTUAL_API_SCHEDULER_WORKFLOW_BYTES")
    import yaml
    wf=yaml.safe_load(local);job=wf["jobs"][p["parent_job_id"]];perms=job.get("permissions",wf.get("permissions",{}))
    require(type(perms) is dict and perms.get("actions")=="write" and wf.get("concurrency")==dict(group=CADENCE["concurrency_group"],**{"cancel-in-progress":False}),
        "EXISTING_GROUP_AND_REGISTERED_ACTIONS_WRITE_REQUIRED")
    return dict(schema_version=VERSION+"-parent",repository=REPOSITORY,run_id=run_id,run_attempt=1,source_sha=p["parent_source_sha"],
        workflow_ref=env["GITHUB_WORKFLOW_REF"],event=env["GITHUB_EVENT_NAME"],actor=actor,job_id=p["parent_job_id"],api_job_id=found[0]["id"],
        job_started_at=found[0]["started_at"],workflow_sha256=sha(local),verified_at_utc=now().isoformat(),
        state="AUTHENTICATED_RUNNING_PARENT_CHILD_MUST_VERIFY_COMPLETION_LATER")


def producer_head(api,p):
    value=api.get(API+"/git/ref/heads/"+quote(p["producer_branch"],safe="/"))
    require(value.get("ref")=="refs/heads/"+p["producer_branch"] and value.get("object",{}).get("type")=="commit"
        and value["object"].get("sha")==p["producer_source_sha"],"EXACT_REGISTERED_CURRENT_PRODUCER_BRANCH_HEAD")


def context(p,proposal,parent,*,at):
    claim=digest(dict(registration_sha256=digest(p),producer_source_sha=p["producer_source_sha"],
        chicago_date=utc(proposal["planned_at_utc"]).astimezone(CHICAGO).date().isoformat(),season=proposal["season"],week=proposal["week"],purpose=proposal["horizon"]))
    return dict(source_sha=p["producer_source_sha"],source_pins=p["producer_source_pins"],operational_registration_sha256=digest(p),
        readiness_proof_sha256=p["readiness_proof_sha256"],scheduled_parent=parent,schedule_plan=proposal,schedule_plan_sha256=digest(proposal),dispatch_claim_id=claim,
        issued_at_utc=utc(at).isoformat(),expires_at_utc=(utc(at)+timedelta(seconds=p["root_lifetime_seconds"])).isoformat(),maximum_new_fits=0)


def dispatch(p,rows,*,season,week,api,env,root,intent_path,metadata_callback,clock=now):
    registration(p,root);at=utc(clock());proposal=plan(rows,season=season,week=week,at=at,event=env.get("GITHUB_EVENT_NAME"),policy=p["capture_policy"])
    if proposal["state"] in {"MISSED_SCHEDULE_WINDOW_NOT_BACKFILLED","NO_FUTURE_GAMES","FUTURE_GAME_TOO_CLOSE_NO_SILENT_OMISSION"}:
        return dict(state=proposal["state"],plan_sha256=digest(proposal),dispatches=0,fits=0)
    parent=actual_parent(api,p,env,root);producer_head(api,p);ctx=context(p,proposal,parent,at=clock())
    # Parent callback authenticates actual readiness, the FULL schedule and an
    # existing atomic durable claim. It receives only a GET view of our client.
    result=metadata_callback(deepcopy(p),deepcopy(proposal),deepcopy(parent),deepcopy(ctx),api_get=api.get)
    require(type(result) is dict and set(result)==CALLBACK_KEYS and result["schema_version"]==VERSION+"-readiness-and-claim"
        and result["ready"] is result["schedule_metadata_verified"] is True and result["registration_sha256"]==digest(p)
        and result["parent_sha256"]==digest(parent) and result["plan_sha256"]==digest(proposal)
        and result["readiness_proof_sha256"]==p["readiness_proof_sha256"],"AUTHENTICATED_PARENT_READINESS_CALLBACK_REQUIRED")
    claim=result["claim"]
    require(type(claim) is dict and set(claim)=={"claim_id","parent_run_id","parent_api_job_id","proof_sha256","state","previous_dispatch_attempts"}
        and claim["claim_id"]==ctx["dispatch_claim_id"] and claim["parent_run_id"]==parent["run_id"] and claim["parent_api_job_id"]==parent["api_job_id"]
        and claim["state"]=="DURABLE_ATOMIC_CLAIM_VERIFIED" and hashed(claim["proof_sha256"])
        and type(claim["previous_dispatch_attempts"]) is int and claim["previous_dispatch_attempts"]==0,"PARENT_VERIFIED_DURABLE_ONCE_ONLY_DISPATCH_CLAIM")
    if at>=utc(proposal["weekly_decision_deadline_utc"]):
        choice=result["choice_evidence"]
        require(type(choice) is dict and set(choice)=={"source_proof_sha256","choice_sha256","actual_frozen_at","decision_write_completed_at","weekly_deadline_utc","schedule_sha256"}
            and hashed(choice["source_proof_sha256"]) and hashed(choice["choice_sha256"]) and choice["schedule_sha256"]==proposal["schedule_sha256"]
            and utc(choice["actual_frozen_at"])<=utc(choice["decision_write_completed_at"])<utc(choice["weekly_deadline_utc"])==utc(proposal["weekly_decision_deadline_utc"]),
            "MISSED_WEEKLY_DEADLINE_WITHOUT_AUTHENTICATED_ORIGINAL_CHOICE")
    expected=deepcopy(p["root_template"])
    for key,path in p["root_bindings"].items():put_path(expected,path,ctx[key])
    root_metadata(expected)
    require(result["root_go"]==expected and len(canonical(expected))<=LIMITS["root_bytes"],"EXACT_NEW_PARENT_BOUND_ROOT_GO_TEMPLATE")
    body=canonical(dict(ref=p["producer_branch"],inputs=dict(mode=MODE,inference_builder_go_json=canonical(expected).decode(),inference_builder_go_sha256=digest(expected))))
    checked=utc(clock());gate=cadence(env["GITHUB_EVENT_NAME"],"daily",checked)
    require(gate["due"] and checked<utc(ctx["expires_at_utc"]) and all(checked<utc(t) for t in proposal["source_cutoffs_utc"].values()),"FRESH_DISPATCH_WINDOW_ROOT_AND_FUTURE_CUTOFFS")
    producer_head(api,p)
    # The child must also match its actual source to this root: GitHub's ref
    # dispatch is not atomic with our final branch GET. No hidden retries.
    intent=dict(schema_version=VERSION+"-dispatch-intent",claim_id=ctx["dispatch_claim_id"],registration_sha256=digest(p),parent=parent,
        root_go_sha256=digest(expected),request_sha256=sha(body),created_at_utc=checked.isoformat(),state="POST_ATTEMPT_UNRESOLVED_NO_RETRY")
    write_once(intent_path,intent)
    try:status,_=api.request(api.allow(API+"/actions/workflows/lab.yml/dispatches"),body=body)
    except Exception:status=None
    state="DISPATCH_ENQUEUED_PARENT_MUST_EXIT" if status==204 else "DISPATCH_UNRESOLVED_NO_RETRY"
    receipt=dict(schema_version=VERSION+"-dispatch-receipt",state=state,claim_id=ctx["dispatch_claim_id"],parent_sha256=digest(parent),
        root_go_sha256=digest(expected),request_sha256=sha(body),HTTP_status=status,dispatch_attempts=1,completed_at_utc=utc(clock()).isoformat(),
        child_completion_claimed=False,parent_completion_must_be_verified_by_child=True,fits=0,public_release=False)
    write_once(str(intent_path)+".receipt.json",receipt)
    return dict(state=state,claim_id=ctx["dispatch_claim_id"],root_go_sha256=digest(expected),receipt_sha256=digest(receipt),dispatches=1,
        HTTP_status=status,fits=0,child_completion_claimed=False)


def verify_completed_parent(api,parent,*,checked_at):
    """Child calls AFTER parent finishes. Never poll/wait inside the dispatcher."""
    base=API+"/actions/runs/"+parent["run_id"];run=api.get(base);listing=api.get(base+"/jobs?per_page=100&page=1")
    require(run.get("id")==int(parent["run_id"]) and run.get("head_sha")==parent["source_sha"] and run.get("run_attempt")==1
        and run.get("event")==parent["event"] and run.get("path")==WORKFLOW and run.get("status")=="completed" and run.get("conclusion")=="success"
        and actor_matches(run.get("actor"),parent["actor"]) and run.get("repository",{}).get("full_name")==run.get("head_repository",{}).get("full_name")==REPOSITORY
        and parent["workflow_ref"]==REPOSITORY+"/"+WORKFLOW+"@refs/heads/"+run["head_branch"],
        "ACTUAL_COMPLETED_SUCCESSFUL_DISPATCH_PARENT_REQUIRED")
    require(type(listing.get("jobs")) is list and listing.get("total_count")==len(listing["jobs"])<=100,"COMPLETE_FINISHED_PARENT_JOB_LIST")
    found=[j for j in listing["jobs"] if j.get("id")==parent["api_job_id"]]
    require(len(found)==1 and found[0].get("name")==parent["job_id"] and found[0].get("run_id")==int(parent["run_id"])
        and found[0].get("head_sha")==parent["source_sha"] and found[0].get("status")=="completed" and found[0].get("conclusion")=="success"
        and utc(found[0]["started_at"])==utc(parent["job_started_at"])<=utc(parent["verified_at_utc"])<=utc(found[0]["completed_at"])<=utc(checked_at),
        "COMPLETED_PARENT_JOB_SOURCE_AND_CAUSAL_CLOCKS")
    return dict(schema_version=VERSION+"-completed-parent",parent_sha256=digest(parent),verified_at_utc=utc(checked_at).isoformat(),
        completed_at=found[0]["completed_at"],state="COMPLETED_PARENT_VERIFIED_NO_IDENTITY_RELABEL")


def load_callback(p,root):
    b=p["builder"];require(sha(read(Path(root)/b["path"],2 << 20))==b["sha256"],"PINNED_METADATA_CALLBACK_SOURCE")
    module=importlib.import_module(b["path"][:-3].replace("/","."));require(Path(module.__file__).resolve()==(Path(root)/b["path"]).resolve(),"ACTUAL_PINNED_METADATA_CALLBACK_MODULE")
    value=getattr(module,b["callable"]);require(callable(value),"PARENT_METADATA_CALLBACK_CALLABLE_REQUIRED");return value
