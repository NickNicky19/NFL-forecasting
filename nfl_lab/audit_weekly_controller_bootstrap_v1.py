"""Fixed-path, live owner registration bootstrap for the frozen controller.

No ROOT field, environment digest, or serialized proof is a trust anchor.
The fixed lab-state record must be a create-only file. Its SAFE_SEAL is the
EXACT public-safe ZIP uploaded by the completed owner registration reader job:
GitHub's artifact metadata digest, not a claimed JSON digest, authenticates it.
The ZIP must be retained before artifact expiry. No artifact/private download
or provider route is used here. Failed/expired/missing metadata fails closed.

Parent wiring is deliberately separate: implement the genuine one-create
private writer, fresh reader and sealer in the THREE existing jobs before
publishing the fixed record. The sealer must build SAFE_SEAL from native store receipts,
never CLI JSON flags. This module does not implement those private operations,
enqueue, activate a schedule, or authorize publication/fits.

ABI: authorize_child(env, source_root, root_bytes) -> controller.Proof.
authorize_parent returns a live Parent with .proof, .registration_bytes and
.template_descriptor for the parent's private-template fetch/build operation.
The root template is private, <=60 KiB, not the old scheduler's 16-KiB inline
registration. Its hash/descriptor is public; full ROOT must never enter seal.

The two verification stages share 32 GET attempts /180s/120CPU/512MiB, with
real per-request timeouts. Bootstrap uses 10 GETs, frozen child uses 20. This is
an explicit NEW wrapper budget, NOT the frozen controller's 20-call contract.
The caller must retain a native hard envelope; cooperative limits cannot stop
an arbitrary injected callback. Native schedule remains schedule, not dispatch.

Explicit registry_version=2 selects a DIFFERENT fixed create-only registry and
SAFE_SEAL schema. Its owner-cleared locator registration contains only native
template IDs/binding/hashes and the closed archived qualification metadata. The
final sealer's actual registration clock follows the original writer/reader;
the original owner ROOT and native proof hashes are preserved separately. The
unchanged template.ParentGETClient owns every actual private read. No old V1
registration is upgraded, rewritten or implicitly accepted as V2.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import io
from pathlib import Path
import resource
import struct
import time
import zlib
from urllib.request import Request, HTTPRedirectHandler, build_opener
import zipfile

from . import audit_weekly_controller_v1 as c

VERSION = "audit-weekly-controller-bootstrap-v1"
LOCATOR_VERSION = "audit-weekly-controller-bootstrap-v2"
MODULE = "nfl_lab/audit_weekly_controller_bootstrap_v1.py"
TOOL = "tools/audit_weekly_controller_bootstrap_v1.py"
TEST = "tests/test_audit_weekly_controller_bootstrap_v1.py"
REGISTRY_PATH = "state/controller-v1/bootstrap-v1.json"
# The first V2 wire registration remains immutable at bootstrap-v2.json.
# Discovery's issued registration also remains immutable. The retained-epoch
# correction requires a separate native registration on its actual source.
LOCATOR_REGISTRY_PATH = "state/controller-v1/bootstrap-v2-20261026-retained-epoch.json"
LOCATOR_CAP = 64 << 10
TEMPLATE_MODULE = "nfl_lab/audit_weekly_template_v1.py"
# Shared executable bytes are checked in BOTH literal source inventories.
# state.py is deliberately role-local: the metadata ABI uses only its reviewed
# canonical/digest/utc functions, without replacing Main's forecast validators.
SHARED_EXECUTABLE_PINS = frozenset({MODULE, TOOL, TEST, c.MODULE, c.TOOL, TEMPLATE_MODULE,
    "nfl_lab/audit_weekly_grade_history_v1.py", "nfl_lab/private_draft_store.py",
    "nfl_lab/private_draft_probe_helpers.py", "nfl_lab/owner_private_bootstrap.py",
    "nfl_lab/owner_bootstrap_bundle.py", "nfl_lab/operational_storage.py",
    "nfl_lab/owned_reference_batch.py",
    "nfl_lab/weekly_durable_acceptance.py", "nfl_lab/cadence.py",
    "tools/private_draft_store_v2.py", "tools/audit_process_guard_v1.py",
    "config/private-draft-storage-v2.json", "config/operational-source-policy-v2.json",
    "requirements-audit-weekly-metadata-v1.lock"})
PARENT_EXECUTABLE_PINS = SHARED_EXECUTABLE_PINS | {
    "nfl_lab/audit_weekly_parent_v1.py", "tools/audit_weekly_parent_v1.py",
    "tests/test_audit_weekly_parent_v1.py", "tests/test_audit_weekly_parent_workflow_v1.py",
    "tests/test_cadence.py",
    "nfl_lab/state.py", c.WORKFLOW}
STATE_REF = "lab-state"
JOBS = dict(write="audit-weekly-produce-v1", read="audit-weekly-restore-v1", seal="audit-weekly-export-v1")
LIMITS = dict(HTTP_calls=32, wall_seconds=180, CPU_seconds=120, RSS_bytes=512 << 20,
              response_bytes=1 << 20, record_bytes=256 << 10, ZIP_bytes=96 << 10,
              safe_seal_bytes=64 << 10, root_bytes=60 << 10, request_timeout_seconds=10,
              retries=0, POSTs=0, fits=0, private_reads=0)
PUBLIC_KEYS = {"schema_version", "repository", "registration_base64", "native_artifact_zip_base64", "artifact_id"}
SAFE_KEYS = {"schema_version", "repository", "run_id", "source_sha", "branch", "workflow_sha256",
             "code_pins_sha256", "registration_sha256", "registered_at_utc", "template_descriptor",
             "writer", "reader", "sealer", "static_public_policy_sha256", "created_at_utc", "public_root", "fits"}
NATIVE_KEYS = {"job_id", "api_job_id", "process_identity", "started_at_utc", "completed_at_utc",
               "receipt_sha256", "template_sha256", "template_bytes", "private_descriptor_sha256",
               "storage_binding_sha256", "operation", "successful_private_creates"}
DESCRIPTOR_KEYS = {"schema_version", "template_sha256", "template_bytes", "private_descriptor_sha256", "storage_binding_sha256"}
SEALER_KEYS = {"job_id", "api_job_id", "process_identity", "started_at_utc", "completed_at_utc"}
LOCATOR_KEYS = {"schema_version", "repository", "registered_at_utc", "owner_root_go_sha256",
    "owner_root_issued_at_utc", "template_seal", "qualified_runtime_package"}
PACKAGE_KEYS = {"schema_version", "run_id", "source_sha", "runtime_id", "binding", "qualification",
                "quota_reservation", "runtime_reserved_bytes"}
PACKAGE_FULL_KEYS = PACKAGE_KEYS | {"root_go_sha256", "private_payload_bytes", "private_durability_qualified", "strict_v1_unchanged"}
QUOTA_KEYS = {"schema_version", "global_cap_bytes", "reserved_before_bytes", "new_runtime_reserved_bytes",
    "reserved_after_bytes", "existing_draft_runtimes", "pending_unlocated_runtimes", "pending_records",
    "charged_existing_bytes", "charged_existing_assets", "inventory_sha256", "pending_census_sha256",
    "new_runtime_id", "old_assets_deleted", "metadata_only"}
_KEY = object()


class BootstrapError(c.ControllerError):
    """Fixed public-safe codes; no response, private ROOT or token interpolation."""


def require(value, code):
    if not value:
        raise BootstrapError(code)


def closed(body, keys, schema, cap):
    require(type(body) is bytes and 0 < len(body) <= cap, "BOUNDED_BOOTSTRAP_METADATA")
    value = c.decode(body)
    require(type(value) is dict and set(value) == keys and body == c.canonical(value)
            and value["schema_version"] == schema, "CLOSED_CANONICAL_BOOTSTRAP_METADATA")
    return value


def unbase(value, cap):
    require(type(value) is str and 0 < len(value) <= 2 * cap, "BOUNDED_BOOTSTRAP_BASE64")
    try:
        body = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise BootstrapError("INVALID_BOOTSTRAP_BASE64") from None
    require(0 < len(body) <= cap and base64.b64encode(body).decode() == value, "EXACT_BOOTSTRAP_BASE64")
    return body


def _registry(registry_version):
    require(type(registry_version) is int and registry_version in {1, 2}, "EXPLICIT_BOOTSTRAP_REGISTRY_VERSION_REQUIRED")
    if registry_version == 1:
        return VERSION, REGISTRY_PATH, PUBLIC_KEYS, SAFE_KEYS
    return LOCATOR_VERSION, LOCATOR_REGISTRY_PATH, PUBLIC_KEYS | {"locator_registration"}, SAFE_KEYS | {
        "locator_registration_sha256", "owner_root_go_sha256", "owner_root_issued_at_utc"}


def template_descriptor(value, *, registry_version=1):
    version, _, _, _ = _registry(registry_version)
    require(type(value) is dict and set(value) == DESCRIPTOR_KEYS
            and value["schema_version"] == version + "-private-template-descriptor"
            and all(c.hashed(value[k]) for k in ("template_sha256", "private_descriptor_sha256", "storage_binding_sha256"))
            and type(value["template_bytes"]) is int and 0 < value["template_bytes"] <= (LIMITS["root_bytes"] if registry_version == 1 else 128 << 10),
            "CLOSED_PRIVATE_TEMPLATE_DESCRIPTOR")
    return value


def safe_seal(packed, *, registry_version=1):
    version, _, _, safe_keys = _registry(registry_version)
    require(type(packed) is bytes and 0 < len(packed) <= LIMITS["ZIP_bytes"], "BOUNDED_NATIVE_SAFE_SEAL_ZIP")
    try:
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            files = archive.infolist()
            require(len(files) == 1 and not archive.comment, "ONE_PUBLIC_SAFE_SEAL_FILE_ONLY")
            entry = files[0]
            require(entry.filename == "SAFE_SEAL.json" and not entry.is_dir()
                    and entry.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    and not entry.flag_bits & 1 and 0 < entry.file_size <= LIMITS["safe_seal_bytes"]
                    and entry.compress_size <= LIMITS["ZIP_bytes"] and not entry.comment and not entry.extra,
                    "BOUNDED_PUBLIC_SAFE_SEAL_ENTRY")
            # zipfile permits prepended/appended opaque bytes and local-header
            # extras. Public SAFE_SEAL cannot carry an uninspected raw corpus.
            name = b"SAFE_SEAL.json"
            require(entry.header_offset == 0 and packed[:4] == b"PK\x03\x04" and len(packed) >= 30,
                    "NO_OPAQUE_SAFE_SEAL_ZIP_PREFIX")
            local = struct.unpack_from("<4s5H3I2H", packed)
            require(local[-2:] == (len(name), 0) and packed[30:30 + len(name)] == name
                    and local[2] == entry.flag_bits and local[3] == entry.compress_type,
                    "NO_OPAQUE_LOCAL_SAFE_SEAL_EXTRA")
            end = 30 + len(name) + entry.compress_size
            if entry.flag_bits & 8:
                require(packed[end:end + 4] == b"PK\x07\x08"
                        and packed[end + 4:end + 16] == struct.pack("<3I", entry.CRC, entry.compress_size, entry.file_size),
                        "EXACT_SAFE_SEAL_DATA_DESCRIPTOR")
                end += 16
            require(archive.start_dir == end and packed[end:end + 4] == b"PK\x01\x02"
                    and packed[end + 46:end + 46 + len(name)] == name, "NO_OPAQUE_SAFE_SEAL_ZIP_GAPS")
            end += 46 + len(name)
            require(len(packed) == end + 22 and packed[end:end + 4] == b"PK\x05\x06"
                    and struct.unpack_from("<4H2IH", packed, end + 4)
                    == (0, 0, 1, 1, 46 + len(name), archive.start_dir, 0),
                    "NO_OPAQUE_SAFE_SEAL_ZIP_SUFFIX_OR_EXTRA")
            with archive.open(entry) as source:
                body = source.read(LIMITS["safe_seal_bytes"] + 1)
            require(len(body) == entry.file_size, "EXACT_NATIVE_SAFE_SEAL_SIZE")
    except (zipfile.BadZipFile, OSError, RuntimeError, EOFError, NotImplementedError, zlib.error):
        raise BootstrapError("INVALID_NATIVE_SAFE_SEAL_ZIP") from None
    return closed(body, safe_keys, version + "-native-safe-seal", LIMITS["safe_seal_bytes"])


def history_url(*, registry_version=1):
    _, path, _, _ = _registry(registry_version)
    return c.API + "/commits?sha=" + STATE_REF + "&path=" + path + "&per_page=2&page=1"


def fixed_route(url):
    if c.fixed_route(url):
        return True
    if url in {history_url(), history_url(registry_version=2)}:
        return True
    if type(url) is not str or not url.startswith(c.API + "/"):
        return False
    import re
    tail = url[len(c.API) + 1:]
    return any(re.fullmatch(pattern, tail) is not None for pattern in (
        r"contents/state/controller-v1/bootstrap-v[12]\.json\?ref=[a-f0-9]{40}",
        r"contents/state/controller-v1/bootstrap-v2-20261026-discovery\.json\?ref=[a-f0-9]{40}",
        r"contents/state/controller-v1/bootstrap-v2-20261026-retained-epoch\.json\?ref=[a-f0-9]{40}",
        r"actions/artifacts/[1-9][0-9]{0,19}"))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise BootstrapError("BOOTSTRAP_REDIRECT_FORBIDDEN")


class Metadata:
    """One live GET-only budget across bootstrap and the frozen controller."""
    def __init__(self, env, callback=None):
        require(callback is None or callable(callback), "LIVE_METADATA_CALLBACK_REQUIRED")
        self._env, self._callback = env, callback
        self.started, self.cpu = time.monotonic(), time.process_time()
        self.calls = []

    def budget(self):
        remaining = LIMITS["wall_seconds"] - (time.monotonic() - self.started)
        require(remaining > 0 and time.process_time() - self.cpu <= LIMITS["CPU_seconds"]
                and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= LIMITS["RSS_bytes"],
                "BOOTSTRAP_SHARED_NATIVE_BUDGET")
        return remaining

    def __call__(self, url, cap):
        remaining = self.budget()
        require(fixed_route(url) and type(cap) is int and 0 < cap <= LIMITS["response_bytes"]
                and len(self.calls) < LIMITS["HTTP_calls"], "BOOTSTRAP_FIXED_GET_ROUTE_OR_SHARED_CAP")
        record = dict(url=url, state="ATTEMPTED")
        self.calls.append(record)
        if self._callback is not None:
            reply = self._callback(url, cap)
        else:
            token = self._env.get("GITHUB_TOKEN")
            require(type(token) is str and token.startswith("ghs_") and not any(x.isspace() for x in token),
                    "AUTOMATIC_ACTIONS_TOKEN_REQUIRED")
            request = Request(url, headers={"Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": VERSION}, method="GET")
            try:
                with build_opener(_NoRedirect()).open(request, timeout=min(10, remaining)) as response:
                    reply = c.Reply(response.status, response.read(cap + 1))
            except BootstrapError:
                raise
            except Exception:
                raise BootstrapError("BOOTSTRAP_METADATA_GET_FAILED") from None
        require(type(reply) is c.Reply and type(reply.status) is int and reply.status == 200
                and type(reply.body) is bytes and 0 < len(reply.body) <= cap,
                "ACTUAL_RAW_BOOTSTRAP_HTTP_BODY_REQUIRED")
        record.update(state="OBSERVED", status=200, bytes=len(reply.body), sha256=c.sha(reply.body))
        self.budget()
        return reply

    def get(self, url, cap=1 << 20):
        return c.decode(self(url, cap).body)


def _local_pins(spec, root):
    """Check the complete inventory belonging to this actual checkout."""
    for name, expected in spec["code_pins"].items():
        c.source_path(name)
        path = Path(root).absolute() / name
        require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file()
                and path.stat().st_size <= 2 << 20 and c.sha(path.read_bytes()) == expected,
                "ACTUAL_REGISTRATION_SOURCE_PIN_BYTES_REQUIRED")


def source_inventories(parent, producer, *, registry_version=2):
    """Bounded role-local inventories, with an explicit identical shared ABI."""
    required = SHARED_EXECUTABLE_PINS if registry_version == 2 else {MODULE, TOOL, TEST, c.MODULE, c.TOOL}
    for spec in (parent, producer):
        pins = spec["code_pins"]
        require(type(pins) is dict and required <= set(pins) and len(pins) <= 128
            and c.hashed(spec["source_sha"], 40) and c.hashed(spec["workflow_sha256"])
            and all(c.hashed(v) for v in pins.values()), "BOUNDED_ROLE_LOCAL_SOURCE_INVENTORY")
        for name in pins:
            c.source_path(name)
        if registry_version == 2:
            require(c.WORKFLOW in pins and pins[c.WORKFLOW] == spec["workflow_sha256"],
                "ROLE_LOCAL_WORKFLOW_PIN_REQUIRED")
    require(all(parent["code_pins"][name] == producer["code_pins"][name] for name in required),
        "BOOTSTRAP_AND_FROZEN_CONTROLLER_MUST_BE_SOURCE_PINNED")
    if registry_version == 2:
        require(PARENT_EXECUTABLE_PINS <= set(parent["code_pins"]), "COMPLETE_PARENT_EXECUTABLE_SOURCE_PINS")


def _native(native, descriptor, role):
    require(type(native) is dict and set(native) == NATIVE_KEYS
            and native["job_id"] == JOBS[role] and c.positive(native["api_job_id"])
            and c.hashed(native["process_identity"]) and c.hashed(native["receipt_sha256"])
            and all(native[k] == descriptor[k] for k in DESCRIPTOR_KEYS - {"schema_version"})
            and type(native["template_bytes"]) is int
            and native["operation"] == {"write": "CREATE_PRIVATE_TEMPLATE_ONCE", "read": "FRESH_PRIVATE_TEMPLATE_READ"}[role]
            and type(native["successful_private_creates"]) is int
            and native["successful_private_creates"] == (1 if role == "write" else 0)
            and c.utc(native["started_at_utc"]) <= c.utc(native["completed_at_utc"]),
            "CLOSED_NATIVE_TEMPLATE_WRITE_OR_FRESH_READ")


class Seal:
    def __init__(self, registration_bytes, descriptor, document, metadata, key, *, registry_version=1, locator_bytes=None):
        require(key is _KEY, "LIVE_BOOTSTRAP_REQUIRED")
        self.registration_bytes = registration_bytes
        self.registration_sha256 = c.sha(registration_bytes)
        self.template_descriptor = deepcopy(descriptor)
        self.document = deepcopy(document)
        self.metadata = metadata
        self.registry_version, self.locator_registration_bytes = registry_version, locator_bytes
        self._integrity = c.digest(self._state())

    def _state(self):
        _registry(self.registry_version)
        value = dict(registration_sha256=self.registration_sha256, template_descriptor=self.template_descriptor, document=self.document)
        if self.registry_version == 2:
            require(type(self.locator_registration_bytes) is bytes, "SEALED_LOCATOR_BYTES_REQUIRED")
            value.update(registry_version=2, locator_registration_sha256=c.sha(self.locator_registration_bytes))
        else:
            require(self.locator_registration_bytes is None, "NO_IMPLICIT_LOCATOR_UPGRADE")
        return value

    @property
    def locators(self):
        return verify_locator_registration(self, self.locator_registration_bytes)

    def verify(self):
        require(self.registration_sha256 == c.sha(self.registration_bytes)
                and self._integrity == c.digest(self._state()), "BOOTSTRAP_LIVE_SEAL_INTEGRITY")
        self.metadata.budget()
        return self

    def __reduce__(self):
        raise BootstrapError("LIVE_BOOTSTRAP_CANNOT_BE_SERIALIZED")


def load_seal(env, source_root, *, metadata_get=None, clock=c.now, read_head=c.git_head, registry_version=1):
    """Only fixed registry path; its bytes/SHA can never be supplied by ROOT."""
    version, registry_path, public_keys, _ = _registry(registry_version)
    history = history_url(registry_version=registry_version)
    api = Metadata(env, metadata_get)
    original = api.get(history, 64 << 10)
    require(type(original) is list and len(original) == 1 and type(original[0]) is dict
            and c.hashed(original[0].get("sha"), 40), "CREATE_ONLY_PUBLIC_BOOTSTRAP_HISTORY_REQUIRED")
    commit_sha = original[0]["sha"]
    commit = api.get(c.API + "/commits/" + commit_sha)
    require(type(commit) is dict and commit.get("sha") == commit_sha
            and type(commit.get("parents")) is list and len(commit["parents"]) == 1
            and c.hashed(commit["parents"][0].get("sha"), 40)
            and type(commit.get("files")) is list and len(commit["files"]) == 1
            and commit["files"][0].get("filename") == registry_path
            and commit["files"][0].get("status") == "added"
            and (c.actor(commit.get("committer"), c.OWNER) or c.actor(commit.get("committer"), c.BOT)),
            "ORIGINAL_ADDED_PUBLIC_BOOTSTRAP_COMMIT")
    raw = c.content(api, registry_path, commit_sha, cap=LIMITS["record_bytes"])
    require(c.blob_sha(raw) == commit["files"][0].get("sha"), "EXACT_PUBLIC_BOOTSTRAP_COMMIT_BLOB")
    record = closed(raw, public_keys, version + "-public-seal", LIMITS["record_bytes"])
    require(record["repository"] == c.REPO and c.positive(record["artifact_id"]), "FIXED_BOOTSTRAP_REPOSITORY_AND_ARTIFACT")
    reg_raw = unbase(record["registration_base64"], 128 << 10)
    p = c.registration(reg_raw, sealed_sha256=c.sha(reg_raw), at=clock())
    packed = unbase(record["native_artifact_zip_base64"], LIMITS["ZIP_bytes"])
    native = safe_seal(packed, registry_version=registry_version)
    spec = p["producer"]
    source_inventories(p["parent"], spec, registry_version=registry_version)
    current = p["parent"] if env.get("GITHUB_EVENT_NAME") == "schedule" or env.get("GITHUB_JOB") == p["parent"]["job_id"] else spec
    c.local_source(current, source_root, read_head)
    _local_pins(current if registry_version == 2 else spec, source_root)
    require(native["repository"] == c.REPO and c.run_id(native["run_id"])
            and native["source_sha"] == spec["source_sha"] and native["branch"] == spec["branch"]
            and native["workflow_sha256"] == spec["workflow_sha256"]
            and native["code_pins_sha256"] == c.digest(spec["code_pins"])
            and native["registration_sha256"] == c.sha(reg_raw)
            and native["registered_at_utc"] == p["registered_at_utc"]
            and native["public_root"] is False and type(native["fits"]) is int and native["fits"] == 0,
            "ACTUAL_SOURCE_BOUND_NATIVE_REGISTRATION_SEAL")
    descriptor = template_descriptor(native["template_descriptor"], registry_version=registry_version)
    for role in ("write", "read"):
        _native(native[{"write": "writer", "read": "reader"}[role]], descriptor, role)
    w, r = native["writer"], native["reader"]
    sealer = native["sealer"]
    require(type(sealer) is dict and set(sealer) == SEALER_KEYS and sealer["job_id"] == JOBS["seal"]
            and c.positive(sealer["api_job_id"]) and c.hashed(sealer["process_identity"])
            and c.hashed(native["static_public_policy_sha256"]), "NATIVE_THIRD_JOB_SEAL_AND_STATIC_POLICY_BINDING")
    original_issued = p["registered_at_utc"] if registry_version == 1 else native["owner_root_issued_at_utc"]
    require(w["process_identity"] != r["process_identity"] and w["api_job_id"] != r["api_job_id"]
            and len({w["process_identity"], r["process_identity"], sealer["process_identity"]}) == 3
            and len({w["api_job_id"], r["api_job_id"], sealer["api_job_id"]}) == 3
            and c.utc(original_issued) <= c.utc(w["started_at_utc"])
            <= c.utc(w["completed_at_utc"]) <= c.utc(r["started_at_utc"])
            <= c.utc(r["completed_at_utc"]) <= c.utc(sealer["started_at_utc"])
            <= c.utc(sealer["completed_at_utc"]) <= c.utc(native["created_at_utc"]) <= c.utc(clock()),
            "ORIGINAL_PRIVATE_CREATE_AND_DISTINCT_FRESH_READER_CLOCKS")
    if registry_version == 2:
        require(c.hashed(native["owner_root_go_sha256"]) and c.hashed(native["locator_registration_sha256"])
                and c.utc(sealer["started_at_utc"]) <= c.utc(p["registered_at_utc"]) <= c.utc(sealer["completed_at_utc"]),
                "ACTUAL_FINAL_SEALER_REGISTRATION_CLOCK_REQUIRED")
    identifier = native["run_id"]
    require(identifier != env.get("GITHUB_RUN_ID") and identifier != p["readiness"]["run_id"],
            "DISTINCT_OWNER_REGISTRATION_RUN_REQUIRED")
    run = c.checked_run(api.get(c.run_url(identifier)), identifier, spec, c.OWNER,
                        event="workflow_dispatch", status="completed")
    listing = api.get(c.jobs_url(identifier))
    actual = {role: c.job(listing, identifier, spec, JOBS[role], status="completed",
                         api_id=native[{"write": "writer", "read": "reader", "seal": "sealer"}[role]]["api_job_id"]) for role in JOBS}
    for role, field in (("write", "writer"), ("read", "reader"), ("seal", "sealer")):
        n, j = native[field], actual[role]
        require(c.utc(j["started_at"]) <= c.utc(n["started_at_utc"])
                <= c.utc(n["completed_at_utc"]) <= c.utc(j["completed_at"]), "NATIVE_TEMPLATE_RECEIPT_WITHIN_ACTUAL_JOB")
    require(c.utc(actual["write"]["completed_at"]) <= c.utc(actual["read"]["started_at"])
            and c.utc(actual["read"]["completed_at"]) <= c.utc(actual["seal"]["started_at"])
            and c.utc(native["created_at_utc"]) <= c.utc(actual["seal"]["completed_at"])
            <= c.utc(run["updated_at"]) <= c.utc(clock()), "COMPLETED_OWNER_REGISTRATION_CHAIN")
    wf_raw = c.content(api, c.WORKFLOW, spec["source_sha"], cap=256 << 10)
    require(c.sha(wf_raw) == spec["workflow_sha256"], "ACTUAL_OWNER_REGISTRATION_WORKFLOW_BYTES")
    import yaml
    wf = yaml.load(wf_raw, Loader=yaml.BaseLoader)
    require(type(wf) is dict and wf.get("concurrency") == {"group": c.GROUP, "cancel-in-progress": "false"}
            and type(wf.get("jobs")) is dict and all(name in wf["jobs"] for name in JOBS.values()),
            "REGISTERED_OWNER_JOBS_SHARE_EXISTING_LAB_GROUP")
    for role, required_job in (("read", JOBS["write"]), ("seal", JOBS["read"])):
        stage = wf["jobs"][JOBS[role]]
        needs = stage.get("needs") if type(stage) is dict else None
        require((type(needs) is str and needs == required_job)
                or (type(needs) is list and required_job in needs and all(x in JOBS.values() for x in needs)),
                "FRESH_TEMPLATE_READ_AND_SEAL_NEED_PREVIOUS_JOB")
    for name in JOBS.values():
        j = wf["jobs"][name]
        permission = j.get("permissions", wf.get("permissions")) if type(j) is dict else None
        require(type(j) is dict and j.get("name", name) == name and "concurrency" not in j
                and type(permission) is dict and permission.get("contents") == "write"
                and permission.get("actions") in {"read", "write"}, "ACTUAL_PRIVATE_TEMPLATE_JOB_PERMISSIONS")
    artifact = api.get(c.API + "/actions/artifacts/" + str(record["artifact_id"]))
    artifact_name = "controller-root-safe-seal-v" + str(registry_version) + "-" + identifier
    require(type(artifact) is dict and type(artifact.get("id")) is int and artifact["id"] == record["artifact_id"]
            and artifact.get("name") == artifact_name and artifact.get("expired") is False
            and artifact.get("digest") == "sha256:" + c.sha(packed)
            and type(artifact.get("size_in_bytes")) is int and artifact["size_in_bytes"] == len(packed)
            and type(artifact.get("workflow_run")) is dict
            and artifact["workflow_run"].get("id") == int(identifier)
            and artifact["workflow_run"].get("head_sha") == spec["source_sha"]
            and artifact["workflow_run"].get("head_repository_id") == artifact["workflow_run"].get("repository_id")
            and type(artifact["workflow_run"].get("repository_id")) is int,
            "GENUINE_OWNER_RUN_NATIVE_ARTIFACT_DIGEST_REQUIRED")
    require(c.utc(native["created_at_utc"]) <= c.utc(artifact["created_at"])
            <= c.utc(artifact["updated_at"]) <= c.utc(actual["seal"]["completed_at"]),
            "NATIVE_SEAL_UPLOAD_INSIDE_THIRD_JOB")
    c.stable(run, api.get(c.run_url(identifier)))
    after = api.get(c.jobs_url(identifier))
    for role in JOBS:
        fresh = c.job(after, identifier, spec, JOBS[role], status="completed", api_id=actual[role]["id"])
        require(all(fresh[k] == actual[role][k] for k in ("started_at", "completed_at")), "OWNER_REGISTRATION_JOB_CHANGED")
    require(api.get(history, 64 << 10) == original, "PUBLIC_BOOTSTRAP_CHANGED_DURING_VERIFICATION")
    locator_bytes = None
    if registry_version == 2:
        locator_bytes = c.canonical(record["locator_registration"])
        _validate_locator_registration(locator_bytes, native, p)
    document = dict(schema_version=version + "-verified", registry_path=registry_path, registry_commit_sha=commit_sha,
        registry_sha256=c.sha(raw), registration_sha256=c.sha(reg_raw), owner_registration_run_id=identifier,
        owner_registration_source_sha=spec["source_sha"], owner_registration_completed_at=run["updated_at"],
        template_descriptor=deepcopy(descriptor), static_public_policy_sha256=native["static_public_policy_sha256"],
        artifact_id=record["artifact_id"], artifact_sha256=c.sha(packed),
        scope="LIVE_COMPLETED_OWNER_REGISTRATION_NOT_CAPTURE_OR_PUBLICATION", activation_authorized=False,
        fits=0, private_reads=0, metadata_GETs=deepcopy(api.calls))
    if registry_version == 2:
        document.update(locator_registration_sha256=c.sha(locator_bytes),
            template_seal_sha256=c.digest(record["locator_registration"]["template_seal"]),
            qualified_runtime_package_sha256=c.digest(record["locator_registration"]["qualified_runtime_package"]),
            owner_root_go_sha256=native["owner_root_go_sha256"], original_owner_root_issued_at_utc=original_issued,
            locator_registered_at_utc=p["registered_at_utc"])
    return Seal(reg_raw, descriptor, document, api, _KEY, registry_version=registry_version, locator_bytes=locator_bytes)


def _event(env, event_bytes):
    if event_bytes is not None:
        require(type(event_bytes) is bytes and len(event_bytes) <= 256 << 10, "BOUNDED_ACTUAL_EVENT_BYTES")
        return event_bytes
    path = Path(env.get("GITHUB_EVENT_PATH", ""))
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file()
            and path.stat().st_size <= 256 << 10, "ACTUAL_GHA_EVENT_FILE_REQUIRED")
    with path.open("rb") as source:
        body = source.read((256 << 10) + 1)
    require(len(body) <= 256 << 10, "BOUNDED_ACTUAL_GHA_EVENT_FILE")
    return body


def _environment(env):
    # No environment enumeration or private credential publication.
    names = ("GITHUB_ACTIONS", "CI", "GITHUB_REPOSITORY", "GITHUB_RUN_ATTEMPT", "GITHUB_RUN_ID",
        "GITHUB_EVENT_NAME", "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_JOB",
        "GITHUB_ACTOR", "GITHUB_ACTOR_ID", "STORE_PERMISSION", "AUDIT_WEEKLY_ROOT_GO_JSON", "AUDIT_WEEKLY_ROOT_GO_SHA256")
    return {name: env.get(name) for name in names}


def authorize_child(env, source_root, root_bytes, *, metadata_get=None, event_bytes=None, clock=c.now, read_head=c.git_head, registry_version=1):
    _recurring(root_bytes, bot=True)
    seal = load_seal(env, source_root, metadata_get=metadata_get, clock=clock, read_head=read_head, registry_version=registry_version).verify()
    proof = c.verify_child(seal.registration_bytes, sealed_sha256=seal.registration_sha256, root_bytes=root_bytes,
        event_bytes=_event(env, event_bytes), env=_environment(env), source_root=source_root,
        metadata_get=seal.metadata, clock=clock, read_head=read_head)
    scheduled = c.decode(root_bytes)["effective_epoch"]["controller_context"]["scheduled_parent"]
    require(c.utc(seal.document["owner_registration_completed_at"]) <= c.utc(scheduled["job_started_at"]),
            "OWNER_REGISTRATION_MUST_COMPLETE_BEFORE_SCHEDULED_PARENT")
    seal.metadata.budget()
    proof.bootstrap_seal = seal
    return proof


class Parent:
    def __init__(self, proof, seal, key):
        require(key is _KEY and type(proof) is c.Proof, "LIVE_PARENT_BOOTSTRAP_REQUIRED")
        self.proof, self.seal = proof, seal
        self.registration_bytes = seal.registration_bytes
        self.template_descriptor = deepcopy(seal.template_descriptor)

    @property
    def locators(self):
        return self.seal.locators

    def __reduce__(self):
        raise BootstrapError("LIVE_PARENT_BOOTSTRAP_CANNOT_BE_SERIALIZED")


def authorize_parent(env, source_root, *, metadata_get=None, event_bytes=None, clock=c.now, read_head=c.git_head, registry_version=1):
    seal = load_seal(env, source_root, metadata_get=metadata_get, clock=clock, read_head=read_head, registry_version=registry_version).verify()
    proof = c.verify_parent(seal.registration_bytes, sealed_sha256=seal.registration_sha256,
        event_bytes=_event(env, event_bytes), env=_environment(env), source_root=source_root,
        metadata_get=seal.metadata, clock=clock, read_head=read_head)
    require(c.utc(seal.document["owner_registration_completed_at"])
            <= c.utc(proof.document["scheduled_parent"]["job_started_at"]),
            "OWNER_REGISTRATION_MUST_COMPLETE_BEFORE_SCHEDULED_PARENT")
    seal.metadata.budget()
    return Parent(proof, seal, _KEY)


def authorize_client(proof, client, env, root_bytes):
    """Scope additive BOT acceptance to this already-authenticated current client.

    Call client.authenticate_actions_job() first. Original historical Nick
    qualification and original receipts must use their unchanged old verifier.
    No proof can authorize another run/job/source, a JSON copy, or ROOT digest.
    """
    require(type(proof) is c.Proof and type(root_bytes) is bytes, "LIVE_CURRENT_CONTROLLER_PROOF_REQUIRED")
    proof.verify(registration_sha256=proof.document["registration_sha256"], run_id=env.get("GITHUB_RUN_ID"),
                 job_id=env.get("GITHUB_JOB"), root_sha256=c.sha(root_bytes))
    d, j = proof.document, client.job
    require(d.get("schema_version") == c.VERSION + "-current-child-proof" and d.get("actor") == c.BOT
            and client.run_id == d["run_id"] and client.source_sha == d["source_sha"] == env.get("GITHUB_SHA")
            and type(j) is dict and j.get("api_job_id") == d["api_job_id"] and type(j.get("api_job_id")) is int
            and j.get("job_id") == d["job_id"] and j.get("execution_lane") == "github_actions"
            and j.get("run_authenticated") is True and j.get("event_name") == "workflow_dispatch"
            and j.get("workflow_sha") == d["source_sha"] and j.get("workflow_ref") == env.get("GITHUB_WORKFLOW_REF")
            and env.get("GITHUB_ACTOR") == c.BOT["login"] and env.get("GITHUB_ACTOR_ID") == str(c.BOT["id"]),
            "CONTROLLER_PROOF_CURRENT_CLIENT_SCOPE")
    return proof


def verify_private_template(seal, body, private_descriptor_bytes, storage_binding_bytes):
    """Pure exact-byte check AFTER a parent-owned authenticated fresh read.

    This proves byte binding only, never remote read authority or readiness.
    The parent must retain the actual native read receipt and then limit ROOT
    changes to explicitly registered dynamic fields before the once claim.
    """
    require(type(seal) is Seal, "LIVE_BOOTSTRAP_REQUIRED")
    seal.verify()
    d = seal.template_descriptor
    require(type(body) is bytes and len(body) == d["template_bytes"] and c.sha(body) == d["template_sha256"]
            and type(private_descriptor_bytes) is bytes and 0 < len(private_descriptor_bytes) <= 64 << 10
            and c.sha(private_descriptor_bytes) == d["private_descriptor_sha256"]
            and type(storage_binding_bytes) is bytes and 0 < len(storage_binding_bytes) <= 16 << 10
            and c.sha(storage_binding_bytes) == d["storage_binding_sha256"], "EXACT_PRIVATE_TEMPLATE_AND_DESCRIPTOR_BYTES")
    value = c.decode(body)
    if seal.registry_version == 2:
        from . import private_draft_store as store
        canonical_body = store.canonical(value)
    else:
        canonical_body = c.canonical(value)
    require(type(value) is dict and body == canonical_body, "CANONICAL_PRIVATE_ROOT_TEMPLATE")
    return value


def _recurring(root_bytes, *, bot):
    require(type(root_bytes) is bytes and 0 < len(root_bytes) <= LIMITS["root_bytes"], "BOUNDED_RECURRING_ROOT")
    root = c.decode(root_bytes)
    require(type(root) is dict and root_bytes == c.canonical(root) and root.get("operation") == "RECURRING_CAPTURE",
            "EXPLICIT_RECURRING_CAPTURE_ROOT_REQUIRED")
    epoch = root.get("effective_epoch")
    require(type(epoch) is dict and epoch.get("schema_version") in {"audit-weekly-recurring-v1-context","audit-weekly-recurring-v2-context","audit-weekly-recurring-v3-context","audit-weekly-recurring-v4-context"}
            and (type(epoch.get("controller_context")) is dict if bot else epoch.get("controller_context") is None)
            and type(epoch.get("previous_capture")) is dict
            and set(epoch["previous_capture"]) == {"feed_sha256", "receipt_sha256"}
            and all(c.hashed(v) for v in epoch["previous_capture"].values()), "RECURRING_CONTEXT_AND_PRIOR_CAPTURE_LOCATOR")
    if epoch["schema_version"] in {"audit-weekly-recurring-v2-context", "audit-weekly-recurring-v3-context","audit-weekly-recurring-v4-context"}:
        locator=epoch.get("previous_checkpoint")
        modern=epoch["schema_version"]=="audit-weekly-recurring-v4-context"
        reference=modern and type(locator) is dict and locator.get("schema_version") is not None
        if reference:
            from .audit_weekly_grade_history_v1 import locator_reference
            locator_reference(locator)
        require(set(epoch)=={"schema_version","controller_context","previous_capture","previous_checkpoint"}
                | ({"plan"} if epoch["schema_version"] in {"audit-weekly-recurring-v3-context","audit-weekly-recurring-v4-context"} else set())
            and (reference or locator is None or type(locator) is dict and set(locator)=={"sha256"} and c.hashed(locator["sha256"])),
            "RECURRING_V2_EXACT_PREVIOUS_GRADING_LOCATOR")
        if modern:
            from .audit_weekly_grade_history_v1 import validate_root_plan
            validate_root_plan(epoch["plan"])
        if epoch["schema_version"] == "audit-weekly-recurring-v3-context":
            plan = epoch["plan"]
            require(type(plan) is dict and set(plan) == {"kind", "season", "week"}
                and plan["kind"] in {"GRADE_ONLY", "FUTURE_CAPABLE"}
                and type(plan["season"]) is int and 2019 <= plan["season"] <= 2100
                and type(plan["week"]) is int and 1 <= plan["week"] <= 18, "CLOSED_RECURRING_ROOT_PLAN")
    # The caller still runs its FULL closed ROOT/epoch schema first. The wrapper
    # checks only its interface, not fields owned by the model/epoch runtime.
    return root


class Owner:
    """Separate manual Nick proof: never invent a parent/controller.Proof."""
    def __init__(self, document, seal, key):
        require(key is _KEY, "LIVE_OWNER_BOOTSTRAP_REQUIRED")
        self.document, self.bootstrap_seal = deepcopy(document), seal
        self.sha256 = c.digest(self.document)

    def verify(self, *, root_sha256):
        require(c.digest(self.document) == self.sha256 and self.document["root_go_sha256"] == root_sha256,
                "OWNER_BOOTSTRAP_SCOPE_OR_INTEGRITY")
        self.bootstrap_seal.verify()
        return self

    def __reduce__(self):
        raise BootstrapError("LIVE_OWNER_BOOTSTRAP_CANNOT_BE_SERIALIZED")


def authorize_owner(env, source_root, root_bytes, *, metadata_get=None, event_bytes=None, clock=c.now, read_head=c.git_head, registry_version=1):
    """Initial manual recurring smoke, exact sealed genuine prior COUNT capture.

    This narrow owner path accepts ONLY the prior receipt already sealed in the
    registration. Later manual advancement to another capture needs an explicit
    source-bound current-capture verifier; no arbitrary receipt flag is accepted.
    """
    root = _recurring(root_bytes, bot=False)
    seal = load_seal(env, source_root, metadata_get=metadata_get, clock=clock, read_head=read_head, registry_version=registry_version).verify()
    p = c.registration(seal.registration_bytes, sealed_sha256=seal.registration_sha256, at=clock())
    spec, api, identifier = p["producer"], seal.metadata, env.get("GITHUB_RUN_ID")
    job_id = env.get("GITHUB_JOB")
    require(job_id in spec["jobs"].values() and identifier not in {p["readiness"]["run_id"], seal.document["owner_registration_run_id"]},
            "DISTINCT_REGISTERED_OWNER_SMOKE_JOB")
    c.common_env(_environment(env), spec, job_id, c.OWNER, event="workflow_dispatch")
    require(env.get("STORE_PERMISSION") == "write" and env.get("AUDIT_WEEKLY_ROOT_GO_JSON") == root_bytes.decode()
            and env.get("AUDIT_WEEKLY_ROOT_GO_SHA256") == c.sha(root_bytes), "OWNER_SMOKE_EXACT_ROOT_ENV")
    event = c.decode(_event(env, event_bytes))
    require(type(event) is dict and event.get("repository", {}).get("full_name") == c.REPO
            and event.get("inputs", {}).get("mode") == c.MODE
            and event["inputs"].get("inference_builder_go_json") == root_bytes.decode()
            and event["inputs"].get("inference_builder_go_sha256") == c.sha(root_bytes), "GENUINE_OWNER_SMOKE_ROOT_EVENT")
    require(root.get("source_sha") == spec["source_sha"] and root.get("mode") == c.MODE
            and root.get("workflow_ref") == c.REPO + "/" + c.WORKFLOW + "@refs/heads/" + spec["branch"]
            and root.get("single_writer_group") == c.GROUP and root.get("code_pins") == spec["code_pins"]
            and root.get("jobs") == {k: spec["jobs"][k] for k in c.ROLES}
            and root.get("failure_restorer") == spec["jobs"]["evidence"], "UNCHANGED_OWNER_SMOKE_ROOT_SOURCE_AND_JOBS")
    require(root["effective_epoch"]["previous_capture"] == dict(
        feed_sha256=p["readiness"]["receipt_bindings"]["feed_sha256"], receipt_sha256=p["readiness"]["receipt_sha256"]),
        "OWNER_SMOKE_REQUIRES_EXACT_SEALED_QUALIFIED_PRIOR_CAPTURE")
    run = c.checked_run(api.get(c.run_url(identifier)), identifier, spec, c.OWNER, event="workflow_dispatch", status="in_progress")
    job = c.job(api.get(c.jobs_url(identifier)), identifier, spec, job_id, status="in_progress")
    require(c.utc(seal.document["owner_registration_completed_at"]) <= c.utc(job["started_at"])
            and c.utc(root["issued_at_utc"]) <= c.utc(job["started_at"]) <= c.utc(clock()) < c.utc(root["expires_at_utc"])
            and 0 < (c.utc(root["expires_at_utc"]) - c.utc(root["issued_at_utc"])).total_seconds() <= 3600,
            "FRESH_OWNER_SMOKE_ROOT_AND_ACTUAL_JOB_CLOCK")
    c.workflow(api, spec, job_id)
    old, ready = c.readiness(api, p, before=job["started_at"])
    c.check_head(api, p)
    c.stable(run, api.get(c.run_url(identifier)))
    c.stable(old, api.get(c.run_url(p["readiness"]["run_id"])))
    c.job(api.get(c.jobs_url(identifier)), identifier, spec, job_id, status="in_progress", api_id=job["id"])
    c.local_source(spec, source_root, read_head)
    require(c.utc(clock()) < c.utc(root["expires_at_utc"]), "OWNER_SMOKE_EXPIRED_DURING_VERIFICATION")
    return Owner(dict(schema_version=VERSION + "-manual-owner-proof", root_go_sha256=c.sha(root_bytes),
        registration_sha256=seal.registration_sha256, source_sha=spec["source_sha"], run_id=identifier,
        job_id=job_id, api_job_id=job["id"], actor=dict(c.OWNER), prior_capture=ready,
        scheduled_parent=None, activation_authorized=False, fits=0), seal, _KEY)


def authorize_policy(proof, root_bytes, policy_bytes):
    """Authenticate STATIC exact policy before accepting its earlier issue clock."""
    require(type(proof) in {c.Proof, Owner} and type(policy_bytes) is bytes and 0 < len(policy_bytes) <= 128 << 10
            and type(root_bytes) is bytes and 0 < len(root_bytes) <= LIMITS["root_bytes"], "LIVE_BOOTSTRAP_POLICY_PROOF_REQUIRED")
    if type(proof) is c.Proof:
        require(proof.document.get("schema_version") == c.VERSION + "-current-child-proof", "CURRENT_CHILD_POLICY_PROOF_REQUIRED")
        proof.verify(registration_sha256=proof.document["registration_sha256"], run_id=proof.document["run_id"],
            job_id=proof.document["job_id"], root_sha256=c.sha(root_bytes))
    else:
        proof.verify(root_sha256=c.sha(root_bytes))
    seal = getattr(proof, "bootstrap_seal", None)
    require(type(seal) is Seal, "EXTERNALLY_VERIFIED_BOOTSTRAP_POLICY_BINDING_REQUIRED")
    seal.verify()
    policy = c.decode(policy_bytes)
    root = c.decode(root_bytes)
    require(type(policy) is dict and policy_bytes == c.canonical(policy)
            and c.sha(policy_bytes) == seal.document["static_public_policy_sha256"]
            and type(root.get("publication_registration")) is dict
            and root["publication_registration"].get("policy_sha256") == c.sha(policy_bytes)
            and policy.get("source_sha") == root.get("source_sha")
            and c.utc(policy["registered_at_utc"]) <= c.utc(root["issued_at_utc"]),
            "EXACT_SEALED_STATIC_POLICY_BEFORE_FRESH_ROOT_ISSUE")
    return dict(policy_sha256=c.sha(policy_bytes), registered_at_utc=policy["registered_at_utc"],
        root_go_sha256=c.sha(root_bytes), scope="STATIC_POLICY_BYTES_ONLY_OLD_FULL_POLICY_CHECKS_STILL_REQUIRED")


def integration_contract():
    """Public-safe template/API only; no invented ready source/clock/artifact."""
    return dict(schema_version=VERSION + "-integration-contract", state="UNREGISTERED_PARENT_WIRING_REQUIRED",
        registry_path=REGISTRY_PATH, registry_ref=STATE_REF, registration_jobs=dict(JOBS), limits=dict(LIMITS),
        public_record_keys=sorted(PUBLIC_KEYS), native_SAFE_SEAL_keys=sorted(SAFE_KEYS),
        native_receipt_keys=sorted(NATIVE_KEYS), template_descriptor_keys=sorted(DESCRIPTOR_KEYS),
        native_sealer_keys=sorted(SEALER_KEYS),
        artifact_name="controller-root-safe-seal-v1-<actual-owner-registration-run-id>",
        artifact_file="SAFE_SEAL.json", actor=dict(c.OWNER), child_actor=dict(c.BOT),
        cadence=dict(c.CADENCE), concurrency=dict(c.CONCURRENCY), parent_return_rule=c.RETURN_RULE,
        blockers=["GENUINE_PRIVATE_TEMPLATE_CREATE_AND_FRESH_READER_NATIVE_ARTIFACT",
            "ROOT_16_KIB_INLINE_SCHEDULER_VS_60_KIB_PRIVATE_DESCRIPTOR_ADAPTER",
            "ROOT_EFFECTIVE_EPOCH_NONE_AND_CURRENT_RUN_NICK_GUARDS",
            "REGISTERED_STATIC_PUBLIC_POLICY_CLOCK_VS_NEW_ROOT_ISSUE_CLOCK",
            "SOURCE_PINNED_32_GET_WRAPPER_ENVELOPE",
            "ATOMIC_ONCE_CLAIM_ENQUEUE_EXIT_AND_NATIVE_SCHEDULE_ROUTE_BEFORE_OLD_GUARD_CHANGE"],
        activation_authorized=False, fits=0, POSTs=0)


def _qualified_locator_package(package, binding, *, before):
    """Closed archived metadata only; not fresh private-storage readiness.

    The parent still uses the original live qualification/canary and its private
    pending-census body checks. Publishing its HASH does not recreate that body.
    """
    from . import owner_private_bootstrap as owner, private_draft_store as store
    require(type(package) is dict and set(package) in (PACKAGE_KEYS, PACKAGE_FULL_KEYS)
            and package["schema_version"] == "audit-private-rotation-v1-qualified-runtime"
            and type(package["qualification"]) is dict
            and package["binding"] == binding and package["runtime_id"] == binding["runtime_id"]
            and package["run_id"] == binding["origin_run_id"] == package["qualification"].get("run_id")
            and package["source_sha"] == package["qualification"].get("source_sha") and c.hashed(package["source_sha"], 40)
            and type(package["runtime_reserved_bytes"]) is int and package["runtime_reserved_bytes"] == 32 << 20,
            "CLOSED_OWNER_CLEARED_QUALIFIED_RUNTIME_PACKAGE")
    owner.archived_qualification(binding, package["qualification"])
    q = package["qualification"]
    require(c.utc(q["created_at_utc"]) <= c.utc(before), "ORIGINAL_QUALIFICATION_PRECEDES_OWNER_ROOT")
    if set(package) == PACKAGE_FULL_KEYS:
        require(c.hashed(package["root_go_sha256"]) and type(package["private_payload_bytes"]) is int
                and package["private_payload_bytes"] == 0 and package["private_durability_qualified"] is False
                and package["strict_v1_unchanged"] == "INCONCLUSIVE", "ORIGINAL_QUALIFICATION_FLAGS_UNCHANGED")
    quota = package["quota_reservation"]
    counts = ("reserved_before_bytes", "reserved_after_bytes", "existing_draft_runtimes", "pending_unlocated_runtimes",
              "pending_records", "charged_existing_bytes", "charged_existing_assets")
    require(type(quota) is dict and set(quota) == QUOTA_KEYS
            and quota["schema_version"] == "audit-private-rotation-v1-quota-reservation"
            and type(quota["global_cap_bytes"]) is int and quota["global_cap_bytes"] == 512 << 20
            and type(quota["new_runtime_reserved_bytes"]) is int and quota["new_runtime_reserved_bytes"] == 32 << 20
            and quota["new_runtime_id"] == binding["runtime_id"] and type(quota["old_assets_deleted"]) is int
            and quota["old_assets_deleted"] == 0 and quota["metadata_only"] is True
            and all(type(quota[k]) is int and quota[k] >= 0 for k in counts)
            and 1 <= quota["existing_draft_runtimes"] <= 15
            and quota["reserved_before_bytes"] == (quota["existing_draft_runtimes"] + quota["pending_unlocated_runtimes"]) * (32 << 20)
            and quota["reserved_after_bytes"] == quota["reserved_before_bytes"] + (32 << 20) <= 512 << 20
            and quota["charged_existing_bytes"] <= quota["existing_draft_runtimes"] * (32 << 20)
            and quota["charged_existing_assets"] <= quota["existing_draft_runtimes"] * 128
            and c.hashed(quota["inventory_sha256"]) and c.hashed(quota["pending_census_sha256"]),
            "CLOSED_ORIGINAL_GLOBAL_RESERVATION_METADATA")
    return package


def _validate_locator_registration(body, native, registration):
    """No arbitrary URLs, files, credentials, encoded bodies or private rows."""
    from . import audit_weekly_template_v1 as template, private_draft_store as store
    loc = closed(body, LOCATOR_KEYS, LOCATOR_VERSION + "-locator-registration", LOCATOR_CAP)
    require(loc["repository"] == c.REPO and c.sha(body) == native["locator_registration_sha256"]
            and loc["registered_at_utc"] == registration["registered_at_utc"] == native["registered_at_utc"]
            and loc["owner_root_go_sha256"] == native["owner_root_go_sha256"]
            and loc["owner_root_issued_at_utc"] == native["owner_root_issued_at_utc"],
            "EXACT_FINAL_OWNER_CLEARED_LOCATOR_REGISTRATION")
    ts = template._handoff(loc["template_seal"], sealed=True)
    require(ts["root_go_sha256"] == loc["owner_root_go_sha256"] and ts["writer"]["run_id"] == native["run_id"]
            and ts["writer"]["source_sha"] == native["source_sha"] == registration["producer"]["source_sha"]
            and ts["writer"]["workflow_ref"] == c.REPO + "/" + c.WORKFLOW + "@refs/heads/" + registration["producer"]["branch"],
            "ORIGINAL_TEMPLATE_OWNER_ROOT_AND_LITERAL_SOURCE")
    for field in ("writer", "reader"):
        identity = ts[field]
        n = native[field]
        require(identity["job_id"] == n["job_id"] and identity["api_job_id"] == n["api_job_id"]
                and type(identity["api_job_id"]) is int and identity["process_identity"] == n["process_identity"],
                "EXACT_ORIGINAL_TEMPLATE_NATIVE_IDENTITIES")
    summary = native["template_descriptor"]
    require(summary["template_sha256"] == ts["template_sha256"] and summary["template_bytes"] == ts["template_bytes"]
            and summary["private_descriptor_sha256"] == store.sha(store.canonical(ts["descriptor"]))
            and summary["storage_binding_sha256"] == store.sha(store.canonical(ts["binding"])),
            "FULL_NATIVE_TEMPLATE_LOCATORS_MATCH_SEALED_SUMMARY")
    original_writer = {key: deepcopy(ts[key]) for key in template.HANDOFF_KEYS}
    original_writer["schema_version"] = template.VERSION + "-appended"
    require(native["writer"]["receipt_sha256"] == store.sha(store.canonical(original_writer))
            and native["reader"]["receipt_sha256"] == ts["reader_proof_sha256"]
            and c.utc(native["writer"]["started_at_utc"]) <= c.utc(ts["appended_at_utc"])
            <= c.utc(native["writer"]["completed_at_utc"])
            and c.utc(native["reader"]["started_at_utc"]) <= c.utc(ts["verified_at_utc"])
            <= c.utc(native["reader"]["completed_at_utc"]) <= c.utc(loc["registered_at_utc"]),
            "UNCHANGED_ORIGINAL_WRITER_AND_READER_PROOFS_BEFORE_FINAL_SEAL")
    _qualified_locator_package(loc["qualified_runtime_package"], ts["binding"], before=loc["owner_root_issued_at_utc"])
    return loc


def verify_locator_registration(seal, body):
    """Return a copy only after the live V2 chain and exact physical bytes check."""
    require(type(seal) is Seal and seal.registry_version == 2, "LIVE_EXPLICIT_V2_LOCATOR_SEAL_REQUIRED")
    seal.verify()
    value = closed(body, LOCATOR_KEYS, LOCATOR_VERSION + "-locator-registration", LOCATOR_CAP)
    require(body == seal.locator_registration_bytes and c.sha(body) == seal.document["locator_registration_sha256"],
            "EXACT_AUTHENTICATED_LOCATOR_BYTES_REQUIRED")
    return deepcopy(value)


def authorize_parent_get_client(parent, client, seal_sha256, *, clock=c.now):
    """Pure callback bridge for EXISTING ParentGETClient, including schedule.

    Example: authenticate=lambda sha: authorize_parent_get_client(parent, client,
    sha). Refresh the parent proof through authorize_parent when it expires.
    This performs NO private IO and never mints a dispatch/native-store proof.
    """
    from . import audit_weekly_template_v1 as template
    require(type(parent) is Parent and type(client) is template.ParentGETClient, "LIVE_PARENT_AND_EXISTING_GET_CLIENT_REQUIRED")
    loc = parent.seal.locators
    expected = c.digest(loc["template_seal"])
    proof = parent.proof
    require(type(proof) is c.Proof, "LIVE_PARENT_CONTROLLER_PROOF_REQUIRED")
    proof.verify(registration_sha256=parent.seal.registration_sha256,
        run_id=client.parent_run_id, job_id=client.parent_job_id)
    require(proof.document.get("schema_version") == c.VERSION + "-parent-proof"
            and client.seal_sha256 == seal_sha256 == expected
            and client.registration_sha256 == parent.seal.registration_sha256,
            "CURRENT_PARENT_GET_EXACT_TRUSTED_TEMPLATE_SEAL")
    scheduled = proof.document["scheduled_parent"]
    require(c.utc(scheduled["verified_at_utc"]) <= c.utc(clock())
            and (c.utc(clock()) - c.utc(scheduled["verified_at_utc"])).total_seconds() <= 180,
            "CURRENT_PARENT_GET_PROOF_EXPIRED")
    c.due(scheduled["event"], clock())
    return proof


def verify_template_payload(seal, body):
    """Pure validation AFTER ParentGETClient read; exact gzip + plain identities."""
    from . import audit_weekly_template_v1 as template, private_draft_store as store
    loc = seal.locators
    ts = loc["template_seal"]
    payload = ts["descriptor"]["entry"]["payload"]
    require(type(body) is bytes and len(body) == payload["bytes"] and store.sha(body) == payload["sha256"],
            "EXACT_PRIVATE_TEMPLATE_NATIVE_PAYLOAD")
    prepared = template.decode_static(body, template_sha256=ts["template_sha256"], template_bytes=ts["template_bytes"])
    p = c.decode(seal.registration_bytes)
    require(prepared.document["source_sha"] == p["producer"]["source_sha"]
            and prepared.document["code_pins"] == p["producer"]["code_pins"], "EXACT_PRIVATE_TEMPLATE_REGISTERED_SOURCE_INVENTORY")
    return prepared


def locator_contract():
    """Offline schema/ABI, never fabricated IDs, clocks, authority or readiness."""
    return dict(schema_version=LOCATOR_VERSION + "-contract", state="UNREGISTERED_OWNER_CLEARED_LOCATORS_REQUIRED",
        registry_path=LOCATOR_REGISTRY_PATH, registry_version=2, locator_keys=sorted(LOCATOR_KEYS),
        public_record_keys=sorted(PUBLIC_KEYS | {"locator_registration"}), template_seal_schema="audit-weekly-template-v1-seal",
        qualified_package_key_sets=[sorted(PACKAGE_KEYS), sorted(PACKAGE_FULL_KEYS)], locator_bytes_cap=LOCATOR_CAP,
        registration_clock="ACTUAL_FINAL_SEALER_CLOCK_AFTER_ORIGINAL_WRITER_READER",
        original_owner_root_preserved=True, original_native_proofs_preserved=True,
        private_reader="audit_weekly_template_v1.ParentGETClient", artifact_expiry_is_maintenance_gate=True,
        authority="ENGINEERING_LOCATORS_ONLY", public_root=False, public_rows=False, public_models=False,
        private_reads=0, POSTs=0, fits=0, activation_authorized=False)
