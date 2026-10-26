"""Fictional E7 transport/metadata; real CAS, query/row/selector composition.

Numerical prediction and history acquisition are injected. No NFL private body,
real transport, estimator fit, outcome or protected confirmation is read.
"""
from copy import deepcopy
from datetime import timedelta
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nfl_lab import audit_weekly_runtime_v1 as r, audit_weekly_epoch_v1 as epoch
from nfl_lab import weekly_future_inference as future, operational_sources as sources
from nfl_lab import private_draft_store as private, audit_count_retained_v1 as retained
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.state import canonical, digest, utc
from tools import audit_weekly_runtime_v1 as cli
from test_audit_weekly_epoch_v1 import fixture, prepare, registered, continuation, CONTINUED

ROOT=Path(__file__).resolve().parents[1]
REGISTERED_BUILDER_SHA = "0c79adea3eb0feb9c5f634f48e546578ed3632e4d20dfdd05dc323c523dafc3c"
REGISTERED_SOURCE_CONTRACT = dict(
    source_policy_sha256="e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441",
    availability_rule="FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION", feature_builder_sha256=REGISTERED_BUILDER_SHA)


def test_registered_original_builder_new_monday_query_features_and_owned_capture(tmp_path,monkeypatch):
    """Fictional new queries, actual builder and literal retained contract.

    No frozen feature replay, model, provider or real outcome is used. This
    deliberately cannot update its expected builder hash from current code.
    """
    from nfl_lab import features,weekly_current_query as query
    monkeypatch.setattr("socket.socket.connect",lambda *_:pytest.fail("NO_REAL_NETWORK"))
    policy=sources.load_source_policy(ROOT/'config/operational-source-policy-v2.json')
    schedule=pd.DataFrame([
        dict(game_id='fictional-sunday',season=2026,week=7,game_type='REG',gameday='2026-10-25',
            gametime='16:00',away_team='C',home_team='D'),
        dict(game_id='fictional-monday',season=2026,week=7,game_type='REG',gameday='2026-10-26',
            gametime='16:00',away_team='A',home_team='B')])
    roster=pd.DataFrame([dict(season=2026,week=7,game_type='REG',team=team,gsis_id=player,
        sleeper_id=str(101+i),position=position,status='ACT',full_name='Fictional')
        for i,(team,player,position) in enumerate([('A','00-0000001','QB'),('B','00-0000002','RB')])])
    packet=query.build_current_queries(roster,schedule,season=2026,week=7,
        cutoff_utc=utc('2026-10-26T07:00:00Z'),expected_remaining_games=1)
    packet['queries']['cutoff_utc']=packet['queries'].game_id.map(
        {'fictional-monday':'2026-10-26T19:00:00Z'}).map(utc)
    history=pd.DataFrame([dict(player_id=player,game_id='fictional-old',team=team,opponent=opponent,
        position=position,season=2020,week=1,kickoff_utc=pd.Timestamp('2020-09-10T20:00:00Z'),
        participation_state='played',**{name:amount for name in features.PLAYER_STATS})
        for player,team,opponent,position,amount in [
            ('00-0000001','A','B','QB',2.0),('00-0000002','B','A','RB',0.0)]])
    # Model the qualified loader's private Parquet round trip in memory. The
    # hand-authored rows are fictional prior observations, never real labels.
    stream=io.BytesIO();history.to_parquet(stream,index=False)
    loaded=pd.read_parquet(io.BytesIO(stream.getvalue()))
    loaded.attrs['operational_manifest']=dict(policy_sha256=policy['_policy_sha256'],code_sha256s=sources._code_hashes(),
        history_frame_sha256=sources._frame_sha(history),asof_utc='2026-10-26T07:00:00Z',
        source_receipts={'fictional':dict(retrieved_utc='2026-10-26T06:59:00Z')})
    contract=deepcopy(REGISTERED_SOURCE_CONTRACT)
    frame=query.build_shared_features(loaded,packet,policy=policy,source_contract=contract)
    assert contract==REGISTERED_SOURCE_CONTRACT
    assert frame.game_id.tolist()==['fictional-monday']*2
    assert frame.player_id.tolist()==['00-0000001','00-0000002']
    assert frame.f_player_rec_mean3.tolist()==[2.0,0.0]
    assert frame.f_player_games_prior.tolist()==[1.0,1.0]
    assert frame.participation_state.eq('unknown').all() and frame.f_player_play_rate8.isna().all()
    owner=OperationalStorage(tmp_path/'cache',policy,state=tmp_path/'state');owner.register_root(tmp_path/'capture')
    source=tmp_path/'capture/fictional-source-metadata';owner.write_bytes(source,b'FICTIONAL_SOURCE_NOT_NFL_ROWS')
    feature_ref,receipt_ref=future.persist_feature_capture(tmp_path/'capture/features.parquet',frame,
        features=[name for name in frame if name.startswith('f_')],source_contract=contract,
        source_bindings=[future.binding(source)],storage=owner,clock=lambda:utc('2026-10-26T07:00:00Z'))
    capture=r.read_owned(owner,receipt_ref)
    assert capture['source_contract']==REGISTERED_SOURCE_CONTRACT
    assert capture['feature_binding']==feature_ref and capture['query_projection_sha256']==future.frame_digest(
        future.query_projection(frame,[name for name in frame if name.startswith('f_')]))
    assert capture['historical_availability_rule']=='FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION'


