"""Fictional threshold arithmetic only; no NFL fitting, prediction or scoring."""
import numpy as np
import pandas as pd
import pytest

import nfl_lab.recorded_thresholds as thresholds


def fixture(n=5, target="rush_yd"):
    return pd.DataFrame({"season": 2026, "week": 6, "game_id": [f"fictional-g{i}" for i in range(n)],
        "player_id": [f"fictional-p{i}" for i in range(n)], "target": target, "line": np.ones(n), "line_from": "dk",
        "actual": np.ones(n), "participation_state": "played", "quarantined": False,
        "site": np.ones(n), "candidate": np.ones(n), "source_coverage": "both"})


def entry(result, target="rush_yd", method="candidate"):
    return next(x for x in result["summary"]["method_target_summaries"] if x["target"] == target and x["method"] == method)


def test_three_way_ties_pushes_fractional_thresholds_signed_yards_and_fixed_tails():
    f = fixture()
    f["line"], f["candidate"], f["actual"] = [1.5, 1, 0, -2.5, 2], [2, 1, 0, -3, 2], [2, 1, 1, -3, 0]
    original = f.copy(deep=True)
    result = thresholds.evaluate_recorded_thresholds(f, {"website": "site", "candidate": "candidate"})
    s = entry(result)
    assert s["scored_rows"] == 5 and s["three_way_accuracy"] == .6 and s["three_way_misclassification_rate"] == .4
    assert s["actual_equal_threshold_rows"] == 1 and s["actual_equal_threshold_rate"] == .2
    assert s["prediction_equal_threshold_rows"] == 3 and s["nonpush_secondary_rows"] == 4
    assert s["nonpush_secondary_accuracy"] == .5 and s["nonpush_prediction_equal_rows"] == 2
    assert s["point_mae"] == .6 and s["point_rmse"] == 1 and s["point_bias_prediction_minus_actual"] == .2
    assert s["point_absolute_error_p90"] == pytest.approx(1.6) and s["point_absolute_error_p95"] == pytest.approx(1.8)
    assert s["point_absolute_error_max"] == 2
    pd.testing.assert_frame_equal(f, original)
    rows = result["rows"].loc[result["rows"].method.eq("candidate")]
    assert rows.point_direction.tolist() == ["over", "equal", "equal", "under", "equal"]
    assert rows.actual_direction.tolist() == ["over", "equal", "over", "under", "under"]


def test_freeze_ignores_all_labels_and_keeps_per_method_clocks_and_literal_float():
    f = fixture(2)
    class LabelPoison:
        def __float__(self):
            raise AssertionError("freeze read an outcome")
    f["actual"], f["participation_state"], f["quarantined"] = [LabelPoison(), LabelPoison()], "poison", "poison"
    f["line"] = [1.0000000000001, 1.]
    f["candidate"] = [1., 1.]
    f["cutoff_utc"], f["kickoff_utc"] = "2026-10-18T10:00:00Z", "2026-10-18T17:00:00Z"
    f["line_recorded_at_utc"] = "2026-10-18T09:00:00Z"
    f["site_clock"], f["candidate_clock"] = "2026-10-18T09:00:00Z", "2026-10-23T04:00:00Z"
    metadata = {"website": {"forecast_recorded_at_utc": "site_clock"}, "candidate": {"forecast_recorded_at_utc": "candidate_clock"}}
    frozen = thresholds.freeze_recorded_directions(f, {"website": "site", "candidate": "candidate"}, method_metadata=metadata)
    assert not {"actual", "participation_state", "quarantined", "actual_direction"} & set(frozen)
    candidate = frozen.loc[frozen.method.eq("candidate")]
    site = frozen.loc[frozen.method.eq("website")]
    assert candidate.point_direction.tolist() == ["under", "equal"]  # no epsilon or rounding
    assert candidate.line.iloc[0] == 1.0000000000001
    assert site.forecast_clock_vs_kickoff.eq("before").all() and candidate.forecast_clock_vs_kickoff.eq("after").all()
    assert candidate.line_clock_vs_cutoff.eq("before").all()


