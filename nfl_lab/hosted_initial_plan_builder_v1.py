"""Metadata-only adapter into the existing strict18 initial inference runner."""
from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

from . import gha_private_checkpoint as cp,private_draft_store as core
from . import weekly_generic_producer as generic,weekly_initial_remaining_v1 as initial
from .state import utc

VERSION='weekly-hosted-initial-plan-builder-v1'
REGISTRATION_SHA='9fdae2c34732602c81155e7b6db0488043886ca45259f8c3560aa6787125ca72'
GO_KEYS={'schema_version','state','authority_kind','root_ledger_writer','procedure_sha256','source_sha','initial_registration_sha256',
    'scope','approved_at_utc','reviewer','independent_review_receipt_sha256','root_ledger_event_sha256','individual_generated_plan_human_review'}


def require(value,code):
    if not value:raise ValueError(code)
def basic(ref):return {k:ref[k] for k in ('path','bytes','sha256')}


def verify_go(go,*,procedure_sha256,source_sha,now,recovery_v2=False,registration_sha256=None,continuation_v3=False):
    from .initial_horizon import resolve
    route=resolve(recovery_v2,continuation_v3=continuation_v3);expected=registration_sha256 if recovery_v2 or continuation_v3 else REGISTRATION_SHA
    require(core.HASH.fullmatch(str(expected)) and (not recovery_v2 or expected!=REGISTRATION_SHA),'EXACT_RECOVERY_REGISTRATION_SHA_REQUIRED')
    require(set(go)==GO_KEYS and go['schema_version']==route.builder_version+'-GO' and go['state']=='ROOT_APPROVED_METADATA_BUILDER'
        and go['authority_kind']=='ROOT_APPROVED_PROCEDURE' and go['root_ledger_writer']=='/root'
        and go['procedure_sha256']==procedure_sha256 and go['source_sha']==source_sha
        and go['initial_registration_sha256']==expected and go['scope']==route.builder_scope
        and go['individual_generated_plan_human_review'] is False and str(go['reviewer']).startswith('/root/')
        and core.HASH.fullmatch(str(go['independent_review_receipt_sha256'])) and core.HASH.fullmatch(str(go['root_ledger_event_sha256']))
        and utc(go['approved_at_utc'])<=now<utc(route.cutoff),'REVIEWED_ROOT_METADATA_BUILDER_GO_REQUIRED')
    return go


def schedule_metadata(body):
    """Read schedule identity/clock fields only; no statistics/roster/model decode."""
    import pandas as pd  # Already an unconditional dependency of original CAS.
    frame=pd.read_csv(io.BytesIO(body),usecols=['season','week','game_type','game_id','gameday','gametime'])
    frame=frame.loc[frame.season.eq(2026)&frame.week.eq(7)&frame.game_type.eq('REG')].copy()
    local=pd.to_datetime(frame.gameday.astype(str)+' '+frame.gametime.astype(str),errors='coerce')
    frame['kickoff_utc']=local.dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('UTC')
    return frame[['season','week','game_type','game_id','kickoff_utc']].to_dict('records')


