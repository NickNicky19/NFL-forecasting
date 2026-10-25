"""Fictional cross-run services and trained stubs only: no real private reads/fits."""
import base64
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_lab import audit_count_retained_v1 as r, audit_count_checkpoint_v1 as effective
from nfl_lab import audit_count_requalify_v1 as audit, gha_private_checkpoint as cp, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_count_retained_v1 as cli, audit_count_verification_receipt_v1 as receipt
from test_audit_count_checkpoint_v1 import effective_packet, produce
from test_private_draft_store_v2 import RUN, SOURCE, Response, Server

ROOT = Path(__file__).resolve().parents[1]
CURRENT_RUN, CURRENT_SOURCE, CURRENT_JOB = "40000000002", "b"*40, "fictional_retained_reader"


@pytest.fixture(scope="module")
def retained_origin(effective_packet, tmp_path_factory):
    origin_root = tmp_path_factory.mktemp("fictional-retained-origin")
    service, handoff = produce(effective_packet,origin_root)
    service.writer_completed = audit.now()
    service.reader_started = audit.now()
    service.reader_active = True
    fresh = tmp_path_factory.mktemp("fictional-original-reader")
    storage = OperationalStorage(fresh/"cache",effective_packet[1],state=fresh/"state")
    storage.register_root(fresh)
    journal = fresh/"journal";journal.mkdir(mode=0o700)
    restored = effective.restore(handoff,service.factory(journal,reader=True),storage=storage,
        output=fresh/"original-restore",root_go_sha256="d"*64)
    reader_completed = audit.now()
    catalog = restored["replay_catalog"]
    public = dict(schema_version=receipt.VERSION,repository=store.REPO,source_sha=SOURCE,run_id=RUN,
        run_attempt=1,reader_job_id=effective.READER_JOB,reader_api_job_id=778,root_go_sha256="d"*64,
        restored_control_sha256=store.sha(store.canonical(restored)),replay_catalog_sha256=store.sha(effective.safe_replay_catalog(catalog)),
        replay_catalog=catalog,model_pairs=18,fits=0,model_artifact_durability=True,successful_forecast=False,
        scientific_qualification=False,public_release=False)
    payload = dict(name=receipt.NAME,head_sha=SOURCE,status="completed",conclusion="success",external_id=RUN+":1",
        output=dict(title=receipt.TITLE,summary=store.canonical(public).decode()))
    source_bytes = {name:(ROOT/name).read_bytes() for name in r.HISTORICAL_FILES}
    registration, _ = r.templates(ROOT)
    registration.update(approved=True,state="ROOT_REGISTERED_RETAINED_EFFECTIVE18",registered_at_utc=audit.now().isoformat(),
        qualified_runtime=dict(binding_sha256=store.sha(store.canonical(service.runtime)),
            qualification_sha256=store.sha(store.canonical(service.q))))
    registration["origin"] = dict(run_id=RUN,source_sha=SOURCE,workflow_ref=handoff["producer"]["workflow_ref"],
        run_conclusion="failure",handoff=handoff,
        reader={k:restored["reader"][k] for k in r.PAST_READER_KEYS},verification_receipt=public,
        restore_control_sha256=public["restored_control_sha256"],replay_catalog=catalog,verification_check_run_id=991,
        verification_body_sha256=store.sha(store.canonical(payload)),
        source_code_sha256={name:store.sha(body) for name,body in source_bytes.items()})
    check = dict(payload,id=991,url=store.API+"/check-runs/991",app=dict(slug="github-actions"),
        completed_at=restored["actual_completed_at"])
    return dict(service=service,registration=registration,restored=restored,policy=effective_packet[1],
        source_bytes=source_bytes,check=check,reader_completed=reader_completed,origin_root=origin_root)


