"""Append publication clocks only for exact files proven in a committed tree.

The publisher supplies the remote OID readback; this module performs no network
operation and does not grant content-publication permission.
"""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from .state import canonical, digest, records, save, utc, writer

SCHEMA = "lab-publication-scope-v1"
SCOPE_RECORDS = "publication_scopes"
MAX_BYTES = 200 * 1024 * 1024
COMMIT = re.compile(r"[0-9a-f]{40}", re.ASCII)
SHA256 = re.compile(r"[0-9a-f]{64}", re.ASCII)


def _git(root, *args):
    return subprocess.run(["git", "--no-replace-objects", *args], cwd=root, check=True, capture_output=True).stdout


def _regular(path):
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("publication scope cannot use symlinks")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("publication scope requires a regular file")


def _file_map(files):
    if not isinstance(files, dict):
        raise ValueError("publication scope requires an explicit file map")
    for name, sha in files.items():
        if not isinstance(name, str):
            raise ValueError("unsafe publication scope path")
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or path.as_posix() != name
                or any(part in {".", ".."} for part in path.parts)
                or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or path.name in {".writer.lock", ".operational-storage-owner"}
                or path.name.startswith(".pending-")):
            raise ValueError("unsafe publication scope path")
        if not isinstance(sha, str) or SHA256.fullmatch(sha) is None:
            raise ValueError("publication scope requires exact SHA256")
    return dict(files)


def scope_document(commit, files, *, verified_remote_commit, policy_sha256=None):
    """Transport the explicit publisher inventory, not a local-state scan."""
    if (not isinstance(commit, str) or COMMIT.fullmatch(commit) is None
            or verified_remote_commit != commit):
        raise ValueError("verified 40-hex publication commit required")
    if policy_sha256 is not None and (not isinstance(policy_sha256, str) or SHA256.fullmatch(policy_sha256) is None):
        raise ValueError("publication policy SHA256 required")
    return {"schema_version": SCHEMA, "commit": commit,
            "verified_remote_commit": verified_remote_commit,
            "policy_sha256": policy_sha256, "files": _file_map(files)}


def _record(body, name):
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        decoded = stream.read(MAX_BYTES + 1)
    if len(decoded) > MAX_BYTES:
        raise ValueError("publication record exceeds bounded decoded size")
    document = json.loads(decoded)
    key = digest(document)
    if name != key + ".json.gz" or not isinstance(document, dict) or not isinstance(document.get("rows"), list):
        raise ValueError("publication immutable record identity mismatch")
    # Validate every clock before any receipt can be appended.
    for row in document["rows"]:
        utc(row["kickoff_utc"])
    return key, document


