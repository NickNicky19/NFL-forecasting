"""Three native owner registration stages, using the existing private store.

Import, contract and request construction are metadata-only. Execution requires
the parent's full hosted.child_context gate, a current owner Actions API job,
literal source inventories and the original qualified runtime. JSON inputs are
locators/evidence, never current authority. No private template enters output.

The third job is still RUNNING when it emits SAFE_SEAL. Its local operation
clocks are not invented job completion times. The parent uploads that one file
with the native artifact action, then independently verifies the completed run
and all three successful jobs before creating the fixed bootstrap V2 registry.
This module neither uploads that artifact nor writes a public registry.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import gzip
import io
from pathlib import Path
import resource
import signal
import time
import zlib

from . import audit_weekly_controller_v1 as c
from . import audit_weekly_controller_bootstrap_v1 as bootstrap
from . import audit_weekly_template_v1 as template
from . import private_draft_store as store

VERSION = "audit-weekly-controller-registration-v1"
ROOT = Path(__file__).resolve().parents[1]
BRANCH = "research/weekly-storage-probe-v1"
PHASES = {
    "controller-template-write": ("produce", "controller-template-write"),
    "controller-template-read": ("restore", "controller-template-read"),
    "controller-template-seal": ("consume", "controller-template-seal"),
}
FILES = ("nfl_lab/audit_weekly_controller_registration_v1.py",
         "tools/audit_weekly_controller_registration_v1.py",
         "tests/test_audit_weekly_controller_registration_v1.py")
REQUIRED_PINS = set(FILES) | {c.MODULE, c.TOOL, c.WORKFLOW, bootstrap.MODULE,
    bootstrap.TOOL, bootstrap.TEST, bootstrap.TEMPLATE_MODULE} | bootstrap.SHARED_EXECUTABLE_PINS
SEPARATE_CONTEXT_SCHEMA = VERSION + "-context-v2"
HISTORY_CONTEXT_SCHEMA = VERSION + "-context-v3"
REQUEST_KEYS = {"schema_version", "phase", "code_pins", "limits", "cache", "state_root", "output", "inputs"}
INPUT_KEYS = {
    "controller-template-write": {"readiness"},
    "controller-template-read": {"template_handoff"},
    "controller-template-seal": {"template_handoff", "template_seal", "writer_native", "reader_native"},
}
OUTPUT_FILES = {
    "controller-template-write": {"template_handoff": "TEMPLATE_HANDOFF.json", "writer_native": "WRITER_NATIVE.json"},
    "controller-template-read": {"template_seal": "TEMPLATE_SEAL.json", "reader_native": "READER_NATIVE.json"},
    "controller-template-seal": {"safe_seal": "SAFE_SEAL.json", "registration": "REGISTRATION.json",
                                 "locator_registration": "LOCATOR_REGISTRATION.json"},
}
LIMITS = dict(wall_seconds=180, CPU_seconds=120, address_space_bytes=512 << 20, RSS_bytes=512 << 20,
    HTTP_calls=80, transfer_bytes=16 << 20, request_bytes=512 << 10, metadata_bytes=1 << 20,
    artifact_bytes=64 << 10, source_pins=128, global_private_bytes=512 << 20,
    fits=0, model_decodes=0, forecast_or_outcome_decodes=0, retries=0, append_attempts=1)
_KEY = object()


class RegistrationError(ValueError):
    """Fixed public-safe codes only."""


def require(ok, code):
    if not ok:
        raise RegistrationError(code)


def context(value):
    """Closed Root.effective_epoch; no registration digest self-reference."""
    require(type(value) is dict, "CLOSED_CONTROLLER_REGISTRATION_CONTEXT")
    modern=value.get("schema_version")==HISTORY_CONTEXT_SCHEMA
    separate = value.get("schema_version") == SEPARATE_CONTEXT_SCHEMA or modern
    keys = {"schema_version", "parent_source_sha", "previous_capture"} | ({"parent_code_pins"} if separate else set()) | ({"history_protocol"} if modern else set())
    require(set(value) == keys
        and value["schema_version"] == (HISTORY_CONTEXT_SCHEMA if modern else SEPARATE_CONTEXT_SCHEMA if separate else VERSION + "-context")
        and c.hashed(value["parent_source_sha"], 40)
        and type(value["previous_capture"]) is dict
        and set(value["previous_capture"]) == {"feed_sha256", "receipt_sha256"}
        and all(c.hashed(v) for v in value["previous_capture"].values()), "CLOSED_CONTROLLER_REGISTRATION_CONTEXT")
    if separate:
        _pins(value["parent_code_pins"], required=bootstrap.PARENT_EXECUTABLE_PINS)
    if modern:
        from . import audit_weekly_grade_history_v1 as history
        require(value["history_protocol"]==history.LOCATOR_VERSION,"EXPLICIT_CLOSED_HISTORY_LOCATOR_PROTOCOL")
    return value


def _pins(value, *, required=REQUIRED_PINS):
    require(type(value) is dict and required <= set(value) and len(value) <= LIMITS["source_pins"]
        and all(c.hashed(v) for v in value.values()), "COMPLETE_BOUNDED_REGISTRATION_SOURCE_PINS")
    for name in value:
        c.source_path(name)


def _source_specs(go):
    """The live owner Root binds each inventory to its own literal commit."""
    ctx = context(go["effective_epoch"])
    producer_pins = go["code_pins"]
    _pins(producer_pins)
    parent_pins = ctx.get("parent_code_pins", producer_pins)
    _pins(parent_pins, required=bootstrap.PARENT_EXECUTABLE_PINS)
    parent = dict(source_sha=ctx["parent_source_sha"], branch="main", code_pins=parent_pins,
        workflow_sha256=parent_pins[c.WORKFLOW])
    producer = dict(source_sha=go["source_sha"], branch=BRANCH, code_pins=producer_pins,
        workflow_sha256=producer_pins[c.WORKFLOW])
    bootstrap.source_inventories(parent, producer, registry_version=2)
    return parent, producer


def _path(value):
    require(type(value) is str and len(value) <= 4096 and Path(value).is_absolute()
        and str(Path(value)) == value and ".." not in Path(value).parts, "CONFINED_REGISTRATION_PATH_REQUIRED")
    return Path(value)


def validate_request(value, phase):
    require(type(phase) is str and phase in PHASES, "CLOSED_CONTROLLER_REGISTRATION_PHASE")
    require(type(value) is dict and set(value) == REQUEST_KEYS and value["schema_version"] == VERSION + "-request"
        and value["phase"] == phase and c.canonical(value["limits"]) == c.canonical(LIMITS)
        and type(value["inputs"]) is dict and set(value["inputs"]) == INPUT_KEYS[phase],
        "CLOSED_CONTROLLER_REGISTRATION_REQUEST")
    _pins(value["code_pins"])
    cache, state, output = (_path(value[k]) for k in ("cache", "state_root", "output"))
    require(cache.name == "cache" and state == cache.parent / "state" and output == cache.parent / PHASES[phase][1],
        "EXACT_REGISTRATION_PHASE_PATHS")
    if phase == "controller-template-write":
        # There is deliberately no caller-provided readiness assertion. The
        # previous_capture receipt is read and checked against actual API jobs.
        require(value["inputs"]["readiness"] is None, "READINESS_MUST_BE_DERIVED_FROM_ACTUAL_PRIOR_RECEIPT")
    else:
        for ref in value["inputs"].values():
            require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "CLOSED_REGISTRATION_METADATA_REFERENCE")
            path = _path(ref["path"])
            require(path.is_relative_to(cache.parent) and not path.is_relative_to(output)
                and type(ref["bytes"]) is int and 0 < ref["bytes"] <= LIMITS["artifact_bytes"]
                and c.hashed(ref["sha256"]), "BOUNDED_CURRENT_OWNED_REGISTRATION_METADATA")
        require(len({r["path"] for r in value["inputs"].values()}) == len(value["inputs"]),
            "DISTINCT_REGISTRATION_METADATA_REFERENCES")
    require(len(store.canonical(value)) <= LIMITS["request_bytes"], "BOUNDED_REGISTRATION_REQUEST")
    return value


def build_request(phase, *, code_pins, cache, state_root, output, inputs):
    """Pure closed request builder. No approval, credential, file or HTTP IO."""
    request = dict(schema_version=VERSION + "-request", phase=phase, code_pins=deepcopy(code_pins),
        limits=dict(LIMITS), cache=str(cache), state_root=str(state_root), output=str(output), inputs=deepcopy(inputs))
    return validate_request(request, phase)


def prepare_template(go, readiness):
    """Pure static derivative of the FULL Root; this confers no IO authority."""
    require(type(go) is dict and set(go) == template.ROOT_KEYS and go["approved"] is True
        and go["operation"] == "CONTROLLER_REGISTRATION", "FULL_OWNER_REGISTRATION_ROOT_REQUIRED")
    ctx=context(go["effective_epoch"])
    _pins(go["code_pins"])
    _source_specs(go)
    require(len(store.canonical(go)) <= 60 << 10, "BOUNDED_FULL_REGISTRATION_ROOT")
    root = deepcopy(go)
    root["approved"] = False
    for key in ("issued_at_utc", "expires_at_utc", "operation", "effective_epoch"):
        root[key] = None
    return template.prepare(dict(schema_version=template.VERSION + ("-static-v2" if ctx["schema_version"]==HISTORY_CONTEXT_SCHEMA else "-static"), source_sha=go["source_sha"],
        code_pins=deepcopy(go["code_pins"]), readiness=deepcopy(readiness), root_template=root))


def native_envelope():
    for kind, maximum in ((resource.RLIMIT_CPU, 120), (resource.RLIMIT_AS, 512 << 20)):
        soft, hard = resource.getrlimit(kind)
        require(type(soft) is int and type(hard) is int and 0 < soft <= hard <= maximum,
            "REGISTRATION_NATIVE_CPU_AS_GUARD_REQUIRED")
    remaining, interval = signal.getitimer(signal.ITIMER_REAL)
    require(signal.getsignal(signal.SIGALRM) == signal.SIG_DFL and 0 < remaining <= 180 and interval == 0,
        "REGISTRATION_NATIVE_WALL_GUARD_REQUIRED")


class _API:
    """Bounded GET-only adapter over a genuine store.Client, not JSON flags."""
    def __init__(self, live):
        self.live = live
        previous = live.go["effective_epoch"]["previous_capture"]
        self.receipt_path = "state/public/weekly-adaptive-v1/receipts/" + previous["feed_sha256"] + ".json.gz"
        self.allowed = {c.run_url(live.run_id), c.jobs_url(live.run_id),
            c.contents_url(self.receipt_path, "lab-state")}
        for source in {live.go["source_sha"], live.go["effective_epoch"]["parent_source_sha"]}:
            self.allowed.update({c.API + "/git/commits/" + source, c.contents_url(c.WORKFLOW, source)})

    def get(self, url, cap=1 << 20):
        self.live.budget()
        require(url in self.allowed and type(cap) is int and 0 < cap <= LIMITS["metadata_bytes"],
            "EXACT_REGISTRATION_METADATA_GET_ROUTE")
        client = self.live.metadata_client
        client.allowed.add(url)
        status, headers, body = client.request(url, cap=cap)
        require(status == 200 and headers.get("x-ratelimit-remaining") != "0" and "retry-after" not in headers,
            "REGISTRATION_METADATA_GET_FAILED")
        self.live.budget()
        return c.decode(body)


class _CreateOnceClient(store.Client):
    """Never let the core append helper reuse a concurrently created payload."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created_assets = []

    def upload(self, name, body, *, reuse_completed=False):
        result = super().upload(name, body, reuse_completed=False)
        self.created_assets.append((name, result["id"]))
        return result


