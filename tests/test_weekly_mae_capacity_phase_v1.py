"""Actual produce/capacity/factory and HTTP budgets, synthetic native boundary.

The four prior children, live Owner/source proof and raw GHA transport are
explicit fixtures. No providers, models, forecast capture or native admission.
The real current-job auth, qualification/canary, inventory/accounting and
40-call/180-second/40MiB guards run with a deterministic monotonic clock.
"""
from copy import deepcopy
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest
from nfl_lab import audit_weekly_hosted_v1 as h,audit_weekly_archive_v1 as archive
from nfl_lab import private_draft_store as s,gha_private_checkpoint as cp
from nfl_lab.operational_storage import OperationalStorage
from test_audit_weekly_hosted_v1 import (
    _pending_budget_case,_pending_budget_runner,_pending_budget_metadata,
    _pending_budget_forbid_network,system,locator_system,
)

REAL_PENDING=h.PendingMetadataClient


class CaptureBoundary(Exception):pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *_:pytest.fail('REAL_NETWORK_FORBIDDEN'))


@pytest.fixture
def capacity_case(tmp_path,monkeypatch,_pending_budget_metadata):
    package,census=_pending_budget_metadata;transport_root=tmp_path/'transport';transport_root.mkdir()
    case=_pending_budget_case(transport_root,package,census,handoff_count=2,asset_count=101,redirects=2)
    runner,old,_,prior_clients,_=_pending_budget_runner(case,monkeypatch)
    runner.authenticate_pending_posts()
    assert runner.pending_scope_authenticated and len(runner.pending_metadata_clients)==2
    runner.go.update(operation='RECURRING_CAPTURE');runner.go_sha=s.sha(s.canonical(runner.go))
    runner.capacity_metadata_clients=[];runner.recovery_metadata_clients=[]
    runner.root=tmp_path/'owned'
    runner.storage=OperationalStorage(runner.root/'cache',Path(h.__file__).resolve().parents[1]/'config/operational-source-policy-v2.json',state=runner.root/'state')
    runner.storage.register_root(runner.root)
    clock=[0.0];old.clock=lambda:clock[0]
    flags={};fresh=[];proofs=[];captured=[];original_root=s.canonical(runner.go)
    counters=(old.started,old.calls,old.transferred)
    def proof():
        # Native Root/source qualification is this explicit fixture boundary;
        # each capacity operation must cross it again before any private GET.
        proofs.append(clock[0])
        if s.canonical(runner.go)!=original_root:raise s.StoreError('FIXTURE_CURRENT_ROOT_CHANGED')
        return runner.operations_proof
    runner.fresh_operations_proof=proof
    def transport(request,timeout):
        response=case.transport(request,timeout);url=request.full_url
        if flags.get('job') and url==s.API+'/actions/runs/'+case.current+'/jobs?per_page=100&page=1':
            body=json.loads(response.body);body['jobs'][0]['head_sha']='0'*40;return case.Response(body)
        if flags.get('package') and url==s.API+'/actions/runs/'+package['qualification']['run_id']:
            body=json.loads(response.body);body['head_sha']='0'*40;return case.Response(body)
        return response
    class CapacityClient(REAL_PENDING):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs,transport=transport,clock=lambda:clock[0]);fresh.append(self);self.drafts=0
        def draft(self):
            super().draft();self.drafts+=1
            # Two drafts belong to full qualification/canary; the third is
            # produce's capacity operation. Consume real budget after it.
            if self.drafts==3 and flags.get('wall'):clock[0]+=181.0
            if self.drafts==3 and flags.get('calls'):
                while self.calls<s.MAX_CALLS:self.json(self.allow(s.API+'/actions/runs/'+self.run_id))
    monkeypatch.setattr(h,'PendingMetadataClient',CapacityClient)
    def recurring():
        clock[0]=222.0
        return {},dict(inputs={'retained_restore':{'fictional':True}},execution_plan={'kind':'FUTURE_CAPABLE'})
    def origin():clock[0]=306.0;return {'fictional_originals':True}
    runner.recurring_prepare=recurring;runner.recover_origin=origin
    runner.recover_models=lambda:{'fictional_models':True}
    runner.metadata=lambda *_:{'retained_restore':{'fictional':True}}
    runner.claim=lambda:None;runner.register_publication=lambda _:None
    def capture(*args):captured.append(args);raise CaptureBoundary
    runner.capture=capture
    return SimpleNamespace(runner=runner,old=old,counters=counters,clock=clock,case=case,flags=flags,
        fresh=fresh,proofs=proofs,captured=captured,prior_clients=prior_clients)


