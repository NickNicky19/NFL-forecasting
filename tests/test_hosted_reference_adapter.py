"""Fictional live identity/quota checks; no remote input or optimizer calls."""
import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab import hosted_reference_adapter as adapter, live, model_artifacts, operational_models, state
from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError
from nfl_lab.reference_runtime import StateBoundStorage, _json


def registry(*rows):
    return pd.DataFrame(rows, columns=["player_id", "sleeper_id", "identity_status"])


def population(players, frozen=None):
    games = [{"game_id": "espn:fictional", "kickoff_utc": "2030-09-01T18:00:00Z", "home": "A", "away": "B"}]
    people = {sid: {"team": "A", "position": "RB", "active": True, "gsis_id": direct} for sid, direct in players}
    result = live.future_population(people, games, 2030, 1, frozen_by_game_sleeper=frozen)
    result["cutoff_utc"] = "2030-09-01T16:00:00Z"
    result["outcome_available_utc"] = pd.to_datetime(result.kickoff_utc, utc=True) + pd.Timedelta(days=7)
    result.index = pd.Index(range(19, 19+len(result)), name="original_index")
    return result


def adapt(frame, table, frozen=None):
    return adapter.adapt_live_identities(frame, table, identity_sha256="a"*64,
                                        frozen_by_game_sleeper=frozen or {})


def test_exact_provider_and_sleeper_paths_repair_only_qualified_ascii_spaces():
    table = registry(("00-0000001", "001", "source_exact_binding"),
        ("00-0000002", "2", "source_exact_binding"), ("00-0000003", "3", "no_sleeper_binding"))
    original = population([("001", None), ("2", " 00-0000002 "), ("4", "\t00-0000004\t"), ("5", None)])
    before = original.copy(deep=True)
    result, receipt = adapt(original, table)
    assert result.player_id.tolist() == ["00-0000001", "00-0000002", "\t00-0000004\t", "sleeper:5"]
    assert result.identity_binding.iloc[0] == "nflverse_exact_id_crosswalk"
    assert result.identity_resolution_state.iloc[1] == "resolved_registry_ascii_space_gsis"
    assert result.identity_resolution_state.iloc[2] == "unresolved_identity_text"
    pd.testing.assert_frame_equal(original, before, check_exact=True)
    context = [c for c in original if c not in {"player_id", "identity_binding"}]
    pd.testing.assert_frame_equal(result[context], original[context], check_exact=True)
    assert result.original_player_id.tolist() == original.player_id.tolist()
    assert receipt["input_rows"] == receipt["output_rows"] == 4 and receipt["dropped_rows"] == 0
    assert result.identity_adapter_version.eq(adapter.VERSION).all()
    assert result.canonical_identity_adapter_version.eq(adapter.query_identity.VERSION).all()
    repeated, same_receipt = adapt(original, table)
    pd.testing.assert_frame_equal(result, repeated, check_exact=True)
    assert receipt == same_receipt


@pytest.mark.parametrize("rows", [
    [("00-0000001", "1", "source_exact_binding"), ("00-0000002", "1", "source_exact_binding")],
    [("00-0000001", "1", "source_exact_binding"), (None, "1", "source_exact_binding")],
    [("00-0000001", "1", "source_exact_binding"), ("00-0000001", "2", "source_exact_binding")]])
def test_ambiguous_or_unusable_crosswalk_never_selects_candidate(rows):
    result, receipt = adapt(population([("1", "00-0000001")]), registry(*rows))
    assert result.player_id.tolist() == ["sleeper:1"]
    assert result.identity_binding.tolist() == ["conflicting_identity_cold_start"]
    assert result.identity_resolution_state.tolist() == ["unresolved_live_provider_registry_conflict"]


def test_provider_disagreement_and_frozen_first_identity_win_last():
    table = registry(("00-0000002", "1", "source_exact_binding"))
    result, receipt = adapt(population([("1", "00-0000001")]), table)
    assert result.player_id.tolist() == ["sleeper:1"]
    frozen = {("espn:fictional", "1"): "sleeper:1"}
    original = population([("1", "00-0000001")], frozen)
    result, receipt = adapt(original, table, frozen)
    assert result.player_id.tolist() == ["sleeper:1"]
    assert result.identity_resolution_state.tolist() == ["frozen_first_identity"]
    assert result.identity_binding.tolist() == ["frozen_first_sleeper_binding"]
    assert receipt["provider_candidates"]["input_rows"] == 0
    assert receipt["frozen_identity_rows"] == 1


