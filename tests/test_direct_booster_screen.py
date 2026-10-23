"""Fictional scoring/coverage checks; no NFL rows or native estimator fits."""
import numpy as np
import pandas as pd
import pytest

from nfl_lab import direct_booster_screen as screen, direct_boosters as direct
from nfl_lab import models
from test_cdf_engine import fictional


def scored(support="count"):
    _, query, category = fictional()
    category = dict(category, support=support)
    rows = query.copy()
    rows["target"], rows["primary_role"] = "pass_att", True
    rows["actual"] = np.arange(len(rows)) % 2
    rows["point"] = .25
    rows["probability"] = rows.point if support == "bernoulli" else np.nan
    rows["outcome_state"], rows["fallback"], rows["history_state"] = "played_zero", "", "warm"
    rows["method"] = screen.METHODS[0]
    control = rows.copy().assign(method="leaf_cdf", point=.75)
    return rows, control, category


def test_all12_six_pipeline_threeblock_slots_preserve_capability_and_ppr_blocks():
    categories = {target: {"state": "BLOCKED" if target == "fantasy_ppr" else "READY"} for target in models.TARGETS}
    slots = screen.planned_slots(categories, dict(xgboost="1", lightgbm="2", catboost="3"))
    assert len(slots) == 216
    assert sum(s["state"] == "BLOCKED_EXACT_PPR" for s in slots) == 18
    assert sum(s["state"] == "UNRUN" for s in slots) == 198
    assert len({(s["year"], s["target"], s["method"]) for s in slots}) == 216
    missing = screen.planned_slots(categories, dict(xgboost="1", lightgbm=None, catboost="3"))
    assert sum(s["state"] == "UNAVAILABLE_CAPABILITY" for s in missing) == 66


@pytest.mark.parametrize("support,metric", [("count", "mse"), ("signed_integer", "mae"), ("bernoulli", "brier")])
def test_product_loss_uses_shared_pairs_and_exact_declared_functional(support, metric):
    a, b, category = scored(support)
    a["actual"], b["actual"] = 0., 0.
    a.loc[a.index[0], "actual"], b.loc[b.index[0], "actual"] = np.nan, np.nan
    a.loc[a.index[1], "participation_state"] = "unknown"
    b.loc[b.index[1], "participation_state"] = "unknown"
    report, pairs = screen.product_pairs(a, b, category)
    assert report["primary_loss"] == metric and report["paired_rows"] == len(a) - 2
    assert pairs.candidate_loss.iloc[:2].isna().all()
    assert report["candidate_loss"] == pytest.approx(.25 ** 2 if support != "signed_integer" else .25)
    assert report["control_loss"] == pytest.approx(.75 ** 2 if support != "signed_integer" else .75)
    assert report["improvement_pct"] > 0
    assert pairs.cutoff_utc.equals(a.cutoff_utc)


def test_pairs_reject_different_population_cutoff_or_outcome():
    a, b, category = scored()
    with pytest.raises(ValueError, match="populations"):
        screen.product_pairs(a, b.iloc[1:], category)
    with pytest.raises(ValueError, match="cutoff"):
        screen.product_pairs(a, b.assign(cutoff_utc=b.cutoff_utc + pd.Timedelta(seconds=1)), category)
    with pytest.raises(ValueError, match="outcomes"):
        screen.product_pairs(a, b.assign(actual=99), category)


def test_binary_boundary_loss_not_clipped():
    a, b, category = scored("bernoulli")
    a["actual"], b["actual"], a["point"], b["point"] = 1., 1., 0., 1.
    report, _ = screen.product_pairs(a, b, category)
    assert report["candidate_loss"] == 1.
    assert report["paired_binary"]["candidate"]["infinite_log_losses"] == len(a)


def test_target_report_preserves_annual_pooled_populations_and_pair_rows():
    a, b, category = scored()
    aa, bb = [], []
    for year in screen.shared.YEARS:
        part = a.assign(season=year, year=year)
        aa.append(part)
        bb.extend(b.assign(season=year, year=year, method=method) for method in screen.CONTROLS)
    report, losses = screen.target_report(pd.concat(aa, ignore_index=True), pd.concat(bb, ignore_index=True), category)
    assert len(report["summaries"]) == 8 and len(report["pairs"]) == 40
    assert len(losses) == 3 * len(a) * len(screen.CONTROLS)
    assert all(p["primary_loss"] == "mse" for p in report["pairs"])
    pooled = [p for p in report["pairs"] if p["period"] == "pooled_2022_2024"]
    assert all(p["paired_rows"] == 3 * len(a) for p in pooled)
    assert all(p["week_interval"]["state"] == "N/A" for p in pooled)  # only six fictional weeks
    assert all(p["candidate_loss"] == pytest.approx(np.mean((a.point - a.actual)**2)) for p in pooled)