@pytest.mark.parametrize('wrong_hash',['0'*64,'069c498ebef85fee291f7f9913bebc6d157988d2242de5feb6b066d6ba68e11e'])
def test_registered_original_builder_guard_rejects_other_source_before_frames(monkeypatch,wrong_hash):
    assert future.sha(ROOT/'nfl_lab/operational_sources.py')==REGISTERED_BUILDER_SHA
    policy=sources.load_source_policy(ROOT/'config/operational-source-policy-v2.json')
    monkeypatch.setattr(sources,'build_operational_features',lambda *_a,**_k:pytest.fail('BUILDER_BEFORE_ORIGINAL_HASH'))
    changed=dict(REGISTERED_SOURCE_CONTRACT,feature_builder_sha256=wrong_hash)
    with pytest.raises(ValueError,match='feature builder identity changed'):
        future.build_future_features(None,None,policy=policy,source_contract=changed)
    actual=future.sha
    monkeypatch.setattr(future,'sha',lambda path:'0'*64 if Path(path)==ROOT/'nfl_lab/operational_sources.py' else actual(path))
    with pytest.raises(ValueError,match='feature builder identity changed'):
        future.build_future_features(None,None,policy=policy,source_contract=REGISTERED_SOURCE_CONTRACT)


class Clock:
    def __init__(self):self.value=CONTINUED+timedelta(seconds=10)
    def __call__(self):
        self.value+=timedelta(microseconds=1)
        return self.value
    def advance(self,seconds):self.value+=timedelta(seconds=seconds)


