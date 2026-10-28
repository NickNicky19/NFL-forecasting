"""SYS007: GET-only discovery of an explicitly registered prior namespace.

Only native entry manifests and the exact index/witness are decoded. Original
proofs/clocks are preserved. A new local derivation is neither capture-body
durability nor publication authority; unchanged weekly_retained still restores
and validates the complete original archive under a separately approved request.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
import resource
import time

from . import audit_weekly_archive_v1 as archive, audit_weekly_retained_v1 as retained
from . import audit_weekly_delivery_v1 as delivery, private_draft_store as store
from . import gha_private_checkpoint as cp, weekly_durable_acceptance as acceptance

VERSION = "audit-weekly-discovery-v1"
LIMITS = dict(clients=6, HTTP_calls=200, HTTP_per_client=40, assets=128,
    wall_seconds=180, CPU_seconds=120, RSS_bytes=512 << 20,
    entry_bytes=cp.ENTRY_CAP, index_bytes=archive.INDEX_CAP, witness_bytes=archive.WITNESS_CAP,
    fits=0, model_decodes=0, outcome_decodes=0, forecast_decodes=0, remote_writes=0, retries=0)
PIN_PATHS = tuple(sorted(set(retained.PIN_PATHS) | {
    "nfl_lab/audit_weekly_discovery_v1.py", "tools/audit_weekly_discovery_v1.py",
    "tests/test_audit_weekly_discovery_recurring_v1.py",
    "tests/test_audit_weekly_discovery_actor_v1.py",
    "nfl_lab/audit_weekly_delivery_v1.py", "nfl_lab/gha_private_checkpoint.py",
    "nfl_lab/owner_bootstrap_bundle.py"}))
_LIVE = object()


def require(ok, code):
    if not ok: raise store.StoreError(code)


def now(): return datetime.now(timezone.utc)


def pins(root=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    return {name:store.sha(store.read_local(root/name, 2 << 20)) for name in PIN_PATHS}


def _discovery_binding(receipt_sha256,package,root_sha,historical):
    return dict(schema_version=VERSION+"-scope",current_root_go_sha256=root_sha,receipt_sha256=receipt_sha256,
        qualified_runtime_sha256=store.sha(store.canonical(package)),historical_source_sha256=deepcopy(historical),helper_sha256=pins())


def _sealed_source(proof,root_sha,at):
    from . import audit_weekly_controller_bootstrap_v1 as bootstrap, audit_weekly_controller_v1 as controller
    require(type(proof) in {bootstrap.Owner,controller.Proof},"LIVE_DISCOVERY_BOOTSTRAP_PROOF_REQUIRED")
    d=proof.document
    if type(proof) is bootstrap.Owner:
        proof.verify(root_sha256=root_sha);actor=controller.OWNER
    else:
        proof.verify(registration_sha256=d["registration_sha256"],run_id=d["run_id"],job_id=d["job_id"],root_sha256=root_sha)
        require(d.get("schema_version")==controller.VERSION+"-current-child-proof","LIVE_DISCOVERY_CURRENT_CHILD_REQUIRED")
        actor=controller.BOT
    seal=getattr(proof,"bootstrap_seal",None)
    require(type(seal) is bootstrap.Seal,"LIVE_DISCOVERY_OWNER_SEAL_REQUIRED");seal.verify()
    registration=controller.registration(seal.registration_bytes,sealed_sha256=seal.registration_sha256,at=at)
    spec=registration["producer"]
    require(d.get("registration_sha256")==seal.registration_sha256 and d.get("actor")==actor
        and d.get("source_sha")==spec["source_sha"] and d.get("job_id") in spec["jobs"].values()
        and type(d.get("api_job_id")) is int and d["api_job_id"]>0
        and controller.utc(seal.document["owner_registration_completed_at"])<=controller.utc(at),
        "EXACT_CURRENT_SEALED_DISCOVERY_SOURCE_AND_ACTOR")
    return dict(registration_sha256=seal.registration_sha256,seal_sha256=controller.digest(seal.document),
        current={k:d[k] for k in ("source_sha","run_id","job_id","api_job_id")},current_actor=dict(actor),
        current_workflow_ref=store.REPO+"/.github/workflows/lab.yml@refs/heads/"+spec["branch"],
        operational_source_sha=spec["source_sha"],operational_policy_sha256=seal.document["static_public_policy_sha256"],
        operational_workflow_sha256=spec["workflow_sha256"],operational_jobs={k:spec["jobs"][k] for k in ("produce","restore","consume")},
        readiness=deepcopy(registration["readiness"]))


def _historical_contract(value,scope):
    operational=(value["source_sha"]==scope["operational_source_sha"]
        and value["policy_sha256"]==scope["operational_policy_sha256"]
        and value["workflow_sha256"]==scope["operational_workflow_sha256"]
        and {role:j["job_id"] for role,j in value["jobs"].items()}==scope["operational_jobs"])
    if operational:
        return dict(kind="CURRENT_SEALED_OPERATIONAL_SOURCE",branch=scope["current_workflow_ref"].split("@refs/heads/",1)[1])
    ready=scope["readiness"]
    require(value["source_sha"]==ready["source_sha"] and value["run_id"]==ready["run_id"]
        and value["workflow_sha256"]==ready["workflow_sha256"] and value["jobs"]==ready["jobs"]
        and store.sha(store.canonical(value))==ready["receipt_body_sha256"]
        and all(value[k]==v for k,v in ready["receipt_bindings"].items()),"EXACT_OWNER_SEALED_DISCOVERY_READINESS_RECEIPT")
    return dict(kind="OWNER_SEALED_NICK_READINESS",branch=ready["branch"])


class DiscoverySourceGrant:
    """In-process source/actor scope; never serialized execution authority."""
    def __init__(self,document,value,proof,authenticate,key,*,source_history_root=None):
        require(key is _LIVE,"LIVE_DISCOVERY_SOURCE_GRANT_REQUIRED")
        self.document=deepcopy(document);self.sha256=store.sha(store.canonical(document))
        self._value,self._proof,self._authenticate=deepcopy(value),proof,authenticate
        self._source_history_root=deepcopy(source_history_root)
    def verify(self,binding,current=None):
        require(self.sha256==store.sha(store.canonical(self.document)) and self.document["binding"]==binding
            and self.document["process_identity"]==store.process_identity()
            and self.document["binding"]["receipt_sha256"]==store.sha(store.canonical(self._value))
            and store.utc(self.document["created_at_utc"])<=now(),"DISCOVERY_SOURCE_GRANT_INTEGRITY_AND_SCOPE")
        scope=_sealed_source(self._proof,binding["current_root_go_sha256"],now())
        contract=(_historical_contract(self._value,scope) if self._source_history_root is None else
            _source_history_contract(self._source_history_root,self._value,scope,binding,self._proof))
        require(scope==self.document["scope"] and contract==self.document["historical_contract"],
            "DISCOVERY_SEALED_SOURCE_GRANT_CHANGED")
        if current is not None:
            require(all(current[k]==v for k,v in scope["current"].items())
                and current["workflow_ref"]==scope["current_workflow_ref"]
                and current["process_identity"]==self.document["process_identity"],"EXACT_DISCOVERY_CURRENT_NATIVE_PROCESS_AND_JOB")
        return self
    def __reduce__(self):raise store.StoreError("DISCOVERY_SOURCE_GRANT_CANNOT_BE_SERIALIZED")


def bind_discovery_source(receipt_body,receipt_sha256,qualified_runtime,*,bootstrap_proof,current_root_go_sha256,
        historical_source_sha256,authenticate,clock=now):
    """Bind public metadata to a live current bootstrap before namespace GETs.

    The parent callback must authenticate this exact root/receipt/package/code
    scope. Discovery independently checks old API jobs/source and invokes it
    again BEFORE private GETs. Historical BOT acceptance is confined to the
    current sealed operational source/policy; old readiness remains Nick-only.
    """
    value=receipt(receipt_body,receipt_sha256);at=clock()
    require(type(current_root_go_sha256) is str and store.HASH.fullmatch(current_root_go_sha256)
        and type(historical_source_sha256) is dict and set(historical_source_sha256)==set(retained.HISTORICAL_FILES)
        and all(type(v) is str and store.HASH.fullmatch(v) for v in historical_source_sha256.values()),"EXACT_DISCOVERY_GRANTED_ROOT_AND_SOURCE_PINS")
    scope=_sealed_source(bootstrap_proof,current_root_go_sha256,at)
    document=dict(schema_version=VERSION+"-source-grant",binding=_discovery_binding(receipt_sha256,qualified_runtime,
        current_root_go_sha256,historical_source_sha256),scope=scope,historical_contract=_historical_contract(value,scope),
        process_identity=store.process_identity(),created_at_utc=at.isoformat() if isinstance(at,datetime) else at)
    retained._grant_authenticate(authenticate,"BIND_SEALED_DISCOVERY_SOURCE",document,at)
    return DiscoverySourceGrant(document,value,bootstrap_proof,authenticate,_LIVE)


def _source_history_contract(root,value,scope,binding,proof):
    """Explicit V4 predecessor; the live current proof/seal stays unchanged."""
    from . import audit_weekly_grade_history_v1 as history,audit_weekly_template_v1 as template
    from . import audit_weekly_controller_v1 as controller
    require(store.sha(store.canonical(root))==binding["current_root_go_sha256"],"EXACT_SOURCE_HISTORY_DISCOVERY_ROOT")
    body=history.validate_source_history_binding(root)
    require(body is not None and root["source_sha"]==scope["operational_source_sha"]
        and root["publication_registration"]["policy_sha256"]==scope["operational_policy_sha256"]
        and root["code_pins"].get(".github/workflows/lab.yml")==scope["operational_workflow_sha256"]
        and root["jobs"]==scope["operational_jobs"],"SOURCE_HISTORY_DISCOVERY_CURRENT_SEALED_AUTHORITY")
    # Bind the entire static Root (including its transport) to the actual
    # native registration, not just a caller-supplied owner-Root hash.
    registration=controller.decode(proof.bootstrap_seal.registration_bytes)
    static=deepcopy(root);static["approved"]=False
    for name in template.DYNAMIC_FIELDS-{"approved"}:static[name]=None
    prepared=template.prepare(dict(schema_version=template.STATIC_V4,source_sha=root["source_sha"],
        code_pins=deepcopy(root["code_pins"]),readiness=deepcopy(registration["readiness"]),root_template=static))
    sealed=proof.bootstrap_seal.template_descriptor
    require(store.sha(prepared.plain)==sealed["template_sha256"] and len(prepared.plain)==sealed["template_bytes"],
        "SOURCE_HISTORY_DISCOVERY_STATIC_ROOT_MUST_MATCH_NATIVE_SEAL")
    pins=history.source_history_scope(root,value)
    require(value["source_sha"]!=root["source_sha"]
        and binding["historical_source_sha256"]=={p:pins[p] for p in retained.HISTORICAL_FILES},
        "SOURCE_HISTORY_DISCOVERY_EXACT_HISTORICAL_PINS")
    package,_=template.capture_runtime(root)
    require(store.sha(store.canonical(package))==binding["qualified_runtime_sha256"],"SOURCE_HISTORY_DISCOVERY_ORIGINAL_RUNTIME")
    branch=root["workflow_ref"].split("@refs/heads/",1)[1]
    require(value["workflow_sha256"]==scope["operational_workflow_sha256"]
        and {role:j["job_id"] for role,j in value["jobs"].items()}==scope["operational_jobs"],
        "SOURCE_HISTORY_DISCOVERY_UNCHANGED_WORKFLOW_AND_JOBS")
    return dict(kind="EXPLICIT_V4_OWNER_SOURCE_HISTORY",branch=branch,
        binding_sha256=store.sha(store.canonical(body)),receipt_sha256=store.sha(store.canonical(value)),
        historical_code_pins_sha256=body["predecessor"]["code_pins_sha256"])


def bind_source_history(receipt_body,receipt_sha256,qualified_runtime,*,bootstrap_proof,current_root_go_sha256,
        historical_source_sha256,current_root,authenticate,clock=now):
    """Bind ONLY the explicit owner-produced predecessor to current authority.

    Legacy discovery contracts keep their source/policy equality checks. This
    separate constructor authenticates the native V4 static commitment before
    any prior-namespace GET. Old BOT sources are not admitted by this adapter.
    """
    value=receipt(receipt_body,receipt_sha256);at=clock()
    scope=_sealed_source(bootstrap_proof,current_root_go_sha256,at)
    binding=_discovery_binding(receipt_sha256,qualified_runtime,current_root_go_sha256,historical_source_sha256)
    contract=_source_history_contract(current_root,value,scope,binding,bootstrap_proof)
    document=dict(schema_version=VERSION+"-source-history-grant",binding=binding,scope=scope,historical_contract=contract,
        process_identity=store.process_identity(),created_at_utc=at.isoformat() if isinstance(at,datetime) else at)
    retained._grant_authenticate(authenticate,"BIND_SEALED_DISCOVERY_SOURCE",document,at)
    return DiscoverySourceGrant(document,value,bootstrap_proof,authenticate,_LIVE,source_history_root=current_root)


def receipt(body, expected_sha256):
    """The parent supplies verified, uncompressed canonical public metadata."""
    require(type(body) is bytes and 0 < len(body) <= 64 << 10 and store.sha(body) == expected_sha256,
        "EXACT_REGISTERED_PUBLIC_RECEIPT_BYTES")
    value = cp.strict_json(body)
    require(type(value) is dict and set(value) == delivery.RECEIPT_KEYS and len(value) == 25
        and value["schema_version"] == delivery.VERSION+"-public-receipt" and body == store.canonical(value),
        "NEW_CLOSED_CANONICAL_DELIVERY_RECEIPT_REQUIRED")
    hashes = {"root_go_sha256", "policy_sha256", "workflow_sha256", "recipe_registration_sha256",
        "rights_authority_sha256", "r0_identity_sha256", "origin_choice_sha256", "feed_sha256"} | delivery.DISCOVERY_HASH_KEYS
    require(all(store.HASH.fullmatch(str(value[k])) for k in hashes)
        and re.fullmatch(r"[a-f0-9]{40}",str(value["source_sha"]))
        and type(value["run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}",value["run_id"])
        and type(value["fits"]) is int and value["fits"] == 0 and value["raw_or_models_public"] is False
        and type(value["rows"]) is int and 0 < value["rows"] <= 5000
        and type(value["feed_bytes"]) is int and 0 < value["feed_bytes"] <= 4 << 20,
        "CLOSED_PUBLIC_RECEIPT_HASHES_AND_COUNTS")
    jobs = value["jobs"]
    require(type(jobs) is dict and set(jobs) == {"produce","restore","consume"}
        and all(type(j) is dict and set(j) == {"job_id","api_job_id"}
            and re.fullmatch(r"[A-Za-z0-9_-]{1,100}",str(j["job_id"]))
            and type(j["api_job_id"]) is int and j["api_job_id"] > 0 for j in jobs.values())
        and len({j["job_id"] for j in jobs.values()}) == len({j["api_job_id"] for j in jobs.values()}) == 3,
        "EXACT_THREE_PUBLIC_RECEIPT_JOB_BINDINGS")
    require(type(value["categories"]) is list and value["categories"] == sorted(set(value["categories"]))
        and value["categories"] and set(value["categories"]) <= set(cp.TARGETS)
        and store.utc(value["policy_registered_at_utc"]) <= store.utc(value["verified_at"]) <= store.utc(value["created_at"]),
        "PUBLIC_RECEIPT_CATEGORIES_AND_ORIGINAL_CLOCKS")
    return value


def routes(value, package):
    """Exact routes for a parent's retained.ReadClient factory; no draft search."""
    return {retained.source_url(value["source_sha"],name) for name in retained.HISTORICAL_FILES} | {
        store.API+"/actions/runs/"+run+suffix
        for run in (value["run_id"],package["qualification"]["run_id"])
        for suffix in ("","/jobs?per_page=100&page=1")}


