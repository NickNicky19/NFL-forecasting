"""Independent group/native-fit monitor. Requires external timeout1500s."""
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


def proc(pid):
    return Path("/proc",str(pid),"stat").read_text().rsplit(")",1)[1].split()


def usage(group):
    rss=cpu=0
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            v=path.read_text().rsplit(")",1)[1].split()
            if int(v[2])==group:
                rss+=int(v[21])*os.sysconf("SC_PAGE_SIZE")
                cpu+=sum(int(v[i]) for i in (11,12,13,14))/os.sysconf("SC_CLK_TCK")
        except (OSError,ValueError,IndexError): pass
    return rss,cpu


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--freeze",required=True);parser.add_argument("--freeze-sha256",required=True)
    args=parser.parse_args()
    # Authenticate helper bytes before importing their executable definitions.
    raw=Path(args.freeze).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.freeze_sha256: raise ValueError("freeze changed")
    initial=json.loads(raw)
    for item in initial["tools"].values():
        if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("frozen tool changed")
    from direct_booster_screen_run import load_freeze,sha
    from direct_booster_screen_guard import guard_reason
    freeze=load_freeze(args.freeze,args.freeze_sha256)
    if sha(__file__)!=freeze["tools"]["supervisor"]["sha256"] or sha(freeze["tools"]["guard"]["path"])!=freeze["tools"]["guard"]["sha256"]:
        raise ValueError("supervisor/guard changed")
    timeout=freeze["timeout"]
    if timeout["path"]!="/usr/bin/timeout" or sha(timeout["path"])!=timeout["sha256"]: raise ValueError("timeout changed")
    env=dict(os.environ)
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT"):
        env[name]="2";os.environ[name]="2"
    env.update(PYTHONDONTWRITEBYTECODE="1",PYTHONPATH=freeze["code_root"])
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    command=[timeout["path"],"--signal=KILL","--kill-after=1s",f"{max(1,1495-(time.monotonic()-START)):.3f}s",
             freeze["environment"]["executable"],"-B",freeze["tools"]["run"]["path"],"--freeze",args.freeze,"--freeze-sha256",args.freeze_sha256]
    process=subprocess.Popen(command,cwd=freeze["code_root"],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    output=Path(freeze["output"]);log=bytearray();reason=None;peak=0;previous=0;seen=False
    try:
        while process.poll() is None or selector.get_map():
            for key,_ in selector.select(timeout=.05):
                body=os.read(key.fileobj.fileno(),65536)
                if body: log.extend(body)
                else: selector.unregister(key.fileobj)
            marker=output/"estimator-cpu-guard.json"
            if marker.exists():
                seen=True
                identity=json.loads((output/"runtime-process.json").read_text())
                control=json.loads(marker.read_text())
                try:
                    v=proc(identity["pid"])
                except FileNotFoundError:
                    if control.get("active") or not (output/"runtime-completed.json").exists(): raise
                else:
                    if int(v[2])!=process.pid or int(v[19])!=identity["process_start_ticks"]:
                        raise ValueError("runtime PID/group identity changed")
                    limit,previous=guard_reason(control,child_pid=identity["pid"],process_start_ticks=identity["process_start_ticks"],
                        cpu_now=(int(v[11])+int(v[12]))/os.sysconf("SC_CLK_TCK"),monotonic_now=time.monotonic(),previous_attempt=previous)
                    reason=reason or limit
            elif seen:
                reason="ESTIMATOR_GUARD_DISAPPEARED"
            rss,cpu=usage(process.pid)
            rss+=int(proc(os.getpid())[21])*os.sysconf("SC_PAGE_SIZE")
            peak=max(peak,rss)
            if time.monotonic()-START>=1496: reason=reason or "WALL_LIMIT"
            elif cpu+time.process_time()>=2398: reason=reason or "CPU_LIMIT"
            elif rss>=2147483648-24*1024**2: reason=reason or "RSS_LIMIT"
            elif len(log)>1024*1024: reason=reason or "LOG_LIMIT"
            # The unchanged global writer enforces the512MiB prewrite peak;
            # this independent free-space check detects a full physical disk.
            if os.statvfs(output if output.exists() else output.parent).f_bavail==0:
                reason=reason or "PHYSICAL_DISK_FULL"
            if reason: break
    except BaseException as error:
        reason="MONITOR_EXCEPTION_"+type(error).__name__
    finally:
        selector.close()
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=3)
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt={"state":"COMPLETED" if process.returncode==0 and not reason else "FAILED","returncode":process.returncode,
        "limit_reason":reason,"wall_seconds":time.monotonic()-START,"CPU_seconds":time.process_time()+child.ru_utime+child.ru_stime,
        "peak_sampled_combined_RSS_bytes":peak,"sample_poll_seconds":.05,"last_observed_estimator_attempt":previous,
        "threads":2,"new_HTTP_attempts":0,"official_forecast_or_confirmation_claims":0}
    # Bootstrap, all source/model work and every quota write above are guarded.
    # Final bounded failure evidence is retained through the same global quota.
    sys.path.insert(0,freeze["code_root"])
    from nfl_lab.operational_storage import OperationalStorage
    plan=json.loads(Path(freeze["plan_path"]).read_text());policy=json.loads(Path(plan["source_policy"]["path"]).read_text())
    storage=OperationalStorage(freeze["cache"],policy);storage.register_root(output)
    storage.write_bytes(output/"screen-supervisor.log",bytes(log[:1024*1024]))
    receipt["wall_seconds"]=time.monotonic()-START
    receipt["CPU_seconds"]=time.process_time()+child.ru_utime+child.ru_stime
    if receipt["wall_seconds"]>=1500 or receipt["CPU_seconds"]>=2400:
        receipt.update(state="FAILED",limit_reason=reason or "FINAL_RESOURCE_LIMIT")
    storage.atomic_json(output/"screen-supervisor-completion.json",receipt)
    print(json.dumps(receipt),flush=True)
    if receipt["state"]!="COMPLETED": raise SystemExit(1)


if __name__=="__main__": main()
