"""Private export provenance. JSON proof validation is not platform acceptance.

Manual records must have an exact root-registered digest. Automatic records can
only be returned in memory by the registered API verifier below; a loaded JSON
record cannot select that authority. Imports perform no I/O or credential reads.
"""
from datetime import datetime,timezone
import base64
import hashlib
import json
from pathlib import Path
import re

REPO='NickNicky19/NFL-forecasting'
IDENTITY={'execution_lane','repository','run_id','run_attempt','source_sha','process_identity','job_id','api_job_id','permission','workflow_ref'}
PRODUCER={'schema_version','identity','terminal_sha256','selected_sha256','bytes','producer_policy_sha256','source_policy_sha256','started_at_utc','created_at_utc'}
PACKAGER=PRODUCER|{'inference_consumed_ref','inference_consumed_at'}
ACCEPTANCE={'schema_version','authority_kind','state','accepted_at','selected_sha256','bytes','terminal_sha256','producer_proof_sha256','restore_proof_sha256','qualification_proof_sha256','runtime_binding_sha256','producer_policy_sha256','source_policy_sha256','producer','restorer','exporter','exporter_started_at','actions_evidence','qualification_acceptance','verifier_procedure_sha256'}
CANARY={'schema_version','authority_kind','state','qualified_proof_sha256','runtime_binding_sha256','run_id','run_attempt','source_sha','workflow_sha256','jobs','verified_at'}
EVIDENCE={'role','repository','run_id','run_attempt','source_sha','run_status','run_conclusion','job_id','api_job_id','job_status','job_conclusion','permission','started_at','completed_at'}
PROCEDURE={'schema_version','source_sha','verifier_sha256','workflow_sha256','producer_job','restorer_job','export_job','permissions'}


def require(value,reason):
    if not value:raise ValueError(reason)
def canonical(doc):return json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(doc):return hashlib.sha256(canonical(doc)).hexdigest()
def h(v):return type(v) is str and bool(re.fullmatch('[a-f0-9]{64}',v))
def utc(v):
    result=datetime.fromisoformat(v.replace('Z','+00:00'));require(result.tzinfo is not None,'ACCEPTANCE_CLOCK');return result.astimezone(timezone.utc)
def identity(v):
    require(type(v) is dict and set(v)==IDENTITY and v['execution_lane']=='github_actions' and v['repository']==REPO
        and type(v['run_id']) is str and bool(re.fullmatch('[1-9][0-9]{0,19}',v['run_id'])) and type(v['run_attempt']) is int and v['run_attempt']==1
        and type(v['source_sha']) is str and bool(re.fullmatch('[a-f0-9]{40}',v['source_sha'])) and h(v['process_identity'])
        and type(v['api_job_id']) is int and v['api_job_id']>0 and type(v['job_id']) is str and bool(re.fullmatch('[A-Za-z0-9_-]+',v['job_id']))
        and v['permission']=='write' and bool(re.fullmatch(re.escape(REPO)+r'/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+',v['workflow_ref'])),'ACCEPTANCE_IDENTITY')
    return v
def restored_identity(proof):
    j=proof['job'];return identity(dict(execution_lane=j['execution_lane'],repository=proof['repository'],run_id=proof['run_id'],run_attempt=proof['run_attempt'],source_sha=proof['source_sha'],
        process_identity=proof['process_identity'],job_id=j['job_id'],api_job_id=j['api_job_id'],permission=j['permission'],workflow_ref=j['workflow_ref']))


def canary_check(record,policy,durable,now):
    """Old canary still requires a root-verified COMPLETED successful run."""
    require(type(record) is dict and set(record)==CANARY and digest(record) in policy.get('root_verified_canary_acceptances',[])
        and record['schema_version']=='weekly-canary-platform-acceptance-v1' and record['authority_kind']=='ROOT_VERIFIED'
        and record['state']=='COMPLETED_SUCCESS_VERIFIED' and record['qualified_proof_sha256']==digest(durable['qualification_proof'])
        and record['runtime_binding_sha256']==digest(durable['runtime_binding']) and h(record['workflow_sha256']) and utc(record['verified_at'])<=utc(now),'ROOT_VERIFIED_CANARY_REQUIRED')
    q=durable['qualification_proof'];proofs=[q['before_proof'],q['read_proof'],q]
    require(record['run_id']==q['run_id'] and record['run_attempt']==1 and record['source_sha']==q['source_sha'] and utc(q['created_at_utc'])<=utc(record['verified_at'])
        and type(record['jobs']) is list and len(record['jobs'])==3,'CANARY_COMPLETED_RUN_REQUIRED')
    for observed,proof in zip(record['jobs'],proofs):
        require(type(observed) is dict and set(observed)=={'job_id','api_job_id','permission','run_status','run_conclusion','status','conclusion'}
            and observed['job_id']==proof['job']['job_id'] and observed['api_job_id']==proof['job']['api_job_id'] and observed['permission']==proof['job']['permission']
            and observed['run_status']=='completed' and observed['run_conclusion']=='success' and observed['status']=='completed' and observed['conclusion']=='success','CANARY_COMPLETED_SUCCESS_REQUIRED')


