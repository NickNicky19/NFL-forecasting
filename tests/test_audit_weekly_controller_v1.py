"""Wholly fictional GHA/API/Git metadata; zero real network, secrets or Git writes."""
import base64
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import pickle
import socket

import pytest

from nfl_lab import audit_weekly_controller_v1 as c
from tools import audit_weekly_controller_v1 as cli

A="a"*40
B="b"*40
C="c"*40
D="d"*40
AT=c.utc("2026-10-25T13:38:00Z")
PSTART="2026-10-25T13:36:05Z"
PVERIFIED="2026-10-25T13:36:10Z"
PEND="2026-10-25T13:37:00Z"
CSTART="2026-10-25T13:37:05Z"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,"connect",lambda *_:pytest.fail("REAL_NETWORK_FORBIDDEN"))


def h(value):
    return c.sha(str(value).encode())


def wf():
    return b"""name: Fictional metadata fixture
on:
  schedule:
    - cron: '36 13,14 * * *'
  workflow_dispatch:
permissions:
  contents: write
  actions: read
concurrency:
  group: nfl-lab-single-writer
  cancel-in-progress: false
jobs:
  lab:
    permissions:
      contents: write
      actions: write
    runs-on: ubuntu-latest
    steps: []
  audit-weekly-produce-v1:
    runs-on: ubuntu-latest
    steps: []
  audit-weekly-restore-v1:
    runs-on: ubuntu-latest
    steps: []
  audit-weekly-export-v1:
    runs-on: ubuntu-latest
    steps: []
  audit-weekly-failure-restore-v1:
    runs-on: ubuntu-latest
    steps: []
  old-produce:
    runs-on: ubuntu-latest
    steps: []
  old-restore:
    runs-on: ubuntu-latest
    steps: []
  old-export:
    runs-on: ubuntu-latest
    steps: []
"""


def content(path,body):
    return dict(type="file",path=path,encoding="base64",size=len(body),sha=c.blob_sha(body),
        content=base64.b64encode(body).decode())


def run(identifier,source,branch,actor,*,event="workflow_dispatch",status="completed",updated=PEND):
    return dict(id=int(identifier),repository=dict(full_name=c.REPO),head_repository=dict(full_name=c.REPO),
        head_sha=source,head_branch=branch,path=c.WORKFLOW,event=event,run_attempt=1,status=status,
        conclusion="success" if status=="completed" else None,actor=deepcopy(actor),triggering_actor=deepcopy(actor),updated_at=updated)


def job(identifier,source,name,number,start,end=None):
    return dict(id=number,run_id=int(identifier),head_sha=source,name=name,started_at=start,
        completed_at=end,status="completed" if end else "in_progress",conclusion="success" if end else None)


class API:
    def __init__(self):
        self.data={};self.calls=[];self.hooks={}
    def __call__(self,url,cap):
        self.calls.append((url,cap))
        assert c.fixed_route(url) and not url.endswith("/dispatches")
        assert url in self.data,"UNEXPECTED_API_ROUTE"
        value=deepcopy(self.data[url])
        if url in self.hooks:
            value=self.hooks[url](value,sum(x[0]==url for x in self.calls))
        raw=c.canonical(value)
        assert len(raw)<=cap
        return c.Reply(200,raw)


