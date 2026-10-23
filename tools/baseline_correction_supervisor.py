"""One600s correction guard using reviewed external/PID/resource primitives."""
import json
import math
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time
START=time.monotonic()
MARKER_FIELDS={'active','pid','process_start_ticks','process_cpu_start','cpu_clock','monotonic_start',
    'attempt','max_wall_seconds','max_CPU_seconds','generated_at'}


def fit_guard(marker,*,pid,start_ticks,cpu_now,monotonic_now,previous=0):
    if not isinstance(marker,dict) or set(marker)!=MARKER_FIELDS:return 'MALFORMED_FIT_GUARD',previous
    if (type(marker['active']) is not bool or type(marker['pid']) is not int or marker['pid']!=pid
            or type(marker['process_start_ticks']) is not int or marker['process_start_ticks']!=start_ticks
            or type(marker['attempt']) is not int or not max(1,previous)<=marker['attempt']<=44
            or marker['cpu_clock']!='proc_utime_plus_stime_over_CLK_TCK'
            or marker['max_wall_seconds']!=20 or marker['max_CPU_seconds']!=20
            or not isinstance(marker['generated_at'],str) or not marker['generated_at']):
        return 'INVALID_FIT_GUARD_IDENTITY_OR_LIMITS',previous
    for name in ('process_cpu_start','monotonic_start'):
        if type(marker[name]) not in (int,float) or not math.isfinite(marker[name]) or marker[name]<0:
            return 'INVALID_FIT_GUARD_CLOCK',previous
    if marker['process_cpu_start']>cpu_now+.03 or marker['monotonic_start']>monotonic_now+.1:return 'FUTURE_FIT_GUARD_CLOCK',previous
    if marker['active']:
        if monotonic_now-marker['monotonic_start']>=19:return 'PER_FIT_WALL_LIMIT',marker['attempt']
        if cpu_now-marker['process_cpu_start']>=19:return 'PER_FIT_CPU_LIMIT',marker['attempt']
    return None,marker['attempt']


def main():
    from baseline_correction_run import arguments,load,verify,extension
    from direct_booster_frozen_report_supervisor import usage,external_guard
    args=arguments()
    def deny(event,values):
        if event.startswith('socket.'):raise RuntimeError('correction supervisor forbids network')
    sys.addaudithook(deny)
    freeze=load(args.freeze,args.freeze_sha256);spec=verify(freeze);parent_guard=external_guard(freeze,args)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS'):os.environ[name]='2'
    sys.path.insert(0,freeze['code_root']);extension(spec['correction_extension'])
    from baseline_correction_orchestrator import storage
    store,output=storage(spec)
    if (output/'correction-supervisor-consumed.json').exists():raise RuntimeError('sole correction invocation consumed')
    store.atomic_json(output/'correction-supervisor-consumed.json',dict(invocations=1,freeze_sha256=args.freeze_sha256,
        external_timeout_parent=parent_guard),replace=False)
    env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':freeze['code_root']}
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS'):env[name]='2'
    if 'LD_LIBRARY_PATH' in os.environ:env['LD_LIBRARY_PATH']=os.environ['LD_LIBRARY_PATH']
    command=[freeze['environment']['executable'],'-B',freeze['tools']['run']['path'],
        '--freeze',args.freeze,'--freeze-sha256',args.freeze_sha256,'--parent-pid',str(os.getpid())]
    process=subprocess.Popen(command,cwd=freeze['code_root'],env=env,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,start_new_session=True)
    start_ticks=int(Path('/proc',str(process.pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    log=bytearray();peak=peak_cpu=previous=0;reason=None;seen=False
    try:
        while process.poll() is None or selector.get_map():
            for key,_ in selector.select(timeout=.05):
                body=os.read(key.fileobj.fileno(),65536)
                if body:log.extend(body)
                else:selector.unregister(key.fileobj)
            rss,cpu=usage(process,start_ticks)
            own=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();own_rss=int(own[21])*os.sysconf('SC_PAGE_SIZE')
            if own_rss<=0:raise RuntimeError('known supervisor RSS absent')
            rss+=own_rss;cpu+=time.process_time();peak=max(peak,rss);peak_cpu=max(peak_cpu,cpu)
            marker=output/'estimator-cpu-guard.json'
            if marker.exists():
                seen=True;control=json.loads(marker.read_text())
                try:worker=Path('/proc',str(process.pid),'stat').read_text().rsplit(')',1)[1].split()
                except FileNotFoundError:
                    if control['active']:raise RuntimeError('active fit worker disappeared')
                else:
                    if int(worker[19])!=start_ticks:raise RuntimeError('worker identity changed')
                    reason,previous=fit_guard(control,pid=process.pid,start_ticks=start_ticks,
                        cpu_now=(int(worker[11])+int(worker[12]))/os.sysconf('SC_CLK_TCK'),
                        monotonic_now=time.monotonic(),previous=previous)
            elif seen:reason='FIT_GUARD_DISAPPEARED'
            if time.monotonic()-START>=595:reason=reason or 'WALL_LIMIT'
            elif cpu>=595:reason=reason or 'CPU_LIMIT'
            elif rss>=1073741824-24*1024**2:reason=reason or 'RSS_LIMIT'
            elif len(log)>1048576:reason=reason or 'LOG_LIMIT'
            elif os.statvfs(output).f_bavail==0:reason=reason or 'PHYSICAL_DISK_FULL'
            if reason:break
    except BaseException as error:reason='MONITOR_EXCEPTION_'+type(error).__name__
    finally:
        selector.close()
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=3);process.stdout.close()
    children=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt=dict(state='COMPLETED' if process.returncode==0 and reason is None and (output/'report.json').exists() else 'FAILED',
        returncode=process.returncode,limit_reason=reason,wall_seconds=time.monotonic()-START,
        CPU_seconds=max(peak_cpu,time.process_time()+children.ru_utime+children.ru_stime),
        peak_sampled_combined_RSS_bytes=peak,child_ru_maxrss_bytes=children.ru_maxrss*1024,
        RSS_scope='explicit known worker/supervisor plus group; child ru_maxrss cross-check; sampling can miss brief combined peaks',
        worker_pid=process.pid,worker_start_ticks=start_ticks,last_observed_fit_attempt=previous,
        threads=2,new_HTTP=0,CDF_refits_model_loads_law_calls=0,retention=store.report_retention())
    store.write_bytes(output/'correction-supervisor.log',bytes(log[:1048576]),replace=False)
    receipt['wall_seconds']=time.monotonic()-START
    receipt['CPU_seconds']=max(peak_cpu,time.process_time()+children.ru_utime+children.ru_stime)
    if receipt['wall_seconds']>=600 or receipt['CPU_seconds']>=600 or children.ru_maxrss*1024>=1073741824:
        receipt.update(state='FAILED',limit_reason=reason or 'FINAL_RESOURCE_LIMIT')
    store.atomic_json(output/'correction-supervisor-completion.json',receipt,replace=False)
    print(json.dumps(receipt),flush=True)
    if receipt['state']!='COMPLETED':raise SystemExit(1)


if __name__=='__main__':main()