@pytest.fixture
def packet(tmp_path,monkeypatch):
    f=fixture(active_reference=False);corrected=prepare(f);registration=registered(corrected);choice=continuation(f,registration)
    policy=sources.load_source_policy(ROOT/'config/operational-source-policy-v2.json')
    storage=OperationalStorage(tmp_path/'cache',policy,state=tmp_path/'state');storage.register_root(tmp_path)
    clock=Clock()
    def put(path,document):return r.write(storage,tmp_path/path,document)
    contract=dict(source_policy_sha256=policy['_policy_sha256'],availability_rule='FROZEN_KICKOFF_PLUS_7DAY_RECONSTRUCTION',
        feature_builder_sha256=future.sha(ROOT/'nfl_lab/operational_sources.py'))
    models=[];aliases=[]
    current=dict(repository=private.REPO,run_id='12346',run_attempt=1,source_sha='b'*40,
        job_id='fictional_runtime',api_job_id=991,workflow_ref=private.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',
        execution_lane='github_actions',permission='write',process_identity='c'*64)
    manifests={}
    for slot in f['replay']['slots']:
        target,method=slot['target'],slot['method_id']
        roles=['QB'] if target.startswith('pass_') else ['WR'] if target in {'rec','rec_yd'} else ['RB']
        if target=='anytime_td':roles=['RB','WR','TE']
        support='bernoulli' if target=='anytime_td' else 'signed_integer' if target.endswith('_yd') else 'count'
        body=canonical(['model',target,method]);mp=tmp_path/'weights'/target/(method+'.opaque')
        storage.write_bytes(mp,body)
        assert future.sha(mp)==slot['model_sha256']
        manifest=dict(schema_version=future.VERSION,artifact_kind='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY',
            family=slot['family'],method_id=method,procedure_version=slot['procedure_version'],
            category=dict(target=target,support=support,modeled_roles=['QB','RB','WR','TE'],primary_roles=roles),
            model=future.binding(mp),source_contract=contract,features=['f_player_games_prior','f_fixture'],dependencies=[],
            code_pins=future.code_pins(),training_cutoff_utc='2026-09-04T00:00:00Z',training_max_available_utc='2026-08-31T00:00:00Z',
            fit_receipt=dict(training_source_capture_completed_at='2026-09-01T00:00:00Z',training_started_at='2026-09-02T00:00:00Z',training_completed_at='2026-09-03T00:00:00Z'),
            probability_law='NONE_POINT_ONLY')
        ref=put(Path('manifests')/target/(method+'.json'),manifest);models.append(ref);manifests[ref['sha256']]=manifest
        aliases.append(dict(target=target,family=slot['family'],method_id=method,model_sha256=slot['model_sha256'],
            procedure_version=slot['procedure_version'],original_transport_manifest_sha256=slot['transport_manifest_sha256'],
            original_verified_reader_manifest_sha256=slot['manifest_sha256'],current_manifest=ref))
    aref=put('retained/RELOCATION_CATALOG.json',dict(schema_version=retained.VERSION+'-manifest-aliases',current=current,models=aliases))
    restored=dict(schema_version=retained.VERSION+'-restore',state='CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE',
        model_pairs=18,models=models,origin=dict(replay_catalog=f['replay']),current=current,relocation_catalog=aref,
        fits=0,current_loader_replay=True,model_artifact_durability=True,public_release=False,
        proofs=[dict(schema_version='weekly-private-proof-v2.1',phase='restore',run_id=current['run_id'],source_sha=current['source_sha'],exact_readback=True,separate_process=True)])
    restored_ref=put('retained/RESTORED.json',restored)
    config=dict(history_seasons=[2026],allowed_periods={'2026':[1,2,3,4,5]},
        freshness_seconds=dict(schedule=86400,current_roster=86400,current_statistics=86400,players=604800))
    runtime=r.Runtime(storage,registration,choice,restored_ref,config,clock=clock)
    schedule=pd.DataFrame([dict(season=2026,week=7,game_type='REG',game_id=g['game_id'],
        gameday=str(utc(g['kickoff_utc']).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date()),
        gametime=utc(g['kickoff_utc']).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).strftime('%H:%M'),
        home_team=home,away_team=away,espn=str(10001+i))
        for i,(g,home,away) in enumerate(zip(f['schedule'],['E','A','C'],['F','B','D']))])
    roster=pd.DataFrame([dict(season=2026,week=7,game_type='REG',team=team,gsis_id='00-'+str(i+1).zfill(7),
        sleeper_id=str(100+i),position=role,status=status,full_name='Fictional')
        for i,(team,role,status) in enumerate([('A','QB','ACT'),('B','RB','ACT'),('C','WR','INA'),('D','TE','RES'),('E','QB','ACT')])])
    requests=[]
    def download(raw,name,url,**kwargs):
        requests.append((name,url,kwargs))
        if name=='schedules.csv':body=schedule.to_csv(index=False).encode()
        elif name=='roster_weekly_2026.parquet':
            out=io.BytesIO();roster.to_parquet(out,index=False);body=out.getvalue()
        else:body=b'FICTIONAL_OPAQUE_IDENTITY_OR_STATISTICS'
        storage.write_bytes(raw/name,body)
        receipt=dict(name=name,url=url,bytes=len(body),sha256=private.sha(body),status='acquired',cache_reused=False,retrieved_utc=clock().isoformat())
        r.write(storage,raw/(name+'.receipt.json'),receipt)
        return receipt
    history_sources={}
    for name,spec in sources._names([2026]).items():
        if name in {'schedules.csv','players.parquet','stats_player_week_2026.parquet','roster_weekly_2026.parquet'}:continue
        body=put('original/'+name,{'fictional_license':True})
        receipt=put('original/'+name+'.receipt.json',dict(url=spec['url'],status='acquired',sha256=body['sha256'],bytes=body['bytes'],retrieved_utc='2026-10-20T00:00:00Z'))
        history_sources[name]=dict(body=body,receipt=receipt)
    acquisitions=[]
    def acquire(cache,years,policy,asof,*,source_cache,allowed_periods,storage):
        acquisitions.append((years,allowed_periods))
        ns=storage.register_root(tmp_path/'fictional-qualified-history')
        raw=Path(source_cache)/'raw';specs=sources._names(years)
        request=dict(allowed_periods=allowed_periods,seasons=years)
        manifest=dict(namespace=str(ns),request=request,source_receipts={},sources={},artifact_sha256s={})
        for name in specs:
            receipt=json.loads((raw/(name+'.receipt.json')).read_bytes())
            manifest['source_receipts'][name]=receipt
            for actual,dest in ((raw/name,ns/'sources'/name),(raw/(name+'.receipt.json'),ns/'sources'/(name+'.receipt.json'))):
                storage.import_file(actual,dest,expected_sha256=future.sha(actual))
            manifest['sources'][name]=dict(sha256=future.sha(raw/name),receipt_sha256=future.sha(raw/(name+'.receipt.json')),bytes=(raw/name).stat().st_size)
        href=r.write(storage,ns/'processed/history.parquet',{'fictional_early_history_only':True})
        manifest['artifact_sha256s']['processed/history.parquet']=href['sha256']
        mref=r.write(storage,ns/'source-manifest.json',manifest);manifest['manifest_sha256']=mref['sha256']
        request_path=storage.cache/'operational-source-v2'/policy['_policy_sha256']/'requests'/(sources._digest(request)+'.json')
        r.write(storage,request_path,{'fictional_request':True})
        return manifest
    monkeypatch.setattr(sources,'acquire_operational_history',acquire)
    loads=[]
    def load(*args,**kwargs):
        loads.append(kwargs)
        return pd.DataFrame({'fictional_history':['early_only']})
    monkeypatch.setattr(sources,'load_operational_history',load)
    feature_calls=[]
    def features(history,queries,**kwargs):
        feature_calls.append(queries.copy())
        return queries.assign(f_player_games_prior=[3.,0.,4.,0.],f_fixture=1.,feature_max_source_available_utc=utc('2026-10-20T00:00:00Z'))
    monkeypatch.setattr(future,'build_future_features',features)
    def prepare_models(session,refs):
        # Real immutable owned auth and row generator; numerical backend only
        # is injected. These opaque fictional model bytes are never decoded.
        session._verify(refs)
        session.models={ref['sha256']:(manifests[ref['sha256']],SimpleNamespace(category=manifests[ref['sha256']]['category'])) for ref in refs}
    monkeypatch.setattr(future.FutureInferenceSession,'prepare',prepare_models)
    def points(model,family,frame):
        support=model.category['support']
        values=np.full(len(frame),.25 if support=='bernoulli' else -2.5 if support=='signed_integer' else 0.)
        values[frame.position.eq('TE')]=np.nan
        reasons=np.where(frame.position.eq('TE'),'UNAVAILABLE_FICTIONAL_NEW_ROLE','')
        return values,reasons
    monkeypatch.setattr(future,'_points',points)
    def forbidden(*args,**kwargs):raise AssertionError('fit/search/reselection forbidden')
    monkeypatch.setattr(future,'fit_future_model',forbidden)
    monkeypatch.setattr(r.selector,'select',forbidden)
    return SimpleNamespace(runtime=runtime,storage=storage,clock=clock,put=put,requests=requests,download=download,
        historical_sources=history_sources,acquisitions=acquisitions,feature_calls=feature_calls,loads=loads,
        root=tmp_path,manifests=manifests,original=f,schedule=schedule,roster=roster)


