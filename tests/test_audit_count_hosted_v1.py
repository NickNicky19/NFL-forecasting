"""Fictional dispatch/source boundaries; these mocks never establish Actions provenance."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import signal

import pytest

from tools import audit_count_hosted_v1 as hosted
from nfl_lab import audit_count_requalify_v1 as audit
from nfl_lab import private_draft_store as store


@pytest.fixture
def fictional_root(tmp_path,monkeypatch):
    names=["tools/audit_count_hosted_v1.py","tools/audit_count_requalify_v1.py",
        "nfl_lab/audit_count_requalify_v1.py","nfl_lab/weekly_future_inference.py",
        ".github/workflows/lab.yml","nfl_lab/audit_count_checkpoint_v1.py",
        "tools/audit_count_checkpoint_v1.py","tools/audit_count_failure_v1.py",
        "nfl_lab/operational_failure_v1.py","tools/operational_failure_v1.py",
        "tools/audit_count_verification_receipt_v1.py"]
    for name in names:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(("FICTIONAL "+name).encode())
    monkeypatch.setattr(hosted,"ROOT",tmp_path)
    monkeypatch.setattr(hosted.subprocess,"check_output",lambda args,**kw: "a"*40+"\n" if args[1]=="rev-parse" else "")
    now=datetime.now(timezone.utc)
    go=dict(schema_version="audit-count-root-GO-v1",approved=True,repository=audit.REPO,source_sha="a"*40,
        workflow_ref=hosted.WORKFLOW_REF,job_id=audit.RESTORE_JOB,
        single_writer_group="nfl-lab-single-writer",issued_at_utc=(now-timedelta(minutes=1)).isoformat(),
        expires_at_utc=(now+timedelta(minutes=30)).isoformat(),operation=hosted.OPERATION,
        maximum_new_fits=0,protected_outcome_reads=0,publication=False,
        helper_sha256={n:audit.sha((tmp_path/n).read_bytes())for n in names},
        owner_authorization="OWNER_NFL_AUDIT_CONTINUATION_20261025")
    env=dict(GITHUB_SHA=go["source_sha"],GITHUB_WORKFLOW_REF=go["workflow_ref"],GITHUB_JOB=audit.RESTORE_JOB,
        GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933",GITHUB_ACTIONS="true",GITHUB_REPOSITORY=audit.REPO,
        GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",STORE_PERMISSION="write",
        GITHUB_EVENT_PATH=str(tmp_path/"event.json"))
    def seal(document):
        body=audit.canonical(document);digest=audit.sha(body)
        Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps(dict(repository=dict(full_name=audit.REPO),
            inputs=dict(mode=audit.MODE,inference_builder_go_json=body.decode(),inference_builder_go_sha256=digest))))
        return body,digest
    return go,env,seal


def test_closed_scope_and_exact_event_body_are_required(fictional_root):
    go,env,seal=fictional_root;body,digest=seal(go)
    assert hosted.checked_root(body,digest,env)==go
    event=json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text());event["inputs"]["inference_builder_go_sha256"]="0"*64
    Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps(event))
    with pytest.raises(audit.AuditGuardError,match="EXACT_NEW_ACTIONS_MODE"):hosted.checked_root(body,digest,env)


@pytest.mark.parametrize("field,value",[("approved",False),("publication",True),("maximum_new_fits",True),
    ("maximum_new_fits",1),("protected_outcome_reads",1),("single_writer_group","other-writer"),
    ("operation","PUBLISH_FORECASTS"),("owner_authorization","unrelated"),("extra","ignored")])
def test_scope_cannot_expand(fictional_root,field,value):
    go,env,seal=fictional_root;go[field]=value;body,digest=seal(go)
    with pytest.raises(audit.AuditGuardError,match="CLOSED_OWNER_ROOT_GO"):hosted.checked_root(body,digest,env)


def test_expired_or_changed_source_is_rejected(fictional_root,monkeypatch):
    go,env,seal=fictional_root;bad=deepcopy(go);bad["expires_at_utc"]=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    with pytest.raises(audit.AuditGuardError,match="ROOT_GO_CURRENT_CLOCK"):hosted.checked_root(*seal(bad),env)
    body,digest=seal(go);(hosted.ROOT/"nfl_lab/weekly_future_inference.py").write_bytes(b"CHANGED")
    with pytest.raises(audit.AuditGuardError,match="EXACT_REVIEWED_HOSTED_SOURCE"):hosted.checked_root(body,digest,env)


def test_dirty_checkout_and_scheduled_event_never_get_authority(fictional_root,monkeypatch):
    go,env,seal=fictional_root;body,digest=seal(go)
    env["GITHUB_EVENT_NAME"]="schedule"
    with pytest.raises(audit.AuditGuardError,match="EXACT_NEW_ACTIONS_MODE"):hosted.checked_root(body,digest,env)
    env["GITHUB_EVENT_NAME"]="workflow_dispatch"
    monkeypatch.setattr(hosted.subprocess,"check_output",lambda args,**kw:"a"*40+"\n" if args[1]=="rev-parse" else "?? tools/injected.py\n")
    with pytest.raises(audit.AuditGuardError,match="CLEAN_EXACT_HOSTED_SOURCE_REQUIRED"):hosted.checked_root(body,digest,env)


def test_real_private_exchange_needs_metadata_timer_and_timer_does_not_reach_children():
    # This reproduces the actual first hosted failure without making HTTP calls.
    before=signal.getitimer(signal.ITIMER_REAL);handler=signal.getsignal(signal.SIGALRM)
    try:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,signal.SIG_DFL)
        with pytest.raises(store.StoreError,match="WALL_GUARD_REQUIRED"):
            with store.exchange_deadline(True):pass
        with hosted.metadata_deadline(2):
            assert signal.getsignal(signal.SIGALRM)==signal.SIG_DFL
            with store.exchange_deadline(True):
                assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 2
        assert signal.getitimer(signal.ITIMER_REAL)==(0.,0.)
        assert signal.getsignal(signal.SIGALRM)==signal.SIG_DFL
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)
        signal.setitimer(signal.ITIMER_REAL,*before)


def test_metadata_failure_restores_the_original_native_envelope():
    before=signal.getitimer(signal.ITIMER_REAL);handler=signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM,signal.SIG_IGN);signal.setitimer(signal.ITIMER_REAL,20)
        with pytest.raises(RuntimeError,match="fictional metadata failure"):
            with hosted.metadata_deadline(2):raise RuntimeError("fictional metadata failure")
        remaining,interval=signal.getitimer(signal.ITIMER_REAL)
        assert 0 < remaining <= 20 and interval==0 and signal.getsignal(signal.SIGALRM)==signal.SIG_IGN
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)
        signal.setitimer(signal.ITIMER_REAL,*before)
