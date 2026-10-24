"""Prepare unsealed replay metadata without unpickling or parquet decoding."""
import argparse
import json
from pathlib import Path
from freeze_direct_booster_frozen_report import basic,full,sha

POLICY_SHA256="81fcf8f0f24090b048d6dce1e72517bb4f0aa0f8eb2ffabc913ccf5f0098ada8"


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--policy",required=True)
    parser.add_argument("--policy-sha256",required=True);parser.add_argument("--destination",required=True)
    args=parser.parse_args()
    if args.policy_sha256!=POLICY_SHA256 or sha(args.policy)!=POLICY_SHA256:
        raise ValueError("exact registered replay policy required")
    policy=json.loads(Path(args.policy).read_text());root=Path(policy["parent_output"])
    old_path=root/"DIRECT_BOOSTER_SCREEN_EXECUTION_FREEZE.json"
    if sha(old_path)!=policy["required_SHA256"]["parent_execution_freeze"]:raise ValueError("original execution changed")
    old=json.loads(old_path.read_text());science_path=Path(old["plan_path"])
    science=json.loads(science_path.read_text());forecast=json.loads((root/"forecast-freeze.json").read_text())
    tools_root=Path(__file__).resolve().parent;repo=tools_root.parent
    metadata=dict(registration_id=policy["registration_id"],output=policy["output"],parent_root=str(root),cache=science["cache"],
        control_root=science["control_root"],parent_execution_freeze=basic(old_path),
        parent_forecast_freeze=basic(root/"forecast-freeze.json"),
        parent_scored_freeze=basic(root/"scored-freeze.json"),
        parent_FAILED_completion=basic(root/"screen-supervisor-completion.json"),
        parent_config=basic(science_path),original_science_registration=basic(science_path),
        source_policy=science["source_policy"],category_contract=science["category_contract"],
        control_scored_freeze=science["control_scored_freeze"],
        canonicalizer=basic(repo/"nfl_lab/direct_binary_canonical_v2.py"),
        canonicalizer_software_registration=basic(repo/"config/direct-booster-binary-canonical-v2.json"),
        cells=[],donors={})
    libc={Path(line.split()[-1]).resolve() for line in Path("/proc/self/maps").read_text().splitlines()
        if len(line.split())>=6 and line.split()[-1].endswith("/libc.so.6")}
    if len(libc)!=1:raise ValueError("one already-loaded libc required")
    metadata["loaded_libc"]=basic(next(iter(libc)))
    for year in (2022,2023,2024):
        count=next(s["rows"] for s in forecast["slots"] if s["year"]==year and s["state"]=="PREDICTION_FROZEN")
        for level in ("small","medium"):
            stem=root/f"private/cells/{year}/anytime_td/direct_xgboost_{level}"
            metadata["cells"].append(dict(year=year,complexity=level,query_rows=count,
                model=basic(stem/"model.joblib"),failure=basic(stem/"FAILURE.json"),
                query=basic(root/f"private/queries/{year}.parquet")))
        metadata["donors"][str(year)]=basic(root/f"private/scored/{year}/anytime_td/direct_lightgbm_small.parquet")
    files=dict(aggregation="direct_xgboost_binary_recovery.py",run="direct_xgboost_binary_recovery_run.py",
        supervisor="direct_xgboost_binary_recovery_supervisor.py",builder="freeze_direct_xgboost_binary_recovery.py",
        reviewed_report_aggregation="direct_booster_frozen_report.py",
        reviewed_report_run="direct_booster_frozen_report_run.py",
        reviewed_report_supervisor="direct_booster_frozen_report_supervisor.py",
        reviewed_report_builder="freeze_direct_booster_frozen_report.py")
    tools={key:basic(tools_root/name) for key,name in files.items()}
    paths={str(p) for p in (Path(old["code_root"])/"nfl_lab").glob("*.py")}
    paths|={args.policy,*(v["path"] for v in tools.values()),
        *(v["path"] for v in metadata.values() if isinstance(v,dict) and "path" in v),
        *(c[k]["path"] for c in metadata["cells"] for k in ("model","query","failure")),
        *(v["path"] for v in metadata["donors"].values())}
    if old["environment"].get("inventory_path"):paths.add(old["environment"]["inventory_path"])
    freeze=dict(state="UNSEALED_TEMPLATE_NO_EXECUTION",seal=None,preexec_review="PENDING",
        code_root=old["code_root"],plan_path=args.policy,plan_sha256=args.policy_sha256,
        tools=tools,execution_metadata=metadata,environment=old["environment"],
        bindings=[full(p) for p in sorted(paths)],external_timeout=full("/usr/bin/timeout"),
        invocation="/usr/bin/timeout --signal=KILL --kill-after=1s 120s <frozen-python> -B <supervisor> --freeze <sealed-owned-freeze> --freeze-sha256 <exact-sha>")
    destination=Path(args.destination)
    if destination.exists() or Path(policy["output"]) in destination.parents:
        raise ValueError("unused template destination outside operational roots required")
    destination.write_text(json.dumps(freeze,sort_keys=True,indent=2)+"\n")
    print(json.dumps(dict(state=freeze["state"],template=str(destination),sha256=sha(destination),
        bytes=destination.stat().st_size,bindings=len(freeze["bindings"]),NFL_values_decoded_or_models_unpickled=0)))


if __name__=="__main__":main()
