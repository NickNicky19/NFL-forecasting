"""Native cross-run discovery and full recovery for the existing weekly writer.

Only the exact root-registered compressed public receipt and its immutable
historical source inventory are accepted. New GET proofs preserve their actual
current identities. Original forecasts, clocks, failures and losing history are
never rewritten. No source acquisition, model decoding, outcome decoding, fits,
private POST, publication or namespace search is performed.
"""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path

VERSION="audit-weekly-operations-restore-v1"
PHASE="operations-retained"
FILES=("nfl_lab/audit_weekly_operations_restore_v1.py","tools/audit_weekly_operations_restore_v1.py",
       "tests/test_audit_weekly_operations_restore_v1.py")
LIMITS=dict(wall_seconds=180,CPU_seconds=120,address_space_bytes=512 << 20,
    RSS_bytes=512 << 20,global_bytes=512 << 20,HTTP_calls=640,
    fits=0,model_decodes=0,outcome_decodes=0,remote_writes=0,retries=0)
KEYS={"schema_version","phase","code_pins","limits","cache","state_root","output","inputs"}


def require(value,code):
    from .private_draft_store import StoreError
    if not value:raise StoreError(code)


def run(args,env,*,transport=None):
    from . import audit_weekly_operations_worker_v1 as worker
    context=worker.authenticate_child(args,env,phase=PHASE,transport=transport)
    return restore(context,transport=transport)


