"""Fictional operational captures/labels; no actual data, models, HTTP or fits."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import io
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nfl_lab import audit_weekly_grade_v1 as g, audit_weekly_epoch_v1 as epoch
from nfl_lab import audit_weekly_runtime_v1 as runtime, audit_weekly_retained_v1 as retained
from nfl_lab import private_draft_store as store, gha_private_checkpoint as cp, state
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_weekly_grade_v1 as cli
from test_audit_weekly_epoch_v1 import fixture, prepare, registered, continuation, next_slate, REGISTERED, CONTINUED, h
from test_audit_weekly_retained_v1 import saved, chain, execute as execute_retained

ROOT = Path(__file__).resolve().parents[1]
GRADE = state.utc("2026-10-28T08:00:00Z")


class Parent:
    """Independent fictional authority seam; no JSON authorization flags."""
    def __init__(self): self.calls=[]; self.allowed=True
    def __call__(self, request):
        self.calls.append(deepcopy(request)); return self.allowed


@pytest.fixture
def packet(tmp_path):
    f=fixture(active_reference=False)
    controls=dict(procedure_version=h('fictional-new-original-control'),model_versions=[h('fictional-control-artifact')],
        procedure_operational_eligible=True,procedure_replay_eligible=False,role='reference',training_state='UPSTREAM_TRAINING_UNOBSERVED',
        control_policy_sha256=h('fictional-registered-control-policy'),control_source_version='fictional-original-v1',event_contract=g.selector.ANYTIME_EVENT_CONTRACT)
    e=prepare(f,effective_controls={'R0':controls}); r=registered(e); c=continuation(f,r)
    storage=OperationalStorage(tmp_path/'cache',ROOT/'config/operational-source-policy-v2.json',state=tmp_path/'state')
    base=tmp_path/'capture';storage.register_root(base)
    aliases={}
    def body(name,raw):
        storage.write_bytes(base/name,raw);ref=cp.binding(base/name);aliases[name]=ref;return ref
    def put(name,doc):return body(name,state.canonical(doc))
    source_at=CONTINUED+timedelta(minutes=5); issued=source_at+timedelta(minutes=1)
    cutoff=c.document['slate']['game_cutoffs']['fictional-sunday']
    schedule=[dict(season=2026,week=7,website_game_id=str(111+i),game_id=x['game_id'],kickoff_utc=x['kickoff_utc'],home='A',away='B') for i,x in enumerate(f['schedule'])]
    roles={t:dict(modeled_roles=['QB'] if t.startswith('pass_') else ['RB'],primary_roles=['QB'] if t.startswith('pass_') else ['RB']) for t in cp.TARGETS}
    capture_id=h('fictional-prevalue-root-capture-id')
    pop=g.population_template(r,c);pop.update(state='ROOT_REGISTERED',stream_id='fictional-epoch-primary-daily',registered_at=(CONTINUED+timedelta(minutes=1)).isoformat(),
        role_catalog_sha256=state.digest(roles),assignments={k:capture_id for k in c.document['slate']['game_cutoffs']})
    parent=Parent();population=g.bind_population(pop,r,c,authenticate=parent,at=source_at)
    query=[];bridges=[]
    for i in range(3):
        q=dict(season=2026,week=7,game_id='fictional-sunday',player_id='00-'+str(i+1).zfill(7),sleeper_id=str(123+i),position='RB',team='A',opponent='B',
            kickoff_utc=f['schedule'][1]['kickoff_utc'],cutoff_utc=cutoff)
        query.append(q)
        b=dict(gsis_id=q['player_id'],gsis_game_id=q['game_id'],sleeper_id=q['sleeper_id'],website_player_id=q['sleeper_id'],website_game_id='112',team='A',opponent='B',
            kickoff_utc=q['kickoff_utc'],query_source_sha256=h('fictional-query'),schedule_source_sha256=h('fictional-schedule'))
        b['identity_binding_sha256']=state.digest(b);bridges.append(b)
    # Genuine Arrow timestamp columns, as produced by current-query code.
    arrow=[dict(q,kickoff_utc=state.utc(q['kickoff_utc']),cutoff_utc=state.utc(q['cutoff_utc'])) for q in query]
    buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(arrow),buf);body('runtime/queries.parquet',buf.getvalue())
    put('runtime/IDENTITY_BRIDGE.json',dict(identities=bridges))
    put('context/source.json',dict(actual_source_started_at=(source_at-timedelta(seconds=1)).isoformat(),actual_completed_at=source_at.isoformat()))
    # Exercise the actual serializer, not an expected-shape fixture. The
    # inference backend is deliberately not constructed: no model is loaded.
    serializer=object.__new__(runtime.Runtime)
    serializer.storage=storage;serializer.registered=r;serializer.choice=c
    serializer.clock=lambda:CONTINUED+timedelta(minutes=2);serializer.progress=lambda:None
    serializer.recipe=dict(schema_version=runtime.VERSION+'-recipe',fictional_metadata_only=True)
    serializer.replay=deepcopy(f['replay']);serializer.artifacts=epoch.artifact_catalog(e)
    serializer.versions=epoch.selected_versions(r,c,now=serializer.clock())
    serializer.restored=dict(proofs=[dict(fictional_effective_model_metadata=True)])
    prepared=serializer.prepare(base/'actual-runtime-serializer')
    actual_choice_ref=runtime.read_owned(storage,prepared)['refs']['choice']
    aliases['runtime/WEEKLY_CHOICE.json']=actual_choice_ref
    catalog=epoch.artifact_catalog(e)['catalog'];slots=[];forecasts=[]
    def original(q,target,method,value,version):
        row=dict(q,category=target,method_id=method,slate_id=c.document['slate']['slate_id'],horizon='player_game',forecast_value=value,model_version=version,
            procedure_version=catalog['methods'][method]['procedure_version'],product=catalog['categories'][target]['product'],
            prediction_functional=g.selector.PRODUCTS[catalog['categories'][target]['product']][1],evidence_lane='original_pregame',operational_eligible=True,
            reference_stream='candidate',issued_at=issued.isoformat(),source_capture_completed_at=source_at.isoformat(),scientific_qualification=False,
            public_export_authorized=False,correction_epoch_sha256=e.sha256,attempt_qualified=True,source_policy_sha256=cp.POLICY_SHA,
            training_cutoff_utc='2026-09-04T00:00:00Z',training_max_available_utc='2026-08-31T00:00:00Z',
            training_source_capture_completed_at='2026-09-01T00:00:00Z',training_started_at='2026-09-02T00:00:00Z',training_completed_at='2026-09-03T00:00:00Z')
        row['offered_id']=g.selector.offered_id(row);return row
    for target,family,method in cp.JOBS:
        version=next(s['manifest_sha256'] for s in f['replay']['slots'] if (s['target'],s['method_id'])==(target,method))
        value=.5 if target=='anytime_td' else 10 if method=='COUNT_A' else 0
        rows=[original(q,target,method,value,version) for q in query]
        for row in rows:
            if row['position'] not in roles[target]['modeled_roles']:row['operational_eligible']=False
        forecasts.extend(rows)
        ref=body(f'runtime/candidates/{target}/{method}.jsonl.gz',gzip.compress(b''.join(state.canonical(x)+b'\n' for x in rows),mtime=0))
        receipt=dict(state='PERSISTED',binding=ref,rows=3,persist_started_at=source_at.isoformat(),completed_at=(issued+timedelta(seconds=1)).isoformat())
        put(f'runtime/candidates/{target}/{method}.jsonl.completion.json',receipt)
        slots.append(dict(target=target,method_id=method,state='CAPTURED',failure=None,attempt_qualified=True,expected_rows=3,issued_rows=3,persistence=receipt))
    put('runtime/CANDIDATES.json',dict(slots=slots))
    controls=[]
    for target in cp.TARGETS:
        for q in query:
            if q['position'] not in roles[target]['primary_roles']:continue
            row=original(q,target,'R0',.25 if target=='anytime_td' else 1,catalog['methods']['R0']['model_versions'][0])
            row.update(training_state='UPSTREAM_TRAINING_UNOBSERVED',control_policy_sha256=catalog['methods']['R0']['control_policy_sha256'],control_source_version='fictional-original-v1',
                source_receipt_sha256=h('fictional-native-source-receipt'),reference_stream='live_R0',saved_event_probability=target=='anytime_td',event_contract=g.selector.ANYTIME_EVENT_CONTRACT if target=='anytime_td' else None,
                public_release=False)
            if target!='anytime_td':row.update(product='point_legacy',prediction_functional='legacy_unknown')
            row.update(source_capture_completed_at=(source_at-timedelta(minutes=1)).isoformat(),issued_at=(source_at-timedelta(seconds=30)).isoformat())
            del row['scientific_qualification'];controls.append(row)
    control_ref=put('r0/control_forecast_rows.json',dict(rows=controls))
    put('r0/control_completion.json',dict(schema_version='audit-reference-capture-v1-control-completion',forecast_binding=control_ref,body_persist_completed_at=source_at.isoformat()))
    offers=[]
    for target in cp.TARGETS:
        for q in query:
            if q['position'] not in roles[target]['primary_roles']:continue
            offer={k:q[k] for k in ('season','week','game_id','player_id','cutoff_utc','kickoff_utc','position','team','opponent')}
            offer.update(category=target,slate_id=c.document['slate']['slate_id'],horizon='player_game')
            offer['offered_id']=g.selector.offered_id(offer);offers.append(offer)
    primary={o['offered_id'] for o in offers}
    panel=g.selector.Panel(dict(schema_version=g.selector.VERSION,offers=offers,forecasts=[r for r in forecasts if r['offered_id'] in primary],outcomes=[],decisions=[x['decision'] for x in c.document['choice']['selections']],weeks=[]),catalog)
    from nfl_lab import weekly_generic_producer as generic
    selected=[]
    for selection in c.document['choice']['selections']:
        for row in generic.issue_registered(g.selector,panel,selection,atomic_TD=True):
            procedure=state.digest(dict(schema_version=epoch.VERSION+'-issued-procedure',epoch_sha256=e.sha256,
                selection_recipe_sha256=state.digest(e.document['selection_recipe']),category=row['category'],members=selection['members']))
            row.update(method_id='P2_SELECTED',procedure_version=procedure,model_version=state.digest([(x['method_id'],x['model_version'],x['weight']) for x in row['components']]),
                issued_at=(issued+timedelta(seconds=2)).isoformat(),source_capture_completed_at=source_at.isoformat(),correction_epoch_sha256=e.sha256,
                scientific_qualification=False,public_export_authorized=False,operational_eligible=row['forecast_value'] is not None,source_policy_sha256=cp.POLICY_SHA)
            selected.append(row)
    selected_ref=body('runtime/selected.jsonl.gz',gzip.compress(b''.join(state.canonical(x)+b'\n' for x in selected),mtime=0))
    selected_completion=dict(state='PERSISTED',binding=selected_ref,rows=len(selected),persist_started_at=source_at.isoformat(),completed_at=(issued+timedelta(seconds=3)).isoformat())
    put('runtime/selected.jsonl.completion.json',selected_completion)
    put('runtime/FINISHED.json',dict(schema_version='audit-weekly-runtime-v1-result',state='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE',epoch_sha256=e.sha256,choice_sha256=c.sha256,
        selected=selected_completion,actual_completed_at=(issued+timedelta(seconds=4)).isoformat()))
    restored=dict(schema_version=g.archive.VERSION+'-restored',state='PRIVATE_CAPTURE_RESTORED',scope_qualified_for_publication=False,public_export_authorized=False,
        captured_bundle_hashes_restored=True,aliases=aliases,index_sha256=h('fictional-qualified-index'),validation=dict(qualified_selected=True),
        restore_proofs=[dict(created_at_utc=(issued+timedelta(minutes=1)).isoformat())],restorer_witness=dict(actual_completed_at=(issued+timedelta(minutes=2)).isoformat()))
    def bind(restoration=None,auth=None):
        return g.bind_capture(r,c,population,restored if restoration is None else restoration,storage=storage,capture_id=capture_id,role_catalog=roles,frozen_schedule=schedule,
            authenticate=parent if auth is None else auth,at=CONTINUED+timedelta(minutes=15))
    capture=bind()
    return dict(f=f,e=e,r=r,c=c,storage=storage,base=base,parent=parent,pop=pop,population=population,query=query,roles=roles,schedule=schedule,
        capture_id=capture_id,capture=capture,restored=restored,bind=bind,serialized_choice=actual_choice_ref,
        forecast_bytes={k:Path(v['path']).read_bytes() for k,v in aliases.items() if k.endswith('.jsonl.gz')})


def batch(q, *, actuals=(0,0,0), states=('played','played','played'), final=True, publication='2026-10-27T06:00:00Z', at=GRADE):
    finality=[dict(season=2026,week=7,status_source_sha256=h('fictional-final-status'),observed_at=(at-timedelta(hours=1)).isoformat(),
        games=[dict(game_id='espn:'+r['website_game_id'],kickoff_utc=r['kickoff_utc'],home=r['home'],away=r['away'],final=final) for r in q['schedule']])]
    observations=[]
    if final:
        for i,query in enumerate(q['query']):
            observations.append(dict(player_id=query['player_id'],game_id='espn:112',target='rec',actual=actuals[i],participation_state=states[i],
                source='fictional-Sleeper-same-origin',source_sha256=h(['fictional-provider-body',actuals,publication]),status_sha256=h('fictional-final-status'),
                observed_at=(at-timedelta(minutes=30)).isoformat(),source_timestamp=publication))
    doc=dict(schema_version=g.VERSION+'-provider-observations',source_policy_sha256=cp.POLICY_SHA,captured_at=at.isoformat(),observations=observations,finality=finality)
    return g.bind_observations([q['capture']],doc,authenticate=q['parent'],at=at)


def grade(q,tmp_path,b=None,previous=None,at=GRADE):
    return g.grade(q['r'],[q['capture']],[batch(q) if b is None else b],storage=q['storage'],output=tmp_path,previous=previous,clock=lambda:at)


def qualify(q,snapshot,at=GRADE+timedelta(minutes=2)):
    writer=dict(execution_lane='github_actions',repository=store.REPO,run_id='12345',run_attempt=1,source_sha='a'*40,process_identity=h('fictional-writer'),
        job_id='fictional-grade-writer',api_job_id=101,permission='write',workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/fictional')
    reader=dict(writer,process_identity=h('fictional-reader'),job_id='fictional-grade-reader',api_job_id=102)
    proof=dict(schema_version=g.VERSION+'-durability',snapshot_sha256=snapshot.sha256,restored_body_sha256=snapshot.binding['sha256'],known_by_at=at.isoformat(),
        producer=writer,reader=reader,proof_sha256=h(['fictional-native-readback',snapshot.sha256]))
    return g.confirm_durable(snapshot,proof,registered=q['r'],authenticate=q['parent'],at=at)


def test_actual_owned_capture_clocks_all18_and_unmodified_originals(packet,tmp_path):
    q=packet;snapshot=grade(q,tmp_path/'grade');durable=qualify(q,snapshot)
    report=g.report(durable,q['r'],at=GRADE+timedelta(minutes=3))
    count=next(x for x in report['metrics'] if (x['category'],x['method_id'])==('rec','COUNT_A'))
    assert count['coverage']['scored']==3 and count['coverage']['scored_played_zero']==3
    assert count['primary_loss']==100 and count['signed_bias']==10 and count['absolute_error_p90_nearest_rank']==10
    assert len(report['candidate_slots'][0]['slots'])==18
    out_of_role=[r for r in q['capture'].document['forecasts'] if r['category'].startswith('pass_')]
    assert len(out_of_role)==18 and all(r['operational_eligible'] is False for r in out_of_role)
    assert not any(o['category'].startswith('pass_') for o in g.history(durable,q['r'],at=GRADE+timedelta(minutes=3))['bundle']['offers'])
    assert report['fits']==0 and report['scientific_qualification'] is False
    assert durable.document['metadata_remote_durability_qualified'] is False
    for name,raw in q['forecast_bytes'].items():assert Path(q['restored']['aliases'][name]['path']).read_bytes()==raw
    assert q['f']['old_history']==b'{"weeks":[{"COUNT_A_loss":123456,"LAB_CDF_loss":0,"week":6}]}'


@pytest.mark.parametrize('auth',[None,lambda request:{'execution_authorized':True},lambda request:False])
def test_external_parent_authentication_before_any_private_decode(packet,monkeypatch,auth):
    def forbidden(*a,**kw):raise AssertionError('private body decoded before parent authority')
    monkeypatch.setattr(g.archive,'read_owned',forbidden)
    with pytest.raises(g.GradeError,match='PARENT_AUTH'):packet['bind'](auth=auth if auth is not None else object())


def test_missing_durability_retained_pending_without_private_body_read(packet,monkeypatch):
    restored=deepcopy(packet['restored']);restored['restore_proofs']=[]
    monkeypatch.setattr(g.archive,'read_owned',lambda *a,**kw:pytest.fail('missing durability read private body'))
    capture=packet['bind'](restoration=restored)
    assert capture.document['pending_reason']=='PENDING_CAPTURE_DURABILITY'
    assert capture.document['forecasts']==[] and not capture.document['ready']


def test_local_snapshot_or_decoded_history_never_qualifies(packet,tmp_path):
    local=grade(packet,tmp_path/'grade')
    for value in (local,local.document,{'durable':True}):
        with pytest.raises(g.GradeError,match='DURABILITY'):g.history(value,packet['r'],at=GRADE+timedelta(minutes=3))


def test_played_zero_DNP_unknown_and_missing_are_distinct(packet,tmp_path):
    q=packet;b=batch(q,actuals=(0,None,None),states=('played','DNP','unknown'))
    d=qualify(q,grade(q,tmp_path/'grade',b));rep=g.report(d,q['r'],at=GRADE+timedelta(minutes=3))
    metric=next(x for x in rep['metrics'] if (x['category'],x['method_id'])==('rec','COUNT_A'))
    assert metric['coverage']['scored']==1 and metric['coverage']['played_zero']==1
    assert metric['coverage']['DNP']==1 and metric['coverage']['unknown']==1
    assert metric['primary_loss']==100
    rows=[r for v in d.document['versions'] for r in v['snapshot']['rows'] if r['category']=='rec']
    assert {r['outcome_state'] for r in rows}=={'played_zero','DNP','unknown'}


def test_corrections_append_versions_order_by_publication_and_preserve_losing_week(packet,tmp_path):
    q=packet;first=grade(q,tmp_path/'first');durable=qualify(q,first)
    old=deepcopy(durable.document)
    later=GRADE+timedelta(hours=2)
    corrected=batch(q,actuals=(10,10,10),publication='2026-10-28T09:00:00Z',at=later)
    second=grade(q,tmp_path/'second',corrected,previous=durable,at=later)
    d2=qualify(q,second,at=later+timedelta(minutes=2))
    assert durable.document==old
    assert len(d2.document['versions'])==2
    assert len(d2.document['week_revisions'])==12
    rows=[x for v in d2.document['versions'] for x in v['snapshot']['rows'] if x['category']=='rec']
    assert {x['revision'] for x in rows}=={1,2}
    assert {x['actual'] for x in rows}=={0,10}
    early=g.report(durable,q['r'],at=GRADE+timedelta(minutes=3))
    current=g.report(d2,q['r'],at=later+timedelta(minutes=3))
    metric=lambda rep:next(m for m in rep['metrics'] if (m['category'],m['method_id'])==('rec','COUNT_A'))
    assert metric(early)['primary_loss']==100 and metric(current)['primary_loss']==0


def test_unknown_publication_conflicting_correction_quarantines_not_latest_arrival(packet,tmp_path):
    q=packet;first=qualify(q,grade(q,tmp_path/'first',batch(q,publication=None)))
    later=GRADE+timedelta(hours=2)
    second=grade(q,tmp_path/'second',batch(q,actuals=(2,2,2),publication=None,at=later),previous=first,at=later)
    d=qualify(q,second,at=later+timedelta(minutes=2))
    rows=[r for v in d.document['versions'] for r in v['snapshot']['rows'] if r['category']=='rec' and r['revision']==2]
    assert all(r['actual'] is None and r['resolution_state']=='unresolved_numeric_conflict' for r in rows)
    report=g.report(d,q['r'],at=later+timedelta(minutes=3))
    assert all(m['primary_loss'] is None for m in report['metrics'] if m['category']=='rec')


def test_idempotent_provider_refresh_does_not_rewrite_revision_or_week_clocks(packet,tmp_path):
    q=packet;first=qualify(q,grade(q,tmp_path/'first'))
    later=GRADE+timedelta(hours=2)
    second=grade(q,tmp_path/'second',batch(q,at=later),previous=first,at=later)
    assert second.document['new_revisions']==0
    assert second.document['versions']==first.document['versions']
    assert second.document['weeks']==first.document['weeks']


def test_one_final_game_cannot_qualify_full_week_and_future_outcomes_forbidden(packet,tmp_path):
    q=packet;b=batch(q);doc=deepcopy(b.document);doc.pop('capture_ids');doc['finality'][0]['games']=doc['finality'][0]['games'][1:2]
    b=g.bind_observations([q['capture']],doc,authenticate=q['parent'],at=GRADE)
    d=qualify(q,grade(q,tmp_path/'grade',b))
    assert not g.history(d,q['r'],at=GRADE+timedelta(minutes=3))['bundle']['weeks']
    assert all(x['state']=='PENDING_FULL_WEEK_FINALITY' for x in d.document['pending_weeks'])
    doc['observations'][0]['game_id']='espn:999999'
    with pytest.raises(g.GradeError,match='FIXED_OPERATIONAL'):g.bind_observations([q['capture']],doc,authenticate=q['parent'],at=GRADE)


def test_duplicate_captures_never_create_independent_games(packet,tmp_path):
    q=packet;duplicate=deepcopy(q['capture'].document);duplicate['capture_id']=h('second-capture-same-game')
    # Even a separately parent-authenticated competing capture is not a new
    # offered player/game and cannot silently select an earliest/latest issue.
    other=g.Capture(duplicate,g._KEY)
    with pytest.raises(g.GradeError,match='INDEPENDENT_OFFER'):
        g.grade(q['r'],[q['capture'],other],[],storage=q['storage'],output=tmp_path/'grade',clock=lambda:GRADE)


def test_parent_must_register_exact_population_before_current_values(packet):
    q=packet;pop=deepcopy(q['pop']);pop['rule']='LATEST_CAPTURE_WINS'
    with pytest.raises(g.GradeError,match='ISSUANCE_POPULATION'):g.bind_population(pop,q['r'],q['c'],authenticate=q['parent'],at=GRADE)
    pop=deepcopy(q['pop']);pop['registered_at']=GRADE.isoformat()
    late=g.bind_population(pop,q['r'],q['c'],authenticate=q['parent'],at=GRADE)
    with pytest.raises(g.GradeError,match='BEFORE_SOURCE_VALUES'):
        g.bind_capture(q['r'],q['c'],late,q['restored'],storage=q['storage'],capture_id=q['capture_id'],role_catalog=q['roles'],frozen_schedule=q['schedule'],authenticate=q['parent'],at=GRADE)


def test_next_week_reuses_exact_epoch_P2_and_deadline_with_no_old_losses(packet,tmp_path):
    q=packet;d=qualify(q,grade(q,tmp_path/'grade'))
    stamp=GRADE+timedelta(minutes=3);slate=next_slate(8,'2026-10-29T20:00:00Z')
    full=[dict(season=2026,week=8,game_type='REG',game_id='fictional-week-8',kickoff_utc='2026-10-29T20:00:00Z')]
    selected=g.select_next(q['r'],d,slate,q['c'],full_schedule=full,authenticate=q['parent'],clock=lambda:stamp)
    expected=epoch.select_next_week(q['r'],g.history(d,q['r'],at=stamp),slate,q['c'],clock=lambda:stamp)
    assert selected.document==expected.document
    rec=next(s for s in selected.document['choice']['selections'] if s['decision']['category']=='rec')
    assert rec['members'][0]['method_id']=='LAB_CDF' and rec['evidence']['scores']['COUNT_A']==100
    assert rec['evidence']['all_negative_weeks_retained']
    with pytest.raises(ValueError,match='deadline'):
        g.select_next(q['r'],d,slate,q['c'],full_schedule=full,authenticate=q['parent'],clock=lambda:state.utc(slate['weekly_deadline_utc']))


@pytest.mark.parametrize('values',[(0,0,0),(1,2,3),(9,10,11),(10,10,10)])
def test_hand_loss_and_bias_properties_over_fixed_cohort(packet,tmp_path,values):
    q=packet;d=qualify(q,grade(q,tmp_path/'grade',batch(q,actuals=values)))
    m=next(m for m in g.report(d,q['r'],at=GRADE+timedelta(minutes=3))['metrics'] if (m['category'],m['method_id'])==('rec','COUNT_A'))
    assert m['primary_loss']==sum((10-v)**2 for v in values)/3
    assert m['signed_bias']==sum(10-v for v in values)/3
    assert m['primary_loss']>=m['signed_bias']**2-1e-12


def test_restored_metadata_requires_new_live_parent_auth_and_changed_inputs_reject(packet,tmp_path):
    q=packet;snapshot=grade(q,tmp_path/'grade')
    restored=g.restore_snapshot(q['storage'],snapshot.binding,q['r'],authenticate=q['parent'],at=GRADE)
    assert restored.document==snapshot.document
    with pytest.raises(g.GradeError,match='AUTHENTICATION_REJECTED'):
        g.restore_snapshot(q['storage'],snapshot.binding,q['r'],authenticate=lambda request:False,at=GRADE)
    snapshot.document['fits']=1
    with pytest.raises(g.GradeError,match='INPUT_CHANGED'):qualify(q,snapshot)


def test_cli_contract_is_preparation_only(tmp_path,capsys):
    assert cli.main(['contract','--output',str(tmp_path/'contract.json')])==0
    assert cli.main(['execute'])==2
    doc=cp.strict_json((tmp_path/'contract.json').read_bytes())
    assert doc['state']=='PREPARED_UNREGISTERED' and doc['local_grading_is_durable'] is False


def test_partial_failure_archive_cannot_qualify_any_successful_forecast(packet,tmp_path):
    q=packet;restored=deepcopy(q['restored']);restored.update(state='PRIVATE_FAILURE_ARCHIVE_RESTORED',validation=dict(qualified_selected=False))
    capture=q['bind'](restoration=restored)
    assert not capture.document['ready'] and capture.document['pending_reason']=='PARTIAL_CAPTURE_NEVER_QUALIFIES'
    q=dict(q,capture=capture)
    durable=qualify(q,grade(q,tmp_path/'grade'))
    report=g.report(durable,q['r'],at=GRADE+timedelta(minutes=3))
    assert not report['metrics']
    assert all(w['state']=='PENDING_COMPLETE_QUALIFIED_CAPTURE_POPULATION' for w in report['pending_weeks'])
    assert len(durable.document['captures'][0]['forecasts'])==72


def test_provider_callback_failure_is_original_and_not_retried(packet):
    calls=[];failure=RuntimeError('FICTIONAL_PROVIDER_INTERRUPTION')
    def collect(request):calls.append(request);raise failure
    with pytest.raises(RuntimeError) as caught:
        g.acquire([packet['capture']],collect=collect,authenticate=packet['parent'],clock=lambda:GRADE)
    assert caught.value is failure and len(calls)==1
    assert calls[0]['retries']==0 and calls[0]['research_or_tuning'] is False


def test_later_durability_cannot_enter_an_earlier_weekly_decision(packet,tmp_path):
    q=packet;local=grade(q,tmp_path/'grade')
    next_week=next_slate(8,'2026-10-29T20:00:00Z');decision=state.utc('2026-10-28T10:00:00Z')
    durable=qualify(q,local,at=decision+timedelta(minutes=1))
    full=[dict(season=2026,week=8,game_type='REG',game_id='fictional-week-8',kickoff_utc='2026-10-29T20:00:00Z')]
    selected=g.select_next(q['r'],durable,next_week,q['c'],full_schedule=full,authenticate=q['parent'],clock=lambda:decision)
    rec=next(s for s in selected.document['choice']['selections'] if s['decision']['category']=='rec')
    assert not rec['evidence']['scores'] and rec['members'][0]['method_id']=='COUNT_A'
    assert selected.document['resolved_prior_keys']==[]


def test_durability_callback_cannot_reuse_writer_job_as_reader(packet,tmp_path,monkeypatch):
    q=packet;local=grade(q,tmp_path/'grade');original=g.confirm_durable
    def repeat(snapshot,proof,**kwargs):
        proof=deepcopy(proof);proof['reader']['api_job_id']=proof['producer']['api_job_id']
        return original(snapshot,proof,**kwargs)
    monkeypatch.setattr(g,'confirm_durable',repeat)
    with pytest.raises(g.GradeError,match='DISTINCT_CURRENT_RUN'):qualify(q,local)


def test_modified_snapshot_physical_binding_never_qualifies(packet,tmp_path):
    q=packet;local=grade(q,tmp_path/'grade');local.binding['sha256']='f'*64
    with pytest.raises(g.GradeError,match='BYTE_BINDING_CHANGED'):qualify(q,local)


def test_interrupted_local_revisions_first_qualify_together_without_fake_clocks(packet,tmp_path):
    q=packet;pending=grade(q,tmp_path/'pending')
    later=GRADE+timedelta(hours=2)
    corrected=batch(q,actuals=(10,10,10),publication='2026-10-28T09:00:00Z',at=later)
    recovered=grade(q,tmp_path/'recovered',corrected,previous=pending,at=later)
    durable=qualify(q,recovered,at=later+timedelta(minutes=2))
    view=g.history(durable,q['r'],at=later+timedelta(minutes=3))
    outcomes=[r for r in view['bundle']['outcomes'] if r['category']=='rec']
    assert all(r['revision']==2 and r['coqualified_prior_revisions']==[1] for r in outcomes)
    assert len({r['available_at'] for r in outcomes})==1
    assert len(durable.document['versions'])==2


def test_next_process_reuses_authenticated_retained_capture_without_reopening_body(packet,tmp_path,monkeypatch):
    q=packet;local=grade(q,tmp_path/'grade')
    restored=g.restore_snapshot(q['storage'],local.binding,q['r'],authenticate=q['parent'],at=GRADE)
    monkeypatch.setattr(g.archive,'read_owned',lambda *a,**kw:pytest.fail('reopened original private body'))
    captures=g.retained_captures(restored,q['r'],at=GRADE)
    assert [c.sha256 for c in captures]==[q['capture'].sha256]
    request=g.provider_request(captures,at=GRADE)
    assert request['scope']=='FIXED_COMPLETED_GAME_OPERATIONAL_GRADING_ONLY'


def test_routine_week_uses_full_Thursday_deadline_not_initial_Sunday_remainder(packet,tmp_path):
    q=packet;durable=qualify(q,grade(q,tmp_path/'grade'));stamp=GRADE+timedelta(minutes=3)
    full=[dict(season=2026,week=8,game_type='REG',game_id=name,kickoff_utc=kickoff) for name,kickoff in
        [('fictional-thursday','2026-10-29T20:00:00Z'),('fictional-sunday','2026-11-01T20:00:00Z')]]
    from nfl_lab import weekly_generic_producer as generic
    slate=generic.prepare_slate(full,season=2026,week=8,game_cutoffs={r['game_id']:(state.utc(r['kickoff_utc'])-timedelta(hours=1)).isoformat() for r in full},now=stamp)
    selected=g.select_next(q['r'],durable,slate,q['c'],full_schedule=full,authenticate=q['parent'],clock=lambda:stamp)
    assert state.utc(selected.document['slate']['weekly_deadline_utc'])==state.utc('2026-10-29T14:00:00Z')
    remaining=deepcopy(slate);remaining.update(weekly_deadline_utc='2026-11-01T14:00:00Z',scheduled_first_kickoff_utc='2026-11-01T20:00:00Z')
    with pytest.raises(g.GradeError,match='CANNOT_INHERIT_INITIAL_REMAINDER'):
        g.select_next(q['r'],durable,remaining,q['c'],full_schedule=full,authenticate=q['parent'],clock=lambda:stamp)


def test_actual_runtime_serializer_full_epoch_choice_required_partial_projection_rejected(packet):
    q=packet
    actual=runtime.read_owned(q['storage'],q['serialized_choice'])
    assert actual['schema_version']==epoch.VERSION+'-choice'
    assert actual==q['c'].document and actual!=q['c'].document['choice']
    assert q['capture'].document['ready'] is True
    partial=g.archive.write(q['storage'],q['base']/'wrong-partial-choice.json',actual['choice'])
    wrong=deepcopy(q['restored']);wrong['aliases']['runtime/WEEKLY_CHOICE.json']=partial
    with pytest.raises(g.GradeError,match='EXACT_ARCHIVED_FROZEN_CHOICE'):q['bind'](restoration=wrong)
    assert runtime.read_owned(q['storage'],q['serialized_choice'])==actual


def test_actual_retained_restore_contract_preserves_historical_and_recovery_clocks(chain):
    # Real retained.restore/native protocol with injected HTTP and separately
    # fictional job identities. No schema cast to archive-restored is made.
    restored=execute_retained(chain);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    before=deepcopy(restored)
    evidence=g._retained_evidence(restored,chain.p.storage,at)
    assert set(restored)==g.RETAINED_KEYS
    assert restored['schema_version']==retained.VERSION+'-result'
    assert evidence['known_by']==max(evidence['original_clocks'],key=state.utc)
    assert state.utc(evidence['known_by'])<state.utc(evidence['recovery_completed_at'])
    assert evidence['current_root_go_sha256']==restored['current_root_go_sha256']
    assert restored==before
    assert all(p['run_id']==restored['current']['run_id'] for p in restored['current_restore_proofs'])
    assert all(p['run_id']==restored['original_archive']['run_id'] for p in restored['historical_reader_witness']['proofs'])
    forged=deepcopy(restored);forged['historical_reader_witness']['actual_completed_at']=restored['created_at_utc']
    with pytest.raises(g.GradeError,match='ORIGINAL_RETAINED_WITNESS'):g._retained_evidence(forged,chain.p.storage,at)
    forged=deepcopy(restored);forged['current_restore_proofs'][0]['payload_sha256']='0'*64
    with pytest.raises(g.GradeError,match='ALL_CURRENT_RETAINED'):g._retained_evidence(forged,chain.p.storage,at)


def test_retained_binding_requires_live_new_authority_before_any_alias_decode(packet,monkeypatch):
    q=packet
    # A saved result header is never authority, even if it claims success.
    candidate=dict(schema_version=retained.VERSION+'-result',state='PRIVATE_PRIOR_CAPTURE_RESTORED')
    monkeypatch.setattr(g.archive,'read_owned',lambda *a,**kw:pytest.fail('decoded before live retained authority'))
    with pytest.raises(g.GradeError,match='AUTHENTICATION_REJECTED'):
        q['bind'](restoration=candidate,auth=lambda request:False)
    assert candidate['schema_version']==retained.VERSION+'-result'


def test_manual_capture_cannot_get_posthoc_population_and_empty_week8_uses_startup(packet):
    q=packet;prepared=g.population_template(q['r'],q['c'])
    with pytest.raises(g.GradeError,match='ISSUANCE_POPULATION'):
        g.bind_population(prepared,q['r'],q['c'],authenticate=q['parent'],at=GRADE)
    late=deepcopy(q['pop']);late['registered_at']=GRADE.isoformat()
    population=g.bind_population(late,q['r'],q['c'],authenticate=q['parent'],at=GRADE)
    with pytest.raises(g.GradeError,match='BEFORE_SOURCE_VALUES'):
        g.bind_capture(q['r'],q['c'],population,q['restored'],storage=q['storage'],capture_id=q['capture_id'],role_catalog=q['roles'],
            frozen_schedule=q['schedule'],authenticate=q['parent'],at=GRADE)
    empty=dict(schema_version=epoch.VERSION+'-history',epoch_sha256=q['e'].sha256,legacy_history_binding=q['e'].origin['history_binding'],
        bundle=dict(schema_version=g.selector.VERSION,offers=[],forecasts=[],outcomes=[],decisions=[],weeks=[]))
    next_choice=epoch.select_next_week(q['r'],empty,next_slate(8,'2026-10-29T20:00:00Z'),q['c'],clock=lambda:GRADE)
    rec=next(x for x in next_choice.document['choice']['selections'] if x['decision']['category']=='rec')
    assert rec['members'][0]['method_id']=='COUNT_A' and not rec['evidence']['scores']
    assert next_choice.document['resolved_prior_keys']==[] and empty['bundle']['offers']==[]
    assert len(q['schedule'])==3 and 'fictional-elapsed' not in {x['original_game_id'] for x in q['capture'].document['opportunities']}


def _clock_metadata_table(kind, values):
    clocks = pa.array(values, type=kind)
    count = len(values)
    fields = {name: [1 if name in ('season', 'week') else 'fictional'] * count
        for name in g.grading.METADATA if name not in ('kickoff_utc', 'cutoff_utc')}
    table = pa.table(fields)
    return table.append_column('kickoff_utc', clocks).append_column('cutoff_utc', clocks)


def test_clock_projection_preserves_original_units_offsets_and_nanoseconds():
    # Literal references include negative epoch time and fractions datetime
    # cannot represent; the production helper does not supply these answers.
    expected = {-1: '1969-12-31T23:59:59.999999999+00:00',
        0: '1970-01-01T00:00:00+00:00',
        1: '1970-01-01T00:00:00.000000001+00:00',
        1000: '1970-01-01T00:00:00.000001+00:00',
        123456789: '1970-01-01T00:00:00.123456789+00:00'}
    epoch_start = datetime(1970, 1, 1, tzinfo=timezone.utc)
    # Both occurrences of Chicago's repeated autumn hour remain distinct.
    fall = []
    for text in ['2026-11-01T06:30:00+00:00', '2026-11-01T07:30:00+00:00']:
        delta = datetime.fromisoformat(text) - epoch_start
        ns = (delta.days * 86400 + delta.seconds) * 1000000000 + 1
        fall.append(ns)
        expected[ns] = text[:-6] + '.000000001+00:00'
    for zone in ['UTC', 'America/Chicago', '+05:30']:
        for unit in ['s', 'ms', 'us', 'ns']:
            values = list(expected) if unit == 'ns' else [-1, 0, 1, 123456789]
            table = _clock_metadata_table(pa.timestamp(unit, tz=zone), values)
            stream = io.BytesIO(); pq.write_table(table, stream)
            parquet = pq.ParquetFile(io.BytesIO(stream.getvalue()))
            legacy = parquet.read(columns=list(g.grading.METADATA)).to_pylist()
            for row in legacy:
                for key in ['kickoff_utc', 'cutoff_utc']:
                    row[key] = state.utc(row[key]).isoformat()
            actual = g._query_metadata(parquet)
            assert actual == legacy
            if unit == 'ns':
                assert [r['kickoff_utc'] for r in actual] == [expected[v] for v in values]


def test_clock_projection_rejects_missing_and_timezone_free_clocks():
    for kind, values in [(pa.timestamp('ns'), [0]),
            (pa.timestamp('ns', tz='UTC'), [None])]:
        table = _clock_metadata_table(kind, values)
        stream = io.BytesIO(); pq.write_table(table, stream)
        with pytest.raises(ValueError):
            g._query_metadata(pq.ParquetFile(io.BytesIO(stream.getvalue())))


def test_clock_projection_cold_process_keeps_pandas_unloaded(tmp_path):
    import json
    import subprocess
    import sys
    table = _clock_metadata_table(pa.timestamp('ns', tz='America/Chicago'), [-1, 0, 1])
    path = tmp_path / 'fictional-nanosecond-clocks.parquet'; pq.write_table(table, path)
    script = '''import sys,json,resource,signal
sys.path.insert(0,sys.argv[1])
resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20));signal.alarm(30)
from nfl_lab import audit_weekly_grade_v1 as grade
import pyarrow.parquet as pq
rows=grade._query_metadata(pq.ParquetFile(sys.argv[2]))
assert 'pandas' not in sys.modules
from pathlib import Path
threads=next(int(line.split(':',1)[1]) for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('Threads:'))
assert threads<=3, 'Metadata decoding exceeded the two numerical threads plus its caller'
assert rows[2]['kickoff_utc']=='1970-01-01T00:00:00.000000001+00:00'
print(json.dumps(dict(rows=len(rows),pandas_loaded=False)))
'''
    profile = json.loads((ROOT/'config/audit-weekly-numerical-runtime-v1.json').read_bytes())['environment']
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(ROOT), str(path)],
        env=profile, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(rows=3, pandas_loaded=False)
