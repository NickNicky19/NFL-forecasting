"""Fictional metadata/Actions seams; real guards/CAS/resume/population/writes.

Composition fixtures are explicitly NOT genuine Actions/remote evidence. The
production path uses the parent-owned child_context and live authority module.
"""
from copy import deepcopy
from datetime import timedelta
import csv
import io
import json
from pathlib import Path
import pickle
import socket
import subprocess
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from nfl_lab import audit_weekly_operations_worker_v1 as w
from nfl_lab import audit_weekly_runtime_v1 as runtime, private_draft_store as store, state, gha_private_checkpoint as cp
from nfl_lab import audit_weekly_operations_authority_v1 as authority
from nfl_lab.weekly_adaptive import select as ORIGINAL_WEEKLY_SELECT
from tools import audit_weekly_operations_worker_v1 as cli
from test_audit_weekly_runtime_v1 import packet as runtime_packet
from test_audit_weekly_resume_v1 import case as resume_case, DAILY
from test_audit_weekly_controller_bootstrap_v1 import system, locator_system
from test_audit_weekly_grade_history_v1 import original_seed as native_history_seed
from test_audit_weekly_operations_v1 import first_future_metadata
import test_audit_weekly_controller_v1 as original

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def deny_actual_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *_:pytest.fail("REAL_NETWORK_FORBIDDEN"))


def fixture_verify(context):
    """Explicit composition-only caller seam; preserves REAL native envelope."""
    w.native_envelope()
    w.require(context._sha == w._digest(dict(request=context.request, authority=context.authority,
        job=context.job, go=context.go)), "FICTIONAL_CONTEXT_CHANGED")
    w.validate_request(context.request, w.PHASE)
    return context


def composition_context(seed):
    from nfl_lab import gha_private_checkpoint as cp
    current = seed["current"]
    job = dict(execution_lane="github_actions", workflow_ref=current["workflow_ref"], workflow_sha=current["source_sha"],
        job_id=current["job_id"], permission="write", event_name="workflow_dispatch", api_job_id=current["api_job_id"], run_authenticated=True)
    client = SimpleNamespace(run_id=current["run_id"], source_sha=current["source_sha"], process=current["process_identity"], job=job)
    result = w.Authenticated(seed["request"], seed["native"], job, seed["go"], {}, client, None, None, w._KEY)
    assert cp.client_identity(client) == current
    return result


@pytest.fixture
def composed(resume_case, monkeypatch):
    c = resume_case
    base = c.storage.cache.parent
    stream = io.StringIO()
    fields = ["season", "week", "game_type", "game_id", "gameday", "gametime", "espn", "home_team", "away_team"]
    writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
    for i, game in enumerate(c.p.original["schedule"]):
        local = state.utc(game["kickoff_utc"]).astimezone(ZoneInfo("America/New_York"))
        writer.writerow(dict(season=2026, week=7, game_type="REG", game_id=game["game_id"],
            gameday=local.date().isoformat(), gametime=local.strftime("%H:%M"), espn=str(10001 + i),
            home_team=["BAL", "BUF", "DAL"][i], away_team=["PIT", "NE", "NYG"][i]))
    raw = stream.getvalue().encode()
    c.storage.write_bytes(c.root / "worker-input/calendar.csv", raw)
    calendar = cp.binding(c.root / "worker-input/calendar.csv")
    receipt = c.put("worker-input/calendar.receipt.json", dict(url=w.CALENDAR_URL, status="acquired",
        sha256=store.sha(raw), bytes=len(raw), retrieved_utc=(DAILY - timedelta(seconds=15)).isoformat()))
    request = dict(schema_version=w.VERSION + "-request", phase=w.PHASE, code_pins={name:"1" * 64 for name in w.FILES},
        limits=deepcopy(w.LIMITS), cache=str(c.storage.cache), state_root=str(c.storage.state_root),
        output=str(base / w.OUTPUT_NAME), inputs=dict(retained_result=c.put("worker-input/RETAINED.json", c.restored),
            retained_models=c.ref, calendar=dict(body=calendar, receipt=receipt),
            canonical_weekly_choice_sha256=c.original_choice["sha256"], capture_id="a" * 64, previous_grade_snapshot=None))
    seed = dict(request=request, native=dict(owner_root_go_sha256="f" * 64,
        issued_at_utc=(DAILY - timedelta(minutes=5)).isoformat(), expires_at_utc=(DAILY + timedelta(hours=1)).isoformat()),
        go=dict(issued_at_utc=(DAILY - timedelta(minutes=5)).isoformat(), effective_epoch=dict(
            schema_version="audit-weekly-recurring-v1-context", controller_context=None,
            previous_capture=dict(feed_sha256="1" * 64, receipt_sha256="2" * 64))), current=c.restored["current"])
    monkeypatch.setattr(w.Authenticated, "verify", fixture_verify)
    monkeypatch.setattr(w, "native_envelope", lambda:None)  # unit composition only; native subprocess below uses REAL guard
    return SimpleNamespace(c=c, seed=seed, request=request, context=lambda:composition_context(seed))


def test_real_prepare_writes_prevalue_roles_calendar_and_scoped_population(composed):
    q = composed
    before = Path(q.c.original_choice["path"]).read_bytes()
    result = w.prepare(q.context(), clock=lambda:DAILY)
    manifest = runtime.read_owned(q.c.storage, result["manifest"])
    assert manifest["state"] == "SAME_WEEK_PREVALUE_METADATA_READY_LOCAL"
    assert manifest["partially_elapsed_week"] is True
    assert manifest["active_game_ids"] == ["fictional-monday"]
    assert set(manifest["elapsed_game_ids"]) == {"fictional-elapsed", "fictional-sunday"}
    assert Path(q.c.original_choice["path"]).read_bytes() == before
    refs = manifest["archive_context"]
    assert set(refs) == {"ops_population", "ops_roles", "ops_schedule", "canonical_weekly_choice", "capture_scope", "ops_previous_checkpoint"}
    assert refs["ops_previous_checkpoint"] is None
    population = runtime.read_owned(q.c.storage, refs["ops_population"])
    schedule = runtime.read_owned(q.c.storage, refs["ops_schedule"])
    roles = runtime.read_owned(q.c.storage, refs["ops_roles"])
    assert len(schedule) == 3 and len(roles) == 11
    assert population["assignments"] == {"fictional-monday":"a" * 64}
    assert population["role_catalog_sha256"] == state.digest(roles)
    assert population["registered_at"] == DAILY.isoformat()
    assert manifest["fits"] == manifest["source_acquisitions"] == manifest["label_acquisitions"] == manifest["model_decodes"] == 0
    assert manifest["current_values_used"] is manifest["public_release"] is manifest["successful_forecast"] is False
    with pytest.raises(w.WorkerError):pickle.dumps(q.context())


