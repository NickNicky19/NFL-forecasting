"""Invented weekly captures and injected service only; no real HTTP/models."""
from copy import deepcopy,copy
from contextlib import redirect_stdout
from datetime import datetime,timedelta,timezone
import base64
import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nfl_lab import audit_weekly_retained_v1 as r,audit_weekly_archive_v1 as a
from nfl_lab import private_draft_store as s,gha_private_checkpoint as cp,audit_reference_capture_v1 as reference
from tools import audit_weekly_retained_v1 as cli
from test_audit_weekly_archive_v1 import capture,Service,produce,ROLES,ROOT
from test_private_draft_store_v2 import Response,RUN,SOURCE

CURRENT_RUN="49900000000";CURRENT_SOURCE="b"*40;CURRENT_JOB="fictional_current_weekly_producer"
WORKFLOW=s.REPO+"/.github/workflows/lab.yml@refs/heads/fictional"


class History:
    """Same old real-code archive path, then a genuinely distinct fictional run."""
    def __init__(self,p):
        self.p=p;self.old=Service(p.base);self.calls=[];self.phase="produce";self.times={};self.finished=False
        self.jobs_bad={};self.old_status="completed";self.old_conclusion="success";self.current_bad=False;self.contents_bad=None
        self.codes={name:("FICTIONAL_PINNED_SOURCE "+name).encode() for name in r.HISTORICAL_FILES}
        workflow="name: fictional\non: workflow_dispatch\npermissions: {contents: write, actions: read}\nconcurrency:\n  group: nfl-lab-single-writer\n  cancel-in-progress: false\njobs:\n"
        for name in ROLES.values():workflow+="  "+name+":\n    runs-on: ubuntu-latest\n"
        self.codes[".github/workflows/lab.yml"]=workflow.encode()
        self.codes["config/private-draft-storage-v2.json"]=(ROOT/"config/private-draft-storage-v2.json").read_bytes()
        self.old.transport=self.transport
    def begin(self,phase):
        self.phase=phase;self.old.active=phase;self.times[phase]=[datetime.now(timezone.utc),None]
    def end(self):
        self.times[self.phase][1]=datetime.now(timezone.utc)
        if self.phase=="produce":self.old.writer_completed=self.times[self.phase][1]
        if self.phase=="restore":self.old.reader_completed=self.times[self.phase][1]
    def transport(self,request,timeout):
        self.calls.append(request);url=request.full_url
        if "/contents/" in url:
            name=url.split("/contents/",1)[1].split("?ref=",1)[0]
            assert url.endswith("?ref="+SOURCE)
            raw=self.codes[name]+(b"CORRUPTED" if self.contents_bad==name else b"")
            return Response(dict(type="file",path=name,encoding="base64",size=len(raw),content=base64.b64encode(raw).decode()))
        if "/actions/runs/" not in url:return self.old.server(request,timeout)
        run=url.split("/runs/",1)[1].split("/",1)[0];listing="/jobs?" in url
        if run==CURRENT_RUN:
            if listing:return Response(dict(total_count=1,jobs=[dict(id=9001,name=CURRENT_JOB,run_id=int(run),head_sha=CURRENT_SOURCE,status="in_progress")]))
            return Response(dict(id=int(run),head_sha=SOURCE if self.current_bad else CURRENT_SOURCE,event="workflow_dispatch",run_attempt=1,status="in_progress",
                path=".github/workflows/lab.yml",head_branch="fictional",actor=dict(login="NickNicky19",id=208912933),
                repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
        if run==self.old.qrun:
            if listing:return Response(dict(total_count=3,jobs=[dict(id=p["job"]["api_job_id"],name=p["job"]["job_id"],run_id=int(run),head_sha=SOURCE,
                status="completed",conclusion="success",started_at=p["started_at_utc"],completed_at=p["created_at_utc"])
                for p in (self.old.q["before_proof"],self.old.q["read_proof"],self.old.q)]))
            return Response(dict(id=int(run),head_sha=SOURCE,event="workflow_dispatch",run_attempt=1,status="completed",conclusion="success",
                path=".github/workflows/lab.yml",head_branch="fictional",actor=dict(login="NickNicky19",id=208912933),
                repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
        assert run==RUN
        if not listing:return Response(dict(id=int(run),head_sha=SOURCE,event="workflow_dispatch",run_attempt=1,
            status=self.old_status if self.finished else "in_progress",conclusion=self.old_conclusion if self.finished else None,
            path=".github/workflows/lab.yml",head_branch="fictional",actor=dict(login="NickNicky19",id=208912933),
            repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
        jobs=[]
        for n,role in enumerate(ROLES):
            if role not in self.times:continue
            start,end=self.times[role];row=dict(id=777+n,name=ROLES[role],run_id=int(RUN),head_sha=SOURCE,
                status="completed" if end else "in_progress",conclusion="success" if end else None,
                started_at=start.isoformat(),completed_at=(end or datetime.now(timezone.utc)).isoformat())
            row.update(self.jobs_bad.get(role,{}));jobs.append(row)
        return Response(dict(total_count=len(jobs),jobs=jobs))


def full_r0(p):
    ts=lambda n:(datetime.now(timezone.utc)+timedelta(seconds=n)).isoformat()
    native=p.body("r0/native.json.gz",gzip.compress(b"FICTIONAL_OPAQUE_NATIVE",mtime=0))
    board=p.put("r0/output/data/week.json",dict(fictional_original_board=True))
    meta=p.put("r0/output/data/meta.json",dict(fictional_original_meta=True))
    cache=p.body("r0/data/cache/default.json",b"FICTIONAL_OPAQUE_CACHE_NOT_A_PARSED_OUTCOME")
    empty=p.body("r0/data/cache/empty.json",b"")
    files={"output/data/week.json":board,"output/data/meta.json":meta,"data/cache/default.json":cache,"data/cache/empty.json":empty}
    state=p.put("r0/state.json",dict(schema_version=reference.VERSION+"-state",source=reference.SOURCE,procedure=reference.PROCEDURE,
        model=reference.ORIGINAL_MODEL,frozen_R0_identity_sha256=reference.R0_IDENTITY,source_files=reference.SOURCE_FILES,
        files=files,native_sha256=native["sha256"],fits=0,public_release=False,actual_completed_at=ts(-10)))
    issued=ts(-9)
    prepared=p.put("r0/prepared.json",dict(current_values_used=False,slate=dict(game_cutoffs=dict(fictional=ts(3600)))))
    controls=p.put("r0/controls.json",dict(rows=[],actual_issued_at=issued))
    observation=p.put("r0/observation.json",dict(status=200,sha256="a"*64,completed_at=ts(-30)))
    native_persisted=ts(-12)
    worker=dict(state="ORIGINAL_R0_DEFAULT_PROCEDURE_CAPTURED",native=native,next_state=state,board=board,meta=meta,
        source_observations=[observation],fixed_original_default_refresh=True,fits=0,public_release=False,
        actual_source_completed_at=ts(-16),actual_native_observed_at=ts(-15),actual_native_persist_completed_at=native_persisted)
    p.put("r0/WORKER_COMPLETE.json",worker)
    completion=p.put("r0/control-completion.json",dict(schema_version=reference.VERSION+"-control-completion",forecast_binding=controls,
        actual_issued_at=issued,body_persist_completed_at=ts(-8),remote_durability_qualified=False,fits=0,public_release=False,
        source_receipt_sha256=s.sha(s.canonical(worker)),original_native_persist_completed_at=native_persisted))
    capture=p.put("r0/CAPTURE_COMPLETE.json",dict(schema_version=reference.VERSION+"-capture",state="ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE",
        prepared=prepared,native=native,original_board=board,next_state=state,control_forecast_rows=controls,control_completion=completion,
        fixed_original_default_refresh=True,fits=0,public_release=False,actual_completed_at=ts(-7)))
    return capture,completion


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    # One full unchanged producer/reader/exporter chain is sufficient. Each
    # rejection below gets independent registration, transport and asset data.
    p=capture.__wrapped__(tmp_path_factory.mktemp("retained-original"));history=History(p);r0,completion=full_r0(p)
    snapshot=a.collect(p.root,p.context,storage=p.storage,output=p.base/"collection",r0=r0)
    # Fixture for the complete declared closure. The archive owner owns adding
    # this missing role to collect(); this new reader never invents its bytes.
    if "r0/control_completion.json" not in {f["logical_path"] for f in snapshot["files"]}:
        item=cp.file_item(completion,"r0/control_completion.json","control");snapshot["files"].append(item)
        snapshot["files"].sort(key=lambda f:f["logical_path"])
        snapshot["census"]["physical_origins"][item["logical_path"]]=completion
        snapshot["census"]["logical_files"]=len(snapshot["files"])
        snapshot["census"]["logical_bytes"]=sum(f["bytes"] for f in snapshot["files"])
    history.begin("produce");handoff,writer,snapshot=produce(p,history.old,snapshot=snapshot);history.end()
    history.begin("restore")
    reader=a.restore(handoff,history.old.factory(p.base/"old-reader-journal","restore"),history.old.package,storage=p.storage,
        output=p.base/"old-reader",root_go_sha256="d"*64,pending_census=history.old.census)
    history.end();reader_handoff=cp.strict_json((p.base/"old-reader/READER_HANDOFF.json").read_bytes())
    history.begin("consume")
    a.consume(reader_handoff,history.old.factory(p.base/"old-exporter-journal","consume"),history.old.package,storage=p.storage,
        output=p.base/"old-exporter",root_go_sha256="d"*64,pending_census=history.old.census)
    history.end();history.finished=True
    return SimpleNamespace(p=p,history=history,reader_handoff=reader_handoff,snapshot=snapshot,old_reader=reader,
        old_raw={f["path"]:Path(f["path"]).read_bytes() for f in snapshot["files"]})


@pytest.fixture
def chain(saved,tmp_path):
    p=copy(saved.p);p.base=tmp_path;p.storage.register_root(tmp_path)
    history=copy(saved.history);history.calls=[];history.codes=dict(saved.history.codes);history.jobs_bad={}
    history.old=copy(saved.history.old);history.old.calls=[]
    history.old.server=copy(saved.history.old.server);history.old.server.calls=[]
    history.old.server.assets=deepcopy(saved.history.old.server.assets);history.old.transport=history.transport
    reader_handoff=deepcopy(saved.reader_handoff)
    request=r.prepare_request(ROOT,reader_handoff,history.old.package,exporter_api_job_id=779,
        historical_source_sha256={name:s.sha(body) for name,body in history.codes.items()},cache=saved.p.base/"cache",state_root=saved.p.base/"state",
        output=p.base/"new-retained",pending_census=history.old.census)
    request["approved"]=True;issued=datetime.now(timezone.utc)
    authority=dict(schema_version=r.VERSION+"-native-authority",phase=r.PHASE,request_sha256=s.sha(s.canonical(request)),repository=s.REPO,
        owner_root_go_sha256="f"*64,owner_root_checked=True,actual_actions_api_authenticated=True,api_job_id=9001,source_sha=CURRENT_SOURCE,
        run_id=CURRENT_RUN,run_attempt=1,job_id=CURRENT_JOB,workflow_ref=WORKFLOW,issued_at_utc=issued.isoformat(),
        expires_at_utc=(issued+timedelta(minutes=15)).isoformat(),fits=0,remote_writes=0,protected_outcome_reads=0,public_release=False)
    journal=p.base/"new-journal";p.storage.register_root(journal)
    class Factory:
        def __init__(self):self.clients=[]
        def __call__(self,operation):
            assert operation=="restore"
            job=dict(execution_lane="github_actions",workflow_ref=WORKFLOW,workflow_sha=CURRENT_SOURCE,job_id=CURRENT_JOB,permission="write",
                event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
            c=r.ReadClient("ghs_FICTIONAL",CURRENT_RUN,journal=journal,source_sha=CURRENT_SOURCE,job=job,operation="restore",
                transport=history.transport,extra_routes=r.routes(request));c.bind(history.old.binding);self.clients.append(c);return c
    return SimpleNamespace(p=p,history=history,request=request,authority=authority,factory=Factory(),snapshot=saved.snapshot,old_reader=saved.old_reader,
        calls_before=len(history.calls),old_raw=saved.old_raw)


def execute(c):
    # The actual CLI has its own fresh process/envelope. A shared combined
    # pytest process may contain unrelated ML libraries; inject only its RSS.
    with patch.object(r.resource,"getrusage",return_value=SimpleNamespace(ru_maxrss=1024)):
        return r.restore(c.request,c.factory,storage=c.p.storage,authority=c.authority,root=ROOT)


def reseal(c):c.authority["request_sha256"]=s.sha(s.canonical(c.request))


def test_cross_run_restores_all18_losers_inputs_epoch_and_complete_original_R0_without_POST(chain):
    c=chain;posts=len([q for q in c.history.calls if q.method=="POST"]);result=execute(c)
    assert result["state"]=="PRIVATE_PRIOR_CAPTURE_RESTORED" and result["current"]["run_id"]==CURRENT_RUN
    assert result["historical_reader_witness"]["restorer"]==c.request["reader_handoff"]["restorer"]
    assert result["historical_producer_proof"]["identity"]["run_id"]==RUN
    assert all(p["run_id"]==CURRENT_RUN and p["source_sha"]==CURRENT_SOURCE for p in result["current_restore_proofs"])
    assert all(p["run_id"]==RUN and p["source_sha"]==SOURCE for p in result["historical_reader_witness"]["proofs"])
    assert all(q.method=="GET" for q in c.history.calls[c.calls_before:])
    assert len([q for q in c.history.calls if q.method=="POST"])==posts
    assert sum(n.startswith("runtime/candidates/") and n.endswith(".jsonl.gz") for n in result["aliases"])==18
    for f in c.snapshot["files"]:
        assert Path(result["aliases"][f["logical_path"]]["path"]).read_bytes()==c.old_raw[f["path"]]
        assert Path(f["path"]).read_bytes()==c.old_raw[f["path"]]
    assert result["previous_state"]==result["aliases"]["r0/next_state.json"]
    assert set(result["previous_state_aliases"])=={"output/data/week.json","output/data/meta.json","data/cache/default.json","data/cache/empty.json"}
    assert Path(result["previous_state_aliases"]["data/cache/empty.json"]["path"]).read_bytes()==b""
    assert set(a.CONTEXT)<=set(result["metadata"])
    assert result["model_replay_performed"] is result["public_release"] is result["public_export_authorized"] is False
    assert result["remote_writes"]==result["model_decodes"]==result["protected_outcome_reads"]==0
    assert all(q.calls<=40 for q in c.factory.clients) and len(c.factory.clients)<=11
    assert (c.p.base/"new-retained/RETAINED_RESULT.json").is_file()


def test_next_run_can_restore_prior_capture_using_unchanged_source_code(chain,monkeypatch):
    # A new run/process/job supplies new current proofs. Daily restoration does
    # not require an unrelated source commit merely to make the SHA different.
    import sys
    monkeypatch.setattr(sys.modules[__name__],"CURRENT_SOURCE",SOURCE)
    chain.authority["source_sha"]=SOURCE
    result=execute(chain)
    assert result["current"]["source_sha"]==result["original_archive"]["source_sha"]==SOURCE
    assert result["current"]["run_id"]!=result["original_archive"]["run_id"]
    assert result["current"]["process_identity"]!=result["original_archive"]["producer"]["process_identity"]
    assert result["remote_writes"]==0
    assert all(q.calls<=40 for q in chain.factory.clients) and len(chain.factory.clients)<=11
    assert (chain.p.base/"new-retained/RETAINED_RESULT.json").is_file()


@pytest.mark.parametrize("role",["produce","restore","consume"])
@pytest.mark.parametrize("field,value",[("conclusion","failure"),("head_sha",CURRENT_SOURCE),("id",9999)])
def test_prior_job_failure_wrong_source_or_registered_API_id_blocks_before_private_payload_GET(chain,role,field,value):
    c=chain;c.history.jobs_bad[role]={field:value}
    with pytest.raises(s.StoreError):execute(c)
    assert not any("/releases/assets/" in q.full_url for q in c.history.calls[c.calls_before:])


@pytest.mark.parametrize("what",["in_progress","failure","old_as_current","current_bad"])
def test_completed_prior_run_and_distinct_current_identity_are_mandatory(chain,what):
    c=chain
    if what=="in_progress":c.history.old_status="in_progress"
    elif what=="failure":c.history.old_conclusion="failure"
    elif what=="old_as_current":c.authority["run_id"]=RUN;c.authority["source_sha"]=SOURCE
    else:c.history.current_bad=True
    with pytest.raises(s.StoreError):execute(c)
    assert not any("/releases/assets/" in q.full_url for q in c.history.calls[c.calls_before:])


@pytest.mark.parametrize("what",["hash","permissions","group"])
def test_historical_code_bytes_and_actual_auth_permissions_are_separately_verified(chain,what):
    c=chain
    if what=="hash":c.history.contents_bad="nfl_lab/audit_weekly_archive_v1.py"
    else:
        raw=c.history.codes[".github/workflows/lab.yml"]
        raw=raw.replace(b"contents: write",b"contents: read") if what=="permissions" else raw.replace(b"nfl-lab-single-writer",b"another-group")
        c.history.codes[".github/workflows/lab.yml"]=raw;c.request["historical_source_sha256"][".github/workflows/lab.yml"]=s.sha(raw);reseal(c)
    with pytest.raises(s.StoreError):execute(c)
    assert not any("/releases/assets/" in q.full_url for q in c.history.calls[c.calls_before:])


def test_request_cannot_switch_old_handoff_under_a_current_GO(chain):
    c=chain;c.request["exporter_api_job_id"]=8888
    with pytest.raises(s.StoreError,match="FRESH_PARENT_AUTHORITY_BINDS"):execute(c)


def test_native_class_rejects_mutation_and_post_reservation_before_transport(chain):
    c=chain;client=c.factory("restore");start=len(c.history.calls)
    with pytest.raises(s.StoreError,match="GET_ONLY"):client.request(s.API,method="POST",data=b"private")
    with pytest.raises(s.StoreError,match="NO_POST_RESERVATIONS"):client.reserve("key",b"private")
    assert len(c.history.calls)==start


@pytest.mark.parametrize("corruption",["missing_proof","unrelated_group","relabelled_source","reader_api"])
def test_historical_proofs_are_not_relabelled_or_replaced_by_current_proofs(chain,corruption):
    c=chain;d=c.request["reader_handoff"]["witness_descriptor"]
    asset=next(v for v in c.history.old.server.assets if v["id"]==d["entry"]["payload_asset_id"])
    witness=a.unpack(asset["body"],a.WITNESS_CAP)
    if corruption=="missing_proof":witness["proofs"].pop()
    elif corruption=="unrelated_group":witness["proofs"][-1]["payload_sha256"]="e"*64
    elif corruption=="relabelled_source":witness["proofs"][0]["source_sha"]=CURRENT_SOURCE
    else:witness["proofs"][0]["job"]["api_job_id"]=9001
    # A changed registered witness remains invalid even when exact new bytes
    # and its native descriptor agree. This exercises proof semantics too.
    body=gzip.compress(s.canonical(witness),mtime=0);asset["body"]=body;asset["size"]=len(body);asset["digest"]="sha256:"+s.sha(body)
    p=cp.payload(body);d["entry"]["payload"]=p;d["entry"]["payload_name"]="blob-"+p["sha256"]+".bin";asset["name"]=d["entry"]["payload_name"]
    encoded=s.canonical(d["entry"]);d["manifest_sha256"]=s.sha(encoded);d["manifest_bytes"]=len(encoded)
    manifest=next(v for v in c.history.old.server.assets if v["id"]==d["manifest_asset_id"])
    manifest.update(name="manifest-"+s.sha(encoded)+".json",body=encoded,size=len(encoded),digest="sha256:"+s.sha(encoded))
    reseal(c)
    with pytest.raises(s.StoreError):execute(c)


def test_missing_control_completion_or_cache_closure_never_fabricates_originals(chain):
    c=chain;result=execute(c)
    index=a.unpack(cp.read_ref(result["original_index"],a.INDEX_CAP),a.INDEX_PLAIN_CAP)
    for name in ("r0/control_completion.json","r0/cache/data/cache/default.json"):
        aliases=deepcopy(result["aliases"]);aliases.pop(name)
        with pytest.raises(s.StoreError):r.r0_closure(index,aliases,c.p.storage)
    aliases=deepcopy(result["aliases"]);aliases["r0/cache/data/cache/default.json"]["sha256"]="e"*64
    with pytest.raises(s.StoreError,match="R0_ORIGINAL_PHYSICAL_METADATA_BINDING"):r.r0_closure(index,aliases,c.p.storage)


def test_old_strict_archive_predecessor_stays_same_run(chain):
    c=chain;client=c.factory("restore");client.authenticate_actions_job()
    with pytest.raises(s.StoreError,match="SAME_SOURCE_ARCHIVE_READER"):
        a.predecessor(client,c.request["reader_handoff"]["archive"]["producer"],[])


def test_full_frozen_request_preparation_remains_unapproved(chain):
    c=chain;p=deepcopy(c.request);p["approved"]=False
    with pytest.raises(s.StoreError,match="APPROVED_EXACT"):r.validate_request(p,ROOT)
    p=deepcopy(c.request);p["reader_handoff"].pop("witness_descriptor")
    with pytest.raises(s.StoreError,match="PRIOR_READER_HANDOFF"):r.validate_request(p,ROOT)


def test_workflow_duplicate_permission_key_is_not_accepted(chain):
    raw=chain.history.codes[".github/workflows/lab.yml"].replace(b"    runs-on: ubuntu-latest",b"    runs-on: ubuntu-latest\n    permissions: {contents: read}\n    permissions: {contents: write, actions: read}",1)
    with pytest.raises(s.StoreError,match="DUPLICATE_HISTORICAL_WORKFLOW_KEY"):
        r.workflow_permissions(raw,chain.request["reader_handoff"]["archive"])


def test_cli_preparation_and_fixed_error_do_not_log_private_library_text():
    stream=io.StringIO()
    with redirect_stdout(stream):assert cli.main(["restore"])==2
    assert "PREPARATION_ONLY" in stream.getvalue()
    for error,expected in [(s.StoreError("EXACT_RETAINED_BLOCKER"),"EXACT_RETAINED_BLOCKER"),
            (s.StoreError("private value"),"RETAINED_WEEKLY_OPERATION_FAILED"),(RuntimeError("PRIVATE_LIBRARY_DETAIL"),"RETAINED_WEEKLY_OPERATION_FAILED")]:
        stream=io.StringIO()
        with patch("tools.private_draft_store_v2.limits"),patch.object(cli,"run",side_effect=error),redirect_stdout(stream):
            assert cli.main(["restore","--execute"])==1
        assert json.loads(stream.getvalue())["reason"]==expected
        assert "private value" not in stream.getvalue() and "PRIVATE_LIBRARY_DETAIL" not in stream.getvalue()


def native(tmp_path):
    current=datetime.now(timezone.utc);root='{"FICTIONAL_NEW_ROOT":true}'
    event=tmp_path/"event.json";event.write_bytes(s.canonical(dict(repository=dict(full_name=s.REPO),inputs=dict(mode=r.MODE,
        inference_builder_go_json=root,inference_builder_go_sha256=s.sha(root.encode())))))
    env=dict(GITHUB_ACTIONS="true",GITHUB_REPOSITORY=s.REPO,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",
        GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933",STORE_PERMISSION="write",GITHUB_SHA=CURRENT_SOURCE,
        GITHUB_WORKFLOW_SHA=CURRENT_SOURCE,GITHUB_RUN_ID=CURRENT_RUN,GITHUB_JOB=CURRENT_JOB,GITHUB_WORKFLOW_REF=WORKFLOW,GITHUB_EVENT_PATH=str(event))
    value=dict(schema_version=r.VERSION+"-native-authority",phase=r.PHASE,request_sha256="e"*64,repository=s.REPO,
        owner_root_go_sha256=s.sha(root.encode()),owner_root_checked=True,actual_actions_api_authenticated=True,api_job_id=9001,
        source_sha=CURRENT_SOURCE,run_id=CURRENT_RUN,run_attempt=1,job_id=CURRENT_JOB,workflow_ref=WORKFLOW,
        issued_at_utc=(current-timedelta(seconds=10)).isoformat(),expires_at_utc=(current+timedelta(minutes=10)).isoformat(),
        fits=0,remote_writes=0,protected_outcome_reads=0,public_release=False)
    return value,env


def checked_native(value,env):
    body=s.canonical(value)
    with patch.object(r.subprocess,"check_output",side_effect=[CURRENT_SOURCE+"\n",""]):
        return r.checked_authority(body,s.sha(body),"e"*64,env,ROOT)


def test_new_parent_native_authority_uses_only_exact_current_inference_root_input(tmp_path):
    value,env=native(tmp_path);assert checked_native(value,env)==value
    event=cp.strict_json(Path(env["GITHUB_EVENT_PATH"]).read_bytes())
    event["inputs"]["bootstrap_locators_json"]=event["inputs"].pop("inference_builder_go_json")
    Path(env["GITHUB_EVENT_PATH"]).write_bytes(s.canonical(event))
    with pytest.raises(s.StoreError,match="ACTUAL_NEW_WEEKLY_RETAINED_ROOT_EVENT"):checked_native(value,env)


@pytest.mark.parametrize("field,value",[("phase","restore"),("request_sha256","f"*64),("source_sha",SOURCE),
    ("run_id",RUN),("owner_root_checked",False),("remote_writes",1),("protected_outcome_reads",1),("public_release",True)])
def test_changed_native_phase_source_binding_or_rights_is_rejected(tmp_path,field,value):
    a,env=native(tmp_path);a[field]=value
    with pytest.raises(s.StoreError):checked_native(a,env)


def test_expired_or_uncommitted_native_source_is_not_reused(tmp_path):
    a,env=native(tmp_path);a["expires_at_utc"]=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    with pytest.raises(s.StoreError,match="FRESH_RETAINED_WEEKLY_ROOT_CLOCK"):checked_native(a,env)
    a,env=native(tmp_path);body=s.canonical(a)
    with patch.object(r.subprocess,"check_output",side_effect=[CURRENT_SOURCE+"\n"," M nfl_lab/audit_weekly_retained_v1.py\n"]),\
            pytest.raises(s.StoreError,match="CLEAN_COMMITTED_CURRENT_RETAINED_HELPERS"):
        r.checked_authority(body,s.sha(body),"e"*64,env,ROOT)
