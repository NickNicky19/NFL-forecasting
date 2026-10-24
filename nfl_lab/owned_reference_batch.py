"""Validate frozen owned references under one existing global quota flock.

Only redundant per-reference quota scans are removed. The original storage
implementation supplies the lock, registry refresh, scans, path checks and CAS
verification; its source and behavior remain unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import re
import stat

from .operational_storage import OperationalStorage, StorageIntegrityError, _digest_file

VERSION = "owned-reference-batch-v1"
REGISTRATION_SHA256 = "d5e040355be0dd07ea0af0c4182e4f7c1fcd386fd8277b52d6a3217dfc196e35"


def validate_owned_references(storage: OperationalStorage, bindings: Mapping) -> tuple[dict, dict]:
    """Return (canonical-path reference map, private entry/exit scan receipt).

    Bindings must be a nonempty mapping of absolute Path/string names to exact
    lowercase SHA256 strings. Resolve frozen manifest-relative paths against the
    caller's authenticated parent output before calling; this function never
    guesses a base root. Canonically duplicate paths are rejected, while two
    distinct owned hardlink references to the same CAS blob remain valid.

    One unchanged exclusive quota lock covers registry refresh and full scan at
    entry, every original per-reference check, and refresh/full scan in finally
    at exit. No result is returned if either scan or any check fails. The caller
    owns recovery eligibility, failure evidence, budgets and receipt writes.
    """
    if not isinstance(storage, OperationalStorage):
        raise StorageIntegrityError("existing OperationalStorage instance required")
    if not isinstance(bindings, Mapping) or not bindings:
        raise StorageIntegrityError("nonempty exact path-to-SHA256 mapping required")
    items = list(bindings.items())
    for raw_path, expected_sha256 in items:
        if not isinstance(raw_path, (str, Path)) or not Path(raw_path).is_absolute():
            raise StorageIntegrityError("absolute reference path required")
        if not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
            raise StorageIntegrityError("exact lowercase SHA256 binding required")

    references = {}
    with storage._locked():
        try:
            storage._refresh()
            entry = storage._scan()
            for raw_path, expected_sha256 in items:
                path = storage._check(raw_path)
                if str(path) in references:
                    raise StorageIntegrityError("duplicate canonical reference path")
                # This is the original validate_reference per-path body, with
                # only its already-covered lock/refresh/full-scan removed.
                info = path.lstat()
                if info.st_mode & 0o222 or not stat.S_ISREG(info.st_mode):
                    raise StorageIntegrityError("published reference must be readonly")
                sha = _digest_file(path)
                if sha != expected_sha256:
                    raise StorageIntegrityError("published reference hash mismatch")
                blob = storage.blob_root / sha
                storage._verify_blob(blob)
                if not os.path.samestat(info, blob.lstat()):
                    raise StorageIntegrityError("reference is not an owned blob alias")
                references[str(path)] = {"path": str(path), "blob": str(blob), "sha256": sha, "bytes": info.st_size}
        finally:
            storage._refresh()
            exit_usage = storage._scan()
        receipt = {"version": VERSION, "registration_sha256": REGISTRATION_SHA256,
            "validated_references": len(references), "full_scan_calls": 2,
            "lock_scope": "existing exclusive global quota flock across entry, references and exit",
            "entry": entry, "exit": exit_usage}
        return references, receipt