@pytest.fixture
def first_future_composed(composed,first_future_metadata,monkeypatch):
    """Real original-index/epoch/resume/CAS and real synthetic GET transport.

    Only the current OWNER proof seam is fictional. Original forecast/model
    bodies remain opaque throughout the metadata preparation.
    """
    from nfl_lab import audit_weekly_operations_v1 as operations
    q=composed;m=first_future_metadata
    old_raw=store.read_local(q.request['inputs']['calendar']['body']['path'],8<<20)
    raw=old_raw+b'2026,8,REG,fictional-week-8,2026-10-29,16:00,20001,ATL,NO\n'
    path=q.c.root/'worker-input/FIRST_CALENDAR.csv';q.c.storage.write_bytes(path,raw)
    q.request['inputs']['calendar']=dict(body=cp.binding(path),receipt=q.c.put('worker-input/FIRST_RECEIPT.json',
        dict(url=w.CALENDAR_URL,status='acquired',sha256=store.sha(raw),bytes=len(raw),
            retrieved_utc=(m.at-timedelta(seconds=15)).isoformat())))
    full=operations.calendar(raw,season=2026,week=8)
    projected=[{k:r[k] for k in ('season','week','game_type','game_id','kickoff_utc')} for r in full]
    epoch_doc=runtime.read_owned(q.c.storage,q.c.restored['aliases']['context/epoch.json'])
    m.root['effective_epoch']['controller_context'].update(retained_epoch_sha256=state.digest(epoch_doc),
        retained_choice_sha256=q.c.original_choice['sha256'],
        retained_root_go_sha256=q.c.restored['original_archive']['root_go_sha256'])
    m.root['effective_epoch']['plan'].update(calendar_sha256=state.digest(projected),
        game_cutoffs={'fictional-week-8':'2026-10-29T19:45:00+00:00'},
        deadline_utc='2026-10-29T19:45:00+00:00')
    q.seed['go']=m.root
    q.seed['native'].update(issued_at_utc=m.root['issued_at_utc'],expires_at_utc=m.root['expires_at_utc'])
    context=q.context()
    m.client.run_id=context.client.run_id;m.client.source_sha=context.client.source_sha
    m.client.process=context.client.process;m.client.job=context.client.job
    context.client=m.client
    # The shared same-week fixture forbids selection as well as fitting. This
    # new week must execute the original startup selector; fitting stays forbidden.
    monkeypatch.setattr(runtime.selector,'select',ORIGINAL_WEEKLY_SELECT)
    monkeypatch.setattr(w,'_first_primary_authority',lambda context:None)  # explicit current OWNER seam only
    return SimpleNamespace(q=q,m=m,context=context)


def test_first_future_real_prepare_preserves_epoch_and_registers_only_week8(first_future_composed):
    from nfl_lab import audit_weekly_operations_v1 as operations
    x=first_future_composed;q=x.q
    original=store.read_local(q.c.original_choice['path'],512<<10)
    result=w.prepare(x.context,clock=lambda:x.m.at)
    value=runtime.read_owned(q.c.storage,result['manifest'])
    assert value['state']=='FIRST_FUTURE_PRIMARY_PREVALUE_METADATA_READY_LOCAL'
    population=runtime.read_owned(q.c.storage,value['archive_context']['ops_population'])
    assert population['assignments']=={'fictional-week-8':'a'*64}
    assert population['stream_id']==operations.STREAM
    assert value['epoch_sha256']==x.m.root['effective_epoch']['controller_context']['retained_epoch_sha256']
    assert value['history_binding']==q.c.p.runtime.registered.epoch.origin['history_binding']
    assert store.read_local(q.c.original_choice['path'],512<<10)==original
    assert value['archive_context']['ops_previous_checkpoint'] is None
    assert {'ops_population','ops_roles','ops_schedule','ops_planning','canonical_weekly_choice','capture_scope'}<=set(value['archive_context'])
    choice=runtime.read_owned(q.c.storage,value['archive_context']['canonical_weekly_choice'])
    assert choice['resolved_prior_keys']==[] and choice['slate']['week']==8
    assert not value['elapsed_game_ids'] and value['active_game_ids']==['fictional-week-8']
    assert len(x.m.calls)==6 and value['fits']==value['source_acquisitions']==value['label_acquisitions']==0


def test_first_future_cannot_forget_even_an_archived_unqualified_primary(first_future_composed):
    x=first_future_composed;q=x.q
    prior=deepcopy(q.c.restored)
    prior['aliases']['context/ops_population.json']=q.c.put('worker-input/PRIOR_PRIMARY.json',{'preserve_failed_assignment':True})
    x.context.request['inputs']['retained_result']=q.c.put('worker-input/NO_RESET.json',prior)
    x.context._sha=w._digest(dict(request=x.context.request,authority=x.context.authority,job=x.context.job,go=x.context.go))
    with pytest.raises(w.WorkerError,match='QUALIFIED_PREVIOUS_PRIMARY_ASSIGNMENT_REQUIRED'):
        w.prepare(x.context,clock=lambda:x.m.at)
    assert x.m.calls==[]


@pytest.fixture
def failed_first_composed(first_future_composed,tmp_path,monkeypatch):
    from nfl_lab import audit_weekly_operations_v1 as operations,audit_weekly_hosted_v1 as hosted
    from test_audit_weekly_hosted_v1 import pending_failure,_failed_first_recovery_case
    x=first_future_composed;q=x.q
    raw=store.read_local(q.request['inputs']['calendar']['body']['path'],8<<20)
    raw+=b''.join(f'2026,8,REG,fictional-week-8-{n:02},2026-10-29,16:00,{20001+n},ATL,NO\n'.encode() for n in range(1,14))
    full=operations.calendar(raw,season=2026,week=8)
    schedule=[{k:r[k] for k in ('season','week','game_type','game_id','kickoff_utc')} for r in full]
    cuts={r['game_id']:(state.utc(r['kickoff_utc'])-timedelta(minutes=15)).isoformat() for r in full}
    plan=dict(kind='FUTURE_CAPABLE',season=2026,week=8,calendar_sha256=state.digest(schedule),game_cutoffs=cuts,deadline_utc=min(cuts.values()))
    base=tmp_path/'new-failure-fixture';base.mkdir()
    case=_failed_first_recovery_case(pending_failure.__wrapped__(base),calendar_plan=plan,
        original_scope=x.m.root['effective_epoch']['controller_context'])
    case.root['qualified_runtime']['qualification']={'run_id':'100','engineering_boundary_v2':True};case.root['pending_census']={}
    q.seed['go']=case.root;x.m.at=case.at
    path=q.c.root/'worker-input/RECOVERY_CALENDAR.csv';q.c.storage.write_bytes(path,raw)
    q.request['inputs']['calendar']=dict(body=cp.binding(path),receipt=q.c.put('worker-input/RECOVERY_RECEIPT.json',
        dict(url=w.CALENDAR_URL,status='acquired',sha256=store.sha(raw),bytes=len(raw),retrieved_utc=case.root['issued_at_utc'])))
    context=q.context();context.client=x.m.client
    case.client.run_id=context.client.run_id;case.client.source_sha=context.client.source_sha
    case.client.job=context.job;case.client.process=context.client.process
    case.client.authenticate_actions_job=lambda:None
    case.client.bind=lambda binding:None
    constructed=[]
    def metadata_client(*a,**kw):
        current=case.client if not constructed else case.claim_reader()
        constructed.append(current);return current
    monkeypatch.setattr(hosted,'PendingMetadataClient',metadata_client)
    monkeypatch.setattr(hosted.archive,'authenticate_qualification',lambda *a,**kw:None)
    monkeypatch.setattr(authority,'attach',lambda *a,**kw:None)
    return SimpleNamespace(context=context,q=q,m=x.m,case=case)