def facts(bundle,policy):
    p=bundle['producer_proof'];d=bundle['durability'];r=d['restore_proof'];c=bundle['completion']
    v1=type(p) is dict and set(p)==PRODUCER and p['schema_version']=='weekly-selected-producer-provenance-v1'
    v2=type(p) is dict and set(p)==PACKAGER and p['schema_version']=='weekly-selected-packager-provenance-v2'
    require(v1 or v2,'PRODUCER_PROVENANCE_REQUIRED')
    producer=identity(p['identity']);restorer=restored_identity(r)
    require(producer['process_identity']!=restorer['process_identity'] and (producer['run_id'],producer['api_job_id'])!=(restorer['run_id'],restorer['api_job_id']),'INDEPENDENT_PRODUCER_RESTORER_REQUIRED')
    require(p['selected_sha256']==c['binding']['sha256']==r['payload_sha256'] and type(p['bytes']) is int and p['bytes']==c['binding']['bytes']==r['bytes']
        and p['terminal_sha256']==bundle['terminal_body_sha256'] and p['producer_policy_sha256']==policy['producer_policy_sha256']
        and p['source_policy_sha256']==policy['source_policy_sha256'],'EXACT_PRODUCER_BODY_REQUIRED')
    if v1:
        require(utc(p['started_at_utc'])<=utc(bundle['terminal']['actual_completed_at'])<=utc(p['created_at_utc'])<=utc(r['started_at_utc']),'EXACT_PRODUCER_BODY_REQUIRED')
    else:
        consumed=bundle['inference_consumed'];ref=p['inference_consumed_ref']
        require(type(ref) is dict and set(ref)=={'path','bytes','sha256'} and ref['sha256']==bundle['inference_consumed_body_sha256']
            and ref['bytes']==bundle['inference_consumed_body_bytes'] and consumed.get('schema_version')=='weekly-generic-future-producer-v1'
            and consumed.get('invocations')==1 and consumed.get('retries')==0 and p['inference_consumed_at']==consumed['at']
            and utc(consumed['at'])<=utc(bundle['terminal']['actual_completed_at'])<=utc(p['started_at_utc'])<=utc(p['created_at_utc'])<=utc(r['started_at_utc']),'HONEST_PACKAGER_CLOCK_AND_SOURCE_REQUIRED')
    return dict(selected_sha256=p['selected_sha256'],bytes=p['bytes'],terminal_sha256=p['terminal_sha256'],producer_proof_sha256=digest(p),restore_proof_sha256=digest(r),
        qualification_proof_sha256=digest(d['qualification_proof']),runtime_binding_sha256=digest(d['runtime_binding']),producer_policy_sha256=p['producer_policy_sha256'],source_policy_sha256=p['source_policy_sha256'],producer=producer,restorer=restorer)


def evidence_check(rows,expected,*,allow_running_run=False):
    require(type(rows) is list and len(rows)==len(expected),'EXACT_ACTIONS_EVIDENCE_REQUIRED')
    for row,(role,ident,start,finish) in zip(rows,expected):
        require(type(row) is dict and set(row)==EVIDENCE and row['role']==role and row['repository']==REPO
            and all(row[k]==ident[k] for k in ['run_id','run_attempt','source_sha','job_id','api_job_id','permission'])
            and ((row['run_status']=='in_progress' and row['run_conclusion'] is None) if allow_running_run else (row['run_status']=='completed' and row['run_conclusion']=='success'))
            and row['job_status']=='completed' and row['job_conclusion']=='success'
            and utc(row['started_at'])<=utc(start)<=utc(finish)<=utc(row['completed_at']),'SUCCESSFUL_PREDECESSOR_REQUIRED')
    require(utc(rows[0]['completed_at'])<=utc(rows[1]['started_at']),'PREDECESSOR_JOB_ORDER_REQUIRED')