class CrossRunService:
    def __init__(self, packet):
        self.packet=packet;self.registration=deepcopy(packet["registration"])
        self.bad_current_actor=False;self.bad_current_branch=False
        self.requests=[];self.writer_success=True;self.reader_success=True;self.bad_code=False
        self.current_bad_source=False;self.bad_check=False
        self.job_name=CURRENT_JOB
        self.private_server=Server()
        self.private_server.tag=packet["service"].server.tag
        self.private_server.assets=deepcopy(packet["service"].server.assets)

    def __call__(self,request,timeout):
        self.requests.append(request)
        assert request.method == "GET", "adapter attempted a remote write"
        url=request.full_url;o=self.registration["origin"];service=self.packet["service"]
        if "/contents/" in url:
            name=url.split("/contents/",1)[1].split("?ref=",1)[0]
            assert url==r.source_url(SOURCE,name)
            body=self.packet["source_bytes"][name]
            if self.bad_code:body+=b"UNREGISTERED_CHANGE"
            return Response(dict(type="file",path=name,encoding="base64",size=len(body),content=base64.b64encode(body).decode()))
        if url==store.API+"/check-runs/991":
            check=deepcopy(self.packet["check"])
            if self.bad_check:check["output"]["summary"]+=' '
            return Response(check)
        if "/actions/runs/" in url:
            run_id=url.split("/runs/",1)[1].split("/",1)[0]
            jobs="/jobs?" in url
            if run_id==CURRENT_RUN:
                if jobs:
                    return Response(dict(total_count=1,jobs=[dict(id=779,name=self.job_name,status="in_progress",run_id=int(CURRENT_RUN),head_sha=CURRENT_SOURCE)]))
                return Response(dict(id=int(CURRENT_RUN),head_sha="c"*40 if self.current_bad_source else CURRENT_SOURCE,
                    event="workflow_dispatch",run_attempt=1,status="in_progress",path=".github/workflows/lab.yml",
                    head_branch="wrong" if self.bad_current_branch else "fictional-current",
                    actor=dict(login="unregistered" if self.bad_current_actor else "NickNicky19",id=208912933),
                    repository=dict(full_name=store.REPO),head_repository=dict(full_name=store.REPO)))
            if run_id==RUN:
                if not jobs:
                    return Response(dict(id=int(RUN),head_sha=SOURCE,event="workflow_dispatch",run_attempt=1,status="completed",
                        conclusion=o["run_conclusion"],path=".github/workflows/lab.yml",head_branch="fictional",
                        repository=dict(full_name=store.REPO),head_repository=dict(full_name=store.REPO)))
                return Response(dict(total_count=2,jobs=[
                    dict(id=777,name=effective.WRITER_JOB,run_id=int(RUN),head_sha=SOURCE,status="completed",
                        conclusion="success" if self.writer_success else "failure",started_at=service.writer_started.isoformat(),
                        completed_at=service.writer_completed.isoformat()),
                    dict(id=778,name=effective.READER_JOB,run_id=int(RUN),head_sha=SOURCE,status="completed",
                        conclusion="success" if self.reader_success else "failure",started_at=service.reader_started.isoformat(),
                        completed_at=self.packet["reader_completed"].isoformat())]))
            if run_id==service.q["run_id"]:
                if not jobs:
                    return Response(dict(id=int(run_id),head_sha=service.q["source_sha"],event="workflow_dispatch",run_attempt=1,
                        status="completed",conclusion="success",path=".github/workflows/lab.yml",
                        repository=dict(full_name=store.REPO),head_repository=dict(full_name=store.REPO)))
                proofs=[service.q["before_proof"],service.q["read_proof"],service.q]
                return Response(dict(total_count=3,jobs=[dict(id=p["job"]["api_job_id"],name=p["job"]["job_id"],
                    head_sha=p["source_sha"],run_id=int(run_id),status="completed",conclusion="success",
                    started_at=p["started_at_utc"],completed_at=p["created_at_utc"]) for p in proofs]))
            raise AssertionError("unregistered historical run")
        return self.private_server(request,timeout)

    def factory(self,journal):
        outer=self
        class Factory:
            def __init__(self):
                self.clients=[];self.qualification=outer.packet["service"].q
            def __call__(self,operation):
                assert operation=="restore" and len(self.clients)<9
                job=dict(execution_lane="github_actions",workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/fictional-current",
                    workflow_sha=CURRENT_SOURCE,job_id=outer.job_name,permission="write",event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
                client=r.ReadClient("ghs_FICTIONAL",CURRENT_RUN,journal=journal,source_sha=CURRENT_SOURCE,
                    job=job,transport=outer,operation="restore",extra_routes=r.routes(outer.registration,self.qualification))
                self.clients.append(client);client.authenticate_actions_job();client.bind(outer.packet["service"].runtime)
                return client
        return Factory()

    def model_body_requests(self):
        canary_id=self.packet["service"].runtime["canary_asset_id"]
        return [q for q in self.requests if "/releases/assets/" in q.full_url
                and q.get_header("Accept")=="application/octet-stream" and not q.full_url.endswith("/"+str(canary_id))]


@pytest.fixture
def current_scope(retained_origin,tmp_path):
    http=CrossRunService(retained_origin)
    root=tmp_path/"current"
    storage=OperationalStorage(root/"cache",retained_origin["policy"],state=root/"state")
    storage.register_root(root)
    journal=root/"journal";journal.mkdir(mode=0o700)
    return SimpleNamespace(http=http,root=root,storage=storage,factory=http.factory(journal),registration=http.registration)


def test_cross_run_restores_all18_without_changing_originals_or_same_run_API(current_scope):
    import subprocess
    import sys
    s=current_scope
    result=r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    assert result["model_pairs"]==18 and result["files"]==38 and result["current_loader_replay"] is True
    assert result["current"]["run_id"]==CURRENT_RUN and result["origin"]["run_id"]==RUN
    assert result["current"]["source_sha"]==CURRENT_SOURCE and result["origin"]["source_sha"]==SOURCE
    assert result["origin"]["run_conclusion"]=="failure"  # Successful jobs in a failed root are valid.
    assert all(q.method=="GET" for q in s.http.requests)
    assert all(p["run_id"]==CURRENT_RUN and p["source_sha"]==CURRENT_SOURCE for p in result["proofs"])
    assert all(c.calls<=store.MAX_CALLS for c in s.factory.clients)
    assert sum(c.calls for c in s.factory.clients)<=360
    assert result["fits"]==result["remote_writes"]==result["protected_outcome_reads"]==0
    assert result["successful_forecast"] is result["public_release"] is result["catalog_epoch_ready"] is result["weekly_choice_restored"] is False
    aliases=json.loads(Path(result["relocation_catalog"]["path"]).read_bytes())["models"]
    assert len(aliases)==18
    for row,old in zip(aliases,s.registration["origin"]["replay_catalog"]["slots"]):
        assert row["original_verified_reader_manifest_sha256"]==old["manifest_sha256"]
        assert row["current_manifest"]["sha256"]!=old["manifest_sha256"]
        manifest=json.loads(Path(row["current_manifest"]["path"]).read_bytes())
        assert manifest["fit_receipt"]==row["original_fit_receipt"]
        assert manifest["training_cutoff_utc"]==row["original_training_cutoff_utc"]
        assert manifest["procedure_version"]==old["procedure_version"]
        assert manifest["model"]["sha256"]==old["model_sha256"]
    # Check with an actual separate local process, using only fictional proof
    # metadata and an injected transport that cannot make HTTP calls. No
    # alternate process identity is fabricated to bypass the normal checker.
    verifier = """
import json,sys,tempfile
from pathlib import Path
from nfl_lab import private_draft_store as store
p=json.load(sys.stdin)
def no_http(*unused):raise AssertionError('proof checker attempted HTTP')
with tempfile.TemporaryDirectory() as directory:
    journal=Path(directory);journal.chmod(0o700)
    client=store.Client('ghs_FICTIONAL',p['current']['run_id'],journal=journal,
        source_sha=p['current']['source_sha'],job=p['proofs'][0]['job'],transport=no_http,operation='restore')
    client.bind(p['binding'])
    for proof in p['proofs']:store.check_proof(client,proof,'restore')
print('STORE21_PROOFS_CHECKED_IN_SEPARATE_PROCESS')
"""
    checked=subprocess.run([sys.executable,"-c",verifier],cwd=ROOT,
        input=store.canonical(dict(current=result["current"],proofs=result["proofs"],binding=s.http.packet["service"].runtime)),
        capture_output=True,timeout=30,check=True)
    assert checked.stdout.strip()==b"STORE21_PROOFS_CHECKED_IN_SEPARATE_PROCESS"


@pytest.mark.parametrize("attribute",["writer_success","reader_success","bad_check","bad_code","current_bad_source",
    "bad_current_actor","bad_current_branch"])
def test_bad_historical_or_current_evidence_stops_before_model_body(current_scope,attribute):
    s=current_scope
    setattr(s.http,attribute,False if attribute.endswith("success") else True)
    with pytest.raises((store.StoreError,ValueError)):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    assert not s.http.model_body_requests()
    assert all(q.method=="GET" for q in s.http.requests)


def test_duplicate_attempt_cannot_read_or_retry(current_scope):
    s=current_scope
    s.http.bad_check=True
    with pytest.raises(store.StoreError):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    calls=len(s.http.requests)
    with pytest.raises(store.StoreError,match="NO_RETRY"):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    assert len(s.http.requests)==calls


def test_same_run_success_reader_still_rejects_cross_run(current_scope):
    s=current_scope
    s.http.job_name=effective.READER_JOB
    with pytest.raises(store.StoreError,match="FRESH_SAME_RUN_EFFECTIVE_READER"):
        effective.restore(s.registration["origin"]["handoff"],s.factory,storage=s.storage,
            output=s.root/"original-api",root_go_sha256="d"*64)
    assert not s.http.model_body_requests()


def test_changed_model_code_or_registration_approval_rejects_before_HTTP(current_scope):
    s=current_scope
    s.registration["approved"]=False
    with pytest.raises(store.StoreError,match="REGISTERED_RETAINED_SUCCESS_REQUIRED"):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    s.registration["approved"]=True
    s.registration["model_code_sha256"]["weekly_future_inference.py"]="f"*64
    s.registration["origin"]["source_code_sha256"]["nfl_lab/weekly_future_inference.py"]="f"*64
    with pytest.raises(store.StoreError,match="MODEL_CODE_CHANGED"):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    assert not s.http.requests


def test_expired_current_scope_stops_before_first_private_payload(current_scope):
    s=current_scope
    def expired():raise store.StoreError("RETAINED_GO_EXPIRED_BEFORE_READ")
    with pytest.raises(store.StoreError,match="GO_EXPIRED"):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64,check_authority=expired)
    assert not s.http.model_body_requests()


