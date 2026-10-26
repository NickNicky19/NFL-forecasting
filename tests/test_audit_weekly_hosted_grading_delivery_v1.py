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
