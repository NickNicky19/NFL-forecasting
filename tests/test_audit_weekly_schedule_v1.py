"""Fictional schedules, sealed metadata callbacks and injected API only."""
from copy import deepcopy
from contextlib import redirect_stdout
from datetime import timedelta
import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nfl_lab import audit_weekly_schedule_v1 as s
from tools import audit_weekly_schedule_v1 as cli

ROOT=Path(__file__).resolve().parents[1]
AT=s.utc("2026-10-21T13:36:00Z")
SOURCE="a"*40;PRODUCER="b"*40;RUN="49900000001"
ACTOR=dict(login="fictional_owner",id=12345)


def rows():
    return [dict(season=2026,week=7,game_type="REG",game_id=name,kickoff_utc=clock) for name,clock in
        (("fictional-thursday","2026-10-22T23:15:00Z"),("fictional-london","2026-10-25T13:30:00Z"),("fictional-sunday","2026-10-25T20:25:00Z"))]


class Response:
    def __init__(self,body,status=200):self.body=body if type(body) is bytes else s.canonical(body);self.status=status;self.headers={"X-RateLimit-Remaining":"99"}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.body[:n]


class Service:
    def __init__(self,workflow):
        self.workflow=workflow;self.calls=[];self.post_status=204;self.ambiguous=False;self.finished=False;self.heads=0;self.head_moved=False
        self.run_bad={};self.job_bad={}
    def __call__(self,request,timeout):
        self.calls.append(request);url=request.full_url
        if request.method=="POST":
            if self.ambiguous:raise TimeoutError("PRIVATE_TRANSPORT_TEXT")
            return Response(b"",self.post_status)
        if "/git/ref/heads/" in url:
            self.heads+=1
            return Response(dict(ref="refs/heads/research/fictional",object=dict(type="commit",sha="c"*40 if self.head_moved and self.heads>1 else PRODUCER)))
        if "/contents/" in url:return Response(dict(type="file",path=s.WORKFLOW,encoding="base64",size=len(self.workflow),content=base64.b64encode(self.workflow).decode()))
        if "/jobs?" in url:
            job=dict(id=7777,name="lab",run_id=int(RUN),head_sha=SOURCE,status="completed" if self.finished else "in_progress",conclusion="success" if self.finished else None,
                started_at=(AT-timedelta(minutes=1)).isoformat(),completed_at=(AT+timedelta(minutes=2)).isoformat());job.update(self.job_bad)
            return Response(dict(total_count=1,jobs=[job]))
        run=dict(id=int(RUN),head_sha=SOURCE,event="schedule",run_attempt=1,status="completed" if self.finished else "in_progress",conclusion="success" if self.finished else None,
            path=s.WORKFLOW,head_branch="main",actor=dict(ACTOR,type="User",node_id="fictional-extra-api-field"),repository=dict(full_name=s.REPOSITORY),head_repository=dict(full_name=s.REPOSITORY))
        run.update(self.run_bad);return Response(run)


@pytest.fixture
def system(tmp_path,monkeypatch):
    root=tmp_path/"repo"
    for name in s.PIN_PATHS:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(("FICTIONAL_SOURCE "+name+"\n").encode())
    workflow=b"name: fictional\non:\n  schedule:\n    - cron: '36 13,14 * * *'\npermissions: {contents: read, actions: read}\nconcurrency:\n  group: nfl-lab-single-writer\n  cancel-in-progress: false\njobs:\n  lab:\n    runs-on: ubuntu-latest\n    permissions: {contents: read, actions: write}\n"
    (root/s.WORKFLOW).write_bytes(workflow)
    builder=root/"tools/fictional_schedule_metadata.py";builder.write_bytes(b"def prepare(*args,**kwargs):\n    raise AssertionError('fictional fixture only')\n")
    p=s.template(root);p.update(approved=True,state="OWNER_SEALED_OPERATIONAL_READY",parent_source_sha=SOURCE,parent_job_id="lab",
        actors={"schedule":dict(ACTOR)},producer_branch="research/fictional",producer_source_sha=PRODUCER,
        producer_source_pins={"nfl_lab/fictional_producer.py":"c"*64},builder=dict(path="tools/fictional_schedule_metadata.py",callable="prepare",sha256=s.sha(builder.read_bytes())),
        readiness_proof_sha256="d"*64,root_template=dict(schema_version="FICTIONAL_ROOT_GO",**{key:None for key in s.BINDINGS}),
        root_bindings={key:[key] for key in s.BINDINGS})
    env=dict(GITHUB_ACTIONS="true",CI="true",GITHUB_REPOSITORY=s.REPOSITORY,GITHUB_RUN_ATTEMPT="1",GITHUB_EVENT_NAME="schedule",
        GITHUB_SHA=SOURCE,GITHUB_WORKFLOW_SHA=SOURCE,GITHUB_JOB="lab",GITHUB_RUN_ID=RUN,GITHUB_ACTOR=ACTOR["login"],GITHUB_ACTOR_ID=str(ACTOR["id"]),
        GITHUB_WORKFLOW_REF=s.REPOSITORY+"/"+s.WORKFLOW+"@refs/heads/main")
    service=Service(workflow);api=s.Client("ghs_FICTIONAL",transport=service)
    monkeypatch.setattr(s,"now",lambda:AT)
    return SimpleNamespace(root=root,p=p,env=env,service=service,api=api,intent=tmp_path/"intent.json",clock=AT)


