"""Fictional native/API protocol; injected current authority is not hosted proof."""
import base64
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import socket
import subprocess
import sys
from types import MethodType,SimpleNamespace
import pytest
from nfl_lab import audit_weekly_grade_history_v1 as history
ROOT=Path(__file__).resolve().parents[1]
NEW_RUN='45000000002'
JOBS=dict(produce='audit-weekly-produce-v1',restore='audit-weekly-restore-v1',consume='audit-weekly-export-v1')

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *_:pytest.fail('REAL_NETWORK_FORBIDDEN'))

@pytest.fixture(scope='module')
def original_seed(tmp_path_factory):
    import test_audit_weekly_operations_grade_v1 as bridge
    from nfl_lab import audit_weekly_operations_grade_v1 as worker,audit_weekly_grade_v1 as grade
    from nfl_lab import audit_weekly_archive_v1 as archive,private_draft_store as store,state,gha_private_checkpoint as cp
    from nfl_lab import audit_weekly_operations_v1 as operations
    root=tmp_path_factory.mktemp('original-history')
    with pytest.MonkeyPatch.context() as patch:
        x=bridge.pipeline.__wrapped__(root,patch);q=x.q
        pop=deepcopy(q['pop']);pop['stream_id']=operations.STREAM
        x.restored['aliases']['context/ops_population.json']=archive.write(q['storage'],x.root/'original-primary-population.json',pop)
        written=worker.execute(x.context(worker.PHASES[0]),fetch=x.fetch,clock=lambda:x.service.now)
        x.service.writer_done=(x.service.now+timedelta(seconds=10)).isoformat();x.service.now+=timedelta(minutes=2)
        read=worker.execute(x.context(worker.PHASES[1],written['checkpoint_handoff']),clock=lambda:x.service.now)
        report=archive.read_owned(q['storage'],read['manifest']);proof=report['grade_read_proof']
        c=archive.Client('ghs_FICTIONAL',bridge.RUN,journal=x.clients[-1].journal,source_sha=bridge.SOURCE,
            job=deepcopy(x.clients[-1].job),operation='append',qualification=x.service.q,transport=x.service.transport,process='f'*64)
        c.bind(x.service.binding);c.authenticate_actions_job()
        encoded=archive.read_owned(q['storage'],report['evidence_envelope'],history.LIMITS['envelope_bytes'],raw=True)
        descriptor=store.append(c,encoded,cp.payload(encoded),x.service.q)
        completion=x.service.now+timedelta(minutes=1)
        workflow=('concurrency:\n  group: nfl-lab-single-writer\n  cancel-in-progress: false\n'
            'permissions:\n  contents: write\n  actions: read\njobs:\n'+''.join('  '+j+':\n    runs-on: ubuntu-latest\n' for j in JOBS.values())).encode()
        receipt=dict(schema_version='audit-weekly-delivery-v1-public-receipt',source_sha=bridge.SOURCE,run_id=bridge.RUN,
            root_go_sha256=bridge.ROOT_SHA,policy_sha256='1'*64,policy_registered_at_utc=q['pop']['registered_at'],
            workflow_sha256=store.sha(workflow),recipe_registration_sha256='2'*64,rights_authority_sha256='3'*64,
            r0_identity_sha256='4'*64,origin_choice_sha256='5'*64,feed_sha256='6'*64,feed_bytes=100,rows=1,categories=['rec'],
            jobs={r:dict(job_id=n,api_job_id=777+i) for i,(r,n) in enumerate(JOBS.items())},
            created_at=(x.service.now+timedelta(seconds=10)).isoformat(),verified_at=x.service.now.isoformat(),fits=0,raw_or_models_public=False,
            archive_index_sha256=x.restored['index_sha256'],archive_files_sha256='7'*64,reader_witness_sha256='8'*64,
            epoch_sha256=q['r'].epoch.sha256,choice_sha256=q['c'].sha256)
        sidecar=history.sidecar_document(receipt,written['checkpoint_handoff'],proof,descriptor,cp.client_identity(c))
        docs=dict(epoch=q['r'].epoch.document,epoch_registration=q['r'].completion,original_choice=q['f']['raw'].decode(),
            origin_witness=q['f']['completion'],original_slate=q['f']['slate'],original_catalog=q['f']['catalog'],original_policy=q['f']['policy'])
        sources={n:base64.b64encode((ROOT/n).read_bytes()).decode() for n in set(grade.pins())|set(sidecar['checkpoint_helper_sha256'])}
        sources['.github/workflows/lab.yml']=base64.b64encode(workflow).decode()
        durable=grade._unpack(archive.read_owned(q['storage'],report['durable_history'],8 << 20,raw=True),64 << 20)
        return dict(sidecar=sidecar,receipt=receipt,package=x.service.package,census=x.service.census,docs=docs,choice=q['c'].document,
            durable_sha256=grade._digest(durable),known_versions=durable['known_versions'],known_weeks=durable['known_weeks'],
            capture_ids=[c['capture_id'] for c in durable['captures']],sources=sources,old_run=bridge.RUN,source=bridge.SOURCE,
            current_at=(completion+timedelta(days=1)).isoformat(),old_complete=completion.isoformat(),tag=x.service.server.tag,
            assets=[dict(a,body=base64.b64encode(a['body']).decode()) for a in x.service.server.assets],
            writer_done=x.service.writer_done,roles=q['roles'],population=pop,schedule=q['schedule'],query=q['query'])

