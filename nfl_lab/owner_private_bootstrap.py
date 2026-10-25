"""Explicit owner-origin private upload, separate from the genuine GHA writer.

No inheritance from Client and no fabricated run/job/environment. Its reviewed
bounded HTTP/inventory primitives are reused as a protocol; owner identity and
archived Actions qualification are authenticated by distinct actual API calls.
"""
from __future__ import annotations

from datetime import datetime,timezone
import os
from pathlib import Path
import re
import time

from . import private_draft_store as core
from . import owner_bootstrap_bundle as bundle

OWNER='NickNicky19'
OWNER_ID=208912933
USER_API='https://api.github.com/user'
VERSION='weekly-owner-private-bootstrap-v1'
ENTRY_KEYS={'schema_version','root_manifest_sha256','bundle_index','payload_asset_id','payload_name','payload_sha256','payload_bytes',
    'producer_process','writer_run_id','writer_origin','binding_sha256','owner_authorization_comment_id','created_at_utc'}
DESCRIPTOR_KEYS={'schema_version','release_binding','root_manifest_asset','entry','manifest_asset_id','manifest_sha256','manifest_bytes'}


def require(value,code):
    if not value:raise core.StoreError(code)


class OwnerBootstrapClient:
    """Owner lane only; core Client's ghs/current-job constructor is unchanged."""
    path=core.Client.path
    browser=core.Client.browser
    bind=core.Client.bind
    request=core.Client.request
    json=core.Client.json
    draft=core.Client.draft
    inventory=core.Client.inventory
    upload=core.Client.upload
    asset=core.Client.asset
    read_asset=core.Client.read_asset

    def __init__(self,token,*,journal,source_sha,transport=None,clock=time.monotonic,process=None,reservation_storage=None):
        require(isinstance(token,str) and token and token.isascii() and not any(c.isspace() for c in token),'EXISTING_OWNER_CREDENTIAL_REQUIRED')
        require(re.fullmatch(r'[a-f0-9]{40}',source_sha),'SOURCE_IDENTITY_REQUIRED')
        self.token=token;self.journal=core.parents_safe(journal)
        require(self.journal.is_dir() and not self.journal.stat().st_mode&0o077,'PRIVATE_JOURNAL_REQUIRED')
        self.source_sha=source_sha;self.run_id=None;self.job=None;self.execution_lane='OWNER_BOOTSTRAP'
        self.clock=clock;self.started=clock();self.started_at=datetime.now(timezone.utc).isoformat()
        self.calls=0;self.transferred=0;self.process=process or core.process_identity()
        require(core.HASH.fullmatch(self.process),'PROCESS_IDENTITY_REQUIRED')
        self.real=transport is None;upstream=transport or core.network
        require(not self.real or reservation_storage is not None,'OWNER_RESERVATION_QUOTA_REQUIRED')
        self.reservation_storage=reservation_storage
        def owner_transport(request,timeout):
            if request.full_url==USER_API:
                # The only added credential realm is the exact actual /user GET.
                require(request.method=='GET','OWNER_ROUTE_FORBIDDEN');request.add_header('Authorization','Bearer '+self.token)
            return upstream(request,timeout)
        self.transport=owner_transport;self.allowed={core.API,USER_API};self.posts={};self.binding=None;self.control_asset_id=None
        self.owner_authorized=False;self.authorized_post_bodies={}

    def reserve(self,key,body,*,name=None):
        if self.reservation_storage is None:return core.Client.reserve(self,key,body,name=name)
        with self.reservation_storage.transaction():
            self.reservation_storage._require(16384)
            core.Client.reserve(self,key,body,name=name)
            self.reservation_storage.snapshot()

    def allow(self,url):
        require(url.startswith(core.API+'/releases/') or url==self.browser(),'OWNER_ROUTE_FORBIDDEN')
        self.allowed.add(url);return url

    def reserve_post(self,url,key,body,*,name=None):
        require(self.binding is not None and url.startswith(core.UPLOAD+'/releases/'+str(self.binding['release_id'])+'/assets?name='),
            'OWNER_ASSET_POST_ONLY_NO_RELEASE_CREATE')
        require(self.owner_authorized and self.authorized_post_bodies.get(name)==(core.sha(body),len(body)),
            'ACTUAL_OWNER_COMMENT_REQUIRED_BEFORE_POST')
        self.reserve(key,body,name=name);self.posts[url]=core.sha(body)


