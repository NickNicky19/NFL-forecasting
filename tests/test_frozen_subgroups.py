"""Only fictional already-scored inputs; no NFL data or model execution."""
import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab import frozen_subgroups as groups
from nfl_lab.cdf_evaluation import summarize as cdf_summary
from nfl_lab.role_boosting_campaign import summary as point_summary


def category(target="pass_yd"):
    return {"target": target, "state": "READY", "support": "bernoulli" if target == "anytime_td" else "count" if target == "pass_att" else "signed_integer", "primary_roles": ["QB"]}


def fictional(target="pass_yd", method="leaf_cdf"):
    result = []
    for year in groups.YEARS:
        for week in range(1, 7):
            actual = [-2., 0., 4., np.nan, np.nan, np.nan][week - 1]
            if target == "anytime_td":
                actual = [1., 0., 1., np.nan, np.nan, np.nan][week - 1]
            if target == "pass_att" and week == 1:
                actual = 2.
            state = "unknown" if week == 5 else "DNP" if week == 6 else "played"
            outcome = state if state != "played" else "played_missing_statistic" if week == 4 else "played_zero" if actual == 0 else "played_nonzero"
            binary = target == "anytime_td"
            point = (0. if week == 1 else .8) if binary else float(week)
            law = method == "leaf_cdf"
            kickoff = pd.Timestamp(f"{year}-09-01", tz="UTC") + pd.Timedelta(days=week * 7)
            with np.errstate(divide="ignore"):
                log = -np.log(point if actual == 1 else 1 - point) if binary and np.isfinite(actual) else .5 if np.isfinite(actual) else np.nan
            below = 1 - point if actual == 1 else 0.
            at = 1. if actual == 1 else 1 - point
            result.append({"season": year, "year": year, "week": week, "game_id": f"fictional-game-{year}-{week}",
                "player_id": f"PRIVATE-FICTIONAL-PLAYER-{week % 3}", "target": target, "method": method,
                "point": point, "probability": point if binary else np.nan,
                "mean": point if law else np.nan, "median": float(point > .5) if law and binary else point if law else np.nan,
                "actual": actual, "participation_state": state, "outcome_state": outcome,
                "primary_role": week <= 3, "position": "QB" if week <= 3 else "RB",
                "team": "FIC" if week % 2 else "TST", "opponent": "TST" if week % 2 else "FIC",
                "fallback": "" if week <= 3 else "cold_start", "history_state": "warm" if week <= 3 else "cold_or_unknown",
                "kickoff_utc": kickoff, "cutoff_utc": kickoff - pd.Timedelta(hours=1),
                "p10": (0. if binary else -3.) if law else np.nan, "p90": (1. if binary else 8.) if law else np.nan,
                "variance": (point * (1 - point) if binary else 2.) if law else np.nan,
                "crps": (point - actual) ** 2 if law and binary else .4 if law and np.isfinite(actual) else np.nan,
                "log_score": log if law else np.nan,
                "cdf_actual_below": (below if binary else .2) if law and np.isfinite(actual) else np.nan,
                "cdf_actual": (at if binary else .7) if law and np.isfinite(actual) else np.nan})
    return pd.DataFrame(result)


def test_exact_evaluator_reuse_privacy_sparse_groups_and_input_immutability():
    rows = fictional()
    before = rows.copy(deep=True)
    public, private = groups.build_frozen_subgroups(rows, category())
    assert public["included_years"] == [2022, 2023, 2024]
    assert public["absent_years"] == [] and public["unit"] == "yards"
    for population, frame in [("all_offered", rows), ("primary_roles", rows.loc[rows.primary_role])]:
        cell = public["populations"][population]
        expected = point_summary(frame, category())
        assert all(cell["summary"][key] == value for key, value in expected.items())
        assert cell["summary"]["cdf_law"] == cdf_summary(frame, "signed_integer")
        assert {v["dimension"] for v in cell["groups"]} == set(groups.DIMENSIONS[1:])
        assert {v["dimension"] for v in private["populations"][population]["groups"]} == {"player_id"}
        assert cell["player_group_coverage"]["offered_player_groups"] == 3
        assert cell["player_group_coverage"]["scored_player_groups"] == 3
        for dimension in groups.DIMENSIONS[1:]:
            assert sum(g["summary"]["offered_rows"] for g in cell["groups"] if g["dimension"] == dimension) == len(frame)
    text = json.dumps(public, allow_nan=False)
    assert "PRIVATE-FICTIONAL-PLAYER" not in text and "fictional-game" not in text
    assert "PRIVATE-FICTIONAL-PLAYER" in json.dumps(private, allow_nan=False)
    assert not any(key in text for key in ('"interval":', '"rank":', '"contrast":'))
    pd.testing.assert_frame_equal(rows, before, check_exact=True)


