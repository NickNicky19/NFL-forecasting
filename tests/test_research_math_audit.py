"""Independent fictional arithmetic for the bounded 2026-10-25 research review.

No NFL observations, confirmation outcomes, private artifacts or source calls.
"""
from fractions import Fraction
import json
import math

import numpy as np
import pandas as pd
import pytest

from nfl_lab.cdf_engine import MixtureBatch, SupportPrior
from nfl_lab.cdf_evaluation import paired_distribution_interval
from nfl_lab.scoring import PPR_COMPONENTS, score_ppr
from nfl_lab.skill import sample_joint_components, summarize_joint_components


def loss_panel(losses):
    return pd.DataFrame({
        "season": 2001, "week": np.arange(len(losses)) + 1,
        "game_id": [f"fictional-game-{i}" for i in range(len(losses))],
        "player_id": "fictional-player", "primary_role": True,
        "actual": 1., "log_score": losses,
    })


@pytest.mark.parametrize("cluster", ["week", "game"])
@pytest.mark.parametrize("left,right,state", [
    ([math.inf, 0.], [math.log(2), math.log(2)], "positive_infinity"),
    ([math.log(2), math.log(2)], [math.inf, 0.], "negative_infinity"),
    ([math.inf, 0.], [math.inf, 0.], "undefined_both_infinite"),
    ([math.inf, 0.], [0., math.inf], "undefined_both_infinite"),
])
def test_impossible_events_remain_in_paired_log_loss(left, right, state, cluster):
    # -log(0) is infinite; an average containing it cannot become finite by
    # omitting that observed event. Infinity minus infinity is undefined.
    result = paired_distribution_interval(loss_panel(left), loss_panel(right),
                                          "log_score", cluster=cluster)
    assert result["diagnostic_version"] == "paired-distribution-interval-v2-20261025"
    assert result["paired_rows"] == 2
    assert result["clusters"] == 2
    assert result["delta_state"] == state
    assert result["mean_delta_candidate_minus_control"] is None
    assert result["interval"] is None
    assert result["candidate_infinite_log_losses"] == sum(math.isinf(x) for x in left)
    assert result["control_infinite_log_losses"] == sum(math.isinf(x) for x in right)
    json.dumps(result, allow_nan=False)


def test_finite_log_losses_and_missing_scores_keep_their_distinct_meanings():
    left, right = loss_panel([1.] * 10 + [np.nan]), loss_panel([3.] * 11)
    result = paired_distribution_interval(left, right, "log_score", cluster="week")
    assert result["paired_rows"] == 10
    assert result["delta_state"] == "finite"
    assert result["mean_delta_candidate_minus_control"] == -2.
    assert result["interval"] == [-2., -2.]
    with pytest.raises(ValueError, match="negative infinite"):
        paired_distribution_interval(loss_panel([-math.inf]), loss_panel([0.]),
                                     "log_score", cluster="game")


def test_geometric_mixture_matches_rational_calculation():
    # P(k)=2^(-k-1), mixed 1/4 with empirical half mass each at 0 and 2.
    # F(0)=1/2, F(1)=9/16; for k>=2, 1-F(k)=2^(-k-3).
    # CRPS(y=1)=1/4+49/256+sum_{k>=2}2^(-2k-6)=85/192.
    law = MixtureBatch([0, 2], [[.5, .5]], SupportPrior("count", q=.5), prior_weight=.25)
    assert law.mean[0] == 1.
    assert law.variance[0] == 1.25
    assert law.crps([1])[0] == pytest.approx(float(Fraction(85, 192)), abs=1e-14)
    assert law.logpmf([1])[0] == pytest.approx(-math.log(16))
    assert law.cdf([0])[0] == .5
    assert law.quantile(.5)[0] == 0
    assert law.quantile(.9)[0] == 2


def test_signed_mixture_uses_negative_support_and_independent_lattice_sum():
    # A centered bilateral geometric with q=1/2 has variance 4. The empirical
    # atoms (-3,1) with weights (1/4,3/4) have mean 0 and second moment 3.
    law = MixtureBatch([-3, 1], [[.25, .75]], SupportPrior("signed_integer", center=-2, q=.5), prior_weight=.2)
    assert law.mean[0] == pytest.approx(-.4)
    assert law.variance[0] == pytest.approx(3.84)
    grid = np.arange(-200, 201)
    mass = .2 / 3 * .5 ** np.abs(grid + 2)
    mass[grid == -3] += .8 * .25
    mass[grid == 1] += .8 * .75
    expected = np.sum((np.cumsum(mass) - (grid >= -1)) ** 2)
    assert law.crps([-1])[0] == pytest.approx(expected, abs=1e-13)


