"""Separate, zero-fit checkpoint recovery and future-manifest requalification.

Imports are deliberately stdlib-only until a qualified hosted replay. Original
models, manifests, fixtures, fit receipts and research replay are never replaced.
Remote traffic uses the established private client and is categorically GET-only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import types

VERSION = "audit-count-requalify-v1"
REPO = "NickNicky19/NFL-forecasting"
MODE = VERSION
RESTORE_JOB = "genuine-hosted-fixed-build-restore-v1"
ORIGINAL_SOURCE = "93e2019"
ORIGINAL_PINS = {
    "weekly_future_inference.py": "0689fdc2e3d0154d7431f7fb834d0684dbddd8f952cd5710e010e7fdd678fad7",
    "cdf_engine.py": "6a963111f4173a88affe90ca1ce17532cd5eb690a1f28b284e9fa4145eecb214",
    "role_boosting.py": "294e7e588215e7b7e98d6f1fb251eed31420921dff9a59e88434913133dbdf93",
    "direct_boosters.py": "475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f",
    "median_boosting.py": "c5bf8ef481c05027a2a1d4e1d19764920c0820f0614f60736826c17526e7799d",
    "baseline_correction.py": "077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2",
}
GO_KEYS = {
    "schema_version", "approved", "phase", "repository", "plan_sha256",
    "source_sha", "run_id", "job_id", "workflow_ref", "single_writer_group",
    "issued_at_utc", "expires_at_utc", "output_root", "local_cache", "local_state",
    "rights_review", "restore_receipt", "maximum_new_fits", "source_acquisitions",
    "remote_writes", "protected_outcome_reads",
    "owner_dispatch_sha256",
}
DISPATCH_KEYS = {"schema_version", "approved", "repository", "source_sha", "procedure_sha256",
    "parent_handoff_sha256", "logical_scope_sha256", "resources_sha256", "registered_at_utc",
    "expires_at_utc", "authorization_basis", "human_review_claim", "maximum_new_fits",
    "remote_writes", "protected_outcome_reads"}


class AuditGuardError(ValueError):
    """Only fixed public-safe audit guard codes may cross the logging boundary."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(value, code):
    if not value:
        raise AuditGuardError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def now():
    return datetime.now(timezone.utc)


def read_json(path, maximum=1 << 20):
    from . import gha_private_checkpoint as cp
    return cp.strict_json(read_bytes(path, maximum))


def read_bytes(path, maximum):
    from . import private_draft_store as core
    return core.read_local(path, maximum)


def private_write(path, body):
    path = Path(path)
    require(not path.exists(), "FRESH_PRIVATE_PACKAGE_REQUIRED")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)


def logical_scope(config):
    from . import gha_private_checkpoint as cp
    names = []
    for target, family, _ in cp.JOBS:
        names += [f"models/{target}/{family}/trained.joblib",
                  f"models/{target}/{family}/future-inference.json"]
    for name in config["source_names"]:
        names += ["source-cache/raw/" + name, "source-cache/raw/" + name + ".receipt.json"]
    names += ["control/" + name for name in config["control_allowlist"]]
    require(len(names) == len(set(names)) == 78, "EXACT78_LOGICAL_SCOPE")
    return sorted(names)


def shared_envelopes():
    from .weekly_generic_producer import LIMITS
    return dict(restore=dict(CPU_seconds=120, wall_seconds=180, address_space_bytes=512 << 20),
        requalify=dict(CPU_seconds=LIMITS["CPU_seconds"], wall_seconds=LIMITS["wall_seconds"],
            address_space_bytes=LIMITS["address_space_bytes"], RSS_bytes=LIMITS["RSS_bytes"],
            RSS_stop_margin_bytes=32 << 20, numerical_threads=LIMITS["numerical_threads"]))


