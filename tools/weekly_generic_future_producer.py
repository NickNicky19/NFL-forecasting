"""Root-sealed native entry; no source/model action without explicit execution."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import time


def _main(*,backend_factory=None,plan_validator=None,diagnostics=False):
    def phase(name):
        if diagnostics:
            from nfl_lab.weekly_inference_diagnostics_v1 import checkpoint
            checkpoint(name)
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",type=Path,required=True);parser.add_argument("--plan-sha256",required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args();phase("PLAN_PIN");body=args.plan.read_bytes()
    if hashlib.sha256(body).hexdigest()!=args.plan_sha256:raise ValueError("exact producer plan required")
    plan=json.loads(body)
    if not args.execute:
        print(json.dumps(dict(state="PREPARATION_ONLY",execution=False,root_seal_required=True)))
        return 0
    if (plan.get("state")!="FROZEN_ROOT_REVIEWER_SEALED" or plan.get("execution_authorized") is not True
        or plan.get("review",{}).get("status")!="PREEXEC_PASS" or plan["review"].get("integrator")!="/root"):
        raise ValueError("unsealed preparation is not source/model/runtime authority")
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    from nfl_lab.weekly_generic_producer import LIMITS,validate_plan,now_utc
    phase("PLAN_VALIDATE")
    validate_plan(plan,now=now_utc())
    phase("ENVIRONMENT")
    for name,value in plan["numerical_environment"].items():
        if os.environ.get(name)!=value:raise ValueError("exact numerical environment required before imports")
    started,cpu=time.monotonic(),time.process_time()
    phase("RESOURCE_GUARDS")
    resource.setrlimit(resource.RLIMIT_CPU,(LIMITS["CPU_seconds"],)*2)
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS["address_space_bytes"],)*2)
    def expired(*unused):raise TimeoutError("whole future producer wall allocation exhausted")
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,LIMITS["wall_seconds"])
    def audit(event,unused):
        if event.startswith(("socket.","subprocess.")) or event in {"os.fork","os.forkpty","os.exec","os.posix_spawn","os.system"}:
            raise RuntimeError("this source-adoption producer forbids HTTP and children")
    sys.addaudithook(audit)
    from tools.weekly_current_query import pin
    from tools.weekly_current_inference_capture import validate_interpreter_binding
    phase("CODE_PINS")
    for name,value in plan["code_pins"].items():pin(dict(path=str(root/name),sha256=value))
    for key in ("source_policy","interpreter","libc","rss_sampler"):
        pin(plan[key])
    phase("INTERPRETER");validate_interpreter_binding(plan)
    if plan_validator is not None:
        phase("ADAPTER_PLAN")
        plan_validator(plan,now=now_utc())
    phase("SAMPLER")
    spec=importlib.util.spec_from_file_location("generic_existing_pid_sampler",plan["rss_sampler"]["path"])
    sampler=importlib.util.module_from_spec(spec);spec.loader.exec_module(sampler)
    process=sampler.process_binding(os.getpid());stop=threading.Event()
    memory=dict(samples=0,sampled_peak_bytes=0,highwater_bytes=0)
    def check():
        rss,_=sampler.required_usage([process]);peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        memory["samples"]+=1;memory["sampled_peak_bytes"]=max(memory["sampled_peak_bytes"],rss);memory["highwater_bytes"]=max(memory["highwater_bytes"],peak)
        if max(rss,peak)>=LIMITS["RSS_bytes"]-33554432:raise MemoryError("unchanged physical RSS stop margin")
        if time.process_time()-cpu>=LIMITS["CPU_seconds"]-10:raise TimeoutError("finite producer finalization CPU reserve")
    def watch():
        while not stop.wait(.01):
            try:check()
            except BaseException:
                os.write(2,b'{"state":"FUTURE_PRODUCER_RESOURCE_STOP"}\n');os.kill(os.getpid(),signal.SIGKILL)
    check();watcher=threading.Thread(target=watch,daemon=True,name="future-existing-rss-monitor");watcher.start()
    try:
        phase("NUMERICAL_IMPORTS")
        import pyarrow as pa
        import threadpoolctl
        pa.set_cpu_count(2);pa.set_io_thread_count(2);pa.set_memory_pool(pa.system_memory_pool())
        from tools.ngboost_law_software_v1 import process_free_threads
        from nfl_lab.weekly_generic_producer import execute
        with process_free_threads(threadpoolctl,plan["libc"]),threadpoolctl.threadpool_limits(limits=2):
            phase("BACKEND_INIT")
            backend=backend_factory(plan,clock=now_utc,resource_check=check) if backend_factory is not None else None
            if diagnostics and backend is not None:backend.diagnostic_checkpoint=phase
            result=execute(plan,backend=backend,resource_check=check)
    finally:
        stop.set();watcher.join(timeout=.5)
    check();signal.setitimer(signal.ITIMER_REAL,0)
    if diagnostics:
        from nfl_lab.weekly_inference_diagnostics_v1 import summary,publish
        publish(summary(state=result["state"],result=result,resources=dict(CPU_seconds=time.process_time()-cpu,
            wall_seconds=time.monotonic()-started,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)))
    print(json.dumps(dict(state=result["state"],CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,
        RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,HTTP=0,fits=0,scores=0,website_activation=False)))
    return int(result["state"]!="LOCAL_FUTURE_SLATE_CAPTURED")


def main(*,backend_factory=None,plan_validator=None,diagnostics=False):
    if not diagnostics:return _main(backend_factory=backend_factory,plan_validator=plan_validator)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from nfl_lab.weekly_inference_diagnostics_v1 import checkpoint,summary,publish
    started,cpu=time.monotonic(),time.process_time()
    checkpoint("PRECHECK")
    try:return _main(backend_factory=backend_factory,plan_validator=plan_validator,diagnostics=True)
    except BaseException as error:
        publish(summary(error=error,resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,
            RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)));return 1


if __name__=="__main__":raise SystemExit(main())
