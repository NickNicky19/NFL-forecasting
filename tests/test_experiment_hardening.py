import json
import os
import signal

import pandas as pd
import pytest

from nfl_lab.evaluation import campaign
from nfl_lab.experiment import ExperimentTerminated, run_experiment
from nfl_lab.state import records


def setup_inputs(tmp_path, methods=("recent",)):
    config={"registration_id":"bounded-test","budgets":{"max_training_seconds":1200,"candidate_configurations_per_category":12},"seasons":{"validation":[2024]},"targets":["rec"],"candidate_families":list(methods)}
    frame=pd.DataFrame({"season":[2021,2024],"week":[1,1],"game_id":["old","new"],"player_id":["private-row-sentinel"]*2,"position":["WR"]*2,"team":["A"]*2,"opponent":["B"]*2,"participation_state":["played"]*2,"kickoff_utc":["2021-01-01T00:00:00Z","2024-01-01T00:00:00Z"],"rec":[1,1]})
    cache=tmp_path/"data";path=cache/"processed/features.parquet";path.parent.mkdir(parents=True)
    frame.to_parquet(path,index=False)
    return config,frame,cache


def predictions(train,test,target,method):
    return pd.DataFrame({"mean":1.,"scale":1.,"family":"negbin","p10":0.,"p50":1.,"p90":2.,"p_participation":.9,"fallback":""},index=test.index)


def test_reporting_reserve_preserves_total_budget_and_checkpoints_every_skip(tmp_path,monkeypatch):
    config,frame,_=setup_inputs(tmp_path,("recent","pooled","ridge"))
    clock=[0.];called=[]
    monkeypatch.setattr("nfl_lab.evaluation.time.monotonic",lambda:clock[0])
    def bounded_fit(*args):
        called.append(args[-1]);clock[0]=1030.
        return predictions(*args)
    monkeypatch.setattr("nfl_lab.models.fit_predict",bounded_fit)
    monkeypatch.setattr("nfl_lab.reporting.finish_reports",lambda output:None)
    result=campaign(frame,tmp_path/"runs",config,seasons=[2024])
    assert called==["recent"]
    assert result["total_budget_seconds"]==1200
    assert result["fit_launch_budget_seconds"]==1020
    assert result["reporting_reserve_seconds"]==180
    assert result["fit_launch_budget_seconds"]+result["reporting_reserve_seconds"]==1200
    assert result["budget_skips"]==2
    output=tmp_path/"runs"/result["attempt_id"]
    trials=json.loads((output/"trials.json").read_text())
    assert [r["state"] for r in trials]==["EVALUATED","NOT_RUN_BUDGET_EXHAUSTED","NOT_RUN_BUDGET_EXHAUSTED"]
    assert len(list((output/"trial-checkpoints").glob("*.json")))==3
    assert len(trials[0]["row_file_sha256"])==64
    assert trials[0]["forecast_rows"]==1
    assert len(result["rows_sha256"])==64
    assert not (tmp_path/"state").exists()


def test_reporting_exception_saves_one_aggregate_then_reraises(tmp_path,monkeypatch):
    config,_,cache=setup_inputs(tmp_path)
    monkeypatch.setattr("nfl_lab.models.fit_predict",predictions)
    def failed_report(output):
        (output/"summary.json").write_text("{")
        raise RuntimeError("injected reporting failure")
    monkeypatch.setattr("nfl_lab.reporting.finish_reports",failed_report)
    with pytest.raises(RuntimeError,match="injected reporting failure"):
        run_experiment(tmp_path,cache,tmp_path/"state",config)
    receipts=list(records(tmp_path/"state","training"))
    assert len(receipts)==1
    receipt=receipts[0]
    assert receipt["state"]=="FAILED"
    assert receipt["campaign"]["phase"]=="reporting"
    assert receipt["trials"][0]["state"]=="EVALUATED"
    assert receipt["checkpoint_read_errors"]==[{"name":"summary","error":"JSONDecodeError"}]
    assert "private-row-sentinel" not in json.dumps(receipt)
    assert "rows" not in receipt