def refresh_inventory(destination):
    """Normal existing gh auth, metadata GETs only; never emit its response/errors."""
    releases = []
    for page in range(1, 5):
        response = subprocess.run(["gh", "api", "--method", "GET",
            f"repos/{REPO}/releases?per_page=100&page={page}"], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        require(len(response.stdout) <= 2 << 20, "BOUNDED_RELEASE_METADATA")
        batch = json.loads(response.stdout)
        require(type(batch) is list and len(batch) <= 100, "RELEASE_METADATA_LIST")
        for record in batch:
            require(type(record.get("assets")) is list and len(record["assets"]) <= 128, "BOUNDED_ASSET_METADATA")
            releases.append({k: record[k] for k in ("id", "tag_name", "draft", "published_at", "created_at")} | {
                "assets": [{k: a.get(k) for k in ("id", "name", "size", "digest", "state")} for a in record["assets"]]})
        if len(batch) < 100:
            break
    else:
        raise AuditGuardError("COMPLETE_BOUNDED_RELEASE_METADATA_REQUIRED")
    private_write(destination, canonical(releases))
    return dict(repository=REPO, authenticated_metadata_only=True, HTTP_calls=page,
                private_body_reads=0, observed_at_utc=now().isoformat())


def prepare_package(checkout, inventory_path, destination, *, original_source=None):
    """Local metadata and public Git objects only; no token or private body I/O."""
    from . import private_draft_store as core
    from tools.owner_private_bootstrap_v1 import checkout_head
    root = Path(checkout).absolute()
    config_path = "config/gha-private-checkpoint-v3.json"
    registration_path = "config/weekly-initial-continuation-v6-registration.json"
    config = read_json(root / config_path)
    registration = read_json(root / registration_path)
    parent = registration["parent"]
    inventory_body = read_bytes(inventory_path, 2 << 20)
    inventory = json.loads(inventory_body)
    handoff = parent["handoff"]
    runtime = handoff["runtime_binding"]
    matches = [r for r in inventory if r.get("id") == runtime["release_id"]]
    require(len(matches) == 1 and matches[0]["draft"] is True
            and matches[0]["published_at"] is None
            and matches[0]["tag_name"] == runtime["tag_name"], "RETAINED_DRAFT_METADATA_REQUIRED")
    assets = matches[0]["assets"]
    descriptor = handoff["index_descriptor"]
    needed = [(descriptor["manifest_asset_id"], "manifest-" + descriptor["manifest_sha256"] + ".json", descriptor["manifest_bytes"]),
              (descriptor["entry"]["payload_asset_id"], descriptor["entry"]["payload_name"], descriptor["entry"]["payload"]["bytes"]),
              (runtime["canary_asset_id"], runtime["canary_name"], runtime["canary_bytes"])]
    for asset_id, name, size in needed:
        require(len([a for a in assets if (a.get("id"), a.get("name"), a.get("size")) == (asset_id, name, size)]) == 1,
                "RETAINED_EXACT_LOCATOR_METADATA_REQUIRED")
    if original_source is None:
        result = subprocess.run(["git", "show", ORIGINAL_SOURCE + ":nfl_lab/weekly_future_inference.py"],
                                cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        original = result.stdout
    else:
        original = read_bytes(original_source, 256 << 10)
    require(sha(original) == ORIGINAL_PINS["weekly_future_inference.py"], "ORIGINAL_SOURCE_HASH")
    pins = set(config["source_sha256"]) | {config_path, registration_path,
        "config/operational-source-policy-v2.json", "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json",
        "nfl_lab/audit_count_requalify_v1.py", "tools/audit_count_requalify_v1.py",
        "tools/private_draft_store_v2.py", "tools/owner_private_bootstrap_v1.py",
        "tools/review_direct_booster_screen_guard_v4.py", "tools/ngboost_law_software_v1.py",
        "nfl_lab/weekly_generic_producer.py", "requirements.lock", "config/weekly-generic-runtime-requirements-v1.lock"}
    pins |= {"nfl_lab/" + name for name in ORIGINAL_PINS}
    for optional in ("tools/audit_count_hosted_v1.py", "tools/audit_count_checkpoint_v1.py",
                     "nfl_lab/audit_count_checkpoint_v1.py", "requirements-hosted-fixed-build-v1.lock"):
        if (root / optional).is_file():
            pins.add(optional)
    plan = dict(schema_version=VERSION + "-plan", repository=REPO,
        state="PREPARED_REQUIRES_FRESH_HOSTED_GO", created_at_utc=now().isoformat(),
        checkout_head_at_preparation=checkout_head(root), source_policy_sha256=config["source_policy_sha256"],
        code_pins={p: sha(read_bytes(root / p, 2 << 20)) for p in sorted(pins)},
        parent=parent, checkpoint_config=config, logical_allowlist=logical_scope(config),
        original_code_pins=ORIGINAL_PINS,
        original_source=dict(name="original-weekly_future_inference.py", bytes=len(original), sha256=sha(original)),
        runtime_envelopes=shared_envelopes(),
        numerical_environment=read_json(root / "config/weekly-owner-private-bootstrap-v1.json")["numerical_environment"],
        inventory_witness=dict(sha256=sha(inventory_body), qualified_draft_assets=len(assets),
            qualified_draft_bytes=sum(a["size"] for a in assets), private_body_reads=0),
        limits=dict(maximum_new_fits=0, source_acquisitions=0, source_claims=0,
            remote_writes=0, protected_outcome_reads=0, global_private_bytes=512 << 20,
            retained_runtime_remote_bytes=32 << 20, HTTP_calls=360, core_operations=9,
            per_asset_bytes=8 << 20, per_manifest_bytes=256 << 10,
            CPU_seconds=120, wall_seconds=180, address_space_bytes=512 << 20),
        authority=dict(old_continuation_cutoff_utc=registration["input_cutoff_utc"],
            old_authority_reusable=False, fresh_GO_required=True, new_publication_authority=False),
        execution=dict(mode=MODE, job_id=RESTORE_JOB, permissions={"contents": "write", "actions": "read"},
            single_writer_group="nfl-lab-single-writer", run_attempt=1, event="workflow_dispatch",
            phases=["restore", "requalify"], same_job_private_files=True))
    destination = core.parents_safe(destination)
    require(not destination.exists(), "FRESH_PRIVATE_PACKAGE_REQUIRED")
    destination.mkdir(mode=0o700)
    body = canonical(plan)
    private_write(destination / "PLAN.json", body)
    private_write(destination / plan["original_source"]["name"], original)
    for phase in ("restore", "requalify"):
        template = dict(schema_version=VERSION + "-GO", approved=False, phase=phase,
            repository=REPO, plan_sha256=sha(body), source_sha=None, run_id=None,
            job_id=RESTORE_JOB, workflow_ref=None, single_writer_group="nfl-lab-single-writer",
            issued_at_utc=None, expires_at_utc=None, output_root=None, local_cache=None, local_state=None,
            rights_review=dict(approved=False, source_policy_sha256=plan["source_policy_sha256"],
                logical_allowlist=plan["logical_allowlist"], scope="OWNER_DELEGATED_PRIVATE_ONLY", human_review_claim=False),
            restore_receipt=None, maximum_new_fits=0, source_acquisitions=0,
            remote_writes=0, protected_outcome_reads=0,
            owner_dispatch_sha256=os.environ.get("AUDIT_COUNT_ROOT_GO_SHA256"))
        private_write(destination / ("GO." + phase + ".template.json"), canonical(template))
    dispatch = dict(schema_version=VERSION + "-owner-dispatch", approved=False, repository=REPO,
        source_sha=None, procedure_sha256=procedure_pin(plan), parent_handoff_sha256=sha(canonical(parent["handoff"])),
        logical_scope_sha256=sha(canonical(plan["logical_allowlist"])), resources_sha256=sha(canonical(plan["runtime_envelopes"])),
        registered_at_utc=None, expires_at_utc=None, authorization_basis="OWNER_DELEGATED_PRIVATE_ONLY", human_review_claim=False,
        maximum_new_fits=0, remote_writes=0, protected_outcome_reads=0)
    private_write(destination / "OWNER_DISPATCH.template.json", canonical(dispatch))
    private_write(destination / "PLAN.sha256", (sha(body) + "\n").encode())
    return dict(state=plan["state"], plan_sha256=sha(body), logical_files=78, model_pairs=18,
                fits=0, private_body_reads=0, hosted_execution=False)


def procedure_pin(plan):
    return sha(canonical({name: plan["code_pins"][name] for name in
                         ("nfl_lab/audit_count_requalify_v1.py", "tools/audit_count_requalify_v1.py")}))


def owner_dispatch(plan, env):
    """The existing two bootstrap inputs carry only a closed digest envelope."""
    from . import private_draft_store as core
    if env.get("AUDIT_COUNT_ROOT_GO_JSON") is not None:
        # Parent owns this separately reviewed bridge and its distinct closed GO.
        # Reuse that real authority; do not require another approval protocol.
        from tools.audit_count_hosted_v1 import checked_root
        text = env["AUDIT_COUNT_ROOT_GO_JSON"]
        expected = env.get("AUDIT_COUNT_ROOT_GO_SHA256", "")
        require(0 < len(text.encode()) <= 16384 and sha(text.encode()) == expected, "EXACT_OWNER_ROOT_DISPATCH_DIGEST")
        approved = checked_root(text.encode(), expected, env)
        require(core.utc(approved["issued_at_utc"]) > core.utc(plan["authority"]["old_continuation_cutoff_utc"]), "FRESH_OWNER_ROOT_AUTHORITY_REQUIRED")
        event = read_json(env["GITHUB_EVENT_PATH"], 256 << 10)
        require(event.get("inputs", {}).get("inference_builder_go_json") == text
                and event["inputs"].get("inference_builder_go_sha256") == expected, "EXACT_OWNER_ROOT_INFERENCE_GO_INPUTS")
        return approved, expected
    text = env.get("BOOTSTRAP_LOCATORS_JSON", "")
    expected = env.get("BOOTSTRAP_LOCATORS_SHA256", "")
    require(0 < len(text.encode()) <= 16384 and sha(text.encode()) == expected, "EXACT_OWNER_DISPATCH_DIGEST")
    document = json.loads(text)
    require(set(document) == DISPATCH_KEYS and document["schema_version"] == VERSION + "-owner-dispatch"
            and document["approved"] is True and document["repository"] == REPO
            and document["source_sha"] == env.get("GITHUB_SHA")
            and document["procedure_sha256"] == procedure_pin(plan)
            and document["parent_handoff_sha256"] == sha(canonical(plan["parent"]["handoff"]))
            and document["logical_scope_sha256"] == sha(canonical(plan["logical_allowlist"]))
            and document["resources_sha256"] == sha(canonical(shared_envelopes()))
            and document["authorization_basis"] == "OWNER_DELEGATED_PRIVATE_ONLY" and document["human_review_claim"] is False
            and all(type(document[k]) is int and document[k] == 0 for k in
                    ("maximum_new_fits", "remote_writes", "protected_outcome_reads")), "EXACT_OWNER_DISPATCH_SCOPE")
    start, end = core.utc(document["registered_at_utc"]), core.utc(document["expires_at_utc"])
    require(core.utc(plan["authority"]["old_continuation_cutoff_utc"]) < start <= now() < end
            and 0 < (end - start).total_seconds() <= 3600, "FRESH_OWNER_DISPATCH_REQUIRED")
    event = read_json(env["GITHUB_EVENT_PATH"], 256 << 10)
    inputs = event.get("inputs", {})
    require(event.get("repository", {}).get("full_name") == REPO and inputs.get("mode") == MODE
            and inputs.get("bootstrap_locators_json") == text and inputs.get("bootstrap_locators_sha256") == expected,
            "EXACT_REAL_OWNER_DISPATCH_INPUTS")
    return document, expected


def seal_phase(plan, plan_sha, phase, env, checkout):
    """Derive a local GO only from the fresh explicit owner dispatch approval."""
    from . import private_draft_store as core, gha_private_checkpoint as cp
    envelope, dispatch_sha = owner_dispatch(plan, env)
    root = core.parents_safe(env["RUNNER_TEMP"]) / (VERSION + "-" + env["GITHUB_RUN_ID"])
    go = dict(schema_version=VERSION + "-GO", approved=True, phase=phase, repository=REPO,
        plan_sha256=plan_sha, source_sha=env["GITHUB_SHA"], run_id=env["GITHUB_RUN_ID"], job_id=RESTORE_JOB,
        workflow_ref=env["GITHUB_WORKFLOW_REF"], single_writer_group="nfl-lab-single-writer",
        issued_at_utc=now().isoformat(), expires_at_utc=envelope["expires_at_utc"], output_root=str(root),
        local_cache=str(root / "cache"), local_state=str(root / "state"),
        rights_review=dict(approved=True, source_policy_sha256=plan["source_policy_sha256"],
            logical_allowlist=plan["logical_allowlist"], scope="OWNER_DELEGATED_PRIVATE_ONLY", human_review_claim=False),
        restore_receipt=cp.binding(root / "RESTORE_RECEIPT.json") if phase == "requalify" else None,
        maximum_new_fits=0, source_acquisitions=0, remote_writes=0, protected_outcome_reads=0,
        owner_dispatch_sha256=dispatch_sha)
    validate_go(plan, plan_sha, go, phase, env, checkout)
    return go


def validate_go(plan, plan_sha, go, phase, env, checkout):
    """No stale registration, credential fallback, fake clock or fake job lane."""
    from . import private_draft_store as core
    from tools.owner_private_bootstrap_v1 import checkout_head
    from tools.private_draft_store_v2 import actions_context
    require(set(go) == GO_KEYS and go["schema_version"] == VERSION + "-GO"
            and go["approved"] is True and go["phase"] == phase
            and go["repository"] == REPO and go["plan_sha256"] == plan_sha
            and go["single_writer_group"] == "nfl-lab-single-writer", "FRESH_CLOSED_PHASE_GO_REQUIRED")
    require(all(type(go[k]) is int and go[k] == 0 for k in
                ("maximum_new_fits", "source_acquisitions", "remote_writes", "protected_outcome_reads")), "ZERO_FIT_PRIVATE_ONLY_SCOPE")
    current = now()
    issued, expires = core.utc(go["issued_at_utc"]), core.utc(go["expires_at_utc"])
    require(issued <= current < expires and 0 < (expires - issued).total_seconds() <= 3600
            and issued > core.utc(plan["authority"]["old_continuation_cutoff_utc"]), "FRESH_GO_CLOCK_REQUIRED")
    envelope, dispatch_sha = owner_dispatch(plan, env)
    require(go["owner_dispatch_sha256"] == dispatch_sha
            and expires <= core.utc(envelope["expires_at_utc"])
            and plan["runtime_envelopes"] == shared_envelopes(), "EXACT_SHARED_ENVELOPE_AND_OWNER_GO")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPO
            and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_RUN_ATTEMPT") == "1"
            and env.get("STORE_PERMISSION") == "write" and env.get("GITHUB_ACTOR") == "NickNicky19"
            and env.get("GITHUB_ACTOR_ID") == "208912933" and env.get("GITHUB_JOB") == go["job_id"] == RESTORE_JOB
            and env.get("GITHUB_RUN_ID") == go["run_id"] != plan["parent"]["run_id"]
            and env.get("GITHUB_SHA") == go["source_sha"] == checkout_head(checkout)
            and env.get("GITHUB_WORKFLOW_REF") == go["workflow_ref"], "GENUINE_FRESH_OWNER_ACTIONS_REQUIRED")
    event = read_json(env["GITHUB_EVENT_PATH"], 256 << 10)
    require(event.get("repository", {}).get("full_name") == REPO
            and event.get("inputs", {}).get("mode") == MODE, "EXACT_NEW_DISPATCH_MODE_REQUIRED")
    for name, value in plan["numerical_environment"].items():
        require(env.get(name) == value, "EXACT_NUMERICAL_STARTUP_REQUIRED")
    require(plan["original_code_pins"] == ORIGINAL_PINS, "ORIGINAL_SOURCE_ALLOWLIST")
    require(plan["logical_allowlist"] == logical_scope(plan["checkpoint_config"]), "EXACT78_LOGICAL_SCOPE")
    for name, expected in plan["code_pins"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts
                and sha(read_bytes(Path(checkout) / name, 2 << 20)) == expected, "REQUALIFICATION_SOURCE_PIN")
    rights = go["rights_review"]
    require(rights == dict(approved=True, source_policy_sha256=plan["source_policy_sha256"],
        logical_allowlist=plan["logical_allowlist"], scope="OWNER_DELEGATED_PRIVATE_ONLY", human_review_claim=False),
        "EXACT_PRIVATE_ONLY_RIGHTS_REQUIRED")
    runner = core.parents_safe(env["RUNNER_TEMP"])
    output = core.parents_safe(go["output_root"])
    require(output == runner / (VERSION + "-" + go["run_id"]), "FRESH_RUN_OWNED_DESTINATION_REQUIRED")
    require(Path(go["local_cache"]) == output / "cache" and Path(go["local_state"]) == output / "state",
            "ONE_ORIGINAL_QUOTA_REQUIRED")
    return actions_context(env, "write")


@contextmanager
def resource_envelope(plan, phase, checkout):
    """Existing opaque restore cap or existing sampled inference envelope."""
    import resource
    import signal
    import threading
    import time
    caps = plan["runtime_envelopes"][phase]
    require(plan["runtime_envelopes"] == shared_envelopes(), "EXACT_SHARED_RUNTIME_ENVELOPES")
    resource.setrlimit(resource.RLIMIT_CPU, (caps["CPU_seconds"],) * 2)
    resource.setrlimit(resource.RLIMIT_AS, (caps["address_space_bytes"],) * 2)
    # Real private exchanges require the original native, default-handler
    # deadline. Keep that strong guard; a custom Python handler is incompatible.
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, caps["wall_seconds"])
    started, cpu = time.monotonic(), time.process_time()
    stats = dict(sampled_peak_bytes=0, highwater_bytes=0, samples=0)
    stop, watcher = threading.Event(), None
    try:
        if phase == "requalify":
            import importlib.util
            path = Path(checkout) / "tools/review_direct_booster_screen_guard_v4.py"
            require(sha(read_bytes(path, 1 << 20)) == plan["code_pins"]["tools/review_direct_booster_screen_guard_v4.py"], "EXISTING_RSS_SAMPLER_PIN")
            spec = importlib.util.spec_from_file_location("audit_count_existing_rss_sampler", path)
            sampler = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sampler)
            process = sampler.process_binding(os.getpid())
            def sample():
                rss, _ = sampler.required_usage([process])
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
                stats["samples"] += 1
                stats["sampled_peak_bytes"] = max(stats["sampled_peak_bytes"], rss)
                stats["highwater_bytes"] = max(stats["highwater_bytes"], peak)
                require(max(rss, peak) < caps["RSS_bytes"] - caps["RSS_stop_margin_bytes"], "EXISTING_PHYSICAL_RSS_STOP")
            def watch():
                while not stop.wait(.01):
                    try:
                        sample()
                    except BaseException:
                        os.write(2, b'{"state":"COUNT_REQUALIFICATION_RESOURCE_STOP"}\n')
                        os.kill(os.getpid(), signal.SIGKILL)
            sample()
            watcher = threading.Thread(target=watch, daemon=True, name="count-existing-rss-monitor")
            watcher.start()
        yield stats
        if phase == "requalify":
            sample()
    finally:
        stop.set()
        if watcher is not None:
            watcher.join(timeout=.5)
        signal.setitimer(signal.ITIMER_REAL, 0)
        stats.update(CPU_seconds=time.process_time() - cpu, wall_seconds=time.monotonic() - started,
                     address_space_bytes=caps["address_space_bytes"])


