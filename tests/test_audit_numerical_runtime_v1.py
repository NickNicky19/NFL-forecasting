"""Fictional bad metadata + fresh real numerical startup; no models/fits/HTTP."""
from copy import deepcopy
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from nfl_lab import audit_numerical_runtime_v1 as n

ROOT=Path(__file__).resolve().parents[1]
CPU="processor : 0\nflags : sse sse2 sse3 avx avx2 fma\n\nprocessor : 1\nflags : sse sse2 sse3 avx avx2 fma\n"


class RequiredOnly:
    """Any access to unrelated/private environment fails the test."""
    def get(self,key):
        assert key in n.ENVIRONMENT,"UNRELATED_OR_CREDENTIAL_ENV_READ"
        return n.ENVIRONMENT[key]
    def __iter__(self):
        pytest.fail("FULL_ENVIRONMENT_ENUMERATION_FORBIDDEN")


def fresh(script, *, startup=True):
    # Explicit public startup keys only; never copy/read the private environment.
    env={"PATH":os.defpath,"PYTHONDONTWRITEBYTECODE":"1"}
    env.update(n.ENVIRONMENT)
    if not startup:
        env.pop("NPY_DISABLE_CPU_FEATURES")
        env.pop("OPENBLAS_CORETYPE")
    return subprocess.run([sys.executable,"-B","-c",script],cwd=ROOT,env=env,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=45)


@pytest.fixture
def copy_root(tmp_path):
    for name in [n.CONFIG]+["nfl_lab/"+name for name in n.MODEL_CODE]:
        out=tmp_path/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,out)
    return tmp_path


def edit(root,change):
    path=root/n.CONFIG;p=json.loads(path.read_bytes());change(p);path.write_bytes(n.canonical(p))


def test_preflight_pure_metadata_no_numeric_import_and_no_credentials():
    script=r'''
import sys,json
from pathlib import Path
from nfl_lab import audit_numerical_runtime_v1 as n
class Env:
 def get(self,key):
  assert key in n.ENVIRONMENT
  return n.ENVIRONMENT[key]
 def __iter__(self):raise AssertionError("NO_PRIVATE_ENV_ENUMERATION")
r=n.preflight(Path.cwd(),Env())
assert not any(x in sys.modules for x in ("numpy","scipy","pandas","sklearn","catboost","joblib"))
assert r["execution_authorized"] is r["forecast_release"] is False
assert r["configuration_id"]=="effective18-haswell-numpy-generic-v1"
print(json.dumps(dict(state="PASS_STDLIB_PREFLIGHT",configuration_id=r["configuration_id"],config_sha256=r["config_sha256"],cpu_count=r["cpu_count"])))
'''
    result=fresh(script)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)["state"]=="PASS_STDLIB_PREFLIGHT"


def test_required_env_only_public_safe_receipt():
    result=n.preflight(ROOT,RequiredOnly(),cpuinfo=CPU)
    assert result["cpu_count"]==2 and result["env_sha256"]==n.sha(n.canonical(n.ENVIRONMENT))
    assert all(len(result[k])==64 for k in ("config_sha256","cpu_flags_sha256","model_code_pins_sha256"))
    assert "OPENBLAS_CORETYPE" not in result and "owner_authorization" not in result
    assert result["original_expected_bits_sha256"]==n.ORIGINAL_BITS_SHA256


@pytest.mark.parametrize("key",sorted(n.ENVIRONMENT))
def test_every_original_or_new_startup_control_is_required(key):
    env=dict(n.ENVIRONMENT);env[key]="FICTIONAL_WRONG"
    with pytest.raises(n.NumericalRuntimeError,match="NUMERICAL_REQUIRED_STARTUP_ENVIRONMENT_MISMATCH"):
        n.preflight(ROOT,env,cpuinfo=CPU)


@pytest.mark.parametrize("bad",[
    "processor: 0\nflags: avx2\n",
    "processor: 0\nflags: fma\n",
    "processor: 0\nflags: avx2 fma\n\nprocessor: 1\nflags: avx2\n",
    "processor: 0\nflags: avx2 fma\n\nprocessor: 0\nflags: avx2 fma\n",
    "processor: 0\nflags: avx2 fma\nflags: avx2 fma\n",
    "model name: fictional\n",
])
def test_all_CPU_records_qualified_or_fail_before_heavy_imports(bad):
    script='''
import sys,json
from pathlib import Path
from nfl_lab import audit_numerical_runtime_v1 as n
try:n.preflight(Path.cwd(),n.ENVIRONMENT,cpuinfo=%r)
except n.NumericalRuntimeError:pass
else:raise AssertionError("UNQUALIFIED_CPU_ACCEPTED")
assert "numpy" not in sys.modules and "scipy" not in sys.modules
print('{"state":"PASS_CPU_REJECTED_BEFORE_IMPORT"}')
'''%bad
    result=fresh(script)
    assert result.returncode==0,result.stderr