@pytest.fixture
def system(tmp_path):
    from types import SimpleNamespace
    x=SimpleNamespace(api=API(),root=tmp_path)
    p=c.registration_template(cadence_policy_version=c.LEGACY_POLICY);p.update(state="OWNER_SEALED_METADATA_BINDING",registered_at_utc="2026-10-25T13:00:00Z")
    p["parent"].update(source_sha=A,workflow_sha256=c.sha(wf()))
    p["producer"].update(source_sha=B,branch="research/current-producer",workflow_sha256=c.sha(wf()))
    for label,spec in (("parent",p["parent"]),("child",p["producer"])):
        root=tmp_path/label;root.mkdir();pins={}
        for name in (c.MODULE,c.TOOL):
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
            body=("FICTIONAL immutable "+name).encode();path.write_bytes(body);pins[name]=c.sha(body)
        path=root/c.WORKFLOW;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(wf());pins[c.WORKFLOW]=c.sha(wf())
        spec["code_pins"]=pins
        setattr(x,label+"_source",root)
    r=p["readiness"]
    r.update(source_sha=C,branch="research/original-readiness",run_id="200",workflow_sha256=c.sha(wf()),
        jobs={role:dict(job_id=name,api_job_id=21+i) for i,(role,name) in enumerate(zip(c.ROLES,("old-produce","old-restore","old-export")))},
        receipt_bindings={k:h("original-"+k) for k in c.RECEIPT_HASH_KEYS})
    receipt=dict(r["receipt_bindings"],schema_version="audit-weekly-delivery-v1-public-receipt",source_sha=C,run_id="200",
        workflow_sha256=r["workflow_sha256"],policy_registered_at_utc="2026-10-25T09:00:00Z",
        feed_bytes=1234,rows=11,categories=sorted(c.TARGETS),jobs=deepcopy(r["jobs"]),
        verified_at="2026-10-25T10:23:00Z",created_at="2026-10-25T10:24:00Z",fits=0,raw_or_models_public=False)
    x.original_receipt=c.canonical(receipt)
    packed=gzip.compress(x.original_receipt,mtime=0)
    r.update(receipt_sha256=c.sha(packed),receipt_body_sha256=c.sha(x.original_receipt))
    x.p=p;x.reg=c.canonical(p);x.seal=c.sha(x.reg)
    parent=dict(schema_version="audit-weekly-schedule-v1-parent",repository=c.REPO,run_id="100",run_attempt=1,
        source_sha=A,workflow_ref=c.REPO+"/"+c.WORKFLOW+"@refs/heads/main",event="schedule",actor=deepcopy(c.OWNER),
        job_id="lab",api_job_id=11,job_started_at=PSTART,workflow_sha256=c.sha(wf()),verified_at_utc=PVERIFIED,
        state="AUTHENTICATED_RUNNING_PARENT_CHILD_MUST_VERIFY_COMPLETION_LATER")
    x.go=dict(source_sha=B,mode=c.MODE,workflow_ref=c.REPO+"/"+c.WORKFLOW+"@refs/heads/research/current-producer",
        single_writer_group=c.GROUP,code_pins=deepcopy(p["producer"]["code_pins"]),jobs={k:p["producer"]["jobs"][k] for k in c.ROLES},
        failure_restorer=p["producer"]["jobs"]["evidence"],issued_at_utc="2026-10-25T13:36:20Z",
        expires_at_utc="2026-10-25T14:36:20Z",effective_epoch=dict(controller_context=c.controller_context(x.seal,parent,h("once-per-daily-key"))))
    x.env=dict(GITHUB_ACTIONS="true",CI="true",GITHUB_REPOSITORY=c.REPO,GITHUB_RUN_ATTEMPT="1",GITHUB_RUN_ID="300",
        GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_SHA=B,GITHUB_WORKFLOW_SHA=B,GITHUB_WORKFLOW_REF=x.go["workflow_ref"],
        GITHUB_JOB=p["producer"]["jobs"]["produce"],GITHUB_ACTOR=c.BOT["login"],GITHUB_ACTOR_ID=str(c.BOT["id"]),STORE_PERMISSION="write")
    def bind_root():
        x.raw=c.canonical(x.go);x.env.update(AUDIT_WEEKLY_ROOT_GO_JSON=x.raw.decode(),AUDIT_WEEKLY_ROOT_GO_SHA256=c.sha(x.raw))
        x.event=c.canonical(dict(repository=dict(full_name=c.REPO),inputs=dict(mode=c.MODE,
            inference_builder_go_json=x.raw.decode(),inference_builder_go_sha256=c.sha(x.raw))))
    x.bind_root=bind_root;bind_root()
    d=x.api.data
    d[c.run_url("100")]=run("100",A,"main",c.OWNER,event="schedule",updated="2026-10-25T13:37:01Z")
    d[c.jobs_url("100")]=dict(total_count=1,jobs=[job("100",A,"lab",11,PSTART,PEND)])
    d[c.run_url("300")]=run("300",B,p["producer"]["branch"],c.BOT,status="in_progress",updated=CSTART)
    d[c.jobs_url("300")]=dict(total_count=1,jobs=[job("300",B,x.env["GITHUB_JOB"],31,CSTART)])
    d[c.run_url("200")]=run("200",C,r["branch"],c.OWNER,updated="2026-10-25T10:30:01Z")
    times=[("10:00:00","10:10:00"),("10:11:00","10:20:00"),("10:21:00","10:30:00")]
    d[c.jobs_url("200")]=dict(total_count=3,jobs=[job("200",C,r["jobs"][role]["job_id"],r["jobs"][role]["api_job_id"],
        "2026-10-25T"+start+"Z","2026-10-25T"+end+"Z")for role,(start,end) in zip(c.ROLES,times)])
    for source in (A,B,C):
        d[c.contents_url(c.WORKFLOW,source)]=content(c.WORKFLOW,wf())
    d[c.head_url(p)]=dict(ref="refs/heads/"+p["producer"]["branch"],object=dict(type="commit",sha=B))
    d[c.contents_url(c.receipt_path(p),"lab-state")]=content(c.receipt_path(p),packed)
    ctx=x.go["effective_epoch"]["controller_context"];path=ctx["claim_locator"]["path"]
    x.claim=dict(schema_version=c.VERSION+"-claim",repository=c.REPO,claim_id=ctx["claim_id"],registration_sha256=x.seal,
        parent_run_id="100",parent_api_job_id=11,parent_source_sha=A,producer_source_sha=B,
        root_go_sha256=c.sha(x.raw),created_at_utc="2026-10-25T13:36:21Z")
    d[c.claim_history(path)]=[dict(sha=D)]
    d[c.API+"/commits/"+D]=dict(sha=D,parents=[dict(sha="e"*40)],committer=deepcopy(c.BOT),
        files=[dict(filename=path,status="added",sha=c.blob_sha(c.canonical(x.claim)))])
    d[c.contents_url(path,D)]=content(path,c.canonical(x.claim))
    x.claim_path=path
    x.read_head=lambda root:A if root==x.parent_source else B
    def verify(**kwargs):
        defaults=dict(sealed_sha256=x.seal,root_bytes=x.raw,event_bytes=x.event,env=x.env,
            source_root=x.child_source,metadata_get=x.api,clock=lambda:AT,read_head=x.read_head)
        defaults.update(kwargs)
        return c.verify_child(x.reg,**defaults)
    x.verify=verify
    return x


