"""Genuine hosted checkpoint: opaque pack/append/fresh restore, no ML imports.

The reusable owner bundle codec supplies only deterministic file transport and
CAS relocation. All origins here are genuine GitHub Actions, never OWNER_BOOTSTRAP.
"""
from datetime import datetime,timezone
import gzip
import hashlib
import json
import io
from pathlib import Path

from . import private_draft_store as store,owner_bootstrap_bundle as codec
from .owned_reference_batch import validate_owned_references

VERSION='weekly-gha-private-checkpoint-v1'
POLICY_SHA='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441'
GROUPS=8;INDEX_CAP=256<<10;ENTRY_CAP=16<<10
TARGETS=('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td')
JOBS=tuple([(t,'leaf_cdf_base','LAB_CDF') for t in TARGETS]+[(t,'count_A','COUNT_A') for t in ('rush_att','rec')]+[(t,'catboost_medium','CATBOOST_MEDIUM') for t in ('pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td')])
INDEX_KEYS={'schema_version','state','source_policy_sha256','procedure_sha256','source_sha','run_id','producer','created_at','build_sha256','files','groups','model_pairs','path_mapping','source_cache_logical','pending_reservations'}
GROUP_KEYS={'index','bytes','sha256','inflated_bytes','files','descriptor'}


def require(v,code):
    if not v:raise store.StoreError(code)
def now():return datetime.now(timezone.utc).isoformat()
def binding(path):
    p=store.parents_safe(path);body=store.read_local(p,store.ASSET_CAP)
    return dict(path=str(p),bytes=len(body),sha256=store.sha(body))
def read_ref(ref,cap=store.ASSET_CAP):
    require(type(ref) is dict and set(ref)=={'path','bytes','sha256'} and type(ref['bytes']) is int and 0<ref['bytes']<=cap and store.HASH.fullmatch(ref['sha256']),'EXACT_CHECKPOINT_REFERENCE')
    body=store.read_local(ref['path'],cap);require(len(body)==ref['bytes'] and store.sha(body)==ref['sha256'],'CHECKPOINT_REFERENCE_HASH');return body
def strict_json(body):
    def pairs(items):
        out={}
        for k,v in items:require(k not in out,'DUPLICATE_PRIVATE_JSON');out[k]=v
        return out
    def bad(_):raise store.StoreError('NONFINITE_PRIVATE_JSON')
    return json.loads(body,object_pairs_hook=pairs,parse_constant=bad)


def source_names(policy):
    """Expand the exact e7 JSON templates, without importing the numeric loader."""
    names={}
    for spec in policy['sources'].values():
        for year in range(2019,2027) if '{season}' in spec['name'] else [None]:
            names[spec['name'].format(season=year)]=spec['url'].format(season=year)
    require(len(names)==19,'EXACT19_SOURCE_NAMES');return names


def file_item(ref,logical,kind):
    return dict(ref,logical_path=codec.logical(logical),kind=kind,required=True,
        origin=dict(source_path=ref['path'],source_sha256=ref['sha256'],source_policy_sha256=POLICY_SHA))