def staged(p):
    prepared=p.runtime.prepare(p.root/'metadata')
    p.clock.advance(60)
    completion=r.read_owned(p.storage,r.read_owned(p.storage,prepared)['choice_completion'])
    p.clock.advance(60)
    source=p.runtime.acquire(prepared,completion,p.historical_sources,p.root/'acquisition',downloader=p.download)
    return prepared,source,completion


def rows(ref):
    import gzip
    return [json.loads(line) for line in gzip.decompress(Path(ref['path']).read_bytes()).splitlines()]


def test_complete_all18_future_only_real_zero_unavailable_and_preserved_choice(packet):
    p=packet;prepared,source,_=staged(p)
    result_ref=p.runtime.infer(prepared,source,p.root/'inference')
    result=r.read_owned(p.storage,result_ref)
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE',result
    assert result['model_pairs']==18 and result['prediction_rows']==72
    assert result['HTTP']==result['fits']==result['searches']==result['scores']==0
    assert result['public_release'] is result['scientific_qualification'] is result['successful_forecast'] is False
    assert len(p.requests)==4 and len(p.acquisitions)==len(p.loads)==len(p.feature_calls)==1
    assert p.acquisitions[0][1]=={'2026':[1,2,3,4,5]}
    candidate=r.read_owned(p.storage,result['candidates'])
    all_rows=[row for slot in candidate['slots'] for row in rows(slot['persistence']['binding'])]
    assert len(candidate['slots'])==18 and all(s['expected_rows']==s['issued_rows']==4 for s in candidate['slots'])
    assert {row['game_id'] for row in all_rows}=={'fictional-sunday','fictional-monday'}
    assert any(row['forecast_value']==0 and row['operational_eligible'] is True for row in all_rows)
    assert any(row['forecast_value'] is None and row['operational_eligible'] is False and row['position']=='TE' for row in all_rows)
    assert all(row['participation_state']=='unknown' for row in all_rows)
    selected=rows(result['selected']['binding'])
    td=next(row for row in selected if row['category']=='anytime_td' and row['forecast_value'] is not None)
    assert [(c['method_id'],c['weight']) for c in td['components']]==[('LAB_CDF',.5),('CATBOOST_MEDIUM',.5)]
    assert result['original_choice_clock']==json.loads(p.original['raw'])['actual_frozen_at']
    assert result['original_weekly_deadline_utc']==p.original['slate']['weekly_deadline_utc']
    assert result['effective_choice_clock']!=result['original_choice_clock']
    assert result['product_kind']=='SOFTWARE_CORRECTION_CONTINUATION'
    handoff=r.read_owned(p.storage,future.binding(p.root/'inference/EXPORT_INPUTS.json'))
    assert handoff['schema_version']==r.HANDOFF and handoff['requires_new_epoch_checkpoint_export_consumer'] is True
    assert handoff['durability'] is handoff['rights'] is None
    assert r.read_owned(p.storage,result['bridge'])['name_matching'] is False


