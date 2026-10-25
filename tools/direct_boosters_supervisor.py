"""Outer whole-process-group software limits, including quota/bootstrap work."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time

START=time.monotonic()
CPU_START=time.process_time()
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def inspect_group(group):
    rss=cpu=0
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            v=path.read_text().rsplit(')',1)[1].split()
            if int(v[2])==group:
                rss+=int(v[21])*os.sysconf('SC_PAGE_SIZE')
                cpu+=sum(int(v[i]) for i in (11,12,13,14))/os.sysconf('SC_CLK_TCK')
        except (OSError,ValueError,IndexError): pass
    return rss,cpu


def software_bytes(spec):
    total=0
    for root in (spec['software'],'/workspace/nfl-direct-boosters-venv'):
        for path in Path(root).rglob('*'):
            try:
                if path.is_file() and not path.is_symlink(): total+=path.stat().st_size
            except FileNotFoundError: continue
    return total


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',required=True);parser.add_argument('--freeze-sha256',required=True)
    args=parser.parse_args(); freeze=Path(args.freeze)
    if hashlib.sha256(freeze.read_bytes()).hexdigest()!=args.freeze_sha256: raise ValueError('freeze changed')
    spec=json.loads(freeze.read_text())
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=spec['supervisor_sha256']: raise ValueError('supervisor changed')
    if spec['timeout_executable']!='/usr/bin/timeout' or hashlib.sha256(Path(spec['timeout_executable']).read_bytes()).hexdigest()!=spec['timeout_sha256']:
        raise ValueError('timeout binary changed')
    if sys.executable!=spec['base_executable'] or sys.version!=spec['base_python']: raise ValueError('base runtime changed')
    # GNU timeout is independent of this monitor and kills the entire isolated
    # group if the monitor exits unexpectedly. No --foreground escape.
    allowance=max(1,235-(time.monotonic()-START))
    command=[spec['timeout_executable'],'--signal=KILL','--kill-after=1s',f'{allowance:.3f}s',sys.executable,str(ROOT/'tools/direct_boosters_capability.py'),'--freeze',str(freeze),'--freeze-sha256',args.freeze_sha256]
    env=dict(os.environ)
    env.update({key:'2' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT')})
    env['PYTHONDONTWRITEBYTECODE']='1'
    os.environ.update({key:env[key] for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','PYTHONDONTWRITEBYTECODE')})
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True,env=env)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    output=bytearray();reason=None;peak=0;peak_cpu=0
    retained=0
    try:
        while process.poll() is None or selector.get_map():
            for key,_ in selector.select(timeout=.05):
                chunk=os.read(key.fileobj.fileno(),65536)
                if chunk: output.extend(chunk)
                else: selector.unregister(key.fileobj)
            rss,cpu=inspect_group(process.pid)
            rss+=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
            peak=max(peak,rss);peak_cpu=max(peak_cpu,cpu+time.process_time())
            retained=software_bytes(spec)
            if time.monotonic()-START>=236: reason='WALL_LIMIT'
            elif peak_cpu>=176: reason='CPU_LIMIT'
            elif peak>=1024**3-24*1024**2: reason='RSS_LIMIT'
            elif retained>=2*1024**3-24*1024**2: reason='SOFTWARE_DISK_LIMIT'
            elif len(output)>1024*1024: reason='LOG_LIMIT'
            if reason: break
    except BaseException as error:
        reason='MONITOR_EXCEPTION_'+type(error).__name__
    finally:
        selector.close()
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=3)
    code=process.returncode
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt={'state':'COMPLETED' if code==0 and reason is None else 'FAILED','returncode':code,'limit_reason':reason,
             'wall_seconds':time.monotonic()-START,'CPU_seconds':time.process_time()+child.ru_utime+child.ru_stime,
             'peak_sampled_combined_RSS_bytes':peak,'sample_poll_seconds':.05,'numerical_threads':2,
             'process_CPU_accounting':'live group utime+stime+reaped-child times; final waited rusage',
             'wall_accounting':'observed monotonic after stdlib imports; external timeout240s covers startup',
             'software_environment_and_wheel_bytes':retained,'NFL_semantic_reads_fits_predictions_outcomes_scores':0}
    # Persist only bounded software logs/metadata using the unchanged global quota.
    from direct_boosters_capability import storage_for
    store=storage_for(spec)
    store.write_bytes(Path(spec['output'])/'outer-process.log',bytes(output[:1024*1024]))
    receipt['wall_seconds']=time.monotonic()-START
    receipt['CPU_seconds']=time.process_time()+child.ru_utime+child.ru_stime
    if receipt['wall_seconds']>=240 or receipt['CPU_seconds']>=180:
        receipt.update(state='FAILED',limit_reason=receipt['limit_reason'] or 'FINAL_RESOURCE_LIMIT')
    store.atomic_json(Path(spec['output'])/'outer-completion.json',receipt)
    print(json.dumps(receipt,sort_keys=True))
    if receipt['state']!='COMPLETED': raise SystemExit(1)


if __name__=='__main__': main()
