"""Six fictional owned-child termination contracts; no old tests or automatic retry."""
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

START=time.monotonic()
VERSION='dynamic-history-termination-guard-v2-software-20261023'
ACCEPTED_GUARD_SHA='6bec15c23d8d30c55e5cdd4b52176201c956a0de6e6afdf6bbf6903e3c2fb047'
SAMPLER_SHA='0477bd08e36700f27b7d9c356f51fabf1b623a9f63e792581f3a5f6071d177de'


class GuardFailure(RuntimeError):
    def __init__(self,code,snapshot=None):self.code=code;self.snapshot=snapshot or {};super().__init__(code)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def pin(item):
    path=Path(item['path'])
    if path.resolve()!=path or any(p.is_symlink() for p in (path,*path.parents)) or path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:
        raise GuardFailure('FROZEN_FILE_CHANGED',dict(path=str(path)))
    return path


def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def verify(args):
    if sha(args.freeze)!=args.freeze_sha256:raise GuardFailure('EXECUTION_FREEZE_CHANGED')
    freeze=json.loads(Path(args.freeze).read_text());root=Path(__file__).resolve().parents[1]
    if freeze['schema_version']!=VERSION or freeze['root']!=str(root):raise GuardFailure('EXECUTION_SCHEMA_OR_ROOT_CHANGED')
    relatives=('nfl_lab/termination_accounting.py','nfl_lab/__init__.py',
        'tests/test_termination_accounting.py','tools/dynamic_history_guard_software_v2.py',
        'config/dynamic-history-guard-v2-software.json')
    extra=('accepted_guard','sampler','timeout','preserved_adapter','preserved_arithmetic_core','preserved_adapter_tests','original_failed','original_worker')
    expected={str(root/p) for p in relatives}|{freeze[k]['path'] for k in extra}
    if set(freeze['bindings'])!=expected:raise GuardFailure('EXACT_SOFTWARE_BINDINGS_REQUIRED')
    for path,item in freeze['bindings'].items():
        if path!=item['path']:raise GuardFailure('BINDING_KEY_MISMATCH')
        pin(item)
    for name in extra:
        if freeze[name]!=freeze['bindings'][freeze[name]['path']]:raise GuardFailure('REFERENCE_BINDING_MISMATCH')
    policy=json.loads(pin(freeze['policy']).read_text())
    if (policy['registration_id']!=VERSION or policy['budgets']!=dict(new_fictional_invocations=1,new_contract_checks=6,
            wall_seconds=30,CPU_seconds=30,combined_RSS_bytes=536870912,threads=1,startup_seconds=2,worker_children=0,
            NFL_semantic_reads_models_sources_HTTP_CAS=0,automatic_retries=0)):
        raise GuardFailure('POLICY_OR_BUDGET_CHANGED')
    for key,relative in (('core_sha256','nfl_lab/termination_accounting.py'),('tests_sha256','tests/test_termination_accounting.py')):
        if sha(root/relative)!=policy[key]:raise GuardFailure('IMMUTABLE_SOFTWARE_CHANGED')
    if set(policy['preserved'])!={'preserved_adapter','preserved_arithmetic_core','preserved_adapter_tests','original_failed','original_worker'}:raise GuardFailure('EXACT_ORIGINAL_PACKET_BINDINGS_REQUIRED')
    for name,expected_sha in policy['preserved'].items():
        if freeze[name]['sha256']!=expected_sha:raise GuardFailure('ORIGINAL_FAILED_PACKET_CHANGED')
    failed=json.loads(pin(freeze['original_failed']).read_text());prior_worker=json.loads(pin(freeze['original_worker']).read_text())
    if (failed.get('state')!='FAILED' or failed.get('freeze_sha256')!='258196cb4c8b08af80726b54f709ab56f7d44fd982a903e4419a43394defe07b'
            or prior_worker.get('state')!='PASS' or prior_worker.get('new_checks')!=18):raise GuardFailure('ORIGINAL_FAILED_STATUS_NOT_PRESERVED')
    if freeze['policy']!=freeze['bindings'][str(root/'config/dynamic-history-guard-v2-software.json')]:raise GuardFailure('POLICY_BINDING_MISMATCH')
    if (freeze['accepted_guard']['sha256']!=ACCEPTED_GUARD_SHA or policy['accepted_guard_sha256']!=ACCEPTED_GUARD_SHA or
            freeze['sampler']['sha256']!=SAMPLER_SHA or policy['accepted_sampler_sha256']!=SAMPLER_SHA):raise GuardFailure('ACCEPTED_GUARD_OR_SAMPLER_CHANGED')
    if freeze['timeout']['path']!='/usr/bin/timeout':raise GuardFailure('EXACT_TIMEOUT_REQUIRED')
    env=freeze['interpreter'];binary=Path(env['binary'])
    if (sys.executable!=env['executable'] or sys.version!=env['version'] or binary!=Path(sys.executable).resolve()
            or sha(binary)!=env['sha256']):raise GuardFailure('EXACT_INTERPRETER_REQUIRED')
    return root,freeze


