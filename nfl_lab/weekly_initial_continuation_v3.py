"""One separately registered zero-fit continuation of an exact hosted snapshot."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from . import weekly_generic_producer as generic, weekly_initial_remaining_v2 as original
from .state import digest, utc

VERSION="weekly-initial-continuation-v3"
REGISTRATION=VERSION+"-registration"
REGISTRATION_ID="2026-REG-W07-continuation-run40129209279-metadata-repair-v4"
REGISTRATION_PATH="config/weekly-initial-continuation-v4-registration.json"
MODE="genuine-hosted-inference-continuation-v3"
CUTOFF=original.CUTOFF
ORIGINAL_REGISTRATION_SHA="bb65b2e0bf5c4c78788fceea3875230126fa8c0856f708bc7deaad14f3430fe6"
FIELDS={"schema_version","registration_id","state","repository","registered_at_utc","input_cutoff_utc","maximum_uses",
    "maximum_new_fits","source_acquisitions","source_claims","scientific_qualification","initial_registration","parent"}
PARENT_FIELDS={"run_id","source_sha","producer_job_id","producer_api_job_id","workflow_ref","checkpoint_procedure_sha256",
    "build_config_sha256","initial_registration_sha256","handoff","failed_inference_api_job_id","failed_inference_forecast_counts"}


def require(value,code):
    if not value:raise ValueError(code)


@dataclass(frozen=True)
class ContinuationOrigin:
    registration: dict
    registration_sha256: str

    @property
    def parent(self):return self.registration["parent"]

    def verify_unchanged(self):
        require(digest(self.registration)==self.registration_sha256,"CONTINUATION_AUTHORITY_CHANGED")

    def check_handoff(self,handoff):
        self.verify_unchanged()
        require(handoff==self.parent["handoff"],"EXACT_REGISTERED_PARENT_HANDOFF_REQUIRED")


def validate_registration(registration,*,now):
    r=registration
    require(type(r) is dict and set(r)==FIELDS and r["schema_version"]==REGISTRATION
        and r["registration_id"]==REGISTRATION_ID and r["state"]=="ROOT_REGISTERED_ZERO_FIT_CONTINUATION"
        and r["repository"]=="NickNicky19/NFL-forecasting" and r["input_cutoff_utc"]==CUTOFF
        and type(r["maximum_uses"]) is int and r["maximum_uses"]==1
        and all(type(r[k]) is int and r[k]==0 for k in ("maximum_new_fits","source_acquisitions","source_claims"))
        and r["scientific_qualification"] is False,"CLOSED_ZERO_FIT_CONTINUATION_REQUIRED")
    original.validate_registration(r["initial_registration"],now=now)
    require(digest(r["initial_registration"])==ORIGINAL_REGISTRATION_SHA
        and utc(r["initial_registration"]["registered_at_utc"])<utc(r["registered_at_utc"])<=now<utc(CUTOFF),
        "NEW_ACTUAL_CONTINUATION_AFTER_ORIGINAL_REGISTRATION_REQUIRED")
    p=r["parent"]
    require(type(p) is dict and set(p)==PARENT_FIELDS and p["run_id"]=="40129209279"
        and type(p["source_sha"]) is str and re.fullmatch('[a-f0-9]{40}',p["source_sha"])
        and p["producer_job_id"]=="genuine-hosted-fixed-build-v1" and type(p["producer_api_job_id"]) is int
        and p["producer_api_job_id"]==120977111674 and p["failed_inference_api_job_id"]==120977667174
        and p["failed_inference_forecast_counts"] is None and p["initial_registration_sha256"]==ORIGINAL_REGISTRATION_SHA
        and p["workflow_ref"].startswith("NickNicky19/NFL-forecasting/.github/workflows/lab.yml@refs/heads/")
        and all(type(p[k]) is str and re.fullmatch('[a-f0-9]{64}',p[k]) for k in ("checkpoint_procedure_sha256","build_config_sha256")),
        "EXACT_COMPLETED_SOURCE_JOB_AND_UNKNOWN_FAILED_INFERENCE_COUNTS_REQUIRED")
    h=p["handoff"]
    require(type(h) is dict and set(h)=={"schema_version","repository","procedure_sha256","source_sha","run_id","runtime_binding","index_descriptor"}
        and h["schema_version"]=="weekly-gha-private-checkpoint-v1-handoff" and h["repository"]==r["repository"]
        and h["source_sha"]==p["source_sha"] and h["run_id"]==p["run_id"] and h["procedure_sha256"]==p["checkpoint_procedure_sha256"]
        and h["index_descriptor"]["entry"]["writer_run_id"]==p["run_id"],"EXACT_ORIGINAL_CHECKPOINT_HANDOFF_REQUIRED")
    return r


def origin(registration,*,now):
    r=validate_registration(registration,now=now)
    return ContinuationOrigin(r,digest(r))


def consume_metadata_once(client,authority,qualification):
    """Serialized existing private upload; distinct from every old source claim."""
    from datetime import datetime,timezone
    from . import private_draft_store as core
    require(type(authority) is ContinuationOrigin,'TYPED_CONTINUATION_ORIGIN_REQUIRED')
    authority.verify_unchanged();validate_registration(authority.registration,now=datetime.now(timezone.utc))
    require(client.job['execution_lane']=='github_actions' and client.job['run_authenticated'] is True
        and client.job['job_id']=='genuine-hosted-fixed-build-restore-v1' and client.run_id!=authority.parent['run_id'],
        'AUTHENTICATED_CURRENT_CONTINUATION_CONSUMER_REQUIRED')
    core.check_proof(client,qualification,'qualified',same_run=False)
    body=core.canonical(authority.registration);require(0<len(body)<=16384 and core.sha(body)==authority.registration_sha256,
        'EXACT_BOUNDED_CONTINUATION_METADATA_BODY')
    name='manifest-'+authority.registration_sha256+'.json'
    asset=client.upload(name,body,reuse_completed=False)
    require(client.read_asset(asset['id'],name,len(body),authority.registration_sha256)==body,'EXACT_CONTINUATION_CLAIM_READBACK')
    client.draft()
    return dict(schema_version=VERSION+'-metadata-consumed',registration_sha256=authority.registration_sha256,
        run_id=client.run_id,source_sha=client.source_sha,job_id=client.job['job_id'],api_job_id=client.job['api_job_id'],
        process_identity=client.process,asset_id=asset['id'],asset_name=name,actual_consumed_at=datetime.now(timezone.utc).isoformat(),
        continuation_metadata_claims=1,source_claims=0,source_acquisitions=0,fits=0,automatic_retry=False)


def validate_metadata_consumption(receipt,*,authority,current_run,current_source,current_api_job_id):
    require(receipt['schema_version']==VERSION+'-metadata-consumed' and receipt['registration_sha256']==authority.registration_sha256
        and receipt['run_id']==current_run and receipt['source_sha']==current_source and receipt['api_job_id']==current_api_job_id
        and receipt['job_id']=='genuine-hosted-fixed-build-restore-v1' and receipt['asset_name']=='manifest-'+authority.registration_sha256+'.json'
        and type(receipt['asset_id']) is int and receipt['asset_id']>0 and receipt['continuation_metadata_claims']==1
        and receipt['source_claims']==receipt['source_acquisitions']==receipt['fits']==0 and receipt['automatic_retry'] is False,
        'EXACT_CURRENT_GLOBAL_CONTINUATION_CONSUMPTION_REQUIRED')
    return receipt


def prepare_initial_slate(schedule,registration,registration_ref,*,now):
    r=validate_registration(registration,now=now)
    original_ref=dict(schema_version=original.REGISTRATION,canonical_sha256=ORIGINAL_REGISTRATION_SHA)
    result=original.prepare_initial_slate(schedule,r["initial_registration"],original_ref,now=now)
    contract=result["slate_contract"]
    result["slate_id"]=REGISTRATION_ID
    result["slate_contract"]=dict(schema_version=VERSION,registration=registration_ref,kind="INITIAL_REMAINING_ZERO_FIT_CONTINUATION",
        registered_at_utc=r["registered_at_utc"],original_source_slate_contract=contract,maximum_uses=1,maximum_new_fits=0,
        source_acquisitions=0,source_claims=0,parent_run_id=r["parent"]["run_id"],parent_source_sha=r["parent"]["source_sha"],
        parent_producer_api_job_id=r["parent"]["producer_api_job_id"],parent_index_sha256=r["parent"]["handoff"]["index_descriptor"]["entry"]["payload"]["sha256"],
        prior_failed_inference_forecast_counts=None,scientific_qualification=False)
    return result


def validate_plan(plan,*,now):
    from tools.weekly_current_query import pin
    require(plan.get("initial_adapter",{}).get("schema_version")==VERSION,"EXPLICIT_CONTINUATION_ADAPTER_REQUIRED")
    ref=plan["initial_adapter"]["registration"];pin(ref)
    r=validate_registration(json.loads(Path(ref["path"]).read_text()),now=now)
    require(plan["startup_policy"]["sha256"]==r["initial_registration"]["startup_policy_sha256"]
        and plan["slate"]["slate_id"]==REGISTRATION_ID
        and plan["slate"]["game_cutoffs"]=={g:CUTOFF for g in original.REMAINING}
        and plan["slate"]["slate_contract"]["registration"]==ref
        and plan.get("continuation_origin_sha256")==digest(r),"EXACT_ZERO_FIT_CONTINUATION_PLAN_BINDING_REQUIRED")
    require({"nfl_lab/weekly_initial_continuation_v3.py","tools/weekly_initial_continuation_v3.py","nfl_lab/initial_horizon.py",
        "nfl_lab/weekly_initial_remaining_v2.py","nfl_lab/weekly_initial_remaining_v1.py"}<=set(plan["code_pins"]),"SEALED_CONTINUATION_AND_ORIGINAL_METADATA_CODE_REQUIRED")
    return r


def validate_prepared_history(prepared,*,origin_sha256,source_sha,run_id,source_contract,source_bindings,allowed_periods,now):
    require(prepared['schema_version']=='weekly-continuation-source-cache-v3' and prepared['state']=='OWNED_ORIGINAL_HISTORY_CACHE_PREPARED'
        and prepared['continuation_origin_sha256']==origin_sha256 and prepared['source_sha']==source_sha and prepared['run_id']==run_id
        and prepared['source_contract']==source_contract and prepared['policy_sha256']==source_contract['source_policy_sha256']
        and prepared['allowed_periods']==allowed_periods and prepared['original_receipts_relabelled'] is False
        and all(type(prepared[k]) is int and prepared[k]==0 for k in ('HTTP','fits','query_rows','forecasts','scores')),
        'EXACT_ZERO_HTTP_ORIGINAL_HISTORY_PREPARATION_REQUIRED')
    require(sorted(prepared['original_source_bindings'],key=lambda b:b['path'])==sorted(source_bindings,key=lambda b:b['path'])
        and utc(prepared['parent_capture_completed_at'])<=utc(prepared['asof_utc'])<=utc(prepared['actual_completed_at'])<=now,
        'EXACT_ORIGINAL_RECEIPTS_AND_ACTUAL_PREPARATION_CLOCKS_REQUIRED')
    return prepared


class InitialContinuationBackend(generic.ProductionBackend):
    def derive_slate(self,schedule):
        r=validate_plan(self.plan,now=self.clock());ref=self.plan["initial_adapter"]["registration"]
        derived=prepare_initial_slate(schedule,r,ref,now=self.clock())
        require(derived==self.plan["slate"],"SEALED_CONTINUATION_SCHEDULE_MISMATCH")
        self.checkpoint("INITIAL_METADATA")
        wanted={"schedules.csv.receipt.json","roster_weekly_2026.parquet.receipt.json","stats_player_week_2026.parquet.receipt.json"}
        receipts={Path(b["path"]).name:self.read(b) for b in self.plan["source_bindings"] if Path(b["path"]).name in wanted}
        original.validate_fresh_initial_metadata(r["initial_registration"],[self.read(b) for b in self.plan["artifacts"]],receipts,now=self.clock())
        self.checkpoint("INITIAL_CONSUME")
        root=Path(self.plan["cache"])/VERSION/"registrations";path=root/(REGISTRATION_ID+".json")
        with self.store.transaction():
            require(not path.exists(),"CONTINUATION_ALREADY_CONSUMED_NO_RETRY")
            self.store.register_root(root)
            self.store.atomic_json(path,dict(schema_version=VERSION+"-consumed",registration=ref,parent_run_id=r["parent"]["run_id"],
                actual_consumed_at=self.clock().isoformat(),maximum_new_fits=0,source_acquisitions=0,source_claims=0,automatic_retries=0))
        return derived