def test_non_linux_or_non_x86_rejected_before_imports(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(n.os,"uname",lambda:SimpleNamespace(sysname="Linux",machine="aarch64"))
    with pytest.raises(n.NumericalRuntimeError,match="NUMERICAL_LINUX_X86_64_REQUIRED"):
        n.preflight(ROOT,n.ENVIRONMENT,cpuinfo=CPU)


@pytest.mark.parametrize("change",[
    lambda p:p.update(execution_authorized=True),
    lambda p:p.update(numerical_configuration_id="FICTIONAL_OTHER"),
    lambda p:p["environment"].update(OPENBLAS_CORETYPE="SkylakeX"),
    lambda p:p["package_versions"].update(numpy="0.0"),
    lambda p:p["original_expected_replay_sha256"].update({"rush_att/COUNT_A":"0"*64}),
    lambda p:p.update(expected_bits_edits=True),
])
def test_closed_profile_and_original_replay_bits_cannot_change(copy_root,change):
    edit(copy_root,change)
    with pytest.raises(n.NumericalRuntimeError):
        n.preflight(copy_root,n.ENVIRONMENT,cpuinfo=CPU)


def test_code_pin_change_and_version_metadata_mismatch_fail(copy_root,monkeypatch):
    path=copy_root/"nfl_lab/cdf_engine.py";path.write_bytes(path.read_bytes()+b"\n# FICTIONAL mutation\n")
    with pytest.raises(n.NumericalRuntimeError,match="NUMERICAL_ORIGINAL_MODEL_CODE_PIN_CHANGED"):
        n.preflight(copy_root,n.ENVIRONMENT,cpuinfo=CPU)
    monkeypatch.setattr(n.importlib.metadata,"version",lambda _: "0.0")
    with pytest.raises(n.NumericalRuntimeError,match="NUMERICAL_PACKAGE_VERSION_MISMATCH"):
        n.preflight(ROOT,n.ENVIRONMENT,cpuinfo=CPU)


def test_oversize_config_rejected(copy_root):
    path=copy_root/n.CONFIG;path.write_bytes(b" "*32769)
    with pytest.raises(n.NumericalRuntimeError,match="NUMERICAL_METADATA_OR_SOURCE_BOUND"):
        n.preflight(copy_root,n.ENVIRONMENT,cpuinfo=CPU)


def test_loaded_real_numpy_scipy_generic_dispatch_Haswell_and_process_free_threads():
    script=r'''
import sys,os,json
from pathlib import Path
from nfl_lab import audit_numerical_runtime_v1 as n
n.preflight(Path.cwd(),os.environ)
def deny(event,args):
 if event.startswith(("subprocess.","socket.")) or event in {"os.fork","os.forkpty","os.exec","os.posix_spawn","os.system"}:
  raise AssertionError("NO_HTTP_OR_SUBPROCESS_LOOKUPS")
sys.addaudithook(deny)
r=n.loaded(Path.cwd(),os.environ)
assert r["actual_versions"]=={"numpy":"2.3.5","scipy":"1.17.0"}
assert r["numpy_dispatch"] and all(v is False for v in r["numpy_dispatch"].values())
pools={p["origin"]:p for p in r["threadpools"] if p["origin"] in {"numpy","scipy"}}
assert set(pools)=={"numpy","scipy"}
assert all(p["architecture"]=="Haswell" and 1<=p["num_threads"]<=2 for p in pools.values())
assert not any("filepath" in p or "prefix" in p for p in r["threadpools"])
assert r["execution_authorized"] is r["forecast_release"] is False
print(json.dumps(dict(state="PASS_ACTUAL_LOADED_NUMERICS",configuration_id=r["configuration_id"],numpy_dispatch=r["numpy_dispatch"],threadpools=r["threadpools"])))
'''
    result=fresh(script)
    assert result.returncode==0,result.stderr
    doc=json.loads(result.stdout);assert doc["state"]=="PASS_ACTUAL_LOADED_NUMERICS"


def test_fake_postimport_environment_cannot_relabel_default_numpy():
    script=r'''
import numpy,os,json
from pathlib import Path
from nfl_lab import audit_numerical_runtime_v1 as n
assert any(numpy._core._multiarray_umath.__cpu_features__.get(x) is True for x in numpy._core._multiarray_umath.__cpu_dispatch__)
os.environ.update(n.ENVIRONMENT)
try:n.loaded(Path.cwd(),os.environ)
except n.NumericalRuntimeError as e:
 assert "ACTUAL_NUMPY_DISPATCH_NOT_DISABLED" in str(e)
else:raise AssertionError("POSTIMPORT_ENV_FLAGS_FAKELY_QUALIFIED")
print('{"state":"PASS_LATE_ENV_REJECTED"}')
'''
    result=fresh(script,startup=False)
    assert result.returncode==0,result.stderr


def test_loaded_does_not_repair_actual_over_threaded_pool():
    script=r'''
import os,json,threadpoolctl,numpy,scipy.linalg
from pathlib import Path
from nfl_lab import audit_numerical_runtime_v1 as n
from tools.ngboost_law_software_v1 import process_free_threads
with process_free_threads(threadpoolctl,n._libc()),threadpoolctl.threadpool_limits(limits=3):
 try:n.loaded(Path.cwd(),os.environ)
 except n.NumericalRuntimeError as e:assert "ACTUAL_THREAD_COUNT_EXCEEDS_TWO" in str(e)
 else:raise AssertionError("TEMPORARY_LIMIT_HID_ACTUAL_THREE_THREADS")
print('{"state":"PASS_ACTUAL_THREE_THREADS_REJECTED"}')
'''
    result=fresh(script)
    assert result.returncode==0,result.stderr

