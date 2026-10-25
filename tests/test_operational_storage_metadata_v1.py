"""Cold metadata storage retains native limits and CAS without numerical imports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def test_actual_native_cold_metadata_cas_blocks_pandas_and_numpy(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = '''import importlib.abc,json,resource,signal,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
resource.setrlimit(resource.RLIMIT_CPU,(120,120))
resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)
class NoNumerics(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'pandas','numpy','scipy','sklearn','catboost'}:
   raise AssertionError('NUMERICAL_IMPORT_FORBIDDEN:'+fullname)
sys.meta_path.insert(0,NoNumerics())
def deny(event,args):
 if event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.forkpty','os.exec','os.posix_spawn'}:
  raise AssertionError('NO_METADATA_EXTERNAL_EXECUTION')
sys.addaudithook(deny)
from nfl_lab import audit_weekly_parent_v1, audit_weekly_controller_bootstrap_v1
from nfl_lab.operational_storage import OperationalStorage,StorageIntegrityError,StorageQuotaError
root,work=map(Path,sys.argv[1:]);policy=json.loads((root/'config/operational-source-policy-v2.json').read_bytes())
policy['storage']['limit_bytes']=4096
owner=OperationalStorage(work/'cache',policy,state=work/'state')
owner.register_root(work/'metadata')
body=b'FICTIONAL original metadata retained'
first,second=work/'metadata/first.json',work/'metadata/second.json'
owner.write_bytes(first,body);before=owner.snapshot()['physical_bytes'];owner.write_bytes(second,body)
assert owner.snapshot()['physical_bytes']==before
assert first.stat().st_ino==second.stat().st_ino
ref=owner.validate_reference(first);assert ref['bytes']==len(body) and first.read_bytes()==body
try:owner.write_bytes(first,b'FICTIONAL overwrite forbidden',replace=True)
except StorageIntegrityError:pass
else:raise AssertionError('IMMUTABLE_CAS_REQUIRED')
try:owner.write_bytes(work/'metadata/overquota.json',b'FICTIONAL cannot fit'*4096)
except StorageQuotaError:pass
else:raise AssertionError('QUOTA_REQUIRED')
assert first.read_bytes()==second.read_bytes()==body
assert not (work/'metadata/overquota.json').exists()
assert not any(n.split('.')[0] in {'pandas','numpy','scipy','sklearn','catboost'} for n in sys.modules)
metrics={row.partition(':')[0]:row.partition(':')[2].strip() for row in Path('/proc/self/status').read_text().splitlines() if row.partition(':')[0] in {'VmPeak','VmSize'}}
print(json.dumps(dict(state='NATIVE_COLD_METADATA_CAS_OK',metrics=metrics,CPU_seconds=time.process_time(),peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
 CPU_limits=resource.getrlimit(resource.RLIMIT_CPU),AS_limits=resource.getrlimit(resource.RLIMIT_AS),wall_remaining_seconds=signal.getitimer(signal.ITIMER_REAL)[0])))
'''
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "TZ") if k in os.environ}
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(root), str(tmp_path)],
        env=env, capture_output=True, text=True, timeout=185)
    wall_seconds = time.monotonic() - started
    assert result.returncode == 0, (result.returncode, result.stderr)
    metrics = json.loads(result.stdout)
    assert metrics["state"] == "NATIVE_COLD_METADATA_CAS_OK"
    assert metrics["CPU_seconds"] < 120 and metrics["peak_RSS_bytes"] <= 512 << 20
    assert metrics["CPU_limits"] == [120, 120] and metrics["AS_limits"] == [512 << 20, 512 << 20]
    assert 0 < metrics["wall_remaining_seconds"] <= 180 and wall_seconds < 180
    assert all(int(value.split()[0]) * 1024 <= 512 << 20 for value in metrics["metrics"].values())
    print(json.dumps(dict(metrics, wall_seconds=wall_seconds), sort_keys=True))
