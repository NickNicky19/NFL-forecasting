"""Scoped quota adapters for frozen operational persistence helpers."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import gzip
import sys
import threading
from pathlib import Path

from . import state

_ACTIVE = ContextVar("operational_storage", default=None)
_SERIALIZERS = threading.RLock()


def active_storage():
    return _ACTIVE.get()


def quota_downloader(storage):
    """Keep the frozen HTTP contract and publish its completed files in CAS."""
    from .data import _download

    def download(raw, name, url, **kwargs):
        with operational_io(storage):
            receipt = _download(raw, name, url, **kwargs)
            path = Path(raw) / name
            if path.exists():
                storage.import_file(path, path, expected_sha256=receipt.get("sha256"))
            metadata = Path(raw) / (name + ".receipt.json")
            if metadata.exists():
                storage.import_file(metadata, metadata)
            return receipt
    return download


def _quota_save(root, kind, doc, max_bytes=200 * 1024 * 1024):
    storage = active_storage()
    if storage is None:
        raise RuntimeError("operational persistence requires its quota scope")
    root = Path(root)
    storage.register_root(root)
    with storage.transaction():
        body = state.canonical(doc)
        key = state.digest(doc)
        path = root / kind / f"{key}.json.gz"
        if path.exists():
            if gzip.decompress(path.read_bytes()) != body:
                raise ValueError("conflicting immutable record")
            return key
        # Preserve the frozen state helper's separate logical 200MiB ceiling.
        size = sum(p.stat().st_size for p in root.rglob("*")
                   if p.is_file() and p.name != ".writer.lock")
        compressed = gzip.compress(body, mtime=0)
        if size + len(compressed) > max_bytes:
            raise RuntimeError("durable evidence cap reached; no evidence deleted")
        try:
            storage.write_bytes(path, compressed, replace=False)
        except FileExistsError:
            if gzip.decompress(path.read_bytes()) != body:
                raise ValueError("conflicting immutable record")
        return key


@contextmanager
def operational_io(storage, *, run_root=None):
    """Route imported save seams and frozen path writers only while active.

    The lock prevents another operational thread from observing partly changed
    serializers. Newly imported modules inherit the adapter from state.save and
    are restored on exit as well. Nested scopes share the active quota context.
    """
    if run_root is not None:
        storage.register_root(Path(run_root))
    with _SERIALIZERS:
        previous = state.save
        outer = previous is not _quota_save
        if outer:
            for module in list(sys.modules.values()):
                if getattr(module, "__name__", "").startswith("nfl_lab") and getattr(module, "save", None) is previous:
                    module.save = _quota_save
        token = _ACTIVE.set(storage)
        try:
            with storage.capture_writes():
                yield storage
        finally:
            _ACTIVE.reset(token)
            if outer:
                # Include modules first imported during this scope.
                for module in list(sys.modules.values()):
                    if getattr(module, "__name__", "").startswith("nfl_lab") and getattr(module, "save", None) is _quota_save:
                        module.save = previous
