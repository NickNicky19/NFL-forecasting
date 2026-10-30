"""One portable source/fictional check; no NFL source or model is loaded."""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import resource
import signal
import sys
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--plan',required=True)
    p.add_argument('--sha256',required=True)
    args=p.parse_args()
    body=Path(args.plan).read_bytes()
    assert hashlib.sha256(body).hexdigest()==args.sha256
    plan=json.loads(body)
    assert plan['version']=='rec-tgt-source-fictional-v1' and plan['attempts']==1
    out=Path(plan['output'])
    assert not out.exists()
    out.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU,(20,21))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('30second source fixture')))
    signal.alarm(30)
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
        os.environ[name]='1'
    def deny(event,unused):
        if event.startswith('socket.') or event in ['subprocess.Popen','os.fork','os.system','os.posix_spawn','pickle.find_class']:
            raise RuntimeError('source fixture excludes network, children and deserialization')
    sys.addaudithook(deny)
    start,cpu=time.monotonic(),time.process_time()
    result={'state':'FAILED_RETAINED','version':plan['version'],'NFL_models_fits_forecasts_CAS_HTTP':0,'automatic_retry':False}
    (out/'CONSUMED.json').write_text(json.dumps({'state':'ONE_SOURCE_CHECK_ATTEMPT_CONSUMED','plan_sha256':args.sha256})+'\n')
    try:
        for ref in plan['sources'].values():
            raw=Path(ref['path']).read_bytes()
            assert len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
        for key in ['module','pilot_worker','qualification_worker']:
            text=Path(plan['sources'][key]['path']).read_text()
            assert '/workspace/' not in text and '/tmp/' not in text
            ast.parse(text)
        source=plan['sources']['module']['path']
        spec=importlib.util.spec_from_file_location('targets_source_fixture',source)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        checks=module.check_fictional()
        assert checks=={'state':'PASS','fictional_checks':8,'NFL_rows':0}
        result.update(state='PASS_NEW_TARGET_PRODUCT_SOURCE_FIXTURE',fictional=checks,portable_source_AST_modules=3,exact_source_pins=plan['sources'])
    except BaseException as exc:
        result.update(error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        signal.alarm(0)
        result['actual']={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
        value=(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        assert len(value)<=32768
        with (out/'RESULT.json').open('xb') as handle:
            handle.write(value)
        print(json.dumps({'state':result['state'],'actual':result['actual']}))


if __name__=='__main__':
    main()
