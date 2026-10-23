from __future__ import annotations

from contextlib import nullcontext
import argparse
import json
from pathlib import Path

from .state import digest, now_utc, records, resolved_outcomes, save, utc, validate_forecast


def main():
    parser=argparse.ArgumentParser(description="Bounded NFL lab; no odds or production website writes")
    parser.add_argument("command",choices=["acquire","experiment","daily","grade","replay","publication"])
    parser.add_argument("--root",type=Path,default=Path.cwd())
    parser.add_argument("--cache",type=Path)
    parser.add_argument("--state",type=Path)
    parser.add_argument("--seasons",default="2019,2020,2021,2022,2023,2024,2025")
    parser.add_argument("--methods")
    parser.add_argument("--source-policy",type=Path,help="Explicit permitted operational source policy; required for current operations")
    parser.add_argument("--publication-commit")
    parser.add_argument("--output",type=Path,help="Quota-managed aggregate receipt inside the registered runs directory")
    args=parser.parse_args();root=args.root.resolve();cache=args.cache or root/"data";state=args.state or root/"state"
    if args.command in {"acquire","experiment","daily","grade"} and args.source_policy is None:
        parser.error("current operations require --source-policy; historical study functions remain available for replay")
    source_policy=(args.source_policy if args.source_policy.is_absolute() else root/args.source_policy) if args.source_policy is not None else None
    seasons=[int(x) for x in args.seasons.split(",")]
    config=json.loads((root/"config/research.json").read_text())
    if source_policy is not None:
        from .operational_sources import load_source_policy
        from .operational_storage import OperationalStorage
        from .operational_io import operational_io
        policy=load_source_policy(source_policy)
        storage=OperationalStorage(cache,policy,state=state)
        scope=operational_io(storage,run_root=root/"runs")
    else:
        scope=nullcontext()
    with scope:
        return _execute(args,root,cache,state,source_policy,seasons,config)


def _execute(args,root,cache,state,source_policy,seasons,config):
    exit_code=0
    if args.command=="acquire":
        from .experiment import acquire_operational_features
        try:
            from .live import fetch
            active_status,_=fetch(cache,"state","https://api.sleeper.app/v1/state/nfl")
            # January belongs to the provider's NFL season, not the UTC year.
            active_year=int(active_status["season"])
            if active_year<2012:raise ValueError("unsupported NFL active season")
            seasons=sorted(set(seasons+[active_year]))
            result=acquire_operational_features(cache,seasons,source_policy,now_utc(),state=state)
        except Exception as error:
            save(state,"health",{"state":"PERMITTED_SOURCE_ACQUISITION_FAILED","error":type(error).__name__+": "+str(error)[:500],
                                  "observed_at":now_utc().isoformat()})
            raise
    elif args.command=="experiment":
        from .experiment import run_experiment
        result=run_experiment(root,cache,state,config,args.methods.split(",") if args.methods else None,source_policy=source_policy)
    elif args.command=="daily":
        from .live import daily
        result=daily(root,cache,state,seasons,args.methods.split(",") if args.methods else None,source_policy=source_policy)
        if result.get("state") in {"PERMITTED_SOURCE_ISSUANCE_ABSTAINED","PERMITTED_OPERATION_FAILED_AFTER_ISSUANCE"}:
            exit_code=1
    elif args.command=="grade":
        from .live import grade_only
        result=grade_only(state,cache,source_policy=source_policy)
    elif args.command=="replay":
        from .prospective import score_saved
        forecasts=0
        for batch in records(state,"forecasts"):
            for row in batch["rows"]:validate_forecast(row);forecasts+=1
        outcomes=resolved_outcomes(state)
        from .website_baselines import score_saved_website
        from .operational_io import active_storage, quota_downloader
        storage=active_storage()
        baseline_cache=storage.live_root/"website-baselines" if storage is not None else cache
        result={"forecasts_validated":forecasts,"outcomes":len(outcomes),"unresolved_conflicts":sum(r["state"].startswith("unresolved") for r in outcomes.values()),"receipt_integrity":"PASS","scorecard":score_saved(state),"website_comparison":score_saved_website(state,baseline_cache,**({"downloader":quota_downloader(storage)} if storage is not None else {}))}
        save(state,"scorecards",result)
    else:
        if not args.publication_commit:raise ValueError("publication commit required")
        observed=now_utc();docs=list(records(state,"forecasts"));prior={r["batch"] for r in records(state,"publication")}
        verified=0;late=0
        for batch in docs:
            key=digest(batch)
            if key in prior:continue
            timely=sum(utc(r["kickoff_utc"])>observed for r in batch["rows"])
            save(state,"publication",{"batch":key,"commit":args.publication_commit,"observed_remote_readback_at":observed.isoformat(),
                 "timely_rows":timely,"late_rows":len(batch["rows"])-timely,"scope":"remote commit readback; input provider publication clocks remain unknown"})
            verified+=timely;late+=len(batch["rows"])-timely
        from .website_baselines import record_website_publication
        website_snapshots=record_website_publication(state,args.publication_commit,observed)
        result={"publication_verified_rows":verified,"late_rows":late,"website_snapshots_publication_checked":website_snapshots}
    encoded=json.dumps(result,indent=2,default=str,allow_nan=False)
    if args.output is not None:
        from .operational_io import active_storage
        storage=active_storage()
        if storage is None:
            raise ValueError("--output requires the v2 source policy")
        destination=args.output if args.output.is_absolute() else root/args.output
        runs=(root/"runs").resolve()
        if not destination.resolve().is_relative_to(runs):
            raise ValueError("operational output must be inside the registered runs directory")
        with storage.capture_writes(roots=[destination]):
            storage.write_text(destination,encoded+"\n",replace=True)
    print(encoded)
    if exit_code:
        raise SystemExit(exit_code)


if __name__=="__main__":main()
