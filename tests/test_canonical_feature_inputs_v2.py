"""Fictional nullable future metadata; no NFL reads, models, fits or HTTP."""
from copy import deepcopy
import json

import numpy as np
import pandas as pd
import pytest

from nfl_lab import canonical_feature_inputs as v1
from nfl_lab import canonical_feature_inputs_v2 as v2
from nfl_lab import operational_sources as source, query_identity as identity
from test_canonical_feature_inputs import SHA, fixture, history


def nullable_metadata(future=None, cutoff=None, kickoff=None):
    original, payload, _ = fixture()
    original["outcome_available_utc"] = future
    if cutoff is not None:
        original["cutoff_utc"] = cutoff
    if kickoff is not None:
        original["kickoff_utc"] = kickoff
    for i, row in enumerate(payload["rows"]):
        for name in ["outcome_available_utc", "cutoff_utc", "kickoff_utc"]:
            row[name] = original[name].iloc[i]
    resolved = pd.DataFrame(payload["rows"], columns=payload["columns"], index=original.index)
    payload["receipt"]["input_query_sha256"] = identity._frame_hash(original)
    payload["receipt"]["output_query_sha256"] = identity._frame_hash(resolved)
    return original, payload, v2.validate_canonical_query(payload, original, expected_identity_sha256=SHA)


@pytest.mark.parametrize("future,missing", [(None, 3),
    ([None, "2030-01-09T00:00:00+00:00", None], 2), ("2030-01-09T01:00:00+01:00", 0)])
def test_null_or_correct_future_placeholder_reuses_builder_once_and_preserves_input(monkeypatch, future, missing):
    original, payload, canonical = nullable_metadata(future)
    before, payload_before = canonical.copy(deep=True), deepcopy(payload)
    h, policy = history()
    calls = []
    implementation = source.build_operational_features
    def once(*a, **k):
        calls.append(1)
        return implementation(*a, **k)
    monkeypatch.setattr(source, "build_operational_features", once)
    result, receipt = v2.build_canonical_features(h, canonical, policy=policy)
    assert len(calls) == 1 and receipt["feature_builder_calls"] == 1
    assert result.outcome_available_utc.eq(pd.Timestamp("2030-01-09", tz="UTC")).all()
    assert receipt["missing_future_placeholder_rows"] == missing
    assert "assumed_not_observed" in receipt["future_placeholder_rule"]
    assert receipt["adapter_version"] == v2.VERSION != v1.VERSION
    assert receipt["metadata_validator_version"] == v1.VERSION
    assert receipt["canonical_query_sha256"] == identity._frame_hash(canonical)
    assert result[list(v2.TARGETS)].isna().all().all() and result.f_player_play_rate8.isna().all()
    assert result.f_player_games_prior.tolist() == [2., 1., 0.]
    assert result.f_player_pass_yd_mean3.iloc[0] == -3.
    assert len([name for name in result if name.startswith("f_")]) == 97
    pd.testing.assert_frame_equal(canonical, before, check_exact=True)
    assert payload == payload_before
    assert "sleeper:123" not in json.dumps(receipt) and "00-0000001" not in json.dumps(receipt)


def test_v1_validator_is_reused_and_failed_v1_guard_remains_unchanged():
    assert v2.validate_canonical_query is v1.validate_canonical_query
    _, _, canonical = nullable_metadata()
    h, policy = history()
    with pytest.raises(ValueError, match="clocks required"):
        v1.build_canonical_features(h, canonical, policy=policy)


@pytest.mark.parametrize("future,cutoff,kickoff", [
    ("2030-01-08T00:00:00Z", None, None),
    ("2030-01-10T00:00:00Z", None, None),
    ("invalid", None, None),
    ("", None, None),
    ("NaT", None, None),
    (None, [None, None, None], None),
    (None, None, [None, None, None]),
    (None, "2030-01-03T00:00:00Z", None),
])
def test_adversarial_future_and_required_clocks_reject_before_builder(monkeypatch, future, cutoff, kickoff):
    _, _, canonical = nullable_metadata(future, cutoff, kickoff)
    monkeypatch.setattr(source, "build_operational_features", lambda *a, **k: pytest.fail("builder must not run"))
    with pytest.raises(ValueError):
        v2.build_canonical_features(pd.DataFrame(), canonical, policy={})


@pytest.mark.parametrize("change", [
    lambda h: h.__setitem__("team", "changed"),
    lambda h: h.attrs["operational_manifest"].update(asof_utc="2031-01-01T00:00:00Z"),
    lambda h: h.attrs["operational_manifest"]["source_receipts"]["fictional"].update(retrieved_utc="2031-01-01T00:00:00Z"),
    lambda h: h.attrs["operational_manifest"].update(code_sha256s={}),
])
def test_original_source_history_and_receipt_gates_remain_active(change):
    _, _, canonical = nullable_metadata()
    h, policy = history()
    change(h)
    with pytest.raises(ValueError):
        v2.build_canonical_features(h, canonical, policy=policy)


def test_history_equal_to_cutoff_still_excluded_by_shared_builder():
    _, _, canonical = nullable_metadata()
    h, policy = history()
    h.loc[1, "outcome_available_utc"] = pd.Timestamp("2030-01-01", tz="UTC")
    h.attrs["operational_manifest"]["history_frame_sha256"] = source._frame_sha(h)
    result, _ = v2.build_canonical_features(h, canonical, policy=policy)
    assert result.f_player_games_prior.tolist() == [1., 1., 0.]
    assert result.feature_max_assumed_history_available_utc.dropna().lt(pd.Timestamp("2030-01-01", tz="UTC")).all()


@pytest.mark.parametrize("column,value", [
    ("outcome_available_utc", pd.NaT),
    ("outcome_available_utc", pd.Timestamp("2030-01-10", tz="UTC")),
    ("feature_max_assumed_history_available_utc", pd.Timestamp("2030-01-01", tz="UTC")),
    ("feature_max_source_available_utc", pd.Timestamp("2030-01-02", tz="UTC")),
    ("pass_yd", 0.), ("f_player_play_rate8", .99), ("f_player_games_prior", np.inf),
])
def test_result_guards_still_reject_bad_output_without_retry(monkeypatch, column, value):
    _, _, canonical = nullable_metadata()
    h, policy = history()
    calls = []
    implementation = source.build_operational_features
    def bad(*a, **k):
        calls.append(1)
        frame = implementation(*a, **k)
        frame[column] = value
        return frame
    monkeypatch.setattr(source, "build_operational_features", bad)
    with pytest.raises(ValueError):
        v2.build_canonical_features(h, canonical, policy=policy)
    assert len(calls) == 1
