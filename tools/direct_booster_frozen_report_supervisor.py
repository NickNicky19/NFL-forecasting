"""Independent 600-second/600-CPU process-tree guard; external timeout600s.

The worker is a direct child, avoiding the original nested-timeout orphan
reaping gap. The final receipt retains both reaped and peak-observed CPU.
"""
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


def external_guard(freeze,supplied):
    """Require the exact pinned GNU timeout as this supervisor's live parent."""
    parent=Path("/proc")/str(os.getppid())
    executable=(parent/"exe").resolve()
    if executable!=Path(freeze["external_timeout"]["path"]):
        raise ValueError("independent frozen external GNU timeout parent required")
    command=(parent/"cmdline").read_bytes().rstrip(b"\0").split(b"\0")
    actual=[part.decode("utf-8") for part in command]
    expected=[freeze["external_timeout"]["path"],"--signal=KILL","--kill-after=1s","600s",
        freeze["environment"]["executable"],"-B",freeze["tools"]["supervisor"]["path"],
        "--freeze",supplied.freeze,"--freeze-sha256",supplied.freeze_sha256]
    if actual!=expected:
        raise ValueError("external timeout argv differs from exact frozen invocation")
    info=(parent/"stat").read_text().rsplit(")",1)[1].split()
    return dict(pid=os.getppid(),process_start_ticks=int(info[19]),
        executable_sha256=freeze["external_timeout"]["sha256"],duration_seconds=600)


def usage(process,worker_start_ticks):
    group=process.pid
    rss=cpu=0
    # Read the known worker explicitly; /proc directory enumeration alone is
    # not sufficient evidence that a live worker was included in accounting.
    try:
        worker=Path("/proc",str(group),"stat").read_text().rsplit(")",1)[1].split()
    except FileNotFoundError:
        if process.poll() is None:
            raise RuntimeError("live known worker absent from /proc accounting")
        worker=None
    if worker is not None:
        if int(worker[2])!=group or int(worker[19])!=worker_start_ticks:
            raise RuntimeError("known worker process identity changed")
        rss=int(worker[21])*os.sysconf("SC_PAGE_SIZE")
        if worker[0]!="Z" and rss<=0:
            raise RuntimeError("live known worker RSS unavailable")
        cpu=sum(int(worker[i]) for i in (11,12,13,14))/os.sysconf("SC_CLK_TCK")
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit() or directory.name==str(group):
            continue
        try:
            values=(directory/"stat").read_text().rsplit(")",1)[1].split()
            if int(values[2])==group:
                rss+=int(values[21])*os.sysconf("SC_PAGE_SIZE")
                cpu+=sum(int(values[i]) for i in (11,12,13,14))/os.sysconf("SC_CLK_TCK")
        except (OSError,ValueError,IndexError):
            continue
    return rss,cpu


