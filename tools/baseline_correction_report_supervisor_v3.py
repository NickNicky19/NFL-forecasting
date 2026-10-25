"""300-second compact frozen reporting completion with unchanged explicit-PID accounting."""
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
sys.path.insert(0,"/workspace/nfl-baseline-correction-v1/tools")
sys.path.insert(0,"/workspace/nfl-baseline-correction-report-v2/tools")
from offline_report_imports_v1 import offline_dependency_imports


def main():
    from baseline_correction_report_run_v3 import arguments,load,verify,extension
    from direct_booster_frozen_report_supervisor import usage
    args=arguments()
    def deny(event,values):
        if event.startswith("socket."):raise RuntimeError("report-only network forbidden")
    sys.addaudithook(deny)
    freeze=load(args.freeze,args.freeze_sha256);spec=verify(freeze)
    external=Path("/proc",str(os.getppid()))
    expected=[freeze["external_timeout"]["path"],"--signal=KILL","--kill-after=1s","300s",
        freeze["environment"]["executable"],"-B",freeze["tools"]["supervisor"]["path"],
        "--freeze",args.freeze,"--freeze-sha256",args.freeze_sha256]
    actual=[x.decode() for x in (external/"cmdline").read_bytes().rstrip(b"\0").split(b"\0")]
    if (external/"exe").resolve()!=Path(freeze["external_timeout"]["path"]) or actual!=expected:
        raise ValueError("exact pinned300s GNU timeout parent required")
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT","ARROW_IO_THREADS"):
        os.environ[name]="2"
    sys.path.insert(0,freeze["code_root"])
    with offline_dependency_imports():
        extension(spec["_inherited_execution"]["execution_metadata"]["correction_extension"])
        from baseline_correction_report_v3 import storage
    store,output=storage(spec)
    if (output/"report-v3-supervisor-consumed.json").exists():raise RuntimeError("sole reporting continuation consumed")
    store.atomic_json(output/"report-v3-supervisor-consumed.json",dict(invocations=1,freeze_sha256=args.freeze_sha256),replace=False)
    env={"PATH":"/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":freeze["code_root"]}
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT","ARROW_IO_THREADS"):env[name]="2"
    if "LD_LIBRARY_PATH" in os.environ:env["LD_LIBRARY_PATH"]=os.environ["LD_LIBRARY_PATH"]
    command=[freeze["environment"]["executable"],"-B",freeze["tools"]["run"]["path"],
        "--freeze",args.freeze,"--freeze-sha256",args.freeze_sha256,"--parent-pid",str(os.getpid())]
    process=subprocess.Popen(command,cwd=freeze["code_root"],env=env,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,start_new_session=True)
    worker_start=int(Path("/proc",str(process.pid),"stat").read_text().rsplit(")",1)[1].split()[19])
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    log=bytearray();peak=peak_cpu=0;reason=None
    try:
        while process.poll() is None or selector.get_map():
            for key,_ in selector.select(timeout=.1):
                body=os.read(key.fileobj.fileno(),65536)
                if body:log.extend(body)
                else:selector.unregister(key.fileobj)
            rss,cpu=usage(process,worker_start)
            own=Path("/proc/self/stat").read_text().rsplit(")",1)[1].split();own_rss=int(own[21])*os.sysconf("SC_PAGE_SIZE")
            if own_rss<=0:raise RuntimeError("known supervisor RSS absent")
            rss+=own_rss;cpu+=time.process_time();peak=max(peak,rss);peak_cpu=max(peak_cpu,cpu)
            if time.monotonic()-START>=295:reason="WALL_LIMIT"
            elif cpu>=295:reason="CPU_LIMIT"
            elif rss>=1073741824-24*1024**2:reason="RSS_LIMIT"
            elif len(log)>1048576:reason="LOG_LIMIT"
            elif (output/"estimator-cpu-guard.json").exists():reason="FORBIDDEN_ESTIMATOR_GUARD"
            elif os.statvfs(output).f_bavail==0:reason="PHYSICAL_DISK_FULL"
            if reason:break
    except BaseException as error:reason="MONITOR_EXCEPTION_"+type(error).__name__
    finally:
        selector.close()
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=3);process.stdout.close()
    children=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt=dict(state="COMPLETED" if process.returncode==0 and reason is None and (output/"report.json").exists() else "FAILED",
        returncode=process.returncode,limit_reason=reason,wall_seconds=time.monotonic()-START,
        CPU_seconds=max(peak_cpu,time.process_time()+children.ru_utime+children.ru_stime),
        peak_sampled_combined_RSS_bytes=peak,child_ru_maxrss_bytes=children.ru_maxrss*1024,
        RSS_scope="explicit known worker/supervisor plus group; child ru_maxrss cross-check; sampling may miss brief peaks",
        worker_pid=process.pid,worker_start_ticks=worker_start,threads=2,
        new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0,retention=store.report_retention(),prior_executions="SCIENTIFIC_PARENT_AND_V2_FAILED_UNCHANGED")
    store.write_bytes(output/"report-v3-supervisor.log",bytes(log[:1048576]),replace=False)
    receipt["wall_seconds"]=time.monotonic()-START
    receipt["CPU_seconds"]=max(peak_cpu,time.process_time()+children.ru_utime+children.ru_stime)
    if receipt["wall_seconds"]>=300 or receipt["CPU_seconds"]>=300 or children.ru_maxrss*1024>=1073741824:
        receipt.update(state="FAILED",limit_reason=reason or "FINAL_RESOURCE_LIMIT")
    store.atomic_json(output/"report-v3-supervisor-completion.json",receipt,replace=False)
    print(json.dumps(receipt),flush=True)
    if receipt["state"]!="COMPLETED":raise SystemExit(1)


if __name__=="__main__":main()
