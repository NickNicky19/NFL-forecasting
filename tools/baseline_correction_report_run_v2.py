"""Sealed, source-free continuation caller using frozen guard primitives."""
import os
import sys
sys.path.insert(0, "/workspace/nfl-baseline-correction-v1/tools")
from direct_booster_frozen_report_run import arm_parent_death, pin, sha
ARMED_PARENT = None
if __name__ == "__main__":
    try: ARMED_PARENT = int(sys.argv[sys.argv.index("--parent-pid") + 1])
    except (ValueError, IndexError): raise SystemExit("explicit guarded parent required")
    arm_parent_death(ARMED_PARENT)
import importlib.metadata
import json
from pathlib import Path
from direct_xgboost_binary_recovery_run import arguments, load
from baseline_correction_run import extension
from offline_report_imports_v1 import offline_dependency_imports

POLICY_SHA256 = "0259cb78935551534453d71458af866037498da3aa1e8b5add95b7b7906eda49"
BUDGETS = dict(actual_invocations=1, wall_seconds=600, CPU_seconds=600, combined_RSS_bytes=1073741824,
    numerical_threads=2, new_retained_bytes=16777216, shared_retention_bytes=536870912, HTTP=0,
    new_fits_inference_scoring_labeljoins_raw_model_law_calls=0, automatic_retries=0)


def verify(freeze):
    if freeze["plan_sha256"] != POLICY_SHA256 or sha(freeze["plan_path"]) != POLICY_SHA256:
        raise ValueError("exact separately registered report-only policy required")
    policy = json.loads(Path(freeze["plan_path"]).read_text())
    spec = freeze["execution_metadata"]
    if policy["budgets"] != BUDGETS or any(spec.get(key) != value for key, value in policy.items()):
        raise ValueError("report-only policy/limits/partition changed")
    bindings = {item["path"]: item for item in freeze["bindings"]}
    if len(bindings) != len(freeze["bindings"]):
        raise ValueError("duplicate execution binding")
    required = {str(path) for path in (Path(freeze["code_root"])/"nfl_lab").glob("*.py")}
    required |= {freeze["plan_path"], *(item["path"] for item in freeze["tools"].values())}
    required |= {item["path"] for item in spec.values() if isinstance(item, dict) and "path" in item}
    required |= {item["path"] for files in spec["completed_outputs"].values() for item in files.values()}
    required |= set(spec["scored_and_control_bindings"])
    if not required <= set(bindings):
        raise ValueError("complete original helpers/environment/source/frozen-row bindings required")
    for item in freeze["bindings"]: pin(item)
    for key, expected in policy["required_SHA256"].items():
        if spec[key]["sha256"] != expected or sha(spec[key]["path"]) != expected:
            raise ValueError("parent failure/freeze identity changed:" + key)
    for name, expected in (("direct_booster_screen.py", "a47a5a21910a132977bda33ad531ba4c82b24cc9120143d40e3b415f32b84016"),
            ("direct_boosters.py", "475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f")):
        if sha(Path(freeze["code_root"])/"nfl_lab"/name) != expected:
            raise ValueError("unchanged original aggregation/scoring helpers required")
    env = freeze["environment"]
    if sys.executable != env["executable"] or sys.version != env["python"] or not env["file_bindings"]:
        raise ValueError("complete original environment required")
    for item in env["file_bindings"]: pin(item)
    for name, version in env["packages"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError("dependency changed:" + name)
    if freeze["external_timeout"]["path"] != "/usr/bin/timeout":
        raise ValueError("pinned external GNU timeout required")
    pin(freeze["external_timeout"])
    return spec


def main():
    args = arguments()
    if ARMED_PARENT is None or args.parent_pid != ARMED_PARENT or os.getppid() != ARMED_PARENT:
        raise RuntimeError("worker parent-death guard absent")
    def deny(event, values):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.posix_spawn", "os.fork", "os.forkpty", "os.system"}:
            raise RuntimeError("report-only worker forbids network/child processes")
    sys.addaudithook(deny)
    freeze = load(args.freeze, args.freeze_sha256)
    spec = verify(freeze)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "OMP_THREAD_LIMIT", "ARROW_IO_THREADS"):
        os.environ[name] = "2"
    sys.path.insert(0, freeze["code_root"])
    with offline_dependency_imports():
        extension(spec["correction_extension"])
        from baseline_correction_report_v2 import run
    run(spec, plan_sha256=freeze["plan_sha256"], final_static=lambda: verify(freeze))
    print(json.dumps(dict(phase="CORRECTION_REPORT_CONTINUATION_COMPLETE", reused=4, aggregated=7,
        new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0)), flush=True)


if __name__ == "__main__": main()
