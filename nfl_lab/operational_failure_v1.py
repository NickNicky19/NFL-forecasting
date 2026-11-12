"""SYS006 failure evidence through the existing qualified private draft store.

No import-time I/O, model loading, retries, forecasts or publication. An append
is not durability: only an authenticated independent restore proves recovery.
The original failure and every clock remain immutable, even if preservation
itself fails. These records are never successful forecast checkpoints.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
import io
from pathlib import Path
import re

from . import gha_private_checkpoint as checkpoint
from . import private_draft_store as store
from .owned_reference_batch import validate_owned_references

VERSION = "weekly-operational-failure-v1"
ATTACHMENT_CAP = 1 << 20
ATTACHMENTS_CAP = 4 << 20
ATTACHMENT_COUNT = 16
METADATA_CAP = 32 << 10
PLAIN_CAP = (ATTACHMENTS_CAP * 4 + 2) // 3 + 2 * METADATA_CAP
PACKAGE_CAP = min(PLAIN_CAP, store.ASSET_CAP)
OPERATIONS = {"source", "build", "producer", "capture", "grading", "selection", "export", "checkpoint"}
KINDS = {"EXCEPTION", "INTERRUPTION", "QUOTA", "DEADLINE", "DUPLICATE", "AMBIGUOUS_POST"}
ATTACHMENT_KINDS = {"original_failure", "partial_output", "control", "post_reservation"}
ATTEMPT_KEYS = {"repository", "run_id", "run_attempt", "source_sha", "job_id", "workflow_ref"}
REQUEST_KEYS = {"schema_version", "attempt", "operation", "state", "failure", "clocks",
                "input_contract_sha256", "attachments"}
GO_KEYS = {"schema_version", "approved", "operation", "repository", "run_id", "source_sha",
           "config_sha256", "scope_manifest_sha256", "qualification_sha256", "single_writer_group",
           "runtime_id", "input_sha256", "job_id", "workflow_ref"}
NEGATIVE_GATES = dict(successful_forecast=False, scientifically_qualified=False,
                      public_export_authorized=False, website_activation=False)


def require(condition, code):
    if not condition:
        raise store.StoreError(code)


def document(body, cap=METADATA_CAP):
    require(type(body) is bytes and 0 < len(body) <= cap, "FAILURE_METADATA_CAP")
    return checkpoint.strict_json(body)


def check_attempt(attempt):
    require(type(attempt) is dict and set(attempt) == ATTEMPT_KEYS, "FAILURE_ATTEMPT_FIELDS")
    require(attempt["repository"] == store.REPO and type(attempt["run_attempt"]) is int
            and attempt["run_attempt"] == 1
            and type(attempt["run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", attempt["run_id"])
            and type(attempt["source_sha"]) is str and re.fullmatch(r"[a-f0-9]{40}", attempt["source_sha"])
            and type(attempt["job_id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", attempt["job_id"])
            and type(attempt["workflow_ref"]) is str
            and re.fullmatch(re.escape(store.REPO) + r"/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]{1,160}",
                             attempt["workflow_ref"]), "FAILURE_ATTEMPT_IDENTITY")


def check_request(request):
    require(type(request) is dict and set(request) == REQUEST_KEYS
            and request["schema_version"] == VERSION + "-request", "FAILURE_REQUEST_FIELDS")
    check_attempt(request["attempt"])
    require(request["operation"] in OPERATIONS and request["state"] in {"FAILED", "PARTIAL"}
            and type(request["input_contract_sha256"]) is str
            and store.HASH.fullmatch(request["input_contract_sha256"]), "FAILURE_ONLY_STATE_REQUIRED")
    failure = request["failure"]
    require(type(failure) is dict and set(failure) == {"kind", "code", "exit_code"}
            and failure["kind"] in KINDS and type(failure["code"]) is str
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", failure["code"])
            and (failure["exit_code"] is None or type(failure["exit_code"]) is int
                 and -127 <= failure["exit_code"] <= 255 and failure["exit_code"] != 0), "ORIGINAL_FAILURE_REQUIRED")
    clocks = request["clocks"]
    require(type(clocks) is dict and set(clocks) == {"started_at_utc", "observed_at_utc", "original"}
            and type(clocks["original"]) is dict and len(clocks["original"]) <= 64, "FAILURE_CLOCK_FIELDS")
    require(store.utc(clocks["started_at_utc"]) <= store.utc(clocks["observed_at_utc"])
            <= datetime.now(timezone.utc), "FAILURE_OBSERVATION_CLOCK")
    for name, value in clocks["original"].items():
        require(type(name) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", name), "ORIGINAL_CLOCK_NAME")
        store.utc(value)  # Validate only. Never rewrite, backdate or infer availability.
    attachments = request["attachments"]
    require(type(attachments) is list and len(attachments) <= ATTACHMENT_COUNT, "FAILURE_ATTACHMENT_COUNT")
    names, paths = set(), set()
    total = 0
    for item in attachments:
        require(type(item) is dict and set(item) == {"label", "kind", "reference"}
                and type(item["label"]) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", item["label"])
                and item["label"] not in names and item["kind"] in ATTACHMENT_KINDS, "FAILURE_ATTACHMENT_FIELDS")
        names.add(item["label"])
        ref = item["reference"]
        require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
                and type(ref["path"]) is str and len(ref["path"]) <= 1024
                and Path(ref["path"]).is_absolute() and ".." not in Path(ref["path"]).parts
                and ref["path"] not in paths
                and type(ref["bytes"]) is int and 0 <= ref["bytes"] <= ATTACHMENT_CAP
                and type(ref["sha256"]) is str and store.HASH.fullmatch(ref["sha256"]), "FAILURE_ATTACHMENT_BOUND")
        total += ref["bytes"]
        paths.add(ref["path"])
    require(total <= ATTACHMENTS_CAP and len(store.canonical(request)) <= METADATA_CAP, "FAILURE_TOTAL_ATTACHMENT_CAP")
    return request


def payload_manifest(body):
    manifest = dict(schema_version="weekly-private-payload-v2", payload_kind="runtime_manifest", format="gzip",
                    bytes=len(body), sha256=store.sha(body), source_policy_sha256=checkpoint.POLICY_SHA)
    return store.payload_manifest(manifest, body)


def unpack(body):
    """Bound inflation and base64; return invented/real attachment bytes opaque."""
    require(type(body) is bytes and 0 < len(body) <= PACKAGE_CAP, "FAILURE_PACKAGE_CAP")
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
        plain = compressed.read(PLAIN_CAP + 1)
    doc = document(plain, PLAIN_CAP)
    require(type(doc) is dict and set(doc) == {"schema_version", "classification", "request", "attachments", "gates"}
            and doc["schema_version"] == VERSION + "-envelope" and doc["classification"] == "FAILURE_EVIDENCE_ONLY"
            and store.canonical(doc["gates"]) == store.canonical(NEGATIVE_GATES)
            and plain == store.canonical(doc), "CLOSED_FAILURE_ENVELOPE")
    request = check_request(doc["request"])
    require(type(doc["attachments"]) is list and len(doc["attachments"]) == len(request["attachments"]),
            "FAILURE_ATTACHMENT_CENSUS")
    decoded = []
    for item, original in zip(doc["attachments"], request["attachments"]):
        require(type(item) is dict and set(item) == {"label", "base64"} and item["label"] == original["label"]
                and type(item["base64"]) is str
                and len(item["base64"]) == 4 * ((original["reference"]["bytes"] + 2) // 3), "OPAQUE_ATTACHMENT_ENCODING")
        value = base64.b64decode(item["base64"], validate=True)
        require(base64.b64encode(value).decode("ascii") == item["base64"]
                and len(value) == original["reference"]["bytes"]
                and store.sha(value) == original["reference"]["sha256"], "OPAQUE_ATTACHMENT_HASH")
        decoded.append(value)
    return request, decoded


def safe_status(state, original_state=None, *, HTTP_calls=0):
    require(state in {"LOCAL_FAILURE_RECORDED", "PRIVATE_APPEND_RESTORE_REQUIRED", "PRIVATE_FAILURE_RESTORED",
                      "PRIVATE_APPEND_FAILED_LOCAL_RETAINED", "FAILURE_PRESERVATION_BLOCKED"}, "FAILURE_STATUS")
    require(original_state in {None, "FAILED", "PARTIAL"}, "FAILURE_ONLY_STATE_REQUIRED")
    require(type(HTTP_calls) is int and 0 <= HTTP_calls <= store.MAX_CALLS, "FAILURE_HTTP_CAP")
    return dict(schema_version=VERSION + "-status", state=state, original_state=original_state,
                failure_evidence_durable=state == "PRIVATE_FAILURE_RESTORED", HTTP_calls=HTTP_calls,
                automatic_retries=0, public_payload_bytes=0, model_decodes=0, **NEGATIVE_GATES)


def record_failure(request, storage, output):
    """Seal once. A quota/hash interruption leaves ATTEMPT.json and old bytes."""
    check_request(request)
    output = store.parents_safe(output)
    with storage.transaction():
        require(not output.exists(), "FAILURE_ATTEMPT_ALREADY_RECORDED_NO_RETRY")
        storage.register_root(output)
        storage.write_bytes(output / "ATTEMPT.json", store.canonical(request))
        # Authenticate original CAS references before reading any attachment.
        refs = {i["reference"]["path"]: i["reference"]["sha256"] for i in request["attachments"]}
        if refs:
            validate_owned_references(storage, refs)
        bodies = []
        for item in request["attachments"]:
            ref = item["reference"]
            value = store.read_local(ref["path"], ATTACHMENT_CAP)
            require(len(value) == ref["bytes"] and store.sha(value) == ref["sha256"], "OPAQUE_ATTACHMENT_HASH")
            bodies.append(dict(label=item["label"], base64=base64.b64encode(value).decode("ascii")))
        envelope = dict(schema_version=VERSION + "-envelope", classification="FAILURE_EVIDENCE_ONLY",
                        request=request, attachments=bodies, gates=NEGATIVE_GATES)
        plain = store.canonical(envelope)
        require(len(plain) <= PLAIN_CAP, "FAILURE_PACKAGE_CAP")
        body = gzip.compress(plain, mtime=0)
        require(len(body) <= PACKAGE_CAP, "FAILURE_PACKAGE_CAP")
        manifest = payload_manifest(body)
        # Admit the entire local seal before its first write; never truncate.
        status = safe_status("LOCAL_FAILURE_RECORDED", request["state"])
        storage._require(len(body) + len(store.canonical(manifest)) + len(store.canonical(status)))
        storage.write_bytes(output / "FAILURE.json.gz", body)
        storage.write_bytes(output / "PAYLOAD.json", store.canonical(manifest))
        storage.write_bytes(output / "LOCAL.json", store.canonical(status))
    return status


def authorize(client, authorization, authorization_sha256, operation, inputs):
    """Unchanged weekly-private-operation-GO-v2.1 shape and physical input pins."""
    require(store.sha(authorization) == authorization_sha256, "GO_HASH")
    go = document(authorization)
    expected_inputs = {"binding", "payload_manifest", "qualification"} if operation == "append" else {"binding", "descriptor"}
    require(type(go) is dict and set(go) == GO_KEYS and go["schema_version"] == "weekly-private-operation-GO-v2.1"
            and go["approved"] is True and go["operation"] == operation == client.operation
            and go["repository"] == store.REPO and go["config_sha256"] == store.config_sha()
            and go["single_writer_group"] == "nfl-lab-single-writer"
            and go["run_id"] == client.run_id and go["source_sha"] == client.source_sha
            and go["job_id"] == client.job["job_id"] and go["workflow_ref"] == client.job["workflow_ref"]
            and client.job["workflow_sha"] == client.source_sha and client.job["execution_lane"] == "github_actions"
            and client.job["permission"] == "write" and client.job["event_name"] == "workflow_dispatch",
            "OPERATION_GO_OR_JOB_IDENTITY")
    require(type(inputs) is dict and set(inputs) == expected_inputs and type(go["input_sha256"]) is dict
            and set(go["input_sha256"]) == expected_inputs
            and all(store.sha(body) == go["input_sha256"][key] for key, body in inputs.items()), "PHASE_INPUT_HASH")
    parsed = {key: document(body, store.META_CAP) for key, body in inputs.items()}
    require(parsed["binding"]["runtime_id"] == go["runtime_id"], "RUNTIME_GO_MISMATCH")
    store.checked_binding(parsed["binding"])
    if operation == "append":
        require(go["scope_manifest_sha256"] == store.sha(store.canonical(parsed["payload_manifest"]))
                and go["qualification_sha256"] == store.sha(store.canonical(parsed["qualification"])), "PAYLOAD_AUTHORIZATION")
    else:
        require(go["scope_manifest_sha256"] is None and go["qualification_sha256"] is None, "EXACT_INPUT_PINS_REQUIRED")
    return parsed


def append_failure(client, storage, output, *, authorization, authorization_sha256, inputs):
    parsed = authorize(client, authorization, authorization_sha256, "append", inputs)
    output = store.parents_safe(output)
    with storage.transaction():
        require(not (output / "APPEND_INTENT.json").exists(), "FAILURE_APPEND_ALREADY_RESERVED_NO_RETRY")
        # Intent precedes even authentication GETs. Original command is never rerun.
        storage.write_bytes(output / "APPEND_INTENT.json", store.canonical(dict(
            schema_version=VERSION + "-append-intent", authorization_sha256=authorization_sha256,
            payload_sha256=parsed["payload_manifest"]["sha256"], automatic_retries=0)))
        request = None
        try:
            client.authenticate_actions_job()
            client.bind(parsed["binding"])
            store.check_proof(client, parsed["qualification"], "qualified", same_run=False)
            storage.validate_reference(output / "FAILURE.json.gz", parsed["payload_manifest"]["sha256"])
            body = store.read_local(output / "FAILURE.json.gz", PACKAGE_CAP)
            require(payload_manifest(body) == parsed["payload_manifest"], "FAILURE_PAYLOAD_SCOPE")
            request, _ = unpack(body)
            expected = dict(repository=store.REPO, run_id=client.run_id, run_attempt=1, source_sha=client.source_sha,
                            job_id=client.job["job_id"], workflow_ref=client.job["workflow_ref"])
            require(request["attempt"] == expected, "ACTUAL_FAILED_ATTEMPT_IDENTITY")
            storage.validate_reference(output / "ATTEMPT.json", store.sha(store.canonical(request)))
            client.draft()
            assets, total = client.inventory()  # Charge unknown, orphan and pending assets.
            require(not any(a["name"] == "blob-" + store.sha(body) + ".bin" for a in assets),
                    "FAILURE_REMOTE_ATTEMPT_ALREADY_PRESENT_NO_RETRY")
            require(total + len(body) + checkpoint.ENTRY_CAP <= store.TOTAL_CAP
                    and client.inventory_slots + 2 <= store.MAX_ASSETS, "FAILURE_COMPLETE_APPEND_REMOTE_CAP")
            # The two existing POST reservations and receipt also consume quota.
            storage._require(2 * checkpoint.ENTRY_CAP + METADATA_CAP)
            descriptor = store.append(client, body, parsed["payload_manifest"], parsed["qualification"])
            checkpoint.descriptor_meta(descriptor, PACKAGE_CAP)
            result = dict(schema_version=VERSION + "-append", descriptor=descriptor,
                          attempt=request["attempt"], request_sha256=store.sha(store.canonical(request)),
                          status=safe_status("PRIVATE_APPEND_RESTORE_REQUIRED", request["state"], HTTP_calls=client.calls))
            storage.write_bytes(output / "APPENDED.json", store.canonical(result))
            return result
        except BaseException:
            # No exception text/URLs/bodies are emitted and no recovery POST occurs.
            try:
                storage.write_bytes(output / "APPEND_FAILED.json", store.canonical(safe_status(
                    "PRIVATE_APPEND_FAILED_LOCAL_RETAINED", request["state"] if request else None, HTTP_calls=client.calls)))
            except Exception:
                pass  # Original failure, original intent and POST journal remain.
            raise


def restore_failure(client, storage, output, *, authorization, authorization_sha256, inputs):
    parsed = authorize(client, authorization, authorization_sha256, "restore", inputs)
    descriptor = parsed["descriptor"]
    entry = checkpoint.descriptor_meta(descriptor, PACKAGE_CAP)
    output = store.parents_safe(output)
    with storage.transaction():
        require(not output.exists(), "FAILURE_RESTORE_ALREADY_ATTEMPTED_NO_RETRY")
        storage.register_root(output)
        storage.write_bytes(output / "RESTORE_INTENT.json", store.canonical(dict(
            schema_version=VERSION + "-restore-intent", authorization_sha256=authorization_sha256, automatic_retries=0)))
        client.authenticate_actions_job()
        client.bind(parsed["binding"])
        # Direct store restore bytes and CAS copies both count. All failures stay.
        storage._require(2 * entry["payload"]["bytes"] + ATTACHMENTS_CAP + METADATA_CAP)
        proof = store.restore(client, descriptor, output / "TRANSPORT.json.gz")
        body = store.read_local(output / "TRANSPORT.json.gz", PACKAGE_CAP)
        request, attachments = unpack(body)
        a = request["attempt"]
        require(a["run_id"] == entry["writer_run_id"] == client.run_id and a["source_sha"] == client.source_sha
                and a["workflow_ref"] == client.job["workflow_ref"] and a["job_id"] != client.job["job_id"],
                "SAME_RUN_INDEPENDENT_FAILURE_RESTORE_REQUIRED")
        # Actual completed producer, including a failed job, precedes this reader.
        jobs = client.json(client.allow(client.path("/actions/runs/" + client.run_id + "/jobs?per_page=100&page=1")))
        require(type(jobs) is dict and type(jobs.get("jobs")) is list
                and jobs.get("total_count") == len(jobs["jobs"]) <= 100, "COMPLETE_FAILURE_PRODUCER_JOB_LIST")
        matches = [j for j in jobs["jobs"] if j.get("name") == a["job_id"] and j.get("run_id") == int(client.run_id)
                   and j.get("head_sha") == client.source_sha]
        require(len(matches) == 1, "ACTUAL_FAILURE_PRODUCER_REQUIRED")
        producer = matches[0]
        require(type(producer.get("id")) is int and producer["id"] > 0 and producer["id"] != client.job["api_job_id"]
                and producer.get("status") == "completed" and producer.get("conclusion") in {"failure", "cancelled", "timed_out", "success"}
                and store.utc(producer["started_at"]) <= store.utc(request["clocks"]["started_at_utc"])
                <= store.utc(request["clocks"]["observed_at_utc"]) <= store.utc(producer["completed_at"])
                <= store.utc(client.started_at), "ACTUAL_FAILURE_PRODUCER_CLOCK_OR_JOB")
        storage.write_bytes(output / "FAILURE.json.gz", body)
        files = []
        for index, value in enumerate(attachments):
            path = output / f"attachment-{index:02}.bin"  # Never extract to supplied paths.
            storage.write_bytes(path, value)
            files.append(dict(label=request["attachments"][index]["label"], path=str(path),
                              bytes=len(value), sha256=store.sha(value)))
        result = dict(schema_version=VERSION + "-restore", attempt=a, request_sha256=store.sha(store.canonical(request)),
                      package_sha256=store.sha(body), producer_api_job_id=producer["id"], proof=proof, attachments=files,
                      status=safe_status("PRIVATE_FAILURE_RESTORED", request["state"], HTTP_calls=client.calls))
        storage.write_bytes(output / "RESTORED.json", store.canonical(result))
        return result


def verify_restore(client, receipt, descriptor, package):
    """A third authenticated process can consume the existing v2.1 proof."""
    require(type(receipt) is dict and set(receipt) == {"schema_version", "attempt", "request_sha256", "package_sha256",
            "producer_api_job_id", "proof", "attachments", "status"}
            and receipt["schema_version"] == VERSION + "-restore", "CLOSED_FAILURE_RESTORE_RECEIPT")
    check_attempt(receipt["attempt"])
    require(client.job["execution_lane"] == "github_actions" and client.job["run_authenticated"] is True
            and receipt["attempt"]["run_id"] == client.run_id and receipt["attempt"]["source_sha"] == client.source_sha,
            "AUTHENTICATED_FAILURE_VERIFIER_REQUIRED")
    entry = checkpoint.descriptor_meta(descriptor, PACKAGE_CAP)
    request, attachments = unpack(package)
    status = receipt["status"]
    require(status == safe_status("PRIVATE_FAILURE_RESTORED", status["original_state"], HTTP_calls=status["HTTP_calls"])
            and receipt["attempt"] == request["attempt"] and status["original_state"] == request["state"]
            and receipt["request_sha256"] == store.sha(store.canonical(request))
            and receipt["package_sha256"] == store.sha(package) == entry["payload"]["sha256"] == receipt["proof"]["payload_sha256"]
            and receipt["proof"]["bytes"] == entry["payload"]["bytes"] == len(package)
            and entry["binding_sha256"] == store.sha(store.canonical(client.binding))
            and entry["writer_run_id"] == receipt["attempt"]["run_id"]
            and receipt["proof"]["process_identity"] != entry["producer_process"]
            and receipt["proof"]["job"]["job_id"] != receipt["attempt"]["job_id"]
            and type(receipt["producer_api_job_id"]) is int and receipt["producer_api_job_id"] > 0
            and receipt["producer_api_job_id"] != receipt["proof"]["job"]["api_job_id"]
            and len(receipt["attachments"]) == len(attachments), "FAILURE_RESTORE_RECEIPT_BINDING")
    for ref, original, value in zip(receipt["attachments"], request["attachments"], attachments):
        require(type(ref) is dict and set(ref) == {"label", "path", "bytes", "sha256"}
                and ref["label"] == original["label"] and ref["bytes"] == len(value)
                and ref["sha256"] == store.sha(value), "FAILURE_RESTORE_ATTACHMENT_BINDING")
    store.check_proof(client, receipt["proof"], "restore")
    return dict(status)
