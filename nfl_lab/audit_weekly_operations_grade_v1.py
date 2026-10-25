"""Native same-run operational grading; no serialized execution authority.

The hosted parent owns requests, current authority, source pins and workflow.
No import performs private IO. Every execution authenticates a fresh current
job before opening the archive. Cross-run grading requires a fresh live history
restore and the original private evidence envelope; saved references alone
cannot qualify history or replace original primary assignments.

Native capacity is NOT qualified. Retained cold tests expose MemoryError in
the shared all-row capture loader at 18k candidates/5k selected, and in the
shared 64MiB gzip unpack at checkpoint append even for the small fixture.
These failures must remain release blockers; no cap, row or validator bypass
is implemented here. The parent owns any separately reviewed shared fix.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import resource
import signal
import time

VERSION="audit-weekly-operations-grade-v1"
ROOT=Path(__file__).resolve().parents[1]
PHASES=("operations-grade-write","operations-grade-read")
FILES=("nfl_lab/audit_weekly_operations_grade_v1.py","tools/audit_weekly_operations_grade_v1.py",
    "tests/test_audit_weekly_operations_grade_v1.py","tests/test_audit_weekly_operations_grade_scale_v1.py")
LIMITS=dict(wall_seconds=180,CPU_seconds=120,address_space_bytes=512 << 20,RSS_bytes=512 << 20,
    global_bytes=512 << 20,request_bytes=512 << 10,archive_metadata_bytes=4 << 20,
    checkpoint_bytes=8 << 20,handoff_bytes=16 << 10,HTTP_per_client=40,fits=0,model_decodes=0,retries=0)
REQUEST_KEYS={"schema_version","phase","code_pins","limits","cache","state_root","output","inputs"}
INPUT_KEYS={PHASES[0]:{"archive_restored","previous_snapshot"},PHASES[1]:{"archive_restored","checkpoint_handoff"}}
EPOCH_ROLES={"epoch","epoch_registration","original_choice","origin_witness","original_slate","original_catalog","original_policy"}
OPS_ROLES={"ops_population","ops_roles","ops_schedule"}
_KEY=object()


class GradeBridgeError(ValueError):pass
def require(ok,code):
    if not ok:raise GradeBridgeError(code)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def native_envelope():
    for kind,cap in ((resource.RLIMIT_CPU,120),(resource.RLIMIT_AS,512 << 20)):
        soft,hard=resource.getrlimit(kind)
        require(type(soft) is int and type(hard) is int and 0<soft<=hard<=cap,"OPERATIONS_GRADE_NATIVE_CPU_AS_REQUIRED")
    remaining,interval=signal.getitimer(signal.ITIMER_REAL)
    require(signal.getsignal(signal.SIGALRM)==signal.SIG_DFL and 0<remaining<=180 and interval==0,
        "OPERATIONS_GRADE_NATIVE_WALL_REQUIRED")


def validate_request(p,phase):
    require(phase in PHASES and type(p) is dict and set(p)==REQUEST_KEYS and p["schema_version"]==VERSION+"-request"
        and p["phase"]==phase and canonical(p["limits"])==canonical(LIMITS)
        and type(p["inputs"]) is dict and set(p["inputs"])==INPUT_KEYS[phase],"CLOSED_OPERATIONS_GRADE_REQUEST")
    cache,state,output=(Path(p[k]) for k in ("cache","state_root","output"))
    require(all(x.is_absolute() and ".." not in x.parts for x in (cache,state,output))
        and cache.name=="cache" and state==cache.parent/"state" and output==cache.parent/phase,"CONFINED_OPERATIONS_GRADE_PATHS")
    ref=p["inputs"]["archive_restored"]
    require(type(ref) is dict and set(ref)=={"path","bytes","sha256"} and type(ref["path"]) is str
        and Path(ref["path"]).is_absolute() and ".." not in Path(ref["path"]).parts
        and Path(ref["path"]).is_relative_to(cache.parent) and Path(ref["path"]).name=="RESTORED.json"
        and type(ref["bytes"]) is int and 0<ref["bytes"]<=LIMITS["archive_metadata_bytes"]
        and type(ref["sha256"]) is str and len(ref["sha256"])==64 and all(c in "0123456789abcdef" for c in ref["sha256"]),
        "ACTUAL_CURRENT_ARCHIVE_RESTORED_REFERENCE_REQUIRED")
    if phase==PHASES[0]:
        require(p["inputs"]["previous_snapshot"] is None,"LIVE_CROSS_RUN_HISTORY_RESTORE_REQUIRED")
    else:
        from . import audit_weekly_grade_checkpoint_v1 as checkpoint
        require(len(canonical(p["inputs"]["checkpoint_handoff"]))<=LIMITS["handoff_bytes"],"BOUNDED_OPERATIONS_GRADE_HANDOFF")
        checkpoint.safe_handoff(p["inputs"]["checkpoint_handoff"])
    return p


class Authenticated:
    def __init__(self,p,a,go,env,client,proof,key):
        require(key is _KEY,"LIVE_OPERATIONS_GRADE_CONTEXT_REQUIRED")
        self.request,self.authority,self.go=map(deepcopy,(p,a,go));self.env=env
        self.client,self.proof=client,proof;self.root_bytes=env.get("AUDIT_WEEKLY_ROOT_GO_JSON","").encode();self.root_sha256=a["owner_root_go_sha256"]
        from . import gha_private_checkpoint as cp,private_draft_store as store
        self.identity=deepcopy(cp.client_identity(client));self.process=store.process_identity()
        self._sha=digest(dict(request=p,authority=a,go=go));self.wall,self.cpu=time.monotonic(),time.process_time()
    def verify(self):
        native_envelope()
        from . import state,audit_weekly_operations_authority_v1 as authority,gha_private_checkpoint as cp,private_draft_store as store
        require(self._sha==digest(dict(request=self.request,authority=self.authority,go=self.go))
            and time.monotonic()-self.wall<=180 and time.process_time()-self.cpu<=120
            and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=512 << 20
            and state.utc(self.authority["issued_at_utc"])<=state.now_utc()<state.utc(self.authority["expires_at_utc"]),
            "OPERATIONS_GRADE_CONTEXT_OR_BUDGET_CHANGED")
        require(self.identity==cp.client_identity(self.client) and self.process==store.process_identity()
            and self.actual_run_sha256==digest(self.actual_run),"OPERATIONS_GRADE_PROCESS_OR_CURRENT_IDENTITY_CHANGED")
        authority._verify(self.proof,self.env,self.root_bytes)
        self.shared.verify()
        authority.authorize_client_actor(self.client,self.actual_run)
        return self
    def __reduce__(self):raise GradeBridgeError("OPERATIONS_GRADE_CONTEXT_CANNOT_BE_SERIALIZED")


def guard(args,env,*,transport=None):
    native_envelope()
    require(args.phase in PHASES,"CLOSED_OPERATIONS_GRADE_PHASE")
    from . import audit_weekly_hosted_v1 as hosted,audit_weekly_operations_worker_v1 as shared_guard
    from . import private_draft_store as store
    raw=env.get("AUDIT_WEEKLY_ROOT_GO_JSON","").encode()
    shared=shared_guard.authenticate_child(args,env,phase=args.phase,transport=transport)
    p,a,go=shared.request,shared.authority,shared.go
    validate_request(p,args.phase)
    from . import audit_weekly_grade_history_v1 as history
    require(go["operation"]=="RECURRING_CAPTURE" and p["code_pins"]==go["code_pins"]==hosted.pins()
        and all(name in p["code_pins"] for name in FILES+history.FILES) and store.canonical(go)==raw,
        "SEALED_OPERATIONS_GRADE_SOURCE_INVENTORY")
    client=shared.client;client.bind(go["qualified_runtime"]["binding"])
    require(client.job["api_job_id"]==a["api_job_id"] and client.run_id==a["run_id"]
        and client.source_sha==a["source_sha"] and store.sha(raw)==a["owner_root_go_sha256"],"ACTUAL_OPERATIONS_GRADE_API_JOB")
    context=Authenticated(p,a,go,env,client,shared.proof,_KEY);context.shared=shared
    context.actual_run=deepcopy(shared.actual_run);context.actual_run_sha256=digest(context.actual_run)
    # The base metadata client deliberately forbids other runs. Only the
    # qualified archive client can recheck this exact runtime's qualifier API.
    # It remains GET-only and inherits the same live current-job proof.
    context.client=_client(context,"metadata",transport,readonly=True)
    return context.verify()


def _client(context,operation,transport,*,readonly=False):
    from . import audit_weekly_archive_v1 as archive,audit_weekly_operations_authority_v1 as authority
    context.verify();base=context.client
    c=archive.Client(context.env.get("GITHUB_TOKEN"),base.run_id,journal=base.journal,source_sha=base.source_sha,
        job=deepcopy(base.job),operation=operation,qualification=context.go["qualified_runtime"]["qualification"],readonly=readonly,transport=transport)
    c.authenticate_actions_job();c.bind(base.binding);authority.attach(c,context.proof,context.env,context.root_bytes)
    require(c.job["api_job_id"]==base.job["api_job_id"],"SAME_ACTUAL_GRADE_WORKER_JOB")
    return c


def _archive(context,storage,clock):
    from . import audit_weekly_archive_v1 as archive,private_draft_store as store,gha_private_checkpoint as cp
    from . import weekly_durable_acceptance as acceptance,state
    context.verify();ref=context.request["inputs"]["archive_restored"]
    restored=archive.read_owned(storage,ref,LIMITS["archive_metadata_bytes"])
    h=restored["archive"];archive.safe_handoff(h)
    write=context.request["phase"]==PHASES[0];role="restore" if write else "consume"
    current=acceptance.identity(restored["current"]);actual=cp.client_identity(context.client)
    require(restored["schema_version"]==archive.VERSION+"-restored"
        and restored["state"]==("PRIVATE_CAPTURE_RESTORED" if write else "PRIVATE_CAPTURE_EXPORT_INPUTS_VERIFIED")
        and restored["captured_bundle_hashes_restored"] is restored["replay_ready"] is True
        and restored["scope_qualified_for_publication"] is restored["public_export_authorized"] is restored["successful_forecast"] is False
        and h["archive_state"]=="COMPLETE_CAPTURE" and h["root_go_sha256"]==context.root_sha256
        and h["jobs"]==context.go["jobs"] and h["source_sha"]==context.client.source_sha and h["run_id"]==context.client.run_id
        and h["runtime_binding"]==context.client.binding and current["job_id"]==h["jobs"][role]
        and all(current[k]==actual[k] for k in ("repository","run_id","run_attempt","source_sha","workflow_ref","job_id","api_job_id")),
        "ACTUAL_COMPLETE_CURRENT_JOB_ARCHIVE_RESTORATION")
    descriptor=h["index_descriptor"];entry=cp.descriptor_meta(descriptor,archive.INDEX_CAP)
    path=Path(ref["path"]).parent/"owned-downloads/index.gz"
    r=storage.validate_reference(path,entry["payload"]["sha256"]);index_ref={k:r[k] for k in ("path","bytes","sha256")}
    require(r["bytes"]==entry["payload"]["bytes"],"EXACT_CURRENT_ARCHIVE_INDEX_BYTES")
    index=archive.check_index(archive.unpack(archive.read_owned(storage,index_ref,archive.INDEX_CAP,raw=True),archive.INDEX_PLAIN_CAP),h)
    originals={f["logical_path"]:f for f in index["files"]};aliases=restored["aliases"]
    require(set(aliases)==set(originals) and all((aliases[n]["bytes"],aliases[n]["sha256"])==(f["bytes"],f["sha256"]) for n,f in originals.items())
        and restored["files_sha256"]==h["files_sha256"] and restored["index_sha256"]==entry["payload"]["sha256"]
        and restored["producer_proof"]==index["producer_proof"],"FULL_CURRENT_ARCHIVE_INDEX_AND_ALIAS_CENSUS")
    archive.validate_owned_references(storage,{r["path"]:r["sha256"] for r in aliases.values()})
    jobs=archive.jobs_for(context.client);producer_job=archive.predecessor(context.client,h["producer"],jobs)
    archive.authenticate_qualification(context.client,context.go["qualified_runtime"],context.go["pending_census"])
    require(index["qualification_sha256"]==digest(context.go["qualified_runtime"]["qualification"])
        and state.utc(producer_job["started_at"])<=state.utc(index["created_at"])<=state.utc(producer_job["completed_at"]),
        "EXACT_QUALIFIED_ARCHIVE_PRODUCER_CLOCK")
    expected=[(entry["payload"]["bytes"],entry["payload"]["sha256"])]+[(g["bytes"],g["sha256"]) for g in index["groups"]]
    witness=restored["restorer_witness"]
    require(witness["schema_version"]==archive.VERSION+"-witness" and witness["index_sha256"]==restored["index_sha256"]
        and witness["files_sha256"]==h["files_sha256"] and witness["producer_proof_sha256"]==state.digest(index["producer_proof"])
        and witness["validation"]==restored["validation"] and witness["archive_state"]=="COMPLETE_CAPTURE"
        and witness["public_export_authorized"] is witness["successful_forecast"] is False
        and state.utc(witness["actual_completed_at"])<=state.utc(clock()),
        "EXACT_CURRENT_ARCHIVE_READER_WITNESS")
    w=cp.descriptor_meta(restored["witness_descriptor"],archive.WITNESS_CAP)
    witness_reader=acceptance.identity(witness["restorer"])
    require(witness_reader["job_id"]==h["jobs"]["restore"]
        and all(witness_reader[k]==current[k] for k in ("repository","run_id","run_attempt","source_sha","workflow_ref"))
        and w["producer_process"]==witness_reader["process_identity"] and w["writer_run_id"]==h["run_id"]
        and w["binding_sha256"]==digest(h["runtime_binding"]),"EXACT_ORIGINAL_READER_WITNESS_DESCRIPTOR")
    if not write:
        reader_job=archive.predecessor(context.client,witness_reader,jobs)
        witness_path=Path(ref["path"]).parent/"owned-downloads/reader-witness.gz"
        r=storage.validate_reference(witness_path,w["payload"]["sha256"])
        require(r["bytes"]==w["payload"]["bytes"],"EXACT_DOWNLOADED_ORIGINAL_READER_WITNESS")
        original=archive.unpack(archive.read_owned(storage,{k:r[k] for k in ("path","bytes","sha256")},archive.WITNESS_CAP,raw=True),archive.WITNESS_CAP)
        require(original==witness and state.utc(reader_job["started_at"])<=state.utc(witness["actual_completed_at"])
            <=state.utc(reader_job["completed_at"]),"EXACT_DOWNLOADED_ORIGINAL_READER_WITNESS")
        expected=[(w["payload"]["bytes"],w["payload"]["sha256"])]+expected
        require(restored["exporter_proofs"]==restored["restore_proofs"],"COMPLETE_CURRENT_EXPORTER_PROOF_CENSUS")
    else:
        require(witness["restorer"]==current and witness["proofs"]==restored["restore_proofs"],"EXACT_ACTUAL_CURRENT_READER_PROOF_COHORT")
        body=gzip.compress(store.canonical(witness),mtime=0)
        require(len(body)==w["payload"]["bytes"] and store.sha(body)==w["payload"]["sha256"],"EXACT_APPENDED_CURRENT_READER_WITNESS")
    original_expected=[(entry["payload"]["bytes"],entry["payload"]["sha256"])]+[(g["bytes"],g["sha256"]) for g in index["groups"]]
    require([(p["bytes"],p["payload_sha256"]) for p in witness["proofs"]]==original_expected,"ALL_ORIGINAL_ARCHIVE_READER_PROOFS")
    for proof in witness["proofs"]:
        store.check_proof(context.client,proof,"restore")
        require(acceptance.restored_identity(proof)==witness_reader
            and state.utc(proof["created_at_utc"])<=state.utc(witness["actual_completed_at"]),"EXACT_ORIGINAL_ARCHIVE_READER_COHORT")
    proofs=restored["restore_proofs"]
    require([(p["bytes"],p["payload_sha256"]) for p in proofs]==expected,"ALL_CURRENT_ARCHIVE_NATIVE_PROOFS")
    for p in proofs:
        store.check_proof(context.client,p,"restore")
        require(acceptance.restored_identity(p)==current and state.utc(p["created_at_utc"])<=state.utc(clock()),"ACTUAL_CURRENT_ARCHIVE_PROOF_IDENTITY")
    require(set(EPOCH_ROLES|OPS_ROLES)<={n.removeprefix("context/").removesuffix(".json") for n in aliases if n.startswith("context/")},
        "REGISTERED_OPERATIONAL_CONTEXT_MISSING_NO_POSTHOC_POPULATION")
    context.verify()
    return restored,index


def _epoch(restored,storage,clock):
    from . import audit_weekly_archive_v1 as archive,audit_weekly_epoch_v1 as epoch,private_draft_store as store,state
    aliases=restored["aliases"]
    def read(role,raw=False):return archive.read_owned(storage,aliases["context/"+role+".json"],4 << 20 if role=="origin_witness" else epoch.CAP,raw=raw)
    docs={r:read(r,r=="original_choice") for r in EPOCH_ROLES};history=docs["epoch"]["original"]["history_binding"]
    e=epoch.restore_epoch(docs["epoch"],docs["original_choice"],docs["origin_witness"],docs["original_slate"],
        docs["original_catalog"],docs["original_policy"],history_binding=history,now=clock())
    registered=epoch.bind_registration(e,docs["epoch_registration"],now=clock())
    # A resumed epoch retains its ORIGINAL owner registration. Its archive is
    # authenticated to the current Root separately; never re-register history
    # or substitute today's Root for the original prevalue registration.
    choice_doc=archive.read_owned(storage,aliases["runtime/WEEKLY_CHOICE.json"],epoch.CAP)
    require(aliases["runtime/WEEKLY_CHOICE.json"]["sha256"]==aliases["prepared/choice.json"]["sha256"],"EXACT_ARCHIVED_FULL_CHOICE")
    choice=epoch.EpochChoice(choice_doc,state.digest(choice_doc));choice.verify(registered,clock())
    return registered,choice


def _replay(restored,registered,storage):
    """Hash-only projection of the authenticated producer's models-only receipt.

    No path relocation, manifest rewrite, model decode or new model proof is
    performed. The resulting union must equal the prevalue archived catalog.
    """
    from . import audit_weekly_archive_v1 as archive,audit_weekly_epoch_v1 as epoch,state
    aliases=restored["aliases"];models=archive.read_owned(storage,aliases["context/retained_models.json"],4 << 20)
    from .audit_weekly_resume_v1 import MODEL_KEYS
    require(set(models)==MODEL_KEYS and models["model_pairs"]==len(models["models"])==18 and models["files"]==38
        and models["fits"]==0 and models["current_loader_replay"] is models["model_artifact_durability"] is True
        and models["public_release"] is False and models["current_go_sha256"]==restored["archive"]["root_go_sha256"]
        and models["current"]["run_id"]==restored["archive"]["run_id"] and models["current"]["source_sha"]==restored["archive"]["source_sha"]
        and models["current"]["api_job_id"]==restored["archive"]["producer"]["api_job_id"],"ARCHIVED_PRODUCER_MODELS_ONLY_RECEIPT")
    replay=epoch._replay(models["origin"]["replay_catalog"])
    for slot,ref in zip(replay["slots"],models["models"]):slot["manifest_sha256"]=ref["sha256"]
    replay.update(source_sha=models["current"]["source_sha"],run_id=models["current"]["run_id"]);epoch._replay(replay)
    catalog=archive.read_owned(storage,aliases["runtime/ARTIFACT_CATALOG.json"],epoch.CAP)
    require(epoch.artifact_catalog(registered.epoch,replay)==catalog,"EXACT_PREVALUE_ARCHIVED_ARTIFACT_UNION")
    return replay


def _exact(context,kind,document,clock):
    from . import state
    expected=state.digest(document)
    def authenticate(request):
        context.verify()
        from . import state,audit_weekly_grade_v1 as grade
        return type(request) is dict and set(request)=={"schema_version","kind","inputs_sha256","at"} \
            and request["schema_version"]==grade.VERSION+"-authentication-request" and request["kind"]==kind \
            and request["inputs_sha256"]==expected and state.utc(request["at"])<=state.utc(clock())
    return authenticate


class E7Fetch:
    """Live fetch evidence, minted only by this executing guarded worker."""
    def __init__(self,context,storage,request,clock,fetch=None):
        from . import live,state,audit_weekly_provider_v1 as provider
        self.context,self.storage,self.request,self.clock=context,storage,deepcopy(request),clock
        body=state.canonical(request)
        require(0<len(body)<=provider.LIMITS["request_bytes"],"BOUNDED_REGISTERED_E7_REQUEST")
        self.request_bytes=len(body);self.request_sha256=hashlib.sha256(body).hexdigest()
        self.fetch=fetch or live.fetch;self.seen={};self.authorized_ref=None
    def _request_matches(self,ref):
        # Collector wrote the exact canonical live request. Validate its full
        # owned bytes/hash without a second JSON graph or cap-sized read buffer.
        if type(ref) is not dict or set(ref)!={"path","bytes","sha256"} or type(ref["bytes"]) is not int \
            or ref["bytes"]!=self.request_bytes or ref["sha256"]!=self.request_sha256:return False
        actual=self.storage.validate_reference(ref["path"],ref["sha256"])
        return {k:actual[k] for k in ("path","bytes","sha256")}==ref
    def __call__(self,cache,name,url,**kwargs):
        self.context.verify()
        from . import state,private_draft_store as store
        allowed={}
        for g in self.request["games"]:
            y,w=g["season"],g["week"]
            allowed[f"schedule-{y}-{w}"]=f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={w}&dates={y}"
            allowed[f"statistics-{y}-{w}"]=f"https://api.sleeper.app/stats/nfl/{y}/{w}?season_type=regular"
        require(self.authorized_ref is not None and state.digest(self.request)==self.request_sha256
            and allowed.get(name)==url and name not in self.seen and Path(cache)==self.storage.cache
            and kwargs.get("storage") is self.storage,"EXACT_ONE_ATTEMPT_REGISTERED_E7_REQUEST")
        self.seen[name]=None
        began=state.utc(self.clock());parsed,receipt=self.fetch(cache,name,url,**kwargs);ended=state.utc(self.clock())
        path=self.storage.live_root/kwargs["day"]/(name+".json");meta=path.with_name(path.name+".receipt.json")
        body=self.storage.validate_reference(path,receipt["sha256"]);native=self.storage.validate_reference(meta)
        require(receipt["status"]=="acquired" and receipt["bytes"]==body["bytes"]
            and began<=state.utc(receipt["retrieved_utc"])<=ended,"ACTUAL_E7_NATIVE_FETCH_RECEIPT")
        self.seen[name]=dict(url=url,body={k:body[k] for k in ("path","bytes","sha256")},native_receipt={k:native[k] for k in ("path","bytes","sha256")},
            actual_started_at=began.isoformat(),actual_completed_at=ended.isoformat())
        return parsed,receipt
    def authenticate(self,request):
        self.context.verify()
        from . import audit_weekly_archive_v1 as archive,audit_weekly_provider_v1 as provider,state
        if type(request) is not dict or set(request)!={"schema_version","kind","inputs","inputs_sha256","at"} \
            or request["schema_version"]!=provider.VERSION+"-authentication-request" \
            or type(request["inputs"]) is not dict or state.utc(request["at"])>state.utc(self.clock()):return False
        require(request["inputs_sha256"]==state.digest(request["inputs"]) and state.digest(self.request)==self.request_sha256,"EXACT_E7_CALLBACK_DIGEST")
        x=request["inputs"];kind=request["kind"]
        if kind=="AUTHORIZE_REGISTERED_REQUEST":
            if self.authorized_ref is not None or x.get("source_policy_sha256")!=self.request["source_policy_sha256"] \
                or x.get("limits")!=provider.LIMITS:return False
            if not self._request_matches(x["request"]):return False
            self.authorized_ref=deepcopy(x["request"]);return True
        if self.authorized_ref is None or x.get("request")!=self.authorized_ref:return False
        if kind=="AUTHENTICATE_SOURCE_BODY":
            seen=self.seen.get(f"{x['kind']}-{x['season']}-{x['week']}")
            return seen is not None and x["url"]==seen["url"] and x["body"]["sha256"]==seen["body"]["sha256"] \
                and x["body"]["bytes"]==seen["body"]["bytes"] and x["native_receipt"]["bytes"]==seen["native_receipt"]["bytes"] \
                and x["native_receipt"]["sha256"]==seen["native_receipt"]["sha256"] \
                and state.utc(seen["actual_started_at"])<=state.utc(x["observed_at"])<=state.utc(seen["actual_completed_at"])
        if kind=="COMPLETE_PROVIDER_OBSERVATIONS":
            schedules={f"schedule-{g['season']}-{g['week']}" for g in self.request["games"]}
            if not schedules<=set(self.seen) or any(s is None for s in self.seen.values()):return False
            expected=sorted((s[k]["bytes"],s[k]["sha256"]) for s in self.seen.values() for k in ("body","native_receipt"))
            return self._request_matches(x["request"]) \
                and sorted((r["bytes"],r["sha256"]) for r in x["sources"])==expected \
                and x["fits"]==x["searches"]==0 and x["public_release"] is False
        return False


def _checkpoint_auth(context,clock):
    """Bind each typed callback to the preceding live native operation."""
    from . import audit_weekly_grade_checkpoint_v1 as checkpoint,gha_private_checkpoint as cp
    from . import audit_weekly_grade_v1 as grade,audit_weekly_archive_v1 as archive,state
    append_scope=restore_scope=native_scope=None
    snapshot_restored=False
    def authenticate(request):
        nonlocal append_scope,restore_scope,native_scope,snapshot_restored
        context.verify()
        if type(request) is not dict:return False
        kind=request.get("kind","")
        keys={"schema_version","kind","inputs_sha256","at"}
        if set(request) not in (keys,keys|{"inputs"}) or state.utc(request["at"])>state.utc(clock()):return False
        if request.get("schema_version")==checkpoint.VERSION+"-authentication-request":
            x=request.get("inputs")
            if type(x) is not dict or request["inputs_sha256"]!=state.digest(x):return False
            root=x.get("handoff",{}).get("current_root_go_sha256") if kind=="CHECKPOINT_APPEND_NATIVE_HANDOFF" else x.get("current_root_go_sha256")
            if root!=context.root_sha256:return False
            identity=cp.client_identity(context.checkpoint_client)
            if kind=="CHECKPOINT_APPEND_CURRENT_ROOT":
                if context.request["phase"]!=PHASES[0] or append_scope is not None:return False
                context.snapshot.verify()
                expected=checkpoint._binding_context(context.root_sha256,context.go["qualified_runtime"],context.snapshot.sha256,context.snapshot.binding["sha256"])
                if any(x.get(k)!=v for k,v in expected.items()) or x.get("producer")!=identity:return False
                append_scope=deepcopy(x);return True
            if kind=="CHECKPOINT_APPEND_NATIVE_HANDOFF":
                if append_scope is None:return False
                handoff=x["handoff"];checkpoint.safe_handoff(handoff)
                return handoff["snapshot_sha256"]==context.snapshot.sha256 and handoff["body_sha256"]==context.snapshot.binding["sha256"] \
                    and handoff["producer"]==identity and handoff["qualified_package_sha256"]==append_scope["qualified_package_sha256"] \
                    and handoff["epoch_sha256"]==context.registered.epoch.sha256 and x["handoff_sha256"]==digest(handoff)
            if context.request["phase"]!=PHASES[1]:return False
            handoff=context.request["inputs"]["checkpoint_handoff"]
            if x.get("handoff")!=handoff or x.get("handoff_sha256")!=digest(handoff) or x.get("reader")!=identity:return False
            if kind=="CHECKPOINT_RESTORE_CURRENT_ROOT_AND_ORIGINAL_HANDOFF":
                if restore_scope is not None:return False
                restore_scope=deepcopy(x);return True
            if kind=="CHECKPOINT_NATIVE_RESTORED_BODY":
                if restore_scope is None or native_scope is not None or any(x.get(k)!=v for k,v in restore_scope.items()):return False
                proof=x["native_restore_proof"]
                if x.get("restored_binding")!=context.checkpoint_binding or proof["payload_sha256"]!=handoff["body_sha256"] \
                    or proof["bytes"]!=handoff["body_bytes"] or proof["process_identity"]!=identity["process_identity"] \
                    or proof["job"]!=context.checkpoint_client.job:return False
                native_scope=deepcopy(x);return True
            return False
        if request.get("schema_version")!=grade.VERSION+"-authentication-request" or set(request)!=keys or native_scope is None:return False
        if kind=="QUALIFIED_PREVIOUS_GRADING_SNAPSHOT":
            snapshot_restored=request["inputs_sha256"]==state.digest(dict(binding=native_scope["restored_binding"],epoch_sha256=context.registered.epoch.sha256))
            return snapshot_restored
        if kind=="FRESH_READER_GRADING_DURABILITY" and snapshot_restored:
            handoff=context.request["inputs"]["checkpoint_handoff"]
            body=archive.read_owned(context.storage,cp.binding(context.checkpoint_proof_path),256 << 10)
            expected_body=dict(schema_version=checkpoint.VERSION+"-fresh-reader-native-evidence",
                context={k:v for k,v in native_scope.items() if k not in {"native_restore_proof","restored_binding"}},
                native_restore_proof=native_scope["native_restore_proof"],restored_binding=native_scope["restored_binding"],known_by_at=body["known_by_at"])
            if body!=expected_body or not state.utc(body["native_restore_proof"]["created_at_utc"])<=state.utc(body["known_by_at"])<=state.utc(clock()):return False
            expected=dict(schema_version=grade.VERSION+"-durability",snapshot_sha256=handoff["snapshot_sha256"],
                restored_body_sha256=handoff["body_sha256"],known_by_at=body["known_by_at"],producer=handoff["producer"],
                reader=cp.client_identity(context.checkpoint_client),proof_sha256=state.digest(body))
            return request["inputs_sha256"]==state.digest(expected)
        return False
    return authenticate


def _same_capture(restored,registered,choice,durable,storage,*,capture_id=None):
    """Fresh readback must describe this exact independently restored archive."""
    from . import audit_weekly_archive_v1 as archive,audit_weekly_provider_v1 as provider
    captures=durable.document["captures"]
    if capture_id is not None:captures=[c for c in captures if c["capture_id"]==capture_id]
    require(len(captures)==1,"ONE_EXACT_SAME_RUN_GRADING_CAPTURE")
    capture=captures[0];aliases=restored["aliases"]
    read=lambda role:archive.read_owned(storage,aliases["context/"+role+".json"],4 << 20)
    require(capture["epoch_sha256"]==registered.epoch.sha256 and capture["choice"]==choice.document
        and capture["archive_index_sha256"]==restored["index_sha256"]
        and capture["population"]==read("ops_population") and capture["roles"]==read("ops_roles")
        and capture["schedule"]==[{k:r[k] for k in provider.GAME_KEYS} for r in read("ops_schedule")]
        and {n:(r["bytes"],r["sha256"]) for n,r in capture["aliases"].items()}
            =={n:(r["bytes"],r["sha256"]) for n,r in aliases.items()},"EXACT_GRADED_AND_FRESH_RESTORED_CAPTURE")


def _previous(context,restored,storage,transport):
    from . import audit_weekly_grade_history_v1 as history
    if context.go.get("effective_epoch") is None or history.previous_checkpoint(context.go) is None:return None
    aliases=restored["aliases"]
    names=("context/ops_previous_checkpoint_sidecar.json","context/ops_previous_public_receipt.json")
    require(all(name in aliases for name in names),"EXACT_ARCHIVED_HISTORY_SIDECAR_AND_RECEIPT_REQUIRED")
    return history.restore_previous(context.shared,storage,aliases[names[0]],aliases[names[1]],transport=transport)


def _retains(previous,durable):
    from . import audit_weekly_grade_v1 as grade
    previous.verify();durable.verify()
    old=previous.durable.document;new=durable.document
    captures={c["capture_id"]:c for c in new["captures"]}
    require(all(c["capture_id"] in captures and grade._digest(c)==grade._digest(captures[c["capture_id"]]) for c in old["captures"])
        and all(new[k].get(n)==v for k in ("known_versions","known_weeks") for n,v in old[k].items()),
        "LOSSLESS_ORIGINAL_PRIMARY_CAPTURES_AND_DURABILITY_CLOCKS")
    for key in ("versions","week_revisions","collector_records","finality_records"):
        retained={grade._digest(row) for row in new[key]}
        require(all(grade._digest(row) in retained for row in old[key]),"ALL_ORIGINAL_GRADING_REVISIONS_AND_NEGATIVE_WEEKS_RETAINED")


def _reuse_assignment(capture,population,roles,schedule,choice):
    from . import state
    original=capture["population"]
    require(original["stream_id"]==population["stream_id"]
        and original["role_catalog_sha256"]==population["role_catalog_sha256"]==state.digest(roles)
        and capture["roles"]==roles and all(original["assignments"].get(g)==v for g,v in population["assignments"].items())
        and state.digest(capture["choice"]["choice"])==state.digest(choice.document["choice"])
        and len({g["game_id"] for g in schedule})==len(schedule)
        and {g["game_id"]:g for g in schedule}=={g["game_id"]:g for g in capture["schedule"]},
        "ORIGINAL_PRIMARY_ASSIGNMENT_REUSE_NO_REFRESH_REISSUANCE")


def execute(context,*,transport=None,fetch=None,clock=None):
    require(type(context) is Authenticated,"LIVE_OPERATIONS_GRADE_CONTEXT_REQUIRED");context.verify()
    from . import audit_weekly_archive_v1 as archive,audit_weekly_grade_v1 as grade,audit_weekly_grade_checkpoint_v1 as checkpoint
    from . import audit_weekly_provider_v1 as provider,private_draft_store as store,state,gha_private_checkpoint as cp
    from .operational_storage import OperationalStorage
    clock=clock or state.now_utc;p=context.request
    validate_request(p,p["phase"])
    storage=OperationalStorage(p["cache"],ROOT/"config/operational-source-policy-v2.json",state=p["state_root"])
    restored,index=_archive(context,storage,clock);registered,choice=_epoch(restored,storage,clock)
    previous=_previous(context,restored,storage,transport)
    if previous is not None:
        require(previous.registered.epoch.sha256==registered.epoch.sha256,"EXACT_CURRENT_AND_PREVIOUS_GRADING_EPOCH")
    output=archive.fresh(storage,p["output"]);context.registered=registered
    if p["phase"]==PHASES[0]:
        aliases=restored["aliases"];read=lambda role:archive.read_owned(storage,aliases["context/"+role+".json"],4 << 20)
        population,roles,full=read("ops_population"),read("ops_roles"),read("ops_schedule")
        require(type(full) is list and 0<len(full)<=32 and all(r.get("game_type")=="REG" for r in full),"FULL_OPERATIONAL_REG_WEEK_SCHEDULE")
        schedule=[{k:r[k] for k in provider.GAME_KEYS} for r in full]
        pop=grade.bind_population(population,registered,choice,authenticate=_exact(context,"POPULATION_BEFORE_VALUES",population,clock),at=clock())
        ids=set(population["assignments"].values());require(len(ids)==1,"ONE_PRIMARY_CAPTURE_ASSIGNMENT_REQUIRED")
        capture_id=next(iter(ids));captures=[]
        if previous is not None:captures=grade.retained_captures(previous.durable,registered,at=clock())
        assigned=next((c for c in captures if c.document["capture_id"]==capture_id),None)
        if assigned is None:
            replay=_replay(restored,registered,storage)
            data=dict(restored=restored,population=population,capture_id=capture_id,roles=roles,schedule=schedule,relocated_replays=(replay,))
            capture=grade.bind_capture(registered,choice,pop,restored,storage=storage,capture_id=capture_id,role_catalog=roles,frozen_schedule=schedule,
                authenticate=_exact(context,"QUALIFIED_CAPTURE_RESTORATION",data,clock),at=clock(),relocated_replays=(replay,))
            captures.append(capture)
        else:
            _reuse_assignment(assigned.document,population,roles,schedule,choice)
        requested=grade.provider_request(captures,at=clock());e7=E7Fetch(context,storage,requested,clock,fetch)
        collector=provider.Collector(storage=storage,output=output/"provider",authenticate=e7.authenticate,fetch=e7,clock=clock)
        document=collector(requested);collector.capture.verify()
        observation_at=clock()
        observation_scope=dict(request=grade.provider_request(captures,at=observation_at),observations=document)
        observations=grade.bind_observations(captures,document,
            authenticate=_exact(context,"COMPLETED_GAME_PROVIDER_OBSERVATIONS",observation_scope,clock),at=observation_at)
        # The bound observations own the exact authenticated values. Raw
        # provider/request graphs are no longer needed by the resolver; their
        # immutable source receipts and completion file remain in the store.
        del collector,e7,document,requested,observation_scope
        snapshot=grade.grade(registered,captures,[observations],storage=storage,output=output/"grade",
            previous=previous.durable if previous is not None else None,clock=clock)
        if previous is not None:_retains(previous,snapshot)
        context.snapshot=snapshot
        # The sealed snapshot now owns every row. Release duplicate live input
        # graphs before the unchanged native checkpoint decoder runs.
        del captures,observations,pop
        if assigned is None:del capture,data
        client=_client(context,"append",transport)
        context.checkpoint_client=client
        handoff=checkpoint.append(snapshot,client,context.go["qualified_runtime"],storage=storage,output=output/"checkpoint",
            current_root_go_sha256=context.root_sha256,authenticate=_checkpoint_auth(context,clock),pending_census=context.go["pending_census"],clock=clock)
        report=dict(schema_version=VERSION+"-write",state="PRIVATE_GRADE_APPENDED_FRESH_READER_REQUIRED",snapshot=snapshot.binding,
            checkpoint_handoff=handoff,provider_capture=cp.binding(output/"provider/COMPLETION.json"),root_go_sha256=context.root_sha256,
            actual_completed_at=state.utc(clock()).isoformat(),fits=0,public_release=False,successful_forecast=False)
    else:
        handoff=p["inputs"]["checkpoint_handoff"];checkpoint.safe_handoff(handoff)
        client=_client(context,"restore",transport,readonly=True)
        context.checkpoint_client=client
        context.storage=storage
        context.checkpoint_binding=dict(path=str(output/"checkpoint/GRADING_SNAPSHOT.json.gz"),bytes=handoff["body_bytes"],sha256=handoff["body_sha256"])
        context.checkpoint_proof_path=output/"checkpoint/FRESH_READER_NATIVE_PROOF.json"
        result=checkpoint.restore(handoff,client,context.go["qualified_runtime"],registered,storage=storage,output=output/"checkpoint",
            current_root_go_sha256=context.root_sha256,authenticate=_checkpoint_auth(context,clock),pending_census=context.go["pending_census"],clock=clock)
        result.verify()
        if previous is None:_same_capture(restored,registered,choice,result.durable,storage)
        else:
            _retains(previous,result.durable)
            population=archive.read_owned(storage,restored["aliases"]["context/ops_population.json"],4 << 20)
            grade.bind_population(population,registered,choice,authenticate=_exact(context,"POPULATION_BEFORE_VALUES",population,clock),at=clock())
            require(set(population["assignments"].values()) <= {c["capture_id"] for c in result.durable.document["captures"]},
                "EXACT_CURRENT_PRIMARY_ASSIGNMENTS_IN_GRADING_HISTORY")
            old_ids={c["capture_id"] for c in previous.durable.document["captures"]}
            for assigned_id in set(population["assignments"].values())-old_ids:
                _same_capture(restored,registered,choice,result.durable,storage,capture_id=assigned_id)
            roles=archive.read_owned(storage,restored["aliases"]["context/ops_roles.json"],4 << 20)
            full=archive.read_owned(storage,restored["aliases"]["context/ops_schedule.json"],4 << 20)
            require(type(full) is list and 0<len(full)<=32 and all(r.get("game_type")=="REG" for r in full),"FULL_OPERATIONAL_REG_WEEK_SCHEDULE")
            for capture in result.durable.document["captures"]:
                if capture["capture_id"] in set(population["assignments"].values()) & old_ids:
                    _reuse_assignment(capture,population,roles,[{k:r[k] for k in provider.GAME_KEYS} for r in full],choice)
        durable_ref=grade.persist_snapshot(result.durable,storage=storage,output=output/"durable")
        from . import audit_weekly_grade_history_v1 as history
        envelope=history.prepare_envelope(result,handoff,cp.binding(context.checkpoint_proof_path),storage=storage,output=output/"history-evidence")
        report=dict(schema_version=VERSION+"-read",state="PRIVATE_OPERATIONAL_GRADING_FRESH_READER_VERIFIED",durable_history=durable_ref,
            evidence_envelope=envelope,grade_read_proof=result.proof,checkpoint_handoff=handoff,
            report=archive.write(storage,output/"REPORT.json",result.report),proof=archive.write(storage,output/"PROOF.json",result.proof),
            root_go_sha256=context.root_sha256,actual_completed_at=state.utc(clock()).isoformat(),fits=0,public_release=False,successful_forecast=False)
    context.verify();ref=archive.write(storage,output/"RESULT.json",report)
    result=dict(state=report["state"],manifest=ref,fits=0,public_release=False,successful_forecast=False)
    if p["phase"]==PHASES[0]:result["checkpoint_handoff"]=report["checkpoint_handoff"]
    require(len(store.canonical(result))<=32 << 10,"CLOSED_OPERATIONS_GRADE_OUTPUT_BOUND")
    return result


def run(args,env,*,transport=None,fetch=None):return execute(guard(args,env,transport=transport),transport=transport,fetch=fetch)
def contract():return dict(schema_version=VERSION+"-contract",state="PARENT_PHASE_WIRING_REQUIRED",phases=list(PHASES),
    request_keys=sorted(REQUEST_KEYS),input_keys={p:sorted(k) for p,k in INPUT_KEYS.items()},limits=LIMITS,
    request_schema_version=VERSION+"-request",output_names={p:p for p in PHASES},
    result_states={PHASES[0]:"PRIVATE_GRADE_APPENDED_FRESH_READER_REQUIRED",PHASES[1]:"PRIVATE_OPERATIONAL_GRADING_FRESH_READER_VERIFIED"},
    result_keys={p:sorted({"state","manifest","fits","public_release","successful_forecast"}|({"checkpoint_handoff"} if p==PHASES[0] else set())) for p in PHASES},
    result_manifest="RESULT.json",archive_reference="OWNED_RESTORED_JSON_WITH_ADJACENT_OWNED_DOWNLOADS",
    previous_snapshot="NONE_ONLY_ROOT_V2_RESTORES_ARCHIVED_HISTORY",required_context_roles=sorted(EPOCH_ROLES|OPS_ROLES),
    history_context_roles=["ops_previous_checkpoint_sidecar","ops_previous_public_receipt"],
    grade_read_manifest_extras=["checkpoint_handoff","grade_read_proof","evidence_envelope"],
    native_capacity_qualified=False,fits=0,public_release=False)