def test_vectorized_subgroups_include_unknown_zero_and_signed_errors():
    a, _, category = scored("signed_integer")
    a["point"], a["actual"] = -2., -1.
    a.loc[a.index[0], "participation_state"] = "unknown"
    a.loc[a.index[1], "fallback"] = "cold_start_role_prior"
    groups = screen.subgroup_rows(a, category)
    overall = groups.loc[groups.dimension.eq("position")].iloc[0]
    assert overall.offered_rows == len(a) and overall.scored_rows == len(a)-1
    assert overall.mae == 1. and overall.mse == 1. and overall.bias == -1.
    assert overall.fallback_rows == 1
    assert set(groups.dimension) == {"player_id", "position", "team", "opponent", "fallback", "history_state"}


def test_partial_pooled_years_are_explicit_and_cannot_be_nominated():
    a, b, category = scored()
    controls = pd.concat([b.assign(method=method) for method in screen.CONTROLS], ignore_index=True)
    report, _ = screen.target_report(a, controls, category)
    pooled = [p for p in report["pairs"] if p["period"] == "pooled_2022_2024"]
    assert all(p["included_years"] == [2022] and p["missing_required_years"] == [2023, 2024] for p in pooled)
    assert all(p["completion"] == "PARTIAL_REQUIRED_YEARS" for p in pooled)
    assert all(n["decision"] == "NOT_NOMINATED" for n in report["research_nominations"])


def test_zero_control_primary_error_remains_na_not_a_manufactured_gain():
    a, b, category = scored()
    a["point"], b["point"], a["actual"], b["actual"] = 0., 0., 0., 0.
    report, _ = screen.product_pairs(a, b, category)
    assert report["candidate_loss"] == report["control_loss"] == 0.
    assert report["improvement_pct"] is None


def test_coverage_masks_are_compared_by_identity_not_input_order():
    a, b, category = scored()
    a.loc[a.index[0], "point"], b.loc[b.index[0], "point"] = np.nan, np.nan
    same, _ = screen.product_pairs(a, b.iloc[::-1], category)
    assert same["forecast_finite_masks_equal"]
    b.loc[b.index[0], "point"], b.loc[b.index[1], "point"] = 1., np.nan
    different, _ = screen.product_pairs(a, b, category)
    assert not different["forecast_finite_masks_equal"]


@pytest.mark.parametrize("field", ["improvement_pct", "candidate_loss", "control_loss", "bias_prediction_minus_actual", "absolute_error_p95", "annual_loss"])
@pytest.mark.parametrize("value", [np.nan, np.inf])
def test_nomination_fails_closed_for_nonfinite_primary_secondary_or_annual(field, value):
    pairs = []
    for control in ("leaf_cdf", "role_B"):
        for period in (*screen.shared.YEARS, "pooled_2022_2024"):
            pairs.append(dict(candidate=screen.METHODS[0], comparator=control, population="primary_roles",
                period=period, missing_required_years=[], improvement_pct=3., candidate_loss=.97, control_loss=1.,
                forecast_finite_masks_equal=True, candidate_point_metrics={"bias_prediction_minus_actual": .1, "absolute_error_p95": 5.},
                control_literal_point_metrics={"bias_prediction_minus_actual": .1, "absolute_error_p95": 5.}))
    assert screen.research_nominations({"pairs": pairs})[0]["decision"] == "DEVELOPMENT_LEAD_REQUIRES_LATER_CONFIRMATION"
    target = next(p for p in pairs if p["period"] == (2022 if field == "annual_loss" else "pooled_2022_2024"))
    if field in ("bias_prediction_minus_actual", "absolute_error_p95"):
        target["candidate_point_metrics"][field] = value
    else:
        target["candidate_loss" if field == "annual_loss" else field] = value
    assert screen.research_nominations({"pairs": pairs})[0]["decision"] == "NOT_NOMINATED"