def test_strict_reference_whitelist_retains_ours_nonexistent_and_bad_lines_without_throwing():
    f = fixture(8, "pass_att")
    f["line_from"] = ["dk", "sleeper", "ours", "DK", None, "other", "dk", "dk"]
    f["line"] = [2.5, "2.5", 2.5, 2.5, 2.5, 2.5, np.inf, True]
    f["candidate"], f["actual"] = 3.25, 3
    result = thresholds.evaluate_recorded_thresholds(f, {"candidate": "candidate"}, reference_method=None)
    assert len(result["rows"]) == len(f)
    assert entry(result, "pass_att")["scored_rows"] == 2
    assert result["rows"].threshold_class.tolist() == ["reference", "reference", "ours", "nonexistent", "nonexistent", "nonexistent", "nonexistent", "nonexistent"]
    assert result["rows"].line_from.iloc[3] == "DK"
    assert result["rows"].point.iloc[0] == 3.25


def test_count_actual_support_quarantine_missing_and_participation_fail_closed():
    f = fixture(9, "rush_att")
    f["actual"] = [0, -1, 1.5, np.nan, 2, 2, 2, "2", True]
    f["participation_state"] = ["played", "played", "played", "played", "DNP", "unknown", "played", "played", "played"]
    f["quarantined"] = [False, False, False, False, False, False, True, None, False]
    result = thresholds.evaluate_recorded_thresholds(f, {"candidate": "candidate"})
    assert result["rows"].eligible.tolist() == [True, False, False, False, False, False, False, False, False]
    assert result["rows"].eligibility_state.iloc[6] == "quarantined" and result["rows"].eligibility_state.iloc[7] == "quarantine_unknown"
    assert result["rows"].point_direction.eq("equal").all()  # frozen point direction stays intact
    absent = thresholds.evaluate_recorded_thresholds(f.drop(columns="quarantined"), {"candidate": "candidate"})
    assert not absent["rows"].eligible.any() and absent["rows"].quarantine_state.eq("unknown").all()
    bad = thresholds.evaluate_recorded_thresholds(f.iloc[[0]].assign(candidate=-.1), {"candidate": "candidate"})
    assert bad["rows"].eligibility_state.iloc[0] == "invalid_count_point"


def test_common_controls_use_exact_target_rows_without_optional_method_shrinking_other_cohorts():
    f = pd.concat([fixture(2, "pass_att"), fixture(2, "rec_yd")], ignore_index=True)
    f["actual"], f["site"], f["candidate"] = [0, 10, 0, 10], [1, 2, 1, 2], [2, 3, 2, 3]
    f["raw"], f["recent"], f["pooled"], f["optional"] = [1, np.nan, 1, 9], [1, 9, 1, 9], [2, 8, 2, 8], [1, 9, 1, 9]
    methods = {"website": "site", "candidate": "candidate", "raw": "raw", "recent": "recent", "pooled": "pooled", "692": "optional"}
    result = thresholds.evaluate_recorded_thresholds(f, methods, common_controls=["raw", "website", "recent", "pooled"], supported_targets={"692": ["pass_att"]})
    comparisons = result["summary"]["comparisons"]
    common = next(x for x in comparisons if x["target"] == "pass_att" and x["candidate"] == "candidate" and x["cohort"] == "declared_common_controls")
    assert common["common_rows"] == 1 and all(x["scored_rows"] == 1 and x["offered_rows"] == 2 for x in common["methods"].values())
    assert common["methods"]["candidate"]["point_mae"] == 2 and common["methods"]["website"]["point_mae"] == 1
    pair = next(x for x in comparisons if x["target"] == "pass_att" and x["candidate"] == "candidate" and x["cohort"] == "pairwise_literal_site")
    assert pair["common_rows"] == 2 and pair["methods"]["candidate"]["point_mae"] == 4.5
    other = next(x for x in comparisons if x["target"] == "rec_yd" and x["candidate"] == "candidate" and x["cohort"] == "declared_common_controls")
    blocked = next(x for x in comparisons if x["target"] == "rec_yd" and x["candidate"] == "692" and x["cohort"] == "declared_common_controls")
    assert other["common_rows"] == 2 and blocked["common_rows"] == 0


