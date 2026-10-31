"""Publish only derived lab state on its dedicated branch; never source feeds."""
import argparse
import gzip
import hashlib
import io
import json
from contextlib import nullcontext
from datetime import datetime, timezone
import re
import uuid
import zlib
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile


def git(*args,cwd=None,capture=False):
    return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=capture).stdout


PUBLICATION_SCHEMA = "operational-publication-review-v2"
PUBLIC_FEED_SCHEMAS = {
    "weekly-derived-selected-feed-v1": "831604c59ab80d979620b935ab50496d6f28ff989849141749b31a6a788c20f8",
    "weekly-derived-selected-feed-v2": "68709b6cb3d9a420835fcd74ee5dd5392ae83c36f54cce985fcd0fa47c372db5",
}


def public_export_names(files):
    if not isinstance(files,dict) or len(files)!=2:
        raise ValueError("public export requires its exact feed and genuine receipt map")
    feeds=[n for n in files if re.fullmatch(r"public/weekly-adaptive-v1/\d{4}-W(?:0[1-9]|1\d|2[0-2])/\d{8}T\d{6}\.\d{6}Z--[a-f0-9]{64}\.json",n)]
    receipts=[n for n in files if re.fullmatch(r"public/weekly-adaptive-v1/receipts/[a-f0-9]{64}\.json\.gz",n)]
    if len(feeds)!=1 or len(receipts)!=1:
        raise ValueError("only the closed derived public feed and receipt paths may publish")
    return feeds[0],receipts[0]


def v5_public_export_names(files):
    """Exactly the unchanged legacy pair plus one separate point-display pair."""
    from nfl_lab.weekly_mae_display_archive_v1 import public_names
    if type(files) is not dict or len(files)!=4:
        raise ValueError("V5 atomic publication requires exactly four public files")
    legacy={n:h for n,h in files.items() if n.startswith("public/weekly-adaptive-v1/")}
    point={n:h for n,h in files.items() if n.startswith("public/stat-point-mae-v1/")}
    if set(legacy)|set(point)!=set(files):
        raise ValueError("closed V5 public inventory required")
    return public_export_names(legacy),public_names(point)


def validate_v5_public_export(state,files,source_policy_sha256):
    from nfl_lab.weekly_mae_display_archive_v1 import validate_public_pair,read_bounded
    legacy,point=v5_public_export_names(files)
    for name,expected in files.items():
        body=read_bounded(Path(state)/name,4 << 20 if name.endswith(".json") else 64 << 10)
        if hashlib.sha256(body).hexdigest()!=expected:
            raise ValueError("V5 publication differs from exact owned file inventory")
    document,receipt=validate_public_pair(read_bounded(Path(state)/point[0],4 << 20),read_bounded(Path(state)/point[1],64 << 10))
    from nfl_lab import audit_weekly_delivery_v1 as legacy_delivery
    from nfl_lab.gha_private_checkpoint import strict_json
    old_body=read_bounded(Path(state)/legacy[0],4 << 20);old_feed=strict_json(old_body)
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
    old_raw=decoder.decompress(read_bounded(Path(state)/legacy[1],64 << 10),(64 << 10)+1)
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(old_raw)>64 << 10:
        raise ValueError("V5 requires exact bounded genuine legacy receipt")
    old_receipt=strict_json(old_raw)
    common=("source_sha","run_id","root_go_sha256","workflow_sha256","jobs","archive_index_sha256","archive_files_sha256","reader_witness_sha256")
    if (type(old_receipt) is not dict or set(old_receipt)!=legacy_delivery.RECEIPT_KEYS
            or old_receipt["schema_version"]!=legacy_delivery.VERSION+"-public-receipt"
            or any(old_receipt[k]!=receipt[k] for k in common)
            or old_receipt["feed_sha256"]!=files[legacy[0]] or old_receipt["feed_bytes"]!=len(old_body)
            or old_receipt["rows"]!=len(old_feed["rows"]) or old_receipt["created_at"]!=old_feed["created_at"]
            or (old_feed["season"],old_feed["week"])!=(document["season"],document["week"])
            or Path(legacy[1]).name!=files[legacy[0]]+".json.gz"):
        raise ValueError("V5 legacy and point pair must share actual source/run/jobs/Root/archive and period")
    stamp=datetime.fromisoformat(document["created_at"].replace("Z","+00:00")).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    if (Path(point[0]).name.split("--")[0]!=stamp
            or Path(point[0]).parent.name!=f"{document['season']}-W{document['week']:02d}"
            or Path(point[0]).stem.split("--")[1]!=files[point[0]]
            or receipt["legacy_feed_sha256"]!=files[legacy[0]]
            or receipt["source_policy_sha256"]!=source_policy_sha256):
        raise ValueError("V5 point receipt must bind coherent legacy feed and frozen policy")
    return files


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