def archived_qualification(binding,q):
    """Closed archived proof verifier; no current GHA identity is asserted."""
    core.checked_binding(binding)
    require(isinstance(q,dict) and set(q)==core.BASE_PROOF_FIELDS|core.PHASE_FIELDS['qualified'],'CLOSED_QUALIFICATION')
    before=q['before_proof'];read=q['read_proof'];proofs=[before,read,q]
    require(len({p.get('process_identity') for p in proofs})==3,'QUALIFICATION_PROCESSES')
    previous=None;now=datetime.now(timezone.utc);jobs=[]
    for phase,p,permission in zip(('write_pin','read_boundary','qualified'),proofs,('write','read','write')):
        require(isinstance(p,dict) and set(p)==core.BASE_PROOF_FIELDS|core.PHASE_FIELDS[phase],'CLOSED_QUALIFICATION')
        require(p['schema_version']=='weekly-private-proof-v2.1' and p['phase']==phase and p['operation']==core.PHASE_OPERATION[phase]
            and p['repository']==core.REPO and type(p['run_attempt']) is int and p['run_attempt']==1 and p['run_id']==q['run_id'] and p['source_sha']==q['source_sha']
            and re.fullmatch(r'[1-9][0-9]{0,19}',p['run_id']) and re.fullmatch(r'[a-f0-9]{40}',p['source_sha'])
            and p['binding_sha256']==core.sha(core.canonical(binding)) and p['config_sha256']==core.config_sha()
            and core.HASH.fullmatch(p['process_identity']),'ARCHIVED_QUALIFICATION_BINDING')
        j=p['job'];require(set(j)==core.JOB_FIELDS and j['execution_lane']=='github_actions' and j['run_authenticated'] is True
            and j['permission']==permission and j['workflow_sha']==p['source_sha'] and j['event_name']=='workflow_dispatch'
            and re.fullmatch(re.escape(core.REPO)+r'/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+',j['workflow_ref'])
            and re.fullmatch(r'[A-Za-z0-9_-]+',j['job_id']),'GENUINE_ARCHIVED_GHA_JOB_REQUIRED')
        core.positive(j['api_job_id']);jobs.append(j['api_job_id'])
        require(type(p['HTTP_calls']) is int and {'write_pin':7,'read_boundary':17,'qualified':7}[phase]<=p['HTTP_calls']<=core.MAX_CALLS
            and type(p['transfer_bytes']) is int and 0<p['transfer_bytes']<=core.TRANSFER_CAP,'ARCHIVED_OPERATION_LIMITS')
        start,end=core.utc(p['started_at_utc']),core.utc(p['created_at_utc'])
        require((previous is None or previous<=start) and start<=end<=now,'ARCHIVED_PROOF_CLOCK');previous=end
    require(len(set(jobs))==3 and before['job']['workflow_ref']==read['job']['workflow_ref']==q['job']['workflow_ref'],'ARCHIVED_JOB_CHAIN')
    require(before['exact_canary_readback'] is True and before['draft_before_after'] is True and read['controls_passed'] is True
        and read['all10_denied'] is True,'ACTUAL_ACL_PROOF_REQUIRED');core.validate_routes(read['routes'])
    require(q['engineering_boundary_v2'] is True and q['strict_v1_unchanged']=='INCONCLUSIVE' and q['restricted_upload_authorized'] is False
        and q['before_sha256']==read['before_sha256']==core.sha(core.canonical(before)) and q['read_sha256']==core.sha(core.canonical(read))
        and q['before_process_identity']==before['process_identity'] and q['read_process_identity']==read['process_identity']
        and q['before_completed_at_utc']==before['created_at_utc'] and q['read_completed_at_utc']==read['created_at_utc'],
        'ARCHIVED_QUALIFICATION_CHAIN')
    return q


def exact_get(client,url):
    require(url.startswith(core.API+'/issues/comments/') or url.startswith(core.API+'/actions/runs/'),'EXACT_ARCHIVED_ROUTE')
    client.allowed.add(url);return client.json(url)


