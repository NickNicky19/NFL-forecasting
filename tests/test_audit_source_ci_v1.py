"""Tiny fictional pytest projects only; no numerical fits or remote actions."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from tools import audit_source_ci_v1 as ci

TOOL = Path(ci.__file__).resolve()
NEEDS = {"collect":{"result":"success"}, "shards":{"result":"success"}}
ATTEMPT = os.environ.get("GITHUB_RUN_ATTEMPT", "1")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,"connect",lambda *_:pytest.fail("NO_NETWORK_IN_CI_HELPER_TEST"))


def command(project, *args, timeout=12, extra_env=None):
    public = ("PATH","LANG","LC_ALL","TZ","GITHUB_REPOSITORY","GITHUB_SHA","GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT")
    env = {key:os.environ[key] for key in public if key in os.environ}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
    if extra_env:env.update(extra_env)
    return subprocess.run([sys.executable,"-B",str(TOOL),*map(str,args)],cwd=project,env=env,
        capture_output=True,text=True,timeout=timeout)


def finalized(project, root, phase, shard=None, seconds=8):
    name = f"audit-source-ci-collection-{ATTEMPT}" if shard is None else f"audit-source-ci-shard-{shard}-{ATTEMPT}"
    out = root/name
    args = [phase,"--output",out,"--seconds",seconds]
    if shard is not None:args += ["--shard",shard]
    result = command(project,*args)
    status = "success" if result.returncode==0 else "failure"
    finish = command(project,"finish","--output",out,"--step-status",status,"--job-status",status)
    assert finish.returncode==0,finish.stderr
    return out,result


@pytest.fixture(scope="module")
def successful_attempt(tmp_path_factory):
    project=tmp_path_factory.mktemp("fictional-source-ci")
    package=project/"tiny_local_package";package.mkdir();(package/"__init__.py").write_text("VALUE=7\n")
    (project/"test_small.py").write_text('''import pytest
from tiny_local_package import VALUE
@pytest.mark.parametrize('value',[0,1])
def test_pass(value): assert value in range(4) and VALUE==7
''')
    (project/"test_other.py").write_text('''import pytest
@pytest.mark.parametrize('value',[2,3])
def test_pass(value): assert value in range(4)
''')
    (project/"test_existing.py").write_text('''import pytest
@pytest.mark.skip(reason='existing explicit fixture skip')
def test_existing_skip(): raise AssertionError('never executed')
@pytest.mark.xfail(reason='existing expected failure',strict=True)
def test_existing_xfail(): assert False
''')
    (project/"test_more.py").write_text('''
def test_more_a(): assert True
def test_more_b(): assert True
''')
    root=project/"artifacts";root.mkdir()
    for phase,shard in [("collect",None)]+[("run",i) for i in range(4)]:
        _,result=finalized(project,root,phase,shard)
        assert result.returncode==0,(result.stdout,result.stderr)
    return project,root


def test_real_four_shards_independently_collect_and_cover_every_node_once(successful_attempt):
    _,root=successful_attempt
    result=ci.verify(root,NEEDS,ATTEMPT)
    assert result["collected"]==result["attempted"]==result["completed"]==8
    assert result["outcome_counts"]==dict(passed=6,skipped=1,xfailed=1)
    assert len(result["explicit_skips"])==2
    assert any("existing explicit fixture skip" in value for value in result["explicit_skips"].values())
    all_nodes=[]
    module_owners={}
    for i in range(4):
        r=ci.read(root/f"audit-source-ci-shard-{i}-{ATTEMPT}"/"receipt.json")
        assert len(r["collection"]["nodes"])==8 and len(r["attempted"])==2
        for node in r["attempted"]:
            module=node.split("::",1)[0]
            assert module not in module_owners or module_owners[module]==i
            module_owners[module]=i
        all_nodes+=r["attempted"]
    assert len(all_nodes)==len(set(all_nodes))==8


@pytest.mark.parametrize("damage",["missing_artifact","extra_artifact","duplicate_attempt","missing_attempt",
    "missing_completed","failed_outcome","different_collection","different_source","different_attempt",
    "worker_failed","job_failed","receipt_only_claim","missing_phase","upstream_failed","upstream_cancelled"])
def test_coverage_rejects_omissions_duplicates_partial_status_and_invented_receipts(tmp_path,successful_attempt,damage):
    _,original=successful_attempt;root=tmp_path/"artifacts";shutil.copytree(original,root)
    shard=root/f"audit-source-ci-shard-0-{ATTEMPT}"
    r=ci.read(shard/"receipt.json");node=r["attempted"][0];needs=deepcopy(NEEDS)
    if damage=="missing_artifact":shutil.rmtree(shard)
    elif damage=="extra_artifact":shutil.copytree(shard,root/"unexpected-copy")
    elif damage=="different_collection":
        c=ci.read(shard/"collection.json");c["nodes"][0]+="-not-original";c["nodes_sha256"]=ci.digest(c["nodes"]);ci.save(shard/"collection.json",c)
    elif damage=="different_source" or damage=="different_attempt":
        m=ci.read(shard/"run.json");m["identity"]["GITHUB_SHA" if damage=="different_source" else "GITHUB_RUN_ATTEMPT"]="OTHER";ci.save(shard/"run.json",m)
    elif damage=="worker_failed":ci.save(shard/"worker.json",dict(exit_code=1,finished_at=ci.stamp()))
    elif damage=="job_failed":r["job_status"]="failure";ci.save(shard/"receipt.json",r)
    elif damage=="receipt_only_claim":r["attempted"]=[];ci.save(shard/"receipt.json",r)
    elif damage.startswith("upstream_"):needs["shards"]["result"]=damage.removeprefix("upstream_")
    else:
        rows=ci.events(shard)
        if damage=="duplicate_attempt":rows.append(dict(type="attempted",nodeid=node))
        if damage=="missing_attempt":rows=[e for e in rows if not(e["type"]=="attempted" and e["nodeid"]==node)]
        if damage=="missing_completed":rows=[e for e in rows if not(e["type"]=="completed" and e["nodeid"]==node)]
        if damage=="failed_outcome":
            for e in rows:
                if e["type"]=="completed" and e["nodeid"]==node:e["outcome"]="failed"
        if damage=="missing_phase":rows=[e for e in rows if not(e["type"]=="report" and e["nodeid"]==node and e["when"]=="teardown")]
        (shard/"events.jsonl").write_bytes(b"".join(ci.canonical(e)+b"\n" for e in rows))
    if damage not in {"missing_artifact","extra_artifact","receipt_only_claim"}:
        ci.materialize(shard)
    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):ci.verify(root,needs,ATTEMPT)
    assert {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}==before


def test_failure_and_setup_error_diagnostics_are_immediate_and_bounded(tmp_path):
    (tmp_path/"test_a.py").write_text("def test_failure():\n print('NATIVE_CAPACITY_STAGE_DIAGNOSTIC')\n raise AssertionError('CALL_FAILURE_DIAGNOSTIC'+'x'*20000)\n")
    (tmp_path/"test_b.py").write_text('''import pytest
@pytest.fixture
def broken(): raise ValueError('SETUP_FAILURE_DIAGNOSTIC')
def test_b(broken): pass
''')
    (tmp_path/"test_c.py").write_text("def test_pass(): assert True\n")
    (tmp_path/"test_d.py").write_text("def test_pass(): assert True\n")
    for i in range(4):
        out,result=finalized(tmp_path,tmp_path/"artifacts","run",i)
        r=ci.read(out/"receipt.json")
        assert r["attempted"]==r["completed"] and len(r["attempted"])==1
        if i<2:
            assert result.returncode==1 and "SOURCE_CI_FAILURE" in result.stdout
            assert list(r["outcomes"].values())==["failed"]
            messages=[e["message"] for e in ci.events(out) if e["type"]=="diagnostic"]
            assert 0<sum(map(len,messages))<=ci.DIAGNOSTIC_CAP
            if i==0:assert any('NATIVE_CAPACITY_STAGE_DIAGNOSTIC' in message for message in messages)
        else:assert result.returncode==0


def test_timeout_retains_started_node_and_prior_failure_in_durable_receipt(tmp_path):
    (tmp_path/"test_stop.py").write_text('''import time
def test_0(): raise AssertionError('FAILURE_BEFORE_TIMEOUT')
def test_1(): pass
def test_2(): pass
def test_3(): pass
def test_4(): time.sleep(20)
''')
    out,result=finalized(tmp_path,tmp_path/"artifacts","run",0,seconds=1.8)
    r=ci.read(out/"receipt.json")
    assert result.returncode==124 and r["state"]=="TIMED_OUT"
    assert len(r["attempted"])==5 and len(r["completed"])==4
    assert "SOURCE_CI_FAILURE" in result.stdout and "FAILURE_BEFORE_TIMEOUT" in result.stdout
    assert list(r["outcomes"].values()).count("failed")==1 and r["worker"] is None


@pytest.mark.parametrize("selection",["-k test_pass","--ignore=test_small.py","--deselect=test_small.py::test_more_a"])
def test_no_environment_selection_can_silently_reduce_full_collection(tmp_path,successful_attempt,selection):
    project,_=successful_attempt
    result=command(project,"collect","--output",tmp_path/"receipt","--seconds",8,extra_env={"PYTEST_ADDOPTS":selection})
    assert result.returncode!=0


def test_collection_errors_are_recorded_before_exit(tmp_path):
    (tmp_path/"test_invalid.py").write_text("def broken syntax\n")
    out,result=finalized(tmp_path,tmp_path/"artifacts","collect")
    r=ci.read(out/"receipt.json")
    assert result.returncode!=0 and r["collection_errors"]
    assert "SOURCE_CI_COLLECTION_ERROR" in result.stdout and not r["attempted"]


def test_failed_coverage_cli_writes_durable_rejection_receipt(tmp_path):
    result=command(tmp_path,"verify","--artifacts",tmp_path/"missing","--output",tmp_path/"coverage.json",
        extra_env={"AUDIT_SOURCE_CI_NEEDS_JSON":json.dumps(NEEDS)})
    assert result.returncode==1
    assert ci.read(tmp_path/"coverage.json")["state"]=="COVERAGE_REJECTED"


def test_full_oversized_nodeids_and_module_fixture_are_preserved_with_empty_shards(tmp_path):
    (tmp_path/"test_large_id.py").write_text('''from pathlib import Path
import pytest
@pytest.fixture(scope='module',autouse=True)
def once():
 p=Path('module-setup-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
@pytest.mark.parametrize('n',[1,2],ids=['ordinary','z'*300000])
def test_parameter(n): assert n in (1,2)
''')
    root=tmp_path/"artifacts";root.mkdir()
    for phase,shard in [("collect",None)]+[("run",i) for i in range(4)]:
        out,result=finalized(tmp_path,root,phase,shard)
        assert result.returncode==0,(result.stdout[-1000:],result.stderr)
        if phase=="run":
            assert max(map(len,result.stdout.splitlines()),default=0)<2000
    assert (tmp_path/"module-setup-count").read_text()=="1"
    assert ci.verify(root,NEEDS,ATTEMPT)["completed"]==2
    nodes=ci.read(root/f"audit-source-ci-collection-{ATTEMPT}"/"collection.json")["nodes"]
    assert max(map(len,nodes))>300000
    for i in (1,2,3):
        assert ci.read(root/f"audit-source-ci-shard-{i}-{ATTEMPT}"/"worker.json")["exit_code"]==5
