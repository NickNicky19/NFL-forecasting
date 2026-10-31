"""Entirely fictional private captures, Actions API and qualified transport."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from contextlib import redirect_stdout
import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nfl_lab import audit_weekly_archive_v1 as a,private_draft_store as s,gha_private_checkpoint as cp
from nfl_lab import audit_private_rotation_v1 as rotation
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_weekly_archive_v1 as cli
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification

ROOT=Path(__file__).resolve().parents[1]
ROLES=dict(produce='fictional_capture_writer',restore='fictional_capture_reader',consume='fictional_capture_exporter')


@pytest.fixture
def capture(tmp_path):
    return capture_case(tmp_path)


def capture_case(tmp_path, *, epoch_document=None, choice_document=None):
    policy=cp.strict_json((ROOT/'config/operational-source-policy-v2.json').read_bytes())
    storage=OperationalStorage(tmp_path/'cache',policy,state=tmp_path/'state');storage.register_root(tmp_path)
    root=tmp_path/'runtime';storage.register_root(root)
    stamp=datetime.now(timezone.utc)
    ts=lambda seconds:(stamp+timedelta(seconds=seconds)).isoformat()
    def put(name,doc):return a.write(storage,tmp_path/name,doc)
    def runtime(name,doc):return a.write(storage,root/name,doc)
    def body(name,raw):storage.write_bytes(tmp_path/name,raw);return cp.binding(tmp_path/name)
    epoch=deepcopy(epoch_document) if epoch_document is not None else {'schema_version':'audit-weekly-correction-epoch-v1','registered_at_utc':ts(-600),'fits':0}
    epoch_ref=put('context/epoch.json',epoch)
    epoch_sha=s.sha(s.canonical(epoch))
    choice=deepcopy(choice_document) if choice_document is not None else {'schema_version':'audit-weekly-correction-epoch-v1-choice','mode':'SOFTWARE_CORRECTION_CONTINUATION','epoch_sha256':epoch_sha,'current_values_used':False}
    choice_ref=runtime('WEEKLY_CHOICE.json',choice);choice_sha=choice_ref['sha256']
    versions=dict(schema_version='audit-weekly-correction-epoch-v1-selected-version-catalog',epoch_sha256=epoch_sha,choice_sha256=choice_sha,rows=[],current_values_used=False)
    version_ref=runtime('SELECTED_VERSION_CATALOG.json',versions)
    recipe_ref=runtime('RUNTIME_RECIPE.json',dict(schema_version=a.RUNTIME+'-recipe',fits=0))
    artifact_ref=runtime('ARTIFACT_CATALOG.json',dict(schema_version='fictional-artifact-catalog',epoch_sha256=epoch_sha))
    bridge_ref=runtime('IDENTITY_BRIDGE.json',dict(schema_version=a.RUNTIME+'-identity',identities=[],name_matching=False))
    for name in ('CONSUMED.json','POPULATION.json','MODEL_ATTEMPTS.json'):runtime(name,dict(schema_version=a.RUNTIME,fits=0))
    columns=dict(season=[2026],week=[7],game_id=['fictional-future'],player_id=['00-0000001'],position=['QB'],
        cutoff_utc=[ts(3600)],kickoff_utc=[ts(7200)],feature_max_source_available_utc=[ts(-86400)],f_fixture=[0.])
    for name in ('features.parquet','queries.parquet','quarantine.parquet','no_remaining_game.parquet'):
        stream=io.BytesIO();pq.write_table(pa.table(columns),stream)
        storage.write_bytes(root/name,stream.getvalue())
    feature_ref=cp.binding(root/'features.parquet')
    feature_capture=runtime('features.capture.json',dict(schema_version='weekly-feature-capture-v1',source_contract={'source_policy_sha256':cp.POLICY_SHA},
        feature_binding=feature_ref,feature_persist_completed_at=ts(-40)))
    slots=[]
    for target,family,method in cp.JOBS:
        row=dict(offered_id=s.sha(s.canonical([target,'fictional-player'])),category=target,method_id=method,attempt_qualified=True,
            evidence_lane='original_pregame',scientific_qualification=False,source_capture_completed_at=ts(-40),issued_at=ts(-30),cutoff_utc=ts(3600),kickoff_utc=ts(7200),
            forecast_value=0.,operational_eligible=True)
        name=f'candidates/{target}/{method}.jsonl.gz';raw=gzip.compress(s.canonical(row)+b'\n',mtime=0)
        storage.write_bytes(root/name,raw);ref=cp.binding(root/name)
        completion=dict(state='PERSISTED',rows=1,binding=ref,persist_started_at=ts(-29.5),completed_at=ts(-29))
        runtime(f'candidates/{target}/{method}.jsonl.completion.json',completion)
        status=dict(target=target,method_id=method,state='CAPTURED',failure=None,attempt_qualified=True,expected_rows=1,issued_rows=1,
            unissued_offered_ids=[],persistence=completion)
        runtime(f'model-status/{target}-{method}.json',status);slots.append(status)
    candidates=runtime('CANDIDATES.json',dict(slots=slots,schema_version=a.RUNTIME+'-candidates'))
    selected_row=dict(offered_id='fictional-selected',category='pass_att',method_id='P2_SELECTED',forecast_value=0.,operational_eligible=True,
        evidence_lane='original_pregame',scientific_qualification=False,source_capture_completed_at=ts(-40),issued_at=ts(-20),cutoff_utc=ts(3600),kickoff_utc=ts(7200))
    storage.write_bytes(root/'selected.jsonl.gz',gzip.compress(s.canonical(selected_row)+b'\n',mtime=0))
    selected_ref=cp.binding(root/'selected.jsonl.gz')
    selected_completion=dict(state='PERSISTED',rows=1,binding=selected_ref,persist_started_at=ts(-19.5),completed_at=ts(-19))
    selected_completion_ref=runtime('selected.jsonl.completion.json',selected_completion)
    prepared_refs=dict(recipe=put('prepared/RUNTIME_RECIPE.json',{'fictional':True}),choice=put('prepared/WEEKLY_CHOICE.json',choice),
        artifact_catalog=put('prepared/ARTIFACT_CATALOG.json',{}),selected_versions=put('prepared/SELECTED_VERSION_CATALOG.json',versions),
        relocated_replay=put('prepared/RELOCATED_REPLAY_CATALOG.json',{}))
    completion=put('prepared/CHOICE_COMPLETION.json',dict(metadata_remote_durability_qualified=False,persisted_completed_at=ts(-100)))
    prepared=put('prepared/PREPARED.json',dict(schema_version=a.RUNTIME+'-prepared',refs=prepared_refs,choice_completion=completion,current_values_used=False))
    namespace=tmp_path/'qualified-source';storage.register_root(namespace)
    source_manifest=put('qualified-source/source-manifest.json',{'fictional_capture_manifest':True})
    subset_manifest=put('qualified-source/subset-manifest.json',{'allowed_periods':{'2026':[1,2,3,4,5]}})
    transient_ref=body('transient/schedules.csv',b'FICTIONAL_HTTP_BODY_NEVER_ARCHIVED')
    receipt=dict(name='schedules.csv',url='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
        sha256=transient_ref['sha256'],bytes=transient_ref['bytes'],status='acquired',retrieved_utc=ts(-65))
    source=put('source/SOURCE_FINISHED.json',dict(schema_version=a.RUNTIME+'-source',prepared=prepared,
        namespace=str(namespace),bindings={source_manifest['path']:source_manifest['sha256'],subset_manifest['path']:subset_manifest['sha256']},
        raw={'schedules.csv':transient_ref},manifest={'source_receipts':{'schedules.csv':receipt}},actual_source_started_at=ts(-70),actual_completed_at=ts(-60)))
    terminal=runtime('FINISHED.json',dict(schema_version=a.RUNTIME+'-result',state='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE',fits=0,searches=0,scores=0,
        public_release=False,public_export_authorized=False,epoch_sha256=epoch_sha,choice_sha256=choice_sha,actual_completed_at=ts(-10),
        prediction_rows=18,query_rows=1,selected=selected_completion))
    runtime('EXPORT_INPUTS.json',dict(schema_version=a.RUNTIME+'-private-handoff',terminal=terminal,selected=selected_ref,completion=selected_completion_ref,
        identity_bridge=bridge_ref,recipe=recipe_ref,choice=choice_ref,artifact_catalog=artifact_ref,selected_version_catalog=version_ref,
        public_export_authorized=False,prepared=prepared,source=source,candidates=candidates))
    context=dict(epoch=epoch_ref,epoch_registration=put('context/epoch_registration.json',dict(epoch_sha256=epoch_sha)),
        original_choice=put('context/original_choice.json',{'original_immutable_choice':True}),
        origin_witness=put('context/origin_witness.json',dict(kind='DERIVED_SOURCE_BOUND_TERMINAL_WITNESS',original_completion_file_retained=False)),
        original_slate=put('context/original_slate.json',{}),original_catalog=put('context/original_catalog.json',{}),
        original_policy=put('context/original_policy.json',{}),retained_models=put('context/retained_models.json',{'separately_qualified38':True}),prepared=prepared,source=source)
    return SimpleNamespace(storage=storage,root=root,base=tmp_path,context=context,put=put,body=body,slots=slots,
        feature=feature_ref,transient=transient_ref,stamp=stamp)


class Service:
    def __init__(self,path, *, qualification_at=None):
        self.server=Server();self.calls=[];self.active='produce';self.bad_writer=False;self.bad_qualifier=False
        self.started=datetime.now(timezone.utc)-timedelta(minutes=10)
        self.writer_completed=None;self.reader_completed=None
        journal=path/'initialize';journal.mkdir(mode=0o700)
        self.qrun='40000000001'
        initial=s.Client('ghs_FICTIONAL',self.qrun,journal=journal,source_sha=SOURCE,transport=self.server,process='e'*64)
        self.binding=s.initialize(initial,'c'*32)
        if qualification_at is None:
            self.q=qualification(self.binding)
        else:
            # A frozen grading service must create its NEW fictional canary
            # proofs at that same synthetic clock, not the host wall clock.
            class QualificationClock(datetime):
                @classmethod
                def now(cls,tz=None):
                    return qualification_at if tz else qualification_at.replace(tzinfo=None)
            from unittest.mock import patch as qualification_patch
            with qualification_patch('test_owner_private_bootstrap.datetime',QualificationClock):
                self.q=qualification(self.binding)
        before,read,q=self.q['before_proof'],self.q['read_proof'],self.q
        for p,k in zip((before,read,q),('write','read','qualify')):p['job']['job_id']=rotation.JOBS[k]
        read['before_sha256']=s.sha(s.canonical(before));q['before_sha256']=read['before_sha256'];q['read_sha256']=s.sha(s.canonical(read))
        self.census=dict(reservations=[])
        quota=dict(schema_version=rotation.VERSION+'-quota-reservation',global_cap_bytes=512 << 20,new_runtime_reserved_bytes=32 << 20,
            new_runtime_id=self.binding['runtime_id'],old_assets_deleted=0,metadata_only=True,reserved_before_bytes=32 << 20,reserved_after_bytes=64 << 20,
            existing_draft_runtimes=1,pending_unlocated_runtimes=0,pending_records=0,charged_existing_bytes=117,charged_existing_assets=1,
            inventory_sha256='a'*64,pending_census_sha256=s.sha(s.canonical(self.census)))
        self.package=dict(schema_version=rotation.VERSION+'-qualified-runtime',runtime_reserved_bytes=32 << 20,runtime_id=self.binding['runtime_id'],
            binding=self.binding,qualification=self.q,quota_reservation=quota,run_id=self.qrun,source_sha=SOURCE)

    def transport(self,request,timeout):
        self.calls.append(request);url=request.full_url
        if '/actions/runs/' in url:
            rid=url.split('/runs/',1)[1].split('/',1)[0]
            if '/jobs?' not in url:
                return Response(dict(id=int(rid),head_sha=SOURCE,event='workflow_dispatch',run_attempt=1,status='in_progress',path='.github/workflows/lab.yml',
                    head_branch='fictional',actor=dict(login='NickNicky19',id=208912933),repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO)))
            if rid==self.qrun:
                return Response(dict(total_count=3,jobs=[dict(id=p['job']['api_job_id'],name=p['job']['job_id'],head_sha=SOURCE,run_id=int(rid),
                    status='completed',conclusion='failure' if self.bad_qualifier else 'success',started_at=p['started_at_utc'],completed_at=p['created_at_utc'])
                    for p in (self.q['before_proof'],self.q['read_proof'],self.q)]))
            jobs=[]
            for i,role in enumerate(('produce','restore','consume')):
                if i>list(ROLES).index(self.active):break
                complete=role!=self.active
                ended=self.writer_completed if role=='produce' else self.reader_completed
                jobs.append(dict(id=777+i,name=ROLES[role],run_id=int(RUN),head_sha=SOURCE,status='completed' if complete else 'in_progress',
                    conclusion='failure' if role=='produce' and self.bad_writer else 'success',started_at=self.started.isoformat(),
                    completed_at=(ended or datetime.now(timezone.utc)).isoformat()))
            return Response(dict(total_count=len(jobs),jobs=jobs))
        return self.server(request,timeout)

    def factory(self,journal,role):
        journal.mkdir(mode=0o700);service=self
        class Factory:
            def __init__(self):self.clients=[]
            def __call__(self,operation):
                assert len(self.clients)<10
                job=dict(execution_lane='github_actions',workflow_ref=s.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',workflow_sha=SOURCE,
                    job_id=ROLES[role],permission='write',event_name='workflow_dispatch',api_job_id=0,run_authenticated=False)
                c=a.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,transport=service.transport,job=job,operation=operation,
                    qualification=service.q,readonly=role=='consume',process=s.sha(('FICTIONAL-'+role).encode()))
                c.bind(service.binding);self.clients.append(c);return c
        return Factory()

    def posts(self):return [c for c in self.calls if c.method=='POST']


def produce(p,service,*,label='producer',snapshot=None):
    snapshot=snapshot or a.collect(p.root,p.context,storage=p.storage,output=p.base/(label+'-collection'))
    factory=service.factory(p.base/(label+'-journal'),'produce')
    handoff=a.produce(snapshot,factory,service.package,storage=p.storage,output=p.base/label,root_go_sha256='d'*64,
        jobs=ROLES,pending_census=service.census)
    service.writer_completed=datetime.now(timezone.utc)
    return handoff,factory,snapshot


def test_complete_producer_reader_exporter_preserves_all18_exact_bytes_and_clocks(capture):
    p=capture;service=Service(p.base)
    handoff,writer,snapshot=produce(p,service)
    assert handoff['archive_state']=='COMPLETE_CAPTURE'
    assert len(a.safe_handoff(handoff))<=16384
    assert not any(f['kind'] in {'model','source_raw','model_manifest'} for f in snapshot['files'])
    service.active='restore'
    reader=service.factory(p.base/'reader-journal','restore')
    result=a.restore(handoff,reader,service.package,storage=p.storage,output=p.base/'reader',root_go_sha256='d'*64,pending_census=service.census)
    assert result['state']=='PRIVATE_CAPTURE_RESTORED' and result['replay_ready'] is True
    assert result['scope_qualified_for_publication'] is result['public_export_authorized'] is result['model_replay_performed'] is False
    for original in snapshot['files']:
        restored=result['aliases'][original['logical_path']]
        assert Path(restored['path']).read_bytes()==Path(original['path']).read_bytes()
        p.storage.validate_reference(restored['path'],original['sha256'])
    assert result['validation']['candidate_rows']==18 and result['validation']['selected_rows']==1
    assert p.transient['sha256'] not in {f['sha256'] for f in snapshot['files']}
    assert not (p.base/'reader/EXPORT_INPUTS.json').exists()
    reader_handoff=cp.strict_json((p.base/'reader/READER_HANDOFF.json').read_bytes())
    service.reader_completed=datetime.now(timezone.utc);service.active='consume'
    before=len(service.posts());exporter=service.factory(p.base/'export-journal','consume')
    consumed=a.consume(reader_handoff,exporter,service.package,storage=p.storage,output=p.base/'export',root_go_sha256='d'*64,pending_census=service.census)
    assert consumed['state']=='PRIVATE_CAPTURE_EXPORT_INPUTS_VERIFIED'
    assert len(service.posts())==before
    exported=cp.strict_json((p.base/'export/EXPORT_INPUTS.json').read_bytes())
    assert exported['public_export_authorized'] is exported['scope_qualified_for_publication'] is False
    assert exported['producer_proof']['identity']==handoff['producer']
    assert exported['restorer_proof']['restorer']!=exported['exporter']
    assert all(c.calls<=40 for f in (writer,reader,exporter) for c in f.clients)


def test_partial_archive_restores_available_forecasts_from_failed_job_but_never_exports(capture):
    p=capture;service=Service(p.base)
    # Preserve actual failure bytes; no synthetic successful completion.
    terminal=p.root/'FINISHED.json'
    doc=cp.strict_json(terminal.read_bytes());doc['state']='PARTIAL_RETAINED_NOT_QUALIFIED'
    # New fixture namespace instead of modifying an immutable owned original.
    partial=p.base/'partial-runtime';p.storage.register_root(partial)
    for path in p.root.rglob('*'):
        if path.is_file() and path.name!='.operational-storage-owner' and path.name!='EXPORT_INPUTS.json':
            dest=partial/path.relative_to(p.root)
            if path==terminal:p.storage.write_bytes(dest,s.canonical(doc))
            else:p.storage.import_file(path,dest,expected_sha256=cp.binding(path)['sha256'])
    snapshot=a.collect(partial,p.context,storage=p.storage,output=p.base/'failure-collection')
    assert snapshot['census']['archive_state']=='FAILURE_EVIDENCE'
    handoff,_,_=produce(p,service,snapshot=snapshot)
    service.bad_writer=True;service.active='restore'
    result=a.restore(handoff,service.factory(p.base/'reader-journal','restore'),service.package,storage=p.storage,
        output=p.base/'reader',root_go_sha256='d'*64,pending_census=service.census)
    assert result['state']=='PRIVATE_FAILURE_ARCHIVE_RESTORED' and result['replay_ready'] is False
    assert not (p.base/'reader/EXPORT_INPUTS.json').exists()
    assert len([n for n in result['aliases'] if n.startswith('runtime/candidates/') and n.endswith('.jsonl.gz')])==18


def test_quota_reserves_all_groups_index_witness_and_failure_before_any_POST(capture):
    p=capture;service=Service(p.base)
    for i in range(4):service.server.add('fictional-orphan-'+str(i),size=7 << 20)
    with pytest.raises(s.StoreError,match='QUOTA_BEFORE_POST'):produce(p,service)
    assert not service.posts()


def test_corrupt_index_size_preflight_and_encoder_failure_never_POST(capture,monkeypatch):
    p=capture;service=Service(p.base)
    monkeypatch.setattr(a,'INDEX_PLAIN_CAP',512)
    with pytest.raises(s.StoreError,match='INDEX_PREFLIGHT'):produce(p,service)
    assert not service.posts()


def test_ambiguous_POST_retains_reservation_and_original_attempt_no_retry(capture):
    p=capture;service=Service(p.base);service.server.ambiguous=True
    with pytest.raises(s.StoreError,match='TRANSPORT_FAILURE_NO_RETRY'):produce(p,service)
    assert len(service.posts())==1
    assert list((p.base/'producer-journal').glob('*.reservation.json'))
    assert not (p.base/'producer/APPENDED.json').exists()
    calls=len(service.calls)
    with pytest.raises(s.StoreError,match='NO_RETRY'):
        a.produce({'files':[],'census':{}},None,None,storage=p.storage,output=p.base/'producer',root_go_sha256='d'*64,jobs=ROLES,pending_census={})
    assert len(service.calls)==calls


def test_unqualified_rotation_stops_before_POST(capture):
    p=capture;service=Service(p.base);service.bad_qualifier=True
    with pytest.raises(s.StoreError,match='ROTATION_JOB_PROOF'):produce(p,service)
    assert not service.posts()


def test_complete_archive_requires_successful_original_producer(capture):
    p=capture;service=Service(p.base);handoff,_,_=produce(p,service)
    service.active='restore';service.bad_writer=True
    before=len(service.calls)
    with pytest.raises(s.StoreError,match='SUCCESSFUL_ARCHIVE_PREDECESSOR'):
        a.restore(handoff,service.factory(p.base/'reader-journal','restore'),service.package,storage=p.storage,
            output=p.base/'reader',root_go_sha256='d'*64,pending_census=service.census)
    assert not any(r.get_header('Accept')=='application/octet-stream' and '/releases/assets/' in r.full_url
        and not r.full_url.endswith('/'+str(service.binding['canary_asset_id'])) for r in service.calls[before:])


def test_unapproved_template_and_no_execute_read_no_context(tmp_path):
    class NoEnv:
        def get(self,*unused):raise AssertionError('credential discovery')
    with redirect_stdout(io.StringIO()):
        assert cli.main(['restore'],environ=NoEnv())==2
        assert cli.main(['template','--output',str(tmp_path/'request.json')],environ=NoEnv())==0
    doc=cp.strict_json((tmp_path/'request.json').read_bytes())
    assert doc['approved'] is False and doc['limits']==a.LIMITS


def test_supplied_original_R0_native_cache_zero_bytes_and_duplicate_roles_are_complete(capture):
    p=capture;service=Service(p.base)
    native=p.body('r0/native.json.gz',gzip.compress(b'{"fictional_original_native":true}',mtime=0))
    board=p.put('r0/output/data/week.json',{'fictional_original_board':True})
    cache=p.put('r0/data/cache/fixture.json',{'fictional_original_cache':True})
    empty=p.body('r0/data/cache/empty.json',b'')
    state=p.put('r0/state.json',dict(files={'output/data/week.json':board,'data/cache/fixture.json':cache,'data/cache/empty.json':empty}))
    ts=lambda seconds:(p.stamp+timedelta(seconds=seconds)).isoformat()
    prepared=p.put('r0/prepared.json',{'current_values_used':False,'slate':{'game_cutoffs':{'fictional':ts(3600)}}})
    controls=p.put('r0/controls.json',{'rows':[],'actual_issued_at':ts(-13)})
    observations=p.put('r0/observation.json',dict(status=200,sha256='a'*64,completed_at=ts(-17)))
    worker=dict(state='ORIGINAL_R0_DEFAULT_PROCEDURE_CAPTURED',native=native,next_state=state,source_observations=[observations],
        actual_source_completed_at=ts(-16),actual_native_observed_at=ts(-15),actual_native_persist_completed_at=ts(-14))
    p.put('r0/WORKER_COMPLETE.json',worker)
    completion=p.put('r0/completion.json',dict(schema_version='audit-reference-capture-v1-control-completion',forecast_binding=controls,
        source_receipt_sha256=s.sha(s.canonical(worker)),original_native_persist_completed_at=ts(-14),actual_issued_at=ts(-13),
        body_persist_completed_at=ts(-12),remote_durability_qualified=False,public_release=False))
    reference=p.put('r0/CAPTURE_COMPLETE.json',dict(schema_version='audit-reference-capture-v1-capture',state='ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE',
        prepared=prepared,native=native,original_board=board,next_state=state,control_forecast_rows=controls,control_completion=completion))
    snapshot=a.collect(p.root,p.context,storage=p.storage,output=p.base/'r0-collection',r0=reference)
    assert snapshot['census']['r0_provided'] is True
    zero=next(f for f in snapshot['files'] if f['logical_path']=='r0/cache/data/cache/empty.json')
    assert zero['bytes']==0 and zero['sha256']==s.sha(b'')
    handoff,_,_=produce(p,service,snapshot=snapshot)
    service.active='restore'
    result=a.restore(handoff,service.factory(p.base/'reader-journal','restore'),service.package,storage=p.storage,
        output=p.base/'reader',root_go_sha256='d'*64,pending_census=service.census)
    assert Path(result['aliases']['r0/original-native.json.gz']['path']).read_bytes()==Path(native['path']).read_bytes()
    assert Path(result['aliases']['r0/cache/data/cache/empty.json']['path']).read_bytes()==b''
    assert Path(result['aliases']['r0/cache/output/data/week.json']['path']).read_bytes()==Path(board['path']).read_bytes()
    assert 'r0/source-observations/000.json' in result['aliases']
    assert Path(result['aliases']['r0/control_completion.json']['path']).read_bytes()==Path(completion['path']).read_bytes()


def test_corrupt_group_retains_failed_readback_and_emits_no_witness_or_success(capture):
    p=capture;service=Service(p.base);handoff,_,_=produce(p,service)
    index_id=handoff['index_descriptor']['entry']['payload_asset_id']
    index=a.unpack(next(v['body'] for v in service.server.assets if v['id']==index_id),a.INDEX_PLAIN_CAP)
    group_id=index['groups'][0]['descriptor']['entry']['payload_asset_id']
    next(v for v in service.server.assets if v['id']==group_id)['body']+=b'FICTIONAL_CORRUPTION'
    service.active='restore';before=len(service.posts())
    with pytest.raises(s.StoreError,match='READBACK_MISMATCH'):
        a.restore(handoff,service.factory(p.base/'reader-journal','restore'),service.package,storage=p.storage,
            output=p.base/'reader',root_go_sha256='d'*64,pending_census=service.census)
    assert len(service.posts())==before
    assert not (p.base/'reader/RESTORED.json').exists() and not (p.base/'reader/READER_HANDOFF.json').exists()
    assert (p.base/'reader/owned-downloads/index.gz').exists()


def test_interrupted_complete_preencoding_does_not_start_POST(capture,monkeypatch):
    p=capture;service=Service(p.base)
    def interrupt(*unused):raise s.StoreError('FICTIONAL_PREENCODE_INTERRUPTION')
    monkeypatch.setattr(a.codec,'encode',interrupt)
    with pytest.raises(s.StoreError,match='PREENCODE_INTERRUPTION'):produce(p,service)
    assert not service.posts()
    assert (p.base/'producer/CONSUMED.json').exists()


def test_native_archive_child_rejects_local_context_before_private_input(tmp_path):
    import os
    import subprocess
    import sys
    env={k:v for k,v in os.environ.items() if not k.startswith(('GITHUB_','AUDIT_WEEKLY_'))}
    result=subprocess.run([sys.executable,'-I','-B',str(ROOT/'tools/audit_weekly_archive_v1.py'),'restore','--execute',
        '--request',str(tmp_path/'NONEXISTENT_PRIVATE_REQUEST'),'--request-sha256','a'*64],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==1,result.stderr
    assert cp.strict_json(result.stdout)['reason']=='GENUINE_OWNER_ARCHIVE_ACTIONS_REQUIRED'
    assert result.stderr==''


def test_complete_codec_and_feature_context_fit_original_native_512MiB_guard(capture):
    import os
    import subprocess
    import sys
    p=capture
    snapshot=a.collect(p.root,p.context,storage=p.storage,output=p.base/'native-collection')
    manifest=p.put('native-fixture.json',snapshot)
    code='''
import json,sys,signal
from pathlib import Path
from tools.private_draft_store_v2 import limits
from nfl_lab import audit_weekly_archive_v1 as a
limits()
assert signal.getsignal(signal.SIGALRM)==signal.SIG_DFL
assert signal.getitimer(signal.ITIMER_REAL)[0]>0
snapshot=json.loads(Path(sys.argv[1]).read_bytes())
paths={f['logical_path']:Path(f['path']) for f in snapshot['files']}
result=a.validate_capture(snapshot,paths.__getitem__,complete=True)
for group in a.codec.groups([f for f in snapshot['files'] if f['bytes']]):
    encoded,size=a.codec.encode(group)
    a.codec.verify_bundle(encoded,dict(bytes=len(encoded),sha256=a.store.sha(encoded),inflated_bytes=size,files=group))
assert result['qualified_selected'] is True
print('FICTIONAL_NATIVE_ARCHIVE_CONTEXT_AND_CODEC_PASSED')
'''
    numerical=cp.strict_json((ROOT/'config/weekly-owner-private-bootstrap-v1.json').read_bytes())['numerical_environment']
    result=subprocess.run([sys.executable,'-B','-c',code,manifest['path']],cwd=ROOT,env={**os.environ,**numerical},capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='FICTIONAL_NATIVE_ARCHIVE_CONTEXT_AND_CODEC_PASSED'


@pytest.mark.parametrize('planning',[False,True])
def test_literal_original_five_operational_roles_pass_context_admission(tmp_path,monkeypatch,planning):
    original={'ops_population','ops_roles','ops_schedule','canonical_weekly_choice','capture_scope'}
    assert a.OPERATIONS_CONTEXT==original
    roles=a.CONTEXT|original|({'ops_planning'} if planning else set())
    context={role:dict(path=str(tmp_path/(role+'.json')),bytes=1,sha256='a'*64) for role in roles}
    class ReachedFilesystem(Exception):pass
    monkeypatch.setattr(a,'fresh',lambda *_a,**_k:(_ for _ in ()).throw(ReachedFilesystem()))
    with pytest.raises(ReachedFilesystem):
        a.collect(tmp_path,context,storage=object(),output=tmp_path/'not-created')
    assert not (tmp_path/'not-created').exists()
    del context['ops_schedule']
    with pytest.raises(s.StoreError,match='COMPLETE_OPERATIONAL_PREVALUE_CONTEXT_REQUIRED'):
        a.collect(tmp_path,context,storage=object(),output=tmp_path/'still-not-created')


@pytest.mark.parametrize('byte_delta,slot_delta', [(0,0),(1,0),(0,1)])
def test_rejected_or_exact_admission_keeps_full_reservation_breakdown(capture, byte_delta, slot_delta):
    """Real codec/inventory/journals; fictional server capacity, no HTTP."""
    p=capture;service=Service(p.base)
    snapshot=a.collect(p.root,p.context,storage=p.storage,output=p.base/'capacity-collection')
    groups=a.capture_groups(snapshot['files'])
    encoded=sum(len(a.codec.encode(g)[0]) for g in groups)
    needed=encoded+a.INDEX_CAP+(len(groups)+2)*a.ENTRY_CAP+a.WITNESS_CAP+a.FAILURE_RESERVE
    slots=2*(len(groups)+1)+4
    target_bytes=s.TOTAL_CAP-needed+byte_delta
    # Metadata-only capacity controls. They are never used as fixture reports,
    # downloadable original evidence, model bytes or a hosted qualification.
    remaining=target_bytes-sum(x['size'] for x in service.server.assets)
    while remaining:
        n=min(remaining,s.ASSET_CAP)
        service.server.add('fictional-capacity-'+str(len(service.server.assets)),b'',size=n)
        remaining-=n
    target_slots=s.MAX_ASSETS-slots+slot_delta
    while len(service.server.assets)<target_slots:
        service.server.add('fictional-slot-'+str(len(service.server.assets)),b'')
    factory=service.factory(p.base/'quota-journal','produce')
    before_posts=len(service.posts())
    args=dict(storage=p.storage,output=p.base/'quota-archive',root_go_sha256='d'*64,
        jobs=ROLES,pending_census=service.census)
    if byte_delta or slot_delta:
        with pytest.raises(s.StoreError,match='FULL_ARCHIVE_INDEX_WITNESS_FAILURE_QUOTA_BEFORE_POST'):
            a.produce(snapshot,factory,service.package,**args)
        assert len(service.posts())==before_posts
    else:
        result=a.produce(snapshot,factory,service.package,**args)
        assert result['archive_state']=='COMPLETE_CAPTURE'
    admission=cp.strict_json((p.base/'quota-archive/ADMISSION.json').read_bytes())
    details=cp.strict_json((p.base/'quota-archive/ADMISSION_DETAILS.json').read_bytes())
    assert admission['admitted_bytes']==s.TOTAL_CAP+byte_delta
    assert admission['existing_slots']+admission['reserved_slots']==s.MAX_ASSETS+slot_delta
    assert details['capacity']['actual_stored_bytes']==target_bytes
    assert details['capacity']['pending_bytes']==details['capacity']['pending_asset_slots']==0
    assert details['encoded_group_bytes']==encoded
    assert len(details['encoded_groups'])==len(groups)
    assert details['required_bytes']==needed and details['required_slots']==slots
    assert details['byte_shortfall']==byte_delta and details['slot_shortfall']==slot_delta
    assert details['failure_package_bytes']+details['failure_manifest_bytes']==a.FAILURE_RESERVE
    assert details['group_manifest_bytes']==(len(groups)+1)*a.ENTRY_CAP
    assert details['remote_POST_attempted'] is details['limits_changed'] is details['original_evidence_deleted'] is False
    if not byte_delta and not slot_delta:
        actual=cp.strict_json((p.base/'quota-archive/SERIALIZED_ADMISSION_DETAILS.json').read_bytes())
        assert 0<actual['index_encoded_bytes']<=a.INDEX_CAP
        assert 0<actual['index_plain_bytes']<=a.INDEX_PLAIN_CAP-4096
        # This correction adds local evidence; it does not change index keys.
        index_asset=next(x for x in service.server.assets if x['id']==result['index_descriptor']['entry']['payload_asset_id'])
        index=a.unpack(index_asset['body'],a.INDEX_PLAIN_CAP)
        assert set(index)==a.INDEX_KEYS
        assert index['admission']==admission


def test_capacity_freshly_counts_pending_and_matched_intents_without_refund(capture):
    p=capture;service=Service(p.base)
    factory=service.factory(p.base/'capacity-journal','produce')
    client=factory('append')
    actual=service.server.assets[0]
    client.reserve('asset:'+actual['name'],actual['body'],name=actual['name'])
    body=b'FICTIONAL_UNRESOLVED_POST'
    client.reserve('asset:blob-'+s.sha(body)+'.bin',body,name='blob-'+s.sha(body)+'.bin')
    before={x.name:x.read_bytes() for x in client.journal.glob('*.reservation.json')}
    details=a.capacity_snapshot(client)
    assert details['actual_stored_bytes']==117
    assert details['pending_bytes']==len(body) and details['pending_asset_slots']==1
    assert details['charged_existing_bytes']==117+len(body) and details['charged_existing_slots']==2
    assert len(details['reservations'])==2
    assert sum(x['charged_pending'] for x in details['reservations'])==1
    assert {x.name:x.read_bytes() for x in client.journal.glob('*.reservation.json')}==before
    # Same pathname and size with a different digest must remain charged.
    service.server.assets.append(dict(id=999,name='blob-'+s.sha(body)+'.bin',size=len(body),state='uploaded',
        digest='sha256:'+'0'*64,url=s.API+'/releases/assets/999',body=b'X'*len(body)))
    again=a.capacity_snapshot(client)
    assert again['pending_bytes']==len(body) and again['pending_asset_slots']==1


def test_frozen_grading_service_qualification_uses_its_own_test_clock(tmp_path):
    at=datetime(2026,10,28,8,1,tzinfo=timezone.utc)
    service=Service(tmp_path,qualification_at=at)
    for proof in (service.q['before_proof'],service.q['read_proof'],service.q):
        assert s.utc(proof['started_at_utc'])<=s.utc(proof['created_at_utc'])<at
    assert s.utc(service.q['created_at_utc'])==at-timedelta(minutes=25,seconds=30)