def restore_checkpoint(plan, go, storage, job, env, *, transport=None):
    """Established checkpoint extractor and private client; no claim/append lane."""
    from . import gha_private_checkpoint as cp, private_draft_store as core, owner_private_bootstrap as owner
    parent = plan["parent"]
    handoff = parent["handoff"]
    output = Path(go["output_root"]) / "restore"
    output.mkdir(mode=0o700)
    journal = output / "journal"
    journal.mkdir(mode=0o700)
    with storage.transaction():
        pending = plan["checkpoint_config"]["external_pending_reservations"]
        storage._require(sum(len(core.canonical(q)) for q in pending))
        cp.seed_pending(journal, pending)
    actual = read_json(Path(__file__).resolve().parents[1] / "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json")
    config = plan["checkpoint_config"]
    require(actual["binding"] == handoff["runtime_binding"]
            and sha(canonical(actual["binding"])) == config["binding_sha256"]
            and sha(canonical(actual["qualification"])) == config["qualification_sha256"]
            and actual["source_sha"] == config["canary_source_sha"], "ARCHIVED_QUALIFIED_RUNTIME_REQUIRED")
    owner.archived_qualification(actual["binding"], actual["qualification"])
    parent_routes = {core.API + "/actions/runs/" + parent["run_id"],
                     core.API + "/actions/runs/" + parent["run_id"] + "/jobs?per_page=100&page=1"}

    class ReadOnlyClient(core.Client):
        def allow(self, url):
            if url in parent_routes:
                self.allowed.add(url)
                return url
            return super().allow(url)

        def request(self, url, *, method="GET", **kwargs):
            require(method == "GET" and kwargs.get("data") is None, "GET_ONLY_PRIVATE_RECOVERY")
            return super().request(url, method=method, **kwargs)

    class Factory:
        last = None

        def __init__(self):
            self.clients = []

        def __call__(self, operation):
            require(operation == "restore" and len(self.clients) < 9, "NINE_GET_ONLY_RESTORE_OPERATIONS")
            c = ReadOnlyClient(env.get("GITHUB_TOKEN"), go["run_id"], journal=journal,
                source_sha=go["source_sha"], job=job, operation="restore", transport=transport)
            self.last = c
            self.clients.append(c)
            c.authenticate_actions_job()
            require(c.job["workflow_ref"] == parent["workflow_ref"], "ESTABLISHED_PARENT_WORKFLOW_REF_REQUIRED")
            c.bind(handoff["runtime_binding"])
            return c

    factory = Factory()
    first = factory("restore")
    parent_run = first.json(first.allow(sorted(parent_routes, key=len)[0]))
    require(parent_run.get("id") == int(parent["run_id"]) and parent_run.get("head_sha") == parent["source_sha"]
            and parent_run.get("status") == "completed" and parent_run.get("conclusion") == "failure"
            and parent_run.get("event") == "workflow_dispatch" and parent_run.get("run_attempt") == 1
            and parent_run.get("path") == ".github/workflows/lab.yml"
            and parent_run.get("repository", {}).get("full_name") == REPO, "EXACT_RETAINED_PARENT_RUN")
    jobs = first.json(first.allow(sorted(parent_routes, key=len)[1]))
    require(type(jobs.get("jobs")) is list and jobs.get("total_count") == len(jobs["jobs"]) <= 100,
            "COMPLETE_PARENT_JOB_LIST")
    matches = [j for j in jobs["jobs"] if j.get("name") == parent["producer_job_id"]]
    require(len(matches) == 1 and matches[0].get("id") == parent["producer_api_job_id"]
            and matches[0].get("head_sha") == parent["source_sha"] and matches[0].get("run_id") == int(parent["run_id"])
            and matches[0].get("status") == "completed" and matches[0].get("conclusion") == "success"
            and core.utc(matches[0]["completed_at"]) <= core.utc(go["issued_at_utc"]), "SUCCESSFUL_ORIGINAL_PRODUCER_REQUIRED")
    owner.authenticate_past_run(first, actual["qualification"])
    first.inventory()  # Includes every unknown/orphan and retained pending byte.
    owner.verify_canary(first)
    # This first metadata client is not an extra payload operation.
    used = False

    class RestoreFactory:
        last = first

        def __call__(self, operation):
            nonlocal used
            if not used:
                used = True
                return first
            self.last = factory(operation)
            return self.last

    restored = cp.restore(handoff, RestoreFactory(), config=plan["checkpoint_config"],
        storage=storage, output=output, producer_api_job_id=parent["producer_api_job_id"])
    calls = sum(c.calls for c in factory.clients)
    require(calls <= plan["limits"]["HTTP_calls"], "RESTORE_TOTAL_HTTP_CAP")
    receipt = dict(schema_version=VERSION + "-restore", state="QUALIFIED_ROUTE_RESTORED_OPAQUE",
        plan_sha256=go["plan_sha256"], current_run_id=go["run_id"], current_source_sha=go["source_sha"],
        parent_origin=parent, restorer=cp.client_identity(factory.last),
        checkpoint_receipt=cp.binding(output / "RESTORE_FINISHED.json"),
        rights_review_sha256=sha(canonical(go["rights_review"])),
        actual_completed_at=now().isoformat(), HTTP_calls=calls,
        fits=0, model_decodes=0, remote_writes=0, protected_outcome_reads=0,
        private_durability_qualified=False, scientific_qualification=False)
    storage.write_bytes(Path(go["output_root"]) / "RESTORE_RECEIPT.json", canonical(receipt))
    return receipt