_LIVE=object()
class LiveAcceptance:
    def __init__(self,record,key):
        require(key is _LIVE,'API_VERIFIER_REQUIRED');self.record=record


def check(bundle,policy,*,now,live=None):
    actual=facts(bundle,policy)
    if live is None:
        record=bundle['durability_acceptance']
        require(type(record) is dict and digest(record) in policy.get('root_verified_durability_acceptances',[])
            and record.get('authority_kind')=='ROOT_VERIFIED' and record.get('verifier_procedure_sha256') is None
            and record.get('exporter') is None and record.get('exporter_started_at') is None,'ROOT_VERIFIED_DURABILITY_REQUIRED')
    else:
        require(type(live) is LiveAcceptance,'LIVE_API_ACCEPTANCE_REQUIRED');record=live.record
        require(record.get('authority_kind')=='ROOT_APPROVED_PROCEDURE_VERIFIED'
            and record.get('verifier_procedure_sha256') in [digest(p) for p in policy.get('durability_verifier_procedures',[])],'REGISTERED_VERIFIER_REQUIRED')
    require(set(record)==ACCEPTANCE and record['schema_version']=='weekly-selected-durability-acceptance-v1' and record['state']=='VERIFIED'
        and all(record[k]==v for k,v in actual.items()) and utc(bundle['durability']['restore_proof']['created_at_utc'])<=utc(record['accepted_at'])<=utc(now),'EXACT_DURABILITY_ACCEPTANCE_REQUIRED')
    canary_check(record['qualification_acceptance'],policy,bundle['durability'],now)
    p=bundle['producer_proof'];r=bundle['durability']['restore_proof']
    evidence_check(record['actions_evidence'],[('producer',actual['producer'],p['started_at_utc'],p['created_at_utc']),('restorer',actual['restorer'],r['started_at_utc'],r['created_at_utc'])],allow_running_run=live is not None)
    if live is not None:
        exporter=identity(record['exporter'])
        require(exporter['run_id']==actual['producer']['run_id']==actual['restorer']['run_id'] and exporter['source_sha']==actual['producer']['source_sha']==actual['restorer']['source_sha']
            and len({exporter['process_identity'],actual['producer']['process_identity'],actual['restorer']['process_identity']})==3
            and len({exporter['api_job_id'],actual['producer']['api_job_id'],actual['restorer']['api_job_id']})==3
            and utc(record['actions_evidence'][1]['completed_at'])<=utc(record['exporter_started_at'])<=utc(record['accepted_at']),'INDEPENDENT_EXPORT_JOB_REQUIRED')
    # Expected provenance comes from root registration or live API observations,
    # never from the untrusted restore proof being checked.
    from . import private_draft_store as store
    from types import SimpleNamespace
    expected=record['restorer']
    verifier=SimpleNamespace(binding=store.checked_binding(bundle['durability']['runtime_binding']),process=store.process_identity(),source_sha=expected['source_sha'],run_id=expected['run_id'],
        job=dict(execution_lane='github_actions',workflow_ref=expected['workflow_ref']))
    store.check_proof(verifier,bundle['durability']['qualification_proof'],'qualified',same_run=False)
    store.check_proof(verifier,bundle['durability']['restore_proof'],'restore',same_run=False)
    return record