def test_genuine_parent_child_metadata_chain_exact_twenty_GETs_no_relabel(system):
    x=system;proof=x.verify()
    assert proof.document["actor"]==c.BOT and proof.document["parent_actor"]==c.OWNER
    assert proof.document["source_sha"]==B and proof.document["readiness"]["source_sha"]==C
    assert len(x.api.calls)==20 and len(proof.document["metadata_GETs"])==20
    assert proof.document["activation_authorized"] is proof.document["public_release"] is False
    assert c.canonical(c.decode(x.original_receipt))==x.original_receipt
    assert proof.verify(registration_sha256=x.seal,run_id="300",job_id=x.env["GITHUB_JOB"],root_sha256=c.sha(x.raw)) is proof


def test_running_parent_proof_is_enqueue_and_return_without_child_wait(system):
    x=system
    x.api.data[c.run_url("100")].update(status="in_progress",conclusion=None,updated_at=PVERIFIED)
    x.api.data[c.jobs_url("100")]["jobs"][0].update(status="in_progress",conclusion=None,completed_at=None)
    env=dict(x.env,GITHUB_RUN_ID="100",GITHUB_EVENT_NAME="schedule",GITHUB_SHA=A,GITHUB_WORKFLOW_SHA=A,
        GITHUB_WORKFLOW_REF=c.REPO+"/"+c.WORKFLOW+"@refs/heads/main",GITHUB_JOB="lab",GITHUB_ACTOR=c.OWNER["login"],GITHUB_ACTOR_ID=str(c.OWNER["id"]))
    event=c.canonical(dict(repository=dict(full_name=c.REPO),schedule=c.CADENCE["cron"]))
    proof=c.verify_parent(x.reg,sealed_sha256=x.seal,env=env,event_bytes=event,source_root=x.parent_source,
        metadata_get=x.api,clock=lambda:c.utc(PVERIFIED),read_head=x.read_head)
    assert proof.document["next_action"]==c.RETURN_RULE and proof.document["child_completion_claimed"] is False
    assert len(x.api.calls)<20 and not any("/300" in u or "dispatches" in u for u,_ in x.api.calls)


