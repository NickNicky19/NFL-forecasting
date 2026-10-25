"""Fictional source/epoch/captures, injected HTTP and real owned-byte checks."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from contextlib import redirect_stdout
import base64
import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nfl_lab import audit_weekly_public_v1 as p, audit_weekly_archive_v1 as archive
from nfl_lab import audit_weekly_epoch_v1 as epoch,weekly_generic_producer as generic,weekly_adaptive as selector
from nfl_lab import private_draft_store as store,gha_private_checkpoint as cp
from tools import audit_weekly_public_v1 as cli
from test_audit_weekly_archive_v1 import capture as archive_capture,Service,ROLES,RUN,SOURCE,produce
from test_audit_weekly_epoch_v1 import fixture as epoch_fixture


def build_packet(tmp_path,parameter=None):
    original=archive_capture.__wrapped__(tmp_path)
    storage=original.storage;stamp=original.stamp
    ts=lambda seconds:(stamp+timedelta(seconds=seconds)).isoformat()
    put=original.put
    f=epoch_fixture(active_reference=False)
    deadline=-5 if parameter=='late_proof' else 3600
    schedule=[dict(season=2026,week=7,game_type='REG',game_id=name,kickoff_utc=ts(seconds))
        for name,seconds in [('fictional-elapsed',-86400),('fictional-future',7200),('fictional-monday',86400)]]
    slate=generic.prepare_slate(schedule,season=2026,week=7,game_cutoffs={g['game_id']:(p.feed.utc(g['kickoff_utc'])-timedelta(hours=1)).isoformat() for g in schedule},
        now=stamp-timedelta(days=2))
    history=dict(schema_version=selector.VERSION,offers=[],forecasts=[],outcomes=[],decisions=[],weeks=[])
    old_choice=generic.freeze_choices(selector,history,f['catalog'],f['policy'],slate,actual_choice_at=stamp-timedelta(days=2))
    old_raw=store.canonical(old_choice)+b'\n'
    old_completion=dict(schema_version=generic.VERSION+'-weekly-choice-completion',choice_binding=dict(path='/fictional/original/choice',bytes=len(old_raw),sha256=store.sha(old_raw)),
        persisted_completed_at=(stamp-timedelta(days=2)+timedelta(seconds=1)).isoformat(),original_predeadline_completion=None)
    corrected=epoch.prepare_epoch(old_raw,old_completion,slate,f['catalog'],f['policy'],f['replay'],history_binding=f['history_binding'],clock=lambda:stamp-timedelta(seconds=300))
    eref=put('public-context/epoch.json',corrected.document)
    er=epoch.owned_cas_readback(storage,{'epoch':eref},{'epoch':corrected.document},scope='EPOCH_METADATA',written_at=ts(-299),clock=lambda:stamp-timedelta(seconds=298))
    registration=dict(schema_version=epoch.VERSION+'-registration-completion',epoch_sha256=corrected.sha256,catalog_sha256=p.feed.digest(corrected.document['catalog']),
        selection_recipe_sha256=p.feed.digest(corrected.document['selection_recipe']),persisted_completed_at=er['readback_completed_at'],
        owner_registration_sha256='b'*64,qualified_artifact_restore=dict(scope='EFFECTIVE18_MODELS_ONLY',proof_sha256='c'*64,replay_catalog_sha256=p.feed.digest(f['replay']),model_pairs=18),
        metadata_cas_readback=er,metadata_remote_durability_qualified=False,current_values_used=False,fits=0)
    registered=epoch.bind_registration(corrected,registration,now=stamp-timedelta(seconds=297))
    choice=epoch.continue_week(registered,schedule,{g['game_id']:ts(deadline if g['game_id']=='fictional-future' else 82800) for g in schedule if g['game_id']!='fictional-elapsed'},
        clock=lambda:stamp-timedelta(seconds=290))
    replay=deepcopy(f['replay']);replay.update(source_sha=SOURCE,run_id=RUN)
    for slot in replay['slots']:slot['manifest_sha256']=p.feed.digest(['fictional-relocated',slot['target'],slot['method_id']])
    artifacts=epoch.artifact_catalog(corrected,replay)
    versions=epoch.selected_versions(registered,choice,relocated_replays=(replay,),now=stamp-timedelta(seconds=280))
    refs=dict(choice=put('public-prepared/choice.json',choice.document),selected_versions=put('public-prepared/versions.json',versions),
        artifact_catalog=put('public-prepared/artifacts.json',artifacts),recipe=put('public-prepared/recipe.json',{'schema_version':archive.RUNTIME+'-recipe'}),
        relocated_replay=put('public-prepared/replay.json',replay))
    cr=epoch.owned_cas_readback(storage,{k:refs[k] for k in ('choice','selected_versions')},dict(choice=choice.document,selected_versions=versions),
        scope='CHOICE_AND_SELECTED_VERSIONS',written_at=ts(-270),clock=lambda:stamp-timedelta(seconds=269))
    completion=dict(schema_version=epoch.VERSION+'-choice-completion',choice_sha256=choice.sha256,catalog_sha256=versions['catalog_sha256'],selected_versions_sha256=p.feed.digest(versions),
        persisted_completed_at=cr['readback_completed_at'],metadata_cas_readback=cr,
        qualified_artifact_restore=dict(scope='EFFECTIVE18_MODELS_ONLY',proof_sha256='c'*64,replay_catalog_sha256=p.feed.digest(replay),model_pairs=18),
        metadata_remote_durability_qualified=False,current_values_used=False)
    completion_ref=put('public-prepared/completion.json',completion)
    prepared=put('public-prepared/PREPARED.json',dict(schema_version=archive.RUNTIME+'-prepared',refs=refs,choice_completion=completion_ref,current_values_used=False))
    source=archive.read_owned(storage,original.context['source']);source['prepared']=prepared
    source_ref=put('public-context/source.json',source)
    context=dict(original.context,epoch=eref,epoch_registration=put('public-context/registration.json',registration),
        original_choice=original.body('public-context/original-choice.json',old_raw),original_slate=put('public-context/original-slate.json',slate),
        original_catalog=put('public-context/original-catalog.json',f['catalog']),original_policy=put('public-context/original-policy.json',f['policy']),
        prepared=prepared,source=source_ref)
    root=original.base/'public-runtime';storage.register_root(root)
    changed={'WEEKLY_CHOICE.json','ARTIFACT_CATALOG.json','SELECTED_VERSION_CATALOG.json','RUNTIME_RECIPE.json','IDENTITY_BRIDGE.json',
        'FINISHED.json','EXPORT_INPUTS.json','CANDIDATES.json','features.parquet','features.capture.json','queries.parquet','selected.jsonl.gz','selected.jsonl.completion.json'}
    for file in original.root.rglob('*'):
        if file.is_file() and file.name!='.operational-storage-owner' and file.relative_to(original.root).as_posix() not in changed \
            and not file.relative_to(original.root).as_posix().startswith(('candidates/','model-status/')):
            storage.import_file(file,root/file.relative_to(original.root),expected_sha256=cp.binding(file)['sha256'])
    def save(name,doc):return archive.write(storage,root/name,doc)
    for name,doc in [('WEEKLY_CHOICE.json',choice.document),('ARTIFACT_CATALOG.json',artifacts),('SELECTED_VERSION_CATALOG.json',versions),('RUNTIME_RECIPE.json',{'schema_version':archive.RUNTIME+'-recipe'})]:save(name,doc)
    frame=dict(season=[2026,2026],week=[7,7],game_id=['fictional-future']*2,player_id=['00-0000001','00-0000002'],position=['QB','QB'],
        cutoff_utc=[ts(deadline)]*2,kickoff_utc=[ts(7200)]*2,feature_max_source_available_utc=[ts(-86400)]*2,f_fixture=[0.,1.])
    for name in ('features.parquet','queries.parquet'):
        out=io.BytesIO();pq.write_table(pa.table(frame),out);storage.write_bytes(root/name,out.getvalue())
    feature_ref=cp.binding(root/'features.parquet');query_ref=cp.binding(root/'queries.parquet')
    feature_capture=save('features.capture.json',dict(schema_version='weekly-feature-capture-v1',source_contract={'source_policy_sha256':cp.POLICY_SHA},feature_binding=feature_ref,feature_persist_completed_at=ts(-40)))
    identities=[]
    for i in range(2):
        ident=dict(gsis_id='00-'+str(i+1).zfill(7),gsis_game_id='fictional-future',sleeper_id=str(1234+i),website_player_id=str(1234+i),website_game_id='9876',
            team='A' if i==0 else 'B',opponent='B' if i==0 else 'A',kickoff_utc=ts(7200),query_source_sha256=query_ref['sha256'],schedule_source_sha256='d'*64,
            identity_bridge_kind='EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES',actual_visible_board_compatibility='NOT_YET_CHECKED')
        ident['identity_binding_sha256']=p.feed.digest(ident);identities.append(ident)
    bridge=save('IDENTITY_BRIDGE.json',dict(identities=identities,visible_board_match='NOT_YET_CHECKED',name_matching=False))
    slots=[]
    for target,family,method in cp.JOBS:
        base=f'candidates/{target}/{method}';candidate_rows=[]
        for i in range(2):candidate_rows.append(dict(offered_id=p.feed.digest([target,i]),category=target,method_id=method,attempt_qualified=True,evidence_lane='original_pregame',
            scientific_qualification=False,source_capture_completed_at=ts(-40),issued_at=ts(-30),cutoff_utc=ts(deadline),kickoff_utc=ts(7200),forecast_value=0.,operational_eligible=True))
        storage.write_bytes(root/(base+'.jsonl.gz'),gzip.compress(b''.join(store.canonical(r)+b'\n' for r in candidate_rows),mtime=0))
        receipt=dict(state='PERSISTED',rows=2,binding=cp.binding(root/(base+'.jsonl.gz')),persist_started_at=ts(-31),completed_at=ts(-29))
        save(base+'.jsonl.completion.json',receipt)
        status=dict(target=target,method_id=method,state='CAPTURED',failure=None,attempt_qualified=True,expected_rows=2,issued_rows=2,unissued_offered_ids=[],persistence=receipt)
        save(f'model-status/{target}-{method}.json',status);slots.append(status)
    candidates=save('CANDIDATES.json',dict(slots=slots))
    selected_choice=next(s for s in choice.document['choice']['selections'] if s['decision']['category']=='pass_att')
    version=next(s['manifest_sha256'] for s in replay['slots'] if s['target']=='pass_att' and s['method_id']=='LAB_CDF')
    selected=[]
    for i,ident in enumerate(identities):
        components=[dict(method_id='LAB_CDF',model_version=version,weight=1.,value=float(i))]
        model=p.feed.digest([(c['method_id'],c['model_version'],c['weight']) for c in components])
        issued=next(r for r in versions['rows'] if r['category']=='pass_att' and r['model_version']==model)
        selected.append(dict(ident,player_id=ident['gsis_id'],game_id=ident['gsis_game_id'],category='pass_att',method_id='P2_SELECTED',
            offered_id=p.feed.digest(dict(season=2026,week=7,game_id=ident['gsis_game_id'],player_id=ident['gsis_id'],category='pass_att')),
            model_version=model,procedure_version=issued['procedure_version'],product='point_mean',prediction_functional='expected_mean',forecast_value=float(i),
            components=components,source_policy_sha256=cp.POLICY_SHA,selection_sha256=p.feed.digest(selected_choice),horizon='player_game',season=2026,week=7,position='QB',
            source_capture_completed_at=ts(-40),issued_at=ts(-20),cutoff_utc=ts(deadline),source_cutoff_utc=ts(deadline),
            evidence_lane='original_pregame',operational_eligible=True,correction_epoch_sha256=corrected.sha256,scientific_qualification=False,public_export_authorized=False))
    if parameter=='bad_weight':selected[0]['components'][0]['weight']=.5
    storage.write_bytes(root/'selected.jsonl.gz',gzip.compress(b''.join(store.canonical(r)+b'\n' for r in selected),mtime=0))
    selected_ref=cp.binding(root/'selected.jsonl.gz');selected_completion=dict(state='PERSISTED',rows=2,binding=selected_ref,persist_started_at=ts(-21),completed_at=ts(-19))
    selected_completed=save('selected.jsonl.completion.json',selected_completion)
    terminal=save('FINISHED.json',dict(schema_version=archive.RUNTIME+'-result',state='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE',fits=0,searches=0,scores=0,
        public_release=False,public_export_authorized=False,epoch_sha256=corrected.sha256,choice_sha256=choice.sha256,actual_completed_at=ts(-10),prediction_rows=36,query_rows=2,selected=selected_completion))
    save('EXPORT_INPUTS.json',dict(schema_version=archive.RUNTIME+'-private-handoff',terminal=terminal,selected=selected_ref,completion=selected_completed,identity_bridge=bridge,
        recipe=cp.binding(root/'RUNTIME_RECIPE.json'),choice=cp.binding(root/'WEEKLY_CHOICE.json'),artifact_catalog=cp.binding(root/'ARTIFACT_CATALOG.json'),selected_version_catalog=cp.binding(root/'SELECTED_VERSION_CATALOG.json'),public_export_authorized=False))
    board=dict(season=2026,week=7,games=[dict(id='9876',kickoff=ts(7200),state='pre')],players=[dict(id=str(1234+i),game_id='9876',team='A' if i==0 else 'B',opp='B' if i==0 else 'A',pos='QB',props=[dict(key='pass_att',proj=20)]) for i in range(2)])
    if parameter=='role_mismatch':board['players'][1]['pos']='RB'
    board_body=store.canonical(board)
    board_ref=original.body('current-reference/output/data/week.json',board_body)
    native=original.body('current-reference/native.json.gz',gzip.compress(b'{"fictional_native":true}',mtime=0))
    state=put('current-reference/state.json',dict(files={'output/data/week.json':board_ref}))
    rprepared=put('current-reference/prepared.json',dict(permit=dict(epoch_sha256=corrected.sha256,choice_sha256=choice.sha256,actual_capture_authorized_at=ts(-80)),
        slate=dict(game_cutoffs=dict(fictional=ts(deadline)))))
    rcontrols=put('current-reference/control_rows.json',{'rows':[],'actual_issued_at':ts(-51)})
    worker=dict(state='ORIGINAL_R0_DEFAULT_PROCEDURE_CAPTURED',native=native,board=board_ref,next_state=state,source_observations=[],
        fixed_original_default_refresh=True,actual_source_completed_at=ts(-55),actual_native_observed_at=ts(-54),
        actual_native_persist_completed_at=ts(-53.5),actual_completed_at=ts(-53))
    put('current-reference/WORKER_COMPLETE.json',worker)
    rcompletion=put('current-reference/control_completion.json',dict(schema_version='audit-reference-capture-v1-control-completion',forecast_binding=rcontrols,
        source_receipt_sha256=store.sha(store.canonical(worker)),original_native_persist_completed_at=ts(-53.5),actual_issued_at=ts(-51),
        body_persist_completed_at=ts(-50),remote_durability_qualified=False,public_release=False))
    reference=put('current-reference/CAPTURE_COMPLETE.json',dict(schema_version='audit-reference-capture-v1-capture',state='ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE',
        prepared=rprepared,native=native,original_board=board_ref,next_state=state,control_forecast_rows=rcontrols,control_completion=rcompletion))
    original.root=root;original.context=context
    service=Service(original.base)
    workflow=b'name: fictional-only\njobs: fictional_capture_writer fictional_capture_reader fictional_capture_exporter\npermissions: contents:write actions:read\n'
    transport=service.transport
    def api(request,timeout):
        if '/contents/.github/workflows/lab.yml?ref=' in request.full_url:
            from test_private_draft_store_v2 import Response
            actual=b'FICTIONAL_WRONG_WORKFLOW' if getattr(service,'bad_workflow',False) else workflow
            return Response(dict(type='file',path='.github/workflows/lab.yml',encoding='base64',content=base64.b64encode(actual).decode()))
        result=transport(request,timeout)
        if '/actions/runs/'+RUN+'/jobs?' in request.full_url:
            from test_private_draft_store_v2 import Response
            data=cp.strict_json(result.body)
            for job in data['jobs']:
                if job['status']=='in_progress':job['conclusion']=None
                if job['id']==778 and service.writer_completed is not None:job['started_at']=service.writer_completed.isoformat()
                if job['id']==779 and service.reader_completed is not None:job['started_at']=service.reader_completed.isoformat()
            return Response(data)
        return result
    service.transport=api
    policy=p.policy_template();policy.update(state='ROOT_REGISTERED',registered_at_utc=ts(-400),source_sha=SOURCE,source_branch='fictional',workflow_sha256=store.sha(workflow),jobs=ROLES,
        origin_choice_sha256=corrected.origin['choice_file']['sha256'],rights_authorities=['e'*64],
        engine_sha256={k:'f'*64 for k in p.feed.ENGINE_FILES},website_code_sha256={k:'f'*64 for k in p.feed.CODE_FILES})
    policy['approved_candidates']=[{k:s[k] for k in ('target','family','method_id','procedure_version')} for s in f['replay']['slots']]
    policy['public_roles']={t:['QB'] if t.startswith('pass_') else ['RB','WR','TE'] for t in cp.TARGETS}
    policy['publication_authority'].update(state='ROOT_REGISTERED',source_sha=SOURCE,source_branch='fictional',export_job=ROLES['consume'])
    r0=dict(schema_version='weekly-actual-r0-freeze-v1',state='ACTUAL_FIRST_RELEASE_R0_FROZEN',deployment_id=1,deployed_source_sha='f'*40,
        visible_board_sha256=store.sha(b'FICTIONAL_ORIGINAL_OCT24_BOARD'),engine_sha256=policy['engine_sha256'],frozen_at=ts(-500))
    policy['r0_identities']=[p.feed.digest(r0)]
    policy['producer_policy_sha256']=p.recipe_commitment(policy)
    policy['publication_authority']['recipe_registration_sha256']=policy['producer_policy_sha256']
    policy_ref=put('public-context/public_policy.json',policy)
    snapshot=archive.collect(root,context,storage=storage,output=original.base/'reference-collection',r0=reference)
    # Parent owns the optional-role collector extension in its actual source.
    # Here the exact extra owned file participates in the real immutable index,
    # transport, census, native readback and exporter proofs without editing the
    # frozen shared collector implementation.
    name='context/public_policy.json';snapshot['files'].append(cp.file_item(policy_ref,name,'control'))
    snapshot['files'].sort(key=lambda f:f['logical_path'])
    snapshot['census']['physical_origins'][name]=policy_ref
    snapshot['census']['logical_files']+=1;snapshot['census']['logical_bytes']+=policy_ref['bytes']
    snapshot['census']['context_roles'].append('public_policy');snapshot['census']['context_roles'].sort()
    handoff,_,_=produce(original,service,snapshot=snapshot)
    service.active='restore'
    restored=archive.restore(handoff,service.factory(original.base/'reader-journal','restore'),service.package,storage=storage,output=original.base/'reader',root_go_sha256='d'*64,pending_census=service.census)
    service.reader_completed=datetime.now(timezone.utc);service.active='consume'
    factory=service.factory(original.base/'export-journal','consume')
    reader=cp.strict_json((original.base/'reader/READER_HANDOFF.json').read_bytes())
    consumed=archive.consume(reader,factory,service.package,storage=storage,output=original.base/'export',root_go_sha256='d'*64,pending_census=service.census)
    client=factory('restore')
    rights=dict(schema_version='weekly-derived-selected-rights-v1',state='SOURCE_REVIEW_ACCEPTED',authority_kind='REGISTERED_SOURCE_RIGHTS_POLICY',
        authority_policy_sha256='e'*64,selected_sha256=selected_ref['sha256'],source_policy_sha256=cp.POLICY_SHA,scope='SELECTED_DERIVED_ONLY',public_fields=list(p.overlay.ROW_FIELDS),reviewed_at=ts(-5))
    return SimpleNamespace(storage=storage,service=service,consumed=consumed,client=client,package=service.package,pending_census=service.census,
        policy=policy,rights=rights,r0=r0,board=board,board_body=board_body,registered=registered,choice=choice,selected=selected,
        original_bytes=(root/'selected.jsonl.gz').read_bytes(),root=root)


@pytest.fixture(scope='module')
def prepared_packet(tmp_path_factory):
    return build_packet(tmp_path_factory.mktemp('fictional-public-proof-chain'))


@pytest.fixture
def packet(request,tmp_path,prepared_packet):
    parameter=getattr(request,'param',None)
    if parameter is not None:return build_packet(tmp_path,parameter)
    q=SimpleNamespace(**vars(prepared_packet))
    for key in ('consumed','package','policy','rights','r0','board','selected'):
        setattr(q,key,deepcopy(getattr(prepared_packet,key)))
    journal=tmp_path/'metadata-journal';journal.mkdir(mode=0o700)
    q.client=archive.Client('ghs_FICTIONAL',RUN,journal=journal,source_sha=SOURCE,job=dict(prepared_packet.client.job),
        transport=q.service.transport,operation='restore',qualification=q.package['qualification'],readonly=True,process=prepared_packet.client.process)
    q.client.bind(q.package['binding'])
    return q


def live(packet):
    q=packet
    return p.verify_live(q.client,q.consumed,q.package,q.policy,q.rights,q.r0,q.board,q.registered,q.choice,
        storage=q.storage,pending_census=q.pending_census,at=datetime.now(timezone.utc).isoformat(),board_body=q.board_body)


def test_genuine_fictional_archive_api_to_exact_V2_wire_keeps_private_flags_and_zeros(packet):
    q=packet;accepted=live(q)
    document=p.export(accepted,at=datetime.now(timezone.utc).isoformat())
    assert document['schema_version']==p.feed.VERSION_V2 and len(document['rows'])==2
    assert document['rows'][0]['forecast_value']==0.
    assert all(set(r)==set(p.overlay.ROW_FIELDS) for r in document['rows'])
    assert (q.root/'selected.jsonl.gz').read_bytes()==q.original_bytes
    assert all(r['public_export_authorized'] is r['scientific_qualification'] is False for r in q.selected)
    assert document['publication']['version_catalog']==accepted.inputs['catalog'].document
    assert document['publication']['source_version_catalog_sha256']==accepted.inputs['catalog'].sha256
    assert accepted.inputs['catalog'].provenance['generic_terminal_claim'] is False
    assert q.r0['visible_board_sha256']!=store.sha(q.board_body)
    assert accepted.record['current_board_sha256']==store.sha(q.board_body)
    assert all(r['persistence_completed_at']==accepted.record['durable_completed_at'] for r in document['rows'])
    assert p.feed.utc(accepted.record['durable_completed_at'])>p.feed.utc(accepted.inputs['completion']['completed_at'])
    import jsonschema
    schema=json.loads((Path(__file__).resolve().parents[1]/'schemas/weekly-derived-selected-feed-v2.json').read_bytes())
    jsonschema.validate(document,schema)


def test_decoded_json_and_saved_acceptance_are_never_authority(packet):
    accepted=live(packet)
    for candidate in (accepted.record,json.loads(json.dumps(accepted.record)),packet.consumed):
        with pytest.raises(p.PublicError,match='IN_MEMORY'):p.export(candidate,at=datetime.now(timezone.utc).isoformat())
    with pytest.raises(p.PublicError,match='LIVE_API_VERIFIER'):p.LiveAcceptance({}, {},object())


@pytest.mark.parametrize('guard',['rights','r0','source','workflow','canary','old_count_procedure'])
def test_metadata_gates_reject_before_selected_decoder(packet,guard):
    q=packet
    if guard=='rights':q.rights['state']='PENDING'
    elif guard=='r0':q.r0['deployment_id']=0
    elif guard=='source':q.client.source_sha='0'*40
    elif guard=='workflow':q.service.bad_workflow=True
    elif guard=='canary':q.package['binding']=dict(q.package['binding'],canary_sha256='0'*64)
    else:q.policy['approved_candidates'][11]['procedure_version']='0'*64
    try:
        with pytest.raises((p.PublicError,store.StoreError,ValueError)):live(q)
    finally:q.service.bad_workflow=False


@pytest.mark.parametrize('packet',['role_mismatch'],indirect=True)
def test_role_mismatch_falls_back_without_changing_or_dropping_private_rows(packet):
    q=packet
    # The NEW archived current board has the conflict. The original frozen R0
    # deployment/board identity is unchanged and does not bind this new board.
    frozen=deepcopy(q.r0)
    accepted=live(q);result=p.export(accepted,at=datetime.now(timezone.utc).isoformat())
    assert len(result['rows'])==1
    assert result['coverage']==dict(private_selected_rows=2,public_rows=1,fallback_counts={'private_ineligible_R0':1})
    assert (q.root/'selected.jsonl.gz').read_bytes()==q.original_bytes
    assert q.r0==frozen


def test_different_unarchived_current_board_cannot_reuse_original_R0_identity(packet):
    q=packet
    q.board['week']=8;q.board_body=store.canonical(q.board)
    with pytest.raises(p.PublicError,match='ARCHIVED_CURRENT'):live(q)


def test_posthoc_policy_clock_or_missing_original_policy_is_not_authority(packet,monkeypatch):
    q=packet;opened=[];original=archive.read_owned
    def read(storage,ref,*args,**kwargs):opened.append(ref['path']);return original(storage,ref,*args,**kwargs)
    monkeypatch.setattr(archive,'read_owned',read)
    q.policy['registered_at_utc']=(p.feed.utc(q.policy['registered_at_utc'])-timedelta(days=1)).isoformat()
    with pytest.raises(p.PublicError,match='ARCHIVED_PREVALUES_PUBLIC_POLICY'):live(q)
    assert q.consumed['aliases']['runtime/selected.jsonl.gz']['path'] not in opened
    q.policy=original(q.storage,q.consumed['aliases']['context/public_policy.json'])
    del q.consumed['aliases']['context/public_policy.json']
    with pytest.raises(p.PublicError,match='ARCHIVED_PREVALUES_PUBLIC_POLICY'):live(q)


@pytest.mark.parametrize('packet',['bad_weight'],indirect=True)
def test_source_family_weight_change_cannot_be_repaired(packet):
    accepted=live(packet)
    with pytest.raises(p.PublicError,match='FAMILIES_WEIGHTS'):p.export(accepted,at=datetime.now(timezone.utc).isoformat())


def test_saved_persistence_or_other_acceptance_inputs_cannot_be_changed(packet):
    accepted=live(packet)
    accepted.inputs['completion']['completed_at']=packet.selected[0]['kickoff_utc']
    with pytest.raises(p.PublicError,match='INPUTS_CHANGED'):p.export(accepted,at=datetime.now(timezone.utc).isoformat())


@pytest.mark.parametrize('packet',['late_proof'],indirect=True)
def test_late_durable_proof_cannot_be_relabelled_as_local_pregame_persistence(packet):
    accepted=live(packet)
    assert p.feed.utc(accepted.record['durable_completed_at'])>p.feed.utc(packet.selected[0]['source_cutoff_utc'])
    with pytest.raises(p.PublicError,match='NO_ELIGIBLE_DERIVED_PUBLIC_ROWS'):p.export(accepted,at=datetime.now(timezone.utc).isoformat())
    assert (packet.root/'selected.jsonl.gz').read_bytes()==packet.original_bytes


def test_preparation_cli_never_decodes_saved_live_facts_or_publishes(tmp_path):
    with redirect_stdout(io.StringIO()):
        assert cli.main(['template','--output',str(tmp_path/'policy.json')])==0
        assert cli.main(['export'])==2
    doc=cp.strict_json((tmp_path/'policy.json').read_bytes())
    assert doc['state']=='PREPARED_UNREGISTERED'
    assert doc['publication_authority']['state']=='PREPARED_UNREGISTERED'
