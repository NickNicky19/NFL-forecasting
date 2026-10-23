"""Fictional bytes and temporary storage only; no NFL inputs or models."""
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import threading

import pytest

from nfl_lab import owned_reference_batch as batch
from nfl_lab.operational_storage import OperationalStorage, StorageIntegrityError, StorageQuotaError


def policy(limit=65536):
    return {"storage": {"version": "operational-storage-v2", "limit_bytes": limit}, "namespaces": {"private_retention_bytes": limit}}


def fictional(tmp_path, n=4):
    storage = OperationalStorage(tmp_path / "cache", policy())
    bindings = {}
    for i in range(n):
        path = storage.source_root / f"fictional-{i}"
        body = f"fictional-body-{i % 2}".encode()
        storage.write_bytes(path, body)
        bindings[str(path)] = hashlib.sha256(body).hexdigest()
    return storage, bindings


def test_exact_equivalence_two_whole_scans_and_no_inner_validate(tmp_path, monkeypatch):
    storage, bindings = fictional(tmp_path, 7)
    expected = {path: storage.validate_reference(path, sha) for path, sha in bindings.items()}
    snapshot = storage.snapshot()
    scan, refresh = storage._scan, storage._refresh
    events = []
    def counted_scan():
        assert storage._local.depth > 0 and storage._local.lock_fd is not None
        events.append("scan")
        return scan()
    def counted_refresh():
        assert storage._local.depth > 0
        events.append("refresh")
        return refresh()
    def forbidden(*args, **kwargs):
        raise AssertionError("per-reference public validator would repeat scans")
    monkeypatch.setattr(storage, "_scan", counted_scan)
    monkeypatch.setattr(storage, "_refresh", counted_refresh)
    monkeypatch.setattr(storage, "validate_reference", forbidden)
    references, receipt = batch.validate_owned_references(storage, bindings)
    assert references == expected
    assert events == ["refresh", "scan", "refresh", "scan"]
    assert receipt["entry"] == receipt["exit"] == snapshot
    assert receipt["validated_references"] == 7 and receipt["full_scan_calls"] == 2
    assert storage._local.depth == 0
    json.dumps(receipt, allow_nan=False)


@pytest.mark.parametrize("bindings", [None, {}, [], [("/fictional", "a" * 64)], {"relative": "a" * 64}, {"/fictional": None}, {"/fictional": "A" * 64}, {"/fictional": "a" * 63}, {"/fictional": "g" * 64}])
def test_malformed_bindings_rejected(tmp_path, bindings):
    storage, _ = fictional(tmp_path)
    with pytest.raises(StorageIntegrityError):
        batch.validate_owned_references(storage, bindings)


def test_duplicate_canonical_names_and_unsafe_paths_rejected(tmp_path):
    storage, bindings = fictional(tmp_path)
    path, sha = next(iter(bindings.items()))
    for bad in [{path: sha, Path(path): sha}, {str(Path(path).parent / ".." / Path(path).parent.name / Path(path).name): sha}, {str(tmp_path / "foreign"): sha}, {str(storage.blob_root / sha): sha}]:
        with pytest.raises(StorageIntegrityError):
            batch.validate_owned_references(storage, bad)


@pytest.mark.parametrize("damage", ["wrong_hash", "writable", "foreign_copy", "symlink", "external_hardlink", "corrupt_blob", "nonregular"])
def test_same_rejection_as_original_for_integrity_failures(tmp_path, damage):
    storage, bindings = fictional(tmp_path)
    raw_path, sha = next(iter(bindings.items()))
    path = Path(raw_path)
    if damage == "wrong_hash":
        sha = "0" * 64
    elif damage == "writable":
        path.chmod(0o644)
    elif damage == "foreign_copy":
        body = path.read_bytes()
        path.unlink()
        path.write_bytes(body)
        path.chmod(0o444)
    elif damage == "symlink":
        path.unlink()
        path.symlink_to(storage.blob_root / sha)
    elif damage == "external_hardlink":
        os.link(path, tmp_path / "unaccounted-link")
    elif damage == "corrupt_blob":
        path.chmod(0o644)
        path.write_bytes(b"fictional-corruption")
        path.chmod(0o444)
    elif damage == "nonregular":
        path.unlink()
        os.mkfifo(path)
    with pytest.raises((StorageIntegrityError, OSError)):
        storage.validate_reference(path, sha)
    with pytest.raises((StorageIntegrityError, OSError)):
        batch.validate_owned_references(storage, {path: sha})