def callback(p,proposal,parent,ctx,*,api_get):
    root=deepcopy(p["root_template"])
    for key,path in p["root_bindings"].items():s.put_path(root,path,ctx[key])
    return dict(schema_version=s.VERSION+"-readiness-and-claim",ready=True,registration_sha256=s.digest(p),parent_sha256=s.digest(parent),
        plan_sha256=s.digest(proposal),readiness_proof_sha256=p["readiness_proof_sha256"],schedule_metadata_verified=True,choice_evidence=None,
        claim=dict(claim_id=ctx["dispatch_claim_id"],parent_run_id=parent["run_id"],parent_api_job_id=parent["api_job_id"],proof_sha256="e"*64,
            state="DURABLE_ATOMIC_CLAIM_VERIFIED",previous_dispatch_attempts=0),root_go=root)


def dispatch(x,cb=callback):
    with patch.object(s.subprocess,"check_output",side_effect=[SOURCE+"\n",""]):
        return s.dispatch(x.p,rows(),season=2026,week=7,api=x.api,env=x.env,root=x.root,intent_path=x.intent,metadata_callback=cb,clock=lambda:x.clock)


@pytest.mark.parametrize("clock,due",[("2026-10-22T13:36:00Z",True),("2026-10-22T13:56:59Z",True),("2026-10-22T13:57:00Z",False),
    ("2026-10-22T14:36:00Z",False),("2026-12-10T13:36:00Z",False),("2026-12-10T14:36:00Z",True),
    ("2026-11-01T13:36:00Z",False),("2026-11-01T14:36:00Z",True),("2026-03-08T13:36:00Z",True),("2026-03-08T14:36:00Z",False)])
def test_unchanged_DST_window_is_exactly_36_through_56(clock,due):
    assert s.cadence("schedule","daily",s.utc(clock))["due"] is due


def test_full_week_deadline_uses_elapsed_first_game_and_no_backfill_or_horizon_claim():
    p=s.plan(rows(),season=2026,week=7,at=s.utc("2026-10-25T13:36:00Z"))
    assert p["weekly_decision_deadline_utc"]==s.utc("2026-10-22T17:15:00Z").isoformat()
    assert set(p["elapsed_game_ids"])=={"fictional-thursday","fictional-london"}
    assert p["future_game_ids"]==["fictional-sunday"]
    assert p["state"]=="MISSED_WEEKLY_DEADLINE_EXISTING_PREDEADLINE_CHOICE_REQUIRED"
    assert "NOT_REGISTERED_EXACT_HORIZON" in p["horizon"] and p["execution_authorized"] is False and p["maximum_new_fits"]==0


def test_future_cutoffs_seven_day_history_and_close_game_are_explicit():
    p=s.plan(rows(),season=2026,week=7,at=AT)
    assert p["history_information_before_utc"]==(AT-timedelta(days=7)).isoformat()
    assert all(AT<s.utc(c)<s.utc(next(g["kickoff_utc"] for g in rows() if g["game_id"]==gid)) for gid,c in p["source_cutoffs_utc"].items())
    p=s.plan(rows(),season=2026,week=7,at=s.utc("2026-10-22T23:14:00Z"),event="workflow_dispatch")
    assert p["state"]=="FUTURE_GAME_TOO_CLOSE_NO_SILENT_OMISSION" and "fictional-thursday" in p["blocked_future_game_ids"]
    with pytest.raises(s.ScheduleError,match="SEVEN_DAY_HISTORY"):s.plan(rows(),season=2026,week=7,at=AT,policy=dict(s.POLICY,history_lag_seconds=86400))


