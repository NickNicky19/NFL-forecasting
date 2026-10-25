"""Fictional local Git/state only; no HTTP, acquisition, models or dispatch."""
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_lab import cli, publication_scope as p
from nfl_lab.state import canonical, digest, records, save

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def git(root, *args):
    return p._git(root, *args).decode().strip()


def setup_repo(tmp_path):
    root = tmp_path / "repo"; root.mkdir()
    git(root, "init", "-b", "main")
    state = root / "state"
    one = save(state, "forecasts", {"rows": [{"kickoff_utc": (NOW + timedelta(hours=1)).isoformat()}]})
    two = save(state, "forecasts", {"rows": [{"kickoff_utc": NOW.isoformat()}]})
    web = save(state, "website_bindings", {"lab_batch": one, "rows": [
        {"kickoff_utc": (NOW + timedelta(hours=1)).isoformat()}, {"kickoff_utc": NOW.isoformat()}]})
    health = save(state, "health", {"state": "FICTIONAL"})
    git(root, "add", "state")
    git(root, "-c", "user.name=fictional", "-c", "user.email=test@example.invalid", "commit", "-m", "fictional state")
    return root, state, git(root, "rev-parse", "HEAD"), one, two, web, health


def scope(root, state, commit, *names, policy=None):
    files = {name: hashlib.sha256((state / name).read_bytes()).hexdigest() for name in names}
    return p.scope_document(commit, files, verified_remote_commit=commit, policy_sha256=policy)


def execute(root, state, commit, envelope, **kwargs):
    return p.record_scoped_publication(root, state, commit=commit, scope=envelope, observed=NOW, **kwargs)


def test_only_exact_selected_batches_get_claims_and_old_receipts_stay_identical(tmp_path):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    old = save(state, "publication", {"batch": one, "commit": "0" * 40,
               "observed_remote_readback_at": (NOW-timedelta(days=5)).isoformat()})
    oldpath = state / "publication" / (old + ".json.gz"); original = oldpath.read_bytes()
    oldweb = save(state, "website_publication", {"snapshot": web, "commit": "0" * 40,
                  "observed_remote_readback_at": (NOW-timedelta(days=5)).isoformat()})
    oldwebpath = state / "website_publication" / (oldweb + ".json.gz"); oldwebbody = oldwebpath.read_bytes()
    envelope = scope(root, state, commit, f"forecasts/{one}.json.gz", f"website_bindings/{web}.json.gz")
    result = execute(root, state, commit, envelope)
    assert result["publication_verified_rows"] == 1
    assert result["website_snapshots_publication_checked"] == 1
    publication = list(records(state, "publication"))
    assert len(publication) == 2 and {r["batch"] for r in publication} == {one}
    receipt = next(r for r in publication if r.get("publication_scope_schema") == p.SCHEMA)
    assert receipt["observed_remote_readback_at"] == NOW.isoformat()
    assert receipt["publication_scope_sha256"] == digest(envelope)
    assert receipt["state_path"] == f"forecasts/{one}.json.gz"
    assert len(receipt["git_blob_oid"]) == 40
    assert oldpath.read_bytes() == original
    website = next(r for r in records(state, "website_publication") if r.get("publication_scope_schema") == p.SCHEMA)
    assert (website["timely_rows"], website["late_rows"]) == (1, 1)
    assert website["observed_remote_readback_at"] == NOW.isoformat()
    assert oldwebpath.read_bytes() == oldwebbody
    before = {str(path): path.read_bytes() for path in state.rglob("*.json.gz")}
    repeated = execute(root, state, commit, envelope)
    assert repeated["publication_verified_rows"] == repeated["website_snapshots_publication_checked"] == 0
    assert before == {str(path): path.read_bytes() for path in state.rglob("*.json.gz")}


def test_aggregate_only_and_empty_scopes_make_zero_claims(tmp_path):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    for names in [(f"health/{health}.json.gz",), ()]:
        result = execute(root, state, commit, scope(root, state, commit, *names))
        assert result["publication_verified_rows"] == result["website_snapshots_publication_checked"] == 0
    assert list(records(state, "publication")) == list(records(state, "website_publication")) == []


