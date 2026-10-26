"""Fictional native recovery; grade identities never relabel original proofs."""
from copy import deepcopy
from datetime import datetime, timezone
import socket

import pytest

from nfl_lab import audit_weekly_grade_v1 as grade, private_draft_store as store
import test_audit_weekly_retained_v1 as fixture
from test_audit_weekly_retained_v1 import saved, chain


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,"connect",lambda *_:pytest.fail("REAL_NETWORK_FORBIDDEN"))


@pytest.fixture
def recovered(chain,monkeypatch):
    monkeypatch.setattr(fixture,"CURRENT_SOURCE",fixture.SOURCE)
    chain.authority['source_sha']=fixture.SOURCE
    result=fixture.execute(chain)
    assert result['current']['source_sha']==result['original_archive']['source_sha']
    return chain,result


def test_same_source_native_recovery_keeps_original_grade_availability_and_all_proofs(recovered):
    chain,result=recovered;before=deepcopy(result)
    evidence=grade._retained_evidence(result,chain.p.storage,datetime.now(timezone.utc))
    original_clocks=[j['completed_at'] for role,j in result['historical_job_evidence'].items() if role in {'produce','restore'}]
    original_clocks += [result['historical_reader_witness']['actual_completed_at']]
    original_clocks += [p['created_at_utc'] for p in result['historical_reader_witness']['proofs']]
    assert evidence['known_by']==max(original_clocks,key=grade.state.utc)
    assert grade.state.utc(evidence['known_by'])<grade.state.utc(evidence['recovery_completed_at'])
    assert result['current']['run_id']!=result['original_archive']['run_id']
    assert all(p['run_id']==result['current']['run_id'] and p['source_sha']==fixture.SOURCE for p in result['current_restore_proofs'])
    assert all(p['run_id']==result['original_archive']['run_id'] and p['source_sha']==fixture.SOURCE for p in result['historical_reader_witness']['proofs'])
    assert result==before
    assert all(q.method=='GET' for q in chain.history.calls[chain.calls_before:])


@pytest.mark.parametrize('failure',['same_run','producer_process','reader_process','reused_api_job','wrong_current_proof_source'])
def test_same_source_cannot_reuse_original_grade_identity_or_relabel_proofs(recovered,failure):
    chain,original=recovered;result=deepcopy(original);current=result['current']
    if failure=='same_run':current['run_id']=result['original_archive']['run_id']
    elif failure=='producer_process':current['process_identity']=result['original_archive']['producer']['process_identity']
    elif failure=='reader_process':current['process_identity']=result['original_reader_handoff']['restorer']['process_identity']
    elif failure=='reused_api_job':current['api_job_id']=result['historical_job_evidence']['consume']['api_job_id']
    else:result['current_restore_proofs'][0]['source_sha']='0'*40
    with pytest.raises(grade.GradeError):grade._retained_evidence(result,chain.p.storage,datetime.now(timezone.utc))
    assert result['historical_reader_witness']==original['historical_reader_witness']