def recovery_case(root,seed,patch,*,native=False,role='produce'):
    from nfl_lab import audit_weekly_grade_checkpoint_v1 as checkpoint,audit_weekly_operations_worker_v1 as shared
    from nfl_lab import audit_weekly_operations_authority_v1 as authority,private_draft_store as store,state
    from nfl_lab import gha_private_checkpoint as cp,audit_weekly_archive_v1 as archive
    from nfl_lab.operational_storage import OperationalStorage
    from test_private_draft_store_v2 import Server,Response
    storage=OperationalStorage(root/'cache',ROOT/'config/operational-source-policy-v2.json',state=root/'state');storage.register_root(root)
    current_at=state.utc(seed['current_at'])
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return current_at if tz else current_at.replace(tzinfo=None)
    patch.setattr(store,'datetime',Clock);patch.setattr(history,'now',lambda:current_at)
    if not native:patch.setattr(checkpoint,'native_envelope',lambda:None)
    patch.setattr(authority,'attach',lambda client,*_a:client)  # explicit current Root/bootstrap seam
    server=Server();server.tag=seed['tag'];server.assets=[dict(a,body=base64.b64decode(a['body'])) for a in seed['assets']]
    calls=[];damage={}
    class API:
        def __call__(self,request,timeout):
            calls.append(request);url=request.full_url
            if request.method!='GET':
                assert getattr(self,'allow_append',False),'RECOVERY_REMOTE_WRITES_FORBIDDEN'
                return server(request,timeout)
            if '/contents/' in url:
                name=url.split('/contents/',1)[1].split('?ref=',1)[0];raw=base64.b64decode(seed['sources'][name])
                if damage.get('source'):raw+=b'FICTIONAL_CHANGED_SOURCE'
                blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                return Response(dict(type='file',path=name,encoding='base64',size=len(raw),content=base64.b64encode(raw).decode(),sha=blob))
            if '/actions/runs/' in url:
                rid=url.split('/runs/',1)[1].split('/',1)[0]
                if rid==seed['package']['qualification']['run_id']:
                    q=seed['package']['qualification']
                    if '/jobs?' not in url:return Response(dict(id=int(rid),head_sha=q['source_sha'],run_attempt=1,event='workflow_dispatch',
                        path='.github/workflows/lab.yml',head_branch='fictional',status='completed',repository=dict(full_name=store.REPO),
                        head_repository=dict(full_name=store.REPO),actor=dict(login='NickNicky19',id=208912933)))
                    return Response(dict(total_count=3,jobs=[dict(id=p['job']['api_job_id'],name=p['job']['job_id'],run_id=int(rid),head_sha=q['source_sha'],
                        status='completed',conclusion='success',started_at=p['started_at_utc'],completed_at=p['created_at_utc']) for p in (q['before_proof'],q['read_proof'],q)]))
                old=rid==seed['old_run']
                if '/jobs?' not in url:return Response(dict(id=int(rid),head_sha=seed['source'],run_attempt=1,event='workflow_dispatch',
                    path='.github/workflows/lab.yml',head_branch='fictional',status='completed' if old else 'in_progress',
                    conclusion=('failure' if damage.get('run') else 'success') if old else None,repository=dict(full_name=store.REPO),
                    head_repository=dict(full_name=store.REPO),actor=dict(login='NickNicky19',id=208912933)))
                if old:
                    h=seed['sidecar']['checkpoint_handoff']
                    times=[(state.utc(h['snapshot_completed_at'])-timedelta(hours=2),state.utc(h['snapshot_completed_at'])-timedelta(hours=1)),
                        (state.utc(h['snapshot_completed_at'])-timedelta(minutes=2),state.utc(seed['writer_done'])),
                        (state.utc(seed['writer_done'])+timedelta(seconds=50),state.utc(seed['old_complete']))]
                    jobs=[dict(id=777+i,name=name,run_id=int(rid),head_sha=seed['source'],status='completed',
                        conclusion='failure' if damage.get('job') and i==1 else 'success',started_at=a.isoformat(),completed_at=b.isoformat())
                        for i,((_,name),(a,b)) in enumerate(zip(JOBS.items(),times))]
                else:jobs=[dict(id=900,name=JOBS[role],run_id=int(rid),head_sha=seed['source'],status='in_progress',conclusion=None,
                    started_at=(current_at-timedelta(minutes=1)).isoformat(),completed_at=None)]
                return Response(dict(total_count=len(jobs),jobs=jobs))
            return server(request,timeout)
    api=API();aliases={}
    for name,doc in seed['docs'].items():
        body=doc.encode() if name=='original_choice' else store.canonical(doc)
        path=root/'epoch'/(name+'.json');storage.write_bytes(path,body);aliases['context/'+name+'.json']=cp.binding(path)
    path=root/'epoch/choice.json';storage.write_bytes(path,store.canonical(seed['choice']))
    aliases.update({'runtime/WEEKLY_CHOICE.json':cp.binding(path),'prepared/choice.json':cp.binding(path)})
    restored=archive.write(storage,root/'epoch/RESTORED.json',dict(aliases=aliases))
    sidecar_body=gzip.compress(store.canonical(seed['sidecar']),mtime=0);receipt_body=gzip.compress(store.canonical(seed['receipt']),mtime=0)
    storage.write_bytes(root/'sidecar.json.gz',sidecar_body);storage.write_bytes(root/'receipt.json.gz',receipt_body)
    journal=root/'journal';journal.mkdir(mode=0o700)
    client=store.Client('ghs_FICTIONAL',NEW_RUN,journal=journal,source_sha=seed['source'],transport=api,
        job=dict(execution_lane='github_actions',workflow_ref=seed['sidecar']['workflow_ref'],workflow_sha=seed['source'],job_id=JOBS[role],
            permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False),operation='metadata')
    client.authenticate_actions_job()
    go=dict(qualified_runtime=deepcopy(seed['package']),pending_census=deepcopy(seed['census']),jobs=JOBS,
        issued_at_utc=(current_at-timedelta(minutes=1)).isoformat(),
        code_pins={n:store.sha((ROOT/n).read_bytes()) for n in history.FILES},
        effective_epoch=dict(schema_version=history.CONTEXT_V2,controller_context=None,
            previous_capture=dict(feed_sha256=seed['receipt']['feed_sha256'],receipt_sha256=store.sha(receipt_body)),
            previous_checkpoint=dict(sha256=store.sha(sidecar_body))))
    context=object.__new__(shared.Authenticated);context.go=go;context.client=client;context.env=dict(GITHUB_TOKEN='ghs_FICTIONAL')
    context.root_sha256='e'*64;context.proof=None;context.request=dict(cache=str(storage.cache),state_root=str(storage.state_root),
        phase='operations-prepare' if role=='produce' else 'operations-grade-'+('write' if role=='restore' else 'read'),inputs=dict(retained_result=restored))
    count=[0]
    def verify(self):
        count[0]+=1
        if native:checkpoint.native_envelope()
        return self
    context.verify=MethodType(verify,context)
    return SimpleNamespace(context=context,storage=storage,sidecar=cp.binding(root/'sidecar.json.gz'),receipt=cp.binding(root/'receipt.json.gz'),
        api=api,calls=calls,damage=damage,server=server,count=count,seed=seed)

