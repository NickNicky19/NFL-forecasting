"""Closed effective18 success checkpoint using existing qualified private storage.

Opaque transport is separate from all78 source recovery and SYS006 failures.
Only an authenticated fresh job plus unchanged loader replay establishes model
durability. No forecasts, raw sources, fits, publication or new store exist here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import gzip
import io
import json
import re
from pathlib import Path

from . import audit_count_requalify_v1 as audit
from . import gha_private_checkpoint as cp, owner_bootstrap_bundle as codec, private_draft_store as store
from .owned_reference_batch import validate_owned_references
from . import operational_failure_v1 as failure

VERSION = "audit-count-checkpoint-v1"
WRITER_JOB = audit.RESTORE_JOB
READER_JOB = "audit-count-effective-restore-v1"
INDEX_CAP = 256 << 10
ENTRY_CAP = 16 << 10
MAX_GROUPS = 8
COUNT_CONTROL_LABELS = tuple(name.lower().replace(".", "-") for name in (
    "restore-CONSUMED.json", "RESTORE_RECEIPT.json", "restore-RESOURCE_FINISHED.json",
    "requalify-CONSUMED.json", "REQUALIFICATION_FINISHED.json", "requalify-RESOURCE_FINISHED.json")) + tuple(
    "phase-" + name.lower().replace(".", "-") for name in (
        "restore-STATUS.json", "restore-STATUS.stderr", "requalify-STATUS.json", "requalify-STATUS.stderr"))
COUNT_FAILURE_CONTRACT = dict(schema_version="audit-count-control-failure-512k-v1",
    original_control_labels=list(COUNT_CONTROL_LABELS), original_controls_bytes=512 << 10,
    status_label="count-control-status", status_bytes=8 << 10, payload_bytes=1 << 20,
    entry_bytes=ENTRY_CAP, remote_slots=2)
COUNT_FAILURE_CONTRACT_SHA256 = store.sha(store.canonical(COUNT_FAILURE_CONTRACT))
FAILURE_RESERVE_BYTES = COUNT_FAILURE_CONTRACT["payload_bytes"] + ENTRY_CAP
FAILURE_RESERVE_SLOTS = 2
CONTROLS = ("REQUALIFICATION_FINISHED.json", "RESTORE_RECEIPT.json")
INDEX_KEYS = {"schema_version", "state", "repository", "source_policy_sha256", "source_sha", "run_id",
    "producer", "created_at", "root_go_sha256", "files", "groups", "model_pairs", "files_sha256",
    "pending_reservations", "result_sha256", "restore_receipt_sha256", "failure_contract_sha256"}
HANDOFF_KEYS = {"schema_version", "repository", "source_sha", "run_id", "runtime_binding",
    "index_descriptor", "root_go_sha256", "producer", "files_sha256"}
PAIR_KEYS = {"target", "family", "method_id", "model_logical", "manifest_logical"}
PRODUCER_KEYS = {"execution_lane", "repository", "run_id", "run_attempt", "source_sha",
    "process_identity", "job_id", "api_job_id", "permission", "workflow_ref"}
CATALOG_SLOT_KEYS = {"target", "family", "method_id", "procedure_version", "model_sha256", "manifest_sha256",
    "transport_manifest_sha256", "warm_rows", "warm_bits_identical", "fallback_rows",
    "fallback_oracle_applicable", "fallback_oracle_passed"}


def require(value, code):
    if not value:
        raise store.StoreError(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_count_failure_variant(request, status, body=None):
    """All ten controls have explicit states; full eligible bytes or bound status.

    The general SYS006 contract remains unchanged. The COUNT bridge must retain
    this closed status as an owned attachment and call this before any POST.
    """
    failure.check_request(request)
    require(type(status) is dict and set(status) == {"schema_version", "contract_sha256", "controls"}
        and status["schema_version"] == COUNT_FAILURE_CONTRACT["schema_version"] + "-status"
        and status["contract_sha256"] == COUNT_FAILURE_CONTRACT_SHA256
        and type(status["controls"]) is list and len(status["controls"]) == len(COUNT_CONTROL_LABELS),
        "CLOSED_COUNT_FAILURE_CONTROL_STATUS")
    status_body = store.canonical(status)
    require(len(status_body) <= COUNT_FAILURE_CONTRACT["status_bytes"], "COUNT_FAILURE_STATUS_CAP")
    attachments = {item["label"]: item["reference"] for item in request["attachments"]}
    require(len(attachments) == len(request["attachments"]), "NO_DUPLICATE_COUNT_CONTROL_ATTACHMENTS")
    attached, total = set(), 0
    for record, expected in zip(status["controls"], COUNT_CONTROL_LABELS):
        require(type(record) is dict and set(record) == {"label", "state", "bytes", "sha256"}
            and record["label"] == expected and record["state"] in {"ATTACHED", "ABSENT", "UNOWNED", "EMPTY", "BOUND_EXCEEDED"},
            "EXPLICIT_FIXED_COUNT_CONTROL_STATUS")
        if record["state"] == "ATTACHED":
            require(type(record["bytes"]) is int and 0 < record["bytes"] <= COUNT_FAILURE_CONTRACT["original_controls_bytes"]
                and record["label"] in attachments and store.HASH.fullmatch(record["sha256"])
                and (attachments[expected]["bytes"], attachments[expected]["sha256"]) == (record["bytes"], record["sha256"]),
                "FULL_COUNT_CONTROL_ATTACHMENT_REQUIRED")
            total += record["bytes"]
            attached.add(expected)
        else:
            require(expected not in attachments, "COUNT_CONTROL_STATUS_ATTACHMENT_CONFLICT")
            if record["state"] == "ABSENT":
                require(record["bytes"] is None and record["sha256"] is None, "EXPLICIT_ABSENT_COUNT_CONTROL")
            elif record["state"] == "EMPTY":
                require(record["bytes"] == 0 and record["sha256"] == store.sha(b""), "EXPLICIT_EMPTY_COUNT_CONTROL")
            else:
                require((record["bytes"] is None or type(record["bytes"]) is int and record["bytes"] >= 0)
                    and (record["sha256"] is None or type(record["sha256"]) is str and store.HASH.fullmatch(record["sha256"])),
                    "EXPLICIT_UNAVAILABLE_COUNT_CONTROL")
                if record["state"] == "BOUND_EXCEEDED":
                    require(type(record["bytes"]) is int and record["bytes"] > 0, "OBSERVED_BOUND_COUNT_CONTROL_SIZE_REQUIRED")
    require(total <= COUNT_FAILURE_CONTRACT["original_controls_bytes"], "COUNT_COMPLETE_CONTROL_BYTES_CAP")
    status_label = COUNT_FAILURE_CONTRACT["status_label"]
    require(set(attachments) == attached | {status_label}
        and (attachments[status_label]["bytes"], attachments[status_label]["sha256"])
        == (len(status_body), store.sha(status_body)), "OWNED_COUNT_CONTROL_STATUS_ATTACHMENT_REQUIRED")
    if body is not None:
        require(type(body) is bytes and 0 < len(body) <= COUNT_FAILURE_CONTRACT["payload_bytes"], "COUNT_FAILURE_ENCODED_PAYLOAD_CAP")
        unpacked, values = failure.unpack(body)
        require(store.canonical(unpacked) == store.canonical(request), "EXACT_COUNT_FAILURE_PACKAGED_REQUEST")
        by_label = dict(zip((a["label"] for a in request["attachments"]), values))
        require(by_label[status_label] == status_body, "EXACT_COUNT_FAILURE_PACKAGED_STATUS")
    return dict(contract_sha256=COUNT_FAILURE_CONTRACT_SHA256, attached_controls=len(attached),
        original_control_bytes=total, status_bytes=len(status_body), payload_cap_bytes=COUNT_FAILURE_CONTRACT["payload_bytes"])


def scope():
    result = {"control/" + name: "control" for name in CONTROLS}
    for target, family, _ in cp.JOBS:
        prefix = f"models/{target}/{family}"
        result[prefix + "/trained.joblib"] = "model"
        result[prefix + "/future-inference.json"] = "model_manifest"
    require(len(result) == 38, "CLOSED38_SUCCESS_SCOPE")
    return result


def pairs():
    return [dict(target=t, family=f, method_id=m, model_logical=f"models/{t}/{f}/trained.joblib",
                 manifest_logical=f"models/{t}/{f}/future-inference.json") for t, f, m in cp.JOBS]


def check_files(files):
    codec.validate_files(files)
    expected = scope()
    require(len(files) == len(expected) and {f["logical_path"] for f in files} == set(expected), "EXACT_EFFECTIVE38_FILES")
    require(all(f["required"] and f["kind"] == expected[f["logical_path"]]
                and f["origin"]["source_policy_sha256"] == cp.POLICY_SHA for f in files), "CLOSED_EFFECTIVE_FILE_KINDS")


def collect(result_ref, restore_ref, storage, *, source_sha, run_id):
    """Read approved metadata only; trained bodies remain opaque."""
    validate_owned_references(storage, {r["path"]: r["sha256"] for r in (result_ref, restore_ref)})
    result = cp.strict_json(cp.read_ref(result_ref))
    restored = cp.strict_json(cp.read_ref(restore_ref))
    require(result["schema_version"] == audit.VERSION + "-result"
            and result["state"] == "ZERO_FIT_REQUALIFIED_PRIVATE_PENDING_INTEGRATION"
            and result["model_pairs"] == len(result["artifacts"]) == 18 and result["fits"] == 0
            and result["current_source_sha"] == restored["current_source_sha"] == source_sha
            and result["current_run_id"] == restored["current_run_id"] == run_id
            and result["original_models_preserved"] is True and result["remote_writes"] == 0
            and result["protected_outcome_reads"] == 0 and result["scientific_qualification"] is False
            and restored["schema_version"] == audit.VERSION + "-restore"
            and restored["state"] == "QUALIFIED_ROUTE_RESTORED_OPAQUE"
            and restored["fits"] == restored["model_decodes"] == 0, "SUCCESSFUL_REQUALIFIED18_REQUIRED")
    files = [cp.file_item(result_ref, "control/" + CONTROLS[0], "control"),
             cp.file_item(restore_ref, "control/" + CONTROLS[1], "control")]
    for artifact, expected in zip(result["artifacts"], cp.JOBS):
        require((artifact["target"], artifact["family"], artifact["method_id"]) == expected
                and artifact["fits"] == 0 and artifact["current_loader_replay_passed"] is True, "EXACT18_EFFECTIVE_SLOTS")
        ref = artifact["manifest"]
        validate_owned_references(storage, {ref["path"]: ref["sha256"]})
        m = cp.strict_json(cp.read_ref(ref, 256 << 10))
        require((m["category"]["target"], m["family"], m["method_id"]) == expected and not m["dependencies"]
                and m["source_contract"]["source_policy_sha256"] == cp.POLICY_SHA
                and m["requalification"]["schema_version"] == audit.VERSION + "-effective-manifest"
                and m["requalification"]["fits"] == 0 and m["requalification"]["parameters_retrained"] is False
                and m["requalification"]["original_replay_preserved"] is True
                and m["requalification"]["restore_receipt"] == restore_ref, "AUTHENTIC_EFFECTIVE_MANIFEST_REQUIRED")
        prefix = f"models/{expected[0]}/{expected[1]}"
        files += [cp.file_item(m["model"], prefix + "/trained.joblib", "model"),
                  cp.file_item(ref, prefix + "/future-inference.json", "model_manifest")]
    check_files(files)
    validate_owned_references(storage, {r["path"]: r["sha256"] for r in files})
    return files


def checked_client(client, label):
    client.authenticate_actions_job()
    require(client.job["execution_lane"] == "github_actions" and client.job["run_authenticated"] is True
            and client.job["job_id"] == label and client.job["permission"] == "write", "GENUINE_EFFECTIVE_CHECKPOINT_JOB")
    return cp.client_identity(client)


def safe_handoff(document):
    require(type(document) is dict and set(document) == HANDOFF_KEYS
            and document["schema_version"] == VERSION + "-handoff"
            and document["repository"] == store.REPO, "CLOSED_SUCCESS_HANDOFF")
    store.checked_binding(document["runtime_binding"])
    descriptor = cp.descriptor_meta(document["index_descriptor"], INDEX_CAP)
    producer = document["producer"]
    require(set(producer) == PRODUCER_KEYS and re.fullmatch(r"[a-f0-9]{40}", document["source_sha"])
            and re.fullmatch(r"[1-9][0-9]{0,19}", document["run_id"])
            and type(producer["api_job_id"]) is int and producer["api_job_id"] > 0
            and re.fullmatch(re.escape(store.REPO) + r"/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+", producer["workflow_ref"])
            and producer["run_id"] == document["run_id"] == descriptor["writer_run_id"]
            and producer["source_sha"] == document["source_sha"] and producer["job_id"] == WRITER_JOB
            and producer["process_identity"] == descriptor["producer_process"]
            and producer["repository"] == store.REPO and producer["execution_lane"] == "github_actions"
            and producer["run_attempt"] == 1 and producer["permission"] == "write"
            and store.HASH.fullmatch(document["root_go_sha256"])
            and store.HASH.fullmatch(document["files_sha256"])
            and descriptor["binding_sha256"] == store.sha(store.canonical(document["runtime_binding"])), "SUCCESS_HANDOFF_ORIGIN")
    body = store.canonical(document)
    require(len(body) <= 16384 and not any(x in body for x in
        (b"https://", b"/workspace/", b"/home/", b"/tmp/", b"ghs_", b"content_b64", b"float64_hex")), "DESCRIPTOR_ONLY_SAFE_HANDOFF")
    return body


def safe_replay_catalog(document):
    """Explicit public-safe audit metadata, independently closed from private index."""
    require(set(document) == {"schema_version", "repository", "source_sha", "run_id", "slots", "fits",
        "model_pairs", "scientific_qualification", "public_release"}
        and document["schema_version"] == VERSION + "-replay-catalog" and document["repository"] == store.REPO
        and re.fullmatch(r"[a-f0-9]{40}", document["source_sha"])
        and re.fullmatch(r"[1-9][0-9]{0,19}", document["run_id"])
        and len(document["slots"]) == document["model_pairs"] == 18 and document["fits"] == 0
        and document["scientific_qualification"] is False and document["public_release"] is False,
        "CLOSED_PUBLIC_SAFE_REPLAY_CATALOG")
    for slot, expected in zip(document["slots"], cp.JOBS):
        count = expected[1] == "count_A"
        require(set(slot) == CATALOG_SLOT_KEYS and (slot["target"], slot["family"], slot["method_id"]) == expected
            and all(type(slot[k]) is str and store.HASH.fullmatch(slot[k]) for k in
                    ("procedure_version", "model_sha256", "manifest_sha256", "transport_manifest_sha256"))
            and all(type(slot[k]) is int and 0 <= slot[k] <= 10000 for k in ("warm_rows", "fallback_rows"))
            and slot["warm_bits_identical"] is True and slot["fallback_oracle_applicable"] is count
            and (slot["fallback_oracle_passed"] is True if count else slot["fallback_oracle_passed"] is None),
            "CLOSED_PUBLIC_SAFE_REPLAY_SLOT")
    body = store.canonical(document)
    require(len(body) <= 16384, "BOUNDED_PUBLIC_SAFE_REPLAY_CATALOG")
    return body


def produce(files, factory, qualification, *, storage, output, root_go_sha256, pending):
    """Preencode every group and preview index, admit quota+failure, then POST once."""
    check_files(files)
    validate_owned_references(storage, {f["path"]: f["sha256"] for f in files})
    output = store.parents_safe(output)
    require(not output.exists(), "FRESH_EFFECTIVE_APPEND_NO_RETRY")
    storage.register_root(output)
    first = factory("append")
    producer = checked_client(first, WRITER_JOB)
    require(store.HASH.fullmatch(root_go_sha256), "EXACT_PARENT_ROOT_GO_HASH")
    with storage.transaction():
        storage._require(64 << 10)
        cp.seed_pending(first.journal, pending)
        storage.write_bytes(output / "APPEND_CONSUMED.json", store.canonical(dict(root_go_sha256=root_go_sha256, producer=producer, fits=0)))
    store.check_proof(first, qualification, "qualified", same_run=False)
    first.draft()
    assets, total = first.inventory()
    prepared = []
    members_list = codec.groups(files)
    require(0 < len(members_list) <= MAX_GROUPS, "EFFECTIVE_GROUPS_CAP")
    for n, members in enumerate(members_list):
        body, inflated = codec.encode(members)
        prepared.append((dict(index=n, bytes=len(body), sha256=store.sha(body), inflated_bytes=inflated, files=members), body))
    existing = {a["name"] for a in assets}
    require(all("blob-" + record["sha256"] + ".bin" not in existing for record, _ in prepared), "EXISTING_EFFECTIVE_PAYLOAD_NO_RETRY")
    files_sha = store.sha(store.canonical(files))
    controls = {f["logical_path"]: f["sha256"] for f in files}
    def index(groups, stamp):
        return dict(schema_version=VERSION + "-index", state="COMPLETE_EFFECTIVE18_SUBSET", repository=store.REPO,
            source_policy_sha256=cp.POLICY_SHA, source_sha=first.source_sha, run_id=first.run_id,
            producer=producer, created_at=stamp, root_go_sha256=root_go_sha256, files=files,
            groups=groups, model_pairs=pairs(), files_sha256=files_sha, pending_reservations=pending,
            failure_contract_sha256=COUNT_FAILURE_CONTRACT_SHA256,
            result_sha256=controls["control/" + CONTROLS[0]], restore_receipt_sha256=controls["control/" + CONTROLS[1]])
    preview = []
    for record, body in prepared:
        entry = dict(schema_version="weekly-private-restore-manifest-v2", payload=cp.payload(body),
            payload_asset_id=10**20-1, payload_name="blob-" + record["sha256"] + ".bin",
            producer_process=first.process, binding_sha256=store.sha(store.canonical(first.binding)), writer_run_id=first.run_id)
        encoded = store.canonical(entry)
        preview.append(dict(record, descriptor=dict(entry=entry, manifest_asset_id=10**20-1,
            manifest_sha256=store.sha(encoded), manifest_bytes=len(encoded))))
    # The exact payload bodies are already frozen; index reservation uses a
    # fully encoded maximal-ID preview, leaving fixed timestamp/metadata room.
    preview_plain = store.canonical(index(preview, "9999-12-31T23:59:59.999999+00:00"))
    preview_encoded = gzip.compress(preview_plain, mtime=0)
    require(len(preview_plain) <= INDEX_CAP - 4096 and len(preview_encoded) <= INDEX_CAP, "PREENCODED_COMPLETE_INDEX_CAP")
    needed = sum(len(body) for _, body in prepared) + INDEX_CAP + (len(prepared) + 1) * ENTRY_CAP
    require(total + needed + FAILURE_RESERVE_BYTES <= store.TOTAL_CAP
            and first.inventory_slots + 2 * (len(prepared) + 1) + FAILURE_RESERVE_SLOTS <= store.MAX_ASSETS,
            "SUCCESS_AND_FAILURE_REMOTE_RESERVE_REQUIRED")
    admission = dict(existing_runtime_bytes=total, new_upper_bytes=needed, failure_reserve_bytes=FAILURE_RESERVE_BYTES,
        failure_reserve_slots=FAILURE_RESERVE_SLOTS, admitted_upper_bytes=total + needed + FAILURE_RESERVE_BYTES,
        existing_slots=first.inventory_slots, new_slots=2 * (len(prepared) + 1), runtime_cap=store.TOTAL_CAP,
        index_preview_sha256=store.sha(preview_encoded), index_reserved_bytes=INDEX_CAP,
        failure_variant=COUNT_FAILURE_CONTRACT["schema_version"], failure_contract_sha256=COUNT_FAILURE_CONTRACT_SHA256)
    storage.write_bytes(output / "INDEX_PREVIEW.json.gz", preview_encoded)
    storage.write_bytes(output / "ADMISSION.json", store.canonical(admission))
    groups = []
    def append(client, body, number):
        identity = checked_client(client, WRITER_JOB)
        require(identity == producer and client.binding == first.binding and client.journal == first.journal,
                "ONE_AUTHENTIC_EFFECTIVE_WRITER")
        storage.write_bytes(output / (f"APPEND_AUTHORIZATION_{number}.json"), store.canonical(dict(
            schema_version=VERSION + "-native-append-authorization", root_go_sha256=root_go_sha256,
            producer=producer, payload=cp.payload(body), files_sha256=files_sha, fits=0,
            computed_after_complete_preencoding=True, human_review_claim=False)))
        return store.append(client, body, cp.payload(body), qualification)
    for n, (record, body) in enumerate(prepared):
        descriptor = append(first if n == 0 else factory("append"), body, n)
        cp.descriptor_meta(descriptor, store.ASSET_CAP)
        groups.append(dict(record, descriptor=descriptor))
    plain = store.canonical(index(groups, now()))
    require(len(plain) <= INDEX_CAP - 4096, "PRIVATE_EFFECTIVE_INDEX_CAP")
    encoded = gzip.compress(plain, mtime=0)
    require(len(encoded) <= INDEX_CAP, "PRIVATE_EFFECTIVE_INDEX_CAP")
    storage.write_bytes(output / "PRIVATE_INDEX.json.gz", encoded)
    descriptor = append(factory("append"), encoded, len(groups))
    handoff = dict(schema_version=VERSION + "-handoff", repository=store.REPO, source_sha=first.source_sha,
        run_id=first.run_id, runtime_binding=first.binding, index_descriptor=descriptor,
        root_go_sha256=root_go_sha256, producer=producer, files_sha256=files_sha)
    safe_handoff(handoff)
    storage.write_bytes(output / "APPENDED.json", store.canonical(dict(schema_version=VERSION + "-append",
        state="EFFECTIVE18_APPENDED_RESTORE_REQUIRED", handoff=handoff, admission=admission, fits=0,
        public_release=False, private_durability_qualified=False)))
    return handoff


def check_index(document, handoff):
    require(type(document) is dict and set(document) == INDEX_KEYS and document["schema_version"] == VERSION + "-index"
            and document["state"] == "COMPLETE_EFFECTIVE18_SUBSET" and document["repository"] == store.REPO
            and document["source_policy_sha256"] == cp.POLICY_SHA
            and document["source_sha"] == handoff["source_sha"] and document["run_id"] == handoff["run_id"]
            and document["producer"] == handoff["producer"] and document["root_go_sha256"] == handoff["root_go_sha256"]
            and document["failure_contract_sha256"] == COUNT_FAILURE_CONTRACT_SHA256
            and document["model_pairs"] == pairs() and document["files_sha256"] == handoff["files_sha256"]
            == store.sha(store.canonical(document["files"])) and store.utc(document["created_at"]) <= datetime.now(timezone.utc),
            "CLOSED_SAME_RUN_EFFECTIVE_INDEX")
    check_files(document["files"])
    originals = {f["logical_path"]: f for f in document["files"]}
    require(document["result_sha256"] == originals["control/" + CONTROLS[0]]["sha256"]
            and document["restore_receipt_sha256"] == originals["control/" + CONTROLS[1]]["sha256"], "SUCCESS_CONTROL_HASHES")
    groups = document["groups"]
    require(type(groups) is list and 0 < len(groups) <= MAX_GROUPS, "EFFECTIVE_GROUPS_CAP")
    seen, asset_ids = set(), [handoff["index_descriptor"]["manifest_asset_id"], handoff["index_descriptor"]["entry"]["payload_asset_id"]]
    for n, group in enumerate(groups):
        require(set(group) == cp.GROUP_KEYS and group["index"] == n and 0 < group["bytes"] <= store.ASSET_CAP,
                "CLOSED_EFFECTIVE_GROUP")
        entry = cp.descriptor_meta(group["descriptor"], store.ASSET_CAP)
        require(entry["writer_run_id"] == handoff["run_id"] and entry["producer_process"] == handoff["producer"]["process_identity"]
                and entry["binding_sha256"] == store.sha(store.canonical(handoff["runtime_binding"]))
                and entry["payload"]["bytes"] == group["bytes"] and entry["payload"]["sha256"] == group["sha256"], "EXACT_EFFECTIVE_GROUP_DESCRIPTOR")
        asset_ids += [entry["payload_asset_id"], group["descriptor"]["manifest_asset_id"]]
        for item in group["files"]:
            require(item == originals.get(item["logical_path"]) and item["logical_path"] not in seen, "CLOSED_EFFECTIVE_PARTITION")
            seen.add(item["logical_path"])
    require(seen == set(originals) and len(asset_ids) == len(set(asset_ids))
            and handoff["runtime_binding"]["canary_asset_id"] not in asset_ids, "COMPLETE_EFFECTIVE_PARTITION")
    return document


def restore(handoff, factory, *, storage, output, root_go_sha256, replay=True, before_replay=None):
    """Fresh job/process, real completed writer, opaque restore, exact loader replay."""
    safe_handoff(handoff)
    require(handoff["root_go_sha256"] == root_go_sha256, "EXACT_SUCCESS_ROOT_AUTHORITY")
    output = store.parents_safe(output)
    require(not output.exists(), "FRESH_EFFECTIVE_RESTORE_NO_RETRY")
    storage.register_root(output)
    first = factory("restore")
    reader = checked_client(first, READER_JOB)
    require(reader["run_id"] == handoff["run_id"] and reader["source_sha"] == handoff["source_sha"]
            and reader["workflow_ref"] == handoff["producer"]["workflow_ref"]
            and reader["process_identity"] != handoff["producer"]["process_identity"]
            and reader["api_job_id"] != handoff["producer"]["api_job_id"], "FRESH_SAME_RUN_EFFECTIVE_READER")
    require(first.binding == handoff["runtime_binding"], "EXACT_SUCCESS_RUNTIME_BINDING")
    jobs = first.json(first.allow(first.path("/actions/runs/" + first.run_id + "/jobs?per_page=100&page=1")))
    require(type(jobs.get("jobs")) is list and jobs.get("total_count") == len(jobs["jobs"]) <= 100, "COMPLETE_EFFECTIVE_JOB_LIST")
    writers = [j for j in jobs["jobs"] if j.get("id") == handoff["producer"]["api_job_id"]]
    readers = [j for j in jobs["jobs"] if j.get("id") == reader["api_job_id"]]
    require(len(writers) == len(readers) == 1, "ACTUAL_EFFECTIVE_WRITER_READER_REQUIRED")
    writer, current = writers[0], readers[0]
    require(writer.get("name") == WRITER_JOB and writer.get("status") == "completed" and writer.get("conclusion") == "success"
            and writer.get("head_sha") == first.source_sha and writer.get("run_id") == int(first.run_id)
            and store.utc(writer["completed_at"]) <= store.utc(current["started_at"]) <= store.utc(first.started_at), "COMPLETED_SUCCESSFUL_EFFECTIVE_WRITER")
    proofs, used = [], False
    def get(descriptor, name):
        nonlocal used
        client = first if not used else factory("restore")
        used = True
        require(checked_client(client, READER_JOB) == reader and client.binding == first.binding, "ONE_AUTHENTIC_EFFECTIVE_READER")
        client.inventory()
        client.draft()  # Real controls also satisfy normal v2.1 operation minima.
        destination = output / "downloads" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        proof = store.restore(client, descriptor, destination)
        require(proof["schema_version"] == "weekly-private-proof-v2.1" and proof["job"]["job_id"] == READER_JOB
                and proof["exact_readback"] is True and proof["separate_process"] is True, "EXACT_STORE21_RESTORE_PROOF")
        # Store proof checker forbids self-process acceptance. A separate local
        # verifier identity is NOT fabricated here; its later verification is
        # exposed via verify_proofs for the parent's independent consumer.
        proofs.append(proof)
        with storage.transaction():
            storage.import_file(destination, output / "owned-downloads" / name,
                expected_sha256=descriptor["entry"]["payload"]["sha256"])
        return store.read_local(output / "owned-downloads" / name, store.ASSET_CAP)
    encoded = get(handoff["index_descriptor"], "index.gz")
    with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as stream:
        plain = stream.read(INDEX_CAP + 1)
    require(len(plain) <= INDEX_CAP, "BOUNDED_EFFECTIVE_INDEX_INFLATION")
    document = check_index(cp.strict_json(plain), handoff)
    require(store.utc(writer["started_at"]) <= store.utc(document["created_at"]) <= store.utc(writer["completed_at"]), "EFFECTIVE_INDEX_WRITER_CLOCK")
    for group in document["groups"]:
        body = get(group["descriptor"], f"group-{group['index']}.gz")
        codec.extract_owned(body, group, storage, output / "files")
    files = {f["logical_path"]: f for f in document["files"]}
    mapping = {name: dict(path=str(output / "files" / name), bytes=f["bytes"], sha256=f["sha256"]) for name, f in files.items()}
    validate_owned_references(storage, {r["path"]: r["sha256"] for r in mapping.values()})
    result_control = cp.strict_json(cp.read_ref(mapping["control/" + CONTROLS[0]]))
    route_control = cp.strict_json(cp.read_ref(mapping["control/" + CONTROLS[1]]))
    require(result_control["schema_version"] == audit.VERSION + "-result"
            and result_control["state"] == "ZERO_FIT_REQUALIFIED_PRIVATE_PENDING_INTEGRATION"
            and result_control["model_pairs"] == len(result_control["artifacts"]) == 18
            and result_control["current_source_sha"] == route_control["current_source_sha"] == first.source_sha
            and result_control["current_run_id"] == route_control["current_run_id"] == first.run_id
            and result_control["fits"] == route_control["fits"] == route_control["model_decodes"] == 0
            and route_control["schema_version"] == audit.VERSION + "-restore"
            and route_control["state"] == "QUALIFIED_ROUTE_RESTORED_OPAQUE", "RESTORED_CURRENT_SUCCESS_CONTROLS")
    refs, metadata, catalog_slots = [], [], []
    for pair, artifact in zip(pairs(), result_control["artifacts"]):
        original, model = mapping[pair["manifest_logical"]], mapping[pair["model_logical"]]
        m = cp.strict_json(cp.read_ref(original, 256 << 10))
        require((artifact["target"], artifact["family"], artifact["method_id"])
                == (m["category"]["target"], m["family"], m["method_id"]) == (pair["target"], pair["family"], pair["method_id"])
                and (artifact["manifest"]["bytes"], artifact["manifest"]["sha256"]) == (original["bytes"], original["sha256"])
                and artifact["current_loader_replay_passed"] is True and artifact["fits"] == 0
                and m["source_contract"]["source_policy_sha256"] == cp.POLICY_SHA
                and m["requalification"]["fits"] == 0
                and m["requalification"]["restore_receipt"]["sha256"] == document["restore_receipt_sha256"], "RESTORED_EFFECTIVE_MODEL_SCOPE")
        relocated = codec.relocate_future_manifest(original, model, output / "relocated-models" / pair["target"] / pair["family"], storage)
        refs.append({k: relocated[k] for k in ("path", "bytes", "sha256")})
        metadata.append((pair, m, original, model))
    require(replay is True, "FRESH_EFFECTIVE_LOADER_REPLAY_REQUIRED")
    if before_replay is not None:
        before_replay()
    import threadpoolctl
    from tools.ngboost_law_software_v1 import process_free_threads
    from .weekly_future_inference import FutureInferenceSession
    libc_path = Path("/usr/lib/x86_64-linux-gnu/libc.so.6").resolve(strict=True)
    libc = dict(path=str(libc_path), bytes=libc_path.stat().st_size,
                sha256=store.sha(store.read_local(libc_path, 8 << 20)))
    with process_free_threads(threadpoolctl, libc), threadpoolctl.threadpool_limits(limits=2):
        with FutureInferenceSession.from_storage(storage) as session:
            session.prepare(refs)
            for relocated, (pair, m, original, model_ref) in zip(refs, metadata):
                comparison = m["requalification"]["comparison"]
                count = pair["family"] == "count_A"
                if count:
                    # Code/environment/source and owned body hashes were checked
                    # by the normal loader before this feature-only replay read.
                    import joblib
                    bundle = joblib.load(io.BytesIO(cp.read_ref(model_ref)))
                    trained, fixture = bundle["model"], bundle["fixture"]
                    comparison = audit.count_replay_oracle(trained, fixture)
                    require(comparison["warm_rows"] > 0, "NONVACUOUS_FRESH_COUNT_WARM_BITS")
                    for role in list(dict.fromkeys(list(trained.priors) + list(m["category"]["modeled_roles"]) + ["audit_unknown_role"])):
                        probe = fixture.iloc[:1].copy()
                        probe["position"], probe["f_player_games_prior"] = role, 0.
                        checked = audit.count_replay_oracle(trained, probe)
                        require(checked["independent_stored_q_mean_verified"] is True, "FRESH_COUNT_FALLBACK_ORACLE")
                catalog_slots.append(dict(target=pair["target"], family=pair["family"], method_id=pair["method_id"],
                    procedure_version=m["procedure_version"], model_sha256=model_ref["sha256"], manifest_sha256=relocated["sha256"],
                    transport_manifest_sha256=original["sha256"], warm_rows=comparison["warm_rows"],
                    warm_bits_identical=comparison["warm_bits_identical"], fallback_rows=comparison["fallback_rows"],
                    fallback_oracle_applicable=count, fallback_oracle_passed=True if count else None))
    catalog = dict(schema_version=VERSION + "-replay-catalog", repository=store.REPO, source_sha=first.source_sha,
        run_id=first.run_id, slots=catalog_slots, fits=0, model_pairs=18, scientific_qualification=False, public_release=False)
    catalog_body = safe_replay_catalog(catalog)
    storage.write_bytes(output / "REPLAY_CATALOG.json", catalog_body)
    result = dict(schema_version=VERSION + "-restore", state="EFFECTIVE18_RESTORED_AND_LOADER_REPLAYED",
        handoff_sha256=store.sha(safe_handoff(handoff)), root_go_sha256=root_go_sha256,
        original_producer=handoff["producer"], reader=reader, models=refs, files=len(files), model_pairs=18,
        proofs=proofs, index_sha256=handoff["index_descriptor"]["entry"]["payload"]["sha256"],
        group_sha256=[g["sha256"] for g in document["groups"]],
        fits=0, fresh_process_replay=True, model_artifact_durability=True,
        replay_catalog=catalog, replay_catalog_sha256=store.sha(catalog_body),
        successful_forecast=False, public_release=False, scientific_qualification=False,
        private_durability_qualified=False, actual_completed_at=now())
    storage.write_bytes(output / "RESTORED.json", store.canonical(result))
    return result


def verify_proofs(client, receipt, handoff):
    """Optional third authenticated process; preserve normal v2.1 proof rules."""
    checked_client(client, client.job["job_id"])
    safe_handoff(handoff)
    require(receipt["schema_version"] == VERSION + "-restore" and receipt["handoff_sha256"] == store.sha(safe_handoff(handoff))
            and receipt["reader"]["run_id"] == client.run_id == handoff["run_id"]
            and receipt["reader"]["source_sha"] == client.source_sha == handoff["source_sha"]
            and receipt["reader"]["process_identity"] != client.process and receipt["fresh_process_replay"] is True
            and receipt["model_pairs"] == 18 and receipt["fits"] == 0
            and receipt["index_sha256"] == handoff["index_descriptor"]["entry"]["payload"]["sha256"]
            and [p["payload_sha256"] for p in receipt["proofs"]] == [receipt["index_sha256"]] + receipt["group_sha256"],
            "INDEPENDENT_EFFECTIVE_PROOF_CONSUMER")
    for proof in receipt["proofs"]:
        store.check_proof(client, proof, "restore")
    return dict(state="EFFECTIVE18_RESTORE_PROOFS_VERIFIED", fits=0, public_release=False)
