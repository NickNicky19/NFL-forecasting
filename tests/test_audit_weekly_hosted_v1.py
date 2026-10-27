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
    return SimpleNamespace(runner=runner,record=record,spec=spec,assets=assets,run=run,job=job,
        old=old,journals=journals,pack=pack,handoff=handoff)


def test_pending_recovery_authenticates_exact_failure_and_deduplicates_current_scopes(pending_failure):
    q=pending_failure;r=q.runner
    actual=hosted.authenticated_pending_records(r.client,q.handoff,q.assets,before=r.go['issued_at_utc'])
    assert actual==[q.record] and q.record['bytes']==len(b'abc')
    r.authenticate_pending_posts()
    assert r.pending_scope_authenticated and len(list(r.journal.glob('*.reservation.json')))==1
    assert all(call in {'GET','draft'} for call in r.client.calls)


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
