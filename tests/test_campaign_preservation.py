import json

import pandas as pd

from nfl_lab.evaluation import campaign


def test_reruns_keep_separate_attempts_and_registration(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    config={"registration_id":"test","budgets":{"max_training_seconds":1,"candidate_configurations_per_category":1},"seasons":{"validation":[2024]},"targets":["rec"],"candidate_families":["recent"]}
    frame=pd.DataFrame({"season":[2021],"kickoff_utc":["2021-01-01T00:00:00Z"]})
    a=campaign(frame,tmp_path/"runs",config,seasons=[2024])
    b=campaign(frame,tmp_path/"runs",config,seasons=[2024])
    assert a["attempt_id"]!=b["attempt_id"]
    assert len(list((tmp_path/"runs").glob("*/manifest.json")))==2