def test_new_registration_policy_is_versioned_and_legacy_policy_is_preserved():
    assert c.registration_template()["cadence"]==c.PARENT_CADENCE
    assert c.registration_template(cadence_policy_version=c.LEGACY_POLICY)["cadence"]==c.CADENCE
    assert c.CADENCE==dict(timezone="America/Chicago",hour=8,minute_first=36,minute_last=56,cron="36 13,14 * * *")
    with pytest.raises(c.ControllerError,match="EXPLICIT_CONTROLLER_CADENCE_VERSION"):
        c.registration_template(cadence_policy_version="unversioned")


@pytest.mark.parametrize("field,value",[("hour",8),("minute_first",35),("minute_last",57),
    ("cron",c.CADENCE["cron"]),("policy_version","unversioned"),("enabled",True)])
def test_sealed_parent_cadence_rejects_partial_or_relaxed_policy(system,field,value):
    p=deepcopy(system.p);p["cadence"]=dict(c.PARENT_CADENCE,**{field:value});raw=c.canonical(p)
    with pytest.raises(c.ControllerError,match="CLOSED_REGISTERED_CONTROLLER_CADENCE_POLICY"):
        c.registration(raw,sealed_sha256=c.sha(raw),at=AT)


def test_versioned_parent_and_child_use_actual_0736_proof_and_completed_parent(system):
    x=system;x.p["cadence"]=deepcopy(c.PARENT_CADENCE);x.p["registered_at_utc"]="2026-10-25T12:00:00Z"
    body=wf().replace(c.CADENCE["cron"].encode(),c.PARENT_CADENCE["cron"].encode())
    for role,source,source_sha in (("parent",x.parent_source,A),("producer",x.child_source,B)):
        (source/c.WORKFLOW).write_bytes(body)
        x.p[role]["workflow_sha256"]=x.p[role]["code_pins"][c.WORKFLOW]=c.sha(body)
        x.api.data[c.contents_url(c.WORKFLOW,source_sha)]=content(c.WORKFLOW,body)
    x.reg=c.canonical(x.p);x.seal=c.sha(x.reg)
    current=x.api.data[c.run_url("100")];actual=x.api.data[c.jobs_url("100")]["jobs"][0]
    current.update(status="in_progress",conclusion=None,updated_at="2026-10-25T12:36:10Z")
    actual.update(status="in_progress",conclusion=None,started_at="2026-10-25T12:36:05Z",completed_at=None)
    env=dict(x.env,GITHUB_RUN_ID="100",GITHUB_EVENT_NAME="schedule",GITHUB_SHA=A,GITHUB_WORKFLOW_SHA=A,
        GITHUB_WORKFLOW_REF=c.REPO+"/"+c.WORKFLOW+"@refs/heads/main",GITHUB_JOB="lab",
        GITHUB_ACTOR=c.OWNER["login"],GITHUB_ACTOR_ID=str(c.OWNER["id"]))
    def verify(event):
        return c.verify_parent(x.reg,sealed_sha256=x.seal,env=env,event_bytes=c.canonical(dict(
            repository=dict(full_name=c.REPO),schedule=event)),source_root=x.parent_source,metadata_get=x.api,
            clock=lambda:c.utc("2026-10-25T12:36:10Z"),read_head=x.read_head)
    with pytest.raises(c.ControllerError,match="ACTUAL_PARENT_EVENT_BODY"):verify(c.CADENCE["cron"])
    assert not x.api.calls
    parent=verify(c.PARENT_CADENCE["cron"]).document["scheduled_parent"]
    current.update(status="completed",conclusion="success",updated_at="2026-10-25T12:37:01Z")
    actual.update(status="completed",conclusion="success",completed_at="2026-10-25T12:37:00Z")
    x.go.update(code_pins=deepcopy(x.p["producer"]["code_pins"]),issued_at_utc="2026-10-25T12:36:20Z",
        expires_at_utc="2026-10-25T13:36:20Z",effective_epoch=dict(controller_context=c.controller_context(x.seal,parent,x.claim["claim_id"])))
    x.bind_root()
    x.claim.update(registration_sha256=x.seal,root_go_sha256=c.sha(x.raw),created_at_utc="2026-10-25T12:36:21Z")
    x.api.data[c.contents_url(x.claim_path,D)]=content(x.claim_path,c.canonical(x.claim))
    x.api.data[c.API+"/commits/"+D]["files"][0]["sha"]=c.blob_sha(c.canonical(x.claim))
    x.api.data[c.run_url("300")]["updated_at"]="2026-10-25T12:37:05Z"
    x.api.data[c.jobs_url("300")]["jobs"][0]["started_at"]="2026-10-25T12:37:05Z"
    proof=x.verify(clock=lambda:c.utc("2026-10-25T12:38:00Z"))
    assert proof.document["source_sha"]==B and proof.document["parent_api_job_id"]==parent["api_job_id"]
    assert proof.document["parent_completed_at"]=="2026-10-25T12:37:00Z"


