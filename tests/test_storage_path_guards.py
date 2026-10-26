"""Filesystem boundary checks for allocation-free ancestor traversal."""
import errno
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import pytest
from nfl_lab import operational_storage as storage


def test_containment_keeps_exact_ancestor_flavor_case_and_root_boundaries():
    cases = [
        (PurePosixPath('/managed/file'), PurePosixPath('/managed'), True),
        (PurePosixPath('/managed'), PurePosixPath('/managed'), True),
        (PurePosixPath('/managed-other/file'), PurePosixPath('/managed'), False),
        (PurePosixPath('/Managed/file'), PurePosixPath('/managed'), False),
        (PurePosixPath('/managed'), PurePosixPath('/managed/file'), False),
        (PurePosixPath('/managed/file'), PurePosixPath('/'), True),
        (PurePosixPath('managed/file'), PurePosixPath('.'), True),
        (PurePosixPath('managed/file'), PurePosixPath('/managed'), False),
        (PurePosixPath('/managed/file'), PurePosixPath('.'), False),
        (PurePosixPath('/'), PurePosixPath('.'), False),
        (PurePosixPath('//managed/file'), PurePosixPath('/managed'), False),
        (PureWindowsPath('C:/Managed/file'), PureWindowsPath('c:/managed'), True),
        (PureWindowsPath('D:/Managed/file'), PureWindowsPath('C:/Managed'), False),
        (PureWindowsPath('C:/Managed/file'), PureWindowsPath('.'), False),
    ]
    for path, root, expected in cases:
        assert storage._beneath(path, root) is expected, (path, root)


def test_every_ancestor_is_lstat_checked_in_original_leaf_to_root_order(tmp_path, monkeypatch):
    leaf = tmp_path/'a'/'missing'/'leaf'
    expected = [os.fspath(p) for p in [leaf, *leaf.parents]]
    actual = os.stat; calls = []
    def observe(path, *, follow_symlinks=True, **kwargs):
        if follow_symlinks is False: calls.append(os.fspath(path))
        return actual(path, follow_symlinks=follow_symlinks, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'stat', observe)
        storage._no_symlinks(leaf)
    assert calls == expected


def test_leaf_ancestor_and_broken_symlinks_still_reject(tmp_path):
    actual = tmp_path/'actual'; actual.mkdir()
    linked = tmp_path/'linked'; linked.symlink_to(actual, target_is_directory=True)
    broken = tmp_path/'broken'; broken.symlink_to(tmp_path/'absent')
    for path in (linked, linked/'missing'/'leaf', broken):
        with pytest.raises(storage.StorageIntegrityError, match='symlink path is forbidden'):
            storage._no_symlinks(path)


def test_permission_and_io_errors_are_not_treated_as_missing(tmp_path, monkeypatch):
    for number in (errno.EACCES, errno.EPERM, errno.EIO):
        def fail(*args, **kwargs): raise OSError(number, 'controlled filesystem error')
        with monkeypatch.context() as patch:
            patch.setattr(os, 'stat', fail)
            with pytest.raises(OSError) as error:
                storage._no_symlinks(tmp_path/'leaf')
        assert error.value.errno == number


def test_original_missing_and_unencodable_path_error_semantics(tmp_path, monkeypatch):
    for value in [OSError(n, 'controlled absent path') for n in (errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP)] + [ValueError('controlled unencodable path')]:
        def fail(*args, **kwargs): raise value
        with monkeypatch.context() as patch:
            patch.setattr(os, 'stat', fail)
            storage._no_symlinks(tmp_path/'leaf')