def load_original_module(package, plan):
    record = plan["original_source"]
    require(record["name"] == "original-weekly_future_inference.py", "CLOSED_ORIGINAL_SOURCE_NAME")
    path = Path(package) / record["name"]
    body = read_bytes(path, 256 << 10)
    require(len(body) == record["bytes"] and sha(body) == record["sha256"]
            == ORIGINAL_PINS["weekly_future_inference.py"], "ORIGINAL_SOURCE_HASH")
    # Execute exactly the authenticated buffer, without reopening a mutable path.
    module = types.ModuleType("nfl_lab._audit_count_original_v1")
    module.__package__ = "nfl_lab"
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def compare_points(model, family, frame, original_module):
    """Compare every offered bit; values and row identities remain private."""
    import numpy as np
    from . import weekly_future_inference as current
    before, reasons = original_module._points(model, family, frame)
    after, new_reasons = current._points(model, family, frame)
    require(np.array_equal(reasons, new_reasons), "FALLBACK_REASONS_CHANGED")
    warm = reasons == ""
    def bits(a):
        return np.asarray(a, dtype="<f8").tobytes()
    require(bits(before[warm]) == bits(after[warm]), "WARM_PREDICTION_BITS_CHANGED")
    if family == "count_A":
        roles = current.cdf.strings(frame, "position")
        for i in np.flatnonzero(~warm):
            prior = model.priors.get(str(roles[i]), model.global_prior)
            if prior is None:
                require(np.isnan(before[i]) and np.isnan(after[i]), "UNSUPPORTED_PRIOR_MUST_ABSTAIN")
            else:
                require(isinstance(prior, current.cdf.SupportPrior) and prior.support == "count"
                        and np.isfinite(prior.q) and 0 <= prior.q < 1, "SUPPORTED_STORED_GEOMETRIC_PRIOR_REQUIRED")
                # Independent arithmetic from the retained distribution parameter,
                # not a second call through the repaired fallback implementation.
                expected_mean = float(prior.q) / (1. - float(prior.q))
                require(np.isfinite(expected_mean) and expected_mean >= 0
                        and bits([after[i]]) == bits([expected_mean]), "STORED_PRIOR_MEAN_REQUIRED")
    else:
        require(bits(before) == bits(after), "NON_COUNT_REPLAY_BITS_CHANGED")
    repeated, repeated_reasons = original_module._points(model, family, frame)
    require(bits(before) == bits(repeated) and np.array_equal(reasons, repeated_reasons), "ORIGINAL_MODEL_PREDICTION_MUTATED")
    return dict(rows=len(frame), warm_rows=int(warm.sum()), fallback_rows=int((~warm).sum()),
        warm_bits_identical=True, fallback_reasons_identical=True,
        stored_prior_means_verified=family == "count_A", original_replay_unchanged=True,
        independent_stored_q_mean_verified=family == "count_A",
        original_bits_sha256=sha(bits(before)), effective_bits_sha256=sha(bits(after)))


