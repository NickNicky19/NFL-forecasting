"""Private v2 byte quota and immutable, owned content-addressed references.

This module performs no acquisition. Frozen helpers may write only within an
explicit capture scope. Every disk write is serialized with the same flock and
checked against actual retained unique-inode file bytes before it starts.
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import threading
import uuid

VERSION = "operational-storage-v2"
MAX_BYTES = 512 * 1024 * 1024
_OWNER = ".operational-storage-owner"
_OPEN = Path.open
_WRITE_BYTES = Path.write_bytes
_WRITE_TEXT = Path.write_text
_CAPTURE_GUARD = threading.RLock()
_CAPTURES = []
_THREAD_GUARD = threading.Lock()
_THREAD_LOCKS = {}
_THREAD_CONTEXTS = {}


class StorageQuotaError(RuntimeError):
    """Incoming bytes do not fit; existing evidence has been preserved."""


class StorageIntegrityError(ValueError):
    """A root, reference or accounting control cannot be trusted."""


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _absolute(path):
    path = Path(path)
    if ".." in path.parts:
        raise StorageIntegrityError("parent traversal is forbidden")
    return Path(os.path.abspath(path))


def _beneath(path, root):
    # Select the only ancestor of the required depth; keep Path's own flavor
    # and case comparison without constructing every intervening ancestor.
    if path == root:
        return True
    parents = path.parents
    index = len(path.parts) - len(root.parts) - 1
    return 0 <= index < len(parents) and parents[index] == root


def _no_symlinks(path):
    # Same leaf-to-root lstat sequence and is_symlink error semantics, without
    # allocating and formatting a Path object for each shared ancestor.
    current = os.fspath(path)
    while True:
        try:
            linked = stat.S_ISLNK(os.stat(current, follow_symlinks=False).st_mode)
        except OSError as error:
            if (error.errno not in (errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP)
                    and getattr(error, "winerror", None) not in (21, 123, 1921)):
                raise
        except ValueError:
            pass  # Path.is_symlink treats an unencodable path as absent too.
        else:
            if linked:
                raise StorageIntegrityError("symlink path is forbidden: " + current)
        parent = os.path.dirname(current) or "."
        if parent == current:
            break
        current = parent


def _walk_error(error):
    raise StorageIntegrityError("cannot inspect every managed file or root owner") from error


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _digest_file(path):
    digest = hashlib.sha256()
    with _OPEN(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OperationalStorage:
    """One canonical cache-owned quota, including all registered state/run roots.

    Registry additions persist across instances, including instances constructed
    without ``state``. The cap cannot change for an existing store. No retained
    blobs, earlier artifacts or failed partial files are garbage collected.
    """

    def __init__(self, cache, policy, *, state=None, live_root=None):
        if isinstance(policy, (str, Path)):
            with _OPEN(Path(policy), "rb") as stream:
                policy = json.load(stream)
        if policy.get("storage", {}).get("version") != VERSION:
            raise StorageIntegrityError("explicit operational storage v2 policy required")
        self.limit_bytes = min(int(policy["storage"]["limit_bytes"]),
                               int(policy["namespaces"]["private_retention_bytes"]), MAX_BYTES)
        if self.limit_bytes <= 0:
            raise StorageIntegrityError("invalid private byte limit")
        self.cache = _absolute(cache)
        self.control_root = self.cache / VERSION
        self.blob_root = self.control_root / "blobs" / "sha256"
        self.source_root = self.cache / "operational-source-v2"
        self.feature_root = self.cache / "processed" / "operational-source-v2"
        self.live_root = _absolute(live_root) if live_root is not None else self.cache / "operational-live-v2"
        self.state_root = _absolute(state) if state is not None else None
        self.model_root = self.state_root / "models" / "permitted-operational-reference-v2" if self.state_root else None
        self.registry_path = self.control_root / "registry.json"
        self.lock_path = self.control_root / ".quota.lock"
        self._verified = {}
        self._stream_owned = {}
        self._roots = [self.control_root]
        _no_symlinks(self.control_root)
        self.control_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with _THREAD_GUARD:
            self._thread_lock = _THREAD_LOCKS.setdefault(str(self.control_root), threading.RLock())
            self._local = _THREAD_CONTEXTS.setdefault(str(self.control_root), threading.local())
        roots = [self.source_root, self.feature_root, self.live_root]
        if self.state_root is not None:
            roots.append(self.state_root)
        with self._locked():
            if self.registry_path.exists():
                self._refresh()
            elif any(p.name != ".quota.lock" for p in self.control_root.iterdir()):
                raise StorageIntegrityError("missing registry in nonempty storage control root")
            self._register(roots)

    @contextlib.contextmanager
    def _locked(self):
        with self._thread_lock:
            if getattr(self._local, "depth", 0):
                self._local.depth += 1
                try:
                    yield
                finally:
                    self._local.depth -= 1
                return
            _no_symlinks(self.lock_path)
            descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                info = os.fstat(descriptor)
                actual = self.lock_path.lstat()
                if (info.st_dev, info.st_ino) != (actual.st_dev, actual.st_ino) or info.st_nlink != 1 or info.st_size:
                    raise StorageIntegrityError("global quota lock identity changed")
                self._local.depth = 1
                self._local.lock_fd = descriptor
                yield
            finally:
                self._local.depth = 0
                self._local.lock_fd = None
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _refresh(self):
        _no_symlinks(self.registry_path)
        try:
            with _OPEN(self.registry_path, "rb") as stream:
                registry = json.load(stream)
            lock_info = os.fstat(self._local.lock_fd)
            if (set(registry) != {"version", "owner", "limit_bytes", "roots", "lock"}
                    or registry["version"] != VERSION or registry["owner"] != str(self.control_root)
                    or registry["limit_bytes"] != self.limit_bytes
                    or registry["lock"] != [lock_info.st_dev, lock_info.st_ino]):
                raise ValueError("registry identity")
            roots = [_absolute(item) for item in registry["roots"]]
            if roots != sorted(set(roots), key=str) or self.control_root not in roots:
                raise ValueError("registry roots")
            expected = self._owner_body()
            for root in roots:
                _no_symlinks(root)
                if root != self.control_root:
                    _no_symlinks(root / _OWNER)
                    with _OPEN(root / _OWNER, "rb") as stream:
                        if stream.read() != expected:
                            raise ValueError("conflicting root owner")
            self._roots = roots
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise StorageIntegrityError("storage registry/ownership is corrupt") from exc

    def _owner_body(self):
        return (str(self.control_root) + "\n").encode()

    def _register(self, additions):
        roots = sorted(set(self._roots + [_absolute(path) for path in additions]), key=str)
        for root in roots:
            _no_symlinks(root)
            markers = [parent / _OWNER for parent in root.parents]
            if root.exists():
                markers.extend(Path(directory) / _OWNER for directory, _, files in os.walk(root, followlinks=False, onerror=_walk_error)
                               if _OWNER in files)
            for owner in markers:
                _no_symlinks(owner)
                if owner.exists():
                    with _OPEN(owner, "rb") as stream:
                        if stream.read() != self._owner_body():
                            raise StorageIntegrityError("overlapping root belongs to another storage quota")
            marker = root / _OWNER
            _no_symlinks(marker)
            if root != self.control_root and marker.exists():
                with _OPEN(marker, "rb") as stream:
                    if stream.read() != self._owner_body():
                        raise StorageIntegrityError("root belongs to another storage quota")
        body = _encoded({"version": VERSION, "owner": str(self.control_root),
                         "limit_bytes": self.limit_bytes, "roots": [str(root) for root in roots],
                         "lock": [os.fstat(self._local.lock_fd).st_dev, os.fstat(self._local.lock_fd).st_ino]})
        old_roots = self._roots
        self._roots = roots
        try:
            missing = [root / _OWNER for root in roots if root != self.control_root and not (root / _OWNER).exists()]
            same = self.registry_path.exists() and self.registry_path.read_bytes() == body
            self._require(len(self._owner_body()) * len(missing) + (0 if same else len(body)))
            for root in roots:
                root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not same:
                self._atomic_plain(self.registry_path, body)
            for marker in missing:
                self._atomic_plain(marker, self._owner_body(), replace=False)
            self.blob_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._refresh()
            self._scan()
        except Exception:
            # A published registry already includes newly registered roots.
            # Interrupted ownership initialization fails closed on restart.
            self._roots = roots if self.registry_path.exists() else old_roots
            raise

    def register_root(self, path):
        """Register all existing and future bytes under a run/intake directory."""
        with self._locked():
            self._refresh()
            self._register([path])
        return _absolute(path)

    def _check(self, path):
        path = _absolute(path)
        if not any(_beneath(path, root) for root in self._roots):
            raise StorageIntegrityError("unregistered operational write destination")
        _no_symlinks(path)
        if _beneath(path, self.control_root):
            raise StorageIntegrityError("direct writes into storage controls/blobs are forbidden")
        if path.name == _OWNER:
            raise StorageIntegrityError("root ownership marker is immutable")
        return path

    def _verify_blob(self, path, info=None):
        _no_symlinks(path)
        info = info or path.lstat()
        sha = path.name
        if (path.parent != self.blob_root or len(sha) != 64
                or any(char not in "0123456789abcdef" for char in sha)
                or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o222):
            raise StorageIntegrityError("invalid or writable owned blob")
        fingerprint = _stamp(info)
        if self._verified.get(path) != fingerprint:
            if _digest_file(path) != sha or _stamp(path.lstat()) != fingerprint:
                raise StorageIntegrityError("owned blob content changed")
            self._verified[path] = fingerprint
        return sha

    def _scan(self):
        descriptor = getattr(self._local, "lock_fd", None)
        if descriptor is not None:
            actual = self.lock_path.lstat()
            locked = os.fstat(descriptor)
            if (actual.st_dev, actual.st_ino) != (locked.st_dev, locked.st_ino):
                raise StorageIntegrityError("global quota lock was replaced")
        paths = set()
        for root in self._roots:
            _no_symlinks(root)
            if not root.exists():
                continue
            if not root.is_dir():
                raise StorageIntegrityError("managed root must be a directory")
            for directory, names, files in os.walk(root, followlinks=False, onerror=_walk_error):
                for name in names + files:
                    path = Path(directory) / name
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode):
                        raise StorageIntegrityError("symlink inside managed root")
                    if not stat.S_ISDIR(info.st_mode):
                        if not stat.S_ISREG(info.st_mode):
                            raise StorageIntegrityError("nonregular managed file")
                        paths.add(path)
        inodes = {}
        logical = 0
        for path in sorted(paths):
            info = path.lstat()
            key = (info.st_dev, info.st_ino)
            logical += info.st_size
            entry = inodes.setdefault(key, [info.st_size, info.st_nlink, 0])
            if entry[:2] != [info.st_size, info.st_nlink]:
                raise StorageIntegrityError("file changed during quota scan")
            entry[2] += 1
            if _beneath(path, self.blob_root):
                self._verify_blob(path, info)
        if any(links != observed for _, links, observed in inodes.values()):
            raise StorageIntegrityError("unaccounted external hardlink")
        physical = sum(entry[0] for entry in inodes.values())
        if physical > self.limit_bytes:
            raise StorageQuotaError("retained managed bytes exceed shared quota; evidence preserved")
        return {"version": VERSION, "physical_bytes": physical, "physical_bytes_unique_inodes": physical,
                "logical_referenced_bytes": logical, "limit_bytes": self.limit_bytes,
                "files": len(paths), "unique_inodes": len(inodes), "roots": [str(root) for root in self._roots]}

    def snapshot(self):
        with self._locked():
            self._refresh()
            return self._scan()

    @contextlib.contextmanager
    def transaction(self):
        """Hold the shared flock across an adapter's additional cap and write."""
        with self._locked():
            self._refresh()
            self._scan()
            yield self

    def _require(self, incoming):
        usage = self._scan()
        if incoming < 0 or usage["physical_bytes"] + incoming > self.limit_bytes:
            raise StorageQuotaError("incoming bytes exceed shared operational quota before write; evidence preserved")
        return usage

    def _temporary(self, directory, prefix):
        _no_symlinks(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / (prefix + uuid.uuid4().hex)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        return path, descriptor

    @staticmethod
    def _write_all(descriptor, body):
        pending = memoryview(body)
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("short storage write")
            pending = pending[count:]

    @staticmethod
    def _sync(directory):
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _atomic_plain(self, path, body, *, replace=True):
        self._require(len(body))
        temporary, descriptor = self._temporary(path.parent, ".control-")
        try:
            self._write_all(descriptor, body)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path, follow_symlinks=False)
            temporary.unlink()
        self._sync(path.parent)

    def _publish_blob(self, temporary, sha):
        blob = self.blob_root / sha
        if blob.exists():
            self._verify_blob(blob)
            temporary.unlink()
        else:
            os.chmod(temporary, 0o444, follow_symlinks=False)
            os.link(temporary, blob, follow_symlinks=False)
            temporary.unlink()
            self._sync(self.blob_root)
        self._verify_blob(blob)
        return blob

    def _alias(self, blob, path, replace):
        self._check(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _no_symlinks(path)
        if not replace:
            os.link(blob, path, follow_symlinks=False)
        elif path.exists() and os.path.samestat(path.stat(), blob.stat()):
            return
        else:
            temporary = path.parent / (".alias-" + uuid.uuid4().hex)
            os.link(blob, temporary, follow_symlinks=False)
            os.replace(temporary, path)
        self._sync(path.parent)

    def _mutable(self, path):
        return any(storage.control_root == self.control_root and scopes is not None
                   and any(_beneath(path, root) for root in scopes)
                   for storage, scopes, mutable in _CAPTURES if mutable)

    def write_bytes(self, path, body, *, replace=False):
        body = bytes(body)
        with self._locked():
            self._refresh()
            path = self._check(path)
            self._scan()
            sha = hashlib.sha256(body).hexdigest()
            blob = self.blob_root / sha
            if path.exists():
                if blob.exists() and os.path.samestat(path.stat(), blob.stat()):
                    self._verify_blob(blob)
                    return len(body)
                if not replace:
                    raise FileExistsError(path)
                if not self._mutable(path):
                    raise StorageIntegrityError("replacement requires an explicit mutable helper scope")
            if blob.exists():
                self._verify_blob(blob)
            else:
                self._require(len(body))
                temporary, descriptor = self._temporary(self.control_root, ".incoming-")
                try:
                    self._write_all(descriptor, body)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                blob = self._publish_blob(temporary, sha)
            self._alias(blob, path, replace)
            return len(body)

    def write_text(self, path, text, encoding=None, errors=None, newline=None, *, replace=False):
        buffer = io.BytesIO()
        with io.TextIOWrapper(buffer, encoding=encoding or "utf-8", errors=errors, newline=newline) as stream:
            count = stream.write(text)
            stream.flush()
            body = buffer.getvalue()
        self.write_bytes(path, body, replace=replace)
        return count

    def atomic_json(self, path, value, *, replace=False):
        self.write_bytes(path, _encoded(value), replace=replace)

    def import_file(self, source, destination, expected_sha256=None):
        source = _absolute(source)
        _no_symlinks(source)
        with self._locked():
            self._refresh()
            destination = self._check(destination)
            self._scan()
            descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode):
                    raise StorageIntegrityError("source is not a regular file")
                sha = _digest_file(source)
                if expected_sha256 is not None and sha != expected_sha256:
                    raise StorageIntegrityError("import source hash mismatch")
                if _stamp(os.fstat(descriptor)) != _stamp(before) or _stamp(source.lstat()) != _stamp(before):
                    raise StorageIntegrityError("import source changed during verification")
                blob = self.blob_root / sha
                if source == destination and not (blob.exists() and os.path.samestat(source.stat(), blob.stat())):
                    if self._stream_owned.get((before.st_dev, before.st_ino)) != (before.st_size, sha):
                        raise StorageIntegrityError("only newly captured staging files may be promoted in place")
                if (destination.exists() and source != destination
                        and not (blob.exists() and os.path.samestat(destination.stat(), blob.stat()))
                        and not self._mutable(destination)):
                    raise StorageIntegrityError("import would replace a published reference")
                if blob.exists():
                    self._verify_blob(blob)
                elif (source == destination
                      and self._stream_owned.get((before.st_dev, before.st_ino)) == (before.st_size, sha)):
                    # Only a registered, unlinked staging inode may be promoted.
                    self._check(source)
                    if before.st_nlink != 1:
                        raise StorageIntegrityError("staging promotion requires a private inode")
                    os.fchmod(descriptor, 0o444)
                    os.rename(source, blob)
                    self._sync(self.blob_root)
                    self._verify_blob(blob)
                else:
                    self._require(before.st_size)
                    temporary, output = self._temporary(self.control_root, ".incoming-")
                    copied = hashlib.sha256()
                    count = 0
                    try:
                        while True:
                            chunk = os.read(descriptor, 1024 * 1024)
                            if not chunk:
                                break
                            count += len(chunk)
                            if count > before.st_size:
                                raise StorageIntegrityError("source grew during immutable copy")
                            self._write_all(output, chunk)
                            copied.update(chunk)
                        os.fsync(output)
                    finally:
                        os.close(output)
                    if (count != before.st_size or copied.hexdigest() != sha
                            or _stamp(os.fstat(descriptor)) != _stamp(before)
                            or _stamp(source.lstat()) != _stamp(before)):
                        raise StorageIntegrityError("source changed during immutable copy")
                    blob = self._publish_blob(temporary, sha)
                self._alias(blob, destination, True)
                return {"path": str(destination), "blob": str(blob), "sha256": sha, "bytes": before.st_size}
            finally:
                os.close(descriptor)

    def validate_reference(self, path, expected_sha256=None):
        with self._locked():
            self._refresh()
            path = self._check(path)
            self._scan()
            info = path.lstat()
            if info.st_mode & 0o222 or not stat.S_ISREG(info.st_mode):
                raise StorageIntegrityError("published reference must be readonly")
            sha = _digest_file(path)
            if expected_sha256 is not None and sha != expected_sha256:
                raise StorageIntegrityError("published reference hash mismatch")
            blob = self.blob_root / sha
            self._verify_blob(blob)
            if not os.path.samestat(info, blob.lstat()):
                raise StorageIntegrityError("reference is not an owned blob alias")
            return {"path": str(path), "blob": str(blob), "sha256": sha, "bytes": info.st_size}

    def write_dataframe(self, frame, path, *, format="parquet", replace=False, **kwargs):
        parquet, csv = _dataframe_writers()
        if format == "parquet":
            buffer = io.BytesIO()
            parquet(frame, buffer, **kwargs)
            self.write_bytes(path, buffer.getvalue(), replace=replace)
        elif format == "csv":
            buffer = io.StringIO(newline="")
            csv(frame, buffer, **kwargs)
            self.write_text(path, buffer.getvalue(), encoding=kwargs.get("encoding") or "utf-8", replace=replace)
        else:
            raise ValueError("unsupported dataframe format")

    def _open_writer(self, path, mode, buffering=-1, encoding=None, errors=None, newline=None):
        with self._locked():
            self._refresh()
            path = self._check(path)
            self._scan()
            if mode in {"a", "ab"} and path.name == ".writer.lock":
                if path.exists() and path.stat().st_size:
                    raise StorageIntegrityError("writer lock must remain empty")
                path.parent.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(path, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                return _ZeroLock(descriptor)
            if mode != "wb":
                raise StorageIntegrityError("unsupported managed writable open mode: " + mode)
            existed = path.exists()
            if existed:
                info = path.lstat()
                if info.st_nlink != 1 or info.st_mode & 0o222 == 0 or info.st_size:
                    raise StorageIntegrityError("stream cannot truncate retained bytes or immutable alias")
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            return _QuotaStream(self, path, descriptor, owned=not existed)

    @contextlib.contextmanager
    def capture_writes(self, roots=None):
        """Capture only registered path destinations used by frozen helpers.

        Direct builtins/io/tempfile writers are outside this adapter. Their
        operational call sites must use explicit atomic serializer adapters.
        """
        with self._locked():
            self._refresh()
            scopes = [_absolute(path) for path in (roots if roots is not None else self._roots) if _absolute(path) != self.control_root]
            for path in scopes:
                self._check(path)
        with _CAPTURE_GUARD:
            global _PANDAS_PARQUET, _PANDAS_CSV
            import pandas as pd
            first = not _CAPTURES
            if first:
                _PANDAS_PARQUET, _PANDAS_CSV = pd.DataFrame.to_parquet, pd.DataFrame.to_csv
                Path.write_bytes, Path.write_text, Path.open = _capture_bytes, _capture_text, _capture_open
                pd.DataFrame.to_parquet, pd.DataFrame.to_csv = _capture_parquet, _capture_csv
            _CAPTURES.append((self, scopes, roots is not None))
            try:
                yield self
            finally:
                _CAPTURES.pop()
                if first:
                    Path.write_bytes, Path.write_text, Path.open = _WRITE_BYTES, _WRITE_TEXT, _OPEN
                    pd.DataFrame.to_parquet, pd.DataFrame.to_csv = _PANDAS_PARQUET, _PANDAS_CSV


class _QuotaStream:
    """Unbuffered chunk sink: the check and actual write share one flock."""

    def __init__(self, storage, path, descriptor, *, owned):
        self.storage, self.path, self.descriptor = storage, path, descriptor
        self.closed = False
        self.name, self.mode = str(path), "wb"
        self.owned = owned
        self.digest = hashlib.sha256()

    def write(self, body):
        if self.closed:
            raise ValueError("write to closed quota stream")
        body = bytes(body)
        with self.storage._locked():
            self.storage._refresh()
            self.storage._check(self.path)
            actual, opened = self.path.lstat(), os.fstat(self.descriptor)
            if not os.path.samestat(actual, opened) or actual.st_nlink != 1 or actual.st_mode & 0o222 == 0:
                raise StorageIntegrityError("stream inode changed or acquired an alias")
            self.storage._require(len(body))
            self.storage._write_all(self.descriptor, body)
            self.digest.update(body)
            return len(body)

    def flush(self):
        if not self.closed:
            os.fsync(self.descriptor)

    def close(self):
        if not self.closed:
            try:
                self.flush()
                info = os.fstat(self.descriptor)
                if self.owned:
                    self.storage._stream_owned[(info.st_dev, info.st_ino)] = (info.st_size, self.digest.hexdigest())
            finally:
                os.close(self.descriptor)
                self.closed = True

    def tell(self):
        return os.lseek(self.descriptor, 0, os.SEEK_CUR)

    def fileno(self):
        # A raw writable descriptor would bypass per-chunk preflight.
        raise StorageIntegrityError("raw quota stream descriptors are not exposed")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _ZeroLock:
    """The frozen state writer may flock an empty append-mode lock only."""

    def __init__(self, descriptor):
        self.descriptor = descriptor

    def fileno(self):
        return self.descriptor

    def write(self, body):
        if body:
            raise StorageIntegrityError("zero-byte writer lock cannot receive data")
        return 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.descriptor)