@pytest.fixture
def case(tmp_path,original_seed,monkeypatch):
    return recovery_case(tmp_path,original_seed,monkeypatch)

def test_cross_run_native_restore_retains_original_clocks_and_primary_assignment(case):
    from nfl_lab import audit_weekly_grade_v1 as grade,audit_weekly_operations_v1 as ops,state
    x=case;result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert result.verify() is result and grade._digest(result.durable.document)==x.seed['durable_sha256']
    assert result.durable.document['known_versions']==x.seed['known_versions'] and result.durable.document['known_weeks']==x.seed['known_weeks']
    assert result.proof['current']['run_id']==NEW_RUN and result.proof['native_snapshot_recovery']['run_id']==NEW_RUN
    assert result.proof['original_grade_read_proof']==x.seed['sidecar']['grade_read_proof']
    assert result.proof['native_snapshot_recovery']['created_at_utc']!=x.seed['sidecar']['grade_read_proof']['known_by_at']
    choice=grade.epoch.EpochChoice(x.seed['choice'],state.digest(x.seed['choice']))
    population,assignment=ops.primary_population(result.registered,choice,x.seed['roles'],capture_id='9'*64,previous=result.durable,
        authenticate=lambda _:True,clock=history.now)
    assert set(population.document['assignments'].values())==set(x.seed['capture_ids'])
    assert assignment['state']=='REFRESH_NOT_ANOTHER_PRIMARY_OBSERVATION' and not assignment['primary_game_ids']
    assert x.count[0]>4 and all(r.method=='GET' for r in x.calls)
    first=next(i for i,r in enumerate(x.calls) if '/releases/' in r.full_url)
    assert {r.full_url.split('/contents/',1)[1].split('?ref=',1)[0] for r in x.calls[:first] if '/contents/' in r.full_url}==set(x.seed['sources'])
    with pytest.raises(history.HistoryError,match='CANNOT_BE_SERIALIZED'):pickle.dumps(result)
    result.proof['current_root_go_sha256']='0'*64
    with pytest.raises(history.HistoryError,match='PROCESS_OR_BINDING_CHANGED'):result.verify()

@pytest.mark.parametrize('role',['restore','consume'])
def test_current_restore_and_consume_jobs_keep_their_new_native_identity(tmp_path,original_seed,monkeypatch,role):
    x=recovery_case(tmp_path,original_seed,monkeypatch,role=role)
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert result.proof['current']['run_id']==NEW_RUN and result.proof['current']['job_id']==JOBS[role]
    assert result.proof['original_grade_read_proof']['reader']==original_seed['sidecar']['grade_read_proof']['reader']

