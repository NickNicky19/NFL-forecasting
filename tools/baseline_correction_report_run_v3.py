"""Compact sealed caller; inherits and verifies the complete V2 freeze."""
import os
import sys
sys.path.insert(0, "/workspace/nfl-baseline-correction-v1/tools")
sys.path.insert(0, "/workspace/nfl-baseline-correction-report-v2/tools")
from direct_booster_frozen_report_run import arm_parent_death, pin, sha
ARMED_PARENT = None
if __name__ == "__main__":
    try: ARMED_PARENT = int(sys.argv[sys.argv.index("--parent-pid")+1])
    except (ValueError, IndexError): raise SystemExit("explicit guarded parent required")
    arm_parent_death(ARMED_PARENT)
import json
from pathlib import Path
from baseline_correction_report_run_v2 import arguments, load, verify as verify_inherited, extension
from offline_report_imports_v1 import offline_dependency_imports
from compact_report_contract_v3 import compact_reference

POLICY_SHA256 = "d0421bec77493eb9aa884c9ba89163129abec572ec633d8ac12902c974198eb0"
BUDGETS = dict(actual_invocations=1, wall_seconds=300, CPU_seconds=300, combined_RSS_bytes=1073741824,
    numerical_threads=2, new_retained_bytes=16777216, shared_retention_bytes=536870912,
    new_fits_inference_scoring_labeljoins_raw_model_law_HTTP_retries=0)


def verify(freeze):
    if freeze["plan_sha256"] != POLICY_SHA256 or sha(freeze["plan_path"]) != POLICY_SHA256:
        raise ValueError("exact new compact reporting policy required")
    policy = json.loads(Path(freeze["plan_path"]).read_text())
    spec = dict(freeze["execution_metadata"])
    if policy["budgets"] != BUDGETS or any(spec.get(key) != value for key, value in policy.items()):
        raise ValueError("V3 registered scope/budget/partition changed")
    binding = freeze["inherited_execution"]
    pin(binding)
    inherited = load(binding["path"], binding["sha256"])
    compact_reference(freeze, policy, inherited, verify_inherited)
    if freeze["code_root"] != inherited["code_root"]:
        raise ValueError("original immutable helper assembly changed")
    bindings = {item["path"]: item for item in freeze["bindings"]}
    if len(bindings) != len(freeze["bindings"]):
        raise ValueError("duplicate V3 delta binding")
    required = {freeze["plan_path"], *(item["path"] for item in freeze["tools"].values()), binding["path"]}
    required |= {item["path"] for item in spec.values() if isinstance(item, dict) and "path" in item}
    required |= {item["path"] for files in spec["completed_outputs"].values() for item in files.values()}
    if not required <= set(bindings):
        raise ValueError("complete V3 code/proof/reused-output deltas required")
    for item in freeze["bindings"]: pin(item)
    if freeze["external_timeout"] != inherited["external_timeout"]:
        raise ValueError("original pinned GNU timeout executable changed")
    pin(freeze["external_timeout"])
    spec["_inherited_execution"] = inherited  # In memory only; never duplicate its environment in new JSON.
    return spec


def main():
    args = arguments()
    if ARMED_PARENT is None or args.parent_pid != ARMED_PARENT or os.getppid() != ARMED_PARENT:
        raise RuntimeError("worker parent-death guard absent")
    def deny(event, values):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.posix_spawn", "os.fork", "os.forkpty", "os.system"}:
            raise RuntimeError("V3 forbids network and worker child processes")
    sys.addaudithook(deny)
    freeze = load(args.freeze, args.freeze_sha256)
    spec = verify(freeze)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "OMP_THREAD_LIMIT", "ARROW_IO_THREADS"):
        os.environ[name] = "2"
    sys.path.insert(0, freeze["code_root"])
    with offline_dependency_imports():
        extension(spec["_inherited_execution"]["execution_metadata"]["correction_extension"])
        from baseline_correction_report_v3 import run
    run(spec, plan_sha256=freeze["plan_sha256"], final_static=lambda: verify(freeze))
    print(json.dumps(dict(phase="V3_REPORT_COMPLETE", reused=9, aggregated=2,
        new_fits_inference_scoring_labeljoins_raw_model_law_HTTP=0)), flush=True)


if __name__ == "__main__": main()