def test_private_client_is_GET_only(current_scope):
    client=current_scope.factory("restore")
    with pytest.raises(store.StoreError,match="GET_ONLY_NO_REMOTE_WRITES"):
        client.request(store.API+"/check-runs",method="POST",data=b"FORBIDDEN")


def test_preparation_is_unapproved_and_restore_preparation_reads_no_context(tmp_path):
    class NoEnvironment:
        def get(self,*args):raise AssertionError("credential/context discovery")
    output=io.StringIO()
    with redirect_stdout(output):
        assert cli.main(["prepare","--output",str(tmp_path/"prepared")],environ=NoEnvironment())==0
    registration=json.loads((tmp_path/"prepared/REGISTRATION.template.json").read_bytes())
    go=json.loads((tmp_path/"prepared/GO.template.json").read_bytes())
    assert registration["approved"] is go["approved"] is False
    with pytest.raises(store.StoreError):r.validate_registration(registration)
    with redirect_stdout(io.StringIO()):
        assert cli.main(["restore"],environ=NoEnvironment())==2


def test_unknown_or_orphan_runtime_bytes_block_before_model_payload(current_scope):
    s=current_scope
    for index in range(4):s.http.private_server.add("fictional-orphan-"+str(index),size=store.ASSET_CAP)
    with pytest.raises(store.StoreError,match="RUNTIME_BYTES_CAP"):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    assert not s.http.model_body_requests()