class Discovery:
    def __init__(self, document, binding, key):
        require(key is _LIVE, "LIVE_DISCOVERY_REQUIRED")
        self.document = deepcopy(document); self.binding = deepcopy(binding)
        self.sha256 = store.sha(store.canonical(document)); self._binding_hash = store.sha(store.canonical(binding))
    def verify(self):
        require(store.sha(store.canonical(self.document)) == self.sha256
            and store.sha(store.canonical(self.binding)) == self._binding_hash, "DISCOVERY_METADATA_CHANGED")
    def __reduce__(self): raise store.StoreError("DISCOVERY_JSON_IS_NOT_EXECUTION_AUTHORITY")


class _Pool:
    def __init__(self, factory, package, authenticate, scope):
        require(callable(factory) and callable(authenticate), "LIVE_PARENT_CLIENT_FACTORY_AND_AUTHENTICATOR_REQUIRED")
        self.factory,self.package,self.authenticate,self.scope = factory,package,authenticate,scope
        self.clients=[]; self.current=None; self.calls=0
        self.started=time.monotonic(); self.CPU=time.process_time(); self.journal=None
    def guard(self):
        require(time.monotonic()-self.started <= LIMITS["wall_seconds"]
            and time.process_time()-self.CPU <= LIMITS["CPU_seconds"]
            and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 <= LIMITS["RSS_bytes"], "DISCOVERY_NATIVE_ENVELOPE")
    def client(self, reserve=3, *, fresh=False):
        self.guard()
        if self.clients and not fresh and self.clients[-1].calls+reserve <= store.MAX_CALLS:
            return self.clients[-1]
        require(len(self.clients) < LIMITS["clients"], "SIX_DISCOVERY_NATIVE_CLIENTS_ONLY")
        c=self.factory("restore")
        require(isinstance(c,retained.ReadClient) and c.binding == self.package["binding"]
            and c.calls == 0 and c.transferred == 0, "EXPLICIT_NAMESPACE_FRESH_GET_ONLY_NATIVE_CLIENT")
        require(all(c is not previous for previous in self.clients), "FRESH_NATIVE_CLIENT_OBJECT_REQUIRED")
        transport=c.transport
        def bounded(request,timeout):
            self.guard()
            require(request.method == "GET" and request.data is None, "DISCOVERY_GET_ONLY")
            require(self.calls < LIMITS["HTTP_calls"], "DISCOVERY_200_HTTP_CALL_CAP")
            self.calls+=1
            return transport(request,timeout)
        c.transport=bounded; self.clients.append(c)
        c.authenticate_actions_job()
        identity=acceptance.identity(cp.client_identity(c))
        require(self.current is None or identity == self.current, "ONE_CURRENT_DISCOVERY_PROCESS_SOURCE_AND_JOB")
        require(self.journal is None or c.journal == self.journal, "ONE_DISCOVERY_PENDING_JOURNAL")
        require(self.authenticate(c,deepcopy(dict(self.scope,current=identity))) is True, "ACTUAL_CURRENT_ROOT_AUTHENTICATION_REQUIRED")
        self.current=identity; self.journal=c.journal
        return c
    def json(self,url):
        c=self.client(); return c.json(c.allow(url))
    def asset(self,record,cap):
        c=self.client(); digest=record.get("digest","")
        require(type(digest) is str and re.fullmatch(r"sha256:[a-f0-9]{64}",digest)
            and type(record["size"]) is int and 0 < record["size"] <= cap,"BOUNDED_SERVER_ASSET_DIGEST_REQUIRED")
        c.asset(record,record["name"],record["size"],digest[7:])
        url=c.allow(c.path("/releases/assets/"+str(record["id"])))
        status,headers,body=c.request(url,octet=True,download=True,cap=cap)
        require(status == 200 and headers.get("x-ratelimit-remaining") != "0" and "retry-after" not in headers
            and len(body) == record["size"] and store.sha(body) == digest[7:], "EXACT_SERVER_METADATA_ASSET_BYTES_NO_RETRY")
        return body


