"""One bounded excluded-source absence check; no outcomes, fits or writes."""
from pathlib import Path
import os,json,hashlib,resource,signal,time,io
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','ARROW_NUM_THREADS','ARROW_IO_THREADS'):
    os.environ[key]='1'
root=Path('/workspace/nfl-methods-integration')
p=root/'config/next-checkpoint-common2025-snap-admission-v1.json';raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='8999784c3a8ecaf355ca81fb2fad58dc36c19dcecd2dd5b07a6622a82ef441b9'
plan=json.loads(raw);cpu=time.process_time();wall=time.monotonic()
resource.setrlimit(resource.RLIMIT_CPU,(10,11))
signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('15ssourcegate')));signal.alarm(15)
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
pa.set_cpu_count(1);pa.set_io_thread_count(1)
summary={};passed=True
for name,ref in plan['inputs'].items():
    path=Path(ref['path']);assert path.resolve()==path
    body=path.read_bytes();assert len(body)==ref['bytes'] and hashlib.sha256(body).hexdigest()==ref['sha256']
    frame=pq.read_table(io.BytesIO(body),columns=plan['columns'],filters=[tuple(f) for f in plan['predicates'][name]])
    cols={}
    for col in plan['columns']:
        a=frame[col].to_numpy(zero_copy_only=False).astype(float)
        finite=np.isfinite(a);disallowed=finite & (np.ones(len(a),dtype=bool) if '_mean' in col else a!=0)
        cols[col]={'rows':len(a),'null_or_nonfinite':int((~finite).sum()),'finite_zero':int((finite&(a==0)).sum()),'disallowed_values':int(disallowed.sum())}
        passed &= not bool(disallowed.any())
    summary[name]={'source_sha256':ref['sha256'],'columns':cols}
use={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
assert use['CPU_seconds']<=10 and use['wall_seconds']<=15 and use['RSS_bytes']<=256*1024**2
signal.alarm(0)
print(json.dumps({'state':'PASS_EXCLUDED_SNAP_CHANNELS_UNAVAILABLE' if passed else 'BLOCKED_EXCLUDED_SNAP_SOURCE_NOT_RESOLVED','plan_sha256':hashlib.sha256(raw).hexdigest(),'sources':summary,'resources':use,'fits':0,'outcome_column_decodes':0,'HTTP':0,'old_studies_unchanged':True},sort_keys=True))