def bounded_json(path,value):
    body=json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(body)>4096:raise GuardFailure('HANDSHAKE_RECEIPT_TOO_LARGE')
    path=Path(path);temporary=path.with_name('.pending-'+path.name)
    with temporary.open('xb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    # Final marker appears only after its complete body is durable. link is
    # exclusive at destination, so retries can never overwrite an old receipt.
    os.link(temporary,path);temporary.unlink()


def identity(sampler,pid):
    return dict(pid=pid,start_ticks=int(sampler.process_stat(pid)[19]))


def sample(sampler,binding,*,stage,allow_startup_zero=False,allow_exit=False):
    snapshot=dict(pid=binding['pid'],start_ticks=binding['start_ticks'],stage=stage)
    try:
        before=sampler.process_stat(binding['pid']);snapshot.update(before_state=before[0],before_start_ticks=int(before[19]),stat_RSS_before_bytes=int(before[21])*os.sysconf('SC_PAGE_SIZE'))
        if int(before[19])!=binding['start_ticks']:raise GuardFailure('PID_START_TICKS_CONFLICT',snapshot)
        fields={}
        for line in Path('/proc',str(binding['pid']),'status').read_text().splitlines():
            name,_,value=line.partition(':')
            if name in ('Pid','VmRSS','VmHWM'):
                if name in fields:raise GuardFailure('DUPLICATE_STATUS_COUNTER',snapshot)
                fields[name]=value.split()
        after=sampler.process_stat(binding['pid']);snapshot.update(after_state=after[0],after_start_ticks=int(after[19]),
            stat_RSS_after_bytes=int(after[21])*os.sysconf('SC_PAGE_SIZE'),status_fields=fields,
            CPU_seconds=(int(after[11])+int(after[12]))/os.sysconf('SC_CLK_TCK'))
        if int(after[19])!=binding['start_ticks'] or fields.get('Pid')!=[str(binding['pid'])]:raise GuardFailure('PID_STATUS_IDENTITY_CONFLICT',snapshot)
        if allow_exit and after[0] in ('Z','X'):
            snapshot.update(state='AUTHENTICATED_EXITED_CHILD',charged_RSS_bytes=0);return snapshot
        values=fields.get('VmRSS')
        if values is None or len(values)!=2 or values[1]!='kB':raise GuardFailure('LIVE_RSS_COUNTER_MISSING',snapshot)
        status_rss=int(values[0])*1024
        snapshot['status_RSS_bytes']=status_rss
        rss=max(snapshot['stat_RSS_before_bytes'],snapshot['stat_RSS_after_bytes'],status_rss)
        if min(snapshot['stat_RSS_before_bytes'],snapshot['stat_RSS_after_bytes'],status_rss)<0:raise GuardFailure('NEGATIVE_RSS_COUNTER',snapshot)
        hwm=fields.get('VmHWM');snapshot['status_HWM_bytes']=int(hwm[0])*1024 if hwm and len(hwm)==2 and hwm[1]=='kB' else None
        snapshot.update(charged_RSS_bytes=rss,RSS_reconciliation='maximum of identity-bound non-atomic stat/status observations')
        if rss==0 and not allow_startup_zero:raise GuardFailure('LIVE_RSS_ZERO_AFTER_RELEASE',snapshot)
        snapshot['state']='AUTHENTICATED_STARTUP_ZERO_RSS' if rss==0 else 'AUTHENTICATED_LIVE_RSS'
        return snapshot
    except GuardFailure:raise
    except (FileNotFoundError,ProcessLookupError):raise GuardFailure('REQUIRED_PROCESS_ACCOUNTING_MISSING',snapshot)
    except (ValueError,IndexError):raise GuardFailure('PROCESS_COUNTER_PARSE_CONFLICT',snapshot)


def worker(args):
    if args.parent_pid is None or os.getppid()!=args.parent_pid:raise GuardFailure('WORKER_PARENT_ABSENT')
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:raise GuardFailure('PDEATHSIG_ARM_FAILED')
    if os.getppid()!=args.parent_pid:os.kill(os.getpid(),signal.SIGKILL)
    resource.setrlimit(resource.RLIMIT_CPU,(27,28))
    root,freeze=verify(args);output=Path(args.output)
    ready,go,started,receipt=(output/name for name in ('READY.json','GO.json','TESTS_STARTED.json','worker.json'))
    own_stat=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();ticks=int(own_stat[19])
    allowed={Path(p) for p in freeze['bindings']}
    allowed|={ready,go,started,receipt,Path(args.freeze)}
    stdlib=Path(sys.base_prefix).resolve()
    writable={ready,started,receipt};temporaries={p.with_name('.pending-'+p.name) for p in writable}
    def deny(event,values):
        if event.startswith('socket.') or event in {'subprocess.Popen','os.posix_spawn','os.fork','os.forkpty','os.system'}:raise GuardFailure('WORKER_NETWORK_OR_CHILD_FORBIDDEN')
        if event=='os.link':
            src,dst=Path(os.fspath(values[0])).absolute(),Path(os.fspath(values[1])).absolute()
            if dst not in writable or src!=dst.with_name('.pending-'+dst.name):raise GuardFailure('WORKER_LINK_FORBIDDEN')
        elif event=='os.remove':
            if Path(os.fspath(values[0])).absolute() not in temporaries:raise GuardFailure('WORKER_REMOVE_FORBIDDEN')
        elif event in {'os.rename','os.rmdir','os.symlink','os.mkdir'}:raise GuardFailure('WORKER_MUTATION_FORBIDDEN')
        if event=='open' and not isinstance(values[0],int):
            path=Path(os.fspath(values[0])).absolute();mode=values[1] or '';flags=values[2]
            writing=any(c in str(mode) for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing and path not in writable|temporaries:raise GuardFailure('WORKER_UNDECLARED_WRITE_FORBIDDEN')
            if not writing and path not in allowed and stdlib not in path.parents:
                if path.suffix=='.pyc' and not path.exists():return
                raise GuardFailure('WORKER_UNDECLARED_READ_FORBIDDEN')
    sys.addaudithook(deny)
    bounded_json(ready,dict(schema_version='termination-guard-ready-v2',state='NO_CONTRACT_IMPORTED_READY',pid=os.getpid(),start_ticks=ticks,
        supervisor_pid=args.parent_pid,freeze_sha256=args.freeze_sha256,PDEATHSIG_armed=True))
    waiting=time.monotonic()
    while not go.exists():
        if os.getppid()!=args.parent_pid:raise GuardFailure('WORKER_PARENT_CHANGED_AT_BARRIER')
        if time.monotonic()-waiting>=2:raise GuardFailure('WORKER_GO_TIMEOUT')
        time.sleep(.01)
    released=json.loads(go.read_text())
    expected=dict(schema_version='termination-guard-go-v2',pid=os.getpid(),start_ticks=ticks,supervisor_pid=args.parent_pid,
        freeze_sha256=args.freeze_sha256,positive_RSS_verified=True)
    if released!=expected:raise GuardFailure('WORKER_GO_BINDING_CONFLICT')
    bounded_json(started,dict(state='CONTRACT_TEST_IMPORT_RELEASED',freeze_sha256=args.freeze_sha256,new_checks=6))
    sys.path.insert(0,str(root));module=load_module(root/'tests/test_termination_accounting.py','termination_guard_v2_new_checks')
    suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    if suite.countTestCases()!=6:raise GuardFailure('EXACT6_NEW_CHECKS_REQUIRED')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    bounded_json(receipt,dict(state='PASS' if result.wasSuccessful() and not result.skipped and result.testsRun==6 else 'FAILED',new_checks=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        NFL_semantic_reads_models_sources_HTTP_CAS=0,worker_children=0,unchanged_suite_reruns=0))
    return 0 if result.wasSuccessful() and not result.skipped and result.testsRun==6 else 1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',required=True);parser.add_argument('--freeze-sha256',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--worker',action='store_true');parser.add_argument('--parent-pid',type=int)
    args=parser.parse_args()
    if args.worker:
        try:return worker(args)
        except GuardFailure as error:
            bounded_json(Path(args.output)/'worker.json',dict(state='FAILED',reason_code=error.code,reason_snapshot=error.snapshot,new_checks=None,completion='UNVERIFIED'))
            return 1
        except BaseException as error:
            bounded_json(Path(args.output)/'worker.json',dict(state='FAILED',reason_code='UNEXPECTED_WORKER_'+type(error).__name__,new_checks=None,completion='UNVERIFIED'))
            return 1
    root,freeze=verify(args);sampler=load_module(freeze['sampler']['path'],'termination_guard_accepted_process_sampler')
    accounting=load_module(root/'nfl_lab/termination_accounting.py','owned_child_termination_guard_v2')
    output=Path(args.output)
    if not output.is_absolute() or output.resolve()!=output or Path('/tmp') not in output.parents or output.exists():raise GuardFailure('FRESH_SOFTWARE_TMP_NAMESPACE_REQUIRED')
    parent_pid=os.getppid();parent_root=Path('/proc',str(parent_pid))
    command=[freeze['timeout']['path'],'--signal=KILL','--kill-after=1s','30s',freeze['interpreter']['executable'],'-B',str(Path(__file__).resolve()),
        '--freeze',args.freeze,'--freeze-sha256',args.freeze_sha256,'--output',args.output]
    if (parent_root/'exe').resolve()!=Path('/usr/bin/timeout') or (parent_root/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')!=[x.encode() for x in command]:raise GuardFailure('EXACT_EXTERNAL30S_TIMEOUT_REQUIRED')
    output.mkdir();bounded_json(output/'CONSUMED.json',dict(invocations=1,freeze_sha256=args.freeze_sha256,prior_software='NO_RETRY_AUTHORITY'))
    required=[identity(sampler,parent_pid),identity(sampler,os.getpid())]
    env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(root)}
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS'):env[name]='1'
    transfers=[];reap_charges=[]
    stage='STARTUP_BARRIER';reason=None;snapshot=None;startup=[];last=[];peak=cpu_peak=0.;zero_samples=mismatches=0;released=False
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with (output/'worker.log').open('xb') as log:
        child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--freeze',args.freeze,'--freeze-sha256',args.freeze_sha256,
            '--output',str(output),'--parent-pid',str(os.getpid())],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        binding=identity(sampler,child.pid);launched=time.monotonic()
        try:
            while child.poll() is None:
                samples=[sample(sampler,item,stage=stage) for item in required]
                try:
                    worker_sample=sample(sampler,binding,stage=stage,allow_startup_zero=not released,allow_exit=True)
                except GuardFailure as error:
                    if not released:raise
                    try:
                        transfer=accounting.confirm_owned_child_exit(child,binding,reason_code=error.code,snapshot=error.snapshot)
                    except accounting.AccountingFailure:
                        raise error
                    # Exact owned waitpid-confirmed termination, not a live RSS
                    # zero. Retain the failed observation and charge full reaped
                    # CPU/HWM below before any final resource acceptance.
                    transfers.append(transfer);last=samples
                    break
                samples.append(worker_sample);last=samples
                rss=sum(s['charged_RSS_bytes'] for s in samples);cpu=sum(s['CPU_seconds'] for s in samples)
                peak=max(peak,rss);cpu_peak=max(cpu_peak,cpu)
                if not released:startup.append(samples)
                zero_samples+=worker_sample['state']=='AUTHENTICATED_STARTUP_ZERO_RSS'
                mismatches+=worker_sample.get('status_RSS_bytes') is not None and worker_sample['stat_RSS_after_bytes']!=worker_sample['status_RSS_bytes']
                if rss>=536870912:raise GuardFailure('COMBINED_RSS_CAP',dict(samples=samples))
                if cpu>=27:raise GuardFailure('COMBINED_CPU_STOP',dict(samples=samples))
                if time.monotonic()-START>=27:raise GuardFailure('GLOBAL_WALL_STOP',dict(samples=samples))
                if not released:
                    if time.monotonic()-launched>=2:raise GuardFailure('STARTUP_BARRIER_TIMEOUT',dict(samples=samples))
                    ready_path=output/'READY.json'
                    if ready_path.exists():
                        ready=json.loads(ready_path.read_text())
                        expected=dict(schema_version='termination-guard-ready-v2',state='NO_CONTRACT_IMPORTED_READY',pid=child.pid,start_ticks=binding['start_ticks'],
                            supervisor_pid=os.getpid(),freeze_sha256=args.freeze_sha256,PDEATHSIG_armed=True)
                        if ready!=expected:raise GuardFailure('READY_BINDING_CONFLICT',dict(ready=ready,samples=samples))
                        if worker_sample['state']=='AUTHENTICATED_LIVE_RSS' and worker_sample['charged_RSS_bytes']>0:
                            bounded_json(output/'GO.json',dict(schema_version='termination-guard-go-v2',pid=child.pid,start_ticks=binding['start_ticks'],
                                supervisor_pid=os.getpid(),freeze_sha256=args.freeze_sha256,positive_RSS_verified=True))
                            released=True;stage='CONTRACT_CHECKS_RELEASED'
                time.sleep(.01)
        except GuardFailure as error:reason=error.code;snapshot=error.snapshot
        except BaseException as error:reason='UNEXPECTED_MONITOR_'+type(error).__name__;snapshot=dict(last_authenticated_samples=last)
        finally:
            if child.poll() is None:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            code=child.wait(timeout=3)
    after=resource.getrusage(resource.RUSAGE_CHILDREN);own=resource.getrusage(resource.RUSAGE_SELF)
    child_cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
    for transfer in transfers:
        try:
            reap_charges.append(accounting.validate_reaped_accounting(transfer,child_CPU_seconds=child_cpu,child_highwater_bytes=after.ru_maxrss*1024))
        except accounting.AccountingFailure:
            reason=reason or 'TERMINATION_REAP_COUNTER_INVALID';snapshot=snapshot or dict(termination_transfer=transfer)

    try:timeout_final=sample(sampler,required[0],stage='POST_REAP_FINAL')
    except GuardFailure as error:
        reason=reason or error.code;snapshot=snapshot or error.snapshot;timeout_final=None
    total_cpu=max(cpu_peak,child_cpu+own.ru_utime+own.ru_stime+(timeout_final['CPU_seconds'] if timeout_final else 0))
    child_result=json.loads((output/'worker.json').read_text()) if (output/'worker.json').exists() else None
    if code!=0 and reason is None:
        reason=('WORKER_'+child_result['reason_code']) if child_result and child_result.get('reason_code') else 'WORKER_EXIT_NONZERO_AFTER_RELEASE' if released else 'WORKER_EXIT_BEFORE_RELEASE'
    individual_HWM_sum=after.ru_maxrss*1024+own.ru_maxrss*1024+((timeout_final.get('status_HWM_bytes') or 0) if timeout_final else 0)
    if total_cpu>=30 or individual_HWM_sum>=536870912 or time.monotonic()-START>=30:reason=reason or 'FINAL_RESOURCE_CAP'
    result=dict(state='PASS' if code==0 and not reason and child_result and child_result['state']=='PASS' else 'FAILED',
        returncode=code,stage=stage,reason_code=reason,reason_snapshot=snapshot,release_verified=released,
        contract_check_completion='VERIFIED6' if child_result and child_result.get('state')=='PASS' else 'UNVERIFIED',
        wall_seconds=time.monotonic()-START,CPU_seconds=total_cpu,child_CPU_seconds=child_cpu,
        CPU_scope='three known processes through final sample' if timeout_final else 'observed lower bound; final timeout sample failed',
        combined_RSS_peak_sampled_bytes=int(peak),child_ru_maxrss_bytes=after.ru_maxrss*1024,supervisor_ru_maxrss_bytes=own.ru_maxrss*1024,
        timeout_final_sample=timeout_final,individual_HWM_sum_upper_bound_bytes=individual_HWM_sum,
        RSS_scope='Exact timeout/supervisor/worker PID+startticks; max(stat_before,stat_after,status); non-atomic sampling may miss transient peaks',
        startup_known_zero_samples=zero_samples,worker_stat_status_mismatch_samples=mismatches,startup_samples=startup,
        last_authenticated_samples=last,termination_transfers=transfers,termination_reap_charges=reap_charges,
        original_dynamic_guard='FAILED_UNCHANGED_NO_RETROACTIVE_PASS',new_fictional_invocations=1,
        freeze_sha256=args.freeze_sha256,NFL_semantic_reads_models_sources_HTTP_CAS=0)
    with (output/'FINISHED.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('startup_samples','last_authenticated_samples','reason_snapshot')}),flush=True)
    print((output/'worker.log').read_text())
    return 0 if result['state']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