def _capture_for(path):
    if not isinstance(path, (str, os.PathLike)):
        if isinstance(path, _QuotaStream):
            return None
        name = getattr(path, "name", None)
        if isinstance(name, (str, os.PathLike)) and _capture_for(name) is not None:
            raise StorageIntegrityError("managed dataframe filelike sink bypasses serialization quota")
        return None
    candidate = Path(path)
    lexical = candidate if candidate.is_absolute() else Path.cwd() / candidate
    normalized = Path(os.path.abspath(lexical))
    managed = False
    for storage, roots, mutable in reversed(_CAPTURES):
        if _beneath(normalized, storage.control_root) or _beneath(lexical, storage.control_root):
            raise StorageIntegrityError("captured writes into storage controls are forbidden")
        if any(_beneath(lexical, root) or _beneath(normalized, root) for root in roots):
            storage._check(lexical)
            return storage
        if any(_beneath(lexical, root) or _beneath(normalized, root) for root in storage._roots):
            managed = True
    if managed:
        raise StorageIntegrityError("managed destination lies outside active helper write scope")
    return None


def _capture_bytes(path, body):
    storage = _capture_for(path)
    return storage.write_bytes(path, body, replace=True) if storage else _WRITE_BYTES(path, body)


def _capture_text(path, text, encoding=None, errors=None, newline=None):
    storage = _capture_for(path)
    return storage.write_text(path, text, encoding, errors, newline, replace=True) if storage else _WRITE_TEXT(path, text, encoding, errors, newline)


