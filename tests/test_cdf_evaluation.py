"""Fictional frozen-row scoring and exact-control binding checks."""
import numpy as np
import pandas as pd
import pytest

from nfl_lab.cdf_engine import LeafCDFModel, prediction_rows, score_frozen_rows
from nfl_lab.cdf_evaluation import bind_saved_control, paired_interval, report_tables
from test_cdf_engine import fictional


def test_frozen_inference_then_single_scoring_reproduces_direct_score():
    train, test, category = fictional()
    model = LeafCDFModel.fit(train, category, "base")
    frozen = prediction_rows(model, test)
    assert frozen.actual.isna().all()
    assert frozen.participation_state.eq("unread").all()
    scored = score_frozen_rows(model, test, frozen)
    pd.testing.assert_frame_equal(scored, prediction_rows(model, test, score=True))
    assert frozen.actual.isna().all()


def test_exact_saved_control_binding_rejects_changed_outcome_state_or_coverage():
    train, test, category = fictional()
    candidate = prediction_rows(LeafCDFModel.fit(train, category, "base"), test, score=True)
    saved = candidate.copy()
    saved["method"] = "pooled"
    saved["mean"] = 10.25
    result = bind_saved_control(saved, test, category, "pooled")
    assert result["mean"].eq(10.25).all()
    assert result.crps.isna().all()
    for mutation in ["actual", "state", "coverage", "team", "opponent", "position", "kickoff_utc", "cutoff_utc"]:
        changed = saved.copy()
        if mutation == "actual":
            changed.loc[changed.index[0], "actual"] += 1
        elif mutation == "state":
            changed.loc[changed.index[0], "participation_state"] = "DNP"
        elif mutation == "coverage":
            changed = changed.iloc[1:]
        elif mutation.endswith("_utc"):
            changed.loc[changed.index[0], mutation] += pd.Timedelta(hours=1)
        else:
            changed.loc[changed.index[0], mutation] = "fictional-changed"
        with pytest.raises(ValueError):
            bind_saved_control(changed, test, category, "pooled")


def test_primary_uses_candidate_median_and_control_mean_with_nominal_intervals():
    train, test, category = fictional()
    candidate = prediction_rows(LeafCDFModel.fit(train, category, "base"), test, score=True)
    candidate["week"] = np.arange(len(candidate)) + 1
    control = candidate.copy()
    control["method"] = "pooled"
    control["mean"] = control.actual + 3
    candidate["median"] = candidate.actual + 1
    candidate["mean"] = candidate.actual + 100
    interval = paired_interval(candidate, control, "count", cluster="week")
    assert interval["mean_delta_candidate_minus_control"] == pytest.approx(-2.)
    assert interval["interval"] == pytest.approx([-2., -2.])
    assert "no familywise" in interval["interval_semantics"]
    report = report_tables(pd.concat([candidate, control], ignore_index=True), category)
    assert report["paired"][0]["comparator"] == "pooled"
    assert report["paired"][0]["status"] == "primary"


def test_failed_annual_cell_intersection_is_explicit_but_partial_row_loss_rejected():
    train, test, category = fictional()
    candidate = prediction_rows(LeafCDFModel.fit(train, category, "base"), test, score=True)
    control = candidate.copy()
    extra = control.copy()
    extra["season"] = 2023
    control = pd.concat([control, extra], ignore_index=True)
    result = paired_interval(candidate, control, "count", cluster="game")
    assert result["compared_complete_years"] == [2022]
    assert result["excluded_unpaired_years"] == [2023]
    with pytest.raises(ValueError, match="population"):
        paired_interval(candidate.iloc[1:], control, "count", cluster="game")


def test_bernoulli_point_probability_not_median_drives_primary_brier():
    train, test, category = fictional()
    category["support"] = "bernoulli"
    train["pass_att"] %= 2
    test["pass_att"] %= 2
    model = LeafCDFModel.fit(train, category, "base")
    candidate = prediction_rows(model, test, score=True)
    control = candidate.copy()
    control["mean"] = .5
    expected = np.mean((candidate["mean"]-candidate.actual)**2 - (.5-control.actual)**2)
    interval = paired_interval(candidate, control, "bernoulli", cluster="game")
    assert interval["primary_loss"] == "brier"
    assert interval["mean_delta_candidate_minus_control"] == pytest.approx(expected)