def test_kickoff_equality_is_late(tmp_path):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    result = execute(root, state, commit, scope(root, state, commit, f"forecasts/{two}.json.gz"))
    assert (result["publication_verified_rows"], result["late_rows"]) == (0, 1)


@pytest.mark.parametrize("name", ["../elsewhere", "forecasts/../x", "/absolute", "x//y", "x/./y", "x\\y", "x\nname", ".writer.lock", ".pending-x"])
def test_unsafe_paths_reject(name):
    with pytest.raises(ValueError, match="unsafe"):
        p.scope_document("a" * 40, {name: "b" * 64}, verified_remote_commit="a" * 40)


@pytest.mark.parametrize("commit", ["HEAD", "a" * 39, "A" * 40, "a" * 40 + "^{tree}", "a" * 64, None])
def test_commit_must_be_exact_hex(commit):
    with pytest.raises(ValueError, match="40-hex"):
        p.scope_document(commit, {}, verified_remote_commit=commit)


@pytest.mark.parametrize("mutation", ["local", "hash", "tree", "symlink", "omitted", "digest", "schema", "policy", "remote"])
def test_invalid_scope_is_atomic_no_receipts(tmp_path, mutation):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    forecast = f"forecasts/{one}.json.gz"; website = f"website_bindings/{web}.json.gz"
    envelope = scope(root, state, commit, forecast, website)
    path = state / website
    if mutation == "local":
        path.write_bytes(path.read_bytes() + b"changed")
    elif mutation == "hash":
        envelope["files"][website] = "0" * 64
    elif mutation == "tree":
        path.write_bytes(gzip.compress(canonical({"rows": []}), mtime=0))
        envelope["files"][website] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == "symlink":
        original = state / "original"; original.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(original)
    elif mutation == "omitted":
        new = save(state, "website_bindings", {"rows": [], "new": True})
        name = f"website_bindings/{new}.json.gz"
        envelope["files"][name] = hashlib.sha256((state / name).read_bytes()).hexdigest()
    elif mutation == "digest":
        false = "website_bindings/" + "0" * 64 + ".json.gz"
        badpath = state / false; badpath.write_bytes(path.read_bytes())
        git(root, "add", "state")
        git(root, "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-m", "bad filename")
        commit = git(root, "rev-parse", "HEAD")
        envelope = scope(root, state, commit, forecast, false)
    elif mutation == "schema":
        envelope["schema_version"] = "unknown"
    elif mutation == "policy":
        envelope["policy_sha256"] = "a" * 64
    else:
        envelope["verified_remote_commit"] = "0" * 40
    with pytest.raises((ValueError, OSError)):
        execute(root, state, commit, envelope)
    assert list(records(state, "publication")) == list(records(state, "website_publication")) == []


def test_wrong_commit_tree_and_tree_object_reject(tmp_path):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    envelope = scope(root, state, commit, f"forecasts/{one}.json.gz")
    git(root, "rm", "-r", "--cached", "state")
    git(root, "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-m", "empty state")
    other = git(root, "rev-parse", "HEAD")
    wrong = p.scope_document(other, envelope["files"], verified_remote_commit=other)
    with pytest.raises(ValueError, match="absent"):
        execute(root, state, other, wrong)
    tree = git(root, "rev-parse", "HEAD^{tree}")
    with pytest.raises(ValueError, match="not a commit"):
        execute(root, state, tree, p.scope_document(tree, {}, verified_remote_commit=tree))


def test_symlink_commit_entry_and_local_ancestor_reject(tmp_path):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    name = f"forecasts/{one}.json.gz"
    envelope = scope(root, state, commit, name)
    folder = state / "forecasts"; moved = state / "moved-forecasts"
    folder.rename(moved); folder.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        execute(root, state, commit, envelope)
    git(root, "add", "state")
    git(root, "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-m", "symlink fixture")
    other = git(root, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="absent or nonregular"):
        execute(root, state, other, p.scope_document(other, envelope["files"], verified_remote_commit=other))