def test_failed_first_recovery_real_worker_preserves_missing_gap_and_new_choice(failed_first_composed):
    x=failed_first_composed;q=x.q
    result=w.prepare(x.context,clock=lambda:x.case.at)
    manifest=runtime.read_owned(q.c.storage,result['manifest'])
    assert manifest['state']=='FAILED_FIRST_RECOVERY_PREVALUE_METADATA_READY_LOCAL'
    refs=manifest['archive_context'];gap=runtime.read_owned(q.c.storage,refs['ops_failed_recovery'])
    choice=runtime.read_owned(q.c.storage,refs['canonical_weekly_choice'])
    assert gap['old_forecast_bodies_missing'] is gap['old_week8_choice_body_missing'] is True
    assert gap['failed_capture_qualified'] is gap['old_forecast_bodies_recovered'] is False
    assert gap['new_choice_sha256']==manifest['choice_sha256']==state.digest(choice)
    assert choice['resolved_prior_keys']==[] and len(choice['slate']['game_cutoffs'])==14
    assert state.utc(choice['choice']['actual_frozen_at'])==x.case.at
    assert refs['ops_previous_checkpoint'] is None
    assert len(x.m.calls)==6 and manifest['fits']==manifest['source_acquisitions']==manifest['label_acquisitions']==0
    assert gap['original_week8_choice_commitment']['sha256']!=manifest['choice_sha256']
    assert all(c in {'GET','draft'} for c in x.case.client.calls)


def test_failed_first_recovery_never_falls_back_to_failed_capture_or_assignment(failed_first_composed):
    x=failed_first_composed;q=x.q
    old=deepcopy(q.c.restored);old['aliases']['context/ops_population.json']=q.c.put('worker-input/FAILED_ASSIGNMENT.json',{'failed':True})
    x.context.request['inputs']['retained_result']=q.c.put('worker-input/NOT_LEGACY.json',old)
    x.context._sha=w._digest(dict(request=x.context.request,authority=x.context.authority,job=x.context.job,go=x.context.go))
    with pytest.raises(w.WorkerError,match='QUALIFIED_PREVIOUS_PRIMARY_ASSIGNMENT_REQUIRED'):
        w.prepare(x.context,clock=lambda:x.case.at)
    assert x.case.client.calls==[]


def test_failed_first_recovery_typed_gap_rejects_promotion_or_choice_drift(failed_first_composed):
    from nfl_lab import audit_weekly_operations_v1 as operations
    x=failed_first_composed;q=x.q
    result=w.prepare(x.context,clock=lambda:x.case.at);m=runtime.read_owned(q.c.storage,result['manifest'])
    gap=runtime.read_owned(q.c.storage,m['archive_context']['ops_failed_recovery'])
    choice=runtime.read_owned(q.c.storage,m['archive_context']['canonical_weekly_choice'])
    def validate(v):return operations.validate_failed_first_gap(v,choice=choice,epoch_sha256=m['epoch_sha256'])
    assert validate(gap)==gap
    for key,value in [('old_capture_state','COMPLETE_CAPTURE'),('old_forecast_bodies_missing',False),
            ('old_forecast_bodies_recovered',True),('failed_capture_qualified',True),('new_choice_sha256','f'*64),
            ('new_choice_actual_frozen_at','2026-10-27T19:00:00Z'),('invented_old_choice',{})]:
        bad=deepcopy(gap);bad[key]=value
        with pytest.raises(operations.OperationsError):validate(bad)
    with pytest.raises(operations.OperationsError):
        operations.validate_failed_first_gap(gap,choice=choice,epoch_sha256=m['epoch_sha256'],root_go_sha256='0'*64)


def test_failed_first_recovery_charges_native_metadata_within_original_byte_cap(failed_first_composed):
    x=failed_first_composed;x.case.client.transferred=w.LIMITS['metadata_bytes']
    with pytest.raises(w.WorkerError,match='OPERATIONS_TOTAL_METADATA_BYTE_CAP'):
        w.prepare(x.context,clock=lambda:x.case.at)
    assert not list(Path(x.q.request['output']).glob('FAILED_FIRST_RECOVERY.json'))