def test_full13_method_all12_matrix_keeps_binary_ppr_and_six_optional_unsupported_slots():
    f = pd.concat([fixture(1, target) for target in thresholds.SUPPORT], ignore_index=True)
    names = ["website", "raw", "recent", "pooled", "cdf_base", "cdf_context", "hgb_base", "hgb_context",
        "cdf_blend_base", "cdf_blend_context", "hgb_blend_base", "hgb_blend_context", "692"]
    methods = {name: "point_" + name for name in names}
    for column in methods.values():
        f[column] = 2.
    supported = {"692": [t for t, support in thresholds.SUPPORT.items() if support == "count"]}
    result = thresholds.evaluate_recorded_thresholds(f, methods, common_controls=["raw", "website", "recent", "pooled"], supported_targets=supported)
    assert len(result["rows"]) == 156 and len(result["summary"]["method_target_summaries"]) == 156
    common = [x for x in result["summary"]["comparisons"] if x["cohort"] == "declared_common_controls"]
    assert len(common) == 144 and sum(x["target"] in ["anytime_td", "fantasy_ppr"] for x in common) == 24
    assert sum(x["method"] == "692" and x["direction_state"] == "method_not_supported_target" for _, x in result["rows"].iterrows()) == 6
    assert not result["rows"].loc[result["rows"].target.isin(["anytime_td", "fantasy_ppr"]), "eligible"].any()
    assert result["summary"]["probabilities_produced"] is False and result["summary"]["bootstrap_replicates"] == 0


@pytest.mark.parametrize("changed", ["identity", "point", "line", "line_from", "method"])
def test_cached_frozen_directions_are_reused_once_and_tampered_binding_rejected(changed, monkeypatch):
    f = fixture(2)
    methods = {"website": "site", "candidate": "candidate"}
    frozen = thresholds.freeze_recorded_directions(f, methods)
    def forbidden(*args, **kwargs):
        raise AssertionError("second conversion attempted")
    monkeypatch.setattr(thresholds, "freeze_recorded_directions", forbidden)
    scored = thresholds.evaluate_recorded_thresholds(f, methods, frozen_directions=frozen)
    assert scored["summary"]["direction_conversion_passes_in_this_call"] == 0
    assert scored["rows"].point_direction.tolist() == frozen.point_direction.tolist()
    bad = frozen.copy()
    column, value = {"identity": ("player_id", "wrong"), "point": ("point", 2.), "line": ("line", 2.),
                     "line_from": ("line_from", "sleeper"), "method": ("method", "wrong")}[changed]
    bad.loc[0, column] = value
    with pytest.raises(ValueError, match="frozen"):
        thresholds.evaluate_recorded_thresholds(f, methods, frozen_directions=bad)


def test_duplicate_snapshots_label_columns_and_financial_metadata_are_rejected_or_ignored():
    f = fixture(1)
    duplicate = pd.concat([f, f.assign(line_recorded_at_utc="different snapshot")], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        thresholds.freeze_recorded_directions(duplicate, {"candidate": "candidate"})
    with pytest.raises(ValueError, match="saved point columns"):
        thresholds.freeze_recorded_directions(f, {"cheat": "actual"})
    with pytest.raises(ValueError, match="label or financial"):
        thresholds.freeze_recorded_directions(f, {"candidate": "candidate"}, method_metadata={"candidate": {"forecast_recorded_at_utc": "actual"}})
    f["odds"], f["price"], f["payout"] = "poison", "poison", "poison"
    result = thresholds.evaluate_recorded_thresholds(f, {"candidate": "candidate", "missing": "absent_column"})
    assert not {"odds", "price", "payout"} & set(result["rows"])
    assert result["rows"].loc[result["rows"].method.eq("missing"), "eligibility_state"].iloc[0] == "missing_or_nonfinite_point"
    assert result["rows"].forecast_clock_vs_kickoff.eq("unknown").all() and result["rows"].line_clock_vs_cutoff.eq("unknown").all()


def test_public_saved_row_summary_reuses_same_metric_implementation_for_declared_group_slice():
    f = fixture(3)
    f["candidate"], f["actual"] = [1, 2, 3], [1, 1, 2]
    result = thresholds.evaluate_recorded_thresholds(f, {"candidate": "candidate"})
    rows = result["rows"]
    direct = thresholds.summarize_recorded_rows(rows)
    assert direct["point_mae"] == entry(result)["point_mae"] and direct["point_absolute_error_p95"] == entry(result)["point_absolute_error_p95"]
    subset = thresholds.summarize_recorded_rows(rows.iloc[:2])
    assert subset["offered_rows"] == 2 and subset["scored_rows"] == 2 and subset["point_mae"] == .5
    invalid = rows.copy()
    invalid.loc[0, "actual"] = .5
    with pytest.raises(ValueError, match="support/direction"):
        thresholds.summarize_recorded_rows(invalid)
