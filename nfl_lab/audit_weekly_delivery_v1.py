"""Same-process owner-authorized weekly consume, verify, export and delivery.

The parent checks the current root/Actions context and supplies its existing
quota owner, authenticated read-only archive.Client factory and PRIOR public
policy/rights/R0 configuration. No JSON-to-live-acceptance shortcut exists.
Original private files and public history remain immutable. A source race after
publication retains all bytes and fails; it never rolls back or retries.
"""
from __future__ import annotations

from contextlib import contextmanager,redirect_stdout,redirect_stderr
from copy import deepcopy
from datetime import datetime,timezone
import gzip
import io
import os
from pathlib import Path
import re
import subprocess
import uuid
from urllib.parse import quote

from . import audit_weekly_archive_v1 as archive,audit_weekly_epoch_v1 as epoch
from . import audit_weekly_public_v1 as public,private_draft_store as store,gha_private_checkpoint as cp
from .operational_storage import OperationalStorage
from .operational_io import operational_io
from .owned_reference_batch import validate_owned_references
from tools import audit_weekly_public_v1 as public_tool,persist_state

VERSION="audit-weekly-delivery-v1"
CONFIG_KEYS={"policy","rights_authority","r0"}
DISCOVERY_HASH_KEYS={"archive_index_sha256","archive_files_sha256","reader_witness_sha256","epoch_sha256","choice_sha256"}
RECEIPT_KEYS={"schema_version","source_sha","run_id","root_go_sha256","policy_sha256","policy_registered_at_utc","workflow_sha256","recipe_registration_sha256",
    "rights_authority_sha256","r0_identity_sha256","origin_choice_sha256","feed_sha256","feed_bytes","rows","categories",
    "jobs","created_at","verified_at","fits","raw_or_models_public"}|DISCOVERY_HASH_KEYS


def require(value,code):
    if not value:raise store.StoreError(code)


def now():return datetime.now(timezone.utc)


def source_head(client,branch):
    """Exactly one bounded GET using the genuine current native client."""
    require(type(branch) is str and re.fullmatch(r"[A-Za-z0-9_./-]{1,160}",branch)
        and not any(p in {"",".",".."} for p in branch.split("/")),"CLOSED_DELIVERY_PRODUCER_BRANCH")
    # A changing query key prevents an intermediary from replaying the first
    # branch response during the post-publication race check.
    url=store.API+"/git/ref/heads/"+quote(branch,safe="/")+"?audit_weekly_delivery_nonce="+uuid.uuid4().hex
    client.allowed.add(url);value=client.json(url)
    require(type(value) is dict and value.get("ref")=="refs/heads/"+branch and value.get("object",{}).get("type")=="commit"
        and re.fullmatch(r"[a-f0-9]{40}",str(value["object"].get("sha"))),"ACTUAL_DELIVERY_PRODUCER_BRANCH_HEAD")
    return value["object"]["sha"]


class Quiet:
    def write(self,value):return len(value)
    def flush(self):pass


@contextmanager
def quiet_publisher(root):
    """Suppress Python and inherited Git/child stdout; never log library text."""
    previous=Path.cwd();saved=[];sink=os.open(os.devnull,os.O_WRONLY)
    try:
        for fd in (1,2):saved.append((fd,os.dup(fd)));os.dup2(sink,fd)
        os.chdir(root)
        with redirect_stdout(Quiet()),redirect_stderr(Quiet()):yield
    finally:
        os.chdir(previous)
        for fd,backup in saved:os.dup2(backup,fd);os.close(backup)
        os.close(sink)