def count_replay_oracle(model, frame):
    """Fresh-reader oracle: raw frozen CountA.predict versus the new mean product."""
    class OriginalCount:
        @staticmethod
        def _points(trained, family, features):
            require(family == "count_A", "COUNT_ORACLE_SCOPE")
            return trained.predict(features)
    return compare_points(model, "count_A", frame, OriginalCount)


def requalify_one(original_ref, model_ref, *, storage, destination, original_module,
                  plan_sha256, restore_receipt, expected_slot=None):
    """New exporter from already-trained runtime state, without training arrays."""
    import joblib
    from . import gha_private_checkpoint as cp, weekly_future_inference as current
    from .owned_reference_batch import validate_owned_references
    from .state import digest
    validate_owned_references(storage, {r["path"]: r["sha256"] for r in (original_ref, model_ref, restore_receipt)})
    original_body = cp.read_ref(original_ref, 256 << 10)
    m = cp.strict_json(original_body)
    if expected_slot is not None:
        require((m["category"]["target"], m["family"], m["method_id"]) == expected_slot,
                "EXACT_RESTORED_MODEL_SLOT_REQUIRED")
    require(m["schema_version"] == current.VERSION and m["artifact_kind"] == "TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY"
            and not m["dependencies"] and m["family"] in {"count_A", "leaf_cdf_base", "catboost_medium"}, "STANDALONE_RETAINED_FUTURE_MODEL_REQUIRED")
    require(m["code_pins"] == ORIGINAL_PINS and m["environment"] == current.environment(), "ORIGINAL_CODE_ENVIRONMENT_REQUIRED")
    require(all(current.code_pins()[name] == expected for name, expected in ORIGINAL_PINS.items()
                if name != "weekly_future_inference.py"), "UNREVIEWED_ESTIMATOR_CODE_CHANGE")
    require(m["source_contract"]["source_policy_sha256"] == cp.POLICY_SHA
            and (m["model"]["sha256"], m["model"]["bytes"]) == (model_ref["sha256"], model_ref["bytes"]), "SOURCE_AND_ORIGINAL_MODEL_HASH_REQUIRED")
    require(isinstance(m["fit_receipt"], dict) and m["fit_clock_status"] == "RECORDED", "ORIGINAL_FIT_RECEIPT_REQUIRED")
    legacy_recipe = digest(dict(registration="weekly-adaptive-release-v1", family=m["family"], source_contract=m["source_contract"],
        code_pins=ORIGINAL_PINS, category_contract_sha256="9154f113d75b8b6af3cbc21e0c407e7af4b79b29e53a288d487a2dc868473de4",
        training_rule="annual earlier seasons since2019; fixed correction earlierOOF since2022; pass_td context/pass_att intercept initially",
        fallback="existing role/global priors; all offered preserved"))
    require(m["procedure_version"] == legacy_recipe, "ORIGINAL_PROCEDURE_VERSION_REQUIRED")
    # Only here, after route/rights/owned/source/environment/hash checks, decode.
    body = cp.read_ref(model_ref)
    payload = joblib.load(io.BytesIO(body))
    require(set(payload) == {"model", "fixture", "expected_bits", "base_artifact_sha256"}
            and payload["base_artifact_sha256"] is None, "ORIGINAL_RUNTIME_BUNDLE_SCHEMA")
    model, fixture = payload["model"], payload["fixture"]
    require(current.model_contract(model, m["family"]) == (m["category"], m["features"]), "RETAINED_MODEL_SCHEMA")
    require(list(current.query_projection(fixture, m["features"]).columns) == list(fixture.columns)
            and current.frame_digest(fixture) == m["replay_fixture_sha256"], "ORIGINAL_FEATURE_ONLY_REPLAY_FIXTURE")
    old_bits = original_module.prediction_bits(model, m["family"], fixture)
    require(old_bits == payload["expected_bits"] and digest(old_bits) == m["replay_bits_sha256"], "ORIGINAL_REPLAY_BITS_REQUIRED")
    comparison = compare_points(model, m["family"], fixture, original_module)
    # Deterministic feature-only probes exercise cold, nonmodeled and global priors.
    probes = []
    if m["family"] == "count_A":
        require(len(fixture) > 0, "NONEMPTY_COUNT_FIXTURE_REQUIRED")
        for role in list(dict.fromkeys(list(model.priors) + list(m["category"]["modeled_roles"]) + ["audit_unknown_role"])):
            row = fixture.iloc[:1].copy()
            row["position"] = role
            row["f_player_games_prior"] = 0.
            probes.append(compare_points(model, m["family"], row, original_module))
        require(comparison["warm_rows"] > 0, "NONVACUOUS_RETAINED_WARM_REPLAY_REQUIRED")
    effective_bits = current.prediction_bits(model, m["family"], fixture)
    fresh = dict(payload, expected_bits=effective_bits)
    stream = io.BytesIO()
    joblib.dump(fresh, stream, compress=3)
    encoded = stream.getvalue()
    require(len(encoded) <= 8 << 20, "UNCHANGED_MODEL_ASSET_CAP")
    destination = Path(destination)
    require(not destination.exists(), "NEW_EFFECTIVE_ARTIFACT_DIRECTORY_REQUIRED")
    with storage.transaction():
        storage._require(len(encoded) + len(original_body) + (512 << 10))
        storage.write_bytes(destination / "original-future-inference.json", original_body)
        storage.import_file(model_ref["path"], destination / "original-trained.joblib", expected_sha256=model_ref["sha256"])
        storage.write_bytes(destination / "trained.joblib", encoded)
        effective = dict(m, model=cp.binding(destination / "trained.joblib"), code_pins=current.code_pins(),
            count_fallback_version=current.COUNT_A_FALLBACK_VERSION if m["family"] == "count_A" else None,
            procedure_version=current.procedure_version(m["family"], m["source_contract"]), replay_bits_sha256=digest(effective_bits),
            requalification=dict(schema_version=VERSION + "-effective-manifest", original_manifest=original_ref,
                original_model=model_ref, original_procedure_version=m["procedure_version"],
                plan_sha256=plan_sha256, restore_receipt=restore_receipt, created_at_utc=now().isoformat(),
                fits=0, parameters_retrained=False, original_replay_preserved=True, comparison=comparison, prior_probes=probes))
        manifest_body = canonical(effective)
        require(len(manifest_body) <= 256 << 10, "UNCHANGED_MANIFEST_CAP")
        storage.write_bytes(destination / "future-inference.json", manifest_body)
    ref = cp.binding(destination / "future-inference.json")
    with current.FutureInferenceSession.from_storage(storage) as session:
        session.prepare([ref])
    validate_owned_references(storage, {r["path"]: r["sha256"] for r in (original_ref, model_ref, ref)})
    return dict(target=m["category"]["target"], family=m["family"], method_id=m["method_id"], manifest=ref,
                original_model_sha256=model_ref["sha256"], original_manifest_sha256=original_ref["sha256"],
                comparison=comparison, prior_probes=probes, fits=0, current_loader_replay_passed=True)