def test_bernoulli_mixture_probability_is_the_law():
    law = MixtureBatch([0, 1], [[.6, .4]], SupportPrior("bernoulli", p=.2), prior_weight=.25)
    # 3/4*.4 + 1/4*.2 = .35; binary CRPS is Brier.
    assert law.mean[0] == pytest.approx(.35)
    assert law.crps([1])[0] == pytest.approx(.65 ** 2)
    assert law.logpmf([1])[0] == pytest.approx(math.log(.35))


def test_ppr_scores_each_joint_fumble_outcome_before_averaging():
    a, b = ({k: 0. for k in PPR_COMPONENTS} for _ in range(2))
    a["fum_rec_td"] = 1.
    b["idp_fum_rec"] = 1.
    assert score_ppr(a).value == 6.
    assert score_ppr(b).value == 0.
    assert summarize_joint_components(pd.DataFrame([a, b]))["fantasy_ppr"]["mean"] == 3.
    assert score_ppr({k: (a[k] + b[k]) / 2 for k in a}).value == 0.
    del a["st_ff"]
    assert score_ppr(a).value is None


def test_joint_poisson_thinning_and_shared_participation_have_independent_expectation():
    # Independent Poisson thinning gives TD means .6 and .4. Thus conditional
    # P(any TD)=1-exp(-1); a shared Bernoulli(.4) participation multiplies it.
    means = {"rush_att": 2., "rush_td": .6, "rec_tgt": 4., "rec": 2., "rec_td": .4}
    n = 30000
    draws = sample_joint_components(means, pd.DataFrame(), draws=n, seed=456,
                                   population="all_player", p_participation=.4)
    probability = .4 * (1 - math.exp(-1))
    actual = ((draws.rush_td + draws.rec_td) > 0).mean()
    assert abs(actual - probability) < 6 * math.sqrt(probability * (1 - probability) / n)
    assert (draws.rush_td <= draws.rush_att).all()
    assert (draws.rec_td <= draws.rec).all()
    assert (draws.rec <= draws.rec_tgt).all()
    assert draws.eq(0).all(axis=1).mean() >= .57


def test_future_artifact_replay_uses_frozen_prior_and_new_qualified_features(tmp_path, monkeypatch):
    from nfl_lab import models
    from nfl_lab.model_artifacts import predict_artifact
    train = pd.DataFrame({
        "player_id": ["fictional-player"] * 2, "game_id": ["fictional-old-a", "fictional-old-b"],
        "position": "QB", "team": "A", "opponent": "B", "participation_state": "played",
        "kickoff_utc": pd.to_datetime(["2000-01-01", "2000-01-09"], utc=True),
        "outcome_available_utc": pd.to_datetime(["2000-01-08", "2000-01-16"], utc=True),
        "pass_yd": [10., 20.],
    })
    query = train.iloc[:1].copy()
    query["game_id"] = "fictional-future"
    query["kickoff_utc"] = pd.Timestamp("2001-01-01", tz="UTC")
    query["cutoff_utc"] = pd.Timestamp("2000-12-31", tz="UTC")
    query["f_player_pass_yd_mean3"], query["f_player_pass_yd_n3"] = 6., 1.
    artifact = tmp_path / "fictional-model.json"
    result = models.fit_predict(train, query, "pass_yd", "recent", artifact_path=artifact)
    assert result["mean"].iloc[0] == 12.75  # (6 + 3*15)/(1+3)
    def forbidden(*args, **kwargs):
        raise AssertionError("replay must not fit")
    monkeypatch.setattr(models, "fit_predict", forbidden)
    query["f_player_pass_yd_mean3"], query["f_player_pass_yd_n3"] = 30., 3.
    query["pass_yd"] = 999999.  # An outcome column cannot influence inference.
    replay = predict_artifact(artifact, query, input_manifest={
        "source_qualified": True, "availability_verified": True, "input_sha256": "b" * 64})
    assert replay["mean"].iloc[0] == 22.5  # (3*30 + 3*15)/(3+3)
