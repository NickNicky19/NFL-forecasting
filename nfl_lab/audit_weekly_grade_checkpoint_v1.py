"""Private grading checkpoint between the existing restore and export jobs.

append(Snapshot, native append Client, qualified_package, ...) returns a CLOSED
handoff, never DurableHistory. restore(handoff, native GET-only Client,
qualified_package, RegisteredEpoch, ...) performs actual private readback and
then calls unchanged grade.restore_snapshot / confirm_durable / report.

The parent must first authenticate genuine archive restore, a population fixed
before values, and the actual collector. Capture5 without that population is
NOT a retrospective primary grading candidate. The live authenticate callback
must bind every request digest to its owned ROOT/source/API/native evidence;
saved JSON, helper output and a self-digest are never execution authority.

Run in a separate native 180-wall/120-CPU/512-MiB worker. The tool installs the
unchanged private-store limits; the library verifies the actual native limits.
No imports acquire credentials, provider bodies, outcomes, models or fits. No
ROOT, workflow, frozen proof, grading algorithm, old clock or gate is changed.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
from pathlib import Path
import re
import resource
import signal
import time

from . import audit_weekly_grade_v1 as grade, audit_weekly_epoch_v1 as epoch
from . import audit_weekly_archive_v1 as archive, private_draft_store as store
from . import gha_private_checkpoint as cp, state, weekly_durable_acceptance as acceptance
from .operational_storage import OperationalStorage

VERSION = "audit-weekly-grade-checkpoint-v1"
MULTIPART_VERSION = "audit-weekly-grade-checkpoint-v2"
JOBS = dict(writer="audit-weekly-restore-v1", reader="audit-weekly-export-v1")
LIMITS = dict(wall_seconds=180, CPU_seconds=120, address_space_bytes=512 << 20,
    global_bytes=512 << 20, encoded_bytes=8 << 20, decoded_bytes=64 << 20,
    handoff_bytes=16 << 10, HTTP_calls=40, retries=0, fits=0, model_decodes=0)
FILES = ("nfl_lab/audit_weekly_grade_checkpoint_v1.py", "tools/audit_weekly_grade_checkpoint_v1.py",
         "tests/test_audit_weekly_grade_checkpoint_v1.py")
HANDOFF_KEYS = {"schema_version", "repository", "current_root_go_sha256", "epoch_sha256", "snapshot_sha256",
    "body_sha256", "body_bytes", "snapshot_completed_at", "producer", "runtime_binding_sha256",
    "qualified_package_sha256", "grade_code_pins_sha256", "helper_sha256", "descriptor", "append_proof",
    "append_proof_sha256", "successful_forecast", "public_release", "fits"}
APPEND_KEYS = {"schema_version", "current_root_go_sha256", "producer", "epoch_sha256", "snapshot_sha256",
    "body_sha256", "body_bytes", "descriptor_sha256", "qualification_sha256", "api_evidence_sha256",
    "started_at_utc", "completed_at_utc", "HTTP_calls", "transfer_bytes"}
PART_APPEND_KEYS = {"schema_version", "index", "local_manifest_sha256", "body_sha256", "body_bytes", "descriptor_sha256",
    "producer", "current_root_go_sha256", "qualification_sha256", "started_at_utc", "completed_at_utc", "HTTP_calls", "transfer_bytes"}
APPEND_ROOT_LINK_KEYS = {"schema_version", "current_root_go_sha256", "epoch_sha256", "snapshot_sha256",
    "local_binding", "native_binding", "native_parts_sha256"}
_KEY = object()


class CheckpointError(ValueError):
    """Fixed public-safe error codes only."""


def require(value, code):
    if not value:
        raise CheckpointError(code)


def hashed(value):
    return type(value) is str and store.HASH.fullmatch(value) is not None


def pins():
    root = Path(__file__).resolve().parents[1]
    return {name: store.sha(store.read_local(root / name, 2 << 20)) for name in FILES}


def native_envelope():
    for kind, maximum in ((resource.RLIMIT_CPU, 120), (resource.RLIMIT_AS, 512 << 20)):
        soft, hard = resource.getrlimit(kind)
        require(type(soft) is int and type(hard) is int and 0 < soft <= hard <= maximum,
                "NATIVE_GRADING_CHECKPOINT_WORKER_LIMITS_REQUIRED")
    timer, interval = signal.getitimer(signal.ITIMER_REAL)
    require(signal.getsignal(signal.SIGALRM) == signal.SIG_DFL and 0 < timer <= 180 and interval == 0,
            "NATIVE_GRADING_CHECKPOINT_WALL_GUARD_REQUIRED")


class Budget:
    def __init__(self):
        native_envelope()
        self.wall, self.cpu = time.monotonic(), time.process_time()
    def check(self, client):
        require(time.monotonic() - self.wall <= 180 and time.process_time() - self.cpu <= 120
                and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= 512 << 20
                and type(client.calls) is int and 0 <= client.calls <= 40,
                "GRADING_CHECKPOINT_NATIVE_BUDGET_EXCEEDED")


def _authenticate(callback, kind, inputs, at):
    require(callable(callback), "LIVE_GRADING_CHECKPOINT_PARENT_AUTHENTICATOR_REQUIRED")
    request = dict(schema_version=VERSION + "-authentication-request", kind=kind,
        inputs=deepcopy(inputs), inputs_sha256=state.digest(inputs), at=state.utc(at).isoformat())
    require(len(store.canonical(request)) <= 64 << 10 and callback(request) is True,
            "LIVE_GRADING_CHECKPOINT_PARENT_AUTHENTICATION_REJECTED")


def api_body(client, suffix):
    url = client.allow(store.API + suffix)
    status, headers, raw = client.request(url)
    require(status == 200 and type(raw) is bytes and 0 < len(raw) <= store.META_CAP
            and headers.get("x-ratelimit-remaining") != "0" and "retry-after" not in headers,
            "ACTUAL_GRADING_CHECKPOINT_API_BODY_REQUIRED")
    return cp.strict_json(raw), store.sha(raw)


def current(client, role, package, pending_census, budget):
    require(isinstance(client, store.Client) and client.operation == ("append" if role == "writer" else "restore")
            and client.binding == package.get("binding") and (role != "reader" or getattr(client, "readonly", False) is True),
            "NATIVE_BOUND_APPEND_OR_GET_ONLY_RESTORE_CLIENT_REQUIRED")
    identity = archive.checked(client, JOBS[role])
    acceptance.identity(identity)
    run, run_sha = api_body(client, "/actions/runs/" + client.run_id)
    listing, jobs_sha = api_body(client, "/actions/runs/" + client.run_id + "/jobs?per_page=100&page=1")
    expected_branch = identity["workflow_ref"].split("@refs/heads/", 1)[1]
    actor = run.get("actor", {})
    require(type(run.get("id")) is int and run["id"] == int(client.run_id)
            and run.get("head_sha") == client.source_sha
            and run.get("repository", {}).get("full_name") == run.get("head_repository", {}).get("full_name") == store.REPO
            and run.get("path") == ".github/workflows/lab.yml"
            and run.get("head_branch") == expected_branch and run.get("status") == "in_progress"
            and run.get("conclusion") is None and run.get("event") == "workflow_dispatch"
            and type(run.get("run_attempt")) is int and run["run_attempt"] == 1
            and (actor.get("login"), actor.get("id")) in {("NickNicky19", 208912933), ("github-actions[bot]", 41898282)}
            and ("triggering_actor" not in run or (run["triggering_actor"].get("login"), run["triggering_actor"].get("id"))
                 == (actor.get("login"), actor.get("id"))), "ACTUAL_CURRENT_GRADING_JOB_ACTOR_AND_BRANCH")
    require(type(listing) is dict and type(listing.get("jobs")) is list and type(listing.get("total_count")) is int
            and listing["total_count"] == len(listing["jobs"]) <= 100, "COMPLETE_CURRENT_GRADING_JOB_CENSUS")
    matches = [j for j in listing["jobs"] if j.get("id") == identity["api_job_id"]]
    require(len(matches) == 1 and matches[0].get("name") == JOBS[role]
            and matches[0].get("status") == "in_progress" and matches[0].get("conclusion") is None
            and matches[0].get("head_sha") == client.source_sha and matches[0].get("run_id") == int(client.run_id)
            and state.utc(matches[0]["started_at"]) <= state.utc(client.started_at), "GENUINE_CURRENT_GRADING_API_JOB")
    archive.authenticate_qualification(client, package, pending_census)
    budget.check(client)
    return identity, matches[0], listing["jobs"], dict(run_sha256=run_sha, jobs_sha256=jobs_sha)


def recheck(client, identity, job):
    """Fresh actual API checks after the native transfer, before typed use."""
    client.authenticate_actions_job()
    require(client.job["api_job_id"] == identity["api_job_id"], "GRADING_CURRENT_JOB_CHANGED_DURING_TRANSFER")
    run, run_sha = api_body(client, "/actions/runs/" + client.run_id)
    listing, jobs_sha = api_body(client, "/actions/runs/" + client.run_id + "/jobs?per_page=100&page=1")
    require(run.get("head_sha") == identity["source_sha"] and run.get("id") == int(identity["run_id"])
            and run.get("status") == "in_progress" and type(run.get("run_attempt")) is int and run["run_attempt"] == 1
            and run.get("conclusion") is None and run.get("path") == ".github/workflows/lab.yml"
            and run.get("repository", {}).get("full_name") == run.get("head_repository", {}).get("full_name") == store.REPO
            and run.get("event") == "workflow_dispatch"
            and run.get("head_branch") == identity["workflow_ref"].split("@refs/heads/", 1)[1]
            and type(listing.get("total_count")) is int and type(listing.get("jobs")) is list
            and listing["total_count"] == len(listing["jobs"]) <= 100, "CURRENT_GRADING_RUN_CHANGED_DURING_TRANSFER")
    found = [j for j in listing["jobs"] if j.get("id") == identity["api_job_id"]]
    require(len(found) == 1 and all(found[0].get(k) == job.get(k) for k in
        ("id", "name", "head_sha", "run_id", "status", "conclusion", "started_at")), "CURRENT_GRADING_JOB_CHANGED_DURING_TRANSFER")
    return dict(run_sha256=run_sha, jobs_sha256=jobs_sha)


def recheck_v2(client, identity, job):
    """One NEW actual run/jobs cohort applies both original recheck guards.

    No previous response, authenticated flag or caller-supplied API body is
    reused. V1 retains its original two-pair implementation above.
    """
    require(isinstance(client, store.Client) and cp.client_identity(client) == identity
        and client.job.get("execution_lane") == "github_actions" and client.job.get("permission") == "write",
        "GRADING_CURRENT_CLIENT_CHANGED_DURING_TRANSFER")
    run, run_sha = api_body(client, "/actions/runs/" + client.run_id)
    listing, jobs_sha = api_body(client, "/actions/runs/" + client.run_id + "/jobs?per_page=100&page=1")
    actor = run.get("actor", {})
    require(type(run.get("id")) is int and run["id"] == int(identity["run_id"])
        and run.get("head_sha") == identity["source_sha"] == client.source_sha
        and run.get("status") == "in_progress" and run.get("conclusion") is None
        and type(run.get("run_attempt")) is int and run["run_attempt"] == 1
        and run.get("path") == ".github/workflows/lab.yml" and run.get("event") == "workflow_dispatch"
        and run.get("repository", {}).get("full_name") == run.get("head_repository", {}).get("full_name") == store.REPO
        and run.get("head_branch") == identity["workflow_ref"].split("@refs/heads/", 1)[1]
        and (actor.get("login"), actor.get("id")) in {("NickNicky19", 208912933), ("github-actions[bot]", 41898282)}
        and ("triggering_actor" not in run or (run["triggering_actor"].get("login"), run["triggering_actor"].get("id"))
            == (actor.get("login"), actor.get("id")))
        and type(listing.get("total_count")) is int and type(listing.get("jobs")) is list
        and listing["total_count"] == len(listing["jobs"]) <= 100
        and all(type(row) is dict for row in listing["jobs"]), "CURRENT_GRADING_RUN_CHANGED_DURING_TRANSFER")
    # The original Client authentication rejects duplicate running job names;
    # the original checkpoint recheck separately binds the exact API job ID.
    named = [row for row in listing["jobs"] if row.get("name") == client.job["job_id"]
        and row.get("status") == "in_progress" and row.get("run_id") == int(client.run_id)
        and row.get("head_sha") == client.source_sha]
    found = [row for row in listing["jobs"] if row.get("id") == identity["api_job_id"]]
    require(len(named) == len(found) == 1 and named[0] is found[0]
        and type(found[0].get("id")) is int and found[0]["id"] > 0
        and all(found[0].get(key) == job.get(key) for key in
            ("id", "name", "head_sha", "run_id", "status", "conclusion", "started_at")),
        "CURRENT_GRADING_JOB_CHANGED_DURING_TRANSFER")
    return dict(run_sha256=run_sha, jobs_sha256=jobs_sha)


def safe_handoff(handoff):
    version = MULTIPART_VERSION if type(handoff) is dict and handoff.get("schema_version") == MULTIPART_VERSION+"-handoff" else VERSION
    require(type(handoff) is dict and set(handoff) == HANDOFF_KEYS
            and handoff["schema_version"] == version + "-handoff" and handoff["repository"] == store.REPO
            and handoff["successful_forecast"] is handoff["public_release"] is False
            and type(handoff["fits"]) is int and handoff["fits"] == 0
            and all(hashed(handoff[k]) for k in ("current_root_go_sha256", "epoch_sha256", "snapshot_sha256", "body_sha256",
                "runtime_binding_sha256", "qualified_package_sha256", "grade_code_pins_sha256", "append_proof_sha256"))
            and type(handoff["body_bytes"]) is int and 0 < handoff["body_bytes"] <= 8 << 20
            and handoff["helper_sha256"] == pins(), "CLOSED_EXACT_GRADING_CHECKPOINT_HANDOFF")
    producer = acceptance.identity(handoff["producer"])
    require(producer["job_id"] == JOBS["writer"], "ONLY_RESTORE_JOB_WRITES_GRADING_CHECKPOINT")
    entry = cp.descriptor_meta(handoff["descriptor"], 8 << 20)
    require(entry["payload"]["sha256"] == handoff["body_sha256"] and entry["payload"]["bytes"] == handoff["body_bytes"]
            and entry["producer_process"] == producer["process_identity"] and entry["writer_run_id"] == producer["run_id"]
            and entry["binding_sha256"] == handoff["runtime_binding_sha256"], "EXACT_ORIGINAL_GRADING_NATIVE_DESCRIPTOR")
    p = handoff["append_proof"]
    require(type(p) is dict and set(p) == APPEND_KEYS and p["schema_version"] == version + "-native-append"
            and state.digest(p) == handoff["append_proof_sha256"] and p["producer"] == producer
            and all(p[k] == handoff[k] for k in ("current_root_go_sha256", "epoch_sha256", "snapshot_sha256", "body_sha256", "body_bytes"))
            and p["descriptor_sha256"] == state.digest(handoff["descriptor"])
            and hashed(p["qualification_sha256"]) and hashed(p["api_evidence_sha256"])
            and type(p["HTTP_calls"]) is int and 0 < p["HTTP_calls"] <= 40
            and type(p["transfer_bytes"]) is int and 0 < p["transfer_bytes"] <= store.TRANSFER_CAP
            and state.utc(handoff["snapshot_completed_at"]) <= state.utc(p["started_at_utc"]) <= state.utc(p["completed_at_utc"]),
            "CLOSED_ORIGINAL_NATIVE_APPEND_PROOF")
    raw = store.canonical(handoff)
    require(len(raw) <= 16 << 10, "FINITE_GRADING_CHECKPOINT_HANDOFF")
    return raw


def output_root(storage, output, reserve):
    require(isinstance(storage, OperationalStorage) and storage.limit_bytes <= 512 << 20,
            "UNCHANGED_GLOBAL_GRADING_STORAGE_REQUIRED")
    output = store.parents_safe(output)
    with storage.transaction():
        require(not output.exists(), "FRESH_GRADING_CHECKPOINT_OPERATION_NO_RETRY")
        storage._require(reserve)
        storage.register_root(output)
    return output


def _binding_context(root_sha, package, snapshot_sha, body_sha):
    return dict(current_root_go_sha256=root_sha, qualified_package_sha256=state.digest(package),
        snapshot_sha256=snapshot_sha, body_sha256=body_sha, helper_sha256=pins(), grade_code_pins_sha256=state.digest(grade.pins()))


def _append_parts(snapshot, manifest, client, package, storage, output, producer, root_sha, budget, clock):
    records = []
    parts = grade._partition_manifest(manifest)["parts"]
    refs = [dict(path=str(Path(snapshot.binding["path"]).parent/part["name"]), bytes=part["bytes"], sha256=part["sha256"])
        for part in parts]
    bodies = grade._read_owned_many(storage, refs, 8 << 20)
    for part in parts:
        budget.check(client)
        body = bodies.pop(0)
        started = state.utc(clock()).isoformat()
        with storage.transaction():
            storage._check(Path(client.journal)/"checkpoint-reservation-probe")
            descriptor = store.append(client, body, cp.payload(body), package["qualification"])
        proof = dict(schema_version=MULTIPART_VERSION+"-part-append", index=part["index"],
            local_manifest_sha256=snapshot.binding["sha256"], body_sha256=part["sha256"], body_bytes=part["bytes"],
            descriptor_sha256=state.digest(descriptor), producer=producer, current_root_go_sha256=root_sha,
            qualification_sha256=state.digest(package["qualification"]), started_at_utc=started,
            completed_at_utc=state.utc(clock()).isoformat(), HTTP_calls=client.calls, transfer_bytes=client.transferred)
        record = dict(index=part["index"], descriptor=descriptor, append_proof=proof)
        storage.write_bytes(output/f"PART_{part['index']:02d}_APPEND.json", store.canonical(record))
        records.append(record); del body
        budget.check(client)
    # The only root carrying private part locators is created after every
    # actual part append. Failed parts/proofs remain; no completed handoff exists.
    root = dict(schema_version=grade.CHECKPOINT_WIRE_V2, snapshot_manifest=manifest,
        snapshot_body_sha256=snapshot.binding["sha256"], parts=records)
    plain = store.canonical(root)
    require(len(plain) <= grade.PARTITION_LIMITS["manifest_bytes"], "FINITE_PRIVATE_GRADING_ROOT")
    body = gzip.compress(plain, mtime=0)
    storage.write_bytes(output/"CHECKPOINT_ROOT.json.gz", body)
    with storage.transaction():
        storage._check(Path(client.journal)/"checkpoint-reservation-probe")
        descriptor = store.append(client, body, cp.payload(body), package["qualification"])
    return body, descriptor


def _private_parts(handoff, wire):
    require(handoff["schema_version"] == MULTIPART_VERSION+"-handoff", "EXPLICIT_MULTIPART_GRADING_HANDOFF")
    manifest = grade._wire_manifest(wire)
    require(wire["schema_version"] == grade.CHECKPOINT_WIRE_V2
        and manifest["logical_sha256"] == handoff["snapshot_sha256"], "EXACT_PRIVATE_GRADING_ROOT_DOCUMENT")
    for part, record in zip(manifest["parts"], wire["parts"]):
        descriptor = record["descriptor"]; entry = cp.descriptor_meta(descriptor, 8 << 20); proof = record["append_proof"]
        require(entry["producer_process"] == handoff["producer"]["process_identity"]
            and entry["writer_run_id"] == handoff["producer"]["run_id"]
            and entry["binding_sha256"] == handoff["runtime_binding_sha256"], "ORIGINAL_PRIVATE_GRADING_PART_PRODUCER")
        require(type(proof) is dict and set(proof) == PART_APPEND_KEYS
            and proof["schema_version"] == MULTIPART_VERSION+"-part-append"
            and type(proof["index"]) is int and proof["index"] == part["index"]
            and proof["producer"] == handoff["producer"] and proof["local_manifest_sha256"] == wire["snapshot_body_sha256"]
            and proof["current_root_go_sha256"] == handoff["current_root_go_sha256"]
            and proof["qualification_sha256"] == handoff["append_proof"]["qualification_sha256"]
            and proof["body_sha256"] == part["sha256"] and proof["body_bytes"] == part["bytes"]
            and proof["descriptor_sha256"] == state.digest(descriptor)
            and type(proof["HTTP_calls"]) is int and 0 < proof["HTTP_calls"] <= handoff["append_proof"]["HTTP_calls"] <= 40
            and type(proof["transfer_bytes"]) is int and 0 < proof["transfer_bytes"] <= handoff["append_proof"]["transfer_bytes"] <= store.TRANSFER_CAP
            and state.utc(handoff["snapshot_completed_at"]) <= state.utc(handoff["append_proof"]["started_at_utc"])
            <= state.utc(proof["started_at_utc"]) <= state.utc(proof["completed_at_utc"])
            <= state.utc(handoff["append_proof"]["completed_at_utc"]), "CLOSED_ORIGINAL_GRADING_PART_APPEND")
    return manifest


def append_root_link(snapshot, handoff, *, storage, native_binding):
    """Closed private callback metadata, not an authorization or new binding.

    The parent derives native_binding from its own checkpoint output directory,
    calls this validator with the original live Snapshot, and compares the
    returned local binding with its approved CHECKPOINT_APPEND_CURRENT_ROOT
    scope. The original Snapshot/binding is never rewritten.
    """
    require(type(snapshot) is grade.Snapshot, "LIVE_ORIGINAL_APPEND_SNAPSHOT_REQUIRED")
    snapshot.verify(); safe_handoff(handoff)
    require(handoff["schema_version"] == MULTIPART_VERSION+"-handoff"
        and handoff["snapshot_sha256"] == snapshot.sha256
        and handoff["epoch_sha256"] == snapshot.document["epoch_sha256"]
        and type(native_binding) is dict and set(native_binding) == {"path", "bytes", "sha256"}
        and native_binding["sha256"] == handoff["body_sha256"] and native_binding["bytes"] == handoff["body_bytes"],
        "EXACT_ORIGINAL_LOCAL_AND_NATIVE_ROOT_SCOPE")
    body, local = grade._read_owned_many(storage, [native_binding, snapshot.binding], grade.PARTITION_LIMITS["manifest_bytes"])
    wire = grade._unpack(body, grade.PARTITION_LIMITS["manifest_bytes"])
    manifest = _private_parts(handoff, wire)
    local_manifest = grade._partition_manifest(grade._unpack(local, grade.PARTITION_LIMITS["manifest_bytes"]))
    require(wire["snapshot_body_sha256"] == snapshot.binding["sha256"] and manifest == local_manifest,
        "UNCHANGED_APPROVED_LOCAL_GRADING_MANIFEST")
    link = dict(schema_version=MULTIPART_VERSION+"-append-root-link", current_root_go_sha256=handoff["current_root_go_sha256"],
        epoch_sha256=handoff["epoch_sha256"], snapshot_sha256=snapshot.sha256,
        local_binding=deepcopy(snapshot.binding), native_binding=deepcopy(native_binding), native_parts_sha256=state.digest(wire["parts"]))
    require(set(link) == APPEND_ROOT_LINK_KEYS and len(store.canonical(link)) <= 16 << 10, "CLOSED_PRIVATE_APPEND_ROOT_LINK")
    return link


def _restore_parts(handoff, client, storage, output, root_binding, root_proof, budget, clock):
    raw = grade._read_owned(storage, root_binding, 8 << 20, raw=True)
    wire = grade._unpack(raw, grade.PARTITION_LIMITS["manifest_bytes"])
    manifest = _private_parts(handoff, wire)
    # The original native root restore already checked the draft immediately
    # before this cohort. One fresh native inventory authenticates all members;
    # each original manifest AND payload still gets its own metadata and byte GET.
    assets, _ = client.inventory(); inventory_sha = state.digest(assets); proofs = []
    def read(asset_id, name, size, sha):
        members = [a for a in assets if a["id"] == asset_id]
        require(len(members) == 1, "PRIVATE_GRADING_PART_NOT_IN_RUNTIME")
        client.asset(members[0], name, size, sha)
        metadata, api_sha = api_body(client, "/releases/assets/"+str(asset_id))
        client.asset(metadata, name, size, sha)
        status, _, body = client.request(client.allow(store.API+"/releases/assets/"+str(asset_id)),
            octet=True, download=True, cap=size)
        require(status == 200 and len(body) == size and store.sha(body) == sha, "EXACT_PRIVATE_GRADING_PART_NATIVE_BYTES")
        budget.check(client)
        return body, api_sha
    for part, record in zip(manifest["parts"], wire["parts"]):
        started = state.utc(clock()).isoformat(); descriptor = record["descriptor"]; entry = descriptor["entry"]
        encoded, manifest_api_sha = read(descriptor["manifest_asset_id"], "manifest-"+descriptor["manifest_sha256"]+".json",
            descriptor["manifest_bytes"], descriptor["manifest_sha256"])
        require(encoded == store.canonical(entry), "EXACT_NATIVE_GRADING_PART_MANIFEST")
        storage.write_bytes(output/f"PART_{part['index']:02d}_NATIVE_MANIFEST.json", encoded)
        body, payload_api_sha = read(entry["payload_asset_id"], entry["payload_name"], part["bytes"], part["sha256"])
        storage.write_bytes(output/part["name"], body); del body
        proof = dict(schema_version=MULTIPART_VERSION+"-part-native-read", index=part["index"],
            descriptor_sha256=state.digest(descriptor), root_native_proof_sha256=state.digest(root_proof),
            root_body_sha256=handoff["body_sha256"], payload_sha256=part["sha256"], bytes=part["bytes"],
            reader=cp.client_identity(client), inventory_canonical_sha256=inventory_sha,
            manifest_api_sha256=manifest_api_sha, payload_api_sha256=payload_api_sha,
            started_at_utc=started, completed_at_utc=state.utc(clock()).isoformat(),
            HTTP_calls=client.calls, transfer_bytes=client.transferred)
        storage.write_bytes(output/f"PART_{part['index']:02d}_NATIVE_READ.json", store.canonical(proof))
        proofs.append(proof)
    client.draft(); budget.check(client)
    return dict(schema_version=MULTIPART_VERSION+"-complete-part-read", parts=proofs,
        completed_at_utc=state.utc(clock()).isoformat(), HTTP_calls=client.calls, transfer_bytes=client.transferred)


@grade._scanned_storage
def restore_parts(handoff, client, *, storage, root_binding, native_root_proof, authenticate, clock=grade.now):
    """Historical-reader interface after its genuine native root GET.

    Authenticate the current Root/source/API through the live callback. Return
    private actual part receipts only; grade.restore_snapshot and the original
    historical durability proof remain separate caller obligations.
    """
    budget = Budget(); safe_handoff(handoff)
    require(isinstance(client, archive.Client) and client.readonly is True and client.operation == "restore"
        and client.source_sha == handoff["producer"]["source_sha"]
        and state.digest(client.binding) == handoff["runtime_binding_sha256"]
        and root_binding["sha256"] == handoff["body_sha256"] and root_binding["bytes"] == handoff["body_bytes"],
        "SAME_SOURCE_GET_ONLY_PRIVATE_GRADING_PART_READER")
    _own_restore(client, native_root_proof, clock())
    require(native_root_proof["payload_sha256"] == handoff["body_sha256"]
        and native_root_proof["bytes"] == handoff["body_bytes"]
        and native_root_proof["exact_readback"] is native_root_proof["separate_process"] is native_root_proof["draft_before_after"] is True,
        "EXACT_ORIGINAL_NATIVE_GRADING_ROOT_RECEIPT")
    reader = archive.checked(client, client.job["job_id"])
    require(reader["process_identity"] == native_root_proof["process_identity"] and reader["api_job_id"] == native_root_proof["job"]["api_job_id"],
        "ORIGINAL_CURRENT_ROOT_READER_UNCHANGED")
    _authenticate(authenticate, "CHECKPOINT_RESTORE_PRIVATE_PARTS", dict(handoff_sha256=state.digest(handoff),
        restored_binding=root_binding, native_root_proof_sha256=state.digest(native_root_proof), reader=reader), clock())
    return _restore_parts(handoff, client, storage, Path(root_binding["path"]).parent, root_binding, native_root_proof, budget, clock)


@grade._scanned_storage
def append(snapshot, client, package, *, storage, output, current_root_go_sha256, authenticate,
           pending_census, clock=grade.now):
    """Snapshot append only; private durability stays UNQUALIFIED until restore."""
    budget = Budget()
    require(type(snapshot) is grade.Snapshot and hashed(current_root_go_sha256) and type(package) is dict,
            "LIVE_LOCAL_SNAPSHOT_AND_CURRENT_ROOT_REQUIRED")
    snapshot.verify()
    producer, job, _, evidence = current(client, "writer", package, pending_census, budget)
    authenticate_inputs = _binding_context(current_root_go_sha256, package, snapshot.sha256, snapshot.binding["sha256"])
    authenticate_inputs.update(producer=producer, api_evidence=evidence)
    _authenticate(authenticate, "CHECKPOINT_APPEND_CURRENT_ROOT", authenticate_inputs, clock())
    body = grade._read_owned(storage, snapshot.binding, 8 << 20, raw=True)
    wire = grade._unpack(body, 64 << 20)
    multipart = type(wire) is dict and wire.get("schema_version") == grade.SNAPSHOT_WIRE_V2
    version = MULTIPART_VERSION if multipart else VERSION
    doc = grade._load_snapshot(storage, snapshot.binding) if multipart else wire
    require(doc == snapshot.document and grade._digest(doc) == snapshot.sha256 and set(doc) == grade.SNAPSHOT_KEYS
            and doc["schema_version"] == grade.VERSION + "-snapshot"
            and hashed(doc["epoch_sha256"]) and doc["local_only"] is True
            and doc["metadata_remote_durability_qualified"] is doc["successful_forecast"] is doc["public_release"] is doc["scientific_qualification"] is False
            and type(doc["fits"]) is int and type(doc["searches"]) is int and doc["fits"] == doc["searches"] == 0
            and state.utc(job["started_at"]) <= state.utc(doc["actual_completed_at"]) <= state.utc(clock()),
            "EXACT_CURRENT_JOB_LOCAL_GRADING_SNAPSHOT_BYTES")
    if not multipart: wire = None
    # All full-document checks above remain. Keep only immutable scalar fields
    # needed for the handoff while the native append holds its body buffers.
    snapshot_code_pins = doc["code_pins"]
    doc = {key:doc[key] for key in ("epoch_sha256", "actual_completed_at")}
    # Validate the exact current source before any intent/native POST, after
    # releasing the redundant decoded row graph. No source check is cached or
    # skipped; the immutable snapshot retains every original row and byte.
    require(snapshot_code_pins == grade.pins(), "EXACT_CURRENT_JOB_LOCAL_GRADING_SNAPSHOT_BYTES")
    output = output_root(storage, output, len(body) + (64 << 10))
    intent = dict(authenticate_inputs, schema_version=VERSION + "-append-intent", body_bytes=len(body),
        epoch_sha256=doc["epoch_sha256"], actual_started_at=state.utc(clock()).isoformat(), public_release=False, successful_forecast=False)
    storage.write_bytes(output / "APPEND_INTENT.json", store.canonical(intent))
    if multipart:
        body, descriptor = _append_parts(snapshot, wire, client, package, storage, output, producer,
            current_root_go_sha256, budget, clock)
    else:
        with storage.transaction():
            storage._check(Path(client.journal) / "checkpoint-reservation-probe")
            descriptor = store.append(client, body, cp.payload(body), package["qualification"])
    evidence["final"] = (recheck_v2 if multipart else recheck)(client, producer, job)
    budget.check(client)
    proof = dict(schema_version=version + "-native-append", current_root_go_sha256=current_root_go_sha256,
        producer=producer, epoch_sha256=doc["epoch_sha256"], snapshot_sha256=snapshot.sha256,
        body_sha256=store.sha(body), body_bytes=len(body), descriptor_sha256=state.digest(descriptor),
        qualification_sha256=state.digest(package["qualification"]), api_evidence_sha256=state.digest(evidence),
        started_at_utc=intent["actual_started_at"], completed_at_utc=state.utc(clock()).isoformat(),
        HTTP_calls=client.calls, transfer_bytes=client.transferred)
    handoff = dict(schema_version=version + "-handoff", repository=store.REPO, current_root_go_sha256=current_root_go_sha256,
        epoch_sha256=doc["epoch_sha256"], snapshot_sha256=snapshot.sha256, body_sha256=store.sha(body), body_bytes=len(body),
        snapshot_completed_at=doc["actual_completed_at"], producer=producer,
        runtime_binding_sha256=state.digest(client.binding), qualified_package_sha256=state.digest(package),
        grade_code_pins_sha256=state.digest(grade.pins()), helper_sha256=pins(), descriptor=descriptor,
        append_proof=proof, append_proof_sha256=state.digest(proof), successful_forecast=False, public_release=False, fits=0)
    raw = safe_handoff(handoff)
    final_scope = dict(handoff_sha256=store.sha(raw), handoff=handoff, api_evidence=evidence)
    if multipart:
        final_scope["root_link"] = append_root_link(snapshot, handoff, storage=storage,
            native_binding=cp.binding(output/"CHECKPOINT_ROOT.json.gz"))
    _authenticate(authenticate, "CHECKPOINT_APPEND_NATIVE_HANDOFF", final_scope, clock())
    storage.write_bytes(output / "HANDOFF.json", raw)
    budget.check(client)
    return handoff


class Restored:
    def __init__(self, durable, report, proof, key):
        require(key is _KEY and type(durable) is grade.DurableHistory, "LIVE_RESTORED_GRADING_HISTORY_REQUIRED")
        self.durable, self.report, self.proof = durable, deepcopy(report), deepcopy(proof)
        self._sha = state.digest(dict(report=self.report, proof=self.proof))
    def verify(self):
        self.durable.verify()
        require(self._sha == state.digest(dict(report=self.report, proof=self.proof)), "RESTORED_CHECKPOINT_RESULT_CHANGED")
        return self
    def __reduce__(self):
        raise CheckpointError("LIVE_GRADING_CHECKPOINT_RESULT_CANNOT_BE_SERIALIZED")


@grade._scanned_storage
def restore(handoff, client, package, registered, *, storage, output, current_root_go_sha256,
            authenticate, pending_census, clock=grade.now):
    """Exact fresh native readback, then unchanged typed grading durability API."""
    budget = Budget()
    raw_handoff = safe_handoff(handoff)
    require(type(registered) is epoch.RegisteredEpoch and hashed(current_root_go_sha256)
            and handoff["current_root_go_sha256"] == current_root_go_sha256
            and handoff["epoch_sha256"] == registered.epoch.sha256
            and handoff["qualified_package_sha256"] == state.digest(package)
            and handoff["runtime_binding_sha256"] == state.digest(package["binding"])
            and handoff["append_proof"]["qualification_sha256"] == state.digest(package["qualification"])
            and handoff["grade_code_pins_sha256"] == state.digest(grade.pins()), "EXACT_CURRENT_ROOT_EPOCH_PACKAGE_AND_CODE")
    registered.verify(state.utc(clock()))
    reader, reader_job, jobs, evidence = current(client, "reader", package, pending_census, budget)
    writer = handoff["producer"]
    require(all(writer[k] == reader[k] for k in ("run_id", "run_attempt", "source_sha", "workflow_ref"))
            and all(writer[k] != reader[k] for k in ("job_id", "api_job_id", "process_identity")),
            "DISTINCT_SAME_RUN_GRADING_EXPORT_READER_REQUIRED")
    original = archive.predecessor(client, writer, jobs)
    require(state.utc(original["started_at"]) <= state.utc(handoff["snapshot_completed_at"])
            <= state.utc(handoff["append_proof"]["started_at_utc"])
            <= state.utc(handoff["append_proof"]["completed_at_utc"])
            <= state.utc(original["completed_at"]) <= state.utc(reader_job["started_at"]),
            "GRADING_WRITER_COMPLETED_BEFORE_FRESH_READER_JOB")
    context = dict(current_root_go_sha256=current_root_go_sha256, handoff_sha256=store.sha(raw_handoff),
        handoff=handoff, reader=reader, api_evidence=evidence)
    _authenticate(authenticate, "CHECKPOINT_RESTORE_CURRENT_ROOT_AND_ORIGINAL_HANDOFF", context, clock())
    output = output_root(storage, output, 2 * handoff["body_bytes"] + (128 << 10))
    storage.write_bytes(output / "RESTORE_INTENT.json", store.canonical(context))
    with storage.transaction():
        storage._check(Path(client.journal) / "checkpoint-reservation-probe")
        native = store.restore(client, handoff["descriptor"], output / "NATIVE_READBACK.json.gz")
    _own_restore(client, native, clock())
    require(native["process_identity"] == reader["process_identity"] and native["run_id"] == reader["run_id"]
            and native["source_sha"] == reader["source_sha"] and native["job"]["api_job_id"] == reader["api_job_id"]
            and native["operation"] == "restore" and native["exact_readback"] is native["separate_process"] is native["draft_before_after"] is True
            and native["payload_sha256"] == handoff["body_sha256"] and native["bytes"] == handoff["body_bytes"],
            "ACTUAL_CURRENT_NATIVE_RESTORE_PROOF_REQUIRED")
    if handoff["schema_version"] == MULTIPART_VERSION+"-handoff":
        storage.import_file(output/"NATIVE_READBACK.json.gz", output/"GRADING_SNAPSHOT.json.gz", expected_sha256=handoff["body_sha256"])
        root_binding = cp.binding(output/"GRADING_SNAPSHOT.json.gz")
        context["multipart_readback"] = _restore_parts(handoff, client, storage, output, root_binding, native, budget, clock)
    return _finish_restore(handoff, client, registered, storage, output, authenticate, clock,
        native, reader, reader_job, context, budget)


def _finish_restore(handoff, client, registered, storage, output, authenticate, clock, native, reader, reader_job, context, budget):
    # safe_handoff already bounds this declared length by the original 8 MiB
    # cap. Keep the exact length/hash checks without reserving the whole cap.
    body = store.read_local(output / "NATIVE_READBACK.json.gz", handoff["body_bytes"])
    require(len(body) == handoff["body_bytes"] and store.sha(body) == handoff["body_sha256"], "EXACT_RESTORED_GRADING_BODY")
    del body
    if handoff["schema_version"] == VERSION+"-handoff":
        storage.import_file(output / "NATIVE_READBACK.json.gz", output / "GRADING_SNAPSHOT.json.gz", expected_sha256=handoff["body_sha256"])
    ref = cp.binding(output / "GRADING_SNAPSHOT.json.gz")
    multipart = handoff["schema_version"] == MULTIPART_VERSION+"-handoff"
    context["final_api_evidence"] = (recheck_v2 if multipart else recheck)(client, reader, reader_job)
    _authenticate(authenticate, "CHECKPOINT_NATIVE_RESTORED_BODY", dict(context,
        native_restore_proof=native, restored_binding=ref), clock())
    snapshot = grade.restore_snapshot(storage, ref, registered, authenticate=authenticate, at=clock())
    require(snapshot.sha256 == handoff["snapshot_sha256"] and snapshot.document["actual_completed_at"] == handoff["snapshot_completed_at"],
            "EXACT_ORIGINAL_RESTORED_GRADING_DOCUMENT")
    known = state.utc(clock()).isoformat()
    version = MULTIPART_VERSION if handoff["schema_version"] == MULTIPART_VERSION+"-handoff" else VERSION
    proof_body = dict(schema_version=version + "-fresh-reader-native-evidence", context=context,
        native_restore_proof=native, restored_binding=ref, known_by_at=known)
    storage.write_bytes(output / "FRESH_READER_NATIVE_PROOF.json", store.canonical(proof_body))
    proof = dict(schema_version=grade.VERSION + "-durability", snapshot_sha256=snapshot.sha256,
        restored_body_sha256=ref["sha256"], known_by_at=known, producer=handoff["producer"], reader=reader,
        proof_sha256=state.digest(proof_body))
    durable = grade.confirm_durable(snapshot, proof, registered=registered, authenticate=authenticate, at=clock())
    del snapshot
    report = grade.report(durable, registered, at=state.utc(clock()).isoformat())
    budget.check(client)
    return Restored(durable, report, proof, _KEY)


def _own_restore(client, proof, at):
    # Original store.check_proof validates a receipt FROM ANOTHER process and
    # deliberately rejects the issuing client. Keep the actual current receipt
    # unchanged; validate its own-process scope directly after store.restore.
    require(type(proof) is dict and set(proof) == store.BASE_PROOF_FIELDS | store.PHASE_FIELDS["restore"]
            and proof["schema_version"] == "weekly-private-proof-v2.1" and proof["phase"] == "restore"
            and proof["operation"] == "restore" and proof["repository"] == store.REPO
            and proof["run_id"] == client.run_id and type(proof["run_attempt"]) is int and proof["run_attempt"] == 1
            and proof["source_sha"] == client.source_sha and proof["process_identity"] == client.process
            and proof["job"] == client.job and proof["binding_sha256"] == state.digest(client.binding)
            and proof["config_sha256"] == store.config_sha() and proof["started_at_utc"] == client.started_at
            and state.utc(proof["started_at_utc"]) <= state.utc(proof["created_at_utc"]) <= state.utc(at)
            and type(proof["HTTP_calls"]) is int and proof["HTTP_calls"] == client.calls
            and type(proof["transfer_bytes"]) is int and proof["transfer_bytes"] == client.transferred,
            "CLOSED_UNCHANGED_CURRENT_NATIVE_RESTORE_RECEIPT")


def contract():
    return dict(schema_version=VERSION + "-contract", state="PARENT_WIRING_REQUIRED", jobs=JOBS, limits=LIMITS,
        helper_sha256=pins(), grade_code_pins=grade.pins(), local_append_is_durable=False,
        requires_prevalue_population=True, capture5_without_population_is_primary_grade_candidate=False,
        multipart_wire_version=MULTIPART_VERSION, multipart_limits=grade.PARTITION_LIMITS,
        multipart_part_locators="PRIVATE_ROOT_ONLY", multipart_requires_all_native_parts=True,
        fits=0, public_release=False, successful_forecast=False)
