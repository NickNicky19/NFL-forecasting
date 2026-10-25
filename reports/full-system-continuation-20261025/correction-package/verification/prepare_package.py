"""Rebuild review-only source files from a fixed local Git object, never a writer.

All Git commands are reads. Scratch has no .git and receives all mutations.
The public package includes source corrections and fictional evidence only.
"""
from pathlib import Path
import difflib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
AUDIT = PACKAGE.parent
SOURCE = AUDIT / "website-caption"
BASE = "89512ed952308dacc1f6a930915ddbcdccd460d9"
SCRATCH = Path("/tmp/nfl-current-corrections-89512ed-v3")
PREPARED = PACKAGE / "inputs"
env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", PYTHONDONTWRITEBYTECODE="1")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    assert not SCRATCH.exists(), "Keep prior failed evidence; choose a fresh scratch for another preparation."
    head = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], env=env).decode().strip()
    assert head == BASE, ("source moved", head)
    raw = subprocess.check_output(["git", "-C", str(SOURCE), "archive", "--format=tar", BASE], env=env)
    baseline = SCRATCH / "baseline"
    combined = SCRATCH / "combined"
    baseline.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        archive.extractall(baseline, filter="data")
    assert not (baseline / ".git").exists()
    shutil.copytree(baseline, combined)
    steps = []
    for name in ["website-audit-math-01-retain-field-goals.patch",
                 "website-audit-math-02-bind-classic-statistics.patch",
                 "website-audit-math-03-require-completed-finals.patch",
                 "website-current-b32b13d2123-rankings-side-guard.patch"]:
        patch = PREPARED / name
        result = subprocess.run(["patch", "--batch", "--no-backup-if-mismatch", "--fuzz=0", "-p1", "-i", str(patch)],
                                cwd=combined, env=env, text=True, capture_output=True, check=True)
        steps.append(dict(patch=name, sha256=sha(patch.read_bytes()), output=result.stdout.strip()))
    spec = importlib.util.spec_from_file_location("retained_proposal", PACKAGE / "verification/retained_proposal_definitions.py")
    proposal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proposal)
    app = (combined / "output/app.js").read_text()
    for name, text in proposal.proposed("05-half-ppr-missing-labels", {"output/app.js": app}, False).items():
        (combined / name).write_text(text)
    builder = (combined / "pull/build.py").read_text()
    assert builder.count('CACHE = ROOT / "data" / "cache"\n') == 1
    assert builder.count('path = CACHE / f"stats_{season}_{week:02d}.json"') == 1
    builder = builder.replace('CACHE = ROOT / "data" / "cache"\n',
        'CACHE = ROOT / "data" / "cache"\n# Normalized before the FG key was retained: never reuse the old R0 cache.\nSTATS_CACHE_VERSION = "stat-keys-fgm-v1"\n')
    builder = builder.replace('path = CACHE / f"stats_{season}_{week:02d}.json"',
        'path = CACHE / STATS_CACHE_VERSION / f"stats_{season}_{week:02d}.json"')
    (combined / "pull/build.py").write_text(builder)
    shutil.copyfile(PACKAGE / "verification/test_fgm_cache_contract.py", combined / "tests/test_fgm_cache_contract.py")
    # Exact main-specific half-PPR diff, preserving the new caption/ranking code.
    (PACKAGE / "half-ppr-89512ed.patch").write_text("".join(difflib.unified_diff(
        app.splitlines(keepends=True), (combined / "output/app.js").read_text().splitlines(keepends=True),
        fromfile="a/output/app.js", tofile="b/output/app.js")))
    source_hashes = {}
    changed = []
    for path in sorted(combined.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(combined).as_posix()
        old = baseline / name
        new_raw = path.read_bytes()
        if old.exists() and old.read_bytes() == new_raw:
            continue
        assert name.startswith(("pull/", "output/", "tests/", "tools/")) and not name.endswith((".orig", ".rej")), name
        target = PACKAGE / "files" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(new_raw)
        changed.append(name)
        old_raw = old.read_bytes() if old.exists() else b""
        source_hashes[name] = dict(preimage_sha256=sha(old_raw) if old.exists() else None,
                                   postimage_sha256=sha(new_raw), bytes=len(new_raw))
    diff = "".join("".join(difflib.unified_diff(
        (baseline / name).read_text().splitlines(keepends=True) if (baseline / name).exists() else [],
        (combined / name).read_text().splitlines(keepends=True),
        fromfile="a/" + name if (baseline / name).exists() else "/dev/null", tofile="b/" + name)) for name in changed)
    (PACKAGE / "combined-89512ed.patch").write_text(diff)
    verification = SCRATCH / "exact-application"
    shutil.copytree(baseline, verification)
    result = subprocess.run(["patch", "--batch", "--no-backup-if-mismatch", "--fuzz=0", "-p1", "-i", str(PACKAGE / "combined-89512ed.patch")],
                            cwd=verification, env=env, text=True, capture_output=True, check=True)
    assert "offset" not in result.stdout and "fuzz" not in result.stdout
    for name in changed:
        assert (verification / name).read_bytes() == (combined / name).read_bytes()
    record = dict(source_base=BASE, sourcebase89512ed=True, full_source_copy="DISPOSABLE_NO_GIT",
                  archive_sha256=sha(raw), changed_files=source_hashes, prepared_patch_applications=steps,
                  combined_patch_exact_application=result.stdout.strip(),
                  negative_count_main="NOT_APPLICABLE_REQUIRES_PRESENCE_AWARE_COMPONENT_CONTRACT",
                  stats_cache_version="stat-keys-fgm-v1", legacy_R0_cache_fallback=False,
                  website_worktree_modified=False, external_actions=False)
    (PACKAGE / "evidence/preparation.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(source_base=BASE, changed=changed, full_source_scratch=str(combined))))

if __name__ == "__main__":
    main()