class _Live:
    """Process-bound current authority; only hosted and live API can create it."""
    def __init__(self, args, env, hosted, checked, transport, key):
        require(key is _KEY, "LIVE_CONTROLLER_REGISTRATION_GUARD_REQUIRED")
        self.args, self.env, self.hosted, self.transport = args, env, hosted, transport
        self.request, self.authority, self.job, self.go = map(deepcopy, checked)
        self.phase = args.phase
        self.run_id = env["GITHUB_RUN_ID"]
        self.root_sha256 = store.sha(store.canonical(self.go))
        self.process = store.process_identity()
        self.started, self.cpu = time.monotonic(), time.process_time()
        self._integrity = c.digest(checked)
        self.native_client = None
        self.spec = dict(source_sha=self.go["source_sha"], branch=BRANCH, code_pins=self.go["code_pins"],
            workflow_sha256=self.go["code_pins"][c.WORKFLOW])
        journal = Path(self.request["cache"]).parent / "journal"
        self.metadata_client = store.Client(env.get("GITHUB_TOKEN"), self.run_id, journal=journal,
            source_sha=self.go["source_sha"], job=self.job, operation="metadata", transport=transport)
        self.api = _API(self)

    def budget(self):
        native_envelope()
        require(c.digest([self.request, self.authority, self.job, self.go]) == self._integrity
            and store.process_identity() == self.process
            and time.monotonic() - self.started <= 180 and time.process_time() - self.cpu <= 120
            and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= LIMITS["RSS_bytes"]
            and c.utc(self.go["issued_at_utc"]) <= c.now() < c.utc(self.go["expires_at_utc"]),
            "REGISTRATION_CURRENT_AUTHORITY_OR_PROCESS_CHANGED")
        clients = [self.metadata_client] + ([self.native_client] if self.native_client is not None else [])
        require(sum(x.calls for x in clients) <= LIMITS["HTTP_calls"]
            and sum(x.transferred for x in clients) <= LIMITS["transfer_bytes"], "REGISTRATION_SHARED_TRANSPORT_BUDGET")

    def snapshot(self):
        self.budget()
        run = c.checked_run(self.api.get(c.run_url(self.run_id)), self.run_id, self.spec, c.OWNER,
            event="workflow_dispatch", status="in_progress")
        listing = self.api.get(c.jobs_url(self.run_id))
        current = c.job(listing, self.run_id, self.spec, self.job["job_id"], status="in_progress",
            api_id=self.authority["api_job_id"])
        require(c.utc(self.go["issued_at_utc"]) <= c.utc(current["started_at"]) <= c.now()
            and current.get("completed_at") is None, "ACTUAL_RUNNING_REGISTRATION_JOB_CLOCK")
        return run, listing, current

    def recheck(self):
        self.budget()
        fresh = self.hosted.child_context(self.args, self.env, self.phase)
        require(c.digest(fresh) == self._integrity, "HOSTED_REGISTRATION_AUTHORITY_CHANGED")
        c.local_source(self.spec, ROOT, c.git_head)
        return self.snapshot()

    def client(self, operation):
        require(self.native_client is None, "ONE_NATIVE_REGISTRATION_TRANSPORT_PER_PHASE")
        self.recheck()
        qualification = self.go["qualified_runtime"]["qualification"]
        self.api.allowed.add(c.run_url(qualification["run_id"]))
        c.checked_run(self.api.get(c.run_url(qualification["run_id"])), qualification["run_id"],
            dict(source_sha=qualification["source_sha"], branch=qualification["job"]["workflow_ref"].split("@refs/heads/", 1)[1]),
            c.OWNER, event="workflow_dispatch", status="completed", strict_trigger=False)
        client_type = _CreateOnceClient if operation == "append" else store.Client
        client = client_type(self.env.get("GITHUB_TOKEN"), self.run_id, journal=self.metadata_client.journal,
            source_sha=self.go["source_sha"], job=self.job, operation=operation, transport=self.transport)
        client.bind(self.go["qualified_runtime"]["binding"])
        require(client.process == self.process, "ACTUAL_NATIVE_REGISTRATION_PROCESS")
        self.native_client = client
        return client

    def callback(self, operation, input_sha256):
        expected = template.digest(dict(phase=operation, input_sha256=input_sha256, root_go_sha256=self.root_sha256))
        def enforce(request_sha256):
            require(request_sha256 == expected, "EXACT_NATIVE_REGISTRATION_CALLBACK_SCOPE")
            self.recheck()
            # Enforce by raising, never return an authorization flag.
        return enforce

    def __reduce__(self):
        raise RegistrationError("REGISTRATION_JSON_IS_NOT_LIVE_AUTHORITY")


