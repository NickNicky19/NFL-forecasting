"""Publish only derived lab state on its dedicated branch; never source feeds."""
import argparse
import hashlib
import json
from contextlib import nullcontext
import uuid
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile


def git(*args,cwd=None,capture=False):
    return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=capture).stdout


PUBLICATION_SCHEMA = "operational-publication-review-v2"


def publication_files(state):
    state = Path(state)
    result = {}
    for path in sorted(state.rglob("*")):
        if path.is_symlink():
            raise ValueError("publication state cannot contain symlinks")
        if (not path.is_file() or path.name in {".writer.lock", ".operational-storage-owner"}
                or path.name.startswith(".pending-")):
            continue
        result[path.relative_to(state).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def reviewed_publication(state, manifest_path, policy_sha256):
    """An explicit frozen content review is required before v2 Git publication."""
    if manifest_path is None:
        raise RuntimeError("v2 publication pending separately frozen content-review manifest; no Git publication authorized")
    manifest_path = Path(manifest_path)
    if any(path.is_symlink() for path in [manifest_path, *manifest_path.parents]):
        raise ValueError("publication manifest cannot use symlinks")
    document = json.loads(manifest_path.read_text())
    if (set(document) != {"schema_version", "review_state", "policy_sha256", "files"}
            or document["schema_version"] != PUBLICATION_SCHEMA
            or document["review_state"] != "ACCEPTED"
            or document["policy_sha256"] != policy_sha256
            or not isinstance(document["files"], dict)):
        raise ValueError("unsupported publication review manifest")
    for name, sha in document["files"].items():
        if not isinstance(name, str):
            raise ValueError("invalid publication path/hash allowlist")
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute()
                or relative.as_posix() != name or any(part in {".", ".."} for part in relative.parts)
                or "\\" in name or not isinstance(sha, str) or len(sha) != 64
                or any(char not in "0123456789abcdef" for char in sha)):
            raise ValueError("invalid publication path/hash allowlist")
    inventory=publication_files(state)
    if any(inventory.get(name) != sha for name, sha in document["files"].items()):
        raise ValueError("publication content differs from exact reviewed path/hash allowlist")
    return document["files"]


def validate_existing_public(root, ref, files):
    """Published paths are append-only; omitted index entries remain intact."""
    listing=subprocess.run(["git","ls-tree","-rlz",ref,"--","state"],cwd=root,
                           check=True,capture_output=True).stdout
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata,name=entry.split(b"\t",1)
        mode,kind,oid,size=metadata.split()
        relative=PurePosixPath(name.decode("utf-8"))
        local=PurePosixPath(*relative.parts[1:]).as_posix()
        if local not in files:
            continue
        if mode not in {b"100644",b"100755"} or kind != b"blob":
            raise ValueError("reviewed state conflicts with nonregular published path")
        if int(size)>200*1024*1024:
            raise ValueError("published state blob exceeds bounded read limit")
        body=subprocess.run(["git","cat-file","blob",oid.decode("ascii")],cwd=root,
                            check=True,capture_output=True).stdout
        if len(body)!=int(size) or hashlib.sha256(body).hexdigest()!=files[local]:
            raise ValueError("reviewed state would overwrite existing public evidence")


def stage_reviewed(target, files):
    # Bounded explicit arguments preserve every omitted remote index entry.
    names=["state/"+name for name in sorted(files)]
    for offset in range(0,len(names),64):
        git("--literal-pathspecs","add","--",*names[offset:offset+64],cwd=target)


def copy_state(state, destination, storage=None, *, files=None):
    """Copy legacy inputs or alias owned v2 bytes; never publish local controls."""
    state, destination = Path(state), Path(destination)
    ignored = {".writer.lock", ".operational-storage-owner"}
    if storage is None:
        shutil.copytree(state, destination, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(*ignored, ".pending-*"))
        return
    if files is None:
        raise RuntimeError("v2 state copy requires the reviewed publication allowlist")
    for name, sha in sorted(files.items()):
        storage.import_file(state / name, destination / name, expected_sha256=sha)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-policy",type=Path)
    parser.add_argument("--publication-manifest",type=Path)
    args=parser.parse_args()
    root=Path.cwd();state=root/"state"
    if args.source_policy is None:
        return persist(root,state)
    from nfl_lab.operational_sources import load_source_policy
    from nfl_lab.operational_storage import OperationalStorage
    from nfl_lab.operational_io import operational_io
    policy_path=args.source_policy.resolve()
    policy=load_source_policy(policy_path)
    files=reviewed_publication(state,args.publication_manifest,policy["_policy_sha256"])
    storage=OperationalStorage(root/"data",policy,state=state)
    with operational_io(storage,run_root=root/"runs"):
        return persist(root,state,storage=storage,policy_path=policy_path,files=files)


def persist(root,state,*,storage=None,policy_path=None,files=None):
    if not list(state.rglob("*.json.gz")):
        print("No derived state to persist");return
    branch="lab-state"
    if storage is None:
        staging=tempfile.TemporaryDirectory(prefix="nfl-lab-state-")
    else:
        target=storage.live_root/"publication-worktrees"/uuid.uuid4().hex/"repo"
        target.parent.mkdir(parents=True,exist_ok=True)
        staging=nullcontext(str(target))
    with staging as temp:
        target=Path(temp)
        try:
            remote=git("rev-parse","refs/remotes/origin/"+branch,capture=True).strip()
            git("worktree","add","--detach",*(["--no-checkout"] if storage is not None else []),str(target),remote)
            if storage is not None:
                validate_existing_public(root,remote,files)
                git("read-tree",remote,cwd=target)
        except subprocess.CalledProcessError:
            git("worktree","add","--detach",*(["--no-checkout"] if storage is not None else []),str(target),"HEAD")
            if storage is None:
                git("checkout","--orphan",branch,cwd=target)
                git("rm","-rf","--ignore-unmatch",".",cwd=target)
            else:
                git("read-tree","--empty",cwd=target)
        try:
            copy_state(state,target/"state",storage,files=files)
            if storage is None:git("add","state",cwd=target)
            else:stage_reviewed(target,files)
            if subprocess.run(["git","diff","--cached","--quiet"],cwd=target).returncode==0:
                print("Idempotent: no new evidence");return
            git("-c","user.name=NFL lab","-c","user.email=nfl-lab@users.noreply.github.com","commit","-m","Append immutable NFL lab observations",cwd=target)
            commit=git("rev-parse","HEAD",cwd=target,capture=True).strip()
            git("push","origin",f"HEAD:refs/heads/{branch}",cwd=target)
            observed=git("ls-remote","origin",f"refs/heads/{branch}",capture=True).split()[0]
            if observed!=commit:raise RuntimeError("remote state readback mismatch")
            publication=[sys.executable,"-m","nfl_lab.cli","publication","--state",str(state),"--publication-commit",commit]
            if storage is not None:
                publication += ["--source-policy",str(policy_path),"--output","runs/operational-v2/publication-result.json"]
            subprocess.run(publication,check=True)
            if storage is not None:
                print("Reviewed state published; new local publication-timing receipts await the next exact content review")
                return
            copy_state(state,target/"state",storage,files=files)
            git("add","state",cwd=target)
            if subprocess.run(["git","diff","--cached","--quiet"],cwd=target).returncode!=0:
                git("-c","user.name=NFL lab","-c","user.email=nfl-lab@users.noreply.github.com","commit","-m","Record remote publication timing",cwd=target)
                git("push","origin",f"HEAD:refs/heads/{branch}",cwd=target)
        finally:
            if storage is None:
                git("worktree","remove","--force",str(target))


if __name__=="__main__":main()
