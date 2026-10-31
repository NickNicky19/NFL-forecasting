"""DRAFT: one owner-bound, GET-only read of one retained failed admission.

Intended install path: tools/audit_weekly_failed_admission_read_v1.py.
Preparation performs no file/credential/network IO. No hosted execution was
performed by this draft. Historical identities remain historical.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
import argparse
import base64
import json
import os
import re
import resource
import signal
import subprocess
import sys

VERSION = "audit-weekly-failed-admission-read-v1"
JOB = VERSION
REPO = "NickNicky19/NFL-forecasting"
BRANCH = "production/archive-admission-read-20261031"
WORKFLOW = REPO + "/.github/workflows/lab.yml@refs/heads/" + BRANCH
ORIGINAL_BRANCH = "research/weekly-storage-probe-v1"
ORIGINAL_WORKFLOW = REPO + "/.github/workflows/lab.yml@refs/heads/" + ORIGINAL_BRANCH
ROOT = Path(__file__).resolve().parents[1]
TOOL = "tools/audit_weekly_failed_admission_read_v1.py"
TEST = "tests/test_failed_admission_reader.py"
GROUP = "nfl-lab-single-writer"
REASON = "EXISTING_PRIVATE_DRAFT_READ_REQUIRES_CONTENTS_WRITE_TOKEN"
QUOTA_REASON = "FULL_ARCHIVE_INDEX_WITNESS_FAILURE_QUOTA_BEFORE_POST"
LIMITS = dict(wall_seconds=180, CPU_seconds=120, address_space_bytes=512 << 20,
    HTTP_calls=40, transfer_bytes=40 << 20, output_bytes=16 << 10,
    POSTs=0, retries=0, model_decodes=0, provider_calls=0, exports=0)
TARGET = dict(run_id="41231404531", source_sha="0409a253d6a365c31a2d421941b8ee5f40d6fd02",
    root_go_sha256="d23dd94003df27351a2c90c455bd0deec6e4f26801ec564cad7e26bf73d43b2d",
    release_id=426251025, runtime_id="adf3d7e86aa66dd02f5d6312cc40952c",
    package_sha256="8aeb5643c35fd2e81f0d03da71254e2e886a7e585d2d1b98726b7f9ad0959cff",
    binding_sha256="58a59333552700d1f490f7b1b1f616fac5ace74528da27a66a260a62c34d20b9",
    manifest_id=696245074, manifest_bytes=662,
    manifest_sha256="74b65808fb3ff980dd7a9c46893f147bc8d2f5c14ccb80c9cc5e141ced4aca9f",
    payload_id=696245027, payload_bytes=91261,
    payload_sha256="c82052f39941ee869e03b7a9370a58fe282aefef53f021e379f2bc9e2f92a669",
    retained_log_sha256="d9b01d70fe7d61914e33c855762af00dcd9beb94da455e1f408f2c9aaf3964bb",
    admission_second="2026-10-31T19:06:32Z", historical_assets=69, historical_bytes=22674543,
    historical_inventory_sha256="541a9fc6ee267e9f2c629e2273aa1c77bd5e16bde3ddd3410dd9b789098168b5")
GO_KEYS = {"schema_version", "approved", "operation", "repository", "source_sha", "workflow_ref",
    "issued_at_utc", "expires_at_utc", "maximum_dispatches", "single_writer_group", "job_id",
    "helper_sha256", "qualified_runtime", "target", "contents_permission", "access_reason", "limits"}


class DiagnosticError(Exception):
    pass


def require(ok, code):
    if not ok:
        raise DiagnosticError(code)


def now():
    return datetime.now(timezone.utc)


def modules():
    # These imports are metadata-only; no providers, models, or numerical runtimes run.
    from nfl_lab import private_draft_store as store, gha_private_checkpoint as cp
    from nfl_lab import operational_failure_v1 as failure, owner_private_bootstrap as owner
    from nfl_lab import audit_private_rotation_v1 as rotation, audit_weekly_hosted_v1 as hosted
    from nfl_lab import audit_weekly_template_v1 as template
    return SimpleNamespace(store=store, cp=cp, failure=failure, owner=owner, rotation=rotation,
        hosted=hosted, template=template)


def dependency_paths(m=None):
    """Complete existing hosted executable closure plus the reader and tests.

    This is a separate diagnostic GO inventory, not a change to the original
    forecast Root's 128-pin ABI or its source-history adapter permissions.
    """
    m = m or modules()
    return tuple(sorted(set(m.hosted.PINS) | {TOOL,TEST,"nfl_lab/__init__.py"}))


def template():
    return dict(schema_version=VERSION + "-root-GO", approved=False,
        operation="READ_EXACT_RETAINED_FAILURE_METADATA_ONLY", repository=REPO, source_sha=None,
        workflow_ref=WORKFLOW, issued_at_utc=None, expires_at_utc=None, maximum_dispatches=1,
        single_writer_group=GROUP, job_id=JOB, helper_sha256={}, qualified_runtime=None,
        target=dict(TARGET), contents_permission="write", access_reason=REASON, limits=dict(LIMITS))


def verify_workflow(raw):
    import yaml
    value = yaml.load(raw, Loader=yaml.BaseLoader)
    require(type(value) is dict and value.get("concurrency") == {"group":GROUP,"cancel-in-progress":"false"},
        "EXACT_EXISTING_SINGLE_WRITER_GROUP")
    job = value.get("jobs", {}).get(JOB)
    require(type(job) is dict and job.get("name", JOB) == JOB and "concurrency" not in job
        and job.get("permissions") == {"contents":"write","actions":"read"}
        and job.get("runs-on") == "ubuntu-latest" and job.get("timeout-minutes") == "4",
        "EXACT_DIAGNOSTIC_PERMISSION_CONTRACT")
    expected_if = "${{ github.event_name == 'workflow_dispatch' && inputs.mode == '"+VERSION+"' && github.run_attempt == 1 }}"
    require(job.get("if") == expected_if, "EXPLICIT_DIAGNOSTIC_MANUAL_JOB_GUARD")
    generic = value.get("jobs", {}).get("lab", {})
    require("inputs.mode != '"+VERSION+"'" in str(generic.get("if", "")),
        "GENERIC_LAB_MUST_EXCLUDE_DIAGNOSTIC_MODE")
    modes = value.get("on", {}).get("workflow_dispatch", {}).get("inputs", {}).get("mode", {}).get("options", [])
    require(VERSION in modes, "EXPLICIT_MANUAL_DIAGNOSTIC_MODE")


def preflight(env, source_root=ROOT, *, read_head=None):
    m = modules(); s = m.store
    raw = env.get("AUDIT_FAILED_ADMISSION_GO_JSON", "").encode()
    require(0 < len(raw) <= 32 << 10 and s.sha(raw) == env.get("AUDIT_FAILED_ADMISSION_GO_SHA256"),
        "EXACT_DIAGNOSTIC_GO_HASH")
    go = m.cp.strict_json(raw)
    require(s.canonical(go) == raw and type(go) is dict and set(go) == GO_KEYS
        and go["schema_version"] == VERSION + "-root-GO" and go["approved"] is True
        and go["operation"] == "READ_EXACT_RETAINED_FAILURE_METADATA_ONLY"
        and go["repository"] == REPO and go["workflow_ref"] == WORKFLOW and go["target"] == TARGET
        and go["maximum_dispatches"] == 1 and type(go["maximum_dispatches"]) is int
        and go["single_writer_group"] == GROUP and go["job_id"] == JOB
        and go["contents_permission"] == "write" and go["access_reason"] == REASON and go["limits"] == LIMITS,
        "CLOSED_OWNER_DIAGNOSTIC_GO")
    issued, expires = s.utc(go["issued_at_utc"]), s.utc(go["expires_at_utc"])
    require(issued <= now() < expires and timedelta(0) < expires-issued <= timedelta(hours=1),
        "FRESH_DIAGNOSTIC_GO")
    require(re.fullmatch(r"[a-f0-9]{40}", str(go["source_sha"]))
        and all(env.get(k) == v for k,v in dict(GITHUB_ACTIONS="true",CI="true",RUNNER_ENVIRONMENT="github-hosted",
            GITHUB_REPOSITORY=REPO,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",
            GITHUB_JOB=JOB,STORE_PERMISSION="write",GITHUB_WORKFLOW_REF=WORKFLOW,
            GITHUB_REF="refs/heads/"+BRANCH,GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933").items())
        and env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == go["source_sha"]
        and env.get("GITHUB_WORKSPACE") == str(source_root)
        and re.fullmatch(r"[1-9][0-9]{10}", env.get("GITHUB_RUN_ID", "")),
        "ACTUAL_OWNER_DIAGNOSTIC_CONTEXT_REQUIRED")
    command = read_head or (lambda args: subprocess.check_output(args, cwd=source_root, text=True))
    require(command(["git","rev-parse","HEAD"]).strip() == go["source_sha"], "EXACT_DIAGNOSTIC_CHECKOUT")
    paths = dependency_paths(m)
    require(command(["git","status","--porcelain","--untracked-files=all","--",*paths]) == "",
        "COMMITTED_DIAGNOSTIC_HELPERS_REQUIRED")
    expected = {p:s.sha(s.read_local(source_root/p, 2 << 20)) for p in paths}
    require(go["helper_sha256"] == expected, "EXACT_DIAGNOSTIC_SOURCE_PINS")
    verify_workflow(s.read_local(source_root/".github/workflows/lab.yml", 256 << 10))
    event = m.cp.strict_json(s.read_local(env["GITHUB_EVENT_PATH"], 256 << 10))
    inputs = event.get("inputs", {})
    require(inputs.get("mode") == VERSION and inputs.get("inference_builder_go_json") == raw.decode()
        and inputs.get("inference_builder_go_sha256") == s.sha(raw)
        and event.get("repository", {}).get("full_name") == REPO
        and event.get("ref") in {BRANCH,"refs/heads/"+BRANCH}, "EXACT_ACTUAL_DIAGNOSTIC_EVENT")
    pin_package(go["qualified_runtime"], TARGET, m)
    return go


def pin_package(package, target, m):
    s = m.store
    require(type(package) is dict and s.sha(s.canonical(package)) == target["package_sha256"],
        "EXACT_REGISTERED_QUALIFIED_PACKAGE")
    binding = s.checked_binding(package["binding"])
    require(binding["release_id"] == target["release_id"] and binding["runtime_id"] == target["runtime_id"]
        and s.sha(s.canonical(binding)) == target["binding_sha256"], "EXACT_REGISTERED_FAILURE_NAMESPACE")
    return binding


def client_type():
    s = modules().store
    class Reader(s.Client):
        """A contents:write token is constrained to fixed GET routes here."""
        def __init__(self, *args, target, package, **kwargs):
            self.target, self.package = target, package
            self.metadata = {}
            current = str(args[1])
            ids = {current,target["run_id"],package["qualification"]["run_id"]}
            self.fixed = {s.API+"/actions/runs/"+r+suffix for r in ids for suffix in ("","/jobs?per_page=100&page=1")}
            self.fixed.add(s.API+"/releases/"+str(target["release_id"]))
            self.fixed.update(s.API+"/releases/"+str(target["release_id"])+f"/assets?per_page=100&page={p}" for p in range(1,5))
            self.payload_urls = {s.API+"/releases/assets/"+str(target[k]) for k in ("manifest_id","payload_id")}
            self.fixed.update(self.payload_urls)
            # bind() registers the original canary routes, but bodies remain forbidden.
            binding = package["binding"]
            self.registration_only = {s.API+"/releases/assets/"+str(binding["canary_asset_id"]),
                "https://github.com/"+REPO+"/releases/download/"+binding["browser_tag"]+"/"+binding["canary_name"]}
            super().__init__(*args, **kwargs)
        def allow(self, url):
            require(url in self.fixed | self.registration_only, "DIAGNOSTIC_FIXED_GET_ROUTE_ONLY")
            self.allowed.add(url)
            return url
        def request(self, url, *, method="GET", **kwargs):
            require(method == "GET" and kwargs.get("data") is None and url in self.fixed,
                "DIAGNOSTIC_GET_ONLY")
            require(not (kwargs.get("octet") or kwargs.get("download")) or url in self.payload_urls,
                "ONLY_TWO_PINNED_FAILURE_BODIES")
            return super().request(url, method=method, **kwargs)
        def json(self, url, **kwargs):
            value = super().json(url, **kwargs)
            if "/actions/runs/" in url:
                self.metadata[url] = value
            return value
        def read_asset(self, asset_id, name, size, digest):
            expected = {(self.target["manifest_id"],"manifest-"+self.target["manifest_sha256"]+".json",
                self.target["manifest_bytes"],self.target["manifest_sha256"]),
                (self.target["payload_id"],"blob-"+self.target["payload_sha256"]+".bin",
                self.target["payload_bytes"],self.target["payload_sha256"])}
            require((asset_id,name,size,digest) in expected, "EXACT_TWO_FAILURE_ASSET_IDENTITIES")
            return super().read_asset(asset_id,name,size,digest)
        def reserve(self, *args, **kwargs):
            raise DiagnosticError("DIAGNOSTIC_RESERVATION_FORBIDDEN")
        def reserve_post(self, *args, **kwargs):
            raise DiagnosticError("DIAGNOSTIC_RESERVATION_FORBIDDEN")
        def upload(self, *args, **kwargs):
            raise DiagnosticError("DIAGNOSTIC_UPLOAD_FORBIDDEN")
    return Reader


def verify_current(client, go, m):
    client.authenticate_actions_job()
    base = m.store.API+"/actions/runs/"+client.run_id
    run, listing = client.metadata[base], client.metadata[base+"/jobs?per_page=100&page=1"]
    owner = dict(login="NickNicky19",id=208912933)
    require(all(type(run.get(k)) is dict and all(run[k].get(n) == v for n,v in owner.items())
        for k in ("actor","triggering_actor")) and run.get("head_branch") == BRANCH,
        "ACTUAL_DIAGNOSTIC_RUN_OWNER_AND_BRANCH")
    jobs = [j for j in listing["jobs"] if j.get("id") == client.job["api_job_id"]]
    require(len(jobs) == 1 and m.store.utc(go["issued_at_utc"]) <= m.store.utc(jobs[0]["started_at"])
        <= m.store.utc(client.started_at) <= now() < m.store.utc(go["expires_at_utc"]),
        "ACTUAL_DIAGNOSTIC_JOB_CLOCK")


def reconstruct(client, target, m):
    """No caller-provided descriptor, handoff, original Root, or PASS is accepted."""
    s = m.store
    raw = client.read_asset(target["manifest_id"], "manifest-"+target["manifest_sha256"]+".json",
        target["manifest_bytes"], target["manifest_sha256"])
    entry = m.cp.strict_json(raw)
    descriptor = dict(entry=entry,manifest_asset_id=target["manifest_id"],
        manifest_sha256=target["manifest_sha256"],manifest_bytes=target["manifest_bytes"])
    m.cp.descriptor_meta(descriptor,m.failure.PACKAGE_CAP)
    require(raw == s.canonical(entry) and entry["writer_run_id"] == target["run_id"]
        and entry["binding_sha256"] == target["binding_sha256"]
        and entry["payload_asset_id"] == target["payload_id"]
        and entry["payload"] == dict(schema_version="weekly-private-payload-v2",payload_kind="runtime_manifest",format="gzip",
            bytes=target["payload_bytes"],sha256=target["payload_sha256"],source_policy_sha256=m.cp.POLICY_SHA),
        "PINNED_FAILURE_MANIFEST_ENTRY")
    body = client.read_asset(target["payload_id"],entry["payload_name"],target["payload_bytes"],target["payload_sha256"])
    request, _ = m.failure.unpack(body)
    require(request["attempt"] == dict(repository=REPO,run_id=target["run_id"],run_attempt=1,
        source_sha=target["source_sha"],job_id=m.hosted.JOBS["produce"],workflow_ref=ORIGINAL_WORKFLOW)
        and request["operation"] == "producer" and request["state"] == "FAILED"
        and request["input_contract_sha256"] == target["root_go_sha256"], "EXACT_ORIGINAL_FAILURE_REQUEST")
    return dict(schema_version=m.hosted.VERSION+"-failure-handoff",binding=client.binding,
        descriptor=descriptor,root_go_sha256=request["input_contract_sha256"])


def verify_qualification(client, package, census, before, m):
    """After authenticated old Root/census; no additional canary body download."""
    s = m.store; q = package["qualification"]
    require(package["schema_version"] == m.rotation.VERSION+"-qualified-runtime"
        and package["runtime_reserved_bytes"] == s.TOTAL_CAP
        and package["runtime_id"] == client.binding["runtime_id"]
        and package["run_id"] == q["run_id"] == client.binding["origin_run_id"]
        and package["source_sha"] == q["source_sha"], "REGISTERED_QUALIFICATION_PACKAGE_BINDING")
    m.rotation.checked_quota(package["quota_reservation"],dict(runtime_id=package["runtime_id"],pending_census=census))
    # Reuse the strict original census row/type/clock validator, without IO or grant.
    from nfl_lab.audit_weekly_grade_history_v1 import _source_history_rotation_quota
    _source_history_rotation_quota(package,census,before=before)
    m.owner.archived_qualification(client.binding,q)
    s.check_proof(client,q,"qualified",same_run=False)
    m.owner.authenticate_past_run(client,q)
    base = s.API+"/actions/runs/"+q["run_id"]
    run = client.metadata[base]
    require(run.get("head_branch") == q["job"]["workflow_ref"].split("@refs/heads/",1)[1]
        and run.get("actor",{}).get("login") == "NickNicky19" and run.get("actor",{}).get("id") == 208912933,
        "ACTUAL_NATIVE_QUALIFICATION_OWNER")
    listing = client.metadata[base+"/jobs?per_page=100&page=1"]
    for proof, phase in zip((q["before_proof"],q["read_proof"],q),("write","read","qualify")):
        require(proof["job"]["job_id"] == m.rotation.JOBS[phase], "EXACT_NATIVE_ROTATION_JOB_ROLE")
        jobs = [j for j in listing["jobs"] if j.get("id") == proof["job"]["api_job_id"]]
        require(len(jobs) == 1 and s.utc(jobs[0]["completed_at"]) <= s.utc(client.started_at),
            "NATIVE_QUALIFICATION_PRECEDES_READER")
    denied = [r for r in q["read_proof"]["routes"] if r["principal"] == "contents_read"]
    require(denied and all(r["status"] == 403 and r["resource_permission_message_exact_match"] is True for r in denied),
        "REGISTERED_READ_TOKEN_DENIAL_EVIDENCE")
    return len(denied)


def projection(assets):
    keys = ("id","name","size","state","digest","created_at")
    return sorted(({k:a[k] for k in keys} for a in assets),key=lambda a:a["id"])


def auxiliary_controls(controls, m):
    out = {}
    for label, (_,raw) in controls.items():
        if not re.fullmatch(r"complete-auxiliary-controls(?:-[0-9]{2})?",label):
            continue
        value = m.cp.strict_json(raw)
        require(type(value) is dict and set(value) == {"schema_version","files"}
            and value["schema_version"] == m.hosted.VERSION+"-complete-auxiliary-controls"
            and type(value["files"]) is list and len(value["files"]) <= 128,"CLOSED_AUXILIARY_CONTROLS")
        for item in value["files"]:
            require(type(item) is dict and set(item) == {"relative_path","bytes","sha256","body_base64"},
                "CLOSED_AUXILIARY_CONTROL")
            name = item["relative_path"]; path = PurePosixPath(name)
            require(type(name) is str and not path.is_absolute() and path.as_posix() == name
                and ".." not in path.parts and "\\" not in name and name not in out,"CLOSED_AUXILIARY_PATH")
            body = base64.b64decode(item["body_base64"],validate=True)
            require(type(item["bytes"]) is int and len(body) == item["bytes"] <= 64 << 10
                and m.store.sha(body) == item["sha256"],"EXACT_AUXILIARY_CONTROL_BYTES")
            out[name] = body
    return out


def aggregate(evidence, records, assets, package, target, denied_routes, m):
    s = m.store; old = evidence["root"]; controls = evidence["controls"]
    require(s.sha(s.canonical(old)) == target["root_go_sha256"]
        and s.canonical(old["qualified_runtime"]) == s.canonical(package),"ORIGINAL_ROOT_REGISTERED_PACKAGE")
    original_pending = m.template.pending_recovery(old)["pending_reservations"]
    observed = {r["key"]:r for r in records}
    require(all(observed.get(r["key"]) == r for r in original_pending),"COMPLETE_ORIGINAL_ARCHIVE_SEEDED_PENDING")
    cut = s.utc(target["admission_second"])
    request = evidence["request"]
    require(request["state"] == "FAILED" and request["operation"] == "producer"
        and s.utc(request["clocks"]["started_at_utc"]) <= cut
        <= s.utc(request["clocks"]["observed_at_utc"]),"ORIGINAL_REQUEST_STATE_AND_ADMISSION_CLOCK_WINDOW")
    # child() writes {exit_code,status:{reason,...},actual_completed_at};
    # execute() separately writes PARENT_FAILED with top-level reason/time.
    # Authenticate both forms when present; neither shape is an authority flag.
    reason_matches = []
    for label,(_,raw) in controls.items():
        if not re.fullmatch(r"phase-[0-9]{2}",label):continue
        document = m.cp.strict_json(raw)
        require(type(document) is dict,"BOUNDED_ORIGINAL_PHASE_STATUS")
        if document.get("reason") == QUOTA_REASON:
            reason_matches.append(("PARENT_REASON",document.get("actual_observed_at")))
        if type(document.get("status")) is dict and document["status"].get("reason") == QUOTA_REASON:
            reason_matches.append(("CHILD_STATUS_REASON",document.get("actual_completed_at")))
    for _,stamp in reason_matches:
        require(stamp is not None and cut <= s.utc(stamp) < cut+timedelta(seconds=1)
            and s.utc(request["clocks"]["started_at_utc"]) <= s.utc(stamp)
            <= s.utc(request["clocks"]["observed_at_utc"]),"ORIGINAL_PHASE_REASON_CLOCK")
    require(all(s.utc(a["created_at"]) != cut for a in assets),"HISTORICAL_INVENTORY_SECOND_AMBIGUITY")
    historical = [a for a in assets if s.utc(a["created_at"]) < cut]
    require(len(historical) == target["historical_assets"] and sum(a["size"] for a in historical) == target["historical_bytes"]
        and s.sha(s.canonical(projection(historical))) == target["historical_inventory_sha256"],
        "EXACT_RETAINED_APPEND_ONLY_HISTORICAL_INVENTORY")
    unmatched = [r for r in records if not any(a["name"] == r["name"] and a["size"] == r["bytes"]
        and a.get("digest") == "sha256:"+r["sha256"] for a in historical)]
    seeded = {r["key"] for r in original_pending}
    nonseeded_unmatched = [r for r in unmatched if r["key"] not in seeded]
    # A journal record has no issue clock. This fixed failed source reached the
    # archive quota guard before any archive POST, and the available controls
    # contain no bounded clocked admission intent proving any unmatched newly
    # issued record existed before that guard. Fail closed rather than charge
    # a preservation POST as original pending, or silently omit an old intent.
    require(not nonseeded_unmatched,"UNMATCHED_NONSEEDED_PRE_ADMISSION_ELIGIBILITY_REQUIRED")
    aux = auxiliary_controls(controls,m)
    graph = m.cp.strict_json(controls["file-graph"][1])
    require(type(graph) is dict and graph.get("schema_version") == m.hosted.VERSION+"-failed-file-graph"
        and type(graph.get("files")) is list and len(graph["files"]) <= 1024,"BOUNDED_ORIGINAL_FILE_GRAPH")
    group_refs = [f for f in graph["files"] if re.fullmatch(r"archive-produce/transport/preencoded/[0-7]\.gz",f.get("relative_path",""))]
    admissions = [p for p in aux if p in {"archive-produce/transport/ADMISSION.json","failure-archive-produce/ADMISSION.json"}]
    # This fixed source rejected before writing ADMISSION, and its complete-file
    # graph excluded both archive subtrees. Never infer gzip sizes from originals.
    require(not group_refs and not admissions,"UNEXPECTED_ENCODED_ADMISSION_EVIDENCE_REQUIRES_REVIEW")
    census = old["pending_census"]; buckets = defaultdict(lambda:dict(records=0,bytes=0,assets=0))
    for row in census["reservations"]:
        key = (row["runtime_id"],row["release_id"])
        bucket = buckets[key]; bucket["records"] += 1
        bucket["bytes"] += row["pending_bytes"]; bucket["assets"] += row["pending_assets"]
    require(len(buckets) <= 16,"BOUNDED_ORIGINAL_RUNTIME_CENSUS_SUMMARY")
    owners = []
    for (runtime,release),v in sorted(buckets.items(),key=lambda x:(str(x[0][0]),str(x[0][1]))):
        owners.append(dict(runtime_id=runtime,release_id=release,**v,purpose="REGISTERED_PENDING_ALLOCATION",
            owner_state="OWNER_BOUND_CENSUS_ORIGINAL_POST_ISSUER_NOT_IN_ROW"))
    purposes = Counter()
    for r in records:
        origin = "INHERITED_SEEDED_RESERVATION" if r["key"] in seeded else "ORIGINAL_ATTEMPT_INTENT"
        purpose = "RESTORE_MANIFEST" if r["name"].startswith("manifest-") else "BLOB_PURPOSE_NOT_RETAINED"
        purposes[(origin,purpose)] += 1
    return dict(schema_version=VERSION+"-metadata",state="AUTHENTICATED_RETAINED_FAILURE_METADATA",
        original_attempt=dict(run_id=target["run_id"],source_sha=target["source_sha"],root_go_sha256=target["root_go_sha256"]),
        permission_contract=dict(contents="write",actions="read",GET_only=True,reason=REASON,
            archived_contents_read_denied_routes=denied_routes,POSTs=0,reservations=0),
        qualification_scope="ARCHIVED_NATIVE_PROOFS_AND_CURRENT_CANARY_METADATA_ONLY",current_canary_body_downloaded=False,
        historical_inventory=dict(state="EXACT_RETAINED_APPEND_ONLY_METADATA_PROJECTION",assets=len(historical),bytes=sum(a["size"] for a in historical)),
        current_inventory=dict(assets=len(assets),bytes=sum(a["size"] for a in assets)),
        original_census=dict(complete=census["complete"],as_of_utc=census["as_of_utc"],owner_evidence_sha256=census["owner_evidence_sha256"],
            sha256=s.sha(s.canonical(census)),records=len(census["reservations"]),runtime_allocations=owners,
            reservations=[{k:r[k] for k in ("reservation_sha256","runtime_id","release_id","pending_bytes","pending_assets")}
                for r in census["reservations"]]),
        pending=dict(authenticated_original_journal_records=len(records),archive_seeded_records=len(original_pending),
            unmatched_at_admission_records=len(unmatched),unmatched_at_admission_bytes=sum(r["bytes"] for r in unmatched),
            existing_admission_bytes=sum(a["size"] for a in historical)+sum(r["bytes"] for r in unmatched),
            existing_admission_slots=len(historical)+len(unmatched),
            owner_purpose=[dict(origin=o,purpose=p,records=n,
                original_issuer_run_id=target["run_id"] if o == "ORIGINAL_ATTEMPT_INTENT" else None,
                original_issuer_source_sha=target["source_sha"] if o == "ORIGINAL_ATTEMPT_INTENT" else None)
                for (o,p),n in sorted(purposes.items())]),
        archive=dict(original_reason=QUOTA_REASON if reason_matches else None,
            original_reason_state="AUTHENTICATED_CORE_STATUS" if reason_matches else "CORE_REASON_UNKNOWN",
            status_reason_match_count=len(reason_matches),status_reason_shapes=sorted({shape for shape,_ in reason_matches}),
            retained_log_sha256=target["retained_log_sha256"],admission_clock_source="PINNED_RETAINED_LOG_WITHIN_AUTHENTICATED_REQUEST_WINDOW",
            encoded_group_count=None,encoded_group_bytes=None,
            exact_requested_bytes=None,exact_rejected_deficit_bytes=None,state="UNKNOWN_PREENCODED_AND_ADMISSION_NOT_RETAINED",
            admission_artifacts=0,preencoded_group_references=0,index_reserve_bytes=512 << 10,
            entry_reserve_bytes=16 << 10,witness_reserve_bytes=256 << 10,failure_reserve_bytes=m.failure.PACKAGE_CAP+(16 << 10),
            group_limit=8,reserved_slots_equation="2G_PLUS_6",fixed_reserve_bytes_equation="6493526_PLUS_16384G"),
        fits=0,provider_calls=0,model_decodes=0,exports=0,remote_writes=0,successful_forecast=False,public_release=False)


def read_diagnostic(client, package, *, before, target=None):
    """Pure orchestration around the real store reader; injectable target is test-only."""
    m = modules(); s = m.store
    target = TARGET if target is None else target
    pin_package(package,target,m)
    client.bind(package["binding"]); client.draft(); assets,_ = client.inventory()
    first = projection(assets)
    handoff = reconstruct(client,target,m)
    evidence = {}
    records = m.hosted.authenticated_pending_records(client,handoff,assets,before=before,_evidence=evidence)
    require(s.canonical(evidence["root"]["qualified_runtime"]) == s.canonical(package),"EXACT_FAILED_ROOT_PACKAGE")
    seeded = m.template.pending_recovery(evidence["root"])["pending_reservations"]
    observed = {r["key"]:r for r in records}
    require(all(observed.get(r["key"]) == r for r in seeded),"COMPLETE_ORIGINAL_ARCHIVE_SEEDED_PENDING")
    denied = verify_qualification(client,package,evidence["root"]["pending_census"],before,m)
    b = client.binding
    canaries = [a for a in assets if a["id"] == b["canary_asset_id"]]
    require(len(canaries) == 1,"CURRENT_CANARY_METADATA_IN_REGISTERED_NAMESPACE")
    client.asset(canaries[0],b["canary_name"],117,b["canary_sha256"])
    result = aggregate(evidence,records,assets,package,target,denied,m)
    client.draft(); final,_ = client.inventory()
    require(projection(final) == first,"DIAGNOSTIC_INVENTORY_CHANGED_NO_RESULT")
    result.update(HTTP_calls=client.calls,transfer_bytes=client.transferred)
    return result


def safe_summary(value):
    raw = modules().store.canonical(value)
    require(len(raw) <= LIMITS["output_bytes"] and not any(x in raw.lower() for x in
        (b"https://",b"/home/",b"/tmp/",b"ghs_",b"body_base64",b"content_b64",b"qualified_runtime\"",b"attachments\"")),
        "BOUNDED_AGGREGATE_METADATA_ONLY")
    return raw


def execute(env, source_root=ROOT):
    m = modules(); s = m.store
    go = preflight(env,source_root)
    directory = s.parents_safe(Path(env["RUNNER_TEMP"])/(VERSION+"-"+env["GITHUB_RUN_ID"]))
    require(not directory.exists(),"ONE_DIAGNOSTIC_ATTEMPT_NO_RETRY")
    directory.mkdir(mode=0o700); journal = directory/"journal"; journal.mkdir(mode=0o700)
    s.create_local(directory/"READ_INTENT.json",s.canonical(dict(schema_version=VERSION+"-intent",
        root_go_sha256=s.sha(s.canonical(go)),target_run_id=TARGET["run_id"],retries=0,POSTs=0)))
    job = dict(execution_lane="github_actions",workflow_ref=WORKFLOW,workflow_sha=go["source_sha"],job_id=JOB,
        permission="write",event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
    client = client_type()(env.get("GITHUB_TOKEN"),env["GITHUB_RUN_ID"],journal=journal,
        source_sha=go["source_sha"],job=job,operation="metadata",target=TARGET,package=go["qualified_runtime"])
    verify_current(client,go,m)
    result = read_diagnostic(client,go["qualified_runtime"],before=go["issued_at_utc"])
    verify_current(client,go,m)
    result["reader"] = dict(run_id=client.run_id,source_sha=client.source_sha,api_job_id=client.job["api_job_id"],
        root_go_sha256=s.sha(s.canonical(go)))
    result.update(HTTP_calls=client.calls,transfer_bytes=client.transferred)
    encoded = safe_summary(result)
    s.create_local(directory/"METADATA_RECEIPT.json",encoded)
    return encoded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("template","read")); parser.add_argument("--execute",action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        value = template() if args.phase == "template" else dict(state="PREPARATION_ONLY_NO_IO",remote_writes=0)
        print(json.dumps(value,sort_keys=True))
        return 0 if args.phase == "template" else 2
    if args.phase != "read":
        print('{"state":"FAILED","reason":"EXPLICIT_READ_PHASE_REQUIRED","remote_writes":0}')
        return 1
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(120,120)); resource.setrlimit(resource.RLIMIT_AS,(512 << 20,512 << 20))
        signal.signal(signal.SIGALRM,signal.SIG_DFL); signal.alarm(180)
        sys.path.insert(0,str(ROOT))
        print(execute(os.environ).decode())
        return 0
    except Exception as error:
        code = getattr(error,"code",str(error))
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",code):
            code = "FAILED_ADMISSION_DIAGNOSTIC_STOPPED"
        print(json.dumps(dict(state="FAILED",reason=code,remote_writes=0,retries=0,public_release=False),sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