def _inventory(client):
    client.draft(); assets,total=client.inventory()
    require(client.inventory_slots == len(assets) <= LIMITS["assets"], "UNRESOLVED_PENDING_DISCOVERY_NAMESPACE")
    return assets,total


def _members(assets):
    return sorted((a["id"],a["name"],a["size"],a.get("digest"),a["state"],a.get("url")) for a in assets)


def _namespace_descriptor(descriptor, selected):
    """Admit only closed unselected JSON controls alongside archive gzip.

    Root consumption claims share this namespace. Their metadata retains every
    native entry/hash/size check; the caller still checks canonical bytes,
    namespace binding and actual payload asset metadata without fetching them.
    Exact receipt-selected entries always use the original gzip-only validator.
    """
    entry=descriptor.get("entry") if type(descriptor) is dict else None
    payload=entry.get("payload") if type(entry) is dict else None
    if type(payload) is not dict or payload.get("format") != "json":
        return cp.descriptor_meta(descriptor,store.ASSET_CAP)
    require(set(descriptor)=={"entry","manifest_asset_id","manifest_sha256","manifest_bytes"}
        and set(entry)=={"schema_version","payload","payload_asset_id","payload_name","producer_process","binding_sha256","writer_run_id"}
        and set(payload)=={"schema_version","payload_kind","format","bytes","sha256","source_policy_sha256"},
        "CLOSED_JSON_CONTROL_NATIVE_ENTRY")
    require(payload["schema_version"]=="weekly-private-payload-v2" and payload["payload_kind"]=="runtime_manifest"
        and payload["source_policy_sha256"]==cp.POLICY_SHA
        and type(payload["bytes"]) is int and 0<payload["bytes"]<=store.ASSET_CAP
        and type(payload["sha256"]) is str and store.HASH.fullmatch(payload["sha256"])
        and entry["payload_name"]=="blob-"+payload["sha256"]+".bin"
        and entry["schema_version"]=="weekly-private-restore-manifest-v2"
        and all(type(entry[k]) is str and store.HASH.fullmatch(entry[k]) for k in ("producer_process","binding_sha256"))
        and type(entry["writer_run_id"]) is str and entry["writer_run_id"].isdigit()
        and all(type(v) is int and 0<v<10**20 for v in (entry["payload_asset_id"],descriptor["manifest_asset_id"]))
        and type(descriptor["manifest_bytes"]) is int
        and descriptor["manifest_bytes"]==len(store.canonical(entry))<=cp.ENTRY_CAP
        and descriptor["manifest_sha256"]==store.sha(store.canonical(entry)),"EXACT_JSON_CONTROL_NATIVE_ENTRY")
    if payload["sha256"] in selected:
        return cp.descriptor_meta(descriptor,store.ASSET_CAP)
    return entry