def _capture_open(path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
    if not any(char in mode for char in "wax+"):
        return _OPEN(path, mode, buffering, encoding, errors, newline)
    storage = _capture_for(path)
    if storage:
        return storage._open_writer(path, mode, buffering, encoding, errors, newline)
    return _OPEN(path, mode, buffering, encoding, errors, newline)


def _capture_parquet(frame, path=None, *args, **kwargs):
    storage = _capture_for(path)
    if storage:
        buffer = io.BytesIO()
        result = _PANDAS_PARQUET(frame, buffer, *args, **kwargs)
        storage.write_bytes(path, buffer.getvalue(), replace=True)
        return result
    return _PANDAS_PARQUET(frame, path, *args, **kwargs)


def _capture_csv(frame, path_or_buf=None, *args, **kwargs):
    storage = _capture_for(path_or_buf)
    if storage:
        buffer = io.StringIO(newline="")
        result = _PANDAS_CSV(frame, buffer, *args, **kwargs)
        storage.write_text(path_or_buf, buffer.getvalue(), encoding=kwargs.get("encoding") or "utf-8", replace=True)
        return result
    return _PANDAS_CSV(frame, path_or_buf, *args, **kwargs)


# Metadata/CAS operations do not import a numerical runtime. Explicit dataframe
# writes still work before the first capture context, using the original methods.
_PANDAS_PARQUET = _PANDAS_CSV = None


def _dataframe_writers():
    global _PANDAS_PARQUET, _PANDAS_CSV
    with _CAPTURE_GUARD:
        if _PANDAS_PARQUET is None:
            import pandas as pd
            _PANDAS_PARQUET, _PANDAS_CSV = pd.DataFrame.to_parquet, pd.DataFrame.to_csv
        return _PANDAS_PARQUET, _PANDAS_CSV
