"""Conditional actor metadata with a real verifier and fictional raw APIs only."""
import base64
from copy import deepcopy
import pickle
import socket
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_discovery_v1 as d, audit_weekly_retained_v1 as retained
from nfl_lab import audit_weekly_controller_v1 as controller, private_draft_store as store
import test_audit_weekly_controller_bootstrap_v1 as bootstrap_fixture
from test_audit_weekly_archive_v1 import Service
from test_private_draft_store_v2 import Response


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *_:pytest.fail('REAL_NETWORK_FORBIDDEN'))


@pytest.fixture
def system(tmp_path,monkeypatch):
    source=tmp_path/'bootstrap';source.mkdir()
    b=bootstrap_fixture.system.__wrapped__(source)
    proof=b.verify()  # Actual bootstrap/claim verifier over injected raw API bodies.
    monkeypatch.setattr(d,'now',lambda:bootstrap_fixture.old.AT)
    service=Service(tmp_path)
    x=SimpleNamespace(b=b,proof=proof,service=service,calls=[],callbacks=[],live=True,private_reached=False)
    def packet(operational=False):
        value=controller.decode(b.original_receipt)
        run_id=value['run_id'];data=deepcopy(b.api.data)
        if operational:
            spec=b.p['producer']
            value.update(source_sha=spec['source_sha'],policy_sha256=proof.bootstrap_seal.document['static_public_policy_sha256'],
                workflow_sha256=spec['workflow_sha256'])
            value['jobs']={role:dict(job_id=spec['jobs'][role],api_job_id=j['api_job_id']) for role,j in value['jobs'].items()}
            data[controller.run_url(run_id)].update(head_sha=spec['source_sha'],head_branch=spec['branch'],actor=dict(controller.BOT))
            by_id={j['api_job_id']:role for role,j in value['jobs'].items()}
            for row in data[controller.jobs_url(run_id)]['jobs']:
                role=by_id[row['id']]
                row.update(head_sha=spec['source_sha'],name=value['jobs'][role]['job_id'])
        workflow=base64.b64decode(data[retained.source_url(value['source_sha'],'.github/workflows/lab.yml')]['content'])
        codes={name:('FICTIONAL PINNED '+name).encode() for name in retained.HISTORICAL_FILES}
        codes['.github/workflows/lab.yml']=workflow
        codes['config/private-draft-storage-v2.json']=store.read_local(store.CONFIG,16384)
        for name,body in codes.items():
            data[retained.source_url(value['source_sha'],name)]=dict(type='file',path=name,encoding='base64',size=len(body),content=base64.b64encode(body).decode())
        pins={name:store.sha(body) for name,body in codes.items()}
        x.value,x.data,x.pins=value,data,pins
        return value
    x.packet=packet;packet()
    def live(request):
        x.callbacks.append(deepcopy(request))
        assert request['inputs_sha256']==store.sha(store.canonical(request['inputs']))
        assert request['kind'] in {'BIND_SEALED_DISCOVERY_SOURCE','LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET'}
        return request['kind']=='BIND_SEALED_DISCOVERY_SOURCE' or x.live
    x.live_auth=live
    def mint(proof_override=None):
        raw=store.canonical(x.value)
        return d.bind_discovery_source(raw,store.sha(raw),service.package,
            bootstrap_proof=proof if proof_override is None else proof_override,current_root_go_sha256=controller.sha(b.raw),
            historical_source_sha256=x.pins,authenticate=live,clock=lambda:bootstrap_fixture.old.AT)
    x.mint=mint
    class PrivateGETReached(Exception):pass
    x.PrivateGETReached=PrivateGETReached
    def transport(request,timeout):
        x.calls.append(request)
        assert request.method=='GET' and request.data is None
        if '/releases/' in request.full_url:
            assert x.callbacks[-1]['kind']=='LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET'
            assert set(x.callbacks[-1]['inputs']['historical_jobs'])=={'produce','restore','consume'}
            x.private_reached=True
            raise PrivateGETReached()
        if request.full_url in x.data:return Response(x.data[request.full_url])
        # The separately qualified old namespace still authenticates its own
        # original Nick jobs. This fake service is not current actor authority.
        return service.transport(request,timeout)
    journal=tmp_path/'discovery-journal';journal.mkdir(mode=0o700)
    def factory(operation):
        assert operation=='restore'
        ident=proof.document
        job=dict(execution_lane='github_actions',workflow_ref=b.env['GITHUB_WORKFLOW_REF'],workflow_sha=ident['source_sha'],
            job_id=ident['job_id'],permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
        c=retained.ReadClient('ghs_FICTIONAL',ident['run_id'],journal=journal,source_sha=ident['source_sha'],job=job,
            operation='restore',transport=transport,extra_routes=d.routes(x.value,service.package))
        c.bind(service.binding)
        return c
    x.factory=factory
    def native_auth(c,scope):
        return (c.job['run_authenticated'] is True and scope['current_root_go_sha256']==controller.sha(b.raw)
            and scope['receipt_sha256']==store.sha(store.canonical(x.value))
            and all(scope['current'][k]==proof.document[k] for k in ('run_id','source_sha','job_id','api_job_id')))
    x.native_auth=native_auth
    def run(grant):
        from nfl_lab.operational_storage import OperationalStorage
        storage=OperationalStorage(tmp_path/'cache',store.CONFIG.parents[0]/'operational-source-policy-v2.json',state=tmp_path/'state')
        raw=store.canonical(x.value)
        return d.discover(raw,store.sha(raw),service.package,factory,storage=storage,output=tmp_path/'discovery',
            historical_source_sha256=x.pins,pending_census=service.census,current_root_go_sha256=controller.sha(b.raw),
            authenticate=native_auth,discovery_grant=grant)
    x.run=run
    return x


@pytest.mark.parametrize('operational',[False,True])
def test_owner_readiness_then_same_source_bot_history_require_live_sealed_grant_before_private_GET(system,operational):
    x=system;x.packet(operational)
    before=store.canonical(x.value);grant=x.mint()
    with pytest.raises(x.PrivateGETReached):x.run(grant)
    assert x.private_reached
    assert store.canonical(x.value)==before
    assert [r['kind'] for r in x.callbacks]==['BIND_SEALED_DISCOVERY_SOURCE','LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET']
    kind='CURRENT_SEALED_OPERATIONAL_SOURCE' if operational else 'OWNER_SEALED_NICK_READINESS'
    assert grant.document['historical_contract']['kind']==kind
    with pytest.raises(store.StoreError,match='CANNOT_BE_SERIALIZED'):pickle.dumps(grant)


@pytest.mark.parametrize('failure',['saved_proof','wrong_policy','wrong_source','readiness_bot','failed_job',
                                  'job_source','stale_current','rejected_live_callback','saved_grant','changed_grant'])
def test_conditional_discovery_rejects_unsealed_or_stale_history_before_any_private_GET(system,failure):
    x=system
    if failure in {'wrong_policy','wrong_source'}:
        x.value['policy_sha256' if failure=='wrong_policy' else 'source_sha']='0'*(64 if failure=='wrong_policy' else 40)
        with pytest.raises(store.StoreError):x.mint()
    elif failure=='saved_proof':
        with pytest.raises(store.StoreError,match='LIVE_DISCOVERY_BOOTSTRAP_PROOF'):x.mint(proof_override=x.proof.document)
    else:
        grant=x.mint();run=x.value['run_id']
        if failure=='readiness_bot':x.data[controller.run_url(run)]['actor']=dict(controller.BOT)
        elif failure=='failed_job':x.data[controller.jobs_url(run)]['jobs'][2]['conclusion']='failure'
        elif failure=='job_source':x.data[controller.jobs_url(run)]['jobs'][0]['head_sha']='0'*40
        elif failure=='stale_current':x.data[controller.run_url(x.proof.document['run_id'])]['head_sha']='0'*40
        elif failure=='rejected_live_callback':x.live=False
        elif failure=='saved_grant':grant=grant.document
        elif failure=='changed_grant':grant.document['scope']['operational_source_sha']='0'*40
        with pytest.raises(store.StoreError):x.run(grant)
    assert not x.private_reached
    assert not any('/releases/' in q.full_url for q in x.calls)


def test_matching_bots_without_explicit_grant_are_not_legacy_owner_authority(system):
    x=system;x.packet(True)
    with pytest.raises(store.StoreError,match='ACTUAL_COMPLETED_PRIOR_RUN_SOURCE_AND_CURRENT_OWNER'):x.run(None)
    assert not x.private_reached
