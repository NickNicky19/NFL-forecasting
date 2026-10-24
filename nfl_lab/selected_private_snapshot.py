"""Opaque candidate+selected snapshot; standard exact-body restore proofs.

No forecasting, model loading, grading, acquisition or publication API.
"""
from datetime import datetime,timezone
import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace

from . import private_draft_store as s,owner_bootstrap_bundle as codec,gha_private_checkpoint as cp
from .owned_reference_batch import validate_owned_references
from . import weekly_durable_acceptance as a

VERSION='weekly-selected-private-snapshot-v1'
META=('terminal','completion','decision','parent_capture','bridge','startup_policy','procedure_catalog','selected_version_catalog')
INDEX_CAP=256<<10
ENTRY_CAP=16<<10
INDEX={'schema_version','procedure_sha256','source_policy_sha256','producer','producer_proof','original_selected','selected_descriptor','metadata_refs','groups','candidates','created_at'}
RELOCATION={'schema_version','original_selected','restored_selected','terminal_sha256','producer_proof_sha256','physical_restore_proof','source_index_sha256'}


def require(v,reason):
    if not v:raise s.StoreError(reason)
def now():return datetime.now(timezone.utc).isoformat()
def ref(path):return cp.binding(path)
def read(ref,cap=s.ASSET_CAP):return cp.read_ref(ref,cap)
def document(ref,cap=2<<20):return cp.strict_json(read(ref,cap))
def manifest(body,kind='runtime_manifest'):return dict(schema_version='weekly-private-payload-v2',payload_kind=kind,format='gzip',bytes=len(body),sha256=s.sha(body),source_policy_sha256=cp.POLICY_SHA)
def descriptor(d,kind,original):
    require(type(d) is dict and set(d)=={'entry','manifest_asset_id','manifest_sha256','manifest_bytes'},'CLOSED_SELECTED_DESCRIPTOR')
    e=d['entry'];require(type(e) is dict and set(e)=={'schema_version','payload','payload_asset_id','payload_name','producer_process','binding_sha256','writer_run_id'},'CLOSED_SELECTED_ENTRY')
    p=e['payload'];require(set(p)=={'schema_version','payload_kind','format','bytes','sha256','source_policy_sha256'} and p['schema_version']=='weekly-private-payload-v2'
        and p['payload_kind']==kind and p['format']=='gzip' and p['source_policy_sha256']==cp.POLICY_SHA and p['bytes']==original['bytes'] and p['sha256']==original['sha256']
        and type(p['bytes']) is int and 0<p['bytes']<=s.ASSET_CAP and a.h(p['sha256'])
        and e['schema_version']=='weekly-private-restore-manifest-v2' and e['payload_name']=='blob-'+p['sha256']+'.bin'
        and d['manifest_sha256']==s.sha(s.canonical(e)) and d['manifest_bytes']==len(s.canonical(e))<=ENTRY_CAP,'EXACT_SELECTED_DESCRIPTOR')
    for value in [d['manifest_asset_id'],e['payload_asset_id']]:require(type(value) is int and 0<value<10**20,'FINITE_ASSET_ID')
    return e
def unpack(body,cap):
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:plain=stream.read(cap+1)
    require(len(plain)<=cap,'PRIVATE_METADATA_INFLATION_CAP');return cp.strict_json(plain)
def required_files(refs,producer,candidates):
    require(set(refs)==set(META)|{'inference_consumed','original_handoff'} and len(candidates)==18
        and {(c['target'],c['method_id']) for c in candidates}=={(t,m) for t,_,m in cp.JOBS},'ALL_ORIGINAL_COMPARISON_STREAMS')
    expected={'metadata/'+name:(r['sha256'],r['bytes']) for name,r in refs.items()}
    expected['metadata/producer_proof']=(a.digest(producer),len(a.canonical(producer)))
    for n,c in enumerate(candidates):
        for role in ['body','completion']:expected[f'candidates/{n:02}-{role}']=(c[role]['sha256'],c[role]['bytes'])
    return expected


