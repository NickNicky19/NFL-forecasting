"""Authenticate a sealed report-only environment before importing helpers."""
import ctypes
import os
import signal
import sys


def arm_parent_death(expected):
    """Linux parent-death guard, including the fork-to-prctl race check."""
    if not isinstance(expected,int) or expected<=1 or os.getppid()!=expected:
        raise RuntimeError("guarded reporting parent is absent")
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:
        raise OSError(ctypes.get_errno(),"PR_SET_PDEATHSIG failed")
    if os.getppid()!=expected:
        os.kill(os.getpid(),signal.SIGKILL)


ARMED_PARENT=None
if __name__=="__main__":
    # Arm before dependency/environment verification or statistical imports.
    try:
        ARMED_PARENT=int(sys.argv[sys.argv.index("--parent-pid")+1])
    except (ValueError,IndexError):
        raise SystemExit("explicit guarded parent PID required")
    arm_parent_death(ARMED_PARENT)

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import stat


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def pin(item):
    path=Path(item["path"])
    if (not path.is_absolute() or str(path.resolve())!=str(path) or
            any(p.is_symlink() for p in (path,*path.parents))):
        raise ValueError("canonical nonsymlink binding required")
    info=path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size!=item["bytes"] or
            [info.st_dev,info.st_ino]!=item["inode"] or oct(info.st_mode)!=item["mode"] or
            sha(path)!=item["sha256"]):
        raise ValueError("frozen bytes/identity changed: "+str(path))


def load(path,expected):
    if sha(path)!=expected:
        raise ValueError("report execution freeze changed")
    freeze=json.loads(Path(path).read_text())
    seal=freeze.get("seal",{})
    if (freeze.get("state")!="SEALED_ROOT_AND_REVIEWER" or seal.get("integrator")!="/root" or
            not isinstance(seal.get("reviewer"),str) or not seal["reviewer"].startswith("/root/") or
            freeze.get("preexec_review")!="PASS"):
        raise ValueError("independent PREEXEC PASS and integrator seal required")
    return freeze


def verify(freeze):
    bindings=freeze["bindings"]
    paths=[item["path"] for item in bindings]
    if len(paths)!=len(set(paths)):
        raise ValueError("duplicate frozen binding")
    required={str(p) for p in (Path(freeze["code_root"])/"nfl_lab").glob("*.py")}
    required|={freeze["plan_path"],*(x["path"] for x in freeze["tools"].values())}
    if not required<=set(paths):
        raise ValueError("complete original helper/tool/plan bindings required")
    for item in bindings:
        pin(item)
    if freeze["external_timeout"]["path"]!="/usr/bin/timeout":
        raise ValueError("exact external timeout executable required")
    pin(freeze["external_timeout"])
    if sha(freeze["plan_path"])!=freeze["plan_sha256"]:
        raise ValueError("registered report plan changed")
    policy=json.loads(Path(freeze["plan_path"]).read_text())
    if freeze["plan_sha256"]!="7789249bdf56d7767ae87eea69184b0a1ea18d63db564e4fe4d1a83181b55e26":
        raise ValueError("different separately preregistered report-only policy")
    plan=dict(freeze["execution_metadata"])
    plan.update(registration_id=policy["registration_id"],state="REGISTERED",budgets=policy["budgets"])
    if (plan["parent_root"]!=policy["original_output"] or plan["output"]!=policy["output"]):
        raise ValueError("policy output namespaces differ")
    for name,key in (("parent_forecast_freeze","forecast-freeze.json"),
            ("parent_scored_freeze","scored-freeze.json"),
            ("parent_completion","screen-supervisor-completion.json"),
            ("control_scored_freeze","original_control_scored_freeze"),
            ("parent_execution_freeze","original_execution_freeze"),
            ("parent_config","original_science_config")):
        if plan[name]["sha256"]!=policy["required_inputs"][key]:
            raise ValueError("immutable report policy input identity differs")
    for name in ("parent_config","parent_execution_freeze","parent_forecast_freeze",
            "parent_scored_freeze","parent_completion","control_scored_freeze",
            "category_contract","source_policy"):
        item=plan[name]
        if item["path"] not in paths or sha(item["path"])!=item["sha256"]:
            raise ValueError("complete original metadata binding required: "+name)
    if freeze["output"]!=plan["output"] or freeze["cache"]!=plan["cache"]:
        raise ValueError("new report namespace differs")
    environment=freeze["environment"]
    if sys.executable!=environment["executable"] or sys.version!=environment["python"]:
        raise ValueError("exact original Python required")
    if not environment["file_bindings"]:
        raise ValueError("complete environment file freeze required")
    for item in environment["file_bindings"]:
        pin(item)
    for name,version in environment["packages"].items():
        if importlib.metadata.version(name)!=version:
            raise ValueError("frozen dependency changed: "+name)
    for name,expected in (("direct_booster_screen.py","a47a5a21910a132977bda33ad531ba4c82b24cc9120143d40e3b415f32b84016"),
            ("direct_boosters.py","475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f")):
        if sha(Path(freeze["code_root"])/"nfl_lab"/name)!=expected:
            raise ValueError("unchanged original aggregation helpers required")
    return plan


def args():
    parser=argparse.ArgumentParser()
    parser.add_argument("--freeze",required=True)
    parser.add_argument("--freeze-sha256",required=True)
    parser.add_argument("--parent-pid",type=int)
    return parser.parse_args()


def main():
    supplied=args()
    if supplied.parent_pid!=ARMED_PARENT or ARMED_PARENT is None or os.getppid()!=ARMED_PARENT:
        raise RuntimeError("report worker parent-death guard was not armed")
    def no_network(event,arguments):
        if event.startswith("socket."):
            raise RuntimeError("report-only forbids network")
    sys.addaudithook(no_network)
    freeze=load(supplied.freeze,supplied.freeze_sha256)
    plan=verify(freeze)
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT"):
        os.environ[name]="2"
    sys.path.insert(0,freeze["code_root"])
    from direct_booster_frozen_report import run
    run(plan,plan_sha256=freeze["plan_sha256"],final_static=lambda:verify(freeze))
    print(json.dumps(dict(phase="REPORT_COMPLETE",targets=12,new_fits_predictions_law_calls_source_label_reads_HTTP=0)),flush=True)


if __name__=="__main__":
    main()