def test_sigterm_checkpoints_active_trial_and_restores_handler(tmp_path,monkeypatch):
    config,_,cache=setup_inputs(tmp_path)
    previous=signal.getsignal(signal.SIGTERM)
    def terminated_fit(*args):
        os.kill(os.getpid(),signal.SIGTERM)
        raise AssertionError("signal should interrupt")
    monkeypatch.setattr("nfl_lab.models.fit_predict",terminated_fit)
    with pytest.raises(ExperimentTerminated) as caught:
        run_experiment(tmp_path,cache,tmp_path/"state",config)
    assert caught.value.code==143
    assert signal.getsignal(signal.SIGTERM)==previous
    receipts=list(records(tmp_path/"state","training"))
    assert len(receipts)==1
    assert receipts[0]["state"]=="INTERRUPTED"
    assert receipts[0]["error"]["signal"]==signal.SIGTERM
    assert receipts[0]["trials"][0]["state"]=="INTERRUPTED"
    output=next((tmp_path/"runs"/config["registration_id"]).iterdir())
    assert len(list((output/"trial-checkpoints").glob("*.json")))==1


def test_preflight_exception_is_preserved_without_raw_features(tmp_path):
    config,_,_=setup_inputs(tmp_path)
    with pytest.raises(RuntimeError,match="run acquire first"):
        run_experiment(tmp_path,tmp_path/"absent",tmp_path/"state",config)
    receipts=list(records(tmp_path/"state","training"))
    assert len(receipts)==1
    assert receipts[0]["state"]=="FAILED"
    assert receipts[0]["trials"]==[]


def test_signal_after_completed_trial_keeps_completed_checkpoint(tmp_path,monkeypatch):
    from nfl_lab.experiment import atomic_checkpoint
    config,_,cache=setup_inputs(tmp_path)
    monkeypatch.setattr("nfl_lab.models.fit_predict",predictions)
    interrupted=[False]
    def checkpoint(path,value):
        if path.name=="progress.json" and value.get("completed_trials")==1 and not interrupted[0]:
            interrupted[0]=True
            raise ExperimentTerminated(signal.SIGTERM)
        atomic_checkpoint(path,value)
    monkeypatch.setattr("nfl_lab.experiment.atomic_checkpoint",checkpoint)
    with pytest.raises(ExperimentTerminated):
        run_experiment(tmp_path,cache,tmp_path/"state",config)
    receipt=next(records(tmp_path/"state","training"))
    assert receipt["state"]=="INTERRUPTED"
    assert [t["state"] for t in receipt["trials"]]==["EVALUATED"]
    output=next((tmp_path/"runs"/config["registration_id"]).iterdir())
    files=list((output/"trial-checkpoints").glob("*.json"))
    assert len(files)==1
    assert json.loads(files[0].read_text())["state"]=="EVALUATED"


def test_signal_after_terminal_commit_does_not_append_second_receipt(tmp_path,monkeypatch):
    from nfl_lab.state import save
    config,_,cache=setup_inputs(tmp_path)
    monkeypatch.setattr("nfl_lab.models.fit_predict",predictions)
    monkeypatch.setattr("nfl_lab.reporting.finish_reports",lambda output:None)
    calls=[]
    def signal_after_commit(*args,**kwargs):
        key=save(*args,**kwargs)
        calls.append(key)
        if len(calls)==1:os.kill(os.getpid(),signal.SIGTERM)
        return key
    monkeypatch.setattr("nfl_lab.experiment.save",signal_after_commit)
    with pytest.raises(ExperimentTerminated):
        run_experiment(tmp_path,cache,tmp_path/"state",config)
    receipts=list(records(tmp_path/"state","training"))
    assert len(calls)==len(receipts)==1
    assert receipts[0]["state"]=="COMPLETED"
