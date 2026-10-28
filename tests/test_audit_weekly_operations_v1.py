"""Fictional metadata only: no models, outcome panels, HTTP or native authority."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

from nfl_lab import audit_weekly_operations_v1 as o, audit_weekly_grade_v1 as grade
from nfl_lab import audit_weekly_epoch_v1 as epoch, gha_private_checkpoint as cp, state
from nfl_lab import private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from test_audit_weekly_epoch_v1 import fixture, prepare, registered, continuation, CONTINUED
from test_audit_weekly_grade_v1 import packet as grade_packet
import test_audit_weekly_grade_v1 as fictional_grade
from test_audit_weekly_hosted_v1 import failed_first_recovery, pending_failure


@pytest.fixture
def first_future_metadata(tmp_path):
    """Real GET/client guards, invented metadata; no network or outcome body."""
    import json
    from types import SimpleNamespace
    from nfl_lab import audit_weekly_hosted_v1 as hosted, audit_weekly_template_v1 as template
    from test_audit_weekly_hosted_v1 import pending_failure
    seed = pending_failure.__wrapped__(tmp_path)
    root = seed.runner.go
    root.update(operation='RECURRING_CAPTURE', source_sha='b'*40,
        issued_at_utc='2026-10-27T20:00:00Z', expires_at_utc='2026-10-27T21:00:00Z')
    root['effective_epoch'].update(controller_context=dict(
        schema_version='audit-weekly-owner-first-future-primary-v1',
        retained_epoch_sha256='1'*64, retained_choice_sha256='2'*64,
        retained_root_go_sha256='3'*64,
        claim_binding_sha256=store.sha(store.canonical(root['qualified_runtime']['binding']))),
        previous_checkpoint=None, previous_capture=dict(feed_sha256='a'*64,receipt_sha256='b'*64),
        plan=dict(kind='FUTURE_CAPABLE',season=2026,week=8,deadline_utc='2026-10-29T19:45:00Z',
            calendar_sha256='4'*64,game_cutoffs={'fictional-week-8':'2026-10-29T19:45:00Z'}))
    journal=tmp_path/'first-client-journal';journal.mkdir(mode=0o700)
    calls=[];damage={};head='a'*40
    class Response:
        def __init__(self,status,value,headers=None):
            self.status=status;self.body=store.canonical(value)
            self.headers={'content-length':str(len(self.body)),'x-ratelimit-remaining':'100',**(headers or {})}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return self.body[:limit]
    def transport(request,timeout):
        assert request.get_method()=='GET' and request.data is None
        url=request.full_url;calls.append(url)
        if '/git/ref/' in url:
            current='c'*40 if damage.get('changed_head') and len(calls)>1 else head
            return Response(200,dict(ref='refs/heads/lab-state',object=dict(type='commit',sha=current)))
        if '/contents/' in url:
            if damage.get('existing_directory'):return Response(200,[])
            if damage.get('forbidden'):return Response(403,dict(message='Forbidden'))
            headers={'x-ratelimit-remaining':'0'} if damage.get('rate') else {}
            return Response(404,dict(message='Not Found' if not damage.get('malformed') else 'Wrong'),headers)
        assert '/commits?' in url
        return Response(200,[dict(sha='d'*40)] if damage.get('historical_deleted') else [])
    job=dict(execution_lane='github_actions',workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1',
        workflow_sha='b'*40,job_id=hosted.JOBS['produce'],permission='write',event_name='workflow_dispatch',api_job_id=301,run_authenticated=True)
    client=hosted.PendingMetadataClient('ghs_FICTIONAL','300',source_sha='b'*40,journal=journal,
        root_go=root,job=job,operation='metadata',transport=transport)
    client.bind(root['qualified_runtime']['binding'])
    return SimpleNamespace(root=root,client=client,calls=calls,damage=damage,
        at=state.utc('2026-10-27T20:01:00Z'),authorize=lambda:None,template=template)


def test_first_future_requires_actual_get_absence_and_undeleted_history(first_future_metadata):
    q=first_future_metadata
    proof=o.first_primary_absence(q.client,q.root,authenticate=q.authorize,clock=lambda:q.at)
    assert proof.verify(q.root) is proof
    assert proof.document['state_head']=='a'*40
    assert len(q.calls)==6 and sum('/contents/' in u for u in q.calls)==2
    assert sum('/commits?' in u for u in q.calls)==2
    import pickle
    with pytest.raises(o.OperationsError,match='CANNOT_BE_SERIALIZED'):pickle.dumps(proof)
    proof.document['state_head']='e'*40
    with pytest.raises(o.OperationsError,match='INTEGRITY'):proof.verify(q.root)


@pytest.mark.parametrize('damage',['existing_directory','historical_deleted','forbidden','rate','changed_head','malformed'])
def test_first_future_absence_fails_closed_on_actual_metadata(first_future_metadata,damage):
    q=first_future_metadata;q.damage[damage]=True
    with pytest.raises((o.OperationsError,store.StoreError)):
        o.first_primary_absence(q.client,q.root,authenticate=q.authorize,clock=lambda:q.at)
    assert not list(q.client.journal.glob('*.reservation.json'))


def test_first_future_scope_is_closed_future_only_and_namespace_bound(first_future_metadata):
    q=first_future_metadata;t=q.template
    assert t.first_primary_root(q.root)['schema_version']==t.FIRST_PRIMARY
    for edit in (lambda r:r['effective_epoch'].update(previous_checkpoint={'sha256':'a'*64}),
                 lambda r:r['effective_epoch']['plan'].update(kind='GRADE_ONLY'),
                 lambda r:r['effective_epoch']['plan'].update(week=7),
                 lambda r:r['effective_epoch']['controller_context'].update(allow_reset=True),
                 lambda r:r['effective_epoch']['controller_context'].update(claim_binding_sha256='0'*64)):
        bad=deepcopy(q.root);edit(bad)
        with pytest.raises(ValueError):t.first_primary_root(bad)
    ordinary=deepcopy(q.root);ordinary['effective_epoch']['controller_context']=None
    assert t.first_primary_root(ordinary) is None
    with pytest.raises(o.OperationsError):
        o.first_primary_absence(q.client,ordinary,authenticate=q.authorize,clock=lambda:q.at)


def test_first_future_reuses_original_startup_without_synthetic_durable_history(first_future_metadata):
    q=first_future_metadata;f=fixture();r=registered(prepare(f));c=continuation(f,r)
    q.root['effective_epoch']['controller_context'].update(retained_epoch_sha256=r.epoch.sha256,retained_choice_sha256=c.sha256)
    full=_next_calendar();cuts={row['game_id']:(state.utc(row['kickoff_utc'])-timedelta(minutes=15)).isoformat() for row in full}
    q.root['effective_epoch']['plan'].update(calendar_sha256=state.digest(full),game_cutoffs=cuts,deadline_utc=min(cuts.values()))
    proof=o.first_primary_absence(q.client,q.root,authenticate=q.authorize,clock=lambda:q.at)
    before=state.canonical(r.epoch.document);old_choice=state.canonical(c.document)
    choice,plan=o.first_future_plan(r,c,full,q.root,proof,authenticate=lambda _:True,
        cutoff_lead_seconds=900,clock=lambda:q.at)
    assert choice.document['resolved_prior_keys']==[] and plan['history_sha256'] is None
    assert choice.document['epoch_sha256']==r.epoch.sha256
    assert choice.document['legacy_history_binding']==r.epoch.origin['history_binding']
    assert choice.document['slate']['week']==8 and plan['kind']=='FUTURE_CAPTURE'
    assert state.canonical(r.epoch.document)==before and state.canonical(c.document)==old_choice
    assert not choice.document['slate']['elapsed_games']
    with pytest.raises(o.OperationsError,match='DURABLE_CAUSAL_HISTORY_REQUIRED_NO_FALLBACK'):
        o.recurring_plan(r,c,full,authenticate=lambda _:True,cutoff_lead_seconds=900,clock=lambda:q.at)


def test_first_future_claim_is_stable_across_root_clock_and_source_changes(first_future_metadata):
    q=first_future_metadata;t=q.template
    claim=t.first_primary_claim(q.root)
    other=deepcopy(q.root);other.update(source_sha='c'*40,issued_at_utc='2026-10-27T20:02:00Z')
    other['effective_epoch']['controller_context']['retained_choice_sha256']='f'*64
    assert t.first_primary_claim(other)==claim
    assert set(claim)=={'schema_version','epoch_sha256','stream_id'}


def test_recovery_schema_is_closed_and_claim_is_one_successor(failed_first_recovery):
    from nfl_lab import audit_weekly_template_v1 as t
    q=failed_first_recovery
    assert t.first_primary_root(q.root) is None
    assert t.failed_first_recovery_root(q.root)['schema_version']==t.FAILED_FIRST_RECOVERY
    claim=t.failed_first_recovery_claim(q.root);other=deepcopy(q.root)
    other.update(source_sha='c'*40,issued_at_utc='2026-10-27T20:04:00Z')
    other['effective_epoch']['controller_context']['retained_choice_sha256']='f'*64
    assert t.failed_first_recovery_claim(other)==claim
    assert set(claim)=={'schema_version','failed_root_go_sha256','epoch_sha256','stream_id'}
    for field,value in [('old_week8_choice_body_missing',False),('old_forecast_bodies_missing',False),('allow_reset',True)]:
        bad=deepcopy(q.root);bad['effective_epoch']['controller_context'][field]=value
        with pytest.raises(ValueError):t.failed_first_recovery_root(bad)
    for change in ('checkpoint','cutoff_count','pending'):
        bad=deepcopy(q.root)
        if change=='checkpoint':bad['effective_epoch']['previous_checkpoint']={'sha256':'f'*64}
        elif change=='cutoff_count':bad['effective_epoch']['plan']['game_cutoffs'].popitem()
        else:bad['effective_epoch']['pending_post_recovery']['handoffs']=[]
        with pytest.raises(ValueError):t.failed_first_recovery_root(bad)
    with pytest.raises(o.OperationsError):
        o.first_primary_absence(q.client,q.root,authenticate=lambda:None,clock=lambda:q.at)


def test_recovery_freezes_new_startup_methods_not_lost_choice(first_future_metadata,tmp_path):
    from test_audit_weekly_hosted_v1 import pending_failure,_failed_first_recovery_case
    from nfl_lab import audit_weekly_template_v1 as t
    q=first_future_metadata;f=fixture();r=registered(prepare(f));old=continuation(f,r)
    full=[dict(season=2026,week=8,game_type='REG',game_id=f'fictional-{n}',kickoff_utc='2026-10-29T20:00:00+00:00') for n in range(14)]
    cuts={v['game_id']:'2026-10-29T19:45:00+00:00' for v in full}
    plan=dict(kind='FUTURE_CAPABLE',season=2026,week=8,calendar_sha256=state.digest(full),game_cutoffs=cuts,deadline_utc=min(cuts.values()))
    base=tmp_path/'failure';base.mkdir()
    x=_failed_first_recovery_case(pending_failure.__wrapped__(base),calendar_plan=plan,
        original_scope=dict(retained_epoch_sha256=r.epoch.sha256,retained_choice_sha256=old.sha256))
    proof=o.authenticate_failed_first_recovery(x.client,x.root,authenticate=lambda:None,claim_reader=x.claim_reader,clock=lambda:x.at)
    q.root=x.root;q.client.binding=x.client.binding;q.client.source_sha=x.root['source_sha']
    absent=o.failed_first_absence(q.client,q.root,proof,authenticate=lambda:None,clock=lambda:x.at)
    choice,execution=o.failed_first_future_plan(r,old,full,x.root,absent,proof,
        authenticate=lambda _:True,cutoff_lead_seconds=900,clock=lambda:x.at)
    project=lambda c:[s['members'] for s in c.document['choice']['selections']]
    assert project(choice)==project(old) and choice.sha256!=proof.document['original_week8_choice_commitment']['sha256']
    assert state.utc(choice.document['choice']['actual_frozen_at'])==x.at
    assert choice.document['slate']['game_cutoffs']==cuts and choice.document['resolved_prior_keys']==[]
    assert execution['reason']=='OWNER_FAILED_FIRST_RECOVERY_NEW_FUTURE_ISSUE' and execution['fits']==0
    with pytest.raises(o.OperationsError):
        o.first_future_plan(r,old,full,x.root,absent,authenticate=lambda _:True,cutoff_lead_seconds=900,clock=lambda:x.at)
    with pytest.raises(o.OperationsError,match='LIVE_FAILED_FIRST_RECOVERY_REQUIRED'):
        o.failed_first_future_plan(r,old,full,x.root,absent,{},authenticate=lambda _:True,cutoff_lead_seconds=900,clock=lambda:x.at)


def test_calendar_independent_DST_offsets_aliases_and_poison_outcomes():
    raw = ("season,week,game_type,game_id,gameday,gametime,espn,home_team,away_team,home_score\n"
        "2026,7,REG,london,2026-10-25,09:30,111,LA,SF,DO_NOT_PARSE_OUTCOME\n"
        "2026,10,REG,november,2026-11-15,13:00,222,LA,SF,DO_NOT_PARSE_OUTCOME\n").encode()
    a=o.calendar(raw,season=2026,week=7)[0];b=o.calendar(raw,season=2026,week=10)[0]
    assert a["kickoff_utc"]=="2026-10-25T13:30:00+00:00" and b["kickoff_utc"]=="2026-11-15T18:00:00+00:00"
    assert a["home"]=="LAR" and a["away"]=="SF" and a["website_game_id"]=="111"
    assert not any("score" in key or "outcome" in key for key in a)


@pytest.mark.parametrize("day,time",[("2026-03-08","02:30"),("2026-11-01","01:30"),("2026-10-25","")])
def test_unknown_or_DST_ambiguous_kickoff_cannot_be_assumed(day,time):
    raw=("season,week,game_type,game_id,gameday,gametime,espn,home_team,away_team\n"
        f"2026,7,REG,fictional,{day},{time},111,LA,SF\n").encode()
    with pytest.raises(o.OperationsError):o.calendar(raw,season=2026,week=7)


@pytest.mark.parametrize("duplicate",["game","espn"])
def test_complete_calendar_rejects_conflicting_identifiers(duplicate):
    line="2026,7,REG,one,2026-10-25,13:00,111,CHI,GB\n"
    second="2026,7,REG,"+("one" if duplicate=="game" else "two")+",2026-10-25,16:00,"+("222" if duplicate=="game" else "111")+",MIN,DET\n"
    raw=("season,week,game_type,game_id,gameday,gametime,espn,home_team,away_team\n"+line+second).encode()
    with pytest.raises(o.OperationsError,match="UNIQUE_FULL_WEEK"):o.calendar(raw,season=2026,week=7)


def test_closed_context_cannot_carry_values_or_a_self_supplied_private_body():
    value=dict(schema_version=o.CONTEXT_SCHEMA,controller_context=None,
        previous_capture=dict(feed_sha256="a"*64,receipt_sha256="b"*64))
    assert o.context(value)==value
    for key in ("forecast_rows","private_template","root_go"):
        changed=dict(value,**{key:[]})
        with pytest.raises(o.OperationsError,match="CLOSED_RECURRING"):o.context(changed)


def _plan(q, full, at, durable=None):
    return o.recurring_plan(q['r'], q['c'], full, authenticate=q['parent'], durable=durable,
        cutoff_lead_seconds=900, clock=lambda:at)


def _next_calendar():
    return [dict(season=2026, week=8, game_type='REG', game_id='fictional-week-8',
        kickoff_utc='2026-10-29T20:00:00Z')]


def test_fully_elapsed_plan_keeps_original_choice_and_never_invokes_future_calendar(grade_packet, monkeypatch):
    q=grade_packet;before=state.canonical(q['c'].document)
    full=[dict(season=2026,week=7,game_type='REG',game_id=r['game_id'],kickoff_utc=r['kickoff_utc']) for r in q['schedule']]
    monkeypatch.setattr(o.resume,'_calendar',lambda *_:pytest.fail('GRADE_ONLY_CANNOT_ENTER_FUTURE_RESUME'))
    choice,plan=_plan(q,full,fictional_grade.GRADE)
    assert choice is q['c'] and state.canonical(choice.document)==before
    assert set(plan)==o.PLAN_KEYS and plan['kind']=='GRADE_ONLY'
    assert plan['future_game_ids']==[] and plan['capture_allowed'] is plan['publication_allowed'] is False
    assert plan['current_values_used'] is False and plan['fits']==0


@pytest.mark.parametrize('conflict',[False,True])
def test_incomplete_or_conflicting_finality_stays_pending_and_cannot_select_next(grade_packet,tmp_path,conflict):
    q=grade_packet;at=fictional_grade.GRADE
    batches=[fictional_grade.batch(q,final=False)]
    if conflict:batches.append(fictional_grade.batch(q,final=True))
    snapshot=grade.grade(q['r'],[q['capture']],batches,storage=q['storage'],output=tmp_path/'pending',clock=lambda:at)
    durable=fictional_grade.qualify(q,snapshot)
    assert not durable.document['weeks'] and durable.document['pending_weeks']
    assert len(durable.document['finality_records'])==len(batches)
    with pytest.raises(o.OperationsError,match='COMPLETE_PRIOR'):
        _plan(q,_next_calendar(),at+timedelta(minutes=3),durable)


def test_next_week_choice_is_exact_existing_P2_before_values_and_deterministic(grade_packet,tmp_path):
    q=grade_packet;durable=fictional_grade.qualify(q,fictional_grade.grade(q,tmp_path/'resolved'))
    stamp=fictional_grade.GRADE+timedelta(minutes=3);full=_next_calendar()
    choice,plan=_plan(q,full,stamp,durable)
    expected=grade.select_next(q['r'],durable,choice.document['slate'],q['c'],full_schedule=full,
        authenticate=q['parent'],clock=lambda:stamp)
    again,again_plan=_plan(q,full,stamp,durable)
    assert state.canonical(choice.document)==state.canonical(expected.document)==state.canonical(again.document)
    assert plan==again_plan and plan['kind']=='FUTURE_CAPTURE' and plan['history_sha256']==durable.sha256
    assert state.utc(choice.document['choice']['actual_frozen_at'])==stamp<state.utc(choice.document['slate']['weekly_deadline_utc'])
    assert q['f']['old_history']==b'{"weeks":[{"COUNT_A_loss":123456,"LAB_CDF_loss":0,"week":6}]}'


def test_next_week_never_falls_back_to_absent_or_local_history(grade_packet,tmp_path):
    q=grade_packet;local=fictional_grade.grade(q,tmp_path/'local')
    for missing in (None,local,local.document):
        with pytest.raises(o.OperationsError,match='DURABLE_CAUSAL_HISTORY_REQUIRED_NO_FALLBACK'):
            _plan(q,_next_calendar(),fictional_grade.GRADE+timedelta(minutes=3),missing)


def test_late_new_week_and_history_not_yet_durable_are_rejected(grade_packet,tmp_path):
    q=grade_packet;snapshot=fictional_grade.grade(q,tmp_path/'resolved');durable=fictional_grade.qualify(q,snapshot)
    late=state.utc('2026-10-29T19:45:00Z')
    with pytest.raises(ValueError):_plan(q,_next_calendar(),late,durable)
    future=fictional_grade.qualify(q,snapshot,at=fictional_grade.GRADE+timedelta(hours=2))
    with pytest.raises(o.OperationsError,match='DURABLE_BEFORE_ACTUAL_DECISION'):
        _plan(q,_next_calendar(),fictional_grade.GRADE+timedelta(minutes=3),future)


def test_closed_v3_root_plan_does_not_accept_labels_or_execution_flags():
    value=dict(schema_version=o.CONTEXT_V3,controller_context=None,
        previous_capture=dict(feed_sha256='a'*64,receipt_sha256='b'*64),previous_checkpoint=dict(sha256='c'*64),
        plan=dict(kind='GRADE_ONLY',season=2026,week=7))
    assert o.context(value)==value
    for change in ({'outcomes':[]},{'execution_authorized':True},{'week':True},{'kind':'REPLAY_AS_FUTURE'}):
        bad=deepcopy(value);bad['plan'].update(change)
        with pytest.raises(o.OperationsError):o.context(bad)


def model_roles_fixture(tmp_path):
    root=Path(__file__).resolve().parents[1]
    storage=OperationalStorage(tmp_path/"cache",root/"config/operational-source-policy-v2.json",state=tmp_path/"state")
    output=storage.register_root(tmp_path/"metadata");refs=[]
    for n,(target,family,method) in enumerate(cp.JOBS):
        roles=["QB"] if target.startswith("pass_") else ["QB","RB","FB","WR","TE"]
        doc=dict(category=dict(target=target,modeled_roles=roles,primary_roles=["QB"] if target.startswith("pass_") else ["RB"]),family=family,method_id=method)
        refs.append(o.archive.write(storage,output/(str(n)+".json"),doc))
    document={key:None for key in o.resume.MODEL_KEYS}
    document.update(state="CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE",model_pairs=18,fits=0,
        current_loader_replay=True,model_artifact_durability=True,models=refs)
    return storage,output,document


def test_manifest_roles_require_live_caller_and_all18_exact_slots(tmp_path):
    storage,output,doc=model_roles_fixture(tmp_path)
    ref=o.archive.write(storage,output/"RESTORED.json",doc)
    with pytest.raises(o.OperationsError,match="LIVE_CURRENT_MODEL"):o.roles_from_manifests(storage,ref,authenticate=lambda _:False)
    roles=o.roles_from_manifests(storage,ref,authenticate=lambda _:True)
    assert set(roles)==set(cp.TARGETS) and roles["pass_yd"]["primary_roles"]==["QB"]
    assert roles["rush_att"]["modeled_roles"]==["QB","RB","FB","WR","TE"]
    bad=deepcopy(doc);bad["models"][0],bad["models"][1]=bad["models"][1],bad["models"][0]
    badref=o.archive.write(storage,output/"BAD.json",bad)
    with pytest.raises(o.OperationsError,match="MANIFEST_ROLE_IDENTITY"):o.roles_from_manifests(storage,badref,authenticate=lambda _:True)


def test_different_model_roles_cannot_silently_change_grading_population(tmp_path):
    storage,output,doc=model_roles_fixture(tmp_path)
    n=next(i for i,x in enumerate(cp.JOBS)if x[2]=="COUNT_A")
    original=o.cp.strict_json(o.cp.read_ref(doc["models"][n]));original["category"]["primary_roles"]=["WR"]
    doc["models"][n]=o.archive.write(storage,output/"ROLE_CHANGE.json",original)
    ref=o.archive.write(storage,output/"RESTORED.json",doc)
    with pytest.raises(o.OperationsError,match="SHARE_REGISTERED_CATEGORY_ROLES"):o.roles_from_manifests(storage,ref,authenticate=lambda _:True)


def test_refresh_preserves_primary_assignment_without_another_observation():
    f=fixture();r=registered(prepare(f));c=continuation(f,r)
    roles={t:dict(modeled_roles=["QB"] if t.startswith("pass_") else ["RB"],primary_roles=["QB"] if t.startswith("pass_") else ["RB"])for t in cp.TARGETS}
    at=CONTINUED+timedelta(minutes=1)
    first,decision=o.primary_population(r,c,roles,capture_id="a"*64,authenticate=lambda _:True,clock=lambda:at)
    assert decision["state"]=="FIRST_PREVALUE_PRIMARY_CAPTURE"
    # This is a fictional typed prior state for metadata composition only. It
    # supplies no native/durability authority and opens no forecast body.
    prior=grade.DurableHistory(dict(epoch_sha256=r.epoch.sha256,captures=[dict(population=first.document)]),grade._KEY)
    second,decision=o.primary_population(r,c,roles,capture_id="b"*64,authenticate=lambda _:True,
        previous=prior,clock=lambda:at+timedelta(minutes=1))
    assert decision["state"]=="REFRESH_NOT_ANOTHER_PRIMARY_OBSERVATION" and not decision["primary_game_ids"]
    assert second.document["assignments"]==first.document["assignments"] and set(second.document["assignments"].values())=={"a"*64}
    assert first.document["registered_at"]!=second.document["registered_at"]
    with pytest.raises(grade.GradeError,match="AUTHENTICATION_REJECTED"):
        o.primary_population(r,c,roles,capture_id="b"*64,authenticate=lambda _:False,clock=lambda:at)
