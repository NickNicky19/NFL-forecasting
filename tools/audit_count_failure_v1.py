"""Bounded SYS006 bridge for the genuine audit-count existing-workflow mode.

The original hosted command is never called here. Its failed step remains
failed even when evidence recovery succeeds. Only the owner-sealed helper
scope can derive the exact existing private-operation GO after packaging.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab import audit_count_requalify_v1 as audit
from nfl_lab import audit_count_checkpoint_v1 as count_checkpoint
from nfl_lab import gha_private_checkpoint as checkpoint, operational_failure_v1 as failure, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_count_hosted_v1 as hosted
from tools.private_draft_store_v2 import actions_context, limits

VERSION = "audit-count-failure-v1"
HANDOFF_CAP = 16 << 10
CONTROLS = ("restore-CONSUMED.json", "RESTORE_RECEIPT.json", "restore-RESOURCE_FINISHED.json",
            "requalify-CONSUMED.json", "REQUALIFICATION_FINISHED.json", "requalify-RESOURCE_FINISHED.json")
PROGRESS_CONTROLS = {"RESTORE_RECEIPT.json", "REQUALIFICATION_FINISHED.json", "requalify-RESOURCE_FINISHED.json"}
PHASE_CONTROLS = ("restore-STATUS.json", "restore-STATUS.stderr", "requalify-STATUS.json", "requalify-STATUS.stderr")
HANDOFF_KEYS = {"schema_version", "repository", "run_id", "source_sha", "root_go_sha256", "binding_sha256",
                "request_sha256", "descriptor", "pending_reservations", "failure_contract_sha256"}
WRITER_STEP = "Restore original artifacts and requalify without fitting"
CHECKPOINT_STEP = "Preserve complete effective artifacts in the qualified private runtime"
# Single contract owned by the success-checkpoint agent; its source is already
# in checked_root's closed helper pins. General SYS006 limits stay unchanged.
COUNT_FAILURE_CONTRACT = count_checkpoint.COUNT_FAILURE_CONTRACT
COUNT_FAILURE_CONTRACT_SHA256 = count_checkpoint.COUNT_FAILURE_CONTRACT_SHA256
COUNT_FAILURE_PACKAGE_CAP = COUNT_FAILURE_CONTRACT["payload_bytes"]
COUNT_FAILURE_RESERVE_BYTES = count_checkpoint.FAILURE_RESERVE_BYTES
COUNT_FAILURE_RESERVE_SLOTS = count_checkpoint.FAILURE_RESERVE_SLOTS


class Quiet:
    def write(self, text):
        return len(text)

    def flush(self):
        pass


def runtime_controls():
    """Archived engineering qualification and pending metadata, no source data."""
    config = checkpoint.strict_json(store.read_local(ROOT / "config/gha-private-checkpoint-v3.json", 1 << 20))
    failure.require(config["canary_report"] == "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json"
                    and config["source_policy_sha256"] == checkpoint.POLICY_SHA, "EXACT_ARCHIVED_RUNTIME_CONTROL")
    archived = checkpoint.strict_json(store.read_local(ROOT / config["canary_report"], store.META_CAP))
    binding, qualification = archived["binding"], archived["qualification"]
    failure.require(store.sha(store.canonical(binding)) == config["binding_sha256"]
                    and store.sha(store.canonical(qualification)) == config["qualification_sha256"]
                    and qualification["source_sha"] == config["canary_source_sha"] == archived["source_sha"],
                    "EXACT_ARCHIVED_QUALIFIED_RUNTIME")
    store.checked_binding(binding)
    return binding, qualification, config["external_pending_reservations"]


def reservations(journal):
    records = []
    for path in sorted(Path(journal).glob("*.reservation.json")):
        failure.require(len(records) < store.MAX_ASSETS, "BOUNDED_FAILURE_PENDING_RECORDS")
        record = checkpoint.strict_json(store.read_local(path, 16384))
        # Reuse the exact validator without writing or making a request.
        failure.require(type(record) is dict and set(record) == {"schema_version", "key", "bytes", "sha256", "name"}
            and record["schema_version"] == "weekly-private-POST-reservation-v2"
            and type(record["bytes"]) is int and 0 < record["bytes"] <= store.ASSET_CAP
            and type(record["sha256"]) is str and store.HASH.fullmatch(record["sha256"])
            and record["name"] in {"blob-" + record["sha256"] + ".bin", "manifest-" + record["sha256"] + ".json"}
            and record["key"] == "asset:" + record["name"], "EXACT_FAILURE_PENDING_METADATA")
        records.append(record)
    return records


def operation_go(client, operation, inputs, binding):
    parsed = {name: checkpoint.strict_json(body) for name, body in inputs.items()}
    go = dict(schema_version="weekly-private-operation-GO-v2.1", approved=True, operation=operation,
        repository=store.REPO, run_id=client.run_id, source_sha=client.source_sha, config_sha256=store.config_sha(),
        scope_manifest_sha256=store.sha(store.canonical(parsed["payload_manifest"])) if operation == "append" else None,
        qualification_sha256=store.sha(store.canonical(parsed["qualification"])) if operation == "append" else None,
        single_writer_group="nfl-lab-single-writer", runtime_id=binding["runtime_id"],
        input_sha256={name: store.sha(body) for name, body in inputs.items()},
        job_id=client.job["job_id"], workflow_ref=client.job["workflow_ref"])
    return store.canonical(go)


def control_reference(path):
    """Hash a whole fixed control with bounded memory, including oversized ones."""
    path = store.parents_safe(path)
    parent, name = store.parent_fd(path)
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        before = os.fstat(descriptor)
        failure.require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= 512 << 20,
                        "BOUNDED_ORIGINAL_CONTROL_FILE_REQUIRED")
        digest, size = hashlib.sha256(), 0
        while True:
            value = os.read(descriptor, 65536)
            if not value:
                break
            size += len(value)
            failure.require(size <= before.st_size, "ORIGINAL_CONTROL_CHANGED")
            digest.update(value)
        after = os.fstat(descriptor)
        stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mode, info.st_mtime_ns, info.st_ctime_ns)
        failure.require(size == before.st_size and stamp(before) == stamp(after), "ORIGINAL_CONTROL_CHANGED")
        return dict(path=str(path), bytes=size, sha256=digest.hexdigest())
    finally:
        os.close(descriptor)


def count_controls(storage, original, root, package_root):
    """Full ten-file census. Overflow archives metadata, never a silent subset."""
    labels = tuple(name.lower().replace(".", "-") for name in CONTROLS) + tuple(
        "phase-" + name.lower().replace(".", "-") for name in PHASE_CONTROLS)
    failure.require(labels == tuple(COUNT_FAILURE_CONTRACT["original_control_labels"]), "SHARED_COUNT_FAILURE_CONTROL_LABELS")
    if package_root.is_dir():
        failure.require(not package_root.stat().st_mode & 0o077, "PRIVATE_ORIGINAL_PHASE_CONTROLS_REQUIRED")
        storage.register_root(package_root)
    candidates = [(original/name, label, True, name in PROGRESS_CONTROLS) for name, label in zip(CONTROLS, labels)]
    candidates += [(package_root/name, label, False, False) for name, label in zip(PHASE_CONTROLS, labels[len(CONTROLS):])]
    controls, eligible = [], []
    progressed = False
    for path, label, owned_required, progress in candidates:
        row = dict(label=label, state="ABSENT", bytes=None, sha256=None)
        if path.exists():
            ref = control_reference(path)
            row.update(bytes=ref["bytes"], sha256=ref["sha256"])
            owned = True
            if owned_required:
                try:
                    storage.validate_reference(path, ref["sha256"])
                except (store.StoreError, ValueError, OSError):
                    owned = False
            if not owned:
                row["state"] = "UNOWNED"
            elif not ref["bytes"]:
                row["state"] = "EMPTY"
            else:
                row["state"] = "ATTACHED"
                eligible.append((row, ref, owned_required))
                progressed = progressed or progress
        controls.append(row)
    total = sum(ref["bytes"] for _, ref, _ in eligible)
    attachments = []
    if total > COUNT_FAILURE_CONTRACT["original_controls_bytes"]:
        for row, _, _ in eligible:
            row["state"] = "BOUND_EXCEEDED"
    else:
        for row, ref, owned in eligible:
            if not owned:
                value = store.read_local(ref["path"], COUNT_FAILURE_CONTRACT["original_controls_bytes"])
                failure.require(len(value) == ref["bytes"] and store.sha(value) == ref["sha256"], "ORIGINAL_CONTROL_CHANGED")
                copied = root / "original-phase-controls" / Path(ref["path"]).name
                storage.write_bytes(copied, value)
                ref = dict(ref, path=str(copied))
            attachments.append(dict(label=row["label"], kind="original_failure", reference=ref))
    status = dict(schema_version=COUNT_FAILURE_CONTRACT["schema_version"] + "-status",
                  contract_sha256=COUNT_FAILURE_CONTRACT_SHA256, controls=controls)
    status_body = store.canonical(status)
    failure.require(len(status_body) <= COUNT_FAILURE_CONTRACT["status_bytes"], "COUNT_FAILURE_STATUS_CAP")
    status_path = root / "COUNT_CONTROL_STATUS.json"
    storage.write_bytes(status_path, status_body)
    attachments.append(dict(label=COUNT_FAILURE_CONTRACT["status_label"], kind="control",
        reference=dict(path=str(status_path), bytes=len(status_body), sha256=store.sha(status_body))))
    return attachments, status, progressed


def count_summary(status, body):
    rows = status["controls"]
    return dict(count_failure_contract_sha256=COUNT_FAILURE_CONTRACT_SHA256,
        control_bound_exceeded=any(row["state"] == "BOUND_EXCEEDED" for row in rows),
        original_control_bodies_complete=not any(row["state"] in {"BOUND_EXCEEDED", "UNOWNED"} for row in rows),
        archived_original_control_bytes=sum(row["bytes"] for row in rows if row["state"] == "ATTACHED"),
        failure_package_bytes=len(body), failure_package_cap_bytes=COUNT_FAILURE_PACKAGE_CAP)


def actual_failed_step(client, env, root_go):
    writer_failed = env.get("AUDIT_COUNT_WRITER_OUTCOME") == "failure"
    checkpoint_failed = env.get("AUDIT_COUNT_WRITER_OUTCOME") == "success" and env.get("AUDIT_COUNT_CHECKPOINT_OUTCOME") == "failure"
    failure.require(writer_failed or checkpoint_failed, "ORIGINAL_FAILED_STEP_REQUIRED")
    started_text = env.get("AUDIT_COUNT_STARTED_AT_UTC")
    started = store.utc(started_text)
    failure.require(store.utc(root_go["issued_at_utc"]) <= started <= datetime.now(timezone.utc),
                    "ACTUAL_ORIGINAL_START_CLOCK_REQUIRED")
    jobs = client.json(client.allow(client.path("/actions/runs/" + client.run_id + "/jobs?per_page=100&page=1")))
    failure.require(type(jobs) is dict and type(jobs.get("jobs")) is list
                    and jobs.get("total_count") == len(jobs["jobs"]) <= 100, "COMPLETE_CURRENT_FAILURE_JOBS")
    current = [j for j in jobs["jobs"] if j.get("id") == client.job["api_job_id"]
               and j.get("name") == audit.RESTORE_JOB and j.get("head_sha") == client.source_sha
               and j.get("run_id") == int(client.run_id)]
    failure.require(len(current) == 1 and type(current[0].get("steps")) is list
                    and len(current[0]["steps"]) <= 128, "ACTUAL_FAILED_STEP_API_REQUIRED")
    matches = []
    for step in current[0]["steps"]:
        if step.get("status") != "completed" or step.get("conclusion") not in {"failure", "timed_out"}:
            continue
        if step.get("name") == (WRITER_STEP if writer_failed else CHECKPOINT_STEP):
            matches.append(step)
    failure.require(len(matches) == 1, "UNAMBIGUOUS_ACTUAL_FAILED_STEP_REQUIRED")
    step = matches[0]
    # The parent's start output is recorded in the immediately preceding step.
    # Keep that actual clock verbatim; do not substitute the later API step start.
    failure.require(store.utc(current[0]["started_at"]) <= started <= store.utc(client.started_at)
                    and store.utc(step["started_at"]) <= store.utc(step["completed_at"])
                    <= store.utc(client.started_at), "FAILURE_STEP_PRECEDES_PRESERVATION")
    code_text = env.get("AUDIT_COUNT_WRITER_EXIT_CODE" if writer_failed else "AUDIT_COUNT_CHECKPOINT_EXIT_CODE", "")
    exit_code = None
    if code_text:
        failure.require(re.fullmatch(r"-?[0-9]{1,3}", code_text) is not None, "ORIGINAL_EXIT_CODE_REQUIRED")
        exit_code = int(code_text)
        failure.require(-127 <= exit_code <= 255 and exit_code != 0, "ORIGINAL_EXIT_CODE_REQUIRED")
    return started_text, step, exit_code


def prepare_client(env, phase, binding, pending):
    runner = store.parents_safe(env["RUNNER_TEMP"])
    run_id = env["GITHUB_RUN_ID"]
    failure.require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None, "EXACT_FAILURE_RUN_ID")
    root = runner / ((VERSION if phase == "record" else VERSION + "-reader") + "-" + run_id)
    failure.require(not root.exists(), "ONE_FAILURE_BRIDGE_INVOCATION_NO_RETRY")
    root.mkdir(mode=0o700)
    journal = root / "journal"
    journal.mkdir(mode=0o700)
    checkpoint.seed_pending(journal, pending)
    job = actions_context(env, "write")
    client = store.Client(env.get("GITHUB_TOKEN"), run_id, journal=journal, source_sha=env["GITHUB_SHA"],
                          job=job, operation="append" if phase == "record" else "restore")
    client.authenticate_actions_job()
    client.bind(binding)
    return root, journal, client


def handoff(result, root_sha, binding, pending):
    doc = dict(schema_version=VERSION + "-handoff", repository=store.REPO,
        run_id=result["attempt"]["run_id"], source_sha=result["attempt"]["source_sha"],
        root_go_sha256=root_sha, binding_sha256=store.sha(store.canonical(binding)),
        request_sha256=result["request_sha256"], descriptor=result["descriptor"], pending_reservations=pending,
        failure_contract_sha256=COUNT_FAILURE_CONTRACT_SHA256)
    encoded = store.canonical(doc)
    failure.require(len(encoded) <= HANDOFF_CAP
                    and not any(marker in encoded for marker in (b"https://", b"/tmp/", b"/home/", b"/workspace/", b"ghs_")),
                    "SAFE_BOUNDED_FAILURE_HANDOFF_ONLY")
    return encoded


def record(env, root_go, binding, qualification, pending):
    failure.require(env.get("GITHUB_JOB") == audit.RESTORE_JOB, "FAILURE_WRITER_JOB_ONLY")
    failure.require(env.get("AUDIT_COUNT_WRITER_OUTCOME") == "failure" or
                    env.get("AUDIT_COUNT_WRITER_OUTCOME") == "success" and env.get("AUDIT_COUNT_CHECKPOINT_OUTCOME") == "failure",
                    "ORIGINAL_FAILED_STEP_REQUIRED")
    failure.require(env.get("GITHUB_OUTPUT") is not None and store.parents_safe(env["GITHUB_OUTPUT"]).is_file(),
                    "GENUINE_FAILURE_OUTPUT_CHANNEL_REQUIRED")
    root, journal, client = prepare_client(env, "record", binding, pending)
    store.check_proof(client, qualification, "qualified", same_run=False)
    started, step, exit_code = actual_failed_step(client, env, root_go)
    original = store.parents_safe(env["RUNNER_TEMP"]) / (audit.VERSION + "-" + client.run_id)
    policy_body = store.read_local(ROOT / "config/operational-source-policy-v2.json", 1 << 20)
    failure.require(store.sha(policy_body) == checkpoint.POLICY_SHA, "EXACT_SOURCE_POLICY_REQUIRED")
    storage = OperationalStorage(original / "cache", checkpoint.strict_json(policy_body), state=original / "state")
    storage.register_root(original)
    storage.register_root(root)
    # Prior actual metadata-only bridge/restore journals can contain unresolved
    # POST intent. Import, never erase or infer absence from their API response.
    old_journals = [original / "journal", original / "private-journal", store.parents_safe(env["RUNNER_TEMP"]) /
                    ("audit-count-package-" + client.run_id) / "journal"]
    with storage.transaction():
        for old in old_journals:
            if old.is_dir():
                if not old.is_relative_to(original):
                    storage.register_root(old.parent)
                checkpoint.seed_pending(journal, reservations(old))
        storage._require(0)  # Existing original and newly imported intent bytes count.
    package_root = store.parents_safe(env["RUNNER_TEMP"]) / ("audit-count-package-" + client.run_id)
    attachments, control_status, progressed = count_controls(storage, original, root, package_root)
    request = dict(schema_version=failure.VERSION + "-request",
        attempt=dict(repository=store.REPO, run_id=client.run_id, run_attempt=1, source_sha=client.source_sha,
                     job_id=audit.RESTORE_JOB, workflow_ref=client.job["workflow_ref"]),
        operation="checkpoint", state="PARTIAL" if progressed else "FAILED",
        input_contract_sha256=env["AUDIT_COUNT_ROOT_GO_SHA256"],
        failure=dict(kind="DEADLINE" if step["conclusion"] == "timed_out" else "EXCEPTION",
                     code="ORIGINAL_HOSTED_COUNT_STEP_FAILED", exit_code=exit_code),
        # API times have second precision; retain them verbatim separately from
        # the actual preservation process's observation clock. Never round or
        # backdate the original microsecond start to fit an API timestamp.
        clocks=dict(started_at_utc=started, observed_at_utc=client.started_at, original=dict(
            github_step_started_at_utc=step["started_at"], github_step_completed_at_utc=step["completed_at"],
            root_issued_at_utc=root_go["issued_at_utc"],
            root_expires_at_utc=root_go["expires_at_utc"])), attachments=attachments)
    output = root / "evidence"
    count_checkpoint.validate_count_failure_variant(request, control_status)
    failure.record_failure(request, storage, output)
    inputs = dict(binding=store.canonical(binding), qualification=store.canonical(qualification),
                  payload_manifest=store.read_local(output / "PAYLOAD.json", failure.METADATA_CAP))
    failure.require(datetime.now(timezone.utc) < store.utc(root_go["expires_at_utc"]), "ROOT_GO_CURRENT_CLOCK")
    authorization = operation_go(client, "append", inputs, binding)
    storage.write_bytes(root / "FAILURE_APPEND_GO.json", authorization)
    # Pre-admit safe output size with maximum-size server IDs and both future
    # POST reservations BEFORE uploading anything. Never strand an oversized handoff.
    body = store.read_local(output / "FAILURE.json.gz", failure.PACKAGE_CAP)
    count_checkpoint.validate_count_failure_variant(request, control_status, body)
    entry = dict(schema_version="weekly-private-restore-manifest-v2", payload=failure.payload_manifest(body),
        payload_asset_id=10**20-1, payload_name="blob-"+store.sha(body)+".bin", producer_process=client.process,
        binding_sha256=store.sha(store.canonical(binding)), writer_run_id=client.run_id)
    encoded_entry = store.canonical(entry)
    preview = dict(entry=entry, manifest_asset_id=10**20-1, manifest_sha256=store.sha(encoded_entry), manifest_bytes=len(encoded_entry))
    future_pending = [checkpoint.reservation_metadata("asset:blob-"+store.sha(body)+".bin", body, "blob-"+store.sha(body)+".bin"),
        checkpoint.reservation_metadata("asset:manifest-"+store.sha(encoded_entry)+".json", encoded_entry, "manifest-"+store.sha(encoded_entry)+".json")]
    handoff(dict(attempt=request["attempt"], request_sha256=store.sha(store.canonical(request)), descriptor=preview),
            env["AUDIT_COUNT_ROOT_GO_SHA256"], binding, reservations(journal) + future_pending)
    result = failure.append_failure(client, storage, output, authorization=authorization,
        authorization_sha256=store.sha(authorization), inputs=inputs)
    encoded = handoff(result, env["AUDIT_COUNT_ROOT_GO_SHA256"], binding, reservations(journal))
    storage.write_bytes(root / "FAILURE_HANDOFF.json", encoded)
    return dict(result["status"], **count_summary(control_status, body)), encoded


def restore(env, root_go, binding, qualification, pending):
    failure.require(env.get("GITHUB_JOB") == hosted.READER_JOB, "FAILURE_READER_JOB_ONLY")
    encoded = env.get("AUDIT_COUNT_FAILURE_HANDOFF_JSON", "").encode()
    failure.require(0 < len(encoded) <= HANDOFF_CAP and store.sha(encoded) == env.get("AUDIT_COUNT_FAILURE_HANDOFF_SHA256"),
                    "EXACT_SAFE_FAILURE_HANDOFF_HASH")
    doc = checkpoint.strict_json(encoded)
    failure.require(type(doc) is dict and set(doc) == HANDOFF_KEYS and doc["schema_version"] == VERSION + "-handoff"
        and doc["repository"] == store.REPO and doc["source_sha"] == env["GITHUB_SHA"] and doc["run_id"] == env["GITHUB_RUN_ID"]
        and doc["root_go_sha256"] == env["AUDIT_COUNT_ROOT_GO_SHA256"]
        and doc["binding_sha256"] == store.sha(store.canonical(binding))
        and doc["failure_contract_sha256"] == COUNT_FAILURE_CONTRACT_SHA256
        and type(doc["request_sha256"]) is str and store.HASH.fullmatch(doc["request_sha256"])
        and encoded == store.canonical(doc), "EXACT_CURRENT_FAILURE_HANDOFF")
    checkpoint.descriptor_meta(doc["descriptor"], COUNT_FAILURE_PACKAGE_CAP)
    root, journal, client = prepare_client(env, "restore", binding, pending)
    checkpoint.seed_pending(journal, doc["pending_reservations"])
    store.check_proof(client, qualification, "qualified", same_run=False)
    policy_body = store.read_local(ROOT / "config/operational-source-policy-v2.json", 1 << 20)
    failure.require(store.sha(policy_body) == checkpoint.POLICY_SHA, "EXACT_SOURCE_POLICY_REQUIRED")
    storage = OperationalStorage(root / "cache", checkpoint.strict_json(policy_body), state=root / "state")
    storage.register_root(root)
    inputs = dict(binding=store.canonical(binding), descriptor=store.canonical(doc["descriptor"]))
    failure.require(datetime.now(timezone.utc) < store.utc(root_go["expires_at_utc"]), "ROOT_GO_CURRENT_CLOCK")
    authorization = operation_go(client, "restore", inputs, binding)
    storage.write_bytes(root / "FAILURE_RESTORE_GO.json", authorization)
    result = failure.restore_failure(client, storage, root / "evidence", authorization=authorization,
        authorization_sha256=store.sha(authorization), inputs=inputs)
    failure.require(result["attempt"]["job_id"] == audit.RESTORE_JOB and result["request_sha256"] == doc["request_sha256"],
                    "EXACT_RESTORED_FAILURE_REQUEST")
    body = store.read_local(root / "evidence/FAILURE.json.gz", COUNT_FAILURE_PACKAGE_CAP)
    request, values = failure.unpack(body)
    attached = dict(zip((item["label"] for item in request["attachments"]), values))
    control_status = failure.document(attached[COUNT_FAILURE_CONTRACT["status_label"]], COUNT_FAILURE_CONTRACT["status_bytes"])
    count_checkpoint.validate_count_failure_variant(request, control_status, body)
    # store.restore already performed the independent-producer-process readback.
    # Bind its returned proof to this real reader. A later third consumer can
    # call failure.verify_restore with its own authenticated process.
    proof = result["proof"]
    failure.require(proof["exact_readback"] is True and proof["separate_process"] is True
        and proof["payload_sha256"] == doc["descriptor"]["entry"]["payload"]["sha256"]
        and proof["job"]["api_job_id"] == client.job["api_job_id"], "ACTUAL_FAILURE_RESTORE_PROOF_REQUIRED")
    return dict(result["status"], **count_summary(control_status, body)), None


def outputs(env, encoded):
    if encoded is None:
        return
    path = env.get("GITHUB_OUTPUT")
    failure.require(path is not None, "GENUINE_FAILURE_OUTPUT_CHANNEL_REQUIRED")
    payload = ("failure_handoff_json=" + encoded.decode() + "\nfailure_handoff_sha256=" + store.sha(encoded)
               + "\nfailure_appended=true\n").encode()
    directory, name = store.parent_fd(path)
    try:
        descriptor = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, dir_fd=directory)
    finally:
        os.close(directory)
    try:
        with os.fdopen(os.dup(descriptor), "ab") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def run(env, phase):
    body = env.get("AUDIT_COUNT_ROOT_GO_JSON", "").encode()
    expected = env.get("AUDIT_COUNT_ROOT_GO_SHA256", "")
    root_go = hosted.checked_root(body, expected, env)
    event = checkpoint.strict_json(store.read_local(env["GITHUB_EVENT_PATH"], store.META_CAP))
    failure.require(event.get("inputs", {}).get("inference_builder_go_json") == body.decode()
                    and event["inputs"].get("inference_builder_go_sha256") == expected,
                    "EXACT_ACTUAL_FAILURE_ROOT_INPUT")
    binding, qualification, pending = runtime_controls()
    method = record if phase == "record" else restore
    status, encoded = method(env, root_go, binding, qualification, pending)
    outputs(env, encoded)
    return status


def main(argv=None, *, environ=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", nargs="?", choices=["record", "append", "restore"], default="record")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print('{"state":"PREPARATION_ONLY_NO_IO","successful_forecast":false}')
        return 2
    try:
        limits()
        with redirect_stdout(Quiet()), redirect_stderr(Quiet()):
            status = run(os.environ if environ is None else environ, "record" if args.phase == "append" else args.phase)
        print(json.dumps(status, sort_keys=True))
        return 0  # Preservation success only. Never override original step outcome.
    except Exception as error:
        code = error.code if isinstance(error, (audit.AuditGuardError, store.StoreError)) else "AUDIT_COUNT_FAILURE_PRESERVATION_FAILED"
        if not isinstance(code, str) or re.fullmatch(r"[A-Z0-9_]{1,90}", code) is None:
            code = "AUDIT_COUNT_FAILURE_PRESERVATION_FAILED"
        status = failure.safe_status("FAILURE_PRESERVATION_BLOCKED")
        status["reason"] = code
        print(json.dumps(status, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
