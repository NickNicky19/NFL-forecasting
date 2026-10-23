"""Prepare an UNSEALED execution inventory without opening scored values.

The integrator/reviewer seal and PREEXEC PASS are external decisions. Write the
template outside managed operational roots; the owner imports the sealed bytes
through the existing quota-owned store before the sole reporting invocation.
"""
import argparse
import hashlib
import json
from pathlib import Path

POLICY_SHA256="7789249bdf56d7767ae87eea69184b0a1ea18d63db564e4fe4d1a83181b55e26"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def basic(path):
    path=Path(path)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def full(path):
    item=basic(path);info=Path(path).stat()
    if Path(path).resolve()!=Path(path) or Path(path).is_symlink():
        raise ValueError("canonical nonsymlink freeze member required")
    return dict(item,inode=[info.st_dev,info.st_ino],mode=oct(info.st_mode))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--policy",required=True)
    parser.add_argument("--policy-sha256",required=True)
    parser.add_argument("--destination",required=True)
    args=parser.parse_args()
    if args.policy_sha256!=POLICY_SHA256 or sha(args.policy)!=POLICY_SHA256:
        raise ValueError("immutable root reporting registration required")
    policy=json.loads(Path(args.policy).read_text())
    root=Path(policy["original_output"])
    old_path=root/"DIRECT_BOOSTER_SCREEN_EXECUTION_FREEZE.json"
    if sha(old_path)!=policy["required_inputs"]["original_execution_freeze"]:
        raise ValueError("original execution identity differs")
    old=json.loads(old_path.read_text())
    science_path=Path(old["plan_path"])
    if sha(science_path)!=policy["required_inputs"]["original_science_config"]:
        raise ValueError("original science config differs")
    science=json.loads(science_path.read_text())
    tools_root=Path(__file__).resolve().parent
    tools={name:basic(tools_root/file) for name,file in dict(
        aggregation="direct_booster_frozen_report.py",run="direct_booster_frozen_report_run.py",
        supervisor="direct_booster_frozen_report_supervisor.py",
        builder="freeze_direct_booster_frozen_report.py").items()}
    metadata=dict(parent_root=str(root),output=policy["output"],cache=science["cache"],
        control_root=science["control_root"],parent_config=basic(science_path),
        parent_execution_freeze=basic(old_path),
        parent_forecast_freeze=basic(root/"forecast-freeze.json"),
        parent_scored_freeze=basic(root/"scored-freeze.json"),
        parent_completion=basic(root/"screen-supervisor-completion.json"),
        control_scored_freeze=science["control_scored_freeze"],
        category_contract=science["category_contract"],source_policy=science["source_policy"],
        original_resource_accounting=dict(
            receipt_CPU_seconds=620.351459637,
            observed_runtime_CPU_seconds=1541.94,
            observed_reaped_chain_CPU_seconds=621.41,
            summed_observed_lower_bound_CPU_seconds=2163.35,
            scope="Original receipt incomplete after timeout/orphan reaping; lower bound is not an exact total"))
    paths={str(p) for p in (Path(old["code_root"])/"nfl_lab").glob("*.py")}
    paths|={args.policy,*(item["path"] for item in tools.values()),
        *(v["path"] for v in metadata.values() if isinstance(v,dict) and "path" in v)}
    if old["environment"].get("inventory_path"):
        paths.add(old["environment"]["inventory_path"])
    freeze=dict(state="UNSEALED_TEMPLATE_NO_EXECUTION",seal=None,preexec_review="PENDING",
        code_root=old["code_root"],plan_path=args.policy,plan_sha256=args.policy_sha256,
        output=policy["output"],cache=science["cache"],tools=tools,
        execution_metadata=metadata,bindings=[full(p) for p in sorted(paths)],
        environment=old["environment"],external_timeout=full("/usr/bin/timeout"),
        invocation="/usr/bin/timeout --signal=KILL --kill-after=1s 600s <frozen-python> -B <supervisor> --freeze <sealed-owned-freeze> --freeze-sha256 <exact-sha>")
    destination=Path(args.destination)
    if destination.exists() or Path(policy["output"]) in destination.parents:
        raise ValueError("unused nonoperational template destination required")
    destination.write_text(json.dumps(freeze,sort_keys=True,indent=2)+"\n")
    print(json.dumps(dict(template=str(destination),sha256=sha(destination),bytes=destination.stat().st_size,
        bindings=len(freeze["bindings"]),environment_bindings=len(freeze["environment"]["file_bindings"]),
        scored_values_opened=0,state=freeze["state"])))


if __name__=="__main__":
    main()
