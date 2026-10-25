"""Append-only draft storage v2. Import performs no HTTP/credential/payload I/O.

No credential discovery, implicit retry, release publication, asset deletion or
model deserialization. Actual use requires the separately pinned operation GO.
The old probe's strict404 policy is never changed.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener

from . import private_draft_probe_helpers as probe

REPO = "NickNicky19/NFL-forecasting"
API = "https://api.github.com/repos/" + REPO
UPLOAD = "https://uploads.github.com/repos/" + REPO
ASSET_CAP, TOTAL_CAP, MAX_ASSETS, MAX_PAGES = 8 << 20, 32 << 20, 128, 4
MAX_CALLS, TRANSFER_CAP, META_CAP = 40, 40 << 20, 256 << 10
KINDS = frozenset({"forecast_batch", "outcome_snapshot", "selection_receipt", "model_artifact", "runtime_manifest", "feature_snapshot", "source_snapshot", "identity_snapshot"})
HASH = re.compile(r"[a-f0-9]{64}\Z")
CONFIG = Path(__file__).resolve().parents[1] / "config/private-draft-storage-v2.json"
CONFIG_SHA256 = "b7a802c1f299d61cdbfb260081e71701f56279c76f2025f3468c6a83bc73959b"


class StoreError(Exception):
    def __init__(self, code="STORE_GUARD_STOP"):
        self.code = code
        super().__init__(code)  # No body, URL, path, token or underlying exception.


def canonical(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def positive(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StoreError()
    return value


def parents_safe(path):
    path = Path(path).absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise StoreError("SYMLINK_FORBIDDEN")
    return path


def parent_fd(path):
    """Descriptor walk forbids ancestor symlinks, including replacement races."""
    path=Path(path).absolute()
    if not path.name or ".." in path.parts: raise StoreError("LOCAL_PATH_FORBIDDEN")
    fd=os.open("/",os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for component in path.parts[1:-1]:
            next_fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        return fd,path.name
    except BaseException:
        os.close(fd);raise


def read_local(path, cap):
    path = parents_safe(path)
    directory,name=parent_fd(path)
    try:fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW,dir_fd=directory)
    finally:os.close(directory)
    try:
        info = os.fstat(fd)
        if not __import__("stat").S_ISREG(info.st_mode) or info.st_size > cap:
            raise StoreError("LOCAL_SIZE_OR_TYPE")
        with os.fdopen(os.dup(fd), "rb") as stream:
            body = stream.read(cap + 1)
        if len(body) > cap:
            raise StoreError("LOCAL_SIZE_OR_TYPE")
        return body
    finally:
        os.close(fd)


def create_local(path, body):
    """O_EXCL/no symlinks; partial writes remain evidence, never removed/reused."""
    path = parents_safe(path)
    parent,name=parent_fd(path)
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,dir_fd=parent)
        try:
            with os.fdopen(os.dup(fd), "wb") as stream:
                stream.write(body); stream.flush(); os.fsync(stream.fileno())
        finally:os.close(fd)
        os.fsync(parent)
    finally:
        os.close(parent)


def process_identity():
    # PID plus boot/start identity, without task-directory assumptions.
    raw = Path("/proc/self/stat").read_text().rsplit(") ", 1)[1].split()
    return sha(canonical([os.getpid(), raw[19], Path("/proc/sys/kernel/random/boot_id").read_text().strip()]))


def config_sha():
    digest=sha(read_local(CONFIG, 16384))
    if digest!=CONFIG_SHA256: raise StoreError("CONFIG_CHANGED")
    return digest


def checked_binding(binding):
    keys = {"schema_version", "repository", "runtime_id", "origin_run_id", "release_id", "tag_name",
            "canary_asset_id", "canary_name", "canary_sha256", "canary_bytes", "browser_tag", "config_sha256"}
    if (set(binding) != keys or binding["schema_version"] != "weekly-private-draft-binding-v2"
            or binding["repository"] != REPO or binding["release_id"] == 422575680
            or binding["config_sha256"] != config_sha()
            or not re.fullmatch(r"[a-f0-9]{32}", binding["runtime_id"])
            or not re.fullmatch(r"[1-9][0-9]{0,19}", binding["origin_run_id"])
            or binding["tag_name"] != "weekly-private-runtime-v2-" + binding["runtime_id"]
            or not HASH.fullmatch(binding["canary_sha256"])
            or binding["canary_name"] != "canary-" + binding["canary_sha256"] + ".txt"
            or binding["canary_bytes"] != 117
            or not (re.fullmatch(r"untagged-[a-f0-9]{20}", binding["browser_tag"]) or binding["browser_tag"] == binding["tag_name"])):
        raise StoreError("BINDING_MISMATCH")
    positive(binding["release_id"]); positive(binding["canary_asset_id"])
    return binding


def network(request, timeout):
    # Default ProxyHandler and SSL context preserve inherited proxy/CA settings.
    # No cookie jar, no redirects, no URL-bearing exception escapes.
    try:
        return build_opener(probe.NoRedirect()).open(request, timeout=timeout)
    except HTTPError as response:
        return response


@contextmanager
def exchange_deadline(real):
    if not real:
        yield; return
    before, started = signal.getitimer(signal.ITIMER_REAL), time.monotonic()
    if before[0] <= 0 or before[1] or signal.getsignal(signal.SIGALRM) != signal.SIG_DFL:
        raise StoreError("WALL_GUARD_REQUIRED")
    signal.setitimer(signal.ITIMER_REAL, min(20., before[0]))
    try:
        yield
    finally:
        remaining = before[0] - (time.monotonic() - started)
        signal.setitimer(signal.ITIMER_REAL, max(.001, remaining))
        if remaining <= 0:
            raise StoreError("OPERATION_DEADLINE")


class Client:
    def __init__(self, token, run_id, *, journal, source_sha, transport=None, clock=time.monotonic, process=None, job=None, operation=None):
        if not token or not token.startswith("ghs_") or any(c.isspace() for c in token):
            raise StoreError("AUTOMATIC_TOKEN_REQUIRED")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", str(run_id)):
            raise StoreError()
        if not re.fullmatch(r"[a-f0-9]{40}",source_sha): raise StoreError("SOURCE_IDENTITY_REQUIRED")
        self.token, self.run_id, self.journal = token, str(run_id), parents_safe(journal)
        self.source_sha=source_sha
        if not self.journal.is_dir() or self.journal.stat().st_mode & 0o077:
            raise StoreError("PRIVATE_JOURNAL_REQUIRED")
        self.transport, self.real = transport or network, transport is None
        self.clock, self.started, self.calls, self.transferred = clock, clock(), 0, 0
        self.process = process or process_identity()
        if not HASH.fullmatch(self.process): raise StoreError("PROCESS_IDENTITY_REQUIRED")
        self.started_at=datetime.now(timezone.utc).isoformat();self.operation=operation
        if job is None:
            if transport is None: raise StoreError("ACTIONS_JOB_CONTEXT_REQUIRED")
            job=dict(execution_lane="fictional_injected_transport",workflow_ref=REPO+"/.github/workflows/lab.yml@refs/heads/fictional",workflow_sha=source_sha,job_id="fictional",permission="read" if token=="ghs_READ" else "write",event_name="workflow_dispatch",api_job_id=int(self.process[:8],16)+1,run_authenticated=False)
        self.job=dict(job)
        self.allowed = {API, "https://api.github.com/repos/cli/cli/releases/tags/v2.0.0"}
        self.posts = {}; self.control_asset_id = None; self.binding = None

    def path(self, suffix):
        return API + suffix

    def browser(self):
        b = self.binding
        return "https://github.com/" + REPO + "/releases/download/" + b["browser_tag"] + "/" + b["canary_name"]

    def allow(self, url):
        if not (url.startswith(API+"/releases/") or url.startswith("https://github.com/"+REPO+"/releases/download/")
                or url in {API+"/actions/runs/"+self.run_id,API+"/actions/runs/"+self.run_id+"/jobs?per_page=100&page=1"}):
            raise StoreError("ROUTE_FORBIDDEN")
        self.allowed.add(url); return url

    def authenticate_actions_job(self):
        """Match the running workflow/run/source/job to genuine API metadata.

        Actual workflow must grant actions:read. No local credential/bootstrap
        fallback or fabricated Actions environment is provided.
        """
        base=API+"/actions/runs/"+self.run_id
        run=self.json(self.allow(base));jobs=self.json(self.allow(base+"/jobs?per_page=100&page=1"))
        if (not isinstance(run,dict) or run.get("id")!=int(self.run_id) or run.get("head_sha")!=self.source_sha
                or run.get("event")!="workflow_dispatch" or run.get("run_attempt")!=1 or run.get("status")!="in_progress"
                or run.get("path")!=".github/workflows/lab.yml" or run.get("repository",{}).get("full_name")!=REPO
                or run.get("head_repository",{}).get("full_name")!=REPO or not isinstance(jobs,dict)
                or not isinstance(jobs.get("jobs"),list) or jobs.get("total_count")!=len(jobs["jobs"]) or len(jobs["jobs"])>100):
            raise StoreError("ACTIONS_API_IDENTITY")
        matches=[j for j in jobs["jobs"] if j.get("name")==self.job["job_id"] and j.get("status")=="in_progress" and j.get("run_id")==int(self.run_id) and j.get("head_sha")==self.source_sha]
        if len(matches)!=1: raise StoreError("ACTIONS_API_JOB_IDENTITY")
        self.job.update(api_job_id=positive(matches[0].get("id")),run_authenticated=True)

    def bind(self, binding):
        self.binding = checked_binding(dict(binding))
        b = self.binding
        for suffix in ["/releases/" + str(b["release_id"]), "/releases/assets/" + str(b["canary_asset_id"])]:
            self.allow(self.path(suffix))
        self.allow(self.browser())

    def reserve(self, key, body, *, name=None):
        record = dict(schema_version="weekly-private-POST-reservation-v2", key=key, bytes=len(body), sha256=sha(body), name=name)
        try:
            create_local(self.journal / (sha(key.encode()) + ".reservation.json"), canonical(record))
        except FileExistsError:
            raise StoreError("POST_ALREADY_RESERVED_NO_RETRY") from None

    def reserve_post(self,url,key,body,*,name=None):
        if not (url==API+"/releases" or self.binding and url.startswith(UPLOAD+"/releases/"+str(self.binding["release_id"])+"/assets?name=")):
            raise StoreError("POST_ROUTE_FORBIDDEN")
        self.reserve(key,body,name=name);self.posts[url]=sha(body)

    def request(self, url, *, method="GET", data=None, anonymous=False, octet=False, download=False, cap=META_CAP):
        parts = urlsplit(url)
        public_asset = "https://api.github.com/repos/cli/cli/releases/assets/" + str(self.control_asset_id)
        public_browser = "https://github.com/cli/cli/releases/download/v2.0.0/gh_2.0.0_checksums.txt"
        if (parts.scheme != "https" or parts.username or parts.password or parts.port or parts.fragment or "\\" in url
                or method not in {"GET", "POST"} or (method == "GET" and url not in self.allowed | {public_asset, public_browser})
                or (method == "POST" and url not in self.posts)):
            raise StoreError("ROUTE_FORBIDDEN")
        if method == "POST":
            if self.posts.pop(url)!=sha(data or b""): raise StoreError("POST_RESERVATION_MISMATCH")
        current = url
        for hop in range(3):
            if self.calls >= MAX_CALLS or self.clock() - self.started >= 180:
                raise StoreError("OPERATION_LIMIT")
            headers = {"Accept": "application/octet-stream" if octet else "application/vnd.github+json",
                       "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "weekly-private-draft-store-v2"}
            if not anonymous and (current == API or current.startswith(API + "/") or current.startswith(UPLOAD + "/")):
                headers["Authorization"] = "Bearer " + self.token
            if data is not None:
                if len(data) > ASSET_CAP: raise StoreError("ASSET_CAP")
                headers["Content-Type"] = "application/json" if current.startswith(API + "/") else "application/octet-stream"
            self.calls += 1; self.transferred += len(data or b"")
            if self.transferred > TRANSFER_CAP: raise StoreError("TRANSFER_CAP")
            try:
                with exchange_deadline(self.real):
                    response = self.transport(Request(current, data=data, headers=headers, method=method), min(20., max(.001, 180-(self.clock()-self.started))))
                    with response:
                        status = response.status; observed = {k.lower(): v for k,v in response.headers.items()}
                        length = observed.get("content-length")
                        if length is not None and (not length.isdigit() or int(length) > cap): raise StoreError("RESPONSE_CAP")
                        body = response.read(min(cap + 1, TRANSFER_CAP - self.transferred + 1))
                        self.transferred += len(body)
                        if len(body) > cap or self.transferred > TRANSFER_CAP: raise StoreError("RESPONSE_CAP")
            except (URLError, OSError, TimeoutError, ValueError):
                raise StoreError("TRANSPORT_FAILURE_NO_RETRY") from None
            if status in {301,302,303,307,308} and download:
                location = observed.get("location", ""); target = urlsplit(location)
                if method != "GET" or hop >= 2 or target.scheme != "https" or target.hostname not in probe.CDN_HOSTS or target.username or target.password or target.port or target.fragment:
                    raise StoreError("REDIRECT_FORBIDDEN")
                current, anonymous = location, True
                continue
            return status, observed, body
        raise StoreError("REDIRECT_FORBIDDEN")

    def json(self, url, *, method="GET", data=None, anonymous=False):
        status, headers, body = self.request(url, method=method, data=data, anonymous=anonymous)
        if status != (201 if method == "POST" else 200) or headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers:
            raise StoreError("HTTP_OR_RATE_AMBIGUITY")
        try: return json.loads(body)
        except (ValueError, UnicodeError): raise StoreError("INVALID_METADATA") from None

    def draft(self):
        b = self.binding; d = self.json(self.path("/releases/" + str(b["release_id"])))
        if (not isinstance(d,dict) or d.get("id") != b["release_id"] or d.get("draft") is not True
                or d.get("published_at", "MISSING") is not None or d.get("tag_name") != b["tag_name"]
                or d.get("url") != self.path("/releases/" + str(b["release_id"]))): raise StoreError("DRAFT_CHANGED_STOP")

    def inventory(self):
        b = self.binding; assets=[]
        for page in range(1, MAX_PAGES + 1):
            url=self.allow(self.path("/releases/"+str(b["release_id"])+f"/assets?per_page=100&page={page}"))
            batch=self.json(url)
            if not isinstance(batch,list) or len(batch)>100: raise StoreError("INVALID_INVENTORY")
            assets.extend(batch)
            if len(assets)>MAX_ASSETS: raise StoreError("ASSET_COUNT_CAP")
            if len(batch)<100: break
        else: raise StoreError("PAGINATION_INCOMPLETE")
        ids=set();names=set();total=0
        for a in assets:
            if (not isinstance(a,dict) or isinstance(a.get("size"),bool) or not isinstance(a.get("size"),int) or a["size"]<0
                    or a["size"]>ASSET_CAP or a.get("state")!="uploaded"
                    or not isinstance(a.get("name"),str) or a.get("id") in ids or a["name"] in names): raise StoreError("INVALID_INVENTORY")
            positive(a.get("id"));ids.add(a["id"]);names.add(a["name"]);total+=a["size"]
        # Charge EVERY unknown/orphan asset; ambiguous POST reservations also
        # count unless exact returned name/size/server digest proves membership.
        reservations=[]
        for entry in os.scandir(self.journal):
            if entry.name.endswith(".reservation.json"):
                reservations.append(Path(entry.path))
                if len(reservations)>MAX_ASSETS+1: raise StoreError("RESERVATION_COUNT_CAP")
        pending_slots=0
        for path in reservations:
            q=json.loads(read_local(path,16384))
            if (set(q)!={"schema_version","key","bytes","sha256","name"} or q["schema_version"]!="weekly-private-POST-reservation-v2"
                    or not isinstance(q["key"],str) or isinstance(q["bytes"],bool) or not isinstance(q["bytes"],int)
                    or not 0<q["bytes"]<=ASSET_CAP or not HASH.fullmatch(q["sha256"])
                    or q["name"] is not None and not re.fullmatch(r"[A-Za-z0-9._-]{1,120}",q["name"])): raise StoreError("INVALID_RESERVATION")
            if q["name"] and not any(a["name"]==q["name"] and a["size"]==q["bytes"] and a.get("digest")=="sha256:"+q["sha256"] for a in assets):
                total+=q["bytes"];pending_slots+=1
        self.inventory_slots=len(assets)+pending_slots
        if self.inventory_slots>MAX_ASSETS: raise StoreError("ASSET_COUNT_CAP")
        if total>TOTAL_CAP: raise StoreError("RUNTIME_BYTES_CAP")
        return assets,total

    def upload(self, name, body, *, reuse_completed=False):
        if len(body)>ASSET_CAP: raise StoreError("ASSET_CAP")
        digest=sha(body)
        if name not in {"blob-"+digest+".bin","manifest-"+digest+".json","canary-"+digest+".txt"}: raise StoreError("DIGEST_BOUND_NAME_REQUIRED")
        self.draft();assets,total=self.inventory()
        existing=[a for a in assets if a["name"]==name]
        if existing:
            if not reuse_completed or not name.startswith("blob-") or len(existing)!=1: raise StoreError("APPEND_ONLY_NAME_EXISTS")
            a=self.asset(existing[0],name,len(body),digest)
            if self.read_asset(a["id"],name,len(body),digest)!=body: raise StoreError("REUSE_READBACK_MISMATCH")
            self.draft();return a
        if self.inventory_slots+1>MAX_ASSETS: raise StoreError("ASSET_COUNT_CAP")
        if total+len(body)>TOTAL_CAP: raise StoreError("RUNTIME_BYTES_CAP")
        url=UPLOAD+"/releases/"+str(self.binding["release_id"])+"/assets?name="+quote(name,safe="")
        self.reserve_post(url,"asset:"+name,body,name=name)
        result=self.json(url,method="POST",data=body)
        self.asset(result,name,len(body),sha(body));self.draft()
        return result

    def asset(self, document, name, size, digest):
        positive(document.get("id"))
        if (document.get("name")!=name or document.get("size")!=size or document.get("state")!="uploaded"
                or document.get("digest")!="sha256:"+digest
                or document.get("url")!=self.path("/releases/assets/"+str(document["id"]))): raise StoreError("ASSET_IDENTITY")
        return document

    def read_asset(self, asset_id, name, size, digest):
        assets,_=self.inventory()
        members=[a for a in assets if a["id"]==asset_id]
        if len(members)!=1: raise StoreError("ASSET_NOT_IN_RUNTIME")
        self.asset(members[0],name,size,digest)
        url=self.allow(self.path("/releases/assets/"+str(positive(asset_id))))
        self.asset(self.json(url),name,size,digest)
        status,_,body=self.request(url,octet=True,download=True,cap=ASSET_CAP)
        if status!=200 or len(body)!=size or sha(body)!=digest: raise StoreError("READBACK_MISMATCH")
        return body


def payload_manifest(document, body):
    keys={"schema_version","payload_kind","format","bytes","sha256","source_policy_sha256"}
    if (set(document)!=keys or document["schema_version"]!="weekly-private-payload-v2" or document["payload_kind"] not in KINDS
            or document["format"] not in {"json","gzip","pickle","npz"} or isinstance(document["bytes"],bool)
            or (document["payload_kind"]!="model_artifact" and document["format"] not in {"json","gzip"})
            or document["bytes"]!=len(body) or not 0<len(body)<=ASSET_CAP or document["sha256"]!=sha(body)
            or not HASH.fullmatch(document["source_policy_sha256"])): raise StoreError("PAYLOAD_SCOPE_OR_HASH")
    return document


def initialize(client, runtime_id):
    if not re.fullmatch(r"[a-f0-9]{32}",runtime_id): raise StoreError()
    body=probe.fixture(client.run_id)
    if len(body)!=117: raise StoreError("CANARY_117_BYTES_REQUIRED")
    own=client.json(API)
    if own.get("full_name")!=REPO or own.get("private") is not False: raise StoreError("OWN_REPO_CONTROL")
    tag="weekly-private-runtime-v2-"+runtime_id;url=client.allow(API+"/releases/tags/"+tag)
    status,h,_=client.request(url)
    if status!=404 or h.get("x-ratelimit-remaining")=="0" or "retry-after" in h: raise StoreError("FRESH_DRAFT_REQUIRED")
    data=canonical(dict(tag_name=tag,name="Private runtime v2 "+runtime_id,body="Private runtime boundary canary; no NFL payload authorized.",draft=True,prerelease=True,generate_release_notes=False))
    client.reserve_post(API+"/releases","create:"+runtime_id,data)
    d=client.json(API+"/releases",method="POST",data=data);release=positive(d.get("id"))
    # A provisional binding is private and never returned before final checks.
    digest=sha(body);binding=dict(schema_version="weekly-private-draft-binding-v2",repository=REPO,runtime_id=runtime_id,origin_run_id=client.run_id,release_id=release,tag_name=tag,canary_asset_id=1,canary_name="canary-"+digest+".txt",canary_sha256=digest,canary_bytes=117,browser_tag=tag,config_sha256=config_sha())
    client.bind(binding);client.draft();assets,total=client.inventory()
    if assets or total: raise StoreError("FRESH_DRAFT_NOT_EMPTY")
    a=client.upload(binding["canary_name"],body)
    browser=urlsplit(a.get("browser_download_url",""));prefix="/"+REPO+"/releases/download/"
    if browser.scheme!="https" or browser.netloc!="github.com" or browser.query or browser.fragment or not browser.path.startswith(prefix): raise StoreError("BROWSER_IDENTITY")
    tail=browser.path[len(prefix):].split("/")
    if len(tail)!=2 or tail[1]!=binding["canary_name"]: raise StoreError("BROWSER_IDENTITY")
    binding.update(canary_asset_id=a["id"],browser_tag=tail[0]);client.bind(binding)
    client.read_asset(a["id"],binding["canary_name"],117,digest);client.draft()
    return binding


PHASE_FIELDS={
    "write_pin":{"exact_canary_readback","draft_before_after"},
    "read_boundary":{"before_sha256","all10_denied","controls_passed","routes"},
    "qualified":{"engineering_boundary_v2","strict_v1_unchanged","restricted_upload_authorized","before_sha256","read_sha256","before_process_identity","read_process_identity","before_completed_at_utc","read_completed_at_utc","before_proof","read_proof"},
    "restore":{"exact_readback","payload_sha256","bytes","separate_process","draft_before_after"},
}
PHASE_OPERATION={"write_pin":"pin","read_boundary":"boundary","qualified":"qualify","restore":"restore"}
BASE_PROOF_FIELDS={"schema_version","phase","operation","repository","run_id","run_attempt","started_at_utc","created_at_utc","source_sha","binding_sha256","config_sha256","process_identity","job","HTTP_calls","transfer_bytes"}
JOB_FIELDS={"execution_lane","workflow_ref","workflow_sha","job_id","permission","event_name","api_job_id","run_authenticated"}
ROUTES=("release_metadata","asset_metadata","asset_list","api_octet","browser")
ROUTE_FIELDS={"sequence","principal","route","status","resource_permission_message_exact_match","rate_header_present","rate_remaining_nonzero","retry_after_present","request_failed"}


def utc(value):
    if not isinstance(value,str): raise StoreError("PROOF_CLOCK")
    try: result=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError: raise StoreError("PROOF_CLOCK") from None
    if result.tzinfo is None or result.utcoffset().total_seconds()!=0: raise StoreError("PROOF_CLOCK")
    return result


def validate_routes(records):
    if not isinstance(records,list) or len(records)!=10: raise StoreError("TEN_EXACT_ROUTES_REQUIRED")
    for i,row in enumerate(records):
        route=ROUTES[i%5];anonymous=i>=5 or route=="browser"
        if (not isinstance(row,dict) or set(row)!=ROUTE_FIELDS
                or row["sequence"]!=("anonymous" if i>=5 else "read_only")
                or row["principal"]!=("anonymous" if anonymous else "contents_read") or row["route"]!=route
                or isinstance(row["status"],bool) or not isinstance(row["status"],int)
                or any(type(row[k]) is not bool for k in ROUTE_FIELDS-{"sequence","principal","route","status"})
                or row["request_failed"] or row["retry_after_present"]
                or not row["rate_header_present"] and row["rate_remaining_nonzero"]): raise StoreError("ROUTE_PROOF_INVALID")
        if row["status"]==404:
            if row["rate_header_present"] and not row["rate_remaining_nonzero"]: raise StoreError("RATE_AMBIGUITY")
        elif (row["status"]!=403 or anonymous or not row["resource_permission_message_exact_match"]
                or not row["rate_header_present"] or not row["rate_remaining_nonzero"]): raise StoreError("BOUNDARY_V2_FAILED")


def receipt(client, phase, **extra):
    return dict(schema_version="weekly-private-proof-v2.1",phase=phase,operation=client.operation or PHASE_OPERATION[phase],repository=REPO,run_id=client.run_id,run_attempt=1,
                started_at_utc=client.started_at,created_at_utc=datetime.now(timezone.utc).isoformat(),source_sha=client.source_sha,
                binding_sha256=sha(canonical(client.binding)),config_sha256=config_sha(),process_identity=client.process,job=dict(client.job),HTTP_calls=client.calls,transfer_bytes=client.transferred,**extra)


def pin_canary(client):
    client.draft();b=client.binding
    body=client.read_asset(b["canary_asset_id"],b["canary_name"],117,b["canary_sha256"])
    if body!=probe.fixture(b["origin_run_id"]): raise StoreError("CANARY_MISMATCH")
    client.draft();return receipt(client,"write_pin",exact_canary_readback=True,draft_before_after=True)


def check_proof(client, document, phase, *, same_run=True):
    if not isinstance(document,dict) or set(document)!=BASE_PROOF_FIELDS|PHASE_FIELDS[phase]: raise StoreError("CLOSED_PHASE_PROOF_REQUIRED")
    job=document["job"];permission="read" if phase=="read_boundary" else "write"
    strings=BASE_PROOF_FIELDS-{"run_attempt","job","HTTP_calls","transfer_bytes"}
    if any(type(document[k]) is not str for k in strings): raise StoreError("PROOF_FIELD_TYPES")
    if (document["schema_version"]!="weekly-private-proof-v2.1" or document["phase"]!=phase or document["operation"]!=PHASE_OPERATION[phase]
            or document["repository"]!=REPO or not re.fullmatch(r"[1-9][0-9]{0,19}",str(document["run_id"]))
            or (same_run and document["run_id"]!=client.run_id) or not re.fullmatch(r"[a-f0-9]{40}",str(document["source_sha"]))
            or (same_run and document["source_sha"]!=client.source_sha) or type(document["run_attempt"]) is not int or document["run_attempt"]!=1
            or document["binding_sha256"]!=sha(canonical(client.binding)) or document["config_sha256"]!=config_sha()
            or not isinstance(document["process_identity"],str) or not HASH.fullmatch(document["process_identity"]) or document["process_identity"]==client.process
            or not isinstance(job,dict) or set(job)!=JOB_FIELDS or job["execution_lane"]!=client.job["execution_lane"]
            or any(type(job[k]) is not str for k in JOB_FIELDS-{"api_job_id","run_authenticated"})
            or (same_run and job["workflow_ref"]!=client.job["workflow_ref"])
            or job["permission"]!=permission or job["workflow_sha"]!=document["source_sha"] or job["event_name"]!="workflow_dispatch"
            or not re.fullmatch(re.escape(REPO)+r"/\.github/workflows/lab\.yml@refs/(heads|tags)/[A-Za-z0-9_./-]+",str(job["workflow_ref"]))
            or not re.fullmatch(r"[A-Za-z0-9_-]+",str(job["job_id"])) or type(job["api_job_id"]) is not int or job["api_job_id"]<=0
            or type(job["run_authenticated"]) is not bool or job["run_authenticated"]!=(job["execution_lane"]=="github_actions")
            or type(document["HTTP_calls"]) is not int or not 1<=document["HTTP_calls"]<=MAX_CALLS
            or type(document["transfer_bytes"]) is not int or not 0<document["transfer_bytes"]<=TRANSFER_CAP): raise StoreError("PROOF_BINDING_OR_PROVENANCE")
    if not utc(document["started_at_utc"])<=utc(document["created_at_utc"])<=datetime.now(timezone.utc): raise StoreError("PROOF_CLOCK")
    minimum_calls={"write_pin":5,"read_boundary":15,"qualified":5,"restore":8}[phase]+(2 if job["execution_lane"]=="github_actions" else 0)
    if document["HTTP_calls"]<minimum_calls: raise StoreError("PROOF_OPERATION_INCOMPLETE")
    if phase=="write_pin":
        if document["exact_canary_readback"] is not True or document["draft_before_after"] is not True: raise StoreError("WRITE_PIN_PROOF")
    elif phase=="read_boundary":
        if document["all10_denied"] is not True or document["controls_passed"] is not True or not HASH.fullmatch(str(document["before_sha256"])): raise StoreError("READ_PROOF")
        validate_routes(document["routes"])
    elif phase=="qualified":
        check_proof(client,document["before_proof"],"write_pin",same_run=False)
        check_proof(client,document["read_proof"],"read_boundary",same_run=False)
        before,read=document["before_proof"],document["read_proof"]
        identities=[document["process_identity"],document["before_process_identity"],document["read_process_identity"]]
        if (any(not isinstance(v,str) or not HASH.fullmatch(v) for v in identities) or len(set(identities))!=3
                or document["engineering_boundary_v2"] is not True or document["strict_v1_unchanged"]!="INCONCLUSIVE" or document["restricted_upload_authorized"] is not False
                or any(not HASH.fullmatch(str(document[k])) for k in ["before_sha256","read_sha256"])
                or document["before_sha256"]!=sha(canonical(before)) or document["read_sha256"]!=sha(canonical(read)) or read["before_sha256"]!=document["before_sha256"]
                or before["run_id"]!=document["run_id"] or read["run_id"]!=document["run_id"]
                or before["source_sha"]!=document["source_sha"] or read["source_sha"]!=document["source_sha"]
                or document["before_process_identity"]!=before["process_identity"] or document["read_process_identity"]!=read["process_identity"]
                or len({before["job"]["api_job_id"],read["job"]["api_job_id"],job["api_job_id"]})!=3
                or document["before_completed_at_utc"]!=before["created_at_utc"] or document["read_completed_at_utc"]!=read["created_at_utc"]
                or utc(before["created_at_utc"])>utc(read["started_at_utc"])
                or not utc(document["before_completed_at_utc"])<=utc(document["read_completed_at_utc"])<=utc(document["started_at_utc"])): raise StoreError("QUALIFICATION_PROVENANCE")
    elif phase=="restore":
        if (document["exact_readback"] is not True or document["separate_process"] is not True or document["draft_before_after"] is not True
                or type(document["payload_sha256"]) is not str or not HASH.fullmatch(document["payload_sha256"])
                or type(document["bytes"]) is not int or not 1<=document["bytes"]<=ASSET_CAP): raise StoreError("RESTORE_PROOF_INVALID")


def boundary(client, before):
    check_proof(client,before,"write_pin")
    if utc(before["created_at_utc"])>utc(client.started_at): raise StoreError("PROOF_CAUSAL_CLOCK")
    probe.public_controls(client)
    b=client.binding;api=[client.path("/releases/"+str(b["release_id"])),client.path("/releases/assets/"+str(b["canary_asset_id"])),client.allow(client.path("/releases/"+str(b["release_id"])+"/assets")),client.path("/releases/assets/"+str(b["canary_asset_id"]))]
    records=[]
    for anonymous in [False,True]:
        for index,url in enumerate(api+[client.browser()]):
            anon=anonymous or index==4;status,h,body=client.request(url,anonymous=anon,octet=index==3)
            try:message=json.loads(body).get("message")
            except (ValueError,AttributeError,UnicodeError):message=None
            remaining=h.get("x-ratelimit-remaining","")
            records.append(dict(sequence="anonymous" if anonymous else "read_only",principal="anonymous" if anon else "contents_read",route=ROUTES[index],status=status,
                resource_permission_message_exact_match=message==probe.RESOURCE_PERMISSION_MESSAGE,rate_header_present="x-ratelimit-remaining" in h,
                rate_remaining_nonzero=remaining.isdigit() and int(remaining)>0,retry_after_present="retry-after" in h,request_failed=False))
    validate_routes(records)
    return receipt(client,"read_boundary",before_sha256=sha(canonical(before)),all10_denied=True,controls_passed=True,routes=records)


def qualify(client,before,read):
    check_proof(client,before,"write_pin");check_proof(client,read,"read_boundary")
    if (read["before_sha256"]!=sha(canonical(before)) or len({before["process_identity"],read["process_identity"],client.process})!=3
            or before["job"]["api_job_id"]==read["job"]["api_job_id"] or client.job["api_job_id"] in {before["job"]["api_job_id"],read["job"]["api_job_id"]}
            or not utc(before["created_at_utc"])<=utc(read["started_at_utc"])<=utc(read["created_at_utc"])<=utc(client.started_at)):
        raise StoreError("QUALIFICATION_PROOF")
    pin_canary(client)
    return receipt(client,"qualified",engineering_boundary_v2=True,strict_v1_unchanged="INCONCLUSIVE",restricted_upload_authorized=False,
        before_sha256=sha(canonical(before)),read_sha256=sha(canonical(read)),before_process_identity=before["process_identity"],read_process_identity=read["process_identity"],
        before_completed_at_utc=before["created_at_utc"],read_completed_at_utc=read["created_at_utc"],before_proof=before,read_proof=read)


def append(client,body,manifest,qualification):
    check_proof(client,qualification,"qualified",same_run=False)
    if qualification.get("engineering_boundary_v2") is not True: raise StoreError("UNQUALIFIED_RUNTIME")
    payload_manifest(manifest,body)
    # Exact manifest authorization is enforced by the CLI/producer contract.
    name="blob-"+manifest["sha256"]+".bin";asset=client.upload(name,body,reuse_completed=True)
    entry=dict(schema_version="weekly-private-restore-manifest-v2",payload=manifest,payload_asset_id=asset["id"],payload_name=name,producer_process=client.process,binding_sha256=sha(canonical(client.binding)),writer_run_id=client.run_id)
    encoded=canonical(entry);remote=client.upload("manifest-"+sha(encoded)+".json",encoded)
    return dict(entry=entry,manifest_asset_id=remote["id"],manifest_sha256=sha(encoded),manifest_bytes=len(encoded))


def restore(client,descriptor,destination):
    if not isinstance(descriptor,dict) or set(descriptor)!={"entry","manifest_asset_id","manifest_sha256","manifest_bytes"}: raise StoreError("CLOSED_RESTORE_DESCRIPTOR")
    entry=descriptor["entry"]
    if (not isinstance(entry,dict) or set(entry)!={"schema_version","payload","payload_asset_id","payload_name","producer_process","binding_sha256","writer_run_id"}
            or not isinstance(entry["producer_process"],str) or not HASH.fullmatch(entry["producer_process"])
            or not isinstance(entry["writer_run_id"],str) or not re.fullmatch(r"[1-9][0-9]{0,19}",entry["writer_run_id"])
            or entry.get("schema_version")!="weekly-private-restore-manifest-v2" or entry.get("binding_sha256")!=sha(canonical(client.binding))
            or entry.get("producer_process")==client.process): raise StoreError("SEPARATE_PROCESS_REQUIRED")
    encoded=canonical(entry)
    if sha(encoded)!=descriptor["manifest_sha256"] or len(encoded)!=descriptor["manifest_bytes"]: raise StoreError("RESTORE_MANIFEST_HASH")
    client.draft();saved=client.read_asset(descriptor["manifest_asset_id"],"manifest-"+sha(encoded)+".json",len(encoded),sha(encoded))
    if saved!=encoded: raise StoreError("RESTORE_MANIFEST_HASH")
    p=entry["payload"];body=client.read_asset(entry["payload_asset_id"],entry["payload_name"],p["bytes"],p["sha256"])
    payload_manifest(p,body);client.draft();create_local(destination,body)
    if sha(read_local(destination,ASSET_CAP))!=p["sha256"]: raise StoreError("LOCAL_RESTORE_HASH")
    return receipt(client,"restore",exact_readback=True,payload_sha256=p["sha256"],bytes=len(body),separate_process=True,draft_before_after=True)