def collect(build_root,storage,policy,*,source_sha,job):
    """Only approved fixed metadata is decoded. All model/raw bytes stay opaque."""
    root=store.parents_safe(build_root);build_ref=binding(root/'FINISHED.json');build=strict_json(read_ref(build_ref))
    require(build['schema_version']=='GENUINE_HOSTED_FIXED_BUILD_V1' and build['state']=='SOURCE_AND_TRAIN18_COMPLETE' and build['fatal'] is None
        and build['source_sha']==source_sha and build['execution_lane']=='github_actions' and build['genuine_job']['run_authenticated'] is True
        and build['genuine_job']==job
        and build['private_remote_persistence']=='NOT_YET_PERFORMED' and build['scoring']==build['searches']==build['forecasts_issued']==0,'COMPLETE_GENUINE_FIXED18_BUILD_REQUIRED')
    source_ref=binding(root/'SOURCE_READBACK.json');source=strict_json(read_ref(source_ref))
    require(build['source']==source and len(build['training']['slots'])==18 and build['training']['new_logical_fits_reserved']==18,'EXACT_BUILD_SOURCE_AND18')
    require(store.sha(store.read_local(Path(policy['_path']),1<<20))==POLICY_SHA,'SOURCE_POLICY_E7_REQUIRED')
    names=source_names(policy);raw_root=store.parents_safe(source['original_source_cache'])/'raw'
    require(source['schema_version']=='genuine-hosted-source-readback-v1' and raw_root.parent==root/'cache/operational-source-v2'/POLICY_SHA/'daily'/source['actual_execution_asof'][:10],'ORIGINAL_DAILY_SOURCE_NAMESPACE')
    expected={str(raw_root/name) for name in names}|{str(raw_root/(name+'.receipt.json')) for name in names}
    refs=source['original_raw_body_receipt_bindings'];require(len(refs)==38 and {r['path'] for r in refs}==expected,'EXACT19_BODY_RECEIPT_PAIRS')
    files=[];pairs=[]
    for slot,job in zip(build['training']['slots'],JOBS):
        t,family,method=job
        require((slot['target'],slot['family'],slot['method_id'])==job and slot['state']=='NEW_OPERATIONAL_ARTIFACT_EXPORTED'
            and slot['estimator_gate_calls']==1,'EXACT18_SUCCESSFUL_SLOTS')
        ref=slot['artifact'];require(Path(ref['path'])==root/'models'/t/family/'future-inference.json','FIXED_MANIFEST_PATH')
        manifest=strict_json(read_ref(ref,256<<10));model=manifest['model']
        require(manifest['schema_version']=='weekly-adaptive-release-v1-future-inference' and manifest['artifact_kind']=='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY'
            and manifest['family']==family and manifest['method_id']==method and manifest['source_contract']['source_policy_sha256']==POLICY_SHA and not manifest['dependencies']
            and Path(model['path'])==root/'models'/t/family/'trained.joblib','FIXED_MODEL_MANIFEST')
        prefix='models/'+t+'/'+family
        files.extend([file_item(model,prefix+'/trained.joblib','model'),file_item(ref,prefix+'/future-inference.json','model_manifest')])
        pairs.append(dict(target=t,family=family,method_id=method,model_logical=prefix+'/trained.joblib',manifest_logical=prefix+'/future-inference.json'))
    by_path={r['path']:r for r in refs}
    for name,url in names.items():
        body=by_path[str(raw_root/name)];receipt=by_path[str(raw_root/(name+'.receipt.json'))]
        meta=strict_json(read_ref(receipt,256<<10))
        require(meta.get('sha256')==body['sha256'] and meta.get('url')==url and meta.get('status') in {'acquired','stale_cache'},'EXACT_ORIGINAL_SOURCE_RECEIPT')
        files.extend([file_item(body,'source-cache/raw/'+name,'source_raw'),file_item(receipt,'source-cache/raw/'+name+'.receipt.json','control')])
    registration_ref=binding(root/'BUILD_REGISTRATION.json');registration=strict_json(read_ref(registration_ref,256<<10))
    require(registration.get('schema_version')=='genuine-hosted-fixed-build-registration-v1' and registration.get('approved') is True
        and registration.get('repository')==store.REPO and registration.get('source_sha')==source_sha and registration.get('maximum_new_fits')==18
        and registration.get('scope')=='SOURCE_AND_TRAIN_FIXED18_ONLY','EXACT_GENUINE_BUILD_REGISTRATION')
    controls=[(build_ref,'BUILD.json'),(registration_ref,'BUILD_REGISTRATION.json'),(source_ref,'SOURCE_READBACK.json'),(source['manifest'],'source-manifest.json')]
    for ref,name in controls:
        require(Path(ref['path']).is_relative_to(root),'BUILD_CONTROL_OUTSIDE_OWNED_ROOT');files.append(file_item(ref,'control/'+name,'control'))
    codec.validate_files(files);require(len(files)==78 and all(i['kind'] in {'model','model_manifest','source_raw','control'} for i in files),'EXACT78_REQUIRED_FILES')
    # This existing validator proves the source paths are immutable original CAS.
    validate_owned_references(storage,{i['path']:i['sha256'] for i in files})
    return files,pairs,build_ref


