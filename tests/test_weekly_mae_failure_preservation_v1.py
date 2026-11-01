"""Actual failure wrapper/validator with explicit authority and transport mocks.

Synthetic metadata and owned files only. No native qualification, model, provider
or successful forecast is claimed by these local regression controls.
"""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_hosted_v1 as hosted
from nfl_lab import audit_weekly_archive_v1 as archive
from nfl_lab import audit_weekly_template_v1 as template
from nfl_lab import private_draft_store as store
from nfl_lab import weekly_mae_display_archive_v1 as display
from nfl_lab.operational_storage import OperationalStorage


@pytest.fixture
def failed_runner(tmp_path,monkeypatch,request):
    """Mock native authority/transport; retain actual wrapper, CAS and validator."""
    runner=object.__new__(hosted.Runner)
    runner.root=tmp_path/'attempt';runner.root.mkdir()
    runner.storage=OperationalStorage(runner.root/'cache',Path(hosted.ROOT)/'config/operational-source-policy-v2.json',state=runner.root/'state')
    runner.storage.register_root(runner.root)
    runner.go=dict(schema_version=getattr(request,'param',display.ROOT_V5),approved=True,source_sha='a'*40,jobs=dict(hosted.JOBS),
        mae_registration=dict(path=display.metadata.REGISTRATION_PATH,bytes=1,sha256='b'*64),
        qualified_runtime=dict(binding=dict(runtime_id='c'*32),qualification={}),pending_census={})
    if runner.go['schema_version']==template.ROOT_V4:runner.go.pop('mae_registration')
    runner.go_sha=display.digest(runner.go)
    runner.started=hosted.now_utc()-timedelta(seconds=1)
    runner.env=dict(GITHUB_OUTPUT=str(tmp_path/'outputs'))
    runner.identity=dict(run_id='49000000001',source_sha='a'*40)
    runner.job={};runner.journal=runner.root/'journal';runner.journal.mkdir()
    runner.require_pending_scope=lambda:None  # Explicit native authority mock.
    runner.fresh_operations_proof=lambda:None  # Appender factory is not invoked.
    hosted.write(runner.storage,runner.root/'OWNER_ROOT.json',runner.go)
    original=(runner.root/'OWNER_ROOT.json').read_bytes()
    expected=deepcopy(runner.go);profile_calls=[];append_calls=[];validations=[]
    def fixture_metadata(value,source_root):
        assert source_root==hosted.ROOT
        if value!=expected:raise ValueError('FICTIONAL_AUTHORITY_REJECTED_ROOT_MUTATION')
        return dict(categories=[])
    monkeypatch.setattr(display.metadata,'validate_root_extension',fixture_metadata)
    actual_checked=display.checked_profile
    def checked(root,digest,source_root):
        profile_calls.append((root,digest,source_root))
        return actual_checked(root,digest,source_root)
    monkeypatch.setattr(display,'checked_profile',checked)
    monkeypatch.setattr(template,'pending_recovery',lambda root:dict(pending_reservations=[]))
    def append(snapshot,factory,package,**kwargs):
        append_calls.append((snapshot,kwargs))
        assert package is runner.go['qualified_runtime']
        path=lambda name:Path(next(f['path']for f in snapshot['files']if f['logical_path']==name))
        validation=archive.validate_capture(snapshot,path,complete=False,display_profile=kwargs.get('display_profile'))
        validations.append(validation)
        assert (runner.root/'OWNER_ROOT.json').read_bytes()==original
        return dict(fictional_transport='FAILURE_EVIDENCE_ONLY')
    monkeypatch.setattr(archive,'produce',append)  # Explicit no-HTTP transport mock.
    monkeypatch.setattr(archive,'safe_handoff',store.canonical)
    return SimpleNamespace(runner=runner,expected=expected,profile_calls=profile_calls,
        append_calls=append_calls,validations=validations,original=original)


def test_actual_v5_failure_wrapper_binds_same_checked_profile_and_remains_unavailable(failed_runner):
    q=failed_runner;r=q.runner
    result=r.preserve_opaque_outputs()
    assert result==dict(fictional_transport='FAILURE_EVIDENCE_ONLY')
    assert len(q.profile_calls)==len(q.append_calls)==1
    assert q.profile_calls[0]==(r.go,r.go_sha,hosted.ROOT)
    snapshot,kwargs=q.append_calls[0];profile=kwargs['display_profile']
    assert type(profile)is display.DisplayProfile and profile.root_sha256==r.go_sha
    assert snapshot['census']['mae_display_profile']==dict(root_go_sha256=r.go_sha,registration_sha256=r.go['mae_registration']['sha256'])
    assert snapshot['census']['archive_state']=='FAILURE_EVIDENCE'
    assert snapshot['census']['fits']==0
    assert snapshot['census']['successful_forecast']is snapshot['census']['public_release']is False
    validation=q.validations[0]
    assert validation['state']=='FAILURE_EVIDENCE' and validation['qualified_selected']is False and validation['forecast_rows']==0
    assert validation['mae_display']['state']=='MAE_UNAVAILABLE'
    assert validation['mae_display']['eligible_rows']==0 and validation['mae_display']['public_export_authorized']is False
    assert (r.root/'OWNER_ROOT.json').read_bytes()==q.original


@pytest.mark.parametrize('failed_runner',[template.ROOT_V4],indirect=True)
def test_actual_legacy_failure_wrapper_keeps_original_census_and_validation(failed_runner):
    q=failed_runner;r=q.runner
    r.preserve_opaque_outputs()
    snapshot,kwargs=q.append_calls[0]
    assert q.profile_calls==[] and kwargs['display_profile']is None
    assert 'mae_display_profile'not in snapshot['census']
    assert q.validations==[dict(state='FAILURE_EVIDENCE',qualified_selected=False,forecast_rows=0)]


@pytest.mark.parametrize('damage',['missing_registration','changed_registration','wrong_root_hash'])
def test_actual_v5_failure_wrapper_rejects_profile_errors_without_legacy_fallback(failed_runner,damage):
    q=failed_runner;r=q.runner
    if damage=='missing_registration':r.go.pop('mae_registration')
    elif damage=='changed_registration':r.go['mae_registration']['sha256']='d'*64
    else:r.go_sha='e'*64
    with pytest.raises(ValueError,match='FICTIONAL_AUTHORITY_REJECTED_ROOT_MUTATION|EXACT_SOURCE_BOUND_ROOT_V5_DISPLAY_PROFILE_REQUIRED'):
        r.preserve_opaque_outputs()
    assert len(q.profile_calls)==1 and q.append_calls==[]
    assert not Path(r.env['GITHUB_OUTPUT']).exists()


@pytest.mark.parametrize('damage',['missing','wrong_root','wrong_registration'])
def test_actual_failure_census_guard_rejects_missing_or_corrupt_v5_binding(failed_runner,damage):
    q=failed_runner;r=q.runner;r.preserve_opaque_outputs()
    snapshot,kwargs=q.append_calls[0];snapshot=deepcopy(snapshot)
    if damage=='missing':snapshot['census'].pop('mae_display_profile')
    elif damage=='wrong_root':snapshot['census']['mae_display_profile']['root_go_sha256']='f'*64
    else:snapshot['census']['mae_display_profile']['registration_sha256']='f'*64
    with pytest.raises(store.StoreError,match='EXACT_ROOT_V5_CAPTURE_PROFILE_BINDING'):
        archive.validate_capture(snapshot,lambda name:Path(next(f['path']for f in snapshot['files']if f['logical_path']==name)),complete=False,display_profile=kwargs['display_profile'])
