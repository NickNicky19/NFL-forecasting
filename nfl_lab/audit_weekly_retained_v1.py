"""GET-only cross-run recovery of an explicitly registered weekly archive.

The parent approves the prior reader handoff, exporter API ID, historical code
pins and qualified runtime in a NEW request/root. Historical proof JSON grants
no authority. Current clients/proofs keep their actual current identities. All
old bytes and original paths stay immutable; relocation is a separate map.
No source acquisition, model loader, fit, outcome parser or publisher is used.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import re
import resource
import subprocess
from urllib.parse import quote

from . import audit_weekly_archive_v1 as archive, private_draft_store as store
from . import gha_private_checkpoint as cp, owner_bootstrap_bundle as codec
from . import weekly_durable_acceptance as acceptance, audit_reference_capture_v1 as reference
from .owned_reference_batch import validate_owned_references

VERSION="audit-weekly-retained-v1"
MODE="audit-weekly-producer-v1"
PHASE="retained"
MAX_CLIENTS=11  # One metadata verifier, then index + eight groups + old witness.
LIMITS=dict(wall_seconds=180,CPU_seconds=120,address_space_bytes=512 << 20,RSS_bytes=512 << 20,
    global_bytes=512 << 20,runtime_bytes=32 << 20,asset_bytes=8 << 20,runtime_assets=128,
    groups=8,files=512,native_clients=MAX_CLIENTS,HTTP_per_client=40,HTTP_calls=440,
    fits=0,model_decodes=0,source_acquisitions=0,protected_outcome_reads=0,remote_writes=0,retries=0,publication=0)
HISTORICAL_FILES=(".github/workflows/lab.yml","nfl_lab/audit_weekly_archive_v1.py","tools/audit_weekly_archive_v1.py",
    "nfl_lab/private_draft_store.py","nfl_lab/owner_bootstrap_bundle.py","nfl_lab/gha_private_checkpoint.py",
    "nfl_lab/audit_reference_capture_v1.py","config/private-draft-storage-v2.json")
PIN_PATHS=tuple(sorted(set(archive.PIN_PATHS)|{"nfl_lab/audit_weekly_retained_v1.py","tools/audit_weekly_retained_v1.py",
    "tests/test_audit_weekly_retained_v1.py","tests/test_audit_weekly_retained_recurring_v1.py",
    "nfl_lab/audit_weekly_controller_v1.py","nfl_lab/audit_weekly_controller_bootstrap_v1.py",
    "nfl_lab/weekly_durable_acceptance.py"}))
REQUEST_KEYS={"schema_version","approved","repository","phase","helper_sha256","limits","registered_at_utc",
    "reader_handoff","exporter_api_job_id","historical_source_sha256","qualified_runtime","pending_census",
    "pending_reservations","cache","state_root","output"}
AUTHORITY_KEYS={"schema_version","phase","request_sha256","repository","owner_root_go_sha256","owner_root_checked",
    "actual_actions_api_authenticated","api_job_id","source_sha","run_id","run_attempt","job_id","workflow_ref",
    "issued_at_utc","expires_at_utc","fits","remote_writes","protected_outcome_reads","public_release"}
WITNESS_KEYS={"schema_version","restorer","index_sha256","files_sha256","producer_proof_sha256","proofs","validation",
    "actual_completed_at","archive_state","public_export_authorized","successful_forecast"}
_GRANT_KEY=object()
_JOB_EVIDENCE_KEYS={"repository","run_id","source_sha","workflow_ref","api_job_id","job_id","status","conclusion",
    "started_at","completed_at","verified_permissions"}


def require(value,code):
    if not value:raise store.StoreError(code)


def now():return datetime.now(timezone.utc)


def pins(root):return {name:store.sha(store.read_local(Path(root)/name,2 << 20)) for name in PIN_PATHS}


def _grant_utc(value):return store.utc(value.isoformat() if isinstance(value,datetime) else value)


def _historical_jobs(p,jobs):
    """Exact original metadata, independently checked again against live APIs."""
    h=p["reader_handoff"]["archive"]
    ids=dict(produce=h["producer"]["api_job_id"],restore=p["reader_handoff"]["restorer"]["api_job_id"],consume=p["exporter_api_job_id"])
    require(type(jobs) is dict and set(jobs)==set(ids),"COMPLETE_GRANTED_HISTORICAL_THREE_JOBS")
    for role,row in jobs.items():
        require(type(row) is dict and set(row)==_JOB_EVIDENCE_KEYS
            and row["repository"]==store.REPO and row["run_id"]==h["run_id"] and row["source_sha"]==h["source_sha"]
            and row["workflow_ref"]==h["producer"]["workflow_ref"] and row["job_id"]==h["jobs"][role]
            and type(row["api_job_id"]) is int and row["api_job_id"]==ids[role]
            and row["status"]=="completed" and row["conclusion"]=="success"
            and row["verified_permissions"]==dict(contents="write",actions="read")
            and store.utc(row["started_at"])<=store.utc(row["completed_at"])<=store.utc(p["registered_at_utc"]),
            "EXACT_GRANTED_HISTORICAL_JOB_SOURCE_AND_CLOCKS")
    require(store.utc(jobs["produce"]["completed_at"])<=store.utc(jobs["restore"]["started_at"])
        and store.utc(jobs["restore"]["completed_at"])<=store.utc(jobs["consume"]["started_at"]),
        "ORDERED_GRANTED_HISTORICAL_THREE_JOBS")
    return jobs


def _bootstrap_scope(proof,authority,at):
    # Lazy import: the legacy Nick reader retains its original authority path.
    from . import audit_weekly_controller_bootstrap_v1 as bootstrap, audit_weekly_controller_v1 as controller
    require(type(proof) in {bootstrap.Owner,controller.Proof},"LIVE_CURRENT_BOOTSTRAP_PROOF_REQUIRED")
    require(type(authority) is dict and set(authority)==AUTHORITY_KEYS
        and authority["schema_version"]==VERSION+"-native-authority" and authority["repository"]==store.REPO
        and authority["phase"]==PHASE and store.utc(authority["issued_at_utc"])<=_grant_utc(at)<store.utc(authority["expires_at_utc"])
        and 0<(store.utc(authority["expires_at_utc"])-store.utc(authority["issued_at_utc"])).total_seconds()<=3600,
        "CURRENT_GRANT_AUTHORITY_SCOPE_AND_CLOCKS")
    if type(proof) is bootstrap.Owner:
        proof.verify(root_sha256=authority["owner_root_go_sha256"])
        expected_actor=controller.OWNER
    else:
        proof.verify(registration_sha256=proof.document["registration_sha256"],run_id=authority["run_id"],
            job_id=authority["job_id"],root_sha256=authority["owner_root_go_sha256"])
        require(proof.document.get("schema_version")==controller.VERSION+"-current-child-proof","CURRENT_CHILD_GRANT_PROOF_REQUIRED")
        expected_actor=controller.BOT
    seal=getattr(proof,"bootstrap_seal",None)
    require(type(seal) is bootstrap.Seal,"LIVE_CURRENT_OWNER_SEAL_REQUIRED");seal.verify()
    registration=controller.registration(seal.registration_bytes,sealed_sha256=seal.registration_sha256,at=at)
    spec=registration["producer"];d=proof.document
    require(d.get("registration_sha256")==seal.registration_sha256 and d.get("actor")==expected_actor
        and all(d.get(k)==authority[k] for k in ("source_sha","run_id","job_id","api_job_id"))
        and authority["source_sha"]==spec["source_sha"] and authority["job_id"] in spec["jobs"].values()
        and authority["workflow_ref"]==store.REPO+"/.github/workflows/lab.yml@refs/heads/"+spec["branch"]
        and store.utc(seal.document["owner_registration_completed_at"])<=store.utc(authority["issued_at_utc"]),
        "EXACT_CURRENT_SEALED_OPERATIONAL_SOURCE_AND_JOB")
    return dict(approved_source_sha=spec["source_sha"],public_policy_sha256=seal.document["static_public_policy_sha256"],
        bootstrap_registration_sha256=seal.registration_sha256,bootstrap_seal_sha256=controller.digest(seal.document),
        operational_jobs={k:spec["jobs"][k] for k in ("produce","restore","consume")},
        operational_workflow_sha256=spec["workflow_sha256"],
        operational_workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/"+spec["branch"],current_actor=dict(expected_actor))


class HistoricalSourceGrant:
    """Live, process-bound extension; JSON and historical proof flags cannot mint it."""
    def __init__(self,document,proof,authenticate,key,*,v5_discovery=None):
        require(key is _GRANT_KEY,"LIVE_HISTORICAL_SOURCE_GRANT_REQUIRED")
        self.document=deepcopy(document);self.sha256=store.sha(store.canonical(document))
        self._proof,self._authenticate,self._process=proof,authenticate,store.process_identity()
        self._v5_discovery=v5_discovery
    def verify(self,p,authority,at):
        require(self.sha256==store.sha(store.canonical(self.document)) and self._process==store.process_identity(),
            "HISTORICAL_SOURCE_GRANT_CHANGED_OR_DIFFERENT_PROCESS")
        scope=_bootstrap_scope(self._proof,authority,at)
        require(self.document["scope"]==scope and self.document["request_sha256"]==store.sha(store.canonical(p))
            and self.document["authority_sha256"]==store.sha(store.canonical(authority))
            and store.utc(self.document["created_at_utc"])<=_grant_utc(at),"EXACT_HISTORICAL_SOURCE_GRANT_BINDING")
        if self._v5_discovery is not None:
            require(self.document["v5_historical_scope"]==_v5_historical_scope(p,authority,self._proof,self._v5_discovery,at),
                "V5_HISTORICAL_SCOPE_CHANGED_OR_UNBOUND")
        return self
    def __reduce__(self):raise store.StoreError("HISTORICAL_SOURCE_GRANT_CANNOT_BE_SERIALIZED")


def _grant_authenticate(callback,kind,document,at):
    require(callable(callback),"LIVE_HISTORICAL_SOURCE_AUTHENTICATOR_REQUIRED")
    request=dict(schema_version=VERSION+"-historical-source-authentication",kind=kind,
        inputs=deepcopy(document),inputs_sha256=store.sha(store.canonical(document)),at_utc=_grant_utc(at).isoformat())
    require(len(store.canonical(request))<=64 << 10 and callback(request) is True,"LIVE_HISTORICAL_SOURCE_AUTHENTICATION_REJECTED")


def bind_historical_source(p,authority,*,bootstrap_proof,public_policy_sha256,historical_jobs,authenticate,root,clock=now):
    """Metadata-only binding BEFORE private bodies; performs no HTTP itself.

    The live parent authenticates the exact public-policy SHA and complete old
    three-job evidence. restore() independently rereads source/jobs and calls
    that authenticator again before its first private GET. BOT history is
    restricted to the currently owner-sealed operational source, never added
    as an unconditional historical actor. Request/result schemas stay intact.
    """
    validate_request(p,root);at=_grant_utc(clock());scope=_bootstrap_scope(bootstrap_proof,authority,at)
    require(type(public_policy_sha256) is str and store.HASH.fullmatch(public_policy_sha256)
        and public_policy_sha256==scope["public_policy_sha256"]
        and authority["request_sha256"]==store.sha(store.canonical(p))
        and store.utc(p["registered_at_utc"])<=store.utc(authority["issued_at_utc"]),"EXACT_GRANTED_POLICY_AND_REGISTERED_REQUEST")
    document=dict(schema_version=VERSION+"-historical-source-grant",scope=scope,
        request_sha256=authority["request_sha256"],authority_sha256=store.sha(store.canonical(authority)),
        historical_jobs=deepcopy(_historical_jobs(p,historical_jobs)),created_at_utc=at.isoformat())
    _grant_authenticate(authenticate,"BIND_SEALED_HISTORICAL_SOURCE",document,at)
    return HistoricalSourceGrant(document,bootstrap_proof,authenticate,_GRANT_KEY)


def _v5_historical_scope(p,authority,proof,grant,at):
    from . import audit_weekly_discovery_v1 as discovery,audit_weekly_controller_bootstrap_v1 as bootstrap
    require(type(proof) is bootstrap.Owner and type(grant) is discovery.DiscoverySourceGrant
        and grant._proof is proof,"V5_SAME_CURRENT_OWNER_AND_DISCOVERY_GRANT_REQUIRED")
    grant.verify(grant.document["binding"])
    current=_bootstrap_scope(proof,authority,at);d=grant.document;v=grant._value
    require(d["historical_contract"]["kind"]==discovery.V5_OWNER_HISTORY
        and d["scope"]["operational_source_sha"]==current["approved_source_sha"]
        and d["scope"]["operational_policy_sha256"]==current["public_policy_sha256"]
        and d["scope"]["current_actor"]==current["current_actor"]
        and d["binding"]["current_root_go_sha256"]==authority["owner_root_go_sha256"],
        "V5_RETAINED_CURRENT_SEAL_SOURCE_POLICY_SCOPE")
    h=p["reader_handoff"]["archive"]
    require(all(h[k]==v[k] for k in ("source_sha","run_id","root_go_sha256"))
        and h["jobs"]=={role:j["job_id"] for role,j in v["jobs"].items()}
        and h["producer"]["api_job_id"]==v["jobs"]["produce"]["api_job_id"]
        and p["reader_handoff"]["restorer"]["api_job_id"]==v["jobs"]["restore"]["api_job_id"]
        and p["exporter_api_job_id"]==v["jobs"]["consume"]["api_job_id"]
        and h["index_descriptor"]["entry"]["payload"]["sha256"]==v["archive_index_sha256"]
        and h["files_sha256"]==v["archive_files_sha256"]
        and p["reader_handoff"]["witness_descriptor"]["entry"]["payload"]["sha256"]==v["reader_witness_sha256"]
        and h["producer"]["workflow_ref"]==store.REPO+"/.github/workflows/lab.yml@refs/heads/"+d["historical_contract"]["branch"]
        and p["historical_source_sha256"]==d["binding"]["historical_source_sha256"]
        and store.sha(store.canonical(p["qualified_runtime"]))==d["binding"]["qualified_runtime_sha256"],
        "V5_RETAINED_EXACT_ORIGINAL_ARCHIVE_SOURCE_PACKAGE")
    return dict(approved_source_sha=v["source_sha"],run_id=v["run_id"],root_go_sha256=v["root_go_sha256"],
        public_policy_sha256=v["policy_sha256"],operational_jobs={role:j["job_id"] for role,j in v["jobs"].items()},
        operational_workflow_sha256=v["workflow_sha256"],operational_workflow_ref=h["producer"]["workflow_ref"],
        authority_sha256=d["historical_contract"]["historical_authority_sha256"])


def bind_v5_source_history(p,authority,*,bootstrap_proof,discovery_grant,historical_jobs,authenticate,root,clock=now):
    """Current Owner/source/policy stay separate from exact old BOT/policy."""
    validate_request(p,root);at=_grant_utc(clock());scope=_bootstrap_scope(bootstrap_proof,authority,at)
    historical=_v5_historical_scope(p,authority,bootstrap_proof,discovery_grant,at)
    require(authority["request_sha256"]==store.sha(store.canonical(p))
        and store.utc(p["registered_at_utc"])<=store.utc(authority["issued_at_utc"]),
        "EXACT_V5_REGISTERED_RETAINED_REQUEST")
    document=dict(schema_version=VERSION+"-historical-source-grant-v5",scope=scope,v5_historical_scope=historical,
        request_sha256=authority["request_sha256"],authority_sha256=store.sha(store.canonical(authority)),
        historical_jobs=deepcopy(_historical_jobs(p,historical_jobs)),created_at_utc=at.isoformat())
    _grant_authenticate(authenticate,"BIND_SEALED_HISTORICAL_SOURCE",document,at)
    return HistoricalSourceGrant(document,bootstrap_proof,authenticate,_GRANT_KEY,v5_discovery=discovery_grant)


def prepare_request(root,reader_handoff,qualified_runtime,*,exporter_api_job_id,historical_source_sha256,
        cache,state_root,output,pending_census,pending_reservations=(),registered_at_utc=None):
    """Offline metadata preparation; NEW parent approval is still required.

    qualified_runtime is the exact qualified package document for the archive's
    own runtime, not an unrelated newer runtime. No private/network read occurs.
    """
    return dict(schema_version=VERSION+"-request",approved=False,repository=store.REPO,phase=PHASE,helper_sha256=pins(root),
        limits=dict(LIMITS),registered_at_utc=registered_at_utc or now().isoformat(),reader_handoff=deepcopy(reader_handoff),
        exporter_api_job_id=exporter_api_job_id,historical_source_sha256=deepcopy(historical_source_sha256),
        qualified_runtime=deepcopy(qualified_runtime),pending_census=deepcopy(pending_census),pending_reservations=list(pending_reservations),
        cache=str(cache),state_root=str(state_root),output=str(output))


def validate_request(p,root):
    require(type(p) is dict and set(p)==REQUEST_KEYS and p["schema_version"]==VERSION+"-request" and p["approved"] is True
        and p["repository"]==store.REPO and p["phase"]==PHASE and p["limits"]==LIMITS and p["helper_sha256"]==pins(root),
        "APPROVED_EXACT_RETAINED_WEEKLY_REQUEST")
    r=p["reader_handoff"]
    require(type(r) is dict and set(r)=={"schema_version","archive","restorer","witness_descriptor"}
        and r["schema_version"]==archive.VERSION+"-reader-handoff","REGISTERED_PRIOR_READER_HANDOFF_REQUIRED")
    h=r["archive"];archive.safe_handoff(h)
    require(h["archive_state"]=="COMPLETE_CAPTURE","ONLY_COMPLETE_PRIOR_WEEKLY_CAPTURE")
    producer=acceptance.identity(h["producer"]);reader=acceptance.identity(r["restorer"])
    require(reader["run_id"]==producer["run_id"]==h["run_id"] and reader["source_sha"]==producer["source_sha"]==h["source_sha"]
        and reader["workflow_ref"]==producer["workflow_ref"] and reader["job_id"]==h["jobs"]["restore"]
        and reader["api_job_id"]!=producer["api_job_id"] and reader["process_identity"]!=producer["process_identity"]
        and type(p["exporter_api_job_id"]) is int and p["exporter_api_job_id"]>0
        and p["exporter_api_job_id"] not in {reader["api_job_id"],producer["api_job_id"]},"EXACT_REGISTERED_THREE_PRIOR_JOB_IDENTITIES")
    e=cp.descriptor_meta(r["witness_descriptor"],archive.WITNESS_CAP)
    require(e["writer_run_id"]==h["run_id"] and e["producer_process"]==reader["process_identity"]
        and e["binding_sha256"]==store.sha(store.canonical(h["runtime_binding"])),"REGISTERED_ORIGINAL_READER_WITNESS_BINDING")
    require(type(p["historical_source_sha256"]) is dict and set(p["historical_source_sha256"])==set(HISTORICAL_FILES)
        and all(type(v) is str and store.HASH.fullmatch(v) for v in p["historical_source_sha256"].values())
        and p["historical_source_sha256"]["config/private-draft-storage-v2.json"]==store.config_sha(),"EXACT_REGISTERED_HISTORICAL_CODE_PINS")
    require(p["qualified_runtime"]["binding"]==h["runtime_binding"],"QUALIFIED_PACKAGE_MUST_COVER_ORIGINAL_ARCHIVE_RUNTIME")
    require(type(p["pending_reservations"]) is list and len(p["pending_reservations"])<=store.MAX_ASSETS,"BOUNDED_RETAINED_PENDING_RESERVATIONS")
    store.utc(p["registered_at_utc"])
    return h


def checked_authority(body,expected_sha256,request_sha256,env,root):
    require(0<len(body)<=16384 and store.sha(body)==expected_sha256,"EXACT_RETAINED_WEEKLY_AUTHORITY_HASH")
    a=cp.strict_json(body)
    require(store.canonical(a)==body and type(a) is dict and set(a)==AUTHORITY_KEYS and a["schema_version"]==VERSION+"-native-authority"
        and a["phase"]==PHASE and a["request_sha256"]==request_sha256 and a["repository"]==store.REPO
        and a["owner_root_checked"] is a["actual_actions_api_authenticated"] is True
        and type(a["api_job_id"]) is int and a["api_job_id"]>0 and type(a["run_attempt"]) is int and a["run_attempt"]==1
        and a["source_sha"]==env.get("GITHUB_SHA")==env.get("GITHUB_WORKFLOW_SHA") and a["run_id"]==env.get("GITHUB_RUN_ID")
        and a["job_id"]==env.get("GITHUB_JOB") and a["workflow_ref"]==env.get("GITHUB_WORKFLOW_REF")
        and all(type(a[k]) is int and a[k]==0 for k in ("fits","remote_writes","protected_outcome_reads")) and a["public_release"] is False,
        "CLOSED_CURRENT_RETAINED_WEEKLY_AUTHORITY")
    require(store.utc(a["issued_at_utc"])<=now()<store.utc(a["expires_at_utc"])
        and 0<(store.utc(a["expires_at_utc"])-store.utc(a["issued_at_utc"])).total_seconds()<=3600,"FRESH_RETAINED_WEEKLY_ROOT_CLOCK")
    require(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
        and env.get("GITHUB_REPOSITORY")==store.REPO and env.get("GITHUB_RUN_ATTEMPT")=="1"
        and env.get("GITHUB_ACTOR")=="NickNicky19" and env.get("GITHUB_ACTOR_ID")=="208912933" and env.get("STORE_PERMISSION")=="write",
        "GENUINE_CURRENT_OWNER_RETAINED_JOB_REQUIRED")
    event=cp.strict_json(store.read_local(env["GITHUB_EVENT_PATH"],256 << 10));inputs=event.get("inputs",{})
    text=inputs.get("inference_builder_go_json","").encode()
    require(inputs.get("mode")==MODE and event.get("repository",{}).get("full_name")==store.REPO and text
        and store.sha(text)==inputs.get("inference_builder_go_sha256")==a["owner_root_go_sha256"],"ACTUAL_NEW_WEEKLY_RETAINED_ROOT_EVENT")
    require(subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()==a["source_sha"]
        and subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",*PIN_PATHS],cwd=root,text=True)=="",
        "CLEAN_COMMITTED_CURRENT_RETAINED_HELPERS")
    return a


def source_url(source,name):return store.API+"/contents/"+quote(name,safe="/")+"?ref="+source


def routes(p):
    h=p["reader_handoff"]["archive"];q=p["qualified_runtime"]["qualification"]
    result={source_url(h["source_sha"],name) for name in HISTORICAL_FILES}
    for run in (h["run_id"],q["run_id"]):result|={store.API+"/actions/runs/"+run,store.API+"/actions/runs/"+run+"/jobs?per_page=100&page=1"}
    return result


class ReadClient(store.Client):
    def __init__(self,*args,extra_routes=(),**kwargs):
        super().__init__(*args,**kwargs);self.extra_routes=frozenset(extra_routes)
    def allow(self,url):
        if url in self.extra_routes:self.allowed.add(url);return url
        return super().allow(url)
    def request(self,url,*,method="GET",**kwargs):
        require(method=="GET" and kwargs.get("data") is None,"RETAINED_WEEKLY_GET_ONLY")
        return super().request(url,method=method,**kwargs)
    def reserve(self,*args,**kwargs):raise store.StoreError("RETAINED_WEEKLY_NO_POST_RESERVATIONS")
    def reserve_post(self,*args,**kwargs):raise store.StoreError("RETAINED_WEEKLY_NO_POST_RESERVATIONS")


def workflow_permissions(raw,h):
    import yaml
    # Duplicate YAML keys cannot silently replace reviewed permissions/jobs.
    class Closed(yaml.SafeLoader):pass
    def mapping(loader,node):
        result={}
        for key,value in node.value:
            k=loader.construct_object(key,deep=True)
            require(k not in result,"DUPLICATE_HISTORICAL_WORKFLOW_KEY")
            result[k]=loader.construct_object(value,deep=True)
        return result
    Closed.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
    value=yaml.load(raw,Loader=Closed)
    require(type(value) is dict and value.get("concurrency")==dict(group="nfl-lab-single-writer",**{"cancel-in-progress":False}),
        "ORIGINAL_WEEKLY_SINGLE_WRITER_WORKFLOW_REQUIRED")
    permissions={}
    for role,name in h["jobs"].items():
        job=value.get("jobs",{}).get(name)
        require(type(job) is dict and "uses" not in job and job.get("runs-on") is not None
            and job.get("permissions",value.get("permissions"))=={"contents":"write","actions":"read"},"EXACT_PRIOR_ARCHIVE_AUTH_PERMISSIONS")
        permissions[role]=dict(contents="write",actions="read")
    return permissions


def authenticate_origin(client,p,authority,*,historical_grant=None):
    h=p["reader_handoff"]["archive"]
    if historical_grant is not None:
        require(type(historical_grant) is HistoricalSourceGrant,"LIVE_HISTORICAL_SOURCE_GRANT_REQUIRED")
        historical_grant.verify(p,authority,now())
    require(client.run_id==authority["run_id"]!=h["run_id"] and client.source_sha==authority["source_sha"]
        and client.job["api_job_id"]==authority["api_job_id"] and client.job["job_id"]==authority["job_id"]
        and client.job["workflow_ref"]==authority["workflow_ref"] and client.job["api_job_id"] not in
        {h["producer"]["api_job_id"],p["reader_handoff"]["restorer"]["api_job_id"],p["exporter_api_job_id"]},"NEW_ACTUAL_READER_NOT_HISTORICAL_IDENTITY")
    current=client.json(client.allow(store.API+"/actions/runs/"+client.run_id))
    current_actor=dict(login="NickNicky19",id=208912933) if historical_grant is None else historical_grant.document["scope"]["current_actor"]
    require(current.get("head_branch")==authority["workflow_ref"].split("@refs/heads/",1)[1]
        and current.get("actor",{}).get("login")==current_actor["login"]
        and type(current.get("actor",{}).get("id")) is int and current["actor"]["id"]==current_actor["id"],"ACTUAL_NEW_RETAINED_BRANCH_OWNER")
    url=store.API+"/actions/runs/"+h["run_id"];run=client.json(client.allow(url));listing=client.json(client.allow(url+"/jobs?per_page=100&page=1"))
    actor=run.get("actor",{});original_owner=actor.get("login")=="NickNicky19" and type(actor.get("id")) is int and actor["id"]==208912933
    v5=historical_grant is not None and historical_grant._v5_discovery is not None
    historical_scope=(historical_grant.document["v5_historical_scope"] if v5 else historical_grant.document["scope"]) if historical_grant is not None else None
    granted_bot=historical_grant is not None and h["source_sha"]==historical_scope["approved_source_sha"] \
        and h["jobs"]==historical_scope["operational_jobs"] \
        and h["producer"]["workflow_ref"]==historical_scope["operational_workflow_ref"] \
        and p["historical_source_sha256"][".github/workflows/lab.yml"]==historical_scope["operational_workflow_sha256"] \
        and actor.get("login")=="github-actions[bot]" and type(actor.get("id")) is int and actor["id"]==41898282
    require(run.get("id")==int(h["run_id"]) and run.get("head_sha")==h["source_sha"] and run.get("status")=="completed"
        and run.get("conclusion")=="success" and run.get("event")=="workflow_dispatch" and run.get("run_attempt")==1
        and run.get("path")==".github/workflows/lab.yml" and run.get("head_branch")==h["producer"]["workflow_ref"].split("@refs/heads/",1)[1]
        and run.get("repository",{}).get("full_name")==run.get("head_repository",{}).get("full_name")==store.REPO
        and ((granted_bot and type(run.get("triggering_actor")) is dict
            and run["triggering_actor"].get("login")=="github-actions[bot]"
            and type(run["triggering_actor"].get("id")) is int and run["triggering_actor"]["id"]==41898282) if v5
            else (original_owner or granted_bot)),
        "ACTUAL_REGISTERED_COMPLETED_SUCCESSFUL_PRIOR_RUN")
    require(type(listing.get("jobs")) is list and listing.get("total_count")==len(listing["jobs"])<=100,"COMPLETE_PRIOR_WEEKLY_JOB_LIST")
    ids=dict(produce=h["producer"]["api_job_id"],restore=p["reader_handoff"]["restorer"]["api_job_id"],consume=p["exporter_api_job_id"])
    evidence={}
    for role,api_id in ids.items():
        matches=[j for j in listing["jobs"] if j.get("id")==api_id]
        require(len(matches)==1,"EXACT_REGISTERED_PRIOR_WEEKLY_API_ID");j=matches[0]
        require(j.get("name")==h["jobs"][role] and j.get("run_id")==int(h["run_id"]) and j.get("head_sha")==h["source_sha"]
            and j.get("status")=="completed" and j.get("conclusion")=="success"
            and store.utc(j["started_at"])<=store.utc(j["completed_at"])<=store.utc(p["registered_at_utc"])<=store.utc(authority["issued_at_utc"]),
            "PRIOR_PRODUCER_READER_EXPORTER_SUCCESS_SOURCE_AND_CLOCKS")
        evidence[role]=dict(repository=store.REPO,run_id=h["run_id"],source_sha=h["source_sha"],workflow_ref=h["producer"]["workflow_ref"],
            api_job_id=api_id,job_id=j["name"],status=j["status"],conclusion=j["conclusion"],started_at=j["started_at"],completed_at=j["completed_at"])
    require(store.utc(evidence["produce"]["completed_at"])<=store.utc(evidence["restore"]["started_at"])
        and store.utc(evidence["restore"]["completed_at"])<=store.utc(evidence["consume"]["started_at"])
        <=store.utc(evidence["consume"]["completed_at"])<store.utc(client.started_at),"CAUSAL_COMPLETED_PRIOR_ARCHIVE_CHAIN")
    for name,digest in p["historical_source_sha256"].items():
        doc=client.json(client.allow(source_url(h["source_sha"],name)))
        require(doc.get("type")=="file" and doc.get("path")==name and doc.get("encoding")=="base64"
            and type(doc.get("size")) is int and 0<doc["size"]<=256 << 10,"BOUNDED_HISTORICAL_ARCHIVE_CODE_METADATA")
        raw=base64.b64decode(doc["content"].replace("\n",""),validate=True)
        require(len(raw)==doc["size"] and store.sha(raw)==digest,"REGISTERED_HISTORICAL_ARCHIVE_SOURCE_HASH")
        if name==".github/workflows/lab.yml":permissions=workflow_permissions(raw,h)
    for role,row in evidence.items():row["verified_permissions"]=permissions[role]
    if historical_grant is not None:
        historical_grant.verify(p,authority,now())
        require(evidence==historical_grant.document["historical_jobs"],"LIVE_HISTORICAL_JOBS_MUST_EQUAL_SEALED_GRANT")
        _grant_authenticate(historical_grant._authenticate,"LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET",
            dict(grant_sha256=historical_grant.sha256,grant=historical_grant.document,
                current_run=current,historical_run=run,historical_jobs=evidence),now())
    q=p["qualified_runtime"]["qualification"]
    qualified=client.json(client.allow(store.API+"/actions/runs/"+q["run_id"]))
    require(qualified.get("status")=="completed" and qualified.get("conclusion")=="success","COMPLETED_SUCCESSFUL_QUALIFIED_RUNTIME_RUN")
    archive.authenticate_qualification(client,p["qualified_runtime"],p["pending_census"])
    client.inventory();client.draft()  # Unknown assets and unresolved pending count.
    return evidence


def r0_closure(index,aliases,storage):
    """Validate state METADATA only; native, board and cache bodies stay opaque."""
    names=set(aliases);origins=index["census"]["physical_origins"]
    fixed={"r0/CAPTURE_COMPLETE.json","r0/prepared.json","r0/original-native.json.gz","r0/original_board.json",
        "r0/next_state.json","r0/control_forecast_rows.json","r0/control_completion.json","r0/WORKER_COMPLETE.json"}
    require(index["census"]["r0_provided"] is True and fixed<=names,"FULL_RETAINED_R0_CONTROLS_AND_STATE_REQUIRED")
    doc=lambda n:archive.read_owned(storage,aliases[n],cap=2 << 20)
    def matches(ref,name):
        require(ref==origins[name] and (ref["bytes"],ref["sha256"])==(aliases[name]["bytes"],aliases[name]["sha256"]),"R0_ORIGINAL_PHYSICAL_METADATA_BINDING")
    capture=doc("r0/CAPTURE_COMPLETE.json");worker=doc("r0/WORKER_COMPLETE.json");state=doc("r0/next_state.json")
    require(capture["schema_version"]==reference.VERSION+"-capture" and capture["state"]=="ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE"
        and capture["fixed_original_default_refresh"] is True and capture["fits"]==0 and capture["public_release"] is False
        and worker["state"]=="ORIGINAL_R0_DEFAULT_PROCEDURE_CAPTURED" and worker["fixed_original_default_refresh"] is True
        and worker["fits"]==0 and worker["public_release"] is False,"UNCHANGED_ORIGINAL_DEFAULT_R0_CAPTURE")
    for role,name in (("prepared","r0/prepared.json"),("native","r0/original-native.json.gz"),("original_board","r0/original_board.json"),
            ("next_state","r0/next_state.json"),("control_forecast_rows","r0/control_forecast_rows.json"),("control_completion","r0/control_completion.json")):
        matches(capture[role],name)
    require(worker["native"]==capture["native"] and worker["next_state"]==capture["next_state"] and worker["board"]==capture["original_board"],
        "EXACT_R0_WORKER_NATIVE_STATE_BOARD")
    require(state["schema_version"]==reference.VERSION+"-state" and state["source"]==reference.SOURCE and state["procedure"]==reference.PROCEDURE
        and state["model"]==reference.ORIGINAL_MODEL and state["frozen_R0_identity_sha256"]==reference.R0_IDENTITY
        and state["source_files"]==reference.SOURCE_FILES and state["fits"]==0 and state["public_release"] is False
        and state["native_sha256"]==capture["native"]["sha256"],"PRESERVED_ORIGINAL_R0_STATE_IDENTITY")
    files=state["files"]
    require(type(files) is dict and 0<len(files)<=256 and sum(r["bytes"] for r in files.values())<=reference.LIMITS["state_bytes"],"COMPLETE_BOUNDED_R0_DEFAULT_CACHE")
    require(files.get("output/data/week.json")==capture["original_board"] and files.get("output/data/meta.json")==worker.get("meta")
        and "output/data/meta.json" in files,"FULL_ORIGINAL_R0_DEFAULT_BOARD_AND_META_STATE")
    previous={}
    for name,ref in files.items():
        require(type(name) is str and PurePosixPath(name).as_posix()==name and reference._state_name(name)
            and not name.endswith((".joblib",".pkl",".pickle",".parquet")),"ORIGINAL_R0_STATE_PATH_SCOPE")
        logical="r0/cache/"+name;require(logical in aliases,"NO_MISSING_ORIGINAL_R0_CACHE_BODY");matches(ref,logical);previous[name]=aliases[logical]
    require({n for n in names if n.startswith("r0/cache/")}=={"r0/cache/"+n for n in files},"NO_EXTRA_OR_DROPPED_R0_STATE_FILES")
    observations=worker["source_observations"]
    require(type(observations) is list and len(observations)<=512,"BOUNDED_R0_SOURCE_OBSERVATION_METADATA")
    require({n for n in names if n.startswith("r0/source-observations/")}=={f"r0/source-observations/{n:03}.json" for n in range(len(observations))},
        "COMPLETE_ORIGINAL_R0_SOURCE_OBSERVATIONS")
    for n,ref in enumerate(observations):matches(ref,f"r0/source-observations/{n:03}.json")
    completion=doc("r0/control_completion.json")
    require(completion["schema_version"]==reference.VERSION+"-control-completion" and completion["forecast_binding"]==capture["control_forecast_rows"]
        and completion["remote_durability_qualified"] is False and completion["fits"]==0 and completion["public_release"] is False
        and store.utc(completion["actual_issued_at"])<=store.utc(completion["body_persist_completed_at"])<=store.utc(capture["actual_completed_at"]),
        "ORIGINAL_R0_CONTROL_COMPLETION_NOT_FABRICATED")
    validate_owned_references(storage,{v["path"]:v["sha256"] for v in previous.values()})
    return dict(previous_state=aliases["r0/next_state.json"],previous_state_aliases=previous,control_forecast_rows=aliases["r0/control_forecast_rows.json"],
        control_completion=aliases["r0/control_completion.json"],capture=aliases["r0/CAPTURE_COMPLETE.json"],original_native=aliases["r0/original-native.json.gz"])


def restore(p,factory,*,storage,authority,root,check_authority=None,historical_grant=None):
    h=validate_request(p,root);r=p["reader_handoff"]
    require(authority["request_sha256"]==store.sha(store.canonical(p)) and store.utc(p["registered_at_utc"])<=store.utc(authority["issued_at_utc"]),
        "FRESH_PARENT_AUTHORITY_BINDS_APPROVED_PRIOR_REGISTRATION")
    output=archive.fresh(storage,p["output"]);clients=[]
    def guard():
        require(store.utc(authority["issued_at_utc"])<=now()<store.utc(authority["expires_at_utc"]),"RETAINED_AUTHORITY_EXPIRED_NO_RETRY")
        if check_authority:check_authority()
    current=None
    def client():
        nonlocal current
        guard();require(len(clients)<MAX_CLIENTS,"ELEVEN_FINITE_GET_ONLY_RETAINED_CLIENTS")
        c=factory("restore");require(isinstance(c,ReadClient) and c.binding==h["runtime_binding"],"REGISTERED_READ_ONLY_NATIVE_CLIENT_REQUIRED")
        c.authenticate_actions_job();ident=acceptance.identity(cp.client_identity(c))
        require(ident["run_id"]==authority["run_id"]!=h["run_id"] and ident["source_sha"]==authority["source_sha"]
            and ident["job_id"]==authority["job_id"] and ident["api_job_id"]==authority["api_job_id"]
            and ident["workflow_ref"]==authority["workflow_ref"] and ident["process_identity"] not in
            {h["producer"]["process_identity"],r["restorer"]["process_identity"]},"CURRENT_PROOF_IDENTITY_NEVER_RELABELLED")
        require(current is None or current==ident,"ONE_GENUINE_CURRENT_RETAINED_PROCESS")
        current=ident;clients.append(c);return c
    first=client();evidence=authenticate_origin(first,p,authority,historical_grant=historical_grant)
    proofs=[];downloads={}
    def get(descriptor,name,cap):
        c=client();entry=cp.descriptor_meta(descriptor,cap);destination=output/"downloads"/name;destination.parent.mkdir(parents=True,exist_ok=True)
        with storage.transaction():
            storage._require(2*entry["payload"]["bytes"]+archive.ENTRY_CAP)
            proof=store.restore(c,descriptor,destination);owned=output/"owned-downloads"/name
            storage.import_file(destination,owned,expected_sha256=entry["payload"]["sha256"])
        require(acceptance.restored_identity(proof)==current and proof["payload_sha256"]==entry["payload"]["sha256"]
            and proof["bytes"]==entry["payload"]["bytes"] and store.utc(authority["issued_at_utc"])<=store.utc(proof["started_at_utc"])
            <=store.utc(proof["created_at_utc"])<=now(),"GENUINE_CURRENT_PAYLOAD_PROOF_AND_NEW_CLOCK")
        proofs.append(proof);downloads[name]=cp.binding(owned);return cp.read_ref(downloads[name],cap)
    raw=get(h["index_descriptor"],"index.gz",archive.INDEX_CAP);index=archive.check_index(archive.unpack(raw,archive.INDEX_PLAIN_CAP),h)
    historical_scope=(historical_grant.document["v5_historical_scope"] if historical_grant._v5_discovery is not None else historical_grant.document["scope"]) if historical_grant is not None else None
    if historical_scope is not None and h["source_sha"]==historical_scope["approved_source_sha"]:
        policy=[f for f in index["files"] if f["logical_path"]=="context/public_policy.json"]
        require(len(policy)==1 and 0<policy[0]["bytes"]<=128 << 10
            and policy[0]["sha256"]==historical_scope["public_policy_sha256"],
            "EXACT_GRANTED_OPERATIONAL_ARCHIVE_PUBLIC_POLICY")
    writer=evidence["produce"];producer=index["producer_proof"]
    require(index["qualification_sha256"]==store.sha(store.canonical(p["qualified_runtime"]["qualification"]))
        and producer["root_go_sha256"]==h["root_go_sha256"] and producer["fits"]==0
        and producer["public_release"] is producer["successful_forecast"] is False
        and store.utc(writer["started_at"])<=store.utc(producer["actual_started_at"])<=store.utc(index["created_at"])<=store.utc(writer["completed_at"]),
        "EXACT_ORIGINAL_QUALIFIED_PRODUCER_PROOF_AND_CLOCKS")
    # Preserve original unresolved POST receipts as metadata. Only exact live
    # name/size/server digest membership can discharge their quota charge.
    cp.seed_pending(first.journal,index["pending_reservations"]);first.inventory()
    past=archive.unpack(get(r["witness_descriptor"],"past-reader-witness.gz",archive.WITNESS_CAP),archive.WITNESS_CAP)
    require(type(past) is dict and set(past)==WITNESS_KEYS and past["schema_version"]==archive.VERSION+"-witness"
        and past["restorer"]==r["restorer"] and past["index_sha256"]==store.sha(raw) and past["files_sha256"]==h["files_sha256"]
        and past["producer_proof_sha256"]==store.sha(store.canonical(producer)) and past["archive_state"]=="COMPLETE_CAPTURE"
        and past["public_export_authorized"] is past["successful_forecast"] is False,"ORIGINAL_READER_WITNESS_EXACT_SOURCE_SCOPE")
    expected=[(len(raw),store.sha(raw))]+[(g["bytes"],g["sha256"]) for g in index["groups"]]
    require(type(past["proofs"]) is list and [(v["bytes"],v["payload_sha256"]) for v in past["proofs"]]==expected,
        "EVERY_ORIGINAL_INDEX_AND_GROUP_READER_PROOF_REQUIRED")
    reader=evidence["restore"]
    for proof in past["proofs"]:
        store.check_proof(first,proof,"restore",same_run=False)
        require(acceptance.restored_identity(proof)==r["restorer"] and store.utc(reader["started_at"])<=store.utc(proof["started_at_utc"])
            <=store.utc(proof["created_at_utc"])<=store.utc(past["actual_completed_at"])<=store.utc(reader["completed_at"]),
            "UNMODIFIED_HISTORICAL_READER_PROOFS_INSIDE_ACTUAL_JOB")
    with storage.transaction():storage._require(sum(f["bytes"] for f in index["files"])+sum(g["bytes"]*2 for g in index["groups"])+(4 << 20))
    for group in index["groups"]:
        guard();archive._extract_owned_group(get(group["descriptor"],str(group["index"])+".gz",store.ASSET_CAP),group,storage,output/"files")
    empty=[(f["logical_path"],b"") for f in index["files"] if f["bytes"]==0]
    if empty:archive._publish_owned_files(storage,empty,output/"files")
    aliases={f["logical_path"]:dict(path=str(output/"files"/f["logical_path"]),bytes=f["bytes"],sha256=f["sha256"]) for f in index["files"]}
    validate_owned_references(storage,{ref["path"]:ref["sha256"] for ref in aliases.values()})
    guard();validation=archive.validate_capture(index,lambda name:Path(aliases[name]["path"]),complete=True)
    require(validation==past["validation"] and validation["replay_ready"] is True,"UNCHANGED_COMPLETE_CAPTURE_READBACK_VALIDATION")
    validate_owned_references(storage,{ref["path"]:ref["sha256"] for ref in aliases.values()})
    r0=r0_closure(index,aliases,storage);guard()
    calls=sum(c.calls for c in clients);rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    require(calls<=LIMITS["HTTP_calls"] and rss<=LIMITS["RSS_bytes"],"FINITE_RETAINED_WEEKLY_HTTP_AND_RSS")
    metadata={role:aliases["context/"+role+".json"] for role in archive.CONTEXT}
    metadata.update(choice=aliases["runtime/WEEKLY_CHOICE.json"],artifact_catalog=aliases["runtime/ARTIFACT_CATALOG.json"],
        selected_versions=aliases["runtime/SELECTED_VERSION_CATALOG.json"],terminal=aliases["runtime/FINISHED.json"],
        prepared_choice_completion=aliases["prepared/choice_completion.json"])
    result=dict(schema_version=VERSION+"-result",state="PRIVATE_PRIOR_CAPTURE_RESTORED",created_at_utc=now().isoformat(),
        registration_sha256=store.sha(store.canonical(p)),current_root_go_sha256=authority["owner_root_go_sha256"],current=current,
        original_archive=h,original_reader_handoff=r,original_index=downloads["index.gz"],original_reader_witness=downloads["past-reader-witness.gz"],
        historical_producer_proof=producer,historical_reader_witness=past,historical_job_evidence=evidence,current_restore_proofs=proofs,
        original_exporter_proof_scope="COMPLETED_JOB_API_AND_PINNED_WORKFLOW_PERMISSIONS_NOT_RETAINED_RAW_EXPORT_PROOF",
        aliases=aliases,metadata=metadata,r0=r0,previous_state=r0["previous_state"],previous_state_aliases=r0["previous_state_aliases"],
        original_physical_bindings=index["census"]["physical_origins"],validation=validation,files_sha256=h["files_sha256"],
        HTTP_calls=calls,RSS_peak_bytes=rss,fits=0,model_decodes=0,source_acquisitions=0,protected_outcome_reads=0,remote_writes=0,
        model_replay_performed=False,public_export_authorized=False,public_release=False,successful_forecast=False)
    archive.write(storage,output/"RETAINED_RESULT.json",result)
    return result