def _origin(pool, value, historical, *, discovery_grant=None):
    require(type(historical) is dict and set(historical) == set(retained.HISTORICAL_FILES)
        and all(store.HASH.fullmatch(str(v)) for v in historical.values())
        and historical["config/private-draft-storage-v2.json"] == store.config_sha(), "REGISTERED_HISTORICAL_NATIVE_CODE_PINS")
    current=pool.json(store.API+"/actions/runs/"+pool.current["run_id"])
    base=store.API+"/actions/runs/"+value["run_id"]
    run=pool.json(base); listing=pool.json(base+"/jobs?per_page=100&page=1")
    owner=dict(login="NickNicky19",id=208912933);bot=dict(login="github-actions[bot]",id=41898282)
    current_actor=current.get("actor",{});old_actor=run.get("actor",{})
    actor_allowed=current_actor.get("login")==owner["login"] and type(current_actor.get("id")) is int and current_actor["id"]==owner["id"] \
        and old_actor.get("login")==owner["login"] and type(old_actor.get("id")) is int and old_actor["id"]==owner["id"]
    if discovery_grant is not None:
        discovery_grant.verify(pool.scope,pool.current)
        expected=discovery_grant.document["scope"]["current_actor"]
        permitted=[owner] if discovery_grant.document["historical_contract"]["kind"] in {
            "OWNER_SEALED_NICK_READINESS","EXPLICIT_V4_OWNER_SOURCE_HISTORY"} else [owner,bot]
        actor_allowed=current_actor.get("login")==expected["login"] and type(current_actor.get("id")) is int and current_actor["id"]==expected["id"] \
            and type(old_actor.get("id")) is int and any(old_actor.get("login")==a["login"] and old_actor["id"]==a["id"] for a in permitted)
        require(current.get("id")==int(pool.current["run_id"]) and current.get("head_sha")==pool.current["source_sha"]
            and current.get("status")=="in_progress" and current.get("event")=="workflow_dispatch" and current.get("run_attempt")==1
            and current.get("path")==".github/workflows/lab.yml"
            and current.get("repository",{}).get("full_name")==current.get("head_repository",{}).get("full_name")==store.REPO
            and current.get("head_branch")==pool.current["workflow_ref"].split("@refs/heads/",1)[1],"ACTUAL_DISCOVERY_GRANTED_CURRENT_RUN")
    require(value["run_id"] != pool.current["run_id"]
        and run.get("id") == int(value["run_id"]) and run.get("head_sha") == value["source_sha"]
        and run.get("status") == "completed" and run.get("conclusion") == "success" and run.get("run_attempt") == 1
        and run.get("event") == "workflow_dispatch" and run.get("path") == ".github/workflows/lab.yml"
        and run.get("repository",{}).get("full_name") == run.get("head_repository",{}).get("full_name") == store.REPO
        and actor_allowed,
        "ACTUAL_COMPLETED_PRIOR_RUN_SOURCE_AND_CURRENT_OWNER")
    branch=run.get("head_branch")
    require(type(branch) is str and re.fullmatch(r"[A-Za-z0-9_./-]+",branch)
        and all(part not in {"", ".", ".."} for part in branch.split("/")), "EXACT_PRIOR_WORKFLOW_BRANCH")
    if discovery_grant is not None:
        require(branch==discovery_grant.document["historical_contract"]["branch"],"EXACT_SEALED_DISCOVERY_HISTORICAL_BRANCH")
    require(type(listing.get("jobs")) is list and listing.get("total_count") == len(listing["jobs"]) <= 100,
        "COMPLETE_ORIGINAL_DISCOVERY_JOB_LIST")
    evidence={}
    for role,expected in value["jobs"].items():
        matches=[j for j in listing["jobs"] if j.get("id") == expected["api_job_id"]]
        require(len(matches) == 1, "EXACT_ORIGINAL_PUBLIC_JOB_API_ID")
        j=matches[0]
        require(j.get("name") == expected["job_id"] and j.get("run_id") == int(value["run_id"])
            and j.get("head_sha") == value["source_sha"] and j.get("status") == "completed" and j.get("conclusion") == "success"
            and store.utc(j["started_at"]) <= store.utc(j["completed_at"]) < store.utc(pool.clients[0].started_at),
            "COMPLETED_SUCCESSFUL_ORIGINAL_THREE_JOBS")
        evidence[role]=j
    require(store.utc(evidence["produce"]["completed_at"]) <= store.utc(evidence["restore"]["started_at"])
        and store.utc(evidence["restore"]["completed_at"]) <= store.utc(evidence["consume"]["started_at"])
        <= store.utc(value["verified_at"]) <= store.utc(value["created_at"]) <= store.utc(evidence["consume"]["completed_at"]),
        "ORDERED_ORIGINAL_PRODUCER_READER_EXPORTER_AND_RECEIPT_CLOCKS")
    for name,expected in historical.items():
        doc=pool.json(retained.source_url(value["source_sha"],name))
        require(doc.get("type") == "file" and doc.get("path") == name and doc.get("encoding") == "base64"
            and type(doc.get("size")) is int and 0 < doc["size"] <= 256 << 10, "BOUNDED_ORIGINAL_SOURCE_METADATA")
        raw=base64.b64decode(doc["content"].replace("\n",""),validate=True)
        require(len(raw) == doc["size"] and store.sha(raw) == expected, "EXACT_ORIGINAL_DISCOVERY_SOURCE_HASH")
        if name == ".github/workflows/lab.yml":
            require(expected == value["workflow_sha256"], "PUBLIC_RECEIPT_ORIGINAL_WORKFLOW_HASH")
            retained.workflow_permissions(raw,dict(jobs={r:j["job_id"] for r,j in value["jobs"].items()}))
    if discovery_grant is not None:
        discovery_grant.verify(pool.scope,pool.current)
        fields=("id","name","run_id","head_sha","status","conclusion","started_at","completed_at")
        retained._grant_authenticate(discovery_grant._authenticate,"LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET",
            dict(grant_sha256=discovery_grant.sha256,grant=discovery_grant.document,current=pool.current,
                current_actor=current_actor,historical_actor=old_actor,
                historical_jobs={role:{k:j[k] for k in fields} for role,j in evidence.items()},
                historical_source_sha256=historical),now())
    return evidence,store.REPO+"/.github/workflows/lab.yml@refs/heads/"+branch