def test_raw_schedule_LA_and_canonical_roster_LAR_preserve_every_future_side(packet):
    p=packet
    # nfldata uses LA while the existing canonical identity contract uses LAR.
    # One complete Rams side must survive; no coverage assertion is weakened.
    p.schedule.loc[p.schedule.home_team.eq('A'),'home_team']='LA'
    p.roster.loc[p.roster.team.eq('A'),'team']='LAR'
    prepared,source,_=staged(p)
    result=r.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'inference'))
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE',result
    assert result['prediction_rows']==72 and result['query_rows']==4
    identity=r.read_owned(p.storage,result['bridge'])['identities']
    assert 'LAR' in {x['team'] for x in identity} and 'LA' not in {x['team'] for x in identity}
    assert {x['game_id'] for x in rows(result['selected']['binding'])}=={'fictional-sunday','fictional-monday'}


def test_cli_preserves_fixed_failure_reason_without_private_library_text():
    from tools.audit_weekly_runtime_v1 import public_summary
    code='ALL_FUTURE_GAME_SIDES_REQUIRE_CURRENT_ROSTER_COVERAGE'
    failed=dict(state='FAILED_RETAINED',reason=code,private_rows=['DO_NOT_PUBLISH'])
    result=public_summary(failed,'infer','a'*64)
    assert result['reason']==code and 'private_rows' not in result
    assert result['public_release'] is result['public_export_authorized'] is False
    failed['reason']='private exception text and source body'
    assert public_summary(failed,'infer','a'*64)['reason']=='UPSTREAM_OPERATION_FAILED'
    assert public_summary(dict(state='PARTIAL_RETAINED_NOT_QUALIFIED'),'infer','a'*64)['reason']=='INCOMPLETE_CANDIDATE_CAPTURE'


