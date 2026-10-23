"""Fictional metadata and feature fixtures; no NFL reads, models or HTTP."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab import canonical_feature_inputs as c
from nfl_lab import features, operational_sources as source, query_identity as identity

SHA = "a" * 64


def fixture():
    original = pd.DataFrame({"cutoff_utc": ["2030-01-01T00:00:00+00:00"] * 3,
        "game_id": ["fictional-game"] * 3, "kickoff_utc": ["2030-01-02T00:00:00+00:00"] * 3,
        "opponent": ["B"] * 3, "outcome_available_utc": ["2030-01-09T00:00:00+00:00"] * 3,
        "participation_state": ["unknown"] * 3, "player_id": ["sleeper:123", " 00-0000002 ", "sleeper:999"],
        "position": ["QB"] * 3, "season": [2030] * 3, "team": ["A"] * 3, "week": [1] * 3})
    original.index = pd.Index([8, 3, 17], name="original-order")
    registry = pd.DataFrame({"player_id": ["00-0000001", "00-0000002"], "sleeper_id": ["123", "456"],
                             "identity_status": ["source_exact_binding"] * 2})
    resolved, receipt = identity.resolve_query_identities(original, registry, identity_sha256=SHA)
    payload = {"evidence_lane": c.EVIDENCE, "columns": list(resolved), "index": resolved.index.tolist(),
               "rows": resolved.to_dict("records"), "receipt": receipt}
    return original, json.loads(json.dumps(payload)), resolved


def history():
    frame = pd.DataFrame({"season": [2029] * 3, "week": [1, 2, 1], "team": ["A"] * 3,
        "opponent": ["B"] * 3, "game_id": ["old-a", "old-b", "old-c"],
        "player_id": ["00-0000001", "00-0000001", "00-0000002"], "position": ["QB"] * 3,
        "kickoff_utc": pd.to_datetime(["2029-01-01T00:00Z", "2029-01-08T00:00Z", "2029-01-01T00:00Z"], utc=True),
        "participation_state": ["played", "unknown", "played"]})
    frame["cutoff_utc"] = frame.kickoff_utc
    frame["outcome_available_utc"] = frame.kickoff_utc + pd.Timedelta(days=7)
    for field in features.PLAYER_STATS:
        frame[field] = [0., np.nan, 1.]
    frame["pass_yd"] = [-3., np.nan, 0.]
    frame["rush_rec_yd"] = frame.rush_yd + frame.rec_yd
    frame["anytime_td"] = [0., np.nan, 1.]
    frame["fantasy_ppr"] = np.nan
    frame["offense_snaps"] = np.nan
    policy = source.load_source_policy(Path(__file__).parents[1] / "config/operational-source-policy-v2.json")
    frame.attrs["operational_manifest"] = {"policy_sha256": policy["_policy_sha256"],
        "code_sha256s": source._code_hashes(), "history_frame_sha256": source._frame_sha(frame),
        "asof_utc": "2029-12-01T00:00:00+00:00", "snapshot_sha256": "b" * 64,
        "training_view_sha256": "c" * 64,
        "source_receipts": {"fictional": {"retrieved_utc": "2029-12-01T00:00:00+00:00"}}}
    return frame, policy


def test_exact_private_envelope_roundtrip_preserves_context_aliases_index_and_inputs():
    original, payload, resolved = fixture()
    before, payload_before = original.copy(deep=True), deepcopy(payload)
    result = c.validate_canonical_query(payload, original, expected_identity_sha256=SHA)
    pd.testing.assert_frame_equal(result, resolved, check_exact=True)
    pd.testing.assert_frame_equal(original, before, check_exact=True)
    assert payload == payload_before
    assert result.attrs[c.VALIDATION_ATTR]["canonical_query_sha256"] == identity._frame_hash(result)


def test_default_range_index_is_restored_without_changing_frame_hash():
    original, _, _ = fixture()
    original = original.reset_index(drop=True)
    registry = pd.DataFrame({"player_id": ["00-0000001"], "sleeper_id": ["123"], "identity_status": ["source_exact_binding"]})
    resolved, receipt = identity.resolve_query_identities(original, registry, identity_sha256=SHA)
    payload = dict(evidence_lane=c.EVIDENCE, columns=list(resolved), index=resolved.index.tolist(), rows=resolved.to_dict("records"), receipt=receipt)
    result = c.validate_canonical_query(payload, original, expected_identity_sha256=SHA)
    pd.testing.assert_index_equal(result.index, original.index, exact=True)
    assert identity._frame_hash(result) == receipt["output_query_sha256"]


@pytest.mark.parametrize("change", [
    lambda p: p.update(unknown="forbidden"),
    lambda p: p.update(evidence_lane="ISSUED"),
    lambda p: p["columns"].reverse(),
    lambda p: p["index"].reverse(),
    lambda p: p["rows"].reverse(),
    lambda p: p["rows"][0].update(pass_yd=0),
    lambda p: p["rows"][0].update(team="changed"),
    lambda p: p["rows"][0].update(original_player_id="changed"),
    lambda p: p["rows"][0].update(identity_source_sha256="b" * 64),
    lambda p: p["rows"][0].update(identity_adapter_version="unknown"),
    lambda p: p["rows"][0].update(identity_resolution_state="unknown"),
    lambda p: p["rows"][0].update(player_id="00-0000002"),
    lambda p: p["receipt"].update(output_query_sha256="b" * 64),
    lambda p: p["receipt"].update(input_query_sha256="b" * 64),
    lambda p: p["receipt"].update(identity_source_sha256="b" * 64),
    lambda p: p["receipt"].update(changed_player_ids=1),
    lambda p: p["receipt"].update(input_rows=True),
    lambda p: p["receipt"]["resolution_state_counts"].update(resolved_source_exact_sleeper=True),
    lambda p: p["receipt"]["registry"].update(quarantined_rows=1000),
    lambda p: p["receipt"]["registry"].update(raw_rows=[]),
])
def test_private_schema_context_receipt_mutations_fail_closed(change):
    original, payload, _ = fixture()
    change(payload)
    with pytest.raises(ValueError):
        c.validate_canonical_query(payload, original, expected_identity_sha256=SHA)


def test_unchanged_builder_called_once_with_context_provenance_and_null_labels(monkeypatch):
    original, payload, _ = fixture()
    canonical = c.validate_canonical_query(payload, original, expected_identity_sha256=SHA)
    h, policy = history()
    before, query_before = h.copy(deep=True), canonical.copy(deep=True)
    calls = []
    implementation = source.build_operational_features
    def once(*args, **kwargs):
        calls.append(1)
        return implementation(*args, **kwargs)
    monkeypatch.setattr(source, "build_operational_features", once)
    result, receipt = c.build_canonical_features(h, canonical, policy=policy)
    assert len(calls) == 1
    assert len([name for name in result if name.startswith("f_")]) == 97
    assert result[list(c.TARGETS)].isna().all().all() and result.f_player_play_rate8.isna().all()
    assert result.f_player_pass_yd_mean3.iloc[0] == -3.  # Preserve signed observations; unknown row stays a slot.
    assert result.f_player_pass_yd_n3.iloc[0] == 1.
    assert result.f_player_games_prior.tolist() == [2., 1., 0.]
    assert receipt["feature_builder_calls"] == 1 and receipt["identity_source_sha256"] == SHA
    assert receipt["feature_values_sha256"] == identity._frame_hash(result[[name for name in result if name.startswith("f_")]])
    assert "sleeper:123" not in json.dumps(receipt) and "00-0000001" not in json.dumps(receipt)
    pd.testing.assert_frame_equal(before, h, check_exact=True)
    pd.testing.assert_frame_equal(query_before, canonical, check_exact=True)


@pytest.mark.parametrize("change", [
    lambda f: f.__setitem__("pass_yd", 0.),
    lambda f: f.__setitem__("participation_state", "played"),
    lambda f: f.__setitem__("f_player_play_rate8", .99),
    lambda f: f.__setitem__("team", "changed"),
    lambda f: f.__setitem__("original_player_id", "changed"),
    lambda f: f.__setitem__("feature_max_source_available_utc", pd.Timestamp("2031-01-01", tz="UTC")),
    lambda f: f.__setitem__("feature_max_assumed_history_available_utc", pd.Timestamp("2030-01-01", tz="UTC")),
    lambda f: f.__setitem__("f_player_games_prior", np.inf),
    lambda f: f.drop(columns="f_player_games_prior", inplace=True),
])
def test_builder_output_contract_failures_are_not_retried(monkeypatch, change):
    original, payload, _ = fixture()
    canonical = c.validate_canonical_query(payload, original, expected_identity_sha256=SHA)
    h, policy = history()
    implementation = source.build_operational_features
    calls = []
    def bad(*args, **kwargs):
        calls.append(1)
        frame = implementation(*args, **kwargs)
        change(frame)
        return frame
    monkeypatch.setattr(source, "build_operational_features", bad)
    with pytest.raises(ValueError):
        c.build_canonical_features(h, canonical, policy=policy)
    assert len(calls) == 1


def test_changed_validated_query_rejected_before_builder(monkeypatch):
    original, payload, _ = fixture()
    canonical = c.validate_canonical_query(payload, original, expected_identity_sha256=SHA)
    canonical.iloc[0, canonical.columns.get_loc("team")] = "changed"
    monkeypatch.setattr(source, "build_operational_features", lambda *a, **k: pytest.fail("builder must not run"))
    with pytest.raises(ValueError, match="changed before"):
        c.build_canonical_features(pd.DataFrame(), canonical, policy={})
