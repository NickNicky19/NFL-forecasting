import numpy as np
import pandas as pd
import pytest

from nfl_lab.coherence_audit import audit_method, paired_week_deltas


def fixture():
    frames = []
    for target, actual, mean in (("rush_rec_yd", 30., 50.), ("rush_yd", 10., 8.), ("rec_yd", 20., 20.)):
        frames.append(pd.DataFrame({"season": [2024] * 9, "week": range(1, 10),
            "game_id": [f"game-{week}" for week in range(1, 10)], "player_id": ["synthetic"] * 9,
            "target": target, "method": "recent", "actual": actual, "mean": mean,
            "participation_state": "played", "p_participation": .8, "team": "A", "opponent": "B",
            "kickoff_utc": pd.Timestamp("2024-01-01T00:00:00Z")}))
    return frames


def test_no_fit_paired_metrics_and_reproducible_week_intervals():
    frames = fixture()
    report = audit_method(*frames, method="recent")
    assert report["paired_scored_rows"] == 9
    assert report["paired_direct_metrics"]["mae"] == 20
    assert report["paired_component_sum_metrics"]["mae"] == 2
    assert report["paired_component_sum_metrics"]["bias"] == -2
    assert report["mean_coherence"]["discrepancies_gt_1_yard"] == 9
    assert report["paired_week_uncertainty"]["intervals"]["mae"] == [-18., -18.]
    assert report["paired_unique_games"] == 9
    assert report["paired_game_uncertainty"]["cluster_unit"] == "game"
    assert report["paired_game_uncertainty"]["intervals"]["mae"] == [-18., -18.]
    assert report == audit_method(*frames, method="recent")


def test_missing_outcomes_and_incompatible_participation_are_not_zero_or_scored():
    direct, rush, rec = fixture()
    rush.loc[0, "actual"] = np.nan
    rec.loc[1, "p_participation"] = .2
    rec.loc[2, "participation_state"] = "unknown"
    rush.loc[3, "mean"] = np.nan
    direct.loc[4, "actual"] = 31
    report = audit_method(direct, rush, rec, method="recent")
    assert report["missing_source_component_outcomes"] == 1
    assert report["participation_probability_incompatible_or_missing_rows"] == 1
    assert report["participation_state_incompatible_rows"] == 1
    assert report["combined_outcome_component_mismatches"] == 1
    assert report["component_missing_forecasts"] == 1
    assert report["paired_scored_rows"] == 4
    assert report["paired_week_uncertainty"]["intervals"] is None
    assert report["direct_natural_coverage_metrics"]["n"] == 9


def test_unmatched_rows_retained_duplicate_or_wrong_method_rejected():
    direct, rush, rec = fixture()
    report = audit_method(direct, rush.iloc[1:], rec, method="recent")
    assert report["population_rows_union"] == 9
    assert report["unmatched_rows"] == 1
    assert report["paired_scored_rows"] == 8
    with pytest.raises(ValueError, match="duplicate"):
        audit_method(pd.concat([direct, direct]), rush, rec, method="recent")
    with pytest.raises(ValueError, match="wrong_frozen"):
        audit_method(direct, rush, rec, method="pooled")


def test_all_missing_forecasts_report_coverage_instead_of_metrics():
    frames = fixture()
    for frame in frames:
        frame["mean"] = np.nan
    report = audit_method(*frames, method="recent")
    assert report["paired_scored_rows"] == 0
    assert report["paired_direct_metrics"]["mae"] is None
    assert report["paired_week_uncertainty"]["reason"] == "no_supported_paired_rows"


def test_unequal_week_sizes_use_player_row_weighting_and_budget_guard():
    rows = pd.DataFrame({"season": [2024] * 9, "week": [1] * 8 + [2],
                         "actual": 0., "direct_mean": 0., "component_mean": [1.] * 8 + [10.]})
    assert paired_week_deltas(rows)["deltas"]["mae"] == 2
    with pytest.raises(ValueError, match="budget"):
        paired_week_deltas(rows, replicates=501)