def seed_pending(journal,records):
    """Copy only authentic safe reservation metadata; never fabricate a POST."""
    require(type(records) is list and len(records)<=128,'PENDING_RESERVATION_SCOPE')
    for q in records:
        require(type(q) is dict and set(q)=={'schema_version','key','bytes','sha256','name'} and q['schema_version']=='weekly-private-POST-reservation-v2'
            and type(q['bytes']) is int and 0<q['bytes']<=store.ASSET_CAP and store.HASH.fullmatch(q['sha256'])
            and q['name'] in {'manifest-'+q['sha256']+'.json','blob-'+q['sha256']+'.bin'} and q['key']=='asset:'+q['name'],'EXACT_EXTERNAL_PENDING_RESERVATION')
        target=Path(journal)/(store.sha(q['key'].encode())+'.reservation.json');encoded=store.canonical(q)
        if target.exists():require(store.read_local(target,16384)==encoded,'PENDING_RECORD_CHANGED')
        else:store.create_local(target,encoded)


def claim_once(client,body,qualification,*,expected_sha256,procedure_sha256):
    """Serialized by the existing workflow lock; no independent CAS claim."""
    registration=strict_json(body)
    require(store.canonical(registration)==body and store.sha(body)==expected_sha256 and len(body)<=16384
        and registration.get('schema_version')=='weekly-initial-remaining-v1-registration' and registration.get('state')=='FROZEN_ROOT_REGISTERED'
        and registration.get('slate_kind')=='INITIAL_REMAINING_ONE_TIME' and registration.get('maximum_uses')==1
        and store.utc(registration['registered_at_utc'])<=datetime.now(timezone.utc)<store.utc(registration['input_cutoff_utc']),'EXACT_LIVE_ROOT_INITIAL_CLAIM')
    require(client.job['execution_lane']=='github_actions' and client.job['run_authenticated'] is True,'REAL_GHA_CLAIM_JOB_REQUIRED')
    store.check_proof(client,qualification,'qualified',same_run=False)
    name='manifest-'+expected_sha256+'.json'
    # Existing or ambiguous prior claim never becomes an idempotent successful
    # rebuild. This call uses the unchanged non-reuse manifest upload contract.
    asset=client.upload(name,body,reuse_completed=False)
    require(client.read_asset(asset['id'],name,len(body),expected_sha256)==body,'EXACT_CLAIM_READBACK');client.draft()
    return dict(schema_version=VERSION+'-source-claim',state='ONE_TIME_SOURCE_CLAIMED',repository=store.REPO,run_id=client.run_id,source_sha=client.source_sha,
        job_id=client.job['job_id'],api_job_id=client.job['api_job_id'],process_identity=client.process,registration_sha256=expected_sha256,registration_bytes=len(body),asset_id=asset['id'],asset_name=name,
        binding_sha256=store.sha(store.canonical(client.binding)),procedure_sha256=procedure_sha256,claimed_at=now())


def profile(files,client):
    """Encode and hash ALL required groups before the first POST."""
    groups=codec.groups(files);require(0<len(groups)<=GROUPS,'EIGHT_REQUIRED_GROUPS_CAP');prepared=[]
    for index,members in enumerate(groups):
        require(len(members)<=64,'GROUP64_FILES_CAP');body,inflated=codec.encode(members)
        prepared.append((dict(index=index,bytes=len(body),sha256=store.sha(body),inflated_bytes=inflated,files=members),body))
    client.draft();assets,total=client.inventory()  # includes all unknown/orphans/pending/canary
    needed=sum(len(body) for _,body in prepared)+INDEX_CAP+(len(prepared)+1)*ENTRY_CAP
    require(total+needed<=store.TOTAL_CAP and client.inventory_slots+2*(len(prepared)+1)<=store.MAX_ASSETS,'COMPLETE_REQUIRED_SNAPSHOT_REMOTE_CAP')
    return prepared,dict(existing_runtime_bytes=total,admitted_new_upper_bytes=needed,admitted_runtime_upper_bytes=total+needed,existing_slots=client.inventory_slots,new_slots=2*(len(prepared)+1))


