"""Combined workflow confidentiality and real cross-job grading dependencies."""
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from tools import mask_dispatch_inputs as masking

ROOT = Path(__file__).resolve().parents[1]


def test_actions_command_escape_does_not_emit_a_second_injected_command(tmp_path):
    private = "fictional-root%\r\n::error::must remain data"
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"inputs": {"inference_builder_go_json": private}}))
    output = io.StringIO()
    assert masking.main({"GITHUB_EVENT_PATH": str(event)}, output) == 0
    assert output.getvalue() == "::add-mask::fictional-root%25%0D%0A::error::must remain data\n"
    assert len(output.getvalue().splitlines()) == 1


@pytest.mark.parametrize("event", [{}, {"inputs": {}}, {"inputs": None}])
def test_non_dispatch_events_emit_no_input_or_environment(event, tmp_path):
    path = tmp_path / "event.json"; path.write_text(json.dumps(event))
    output = io.StringIO()
    assert masking.main({"GITHUB_EVENT_PATH": str(path)}, output) == 0
    assert output.getvalue() == ""


@pytest.mark.parametrize("body", [b"fictional private malformed JSON", b"x" * (masking.CAP + 1),
    json.dumps({"inputs": {"inference_builder_go_json": {"private": "do not print"}}}).encode()])
