"""One bounded fictional-only invocation; no source/model/network/process access."""
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

ROOT=Path('/workspace/nfl-baseline-correction-report-v3')
RECEIPT=Path('/tmp/baseline-correction-report-v3-software-checks.json')
if RECEIPT.exists():
    raise SystemExit('single invocation receipt already exists; no retry')
FILES=('tools/baseline_correction_report_v3.py', 'tools/baseline_correction_report_run_v3.py', 'tools/baseline_correction_report_supervisor_v3.py', 'tools/freeze_baseline_correction_report_v3.py', 'tools/compact_report_contract_v3.py', 'tests/test_baseline_correction_report_v3.py', 'config/baseline-correction-report-v3.json', 'reports/BASELINE_CORRECTION_REPORT_PLAN_V3.md', 'reports/BASELINE_CORRECTION_REPORT_V3_METADATA_INVENTORY.json')
bindings={name:{'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),
                'bytes':(ROOT/name).stat().st_size} for name in FILES}
threads=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS')
if any(os.environ.get(x)!='1' for x in threads) or not sys.dont_write_bytecode:
    raise SystemExit('one-thread Python -B required')
CONSUMED=Path('/tmp/baseline-correction-report-v3-software-CONSUMED.json')
if CONSUMED.exists(): raise SystemExit('software budget consumed; no retry')
CONSUMED.write_text(json.dumps({'invocations':1,'automatic_retries':0,'scope':'fictional_only'})+'\n')
resource.setrlimit(resource.RLIMIT_CPU,(30,30))
start=time.monotonic(); cpu_start=time.process_time(); rss_limit=536870912
counts={'lines':0,'resource_checks':0,'denied_effects':0}
def budget():
    counts['resource_checks']+=1
    if (time.monotonic()-start>=28 or time.process_time()-cpu_start>=28
            or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>rss_limit):
        raise RuntimeError('finite software-check resource bound exceeded')
def trace(frame,event,arg):
    if event=='line':
        counts['lines']+=1
        if counts['lines']%200==0: budget()
    return trace

def stop(signum,frame): raise TimeoutError('finite software-check wall bound')
signal.signal(signal.SIGALRM,stop); signal.setitimer(signal.ITIMER_REAL,29)
forbidden=set()
def audit(event,args):
    denied=(event.startswith('socket.') or event.startswith('subprocess.')
        or event in {'os.system','os.fork','os.forkpty','os.posix_spawn','os.exec','pty.spawn'})
    if event=='import' and args and (args[0] in forbidden or args[0].split('.')[0] in forbidden): denied=True
    if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
        path=os.fsdecode(args[0])
        if '/workspace/website-methods-research/' in path or path.endswith(('.parquet','.joblib','.pickle','.pkl')):
            denied=True
    if denied:
        counts['denied_effects']+=1
        raise RuntimeError('forbidden source/model/network/process effect')
sys.addaudithook(audit); sys.path.insert(0,str(ROOT)); sys.settrace(trace)
result=None; error=None; stream=io.StringIO()
try:
    spec=importlib.util.spec_from_file_location('new_v3_delta_contracts',ROOT/'tests/test_baseline_correction_report_v3.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    if suite.countTestCases()!=4: raise RuntimeError('exact4 new fictional checks required')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    budget()
except BaseException as exc:
    error={'type':type(exc).__name__,'message':str(exc)}
finally:
    sys.settrace(None); signal.setitimer(signal.ITIMER_REAL,0)
    budget_wall=time.monotonic()-start; budget_cpu=time.process_time()-cpu_start
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    success=result is not None and result.wasSuccessful() and error is None and counts['denied_effects']==0 and peak<=rss_limit
    receipt={'schema_version':'baseline-correction-report-v3-delta-checks','state':'PASS' if success else 'FAILED',
        'invocations':1,'automatic_retries':0,'tests_run':None if result is None else result.testsRun,
        'failures':None if result is None else len(result.failures),'errors':None if result is None else len(result.errors),
        'wall_seconds_before_receipt_write':budget_wall,'CPU_seconds_before_receipt_write':budget_cpu,
        'process_ru_maxrss_bytes':peak,'RSS_cap_bytes':rss_limit,'numerical_threads':1,
        'RSS_scope':'single process; known highwater and traced checks, not kernel-enforced continuous RSS',
        'CPU_wall_caps_seconds':30,'HTTP_source_model_semantic_reads_fits_scores_child_processes':0,
        'counts':counts,'bindings':bindings,'exception':error,'unittest_log':stream.getvalue(),
        'requested_model':'GPT-6.1 Sol','requested_reasoning_effort':'Extra High','actual_backend_settings':'UNATTESTED'}
    RECEIPT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({key:receipt[key] for key in ('state','tests_run','failures','errors','wall_seconds_before_receipt_write','CPU_seconds_before_receipt_write','process_ru_maxrss_bytes','exception')}))
    print('receipt_sha256',hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),'bytes',RECEIPT.stat().st_size)
    if not success: print(stream.getvalue())
raise SystemExit(0 if success else 1)