def test_failed_first_recovery_claim_appends_once_retains_old_claim_and_rejects_duplicate(failed_first_composed,monkeypatch):
    from nfl_lab import audit_weekly_hosted_v1 as hosted,audit_weekly_operations_v1 as operations
    from nfl_lab import audit_weekly_template_v1 as template,audit_weekly_controller_bootstrap_v1 as bootstrap
    x=failed_first_composed;q=x.q;w.prepare(x.context,clock=lambda:x.case.at)
    r=hosted.Runner.__new__(hosted.Runner);r.go=x.context.go;r.go_sha=x.context.root_sha256
    r.root=Path(q.request['cache']).parent;r.storage=q.c.storage;r.journal=r.root/'claim-journal';r.journal.mkdir(mode=0o700)
    r.identity=dict(run_id=x.context.client.run_id,source_sha=x.context.client.source_sha);r.job=x.context.job
    r.env=dict(GITHUB_ACTOR='NickNicky19',GITHUB_ACTOR_ID='208912933',GITHUB_TOKEN='ghs_FICTIONAL')
    owner=bootstrap.Owner.__new__(bootstrap.Owner);r.operations_proof=owner;r.fresh_operations_proof=lambda:owner
    r.pending_scope_authenticated=True;r.recovery_metadata_client=x.case.claim_reader
    assets=deepcopy(x.case.assets);bodies={};uploads=[];real_client=hosted.archive.Client
    old_claim=next(a for a in assets if a['id']==17)
    class FreshClient(real_client):
        def __init__(self,*a,**kw):super().__init__(*a,**kw,transport=x.m.client.transport,clock=lambda:10)
        def authenticate_actions_job(self):pass
        def inventory(self):self.inventory_slots=len(assets);return assets,sum(a['size'] for a in assets)
        def upload(self,name,body,*,reuse_completed=False):
            assert reuse_completed is False and not any(a['name']==name for a in assets)
            uploads.append(name);a=dict(id=100+len(uploads),name=name,size=len(body),state='uploaded',digest='sha256:'+store.sha(body))
            assets.append(a);bodies[name]=body;return a
    original_auth=operations.authenticate_failed_first_recovery;original_absence=operations.failed_first_absence
    monkeypatch.setattr(operations,'authenticate_failed_first_recovery',lambda client,root,*,authenticate,claim_reader:
        original_auth(client,root,authenticate=authenticate,claim_reader=claim_reader,clock=lambda:x.case.at))
    monkeypatch.setattr(operations,'failed_first_absence',lambda client,root,proof,*,authenticate:
        original_absence(client,root,proof,authenticate=authenticate,clock=lambda:x.case.at))
    monkeypatch.setattr(hosted.archive,'Client',FreshClient)
    monkeypatch.setattr(hosted.operations_authority,'_verify',lambda *a,**kw:None)
    monkeypatch.setattr(store,'check_proof',lambda *a,**kw:None)  # fictional qualification only; append wire is real
    r.claim()
    expected=store.canonical(template.failed_first_recovery_claim(r.go))
    assert bodies['blob-'+store.sha(expected)+'.bin']==expected and len(uploads)==2
    assert next(a for a in assets if a['id']==17)==old_claim
    with pytest.raises(store.StoreError,match='OWNER_ROOT_ALREADY_CONSUMED_NO_RETRY'):r.claim()
    assert len(uploads)==2


def test_failed_first_recovery_gap_survives_optional_owned_archive_transport(failed_first_composed,tmp_path_factory):
    """Runs with the separately supplied archive delta; fictional metadata only."""
    from nfl_lab import audit_weekly_archive_v1 as archive,audit_weekly_operations_v1 as operations
    from test_audit_weekly_archive_v1 import capture_case
    if 'ops_failed_recovery' not in getattr(archive,'OPERATIONS_RECOVERY_CONTEXT',set()):
        pytest.skip('Apply the separate optional archive-role patch for this integration check')
    x=failed_first_composed;q=x.q;result=w.prepare(x.context,clock=lambda:x.case.at)
    m=runtime.read_owned(q.c.storage,result['manifest']);new_choice=runtime.read_owned(q.c.storage,m['archive_context']['canonical_weekly_choice'])
    epoch_doc=runtime.read_owned(q.c.storage,m['inputs']['epoch'])
    base=tmp_path_factory.mktemp('recovery-gap-archive');p=capture_case(base,epoch_document=epoch_doc,choice_document=new_choice)
    context=dict(p.context)
    for role,ref in m['archive_context'].items():
        if ref is not None:context[role]=p.put('recovery/'+role+'.json',runtime.read_owned(q.c.storage,ref))
    snapshot=archive.collect(p.root,context,storage=p.storage,output=p.base/'collected')
    member=next(f for f in snapshot['files'] if f['logical_path']=='context/ops_failed_recovery.json')
    encoded,inflated=archive.codec.encode([member]);record=dict(bytes=len(encoded),sha256=store.sha(encoded),inflated_bytes=inflated,files=[member])
    destination=p.base/'fresh-owned-gap';archive._extract_owned_group(encoded,record,p.storage,destination)
    restored=archive.read_owned(p.storage,cp.binding(destination/member['logical_path']))
    assert restored==runtime.read_owned(q.c.storage,m['archive_context']['ops_failed_recovery'])
    assert operations.validate_failed_first_gap(restored,choice=new_choice,epoch_sha256=m['epoch_sha256'])==restored
    assert restored['old_capture_state']=='FAILED' and restored['old_forecast_bodies_missing'] is True
    assert not any('LOST_WEEK8_CHOICE' in f['logical_path'] for f in snapshot['files'])


def test_first_future_manual_authority_rejects_bot_or_serialized_owner_before_gets():
    context=SimpleNamespace(verify=lambda:None,env={'GITHUB_ACTOR':'github-actions[bot]','GITHUB_ACTOR_ID':'41898282'},proof={})
    with pytest.raises(w.WorkerError,match='LIVE_OWNER_FIRST_PRIMARY_PROOF_REQUIRED'):
        w._first_primary_authority(context)


def test_first_future_owner_path_forwards_exact_root_to_current_verifier(monkeypatch):
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    proof=bootstrap.Owner.__new__(bootstrap.Owner)
    env={'GITHUB_ACTOR':'NickNicky19','GITHUB_ACTOR_ID':'208912933'}
    calls=[]
    context=SimpleNamespace(verify=lambda:calls.append('context'),env=env,proof=proof,
        go={'fictional':'exact-root'})
    def current_verifier(actual,actual_env,body):
        assert actual is proof and actual_env is env and body==b'{"fictional":"exact-root"}'
        calls.append('current-owner-verifier')
    monkeypatch.setattr(authority,'_verify',current_verifier)  # Explicit verifier seam, no live grant.
    w._first_primary_authority(context)
    assert calls==['context','current-owner-verifier']


def test_prepare_never_decodes_model_or_forecast_bodies(composed, monkeypatch):
    real = runtime.read_owned
    def metadata_only(storage, ref, *args, **kwargs):
        assert not ref["path"].endswith(".opaque") and "opaque-private-forecast" not in ref["path"]
        return real(storage, ref, *args, **kwargs)
    monkeypatch.setattr(runtime, "read_owned", metadata_only)
    assert w.prepare(composed.context(), clock=lambda:DAILY)["fits"] == 0


def test_owned_CAS_previous_snapshot_cannot_replace_fresh_native_restore(composed, monkeypatch):
    q = composed
    q.request["inputs"]["previous_grade_snapshot"] = q.request["inputs"]["retained_models"]
    from nfl_lab import audit_weekly_grade_v1 as grade
    monkeypatch.setattr(grade, "restore_snapshot", lambda *_args, **_kwargs:pytest.fail("CAS_ALONE_IS_NOT_QUALIFIED_RESTORE"))
    with pytest.raises(w.WorkerError, match="LIVE_HISTORY_SIDECAR_AND_PUBLIC_RECEIPT_PAIR_REQUIRED"):
        w.prepare(q.context(), clock=lambda:DAILY)
    assert not Path(q.request["output"]).exists()