def test_supported_zeros_signed_values_unknown_dnp_missing_and_no_group_selection():
    public, private = groups.build_frozen_subgroups(fictional(), category())
    all_rows = public["populations"]["all_offered"]["summary"]
    assert all_rows["offered_rows"] == 18 and all_rows["scored_rows"] == 9
    assert all_rows["supported_played_zero_rows"] == 3
    assert all_rows["supported_played_negative_rows"] == 3
    assert all_rows["played_missing_actual_rows"] == 3
    assert all_rows["unknown_participation_rows"] == 3 and all_rows["known_DNP_rows"] == 3
    assert all_rows["missing_actual_rows"] == 9 and all_rows["fallback_rows"] == 9
    assert all_rows["offered_season_weeks"] == 18 and all_rows["weeks"] == 9
    assert any(g["summary"]["scored_rows"] == 0 for g in public["populations"]["all_offered"]["groups"])
    assert private["privacy"] == "PRIVATE_PLAYER_GROUPS_DO_NOT_PUBLISH"


def test_binary_boundary_infinities_are_explicit_and_not_clipped():
    public, private = groups.build_frozen_subgroups(fictional("anytime_td"), category("anytime_td"))
    summary = public["populations"]["all_offered"]["summary"]
    assert public["unit"] == "probability"
    assert summary["log_loss_state"] == "positive_infinity" and summary["infinite_log_losses"] == 3
    assert summary["probability_clipping"] == "none"
    assert summary["cdf_law"]["distribution"]["infinite_log_losses"] == 3
    assert summary["cdf_law"]["mean"]["log_loss_status"] == "infinite"
    json.dumps(public, allow_nan=False)
    json.dumps(private, allow_nan=False)


def test_point_only_methods_do_not_acquire_distributions_or_mean_claims():
    for method in groups.METHODS[1:]:
        rows = fictional(method=method)
        rows.loc[rows.week.eq(1), "point"] = np.nan
        public, _ = groups.build_frozen_subgroups(rows, category())
        summary = public["populations"]["all_offered"]["summary"]
        assert "cdf_law" not in summary and "mean" not in summary
        assert summary["missing_points"] == 3 and summary["scored_rows"] == 6


def test_missing_group_values_and_partial_years_remain_explicit():
    rows = fictional().loc[lambda f: f.season.ne(2023)].copy()
    rows.loc[rows.week.eq(1), "team"] = None
    rows.loc[rows.week.eq(2), "history_state"] = None
    public, _ = groups.build_frozen_subgroups(rows, category())
    assert public["included_years"] == [2022, 2024] and public["absent_years"] == [2023]
    missing = [g for g in public["populations"]["all_offered"]["groups"] if g["missing_group_value"]]
    assert {g["dimension"] for g in missing} == {"team", "history_state"}
    assert all(g["value"] is None and g["summary"]["offered_rows"] == 2 for g in missing)
    json.dumps(public, allow_nan=False)


def test_empty_primary_population_and_unscored_player_coverage():
    rows = fictional(method="recent")
    rows["position"], rows["primary_role"] = "RB", False
    rows.loc[rows.player_id.eq("PRIVATE-FICTIONAL-PLAYER-1"), "point"] = np.nan
    public, private = groups.build_frozen_subgroups(rows, category())
    coverage = public["populations"]["all_offered"]["player_group_coverage"]
    assert coverage["unscored_player_groups"] == 1 and coverage["scored_player_groups"] == 2
    primary = public["populations"]["primary_roles"]
    assert primary["summary"]["offered_rows"] == 0 and primary["groups"] == []
    assert private["populations"]["primary_roles"]["groups"] == []


@pytest.mark.parametrize("field,value", [
    ("season", 2025), ("season", 2021), ("year", 2023), ("week", 19),
    ("target", "fantasy_ppr"), ("method", "role_prior"), ("primary_role", False),
    ("participation_state", "unread"), ("cutoff_utc", "2030-01-01T00:00:00Z"),
    ("kickoff_utc", None), ("point", np.inf), ("probability", .4),
    ("log_score", -np.inf), ("cdf_actual", 1.2), ("variance", -1.),
    ("median", 1.5), ("team", 123), ("season_type", "POST")])
