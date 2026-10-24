"""Fictional byte/dataframe fixtures only; no NFL source or model execution."""
import fcntl
import hashlib
import io
import multiprocessing
import os
from pathlib import Path

import pandas as pd
import pytest

from nfl_lab.operational_storage import OperationalStorage, StorageIntegrityError, StorageQuotaError


def policy(limit=64 * 1024):
    return {"storage": {"version": "operational-storage-v2", "limit_bytes": limit},
            "namespaces": {"private_retention_bytes": limit}}


def store(tmp_path, limit=64 * 1024, **kwargs):
    return OperationalStorage(tmp_path / "cache", policy(limit), **kwargs)


def test_explicit_v2_policy_required(tmp_path):
    with pytest.raises(StorageIntegrityError):
        OperationalStorage(tmp_path / "cache", {"namespaces": {"private_retention_bytes": 123}})


def test_unique_inode_and_logical_accounting_and_immutable_dedup(tmp_path):
    storage = store(tmp_path)
    initial = storage.snapshot()
    a, b = storage.source_root / "first", storage.feature_root / "second"
    storage.write_bytes(a, b"fictional-body")
    one = storage.snapshot()
    storage.write_bytes(b, b"fictional-body")
    two = storage.snapshot()
    assert a.stat().st_ino == b.stat().st_ino
    assert one["physical_bytes"] == two["physical_bytes"] == initial["physical_bytes"] + 14
    assert two["logical_referenced_bytes"] == one["logical_referenced_bytes"] + 14
    assert two["logical_referenced_bytes"] > two["physical_bytes"]
    assert not a.stat().st_mode & 0o222
    assert storage.validate_reference(a)["sha256"] == hashlib.sha256(a.read_bytes()).hexdigest()


def test_legacy_import_copies_and_preserves_mutable_original(tmp_path):
    storage = store(tmp_path)
    original = tmp_path / "legacy"
    original.write_bytes(b"fictional-legacy")
    before = original.stat()
    destination = storage.source_root / "source"
    result = storage.import_file(original, destination, hashlib.sha256(original.read_bytes()).hexdigest())
    assert original.stat().st_ino == before.st_ino
    assert original.stat().st_mode == before.st_mode
    assert original.stat().st_nlink == 1
    assert original.stat().st_ino != destination.stat().st_ino
    original.write_bytes(b"changed-old-cache")
    assert destination.read_bytes() == b"fictional-legacy"
    assert storage.validate_reference(destination) == result


def test_authentic_receipt_clocks_are_separate_bytes(tmp_path):
    storage = store(tmp_path)
    storage.atomic_json(storage.source_root / "receipt-a", {"clock": "earlier"})
    storage.atomic_json(storage.source_root / "receipt-b", {"clock": "later"})
    assert (storage.source_root / "receipt-a").stat().st_ino != (storage.source_root / "receipt-b").stat().st_ino


def test_prewrite_rejection_has_no_body_or_temporary(tmp_path):
    storage = store(tmp_path, 4096)
    before = storage.snapshot()
    target = storage.source_root / "too-large"
    with pytest.raises(StorageQuotaError, match="before write"):
        storage.write_bytes(target, b"x" * (4096 - before["physical_bytes"] + 1))
    assert not target.exists()
    assert storage.snapshot() == before
    assert not list(storage.control_root.glob(".incoming-*"))


def test_atomic_replacement_reserves_old_plus_incoming_and_preserves_old(tmp_path):
    storage = store(tmp_path, 4096)
    stage = storage.source_root / ".staging-fixture"
    target = stage / "history"
    storage.write_bytes(target, b"a" * 100)
    remaining = 4096 - storage.snapshot()["physical_bytes"]
    storage.write_bytes(stage / "filler", b"f" * (remaining - 40))
    before = storage.snapshot()
    with storage.capture_writes(roots=[stage]), pytest.raises(StorageQuotaError):
        target.write_bytes(b"b" * 41)
    assert target.read_bytes() == b"a" * 100
    assert storage.snapshot() == before
    with storage.capture_writes(roots=[stage]):
        target.write_bytes(b"b" * 40)
    assert storage.snapshot()["physical_bytes"] == 4096
    assert any(path.read_bytes() == b"a" * 100 for path in storage.blob_root.iterdir())
    with pytest.raises(StorageQuotaError):
        storage.atomic_json(stage / "FAILURE.json", {"failure": "cannot fit"})
    assert not (stage / "FAILURE.json").exists()


