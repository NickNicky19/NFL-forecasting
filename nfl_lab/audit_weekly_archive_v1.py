"""Complete private weekly capture transport; no inference or publication.

Original controls and physical hashes stay unchanged. Relocation is a separate
map, never a fabricated old receipt. The parent authenticates origin/epoch and
rights. This module authenticates actual jobs, qualified storage and native
transport proofs. Models and the raw HTTP corpus are not capture-archive files.
"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import gzip
import io
import json
import os
from pathlib import Path
import re

from . import private_draft_store as store, owner_bootstrap_bundle as codec
from . import gha_private_checkpoint as cp, owner_private_bootstrap as owner
from . import operational_failure_v1 as failure, audit_private_rotation_v1 as rotation
from .owned_reference_batch import validate_owned_references
from .operational_storage import OperationalStorage, _OWNER

VERSION = "audit-weekly-archive-v1"
RUNTIME = "audit-weekly-runtime-v1"
INDEX_PLAIN_CAP, INDEX_CAP = 1 << 20, 512 << 10
ENTRY_CAP, WITNESS_CAP = 16 << 10, 256 << 10
FAILURE_RESERVE = failure.PACKAGE_CAP + ENTRY_CAP
MAX_GROUPS, MAX_FILES, MAX_CLIENTS = 8, 512, 10
FAILURE_OBSERVATIONS_NAME = "failed/reference/SOURCE_OBSERVATIONS_BUNDLE.json"
FAILURE_OBSERVATIONS_SCHEMA = "audit-weekly-hosted-v2-original-source-observations-bundle"
SEMANTIC_CAP = 128 << 20
LIMITS = dict(wall_seconds=180, CPU_seconds=120, address_space_bytes=512 << 20,
    global_bytes=512 << 20, runtime_bytes=32 << 20, asset_bytes=8 << 20,
    groups=8, native_clients=10, HTTP_per_client=40, fits=0, retries=0)
CONTEXT = {"epoch", "epoch_registration", "original_choice", "origin_witness", "original_slate",
    "original_catalog", "original_policy", "retained_models", "prepared", "source"}
OPERATIONS_CONTEXT = {"ops_population", "ops_roles", "ops_schedule", "canonical_weekly_choice", "capture_scope"}
OPERATIONS_HISTORY_CONTEXT = {"ops_previous_checkpoint_sidecar", "ops_previous_public_receipt"}
CONTROL_FILES = {"CONSUMED.json", "RUNTIME_RECIPE.json", "WEEKLY_CHOICE.json", "ARTIFACT_CATALOG.json",
    "SELECTED_VERSION_CATALOG.json", "POPULATION.json", "MODEL_ATTEMPTS.json", "FINISHED.json",
    "queries.parquet", "quarantine.parquet", "no_remaining_game.parquet", "IDENTITY_BRIDGE.json",
    "features.parquet", "features.capture.json", "selected.jsonl.gz", "selected.jsonl.completion.json",
    "CANDIDATES.json", "EXPORT_INPUTS.json"}
CANDIDATE_NAMES = {f"candidates/{t}/{m}{suffix}" for t,_,m in cp.JOBS for suffix in (".jsonl.gz", ".jsonl.completion.json")}
STATUS_NAMES = {f"model-status/{t}-{m}.json" for t,_,m in cp.JOBS}
HANDOFF_KEYS = {"schema_version","repository","source_sha","run_id","root_go_sha256","producer",
    "runtime_binding","index_descriptor","files_sha256","archive_state","jobs"}
INDEX_KEYS = {"schema_version","repository","source_sha","run_id","root_go_sha256","producer","producer_proof",
    "created_at","runtime_binding_sha256","qualification_sha256","files","files_sha256","groups","census",
    "archive_state","jobs","admission","pending_reservations"}
PIN_PATHS = ("nfl_lab/audit_weekly_archive_v1.py","tools/audit_weekly_archive_v1.py",
    "nfl_lab/owner_bootstrap_bundle.py","nfl_lab/private_draft_store.py","nfl_lab/private_draft_probe_helpers.py",
    "nfl_lab/gha_private_checkpoint.py","nfl_lab/owner_private_bootstrap.py","nfl_lab/operational_storage.py",
    "nfl_lab/owned_reference_batch.py","nfl_lab/operational_failure_v1.py","nfl_lab/audit_private_rotation_v1.py",
    "nfl_lab/audit_weekly_runtime_v1.py","nfl_lab/audit_weekly_epoch_v1.py","tools/private_draft_store_v2.py",
    "nfl_lab/audit_reference_capture_v1.py","tools/audit_process_guard_v1.py",".github/workflows/lab.yml","config/private-draft-storage-v2.json",
    "config/weekly-owner-private-bootstrap-v1.json","config/operational-source-policy-v2.json")


def require(ok, code):
    if not ok: raise store.StoreError(code)


def now(): return datetime.now(timezone.utc).isoformat()


def pins():
    root=Path(__file__).resolve().parents[1]
    return {p:store.sha(store.read_local(root/p,2 << 20)) for p in PIN_PATHS}


def capture_groups(files):
    """Deterministic bounded packing of every required immutable file.

    The codec's lexical next-fit order can exhaust eight groups even when the
    same full census fits. Balance larger encoded members across a bounded
    number of groups, keeping the codec, file-count and inflated-size bounds. This
    chooses a finite packing, never promises an optimal solution or drops a
    file that does not fit. All grouping/encoding completes before any POST.
    """
    validate_files(files)
    members=[item for item in files if item["bytes"]]
    empty=codec.inflated_size([])
    costs={item["logical_path"]:codec.inflated_size([item])-empty for item in members}
    ordered=sorted(members,key=lambda item:(-costs[item["logical_path"]],item["logical_path"]))
    require(all(empty+cost<=codec.GROUP_JSON for cost in costs.values()),"SINGLE_FILE_BUNDLE_CAP")
    if not ordered:return []
    # Filling early groups to their byte cap can strand their file slots and
    # consume too many groups for the remaining small original receipts.
    lower=max((len(ordered)+codec.MAX_FILES-1)//codec.MAX_FILES,
        (sum(costs.values())+codec.GROUP_JSON-empty-1)//(codec.GROUP_JSON-empty))
    groups=[];sizes=[]
    for count in range(lower,MAX_GROUPS+1):
        bins=[[] for _ in range(count)];loads=[empty]*count
        for item in ordered:
            cost=costs[item["logical_path"]]
            eligible=[n for n,group in enumerate(bins) if len(group)<codec.MAX_FILES
                and loads[n]+cost+bool(group)<=codec.GROUP_JSON]
            if not eligible:break
            n=min(eligible,key=lambda n:(loads[n],len(bins[n]),n))
            loads[n]+=cost+bool(bins[n]);bins[n].append(item)
        else:
            groups=[group for group in bins if group]
            sizes=[load for group,load in zip(bins,loads) if group]
            break
    require(groups,"EIGHT_ARCHIVE_GROUPS_NO_OMISSIONS")
    require(sorted(item["logical_path"] for group in groups for item in group)
        ==sorted(item["logical_path"] for item in members),"EXACT_COMPLETE_ARCHIVE_PACKING_CENSUS")
    require(all(len(group)<=codec.MAX_FILES and codec.inflated_size(group)==size<=codec.GROUP_JSON
        for group,size in zip(groups,sizes)),"UNCHANGED_ARCHIVE_CODEC_GROUP_BOUNDS")
    return groups


def write(storage,path,value):
    storage.write_bytes(path,store.canonical(value))
    return cp.binding(path)


def read_owned(storage,ref,cap=store.ASSET_CAP,*,raw=False):
    require(type(ref) is dict and set(ref)=={"path","bytes","sha256"},"CLOSED_ARCHIVE_REFERENCE")
    require(type(ref["bytes"]) is int and 0<ref["bytes"]<=cap,"EXACT_CHECKPOINT_REFERENCE")
    validate_owned_references(storage,{ref["path"]:ref["sha256"]})
    # Keep the caller's ceiling, CAS validation and exact readback checks, but
    # allocate the declared actual length rather than the entire ceiling.
    body=cp.read_ref(ref,ref["bytes"])
    return body if raw else cp.strict_json(body)


def _owned_files(storage, files):
    """One original exclusive ownership check for a complete bounded cohort."""
    bindings={}
    for ref in files:
        require(type(ref) is dict and {"path","bytes","sha256"} <= set(ref),"CLOSED_ARCHIVE_REFERENCE")
        require(ref["path"] not in bindings or bindings[ref["path"]]==ref["sha256"],"ONE_HASH_PER_ORIGINAL_CAPTURE_PATH")
        bindings[ref["path"]]=ref["sha256"]
    owned,_=validate_owned_references(storage,bindings)
    require(all(owned[ref["path"]]["bytes"]==ref["bytes"] for ref in files),"EXACT_OWNED_CAPTURE_FILE_SIZES")


def _publish_owned_files(storage, files, destination):
    """Publish one verified codec cohort under the original global quota flock.

    Reserve its full incoming byte upper bound before the first write. Use the
    original storage path, immutable blob, fsync and hardlink primitives, with
    full registry/unique-inode scans at both boundaries rather than per file.
    Partial failures remain retained; no rollback, replacement or quota reset.
    """
    require(isinstance(storage,OperationalStorage) and 0<len(files)<=MAX_FILES,"FINITE_OWNED_ARCHIVE_EXTRACTION")
    destination=store.parents_safe(destination)
    require(sum(len(body) for _,body in files)<=codec.INFLATED,"BOUNDED_OWNED_ARCHIVE_EXTRACTION")
    with storage._locked():
        try:
            storage._refresh()
            targets=[]
            for name,body in files:
                target=storage._check(store.parents_safe(destination/codec.logical(name)))
                require(not target.exists(),"EXTRACTION_EXISTS")
                targets.append((target,body))
            require(len({target for target,_ in targets})==len(targets),"UNIQUE_OWNED_ARCHIVE_EXTRACTION")
            storage._require(sum(len(body) for _,body in targets))
            for target,body in targets:
                digest=store.sha(body);blob=storage.blob_root/digest
                if blob.exists():storage._verify_blob(blob)
                else:
                    temporary,descriptor=storage._temporary(storage.control_root,".incoming-")
                    try:
                        storage._write_all(descriptor,body)
                        os.fsync(descriptor)
                    finally:os.close(descriptor)
                    blob=storage._publish_blob(temporary,digest)
                storage._alias(blob,target,False)
        finally:
            storage._refresh()
            storage._scan()
    return dict(files=len(files),bytes=sum(len(body) for _,body in files),model_decodes=0)


def _extract_owned_group(body,record,storage,destination):
    # All unchanged codec schema/base64/size/hash/origin checks precede writes.
    return _publish_owned_files(storage,codec.verify_bundle(body,record),destination)


def fresh(storage,path):
    path=store.parents_safe(path)
    require(not path.exists(),"FRESH_ARCHIVE_PHASE_NO_RETRY")
    return storage.register_root(path)


def validate_files(files):
    # The unchanged bundle codec requires positive files. Explicit zero-length
    # originals are carried in the new index/census and recreated separately;
    # no empty original is padded, dropped or passed to that codec.
    require(type(files) is list and files and all(type(f.get("bytes")) is int and f["bytes"]>=0 for f in files),"FINITE_CAPTURE_FILE_CENSUS")
    codec.validate_files([f if f["bytes"] else dict(f,bytes=1) for f in files])
    require(all(f["bytes"] or f["sha256"]==store.sha(b"") for f in files),"EXACT_EMPTY_ORIGINAL_FILE_HASH")


def allowed_runtime_name(name):
    return name in CONTROL_FILES|CANDIDATE_NAMES|STATUS_NAMES or re.fullmatch(r"views/[0-9]{1,2}/projections/[a-f0-9]{64}\.json",name) is not None


def collect(runtime_root, context, *, storage, output, r0=None):
    """All available bytes, with a closed missing census for partial failures.