def authenticate_past_run(client,q):
    url=core.API+'/actions/runs/'+q['run_id'];run=exact_get(client,url);jobs=exact_get(client,url+'/jobs?per_page=100&page=1')
    require(run.get('id')==int(q['run_id']) and run.get('head_sha')==q['source_sha'] and run.get('event')=='workflow_dispatch'
        and run.get('run_attempt')==1 and run.get('status')=='completed' and run.get('conclusion')=='success'
        and run.get('path')=='.github/workflows/lab.yml' and run.get('repository',{}).get('full_name')==core.REPO
        and run.get('head_repository',{}).get('full_name')==core.REPO,'ACTUAL_QUALIFIED_RUN_REQUIRED')
    require(type(jobs.get('total_count')) is int and isinstance(jobs.get('jobs'),list) and jobs['total_count']==len(jobs['jobs'])<=100,'COMPLETE_GHA_JOB_LIST')
    for proof in (q['before_proof'],q['read_proof'],q):
        matches=[j for j in jobs['jobs'] if j.get('id')==proof['job']['api_job_id']]
        require(len(matches)==1,'ACTUAL_QUALIFIED_JOB_REQUIRED');job=matches[0]
        require(job.get('name')==proof['job']['job_id'] and job.get('head_sha')==q['source_sha'] and job.get('run_id')==int(q['run_id'])
            and job.get('status')=='completed' and job.get('conclusion')=='success'
            and core.utc(job['started_at'])<=core.utc(proof['started_at_utc'])<=core.utc(proof['created_at_utc'])<=core.utc(job['completed_at']),
            'ACTUAL_QUALIFIED_JOB_REQUIRED')


def validate_root(manifest):
    keys={'schema_version','repository','source_sha','source_code_pins','release_binding','qualification','rights_review','source_policy_sha256',
        'bundles','pending_raw_archive','total_payload_bytes','remote_metadata_reserve_bytes','public_export','scope_encoding'}
    require(set(manifest)==keys and manifest['schema_version']=='weekly-owner-bootstrap-root-manifest-v1'
        and manifest['repository']==core.REPO and manifest['public_export'] is False
        and re.fullmatch(r'[a-f0-9]{40}',manifest['source_sha']) and store_hashes(manifest['source_code_pins'])
        and manifest['source_policy_sha256']=='e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441',
        'CLOSED_ROOT_MANIFEST')
    archived_qualification(manifest['release_binding'],manifest['qualification'])
    require(1<=len(manifest['bundles'])<=8 and manifest['remote_metadata_reserve_bytes']==262144,'ROOT_BUNDLE_CAP')
    all_files=[]
    for i,p in enumerate(manifest['bundles']):
        require(set(p)=={'index','bytes','sha256','inflated_bytes','files'} and p['index']==i and type(p['bytes']) is int
            and 0<p['bytes']<=core.ASSET_CAP and core.HASH.fullmatch(p['sha256']) and 0<p['inflated_bytes']<=bundle.INFLATED
            and len(p['files'])<=64,'ROOT_BUNDLE_CAP');all_files.extend(p['files'])
    bundle.validate_files(all_files)
    require(all(i['origin']['source_policy_sha256']==manifest['source_policy_sha256'] for i in all_files),'ORIGIN_SOURCE_POLICY')
    require(sum(p['bytes'] for p in manifest['bundles'])==manifest['total_payload_bytes']
        and manifest['total_payload_bytes']+262144+manifest['release_binding']['canary_bytes']<=core.TOTAL_CAP,'ROOT_RUNTIME_CAP')
    rights=manifest['rights_review']
    require(rights.get('schema_version')=='weekly-owner-bootstrap-rights-review-v1' and rights.get('approved') is True
        and rights.get('basis')=='OWNER_DELEGATED_OCT24_PRIVATE_ONLY' and rights.get('human_review_claim') is False
        and set(i['logical_path'] for i in all_files)<=set(rights['approved_logical_paths']),'ROOT_RIGHTS_REVIEW')
    return manifest


def store_hashes(document):
    return isinstance(document,dict) and bool(document) and all(isinstance(k,str) and core.HASH.fullmatch(v) for k,v in document.items())


def authorization_body(manifest):
    validate_root(manifest);q=manifest['qualification']
    approval=dict(schema_version='weekly-owner-bootstrap-authorization-v1',repository=core.REPO,authorization_basis='OWNER_DELEGATED_OCT24_PRIVATE_ONLY',
        human_review_claim=False,root_manifest_sha256=core.sha(core.canonical(manifest)),root_manifest_bytes=len(core.canonical(manifest)),source_sha=manifest['source_sha'],source_code_pins=manifest['source_code_pins'],
        release_binding_sha256=core.sha(core.canonical(manifest['release_binding'])),qualification_sha256=core.sha(core.canonical(q)),
        qualified_run_id=q['run_id'],qualified_head_sha=q['source_sha'],qualified_job_ids=[p['job']['api_job_id'] for p in (q['before_proof'],q['read_proof'],q)],
        rights_review_sha256=core.sha(core.canonical(manifest['rights_review'])),payloads=[{k:p[k] for k in ('index','bytes','sha256')} for p in manifest['bundles']])
    return 'NFL LAB OWNER BOOTSTRAP V1\n'+core.canonical(approval).decode()