def test_exit_scan_failure_returns_no_success(tmp_path, monkeypatch):
    storage, bindings = fictional(tmp_path)
    scan = storage._scan
    calls = []
    def fail_exit():
        calls.append(1)
        if len(calls) == 2:
            raise StorageIntegrityError("fictional exit scan failure")
        return scan()
    monkeypatch.setattr(storage, "_scan", fail_exit)
    with pytest.raises(StorageIntegrityError, match="exit scan failure"):
        batch.validate_owned_references(storage, bindings)
    assert len(calls) == 2 and storage._local.depth == 0


def test_failed_reference_still_runs_exit_scan_and_releases_lock(tmp_path, monkeypatch):
    storage, bindings = fictional(tmp_path)
    bindings[next(iter(bindings))] = "0" * 64
    scan = storage._scan
    calls = []
    def counted():
        calls.append(1)
        return scan()
    monkeypatch.setattr(storage, "_scan", counted)
    with pytest.raises(StorageIntegrityError, match="hash mismatch"):
        batch.validate_owned_references(storage, bindings)
    assert len(calls) == 2 and storage._local.depth == 0


def test_quota_and_scan_error_guards_preserved(tmp_path, monkeypatch):
    storage, bindings = fictional(tmp_path)
    filler = storage.source_root / "unmanaged-incoming"
    filler.write_bytes(b"x" * storage.limit_bytes)
    with pytest.raises(StorageQuotaError):
        batch.validate_owned_references(storage, bindings)
    filler.unlink()
    def walk_failure(*args, **kwargs):
        kwargs["onerror"](OSError("fictional inaccessible directory"))
        return iter(())
    monkeypatch.setattr(os, "walk", walk_failure)
    with pytest.raises(StorageIntegrityError, match="cannot inspect"):
        batch.validate_owned_references(storage, bindings)


def _attempt_flock(lock_path, connection):
    with open(lock_path, "r+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            connection.send("excluded")
        else:
            connection.send("unexpectedly_acquired")
            fcntl.flock(stream, fcntl.LOCK_UN)
    connection.close()


def test_global_process_flock_held_during_every_reference_and_exit(tmp_path, monkeypatch):
    storage, bindings = fictional(tmp_path, 2)
    digest = batch._digest_file
    probes = []
    def checked_digest(path):
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=_attempt_flock, args=(str(storage.lock_path), child))
        process.start()
        child.close()
        try:
            assert parent.poll(5), "fictional flock probe timeout"
            probes.append(parent.recv())
            process.join(5)
            assert process.exitcode == 0
        finally:
            parent.close()
            if process.is_alive():
                process.terminate()
                process.join(5)
        return digest(path)
    monkeypatch.setattr(batch, "_digest_file", checked_digest)
    batch.validate_owned_references(storage, bindings)
    assert probes == ["excluded", "excluded"]


def test_concurrent_storage_writer_waits_until_batch_unlocks(tmp_path, monkeypatch):
    storage, bindings = fictional(tmp_path, 1)
    other = OperationalStorage(storage.cache, policy())
    entered, finished = threading.Event(), threading.Event()
    errors = []
    destination = storage.feature_root / "fictional-concurrent"
    def writer():
        entered.set()
        try:
            other.write_bytes(destination, b"fictional-writer")
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()
    digest = batch._digest_file
    worker = None
    def checked_digest(path):
        nonlocal worker
        worker = threading.Thread(target=writer)
        worker.start()
        assert entered.wait(2)
        assert not finished.wait(.03)
        assert not destination.exists()
        return digest(path)
    monkeypatch.setattr(batch, "_digest_file", checked_digest)
    batch.validate_owned_references(storage, bindings)
    assert finished.wait(5)
    worker.join(5)
    assert not errors and destination.read_bytes() == b"fictional-writer"