def test_new_identity_cannot_collide_with_already_frozen_game_key():
    frozen = {("espn:fictional", "2"): "00-0000001"}
    original = population([("1", None), ("2", None)], frozen)
    with pytest.raises(ValueError, match="collision"):
        adapt(original, registry(("00-0000001", "1", "source_exact_binding")), frozen)


@pytest.mark.parametrize("mutation", ["typed-provider", "typed-registry", "duplicate-index", "foreign-stat", "unchecked-binding", "unknown-participation", "bad-frozen"])
def test_invalid_metadata_fails_closed_without_input_mutation(mutation):
    original = population([("1", None)])
    table = registry(("00-0000001", "1", "source_exact_binding"))
    frozen = {}
    if mutation == "typed-provider": original["player_id"] = 123
    elif mutation == "typed-registry": table["sleeper_id"] = 1
    elif mutation == "duplicate-index":
        original = pd.concat([original, original.assign(sleeper_id="2", player_id="sleeper:2")])
    elif mutation == "foreign-stat": original["rush_yd"] = 42
    elif mutation == "unchecked-binding": original["identity_binding"] = "nflverse_exact_id_crosswalk"
    elif mutation == "unknown-participation": original["participation_state"] = "played"
    else: frozen = {("espn:fictional", "1"): None}
    before = original.copy(deep=True)
    with pytest.raises((ValueError, TypeError)):
        adapt(original, table, frozen)
    pd.testing.assert_frame_equal(original, before, check_exact=True)


def test_identity_receipt_and_code_hashes_bind_exact_sources():
    result, receipt = adapt(population([("01", None)]), registry(("00-0000001", "1", "source_exact_binding")))
    assert result.player_id.tolist() == ["sleeper:01"]
    supplied = receipt.pop("receipt_sha256")
    assert supplied == state.digest(receipt)
    assert set(adapter.code_hashes()) == {"hosted_reference_adapter.py", "query_identity.py", "reference_runtime.py"}
    assert all(len(sha) == 64 for sha in adapter.code_hashes().values())


@pytest.mark.parametrize("phase", ["provisional", "final"])
def test_real_reference_serializer_state_peak_rejects_before_write(tmp_path, monkeypatch, phase):
    from nfl_lab import models
    from test_models import histories
    train, query = histories(8)
    policy = {"storage": {"version": "operational-storage-v2", "limit_bytes": 1_000_000},
        "namespaces": {"private_retention_bytes": 1_000_000}, "_policy_sha256": "a"*64}
    storage = OperationalStorage(tmp_path / "cache", policy, state=tmp_path / "state")
    manifest = {"adapter_version": "permitted-operational-nfl-history-v2", "policy_sha256": "a"*64,
        "snapshot_sha256": "b"*64, "training_view_sha256": "c"*64, "namespace": "fictional"}
    binding = operational_models.model_binding(policy, manifest, train, query, "d"*64)
    payload = {"target": "pass_yd", "method": "recent", "training_audit": {}}
    core = {"artifact": payload, "sha256": state.digest(payload)}
    final_payload = copy.deepcopy(payload)
    final_payload.update(participation={"kind": "unavailable"}, operational_source_binding=binding)
    final_payload["training_audit"]["participation"] = operational_models.PARTICIPATION.copy()
    final = {"artifact": final_payload, "sha256": state.digest(final_payload)}
    current = sum(path.stat().st_size for path in storage.state_root.rglob("*") if path.is_file())
    cap = current + len(_json(core)) - 1 if phase == "provisional" else current + len(_json(core)) + len(_json(final)) - 1
    guarded = StateBoundStorage(storage, storage.state_root, cap)
    original = model_artifacts._atomic_json
    def inert_core(train, query, target, method, *, artifact_path):
        model_artifacts._atomic_json(artifact_path, core)
        return pd.DataFrame({"mean": 1., "p_participation": np.nan}, index=query.index)
    monkeypatch.setattr(models, "fit_predict", inert_core)
    destination = storage.model_root / "fictional.json"
    before = storage.snapshot()["physical_bytes"]
    with pytest.raises(StorageQuotaError, match="serialized state"):
        operational_models.fit_operational_reference(train, query, "pass_yd", "recent",
            artifact_path=destination, binding=binding, storage=guarded)
    assert not destination.exists()
    assert model_artifacts._atomic_json is original
    if phase == "provisional": assert storage.snapshot()["physical_bytes"] == before
    else: assert storage.snapshot()["physical_bytes"] > before  # Failed provisional CAS evidence retained.