def payload(body):return dict(schema_version='weekly-private-payload-v2',payload_kind='runtime_manifest',format='gzip',bytes=len(body),sha256=store.sha(body),source_policy_sha256=POLICY_SHA)
def reservation_metadata(key,body,name):
    digest=store.sha(body)
    require(name in {'blob-'+digest+'.bin','manifest-'+digest+'.json'} and key=='asset:'+name,'SAFE_POST_INTENT_SCOPE')
    return dict(schema_version='weekly-private-POST-reservation-v2',key=key,bytes=len(body),sha256=digest,name=name)
def client_identity(client):return dict(execution_lane='github_actions',repository=store.REPO,run_id=client.run_id,run_attempt=1,source_sha=client.source_sha,process_identity=client.process,job_id=client.job['job_id'],api_job_id=client.job['api_job_id'],permission='write',workflow_ref=client.job['workflow_ref'])
def descriptor_meta(d,cap):
    require(type(d) is dict and set(d)=={'entry','manifest_asset_id','manifest_sha256','manifest_bytes'},'CLOSED_CHECKPOINT_DESCRIPTOR')
    e=d['entry'];require(type(e) is dict and set(e)=={'schema_version','payload','payload_asset_id','payload_name','producer_process','binding_sha256','writer_run_id'},'CLOSED_CHECKPOINT_ENTRY')
    p=e['payload'];require(type(p) is dict and set(p)=={'schema_version','payload_kind','format','bytes','sha256','source_policy_sha256'}
        and p['schema_version']=='weekly-private-payload-v2' and p['payload_kind']=='runtime_manifest' and p['format']=='gzip' and p['source_policy_sha256']==POLICY_SHA
        and type(p['bytes']) is int and 0<p['bytes']<=cap and store.HASH.fullmatch(p['sha256']) and e['payload_name']=='blob-'+p['sha256']+'.bin'
        and e['schema_version']=='weekly-private-restore-manifest-v2' and store.HASH.fullmatch(e['producer_process']) and store.HASH.fullmatch(e['binding_sha256'])
        and type(e['writer_run_id']) is str and e['writer_run_id'].isdigit()
        and all(type(v) is int and 0<v<10**20 for v in [e['payload_asset_id'],d['manifest_asset_id']])
        and type(d['manifest_bytes']) is int and d['manifest_bytes']==len(store.canonical(e))<=ENTRY_CAP and d['manifest_sha256']==store.sha(store.canonical(e)),'EXACT_CHECKPOINT_DESCRIPTOR')
    return e