def collect(inference_root,storage,output,client,config):
    """Read only metadata; all 18 candidate bodies and selected bytes are opaque."""
    root=Path(inference_root);handoff_ref=ref(root/'EXPORT_INPUTS.json');h=document(handoff_ref)
    require(client.job['execution_lane']=='github_actions' and client.job['run_authenticated'] is True and client.job['job_id']==config['produce_job'],'AUTHENTIC_SELECTED_PRODUCER_JOB')
    require(h['schema_version']=='weekly-generic-selected-handoff-v1','GENERIC_HANDOFF_REQUIRED')
    refs={name:h[name] for name in META};docs={name:document(value) for name,value in refs.items()}
    t=docs['terminal'];c=docs['completion'];parent=docs['parent_capture']
    require(t['schema_version']=='weekly-generic-future-producer-v1' and t['state'] in {'LOCAL_FUTURE_SLATE_CAPTURED','PARTIAL_FUTURE_SLATE_RETAINED'} and t['fatal'] is None
        and t['selected']==c and c['state']=='PERSISTED' and c['binding']==h['selected'] and t['decision']==refs['decision'] and t['parent_capture']==refs['parent_capture']
        and t['startup_policy']==refs['startup_policy'] and refs['startup_policy']['sha256']==config['producer_policy_sha256'],'AUTHENTIC_COMPLETE_HANDOFF_REQUIRED')
    require(parent['schema_version']=='weekly-generic-future-producer-v1-candidate-capture' and parent['state']=='GENERIC_CANDIDATE_FORECASTS_PERSISTED'
        and docs['selected_version_catalog']['current_values_used'] is False,'ORIGINAL_COMPARISON_METADATA_REQUIRED')
    consumed_ref=ref(root/'CONSUMED.json');consumed=document(consumed_ref)
    require(consumed['schema_version']=='weekly-generic-future-producer-v1' and consumed['invocations']==1 and consumed['retries']==0
        and s.utc(consumed['at'])<=s.utc(t['actual_completed_at'])<=s.utc(client.started_at),'HONEST_PACKAGER_START_REQUIRED')
    refs.update(inference_consumed=consumed_ref,original_handoff=handoff_ref)
    candidates=[];files=[];jobs={(t,m) for t,_,m in cp.JOBS}
    require(len(parent['models'])==18 and {(m['target'],m['method_id']) for m in parent['models']}==jobs,'ALL18_COMPARISON_STREAMS_REQUIRED')
    for n,m in enumerate(parent['models']):
        original=m['persistence']['binding'];require(Path(original['path']).is_relative_to(root/'candidates'),'ORIGINAL_CANDIDATE_NAMESPACE')
        completion=ref(Path(original['path']).with_suffix('.completion.json'))
        require(document(completion)==m['persistence'],'EXACT_CANDIDATE_COMPLETION')
        for role,r in [('body',original),('completion',completion)]:files.append(cp.file_item(r,f'candidates/{n:02}-{role}', 'forecast' if role=='body' else 'completion'))
        candidates.append(dict(target=m['target'],method_id=m['method_id'],body=original,completion=completion,rows=m['persistence']['rows'],failure=m['failure']))
    # Copy code/config metadata only when it is outside this owned CAS; bytes
    # and original refs stay separate and unchanged in the private index.
    for name,r in refs.items():
        body=read(r,2<<20);owned=Path(output)/'metadata-originals'/name;storage.write_bytes(owned,body)
        files.append(cp.file_item(ref(owned),'metadata/'+name,'control'))
    producer=dict(schema_version='weekly-selected-packager-provenance-v2',identity=cp.client_identity(client),terminal_sha256=refs['terminal']['sha256'],selected_sha256=h['selected']['sha256'],bytes=h['selected']['bytes'],
        producer_policy_sha256=config['producer_policy_sha256'],source_policy_sha256=cp.POLICY_SHA,started_at_utc=client.started_at,created_at_utc=now(),inference_consumed_ref=consumed_ref,inference_consumed_at=consumed['at'])
    storage.write_bytes(Path(output)/'PACKAGER_PROOF.json',a.canonical(producer));r=ref(Path(output)/'PACKAGER_PROOF.json');files.append(cp.file_item(r,'metadata/producer_proof','control'))
    validate_owned_references(storage,{i['path']:i['sha256'] for i in files}|{h['selected']['path']:h['selected']['sha256']})
    return h['selected'],files,refs,producer,candidates