def test_rejects_changed_binding_roles_exposed_years_and_invalid_scores(field, value):
    rows = fictional()
    if field == "cutoff_utc":
        rows[field] = rows[field].astype(object)
    rows.loc[0, field] = value
    with pytest.raises((ValueError, TypeError)):
        groups.build_frozen_subgroups(rows, category())


def test_duplicate_null_keys_mixed_cells_missing_fields_and_blocked_category_rejected():
    rows = fictional()
    bad = [pd.concat([rows, rows.iloc[:1]]), rows.drop(columns="cutoff_utc"), rows.iloc[:0]]
    null_key = rows.copy()
    null_key.loc[0, "player_id"] = None
    mixed = rows.copy()
    mixed.loc[0, "method"] = "pooled"
    bad.extend([null_key, mixed])
    for frame in bad:
        with pytest.raises(ValueError):
            groups.build_frozen_subgroups(frame, category())
    for contract in [dict(category(), target="fantasy_ppr"), dict(category(), state="BLOCKED"), dict(category(), support="count")]:
        with pytest.raises(ValueError):
            groups.build_frozen_subgroups(rows, contract)


def test_genuine_binary_boundary_and_probability_identity_guards():
    for field, value in [("point", 1.01), ("probability", .1)]:
        rows = fictional("anytime_td")
        rows.loc[0, field] = value
        with pytest.raises(ValueError):
            groups.build_frozen_subgroups(rows, category("anytime_td"))


def test_no_io_or_predictions_and_cdf_helper_called_only_for_cdf(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden IO or non-CDF distribution evaluation")
    monkeypatch.setattr(pd, "read_parquet", forbidden)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", forbidden)
    monkeypatch.setattr(groups, "cdf_summary", forbidden)
    public, _ = groups.build_frozen_subgroups(fictional(method="median_hgb"), category())
    assert public["method"] == "median_hgb"


def test_invalid_count_support_stays_unscored_and_unknown_zero_is_not_played_zero():
    rows = fictional("pass_att", method="count_A")
    rows.loc[rows.week.eq(1), "actual"] = -2.
    rows.loc[rows.week.eq(1), "outcome_state"] = "played_invalid_support"
    rows.loc[rows.week.eq(5), "actual"] = 0.
    public, _ = groups.build_frozen_subgroups(rows, category("pass_att"))
    summary = public["populations"]["all_offered"]["summary"]
    assert public["unit"] == "events"
    assert summary["scored_rows"] == 6 and summary["played_invalid_support_rows"] == 3
    assert summary["supported_played_negative_rows"] == 0
    assert summary["supported_played_zero_rows"] == 3


def test_pooled_metrics_use_rows_not_annual_averages_and_cache_matches_evaluator(monkeypatch):
    rows = fictional(method="recent")
    rows = rows.loc[~(rows.season.eq(2023) & rows.week.gt(1))].copy()
    for year, error in [(2022, 1.), (2023, 10.), (2024, 3.)]:
        mask = rows.season.eq(year) & rows.participation_state.eq("played") & rows.actual.notna()
        rows.loc[mask, "point"] = rows.loc[mask, "actual"] + error
    public, private = groups.build_frozen_subgroups(rows, category())
    assert public["populations"]["all_offered"]["summary"]["point_metrics"]["mae"] == pytest.approx(22 / 7)
    assert public["populations"]["all_offered"]["summary"]["point_metrics"]["mae"] != pytest.approx(14 / 3)
    for population, part in [("all_offered", rows), ("primary_roles", rows.loc[rows.primary_role])]:
        for item in private["populations"][population]["groups"]:
            expected = point_summary(part.loc[part.player_id.eq(item["value"])], category())
            assert all(item["summary"][key] == value for key, value in expected.items())
    original = groups.point_summary
    calls = []
    def spy(part, contract):
        calls.append(tuple(part.index))
        return original(part, contract)
    monkeypatch.setattr(groups, "point_summary", spy)
    primary_only = rows.loc[rows.primary_role]
    groups.build_frozen_subgroups(primary_only, category())
    # Aggregate summaries are separate; each fixed group is evaluated once.
    expected_groups = sum(primary_only[field].nunique(dropna=False) for field in groups.DIMENSIONS)
    assert len(calls) == 2 + expected_groups