def test_prior_primary_population_cannot_be_forgotten_on_refresh(composed):
    q = composed
    changed = deepcopy(q.c.restored)
    changed["aliases"]["context/ops_population.json"] = q.c.put("worker-input/old-population.json", {"old_assignment":"retained"})
    q.request["inputs"]["retained_result"] = q.c.put("worker-input/OLD_PRIMARY.json", changed)
    with pytest.raises(w.WorkerError, match="QUALIFIED_PREVIOUS_PRIMARY_ASSIGNMENT_REQUIRED"):
        w.prepare(q.context(), clock=lambda:DAILY)
    assert not Path(q.request["output"]).exists()


@pytest.mark.parametrize("damage", ["v1_pair", "v2_missing_pair", "sidecar_hash", "receipt_hash", "saved_authority"])
def test_history_requires_exact_Root_v2_pair_before_restore_or_current_values(composed, monkeypatch, damage):
    from nfl_lab import audit_weekly_grade_history_v1 as history
    q = composed
    pair = dict(sidecar=q.c.put("worker-input/SIDECAR.json", {"metadata":"fixture"}),
        public_receipt=q.c.put("worker-input/PUBLIC_RECEIPT.json", {"metadata":"fixture"}))
    q.seed["go"]["effective_epoch"].update(schema_version=history.CONTEXT_V2,
        previous_checkpoint=dict(sha256=pair["sidecar"]["sha256"]))
    q.seed["go"]["effective_epoch"]["previous_capture"]["receipt_sha256"] = pair["public_receipt"]["sha256"]
    q.request["inputs"]["previous_grade_snapshot"] = pair
    if damage == "v1_pair":
        q.seed["go"]["effective_epoch"].update(schema_version="audit-weekly-recurring-v1-context")
        del q.seed["go"]["effective_epoch"]["previous_checkpoint"]
    elif damage == "v2_missing_pair":q.request["inputs"]["previous_grade_snapshot"] = None
    elif damage == "sidecar_hash":pair["sidecar"]["sha256"] = "0" * 64
    elif damage == "receipt_hash":pair["public_receipt"]["sha256"] = "0" * 64
    calls = []
    def restore(*args, **kwargs):
        calls.append((args, kwargs))
        assert damage == "saved_authority", "REJECT_BEFORE_LIVE_RESTORE"
        return dict(durable={"qualified":True}, binding=q.c.ref)
    monkeypatch.setattr(history, "restore_previous", restore)
    real = runtime.read_owned
    def before_current(storage, ref, *args, **kwargs):
        assert ref != q.request["inputs"]["calendar"]["body"], "NO_CURRENT_CALENDAR_BEFORE_HISTORY"
        return real(storage, ref, *args, **kwargs)
    monkeypatch.setattr(runtime, "read_owned", before_current)
    with pytest.raises(w.WorkerError, match="LIVE_CURRENT_VERIFIED_HISTORY_REQUIRED" if damage == "saved_authority" else "EXACT_ROOT_HISTORY_INPUT"):
        w.prepare(q.context(), clock=lambda:DAILY, transport="fictional-test-transport")
    assert len(calls) == (1 if damage == "saved_authority" else 0)
    if calls:assert calls[0][1] == dict(transport="fictional-test-transport")
    assert not Path(q.request["output"]).exists()


def test_run_forwards_transport_to_guard_and_inline_recovery(monkeypatch):
    token = object(); context = object(); calls = []
    def guard(args, env, *, transport):
        assert transport is token
        return context
    def prepare(current, *, transport):
        assert current is context and transport is token
        calls.append(current)
        return {"prepared":True}
    monkeypatch.setattr(w, "guard", guard); monkeypatch.setattr(w, "prepare", prepare)
    assert w.run(SimpleNamespace(), {}, transport=token) == {"prepared":True} and calls == [context]


@pytest.mark.parametrize("bad_old_run", [False, True])
def test_prepare_calls_real_cross_run_recovery_before_current_calendar(tmp_path, native_history_seed, monkeypatch, bad_old_run):
    """Real history/native GET protocol; current authority is a fictional seam.

    Stop at current calendar I/O: the seed's week has elapsed. Its original
    clocks are preserved rather than shifted to manufacture an active week.
    Complete same-week resume/writes have their own real composition test.
    """
    from test_audit_weekly_grade_history_v1 import recovery_case
    from nfl_lab import audit_weekly_grade_history_v1 as history
    x = recovery_case(tmp_path, native_history_seed, monkeypatch)
    current = cp.client_identity(x.context.client)
    retained = runtime.read_owned(x.storage, x.context.request["inputs"]["retained_result"])
    retained.update(current=current, current_root_go_sha256=x.context.root_sha256)
    def put(name, value):return runtime.write(x.storage, tmp_path / name, value)
    request = dict(schema_version=w.VERSION + "-request", phase=w.PHASE,
        code_pins=deepcopy(x.context.go["code_pins"]), limits=deepcopy(w.LIMITS),
        cache=str(x.storage.cache), state_root=str(x.storage.state_root), output=str(tmp_path / w.OUTPUT_NAME),
        inputs=dict(retained_result=put("current-retained.json", retained),
            retained_models=put("current-models.json", dict(current=current, current_go_sha256=x.context.root_sha256,
                actual_completed_at=(history.now() - timedelta(seconds=1)).isoformat())),
            calendar=dict(body=put("current-calendar.json", {"read_must_follow_live_history":True}),
                receipt=put("current-calendar-receipt.json", {"fictional":True})),
            canonical_weekly_choice_sha256=retained["aliases"]["runtime/WEEKLY_CHOICE.json"]["sha256"],
            capture_id="a" * 64, previous_grade_snapshot=dict(sidecar=x.sidecar, public_receipt=x.receipt)))
    x.context.request = request
    x.damage["run"] = bad_old_run
    recovered = []
    actual_restore, actual_read = history.restore_previous, runtime.read_owned
    def restore(*args, **kwargs):
        value = actual_restore(*args, **kwargs)
        recovered.append(value)
        return value
    class CurrentCalendarReached(Exception):pass
    def read(storage, ref, *args, **kwargs):
        if ref == request["inputs"]["calendar"]["body"]:
            assert len(recovered) == 1 and recovered[0].verify() is recovered[0]
            raise CurrentCalendarReached
        return actual_read(storage, ref, *args, **kwargs)
    monkeypatch.setattr(history, "restore_previous", restore)
    monkeypatch.setattr(runtime, "read_owned", read)
    with pytest.raises(history.HistoryError if bad_old_run else CurrentCalendarReached):
        w.prepare(x.context, clock=history.now, transport=x.api)
    assert len(recovered) == (0 if bad_old_run else 1)
    private = [r for r in x.calls if "/releases/" in r.full_url]
    assert bool(private) is (not bad_old_run) and all(r.method == "GET" for r in x.calls)
    if recovered:
        value = recovered[0]
        assert value.proof["original_grade_read_proof"] == native_history_seed["sidecar"]["grade_read_proof"]
        assert value.proof["current"]["run_id"] != value.proof["original_grade_read_proof"]["reader"]["run_id"]
        assert value.durable.document["known_versions"] == native_history_seed["known_versions"]
        assert value.durable.document["known_weeks"] == native_history_seed["known_weeks"]
        assert [c["capture_id"] for c in value.durable.document["captures"]] == native_history_seed["capture_ids"]
        assert Path(value.binding["path"]).is_file()
    assert not Path(request["output"]).exists()