def produce(files,pairs,build_ref,factory,qualification,*,procedure_sha256,source_sha,run_id,output,storage,pending,first=None):
    first=first or factory('append');prepared,admission=profile(files,first);groups=[]
    def index(records,stamp):
        return dict(schema_version=VERSION+'-index',state='COMPLETE_REQUIRED_SNAPSHOT',source_policy_sha256=POLICY_SHA,procedure_sha256=procedure_sha256,source_sha=source_sha,run_id=run_id,
            producer=client_identity(first),created_at=stamp,build_sha256=build_ref['sha256'],files=files,groups=records,model_pairs=pairs,path_mapping={i['path']:i['logical_path'] for i in files},source_cache_logical='source-cache',pending_reservations=pending)
    preview=[]
    for record,body in prepared:
        entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=payload(body),payload_asset_id=10**20-1,payload_name='blob-'+record['sha256']+'.bin',producer_process=first.process,binding_sha256=store.sha(store.canonical(first.binding)),writer_run_id=run_id)
        encoded_entry=store.canonical(entry)
        descriptor=dict(entry=entry,manifest_asset_id=10**20-1,manifest_sha256=store.sha(encoded_entry),manifest_bytes=len(encoded_entry))
        preview.append(dict(record,descriptor=descriptor))
    # Before any POST, complete index metadata also fits with maximum-size IDs.
    require(len(store.canonical(index(preview,'9999-12-31T23:59:59.999999+00:00')))<=INDEX_CAP-4096,'COMPLETE_PRIVATE_INDEX_METADATA_CAP')
    def append(client,body,scope,number):
        manifest=payload(body)
        go=dict(schema_version=VERSION+'-native-append-GO',authority_kind='ROOT_APPROVED_PROCEDURE',human_approval=False,procedure_sha256=procedure_sha256,
            repository=store.REPO,source_sha=source_sha,run_id=run_id,job=client.job,runtime_binding_sha256=store.sha(store.canonical(client.binding)),
            operation='append',payload_manifest_sha256=store.sha(store.canonical(manifest)),scope_sha256=store.sha(store.canonical(scope)),computed_after_actual_build=True,created_at=now())
        storage.write_bytes(Path(output)/('NATIVE_APPEND_GO-'+str(number)+'.json'),store.canonical(go))
        return store.append(client,body,manifest,qualification)
    for n,(record,body) in enumerate(prepared):
        client=first if n==0 else factory('append')
        descriptor=append(client,body,record,n)
        require(descriptor['manifest_bytes']<=ENTRY_CAP and all(type(descriptor[k]) is int and 0<descriptor[k]<10**20 for k in ['manifest_asset_id'])
            and type(descriptor['entry']['payload_asset_id']) is int and 0<descriptor['entry']['payload_asset_id']<10**20,'PRIVATE_ENTRY_METADATA_CAP')
        groups.append(dict(record,descriptor=descriptor))
    document=index(groups,now())
    plain=store.canonical(document);require(len(plain)<=INDEX_CAP-4096,'PRIVATE_INDEX_CAP');encoded=gzip.compress(plain,mtime=0)
    require(len(encoded)<=INDEX_CAP,'PRIVATE_INDEX_CAP')
    storage.write_bytes(Path(output)/'PRIVATE_INDEX.json.gz',encoded)
    index_client=factory('append');descriptor=append(index_client,encoded,dict(kind='COMPLETE_PRIVATE_INDEX',group_hashes=[g['sha256'] for g in groups],files_sha256=store.sha(store.canonical(files))),len(groups))
    require(descriptor['manifest_bytes']<=ENTRY_CAP,'PRIVATE_ENTRY_METADATA_CAP')
    handoff=dict(schema_version=VERSION+'-handoff',repository=store.REPO,procedure_sha256=procedure_sha256,source_sha=source_sha,run_id=run_id,runtime_binding=first.binding,index_descriptor=descriptor)
    descriptor_meta(descriptor,INDEX_CAP)
    safe=store.canonical(handoff);require(len(safe)<=16384 and not any(x in safe for x in [b'https://',b'/workspace/',b'/home/',b'/tmp/',b'ghs_']),'SAFE_INDEX_DESCRIPTOR_ONLY')
    storage.write_bytes(Path(output)/'PRODUCER_FINISHED.json',store.canonical(dict(schema_version=VERSION+'-producer',state='PRIVATE_CHECKPOINT_APPENDED',handoff=handoff,index_sha256=store.sha(encoded),admission=admission,actual_completed_at=now(),producer=client_identity(first),required_files=len(files),groups=len(groups),model_decodes=0,scoring=0,selected_forecast_durability='NOT_CLAIMED')))
    return handoff


