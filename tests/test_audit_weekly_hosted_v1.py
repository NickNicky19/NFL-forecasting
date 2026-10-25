"""Independent calendar/ownership/failure probes; all service values fictional."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nfl_lab import audit_weekly_hosted_v1 as hosted, audit_weekly_epoch_v1 as epoch
from nfl_lab import private_draft_store as store, operational_failure_v1 as failure
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references


def test_calendar_uses_new_york_kickoff_clock_across_both_dst_offsets_and_not_scores():
    raw=("season,week,game_type,game_id,gameday,gametime,home_score\n"
        "2026,7,REG,oct,2026-10-25,09:30,DO_NOT_READ_OUTCOME\n"
        "2026,10,REG,nov,2026-11-15,13:00,DO_NOT_READ_OUTCOME\n").encode()
    a=hosted.schedule_metadata(raw,season=2026,week=7)
    b=hosted.schedule_metadata(raw,season=2026,week=10)
    assert a[0]['kickoff_utc']=='2026-10-25T13:30:00+00:00'
    assert b[0]['kickoff_utc']=='2026-11-15T18:00:00+00:00'
    assert all('score' not in k for x in a+b for k in x)
    with pytest.raises(store.StoreError,match='COMPLETE_UNIQUE_WEEK_CALENDAR'):
        hosted.schedule_metadata(raw+raw.splitlines()[1]+b'\n',season=2026,week=7)


def test_old_raw_completion_and_new_terminal_witness_are_distinct_epoch_origins():
    from test_audit_weekly_origin_v1 import fixture,CHECKED
    from test_audit_weekly_epoch_v1 import fixture as model_fixture
    f=fixture();w=f['witness']
    history=dict(bytes=123,sha256='f'*64)
    e=epoch.prepare_epoch(f['raw_choice'],w,f['slate'],f['catalog'],f['policy'],model_fixture()['replay'],
        history_binding=history,clock=lambda:CHECKED)
    assert e.origin['completion']['schema_version']=='audit-weekly-origin-v1-terminal-witness'
    assert e.origin['completion']['original_completion_file_retained'] is False
    assert e.origin['completion']['created_at_utc']!=e.origin['completion']['actual_decision_persist_completed_at']
    e2=epoch.restore_epoch(e.document,f['raw_choice'],w,f['slate'],f['catalog'],f['policy'],history_binding=history,now=CHECKED+timedelta(seconds=1))
    assert e2.sha256==e.sha256
    for key,value in [('created_at_utc','2027-01-01T00:00:00Z'),('fabricated_original_receipt',True)]:
        changed=deepcopy(w);changed[key]=value
        with pytest.raises(epoch.EpochError,match='SOURCE_BOUND_ORIGINAL_TERMINAL_WITNESS_REQUIRED'):
            epoch.prepare_epoch(f['raw_choice'],changed,f['slate'],f['catalog'],f['policy'],model_fixture()['replay'],history_binding=history,clock=lambda:CHECKED)


def test_entry_preparation_has_no_network_credentials_or_package_dependencies():
    path=Path(__file__).resolve().parents[1]/'tools/audit_weekly_hosted_v1.py'
    result=subprocess.run([sys.executable,'-I','-B',str(path),'produce'],env={},capture_output=True,text=True)
    assert result.returncode==2
    assert json.loads(result.stdout)==dict(state='WEEKLY_PREPARATION_ONLY_NO_IO',fits=0,public_release=False)
    assert not result.stderr


def test_operational_past_history_and_software_acceptance_have_distinct_purposes():
    from nfl_lab import audit_weekly_runtime_v1 as runtime
    config=dict(history_seasons=[2026],allowed_periods={'2026':[1,2,3,4,5,6]},
        freshness_seconds=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800))
    slate=dict(season=2026,week=7)
    with pytest.raises(runtime.RuntimeErrorCode,match='EARLY_HISTORY_ONLY_NO_PROTECTED_CONFIRMATION'):
        runtime.config_check(config,slate)
    config['purpose']='CURRENT_OPERATIONAL_INFERENCE'
    runtime.config_check(config,slate)
    # The unchanged E7 reader still applies the full-week kickoff+7day gate
    # before parquet values. This scope only admits prior-week requests.
    config['allowed_periods']['2026'].append(7)
    with pytest.raises(runtime.RuntimeErrorCode,match='EARLY_HISTORY_ONLY_NO_PROTECTED_CONFIRMATION'):
        runtime.config_check(config,slate)
    config['allowed_periods']['2026']=[6];config['purpose']='TUNING'
    with pytest.raises(runtime.RuntimeErrorCode,match='EXPLICIT_SOURCE_READ_PURPOSE'):
        runtime.config_check(config,slate)


def test_owned_worker_dies_when_its_parent_is_interrupted(tmp_path):
    import time
    child_code='from tools.audit_process_guard_v1 import arm_parent_death;from pathlib import Path;import os,sys,time;arm_parent_death();Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(20)'
    parent_code='import os,subprocess,sys,time;subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]],env=dict(os.environ,AUDIT_WEEKLY_PARENT_PID=str(os.getpid())));time.sleep(20)'
    marker=tmp_path/'owned-pid'
    parent=subprocess.Popen([sys.executable,'-c',parent_code,child_code,str(marker)],cwd=hosted.ROOT)
    child_pid=None
    try:
        deadline=time.monotonic()+5
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert marker.exists(),'owned child did not start'
        child_pid=int(marker.read_text());assert child_pid!=parent.pid
        parent.kill();parent.wait(timeout=5)
        def alive():
            stat=Path(f'/proc/{child_pid}/stat')
            return stat.exists() and stat.read_text().rsplit(') ',1)[1].split()[0] not in {'Z','X'}
        deadline=time.monotonic()+5
        while alive() and time.monotonic()<deadline:time.sleep(.02)
        assert not alive(),'owned child survived parent interruption'
    finally:
        if parent.poll() is None:parent.kill();parent.wait(timeout=5)


def test_early_failed_attempt_is_recoverable_failure_evidence_in_fresh_process(tmp_path):
    # Real owned filesystem/CAS and original failure codec, injected append only.
    # A newly loaded JSON status cannot authorize a successful forecast.
    r=object.__new__(hosted.Runner);r.root=tmp_path/'attempt';r.root.mkdir()
    r.storage=OperationalStorage(r.root/'cache',Path(hosted.ROOT)/'config/operational-source-policy-v2.json',state=r.root/'state')
    r.storage.register_root(r.root)
    r.go_sha='a'*64;r.go=dict(qualified_runtime=dict(binding=dict(runtime_id='b'*32),qualification=dict()))
    r.root_ref=hosted.write(r.storage,r.root/'OWNER_ROOT.json',dict(fictional_root=True))
    r.identity=dict(repository=store.REPO,run_id='49900000000',run_attempt=1,source_sha='c'*40,
        job_id=hosted.JOBS['produce'],workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/fictional')
    r.started=hosted.now_utc()-timedelta(seconds=2);r.env=dict(GITHUB_OUTPUT=str(tmp_path/'output'))
    (tmp_path/'output').touch()
    hosted.write(r.storage,r.root/'phase-status'/'01-source.json',dict(state='FAILED_RETAINED',reason='FICTIONAL_SOURCE_UNAVAILABLE',successful_forecast=False))
    hosted.write(r.storage,r.root/'journal'/'one.reservation.json',dict(schema_version='weekly-private-POST-reservation-v2',key='fictional',bytes=7,sha256='d'*64,name='fictional'))
    observed={}
    def append(client,storage,output,**kwargs):
        request,bodies=failure.unpack((output/'FAILURE.json.gz').read_bytes())
        attachments={item['label']:body for item,body in zip(request['attachments'],bodies)}
        assert request['failure']['exit_code']==1 and request['state']=='FAILED'
        assert set(attachments)=={'file-graph','owner-root','original-post-reservations','phase-00'}
        assert b'FICTIONAL_SOURCE_UNAVAILABLE' in attachments['phase-00']
        assert b'one.reservation.json' in attachments['original-post-reservations']
        assert kwargs['inputs']['payload_manifest']==store.canonical(failure.payload_manifest((output/'FAILURE.json.gz').read_bytes()))
        observed['package']=output/'FAILURE.json.gz'
        return dict(descriptor=dict(fictional=True))
    with patch.object(r,'failure_client',return_value=object()),patch.object(r,'operation_go',return_value=dict()),patch.object(failure,'append_failure',side_effect=append):
        result=r.preserve_failure()
    assert result['successful_forecast'] is result['public_release'] is False
    script='from pathlib import Path;from nfl_lab.operational_failure_v1 import unpack;import json,sys; r,a=unpack(Path(sys.argv[1]).read_bytes());print(json.dumps(dict(state=r["state"],files=len(a))))'
    out=subprocess.run([sys.executable,'-c',script,str(observed['package'])],cwd=hosted.ROOT,capture_output=True,text=True,check=True)
    assert json.loads(out.stdout)==dict(state='FAILED',files=4)
    with pytest.raises(store.StoreError,match='FAILED_ATTEMPT_PRESERVATION_ALREADY_CONSUMED'):
        r.preserve_failure()
