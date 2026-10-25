"""Portable fictional native failure wire; no real auth, HTTP, models or fits.

Exercise the actual failure codec/store against real OperationalStorage. Only
the HTTP transport is injected; append_failure/restore_failure are never mocked.
No actual RootGO, private metadata, forecasts or outcomes are fixtures here.
"""
import ast
import json
from pathlib import Path

import pytest

from nfl_lab import operational_failure_v1 as failure,private_draft_store as store
import test_operational_failure_v1 as fixtures

ROLES={"produce":"audit-weekly-produce-v1","restore":"audit-weekly-restore-v1",
    "consume":"audit-weekly-export-v1","evidence":"audit-weekly-failure-restore-v1"}
JOB_IDS={role:777+n for n,role in enumerate(ROLES)}


@pytest.fixture
def owned_service():
    value=fixtures.FailureTests(methodName="runTest");value.setUp()
    try:yield value
    finally:value.tearDown()


def native_client(service,role,operation,*,writer,completed=False,process):
    """Complete three weekly roles plus the separate failure-evidence job."""
    job=dict(execution_lane="github_actions",workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/fictional",
        workflow_sha=fixtures.SOURCE,job_id=ROLES[role],permission="write",event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
    def transport(request,timeout):
        if "/jobs?per_page=100&page=1" in request.full_url:
            service.server.calls.append(request);jobs=[]
            for key,name in ROLES.items():
                record=dict(id=JOB_IDS[key],name=name,run_id=int(fixtures.RUN),head_sha=fixtures.SOURCE,
                    status="in_progress" if key==role else "queued",conclusion=None)
                if key==writer and completed:
                    record.update(status="completed",conclusion="failure",started_at=(service.started-fixtures.timedelta(seconds=1)).isoformat(),
                        completed_at=(service.observed+fixtures.timedelta(seconds=1)).isoformat())
                jobs.append(record)
            return fixtures.Response(dict(total_count=len(jobs),jobs=jobs))
        return service.server(request,timeout)
    return store.Client("ghs_FICTIONAL",fixtures.RUN,journal=service.journal,source_sha=fixtures.SOURCE,
        transport=transport,process=process,job=job,operation=operation)


@pytest.mark.parametrize("writer,reader",[("produce","restore"),("restore","evidence"),("consume","evidence")])
def test_native_failure_authorization_bytes_append_and_independent_restore(owned_service,writer,reader):
    service=owned_service
    request=service.request(body=b"FICTIONAL original failure control; immutable opaque bytes\x00\xff")
    request["attempt"]["job_id"]=ROLES[writer]
    failure.record_failure(request,service.storage,service.output)
    original=(service.base/"original.bin").read_bytes();payload=(service.output/"FAILURE.json.gz").read_bytes()
    payload_sha=store.sha(payload)
    sender=native_client(service,writer,"append",writer=writer,process="4"*64)
    append_go=service.go(sender)
    dictionary=json.loads(append_go["authorization"])
    assert store.sha(store.canonical(dictionary))==append_go["authorization_sha256"]
    with pytest.raises(TypeError):
        failure.append_failure(sender,service.storage,service.output,**dict(append_go,authorization=dictionary))
    assert not service.server.calls and not (service.output/"APPEND_INTENT.json").exists()
    assert (service.output/"FAILURE.json.gz").read_bytes()==payload

    # Same GO object/hash, canonical byte wire: actual native append, two fake
    # service POSTs, with all production authorization and ownership checks.
    appended=failure.append_failure(sender,service.storage,service.output,**append_go)
    assert appended["status"]["failure_evidence_durable"] is False
    assert len(service.posts())==2 and sender.calls<=store.MAX_CALLS
    assert (service.output/"FAILURE.json.gz").read_bytes()==payload
    receiver=native_client(service,reader,"restore",writer=writer,completed=True,process="5"*64)
    restore_go=service.go(receiver,"restore",appended["descriptor"])
    restore_dictionary=json.loads(restore_go["authorization"])
    assert store.sha(store.canonical(restore_dictionary))==restore_go["authorization_sha256"]
    before=len(service.server.calls);destination=service.base/"independent-reader"
    with pytest.raises(TypeError):
        failure.restore_failure(receiver,service.storage,destination,**dict(restore_go,authorization=restore_dictionary))
    assert len(service.server.calls)==before and not destination.exists()
    restored=failure.restore_failure(receiver,service.storage,destination,**restore_go)
    assert len(service.posts())==2 and all(r.method=="GET" for r in service.server.calls[before:])
    assert restored["proof"]["job"]["job_id"]==ROLES[reader] and restored["producer_api_job_id"]==JOB_IDS[writer]
    assert restored["proof"]["job"]["api_job_id"]==JOB_IDS[reader]
    assert restored["proof"]["process_identity"]!=appended["descriptor"]["entry"]["producer_process"]
    assert restored["package_sha256"]==payload_sha and restored["attempt"]==request["attempt"]
    assert restored["status"]["failure_evidence_durable"] is True and receiver.calls<=store.MAX_CALLS
    assert all(restored["status"][key] is False for key in failure.NEGATIVE_GATES)
    assert (destination/"FAILURE.json.gz").read_bytes()==payload
    assert failure.unpack((destination/"FAILURE.json.gz").read_bytes())==(request,[original])
    assert Path(restored["attachments"][0]["path"]).read_bytes()==original
    assert (service.base/"original.bin").read_bytes()==original and (service.output/"FAILURE.json.gz").read_bytes()==payload


def test_root_append_and_restore_callers_supply_canonical_authorization_bytes():
    """Pair actual typed-boundary tests with both integrated Root call sites."""
    path=Path(failure.__file__).with_name("audit_weekly_hosted_v1.py")
    if not path.is_file():pytest.skip("integrated weekly Root is absent from this assembly checkout")
    tree=ast.parse(path.read_bytes());runner=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=="Runner")
    found={}
    for method,callee in (("preserve_failure","append_failure"),("restore","restore_failure")):
        function=next(node for node in runner.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==method)
        calls=[node for node in ast.walk(function) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
            and isinstance(node.func.value,ast.Name) and node.func.value.id=="failure" and node.func.attr==callee]
        assert len(calls)==1, "one registered core-failure call per Root route"
        authorization=next(keyword.value for keyword in calls[0].keywords if keyword.arg=="authorization")
        assert isinstance(authorization,ast.Call) and isinstance(authorization.func,ast.Attribute)
        assert isinstance(authorization.func.value,ast.Name) and authorization.func.value.id=="store" and authorization.func.attr=="canonical"
        assert len(authorization.args)==1 and isinstance(authorization.args[0],ast.Name) and authorization.args[0].id=="go"
        found[method]=True
    assert set(found)=={"preserve_failure","restore"}
