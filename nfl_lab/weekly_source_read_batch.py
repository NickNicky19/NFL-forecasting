"""Read-only source verification under the existing exclusive quota lock.

The original loader and source-manifest checks still execute. Only repeated
whole-store scans inside each validate_reference call share one immutable,
explicitly authenticated operation. Nothing from this context grants writes.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import threading

from .operational_storage import OperationalStorage, StorageIntegrityError
from .owned_reference_batch import validate_owned_references


def identity(path):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o222:
        raise StorageIntegrityError("immutable regular source required")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode, info.st_nlink)


@contextmanager
def source_read_operation(storage, bindings):
    """Exact source whitelist; unchanged entry/exit ownership and quota checks.

    The caller supplies all hashes before source decoding. An unknown path or
    another store is rejected, rather than obtaining a cached authorization.
    The original method is restored before the finally authentication runs.
    One global exclusive lock covers the entire caller's original load.
    """
    original = OperationalStorage.validate_reference
    owner = threading.get_ident()
    receipt = {"reference_calls": 0, "original_loader_required": True,
               "whole_operation_exclusive_lock": True, "writes_authorized": False}
    with storage.transaction():
        references, entry = validate_owned_references(storage, bindings)
        stamps = {path: identity(path) for path in references}
        receipt["entry"] = entry

        def verified(instance, path, expected_sha256=None):
            if threading.get_ident() != owner:
                raise StorageIntegrityError("source operation cannot authorize another thread")
            if instance.control_root != storage.control_root:
                raise StorageIntegrityError("source operation cannot authorize another store")
            canonical = str(instance._check(path))
            if canonical not in references:
                raise StorageIntegrityError("source reference outside frozen operation")
            ref = references[canonical]
            if expected_sha256 is not None and expected_sha256 != ref["sha256"]:
                raise StorageIntegrityError("source expected hash changed")
            if identity(canonical) != stamps[canonical]:
                raise StorageIntegrityError("source changed during authenticated operation")
            blob = instance.blob_root / ref["sha256"]
            if not os.path.samestat(Path(canonical).lstat(), blob.lstat()):
                raise StorageIntegrityError("source lost its owned alias")
            receipt["reference_calls"] += 1
            return dict(ref)

        OperationalStorage.validate_reference = verified
        try:
            yield receipt
        finally:
            OperationalStorage.validate_reference = original
            for path, stamp in stamps.items():
                if identity(path) != stamp:
                    raise StorageIntegrityError("source changed before operation close")
            _, exit_receipt = validate_owned_references(storage, bindings)
            receipt["exit"] = exit_receipt


def manifest_bindings(namespace, manifest, *, manifest_sha256, request_binding,
                      request_binding_sha256):
    """Create no identities: all expected hashes come from the frozen inputs."""
    namespace = Path(namespace)
    result = {str(namespace / "source-manifest.json"): manifest_sha256,
              str(request_binding): request_binding_sha256}
    for name, item in manifest["sources"].items():
        if Path(name).name != name or name in {".", ".."}:
            raise StorageIntegrityError("source name escapes manifest directory")
        result[str(namespace / "sources" / name)] = item["sha256"]
        result[str(namespace / "sources" / (name + ".receipt.json"))] = item["receipt_sha256"]
    for relative, expected in manifest["artifact_sha256s"].items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise StorageIntegrityError("source manifest relative path escapes")
        result[str(namespace / path)] = expected
    return result
