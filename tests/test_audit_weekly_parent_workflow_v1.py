"""Lab-only routing: explicit request never substitutes for live qualification."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
import yaml

from nfl_lab import audit_weekly_parent_v1 as parent
from tools import hosted_safety_guard as guard
from test_audit_weekly_parent_v1 import case, locator_system, system, no_network

ROOT = Path(__file__).resolve().parents[1]


def workflow():
    return yaml.load((ROOT / ".github/workflows/lab.yml").read_bytes(), Loader=yaml.BaseLoader)


def steps():
    return {s.get("id", s.get("name", s.get("uses"))):s for s in workflow()["jobs"]["lab"]["steps"]}


def condition(expression, requested, outcome, *, due="true", mode="daily"):
    values = {"steps.parent_route.outputs.requested":requested, "steps.weekly_parent.outcome":outcome,
        "steps.parent_cadence.outputs.due":due, "steps.cadence.outputs.due":due,
        "steps.cadence.outputs.mode":mode, "steps.cadence.outcome":"success", "steps.readiness.outcome":"success"}
    source = expression.replace("always()", "True").replace("&&", " and ").replace("||", " or ")
    source = re.sub(r"steps\.[A-Za-z_][A-Za-z0-9_]*(?:\.outputs\.[A-Za-z_][A-Za-z0-9_]*|\.outcome)",
        lambda m:repr(values[m[0]]), source)
    return bool(eval(source, {"__builtins__":{}}, {}))


@pytest.mark.parametrize("enabled,event,mode,ref,expected", [
    ("", "schedule", "", "refs/heads/main", False),
    ("false", "workflow_dispatch", "daily", "refs/heads/main", False),
    ("TRUE", "schedule", "", "refs/heads/main", False),
    ("true", "schedule", "", "refs/heads/main", True),
    ("true", "workflow_dispatch", "daily", "refs/heads/main", True),
    ("true", "schedule", "", "refs/heads/research/weekly-storage-probe-v1", False),
    ("true", "workflow_dispatch", "daily", "refs/heads/research/weekly-storage-probe-v1", False),
    ("true", "push", "", "refs/heads/main", False),
    ("true", "workflow_dispatch", "train", "refs/heads/main", False),
    ("true", "workflow_dispatch", "grade", "refs/heads/main", False),
    ("true", "workflow_dispatch", "replay", "refs/heads/main", False),
    ("true", "workflow_dispatch", "audit-weekly-producer-v1", "refs/heads/main", False),
])
def test_actual_selector_is_disabled_by_default_and_main_daily_only(tmp_path, enabled, event, mode, ref, expected):
    step = steps()["parent_route"]
    assert step["env"] == {"PARENT_ENABLED":"${{ vars.AUDIT_WEEKLY_PARENT_ENABLED }}", "EVENT":"${{ github.event_name }}",
        "MODE":"${{ inputs.mode }}", "REF":"${{ github.ref }}"}
    output = tmp_path / "output"
    result = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path, capture_output=True, text=True, timeout=10, env={"PATH":os.defpath,
            "PYTHONDONTWRITEBYTECODE":"1", "GITHUB_OUTPUT":str(output), "PARENT_ENABLED":enabled,
            "EVENT":event, "MODE":mode, "REF":ref})
    assert result.returncode == 0, result.stderr
    assert output.read_text() == "requested=" + str(expected).lower() + "\n"
    assert result.stdout == "" and "ready" not in output.read_text()


def test_single_scheduler_mutex_permissions_budgets_and_no_lab_root_or_blanket_mask():
    wf = workflow(); lab = wf["jobs"]["lab"]; contract = parent.workflow_contract()
    assert wf["on"]["schedule"] == [{"cron":"36 12,13,14 * * *"}]
    assert wf["concurrency"] == {"group":"nfl-lab-single-writer", "cancel-in-progress":"false"}
    assert wf["permissions"] == {"contents":"write", "actions":"read"}
    assert lab["permissions"] == contract["required_job_permissions"]
    assert lab["timeout-minutes"] == "40" and "concurrency" not in lab
    assert not any(s.get("run") == "python3 tools/mask_dispatch_inputs.py" for s in lab["steps"])
    assert not ({"GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF", "AUDIT_WEEKLY_ROOT_GO_JSON"} & set(lab["env"]))
    for step in lab["steps"]:
        assert not any("_json" in value and "inputs." in value for value in step.get("env", {}).values())
    checkout = next(s for s in lab["steps"] if s.get("uses") == "actions/checkout@v4")
    assert checkout["with"] == {"ref":"${{ github.sha }}", "persist-credentials":"false", "fetch-depth":"0"}
    cli = steps()["weekly_parent"]
    assert cli["run"] == contract["step"]["run"]
    assert cli["if"] == contract["step"]["if"]
    assert cli["env"] == {"GITHUB_TOKEN":"${{ github.token }}"}
    assert "continue-on-error" not in cli
    cadence = steps()["parent_cadence"]["run"]
    assert "from nfl_lab.cadence import decision" in cadence
    assert "decision(os.environ['EVENT'],os.environ['MODE'] or None,policy=PARENT_POLICY)" in cadence
    legacy = steps()["cadence"]["run"]
    assert "decision(os.environ['EVENT'],os.environ['MODE'] or None)" in legacy and "policy=" not in legacy
    assert "steps.parent_cadence.outputs.mode" not in cli["if"]  # Sunday train label cannot select a fit.


def test_workflow_parent_contract_runs_with_metadata_lock_and_no_numerical_dependencies():
    install=steps()["Install exact metadata-only parent dependencies"]
    assert install["if"]=="steps.parent_route.outputs.requested == 'true'"
    assert install["run"].startswith("timeout 90s python -m pip install ")
    assert "--only-binary=:all:" in install["run"] and "--no-deps" in install["run"]
    assert install["run"].endswith("-r requirements-audit-weekly-metadata-v1.lock")
    assert (ROOT/"requirements-audit-weekly-metadata-v1.lock").read_text().splitlines()==["PyYAML==6.0.3"]
    script='''import contextlib,importlib.abc,io,json,resource,signal,sys
sys.path.insert(0,sys.argv[1]);sys.path.insert(1,sys.argv[2])
resource.setrlimit(resource.RLIMIT_CPU,(120,120))
resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)
class MetadataOnly(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if not fullname.startswith('_sysconfigdata_') and fullname.partition('.')[0] not in sys.stdlib_module_names|{'nfl_lab','tools','yaml'}:
   raise RuntimeError('PARENT_DEPENDENCY_NOT_IN_METADATA_LOCK:'+fullname)
sys.meta_path.insert(0,MetadataOnly())
def deny(event,args):
 if event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.exec','os.posix_spawn'}:
  raise RuntimeError('PARENT_METADATA_TEST_EXTERNAL_IO_FORBIDDEN')
sys.addaudithook(deny)
import yaml
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab import audit_weekly_grade_history_v1,state,weekly_durable_acceptance
from tools import audit_weekly_parent_v1 as cli
output=io.StringIO()
with contextlib.redirect_stdout(output):
 assert cli.main(['--contract'],environ={})==0
plan=json.loads(output.getvalue())
assert plan['default_POSTs']==0 and plan['limits']['address_space_bytes']==512<<20
assert plan['cadence']['policy_version']=='audit-weekly-parent-0736-v1'
print(json.dumps(dict(state='METADATA_LOCK_PARENT_CONTRACT_COMPLETE',yaml_version=yaml.__version__)))
'''
    result=subprocess.run([sys.executable,"-I","-S","-B","-c",script,str(ROOT),str(Path(yaml.__file__).parents[1])],
        capture_output=True,text=True,timeout=30,env={"PATH":os.defpath,"PYTHONDONTWRITEBYTECODE":"1"})
    assert result.returncode==0,(result.returncode,result.stderr)
    assert json.loads(result.stdout)==dict(state="METADATA_LOCK_PARENT_CONTRACT_COMPLETE",yaml_version="6.0.3")


@pytest.mark.parametrize("outcome", ["success", "failure", "skipped", "cancelled"])
def test_requested_route_cannot_fall_through_to_legacy_work(outcome):
    entries = steps()
    for name in ("acceptance", "cadence", "daily", "grading", "training", "replay",
        "Restore derived evidence state", "Persist only lab-derived forecasts and corrections", "Install exact tested dependencies"):
        assert not condition(entries[name]["if"], "true", outcome, mode="train"), name
    assert not condition(entries["readiness"]["if"], "true", outcome)
    assert condition(entries["parent_readiness_block"]["if"], "true", outcome) == (outcome != "success")
    assert condition(entries["Upload exact public-safe readiness receipt"]["if"], "true", outcome) == (outcome != "success")
    assert condition(entries["Upload public-safe parent enqueue status"]["if"], "true", outcome)


@pytest.mark.parametrize("mode,due,daily,grading,training", [
    ("daily","true",True,False,False), ("train","true",True,False,True),
    ("grade","true",False,True,False), ("replay","true",False,False,False),
    ("grade","false",False,True,False),
])
def test_unselected_legacy_conditions_and_commands_are_preserved(mode, due, daily, grading, training):
    entries = steps()
    assert condition(entries["readiness"]["if"], "false", "skipped")
    assert not condition(entries["weekly_parent"]["if"], "false", "skipped", due=due)
    for name, wanted in (("daily",daily), ("grading",grading), ("training",training)):
        assert condition(entries[name]["if"], "false", "skipped", due=due, mode=mode) == wanted
    assert entries["daily"]["run"] == "timeout 900 python -m nfl_lab.cli daily > daily-result.json"
    assert entries["grading"]["run"] == "timeout 300 python -m nfl_lab.cli grade > grading-result.json"
    assert entries["training"]["run"].splitlines() == ["timeout 300 python -m nfl_lab.cli acquire > acquire-result.json",
        "timeout 1200 python -m nfl_lab.cli experiment > experiment-result.json"]
    assert entries["replay"]["run"] == "python -m nfl_lab.cli replay"


def test_flag_and_count7_do_not_bypass_actual_parent_qualification_or_existing_guard(case):
    case.initial_only()
    with pytest.raises(parent.ParentError, match="SAME_SOURCE_OPS_CAPTURE_AND_CHECKPOINT_REQUIRED"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)
    assert case.service.dispatch_body is case.service.claim_body is None
    entries = steps()
    assert entries["parent_readiness_block"]["run"] == entries["readiness"]["run"]
    assert condition(entries["parent_readiness_block"]["if"], "true", "failure")
    receipt = guard.readiness(ROOT, repository=guard.REPOSITORY, source_commit="a"*40, run_id="100", run_attempt="1")
    assert receipt["exit_code"] == 78 and receipt["state"] == "BLOCKED_PENDING_QUALIFIED_HANDOVER"


def test_actual_same_source_ops_and_sidecar_success_returns_without_legacy_or_missing_receipt(case):
    result = case.execute()
    assert result["state"] == "ENQUEUE_ONCE_AND_EXIT" and result["dispatch_http_status"] == 204
    assert result["previous_checkpoint"] is not None and result["child_completion_claimed"] is False
    assert case.service.calls[-1].full_url == parent.DISPATCH_URL
    assert not condition(steps()["parent_readiness_block"]["if"], "true", "success")
    assert not condition(steps()["Upload exact public-safe readiness receipt"]["if"], "true", "success")
    upload = steps()["Upload public-safe parent enqueue status"]
    assert upload["with"]["path"] == "controller-parent-result.json"
    assert upload["with"]["if-no-files-found"] == "ignore"
