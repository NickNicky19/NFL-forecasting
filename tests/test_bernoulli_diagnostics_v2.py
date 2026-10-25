"""Fictional frozen Bernoulli rows only; no source, learner or law execution."""
import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab import bernoulli_diagnostics_v2 as adapter
from nfl_lab import source_matched_reporting as reporting
from nfl_lab.models import COUNT_TARGETS, TARGETS
from nfl_lab.role_boosting_campaign import summary


def categories():
    return {target: {"target": target, "state": "BLOCKED" if target == "fantasy_ppr" else "READY",
        "support": "bernoulli" if target == "anytime_td" else "count" if target in COUNT_TARGETS else "signed_integer",
        "primary_roles": ["QB"]} for target in TARGETS}


def fictional(method="leaf_cdf"):
    probabilities = [0., 0., 1., 1., .2, .8, .5, .1, .9, np.nan]
    actuals = [0., 1., 0., 1., 0., 1., 1., np.nan, 0., 1.]
    records = []
    for i, (p, y) in enumerate(zip(probabilities, actuals)):
        played = i != 8
        valid = played and np.isfinite(y) and np.isfinite(p)
        with np.errstate(divide="ignore", invalid="ignore"):
            log = -(np.log(p) if y == 1 else np.log1p(-p)) if valid else np.nan
        kickoff = pd.Timestamp("2023-10-01", tz="UTC") + pd.Timedelta(days=i * 7)
        records.append({"season": 2023, "year": 2023, "week": i + 1, "game_id": f"PRIVATE-game-{i}", "player_id": f"PRIVATE-player-{i}",
            "target": "anytime_td", "method": method, "point": p, "probability": p, "mean": p,
            "median": (0. if p <= .5 else 1.) if np.isfinite(p) else np.nan,
            "p10": (0. if p <= .9 else 1.) if np.isfinite(p) else np.nan,
            "p90": (0. if p <= .1 else 1.) if np.isfinite(p) else np.nan,
            "variance": p * (1 - p), "actual": y, "participation_state": "played" if played else "unknown",
            "outcome_state": "unknown" if not played else "played_missing_statistic" if not np.isfinite(y) else "played_zero" if y == 0 else "played_nonzero",
            "primary_role": i % 2 == 0, "position": "QB" if i % 2 == 0 else "RB", "team": "FIC", "opponent": "TST",
            "kickoff_utc": kickoff, "cutoff_utc": kickoff - pd.Timedelta(hours=1), "fallback": "", "history_state": "warm",
            "cdf_actual_below": (0. if y == 0 else 1 - p) if valid else np.nan,
            "cdf_actual": (1 - p if y == 0 else 1.) if valid else np.nan,
            "crps": (p - y)**2 if valid else np.nan, "log_score": log, "brier": (p - y)**2 if valid else np.nan})
    frame = pd.DataFrame(records, index=pd.Index(range(10, 20), name="frozen_order"))
    # The known failure is an endpoint outside [0,1], never a changed p.
    frame.loc[15, "cdf_actual"] = np.nextafter(1., np.inf)
    frame.loc[14, "crps"] = np.nextafter(frame.loc[14, "crps"], np.inf)
    frame.loc[15, "log_score"] = np.nextafter(frame.loc[15, "log_score"], np.inf)
    return frame


@pytest.mark.parametrize("method", adapter.METHODS)
def test_closed_form_strict_validator_acceptance_original_failure_and_all_bits_preserved(method):
    raw = fictional(method)
    before = raw.copy(deep=True)
    # Deliberate NaN payload and signed zero outside the four mutable columns.
    raw.loc[17, "variance"] = np.array([0x7ff8000000000042], dtype=np.uint64).view(np.float64)[0]
    raw.loc[10, "brier"] = -0.
    before = raw.copy(deep=True)
    with pytest.raises(ValueError, match="CDF bracket"):
        reporting._validate(raw, categories(), 500, 1703)
    derivative, receipt = adapter.canonical_bernoulli_diagnostics(raw)
    reporting._validate(derivative, categories(), 500, 1703)
    pd.testing.assert_frame_equal(raw, before, check_exact=True)
    adapter._assert_preserved(raw, derivative)
    for name in raw.columns.difference(adapter.FIELDS):
        pd.testing.assert_series_equal(raw[name], derivative[name], check_exact=True)
        if raw[name].dtype == np.dtype("float64"):
            np.testing.assert_array_equal(raw[name].to_numpy().view(np.uint64), derivative[name].to_numpy().view(np.uint64))
    assert summary(raw, categories()["anytime_td"]) == summary(derivative, categories()["anytime_td"])
    assert receipt["raw_state"] == "INVALID_V1_CDF_BRACKET" and receipt["raw_strict_CDF_bracket_invalid_rows"] == 1
    assert receipt["field_differences"]["cdf_actual"]["different_rows"] == 1
    assert receipt["field_differences"]["crps"]["max_abs_difference_finite_pairs"] > 0
    assert receipt["field_differences"]["log_score"]["different_rows"] == 1
    assert receipt["unknown_participation_rows"] == receipt["played_missing_actual_rows"] == receipt["missing_probability_rows"] == 1
    assert derivative.loc[[17, 18, 19], list(adapter.FIELDS)].isna().all(axis=None)
    assert np.isposinf(derivative.loc[[11, 12], "log_score"]).all()
    assert derivative.loc[10, "cdf_actual_below"] == 0 and derivative.loc[10, "cdf_actual"] == 1
    assert derivative.loc[13, "cdf_actual_below"] == 0 and derivative.loc[13, "cdf_actual"] == 1
    assert "PRIVATE-" not in json.dumps(receipt, allow_nan=False)


