"""Compact metadata-only V3 freeze; reference and fully reverify old inventory."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, "/workspace/nfl-baseline-correction-v1/tools")
from freeze_direct_booster_frozen_report import basic, full, sha

POLICY_SHA256 = "d0421bec77493eb9aa884c9ba89163129abec572ec633d8ac12902c974198eb0"


def build(policy_path, destination):
    if sha(policy_path) != POLICY_SHA256:
        raise ValueError("exact new V3 policy required")
    policy = json.loads(Path(policy_path).read_text())
    parent_binding = policy["inherited_execution"]
    if basic(parent_binding["path"]) != parent_binding:
        raise ValueError("original full sealed inventory changed")
    inherited = json.loads(Path(parent_binding["path"]).read_text())
    if inherited["state"] != "SEALED_ROOT_AND_REVIEWER" or inherited["preexec_review"] != "PASS":
        raise ValueError("previously accepted full sealed inventory required")
    if inherited["code_root"] != policy["code_root"]:
        raise ValueError("original immutable helper assembly changed")
    for key in ("V2_failed_supervisor", "V2_worker_failure", "V2_worker_finished", "V2_failed_log"):
        if basic(policy[key]["path"]) != policy[key]:
            raise ValueError("V2 failed proof changed:" + key)
    for files in policy["completed_outputs"].values():
        for binding in files.values():
            if basic(binding["path"]) != binding:
                raise ValueError("completed report/private bytes changed")
    tools_root = Path(__file__).resolve().parent
    tools = {key: basic(tools_root/name) for key, name in dict(
        aggregation="baseline_correction_report_v3.py", run="baseline_correction_report_run_v3.py",
        supervisor="baseline_correction_report_supervisor_v3.py", builder="freeze_baseline_correction_report_v3.py",
        compact_contract="compact_report_contract_v3.py").items()}
    paths = {str(Path(policy_path).resolve()), *(item["path"] for item in tools.values()),
        *(item["path"] for item in policy.values() if isinstance(item, dict) and "path" in item)}
    paths |= {item["path"] for files in policy["completed_outputs"].values() for item in files.values()}
    freeze = dict(state="UNSEALED_TEMPLATE_NO_EXECUTION", seal=None, preexec_review="PENDING",
        code_root=policy["code_root"], plan_path=str(Path(policy_path).resolve()), plan_sha256=POLICY_SHA256,
        tools=tools, inherited_execution=full(parent_binding["path"]), execution_metadata=policy,
        environment={key: inherited["environment"][key] for key in ("executable", "python", "packages")},
        bindings=[full(path) for path in sorted(paths)], external_timeout=inherited["external_timeout"],
        inherited_full_verification="Call unchanged V2 verifier on the authenticated FULL old freeze, including every original environment/code/input pin, before checking V3 deltas",
        invocation="/usr/bin/timeout --signal=KILL --kill-after=1s 300s <frozen-python> -B <supervisor> --freeze <sealed-owned-compact-freeze> --freeze-sha256 <exact-sha>")
    destination = Path(destination)
    if destination.exists() or Path(policy["output"]) in destination.parents:
        raise ValueError("fresh template outside actual namespace required")
    destination.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    return freeze


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    value = build(args.policy, args.destination)
    print(json.dumps(dict(state=value["state"], bytes=Path(args.destination).stat().st_size,
        sha256=sha(args.destination), V3_delta_bindings=len(value["bindings"]),
        inherited_environment_and_input_pins="FULL_ORIGINAL_VERIFIER_REQUIRED", NFL_values_decoded=0)))