@pytest.mark.parametrize('damage',['run','job','source'])
def test_old_run_jobs_and_same_code_fail_before_private_GET(case,damage):
    case.damage[damage]=True
    with pytest.raises(history.HistoryError):history.restore_previous(case.context,case.storage,case.sidecar,case.receipt,transport=case.api)
    assert not [r for r in case.calls if '/releases/' in r.full_url]

@pytest.mark.parametrize('damage',['hash','same_run','same_root','source_version','namespace','known_by','missing_evidence'])
def test_saved_sidecar_or_wrong_binding_never_enables_private_GET(case,damage):
    from nfl_lab import private_draft_store as store,gha_private_checkpoint as cp
    x=case;value=deepcopy(x.seed['sidecar'])
    if damage=='hash':x.context.go['effective_epoch']['previous_checkpoint']['sha256']='0'*64
    elif damage=='same_run':x.context.client.run_id=value['run_id']
    elif damage=='same_root':x.context.root_sha256=value['root_go_sha256']
    elif damage=='source_version':x.context.client.source_sha='0'*40
    elif damage=='namespace':x.context.go['qualified_runtime']['binding']['runtime_id']='0'*32
    elif damage=='known_by':value['grade_read_proof']['known_by_at']=x.seed['current_at']
    else:del value['evidence_descriptor']
    if damage in {'known_by','missing_evidence'}:
        body=gzip.compress(store.canonical(value),mtime=0);path=Path(x.context.request['cache']).parent/'changed-sidecar.json.gz'
        x.storage.write_bytes(path,body);x.sidecar=cp.binding(path);x.context.go['effective_epoch']['previous_checkpoint']['sha256']=store.sha(body)
    with pytest.raises((history.HistoryError,store.StoreError)):
        history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert not [r for r in x.calls if '/releases/' in r.full_url]

def test_v1_saved_snapshot_never_becomes_live_history(case):
    case.context.go['effective_epoch'].pop('previous_checkpoint');case.context.go['effective_epoch']['schema_version']='audit-weekly-recurring-v1-context'
    with pytest.raises(history.HistoryError,match='EXPLICIT_PINNED_ROOT_HISTORY_READER_REQUIRED'):
        history.restore_previous(case.context,case.storage,case.sidecar,case.receipt,transport=case.api)
    assert not [r for r in case.calls if '/releases/' in r.full_url]

def test_current_rejection_precedes_owned_metadata(case):
    def reject(self):raise history.HistoryError('CURRENT_AUTHORITY_REJECTED')
    case.context.verify=MethodType(reject,case.context)
    with pytest.raises(history.HistoryError,match='CURRENT_AUTHORITY_REJECTED'):
        history.restore_previous(case.context,case.storage,dict(path='MUST_NOT_OPEN'),case.receipt,transport=case.api)

def test_original_seven_fields_do_not_qualify_missing_or_changed_native_evidence(case):
    x=case;sidecar=x.seed['sidecar']
    asset_id=sidecar['evidence_descriptor']['entry']['payload_asset_id']
    body=next(a['body'] for a in x.server.assets if a['id']==asset_id)
    envelope=json.loads(gzip.decompress(body));envelope['native_read_evidence']['known_by_at']=x.seed['current_at']
    with pytest.raises(history.HistoryError,match='ORIGINAL_NATIVE_GRADE_READ_PROOF_BODY_REQUIRED'):
        history._native_evidence(envelope,sidecar,x.context.client,{})

def test_corrupt_native_evidence_cannot_decode_or_qualify_history(case,monkeypatch):
    from nfl_lab import audit_weekly_grade_v1 as grade,private_draft_store as store
    asset_id=case.seed['sidecar']['evidence_descriptor']['entry']['payload_asset_id']
    next(a for a in case.server.assets if a['id']==asset_id)['body']=b'FICTIONAL_CORRUPTED_NATIVE_EVIDENCE'
    monkeypatch.setattr(grade,'restore_snapshot',lambda *_a,**_k:pytest.fail('SNAPSHOT_DECODE_WITHOUT_ORIGINAL_NATIVE_EVIDENCE'))
    with pytest.raises(store.StoreError):history.restore_previous(case.context,case.storage,case.sidecar,case.receipt,transport=case.api)

def test_serialized_current_authority_flags_cannot_start_history(case):
    with pytest.raises(history.HistoryError,match='LIVE_SHARED_HISTORY_CONTEXT_REQUIRED'):
        history.restore_previous(dict(verified=True),case.storage,case.sidecar,case.receipt,transport=case.api)