def _typed_epoch(storage,aliases,at,expected_original_choice_sha256):
    required={"context/"+role+".json" for role in archive.CONTEXT}|{"context/public_policy.json",
        "runtime/WEEKLY_CHOICE.json","prepared/relocated_replay.json","r0/original_board.json"}
    require(required<=set(aliases),"FULL_ARCHIVED_DELIVERY_CONTEXT_REQUIRED")
    def doc(name,raw=False,cap=2 << 20):return archive.read_owned(storage,aliases[name],cap,raw=raw)
    original=doc("context/original_choice.json",True,epoch.CAP)
    require(store.sha(original)==expected_original_choice_sha256,"EXACT_PINNED_ORIGINAL_WEEKLY_CHOICE_BYTES")
    document=doc("context/epoch.json")
    # The old history anchor is recorded in the epoch's original metadata.
    # Do not invent it from a missing completion or grade/read old outcomes.
    history=document["original"]["history_binding"]
    restored=epoch.restore_epoch(document,original,doc("context/origin_witness.json",cap=4 << 20),
        doc("context/original_slate.json"),doc("context/original_catalog.json"),doc("context/original_policy.json"),
        history_binding=history,now=at)
    registered=epoch.bind_registration(restored,doc("context/epoch_registration.json"),now=at)
    choice_document=doc("runtime/WEEKLY_CHOICE.json")
    choice=epoch.EpochChoice(choice_document,public.feed.digest(choice_document));choice.verify(registered,at)
    # Verify archived relocation metadata without changing the frozen catalog.
    epoch.artifact_catalog(restored,doc("prepared/relocated_replay.json"))
    return registered,choice


def public_pair(storage,state,exported,live,policy,root_sha,origin_sha,reader_witness_sha256):
    """NEW V3-policy receipt, never an old V2 verifier/receipt impersonation."""
    live.verify();document=exported["document"];body=exported["body"];p=document["publication"]
    require(document["schema_version"]==public.feed.VERSION_V2 and document["state"]=="DERIVED_SELECTED_ONLY"
        and set(document)==public.feed.META_FIELDS|{"publication","publication_sha256"}
        and body==public.feed.canonical(document) and store.sha(body)==exported["sha256"] and len(body)<=public.feed.MAX_BYTES
        and len(document["rows"])==exported["rows"] and document["rows"]
        and all(set(row)==set(public.overlay.ROW_FIELDS) for row in document["rows"]),"EXACT_TYPED_NEW_PUBLIC_FEED_WIRE")
    require(document["producer_policy_sha256"]==policy["producer_policy_sha256"]==public.recipe_commitment(policy)
        and document["rights_authority_sha256"]==live.inputs["rights"]["authority_policy_sha256"]
        and document["r0_identity_sha256"]==public.feed.digest(live.inputs["r0"])
        and document["durability_receipt_sha256"]==public.feed.digest(live.record)
        and document["publication_sha256"]==public.feed.digest(p)
        and p["source_sha"]==policy["source_sha"] and p["run_id"]==live.record["exporter"]["run_id"]
        and p["authority_sha256"]==public.feed.digest(policy["publication_authority"])
        and p["version_catalog"]==live.inputs["catalog"].document
        and p["source_version_catalog_sha256"]==live.inputs["catalog"].sha256,"NEW_SOURCE_BOUND_RECIPE_LIVE_RIGHTS_AND_CATALOG")
    jobs={role:dict(job_id=live.record[key]["job_id"],api_job_id=live.record[key]["api_job_id"])
        for role,key in (("produce","producer"),("restore","restorer"),("consume","exporter"))}
    receipt=dict(schema_version=VERSION+"-public-receipt",source_sha=policy["source_sha"],run_id=p["run_id"],root_go_sha256=root_sha,
        policy_sha256=public.feed.digest(policy),policy_registered_at_utc=policy["registered_at_utc"],workflow_sha256=live.record["workflow_sha256"],
        recipe_registration_sha256=policy["producer_policy_sha256"],
        rights_authority_sha256=document["rights_authority_sha256"],r0_identity_sha256=document["r0_identity_sha256"],origin_choice_sha256=origin_sha,
        archive_index_sha256=live.record["archive_index_sha256"],archive_files_sha256=live.record["archive_files_sha256"],
        reader_witness_sha256=reader_witness_sha256,epoch_sha256=live.inputs["terminal"]["epoch_sha256"],choice_sha256=live.inputs["terminal"]["choice_sha256"],
        feed_sha256=store.sha(body),feed_bytes=len(body),rows=len(document["rows"]),categories=sorted({r["category"] for r in document["rows"]}),
        jobs=jobs,created_at=document["created_at"],verified_at=live.record["accepted_at"],fits=0,raw_or_models_public=False)
    require(set(receipt)==RECEIPT_KEYS and receipt["workflow_sha256"]==policy["workflow_sha256"]
        and public.feed.utc(receipt["policy_registered_at_utc"])<=public.feed.utc(live.inputs["source"]["actual_source_started_at"])
        and all(public.feed.h(receipt[k]) for k in DISCOVERY_HASH_KEYS)
        and all(set(v)=={"job_id","api_job_id"} and type(v["api_job_id"]) is int and v["api_job_id"]>0
        for v in jobs.values()),"CLOSED_HASH_CLOCK_JOB_CATEGORY_PUBLIC_RECEIPT")
    plain=store.canonical(receipt);require(len(plain)<=64 << 10,"PUBLIC_DELIVERY_RECEIPT_BOUND")
    encoded=gzip.compress(plain,mtime=0)
    stamp=public.feed.utc(document["created_at"]).strftime("%Y%m%dT%H%M%S.%fZ")
    feed_path=f"public/weekly-adaptive-v1/{document['season']}-W{document['week']:02d}/{stamp}--{store.sha(body)}.json"
    receipt_path="public/weekly-adaptive-v1/receipts/"+store.sha(body)+".json.gz"
    payloads={feed_path:body,receipt_path:encoded};files={n:store.sha(b) for n,b in payloads.items()}
    require(persist_state.public_export_names(files)==(feed_path,receipt_path),"CLOSED_TWO_PUBLIC_DELIVERY_PATHS")
    with storage.transaction():storage._require(sum(len(b) for b in payloads.values())+(64 << 10))
    for name,payload in payloads.items():storage.write_bytes(Path(state)/name,payload)
    validate_owned_references(storage,{str(Path(state)/name):h for name,h in files.items()})
    require(archive.read_owned(storage,cp.binding(Path(state)/feed_path),public.feed.MAX_BYTES,raw=True)==body,"PUBLIC_FEED_EXACT_BYTE_READBACK")
    saved=archive.read_owned(storage,cp.binding(Path(state)/receipt_path),64 << 10,raw=True)
    with gzip.GzipFile(fileobj=io.BytesIO(saved)) as stream:decoded=stream.read((64 << 10)+1)
    require(decoded==plain and cp.strict_json(decoded)==receipt,"NEW_PUBLIC_RECEIPT_EXACT_BYTE_READBACK")
    return files,receipt


