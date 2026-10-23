"""Sealed six-model replay caller; frozen original package plus one extension."""
import os
import sys
from direct_booster_frozen_report_run import arm_parent_death,pin,sha

ARMED_PARENT=None
if __name__=="__main__":
    try:ARMED_PARENT=int(sys.argv[sys.argv.index("--parent-pid")+1])
    except (ValueError,IndexError):raise SystemExit("explicit guarded parent PID required")
    arm_parent_death(ARMED_PARENT)

import argparse
import importlib.metadata
import json
from pathlib import Path

POLICY_SHA256="81fcf8f0f24090b048d6dce1e72517bb4f0aa0f8eb2ffabc913ccf5f0098ada8"
BUDGETS=dict(actual_invocations=1,wall_seconds=120,CPU_seconds=180,combined_RSS_bytes=1073741824,
    numerical_threads=2,new_retained_bytes=16777216,shared_retention_bytes=536870912,HTTP=0,
    new_fits=0,original_saved_models=6,query_prediction_row_incidences=60000,automatic_retries=0)


def arguments():
    parser=argparse.ArgumentParser();parser.add_argument("--freeze",required=True)
    parser.add_argument("--freeze-sha256",required=True);parser.add_argument("--parent-pid",type=int)
    return parser.parse_args()


def load(path,expected):
    if sha(path)!=expected:raise ValueError("binary recovery execution freeze changed")
    freeze=json.loads(Path(path).read_text());seal=freeze.get("seal",{})
    if (freeze.get("state")!="SEALED_ROOT_AND_REVIEWER" or freeze.get("preexec_review")!="PASS"
            or seal.get("integrator")!="/root" or not isinstance(seal.get("reviewer"),str)
            or not seal["reviewer"].startswith("/root/")):
        raise ValueError("root seal and independent PREEXEC PASS required")
    return freeze


def verify(freeze):
    if freeze["plan_sha256"]!=POLICY_SHA256 or sha(freeze["plan_path"])!=POLICY_SHA256:
        raise ValueError("exact preregistered binary replay policy required")
    policy=json.loads(Path(freeze["plan_path"]).read_text())
    if policy["budgets"]!=BUDGETS:raise ValueError("fixed one-shot binary replay budget changed")
    bindings={item["path"]:item for item in freeze["bindings"]}
    if len(bindings)!=len(freeze["bindings"]):raise ValueError("duplicate execution binding")
    metadata=freeze["execution_metadata"]
    required={str(path) for path in (Path(freeze["code_root"])/"nfl_lab").glob("*.py")}
    required|={freeze["plan_path"],*(item["path"] for item in freeze["tools"].values())}
    required|={v["path"] for v in metadata.values() if isinstance(v,dict) and "path" in v}
    required|={cell[name]["path"] for cell in metadata["cells"] for name in ("model","failure","query")}
    required|={item["path"] for item in metadata["donors"].values()}
    if not required<=set(bindings):raise ValueError("complete helper/config/tool metadata freeze required")
    for item in freeze["bindings"]:pin(item)
    for key,expected in policy["required_SHA256"].items():
        if metadata[key]["sha256"]!=expected or sha(metadata[key]["path"])!=expected:
            raise ValueError("frozen parent/canonicalizer identity differs: "+key)
    if (metadata["registration_id"]!=policy["registration_id"] or metadata["parent_config"]!=metadata["original_science_registration"] or
            metadata["output"]!=policy["output"] or metadata["parent_root"]!=policy["parent_output"]):
        raise ValueError("binary replay namespace/config provenance changed")
    for name,expected in (("direct_booster_screen.py","a47a5a21910a132977bda33ad531ba4c82b24cc9120143d40e3b415f32b84016"),
            ("direct_boosters.py","475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f")):
        if sha(Path(freeze["code_root"])/"nfl_lab"/name)!=expected:
            raise ValueError("original model/report helper changed")
    env=freeze["environment"]
    if sys.executable!=env["executable"] or sys.version!=env["python"] or not env["file_bindings"]:
        raise ValueError("exact parent Python/environment inventory required")
    for item in env["file_bindings"]:pin(item)
    for name,version in env["packages"].items():
        if importlib.metadata.version(name)!=version:raise ValueError("frozen dependency changed")
    if freeze["external_timeout"]["path"]!="/usr/bin/timeout":raise ValueError("pinned GNU timeout required")
    pin(freeze["external_timeout"])
    return metadata


def main():
    args=arguments()
    if args.parent_pid!=ARMED_PARENT or ARMED_PARENT is None or os.getppid()!=ARMED_PARENT:
        raise RuntimeError("parent lifetime guard is not armed")
    def deny(event,values):
        if event.startswith("socket."):raise RuntimeError("binary replay forbids network")
        if event in {"subprocess.Popen","os.posix_spawn","os.fork","os.forkpty","os.system"}:
            raise RuntimeError("binary replay worker forbids child processes")
    sys.addaudithook(deny)
    freeze=load(args.freeze,args.freeze_sha256);spec=verify(freeze)
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT","ARROW_IO_THREADS"):
        os.environ[name]="2"
    sys.path.insert(0,freeze["code_root"])
    from direct_xgboost_binary_recovery import run
    run(spec,plan_sha256=freeze["plan_sha256"],final_static=lambda:verify(freeze))
    print(json.dumps(dict(phase="BINARY_RECOVERY_REPORT_COMPLETE",cells=6,new_fits_HTTP=0)),flush=True)


if __name__=="__main__":main()