def test_masking_failure_prints_only_a_fixed_code(body, tmp_path):
    event = tmp_path / "event.json"; event.write_bytes(body)
    result = subprocess.run([sys.executable, str(ROOT / "tools/mask_dispatch_inputs.py")],
        env={"GITHUB_EVENT_PATH": str(event)}, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == "DISPATCH_INPUT_MASKING_FAILED\n"


def test_private_job_environment_is_absent_until_masking_has_completed():
    workflow = yaml.load((ROOT / ".github/workflows/lab.yml").read_bytes(), Loader=yaml.BaseLoader)
    for name in ("audit-weekly-produce-v1", "audit-weekly-restore-v1", "audit-weekly-export-v1", "audit-weekly-failure-restore-v1"):
        job = workflow["jobs"][name]
        assert not any("inputs." in value and ("_json" in value or "_JSON" in key)
            for key, value in job.get("env", {}).items()), name
        steps = job["steps"]
        mask = [i for i, step in enumerate(steps) if step.get("run") == "python3 tools/mask_dispatch_inputs.py"]
        assert len(mask) == 1, name
        assert any(step.get("uses") == "actions/checkout@v4" for step in steps[:mask[0]]), name
        for index, step in enumerate(steps):
            if any("inputs." in value and "_json" in value for value in step.get("env", {}).values()):
                assert index > mask[0], name


def test_current_weekly_steps_bind_the_actual_masked_root_and_grading_handoff():
    workflow = yaml.load((ROOT / ".github/workflows/lab.yml").read_bytes(), Loader=yaml.BaseLoader)
    for role in ("produce", "restore", "export", "failure-restore"):
        job = workflow["jobs"]["audit-weekly-" + role + "-v1"]
        for step in job["steps"]:
            if "tools/audit_weekly_hosted_v1.py" in step.get("run", ""):
                assert step["env"]["AUDIT_WEEKLY_ROOT_GO_JSON"] == "${{ inputs.inference_builder_go_json }}"
                assert step["env"]["AUDIT_WEEKLY_ROOT_GO_SHA256"] == "${{ inputs.inference_builder_go_sha256 }}"
    reader = workflow["jobs"]["audit-weekly-restore-v1"]
    assert reader["outputs"]["grade_checkpoint_handoff_json"] == "${{ steps.weekly.outputs.grade_checkpoint_handoff_json }}"
    exporter = workflow["jobs"]["audit-weekly-export-v1"]
    step = next(s for s in exporter["steps"] if s.get("id") == "weekly")
    assert step["env"]["AUDIT_WEEKLY_GRADE_HANDOFF_JSON"] == "${{ needs.audit-weekly-restore-v1.outputs.grade_checkpoint_handoff_json }}"
    assert step["env"]["AUDIT_WEEKLY_GRADE_HANDOFF_SHA256"] == "${{ needs.audit-weekly-restore-v1.outputs.grade_checkpoint_handoff_sha256 }}"


def test_grade_only_can_reach_existing_read_jobs_without_fabricating_archive_outputs():
    workflow=yaml.load((ROOT/'.github/workflows/lab.yml').read_bytes(),Loader=yaml.BaseLoader)
    jobs=workflow['jobs'];producer=jobs['audit-weekly-produce-v1'];reader=jobs['audit-weekly-restore-v1'];exporter=jobs['audit-weekly-export-v1']
    assert producer['outputs']['grade_only_plan_json']=='${{ steps.weekly.outputs.grade_only_plan_json }}'
    assert producer['outputs']['grade_only_plan_sha256']=='${{ steps.weekly.outputs.grade_only_plan_sha256 }}'
    for name in ('history_planning_json','history_planning_sha256'):
        assert producer['outputs'][name]=='${{ steps.weekly.outputs.'+name+' }}'
        for job in (reader,exporter):
            step=next(s for s in job['steps'] if s.get('id')=='weekly')
            assert step['env']['AUDIT_WEEKLY_'+name.upper()]=='${{ needs.audit-weekly-produce-v1.outputs.'+name+' }}'
    assert "needs.audit-weekly-produce-v1.outputs.grade_only_plan_json != ''" in reader['if']
    assert "needs.audit-weekly-produce-v1.outputs.grade_only_plan_json != '' && needs.audit-weekly-restore-v1.outputs.grade_checkpoint_handoff_json != ''" in exporter['if']
    assert "needs.audit-weekly-produce-v1.result == 'success'" in exporter['if']
    assert "needs.audit-weekly-restore-v1.result == 'success'" in exporter['if']
    for job in (producer,reader,exporter):
        assert job['permissions']==dict(contents='write',actions='read')
    assert reader['needs']=='audit-weekly-produce-v1'
    assert exporter['needs']==['audit-weekly-produce-v1','audit-weekly-restore-v1']


def test_runtime_inventory_covers_parent_and_grading_contracts_within_the_original_bound():
    from nfl_lab import audit_weekly_hosted_v1 as hosted, audit_weekly_parent_v1 as parent
    from nfl_lab import audit_weekly_grade_v1 as grade, audit_weekly_grade_checkpoint_v1 as checkpoint
    required=set(parent.REQUIRED_PINS)|set(grade.pins())|set(checkpoint.pins())
    assert required<=set(hosted.PINS)
    assert len(hosted.PINS)<=128
    # These tests are not executed by the production jobs. Full source CI
    # continues discovering them; moving them out of Root is not a CI filter.
    for name in hosted.CI_ONLY_QUALIFICATION_TESTS:
        assert (ROOT/name).is_file() and name not in hosted.PINS
    ci=yaml.load((ROOT/'.github/workflows/audit-source-checks.yml').read_bytes(),Loader=yaml.BaseLoader)
    assert ci['permissions']=={'contents':'read'} and 'schedule' not in ci['on']
    jobs=ci['jobs'];assert set(jobs)=={'collect','shards','offline'}
    assert jobs['shards']['strategy']=={'fail-fast':'false','max-parallel':'4','matrix':{'shard':['0','1','2','3']}}
    assert 'needs' not in jobs['shards']  # Independent full discovery even if the separate collector fails.
    assert jobs['offline']['needs']==['collect','shards'] and jobs['offline']['if']=='always()'
    for job in jobs.values():
        assert job['timeout-minutes']=='20' and 'continue-on-error' not in job
    for name,phase in [('collect','collect'),('shards','run')]:
        steps=jobs[name]['steps']
        run=next(step for step in steps if step.get('id')=='tests')
        assert f'tools/audit_source_ci_v1.py {phase} ' in run['run']
        assert '--seconds 960' in run['run']
        assert '-k ' not in run['run'] and '--ignore' not in run['run']
        r0=next(step for step in steps if step.get('with',{}).get('repository')=='NickNicky19/nicks-expert-nfl-picks')
        assert r0['with']['ref']=='89512ed952308dacc1f6a930915ddbcdccd460d9'
        assert r0['with']['persist-credentials']=='false'
        finish=next(step for step in steps if ' finish ' in step.get('run',''))
        assert finish['if']=='always()' and '--step-status "${{ steps.tests.outcome }}"' in finish['run']
        upload=next(step for step in steps if step.get('uses')=='actions/upload-artifact@v4')
        assert upload['if']=='always()' and upload['with']['if-no-files-found']=='error'
        assert '${{ github.run_attempt }}' in upload['with']['name']
    verify=next(step for step in jobs['offline']['steps'] if ' verify ' in step.get('run',''))
    assert verify['env']=={'AUDIT_SOURCE_CI_NEEDS_JSON':'${{ toJSON(needs) }}'}
    assert '--artifacts source-ci-evidence' in verify['run']
    from nfl_lab.audit_numerical_runtime_v1 import ENVIRONMENT
    assert ci['env']==ENVIRONMENT and len(ci['env'])==11
    assert 'tools/audit_source_ci_v1.py' not in hosted.PINS
    assert 'tests/test_audit_source_ci_v1.py' not in hosted.PINS
