"""Independent calendar/ownership/failure probes; all service values fictional."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nfl_lab import audit_weekly_hosted_v1 as hosted, audit_weekly_epoch_v1 as epoch
from nfl_lab import private_draft_store as store, operational_failure_v1 as failure
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references
from test_audit_weekly_template_v1 import dual_document


@pytest.fixture
def pending_failure(tmp_path):
    """Invented completed job and opaque core envelope; no native authority."""
    import base64,gzip
    from nfl_lab import audit_weekly_template_v1 as t
    binding=dict(schema_version='weekly-private-draft-binding-v2',repository=store.REPO,runtime_id='d'*32,
        origin_run_id='100',release_id=91,tag_name='weekly-private-runtime-v2-'+'d'*32,
        canary_asset_id=5,canary_name='canary-'+'a'*64+'.txt',canary_sha256='a'*64,canary_bytes=117,
        browser_tag='untagged-'+'e'*20,config_sha256=store.config_sha())
    record=dict(schema_version='weekly-private-POST-reservation-v2',key='asset:blob-'+store.sha(b'abc')+'.bin',
        bytes=3,sha256=store.sha(b'abc'),name='blob-'+store.sha(b'abc')+'.bin')
    source='a'*40;workflow=store.REPO+'/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1'
    old=dict(approved=True,repository=store.REPO,mode=hosted.MODE,owner_authorization='OWNER_NFL_AUDIT_CONTINUATION_20261025',
        source_sha=source,workflow_ref=workflow,jobs=hosted.JOBS,qualified_runtime=dict(binding=binding),
        issued_at_utc='2025-12-31T23:59:00Z',effective_epoch=dict(controller_context=None))
    def wrap(prefix, item=None):
        item=record if item is None else item
        raw=store.canonical(item)
        return dict(relative_path=prefix+store.sha(item['key'].encode())+'.reservation.json',
            bytes=len(raw),sha256=store.sha(raw),body_base64=base64.b64encode(raw).decode())
    old_record=dict(record,sha256=store.sha(b'old'),name='blob-'+store.sha(b'old')+'.bin',key='asset:blob-'+store.sha(b'old')+'.bin')
    journals=dict(schema_version=hosted.VERSION+'-original-post-journals',records=[wrap('journal/'),
        wrap('archive-produce/journal/'),wrap('origin/old/journal/',old_record)])
    def pack():
        root_raw=store.canonical(old);journal_raw=store.canonical(journals)
        attachments=[];encoded=[]
        for label,kind,raw in [('owner-root','control',root_raw),('original-post-reservations','post_reservation',journal_raw)]:
            attachments.append(dict(label=label,kind=kind,reference=dict(path='/fictional/'+label+'.json',
                bytes=len(raw),sha256=store.sha(raw))))
            encoded.append(dict(label=label,base64=base64.b64encode(raw).decode()))
        request=dict(schema_version=failure.VERSION+'-request',operation='producer',state='FAILED',
            attempt=dict(repository=store.REPO,run_id='200',run_attempt=1,source_sha=source,
                job_id=hosted.JOBS['produce'],workflow_ref=workflow),input_contract_sha256=store.sha(root_raw),
            failure=dict(kind='AMBIGUOUS_POST',code='HTTP_OR_RATE_AMBIGUITY',exit_code=1),
            clocks=dict(started_at_utc='2026-01-01T00:00:01Z',observed_at_utc='2026-01-01T00:00:30Z',original={}),
            attachments=attachments)
        body=gzip.compress(store.canonical(dict(schema_version=failure.VERSION+'-envelope',
            classification='FAILURE_EVIDENCE_ONLY',request=request,attachments=encoded,gates=failure.NEGATIVE_GATES)),mtime=0)
        entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=failure.payload_manifest(body),
            payload_asset_id=7,payload_name='blob-'+store.sha(body)+'.bin',producer_process='c'*64,
            binding_sha256=t.digest(binding),writer_run_id='200')
        manifest=store.canonical(entry)
        handoff=dict(schema_version=hosted.VERSION+'-failure-handoff',binding=binding,root_go_sha256=store.sha(root_raw),
            descriptor=dict(entry=entry,manifest_asset_id=8,manifest_sha256=store.sha(manifest),manifest_bytes=len(manifest)))
        assets=[dict(id=7,name=entry['payload_name'],size=len(body),digest='sha256:'+store.sha(body),state='uploaded'),
            dict(id=8,name='manifest-'+store.sha(manifest)+'.json',size=len(manifest),digest='sha256:'+store.sha(manifest),state='uploaded')]
        return handoff,assets,{7:body,8:manifest}
    handoff,assets,bodies=pack()
    run=dict(id=200,head_sha=source,run_attempt=1,event='workflow_dispatch',path='.github/workflows/lab.yml',
        head_branch='research/weekly-storage-probe-v1',repository=dict(full_name=store.REPO),
        head_repository=dict(full_name=store.REPO),status='completed',conclusion='failure',actor=dict(login='NickNicky19',id=208912933))
    job=dict(id=201,run_id=200,head_sha=source,name=hosted.JOBS['produce'],status='completed',conclusion='failure',
        started_at='2026-01-01T00:00:00Z',completed_at='2026-01-01T00:01:00Z')
    class Metadata:
        def __init__(self):self.binding=binding;self.calls=[]
        def allow(self,url):return url
        def draft(self):self.calls.append('draft')
        def inventory(self):return assets,sum(a['size'] for a in assets)
        def read_asset(self,identity,name,size,digest):
            self.calls.append('GET');value=bodies[identity]
            assert len(value)==size and store.sha(value)==digest
            return value
        def json(self,url):
            self.calls.append('GET')
            if '/workflows/' in url:return dict(total_count=2,workflow_runs=[run,dict(run,id=100,conclusion='success')])
            if '/jobs?' in url:return dict(total_count=1,jobs=[job])
            return run
    spec=dict(schema_version=t.PENDING_RECOVERY,handoffs=[handoff],pending_reservations=[record])
    runner=hosted.Runner.__new__(hosted.Runner);runner.journal=tmp_path/'fresh-journal';runner.journal.mkdir()
    runner.go=dict(qualified_runtime=dict(binding=binding),issued_at_utc='2026-01-01T00:02:00Z',
        effective_epoch=dict(schema_version=t.RECURRING_V5,pending_post_recovery=spec))
    runner.client=Metadata();runner.pending_scope_authenticated=False
    runner.pending_metadata_client=lambda:runner.client
    return SimpleNamespace(runner=runner,record=record,spec=spec,assets=assets,run=run,job=job,
        old=old,journals=journals,pack=pack,handoff=handoff)


def test_pending_recovery_authenticates_exact_failure_and_deduplicates_current_scopes(pending_failure):
    q=pending_failure;r=q.runner
    actual=hosted.authenticated_pending_records(r.client,q.handoff,q.assets,before=r.go['issued_at_utc'])
    assert actual==[q.record] and q.record['bytes']==len(b'abc')
    r.authenticate_pending_posts()
    assert r.pending_scope_authenticated and len(list(r.journal.glob('*.reservation.json')))==1
    assert all(call in {'GET','draft'} for call in r.client.calls)


@pytest.fixture
def failed_first_recovery(pending_failure):
    return _failed_first_recovery_case(pending_failure)


def _failed_first_recovery_case(pending_failure, *, original_scope=None, calendar_plan=None):
    """Invented Core/claim native bytes, no old choice or forecast body."""
    import base64,gzip
    from nfl_lab import audit_weekly_template_v1 as t,gha_private_checkpoint as cp
    q=pending_failure;r=q.runner;binding=r.client.binding;old_run=str(q.run['id'])
    q.job['run_id']=int(old_run)
    plan=dict(kind='FUTURE_CAPABLE',season=2026,week=8,calendar_sha256='4'*64,
        game_cutoffs={f'fictional-{n}':'2026-10-29T19:45:00Z' for n in range(14)},deadline_utc='2026-10-29T19:45:00Z')
    old_scope=dict(schema_version=t.FIRST_PRIMARY,retained_epoch_sha256='1'*64,retained_choice_sha256='2'*64,
        retained_root_go_sha256='3'*64,claim_binding_sha256=t.digest(binding))
    if original_scope is not None:old_scope.update(original_scope,claim_binding_sha256=t.digest(binding))
    if calendar_plan is not None:plan=deepcopy(calendar_plan)
    q.old.update(operation='RECURRING_CAPTURE',issued_at_utc='2026-10-27T20:00:00Z',expires_at_utc='2026-10-27T21:00:00Z',
        cutoff_lead_seconds=900,effective_epoch=dict(schema_version=t.RECURRING_V5,controller_context=old_scope,
            previous_checkpoint=None,previous_capture=dict(feed_sha256='a'*64,receipt_sha256='b'*64),plan=plan))
    q.job.update(started_at='2026-10-27T20:00:01Z',completed_at='2026-10-27T20:01:00Z')
    reader=dict(q.job,id=202,name=hosted.JOBS['restore'],conclusion='success',started_at='2026-10-27T20:01:01Z',completed_at='2026-10-27T20:02:00Z')
    identity=dict(repository=store.REPO,run_id=old_run,run_attempt=1,source_sha=q.old['source_sha'],
        workflow_ref=q.old['workflow_ref'],job_id=hosted.JOBS['produce'],api_job_id=201,process_identity='9'*64,
        execution_lane='github_actions',permission='write')
    claim=store.canonical(t.first_primary_claim(q.old));payload=dict(schema_version='weekly-private-payload-v2',
        payload_kind='runtime_manifest',format='json',bytes=len(claim),sha256=store.sha(claim),source_policy_sha256=cp.POLICY_SHA)
    entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=payload,payload_asset_id=17,
        payload_name='blob-'+store.sha(claim)+'.bin',producer_process=identity['process_identity'],
        binding_sha256=t.digest(binding),writer_run_id=old_run)
    manifest=store.canonical(entry)
    claim_assets=[dict(id=17,name=entry['payload_name'],size=len(claim),digest='sha256:'+store.sha(claim),state='uploaded'),
        dict(id=18,name='manifest-'+store.sha(manifest)+'.json',size=len(manifest),digest='sha256:'+store.sha(manifest),state='uploaded')]
    claim_records=[]
    for a in claim_assets:
        rec=dict(schema_version='weekly-private-POST-reservation-v2',key='asset:'+a['name'],name=a['name'],
            bytes=a['size'],sha256=a['digest'][7:]);claim_records.append(rec);raw=store.canonical(rec)
        q.journals['records'].append(dict(relative_path='journal/'+store.sha(rec['key'].encode())+'.reservation.json',
            bytes=len(raw),sha256=store.sha(raw),body_base64=base64.b64encode(raw).decode()))
    parent=store.canonical(dict(actual_identity=identity,actual_started_at='2026-10-27T20:00:02Z'))
    documents={'owner-root':q.old,'original-post-reservations':q.journals,
        'file-graph':dict(schema_version=hosted.VERSION+'-failed-file-graph',files=[dict(relative_path='runtime/WEEKLY_CHOICE.json',
            reference=dict(path='/fictional/LOST_WEEK8_CHOICE.json',bytes=14111,sha256='e'*64))]),
        'secondary-preservation-failure':dict(state='FAILED_RETAINED',reason='SINGLE_FILE_BUNDLE_CAP',
            original_failure_replaced=False,partial_forecast_durability_established=False,successful_forecast=False,public_release=False),
        'complete-auxiliary-controls':dict(schema_version=hosted.VERSION+'-complete-auxiliary-controls',files=[dict(
            relative_path='PARENT_STARTED.json',bytes=len(parent),sha256=store.sha(parent),body_base64=base64.b64encode(parent).decode())])}
    for label,state in [('phase-02','FIRST_FUTURE_PRIMARY_PREVALUE_METADATA_READY_LOCAL'),
            ('phase-06','PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'),('phase-07','ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE')]:
        documents[label]=dict(exit_code=0,status=dict(state=state,fits=0,public_release=False))
    for label in ('phase-08','phase-09'):
        documents[label]=dict(status=dict(state='FAILED_RETAINED',reason='SINGLE_FILE_BUNDLE_CAP',successful_forecast=False,public_release=False))
    def pack():
        attachments=[];values=[]
        for label,d in documents.items():
            raw=store.canonical(d)
            attachments.append(dict(label=label,kind='post_reservation' if label=='original-post-reservations' else 'control',
                reference=dict(path='/fictional/'+label+'.json',bytes=len(raw),sha256=store.sha(raw))))
            values.append(dict(label=label,base64=base64.b64encode(raw).decode()))
        request=dict(schema_version=failure.VERSION+'-request',operation='producer',state='FAILED',
            attempt=dict(repository=store.REPO,run_id=old_run,run_attempt=1,source_sha=q.old['source_sha'],
                job_id=hosted.JOBS['produce'],workflow_ref=q.old['workflow_ref']),input_contract_sha256=t.digest(q.old),
            failure=dict(kind='EXCEPTION',code='SINGLE_FILE_BUNDLE_CAP',exit_code=1),
            clocks=dict(started_at_utc='2026-10-27T20:00:02Z',observed_at_utc='2026-10-27T20:00:50Z',original={}),attachments=attachments)
        body=gzip.compress(store.canonical(dict(schema_version=failure.VERSION+'-envelope',classification='FAILURE_EVIDENCE_ONLY',
            request=request,attachments=values,gates=failure.NEGATIVE_GATES)),mtime=0)
        core=dict(entry,payload=failure.payload_manifest(body),payload_asset_id=7,payload_name='blob-'+store.sha(body)+'.bin',producer_process='c'*64)
        encoded=store.canonical(core)
        handoff=dict(schema_version=hosted.VERSION+'-failure-handoff',binding=binding,root_go_sha256=t.digest(q.old),
            descriptor=dict(entry=core,manifest_asset_id=8,manifest_sha256=store.sha(encoded),manifest_bytes=len(encoded)))
        assets=[dict(id=7,name=core['payload_name'],size=len(body),digest='sha256:'+store.sha(body),state='uploaded'),
            dict(id=8,name='manifest-'+store.sha(encoded)+'.json',size=len(encoded),digest='sha256:'+store.sha(encoded),state='uploaded'),*claim_assets]
        return handoff,assets,{7:body,8:encoded,17:claim,18:manifest}
    handoff,assets,bodies=pack()
    scope=dict(old_scope,schema_version=t.FAILED_FIRST_RECOVERY,failed_root_go_sha256=t.digest(q.old),
        old_week8_choice_body_missing=True,old_forecast_bodies_missing=True)
    root=dict(r.go,operation='RECURRING_CAPTURE',source_sha='b'*40,expires_at_utc='2026-10-27T21:00:00Z',
        issued_at_utc='2026-10-27T20:03:00Z',cutoff_lead_seconds=900,effective_epoch=dict(q.old['effective_epoch'],
            controller_context=scope,pending_post_recovery=dict(schema_version=t.PENDING_RECOVERY,handoffs=[handoff],
                pending_reservations=sorted([q.record,*claim_records],key=lambda v:v['key']))))
    client=r.client;client.run_id='300';client.source_sha='b'*40;client.process=store.process_identity();client.transferred=0
    client.job=dict(execution_lane='github_actions',workflow_ref=q.old['workflow_ref'],job_id=hosted.JOBS['produce'],
        api_job_id=301,permission='write',run_authenticated=True,workflow_sha='b'*40,event_name='workflow_dispatch')
    client.inventory=lambda:(assets,sum(a['size'] for a in assets))
    def read_asset(i,name,size,digest):
        client.calls.append('GET');raw=bodies[i]
        assert len(raw)==size and store.sha(raw)==digest
        client.transferred+=len(raw)
        return raw
    client.read_asset=read_asset
    client.json=lambda url:dict(total_count=2,jobs=[q.job,reader]) if '/jobs?' in url else q.run
    def claim_reader():
        from copy import copy
        fresh=copy(client);fresh.transferred=0
        def read(i,name,size,digest):
            fresh.calls.append('GET');raw=bodies[i]
            assert len(raw)==size and store.sha(raw)==digest
            fresh.transferred+=len(raw);return raw
        fresh.read_asset=read
        return fresh
    return SimpleNamespace(root=root,old=q.old,client=client,assets=assets,bodies=bodies,documents=documents,
        handoff=handoff,reader=reader,job=q.job,pack=pack,claim_assets=claim_assets,claim_records=claim_records,
        journals=q.journals,claim_reader=claim_reader,at=hosted.utc('2026-10-27T20:03:01Z'))


def test_failed_first_recovery_authenticates_Core_native_claim_and_POST_pair(failed_first_recovery):
    from nfl_lab import audit_weekly_operations_v1 as o
    import pickle
    q=failed_first_recovery
    proof=o.authenticate_failed_first_recovery(q.client,q.root,authenticate=lambda:None,claim_reader=q.claim_reader,clock=lambda:q.at)
    assert proof.verify(q.root) is proof
    assert proof.document['old_week8_choice_body_missing'] is proof.document['old_forecast_bodies_missing'] is True
    assert proof.document['failed_capture_qualified'] is False
    assert proof.document['original_week8_choice_commitment']==dict(bytes=14111,sha256='e'*64)
    assert all(c in {'GET','draft'} for c in q.client.calls)
    with pytest.raises(o.OperationsError,match='CANNOT_BE_SERIALIZED'):pickle.dumps(proof)
    proof.document['failed_capture_qualified']=True
    with pytest.raises(o.OperationsError,match='INTEGRITY'):proof.verify(q.root)


@pytest.mark.parametrize('damage',['claim_missing','claim_manifest','claim_POST','reader_failure','same_reader',
    'reader_clock','failed_actor','cutoff','old_method_anchor','missing_gap','Core_phase','saved_owner'])
def test_failed_first_recovery_rejects_damaged_native_lineage(failed_first_recovery,damage):
    from nfl_lab import audit_weekly_operations_v1 as o,audit_weekly_template_v1 as t
    q=failed_first_recovery;auth=lambda:None
    if damage=='claim_missing':q.assets.remove(q.claim_assets[0])
    elif damage=='claim_manifest':q.claim_assets[1]['digest']='sha256:'+'0'*64
    elif damage=='claim_POST':q.journals['records']=[v for v in q.journals['records'] if v['relative_path']!='journal/'+store.sha(q.claim_records[0]['key'].encode())+'.reservation.json']
    elif damage=='reader_failure':q.reader['conclusion']='failure'
    elif damage=='same_reader':q.reader['id']=q.job['id']
    elif damage=='reader_clock':q.reader['started_at']='2026-10-27T20:00:10Z'
    elif damage=='failed_actor':pass
    elif damage=='cutoff':q.root['effective_epoch']['plan']=dict(q.root['effective_epoch']['plan'],deadline_utc='2026-10-29T20:45:00Z')
    elif damage=='old_method_anchor':q.root['effective_epoch']['controller_context']['retained_choice_sha256']='f'*64
    elif damage=='missing_gap':q.documents['secondary-preservation-failure']['partial_forecast_durability_established']=True
    elif damage=='Core_phase':q.documents['phase-06']['status']['state']='NOT_COMPLETE'
    else:auth=lambda:True
    if damage=='failed_actor':
        original=q.client.json
        q.client.json=lambda url:dict(original(url),actor=dict(login='github-actions[bot]',id=41898282)) if '/jobs?' not in url else original(url)
    if damage in {'claim_POST','missing_gap','Core_phase'}:
        handoff,assets,bodies=q.pack();q.assets[:]=assets;q.bodies.clear();q.bodies.update(bodies)
        q.root['effective_epoch']['pending_post_recovery']['handoffs']=[handoff]
    with pytest.raises((ValueError,store.StoreError,AssertionError)):
        o.authenticate_failed_first_recovery(q.client,q.root,authenticate=auth,claim_reader=q.claim_reader,clock=lambda:q.at)
    assert all(c in {'GET','draft'} for c in q.client.calls)


def test_failed_first_recovery_real_GET_client_keeps_original_wire_and_bounds(failed_first_recovery,tmp_path):
    from nfl_lab import audit_weekly_operations_v1 as o
    q=failed_first_recovery;requests=[]
    class Response:
        def __init__(self,body):self.status=200;self.body=body;self.headers={'content-length':str(len(body)),'x-ratelimit-remaining':'100'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return self.body[:limit]
    def transport(request,timeout):
        assert request.get_method()=='GET' and request.data is None
        requests.append(request.full_url)
        if '/releases/assets/' in request.full_url:
            identity=int(request.full_url.rsplit('/',1)[1])
            if request.headers.get('Accept')=='application/octet-stream':body=q.bodies[identity]
            else:body=store.canonical(next(a for a in q.assets if a['id']==identity))
        else:body=store.canonical(q.client.json(request.full_url))
        return Response(body)
    for a in q.assets:a['url']=store.API+'/releases/assets/'+str(a['id'])
    class Native(hosted.PendingMetadataClient):
        def inventory(self):return q.assets,sum(a['size'] for a in q.assets)
        def draft(self):return None
    journal=tmp_path/'bounded-recovery';journal.mkdir()
    client=Native('ghs_FICTIONAL','300',source_sha=q.root['source_sha'],journal=journal,
        job=q.client.job,operation='metadata',root_go=q.root,transport=transport)
    client.bind(q.client.binding)
    claims=Native('ghs_FICTIONAL','300',source_sha=q.root['source_sha'],journal=journal,
        job=q.client.job,operation='metadata',root_go=q.root,transport=transport)
    claims.bind(q.client.binding)
    proof=o.authenticate_failed_first_recovery(client,q.root,authenticate=lambda:None,claim_reader=lambda:claims,clock=lambda:q.at)
    assert proof.verify(q.root) is proof
    assert len(requests)==client.calls+claims.calls==10 and max(client.calls,claims.calls)<=store.MAX_CALLS==40
    assert not list(journal.glob('*.reservation.json'))


@pytest.mark.parametrize('scope',['ordinary','first','recovery'])
def test_recurring_prepare_constructs_real_restore_request_without_module_shadow(failed_first_recovery,tmp_path,scope):
    from nfl_lab import audit_weekly_operations_restore_v1 as restore,audit_weekly_template_v1 as template
    q=failed_first_recovery;r=hosted.Runner.__new__(hosted.Runner);r.go=deepcopy(q.root)
    if scope=='ordinary':r.go['effective_epoch']['controller_context']=None
    elif scope=='first':r.go['effective_epoch']['controller_context']=deepcopy(q.old['effective_epoch']['controller_context'])
    r.operations_proof=object();r.root=tmp_path/'parent';r.storage=SimpleNamespace(cache=r.root/'cache')
    events=[];r.claim=lambda:events.append('claim')
    prior=dict(receipt=dict(path='/fictional/receipt.gz',bytes=1,sha256='a'*64),historical_source_sha256={})
    r.prior_public_metadata=lambda:prior
    r.native=lambda version,phase,request:dict(version=version,phase=phase)
    class AtRealRestoreBoundary(Exception):pass
    def child(tool,phase,request,authority,namespace,seconds):
        assert tool=='audit_weekly_operations_restore_v1' and phase==restore.PHASE
        assert request['schema_version']==restore.VERSION+'-request' and request['limits']==restore.LIMITS
        assert request['inputs']==prior and request['output']==str(r.root/restore.PHASE)
        assert authority==dict(version=hosted.VERSION,phase=restore.PHASE)
        assert namespace=='AUDIT_WEEKLY_NATIVE_AUTHORITY' and seconds==190
        events.append('real_restore_request');raise AtRealRestoreBoundary
    r.child=child
    with pytest.raises(AtRealRestoreBoundary):r.recurring_prepare()
    assert events==(['claim'] if scope=='ordinary' else [])+['real_restore_request']


@pytest.mark.parametrize('damage',['actor','source','job_clock','namespace','membership','omitted','conflict','unknown_failed_run','short_census','missing_origin'])
def test_pending_recovery_damage_fails_before_any_write(pending_failure,damage):
    q=pending_failure;r=q.runner
    if damage=='actor':q.run['actor']['id']=123
    elif damage=='source':q.run['head_sha']='f'*40
    elif damage=='job_clock':q.job['completed_at']='2026-01-01T00:00:10Z'
    elif damage=='namespace':r.go['qualified_runtime']['binding']=dict(r.go['qualified_runtime']['binding'],release_id=92)
    elif damage=='membership':q.assets.pop()
    elif damage=='omitted':q.spec['pending_reservations']=[]
    elif damage=='conflict':q.spec['pending_reservations']=[dict(q.record,bytes=4)]
    elif damage=='unknown_failed_run':
        original=r.client.json
        r.client.json=lambda url:dict(total_count=3,workflow_runs=[dict(q.run,id=300),q.run,dict(q.run,id=100,conclusion='success')]) if '/workflows/' in url else original(url)
    else:
        original=r.client.json
        r.client.json=lambda url:dict(total_count=2 if damage=='short_census' else 1,workflow_runs=[q.run]) if '/workflows/' in url else original(url)
    with pytest.raises((ValueError,store.StoreError)):r.authenticate_pending_posts()
    assert not r.pending_scope_authenticated and not list(r.journal.glob('*.reservation.json'))
    for action in [lambda:r.claim(),lambda:r.failure_client('append'),lambda:r.preserve_opaque_outputs()]:
        with pytest.raises(store.StoreError,match='PENDING_SCOPE_NOT_AUTHENTICATED_NO_WRITE'):action()


def test_pending_records_survive_fresh_process_count_once_and_never_retry(pending_failure,tmp_path):
    q=pending_failure;r=q.runner;r.authenticate_pending_posts()
    configuration=tmp_path/'quota.json';configuration.write_text(json.dumps(dict(binding=r.client.binding,assets=q.assets,record=q.record)))
    script='''import json,sys
from pathlib import Path
from nfl_lab import private_draft_store as s
x=json.loads(Path(sys.argv[2]).read_text());c=s.Client.__new__(s.Client)
c.binding=x['binding'];c.journal=Path(sys.argv[1]);c.allow=lambda u:u
c.json=lambda *a,**k:x['assets']
_,charged=c.inventory();base=sum(a['size'] for a in x['assets'])
assert charged==base+3 and c.inventory_slots==len(x['assets'])+1
x['assets'].append(dict(id=99,name=x['record']['name'],size=3,digest='sha256:'+x['record']['sha256'],state='uploaded'))
_,matched=c.inventory();assert matched==base+3 and c.inventory_slots==len(x['assets'])
try:c.reserve(x['record']['key'],b'abc',name=x['record']['name'])
except s.StoreError as e:assert e.code=='POST_ALREADY_RESERVED_NO_RETRY'
else:raise AssertionError('ambiguous POST was retried')
print('fresh-process pending accounting and no-retry PASS')
'''
    p=subprocess.run([sys.executable,'-c',script,str(r.journal),str(configuration)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr


def test_archive_request_carries_root_pending_and_child_rejects_omission(pending_failure,tmp_path):
    from tools import audit_weekly_archive_v1 as cli
    from nfl_lab import audit_weekly_archive_v1 as archive
    q=pending_failure;r=q.runner;r.root=tmp_path/'runner';r.storage=SimpleNamespace(cache=tmp_path/'cache');r.package_ref={}
    r.go['pending_census']={}
    request=r.archive_request('produce',context={},r0={})
    assert request['pending_reservations']==[q.record]
    request['pending_reservations']=[]
    raw=store.canonical(request);path=tmp_path/'request.json';path.write_bytes(raw)
    args=SimpleNamespace(phase='produce',request=str(path),request_sha256=store.sha(raw))
    with patch.object(cli,'guard',return_value=({},dict(job_id=hosted.JOBS['produce']),None,store.canonical(r.go))):
        with pytest.raises(store.StoreError,match='EXACT_ROOT_PRIOR_PENDING_RECORDS_IN_ARCHIVE_CHILD'):
            cli.run(args,{})


def test_real_pending_metadata_client_routes_are_exact_and_get_only(pending_failure,tmp_path):
    q=pending_failure;journal=tmp_path/'real-client-journal';journal.mkdir(mode=0o700)
    client=hosted.PendingMetadataClient('ghs_FICTIONAL','300',source_sha='b'*40,journal=journal,
        root_go=q.runner.go,operation='metadata',transport=lambda *_:pytest.fail('NO_NETWORK_IN_ROUTE_TEST'))
    base=store.API+'/actions/runs/200'
    assert client.allow(base)==base
    assert client.allow(base+'/jobs?per_page=100&page=1').startswith(base)
    for page in range(1,5):
        url=store.API+'/actions/workflows/lab.yml/runs?event=workflow_dispatch&branch=research%2Fweekly-storage-probe-v1&per_page=5&page='+str(page)
        assert client.allow(url)==url
        with pytest.raises(store.StoreError,match='ROOT_METADATA_GET_ONLY'):client.request(url,method='POST',data=b'{}')
    with pytest.raises(store.StoreError,match='ROUTE_FORBIDDEN'):client.allow(store.API+'/actions/runs/999')
    with pytest.raises(store.StoreError,match='ROUTE_FORBIDDEN'):client.allow(url.replace('page=4','page=5'))


def test_root_claim_reserves_manifest_slots_in_addition_to_pending_slots(pending_failure):
    q=pending_failure;r=q.runner
    r.env={};r.identity=dict(run_id='300',source_sha='b'*40);r.job={};r.go_sha='e'*64
    r.operations_proof=None;r.pending_scope_authenticated=True
    r.go['qualified_runtime']['qualification']={}
    r.go['pending_census']={}
    class NearCapacity:
        def __init__(self,*a,**k):self.inventory_slots=127
        def authenticate_actions_job(self):pass
        def bind(self,b):self.binding=b
        def inventory(self):return [dict(name='existing-'+str(n)) for n in range(126)],0
    # 126 uploaded + 1 unresolved + payload/manifest 2 = 129 > 128.
    with patch.object(hosted.archive,'Client',NearCapacity),patch.object(hosted.operations_authority,'attach'),\
            patch.object(hosted.archive,'authenticate_qualification'),\
            patch.object(store,'append',side_effect=AssertionError('PAYLOAD_POST_BEFORE_FULL_CLAIM_ADMISSION')) as append:
        with pytest.raises(store.StoreError,match='ROOT_CLAIM_CAPACITY'):r.claim()
    append.assert_not_called()


@pytest.mark.parametrize('exhausted',['wall','calls'])
def test_first_primary_claim_checks_absence_with_fresh_bounded_client(tmp_path,exhausted):
    from nfl_lab import audit_weekly_operations_v1 as operations
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    from nfl_lab import audit_weekly_template_v1 as template
    from test_audit_weekly_operations_v1 import first_future_metadata
    q=first_future_metadata.__wrapped__(tmp_path)
    r=hosted.Runner.__new__(hosted.Runner)
    r.go=q.root;r.go['qualified_runtime']['qualification']={'run_id':'100'};r.go['pending_census']={}
    r.go_sha=store.sha(store.canonical(r.go));r.root=tmp_path/'late-claim'
    r.storage=OperationalStorage(r.root/'cache',Path(hosted.__file__).resolve().parents[1]/'config/operational-source-policy-v2.json',state=r.root/'state')
    r.storage.register_root(r.root)
    r.journal=r.root/'journal';r.journal.mkdir(mode=0o700)
    r.storage.write_bytes(r.root/'operations-prepared/PREPARED.json',store.canonical(dict(
        current_root_go_sha256=r.go_sha,first_primary=dict(scope=template.first_primary_root(r.go)),
        epoch_sha256=r.go['effective_epoch']['controller_context']['retained_epoch_sha256'],
        state='FIRST_FUTURE_PRIMARY_PREVALUE_METADATA_READY_LOCAL')))
    r.client=q.client;r.client.started=0;r.client.clock=lambda:181 if exhausted=='wall' else 0
    r.client.calls=40 if exhausted=='calls' else 0
    old_counters=(r.client.started,r.client.calls)
    r.env=dict(GITHUB_ACTOR='NickNicky19',GITHUB_ACTOR_ID='208912933',GITHUB_TOKEN='ghs_FICTIONAL')
    r.identity=dict(run_id='300',source_sha='b'*40);r.job=deepcopy(q.client.job)
    r.pending_scope_authenticated=True
    proof=bootstrap.Owner.__new__(bootstrap.Owner);r.operations_proof=proof;r.fresh_operations_proof=lambda:proof
    clients=[];real_client=hosted.archive.Client;real_absence=operations.first_primary_absence
    class FreshClaimClient(real_client):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs,transport=q.client.transport,clock=lambda:10)
            clients.append(self)
        def authenticate_actions_job(self):assert self.job['run_authenticated'] is True
        def inventory(self):self.inventory_slots=0;return [],0
    class BeforeAppend(Exception):pass
    def actual_absence(client,root,*,authenticate):
        return real_absence(client,root,authenticate=authenticate,clock=lambda:q.at)
    def verify_owner(actual,env,body):
        assert actual is proof and env is r.env and body==store.canonical(r.go)
    with patch.object(hosted.archive,'Client',FreshClaimClient),\
            patch.object(hosted.archive,'authenticate_qualification'),\
            patch.object(hosted.operations_authority,'attach'),\
            patch.object(hosted.operations_authority,'_verify',side_effect=verify_owner),\
            patch.object(operations,'first_primary_absence',side_effect=actual_absence),\
            patch.object(store,'append',side_effect=BeforeAppend) as append:
        with pytest.raises(BeforeAppend):r.claim()
    assert len(clients)==1 and clients[0].calls==6 and len(q.calls)==6
    assert (r.client.started,r.client.calls)==old_counters  # Never reset an expired scope.
    assert store.MAX_CALLS==40 and append.call_count==1


@pytest.mark.parametrize('exhausted',['wall','calls'])
@pytest.mark.parametrize('checkpoint',['none','legacy','locator'])
def test_prior_public_metadata_uses_its_own_bounded_get_client(tmp_path,exhausted,checkpoint):
    import base64,gzip
    from nfl_lab import audit_weekly_discovery_v1 as discovery, audit_weekly_grade_history_v1 as history
    from nfl_lab import gha_private_checkpoint as cp
    from test_audit_weekly_operations_v1 import first_future_metadata
    q=first_future_metadata.__wrapped__(tmp_path)
    r=hosted.Runner.__new__(hosted.Runner);r.go=q.root
    r.root=tmp_path/'prior-public'
    r.storage=OperationalStorage(r.root/'cache',hosted.ROOT/'config/operational-source-policy-v2.json',state=r.root/'state')
    r.storage.register_root(r.root);r.journal=r.root/'journal';r.journal.mkdir(mode=0o700)
    r.client=q.client;r.client.started=0;r.client.calls=40 if exhausted=='calls' else 0
    r.client.clock=lambda:181 if exhausted=='wall' else 0
    old_counters=(r.client.started,r.client.calls)
    r.env=dict(GITHUB_TOKEN='ghs_FICTIONAL');r.job=deepcopy(q.client.job)
    r.identity=cp.client_identity(q.client);r.operations_proof=object()
    r.check=lambda:None;r.fresh_operations_proof=lambda:r.operations_proof
    hashes={'root_go_sha256','policy_sha256','workflow_sha256','recipe_registration_sha256',
        'rights_authority_sha256','r0_identity_sha256','origin_choice_sha256','feed_sha256',
        'archive_index_sha256','archive_files_sha256','reader_witness_sha256','epoch_sha256','choice_sha256'}
    value={k:'a'*64 for k in hashes}
    value.update(schema_version=discovery.delivery.VERSION+'-public-receipt',source_sha='a'*40,run_id='200',
        policy_registered_at_utc='2026-01-01T00:00:00Z',verified_at='2026-01-01T00:01:00Z',
        created_at='2026-01-01T00:02:00Z',feed_bytes=100,rows=1,categories=['pass_att'],fits=0,
        raw_or_models_public=False,jobs={role:dict(job_id=name,api_job_id=100+n)
            for n,(role,name) in enumerate(hosted.JOBS.items())})
    compressed=gzip.compress(store.canonical(value),mtime=0)
    r.go['effective_epoch']['previous_capture']=dict(feed_sha256='a'*64,receipt_sha256=store.sha(compressed))
    files={name:('fictional original '+name).encode() for name in hosted.weekly_retained.HISTORICAL_FILES}
    prior_path='state/public/weekly-adaptive-v1/receipts/'+'a'*64+'.json.gz';files[prior_path]=compressed
    checkpoint_body=b'fictional exact original grading sidecar'
    locator='20261027T190000.000000Z--200--'+'d'*64+'.json.gz'
    if checkpoint!='none':
        r.go['effective_epoch']['controller_context']=None
        path=history.LOCATOR_ROOT+'/'+locator if checkpoint=='locator' else 'state/controller-v1/grade-checkpoints/'+'a'*64+'.json.gz'
        files[path]=checkpoint_body
        r.go['effective_epoch']['previous_checkpoint']=dict(sha256=store.sha(checkpoint_body))
        if checkpoint=='locator':r.go['effective_epoch']['previous_checkpoint'].update(schema_version=history.LOCATOR_REF,path=locator)
    calls=[];clients=[]
    class Response:
        status=200
        def __init__(self,value):self.body=store.canonical(value);self.headers={'x-ratelimit-remaining':'100'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,cap):return self.body[:cap]
    def transport(request,timeout):
        assert request.get_method()=='GET' and request.data is None
        url=request.full_url;calls.append(url)
        if '/contents/'+history.LOCATOR_ROOT+'?' in url:
            return Response([dict(type='file',name=locator,path=history.LOCATOR_ROOT+'/'+locator,size=len(checkpoint_body))])
        if '/contents/' in url:
            path=url.split('/contents/',1)[1].split('?',1)[0];body=files[path]
            from nfl_lab import audit_weekly_controller_v1 as controller
            return Response(dict(type='file',path=path,encoding='base64',size=len(body),
                content=base64.b64encode(body).decode(),sha=controller.blob_sha(body)))
        run=dict(id=300,head_sha='b'*40,event='workflow_dispatch',run_attempt=1,status='in_progress',
            path='.github/workflows/lab.yml',repository=dict(full_name=store.REPO),head_repository=dict(full_name=store.REPO))
        return Response(dict(jobs=[dict(id=301,name=hosted.JOBS['produce'],status='in_progress',run_id=300,head_sha='b'*40)],total_count=1)
            if '/jobs?' in url else run)
    r.client.transport=transport
    real_client=hosted.archive.Client
    class FreshPublicClient(real_client):
        def __init__(self,*args,**kwargs):
            assert kwargs.get('readonly') is True
            super().__init__(*args,**kwargs,transport=transport,clock=lambda:10);clients.append(self)
    with patch.object(hosted.archive,'Client',FreshPublicClient),patch.object(hosted.operations_authority,'attach') as attach:
        actual=r.prior_public_metadata()
    expected_calls=11+(1 if checkpoint=='legacy' else 2 if checkpoint=='locator' else 0)
    assert len(clients)==1 and clients[0].calls==len(calls)==expected_calls<=store.MAX_CALLS==40
    assert (r.client.started,r.client.calls)==old_counters
    assert actual['historical_source_sha256']=={name:store.sha(files[name]) for name in hosted.weekly_retained.HISTORICAL_FILES}
    assert Path(actual['receipt']['path']).read_bytes()==compressed
    assert (actual['previous_grade_snapshot'] is None)==(checkpoint=='none')
    assert attach.call_count==1 and not list(r.journal.glob('*.reservation.json'))


def test_calendar_uses_new_york_kickoff_clock_across_both_dst_offsets_and_not_scores():
    raw=("season,week,game_type,game_id,gameday,gametime,home_score\n"
        "2026,7,REG,oct,2026-10-25,09:30,DO_NOT_READ_OUTCOME\n"
        "2026,10,REG,nov,2026-11-15,13:00,DO_NOT_READ_OUTCOME\n").encode()
    a=hosted.schedule_metadata(raw,season=2026,week=7)
    b=hosted.schedule_metadata(raw,season=2026,week=10)
    assert a[0]['kickoff_utc']=='2026-10-25T13:30:00+00:00'
    assert b[0]['kickoff_utc']=='2026-11-15T18:00:00+00:00'
    assert all('score' not in k for x in a+b for k in x)
    with pytest.raises(store.StoreError,match='COMPLETE_UNIQUE_WEEK_CALENDAR'):
        hosted.schedule_metadata(raw+raw.splitlines()[1]+b'\n',season=2026,week=7)


def test_old_raw_completion_and_new_terminal_witness_are_distinct_epoch_origins():
    from test_audit_weekly_origin_v1 import fixture,CHECKED
    from test_audit_weekly_epoch_v1 import fixture as model_fixture
    f=fixture();w=f['witness']
    history=dict(bytes=123,sha256='f'*64)
    e=epoch.prepare_epoch(f['raw_choice'],w,f['slate'],f['catalog'],f['policy'],model_fixture()['replay'],
        history_binding=history,clock=lambda:CHECKED)
    assert e.origin['completion']['schema_version']=='audit-weekly-origin-v1-terminal-witness'
    assert e.origin['completion']['original_completion_file_retained'] is False
    assert e.origin['completion']['created_at_utc']!=e.origin['completion']['actual_decision_persist_completed_at']
    e2=epoch.restore_epoch(e.document,f['raw_choice'],w,f['slate'],f['catalog'],f['policy'],history_binding=history,now=CHECKED+timedelta(seconds=1))
    assert e2.sha256==e.sha256
    for key,value in [('created_at_utc','2027-01-01T00:00:00Z'),('fabricated_original_receipt',True)]:
        changed=deepcopy(w);changed[key]=value
        with pytest.raises(epoch.EpochError,match='SOURCE_BOUND_ORIGINAL_TERMINAL_WITNESS_REQUIRED'):
            epoch.prepare_epoch(f['raw_choice'],changed,f['slate'],f['catalog'],f['policy'],model_fixture()['replay'],history_binding=history,clock=lambda:CHECKED)


def test_entry_preparation_has_no_network_credentials_or_package_dependencies():
    path=Path(__file__).resolve().parents[1]/'tools/audit_weekly_hosted_v1.py'
    result=subprocess.run([sys.executable,'-I','-B',str(path),'produce'],env={},capture_output=True,text=True)
    assert result.returncode==2
    assert json.loads(result.stdout)==dict(state='WEEKLY_PREPARATION_ONLY_NO_IO',fits=0,public_release=False)
    assert not result.stderr


def public_root_fixture():
    import base64,gzip
    from nfl_lab import audit_weekly_public_v1 as public
    from test_audit_weekly_epoch_v1 import fixture
    at=hosted.utc('2026-10-25T06:30:00Z');source='b'*40
    replay=fixture()['replay']
    rights=dict(schema_version='weekly-selected-derived-rights-authority-v1',state='ROOT_REGISTERED',
        scope='SELECTED_DERIVED_ONLY',authority_kind='ROOT_APPROVED_DERIVED_PUBLICATION',
        source_policy_sha256=public.cp.POLICY_SHA,public_fields=list(public.overlay.ROW_FIELDS),
        public_raw_or_model_weights=False,human_approval=False,source_review_sha256='d'*64,
        basis='Fictional selected derivatives only; no upstream blanket grant',upstream_blanket_grant=False)
    r0=dict(schema_version='weekly-actual-r0-freeze-v1',state='ACTUAL_FIRST_RELEASE_R0_FROZEN',
        deployment_id=1,deployed_source_sha='c'*40,visible_board_sha256='d'*64,
        engine_sha256={p:'e'*64 for p in public.feed.ENGINE_FILES},frozen_at='2026-10-24T10:00:00Z')
    policy=public.policy_template()
    policy.update(state='ROOT_REGISTERED',registered_at_utc=at.isoformat(),source_sha=source,
        source_branch='research/weekly-storage-probe-v1',workflow_sha256=store.sha((hosted.ROOT/'.github/workflows/lab.yml').read_bytes()),
        origin_choice_sha256='a'*64,jobs=hosted.JOBS,rights_authorities=[hosted.digest(rights)],r0_identities=[hosted.digest(r0)],
        public_roles={t:['QB'] for t in public.cp.TARGETS},engine_sha256=r0['engine_sha256'],
        website_code_sha256={p:'e'*64 for p in public.feed.CODE_FILES},
        approved_candidates=[{k:s[k] for k in ('target','family','method_id','procedure_version')} for s in replay['slots']])
    policy['producer_policy_sha256']=public.recipe_commitment(policy)
    policy['publication_authority'].update(state='ROOT_REGISTERED',source_sha=source,source_branch=policy['source_branch'],
        export_job=hosted.JOBS['consume'],recipe_registration_sha256=policy['producer_policy_sha256'])
    go=dict(publication=True,source_sha=source,issued_at_utc=at.isoformat(),retained_registration=dict(origin=dict(replay_catalog=replay)))
    def bind(doc):
        body=store.canonical(doc)
        go['publication_registration']=dict(policy_gzip_base64=base64.b64encode(gzip.compress(body,mtime=0)).decode(),
            policy_sha256=store.sha(body),rights_authority=rights,r0=r0)
    bind(policy)
    return go,policy,bind,at


def controller_admission_root(*, separate):
    """Fictional Root with the actual clock, source, config and context guards.

    Only retained model artifact qualification is outside this admission test;
    its independent validator is exercised by the retained-artifact suites.
    """
    from nfl_lab import audit_weekly_controller_registration_v1 as registration
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    at=hosted.utc('2026-10-25T19:30:00Z')
    context=dict(schema_version=registration.VERSION+'-context',parent_source_sha='a'*40,
        previous_capture=dict(feed_sha256='b'*64,receipt_sha256='c'*64))
    if separate:
        context.update(schema_version=registration.SEPARATE_CONTEXT_SCHEMA,
            parent_code_pins={name:'d'*64 for name in bootstrap.PARENT_EXECUTABLE_PINS})
    root={key:None for key in hosted.ROOT_KEYS}
    root.update(schema_version=hosted.VERSION+'-root-GO',approved=True,repository=store.REPO,
        mode=hosted.MODE,operation='CONTROLLER_REGISTRATION',source_sha='e'*40,
        workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1',
        owner_authorization='OWNER_NFL_AUDIT_CONTINUATION_20261025',issued_at_utc=at.isoformat(),
        expires_at_utc=(at+timedelta(minutes=30)).isoformat(),single_writer_group='nfl-lab-single-writer',
        code_pins=hosted.pins(),limits=hosted.LIMITS.copy(),jobs=hosted.JOBS.copy(),
        failure_restorer=hosted.FAILURE_JOB,cutoff_lead_seconds=5400,publication=False,
        qualified_runtime=dict(schema_version='audit-private-rotation-v1-qualified-runtime',runtime_reserved_bytes=32<<20),
        source_config=dict(purpose='CURRENT_OPERATIONAL_INFERENCE',history_seasons=[2026],
            allowed_periods={'2026':[1,2,3,4,5,6]},
            freshness_seconds=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800)),
        effective_epoch=context)
    return root,at


@pytest.mark.parametrize('separate',[False,True])
def test_actual_root_admission_accepts_original_and_separate_source_context(separate):
    root,at=controller_admission_root(separate=separate)
    with patch.object(hosted.retained,'validate_registration') as retained_check:
        assert hosted.validate_root(root,now=at) is root
    retained_check.assert_called_once_with(None)


def test_actual_root_v3_admission_keeps_exact_sealed_prior_package_and_v2_keys(dual_document):
    from nfl_lab import audit_weekly_template_v1 as template
    root,at=controller_admission_root(separate=True)
    for name in ('schema_version','qualified_runtime','pending_census','prior_capture_qualified_runtime'):
        root[name]=deepcopy(dual_document['root_template'][name])
    old=store.canonical(root['prior_capture_qualified_runtime'])
    with patch.object(hosted.retained,'validate_registration'),pytest.raises(store.StoreError,match='EXPLICIT_DUAL_RUNTIME_PENDING_REGISTRATION'):
        hosted.validate_root(root,now=at)
    from nfl_lab import audit_weekly_controller_registration_v1 as registration, audit_weekly_grade_history_v1 as history
    root['effective_epoch'].update(schema_version=registration.RECOVERY_CONTEXT_SCHEMA,
        history_protocol=history.LOCATOR_VERSION,
        pending_post_recovery=dict(schema_version=template.PENDING_RECOVERY,handoffs=[],pending_reservations=[]))
    with patch.object(hosted.retained,'validate_registration'):
        assert hosted.validate_root(root,now=at) is root
    assert store.canonical(root['prior_capture_qualified_runtime'])==old
    assert set(root)==template.ROOT_V3_KEYS and len(root['code_pins'])==128
    changed=deepcopy(root);changed['schema_version']=hosted.VERSION+'-root-GO'
    with patch.object(hosted.retained,'validate_registration') as guarded,pytest.raises(store.StoreError,match='CLOSED_CURRENT_WEEKLY_ROOT_REQUIRED'):
        hosted.validate_root(changed,now=at)
    guarded.assert_not_called()


@pytest.mark.parametrize('damage',['extra','unknown_schema','parent_sha','missing_pin','invalid_pin','too_many_pins'])
def test_actual_root_admission_rejects_bad_split_context_before_artifact_qualification(damage):
    root,at=controller_admission_root(separate=True)
    ctx=root['effective_epoch'];pins=ctx['parent_code_pins']
    if damage=='extra':ctx['approved']=True
    elif damage=='unknown_schema':ctx['schema_version']='unregistered-context'
    elif damage=='parent_sha':ctx['parent_source_sha']='a'*39
    elif damage=='missing_pin':pins.pop('nfl_lab/owned_reference_batch.py')
    elif damage=='invalid_pin':pins['nfl_lab/owned_reference_batch.py']='unbound'
    elif damage=='too_many_pins':
        pins.update({'nfl_lab/fictional_extra_%03d.py'%i:'f'*64 for i in range(129-len(pins))})
    with patch.object(hosted.retained,'validate_registration') as retained_check:
        with pytest.raises(store.StoreError,match='EXACT_OWNER_CONTROLLER_REGISTRATION_CONTEXT'):
            hosted.validate_root(root,now=at)
    retained_check.assert_not_called()


@pytest.mark.parametrize('case',['missing_review','blanket','unknown_field','invalid_review','invalid_basis','zero_deployment','late_freeze','wrong_engine'])
def test_invalid_rights_or_R0_reject_before_any_source_or_forecast_read(case):
    go,policy,bind,at=public_root_fixture()
    value=go['publication_registration'];rights=value['rights_authority'];r0=value['r0']
    if case=='missing_review':rights.pop('source_review_sha256')
    elif case=='blanket':rights['upstream_blanket_grant']=True
    elif case=='unknown_field':rights['new_claim']=True
    elif case=='invalid_review':rights['source_review_sha256']='unbound'
    elif case=='invalid_basis':rights['basis']=''
    elif case=='zero_deployment':r0['deployment_id']=0
    elif case=='late_freeze':r0['frozen_at']='2026-10-25T06:31:00Z'
    elif case=='wrong_engine':r0['engine_sha256']={k:'f'*64 for k in r0['engine_sha256']}
    # A matching new digest is insufficient to turn a malformed authority or
    # later freeze into a valid prior registration.
    policy['rights_authorities']=[hosted.digest(rights)];policy['r0_identities']=[hosted.digest(r0)];bind(policy)
    with pytest.raises(store.StoreError,match='REGISTERED_DERIVED_SOURCE_RIGHTS|ORIGINAL_R0_FROZEN'):
        hosted.publication_configuration(go,now=at)


def test_root_publication_metadata_is_exact_current_source_recipe_and_prior_clock():
    go,policy,bind,at=public_root_fixture()
    result=hosted.publication_configuration(go,now=at)
    assert result['policy']==policy
    assert result['rights_authority']['public_raw_or_model_weights'] is False
    for field,value in [('source_sha','f'*40),('registered_at_utc','2026-10-25T06:29:00+00:00'),
        ('workflow_sha256','f'*64)]:
        changed=deepcopy(policy);changed[field]=value;bind(changed)
        with pytest.raises((store.StoreError,hosted.public.PublicError)):
            hosted.publication_configuration(go,now=at)
    changed=deepcopy(policy);changed['approved_candidates'][0]['procedure_version']='f'*64
    changed['producer_policy_sha256']=hosted.public.recipe_commitment(changed)
    changed['publication_authority']['recipe_registration_sha256']=changed['producer_policy_sha256'];bind(changed)
    with pytest.raises(store.StoreError,match='EXACT_CURRENT_ROOT_PUBLICATION_SCOPE'):
        hosted.publication_configuration(go,now=at)


def test_root_publication_metadata_rejects_corruption_inflation_and_implicit_approval():
    import base64,gzip
    go,policy,bind,at=public_root_fixture()
    go['publication_registration']['policy_sha256']='f'*64
    with pytest.raises(store.StoreError,match='EXACT_BOUNDED_PUBLIC_POLICY_BODY'):
        hosted.publication_configuration(go,now=at)
    bind(policy)
    go['publication_registration']['policy_gzip_base64']=base64.b64encode(gzip.compress(b' '*((128<<10)+2))).decode()
    with pytest.raises(store.StoreError,match='EXACT_BOUNDED_PUBLIC_POLICY_BODY'):
        hosted.publication_configuration(go,now=at)
    bind(policy);go['publication_registration']['rights_authority']['public_raw_or_model_weights']=True
    with pytest.raises(store.StoreError,match='REGISTERED_DERIVED_SOURCE_RIGHTS'):
        hosted.publication_configuration(go,now=at)
    go['publication']=False
    with pytest.raises(store.StoreError,match='NO_IMPLICIT_PUBLICATION_REGISTRATION'):
        hosted.publication_configuration(go,now=at)
    go['publication_registration']=None
    assert hosted.publication_configuration(go,now=at) is None


@pytest.mark.parametrize('phase',['produce','restore','consume'])
def test_fresh_failure_preserver_reopens_only_the_original_job_phase(phase):
    observed=[]
    class Original:
        def __init__(self,actual,env,*,existing):
            observed.append((actual,existing));assert actual==phase and existing is True
        def preserve_failure(self):return dict(state='FAILED_ATTEMPT_APPENDED_READER_REQUIRED',public_release=False,successful_forecast=False)
        def produce(self):raise AssertionError('must not rerun original phase')
        restore=produce;consume=produce
    with patch.object(hosted,'Runner',Original):
        result=hosted.execute('preserve',dict(GITHUB_JOB=hosted.JOBS[phase]))
    assert observed==[(phase,True)] and result['successful_forecast'] is result['public_release'] is False
    with pytest.raises(store.StoreError,match='ONLY_ORIGINAL_FAILED_PHASE'):
        hosted.execute('preserve',dict(GITHUB_JOB=hosted.FAILURE_JOB))


def test_failed_jobs_have_a_closed_evidence_only_reader_and_exact_source_checkout():
    import yaml
    workflow=yaml.load((hosted.ROOT/'.github/workflows/lab.yml').read_text(),Loader=yaml.BaseLoader)
    jobs=workflow['jobs'];evidence=jobs[hosted.FAILURE_JOB]
    assert evidence['needs']==list(hosted.JOBS.values())
    assert "needs.audit-weekly-export-v1.outputs.failure_handoff_json != ''" in evidence['if']
    commands=[step.get('run','') for step in evidence['steps']]
    assert sum(' audit_weekly_hosted_v1.py ' in cmd for cmd in commands)==0
    assert commands[-1].endswith('tools/audit_weekly_hosted_v1.py evidence --execute')
    checkout=next(s for s in evidence['steps'] if s.get('uses')=='actions/checkout@v4')
    assert checkout['with']=={'ref':'${{ github.sha }}','persist-credentials':'false','fetch-depth':'0'}
    for phase in ('restore','consume'):
        job=jobs[hosted.JOBS[phase]]
        preserve=next(s for s in job['steps'] if s.get('id')=='preserve')
        assert "steps.weekly.outcome == 'failure'" in preserve['if']
        assert preserve['run'].endswith('tools/audit_weekly_hosted_v1.py preserve --execute')
        assert job['outputs']['failure_handoff_json']=='${{ steps.preserve.outputs.failure_handoff_json }}'
        expected_exit="${{ steps.weekly.outcome == 'failure' && steps.weekly.outputs.exit_code || '' }}" \
            if phase=='consume' else '${{ steps.weekly.outputs.exit_code }}'
        assert preserve['env']['AUDIT_WEEKLY_ORIGINAL_EXIT_CODE']==expected_exit
        if phase=='consume':
            assert "steps.controller_seal_upload.outcome == 'failure'" in preserve['if']
            assert "steps.controller_seal_upload.outcome == 'failure'" in preserve['env']['AUDIT_WEEKLY_FAILED_ACTION_STEP']
            assert 'Upload only the closed controller SAFE_SEAL metadata' in preserve['env']['AUDIT_WEEKLY_FAILED_ACTION_STEP']
        original=next(s for s in job['steps'] if s.get('id')=='weekly')
        assert 'weekly_phase_exit=$?' in original['run'] and 'exit "$weekly_phase_exit"' in original['run']


@pytest.mark.parametrize('code,recorded,kind,expected',[('',False,'INTERRUPTION',None),('',True,'EXCEPTION',None),
    ('137',False,'INTERRUPTION',137),('124',False,'DEADLINE',124),('1',True,'EXCEPTION',1)])
def test_failure_keeps_actual_exit_or_explicit_unknown(code,recorded,kind,expected):
    result=hosted.actual_failure(dict(AUDIT_WEEKLY_ORIGINAL_EXIT_CODE=code),python_failure_recorded=recorded)
    assert result['kind']==kind and result['exit_code']==expected
    for invalid in ('0','-9','256','unknown'):
        with pytest.raises(store.StoreError,match='ACTUAL_FAILED_STEP_EXIT_CODE'):
            hosted.actual_failure(dict(AUDIT_WEEKLY_ORIGINAL_EXIT_CODE=invalid),python_failure_recorded=recorded)


def test_diagnostic_retains_only_public_code_locations_without_exception_values():
    secret='DO_NOT_PRINT_PRIVATE_EXCEPTION_VALUES'
    value=hosted.error_diagnostic(ValueError(secret))
    assert value==dict(error_type='ValueError',source_frames=[])
    try:hosted.require(False,'FICTIONAL_PUBLIC_GUARD')
    except store.StoreError as error:value=hosted.error_diagnostic(error)
    assert value['error_type']=='StoreError' and value['source_frames']
    assert all(set(f)=={'file','line'} and f['file'].startswith(('nfl_lab/','tools/')) and type(f['line']) is int for f in value['source_frames'])
    encoded=json.dumps(value)
    assert secret not in encoded and 'FICTIONAL_PUBLIC_GUARD' not in encoded and '/workspace/' not in encoded and '/tmp/' not in encoded


def test_operational_past_history_and_software_acceptance_have_distinct_purposes():
    from nfl_lab import audit_weekly_runtime_v1 as runtime
    config=dict(history_seasons=[2026],allowed_periods={'2026':[1,2,3,4,5,6]},
        freshness_seconds=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800))
    slate=dict(season=2026,week=7)
    with pytest.raises(runtime.RuntimeErrorCode,match='EARLY_HISTORY_ONLY_NO_PROTECTED_CONFIRMATION'):
        runtime.config_check(config,slate)
    config['purpose']='CURRENT_OPERATIONAL_INFERENCE'
    runtime.config_check(config,slate)
    # The unchanged E7 reader still applies the full-week kickoff+7day gate
    # before parquet values. This scope only admits prior-week requests.
    config['allowed_periods']['2026'].append(7)
    with pytest.raises(runtime.RuntimeErrorCode,match='EARLY_HISTORY_ONLY_NO_PROTECTED_CONFIRMATION'):
        runtime.config_check(config,slate)
    config['allowed_periods']['2026']=[6];config['purpose']='TUNING'
    with pytest.raises(runtime.RuntimeErrorCode,match='EXPLICIT_SOURCE_READ_PURPOSE'):
        runtime.config_check(config,slate)


def test_owned_worker_dies_when_its_parent_is_interrupted(tmp_path):
    import time
    child_code='from tools.audit_process_guard_v1 import arm_parent_death;from pathlib import Path;import os,sys,time;arm_parent_death();Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(20)'
    parent_code='import os,subprocess,sys,time;subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]],env=dict(os.environ,AUDIT_WEEKLY_PARENT_PID=str(os.getpid())));time.sleep(20)'
    marker=tmp_path/'owned-pid'
    parent=subprocess.Popen([sys.executable,'-c',parent_code,child_code,str(marker)],cwd=hosted.ROOT)
    child_pid=None
    try:
        deadline=time.monotonic()+5
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert marker.exists(),'owned child did not start'
        child_pid=int(marker.read_text());assert child_pid!=parent.pid
        parent.kill();parent.wait(timeout=5)
        def alive():
            stat=Path(f'/proc/{child_pid}/stat')
            return stat.exists() and stat.read_text().rsplit(') ',1)[1].split()[0] not in {'Z','X'}
        deadline=time.monotonic()+5
        while alive() and time.monotonic()<deadline:time.sleep(.02)
        assert not alive(),'owned child survived parent interruption'
    finally:
        if parent.poll() is None:parent.kill();parent.wait(timeout=5)


@pytest.mark.parametrize('phase,has_delivery',[('produce',False),('consume',True)])
def test_early_failed_attempt_is_recoverable_failure_evidence_in_fresh_process(tmp_path,phase,has_delivery):
    # Real owned filesystem/CAS and original failure codec, injected append only.
    # A newly loaded JSON status cannot authorize a successful forecast.
    r=object.__new__(hosted.Runner);r.phase=phase;r.root=tmp_path/'attempt';r.root.mkdir()
    r.storage=OperationalStorage(r.root/'cache',Path(hosted.ROOT)/'config/operational-source-policy-v2.json',state=r.root/'state')
    r.storage.register_root(r.root)
    r.go_sha='a'*64;r.go=dict(qualified_runtime=dict(binding=dict(runtime_id='b'*32),qualification=dict()))
    r.root_ref=hosted.write(r.storage,r.root/'OWNER_ROOT.json',dict(fictional_root=True))
    r.identity=dict(repository=store.REPO,run_id='49900000000',run_attempt=1,source_sha='c'*40,
        job_id=hosted.JOBS[phase],workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/fictional')
    exit_code=137 if has_delivery else 1
    r.started=hosted.now_utc()-timedelta(seconds=2);r.env=dict(GITHUB_OUTPUT=str(tmp_path/'output'),AUDIT_WEEKLY_ORIGINAL_EXIT_CODE=str(exit_code))
    (tmp_path/'output').touch()
    hosted.write(r.storage,r.root/'phase-status'/'01-source.json',dict(state='FAILED_RETAINED',reason='FICTIONAL_SOURCE_UNAVAILABLE',successful_forecast=False))
    hosted.write(r.storage,r.root/'journal'/'one.reservation.json',dict(schema_version='weekly-private-POST-reservation-v2',key='fictional',bytes=7,sha256='d'*64,name='fictional'))
    original_controls={}
    if has_delivery:
        for name in ('DELIVERY_PUBLISH_INTENT.json','DELIVERY_FAILED.json'):
            path=r.root/'delivery'/name
            hosted.write(r.storage,path,dict(state='FICTIONAL_ORIGINAL_EXPORT_FAILURE',name=name))
            original_controls['delivery/'+name]=path.read_bytes()
    observed={}
    def append(client,storage,output,**kwargs):
        request,bodies=failure.unpack((output/'FAILURE.json.gz').read_bytes())
        attachments={item['label']:body for item,body in zip(request['attachments'],bodies)}
        assert request['failure']['exit_code']==exit_code and request['state']=='FAILED'
        # This isolated core fixture intentionally has no qualified native
        # archive client. Its secondary failure must be retained too.
        expected={'file-graph','owner-root','original-post-reservations','phase-00','secondary-preservation-failure'}
        if has_delivery:expected.add('complete-auxiliary-controls')
        assert set(attachments)==expected
        secondary=hosted.cp.strict_json(attachments['secondary-preservation-failure'])
        assert secondary['original_failure_replaced'] is secondary['partial_forecast_durability_established'] is False
        if has_delivery:
            import base64
            assert request['operation']=='export' and request['failure']['kind']=='INTERRUPTION'
            auxiliary=hosted.cp.strict_json(attachments['complete-auxiliary-controls'])
            assert {f['relative_path']:base64.b64decode(f['body_base64'],validate=True) for f in auxiliary['files']}==original_controls
        assert b'FICTIONAL_SOURCE_UNAVAILABLE' in attachments['phase-00']
        assert b'one.reservation.json' in attachments['original-post-reservations']
        assert kwargs['inputs']['payload_manifest']==store.canonical(failure.payload_manifest((output/'FAILURE.json.gz').read_bytes()))
        observed['package']=output/'FAILURE.json.gz'
        return dict(descriptor=dict(fictional=True))
    with patch.object(r,'failure_client',return_value=object()),patch.object(r,'operation_go',return_value=dict()),patch.object(failure,'append_failure',side_effect=append):
        result=r.preserve_failure()
    assert result['successful_forecast'] is result['public_release'] is False
    script='from pathlib import Path;from nfl_lab.operational_failure_v1 import unpack;import json,sys; r,a=unpack(Path(sys.argv[1]).read_bytes());print(json.dumps(dict(state=r["state"],files=len(a))))'
    out=subprocess.run([sys.executable,'-c',script,str(observed['package'])],cwd=hosted.ROOT,capture_output=True,text=True,check=True)
    assert json.loads(out.stdout)==dict(state='FAILED',files=6 if has_delivery else 5)
    with pytest.raises(store.StoreError,match='FAILED_ATTEMPT_PRESERVATION_ALREADY_CONSUMED'):
        r.preserve_failure()


"""Paste into a separate tests/test_pending_budget_independent.py.

