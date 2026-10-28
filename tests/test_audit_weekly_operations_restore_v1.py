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
import os
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


def _fictional_archive(base,workflow,policy,source,roles,workflow_ref,*,hour=13,closed_census=False,history_seed=None):
    """Generate original native bytes under a fictional earlier acquisition clock."""
    from contextlib import ExitStack
    import test_audit_weekly_archive_v1 as old
    import test_audit_weekly_retained_v1 as historical
    import test_owner_private_bootstrap as qualifier
    from nfl_lab import audit_weekly_archive_v1 as archive,gha_private_checkpoint as cp
    from nfl_lab import owner_private_bootstrap as owner
    start=datetime.now(timezone.utc);phase_start=[start];phase_seconds=[2]
    root_sha="d"*64 if history_seed is None else store.sha(store.canonical(history_seed["original_root"]))
    began=None if history_seed is None else store.utc(history_seed["original_root"]["issued_at_utc"])
    class HistoricalClock(datetime):
        @classmethod
        def now(cls,tz=None):
            value=(datetime(2026,10,25,hour,10,tzinfo=timezone.utc)+(datetime.now(timezone.utc)-start) if began is None else
                began+timedelta(seconds=phase_seconds[0])+(datetime.now(timezone.utc)-phase_start[0]))
            return value if tz is not None else value.replace(tzinfo=None)
    with ExitStack() as scope:
        for module in (old,historical,qualifier,store,archive,owner):
            if hasattr(module,"datetime"):scope.enter_context(patch.object(module,"datetime",HistoricalClock))
        for module in (old,historical,qualifier):scope.enter_context(patch.object(module,"SOURCE",source))
        for module in (old,historical):scope.enter_context(patch.object(module,"ROLES",roles))
        if history_seed is not None:
            for module in (old,historical):scope.enter_context(patch.object(module,"RUN",history_seed["old_run"]))
            p=old.capture_case(base,epoch_document=history_seed["docs"]["epoch"],choice_document=history_seed["choice"])
            for name,doc in history_seed["docs"].items():
                raw=doc.encode() if name=="original_choice" else store.canonical(doc)
                p.context[name]=p.body("history-context/"+name+".json",raw)
        else:p=old.capture.__wrapped__(base)
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
        if history_seed is not None:
            history.old.package=deepcopy(history_seed["package"]);history.old.q=history.old.package["qualification"]
            history.old.binding=history.old.package["binding"];history.old.qrun=history.old.q["run_id"]
            history.old.census=deepcopy(history_seed["census"])
            server=history.old.server;server.tag=history_seed["tag"]
            server.assets=[dict(a,body=base64.b64decode(a["body"])) for a in history_seed["assets"]]
            history.old.started=began+timedelta(seconds=1)
        if closed_census:
            history.old.census.update(schema_version="audit-private-rotation-v1-pending-census",complete=True,
                as_of_utc=history.old.q["before_proof"]["started_at_utc"],
                owner_evidence_sha256=store.sha(b"FICTIONAL original COUNT7 reservation evidence"))
            history.old.package["quota_reservation"]["pending_census_sha256"]=store.sha(store.canonical(history.old.census))
        history.codes[".github/workflows/lab.yml"]=workflow
        original_transport=history.transport
        def historical_transport(req,timeout):
            response=original_transport(req,timeout)
            if req.full_url==store.API+"/actions/runs/"+old.RUN:
                from test_private_draft_store_v2 import Response
                body=json.loads(response.body);body["head_branch"]=workflow_ref.split("@refs/heads/",1)[1]
                return Response(body)
            if history_seed is not None and req.full_url==store.API+"/actions/runs/"+old.RUN+"/jobs?per_page=100&page=1":
                from test_private_draft_store_v2 import Response
                body=json.loads(response.body)
                for i,job in enumerate(body["jobs"]):job["id"]=888+i
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
        history.begin("produce")
        handoff=archive.produce(snapshot,factory(base/"producer-journal","produce"),history.old.package,
            storage=p.storage,output=base/"producer",root_go_sha256=root_sha,jobs=roles,pending_census=history.old.census)
        history.old.writer_completed=HistoricalClock.now(timezone.utc);history.end()
        if history_seed is not None:phase_seconds[0]=12;phase_start[0]=datetime.now(timezone.utc)
        history.begin("restore")
        archive.restore(handoff,factory(base/"old-reader-journal","restore"),history.old.package,
            storage=p.storage,output=base/"old-reader",root_go_sha256=root_sha,pending_census=history.old.census)
        history.end();reader=cp.strict_json((base/"old-reader/READER_HANDOFF.json").read_bytes())
        if history_seed is not None:phase_seconds[0]=72;phase_start[0]=datetime.now(timezone.utc)
        history.begin("consume");verified=HistoricalClock.now(timezone.utc)
        archive.consume(reader,factory(base/"old-export-journal","consume"),history.old.package,
            storage=p.storage,output=base/"old-export",root_go_sha256=root_sha,pending_census=history.old.census)
        created=HistoricalClock.now(timezone.utc);history.end();history.finished=True
        api={}
        for run_id in (old.RUN,history.old.qrun):
            for tail in ("","/jobs?per_page=100&page=1"):
                url=store.API+"/actions/runs/"+run_id+tail
                value=json.loads(history.transport(SimpleNamespace(full_url=url),20).body)
                if run_id==old.RUN and not tail:value["head_branch"]=workflow_ref.split("@refs/heads/",1)[1]
                api[url]=value
        if history_seed is not None:
            jobs=api[store.API+"/actions/runs/"+old.RUN+"/jobs?per_page=100&page=1"]["jobs"]
            for job,(started,completed) in zip(jobs,history_seed["job_times"]):
                job.update(started_at=started,completed_at=completed)
            verified=store.utc(history_seed["locator"]["cohort"]["verified_at"])
            created=store.utc(history_seed["locator"]["cohort"]["created_at"])
        from nfl_lab import audit_weekly_retained_v1 as retained,audit_weekly_discovery_v1 as discovery
        for name,body in history.codes.items():
            import hashlib
            blob_sha=hashlib.sha1(b"blob "+str(len(body)).encode()+b"\0"+body).hexdigest()
            api[retained.source_url(source,name)]=dict(type="file",path=name,encoding="base64",size=len(body),
                sha=blob_sha,content=base64.b64encode(body).decode())
        files={f["logical_path"]:f for f in snapshot["files"]}
        receipt=dict(schema_version=discovery.delivery.VERSION+"-public-receipt",source_sha=source,run_id=old.RUN,
            root_go_sha256=root_sha,policy_sha256=store.sha(policy),policy_registered_at_utc=f"2026-10-25T{hour-2:02d}:00:00Z",
            workflow_sha256=store.sha(workflow),recipe_registration_sha256="1"*64,rights_authority_sha256="2"*64,
            r0_identity_sha256="3"*64,origin_choice_sha256="4"*64,feed_sha256=store.sha(public_body),
            feed_bytes=len(public_body),rows=len(rows),categories=sorted({r["category"] for r in rows}),
            jobs={role:dict(job_id=name,api_job_id=(777 if history_seed is None else 888)+i)for i,(role,name)in enumerate(roles.items())},
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
    if mode in {"bot-operational","dual-runtime","source-history"}:
        if mode=="dual-runtime":
            # Establish the fictional policy before COUNT7 and the original
            # template registration, rather than backdating retained bytes.
            x.static_policy=store.canonical(dict(source_sha=x.go["source_sha"],
                registered_at_utc="2026-10-25T08:00:00Z",fictional_static_contract=True))
            x.native["static_public_policy_sha256"]=store.sha(x.static_policy)
            x.go["publication_registration"]["policy_sha256"]=store.sha(x.static_policy)
        roles={k:x.p["producer"]["jobs"][k]for k in ("produce","restore","consume")}
        transition=mode=="source-history"
        old=_fictional_archive(tmp_path/"old",x.workflow,
            store.canonical(dict(fictional_original_policy=True)) if transition else x.static_policy,
            "8"*40 if transition else x.go["source_sha"],roles,x.go["workflow_ref"],
            hour=10 if mode in {"dual-runtime","source-history"} else 13,closed_census=mode in {"dual-runtime","source-history"})
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


def _dual_runtime_seed(case,damage=None,*,root_override=None):
    """Seal invented V3 metadata around an actually appended COUNT7 archive.

    Malformed package/census cases intentionally enter the existing incomplete
    Root seam; selectors must still fail closed before any archive GET.
    """
    import test_audit_weekly_operations_worker_v1 as fixture
    from test_audit_weekly_template_v1 import dual_runtime_root
    from nfl_lab import audit_weekly_template_v1 as template,audit_weekly_controller_v1 as controller
    from nfl_lab import audit_weekly_operations_v1 as operations
    q=case.q;x=q.x;old=case.old
    root=deepcopy(x.prepared.document["root_template"]);root.update(deepcopy(x.go))
    if root_override is None:
        root=dual_runtime_root(root,old["package"],old["census"],root["effective_epoch"]["previous_capture"])
        root["approved"]=True
        root["effective_epoch"].update(schema_version=operations.CONTEXT_V4,previous_checkpoint=None,
            plan=dict(kind="FUTURE_CAPABLE",season=2026,week=7,deadline_utc="2026-10-25T14:00:00Z",
                calendar_sha256=store.sha(b"FICTIONAL calendar"),game_cutoffs={"fictional-future":"2026-10-25T14:00:00Z"}))
    else:root=deepcopy(root_override)
    if damage in {"feed-anchor","receipt-anchor"}:
        key="feed_sha256" if damage=="feed-anchor" else "receipt_sha256"
        root["prior_capture_qualified_runtime"]["anchor"][key]="0"*64
    document=deepcopy(x.prepared.document)
    document["schema_version"]=template.STATIC_V4 if root["schema_version"]==template.ROOT_V4 else template.STATIC_V3
    document.update(source_sha=root["source_sha"],code_pins=deepcopy(root["code_pins"]),readiness=deepcopy(x.p["readiness"]))
    document["root_template"]=deepcopy(root);document["root_template"]["approved"]=False
    for key in template.DYNAMIC_FIELDS-{"approved"}:document["root_template"][key]=None
    x.prepared=template.prepare(document)
    # This remains fictional registration metadata, not a native qualification
    # of the new runtime. Its actual template codec and bootstrap seals run.
    current=root["qualified_runtime"];seal=x.template_seal;entry=seal["descriptor"]["entry"]
    seal["binding"]=deepcopy(current["binding"]);entry["binding_sha256"]=template.digest(current["binding"])
    entry["payload"].update(bytes=len(x.prepared.body),sha256=store.sha(x.prepared.body))
    entry["payload_name"]="blob-"+entry["payload"]["sha256"]+".bin"
    seal["descriptor"].update(manifest_sha256=template.digest(entry),manifest_bytes=len(store.canonical(entry)))
    seal.update(template_sha256=store.sha(x.prepared.plain),template_bytes=len(x.prepared.plain))
    summary=x.native["template_descriptor"]
    summary.update(template_sha256=seal["template_sha256"],template_bytes=seal["template_bytes"],
        private_descriptor_sha256=template.digest(seal["descriptor"]),storage_binding_sha256=template.digest(current["binding"]))
    for role in ("writer","reader"):x.native[role].update({k:v for k,v in summary.items()if k!="schema_version"})
    writer={key:deepcopy(seal[key])for key in template.HANDOFF_KEYS};writer["schema_version"]=template.VERSION+"-appended"
    x.native["writer"]["receipt_sha256"]=template.digest(writer)
    x.locators.update(template_seal=deepcopy(seal),qualified_runtime_package=deepcopy(current))
    x.publish_locator()
    if damage=="census":root["prior_capture_qualified_runtime"]["pending_census"]["owner_evidence_sha256"]="0"*64
    if damage=="package":root["prior_capture_qualified_runtime"]["qualified_runtime"]["run_id"]=current["run_id"]
    x.go.clear();x.go.update(root);x.bind_root()
    x.claim["root_go_sha256"]=store.sha(x.raw)
    x.api.data[controller.contents_url(x.claim_path,fixture.original.D)]=fixture.original.content(x.claim_path,store.canonical(x.claim))
    x.api.data[controller.API+"/commits/"+fixture.original.D]["files"][0]["sha"]=controller.blob_sha(store.canonical(x.claim))
    q.native["owner_root_go_sha256"]=store.sha(x.raw)
    q.env.update(AUDIT_WEEKLY_ROOT_GO_JSON=x.raw.decode(),AUDIT_WEEKLY_ROOT_GO_SHA256=store.sha(x.raw),
        AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON=store.canonical(q.native).decode(),AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256=template.digest(q.native))
    api=deepcopy(old["api"]);api.update(deepcopy(x.api.data))
    return dict(case.seed,go=deepcopy(root),native=deepcopy(q.native),env=deepcopy(q.env),api=api,
        event_base64=base64.b64encode(x.event).decode(),static_template_base64=base64.b64encode(x.prepared.body).decode(),
        dual_runtime=True,damage=damage,parent_pid=os.getpid())


def _source_history_seed(case,*,actor="bot"):
    """Actual entry with a distinct non-readiness predecessor and sealed V4.

    Fictional Root/template/API IDs only. No saved JSON substitutes for the
    current typed proof or its native registration seal.
    """
    from nfl_lab import audit_weekly_grade_history_v1 as history,audit_weekly_hosted_v1 as hosted
    from nfl_lab import audit_weekly_template_v1 as template,audit_weekly_controller_v1 as controller
    from nfl_lab import audit_weekly_retained_v1 as retained
    q=case.q;x=q.x;old=case.old
    # Authenticate all 128 current literal fixture pins, including unchanged
    # old archive/checkpoint kernels. Only declared orchestration pins differ.
    bodies={p:(x.child_source/p).read_bytes() if (x.child_source/p).exists() else ("FICTIONAL "+p).encode()
        for p in hosted.PINS}
    for path in retained.HISTORICAL_FILES:
        bodies[path]=base64.b64decode(old["api"][retained.source_url(old["receipt"]["source_sha"],path)]["content"])
    assert set(x.p["producer"]["code_pins"])<=set(bodies)
    for role,source in (("parent",x.parent_source),("producer",x.child_source)):
        names=set(bodies) if role=="producer" else set(x.p[role]["code_pins"])
        for name in names:
            body=bodies.get(name,(source/name).read_bytes() if (source/name).exists() else b"FICTIONAL parent")
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
            x.p[role]["code_pins"][name]=store.sha(body)
    root=deepcopy(x.prepared.document["root_template"]);root.update(deepcopy(x.go))
    root.update(schema_version=history.ROOT_V4,approved=True,code_pins=deepcopy(x.p["producer"]["code_pins"]))
    root["effective_epoch"].update(schema_version=history.CONTEXT_V5,
        pending_post_recovery=dict(schema_version=template.PENDING_RECOVERY,handoffs=[],pending_reservations=[]),
        previous_checkpoint=dict(schema_version=history.LOCATOR_REF,
            path="20261025T101100.000000Z--"+old["receipt"]["run_id"]+"--"+"a"*64+".json.gz",sha256="b"*64),
        plan=dict(kind="FUTURE_CAPABLE",season=2026,week=7,deadline_utc="2026-10-25T14:00:00Z",
            calendar_sha256=store.sha(b"FICTIONAL calendar"),game_cutoffs={"fictional-future":"2026-10-25T14:00:00Z"}))
    from test_audit_weekly_controller_bootstrap_v1 import fictional_runtime_metadata
    root["qualified_runtime"]=fictional_runtime_metadata(old["package"],old["census"],number=6)
    root["pending_census"]=deepcopy(old["census"])
    root["prior_capture_qualified_runtime"]=dict(schema_version=template.PRIOR_RUNTIME,purpose="PRIOR_CAPTURE_QUALIFIED_RUNTIME",
        anchor=deepcopy(root["effective_epoch"]["previous_capture"]),qualified_runtime=deepcopy(old["package"]),
        pending_census=deepcopy(old["census"]),root_static_sha256="d"*64)
    original_pins=deepcopy(root["code_pins"])
    overrides={p:store.sha(("FICTIONAL old orchestration "+p).encode()) for p in (
        "nfl_lab/audit_weekly_discovery_v1.py","nfl_lab/audit_weekly_operations_restore_v1.py")}
    original_pins.update(overrides)
    predecessor={k:old["receipt"][k]for k in ("source_sha","workflow_sha256","policy_sha256","recipe_registration_sha256",
        "run_id","feed_sha256","root_go_sha256","epoch_sha256","choice_sha256")}
    predecessor.update(receipt_sha256=root["effective_epoch"]["previous_capture"]["receipt_sha256"],root_static_sha256="d"*64,
        code_pins_sha256=store.sha(store.canonical(original_pins)),locator={k:root["effective_epoch"]["previous_checkpoint"][k]for k in ("path","sha256")})
    body=dict(schema_version=history.SOURCE_HISTORY_BINDING,target_source_sha=root["source_sha"],
        target_policy_sha256=root["publication_registration"]["policy_sha256"],predecessor=predecessor,
        pin_overrides=overrides,runtime_transition="DUAL_RUNTIME_ROTATE")
    root["source_history_binding"]=history.source_history_envelope(body)
    assert len(root["code_pins"])==128 and history.source_history_scope(root,old["receipt"])==original_pins
    assert old["receipt"]["source_sha"] not in {root["source_sha"],x.p["readiness"]["source_sha"]}
    assert old["receipt"]["policy_sha256"]!=root["publication_registration"]["policy_sha256"]
    q.request["code_pins"]=deepcopy(root["code_pins"])
    q.native["request_sha256"]=store.sha(store.canonical(q.request))
    if actor=="owner":
        root["effective_epoch"]["controller_context"]=None
        q.env.update(GITHUB_ACTOR=controller.OWNER["login"],GITHUB_ACTOR_ID=str(controller.OWNER["id"]))
        x.api.data[controller.run_url("300")].update(actor=deepcopy(controller.OWNER),triggering_actor=deepcopy(controller.OWNER))
    x.reg=store.canonical(x.p);x.seal=store.sha(x.reg)
    x.native.update(registration_sha256=x.seal,code_pins_sha256=store.sha(store.canonical(root["code_pins"])))
    if actor=="bot":root["effective_epoch"]["controller_context"]["registration_sha256"]=x.seal
    x.claim["registration_sha256"]=x.seal
    seed=_dual_runtime_seed(case,root_override=root)
    seed.update(source_history=True,actor=actor)
    return seed


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
    calls=[];grants=[];clients=[];metadata_calls=[];selected=[];qualification_checks=[];prepared_requests=[];historical_grants=[]
    dual=seed.get("dual_runtime",False);source_history=seed.get("source_history",False)
    context=None
    def metadata(url,cap):
        assert url in api and bootstrap.fixed_route(url)
        metadata_calls.append(url)
        body=store.canonical(api[url]);assert len(body)<=cap
        return controller.Reply(200,body)
    def transport(req,timeout):
        assert req.method=="GET" and req.data is None
        calls.append((req.full_url,req.get_header("Accept")))
        if dual and req.full_url not in api:
            assert context is not None and type(context)is worker.Authenticated
            context.verify()
            if req.full_url.startswith(store.API+"/actions/runs/"):
                # A mismatched sealed anchor selects only the current package;
                # no current qualification API evidence exists in this test.
                assert req.full_url==store.API+"/actions/runs/"+go["qualified_runtime"]["run_id"]
                return Response(status=404)
            assert selected and all(p==seed["old"]["package"] for p in selected)
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
    from nfl_lab import audit_weekly_archive_v1 as archive,owner_private_bootstrap as owner,audit_weekly_template_v1 as template
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
    if dual:
        real_select=template.capture_runtime;real_qualification=archive.authenticate_qualification
        real_prepare=retained.prepare_request;real_bind=retained.bind_historical_source
        def select(root,**kwargs):
            package,pending=real_select(root,**kwargs);selected.append(deepcopy(package))
            if seed["damage"] is None:assert pending==seed["old"]["census"]
            return package,pending
        def qualify(client,package,pending):
            qualification_checks.append((deepcopy(package),deepcopy(pending)))
            return real_qualification(client,package,pending)
        def prepare(root,handoff,package,**kwargs):
            prepared=real_prepare(root,handoff,package,**kwargs);prepared_requests.append(deepcopy(prepared));return prepared
        def bind(request,native,**kwargs):
            grant=real_bind(request,native,**kwargs)
            historical_grants.append((grant,deepcopy(request),deepcopy(native)));return grant
        clock_scope.enter_context(patch.object(template,"capture_runtime",select))
        clock_scope.enter_context(patch.object(archive,"authenticate_qualification",qualify))
        clock_scope.enter_context(patch.object(retained,"prepare_request",prepare))
        clock_scope.enter_context(patch.object(retained,"bind_historical_source",bind))
    with clock_scope,patch.object(authority,"current",current),patch.object(hosted,"validate_root",validate),\
         patch.object(hosted,"child_context",child),patch.object(hosted,"pins",lambda:deepcopy(go["code_pins"])),\
         patch.object(retained,"_grant_authenticate",record_grant),patch.object(real_client,"__init__",init):
        context=worker.authenticate_child(SimpleNamespace(phase=recovery.PHASE,request="fictional-owned-control",request_sha256=native["request_sha256"]),
            env,phase=recovery.PHASE,transport=transport)
        assert context.verify()is context
        if dual:
            expected_proof=bootstrap.Owner if source_history and seed["actor"]=="owner" else controller.Proof
            assert type(context)is worker.Authenticated and type(context.proof)is expected_proof
            assert type(context.proof.bootstrap_seal)is bootstrap.Seal
            assert context.proof.document["actor"]==(controller.OWNER if expected_proof is bootstrap.Owner else controller.BOT)
            assert context.proof.document["root_go_sha256"]==store.sha(store.canonical(go))
            prepared=bootstrap.verify_template_payload(context.proof.bootstrap_seal,base64.b64decode(seed["static_template_base64"]))
            assert prepared.document["schema_version"]==(template.STATIC_V4 if source_history else template.STATIC_V3)
            sealed=prepared.document["root_template"]["prior_capture_qualified_runtime"]
            assert sealed["qualified_runtime"]==seed["old"]["package"] and sealed["pending_census"]==seed["old"]["census"]
            if seed["damage"] not in {"census","package"}:
                assert template.static_root_sha256(go)==template.digest(prepared.document["root_template"])
            if not source_history:assert sealed["root_static_sha256"]is None and go["effective_epoch"]["previous_checkpoint"]is None
            assert os.getpid()!=seed["parent_pid"]
            assert len(store.canonical(go))<=60<<10 and len(go["code_pins"])<=128
            dispatch_bytes=len(store.canonical(cp.strict_json(base64.b64decode(seed["event_base64"]))["inputs"]))
            assert dispatch_bytes<=65535
        try:
            result=recovery.restore(context,transport=transport)
        except (store.StoreError,template.TemplateError,bootstrap.BootstrapError) as error:
            if dual and seed["damage"] is not None:
                expected={"census":"ORIGINAL_PRIOR_QUALIFICATION_CENSUS","package":"CLOSED_OWNER_CLEARED_QUALIFIED_RUNTIME_PACKAGE"}
                if seed["damage"] in expected:
                    assert str(error)==expected[seed["damage"]]
                    assert not clients and not selected and not qualification_checks
                else:
                    assert selected==[go["qualified_runtime"]] and qualification_checks==[(go["qualified_runtime"],go["pending_census"])]
                    assert store.API+"/actions/runs/"+go["qualified_runtime"]["run_id"] in [url for url,_ in calls]
                assert not server.calls and not prepared_requests
                assert not (Path(request["output"])/"restored").exists()
                worker.native_envelope()
                return dict(state="PASS_FICTIONAL_DUAL_RUNTIME_REJECTED",damage=seed["damage"],error=str(error),
                    selected_runtime_ids=[p["runtime_id"]for p in selected],private_GETs=0,
                    root_bytes=len(store.canonical(go)),dispatch_input_bytes=dispatch_bytes,
                    pins=len(go["code_pins"]),HTTP_calls=len(calls)+len(metadata_calls),
                    bootstrap_metadata_GETs=len(metadata_calls),remote_writes=0,genuine_Actions_evidence=False)
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
    if dual:
        assert selected and all(p==seed["old"]["package"] for p in selected) and len(qualification_checks)>=2 and len(prepared_requests)==1
        assert all(package==seed["old"]["package"] and census==seed["old"]["census"] for package,census in qualification_checks)
        assert prepared_requests[0]["qualified_runtime"]==seed["old"]["package"]
        assert prepared_requests[0]["pending_census"]==seed["old"]["census"]
        assert all(c.binding==seed["old"]["package"]["binding"] for c in clients)
        bindings=[c._audit_operations_current for c in clients if hasattr(c,"_audit_operations_current")]
        assert bindings and all(type(binding)is authority.CurrentClient and binding.proof is context.proof for binding in bindings)
        assert all(cp.client_identity(c)==cp.client_identity(context.client) for c in clients)
        if not (source_history and seed["actor"]=="owner"):
            assert len(historical_grants)==1
            grant,approved,native=historical_grants[0]
            assert type(grant)is retained.HistoricalSourceGrant and grant._proof is context.proof
            assert approved==dict(prepared_requests[0],approved=True)
            assert grant.verify(approved,native,ScenarioClock.now(timezone.utc))is grant
            if source_history:
                assert grant.document["scope"]["public_policy_sha256"]==go["publication_registration"]["policy_sha256"]
                assert grant.document["scope"]["public_policy_sha256"]!=seed["old"]["receipt"]["policy_sha256"]
        else:assert not historical_grants
        assert all(c.extra_routes==frozenset(discovery.routes(seed["old"]["receipt"],seed["old"]["package"])) for c in clients)
        assert all(req.method=="GET" and req.data is None for req in server.calls)
        assert server.assets==[dict({k:v for k,v in a.items()if k!="body_base64"},body=base64.b64decode(a["body_base64"]))for a in seed["old"]["assets"]]
        assert manifest["current_root_go_sha256"]==context.root_sha256
        assert len(calls)+len(metadata_calls)<=recovery.LIMITS["HTTP_calls"]==640
    worker.native_envelope()
    return dict(state="PASS_FICTIONAL_NATIVE_DISCOVERY_AND_FULL_RECOVERY",calls=len(calls),clients=len(clients),files=result["files"],
        grant_kinds=[x[0]for x in grants],max_RSS_KiB=__import__("resource").getrusage(__import__("resource").RUSAGE_SELF).ru_maxrss,
        fits=result["fits"],model_decodes=result["model_decodes"],outcome_decodes=result["outcome_decodes"],remote_writes=result["remote_writes"],
        genuine_Actions_evidence=False,public_release=False,
        **(dict(root_bytes=len(store.canonical(go)),dispatch_input_bytes=dispatch_bytes,
            pins=len(go["code_pins"]),HTTP_calls=len(calls)+len(metadata_calls),
            bootstrap_metadata_GETs=len(metadata_calls),private_GETs=len(server.calls),
            original_runtime_id=seed["old"]["package"]["runtime_id"],current_runtime_id=go["qualified_runtime"]["runtime_id"],
            restored_original_bytes=True,native_wall_seconds=180,native_CPU_seconds=120,native_address_space_bytes=512<<20)
            if dual else {}))


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


@pytest.mark.parametrize("operational_case",["dual-runtime"],indirect=True)
@pytest.mark.parametrize("damage",[None,"feed-anchor","receipt-anchor","census","package"])
def test_fresh_v3_capture_uses_original_namespace_with_current_live_authority(operational_case,tmp_path,record_property,damage):
    seed=_dual_runtime_seed(operational_case,damage)
    assert seed["go"]["qualified_runtime"]["binding"]!=seed["old"]["package"]["binding"]
    path=tmp_path/"fictional-dual-runtime-seed.json";path.write_bytes(store.canonical(seed))
    script='''
import sys,json,socket
from pathlib import Path
from tools.private_draft_store_v2 import limits
limits()
sys.path.insert(0,str(Path.cwd()/'tests'))
import test_audit_weekly_operations_restore_v1 as probe
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('REAL_NETWORK_FORBIDDEN'))
seed=json.loads(Path(sys.argv[1]).read_bytes())
print(json.dumps(probe._native(seed),sort_keys=True))
'''
    profile=json.loads((ROOT/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    result=subprocess.run([sys.executable,"-B","-c",script,str(path)],cwd=ROOT,
        env={"PYTHONDONTWRITEBYTECODE":"1",**profile},capture_output=True,text=True,timeout=185)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout);record_property("fictional_dual_runtime",json.dumps(value,sort_keys=True))
    assert value["root_bytes"]<=60<<10 and value["dispatch_input_bytes"]<=65535 and value["pins"]<=128
    assert value["HTTP_calls"]<=recovery.LIMITS["HTTP_calls"]==640
    assert value["bootstrap_metadata_GETs"]>0 and value["remote_writes"]==0
    assert value["genuine_Actions_evidence"]is False
    if damage is not None:
        assert value["state"]=="PASS_FICTIONAL_DUAL_RUNTIME_REJECTED" and value["damage"]==damage
        assert value["private_GETs"]==0
        return
    assert value["state"]=="PASS_FICTIONAL_NATIVE_DISCOVERY_AND_FULL_RECOVERY"
    assert value["original_runtime_id"]!=value["current_runtime_id"] and value["private_GETs"]>0
    assert value["restored_original_bytes"]is True
    assert value["fits"]==value["model_decodes"]==value["outcome_decodes"]==0
    assert value["public_release"]is False
    assert value["native_wall_seconds"]==180 and value["native_CPU_seconds"]==120
    assert value["native_address_space_bytes"]==512<<20
    assert value["grant_kinds"]==["BIND_SEALED_DISCOVERY_SOURCE","LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET",
        "BIND_SEALED_HISTORICAL_SOURCE","LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET"]


@pytest.mark.parametrize("operational_case",["source-history"],indirect=True)
@pytest.mark.parametrize("actor",["bot","owner"])
def test_v4_actual_operations_retained_entry_keeps_old_receipt_and_current_authority(operational_case,tmp_path,actor):
    seed=_source_history_seed(operational_case,actor=actor)
    path=tmp_path/"fictional-source-history-seed.json";path.write_bytes(store.canonical(seed))
    script='''
import sys,json,socket
from pathlib import Path
from tools.private_draft_store_v2 import limits
limits()
sys.path.insert(0,str(Path.cwd()/'tests'))
import test_audit_weekly_operations_restore_v1 as probe
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('REAL_NETWORK_FORBIDDEN'))
print(json.dumps(probe._native(json.loads(Path(sys.argv[1]).read_bytes())),sort_keys=True))
'''
    profile=json.loads((ROOT/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    result=subprocess.run([sys.executable,"-B","-c",script,str(path)],cwd=ROOT,
        env={"PYTHONDONTWRITEBYTECODE":"1",**profile},capture_output=True,text=True,timeout=185)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout)
    assert value["state"]=="PASS_FICTIONAL_NATIVE_DISCOVERY_AND_FULL_RECOVERY" and value["restored_original_bytes"]is True
    assert value["original_runtime_id"]!=value["current_runtime_id"] and value["private_GETs"]>0
    assert value["fits"]==value["model_decodes"]==value["outcome_decodes"]==value["remote_writes"]==0
    assert value["genuine_Actions_evidence"]is value["public_release"]is False
    assert value["pins"]==128 and value["root_bytes"]<=60<<10 and value["dispatch_input_bytes"]<=65535
    expected=["BIND_SEALED_DISCOVERY_SOURCE","LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET"]
    if actor=="bot":expected += ["BIND_SEALED_HISTORICAL_SOURCE","LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET"]
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
