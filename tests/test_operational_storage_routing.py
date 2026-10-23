"""Fictional route checks; no NFL input, HTTP, model fitting or publication."""
import gzip
import hashlib
import importlib.util
import json
import multiprocessing
from pathlib import Path
import subprocess

import pytest

from nfl_lab import experiment, live, operational_models, state, website_baselines
from nfl_lab.operational_io import operational_io
from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError


def policy(limit=1024 * 1024):
    return {"storage": {"version": "operational-storage-v2", "limit_bytes": limit},
            "namespaces": {"private_retention_bytes": limit}, "_policy_sha256": "a" * 64}


def tool(name):
    path = Path(__file__).parents[1] / "tools" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_imported_state_save_seams_and_original_bytes(tmp_path):
    storage = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "state")
    original = state.save
    old = tmp_path / "state/old.bin"
    old.write_bytes(b"preserved original")
    with operational_io(storage):
        for module in (state, live, experiment, website_baselines):
            assert module.save is state.save
        key = live.save(storage.state_root, "health", {"fictional": "receipt"})
        path = storage.state_root / "health" / (key + ".json.gz")
        assert gzip.decompress(path.read_bytes()) == state.canonical({"fictional": "receipt"})
        storage.validate_reference(path)
    assert state.save is live.save is experiment.save is original
    assert old.read_bytes() == b"preserved original"


def test_state_200mib_guard_precedes_disk_write_and_quota_guard(tmp_path):
    storage = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "state")
    before = storage.snapshot()["physical_bytes"]
    with operational_io(storage):
        with pytest.raises(RuntimeError, match="durable evidence cap"):
            state.save(storage.state_root, "health", {"fictional": "receipt"}, max_bytes=1)
    assert storage.snapshot()["physical_bytes"] == before
    assert not list(storage.state_root.rglob("*.json.gz"))


def save_concurrently(cache, state_root, max_bytes, barrier, result, number):
    storage = OperationalStorage(cache, policy(), state=state_root)
    barrier.wait(timeout=10)
    try:
        with operational_io(storage):
            state.save(state_root, "health", {"fictional": str(number) * 1000}, max_bytes=max_bytes)
        result.put("saved")
    except RuntimeError as error:
        result.put(str(error))


def test_state_logical_limit_is_atomic_across_processes(tmp_path):
    storage = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "state")
    size = sum(p.stat().st_size for p in storage.state_root.rglob("*") if p.is_file())
    max_bytes = size + len(gzip.compress(state.canonical({"fictional": "0" * 1000}), mtime=0)) + 1
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(3)
    result = context.Queue()
    processes = [context.Process(target=save_concurrently,
        args=(storage.cache, storage.state_root, max_bytes, barrier, result, number)) for number in (0, 1)]
    for process in processes:
        process.start()
    barrier.wait(timeout=10)
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    messages = [result.get(timeout=2) for _ in processes]
    assert messages.count("saved") == 1
    assert sum("durable evidence cap" in message for message in messages) == 1
    assert len(list(state.records(storage.state_root, "health"))) == 1


def test_cli_failed_daily_quota_output_is_saved_before_nonzero_exit(tmp_path, monkeypatch):
    from nfl_lab import cli, operational_sources
    (tmp_path / "config").mkdir()
    (tmp_path / "config/research.json").write_text("{}")
    monkeypatch.setattr(operational_sources, "load_source_policy", lambda value: policy())
    monkeypatch.setattr(live, "daily", lambda *args, **kwargs: {"state": "PERMITTED_SOURCE_ISSUANCE_ABSTAINED"})
    monkeypatch.setattr("sys.argv", ["nfl-lab", "daily", "--root", str(tmp_path),
        "--source-policy", "config/fictional.json", "--output", "runs/operational-v2/daily-result.json"])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 1
    storage = OperationalStorage(tmp_path / "data", policy(), state=tmp_path / "state")
    report = tmp_path / "runs/operational-v2/daily-result.json"
    storage.validate_reference(report)
    assert json.loads(report.read_text())["state"] == "PERMITTED_SOURCE_ISSUANCE_ABSTAINED"