@pytest.mark.parametrize('damage',['assignment','roles','schedule','choice'])
def test_refresh_cannot_change_original_assignment_roles_schedule_or_weekly_recipe(original_seed,damage):
    from nfl_lab import audit_weekly_operations_grade_v1 as worker,audit_weekly_grade_v1 as grade,state
    descriptor=original_seed['sidecar']['checkpoint_handoff']['descriptor']
    body=base64.b64decode(next(a['body'] for a in original_seed['assets'] if a['id']==descriptor['entry']['payload_asset_id']))
    capture=grade._unpack(body,64 << 20)['captures'][0]
    population=deepcopy(original_seed['population']);roles=deepcopy(original_seed['roles']);schedule=deepcopy(original_seed['schedule'])
    choice=grade.epoch.EpochChoice(deepcopy(original_seed['choice']),state.digest(original_seed['choice']))
    worker._reuse_assignment(capture,population,roles,schedule,choice)
    if damage=='assignment':population['assignments'][next(iter(population['assignments']))]='0'*64
    elif damage=='roles':roles['rec']['primary_roles']=['QB']
    elif damage=='schedule':schedule[0]['website_game_id']='999999'
    else:choice.document['choice']['selections'][0]['members'][0]['weight']=0.123
    with pytest.raises(worker.GradeBridgeError,match='ORIGINAL_PRIMARY_ASSIGNMENT_REUSE_NO_REFRESH_REISSUANCE'):
        worker._reuse_assignment(capture,population,roles,schedule,choice)

def test_grade_write_requalifies_history_and_refresh_uses_original_capture(tmp_path,original_seed,monkeypatch):
    from nfl_lab import audit_weekly_operations_grade_v1 as worker,audit_weekly_grade_v1 as grade
    from nfl_lab import audit_weekly_archive_v1 as archive,private_draft_store as store,state,gha_private_checkpoint as cp
    x=recovery_case(tmp_path,original_seed,monkeypatch,role='restore');x.api.allow_append=True
    x.context.client.bind(x.context.go['qualified_runtime']['binding'])
    restored=cp.strict_json(archive.read_owned(x.storage,x.context.request['inputs']['retained_result'],raw=True))
    population=deepcopy(original_seed['population']);population['registered_at']=history.now().isoformat()
    for name,doc in [('ops_population',population),('ops_roles',original_seed['roles']),
        ('ops_schedule',[dict(r,game_type='REG') for r in original_seed['schedule']])]:
        restored['aliases']['context/'+name+'.json']=archive.write(x.storage,tmp_path/'current-context'/(name+'.json'),doc)
    restored['aliases']['context/ops_previous_checkpoint_sidecar.json']=x.sidecar
    restored['aliases']['context/ops_previous_public_receipt.json']=x.receipt
    restored['index_sha256']='a'*64
    ref=archive.write(x.storage,tmp_path/'current-archive/RESTORED.json',restored)
    p=dict(schema_version=worker.VERSION+'-request',phase=worker.PHASES[0],code_pins={},limits=dict(worker.LIMITS),
        cache=str(x.storage.cache),state_root=str(x.storage.state_root),output=str(tmp_path/worker.PHASES[0]),
        inputs=dict(archive_restored=ref,previous_snapshot=None))
    context=object.__new__(worker.Authenticated);context.request=p;context.shared=x.context;context.go=x.context.go
    context.client=x.context.client;context.root_sha256=x.context.root_sha256;context.env=x.context.env
    context.proof=None;context.root_bytes=store.canonical(context.go);context.verify=MethodType(lambda self:self,context)
    monkeypatch.setattr(worker,'_archive',lambda *_:(restored,{}))  # archive gate has its own real native protocol suite
    monkeypatch.setattr(grade,'bind_capture',lambda *_a,**_k:pytest.fail('REFRESH_MUST_NOT_REISSUE_PRIMARY_CAPTURE'))
    calls=[]
    def fetch(cache,name,url,*,day,storage):
        calls.append(url)
        if name.startswith('schedule'):
            status=dict(completed=True,state='post',name='STATUS_FINAL')
            events=[dict(id=g['website_game_id'],date=g['kickoff_utc'],status=dict(type=status),competitions=[dict(status=dict(type=status),
                competitors=[dict(homeAway='home',team=dict(abbreviation=g['home'])),dict(homeAway='away',team=dict(abbreviation=g['away']))])]) for g in original_seed['schedule']]
            value=dict(season=dict(year=2026,type=2),week=dict(number=7),events=events)
        else:value=[dict(player_id=r['sleeper_id'],season=2026,week=7,team=r['team'],stats=dict(gp=1,rec=0)) for r in original_seed['query']]
        raw=state.canonical(value);path=storage.live_root/day/(name+'.json')
        receipt=dict(name=name+'.json',url=url,status='acquired',bytes=len(raw),sha256=store.sha(raw),retrieved_utc=history.now().isoformat(),
            original_publication_utc=None,cache_reused=False)
        storage.write_bytes(path,raw);storage.write_bytes(path.with_name(path.name+'.receipt.json'),state.canonical(receipt))
        return value,receipt
    written=worker.execute(context,transport=x.api,fetch=fetch,clock=history.now)
    report=archive.read_owned(x.storage,written['manifest'])
    doc=grade._unpack(archive.read_owned(x.storage,report['snapshot'],8 << 20,raw=True),64 << 20)
    assert [c['capture_id'] for c in doc['captures']]==original_seed['capture_ids']
    assert doc['captures'][0]['archive_index_sha256']!=restored['index_sha256']
    assert all(doc['known_versions'][k]==v for k,v in original_seed['known_versions'].items())
    assert all(doc['known_weeks'][k]==v for k,v in original_seed['known_weeks'].items())
    assert len(calls)==2 and written['state']=='PRIVATE_GRADE_APPENDED_FRESH_READER_REQUIRED'
    assert written['checkpoint_handoff']['producer']['run_id']==NEW_RUN
    assert any('/contents/' in r.full_url for r in x.calls) and any(r.method=='POST' for r in x.calls)

