"""One identity-only diagnostic; never project target or action statistics."""
from pathlib import Path
import argparse
import datetime
import hashlib
import io
import json
import os
import resource
import signal
import sys
import time

VERSION='rec-tgt-identity-only-diagnostic-v3-20261029'
KEYS=['season','week','game_id','player_id']


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--go',required=True);a=p.parse_args()
    body=Path(a.plan).read_bytes();assert hashlib.sha256(body).hexdigest()==a.sha256;plan=json.loads(body)
    assert plan['version']==VERSION
    assert json.loads(Path(a.go).read_bytes())=={'state':'GO','root':'/root','scope':VERSION,'plan_sha256':a.sha256}
    out=Path(plan['output']);assert not out.exists();out.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU,(10,11));signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('15second metadata diagnostic')));signal.alarm(15)
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
    def deny(event,unused):
        if event.startswith('socket.') or event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn','pickle.find_class']:raise RuntimeError('offline childfree identityonly diagnostic')
    sys.addaudithook(deny)
    start,cpu=time.monotonic(),time.process_time();r={'state':'FAILED_RETAINED','version':VERSION,'NFL_stat_values_models_fits_forecasts_HTTP_CAS':0}
    (out/'CONSUMED.json').write_text(json.dumps({'at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':a.sha256,'one_attempt':True})+'\n')
    try:
        import pandas as pd,pyarrow as pa,pyarrow.parquet as pq,pyarrow.dataset as ds
        def auth(ref):
            b=Path(ref['path']).read_bytes();assert len(b)==ref['bytes'] and hashlib.sha256(b).hexdigest()==ref['sha256'];return b
        for ref in plan['source_pins'].values():auth(ref)
        inputs={k:auth(v) for k,v in plan['inputs'].items()}
        prior=json.loads(inputs['previous_failure']);assert prior['state']=='FAILED_RETAINED' and prior['error']=='complete canonical identity required'
        columns=KEYS+['team','position','opponent_team','season_type']
        d=ds.dataset(plan['inputs']['raw_weekly']['path'],format='parquet')
        raw=d.to_table(columns=columns,filter=(ds.field('season')==2026)&(ds.field('week')>=1)&(ds.field('week')<=7)&(ds.field('season_type')=='REG'),use_threads=False).to_pandas()
        q=pq.read_table(pa.BufferReader(inputs['query']),columns=KEYS+['team','opponent','position'],use_threads=False).to_pandas()
        source_required=KEYS+['team'];query_required=KEYS+['team','opponent','position']
        complete=raw[source_required].notna().all(axis=1)
        r.update(state='COMPLETE_IDENTITY_ONLY_DIAGNOSTIC',source_row_count=len(raw),query_row_count=len(q),source_identity_missing_counts={k:int(raw[k].isna().sum()) for k in source_required},query_context_missing_counts={k:int(q[k].isna().sum()) for k in query_required},source_unresolved_identity_rows=int((~complete).sum()),source_complete_identity_duplicate_rows=int(raw.loc[complete].duplicated(KEYS,keep=False).sum()),source_unresolved_identity_by_week={str(k):int(v) for k,v in raw.loc[~complete].groupby('week').size().items()},projected_columns={'raw':columns,'query':KEYS+['team','opponent','position']},source_weekly_target_or_action_stat_values_read=False,prior_failed_qualification_preserved=True)
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=plan['resources']['RSS_bytes']
    except BaseException as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        signal.alarm(0);r['terminal_at_UTC']=datetime.datetime.now(datetime.timezone.utc).isoformat();r['actual']={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};b=(json.dumps(r,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();assert len(b)<=16384;(out/'RESULT.json').write_bytes(b);print(json.dumps({'state':r['state'],'actual':r['actual']}))


if __name__=='__main__':main()