def test_live_download_uses_owned_v2_root_and_preserves_legacy(tmp_path, monkeypatch):
    from nfl_lab import data
    storage = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "state")
    legacy = storage.cache / "raw/live/fictional/state.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy must remain untouched")
    observed = []

    def download(raw, name, url):
        observed.append(raw)
        body = b'{"fictional":true}'
        partial = raw / (name + ".partial")
        with partial.open("wb") as sink:
            sink.write(body)
        partial.replace(raw / name)
        receipt = {"sha256": hashlib.sha256(body).hexdigest(), "retrieved_utc": "2030-01-01T00:00:00Z"}
        (raw / (name + ".receipt.json")).write_text(json.dumps(receipt))
        return receipt

    monkeypatch.setattr(data, "_download", download)
    with operational_io(storage):
        result, receipt = live.fetch(storage.cache, "state", "fictional:no-network", day="fictional")
    assert observed == [storage.live_root / "fictional"]
    assert result == {"fictional": True}
    storage.validate_reference(observed[0] / "state.json", receipt["sha256"])
    assert legacy.read_bytes() == b"legacy must remain untouched"


def test_model_serializer_override_restores_on_quota_failure(tmp_path, monkeypatch):
    from nfl_lab import model_artifacts, models
    from test_models import histories
    train, query = histories(8)
    storage = OperationalStorage(tmp_path / "cache", policy(8192), state=tmp_path / "state")
    manifest = {"adapter_version": "permitted-operational-nfl-history-v2", "policy_sha256": "a" * 64,
                "snapshot_sha256": "b" * 64, "training_view_sha256": "c" * 64, "namespace": "fictional"}
    binding = operational_models.model_binding(policy(8192), manifest, train, query, "d" * 64)
    original = model_artifacts._atomic_json

    def fake_fit(train, query, target, method, *, artifact_path):
        model_artifacts._atomic_json(artifact_path, {"fictional": "x" * 9000}, replace=False)
        pytest.fail("oversized provisional model was written")

    monkeypatch.setattr(models, "fit_predict", fake_fit)
    before = storage.snapshot()["physical_bytes"]
    with pytest.raises(StorageQuotaError):
        operational_models.fit_operational_reference(train, query, "pass_yd", "recent",
            artifact_path=storage.model_root / "reference.json", binding=binding, storage=storage)
    assert model_artifacts._atomic_json is original
    assert storage.snapshot()["physical_bytes"] == before
    assert not list(storage.model_root.rglob("*.json"))


def test_reviewed_publication_exact_bytes_aliases_and_control_omission(tmp_path):
    publish = tool("persist_state")
    storage = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "state")
    with operational_io(storage):
        state.save(storage.state_root, "health", {"fictional": "reviewed aggregate"})
    files = publish.publication_files(storage.state_root)
    private = storage.state_root / "models/private-unreviewed.json"
    storage.write_bytes(private, b"fictional private weights")
    manifest = tmp_path / "review.json"
    manifest.write_text(json.dumps({"schema_version": publish.PUBLICATION_SCHEMA, "review_state": "ACCEPTED",
                                   "policy_sha256": "a" * 64, "files": files}))
    assert publish.reviewed_publication(storage.state_root, manifest, "a" * 64) == files
    destination = storage.live_root / "publication-worktrees/fictional/state"
    before = storage.snapshot()["physical_bytes"]
    publish.copy_state(storage.state_root, destination, storage, files=files)
    assert not (destination / "models/private-unreviewed.json").exists()
    assert not (destination / ".operational-storage-owner").exists()
    assert not (destination / ".writer.lock").exists()
    for relative in files:
        assert (destination / relative).read_bytes() == (storage.state_root / relative).read_bytes()
        assert (destination / relative).stat().st_ino == (storage.state_root / relative).stat().st_ino
    assert storage.snapshot()["physical_bytes"] == before
    with pytest.raises(RuntimeError, match="pending.*content-review"):
        publish.reviewed_publication(storage.state_root, None, "a" * 64)
    changed = json.loads(manifest.read_text())
    changed["files"] = {"../escape": "0" * 64}
    manifest.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="path/hash"):
        publish.reviewed_publication(storage.state_root, manifest, "a" * 64)