def append_snapshot(selected,files,refs,producer,candidates,factory,qualification,storage,output,config,*,first):
    require(s.utc(now())<s.utc(config['input_cutoff_utc']),'ORIGINAL_SELECTED_CUTOFF_EXPIRED')
    expected=required_files(refs,producer,candidates)
    require(len(files)==len(expected) and {i['logical_path']:(i['sha256'],i['bytes']) for i in files}==expected,'NO_DROPPED_COMPARISON_BODY_OR_METADATA')
    body=read(selected,4<<20);groups=codec.groups(files);require(0<len(groups)<=8,'EIGHT_METADATA_GROUPS_CAP')
    prepared=[]
    for n,items in enumerate(groups):
        encoded,inflated=codec.encode(items);prepared.append((dict(index=n,bytes=len(encoded),sha256=s.sha(encoded),inflated_bytes=inflated,files=items),encoded))
    first.draft();_,total=first.inventory()
    # Reserve index, every native entry, and the later job3 witness+entry now.
    incoming=len(body)+sum(len(b) for _,b in prepared)+2*INDEX_CAP+(len(prepared)+3)*ENTRY_CAP
    require(total+incoming<=s.TOTAL_CAP and first.inventory_slots+2*(len(prepared)+3)<=s.MAX_ASSETS,'ALL_COMPARISONS_AND_WITNESS_REMOTE_CAP')
    def make_index(sd,records):return dict(schema_version=VERSION,procedure_sha256=config['_sha256'],source_policy_sha256=cp.POLICY_SHA,producer=producer['identity'],producer_proof=producer,
        original_selected=selected,selected_descriptor=sd,metadata_refs=refs,groups=records,candidates=candidates,created_at=now())
    def fake(p):
        e=dict(schema_version='weekly-private-restore-manifest-v2',payload=p,payload_asset_id=10**20-1,payload_name='blob-'+p['sha256']+'.bin',producer_process=first.process,binding_sha256=s.sha(s.canonical(first.binding)),writer_run_id=first.run_id)
        return dict(entry=e,manifest_asset_id=10**20-1,manifest_sha256=s.sha(s.canonical(e)),manifest_bytes=len(s.canonical(e)))
    require(len(s.canonical(make_index(fake(manifest(body,'forecast_batch')),[dict(r,descriptor=fake(manifest(b))) for r,b in prepared])))<=INDEX_CAP-4096,'FULL_PRIVATE_INDEX_PREFLIGHT')
    def put(c,b,kind,scope,n):
        m=manifest(b,kind);storage.write_bytes(Path(output)/('APPEND_GO-'+str(n)+'.json'),s.canonical(dict(authority_kind='ROOT_APPROVED_PROCEDURE',human_approval=False,procedure_sha256=config['_sha256'],job=c.job,manifest_sha256=a.digest(m),scope_sha256=a.digest(scope))))
        return s.append(c,b,m,qualification)
    sd=put(first,body,'forecast_batch',selected,0);records=[]
    for n,(r,b) in enumerate(prepared):records.append(dict(r,descriptor=put(factory('append'),b,'runtime_manifest',r,n+1)))
    encoded=gzip.compress(s.canonical(make_index(sd,records)),mtime=0);require(len(encoded)<=INDEX_CAP,'PRIVATE_INDEX_CAP')
    index=put(factory('append'),encoded,'runtime_manifest',dict(kind='complete_snapshot'),len(records)+1)
    handoff=dict(schema_version=VERSION+'-handoff',runtime_binding=first.binding,source_sha=first.source_sha,run_id=first.run_id,procedure_sha256=config['_sha256'],index_descriptor=index)
    storage.write_bytes(Path(output)/'APPENDED.json',s.canonical(handoff));return handoff