def requalify_restored(plan, go, storage, package):
    from . import gha_private_checkpoint as cp, private_draft_store as core
    from .owned_reference_batch import validate_owned_references
    proof_ref = go["restore_receipt"]
    require(isinstance(proof_ref, dict) and Path(proof_ref["path"]) == Path(go["output_root"]) / "RESTORE_RECEIPT.json", "EXACT_CURRENT_RESTORE_RECEIPT")
    validate_owned_references(storage, {proof_ref["path"]: proof_ref["sha256"]})
    proof = cp.strict_json(cp.read_ref(proof_ref))
    require(proof["schema_version"] == VERSION + "-restore" and proof["state"] == "QUALIFIED_ROUTE_RESTORED_OPAQUE"
            and proof["plan_sha256"] == go["plan_sha256"] and proof["current_run_id"] == go["run_id"]
            and proof["current_source_sha"] == go["source_sha"] and proof["parent_origin"] == plan["parent"]
            and proof["rights_review_sha256"] == sha(canonical(go["rights_review"]))
            and core.utc(proof["actual_completed_at"]) <= now(), "CURRENT_RESTORE_ROUTE_AND_RIGHTS_REQUIRED")
    checkpoint_ref = proof["checkpoint_receipt"]
    require(Path(checkpoint_ref["path"]) == Path(go["output_root"]) / "restore/RESTORE_FINISHED.json", "EXACT_CHECKPOINT_RECEIPT_PATH")
    validate_owned_references(storage, {checkpoint_ref["path"]: checkpoint_ref["sha256"]})
    checkpoint = cp.strict_json(cp.read_ref(checkpoint_ref))
    require(checkpoint["state"] == "FULL_PRIVATE_CHECKPOINT_RESTORED" and checkpoint["model_decodes"] == 0
            and checkpoint["run_id"] == plan["parent"]["run_id"] and checkpoint["source_sha"] == plan["parent"]["source_sha"]
            and checkpoint["index_sha256"] == plan["parent"]["handoff"]["index_descriptor"]["entry"]["payload"]["sha256"]
            and checkpoint["restorer"] == proof["restorer"], "EXACT_ORIGINAL_CHECKPOINT_REQUIRED")
    mapping = {}
    extracted = Path(go["output_root"]) / "restore/files"
    for ref in checkpoint["path_mapping"].values():
        name = Path(ref["path"]).relative_to(extracted).as_posix()
        require(name not in mapping, "NO_DUPLICATE_RESTORED_LOGICAL_PATH")
        mapping[name] = ref
    require(sorted(mapping) == plan["logical_allowlist"], "EXACT78_RESTORED_LOGICAL_SCOPE")
    validate_owned_references(storage, {r["path"]: r["sha256"] for r in mapping.values()})
    module = load_original_module(package, plan)
    artifacts = []
    for target, family, method in cp.JOBS:
        prefix = f"models/{target}/{family}"
        artifacts.append(requalify_one(mapping[prefix + "/future-inference.json"], mapping[prefix + "/trained.joblib"],
            storage=storage, destination=Path(go["output_root"]) / "effective-models" / target / family,
            original_module=module, plan_sha256=go["plan_sha256"], restore_receipt=proof_ref,
            expected_slot=(target, family, method)))
    result = dict(schema_version=VERSION + "-result", state="ZERO_FIT_REQUALIFIED_PRIVATE_PENDING_INTEGRATION",
        plan_sha256=go["plan_sha256"], current_run_id=go["run_id"], current_source_sha=go["source_sha"],
        artifacts=artifacts, fits=0, model_pairs=len(artifacts), original_models_preserved=True,
        remote_writes=0, protected_outcome_reads=0, public_release=False, scientific_qualification=False,
        private_durability_qualified=False, actual_completed_at=now().isoformat())
    storage.write_bytes(Path(go["output_root"]) / "REQUALIFICATION_FINISHED.json", canonical(result))
    return result