def test_corrupt_private_index_never_becomes_replayed_success(current_scope):
    s=current_scope
    payload_id=s.registration["origin"]["handoff"]["index_descriptor"]["entry"]["payload_asset_id"]
    next(a for a in s.http.private_server.assets if a["id"]==payload_id)["body"]+=b"CORRUPT"
    with pytest.raises(store.StoreError):
        r.restore(s.registration,s.factory,storage=s.storage,output=s.root/"retained",current_go_sha256="c"*64)
    assert not (s.root/"retained/RESTORED.json").exists()
    assert (s.root/"retained/NATIVE_CURRENT_RESTORE_GO.json").exists()


def test_current_GO_and_event_are_separate_from_historical_identity(current_scope,tmp_path,monkeypatch):
    import subprocess
    from tools import private_draft_store_v2 as shared
    s=current_scope
    _,go=r.templates(ROOT)
    go.update(approved=True,registration_sha256=store.sha(store.canonical(s.registration)),source_sha=CURRENT_SOURCE,
        job_id=CURRENT_JOB,workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/fictional-current",
        issued_at_utc=(audit.now()-timedelta(seconds=1)).isoformat(),expires_at_utc=(audit.now()+timedelta(minutes=20)).isoformat())
    event=tmp_path/"event.json"
    body=store.canonical(go);digest=store.sha(body)
    event.write_bytes(store.canonical(dict(repository=dict(full_name=store.REPO),inputs=dict(mode=r.MODE,
        inference_builder_go_json=body.decode(),inference_builder_go_sha256=digest))))
    env=dict(GITHUB_ACTIONS="true",GITHUB_REPOSITORY=store.REPO,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",
        STORE_PERMISSION="write",GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933",GITHUB_SHA=CURRENT_SOURCE,
        GITHUB_RUN_ID=CURRENT_RUN,GITHUB_JOB=CURRENT_JOB,GITHUB_WORKFLOW_REF=go["workflow_ref"],GITHUB_EVENT_PATH=str(event),
        AUDIT_COUNT_RETAINED_GO_SHA256=digest)
    monkeypatch.setattr(shared,"actions_context",lambda env,permission:{"fictional_context_only":True})
    monkeypatch.setattr(subprocess,"check_output",lambda *a,**kw:"")
    assert r.validate_go(go,go["registration_sha256"],env,ROOT)=={"fictional_context_only":True}
    for key,value in (("approved",False),("source_sha",SOURCE),("job_id",effective.READER_JOB),
                      ("remote_writes",1),("extra",True)):
        bad=deepcopy(go);bad[key]=value
        with pytest.raises(store.StoreError):r.validate_go(bad,go["registration_sha256"],env,ROOT)
    changed=json.loads(event.read_bytes());changed["inputs"]["inference_builder_go_sha256"]="f"*64
    event.write_bytes(store.canonical(changed))
    with pytest.raises(store.StoreError,match="DISPATCH_GO"):
        r.validate_go(go,go["registration_sha256"],env,ROOT)
    assert not s.http.requests