def check_index(doc,handoff,config,producer_api_job_id,workflow_ref):
    require(type(doc) is dict and set(doc)==INDEX_KEYS and doc['schema_version']==VERSION+'-index' and doc['state']=='COMPLETE_REQUIRED_SNAPSHOT'
        and doc['source_policy_sha256']==POLICY_SHA and doc['procedure_sha256']==handoff['procedure_sha256'] and doc['source_sha']==handoff['source_sha'] and doc['run_id']==handoff['run_id']
        and doc['producer']['execution_lane']=='github_actions' and doc['producer']['job_id']==config['produce_job'] and doc['producer']['source_sha']==handoff['source_sha']
        and doc['producer']['run_id']==handoff['run_id'] and doc['producer']['process_identity']==handoff['index_descriptor']['entry']['producer_process']
        and type(producer_api_job_id) is int and doc['producer']['api_job_id']==producer_api_job_id
        and set(doc['producer'])=={'execution_lane','repository','run_id','run_attempt','source_sha','process_identity','job_id','api_job_id','permission','workflow_ref'}
        and doc['producer']['repository']==store.REPO and doc['producer']['run_attempt']==1 and doc['producer']['permission']=='write'
        and doc['producer']['workflow_ref']==workflow_ref and store.utc(doc['created_at'])<=datetime.now(timezone.utc)
        and doc['source_cache_logical']=='source-cache' and doc['pending_reservations']==config['external_pending_reservations'],'CLOSED_PRIVATE_INDEX')
    codec.validate_files(doc['files']);require(len(doc['files'])==78 and 0<len(doc['groups'])<=8 and len(doc['model_pairs'])==18,'COMPLETE78_FILE_SNAPSHOT')
    originals={i['logical_path']:i for i in doc['files']};expected=set()
    require(doc['build_sha256']==originals['control/BUILD.json']['sha256'],'EXACT_BUILD_RESULT_HASH')
    for p,job in zip(doc['model_pairs'],JOBS):
        t,family,method=job;prefix='models/'+t+'/'+family
        require(p==dict(target=t,family=family,method_id=method,model_logical=prefix+'/trained.joblib',manifest_logical=prefix+'/future-inference.json'),'EXACT18_RESTORE_MODEL_PAIRS')
        expected.update([prefix+'/trained.joblib',prefix+'/future-inference.json'])
    for name in config['source_names']:expected.update(['source-cache/raw/'+name,'source-cache/raw/'+name+'.receipt.json'])
    expected.update('control/'+name for name in ['BUILD.json','BUILD_REGISTRATION.json','SOURCE_READBACK.json','source-manifest.json'])
    require(set(originals)==expected and doc['path_mapping']=={i['path']:i['logical_path'] for i in doc['files']}
        and all(i['required'] and i['origin']['source_policy_sha256']==POLICY_SHA for i in doc['files']),'EXACT_REQUIRED_RESTORE_SCOPE')
    for name,item in originals.items():
        expected_kind='model' if name.endswith('/trained.joblib') else 'model_manifest' if name.endswith('/future-inference.json') else 'source_raw' if name.startswith('source-cache/raw/') and not name.endswith('.receipt.json') else 'control'
        require(item['kind']==expected_kind,'EXACT_RESTORE_FILE_KIND')
    seen=set()
    asset_ids=[handoff['index_descriptor']['entry']['payload_asset_id'],handoff['index_descriptor']['manifest_asset_id']]
    for n,g in enumerate(doc['groups']):
        require(type(g) is dict and set(g)==GROUP_KEYS and g['index']==n and 0<g['bytes']<=store.ASSET_CAP and len(g['files'])<=64,'CLOSED_RESTORE_GROUP')
        for item in g['files']:
            require(item==originals.get(item['logical_path']) and item['logical_path'] not in seen,'EXACT_GROUP_PARTITION');seen.add(item['logical_path'])
        e=descriptor_meta(g['descriptor'],store.ASSET_CAP);asset_ids.extend([e['payload_asset_id'],g['descriptor']['manifest_asset_id']]);p=e['payload'];require(p==dict(schema_version='weekly-private-payload-v2',payload_kind='runtime_manifest',format='gzip',bytes=g['bytes'],sha256=g['sha256'],source_policy_sha256=POLICY_SHA)
            and e['writer_run_id']==handoff['run_id'] and e['producer_process']==doc['producer']['process_identity'] and e['binding_sha256']==store.sha(store.canonical(handoff['runtime_binding'])),'EXACT_GROUP_DESCRIPTOR')
    require(seen==expected and len(set(asset_ids))==len(asset_ids) and handoff['runtime_binding']['canary_asset_id'] not in asset_ids,'MISSING_OR_DUPLICATE_GROUP_FILES');return doc