def validate_restore(restored,*,restore_ref,root,config,source_sha,run_id,workflow_ref,process_identity,now,read,registration,recovery_v2=False,continuation=None):
    """Authenticate original controls and path relocation, with opaque model bytes."""
    from .initial_horizon import resolve
    route=resolve(recovery_v2);adapter=route.adapter()
    origin_source=source_sha;origin_run=run_id;origin_workflow=workflow_ref
    if continuation is not None:
        from .weekly_initial_continuation_v3 import ContinuationOrigin
        require(type(continuation) is ContinuationOrigin and recovery_v2,'TYPED_V2_SOURCE_CONTINUATION_REQUIRED')
        continuation.verify_unchanged();parent=continuation.parent
        origin_source=parent['source_sha'];origin_run=parent['run_id'];origin_workflow=parent['workflow_ref']
        require(run_id!=origin_run and restored['continuation_origin_sha256']==continuation.registration_sha256
            and restored['parent_origin']==parent and restored['original_procedure_sha256']==parent['checkpoint_procedure_sha256']
            and restored['index_sha256']==parent['handoff']['index_descriptor']['entry']['payload']['sha256'],
            'EXACT_REGISTERED_CROSS_RUN_ORIGIN_REQUIRED')
    registration_sha=core.sha(core.canonical(registration)) if recovery_v2 else REGISTRATION_SHA
    if recovery_v2:adapter.validate_registration(registration,now=now)
    root=Path(root);output=root/'private-checkpoint-restore';files=output/'files'
    expected={'control/'+n for n in ('BUILD.json','BUILD_REGISTRATION.json','SOURCE_READBACK.json','source-manifest.json')}
    expected|={'source-cache/raw/'+n+s for n in config['source_names'] for s in ('','.receipt.json')}
    expected|={'models/'+t+'/'+f+'/'+n for t,f,m in cp.JOBS for n in ('trained.joblib','future-inference.json')}
    expected_schema=cp.VERSION+('-continuation-restore-v3' if continuation is not None else '-restore')
    require(restored['schema_version']==expected_schema and restored['state']=='FULL_PRIVATE_CHECKPOINT_RESTORED'
        and restored['source_sha']==source_sha and restored['run_id']==run_id and restored['procedure_sha256']==config['_sha256']
        and restored['files']==78 and type(restored['groups']) is int and 1<=restored['groups']<=8
        and restored['model_decodes']==restored['scoring']==0 and restored['old_model_hash_reproduction'] is False
        and restored['selected_forecast_durability']=='NOT_CLAIMED' and len(restored['path_mapping'])==78
        and len(restored['models'])==18 and restored['source_cache']==str(files/'source-cache')
        and utc(restored['actual_completed_at'])<=now and Path(restore_ref['path'])==output/'RESTORE_FINISHED.json','EXACT_SAME_RUN_STRICT18_RESTORE_REQUIRED')
    mapped={}
    for original,ref in restored['path_mapping'].items():
        path=Path(ref['path']);require(path.is_relative_to(files) and path.relative_to(files).as_posix() not in mapped,'RESTORE_MAPPING_SCOPE')
        mapped[path.relative_to(files).as_posix()]=basic(ref)
    require(set(mapped)==expected,'COMPLETE_FIXED78_RESTORED_MAPPING_REQUIRED')
    producer=restored['original_producer'];restorer=restored['restorer']
    for ident,job in ((producer,config['produce_job']),(restorer,config['restore_job'])):
        original=ident is producer
        require(ident['execution_lane']=='github_actions' and ident['repository']==core.REPO
            and ident['source_sha']==(origin_source if original else source_sha)
            and ident['run_id']==(origin_run if original else run_id) and ident['run_attempt']==1 and ident['permission']=='write' and ident['job_id']==job
            and ident['workflow_ref']==(origin_workflow if original else workflow_ref) and type(ident['api_job_id']) is int and ident['api_job_id']>0
            and core.HASH.fullmatch(ident['process_identity']),'GENUINE_SAME_RUN_PRODUCER_RESTORER_METADATA_REQUIRED')
    if continuation is not None:require(producer['api_job_id']==continuation.parent['producer_api_job_id'],'EXACT_PARENT_SOURCE_API_JOB')
    require(producer['api_job_id']!=restorer['api_job_id'] and len({producer['process_identity'],restorer['process_identity'],process_identity})==3,
        'FRESH_BUILDER_PROCESS_AFTER_FRESH_RESTORE_REQUIRED')
    require(len(restored['proofs'])==restored['groups']+1,'COMPLETE_RESTORE_PROOF_CENSUS')
    context=SimpleNamespace(run_id=run_id,source_sha=source_sha,binding=config['_runtime_binding'],process=process_identity,
        job={'execution_lane':'github_actions','workflow_ref':workflow_ref})
    for proof in restored['proofs']:
        core.check_proof(context,proof,'restore')
        require(proof['job']['job_id']==config['restore_job'] and proof['job']['api_job_id']==restorer['api_job_id']
            and proof['job']['run_authenticated'] is True and proof['process_identity']==restorer['process_identity']
            and utc(proof['created_at_utc'])<=utc(restored['actual_completed_at']),'API_AUTHENTICATED_SAME_JOB_PREDECESSOR_REQUIRED')
    require(restored['proofs'][0]['payload_sha256']==restored['index_sha256'],'EXACT_PRIVATE_INDEX_RESTORE_PROOF')
    build=read(mapped['control/BUILD.json']);source=read(mapped['control/SOURCE_READBACK.json']);build_registration=read(mapped['control/BUILD_REGISTRATION.json'])
    source_manifest=read(mapped['control/source-manifest.json'])
    require(build['schema_version']=='GENUINE_HOSTED_FIXED_BUILD_V1' and build['state']=='SOURCE_AND_TRAIN18_COMPLETE' and build['fatal'] is None
        and build['source_sha']==origin_source and build['execution_lane']=='github_actions' and build['genuine_job']['run_authenticated'] is True
        and build['genuine_job']['api_job_id']==producer['api_job_id'] and build['genuine_job']['job_id']==producer['job_id']
        and build['scoring']==build['searches']==build['forecasts_issued']==0 and build['source']==source
        and build['training']['new_logical_fits_reserved']==18 and len(build['training']['slots'])==18,'COMPLETE_ORIGINAL_BUILD_CONTROL_REQUIRED')
    require(build_registration['schema_version']==route.build_registration_schema and build_registration['approved'] is True
        and build_registration['repository']==core.REPO and build_registration['source_sha']==origin_source
        and build_registration['maximum_new_fits']==18 and build_registration['scope']=='SOURCE_AND_TRAIN_FIXED18_ONLY'
        and build_registration['initial_registration']==registration and build_registration['initial_registration_sha256']==registration_sha
        and core.sha(core.canonical(registration))==registration_sha,'ORIGINAL_EXACT_ROOT_REGISTERED_NEW_BUILD_REQUIRED')
    if recovery_v2:
        adapter.validate_build_registration(build_registration,source_sha=origin_source,config_sha256=config['_build_config_sha256'],
            initial_sha256=registration_sha,now=now)
    contract=config['_source_contract']
    require(source['source_contract']==contract and source_manifest['policy_sha256']==cp.POLICY_SHA
        and source_manifest['code_sha256s']==config['_source_code_pins'] and source_manifest['allowed_periods']==config['_allowed_periods']
        and utc(registration['registered_at_utc'])<=utc(source['actual_execution_asof'])<=utc(source['actual_source_and_feature_capture_completed_at'])<=now,
        'UNCHANGED_SOURCE_POLICY_CODE_PERIODS_AND_ACTUAL_CAPTURE_CLOCKS_REQUIRED')
    receipts={};source_refs=[]
    for name,url in config['source_names'].items():
        body=mapped['source-cache/raw/'+name];rref=mapped['source-cache/raw/'+name+'.receipt.json'];receipt=read(rref)
        require(receipt['sha256']==body['sha256'] and receipt['url']==url and receipt==source_manifest['source_receipts'][name]
            and source_manifest['sources'][name]==dict(sha256=body['sha256'],receipt_sha256=rref['sha256'],bytes=body['bytes']),
            'AUTHENTIC_ORIGINAL_SOURCE_BODY_RECEIPT_BINDINGS_REQUIRED')
        receipts[name]=receipt;source_refs.extend([body,rref])
    records=[];artifacts=[];all_refs=[restore_ref,*mapped.values()]
    for item,slot,job in zip(restored['models'],build['training']['slots'],cp.JOBS):
        t,family,method=job;prefix='models/'+t+'/'+family
        require((item['target'],item['family'],item['method_id'])==(slot['target'],slot['family'],slot['method_id'])==job
            and slot['state']=='NEW_OPERATIONAL_ARTIFACT_EXPORTED' and slot['estimator_gate_calls']==1,'STRICT18_ORIGINAL_SUCCESSFUL_SLOTS_REQUIRED')
        original_ref=mapped[prefix+'/future-inference.json'];original=read(original_ref);ref=basic(item['manifest']);m=read(ref)
        require(Path(ref['path'])==output/'relocated-models'/t/family/'future-inference.json'
            and (original_ref['bytes'],original_ref['sha256'])==(slot['artifact']['bytes'],slot['artifact']['sha256'])
            and original['fit_receipt']==slot['fit_receipt'] and original['source_contract']==contract
            and original['method_id']==method and original['family']==family and original['category']['target']==t
            and original['code_pins']==config['_numeric_code_pins'] and original['environment']==config['_environment']
            and original['training_cutoff_utc']=='2026-09-01T00:00:00+00:00' and not original['dependencies'],
            'EXACT_ORIGINAL_MODEL_SOURCE_ENVIRONMENT_AND_FIT_BINDINGS_REQUIRED')
        require(m['relocation']==dict(schema_version=generic.MODEL_BOUNDARY,original_manifest=original_ref,original_model=original['model'],
            relocated_model_path=m['model']['path'],parameters_fixtures_code_source_unchanged=True,model_decodes=0)
            and Path(m['model']['path'])==output/'relocated-models'/t/family/'trained.joblib'
            and (m['model']['bytes'],m['model']['sha256'])==(original['model']['bytes'],original['model']['sha256'])
            and (m['model']['bytes'],m['model']['sha256'])==(mapped[prefix+'/trained.joblib']['bytes'],mapped[prefix+'/trained.joblib']['sha256'])
            and item['original_model_sha256']==original['model']['sha256'],'EXACT_OPAQUE_MODEL_RELOCATION_REQUIRED')
        comparison=dict(m);comparison.pop('relocation');comparison['model']=original['model']
        require(comparison==original,'RELOCATION_CANNOT_CHANGE_PARAMETERS_FIXTURES_SOURCE_OR_CLOCKS')
        artifacts.append(ref);records.append(m);all_refs.extend([ref,basic(m['model'])])
    adapter.validate_fresh_initial_metadata(registration,records,{n+'.receipt.json':r for n,r in receipts.items()},now=now)
    generic.validate_freshness(receipts,now=now,season=2026,limits=config['source_freshness_seconds'])
    return dict(records=records,artifacts=artifacts,owned_inputs=all_refs,source_bindings=source_refs,source_cache=restored['source_cache'],
        schedule=mapped['source-cache/raw/schedules.csv'],roster=mapped['source-cache/raw/roster_weekly_2026.parquet'],build=mapped['control/BUILD.json'])


