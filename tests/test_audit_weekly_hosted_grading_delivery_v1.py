"""Actual grade codec/private store with fictional Actions and publisher seams."""
from copy import deepcopy
import gzip
from pathlib import Path

import pytest

from nfl_lab import audit_weekly_hosted_v1 as hosted, audit_weekly_grade_history_v1 as history
from nfl_lab import audit_weekly_operations_grade_v1 as worker, audit_weekly_archive_v1 as archive
from nfl_lab import private_draft_store as store, gha_private_checkpoint as cp
from tools import persist_state
import test_audit_weekly_operations_grade_v1 as bridge
from test_audit_weekly_grade_history_v1 import locator_seed,original_seed


def test_real_produce_grade_only_route_never_reaches_capture_reference_or_publication(monkeypatch,tmp_path):
    r=object.__new__(hosted.Runner)
    r.go=dict(operation='RECURRING_CAPTURE',effective_epoch=dict(plan=dict(kind='GRADE_ONLY')))
    r.go_sha='a'*64;r.env=dict(GITHUB_OUTPUT=str(tmp_path/'outputs'));r.check=lambda:None
    r.recurring_prepare=lambda:({},dict(execution_plan=dict(kind='GRADE_ONLY'),inputs=None))
    def forbidden(*args,**kwargs):pytest.fail('GRADE_ONLY_MUST_NOT_ISSUE_OR_PUBLISH_FORECAST')
    for name in ('recover_origin','capture','reference','register_publication','archive_call'):
        monkeypatch.setattr(r,name,forbidden)
    result=r.produce()
    assert result['state']=='ORIGINAL_CAPTURE_RECOVERED_GRADE_ONLY_NO_NEW_FORECAST'
    assert result['public_feed_written'] is result['successful_forecast'] is result['public_release'] is False
    lines=(tmp_path/'outputs').read_text().splitlines()
    assert lines[0].startswith('grade_only_plan_json=') and lines[1].startswith('grade_only_plan_sha256=')
    assert not any(line.startswith(('archive_handoff_json=','archive_reader_handoff_json=')) for line in lines)


@pytest.mark.parametrize('phase',['restore','consume'])
def test_grade_only_real_phase_router_requires_no_fake_archive_handoff(phase):
    r=object.__new__(hosted.Runner);r.go=dict(operation='RECURRING_CAPTURE',effective_epoch=dict(plan=dict(kind='GRADE_ONLY')))
    body=store.canonical({'fictional':'native handoff checked by guarded grade worker'})
    r.env=dict(AUDIT_WEEKLY_GRADE_HANDOFF_JSON=body.decode(),AUDIT_WEEKLY_GRADE_HANDOFF_SHA256=store.sha(body))
    seen=[]
    r.grade_only=lambda **kwargs:(seen.append(kwargs) or dict(state='FICTIONAL_ROUTING_ONLY'))
    result=getattr(r,phase)()
    assert result['state']=='FICTIONAL_ROUTING_ONLY'
    assert seen==([{}] if phase=='restore' else [dict(handoff=cp.strict_json(body))])


def test_grade_only_consume_rejects_corrupt_native_handoff_before_any_restore():
    r=object.__new__(hosted.Runner);r.go=dict(operation='RECURRING_CAPTURE',effective_epoch=dict(plan=dict(kind='GRADE_ONLY')))
    r.env=dict(AUDIT_WEEKLY_GRADE_HANDOFF_JSON='{}',AUDIT_WEEKLY_GRADE_HANDOFF_SHA256='0'*64)
    r.grade_only=lambda **kwargs:pytest.fail('CORRUPT_HANDOFF_CANNOT_TRIGGER_PRIVATE_RESTORATION')
    with pytest.raises(store.StoreError,match='EXACT_NATIVE_GRADING_WRITER_HANDOFF_REQUIRED'):r.consume()