def test_publication_copy_refuses_unreserved_new_bytes(tmp_path):
    publish = tool("persist_state")
    storage = OperationalStorage(tmp_path / "cache", policy(8192), state=tmp_path / "state")
    original = storage.state_root / "preserved.bin"
    original.write_bytes(b"x" * 4000)
    before = storage.snapshot()["physical_bytes"]
    with pytest.raises(StorageQuotaError):
        publish.copy_state(storage.state_root, storage.live_root / "publication/state", storage,
                           files=publish.publication_files(storage.state_root))
    assert original.read_bytes() == b"x" * 4000
    assert storage.snapshot()["physical_bytes"] == before


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def local_history(root, *, symlink=False):
    root.mkdir()
    git(root, "init", "-q")
    state_dir = root / "state/health"
    state_dir.mkdir(parents=True)
    body = gzip.compress(b'{"fictional":"prior aggregate"}', mtime=0)
    (state_dir / "fictional.json.gz").write_bytes(body)
    if symlink:
        (state_dir / "unsafe").symlink_to("/tmp/outside")
    git(root, "add", "state")
    git(root, "-c", "user.name=Fictional", "-c", "user.email=fictional@example.invalid",
        "commit", "-qm", "Fictional local evidence")
    git(root, "update-ref", "refs/remotes/origin/lab-state", "HEAD")
    return body


def test_local_git_restore_is_bounded_owned_and_idempotent(tmp_path):
    restore = tool("restore_state")
    root = tmp_path / "repo"
    body = local_history(root)
    storage = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "restored-state")
    first = restore.restore_state(root, "refs/remotes/origin/lab-state", storage)
    path = storage.state_root / "health/fictional.json.gz"
    assert path.read_bytes() == body
    storage.validate_reference(path)
    second = restore.restore_state(root, "refs/remotes/origin/lab-state", storage)
    assert second == first
    small = OperationalStorage(tmp_path / "small-cache", policy(), state=tmp_path / "small-state")
    before = small.snapshot()["physical_bytes"]
    with pytest.raises(RuntimeError, match="restore limit|durable evidence cap"):
        restore.restore_state(root, "refs/remotes/origin/lab-state", small, max_bytes=1)
    assert small.snapshot()["physical_bytes"] == before
    existing = OperationalStorage(tmp_path / "existing-cache", policy(), state=tmp_path / "existing-state")
    original = existing.state_root / "health/fictional.json.gz"
    original.parent.mkdir()
    original.write_bytes(body)
    info = original.stat()
    restore.restore_state(root, "refs/remotes/origin/lab-state", existing)
    assert original.stat().st_ino == info.st_ino
    assert original.stat().st_mode == info.st_mode


def test_local_git_restore_rejects_symlink_before_any_file_body(tmp_path):
    restore = tool("restore_state")
    root = tmp_path / "repo"
    local_history(root, symlink=True)
    storage = OperationalStorage(tmp_path / "cache", policy(), state=tmp_path / "restored-state")
    before = storage.snapshot()["physical_bytes"]
    with pytest.raises(ValueError, match="nonregular"):
        restore.restore_state(root, "refs/remotes/origin/lab-state", storage)
    assert storage.snapshot()["physical_bytes"] == before


def test_publication_subset_preserves_omitted_remote_index_and_rejects_overwrite(tmp_path):
    publish = tool("persist_state")
    root = tmp_path / "repo"
    old = local_history(root)
    new = root / "state/health/new[1].json.gz"
    new.write_bytes(gzip.compress(b'{"fictional":"new reviewed aggregate"}', mtime=0))
    files = {"health/new[1].json.gz": hashlib.sha256(new.read_bytes()).hexdigest()}
    publish.validate_existing_public(root, "HEAD", files)
    (root / "state/health/fictional.json.gz").unlink()
    publish.stage_reviewed(root, files)
    staged = git(root, "ls-files", "-z").split(b"\0")
    assert b"state/health/fictional.json.gz" in staged
    assert b"state/health/new[1].json.gz" in staged
    assert git(root, "show", ":state/health/fictional.json.gz") == old
    with pytest.raises(ValueError, match="overwrite existing public"):
        publish.validate_existing_public(root, "HEAD", {"health/fictional.json.gz": "0" * 64})