def verify_current_actions(client,procedure,bundle,policy,canary,*,now,clock=None):
    """Three exact GETs using the existing bounded store transport; no retries.

    Permission evidence is API-fetched workflow bytes matched to the registered
    reviewed job-role declarations. Jobs API does not expose token permissions.
    The current run may be in progress; both predecessor jobs must be successful.
    """
    require(type(procedure) is dict and set(procedure)==PROCEDURE and procedure in policy.get('durability_verifier_procedures',[])
        and procedure['schema_version']=='weekly-durable-verifier-procedure-v1' and procedure['source_sha']==client.source_sha
        and procedure['verifier_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        and procedure['permissions']=={'producer':{'contents':'write','actions':'read'},'restorer':{'contents':'write','actions':'read'},'export':{'contents':'write','actions':'read'}}
        and len({procedure[k] for k in ['producer_job','restorer_job','export_job']})==3,'REGISTERED_VERIFIER_PROCEDURE_REQUIRED')
    actual=facts(bundle,policy);canary_check(canary,policy,bundle['durability'],now)
    require(client.job['execution_lane']=='github_actions' and client.job['job_id']==procedure['export_job'] and client.job['permission']=='write'
        and client.process not in {actual['producer']['process_identity'],actual['restorer']['process_identity']}
        and all(v['run_id']==client.run_id and v['source_sha']==client.source_sha for v in [actual['producer'],actual['restorer']])
        and all(v['workflow_ref']==client.job['workflow_ref'] for v in [actual['producer'],actual['restorer']])
        and actual['producer']['job_id']==procedure['producer_job'] and actual['restorer']['job_id']==procedure['restorer_job'],'SEPARATE_EXPORT_JOB_REQUIRED')
    base=client.path('/actions/runs/'+client.run_id)
    run=client.json(client.allow(base));jobs=client.json(client.allow(base+'/jobs?per_page=100&page=1'))
    require(type(run) is dict and run.get('id')==int(client.run_id) and run.get('head_sha')==client.source_sha
        and run.get('event')=='workflow_dispatch' and run.get('run_attempt')==1 and run.get('status')=='in_progress' and run.get('conclusion') is None
        and run.get('path')=='.github/workflows/lab.yml' and run.get('repository',{}).get('full_name')==REPO and run.get('head_repository',{}).get('full_name')==REPO
        and type(jobs) is dict and type(jobs.get('jobs')) is list and jobs.get('total_count')==len(jobs['jobs']) and len(jobs['jobs'])<=100,'ACTIONS_API_CURRENT_RUN_REQUIRED')
    url=client.path('/contents/.github/workflows/lab.yml?ref='+client.source_sha);client.allowed.add(url)
    workflow=client.json(url)
    require(type(workflow) is dict and workflow.get('type')=='file' and workflow.get('path')=='.github/workflows/lab.yml' and workflow.get('encoding')=='base64','API_WORKFLOW_REQUIRED')
    body=base64.b64decode(workflow['content'].replace('\n',''),validate=True)
    require(len(body)<=128<<10 and hashlib.sha256(body).hexdigest()==procedure['workflow_sha256'],'REGISTERED_WORKFLOW_PERMISSION_BYTES_REQUIRED')
    evidence=[];exporter=None;exporter_started=None
    for role in ['producer','restorer','export']:
        name=procedure[role+'_job'];matches=[j for j in jobs['jobs'] if j.get('name')==name and j.get('run_id')==int(client.run_id) and j.get('head_sha')==client.source_sha]
        require(len(matches)==1,'ACTIONS_API_EXACT_JOB_REQUIRED');job=matches[0]
        if role=='export':
            require(job.get('status')=='in_progress' and job.get('conclusion') is None and type(job.get('id')) is int and job['id']>0
                and job['id'] not in {actual['producer']['api_job_id'],actual['restorer']['api_job_id']} and utc(job['started_at'])<=utc(now),'FRESH_EXPORT_JOB_REQUIRED')
            exporter=identity(dict(execution_lane='github_actions',repository=REPO,run_id=client.run_id,run_attempt=1,source_sha=client.source_sha,process_identity=client.process,
                job_id=name,api_job_id=job['id'],permission='write',workflow_ref=client.job['workflow_ref']));exporter_started=job['started_at']
            continue
        ident=actual[role]
        evidence.append(dict(role=role,repository=REPO,run_id=client.run_id,run_attempt=1,source_sha=client.source_sha,run_status=run['status'],run_conclusion=run['conclusion'],job_id=name,
            api_job_id=job['id'],job_status=job['status'],job_conclusion=job['conclusion'],permission='write',started_at=job['started_at'],completed_at=job['completed_at']))
    accepted_at=(clock() if clock else datetime.now(timezone.utc).isoformat())
    require(utc(now)<=utc(accepted_at),'VERIFIER_COMPLETION_CLOCK')
    record=dict(schema_version='weekly-selected-durability-acceptance-v1',authority_kind='ROOT_APPROVED_PROCEDURE_VERIFIED',state='VERIFIED',accepted_at=accepted_at,
        **actual,exporter=exporter,exporter_started_at=exporter_started,actions_evidence=evidence,qualification_acceptance=canary,verifier_procedure_sha256=digest(procedure))
    live=LiveAcceptance(record,_LIVE);check(bundle,policy,now=accepted_at,live=live);return live
