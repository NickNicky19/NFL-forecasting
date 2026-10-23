"""Unsealed scoring inventory; metadata/hashes only, no model/row decoding."""
import argparse
import json
from pathlib import Path
from freeze_direct_booster_frozen_report import basic,full,sha
POLICY_SHA256="f9c9c97b1922ee1cccee43c70fdf0bd5d9e9b2f821a2a71a3ceb724213506e28"


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--policy",required=True)
    parser.add_argument("--policy-sha256",required=True);parser.add_argument("--destination",required=True)
    args=parser.parse_args()
    if args.policy_sha256!=POLICY_SHA256 or sha(args.policy)!=POLICY_SHA256:raise ValueError("registered scoring-only policy required")
    policy=json.loads(Path(args.policy).read_text());root=Path(policy["v2_output"])
    v2_path=root/"BINARY_RECOVERY_EXECUTION_FREEZE.json"
    if sha(v2_path)!=policy["required_SHA256"]["v2_execution_freeze"]:raise ValueError("frozen v2 execution changed")
    v2=json.loads(v2_path.read_text());old=v2["execution_metadata"]
    forecast_path=root/"forecast-freeze.json"
    if sha(forecast_path)!=policy["required_SHA256"]["v2_forecast_freeze"]:raise ValueError("six global forecasts changed")
    forecast=json.loads(forecast_path.read_text())
    spec={key:old[key] for key in ("cache","control_root","source_policy","category_contract","control_scored_freeze",
        "parent_execution_freeze","parent_forecast_freeze","parent_scored_freeze","parent_FAILED_completion","parent_config","loaded_libc")}
    spec.update(registration_id=policy["registration_id"],output=policy["output"],v2_root=str(root),
        v2_execution_freeze=basic(v2_path),v2_forecast_freeze=basic(forecast_path),
        v2_FAILED_completion=basic(root/"binary-supervisor-completion.json"),
        queries={str(y):next(c["query"] for c in old["cells"] if c["year"]==y) for y in (2022,2023,2024)},
        donors=old["donors"],forecast_files=[basic(root/s["forecast"]) for s in forecast["slots"]])
    tools_root=Path(__file__).resolve().parent
    names=dict(aggregation="direct_xgboost_binary_scoring.py",run="direct_xgboost_binary_scoring_run.py",
        supervisor="direct_xgboost_binary_scoring_supervisor.py",builder="freeze_direct_xgboost_binary_scoring.py",
        binary_helpers="direct_xgboost_binary_recovery.py",binary_run_helpers="direct_xgboost_binary_recovery_run.py",
        report_helpers="direct_booster_frozen_report.py",report_run_helpers="direct_booster_frozen_report_run.py",
        report_supervisor_helpers="direct_booster_frozen_report_supervisor.py",
        report_freeze_helpers="freeze_direct_booster_frozen_report.py")
    tools={key:basic(tools_root/name) for key,name in names.items()}
    paths={str(p) for p in (Path(v2["code_root"])/"nfl_lab").glob("*.py")}
    paths|={args.policy,*(v["path"] for v in tools.values()),
        *(v["path"] for v in spec.values() if isinstance(v,dict) and "path" in v),
        *(v["path"] for v in [*spec["queries"].values(),*spec["donors"].values(),*spec["forecast_files"]])}
    if v2["environment"].get("inventory_path"):paths.add(v2["environment"]["inventory_path"])
    freeze=dict(state="UNSEALED_TEMPLATE_NO_EXECUTION",seal=None,preexec_review="PENDING",
        code_root=v2["code_root"],plan_path=args.policy,plan_sha256=args.policy_sha256,tools=tools,
        execution_metadata=spec,environment=v2["environment"],bindings=[full(p) for p in sorted(paths)],
        external_timeout=full("/usr/bin/timeout"),
        invocation="/usr/bin/timeout --signal=KILL --kill-after=1s 180s <frozen-python> -B <supervisor> --freeze <sealed-owned-freeze> --freeze-sha256 <exact-sha>")
    destination=Path(args.destination)
    if destination.exists() or Path(policy["output"]) in destination.parents:raise ValueError("unused template path outside operational roots required")
    destination.write_text(json.dumps(freeze,sort_keys=True,indent=2)+"\n")
    print(json.dumps(dict(state=freeze["state"],path=str(destination),bytes=destination.stat().st_size,
        sha256=sha(destination),bindings=len(freeze["bindings"]),NFL_values_models_decoded=0)))


if __name__=="__main__":main()
