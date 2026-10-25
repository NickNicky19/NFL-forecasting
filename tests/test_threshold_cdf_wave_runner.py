"""Fictional contracts only; no retained NFL cache or fit is opened."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

spec=importlib.util.spec_from_file_location("threshold_wave",Path(__file__).resolve().parents[1]/"tools/run_threshold_cdf_after_audit.py")
wave=importlib.util.module_from_spec(spec);spec.loader.exec_module(wave)


def rows():
    return pd.DataFrame({"season":[2001]*8,"week":list(range(1,9)),"game_id":[f"g{x}" for x in range(8)],
        "player_id":["p"]*8,"participation_state":["played"]*8,"actual":[0.]*8,
        "mean":[.3]*8,"median":[0.]*8,"fallback":[""]*8,
        "crps":[.1]*8,"log_score":[.2]*8,"brier":[.09]*8,"p10":[0.]*8,"p90":[1.]*8,"mass_zero":[.7]*8})


def test_paired_week_bootstrap_keeps_games():
    a=rows();b=rows();a["mean"]+=.1
    p=wave.paired(a,b,"MSE","count")
    assert p["n"]==8 and p["weeks"]==8 and p["delta"]>0
    assert p["intervals"]["week"][0]>0


def test_infinite_log_population_is_retained():
    a=rows();b=rows();a.loc[0,"log_score"]=np.inf
    p=wave.paired(a,b,"log_score","count")
    assert p["n"]==8 and p["candidate_infinite"]==1 and p["delta"] is None


def test_participation_mismatch_rejects_pair():
    a=rows();b=rows();b.loc[0,"participation_state"]="unknown"
    with pytest.raises(ValueError,match="population"):wave.paired(a,b,"crps","count")


def test_unknown_dnp_missing_and_zero_stay_distinct():
    a=rows();a.loc[0,"participation_state"]="DNP";a.loc[1,"participation_state"]="unknown";a.loc[2,"actual"]=np.nan
    s=wave.loss_summary(a,"count")
    assert s["DNP"]==1 and s["unknown_participation"]==1 and s["played_missing_stat"]==1 and s["played_zero"]==5


def test_count_fallback_mean_leaves_warm_point():
    from nfl_lab.cdf_engine import SupportPrior
    class Model:
        priors={"RB":SupportPrior("count",q=.75)}
        global_prior=None
        def predict(self,query):return np.array([8.,2.]),np.array(["","cold_start_role_prior"])
    points,reasons=wave.count_mean(Model(),pd.DataFrame({"position":["RB","RB"]}))
    assert points.tolist()==[8.,3.] and reasons[0]==""


def test_mean_control_is_not_scored_as_a_distribution():
    a=rows();a[["crps","log_score","brier"]]=np.nan;a["median"]=np.nan
    s=wave.loss_summary(a,"count")
    assert s["mean"]["n"]==8 and s["median"]["n"]==0 and "distribution" not in s


def test_approved_source_participation_rate_stays_unavailable():
    raw=pd.DataFrame({"f_player_play_rate8":[1.,1.,np.nan],"f_player_known_participation_n8":[2.,1.,0.]})
    out=wave.qualify_source_features(raw)
    assert out.f_player_play_rate8.isna().all()
    assert out.f_player_known_participation_n8.tolist()==[2.,1.,0.]
    assert out.participation_probability_state.eq("unavailable_incomplete_nonappearance_denominator").all()
    assert raw.f_player_play_rate8.notna().sum()==2