def verify_committed_scope(root, state, *, commit, scope, policy_sha256=None, storage=None):
    """Return only forecast/binding records in the exact verified file map."""
    if not isinstance(scope, dict) or set(scope) != {
            "schema_version", "commit", "verified_remote_commit", "policy_sha256", "files"}:
        raise ValueError("explicit publication scope required")
    expected = scope_document(commit, scope["files"],
                              verified_remote_commit=scope["verified_remote_commit"],
                              policy_sha256=policy_sha256)
    if scope != expected:
        raise ValueError("publication scope commit/policy/schema mismatch")
    if _git(root, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("publication object is not a commit")
    listing = _git(root, "--literal-pathspecs", "ls-tree", "-rlz", commit, "--", "state")
    tree = {}
    for entry in listing.split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            tree[name.decode("utf-8")] = metadata.split()
    selected, total = [], 0
    state = Path(state).absolute()
    for name, sha in sorted(expected["files"].items()):
        metadata = tree.get("state/" + name)
        if metadata is None or len(metadata) != 4 or metadata[0] not in {b"100644", b"100755"} or metadata[1] != b"blob":
            raise ValueError("reviewed publication file absent or nonregular in commit tree")
        size = int(metadata[3]); total += size
        if size < 0 or total > MAX_BYTES:
            raise ValueError("publication file inventory exceeds state ceiling")
        local = state / name
        _regular(local)
        if storage is not None:
            storage.validate_reference(local, expected_sha256=sha)
        if local.stat().st_size != size:
            raise ValueError("publication local/committed file size mismatch")
        body = local.read_bytes()
        if hashlib.sha256(body).hexdigest() != sha:
            raise ValueError("publication local file hash mismatch")
        committed = _git(root, "cat-file", "blob", metadata[2].decode("ascii"))
        if len(committed) != size or hashlib.sha256(committed).hexdigest() != sha or committed != body:
            raise ValueError("publication committed file hash mismatch")
        parts = PurePosixPath(name).parts
        if parts[0] in {"forecasts", "website_bindings"}:
            if len(parts) != 2:
                raise ValueError("publication record path identity mismatch")
            key, document = _record(body, parts[1])
            selected.append((parts[0], key, document, {"state_path": name,
                "file_sha256": sha, "git_blob_oid": metadata[2].decode("ascii")}))
    return selected


def _saved_scope(path, expected_policy_sha256):
    """Decode one bounded immutable original; CAS hard links remain legal."""
    _regular(path)
    before = path.stat()
    if before.st_size > MAX_BYTES:
        raise ValueError("saved publication scope compressed size exceeds bound")
    with path.open("rb") as stream:
        compressed = stream.read(MAX_BYTES + 1)
    if len(compressed) != before.st_size:
        raise ValueError("saved publication scope changed during read")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        body = stream.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("saved publication scope decoded size exceeds bound")
    envelope = json.loads(body)
    if not isinstance(envelope, dict) or set(envelope) != {
            "schema_version", "commit", "verified_remote_commit", "policy_sha256", "files"}:
        raise ValueError("saved original full publication scope required")
    expected = scope_document(envelope["commit"], envelope["files"],
                              verified_remote_commit=envelope["verified_remote_commit"],
                              policy_sha256=expected_policy_sha256)
    if envelope != expected or body != canonical(envelope):
        raise ValueError("saved publication scope schema/policy/canonical mismatch")
    scope_sha = digest(envelope)
    if path.name != scope_sha + ".json.gz":
        raise ValueError("saved publication scope digest/path mismatch")
    _regular(path)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("saved publication scope changed during read")
    return scope_sha, envelope, len(body), len(compressed)


def saved_scope_evidence(state, expected_policy_sha256):
    """Return copied original envelopes only; never infer missing evidence.

    This metadata reader checks paths, bytes and canonical identities, not CAS
    ownership or remote publication. The caller retains the existing storage
    integrity boundary; owned CAS aliases legitimately have multiple hard links.
    The qualifier rechecks committed file/record proof before using an envelope.
    """
    # This API feeds the qualified views, which require a source-policy version.
    if (not isinstance(expected_policy_sha256, str)
            or SHA256.fullmatch(expected_policy_sha256) is None):
        raise ValueError("saved publication scopes require explicit policy SHA256")
    state = Path(state)
    if ".." in state.parts:
        raise ValueError("saved publication scope parent traversal forbidden")
    directory = state / SCOPE_RECORDS
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise ValueError("saved publication scope cannot use symlinks")
    if not directory.exists():
        return {}
    if not directory.is_dir():
        raise ValueError("saved publication scope directory required")
    result, decoded, compressed = {}, 0, 0
    for path in sorted(directory.glob("*.json.gz")):
        key, envelope, body_size, file_size = _saved_scope(path, expected_policy_sha256)
        decoded += body_size; compressed += file_size
        if max(decoded, compressed) > MAX_BYTES:
            raise ValueError("saved publication scope inventory exceeds bound")
        result[key] = deepcopy(envelope)
    return result


def record_scoped_publication(root, state, *, commit, scope, observed,
                              policy_sha256=None, storage=None):
    """Validate the entire scope before appending any timing receipt."""
    observed = utc(observed)
    scope = deepcopy(scope)
    if storage is not None:
        from .operational_io import operational_io
    with (operational_io(storage) if storage is not None else nullcontext()), writer(state):
        selected = verify_committed_scope(root, state, commit=commit, scope=scope,
                                         policy_sha256=policy_sha256, storage=storage)
        scope_sha = digest(scope)
        publications = list(records(state, "publication"))
        website_publications = list(records(state, "website_publication"))
        witness = Path(state) / SCOPE_RECORDS / (scope_sha + ".json.gz")
        if not witness.exists() and any(
                r.get("publication_scope_schema") == SCHEMA and r.get("publication_scope_sha256") == scope_sha
                for r in (*publications, *website_publications)):
            raise ValueError("missing original witness cannot retrospectively qualify an old receipt; publish a new scope")
        # The exact supplied envelope must be durable before any timing claim.
        if save(state, SCOPE_RECORDS, scope) != scope_sha:
            raise ValueError("saved publication scope identity mismatch")
        saved = _saved_scope(witness, policy_sha256)
        if saved[0] != scope_sha or saved[1] != scope:
            raise ValueError("saved publication scope differs from original")
        prior = {(r["batch"], r.get("publication_scope_sha256")) for r in publications if r.get("publication_scope_schema") == SCHEMA}
        website_prior = {(r["snapshot"], r.get("publication_scope_sha256")) for r in website_publications if r.get("publication_scope_schema") == SCHEMA}
        verified = late = snapshots = 0
        for kind, key, document, evidence in selected:
            if (key, scope_sha) in (prior if kind == "forecasts" else website_prior):
                continue
            timely = sum(utc(row["kickoff_utc"]) > observed for row in document["rows"])
            receipt = {"commit": commit, "observed_remote_readback_at": observed.isoformat(),
                       "timely_rows": timely, "late_rows": len(document["rows"]) - timely,
                       "publication_scope_schema": SCHEMA, "publication_scope_sha256": scope_sha,
                       "verified_remote_commit": scope["verified_remote_commit"], **evidence,
                       "scope": "Exact reviewed local bytes verified in remote-readback commit tree; provider publication clocks remain unknown."}
            if kind == "forecasts":
                save(state, "publication", {"batch": key, **receipt})
                verified += timely; late += len(document["rows"]) - timely
            else:
                save(state, "website_publication", {"snapshot": key, **receipt})
                snapshots += 1
        return {"publication_verified_rows": verified, "late_rows": late,
                "website_snapshots_publication_checked": snapshots,
                "publication_scope_sha256": scope_sha, "verified_scope_files": len(scope["files"])}