def discover(receipt_body, receipt_sha256, qualified_runtime, factory, *, storage, output,
        historical_source_sha256, pending_census, current_root_go_sha256, authenticate, pending_reservations=(),discovery_grant=None):
    """Root callback binds receipt/package/code hashes to CURRENT genuine GO.

    factory('restore') supplies a zero-HTTP retained.ReadClient already bound to
    the explicit qualified package, with routes(receipt,package) configured.
    This adapter authenticates each actual current process/job/source via API.
    authenticate(client,scope) MUST check the actual root/actor/policy authority;
    persisted JSON booleans cannot substitute for this parent callback.
    """
    value=receipt(receipt_body,receipt_sha256)
    require(store.HASH.fullmatch(str(current_root_go_sha256)), "EXACT_CURRENT_DISCOVERY_ROOT_HASH")
    scope=_discovery_binding(receipt_sha256,qualified_runtime,current_root_go_sha256,historical_source_sha256)
    if discovery_grant is not None:
        require(type(discovery_grant) is DiscoverySourceGrant,"LIVE_DISCOVERY_SOURCE_GRANT_REQUIRED")
        discovery_grant.verify(scope)
    pool=_Pool(factory,qualified_runtime,authenticate,scope); first=pool.client()
    # A new authenticated run may execute the same pinned source. The source
    # of each run remains independently API-bound, never rewritten as freshness.
    require(first.run_id != value["run_id"], "FRESH_CROSS_RUN_DISCOVERY_CONTEXT")
    require(pool.current["api_job_id"] not in {j["api_job_id"] for j in value["jobs"].values()},"FRESH_DISCOVERY_API_JOB")
    if discovery_grant is not None:discovery_grant.verify(scope,pool.current)
    evidence,workflow_ref=_origin(pool,value,historical_source_sha256,discovery_grant=discovery_grant)
    cp.seed_pending(first.journal,list(pending_reservations))
    archive.authenticate_qualification(first,qualified_runtime,pending_census)
    qrun=pool.json(store.API+"/actions/runs/"+qualified_runtime["qualification"]["run_id"])
    require(qrun.get("status") == "completed" and qrun.get("conclusion") == "success", "COMPLETED_QUALIFIED_DISCOVERY_NAMESPACE")
    initial,_=_inventory(pool.client(reserve=5)); initial_members=_members(initial)
    output=archive.fresh(storage,output); descriptors={}
    selected={value["archive_index_sha256"],value["reader_witness_sha256"]}
    by_id={a["id"]:a for a in initial}
    for asset in initial:
        if not asset["name"].startswith("manifest-"): continue
        require(re.fullmatch(r"manifest-[a-f0-9]{64}\.json",asset["name"]), "NATIVE_ENTRY_NAME_ONLY")
        body=pool.asset(asset,cp.ENTRY_CAP); entry=cp.strict_json(body)
        descriptor=dict(entry=entry,manifest_asset_id=asset["id"],manifest_sha256=store.sha(body),manifest_bytes=len(body))
        _namespace_descriptor(descriptor,selected)
        require(body == store.canonical(entry) and asset["name"] == "manifest-"+store.sha(body)+".json"
            and entry["binding_sha256"] == store.sha(store.canonical(qualified_runtime["binding"])), "EXACT_CANONICAL_ORIGINAL_NATIVE_ENTRY")
        payload=by_id.get(entry["payload_asset_id"])
        require(payload is not None, "UNAVAILABLE_NATIVE_ENTRY_PAYLOAD")
        first.asset(payload,entry["payload_name"],entry["payload"]["bytes"],entry["payload"]["sha256"])
        if entry["payload"]["sha256"] in selected:
            descriptors.setdefault(entry["payload"]["sha256"],[]).append(descriptor)
        storage.write_bytes(output/"entries"/(str(asset["id"])+".json"),body)
    require(value["archive_index_sha256"] != value["reader_witness_sha256"]
        and all(len(descriptors.get(value[key],[])) == 1 for key in ("archive_index_sha256","reader_witness_sha256")),
        "UNIQUE_INDEX_AND_WITNESS_NO_LATEST_OR_FALLBACK")
    index_descriptor=descriptors[value["archive_index_sha256"]][0]
    witness_descriptor=descriptors[value["reader_witness_sha256"]][0]
    require(pool.current["process_identity"] not in
        {index_descriptor["entry"]["producer_process"],witness_descriptor["entry"]["producer_process"]},"FRESH_DISCOVERY_PROCESS")
    metadata_proofs=[]
    def get(descriptor,name,cap,plain_cap):
        cp.descriptor_meta(descriptor,cap); c=pool.client(reserve=14)
        destination=output/"downloads"/name;destination.parent.mkdir(parents=True,exist_ok=True)
        with storage.transaction():
            storage._require(2*descriptor["entry"]["payload"]["bytes"]+cp.ENTRY_CAP)
            proof=store.restore(c,descriptor,destination)
            owned=output/"owned"/name;storage.import_file(destination,owned,expected_sha256=descriptor["entry"]["payload"]["sha256"])
        require(acceptance.restored_identity(proof) == pool.current, "ACTUAL_CURRENT_METADATA_GET_IDENTITY")
        metadata_proofs.append(proof)
        return archive.unpack(archive.read_owned(storage,cp.binding(owned),cap,raw=True),plain_cap)
    index=get(index_descriptor,"index.gz",archive.INDEX_CAP,archive.INDEX_PLAIN_CAP)
    handoff=dict(schema_version=archive.VERSION+"-handoff",repository=store.REPO,source_sha=value["source_sha"],run_id=value["run_id"],
        root_go_sha256=value["root_go_sha256"],producer=index["producer"],runtime_binding=qualified_runtime["binding"],
        index_descriptor=index_descriptor,files_sha256=value["archive_files_sha256"],archive_state="COMPLETE_CAPTURE",
        jobs={r:j["job_id"] for r,j in value["jobs"].items()})
    archive.safe_handoff(handoff);archive.check_index(index,handoff)
    require(index["qualification_sha256"] == store.sha(store.canonical(qualified_runtime["qualification"]))
        and index["census"]["missing_required"] == [] and index["census"]["raw_HTTP_corpus_archived"] is False
        and index["census"]["model_weights_reuploaded"] is False, "COMPLETE_ORIGINAL_QUALIFIED_INDEX_ONLY")
    producer=acceptance.identity(index["producer"]); produced=index["producer_proof"]
    require(producer["workflow_ref"] == workflow_ref and producer["api_job_id"] == value["jobs"]["produce"]["api_job_id"]
        and produced["root_go_sha256"] == value["root_go_sha256"] and produced["fits"] == 0
        and produced["public_release"] is produced["successful_forecast"] is False
        and store.utc(evidence["produce"]["started_at"]) <= store.utc(produced["actual_started_at"]) <= store.utc(index["created_at"]) <= store.utc(evidence["produce"]["completed_at"])
        and store.utc(value["policy_registered_at_utc"]) <= store.utc(produced["source_started_at"]) <= store.utc(produced["source_completed_at"]) <= store.utc(produced["actual_started_at"]),
        "ORIGINAL_PRODUCER_SOURCE_ROOT_AND_CLOCKS")
    originals={f["logical_path"]:f for f in index["files"]}
    required={"runtime/"+name for name in archive.CONTROL_FILES | archive.CANDIDATE_NAMES | archive.STATUS_NAMES}
    required |= {"r0/"+name for name in ("CAPTURE_COMPLETE.json","prepared.json","original-native.json.gz",
        "original_board.json","next_state.json","control_forecast_rows.json","control_completion.json","WORKER_COMPLETE.json")}
    require(required <= set(originals) and index["census"]["r0_provided"] is True
        and all(f["required"] is True and f["kind"] not in {"model","model_manifest","source_raw"} for f in originals.values()),
        "FULL_ORIGINAL_CANDIDATE_R0_CONTROL_CENSUS_NO_MODELS")
    for name,key in (("context/public_policy.json","policy_sha256"),("context/epoch.json","epoch_sha256"),("prepared/choice.json","choice_sha256")):
        require(name in originals and originals[name]["sha256"] == value[key], "PUBLIC_IDENTITY_MUST_MATCH_ORIGINAL_CANONICAL_METADATA_FILE")
    cp.seed_pending(first.journal,index["pending_reservations"])
    _inventory(pool.client(reserve=5))
    witness=get(witness_descriptor,"reader-witness.gz",archive.WITNESS_CAP,archive.WITNESS_CAP)
    require(type(witness) is dict and set(witness) == retained.WITNESS_KEYS and witness["schema_version"] == archive.VERSION+"-witness"
        and witness["index_sha256"] == value["archive_index_sha256"] and witness["files_sha256"] == value["archive_files_sha256"]
        and witness["producer_proof_sha256"] == store.sha(store.canonical(produced)) and witness["archive_state"] == "COMPLETE_CAPTURE"
        and witness["public_export_authorized"] is witness["successful_forecast"] is False
        and type(witness["validation"]) is dict and witness["validation"].get("qualified_selected") is True
        and type(witness["proofs"]) is list and 1 <= len(witness["proofs"]) <= 9, "COMPLETE_ORIGINAL_WITNESS_SOURCE_SCOPE")
    reader=acceptance.identity(witness["restorer"])
    require(reader["run_id"] == value["run_id"] and reader["source_sha"] == value["source_sha"] and reader["workflow_ref"] == workflow_ref
        and reader["job_id"] == value["jobs"]["restore"]["job_id"] and reader["api_job_id"] == value["jobs"]["restore"]["api_job_id"]
        and reader["process_identity"] != producer["process_identity"]
        and witness_descriptor["entry"]["writer_run_id"] == value["run_id"]
        and witness_descriptor["entry"]["producer_process"] == reader["process_identity"], "ORIGINAL_READER_NOT_DERIVED_IDENTITY")
    expected=[(index_descriptor["entry"]["payload"]["bytes"],value["archive_index_sha256"])]+[(g["bytes"],g["sha256"]) for g in index["groups"]]
    require([(p["bytes"],p["payload_sha256"]) for p in witness["proofs"]] == expected, "ALL_ORIGINAL_INDEX_GROUP_PROOFS_NO_OMISSION")
    for proof in witness["proofs"]:
        store.check_proof(first,proof,"restore",same_run=False)
        require(acceptance.restored_identity(proof) == reader
            and store.utc(evidence["restore"]["started_at"]) <= store.utc(proof["started_at_utc"]) <= store.utc(proof["created_at_utc"])
            <= store.utc(witness["actual_completed_at"]) <= store.utc(evidence["restore"]["completed_at"]), "ORIGINAL_NATIVE_READER_PROOF_CLOCKS")
    final,_=_inventory(pool.client(reserve=5))
    require(_members(final) == initial_members, "DISCOVERY_NAMESPACE_CHANGED_NO_RETRY")
    reader_handoff=dict(schema_version=archive.VERSION+"-reader-handoff",archive=handoff,restorer=reader,witness_descriptor=witness_descriptor)
    document=dict(schema_version=VERSION+"-derived",state="DERIVED_FROM_ORIGINAL_METADATA",derived_at_utc=now().isoformat(),
        public_receipt_sha256=receipt_sha256,current_root_go_sha256=current_root_go_sha256,current=pool.current,reader_handoff=reader_handoff,
        historical_source_sha256=deepcopy(historical_source_sha256),exporter_api_job_id=value["jobs"]["consume"]["api_job_id"],
        original_receipt=value,original_job_evidence=evidence,metadata_get_proofs=metadata_proofs,pending_reservations=index["pending_reservations"],
        HTTP_calls=pool.calls,native_clients=len(pool.clients),inventory_assets=len(initial),helper_sha256=scope["helper_sha256"],
        capture_body_restored=False,capture_durability_established=False,public_authority=False,public_release=False,fits=0)
    pool.guard(); ref=archive.write(storage,output/"DISCOVERED.json",document)
    archive.write(storage,output/"READER_HANDOFF.json",reader_handoff)
    return Discovery(document,ref,_LIVE)