@pytest.mark.parametrize("missing", [None, "ops_previous_checkpoint_sidecar", "ops_previous_public_receipt"])
def test_archive_collect_preserves_exact_history_pair_without_granting_authority(tmp_path, missing):
    from test_audit_weekly_archive_v1 import capture
    from nfl_lab import audit_weekly_archive_v1 as archive
    x = capture.__wrapped__(tmp_path)
    context = deepcopy(x.context)
    for role in archive.OPERATIONS_CONTEXT:
        context[role] = x.put("ops/" + role + ".json", {"fictional_prevalue_metadata":role})
    for role in w.HISTORY_ARCHIVE_ROLES:
        context[role] = x.body("ops/" + role + ".gz", b"OPAQUE_PRIOR_METADATA_WITHOUT_AUTHORITY:" + role.encode())
    context["ops_previous_checkpoint"] = x.body("ops/fresh-checkpoint.gz", b"OPAQUE_SNAPSHOT_REQUIRES_FRESH_RESTORE")
    if missing is not None:del context[missing]
    output = tmp_path / "collected"
    if missing is not None:
        with pytest.raises(store.StoreError, match="PAIRED_OPERATIONAL_HISTORY_REFERENCES_REQUIRED"):
            archive.collect(x.root, context, storage=x.storage, output=output)
        assert not output.exists()
        return
    census = archive.collect(x.root, context, storage=x.storage, output=output)
    for role in w.HISTORY_ARCHIVE_ROLES + ("ops_previous_checkpoint",):
        logical = "context/" + role + ".json"
        assert census["census"]["physical_origins"][logical] == context[role]
        item = next(f for f in census["files"] if f["logical_path"] == logical)
        assert item["sha256"] == context[role]["sha256"] and item["bytes"] == context[role]["bytes"]
    assert census["census"]["archive_state"] == "COMPLETE_CAPTURE"


@pytest.mark.parametrize("field,value", [("url", "https://example.invalid/"), ("sha256", "0" * 64),
    ("retrieved_utc", "2026-10-20T00:00:00Z"), ("status", "cached_unknown")])
def test_calendar_requires_current_exact_source_receipt(composed, field, value):
    q = composed
    document = runtime.read_owned(q.c.storage, q.request["inputs"]["calendar"]["receipt"])
    document[field] = value
    q.request["inputs"]["calendar"]["receipt"] = q.c.put("worker-input/BAD_RECEIPT.json", document)
    with pytest.raises(w.WorkerError, match="ACTUAL_CURRENT_FULL_CALENDAR_RECEIPT_REQUIRED"):
        w.prepare(q.context(), clock=lambda:DAILY)
    assert not Path(q.request["output"]).exists()


def test_no_fallback_for_wrong_canonical_weekly_choice(composed):
    q = composed; q.request["inputs"]["canonical_weekly_choice_sha256"] = "0" * 64
    from nfl_lab import audit_weekly_resume_v1 as resume
    with pytest.raises(resume.ResumeError, match="REGISTERED_CANONICAL_WEEKLY_CHOICE_REQUIRED"):
        w.prepare(q.context(), clock=lambda:DAILY)
    assert not (Path(q.request["output"]) / "PREPARED.json").exists()


@pytest.mark.parametrize("phase", list(w.PENDING_PHASES))
def test_grade_phases_are_visibly_blocked_before_root_or_client_IO(phase, monkeypatch):
    monkeypatch.setattr(w, "native_envelope", lambda:None)
    monkeypatch.setattr(w, "authenticate_child", lambda *_a, **_k:pytest.fail("NO_UNIMPLEMENTED_PHASE_AUTH_OR_IO"))
    with pytest.raises(w.WorkerError, match="OPERATIONS_PHASE_NOT_IMPLEMENTED"):
        w.run(SimpleNamespace(phase=phase), {})


def test_real_native_guard_precedes_imports_and_any_private_path_in_fresh_process():
    script = '''
import sys
from types import SimpleNamespace
from nfl_lab import audit_weekly_operations_worker_v1 as w
try:w.authenticate_child(SimpleNamespace(phase=w.PHASE),{},phase=w.PHASE)
except w.WorkerError as error:assert str(error)=='OPERATIONS_NATIVE_CPU_AS_GUARD_REQUIRED'
else:raise AssertionError('UNGUARDED_WORKER_ACCEPTED')
assert 'nfl_lab.audit_weekly_hosted_v1' not in sys.modules
assert 'numpy' not in sys.modules
print('NATIVE_GUARD_FIRST')
'''
    r = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, env={"PYTHONDONTWRITEBYTECODE":"1"},
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "NATIVE_GUARD_FIRST"


def test_actual_CLI_without_execute_never_reads_requested_private_file():
    r = subprocess.run([sys.executable, "-I", "-B", str(ROOT / w.FILES[1]), w.PHASE,
        "--request", "/nonexistent/SHOULD_NEVER_OPEN"], env={}, capture_output=True, text=True, timeout=10)
    assert r.returncode == 2 and r.stderr == ""
    assert json.loads(r.stdout)["state"] == "OPERATIONS_PREPARATION_ONLY_NO_IO"


def test_CLI_failure_does_not_claim_retention_or_expose_private_error(monkeypatch,capsys):
    from tools import private_draft_store_v2
    def fail():raise ValueError("FICTIONAL_PRIVATE_BODY_SHOULD_NOT_BE_PRINTED:/private/value")
    monkeypatch.setattr(private_draft_store_v2,"limits",fail)
    assert cli.main([w.PHASE,"--execute"],environ={})==1
    result=json.loads(capsys.readouterr().out)
    assert result==dict(state="FAILED_LOCAL",reason="OPERATIONS_WORKER_FAILED",
        metadata_remote_durability_qualified=False,fits=0,public_release=False,successful_forecast=False)


@pytest.mark.parametrize("change", [lambda r:r.update(phase="operations-grade-write"),
    lambda r:r["limits"].update(address_space_bytes=4 << 30), lambda r:r["inputs"].update(authorised=True),
    lambda r:r.update(output=r["output"] + "/escape"), lambda r:r["inputs"]["calendar"]["body"].update(path="/outside/private")])