def test_daily_cannot_guarantee_T24_T6_T90_and_London_is_explicit_proposal_only():
    proposal=s.horizon_proposal(rows(),season=2026,week=7);london={e["horizon"]:e for e in proposal["events"] if e["game_id"]=="fictional-london"}
    assert london["T24"]["daily_tick_offset_seconds"]==360
    assert all(v["daily_tick_offset_seconds"]>0 for v in london.values())
    assert proposal["additional_cron_activated"] is proposal["daily_cadence_guarantees_T24_T6_T90"] is proposal["initial_player_game_capture_is_exact_horizon"] is False
    assert proposal["state"]=="POLICY_REGISTRATION_REQUIRED_NO_ACTIVATION"


def test_horizon_subtraction_is_UTC_correct_across_fall_DST():
    schedule=[dict(season=2026,week=8,game_type="REG",game_id="fictional-DST-london",kickoff_utc="2026-11-01T13:30:00Z")]
    p=s.horizon_proposal(schedule,season=2026,week=8);by={e["horizon"]:e for e in p["events"]}
    assert s.utc(by["T24"]["desired_capture_utc"])==s.utc("2026-10-31T13:30:00Z")
    assert s.utc(by["T6"]["same_day_daily_tick_utc"])==s.utc("2026-11-01T14:36:00Z")


def test_single_dispatch_fresh_root_actual_parent_and_immediate_exit_without_wait(system):
    x=system;result=dispatch(x)
    assert result["state"]=="DISPATCH_ENQUEUED_PARENT_MUST_EXIT" and result["dispatches"]==1
    posts=[r for r in x.service.calls if r.method=="POST"];assert len(posts)==1 and x.service.calls[-1] is posts[0]
    payload=s.decode(posts[0].data);root=s.decode(payload["inputs"]["inference_builder_go_json"])
    assert payload["ref"]=="research/fictional" and payload["inputs"]["mode"]==s.MODE
    assert root["source_sha"]==PRODUCER and root["scheduled_parent"]["run_id"]==RUN
    assert root["maximum_new_fits"]==0 and root["schedule_plan"]["source_cutoffs_utc"]
    assert root["issued_at_utc"]==AT.isoformat() and root["expires_at_utc"]==(AT+timedelta(hours=1)).isoformat()
    assert x.intent.is_file() and Path(str(x.intent)+".receipt.json").is_file()
    assert result["child_completion_claimed"] is False and len(x.service.calls)<=s.LIMITS["HTTP_calls"]


def test_ambiguous_dispatch_is_durable_unresolved_and_never_retried(system):
    x=system;x.service.ambiguous=True;result=dispatch(x)
    assert result["state"]=="DISPATCH_UNRESOLVED_NO_RETRY" and result["HTTP_status"] is None
    assert s.decode(x.intent.read_bytes())["state"]=="POST_ATTEMPT_UNRESOLVED_NO_RETRY"
    with pytest.raises(FileExistsError):dispatch(x)
    assert len([r for r in x.service.calls if r.method=="POST"])==1
    assert "PRIVATE_TRANSPORT_TEXT" not in json.dumps(result)


@pytest.mark.parametrize("field,value",[("head_sha","c"*40),("event","push"),("actor",dict(login="another",id=12)),("run_attempt",2),("status","completed")])
def test_actual_parent_source_event_actor_attempt_and_running_job_are_verified(system,field,value):
    x=system;x.service.run_bad[field]=value
    with pytest.raises(s.ScheduleError):dispatch(x)
    assert not any(r.method=="POST" for r in x.service.calls)


def test_moved_producer_head_blocks_immediately_before_dispatch(system):
    x=system;x.service.head_moved=True
    with pytest.raises(s.ScheduleError,match="CURRENT_PRODUCER_BRANCH_HEAD"):dispatch(x)
    assert not x.intent.exists() and not any(r.method=="POST" for r in x.service.calls)


@pytest.mark.parametrize("field,value",[("ready",False),("schedule_metadata_verified",False),("readiness_proof_sha256","f"*64),("parent_sha256","f"*64)])
def test_approved_template_does_not_self_assert_ready_or_authenticate_schedule(system,field,value):
    def changed(*args,**kwargs):
        result=callback(*args,**kwargs);result[field]=value;return result
    with pytest.raises(s.ScheduleError,match="READINESS_CALLBACK"):dispatch(system,changed)
    assert not any(r.method=="POST" for r in system.service.calls)


@pytest.mark.parametrize("field,value",[("previous_dispatch_attempts",1),("state","LOCAL_ONLY"),("parent_run_id","111"),("proof_sha256",None)])
def test_consumed_or_unverified_claim_cannot_dispatch(system,field,value):
    def changed(*args,**kwargs):
        result=callback(*args,**kwargs);result["claim"][field]=value;return result
    with pytest.raises(s.ScheduleError,match="ONCE_ONLY_DISPATCH_CLAIM"):dispatch(system,changed)
    assert not system.intent.exists()


