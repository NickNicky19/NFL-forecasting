"""Live V2 parent: recover metadata, create one claim, enqueue once and exit.

No import or contract call discovers credentials, reads a template or performs
HTTP. JSON is never a source of parent authority: bootstrap.authorize_parent
and controller.verify_parent supply the actual current typed proof. The only
private transport is the unchanged template.ParentGETClient.

Public discovery reads dated filenames and closed compressed receipts, never a
feed row. This wrapper preserves the original source configuration and weekly
selection. Rollover/selection and workflow activation are separate owner work.
No child is polled, and a 204 only confirms an enqueue.

Sealed COUNT7 readiness is a bootstrap foundation, never BOT Ops readiness.
The first recurring Ops run is a separate direct Owner smoke. Parent enqueue
requires its same-source/policy/recipe successful Ops feed and validated grading
sidecar; this wrapper cannot bootstrap that evidence from the old receipt.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta
import importlib
from pathlib import Path
import re
import resource
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo
import zlib

from . import audit_weekly_controller_v1 as c
from . import audit_weekly_controller_bootstrap_v1 as bootstrap
from . import audit_weekly_template_v1 as template
from . import private_draft_store as store

VERSION = "audit-weekly-parent-v1"
ROOT = Path(__file__).resolve().parents[1]
FILES = ("nfl_lab/audit_weekly_parent_v1.py", "tools/audit_weekly_parent_v1.py", "tests/test_audit_weekly_parent_v1.py")
REQUIRED_PINS = set(FILES) | {c.MODULE, c.TOOL, c.WORKFLOW, bootstrap.MODULE, bootstrap.TOOL,
    bootstrap.TEST, bootstrap.TEMPLATE_MODULE, "nfl_lab/private_draft_store.py", "nfl_lab/owner_private_bootstrap.py",
    "nfl_lab/operational_storage.py", "tools/private_draft_store_v2.py", "tools/audit_process_guard_v1.py",
    "config/operational-source-policy-v2.json", "requirements-audit-weekly-metadata-v1.lock", "nfl_lab/cadence.py",
    "tests/test_cadence.py", "tests/test_audit_weekly_parent_workflow_v1.py"}
HISTORY_MODULE = "nfl_lab/audit_weekly_grade_history_v1.py"
# The local parent qualification is metadata-only. The Producer Root separately
# retains history.FILES, including its full native grading/history test suite.
HISTORY_TEST = FILES[2]
PRODUCER_HISTORY_TEST = "tests/test_audit_weekly_grade_history_v1.py"
PUBLIC_ROOT = "state/public/weekly-adaptive-v1"
CONTEXT_SCHEMA = "audit-weekly-recurring-v2-context"
DISPATCH_URL = c.API + "/actions/workflows/lab.yml/dispatches"
STATE_REF_URL = c.API + "/git/ref/heads/lab-state"
STATE_UPDATE_URL = c.API + "/git/refs/heads/lab-state"
DYNAMIC_FIELDS = {"approved", "issued_at_utc", "expires_at_utc", "operation", "effective_epoch"}
CHICAGO = ZoneInfo("America/Chicago")
LIMITS = dict(wall_seconds=180, CPU_seconds=120, address_space_bytes=512 << 20, RSS_bytes=512 << 20,
    HTTP_calls=140, authority_calls=80, private_calls=40, state_calls=20, transfer_bytes=32 << 20,
    response_bytes=1 << 20, request_timeout_seconds=10, root_bytes=60 << 10, root_lifetime_seconds=3600,
    receipt_bytes=64 << 10, sidecar_bytes=64 << 10, sidecar_plain_bytes=128 << 10,
    week_directories=24, directory_entries=256, feed_filenames=2048, candidate_receipts=8,
    source_pins=128, dispatches=1, blob_creates=1, tree_creates=1, commit_creates=1, ref_updates=1,
    retries=0, fits=0, model_decodes=0, feed_row_decodes=0, outcome_decodes=0)
_KEY = object()


class ParentError(ValueError):
    """Fixed public-safe errors, without underlying values or HTTP bodies."""


def require(ok, code):
    if not ok:
        raise ParentError(code)


def native_envelope():
    for kind, maximum in ((resource.RLIMIT_CPU, 120), (resource.RLIMIT_AS, 512 << 20)):
        soft, hard = resource.getrlimit(kind)
        require(type(soft) is int and type(hard) is int and 0 < soft <= hard <= maximum,
            "PARENT_NATIVE_CPU_AS_GUARD_REQUIRED")
    remaining, interval = signal.getitimer(signal.ITIMER_REAL)
    require(signal.getsignal(signal.SIGALRM) == signal.SIG_DFL and 0 < remaining <= 180 and interval == 0,
        "PARENT_NATIVE_WALL_GUARD_REQUIRED")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class _Response:
    def __init__(self, response, ledger, record, cap):
        self.response, self.ledger, self.record, self.cap = response, ledger, record, cap
        self.status, self.headers = response.status, response.headers
        record["status"] = self.status

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def read(self, count):
        self.ledger.budget()
        require(type(count) is int and 0 <= count <= store.ASSET_CAP + 1, "BOUNDED_PARENT_RESPONSE_READ")
        remaining = LIMITS["transfer_bytes"] - self.ledger.transferred
        body = self.response.read(min(count, self.cap + 1, max(0, remaining) + 1))
        require(type(body) is bytes, "ACTUAL_PARENT_HTTP_BYTES_REQUIRED")
        self.ledger.transferred += len(body)
        self.record["response_bytes"] += len(body)
        self.ledger.budget()
        require(len(body) <= self.cap, "PARENT_RESPONSE_CAP")
        return body


class _Ledger:
    """Counts EVERY exchange, including bootstrap, redirects and failed writes."""
    def __init__(self, token, transport):
        native_envelope()
        require(type(token) is str and token.startswith("ghs_") and not any(x.isspace() for x in token),
            "FRESH_AUTOMATIC_GITHUB_TOKEN_REQUIRED")
        require(transport is None or callable(transport), "LIVE_PARENT_HTTP_TRANSPORT_REQUIRED")
        self._token, self.transport = token, transport
        self.wall, self.cpu, self.process = time.monotonic(), time.process_time(), store.process_identity()
        self.counts = dict(authority=0, private=0, state=0)
        self.transferred, self.records, self.mutations = 0, [], set()
        self.journal = None

    def budget(self):
        native_envelope()
        require(store.process_identity() == self.process and time.monotonic() - self.wall < 180
            and time.process_time() - self.cpu <= 120
            and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= LIMITS["RSS_bytes"]
            and sum(self.counts.values()) <= LIMITS["HTTP_calls"] and self.transferred <= LIMITS["transfer_bytes"],
            "PARENT_SHARED_NATIVE_OR_TRANSFER_BUDGET")

    def _open(self, request, lane, cap):
        self.budget()
        require(lane in self.counts and self.counts[lane] < LIMITS[lane + "_calls"]
            and sum(self.counts.values()) < LIMITS["HTTP_calls"], "PARENT_SHARED_HTTP_ATTEMPT_CAP")
        method, url = request.get_method(), request.full_url
        if method != "GET":
            require(lane == "state" and method in {"POST", "PATCH"} and self.journal is not None,
                "PARENT_ONLY_REGISTERED_STATE_MUTATIONS")
            key = (method, url)
            require(key not in self.mutations, "PARENT_MUTATION_ALREADY_ATTEMPTED_NO_RETRY")
            self.mutations.add(key)
            # A durable LOCAL reservation precedes every attempt. It contains
            # hashes only, never the private dispatch body or a credential.
            store.create_local(self.journal / (c.digest([method, url]) + ".intent.json"), c.canonical(dict(
                schema_version=VERSION + "-http-intent", method=method, route_sha256=c.sha(url.encode()),
                body_sha256=c.sha(request.data or b""), automatic_retry=False)))
        self.counts[lane] += 1
        self.transferred += len(request.data or b"")
        record = dict(lane=lane, method=method, status=None, response_bytes=0)
        self.records.append(record)
        self.budget()
        timeout = min(LIMITS["request_timeout_seconds"], max(.001, 180 - (time.monotonic() - self.wall)))
        try:
            if self.transport is not None:
                response = self.transport(request, timeout)
            else:
                try:
                    response = build_opener(_NoRedirect()).open(request, timeout=timeout)
                except HTTPError as error:
                    response = error
        except (URLError, OSError, TimeoutError):
            raise ParentError("PARENT_HTTP_ATTEMPT_FAILED_NO_RETRY") from None
        return _Response(response, self, record, cap)

    def request(self, url, *, lane="authority", method="GET", value=None, cap=1 << 20):
        require(type(url) is str and url.startswith(c.API + "/") and 0 < cap <= LIMITS["response_bytes"]
            and method in {"GET", "POST", "PATCH"} and (value is None) == (method == "GET"),
            "EXACT_PARENT_AUTHENTICATED_API_EXCHANGE")
        body = None if value is None else c.canonical(value)
        require(body is None or len(body) <= 128 << 10, "BOUNDED_PARENT_HTTP_REQUEST")
        request = Request(url, data=body, method=method, headers={"Authorization": "Bearer " + self._token,
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
        with self._open(request, lane, cap) as response:
            headers = {k.lower(): v for k, v in response.headers.items()}
            raw = response.read(cap + 1)
            status = response.status
        require("retry-after" not in headers and headers.get("x-ratelimit-remaining") != "0", "PARENT_API_RATE_GUARD")
        return c.Reply(status, raw)

    def bootstrap_get(self, url, cap):
        require(bootstrap.fixed_route(url), "FIXED_V2_PARENT_BOOTSTRAP_ROUTE_ONLY")
        return self.request(url, cap=cap)

    def private_get(self, request, _timeout):
        require(request.get_method() == "GET" and request.data is None, "PARENT_PRIVATE_GET_ONLY")
        return self._open(request, "private", store.ASSET_CAP)


class _API:
    def __init__(self, ledger):
        self.ledger, self.allowed = ledger, {STATE_REF_URL}

    def add(self, url):
        self.allowed.add(url)
        return url

    def get(self, url, cap=1 << 20):
        require(url in self.allowed or bootstrap.fixed_route(url), "SOURCE_DERIVED_PARENT_METADATA_ROUTE_ONLY")
        reply = self.ledger.request(url, cap=cap)
        require(reply.status == 200, "PARENT_METADATA_GET_REQUIRED")
        return c.decode(reply.body)

    def content(self, path, ref, cap):
        self.add(c.contents_url(path, ref))
        return c.content(self, path, ref, cap=cap)

    def state_head(self, *, state=False):
        if state:
            reply = self.ledger.request(STATE_REF_URL, lane="state")
            require(reply.status == 200, "ACTUAL_PARENT_STATE_REF_REQUIRED")
            value = c.decode(reply.body)
        else:
            value = self.get(STATE_REF_URL)
        require(type(value) is dict and value.get("ref") == "refs/heads/lab-state"
            and value.get("object", {}).get("type") == "commit" and c.hashed(value["object"].get("sha"), 40),
            "EXACT_EXISTING_LAB_STATE_HEAD")
        return value["object"]["sha"]


def _unpack(body, *, packed_cap, plain_cap):
    require(type(body) is bytes and 0 < len(body) <= packed_cap, "BOUNDED_PARENT_COMPRESSED_METADATA")
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        plain = decoder.decompress(body, plain_cap + 1)
        require(len(plain) <= plain_cap and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            "BOUNDED_SINGLE_PARENT_METADATA_GZIP")
    except zlib.error:
        raise ParentError("INVALID_PARENT_METADATA_GZIP") from None
    value = c.decode(plain)
    require(plain == c.canonical(value), "CANONICAL_PARENT_METADATA_BODY")
    return value


def _receipt(body):
    value = _unpack(body, packed_cap=LIMITS["receipt_bytes"], plain_cap=LIMITS["receipt_bytes"])
    require(type(value) is dict and set(value) == c.RECEIPT_KEYS
        and value["schema_version"] == "audit-weekly-delivery-v1-public-receipt"
        and c.hashed(value["source_sha"], 40) and c.run_id(value["run_id"])
        and all(c.hashed(value[k]) for k in c.RECEIPT_HASH_KEYS | {"workflow_sha256"})
        and type(value["fits"]) is int and value["fits"] == 0 and value["raw_or_models_public"] is False
        and type(value["rows"]) is int and 0 < value["rows"] <= 5000
        and type(value["feed_bytes"]) is int and 0 < value["feed_bytes"] <= 4 << 20
        and type(value["categories"]) is list and value["categories"] == sorted(c.TARGETS),
        "CLOSED_PARENT_PUBLIC_RECEIPT")
    jobs = value["jobs"]
    require(type(jobs) is dict and set(jobs) == set(c.ROLES)
        and all(type(j) is dict and set(j) == {"job_id", "api_job_id"} and template.label(j["job_id"])
            and c.positive(j["api_job_id"]) for j in jobs.values())
        and len({j["api_job_id"] for j in jobs.values()}) == len({j["job_id"] for j in jobs.values()}) == 3
        and c.utc(value["policy_registered_at_utc"]) <= c.utc(value["verified_at"]) <= c.utc(value["created_at"]),
        "CLOSED_PARENT_RECEIPT_JOBS_AND_CLOCKS")
    return value


def _policy(parent, document):
    root, p = document["root_template"], c.decode(parent.registration_bytes)
    value = root["publication_registration"]
    require(type(value) is dict and set(value) == {"policy_gzip_base64", "policy_sha256", "rights_authority", "r0"}
        and value["policy_sha256"] == parent.seal.document["static_public_policy_sha256"]
        and type(value["policy_gzip_base64"]) is str and 0 < len(value["policy_gzip_base64"]) <= 48 << 10,
        "EXACT_SEALED_PARENT_STATIC_POLICY")
    try:
        packed = base64.b64decode(value["policy_gzip_base64"], validate=True)
    except (ValueError, TypeError):
        raise ParentError("INVALID_SEALED_PARENT_POLICY_ENCODING") from None
    policy = _unpack(packed, packed_cap=48 << 10, plain_cap=128 << 10)
    require(type(policy) is dict and c.sha(store.canonical(policy)) == value["policy_sha256"]
        and policy.get("source_sha") == p["producer"]["source_sha"]
        and policy.get("source_branch") == p["producer"]["branch"]
        and policy.get("workflow_sha256") == p["producer"]["workflow_sha256"]
        and c.hashed(policy.get("producer_policy_sha256")) and root["publication"] is True,
        "SEALED_POLICY_LITERAL_PRODUCER_AND_RECIPE")
    return policy


def _source(parent, source_root, read_head):
    require(type(parent) is bootstrap.Parent and type(parent.proof) is c.Proof and parent.seal.registry_version == 2,
        "LIVE_EXPLICIT_V2_PARENT_REQUIRED")
    parent.seal.verify()
    p = c.decode(parent.registration_bytes)
    require(c.canonical(p["cadence"]) == c.canonical(c.PARENT_CADENCE), "EXPLICIT_PARENT_0736_REGISTRATION_REQUIRED")
    require(REQUIRED_PINS <= set(p["parent"]["code_pins"])
        and len(p["parent"]["code_pins"]) <= LIMITS["source_pins"], "SEALED_LITERAL_PARENT_WRAPPER_SOURCE_PINS_REQUIRED")
    bootstrap.source_inventories(p["parent"], p["producer"], registry_version=2)
    c.local_source(p["parent"], source_root, read_head)
    return p


def _live(parent, env, source_root, read_head, clock):
    p = _source(parent, source_root, read_head)
    parent.proof.verify(registration_sha256=parent.seal.registration_sha256,
        run_id=env.get("GITHUB_RUN_ID"), job_id=env.get("GITHUB_JOB"))
    d = parent.proof.document
    require(d.get("schema_version") == c.VERSION + "-parent-proof", "ACTUAL_CONTROLLER_PARENT_PROOF_REQUIRED")
    at, scheduled = c.utc(clock()), d["scheduled_parent"]
    require(c.utc(scheduled["verified_at_utc"]) <= at
        and (at - c.utc(scheduled["verified_at_utc"])).total_seconds() < 180, "FRESH_PARENT_PROOF_REQUIRED")
    # Preserve the original event policy: cron has the Chicago window; an
    # actual Owner workflow_dispatch/daily retains its explicit manual scope.
    c.due(scheduled["event"], scheduled["job_started_at"], cadence=p["cadence"])
    c.due(scheduled["event"], at, cadence=p["cadence"])
    c.common_env(bootstrap._environment(env), p["parent"], p["parent"]["job_id"], c.OWNER, event=scheduled["event"])
    return p


def _workspace(env, work_root):
    if work_root is None:
        temporary = env.get("RUNNER_TEMP")
        require(type(temporary) is str and Path(temporary).is_absolute(), "ACTUAL_PARENT_RUNNER_TEMP_REQUIRED")
        work_root = Path(temporary) / (VERSION + "-" + env["GITHUB_RUN_ID"] + "-1")
    require(Path(work_root).is_absolute(), "ABSOLUTE_PRIVATE_PARENT_WORKSPACE_REQUIRED")
    path = store.parents_safe(work_root)
    require(path.is_absolute() and not path.exists() and path.parent.is_dir(), "FRESH_PRIVATE_PARENT_WORKSPACE_REQUIRED")
    path.mkdir(mode=0o700)
    journal = path / "journal"
    journal.mkdir(mode=0o700)
    return path, journal


def _recover(parent, env, source_root, read_head, clock, ledger, workspace, journal):
    from .operational_storage import OperationalStorage
    _live(parent, env, source_root, read_head, clock)
    storage = OperationalStorage(workspace / "cache", Path(source_root) / "config/operational-source-policy-v2.json",
        state=workspace / "state")
    storage.register_root(workspace)
    locators = parent.locators
    seal = locators["template_seal"]
    def authenticate(sha):
        ledger.budget()
        _live(parent, env, source_root, read_head, clock)
        # Preserve the old 08:36 bootstrap bridge for old registrations. This
        # explicit policy bridge uses the same typed proof and sealed locator.
        require(sha == client.seal_sha256 == c.digest(parent.locators["template_seal"])
            and client.registration_sha256 == parent.seal.registration_sha256
            and client.parent_run_id == env["GITHUB_RUN_ID"] and client.parent_job_id == env["GITHUB_JOB"],
            "CURRENT_PARENT_GET_EXACT_TRUSTED_TEMPLATE_SEAL")
        return parent.proof
    client = template.ParentGETClient(ledger._token, seal_sha256=c.digest(seal),
        registration_sha256=parent.seal.registration_sha256, parent_run_id=env["GITHUB_RUN_ID"], parent_job_id=env["GITHUB_JOB"],
        authenticate=authenticate, journal=journal, transport=ledger.private_get)
    result = template.recover_for_parent(seal, locators["qualified_runtime_package"], client,
        storage=storage, output=workspace / "private-template")
    document = result["document"]
    plain = store.canonical(document)
    bootstrap.verify_private_template(parent.seal, plain, store.canonical(seal["descriptor"]), store.canonical(seal["binding"]))
    template.prepare(document)
    p = c.decode(parent.registration_bytes)
    require(document["source_sha"] == p["producer"]["source_sha"] and document["code_pins"] == p["producer"]["code_pins"]
        and document["readiness"] == p["readiness"] and document["root_template"]["qualified_runtime"] == locators["qualified_runtime_package"],
        "EXACT_RECOVERED_STATIC_ROOT_AND_REGISTERED_INVENTORY")
    return document, client, storage


def _listing(api, path, head):
    url = api.add(c.contents_url(path, head))
    value = api.get(url)
    require(type(value) is list and len(value) <= LIMITS["directory_entries"]
        and all(type(item) is dict and type(item.get("name")) is str and item.get("path") == path + "/" + item["name"]
            and item.get("type") in {"file", "dir"} and c.hashed(item.get("sha"), 40) for item in value)
        and len({item["name"] for item in value}) == len(value), "COMPLETE_BOUNDED_PARENT_PUBLIC_DIRECTORY")
    return value


def _filenames(api, head):
    directories = _listing(api, PUBLIC_ROOT, head)
    weeks = []
    for entry in directories:
        require(entry["type"] == "dir" and (entry["name"] == "receipts"
            or re.fullmatch(r"[12][0-9]{3}-W(?:0[1-9]|1[0-9]|2[0-2])", entry["name"])), "DATED_PUBLIC_WEEK_DIRECTORY_ONLY")
        if entry["name"] != "receipts": weeks.append(entry["name"])
    require(0 < len(weeks) <= LIMITS["week_directories"], "BOUNDED_COMPLETE_PARENT_WEEK_DIRECTORY_CENSUS")
    result = []
    for week in sorted(weeks):
        for entry in _listing(api, PUBLIC_ROOT + "/" + week, head):
            match = re.fullmatch(r"([0-9]{8}T[0-9]{6}\.[0-9]{6}Z)--([a-f0-9]{64})\.json", entry["name"])
            require(entry["type"] == "file" and match is not None and type(entry.get("size")) is int
                and 0 < entry["size"] <= 4 << 20, "DATED_PUBLIC_FEED_FILENAME_METADATA_ONLY")
            try: stamp = datetime.strptime(match[1], "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=c.timezone.utc)
            except ValueError: raise ParentError("VALID_PUBLIC_FEED_FILENAME_CLOCK_REQUIRED") from None
            result.append(dict(path=entry["path"], week=week, stamp=stamp.isoformat(), feed_sha256=match[2], bytes=entry["size"]))
            require(len(result) <= LIMITS["feed_filenames"], "PARENT_PUBLIC_FILENAME_CENSUS_CAP")
    require(len({item["feed_sha256"] for item in result}) == len(result), "UNIQUE_PUBLIC_FEED_FILENAME_HASHES")
    return sorted(result, key=lambda x: (x["stamp"], x["feed_sha256"]), reverse=True)


def _completed(api, p, receipt, *, initial, before, clock):
    identifier = receipt["run_id"]
    spec = p["readiness"] if initial else p["producer"]
    run = api.get(c.run_url(identifier))
    expected_actor = c.OWNER if initial else run.get("actor")
    require(c.actor(expected_actor, c.OWNER) or c.actor(expected_actor, c.BOT), "ACTUAL_PRIOR_CAPTURE_OWNER_OR_BOT")
    c.checked_run(run, identifier, spec, expected_actor, event="workflow_dispatch", status="completed", strict_trigger=False)
    listing = api.get(c.jobs_url(identifier))
    expected_jobs = p["readiness"]["jobs"] if initial else {k: dict(job_id=p["producer"]["jobs"][k],
        api_job_id=receipt["jobs"][k]["api_job_id"]) for k in c.ROLES}
    require(receipt["jobs"] == expected_jobs, "EXACT_REGISTERED_PRIOR_CAPTURE_JOB_NAMES")
    jobs = {role: c.job(listing, identifier, spec, receipt["jobs"][role]["job_id"], status="completed",
        api_id=receipt["jobs"][role]["api_job_id"]) for role in c.ROLES}
    require(c.utc(jobs["produce"]["completed_at"]) <= c.utc(jobs["restore"]["started_at"])
        and c.utc(jobs["restore"]["completed_at"]) <= c.utc(jobs["consume"]["started_at"])
        <= c.utc(receipt["verified_at"]) <= c.utc(receipt["created_at"]) <= c.utc(jobs["consume"]["completed_at"])
        <= c.utc(run["updated_at"]) <= c.utc(before) <= c.utc(clock()), "ACTUAL_COMPLETED_PRIOR_CAPTURE_CHAIN_CLOCKS")
    c.workflow(api, spec, receipt["jobs"]["consume"]["job_id"])
    c.stable(run, api.get(c.run_url(identifier)))
    fresh = api.get(c.jobs_url(identifier))
    for role in c.ROLES:
        require(c.job(fresh, identifier, spec, receipt["jobs"][role]["job_id"], status="completed",
            api_id=receipt["jobs"][role]["api_job_id"]) == jobs[role], "PRIOR_CAPTURE_API_JOB_CHANGED")
    return jobs, run


def _checkpoint_metadata(packed, *, receipt, qualified_runtime, code_pins, jobs, at):
    """Pending shared ABI is explicit; no flag/old digest enables this path."""
    require({HISTORY_MODULE, PRODUCER_HISTORY_TEST} <= set(code_pins), "SOURCE_PINNED_PARENT_HISTORY_HELPER_REQUIRED")
    history = importlib.import_module("nfl_lab.audit_weekly_grade_history_v1")
    validator = getattr(history, "validate_parent_sidecar", None)
    require(callable(validator), "PARENT_HISTORY_METADATA_VALIDATOR_UNAVAILABLE")
    parsed = _unpack(packed, packed_cap=LIMITS["sidecar_bytes"], plain_cap=LIMITS["sidecar_plain_bytes"])
    value = validator(packed, receipt=deepcopy(receipt), qualified_runtime=deepcopy(qualified_runtime),
        code_pins=deepcopy(code_pins), jobs=deepcopy(jobs), at=at)
    require(type(value) is dict and value == parsed and set(value) == history.SIDECAR_KEYS,
        "EXACT_VALIDATED_PARENT_HISTORY_SIDECAR_BYTES")
    require(all(value[k] == receipt[k] for k in ("feed_sha256", "source_sha", "run_id", "root_go_sha256", "workflow_sha256", "epoch_sha256"))
        and value["repository"] == c.REPO, "EXACT_PARENT_HISTORY_RECEIPT_BINDINGS")
    template._metadata(value)
    return dict(sha256=c.sha(packed))


class _Capture:
    def __init__(self, receipt, packed_sha256, checkpoint, state_head, registration_sha256, initial, jobs, run, key):
        require(key is _KEY, "LIVE_PARENT_CAPTURE_DISCOVERY_REQUIRED")
        self.receipt, self.checkpoint = deepcopy(receipt), deepcopy(checkpoint)
        self.packed_sha256, self.state_head = packed_sha256, state_head
        self.registration_sha256, self.initial = registration_sha256, initial
        self.jobs, self.run = deepcopy(jobs), deepcopy(run)
        self._sha = c.digest(self._state())

    def _state(self):
        return [self.receipt, self.checkpoint, self.packed_sha256, self.state_head, self.registration_sha256, self.initial, self.jobs, self.run]

    def verify(self, parent):
        require(self._sha == c.digest(self._state()) and self.registration_sha256 == parent.seal.registration_sha256,
            "PARENT_CAPTURE_SCOPE_OR_INTEGRITY_CHANGED")
        p = c.decode(parent.registration_bytes)
        require(self.initial is False and self.receipt["feed_sha256"] != p["readiness"]["receipt_bindings"]["feed_sha256"]
            and self.receipt["run_id"] != p["readiness"]["run_id"]
            and self.receipt["source_sha"] == p["producer"]["source_sha"]
            and self.receipt["workflow_sha256"] == p["producer"]["workflow_sha256"]
            and self.receipt["policy_sha256"] == parent.seal.document["static_public_policy_sha256"]
            and type(self.checkpoint) is dict and set(self.checkpoint) == {"sha256"} and c.hashed(self.checkpoint["sha256"]),
            "SAME_SOURCE_OPS_CAPTURE_AND_CHECKPOINT_REQUIRED")
        return self

    def recheck(self, parent, api):
        self.verify(parent)
        after = api.get(c.run_url(self.receipt["run_id"]))
        c.stable(self.run, after)
        listing = api.get(c.jobs_url(self.receipt["run_id"]))
        p = c.decode(parent.registration_bytes)
        spec = p["readiness"] if self.initial else p["producer"]
        for role in c.ROLES:
            ref = self.receipt["jobs"][role]
            require(c.job(listing, self.receipt["run_id"], spec, ref["job_id"], status="completed",
                api_id=ref["api_job_id"]) == self.jobs[role], "PRIOR_CAPTURE_CHANGED_BEFORE_ROOT_BUILD")

    def __reduce__(self):
        raise ParentError("PARENT_CAPTURE_JSON_IS_NOT_AUTHORITY")


def _discover(parent, document, api, clock):
    p, policy = c.decode(parent.registration_bytes), _policy(parent, document)
    head = api.state_head()
    records = _filenames(api, head)
    ready = p["readiness"]
    anchors = [r for r in records if r["feed_sha256"] == ready["receipt_bindings"]["feed_sha256"]]
    require(len(anchors) == 1, "SEALED_READINESS_DATED_FEED_FILENAME_REQUIRED")
    anchor = anchors[0]
    candidates = [r for r in records if c.utc(r["stamp"]) >= c.utc(anchor["stamp"])]
    selected = None
    for record in candidates[:LIMITS["candidate_receipts"]]:
        raw = api.content(PUBLIC_ROOT + "/receipts/" + record["feed_sha256"] + ".json.gz", head, LIMITS["receipt_bytes"])
        receipt = _receipt(raw)
        require(receipt["feed_sha256"] == record["feed_sha256"] and receipt["feed_bytes"] == record["bytes"]
            and c.utc(receipt["created_at"]) == c.utc(record["stamp"]), "PUBLIC_FILENAME_RECEIPT_HASH_SIZE_AND_CLOCK")
        initial = record["feed_sha256"] == anchor["feed_sha256"]
        if initial:
            require(c.sha(raw) == ready["receipt_sha256"] and c.sha(c.canonical(receipt)) == ready["receipt_body_sha256"]
                and receipt["source_sha"] == ready["source_sha"] and receipt["run_id"] == ready["run_id"]
                and receipt["workflow_sha256"] == ready["workflow_sha256"]
                and all(receipt[k] == v for k, v in ready["receipt_bindings"].items()), "EXACT_SEALED_INITIAL_COUNT7_READINESS")
            # Foundation metadata can be discovered, but cannot authorize the
            # BOT retained restore path under the newly registered Ops policy.
            continue
        elif not (receipt["source_sha"] == p["producer"]["source_sha"]
            and receipt["policy_sha256"] == document["root_template"]["publication_registration"]["policy_sha256"]
            and receipt["recipe_registration_sha256"] == policy["producer_policy_sha256"]):
            continue
        require(record["week"] == anchor["week"], "NEW_WEEK_SELECTION_AND_ROLLOVER_NOT_WIRED")
        require(receipt["run_id"] != parent.proof.document["run_id"] and (initial
            or receipt["workflow_sha256"] == p["producer"]["workflow_sha256"]), "DISTINCT_SOURCE_BOUND_PRIOR_CAPTURE")
        jobs, actual_run = _completed(api, p, receipt, initial=initial,
            before=parent.proof.document["scheduled_parent"]["job_started_at"], clock=clock)
        sidecar = api.content("state/controller-v1/grade-checkpoints/" + receipt["feed_sha256"] + ".json.gz",
            head, LIMITS["sidecar_bytes"])
        checkpoint = _checkpoint_metadata(sidecar, receipt=receipt, qualified_runtime=document["root_template"]["qualified_runtime"],
            code_pins=p["producer"]["code_pins"], jobs=jobs, at=clock())
        selected = _Capture(receipt, c.sha(raw), checkpoint, head, parent.seal.registration_sha256, initial, jobs, actual_run, _KEY)
        break
    require(selected is not None, "SAME_SOURCE_OPS_CAPTURE_AND_CHECKPOINT_REQUIRED")
    return selected


class _HistoryCapture:
    """Process-only result of completed API/source and fresh private reads."""
    def __init__(self, receipt, packed_sha256, locator, checkpoint, state_head, parent, cohorts, key):
        require(key is _KEY,"LIVE_PARENT_HISTORY_DISCOVERY_REQUIRED")
        self.receipt,self.packed_sha256=deepcopy(receipt),packed_sha256
        self.locator,self.checkpoint=deepcopy(locator),deepcopy(checkpoint)
        self.state_head,self.registration_sha256=state_head,parent.seal.registration_sha256
        self.cohorts=deepcopy(cohorts);self.process=store.process_identity()
        self._sha=c.digest(self._state())

    def _state(self):
        return [self.receipt,self.packed_sha256,self.locator,self.checkpoint,self.state_head,self.registration_sha256,self.cohorts,self.process]

    def verify(self,parent):
        require(self._sha==c.digest(self._state()) and self.process==store.process_identity()
            and self.registration_sha256==parent.seal.registration_sha256,"LIVE_PARENT_HISTORY_SCOPE_OR_INTEGRITY_CHANGED")
        p=c.decode(parent.registration_bytes)
        require(self.locator["anchor"]==dict(feed_sha256=self.receipt["feed_sha256"],receipt_sha256=self.packed_sha256)
            and self.receipt["source_sha"]==self.locator["cohort"]["source_sha"]==p["producer"]["source_sha"]
            and self.receipt["policy_sha256"]==parent.seal.document["static_public_policy_sha256"],"SAME_SOURCE_HISTORY_AND_ORIGINAL_ANCHOR")
        return self

    def recheck(self,parent,api):
        self.verify(parent);p=c.decode(parent.registration_bytes)
        for receipt,jobs,run in self.cohorts:
            c.stable(run,api.get(c.run_url(receipt["run_id"])))
            listing=api.get(c.jobs_url(receipt["run_id"]))
            for role in c.ROLES:
                ref=receipt["jobs"][role]
                require(c.job(listing,receipt["run_id"],p["producer"],ref["job_id"],status="completed",
                    api_id=ref["api_job_id"])==jobs[role],"HISTORY_COHORT_CHANGED_BEFORE_ROOT_BUILD")

    def __reduce__(self):raise ParentError("SAVED_HISTORY_METADATA_IS_NOT_PARENT_AUTHORITY")


def _discover_history(parent,document,api,clock,client,storage,workspace):
    """V2 opt-in; no successful new feed is required for a grading-only run."""
    from . import audit_weekly_grade_history_v1 as history
    p,policy=c.decode(parent.registration_bytes),_policy(parent,document)
    head=api.state_head();entries=_listing(api,history.LOCATOR_ROOT,head)
    name=history.latest_locator(entries)
    raw=api.content(history.LOCATOR_ROOT+"/"+name,head,LIMITS["sidecar_bytes"])
    value=history.metadata_document(raw)
    require(type(value) is dict and set(value)==history.LOCATOR_KEYS
        and history.locator_filename(value)==name,"EXACT_LATEST_HISTORY_FILENAME_AND_READER_CLOCK")
    anchor=value["anchor"];cohort=value["cohort"]
    history.validate_cohort(cohort)
    receipt_raw=api.content(PUBLIC_ROOT+"/receipts/"+anchor["feed_sha256"]+".json.gz",head,LIMITS["receipt_bytes"])
    receipt=_receipt(receipt_raw)
    require(c.sha(receipt_raw)==anchor["receipt_sha256"] and receipt["feed_sha256"]==anchor["feed_sha256"]
        and receipt["source_sha"]==cohort["source_sha"]==p["producer"]["source_sha"]
        and receipt["policy_sha256"]==document["root_template"]["publication_registration"]["policy_sha256"]
        and receipt["recipe_registration_sha256"]==policy["producer_policy_sha256"]
        and receipt["run_id"]!=p["readiness"]["run_id"] and cohort["run_id"]!=parent.proof.document["run_id"],
        "SAME_SOURCE_POLICY_OPS_HISTORY_NO_COUNT7_OR_IMPLICIT_MIGRATION")
    before=parent.proof.document["scheduled_parent"]["job_started_at"]
    jobs,run=_completed(api,p,cohort,initial=False,before=before,clock=clock)
    cohorts=[(cohort,jobs,run)]
    if receipt["run_id"]!=cohort["run_id"]:
        old_jobs,old_run=_completed(api,p,receipt,initial=False,before=before,clock=clock)
        cohorts.append((receipt,old_jobs,old_run))
    else:require(cohort["kind"]=="CAPTURE_AND_GRADE" and receipt["jobs"]==cohort["jobs"],"DISTINCT_GRADE_ONLY_RUN_NO_RELABELING")
    history.locator_metadata(raw,receipt=receipt,qualified_runtime=document["root_template"]["qualified_runtime"],
        code_pins=p["producer"]["code_pins"],jobs=jobs,at=clock())
    pins={**value["sidecar"]["grade_code_pins"],**value["sidecar"]["checkpoint_helper_sha256"],
        **value["helper_sha256"],c.WORKFLOW:cohort["workflow_sha256"]}
    # Authenticate literal commit/blob bytes BEFORE any private history GET.
    for path,sha in sorted(pins.items()):
        require(c.sha(api.content(path,cohort["source_sha"],history.LIMITS["source_bytes"]))==sha,
            "HISTORY_EXECUTABLE_SOURCE_CHANGED_OR_ADAPTER_REQUIRED")
    require(type(client) is template.ParentGETClient,"ACTUAL_PRIVATE_TEMPLATE_READER_REUSED")
    descriptor=value["sidecar"]["evidence_descriptor"];entry=descriptor["entry"]
    client.asset_ids.update({descriptor["manifest_asset_id"],entry["payload_asset_id"]})
    client.guard();client.draft()
    saved=client.read_asset(descriptor["manifest_asset_id"],"manifest-"+descriptor["manifest_sha256"]+".json",
        descriptor["manifest_bytes"],descriptor["manifest_sha256"])
    require(saved==store.canonical(entry),"EXACT_HISTORY_EVIDENCE_NATIVE_MANIFEST")
    payload=entry["payload"]
    packed=client.read_asset(entry["payload_asset_id"],entry["payload_name"],payload["bytes"],payload["sha256"])
    client.draft();client.guard()
    history.validate_parent_envelope(packed,value,client,jobs,code_pins=p["producer"]["code_pins"],
        static_root=document["root_template"],at=clock())
    storage.register_root(workspace/"history-metadata")
    storage.write_bytes(workspace/"history-metadata/ORIGINAL_READER_EVIDENCE.json.gz",packed)
    reference=dict(schema_version=history.LOCATOR_REF,path=name,sha256=c.sha(raw))
    return _HistoryCapture(receipt,c.sha(receipt_raw),value,reference,head,parent,cohorts,_KEY).verify(parent)


def daily_claim_id(registration_sha256, producer_source_sha, at):
    """Pure daily ID; no Root or claim-body SHA creates a self-reference."""
    require(c.hashed(registration_sha256) and c.hashed(producer_source_sha, 40), "LITERAL_DAILY_CLAIM_SOURCE_BINDINGS")
    return c.digest(dict(schema_version=VERSION + "-daily-key", repository=c.REPO,
        registration_sha256=registration_sha256, producer_source_sha=producer_source_sha,
        chicago_date=c.utc(at).astimezone(CHICAGO).date().isoformat()))


def _build_root(parent, document, capture, at, *, plan=None):
    require(type(parent) is bootstrap.Parent and type(capture) in {_Capture,_HistoryCapture}, "LIVE_PARENT_AND_CAPTURE_REQUIRED")
    capture.verify(parent)
    parent.seal.verify()
    p = c.decode(parent.registration_bytes)
    plain = store.canonical(document)
    require(c.sha(plain) == parent.template_descriptor["template_sha256"]
        and len(plain) == parent.template_descriptor["template_bytes"], "UNCHANGED_PRIVATE_TEMPLATE_AT_ROOT_BUILD")
    template.prepare(document)
    root = deepcopy(document["root_template"])
    at = c.utc(at)
    require(c.utc(parent.proof.document["scheduled_parent"]["verified_at_utc"]) <= at, "ROOT_ISSUED_AFTER_ACTUAL_PARENT_PROOF")
    claim_id = daily_claim_id(parent.seal.registration_sha256, p["producer"]["source_sha"], at)
    root.update(approved=True, issued_at_utc=at.isoformat(), expires_at_utc=(at + timedelta(seconds=3600)).isoformat(),
        operation="RECURRING_CAPTURE", effective_epoch=dict(schema_version=CONTEXT_SCHEMA,
            controller_context=c.controller_context(parent.seal.registration_sha256,
                parent.proof.document["scheduled_parent"], claim_id),
            previous_capture=dict(feed_sha256=capture.receipt["feed_sha256"], receipt_sha256=capture.packed_sha256),
            previous_checkpoint=deepcopy(capture.checkpoint)))
    if type(capture) is _HistoryCapture:
        from . import audit_weekly_grade_history_v1 as history
        require(document["schema_version"]==template.VERSION+"-static-v2" and plan is None,"EXPLICIT_NEW_TEMPLATE_AND_PRIVATE_HISTORY_ROUTING")
        root["effective_epoch"].update(schema_version=history.CONTEXT_V4,
            plan=history.next_plan(capture.locator["planning"],at=at))
    elif plan is not None:
        require(type(plan) is dict and set(plan)=={"kind","season","week"}
            and plan["kind"] in {"GRADE_ONLY","FUTURE_CAPABLE"}
            and type(plan["season"]) is int and 2019<=plan["season"]<=2100
            and type(plan["week"]) is int and 1<=plan["week"]<=18,"EXPLICIT_CLOSED_RECURRING_PLAN")
        root["effective_epoch"]["schema_version"]="audit-weekly-recurring-v3-context"
        root["effective_epoch"]["plan"]=deepcopy(plan)
    require(set(root) == template.ROOT_KEYS and all(root[k] == document["root_template"][k] for k in set(root) - DYNAMIC_FIELDS)
        and root["code_pins"] == p["producer"]["code_pins"] and root["source_sha"] == p["producer"]["source_sha"]
        and root["workflow_ref"] == c.REPO + "/" + c.WORKFLOW + "@refs/heads/" + p["producer"]["branch"]
        and root["single_writer_group"] == c.GROUP and root["jobs"] == {r: p["producer"]["jobs"][r] for r in c.ROLES}
        and root["failure_restorer"] == p["producer"]["jobs"]["evidence"], "EXACT_FIVE_DYNAMIC_ROOT_FIELDS_ONLY")
    raw = c.canonical(root)
    require(raw == store.canonical(root) and 0 < len(raw) <= LIMITS["root_bytes"], "BOUNDED_DUAL_CANONICAL_PRIVATE_ROOT")
    c.due(parent.proof.document["scheduled_parent"]["event"], at, cadence=p["cadence"])
    return root, raw


def _fast_guard(parent, env, api, source_root, read_head, clock, *, before_run=None):
    p = _live(parent, env, source_root, read_head, clock)
    scheduled = parent.proof.document["scheduled_parent"]
    run = c.checked_run(api.get(c.run_url(scheduled["run_id"])), scheduled["run_id"], p["parent"], c.OWNER,
        event=scheduled["event"], status="in_progress")
    job = c.job(api.get(c.jobs_url(scheduled["run_id"])), scheduled["run_id"], p["parent"], scheduled["job_id"],
        status="in_progress", api_id=scheduled["api_job_id"])
    require(job["started_at"] == scheduled["job_started_at"] and job.get("completed_at") is None,
        "CURRENT_PARENT_JOB_CHANGED_BEFORE_MUTATION")
    if before_run is not None: c.stable(before_run, run)
    c.check_head(api, p)
    return run


def _claim(parent, root, raw_root, capture, api, live_check, clock):
    capture.verify(parent)
    ledger = api.ledger
    require(ledger.counts["state"] + 14 <= LIMITS["state_calls"], "RESERVED_FINITE_CLAIM_AND_DISPATCH_ATTEMPTS")
    claim_id = root["effective_epoch"]["controller_context"]["claim_id"]
    path = c.claim_path(claim_id)
    expected = capture.state_head
    require(api.state_head(state=True) == expected, "LAB_STATE_HEAD_CHANGED_BEFORE_CLAIM")
    existing = ledger.request(c.contents_url(path, expected), lane="state", cap=32 << 10)
    require(existing.status == 404, "DAILY_DISPATCH_CLAIM_ALREADY_EXISTS_OR_AMBIGUOUS")
    history = ledger.request(c.claim_history(path), lane="state", cap=64 << 10)
    require(history.status == 200 and c.decode(history.body) == [], "CREATE_ONLY_DAILY_CLAIM_HISTORY_REQUIRED")
    base = ledger.request(c.API + "/git/commits/" + expected, lane="state")
    require(base.status == 200, "EXACT_CLAIM_BASE_GIT_COMMIT_REQUIRED")
    commit = c.decode(base.body)
    require(commit.get("sha") == expected and c.hashed(commit.get("tree", {}).get("sha"), 40), "EXACT_CLAIM_BASE_TREE")
    scheduled = parent.proof.document["scheduled_parent"]
    p = c.decode(parent.registration_bytes)
    claim = dict(schema_version=c.VERSION + "-claim", repository=c.REPO, claim_id=claim_id,
        registration_sha256=parent.seal.registration_sha256, parent_run_id=scheduled["run_id"],
        parent_api_job_id=scheduled["api_job_id"], parent_source_sha=p["parent"]["source_sha"],
        producer_source_sha=p["producer"]["source_sha"], root_go_sha256=c.sha(raw_root), created_at_utc=c.utc(clock()).isoformat())
    require(set(claim) == c.CLAIM_KEYS and c.utc(root["issued_at_utc"]) <= c.utc(claim["created_at_utc"])
        < c.utc(root["expires_at_utc"]), "CLOSED_PUBLIC_DAILY_CLAIM_ONLY")
    claim_raw = c.canonical(claim)
    def mutate(url, value, *, method="POST", status=201):
        live_check()
        require(c.utc(clock()) < c.utc(root["expires_at_utc"]), "PARENT_ROOT_EXPIRED_BEFORE_CLAIM_MUTATION")
        response = ledger.request(url, lane="state", method=method, value=value)
        require(response.status == status, "CLAIM_WRITE_UNCONFIRMED_NO_RETRY")
        return c.decode(response.body)
    blob = mutate(c.API + "/git/blobs", dict(content=base64.b64encode(claim_raw).decode(), encoding="base64"))
    require(blob.get("sha") == c.blob_sha(claim_raw), "ACTUAL_CANONICAL_CLAIM_GIT_BLOB")
    tree = mutate(c.API + "/git/trees", dict(base_tree=commit["tree"]["sha"],
        tree=[dict(path=path, mode="100644", type="blob", sha=blob["sha"])]))
    require(c.hashed(tree.get("sha"), 40), "ACTUAL_ONE_FILE_CLAIM_TREE_REQUIRED")
    bot = dict(name=c.BOT["login"], email="41898282+github-actions[bot]@users.noreply.github.com")
    created = mutate(c.API + "/git/commits", dict(message="Record daily controller dispatch claim",
        tree=tree["sha"], parents=[expected], author=bot, committer=bot))
    require(c.hashed(created.get("sha"), 40) and type(created.get("parents")) is list and len(created["parents"]) == 1
        and created["parents"][0].get("sha") == expected
        and created.get("tree", {}).get("sha") == tree["sha"], "ONE_PARENT_CREATE_ONLY_CLAIM_COMMIT")
    require(api.state_head(state=True) == expected, "LAB_STATE_HEAD_RACED_NO_RETRY")
    result = mutate(STATE_UPDATE_URL, dict(sha=created["sha"], force=False), method="PATCH", status=200)
    require(result.get("ref") == "refs/heads/lab-state" and result.get("object", {}).get("sha") == created["sha"]
        and result["object"].get("type") == "commit" and api.state_head(state=True) == created["sha"], "EXACT_NONFORCE_CLAIM_REF_READBACK")
    actual = ledger.request(c.API + "/commits/" + created["sha"], lane="state")
    require(actual.status == 200, "ACTUAL_ADDED_CLAIM_COMMIT_READBACK")
    observed = c.decode(actual.body)
    require(observed.get("sha") == created["sha"] and type(observed.get("parents")) is list and len(observed["parents"]) == 1
        and observed["parents"][0].get("sha") == expected
        and type(observed.get("files")) is list and len(observed["files"]) == 1
        and observed["files"][0].get("filename") == path and observed["files"][0].get("status") == "added"
        and observed["files"][0].get("sha") == c.blob_sha(claim_raw)
        and (c.actor(observed.get("committer"), c.OWNER) or c.actor(observed.get("committer"), c.BOT)),
        "GENUINE_ONE_ADDED_FILE_PUBLIC_CLAIM_COMMIT")
    readback = ledger.request(c.contents_url(path, created["sha"]), lane="state", cap=64 << 10)
    require(readback.status == 200, "ACTUAL_PUBLIC_CLAIM_BODY_READBACK")
    value = c.decode(readback.body)
    try: physical = base64.b64decode(value.get("content", "").replace("\n", ""), validate=True)
    except (ValueError, TypeError): raise ParentError("INVALID_PUBLIC_CLAIM_READBACK_ENCODING") from None
    require(value.get("type") == "file" and value.get("path") == path and value.get("encoding") == "base64"
        and value.get("size") == len(claim_raw) and value.get("sha") == c.blob_sha(claim_raw) and physical == claim_raw,
        "EXACT_PUBLIC_CLAIM_CANONICAL_ROOT_HASH_READBACK")
    final_history = ledger.request(c.claim_history(path), lane="state", cap=64 << 10)
    history_value = c.decode(final_history.body) if final_history.status == 200 else None
    require(type(history_value) is list and len(history_value) == 1 and type(history_value[0]) is dict
        and history_value[0].get("sha") == created["sha"],
        "ORIGINAL_ONE_CREATE_DAILY_CLAIM_HISTORY_READBACK")
    return dict(claim_id=claim_id, claim_sha256=c.sha(claim_raw), claim_commit_sha=created["sha"])


def run(env, *, source_root=ROOT, work_root=None, transport=None, clock=c.now, read_head=c.git_head):
    """Only an actual current registered parent can reach a mutation/dispatch."""
    ledger = _Ledger(env.get("GITHUB_TOKEN"), transport)
    parent = bootstrap.authorize_parent(env, source_root, metadata_get=ledger.bootstrap_get,
        clock=clock, read_head=read_head, registry_version=2)
    p = _live(parent, env, source_root, read_head, clock)
    workspace, journal = _workspace(env, work_root)
    ledger.journal = journal
    document,private_client,storage = _recover(parent, env, source_root, read_head, clock, ledger, workspace, journal)
    api = _API(ledger)
    capture = (_discover_history(parent,document,api,clock,private_client,storage,workspace)
        if document["schema_version"]==template.VERSION+"-static-v2" else _discover(parent, document, api, clock))
    # Refresh through the unchanged actual verifier, using a separately counted
    # GET lane. The original bootstrap's 32-call cap is not enlarged or reset.
    parent.proof = c.verify_parent(parent.registration_bytes, sealed_sha256=parent.seal.registration_sha256,
        env=bootstrap._environment(env), event_bytes=bootstrap._event(env, None), source_root=source_root,
        metadata_get=ledger.bootstrap_get, clock=clock, read_head=read_head)
    _live(parent, env, source_root, read_head, clock)
    capture.recheck(parent, api)
    root, raw_root = _build_root(parent, document, capture, clock())
    before = _fast_guard(parent, env, api, source_root, read_head, clock)
    def live_check():
        ledger.budget()
        _live(parent, env, source_root, read_head, clock)
    claimed = _claim(parent, root, raw_root, capture, api, live_check, clock)
    _fast_guard(parent, env, api, source_root, read_head, clock, before_run=before)
    live_check()
    require(c.utc(clock()) < c.utc(root["expires_at_utc"]), "PARENT_ROOT_EXPIRED_BEFORE_ENQUEUE")
    if root["effective_epoch"]["schema_version"]=="audit-weekly-recurring-v4-context":
        plan=root["effective_epoch"]["plan"]
        require(plan["kind"]=="GRADE_ONLY" or c.utc(clock())<c.utc(plan["deadline_utc"]),"FROZEN_DEADLINE_ELAPSED_BEFORE_ENQUEUE")
    response = ledger.request(DISPATCH_URL, lane="state", method="POST", cap=4096, value=dict(ref=p["producer"]["branch"],
        inputs=dict(mode=c.MODE, inference_builder_go_json=raw_root.decode(), inference_builder_go_sha256=c.sha(raw_root))))
    require(response.status == 204 and response.body == b"", "DISPATCH_POST_UNCONFIRMED_NO_RETRY")
    # No API calls, waits or child status checks follow the accepted enqueue.
    return dict(schema_version=VERSION + "-result", state="ENQUEUE_ONCE_AND_EXIT", dispatches=1, dispatch_http_status=204,
        parent_run_id=env["GITHUB_RUN_ID"], registration_sha256=parent.seal.registration_sha256, root_go_sha256=c.sha(raw_root),
        previous_capture=dict(feed_sha256=capture.receipt["feed_sha256"], receipt_sha256=capture.packed_sha256),
        previous_checkpoint=capture.checkpoint, **claimed, HTTP_calls=sum(ledger.counts.values()),
        HTTP_by_lane=dict(ledger.counts), child_completion_claimed=False, activation_authorized=False, fits=0,
        public_root=False, automatic_retry=False, parent_return_rule=c.RETURN_RULE)


def workflow_contract():
    """Concrete reviewable integration data, never a workflow/guard mutation."""
    route = "steps.parent_route.outputs.requested == 'true' && steps.parent_cadence.outputs.due == 'true'"
    return dict(workflow=c.WORKFLOW, job_id="lab", cadence=deepcopy(c.PARENT_CADENCE), concurrency=deepcopy(c.CONCURRENCY),
        required_job_permissions=dict(contents="write", actions="write"),
        checkout=dict(uses="actions/checkout@v4", **{"with":dict(ref="${{ github.sha }}",
            **{"persist-credentials":False, "fetch-depth":0})}),
        step=dict(name="Enqueue one qualified same-source Ops capture and return", id="weekly_parent", **{"if":route},
            env=dict(GITHUB_TOKEN="${{ github.token }}"),
            run="timeout --signal=KILL --kill-after=1s 180s python -I -B tools/audit_weekly_parent_v1.py --execute > controller-parent-result.json"),
        insert_after=["parent_route", "parent_cadence"], requires_accepted_versioned_readiness_guard=True,
        root_inputs_or_job_environment=False, legacy_routes_remain_guarded=True,
        legacy_step_exclusion="steps.parent_route.outputs.requested != 'true' && steps.weekly_parent.outcome == 'skipped'",
        legacy_steps_requiring_exclusion=["daily", "grading", "training", "replay", "Persist only lab-derived forecasts and corrections"],
        scheduled_sunday_uses_parent_without_training=True, finish_existing_job_after_enqueue=True,
        result_artifact="controller-parent-result.json", result_contains_private_root=False,
        bootstrap_order=["REVIEW_AND_WIRE_EXISTING_WORKFLOW_WITH_GUARD_STILL_BLOCKING",
            "PIN_REVIEWED_PARENT_AND_PRODUCER_INVENTORIES_AND_EACH_WORKFLOW", "COMPLETE_NATIVE_THREE_JOB_OWNER_REGISTRATION",
            "VERIFY_NATIVE_ARTIFACT_AND_CREATE_ONLY_V2_REGISTRY", "COMPLETE_SEPARATE_DIRECT_OWNER_OPS_SMOKE_PREV_COUNT7_NULL_CHECKPOINT",
            "VERIFY_SAME_SOURCE_OPS_FEED_AND_QUALIFIED_GRADE_SIDECAR", "ACCEPT_COMBINED_READINESS_BEFORE_ACTIVATION"],
        clock_dependency=dict(research_chicago="07:36", website_chicago="08:06", legacy_research_chicago="08:36",
            scheduled_tick_before_website=True, actual_delivery_before_website_requires_operational_evidence=True,
            clock_policy_version=c.PARENT_POLICY, additional_scheduler=False))


def contract():
    """No IO, no active readiness claim and no caller-supplied Root authority."""
    return dict(schema_version=VERSION + "-contract", state="LIVE_SEALED_PARENT_AND_WORKFLOW_GATES_REQUIRED",
        API="run(env, *, source_root=ROOT, work_root=None, transport=None, clock=c.now, read_head=c.git_head)",
        registry_version=2, registry_path=bootstrap.LOCATOR_REGISTRY_PATH, required_pins=sorted(REQUIRED_PINS),
        workflow_integration=workflow_contract(),
        history_pins=[HISTORY_MODULE, HISTORY_TEST], producer_history_pins=[HISTORY_MODULE, PRODUCER_HISTORY_TEST], history_metadata_API=
            "grade_history.validate_parent_sidecar(packed, *, receipt, qualified_runtime, code_pins, jobs, at) -> exact parsed sidecar",
        context_schema=CONTEXT_SCHEMA, root_dynamic_fields=sorted(DYNAMIC_FIELDS), limits=dict(LIMITS),
        credential_variable="GITHUB_TOKEN", cadence=deepcopy(c.PARENT_CADENCE), legacy_cadence=deepcopy(c.CADENCE), concurrency=deepcopy(c.CONCURRENCY),
        manual_daily_uses_same_chicago_window=False, manual_daily_policy="EXISTING_OWNER_SOURCE_DAILY_EVENT_AND_LIVE_API_PROOF",
        automatic_daily_policy="VERSIONED_CHICAGO_0736_THROUGH_0756_NO_BACKFILL",
        sealed_initial_readiness_scope="ARTIFACT_AND_PIPELINE_FOUNDATION_ONLY", sealed_initial_readiness_permits_parent_enqueue=False,
        parent_enqueue_requires=["SAME_SOURCE_POLICY_RECIPE_SUCCESSFUL_OPS_FEED", "VALIDATED_PER_FEED_GRADE_CHECKPOINT_SIDECAR"],
        parent_previous_checkpoint_required=True, first_owner_ops_smoke_is_separate=True, first_owner_ops_smoke_checkpoint=None,
        default_remote_calls=0,
        default_POSTs=0, public_root=False, fits=0, child_completion_claimed=False,
        return_rule=c.RETURN_RULE, parent_remaining=["WORKFLOW_ACTIVATION_AND_READINESS_GUARD", "LAB_ACTIONS_WRITE_PERMISSION",
            "QUALIFIED_OWNER_OPS_FEED_AND_GRADE_SIDECAR", "MEASURED_DELIVERY_BEFORE_WEBSITE",
            "NEW_WEEK_SELECTION_AND_ROLLOVER"])
