"""Fresh-process calibration startup check; stdlib until strict guards enter.

No input frame, model fit, inference or score is permitted. The accepted
process_free_threads helper resolves only the already mapped, pinned ELF libc.
Its normal context exit restores threadpoolctl.find_library exactly.
"""
from contextlib import contextmanager
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

VERSION="anytime-calibration-startup-v1-20261025"
THREAD_VARS=("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS",
             "VECLIB_MAXIMUM_THREADS","OMP_THREAD_LIMIT","ARROW_IO_THREADS")


class StartupGuardError(BaseException): pass


def pin(binding):
    path=Path(binding["path"])
    if (not path.is_absolute() or path.resolve()!=path or any(p.is_symlink() for p in [path,*path.parents])
            or not path.is_file() or path.stat().st_size!=binding["bytes"]):
        raise StartupGuardError("startup binding identity changed")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest()!=binding["sha256"]:
            raise StartupGuardError("startup binding SHA256 changed")
    return path


def libc_identity(binding):
    path=pin(binding);info=path.stat()
    with path.open("rb") as stream:
        if stream.read(4)!=b"\x7fELF":raise StartupGuardError("pinned libc is not ELF")
    device=f"{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x}"
    mapped=[]
    for line in Path("/proc/self/maps").read_text().splitlines():
        fields=line.split()
        if len(fields)>=6 and fields[-1]==str(path):
            if fields[3]!=device or int(fields[4])!=info.st_ino:
                raise StartupGuardError("mapped libc device/inode differs from pinned ELF")
            mapped.append(fields[1])
    if not mapped or not any("x" in permissions for permissions in mapped):
        raise StartupGuardError("pinned libc is not already executable-mapped")
    return dict(path=str(path),sha256=binding["sha256"],bytes=info.st_size,
                device=device,inode=info.st_ino,mapped_segments=len(mapped),executable_mapping=True)


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    loaded=importlib.util.module_from_spec(spec);sys.modules[name]=loaded;spec.loader.exec_module(loaded)
    return loaded


@contextmanager
def guarded_threads(threadpoolctl,libc,helper_binding):
    identity=libc_identity(libc)
    helper_path=pin(helper_binding)
    helper=module(helper_path,"_anytime_accepted_thread_helper")
    original=threadpoolctl.find_library
    with helper.process_free_threads(threadpoolctl,libc):
        # The reviewed helper itself rejects every resolver name except 'c'.
        if threadpoolctl.find_library("c")!=libc["path"]:
            raise StartupGuardError("exact libc resolver changed")
        yield identity
    if threadpoolctl.find_library is not original:
        raise StartupGuardError("thread library resolver was not restored")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("freeze");parser.add_argument("sha256");parser.add_argument("--receipt",required=True);args=parser.parse_args()
    started=time.monotonic();cpu=time.process_time();phase="authenticate_startup_metadata"
    freeze_path=Path(args.freeze)
    if hashlib.sha256(freeze_path.read_bytes()).hexdigest()!=args.sha256:
        raise StartupGuardError("startup metadata SHA mismatch")
    freeze=json.loads(freeze_path.read_text())
    if freeze.get("version")!=VERSION:raise StartupGuardError("wrong startup packet")
    for binding in freeze["code"].values():pin(binding)
    for key in ["runner","calibrator","helper","libc"]:pin(freeze[key])
    output=Path(args.receipt)
    descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    counts=dict(child_attempts=0,socket_attempts=0,forbidden_input_reads=0,scientific_calls=0)
    receipt=dict(version=VERSION,freeze_sha256=args.sha256,pid=os.getpid(),state="FAILED",phase=phase,
                 counts=counts,libc=None,resolver_restored=False)
    def guard(event,values):
        if event.startswith("socket."):
            counts["socket_attempts"]+=1;raise StartupGuardError("startup socket forbidden")
        if event in {"subprocess.Popen","os.system","os.fork","os.forkpty","os.posix_spawn","os.exec","pty.spawn"}:
            counts["child_attempts"]+=1;raise StartupGuardError("startup child/process forbidden")
        if event=="open" and isinstance(values[0],(str,bytes,os.PathLike)):
            name=os.fsdecode(values[0])
            if "/website-methods-research/" in name or name.endswith((".parquet",".csv",".joblib")):
                counts["forbidden_input_reads"]+=1;raise StartupGuardError("startup NFL/model input forbidden")
    def scientific(frame,event,_argument):
        if (event=="call" and frame.f_code.co_name in {"fit","predict","predict_proba","run","load_forecasts","load_labels","binary_losses","summary","paired"}
                and ("/nfl_lab/" in frame.f_code.co_filename or frame.f_code.co_filename==freeze["runner"]["path"])):
            counts["scientific_calls"]+=1;raise StartupGuardError("startup scientific call forbidden")
    try:
        def expired(*_):raise StartupGuardError("finite startup smoke deadline")
        signal.signal(signal.SIGALRM,expired);signal.signal(signal.SIGXCPU,expired)
        signal.alarm(28);resource.setrlimit(resource.RLIMIT_CPU,(28,30))
        resource.setrlimit(resource.RLIMIT_AS,(8589934592,8589934592))
        for name in THREAD_VARS:os.environ[name]="2"
        sys.dont_write_bytecode=True
        sys.addaudithook(guard);sys.setprofile(scientific)
        phase="import_threadpoolctl_with_guards"
        import threadpoolctl
        original=threadpoolctl.find_library
        phase="enter_pinned_resolver"
        with guarded_threads(threadpoolctl,freeze["libc"],freeze["helper"]) as identity:
            receipt["libc"]=identity
            phase="import_exact_calibration_runner_with_guards"
            runner=module(freeze["runner"]["path"],"_anytime_fresh_startup_runner")
            if runner.VERSION!="anytime-calibration-v1-20261025":raise StartupGuardError("wrong runner imported")
            phase="import_numerical_runtime_under_pinned_guard"
            runner.load_runtime()
            if Path(sys.modules["nfl_lab.anytime_calibration"].__file__).resolve()!=Path(freeze["calibrator"]["path"]):
                raise StartupGuardError("wrong calibrator module imported")
            phase="enter_threadpool_limits_without_children"
            with threadpoolctl.threadpool_limits(limits=2):
                information=threadpoolctl.threadpool_info()
                if any(item.get("num_threads",0)>2 for item in information):raise StartupGuardError("native thread ceiling exceeded")
                if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>2147483648:raise StartupGuardError("startup RSS ceiling exceeded")
                receipt["native_pools"]=[{key:item.get(key) for key in ["internal_api","num_threads","version"]} for item in information]
        receipt.update(state="PASS",resolver_restored=threadpoolctl.find_library is original)
        phase="completed_and_resolver_restored"
    except BaseException as error:
        receipt.update(exception=type(error).__name__,detail=str(error),traceback=traceback.format_exc())
    finally:
        signal.alarm(0)
        sys.setprofile(None)
        receipt.update(phase=phase,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,
                       peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        data=(json.dumps(receipt,indent=2,allow_nan=False)+"\n").encode()
        try:
            if len(data)>65536:raise StartupGuardError("startup receipt too large")
            pending=memoryview(data)
            while pending:pending=pending[os.write(descriptor,pending):]
            os.fsync(descriptor)
        finally:os.close(descriptor)
    raise SystemExit(0 if receipt["state"]=="PASS" else 1)


if __name__=="__main__":main()
