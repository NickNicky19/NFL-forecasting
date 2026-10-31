"""Real registered-ref fault isolation; all model/native records fictional.

The Runtime fixture mocks numerical prepare/prediction and native API proof,
while the unchanged FutureSession._verify/strict close and owned storage run.
An additional small Leaf fixture exercises real joblib prepare/replay/close.
No actual NFL model, provider, fit, capture or native admission is used.
"""
from pathlib import Path
import pytest
from nfl_lab import audit_weekly_runtime_v1 as runtime
from nfl_lab import weekly_future_inference as future
from nfl_lab import weekly_mae_display_runtime_v1 as display
from test_weekly_mae_display_runtime_v1 import packet,staged,install_display


@pytest.fixture(autouse=True)
def synthetic_readiness(monkeypatch):
    monkeypatch.setattr(runtime.numerical,'loaded',lambda *_:None)


def old_snapshot(root):
    return {str(p):future.sha(p) for p in Path(root).rglob('*')
        if p.is_file() and not p.relative_to(root).as_posix().startswith('mae-display/')}


def test_legacy_terminal_and_handoff_precede_three_fresh_one_model_sessions(packet,monkeypatch):
    p=packet;install_display(p,monkeypatch);prepared,source,_=staged(p)
    prepare=future.FutureInferenceSession.prepare;close=future.FutureInferenceSession.close
    sessions=[];closed=[];snapshots=[]
    def observed_prepare(session,refs):
        if sessions:
            assert sessions[0].closed is True
            assert len(refs)==1
            terminal=p.root/'runtime/FINISHED.json';handoff=p.root/'runtime/EXPORT_INPUTS.json'
            assert terminal.is_file() and handoff.is_file()
            value=runtime.read_owned(p.storage,future.binding(terminal))
            assert value['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'
            assert runtime.read_owned(p.storage,future.binding(handoff))['terminal']==future.binding(terminal)
            snapshots.append(old_snapshot(p.root/'runtime'))
        sessions.append(session)
        return prepare(session,refs)
    def observed_close(session):
        result=close(session);closed.append(session);return result
    monkeypatch.setattr(future.FutureInferenceSession,'prepare',observed_prepare)
    monkeypatch.setattr(future.FutureInferenceSession,'close',observed_close)
    result_ref=p.runtime.infer(prepared,source,p.root/'runtime')
    result=runtime.read_owned(p.storage,result_ref)
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'
    assert len(sessions)==len(closed)==4 and len({id(s) for s in sessions})==4
    assert len(snapshots)==3 and all(s==snapshots[0] for s in snapshots)
    assert old_snapshot(p.root/'runtime')==snapshots[0]
    side=runtime.read_owned(p.storage,future.binding(p.root/'runtime/mae-display/FINISHED.json'))
    assert [s['state'] for s in side['statuses']]==['CAPTURED']*3
    assert side['extra_traversal_rows_reserved']==2*3*result['query_rows']
    assert side['legacy_prediction_rows']+side['extra_traversal_rows_reserved']<=18000
    assert len(p.loads)==len(p.feature_calls)==1 and len(p.requests)==4


def test_registered_point_ref_deletion_retains_closed_legacy_and_healthy_siblings(packet,monkeypatch):
    p=packet;install_display(p,monkeypatch);prepared,source,_=staged(p)
    fault=p.put('point-fault/independently-owned-receipt.json',{'fictional_point_only':True})
    prepare=future.FutureInferenceSession.prepare;predict=display.point.predict_point_chunks;close=future.FutureInferenceSession.close
    sessions=[];close_errors=[];damaged=[]
    def observed_prepare(session,refs):
        sessions.append(session);return prepare(session,refs)
    def broken_point(session,doc,*args,**kwargs):
        yield from predict(session,doc,*args,**kwargs)
        if doc['target']=='pass_int' and not damaged:
            session._verify([fault])
            assert fault['path'] in session.refs  # actual registration/stamp
            damaged.append(session)
            Path(fault['path']).unlink()  # explicit filesystem fault injection
            raise ValueError('FICTIONAL_POINT_RECEIPT_INTERRUPTED')
    def observed_close(session):
        try:return close(session)
        except Exception:
            close_errors.append(session);raise
    monkeypatch.setattr(future.FutureInferenceSession,'prepare',observed_prepare)
    monkeypatch.setattr(future.FutureInferenceSession,'close',observed_close)
    monkeypatch.setattr(display.point,'predict_point_chunks',broken_point)
    result=runtime.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'runtime'))
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'
    assert result['selected']['state']=='PERSISTED'
    assert sessions[0].closed is True and fault['path'] not in sessions[0].refs
    side=runtime.read_owned(p.storage,future.binding(p.root/'runtime/mae-display/FINISHED.json'))
    assert [s['state'] for s in side['statuses']]==['CAPTURED','FAILED_RETAINED','CAPTURED']
    assert side['statuses'][1]['failure']=='MAE_CATEGORY_SESSION_CLOSE_FAILED'
    assert side['statuses'][1]['persistence'] is None
    assert damaged==close_errors and len(damaged)==1
    assert damaged[0].closed is False and fault['path'] in damaged[0].refs  # never pruned/pretended closed
    assert len(sessions)==4 and sessions[1].closed and sessions[3].closed
    handoff=runtime.read_owned(p.storage,future.binding(p.root/'runtime/EXPORT_INPUTS.json'))
    assert handoff['terminal']==future.binding(p.root/'runtime/FINISHED.json')


def test_abrupt_optional_stop_keeps_already_written_legacy_finalization(packet,monkeypatch):
    p=packet;install_display(p,monkeypatch);prepared,source,_=staged(p)
    saved=[]
    def stopped(*args,**kwargs):
        snapshot=old_snapshot(p.root/'runtime')
        assert str(p.root/'runtime/FINISHED.json') in snapshot
        assert str(p.root/'runtime/EXPORT_INPUTS.json') in snapshot
        saved.append(snapshot)
        raise KeyboardInterrupt('FICTIONAL_HARD_STOP_AFTER_LEGACY_FINALIZATION')
    monkeypatch.setattr(p.runtime._mae,'capture',stopped)
    with pytest.raises(KeyboardInterrupt):p.runtime.infer(prepared,source,p.root/'runtime')
    assert old_snapshot(p.root/'runtime')==saved[0]
    terminal=runtime.read_owned(p.storage,future.binding(p.root/'runtime/FINISHED.json'))
    assert terminal['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE' and terminal['selected']['state']=='PERSISTED'


def test_genuine_prepared_leaf_scopes_strictly_reject_their_own_missing_registered_ref(tmp_path):
    from test_weekly_mae_point_inference_v2 import SyntheticPreparedLeaf
    fixture=SyntheticPreparedLeaf(tmp_path/'genuine-leaf')
    fresh=future.FutureInferenceSession(fixture.session.authenticate)
    fresh.prepare([fixture.artifact])  # actual decode/schema/replay qualification, zero fitting
    assert set(fresh.models)=={fixture.artifact['sha256']}
    fault=fixture.put('fresh-scope-only.json',{'fictional':True})
    fresh._verify([fault]);Path(fault['path']).unlink()
    with pytest.raises(FileNotFoundError):fresh.close()
    assert fresh.closed is False and fault['path'] in fresh.refs
    fixture.session.close()
    assert fixture.session.closed is True