def test_closed_request_does_not_admit_scope_caps_paths_or_authority_flags(composed, change):
    request = deepcopy(composed.request); change(request)
    with pytest.raises(w.WorkerError):w.validate_request(request, w.PHASE)


def test_contract_lists_pending_phases_and_previous_checkpoint_boundary(capsys):
    assert cli.main(["contract"]) == 2
    value = json.loads(capsys.readouterr().out)
    assert value["supported_phases"] == [w.PHASE] and value["same_week_only"] is False
    assert value["same_week_future_guards_unchanged"] is value["later_week_requires_durable_resolved_history"] is True
    assert value["grade_only_requires_original_prevalue_population"] is True
    assert value["scheduled_grade_only_discovery_ready"] is False
    assert value["previous_checkpoint_requires_unimplemented_live_native_restore"] is False
    assert value["history_requires_live_native_restore"] is True and value["history_json_is_authority"] is False
    assert set(value["history_input_keys"]) == {"sidecar", "public_receipt"}
    assert value["history_archive_roles"] == ["ops_previous_checkpoint_sidecar", "ops_previous_public_receipt"]
    assert value["limits"]["address_space_bytes"] == 512 << 20


def test_native_512_prepare_executes_actual_metadata_writes(composed, tmp_path):
    """Fresh native body test; fictional authority seam, NOT real GHA evidence."""
    seed_path = tmp_path / "fictional-inputs.json"
    seed_path.write_bytes(store.canonical(composed.seed))
    script = r'''
import ast,json,sys
from pathlib import Path
from types import SimpleNamespace
from tools.private_draft_store_v2 import limits
limits()
from nfl_lab import audit_weekly_operations_worker_v1 as w, audit_weekly_runtime_v1 as runtime, state
tree=ast.parse((Path.cwd()/'tests/test_audit_weekly_operations_worker_v1.py').read_text())
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'fixture_verify','composition_context'}]
unit=ast.Module(body=nodes,type_ignores=[]);ast.fix_missing_locations(unit)
exec(compile(unit,'fictional_owned_metadata_context','exec'),globals())
w.Authenticated.verify=fixture_verify
seed=json.loads(Path(sys.argv[1]).read_bytes())
result=w.prepare(composition_context(seed),clock=lambda:state.utc('2026-10-26T08:00:00Z'))
from nfl_lab.operational_storage import OperationalStorage
storage=OperationalStorage(seed['request']['cache'],Path.cwd()/'config/operational-source-policy-v2.json',state=seed['request']['state_root'])
manifest=runtime.read_owned(storage,result['manifest'])
assert manifest['partially_elapsed_week'] is True
assert manifest['active_game_ids']==['fictional-monday']
for role,ref in manifest['archive_context'].items():
 if ref is not None:assert Path(ref['path']).is_file()
assert Path(seed['request']['output'],'OPS_POPULATION.json').is_file()
assert Path(seed['request']['output'],'OPS_ROLES.json').is_file()
assert Path(seed['request']['output'],'OPS_SCHEDULE.json').is_file()
w.native_envelope()
assert 'scipy' not in sys.modules and 'sklearn' not in sys.modules and 'catboost' not in sys.modules
print('PASS_NATIVE_PREPARE_WRITES_180_120_512_FICTIONAL_AUTHORITY')
'''
    profile = json.loads((ROOT / "config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    r = subprocess.run([sys.executable, "-B", "-c", script, str(seed_path)], cwd=ROOT,
        env={"PYTHONDONTWRITEBYTECODE":"1", **profile}, capture_output=True, text=True, timeout=45)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "PASS_NATIVE_PREPARE_WRITES_180_120_512_FICTIONAL_AUTHORITY"


@pytest.fixture
def guard_case(locator_system, tmp_path, monkeypatch):
    """Real bootstrap/client bytecode; fictional Root-validation boundary."""
    from nfl_lab import audit_weekly_hosted_v1 as h, audit_weekly_template_v1 as t
    from nfl_lab import audit_weekly_controller_v1 as c
    x = locator_system
    for role, source in (("parent", x.parent_source), ("producer", x.child_source)):
        for name in w.FILES:
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(("FICTIONAL "+name).encode())
            x.p[role]["code_pins"][name]=store.sha(path.read_bytes())
    document=deepcopy(x.prepared.document)
    document["code_pins"]=deepcopy(x.p["producer"]["code_pins"])
    document["root_template"]["code_pins"]=deepcopy(document["code_pins"])
    x.prepared=t.prepare(document)
    ts=x.template_seal;desc=ts["descriptor"];entry=desc["entry"]
    entry["payload"].update(bytes=len(x.prepared.body),sha256=store.sha(x.prepared.body))
    entry["payload_name"]="blob-"+entry["payload"]["sha256"]+".bin"
    desc.update(manifest_sha256=store.sha(store.canonical(entry)),manifest_bytes=len(store.canonical(entry)))
    ts.update(template_sha256=store.sha(x.prepared.plain),template_bytes=len(x.prepared.plain))
    summary=x.native["template_descriptor"]
    summary.update(template_sha256=ts["template_sha256"],template_bytes=ts["template_bytes"],
        private_descriptor_sha256=store.sha(store.canonical(desc)))
    for field in ("writer","reader"):
        x.native[field].update({k:v for k,v in summary.items() if k!="schema_version"})
    writer={key:deepcopy(ts[key])for key in t.HANDOFF_KEYS};writer["schema_version"]=t.VERSION+"-appended"
    x.native["writer"]["receipt_sha256"]=store.sha(store.canonical(writer))
    x.reg=c.canonical(x.p);x.seal=c.sha(x.reg)
    x.native.update(registration_sha256=x.seal,code_pins_sha256=c.digest(x.p["producer"]["code_pins"]))
    x.go["code_pins"]=deepcopy(x.p["producer"]["code_pins"])
    x.go["effective_epoch"]["controller_context"]["registration_sha256"]=x.seal
    x.bind_root();x.claim.update(registration_sha256=x.seal,root_go_sha256=c.sha(x.raw))
    x.api.data[c.contents_url(x.claim_path,original.D)]=original.content(x.claim_path,c.canonical(x.claim))
    x.api.data[c.API+"/commits/"+original.D]["files"][0]["sha"]=c.blob_sha(c.canonical(x.claim))
    x.publish_locator()
    base=tmp_path/"producer";(base/"journal").mkdir(parents=True,mode=0o700)
    ref=lambda label:dict(path=str(base/label),bytes=1,sha256="1"*64)
    request=dict(schema_version=w.VERSION+"-request",phase=w.PHASE,code_pins=x.go["code_pins"],limits=deepcopy(w.LIMITS),
        cache=str(base/"cache"),state_root=str(base/"state"),output=str(base/w.OUTPUT_NAME),inputs=dict(
            retained_result=ref("retained"),retained_models=ref("models"),calendar=dict(body=ref("calendar"),receipt=ref("receipt")),
            canonical_weekly_choice_sha256="2"*64,capture_id="3"*64,previous_grade_snapshot=None))
    native=dict(schema_version=h.VERSION+"-native-authority",phase=w.PHASE,request_sha256=state.digest(request),
        owner_root_go_sha256=store.sha(x.raw),repository=store.REPO,source_sha=x.env["GITHUB_SHA"],run_id=x.env["GITHUB_RUN_ID"],
        run_attempt=1,job_id=x.env["GITHUB_JOB"],workflow_ref=x.env["GITHUB_WORKFLOW_REF"],api_job_id=31,
        issued_at_utc=x.go["issued_at_utc"],expires_at_utc=x.go["expires_at_utc"],
        actual_actions_api_authenticated=True,owner_root_checked=True,fits=0,public_release=False)
    env=dict(x.env,GITHUB_TOKEN="ghs_FICTIONAL",AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON=store.canonical(native).decode(),
        AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256=state.digest(native))
    args=SimpleNamespace(phase=w.PHASE,request="unused-fictional-parent-context",request_sha256=state.digest(request))
    calls=[]
    real_current=authority.current
    def current(env,raw,_root):
        calls.append("fresh-proof")
        return real_current(env,raw,x.child_source,metadata_get=x.get,event_bytes=x.event,clock=lambda:original.AT,read_head=x.read_head)
    monkeypatch.setattr(w,"native_envelope",lambda:None)
    monkeypatch.setattr(authority,"current",current)
    monkeypatch.setattr(state,"now_utc",lambda:original.AT)
    def validate(go,*,now):
        assert go==x.go;calls.append("static-root");return go
    monkeypatch.setattr(h,"validate_root",validate)
    monkeypatch.setattr(h,"pins",lambda:deepcopy(x.go["code_pins"]))
    def child(args,env,phase,*,operations_proof):
        calls.append("child-context")
        authority._verify(operations_proof,env,x.raw)
        assert args.request_sha256==native["request_sha256"]==state.digest(request)
        job=dict(execution_lane="github_actions",workflow_ref=x.env["GITHUB_WORKFLOW_REF"],workflow_sha=x.env["GITHUB_SHA"],
            job_id=x.env["GITHUB_JOB"],permission="write",event_name="workflow_dispatch",api_job_id=0,run_authenticated=False)
        return request,native,job,x.go
    monkeypatch.setattr(h,"child_context",child)
    def transport(req,timeout):
        assert req.method=="GET" and req.full_url in {c.run_url("300"),c.jobs_url("300")}
        from test_private_draft_store_v2 import Response
        return Response(x.api.data[req.full_url])
    return SimpleNamespace(x=x,request=request,native=native,env=env,args=args,calls=calls,transport=transport,hosted=h)


def test_actual_native_client_and_fresh_typed_scope_before_payload_reads(guard_case):
    q=guard_case;context=w.guard(q.args,q.env,transport=q.transport)
    assert context.verify() is context
    assert q.calls.index("static-root") < q.calls.index("fresh-proof") < q.calls.index("child-context")
    assert type(context.client._audit_operations_current) is authority.CurrentClient
    assert context.actor_binding is context.client._audit_operations_current
    assert context.client.job["api_job_id"]==31 and not Path(q.request["output"]).exists()
    assert not Path(q.request["inputs"]["retained_result"]["path"]).exists()
    with pytest.raises(w.WorkerError):pickle.dumps(context)


def test_generic_authenticator_requires_declared_phase_and_caller_validation(guard_case,monkeypatch):
    q=guard_case
    with pytest.raises(w.WorkerError,match="EXACT_HOSTED_OPERATIONS_PHASE_REQUIRED"):
        w.authenticate_child(q.args,q.env,phase="operations-INVENTED",transport=q.transport)
    q.request["schema_version"]="upstream-private-control-v1";q.request["inputs"]={"caller_owns_this_schema":True}
    q.args.request_sha256=q.native["request_sha256"]=state.digest(q.request)
    context=w.authenticate_child(q.args,q.env,phase=w.PHASE,transport=q.transport)
    with pytest.raises(w.WorkerError,match="CLOSED_OPERATIONS_PREPARE_REQUEST_REQUIRED"):
        w.validate_request(context.request,w.PHASE)


@pytest.mark.parametrize("wrong_output", [False,True])
def test_shared_authenticator_uses_exact_declared_upstream_phase_map(guard_case,wrong_output):
    q=guard_case;phase="operations-retained"
    assert q.hosted.OPERATIONS_PHASES[phase]==("produce",phase)
    q.args.phase=phase;q.request["phase"]=phase;q.native["phase"]=phase
    q.request["schema_version"]="upstream-private-control-v1"
    q.request["inputs"]={"caller_owns_this_schema":True}
    q.request["output"]=str(Path(q.request["cache"]).parent/(w.OUTPUT_NAME if wrong_output else phase))
    q.args.request_sha256=q.native["request_sha256"]=state.digest(q.request)
    q.env["AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON"]=store.canonical(q.native).decode()
    q.env["AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256"]=state.digest(q.native)
    if wrong_output:
        with pytest.raises(w.WorkerError,match="OPERATIONS_GENUINE_CURRENT_API_JOB_REQUIRED"):
            w.authenticate_child(q.args,q.env,phase=phase,transport=q.transport)
    else:
        context=w.authenticate_child(q.args,q.env,phase=phase,transport=q.transport)
        assert context.verify() is context and context.request["output"]==q.request["output"]
    assert not Path(q.request["inputs"].get("path","/nonexistent/fictional-input")).exists()


def test_serialized_authentication_flags_never_create_live_client_scope(guard_case,monkeypatch):
    q=guard_case
    monkeypatch.setattr(authority,"current",lambda *_:dict(actual_actions_api_authenticated=True))
    with pytest.raises(store.StoreError,match="LIVE_OPERATIONS_BOOTSTRAP_REQUIRED"):
        w.guard(q.args,q.env,transport=lambda *_:pytest.fail("NO_NATIVE_CLIENT_HTTP_FOR_JSON_AUTHORITY"))
    assert "child-context" not in q.calls


def test_false_native_attestation_rejected_before_bootstrap_or_client(guard_case):
    q=guard_case;native=deepcopy(q.native);native["actual_actions_api_authenticated"]=False
    q.env["AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON"]=store.canonical(native).decode()
    q.env["AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256"]=state.digest(native)
    with pytest.raises(w.WorkerError,match="CLOSED_OPERATIONS_NATIVE_AUTHORITY_REQUIRED"):
        w.guard(q.args,q.env,transport=lambda *_:pytest.fail("NO_METADATA_IO_FOR_BAD_ATTESTATION"))
    assert q.calls==[]
