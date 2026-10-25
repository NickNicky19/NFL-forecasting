"""Fictional current context/E7/native service; no real Actions or NFL reads."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import gzip
import json
from pathlib import Path
import pickle
import resource
import signal
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nfl_lab import audit_weekly_operations_grade_v1 as worker
from nfl_lab import audit_weekly_grade_checkpoint_v1 as checkpoint,audit_weekly_grade_v1 as grade
from nfl_lab import audit_weekly_archive_v1 as archive,private_draft_store as store,state,gha_private_checkpoint as cp
from tools import audit_weekly_operations_grade_v1 as cli
from test_audit_weekly_grade_v1 import packet as grade_packet,GRADE
from test_audit_weekly_grade_checkpoint_v1 import Service,RUN,SOURCE,ROOT_SHA
from nfl_lab.operational_storage import StorageIntegrityError

ROOT=Path(__file__).resolve().parents[1]
ACTUAL_ARCHIVE=worker._archive
ACTUAL_EPOCH=worker._epoch


def test_grade_only_v2_reference_requires_explicit_root_and_owned_history_pair(tmp_path):
    base=tmp_path/'owned';p=request(base,worker.PHASES[0])
    p['schema_version']=worker.VERSION+'-request-v2'
    p['inputs']['archive_restored']['path']=str(base/'recovered'/'RETAINED_RESULT.json')
    pair={name:dict(path=str(base/(name+'.json.gz')),bytes=10,sha256='a'*64) for name in ('sidecar','public_receipt')}
    p['inputs']['previous_history']=pair
    go=dict(effective_epoch=dict(plan=dict(kind='GRADE_ONLY')))
    assert worker.validate_request(p,worker.PHASES[0],go=go) is p
    for root in (None,dict(effective_epoch=None),dict(effective_epoch=dict(plan=dict(kind='FUTURE_CAPABLE')))):
        with pytest.raises(worker.GradeBridgeError):worker.validate_request(p,worker.PHASES[0],go=root)
    bad=deepcopy(p);bad['inputs']['previous_history']['outcomes']=[]
    with pytest.raises(worker.GradeBridgeError):worker.validate_request(bad,worker.PHASES[0],go=go)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *_:pytest.fail('REAL_NETWORK_FORBIDDEN'))


def request(root,phase):
    return dict(schema_version=worker.VERSION+'-request',phase=phase,limits=dict(worker.LIMITS),code_pins={n:'a'*64 for n in worker.FILES},
        cache=str(root/'cache'),state_root=str(root/'state'),output=str(root/phase),inputs=dict(archive_restored=dict(
            path=str(root/'archive/RESTORED.json'),bytes=1,sha256='a'*64),**({'previous_snapshot':None} if phase==worker.PHASES[0] else {'checkpoint_handoff':{}})))


def test_closed_request_never_accepts_a_saved_previous_snapshot_or_extra_callback_name(tmp_path):
    p=request(tmp_path,worker.PHASES[0]);assert worker.validate_request(p,p['phase']) is p
    p['inputs']['previous_snapshot']=dict(qualified=True,source_sha='a'*40)
    with pytest.raises(worker.GradeBridgeError,match='CROSS_RUN'):worker.validate_request(p,p['phase'])
    p['inputs']['previous_snapshot']=None;p['inputs']['callback']='approve'
    with pytest.raises(worker.GradeBridgeError,match='CLOSED'):worker.validate_request(p,p['phase'])


def test_real_native_caps_and_stdlib_import_in_fresh_process():
    script='''import sys,json,resource,signal
sys.path.insert(0,sys.argv[1])
from nfl_lab import audit_weekly_operations_grade_v1 as w
assert not any(n in sys.modules for n in ("numpy","scipy","sklearn","pandas"))
try:w.native_envelope()
except w.GradeBridgeError:pass
else:raise AssertionError("MISSING_NATIVE_GUARD_ACCEPTED")
from tools.private_draft_store_v2 import limits
limits();w.native_envelope()
assert resource.getrlimit(resource.RLIMIT_CPU)==(120,120)
assert resource.getrlimit(resource.RLIMIT_AS)==(512<<20,512<<20)
assert signal.getsignal(signal.SIGALRM)==signal.SIG_DFL and 0<signal.getitimer(signal.ITIMER_REAL)[0]<=180
print(json.dumps({"native_envelope":True,"private_IO":False}))
'''
    result=subprocess.run([sys.executable,'-I','-B','-c',script,str(ROOT)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==dict(native_envelope=True,private_IO=False)


def test_actual_root_rejection_precedes_owned_request_and_private_body_reads(tmp_path,monkeypatch):
    from nfl_lab import audit_weekly_hosted_v1 as hosted,audit_weekly_operations_worker_v1 as shared_guard
    monkeypatch.setattr(worker,'native_envelope',lambda:None)
    def reject(*args,**kwargs):raise store.StoreError('ACTUAL_ROOT_REJECTED')
    monkeypatch.setattr(shared_guard,'authenticate_child',reject)
    monkeypatch.setattr(hosted,'child_context',lambda *_a,**_k:pytest.fail('READ_REQUEST_BEFORE_CURRENT_AUTHORITY'))
    monkeypatch.setattr(archive,'read_owned',lambda *_a,**_k:pytest.fail('READ_BODY_BEFORE_CURRENT_AUTHORITY'))
    args=SimpleNamespace(phase=worker.PHASES[0],request=str(tmp_path/'private'),request_sha256='a'*64)
    with pytest.raises(store.StoreError,match='ACTUAL_ROOT_REJECTED'):worker.guard(args,{'AUDIT_WEEKLY_ROOT_GO_JSON':'{"owner_root_checked":true}'})


@pytest.fixture
def authenticated_guard(tmp_path,monkeypatch):
    """Actual typed bootstrap/API/client bytecode, fictional child_context seam."""
    import test_audit_weekly_operations_worker_v1 as fixture
    from nfl_lab import audit_weekly_operations_worker_v1 as shared,audit_weekly_controller_v1 as controller
    (tmp_path/'bootstrap').mkdir()
    x=fixture.locator_system.__wrapped__(fixture.system.__wrapped__(tmp_path/'bootstrap'))
    from nfl_lab import audit_weekly_grade_history_v1 as history
    with patch.object(shared,'FILES',shared.FILES+worker.FILES+history.FILES):
        q=fixture.guard_case.__wrapped__(x,tmp_path/'grade-guard',monkeypatch)
    phase=worker.PHASES[0];base=Path(q.request['cache']).parent
    q.request.clear();q.request.update(request(base,phase));q.request['code_pins']=x.go['code_pins']
    x.env['GITHUB_JOB']=q.env['GITHUB_JOB']=x.go['jobs']['restore']
    x.api.data[controller.jobs_url('300')]['jobs'][0]['name']=x.env['GITHUB_JOB']
    x.go.update(qualified_runtime=x.package,pending_census=dict(reservations=[]));x.bind_root()
    x.claim['root_go_sha256']=store.sha(x.raw)
    x.api.data[controller.contents_url(x.claim_path,fixture.original.D)]=fixture.original.content(x.claim_path,store.canonical(x.claim))
    x.api.data[controller.API+'/commits/'+fixture.original.D]['files'][0]['sha']=controller.blob_sha(store.canonical(x.claim))
    q.native.update(phase=phase,job_id=x.env['GITHUB_JOB'],owner_root_go_sha256=store.sha(x.raw),request_sha256=state.digest(q.request))
    q.env.update(AUDIT_WEEKLY_ROOT_GO_JSON=x.raw.decode(),AUDIT_WEEKLY_ROOT_GO_SHA256=store.sha(x.raw),
        AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON=store.canonical(q.native).decode(),AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256=state.digest(q.native))
    q.args.phase=phase;q.args.request_sha256=state.digest(q.request)
    monkeypatch.setattr(worker,'native_envelope',lambda:None)  # syscall coverage is in separate cold workers
    return q


def test_guard_verifies_fresh_typed_Root_API_and_attaches_actual_client_before_private_read(authenticated_guard,monkeypatch):
    q=authenticated_guard
    monkeypatch.setattr(archive,'read_owned',lambda *_a,**_k:pytest.fail('NO_PRIVATE_BODY_READ_DURING_AUTH'))
    context=worker.guard(q.args,q.env,transport=q.transport)
    assert context.verify()is context
    assert context.client.job['api_job_id']==31 and context.client.job['job_id']==checkpoint.JOBS['writer']
    assert context.client.binding==q.x.package['binding']
    assert isinstance(context.client,archive.Client) and context.client.readonly is True
    qualifier_url=store.API+'/actions/runs/'+q.x.package['qualification']['run_id']
    assert context.client.allow(qualifier_url)==qualifier_url
    assert not Path(context.request['inputs']['archive_restored']['path']).exists()
    assert q.calls.index('static-root')<q.calls.index('fresh-proof')<q.calls.index('child-context')
    with pytest.raises(worker.GradeBridgeError,match='CANNOT_BE_SERIALIZED'):pickle.dumps(context)
    context.client.process='0'*64
    with pytest.raises(worker.GradeBridgeError,match='PROCESS_OR_CURRENT_IDENTITY_CHANGED'):context.verify()


@pytest.mark.parametrize('failure',['root_hash','source','actor','job','inventory'])
def test_actual_root_source_actor_job_and_code_failure_never_reads_payload(authenticated_guard,monkeypatch,failure):
    q=authenticated_guard
    from nfl_lab import audit_weekly_controller_v1 as c,audit_weekly_controller_bootstrap_v1 as b,audit_weekly_operations_worker_v1 as shared
    monkeypatch.setattr(archive,'read_owned',lambda *_a,**_k:pytest.fail('REJECT_BEFORE_PRIVATE_BODY'))
    if failure=='root_hash':q.env['AUDIT_WEEKLY_ROOT_GO_SHA256']='0'*64
    elif failure=='source':q.x.api.data[c.run_url('300')]['head_sha']='0'*40
    elif failure=='actor':q.x.api.data[c.run_url('300')]['actor']=dict(c.OWNER)
    elif failure=='job':q.x.api.data[c.jobs_url('300')]['jobs'][0]['name']='wrong_job'
    else:(q.x.child_source/worker.FILES[0]).write_bytes(b'FICTIONAL_CHANGED_CURRENT_EXECUTABLE')
    with pytest.raises((worker.GradeBridgeError,shared.WorkerError,store.StoreError,c.ControllerError,b.BootstrapError)):
        worker.guard(q.args,q.env,transport=q.transport)
    assert not Path(q.request['output']).exists()


@pytest.fixture
def pipeline(tmp_path,monkeypatch):
    root=tmp_path/'owned';root.mkdir();q=grade_packet.__wrapped__(root)
    q['storage'].register_root(tmp_path)
    service=Service(tmp_path)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return service.now if tz else service.now.replace(tzinfo=None)
    monkeypatch.setattr(store,'datetime',Clock)
    # Native syscalls/current hosted context are independently injected here.
    # The fresh-process test above exercises the real syscall preconditions.
    monkeypatch.setattr(worker.Authenticated,'verify',lambda self:self)
    monkeypatch.setattr(checkpoint,'native_envelope',lambda:None)
    monkeypatch.setattr(resource,'getrusage',lambda *_:SimpleNamespace(ru_maxrss=1024))
    restored=deepcopy(q['restored'])
    def put(name,doc):return archive.write(q['storage'],root/name,doc)
    for role,value in [('ops_population',q['pop']),('ops_roles',q['roles']),('ops_schedule',[dict(r,game_type='REG') for r in q['schedule']])]:
        restored['aliases']['context/'+role+'.json']=put('ops/'+role+'.json',value)
    restored_ref=put('input/RESTORED.json',restored)
    counters=[0];clients=[];fetch_calls=[]
    def client(context,operation,transport,readonly=False):
        counters[0]+=1;role='writer' if operation=='append' else 'reader'
        journal=tmp_path/('native-journal-'+str(counters[0]));q['storage'].register_root(journal)
        c=archive.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=service.transport,
            job=dict(execution_lane='github_actions',workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',
                workflow_sha=SOURCE,job_id=checkpoint.JOBS[role],permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False),
            operation=operation,qualification=service.q,readonly=readonly,process=store.sha((role+str(counters[0])).encode()))
        c.bind(service.binding);clients.append(c);return c
    monkeypatch.setattr(worker,'_client',client)
    # Archive authentication and typed epoch loading have separate negative
    # coverage. This seam represents the already authenticated fictional graph.
    monkeypatch.setattr(worker,'_archive',lambda *_:(restored,{}))
    monkeypatch.setattr(worker,'_epoch',lambda *_:(q['r'],q['c']))
    monkeypatch.setattr(worker,'_replay',lambda *_:q['f']['replay'])
    def context(phase,handoff=None):
        p=request(root,phase);p['inputs']['archive_restored']=restored_ref
        if handoff is not None:p['inputs']['checkpoint_handoff']=handoff
        c=object.__new__(worker.Authenticated);c.request=p;c.go=dict(qualified_runtime=service.package,pending_census=service.census)
        c.root_sha256=ROOT_SHA;c.env={};return c
    def fetch(cache,name,url,*,day,storage):
        fetch_calls.append(url)
        if name.startswith('schedule'):
            events=[]
            for game in q['schedule']:
                status=dict(completed=True,state='post',name='STATUS_FINAL')
                events.append(dict(id=game['website_game_id'],date=game['kickoff_utc'],status=dict(type=status),competitions=[dict(status=dict(type=status),
                    competitors=[dict(homeAway='home',team=dict(abbreviation=game['home'])),dict(homeAway='away',team=dict(abbreviation=game['away']))])]))
            value=dict(season=dict(year=2026,type=2),week=dict(number=7),events=events)
        else:
            value=[dict(player_id=r['sleeper_id'],season=2026,week=7,team=r['team'],stats=dict(gp=1,rec=0)) for r in q['query']]
        raw=state.canonical(value);path=storage.live_root/day/(name+'.json')
        receipt=dict(name=name+'.json',url=url,status='acquired',bytes=len(raw),sha256=store.sha(raw),retrieved_utc=service.now.isoformat(),
            original_publication_utc=None,cache_reused=False)
        storage.write_bytes(path,raw);storage.write_bytes(path.with_name(path.name+'.receipt.json'),state.canonical(receipt))
        return value,receipt
    return SimpleNamespace(q=q,root=root,service=service,context=context,fetch=fetch,fetch_calls=fetch_calls,clients=clients,restored=restored)


def test_real_provider_grade_native_append_and_distinct_job_restore_remain_private(pipeline):
    x=pipeline;originals={k:Path(v['path']).read_bytes() for k,v in x.restored['aliases'].items()}
    written=worker.execute(x.context(worker.PHASES[0]),fetch=x.fetch,clock=lambda:x.service.now)
    handoff=written['checkpoint_handoff'];checkpoint.safe_handoff(handoff)
    assert written['state']=='PRIVATE_GRADE_APPENDED_FRESH_READER_REQUIRED'
    assert len(x.fetch_calls)==2 and x.fetch_calls[0].startswith('https://site.api.espn.com/')
    assert x.fetch_calls[1].startswith('https://api.sleeper.app/stats/nfl/')
    assert not written['public_release'] and not written['successful_forecast']
    x.service.writer_done=(x.service.now+timedelta(seconds=10)).isoformat();x.service.now+=timedelta(minutes=2)
    read=worker.execute(x.context(worker.PHASES[1],handoff),clock=lambda:x.service.now)
    assert read['state']=='PRIVATE_OPERATIONAL_GRADING_FRESH_READER_VERIFIED'
    result=archive.read_owned(x.q['storage'],read['manifest'])
    durable=archive.unpack(archive.read_owned(x.q['storage'],result['durable_history'],8 << 20,raw=True),64 << 20)
    assert durable['local_only'] is False and durable['public_release'] is False
    rows=[r for v in durable['versions'] for r in v['snapshot']['rows'] if r['category']=='rec']
    assert rows and all(r['actual']==0 and r['participation_state']=='played' for r in rows)
    assert all(c.calls<=40 for c in x.clients)
    assert x.clients[0].job['api_job_id']!=x.clients[1].job['api_job_id']
    assert len([r for r in x.service.calls if r.method=='POST'])==2
    for name,ref in x.restored['aliases'].items():assert Path(ref['path']).read_bytes()==originals[name]


def test_provider_failure_retains_native_sources_without_checkpoint_POST(pipeline):
    x=pipeline
    def fail(cache,name,url,**kwargs):
        if name.startswith('statistics'):raise RuntimeError('FICTIONAL_PRIVATE_LIBRARY_TEXT')
        return x.fetch(cache,name,url,**kwargs)
    with pytest.raises(RuntimeError):worker.execute(x.context(worker.PHASES[0]),fetch=fail,clock=lambda:x.service.now)
    assert not [r for r in x.service.calls if r.method=='POST']
    assert (x.root/worker.PHASES[0]/'provider/sources/schedule-2026-7.json').is_file()
    assert not (x.root/worker.PHASES[0]/'RESULT.json').exists()


@pytest.mark.parametrize('damage',['body_sha','status','clock'])
def test_provider_receipt_hash_status_and_clock_cannot_create_checkpoint(pipeline,damage):
    x=pipeline
    def changed(cache,name,url,**kwargs):
        value,receipt=x.fetch(cache,name,url,**kwargs)
        if damage=='body_sha':receipt['sha256']='0'*64
        elif damage=='status':receipt['status']='unavailable'
        else:receipt['retrieved_utc']=(x.service.now+timedelta(seconds=1)).isoformat()
        return value,receipt
    with pytest.raises((worker.GradeBridgeError,StorageIntegrityError)):
        worker.execute(x.context(worker.PHASES[0]),fetch=changed,clock=lambda:x.service.now)
    assert not [r for r in x.service.calls if r.method=='POST']
    assert not (x.root/worker.PHASES[0]/'checkpoint/HANDOFF.json').exists()


@pytest.mark.parametrize('damage',['failed','partial','root','run','job','durability','export'])
def test_actual_archive_gate_rejects_failed_partial_or_wrong_current_scope_before_rows(pipeline,monkeypatch,damage):
    x=pipeline;context=x.context(worker.PHASES[0]);client=worker._client(context,'append',None)
    client.authenticate_actions_job();context.client=client
    identity=cp.client_identity(client);jobs=dict(produce='fictional_producer',restore=checkpoint.JOBS['writer'],consume=checkpoint.JOBS['reader'])
    context.go['jobs']=jobs
    producer=dict(identity,job_id=jobs['produce'],api_job_id=777,process_identity='e'*64)
    payload=cp.payload(gzip.compress(b'FICTIONAL_UNREAD_INDEX',mtime=0))
    entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=payload,payload_asset_id=201,
        payload_name='blob-'+payload['sha256']+'.bin',producer_process=producer['process_identity'],
        binding_sha256=state.digest(client.binding),writer_run_id=RUN)
    descriptor=dict(entry=entry,manifest_asset_id=202,manifest_sha256=state.digest(entry),manifest_bytes=len(store.canonical(entry)))
    h=dict(schema_version=archive.VERSION+'-handoff',repository=store.REPO,source_sha=SOURCE,run_id=RUN,
        root_go_sha256=ROOT_SHA,producer=producer,runtime_binding=client.binding,index_descriptor=descriptor,
        files_sha256='f'*64,archive_state='COMPLETE_CAPTURE',jobs=jobs)
    archive.safe_handoff(h)
    value=dict(schema_version=archive.VERSION+'-restored',state='PRIVATE_CAPTURE_RESTORED',archive=h,current=identity,
        captured_bundle_hashes_restored=True,replay_ready=True,scope_qualified_for_publication=False,
        public_export_authorized=False,successful_forecast=False)
    if damage=='failed':value['state']='PRIVATE_FAILURE_ARCHIVE_RESTORED'
    elif damage=='partial':h['archive_state']='FAILURE_EVIDENCE'
    elif damage=='root':h['root_go_sha256']='0'*64
    elif damage=='run':value['current']=dict(identity,run_id='49900000001')
    elif damage=='job':value['current']=dict(identity,job_id=jobs['produce'])
    elif damage=='durability':value['captured_bundle_hashes_restored']=False
    else:value['public_export_authorized']=True
    ref=archive.write(x.q['storage'],x.root/'gate-input/RESTORED.json',value)
    context.request['inputs']['archive_restored']=ref
    actual_read=archive.read_owned
    def metadata_only(storage,binding,*args,**kwargs):
        assert binding==ref,'failed/partial current metadata must reject before any row/index read'
        return actual_read(storage,binding,*args,**kwargs)
    monkeypatch.setattr(archive,'read_owned',metadata_only)
    with pytest.raises(worker.GradeBridgeError,match='ACTUAL_COMPLETE_CURRENT_JOB_ARCHIVE_RESTORATION'):
        ACTUAL_ARCHIVE(context,x.q['storage'],lambda:x.service.now)
    assert not [r for r in x.service.calls if r.method=='POST']


def test_append_failure_original_intent_retained_never_retried(pipeline):
    x=pipeline;x.service.server.ambiguous=True
    with pytest.raises(store.StoreError):worker.execute(x.context(worker.PHASES[0]),fetch=x.fetch,clock=lambda:x.service.now)
    assert len([r for r in x.service.calls if r.method=='POST'])==1
    assert (x.root/worker.PHASES[0]/'checkpoint/APPEND_INTENT.json').is_file()
    with pytest.raises(store.StoreError):worker.execute(x.context(worker.PHASES[0]),fetch=x.fetch,clock=lambda:x.service.now)
    assert len([r for r in x.service.calls if r.method=='POST'])==1


def test_contract_and_preparation_never_execute_or_print_private_error(capsys,monkeypatch):
    assert cli.main(['operations-grade-write'])==2
    assert json.loads(capsys.readouterr().out)['state']=='OPERATIONS_GRADE_PREPARATION_ONLY_NO_IO'
    assert cli.main(['contract'])==2
    value=json.loads(capsys.readouterr().out)
    assert value['previous_snapshot']=='NONE_ONLY_ROOT_V2_RESTORES_ARCHIVED_HISTORY'
    assert value['native_capacity_qualified'] is False


def test_unknown_library_errors_never_become_public_reason_codes(capsys,monkeypatch):
    from tools import private_draft_store_v2,audit_process_guard_v1
    from nfl_lab import audit_numerical_runtime_v1 as numerical
    monkeypatch.setattr(private_draft_store_v2,'limits',lambda:None)
    monkeypatch.setattr(audit_process_guard_v1,'arm_parent_death',lambda:None)
    monkeypatch.setattr(numerical,'preflight',lambda *_a,**_k:None)
    def fail(*_a,**_k):raise RuntimeError('FICTIONAL_PRIVATE_LIBRARY_TEXT')
    monkeypatch.setattr(worker,'run',fail)
    assert cli.main(['operations-grade-write','--execute'])==1
    output=capsys.readouterr().out
    assert 'FICTIONAL_PRIVATE_LIBRARY_TEXT' not in output
    status=json.loads(output)
    assert status['reason']=='OPERATIONS_GRADE_FAILED' and status['state']=='FAILED_LOCAL'
    assert status['metadata_remote_durability_qualified'] is False


def test_preflight_library_output_and_exception_are_sanitized(capsys,monkeypatch):
    from tools import private_draft_store_v2,audit_process_guard_v1
    from nfl_lab import audit_numerical_runtime_v1 as numerical
    monkeypatch.setattr(private_draft_store_v2,'limits',lambda:None)
    monkeypatch.setattr(audit_process_guard_v1,'arm_parent_death',lambda:None)
    def fail(*_a,**_k):
        print('FICTIONAL_PRIVATE_PREFLIGHT_OUTPUT')
        print('FICTIONAL_PRIVATE_PREFLIGHT_ERROR',file=sys.stderr)
        raise RuntimeError('FICTIONAL_PRIVATE_LIBRARY_TEXT')
    monkeypatch.setattr(numerical,'preflight',fail)
    assert cli.main(['operations-grade-read','--execute'])==1
    captured=capsys.readouterr()
    assert captured.err=='' and 'FICTIONAL_PRIVATE' not in captured.out
    assert json.loads(captured.out)['reason']=='OPERATIONS_GRADE_FAILED'


def test_exact_grade_callbacks_reject_wrong_schema_kind_hash_and_extra_authority():
    context=SimpleNamespace(verify=lambda:None)
    body=dict(fictional=True,unicode_metadata='fictional-\u00e9')
    auth=worker._exact(context,'POPULATION_BEFORE_VALUES',body,lambda:GRADE)
    valid=dict(schema_version=grade.VERSION+'-authentication-request',kind='POPULATION_BEFORE_VALUES',inputs_sha256=state.digest(body),at=GRADE.isoformat())
    assert auth(valid) is True
    for key,value in [('schema_version','saved-result'),('kind','another-kind'),('inputs_sha256','0'*64),('qualified',True)]:
        assert auth(dict(valid,**{key:value})) is False


def test_e7_and_checkpoint_callbacks_reject_saved_authority_before_private_read(tmp_path,monkeypatch):
    context=SimpleNamespace(verify=lambda:None)
    def private_read(*_a,**_k):pytest.fail('CALLBACK_PRIVATE_READ_BEFORE_LIVE_STAGE')
    monkeypatch.setattr(archive,'read_owned',private_read)
    e7=worker.E7Fetch(context,SimpleNamespace(cache=tmp_path/'cache'),dict(games=[],source_policy_sha256=cp.POLICY_SHA),lambda:GRADE)
    with pytest.raises(worker.GradeBridgeError,match='EXACT_ONE_ATTEMPT_REGISTERED_E7_REQUEST'):
        e7(tmp_path/'cache','statistics-2026-7','https://api.sleeper.app/stats/nfl/2026/7?season_type=regular',storage=e7.storage)
    assert e7.authenticate(dict(qualified=True)) is False
    auth=worker._checkpoint_auth(context,lambda:GRADE)
    for kind in ('QUALIFIED_PREVIOUS_GRADING_SNAPSHOT','FRESH_READER_GRADING_DURABILITY'):
        assert auth(dict(schema_version=grade.VERSION+'-authentication-request',kind=kind,inputs_sha256='a'*64,at=GRADE.isoformat())) is False


def test_e7_request_matches_full_owned_canonical_bytes_without_duplicate_decode(pipeline,monkeypatch):
    from nfl_lab import audit_weekly_provider_v1 as provider
    x=pipeline
    request_doc=dict(games=[],source_policy_sha256=cp.POLICY_SHA,unicode_metadata='fictional-\u00e9')
    path=x.root/'canonical-provider/REQUEST.json'
    x.q['storage'].write_bytes(path,state.canonical(request_doc))
    ref=cp.binding(path)
    e7=worker.E7Fetch(SimpleNamespace(verify=lambda:None),x.q['storage'],request_doc,lambda:x.service.now)
    monkeypatch.setattr(archive,'read_owned',lambda *_a,**_k:pytest.fail('DUPLICATE_PROVIDER_REQUEST_JSON_DECODE'))
    assert e7._request_matches(ref) is True
    assert e7._request_matches(dict(ref,bytes=ref['bytes']+1)) is False
    assert e7._request_matches(dict(ref,sha256='0'*64)) is False
    inputs=dict(request=ref,source_policy_sha256=cp.POLICY_SHA,limits=provider.LIMITS)
    assert e7.authenticate(dict(schema_version=provider.VERSION+'-authentication-request',kind='AUTHORIZE_REGISTERED_REQUEST',
        inputs=inputs,inputs_sha256=state.digest(inputs),at=x.service.now.isoformat())) is True


def test_epoch_preserves_original_registration_and_exact_archived_choice(pipeline):
    x=pipeline;q=x.q;restored=deepcopy(x.restored)
    docs=dict(epoch=q['r'].epoch.document,epoch_registration=q['r'].completion,original_choice=q['f']['raw'],
        origin_witness=q['f']['completion'],original_slate=q['f']['slate'],original_catalog=q['f']['catalog'],original_policy=q['f']['policy'])
    for role,document in docs.items():
        path=x.root/'epoch-auth'/('context-'+role+'.json')
        q['storage'].write_bytes(path,document if type(document) is bytes else store.canonical(document))
        restored['aliases']['context/'+role+'.json']=cp.binding(path)
    restored['aliases']['prepared/choice.json']=restored['aliases']['runtime/WEEKLY_CHOICE.json']
    restored['archive']=dict(root_go_sha256=ROOT_SHA)
    registered,choice=ACTUAL_EPOCH(restored,q['storage'],lambda:x.service.now)
    assert registered.epoch.sha256==q['r'].epoch.sha256 and choice.sha256==q['c'].sha256
    assert registered.completion==q['r'].completion
    assert registered.completion['owner_registration_sha256']!=ROOT_SHA
    restored['aliases']['prepared/choice.json']=dict(restored['aliases']['prepared/choice.json'],sha256='0'*64)
    with pytest.raises(worker.GradeBridgeError,match='EXACT_ARCHIVED_FULL_CHOICE'):
        ACTUAL_EPOCH(restored,q['storage'],lambda:x.service.now)


def test_fresh_grading_history_must_match_the_current_archive(pipeline):
    x=pipeline;q=x.q;capture=deepcopy(q['capture'].document)
    capture['aliases']=deepcopy(x.restored['aliases'])
    durable=SimpleNamespace(document=dict(captures=[capture]))
    worker._same_capture(x.restored,q['r'],q['c'],durable,q['storage'])
    capture['archive_index_sha256']='0'*64
    with pytest.raises(worker.GradeBridgeError,match='EXACT_GRADED_AND_FRESH_RESTORED_CAPTURE'):
        worker._same_capture(x.restored,q['r'],q['c'],durable,q['storage'])


@pytest.fixture(scope='module')
def native_archive_graph(tmp_path_factory):
    """Actual native archive codec, store, API and owned files; fictional HTTP."""
    import test_audit_weekly_archive_v1 as original
    root=tmp_path_factory.mktemp('ops-grade-native-archive')
    p=original.capture.__wrapped__(root)
    # Use the parent's complete operational context contract without changing
    # its collector, census, semantic validators or native transport.
    for role in sorted(archive.OPERATIONS_CONTEXT):
        p.context[role]=p.put('context/'+role+'.json',dict(fictional=True))
    service=original.Service(root)
    handoff,_,_=original.produce(p,service)
    service.active='restore'
    reader=service.factory(root/'archive-reader-journal','restore')
    writer_restored=archive.restore(handoff,reader,service.package,storage=p.storage,output=root/'archive-reader',
        root_go_sha256=ROOT_SHA,pending_census=service.census)
    reader_handoff=archive.read_owned(p.storage,cp.binding(root/'archive-reader/READER_HANDOFF.json'))
    contexts={}
    def context(phase,role,restored,directory):
        journal=root/('grade-'+role+'-journal');journal.mkdir(mode=0o700)
        client=archive.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=service.transport,
            job=dict(reader.clients[0].job,job_id=original.ROLES[role],api_job_id=0,run_authenticated=False),
            operation='metadata',qualification=service.q,readonly=True,process=store.sha(('FICTIONAL-grade-'+role).encode()))
        client.bind(service.binding);client.authenticate_actions_job()
        request_doc=request(root,phase);request_doc['inputs']['archive_restored']=cp.binding(directory/'RESTORED.json')
        return SimpleNamespace(request=request_doc,root_sha256=ROOT_SHA,client=client,verify=lambda:None,
            go=dict(jobs=original.ROLES,qualified_runtime=service.package,pending_census=service.census))
    contexts['write']=context(worker.PHASES[0],'restore',writer_restored,root/'archive-reader')
    checked_write=ACTUAL_ARCHIVE(contexts['write'],p.storage,state.now_utc)[0]
    assert checked_write==writer_restored
    service.reader_completed=datetime.now(timezone.utc);service.active='consume'
    exporter=service.factory(root/'archive-exporter-journal','consume')
    read_restored=archive.consume(reader_handoff,exporter,service.package,storage=p.storage,output=root/'archive-exporter',
        root_go_sha256=ROOT_SHA,pending_census=service.census)
    contexts['read']=context(worker.PHASES[1],'consume',read_restored,root/'archive-exporter')
    return SimpleNamespace(p=p,service=service,context=contexts['read'],restored=read_restored,checked_write=checked_write)


def test_actual_native_archive_writer_and_exporter_evidence_are_accepted(native_archive_graph):
    x=native_archive_graph
    restored,index=ACTUAL_ARCHIVE(x.context,x.p.storage,state.now_utc)
    assert x.checked_write['state']=='PRIVATE_CAPTURE_RESTORED'
    assert restored==x.restored and index['files_sha256']==restored['files_sha256']
    assert len(restored['restore_proofs'])==2+len(index['groups'])
    assert restored['current']['process_identity']!=x.context.client.process


@pytest.mark.parametrize('damage',['witness_body','descriptor_process','original_cohort','original_proof_hash','exporter_cohort'])
def test_archive_native_descriptor_witness_and_cohort_tampering_reject(native_archive_graph,damage):
    x=native_archive_graph;value=deepcopy(x.restored)
    if damage=='witness_body':value['restorer_witness']['actual_completed_at']=(state.utc(value['restorer_witness']['actual_completed_at'])-timedelta(seconds=1)).isoformat()
    elif damage=='descriptor_process':
        d=value['witness_descriptor'];d['entry']['producer_process']='0'*64
        d['manifest_sha256']=state.digest(d['entry']);d['manifest_bytes']=len(store.canonical(d['entry']))
    elif damage=='original_cohort':value['restorer_witness']['proofs'][0]['process_identity']='0'*64
    elif damage=='original_proof_hash':value['restorer_witness']['proofs'][0]['payload_sha256']='0'*64
    else:value['restore_proofs'][-1]['process_identity']='0'*64;value['exporter_proofs']=deepcopy(value['restore_proofs'])
    directory=x.p.base/('tampered-'+damage)
    for name in ('index.gz','reader-witness.gz'):
        x.p.storage.import_file(x.p.base/'archive-exporter/owned-downloads'/name,directory/'owned-downloads'/name)
    ref=archive.write(x.p.storage,directory/'RESTORED.json',value)
    context=SimpleNamespace(**vars(x.context));context.request=deepcopy(x.context.request)
    context.request['inputs']['archive_restored']=ref
    with pytest.raises((worker.GradeBridgeError,store.StoreError,StorageIntegrityError)):
        ACTUAL_ARCHIVE(context,x.p.storage,state.now_utc)


def test_direct_execute_cannot_enable_previous_snapshot_or_unclosed_read_handoff(pipeline,monkeypatch):
    x=pipeline
    monkeypatch.setattr(worker,'_archive',lambda *_:pytest.fail('PRIVATE_READ_BEFORE_CLOSED_REQUEST'))
    context=x.context(worker.PHASES[0]);context.request['inputs']['previous_snapshot']={'qualified':True}
    with pytest.raises(worker.GradeBridgeError,match='LIVE_CROSS_RUN_HISTORY_RESTORE_REQUIRED'):
        worker.execute(context)
    with pytest.raises(checkpoint.CheckpointError,match='CLOSED_EXACT_GRADING_CHECKPOINT_HANDOFF'):
        worker.execute(x.context(worker.PHASES[1],{'qualified':True}))
    assert not x.service.calls


def test_cold_provider_grade_write_and_fresh_read_each_under_actual_512MiB(pipeline,tmp_path):
    """Run real collection/grading/codec/private transport in TWO cold workers.

    All capture bytes and current-job authority are FICTIONAL fixture inputs;
    this does not claim a genuine hosted archive or a new durability proof.
    Numerical/Arrow fixture construction happens outside the capped children.
    Inside, reconstruct typed epoch metadata through its real validator and
    execute the full provider/bind/grade/checkpoint write/read code paths.
    """
    x=pipeline;q=x.q;f=q['f']
    seed=dict(root=str(x.root),work=str(tmp_path/'cold-transport'),cache=str(q['storage'].cache),state_root=str(q['storage'].state_root),
        restored=x.restored,restored_ref=x.context(worker.PHASES[0]).request['inputs']['archive_restored'],
        epoch=q['r'].epoch.document,completion=q['r'].completion,original_choice=f['raw'].decode(),original_completion=f['completion'],
        slate=f['slate'],catalog=f['catalog'],policy=f['policy'],history_binding=f['history_binding'],choice=q['c'].document,
        replay=f['replay'],schedule=q['schedule'],query=q['query'])
    seed_path=tmp_path/'fictional-cold-inputs.json';seed_path.write_bytes(store.canonical(seed))
    script=r'''
import ast,base64,json,socket,sys,resource,signal
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path.cwd()/"tests"))
from tools.private_draft_store_v2 import limits
limits()
from nfl_lab import audit_weekly_operations_grade_v1 as worker,audit_weekly_grade_v1 as grade
from nfl_lab import audit_weekly_grade_checkpoint_v1 as checkpoint,audit_weekly_epoch_v1 as epoch
from nfl_lab import audit_weekly_archive_v1 as archive,private_draft_store as store,state,audit_private_rotation_v1 as rotation
from nfl_lab.operational_storage import OperationalStorage
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError("REAL_NETWORK_FORBIDDEN"))
ROOT=Path.cwd();ROOT_SHA="d"*64;GRADE=state.utc("2026-10-28T08:00:00Z")
seed=json.loads(Path(sys.argv[1]).read_bytes());phase=sys.argv[2]
storage=OperationalStorage(seed["cache"],ROOT/"config/operational-source-policy-v2.json",state=seed["state_root"])
e=epoch.restore_epoch(seed["epoch"],seed["original_choice"].encode(),seed["original_completion"],seed["slate"],seed["catalog"],seed["policy"],history_binding=seed["history_binding"],now=GRADE)
registered=epoch.bind_registration(e,seed["completion"],now=GRADE)
choice=epoch.EpochChoice(seed["choice"],state.digest(seed["choice"]));choice.verify(registered,GRADE)
root=Path(seed["root"]);tmp_path=Path(seed["work"]);tmp_path.mkdir(exist_ok=True)
restored=seed["restored"];restored_ref=seed["restored_ref"]
q=dict(storage=storage,r=registered,c=choice,f=dict(replay=seed["replay"]),schedule=seed["schedule"],query=seed["query"])
# Reuse the exact fictional HTTP service definitions, avoiding imports of the
# unrelated ML fixture builders. No production validator or cap is replaced.
ns=globals();s=store;k=checkpoint;a=archive
ROLES=dict(produce="fictional_capture_writer",restore="fictional_capture_reader",consume="fictional_capture_exporter")
for filename in ("test_audit_weekly_archive_v1.py","test_audit_weekly_grade_checkpoint_v1.py"):
    tree=ast.parse((ROOT/"tests"/filename).read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="Service"]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),filename,"exec"),ns)
    if filename=="test_audit_weekly_archive_v1.py":ArchiveService=Service
transport_file=tmp_path/"server.json"
if phase=="write":
    service=Service(tmp_path)
else:
    raw=json.loads(transport_file.read_bytes())
    service=Service.__new__(Service);service.server=Server();service.server.tag=raw["tag"]
    service.server.assets=[dict(v,body=base64.b64decode(v["body"])) for v in raw["assets"]]
    for name in ("binding","qrun","q","package","census"):setattr(service,name,raw[name])
    service.calls=[];service.active="consume";service.bad_writer=service.bad_qualifier=service.bad_source=service.same_api_id=False
    service.run_attempt=1;service.writer_done=raw["writer_done"];service.started=state.utc(raw["started"])
    service.writer_completed=None;service.reader_completed=None;service.now=state.utc(raw["now"])
class Clock(datetime):
    @classmethod
    def now(cls,tz=None):return service.now if tz else service.now.replace(tzinfo=None)
store.datetime=Clock
counters=[0 if phase=="write" else 100];clients=[];fetch_calls=[]
tree=ast.parse((ROOT/"tests/test_audit_weekly_operations_grade_v1.py").read_text())
pipeline_node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="pipeline")
selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="request"]
selected += [n for n in pipeline_node.body if isinstance(n,ast.FunctionDef) and n.name in {"client","context","fetch"}]
exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),"fictional-cold-seams","exec"),ns)
# Only the independent current-job/archive authority fixture is injected.
# The real native envelope runs on EVERY context check, and typed epoch/model
# metadata was validated above. No production CLI can select these seams.
worker.Authenticated.verify=lambda self:(worker.native_envelope() or self)
worker._client=client
worker._archive=lambda *_:(restored,{})
worker._epoch=lambda *_:(registered,choice)
worker._replay=lambda *_:seed["replay"]
if phase=="write":
    result=worker.execute(context(worker.PHASES[0]),fetch=fetch,clock=lambda:service.now)
    assert len(fetch_calls)==2
    service.writer_done=(service.now+timedelta(seconds=10)).isoformat();service.now+=timedelta(minutes=2)
    remote=dict(tag=service.server.tag,assets=[dict(v,body=base64.b64encode(v["body"]).decode()) for v in service.server.assets],
        **{n:getattr(service,n) for n in ("binding","qrun","q","package","census")},started=service.started.isoformat(),
        now=service.now.isoformat(),writer_done=service.writer_done,handoff=result["checkpoint_handoff"])
    transport_file.write_bytes(store.canonical(remote))
else:
    result=worker.execute(context(worker.PHASES[1],raw["handoff"]),clock=lambda:service.now)
    assert not fetch_calls
    assert all(r.method=="GET" for r in service.calls)
assert result["public_release"] is result["successful_forecast"] is False
assert all(c.calls<=40 for c in clients)
worker.native_envelope();checkpoint.native_envelope()
assert "sklearn" not in sys.modules and "catboost" not in sys.modules
memory={}
for line in Path("/proc/self/status").read_text().splitlines():
    key,_,value=line.partition(":")
    if key in {"VmSize","VmPeak","VmRSS","VmHWM"}:memory[key]=int(value.split()[0])*1024
print(json.dumps(dict(fictional=True,phase=phase,state=result["state"],AS_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],**memory)))
'''
    profile=json.loads((ROOT/'config/audit-weekly-numerical-runtime-v1.json').read_bytes())['environment']
    env=dict(PYTHONDONTWRITEBYTECODE='1',**profile)
    # Different owned outputs from the earlier in-process test fixture.
    for phase in ('write','read'):
        result=subprocess.run([sys.executable,'-B','-c',script,str(seed_path),phase],cwd=ROOT,env=env,capture_output=True,text=True,timeout=185)
        print(result.stdout,end='',flush=True)
        if result.returncode:print(result.stderr,end='',file=sys.stderr,flush=True)
        assert result.returncode==0,(phase,result.stderr)
        report=json.loads(result.stdout.splitlines()[-1])
        assert report['AS_bytes']==512 << 20 and report['VmPeak']<=512 << 20