def main():
    from direct_booster_frozen_report_run import args,load,verify,sha
    supplied=args()
    def no_network(event,arguments):
        if event.startswith("socket."):
            raise RuntimeError("report-only supervisor forbids network")
    sys.addaudithook(no_network)
    freeze=load(supplied.freeze,supplied.freeze_sha256)
    plan=verify(freeze)
    parent_guard=external_guard(freeze,supplied)
    # Verify budgets before constructing any writable storage handle.
    sys.path.insert(0,freeze["code_root"])
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT"):
        os.environ[name]="2"
    from direct_booster_frozen_report import LIMITS,VERSION,cap_output
    if plan["registration_id"]!=VERSION or plan["state"]!="REGISTERED" or plan["budgets"]!=LIMITS:
        raise ValueError("changed/unregistered finite report budget")
    from nfl_lab.operational_storage import OperationalStorage
    storage=OperationalStorage(plan["cache"],json.loads(Path(plan["source_policy"]["path"]).read_text()))
    output=storage.register_root(plan["output"])
    cap_output(storage,output)
    if (output/"report-supervisor-consumed.json").exists():
        raise RuntimeError("one report invocation already consumed; no retry")
    storage.atomic_json(output/"report-supervisor-consumed.json",dict(at=time.time(),invocations=1,
        execution_freeze_sha256=supplied.freeze_sha256,external_timeout_parent=parent_guard),replace=False)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONPATH=freeze["code_root"])
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT"):
        env[name]="2";os.environ[name]="2"
    command=[freeze["environment"]["executable"],"-B",freeze["tools"]["run"]["path"],
        "--freeze",supplied.freeze,"--freeze-sha256",supplied.freeze_sha256,
        "--parent-pid",str(os.getpid())]
    process=subprocess.Popen(command,cwd=freeze["code_root"],env=env,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,start_new_session=True)
    initial_worker=Path("/proc",str(process.pid),"stat").read_text().rsplit(")",1)[1].split()
    worker_start_ticks=int(initial_worker[19])
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    log=bytearray();reason=None;peak=0;peak_cpu=0
    try:
        while process.poll() is None or selector.get_map():
            for key,_ in selector.select(timeout=.1):
                body=os.read(key.fileobj.fileno(),65536)
                if body:log.extend(body)
                else:selector.unregister(key.fileobj)
            rss,cpu=usage(process,worker_start_ticks)
            own=Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()
            own_rss=int(own[21])*os.sysconf("SC_PAGE_SIZE")
            if own_rss<=0:
                raise RuntimeError("known supervisor RSS unavailable")
            rss+=own_rss
            cpu+=time.process_time()
            peak=max(peak,rss);peak_cpu=max(peak_cpu,cpu)
            if time.monotonic()-START>=595:reason="WALL_LIMIT"
            elif cpu>=595:reason="CPU_LIMIT"
            elif rss>=2147483648-24*1024**2:reason="RSS_LIMIT"
            elif len(log)>1048576:reason="LOG_LIMIT"
            elif (output/"estimator-cpu-guard.json").exists():reason="FORBIDDEN_ESTIMATOR_GUARD"
            elif os.statvfs(output).f_bavail==0:reason="PHYSICAL_DISK_FULL"
            if reason:break
    except BaseException as error:
        reason="MONITOR_EXCEPTION_"+type(error).__name__
    finally:
        selector.close()
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=3)
        process.stdout.close()
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    reaped=time.process_time()+child.ru_utime+child.ru_stime
    report_exists=(output/"report.json").exists()
    receipt=dict(state="COMPLETED" if process.returncode==0 and reason is None and report_exists else "FAILED",
        returncode=process.returncode,limit_reason=reason,wall_seconds=time.monotonic()-START,
        CPU_seconds=max(reaped,peak_cpu),reaped_CPU_seconds=reaped,peak_observed_CPU_seconds=peak_cpu,
        CPU_scope="supervisor plus direct worker/process group; max(reaped, peak sampled)",
        peak_sampled_combined_RSS_bytes=peak,child_ru_maxrss_bytes=child.ru_maxrss*1024,
        RSS_scope="sampled simultaneous group plus supervisor; child ru_maxrss cross-check; sampling may miss brief peaks",
        sample_poll_seconds=.1,threads=2,
        new_fits_predictions_law_calls_source_label_reads_HTTP=0,
        original_run_state="FAILED",report_exists=report_exists,
        external_timeout_parent=parent_guard,worker_parent_death_signal="SIGKILL; parent PID race checked",
        known_worker_pid=process.pid,known_worker_start_ticks=worker_start_ticks,
        retention=storage.report_retention(),
        RSS_accounting="explicit known worker and supervisor reads plus other enumerated group members; live known PID omission fails closed")
    storage.write_bytes(output/"report-supervisor.log",bytes(log[:1048576]),replace=False)
    receipt["wall_seconds"]=time.monotonic()-START
    receipt["CPU_seconds"]=max(peak_cpu,time.process_time()+child.ru_utime+child.ru_stime)
    if child.ru_maxrss*1024>=2147483648:
        receipt.update(state="FAILED",limit_reason=reason or "FINAL_CHILD_RSS_LIMIT")
    if receipt["wall_seconds"]>=600 or receipt["CPU_seconds"]>=600:
        receipt.update(state="FAILED",limit_reason=reason or "FINAL_RESOURCE_LIMIT")
    storage.atomic_json(output/"report-supervisor-completion.json",receipt,replace=False)
    print(json.dumps(receipt),flush=True)
    if receipt["state"]!="COMPLETED":
        raise SystemExit(1)


if __name__=="__main__":
    main()