def deliver(reader_handoff,package,factory,storage,output,root_go_sha256,pending_census,configuration,root_repository,*,
        expected_source_sha,expected_original_choice_sha256,source_policy_path=None,root_go=None,at=None,
        source_check=None,publisher=None,before_publication=None,clock=now):
    """Return only a public-safe final marker; transport injection is in factory.

    source_check/publisher are explicit fictional-test seams. Production uses
    source_head and the unchanged persist_state.persist(metadata_policy=True).
    Parent calls only after validating go.publication is True. If supplied,
    root_go is independently checked too. at is a start-clock lower bound,
    never a frozen clock for later live verification or publication.
    """
    try:
        if at is not None:require(public.feed.utc(at if type(at) is str else at.isoformat())<=clock(),"ACTUAL_DELIVERY_START_CLOCK")
        if root_go is not None:
            require(type(root_go) is dict and root_go.get("publication") is True and root_go.get("approved") is True
                and root_go.get("repository")==store.REPO and root_go.get("source_sha")==expected_source_sha
                and store.sha(store.canonical(root_go))==root_go_sha256,"EXPLICIT_ROOT_AUTHORIZED_PUBLIC_DELIVERY")
            recurring=root_go.get("operation")=="RECURRING_CAPTURE"
            require(recurring==callable(before_publication),"RECURRING_PUBLICATION_REQUIRES_NATIVE_GRADING_DELIVERY")
        elif before_publication is not None:
            require(callable(before_publication) and source_check is not None and publisher is not None,
                "PRODUCTION_GRADING_CALLBACK_REQUIRES_CURRENT_ROOT")
        return _deliver(storage=storage,factory=factory,qualified_runtime=package,root_go_sha256=root_go_sha256,
            reader_handoff=reader_handoff,publication=configuration,expected_source_sha=expected_source_sha,
            expected_original_choice_sha256=expected_original_choice_sha256,repository_root=root_repository,output=output,
            source_policy_path=Path(root_repository)/"config/operational-source-policy-v2.json" if source_policy_path is None else source_policy_path,
            pending_census=pending_census,source_check=source_check,publisher=publisher,
            before_publication=before_publication,clock=clock)
    except (store.StoreError,public.PublicError,epoch.EpochError) as error:
        reason=str(error)
        raise store.StoreError(reason if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",reason) else "PUBLIC_DELIVERY_UPSTREAM_GUARD") from None
    except Exception:
        raise store.StoreError("PUBLIC_DELIVERY_UPSTREAM_GUARD") from None


def _deliver(*,storage,factory,qualified_runtime,root_go_sha256,reader_handoff,publication,
        expected_source_sha,expected_original_choice_sha256,repository_root,output,source_policy_path,pending_census,
        source_check,publisher,before_publication,clock):
    require(isinstance(storage,OperationalStorage) and storage.limit_bytes==512 << 20,"EXISTING_SHARED_DELIVERY_STORAGE_OWNER_REQUIRED")
    require(type(publication) is dict and set(publication)==CONFIG_KEYS and re.fullmatch(r"[a-f0-9]{40}",str(expected_source_sha))
        and re.fullmatch(r"[a-f0-9]{64}",str(expected_original_choice_sha256))
        and re.fullmatch(r"[a-f0-9]{64}",str(root_go_sha256)),"EXPLICIT_PINNED_PUBLIC_DELIVERY_CONFIGURATION")
    at=clock();policy=deepcopy(publication["policy"]);r0=deepcopy(publication["r0"])
    public.policy_check(policy,at=at.isoformat())
    require(policy["source_sha"]==expected_source_sha and policy["origin_choice_sha256"]==expected_original_choice_sha256
        and policy["jobs"]==reader_handoff["archive"]["jobs"]
        and type(publication["rights_authority"]) is dict and public.feed.digest(publication["rights_authority"]) in policy["rights_authorities"]
        and public.feed.digest(r0) in policy["r0_identities"],
        "PINNED_PRIOR_PUBLIC_POLICY_RIGHTS_R0_AND_ORIGINAL_CHOICE")
    workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/"+policy["source_branch"]
    require(reader_handoff["archive"]["source_sha"]==expected_source_sha and reader_handoff["archive"]["root_go_sha256"]==root_go_sha256,
        "SAME_REGISTERED_PUBLIC_ARCHIVE_SOURCE_AND_ROOT")
    policy_path=Path(source_policy_path)
    require(store.sha(store.read_local(policy_path,2 << 20))==cp.POLICY_SHA==policy["source_policy_sha256"],"FROZEN_DELIVERY_SOURCE_POLICY")
    output=archive.fresh(storage,output);clients=[];identity=None
    if publisher is None:
        require(Path(repository_root).resolve()==Path(public.__file__).resolve().parents[1]
            and subprocess.check_output(["git","rev-parse","HEAD"],cwd=repository_root,text=True,stderr=subprocess.DEVNULL).strip()==expected_source_sha,
            "ACTUAL_PUBLICATION_REPOSITORY_SOURCE_REQUIRED")
    def native(operation):
        nonlocal identity
        require(operation=="restore","DELIVERY_CONSUME_GET_ONLY")
        require(len(clients)<archive.MAX_CLIENTS,"DELIVERY_NATIVE_CLIENT_CAP")
        c=factory(operation)
        require(isinstance(c,archive.Client) and c.readonly is True and c.binding==qualified_runtime["binding"],"GENUINE_READ_ONLY_ARCHIVE_CLIENT_REQUIRED")
        actual=archive.checked(c,policy["jobs"]["consume"])
        require(actual["source_sha"]==expected_source_sha and actual["workflow_ref"]==workflow_ref
            and (identity is None or identity==actual),"ONE_CURRENT_EXPORTER_PROCESS_FOR_CONSUME_AND_VERIFY")
        identity=actual;clients.append(c);return c
    first=native("restore");check=source_head if source_check is None else source_check
    require(check(first,policy["source_branch"])==expected_source_sha,"PRODUCER_SOURCE_CHANGED_BEFORE_DELIVERY")
    used=False
    def reuse(operation):
        nonlocal used
        if not used:used=True;return first
        return native(operation)
    # Direct call: no JSON receipt or subprocess can recreate LiveAcceptance.
    consumed=archive.consume(reader_handoff,reuse,qualified_runtime,storage=storage,output=output/"consumed",
        root_go_sha256=root_go_sha256,pending_census=pending_census)
    client=clients[-1];aliases=consumed["aliases"]
    require(cp.client_identity(client)==consumed["current"]==identity,"CONSUMED_PROOFS_MUST_MATCH_CURRENT_EXPORTER")
    require(archive.read_owned(storage,aliases["context/public_policy.json"],128 << 10)==policy,"EXACT_ARCHIVED_BEFORE_VALUES_PUBLIC_POLICY")
    registered,choice=_typed_epoch(storage,aliases,clock(),expected_original_choice_sha256)
    board_body=archive.read_owned(storage,aliases["r0/original_board.json"],public.feed.MAX_BYTES,raw=True);board=cp.strict_json(board_body)
    rights=dict(schema_version="weekly-derived-selected-rights-v1",state="SOURCE_REVIEW_ACCEPTED",authority_kind="REGISTERED_SOURCE_RIGHTS_POLICY",
        authority_policy_sha256=public.feed.digest(publication["rights_authority"]),selected_sha256=aliases["runtime/selected.jsonl.gz"]["sha256"],
        source_policy_sha256=policy["source_policy_sha256"],scope="SELECTED_DERIVED_ONLY",public_fields=policy["public_fields"],reviewed_at=clock().isoformat())
    live=public.verify_live(client,consumed,qualified_runtime,policy,rights,r0,board,registered,choice,storage=storage,
        pending_census=pending_census,at=clock().isoformat(),board_body=board_body)
    exported=public_tool.run(live,at=clock().isoformat());document=exported["document"]
    state=storage.register_root(output/"public-state")
    require(consumed["witness_descriptor"]==reader_handoff["witness_descriptor"],"EXACT_VERIFIED_READER_WITNESS_DESCRIPTOR")
    files,public_receipt=public_pair(storage,state,exported,live,policy,root_go_sha256,expected_original_choice_sha256,
        consumed["witness_descriptor"]["entry"]["payload"]["sha256"])
    feed_path,receipt_path=persist_state.public_export_names(files)
    require(len(files)==2 and files[feed_path]==exported["sha256"],"EXACT_TWO_DERIVED_PUBLIC_DELIVERY_FILES")
    safe=dict(schema_version=VERSION+"-receipt",state="PUBLIC_FILES_PREPARED",source_sha=expected_source_sha,run_id=identity["run_id"],
        root_go_sha256=root_go_sha256,feed_path=feed_path,feed_sha256=files[feed_path],export_receipt_path=receipt_path,export_receipt_sha256=files[receipt_path],
        policy_sha256=public.feed.digest(policy),policy_registered_at_utc=public_receipt["policy_registered_at_utc"],
        workflow_sha256=public_receipt["workflow_sha256"],origin_choice_sha256=expected_original_choice_sha256,
        jobs={role:dict(job_id=ident["job_id"],api_job_id=ident["api_job_id"]) for role,ident in
            (("produce",consumed["archive"]["producer"]),("restore",consumed["restorer_witness"]["restorer"]),("consume",identity))},
        categories=sorted({row["category"] for row in document["rows"]}),created_at=document["created_at"],verified_at=live.record["accepted_at"],
        fits=0,raw_or_models_public=False)
    safe.update({key:public_receipt[key] for key in DISCOVERY_HASH_KEYS})
    archive.write(storage,output/"DELIVERY_PUBLISH_INTENT.json",safe)
    require(check(client,policy["source_branch"])==expected_source_sha,"PRODUCER_SOURCE_CHANGED_BEFORE_PUBLICATION")
    grading=None
    if before_publication is not None:
        try:
            grading=before_publication(deepcopy(public_receipt))
            require(type(grading) is dict and set(grading)=={"schema_version","feed_sha256","sidecar_sha256",
                "sidecar_path","evidence_descriptor_sha256"} and grading["schema_version"]=="audit-weekly-grading-delivery-v1"
                and grading["feed_sha256"]==files[feed_path]
                and all(public.feed.h(grading[k]) for k in ("sidecar_sha256","evidence_descriptor_sha256"))
                and grading["sidecar_path"]=="controller-v1/grade-checkpoints/"+files[feed_path]+".json.gz",
                "CLOSED_SAME_FEED_GRADING_DELIVERY_REQUIRED")
        except Exception:
            archive.write(storage,output/"DELIVERY_FAILED.json",dict(safe,
                state="GRADING_DELIVERY_FAILED_FEED_NOT_PUBLISHED",failed_at=clock().isoformat()))
            raise store.StoreError("GRADING_DELIVERY_FAILED_FEED_NOT_PUBLISHED") from None
        # The callback performs durable private/public metadata writes. Its
        # completion is not permission to publish from a source that advanced.
        require(check(client,policy["source_branch"])==expected_source_sha,
            "PRODUCER_SOURCE_CHANGED_AFTER_GRADING_BEFORE_FEED")
    publish=persist_state.persist if publisher is None else publisher
    try:
        with quiet_publisher(repository_root),operational_io(storage,run_root=Path(repository_root)/"runs"):
            publish(Path(repository_root),Path(state),storage=storage,policy_path=policy_path,files=files,metadata_policy=True)
    except Exception:
        archive.write(storage,output/"DELIVERY_FAILED.json",dict(safe,state="PUBLICATION_FAILED_BYTES_RETAINED",failed_at=clock().isoformat()))
        raise store.StoreError("PUBLIC_DELIVERY_PUBLICATION_FAILED_BYTES_RETAINED") from None
    try:observed=check(client,policy["source_branch"])
    except Exception:
        archive.write(storage,output/"DELIVERY_FAILED.json",dict(safe,state="SOURCE_RECHECK_UNRESOLVED_AFTER_PUBLICATION_BYTES_RETAINED",failed_at=clock().isoformat()))
        raise store.StoreError("PRODUCER_SOURCE_RECHECK_UNRESOLVED_AFTER_PUBLICATION") from None
    if observed!=expected_source_sha:
        archive.write(storage,output/"DELIVERY_FAILED.json",dict(safe,state="SOURCE_RACE_AFTER_PUBLICATION_BYTES_RETAINED",observed_source_sha=observed,failed_at=clock().isoformat()))
        raise store.StoreError("PRODUCER_SOURCE_CHANGED_AFTER_PUBLICATION")
    receipt=dict(safe,state="PUBLIC_DERIVED_DELIVERY_COMPLETE",published_at=clock().isoformat(),source_head_verified_before_after=True)
    if grading is not None:receipt["grading_checkpoint"]=grading
    ref=archive.write(storage,output/"DELIVERY_RECEIPT.json",receipt)
    result=dict(state=receipt["state"],feed_path=feed_path,feed_sha256=files[feed_path],export_receipt_path=receipt_path,
        export_receipt_sha256=files[receipt_path],delivery_receipt_sha256=ref["sha256"],source_sha=expected_source_sha,run_id=identity["run_id"],
        categories=receipt["categories"],jobs=receipt["jobs"],published_at=receipt["published_at"],fits=0,raw_or_models_public=False,
        policy_registered_at_utc=receipt["policy_registered_at_utc"],workflow_sha256=receipt["workflow_sha256"],
        **{key:public_receipt[key] for key in DISCOVERY_HASH_KEYS})
    if grading is not None:result["grading_checkpoint"]=grading
    return result