@pytest.fixture
def ready(tmp_path,monkeypatch):
    x=bridge.pipeline.__wrapped__(tmp_path,monkeypatch);q=x.q
    first=worker.execute(x.context(worker.PHASES[0]),fetch=x.fetch,clock=lambda:x.service.now)
    from datetime import timedelta
    x.service.writer_done=(x.service.now+timedelta(seconds=10)).isoformat();x.service.now+=timedelta(minutes=2)
    second=worker.execute(x.context(worker.PHASES[1],first['checkpoint_handoff']),clock=lambda:x.service.now)
    report=archive.read_owned(q['storage'],second['manifest']);proof=report['grade_read_proof']
    client=archive.Client('ghs_FICTIONAL',bridge.RUN,journal=x.clients[-1].journal,source_sha=bridge.SOURCE,
        job=deepcopy(x.clients[-1].job),operation='append',qualification=x.service.q,transport=x.service.transport,process='f'*64)
    client.bind(x.service.binding);client.authenticate_actions_job()
    r=object.__new__(hosted.Runner);r.phase='consume';r.storage=q['storage']
    r.root=r.storage.register_root(tmp_path/'hosted-consume');r.check=lambda:None
    r.go=dict(operation='RECURRING_CAPTURE',publication=True,qualified_runtime=x.service.package,source_sha=bridge.SOURCE)
    r.go_sha=bridge.ROOT_SHA;r.identity=cp.client_identity(client);r.failure_client=lambda operation:client
    source=r.storage.register_root(tmp_path/'fictional-checkout');monkeypatch.setattr(hosted,'ROOT',source)
    receipt=dict(feed_sha256='6'*64,source_sha=bridge.SOURCE,run_id=bridge.RUN,root_go_sha256=bridge.ROOT_SHA,
        workflow_sha256='7'*64,epoch_sha256=first['checkpoint_handoff']['epoch_sha256'],
        jobs={role:{k:identity[k] for k in ('job_id','api_job_id')} for role,identity in
            [('restore',proof['producer']),('consume',proof['reader'])]})
    return r,second['manifest'],receipt,x


def test_hosted_native_reader_evidence_is_private_and_publication_is_one_closed_locator(ready,monkeypatch):
    r,manifest,receipt,x=ready;calls=[];before=len(x.service.server.assets)
    def publish(root,state,**kwargs):
        assert root==hosted.ROOT and kwargs['storage'] is r.storage
        expected='controller-v1/grade-checkpoints/'+receipt['feed_sha256']+'.json.gz'
        assert set(kwargs['files'])=={expected}
        raw=(state/expected).read_bytes();assert store.sha(raw)==kwargs['files'][expected]
        value=cp.strict_json(gzip.decompress(raw));assert set(value)==history.SIDECAR_KEYS
        assert value['feed_sha256']==receipt['feed_sha256']
        assert value['grade_read_proof']['reader']['api_job_id']==r.identity['api_job_id']
        assert not {'rows','outcomes','observations','resolver_versions','native_read_evidence'} & set(value)
        assert (r.root/'grading-delivery/APPENDED.json').is_file()
        calls.append(value)
    monkeypatch.setattr(persist_state,'persist',publish)
    result=r.grading_delivery(manifest,receipt)
    assert len(calls)==1 and len(x.service.server.assets)==before+2
    assert result['sidecar_path']=='controller-v1/grade-checkpoints/'+receipt['feed_sha256']+'.json.gz'
    assert result['evidence_descriptor_sha256']==store.sha(store.canonical(calls[0]['evidence_descriptor']))


def test_sidecar_publish_failure_retains_actual_evidence_append_and_original_manifest(ready,monkeypatch):
    r,manifest,receipt,x=ready;original=cp.read_ref(manifest)
    def fail(*args,**kwargs):raise RuntimeError('FICTIONAL_PUBLISH_FAILURE')
    monkeypatch.setattr(persist_state,'persist',fail)
    with pytest.raises(RuntimeError,match='^FICTIONAL_PUBLISH_FAILURE$'):
        r.grading_delivery(manifest,receipt)
    assert cp.read_ref(manifest)==original
    appended=cp.strict_json((r.root/'grading-delivery/APPENDED.json').read_bytes())
    assert appended['descriptor']['entry']['writer_run_id']==r.identity['run_id']
    assert appended['evidence_sha256']==archive.read_owned(r.storage,manifest)['evidence_envelope']['sha256']


def test_grade_only_reader_evidence_is_privately_retained_without_any_feed_or_locator(ready,monkeypatch):
    r,manifest,receipt,x=ready
    r.go['effective_epoch']=dict(plan=dict(kind='GRADE_ONLY',season=2026,week=7),
        previous_capture=dict(feed_sha256=receipt['feed_sha256'],receipt_sha256='9'*64))
    before=len(x.service.server.assets);original=cp.read_ref(manifest)
    monkeypatch.setattr(persist_state,'persist',lambda *_a,**_k:pytest.fail('GRADE_ONLY_CANNOT_PUBLISH_A_FEED'))
    result=r.retain_grade_only_evidence(manifest)
    assert len(x.service.server.assets)==before+2
    saved=archive.read_owned(r.storage,result['receipt'])
    report=archive.read_owned(r.storage,manifest)
    assert saved['grade_read_proof']==report['grade_read_proof']
    assert saved['checkpoint_handoff']==report['checkpoint_handoff']
    assert saved['evidence_sha256']==report['evidence_envelope']['sha256']
    assert cp.read_ref(manifest)==original
    assert saved['public_release'] is saved['successful_forecast'] is False
    assert result['public_feed_written'] is result['scheduled_parent_discoverable'] is False
    assert not (r.root/'grade-only-evidence/public-state').exists()


