"""One bounded fictional-only core check; root ledger GO precedes invocation.

The worker cannot create children, use network, read football namespaces or
write anything except its exact software receipt. Existing suites never run.
"""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import unittest

RELATIVE=('nfl_lab/dynamic_opportunity_core.py','nfl_lab/__init__.py',
    'tests/test_dynamic_opportunity_core.py','tools/dynamic_opportunity_core_software.py',
    'config/dynamic-opportunity-core-v1-software.json')


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(path,digest):
    if sha(path)!=digest:raise ValueError('software freeze changed')
    freeze=json.loads(Path(path).read_text());root=Path(__file__).resolve().parents[1]
    if freeze['schema_version']!='dynamic-opportunity-core-software-freeze-v1' or freeze['root']!=str(root):raise ValueError('exact isolated software root required')
    expected={str(root/name) for name in RELATIVE}
    if set(freeze['bindings'])!=expected:raise ValueError('exact new-core/harness/config/init bindings required')
    for name,item in freeze['bindings'].items():
        file=Path(name)
        if file.resolve()!=file or any(p.is_symlink() for p in (file,*file.parents)) or file.stat().st_size!=item['bytes'] or sha(file)!=item['sha256']:
            raise ValueError('software binding changed:'+name)
    policy=json.loads((root/'config/dynamic-opportunity-core-v1-software.json').read_text())
    if policy['registration_id']!='dynamic-opportunity-core-v1-software-20261023':raise ValueError('wrong software policy')
    if policy['budgets']!=dict(new_fictional_invocations=1,maximum_new_checks=40,wall_seconds=120,CPU_seconds=120,
            combined_RSS_bytes=536870912,numerical_threads=2,NFL_semantic_reads_model_loads_real_fits_predictions_HTTP_CAS=0,
            worker_child_processes=0,existing_suite_reruns=0):raise ValueError('fixed finite software budget changed')
    env=freeze['interpreter'];binary=Path(env['binary'])
    if sys.executable!=env['executable'] or sys.version!=env['version'] or binary!=Path(sys.executable).resolve() or sha(binary)!=env['sha256']:
        raise ValueError('software interpreter changed')
    return root,freeze