def test_cli_unscoped_rejects_and_scoped_aggregate_does_not_call_legacy_publisher(tmp_path, monkeypatch):
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    args = SimpleNamespace(command="publication", publication_commit=commit, publication_scope_stdin=False, output=None)
    with pytest.raises(ValueError, match="explicit committed"):
        cli._execute(args, root, root / "data", state, None, [], {})
    from nfl_lab import website_baselines
    monkeypatch.setattr(website_baselines, "record_website_publication", lambda *a: pytest.fail("legacy broad scan forbidden"))
    args.publication_scope_stdin = True
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(scope(root, state, commit, f"health/{health}.json.gz"))))
    cli._execute(args, root, root / "data", state, None, [], {})
    assert list(records(state, "publication")) == list(records(state, "website_publication")) == []


def test_v2_quota_and_policy_scope_are_preserved(tmp_path):
    from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError
    from nfl_lab.operational_io import operational_io
    from nfl_lab.operational_sources import load_source_policy
    policy = load_source_policy(Path(__file__).resolve().parents[1] / "config/operational-source-policy-v2.json")
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    policy["namespaces"]["private_retention_bytes"] = 32 * 1024  # Fictional smaller global quota.
    managed = root / "managed-state"
    storage = OperationalStorage(root / "data", policy, state=managed)
    for path in list(state.rglob("*.json.gz")):
        storage.write_bytes(managed / path.relative_to(state), path.read_bytes())
    state = managed
    envelope = scope(root, state, commit, f"forecasts/{one}.json.gz", policy=policy["_policy_sha256"])
    with operational_io(storage, run_root=root / "runs"):
        result = execute(root, state, commit, envelope, policy_sha256=policy["_policy_sha256"], storage=storage)
        assert result["publication_verified_rows"] == 1
    assert len(list(records(state, "publication"))) == 1
    remaining = storage.limit_bytes - storage.snapshot()["physical_bytes"] - 16
    storage.write_bytes(storage.live_root / "fictional-filler.bin", b"x" * remaining)
    late_scope = scope(root, state, commit, f"forecasts/{two}.json.gz", policy=policy["_policy_sha256"])
    with operational_io(storage, run_root=root / "runs"):
        with pytest.raises(StorageQuotaError):
            execute(root, state, commit, late_scope, policy_sha256=policy["_policy_sha256"], storage=storage)
    assert len(list(records(state, "publication"))) == 1


def test_v2_publisher_passes_exact_reviewed_scope_after_readback(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("fictional_persist_scope", source / "tools/persist_state.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    root, state, commit, one, two, web, health = setup_repo(tmp_path)
    policy_path = source / "config/operational-source-policy-v2.json"
    from nfl_lab.operational_sources import load_source_policy
    policy = load_source_policy(policy_path)
    files = scope(root, state, commit, f"health/{health}.json.gz")["files"]
    calls = []
    def fake_git(*args, **kwargs):
        if args[0] == "rev-parse": return commit + "\n"
        if args[0] == "ls-remote": return commit + "\trefs/heads/lab-state\n"
        return ""
    def fake_run(command, **kwargs):
        if "nfl_lab.cli" in command:
            calls.append((command, json.loads(kwargs["input"])))
        return SimpleNamespace(returncode=1 if "diff" in command else 0)
    monkeypatch.setattr(module, "git", fake_git)
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "validate_existing_public", lambda *a: None)
    monkeypatch.setattr(module, "copy_state", lambda *a, **kw: None)
    monkeypatch.setattr(module, "stage_reviewed", lambda *a: None)
    storage = SimpleNamespace(live_root=root / "private")
    module.persist(root, state, storage=storage, policy_path=policy_path, files=files)
    assert len(calls) == 1 and "--publication-scope-stdin" in calls[0][0]
    assert calls[0][1] == p.scope_document(commit, files, verified_remote_commit=commit, policy_sha256=policy["_policy_sha256"])
