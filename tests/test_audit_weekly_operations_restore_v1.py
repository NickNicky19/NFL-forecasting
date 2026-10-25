"""Wholly fictional protocol/API integration, never genuine release evidence.

Native tests run real discovery, complete retained recovery, typed source/receipt
grants, current client and bootstrap verifiers. The incomplete historical Root
fixture uses an explicit child_context seam. No network or model fitting.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import base64
import gzip
import json
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from nfl_lab import audit_weekly_operations_restore_v1 as recovery,private_draft_store as store

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_actual_network(monkeypatch):
    monkeypatch.setattr(socket.socket,"connect",lambda *_:pytest.fail("REAL_NETWORK_FORBIDDEN"))


def _fictional_archive(base,workflow,policy,source,roles,workflow_ref,*,hour=13):
    """Generate original native bytes under a fictional earlier acquisition clock."""
    from contextlib import ExitStack
    import test_audit_weekly_archive_v1 as old
    import test_audit_weekly_retained_v1 as historical
    import test_owner_private_bootstrap as qualifier
    from nfl_lab import audit_weekly_archive_v1 as archive,gha_private_checkpoint as cp
    from nfl_lab import owner_private_bootstrap as owner
    start=datetime.now(timezone.utc)
    class HistoricalClock(datetime):
        @classmethod
        def now(cls,tz=None):
            value=datetime(2026,10,25,hour,10,tzinfo=timezone.utc)+(datetime.now(timezone.utc)-start)
            return value if tz is not None else value.replace(tzinfo=None)
    with ExitStack() as scope:
        for module in (old,historical,qualifier,store,archive,owner):
            if hasattr(module,"datetime"):scope.enter_context(patch.object(module,"datetime",HistoricalClock))
        for module in (old,historical,qualifier):scope.enter_context(patch.object(module,"SOURCE",source))
        for module in (old,historical):scope.enter_context(patch.object(module,"ROLES",roles))
        p=old.capture.__wrapped__(base)
        # The controller's readiness contract requires all eleven categories.
        # Construct that actual fictional selected body BEFORE the first
        # append, rather than relabelling a one-category receipt as complete.
        selected_path=p.root/"selected.jsonl.gz"
        original=json.loads(gzip.decompress(selected_path.read_bytes()))
        rows=[dict(original,category=target,offered_id=store.sha(store.canonical([target,"fictional-player"])))
            for target in sorted(cp.TARGETS)]
        raw=gzip.compress(b"".join(store.canonical(row)+b"\n" for row in rows),mtime=0)
        with p.storage.capture_writes([p.root]):
            p.storage.write_bytes(selected_path,raw,replace=True)
        selected=cp.binding(selected_path)
        def replace_json(name,value):
            path=p.root/name
            with p.storage.capture_writes([p.root]):
                p.storage.write_bytes(path,store.canonical(value),replace=True)
            return cp.binding(path)
        completion=json.loads((p.root/"selected.jsonl.completion.json").read_bytes())
        completion.update(rows=len(rows),binding=selected)
        completion_ref=replace_json("selected.jsonl.completion.json",completion)
        terminal=json.loads((p.root/"FINISHED.json").read_bytes());terminal["selected"]=completion
        terminal_ref=replace_json("FINISHED.json",terminal)
        export=json.loads((p.root/"EXPORT_INPUTS.json").read_bytes())
        export.update(terminal=terminal_ref,selected=selected,completion=completion_ref)
        replace_json("EXPORT_INPUTS.json",export)
        public_body=store.canonical(dict(schema_version="FICTIONAL_DERIVED_CATEGORY_ROWS",rows=rows))
        history=historical.History(p)
        history.codes[".github/workflows/lab.yml"]=workflow
        original_transport=history.transport
        def historical_transport(req,timeout):
            response=original_transport(req,timeout)
            if req.full_url==store.API+"/actions/runs/"+old.RUN:
                from test_private_draft_store_v2 import Response
                body=json.loads(response.body);body["head_branch"]=workflow_ref.split("@refs/heads/",1)[1]
                return Response(body)
            return response
        history.transport=historical_transport
        def factory(journal,role):
            journal.mkdir(mode=0o700)
            class Factory:
                def __init__(self):self.clients=[]
                def __call__(self,operation):
                    job=dict(execution_lane="github_actions",workflow_ref=workflow_ref,workflow_sha=source,
                        job_id=roles[role],permission="write",event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
                    client=archive.Client("ghs_FICTIONAL",old.RUN,journal=journal,source_sha=source,transport=history.transport,
                        job=job,operation=operation,qualification=history.old.q,readonly=role=="consume",process=store.sha(("FICTIONAL-"+role).encode()))
                    client.bind(history.old.binding);self.clients.append(client);return client
            return Factory()
        history.old.factory=factory
        r0,completion=historical.full_r0(p)
        snapshot=archive.collect(p.root,p.context,storage=p.storage,output=base/"collection",r0=r0)
        assert "r0/control_completion.json" in {f["logical_path"]for f in snapshot["files"]}
        policy_ref=p.body("context/public-policy.json",policy)
        item=cp.file_item(policy_ref,"context/public_policy.json","control")
        snapshot["files"].append(item);snapshot["files"].sort(key=lambda f:f["logical_path"])
        census=snapshot["census"];census["physical_origins"][item["logical_path"]]=policy_ref
        census["logical_files"]=len(snapshot["files"]);census["logical_bytes"]=sum(f["bytes"]for f in snapshot["files"])
        census["context_roles"].append("public_policy");census["context_roles"].sort()
        history.begin("produce");handoff,_,_=old.produce(p,history.old,snapshot=snapshot);history.end()
        history.begin("restore")
        archive.restore(handoff,factory(base/"old-reader-journal","restore"),history.old.package,
            storage=p.storage,output=base/"old-reader",root_go_sha256="d"*64,pending_census=history.old.census)
        history.end();reader=cp.strict_json((base/"old-reader/READER_HANDOFF.json").read_bytes())
        history.begin("consume");verified=HistoricalClock.now(timezone.utc)
        archive.consume(reader,factory(base/"old-export-journal","consume"),history.old.package,
            storage=p.storage,output=base/"old-export",root_go_sha256="d"*64,pending_census=history.old.census)
        created=HistoricalClock.now(timezone.utc);history.end();history.finished=True
        api={}
        for run_id in (old.RUN,history.old.qrun):
            for tail in ("","/jobs?per_page=100&page=1"):
                url=store.API+"/actions/runs/"+run_id+tail
                value=json.loads(history.transport(SimpleNamespace(full_url=url),20).body)
                if run_id==old.RUN and not tail:value["head_branch"]=workflow_ref.split("@refs/heads/",1)[1]
                api[url]=value
        from nfl_lab import audit_weekly_retained_v1 as retained,audit_weekly_discovery_v1 as discovery
        for name,body in history.codes.items():
            import hashlib
            blob_sha=hashlib.sha1(b"blob "+str(len(body)).encode()+b"\0"+body).hexdigest()
            api[retained.source_url(source,name)]=dict(type="file",path=name,encoding="base64",size=len(body),
                sha=blob_sha,content=base64.b64encode(body).decode())
        files={f["logical_path"]:f for f in snapshot["files"]}
        receipt=dict(schema_version=discovery.delivery.VERSION+"-public-receipt",source_sha=source,run_id=old.RUN,
            root_go_sha256="d"*64,policy_sha256=store.sha(policy),policy_registered_at_utc=f"2026-10-25T{hour-2:02d}:00:00Z",
            workflow_sha256=store.sha(workflow),recipe_registration_sha256="1"*64,rights_authority_sha256="2"*64,
            r0_identity_sha256="3"*64,origin_choice_sha256="4"*64,feed_sha256=store.sha(public_body),
            feed_bytes=len(public_body),rows=len(rows),categories=sorted({r["category"] for r in rows}),
            jobs={role:dict(job_id=name,api_job_id=777+i)for i,(role,name)in enumerate(roles.items())},
            created_at=created.isoformat(),verified_at=verified.isoformat(),fits=0,raw_or_models_public=False,
            archive_index_sha256=handoff["index_descriptor"]["entry"]["payload"]["sha256"],archive_files_sha256=handoff["files_sha256"],
            reader_witness_sha256=reader["witness_descriptor"]["entry"]["payload"]["sha256"],epoch_sha256=files["context/epoch.json"]["sha256"],
            choice_sha256=files["prepared/choice.json"]["sha256"])
    server=history.old.server
    assets=[]
    for asset in server.assets:
        item={k:v for k,v in asset.items()if k!="body"};item["body_base64"]=base64.b64encode(asset["body"]).decode();assets.append(item)
    return dict(package=history.old.package,census=history.old.census,receipt=receipt,reader=reader,
        historical={name:store.sha(body)for name,body in history.codes.items()},api=api,assets=assets,
        tag=server.tag,original_files={f["logical_path"]:dict(bytes=f["bytes"],sha256=f["sha256"])for f in snapshot["files"]})


def _register_fixture_readiness(x,old,fixture):
    """Mint fictional owner-registration bytes around the exact prior archive."""
    from nfl_lab import audit_weekly_controller_v1 as c,audit_weekly_template_v1 as t
    value=old["receipt"];raw=store.canonical(value)
    x.p["readiness"].update(source_sha=value["source_sha"],run_id=value["run_id"],jobs=value["jobs"],
        workflow_sha256=value["workflow_sha256"],receipt_sha256=store.sha(gzip.compress(raw,mtime=0)),
        receipt_body_sha256=store.sha(raw),receipt_bindings={k:value[k]for k in c.RECEIPT_HASH_KEYS})
    x.original_receipt=raw
    x.api.data.update(deepcopy(old["api"]))
    x.api.data[c.contents_url(c.receipt_path(x.p),"lab-state")]=fixture.original.content(c.receipt_path(x.p),gzip.compress(raw,mtime=0))
    document=deepcopy(x.prepared.document);document["readiness"]=deepcopy(x.p["readiness"])
    x.prepared=t.prepare(document)
    desc=x.template_seal["descriptor"];entry=desc["entry"]
    entry["payload"].update(bytes=len(x.prepared.body),sha256=store.sha(x.prepared.body))
    entry["payload_name"]="blob-"+entry["payload"]["sha256"]+".bin"
    desc.update(manifest_sha256=store.sha(store.canonical(entry)),manifest_bytes=len(store.canonical(entry)))
    x.template_seal.update(template_sha256=store.sha(x.prepared.plain),template_bytes=len(x.prepared.plain))
    summary=x.native["template_descriptor"]
    summary.update(template_sha256=x.template_seal["template_sha256"],template_bytes=x.template_seal["template_bytes"],
        private_descriptor_sha256=store.sha(store.canonical(desc)))
    for role in ("writer","reader"):x.native[role].update({k:v for k,v in summary.items()if k!="schema_version"})
    writer={key:deepcopy(x.template_seal[key])for key in t.HANDOFF_KEYS};writer["schema_version"]=t.VERSION+"-appended"
    x.native["writer"]["receipt_sha256"]=store.sha(store.canonical(writer))
    x.reg=store.canonical(x.p);x.seal=store.sha(x.reg);x.native["registration_sha256"]=x.seal
    x.go["effective_epoch"]["controller_context"]["registration_sha256"]=x.seal
    x.claim["registration_sha256"]=x.seal
    x.publish_locator()


@pytest.fixture
def operational_case(tmp_path,monkeypatch,request):
    """Reuse the frozen real typed bootstrap/current-client guard fixture."""
    import test_audit_weekly_operations_worker_v1 as fixture
    (tmp_path/"bootstrap").mkdir()
    bootstrap=fixture.system.__wrapped__(tmp_path/"bootstrap")
    locator=fixture.locator_system.__wrapped__(bootstrap)
    q=fixture.guard_case.__wrapped__(locator,tmp_path/"live",monkeypatch)
    x=q.x;mode=getattr(request,"param","bot-operational")
    if mode=="bot-operational":
        roles={k:x.p["producer"]["jobs"][k]for k in ("produce","restore","consume")}
        old=_fictional_archive(tmp_path/"old",x.workflow,x.static_policy,x.go["source_sha"],roles,x.go["workflow_ref"])
    else:
        spec=x.p["readiness"];roles={k:v["job_id"]for k,v in spec["jobs"].items()}
        ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/"+spec["branch"]
        old=_fictional_archive(tmp_path/"old",fixture.original.wf(),store.canonical(dict(fictional_old_policy=True)),
            spec["source_sha"],roles,ref,hour=10)
        _register_fixture_readiness(x,old,fixture)
        if mode=="owner-readiness":
            from nfl_lab import audit_weekly_controller_v1 as c
            x.go["effective_epoch"]["controller_context"]=None
            q.env.update(GITHUB_ACTOR=c.OWNER["login"],GITHUB_ACTOR_ID=str(c.OWNER["id"]))
            x.api.data[c.run_url("300")].update(actor=deepcopy(c.OWNER),triggering_actor=deepcopy(c.OWNER))
    q.request.clear();base=tmp_path/"live/producer"
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab import gha_private_checkpoint as cp
    storage=OperationalStorage(base/"cache",ROOT/"config/operational-source-policy-v2.json",state=base/"state")
    storage.register_root(base)
    encoded=gzip.compress(store.canonical(old["receipt"]),mtime=0)
    storage.write_bytes(base/"inputs/receipt.json.gz",encoded)
    q.request.update(schema_version=recovery.VERSION+"-request",phase=recovery.PHASE,code_pins=x.go["code_pins"],
        limits=dict(recovery.LIMITS),cache=str(base/"cache"),state_root=str(base/"state"),output=str(base/recovery.PHASE),
        inputs=dict(receipt=cp.binding(base/"inputs/receipt.json.gz"),historical_source_sha256=old["historical"]))
    x.go.update(qualified_runtime=old["package"],pending_census=old["census"])
    x.go["effective_epoch"]["previous_capture"]=dict(feed_sha256=old["receipt"]["feed_sha256"],receipt_sha256=store.sha(encoded))
    x.bind_root();x.claim.update(root_go_sha256=store.sha(x.raw))
    from nfl_lab import audit_weekly_controller_v1 as controller
    x.api.data[controller.contents_url(x.claim_path,fixture.original.D)]=fixture.original.content(x.claim_path,store.canonical(x.claim))
    x.api.data[controller.API+"/commits/"+fixture.original.D]["files"][0]["sha"]=controller.blob_sha(store.canonical(x.claim))
    q.native.update(phase=recovery.PHASE,owner_root_go_sha256=store.sha(x.raw),request_sha256=store.sha(store.canonical(q.request)))
    q.env.update(AUDIT_WEEKLY_ROOT_GO_JSON=x.raw.decode(),AUDIT_WEEKLY_ROOT_GO_SHA256=store.sha(x.raw),
        AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON=store.canonical(q.native).decode(),AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256=store.sha(store.canonical(q.native)))
    q.args.phase=recovery.PHASE;q.args.request_sha256=q.native["request_sha256"]
    api=deepcopy(old["api"]);api.update(deepcopy(x.api.data))
    seed=dict(old=old,request=q.request,native=q.native,env=q.env,go=x.go,mode=mode,
        api=api,event_base64=base64.b64encode(x.event).decode(),child_source=str(x.child_source))
    return SimpleNamespace(q=q,old=old,seed=seed,storage=storage)


def _native(seed,failure=None):
    """Native positive body + real typed auth, only raw fictional transports."""
    from nfl_lab import audit_weekly_operations_worker_v1 as worker,audit_weekly_operations_authority_v1 as authority
    from nfl_lab import audit_weekly_hosted_v1 as hosted,audit_weekly_controller_v1 as controller
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap,gha_private_checkpoint as cp
    from test_private_draft_store_v2 import Server,Response
    seed=deepcopy(seed);request=seed["request"];native=seed["native"];env=seed["env"];go=seed["go"];api=seed["api"]
    server=Server();server.tag=seed["old"]["tag"]
    server.assets=[dict(a,body=base64.b64decode(a["body_base64"]))for a in seed["old"]["assets"]]
    for asset in server.assets:asset.pop("body_base64")
    calls=[];grants=[];clients=[]
    def metadata(url,cap):
        assert url in api and bootstrap.fixed_route(url)
        body=store.canonical(api[url]);assert len(body)<=cap
        return controller.Reply(200,body)
    def transport(req,timeout):
        assert req.method=="GET" and req.data is None
        calls.append((req.full_url,req.get_header("Accept")))
        return Response(api[req.full_url])if req.full_url in api else server(req,timeout)
    source=Path(seed["child_source"])
    real_current=authority.current
    def current(e,body,_source):
        return real_current(e,body,source,metadata_get=metadata,event_bytes=base64.b64decode(seed["event_base64"]),
            clock=lambda:datetime(2026,10,25,13,38,tzinfo=timezone.utc),read_head=lambda _:go["source_sha"])
    def validate(body,*,now):assert body==go;return body  # explicit incomplete-Root fixture boundary
    def child(args,e,phase,*,operations_proof):
        authority._verify(operations_proof,e,store.canonical(go))
        assert phase==recovery.PHASE and args.request_sha256==native["request_sha256"]==store.sha(store.canonical(request))
        assert request["output"]==str(Path(request["cache"]).parent/hosted.OPERATIONS_PHASES[phase][1])
        assert request["code_pins"]==go["code_pins"] and native["owner_root_go_sha256"]==store.sha(store.canonical(go))
        job=dict(execution_lane="github_actions",workflow_ref=e["GITHUB_WORKFLOW_REF"],workflow_sha=e["GITHUB_SHA"],
            job_id=e["GITHUB_JOB"],permission="write",event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
        return request,native,job,go
    from nfl_lab import audit_weekly_retained_v1 as retained,audit_weekly_discovery_v1 as discovery,state
    real_grant=retained._grant_authenticate
    def record_grant(callback,kind,document,at):
        grants.append((kind,deepcopy(document)))
        return real_grant(callback,kind,document,at)
    real_client=retained.ReadClient;real_init=real_client.__init__
    def init(c,*a,**kw):real_init(c,*a,**kw);clients.append(c)
    # These are fixed fictional October25 13:38 jobs. Keep every protocol
    # clock in that same scenario while native wall/CPU/resource timers remain
    # real. Otherwise the fixture silently expires as the real audit continues.
    from contextlib import ExitStack
    from nfl_lab import audit_weekly_archive_v1 as archive,owner_private_bootstrap as owner
    from nfl_lab import weekly_durable_acceptance as acceptance
    actual_start=datetime.now(timezone.utc)
    class ScenarioClock(datetime):
        @classmethod
        def now(cls,tz=None):
            value=cls(2026,10,25,13,38,tzinfo=timezone.utc)+(datetime.now(timezone.utc)-actual_start)
            return value if tz is not None else value.replace(tzinfo=None)
    clock_scope=ExitStack()
    for module in (store,cp,archive,retained,discovery,state,owner,acceptance,recovery):
        if hasattr(module,"datetime"):clock_scope.enter_context(patch.object(module,"datetime",ScenarioClock))
    with clock_scope,patch.object(authority,"current",current),patch.object(hosted,"validate_root",validate),\
         patch.object(hosted,"child_context",child),patch.object(hosted,"pins",lambda:deepcopy(go["code_pins"])),\
         patch.object(retained,"_grant_authenticate",record_grant),patch.object(real_client,"__init__",init):
        context=worker.authenticate_child(SimpleNamespace(phase=recovery.PHASE,request="fictional-owned-control",request_sha256=native["request_sha256"]),
            env,phase=recovery.PHASE,transport=transport)
        assert context.verify()is context
        try:
            result=recovery.restore(context,transport=transport)
        except store.StoreError as error:
            if failure!="bot-readiness":raise
            # Initial Nick readiness permits the manual owner smoke. It does
            # not give a BOT the later sealed operational-policy grant. The
            # first BOT must follow the successful owner operational capture.
            assert seed["mode"]=="bot-readiness"
            assert str(error)=="EXACT_GRANTED_POLICY_AND_REGISTERED_REQUEST"
            assert not (Path(request["output"])/"restored").exists()
            return dict(state="PASS_UNSUPPORTED_BOT_READINESS_REJECTED",full_forecast_group_restore_started=False,
                fits=0,model_decodes=0,outcome_decodes=0,remote_writes=0,genuine_Actions_evidence=False)
    manifest=cp.strict_json(Path(result["retained_result"]["path"]).read_bytes())
    assert result["state"]=="PRIVATE_PRIOR_CAPTURE_RECOVERED_FOR_RECURRING"
    assert manifest["original_reader_handoff"]==seed["old"]["reader"]
    assert result["current_run_id"]!=result["original_run_id"]
    assert result["current_source_sha"]==env["GITHUB_SHA"] and result["original_source_sha"]==seed["old"]["receipt"]["source_sha"]
    assert manifest["current"]["process_identity"]==store.process_identity()
    assert manifest["model_replay_performed"]is manifest["public_export_authorized"]is False
    for name,ref in manifest["aliases"].items():
        body=Path(ref["path"]).read_bytes();assert dict(bytes=len(body),sha256=store.sha(body))==seed["old"]["original_files"][name]
    assert len([name for name in manifest["aliases"]if name.startswith("runtime/candidates/")and name.endswith(".jsonl.gz")])==18
    assert len({str(c.journal)for c in clients})==1 and sum(c.calls for c in clients)<=640
    assert all(c.calls<=40 for c in clients)and len(clients)<=17
    worker.native_envelope()
    return dict(state="PASS_FICTIONAL_NATIVE_DISCOVERY_AND_FULL_RECOVERY",calls=len(calls),clients=len(clients),files=result["files"],
        grant_kinds=[x[0]for x in grants],max_RSS_KiB=__import__("resource").getrusage(__import__("resource").RUSAGE_SELF).ru_maxrss,
        fits=result["fits"],model_decodes=result["model_decodes"],outcome_decodes=result["outcome_decodes"],remote_writes=result["remote_writes"],
        genuine_Actions_evidence=False,public_release=False)


@pytest.mark.parametrize("operational_case",["bot-operational","owner-readiness","bot-readiness"],indirect=True)
def test_native_discovery_recovery_enforces_source_and_actor_contract(operational_case,tmp_path):
    seed=tmp_path/"fictional-native-seed.json";seed.write_bytes(store.canonical(operational_case.seed))
    script='''
import sys,json,socket
from pathlib import Path
from tools.private_draft_store_v2 import limits
limits()
sys.path.insert(0,str(Path.cwd()/'tests'))
import test_audit_weekly_operations_restore_v1 as probe
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('REAL_NETWORK_FORBIDDEN'))
seed=json.loads(Path(sys.argv[1]).read_bytes())
result=probe._native(seed,failure='bot-readiness' if seed['mode']=='bot-readiness' else None)
print(json.dumps(result,sort_keys=True))
'''
    profile=json.loads((ROOT/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    result=subprocess.run([sys.executable,"-B","-c",script,str(seed)],cwd=ROOT,
        env={"PYTHONDONTWRITEBYTECODE":"1",**profile},capture_output=True,text=True,timeout=185)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout)
    if operational_case.seed["mode"]=="bot-readiness":
        assert value["state"]=="PASS_UNSUPPORTED_BOT_READINESS_REJECTED"
        assert value["full_forecast_group_restore_started"] is False
        assert value["genuine_Actions_evidence"] is False
        return
    assert value["state"]=="PASS_FICTIONAL_NATIVE_DISCOVERY_AND_FULL_RECOVERY"and value["calls"]<=640
    assert value["fits"]==value["model_decodes"]==value["outcome_decodes"]==value["remote_writes"]==0
    assert value["genuine_Actions_evidence"]is value["public_release"]is False
    expected=["BIND_SEALED_DISCOVERY_SOURCE","LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET"]
    if operational_case.seed["mode"]!="owner-readiness":
        expected += ["BIND_SEALED_HISTORICAL_SOURCE","LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET"]
    assert value["grant_kinds"]==expected


def test_restore_preparation_has_no_runtime_or_credential_dependency():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,"-I","-B",str(root/"tools/audit_weekly_operations_restore_v1.py"),
        "operations-retained"],env={},capture_output=True,text=True,timeout=10)
    assert result.returncode==2
    assert json.loads(result.stdout)==dict(state="RECURRING_RESTORE_PREPARATION_ONLY_NO_IO",remote_writes=0,fits=0)
    assert not result.stderr


@pytest.mark.parametrize("saved",[None,True,{}, {"actual_actions_api_authenticated":True},
    {"schema_version":"audit-weekly-controller-v1-current-child-proof","source_sha":"a"*40}])
def test_saved_documents_never_authorize_private_recovery(saved):
    with pytest.raises(store.StoreError,match="LIVE_RECURRING_RESTORE_CONTEXT_REQUIRED"):
        recovery.restore(saved)