def test_metadata_and_version_catalog_precede_downloads_or_current_values(packet):
    p=packet
    prepared=p.runtime.prepare(p.root/'metadata')
    assert p.requests==p.feature_calls==p.loads==[]
    document=r.read_owned(p.storage,prepared)
    assert document['current_values_used'] is False
    for ref in document['refs'].values():p.storage.validate_reference(ref['path'],ref['sha256'])
    with pytest.raises(epoch.EpochError):p.runtime.acquire(prepared,{},p.historical_sources,p.root/'bad',downloader=p.download)
    assert not p.requests and not (p.root/'bad').exists()


@pytest.mark.parametrize('kind',['cache_reused','stale','old_clock'])
def test_mutable_cache_is_never_relabelled_as_a_refresh(packet,kind):
    p=packet
    original=p.download
    def bad(*args,**kwargs):
        receipt=original(*args,**kwargs)
        if kind=='old_clock':receipt['retrieved_utc']='2026-10-20T00:00:00Z'
        else:receipt[kind]=True
        return receipt
    p.download=bad
    with pytest.raises(r.RuntimeErrorCode,match='NO_RELABELLED'):staged(p)
    assert not p.acquisitions
    assert (p.root/'acquisition/SOURCE_FAILED.json').is_file()


def test_interrupted_slot_retains_prefix_forever_unqualified_and_no_success_handoff(packet,monkeypatch):
    p=packet;prepared,source,_=staged(p)
    original=future.FutureInferenceSession.predict_chunks
    failed=p.runtime.records[0]['binding']['sha256']
    def interrupted(session,version,*args,**kwargs):
        yield from original(session,version,*args,**kwargs)
        if version==failed:raise OSError('FICTIONAL_PRIVATE_ERROR_SHOULD_NOT_ESCAPE')
    monkeypatch.setattr(future.FutureInferenceSession,'predict_chunks',interrupted)
    result=r.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'inference'))
    assert result['state']=='PARTIAL_RETAINED_NOT_QUALIFIED'
    capture=r.read_owned(p.storage,result['candidates'])
    assert len(capture['slots'])==18 and capture['slots'][0]['attempt_qualified'] is False
    prefix=rows(capture['slots'][0]['persistence']['binding'])
    assert prefix and all(row['operational_eligible'] is row['attempt_qualified'] is False for row in prefix)
    assert result['selected']['rows']==0 and not (p.root/'inference/EXPORT_INPUTS.json').exists()
    assert 'FICTIONAL_PRIVATE_ERROR' not in json.dumps(result)


def test_changed_source_schedule_keeps_failure_and_no_backfill(packet):
    p=packet;prepared,source,_=staged(p)
    p.clock.value=utc('2026-10-25T19:31:00Z')
    with pytest.raises(r.RuntimeErrorCode,match='INPUT_CUTOFF_ELAPSED'):p.runtime.infer(prepared,source,p.root/'inference')
    assert not p.feature_calls


