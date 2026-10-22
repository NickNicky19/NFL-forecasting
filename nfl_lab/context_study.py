"""Finite development-only NGS ablation using the existing loader/model/evaluator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import warnings

import numpy as np
import pandas as pd

from .context import load_ngs,merge_ngs_asof
from .evaluation import summarize
from .models import fit_predict
from .state import digest,now_utc,source_tree_digest


def run(root:Path,cache:Path):
    config=json.loads((root/"config/context-study.json").read_text())
    path=cache/"processed/features.parquet"
    checksum=hashlib.file_digest(path.open("rb"),"sha256").hexdigest()
    expected="ff7a14bac024958f32cbf367e83f6d70e4f86572f461ca6ebd33a9207d04d297"
    if checksum!=expected:raise ValueError("cached baseline feature version changed; new paired protocol required")
    output=root/"runs"/config["registration_id"]/now_utc().strftime("%Y%m%dT%H%M%S%f")
    output.mkdir(parents=True,exist_ok=False)
    (output/"registration.json").write_text(json.dumps(config,indent=2))
    features=pd.read_parquet(path)
    ngs=load_ngs(cache,config["sources_ngs_seasons"])
    augmented=merge_ngs_asof(features,ngs)
    base_columns=[c for c in features if c.startswith("f_")]
    pd.testing.assert_frame_equal(features[base_columns],augmented[base_columns])
    manifest={"registration_sha256":digest(config),"base_features_sha256":checksum,"source_tree_sha256":source_tree_digest(root),
              "ngs_feature_columns":[c for c in augmented if c.startswith("f_ngs_")],"source_profile":augmented.attrs,
              "ngs_sources":ngs.attrs.get("manifest"),"ngs_source_manifest_canonical_sha256":digest(ngs.attrs.get("manifest"))}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2,default=str,allow_nan=False))
    year=config["development_season"];test=augmented.loc[augmented.season.eq(year)]
    first=pd.to_datetime(test.kickoff_utc,utc=True).min()
    train=augmented.loc[augmented.season.isin(config["training_seasons"]) & (pd.to_datetime(augmented.outcome_available_utc,utc=True)<first)]
    started=time.monotonic();results=[]
    for target in config["targets"]:
        if time.monotonic()-started>config["budgets"]["fit_seconds"]:
            results.append({"target":target,"state":"NOT_RUN_BUDGET_EXHAUSTED"});continue
        baseline=root/"runs/lab-v1-2026-10-22"/f"2023-{target}-ridge.parquet"
        prior=pd.read_parquet(baseline)
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                pred=fit_predict(train,test,target,"ridge")
            current=test[["season","week","game_id","player_id","team","opponent","position","kickoff_utc","participation_state"]].copy()
            current["actual"]=test[target];current["target"]=target;current["method"]="ridge_plus_ngs_new_v1"
            for col in ["mean","scale","family","p10","p50","p90","p_participation","fallback"]:current[col]=pred[col]
            keys=["game_id","player_id"]
            paired=prior[keys+["actual"]].merge(current[keys+["actual"]],on=keys,suffixes=("_base","_new"),validate="one_to_one")
            if len(paired)!=len(prior) or not np.allclose(paired.actual_base,paired.actual_new,equal_nan=True):raise ValueError("baseline outcome/population version mismatch")
            current.to_parquet(output/f"{target}-rows.parquet",index=False)
            scores={"base":summarize(prior),"plus_ngs":summarize(current)}
            field="brier" if target=="anytime_td" else "mae"
            base=scores["base"].get("bernoulli",{}).get(field) if field=="brier" else scores["base"].get(field)
            new=scores["plus_ngs"].get("bernoulli",{}).get(field) if field=="brier" else scores["plus_ngs"].get(field)
            results.append({"target":target,"state":"EVALUATED_DEVELOPMENT_ONLY","primary_metric":field,"base_loss":base,"ngs_loss":new,
                            "relative_gain":(base-new)/base if base and new is not None else None,"scores":scores,
                            "parameters":pred.attrs,"warnings":[str(w.message) for w in captured]})
        except Exception as exc:results.append({"target":target,"state":"FAILED","error":repr(exc)})
        (output/"trials.json").write_text(json.dumps(results,indent=2,allow_nan=False))
    (output/"trials.json").write_text(json.dumps(results,indent=2,allow_nan=False))
    report={"registration":config,"manifest":manifest,"elapsed_seconds":time.monotonic()-started,"results":results,
            "future_confirmation":"not read","promotion":[],"new_prospective_activation":False,
            "interpretation":"already exposed development only; incremental inputs need not improve loss; current NGS unavailable"}
    (output/"report.json").write_text(json.dumps(report,indent=2,default=str,allow_nan=False))
    return report,output


if __name__=="__main__":
    root=Path.cwd();report,path=run(root,root/"data")
    print(json.dumps({"output":str(path),"elapsed_seconds":report["elapsed_seconds"],"results":[{k:r.get(k) for k in ["target","state","base_loss","ngs_loss","relative_gain"]} for r in report["results"]]},indent=2))