Independent scratch regression. No private files, credentials, network or native
claims. Uses fictional existing fixtures, REAL Client authentication, qualified
canary, inventory pagination, two CDN redirects per download, original failure
validation and 40-call guard. Only the nonserializable native owner proof bridge
is mocked. No budget or authenticated_pending_records mocks.

Run via the existing venv and run_numerical_profile.py. On Source4202 the three
positive cases MUST fail with OPERATION_LIMIT. On the repair they MUST pass;
the two last-handoff negative cases must fail for their specific guard, never
seed any reservation, and never send a POST. Do not add xfail to hide baseline.
"""
import base64
from copy import deepcopy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs,urlsplit
from unittest.mock import Mock
import pytest
from nfl_lab import audit_weekly_hosted_v1 as h,audit_weekly_archive_v1 as a
from nfl_lab import private_draft_store as s,audit_weekly_template_v1 as t
from nfl_lab import gha_private_checkpoint as cp,operational_failure_v1 as failure
from test_audit_weekly_controller_bootstrap_v1 import system,locator_system

@pytest.fixture
def _pending_budget_forbid_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('REAL_NETWORK_FORBIDDEN'))

@pytest.fixture
def _pending_budget_metadata(locator_system,_pending_budget_forbid_network):
    package=deepcopy(locator_system.package)
    proof=package['qualification'];before=proof['before_proof'];read=proof['read_proof']
    for p,key in [(before,'write'),(read,'read'),(proof,'qualify')]:
        p['job']['job_id']=a.rotation.JOBS[key]
    read['before_sha256']=s.sha(s.canonical(before))
    proof.update(before_sha256=s.sha(s.canonical(before)),read_sha256=s.sha(s.canonical(read)))
    return package,dict(reservations=[])

def _pending_budget_case(tmp_path, package, census, handoff_count=8, asset_count=101, redirects=2, damage=None):
    temp = tmp_path
    origin = int(package['binding']['origin_run_id'])
    current = '99999999999'
    job = dict(execution_lane='github_actions', workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',
        workflow_sha='b'*40, job_id=h.JOBS['produce'], permission='write', event_name='workflow_dispatch',
        api_job_id=9001, run_authenticated=False)
    q = pending_failure.__wrapped__(temp)
    q.old['qualified_runtime']['binding'].clear()
    q.old['qualified_runtime']['binding'].update(deepcopy(package['binding']))
    records = [q.record]
    for n in range(16):
        digest = s.sha(('fictional-record-' + str(n)).encode())
        record = dict(schema_version='weekly-private-POST-reservation-v2', key='asset:blob-' + digest + '.bin',
                      bytes=n+1, sha256=digest, name='blob-' + digest + '.bin')
        records.append(record)
        raw = s.canonical(record)
        q.journals['records'].append(dict(relative_path='journal/' + s.sha(record['key'].encode()) + '.reservation.json',
             bytes=len(raw), sha256=s.sha(raw), body_base64=base64.b64encode(raw).decode()))
    original, _, bodies0 = q.pack()
    original_body = bodies0[original['descriptor']['entry']['payload_asset_id']]
    handoffs = []
    bodies = {package['binding']['canary_asset_id']: s.probe.fixture(str(origin))}
    assets = []
    def add(asset_id, name, body):
        bodies[asset_id] = body
        assets.append(dict(id=asset_id, name=name, size=len(body), state='uploaded',
                           digest='sha256:' + s.sha(body), url=s.API+'/releases/assets/'+str(asset_id)))
    add(package['binding']['canary_asset_id'], package['binding']['canary_name'], bodies[package['binding']['canary_asset_id']])
    for n in range(handoff_count):
        run_id = str(origin+n+1)
        envelope = json.loads(gzip.decompress(original_body))
        envelope['request']['attempt']['run_id'] = run_id
        body = gzip.compress(s.canonical(envelope), mtime=0)
        handoff = deepcopy(original)
        entry = handoff['descriptor']['entry']
        entry.update(writer_run_id=run_id, payload=failure.payload_manifest(body), payload_asset_id=10001+2*n,
                     payload_name='blob-'+s.sha(body)+'.bin')
        raw = s.canonical(entry)
        handoff['descriptor'].update(manifest_asset_id=10002+2*n, manifest_sha256=s.sha(raw), manifest_bytes=len(raw))
        add(entry['payload_asset_id'], entry['payload_name'], body)
        add(handoff['descriptor']['manifest_asset_id'], 'manifest-'+s.sha(raw)+'.json', raw)
        handoffs.append(handoff)
    for n in range(asset_count-len(assets)):
        body = ('fictional filler '+str(n)).encode()
        add(20000+n, 'blob-'+s.sha(body)+'.bin', body)
    root = dict(qualified_runtime=deepcopy(package), pending_census=deepcopy(census), source_sha=job['workflow_sha'], issued_at_utc='2026-01-01T00:02:00Z',
                effective_epoch=dict(schema_version=t.RECURRING_V5, pending_post_recovery=dict(
                    schema_version=t.PENDING_RECOVERY, handoffs=handoffs,
                    pending_reservations=sorted(records, key=lambda x:x['key']))))
    journal = temp/'counted-journal'; journal.mkdir(mode=0o700)
    exchanges = []
    class Response:
        def __init__(self, value, status=200, headers=None):
            self.body = value if isinstance(value, bytes) else s.canonical(value)
            self.status = status
            self.headers = {'content-length':str(len(self.body)), 'x-ratelimit-remaining':'999', **(headers or {})}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,limit): return self.body[:limit]
    def download_body(asset_id):
        body = bodies[asset_id]
        if damage=='hash' and asset_id==handoffs[-1]['descriptor']['entry']['payload_asset_id']:
            body=body[:-1]+bytes([body[-1]^1])
        return body
    def transport(request, timeout):
        assert request.get_method() == 'GET' and request.data is None
        url = request.full_url; p = urlsplit(url); exchanges.append(p.path)
        if p.hostname == 'objects.githubusercontent.com':
            parts = p.path.strip('/').split('/'); asset_id = int(parts[0]); hop = int(parts[1])
            if hop < redirects:
                return Response(b'',302,{'location':'https://objects.githubusercontent.com/'+str(asset_id)+'/'+str(hop+1)})
            return Response(download_body(asset_id))
        if '/actions/runs/' in url:
            run_id = p.path.split('/runs/')[1].split('/')[0]
            if run_id == current:
                if '/jobs' in url:
                    return Response(dict(total_count=1, jobs=[dict(id=9001, name=job['job_id'], run_id=int(current),
                        head_sha=job['workflow_sha'], status='in_progress')]))
                return Response(dict(id=int(current), head_sha=job['workflow_sha'], event='workflow_dispatch', run_attempt=1,
                    status='in_progress', path='.github/workflows/lab.yml', repository={'full_name':s.REPO},
                    head_repository={'full_name':s.REPO}, head_branch=job['workflow_ref'].split('@refs/heads/')[1],
                    actor={'login':'NickNicky19','id':208912933}))
            if run_id == package['qualification']['run_id']:
                proof = package['qualification']; proofs = [proof['before_proof'],proof['read_proof'],proof]
                if '/jobs' in url:
                    return Response(dict(total_count=3,jobs=[dict(id=x['job']['api_job_id'],name=x['job']['job_id'],
                        run_id=int(run_id),head_sha=proof['source_sha'],status='completed',conclusion='success',
                        started_at=x['started_at_utc'],completed_at=x['created_at_utc']) for x in proofs]))
                return Response(dict(id=int(run_id),head_sha=proof['source_sha'],run_attempt=1,event='workflow_dispatch',
                    path='.github/workflows/lab.yml',status='completed',repository={'full_name':s.REPO},
                    head_repository={'full_name':s.REPO}, head_branch=proof['job']['workflow_ref'].split('@refs/heads/')[1],
                    actor={'login':'NickNicky19','id':208912933}))
            if '/jobs' in url:
                return Response(dict(total_count=1,jobs=[dict(q.job,run_id=int(run_id))]))
            run=dict(q.run,id=int(run_id))
            if damage=='actor' and run_id==handoffs[-1]['descriptor']['entry']['writer_run_id']:
                run['actor']=dict(login='FICTIONAL_WRONG_ACTOR',id=123)
            return Response(run)
        if '/actions/workflows/' in url:
            runs=[dict(id=int(current),status='in_progress'), *[dict(q.run,id=int(x['descriptor']['entry']['writer_run_id'])) for x in reversed(handoffs)], dict(q.run,id=origin,conclusion='success')]
            page=int(parse_qs(p.query)['page'][0])
            return Response(dict(total_count=len(runs),workflow_runs=runs[(page-1)*5:page*5]))
        if p.path.endswith('/releases/'+str(package['binding']['release_id'])):
            return Response(dict(id=package['binding']['release_id'],draft=True,published_at=None,
                 tag_name=package['binding']['tag_name'],url=s.API+'/releases/'+str(package['binding']['release_id'])))
        if p.path.endswith('/assets'):
            page=int(parse_qs(p.query)['page'][0]); return Response(assets[(page-1)*100:page*100])
        if '/releases/assets/' in url:
            asset_id=int(p.path.rsplit('/',1)[-1])
            if request.get_header('Accept') == 'application/octet-stream':
                if redirects: return Response(b'',302,{'location':'https://objects.githubusercontent.com/'+str(asset_id)+'/1'})
                return Response(download_body(asset_id))
            return Response(next(x for x in assets if x['id']==asset_id))
        if '/contents/fictional-public-' in url: return Response({})
        raise AssertionError('UNEXPECTED_FIXTURE_ROUTE')
    def new_client(qualify=True):
        client=h.PendingMetadataClient('ghs_FICTIONAL',current,source_sha=job['workflow_sha'],journal=journal,
            job=job,operation='metadata',qualification=package['qualification'],root_go=root,transport=transport,clock=lambda:0)
        client.authenticate_actions_job();client.bind(package['binding'])
        if qualify:a.authenticate_qualification(client,package,census)
        assert cp.client_identity(client)['api_job_id']==9001
        return client
    return SimpleNamespace(root=root,journal=journal,exchanges=exchanges,new_client=new_client,
        transport=transport,job=job,current=current,package=package,assets=assets,bodies=bodies,
        handoffs=handoffs,seed=q,Response=Response)

def _pending_budget_runner(case,monkeypatch):
    old=case.new_client();a.jobs_for(old)
    runner=h.Runner.__new__(h.Runner)
    runner.go=case.root;runner.go_sha=s.sha(s.canonical(case.root))
    runner.journal=case.journal;runner.client=old;runner.job=deepcopy(case.job)
    runner.identity=cp.client_identity(old)
    runner.env=dict(GITHUB_TOKEN='ghs_FICTIONAL',GITHUB_ACTOR='NickNicky19',GITHUB_ACTOR_ID='208912933')
    runner.operations_proof=object();runner.check=lambda:None
    runner.fresh_operations_proof=lambda:runner.operations_proof
    runner.pending_scope_authenticated=False
    runner.pending_metadata_clients=[]
    originals=(old.started,old.calls)
    readers=[];real_client=h.PendingMetadataClient
    class InjectedPendingClient(real_client):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs,transport=case.transport,clock=lambda:0)
            readers.append(self)
    def attach(client,proof,env,raw):
        assert proof is runner.operations_proof and env is runner.env
        assert raw==s.canonical(runner.go)
        assert client.job['run_authenticated'] is True
        assert cp.client_identity(client)['api_job_id']==runner.identity['api_job_id']
        return client
    monkeypatch.setattr(h,'PendingMetadataClient',InjectedPendingClient)
    monkeypatch.setattr(h.operations_authority,'attach',attach)
    seeded=Mock(wraps=cp.seed_pending);monkeypatch.setattr(cp,'seed_pending',seeded)
    return runner,old,originals,readers,seeded


@pytest.mark.parametrize('handoff_count',[2,3,8])
def test_pending_full_handoff_budget_uses_independent_real_clients(tmp_path,monkeypatch,_pending_budget_metadata,handoff_count):
    package,census=_pending_budget_metadata
    case=_pending_budget_case(tmp_path,package,census,handoff_count=handoff_count)
    runner,old,originals,readers,seeded=_pending_budget_runner(case,monkeypatch)
    runner.authenticate_pending_posts()
    assert runner.pending_scope_authenticated and seeded.call_count==1
    assert len(readers)==handoff_count<=8
    # 101 uploaded assets => 2 inventory pages; 2 CDN redirects per read.
    # Old client: 14 startup GETs + 2 inventory + census (1 or 2 pages).
    assert old.started==originals[0]
    assert old.calls==originals[1]+2+(2 if handoff_count==8 else 1)<=20
    # Each fresh scope: 2 auth + 10 qualification/canary + 16 handoff GETs.
    assert all(c.calls==28 and c.started==0 for c in readers)
    assert all(c.job['api_job_id']==9001 and c.binding==package['binding'] for c in readers)
    assert s.MAX_CALLS==40
    records=[s.read_local(p,16384) for p in sorted(case.journal.glob('*.reservation.json'))]
    assert len(records)==17
    assert sorted(records)==sorted(s.canonical(r) for r in case.root['effective_epoch']['pending_post_recovery']['pending_reservations'])
    assert not old.posts and all(not c.posts for c in readers)
    # Every transport exchange asserts GET and no request body.
    assert len(case.exchanges)==old.calls+sum(c.calls for c in readers)


@pytest.mark.parametrize('damage,code',[('actor','ACTUAL_COMPLETED_FAILED_PRIOR_RUN'),('hash','READBACK_MISMATCH')])
def test_last_pending_handoff_guard_prevents_all_seeding(tmp_path,monkeypatch,_pending_budget_metadata,damage,code):
    package,census=_pending_budget_metadata
    case=_pending_budget_case(tmp_path,package,census,handoff_count=8,damage=damage)
    runner,old,originals,readers,seeded=_pending_budget_runner(case,monkeypatch)
    with pytest.raises((s.StoreError,ValueError),match=code):runner.authenticate_pending_posts()
    assert not runner.pending_scope_authenticated
    seeded.assert_not_called()
    assert not list(case.journal.glob('*.reservation.json'))
    assert len(readers)==8 and all(c.calls<=40 for c in readers)
    assert old.started==originals[0] and old.calls==originals[1]+2
    assert not old.posts and all(not c.posts for c in readers)


def _recovery_budget_case(tmp_path,package,census,handoff_count):
    """111 uploaded + 17 unresolved = 128 charged slots, two inventory pages."""
    pending_root=tmp_path/'pending';pending_root.mkdir()
    case=_pending_budget_case(pending_root,package,census,handoff_count=handoff_count,asset_count=109,redirects=2)
    failed_root=tmp_path/'failed';failed_root.mkdir();seed=pending_failure.__wrapped__(failed_root)
    seed.run['id']=int(case.handoffs[-1]['descriptor']['entry']['writer_run_id'])
    seed.old['qualified_runtime']['binding'].clear();seed.old['qualified_runtime']['binding'].update(deepcopy(package['binding']))
    recovered=_failed_first_recovery_case(seed)
    stale=case.handoffs[-1]['descriptor']
    removed={stale['manifest_asset_id'],stale['entry']['payload_asset_id']}
    case.assets[:]=[x for x in case.assets if x['id'] not in removed]
    for asset in recovered.assets:
        asset['url']=s.API+'/releases/assets/'+str(asset['id']);case.assets.append(asset)
    assert len(case.assets)==111 and len({x['id'] for x in case.assets})==111
    case.bodies.update(recovered.bodies);case.handoffs[-1]=recovered.handoff
    reservations=case.root['effective_epoch']['pending_post_recovery']['pending_reservations']+recovered.claim_records
    root=deepcopy(recovered.root);root.update(qualified_runtime=deepcopy(package),pending_census=deepcopy(census))
    root['effective_epoch']['pending_post_recovery'].update(handoffs=case.handoffs,
        pending_reservations=sorted(reservations,key=lambda v:v['key']))
    case.root.clear();case.root.update(root)
    original=case.transport;failed_run=recovered.handoff['descriptor']['entry']['writer_run_id']
    def transport(request,timeout):
        if request.full_url in {s.API+'/actions/runs/'+failed_run,s.API+'/actions/runs/'+failed_run+'/jobs?per_page=100&page=1'}:
            assert request.get_method()=='GET' and request.data is None
            case.exchanges.append(urlsplit(request.full_url).path)
            return case.Response(recovered.client.json(request.full_url))
        return original(request,timeout)
    case.transport=transport
    return case,recovered


@pytest.mark.parametrize('handoff_count',[4,8])
def test_recovery_two_real_clients_fit_128_slots_two_pages_and_two_redirects(tmp_path,monkeypatch,_pending_budget_metadata,handoff_count):
    from nfl_lab import audit_weekly_operations_v1 as operations
    package,census=_pending_budget_metadata;case,recovered=_recovery_budget_case(tmp_path,package,census,handoff_count)
    runner,old,_,readers,_=_pending_budget_runner(case,monkeypatch)
    runner.recovery_metadata_clients=[]
    runner.authenticate_pending_posts()
    assert runner.pending_scope_authenticated and len(runner.pending_metadata_clients)==handoff_count
    previous=[(c,c.calls,c.started) for c in [old,*readers]]
    proof=operations.authenticate_failed_first_recovery(runner.recovery_metadata_client(),case.root,
        authenticate=lambda:None,claim_reader=runner.recovery_metadata_client,clock=lambda:recovered.at)
    assert proof.verify(case.root) is proof
    assert [c.calls for c in runner.recovery_metadata_clients]==[30,28]
    assert all(c.calls<=s.MAX_CALLS==40 and c.started==0 and c.inventory_slots==128 for c in runner.recovery_metadata_clients)
    assert all(c.calls==calls and c.started==started for c,calls,started in previous)
    assert len(runner.pending_metadata_clients)==handoff_count<=8 and len(readers)==handoff_count+2
    assert proof.document['original_claim_payload_sha256']==recovered.claim_assets[0]['digest'][7:]
    assert proof.document['original_claim_manifest_sha256']==recovered.claim_assets[1]['digest'][7:]
    assert not any(c.posts for c in readers) and len(list(case.journal.glob('*.reservation.json')))==19
    before=len(case.exchanges)
    with pytest.raises(s.StoreError,match='TWO_RECOVERY_METADATA_CLIENTS'):runner.recovery_metadata_client()
    if handoff_count==8:
        with pytest.raises(s.StoreError,match='EIGHT_PENDING_FAILURE_METADATA_CLIENTS'):runner.pending_metadata_client()
    assert len(case.exchanges)==before


def test_recovery_old_single_actual_client_hits_40_without_counter_reset(tmp_path,monkeypatch,_pending_budget_metadata):
    package,census=_pending_budget_metadata;case,recovered=_recovery_budget_case(tmp_path,package,census,4)
    runner,_,_,readers,_=_pending_budget_runner(case,monkeypatch);runner.recovery_metadata_clients=[]
    current=runner.recovery_metadata_client();assets,_=current.inventory()
    hosted.authenticated_pending_records(current,recovered.handoff,assets,before=case.root['issued_at_utc'])
    assert current.calls==30
    one,two=recovered.claim_assets
    assert current.read_asset(one['id'],one['name'],one['size'],one['digest'][7:])==recovered.bodies[one['id']]
    assert current.calls==36
    with pytest.raises(s.StoreError,match='OPERATION_LIMIT'):
        current.read_asset(two['id'],two['name'],two['size'],two['digest'][7:])
    assert current.calls==s.MAX_CALLS==40 and current.started==0 and not current.posts
    assert not list(case.journal.glob('*.reservation.json'))