def check_comment(client,manifest,comment_id,*,at):
    core.positive(comment_id);url=core.API+'/issues/comments/'+str(comment_id);comment=exact_get(client,url)
    require(comment.get('id')==comment_id and comment.get('url')==url and comment.get('user',{}).get('login')==OWNER
        and comment.get('user',{}).get('id')==OWNER_ID and comment.get('author_association')=='OWNER'
        and comment.get('body')==authorization_body(manifest) and comment.get('created_at')==comment.get('updated_at'),
        'ACTUAL_UNEDITED_OWNER_COMMENT_REQUIRED')
    created=core.utc(comment['created_at']);require(core.utc(manifest['qualification']['created_at_utc'])<=created<=at
        and 0<=(at-created).total_seconds()<=3600 and at<=datetime.now(timezone.utc),'FRESH_OWNER_AUTHORIZATION_REQUIRED')
    return comment_id


def verify_canary(client):
    client.draft();b=client.binding
    body=client.read_asset(b['canary_asset_id'],b['canary_name'],117,b['canary_sha256'])
    require(body==core.probe.fixture(b['origin_run_id']),'QUALIFIED_CANARY_CHANGED');client.draft()


def upload_one(client,manifest,index,comment_id,body):
    require(type(client) is OwnerBootstrapClient and client.execution_lane=='OWNER_BOOTSTRAP','OWNER_LANE_REQUIRED')
    validate_root(manifest);require(client.source_sha==manifest['source_sha'],'OWNER_SOURCE_CHANGED')
    client.bind(manifest['release_binding']);require(type(index) is int and 0<=index<len(manifest['bundles']),'EXACT_FROZEN_BUNDLE_REQUIRED');record=manifest['bundles'][index]
    require(len(body)==record['bytes'] and core.sha(body)==record['sha256'],'EXACT_FROZEN_BUNDLE_REQUIRED')
    user=client.json(USER_API);repo=client.json(core.API)
    require(user.get('login')==OWNER and user.get('id')==OWNER_ID and user.get('type')=='User'
        and repo.get('full_name')==core.REPO and repo.get('owner',{}).get('id')==OWNER_ID
        and repo.get('permissions',{}).get('push') is True,'ACTUAL_OWNER_AND_REPO_PUSH_REQUIRED')
    at=datetime.now(timezone.utc);check_comment(client,manifest,comment_id,at=at);authenticate_past_run(client,manifest['qualification']);verify_canary(client)
    client.owner_authorized=True
    root_body=core.canonical(manifest);require(len(root_body)<=core.META_CAP,'PRIVATE_ROOT_MANIFEST_CAP')
    root_sha=core.sha(root_body);root_name='manifest-'+root_sha+'.json'
    client.reserve('owner-bootstrap-operation:'+root_sha+':'+str(index),core.canonical(dict(root_manifest_sha256=root_sha,bundle_index=index)))
    assets,_=client.inventory();present=[a for a in assets if a['name']==root_name]
    if present:
        require(len(present)==1,'PRIVATE_ROOT_MANIFEST_IDENTITY');root_asset=client.asset(present[0],root_name,len(root_body),root_sha)
    else:
        client.authorized_post_bodies[root_name]=(root_sha,len(root_body));root_asset=client.upload(root_name,root_body)
    require(client.read_asset(root_asset['id'],root_name,len(root_body),root_sha)==root_body,'PRIVATE_ROOT_MANIFEST_READBACK')
    name='blob-'+record['sha256']+'.bin';client.authorized_post_bodies[name]=(record['sha256'],len(body))
    asset=client.upload(name,body,reuse_completed=False)
    require(client.read_asset(asset['id'],name,len(body),record['sha256'])==body,'OWNER_PAYLOAD_READBACK');client.draft()
    entry=dict(schema_version='weekly-owner-bootstrap-remote-entry-v1',root_manifest_sha256=core.sha(core.canonical(manifest)),bundle_index=index,payload_asset_id=asset['id'],payload_name=name,
        payload_sha256=record['sha256'],payload_bytes=len(body),producer_process=client.process,writer_run_id=None,
        writer_origin=dict(execution_lane='OWNER_BOOTSTRAP',owner_login=OWNER,owner_user_id=OWNER_ID,source_sha=client.source_sha),
        binding_sha256=core.sha(core.canonical(client.binding)),owner_authorization_comment_id=comment_id,created_at_utc=at.isoformat())
    encoded=core.canonical(entry);require(len(encoded)<=core.META_CAP,'REMOTE_DESCRIPTOR_CAP')
    client.authorized_post_bodies['manifest-'+core.sha(encoded)+'.json']=(core.sha(encoded),len(encoded))
    saved=client.upload('manifest-'+core.sha(encoded)+'.json',encoded)
    require(client.read_asset(saved['id'],'manifest-'+core.sha(encoded)+'.json',len(encoded),core.sha(encoded))==encoded,'OWNER_DESCRIPTOR_READBACK')
    client.inventory();client.draft()
    return dict(schema_version=VERSION+'-descriptor',release_binding=client.binding,
        root_manifest_asset=dict(asset_id=root_asset['id'],name=root_name,bytes=len(root_body),sha256=root_sha),
        entry=entry,manifest_asset_id=saved['id'],manifest_sha256=core.sha(encoded),manifest_bytes=len(encoded))