@pytest.mark.parametrize('mode',['RECURRING_CAPTURE','CURRENT_CORRECTION_CAPTURE'])
def test_produce_uses_one_fresh_capacity_operation_after_old_client_expires(capacity_case,mode):
    x=capacity_case;r=x.runner
    if mode!='RECURRING_CAPTURE':
        r.go.update(operation=mode,effective_epoch=None);r.go_sha=s.sha(s.canonical(r.go))
        # Separate original-owner control in this fixture; the production
        # default branch still uses the same fresh capacity operation.
        expected=s.canonical(r.go)
        def proof():
            x.proofs.append(x.clock[0]);assert s.canonical(r.go)==expected;return r.operations_proof
        r.fresh_operations_proof=proof
    # All failure/recovery allowances stay available and are independent of
    # the capacity list, including the fully allocated8/2 boundary.
    r.pending_metadata_clients.extend([object()]*(8-len(r.pending_metadata_clients)))
    r.recovery_metadata_clients.extend([object(),object()])
    with pytest.raises(CaptureBoundary):r.produce()
    assert len(x.captured)==1 and len(x.fresh)==len(r.capacity_metadata_clients)==1
    current=x.fresh[0]
    assert current is not x.old and current.started==306.0 and 0<current.calls<=40
    assert current.clock()-current.started<=180 and current.transferred<=s.TRANSFER_CAP==40<<20
    assert (x.old.started,x.old.calls,x.old.transferred)==x.counters
    assert x.old.clock()-x.old.started==306.0 and x.old.calls<40
    assert len(r.pending_metadata_clients)==8 and len(r.recovery_metadata_clients)==2
    assert len(x.proofs)==1 and not current.posts and not x.old.posts
    assert all(c.job['api_job_id']==r.identity['api_job_id'] and c.binding==r.go['qualified_runtime']['binding'] for c in x.fresh)
    snapshot=h.read_owned(r.storage,cp.binding(r.root/'ARCHIVE_CAPACITY_BEFORE_CAPTURE.json'))
    assert snapshot['observed_at_utc'] and snapshot['payload_feasibility']=='UNKNOWN_UNTIL_ACTUAL_SERIALIZATION'
    calls=current.calls
    with pytest.raises(s.StoreError,match='ONE_PRE_CAPTURE_CAPACITY_CLIENT'):r.capacity_metadata_client()
    assert current.calls==calls and len(x.fresh)==1


@pytest.mark.parametrize('damage,reason',[
    ('root','FIXTURE_CURRENT_ROOT_CHANGED'),('job','ACTIONS_API_JOB_IDENTITY'),
    ('package','ACTUAL_QUALIFIED_ROTATION_RUN_REQUIRED')])
def test_current_root_job_and_qualified_package_changes_prevent_capture(capacity_case,damage,reason):
    x=capacity_case
    if damage=='root':x.runner.go['source_sha']='0'*40
    else:x.flags[damage]=True
    with pytest.raises(s.StoreError,match=reason):x.runner.produce()
    assert not x.captured and (x.old.started,x.old.calls,x.old.transferred)==x.counters
    assert len(x.fresh)<=1 and all(not c.posts for c in x.fresh)


@pytest.mark.parametrize('limit',['wall','calls'])
def test_capacity_operation_still_stops_at_its_own_180_seconds_or_40_calls(capacity_case,limit):
    x=capacity_case;x.flags[limit]=True
    with pytest.raises(s.StoreError,match='OPERATION_LIMIT'):x.runner.produce()
    assert not x.captured and len(x.fresh)==1
    current=x.fresh[0]
    if limit=='wall':assert current.clock()-current.started==181.0 and current.calls<40
    else:assert current.calls==40 and current.clock()-current.started==0.0
    assert current.started==306.0 and (x.old.started,x.old.calls,x.old.transferred)==x.counters
    assert len(x.runner.capacity_metadata_clients)==1 and not current.posts


@pytest.mark.parametrize('mode',['RECURRING_CAPTURE','CURRENT_CORRECTION_CAPTURE'])
def test_insufficient_current_capacity_preserves_records_and_never_starts_capture(capacity_case,mode):
    x=capacity_case;r=x.runner
    if mode!='RECURRING_CAPTURE':
        r.go.update(operation=mode,effective_epoch=None);r.go_sha=s.sha(s.canonical(r.go));r.fresh_operations_proof=lambda:r.operations_proof
    # Orphan metadata is still charged. Seven extra uploaded members leave
    # fewer than8 slots after the original unresolved reservations are charged.
    for n in range(7):
        body=('fictional-orphan-'+str(n)).encode();digest=s.sha(body);identity=30000+n
        x.case.assets.append(dict(id=identity,name='blob-'+digest+'.bin',size=len(body),state='uploaded',
            digest='sha256:'+digest,url=s.API+'/releases/assets/'+str(identity)))
    before={p.name:p.read_bytes() for p in r.journal.glob('*.reservation.json')}
    with pytest.raises(s.StoreError,match='ARCHIVE_MINIMUM_METADATA_FAILURE_RESERVE_BEFORE_CAPTURE'):r.produce()
    assert not x.captured and len(x.fresh)==1
    snapshot=h.read_owned(r.storage,cp.binding(r.root/'ARCHIVE_CAPACITY_BEFORE_CAPTURE.json'))
    assert snapshot['remaining_slots']<8
    assert {p.name:p.read_bytes() for p in r.journal.glob('*.reservation.json')}==before
    assert (x.old.started,x.old.calls,x.old.transferred)==x.counters and not x.fresh[0].posts
