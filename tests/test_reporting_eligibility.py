import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab.reporting import finish_reports


def make_report(tmp_path,change=None,target="rec",missing_manifest=False):
    trials=[]
    methods=["recent","ridge"]
    registration={"seasons":{"development":[2022,2023]},"candidate_families":methods+["raw_sleeper"]}
    if not missing_manifest:(tmp_path/"manifest.json").write_text(json.dumps({"registration":registration}))
    for season in [2022,2023]:
        for method in methods:
            if (change=="partial" and method=="ridge" and season==2023) or (change=="absent" and method=="ridge"):
                trials.append({"season":season,"target":target,"method":method,"state":"NOT_RUN_BUDGET_EXHAUSTED"});continue
            rows=pd.DataFrame({"season":season,"week":1,"game_id":[f"{season}-a",f"{season}-b"],"player_id":["a","b"],"team":"T","opponent":"O","position":"WR","target":target,"method":method,"split":"development","participation_state":"played","actual":[1.,2.],"mean":[1.,2.] if method=="ridge" else [2.,3.],"scale":1.,"family":"normal","p_participation":.9,"fallback":""})
            if change=="coverage" and season==2023 and method=="ridge":rows=rows.iloc[:1]
            if change=="outcome" and season==2023 and method=="ridge":rows.loc[1,"actual"]=3.
            if change=="duplicate" and season==2023:rows=pd.concat([rows,rows.iloc[-1:]],ignore_index=True)
            if change=="permuted" and method=="ridge":rows=rows.iloc[::-1]
            if target=="fantasy_ppr":rows["actual"]=np.nan;rows["mean"]=np.nan
            rows.to_parquet(tmp_path/f"{season}-{target}-{method}.parquet",index=False)
            trials.append({"season":season,"target":target,"method":method,"state":"EVALUATED"})
    (tmp_path/"trials.json").write_text(json.dumps(trials))


@pytest.mark.parametrize("change",["partial","absent"])
def test_incomplete_development_blocks_target_selection(tmp_path,change):
    make_report(tmp_path,change)
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["state"]=="DEVELOPMENT_PENDING"
    assert "development_selected_method" not in selected
    assert selected["planned_development_seasons"]==[2022,2023]
    assert next(r for r in selected["development_eligibility"] if r["method"]=="ridge")["state"]=="DEVELOPMENT_PENDING"
    assert json.loads((tmp_path/"summary.json").read_text())


@pytest.mark.parametrize("change",["coverage","outcome","duplicate"])
def test_unmatched_support_outcomes_or_duplicate_keys_block_selection(tmp_path,change):
    make_report(tmp_path,change)
    original_trials=(tmp_path/"trials.json").read_bytes()
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["state"]=="INELIGIBLE_COVERAGE"
    assert "development_selected_method" not in selected
    assert (tmp_path/"trials.json").read_bytes()==original_trials
    summaries=json.loads((tmp_path/"summary.json").read_text())
    assert all("mae" in s for s in summaries)


def test_complete_fair_selection_ignores_archival_abstentions_without_extra_reads(tmp_path,monkeypatch):
    make_report(tmp_path,"permuted")
    original=pd.read_parquet;reads=[]
    def counted(path,*args,**kwargs):
        reads.append(str(path));return original(path,*args,**kwargs)
    monkeypatch.setattr(pd,"read_parquet",counted)
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["development_selected_method"]=="ridge"
    assert selected["state"]=="VALIDATION_PENDING_OR_NOT_RUN"
    assert all(r["state"]=="ELIGIBLE" for r in selected["development_eligibility"])
    assert "raw_sleeper" not in {r["method"] for r in selected["development_eligibility"]}
    assert len(reads)==len(set(reads))==4


def test_missing_manifest_uses_registered_default_development_folds(tmp_path):
    make_report(tmp_path,missing_manifest=True)
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["planned_development_seasons"]==[2022,2023]
    assert selected["development_selected_method"]=="ridge"


def test_zero_supported_exact_ppr_retains_no_supported_state(tmp_path):
    make_report(tmp_path,target="fantasy_ppr")
    finish_reports(tmp_path)
    assert json.loads((tmp_path/"selected.json").read_text())==[{"target":"fantasy_ppr","state":"NO_SUPPORTED_COMPARISON"}]