def catalog_metadata(records,*,registered_at):
    catalog=dict(schema_version='weekly-adaptive-release-v1',methods={},categories={})
    products={'count':('point_mean','point_mse'),'signed_integer':('point_median','point_mae'),'bernoulli':('binary_probability','brier')}
    for ref,m in records:
        method=m['method_id'];target=m['category']['target'];p,metric=products[m['category']['support']]
        spec=catalog['methods'].setdefault(method,dict(procedure_version=m['procedure_version'],model_versions=[],registered_at=registered_at,
            procedure_operational_eligible=True,procedure_replay_eligible=False))
        require(spec['procedure_version']==m['procedure_version'],'ONE_REGISTERED_PROCEDURE_PER_METHOD_REQUIRED')
        spec['model_versions'].append(ref['sha256'])
        category=catalog['categories'].setdefault(target,dict(state='READY',support=m['category']['support'],product=p,primary_metric=metric,
            reference_id='R0',shortlist=[],eligible_methods=['R0']))
        require(category['support']==m['category']['support'] and m['product']==p,'FIXED_CATEGORY_SUPPORT_PRODUCT_REQUIRED')
        category['shortlist'].append(method);category['eligible_methods'].append(method)
    catalog['methods']['R0']=dict(procedure_version='LIVE_R0_NOT_PROVIDED',model_versions=[],registered_at=registered_at,
        procedure_operational_eligible=False,procedure_replay_eligible=False,role='reference')
    return catalog