@pytest.fixture
def parent_metadata():
    """Synthetic public metadata only; deliberately no private history grant.

    No grade/checkpoint execution or mutable numerical helper pin is needed to
    test this parser. Full native provenance remains covered by original_seed.
    """
    from nfl_lab import private_draft_store as store,state
    from test_owner_private_bootstrap import qualification
    sha=lambda label:store.sha(label.encode())
    stamp=lambda time:'2026-10-28T'+time+'+00:00'
    run='45000000001';workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/fictional'
    pins={n:sha('FICTIONAL_DECLARED_ROOT_PIN:'+n) for n in history._GRADE_PIN_PATHS|history._CHECKPOINT_PIN_PATHS|set(history.FILES)|{'.github/workflows/lab.yml'}}
    grade_pins={n:pins[n] for n in history._GRADE_PIN_PATHS};helper_pins={n:pins[n] for n in history._CHECKPOINT_PIN_PATHS}
    tag='weekly-private-runtime-v2-'+'c'*32;canary=sha('FICTIONAL_CANARY')
    binding=dict(schema_version='weekly-private-draft-binding-v2',repository=store.REPO,runtime_id='c'*32,origin_run_id='40000000001',
        release_id=42,tag_name=tag,canary_asset_id=1,canary_name='canary-'+canary+'.txt',canary_sha256=canary,canary_bytes=117,
        browser_tag=tag,config_sha256=store.CONFIG_SHA256)
    q=qualification(binding);q['created_at_utc']='2026-10-20T00:00:00+00:00';source=q['source_sha']
    package=dict(schema_version='audit-private-rotation-v1-qualified-runtime',runtime_reserved_bytes=store.TOTAL_CAP,runtime_id=binding['runtime_id'],
        binding=binding,qualification=q,quota_reservation={},run_id=q['run_id'],source_sha=source)
    bind_sha=store.sha(store.canonical(binding))
    def identity(role,process):
        return dict(execution_lane='github_actions',repository=store.REPO,run_id=run,run_attempt=1,source_sha=source,process_identity=process*64,
            job_id=JOBS[role],api_job_id=778 if role=='restore' else 779,permission='write',workflow_ref=workflow_ref)
    writer=identity('restore','b');reader=identity('consume','d');evidence_writer=identity('consume','f')
    def descriptor(label,process,asset_id):
        body=gzip.compress(store.canonical(dict(fictional_metadata_reference_only=label)),mtime=0);body_sha=store.sha(body)
        payload=dict(schema_version='weekly-private-payload-v2',payload_kind='runtime_manifest',format='gzip',bytes=len(body),sha256=body_sha,
            source_policy_sha256=history._METADATA_POLICY_SHA)
        entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=payload,payload_asset_id=asset_id,payload_name='blob-'+body_sha+'.bin',
            producer_process=process,binding_sha256=bind_sha,writer_run_id=run)
        return dict(entry=entry,manifest_asset_id=asset_id+1,manifest_sha256=store.sha(store.canonical(entry)),manifest_bytes=len(store.canonical(entry)))
    snapshot=descriptor('snapshot',writer['process_identity'],11);envelope=descriptor('evidence',evidence_writer['process_identity'],13)
    h=dict(schema_version='audit-weekly-grade-checkpoint-v1-handoff',repository=store.REPO,current_root_go_sha256='c'*64,epoch_sha256='e'*64,
        snapshot_sha256=sha('FICTIONAL_SNAPSHOT_DOCUMENT'),body_sha256=snapshot['entry']['payload']['sha256'],body_bytes=snapshot['entry']['payload']['bytes'],
        snapshot_completed_at=stamp('08:01:00'),producer=writer,runtime_binding_sha256=bind_sha,qualified_package_sha256=state.digest(package),
        grade_code_pins_sha256=state.digest(grade_pins),helper_sha256=helper_pins,descriptor=snapshot,successful_forecast=False,public_release=False,fits=0)
    append=dict(schema_version='audit-weekly-grade-checkpoint-v1-native-append',producer=writer,
        **{k:h[k] for k in ('current_root_go_sha256','epoch_sha256','snapshot_sha256','body_sha256','body_bytes')},descriptor_sha256=state.digest(snapshot),
        qualification_sha256=state.digest(q),api_evidence_sha256=sha('FICTIONAL_API_EVIDENCE'),started_at_utc=stamp('08:01:00'),
        completed_at_utc=stamp('08:01:05'),HTTP_calls=20,transfer_bytes=1000)
    h.update(append_proof=append,append_proof_sha256=state.digest(append))
    proof=dict(schema_version='audit-weekly-grade-v1-durability',snapshot_sha256=h['snapshot_sha256'],restored_body_sha256=h['body_sha256'],
        known_by_at=stamp('08:03:00'),producer=writer,reader=reader,proof_sha256=sha('FICTIONAL_UNREAD_NATIVE_EVIDENCE'))
    times=[('07:00:00','07:30:00'),('07:59:00','08:01:10'),('08:02:00','08:04:00')]
    jobs={r:dict(id=777+i,name=name,run_id=int(run),head_sha=source,status='completed',conclusion='success',started_at=stamp(a),completed_at=stamp(b))
        for i,((r,name),(a,b)) in enumerate(zip(JOBS.items(),times))}
    receipt=dict(schema_version='audit-weekly-delivery-v1-public-receipt',source_sha=source,run_id=run,root_go_sha256=h['current_root_go_sha256'],
        policy_sha256=sha('policy'),policy_registered_at_utc='2026-10-20T00:00:00+00:00',workflow_sha256=pins['.github/workflows/lab.yml'],
        recipe_registration_sha256=sha('recipe'),rights_authority_sha256=sha('rights'),r0_identity_sha256=sha('R0'),origin_choice_sha256=sha('origin'),
        feed_sha256=sha('feed'),feed_bytes=100,rows=1,categories=['rec'],jobs={r:dict(job_id=j['name'],api_job_id=j['id']) for r,j in jobs.items()},
        created_at=stamp('08:03:10'),verified_at=stamp('08:03:00'),fits=0,raw_or_models_public=False,archive_index_sha256=sha('index'),
        archive_files_sha256=sha('files'),reader_witness_sha256=sha('witness'),epoch_sha256=h['epoch_sha256'],choice_sha256=sha('choice'))
    value=dict(schema_version=history.VERSION+'-sidecar',repository=store.REPO,
        **{k:receipt[k] for k in ('feed_sha256','source_sha','run_id','root_go_sha256','workflow_sha256','epoch_sha256')},workflow_ref=workflow_ref,
        checkpoint_handoff=h,grade_read_proof=proof,grade_code_pins=grade_pins,checkpoint_helper_sha256=helper_pins,
        evidence_descriptor=envelope,evidence_producer=evidence_writer)
    return dict(packed=gzip.compress(store.canonical(value),mtime=0),receipt=receipt,qualified_runtime=package,code_pins=pins,jobs=jobs,
        at='2026-10-29T08:00:00+00:00')

