"""Build unsealed metadata inventory, never decode scored/forecast values."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, "/workspace/nfl-baseline-correction-v1/tools")
from freeze_direct_booster_frozen_report import basic, full, sha

POLICY_SHA256 = "0259cb78935551534453d71458af866037498da3aa1e8b5add95b7b7906eda49"


def build(policy_path, destination):
    if sha(policy_path) != POLICY_SHA256:
        raise ValueError("exact predeclared reporting continuation policy required")
    policy = json.loads(Path(policy_path).read_text())
    root = Path(policy["parent_root"])
    execution_path = root / "CORRECTION_EXECUTION_FREEZE.json"
    old = json.loads(execution_path.read_text())
    spec = dict(policy)
    spec.update(parent_execution_freeze=basic(execution_path), parent_config=basic(old["plan_path"]),
        correction_extension=old["execution_metadata"]["correction_extension"],
        loaded_libc=old["execution_metadata"]["loaded_libc"],
        source_policy=old["execution_metadata"]["source_policy"],
        source_manifest=old["execution_metadata"]["source_manifest"],
        category_contract=old["execution_metadata"]["category_contract"],
        control_scored_freeze=old["execution_metadata"]["control_scored_freeze"])
    if old["code_root"] != policy["code_root"] or old["execution_metadata"]["output"] != policy["parent_root"]:
        raise ValueError("original correction source/helper namespace changed")
    for key, name in (("parent_forecast_freeze", "forecast-freeze.json"),
            ("parent_scored_freeze", "scored-freeze.json"),
            ("parent_FAILED_completion", "correction-supervisor-completion.json")):
        spec[key] = basic(root / name)
        if spec[key]["sha256"] != policy["required_SHA256"][key]:
            raise ValueError("original proof changed:" + key)
    scored = json.loads(Path(spec["parent_scored_freeze"]["path"]).read_text())
    controls = json.loads(Path(spec["control_scored_freeze"]["path"]).read_text())
    owned = {}
    for slot in scored["slots"]:
        path = root / slot["scored"]
        binding = basic(path)
        if binding["sha256"] != scored["bindings"][slot["scored"]]:
            raise ValueError("frozen scored byte identity changed")
        owned[str(path)] = binding["sha256"]
    for year in (2022, 2023, 2024):
        for target in policy["reused_targets"] + policy["remaining_targets"]:
            for method in ("leaf_cdf", "count_A", "role_B", "recent", "pooled"):
                name = f"private/scored/{year}/{target}/{method}/rows.parquet"
                binding = basic(Path(policy["control_root"]) / name)
                if name not in controls["scored_files"] or binding["sha256"] != controls["bindings"][name]:
                    raise ValueError("original five-control bytes changed")
                owned[binding["path"]] = binding["sha256"]
    if len(owned) != 231:
        raise ValueError("all66 frozen scored/all165 controls required")
    spec["scored_and_control_bindings"] = owned
    for files in policy["completed_outputs"].values():
        for binding in files.values():
            if basic(binding["path"]) != binding:
                raise ValueError("original complete report/private bytes changed")
    tools_root = Path(__file__).resolve().parent
    tools = {key: basic(tools_root / name) for key, name in dict(
        aggregation="baseline_correction_report_v2.py", run="baseline_correction_report_run_v2.py",
        supervisor="baseline_correction_report_supervisor_v2.py", builder="freeze_baseline_correction_report_v2.py",
        offline_imports="offline_report_imports_v1.py").items()}
    tools.update({"original_" + key: value for key, value in old["tools"].items()})
    paths = {str(path) for path in (Path(policy["code_root"])/"nfl_lab").glob("*.py")}
    paths |= {str(Path(policy_path).resolve()), *(binding["path"] for binding in tools.values()),
        *(item["path"] for item in spec.values() if isinstance(item, dict) and "path" in item), *owned}
    paths |= {item["path"] for files in policy["completed_outputs"].values() for item in files.values()}
    if old["environment"].get("inventory_path"):
        paths.add(old["environment"]["inventory_path"])
    freeze = dict(state="UNSEALED_TEMPLATE_NO_EXECUTION", seal=None, preexec_review="PENDING",
        code_root=policy["code_root"], plan_path=str(Path(policy_path).resolve()), plan_sha256=POLICY_SHA256,
        tools=tools, execution_metadata=spec, environment=old["environment"],
        bindings=[full(path) for path in sorted(paths)], external_timeout=full("/usr/bin/timeout"),
        invocation="/usr/bin/timeout --signal=KILL --kill-after=1s 600s <frozen-python> -B <supervisor> --freeze <owned-sealed-freeze> --freeze-sha256 <exact-sha>")
    destination = Path(destination)
    if destination.exists() or Path(policy["output"]) in destination.parents:
        raise ValueError("fresh template path outside operational roots required")
    destination.write_text(json.dumps(freeze, sort_keys=True, indent=2) + "\n")
    return freeze


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    value = build(args.policy, args.destination)
    print(json.dumps(dict(state=value["state"], bindings=len(value["bindings"]),
        sha256=sha(args.destination), bytes=Path(args.destination).stat().st_size, NFL_values_decoded=0)))
