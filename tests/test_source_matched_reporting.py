"""Fictional frozen scores only; no models, NFL inputs, I/O or fitting."""
import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab import source_matched_reporting as reporting
from nfl_lab.models import COUNT_TARGETS, TARGETS


def categories():
    return {target: {"target": target, "state": "BLOCKED_LABEL_CONTRACT" if target == "fantasy_ppr" else "READY",
        "support": "bernoulli" if target == "anytime_td" else "count" if target in COUNT_TARGETS else "signed_integer",
        "primary_roles": ["QB"], "modeled_roles": ["QB", "RB"]} for target in TARGETS}


def fictional(target="pass_att", *, year_counts=(12, 12, 12), infinite_binary=False):
    rows = []
    for year, n in zip(reporting.YEARS, year_counts):
        for w in range(1, n + 1):
            actual = float(w % 2) if target == "anytime_td" else float(w % 5)
            kickoff = pd.Timestamp(f"{year}-01-01", tz="UTC") + pd.Timedelta(days=7 * w)
            for method in (*reporting.METHODS, "role_prior"):
                binary = target == "anytime_td"
                error = {"leaf_cdf": 1., "median_hgb": 2., "count_A": 3., "role_B": 6., "recent": 4., "pooled": 5., "role_prior": 2.}[method]
                point = (.8 if actual else .2) if binary else actual + error
                if binary and method == "median_hgb":
                    point = .6 if actual else .4
                if binary and infinite_binary and method == "leaf_cdf" and actual == 1:
                    point = 0.
                law = method in reporting.LAW_METHODS
                below = 0. if actual == 0 else 1 - point
                at = 1 - point if actual == 0 else 1.
                with np.errstate(divide="ignore"):
                    log = -np.log(point if actual else 1 - point) if binary else .7 if method == "leaf_cdf" else 1.2
                rows.append({"season": year, "week": w, "game_id": f"fictional-{year}-{w}", "player_id": f"fictional-player-{w}",
                    "year": year, "target": target, "method": method, "point": point,
                    "probability": point if binary else np.nan, "mean": point if law else np.nan,
                    "median": (float(point >= .5) if binary else point) if law else np.nan, "actual": actual, "participation_state": "played",
                    "outcome_state": "played_zero" if actual == 0 else "played_nonzero", "primary_role": w % 3 != 0,
                    "position": "QB" if w % 3 != 0 else "RB", "team": "FIC", "opponent": "TST", "fallback": "" if w % 4 else "cold_start_role_prior",
                    "history_state": "warm" if w % 4 else "cold_or_unknown", "kickoff_utc": kickoff, "cutoff_utc": kickoff - pd.Timedelta(hours=1),
                    "p10": (0. if binary else max(0., actual - 1)) if law else np.nan,
                    "p90": (1. if binary else actual + 4) if law else np.nan,
                    "variance": (point * (1 - point) if binary else 2.) if law else np.nan,
                    "crps": ((point - actual) ** 2 if binary else .4 if method == "leaf_cdf" else 1.2) if law else np.nan,
                    "log_score": log if law else np.nan, "cdf_actual_below": (below if binary else .2) if law else np.nan,
                    "cdf_actual": (at if binary else .6) if law else np.nan})
    return pd.DataFrame(rows)


def comparison(report, target, candidate, comparator, *, population="all_offered", period="pooled2022-2024", distribution=False, metric=None):
    entries = report["targets"][target]["distribution_comparisons" if distribution else "point_comparisons"]
    return next(entry for entry in entries if entry["candidate"] == candidate and entry["comparator"] == comparator
                and entry["population"] == population and entry["period"] == period and (metric is None or entry["metric"] == metric))


def test_exact_pairs_both_populations_losses_negative_improvements_and_all_blocked_slots():
    frame = fictional()
    before = frame.copy(deep=True)
    report, losses = reporting.build_reports(frame, categories())
    assert report["planned_slots"] == 216 and report["blocked_exact_ppr_slots"] == 18
    assert len(report["targets"]) == 12
    assert len(report["targets"]["fantasy_ppr"]["slots"]) == 18
    assert all(slot["state"] == "BLOCKED_EXACT_PPR" for slot in report["targets"]["fantasy_ppr"]["slots"])
    all_rows = comparison(report, "pass_att", "leaf_cdf", "median_hgb")
    primary = comparison(report, "pass_att", "leaf_cdf", "median_hgb", population="primary_roles")
    assert all_rows["paired_rows"] == 36 and primary["paired_rows"] == 24
    assert all_rows["candidate_loss"] == 1. and all_rows["control_loss"] == 2.
    assert all_rows["delta_candidate_minus_control"] == -1. and all_rows["improvement_pct"] == 50.
    losing = comparison(report, "pass_att", "role_B", "recent")
    assert losing["improvement_pct"] == -50.
    assert list(losses) == reporting.LOSS_COLUMNS
    assert len(losses) == 36 * (11 + 2)
    assert not losses.duplicated([*reporting.KEYS, "target", "candidate_method", "comparator", "metric"]).any()
    assert losses.primary_paired_eligible.eq(losses.paired_eligible & losses.primary_role).all()
    assert not any(name in losses for name in ("point", "actual", "mean", "median"))
    assert isinstance(losses.player_id.dtype, pd.CategoricalDtype)
    assert isinstance(losses.target.dtype, pd.CategoricalDtype)
    text = json.dumps(report, allow_nan=False)
    assert "fictional-player" not in text and "fictional-2022" not in text
    pd.testing.assert_frame_equal(frame, before, check_exact=True)


