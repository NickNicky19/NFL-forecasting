"""A real cold metadata process must fit the unchanged native envelope."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_metadata_composition_imports_before_private_work_within_native_cap():
    root=Path(__file__).resolve().parents[1]
    profile=json.loads((root/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())
    env={k:os.environ[k] for k in ("PATH","LANG","LC_ALL","TZ") if k in os.environ}
    env.update(profile["environment"])
    script='''import json,resource,signal,sys
sys.path.insert(0,sys.argv[1])
resource.setrlimit(resource.RLIMIT_CPU,(120,120))
resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)
def deny(event,unused):
 if event.startswith(("socket.","subprocess.")) or event in {"os.system","os.fork","os.forkpty","os.exec","os.posix_spawn"}:
  raise RuntimeError("METADATA_IMPORT_HAS_NO_EXTERNAL_EXECUTION")
sys.addaudithook(deny)
from nfl_lab import audit_weekly_grade_v1,audit_weekly_operations_v1,audit_weekly_hosted_v1
from nfl_lab import audit_weekly_provider_v1,audit_weekly_operations_grade_v1
from pathlib import Path
metrics={row.partition(':')[0]:row.partition(':')[2].strip() for row in Path('/proc/self/status').read_text().splitlines() if row.partition(':')[0] in {'VmPeak','VmSize'}}
print(json.dumps(dict(state='NATIVE_METADATA_IMPORT_COMPLETE',metrics=metrics,unneeded_models_loaded=any(x in sys.modules for x in ('numpy','pandas','pyarrow','sklearn','scipy','catboost')))))
'''
    result=subprocess.run([sys.executable,"-I","-B","-c",script,str(root)],env=env,
        capture_output=True,text=True,timeout=190)
    assert result.returncode==0,(result.returncode,result.stderr)
    summary=json.loads(result.stdout)
    assert summary["state"]=="NATIVE_METADATA_IMPORT_COMPLETE"
    assert summary["unneeded_models_loaded"] is False
    assert all(int(value.split()[0])*1024<=512<<20 for value in summary["metrics"].values())
