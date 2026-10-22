import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from nfl_lab.evaluation import probability_scores,summarize,paired_week_interval


def test_normal_crps_known_value_and_signed_support():
    s=probability_scores([-1],[-1],[1],"normal")
    assert s["crps"]==pytest.approx((np.sqrt(2)-1)/np.sqrt(np.pi))
    assert s["interval_80_coverage"]==1


def test_bernoulli_no_clipping_impossible_events():
    s=probability_scores([1],[0],[1],"bernoulli")
    assert s["infinite_log_losses"]==1 and s["log_score"] is None
    assert s["brier"]==1


def test_count_support_and_zero_mass():
    s=probability_scores([0,1],[.1,1],[1,2],"negbin")
    assert s["crps"]>=0 and s["log_score"]>=0
    with pytest.raises(ValueError):probability_scores([.5],[1],[2],"negbin")
    zero=probability_scores([0],[0],[0],"negbin")
    assert zero["crps"]==0 and zero["log_score"]==0


def test_paired_uses_identical_outcomes():
    rows=[]
    for w in range(1,10):
        for method,mean in [("recent",3),("ridge",2)]:
            rows.append(dict(season=2024,week=w,game_id=str(w),player_id="p",target="rec",actual=1,mean=mean,method=method,participation_state="played"))
    s=paired_week_interval(pd.DataFrame(rows),"recent","ridge")
    assert s["paired_n"]==9 and s["interval"]==[-1,-1]
    frame=pd.DataFrame(rows);frame.loc[0,"actual"]=0
    with pytest.raises(ValueError,match="mismatch"):paired_week_interval(frame,"recent","ridge")


def test_binary_primary_interval_is_brier():
    rows=pd.DataFrame([dict(season=2024,week=1,game_id="g",player_id="p",target="anytime_td",actual=1,mean=p,method=m,participation_state="played") for m,p in [("recent",.1),("ridge",.4)]])
    s=paired_week_interval(rows,"recent","ridge")
    assert s["primary_metric"]=="brier" and s["primary_delta"]==pytest.approx(-.45)