def test_pooled_metrics_are_row_weighted_and_keep_target_units_separate():
    frame = fictional(year_counts=(8, 16, 8))
    for year, error in zip(reporting.YEARS, [1., 5., 10.]):
        mask = frame.method.eq("leaf_cdf") & frame.year.eq(year)
        frame.loc[mask, "point"] = frame.loc[mask, "actual"] + error
        frame.loc[mask, "median"] = frame.loc[mask, "point"]
    report, _ = reporting.build_reports(frame, categories())
    cell = next(v for v in report["targets"]["pass_att"]["summaries"] if v["method"] == "leaf_cdf" and v["period"] == "pooled2022-2024" and v["population"] == "all_offered")
    assert cell["point_metrics"]["mae"] == 5.25
    assert cell["point_metrics"]["mae"] != np.mean([1., 5., 10.])
    assert report["targets"]["pass_att"]["unit"] == "events"


def test_missing_failed_annual_package_retains_na_and_complete_common_years_only():
    frame = fictional()
    frame = frame.loc[~(frame.method.eq("median_hgb") & frame.year.eq(2023))]
    contract = categories()
    contract["pass_att"]["benchmark_slots"] = [{"year": 2023, "method": "median_hgb", "state": "FAILED_CONSUMED", "reason": "private detail"}]
    report, losses = reporting.build_reports(frame, contract)
    pooled = comparison(report, "pass_att", "leaf_cdf", "median_hgb")
    assert pooled["state"] == "PARTIAL_COMMON_COMPLETED_YEARS"
    assert pooled["included_years"] == [2022, 2024] and pooled["excluded_years"] == [2023]
    assert pooled["paired_rows"] == 24
    annual = comparison(report, "pass_att", "leaf_cdf", "median_hgb", period="2023")
    assert annual["state"] == "N/A_MISSING_SLOT"
    slot = next(s for s in report["targets"]["pass_att"]["slots"] if s["year"] == 2023 and s["method"] == "median_hgb")
    assert slot["state"] == "FAILED_CONSUMED" and slot["failure_detail_available"]
    assert "private detail" not in json.dumps(report)
    assert set(losses.loc[losses.comparator.eq("median_hgb"), "year"]) == {2022, 2024}


def test_binary_infinite_log_losses_retained_and_json_explicit_not_clipped():
    report, losses = reporting.build_reports(fictional("anytime_td", infinite_binary=True), categories())
    summary = next(v for v in report["targets"]["anytime_td"]["summaries"] if v["method"] == "leaf_cdf" and v["population"] == "all_offered" and v["period"] == "pooled2022-2024")
    assert summary["log_loss_state"] == "positive_infinity" and summary["infinite_log_losses"] == 18
    proper = comparison(report, "anytime_td", "leaf_cdf", "role_prior", distribution=True, metric="log_score")
    assert proper["infinite_candidate_losses"] == 18 and proper["loss_state"] == "nonfinite_or_undefined_log_loss"
    assert proper["candidate_loss"] == {"state": "positive_infinity"}
    assert all(i["state"] == "N/A" and i["reason"] == "nonfinite_or_undefined_paired_log_loss_delta" for i in proper["intervals"])
    assert np.isposinf(losses.loc[losses.metric.eq("log_score"), "candidate_loss"]).sum() == 18
    json.dumps(report, allow_nan=False)