@pytest.mark.parametrize("target,actor",[("100",dict(login="someone",id=7)),("300",c.OWNER),("200",c.BOT)])
def test_wrong_parent_child_or_old_owner_actor_rejected(system,target,actor):
    x=system;x.api.data[c.run_url(target)]["actor"]=actor
    with pytest.raises(c.ControllerError):x.verify()


@pytest.mark.parametrize("target,change",[("100",dict(status="in_progress",conclusion=None)),
    ("100",dict(head_sha=B)),("100",dict(conclusion="failure")),("300",dict(event="push")),("300",dict(run_attempt=2)),
    ("200",dict(head_sha=A))])
def test_parent_pending_wrong_source_failed_child_rerun_or_wrong_old_source(system,target,change):
    x=system;x.api.data[c.run_url(target)].update(change)
    with pytest.raises(c.ControllerError):x.verify()


def test_unconditional_bot_or_fake_Nick_environment_never_accepted(system):
    x=system
    for update in (dict(GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933"),dict(GITHUB_EVENT_NAME="schedule"),dict(GITHUB_RUN_ATTEMPT="2")):
        env=dict(x.env,**update)
        with pytest.raises(c.ControllerError):x.verify(env=env)


@pytest.mark.parametrize("field,value",[("completed_at","2026-10-25T13:37:06Z"),("started_at","2026-10-25T13:36:11Z")])
def test_parent_clock_must_be_actual_and_before_child_job(system,field,value):
    x=system;x.api.data[c.jobs_url("100")]["jobs"][0][field]=value
    with pytest.raises(c.ControllerError):x.verify()


@pytest.mark.parametrize("target",["100","300","200"])
def test_restart_or_raced_API_run_rejected_on_final_read(system,target):
    x=system
    x.api.hooks[c.run_url(target)]=lambda value,n:dict(value,run_attempt=2) if n>1 else value
    with pytest.raises(c.ControllerError,match="GHA_RUN_RESTARTED_OR_CHANGED"):x.verify()


def test_current_job_can_change_while_run_stays_in_progress(system):
    x=system
    def mutate(value,n):
        if n>1:value["jobs"][0]["id"]=999
        return value
    x.api.hooks[c.jobs_url("300")]=mutate
    with pytest.raises(c.ControllerError,match="ACTUAL_REGISTERED_GHA_JOB"):x.verify()


def test_registered_producer_head_race_fails(system):
    x=system
    x.api.hooks[c.head_url(x.p)]=lambda value,n:dict(value,object=dict(type="commit",sha=A))if n>1 else value
    with pytest.raises(c.ControllerError,match="PRODUCER_REF_RACED_OR_WRONG_SOURCE"):x.verify()


@pytest.mark.parametrize("kind",["no-history","modified","false-JSON-state","wrong-root","wrong-parent","wrong-source"])
def test_claim_requires_original_actual_Git_added_file_and_exact_ROOT(system,kind):
    x=system
    if kind=="no-history":x.api.data[c.claim_history(x.claim_path)]=[]
    elif kind=="modified":x.api.data[c.API+"/commits/"+D]["files"][0]["status"]="modified"
    else:
        if kind=="false-JSON-state":x.claim["state"]="DURABLE_ATOMIC_CLAIM_VERIFIED"
        elif kind=="wrong-root":x.claim["root_go_sha256"]="0"*64
        elif kind=="wrong-parent":x.claim["parent_run_id"]="999"
        else:x.claim["producer_source_sha"]=A
        raw=c.canonical(x.claim)
        x.api.data[c.contents_url(x.claim_path,D)]=content(x.claim_path,raw)
        x.api.data[c.API+"/commits/"+D]["files"][0]["sha"]=c.blob_sha(raw)
    with pytest.raises(c.ControllerError):x.verify()


def test_changed_or_recreated_claim_history_is_not_original_atomic_claim(system):
    x=system;x.api.data[c.claim_history(x.claim_path)].append(dict(sha="e"*40))
    with pytest.raises(c.ControllerError,match="ORIGINAL_CREATE_ONLY_CLAIM_HISTORY_REQUIRED"):x.verify()


def test_ROOT_hash_cannot_self_bind_through_claim_hash_and_event_must_match(system):
    x=system
    assert set(x.go["effective_epoch"]["controller_context"]["claim_locator"])=={"repository","ref","path"}
    env=dict(x.env,AUDIT_WEEKLY_ROOT_GO_SHA256="0"*64)
    with pytest.raises(c.ControllerError,match="CURRENT_CHILD_EXACT_ROOT_ENVIRONMENT"):x.verify(env=env)
    event=c.decode(x.event);event["inputs"]["inference_builder_go_sha256"]="0"*64
    with pytest.raises(c.ControllerError,match="ACTUAL_CHILD_DISPATCH_ROOT_INPUT_SHA"):x.verify(event_bytes=c.canonical(event))


def test_external_seal_must_be_independent_and_template_never_authorizes(system):
    x=system
    with pytest.raises(c.ControllerError,match="EXTERNAL_OWNER_SEAL_REQUIRED"):x.verify(sealed_sha256="0"*64)
    body=c.canonical(c.registration_template())
    with pytest.raises(c.ControllerError):c.registration(body,sealed_sha256=c.sha(body),at=AT)


def test_fixed_registration_booleans_cannot_be_numeric_aliases(system):
    x=system;bad=deepcopy(x.p);bad["concurrency"]["cancel_in_progress"]=0
    raw=c.canonical(bad)
    with pytest.raises(c.ControllerError,match="CLOSED_SEALED_CONTROLLER_REGISTRATION"):
        c.registration(raw,sealed_sha256=c.sha(raw),at=AT)


def test_ROOT_expiring_during_actual_metadata_verification_is_rejected(system):
    x=system
    def clock():
        return c.utc("2026-10-25T14:36:21Z")if len(x.api.calls)==20 else AT
    with pytest.raises(c.ControllerError,match="ROOT_EXPIRED_DURING_CONTROLLER_VERIFICATION"):x.verify(clock=clock)


def test_module_import_performs_no_parent_IO_or_metadata_execution(monkeypatch):
    import sys
    from types import ModuleType
    raw=Path(c.__file__).read_bytes();name="fictional_controller_import_probe"
    mod=ModuleType(name);mod.__package__="nfl_lab";sys.modules[name]=mod
    try:
        monkeypatch.setattr(Path,"read_bytes",lambda *_:pytest.fail("IMPORT_SOURCE_READ_FORBIDDEN"))
        monkeypatch.setattr(c.subprocess,"check_output",lambda *_a,**_k:pytest.fail("IMPORT_COMMAND_FORBIDDEN"))
        exec(compile(raw,"FICTIONAL_controller_import_probe.py","exec"),mod.__dict__)
        assert mod.registration_template()["state"]=="PREPARED_UNREGISTERED"
    finally:
        del sys.modules[name]


def test_readiness_receipt_body_is_actually_checked_not_echoed(system):
    x=system;url=c.contents_url(c.receipt_path(x.p),"lab-state");doc=c.decode(x.original_receipt)
    doc["source_sha"]=B
    packed=gzip.compress(c.canonical(doc),mtime=0);x.api.data[url]=content(c.receipt_path(x.p),packed)
    with pytest.raises(c.ControllerError,match="EXACT_OLD_READINESS_RECEIPT_BYTES"):x.verify()


def test_changed_current_source_bytes_or_head_not_allowed(system):
    x=system;(x.child_source/c.MODULE).write_bytes(b"FICTIONAL changed implementation")
    with pytest.raises(c.ControllerError,match="CURRENT_CODE_INVENTORY_MISMATCH"):x.verify()
    with pytest.raises(c.ControllerError,match="CURRENT_LOCAL_SOURCE_HEAD_MISMATCH"):x.verify(read_head=lambda _:A)


@pytest.mark.parametrize("change",["permission","group","cancel","extra-cron"])
def test_workflow_permissions_concurrency_cadence_checked_beyond_bodyhash(system,change):
    x=system;body=wf()
    if change=="permission":body=body.replace(b"actions: write",b"actions: read")
    elif change=="group":body=body.replace(b"group: nfl-lab-single-writer",b"group: another-group")
    elif change=="cancel":body=body.replace(b"cancel-in-progress: false",b"cancel-in-progress: true")
    else:body=body.replace(b"  workflow_dispatch:",b"    - cron: '*/5 * * * *'\n  workflow_dispatch:")
    spec=dict(x.p["parent"],workflow_sha256=c.sha(body))
    url=c.contents_url(c.WORKFLOW,A);x.api.data[url]=content(c.WORKFLOW,body)
    api=c.Metadata(x.api,{url})
    with pytest.raises(c.ControllerError):c.workflow(api,spec,"lab",parent=True)


def test_GET_only_fixed_routes_and_failed_calls_consume_budget():
    count=[]
    url=c.run_url("123")
    def GET(url,cap):
        count.append(url);return c.Reply(500,b'{"state":"error"}')
    api=c.Metadata(GET,{url,"https://evil.invalid/metadata",c.API+"/actions/workflows/lab.yml/dispatches"})
    for bad in ("https://evil.invalid/metadata",c.API+"/actions/workflows/lab.yml/dispatches"):
        with pytest.raises(c.ControllerError):api.get(bad)
    assert count==[]
    for _ in range(20):
        with pytest.raises(c.ControllerError):api.get(url)
    with pytest.raises(c.ControllerError,match="FIXED_METADATA_GET_ROUTE_OR_CALL_CAP"):api.get(url)
    assert len(count)==20


def test_JSON_auth_flags_are_not_a_raw_HTTP_reply():
    url=c.run_url("123")
    api=c.Metadata(lambda *_:dict(status=200,run_authenticated=True),{url})
    with pytest.raises(c.ControllerError,match="GENUINE_METADATA_HTTP_BODY_REQUIRED"):api.get(url)


def test_live_proof_is_not_serializable_or_reusable_for_another_job(system):
    x=system;proof=x.verify()
    with pytest.raises(c.ControllerError,match="LIVE_CONTROLLER_PROOF_CANNOT_BE_SERIALIZED"):pickle.dumps(proof)
    with pytest.raises(c.ControllerError,match="CONTROLLER_PROOF_SCOPE_OR_INTEGRITY"):
        proof.verify(registration_sha256=x.seal,run_id="300",job_id="other",root_sha256=c.sha(x.raw))
    proof.document["actor"]=c.OWNER
    with pytest.raises(c.ControllerError):proof.verify(registration_sha256=x.seal,run_id="300",job_id=x.env["GITHUB_JOB"])


def test_cli_template_is_unregistered_and_cannot_dispatch_or_read_credentials(tmp_path,monkeypatch):
    monkeypatch.setattr(c,"verify_child",lambda *_a,**_k:pytest.fail("NO_EXECUTION_FROM_CLI_JSON"))
    out=tmp_path/"public-template.json"
    assert cli.main(["template","--output",str(out)])==0
    assert c.decode(out.read_bytes())["state"]=="PREPARED_UNREGISTERED"
    assert cli.main(["execute"])==2


def test_only_the_registered_public_canary_receipt_is_an_admitted_report_pin():
    public = "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json"
    assert c.source_path(public) == public
    for path in ["reports/private-draft-canary-v2/secret.json", "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json.bak",
            "reports/private-draft-canary-v2/../ACTUAL_HOSTED_RESULT.json", "reports/other/ACTUAL_HOSTED_RESULT.json",
            "/reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json", "private/ACTUAL_HOSTED_RESULT.json"]:
        with pytest.raises(c.ControllerError, match="PUBLIC_SOURCE_PIN_PATH_ONLY"):
            c.source_path(path)
