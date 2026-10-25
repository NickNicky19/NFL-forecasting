"""Additive GHA controller authentication, never activation or dispatch.

The externally trusted seal is supplied separately from ROOT/context JSON. Its
public registration contains literal source SHAs, so no Git self-reference is
introduced. Every live verification reads raw API bodies through a fixed-route
GET-only callback; saved JSON flags/proofs cannot replace it. No import performs
IO, credential access, provider reads, fitting, publication or workflow mutation.

ROOT.effective_epoch.controller_context contains only a deterministic claim
path, not the final claim/body hash (which would make ROOT self-referential).
The owner-controlled append-only lab-state publisher must atomically create the
closed claim after ROOT serialization and before enqueue. The child verifies
its original added-file history and exact ROOT SHA. Creating that claim, sealing
registration, complete source/artifact readiness, constructing private ROOT,
enqueueing ONCE and EXITING the parent are the integrator's separate work.

The parent must enforce its native 180s/120CPU/512MiB envelope. Cooperative
checks here do not interrupt a blocked metadata callback. No polling or retries.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import resource
import subprocess
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo
import zlib

from .cadence import LEGACY_POLICY, PARENT_POLICY, SINGLE_WORKFLOW_CRON

VERSION = "audit-weekly-controller-v1"
REPO = "NickNicky19/NFL-forecasting"
API = "https://api.github.com/repos/"+REPO
WORKFLOW = ".github/workflows/lab.yml"
MODE = "audit-weekly-producer-v1"
GROUP = "nfl-lab-single-writer"
OWNER = dict(login="NickNicky19",id=208912933)
BOT = dict(login="github-actions[bot]",id=41898282)
CADENCE = dict(timezone="America/Chicago",hour=8,minute_first=36,minute_last=56,cron="36 13,14 * * *")
PARENT_CADENCE = dict(policy_version=PARENT_POLICY,timezone="America/Chicago",hour=7,
    minute_first=36,minute_last=56,cron=SINGLE_WORKFLOW_CRON)
CONCURRENCY = dict(group=GROUP,cancel_in_progress=False)
LIMITS = dict(HTTP_calls=20,wall_seconds=180,CPU_seconds=120,RSS_bytes=512 << 20,
    metadata_bytes=1 << 20,root_bytes=60 << 10,retries=0,POSTs=0,fits=0)
RETURN_RULE = "ENQUEUE_ONCE_AND_EXIT_NO_CHILD_POLL"
ROLES = ("produce","restore","consume")
JOB_ROLES = set(ROLES)|{"evidence"}
MODULE = "nfl_lab/audit_weekly_controller_v1.py"
TOOL = "tools/audit_weekly_controller_v1.py"
REG_KEYS = {"schema_version","state","scope","repository","registered_at_utc","parent","producer",
    "readiness","cadence","concurrency","limits","parent_return_rule"}
PARENT_KEYS = {"source_sha","branch","job_id","workflow_sha256","code_pins","actors"}
PRODUCER_KEYS = {"source_sha","branch","mode","workflow_sha256","code_pins","actor","jobs"}
READY_KEYS = {"source_sha","branch","run_id","workflow_sha256","jobs","receipt_sha256","receipt_body_sha256","receipt_bindings"}
RECEIPT_HASH_KEYS = {"root_go_sha256","policy_sha256","recipe_registration_sha256","feed_sha256",
    "archive_index_sha256","archive_files_sha256","reader_witness_sha256","epoch_sha256","choice_sha256",
    "origin_choice_sha256","r0_identity_sha256","rights_authority_sha256"}
RECEIPT_KEYS = RECEIPT_HASH_KEYS|{"schema_version","source_sha","run_id","policy_registered_at_utc","workflow_sha256",
    "feed_bytes","rows","categories","jobs","created_at","verified_at","fits","raw_or_models_public"}
PARENT_DOC_KEYS = {"schema_version","repository","run_id","run_attempt","source_sha","workflow_ref","event","actor",
    "job_id","api_job_id","job_started_at","workflow_sha256","verified_at_utc","state"}
CONTEXT_KEYS = {"schema_version","registration_sha256","scheduled_parent","claim_id","claim_locator"}
CLAIM_KEYS = {"schema_version","repository","claim_id","registration_sha256","parent_run_id","parent_api_job_id",
    "parent_source_sha","producer_source_sha","root_go_sha256","created_at_utc"}
TARGETS = {"pass_yd","pass_td","pass_cmp","pass_att","pass_int","rush_yd","rush_att","rec","rec_yd","rush_rec_yd","anytime_td"}
_KEY = object()


class ControllerError(ValueError):
    """Fixed public-safe errors only."""


def require(value,code):
    if not value:
        raise ControllerError(code)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def digest(value):
    return sha(canonical(value))


def decode(body):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,"DUPLICATE_CONTROLLER_JSON")
            result[key]=value
        return result
    def bad(_):
        raise ControllerError("NONFINITE_CONTROLLER_JSON")
    return json.loads(body,object_pairs_hook=pairs,parse_constant=bad)


def utc(value):
    stamp=value if isinstance(value,datetime) else datetime.fromisoformat(value.replace("Z","+00:00"))
    require(stamp.tzinfo is not None,"AWARE_CONTROLLER_CLOCK_REQUIRED")
    return stamp.astimezone(timezone.utc)


def now():
    return datetime.now(timezone.utc)


def hashed(value,n=64):
    return type(value) is str and re.fullmatch("[a-f0-9]{%d}"%n,value) is not None


def positive(value):
    return type(value) is int and value>0


def run_id(value):
    return type(value) is str and re.fullmatch("[1-9][0-9]{0,19}",value) is not None


def branch(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,159}",value) and all(
        x not in {"",".",".."} and not x.endswith(".lock") for x in value.split("/"))


def actor(value,expected):
    return type(value) is dict and value.get("login")==expected["login"] and type(value.get("id")) is int and value["id"]==expected["id"]


def source_path(path):
    require(type(path) is str and not path.startswith("/") and "\\" not in path
        and all(x not in {"",".",".."} for x in path.split("/"))
        and (re.fullmatch(r"(?:nfl_lab|tools|tests|config|schemas)/[A-Za-z0-9_./-]+\.(?:py|json|yml|yaml)",path)
             or re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml",path)
             or re.fullmatch(r"requirements[A-Za-z0-9_.-]*\.lock",path)), "PUBLIC_SOURCE_PIN_PATH_ONLY")
    return path


def cadence_policy(value):
    """Old sealed cadence bytes keep their meaning; new policy is explicit."""
    require(type(value) is dict and canonical(value) in {canonical(CADENCE),canonical(PARENT_CADENCE)},
        "CLOSED_REGISTERED_CONTROLLER_CADENCE_POLICY")
    return value


def registration_template(*,cadence_policy_version=PARENT_POLICY):
    """Public-safe, deliberately unusable until independently owner-sealed."""
    require(cadence_policy_version in {LEGACY_POLICY,PARENT_POLICY},"EXPLICIT_CONTROLLER_CADENCE_VERSION")
    policy=CADENCE if cadence_policy_version==LEGACY_POLICY else PARENT_CADENCE
    return dict(schema_version=VERSION+"-registration",state="PREPARED_UNREGISTERED",
        scope="GHA_METADATA_AND_ONCE_CLAIM_BINDING_ONLY",repository=REPO,registered_at_utc=None,
        parent=dict(source_sha=None,branch="main",job_id="lab",workflow_sha256=None,code_pins={},
            actors=dict(schedule=deepcopy(OWNER),workflow_dispatch=deepcopy(OWNER))),
        producer=dict(source_sha=None,branch=None,mode=MODE,workflow_sha256=None,code_pins={},actor=deepcopy(BOT),
            jobs=dict(produce="audit-weekly-produce-v1",restore="audit-weekly-restore-v1",
                consume="audit-weekly-export-v1",evidence="audit-weekly-failure-restore-v1")),
        readiness=dict(source_sha=None,branch=None,run_id=None,workflow_sha256=None,jobs={},
            receipt_sha256=None,receipt_body_sha256=None,receipt_bindings={}),
        cadence=deepcopy(policy),concurrency=deepcopy(CONCURRENCY),limits=dict(LIMITS),parent_return_rule=RETURN_RULE)


def registration(body,*,sealed_sha256,at):
    require(type(body) is bytes and 0<len(body)<=128 << 10 and hashed(sealed_sha256)
        and sha(body)==sealed_sha256,"EXTERNAL_OWNER_SEAL_REQUIRED")
    p=decode(body)
    require(type(p) is dict and set(p)==REG_KEYS,"CLOSED_SEALED_CONTROLLER_REGISTRATION")
    cadence_policy(p["cadence"])
    require(type(p) is dict and set(p)==REG_KEYS and body==canonical(p)
        and p["schema_version"]==VERSION+"-registration" and p["state"]=="OWNER_SEALED_METADATA_BINDING"
        and p["scope"]=="GHA_METADATA_AND_ONCE_CLAIM_BINDING_ONLY" and p["repository"]==REPO
        and canonical(p["concurrency"])==canonical(CONCURRENCY)
        and canonical(p["limits"])==canonical(LIMITS)
        and p["parent_return_rule"]==RETURN_RULE and utc(p["registered_at_utc"])<=utc(at),"CLOSED_SEALED_CONTROLLER_REGISTRATION")
    for value,keys in ((p["parent"],PARENT_KEYS),(p["producer"],PRODUCER_KEYS)):
        require(type(value) is dict and set(value)==keys and hashed(value["source_sha"],40) and branch(value["branch"])
            and hashed(value["workflow_sha256"]),"LITERAL_PARENT_AND_PRODUCER_SOURCE_BINDINGS")
        pins=value["code_pins"]
        require(type(pins) is dict and {MODULE,TOOL}<=set(pins) and len(pins)<=128
            and all(hashed(v) for v in pins.values()),"EXACT_CONTROLLER_SOURCE_INVENTORY")
        for path in pins:
            source_path(path)
        if WORKFLOW in pins:
            require(pins[WORKFLOW]==value["workflow_sha256"],"WORKFLOW_PIN_CONSISTENCY")
    require(canonical(p["parent"]["actors"])==canonical(dict(schedule=OWNER,workflow_dispatch=OWNER))
        and re.fullmatch("[A-Za-z0-9_-]{1,100}",str(p["parent"]["job_id"]))
        and canonical(p["producer"]["actor"])==canonical(BOT) and p["producer"]["mode"]==MODE
        and type(p["producer"]["jobs"]) is dict and set(p["producer"]["jobs"])==JOB_ROLES
        and len(set(p["producer"]["jobs"].values()))==4
        and all(type(v) is str and re.fullmatch("[A-Za-z0-9_-]{1,100}",v) for v in p["producer"]["jobs"].values()),
        "FIXED_OWNER_PARENT_AND_BOT_CHILD_ROLES")
    r=p["readiness"]
    require(type(r) is dict and set(r)==READY_KEYS and hashed(r["source_sha"],40) and branch(r["branch"])
        and run_id(r["run_id"]) and all(hashed(r[k]) for k in ("workflow_sha256","receipt_sha256","receipt_body_sha256"))
        and type(r["receipt_bindings"]) is dict and set(r["receipt_bindings"])==RECEIPT_HASH_KEYS
        and all(hashed(v) for v in r["receipt_bindings"].values()),"PINNED_HISTORICAL_READINESS_RECEIPT")
    require(type(r["jobs"]) is dict and set(r["jobs"])==set(ROLES)
        and all(type(j) is dict and set(j)=={"job_id","api_job_id"} and positive(j["api_job_id"])
            and type(j["job_id"]) is str and re.fullmatch("[A-Za-z0-9_-]{1,100}",j["job_id"]) for j in r["jobs"].values())
        and len({j["api_job_id"] for j in r["jobs"].values()})==3 and len({j["job_id"] for j in r["jobs"].values()})==3,
        "EXACT_OLD_THREE_JOB_IDENTITIES")
    return p


@dataclass(frozen=True)
class Reply:
    """Only an in-process HTTP callback can supply transport status/raw bytes."""
    status: int
    body: bytes


class Metadata:
    def __init__(self,get_metadata,allowed,*,clock=now):
        require(callable(get_metadata) and callable(clock),"LIVE_RAW_METADATA_GET_CALLBACK_REQUIRED")
        self.get_metadata,self.allowed,self.clock=get_metadata,frozenset(allowed),clock
        self.started=time.monotonic();self.cpu=time.process_time();self.calls=[]
    def budget(self):
        require(time.monotonic()-self.started<=180 and time.process_time()-self.cpu<=120
            and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=512 << 20,"CONTROLLER_NATIVE_BUDGET_REQUIRED")
    def get(self,url,cap=1 << 20):
        self.budget()
        require(url in self.allowed and fixed_route(url) and len(self.calls)<20 and type(cap) is int and 0<cap<=1 << 20,
            "FIXED_METADATA_GET_ROUTE_OR_CALL_CAP")
        record=dict(url=url,state="ATTEMPTED");self.calls.append(record)
        response=self.get_metadata(url,cap)
        if type(response) is Reply and type(response.body) is bytes:
            record.update(status=response.status,sha256=sha(response.body),bytes=len(response.body))
        require(type(response) is Reply and type(response.status) is int and response.status==200
            and type(response.body) is bytes and 0<len(response.body)<=cap,"GENUINE_METADATA_HTTP_BODY_REQUIRED")
        record["state"]="OBSERVED"
        self.budget()
        return decode(response.body)


def fixed_route(url):
    if type(url) is not str or not url.startswith(API+"/"):
        return False
    path=url[len(API)+1:]
    if "\\" in path or "%" in path or any(x in {".",".."} for x in path.split("/")):
        return False
    return any(re.fullmatch(pattern,path) for pattern in (
        r"actions/runs/[1-9][0-9]{0,19}(?:/jobs\?per_page=100&page=1)?",
        r"contents/\.github/workflows/lab\.yml\?ref=[a-f0-9]{40}",
        r"contents/state/public/weekly-adaptive-v1/receipts/[a-f0-9]{64}\.json\.gz\?ref=lab-state",
        r"contents/state/controller-v1/claims/[a-f0-9]{64}\.json\?ref=[a-f0-9]{40}",
        r"git/ref/heads/[A-Za-z0-9_][A-Za-z0-9_./-]{0,159}",
        r"commits\?sha=lab-state&path=state/controller-v1/claims/[a-f0-9]{64}\.json&per_page=2&page=1",
        r"commits/[a-f0-9]{40}")) is True


def run_url(identifier):
    require(run_id(identifier),"EXACT_GHA_RUN_ID")
    return API+"/actions/runs/"+identifier


def jobs_url(identifier):
    return run_url(identifier)+"/jobs?per_page=100&page=1"


def contents_url(path,ref):
    require(type(path) is str and type(ref) is str and (hashed(ref,40) or ref=="lab-state"),"FIXED_CONTENTS_REFERENCE")
    return API+"/contents/"+quote(path,safe="/")+"?ref="+ref


def head_url(p):
    return API+"/git/ref/heads/"+quote(p["producer"]["branch"],safe="/")


def receipt_path(p):
    return "state/public/weekly-adaptive-v1/receipts/"+p["readiness"]["receipt_bindings"]["feed_sha256"]+".json.gz"


def claim_path(identifier):
    require(hashed(identifier),"EXACT_DISPATCH_CLAIM_ID")
    return "state/controller-v1/claims/"+identifier+".json"


def claim_history(path):
    return API+"/commits?sha=lab-state&path="+quote(path,safe="/")+"&per_page=2&page=1"


def git_head(root):
    """Read-only; existing caller ROOT/head/clean-tree checks remain required."""
    value=subprocess.check_output(["git","--no-lazy-fetch","-c","core.fsmonitor=false","rev-parse","HEAD"],
        cwd=root,stderr=subprocess.DEVNULL,timeout=5,text=True).strip()
    require(hashed(value,40),"ACTUAL_LOCAL_HEAD_REQUIRED")
    return value


def local_source(spec,root,read_head):
    root=Path(root).absolute()
    require(read_head(root)==spec["source_sha"],"CURRENT_LOCAL_SOURCE_HEAD_MISMATCH")
    for name,expected in spec["code_pins"].items():
        source_path(name);path=root/name
        require(not any(x.is_symlink() for x in (path,*path.parents)) and path.is_file() and path.stat().st_size<=2 << 20,
            "PLAIN_PINNED_LOCAL_SOURCE_REQUIRED")
        require(sha(path.read_bytes())==expected,"CURRENT_CODE_INVENTORY_MISMATCH")
    return digest(spec["code_pins"])


def blob_sha(body):
    return hashlib.sha1(b"blob "+str(len(body)).encode()+b"\0"+body).hexdigest()


def content(api,path,ref,*,cap):
    value=api.get(contents_url(path,ref),min(1 << 20,2*cap+8192))
    require(type(value) is dict and value.get("type")=="file" and value.get("path")==path
        and value.get("encoding")=="base64" and type(value.get("content")) is str,"EXACT_API_CONTENTS_FILE")
    try:
        body=base64.b64decode(value["content"].replace("\n",""),validate=True)
    except (ValueError,TypeError):
        raise ControllerError("INVALID_API_CONTENTS_ENCODING") from None
    require(0<len(body)<=cap and type(value.get("size")) is int and value["size"]==len(body)
        and value.get("sha")==blob_sha(body),"API_CONTENTS_PHYSICAL_GIT_BLOB")
    return body


def workflow(api,spec,job_id,*,parent=False,cadence=None):
    body=content(api,WORKFLOW,spec["source_sha"],cap=256 << 10)
    require(sha(body)==spec["workflow_sha256"],"EXACT_REGISTERED_WORKFLOW_BYTES")
    import yaml
    wf=yaml.load(body,Loader=yaml.BaseLoader)  # "on" stays a key; no custom tags or executable constructors.
    require(type(wf) is dict and wf.get("concurrency")=={"group":GROUP,"cancel-in-progress":"false"}
        and type(wf.get("jobs")) is dict and job_id in wf["jobs"],"UNCHANGED_SINGLE_WRITER_CONCURRENCY")
    job=wf["jobs"][job_id]
    require(type(job) is dict and job.get("name",job_id)==job_id and "concurrency" not in job,"EXACT_UNALIASED_JOB_AND_GROUP")
    permissions=job.get("permissions",wf.get("permissions"))
    require(type(permissions) is dict and permissions.get("contents")=="write"
        and permissions.get("actions") in ({"write"} if parent else {"read","write"}),"ACTUAL_WORKFLOW_PERMISSIONS")
    if parent:
        # The native registrar validates either closed reviewed workflow. Live
        # parent/child verification always supplies the actual sealed policy.
        crons={CADENCE["cron"],PARENT_CADENCE["cron"]} if cadence is None else {cadence_policy(cadence)["cron"]}
        require(type(wf.get("on")) is dict and wf["on"].get("schedule") in [[{"cron":cron}] for cron in crons]
            and "workflow_dispatch" in wf["on"],"EXISTING_DAILY_CADENCE_ONLY")
    return sha(body)


def complete_jobs(value):
    require(type(value) is dict and type(value.get("jobs")) is list and type(value.get("total_count")) is int
        and value["total_count"]==len(value["jobs"])<=100 and all(type(x) is dict for x in value["jobs"]),
        "COMPLETE_GHA_JOB_LIST_REQUIRED")
    return value["jobs"]


def checked_run(value,identifier,spec,expected_actor,*,event,status,strict_trigger=True):
    require(type(value) is dict and type(value.get("id")) is int and value["id"]==int(identifier)
        and value.get("repository",{}).get("full_name")==value.get("head_repository",{}).get("full_name")==REPO
        and value.get("head_sha")==spec["source_sha"] and value.get("head_branch")==spec["branch"]
        and value.get("event")==event and value.get("path")==WORKFLOW and type(value.get("run_attempt")) is int and value["run_attempt"]==1
        and value.get("status")==status and value.get("conclusion")==("success" if status=="completed" else None)
        and actor(value.get("actor"),expected_actor),"ACTUAL_GHA_RUN_SOURCE_EVENT_ACTOR_STATUS")
    if strict_trigger or "triggering_actor" in value:
        require(actor(value.get("triggering_actor"),expected_actor),"ACTUAL_GHA_TRIGGERING_ACTOR")
    return value


def job(value,identifier,spec,name,*,status,api_id=None):
    items=complete_jobs(value)
    found=[x for x in items if x.get("name")==name]
    require(len(found)==1,"UNIQUE_REGISTERED_GHA_JOB")
    result=found[0]
    require(positive(result.get("id")) and (api_id is None or result["id"]==api_id)
        and type(result.get("run_id")) is int and result["run_id"]==int(identifier) and result.get("head_sha")==spec["source_sha"]
        and result.get("status")==status and result.get("conclusion")==("success" if status=="completed" else None)
        and type(result.get("started_at")) is str,
        "ACTUAL_REGISTERED_GHA_JOB")
    if status=="completed":
        require(type(result.get("completed_at")) is str and utc(result["started_at"])<=utc(result["completed_at"]),
            "COMPLETED_GHA_JOB_CLOCK")
    return result


def common_env(env,spec,job_id,expected_actor,*,event):
    require(type(env) is dict and env.get("GITHUB_ACTIONS")=="true" and env.get("CI")=="true"
        and env.get("GITHUB_REPOSITORY")==REPO and env.get("GITHUB_RUN_ATTEMPT")=="1"
        and run_id(env.get("GITHUB_RUN_ID")) and env.get("GITHUB_EVENT_NAME")==event
        and env.get("GITHUB_SHA")==env.get("GITHUB_WORKFLOW_SHA")==spec["source_sha"]
        and env.get("GITHUB_WORKFLOW_REF")==REPO+"/"+WORKFLOW+"@refs/heads/"+spec["branch"]
        and env.get("GITHUB_JOB")==job_id and env.get("GITHUB_ACTOR")==expected_actor["login"]
        and env.get("GITHUB_ACTOR_ID")==str(expected_actor["id"]),"EXACT_CURRENT_GHA_ENVIRONMENT")


def due(event,stamp,*,cadence=None):
    policy=CADENCE if cadence is None else cadence_policy(cadence)
    if event=="schedule":
        local=utc(stamp).astimezone(ZoneInfo(policy["timezone"]))
        require(local.hour==policy["hour"] and policy["minute_first"]<=local.minute<=policy["minute_last"],"MISSED_DAILY_WINDOW_NO_BACKFILL")


def readiness(api,p,*,before):
    r=p["readiness"];identifier=r["run_id"]
    current=checked_run(api.get(run_url(identifier)),identifier,r,OWNER,event="workflow_dispatch",status="completed",strict_trigger=False)
    listing=api.get(jobs_url(identifier))
    chain=[job(listing,identifier,r,r["jobs"][role]["job_id"],status="completed",api_id=r["jobs"][role]["api_job_id"]) for role in ROLES]
    require(utc(chain[0]["completed_at"])<=utc(chain[1]["started_at"])
        and utc(chain[1]["completed_at"])<=utc(chain[2]["started_at"])
        and utc(chain[2]["completed_at"])<=utc(p["registered_at_utc"])<=utc(before),"ORIGINAL_READINESS_BEFORE_CONTROLLER_REGISTRATION")
    workflow(api,r,r["jobs"]["consume"]["job_id"])
    raw=content(api,receipt_path(p),"lab-state",cap=64 << 10)
    require(sha(raw)==r["receipt_sha256"],"EXACT_OLD_READINESS_RECEIPT_BYTES")
    try:
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS);plain=decoder.decompress(raw,(64 << 10)+1)
        require(len(plain)<=64 << 10 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,"BOUNDED_SINGLE_READINESS_GZIP")
    except zlib.error:
        raise ControllerError("INVALID_READINESS_GZIP") from None
    doc=decode(plain)
    require(type(doc) is dict and set(doc)==RECEIPT_KEYS and plain==canonical(doc)
        and sha(plain)==r["receipt_body_sha256"] and doc["schema_version"]=="audit-weekly-delivery-v1-public-receipt"
        and doc["source_sha"]==r["source_sha"] and doc["run_id"]==identifier and doc["workflow_sha256"]==r["workflow_sha256"]
        and doc["jobs"]==r["jobs"] and all(doc[k]==v for k,v in r["receipt_bindings"].items())
        and type(doc["fits"]) is int and doc["fits"]==0 and doc["raw_or_models_public"] is False
        and set(doc["categories"])==TARGETS and len(doc["categories"])==11 and type(doc["rows"]) is int and doc["rows"]>0
        and type(doc["feed_bytes"]) is int and doc["feed_bytes"]>0,"ACTUAL_HISTORICAL_THREE_JOB_RECEIPT")
    require(utc(doc["policy_registered_at_utc"])<=utc(doc["verified_at"])
        and utc(chain[2]["started_at"])<=utc(doc["verified_at"])<=utc(doc["created_at"])<=utc(chain[2]["completed_at"]),
        "PRESERVED_ORIGINAL_READINESS_CLOCKS")
    return current,dict(source_sha=r["source_sha"],run_id=identifier,receipt_sha256=sha(raw),receipt_body_sha256=sha(plain),
        jobs=deepcopy(r["jobs"]),scope="HISTORICAL_THREE_JOB_RECEIPT_ONLY_NOT_CURRENT_ARTIFACT_READINESS")


def check_head(api,p):
    value=api.get(head_url(p))
    require(type(value) is dict and value.get("ref")=="refs/heads/"+p["producer"]["branch"]
        and value.get("object",{}).get("type")=="commit" and value["object"].get("sha")==p["producer"]["source_sha"],
        "PRODUCER_REF_RACED_OR_WRONG_SOURCE")


def stable(before,after):
    fields=("id","repository","head_repository","head_sha","head_branch","path","event","run_attempt","status","conclusion","actor","triggering_actor","updated_at")
    require(all(before.get(k)==after.get(k) for k in fields),"GHA_RUN_RESTARTED_OR_CHANGED")


class Proof:
    """Live, exact-scope evidence. Public metadata exports cannot be rehydrated."""
    def __init__(self,document,key):
        require(key is _KEY,"LIVE_CONTROLLER_VERIFICATION_REQUIRED")
        self.document=deepcopy(document);self.sha256=digest(document)
    def verify(self,*,registration_sha256,run_id,job_id,root_sha256=None):
        require(self.sha256==digest(self.document) and self.document["registration_sha256"]==registration_sha256
            and self.document["run_id"]==run_id and self.document["job_id"]==job_id
            and (root_sha256 is None or self.document.get("root_go_sha256")==root_sha256),"CONTROLLER_PROOF_SCOPE_OR_INTEGRITY")
        return self
    def __reduce__(self):
        raise ControllerError("LIVE_CONTROLLER_PROOF_CANNOT_BE_SERIALIZED")


def controller_context(registration_sha256,scheduled_parent,claim_id):
    require(hashed(registration_sha256) and hashed(claim_id),"SEALED_CONTEXT_HASHES_REQUIRED")
    return dict(schema_version=VERSION+"-context",registration_sha256=registration_sha256,scheduled_parent=deepcopy(scheduled_parent),
        claim_id=claim_id,claim_locator=dict(repository=REPO,ref="lab-state",path=claim_path(claim_id)))


def _urls(p,identifiers):
    result={head_url(p),contents_url(WORKFLOW,p["parent"]["source_sha"]),contents_url(WORKFLOW,p["producer"]["source_sha"]),
        contents_url(WORKFLOW,p["readiness"]["source_sha"]),contents_url(receipt_path(p),"lab-state")}
    for identifier in identifiers:
        result|={run_url(identifier),jobs_url(identifier)}
    return result


def verify_parent(registration_bytes,*,sealed_sha256,env,event_bytes,source_root,metadata_get,clock=now,read_head=git_head):
    """Metadata proof for enqueue-and-return. No dispatch/claim/wait is performed."""
    at=utc(clock());p=registration(registration_bytes,sealed_sha256=sealed_sha256,at=at);spec=p["parent"]
    event=env.get("GITHUB_EVENT_NAME");require(event in {"schedule","workflow_dispatch"},"REGISTERED_PARENT_EVENT_ONLY")
    common_env(env,spec,spec["job_id"],OWNER,event=event)
    data=decode(event_bytes)
    require(data.get("repository",{}).get("full_name")==REPO and
        (data.get("schedule")==p["cadence"]["cron"] if event=="schedule" else data.get("inputs",{}).get("mode")=="daily"),"ACTUAL_PARENT_EVENT_BODY")
    local_source(spec,source_root,read_head)
    identifier=env["GITHUB_RUN_ID"];api=Metadata(metadata_get,_urls(p,(identifier,p["readiness"]["run_id"])),clock=clock)
    current=checked_run(api.get(run_url(identifier)),identifier,spec,OWNER,event=event,status="in_progress")
    actual=job(api.get(jobs_url(identifier)),identifier,spec,spec["job_id"],status="in_progress")
    require(utc(p["registered_at_utc"])<=utc(actual["started_at"])<=at,"CURRENT_PARENT_ACTUAL_CLOCK")
    due(event,actual["started_at"],cadence=p["cadence"]);workflow(api,spec,spec["job_id"],parent=True,cadence=p["cadence"])
    old,ready=readiness(api,p,before=actual["started_at"]);check_head(api,p)
    stable(old,api.get(run_url(p["readiness"]["run_id"])))
    stable(current,api.get(run_url(identifier)))
    job(api.get(jobs_url(identifier)),identifier,spec,spec["job_id"],status="in_progress",api_id=actual["id"])
    check_head(api,p)
    due(event,clock(),cadence=p["cadence"])
    local_source(spec,source_root,read_head);api.budget()
    parent=dict(schema_version="audit-weekly-schedule-v1-parent",repository=REPO,run_id=identifier,run_attempt=1,
        source_sha=spec["source_sha"],workflow_ref=env["GITHUB_WORKFLOW_REF"],event=event,actor=deepcopy(OWNER),
        job_id=spec["job_id"],api_job_id=actual["id"],job_started_at=actual["started_at"],workflow_sha256=spec["workflow_sha256"],
        verified_at_utc=utc(clock()).isoformat(),state="AUTHENTICATED_RUNNING_PARENT_CHILD_MUST_VERIFY_COMPLETION_LATER")
    return Proof(dict(schema_version=VERSION+"-parent-proof",registration_sha256=sealed_sha256,run_id=identifier,job_id=spec["job_id"],
        scheduled_parent=parent,readiness=ready,metadata_GETs=deepcopy(api.calls),next_action=RETURN_RULE,
        child_completion_claimed=False,activation_authorized=False),_KEY)


def verify_child(registration_bytes,*,sealed_sha256,root_bytes,event_bytes,env,source_root,metadata_get,clock=now,read_head=git_head):
    """Additive BOT actor proof; original ROOT/head/source guards stay required."""
    at=utc(clock());p=registration(registration_bytes,sealed_sha256=sealed_sha256,at=at);spec=p["producer"]
    require(type(root_bytes) is bytes and 0<len(root_bytes)<=LIMITS["root_bytes"],"BOUNDED_ACTUAL_CHILD_ROOT")
    root=decode(root_bytes);root_sha=sha(root_bytes)
    require(root_bytes==canonical(root) and root.get("source_sha")==spec["source_sha"] and root.get("mode")==MODE
        and root.get("workflow_ref")==REPO+"/"+WORKFLOW+"@refs/heads/"+spec["branch"]
        and root.get("single_writer_group")==GROUP and root.get("code_pins")==spec["code_pins"]
        and root.get("jobs")=={k:spec["jobs"][k] for k in ROLES} and root.get("failure_restorer")==spec["jobs"]["evidence"],
        "UNCHANGED_CURRENT_ROOT_SOURCE_WORKFLOW_AND_JOBS")
    ctx=root.get("effective_epoch",{}).get("controller_context")
    require(type(ctx) is dict and set(ctx)==CONTEXT_KEYS and ctx["schema_version"]==VERSION+"-context"
        and ctx["registration_sha256"]==sealed_sha256 and hashed(ctx["claim_id"])
        and ctx["claim_locator"]==dict(repository=REPO,ref="lab-state",path=claim_path(ctx["claim_id"])),"EXPLICIT_SEALED_CONTROLLER_CONTEXT")
    parent=ctx["scheduled_parent"];ps=p["parent"]
    require(type(parent) is dict and set(parent)==PARENT_DOC_KEYS and parent["schema_version"]=="audit-weekly-schedule-v1-parent"
        and parent["repository"]==REPO and run_id(parent["run_id"]) and type(parent["run_attempt"]) is int and parent["run_attempt"]==1
        and parent["source_sha"]==ps["source_sha"] and parent["workflow_sha256"]==ps["workflow_sha256"]
        and parent["workflow_ref"]==REPO+"/"+WORKFLOW+"@refs/heads/"+ps["branch"] and parent["event"] in ps["actors"]
        and parent["actor"]==OWNER and parent["job_id"]==ps["job_id"] and positive(parent["api_job_id"])
        and parent["state"]=="AUTHENTICATED_RUNNING_PARENT_CHILD_MUST_VERIFY_COMPLETION_LATER","EXACT_SCHEDULED_PARENT_CONTEXT")
    job_id=env.get("GITHUB_JOB");require(job_id in spec["jobs"].values(),"REGISTERED_CURRENT_CHILD_JOB")
    common_env(env,spec,job_id,BOT,event="workflow_dispatch")
    require(env.get("STORE_PERMISSION")=="write" and env.get("AUDIT_WEEKLY_ROOT_GO_SHA256")==root_sha
        and env.get("AUDIT_WEEKLY_ROOT_GO_JSON")==root_bytes.decode(),"CURRENT_CHILD_EXACT_ROOT_ENVIRONMENT")
    event=decode(event_bytes)
    require(event.get("repository",{}).get("full_name")==REPO and event.get("inputs",{}).get("mode")==MODE
        and event["inputs"].get("inference_builder_go_json")==root_bytes.decode()
        and event["inputs"].get("inference_builder_go_sha256")==root_sha,"ACTUAL_CHILD_DISPATCH_ROOT_INPUT_SHA")
    local_source(spec,source_root,read_head)
    identifier=env["GITHUB_RUN_ID"];require(identifier!=parent["run_id"] and identifier!=p["readiness"]["run_id"],"DISTINCT_CURRENT_CHILD_RUN")
    path=claim_path(ctx["claim_id"])
    allowed=_urls(p,(identifier,parent["run_id"],p["readiness"]["run_id"]))|{claim_history(path)}
    api=Metadata(metadata_get,allowed,clock=clock)
    pr=checked_run(api.get(run_url(parent["run_id"])),parent["run_id"],ps,OWNER,event=parent["event"],status="completed")
    pj=job(api.get(jobs_url(parent["run_id"])),parent["run_id"],ps,ps["job_id"],status="completed",api_id=parent["api_job_id"])
    require(utc(pj["started_at"])==utc(parent["job_started_at"])<=utc(parent["verified_at_utc"])<=utc(pj["completed_at"]),
        "COMPLETED_PARENT_ACTUAL_JOB_CLOCKS")
    due(parent["event"],pj["started_at"],cadence=p["cadence"]);workflow(api,ps,ps["job_id"],parent=True,cadence=p["cadence"])
    due(parent["event"],parent["verified_at_utc"],cadence=p["cadence"]);due(parent["event"],root["issued_at_utc"],cadence=p["cadence"])
    cr=checked_run(api.get(run_url(identifier)),identifier,spec,BOT,event="workflow_dispatch",status="in_progress")
    cj=job(api.get(jobs_url(identifier)),identifier,spec,job_id,status="in_progress")
    require(utc(pj["completed_at"])<=utc(pr["updated_at"])<=utc(cj["started_at"])<=at
        and utc(p["registered_at_utc"])<=utc(parent["verified_at_utc"])<=utc(root["issued_at_utc"])
        <utc(root["expires_at_utc"]) and utc(root["issued_at_utc"])<=utc(cj["started_at"])
        and at<utc(root["expires_at_utc"]),"PARENT_FINISHED_BEFORE_CURRENT_CHILD_JOB")
    workflow(api,spec,job_id);check_head(api,p)
    rr,ready=readiness(api,p,before=pj["started_at"])
    history=api.get(claim_history(path),64 << 10)
    require(type(history) is list and len(history)==1 and type(history[0]) is dict and hashed(history[0].get("sha"),40),
        "ORIGINAL_CREATE_ONLY_CLAIM_HISTORY_REQUIRED")
    commit_sha=history[0]["sha"]
    commit_url=API+"/commits/"+commit_sha;body_url=contents_url(path,commit_sha)
    # These two adaptive routes are derived only from the fixed history route's
    # exact SHA; there is no arbitrary allow(), redirect or user URL facility.
    api.allowed=frozenset(set(api.allowed)|{commit_url,body_url})
    commit=api.get(commit_url)
    require(type(commit) is dict and commit.get("sha")==commit_sha and type(commit.get("parents")) is list
        and len(commit["parents"])==1 and hashed(commit["parents"][0].get("sha"),40)
        and type(commit.get("files")) is list and len(commit["files"])==1
        and commit["files"][0].get("filename")==path and commit["files"][0].get("status")=="added"
        and (actor(commit.get("committer"),OWNER) or actor(commit.get("committer"),BOT)),"ACTUAL_ONCE_CLAIM_ADDED_COMMIT")
    claim_raw=content(api,path,commit_sha,cap=16 << 10);claim=decode(claim_raw)
    require(type(claim) is dict and set(claim)==CLAIM_KEYS and claim_raw==canonical(claim)
        and blob_sha(claim_raw)==commit["files"][0].get("sha")
        and claim["schema_version"]==VERSION+"-claim" and claim["repository"]==REPO
        and claim["claim_id"]==ctx["claim_id"] and claim["registration_sha256"]==sealed_sha256
        and claim["parent_run_id"]==parent["run_id"] and claim["parent_api_job_id"]==parent["api_job_id"]
        and type(claim["parent_api_job_id"]) is int and claim["parent_source_sha"]==ps["source_sha"]
        and claim["producer_source_sha"]==spec["source_sha"] and claim["root_go_sha256"]==root_sha
        and utc(root["issued_at_utc"])<=utc(claim["created_at_utc"])<=utc(pj["completed_at"]),
        "ORIGINAL_DURABLE_PARENT_CLAIM_EXACT_ROOT_SHA")
    stable(pr,api.get(run_url(parent["run_id"])))
    stable(cr,api.get(run_url(identifier)))
    check_head(api,p);stable(rr,api.get(run_url(p["readiness"]["run_id"])))
    job(api.get(jobs_url(identifier)),identifier,spec,job_id,status="in_progress",api_id=cj["id"])
    job(api.get(jobs_url(parent["run_id"])),parent["run_id"],ps,ps["job_id"],status="completed",api_id=pj["id"])
    local_source(spec,source_root,read_head);api.budget()
    require(utc(clock())<utc(root["expires_at_utc"]),"ROOT_EXPIRED_DURING_CONTROLLER_VERIFICATION")
    return Proof(dict(schema_version=VERSION+"-current-child-proof",registration_sha256=sealed_sha256,root_go_sha256=root_sha,
        run_id=identifier,job_id=job_id,api_job_id=cj["id"],source_sha=spec["source_sha"],actor=deepcopy(BOT),
        parent_run_id=parent["run_id"],parent_actor=deepcopy(OWNER),parent_api_job_id=pj["id"],parent_completed_at=pj["completed_at"],
        claim_id=ctx["claim_id"],claim_sha256=sha(claim_raw),claim_commit_sha=commit_sha,readiness=ready,
        metadata_GETs=deepcopy(api.calls),old_ROOT_source_head_guards_still_required=True,
        public_release=False,activation_authorized=False,fits=0),_KEY)
