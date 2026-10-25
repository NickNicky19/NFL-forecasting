"""Frozen run/report caller; no extra learner, evaluator, or source pipeline."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import sys
import time


def sha(path):
    with Path(path).open("rb") as stream: return hashlib.file_digest(stream,"sha256").hexdigest()


def load_freeze(path, expected):
    path=Path(path)
    if sha(path)!=expected: raise ValueError("execution freeze changed")
    freeze=json.loads(path.read_text())
    if freeze["state"]!="SEALED_ROOT_AND_REVIEWER": raise ValueError("template/unreviewed freeze cannot execute")
    if freeze["seal"]!={"integrator":"/root","reviewer":"/root/reference_independent_reviewer"}:
        raise ValueError("separate root/reviewer seal required")
    return freeze


def verify(freeze):
    code=Path(freeze["code_root"])
    bindings={item["path"]:item for item in freeze["bindings"]}
    required={str(p) for p in (code/"nfl_lab").glob("*.py")}
    required|={freeze["plan_path"],*(item["path"] for item in freeze["tools"].values())}
    plan=json.loads(Path(freeze["plan_path"]).read_text())
    if sha(freeze["plan_path"])!=freeze["plan_sha256"]: raise ValueError("screen config changed")
    for key in ("input_features","source_manifest","source_policy","category_contract","control_scored_freeze","capability_installation"):
        required.add(plan[key]["path"])
    required|={item["path"] for item in plan["partition_audits"].values()}
    required.add(freeze["environment"]["inventory_path"])
    if not required<=set(bindings) or not freeze["environment"]["file_bindings"]:
        raise ValueError("complete code/config/input/environment bindings required")
    for item in [*freeze["bindings"],*freeze["environment"]["file_bindings"]]:
        path=Path(item["path"])
        if not path.is_absolute() or ".." in path.parts or str(path.resolve())!=str(path):
            raise ValueError("noncanonical frozen path")
        if any(p.is_symlink() for p in (path,*path.parents)) or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("frozen member must be regular and nonsymlink")
        info=path.stat()
        if (info.st_size!=item["bytes"] or [info.st_dev,info.st_ino]!=item["inode"]
                or oct(info.st_mode)!=item["mode"] or sha(path)!=item["sha256"]):
            raise ValueError("frozen member bytes changed: "+str(path))
    env=freeze["environment"]
    if sys.executable!=env["executable"] or sys.version!=env["python"]:
        raise ValueError("wrong exact Python environment")
    for name,version in env["packages"].items():
        if importlib.metadata.version(name)!=version: raise ValueError("dependency version changed: "+name)
    expected={"max_wall_seconds":1500,"max_CPU_seconds":2400,"max_RSS_bytes":2147483648,
              "max_fit_attempts":198,"per_estimator_wall_seconds":30,"per_estimator_CPU_seconds":45,
              "max_HTTP_attempts":0,"threads":2,"max_shared_retained_unique_file_bytes":536870912}
    if any(plan["budgets"].get(k)!=v for k,v in expected.items()): raise ValueError("screen limits changed")
    if freeze["output"]!=plan["output"] or freeze["cache"]!=plan["cache"]: raise ValueError("namespace mismatch")
    return plan


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--freeze",required=True);parser.add_argument("--freeze-sha256",required=True)
    args=parser.parse_args();freeze=load_freeze(args.freeze,args.freeze_sha256)
    def no_network(event,args):
        if event in {"socket.connect","socket.connect_ex","socket.getaddrinfo"}: raise RuntimeError("zero HTTP/network screen")
    sys.addaudithook(no_network)
    plan=verify(freeze)
    sys.path.insert(0,freeze["code_root"])
    from nfl_lab.operational_storage import OperationalStorage
    policy=json.loads(Path(plan["source_policy"]["path"]).read_text())
    storage=OperationalStorage(plan["cache"],policy)
    output=storage.register_root(plan["output"])
    if (output/"screen-supervisor-consumed.json").exists(): raise ValueError("sole invocation already consumed")
    storage.atomic_json(output/"screen-supervisor-consumed.json",{"invocations":1,"freeze_sha256":args.freeze_sha256})
    proc=Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()
    storage.atomic_json(output/"runtime-process.json",{"pid":os.getpid(),"group_id":os.getpgrp(),
        "process_start_ticks":int(proc[19]),"monotonic_start":time.monotonic()})
    from nfl_lab.direct_booster_screen import run_screen,report_screen
    result=run_screen(freeze["plan_path"],config_sha256=freeze["plan_sha256"])
    print(json.dumps({"phase":"GLOBAL_FORECASTS_FROZEN","fatal":result["fatal"],"usage":result["usage"],"slots":len(result["slots"])}),flush=True)
    report=report_screen(freeze["plan_path"],config_sha256=freeze["plan_sha256"])
    verify(freeze)
    storage.atomic_json(output/"runtime-completed.json",{"state":"COMPLETED","targets":len(report["targets"]),
        "registration_sha256":freeze["plan_sha256"],"evidence":"EXPOSED_SOURCE_MATCHED_DEVELOPMENT"})
    print(json.dumps({"phase":"REPORT_COMPLETE","targets":len(report["targets"])}),flush=True)


if __name__=="__main__": main()