def test_parent_validator_is_pure_metadata_and_preserves_original_proof(parent_metadata,monkeypatch):
    from nfl_lab import audit_weekly_grade_v1 as grade,private_draft_store as store
    from nfl_lab import audit_weekly_parent_v1 as parent
    original=deepcopy(parent_metadata);sidecar=json.loads(gzip.decompress(parent_metadata['packed']))
    def forbidden(*_a,**_k):pytest.fail('PARENT_METADATA_MUST_NOT_READ_FILES_NETWORK_OR_GRADE_BODIES')
    monkeypatch.setattr(history,'_modules',forbidden)
    monkeypatch.setattr(store,'read_local',forbidden)
    monkeypatch.setattr(grade,'restore_snapshot',forbidden);monkeypatch.setattr(grade,'confirm_durable',forbidden)
    monkeypatch.setattr(grade,'_unpack',forbidden)
    monkeypatch.setattr(Path,'read_bytes',forbidden);monkeypatch.setattr(Path,'read_text',forbidden)
    monkeypatch.setattr('builtins.open',forbidden)
    result=history.validate_parent_sidecar(**parent_metadata)
    assert type(result) is dict and result==sidecar
    assert result['grade_read_proof']==sidecar['grade_read_proof']
    assert result['grade_read_proof']['known_by_at']==sidecar['grade_read_proof']['known_by_at']
    assert parent_metadata==original
    assert parent._checkpoint_metadata(**parent_metadata)==dict(sha256=store.sha(parent_metadata['packed']))

@pytest.mark.parametrize('damage',['sidecar_keys','receipt_source','receipt_root','receipt_feed','receipt_epoch','receipt_jobs',
    'job_failed','job_source','job_run','job_id','job_clock','known_by','append_clock','descriptor','envelope_process',
    'namespace','grade_pin','helper_pin','workflow_pin','missing_pin','authority_flag','gzip_trailing','gzip_multiple',
    'noncanonical','oversize_plain','oversize_packed'])