def test_infinity_transitions_are_explicit_no_probability_clipping():
    raw = fictional()
    raw.loc[11, "log_score"] = 100.
    raw.loc[14, "log_score"] = np.inf
    _, receipt = adapter.canonical_bernoulli_diagnostics(raw)
    transitions = receipt["field_differences"]["log_score"]["value_state_transitions"]
    assert transitions["finite_to_positive_infinity"] == 1
    assert transitions["positive_infinity_to_finite"] == 1
    assert receipt["probability_clipping"] == "none"


@pytest.mark.parametrize("field,value", [("probability", -.01), ("probability", 1.01), ("probability", np.inf),
    ("probability", -np.inf), ("actual", 2.), ("actual", -.5), ("actual", np.inf), ("point", .3), ("mean", .3)])
def test_invalid_event_probability_actual_or_frozen_point_identity_rejected(field, value):
    raw = fictional()
    raw.loc[14, field] = value
    with pytest.raises(adapter.DiagnosticInputError) as caught:
        adapter.canonical_bernoulli_diagnostics(raw)
    assert caught.value.receipt["state"] == "REJECTED"
    assert "PRIVATE-" not in json.dumps(caught.value.receipt, allow_nan=False)


@pytest.mark.parametrize("row,field,value", [(17, "crps", .1), (18, "cdf_actual", .5), (19, "log_score", 1.),
    (14, "crps", np.nan), (14, "log_score", np.nan), (14, "cdf_actual_below", np.inf), (14, "log_score", -np.inf)])
def test_missingness_masks_never_create_new_scores_or_guessed_zero(row, field, value):
    raw = fictional()
    raw.loc[row, field] = value
    with pytest.raises(adapter.DiagnosticInputError, match="missing|already-frozen"):
        adapter.canonical_bernoulli_diagnostics(raw)


def test_exact_identities_detect_wrong_in_range_values_that_old_validator_allows():
    derivative, _ = adapter.canonical_bernoulli_diagnostics(fictional())
    for field in adapter.FIELDS:
        wrong = derivative.copy()
        wrong.loc[14, field] = .4
        reporting._validate(wrong, categories(), 500, 1703)
        with pytest.raises(ValueError, match="identity"):
            adapter._assert_identities(wrong)
    for field, value in [("variance", -1.), ("p10", .5), ("primary_role", False)]:
        wrong = derivative.copy()
        wrong.loc[14, field] = value
        with pytest.raises(ValueError):
            reporting._validate(wrong, categories(), 500, 1703)


def test_scope_keys_and_float_schema_guards():
    raw = fictional()
    wrongs = [raw.iloc[:0], pd.concat([raw, raw.iloc[:1]]), raw.assign(target="pass_yd"), raw.assign(method="recent"),
        raw.assign(participation_state="unread"), raw.astype({"crps": "float32"})]
    for wrong in wrongs:
        with pytest.raises(ValueError):
            adapter.canonical_bernoulli_diagnostics(wrong)


def test_no_io_or_model_law_calls(monkeypatch):
    from nfl_lab.cdf_engine import MixtureBatch
    def forbidden(*args, **kwargs):
        raise AssertionError("no IO or model/law operation allowed")
    monkeypatch.setattr(pd, "read_parquet", forbidden)
    for name in ("cdf", "crps", "logpmf"):
        monkeypatch.setattr(MixtureBatch, name, forbidden)
    derivative, _ = adapter.canonical_bernoulli_diagnostics(fictional())
    assert len(derivative) == 10
