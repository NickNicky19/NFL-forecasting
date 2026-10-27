"""Same-code cross-run history recovery; public metadata is never a live grant.

The current guarded process authenticates the old completed delivery and source
BEFORE any private GET. A private envelope preserves the original native read
evidence: a seven-field digest alone cannot qualify old durability. Recovery
receipts keep today's identity and clock; original grading clocks stay original.
No import performs IO. Publication and envelope append belong to the parent.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import re
import time
import zlib

VERSION = "audit-weekly-grade-history-v1"
CHECKPOINT_V1 = "audit-weekly-grade-checkpoint-v1"
CHECKPOINT_V2 = "audit-weekly-grade-checkpoint-v2"
PART_READ_KEYS = {"schema_version","index","descriptor_sha256","root_native_proof_sha256","root_body_sha256",
    "payload_sha256","bytes","reader","inventory_canonical_sha256","manifest_api_sha256","payload_api_sha256",
    "started_at_utc","completed_at_utc","HTTP_calls","transfer_bytes"}
CONTEXT_V2 = "audit-weekly-recurring-v2-context"
CONTEXT_V4 = "audit-weekly-recurring-v4-context"
CONTEXT_V5 = "audit-weekly-recurring-v5-context"
LOCATOR_VERSION = "audit-weekly-grade-history-v2-locator"
LOCATOR_REF = LOCATOR_VERSION + "-reference"
LOCATOR_ROOT = "state/controller-v1/history-v2"
LOCATOR_KEYS = {"schema_version", "repository", "anchor", "cohort", "sidecar", "planning", "helper_sha256"}
COHORT_KEYS = {"schema_version", "kind", "repository", "source_sha", "run_id", "root_go_sha256",
    "workflow_sha256", "epoch_sha256", "feed_sha256", "jobs", "root_issued_at_utc", "verified_at",
    "created_at", "fits", "public_release", "successful_forecast"}
ENVELOPE_V2_KEYS = {"schema_version", "handoff_sha256", "grade_read_proof", "native_read_evidence", "durable_sha256",
    "grade_code_pins", "checkpoint_helper_sha256", "planning", "root_go"}
LOCATOR_HELPERS = {"nfl_lab/audit_weekly_grade_history_v1.py", "nfl_lab/audit_weekly_hosted_v1.py",
    "nfl_lab/audit_weekly_operations_v1.py", "nfl_lab/audit_weekly_operations_worker_v1.py",
    "nfl_lab/audit_weekly_operations_grade_v1.py", "nfl_lab/audit_weekly_operations_restore_v1.py",
    "nfl_lab/audit_weekly_resume_v1.py", "nfl_lab/audit_weekly_template_v1.py"}
FILES = ("nfl_lab/audit_weekly_grade_history_v1.py", "tests/test_audit_weekly_grade_history_v1.py")
SIDECAR_KEYS = {"schema_version", "repository", "feed_sha256", "source_sha", "run_id", "root_go_sha256",
    "workflow_ref", "workflow_sha256", "epoch_sha256", "checkpoint_handoff", "grade_read_proof",
    "grade_code_pins", "checkpoint_helper_sha256", "evidence_descriptor", "evidence_producer"}
PROOF_KEYS = {"schema_version", "snapshot_sha256", "restored_body_sha256", "known_by_at", "producer", "reader", "proof_sha256"}
ENVELOPE_KEYS = {"schema_version", "handoff_sha256", "grade_read_proof", "native_read_evidence", "durable_sha256",
    "grade_code_pins", "checkpoint_helper_sha256"}
LIMITS = dict(sidecar_bytes=64 << 10, metadata_plain_bytes=128 << 10, envelope_bytes=256 << 10,
    snapshot_bytes=8 << 20, source_bytes=128 << 10, wall_seconds=180, CPU_seconds=120,
    address_space_bytes=512 << 20, clients=3, HTTP_per_client=40, fits=0, retries=0)
_KEY = object()
# Fixed metadata ABI for the first same-code adapter. These inventories are
# checked against the caller's already authenticated Root pins, without opening
# source files or importing the numerical grader/checkpoint implementations.
_GRADE_PIN_PATHS = {"nfl_lab/audit_weekly_grade_v1.py", "tools/audit_weekly_grade_v1.py", "nfl_lab/weekly_grading.py",
    "nfl_lab/weekly_adaptive.py", "nfl_lab/state.py", "nfl_lab/audit_weekly_epoch_v1.py", "nfl_lab/weekly_generic_producer.py",
    "nfl_lab/audit_weekly_retained_v1.py", "nfl_lab/weekly_durable_acceptance.py"}
_CHECKPOINT_PIN_PATHS = {"nfl_lab/audit_weekly_grade_checkpoint_v1.py", "tools/audit_weekly_grade_checkpoint_v1.py",
    "tests/test_audit_weekly_grade_checkpoint_v1.py"}
_HANDOFF_KEYS = {"schema_version", "repository", "current_root_go_sha256", "epoch_sha256", "snapshot_sha256", "body_sha256",
    "body_bytes", "snapshot_completed_at", "producer", "runtime_binding_sha256", "qualified_package_sha256", "grade_code_pins_sha256",
    "helper_sha256", "descriptor", "append_proof", "append_proof_sha256", "successful_forecast", "public_release", "fits"}
_APPEND_KEYS = {"schema_version", "current_root_go_sha256", "producer", "epoch_sha256", "snapshot_sha256", "body_sha256", "body_bytes",
    "descriptor_sha256", "qualification_sha256", "api_evidence_sha256", "started_at_utc", "completed_at_utc", "HTTP_calls", "transfer_bytes"}
_RECEIPT_HASH_KEYS = {"root_go_sha256", "policy_sha256", "workflow_sha256", "recipe_registration_sha256", "rights_authority_sha256",
    "r0_identity_sha256", "origin_choice_sha256", "feed_sha256", "archive_index_sha256", "archive_files_sha256",
    "reader_witness_sha256", "epoch_sha256", "choice_sha256"}
_RECEIPT_KEYS = _RECEIPT_HASH_KEYS | {"schema_version", "source_sha", "run_id", "policy_registered_at_utc", "feed_bytes", "rows",
    "categories", "jobs", "created_at", "verified_at", "fits", "raw_or_models_public"}
_METADATA_POLICY_SHA = "e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441"
_METADATA_TARGETS = {"pass_yd","pass_td","pass_cmp","pass_att","pass_int","rush_yd","rush_att","rec","rec_yd","rush_rec_yd","anytime_td"}


class HistoryError(ValueError): pass


def require(ok, code):
    if not ok: raise HistoryError(code)


def now(): return datetime.now(timezone.utc)


def checkpoint_version(handoff):
    require(type(handoff) is dict and handoff.get("schema_version") in {CHECKPOINT_V1+"-handoff",CHECKPOINT_V2+"-handoff"},
        "EXPLICIT_CLOSED_CHECKPOINT_WIRE_VERSION")
    return CHECKPOINT_V2 if handoff["schema_version"]==CHECKPOINT_V2+"-handoff" else CHECKPOINT_V1


def _modules():
    from . import audit_weekly_grade_v1 as grade, audit_weekly_grade_checkpoint_v1 as checkpoint
    from . import private_draft_store as store, gha_private_checkpoint as cp, state
    return grade, checkpoint, store, cp, state


def previous_checkpoint(go):
    """Closed Root locator; v1 never implicitly enables history."""
    _, _, store, _, _ = _modules()
    value = go["effective_epoch"]
    require(type(value) is dict, "CLOSED_HISTORY_ROOT_CONTEXT")
    prior=value.get("previous_capture")
    require(type(prior) is dict and set(prior)=={"feed_sha256","receipt_sha256"}
        and all(type(v) is str and store.HASH.fullmatch(v) for v in prior.values())
        and (value.get("controller_context") is None or type(value["controller_context"]) is dict),"CLOSED_HISTORY_PRIOR_CAPTURE_LOCATOR")
    if value.get("schema_version") == "audit-weekly-recurring-v1-context":
        require(set(value) == {"schema_version", "controller_context", "previous_capture"}, "CLOSED_HISTORY_V1_CONTEXT")
        return None
    require(value.get("schema_version") in {CONTEXT_V2, "audit-weekly-recurring-v3-context",CONTEXT_V4,CONTEXT_V5}
        and set(value) == {"schema_version", "controller_context", "previous_capture", "previous_checkpoint"}
            | ({"plan"} if value.get("schema_version") in {"audit-weekly-recurring-v3-context",CONTEXT_V4,CONTEXT_V5} else set())
            | ({"pending_post_recovery"} if value.get("schema_version")==CONTEXT_V5 else set()),
        "CLOSED_HISTORY_V2_CONTEXT")
    if value["schema_version"]==CONTEXT_V5:
        from .audit_weekly_template_v1 import pending_recovery
        pending_recovery(go)
    locator = value["previous_checkpoint"]
    if value["schema_version"] in {CONTEXT_V4,CONTEXT_V5} and type(locator) is dict and locator.get("schema_version")==LOCATOR_REF:
        return locator_reference(locator)
    require(locator is None or type(locator) is dict and set(locator) == {"sha256"}
        and type(locator["sha256"]) is str and store.HASH.fullmatch(locator["sha256"]), "EXACT_ROOT_HISTORY_SIDECAR_HASH")
    return locator


def locator_reference(value):
    from . import private_draft_store as store
    require(type(value) is dict and set(value)=={"schema_version","path","sha256"}
        and value["schema_version"]==LOCATOR_REF and type(value["sha256"]) is str and store.HASH.fullmatch(value["sha256"])
        and type(value["path"]) is str and re.fullmatch(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z--[1-9][0-9]{0,19}--[a-f0-9]{64}\.json\.gz",value["path"]),
        "CLOSED_IMMUTABLE_HISTORY_LOCATOR_REFERENCE")
    return value


def latest_locator(entries):
    """Filename ordering is a bounded hint; selected bytes/proofs are checked."""
    require(type(entries) is list and 0<len(entries)<=256,"BOUNDED_COMPLETE_HISTORY_LOCATOR_DIRECTORY")
    names=[]
    for row in entries:
        require(type(row) is dict and row.get("type")=="file" and type(row.get("name")) is str
            and row.get("path")==LOCATOR_ROOT+"/"+row["name"] and type(row.get("size")) is int
            and 0<row["size"]<=LIMITS["sidecar_bytes"],"CLOSED_IMMUTABLE_HISTORY_LOCATOR_ENTRY")
        locator_reference(dict(schema_version=LOCATOR_REF,path=row["name"],sha256="0"*64))
        names.append(row["name"])
    require(len(set(names))==len(names),"UNIQUE_HISTORY_LOCATOR_FILENAMES")
    latest=max(names)
    require(sum(n.split("--",1)[0]==latest.split("--",1)[0] for n in names)==1,"AMBIGUOUS_FRESHEST_HISTORY_REQUIRES_REVIEW")
    return latest


def require_latest(client, reference):
    """Public metadata recheck before any new decision; no body authority."""
    from . import private_draft_store as store
    locator_reference(reference)
    url=store.API+"/contents/"+LOCATOR_ROOT+"?ref=lab-state"
    client.allowed.add(url)
    require(latest_locator(client.json(url))==reference["path"],"NEWER_KNOWN_HISTORY_REQUIRES_A_FRESH_ROOT")


def validate_root_plan(value):
    from . import private_draft_store as store,state
    require(type(value) is dict and set(value)=={"kind","season","week","deadline_utc","calendar_sha256","game_cutoffs"}
        and value["kind"] in {"GRADE_ONLY","FUTURE_CAPABLE"} and type(value["season"]) is int and 2019<=value["season"]<=2100
        and type(value["week"]) is int and 1<=value["week"]<=18 and type(value["calendar_sha256"]) is str
        and store.HASH.fullmatch(value["calendar_sha256"]),"CLOSED_V4_CAUSAL_EXECUTION_PLAN")
    cuts=value["game_cutoffs"]
    require(type(cuts) is dict and len(cuts)<=32 and all(type(k) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}",k)
        and type(v) is str and 0<len(v)<=40 for k,v in cuts.items()),"FINITE_ROOT_FROZEN_CUTOFFS")
    if value["kind"]=="GRADE_ONLY":require(not cuts and value["deadline_utc"] is None,"GRADE_ONLY_HAS_NO_FUTURE_ISSUANCE_DEADLINE")
    else:require(cuts and state.utc(value["deadline_utc"])==min(map(state.utc,cuts.values())),"ACTUAL_FROZEN_DECISION_DEADLINE")
    return value


def next_plan(planning, *, at):
    """Routing hint from privately checked metadata; producer rechecks history."""
    from . import state
    validate_planning(planning);at=state.utc(at);current=planning["current"]
    future=[r for r in current["schedule"] if state.utc(r["kickoff_utc"])>at]
    target=current;cuts={}
    if future:
        require(all(r["game_id"] in current["game_cutoffs"] for r in future),"ALL_FUTURE_GAMES_KEEP_CANONICAL_CUTOFFS")
        remaining={r["game_id"]:current["game_cutoffs"][r["game_id"]] for r in future}
        if any(at<state.utc(t) for t in remaining.values()):
            require(all(at<state.utc(t) for t in remaining.values()),"MISSED_REQUIRED_FUTURE_CUTOFF_NO_COVERAGE_CUT")
            cuts=remaining
    require(state.utc(planning["known_by_at"])<at,"HISTORY_KNOWN_BEFORE_ACTUAL_PARENT_DECISION")
    if not cuts and current["week"] in planning["resolved_weeks"] and planning["next"] is not None:
        candidate=planning["next"]
        if all(at<state.utc(t) for t in candidate["game_cutoffs"].values()):target=candidate;cuts=target["game_cutoffs"]
    value=dict(kind="FUTURE_CAPABLE" if cuts else "GRADE_ONLY",season=target["season"],week=target["week"],
        deadline_utc=min(cuts.values(),key=state.utc) if cuts else None,
        calendar_sha256=state.digest(target["schedule"]),game_cutoffs=deepcopy(cuts))
    return validate_root_plan(value)


def _read(storage, ref, cap):
    from . import audit_weekly_archive_v1 as archive
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
        and type(ref["bytes"]) is int and 0 < ref["bytes"] <= cap, "BOUNDED_OWNED_HISTORY_REFERENCE")
    return archive.read_owned(storage, ref, ref["bytes"], raw=True)


def _unpack(body, cap):
    _, _, store, cp, _ = _modules()
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        chunks = []; size = 0
        while True:
            chunk = stream.read(min(16384, cap + 1 - size))
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            require(size <= cap, "BOUNDED_HISTORY_METADATA_INFLATION")
    raw = b"".join(chunks); doc = cp.strict_json(raw)
    require(raw == store.canonical(doc), "CANONICAL_HISTORY_METADATA")
    return doc


def _sidecar(value):
    grade, checkpoint, store, cp, state = _modules()
    from .weekly_durable_acceptance import identity
    require(type(value) is dict and set(value) == SIDECAR_KEYS and value["schema_version"] == VERSION + "-sidecar"
        and value["repository"] == store.REPO and value["grade_code_pins"] == grade.pins()
        and value["checkpoint_helper_sha256"] == checkpoint.pins(), "SAME_CODE_CLOSED_HISTORY_SIDECAR_REQUIRED")
    h = value["checkpoint_handoff"]; checkpoint.safe_handoff(h)
    p = value["grade_read_proof"]
    require(type(p) is dict and set(p) == PROOF_KEYS and p["schema_version"] == grade.VERSION + "-durability"
        and p["snapshot_sha256"] == h["snapshot_sha256"] and p["restored_body_sha256"] == h["body_sha256"]
        and p["producer"] == h["producer"] and store.HASH.fullmatch(str(p["proof_sha256"])), "EXACT_ORIGINAL_GRADE_READ_PROOF")
    writer, reader, evidence_writer = (identity(x) for x in (p["producer"], p["reader"], value["evidence_producer"]))
    require(writer["job_id"] == checkpoint.JOBS["writer"] and reader["job_id"] == evidence_writer["job_id"] == checkpoint.JOBS["reader"]
        and all(writer[k] == reader[k] == evidence_writer[k] for k in ("repository", "run_id", "run_attempt", "source_sha", "workflow_ref"))
        and all(writer[k] != reader[k] for k in ("job_id", "api_job_id", "process_identity"))
        and evidence_writer["api_job_id"] == reader["api_job_id"]
        and (value["source_sha"], value["run_id"], value["root_go_sha256"], value["epoch_sha256"], value["workflow_ref"])
            == (writer["source_sha"], writer["run_id"], h["current_root_go_sha256"], h["epoch_sha256"], writer["workflow_ref"])
        and h["grade_code_pins_sha256"] == state.digest(value["grade_code_pins"]), "EXACT_ORIGINAL_HISTORY_JOB_COHORT")
    e = cp.descriptor_meta(value["evidence_descriptor"], LIMITS["envelope_bytes"])
    require(e["producer_process"] == evidence_writer["process_identity"] and e["writer_run_id"] == writer["run_id"]
        and e["binding_sha256"] == h["runtime_binding_sha256"], "ORIGINAL_HISTORY_EVIDENCE_NAMESPACE_AND_PRODUCER")
    require(all(type(value[k]) is str and store.HASH.fullmatch(value[k]) for k in ("feed_sha256", "workflow_sha256"))
        and state.utc(h["snapshot_completed_at"]) <= state.utc(p["known_by_at"]), "ORIGINAL_HISTORY_HASHES_AND_CLOCK")
    return value


def sidecar_document(receipt, handoff, grade_read_proof, evidence_descriptor, evidence_producer):
    """Parent publishes canonical gzip only after its actual private append."""
    grade, checkpoint, _, _, _ = _modules()
    value = dict(schema_version=VERSION + "-sidecar", repository=handoff["repository"],
        **{k: receipt[k] for k in ("feed_sha256", "source_sha", "run_id", "root_go_sha256", "workflow_sha256")},
        workflow_ref=grade_read_proof["reader"]["workflow_ref"], epoch_sha256=handoff["epoch_sha256"],
        checkpoint_handoff=deepcopy(handoff), grade_read_proof=deepcopy(grade_read_proof), grade_code_pins=grade.pins(),
        checkpoint_helper_sha256=checkpoint.pins(), evidence_descriptor=deepcopy(evidence_descriptor), evidence_producer=deepcopy(evidence_producer))
    return _sidecar(value)


def _descriptor_meta(d,cap):
    from . import private_draft_store as store
    def hashed(value):return type(value) is str and store.HASH.fullmatch(value) is not None
    def positive(value):return type(value) is int and 0 < value < 10**20
    # Metadata-only equivalent of cp.descriptor_meta. Importing cp would
    # import operational_storage and pandas, so this fixed V1 ABI stays local.
    require(type(d) is dict and set(d)=={"entry","manifest_asset_id","manifest_sha256","manifest_bytes"},"CLOSED_PARENT_NATIVE_DESCRIPTOR")
    e=d["entry"]
    require(type(e) is dict and set(e)=={"schema_version","payload","payload_asset_id","payload_name","producer_process","binding_sha256","writer_run_id"},
        "CLOSED_PARENT_NATIVE_ENTRY")
    p=e["payload"]
    require(type(p) is dict and set(p)=={"schema_version","payload_kind","format","bytes","sha256","source_policy_sha256"}
        and p["schema_version"]=="weekly-private-payload-v2" and p["payload_kind"]=="runtime_manifest" and p["format"]=="gzip"
        and p["source_policy_sha256"]==_METADATA_POLICY_SHA and type(p["bytes"]) is int and 0<p["bytes"]<=cap and hashed(p["sha256"])
        and e["payload_name"]=="blob-"+p["sha256"]+".bin" and e["schema_version"]=="weekly-private-restore-manifest-v2"
        and hashed(e["producer_process"]) and hashed(e["binding_sha256"]) and type(e["writer_run_id"]) is str
        and re.fullmatch(r"[1-9][0-9]{0,19}",e["writer_run_id"]) and positive(e["payload_asset_id"]) and positive(d["manifest_asset_id"])
        and type(d["manifest_bytes"]) is int and d["manifest_bytes"]==len(store.canonical(e))<=16<<10
        and d["manifest_sha256"]==store.sha(store.canonical(e)),"EXACT_PARENT_NATIVE_DESCRIPTOR")
    return e


def private_checkpoint_root(packed, handoff):
    """Metadata-only V2 root validation; never decode a forecast/outcome part."""
    from . import private_draft_store as store,state
    require(checkpoint_version(handoff)==CHECKPOINT_V2 and type(packed) is bytes
        and len(packed)==handoff["body_bytes"] and store.sha(packed)==handoff["body_sha256"],"EXACT_PRIVATE_MULTIPART_ROOT_BYTES")
    wire=metadata_document(packed,cap=64 << 10)
    require(type(wire) is dict and set(wire)=={"schema_version","snapshot_manifest","snapshot_body_sha256","parts"}
        and wire["schema_version"]==CHECKPOINT_V2+"-root","CLOSED_PRIVATE_MULTIPART_ROOT")
    m=wire["snapshot_manifest"]
    require(type(m) is dict and set(m)=={"schema_version","logical_sha256","logical_bytes","parts"}
        and m["schema_version"]=="audit-weekly-grade-snapshot-v2" and m["logical_sha256"]==handoff["snapshot_sha256"]
        and type(m["logical_bytes"]) is int and 0<m["logical_bytes"]<=128 << 20
        and type(m["parts"]) is list and 0<len(m["parts"])<=2,"CLOSED_BOUNDED_PRIVATE_PARTITION_MANIFEST")
    fields={"index","name","bytes","sha256","decoded_bytes","decoded_sha256"}
    for i,p in enumerate(m["parts"]):
        require(type(p) is dict and set(p)==fields and type(p["index"]) is int and p["index"]==i
            and all(type(p[k]) is str and store.HASH.fullmatch(p[k]) for k in ("sha256","decoded_sha256"))
            and p["name"]==f"GRADING_PART_{i:02d}_{p['sha256']}.json.gz"
            and type(p["bytes"]) is int and 0<p["bytes"]<=8 << 20
            and type(p["decoded_bytes"]) is int and 0<p["decoded_bytes"]<=64 << 20,"EXACT_ORDERED_PRIVATE_PARTITION")
    require(sum(p["decoded_bytes"] for p in m["parts"])==m["logical_bytes"]
        and sum(p["bytes"] for p in m["parts"])<=16 << 20
        and wire["snapshot_body_sha256"]==store.sha(gzip.compress(state.canonical(m),mtime=0))
        and type(wire["parts"]) is list and len(wire["parts"])==len(m["parts"]),"EXACT_COMPLETE_LOCAL_AND_NATIVE_ROOT_RELATION")
    keys={"schema_version","index","local_manifest_sha256","body_sha256","body_bytes","descriptor_sha256",
        "producer","current_root_go_sha256","qualification_sha256","started_at_utc","completed_at_utc","HTTP_calls","transfer_bytes"}
    for p,r in zip(m["parts"],wire["parts"]):
        require(type(r) is dict and set(r)=={"index","descriptor","append_proof"}
            and type(r["index"]) is int and r["index"]==p["index"],"EXACT_PRIVATE_PART_DESCRIPTOR_ORDER")
        entry=_descriptor_meta(r["descriptor"],8 << 20);proof=r["append_proof"];outer=handoff["append_proof"]
        require(entry["payload"]["sha256"]==p["sha256"] and entry["payload"]["bytes"]==p["bytes"]
            and entry["producer_process"]==handoff["producer"]["process_identity"]
            and entry["writer_run_id"]==handoff["producer"]["run_id"]
            and entry["binding_sha256"]==handoff["runtime_binding_sha256"],"EXACT_PRIVATE_PART_NATIVE_DESCRIPTOR")
        require(type(proof) is dict and set(proof)==keys and proof["schema_version"]==CHECKPOINT_V2+"-part-append"
            and type(proof["index"]) is int and proof["index"]==p["index"] and proof["producer"]==handoff["producer"]
            and proof["local_manifest_sha256"]==wire["snapshot_body_sha256"]
            and proof["current_root_go_sha256"]==handoff["current_root_go_sha256"]
            and proof["qualification_sha256"]==outer["qualification_sha256"]
            and proof["body_sha256"]==p["sha256"] and type(proof["body_bytes"]) is int and proof["body_bytes"]==p["bytes"]
            and proof["descriptor_sha256"]==state.digest(r["descriptor"])
            and type(proof["HTTP_calls"]) is int and 0<proof["HTTP_calls"]<=outer["HTTP_calls"]<=40
            and type(proof["transfer_bytes"]) is int and 0<proof["transfer_bytes"]<=outer["transfer_bytes"]<=store.TRANSFER_CAP
            and state.utc(handoff["snapshot_completed_at"])<=state.utc(outer["started_at_utc"])
            <=state.utc(proof["started_at_utc"])<=state.utc(proof["completed_at_utc"])
            <=state.utc(outer["completed_at_utc"]),"EXACT_PRIVATE_PART_APPEND_PROOF")
    return wire


def validate_multipart_readback(value, handoff, native, reader, *, known_by_at, wire):
    """Bind every original part receipt to its private, hash-verified root."""
    from . import private_draft_store as store,state
    require(checkpoint_version(handoff)==CHECKPOINT_V2 and type(value) is dict
        and set(value)=={"schema_version","parts","completed_at_utc","HTTP_calls","transfer_bytes"}
        and value["schema_version"]==CHECKPOINT_V2+"-complete-part-read"
        and type(value["parts"]) is list and len(value["parts"])==len(wire["parts"]),"COMPLETE_ORIGINAL_NATIVE_PART_READ_REQUIRED")
    previous=state.utc(native["created_at_utc"]);calls=native["HTTP_calls"];transferred=native["transfer_bytes"];inventory=None
    for p,r,proof in zip(wire["snapshot_manifest"]["parts"],wire["parts"],value["parts"]):
        require(type(proof) is dict and set(proof)==PART_READ_KEYS and proof["schema_version"]==CHECKPOINT_V2+"-part-native-read"
            and type(proof["index"]) is int and proof["index"]==p["index"]
            and proof["descriptor_sha256"]==state.digest(r["descriptor"])
            and proof["root_native_proof_sha256"]==state.digest(native) and proof["root_body_sha256"]==handoff["body_sha256"]
            and proof["payload_sha256"]==p["sha256"] and type(proof["bytes"]) is int and proof["bytes"]==p["bytes"] and proof["reader"]==reader
            and all(type(proof[k]) is str and store.HASH.fullmatch(proof[k]) for k in
                ("inventory_canonical_sha256","manifest_api_sha256","payload_api_sha256"))
            and (inventory is None or inventory==proof["inventory_canonical_sha256"])
            and previous<=state.utc(proof["started_at_utc"])<=state.utc(proof["completed_at_utc"])<=state.utc(known_by_at)
            and type(proof["HTTP_calls"]) is int and calls+4<=proof["HTTP_calls"]<=40
            and type(proof["transfer_bytes"]) is int and transferred<proof["transfer_bytes"]<=store.TRANSFER_CAP,
            "EXACT_ORIGINAL_NATIVE_PART_PROOF_AND_CLOCK")
        previous=state.utc(proof["completed_at_utc"]);calls=proof["HTTP_calls"];transferred=proof["transfer_bytes"]
        inventory=proof["inventory_canonical_sha256"]
    require(previous<=state.utc(value["completed_at_utc"])<=state.utc(known_by_at)
        and type(value["HTTP_calls"]) is int and calls<value["HTTP_calls"]<=40
        and type(value["transfer_bytes"]) is int and transferred<value["transfer_bytes"]<=store.TRANSFER_CAP,
        "NATIVE_PARTS_COMPLETE_BEFORE_ORIGINAL_KNOWN_BY")
    return value


def validate_parent_sidecar(packed, *, receipt, qualified_runtime, code_pins, jobs, at):
    """Strict original feed-linked reader; never accepts v2 locators/cohorts."""
    return _validate_parent_core(packed, receipt=receipt, qualified_runtime=qualified_runtime,
        code_pins=code_pins, jobs=jobs, at=at, grading_cohort=False)


def _validate_parent_core(packed, *, receipt, qualified_runtime, code_pins, jobs, at, grading_cohort):
    """Return exact parsed metadata, never a history/durability authority.

