"""Restore local fetched Git evidence through the shared v2 prewrite quota."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import subprocess


def restore_state(root, ref, storage, *, max_bytes=200 * 1024 * 1024):
    root = Path(root)
    state = storage.state_root
    if state is None:
        raise ValueError("state restore requires a registered state root")
    found = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref], cwd=root)
    if found.returncode == 1:
        return {"state": "NO_PRIOR_STATE", "restored_files": 0}
    if found.returncode:
        raise RuntimeError("could not inspect prior state ref")
    listing = subprocess.run(["git", "ls-tree", "-rlz", ref, "--", "state"], cwd=root,
                             check=True, capture_output=True).stdout
    files = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid, encoded_size = metadata.split()
        name = name.decode("utf-8")
        relative = PurePosixPath(name)
        if (mode not in {b"100644", b"100755"} or kind != b"blob"
                or relative.is_absolute() or relative.as_posix() != name
                or len(relative.parts) < 2 or relative.parts[0] != "state"
                or any(part in {".", ".."} for part in relative.parts) or "\\" in name
                or relative.name in {".operational-storage-owner", ".writer.lock"}
                or relative.name.startswith(".pending-")):
            raise ValueError("unsafe or nonregular prior state entry")
        size = int(encoded_size)
        if size < 0 or size > min(max_bytes, storage.limit_bytes):
            raise RuntimeError("prior state blob exceeds bounded restore limit")
        files.append((Path(*relative.parts[1:]), oid.decode("ascii"), size))
    restored = 0
    for relative, oid, size in files:
        destination = state / relative
        with storage.transaction():
            logical_size = sum(path.stat().st_size for path in state.rglob("*")
                               if path.is_file() and path.name != ".writer.lock")
            if not destination.exists() and logical_size + size > max_bytes:
                raise RuntimeError("durable evidence cap reached during restore; no evidence deleted")
            # ls-tree size is checked before asking Git to materialize a body
            # in RAM. No tar/copy/tempfile can write unreserved state bytes.
            body = subprocess.run(["git", "cat-file", "blob", oid], cwd=root,
                                  check=True, capture_output=True).stdout
            if len(body) != size:
                raise ValueError("prior state blob size changed")
            if destination.exists():
                if destination.read_bytes() != body:
                    raise ValueError("prior state restore conflicts with preserved local bytes")
            else:
                storage.write_bytes(destination, body, replace=False)
            restored += 1
    return {"state": "RESTORED", "restored_files": restored,
            "physical_bytes": storage.snapshot()["physical_bytes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-policy", type=Path, required=True)
    parser.add_argument("--ref", default="refs/remotes/origin/lab-state")
    args = parser.parse_args()
    from nfl_lab.operational_sources import load_source_policy
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.operational_io import operational_io
    root = Path.cwd()
    storage = OperationalStorage(root / "data", load_source_policy(args.source_policy), state=root / "state")
    with operational_io(storage, run_root=root / "runs"):
        try:
            result = restore_state(root, args.ref, storage)
            report=root / "runs/operational-v2/restore-result.json"
            with storage.capture_writes(roots=[report]):
                storage.atomic_json(report, result, replace=True)
            print(result)
        except Exception as error:
            try:
                from nfl_lab import state
                state.save(storage.state_root, "health", {"state": "STATE_RESTORE_FAILED",
                    "error": type(error).__name__ + ": " + str(error)[:500]})
            except Exception as receipt_error:
                error.add_note("Restore failure receipt could not be persisted: " + str(receipt_error))
            raise


if __name__ == "__main__":
    main()
