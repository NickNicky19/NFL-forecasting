"""Fictional fixed-route API proofs; saved JSON never grants BOT authority."""
from copy import deepcopy
import pickle
import socket
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_operations_authority_v1 as a
from nfl_lab import audit_weekly_controller_v1 as c, private_draft_store as store
from test_audit_weekly_controller_bootstrap_v1 import system, locator_system
import test_audit_weekly_controller_v1 as original


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *_:pytest.fail("FICTIONAL_PROOFS_ONLY"))


def proof(x):
    return a.current(x.env, x.raw, x.child_source, metadata_get=x.get,
        event_bytes=x.event, clock=lambda:original.AT, read_head=x.read_head)


def client(x, p):
    d=p.document
    return SimpleNamespace(run_id=d["run_id"], source_sha=d["source_sha"], process=store.process_identity(),
        job=dict(execution_lane="github_actions",run_authenticated=True,api_job_id=d["api_job_id"],
            job_id=d["job_id"],workflow_ref=x.env["GITHUB_WORKFLOW_REF"],workflow_sha=d["source_sha"],
            event_name="workflow_dispatch",permission="write"))


def test_current_bot_needs_actual_registered_metadata_before_client_scope(locator_system):
    x=locator_system;p=proof(x);q=client(x,p)
    history = c.API + "/commits?sha=lab-state&path=state/controller-v1/bootstrap-v2-20261026-retained-epoch.json&per_page=2&page=1"
    record = c.contents_url("state/controller-v1/bootstrap-v2-20261026-retained-epoch.json", x.public_commit)
    assert any(url == history for url,_ in x.calls)
    assert any(url == record for url,_ in x.calls)
    assert not any("/bootstrap-v2.json" in url for url,_ in x.calls)
    assert not any("/bootstrap-v2-20261026-discovery.json" in url for url,_ in x.calls)
    assert any("/actions/runs/300/jobs" in url for url,_ in x.calls)
    a.attach(q,p,x.env,x.raw)
    assert a.authorize_client_actor(q,x.api.data[c.run_url(q.run_id)]) is True
    with pytest.raises(store.StoreError):pickle.dumps(q._audit_operations_current)
    q._audit_operations_current.proof.document["source_sha"]="0"*40
    with pytest.raises((store.StoreError,c.ControllerError)):a.authorize_client_actor(q,x.api.data[c.run_url(q.run_id)])


@pytest.mark.parametrize("field",["run_id","source_sha","process","job_id","api_job_id"])
def test_attached_current_authority_cannot_move_to_other_identity(locator_system,field):
    x=locator_system;p=proof(x);q=client(x,p);a.attach(q,p,x.env,x.raw)
    if field in {"job_id","api_job_id"}:q.job[field]="other" if field=="job_id" else 12345
    else:setattr(q,field,"9"*64 if field=="process" else "9"*40)
    with pytest.raises(store.StoreError,match="CURRENT_CLIENT_SCOPE_OR_PROCESS_CHANGED"):
        a.authorize_client_actor(q,x.api.data[c.run_url(p.document["run_id"])])


@pytest.mark.parametrize("value",[None,True,{}, {"actual_actions_api_authenticated":True}])
def test_json_flags_cannot_authorize_current_bot(locator_system,value):
    x=locator_system;p=proof(x);q=client(x,p)
    with pytest.raises(store.StoreError):a.attach(q,value,x.env,x.raw)
    q._audit_operations_current=value
    with pytest.raises(store.StoreError,match="LIVE_CURRENT_BOT_CLIENT_REQUIRED"):
        a.authorize_client_actor(q,x.api.data[c.run_url(q.run_id)])


def test_registered_owner_and_ordinary_owner_stay_distinct(locator_system):
    x=locator_system
    x.go["effective_epoch"]["controller_context"]=None;x.bind_root()
    x.env.update(GITHUB_ACTOR=c.OWNER["login"],GITHUB_ACTOR_ID=str(c.OWNER["id"]))
    x.api.data[c.run_url("300")].update(actor=deepcopy(c.OWNER),triggering_actor=deepcopy(c.OWNER))
    p=proof(x);q=client(x,p);a.attach(q,p,x.env,x.raw)
    assert type(p) is a.bootstrap.Owner
    assert a.authorize_client_actor(q,x.api.data[c.run_url(q.run_id)]) is True
    ordinary=store.canonical(dict(operation="CURRENT_CORRECTION_CAPTURE"))
    assert a.current(x.env,ordinary,x.child_source) is None
    with pytest.raises(store.StoreError,match="ORIGINAL_OWNER_ONLY_OPERATION"):
        a.current(dict(x.env,GITHUB_ACTOR=c.BOT["login"],GITHUB_ACTOR_ID=str(c.BOT["id"])),ordinary,x.child_source)


def test_bot_actor_body_alone_or_a_copied_client_grants_nothing(locator_system):
    x=locator_system;p=proof(x);q=client(x,p)
    with pytest.raises(store.StoreError):a.authorize_client_actor(q,x.api.data[c.run_url(q.run_id)])
    a.attach(q,p,x.env,x.raw)
    other=client(x,p);other._audit_operations_current=q._audit_operations_current
    with pytest.raises(store.StoreError,match="CURRENT_CLIENT_SCOPE_OR_PROCESS_CHANGED"):
        a.authorize_client_actor(other,x.api.data[c.run_url(q.run_id)])
