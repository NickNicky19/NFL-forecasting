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
def original_seed(tmp_path_factory,*,workflow=None,policy_sha256=None):
    import test_audit_weekly_operations_grade_v1 as bridge
    from nfl_lab import audit_weekly_operations_grade_v1 as worker,audit_weekly_grade_v1 as grade
    from nfl_lab import audit_weekly_archive_v1 as archive,private_draft_store as store,state,gha_private_checkpoint as cp
    from nfl_lab import audit_weekly_operations_v1 as operations
    root=tmp_path_factory.mktemp('original-history')
    with pytest.MonkeyPatch.context() as patch:
        x=bridge.pipeline.__wrapped__(root,patch);q=x.q
        # Seal complete fictional owner census metadata before the first
        # grading append. A later namespace transition cannot invent it.
        x.service.census=dict(schema_version='audit-private-rotation-v1-pending-census',complete=True,
            as_of_utc=x.service.q['before_proof']['started_at_utc'],owner_evidence_sha256='a'*64,reservations=[])
        x.service.package['quota_reservation'].update(pending_records=0,
            pending_census_sha256=store.sha(store.canonical(x.service.census)))
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
        workflow=workflow or ('concurrency:\n  group: nfl-lab-single-writer\n  cancel-in-progress: false\n'
            'permissions:\n  contents: write\n  actions: read\njobs:\n'+''.join('  '+j+':\n    runs-on: ubuntu-latest\n' for j in JOBS.values())).encode()
        receipt=dict(schema_version='audit-weekly-delivery-v1-public-receipt',source_sha=bridge.SOURCE,run_id=bridge.RUN,
            root_go_sha256=bridge.ROOT_SHA,policy_sha256=policy_sha256 or '1'*64,policy_registered_at_utc=q['pop']['registered_at'],
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

def recovery_case(root,seed,patch,*,native=False,role='produce',current_run=NEW_RUN):
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
                anchor='locator' in seed and rid==seed['receipt']['run_id'] and rid!=seed['old_run']
                old=rid==seed['old_run'] or anchor
                if anchor and damage.get('anchor_deleted'):return Response(b'{"message":"Not Found"}',404)
                if '/jobs?' not in url:return Response(dict(id=int(rid),head_sha='0'*40 if anchor and damage.get('anchor_source') else seed['source'],
                    run_attempt=2 if anchor and damage.get('anchor_attempt') else 1,event='workflow_dispatch',
                    path='.github/workflows/lab.yml',head_branch='fictional',status='completed' if old else 'in_progress',
                    conclusion=('failure' if damage.get('run') or anchor and damage.get('anchor_failed') else 'success') if old else None,repository=dict(full_name=store.REPO),
                    head_repository=dict(full_name=store.REPO),actor=dict(login='OTHER' if anchor and damage.get('anchor_actor') else 'NickNicky19',id=208912933)))
                if old:
                    h=seed['sidecar']['checkpoint_handoff']
                    times=[(state.utc(h['snapshot_completed_at'])-timedelta(hours=2),state.utc(h['snapshot_completed_at'])-timedelta(hours=1)),
                        (state.utc(h['snapshot_completed_at'])-timedelta(minutes=2),state.utc(seed['writer_done'])),
                        (state.utc(seed['writer_done'])+timedelta(seconds=50),state.utc(seed['old_complete']))]
                    if 'job_times' in seed:times=[(state.utc(a),state.utc(b)) for a,b in seed['job_times']]
                    refs=(seed.get('locator') or {}).get('cohort',seed['receipt'])['jobs']
                    if anchor:
                        times=[(state.utc(a),state.utc(b)) for a,b in seed['anchor_job_times']]
                        refs=seed['receipt']['jobs']
                    jobs=[dict(id=refs[r]['api_job_id'],name=name,run_id=int(rid),head_sha=seed['source'],status='completed',
                        conclusion='failure' if (damage.get('job') or anchor and damage.get('anchor_job')) and i==1 else 'success',started_at=a.isoformat(),completed_at=b.isoformat())
                        for i,((r,name),(a,b)) in enumerate(zip(JOBS.items(),times))]
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
    client=store.Client('ghs_FICTIONAL',current_run,journal=journal,source_sha=seed['source'],transport=api,
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


@pytest.fixture
def locator_seed(tmp_path,original_seed,monkeypatch,*,source_transition=False,historical_pending=False,root_static=None):
    """Real grade/CAS/append/read, fictional authority/API and no new labels.

    The prior fixture is an input to this codec test, not an old-source
    migration or a genuine hosted Root. All original snapshots and receipts
    remain in the in-memory release. The new grading run has its own identity.
    """
    from nfl_lab import audit_weekly_grade_v1 as grade,audit_weekly_grade_checkpoint_v1 as checkpoint
    from nfl_lab import audit_weekly_archive_v1 as archive,audit_weekly_template_v1 as template
    from nfl_lab import private_draft_store as store,state,gha_private_checkpoint as cp
    from test_private_draft_store_v2 import Response
    x=recovery_case(tmp_path/'writer',original_seed,monkeypatch)
    previous=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    began=state.utc(original_seed['current_at']);actual=[began+timedelta(seconds=30)];done=[None]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return actual[0] if tz else actual[0].replace(tzinfo=None)
    monkeypatch.setattr(store,'datetime',Clock);monkeypatch.setattr(history,'now',lambda:actual[0])
    x.api.allow_append=True
    def api(request,timeout):
        if '/actions/runs/'+NEW_RUN in request.full_url:
            if '/jobs?' not in request.full_url:
                return Response(dict(id=int(NEW_RUN),head_sha=original_seed['source'],run_attempt=1,event='workflow_dispatch',
                    path='.github/workflows/lab.yml',head_branch='fictional',status='in_progress',conclusion=None,
                    repository=dict(full_name=store.REPO),head_repository=dict(full_name=store.REPO),actor=dict(login='NickNicky19',id=208912933)))
            jobs=[dict(id=888,name=JOBS['produce'],run_id=int(NEW_RUN),head_sha=original_seed['source'],status='completed',conclusion='success',
                started_at=(began+timedelta(seconds=1)).isoformat(),completed_at=(began+timedelta(seconds=5)).isoformat()),
                dict(id=889,name=JOBS['restore'],run_id=int(NEW_RUN),head_sha=original_seed['source'],status='completed' if done[0] else 'in_progress',
                    conclusion='success' if done[0] else None,started_at=(began+timedelta(seconds=10)).isoformat(),completed_at=done[0])]
            if done[0]:jobs.append(dict(id=890,name=JOBS['consume'],run_id=int(NEW_RUN),head_sha=original_seed['source'],status='in_progress',conclusion=None,
                started_at=(began+timedelta(seconds=70)).isoformat(),completed_at=None))
            return Response(dict(total_count=len(jobs),jobs=jobs))
        return x.api(request,timeout)
    captures=grade.retained_captures(previous.durable,previous.registered,at=actual[0])
    # Missing finality/observations remains missing. Prior originals, versions,
    # negative results, known-by clocks and assignments are retained by grade().
    batch=grade.bind_observations(captures,dict(schema_version=grade.VERSION+'-provider-observations',source_policy_sha256=cp.POLICY_SHA,
        captured_at=actual[0].isoformat(),observations=[],finality=[]),authenticate=lambda _:True,at=actual[0])
    snapshot=grade.grade(previous.registered,captures,[batch],storage=x.storage,output=tmp_path/'writer/regrade',previous=previous.durable,clock=lambda:actual[0])
    schedule=[{k:dict(r,game_type='REG')[k] for k in ('season','week','game_type','game_id','kickoff_utc')} for r in original_seed['schedule']]
    current=dict(season=2026,week=7,schedule=schedule,game_cutoffs=original_seed['choice']['slate']['game_cutoffs'],
        canonical_choice_sha256=state.digest(original_seed['choice']))
    seed=dict(schema_version=history.LOCATOR_VERSION+'-planning',epoch_sha256=previous.registered.epoch.sha256,current=current,next=None,
        resolved_weeks=[],known_by_at=(began+timedelta(seconds=3)).isoformat(),calendar=dict(url='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
            sha256=store.sha(b'FICTIONAL_CALENDAR_ONLY'),bytes=23,retrieved_utc=(began+timedelta(seconds=3)).isoformat()))
    pins={p:store.sha((ROOT/p).read_bytes()) for p in set(history.FILES)|history._GRADE_PIN_PATHS|history._CHECKPOINT_PIN_PATHS|history.LOCATOR_HELPERS}
    pins['.github/workflows/lab.yml']=original_seed['receipt']['workflow_sha256']
    root={p:None for p in template.ROOT_KEYS}
    anchor=dict(feed_sha256=original_seed['receipt']['feed_sha256'],receipt_sha256=x.receipt['sha256'])
    root.update(schema_version='audit-weekly-hosted-v2-root-GO',approved=True,operation='RECURRING_CAPTURE',source_sha=original_seed['source'],code_pins=pins,jobs=JOBS,
        qualified_runtime=original_seed['package'],pending_census=original_seed['census'],issued_at_utc=began.isoformat(),expires_at_utc=(began+timedelta(hours=1)).isoformat(),
        effective_epoch=dict(schema_version=history.CONTEXT_V4,controller_context=None,previous_capture=anchor,
            previous_checkpoint=dict(schema_version=history.LOCATOR_REF,path='20261028T080300.000000Z--40000000001--'+'a'*64+'.json.gz',sha256='b'*64),
            plan=dict(kind='GRADE_ONLY',season=2026,week=7,deadline_utc=None,calendar_sha256=state.digest(schedule),game_cutoffs={})))
    if source_transition:
        # A fictional V3 capture Root with two already-qualified namespaces.
        # No allocation, training, original asset rewrite or real NFL input.
        from nfl_lab import audit_weekly_hosted_v1 as hosted
        from test_audit_weekly_controller_bootstrap_v1 import fictional_runtime_metadata
        pins.update({p:store.sha((ROOT/p).read_bytes()) for p in hosted.PINS})
        pins['.github/workflows/lab.yml']=original_seed['receipt']['workflow_sha256']
        prior=fictional_runtime_metadata(original_seed['package'],original_seed['census'])
        root.update(schema_version=template.ROOT_V3,prior_capture_qualified_runtime=dict(
            schema_version=template.PRIOR_RUNTIME,purpose='PRIOR_CAPTURE_QUALIFIED_RUNTIME',
            anchor=deepcopy(anchor),qualified_runtime=prior,pending_census=deepcopy(original_seed['census']),root_static_sha256='a'*64),
            publication_registration=dict(policy_gzip_base64='FICTIONAL_OLD_POLICY',policy_sha256=original_seed['receipt']['policy_sha256'],
                rights_authority={'original':'rights'},r0={'original':'R0'}))
        for p in ('nfl_lab/audit_weekly_grade_history_v1.py','nfl_lab/audit_weekly_template_v1.py'):
            pins[p]=store.sha((ROOT/p).read_bytes()+b'\n# FICTIONAL original orchestration\n')
        # A future-only fictional calendar is metadata, never reconstructed NFL
        # availability. All retained negative grades/clocks remain untouched.
        schedule=[dict(r,kickoff_utc=(began+timedelta(days=2,minutes=i)).isoformat()) for i,r in enumerate(schedule)]
        cuts={r['game_id']:(state.utc(r['kickoff_utc'])-timedelta(minutes=15)).isoformat() for r in schedule}
        seed['current'].update(schedule=schedule,game_cutoffs=cuts)
        root['effective_epoch'].update(schema_version=history.CONTEXT_V5,
            pending_post_recovery=dict(schema_version=template.PENDING_RECOVERY,handoffs=[],pending_reservations=[]),
            plan=dict(kind='FUTURE_CAPABLE',season=2026,week=7,deadline_utc=min(cuts.values()),calendar_sha256=state.digest(schedule),game_cutoffs=cuts))
        if historical_pending:
            root['owner_authorization']='FICTIONAL_OWNER_caf\u00e9'
            descriptor=deepcopy(original_seed['sidecar']['evidence_descriptor']);entry=descriptor['entry']
            records=[]
            for name,size,sha in ((entry['payload_name'],entry['payload']['bytes'],entry['payload']['sha256']),
                    ('manifest-'+descriptor['manifest_sha256']+'.json',descriptor['manifest_bytes'],descriptor['manifest_sha256'])):
                records.append(dict(schema_version='weekly-private-POST-reservation-v2',key='asset:'+name,name=name,bytes=size,sha256=sha))
            pool=dict(schema_version=template.PENDING_RECOVERY,handoffs=[dict(schema_version='audit-weekly-hosted-v2-failure-handoff',
                binding=deepcopy(original_seed['package']['binding']),descriptor=descriptor,root_go_sha256='7'*64)],
                pending_reservations=sorted(records,key=lambda r:r['key']))
            raw_pool=store.canonical(pool)
            root['effective_epoch']['pending_post_recovery']=dict(schema_version=template.PENDING_RECOVERY_ENVELOPE,
                body_sha256=store.sha(raw_pool),body_bytes=len(raw_pool),gzip_base64=base64.b64encode(gzip.compress(raw_pool,mtime=0)).decode())
    if root_static is not None:
        assert not set(root_static)&(template.DYNAMIC_FIELDS|{'schema_version','code_pins','source_sha','qualified_runtime','pending_census','prior_capture_qualified_runtime'})
        root.update(deepcopy(root_static))
    def client(role,operation):
        journal=tmp_path/('journal-'+role+'-'+operation);x.storage.register_root(journal)
        c=archive.Client('ghs_FICTIONAL',NEW_RUN,journal=journal,source_sha=original_seed['source'],operation=operation,transport=api,readonly=operation=='restore',
            process=store.sha((role+operation).encode()),qualification=original_seed['package']['qualification'],job=dict(execution_lane='github_actions',workflow_ref=original_seed['sidecar']['workflow_ref'],
                workflow_sha=original_seed['source'],job_id=JOBS[role],permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False))
        c.bind(original_seed['package']['binding']);return c
    root_sha=store.sha(store.canonical(root));writer=client('restore','append')
    handoff=checkpoint.append(snapshot,writer,original_seed['package'],storage=x.storage,output=tmp_path/'writer/checkpoint-write',
        current_root_go_sha256=root_sha,authenticate=lambda _:True,pending_census=original_seed['census'],clock=lambda:actual[0])
    done[0]=(began+timedelta(seconds=50)).isoformat();actual[0]=began+timedelta(seconds=90)
    reader=client('consume','restore')
    result=checkpoint.restore(handoff,reader,original_seed['package'],previous.registered,storage=x.storage,output=tmp_path/'writer/checkpoint-read',
        current_root_go_sha256=root_sha,authenticate=lambda _:True,pending_census=original_seed['census'],clock=lambda:actual[0])
    native=cp.binding(tmp_path/'writer/checkpoint-read/FRESH_READER_NATIVE_PROOF.json')
    ref=history.prepare_envelope(result,handoff,native,storage=x.storage,output=tmp_path/'writer/envelope',planning=seed,root_go=root)
    envelope=history.metadata_document(archive.read_owned(x.storage,ref,history.LIMITS['envelope_bytes'],raw=True),cap=history.LIMITS['envelope_bytes'])
    appender=client('consume','append');appender.authenticate_actions_job()
    encoded=archive.read_owned(x.storage,ref,history.LIMITS['envelope_bytes'],raw=True)
    descriptor=store.append(appender,encoded,cp.payload(encoded),original_seed['package']['qualification'])
    completed=began+timedelta(seconds=120)
    cohort=dict(schema_version=history.LOCATOR_VERSION+'-cohort',kind='CAPTURE_AND_GRADE' if source_transition else 'GRADING_ONLY',repository=store.REPO,source_sha=original_seed['source'],run_id=NEW_RUN,
        root_go_sha256=root_sha,workflow_sha256=pins['.github/workflows/lab.yml'],epoch_sha256=previous.registered.epoch.sha256,feed_sha256=anchor['feed_sha256'],
        jobs={r:dict(job_id=JOBS[r],api_job_id=888+i) for i,r in enumerate(JOBS)},root_issued_at_utc=began.isoformat(),verified_at=result.proof['known_by_at'],
        created_at=(began+timedelta(seconds=100)).isoformat(),fits=0,public_release=False,successful_forecast=False)
    receipt=deepcopy(original_seed['receipt'])
    if source_transition:
        receipt.update(**{k:cohort[k] for k in ('source_sha','run_id','root_go_sha256','workflow_sha256','epoch_sha256','jobs','verified_at','created_at')})
        receipt['policy_registered_at_utc']=began.isoformat()
        anchor=dict(feed_sha256=receipt['feed_sha256'],receipt_sha256=store.sha(gzip.compress(store.canonical(receipt),mtime=0)))
    locator=history.locator_document(anchor,cohort,handoff,result.proof,descriptor,cp.client_identity(appender),envelope['planning'],code_pins=pins)
    modified=deepcopy(original_seed)
    modified.update(sidecar=locator['sidecar'],locator=locator,original_root=root,receipt=receipt,old_run=NEW_RUN,old_complete=completed.isoformat(),writer_done=done[0],
        current_at=(completed+timedelta(days=1)).isoformat(),durable_sha256=grade._digest(result.durable.document),
        assets=[dict(a,body=base64.b64encode(a['body']).decode()) for a in x.server.assets])
    modified['job_times']=[((began+timedelta(seconds=a)).isoformat(),(began+timedelta(seconds=b)).isoformat()) for a,b in ((1,5),(10,50),(70,120))]
    original=original_seed['sidecar']['checkpoint_handoff']
    modified['anchor_job_times']=[(a.isoformat(),b.isoformat()) for a,b in (
        (state.utc(original['snapshot_completed_at'])-timedelta(hours=2),state.utc(original['snapshot_completed_at'])-timedelta(hours=1)),
        (state.utc(original['snapshot_completed_at'])-timedelta(minutes=2),state.utc(original_seed['writer_done'])),
        (state.utc(original_seed['writer_done'])+timedelta(seconds=50),state.utc(original_seed['old_complete'])))]
    modified['sources'].update({p:base64.b64encode((ROOT/p).read_bytes()).decode() for p in history.LOCATOR_HELPERS})
    if source_transition:
        for p in ('nfl_lab/audit_weekly_grade_history_v1.py','nfl_lab/audit_weekly_template_v1.py'):
            modified['sources'][p]=base64.b64encode((ROOT/p).read_bytes()+b'\n# FICTIONAL original orchestration\n').decode()
    assert result.durable.document['known_versions']==previous.durable.document['known_versions']
    assert result.durable.document['captures']==previous.durable.document['captures']
    return modified


def locator_recovery_case(root,locator_seed,monkeypatch):
    from nfl_lab import private_draft_store as store,state,gha_private_checkpoint as cp
    x=recovery_case(root,locator_seed,monkeypatch,current_run='45000000003')
    raw=gzip.compress(store.canonical(locator_seed['locator']),mtime=0)
    path=Path(root)/'locator.json.gz';x.storage.write_bytes(path,raw);x.sidecar=cp.binding(path)
    go=deepcopy(locator_seed['original_root']);go['issued_at_utc']=locator_seed['current_at']
    go['expires_at_utc']=(state.utc(go['issued_at_utc'])+timedelta(hours=1)).isoformat()
    go['effective_epoch']['previous_checkpoint']=dict(schema_version=history.LOCATOR_REF,path=history.locator_filename(locator_seed['locator']),sha256=store.sha(raw))
    x.context.go=go
    return x


def test_grade_only_locator_recovers_actual_new_checkpoint_with_original_anchor_and_full_history(tmp_path,locator_seed,monkeypatch,record_property):
    from nfl_lab import audit_weekly_grade_v1 as grade
    x=locator_recovery_case(tmp_path/'next-reader',locator_seed,monkeypatch)
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert grade._digest(result.durable.document)==locator_seed['durable_sha256']
    assert result.proof['planning']==locator_seed['locator']['planning']
    assert result.proof['current']['run_id']=='45000000003'
    assert result.proof['original_grade_read_proof']['reader']['run_id']==NEW_RUN
    assert result.durable.document['known_versions']==locator_seed['known_versions']
    assert all(r.method=='GET' for r in x.calls)
    first=next(i for i,r in enumerate(x.calls) if '/releases/' in r.full_url)
    anchor='/actions/runs/'+locator_seed['receipt']['run_id']
    assert {r.full_url for r in x.calls[:first] if anchor in r.full_url}=={
        'https://api.github.com/repos/NickNicky19/NFL-forecasting'+anchor,
        'https://api.github.com/repos/NickNicky19/NFL-forecasting'+anchor+'/jobs?per_page=100&page=1'}
    assert len([r for r in x.calls if anchor in r.full_url])>=4
    record_property('actual_fictional_GET_calls',len(x.calls))


@pytest.mark.parametrize('damage',['anchor_deleted','anchor_failed','anchor_attempt','anchor_source','anchor_actor','anchor_job'])
def test_child_independently_rejects_bad_forecast_anchor_before_first_private_GET(tmp_path,locator_seed,monkeypatch,damage):
    x=locator_recovery_case(tmp_path/'reject-anchor',locator_seed,monkeypatch);x.damage[damage]=True
    def transport(request,timeout):
        assert '/releases/' not in request.full_url,'FIRST_PRIVATE_GET_BEFORE_ORIGINAL_ANCHOR_AUTHENTICATION'
        return x.api(request,timeout)
    with pytest.raises(history.HistoryError):history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=transport)
    anchor='/actions/runs/'+locator_seed['receipt']['run_id']
    assert any(anchor in r.full_url for r in x.calls)
    assert not any('/releases/' in r.full_url for r in x.calls)


@pytest.fixture
def multipart_locator_seed(tmp_path,original_seed,monkeypatch):
    """Same-source current V2 dependency, real grade/parts/native byte codec."""
    from nfl_lab import audit_weekly_grade_v1 as grade
    actual_grade=grade.grade;actual_parts=grade._write_snapshot_v2
    def split(storage,output,document,*,part_bytes=None):
        size=sum(len(c) for c in grade._canonical_chunks(document))
        return actual_parts(storage,output,document,part_bytes=min(64 << 20,(size+1)//2))
    monkeypatch.setattr(grade,'_write_snapshot_v2',split)
    monkeypatch.setattr(grade,'grade',lambda *a,**kw:actual_grade(*a,**kw,wire_version=2))
    return locator_seed.__wrapped__(tmp_path,original_seed,monkeypatch)


def test_same_source_multipart_history_recovers_all_parts_and_original_known_clocks(tmp_path,multipart_locator_seed,monkeypatch,record_property):
    from nfl_lab import audit_weekly_grade_v1 as grade
    seed=multipart_locator_seed;x=locator_recovery_case(tmp_path/'parts-reader',seed,monkeypatch)
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert grade._digest(result.durable.document)==seed['durable_sha256']
    assert result.durable.document['known_versions']==seed['known_versions']
    assert result.proof['original_grade_read_proof']==seed['sidecar']['grade_read_proof']
    parts=result.proof['native_part_recovery']
    assert len(parts['parts'])==2 and parts['HTTP_calls']<=40
    assert all(p['reader']['run_id']=='45000000003' for p in parts['parts'])
    assert parts['completed_at_utc']<=result.proof['actual_recovered_at']
    assert all(r.method=='GET' for r in x.calls)
    record_property('recovery_total_GETs',len(x.calls));record_property('part_reader_HTTP_calls',parts['HTTP_calls'])


def test_multipart_historical_reader_rejects_foreign_source_before_private_GET(tmp_path,multipart_locator_seed,monkeypatch):
    x=locator_recovery_case(tmp_path/'foreign-source',multipart_locator_seed,monkeypatch)
    x.context.client.source_sha='0'*40
    with pytest.raises(history.HistoryError,match='SOURCE_VERSION_HISTORY_ADAPTER_REQUIRED'):
        history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert not any('/releases/' in r.full_url for r in x.calls)


def dual_locator_case(root, seed, monkeypatch):
    """Real original bytes in one binding; a sealed distinct write binding."""
    from test_audit_weekly_template_v1 import dual_runtime_root
    x=locator_recovery_case(root,seed,monkeypatch)
    x.context.go=dual_runtime_root(x.context.go,seed['package'],seed['census'],seed['locator']['anchor'],
        original_root=seed['original_root'])
    return x


def test_v3_prior_namespace_restores_every_multipart_row_without_relabeling(tmp_path,multipart_locator_seed,monkeypatch,record_property):
    from nfl_lab import audit_weekly_grade_v1 as grade,private_draft_store as store
    seed=multipart_locator_seed;x=dual_locator_case(tmp_path/'dual-reader',seed,monkeypatch)
    root_before=store.canonical(x.context.go)
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert grade._digest(result.durable.document)==seed['durable_sha256']
    assert result.durable.document['known_versions']==seed['known_versions']
    assert result.durable.document['known_weeks']==seed['known_weeks']
    assert result.proof['original_grade_read_proof']==seed['sidecar']['grade_read_proof']
    assert len(result.proof['native_part_recovery']['parts'])==2
    assert result.proof['native_snapshot_recovery']['binding_sha256']==store.sha(store.canonical(seed['package']['binding']))
    assert all(r.method=='GET' for r in x.calls)
    current_release=str(x.context.go['qualified_runtime']['binding']['release_id'])
    assert not any('/releases/'+current_release in r.full_url for r in x.calls)
    assert store.canonical(x.context.go)==root_before
    record_property('dual_namespace_recovery_GETs',len(x.calls))


def test_v3_restored_history_is_really_appended_and_read_from_new_namespace(tmp_path,multipart_locator_seed,monkeypatch):
    """Two fictional releases; real append, multipart codec and fresh reader."""
    seed=multipart_locator_seed;x=dual_locator_case(tmp_path/'transition',seed,monkeypatch)
    previous=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert_rotated_append_read(tmp_path,seed,x,previous,monkeypatch)


def assert_rotated_append_read(tmp_path,seed,x,previous,monkeypatch):
    """Unchanged checkpoint API writes/reads only the new qualified namespace."""
    from nfl_lab import audit_weekly_grade_v1 as grade,audit_weekly_grade_checkpoint_v1 as checkpoint
    from nfl_lab import audit_weekly_archive_v1 as archive,private_draft_store as store,state
    from test_private_draft_store_v2 import Server,Response
    package=x.context.go['qualified_runtime'];binding=package['binding'];q=package['qualification']
    current_source=x.context.go['source_sha']
    asset_offset=binding['canary_asset_id']-seed['package']['binding']['canary_asset_id']
    class NewServer(Server):
        def release(self):
            result=super().release();result.update(id=binding['release_id'],url=store.API+'/releases/'+str(binding['release_id']))
            return result
        def add(self,name,body=b'fictional',size=None):
            a=super().add(name,body,size);a['id']+=asset_offset
            a['url']=store.API+'/releases/assets/'+str(a['id'])
            a['browser_download_url']='https://github.com/'+store.REPO+'/releases/download/'+self.tag+'/'+name
            return a
        def __call__(self,request,timeout):
            url=request.full_url;release=store.API+'/releases/'+str(binding['release_id'])
            if url==release:
                self.calls.append(request);return Response(self.release())
            if url==release+'/assets?per_page=100&page=1':
                self.calls.append(request);return Response([self.metadata(a) for a in self.assets])
            return super().__call__(request,timeout)
    server=NewServer();journal=tmp_path/'initialize-new';journal.mkdir(mode=0o700)
    init=store.Client('ghs_FICTIONAL',package['run_id'],journal=journal,source_sha=package['source_sha'],transport=server,process='2'*64)
    actual_binding=store.initialize(init,binding['runtime_id'])
    assert actual_binding==binding
    at=[state.utc(seed['current_at'])+timedelta(minutes=2)];finished=[None]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at[0] if tz else at[0].replace(tzinfo=None)
    monkeypatch.setattr(store,'datetime',Clock)
    def transport(request,timeout):
        url=request.full_url
        if '/actions/runs/' in url:
            rid=url.split('/runs/',1)[1].split('/',1)[0]
            if rid==q['run_id']:
                if '/jobs?' not in url:return Response(dict(id=int(rid),head_sha=q['source_sha'],run_attempt=1,event='workflow_dispatch',
                    path='.github/workflows/lab.yml',head_branch=q['job']['workflow_ref'].split('@refs/heads/',1)[1],
                    status='completed',repository=dict(full_name=store.REPO),head_repository=dict(full_name=store.REPO),
                    actor=dict(login='NickNicky19',id=208912933)))
                return Response(dict(total_count=3,jobs=[dict(id=p['job']['api_job_id'],name=p['job']['job_id'],run_id=int(rid),
                    head_sha=p['source_sha'],status='completed',conclusion='success',started_at=p['started_at_utc'],completed_at=p['created_at_utc'])
                    for p in (q['before_proof'],q['read_proof'],q)]))
            assert rid==x.context.client.run_id
            if '/jobs?' not in url:return Response(dict(id=int(rid),head_sha=current_source,run_attempt=1,event='workflow_dispatch',
                path='.github/workflows/lab.yml',head_branch='fictional',status='in_progress',conclusion=None,
                repository=dict(full_name=store.REPO),head_repository=dict(full_name=store.REPO),actor=dict(login='NickNicky19',id=208912933)))
            jobs=[dict(id=901,name=JOBS['restore'],run_id=int(rid),head_sha=current_source,
                started_at=(state.utc(seed['current_at'])+timedelta(minutes=1)).isoformat(),completed_at=finished[0],
                status='completed' if finished[0] else 'in_progress',conclusion='success' if finished[0] else None)]
            if finished[0]:jobs.append(dict(id=902,name=JOBS['consume'],run_id=int(rid),head_sha=current_source,
                started_at=(state.utc(finished[0])+timedelta(seconds=1)).isoformat(),completed_at=None,status='in_progress',conclusion=None))
            return Response(dict(total_count=len(jobs),jobs=jobs))
        return server(request,timeout)
    captures=grade.retained_captures(previous.durable,previous.registered,at=at[0])
    batch=grade.bind_observations(captures,dict(schema_version=grade.VERSION+'-provider-observations',
        source_policy_sha256=history._METADATA_POLICY_SHA,captured_at=at[0].isoformat(),observations=[],finality=[]),
        authenticate=lambda _:True,at=at[0])
    snapshot=grade.grade(previous.registered,captures,[batch],storage=x.storage,output=tmp_path/'transition/new-grade',
        previous=previous.durable,clock=lambda:at[0])
    def client(role):
        journal=tmp_path/('new-'+role);x.storage.register_root(journal)
        c=archive.Client('ghs_FICTIONAL',x.context.client.run_id,journal=journal,source_sha=current_source,transport=transport,
            job=dict(execution_lane='github_actions',workflow_ref=seed['sidecar']['workflow_ref'],workflow_sha=current_source,
                job_id=JOBS[role],permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False),
            operation='append' if role=='restore' else 'restore',readonly=role=='consume',process=('3' if role=='restore' else '4')*64,
            qualification=q)
        c.bind(binding);return c
    writer=client('restore')
    handoff=checkpoint.append(snapshot,writer,package,storage=x.storage,output=tmp_path/'transition/new-append',
        current_root_go_sha256=x.context.root_sha256,authenticate=lambda _:True,
        pending_census=x.context.go['pending_census'],clock=lambda:at[0])
    finished[0]=(at[0]+timedelta(seconds=10)).isoformat();at[0]+=timedelta(seconds=30)
    reader=client('consume')
    restored=checkpoint.restore(handoff,reader,package,previous.registered,storage=x.storage,output=tmp_path/'transition/new-read',
        current_root_go_sha256=x.context.root_sha256,authenticate=lambda _:True,
        pending_census=x.context.go['pending_census'],clock=lambda:at[0])
    assert restored.durable.document['captures']==previous.durable.document['captures']
    assert restored.durable.document['known_versions']==previous.durable.document['known_versions']
    assert restored.durable.document['known_weeks']==previous.durable.document['known_weeks']
    assert handoff['runtime_binding_sha256']==store.sha(store.canonical(binding))
    assert handoff['runtime_binding_sha256']!=seed['sidecar']['checkpoint_handoff']['runtime_binding_sha256']
    assert handoff['producer']['source_sha']==current_source
    assert restored.proof['reader']['source_sha']==current_source
    assert {a['id'] for a in server.assets}.isdisjoint({a['id'] for a in x.server.assets})
    assert all(r.method=='GET' for r in x.calls)
    assert any(r.method=='POST' for r in server.calls)
    # Forecast anchor stays old after grade-only, while this checkpoint is new.
    from nfl_lab import audit_weekly_template_v1 as template
    assert template.capture_runtime(x.context.go)[0]==seed['package']
    assert template.checkpoint_runtime(x.context.go,handoff)[0]==package


@pytest.mark.parametrize('damage',['anchor','census','root_preimage','third_namespace','mixed_binding','source'])
def test_v3_history_rejects_unsealed_namespace_or_original_root(tmp_path,multipart_locator_seed,monkeypatch,damage):
    from nfl_lab import audit_weekly_template_v1 as template,private_draft_store as store,audit_weekly_controller_bootstrap_v1 as bootstrap
    x=dual_locator_case(tmp_path/'dual-rejected',multipart_locator_seed,monkeypatch)
    old=x.context.go['prior_capture_qualified_runtime']
    if damage=='anchor':old['anchor']['receipt_sha256']='0'*64
    elif damage=='census':old['pending_census']['owner_evidence_sha256']='0'*64
    elif damage=='root_preimage':old['root_static_sha256']='0'*64
    elif damage=='third_namespace':old['qualified_runtime']['binding']['runtime_id']='0'*32
    elif damage=='mixed_binding':
        old['qualified_runtime']=deepcopy(x.context.go['qualified_runtime'])
    else:x.context.client.source_sha='0'*40
    with pytest.raises((history.HistoryError,template.TemplateError,store.StoreError,bootstrap.BootstrapError)):
        history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert all(r.method=='GET' for r in x.calls)
    if damage!='root_preimage':assert not any('/releases/' in r.full_url for r in x.calls)

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

def _full_parent_runtime(data):
    """Keep the original full-package digest, including its closed flags."""
    data=deepcopy(data)
    data['qualified_runtime'].update(root_go_sha256='a'*64,private_payload_bytes=0,
        private_durability_qualified=False,strict_v1_unchanged='INCONCLUSIVE')
    value=json.loads(gzip.decompress(data['packed']))
    value['checkpoint_handoff']['qualified_package_sha256']=hashlib.sha256(json.dumps(
        data['qualified_runtime'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    data['packed']=gzip.compress(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),mtime=0)
    return data


def test_parent_full_runtime_preserves_original_package_commitment(parent_metadata):
    data=_full_parent_runtime(parent_metadata)
    expected=json.loads(gzip.decompress(data['packed']))
    assert history.validate_parent_sidecar(**data)==expected
    # The legacy eight-field projection is not the package that was issued.
    for key in ('root_go_sha256','private_payload_bytes','private_durability_qualified','strict_v1_unchanged'):
        del data['qualified_runtime'][key]
    with pytest.raises(history.HistoryError):history.validate_parent_sidecar(**data)


@pytest.mark.parametrize('field,bad',[
    ('root_go_sha256','bad'),('root_go_sha256',None),
    ('private_payload_bytes',1),('private_payload_bytes',True),('private_payload_bytes',0.0),
    ('private_durability_qualified',True),('private_durability_qualified',0),
    ('strict_v1_unchanged','QUALIFIED'),('strict_v1_unchanged',None),
    ('unexpected_authority',False)])
def test_parent_full_runtime_rejects_invalid_flags_even_with_matching_digest(parent_metadata,field,bad):
    data=_full_parent_runtime(parent_metadata)
    data['qualified_runtime'][field]=bad
    value=json.loads(gzip.decompress(data['packed']))
    value['checkpoint_handoff']['qualified_package_sha256']=hashlib.sha256(json.dumps(
        data['qualified_runtime'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    data['packed']=gzip.compress(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),mtime=0)
    with pytest.raises(history.HistoryError):history.validate_parent_sidecar(**data)


@pytest.mark.parametrize('omitted',[tuple(key for index,key in enumerate(
    ('root_go_sha256','private_payload_bytes','private_durability_qualified','strict_v1_unchanged'))
    if mask & (1<<index)) for mask in range(1,15)])
def test_parent_full_runtime_rejects_partial_flag_sets(parent_metadata,omitted):
    data=_full_parent_runtime(parent_metadata)
    for key in omitted:del data['qualified_runtime'][key]
    value=json.loads(gzip.decompress(data['packed']))
    value['checkpoint_handoff']['qualified_package_sha256']=hashlib.sha256(json.dumps(
        data['qualified_runtime'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    data['packed']=gzip.compress(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),mtime=0)
    with pytest.raises(history.HistoryError,match='^CLOSED_PARENT_HISTORY_RUNTIME_PACKAGE$'):
        history.validate_parent_sidecar(**data)


def test_parent_runtime_forms_match_original_bootstrap_inventories(parent_metadata):
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    assert set(parent_metadata['qualified_runtime'])==bootstrap.PACKAGE_KEYS
    assert set(_full_parent_runtime(parent_metadata)['qualified_runtime'])==bootstrap.PACKAGE_FULL_KEYS


@pytest.mark.parametrize('full',[False,True])
def test_parent_validator_cold_import_does_not_load_grade_or_read_sources(parent_metadata,tmp_path,full):
    if full:parent_metadata=_full_parent_runtime(parent_metadata)
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


def source_transition_root(original, receipt, locator, *, runtime_transition='PRESERVE'):
    """New synthetic metadata; original Root/runtime bytes remain untouched."""
    from nfl_lab import private_draft_store as store,audit_weekly_template_v1 as template
    target=deepcopy(original);target.update(schema_version=history.ROOT_V4,source_sha='9'*40)
    target['publication_registration'].update(policy_sha256=store.sha(b'FICTIONAL_NEW_SOURCE_POLICY'),
        policy_gzip_base64='FICTIONAL_NEW_POLICY')
    overrides={}
    for p in ('nfl_lab/audit_weekly_grade_history_v1.py','nfl_lab/audit_weekly_template_v1.py'):
        overrides[p]=target['code_pins'][p]
        target['code_pins'][p]=store.sha(('FICTIONAL_CURRENT_SOURCE:'+p).encode())
    packed=gzip.compress(store.canonical(locator),mtime=0)
    predecessor={k:receipt[k] for k in ('source_sha','workflow_sha256','policy_sha256','recipe_registration_sha256',
        'run_id','feed_sha256','root_go_sha256','epoch_sha256','choice_sha256')}
    predecessor.update(receipt_sha256=locator['anchor']['receipt_sha256'],root_static_sha256=template.static_root_sha256(original),
        code_pins_sha256=store.sha(store.canonical(original['code_pins'])),
        locator=dict(path=history.locator_filename(locator),sha256=store.sha(packed)))
    binding=dict(schema_version=history.SOURCE_HISTORY_BINDING,target_source_sha=target['source_sha'],
        target_policy_sha256=target['publication_registration']['policy_sha256'],predecessor=predecessor,pin_overrides=overrides,
        runtime_transition=runtime_transition)
    target['source_history_binding']=history.source_history_envelope(binding)
    target['effective_epoch'].update(previous_capture=deepcopy(locator['anchor']),
        previous_checkpoint=dict(schema_version=history.LOCATOR_REF,**predecessor['locator']))
    if runtime_transition=='DUAL_RUNTIME_ROTATE':
        from test_audit_weekly_controller_bootstrap_v1 import dual_runtime_root,fictional_runtime_metadata
        target=dual_runtime_root(target,original['qualified_runtime'],original['pending_census'],locator['anchor'],original_root=original)
        target['schema_version']=history.ROOT_V4
        target['qualified_runtime']=fictional_runtime_metadata(original['qualified_runtime'],original['pending_census'],number=5)
    return target


@pytest.fixture
def source_metadata(parent_metadata):
    """128 synthetic pins and closed metadata, no private body or authority."""
    from nfl_lab import private_draft_store as store,audit_weekly_template_v1 as template,audit_weekly_hosted_v1 as hosted
    data=deepcopy(parent_metadata);sidecar=json.loads(gzip.decompress(data['packed']))
    pins={p:store.sha(('FICTIONAL_OLD_PIN:'+p).encode()) for p in hosted.PINS}
    pins.update(data['code_pins'])
    assert len(pins)==128
    schedule=[dict(season=2026,week=8,game_type='REG',game_id='FICTIONAL_GAME',kickoff_utc='2026-10-30T00:00:00+00:00')]
    cuts={'FICTIONAL_GAME':'2026-10-29T23:45:00+00:00'}
    old={k:None for k in template.ROOT_V3_KEYS}
    old.update(schema_version=template.ROOT_V3,source_sha=data['receipt']['source_sha'],approved=True,operation='RECURRING_CAPTURE',
        repository=store.REPO,code_pins=pins,qualified_runtime=data['qualified_runtime'],pending_census={'original':'census4'},
        prior_capture_qualified_runtime={'original':'COUNT7 runtime2'},
        issued_at_utc='2026-10-28T06:00:00+00:00',expires_at_utc='2026-10-28T07:00:00+00:00',
        publication_registration=dict(policy_sha256=data['receipt']['policy_sha256'],policy_gzip_base64='FICTIONAL_OLD_POLICY',
            rights_authority={'original':'rights'},r0={'original':'R0'}),
        effective_epoch=dict(schema_version=history.CONTEXT_V5,controller_context=None,previous_capture={'old':'COUNT7'},previous_checkpoint=None,
            pending_post_recovery={'original':'pending'},plan=dict(kind='FUTURE_CAPABLE',season=2026,week=8,
                deadline_utc=min(cuts.values()),calendar_sha256=store.sha(store.canonical(schedule)),game_cutoffs=cuts)))
    receipt=data['receipt'];receipt['root_go_sha256']=store.sha(store.canonical(old))
    sidecar['root_go_sha256']=receipt['root_go_sha256']
    planning=dict(schema_version=history.LOCATOR_VERSION+'-planning',epoch_sha256=receipt['epoch_sha256'],
        current=dict(season=2026,week=8,schedule=schedule,game_cutoffs=cuts,canonical_choice_sha256=receipt['choice_sha256']),
        next=None,resolved_weeks=[],known_by_at=sidecar['grade_read_proof']['known_by_at'],
        calendar=dict(url='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',sha256='a'*64,bytes=10,
            retrieved_utc='2026-10-28T06:01:00+00:00'))
    cohort=dict(schema_version=history.LOCATOR_VERSION+'-cohort',kind='CAPTURE_AND_GRADE',repository=store.REPO,
        **{k:deepcopy(receipt[k]) for k in ('source_sha','run_id','root_go_sha256','workflow_sha256','epoch_sha256','feed_sha256','jobs','verified_at','created_at')},
        root_issued_at_utc=old['issued_at_utc'],fits=0,public_release=False,successful_forecast=False)
    locator=dict(schema_version=history.LOCATOR_VERSION,repository=store.REPO,cohort=cohort,sidecar=sidecar,planning=planning,
        anchor=dict(feed_sha256=receipt['feed_sha256'],receipt_sha256=store.sha(gzip.compress(store.canonical(receipt),mtime=0))),
        helper_sha256={p:pins[p] for p in history.LOCATOR_HELPERS})
    root=source_transition_root(old,receipt,locator)
    return SimpleNamespace(root=root,original=old,receipt=receipt,locator=locator,jobs=data['jobs'],at=data['at'])


def replace_source_body(root, body):
    """Encode deliberately invalid test metadata without the builder's guards."""
    from nfl_lab import private_draft_store as store
    raw=store.canonical(body)
    root['source_history_binding']=dict(schema_version=history.SOURCE_HISTORY_TRANSPORT,body_sha256=store.sha(raw),
        body_bytes=len(raw),gzip_base64=base64.b64encode(gzip.compress(raw,mtime=0)).decode())


def test_source_scope_static_transport_and_current_source_continuation(source_metadata):
    from nfl_lab import private_draft_store as store,audit_weekly_template_v1 as template
    x=source_metadata;before=store.canonical(x.original)
    binding=history.validate_source_history_binding(x.root)
    assert x.root['source_history_binding']==history.source_history_envelope(binding)
    assert gzip.decompress(base64.b64decode(x.root['source_history_binding']['gzip_base64']))==store.canonical(binding)
    assert history.source_history_scope(x.root,x.receipt,locator=x.locator,
        locator_sha256=binding['predecessor']['locator']['sha256'])==x.original['code_pins']
    static=deepcopy(x.root);static['approved']=False
    for k in template.DYNAMIC_FIELDS-{'approved'}:static[k]=None
    assert history.validate_source_history_binding(static)==binding
    assert history.source_history_scope(static,x.receipt,locator=x.locator,
        locator_sha256=binding['predecessor']['locator']['sha256'])==x.original['code_pins']
    assert template.static_root_sha256(static)==template.static_root_sha256(x.root)
    later=deepcopy(x.receipt);later.update(source_sha=x.root['source_sha'],policy_sha256=binding['target_policy_sha256'])
    assert history.source_history_scope(x.root,later)==x.root['code_pins']
    x.root['effective_epoch']['previous_capture']['feed_sha256']='f'*64
    with pytest.raises(history.HistoryError,match='REGISTERED_PREDECESSOR'):
        history.source_history_scope(x.root,x.receipt)
    assert store.canonical(x.original)==before
    assert history._SOURCE_ROOT_V3_KEYS==template.ROOT_V3_KEYS


@pytest.mark.parametrize('field',['source_sha','workflow_sha256','policy_sha256','recipe_registration_sha256',
    'run_id','feed_sha256','root_go_sha256','epoch_sha256','choice_sha256'])
def test_source_scope_rejects_any_changed_original_receipt(source_metadata,field):
    x=source_metadata;x.receipt[field]='123' if field=='run_id' else '0'*(40 if field=='source_sha' else 64)
    with pytest.raises(history.HistoryError):history.source_history_scope(x.root,x.receipt)


@pytest.mark.parametrize('damage',['binding_extra','predecessor_extra','missing_binding','raw_body','old_root','target_source','target_policy',
    'pin_digest','missing_pin','added_pin','unchanged_override','forbidden_grade','forbidden_checkpoint','forbidden_workflow','forbidden_feature',
    'forbidden_R0','forbidden_config','forbidden_procedure','forbidden_numerical','locator_run','receipt_anchor','locator_hash','locator_path','cohort','jobs'])
def test_source_binding_rejects_scope_or_pin_mutations(source_metadata,damage):
    from nfl_lab import private_draft_store as store
    x=source_metadata;body=history.validate_source_history_binding(x.root)
    if damage=='binding_extra':body['waiver']=True
    elif damage=='predecessor_extra':body['predecessor']['reset_claim']=True
    elif damage=='missing_binding':del x.root['source_history_binding']
    elif damage=='raw_body':x.root['source_history_binding']=body
    elif damage=='old_root':x.root['schema_version']='audit-weekly-hosted-v3-root-GO'
    elif damage=='target_source':x.root['source_sha']='0'*40
    elif damage=='target_policy':x.root['publication_registration']['policy_sha256']='0'*64
    elif damage=='pin_digest':body['predecessor']['code_pins_sha256']='0'*64
    elif damage=='missing_pin':del x.root['code_pins'][history.FILES[1]]
    elif damage=='added_pin':x.root['code_pins']['nfl_lab/not_original.py']='0'*64
    elif damage=='unchanged_override':body['pin_overrides'][history.FILES[0]]=x.root['code_pins'][history.FILES[0]]
    elif damage.startswith('forbidden_'):
        p={'grade':'nfl_lab/audit_weekly_grade_v1.py','checkpoint':'nfl_lab/audit_weekly_grade_checkpoint_v1.py',
            'workflow':'.github/workflows/lab.yml','feature':'nfl_lab/features.py','R0':'nfl_lab/audit_reference_capture_v1.py',
            'config':'config/audit-weekly-numerical-runtime-v1.json','procedure':'nfl_lab/weekly_generic_producer.py',
            'numerical':'nfl_lab/audit_numerical_runtime_v1.py'}[damage.split('_',1)[1]]
        body['pin_overrides'][p]='0'*64
    elif damage=='locator_run':body['predecessor']['locator']['path']=body['predecessor']['locator']['path'].replace('--45000000001--','--45000000099--')
    elif damage=='receipt_anchor':x.locator['anchor']['receipt_sha256']='0'*64
    elif damage=='locator_hash':body['predecessor']['locator']['sha256']='0'*64
    elif damage=='locator_path':x.locator['sidecar']['checkpoint_handoff']['snapshot_sha256']='0'*64
    elif damage=='cohort':x.locator['cohort']['source_sha']='0'*40
    elif damage=='jobs':x.locator['cohort']['jobs']['restore']['api_job_id']+=100
    if damage not in {'missing_binding','raw_body'}:replace_source_body(x.root,body)
    locator_sha=store.sha(gzip.compress(store.canonical(x.locator),mtime=0))
    with pytest.raises(history.HistoryError):
        history.source_history_scope(x.root,x.receipt,locator=x.locator,locator_sha256=locator_sha)


@pytest.mark.parametrize('damage',['extra','body_hash','body_bytes','boolean_bytes','base64','trailing','multiple','truncated','noncanonical','duplicate',
    'nan','infinity','oversize_plain','oversize_encoded'])
def test_source_transport_is_closed_single_canonical_bounded_gzip(source_metadata,damage):
    from nfl_lab import private_draft_store as store
    root=source_metadata.root;envelope=root['source_history_binding'];raw=gzip.decompress(base64.b64decode(envelope['gzip_base64']))
    packed=None
    if damage=='extra':envelope['body']=json.loads(raw)
    elif damage=='body_hash':envelope['body_sha256']='0'*64
    elif damage=='body_bytes':envelope['body_bytes']+=1
    elif damage=='boolean_bytes':envelope['body_bytes']=True
    elif damage=='base64':envelope['gzip_base64']='***'
    elif damage=='trailing':packed=base64.b64decode(envelope['gzip_base64'])+b'junk'
    elif damage=='multiple':packed=base64.b64decode(envelope['gzip_base64'])+gzip.compress(b'{}',mtime=0)
    elif damage=='truncated':packed=base64.b64decode(envelope['gzip_base64'])[:-1]
    elif damage=='noncanonical':raw=json.dumps(json.loads(raw),indent=2).encode()
    elif damage=='duplicate':raw=b'{"schema_version":"duplicate",'+raw[1:]
    elif damage=='nan':raw=raw.replace(b'"pin_overrides":{',b'"pin_overrides":{"invalid":NaN,')
    elif damage=='infinity':raw=raw.replace(b'"pin_overrides":{',b'"pin_overrides":{"invalid":Infinity,')
    elif damage=='oversize_plain':raw=b' '*(history.SOURCE_HISTORY_PLAIN_CAP+1)
    elif damage=='oversize_encoded':envelope['gzip_base64']='A'*(history.SOURCE_HISTORY_ENCODED_CAP+1)
    if damage in {'noncanonical','duplicate','nan','infinity','oversize_plain'}:
        envelope.update(body_bytes=len(raw),body_sha256=store.sha(raw));packed=gzip.compress(raw,mtime=0)
    if packed is not None:envelope['gzip_base64']=base64.b64encode(packed).decode()
    with pytest.raises(history.HistoryError):history.validate_source_history_binding(root)


@pytest.fixture
def source_transition_seed(tmp_path,original_seed,monkeypatch,*,historical_pending=False):
    from nfl_lab import audit_weekly_grade_v1 as grade
    actual_grade=grade.grade;actual_parts=grade._write_snapshot_v2
    def split(storage,output,document,*,part_bytes=None):
        size=sum(len(c) for c in grade._canonical_chunks(document))
        return actual_parts(storage,output,document,part_bytes=min(64<<20,(size+1)//2))
    monkeypatch.setattr(grade,'_write_snapshot_v2',split)
    monkeypatch.setattr(grade,'grade',lambda *a,**kw:actual_grade(*a,**kw,wire_version=2))
    return locator_seed.__wrapped__(tmp_path,original_seed,monkeypatch,source_transition=True,historical_pending=historical_pending)


def source_transition_case(root,seed,monkeypatch,*,runtime_transition='PRESERVE'):
    from nfl_lab import private_draft_store as store,state
    from test_private_draft_store_v2 import Response
    x=locator_recovery_case(root,seed,monkeypatch)
    x.context.go=source_transition_root(seed['original_root'],seed['receipt'],seed['locator'],runtime_transition=runtime_transition)
    x.context.go['issued_at_utc']=seed['current_at']
    x.context.go['expires_at_utc']=(state.utc(seed['current_at'])+timedelta(hours=1)).isoformat()
    x.context.root_sha256=store.sha(store.canonical(x.context.go))
    original_api=x.api;target=x.context.go['source_sha'];directory=[]
    def transport(request,timeout):
        if '/contents/'+history.LOCATOR_ROOT+'?' in request.full_url:
            x.calls.append(request)
            name=history.locator_filename(seed['locator'])
            rows=[dict(type='file',name=name,path=history.LOCATOR_ROOT+'/'+name,size=x.sidecar['bytes'])]
            if x.damage.get('newer_locator'):
                name=name.replace('2026','2027',1);rows.append(dict(type='file',name=name,path=history.LOCATOR_ROOT+'/'+name,size=100))
            directory.append(request);return Response(rows)
        response=original_api(request,timeout)
        if '/actions/runs/'+x.context.client.run_id in request.full_url:
            doc=json.loads(response.body)
            if 'jobs' in doc:
                for job in doc['jobs']:job['head_sha']=target
            else:doc['head_sha']='0'*40 if x.damage.get('current_source') else target
            return Response(doc)
        return response
    x.api=transport;x.context.client.transport=transport
    x.context.client.source_sha=target;x.context.client.job['workflow_sha']=target
    x.directory=directory
    return x


def test_source_transition_restores_full_native_multipart_history_with_current_identity(tmp_path,source_transition_seed,monkeypatch):
    from nfl_lab import audit_weekly_grade_v1 as grade,private_draft_store as store
    seed=source_transition_seed;x=source_transition_case(tmp_path/'new-source',seed,monkeypatch)
    root_before=store.canonical(x.context.go);old_before=store.canonical(seed['original_root'])
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert grade._digest(result.durable.document)==seed['durable_sha256']
    assert result.durable.document['known_versions']==seed['known_versions']
    assert result.durable.document['known_weeks']==seed['known_weeks']
    assert result.proof['original_grade_read_proof']==seed['sidecar']['grade_read_proof']
    assert result.proof['current']['source_sha']==x.context.go['source_sha']!=seed['source']
    assert len(result.proof['native_part_recovery']['parts'])==2
    assert len(x.directory)==2 and all(r.method=='GET' for r in x.calls)
    assert store.canonical(x.context.go)==root_before and store.canonical(seed['original_root'])==old_before
    for k in ('qualified_runtime','pending_census','prior_capture_qualified_runtime'):
        assert x.context.go[k]==seed['original_root'][k]
    assert not any('/contents/' in r.full_url and '?ref='+x.context.go['source_sha'] in r.full_url for r in x.calls)


@pytest.mark.parametrize('damage',['source','run','job','current_source','newer_locator'])
def test_source_transition_authenticates_old_and_current_sources_before_private_GET(tmp_path,source_transition_seed,monkeypatch,damage):
    from nfl_lab import private_draft_store as store
    x=source_transition_case(tmp_path/'reject',source_transition_seed,monkeypatch);x.damage[damage]=True
    with pytest.raises((history.HistoryError,store.StoreError)):
        history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert not any('/releases/' in r.full_url for r in x.calls)


@pytest.mark.parametrize('field',['retained_registration','original_selected_handoff','source_config','qualified_runtime','pending_census',
    'prior_capture_qualified_runtime','cutoff_lead_seconds','jobs','limits','owner_authorization','publication','workflow_ref','single_writer_group'])
def test_source_transition_rejects_changed_protected_static_root_fields(tmp_path,source_transition_seed,monkeypatch,field):
    seed=source_transition_seed;x=source_transition_case(tmp_path/'static',seed,monkeypatch)
    x.context.go[field]={'FORBIDDEN':'STATIC_CHANGE'}
    envelope=next(history.metadata_document(base64.b64decode(a['body']),cap=history.LIMITS['envelope_bytes'])
        for a in seed['assets'] if a['name']=='blob-'+seed['sidecar']['evidence_descriptor']['entry']['payload']['sha256']+'.bin')
    pins=history._source_history_pins(x.context.go,history.validate_source_history_binding(x.context.go))
    jobs={role:dict(id=seed['locator']['cohort']['jobs'][role]['api_job_id'],name=JOBS[role],head_sha=seed['source'],
        run_id=int(seed['old_run']),status='completed',conclusion='success',started_at=a,completed_at=b)
        for (role,(a,b)) in zip(JOBS,seed['job_times'])}
    with pytest.raises(history.HistoryError,match='STATIC_FIELDS_AND_RUNTIMES_UNCHANGED'):
        history._root_envelope(envelope,seed['locator'],jobs,code_pins=pins,static_root=x.context.go,at=seed['current_at'])


@pytest.mark.parametrize('schema',['audit-weekly-hosted-v1-root-GO','audit-weekly-hosted-v2-root-GO','audit-weekly-hosted-v3-root-GO'])
def test_legacy_roots_cannot_smuggle_source_binding(source_metadata,schema):
    root=source_metadata.root;root['schema_version']=schema
    with pytest.raises(history.HistoryError,match='REQUIRES_ROOT_V4'):history.validate_source_history_binding(root)
    del root['source_history_binding']
    assert history.validate_source_history_binding(root) is None
    with pytest.raises(history.HistoryError,match='ADAPTER_REQUIRED'):history.source_history_scope(root,source_metadata.receipt)


def test_source_transport_preserves_58210_byte_root_within_existing_dispatch_caps(source_metadata):
    from nfl_lab import private_draft_store as store
    x=source_metadata;old=deepcopy(x.original)
    old['owner_authorization']='x'*(58210-len(store.canonical(old))+2)
    assert len(store.canonical(old))==58210
    receipt=deepcopy(x.receipt);receipt['root_go_sha256']=store.sha(store.canonical(old))
    locator=deepcopy(x.locator);locator['cohort']['root_go_sha256']=receipt['root_go_sha256']
    locator['sidecar']['root_go_sha256']=receipt['root_go_sha256']
    locator['anchor']['receipt_sha256']=store.sha(gzip.compress(store.canonical(receipt),mtime=0))
    target=source_transition_root(old,receipt,locator);raw=store.canonical(target)
    dispatch=dict(ref='fictional',inputs=dict(mode='audit-weekly-producer-v1',inference_builder_go_json=raw.decode(),
        inference_builder_go_sha256=store.sha(raw)))
    assert len(raw)<=60<<10 and len(store.canonical(dispatch))<65535
    binding=history.validate_source_history_binding(target)
    assert binding['predecessor']['root_go_sha256']==store.sha(store.canonical(old))
    assert int.from_bytes(base64.b64decode(target['source_history_binding']['gzip_base64'])[4:8],'little')==0


def test_source_metadata_cold_process_never_imports_numerical_or_performs_io(source_metadata,tmp_path):
    from nfl_lab import private_draft_store as store
    x=source_metadata;path=tmp_path/'source-metadata.json'
    path.write_bytes(store.canonical(dict(root=x.root,receipt=x.receipt,locator=x.locator)))
    script='''import sys,json,socket
from pathlib import Path
from unittest.mock import patch
from nfl_lab import audit_weekly_grade_history_v1 as h
data=json.loads(Path(sys.argv[1]).read_bytes())
def denied(*a,**k):raise AssertionError("SOURCE_METADATA_IO_OR_NUMERICAL_FORBIDDEN")
with patch.object(h,"_modules",denied),patch.object(Path,"read_bytes",denied),patch.object(Path,"read_text",denied),patch("builtins.open",denied),patch.object(socket.socket,"connect",denied):
 binding=h.validate_source_history_binding(data["root"])
 pins=h.source_history_scope(data["root"],data["receipt"],locator=data["locator"],locator_sha256=binding["predecessor"]["locator"]["sha256"])
 assert len(pins)==128
 assert h.source_history_envelope(binding)==data["root"]["source_history_binding"]
assert not any(n in sys.modules for n in ("nfl_lab.audit_weekly_grade_v1","nfl_lab.audit_weekly_grade_checkpoint_v1","numpy","scipy","pandas","sklearn"))
print("PURE_SOURCE_HISTORY_METADATA_OK")
'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(path)],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='PURE_SOURCE_HISTORY_METADATA_OK'


@pytest.mark.parametrize('damage',['full_hash','static_hash','old_root_body','old_root_pins','old_schema','rights','r0','locator_hash'])
def test_source_root_preimage_and_original_policy_commitments_are_independent(source_metadata,damage):
    x=source_metadata;body=history.validate_source_history_binding(x.root)
    old=deepcopy(x.original)
    if damage=='full_hash':body['predecessor']['root_go_sha256']='f'*64
    elif damage=='static_hash':body['predecessor']['root_static_sha256']='f'*64
    elif damage=='old_root_body':old['owner_authorization']='FORBIDDEN_OLD_ROOT_REWRITE'
    elif damage=='old_root_pins':old['code_pins'][history.FILES[0]]='f'*64
    elif damage=='old_schema':old['schema_version']='audit-weekly-hosted-v2-root-GO'
    elif damage in {'rights','r0'}:x.root['publication_registration']['rights_authority' if damage=='rights' else 'r0']={'forbidden':'new identity'}
    replace_source_body(x.root,body)
    envelope=dict(root_go=old,planning=deepcopy(x.locator['planning']))
    kwargs=dict(code_pins=x.original['code_pins'],static_root=x.root,at=x.at)
    if damage=='locator_hash':kwargs['locator_sha256']='f'*64
    with pytest.raises(history.HistoryError):history._root_envelope(envelope,x.locator,x.jobs,**kwargs)


@pytest.mark.parametrize('value',[None,'','ROTATE','PRESERVE_THEN_FALLBACK',True,[],{}])
def test_source_runtime_transition_must_be_an_explicit_closed_enum(source_metadata,value):
    root=source_metadata.root;body=history.validate_source_history_binding(root)
    body['runtime_transition']=value;replace_source_body(root,body)
    with pytest.raises(history.HistoryError,match='EXPLICIT_SOURCE_HISTORY_RUNTIME_TRANSITION'):
        history.validate_source_history_binding(root)
    del body['runtime_transition'];replace_source_body(root,body)
    with pytest.raises(history.HistoryError,match='CLOSED_SOURCE_HISTORY_BINDING'):
        history.validate_source_history_binding(root)


def source_rotation_envelope(seed):
    return next(history.metadata_document(base64.b64decode(a['body']),cap=history.LIMITS['envelope_bytes'])
        for a in seed['assets'] if a['name']=='blob-'+seed['sidecar']['evidence_descriptor']['entry']['payload']['sha256']+'.bin')


def source_rotation_jobs(seed):
    return {role:dict(id=seed['locator']['cohort']['jobs'][role]['api_job_id'],name=JOBS[role],head_sha=seed['source'],
        run_id=int(seed['old_run']),status='completed',conclusion='success',started_at=a,completed_at=b)
        for role,(a,b) in zip(JOBS,seed['job_times'])}


def test_cross_source_rotation_reads_original4_then_appends_and_reads_current5(tmp_path,source_transition_seed,monkeypatch):
    from nfl_lab import private_draft_store as store,audit_weekly_grade_v1 as grade,audit_weekly_template_v1 as template
    seed=source_transition_seed;old=store.canonical(seed['original_root'])
    x=source_transition_case(tmp_path/'rotation',seed,monkeypatch,runtime_transition='DUAL_RUNTIME_ROTATE')
    root_before=store.canonical(x.context.go)
    # An already-consumed first-future claim remains in the original release;
    # neither source transition nor rotation creates another bootstrap claim.
    claim=store.canonical(dict(schema_version='audit-weekly-owner-first-future-primary-v1-claim',
        epoch_sha256=seed['receipt']['epoch_sha256'],stream_id='weekly-corrected-primary-player-game-v1'))
    x.server.add('blob-'+store.sha(claim)+'.bin',claim)
    old_assets=deepcopy(x.server.assets)
    current=x.context.go['qualified_runtime'];prior=x.context.go['prior_capture_qualified_runtime']
    assert template.capture_runtime(x.context.go)==(seed['package'],seed['census'])
    assert store.canonical(prior['qualified_runtime'])==store.canonical(seed['original_root']['qualified_runtime'])
    assert store.canonical(prior['pending_census'])==store.canonical(seed['original_root']['pending_census'])
    assert prior['anchor']==seed['locator']['anchor']
    assert prior['root_static_sha256']==template.static_root_sha256(seed['original_root'])
    previous=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert grade._digest(previous.durable.document)==seed['durable_sha256']
    assert previous.proof['original_grade_read_proof']==seed['sidecar']['grade_read_proof']
    assert previous.proof['native_snapshot_recovery']['binding_sha256']==store.sha(store.canonical(prior['qualified_runtime']['binding']))
    assert previous.proof['current']['source_sha']==x.context.go['source_sha']
    assert x.server.assets==old_assets and all(r.method=='GET' for r in x.calls)
    assert not any('/releases/'+str(current['binding']['release_id']) in r.full_url for r in x.calls)
    assert_rotated_append_read(tmp_path,seed,x,previous,monkeypatch)
    assert store.canonical(seed['original_root'])==old and store.canonical(x.context.go)==root_before
    assert x.server.assets==old_assets


@pytest.mark.parametrize('damage',['preserve_enum','prior_package','prior_census','anchor','root_static','same_runtime','reuse_COUNT7',
    'unqualified','new_census','quota_cap','deletion','source_config','retained_registration','rights','r0','limits','new_binding'])
def test_source_rotation_rejects_unsealed_or_migrated_runtime_metadata(tmp_path,source_transition_seed,monkeypatch,damage):
    from nfl_lab import private_draft_store as store,audit_private_rotation_v1 as rotation
    seed=source_transition_seed;x=source_transition_case(tmp_path/'reject-rotation',seed,monkeypatch,runtime_transition='DUAL_RUNTIME_ROTATE')
    root=x.context.go;prior=root['prior_capture_qualified_runtime'];current=root['qualified_runtime']
    if damage=='preserve_enum':
        body=history.validate_source_history_binding(root);body['runtime_transition']='PRESERVE';replace_source_body(root,body)
    elif damage=='prior_package':prior['qualified_runtime']['root_go_sha256']='f'*64
    elif damage=='prior_census':prior['pending_census']['owner_evidence_sha256']='f'*64
    elif damage=='anchor':prior['anchor']['feed_sha256']='f'*64
    elif damage=='root_static':prior['root_static_sha256']='f'*64
    elif damage=='same_runtime':root['qualified_runtime']=deepcopy(prior['qualified_runtime'])
    elif damage=='reuse_COUNT7':root['qualified_runtime']=deepcopy(seed['original_root']['prior_capture_qualified_runtime']['qualified_runtime'])
    elif damage=='unqualified':current['qualification']['exact_readback']=False
    elif damage=='new_census':root['pending_census']['owner_evidence_sha256']='f'*64
    elif damage=='quota_cap':current['quota_reservation']['reserved_after_bytes']=513<<20
    elif damage=='deletion':current['quota_reservation']['old_assets_deleted']=1
    elif damage in {'source_config','retained_registration','limits'}:root[damage]={'forbidden':'migration'}
    elif damage in {'rights','r0'}:root['publication_registration']['rights_authority' if damage=='rights' else 'r0']={'forbidden':'migration'}
    elif damage=='new_binding':current['binding']['release_id']+=1
    pins=history._source_history_pins(root,history.validate_source_history_binding(root))
    with pytest.raises((history.HistoryError,ValueError,store.StoreError,rotation.RotationError)):
        history._root_envelope(source_rotation_envelope(seed),seed['locator'],source_rotation_jobs(seed),code_pins=pins,
            static_root=root,at=seed['current_at'])


@pytest.fixture
def rotation_quota_metadata(original_seed):
    return dict(package=deepcopy(original_seed['package']),census=deepcopy(original_seed['census']),before=original_seed['current_at'])


@pytest.mark.parametrize('existing,unknown',[(1,0),(6,0),(6,1),(15,0)])
def test_main_quota_metadata_matches_rotation_and_never_performs_io(rotation_quota_metadata,monkeypatch,existing,unknown):
    from nfl_lab import audit_private_rotation_v1 as rotation,private_draft_store as store
    data=rotation_quota_metadata;q=data['package']['quota_reservation']
    q.update(existing_draft_runtimes=existing,pending_unlocated_runtimes=unknown,
        reserved_before_bytes=(existing+unknown)*(32<<20),reserved_after_bytes=(existing+unknown+1)*(32<<20),
        charged_existing_bytes=0,charged_existing_assets=0)
    original=store.canonical(data)
    rotation.checked_quota(q,dict(runtime_id=data['package']['runtime_id'],pending_census=data['census']))
    def denied(*a,**k):pytest.fail('QUOTA_METADATA_IO_OR_PRODUCER_CALL_FORBIDDEN')
    monkeypatch.setattr(rotation,'checked_quota',denied);monkeypatch.setattr(history,'_modules',denied)
    monkeypatch.setattr(store,'read_local',denied);monkeypatch.setattr(Path,'read_bytes',denied);monkeypatch.setattr(Path,'read_text',denied)
    monkeypatch.setattr('builtins.open',denied)
    assert history._source_history_rotation_quota(**data)==q
    assert store.canonical(data)==original


@pytest.mark.parametrize('damage',['extra','missing','schema','global_cap','runtime_cap','target','deleted','metadata','bool_count','negative',
    'no_existing','global_overflow','reserved_before','reserved_after','charged_bytes','charged_assets','pending_count','census_hash','inventory_hash'])
def test_main_quota_mutations_rejected_by_existing_rotation_and_metadata(rotation_quota_metadata,damage):
    from nfl_lab import audit_private_rotation_v1 as rotation
    data=rotation_quota_metadata;q=data['package']['quota_reservation']
    if damage=='extra':q['waiver']=True
    elif damage=='missing':del q['old_assets_deleted']
    elif damage=='schema':q['schema_version']='not-qualified'
    elif damage=='global_cap':q['global_cap_bytes']+=1
    elif damage=='runtime_cap':q['new_runtime_reserved_bytes']+=1
    elif damage=='target':q['new_runtime_id']='f'*32
    elif damage=='deleted':q['old_assets_deleted']=1
    elif damage=='metadata':q['metadata_only']=False
    elif damage=='bool_count':q['pending_records']=False
    elif damage=='negative':q['pending_unlocated_runtimes']=-1
    elif damage=='no_existing':q['existing_draft_runtimes']=0
    elif damage=='global_overflow':q.update(existing_draft_runtimes=15,pending_unlocated_runtimes=1,reserved_before_bytes=512<<20,reserved_after_bytes=544<<20)
    elif damage=='reserved_before':q['reserved_before_bytes']+=1
    elif damage=='reserved_after':q['reserved_after_bytes']+=1
    elif damage=='charged_bytes':q['charged_existing_bytes']=q['existing_draft_runtimes']*(32<<20)+1
    elif damage=='charged_assets':q['charged_existing_assets']=q['existing_draft_runtimes']*128+1
    elif damage=='pending_count':q['pending_records']+=1
    elif damage=='census_hash':q['pending_census_sha256']='f'*64
    elif damage=='inventory_hash':q['inventory_sha256']='invalid'
    with pytest.raises(rotation.RotationError):
        rotation.checked_quota(q,dict(runtime_id=data['package']['runtime_id'],pending_census=data['census']))
    with pytest.raises(history.HistoryError):history._source_history_rotation_quota(**data)


@pytest.mark.parametrize('damage',['census_extra','incomplete','owner_hash','future_census','naive_clock','qualification_future','row_extra',
    'row_duplicate','row_boolean','row_over_cap','row_current_runtime','row_release_boolean','row_runtime','bool_deleted','float_global_cap'])
def test_main_rotation_census_keeps_existing_strict_types_and_clocks(rotation_quota_metadata,damage):
    from nfl_lab import private_draft_store as store
    data=rotation_quota_metadata;p=data['package'];c=data['census']
    row=dict(reservation_sha256='e'*64,runtime_id=None,release_id=None,pending_bytes=1,pending_assets=1)
    if damage=='census_extra':c['reset_claim']=True
    elif damage=='incomplete':c['complete']=False
    elif damage=='owner_hash':c['owner_evidence_sha256']='invalid'
    elif damage=='future_census':c['as_of_utc']='2099-01-01T00:00:00+00:00'
    elif damage=='naive_clock':c['as_of_utc']='2026-01-01T00:00:00'
    elif damage=='qualification_future':p['qualification']['created_at_utc']='2099-01-01T00:00:00+00:00'
    elif damage=='bool_deleted':p['quota_reservation']['old_assets_deleted']=False
    elif damage=='float_global_cap':p['quota_reservation']['global_cap_bytes']=float(512<<20)
    else:
        c['reservations']=[row]
        if damage=='row_extra':row['fallback']=True
        elif damage=='row_duplicate':c['reservations'].append(deepcopy(row))
        elif damage=='row_boolean':row['pending_assets']=True
        elif damage=='row_over_cap':row['pending_bytes']=(32<<20)+1
        elif damage=='row_current_runtime':row['runtime_id']=p['runtime_id']
        elif damage=='row_release_boolean':row['release_id']=True
        elif damage=='row_runtime':row['runtime_id']='invalid'
    p['quota_reservation'].update(pending_records=len(c['reservations']),pending_census_sha256=store.sha(store.canonical(c)))
    with pytest.raises(history.HistoryError):history._source_history_rotation_quota(**data)


@pytest.fixture
def source_pending_seed(tmp_path,original_seed,monkeypatch):
    return source_transition_seed.__wrapped__(tmp_path,original_seed,monkeypatch,historical_pending=True)


def test_continued_pending_pool_preserve_same_source_and_rotation_keep_original_evidence(tmp_path,source_pending_seed,monkeypatch):
    from nfl_lab import private_draft_store as store,audit_weekly_template_v1 as template,state
    seed=source_pending_seed;old=seed['original_root'];before=store.canonical(old);pool=template.pending_recovery(old)
    assert store.sha(before)!=state.digest(old),'ROOT_WIRE_CANONICAL_ENCODING_MUST_BE_TESTED'
    assert pool['handoffs'] and pool['pending_reservations']
    assert history.continued_pending_recovery(old,old)==pool
    preserve=source_transition_root(old,seed['receipt'],seed['locator'])
    assert history.continued_pending_recovery(preserve,old)==pool
    x=source_transition_case(tmp_path/'pending-rotation',seed,monkeypatch,runtime_transition='DUAL_RUNTIME_ROTATE')
    new_pool=history.continued_pending_recovery(x.context.go,old)
    assert new_pool==dict(schema_version=template.PENDING_RECOVERY,handoffs=[],pending_reservations=[])
    # The inherited old pool may not be passed as new-namespace evidence.
    with pytest.raises(template.TemplateError,match='PENDING_POST_NAMESPACE_MISMATCH'):template.pending_recovery(x.context.go)
    x.context.go['effective_epoch']['pending_post_recovery']=new_pool
    x.context.root_sha256=store.sha(store.canonical(x.context.go))
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    proof=result.proof['source_history_continuation']
    assert proof['original_root_go_sha256']==store.sha(before)
    assert proof['original_pending_recovery_sha256']==store.sha(store.canonical(pool))
    assert proof['continued_pending_recovery_sha256']==store.sha(store.canonical(new_pool))
    retained=history.metadata_document(Path(proof['original_native_evidence_envelope']['path']).read_bytes(),cap=history.LIMITS['envelope_bytes'])
    assert store.canonical(retained['root_go'])==before
    assert template.pending_recovery(retained['root_go'])==pool
    assert store.canonical(old)==before and all(r.method=='GET' for r in x.calls)


@pytest.mark.parametrize('damage',['old_root','prior_pool_namespace','prior_package','prior_census','anchor','quota','same_source_namespace'])
def test_continued_pending_rejects_wrong_root_runtime_and_namespace(source_pending_seed,damage):
    from nfl_lab import private_draft_store as store,audit_weekly_template_v1 as template
    seed=source_pending_seed;old=deepcopy(seed['original_root'])
    root=source_transition_root(old,seed['receipt'],seed['locator'],runtime_transition='DUAL_RUNTIME_ROTATE')
    if damage=='old_root':old['owner_authorization']='changed'
    elif damage=='prior_pool_namespace':
        pool=template.pending_recovery(old);pool['handoffs'][0]['binding']=deepcopy(root['qualified_runtime']['binding'])
        old['effective_epoch']['pending_post_recovery']=pool
    elif damage=='prior_package':root['prior_capture_qualified_runtime']['qualified_runtime']['root_go_sha256']='f'*64
    elif damage=='prior_census':root['prior_capture_qualified_runtime']['pending_census']['owner_evidence_sha256']='f'*64
    elif damage=='anchor':root['prior_capture_qualified_runtime']['anchor']['feed_sha256']='f'*64
    elif damage=='quota':root['qualified_runtime']['quota_reservation']['old_assets_deleted']=1
    elif damage=='same_source_namespace':
        root['source_sha']=old['source_sha'];del root['source_history_binding'];root['schema_version']='audit-weekly-hosted-v3-root-GO'
    with pytest.raises((history.HistoryError,ValueError,store.StoreError)):history.continued_pending_recovery(root,old)


def test_cold_main_rotation_and_pending_continuation_have_no_producer_dependency(source_pending_seed,tmp_path):
    """Load only the literal Parent dependency inventory in a fresh process."""
    from nfl_lab import private_draft_store as store
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    # A hosted checkout has no sibling audit worktree. Reproduce the declared
    # Parent package boundary, with no implicit access to Producer modules.
    main=tmp_path/'metadata-only'
    for name in bootstrap.PARENT_EXECUTABLE_PINS|{'nfl_lab/__init__.py'}:
        target=main/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    assert not (main/'nfl_lab/audit_private_rotation_v1.py').exists()
    assert not (main/'nfl_lab/audit_weekly_grade_v1.py').exists()
    seed=source_pending_seed
    root=source_transition_root(seed['original_root'],seed['receipt'],seed['locator'],runtime_transition='DUAL_RUNTIME_ROTATE')
    root['approved']=False
    for k in ('issued_at_utc','expires_at_utc','operation','effective_epoch'):root[k]=None
    path=tmp_path/'main-rotation-metadata.json'
    path.write_bytes(store.canonical(dict(root=root,receipt=seed['receipt'],locator=seed['locator'],
        locator_sha256=store.sha(gzip.compress(store.canonical(seed['locator']),mtime=0)),
        envelope=source_rotation_envelope(seed),jobs=source_rotation_jobs(seed),at=seed['current_at'])))
    script='''import sys,json,importlib.util,importlib.abc,socket,resource,signal
from pathlib import Path
from unittest.mock import patch
main=Path(sys.argv[1]);sys.path.insert(0,str(main))
resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(180)
class MetadataOnly(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in {"nfl_lab.audit_private_rotation_v1","nfl_lab.audit_weekly_grade_v1","nfl_lab.audit_weekly_grade_checkpoint_v1"} or fullname.split(".")[0] in {"numpy","scipy","pandas","sklearn","catboost"}:
   raise AssertionError("MAIN_ROTATION_PRODUCER_IMPORT_FORBIDDEN:"+fullname)
sys.meta_path.insert(0,MetadataOnly())
import nfl_lab
spec=importlib.util.spec_from_file_location("nfl_lab.audit_weekly_grade_history_v1",sys.argv[2])
h=importlib.util.module_from_spec(spec);sys.modules[spec.name]=h;setattr(nfl_lab,"audit_weekly_grade_history_v1",h);spec.loader.exec_module(h)
from nfl_lab import audit_weekly_template_v1 as t,private_draft_store as store
data=json.loads(Path(sys.argv[3]).read_bytes())
def denied(*a,**k):raise AssertionError("MAIN_METADATA_BODY_OR_NETWORK_FORBIDDEN")
read_local=store.read_local
def config_only(path,cap):
 assert Path(path)==store.CONFIG
 return read_local(path,cap)
with patch.object(h,"_modules",denied),patch.object(Path,"read_bytes",denied),patch.object(Path,"read_text",denied),patch("builtins.open",denied),patch.object(socket.socket,"connect",denied),patch.object(store,"read_local",config_only):
 pins=h.source_history_scope(data["root"],data["receipt"],locator=data["locator"],locator_sha256=data["locator_sha256"])
 assert h._root_envelope(data["envelope"],data["locator"],data["jobs"],code_pins=pins,static_root=data["root"],at=data["at"],locator_sha256=data["locator_sha256"])==data["envelope"]
 old=data["envelope"]["root_go"];before=store.canonical(old)
 old_pool=t.pending_recovery(old);new_pool=h.continued_pending_recovery(data["root"],old)
 assert old_pool["handoffs"] and old_pool["pending_reservations"]
 assert new_pool==dict(schema_version=t.PENDING_RECOVERY,handoffs=[],pending_reservations=[])
 assert store.canonical(old)==before
for name,module in tuple(sys.modules.items()):
 if name.startswith("nfl_lab.") and name!="nfl_lab.audit_weekly_grade_history_v1" and getattr(module,"__file__",None):
  assert Path(module.__file__).is_relative_to(main),(name,module.__file__)
print("COLD_MAIN_ROTATION_AND_PENDING_METADATA_OK")
'''
    result=subprocess.run([sys.executable,'-I','-B','-c',script,str(main),str(ROOT/'nfl_lab/audit_weekly_grade_history_v1.py'),str(path)],
        cwd=main,capture_output=True,text=True,timeout=185)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='COLD_MAIN_ROTATION_AND_PENDING_METADATA_OK'


@pytest.mark.parametrize('path', ['nfl_lab/audit_weekly_archive_v1.py','tests/test_audit_weekly_archive_v1.py'])
def test_archive_admission_only_source_change_retains_exact_original_binding(source_metadata,path):
    x=deepcopy(source_metadata)
    body=history.validate_source_history_binding(x.root)
    original=x.root['code_pins'][path]
    x.root['code_pins'][path]='d'*64
    body['pin_overrides'][path]=original
    replace_source_body(x.root,body)
    old=deepcopy(x.original)
    locator_sha=body['predecessor']['locator']['sha256']
    scope=history.source_history_scope(x.root,x.receipt,locator=x.locator,locator_sha256=locator_sha)
    assert scope==old['code_pins']
    assert x.original==old
    assert x.root['code_pins'][path]!=scope[path]
    assert '.github/workflows/lab.yml' not in history.SOURCE_HISTORY_PIN_OVERRIDES
    assert 'nfl_lab/private_draft_store.py' not in history.SOURCE_HISTORY_PIN_OVERRIDES
    assert 'nfl_lab/weekly_future_inference.py' not in history.SOURCE_HISTORY_PIN_OVERRIDES
