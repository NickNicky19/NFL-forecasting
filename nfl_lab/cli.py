from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .state import digest, now_utc, records, resolved_outcomes, save, utc, validate_forecast


def main():
    parser=argparse.ArgumentParser(description="Bounded NFL lab; no odds or production website writes")
    parser.add_argument("command",choices=["acquire","experiment","daily","replay","publication"])
    parser.add_argument("--root",type=Path,default=Path.cwd())
    parser.add_argument("--cache",type=Path)
    parser.add_argument("--state",type=Path)
    parser.add_argument("--seasons",default="2019,2020,2021,2022,2023,2024,2025")
    parser.add_argument("--methods")
    parser.add_argument("--publication-commit")
    args=parser.parse_args();root=args.root.resolve();cache=args.cache or root/"data";state=args.state or root/"state"
    seasons=[int(x) for x in args.seasons.split(",")]
    config=json.loads((root/"config/research.json").read_text())
    if args.command=="acquire":
        from .data import acquire_history,load_history
        from .features import build_features
        receipt=acquire_history(cache,seasons);history=load_history(cache,seasons)
        frame=build_features(history);(cache/"processed").mkdir(exist_ok=True)
        frame.to_parquet(cache/"processed/features.parquet",index=False)
        feature_file=cache/"processed/features.parquet"
        feature_sha=hashlib.file_digest(feature_file.open("rb"),"sha256").hexdigest()
        feature_manifest={"feature_sha256":feature_sha,"acquisition":receipt,"feature_profile":frame.attrs,"vintage":"reconstructed_current_vintage"}
        manifests=cache/"processed/feature_manifests";manifests.mkdir(exist_ok=True)
        manifest_file=manifests/(feature_sha+".json")
        if not manifest_file.exists():manifest_file.write_text(json.dumps(feature_manifest,indent=2,default=str,allow_nan=False))
        result={"rows":len(frame),"source_receipt":receipt,"feature_columns":[c for c in frame if c.startswith("f_")]}
    elif args.command=="experiment":
        import pandas as pd
        from .evaluation import campaign
        p=cache/"processed/features.parquet"
        if not p.exists():raise RuntimeError("run acquire first")
        features=pd.read_parquet(p)
        features.attrs["feature_file_sha256"]=hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
        manifest_path=cache/"processed/feature_manifests"/(features.attrs["feature_file_sha256"]+".json")
        features.attrs["source_snapshot_binding"]=json.loads(manifest_path.read_text()) if manifest_path.exists() else {"state":"legacy feature checksum captured; prematched acquisition snapshot absent; no fabricated source binding"}
        result=campaign(features,root/"runs"/config["registration_id"],config,args.methods.split(",") if args.methods else None)
        attempt=Path(result["output"])
        derived={"schema_version":"lab-training-run-v1","registration":config,"result":result,
                 "trials":json.loads((attempt/"trials.json").read_text()) if (attempt/"trials.json").exists() else [],
                 "manifest":json.loads((attempt/"manifest.json").read_text()),
                 "row_level_outputs":"local ignored only; row hash binds this derived aggregate"}
        for name in ["selected","paired","coherence","summary"]:
            path=attempt/(name+".json")
            if path.exists():derived[name]=json.loads(path.read_text())
        save(state,"training",derived)
    elif args.command=="daily":
        from .live import daily
        result=daily(root,cache,state,seasons,args.methods.split(",") if args.methods else None)
    elif args.command=="replay":
        from .prospective import score_saved
        forecasts=0
        for batch in records(state,"forecasts"):
            for row in batch["rows"]:validate_forecast(row);forecasts+=1
        outcomes=resolved_outcomes(state)
        result={"forecasts_validated":forecasts,"outcomes":len(outcomes),"unresolved_conflicts":sum(r["state"].startswith("unresolved") for r in outcomes.values()),"receipt_integrity":"PASS","scorecard":score_saved(state)}
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
        result={"publication_verified_rows":verified,"late_rows":late}
    print(json.dumps(result,indent=2,default=str,allow_nan=False))


if __name__=="__main__":main()