def test_parent_validator_rejects_unbound_or_noncanonical_metadata(parent_metadata,damage):
    from nfl_lab import private_draft_store as store
    data=deepcopy(parent_metadata);value=json.loads(gzip.decompress(data['packed']))
    if damage=='sidecar_keys':value['rows']=[]
    elif damage.startswith('receipt_') and damage!='receipt_jobs':data['receipt'][dict(receipt_source='source_sha',receipt_root='root_go_sha256',
        receipt_feed='feed_sha256',receipt_epoch='epoch_sha256')[damage]]='0'*(40 if damage=='receipt_source' else 64)
    elif damage=='receipt_jobs':data['receipt']['jobs']['consume']['api_job_id']+=1
    elif damage=='job_failed':data['jobs']['restore']['conclusion']='failure'
    elif damage=='job_source':data['jobs']['restore']['head_sha']='0'*40
    elif damage=='job_run':data['jobs']['consume']['run_id']+=1
    elif damage=='job_id':data['jobs']['consume']['id']+=1
    elif damage=='job_clock':data['jobs']['consume']['completed_at']=data['jobs']['consume']['started_at']
    elif damage=='known_by':value['grade_read_proof']['known_by_at']=data['at']
    elif damage=='append_clock':
        value['checkpoint_handoff']['append_proof']['completed_at_utc']=data['at']
        value['checkpoint_handoff']['append_proof_sha256']=hashlib.sha256(json.dumps(value['checkpoint_handoff']['append_proof'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    elif damage=='descriptor':value['checkpoint_handoff']['descriptor']['entry']['payload']['sha256']='0'*64
    elif damage=='envelope_process':
        d=value['evidence_descriptor'];d['entry']['producer_process']='0'*64
        d['manifest_bytes']=len(store.canonical(d['entry']));d['manifest_sha256']=store.sha(store.canonical(d['entry']))
    elif damage=='namespace':data['qualified_runtime']['binding']['release_id']+=1
    elif damage=='grade_pin':data['code_pins']['nfl_lab/audit_weekly_grade_v1.py']='0'*64
    elif damage=='helper_pin':data['code_pins']['nfl_lab/audit_weekly_grade_checkpoint_v1.py']='0'*64
    elif damage=='workflow_pin':data['code_pins']['.github/workflows/lab.yml']='0'*64
    elif damage=='missing_pin':del data['code_pins'][history.FILES[0]]
    elif damage=='authority_flag':data['qualified_runtime']=dict(qualified=True)
    body=store.canonical(value)
    if damage=='noncanonical':body=json.dumps(value,indent=2).encode()
    elif damage=='oversize_plain':body=b' '*(history.LIMITS['metadata_plain_bytes']+1)
    data['packed']=gzip.compress(body,mtime=0)
    if damage=='gzip_trailing':data['packed']+=b'FORBIDDEN_TRAILING_BYTES'
    elif damage=='gzip_multiple':data['packed']+=gzip.compress(b'{}',mtime=0)
    elif damage=='oversize_packed':data['packed']=b'X'*(history.LIMITS['sidecar_bytes']+1)
    with pytest.raises(history.HistoryError):history.validate_parent_sidecar(**data)

def test_parent_validator_cold_import_does_not_load_grade_or_read_sources(parent_metadata,tmp_path):
    data=deepcopy(parent_metadata);data['packed']=base64.b64encode(data['packed']).decode()
    path=tmp_path/'parent-metadata.json';path.write_text(json.dumps(data))
    script='''import sys,json,base64,socket
from pathlib import Path
from unittest.mock import patch
from nfl_lab import audit_weekly_grade_history_v1 as history,private_draft_store as store
data=json.loads(Path(sys.argv[1]).read_text());data["packed"]=base64.b64decode(data["packed"])
def forbidden(*args,**kwargs):raise AssertionError("METADATA_IO_FORBIDDEN")
with patch.object(store,"read_local",forbidden),patch.object(Path,"read_bytes",forbidden),patch.object(Path,"read_text",forbidden),patch("builtins.open",forbidden),patch.object(socket.socket,"connect",forbidden):
    result=history.validate_parent_sidecar(**data)
assert type(result) is dict
assert not any(n in sys.modules for n in ("nfl_lab.audit_weekly_grade_v1","nfl_lab.audit_weekly_grade_checkpoint_v1","numpy","scipy","pandas","sklearn"))
print("PURE_PARENT_METADATA_OK")
'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(path)],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='PURE_PARENT_METADATA_OK'

def test_native_bounded_history_recovery_once(original_seed,tmp_path):
    seed=tmp_path/'fictional-history-seed.json';seed.write_text(json.dumps(original_seed))
    script='''import sys,json,resource,socket
from pathlib import Path
from tools.private_draft_store_v2 import limits
limits()
sys.path.insert(0,str(Path.cwd()/"tests"))
from pytest import MonkeyPatch
from test_audit_weekly_grade_history_v1 import recovery_case
from nfl_lab import audit_weekly_grade_history_v1 as history,audit_weekly_grade_v1 as grade
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError("REAL_NETWORK_FORBIDDEN"))
seed=json.loads(Path(sys.argv[1]).read_text());patch=MonkeyPatch()
case=recovery_case(Path(sys.argv[2]),seed,patch,native=True)
value=history.restore_previous(case.context,case.storage,case.sidecar,case.receipt,transport=case.api)
assert grade._digest(value.durable.document)==seed["durable_sha256"]
assert all(r.method=="GET" for r in case.calls)
print(json.dumps(dict(fictional=True,AS_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],RSS_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)))
'''
    profile=json.loads((ROOT/'config/audit-weekly-numerical-runtime-v1.json').read_text())['environment']
    result=subprocess.run([sys.executable,'-B','-c',script,str(seed),str(tmp_path/'native-owned')],cwd=ROOT,
        env=dict(PYTHONDONTWRITEBYTECODE='1',**profile),capture_output=True,text=True,timeout=185)
    print(result.stdout,end='')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['AS_bytes']==512 << 20