def reviewed_publication(state, manifest_path, policy_sha256, *, selected_only=False):
    """An explicit frozen content review is required before v2 Git publication."""
    if manifest_path is None:
        raise RuntimeError("v2 publication pending separately frozen content-review manifest; no Git publication authorized")
    manifest_path = Path(manifest_path)
    if any(path.is_symlink() for path in [manifest_path, *manifest_path.parents]):
        raise ValueError("publication manifest cannot use symlinks")
    if selected_only:
        from nfl_lab.private_draft_store import read_local
        document=json.loads(read_local(manifest_path,1<<20))
    else:
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
    if selected_only:
        public_export_names(document["files"])  # Scope check precedes every candidate payload read.
        inventory={name:hashlib.sha256(read_local(Path(state)/name,4<<20)).hexdigest() for name in document["files"]}
    else:
        inventory=publication_files(state)
    if any(inventory.get(name) != sha for name, sha in document["files"].items()):
        raise ValueError("publication content differs from exact reviewed path/hash allowlist")
    return document["files"]


def validate_public_export(state, files, public_policy, source_policy_sha256):
    """Only the exporter-owned derived feed and genuine receipt, never private state."""
    from jsonschema import Draft202012Validator, FormatChecker
    from nfl_lab.private_draft_store import read_local
    name,receipt_name=public_export_names(files);body=read_local(Path(state)/name,4<<20)
    if hashlib.sha256(body).hexdigest()!=files[name] or Path(name).stem.split("--")[1]!=files[name]:
        raise ValueError("public feed physical hash/filename differs")
    document=json.loads(body);json.dumps(document,allow_nan=False)
    version=document.get("schema_version");expected=PUBLIC_FEED_SCHEMAS.get(version)
    if expected is None:raise ValueError("unsupported closed public feed schema")
    schema_path=Path(__file__).resolve().parents[1]/"schemas"/(version+".json")
    schema_body=read_local(schema_path,1<<20)
    if hashlib.sha256(schema_body).hexdigest()!=expected:raise ValueError("public schema code pin differs")
    schema=json.loads(schema_body);Draft202012Validator(schema,format_checker=FormatChecker()).validate(document)
    stamp=datetime.fromisoformat(document["created_at"].replace("Z","+00:00")).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    if (Path(name).parent.name!=f"{document['season']}-W{document['week']:02d}" or Path(name).name.split("--")[0]!=stamp
            or any(r["source_policy_sha256"]!=source_policy_sha256 for r in document["rows"])):
        raise ValueError("public feed period/clock/source policy differs")
    compressed=read_local(Path(state)/receipt_name,64<<10)
    if hashlib.sha256(compressed).hexdigest()!=files[receipt_name] or Path(receipt_name).name!=files[receipt_name]+".json.gz":
        raise ValueError("genuine public export receipt physical hash differs")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:raw=stream.read((64<<10)+1)
    if len(raw)>64<<10:raise ValueError("public export receipt decoded bound exceeded")
    receipt=json.loads(raw)
    fields={"schema_version","authority_kind","human_approval","policy_sha256","feed_sha256","feed_bytes","rows","created_at","public_fields"}
    from nfl_lab.weekly_public_feed import digest
    if (not isinstance(receipt,dict) or set(receipt)!=fields
            or receipt["schema_version"]!="weekly-derived-export-receipt-v1"
            or receipt["authority_kind"]!="AUTOMATED_REGISTERED_DERIVED_POLICY" or receipt["human_approval"] is not False
            or receipt["policy_sha256"]!=digest(public_policy) or receipt["feed_sha256"]!=files[name]
            or receipt["feed_bytes"]!=len(body) or receipt["rows"]!=len(document["rows"])
            or receipt["created_at"]!=document["created_at"] or receipt["public_fields"]!=public_policy["public_fields"]
            or set(receipt["public_fields"])!=set(schema["properties"]["rows"]["items"]["required"])):
        raise ValueError("genuine automated export receipt binding differs")
    return files