context roles are exact owned metadata bindings, including the parent's honest
origin witness and the separately qualified retained-model restore receipt.
No old completion is invented. Missing files force a failure archive.
"""
    require(type(context) is dict and CONTEXT <= set(context)
        <= CONTEXT | OPERATIONS_CONTEXT | OPERATIONS_HISTORY_CONTEXT | {"public_policy", "ops_previous_checkpoint"},"EXACT_ARCHIVE_CONTEXT_ROLES")
    history=set(context) & OPERATIONS_HISTORY_CONTEXT
    require(not history or history == OPERATIONS_HISTORY_CONTEXT,"PAIRED_OPERATIONAL_HISTORY_REFERENCES_REQUIRED")
    operations=set(context) & (OPERATIONS_CONTEXT | OPERATIONS_HISTORY_CONTEXT | {"ops_previous_checkpoint"})
    require(not operations or OPERATIONS_CONTEXT <= set(context), "COMPLETE_OPERATIONAL_PREVALUE_CONTEXT_REQUIRED")
    root=store.parents_safe(runtime_root);output=fresh(storage,output)
    entries={};physical_origins={}
    def add(ref,name,kind="control"):
        codec.logical(name)
        require(name not in entries and len(entries)<MAX_FILES,"FINITE_UNIQUE_CAPTURE_CENSUS")
        require(type(ref) is dict and set(ref)=={"path","bytes","sha256"},"CLOSED_ARCHIVE_REFERENCE")
        require(type(ref["bytes"]) is int and 0 <= ref["bytes"] <= store.ASSET_CAP,"COMPLETE_FILE_ASSET_BOUND_NO_TRUNCATION")
        physical_origins[name]=dict(ref)
        entries[name]=cp.file_item(ref,name,kind)
    observed=set()
    for directory,dirs,names in os.walk(root,followlinks=False):
        require(len(observed)+len(dirs)+len(names)<=MAX_FILES+128,"BOUNDED_RUNTIME_DIRECTORY_CENSUS")
        for part in dirs: require(not (Path(directory)/part).is_symlink(),"ARCHIVE_SOURCE_SYMLINK")
        for basename in names:
            if basename==_OWNER: continue
            path=Path(directory)/basename;name=path.relative_to(root).as_posix()
            require(allowed_runtime_name(name) and not path.is_symlink(),"UNDECLARED_RUNTIME_FILE_NO_SILENT_OMISSION")
            kind="forecast" if name.endswith(".jsonl.gz") else "feature" if name=="features.parquet" else "query" if name.endswith(".parquet") else "control"
            add(cp.binding(path),"runtime/"+name,kind);observed.add(name)
    for role,ref in context.items():add(ref,"context/"+role+".json")
    prepared=read_owned(storage,context["prepared"]);source=read_owned(storage,context["source"])
    require(prepared["schema_version"]==RUNTIME+"-prepared" and source["schema_version"]==RUNTIME+"-source"
        and source["prepared"]==context["prepared"],"EXACT_RUNTIME_SOURCE_AND_METADATA_CONTEXT")
    for role,ref in prepared["refs"].items():add(ref,"prepared/"+codec.logical(role)+".json")
    add(prepared["choice_completion"],"prepared/choice_completion.json")
    namespace=store.parents_safe(source["namespace"])
    for name in ("source-manifest.json","subset-manifest.json"):
        path=namespace/name
        require(str(path) in source["bindings"],"EXACT_SOURCE_CAPTURE_MANIFEST_REQUIRED")
        ref=cp.binding(path);require(ref["sha256"]==source["bindings"][str(path)],"SOURCE_CAPTURE_MANIFEST_HASH")
        add(ref,"source/"+name,"source_manifest")
    raw_inventory=[]
    for name,ref in sorted(source["raw"].items()):
        require(Path(name).name==name and name in source["manifest"]["source_receipts"],"CLOSED_TRANSIENT_HTTP_SOURCE")
        receipt=source["manifest"]["source_receipts"][name]
        require(receipt["sha256"]==ref["sha256"] and receipt["bytes"]==ref["bytes"],"HTTP_BODY_HASH_AND_CLOCK_CENSUS")
        raw_inventory.append(dict(name=name,body_sha256=ref["sha256"],bytes=ref["bytes"],receipt=receipt,
            archive_status="PRIVATE_TRANSIENT_HTTP_BODY_NOT_ARCHIVED"))
    transient=write(storage,output/"TRANSIENT_HTTP_CENSUS.json",dict(schema_version=VERSION+"-transient",files=raw_inventory,
        raw_HTTP_corpus_archived=False,source_intermediates_archived=False,
        transient_source_references=[dict(path=path,sha256=digest,archive_status="PRIVATE_TRANSIENT_SOURCE_REFERENCE_NOT_ARCHIVED")
            for path,digest in sorted(source["bindings"].items()) if Path(path).name not in {"source-manifest.json","subset-manifest.json"}],
        model_weights_reuploaded=False,retained_models=context["retained_models"]))
    add(transient,"source/TRANSIENT_HTTP_CENSUS.json","source_manifest")
    if r0 is not None:
        add(r0,"r0/CAPTURE_COMPLETE.json")
        reference=read_owned(storage,r0)
        require(reference["schema_version"]=="audit-reference-capture-v1-capture"
            and reference["state"]=="ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE","EXACT_ORIGINAL_R0_CAPTURE_REQUIRED")
        for role in ("prepared","native","original_board","next_state","control_forecast_rows","control_completion"):
            add(reference[role],"r0/"+role+".json" if role!="native" else "r0/original-native.json.gz","control")
        state=read_owned(storage,reference["next_state"])
        require(type(state["files"]) is dict and 0<len(state["files"])<=256,"FULL_ORIGINAL_R0_CACHE_CENSUS")
        for name,ref in state["files"].items():
            require(name.startswith(("data/cache/","output/data/")) and not name.endswith((".joblib",".pkl",".pickle",".parquet")),"NORMALIZED_ORIGINAL_R0_CACHE_ONLY")
            add(ref,"r0/cache/"+codec.logical(name),"control")
        worker_ref=cp.binding(Path(r0["path"]).parent/"WORKER_COMPLETE.json")
        add(worker_ref,"r0/WORKER_COMPLETE.json");worker=read_owned(storage,worker_ref)
        require(worker["state"]=="ORIGINAL_R0_DEFAULT_PROCEDURE_CAPTURED" and worker["native"]==reference["native"]
            and worker["next_state"]==reference["next_state"],"EXACT_ORIGINAL_R0_WORKER_AND_SOURCE_CLOCKS")
        for n,ref in enumerate(worker["source_observations"]):add(ref,f"r0/source-observations/{n:03}.json","source_manifest")
    # Discovery does not decode forecast bodies. Authenticate every original
    # together before semantic reads or duplicate-role alias publication. Each
    # input remains subject to the unchanged per-path CAS/hash/readonly checks;
    # only redundant whole-registry scans are removed.
    _owned_files(storage,list(entries.values()))
    seen=set()
    for name,item in list(entries.items()):
        if item["path"] in seen:
            alias=output/"physical-aliases"/name
            storage.import_file(item["path"],alias,expected_sha256=item["sha256"])
            entries[name]=cp.file_item(dict(path=str(alias),bytes=item["bytes"],sha256=item["sha256"]),name,item["kind"])
        else:seen.add(item["path"])
    missing=sorted((CONTROL_FILES|CANDIDATE_NAMES|STATUS_NAMES)-observed)
    files=sorted(entries.values(),key=lambda f:f["logical_path"])
    validate_files(files)
    census=dict(schema_version=VERSION+"-census",runtime_root=str(root),required_runtime=sorted(CONTROL_FILES|CANDIDATE_NAMES|STATUS_NAMES),
        observed_runtime=sorted(observed),missing_required=missing,context_roles=sorted(context),r0_provided=r0 is not None,
        raw_HTTP_corpus_archived=False,source_intermediates_archived=False,model_weights_reuploaded=False,models_dependency=context["retained_models"],
        physical_origins=physical_origins,actual_collected_at=now(),source_started_at=source["actual_source_started_at"],source_completed_at=source["actual_completed_at"],
        archive_state="COMPLETE_CAPTURE" if not missing else "FAILURE_EVIDENCE",logical_files=len(files),
        logical_bytes=sum(f["bytes"] for f in files),fits=0,public_export_authorized=False)
    # Complete-looking files do not turn a failed original attempt into success.
    if "FINISHED.json" in observed:
        terminal=cp.strict_json(cp.read_ref(physical_origins["runtime/FINISHED.json"]))
        if terminal.get("state")!="PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE":census["archive_state"]="FAILURE_EVIDENCE"
    result=dict(files=files,census=census)
    validate_capture(result,lambda name:Path(entries[name]["path"]),complete=census["archive_state"]=="COMPLETE_CAPTURE")
    _owned_files(storage,files)
    write(storage,output/"COLLECTED.json",result)
    return result


def validate_capture(snapshot,path,*,complete):
    """Semantic readback of forecast/control bytes only; no model/outcome API."""
    files=snapshot["files"];validate_files(files)
    names={f["logical_path"] for f in files};census=snapshot["census"]
    require(len(names)==len(files) and all(f["required"] and f["kind"] not in {"model","model_manifest","source_raw"}
        and f["origin"]["source_policy_sha256"]==cp.POLICY_SHA for f in files),"NO_MODEL_RAW_OR_OPTIONAL_CAPTURE_FILES")
    require(census["raw_HTTP_corpus_archived"] is census["model_weights_reuploaded"] is False,"EXPLICIT_CAPTURE_SCOPE")
    doc=lambda name:cp.strict_json(store.read_local(path(name),2 << 20))
    if not complete:
        bundled=census.get("bundled_control_sources",{})
        require(type(bundled) is dict and set(bundled)<={FAILURE_OBSERVATIONS_NAME},"CLOSED_FAILED_CONTROL_BUNDLE_SCOPE")
        require((FAILURE_OBSERVATIONS_NAME in names)==bool(bundled),"FAILED_CONTROL_BUNDLE_AND_CENSUS_REQUIRED_TOGETHER")
        for name,expected in bundled.items():
            require(name in names and type(expected) is list and 0<len(expected)<=1024,"COMPLETE_FAILED_OBSERVATION_CENSUS")
            body=store.read_local(path(name),1 << 20);value=cp.strict_json(body)
            require(type(value) is dict and set(value)=={"schema_version","records"}
                and value["schema_version"]==FAILURE_OBSERVATIONS_SCHEMA and body==store.canonical(value)
                and type(value["records"]) is list and len(value["records"])==len(expected),"EXACT_FAILED_CONTROL_BUNDLE")
            seen=[];projection=[]
            for record in value["records"]:
                require(type(record) is dict and set(record)=={"logical_path","reference","body_base64"}
                    and type(record["logical_path"]) is str
                    and re.fullmatch(r"failed/reference/source-observations/[0-9]{4}-(?:BEGIN|END)\.json",record["logical_path"]),
                    "ONLY_ORIGINAL_SOURCE_OBSERVATION_CONTROLS_BUNDLED")
                ref=record["reference"]
                require(type(ref) is dict and set(ref)=={"path","bytes","sha256"}
                    and type(ref["path"]) is str and Path(ref["path"]).is_absolute() and len(ref["path"])<=1024
                    and type(ref["bytes"]) is int and 0<=ref["bytes"]<=64 << 10
                    and store.HASH.fullmatch(str(ref["sha256"])) and type(record["body_base64"]) is str,
                    "EXACT_ORIGINAL_BUNDLED_CONTROL_BINDING")
                try:original=base64.b64decode(record["body_base64"],validate=True)
                except (ValueError,TypeError):raise store.StoreError("FAILED_CONTROL_BUNDLE_ENCODING") from None
                require(len(original)==ref["bytes"] and store.sha(original)==ref["sha256"],"FULL_ORIGINAL_BUNDLED_CONTROL_BYTES")
                seen.append(record["logical_path"]);projection.append({k:record[k] for k in ("logical_path","reference")})
            require(seen==sorted(set(seen)) and projection==expected,"NO_OMITTED_DUPLICATED_OR_CHANGED_BUNDLED_CONTROL")
        return dict(state="FAILURE_EVIDENCE",qualified_selected=False,forecast_rows=0)
    require(not census["missing_required"] and {"runtime/"+n for n in CONTROL_FILES|CANDIDATE_NAMES|STATUS_NAMES}<=names,"COMPLETE_ORIGINAL_RUNTIME_CENSUS")
    terminal=doc("runtime/FINISHED.json");handoff=doc("runtime/EXPORT_INPUTS.json")
    require(terminal["schema_version"]==RUNTIME+"-result" and terminal["state"]=="PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE"
        and terminal["fits"]==terminal["searches"]==terminal["scores"]==0
        and terminal["public_release"] is terminal["public_export_authorized"] is False
        and handoff["schema_version"]==RUNTIME+"-private-handoff" and handoff["public_export_authorized"] is False,
        "COMPLETE_NEW_RUNTIME_HANDOFF_REQUIRED")
    original={f["logical_path"]:f for f in files}
    def matches(ref,name):return ref["sha256"]==original[name]["sha256"] and ref["bytes"]==original[name]["bytes"]
    for role,name in (("terminal","FINISHED.json"),("selected","selected.jsonl.gz"),("completion","selected.jsonl.completion.json"),
        ("identity_bridge","IDENTITY_BRIDGE.json"),("recipe","RUNTIME_RECIPE.json"),("choice","WEEKLY_CHOICE.json"),
        ("artifact_catalog","ARTIFACT_CATALOG.json"),("selected_version_catalog","SELECTED_VERSION_CATALOG.json")):
        require(matches(handoff[role],"runtime/"+name),"HANDOFF_PHYSICAL_BINDING_MISMATCH")
    prepared=doc("context/prepared.json");source=doc("context/source.json")
    versions=doc("runtime/SELECTED_VERSION_CATALOG.json");choice=doc("runtime/WEEKLY_CHOICE.json")
    epoch_doc=doc("context/epoch.json");epoch_registration=doc("context/epoch_registration.json")
    completion=doc("prepared/choice_completion.json");capture=doc("runtime/features.capture.json")
    require(versions["current_values_used"] is False and prepared["current_values_used"] is False
        and versions["epoch_sha256"]==terminal["epoch_sha256"]==epoch_registration["epoch_sha256"]==store.sha(store.canonical(epoch_doc))
        and versions["choice_sha256"]==terminal["choice_sha256"]==store.sha(store.canonical(choice))
        and completion["metadata_remote_durability_qualified"] is False
        and store.utc(completion["persisted_completed_at"])<store.utc(source["actual_source_started_at"])
        <=store.utc(source["actual_completed_at"])<=store.utc(terminal["actual_completed_at"])
        and capture["source_contract"]["source_policy_sha256"]==cp.POLICY_SHA
        and matches(capture["feature_binding"],"runtime/features.parquet"),"PREVALUES_CATALOG_CAS_SOURCE_FEATURE_CLOCKS_REQUIRED")
    candidate=doc("runtime/CANDIDATES.json");slots=candidate["slots"]
    require(len(slots)==18 and {(s["target"],s["method_id"]) for s in slots}=={(t,m) for t,_,m in cp.JOBS},"ALL18_LOSERS_AND_WINNERS_REQUIRED")
    total=0;semantic=0
    def stream(name,expected,receipt,target=None,method=None):
        nonlocal total,semantic
        count=0;seen=set()
        with gzip.open(path(name),"rb") as reader:
            while True:
                body=reader.readline(32769)
                if not body:break
                count+=1;semantic+=len(body)
                require(count<=expected and len(body)<=32768 and body.endswith(b"\n") and semantic<=SEMANTIC_CAP,"FINITE_COMPLETE_FORECAST_ROW_STREAM")
                row=cp.strict_json(body)
                require(not {"actual","label","loss","outcome"}&set(row) and row["offered_id"] not in seen
                    and row["evidence_lane"]=="original_pregame" and row["scientific_qualification"] is False
                    and store.utc(row["source_capture_completed_at"])<=store.utc(row["issued_at"])<=store.utc(receipt["completed_at"])
                    and store.utc(receipt["persist_started_at"])<=store.utc(receipt["completed_at"])
                    <=store.utc(terminal["actual_completed_at"])<store.utc(row["cutoff_utc"])<store.utc(row["kickoff_utc"]),"ORIGINAL_FORECAST_FIELDS_AND_CLOCKS")
                seen.add(row["offered_id"])
                if target is not None:require(row["category"]==target and row["method_id"]==method and row["attempt_qualified"] is True,"EXACT_COMPLETE_CANDIDATE_SLOT")
        require(count==expected,"NO_DROPPED_FORECAST_ROWS")
        total+=count
    for slot in slots:
        target,method=slot["target"],slot["method_id"];base=f"runtime/candidates/{target}/{method}"
        require(slot["state"]=="CAPTURED" and slot["failure"] is None and slot["attempt_qualified"] is True
            and slot["expected_rows"]==slot["issued_rows"]==slot["persistence"]["rows"]<=1000
            and not slot["unissued_offered_ids"] and slot["persistence"]==doc(base+".jsonl.completion.json")
            and slot["persistence"]["state"]=="PERSISTED" and matches(slot["persistence"]["binding"],base+".jsonl.gz"),"EXACT_COMPLETE_CANDIDATE_BODY_AND_COMPLETION")
        stream(base+".jsonl.gz",slot["issued_rows"],slot["persistence"],target,method)
    require(total==terminal["prediction_rows"]<=18000,"ALL18_CANDIDATE_ROW_CENSUS")
    selected=doc("runtime/selected.jsonl.completion.json")
    require(selected==terminal["selected"] and selected["state"]=="PERSISTED" and selected["rows"]<=5000
        and matches(selected["binding"],"runtime/selected.jsonl.gz"),"EXACT_SELECTED_BYTES_AND_COMPLETION")
    stream("runtime/selected.jsonl.gz",selected["rows"],selected)
    # Parquet footer only: all qualified input columns remain in the exact body.
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(2);pa.set_io_thread_count(2);pa.set_memory_pool(pa.system_memory_pool())
    columns=set(pq.ParquetFile(path("runtime/features.parquet")).schema_arrow.names)
    require({"season","week","game_id","player_id","position","cutoff_utc","kickoff_utc","feature_max_source_available_utc"}<=columns
        and any(c.startswith("f_") for c in columns),"FULL_QUALIFIED_CURRENT_FEATURE_SNAPSHOT_REQUIRED")
    for name in names:
        if re.fullmatch(r"runtime/views/[0-9]{1,2}/projections/[a-f0-9]{64}\.json",name):
            projection=doc(name)
            require(set(projection["projection_features"])<=columns and projection["parent_shared_capture"]["sha256"]==original["runtime/features.capture.json"]["sha256"]
                and matches(projection["feature_binding"],"runtime/features.parquet"),"NO_DROPPED_QUALIFIED_CURRENT_INPUT_COLUMNS")
    if census["r0_provided"]:
        required={"r0/"+role+".json" for role in ("prepared","original_board","next_state","control_forecast_rows","control_completion")}
        require(required | {"r0/CAPTURE_COMPLETE.json","r0/WORKER_COMPLETE.json","r0/original-native.json.gz"} <= names,
            "COMPLETE_ORIGINAL_R0_FILE_GRAPH_REQUIRED")
        r0=doc("r0/CAPTURE_COMPLETE.json");worker=doc("r0/WORKER_COMPLETE.json");completion=doc("r0/control_completion.json")
        for role in ("prepared","original_board","next_state","control_forecast_rows","control_completion"):
            require(matches(r0[role],"r0/"+role+".json"),"R0_CONTROL_AND_COMPLETION_PHYSICAL_BINDING")
        require(matches(r0["native"],"r0/original-native.json.gz") and worker["native"]==r0["native"]
            and worker["next_state"]==r0["next_state"],"R0_NATIVE_WORKER_AND_CACHE_BINDING")
        require(completion["schema_version"]=="audit-reference-capture-v1-control-completion"
            and completion["forecast_binding"]==r0["control_forecast_rows"]
            and completion["source_receipt_sha256"]==store.sha(store.canonical(worker))
            and completion["original_native_persist_completed_at"]==worker["actual_native_persist_completed_at"]
            and completion["remote_durability_qualified"] is completion["public_release"] is False,
            "EXACT_ORIGINAL_R0_COMPLETION_SOURCE_SCOPE")
        controls=cp.strict_json(store.read_local(path("r0/control_forecast_rows.json"),store.ASSET_CAP))
        prepared=doc("r0/prepared.json")
        require(completion["actual_issued_at"]==controls["actual_issued_at"]
            and store.utc(worker["actual_source_completed_at"])<=store.utc(worker["actual_native_observed_at"])
            <=store.utc(worker["actual_native_persist_completed_at"])<=store.utc(completion["actual_issued_at"])
            <=store.utc(completion["body_persist_completed_at"])<min(map(store.utc,prepared["slate"]["game_cutoffs"].values())),
            "HONEST_R0_CONTROL_ISSUANCE_AND_PERSISTENCE_CLOCKS")
    return dict(state="COMPLETE_CAPTURE",qualified_selected=True,candidate_rows=terminal["prediction_rows"],selected_rows=selected["rows"],
        forecast_rows=total,replay_ready=True,model_replay_performed=False,raw_HTTP_corpus_archived=False)


class Client(store.Client):
    def __init__(self,*args,qualification=None,readonly=False,**kwargs):
        super().__init__(*args,**kwargs);self.qualification=qualification;self.readonly=readonly
    def allow(self,url):
        if self.qualification is not None and url in {store.API+"/actions/runs/"+self.qualification["run_id"],store.API+"/actions/runs/"+self.qualification["run_id"]+"/jobs?per_page=100&page=1"}:
            self.allowed.add(url);return url
        return super().allow(url)
    def request(self,url,*,method="GET",**kwargs):
        require(not self.readonly or method=="GET","ARCHIVE_EXPORT_CONSUMER_GET_ONLY")
        return super().request(url,method=method,**kwargs)


def checked(client,label):
    client.authenticate_actions_job()
    require(client.job["execution_lane"]=="github_actions" and client.job["run_authenticated"] is True
        and client.job["job_id"]==label and client.job["permission"]=="write","GENUINE_ARCHIVE_ACTIONS_JOB_REQUIRED")
    return cp.client_identity(client)


def authenticate_qualification(client,package,pending_census):
    binding,q=package["binding"],package["qualification"]
    require(client.binding==binding and package["schema_version"]==rotation.VERSION+"-qualified-runtime"
        and package["runtime_reserved_bytes"]==store.TOTAL_CAP and package["runtime_id"]==binding["runtime_id"]
        and package["run_id"]==q["run_id"]==binding["origin_run_id"] and package["source_sha"]==q["source_sha"],"NEW_QUALIFIED_ROTATION_PACKAGE_REQUIRED")
    rotation.checked_quota(package["quota_reservation"],dict(runtime_id=binding["runtime_id"],pending_census=pending_census))
    owner.archived_qualification(binding,q);store.check_proof(client,q,"qualified",same_run=False)
    base=store.API+"/actions/runs/"+q["run_id"]
    run=client.json(client.allow(base));jobs=client.json(client.allow(base+"/jobs?per_page=100&page=1"))
    require(run.get("id")==int(q["run_id"]) and run.get("head_sha")==q["source_sha"] and run.get("run_attempt")==1
        and run.get("event")=="workflow_dispatch" and run.get("path")==".github/workflows/lab.yml"
        and run.get("status") in {"in_progress","completed"} and run.get("repository",{}).get("full_name")==store.REPO
        and run.get("head_repository",{}).get("full_name")==store.REPO
        and run.get("head_branch")==q["job"]["workflow_ref"].split("@refs/heads/",1)[1]
        and run.get("actor",{}).get("id")==208912933 and run.get("actor",{}).get("login")=="NickNicky19"
        and type(jobs.get("jobs")) is list and jobs.get("total_count")==len(jobs["jobs"])<=100,"ACTUAL_QUALIFIED_ROTATION_RUN_REQUIRED")
    for proof,label in zip((q["before_proof"],q["read_proof"],q),(rotation.JOBS[k] for k in ("write","read","qualify"))):
        matches=[j for j in jobs["jobs"] if j.get("id")==proof["job"]["api_job_id"]]
        require(len(matches)==1,"ACTUAL_ROTATION_JOB_REQUIRED");job=matches[0]
        require(proof["job"]["job_id"]==job.get("name")==label and job.get("status")=="completed" and job.get("conclusion")=="success"
            and job.get("run_id")==int(q["run_id"]) and job.get("head_sha")==q["source_sha"]
            and store.utc(job["started_at"])<=store.utc(proof["started_at_utc"])<=store.utc(proof["created_at_utc"])
            <=store.utc(job["completed_at"])<=store.utc(client.started_at),"COMPLETED_GENUINE_ROTATION_JOB_PROOF_REQUIRED")
    owner.verify_canary(client)


def jobs_for(client):
    run=client.json(client.allow(store.API+"/actions/runs/"+client.run_id))
    from . import audit_weekly_operations_authority_v1 as operations_authority
    require(run.get("head_branch")==client.job["workflow_ref"].split("@refs/heads/",1)[1]
        and operations_authority.authorize_client_actor(client,run),"ACTUAL_ARCHIVE_BRANCH_AND_OWNER")
    data=client.json(client.allow(store.API+"/actions/runs/"+client.run_id+"/jobs?per_page=100&page=1"))
    require(type(data.get("jobs")) is list and data.get("total_count")==len(data["jobs"])<=100,"COMPLETE_ARCHIVE_ACTIONS_JOB_LIST")
    return data["jobs"]


def predecessor(client,identity,jobs,*,failure_archive=False):
    require(identity["run_id"]==client.run_id and identity["source_sha"]==client.source_sha and identity["workflow_ref"]==client.job["workflow_ref"]
        and identity["api_job_id"]!=client.job["api_job_id"] and identity["process_identity"]!=client.process,"FRESH_DISTINCT_SAME_SOURCE_ARCHIVE_READER")
    matches=[j for j in jobs if j.get("id")==identity["api_job_id"]]
    require(len(matches)==1,"EXACT_ARCHIVE_PREDECESSOR_API_ID");job=matches[0]
    require(job.get("name")==identity["job_id"] and job.get("status")=="completed"
        and job.get("conclusion") in ({"success","failure"} if failure_archive else {"success"})
        and job.get("head_sha")==client.source_sha and job.get("run_id")==int(client.run_id)
        and store.utc(job["completed_at"])<=store.utc(client.started_at),"COMPLETED_SUCCESSFUL_ARCHIVE_PREDECESSOR")
    return job


def fake_descriptor(body,client):
    entry=dict(schema_version="weekly-private-restore-manifest-v2",payload=cp.payload(body),payload_asset_id=10**20-1,
        payload_name="blob-"+store.sha(body)+".bin",producer_process=client.process,binding_sha256=store.sha(store.canonical(client.binding)),writer_run_id=client.run_id)
    raw=store.canonical(entry)
    return dict(entry=entry,manifest_asset_id=10**20-1,manifest_sha256=store.sha(raw),manifest_bytes=len(raw))


def safe_handoff(value):
    require(type(value) is dict and set(value)==HANDOFF_KEYS and value["schema_version"]==VERSION+"-handoff"
        and value["repository"]==store.REPO and value["archive_state"] in {"COMPLETE_CAPTURE","FAILURE_EVIDENCE"},"CLOSED_ARCHIVE_HANDOFF")
    store.checked_binding(value["runtime_binding"]);entry=cp.descriptor_meta(value["index_descriptor"],INDEX_CAP)
    require(type(value["jobs"]) is dict and set(value["jobs"])=={"produce","restore","consume"} and len(set(value["jobs"].values()))==3
        and all(type(v) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,100}",v) for v in value["jobs"].values())
        and re.fullmatch(r"[a-f0-9]{40}",str(value["source_sha"])) and re.fullmatch(r"[1-9][0-9]{0,19}",str(value["run_id"]))
        and value["producer"]["repository"]==store.REPO and value["producer"]["execution_lane"]=="github_actions"
        and type(value["producer"]["api_job_id"]) is int and value["producer"]["api_job_id"]>0
        and entry["binding_sha256"]==store.sha(store.canonical(value["runtime_binding"])),"CLOSED_ACTUAL_ARCHIVE_PRODUCER_ROLES")
    require(value["producer"]["run_id"]==value["run_id"]==entry["writer_run_id"]
        and value["producer"]["source_sha"]==value["source_sha"] and value["producer"]["process_identity"]==entry["producer_process"]
        and value["producer"]["job_id"]==value["jobs"]["produce"]
        and all(store.HASH.fullmatch(str(value[k])) for k in ("root_go_sha256","files_sha256")),"EXACT_ARCHIVE_HANDOFF_BINDINGS")
    body=store.canonical(value)
    require(len(body)<=16384 and not any(t in body for t in (b"https://",b"/home/",b"/tmp/",b"ghs_",b"content_b64")),"BOUNDED_DESCRIPTOR_ONLY_ARCHIVE_HANDOFF")
    return body


def produce(snapshot,factory,package,*,storage,output,root_go_sha256,jobs,pending_census,pending=()):
    output=fresh(storage,output);files,census=snapshot["files"],snapshot["census"]
    validate_files(files);validate_owned_references(storage,{f["path"]:f["sha256"] for f in files})
    require(set(jobs)=={"produce","restore","consume"} and len(set(jobs.values()))==3 and store.HASH.fullmatch(root_go_sha256),"CLOSED_PARENT_ARCHIVE_ROLES_AND_ROOT_GO")
    first=factory("append");producer=checked(first,jobs["produce"])
    cp.seed_pending(first.journal,list(pending));authenticate_qualification(first,package,pending_census);jobs_for(first)
    proof=dict(schema_version=VERSION+"-producer",identity=producer,root_go_sha256=root_go_sha256,
        files_sha256=store.sha(store.canonical(files)),census_sha256=store.sha(store.canonical(census)),actual_started_at=first.started_at,
        source_started_at=census["source_started_at"],source_completed_at=census["source_completed_at"],actual_collected_at=census["actual_collected_at"],
        fits=0,successful_forecast=False,public_release=False)
    write(storage,output/"CONSUMED.json",proof)
    complete=census["archive_state"]=="COMPLETE_CAPTURE"
    validate_capture(snapshot,lambda n:Path(next(f["path"] for f in files if f["logical_path"]==n)),complete=complete)
    prepared=[]
    for n,members in enumerate(capture_groups(files)):
        require(n<MAX_GROUPS,"EIGHT_ARCHIVE_GROUPS_NO_OMISSIONS")
        body,inflated=codec.encode(members)
        record=dict(index=n,bytes=len(body),sha256=store.sha(body),inflated_bytes=inflated,files=members)
        path=output/"preencoded"/(str(n)+".gz");storage.write_bytes(path,body)
        prepared.append((record,cp.binding(path)))
    first.draft();assets,total=first.inventory()
    require(not any("blob-"+r["sha256"]+".bin" in {a["name"] for a in assets} for r,_ in prepared),"ARCHIVE_PAYLOAD_ALREADY_PRESENT_NO_RETRY")
    needed=sum(r["bytes"] for r,_ in prepared)+INDEX_CAP+(len(prepared)+1)*ENTRY_CAP+WITNESS_CAP+ENTRY_CAP+FAILURE_RESERVE
    slots=2*(len(prepared)+1)+2+2
    require(total+needed<=store.TOTAL_CAP and first.inventory_slots+slots<=store.MAX_ASSETS,"FULL_ARCHIVE_INDEX_WITNESS_FAILURE_QUOTA_BEFORE_POST")
    admission=dict(existing_bytes=total,reserved_upper_bytes=needed,admitted_bytes=total+needed,runtime_cap=store.TOTAL_CAP,
        existing_slots=first.inventory_slots,reserved_slots=slots,index_bytes=INDEX_CAP,witness_bytes=WITNESS_CAP,
        failure_bytes=FAILURE_RESERVE,failure_slots=2,model_weights_reuploaded=False)
    def index(records,created):
        return dict(schema_version=VERSION+"-index",repository=store.REPO,source_sha=first.source_sha,run_id=first.run_id,
            root_go_sha256=root_go_sha256,producer=producer,producer_proof=proof,created_at=created,
            runtime_binding_sha256=store.sha(store.canonical(first.binding)),qualification_sha256=store.sha(store.canonical(package["qualification"])),
            files=files,files_sha256=proof["files_sha256"],groups=records,census=census,archive_state=census["archive_state"],jobs=jobs,
            admission=admission,pending_reservations=list(pending))
    preview=[]
    for record,ref in prepared:preview.append(dict(record,descriptor=fake_descriptor(cp.read_ref(ref),first)))
    plain=store.canonical(index(preview,"9999-12-31T23:59:59.999999+00:00"));encoded=gzip.compress(plain,mtime=0)
    require(len(plain)<=INDEX_PLAIN_CAP-4096 and len(encoded)<=INDEX_CAP,"COMPLETE_ENCODED_INDEX_PREFLIGHT")
    with storage.transaction():
        storage._require(INDEX_CAP+WITNESS_CAP+FAILURE_RESERVE+((len(prepared)+3)<<15))
        write(storage,output/"ADMISSION.json",admission);storage.write_bytes(output/"INDEX_PREVIEW.gz",encoded)
    def put(client,body,number):
        require(checked(client,jobs["produce"])==producer and client.binding==first.binding and client.journal==first.journal,"ONE_AUTHENTIC_ARCHIVE_PRODUCER")
        write(storage,output/(f"APPEND_INTENT_{number}.json"),dict(schema_version=VERSION+"-native-append",producer=producer,
            root_go_sha256=root_go_sha256,payload=cp.payload(body),files_sha256=proof["files_sha256"],complete_preencoding_admitted=True))
        return store.append(client,body,cp.payload(body),package["qualification"])
    records=[]
    try:
        for n,(record,ref) in enumerate(prepared):records.append(dict(record,descriptor=put(first if n==0 else factory("append"),cp.read_ref(ref),n)))
        plain=store.canonical(index(records,now()));encoded=gzip.compress(plain,mtime=0)
        require(len(plain)<=INDEX_PLAIN_CAP-4096 and len(encoded)<=INDEX_CAP,"ACTUAL_INDEX_WITHIN_RESERVED_PREFLIGHT")
        descriptor=put(factory("append"),encoded,len(records))
        handoff=dict(schema_version=VERSION+"-handoff",repository=store.REPO,source_sha=first.source_sha,run_id=first.run_id,
            root_go_sha256=root_go_sha256,producer=producer,runtime_binding=first.binding,index_descriptor=descriptor,
            files_sha256=proof["files_sha256"],archive_state=census["archive_state"],jobs=jobs)
        safe_handoff(handoff);write(storage,output/"APPENDED.json",dict(handoff=handoff,private_capture_durability=False,public_release=False))
        return handoff
    except BaseException:
        write(storage,output/"APPEND_FAILED.json",dict(state="FAILED_ARCHIVE_APPEND_NO_RETRY",successful_forecast=False,public_release=False))
        raise


def unpack(body,cap):
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:plain=stream.read(cap+1)
    require(len(plain)<=cap,"ARCHIVE_METADATA_INFLATION_CAP")
    return cp.strict_json(plain)


def check_index(index,handoff):
    require(type(index) is dict and set(index)==INDEX_KEYS and index["schema_version"]==VERSION+"-index"
        and all(index[k]==handoff[k] for k in ("repository","source_sha","run_id","root_go_sha256","producer","files_sha256","archive_state","jobs"))
        and index["runtime_binding_sha256"]==store.sha(store.canonical(handoff["runtime_binding"]))
        and index["producer_proof"]["identity"]==handoff["producer"]
        and index["files_sha256"]==store.sha(store.canonical(index["files"])),"EXACT_ORIGINAL_ARCHIVE_INDEX")
    validate_files(index["files"])
    require(index["census"]["archive_state"]==index["archive_state"] and index["producer_proof"]["files_sha256"]==index["files_sha256"]
        and index["producer_proof"]["census_sha256"]==store.sha(store.canonical(index["census"])),"ORIGINAL_PRODUCER_CENSUS_PROOF")
    census=index["census"];originals={f["logical_path"]:f for f in index["files"]}
    require(census["logical_files"]==len(originals) and census["logical_bytes"]==sum(f["bytes"] for f in originals.values())
        and set(census["physical_origins"])==set(originals)
        and all(census["physical_origins"][n]["bytes"]==f["bytes"] and census["physical_origins"][n]["sha256"]==f["sha256"] for n,f in originals.items()),
        "FULL_LOGICAL_AND_ORIGINAL_PHYSICAL_CENSUS")
    groups=index["groups"];require(type(groups) is list and 0<len(groups)<=MAX_GROUPS,"EIGHT_COMPLETE_ARCHIVE_GROUPS")
    originals={f["logical_path"]:f for f in index["files"]};seen=set();assets=[handoff["index_descriptor"]["manifest_asset_id"],handoff["index_descriptor"]["entry"]["payload_asset_id"]]
    for n,group in enumerate(groups):
        require(set(group)==cp.GROUP_KEYS and group["index"]==n,"CLOSED_ORDERED_ARCHIVE_GROUP")
        entry=cp.descriptor_meta(group["descriptor"],store.ASSET_CAP)
        require(entry["writer_run_id"]==handoff["run_id"] and entry["producer_process"]==handoff["producer"]["process_identity"]
            and entry["binding_sha256"]==index["runtime_binding_sha256"] and entry["payload"]["sha256"]==group["sha256"]
            and entry["payload"]["bytes"]==group["bytes"],"ORIGINAL_ARCHIVE_GROUP_PRODUCER_AND_HASH")
        assets.extend([group["descriptor"]["manifest_asset_id"],entry["payload_asset_id"]])
        for file in group["files"]:
            require(file==originals.get(file["logical_path"]) and file["logical_path"] not in seen,"NO_DUPLICATE_OR_OMITTED_CAPTURE_FILE")
            seen.add(file["logical_path"])
    require(seen=={n for n,f in originals.items() if f["bytes"]} and len(assets)==len(set(assets)) and handoff["runtime_binding"]["canary_asset_id"] not in assets,"COMPLETE_CAPTURE_PARTITION")
    return index


def restore(handoff,factory,package,*,storage,output,root_go_sha256,pending_census,reader_handoff=None):
    """Fresh reader writes one reserved witness; exporter variant is GET only."""
    safe_handoff(handoff);require(root_go_sha256==handoff["root_go_sha256"],"EXACT_CAPTURE_ROOT_GO")
    output=fresh(storage,output);exporter=reader_handoff is not None;role="consume" if exporter else "restore"
    first=factory("restore");current=checked(first,handoff["jobs"][role])
    authenticate_qualification(first,package,pending_census);jobs=jobs_for(first)
    writer=predecessor(first,handoff["producer"],jobs,failure_archive=handoff["archive_state"]=="FAILURE_EVIDENCE")
    prior_witness=None
    if exporter:
        require(set(reader_handoff)=={"schema_version","archive","restorer","witness_descriptor"}
            and reader_handoff["schema_version"]==VERSION+"-reader-handoff" and reader_handoff["archive"]==handoff
            and reader_handoff["restorer"]["job_id"]==handoff["jobs"]["restore"],"EXACT_READER_WITNESS_HANDOFF")
        predecessor(first,reader_handoff["restorer"],jobs)
        entry=cp.descriptor_meta(reader_handoff["witness_descriptor"],WITNESS_CAP)
        require(entry["producer_process"]==reader_handoff["restorer"]["process_identity"]
            and entry["writer_run_id"]==handoff["run_id"] and entry["binding_sha256"]==store.sha(store.canonical(handoff["runtime_binding"])),
            "EXACT_ORIGINAL_RESTORER_WITNESS_DESCRIPTOR")
    proofs=[];used=False
    def get(descriptor,name):
        nonlocal used
        entry=cp.descriptor_meta(descriptor,store.ASSET_CAP)
        client=first if not used else factory("restore");used=True
        require(checked(client,handoff["jobs"][role])==current and client.binding==handoff["runtime_binding"],"ONE_AUTHENTIC_ARCHIVE_READER")
        destination=output/"downloads"/name;destination.parent.mkdir(parents=True,exist_ok=True)
        with storage.transaction():
            storage._require(2*entry["payload"]["bytes"]+ENTRY_CAP)
            proof=store.restore(client,descriptor,destination)
            owned=output/"owned-downloads"/name;storage.import_file(destination,owned,expected_sha256=entry["payload"]["sha256"])
        proofs.append(proof)
        return store.read_local(owned,store.ASSET_CAP)
    if exporter:
        prior_witness=unpack(get(reader_handoff["witness_descriptor"],"reader-witness.gz"),WITNESS_CAP)
        require(prior_witness["schema_version"]==VERSION+"-witness" and prior_witness["restorer"]==reader_handoff["restorer"]
            and prior_witness["index_sha256"]==handoff["index_descriptor"]["entry"]["payload"]["sha256"],"AUTHENTIC_ORIGINAL_READER_WITNESS")
        for proof in prior_witness["proofs"]:store.check_proof(first,proof,"restore")
    encoded=get(handoff["index_descriptor"],"index.gz");index=check_index(unpack(encoded,INDEX_PLAIN_CAP),handoff)
    require(index["qualification_sha256"]==store.sha(store.canonical(package["qualification"]))
        and store.utc(writer["started_at"])<=store.utc(index["created_at"])<=store.utc(writer["completed_at"]),"QUALIFIED_INDEX_AND_GENUINE_PRODUCER_CLOCK")
    if exporter:
        expected=[store.sha(encoded)]+[g["sha256"] for g in index["groups"]]
        require([p["payload_sha256"] for p in prior_witness["proofs"]]==expected
            and all(p["process_identity"]==reader_handoff["restorer"]["process_identity"]
                and p["job"]["api_job_id"]==reader_handoff["restorer"]["api_job_id"]
                and p["job"]["job_id"]==handoff["jobs"]["restore"] for p in prior_witness["proofs"]),"ALL_ORIGINAL_READER_PROOFS_BOUND_TO_COMPLETE_INDEX")
    with storage.transaction():storage._require(sum(f["bytes"] for f in index["files"])+sum(g["bytes"]*2 for g in index["groups"])+(2 << 20))
    for group in index["groups"]:_extract_owned_group(get(group["descriptor"],str(group["index"])+".gz"),group,storage,output/"files")
    empty=[(f["logical_path"],b"") for f in index["files"] if f["bytes"]==0]
    if empty:_publish_owned_files(storage,empty,output/"files")
    aliases={f["logical_path"]:dict(path=str(output/"files"/f["logical_path"]),bytes=f["bytes"],sha256=f["sha256"]) for f in index["files"]}
    _owned_files(storage,list(aliases.values()))
    validation=validate_capture(index,lambda n:Path(aliases[n]["path"]),complete=index["archive_state"]=="COMPLETE_CAPTURE")
    _owned_files(storage,list(aliases.values()))
    witness=dict(schema_version=VERSION+"-witness",restorer=current,index_sha256=store.sha(encoded),files_sha256=index["files_sha256"],
        producer_proof_sha256=store.sha(store.canonical(index["producer_proof"])),proofs=proofs,validation=validation,actual_completed_at=now(),
        archive_state=index["archive_state"],public_export_authorized=False,successful_forecast=False)
    if exporter:
        require(prior_witness["files_sha256"]==index["files_sha256"] and prior_witness["producer_proof_sha256"]==witness["producer_proof_sha256"]
            and prior_witness["validation"]==validation,"COMPLETE_PRODUCER_RESTORER_EXPORTER_CHAIN")
        witness_descriptor=reader_handoff["witness_descriptor"]
    else:
        raw=store.canonical(witness);body=gzip.compress(raw,mtime=0)
        require(len(raw)<=WITNESS_CAP and len(body)<=WITNESS_CAP,"RESERVED_FULL_READER_WITNESS_BOUND")
        client=factory("append")
        require(checked(client,handoff["jobs"]["restore"])==current and client.binding==handoff["runtime_binding"],"SAME_ACTUAL_WITNESS_READER")
        write(storage,output/"WITNESS_POST_INTENT.json",dict(root_go_sha256=root_go_sha256,payload=cp.payload(body),original_archive=handoff))
        witness_descriptor=store.append(client,body,cp.payload(body),package["qualification"])
    result=dict(schema_version=VERSION+"-restored",state="PRIVATE_CAPTURE_EXPORT_INPUTS_VERIFIED" if exporter and validation["qualified_selected"] else
        "PRIVATE_CAPTURE_RESTORED" if validation["qualified_selected"] else "PRIVATE_FAILURE_ARCHIVE_RESTORED",
        archive=handoff,current=current,producer_proof=index["producer_proof"],restorer_witness=prior_witness if exporter else witness,
        exporter_proofs=proofs if exporter else None,restore_proofs=proofs,aliases=aliases,validation=validation,
        index_sha256=store.sha(encoded),files_sha256=index["files_sha256"],witness_descriptor=witness_descriptor,
        replay_ready=validation.get("replay_ready",False),model_replay_performed=False,raw_HTTP_corpus_archived=False,
        captured_bundle_hashes_restored=True,scope_qualified_for_publication=False,public_export_authorized=False,successful_forecast=False)
    write(storage,output/"RESTORED.json",result)
    reader=dict(schema_version=VERSION+"-reader-handoff",archive=handoff,restorer=current,witness_descriptor=witness_descriptor)
    if not exporter:write(storage,output/"READER_HANDOFF.json",reader)
    if exporter and validation["qualified_selected"]:
        write(storage,output/"EXPORT_INPUTS.json",dict(schema_version=VERSION+"-export-inputs",restored=cp.binding(output/"RESTORED.json"),
            producer_proof=index["producer_proof"],restorer_proof=prior_witness,exporter=current,exporter_proofs=proofs,
            selected=aliases["runtime/selected.jsonl.gz"],selected_completion=aliases["runtime/selected.jsonl.completion.json"],
            candidate_census=aliases["runtime/CANDIDATES.json"],prevalues_catalog=aliases["runtime/SELECTED_VERSION_CATALOG.json"],
            feature_snapshot=aliases["runtime/features.parquet"],identity_bridge=aliases["runtime/IDENTITY_BRIDGE.json"],
            rights=None,policy_acceptance=None,public_export_authorized=False,scope_qualified_for_publication=False))
    return result


def consume(reader_handoff,factory,package,**kwargs):
    return restore(reader_handoff["archive"],factory,package,reader_handoff=reader_handoff,**kwargs)