The parent supplies its live-authenticated receipt, Root pins, namespace and
three completed API job dictionaries. This function performs no filesystem or
network IO and decodes no checkpoint, envelope, forecast or outcome body. The
complete original native read evidence is still mandatory at restore_previous.
"""
    from . import private_draft_store as store, state
    from .weekly_durable_acceptance import identity
    def hashed(value): return type(value) is str and store.HASH.fullmatch(value) is not None
    def positive(value): return type(value) is int and 0 < value < 10**20
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,"DUPLICATE_PARENT_HISTORY_JSON")
            result[key]=value
        return result
    def nonfinite(_):raise HistoryError("NONFINITE_PARENT_HISTORY_JSON")
    descriptor=_descriptor_meta
    try:
        require(type(packed) is bytes and 0 < len(packed) <= LIMITS["sidecar_bytes"], "BOUNDED_PARENT_HISTORY_SIDECAR")
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        plain = decoder.decompress(packed, LIMITS["metadata_plain_bytes"] + 1)
        require(len(plain) <= LIMITS["metadata_plain_bytes"] and decoder.eof
            and not decoder.unused_data and not decoder.unconsumed_tail, "BOUNDED_SINGLE_PARENT_HISTORY_GZIP")
        value = json.loads(plain,object_pairs_hook=pairs,parse_constant=nonfinite)
        require(plain == store.canonical(value), "CANONICAL_PARENT_HISTORY_SIDECAR")
        require(type(code_pins) is dict and 0 < len(code_pins) <= 128
            and all(type(k) is str and hashed(v) for k,v in code_pins.items())
            and _GRADE_PIN_PATHS | _CHECKPOINT_PIN_PATHS | set(FILES) | {".github/workflows/lab.yml"} <= set(code_pins), "EXACT_ROOT_PARENT_HISTORY_CODE_PINS")
        grade_pins = {n:code_pins[n] for n in _GRADE_PIN_PATHS}
        checkpoint_pins = {n:code_pins[n] for n in _CHECKPOINT_PIN_PATHS}
        require(type(value) is dict and set(value) == SIDECAR_KEYS and value["schema_version"] == VERSION + "-sidecar"
            and value["repository"] == store.REPO and value["grade_code_pins"] == grade_pins
            and value["checkpoint_helper_sha256"] == checkpoint_pins, "SAME_CODE_CLOSED_PARENT_HISTORY_SIDECAR")
        if grading_cohort:
            validate_cohort(receipt)
        else:
            require(type(receipt) is dict and set(receipt) == _RECEIPT_KEYS
            and receipt["schema_version"] == "audit-weekly-delivery-v1-public-receipt"
            and len(store.canonical(receipt)) <= 64 << 10 and all(hashed(receipt[k]) for k in _RECEIPT_HASH_KEYS)
            and type(receipt["source_sha"]) is str and re.fullmatch(r"[a-f0-9]{40}",receipt["source_sha"])
            and type(receipt["run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}",receipt["run_id"])
            and type(receipt["fits"]) is int and receipt["fits"] == 0 and receipt["raw_or_models_public"] is False
            and type(receipt["rows"]) is int and 0 < receipt["rows"] <= 5000
            and type(receipt["feed_bytes"]) is int and 0 < receipt["feed_bytes"] <= 4 << 20,
                "CLOSED_PARENT_HISTORY_DELIVERY_RECEIPT")
        require(grading_cohort or type(receipt["categories"]) is list and receipt["categories"]
            and all(type(c) is str for c in receipt["categories"])
            and receipt["categories"] == sorted(set(receipt["categories"]))
            and set(receipt["categories"]) <= _METADATA_TARGETS, "CLOSED_PARENT_HISTORY_RECEIPT_CATEGORIES")
        require(all(value[k] == receipt[k] for k in ("feed_sha256","source_sha","run_id","root_go_sha256","workflow_sha256","epoch_sha256")),
            "EXACT_PARENT_HISTORY_RECEIPT_BINDINGS")
        require(value["workflow_sha256"] == code_pins[".github/workflows/lab.yml"], "EXACT_PARENT_HISTORY_WORKFLOW_PIN")
        require(type(qualified_runtime) is dict and set(qualified_runtime) == {"schema_version","runtime_reserved_bytes","runtime_id",
            "binding","qualification","quota_reservation","run_id","source_sha"}
            and qualified_runtime["schema_version"] == "audit-private-rotation-v1-qualified-runtime"
            and type(qualified_runtime["runtime_reserved_bytes"]) is int and qualified_runtime["runtime_reserved_bytes"] == store.TOTAL_CAP,
            "CLOSED_PARENT_HISTORY_RUNTIME_PACKAGE")
        binding = qualified_runtime["binding"]; qualification = qualified_runtime["qualification"]
        require(type(binding) is dict and set(binding) == {"schema_version","repository","runtime_id","origin_run_id","release_id","tag_name",
            "canary_asset_id","canary_name","canary_sha256","canary_bytes","browser_tag","config_sha256"}
            and binding["schema_version"] == "weekly-private-draft-binding-v2" and binding["repository"] == store.REPO
            and binding["config_sha256"] == store.CONFIG_SHA256 and positive(binding["release_id"]) and binding["release_id"] != 422575680
            and type(binding["runtime_id"]) is str and re.fullmatch(r"[a-f0-9]{32}",binding["runtime_id"])
            and type(binding["origin_run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}",binding["origin_run_id"])
            and binding["tag_name"] == "weekly-private-runtime-v2-" + binding["runtime_id"]
            and positive(binding["canary_asset_id"]) and hashed(binding["canary_sha256"])
            and binding["canary_name"] == "canary-" + binding["canary_sha256"] + ".txt"
            and type(binding["canary_bytes"]) is int and binding["canary_bytes"] == 117
            and type(binding["browser_tag"]) is str and (binding["browser_tag"] == binding["tag_name"]
                or re.fullmatch(r"untagged-[a-f0-9]{20}",binding["browser_tag"])), "CLOSED_PARENT_HISTORY_RUNTIME_BINDING")
        binding_sha = store.sha(store.canonical(binding))
        require(type(qualification) is dict and set(qualification) == store.BASE_PROOF_FIELDS | store.PHASE_FIELDS["qualified"]
            and qualification["schema_version"] == "weekly-private-proof-v2.1" and qualification["phase"] == "qualified"
            and qualification["operation"] == store.PHASE_OPERATION["qualified"]
            and qualification["binding_sha256"] == binding_sha and qualification["config_sha256"] == store.CONFIG_SHA256
            and qualified_runtime["runtime_id"] == binding["runtime_id"]
            and qualified_runtime["run_id"] == binding["origin_run_id"] == qualification["run_id"]
            and qualified_runtime["source_sha"] == qualification["source_sha"], "EXACT_PARENT_HISTORY_RUNTIME_METADATA")
        h = value["checkpoint_handoff"];wire_version=checkpoint_version(h)
        require(type(h) is dict and set(h) == _HANDOFF_KEYS and h["schema_version"] == wire_version+"-handoff"
            and h["repository"] == store.REPO and h["successful_forecast"] is h["public_release"] is False
            and type(h["fits"]) is int and h["fits"] == 0 and h["helper_sha256"] == checkpoint_pins
            and all(hashed(h[k]) for k in ("current_root_go_sha256","epoch_sha256","snapshot_sha256","body_sha256",
                "runtime_binding_sha256","qualified_package_sha256","grade_code_pins_sha256","append_proof_sha256"))
            and type(h["body_bytes"]) is int and 0 < h["body_bytes"] <= LIMITS["snapshot_bytes"]
            and len(store.canonical(h)) <= 16 << 10, "CLOSED_PARENT_HISTORY_CHECKPOINT_HANDOFF")
        require(h["runtime_binding_sha256"] == binding_sha and h["qualified_package_sha256"] == state.digest(qualified_runtime)
            and h["grade_code_pins_sha256"] == state.digest(grade_pins), "EXACT_PARENT_HISTORY_NAMESPACE_AND_PINS")
        proof = value["grade_read_proof"]
        require(type(proof) is dict and set(proof) == PROOF_KEYS and proof["schema_version"] == "audit-weekly-grade-v1-durability"
            and proof["snapshot_sha256"] == h["snapshot_sha256"] and proof["restored_body_sha256"] == h["body_sha256"]
            and proof["producer"] == h["producer"] and hashed(proof["proof_sha256"]), "EXACT_PARENT_ORIGINAL_GRADE_READ_PROOF")
        writer,reader,evidence_writer = (identity(x) for x in (proof["producer"],proof["reader"],value["evidence_producer"]))
        require(writer["job_id"] == "audit-weekly-restore-v1" and reader["job_id"] == evidence_writer["job_id"] == "audit-weekly-export-v1"
            and all(writer[k] == reader[k] == evidence_writer[k] for k in ("repository","run_id","run_attempt","source_sha","workflow_ref"))
            and all(writer[k] != reader[k] for k in ("job_id","api_job_id","process_identity"))
            and evidence_writer["api_job_id"] == reader["api_job_id"]
            and (value["source_sha"],value["run_id"],value["root_go_sha256"],value["epoch_sha256"],value["workflow_ref"])
                == (writer["source_sha"],writer["run_id"],h["current_root_go_sha256"],h["epoch_sha256"],writer["workflow_ref"]),
            "EXACT_PARENT_ORIGINAL_HISTORY_JOB_COHORT")
        snapshot_entry = descriptor(h["descriptor"],LIMITS["snapshot_bytes"])
        envelope_entry = descriptor(value["evidence_descriptor"],LIMITS["envelope_bytes"])
        require(snapshot_entry["payload"]["sha256"] == h["body_sha256"] and snapshot_entry["payload"]["bytes"] == h["body_bytes"]
            and all(entry["writer_run_id"] == value["run_id"] and entry["binding_sha256"] == binding_sha
                and entry["producer_process"] == producer["process_identity"]
                for entry,producer in ((snapshot_entry,writer),(envelope_entry,evidence_writer))), "EXACT_PARENT_ORIGINAL_NATIVE_DESCRIPTORS")
        assets=[h["descriptor"]["manifest_asset_id"],snapshot_entry["payload_asset_id"],value["evidence_descriptor"]["manifest_asset_id"],envelope_entry["payload_asset_id"]]
        require(len(set(assets)) == 4 and binding["canary_asset_id"] not in assets,"DISTINCT_PARENT_HISTORY_NATIVE_ASSETS")
        append = h["append_proof"]
        require(type(append) is dict and set(append) == _APPEND_KEYS and append["schema_version"] == wire_version+"-native-append"
            and state.digest(append) == h["append_proof_sha256"] and append["producer"] == writer
            and all(append[k] == h[k] for k in ("current_root_go_sha256","epoch_sha256","snapshot_sha256","body_sha256","body_bytes"))
            and append["descriptor_sha256"] == state.digest(h["descriptor"])
            and append["qualification_sha256"] == state.digest(qualification) and hashed(append["api_evidence_sha256"])
            and type(append["HTTP_calls"]) is int and 0 < append["HTTP_calls"] <= 40
            and type(append["transfer_bytes"]) is int and 0 < append["transfer_bytes"] <= store.TRANSFER_CAP,
            "EXACT_PARENT_ORIGINAL_CHECKPOINT_APPEND_METADATA")
        receipt_jobs=receipt["jobs"]
        require(type(receipt_jobs) is dict and set(receipt_jobs) == {"produce","restore","consume"}
            and type(jobs) is dict and set(jobs) == set(receipt_jobs)
            and all(type(ref) is dict and set(ref) == {"job_id","api_job_id"} and type(ref["job_id"]) is str
                and re.fullmatch(r"[A-Za-z0-9_-]{1,100}",ref["job_id"]) and positive(ref["api_job_id"]) for ref in receipt_jobs.values())
            and len({ref["job_id"] for ref in receipt_jobs.values()}) == len({ref["api_job_id"] for ref in receipt_jobs.values()}) == 3,
            "CLOSED_PARENT_HISTORY_THREE_RECEIPT_JOBS")
        for role,j in jobs.items():
            ref=receipt_jobs[role]
            require(type(j) is dict and type(j.get("id")) is int and j["id"] == ref["api_job_id"] and j.get("name") == ref["job_id"]
                and type(j.get("run_id")) is int and j["run_id"] == int(value["run_id"]) and j.get("head_sha") == value["source_sha"]
                and j.get("status") == "completed" and j.get("conclusion") == "success"
                and state.utc(j["started_at"]) <= state.utc(j["completed_at"]) <= state.utc(at), "SUCCESSFUL_PARENT_HISTORY_API_JOB_METADATA")
        require(receipt_jobs["restore"] == {k:writer[k] for k in ("job_id","api_job_id")}
            and receipt_jobs["consume"] == {k:reader[k] for k in ("job_id","api_job_id")}
            and state.utc(qualification["created_at_utc"]) <= state.utc(append["started_at_utc"])
            and state.utc(receipt["root_issued_at_utc" if grading_cohort else "policy_registered_at_utc"]) <= state.utc(receipt["verified_at"])
            and state.utc(jobs["produce"]["completed_at"]) <= state.utc(jobs["restore"]["started_at"])
            <= state.utc(h["snapshot_completed_at"]) <= state.utc(append["started_at_utc"])
            <= state.utc(append["completed_at_utc"]) <= state.utc(jobs["restore"]["completed_at"])
            <= state.utc(jobs["consume"]["started_at"]) <= state.utc(proof["known_by_at"])
            <= state.utc(receipt["verified_at"]) <= state.utc(receipt["created_at"])
            <= state.utc(jobs["consume"]["completed_at"]) <= state.utc(at), "ORIGINAL_PARENT_HISTORY_CLOCKS")
        return value
    except HistoryError:
        raise
    except (KeyError,TypeError,ValueError,OverflowError,zlib.error,store.StoreError):
        raise HistoryError("INVALID_PARENT_HISTORY_METADATA") from None


def metadata_document(packed, *, cap=None):
    """Canonical bounded metadata only; safe in Main without numerical modules."""
    from . import private_draft_store as store
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,"DUPLICATE_HISTORY_METADATA_KEY");result[key]=value
        return result
    def reject(_):raise HistoryError("NONFINITE_HISTORY_METADATA")
    cap=LIMITS["metadata_plain_bytes"] if cap is None else cap
    require(type(packed) is bytes and 0<len(packed)<=LIMITS["envelope_bytes"],"BOUNDED_HISTORY_METADATA")
    try:
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS);raw=decoder.decompress(packed,cap+1)
        require(len(raw)<=cap and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,"ONE_BOUNDED_HISTORY_METADATA_MEMBER")
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=reject)
        require(raw==store.canonical(value),"CANONICAL_HISTORY_METADATA")
        return value
    except (ValueError,TypeError,UnicodeError,zlib.error):raise HistoryError("INVALID_HISTORY_METADATA") from None


def validate_cohort(value):
    from . import private_draft_store as store,state
    require(type(value) is dict and set(value)==COHORT_KEYS and value["schema_version"]==LOCATOR_VERSION+"-cohort"
        and value["kind"] in {"GRADING_ONLY","CAPTURE_AND_GRADE"} and value["repository"]==store.REPO
        and type(value["fits"]) is int and value["fits"]==0
        and value["public_release"] is value["successful_forecast"] is False,"CLOSED_NONFORECAST_HISTORY_COHORT")
    require(type(value["source_sha"]) is str and re.fullmatch(r"[a-f0-9]{40}",value["source_sha"])
        and type(value["run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}",value["run_id"])
        and all(type(value[k]) is str and store.HASH.fullmatch(value[k]) for k in
            ("root_go_sha256","workflow_sha256","epoch_sha256","feed_sha256")),"EXACT_HISTORY_COHORT_SOURCE_AND_HASHES")
    require(type(value["jobs"]) is dict and set(value["jobs"])=={"produce","restore","consume"}
        and all(type(v) is dict and set(v)=={"job_id","api_job_id"} and type(v["job_id"]) is str
            and re.fullmatch(r"[A-Za-z0-9_-]{1,100}",v["job_id"]) and type(v["api_job_id"]) is int and v["api_job_id"]>0
            for v in value["jobs"].values())
        and len({v["api_job_id"] for v in value["jobs"].values()})==3,"EXACT_HISTORY_COHORT_JOBS")
    require(state.utc(value["root_issued_at_utc"])<=state.utc(value["verified_at"])<=state.utc(value["created_at"]),
        "HISTORY_COHORT_CLOCKS")
    return value


def validate_planning(value):
    from . import private_draft_store as store,state
    require(type(value) is dict and set(value)=={"schema_version","epoch_sha256","current","next","resolved_weeks","known_by_at","calendar"}
        and value["schema_version"]==LOCATOR_VERSION+"-planning" and type(value["epoch_sha256"]) is str
        and store.HASH.fullmatch(value["epoch_sha256"]),"CLOSED_CAUSAL_HISTORY_PLANNING_METADATA")
    def week(w,current):
        keys={"season","week","schedule","game_cutoffs"}|({"canonical_choice_sha256"} if current else set())
        require(type(w) is dict and set(w)==keys and type(w["season"]) is int and 2019<=w["season"]<=2100
            and type(w["week"]) is int and 1<=w["week"]<=18,"CLOSED_HISTORY_WEEK")
        rows=w["schedule"];fields={"season","week","game_type","game_id","kickoff_utc"}
        require(type(rows) is list and 0<len(rows)<=32 and all(type(r) is dict and set(r)==fields
            and type(r["season"]) is int and type(r["week"]) is int
            and (r["season"],r["week"])==(w["season"],w["week"]) and r["game_type"]=="REG"
            and type(r["game_id"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}",r["game_id"]) for r in rows)
            and len({r["game_id"] for r in rows})==len(rows),"FULL_PUBLIC_SAFE_HISTORY_CALENDAR")
        cuts=w["game_cutoffs"]
        require(type(cuts) is dict and cuts and set(cuts)<=set(r["game_id"] for r in rows)
            and (current or set(cuts)==set(r["game_id"] for r in rows)),"EXACT_FROZEN_HISTORY_CUTOFF_CENSUS")
        for r in rows:
            state.utc(r["kickoff_utc"])
            if r["game_id"] in cuts:require(state.utc(cuts[r["game_id"]])<state.utc(r["kickoff_utc"]),"FROZEN_CUTOFF_BEFORE_KICKOFF")
        if current:require(type(w["canonical_choice_sha256"]) is str and store.HASH.fullmatch(w["canonical_choice_sha256"]),"EXACT_CANONICAL_WEEKLY_CHOICE_HASH")
    week(value["current"],True)
    if value["next"] is not None:
        week(value["next"],False)
        require(value["next"]["season"]==value["current"]["season"] and value["next"]["week"]==value["current"]["week"]+1,
            "ONLY_ADJACENT_SAME_SEASON_REG_WEEK")
    require(type(value["resolved_weeks"]) is list and len(value["resolved_weeks"])<=18
        and value["resolved_weeks"]==sorted(set(value["resolved_weeks"]))
        and all(type(w) is int and 1<=w<=value["current"]["week"] for w in value["resolved_weeks"]),"CAUSAL_RESOLVED_CURRENT_EPOCH_WEEKS")
    cal=value["calendar"]
    require(type(cal) is dict and set(cal)=={"url","sha256","bytes","retrieved_utc"}
        and cal["url"]=="https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
        and type(cal["sha256"]) is str and store.HASH.fullmatch(cal["sha256"])
        and type(cal["bytes"]) is int and 0<cal["bytes"]<=8<<20
        and state.utc(cal["retrieved_utc"])<=state.utc(value["known_by_at"]),"ACTUAL_CALENDAR_PROVENANCE_BEFORE_HISTORY_READ")
    return value


def locator_filename(value):
    from . import state
    stamp=state.utc(value["sidecar"]["grade_read_proof"]["known_by_at"]).strftime("%Y%m%dT%H%M%S.%fZ")
    return stamp+"--"+value["cohort"]["run_id"]+"--"+value["sidecar"]["checkpoint_handoff"]["snapshot_sha256"]+".json.gz"


def locator_metadata(packed, *, receipt, qualified_runtime, code_pins, jobs, at):
    """New opt-in protocol. Return metadata, never future/history authority."""
    from . import private_draft_store as store,state
    require(type(packed) is bytes and 0<len(packed)<=LIMITS["sidecar_bytes"],"BOUNDED_PUBLIC_HISTORY_LOCATOR")
    value=metadata_document(packed)
    require(type(value) is dict and set(value)==LOCATOR_KEYS and value["schema_version"]==LOCATOR_VERSION
        and value["repository"]==store.REPO,"CLOSED_PUBLIC_NONFORECAST_HISTORY_LOCATOR")
    validate_cohort(value["cohort"]);validate_planning(value["planning"])
    require(type(value["helper_sha256"]) is dict and set(value["helper_sha256"])==LOCATOR_HELPERS
        and all(code_pins.get(n)==h for n,h in value["helper_sha256"].items()),"EXACT_LOCATOR_EXECUTABLE_HELPER_PINS")
    anchor=value["anchor"]
    require(type(anchor) is dict and set(anchor)=={"feed_sha256","receipt_sha256"}
        and all(type(v) is str and store.HASH.fullmatch(v) for v in anchor.values())
        and anchor["feed_sha256"]==receipt["feed_sha256"]==value["cohort"]["feed_sha256"],"UNCHANGED_ORIGINAL_FEED_ANCHOR")
    # Original feed metadata is checked independently; it is never relabeled to
    # have the later grading run's identity, Root, jobs, or success state.
    require(type(receipt) is dict and set(receipt)==_RECEIPT_KEYS and receipt["schema_version"]=="audit-weekly-delivery-v1-public-receipt"
        and receipt["epoch_sha256"]==value["cohort"]["epoch_sha256"] and receipt["source_sha"]==value["cohort"]["source_sha"],
        "SAME_SOURCE_ORIGINAL_CAPTURE_AND_GRADING_EPOCH")
    core=value["sidecar"];cohort=value["cohort"]
    checked=_validate_parent_core(gzip.compress(store.canonical(core),mtime=0),receipt=cohort,
        qualified_runtime=qualified_runtime,code_pins=code_pins,jobs=jobs,at=at,grading_cohort=True)
    require(checked==core and core["epoch_sha256"]==value["planning"]["epoch_sha256"]
        and value["planning"]["known_by_at"]==core["grade_read_proof"]["known_by_at"]
        and state.utc(core["grade_read_proof"]["known_by_at"])<=state.utc(at),"EXACT_CAUSAL_LOCATOR_AND_READER_COHORT")
    return value


def locator_document(anchor, cohort, handoff, proof, descriptor, producer, planning, *, code_pins):
    """Build a closed metadata locator after the real private evidence append.

    Completion of the run is deliberately checked by the later reader. This
    file records no forecast, contains no outcome rows, and grants no authority.
    """
    from . import private_draft_store as store
    validate_cohort(cohort);validate_planning(planning)
    require(set(LOCATOR_HELPERS)<=set(code_pins),"ALL_LOCATOR_HELPERS_PINNED")
    value=dict(schema_version=LOCATOR_VERSION,repository=store.REPO,anchor=deepcopy(anchor),
        cohort=deepcopy(cohort),sidecar=sidecar_document(cohort,handoff,proof,descriptor,producer),
        planning=deepcopy(planning),helper_sha256={p:code_pins[p] for p in sorted(LOCATOR_HELPERS)})
    require(set(anchor)=={"feed_sha256","receipt_sha256"} and anchor["feed_sha256"]==cohort["feed_sha256"]
        and all(type(v) is str and store.HASH.fullmatch(v) for v in anchor.values())
        and planning["epoch_sha256"]==cohort["epoch_sha256"]
        and planning["known_by_at"]==proof["known_by_at"],"EXACT_ORIGINAL_LOCATOR_ANCHOR_AND_PLANNING")
    require(len(store.canonical(value))<=LIMITS["metadata_plain_bytes"],"BOUNDED_LOCATOR_METADATA")
    return value


def prepare_envelope(result, handoff, native_evidence_ref, *, storage, output, planning=None, root_go=None):
    """Lossless private evidence, prepared locally; no append/publication grant."""
    grade, checkpoint, store, cp, state = _modules()
    require(type(result) is checkpoint.Restored, "LIVE_ORIGINAL_GRADE_READ_RESULT_REQUIRED")
    result.verify(); checkpoint.safe_handoff(handoff)
    body = cp.strict_json(_read(storage, native_evidence_ref, LIMITS["envelope_bytes"]))
    require(state.digest(body) == result.proof["proof_sha256"] and body["context"]["handoff"] == handoff
        and body["native_restore_proof"]["payload_sha256"] == handoff["body_sha256"]
        and result.proof["snapshot_sha256"] == handoff["snapshot_sha256"], "EXACT_ORIGINAL_NATIVE_READ_EVIDENCE_REQUIRED")
    if checkpoint_version(handoff)==CHECKPOINT_V2:
        root=private_checkpoint_root(_read(storage,body["restored_binding"],8 << 20),handoff)
        validate_multipart_readback(body["context"].get("multipart_readback"),handoff,body["native_restore_proof"],result.proof["reader"],
            known_by_at=result.proof["known_by_at"],wire=root)
    envelope = dict(schema_version=VERSION + "-evidence-envelope", handoff_sha256=store.sha(store.canonical(handoff)),
        grade_read_proof=deepcopy(result.proof), native_read_evidence=body, durable_sha256=grade._digest(result.durable.document),
        grade_code_pins=grade.pins(), checkpoint_helper_sha256=checkpoint.pins())
    if planning is not None:
        require(type(root_go) is dict and root_go["effective_epoch"]["schema_version"] in {CONTEXT_V4,CONTEXT_V5}
            and store.sha(store.canonical(root_go))==handoff["current_root_go_sha256"],"EXACT_PRIVATE_ROOT_FOR_HISTORY_PLANNING")
        planning=deepcopy(planning)
        planning["known_by_at"]=result.proof["known_by_at"]
        planning["resolved_weeks"]=sorted({w["week"] for w in result.durable.document["weeks"]
            if w["season"]==planning["current"]["season"] and state.utc(w["grade_completed_at"])<state.utc(result.proof["known_by_at"])})
        validate_planning(planning)
        require(planning["epoch_sha256"]==handoff["epoch_sha256"],"ORIGINAL_PLANNING_EPOCH")
        envelope.update(schema_version=LOCATOR_VERSION+"-evidence-envelope",planning=planning,root_go=deepcopy(root_go))
    plain = store.canonical(envelope)
    require(len(plain) <= LIMITS["envelope_bytes"], "COMPLETE_HISTORY_EVIDENCE_ENVELOPE_BOUND")
    encoded = gzip.compress(plain, mtime=0)
    require(len(encoded) <= LIMITS["envelope_bytes"], "COMPLETE_HISTORY_EVIDENCE_ENVELOPE_BOUND")
    from . import audit_weekly_archive_v1 as archive
    output = archive.fresh(storage, output); storage.write_bytes(output / "ORIGINAL_GRADE_READ_EVIDENCE.json.gz", encoded)
    return cp.binding(output / "ORIGINAL_GRADE_READ_EVIDENCE.json.gz")


class VerifiedHistory:
    def __init__(self, context, registered, durable, binding, proof, key):
        require(key is _KEY, "LIVE_VERIFIED_HISTORY_REQUIRED")
        _, _, store, _, state = _modules()
        self.context, self.registered, self.durable = context, registered, durable
        self.binding, self.proof = deepcopy(binding), deepcopy(proof)
        self._sha = state.digest(dict(binding=binding, proof=proof)); self._process = store.process_identity()
    def verify(self):
        _, _, store, _, state = _modules()
        self.context.verify(); self.durable.verify()
        require(self._process == store.process_identity() and self._sha == state.digest(dict(binding=self.binding, proof=self.proof)),
            "VERIFIED_HISTORY_PROCESS_OR_BINDING_CHANGED")
        self.registered.verify(now()); return self
    def __reduce__(self): raise HistoryError("VERIFIED_HISTORY_CANNOT_BE_SERIALIZED")


def _client(context, operation, transport, routes=(), *, package=None):
    from . import audit_weekly_archive_v1 as archive, audit_weekly_operations_authority_v1 as authority
    _, _, store, _, _ = _modules()
    class ReadClient(archive.Client):
        def allow(self, url):
            if url in routes: self.allowed.add(url); return url
            return super().allow(url)
        def reserve_post(self,*args,**kwargs):raise HistoryError("HISTORY_RECOVERY_GET_ONLY")
        def reserve(self,*args,**kwargs):raise HistoryError("HISTORY_RECOVERY_GET_ONLY")
    context.verify(); base = context.client
    package = context.go["qualified_runtime"] if package is None else package
    client = ReadClient(context.env.get("GITHUB_TOKEN"), base.run_id, journal=base.journal, source_sha=base.source_sha,
        job=deepcopy(base.job), operation=operation, qualification=package["qualification"], readonly=True, transport=transport)
    client.authenticate_actions_job(); client.bind(package["binding"])
    authority.attach(client, context.proof, context.env, store.canonical(context.go))
    require(client.job["api_job_id"] == base.job["api_job_id"] and client.job["job_id"] in context.go["jobs"].values(),
        "ACTUAL_CURRENT_HISTORY_JOB_REQUIRED")
    return client


def _json(client, url, evidence):
    _, _, store, cp, _ = _modules()
    status, headers, raw = client.request(client.allow(url))
    require(status == 200 and 0 < len(raw) <= store.META_CAP and headers.get("x-ratelimit-remaining") != "0"
        and "retry-after" not in headers, "ACTUAL_HISTORY_API_BODY_REQUIRED")
    evidence[url] = store.sha(raw); return cp.strict_json(raw)


def _original(client, value, receipt, evidence, *, check_sources=True, extra_pins=None):
    grade, checkpoint, store, _, state = _modules()
    from . import audit_weekly_retained_v1 as retained, audit_weekly_controller_v1 as controller
    base = store.API + "/actions/runs/" + value["run_id"]
    run = _json(client, base, evidence); listing = _json(client, base + "/jobs?per_page=100&page=1", evidence)
    actor = run.get("actor", {}); actor_id = (actor.get("login"), actor.get("id"))
    require(run.get("id") == int(value["run_id"]) and run.get("head_sha") == value["source_sha"]
        and run.get("status") == "completed" and run.get("conclusion") == "success" and type(run.get("run_attempt")) is int and run["run_attempt"] == 1
        and run.get("event") == "workflow_dispatch" and run.get("path") == ".github/workflows/lab.yml"
        and run.get("head_branch") == value["workflow_ref"].split("@refs/heads/", 1)[1]
        and run.get("repository", {}).get("full_name") == run.get("head_repository", {}).get("full_name") == store.REPO
        and actor_id in {(a["login"], a["id"]) for a in (controller.OWNER, controller.BOT)}
        and ("triggering_actor" not in run or (run["triggering_actor"].get("login"), run["triggering_actor"].get("id")) == actor_id),
        "ORIGINAL_COMPLETED_HISTORY_DELIVERY_RUN_REQUIRED")
    require(type(listing.get("jobs")) is list and type(listing.get("total_count")) is int
        and listing["total_count"] == len(listing["jobs"]) <= 100, "COMPLETE_ORIGINAL_HISTORY_JOB_CENSUS")
    jobs = {}
    for role, ref in receipt["jobs"].items():
        matches = [j for j in listing["jobs"] if j.get("id") == ref["api_job_id"]]
        require(len(matches) == 1, "UNIQUE_ORIGINAL_HISTORY_API_JOB")
        j = matches[0]
        require(j.get("name") == ref["job_id"] and j.get("head_sha") == value["source_sha"] and j.get("run_id") == int(value["run_id"])
            and j.get("status") == "completed" and j.get("conclusion") == "success"
            and state.utc(j["started_at"]) <= state.utc(j["completed_at"]) <= now(), "SUCCESSFUL_ORIGINAL_HISTORY_THREE_JOBS_REQUIRED")
        jobs[role] = j
    p = value["grade_read_proof"]; h = value["checkpoint_handoff"]
    require(receipt["jobs"]["restore"] == {k: p["producer"][k] for k in ("job_id", "api_job_id")}
        and receipt["jobs"]["consume"] == {k: p["reader"][k] for k in ("job_id", "api_job_id")}
        and state.utc(jobs["produce"]["completed_at"]) <= state.utc(jobs["restore"]["started_at"])
        <= state.utc(h["snapshot_completed_at"]) <= state.utc(h["append_proof"]["started_at_utc"])
        <= state.utc(h["append_proof"]["completed_at_utc"]) <= state.utc(jobs["restore"]["completed_at"])
        <= state.utc(jobs["consume"]["started_at"]) <= state.utc(p["known_by_at"])
        <= state.utc(receipt["verified_at"]) <= state.utc(receipt["created_at"])
        <= state.utc(jobs["consume"]["completed_at"]), "ORIGINAL_GRADING_AND_PUBLIC_DELIVERY_CLOCKS_REQUIRED")
    if not check_sources:return jobs
    pins = dict(value["grade_code_pins"])
    for name, sha in value["checkpoint_helper_sha256"].items():
        require(name not in pins or pins[name] == sha, "ONE_ORIGINAL_HISTORY_SOURCE_HASH")
        pins[name] = sha
    pins[".github/workflows/lab.yml"] = receipt["workflow_sha256"]
    for name,sha in (extra_pins or {}).items():
        require(name not in pins or pins[name]==sha,"ONE_ORIGINAL_HISTORY_SOURCE_HASH")
        pins[name]=sha
    for name, sha in pins.items():
        source = _json(client, retained.source_url(value["source_sha"], name), evidence)
        require(source.get("type") == "file" and source.get("path") == name and source.get("encoding") == "base64"
            and type(source.get("size")) is int and 0 < source["size"] <= LIMITS["source_bytes"], "CLOSED_ORIGINAL_HISTORY_SOURCE_FILE")
        raw = base64.b64decode(source["content"].replace("\n", ""), validate=True)
        require(len(raw) == source["size"] and store.sha(raw) == sha and source.get("sha") == controller.blob_sha(raw),
            "SAME_CODE_HISTORY_SOURCE_MISMATCH_ADAPTER_REQUIRED")
        if name == ".github/workflows/lab.yml":
            retained.workflow_permissions(raw, dict(jobs={r: j["job_id"] for r, j in receipt["jobs"].items()}))
    return jobs


def _anchor(client, receipt, evidence, *, workflow_ref, expected_jobs, before, prior=None):
    """Independently authenticate the original forecast cohort before GETs."""
    from . import private_draft_store as store,state,audit_weekly_controller_v1 as controller
    base=store.API+"/actions/runs/"+receipt["run_id"]
    def read():
        run=_json(client,base,evidence);listing=_json(client,base+"/jobs?per_page=100&page=1",evidence)
        actor=run.get("actor",{});who=(actor.get("login"),actor.get("id"))
        require(run.get("id")==int(receipt["run_id"]) and run.get("head_sha")==receipt["source_sha"]
            and run.get("status")=="completed" and run.get("conclusion")=="success"
            and type(run.get("run_attempt")) is int and run["run_attempt"]==1
            and run.get("event")=="workflow_dispatch" and run.get("path")==".github/workflows/lab.yml"
            and run.get("head_branch")==workflow_ref.split("@refs/heads/",1)[1]
            and run.get("repository",{}).get("full_name")==run.get("head_repository",{}).get("full_name")==store.REPO
            and who in {(a["login"],a["id"]) for a in (controller.OWNER,controller.BOT)}
            and ("triggering_actor" not in run or (run["triggering_actor"].get("login"),run["triggering_actor"].get("id"))==who),
            "ORIGINAL_FORECAST_ANCHOR_COMPLETED_RUN_SOURCE_ACTOR_REQUIRED")
        require(type(listing) is dict and type(listing.get("jobs")) is list and type(listing.get("total_count")) is int
            and listing["total_count"]==len(listing["jobs"])<=100 and set(receipt["jobs"])==set(expected_jobs),
            "COMPLETE_ORIGINAL_FORECAST_ANCHOR_JOB_CENSUS")
        jobs={}
        for role,ref in receipt["jobs"].items():
            require(ref["job_id"]==expected_jobs[role],"ORIGINAL_FORECAST_ANCHOR_REGISTERED_WORKFLOW_JOBS")
            matches=[j for j in listing["jobs"] if j.get("id")==ref["api_job_id"]]
            require(len(matches)==1,"UNIQUE_ORIGINAL_FORECAST_ANCHOR_JOB")
            j=matches[0]
            require(j.get("name")==ref["job_id"] and j.get("run_id")==int(receipt["run_id"])
                and j.get("head_sha")==receipt["source_sha"] and j.get("status")=="completed" and j.get("conclusion")=="success"
                and state.utc(j["started_at"])<=state.utc(j["completed_at"])<=state.utc(before),
                "ORIGINAL_FORECAST_ANCHOR_JOB_SOURCE_STATUS_CLOCK")
            jobs[role]=j
        require(state.utc(jobs["produce"]["completed_at"])<=state.utc(jobs["restore"]["started_at"])
            <=state.utc(jobs["restore"]["completed_at"])<=state.utc(jobs["consume"]["started_at"])
            <=state.utc(receipt["verified_at"])<=state.utc(receipt["created_at"])
            <=state.utc(jobs["consume"]["completed_at"])<=state.utc(before),"ORIGINAL_FORECAST_ANCHOR_CAPTURE_CHAIN_CLOCKS")
        return run,jobs
    run,jobs=read()
    if prior is not None:
        controller.stable(prior[0],run)
        require(jobs==prior[1],"ORIGINAL_FORECAST_ANCHOR_CHANGED_DURING_RECOVERY")
    return run,jobs


def _registered(context, storage):
    from . import audit_weekly_operations_grade_v1 as worker
    _, _, _, cp, _ = _modules()
    inputs = context.request["inputs"]
    ref = inputs.get("retained_result") or inputs.get("archive_restored")
    require(ref is not None, "OWNED_REGISTERED_HISTORY_EPOCH_CONTEXT_REQUIRED")
    restored = cp.strict_json(_read(storage, ref, 4 << 20))
    return worker._epoch(restored, storage, now)[0]


def _native_evidence(envelope, sidecar, client, jobs, *, private_root=None):
    return validate_native_envelope(envelope,sidecar,client,jobs,version2=False,private_root=private_root)


def validate_native_envelope(envelope, sidecar, client, jobs, *, version2, private_root=None):
    """Exact original proof-body checks; no grader import or snapshot decode."""
    from . import private_draft_store as store,state
    from .weekly_durable_acceptance import restored_identity
    require(type(envelope) is dict and set(envelope) == (ENVELOPE_V2_KEYS if version2 else ENVELOPE_KEYS)
        and envelope["schema_version"] == (LOCATOR_VERSION+"-evidence-envelope" if version2 else VERSION+"-evidence-envelope")
        and envelope["handoff_sha256"] == store.sha(store.canonical(sidecar["checkpoint_handoff"]))
        and envelope["grade_read_proof"] == sidecar["grade_read_proof"] and envelope["grade_code_pins"] == sidecar["grade_code_pins"]
        and envelope["checkpoint_helper_sha256"] == sidecar["checkpoint_helper_sha256"], "EXACT_PRIVATE_HISTORY_EVIDENCE_ENVELOPE")
    body = envelope["native_read_evidence"]; p = sidecar["grade_read_proof"]; h = sidecar["checkpoint_handoff"]
    wire_version=checkpoint_version(h);multipart=wire_version==CHECKPOINT_V2
    require(type(body) is dict and set(body) == {"schema_version", "context", "native_restore_proof", "restored_binding", "known_by_at"}
        and body["schema_version"] == wire_version+"-fresh-reader-native-evidence"
        and state.digest(body) == p["proof_sha256"] and body["known_by_at"] == p["known_by_at"], "ORIGINAL_NATIVE_GRADE_READ_PROOF_BODY_REQUIRED")
    c = body["context"]
    ref=body["restored_binding"]
    require(type(c) is dict and set(c) == {"current_root_go_sha256", "handoff_sha256", "handoff", "reader", "api_evidence", "final_api_evidence"}
            | ({"multipart_readback"} if multipart else set())
        and c["current_root_go_sha256"] == h["current_root_go_sha256"] and c["handoff"] == h
        and c["handoff_sha256"] == envelope["handoff_sha256"] and c["reader"] == p["reader"]
        and type(ref) is dict and set(ref)=={"path","bytes","sha256"} and type(ref["path"]) is str
        and Path(ref["path"]).is_absolute() and ".." not in Path(ref["path"]).parts
        and ref["sha256"] == h["body_sha256"] and ref["bytes"] == h["body_bytes"],
        "ORIGINAL_GRADE_READ_NATIVE_CONTEXT_AND_BODY")
    require(all(type(c[k]) is dict and set(c[k])=={"run_sha256","jobs_sha256"}
        and all(store.HASH.fullmatch(str(v)) for v in c[k].values()) for k in ("api_evidence","final_api_evidence")),
        "ORIGINAL_GRADE_READ_API_EVIDENCE_HASHES")
    native = body["native_restore_proof"]
    from . import audit_weekly_template_v1 as template
    if type(client) is template.ParentGETClient:
        # An immutable validation scope, not a Client/Actions job or receipt
        # issuer. Keep ParentGETClient's original metadata-only ABI intact.
        # same_run=False reads only these actual binding/process/lane fields.
        from types import SimpleNamespace
        client.guard()
        scope=SimpleNamespace(binding=client.binding,process=store.process_identity(),job={"execution_lane":"github_actions"})
    else:scope=client
    store.check_proof(scope, native, "restore", same_run=False)
    require(restored_identity(native) == p["reader"] and native["payload_sha256"] == h["body_sha256"] and native["bytes"] == h["body_bytes"]
        and state.utc(jobs["consume"]["started_at"]) <= state.utc(native["started_at_utc"])
        <= state.utc(native["created_at_utc"]) <= state.utc(p["known_by_at"]), "ORIGINAL_NATIVE_HISTORY_READER_COHORT_AND_CLOCK")
    if multipart:
        root=private_checkpoint_root(private_root,h)
        validate_multipart_readback(c["multipart_readback"],h,native,p["reader"],known_by_at=p["known_by_at"],wire=root)
    else:require(private_root is None,"NO_MULTIPART_ROOT_ON_ORIGINAL_V1_EVIDENCE")


def _root_envelope(envelope, locator, jobs, *, code_pins, static_root, at):
    from . import private_draft_store as store,state,audit_weekly_template_v1 as template
    require(envelope["planning"]==locator["planning"],"PUBLIC_PLANNING_BOUND_TO_PRIVATE_READER_EVIDENCE")
    root=envelope["root_go"];cohort=locator["cohort"]
    dynamic={"approved","issued_at_utc","expires_at_utc","operation","effective_epoch"}
    require(type(root) is dict and set(root)==template.root_keys(root) and root["approved"] is True
        and root["operation"]=="RECURRING_CAPTURE" and root["source_sha"]==cohort["source_sha"]
        and root["code_pins"]==code_pins
        and store.sha(store.canonical(root))==cohort["root_go_sha256"] and root["issued_at_utc"]==cohort["root_issued_at_utc"]
        and root["effective_epoch"]["schema_version"] in {CONTEXT_V4,CONTEXT_V5},"ORIGINAL_REGISTERED_LITERAL_ROOT_PREIMAGE")
    package,_=template.checkpoint_runtime(static_root,locator['sidecar']['checkpoint_handoff'],
        anchor=locator['anchor'],checkpoint={'sha256':store.sha(store.canonical(locator))})
    prior=template.prior_runtime(static_root)
    if prior is not None and package==prior['qualified_runtime']:
        require(template.static_root_sha256(root)==prior['root_static_sha256']
            and root['qualified_runtime']==package and root['pending_census']==prior['pending_census'],
            'EXACT_SEALED_ORIGINAL_RUNTIME_ROOT_PREIMAGE')
    else:
        require(set(root)==set(static_root) and all(root[k]==static_root[k] for k in set(root)-dynamic),
            'ORIGINAL_REGISTERED_LITERAL_ROOT_PREIMAGE')
    require(state.utc(root["issued_at_utc"])<=state.utc(jobs["produce"]["started_at"])
        and state.utc(root["issued_at_utc"])<state.utc(root["expires_at_utc"])
        and (state.utc(root["expires_at_utc"])-state.utc(root["issued_at_utc"])).total_seconds()<=3600
        and state.utc(locator["sidecar"]["grade_read_proof"]["known_by_at"])<state.utc(root["expires_at_utc"])
        and state.utc(jobs["consume"]["completed_at"])<=state.utc(at),"ACTUAL_ORIGINAL_ROOT_AND_COMPLETED_JOB_CLOCKS")
    plan=validate_root_plan(root["effective_epoch"]["plan"])
    current=envelope["planning"]["current"]
    require((plan["season"],plan["week"])==(current["season"],current["week"])
        and plan["calendar_sha256"]==state.digest(current["schedule"])
        and state.utc(root["issued_at_utc"])<=state.utc(envelope["planning"]["calendar"]["retrieved_utc"])
        <=state.utc(jobs["produce"]["completed_at"]),"ORIGINAL_ROOT_FROZEN_CALENDAR_AND_ACTUAL_ACQUISITION_CLOCK")
    if cohort["kind"]=="GRADING_ONLY":
        require(root["effective_epoch"]["previous_capture"]==locator["anchor"]
            and root["effective_epoch"]["plan"]["kind"]=="GRADE_ONLY","ORIGINAL_GRADE_ONLY_ROOT_AND_CAPTURE_ANCHOR")
        locator_reference(root["effective_epoch"]["previous_checkpoint"])
    else:require(plan["kind"]=="FUTURE_CAPABLE" and state.utc(root["issued_at_utc"])<state.utc(plan["deadline_utc"]),"ORIGINAL_CAPTURE_CAPABLE_ROOT")
    template.pending_recovery(root)
    return envelope


def validate_parent_envelope(packed, locator, client, jobs, *, code_pins, static_root, at, private_root=None):
    """Fresh private metadata read, never a decoded-history/future grant."""
    from . import audit_weekly_template_v1 as template
    require(type(client) is template.ParentGETClient,"LIVE_READ_ONLY_PARENT_EVIDENCE_CLIENT")
    client.guard()
    envelope=metadata_document(packed,cap=LIMITS["envelope_bytes"])
    validate_native_envelope(envelope,locator["sidecar"],client,jobs,version2=True,private_root=private_root)
    return _root_envelope(envelope,locator,jobs,code_pins=code_pins,static_root=static_root,at=at)


def restore_previous(context, storage, sidecar_ref, prior_public_receipt_ref, *, transport=None):
    """Return a live history only after current API, old API/source and native GETs."""
    from . import audit_weekly_operations_worker_v1 as shared, audit_weekly_archive_v1 as archive
    from . import audit_weekly_operations_authority_v1 as authority, audit_weekly_discovery_v1 as discovery
    from . import audit_weekly_retained_v1 as retained
    grade, checkpoint, store, cp, state = _modules()
    require(type(context) is shared.Authenticated, "LIVE_SHARED_HISTORY_CONTEXT_REQUIRED")
    context.verify(); checkpoint.native_envelope(); began = time.monotonic()
    require(Path(context.request["cache"]) == storage.cache and Path(context.request["state_root"]) == storage.state_root,
        "EXACT_CURRENT_HISTORY_OWNED_STORAGE")
    locator = previous_checkpoint(context.go)
    require(locator is not None and set(FILES) <= set(context.go["code_pins"]), "EXPLICIT_PINNED_ROOT_HISTORY_READER_REQUIRED")
    raw = _read(storage, sidecar_ref, LIMITS["sidecar_bytes"])
    require(store.sha(raw) == locator["sha256"], "EXACT_ROOT_REGISTERED_HISTORY_SIDECAR_BYTES")
    wrapper=None
    if locator.get("schema_version")==LOCATOR_REF:
        wrapper=metadata_document(raw)
        require(type(wrapper) is dict and set(wrapper)==LOCATOR_KEYS and wrapper["schema_version"]==LOCATOR_VERSION
            and locator_filename(wrapper)==locator["path"],"EXACT_IMMUTABLE_HISTORY_LOCATOR_FILENAME")
        value=_sidecar(wrapper["sidecar"])
    else:value = _sidecar(_unpack(raw, LIMITS["metadata_plain_bytes"]))
    receipt_body = _read(storage, prior_public_receipt_ref, LIMITS["sidecar_bytes"])
    previous = context.go["effective_epoch"]["previous_capture"]
    require(store.sha(receipt_body) == previous["receipt_sha256"], "EXACT_ROOT_PRIOR_PUBLIC_RECEIPT_BYTES")
    receipt = _unpack(receipt_body, LIMITS["metadata_plain_bytes"])
    discovery.receipt(store.canonical(receipt), store.sha(store.canonical(receipt)))
    original_receipt=receipt
    if wrapper is not None:
        require(wrapper["anchor"]==previous and receipt["source_sha"]==value["source_sha"]
            and receipt["epoch_sha256"]==value["epoch_sha256"] and receipt["workflow_sha256"]==value["workflow_sha256"],
            "UNCHANGED_ORIGINAL_CAPTURE_ANCHOR")
        if wrapper["cohort"]["kind"]=="CAPTURE_AND_GRADE":
            require(all(receipt[k]==wrapper["cohort"][k] for k in
                ("source_sha","run_id","root_go_sha256","workflow_sha256","epoch_sha256","jobs")),"SAME_CAPTURE_AND_GRADING_ANCHOR_COHORT")
        else:require(receipt["run_id"]!=wrapper["cohort"]["run_id"],"DISTINCT_ORIGINAL_FORECAST_AND_LATER_GRADING_COHORT")
        receipt=wrapper["cohort"];validate_cohort(receipt)
    require(all(value[k] == receipt[k] for k in ("feed_sha256", "source_sha", "run_id", "root_go_sha256", "workflow_sha256", "epoch_sha256"))
        and value["feed_sha256"] == previous["feed_sha256"] and value["run_id"] != context.client.run_id
        and value["root_go_sha256"] != context.root_sha256, "EXACT_DIFFERENT_ROOT_RUN_PUBLIC_HISTORY_DELIVERY")
    require(value["source_sha"]==context.client.source_sha,"SOURCE_VERSION_HISTORY_ADAPTER_REQUIRED")
    from . import audit_weekly_template_v1 as template
    h = value["checkpoint_handoff"]
    package,pending=template.checkpoint_runtime(context.go,h)
    require(context.go.get('schema_version')!=template.ROOT_V3 or wrapper is not None,
        'ORIGINAL_V2_READER_ROOT_EVIDENCE_REQUIRED')
    require(h["runtime_binding_sha256"] == store.sha(store.canonical(package["binding"]))
        and h["qualified_package_sha256"] == state.digest(package)
        and h["append_proof"]["qualification_sha256"] == state.digest(package["qualification"]), "SAME_QUALIFIED_HISTORY_NAMESPACE_REQUIRED")
    pins = set(value["grade_code_pins"]) | set(value["checkpoint_helper_sha256"]) | {".github/workflows/lab.yml"}
    if wrapper is not None:pins |= LOCATOR_HELPERS
    routes = {retained.source_url(value["source_sha"], name) for name in pins}
    routes |= {store.API + "/actions/runs/" + value["run_id"] + suffix for suffix in ("", "/jobs?per_page=100&page=1")}
    if wrapper is not None:routes|={store.API+"/actions/runs/"+original_receipt["run_id"]+suffix for suffix in ("","/jobs?per_page=100&page=1")}
    metadata = _client(context, "metadata", transport, routes,package=package); evidence = {}
    run = _json(metadata, store.API + "/actions/runs/" + metadata.run_id, evidence)
    authority.authorize_client_actor(metadata, run)
    require(run.get("status") == "in_progress" and run.get("conclusion") is None and run.get("head_sha") == metadata.source_sha,
        "CURRENT_HISTORY_RUN_API_REQUIRED")
    extra={n:context.go["code_pins"][n] for n in LOCATOR_HELPERS} if wrapper is not None else None
    jobs = _original(metadata, value, receipt, evidence,extra_pins=extra)
    if wrapper is not None:
        locator_metadata(raw,receipt=original_receipt,qualified_runtime=package,code_pins=context.go["code_pins"],jobs=jobs,at=now())
    anchor_jobs=None
    if wrapper is not None and original_receipt["run_id"]!=value["run_id"]:
        anchor_jobs=_anchor(metadata,original_receipt,evidence,workflow_ref=value["workflow_ref"],expected_jobs=context.go["jobs"],
            before=wrapper["cohort"]["root_issued_at_utc"])
    require(state.utc(jobs["consume"]["completed_at"])<=state.utc(context.go["issued_at_utc"]),
        "HISTORY_COMPLETED_BEFORE_CURRENT_ROOT_AND_VALUES")
    registered = _registered(context, storage)
    require(registered.epoch.sha256 == h["epoch_sha256"], "EXACT_REGISTERED_HISTORY_EPOCH_REQUIRED")
    archive.authenticate_qualification(metadata, package, pending)
    context.verify()
    output = checkpoint.output_root(storage, Path(context.request["cache"]).parent / (context.request["phase"]+"-history"), 2*h["body_bytes"] + (1 << 20))
    archive.write(storage,output/"RESTORE_INTENT.json",dict(schema_version=VERSION+"-restore-intent",
        current_root_go_sha256=context.root_sha256,current=cp.client_identity(metadata),sidecar=sidecar_ref,
        prior_public_receipt=prior_public_receipt_ref,original_grade_read_proof=value["grade_read_proof"],
        authenticated_original_api_sha256=state.digest(evidence)))
    clients = []
    def get(descriptor, name):
        context.verify(); client = _client(context, "restore", transport,package=package); clients.append(client)
        destination = output / name
        with storage.transaction():
            storage._check(Path(client.journal) / "history-reservation-probe")
            proof = store.restore(client, descriptor, destination)
            owned = output / ("owned-" + name); storage.import_file(destination, owned, expected_sha256=descriptor["entry"]["payload"]["sha256"])
        checkpoint._own_restore(client, proof, now())
        return cp.binding(owned), proof, client
    envelope_ref, recovery_envelope, envelope_client = get(value["evidence_descriptor"], "EVIDENCE.json.gz")
    envelope = metadata_document(_read(storage, envelope_ref, LIMITS["envelope_bytes"]),cap=LIMITS["envelope_bytes"])
    multipart=checkpoint_version(h)==CHECKPOINT_V2
    if not multipart:validate_native_envelope(envelope,value,envelope_client,jobs,version2=wrapper is not None)
    snapshot_ref, recovery_snapshot, snapshot_client = get(h["descriptor"], "SNAPSHOT.json.gz")
    part_recovery=None
    if multipart:
        raw_root=_read(storage,snapshot_ref,LIMITS["snapshot_bytes"])
        validate_native_envelope(envelope,value,envelope_client,jobs,version2=wrapper is not None,private_root=raw_root)
        expected_parts=dict(handoff_sha256=state.digest(h),restored_binding=snapshot_ref,
            native_root_proof_sha256=state.digest(recovery_snapshot),reader=cp.client_identity(snapshot_client))
        admitted=[False]
        def parts_auth(request):
            context.verify()
            ok=type(request) is dict and set(request)=={"schema_version","kind","inputs","inputs_sha256","at"} \
                and request["schema_version"]==checkpoint.VERSION+"-authentication-request" \
                and request["kind"]=="CHECKPOINT_RESTORE_PRIVATE_PARTS" and request["inputs"]==expected_parts \
                and request["inputs_sha256"]==state.digest(expected_parts) and state.utc(request["at"])<=now() and not admitted[0]
            if ok:admitted[0]=True
            return ok
        part_recovery=checkpoint.restore_parts(h,snapshot_client,storage=storage,root_binding=snapshot_ref,
            native_root_proof=recovery_snapshot,authenticate=parts_auth,clock=now)
        require(admitted[0],"LIVE_CURRENT_ROOT_SOURCE_API_PART_AUTHENTICATION_REQUIRED")
        validate_multipart_readback(part_recovery,h,recovery_snapshot,cp.client_identity(snapshot_client),
            known_by_at=now(),wire=private_checkpoint_root(raw_root,h))
    if wrapper is not None:
        _root_envelope(envelope,wrapper,jobs,code_pins=context.go["code_pins"],static_root=context.go,at=now())
    snapshot_client.authenticate_actions_job()
    current_run=_json(snapshot_client,store.API+"/actions/runs/"+snapshot_client.run_id,evidence)
    authority.authorize_client_actor(snapshot_client,current_run)
    require(current_run.get("status")=="in_progress" and current_run.get("conclusion") is None
        and current_run.get("head_sha")==snapshot_client.source_sha,"CURRENT_HISTORY_JOB_CHANGED_DURING_RECOVERY")
    # Recheck the completed old cohort and same source after transfers.
    require(_original(metadata, value, receipt, evidence, check_sources=False) == jobs, "ORIGINAL_HISTORY_API_CHANGED_DURING_RECOVERY")
    if anchor_jobs is not None:
        require(_anchor(metadata,original_receipt,evidence,workflow_ref=value["workflow_ref"],expected_jobs=context.go["jobs"],
            before=wrapper["cohort"]["root_issued_at_utc"],prior=anchor_jobs)==anchor_jobs,"ORIGINAL_FORECAST_ANCHOR_CHANGED_DURING_RECOVERY")
    context.verify(); original = value["grade_read_proof"]
    expected = {"QUALIFIED_PREVIOUS_GRADING_SNAPSHOT": state.digest(dict(binding=snapshot_ref, epoch_sha256=registered.epoch.sha256)),
        "FRESH_READER_GRADING_DURABILITY": state.digest(original)}
    def authenticate(request):
        context.verify()
        return type(request) is dict and set(request) == {"schema_version", "kind", "inputs_sha256", "at"} \
            and request["schema_version"] == grade.VERSION + "-authentication-request" \
            and request.get("kind") in expected and request["inputs_sha256"] == expected[request["kind"]] \
            and state.utc(request["at"]) <= now()
    snapshot = grade.restore_snapshot(storage, snapshot_ref, registered, authenticate=authenticate, at=now())
    require(snapshot.sha256 == h["snapshot_sha256"] and snapshot.document["actual_completed_at"] == h["snapshot_completed_at"], "EXACT_ORIGINAL_HISTORY_SNAPSHOT")
    durable = grade.confirm_durable(snapshot, original, registered=registered, authenticate=authenticate, at=now())
    if wrapper is not None:
        require(all(state.utc(k["known_by_at"])<=state.utc(original["known_by_at"])
            for field in ("known_versions","known_weeks") for k in durable.document[field].values()),
            "ALL_HISTORY_KNOWN_BY_ORIGINAL_NATIVE_READER_BEFORE_CURRENT_ROOT")
    require(grade._digest(durable.document) == envelope["durable_sha256"], "LOSSLESS_ORIGINAL_DURABLE_HISTORY_REQUIRED")
    binding = grade.persist_snapshot(durable, storage=storage, output=output / "durable")
    proof = dict(schema_version=VERSION + "-recovery", current_root_go_sha256=context.root_sha256,
        current=cp.client_identity(snapshot_client), actual_recovered_at=state.utc(now()).isoformat(), original_grade_read_proof=original,
        sidecar=sidecar_ref, prior_public_receipt=prior_public_receipt_ref, native_envelope_recovery=recovery_envelope,
        native_snapshot_recovery=recovery_snapshot, original_api_evidence_sha256=state.digest(evidence))
    if part_recovery is not None:proof["native_part_recovery"]=part_recovery
    if wrapper is not None:
        planning=deepcopy(envelope["planning"])
        require(planning["resolved_weeks"]==sorted({w["week"] for w in durable.document["weeks"]
            if w["season"]==planning["current"]["season"] and state.utc(w["grade_completed_at"])<state.utc(original["known_by_at"])}),
            "EXACT_RESOLVED_WEEK_METADATA_FROM_COMPLETE_DURABLE_HISTORY")
        proof["planning"]=planning
    archive.write(storage, output / "RECOVERY.json", proof)
    require(time.monotonic()-began <= 180 and all(c.calls <= 40 for c in [metadata]+clients), "BOUNDED_NATIVE_HISTORY_RECOVERY")
    return VerifiedHistory(context, registered, durable, binding, proof, _KEY).verify()


def contract():
    return dict(schema_version=VERSION+"-contract",api="restore_previous(shared.Authenticated, storage, sidecar_ref, prior_public_receipt_ref, *, transport=None)",
        mandatory_files=list(FILES),root_context_schema=CONTEXT_V2,sidecar_schema=VERSION+"-sidecar",sidecar_keys=sorted(SIDECAR_KEYS),
        public_path="state/controller-v1/grade-checkpoints/<priorFeedSHA>.json.gz",compressed_sidecar_hash_registered_before_values=True,
        archived_context_roles=["ops_previous_checkpoint_sidecar","ops_previous_public_receipt"],
        envelope_schema=VERSION+"-evidence-envelope",envelope_keys=sorted(ENVELOPE_KEYS),
        prepare_envelope="prepare_envelope(Restored, handoff, native_evidence_ref, *, storage, output)",
        sidecar_builder="sidecar_document(receipt, handoff, grade_read_proof, evidence_descriptor, evidence_producer)",
        parent_sidecar_validator="validate_parent_sidecar(packed, *, receipt, qualified_runtime, code_pins, jobs, at) -> exact parsed dict (metadata only)",
        parent_must_append_envelope=True,sidecar_without_private_original_evidence_is_qualified=False,
        compatibility="SAME_SOURCE_SHA_AND_EXACT_UNCHANGED_GRADE_CHECKPOINT_PINS",original_known_by_is_preserved=True,
        recovery_clock_is_original_clock=False,verified_history_serializable=False,limits=LIMITS,fits=0,remote_writes=0)