def persist_public_export(root, plan_path, plan_sha256, *, storage=None):
    """Compose the existing publisher with one already registered export owner."""
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from nfl_lab.private_draft_store import read_local
    from nfl_lab.frozen_source_policy import load_frozen_source_policy as load_source_policy
    from nfl_lab.operational_io import operational_io
    def read_ref(ref):
        body=read_local(ref["path"],1<<20)
        if len(body)!=ref["bytes"] or hashlib.sha256(body).hexdigest()!=ref["sha256"]:
            raise ValueError("exact public export metadata reference required")
        return body
    body=read_local(plan_path,1<<20)
    if hashlib.sha256(body).hexdigest()!=plan_sha256:raise ValueError("exact public export plan required")
    plan=json.loads(body)
    if (plan.get("schema_version")!="weekly-public-feed-export-plan-v1" or plan.get("execution_authorized") is not True
            or plan.get("authority_kind")!="AUTOMATED_REGISTERED_DERIVED_POLICY"
            or plan.get("registration_policy_sha256")!=plan.get("policy",{}).get("sha256")):
        raise ValueError("registered export plan required; no new review authority")
    if not plan.get("publication_manifest"):raise ValueError("genuine reviewed publication manifest required")
    public_policy=json.loads(read_ref(plan["policy"]));read_ref(plan["source_policy"])
    policy_path=Path(plan["source_policy"]["path"]);policy=load_source_policy(policy_path)
    if public_policy["source_policy_sha256"]!=policy["_policy_sha256"]:raise ValueError("public export source policy differs")
    cache=Path(plan["cache_root"]).absolute();state=Path(plan["state_root"]).absolute()
    if storage is None:
        # Reopen only the export job's existing owner. Never initialize root/data.
        read_local(cache/"operational-storage-v2"/"registry.json",1<<20)
        from nfl_lab.operational_storage import OperationalStorage
        storage=OperationalStorage(cache,policy)
    if Path(storage.cache).absolute()!=cache:raise ValueError("public export must reuse its original shared quota owner")
    storage.validate_reference(plan["publication_manifest"])
    files=reviewed_publication(state,plan["publication_manifest"],policy["_policy_sha256"],selected_only=True)
    validate_public_export(state,files,public_policy,policy["_policy_sha256"])
    for name,expected in files.items():storage.validate_reference(state/name,expected_sha256=expected)
    with operational_io(storage,run_root=Path(root)/"runs"):
        return persist(Path(root),state,storage=storage,policy_path=policy_path,files=files,metadata_policy=True)


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


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-policy",type=Path)
    parser.add_argument("--publication-manifest",type=Path)
    parser.add_argument("--public-export-plan",type=Path,help="Reuse an authorized derived export's exact owner, state and reviewed two-file map")
    parser.add_argument("--public-export-plan-sha256")
    args=parser.parse_args(argv)
    root=Path.cwd();state=root/"state"
    if args.public_export_plan is not None or args.public_export_plan_sha256 is not None:
        if (args.public_export_plan is None or args.public_export_plan_sha256 is None
                or args.source_policy is not None or args.publication_manifest is not None):
            parser.error("public export requires its plan and exact SHA only; policy/manifest come from that plan")
        return persist_public_export(root,args.public_export_plan,args.public_export_plan_sha256)
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


def persist(root,state,*,storage=None,policy_path=None,files=None,metadata_policy=False,v5_metadata_policy=False):
    if v5_metadata_policy:
        if metadata_policy or storage is None or policy_path is None:
            raise ValueError("explicit V5 metadata mode requires one quota owner and frozen source policy")
        from nfl_lab.frozen_source_policy import load_frozen_source_policy
        validate_v5_public_export(state,files,load_frozen_source_policy(policy_path)["_policy_sha256"])
    if metadata_policy:
        if storage is None or policy_path is None:raise ValueError("frozen public metadata publication requires its quota owner and policy")
        public_export_names(files)
    if not list(state.rglob("*.json.gz")):
        print("No derived state to persist");return
    if storage is None:
        files=publication_files(state)
    elif files is None:
        raise RuntimeError("v2 publication requires its exact reviewed file map")
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
            from nfl_lab.publication_scope import scope_document
            if metadata_policy or v5_metadata_policy:
                from nfl_lab.frozen_source_policy import load_frozen_source_policy as load_source_policy
            else:
                from nfl_lab.operational_sources import load_source_policy
            policy_sha=load_source_policy(policy_path)["_policy_sha256"] if storage is not None else None
            scope=scope_document(commit,files,verified_remote_commit=observed,policy_sha256=policy_sha)
            publication=[sys.executable,"-m","nfl_lab.cli","publication","--root",str(root),"--state",str(state),"--publication-commit",commit,"--publication-scope-stdin"]
            if storage is not None:
                publication += ["--cache",str(storage.cache),"--source-policy",str(policy_path),"--output","runs/operational-v2/publication-result.json"]
                if metadata_policy or v5_metadata_policy:publication += ["--frozen-public-policy"]
            subprocess.run(publication,check=True,input=json.dumps(scope),text=True)
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
