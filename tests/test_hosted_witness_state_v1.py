"""Fictional metadata, stubbed weekly estimators, and local Git only."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_lab import experiment, operational_models, publication_scope as p
from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError
from nfl_lab.reference_runtime import StateBoundStorage
from nfl_lab.state import canonical, digest, records, save
from test_publication_scope import NOW, git, scope, setup_repo

POLICY_SHA = "a" * 64


def envelope_fixture(tmp_path):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    envelope = scope(root, state, commit, f"forecasts/{one}.json.gz",
                     f"website_bindings/{web}.json.gz", f"health/{health}.json.gz", policy=POLICY_SHA)
    return root, state, commit, one, web, envelope


def publish(f, observed=NOW, storage=None):
    root, state, commit, _, _, envelope = f
    return p.record_scoped_publication(root, state, commit=commit, scope=envelope,
        observed=observed, policy_sha256=POLICY_SHA, storage=storage)


def test_original_full_envelope_roundtrip_precedes_receipts_and_is_copied(tmp_path, monkeypatch):
    f = envelope_fixture(tmp_path)
    original_save = p.save
    calls = []
    def ordered(state, kind, document, **kwargs):
        if kind in {"publication", "website_publication"}:
            assert p.saved_scope_evidence(state, POLICY_SHA) == {digest(f[-1]): f[-1]}
        calls.append(kind)
        return original_save(state, kind, document, **kwargs)
    monkeypatch.setattr(p, "save", ordered)
    publish(f)
    assert calls == [p.SCOPE_RECORDS, "publication", "website_publication"]
    original = deepcopy(f[-1])
    assert list(records(f[1], p.SCOPE_RECORDS)) == [original]
    monkeypatch.setattr(p, "_git", lambda *a: pytest.fail("loader must not read Git or source files"))
    evidence = p.saved_scope_evidence(f[1], POLICY_SHA)
    evidence[digest(original)]["files"].clear()
    assert p.saved_scope_evidence(f[1], POLICY_SHA) == {digest(original): original}
    assert len(original["files"]) == 3


def test_absence_does_not_reconstruct_legacy_scope(tmp_path):
    state = tmp_path / "state"
    save(state, "publication", {"batch": "b" * 64, "publication_scope_schema": p.SCHEMA,
         "publication_scope_sha256": "c" * 64, "observed_remote_readback_at": NOW.isoformat()})
    assert p.saved_scope_evidence(state, POLICY_SHA) == {}
    assert not (state / p.SCOPE_RECORDS).exists()


@pytest.mark.parametrize("kind,field,index", [("publication", "batch", 3), ("website_publication", "snapshot", 4)])
def test_old_scoped_receipt_without_original_witness_cannot_be_retroqualified(tmp_path, kind, field, index):
    from datetime import timedelta
    f = envelope_fixture(tmp_path)
    key = save(f[1], kind, {field: f[index], "publication_scope_schema": p.SCHEMA,
        "publication_scope_sha256": digest(f[-1]), "observed_remote_readback_at": NOW.isoformat()})
    old = f[1] / kind / (key + ".json.gz"); original = old.read_bytes()
    before = {str(path): path.read_bytes() for path in f[1].rglob("*.json.gz")}
    with pytest.raises(ValueError, match="missing original witness"):
        publish(f)
    assert p.saved_scope_evidence(f[1], POLICY_SHA) == {}
    assert before == {str(path): path.read_bytes() for path in f[1].rglob("*.json.gz")}
    assert old.read_bytes() == original
    # A genuinely new commit/scope may establish only its new actual clock.
    git(f[0], "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "--allow-empty", "-m", "new publication event")
    new_commit = git(f[0], "rev-parse", "HEAD")
    new_scope = p.scope_document(new_commit, f[-1]["files"], verified_remote_commit=new_commit,
                                 policy_sha256=POLICY_SHA)
    publish((f[0], f[1], new_commit, f[3], f[4], new_scope), NOW+timedelta(hours=2))
    assert p.saved_scope_evidence(f[1], POLICY_SHA) == {digest(new_scope): new_scope}
    new = [r for r in records(f[1], kind) if r.get("publication_scope_sha256") == digest(new_scope)]
    assert len(new) == 1 and new[0]["observed_remote_readback_at"] == (NOW+timedelta(hours=2)).isoformat()
    assert old.read_bytes() == original


@pytest.mark.parametrize("policy", [None, "bad", "A"*64])
def test_loader_requires_explicit_policy_even_when_scope_directory_is_absent(tmp_path, policy):
    with pytest.raises(ValueError, match="explicit policy"):
        p.saved_scope_evidence(tmp_path / "absent", policy)


def test_verification_failure_cannot_persist_witness_or_receipt(tmp_path):
    f = envelope_fixture(tmp_path)
    f[-1]["files"][f"forecasts/{f[3]}.json.gz"] = "0" * 64
    with pytest.raises(ValueError):
        publish(f)
    assert list(records(f[1], p.SCOPE_RECORDS)) == []
    assert list(records(f[1], "publication")) == list(records(f[1], "website_publication")) == []


def test_witness_persistence_failure_cannot_append_partial_receipts(tmp_path, monkeypatch):
    f = envelope_fixture(tmp_path)
    real_save = p.save
    def full(state, kind, document, **kwargs):
        if kind == p.SCOPE_RECORDS:
            raise StorageQuotaError("fictional witness byte reservation failed")
        return real_save(state, kind, document, **kwargs)
    monkeypatch.setattr(p, "save", full)
    with pytest.raises(StorageQuotaError, match="reservation"):
        publish(f)
    assert list(records(f[1], "publication")) == list(records(f[1], "website_publication")) == []


def test_existing_contradictory_witness_cannot_be_silently_reused(tmp_path):
    f = envelope_fixture(tmp_path)
    folder = f[1] / p.SCOPE_RECORDS; folder.mkdir()
    (folder / (digest(f[-1]) + ".json.gz")).write_bytes(gzip.compress(canonical({"not": "original"}), mtime=0))
    with pytest.raises(ValueError):
        publish(f)
    assert list(records(f[1], "publication")) == list(records(f[1], "website_publication")) == []


def test_same_scope_idempotent_new_verified_scope_has_own_actual_clock(tmp_path):
    from datetime import timedelta
    f = envelope_fixture(tmp_path)
    old = save(f[1], "publication", {"batch": f[3], "observed_remote_readback_at": (NOW-timedelta(days=10)).isoformat()})
    oldpath = f[1] / "publication" / (old + ".json.gz"); original = oldpath.read_bytes()
    publish(f)
    before = {str(path): path.read_bytes() for path in f[1].rglob("*.json.gz")}
    repeated = publish(f, NOW+timedelta(hours=2))
    assert repeated["publication_verified_rows"] == repeated["website_snapshots_publication_checked"] == 0
    assert before == {str(path): path.read_bytes() for path in f[1].rglob("*.json.gz")}
    # A genuinely different verified scope contains the same two exact records
    # but omits the aggregate. Its new event is late and retains that clock.
    later = deepcopy(f[-1]); later["files"] = {k: v for k, v in later["files"].items() if not k.startswith("health/")}
    f2 = (*f[:-1], later)
    result = publish(f2, NOW+timedelta(hours=2))
    assert result["publication_verified_rows"] == 0 and result["late_rows"] == 1
    assert result["website_snapshots_publication_checked"] == 1
    assert set(p.saved_scope_evidence(f[1], POLICY_SHA)) == {digest(f[-1]), digest(later)}
    for kind in ("publication", "website_publication"):
        new = [r for r in records(f[1], kind) if r.get("publication_scope_sha256") == digest(later)]
        assert len(new) == 1 and new[0]["observed_remote_readback_at"] == (NOW+timedelta(hours=2)).isoformat()
    assert oldpath.read_bytes() == original


def test_aggregate_scope_is_retained_and_makes_zero_timing_claims(tmp_path):
    f = envelope_fixture(tmp_path)
    aggregate = deepcopy(f[-1]); aggregate["files"] = {k: v for k, v in aggregate["files"].items() if k.startswith("health/")}
    f = (*f[:-1], aggregate)
    result = publish(f)
    assert result["publication_verified_rows"] == result["website_snapshots_publication_checked"] == 0
    assert p.saved_scope_evidence(f[1], POLICY_SHA) == {digest(aggregate): aggregate}
    assert list(records(f[1], "publication")) == list(records(f[1], "website_publication")) == []


@pytest.mark.parametrize("mutation", ["hash", "policy", "schema", "path", "commit", "remote", "gzip", "noncanonical", "symlink", "parent_symlink"])
def test_saved_scope_loader_rejects_invalid_original_evidence(tmp_path, mutation):
    f = envelope_fixture(tmp_path)
    envelope = deepcopy(f[-1])
    if mutation == "policy": envelope["policy_sha256"] = "f" * 64
    if mutation == "schema": envelope["schema_version"] = "other"
    if mutation == "path": envelope["files"] = {"../escape": "b" * 64}
    if mutation == "commit": envelope["commit"] = "HEAD"
    if mutation == "remote": envelope["verified_remote_commit"] = "0" * 40
    key = save(f[1], p.SCOPE_RECORDS, envelope)
    path = f[1] / p.SCOPE_RECORDS / (key + ".json.gz")
    if mutation == "hash": path.rename(path.with_name("0" * 64 + ".json.gz"))
    if mutation == "gzip": path.write_bytes(b"not gzip")
    if mutation == "noncanonical": path.write_bytes(gzip.compress(json.dumps(envelope).encode(), mtime=0))
    if mutation == "symlink":
        other = f[1] / "elsewhere"; other.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(other)
    if mutation == "parent_symlink":
        folder = path.parent; other = f[1] / "elsewhere"; folder.rename(other); folder.symlink_to(other, target_is_directory=True)
    with pytest.raises((ValueError, OSError, EOFError)):
        p.saved_scope_evidence(f[1], POLICY_SHA)


def test_loader_bounds_encoded_decoded_inventory_and_rejects_parent_traversal(tmp_path, monkeypatch):
    f = envelope_fixture(tmp_path); publish(f)
    with pytest.raises(ValueError, match="traversal"):
        p.saved_scope_evidence(f[1] / "x" / "..", POLICY_SHA)
    size = (f[1] / p.SCOPE_RECORDS / (digest(f[-1]) + ".json.gz")).stat().st_size
    monkeypatch.setattr(p, "MAX_BYTES", size-1)
    with pytest.raises(ValueError, match="compressed"):
        p.saved_scope_evidence(f[1], POLICY_SHA)
    monkeypatch.setattr(p, "MAX_BYTES", size+1)
    with pytest.raises(ValueError, match="decoded"):
        p.saved_scope_evidence(f[1], POLICY_SHA)


def test_loader_bounds_the_total_inventory_even_when_each_record_fits(tmp_path, monkeypatch):
    f = envelope_fixture(tmp_path)
    other = {**f[-1], "commit": "b"*40, "verified_remote_commit": "b"*40}
    save(f[1], p.SCOPE_RECORDS, f[-1]); save(f[1], p.SCOPE_RECORDS, other)
    monkeypatch.setattr(p, "MAX_BYTES", max(len(canonical(e)) for e in (f[-1], other)))
    with pytest.raises(ValueError, match="inventory"):
        p.saved_scope_evidence(f[1], POLICY_SHA)


def test_owned_cas_hardlinks_and_global_quota_writer_remain_supported(tmp_path, monkeypatch):
    f = envelope_fixture(tmp_path)
    policy = {"storage": {"version": "operational-storage-v2", "limit_bytes": 1024*1024},
              "namespaces": {"private_retention_bytes": 1024*1024}}
    managed = f[0] / "managed-state"
    storage = OperationalStorage(f[0] / "cache", policy, state=managed)
    for source in f[1].rglob("*.json.gz"):
        storage.write_bytes(managed / source.relative_to(f[1]), source.read_bytes())
    managed_f = (f[0], managed, *f[2:])
    publish(managed_f, storage=storage)  # Direct caller needs no outer quota scope.
    path = managed / p.SCOPE_RECORDS / (digest(f[-1]) + ".json.gz")
    assert path.stat().st_nlink >= 2
    storage.validate_reference(path)
    assert p.saved_scope_evidence(managed, POLICY_SHA) == {digest(f[-1]): f[-1]}
    # New scope must enter the same explicit quota writer before receipts.
    changed = deepcopy(f[-1]); changed["files"] = {}
    original_write = storage.write_bytes
    def quota_failure(destination, body, **kwargs):
        if Path(destination).parent.name == p.SCOPE_RECORDS:
            raise StorageQuotaError("fictional global reservation")
        return original_write(destination, body, **kwargs)
    monkeypatch.setattr(storage, "write_bytes", quota_failure)
    prior = {str(path): path.read_bytes() for path in managed.rglob("*.json.gz")}
    with pytest.raises(StorageQuotaError, match="global reservation"):
        publish((*managed_f[:-1], changed), storage=storage)
    assert prior == {str(path): path.read_bytes() for path in managed.rglob("*.json.gz")}


@pytest.mark.parametrize("failure", [None, "provisional", "final"])
def test_weekly_propagates_unchanged_exact_state_proxy_to_fit_and_replay(tmp_path, monkeypatch, failure):
    from nfl_lab import operational_sources
    policy = {"_policy_sha256": POLICY_SHA,
        "storage": {"version": "operational-storage-v2", "limit_bytes": 1024*1024},
        "namespaces": {"private_retention_bytes": 1024*1024},
        "operational_routing": {"weekly_reference_budget": {"max_supported_packages": 22, "max_wall_seconds": 1200}}}
    monkeypatch.setattr(operational_sources, "load_source_policy", lambda p: p)
    features = pd.DataFrame({"player_id": ["fictional"], "game_id": ["past-fictional"],
        "position": ["QB"], "kickoff_utc": pd.to_datetime(["2029-01-01"], utc=True),
        "outcome_available_utc": pd.to_datetime(["2029-01-08"], utc=True),
        "participation_state": ["played"], "pass_yd": [12.0]})
    document = {"asof_utc": "2030-01-01T00:00:00Z", "feature_sha256": "b"*64,
                "source_binding": {"fictional": True}, "operational_manifest": {"fictional": True}}
    monkeypatch.setattr(experiment, "load_operational_features", lambda *a: (features, document))
    monkeypatch.setattr(operational_models, "model_binding", lambda *a: {"fictional": "exact-binding"})
    monkeypatch.setattr(operational_models, "check_operational_storage", lambda *a, **kw: None)
    seen, partial = [], []
    def prediction(query):
        return pd.DataFrame({"mean": np.ones(len(query)), "scale": np.ones(len(query)),
            "p10": np.zeros(len(query)), "p50": np.ones(len(query)), "p90": np.ones(len(query))*2,
            "p_participation": np.full(len(query), np.nan), "fallback": ["fictional"]*len(query)})
    def fit(train, query, target, method, *, artifact_path, binding, storage):
        assert isinstance(storage, StateBoundStorage)
        assert storage.limit == 200*1024*1024 and binding == {"fictional": "exact-binding"}
        seen.append(storage)
        provisional = Path(artifact_path).parent / "provisional.json"
        body = {"stage": "provisional", "fictional": "x"*100}
        if failure == "provisional":
            storage.limit = sum(p.stat().st_size for p in storage.state.rglob("*") if p.is_file()) + len(
                (json.dumps(body, sort_keys=True, separators=(",", ":"))+"\n").encode()) - 1
        storage.atomic_json(provisional, body)
        partial.append(provisional)
        if failure == "final":
            storage.limit = sum(p.stat().st_size for p in storage.state.rglob("*") if p.is_file())
        storage.atomic_json(artifact_path, {"stage": "final"})
        return prediction(query)
    def replay(path, query, *, binding, storage):
        assert storage is seen[0]
        storage.validate_reference(path)
        seen.append(storage)
        return prediction(query)
    monkeypatch.setattr(operational_models, "fit_operational_reference", fit)
    monkeypatch.setattr(operational_models, "predict_operational_artifact", replay)
    monkeypatch.setattr("nfl_lab.models.fit_predict", lambda *a, **kw: pytest.fail("no learner fit permitted"))
    args = (tmp_path, tmp_path / "cache", tmp_path / "state", policy, ["recent"])
    if failure:
        with pytest.raises(StorageQuotaError, match="exact serialized"):
            experiment.run_reference_learning(*args)
        assert len(seen) == 1
        assert not list((tmp_path / "state/models").rglob("pass_yd-recent.json"))
        assert bool(partial) == (failure == "final")
        if partial: assert partial[0].exists()
        assert next(records(tmp_path / "state", "training"))["state"] == "FAILED"
    else:
        result = experiment.run_reference_learning(*args)
        assert result["package_count"] == 1 and len(seen) == 2
        assert result["new_accuracy_scores"] == 0 and result["promotion"] == "NONE"