def test_bootstrap_exact_registered_generator_cluster_keys_and_reproducibility():
    losses = pd.DataFrame({"season": [2022] * 36, "week": np.repeat(np.arange(1, 9), np.arange(1, 9)),
        "game_id": np.repeat([f"fictional-g{i}" for i in range(8)], np.arange(1, 9)),
        "delta_candidate_minus_control": np.repeat([-7., -3., -1., 0., 1., 2., 4., 8.], np.arange(1, 9))})
    state = np.random.get_state()
    a = reporting._bootstrap(losses, np.ones(36, dtype=bool), "week", 500, 1703)
    b = reporting._bootstrap(losses, np.ones(36, dtype=bool), "game", 500, 1703)
    assert a["interval"] == b["interval"]
    assert a["generator"] == "PCG64" and a["seed"] == 1703 and a["percentile_method"] == "linear"
    assert a["clusters"] == 8 and a["paired_rows"] == 36 and a["state"] == "DESCRIPTIVE"
    assert reporting._bootstrap(losses, np.ones(36, dtype=bool), "week", 500, 1703) == a
    for old, new in zip(state, np.random.get_state()):
        if isinstance(old, np.ndarray):
            np.testing.assert_array_equal(old, new)
        else:
            assert old == new
    small = reporting._bootstrap(losses.iloc[:6], np.ones(6, dtype=bool), "week", 500, 1703)
    assert small["state"] == "N/A" and small["reason"] == "fewer_than_8_clusters"


def test_unknown_dnp_and_played_missing_rows_remain_in_coverage_and_private_losses():
    frame = fictional()
    for week, state, outcome in [(1, "unknown", "unknown"), (2, "DNP", "DNP"), (3, "played", "played_missing_statistic")]:
        selected = frame.week.eq(week)
        frame.loc[selected, "actual"] = np.nan
        frame.loc[selected, "participation_state"] = state
        frame.loc[selected, "outcome_state"] = outcome
    report, losses = reporting.build_reports(frame, categories())
    cell = comparison(report, "pass_att", "leaf_cdf", "median_hgb")
    assert cell["offered_rows"] == 36 and cell["paired_rows"] == 27
    assert len(losses) == 36 * 13
    assert not losses.loc[losses.week.isin([1, 2, 3]), "paired_eligible"].any()


def test_target_local_reports_equal_full_wrapper_with_completed_sibling_statuses():
    frame = pd.concat([fictional(year_counts=(8, 8, 8)), fictional("anytime_td", year_counts=(8, 8, 8))], ignore_index=True)
    contract = categories()
    for target in ("pass_att", "anytime_td"):
        contract[target]["benchmark_slots"] = [{"year": year, "method": method, "state": "COMPLETED"}
            for year in reporting.YEARS for method in reporting.METHODS]
    full, losses = reporting.build_reports(frame, contract)
    header = reporting.reporting_header()
    for target in ("pass_att", "anytime_td"):
        item, local = reporting.build_target_report(frame.loc[frame.target.eq(target)], contract, target=target)
        assert item == full["targets"][target]
        expected = losses.loc[losses.target.eq(target)].reset_index(drop=True)
        pd.testing.assert_frame_equal(local.reset_index(drop=True), expected, check_categorical=False)
        header["targets"][target] = item
    assert {key: value for key, value in header.items() if key != "targets"} == {key: value for key, value in full.items() if key != "targets"}
    assert contract["pass_att"]["benchmark_slots"][0]["state"] == "COMPLETED"
    blocked, empty = reporting.build_target_report(frame.iloc[:0], contract, target="fantasy_ppr")
    assert len(blocked["slots"]) == 18 and blocked["state"] == "BLOCKED_EXACT_PPR" and empty.empty
    with pytest.raises(ValueError, match="named target"):
        reporting.build_target_report(frame, contract, target="pass_att")


@pytest.mark.parametrize("field,value", [("variance", -1.), ("crps", -1.), ("p10", .5), ("cdf_actual", 2.)])
def test_invalid_cdf_score_support_rejected(field, value):
    frame = fictional()
    frame.loc[frame.method.eq("leaf_cdf"), field] = value
    with pytest.raises(ValueError):
        reporting.build_reports(frame, categories())


@pytest.mark.parametrize("mutation", [
    lambda f: f.loc[f.index[0], "cutoff_utc"] - pd.Timedelta(minutes=1),
])
def test_context_cutoff_mismatch_rejected(mutation):
    frame = fictional()
    frame.loc[frame.index[0], "cutoff_utc"] = mutation(frame)
    with pytest.raises(ValueError, match="context/cutoff"):
        reporting.build_reports(frame, categories())


@pytest.mark.parametrize("change", [
    lambda f: f.__setitem__("target", "fantasy_ppr"),
    lambda f: f.__setitem__("year", 2026),
    lambda f: f.__setitem__("primary_role", True),
    lambda f: f.__setitem__("point", "not numeric"),
    lambda f: f.loc.__setitem__((f.index[1], "actual"), 99.),
])
def test_bad_schema_roles_ppr_and_outcome_mismatches_rejected(change):
    frame = fictional()
    change(frame)
    with pytest.raises(ValueError):
        reporting.build_reports(frame, categories())


@pytest.mark.parametrize("kwargs", [{"replicates": 1}, {"seed": 1701}, {"replicates": True}])
def test_unregistered_resampling_arguments_rejected(kwargs):
    with pytest.raises(ValueError):
        reporting.build_reports(fictional(), categories(), **kwargs)