def restore_snapshot(handoff,factory,storage,output,config,*,producer_api_job_id,witness=None,witness_api_job_id=None):
    """Job3 writes witness; job4 can restore again while preserving job3 proof."""
    output=Path(output);proofs=[]
    def get(d,name,kind):
        p=d['entry']['payload'];descriptor(d,kind,p);c=factory('restore');destination=output/'downloads'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        with storage.transaction():
            storage._require(p['bytes']);proof=s.restore(c,d,destination);owned=output/'owned'/name;storage.import_file(destination,owned,expected_sha256=p['sha256'])
        proofs.append(proof);return read(ref(owned)),ref(owned),proof
    encoded,index_ref,_=get(handoff['index_descriptor'],'index.gz','runtime_manifest');index=unpack(encoded,INDEX_CAP)
    require(set(index)==INDEX and index['schema_version']==VERSION and index['procedure_sha256']==config['_sha256'] and index['source_policy_sha256']==cp.POLICY_SHA
        and index['producer']['run_id']==handoff['run_id'] and index['producer']['source_sha']==handoff['source_sha'] and len(index['candidates'])==18 and 0<len(index['groups'])<=8,'CLOSED_COMPLETE_SELECTED_INDEX')
    a.identity(index['producer']);require(index['producer']==index['producer_proof']['identity'] and index['producer']['process_identity']==index['selected_descriptor']['entry']['producer_process']
        and index['producer']['process_identity']==handoff['index_descriptor']['entry']['producer_process'] and index['producer']['job_id']==config['produce_job']
        and type(producer_api_job_id) is int and index['producer']['api_job_id']==producer_api_job_id,'EXACT_GENUINE_PACKAGER')
    expected=required_files(index['metadata_refs'],index['producer_proof'],index['candidates'])
    observed={}
    for g in index['groups']:
        require(set(g)=={'index','bytes','sha256','inflated_bytes','files','descriptor'},'CLOSED_COMPARISON_GROUP')
        e=descriptor(g['descriptor'],'runtime_manifest',g)
        require(e['producer_process']==index['producer']['process_identity'] and e['writer_run_id']==handoff['run_id'] and e['binding_sha256']==a.digest(handoff['runtime_binding']),'SAME_PRODUCER_GROUPS')
        for item in g['files']:
            require(item['logical_path'] not in observed and item['required'] is True and item['origin']['source_policy_sha256']==cp.POLICY_SHA,'UNIQUE_REQUIRED_CAPTURE_FILES')
            observed[item['logical_path']]=(item['sha256'],item['bytes'])
    require(observed==expected,'NO_DROPPED_COMPARISON_BODY_OR_METADATA')
    for n,g in enumerate(index['groups']):
        require(g['index']==n,'EXACT_GROUP_ORDER');body,_,_=get(g['descriptor'],'metadata-'+str(n)+'.gz','runtime_manifest');codec.extract_owned(body,g,storage,output/'files')
    _,selected_ref,physical_proof=get(index['selected_descriptor'],'selected.jsonl.gz','forecast_batch')
    require((selected_ref['sha256'],selected_ref['bytes'])==(index['original_selected']['sha256'],index['original_selected']['bytes']),'EXACT_ORIGINAL_SELECTED_BYTES')
    metadata={name:ref(output/'files/metadata'/name) for name in META+('inference_consumed',)}
    for name,r in metadata.items():require((r['sha256'],r['bytes'])==(index['metadata_refs'][name]['sha256'],index['metadata_refs'][name]['bytes']),'ORIGINAL_METADATA_BYTES')
    producer=ref(output/'files/metadata/producer_proof');require(document(producer)==index['producer_proof'],'EXACT_PACKAGER_PROOF')
    if witness is None:authoritative=physical_proof
    else:
        w,_,_=get(witness,'job3-witness.gz','runtime_manifest');w=unpack(w,INDEX_CAP)
        require(set(w)=={'schema_version','index_sha256','producer_proof_sha256','restore_proof'} and w['schema_version']==VERSION+'-witness'
            and w['index_sha256']==index_ref['sha256'] and w['producer_proof_sha256']==a.digest(index['producer_proof']),'SOURCE_BOUND_JOB3_WITNESS')
        authoritative=w['restore_proof'];require(authoritative['payload_sha256']==selected_ref['sha256'] and authoritative['bytes']==selected_ref['bytes'],'EXACT_JOB3_BODY_PROOF')
        require(authoritative['job']['job_id']==config['restore_job'] and authoritative['process_identity']==witness['entry']['producer_process']
            and authoritative['source_sha']==handoff['source_sha'] and authoritative['run_id']==handoff['run_id']
            and type(witness_api_job_id) is int and authoritative['job']['api_job_id']==witness_api_job_id,'GENUINE_JOB3_WITNESS_SOURCE')
    durability=dict(runtime_binding=handoff['runtime_binding'],qualification_proof=config['_qualification'],restore_proof=authoritative)
    storage.write_bytes(output/'DURABILITY.json',s.canonical(durability))
    relocation=dict(schema_version='weekly-selected-immutable-relocation-v1',original_selected=index['original_selected'],restored_selected=selected_ref,terminal_sha256=metadata['terminal']['sha256'],producer_proof_sha256=producer['sha256'],physical_restore_proof=physical_proof,source_index_sha256=index_ref['sha256'])
    storage.write_bytes(output/'SELECTED_RELOCATION.json',s.canonical(relocation))
    result=dict(schema_version=VERSION+'-restored-inputs',selected=selected_ref,producer_proof=producer,**metadata,durability=ref(output/'DURABILITY.json'),selected_relocation=ref(output/'SELECTED_RELOCATION.json'),selected_snapshot_index=index_ref,candidate_rows=sum(c['rows'] for c in index['candidates']),candidates_retained=18,public_export_authorized=False)
    storage.write_bytes(output/'EXPORT_INPUTS_RELOCATED.json',s.canonical(result))
    if witness is None:
        body=gzip.compress(s.canonical(dict(schema_version=VERSION+'-witness',index_sha256=index_ref['sha256'],producer_proof_sha256=a.digest(index['producer_proof']),restore_proof=physical_proof)),mtime=0)
        require(len(body)<=INDEX_CAP,'JOB3_WITNESS_CAP')
        storage.write_bytes(output/'WITNESS_APPEND_GO.json',s.canonical(dict(authority_kind='ROOT_APPROVED_PROCEDURE',human_approval=False,procedure_sha256=config['_sha256'],manifest_sha256=a.digest(manifest(body)),scope='EXACT_JOB3_SELECTED_BODY_RESTORE_WITNESS')))
        result['witness_descriptor']=s.append(factory('append'),body,manifest(body),config['_qualification'])
    return result