def test_duplicate_phase_no_reads_or_retry(packet):
    p=packet;prepared,source,completion=staged(p)
    count=len(p.requests)
    with pytest.raises(r.RuntimeErrorCode,match='NO_RETRY'):
        p.runtime.acquire(prepared,completion,p.historical_sources,p.root/'acquisition',downloader=p.download)
    assert len(p.requests)==count


def test_explicit_early_filter_rejects_protected_and_current_periods(packet):
    c=deepcopy(packet.runtime.config)
    c['allowed_periods']['2026']=[1,2,5,8]
    with pytest.raises(r.RuntimeErrorCode,match='PROTECTED_CONFIRMATION'):r.config_check(c,packet.runtime.choice.document['slate'])
    c['allowed_periods']['2026']=[6]
    with pytest.raises(r.RuntimeErrorCode,match='PROTECTED_CONFIRMATION'):r.config_check(c,packet.runtime.choice.document['slate'])


def test_original_E7_parquet_predicates_exclude_fictional_protected_rows_before_values(tmp_path,monkeypatch):
    path=tmp_path/'fictional-statistics.parquet'
    pd.DataFrame([dict(season=2026,week=w,season_type='REG',passing_yards=100+w) for w in [1,5,8]]).to_parquet(path,index=False)
    original=pd.read_parquet;calls=[]
    def read(path,**kwargs):calls.append(kwargs);return original(path,**kwargs)
    monkeypatch.setattr(pd,'read_parquet',read)
    frame,filters=sources._filtered_parquet(path,['season','week','season_type','passing_yards'],year=2026,weeks=[1,5],kind='statistics')
    assert set(frame.week)=={1,5} and calls[0]['filters']==filters
    assert ('week','in',[1,5]) in filters[0]


def test_unapproved_template_and_no_execute_discover_no_context(tmp_path):
    class NoEnvironment:
        def get(self,*unused):raise AssertionError('context discovery')
    with redirect_stdout(io.StringIO()):
        assert cli.main(['infer'],environ=NoEnvironment())==2
        path=tmp_path/'template.json'
        assert cli.main(['template','--output',str(path)],environ=NoEnvironment())==0
    template=json.loads(path.read_bytes())
    assert template['approved'] is False and template['limits']==r.LIMITS
    assert path.stat().st_mode&0o077==0


def test_added_or_changed_candidate_fields_fail_slot_without_qualification(packet,monkeypatch):
    p=packet;prepared,source,_=staged(p)
    original=future.FutureInferenceSession.predict_chunks
    broken=p.runtime.records[0]['binding']['sha256']
    def changed(session,version,*args,**kwargs):
        for chunk in original(session,version,*args,**kwargs):
            if version==broken:chunk[0]['unexpected_private_actual']=123
            yield chunk
    monkeypatch.setattr(future.FutureInferenceSession,'predict_chunks',changed)
    result=r.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'inference'))
    capture=r.read_owned(p.storage,result['candidates'])
    assert result['state']=='PARTIAL_RETAINED_NOT_QUALIFIED'
    assert capture['slots'][0]['state']=='FAILED_RETAINED'
    assert capture['slots'][0]['issued_rows']==0
    assert len(capture['slots'][0]['unissued_offered_ids'])==4
    assert not (p.root/'inference/EXPORT_INPUTS.json').exists()


def test_complete_fresh_source_cannot_hide_a_future_game_side(packet,monkeypatch):
    p=packet;prepared,source,_=staged(p)
    original=pd.read_parquet
    def missing(path,**kwargs):
        frame=original(path,**kwargs)
        if str(path).endswith('roster_weekly_2026.parquet'):return frame.loc[frame.team.ne('D')]
        return frame
    monkeypatch.setattr(pd,'read_parquet',missing)
    result=r.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'inference'))
    assert result['state']=='FAILED_RETAINED' and result['reason']=='ALL_FUTURE_GAME_SIDES_REQUIRE_CURRENT_ROSTER_COVERAGE'
    assert not p.loads and not p.feature_calls