def _sources(live):
    """Authenticate each map at its own commit, retaining shared byte equality."""
    parent, producer = _source_specs(live.go)
    c.local_source(live.spec, ROOT, c.git_head)
    # Retain the hash-after-read check: local_source's earlier check alone does
    # not authenticate a file changed between validation and tree comparison.
    blobs = {}
    for name, expected in producer["code_pins"].items():
        body = store.read_local(ROOT / name, 2 << 20)
        require(c.sha(body) == expected, "CURRENT_REGISTRATION_SOURCE_CHANGED")
        blobs[name] = c.blob_sha(body)
    del body
    for spec in (producer, parent):
        source = spec["source_sha"]
        commit = live.api.get(c.API + "/git/commits/" + source)
        require(type(commit) is dict and commit.get("sha") == source and type(commit.get("tree")) is dict
            and c.hashed(commit["tree"].get("sha"), 40), "ACTUAL_LITERAL_REGISTRATION_GIT_COMMIT")
        tree_sha = commit["tree"]["sha"]
        url = c.API + "/git/trees/" + tree_sha + "?recursive=1"
        live.api.allowed.add(url)
        tree = live.api.get(url)
        require(type(tree) is dict and tree.get("sha") == tree_sha and tree.get("truncated") is False
            and type(tree.get("tree")) is list and len(tree["tree"]) <= 8192
            and all(type(item) is dict and type(item.get("path")) is str for item in tree["tree"]),
            "COMPLETE_LITERAL_REGISTRATION_SOURCE_TREE")
        for name, expected in spec["code_pins"].items():
            matches = [item for item in tree["tree"] if item["path"] == name]
            require(len(matches) == 1 and matches[0].get("type") == "blob"
                and matches[0].get("mode") in {"100644", "100755"}, "PLAIN_ROLE_LOCAL_PINNED_SOURCE_BLOB")
            if producer["code_pins"].get(name) == expected:
                blob = blobs[name]
            else:
                live.api.allowed.add(c.contents_url(name, source))
                body = c.content(live.api, name, source, cap=2 << 20)
                require(c.sha(body) == expected, "ROLE_LOCAL_PINNED_BYTES_MUST_MATCH_LITERAL_COMMIT")
                blob = c.blob_sha(body)
                del body
            require(matches[0].get("sha") == blob,
                "ROLE_LOCAL_PINNED_BYTES_MUST_MATCH_LITERAL_COMMIT")
    for spec, is_parent in ((producer, False), (parent, True)):
        c.workflow(live.api, spec, "lab" if is_parent else live.job["job_id"], parent=is_parent)
    body = store.read_local(ROOT / c.WORKFLOW, 256 << 10)
    import yaml
    wf = yaml.load(body, Loader=yaml.BaseLoader)
    for role, predecessor in (("read", "write"), ("seal", "read")):
        needs = wf["jobs"][bootstrap.JOBS[role]].get("needs")
        require(needs == bootstrap.JOBS[predecessor] or type(needs) is list
            and bootstrap.JOBS[predecessor] in needs and all(x in bootstrap.JOBS.values() for x in needs),
            "REGISTRATION_NATIVE_JOBS_REQUIRE_PREDECESSOR")