def restore_owner_bundle(client,descriptor,*,expected_root_sha256,expected_comment_id):
    """Genuine fresh GHA client only; old core.restore schema is not relaxed."""
    require(type(client) is core.Client and client.job['execution_lane']=='github_actions','GENUINE_GHA_RESTORE_REQUIRED')
    client.authenticate_actions_job()
    require(set(descriptor)==DESCRIPTOR_KEYS and descriptor['schema_version']==VERSION+'-descriptor' and set(descriptor['entry'])==ENTRY_KEYS,'CLOSED_OWNER_DESCRIPTOR')
    entry=descriptor['entry'];encoded=core.canonical(entry)
    require(entry['root_manifest_sha256']==expected_root_sha256 and entry['owner_authorization_comment_id']==expected_comment_id,'OWNER_ROOT_EXPECTATION')
    client.bind(descriptor['release_binding']);client.draft();root=descriptor['root_manifest_asset']
    require(set(root)=={'asset_id','name','bytes','sha256'} and root['sha256']==expected_root_sha256
        and root['name']=='manifest-'+expected_root_sha256+'.json' and type(root['bytes']) is int and 0<root['bytes']<=core.META_CAP,'PRIVATE_ROOT_LOCATOR')
    raw=client.read_asset(root['asset_id'],root['name'],root['bytes'],root['sha256'])
    try:manifest=validate_root(__import__('json').loads(raw))
    except (ValueError,UnicodeError):raise core.StoreError('PRIVATE_ROOT_MANIFEST_JSON') from None
    require(manifest['release_binding']==descriptor['release_binding'],'PRIVATE_ROOT_RELEASE_MISMATCH')
    require(entry['schema_version']=='weekly-owner-bootstrap-remote-entry-v1' and entry['writer_run_id'] is None
        and entry['writer_origin']==dict(execution_lane='OWNER_BOOTSTRAP',owner_login=OWNER,owner_user_id=OWNER_ID,source_sha=manifest['source_sha'])
        and entry['producer_process']!=client.process and core.HASH.fullmatch(entry['producer_process'])
        and core.sha(core.canonical(manifest))==entry['root_manifest_sha256']==expected_root_sha256 and entry['owner_authorization_comment_id']==expected_comment_id
        and core.sha(encoded)==descriptor['manifest_sha256'] and len(encoded)==descriptor['manifest_bytes'],
        'OWNER_DESCRIPTOR_BINDING')
    client.bind(manifest['release_binding']);require(entry['binding_sha256']==core.sha(core.canonical(client.binding)),'OWNER_RELEASE_BINDING')
    check_comment(client,manifest,expected_comment_id,at=core.utc(entry['created_at_utc']));authenticate_past_run(client,manifest['qualification']);verify_canary(client)
    remote=client.read_asset(descriptor['manifest_asset_id'],'manifest-'+core.sha(encoded)+'.json',len(encoded),core.sha(encoded))
    require(remote==encoded,'OWNER_DESCRIPTOR_REMOTE_HASH')
    index=entry['bundle_index'];require(type(index) is int and 0<=index<len(manifest['bundles']),'OWNER_BUNDLE_INDEX');record=manifest['bundles'][index]
    require((entry['payload_sha256'],entry['payload_bytes'],entry['payload_name'])==(record['sha256'],record['bytes'],'blob-'+record['sha256']+'.bin'),'OWNER_PAYLOAD_BINDING')
    body=client.read_asset(entry['payload_asset_id'],entry['payload_name'],record['bytes'],record['sha256']);client.draft()
    return body,record,dict(schema_version=VERSION+'-restore',execution_lane='github_actions',restore_run_id=client.run_id,
        origin_execution_lane='OWNER_BOOTSTRAP',origin_writer_run_id=None,owner_authorization_comment_id=expected_comment_id,
        root_manifest_sha256=expected_root_sha256,payload_sha256=record['sha256'],bytes=len(body),exact_remote_readback=True,
        separate_process=True,model_decodes=0,private_durability_qualified=False)
