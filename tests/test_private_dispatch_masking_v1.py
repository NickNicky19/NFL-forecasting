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
    private = 'fictional-root%\r\n::error::must remain data'
    event = tmp_path / 'event.json'
    event.write_text(json.dumps({'inputs': {'inference_builder_go_json': private}}))
    output = io.StringIO()
    assert masking.main({'GITHUB_EVENT_PATH': str(event)}, output) == 0
    assert output.getvalue() == '::add-mask::fictional-root%25%0D%0A::error::must remain data\n'
    assert len(output.getvalue().splitlines()) == 1

@pytest.mark.parametrize('event', [{}, {'inputs': {}}, {'inputs': None}])
def test_non_dispatch_events_emit_no_input_or_environment(event, tmp_path):
    path = tmp_path / 'event.json'
    path.write_text(json.dumps(event))
    output = io.StringIO()
    assert masking.main({'GITHUB_EVENT_PATH': str(path)}, output) == 0
    assert output.getvalue() == ''

@pytest.mark.parametrize('body', [b'fictional private malformed JSON', b'x' * (masking.CAP + 1), json.dumps({'inputs': {'inference_builder_go_json': {'private': 'do not print'}}}).encode()])
def test_masking_failure_prints_only_a_fixed_code(body, tmp_path):
    event = tmp_path / 'event.json'
    event.write_bytes(body)
    result = subprocess.run([sys.executable, str(ROOT / 'tools/mask_dispatch_inputs.py')], env={'GITHUB_EVENT_PATH': str(event)}, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ''
    assert result.stderr == 'DISPATCH_INPUT_MASKING_FAILED\n'

def test_private_job_environment_is_absent_until_masking_has_completed():
    workflow = yaml.load((ROOT / '.github/workflows/lab.yml').read_bytes(), Loader=yaml.BaseLoader)
    for name, job in workflow['jobs'].items():
        if name not in {'audit-weekly-produce-v1', 'audit-weekly-restore-v1', 'audit-weekly-export-v1', 'audit-weekly-failure-restore-v1'}:
            continue
        assert not any(('inputs.' in value and ('_json' in value or '_JSON' in key) for key, value in job.get('env', {}).items())), name
        steps = job['steps']
        mask = [i for i, step in enumerate(steps) if step.get('run') == 'python3 tools/mask_dispatch_inputs.py']
        assert len(mask) == 1, name
        assert any((step.get('uses') == 'actions/checkout@v4' for step in steps[:mask[0]])), name
        for index, step in enumerate(steps):
            if any(('inputs.' in value and '_json' in value for value in step.get('env', {}).values())):
                assert index > mask[0], name