def restore(context,*,transport=None):
    from . import audit_weekly_operations_worker_v1 as worker
    from . import audit_weekly_operations_authority_v1 as authority
    from . import audit_weekly_discovery_v1 as discovery,audit_weekly_retained_v1 as retained
    from . import audit_weekly_archive_v1 as archive,private_draft_store as store,gha_private_checkpoint as cp
    from . import audit_weekly_controller_v1 as controller
    from .operational_storage import OperationalStorage
    require(type(context) is worker.Authenticated,"LIVE_RECURRING_RESTORE_CONTEXT_REQUIRED")
    context.verify();p=context.request
    require(type(p) is dict and set(p)==KEYS and p["schema_version"]==VERSION+"-request"
        and p["phase"]==PHASE and p["limits"]==LIMITS and type(p["inputs"]) is dict
        and set(p["inputs"])=={"receipt","historical_source_sha256"},"CLOSED_RECURRING_RESTORE_REQUEST")
    inputs=p["inputs"];base=Path(p["cache"]).parent;output=Path(p["output"])
    require(output==base/PHASE and Path(p["state_root"])==base/"state","EXACT_RECURRING_RESTORE_PATHS")
    worker._reference(inputs["receipt"],base,64 << 10)
    historical=inputs["historical_source_sha256"]
    require(type(historical) is dict and set(historical)==set(retained.HISTORICAL_FILES)
        and all(type(v) is str and store.HASH.fullmatch(v) for v in historical.values()),"EXACT_HISTORICAL_RESTORE_SOURCE_CENSUS")
    storage=OperationalStorage(p["cache"],worker.ROOT/"config/operational-source-policy-v2.json",state=p["state_root"])
    storage.register_root(base)
    encoded=archive.read_owned(storage,inputs["receipt"],64 << 10,raw=True)
    previous=context.go["effective_epoch"]["previous_capture"]
    require(store.sha(encoded)==previous["receipt_sha256"],"EXACT_ROOT_REGISTERED_COMPRESSED_PRIOR_RECEIPT")
    value=archive.unpack(encoded,64 << 10);plain=store.canonical(value);plain_sha=store.sha(plain)
    discovery.receipt(plain,plain_sha)
    require(value["feed_sha256"]==previous["feed_sha256"] and value["run_id"]!=context.client.run_id,
        "EXACT_ROOT_REGISTERED_DISTINCT_PRIOR_CAPTURE")
    output=archive.fresh(storage,output);journal=storage.register_root(output/"journal")
    package=context.go["qualified_runtime"]
    extra=discovery.routes(value,package)
    clients=[]
    def factory(operation):
        context.verify()
        require(operation=="restore" and len(clients)<discovery.LIMITS["clients"]+retained.MAX_CLIENTS,
            "BOUNDED_GET_ONLY_RECURRING_RESTORE_CLIENTS")
        c=retained.ReadClient(context.env.get("GITHUB_TOKEN"),context.client.run_id,source_sha=context.client.source_sha,
            journal=journal,job=context.client.job,operation="restore",extra_routes=extra,transport=transport)
        c.bind(package["binding"]);clients.append(c);return c
    root_bytes=store.canonical(context.go)
    def grant_auth(request):
        context.verify()
        require(request.get("kind") in {"BIND_SEALED_DISCOVERY_SOURCE","LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET",
            "BIND_SEALED_HISTORICAL_SOURCE","LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET"},"CLOSED_RESTORE_GRANT_PURPOSE")
        require(store.sha(store.canonical(request["inputs"]))==request["inputs_sha256"],"EXACT_LIVE_RESTORE_GRANT_INPUTS")
        require(value["feed_sha256"]==context.go["effective_epoch"]["previous_capture"]["feed_sha256"]
            and store.sha(encoded)==context.go["effective_epoch"]["previous_capture"]["receipt_sha256"],
            "UNCHANGED_LIVE_REGISTERED_PRIOR_CAPTURE")
        return True
    expected=discovery._discovery_binding(plain_sha,package,context.root_sha256,historical)
    def authenticate_client(client,scope):
        context.verify()
        require(scope==dict(expected,current=cp.client_identity(client)),"EXACT_CURRENT_DISCOVERY_SCOPE")
        authority.attach(client,context.proof,context.env,root_bytes)
        require(cp.client_identity(client)["api_job_id"]==context.client.job["api_job_id"],"SAME_CURRENT_DISCOVERY_API_JOB")
        return True
    dgrant=discovery.bind_discovery_source(plain,plain_sha,package,bootstrap_proof=context.proof,
        current_root_go_sha256=context.root_sha256,historical_source_sha256=historical,authenticate=grant_auth)
    discovered=discovery.discover(plain,plain_sha,package,factory,storage=storage,output=output/"discovery",
        historical_source_sha256=historical,pending_census=context.go["pending_census"],
        current_root_go_sha256=context.root_sha256,authenticate=authenticate_client,discovery_grant=dgrant)
    discovered.verify();doc=discovered.document
    request=retained.prepare_request(worker.ROOT,doc["reader_handoff"],package,
        exporter_api_job_id=doc["exporter_api_job_id"],historical_source_sha256=historical,
        cache=p["cache"],state_root=p["state_root"],output=output/"restored",
        pending_census=context.go["pending_census"],pending_reservations=doc["pending_reservations"])
    request["approved"]=True
    native={key:context.authority[key] for key in ("repository","owner_root_go_sha256","source_sha","run_id",
        "run_attempt","job_id","workflow_ref","api_job_id","expires_at_utc")}
    native.update(schema_version=retained.VERSION+"-native-authority",phase=retained.PHASE,
        request_sha256=store.sha(store.canonical(request)),issued_at_utc=datetime.now(timezone.utc).isoformat(),
        actual_actions_api_authenticated=True,owner_root_checked=True,fits=0,remote_writes=0,
        protected_outcome_reads=0,public_release=False)
    require(set(native)==retained.AUTHORITY_KEYS,"CLOSED_DERIVED_RESTORE_AUTHORITY")
    grant=None
    if context.proof.document["actor"]==controller.BOT:
        jobs={role:dict(repository=store.REPO,run_id=value["run_id"],source_sha=value["source_sha"],
            workflow_ref=doc["reader_handoff"]["archive"]["producer"]["workflow_ref"],api_job_id=j["id"],job_id=j["name"],
            status=j["status"],conclusion=j["conclusion"],started_at=j["started_at"],completed_at=j["completed_at"],
            verified_permissions=dict(contents="write",actions="read")) for role,j in doc["original_job_evidence"].items()}
        # discovery validated the exact original workflow's permissions;
        # retained.restore independently rechecks them before private GETs.
        grant=retained.bind_historical_source(request,native,bootstrap_proof=context.proof,
            public_policy_sha256=value["policy_sha256"],historical_jobs=jobs,authenticate=grant_auth,root=worker.ROOT)
    result=retained.restore(request,factory,storage=storage,authority=native,root=worker.ROOT,
        check_authority=context.verify,historical_grant=grant)
    context.verify()
    require(sum(c.calls for c in clients)<=LIMITS["HTTP_calls"],"RECURRING_RESTORE_AGGREGATE_HTTP_CAP")
    binding=cp.binding(output/"restored"/"RETAINED_RESULT.json")
    require(archive.read_owned(storage,binding)==result,"EXACT_RETAINED_RECURRING_RESULT_BYTES")
    return dict(state="PRIVATE_PRIOR_CAPTURE_RECOVERED_FOR_RECURRING",retained_result=binding,
        original_run_id=value["run_id"],original_source_sha=value["source_sha"],
        current_run_id=context.client.run_id,current_source_sha=context.client.source_sha,
        files=len(result["aliases"]),fits=0,model_decodes=0,outcome_decodes=0,remote_writes=0,
        successful_forecast=False,public_release=False)