def _readiness(live):
    """Derive every readiness field from the exact compressed public receipt."""
    previous = live.go["effective_epoch"]["previous_capture"]
    raw = c.content(live.api, live.api.receipt_path, "lab-state", cap=64 << 10)
    require(c.sha(raw) == previous["receipt_sha256"], "EXACT_PRIOR_COUNT7_COMPRESSED_RECEIPT")
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        plain = decoder.decompress(raw, (64 << 10) + 1)
        require(len(plain) <= 64 << 10 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            "BOUNDED_SINGLE_PRIOR_COUNT7_RECEIPT")
    except zlib.error:
        raise RegistrationError("INVALID_PRIOR_COUNT7_RECEIPT_GZIP") from None
    doc = c.decode(plain)
    require(type(doc) is dict and set(doc) == c.RECEIPT_KEYS and plain == c.canonical(doc)
        and doc["schema_version"] == "audit-weekly-delivery-v1-public-receipt"
        and doc["feed_sha256"] == previous["feed_sha256"] and c.hashed(doc["source_sha"], 40)
        and c.run_id(doc["run_id"]) and doc["run_id"] != live.run_id, "ACTUAL_PRIOR_COUNT7_RECEIPT_METADATA")
    identifier = doc["run_id"]
    live.api.allowed.update({c.run_url(identifier), c.jobs_url(identifier), c.contents_url(c.WORKFLOW, doc["source_sha"])})
    run = live.api.get(c.run_url(identifier))
    require(type(run) is dict and c.branch(run.get("head_branch")), "ACTUAL_PRIOR_COUNT7_BRANCH")
    readiness = dict(source_sha=doc["source_sha"], branch=run["head_branch"], run_id=identifier,
        workflow_sha256=doc["workflow_sha256"], jobs=deepcopy(doc["jobs"]), receipt_sha256=c.sha(raw),
        receipt_body_sha256=c.sha(plain), receipt_bindings={key: doc[key] for key in c.RECEIPT_HASH_KEYS})
    template._readiness(readiness)
    # Root's original authorization precedes every registration stage/current
    # value. The final registration clock is assigned separately by the sealer.
    prior, _ = c.readiness(live.api, dict(readiness=readiness, registered_at_utc=live.go["issued_at_utc"]),
        before=live.go["issued_at_utc"])
    c.stable(run, prior)
    return readiness


