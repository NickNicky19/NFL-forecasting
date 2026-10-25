"""Exactly one stdlib-only, fictional producer/orchestration contract packet."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import unittest

VERSION = "dynamic-opportunity-source-v1-software-20261023"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--freeze',required=True,type=Path)
    parser.add_argument('--freeze-sha256',required=True); args=parser.parse_args()
    if sha(args.freeze)!=args.freeze_sha256:raise RuntimeError('software freeze changed')
    freeze=json.loads(args.freeze.read_text());root=Path(__file__).resolve().parents[1]
    if freeze['schema_version']!=VERSION or freeze['root']!=str(root):raise RuntimeError('exact root/version required')
    expected=('nfl_lab/dynamic_opportunity_source.py','nfl_lab/dynamic_opportunity_study.py',
              'nfl_lab/dynamic_opportunity_core.py','nfl_lab/dynamic_opportunity_history.py','nfl_lab/state.py','nfl_lab/__init__.py',
              'tests/test_dynamic_opportunity_source.py','tools/dynamic_opportunity_source_software_v1.py',
              'config/dynamic-opportunity-source-v1-software.json')
    if set(freeze['bindings'])!={str(root/p) for p in expected}:raise RuntimeError('exact software bindings required')
    for path,ref in freeze['bindings'].items():
        item=Path(path)
        if item.is_symlink() or item.stat().st_size!=ref['bytes'] or sha(item)!=ref['sha256']:
            raise RuntimeError('immutable software binding changed')
    env=freeze['interpreter']
    if (sys.executable!=env['executable'] or sys.version!=env['version'] or not sys.dont_write_bytecode
            or str(Path(sys.executable).resolve())!=env['binary'] or sha(env['binary'])!=env['sha256']):
        raise RuntimeError('exact Python -B required')
    thread_vars=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_THREAD_LIMIT')
    if any(os.environ.get(k)!='2' for k in thread_vars):raise RuntimeError('all numerical caps2 required')
    destination=Path(freeze['output']);destination.mkdir(exist_ok=False)
    (destination/'CONSUMED.json').write_text('{"invocations":1,"automatic_retries":0}\n')
    start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(120,120))
    counts=dict(denied_effects=0,lines=0,resource_checks=0);exception=None;result=None;log=io.StringIO()
    def budget():
        counts['resource_checks']+=1
        if (time.monotonic()-start>=118 or time.process_time()-cpu>=118
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>536870912):
            raise RuntimeError('finite software resource cap')
    def trace(frame,event,arg):
        if event=='line':
            counts['lines']+=1
            if counts['lines']%200==0:budget()
        return trace
    def audit(event,arguments):
        denied=event.startswith(('socket.','subprocess.')) or event in {'os.system','os.fork','os.forkpty','os.exec','os.posix_spawn','pty.spawn'}
        if event=='open' and arguments and isinstance(arguments[0],(str,bytes,os.PathLike)):
            name=os.fsdecode(arguments[0])
            denied|=('/workspace/website-methods-research/' in name or name.endswith(('.parquet','.joblib','.pkl','.pickle','.csv')))
        if denied:
            counts['denied_effects']+=1
            raise RuntimeError('forbidden software source/model/network/process effect')
    def timeout(signum,frame):raise TimeoutError('software wall bound')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,119)
    sys.addaudithook(audit);sys.settrace(trace);sys.path.insert(0,str(root))
    try:
        path=root/'tests/test_dynamic_opportunity_source.py'
        spec=importlib.util.spec_from_file_location('new_source_contracts',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        suite=unittest.defaultTestLoader.loadTestsFromModule(module)
        if suite.countTestCases()!=12:raise RuntimeError('exact twelve NEW fictional methods required')
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite);budget()
    except BaseException as error:
        exception=dict(type=type(error).__name__,message=str(error))
    finally:
        sys.settrace(None);signal.setitimer(signal.ITIMER_REAL,0)
        wall=time.monotonic()-start;used=time.process_time()-cpu;peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        passed=(result is not None and result.wasSuccessful() and exception is None and counts['denied_effects']==0
                and wall<120 and used<120 and peak<=536870912)
        receipt=dict(schema_version=VERSION,state='PASS' if passed else 'FAILED',tests_run=None if result is None else result.testsRun,
            failures=None if result is None else len(result.failures),errors=None if result is None else len(result.errors),
            wall_seconds_before_receipt_write=wall,CPU_seconds_before_receipt_write=used,process_ru_maxrss_bytes=peak,
            RSS_scope='single process highwater plus traced checks; not kernel-enforced continuous RSS',
            limits=dict(wall_CPU_seconds=120,RSS_bytes=536870912,numerical_thread_caps=2,worker_children=0),
            invocations=1,automatic_retries=0,NFL_semantic_model_source_HTTP_CAS_old_suite_runs=0,
            counts=counts,exception=exception,log=log.getvalue(),freeze_sha256=args.freeze_sha256,
            requested_model='GPT-6.1 Sol Extra High',actual_backend='UNATTESTED')
        body=(json.dumps(receipt,indent=2,sort_keys=True)+'\n').encode()
        if len(body)>1048576:raise RuntimeError('software receipt too large')
        (destination/'FINISHED.json').write_bytes(body)
        print(json.dumps({k:receipt[k] for k in ('state','tests_run','failures','errors','wall_seconds_before_receipt_write','CPU_seconds_before_receipt_write','process_ru_maxrss_bytes','counts','exception')}))
        print('receipt_sha256',hashlib.sha256(body).hexdigest())
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
