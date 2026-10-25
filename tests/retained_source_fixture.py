"""Exact public source fixtures for retired, immutable procedure registrations.

These controls test an old registration against its original bytes. They do not
qualify the current checkout, a genuine Actions job, a private model or a feed.
Missing historical bytes fail; no expected hash is edited or ignored.
"""
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=128)
def registered_bytes(name, expected):
    path = Path(name)
    assert not path.is_absolute() and ".." not in path.parts
    actual = REPOSITORY / path
    if actual.is_file():
        raw = actual.read_bytes()
        if hashlib.sha256(raw).hexdigest() == expected:
            return raw
    commits = subprocess.check_output(["git", "log", "--all", "--format=%H", "--", name],
                                      cwd=REPOSITORY, text=True).splitlines()
    assert len(commits) <= 256, "retained source search bound exceeded"
    for commit in commits:
        result = subprocess.run(["git", "show", commit+":"+name], cwd=REPOSITORY,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            assert len(result.stdout) <= 2 << 20
            if hashlib.sha256(result.stdout).hexdigest() == expected:
                return result.stdout
    raise AssertionError("exact registered source bytes unavailable: "+name)


@contextmanager
def retained_procedure(module, config_name, *, test_module=None):
    body = (REPOSITORY/config_name).read_bytes()
    configuration = json.loads(body)
    with tempfile.TemporaryDirectory(prefix="retained-procedure-") as directory:
        root = Path(directory)
        for name, expected in configuration["source_sha256"].items():
            destination = root/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(registered_bytes(name, expected))
        destination = root/config_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        with patch.object(module, "ROOT", root):
            with patch.object(module, "CONFIG", destination):
                if test_module is None:
                    yield root
                else:
                    with patch.object(test_module, "ROOT", root):
                        yield root


def workflow_job(text, name):
    marker = "  "+name+":\n"
    assert text.count(marker) == 1
    lines = text.split(marker, 1)[1].splitlines(keepends=True)
    result = []
    for line in lines:
        if line.startswith("  ") and not line.startswith("    ") and line.strip():
            break
        result.append(line)
    return marker+"".join(result)