def test_missed_deadline_requires_real_original_predeadline_write_clock(system):
    x=system;x.clock=s.utc("2026-10-25T13:36:00Z")
    with pytest.raises(s.ScheduleError,match="MISSED_WEEKLY_DEADLINE"):dispatch(x)
    def preserved(p,proposal,parent,ctx,**kwargs):
        result=callback(p,proposal,parent,ctx,**kwargs)
        result["choice_evidence"]=dict(source_proof_sha256="1"*64,choice_sha256="2"*64,actual_frozen_at="2026-10-21T12:00:00Z",
            decision_write_completed_at="2026-10-21T12:01:00Z",weekly_deadline_utc=proposal["weekly_decision_deadline_utc"],schedule_sha256=proposal["schedule_sha256"])
        return result
    assert dispatch(x,preserved)["state"]=="DISPATCH_ENQUEUED_PARENT_MUST_EXIT"


def test_late_initial_copy_cannot_be_backdated_into_a_full_week_choice(system):
    x=system;x.clock=s.utc("2026-10-25T13:36:00Z")
    def late(p,proposal,parent,ctx,**kwargs):
        result=callback(p,proposal,parent,ctx,**kwargs)
        result["choice_evidence"]=dict(source_proof_sha256="1"*64,choice_sha256="2"*64,actual_frozen_at="2026-10-24T12:00:00Z",
            decision_write_completed_at="2026-10-24T12:01:00Z",weekly_deadline_utc=proposal["weekly_decision_deadline_utc"],schedule_sha256=proposal["schedule_sha256"])
        return result
    with pytest.raises(s.ScheduleError,match="MISSED_WEEKLY_DEADLINE"):dispatch(x,late)


def test_child_checks_completed_parent_later_without_identity_relabel(system):
    x=system;dispatch(x);parent=s.decode(x.intent.read_bytes())["parent"]
    with pytest.raises(s.ScheduleError,match="COMPLETED_SUCCESSFUL_DISPATCH_PARENT"):s.verify_completed_parent(x.api,parent,checked_at=AT+timedelta(minutes=3))
    x.service.finished=True
    proof=s.verify_completed_parent(x.api,parent,checked_at=AT+timedelta(minutes=3))
    assert proof["state"]=="COMPLETED_PARENT_VERIFIED_NO_IDENTITY_RELABEL"
    assert proof["parent_sha256"]==s.digest(parent)


def test_window_miss_never_contacts_API_and_full_schedule_rejects_outcomes(system):
    x=system;x.clock=s.utc("2026-10-21T13:57:00Z")
    assert dispatch(x)["state"]=="MISSED_SCHEDULE_WINDOW_NOT_BACKFILLED" and not x.service.calls
    unsafe=rows();unsafe[0]["home_score"]=None
    with pytest.raises(s.ScheduleError,match="NO_OUTCOMES"):s.plan(unsafe,season=2026,week=7,at=AT)


def test_template_is_unapproved_and_root_cannot_carry_private_bodies(system):
    x=system;p=s.template(x.root)
    with pytest.raises(s.ScheduleError,match="SEALED_REAL_OPERATIONAL"):s.registration(p,x.root)
    x.p["root_template"]["forecast_rows"]=[dict(player_id="fictional",forecast_value=1.)]
    with pytest.raises(s.ScheduleError,match="NO_SECRETS_OR_PRIVATE_BODIES"):s.registration(x.p,x.root)


def test_metadata_transport_does_not_follow_private_payload_or_unrelated_repo_routes(system):
    for route in (s.API+"/releases/assets/123",s.API+"/../other",s.API.replace(s.REPOSITORY,"another/repo")+"/actions/runs/1"):
        with pytest.raises(s.ScheduleError):system.api.get(route)
    assert not system.service.calls


def test_preparation_CLI_does_not_discover_token_or_dispatch(tmp_path):
    class NoCredentials(dict):
        def get(self,key,*args):
            if key=="GITHUB_TOKEN":raise AssertionError("credential discovery during preparation")
            return super().get(key,*args)
    stream=io.StringIO()
    with redirect_stdout(stream):assert cli.main(["dispatch"],environ=NoCredentials())==2
    with redirect_stdout(stream):assert cli.main(["template","--output",str(tmp_path/"template.json")],environ=NoCredentials())==0
    assert "UNAPPROVED_SCHEDULE_TEMPLATE" in stream.getvalue()