def test_new_grade_only_publication_is_only_a_closed_nonforecast_locator(locator_seed,tmp_path,monkeypatch):
    """Real codec/private append in seed; fictional API and publisher boundary."""
    from nfl_lab.operational_storage import OperationalStorage
    from test_private_draft_store_v2 import Response
    seed=locator_seed;v=seed['locator'];cohort=v['cohort'];root=tmp_path/'metadata-only'
    storage=OperationalStorage(root/'cache',Path(__file__).resolve().parents[1]/'config/operational-source-policy-v2.json',state=root/'state')
    storage.register_root(root);journal=storage.register_root(root/'journal')
    def api(request,timeout):
        assert request.method=='GET'
        if '/jobs?' not in request.full_url:return Response(dict(id=int(cohort['run_id']),head_sha=seed['source'],event='workflow_dispatch',run_attempt=1,
            path='.github/workflows/lab.yml',head_branch='fictional',status='in_progress',conclusion=None,repository=dict(full_name=store.REPO),
            head_repository=dict(full_name=store.REPO),actor=dict(login='NickNicky19',id=208912933)))
        return Response(dict(total_count=3,jobs=[dict(id=cohort['jobs'][role]['api_job_id'],name=name,run_id=int(cohort['run_id']),head_sha=seed['source'],
            status='in_progress' if role=='consume' else 'completed',conclusion=None if role=='consume' else 'success',started_at=a,completed_at=None if role=='consume' else b)
            for (role,name),(a,b) in zip(hosted.JOBS.items(),seed['job_times'])]))
    identity=v['sidecar']['evidence_producer']
    client=archive.Client('ghs_FICTIONAL',cohort['run_id'],journal=journal,source_sha=seed['source'],operation='append',transport=api,process=identity['process_identity'],
        job=dict(execution_lane='github_actions',workflow_ref=identity['workflow_ref'],workflow_sha=seed['source'],job_id=hosted.JOBS['consume'],permission='write',
            event_name='workflow_dispatch',api_job_id=identity['api_job_id'],run_authenticated=True))
    r=object.__new__(hosted.Runner);r.go=seed['original_root'];r.go_sha=cohort['root_go_sha256'];r.identity=identity;r.storage=storage;r.root=root
    r.phase='consume';r.client=None;r.check=lambda:None  # expired/absent boot client cannot be used
    body=next(a['body'] for a in seed['assets'] if a['id']==v['sidecar']['evidence_descriptor']['entry']['payload_asset_id'])
    import base64
    envelope=history.metadata_document(base64.b64decode(body),cap=history.LIMITS['envelope_bytes'])
    from nfl_lab import state
    monkeypatch.setattr(hosted,'now_utc',lambda:state.utc(cohort['created_at']))  # explicit fictional clock, not hosted evidence
    seen=[]
    def persist(_root,state,**kwargs):
        assert len(kwargs['files'])==1
        name=next(iter(kwargs['files']));assert name.startswith('controller-v1/history-v2/')
        raw=(state/name).read_bytes();assert store.sha(raw)==kwargs['files'][name]
        doc=history.metadata_document(raw)
        assert doc['anchor']==v['anchor'] and doc['cohort']['kind']=='GRADING_ONLY'
        assert doc['cohort']['successful_forecast'] is doc['cohort']['public_release'] is False
        assert doc['sidecar']['checkpoint_handoff']==v['sidecar']['checkpoint_handoff']
        assert not any(key in doc for key in ('rows','outcomes','forecast_rows','native_read_evidence','root_go'))
        seen.append(doc)
    monkeypatch.setattr(persist_state,'persist',persist);monkeypatch.setattr(hosted,'ROOT',storage.register_root(root/'checkout'))
    result=r.publish_history_locator(envelope,v['sidecar']['checkpoint_handoff'],v['sidecar']['grade_read_proof'],v['sidecar']['evidence_descriptor'],identity,
        anchor=v['anchor'],kind='GRADING_ONLY',folder=storage.register_root(root/'publication'),append_client=client)
    assert len(seen)==1 and result['path'].endswith(history.locator_filename(seen[0]))
    assert not (root/'publication/history-public-state/public').exists()
    with pytest.raises(store.StoreError,match='EXACT_NONFORECAST_LOCATOR_KIND'):
        r.publish_history_locator(envelope,v['sidecar']['checkpoint_handoff'],v['sidecar']['grade_read_proof'],v['sidecar']['evidence_descriptor'],identity,
            anchor=v['anchor'],kind='CAPTURE_AND_GRADE',folder=root/'rejected',append_client=client)