def test_published_reference_cannot_be_replaced_without_mutable_scope(tmp_path):
    storage = store(tmp_path)
    target = storage.source_root / "published"
    storage.write_bytes(target, b"old")
    with pytest.raises(FileExistsError):
        storage.write_bytes(target, b"new")
    with pytest.raises(StorageIntegrityError, match="mutable"):
        storage.write_bytes(target, b"new", replace=True)
    with storage.capture_writes(), pytest.raises(StorageIntegrityError):
        target.write_bytes(b"new")
    assert target.read_bytes() == b"old"


def test_state_all_bytes_registered_and_discovered_without_state_argument(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    original = state / "old-evidence"
    original.write_bytes(b"preexisting")
    old = original.stat()
    storage = store(tmp_path, state=state)
    storage.write_bytes(storage.model_root / "fictional-model-json", b"fictional")
    restarted = store(tmp_path)
    assert str(state) in restarted.snapshot()["roots"]
    assert restarted.snapshot()["physical_bytes"] == storage.snapshot()["physical_bytes"]
    assert original.stat().st_ino == old.st_ino and original.stat().st_mode == old.st_mode
    with pytest.raises(StorageIntegrityError):
        restarted.import_file(original, original)
    assert original.stat().st_ino == old.st_ino and original.stat().st_mode == old.st_mode


def test_register_existing_root_counts_bytes_before_registry_write(tmp_path):
    storage = store(tmp_path, 4096)
    run = tmp_path / "run"
    run.mkdir()
    original = run / "too-large"
    original.write_bytes(b"z" * 4096)
    before = storage.snapshot()
    with pytest.raises(StorageQuotaError):
        storage.register_root(run)
    assert original.read_bytes() == b"z" * 4096
    assert storage.snapshot() == before
    assert not (run / ".operational-storage-owner").exists()


@pytest.mark.parametrize("relationship", ["same", "parent", "child"])
def test_conflicting_root_owners_rejected_for_all_overlap_relationships(tmp_path, relationship):
    state = tmp_path / "shared" / "nested"
    first = OperationalStorage(tmp_path / "cache-a", policy(), state=state)
    other = state if relationship == "same" else (state.parent if relationship == "parent" else state / "child")
    with pytest.raises(StorageIntegrityError, match="owner|belongs"):
        OperationalStorage(tmp_path / "cache-b", policy(), state=other)
    first.snapshot()


def test_registered_runs_and_baseline_bytes_persist(tmp_path):
    storage = store(tmp_path)
    run = storage.register_root(tmp_path / "runs")
    baseline = storage.register_root(tmp_path / "baseline")
    storage.write_bytes(run / "receipt", b"run")
    storage.write_bytes(baseline / "fixture", b"baseline")
    restarted = store(tmp_path)
    assert restarted.snapshot() == storage.snapshot()
    assert restarted.validate_reference(run / "receipt")["bytes"] == 3


def test_partial_io_failure_is_retained_and_counted(tmp_path, monkeypatch):
    storage = store(tmp_path)
    before = storage.snapshot()["physical_bytes"]
    def fail(descriptor, body):
        os.write(descriptor, b"part")
        raise OSError("fictional disk interruption")
    monkeypatch.setattr(storage, "_write_all", fail)
    with pytest.raises(OSError):
        storage.write_bytes(storage.source_root / "never-published", b"incoming")
    assert storage.snapshot()["physical_bytes"] == before + 4
    assert not (storage.source_root / "never-published").exists()
    assert len(list(storage.control_root.glob(".incoming-*"))) == 1
    assert store(tmp_path).snapshot()["physical_bytes"] == before + 4


def test_failed_atomic_alias_publication_retains_complete_owned_bytes(tmp_path, monkeypatch):
    storage = store(tmp_path)
    target = storage.source_root / "never-published"
    before = storage.snapshot()["physical_bytes"]
    original = os.replace
    def fail(source, destination, *args, **kwargs):
        if Path(source).name.startswith(".alias-"):
            raise OSError("fictional publication interruption")
        return original(source, destination, *args, **kwargs)
    monkeypatch.setattr(os, "replace", fail)
    # A new reference uses no-replace link publication; replacement publication
    # is exercised by the explicit mutable staging route.
    with storage.capture_writes(roots=[storage.source_root]), pytest.raises(OSError):
        target.write_bytes(b"complete-fictional-body")
    assert not target.exists()
    assert storage.snapshot()["physical_bytes"] == before + len(b"complete-fictional-body")
    assert len(list(storage.source_root.glob(".alias-*"))) == 1
    restarted = store(tmp_path)
    restarted.write_bytes(target, b"complete-fictional-body")
    assert target.read_bytes() == b"complete-fictional-body"
    assert restarted.snapshot()["physical_bytes"] == storage.snapshot()["physical_bytes"]


@pytest.mark.parametrize("kind", ["ancestor", "target", "inside"])
def test_symlinks_fail_closed(tmp_path, kind):
    storage = store(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    if kind == "ancestor":
        link = storage.source_root / "linked"
        link.symlink_to(external, target_is_directory=True)
        target = link / "escaped"
    elif kind == "target":
        (external / "body").write_bytes(b"external")
        target = storage.source_root / "target"
        target.symlink_to(external / "body")
    else:
        (storage.source_root / "inside").symlink_to(external, target_is_directory=True)
        target = storage.feature_root / "unrelated"
    with pytest.raises(StorageIntegrityError):
        storage.write_bytes(target, b"blocked")
    assert not (external / "escaped").exists()


def test_explicit_and_capture_parent_escape_rejected(tmp_path):
    storage = store(tmp_path)
    with pytest.raises(StorageIntegrityError):
        storage.write_bytes(tmp_path / "outside", b"blocked")
    with storage.capture_writes(roots=[storage.source_root]), pytest.raises(StorageIntegrityError):
        (storage.source_root / ".." / "escape").write_bytes(b"blocked")
    assert not (storage.cache / "escape").exists()
    outside = tmp_path / "outside-directory"
    outside.mkdir()
    reverse = outside / ".." / "cache" / "operational-source-v2" / "escaped"
    with storage.capture_writes(), pytest.raises(StorageIntegrityError):
        reverse.write_bytes(b"blocked")
    assert not (storage.source_root / "escaped").exists()


def test_capture_controls_and_outside_active_scope_fail_closed(tmp_path):
    storage = store(tmp_path)
    with storage.capture_writes(roots=[storage.source_root]):
        assert storage.registry_path.read_bytes()
        with pytest.raises(StorageIntegrityError):
            storage.registry_path.write_bytes(b"blocked")
        with pytest.raises(StorageIntegrityError):
            (storage.feature_root / "outside-scope").write_bytes(b"blocked")


def test_external_hardlink_and_foreign_hardlink_rejected(tmp_path):
    storage = store(tmp_path)
    target = storage.source_root / "owned"
    storage.write_bytes(target, b"owned")
    external = tmp_path / "external-link"
    os.link(target, external)
    with pytest.raises(StorageIntegrityError, match="hardlink"):
        storage.write_bytes(storage.feature_root / "blocked", b"never-written")
    external.unlink()
    legacy = tmp_path / "legacy"
    legacy.write_bytes(b"foreign")
    os.link(legacy, storage.source_root / "foreign")
    with pytest.raises(StorageIntegrityError, match="hardlink"):
        storage.snapshot()


def test_blob_corruption_and_readonly_unowned_reference_rejected(tmp_path):
    storage = store(tmp_path)
    target = storage.source_root / "owned"
    storage.write_bytes(target, b"valid")
    os.chmod(target, 0o644)
    target.write_bytes(b"wrong")
    os.chmod(target, 0o444)
    with pytest.raises(StorageIntegrityError, match="content changed"):
        storage.snapshot()
    second = OperationalStorage(tmp_path / "other-cache", policy())
    unowned = second.source_root / "forged"
    unowned.write_bytes(b"readonly-forged")
    unowned.chmod(0o444)
    with pytest.raises((StorageIntegrityError, FileNotFoundError)):
        second.validate_reference(unowned)


def test_registry_corruption_and_global_lock_replacement_rejected(tmp_path):
    storage = store(tmp_path)
    original = storage.registry_path.read_bytes()
    storage.registry_path.write_bytes(b"not-json")
    with pytest.raises(StorageIntegrityError):
        storage.snapshot()
    storage.registry_path.write_bytes(original)
    old_lock = storage.lock_path.with_name(".retained-original-lock")
    storage.lock_path.rename(old_lock)
    with pytest.raises(StorageIntegrityError):
        storage.snapshot()
    with pytest.raises(StorageIntegrityError):
        store(tmp_path)


@pytest.mark.parametrize("operation", ["snapshot", "register"])
def test_unreadable_descendants_cannot_be_omitted_from_accounting(tmp_path, monkeypatch, operation):
    storage = store(tmp_path)
    root = storage.source_root if operation == "snapshot" else tmp_path / "new-run"
    blocked = root / "unreadable"
    blocked.mkdir(parents=True)
    (blocked / "retained").write_bytes(b"must-always-be-counted")
    original = os.scandir
    def unreadable(path):
        if Path(path) == blocked:
            raise PermissionError("fictional unreadable managed descendant")
        return original(path)
    monkeypatch.setattr(os, "scandir", unreadable)
    with pytest.raises(StorageIntegrityError, match="cannot inspect every"):
        storage.snapshot() if operation == "snapshot" else storage.register_root(root)


def test_capture_path_and_dataframe_serialization_exact_and_scoped(tmp_path):
    storage = store(tmp_path)
    frame = pd.DataFrame({"fictional": [1, None], "label": ["alpha", "beta"]})
    parquet = frame.to_parquet(index=False)
    csv = frame.to_csv(index=False).encode()
    outside = tmp_path / "outside"
    stage = storage.source_root / ".staging-fictional"
    with storage.capture_writes(roots=[stage]):
        (stage / "text").write_text("fictional\n")
        frame.to_parquet(stage / "frame.parquet", index=False)
        frame.to_csv(stage / "frame.csv", index=False)
        outside.write_bytes(b"outside-capture")
        assert frame.to_parquet(index=False) == parquet
    assert (stage / "frame.parquet").read_bytes() == parquet
    assert (stage / "frame.csv").read_bytes() == csv
    storage.validate_reference(stage / "text")
    assert outside.read_bytes() == b"outside-capture"


def test_capture_restores_after_exception_and_nesting(tmp_path):
    storage = store(tmp_path)
    original = Path.write_bytes
    with pytest.raises(RuntimeError), storage.capture_writes():
        with storage.capture_writes(roots=[storage.source_root]):
            (storage.source_root / "one").write_bytes(b"one")
        raise RuntimeError("fictional helper failure")
    assert Path.write_bytes is original


def test_nested_mutable_scope_keeps_outer_registered_writes_captured(tmp_path):
    storage = store(tmp_path)
    stage = storage.source_root / ".staging-fixture"
    with storage.capture_writes():
        with storage.capture_writes(roots=[stage]):
            (stage / "intermediate").write_bytes(b"one")
            (stage / "intermediate").write_bytes(b"two")
            (storage.source_root / "request-binding").write_bytes(b"immutable")
        with pytest.raises(StorageIntegrityError):
            (storage.source_root / "request-binding").write_bytes(b"changed")
    storage.validate_reference(storage.source_root / "request-binding")


@pytest.mark.parametrize("mode", ["a", "ab", "x", "xb", "r+", "w+", "wb+", "w"])
def test_unsupported_write_modes_fail_closed(tmp_path, mode):
    storage = store(tmp_path)
    with storage.capture_writes(), pytest.raises(StorageIntegrityError):
        (storage.source_root / "blocked").open(mode)
    assert not (storage.source_root / "blocked").exists()


def test_zero_state_writer_lock_cannot_receive_bytes(tmp_path):
    storage = store(tmp_path, state=tmp_path / "state")
    path = storage.state_root / ".writer.lock"
    with storage.capture_writes(), path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(StorageIntegrityError):
            lock.write("not-empty")
        with pytest.raises(OSError):
            os.write(lock.fileno(), b"not-empty")
    assert path.stat().st_size == 0


def test_stream_chunk_preflight_and_owned_promotion(tmp_path):
    storage = store(tmp_path, 4096)
    path = storage.live_root / "body.partial"
    remaining = 4096 - storage.snapshot()["physical_bytes"]
    with storage.capture_writes(roots=[storage.live_root]), path.open("wb") as stream:
        assert stream.write(b"a" * remaining) == remaining
        with pytest.raises(StorageQuotaError):
            stream.write(b"b")
        with pytest.raises(StorageIntegrityError):
            stream.fileno()
    assert storage.snapshot()["physical_bytes"] == 4096
    final = path.with_name("body")
    path.replace(final)
    before = final.stat().st_ino
    result = storage.import_file(final, final)
    assert final.stat().st_ino == before
    assert storage.validate_reference(final) == result
    assert storage.snapshot()["physical_bytes"] == 4096


def test_stream_cannot_truncate_or_write_after_link_manipulation(tmp_path):
    storage = store(tmp_path)
    target = storage.source_root / "owned"
    storage.write_bytes(target, b"owned")
    with storage.capture_writes(), pytest.raises(StorageIntegrityError):
        target.open("wb")
    partial = storage.source_root / "partial"
    with storage.capture_writes(), partial.open("wb") as stream:
        os.link(partial, storage.feature_root / "foreign-alias")
        with pytest.raises(StorageIntegrityError):
            stream.write(b"blocked")
    assert partial.stat().st_size == 0


def test_dataframe_filelike_bypass_rejected(tmp_path):
    storage = store(tmp_path)
    target = storage.source_root / "filelike"
    with target.open("wb") as stream:
        with storage.capture_writes(), pytest.raises(StorageIntegrityError):
            pd.DataFrame({"fictional": [1]}).to_parquet(stream)
    assert target.stat().st_size == 0


def test_same_cache_instances_share_reentrant_transaction(tmp_path):
    first = store(tmp_path)
    second = store(tmp_path)
    with first.transaction():
        with second.transaction():
            second.write_bytes(second.source_root / "nested", b"nested")
    assert first.snapshot() == second.snapshot()


def _concurrent_writer(cache, cap, name, ready, begin, output):
    try:
        storage = OperationalStorage(cache, policy(cap))
        ready.put(name)
        begin.wait(10)
        storage.write_bytes(storage.source_root / name, name.encode() * 300)
        output.put("written")
    except StorageQuotaError:
        output.put("rejected")
    except Exception as exc:
        output.put(type(exc).__name__ + ": " + str(exc))


def test_concurrent_processes_cannot_double_spend(tmp_path):
    storage = store(tmp_path, 4096)
    remaining = 4096 - storage.snapshot()["physical_bytes"]
    storage.write_bytes(storage.source_root / "filler", b"f" * (remaining - 400))
    context = multiprocessing.get_context("fork")
    ready, output, begin = context.Queue(), context.Queue(), context.Event()
    processes = [context.Process(target=_concurrent_writer,
                                args=(storage.cache, 4096, name, ready, begin, output)) for name in ("a", "b")]
    for process in processes:
        process.start()
    assert {ready.get(timeout=10), ready.get(timeout=10)} == {"a", "b"}
    begin.set()
    results = [output.get(timeout=10), output.get(timeout=10)]
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    assert sorted(results) == ["rejected", "written"]
    assert storage.snapshot()["physical_bytes"] == 3996