def test_unknown_failed_bytes_count_against_original_global_quota_before_inference(packet):
    from nfl_lab.operational_storage import StorageQuotaError
    p=packet;prepared,source,_=staged(p)
    retained_partial=p.root/'fictional-orphaned-partial'
    with retained_partial.open('wb') as stream:stream.truncate(512 << 20)
    with pytest.raises(StorageQuotaError):p.runtime.infer(prepared,source,p.root/'inference')
    assert retained_partial.stat().st_size==512 << 20
    assert not p.loads and not p.feature_calls


def test_parent_native_identity_is_distinct_from_the_owner_dispatch_input(tmp_path,monkeypatch):
    import subprocess
    from tools import private_draft_store_v2 as shared
    go=canonical({'fictional_root':True})
    event=tmp_path/'event.json';event.write_bytes(canonical(dict(repository=dict(full_name=private.REPO),
        inputs=dict(inference_builder_go_json=go.decode(),inference_builder_go_sha256=private.sha(go)))))
    current=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=private.REPO,GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',
        GITHUB_ACTOR='NickNicky19',GITHUB_ACTOR_ID='208912933',GITHUB_SHA='b'*40,GITHUB_RUN_ID='12346',GITHUB_JOB='fictional_runtime',
        GITHUB_WORKFLOW_REF=private.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',GITHUB_EVENT_PATH=str(event))
    authority=dict(schema_version=r.VERSION+'-native-authority',phase='infer',request_sha256='e'*64,owner_root_go_sha256=private.sha(go),
        repository=private.REPO,source_sha=current['GITHUB_SHA'],run_id=current['GITHUB_RUN_ID'],run_attempt=1,
        job_id=current['GITHUB_JOB'],workflow_ref=current['GITHUB_WORKFLOW_REF'],api_job_id=991,
        issued_at_utc=(r.now_utc()-timedelta(seconds=10)).isoformat(),expires_at_utc=(r.now_utc()+timedelta(minutes=10)).isoformat(),
        actual_actions_api_authenticated=True,owner_root_checked=True,fits=0,public_release=False)
    monkeypatch.setattr(shared,'actions_context',lambda env,permission:dict(job_id=env['GITHUB_JOB'],workflow_ref=env['GITHUB_WORKFLOW_REF']))
    monkeypatch.setattr(subprocess,'check_output',lambda *args,**kwargs:'')
    def env(doc):
        body=canonical(doc)
        return dict(current,AUDIT_WEEKLY_RUNTIME_AUTHORITY_JSON=body.decode(),AUDIT_WEEKLY_RUNTIME_AUTHORITY_SHA256=private.sha(body))
    args=SimpleNamespace(phase='infer',request_sha256='e'*64)
    assert cli.context(args,env(authority))==authority
    for key,value in [('phase','acquire'),('request_sha256','f'*64),('source_sha','a'*40),('owner_root_checked',False),
                      ('actual_actions_api_authenticated',False),('extra',True),('owner_root_go_sha256','f'*64)]:
        changed=dict(authority);changed[key]=value
        with pytest.raises(r.RuntimeErrorCode):cli.context(args,env(changed))


def test_standalone_child_without_actual_authority_stops_before_private_inputs(tmp_path):
    import os
    import subprocess
    import sys
    numerical=json.loads((ROOT/'config/weekly-owner-private-bootstrap-v1.json').read_bytes())['numerical_environment']
    env={k:v for k,v in os.environ.items() if not k.startswith(('GITHUB_','AUDIT_WEEKLY_'))}
    result=subprocess.run([sys.executable,'-I','-B',str(ROOT/'tools/audit_weekly_runtime_v1.py'),'infer','--execute',
        '--request',str(tmp_path/'NONEXISTENT_PRIVATE_REQUEST'),'--request-sha256','f'*64],cwd=ROOT,
        env={**env,**numerical},capture_output=True,text=True,timeout=30)
    assert result.returncode==1,result.stderr
    output=json.loads(result.stdout)
    assert output['reason']=='ACTUAL_OWNER_ACTIONS_CHILD_ONLY'
    assert output['public_export_authorized'] is False
    assert result.stderr==''
