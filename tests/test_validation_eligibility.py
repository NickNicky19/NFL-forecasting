import json

import pandas as pd
import pytest

from nfl_lab.reporting import finish_reports
from test_reporting_eligibility import make_report


def validation_report(tmp_path,change):
    make_report(tmp_path)
    trials=json.loads((tmp_path/"trials.json").read_text())
    for method in ["recent","ridge"]:
        rows=pd.DataFrame({"season":2024,"week":1,"game_id":["2024-a","2024-b"],"player_id":["a","b"],"team":"T","opponent":"O","position":"WR","target":"rec","method":method,"split":"validation","participation_state":"played","actual":[1.,2.],"mean":[1.,2.] if method=="ridge" else [2.,3.],"scale":1.,"family":"normal","p_participation":.9,"fallback":""})
        if change=="keys" and method=="ridge":rows.loc[1,"game_id"]="2024-substituted"
        if change=="outcomes" and method=="ridge":rows.loc[1,"actual"]=3.
        if change=="duplicate":rows=pd.concat([rows,rows.iloc[-1:]],ignore_index=True)
        if change=="missing_key" and method=="ridge":rows.loc[1,"player_id"]=None
        if change=="unequal_count" and method=="ridge":rows=rows.iloc[:1]
        if change=="fair" and method=="ridge":rows=rows.iloc[::-1]
        rows.to_parquet(tmp_path/f"2024-rec-{method}.parquet",index=False)
        trials.append({"season":2024,"target":"rec","method":method,"state":"EVALUATED"})
    (tmp_path/"trials.json").write_text(json.dumps(trials))


@pytest.mark.parametrize("change",["keys","outcomes","duplicate","missing_key","unequal_count"])
def test_invalid_validation_support_retains_metrics_without_gain_or_pairing(tmp_path,monkeypatch,change):
    validation_report(tmp_path,change)
    original_trials=(tmp_path/"trials.json").read_bytes()
    def no_pairing(*args,**kwargs):
        raise AssertionError("ineligible validation must not be paired")
    monkeypatch.setattr("nfl_lab.reporting.paired_week_interval",no_pairing)
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["development_selected_method"]=="ridge"
    assert selected["state"]=="VALIDATION_INELIGIBLE_COVERAGE"
    assert selected["coverage_unchanged"] is False
    assert selected["validation_recent"] is not None
    assert selected["validation_candidate"] is not None
    assert "relative_primary_gain" not in selected
    assert "paired_n" not in selected
    assert "bias_gate" not in selected
    assert json.loads((tmp_path/"paired.json").read_text())==[]
    assert (tmp_path/"trials.json").read_bytes()==original_trials
    validation=[s for s in json.loads((tmp_path/"summary.json").read_text()) if s["split"]=="validation"]
    assert len(validation)==2 and all("mae" in s for s in validation)
    assert set(selected["validation_support"])=={"recent","candidate"}


def test_fair_validation_keeps_matched_gain_and_pairing(tmp_path):
    validation_report(tmp_path,"fair")
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["state"]=="EXPLORATORY_HISTORICAL_ONLY_CONFIRMATION_PENDING"
    assert selected["coverage_unchanged"] is True
    assert selected["relative_primary_gain"]==1.
    assert selected["paired_n"]==2
    assert selected["validation_support"]["recent"]["scored_key_actual_sha256"]==selected["validation_support"]["candidate"]["scored_key_actual_sha256"]
    assert len(json.loads((tmp_path/"paired.json").read_text()))==1


@pytest.mark.parametrize("state",["FAILED","NOT_RUN_BUDGET_EXHAUSTED","missing"])
def test_stale_development_parquet_cannot_replace_evaluated_trial_evidence(tmp_path,state):
    make_report(tmp_path)
    trials=json.loads((tmp_path/"trials.json").read_text())
    for trial in trials:
        if trial["season"]==2023 and trial["method"]=="ridge":trial["state"]=state
    if state=="missing":trials=[r for r in trials if r["state"]!="missing"]
    (tmp_path/"trials.json").write_text(json.dumps(trials))
    assert (tmp_path/"2023-rec-ridge.parquet").exists()
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["state"]=="DEVELOPMENT_PENDING"
    assert "development_selected_method" not in selected
    assert len(json.loads((tmp_path/"summary.json").read_text()))==2


@pytest.mark.parametrize("extra_state",["EVALUATED","FAILED"])
def test_duplicate_or_conflicting_development_trial_entries_block_selection(tmp_path,extra_state):
    make_report(tmp_path)
    trials=json.loads((tmp_path/"trials.json").read_text())
    trials.append({"season":2023,"target":"rec","method":"ridge","state":extra_state})
    (tmp_path/"trials.json").write_text(json.dumps(trials))
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["state"]=="INELIGIBLE_COVERAGE"
    assert "development_selected_method" not in selected


@pytest.mark.parametrize("state",["FAILED","NOT_RUN_BUDGET_EXHAUSTED","missing","duplicate"])
def test_stale_validation_parquet_requires_unique_evaluated_trial(tmp_path,state,monkeypatch):
    validation_report(tmp_path,"fair")
    trials=json.loads((tmp_path/"trials.json").read_text())
    for trial in trials:
        if trial["season"]==2024 and trial["method"]=="ridge":
            if state!="duplicate":trial["state"]=state
    if state=="missing":trials=[r for r in trials if r["state"]!="missing"]
    if state=="duplicate":trials.append({"season":2024,"target":"rec","method":"ridge","state":"EVALUATED"})
    (tmp_path/"trials.json").write_text(json.dumps(trials))
    def no_pairing(*args,**kwargs):raise AssertionError("invalid trial evidence cannot be paired")
    monkeypatch.setattr("nfl_lab.reporting.paired_week_interval",no_pairing)
    finish_reports(tmp_path)
    selected=json.loads((tmp_path/"selected.json").read_text())[0]
    assert selected["state"]=="VALIDATION_INELIGIBLE_COVERAGE"
    assert selected["validation_trial_evidence"]["candidate"]["eligible"] is False
    assert "relative_primary_gain" not in selected
    assert json.loads((tmp_path/"paired.json").read_text())==[]