def _policy(go):
    registration = go["publication_registration"]
    require(type(registration) is dict and set(registration) == {"policy_gzip_base64", "policy_sha256", "rights_authority", "r0"}
        and c.hashed(registration["policy_sha256"]) and type(registration["policy_gzip_base64"]) is str
        and len(registration["policy_gzip_base64"]) <= 48 << 10, "ORIGINAL_STATIC_PUBLIC_POLICY_REQUIRED")
    try:
        packed = base64.b64decode(registration["policy_gzip_base64"], validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as source:
            body = source.read(template.PLAIN_CAP + 1)
    except (ValueError, OSError, EOFError):
        raise RegistrationError("INVALID_STATIC_REGISTRATION_POLICY") from None
    policy = c.decode(body)
    require(0 < len(body) <= template.PLAIN_CAP and body == store.canonical(policy)
        and store.sha(body) == registration["policy_sha256"] and policy["source_sha"] == go["source_sha"]
        and policy["workflow_sha256"] == go["code_pins"][c.WORKFLOW]
        and c.utc(policy["registered_at_utc"]) <= c.utc(go["issued_at_utc"]), "UNCHANGED_PREVALUE_STATIC_POLICY_CLOCK")
    return registration["policy_sha256"]


def authenticate_child(args, env, *, transport=None):
    native_envelope()
    from . import audit_weekly_hosted_v1 as hosted
    require(args.phase in PHASES and hosted.OPERATIONS_PHASES.get(args.phase) == PHASES[args.phase],
        "PARENT_HOSTED_REGISTRATION_PHASE_WIRING_REQUIRED")
    checked = hosted.child_context(args, env, args.phase)
    request, authority, job, go = checked
    validate_request(request, args.phase)
    require(type(go) is dict and set(go) == template.ROOT_KEYS and go["operation"] == "CONTROLLER_REGISTRATION"
        and go["approved"] is True and go["code_pins"] == request["code_pins"]
        and go["jobs"] == dict(produce=bootstrap.JOBS["write"], restore=bootstrap.JOBS["read"], consume=bootstrap.JOBS["seal"])
        and go["failure_restorer"] == "audit-weekly-failure-restore-v1", "FULL_UNCHANGED_OWNER_REGISTRATION_ROOT")
    context(go["effective_epoch"])
    raw = store.canonical(go)
    require(len(raw) <= 60 << 10 and env.get("AUDIT_WEEKLY_ROOT_GO_JSON") == raw.decode()
        and env.get("AUDIT_WEEKLY_ROOT_GO_SHA256") == store.sha(raw) == authority["owner_root_go_sha256"]
        and type(authority) is dict and set(authority) == hosted.NATIVE_KEYS
        and authority["schema_version"] == hosted.VERSION + "-native-authority" and authority["phase"] == args.phase
        and authority["request_sha256"] == args.request_sha256 == store.sha(store.canonical(request)),
        "EXACT_HOSTED_REGISTRATION_ROOT_REQUEST_AUTHORITY")
    spec = dict(source_sha=go["source_sha"], branch=BRANCH)
    role, _ = PHASES[args.phase]
    names = ("GITHUB_ACTIONS", "CI", "GITHUB_REPOSITORY", "GITHUB_RUN_ATTEMPT", "GITHUB_RUN_ID",
        "GITHUB_EVENT_NAME", "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_JOB",
        "GITHUB_ACTOR", "GITHUB_ACTOR_ID")
    c.common_env({name: env.get(name) for name in names}, spec, go["jobs"][role], c.OWNER, event="workflow_dispatch")
    require(env.get("STORE_PERMISSION") == "write" and go["workflow_ref"] == c.REPO + "/" + c.WORKFLOW + "@refs/heads/" + BRANCH
        and type(job) is dict and set(job) == store.JOB_FIELDS and job["execution_lane"] == "github_actions"
        and job["permission"] == "write" and job["workflow_sha"] == go["source_sha"]
        and job["workflow_ref"] == go["workflow_ref"] and job["job_id"] == go["jobs"][role],
        "ACTUAL_OWNER_REGISTRATION_ACTIONS_CONTEXT")
    _policy(go)
    bootstrap._qualified_locator_package(go["qualified_runtime"], go["qualified_runtime"]["binding"], before=go["issued_at_utc"])
    require(not store.parents_safe(request["output"]).exists(), "ONE_REGISTRATION_PHASE_NO_RETRY")
    live = _Live(args, env, hosted, checked, transport, _KEY)
    live.metadata_client.authenticate_actions_job()
    require(live.metadata_client.job["api_job_id"] == authority["api_job_id"], "ACTUAL_REGISTRATION_API_JOB_ID")
    live.snapshot()
    _sources(live)
    return live


def _storage(live):
    from .operational_storage import OperationalStorage
    storage = OperationalStorage(live.request["cache"], ROOT / "config/operational-source-policy-v2.json",
        state=live.request["state_root"])
    storage.register_root(Path(live.request["cache"]).parent)
    return storage


def _inputs(live, storage):
    from .owned_reference_batch import validate_owned_references
    refs = live.request["inputs"]
    validate_owned_references(storage, {r["path"]: r["sha256"] for r in refs.values()})
    result = {}
    for name, ref in refs.items():
        raw = store.read_local(ref["path"], LIMITS["artifact_bytes"])
        require(len(raw) == ref["bytes"] and store.sha(raw) == ref["sha256"], "EXACT_OWNED_REGISTRATION_METADATA_BYTES")
        value = c.decode(raw)
        require(store.canonical(value) == raw, "CANONICAL_OWNED_REGISTRATION_METADATA")
        result[name] = value
    return result


def _descriptor(handoff):
    return bootstrap.template_descriptor(dict(schema_version=bootstrap.LOCATOR_VERSION + "-private-template-descriptor",
        template_sha256=handoff["template_sha256"], template_bytes=handoff["template_bytes"],
        private_descriptor_sha256=store.sha(store.canonical(handoff["descriptor"])),
        storage_binding_sha256=store.sha(store.canonical(handoff["binding"]))), registry_version=2)


def _handoff(live, handoff, prepared):
    template._handoff(handoff)
    identity = handoff["writer"]
    require(handoff["root_go_sha256"] == live.root_sha256 and handoff["binding"] == live.go["qualified_runtime"]["binding"]
        and handoff["template_sha256"] == store.sha(prepared.plain) and handoff["template_bytes"] == len(prepared.plain)
        and identity["run_id"] == live.run_id and identity["source_sha"] == live.go["source_sha"]
        and identity["workflow_ref"] == live.go["workflow_ref"] and identity["job_id"] == bootstrap.JOBS["write"]
        and identity["process_identity"] != live.process, "EXACT_ORIGINAL_OWNER_TEMPLATE_HANDOFF")
    return _descriptor(handoff)


def _summary(handoff, identity, started, completed, *, reader=False):
    result = dict({k: v for k, v in _descriptor(handoff).items() if k != "schema_version"},
        job_id=identity["job_id"], api_job_id=identity["api_job_id"], process_identity=identity["process_identity"],
        started_at_utc=started, completed_at_utc=completed,
        receipt_sha256=handoff["reader_proof_sha256"] if reader else store.sha(store.canonical(handoff)),
        operation="FRESH_PRIVATE_TEMPLATE_READ" if reader else "CREATE_PRIVATE_TEMPLATE_ONCE",
        successful_private_creates=0 if reader else 1)
    bootstrap._native(result, _descriptor(handoff), "read" if reader else "write")
    return result


def _within(native, job):
    require(c.utc(job["started_at"]) <= c.utc(native["started_at_utc"])
        <= c.utc(native["completed_at_utc"]) <= c.utc(job["completed_at"]), "ORIGINAL_NATIVE_RECEIPT_WITHIN_ACTUAL_JOB")


def _emit(live, storage, documents):
    live.budget()
    output = store.parents_safe(live.request["output"])
    require(not output.exists(), "ONE_REGISTRATION_PHASE_NO_RETRY")
    # The entire current-job base is already registered. Registering this
    # subdirectory would add a private storage-owner control file to output.
    require(set(documents) == set(OUTPUT_FILES[live.phase]), "CLOSED_REGISTRATION_STAGE_OUTPUTS")
    artifacts = {}
    for name, value in documents.items():
        raw = store.canonical(value)
        require(0 < len(raw) <= LIMITS["artifact_bytes"], "BOUNDED_PUBLIC_REGISTRATION_ARTIFACT")
        path = output / OUTPUT_FILES[live.phase][name]
        storage.write_bytes(path, raw)
        artifacts[name] = dict(path=str(path), bytes=len(raw), sha256=store.sha(raw))
    return dict(schema_version=VERSION + "-result", phase=live.phase,
        state="SAFE_SEAL_READY_FOR_NATIVE_ARTIFACT_UPLOAD" if live.phase.endswith("seal") else "NATIVE_TEMPLATE_STAGE_COMPLETED",
        artifacts=artifacts, public_root=False, fits=0, registry_created=False, registration_run_completed=False)


def _write(live, readiness, prepared, storage):
    client = live.client("append")
    handoff = template.append(prepared, client, live.go["qualified_runtime"], storage=storage,
        output=Path(live.request["state_root"]) / "controller-registration-native-write",
        root_go_sha256=live.root_sha256, check_authority=live.callback("append", store.sha(prepared.plain)))
    descriptor = handoff["descriptor"]
    require(client.created_assets == [(descriptor["entry"]["payload_name"], descriptor["entry"]["payload_asset_id"]),
        ("manifest-" + descriptor["manifest_sha256"] + ".json", descriptor["manifest_asset_id"])],
        "ACTUAL_TWO_CREATED_NATIVE_TEMPLATE_ASSETS_REQUIRED")
    writer = _summary(handoff, handoff["writer"], client.started_at, handoff["appended_at_utc"])
    _, _, job = live.recheck()
    require(c.utc(job["started_at"]) <= c.utc(writer["started_at_utc"]) <= c.utc(writer["completed_at_utc"]) <= c.now(),
        "ACTUAL_NATIVE_WRITER_OPERATION_CLOCK")
    return _emit(live, storage, dict(template_handoff=handoff, writer_native=writer))


def _read(live, readiness, prepared, storage):
    handoff = _inputs(live, storage)["template_handoff"]
    _handoff(live, handoff, prepared)
    _, listing, current = live.recheck()
    writer = c.job(listing, live.run_id, live.spec, bootstrap.JOBS["write"], status="completed",
        api_id=handoff["writer"]["api_job_id"])
    require(c.utc(live.go["issued_at_utc"]) <= c.utc(writer["started_at"])
        <= c.utc(handoff["appended_at_utc"]) <= c.utc(writer["completed_at"]) <= c.utc(current["started_at"]),
        "COMPLETED_NATIVE_WRITER_PRECEDES_FRESH_READER")
    client = live.client("restore")
    restored = template.restore(handoff, client, live.go["qualified_runtime"], storage=storage,
        output=Path(live.request["state_root"]) / "controller-registration-native-read",
        root_go_sha256=live.root_sha256, check_authority=live.callback("restore", template.digest(handoff)))
    seal, proof = restored["seal"], restored["proof"]
    summary = _summary(seal, seal["reader"], proof["started_at_utc"], seal["verified_at_utc"], reader=True)
    live.recheck()
    return _emit(live, storage, dict(template_seal=seal, reader_native=dict(receipt=summary, proof=proof)))


def _seal(live, readiness, prepared, storage):
    inputs = _inputs(live, storage)
    handoff, ts, writer = (inputs[k] for k in ("template_handoff", "template_seal", "writer_native"))
    descriptor = _handoff(live, handoff, prepared)
    template._handoff(ts, sealed=True)
    original = {key: deepcopy(ts[key]) for key in template.HANDOFF_KEYS}
    original["schema_version"] = template.VERSION + "-appended"
    require(original == handoff, "UNCHANGED_NATIVE_TEMPLATE_HANDOFF_AT_SEAL")
    reader_native = inputs["reader_native"]
    require(type(reader_native) is dict and set(reader_native) == {"receipt", "proof"}, "CLOSED_ORIGINAL_READER_NATIVE_PROOF")
    reader, proof = reader_native["receipt"], reader_native["proof"]
    bootstrap._native(writer, descriptor, "write")
    bootstrap._native(reader, descriptor, "read")
    for name, native in (("writer", writer), ("reader", reader)):
        identity = ts[name]
        require(all(native[k] == identity[k] for k in ("job_id", "api_job_id", "process_identity")),
            "UNCHANGED_ORIGINAL_NATIVE_TEMPLATE_IDENTITIES")
    require(writer["receipt_sha256"] == store.sha(store.canonical(handoff))
        and writer["completed_at_utc"] == handoff["appended_at_utc"]
        and reader["receipt_sha256"] == ts["reader_proof_sha256"] == store.sha(store.canonical(proof))
        and reader["started_at_utc"] == proof["started_at_utc"] and reader["completed_at_utc"] == ts["verified_at_utc"]
        and proof["process_identity"] == ts["reader"]["process_identity"]
        and proof["job"]["api_job_id"] == ts["reader"]["api_job_id"]
        and proof["job"]["job_id"] == bootstrap.JOBS["read"], "EXACT_ORIGINAL_NATIVE_TEMPLATE_RECEIPTS")
    require(len({writer["process_identity"], reader["process_identity"], live.process}) == 3
        and len({writer["api_job_id"], reader["api_job_id"], live.authority["api_job_id"]}) == 3,
        "THREE_DISTINCT_NATIVE_REGISTRATION_JOBS_AND_PROCESSES")
    run, listing, current = live.recheck()
    actual = {role: c.job(listing, live.run_id, live.spec, bootstrap.JOBS[role], status="completed", api_id=n["api_job_id"])
        for role, n in (("write", writer), ("read", reader))}
    _within(writer, actual["write"])
    _within(reader, actual["read"])
    require(c.utc(live.go["issued_at_utc"]) <= c.utc(writer["started_at_utc"])
        <= c.utc(writer["completed_at_utc"]) <= c.utc(reader["started_at_utc"])
        <= c.utc(reader["completed_at_utc"]) <= c.utc(current["started_at"])
        and c.utc(live.go["issued_at_utc"]) <= c.utc(actual["write"]["started_at"])
        and c.utc(actual["write"]["completed_at"]) <= c.utc(actual["read"]["started_at"])
        and c.utc(actual["read"]["completed_at"]) <= c.utc(current["started_at"]),
        "GENUINE_COMPLETED_WRITER_READER_BEFORE_CURRENT_SEALER")
    client = live.client("metadata")
    client.authenticate_actions_job()
    template._package(client, live.go["qualified_runtime"])
    store.check_proof(client, proof, "restore")
    payload = ts["descriptor"]["entry"]["payload"]
    require(proof["exact_readback"] is proof["separate_process"] is proof["draft_before_after"] is True
        and proof["payload_sha256"] == payload["sha256"] and type(proof["bytes"]) is int
        and proof["bytes"] == payload["bytes"]
        and c.utc(proof["created_at_utc"]) <= c.utc(ts["verified_at_utc"]), "ORIGINAL_NATIVE_RESTORE_PAYLOAD_AND_CLOCK")
    # Fresh authenticated sealer readback checks the actual persisted manifest
    # and original compressed bytes. It does not relabel a JSON proof as IO.
    d, entry = ts["descriptor"], ts["descriptor"]["entry"]
    client.draft()
    saved = client.read_asset(d["manifest_asset_id"], "manifest-" + d["manifest_sha256"] + ".json",
        d["manifest_bytes"], d["manifest_sha256"])
    require(saved == store.canonical(entry), "ACTUAL_ORIGINAL_NATIVE_TEMPLATE_MANIFEST")
    body = client.read_asset(entry["payload_asset_id"], entry["payload_name"], payload["bytes"], payload["sha256"])
    recovered = template.decode_static(body, template_sha256=ts["template_sha256"], template_bytes=ts["template_bytes"])
    require(recovered.plain == prepared.plain, "ACTUAL_PRIVATE_TEMPLATE_EQUALS_FULL_ROOT_DERIVATIVE")
    client.draft()
    after_run, after_listing, after_current = live.recheck()
    c.stable(run, after_run)
    for role, native in (("write", writer), ("read", reader)):
        fresh = c.job(after_listing, live.run_id, live.spec, bootstrap.JOBS[role], status="completed", api_id=native["api_job_id"])
        require(fresh == actual[role], "NATIVE_REGISTRATION_PREDECESSOR_JOB_CHANGED")
    require(after_current == current, "NATIVE_REGISTRATION_SEALER_JOB_CHANGED")
    registered = c.now().isoformat()
    registration = c.registration_template()
    registration.update(state="OWNER_SEALED_METADATA_BINDING", registered_at_utc=registered, readiness=deepcopy(readiness))
    pins = deepcopy(live.go["code_pins"])
    parent_spec, _ = _source_specs(live.go)
    registration["parent"].update(deepcopy(parent_spec))
    registration["producer"].update(source_sha=live.go["source_sha"], branch=BRANCH, code_pins=pins,
        workflow_sha256=pins[c.WORKFLOW], jobs=dict(live.go["jobs"], evidence=live.go["failure_restorer"]))
    reg_raw = c.canonical(registration)
    c.registration(reg_raw, sealed_sha256=c.sha(reg_raw), at=c.now())
    locators = dict(schema_version=bootstrap.LOCATOR_VERSION + "-locator-registration", repository=c.REPO,
        registered_at_utc=registered, owner_root_go_sha256=live.root_sha256,
        owner_root_issued_at_utc=live.go["issued_at_utc"], template_seal=deepcopy(ts),
        qualified_runtime_package=deepcopy(live.go["qualified_runtime"]))
    completed = c.now().isoformat()
    native = dict(schema_version=bootstrap.LOCATOR_VERSION + "-native-safe-seal", repository=c.REPO,
        run_id=live.run_id, source_sha=live.go["source_sha"], branch=BRANCH, workflow_sha256=pins[c.WORKFLOW],
        code_pins_sha256=c.digest(pins), registration_sha256=c.sha(reg_raw), registered_at_utc=registered,
        template_descriptor=descriptor, writer=writer, reader=reader,
        sealer=dict(job_id=live.job["job_id"], api_job_id=live.authority["api_job_id"], process_identity=client.process,
            started_at_utc=client.started_at, completed_at_utc=completed), static_public_policy_sha256=_policy(live.go),
        created_at_utc=c.now().isoformat(), public_root=False, fits=0,
        locator_registration_sha256=c.sha(c.canonical(locators)), owner_root_go_sha256=live.root_sha256,
        owner_root_issued_at_utc=live.go["issued_at_utc"])
    require(set(native) == bootstrap.SAFE_KEYS | {"locator_registration_sha256", "owner_root_go_sha256", "owner_root_issued_at_utc"}
        and c.utc(current["started_at"]) <= c.utc(client.started_at) <= c.utc(registered) <= c.utc(completed)
        <= c.utc(native["created_at_utc"]) <= c.now(), "CLOSED_ACTUAL_SEALER_REGISTRATION_CLOCK")
    bootstrap._validate_locator_registration(c.canonical(locators), native, registration)
    return _emit(live, storage, dict(safe_seal=native, registration=registration, locator_registration=locators))


def run(args, env, *, transport=None):
    live = authenticate_child(args, env, transport=transport)
    readiness = _readiness(live)
    prepared = prepare_template(live.go, readiness)
    storage = _storage(live)
    execute = {"controller-template-write": _write, "controller-template-read": _read, "controller-template-seal": _seal}
    return execute[live.phase](live, readiness, prepared, storage)


def contract():
    """Offline ABI only; never evidence of a genuine hosted execution."""
    return dict(schema_version=VERSION + "-contract", phases={k: list(v) for k, v in PHASES.items()},
        request_keys=sorted(REQUEST_KEYS), input_keys={k: sorted(v) for k, v in INPUT_KEYS.items()},
        write_readiness=None, reference_keys=["path", "bytes", "sha256"], references="CURRENT_JOB_IMMUTABLE_OWNED_METADATA",
        output_files=deepcopy(OUTPUT_FILES), reader_native_keys=["receipt", "proof"], native_receipt_keys=sorted(bootstrap.NATIVE_KEYS),
        required_pins=sorted(REQUIRED_PINS), limits=dict(LIMITS), authority_namespace="AUDIT_WEEKLY_NATIVE_AUTHORITY",
        authority_schema="hosted.VERSION-native-authority", root_operation="CONTROLLER_REGISTRATION",
        context_schema=VERSION + "-context", separate_context_schema=SEPARATE_CONTEXT_SCHEMA,
        parent_inventory_field="effective_epoch.parent_code_pins", shared_executable_pins=sorted(bootstrap.SHARED_EXECUTABLE_PINS),
        template_dynamic_fields=["approved", "issued_at_utc", "expires_at_utc", "operation", "effective_epoch"],
        registry_version=2, artifact_file="SAFE_SEAL.json", artifact_name="controller-root-safe-seal-v2-<actual-run-id>",
        native_clocks="ACTUAL_LOCAL_OPERATIONS_NOT_JOB_COMPLETION", public_root=False, fits=0,
        registry_created=False, registration_run_completed=False,
        parent_remaining=["NATIVE_SAFE_SEAL_ARTIFACT_UPLOAD", "ACTUAL_WHOLE_RUN_AND_THREE_JOBS_SUCCESS", "CREATE_ONLY_FIXED_PUBLIC_REGISTRY"])