def test_metadata_preparation_never_approves_even_a_real_shaped_success(retained_origin,tmp_path,monkeypatch):
    import subprocess
    p=retained_origin
    verification=tmp_path/"verification.json";verification.write_bytes(store.canonical(p["registration"]["origin"]["verification_receipt"]))
    catalog=tmp_path/"catalog.json";catalog.write_bytes(store.canonical(p["registration"]["origin"]["replay_catalog"]))
    handoff=tmp_path/"handoff.json";handoff.write_bytes(store.canonical(p["registration"]["origin"]["handoff"]));handoff.chmod(0o600)
    original_read=store.read_local
    def read(path,cap):
        if str(path).endswith("reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json"):
            return store.canonical(dict(binding=p["service"].runtime,qualification=p["service"].q))
        return original_read(path,cap)
    def git(command,**kwargs):
        name=command[-1].split(":",1)[1]
        raw=p["source_bytes"][name]
        return str(len(raw))+"\n" if command[1]=="cat-file" else raw
    monkeypatch.setattr(subprocess,"check_output",git)
    monkeypatch.setattr(store,"read_local",read)
    registration,go=r.prepare_from_metadata(ROOT,verification,catalog,handoff,991,run_conclusion="failure")
    assert registration["approved"] is go["approved"] is False
    assert registration["origin"]["run_id"]==RUN
    assert registration["origin"]["source_sha"]==SOURCE
    assert registration["origin"]["reader"]["api_job_id"]==778
    assert registration["model_code_sha256"]==r.model_pins(ROOT)
    with pytest.raises(store.StoreError):r.validate_registration(registration)


def test_execute_unapproved_registration_rejects_without_credentials_or_HTTP(tmp_path):
    registration,_=r.templates(ROOT)
    body=store.canonical(registration)
    path=tmp_path/"registration.json";path.write_bytes(body)
    class NoEnvironment:
        def get(self,*unused):raise AssertionError("unexpected credential discovery")
    def no_http(*unused):raise AssertionError("unexpected HTTP")
    output=io.StringIO()
    with redirect_stdout(output):
        assert cli.main(["restore","--execute","--registration",str(path),"--registration-sha256",store.sha(body)],
            environ=NoEnvironment(),transport=no_http)==1
    assert json.loads(output.getvalue())["reason"]=="REGISTERED_RETAINED_SUCCESS_REQUIRED"
