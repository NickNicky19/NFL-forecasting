"""Append publication clocks only for exact files proven in a committed tree.

The publisher supplies the remote OID readback; this module performs no network
operation and does not grant content-publication permission.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from .state import digest, records, save, utc, writer

SCHEMA = "lab-publication-scope-v1"
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


def record_scoped_publication(root, state, *, commit, scope, observed,
                              policy_sha256=None, storage=None):
    """Validate the entire scope before appending any timing receipt."""
    observed = utc(observed)
    with writer(state):
        selected = verify_committed_scope(root, state, commit=commit, scope=scope,
                                         policy_sha256=policy_sha256, storage=storage)
        prior = {r["batch"] for r in records(state, "publication") if r.get("publication_scope_schema") == SCHEMA}
        website_prior = {r["snapshot"] for r in records(state, "website_publication") if r.get("publication_scope_schema") == SCHEMA}
        verified = late = snapshots = 0
        scope_sha = digest(scope)
        for kind, key, document, evidence in selected:
            if key in (prior if kind == "forecasts" else website_prior):
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