def worker(args):
    if args.parent_pid is None or args.parent_pid<=1 or os.getppid()!=args.parent_pid:raise RuntimeError('fictional supervisor absent')
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:raise OSError(ctypes.get_errno(),'PDEATHSIG failed')
    if os.getppid()!=args.parent_pid:os.kill(os.getpid(),signal.SIGKILL)
    resource.setrlimit(resource.RLIMIT_CPU,(117,118))
    root,freeze=verify(args.freeze,args.freeze_sha256)
    allowed={Path(p) for p in freeze['bindings']};receipt=Path(args.output)/'worker.json'
    stdlib=Path(sys.base_prefix).resolve()
    def deny(event,values):
        if event.startswith('socket.') or event in {'subprocess.Popen','os.posix_spawn','os.fork','os.forkpty','os.system'}:
            raise RuntimeError('fictional worker forbids network/children')
        if event in {'os.remove','os.rename','os.rmdir','os.link','os.symlink','os.mkdir'}:raise RuntimeError('fictional worker forbids filesystem mutation')
        if event=='open' and not isinstance(values[0],int):
            path=Path(os.fspath(values[0])).absolute();mode=values[1] or '';flags=values[2]
            writing=any(c in str(mode) for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing and path!=receipt:raise RuntimeError('only exact fictional worker receipt is writable')
            if not writing and path not in allowed and path!=receipt and stdlib not in path.parents:
                # Importlib probes absent caches even with -B. Permit no actual
                # unfrozen bytecode read: an existing cache remains forbidden.
                if path.suffix=='.pyc' and not path.exists():return
                raise RuntimeError('fictional worker read outside frozen code/stdlib')
    sys.addaudithook(deny);sys.path.insert(0,str(root))
    module_path=root/'tests/test_dynamic_opportunity_core.py'
    spec=importlib.util.spec_from_file_location('dynamic_core_new_checks',module_path);module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module;spec.loader.exec_module(module)
    suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    if suite.countTestCases()!=24:raise ValueError('exact24 new fictional checks required')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    value=dict(state='PASS' if result.wasSuccessful() else 'FAILED',new_checks=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        NFL_semantic_reads_model_loads_real_fits_predictions_HTTP_CAS=0,worker_children=0,unchanged_suite_reruns=0)
    with receipt.open('x') as stream:json.dump(value,stream,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def proc(pid):return Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',required=True);parser.add_argument('--freeze-sha256',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--worker',action='store_true');parser.add_argument('--parent-pid',type=int)
    args=parser.parse_args()
    if args.worker:worker(args)
    root,freeze=verify(args.freeze,args.freeze_sha256)
    output=Path(args.output)
    if not output.is_absolute() or output.resolve()!=output or Path('/tmp') not in output.parents or output.exists():
        raise ValueError('fresh exact/tmp software namespace required; no CAS/root write')
    output.mkdir()
    with (output/'CONSUMED.json').open('x') as stream:json.dump(dict(invocations=1,freeze_sha256=args.freeze_sha256),stream)
    env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(root)}
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS'):env[name]='2'
    started=time.monotonic();peak=0;reason=None
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with (output/'worker.log').open('xb') as log:
        child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--freeze',args.freeze,
            '--freeze-sha256',args.freeze_sha256,'--output',str(output),'--parent-pid',str(os.getpid())],
            cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        ticks=int(proc(child.pid)[19])
        try:
            while child.poll() is None:
                try:
                    state=proc(child.pid)
                    if int(state[19])!=ticks:raise RuntimeError('known fictional worker identity changed')
                    rss=int(state[21])*os.sysconf('SC_PAGE_SIZE')
                    if state[0]!='Z' and rss<=0:raise RuntimeError('known live fictional worker RSS absent')
                except FileNotFoundError:
                    if child.poll() is None:raise
                    rss=0
                own_rss=int(proc(os.getpid())[21])*os.sysconf('SC_PAGE_SIZE')
                if own_rss<=0:raise RuntimeError('known supervisor RSS absent')
                peak=max(peak,rss+own_rss)
                if peak>=536870912:reason='COMBINED_RSS_CAP'
                if time.monotonic()-started>=117:reason='WALL_CAP'
                if reason:break
                time.sleep(.05)
        except BaseException as error:reason='MONITOR_EXCEPTION_'+type(error).__name__
        finally:
            if child.poll() is None:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            code=child.wait(timeout=3)
    after=resource.getrusage(resource.RUSAGE_CHILDREN);own=resource.getrusage(resource.RUSAGE_SELF)
    child_cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
    total_cpu=child_cpu+own.ru_utime+own.ru_stime
    if total_cpu>=120 or after.ru_maxrss*1024>=536870912:reason=reason or 'FINAL_RESOURCE_CAP'
    child_result=json.loads((output/'worker.json').read_text()) if (output/'worker.json').exists() else None
    receipt=dict(state='PASS' if code==0 and reason is None and child_result and child_result['state']=='PASS' else 'FAILED',
        returncode=code,limit_reason=reason,wall_seconds=time.monotonic()-started,CPU_seconds=total_cpu,
        child_CPU_seconds=child_cpu,sampled_combined_peak_RSS_bytes=peak,child_ru_maxrss_bytes=after.ru_maxrss*1024,
        RSS_scope='Known worker/startticks and supervisor sampled50ms; childru_maxrss crosscheck; combined sampling can miss peaks',
        freeze_sha256=args.freeze_sha256,bindings=freeze['bindings'],interpreter=freeze['interpreter'],
        new_fictional_invocations=1,expected_new_checks=24,NFL_semantic_reads_model_loads_real_fits_predictions_HTTP_CAS=0)
    with (output/'FINISHED.json').open('x') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps(receipt),flush=True);print((output/'worker.log').read_text())
    if receipt['state']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
