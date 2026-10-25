"""Versioned, GET-only cross-run recovery of a registered effective18 subset.

Historical and current identities remain separate. This does not call or alter
the same-run checkpoint.restore, reuse expired authority, fit, issue forecasts,
publish, or register new catalog/weekly choices. Import starts no operation.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
import io
from pathlib import Path
import re
from urllib.parse import quote

from . import audit_count_checkpoint_v1 as effective, audit_count_requalify_v1 as audit
from . import gha_private_checkpoint as cp, owner_bootstrap_bundle as codec
from . import owner_private_bootstrap as owner, private_draft_store as store
from .owned_reference_batch import validate_owned_references

VERSION = "audit-count-retained-v1"
MODE = VERSION
OPERATION = "RESTORE_REGISTERED_RETAINED_EFFECTIVE18_PRIVATE_ONLY"
REGISTRATION_CAP = 256 << 10
GO_CAP = 32 << 10
SOURCE_CAP = 256 << 10
NUMERIC_FILES = ("weekly_future_inference.py", "cdf_engine.py", "role_boosting.py",
                 "direct_boosters.py", "median_boosting.py", "baseline_correction.py")
HISTORICAL_FILES = tuple("nfl_lab/" + name for name in NUMERIC_FILES) + (
    "nfl_lab/audit_count_checkpoint_v1.py", "nfl_lab/audit_count_requalify_v1.py",
    "nfl_lab/private_draft_store.py", "nfl_lab/owner_bootstrap_bundle.py",
    "tools/audit_count_checkpoint_v1.py", "tools/audit_count_verification_receipt_v1.py")
CURRENT_FILES = tuple(sorted(set(HISTORICAL_FILES) | {
    "nfl_lab/audit_count_retained_v1.py", "tools/audit_count_retained_v1.py",
    "nfl_lab/gha_private_checkpoint.py", "nfl_lab/owner_private_bootstrap.py",
    "nfl_lab/operational_storage.py", "nfl_lab/owned_reference_batch.py",
    "tools/private_draft_store_v2.py", "tools/ngboost_law_software_v1.py",
    "tools/review_direct_booster_screen_guard_v4.py", ".github/workflows/lab.yml",
    "config/operational-source-policy-v2.json", "config/private-draft-storage-v2.json",
    "config/weekly-owner-private-bootstrap-v1.json", "config/gha-private-checkpoint-v3.json",
    "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json",
    "requirements.lock", "requirements-hosted-fixed-build-v1.lock"}))
REG_KEYS = {"schema_version", "approved", "state", "repository", "registered_at_utc", "origin",
    "model_code_sha256", "qualified_runtime", "pending_reservations", "runtime_envelopes",
    "maximum_new_fits", "forecasts", "protected_outcome_reads", "remote_writes", "public_release"}
ORIGIN_KEYS = {"run_id", "source_sha", "workflow_ref", "run_conclusion", "handoff", "reader",
    "verification_receipt", "restore_control_sha256", "replay_catalog",
    "verification_check_run_id", "verification_body_sha256", "source_code_sha256"}
GO_KEYS = {"schema_version", "approved", "repository", "operation", "registration_sha256", "mode",
    "source_sha", "run_attempt", "job_id", "workflow_ref", "issued_at_utc", "expires_at_utc",
    "single_writer_group", "helper_sha256", "owner_authorization", "maximum_new_fits", "forecasts",
    "protected_outcome_reads", "remote_writes", "public_release"}
ZERO_FIELDS = ("maximum_new_fits", "forecasts", "protected_outcome_reads", "remote_writes")
PAST_READER_KEYS = {"repository", "run_id", "run_attempt", "source_sha", "job_id", "api_job_id", "workflow_ref"}


def require(value, code):
    if not value:
        raise store.StoreError(code)


def now():
    return datetime.now(timezone.utc)


def current_pins(root):
    return {name: store.sha(store.read_local(Path(root)/name, 2 << 20)) for name in CURRENT_FILES}


def model_pins(root):
    return {name: store.sha(store.read_local(Path(root)/"nfl_lab"/name, SOURCE_CAP)) for name in NUMERIC_FILES}


def templates(root):
    registration = dict(schema_version=VERSION+"-registration", approved=False, state="PREPARED_UNREGISTERED",
        repository=store.REPO, registered_at_utc=None, origin={key:None for key in ORIGIN_KEYS},
        model_code_sha256=model_pins(root), qualified_runtime=dict(binding_sha256=None, qualification_sha256=None),
        pending_reservations=[], runtime_envelopes=audit.shared_envelopes(), maximum_new_fits=0, forecasts=0,
        protected_outcome_reads=0, remote_writes=0, public_release=False)
    registration["origin"]["source_code_sha256"] = {name:None for name in HISTORICAL_FILES}
    go = dict(schema_version=VERSION+"-GO", approved=False, repository=store.REPO, operation=OPERATION,
        registration_sha256=None, mode=MODE, source_sha=None, run_attempt=1, job_id=None,
        workflow_ref=None, issued_at_utc=None, expires_at_utc=None, single_writer_group="nfl-lab-single-writer",
        helper_sha256=current_pins(root), owner_authorization="OWNER_REGISTERED_RETAINED_EFFECTIVE18_V1",
        maximum_new_fits=0, forecasts=0, protected_outcome_reads=0, remote_writes=0, public_release=False)
    return registration, go


def identity(value, label):
    require(type(value) is dict and set(value) == effective.PRODUCER_KEYS
        and value["execution_lane"] == "github_actions" and value["repository"] == store.REPO
        and value["job_id"] == label and value["permission"] == "write"
        and type(value["run_attempt"]) is int and value["run_attempt"] == 1
        and type(value["api_job_id"]) is int and value["api_job_id"] > 0
        and re.fullmatch(r"[1-9][0-9]{0,19}", str(value["run_id"]))
        and re.fullmatch(r"[a-f0-9]{40}", str(value["source_sha"]))
        and store.HASH.fullmatch(str(value["process_identity"]))
        and re.fullmatch(re.escape(store.REPO)+r"/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+",
                         str(value["workflow_ref"])), "CLOSED_RETAINED_ACTIONS_IDENTITY")


def prepare_from_metadata(root, verification_path, catalog_path, handoff_path, check_run_id, *, run_conclusion=None):
    """Offline metadata/public Git source only. Both approvals stay false."""
    from tools import audit_count_verification_receipt_v1 as receipt
    import subprocess
    require(not Path(handoff_path).stat().st_mode & 0o077, "PRIVATE_RETAINED_HANDOFF_FILE_REQUIRED")
    public = cp.strict_json(store.read_local(verification_path,32 << 10))
    catalog = cp.strict_json(store.read_local(catalog_path,16 << 10))
    handoff = cp.strict_json(store.read_local(handoff_path,16384))
    require(type(public) is dict and set(public) == receipt.PUBLIC_KEYS and public["schema_version"] == receipt.VERSION,
        "EXACT_REGISTERED_PUBLIC_VERIFICATION")
    effective.safe_handoff(handoff)
    catalog_body = effective.safe_replay_catalog(catalog)
    require(public["replay_catalog"] == catalog and public["replay_catalog_sha256"] == store.sha(catalog_body)
        and public["source_sha"] == catalog["source_sha"] == handoff["source_sha"]
        and public["run_id"] == catalog["run_id"] == handoff["run_id"]
        and public["root_go_sha256"] == handoff["root_go_sha256"]
        and public["reader_job_id"] == effective.READER_JOB and public["model_artifact_durability"] is True
        and type(check_run_id) is int and check_run_id > 0 and run_conclusion in {None,"success","failure"},
        "BOUND_ACTUAL_RETAINED_METADATA")
    registration, go = templates(root)
    code = {}
    for name in HISTORICAL_FILES:
        size = subprocess.check_output(["git","cat-file","-s",handoff["source_sha"]+":"+name],cwd=root,text=True,timeout=10)
        require(size.strip().isdigit() and 0 < int(size) <= SOURCE_CAP,"HISTORICAL_SOURCE_CODE_CAP")
        raw = subprocess.check_output(["git","show",handoff["source_sha"]+":"+name],cwd=root,timeout=10,stderr=subprocess.DEVNULL)
        require(len(raw) == int(size),"HISTORICAL_SOURCE_CODE_SIZE")
        code[name] = store.sha(raw)
    require(all(registration["model_code_sha256"][name] == code["nfl_lab/"+name] for name in NUMERIC_FILES),
        "REQUALIFICATION_REQUIRED_MODEL_CODE_CHANGED")
    archived = cp.strict_json(store.read_local(Path(root)/"reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json",store.META_CAP))
    config = cp.strict_json(store.read_local(Path(root)/"config/gha-private-checkpoint-v3.json",1 << 20))
    require(archived["binding"] == handoff["runtime_binding"],"EXACT_REGISTERED_RETAINED_RUNTIME")
    summary = store.canonical(public).decode()
    payload = dict(name=receipt.NAME,head_sha=handoff["source_sha"],status="completed",conclusion="success",
                   external_id=handoff["run_id"]+":1",output=dict(title=receipt.TITLE,summary=summary))
    registration["origin"] = dict(run_id=handoff["run_id"],source_sha=handoff["source_sha"],
        workflow_ref=handoff["producer"]["workflow_ref"],run_conclusion=run_conclusion,handoff=handoff,
        reader=dict(repository=store.REPO,run_id=handoff["run_id"],run_attempt=1,source_sha=handoff["source_sha"],
            job_id=effective.READER_JOB,api_job_id=public["reader_api_job_id"],workflow_ref=handoff["producer"]["workflow_ref"]),
        verification_receipt=public,restore_control_sha256=public["restored_control_sha256"],replay_catalog=catalog,
        verification_check_run_id=check_run_id,verification_body_sha256=store.sha(store.canonical(payload)),source_code_sha256=code)
    registration["qualified_runtime"] = dict(binding_sha256=store.sha(store.canonical(archived["binding"])),
        qualification_sha256=store.sha(store.canonical(archived["qualification"])))
    registration["pending_reservations"] = config["external_pending_reservations"]
    go["registration_sha256"] = store.sha(store.canonical(registration))
    return registration,go


def validate_registration(registration):
    r = registration
    require(type(r) is dict and set(r) == REG_KEYS and r["schema_version"] == VERSION+"-registration"
        and r["approved"] is True and r["state"] == "ROOT_REGISTERED_RETAINED_EFFECTIVE18"
        and r["repository"] == store.REPO and r["runtime_envelopes"] == audit.shared_envelopes()
        and all(type(r[k]) is int and r[k] == 0 for k in ZERO_FIELDS) and r["public_release"] is False,
        "REGISTERED_RETAINED_SUCCESS_REQUIRED")
    require(store.utc(r["registered_at_utc"]) <= now(), "RETAINED_REGISTRATION_CLOCK")
    o = r["origin"]
    require(type(o) is dict and set(o) == ORIGIN_KEYS and o["run_conclusion"] in {"success", "failure"},
        "CLOSED_RETAINED_ORIGIN")
    effective.safe_handoff(o["handoff"])
    producer = o["handoff"]["producer"]
    identity(producer, effective.WRITER_JOB)
    reader = o["reader"]
    require(type(reader) is dict and set(reader) == PAST_READER_KEYS and reader["repository"] == store.REPO
        and type(reader["run_attempt"]) is int and reader["run_attempt"] == 1
        and reader["job_id"] == effective.READER_JOB and type(reader["api_job_id"]) is int and reader["api_job_id"] > 0,
        "CLOSED_ORIGINAL_VERIFIED_READER_API_IDENTITY")
    require(all(v["run_id"] == o["run_id"] and v["source_sha"] == o["source_sha"]
                and v["workflow_ref"] == o["workflow_ref"] for v in (producer,reader)), "REGISTERED_WRITER_READER_ORIGIN")
    require(producer["api_job_id"] != reader["api_job_id"], "DISTINCT_RETAINED_WRITER_READER")
    require(type(o["source_code_sha256"]) is dict and set(o["source_code_sha256"]) == set(HISTORICAL_FILES)
        and all(store.HASH.fullmatch(str(v)) for v in o["source_code_sha256"].values())
        and type(r["model_code_sha256"]) is dict and set(r["model_code_sha256"]) == set(NUMERIC_FILES)
        and all(r["model_code_sha256"][name] == o["source_code_sha256"]["nfl_lab/"+name] for name in NUMERIC_FILES),
        "EXACT_RETAINED_SOURCE_CODE_PINS")
    catalog = o["replay_catalog"]
    effective.safe_replay_catalog(catalog)
    require(catalog["run_id"] == o["run_id"] and catalog["source_sha"] == o["source_sha"], "RETAINED_CATALOG_ORIGIN")
    require(store.HASH.fullmatch(str(o["restore_control_sha256"]))
        and store.HASH.fullmatch(str(o["verification_body_sha256"]))
        and type(o["verification_check_run_id"]) is int and o["verification_check_run_id"] > 0,
        "EXACT_RETAINED_VERIFICATION_REGISTRATION")
    require(type(o["verification_receipt"]) is dict and o["verification_receipt"]["replay_catalog"] == catalog,
        "REGISTERED_ORIGINAL_READER_VERIFICATION_PROOF")
    require(type(r["qualified_runtime"]) is dict and set(r["qualified_runtime"]) == {"binding_sha256","qualification_sha256"}
        and r["qualified_runtime"]["binding_sha256"] == store.sha(store.canonical(o["handoff"]["runtime_binding"]))
        and store.HASH.fullmatch(str(r["qualified_runtime"]["qualification_sha256"]))
        and type(r["pending_reservations"]) is list and len(r["pending_reservations"]) <= 128,
        "REGISTERED_QUALIFIED_RUNTIME_REQUIRED")
    return r


def validate_go(go, registration_sha256, env, root):
    require(type(go) is dict and set(go) == GO_KEYS and go["schema_version"] == VERSION+"-GO"
        and go["approved"] is True and go["repository"] == store.REPO and go["operation"] == OPERATION
        and go["registration_sha256"] == registration_sha256 and go["mode"] == MODE
        and go["single_writer_group"] == "nfl-lab-single-writer"
        and go["owner_authorization"] == "OWNER_REGISTERED_RETAINED_EFFECTIVE18_V1"
        and all(type(go[k]) is int and go[k] == 0 for k in ZERO_FIELDS) and go["public_release"] is False,
        "FRESH_RETAINED_OWNER_GO_REQUIRED")
    issued, expires = store.utc(go["issued_at_utc"]), store.utc(go["expires_at_utc"])
    require(issued <= now() < expires and 0 < (expires-issued).total_seconds() <= 3600, "RETAINED_GO_CLOCK")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == store.REPO
        and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_RUN_ATTEMPT") == "1"
        and env.get("STORE_PERMISSION") == "write" and env.get("GITHUB_ACTOR") == "NickNicky19"
        and env.get("GITHUB_ACTOR_ID") == "208912933" and go["source_sha"] == env.get("GITHUB_SHA")
        and re.fullmatch(r"[1-9][0-9]{0,19}",env.get("GITHUB_RUN_ID",""))
        and type(go["run_attempt"]) is int and go["run_attempt"] == 1
        and go["job_id"] == env.get("GITHUB_JOB") and go["workflow_ref"] == env.get("GITHUB_WORKFLOW_REF"),
        "ACTUAL_CURRENT_RETAINED_ACTIONS_REQUIRED")
    require(go["helper_sha256"] == current_pins(root), "CURRENT_RETAINED_HELPER_SOURCE_PINS")
    event = cp.strict_json(store.read_local(env["GITHUB_EVENT_PATH"], 256 << 10))
    require(event.get("repository",{}).get("full_name") == store.REPO and event.get("inputs",{}).get("mode") == MODE
        and event["inputs"].get("inference_builder_go_json") == store.canonical(go).decode()
        and event["inputs"].get("inference_builder_go_sha256") == env.get("AUDIT_COUNT_RETAINED_GO_SHA256"),
        "EXACT_CURRENT_RETAINED_DISPATCH_GO")
    from tools.private_draft_store_v2 import actions_context
    job = actions_context(env,"write")
    import subprocess
    changes = subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",
        ".github","nfl_lab","tools","config","schemas","pyproject.toml","requirements.lock",
        "requirements-hosted-fixed-build-v1.lock"],cwd=root,text=True)
    require(changes == "", "CLEAN_COMMITTED_RETAINED_SOURCE_REQUIRED")
    return job


def source_url(source_sha, name):
    return store.API+"/contents/"+quote(name,safe="/")+"?ref="+source_sha


class ReadClient(store.Client):
    """Only registered historical metadata/code/checks and normal private GETs."""
    def __init__(self,*args,extra_routes=(),**kwargs):
        super().__init__(*args,**kwargs)
        self.extra_routes = frozenset(extra_routes)

    def allow(self,url):
        if url in self.extra_routes:
            self.allowed.add(url)
            return url
        return super().allow(url)

    def request(self,url,*,method="GET",**kwargs):
        require(method == "GET" and kwargs.get("data") is None, "RETAINED_GET_ONLY_NO_REMOTE_WRITES")
        return super().request(url,method=method,**kwargs)


def routes(registration, qualification):
    o = registration["origin"]
    result = {store.API+"/check-runs/"+str(o["verification_check_run_id"])}
    for run_id in (o["run_id"], qualification["run_id"]):
        result |= {store.API+"/actions/runs/"+run_id, store.API+"/actions/runs/"+run_id+"/jobs?per_page=100&page=1"}
    return result | {source_url(o["source_sha"],name) for name in HISTORICAL_FILES}


def authenticate_origin(client, registration, qualification):
    r, o = registration, registration["origin"]
    producer, reader = o["handoff"]["producer"], o["reader"]
    require(client.run_id != o["run_id"] and client.job["execution_lane"] == "github_actions"
        and client.job["run_authenticated"] is True and client.job["api_job_id"] not in {producer["api_job_id"],reader["api_job_id"]}
        and client.process != producer["process_identity"], "FRESH_CROSS_RUN_READER_REQUIRED")
    current_run = client.json(client.allow(store.API+"/actions/runs/"+client.run_id))
    require(current_run.get("head_branch") == client.job["workflow_ref"].split("@refs/heads/",1)[1]
        and current_run.get("actor",{}).get("login") == "NickNicky19"
        and current_run.get("actor",{}).get("id") == 208912933,
        "ACTUAL_CURRENT_RETAINED_BRANCH_AND_OWNER")
    run_url = store.API+"/actions/runs/"+o["run_id"]
    run = client.json(client.allow(run_url))
    jobs = client.json(client.allow(run_url+"/jobs?per_page=100&page=1"))
    require(run.get("id") == int(o["run_id"]) and run.get("head_sha") == o["source_sha"]
        and run.get("event") == "workflow_dispatch" and run.get("run_attempt") == 1
        and run.get("status") == "completed" and run.get("conclusion") == o["run_conclusion"]
        and run.get("path") == ".github/workflows/lab.yml"
        and run.get("head_branch") == o["workflow_ref"].split("@refs/heads/",1)[1]
        and run.get("repository",{}).get("full_name") == store.REPO and run.get("head_repository",{}).get("full_name") == store.REPO,
        "ACTUAL_REGISTERED_ORIGINAL_RUN_REQUIRED")
    require(type(jobs.get("jobs")) is list and jobs.get("total_count") == len(jobs["jobs"]) <= 100,
        "COMPLETE_ORIGINAL_WRITER_READER_JOBS")
    found = []
    for identity_, label in ((producer,effective.WRITER_JOB),(reader,effective.READER_JOB)):
        matches = [j for j in jobs["jobs"] if j.get("id") == identity_["api_job_id"]]
        require(len(matches) == 1, "EXACT_ORIGINAL_JOB_ID")
        job = matches[0]
        require(job.get("name") == label and job.get("run_id") == int(o["run_id"])
            and job.get("head_sha") == o["source_sha"] and job.get("status") == "completed"
            and job.get("conclusion") == "success" and store.utc(job["started_at"]) <= store.utc(job["completed_at"])
            <= store.utc(r["registered_at_utc"]), "ACTUAL_SUCCESSFUL_ORIGINAL_JOB_REQUIRED")
        found.append(job)
    writer_job, reader_job = found
    require(store.utc(writer_job["completed_at"]) <= store.utc(reader_job["started_at"]) <= store.utc(reader_job["completed_at"])
        <= store.utc(client.started_at), "HISTORICAL_RESTORE_CAUSAL_CLOCKS")
    check_url = store.API+"/check-runs/"+str(o["verification_check_run_id"])
    check = client.json(client.allow(check_url))
    from tools import audit_count_verification_receipt_v1 as receipt
    public = cp.strict_json(check.get("output",{}).get("summary", ""))
    require(type(public) is dict and set(public) == receipt.PUBLIC_KEYS and public["schema_version"] == receipt.VERSION
        and public["repository"] == store.REPO and public["source_sha"] == o["source_sha"] and public["run_id"] == o["run_id"]
        and public["reader_api_job_id"] == reader["api_job_id"] and public["reader_job_id"] == effective.READER_JOB
        and public["root_go_sha256"] == o["handoff"]["root_go_sha256"]
        and public["restored_control_sha256"] == o["restore_control_sha256"]
        and public == o["verification_receipt"] and public["replay_catalog"] == o["replay_catalog"]
        and public["replay_catalog_sha256"] == store.sha(effective.safe_replay_catalog(o["replay_catalog"]))
        and public["model_pairs"] == 18 and public["fits"] == 0 and public["model_artifact_durability"] is True
        and public["successful_forecast"] is public["scientific_qualification"] is public["public_release"] is False,
        "ACTUAL_HISTORICAL_VERIFICATION_RECEIPT")
    summary = store.canonical(public).decode()
    payload = dict(name=receipt.NAME,head_sha=o["source_sha"],status="completed",conclusion="success",
                   external_id=o["run_id"]+":1",output=dict(title=receipt.TITLE,summary=summary))
    receipt.check_response(check,payload,o["verification_check_run_id"])
    require(store.sha(store.canonical(payload)) == o["verification_body_sha256"]
        and check.get("app",{}).get("slug") == "github-actions"
        and store.utc(reader_job["started_at"]) <= store.utc(check["completed_at"]) <= store.utc(reader_job["completed_at"]),
        "EXACT_REGISTERED_VERIFICATION_PAYLOAD")
    for name, digest in o["source_code_sha256"].items():
        url = client.allow(source_url(o["source_sha"],name))
        status, headers, body = client.request(url,cap=1 << 20)
        require(status == 200 and headers.get("x-ratelimit-remaining") != "0" and "retry-after" not in headers,
            "HISTORICAL_SOURCE_METADATA_HTTP")
        doc = cp.strict_json(body)
        require(doc.get("type") == "file" and doc.get("path") == name and doc.get("encoding") == "base64"
            and type(doc.get("size")) is int and 0 < doc["size"] <= SOURCE_CAP, "EXACT_HISTORICAL_SOURCE_FILE")
        raw = base64.b64decode(doc["content"].replace("\n",""),validate=True)
        require(len(raw) == doc["size"] and store.sha(raw) == digest, "AUTHENTIC_HISTORICAL_SOURCE_SHA256")
    store.check_proof(client,qualification,"qualified",same_run=False)
    owner.authenticate_past_run(client,qualification)
    owner.verify_canary(client)
    client.inventory();client.draft()
    return writer_job, reader_job


def restore(registration, factory, *, storage, output, current_go_sha256, before_replay=None, check_authority=None):
    """New cross-run composition. Original same-run reader is never invoked."""
    validate_registration(registration)
    require(store.HASH.fullmatch(str(current_go_sha256)),"EXACT_CURRENT_RETAINED_GO_HASH")
    require(model_pins(Path(__file__).resolve().parents[1]) == registration["model_code_sha256"],
        "REQUALIFICATION_REQUIRED_MODEL_CODE_CHANGED")
    o, handoff = registration["origin"], registration["origin"]["handoff"]
    output = store.parents_safe(output)
    require(not output.exists(), "FRESH_RETAINED_RESTORE_NO_RETRY")
    storage.register_root(output)
    first = factory("restore")
    first.authenticate_actions_job()
    require(first.binding == handoff["runtime_binding"]
        and store.sha(store.canonical(factory.qualification)) == registration["qualified_runtime"]["qualification_sha256"],
        "EXACT_RETAINED_QUALIFICATION_BINDING")
    current = cp.client_identity(first)
    writer_job, reader_job = authenticate_origin(first,registration,factory.qualification)
    if check_authority is not None:
        check_authority()
    storage.write_bytes(output/"NATIVE_CURRENT_RESTORE_GO.json",store.canonical(dict(schema_version=VERSION+"-native-GO",
        current=current,owner_go_sha256=current_go_sha256,registration_sha256=store.sha(store.canonical(registration)),
        operation=OPERATION,computed_after_actual_current_and_historical_authentication=True,remote_writes=0,fits=0)))
    storage.write_bytes(output/"CONSUMED.json",store.canonical(dict(schema_version=VERSION,
        current=current, registration_sha256=store.sha(store.canonical(registration)), current_go_sha256=current_go_sha256,
        original_run_id=o["run_id"], fits=0,remote_writes=0)))
    proofs, used = [], False
    def get(descriptor,name):
        nonlocal used
        client = first if not used else factory("restore")
        used = True
        require(cp.client_identity(client) == current and client.binding == first.binding, "ONE_AUTHENTIC_CURRENT_RETAINED_READER")
        if check_authority is not None:
            check_authority()
        destination = output/"downloads"/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        with storage.transaction():
            storage._require(2*descriptor["entry"]["payload"]["bytes"])
            proof = store.restore(client,descriptor,destination)
            storage.import_file(destination,output/"owned-downloads"/name,expected_sha256=descriptor["entry"]["payload"]["sha256"])
        require(proof["schema_version"] == "weekly-private-proof-v2.1"
            and proof["run_id"] == current["run_id"] and proof["source_sha"] == current["source_sha"]
            and proof["exact_readback"] is proof["separate_process"] is True,
            "EXACT_CURRENT_STORE21_RESTORE_PROOF")
        if check_authority is not None:
            check_authority()
        proofs.append(proof)
        return store.read_local(output/"owned-downloads"/name,store.ASSET_CAP)
    encoded = get(handoff["index_descriptor"],"index.gz")
    with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as compressed:
        plain = compressed.read(effective.INDEX_CAP+1)
    require(len(plain) <= effective.INDEX_CAP,"RETAINED_INDEX_INFLATION_CAP")
    document = effective.check_index(cp.strict_json(plain),handoff)
    require(store.utc(writer_job["started_at"]) <= store.utc(document["created_at"]) <= store.utc(writer_job["completed_at"]),
        "ORIGINAL_INDEX_WRITER_CLOCK")
    require(all(q in registration["pending_reservations"] for q in document["pending_reservations"]),
        "ALL_ORIGINAL_PENDING_RESERVATIONS_RETAINED")
    with storage.transaction():
        storage._require(sum(f["bytes"] for f in document["files"]) + sum(g["bytes"]*2 for g in document["groups"]) + (2 << 20))
    for group in document["groups"]:
        codec.extract_owned(get(group["descriptor"],f"group-{group['index']}.gz"),group,storage,output/"files")
    mapping = {f["logical_path"]:dict(path=str(output/"files"/f["logical_path"]),bytes=f["bytes"],sha256=f["sha256"])
               for f in document["files"]}
    validate_owned_references(storage,{r["path"]:r["sha256"] for r in mapping.values()})
    result = cp.strict_json(cp.read_ref(mapping["control/REQUALIFICATION_FINISHED.json"]))
    route = cp.strict_json(cp.read_ref(mapping["control/RESTORE_RECEIPT.json"]))
    require(result["schema_version"] == audit.VERSION+"-result" and result["state"] == "ZERO_FIT_REQUALIFIED_PRIVATE_PENDING_INTEGRATION"
        and result["current_run_id"] == route["current_run_id"] == o["run_id"]
        and result["current_source_sha"] == route["current_source_sha"] == o["source_sha"]
        and result["model_pairs"] == len(result["artifacts"]) == 18 and result["fits"] == route["fits"] == route["model_decodes"] == 0
        and route["schema_version"] == audit.VERSION+"-restore" and route["state"] == "QUALIFIED_ROUTE_RESTORED_OPAQUE",
        "ORIGINAL_RETAINED_SUCCESS_CONTROLS")
    refs, alias_rows, metadata = [], [], []
    for pair, artifact, slot in zip(effective.pairs(),result["artifacts"],o["replay_catalog"]["slots"]):
        original, model = mapping[pair["manifest_logical"]],mapping[pair["model_logical"]]
        m = cp.strict_json(cp.read_ref(original,256 << 10))
        require((artifact["target"],artifact["family"],artifact["method_id"])
            == (m["category"]["target"],m["family"],m["method_id"]) == (slot["target"],slot["family"],slot["method_id"])
            == (pair["target"],pair["family"],pair["method_id"])
            and artifact["manifest"]["bytes"] == original["bytes"]
            and artifact["manifest"]["sha256"] == original["sha256"] == slot["transport_manifest_sha256"]
            and artifact["current_loader_replay_passed"] is True and artifact["fits"] == 0
            and model["sha256"] == slot["model_sha256"] and m["procedure_version"] == slot["procedure_version"]
            and m["code_pins"] == registration["model_code_sha256"] and not m["dependencies"]
            and m["source_contract"]["source_policy_sha256"] == cp.POLICY_SHA
            and m["requalification"]["fits"] == 0
            and m["requalification"]["restore_receipt"]["sha256"] == document["restore_receipt_sha256"],
            "EXACT_RETAINED_MODEL_CATALOG_AND_PROVENANCE")
        relocated = codec.relocate_future_manifest(original,model,output/"relocated-models"/pair["target"]/pair["family"],storage)
        ref = {k:relocated[k] for k in ("path","bytes","sha256")}
        refs.append(ref);metadata.append((pair,m,model))
        alias_rows.append(dict(target=pair["target"],family=pair["family"],method_id=pair["method_id"],
            original_transport_manifest_sha256=original["sha256"], original_verified_reader_manifest_sha256=slot["manifest_sha256"],
            current_manifest=ref, model_sha256=model["sha256"], procedure_version=m["procedure_version"],
            original_fit_receipt=m["fit_receipt"], original_training_cutoff_utc=m["training_cutoff_utc"]))
    if before_replay is not None:
        before_replay()
    if check_authority is not None:
        check_authority()
    from . import weekly_future_inference as future
    require(future.code_pins() == registration["model_code_sha256"], "PRESERVED_SIX_MODEL_CODE_PINS_REQUIRED")
    import threadpoolctl
    from tools.ngboost_law_software_v1 import process_free_threads
    libc_path = Path("/usr/lib/x86_64-linux-gnu/libc.so.6").resolve(strict=True)
    libc = dict(path=str(libc_path),bytes=libc_path.stat().st_size,sha256=store.sha(store.read_local(libc_path,8 << 20)))
    with process_free_threads(threadpoolctl,libc),threadpoolctl.threadpool_limits(limits=2):
        with future.FutureInferenceSession.from_storage(storage) as session:
            session.prepare(refs)  # Unchanged loader replays each original feature-only fixture.
            for pair,m,model in metadata:
                if pair["family"] == "count_A":
                    import joblib
                    bundle = joblib.load(io.BytesIO(cp.read_ref(model)))
                    trained, fixture = bundle["model"],bundle["fixture"]
                    require(audit.count_replay_oracle(trained,fixture)["warm_rows"] > 0,"NONVACUOUS_RETAINED_WARM_REPLAY")
                    for role in list(dict.fromkeys(list(trained.priors)+list(m["category"]["modeled_roles"])+["audit_unknown_role"])):
                        probe = fixture.iloc[:1].copy();probe["position"],probe["f_player_games_prior"] = role,0.
                        require(audit.count_replay_oracle(trained,probe)["independent_stored_q_mean_verified"] is True,
                            "RETAINED_STORED_Q_FALLBACK_ORACLE")
    require(sum(c.calls for c in factory.clients) <= 360,"RETAINED_TOTAL_HTTP_CAP")
    catalog = dict(schema_version=VERSION+"-manifest-aliases", origin_registration_sha256=store.sha(store.canonical(registration)),
        original_source_sha=o["source_sha"],original_run_id=o["run_id"],current=current,models=alias_rows,
        catalog_epoch_ready=False,weekly_choice_restored=False,forecast_issuance_authorized=False)
    storage.write_bytes(output/"RELOCATION_CATALOG.json",store.canonical(catalog))
    restored = dict(schema_version=VERSION+"-restore",state="CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE",
        origin=registration["origin"],current=current,current_go_sha256=current_go_sha256,
        registration_sha256=store.sha(store.canonical(registration)), models=refs, model_pairs=18, files=38,
        proofs=proofs,index_sha256=handoff["index_descriptor"]["entry"]["payload"]["sha256"],
        group_sha256=[g["sha256"] for g in document["groups"]],relocation_catalog=cp.binding(output/"RELOCATION_CATALOG.json"),
        fits=0,source_feed_acquisitions=0,remote_writes=0,protected_outcome_reads=0,
        current_loader_replay=True,model_artifact_durability=True,successful_forecast=False,
        scientifically_qualified=False,public_release=False,catalog_epoch_ready=False,weekly_choice_restored=False,
        actual_completed_at=now().isoformat())
    storage.write_bytes(output/"RESTORED.json",store.canonical(restored))
    return restored