def verify_relocation(r,bundle,selected,storage,accepted,index_ref):
    require(type(r) is dict and set(r)==RELOCATION and r['schema_version']=='weekly-selected-immutable-relocation-v1'
        and r['original_selected']==bundle['completion']['binding'] and r['restored_selected']==selected
        and r['terminal_sha256']==bundle['terminal_body_sha256'] and r['producer_proof_sha256']==a.digest(bundle['producer_proof'])
        and a.h(r['source_index_sha256']) and r['source_index_sha256']==index_ref['sha256'] and (selected['bytes'],selected['sha256'])==(r['original_selected']['bytes'],r['original_selected']['sha256']),'IMMUTABLE_SELECTED_RELOCATION_REQUIRED')
    index=unpack(read(index_ref,INDEX_CAP),INDEX_CAP)
    require(set(index)==INDEX and index['schema_version']==VERSION and index['original_selected']==r['original_selected'] and index['producer_proof']==bundle['producer_proof']
        and index['producer']==accepted['producer'] and index['metadata_refs']['terminal']['sha256']==r['terminal_sha256'],'SOURCE_BOUND_RELOCATION_INDEX_REQUIRED')
    p=r['physical_restore_proof'];ident=a.restored_identity(p);expected=accepted.get('exporter') or accepted['restorer']
    require(all(ident[k]==expected[k] for k in a.IDENTITY-{'process_identity'}) and ident['process_identity']!=accepted['producer']['process_identity']
        and p['payload_sha256']==selected['sha256'] and p['bytes']==selected['bytes'],'REGISTERED_PHYSICAL_RESTORE_REQUIRED')
    verifier=SimpleNamespace(binding=s.checked_binding(bundle['durability']['runtime_binding']),process=s.process_identity(),source_sha=expected['source_sha'],run_id=expected['run_id'],job=dict(execution_lane='github_actions',workflow_ref=expected['workflow_ref']))
    s.check_proof(verifier,p,'restore',same_run=False);validate_owned_references(storage,{selected['path']:selected['sha256'],index_ref['path']:index_ref['sha256']})
