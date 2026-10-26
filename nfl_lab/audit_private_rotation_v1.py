"""New canary-only runtime rotation; old procedures/configs remain immutable.

No network/credential access on import or preparation. Only run_phase after a
fresh owner GO and genuine hosted identity may execute the four existing store
CLI operations. Global inventory is metadata GET only. No payload, model,
provider, outcome, deletion, publication or retry operation is implemented.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

VERSION = "audit-private-rotation-v1"
ROOT = Path(__file__).resolve().parents[1]
REPO = "NickNicky19/NFL-forecasting"
GROUP = "nfl-lab-single-writer"
GLOBAL_CAP, RUNTIME_CAP, ASSET_CAP, MAX_ASSETS = 512 << 20, 32 << 20, 8 << 20, 128
OUTPUT_CAP = 16 << 10
JOBS = {p: "audit-private-rotation-" + p + "-v1" for p in ("write", "read", "qualify")}
OPERATIONS = {"write": ("initialize", "pin"), "read": ("boundary",), "qualify": ("qualify",)}
PINS = ("nfl_lab/audit_private_rotation_v1.py", "tools/audit_private_rotation_v1.py", "tests/test_audit_private_rotation_v1.py",
    "nfl_lab/__init__.py", "nfl_lab/private_draft_store.py", "nfl_lab/private_draft_probe_helpers.py",
    "tools/private_draft_store_v2.py", "schemas/private-draft-store-v2.json", "config/private-draft-storage-v2.json", ".github/workflows/lab.yml")
ROOT_KEYS = {"schema_version", "approved", "operation", "repository", "source_sha", "workflow_ref", "owner_authorization",
    "issued_at_utc", "expires_at_utc", "runtime_id", "single_writer_group", "maximum_dispatches", "helper_sha256",
    "jobs", "budgets", "preserved_bindings", "pending_census", "private_payload_bytes", "new_fits", "publication"}
HANDOFF_KEYS = {"schema_version", "phase", "root_go_sha256", "run_id", "source_sha", "runtime_id", "binding", "quota_reservation", "before"}
PENDING_KEYS = {"reservation_sha256", "runtime_id", "release_id", "pending_bytes", "pending_assets"}
HASH = re.compile(r"[a-f0-9]{64}\Z")
RUNTIME = re.compile(r"[a-f0-9]{32}\Z")
BUDGETS = dict(global_bytes=GLOBAL_CAP, runtime_bytes=RUNTIME_CAP, runtime_assets=MAX_ASSETS,
    CPU_seconds=120, address_space_bytes=512 << 20, operation_wall_seconds=180, writer_wall_seconds=360,
    metadata_HTTP_calls=40, store_HTTP_calls_per_operation=40, automatic_retry=False)


class RotationError(Exception):
    pass


def require(ok, code):
    if not ok:
        raise RotationError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def utc(value):
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(result.tzinfo is not None, "ROTATION_TIMEZONE_REQUIRED")
    return result.astimezone(timezone.utc)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "ROTATION_DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(RotationError("ROTATION_NONFINITE_JSON")))


def read(path, cap):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file() and path.stat().st_size <= cap,
        "ROTATION_LOCAL_INPUT_BOUND")
    raw = path.read_bytes()
    require(len(raw) <= cap, "ROTATION_LOCAL_INPUT_BOUND")
    return raw


def helper_pins():
    return {p: sha(read(ROOT / p, 2 << 20)) for p in PINS}


def root_template(*, source_sha, workflow_ref, runtime_id, issued_at_utc, expires_at_utc, preserved_bindings, pending_census):
    """Reviewable metadata only, unapproved; no identity/time/GO is fabricated."""
    return dict(schema_version=VERSION + "-root-GO", approved=False, operation="INITIALIZE_AND_QUALIFY_117_BYTE_CANARY_ONLY",
        repository=REPO, source_sha=source_sha, workflow_ref=workflow_ref, runtime_id=runtime_id,
        owner_authorization="OWNER_NFL_AUDIT_CONTINUATION_20261025", issued_at_utc=issued_at_utc, expires_at_utc=expires_at_utc,
        single_writer_group=GROUP, maximum_dispatches=1, helper_sha256=helper_pins(),
        jobs={p: dict(job_id=JOBS[p], permission="read" if p == "read" else "write", operations=list(OPERATIONS[p])) for p in JOBS},
        budgets=dict(BUDGETS), preserved_bindings=preserved_bindings, pending_census=pending_census,
        private_payload_bytes=0, new_fits=0, publication=False)


def validate_root(root, *, now):
    require(type(root) is dict and set(root) == ROOT_KEYS and root["schema_version"] == VERSION + "-root-GO"
        and root["approved"] is True and root["operation"] == "INITIALIZE_AND_QUALIFY_117_BYTE_CANARY_ONLY"
        and root["repository"] == REPO and root["owner_authorization"] == "OWNER_NFL_AUDIT_CONTINUATION_20261025"
        and type(root["maximum_dispatches"]) is int and root["maximum_dispatches"] == 1
        and root["single_writer_group"] == GROUP and root["budgets"] == BUDGETS
        and type(root["private_payload_bytes"]) is int and root["private_payload_bytes"] == 0
        and type(root["new_fits"]) is int and root["new_fits"] == 0 and root["publication"] is False,
        "CLOSED_HARMLESS_ROTATION_ROOT_GO_REQUIRED")
    require(type(root["source_sha"]) is str and re.fullmatch(r"[a-f0-9]{40}", root["source_sha"])
        and type(root["runtime_id"]) is str and RUNTIME.fullmatch(root["runtime_id"])
        and re.fullmatch(re.escape(REPO) + r"/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+", root["workflow_ref"]),
        "EXACT_NEW_ROTATION_SOURCE_RUNTIME_REQUIRED")
    issued, expires = utc(root["issued_at_utc"]), utc(root["expires_at_utc"])
    require(issued <= now < expires and 0 < (expires - issued).total_seconds() <= 3600, "ROTATION_GO_EXPIRED_OR_FUTURE")
    require(root["jobs"] == {p: dict(job_id=JOBS[p], permission="read" if p == "read" else "write", operations=list(OPERATIONS[p])) for p in JOBS},
        "CLOSED_ROTATION_PER_JOB_OPERATIONS")
    require(root["helper_sha256"] == helper_pins(), "ROTATION_SOURCE_PINS_CHANGED")
    pending = root["pending_census"]
    require(type(pending) is dict and set(pending) == {"schema_version", "complete", "as_of_utc", "owner_evidence_sha256", "reservations"}
        and pending["schema_version"] == VERSION + "-pending-census" and pending["complete"] is True
        and HASH.fullmatch(str(pending["owner_evidence_sha256"]))
        and issued - timedelta(hours=1) <= utc(pending["as_of_utc"]) <= issued
        and type(pending["reservations"]) is list and len(pending["reservations"]) <= 128,
        "COMPLETE_OWNER_BOUND_PENDING_CENSUS_REQUIRED")
    seen = set()
    for row in pending["reservations"]:
        require(type(row) is dict and set(row) == PENDING_KEYS and HASH.fullmatch(str(row["reservation_sha256"]))
            and row["reservation_sha256"] not in seen
            and (row["runtime_id"] is None or type(row["runtime_id"]) is str and RUNTIME.fullmatch(row["runtime_id"]))
            and (row["release_id"] is None or type(row["release_id"]) is int and row["release_id"] > 0)
            and type(row["pending_bytes"]) is int and 0 <= row["pending_bytes"] <= RUNTIME_CAP
            and type(row["pending_assets"]) is int and 0 <= row["pending_assets"] <= MAX_ASSETS,
            "CLOSED_UNKNOWN_AND_PENDING_RESERVATIONS_REQUIRED")
        require(row["runtime_id"] != root["runtime_id"], "NEW_RUNTIME_ALREADY_RESERVED_NO_RETRY")
        seen.add(row["reservation_sha256"])
    require(type(root["preserved_bindings"]) is list and 1 <= len(root["preserved_bindings"]) <= 15,
        "ORIGINAL_QUALIFIED_RUNTIME_BINDINGS_REQUIRED")
    from . import private_draft_store as store
    for binding in root["preserved_bindings"]:
        store.checked_binding(binding)
        require(binding["runtime_id"] != root["runtime_id"], "OLD_RUNTIME_MUST_NEVER_BE_ROTATED_IN_PLACE")
    require(len({b["release_id"] for b in root["preserved_bindings"]}) == len(root["preserved_bindings"]), "DUPLICATE_PRESERVED_RUNTIME")
    return root


def preflight(phase, env):
    require(phase in JOBS, "CLOSED_ROTATION_PHASE")
    body = env.get("AUDIT_PRIVATE_ROTATION_GO_JSON", "").encode()
    require(0 < len(body) <= OUTPUT_CAP and sha(body) == env.get("AUDIT_PRIVATE_ROTATION_GO_SHA256"), "ROTATION_ROOT_GO_HASH")
    root = strict_json(body)
    require(canonical(root) == body, "ROTATION_ROOT_GO_CANONICAL")
    validate_root(root, now=datetime.now(timezone.utc))
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("CI") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and env.get("GITHUB_REPOSITORY") == REPO and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and env.get("GITHUB_RUN_ATTEMPT") == "1" and re.fullmatch(r"[1-9][0-9]{10}", env.get("GITHUB_RUN_ID", ""))
        and env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == root["source_sha"]
        and env.get("GITHUB_WORKFLOW_REF") == root["workflow_ref"] and env.get("GITHUB_WORKSPACE") == str(ROOT)
        and env.get("GITHUB_JOB") == JOBS[phase] and env.get("STORE_PERMISSION") == ("read" if phase == "read" else "write")
        and env.get("GITHUB_ACTOR") == "NickNicky19" and env.get("GITHUB_ACTOR_ID") == "208912933",
        "GENUINE_OWNER_ROTATION_ACTIONS_CONTEXT_REQUIRED")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == root["source_sha"], "ROTATION_CHECKOUT_SOURCE")
    require(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all", "--", *PINS], cwd=ROOT, text=True) == "",
        "ROTATION_REQUIRES_CLEAN_COMMITTED_HELPERS")
    event = strict_json(read(env["GITHUB_EVENT_PATH"], 256 << 10))
    require(event.get("inputs", {}).get("mode") == VERSION and event["inputs"].get("inference_builder_go_json") == body.decode()
        and event["inputs"].get("inference_builder_go_sha256") == sha(body) and event.get("repository", {}).get("full_name") == REPO
        and event.get("ref") in {env.get("GITHUB_REF"), env.get("GITHUB_REF", "").removeprefix("refs/heads/")},
        "ACTUAL_INFERENCE_BUILDER_GO_INPUTS_ONLY")
    return root


def metadata_client(env, journal, *, transport=None):
    """An additional GET-only metadata scope; native store APIs are unchanged."""
    from . import private_draft_store as store
    from tools.private_draft_store_v2 import actions_context
    class MetadataClient(store.Client):
        def json(self, url, **kwargs):
            value = super().json(url, **kwargs)
            if "/actions/runs/" in url:
                self.identity_metadata[url] = value
            return value
        def allow(self, url):
            if re.fullmatch(re.escape(store.API) + r"/releases\?per_page=1&page=(?:[1-9]|[1-3][0-9]|40)", url):
                self.allowed.add(url); return url
            return super().allow(url)
        def request(self, url, **kwargs):
            require(kwargs.get("method", "GET") == "GET" and kwargs.get("data") is None
                and not kwargs.get("octet") and not kwargs.get("download"), "ROTATION_METADATA_GET_ONLY")
            return super().request(url, **kwargs)
    client = MetadataClient(env.get("GITHUB_TOKEN"), env["GITHUB_RUN_ID"], journal=journal, source_sha=env["GITHUB_SHA"],
        job=actions_context(env, "read" if env["GITHUB_JOB"] == JOBS["read"] else "write"), operation="rotation_metadata", transport=transport)
    client.identity_metadata = {}
    client.authenticate_actions_job()
    return client


def authenticate_phase(client, phase, root, env, previous=()):
    from . import private_draft_store as store
    run = client.identity_metadata[store.API + "/actions/runs/" + env["GITHUB_RUN_ID"]]
    jobs = client.identity_metadata[store.API + "/actions/runs/" + env["GITHUB_RUN_ID"] + "/jobs?per_page=100&page=1"]["jobs"]
    require(run.get("actor", {}).get("id") == run.get("triggering_actor", {}).get("id") == 208912933
        and run.get("actor", {}).get("login") == run.get("triggering_actor", {}).get("login") == "NickNicky19"
        and utc(root["issued_at_utc"]) <= utc(run["created_at"]) <= utc(client.started_at), "ACTUAL_OWNER_CREATED_ROTATION_RUN_REQUIRED")
    current = next(j for j in jobs if j["id"] == client.job["api_job_id"])
    for proof, expected in previous:
        matches = [j for j in jobs if j.get("id") == proof["job"]["api_job_id"] and j.get("name") == JOBS[expected]
            and j.get("status") == "completed" and j.get("conclusion") == "success" and j.get("run_id") == int(env["GITHUB_RUN_ID"])
            and j.get("head_sha") == env["GITHUB_SHA"]]
        require(len(matches) == 1 and utc(proof["created_at_utc"]) <= utc(matches[0]["completed_at"]) <= utc(current["started_at"]),
            "EXACT_COMPLETED_PREDECESSOR_JOB_REQUIRED")


def global_inventory(client, root):
    """Count ALL draft assets and pending/orphan allocations before any POST."""
    from . import private_draft_store as store
    own = client.json(store.API)
    require(own.get("full_name") == REPO and own.get("url") == store.API and own.get("private") is False, "ROTATION_OWN_REPOSITORY_CONTROL")
    releases = []
    # GitHub embeds every release's asset metadata. Several otherwise valid
    # runtimes can overflow the unchanged 256-KiB response cap in one page.
    # Keep the original <40-release bound and the shared 40-request budget.
    for page in range(1, 41):
        batch = client.json(client.allow(store.API + f"/releases?per_page=1&page={page}"))
        require(type(batch) is list and len(batch) <= 1, "GLOBAL_RELEASE_INVENTORY_SHAPE")
        releases.extend(batch)
        if not batch:
            break
    else:
        raise RotationError("GLOBAL_RELEASE_INVENTORY_BOUND")
    ids = set(); tags = set(); drafts = []
    for release in releases:
        require(type(release) is dict and type(release.get("id")) is int and release["id"] > 0
            and release["id"] not in ids and type(release.get("tag_name")) is str and release["tag_name"] not in tags
            and type(release.get("draft")) is bool and release.get("url") == store.API + "/releases/" + str(release["id"]),
            "GLOBAL_RELEASE_IDENTITY_AMBIGUOUS")
        ids.add(release["id"]); tags.add(release["tag_name"])
        private = release["tag_name"].startswith("weekly-private-runtime-v2-")
        require(not private or release["draft"] is True and release.get("published_at", "MISSING") is None, "OLD_PRIVATE_RUNTIME_PUBLISHED_OR_CHANGED")
        if release["draft"]:
            require(release.get("published_at", "MISSING") is None, "DRAFT_METADATA_AMBIGUITY")
            drafts.append(release)
    require("weekly-private-runtime-v2-" + root["runtime_id"] not in tags, "ROTATION_TARGET_ALREADY_EXISTS_NO_RETRY")
    require((len(drafts) + 1) * RUNTIME_CAP <= GLOBAL_CAP, "GLOBAL_RUNTIME_RESERVATION_CAP")
    records = {}; runtime_to_release = {}
    for release in drafts:
        assets = []
        for page in range(1, 3):
            batch = client.json(client.allow(store.API + f"/releases/{release['id']}/assets?per_page=100&page={page}"))
            require(type(batch) is list and len(batch) <= 100, "GLOBAL_ASSET_INVENTORY_SHAPE")
            assets.extend(batch)
            require(len(assets) <= MAX_ASSETS, "EXISTING_RUNTIME_ASSET_CAP")
            if len(batch) < 100:
                break
        else:
            raise RotationError("GLOBAL_ASSET_INVENTORY_BOUND")
        asset_ids = set(); names = set(); charged = 0
        for asset in assets:
            require(type(asset) is dict and type(asset.get("id")) is int and asset["id"] > 0 and asset["id"] not in asset_ids
                and type(asset.get("name")) is str and asset["name"] not in names
                and type(asset.get("size")) is int and 0 <= asset["size"] <= ASSET_CAP and asset.get("state") in {"uploaded", "starter"},
                "UNKNOWN_ASSET_METADATA_CANNOT_BE_OMITTED")
            asset_ids.add(asset["id"]); names.add(asset["name"])
            charged += ASSET_CAP if asset["state"] == "starter" else asset["size"]
        require(charged <= RUNTIME_CAP, "EXISTING_RUNTIME_BYTES_CAP")
        records[release["id"]] = dict(tag_name=release["tag_name"], assets=assets, charged_bytes=charged, charged_assets=len(assets))
        match = re.fullmatch(r"weekly-private-runtime-v2-([a-f0-9]{32})", release["tag_name"])
        if match:
            runtime_to_release[match.group(1)] = release["id"]
    for binding in root["preserved_bindings"]:
        record = records.get(binding["release_id"])
        require(record is not None and record["tag_name"] == binding["tag_name"]
            and any(a["id"] == binding["canary_asset_id"] and a["name"] == binding["canary_name"] and a["size"] == 117
                and a["state"] == "uploaded" for a in record["assets"]), "ORIGINAL_QUALIFIED_RUNTIME_MUST_REMAIN_PRESENT")
    extra = {}
    for index, row in enumerate(root["pending_census"]["reservations"]):
        rid = row["release_id"]
        inferred = runtime_to_release.get(row["runtime_id"])
        require(rid is None or inferred is None or rid == inferred, "PENDING_RUNTIME_LOCATOR_CONFLICT")
        rid = rid if rid is not None else inferred
        if rid in records:
            record = records[rid]
            record["charged_bytes"] += row["pending_bytes"]; record["charged_assets"] += row["pending_assets"]
            require(record["charged_bytes"] <= RUNTIME_CAP and record["charged_assets"] <= MAX_ASSETS, "PENDING_EXISTING_RUNTIME_CAP")
        else:
            key = ("runtime", row["runtime_id"]) if row["runtime_id"] is not None else ("unknown", index)
            value = extra.setdefault(key, [0, 0])
            value[0] += row["pending_bytes"]; value[1] += row["pending_assets"]
            require(value[0] <= RUNTIME_CAP and value[1] <= MAX_ASSETS, "PENDING_UNLOCATED_RUNTIME_CAP")
    reserved = (len(records) + len(extra)) * RUNTIME_CAP
    require(reserved + RUNTIME_CAP <= GLOBAL_CAP, "GLOBAL_PENDING_PLUS_NEW_RUNTIME_CAP")
    return dict(schema_version=VERSION + "-quota-reservation", global_cap_bytes=GLOBAL_CAP,
        reserved_before_bytes=reserved, new_runtime_reserved_bytes=RUNTIME_CAP, reserved_after_bytes=reserved + RUNTIME_CAP,
        existing_draft_runtimes=len(records), pending_unlocated_runtimes=len(extra), pending_records=len(root["pending_census"]["reservations"]),
        charged_existing_bytes=sum(r["charged_bytes"] for r in records.values()), charged_existing_assets=sum(r["charged_assets"] for r in records.values()),
        inventory_sha256=sha(canonical(records)), pending_census_sha256=sha(canonical(root["pending_census"])),
        new_runtime_id=root["runtime_id"], old_assets_deleted=0, metadata_only=True)


def phase_go(operation, inputs, root, env):
    from . import private_draft_store as store
    phase = next((p for p in JOBS if JOBS[p] == env["GITHUB_JOB"]), None)
    require(phase is not None and operation in OPERATIONS[phase], "ROTATION_OPERATION_NOT_AUTHORIZED_FOR_JOB")
    fields = {"initialize": set(), "pin": {"binding"}, "boundary": {"binding", "before"}, "qualify": {"binding", "before", "read_proof"}}
    require(set(inputs) == fields[operation], "CLOSED_ROTATION_OPERATION_INPUTS")
    if "binding" in inputs:
        require(inputs["binding"]["runtime_id"] == root["runtime_id"] and inputs["binding"]["origin_run_id"] == env["GITHUB_RUN_ID"],
            "ONLY_THE_NEW_RUNTIME_MAY_BE_PASSED_TO_STORE_CLI")
    return dict(schema_version="weekly-private-operation-GO-v2.1", approved=True, operation=operation, repository=REPO,
        run_id=env["GITHUB_RUN_ID"], source_sha=root["source_sha"], config_sha256=store.config_sha(),
        scope_manifest_sha256=None, qualification_sha256=None, single_writer_group=GROUP, runtime_id=root["runtime_id"],
        input_sha256={k: sha(canonical(v)) for k, v in inputs.items()}, job_id=env["GITHUB_JOB"], workflow_ref=root["workflow_ref"])


def run_cli(argv, timeout):
    """Fresh native CLI; private text is discarded and no operation is retried."""
    child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, "ROTATION_NATIVE_CLI_DEADLINE")
            try:
                stdout, stderr = child.communicate(timeout=min(.25, remaining))
                break
            except subprocess.TimeoutExpired:
                usage = resource.getrusage(resource.RUSAGE_SELF); done = resource.getrusage(resource.RUSAGE_CHILDREN)
                cpu = usage.ru_utime + usage.ru_stime + done.ru_utime + done.ru_stime
                try:
                    stat = Path(f"/proc/{child.pid}/stat").read_text().rsplit(") ", 1)[1].split()
                    cpu += (int(stat[11]) + int(stat[12])) / os.sysconf("SC_CLK_TCK")
                except FileNotFoundError:
                    pass
                require(cpu <= 120, "ROTATION_PHASE_CPU_LIMIT")
        require(len(stdout.encode()) <= OUTPUT_CAP and len(stderr.encode()) <= OUTPUT_CAP, "ROTATION_NATIVE_OUTPUT_BOUND")
        result = strict_json(stdout)
        if child.returncode != 0:
            native_failure = (type(result) is dict and set(result) == {"state", "reason", "HTTP_calls", "private_durability_qualified"}
                and result["state"] == "FAILED" and type(result["HTTP_calls"]) is int and 0 <= result["HTTP_calls"] <= 40
                and result["private_durability_qualified"] is False)
            code = result.get("reason") if native_failure else None
            require(False, code if type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "ROTATION_NATIVE_CLI_FAILED")
        require(result.get("state") == "COMPLETE", "ROTATION_NATIVE_CLI_FAILED")
        return result
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()


def run_operation(operation, inputs, root, env, directory, deadline, runner):
    from . import private_draft_store as store
    validate_root(root, now=datetime.now(timezone.utc))
    go = phase_go(operation, inputs, root, env)
    go_path = directory / (operation + "-GO.json"); store.create_local(go_path, canonical(go))
    receipt = directory / (operation + "-receipt.json")
    argv = [sys.executable, "-I", "-B", str(ROOT / "tools/private_draft_store_v2.py"), operation, "--execute",
        "--authorization", str(go_path), "--authorization-sha256", sha(canonical(go)), "--journal", str(directory / "journal"), "--receipt", str(receipt)]
    if operation == "initialize":
        argv += ["--runtime-id", root["runtime_id"]]
    for key, value in inputs.items():
        path = directory / (operation + "-" + key + ".json"); store.create_local(path, canonical(value))
        argv += ["--" + key.replace("_", "-"), str(path)]
    remaining = deadline - time.monotonic() - 1
    require(remaining > 0, "ROTATION_PHASE_DEADLINE")
    result = runner(argv, min(180, remaining))
    require(type(result) is dict and set(result) == {"state", "operation", "receipt_sha256", "HTTP_calls", "transfer_bytes",
        "private_durability_qualified", "restricted_payload_uploaded"} and result.get("state") == "COMPLETE"
        and type(result["transfer_bytes"]) is int and 0 < result["transfer_bytes"] <= store.TRANSFER_CAP, "ROTATION_NATIVE_CLI_FAILED")
    body = store.read_local(receipt, OUTPUT_CAP); document = strict_json(body)
    require(canonical(document) == body and result.get("operation") == operation and result.get("receipt_sha256") == sha(body)
        and type(result.get("HTTP_calls")) is int and 0 <= result["HTTP_calls"] <= 40
        and result.get("restricted_payload_uploaded") is False and result.get("private_durability_qualified") is False,
        "EXACT_NATIVE_ROTATION_RECEIPT_REQUIRED")
    return document, result["HTTP_calls"]


def checked_quota(value, root):
    fields = {"schema_version", "global_cap_bytes", "reserved_before_bytes", "new_runtime_reserved_bytes", "reserved_after_bytes",
        "existing_draft_runtimes", "pending_unlocated_runtimes", "pending_records", "charged_existing_bytes", "charged_existing_assets",
        "inventory_sha256", "pending_census_sha256", "new_runtime_id", "old_assets_deleted", "metadata_only"}
    require(type(value) is dict and set(value) == fields and value["schema_version"] == VERSION + "-quota-reservation"
        and value["global_cap_bytes"] == GLOBAL_CAP and value["new_runtime_reserved_bytes"] == RUNTIME_CAP
        and value["new_runtime_id"] == root["runtime_id"] and value["old_assets_deleted"] == 0 and value["metadata_only"] is True
        and all(type(value[k]) is int and value[k] >= 0 for k in ("reserved_before_bytes", "reserved_after_bytes", "existing_draft_runtimes",
            "pending_unlocated_runtimes", "pending_records", "charged_existing_bytes", "charged_existing_assets"))
        and 1 <= value["existing_draft_runtimes"] <= 15
        and value["reserved_before_bytes"] == (value["existing_draft_runtimes"] + value["pending_unlocated_runtimes"]) * RUNTIME_CAP
        and value["reserved_after_bytes"] == value["reserved_before_bytes"] + RUNTIME_CAP <= GLOBAL_CAP
        and value["charged_existing_bytes"] <= value["existing_draft_runtimes"] * RUNTIME_CAP
        and value["charged_existing_assets"] <= value["existing_draft_runtimes"] * MAX_ASSETS
        and value["pending_records"] == len(root["pending_census"]["reservations"])
        and value["pending_census_sha256"] == sha(canonical(root["pending_census"])) and HASH.fullmatch(str(value["inventory_sha256"])),
        "CLOSED_FULL_GLOBAL_RUNTIME_RESERVATION_REQUIRED")


def checked_handoff(text, expected, phase, root, env, verifier):
    from . import private_draft_store as store
    require(0 < len(text.encode()) <= OUTPUT_CAP and sha(text.encode()) == expected, "ROTATION_HANDOFF_HASH")
    value = strict_json(text)
    fields = HANDOFF_KEYS | ({"read"} if phase == "read" else set())
    require(type(value) is dict and set(value) == fields and canonical(value).decode() == text
        and value["schema_version"] == VERSION + "-handoff" and value["phase"] == phase
        and value["root_go_sha256"] == sha(canonical(root)) and value["run_id"] == env["GITHUB_RUN_ID"]
        and value["source_sha"] == root["source_sha"] and value["runtime_id"] == root["runtime_id"], "EXACT_CAUSAL_ROTATION_HANDOFF_REQUIRED")
    store.checked_binding(value["binding"])
    require(value["binding"]["origin_run_id"] == env["GITHUB_RUN_ID"] and value["binding"]["runtime_id"] == root["runtime_id"]
        and value["binding"]["canary_sha256"] == store.sha(store.probe.fixture(env["GITHUB_RUN_ID"])), "EXACT_NEW_CANARY_NONCE_BINDING")
    verifier.binding = value["binding"]
    checked_quota(value["quota_reservation"], root)
    store.check_proof(verifier, value["before"], "write_pin")
    require(value["before"]["job"]["job_id"] == JOBS["write"], "ROTATION_WRITER_PROOF_JOB")
    if phase == "read":
        store.check_proof(verifier, value["read"], "read_boundary")
        require(value["read"]["job"]["job_id"] == JOBS["read"]
            and value["read"]["before_sha256"] == sha(canonical(value["before"])), "ROTATION_READ_PROOF_JOB_AND_PARENT")
    return value


def safe_output(document):
    body = canonical(document)
    require(len(body) + 100 <= OUTPUT_CAP and not any(m in body for m in (b"https://", b"http://", b"ghs_", b"/workspace/", b"/tmp/")),
        "ROTATION_PUBLIC_SAFE_OUTPUT_BOUND")
    return body


def output(env, document):
    from . import private_draft_store as store
    body = safe_output(document)
    parent, name = store.parent_fd(env["GITHUB_OUTPUT"])
    try:
        fd = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_size == 0, "FRESH_ROTATION_OUTPUT_REQUIRED")
        with os.fdopen(os.dup(fd), "wb") as stream:
            stream.write(b"handoff_json=" + body + b"\nhandoff_sha256=" + sha(body).encode() + b"\n")
            stream.flush(); os.fsync(stream.fileno())
    finally:
        os.close(fd)


def run_phase(phase, env, root, *, runner=run_cli, client_factory=metadata_client):
    from . import private_draft_store as store
    validate_root(root, now=datetime.now(timezone.utc))
    require(env["GITHUB_JOB"] == JOBS[phase] and env["STORE_PERMISSION"] == ("read" if phase == "read" else "write"), "ROTATION_PHASE_ROLE")
    require(len(store.probe.fixture(env["GITHUB_RUN_ID"])) == 117, "ORIGINAL_117_BYTE_CANARY_REQUIRED")
    directory = store.parents_safe(Path(env["RUNNER_TEMP"]) / (VERSION + "-" + env["GITHUB_RUN_ID"] + "-" + phase))
    require(not directory.exists(), "FRESH_ROTATION_PHASE_REQUIRED_NO_RETRY")
    directory.mkdir(mode=0o700); (directory / "journal").mkdir(mode=0o700)
    store.create_local(directory / "ROOT_GO.json", canonical(root))
    # Check the output handle before allowing the first harmless POST.
    parent, name = store.parent_fd(env["GITHUB_OUTPUT"])
    try:
        fd = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, dir_fd=parent)
        try: require(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_size == 0, "FRESH_ROTATION_OUTPUT_REQUIRED")
        finally: os.close(fd)
    finally: os.close(parent)
    deadline = time.monotonic() + (360 if phase == "write" else 180)
    client = client_factory(env, directory / "journal")
    verifier = SimpleNamespace(run_id=env["GITHUB_RUN_ID"], source_sha=env["GITHUB_SHA"], process=store.process_identity(),
        job=client.job, binding=None)
    authenticate_phase(client, phase, root, env)
    calls = 0
    if phase == "write":
        quota = global_inventory(client, root)
        store.create_local(directory / "GLOBAL_RESERVATION.json", canonical(quota))
        binding, count = run_operation("initialize", {}, root, env, directory, deadline, runner); calls += count
        store.checked_binding(binding)
        require(binding["runtime_id"] == root["runtime_id"] and binding["origin_run_id"] == env["GITHUB_RUN_ID"]
            and binding["canary_sha256"] == store.sha(store.probe.fixture(env["GITHUB_RUN_ID"])), "EXACT_INITIALIZED_ROTATION_BINDING")
        before, count = run_operation("pin", dict(binding=binding), root, env, directory, deadline, runner); calls += count
        result = dict(schema_version=VERSION + "-handoff", phase="write", root_go_sha256=sha(canonical(root)), run_id=env["GITHUB_RUN_ID"],
            source_sha=env["GITHUB_SHA"], runtime_id=root["runtime_id"], binding=binding, quota_reservation=quota, before=before)
    else:
        predecessor = "write" if phase == "read" else "read"
        result = checked_handoff(env.get("AUDIT_PRIVATE_ROTATION_HANDOFF_JSON", ""), env.get("AUDIT_PRIVATE_ROTATION_HANDOFF_SHA256", ""),
            predecessor, root, env, verifier)
        authenticate_phase(client, phase, root, env, [(result["before"], "write")] + ([(result["read"], "read")] if phase == "qualify" else []))
        binding = result["binding"]
        if phase == "read":
            read_proof, count = run_operation("boundary", dict(binding=binding, before=result["before"]), root, env, directory, deadline, runner); calls += count
            result = dict(result, phase="read", read=read_proof)
        else:
            proof, count = run_operation("qualify", dict(binding=binding, before=result["before"], read_proof=result["read"]), root, env, directory, deadline, runner); calls += count
            verifier.binding = binding; store.check_proof(verifier, proof, "qualified")
            require(proof["job"]["job_id"] == JOBS["qualify"], "ROTATION_QUALIFY_JOB_PROOF")
            result = dict(schema_version=VERSION + "-qualified-runtime", root_go_sha256=sha(canonical(root)), run_id=env["GITHUB_RUN_ID"],
                source_sha=env["GITHUB_SHA"], runtime_id=root["runtime_id"], binding=binding, qualification=proof,
                quota_reservation=result["quota_reservation"], runtime_reserved_bytes=RUNTIME_CAP, private_payload_bytes=0,
                private_durability_qualified=False, strict_v1_unchanged="INCONCLUSIVE")
    if phase in {"write", "read"}:
        checked_handoff(canonical(result).decode(), sha(canonical(result)), phase, root, env, verifier)
    require(client.calls <= 40 and calls <= 40 * len(OPERATIONS[phase]) and time.monotonic() < deadline, "ROTATION_FINITE_PHASE_BUDGET")
    validate_root(root, now=datetime.now(timezone.utc))
    store.create_local(directory / "PHASE_FINISHED.json", canonical(dict(phase=phase, metadata_HTTP_calls=client.calls,
        native_HTTP_calls=calls, root_go_sha256=sha(canonical(root)), handoff_sha256=sha(canonical(result)), private_payload_bytes=0)))
    output(env, result)  # Last mutation: no fallible resource/status writes after handoff.
    return result