def restore(handoff,factory,*,config,storage,output,producer_api_job_id):
    """Fresh job; exact readback, opaque extraction and new path-bound manifests."""
    output=Path(output);proofs=[]
    def get(descriptor,name):
        client=factory('restore');p=descriptor['entry']['payload'];destination=output/'downloads'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        with storage.transaction():
            storage._require(p['bytes']);proof=store.restore(client,descriptor,destination)
            owned=output/'owned-bundles'/name;storage.import_file(destination,owned,expected_sha256=p['sha256'])
        proofs.append(proof);return store.read_local(owned,store.ASSET_CAP)
    descriptor_meta(handoff['index_descriptor'],INDEX_CAP)
    encoded=get(handoff['index_descriptor'],'index.gz')
    with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as stream:plain=stream.read(INDEX_CAP+1)
    require(len(plain)<=INDEX_CAP,'PRIVATE_INDEX_INFLATED_CAP');doc=check_index(strict_json(plain),handoff,config,producer_api_job_id,factory.last.job['workflow_ref'])
    extracted=output/'files'
    for g in doc['groups']:
        body=get(g['descriptor'],'group-'+str(g['index'])+'.gz');codec.extract_owned(body,g,storage,extracted)
    mapping={i['path']:dict(path=str(extracted/i['logical_path']),bytes=i['bytes'],sha256=i['sha256']) for i in doc['files']}
    originals={i['logical_path']:i for i in doc['files']}
    for name,url in config['source_names'].items():
        r=strict_json(store.read_local(extracted/'source-cache/raw'/(name+'.receipt.json'),256<<10))
        require(r.get('sha256')==originals['source-cache/raw/'+name]['sha256'] and r.get('url')==url and r.get('status') in {'acquired','stale_cache'},'RESTORED_ORIGINAL_SOURCE_RECEIPT')
    model_refs=[]
    for p in doc['model_pairs']:
        original=mapping[originals[p['manifest_logical']]['path']];model=mapping[originals[p['model_logical']]['path']]
        meta=strict_json(read_ref(original,256<<10));require(meta['family']==p['family'] and meta['method_id']==p['method_id'] and meta['source_contract']['source_policy_sha256']==POLICY_SHA,'RESTORED_MODEL_METADATA_SCOPE')
        relocated=codec.relocate_future_manifest(original,model,output/'relocated-models'/p['target']/p['family'],storage)
        model_refs.append(dict(target=p['target'],family=p['family'],method_id=p['method_id'],manifest=relocated,original_model_sha256=model['sha256']))
    result=dict(schema_version=VERSION+'-restore',state='FULL_PRIVATE_CHECKPOINT_RESTORED',source_sha=handoff['source_sha'],run_id=handoff['run_id'],procedure_sha256=handoff['procedure_sha256'],
        index_sha256=store.sha(encoded),actual_completed_at=now(),original_producer=doc['producer'],restorer=client_identity(factory.last),proofs=proofs,path_mapping=mapping,models=model_refs,
        source_cache=str(extracted/'source-cache'),files=len(doc['files']),groups=len(doc['groups']),model_decodes=0,scoring=0,old_model_hash_reproduction=False,selected_forecast_durability='NOT_CLAIMED')
    storage.write_bytes(output/'RESTORE_FINISHED.json',store.canonical(result));return result
