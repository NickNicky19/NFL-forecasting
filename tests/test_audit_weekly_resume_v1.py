"""Fictional owned metadata/attestations, separately injected live authority.

The serializer/CAS/epoch/runtime preparation are real code. Native identities
and parent authentication are explicitly fictional seams, not actual Actions
or remote-durability evidence. No model, row, provider or outcome is decoded.
"""
from copy import deepcopy
from datetime import timedelta
import gzip
from pathlib import Path
import pickle
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_resume_v1 as m, audit_weekly_runtime_v1 as runtime
from nfl_lab import audit_weekly_epoch_v1 as epoch, audit_weekly_archive_v1 as archive
from nfl_lab import private_draft_store as store, gha_private_checkpoint as cp, owner_bootstrap_bundle as codec
from nfl_lab.state import digest, utc
from tools import audit_weekly_resume_v1 as cli
from test_audit_weekly_runtime_v1 import packet as runtime_packet
from test_audit_weekly_epoch_v1 import CONTINUED, COUNT7_PINS
from test_audit_weekly_archive_v1 import Service, ROLES

DAILY = utc("2026-10-26T08:00:00Z")


def native(identity, body, binding, started, completed):
    return dict(schema_version="weekly-private-proof-v2.1", phase="restore", operation="restore", repository=store.REPO,
        run_id=identity["run_id"], run_attempt=1, source_sha=identity["source_sha"], process_identity=identity["process_identity"],
        binding_sha256=digest(binding), config_sha256=store.config_sha(), started_at_utc=started.isoformat(), created_at_utc=completed.isoformat(),
        job=dict(execution_lane="github_actions", workflow_ref=identity["workflow_ref"], workflow_sha=identity["source_sha"],
            job_id=identity["job_id"], permission="write", event_name="workflow_dispatch", api_job_id=identity["api_job_id"], run_authenticated=True),
        HTTP_calls=12, transfer_bytes=len(body)+1000, bytes=len(body), payload_sha256=store.sha(body),
        exact_readback=True, separate_process=True, draft_before_after=True)


@pytest.fixture
def case(runtime_packet):
    p=runtime_packet; storage=p.storage; root=p.root/"resume-fixture"; storage.register_root(root)
    def put(name, document):
        return runtime.write(storage,root/name,document)
    def body(name, raw):
        storage.write_bytes(root/name,raw); return cp.binding(root/name)
    # Actual Runtime.prepare writes the FULL EpochChoice, with original clocks.
    prepared=runtime.read_owned(storage,p.runtime.prepare(p.root/"original-preparation"))
    original_choice=prepared["refs"]["choice"]
    corrected=p.runtime.registered.epoch; origin=corrected.origin
    context={"epoch":put("context/epoch.json",corrected.document),
        "epoch_registration":put("context/epoch_registration.json",p.runtime.registered.completion),
        "original_choice":body("context/original_choice.json",p.original["raw"]),
        "origin_witness":put("context/origin_witness.json",origin["completion"]),
        "original_slate":put("context/original_slate.json",origin["slate"]),
        "original_catalog":put("context/original_catalog.json",origin["catalog"]),
        "original_policy":put("context/original_policy.json",origin["policy"])}
    # This index/proof fixture is protocol metadata only. It does not claim
    # execution of a genuine native restore. The parent seam below is separate.
    native_root=storage.register_root(root/"fictional-native")
    service=Service(native_root); binding=service.binding
    current=deepcopy(p.runtime.restored["current"])
    producer=dict(current,run_id="12345",source_sha="a"*40,job_id=ROLES["produce"],api_job_id=777,process_identity="1"*64)
    old_reader=dict(producer,job_id=ROLES["restore"],api_job_id=778,process_identity="2"*64)
    def descriptor(raw, writer, number):
        entry=dict(schema_version="weekly-private-restore-manifest-v2",payload=cp.payload(raw),payload_asset_id=number,
            payload_name="blob-"+store.sha(raw)+".bin",producer_process=writer["process_identity"],binding_sha256=digest(binding),writer_run_id=writer["run_id"])
        return dict(entry=entry,manifest_asset_id=number+1,manifest_sha256=digest(entry),manifest_bytes=len(store.canonical(entry)))
    def bundle(name, choice_ref=original_choice, extras=None, created=DAILY-timedelta(minutes=2), *,
               producer=producer, old_reader=old_reader, current=current):
        aliases={"context/"+k+".json":v for k,v in context.items()}
        aliases["runtime/WEEKLY_CHOICE.json"]=choice_ref
        aliases["prepared/choice.json"]=body(name+"/prepared-choice.json",Path(choice_ref["path"]).read_bytes())
        # These bytes deliberately are not valid JSON/model/forecast bodies.
        # Adapter reads must remain confined to metadata, including on failures.
        aliases["runtime/candidates/rec/COUNT_A.jsonl.gz"]=body(name+"/opaque-private-forecast",b"FICTIONAL_PRIVATE_ROWS_NEVER_DECODE")
        aliases.update(extras or {})
        files=[cp.file_item(v,k,"control") for k,v in sorted(aliases.items())]
        raw_group,inflated=codec.encode(files)
        group=dict(index=0,bytes=len(raw_group),sha256=store.sha(raw_group),inflated_bytes=inflated,files=files,descriptor=descriptor(raw_group,producer,5000))
        census=dict(archive_state="COMPLETE_CAPTURE",logical_files=len(files),logical_bytes=sum(f["bytes"] for f in files),physical_origins=deepcopy(aliases),
            missing_required=[],raw_HTTP_corpus_archived=False,model_weights_reuploaded=False)
        proof=dict(identity=producer,files_sha256=digest(files),census_sha256=digest(census))
        index=dict(schema_version=archive.VERSION+"-index",repository=store.REPO,source_sha=producer["source_sha"],run_id=producer["run_id"],
            root_go_sha256="d"*64,producer=producer,producer_proof=proof,created_at=(CONTINUED+timedelta(minutes=5)).isoformat(),
            runtime_binding_sha256=digest(binding),qualification_sha256="e"*64,files=files,files_sha256=digest(files),groups=[group],census=census,
            archive_state="COMPLETE_CAPTURE",jobs=ROLES,admission={},pending_reservations=[])
        raw_index=gzip.compress(store.canonical(index),mtime=0)
        handoff=dict(schema_version=archive.VERSION+"-handoff",repository=store.REPO,source_sha=producer["source_sha"],run_id=producer["run_id"],
            root_go_sha256="d"*64,producer=producer,runtime_binding=binding,index_descriptor=descriptor(raw_index,producer,6000),files_sha256=digest(files),
            archive_state="COMPLETE_CAPTURE",jobs=ROLES)
        validation=dict(qualified_selected=True,replay_ready=True)
        witness=dict(schema_version=archive.VERSION+"-witness",restorer=old_reader,index_sha256=store.sha(raw_index),files_sha256=digest(files),
            producer_proof_sha256=digest(proof),proofs=[],validation=validation,actual_completed_at=(CONTINUED+timedelta(minutes=10)).isoformat(),
            archive_state="COMPLETE_CAPTURE",public_export_authorized=False,successful_forecast=False)
        raw_witness=gzip.compress(store.canonical(witness),mtime=0)
        values={k:None for k in m.RETAINED_KEYS}
        values.update(schema_version=m.retained.VERSION+"-result",state="PRIVATE_PRIOR_CAPTURE_RESTORED",created_at_utc=created.isoformat(),
            registration_sha256="e"*64,current_root_go_sha256="f"*64,current=current,original_archive=handoff,
            original_reader_handoff=dict(schema_version=archive.VERSION+"-reader-handoff",archive=handoff,restorer=old_reader,witness_descriptor=descriptor(raw_witness,old_reader,7000)),
            original_index=body(name+"/original-index.gz",raw_index),original_reader_witness=body(name+"/original-witness.gz",raw_witness),
            historical_producer_proof=proof,historical_reader_witness=witness,historical_job_evidence={},aliases=aliases,metadata=context,
            original_physical_bindings=deepcopy(aliases),validation=validation,files_sha256=digest(files),HTTP_calls=45,RSS_peak_bytes=1024,
            fits=0,model_decodes=0,source_acquisitions=0,protected_outcome_reads=0,remote_writes=0,model_replay_performed=False,
            public_export_authorized=False,public_release=False,successful_forecast=False)
        values["current_restore_proofs"]=[native(current,raw,binding,created-timedelta(seconds=20),created-timedelta(seconds=10)) for raw in (raw_index,raw_witness,raw_group)]
        return values
    restored=bundle("first")
    fresh=deepcopy(p.runtime.restored)
    fresh.update(current_go_sha256="f"*64,registration_sha256="e"*64,files=38,index_sha256="1"*64,group_sha256=["2"*64],
        source_feed_acquisitions=0,remote_writes=0,protected_outcome_reads=0,successful_forecast=False,scientifically_qualified=False,
        catalog_epoch_ready=False,weekly_choice_restored=False,actual_completed_at=(DAILY-timedelta(minutes=1)).isoformat())
    fresh["proofs"]=[native(current,b"FICTIONAL_MODEL_GROUP_METADATA",binding,DAILY-timedelta(minutes=3),DAILY-timedelta(minutes=2))]
    retained_ref=put("fresh-models/RESTORED.json",fresh)
    assert set(fresh)==m.MODEL_KEYS
    requests=[]
    def auth(request):
        requests.append(deepcopy(request))
        return request["kind"]=="GENUINE_RETAINED_CAPTURE_AND_FRESH_EFFECTIVE18" and request["inputs_sha256"]==digest(dict(
            retained_result=restored,retained_ref=retained_ref,original_weekly_choice_sha256=original_choice['sha256'],
            helper_sha256=m.pins(),source_policy_sha256=cp.POLICY_SHA))
    def calendar(request):
        requests.append(deepcopy(request));return request["kind"]=="CURRENT_COMPLETE_SAME_WEEK_CALENDAR"
    def run(*, at=DAILY, value=None, schedule=None, authority=None, calendar_authority=None, output="resumed", model_ref=None, original_sha=None):
        # Positive callback must bind the exact changed fixture as well.
        selected=restored if value is None else value
        ref=retained_ref if model_ref is None else model_ref
        canonical_sha=original_choice['sha256'] if original_sha is None else original_sha
        def exact(request):
            requests.append(deepcopy(request))
            return request["inputs_sha256"]==digest(dict(retained_result=selected,retained_ref=ref,original_weekly_choice_sha256=canonical_sha,
                helper_sha256=m.pins(),source_policy_sha256=cp.POLICY_SHA))
        return m.resume(selected,ref,p.original["schedule"] if schedule is None else schedule,storage=storage,output=root/output,
            original_weekly_choice_sha256=canonical_sha,authenticate=exact if authority is None else authority,
            authenticate_calendar=calendar if calendar_authority is None else calendar_authority,clock=lambda:at)
    return SimpleNamespace(p=p,root=root,storage=storage,restored=restored,ref=retained_ref,context=context,
        run=run,bundle=bundle,put=put,requests=requests,original_choice=original_choice,fresh=fresh,auth=auth)


@pytest.fixture
def retained_count7_case(tmp_path,monkeypatch):
    # Fictional, fully owned archive/proofs constructed under the exact literal
    # historical interpretation pins; execution switches back to current code
    # before any resume or typed metadata restoration.
    with monkeypatch.context() as old:
        old.setattr(epoch,"implementation_pins",lambda:deepcopy(COUNT7_PINS))
        packet=runtime_packet.__wrapped__(tmp_path,monkeypatch)
        value=case.__wrapped__(packet)
    return value


def test_retained_count7_resume_keeps_originals_and_authenticates_current_helpers(retained_count7_case,monkeypatch):
    c=retained_count7_case
    monkeypatch.setattr("socket.socket",lambda *a,**k:pytest.fail("fictional replay cannot use network"))
    before={role:Path(ref["path"]).read_bytes() for role,ref in c.context.items()}
    old_epoch=c.p.runtime.registered.epoch
    old_registration=deepcopy(c.p.runtime.registered.completion)
    result=c.run();result.verify(DAILY)
    assert result.registered.epoch.document==old_epoch.document
    assert result.registered.epoch.sha256==old_epoch.sha256
    assert result.registered.completion==old_registration
    assert result.original_choice.sha256==c.original_choice["sha256"]
    assert result.choice.document["choice"]==result.original_choice.document["choice"]
    assert result.registered.epoch.document["selection_recipe"]["code_pins"]==COUNT7_PINS
    current=m.pins()
    assert current["nfl_lab/audit_weekly_epoch_v1.py"]!=COUNT7_PINS["nfl_lab/audit_weekly_epoch_v1.py"]
    auth=next(r for r in c.requests if r["kind"]=="GENUINE_RETAINED_CAPTURE_AND_FRESH_EFFECTIVE18")
    assert auth["inputs_sha256"]==digest(dict(retained_result=c.restored,retained_ref=c.ref,
        original_weekly_choice_sha256=c.original_choice["sha256"],helper_sha256=current,source_policy_sha256=cp.POLICY_SHA))
    assert before=={role:Path(ref["path"]).read_bytes() for role,ref in c.context.items()}


def test_retained_count7_uses_same_strict_grading_and_delivery_metadata_callers(retained_count7_case,monkeypatch):
    from nfl_lab import audit_weekly_delivery_v1 as delivery,audit_weekly_operations_grade_v1 as operations_grade
    c=retained_count7_case
    monkeypatch.setattr("socket.socket",lambda *a,**k:pytest.fail("fictional replay cannot use network"))
    aliases=dict(c.restored["aliases"])
    # These lower-level helpers receive the owned aliases AFTER their caller's
    # genuine archive authentication. Unread required fixture roles are opaque;
    # this test makes no claim to execute that live authentication or native IO.
    for name in {"context/"+role+".json" for role in archive.CONTEXT}|{
            "context/public_policy.json","r0/original_board.json"}:
        if name not in aliases:aliases[name]=c.put("typed-fixture/"+name,dict(fictional_opaque_metadata_role=name))
    aliases["prepared/relocated_replay.json"]=c.put("typed-fixture/replay.json",c.p.original["replay"])
    restored=dict(c.restored,aliases=aliases)
    graded,graded_choice=operations_grade._epoch(restored,c.storage,lambda:DAILY)
    delivered,delivered_choice=delivery._typed_epoch(c.storage,aliases,DAILY,c.context["original_choice"]["sha256"])
    for registered in (graded,delivered):
        assert registered.epoch.document==c.p.runtime.registered.epoch.document
        assert registered.completion==c.p.runtime.registered.completion
        registered.verify(DAILY)
    assert graded_choice.sha256==delivered_choice.sha256==c.original_choice["sha256"]


def test_retained_count7_cannot_replace_live_authentication_current_source_or_literal_pins(retained_count7_case):
    c=retained_count7_case
    with pytest.raises(m.ResumeError,match="AUTHENTICATION_REJECTED"):
        c.run(authority=lambda _:False,output="denied-current-authority")
    changed=deepcopy(c.fresh);changed["current"]["source_sha"]="0"*40
    ref=c.put("wrong-current-model-source.json",changed)
    with pytest.raises(m.ResumeError):c.run(model_ref=ref,output="wrong-current-source")
    changed=deepcopy(c.p.runtime.registered.epoch.document)
    changed["selection_recipe"]["code_pins"]["nfl_lab/audit_weekly_origin_v1.py"]="0"*64
    epoch_ref=c.put("tampered-retained-epoch.json",changed)
    value=c.bundle("tampered-retained",extras={"context/epoch.json":epoch_ref})
    with pytest.raises(epoch.EpochError,match="EXACT_RETAINED_EPOCH_SOURCE_PINS"):
        c.run(value=value,output="wrong-retained-pins")
    assert all(not (c.root/name).exists() for name in ("denied-current-authority","wrong-current-source","wrong-retained-pins"))


def test_real_runtime_prepare_keeps_frozen_weekly_dictionary_and_new_capture_commitment(case,monkeypatch):
    c=case; old_bytes=Path(c.original_choice["path"]).read_bytes();old=cp.strict_json(old_bytes)
    reads=[];real=runtime.read_owned
    def metadata_only(storage,ref,*args,**kwargs):
        reads.append(ref["path"])
        assert ref["path"] not in {r["path"] for r in c.fresh["models"]}
        assert "opaque-private-forecast" not in ref["path"] and not ref["path"].endswith(".opaque")
        return real(storage,ref,*args,**kwargs)
    monkeypatch.setattr(runtime,"read_owned",metadata_only)
    result=c.run();result.verify(DAILY)
    calendar_request=next(r for r in c.requests if r["kind"]=="CURRENT_COMPLETE_SAME_WEEK_CALENDAR")
    assert calendar_request["inputs_sha256"]==digest(dict(full_schedule=c.p.original["schedule"],
        original_weekly_choice_sha256=result.original_choice.sha256,epoch_sha256=result.registered.epoch.sha256,
        current_root_go_sha256=c.restored["current_root_go_sha256"]))
    assert result.choice.document["choice"]==old["choice"]
    expected=deepcopy(old);expected['slate']['game_cutoffs']=result.choice.document['slate']['game_cutoffs']
    assert result.choice.document==expected
    assert 'capture_scope' not in result.choice.document and 'capture_scope' not in result.choice.document['slate']
    assert result.registered.epoch.document==c.p.runtime.registered.epoch.document
    assert result.registered.completion==c.p.runtime.registered.completion
    assert result.choice.sha256!=result.original_choice.sha256
    assert set(result.choice.document)==set(old)
    assert result.choice.document["slate"]["scheduled_first_kickoff_utc"]==old["slate"]["scheduled_first_kickoff_utc"]
    assert utc(old["slate"]["scheduled_first_kickoff_utc"])<DAILY
    assert result.choice.document["slate"]["weekly_deadline_utc"]==old["slate"]["weekly_deadline_utc"]
    assert set(result.choice.document["slate"]["game_cutoffs"])=={"fictional-monday"}
    assert result.document["capture_scope"]["elapsed_game_ids"]==["fictional-elapsed","fictional-sunday"]
    assert result.document["grade_population_registered"] is result.document["prospective_grade_evidence"] is False
    assert result.document['existing_primary_assignments_unchanged'] is True
    assert Path(c.original_choice["path"]).read_bytes()==old_bytes
    # Actual constructor reads only model MANIFEST metadata, never opaque model
    # bytes; preparation then performs its real owned-CAS receipt/readback.
    monkeypatch.setattr(runtime,"read_owned",real)
    class Clock:
        value=DAILY+timedelta(seconds=1)
        def __call__(self):self.value+=timedelta(microseconds=1);return self.value
    clock=Clock()
    backend=runtime.Runtime(c.storage,result.registered,result.choice,c.ref,c.p.runtime.config,clock=clock)
    prepared=real(c.storage,backend.prepare(c.root/"actual-runtime-prepare"))
    full=real(c.storage,prepared["refs"]["choice"])
    assert full==result.choice.document and full["choice"]==old["choice"]
    versions=real(c.storage,prepared["refs"]["selected_versions"])
    assert versions["choice_sha256"]==result.choice.sha256
    old_versions=epoch.selected_versions(result.registered,result.original_choice,relocated_replays=(result.replay,),now=clock())
    assert versions["rows"]==old_versions["rows"]
    completion=real(c.storage,prepared["choice_completion"])
    permit=epoch.authorize_capture(result.registered,result.choice,completion,relocated_replays=(result.replay,),clock=clock)
    assert permit.document["game_cutoffs"]==result.choice.document["slate"]["game_cutoffs"]
    assert len(result.inputs)==9 and result.document["source_refresh_required"] is True
    with pytest.raises(m.ResumeError,match="NOT_LIVE_AUTHORITY"):pickle.dumps(result)


def test_expired_future_cutoff_fails_without_dropping_sunday_or_extending_clock(case):
    with pytest.raises(m.ResumeError,match="EXPIRED_FUTURE_CUTOFF"):
        case.run(at=utc("2026-10-26T19:45:00Z"))
    assert not (case.root/"resumed").exists()
    assert set(cp.strict_json(Path(case.original_choice["path"]).read_bytes())["slate"]["game_cutoffs"])=={"fictional-sunday","fictional-monday"}


def test_actual_full_choice_missing_future_original_cutoff_never_becomes_coverage_cut(case):
    c=case;document=runtime.read_owned(c.storage,c.original_choice)
    del document["slate"]["game_cutoffs"]["fictional-monday"]
    # A complete current calendar remains authentic. Changing the old choice
    # fixture/index does not authorize inventing its missing Monday cutoff.
    incomplete=c.put("missing-original-cutoff.json",document)
    values=c.bundle("missing-future-cutoff",incomplete)
    with pytest.raises(m.ResumeError,match="ALL_FUTURE_GAMES_MUST_HAVE_ORIGINAL_CUTOFFS"):
        c.run(value=values,original_sha=incomplete['sha256'])
    assert not (c.root/"resumed").exists()


def test_sealed_resume_canonical_choice_cannot_be_replaced_with_scoped_choice(case):
    result=case.run()
    result.original_choice=result.choice
    with pytest.raises(m.ResumeError,match="LIVE_RESUME_CHANGED"):
        result.verify(DAILY)


@pytest.mark.parametrize("change",["kickoff","remove_elapsed","add_game","new_week","score_column"])
def test_changed_or_incomplete_calendar_rejected_before_any_output(case,change):
    schedule=deepcopy(case.p.original["schedule"])
    if change=="kickoff":schedule[-1]["kickoff_utc"]="2026-10-26T21:00:00Z"
    elif change=="remove_elapsed":schedule.pop(0)
    elif change=="add_game":schedule.append(dict(schedule[-1],game_id="fictional-extra"))
    elif change=="new_week":schedule[-1]["week"]=8
    else:schedule[-1]["score"]=0
    with pytest.raises(m.ResumeError,match="CALENDAR"):case.run(schedule=schedule)
    assert not (case.root/"resumed").exists()


def test_saved_flags_cannot_replace_live_auth_and_calendar_auth_before_scope(case,monkeypatch):
    original=runtime.read_owned
    monkeypatch.setattr(runtime,"read_owned",lambda *a,**kw:pytest.fail("private read before initial live authority"))
    with pytest.raises(m.ResumeError,match="AUTHENTICATION_REJECTED"):case.run(authority=lambda r:False)
    monkeypatch.setattr(runtime,"read_owned",original)
    with pytest.raises(m.ResumeError,match="AUTHENTICATION_REJECTED"):case.run(calendar_authority=lambda r:False)
    assert not (case.root/"resumed").exists()


@pytest.mark.parametrize("change",["missing_proof","stale_model_job","unqualified_model","epoch_pin"])
def test_changed_proofs_model_result_or_frozen_implementation_do_not_resume(case,change,monkeypatch):
    value=deepcopy(case.restored);ref=case.ref
    if change=="missing_proof":value["current_restore_proofs"].pop()
    elif change in {"stale_model_job","unqualified_model"}:
        fresh=deepcopy(case.fresh)
        if change=="stale_model_job":fresh["current"]["run_id"]="12345"
        else:fresh["model_artifact_durability"]=False
        ref=case.put("changed-model-result.json",fresh)
    else:monkeypatch.setattr(epoch,"implementation_pins",lambda:{"unregistered":"0"*64})
    with pytest.raises((m.ResumeError,epoch.EpochError)):case.run(value=value,model_ref=ref)
    assert not (case.root/"resumed").exists()


def test_repeated_same_week_capture_carries_canonical_weekly_anchor_not_last_scope(case):
    c=case;first=c.run(at=DAILY,output="first-resume")
    old=first.document["archive_context"]
    values=c.bundle("later-capture",first.inputs["choice"],extras={m.CANONICAL_ROLE:old["canonical_weekly_choice"],m.SCOPE_ROLE:old["capture_scope"]},created=DAILY+timedelta(minutes=10))
    second=c.run(value=values,at=DAILY+timedelta(minutes=20),output="second-resume")
    assert second.original_choice.sha256==first.original_choice.sha256
    assert second.choice.document["choice"]==first.choice.document["choice"]
    assert second.choice.sha256==first.choice.sha256
    assert second.document['capture_scope_binding']['sha256']!=first.document['capture_scope_binding']['sha256']
    assert second.document["capture_scope"]["prior_capture_choice_sha256"]==first.choice.sha256
    assert second.document["capture_scope"]["original_weekly_choice_sha256"]==first.original_choice.sha256
    assert second.document["grade_population_registered"] is False
    assert second.document['prospective_grade_evidence'] is False and second.document['existing_primary_assignments_unchanged'] is True
    # An archived scoped choice cannot silently become a new weekly anchor.
    missing=c.bundle("missing-anchor",first.inputs["choice"])
    with pytest.raises(m.ResumeError,match="REGISTERED_CANONICAL_WEEKLY_CHOICE_REQUIRED"):
        c.run(value=missing,at=DAILY+timedelta(minutes=30),output="wrong-reset")


def _same_source_models(c,current,at,name):
    # New CURRENT fictional receipts only. Original archive proofs stay byte
    # identical; this never rehydrates a saved Actions authority.
    fresh=deepcopy(c.fresh);fresh['current']=deepcopy(current)
    aliases=runtime.read_owned(c.storage,c.fresh['relocation_catalog'])
    aliases['current']=deepcopy(current)
    fresh['relocation_catalog']=c.put(name+'.aliases.json',aliases)
    fresh['actual_completed_at']=(at-timedelta(minutes=1)).isoformat()
    fresh['proofs']=[native(current,b'FICTIONAL_MODEL_GROUP_METADATA',c.restored['original_archive']['runtime_binding'],
        at-timedelta(minutes=3),at-timedelta(minutes=2))]
    return c.put(name,fresh)


def test_two_unchanged_code_cycles_keep_original_weekly_choice_and_fresh_current_proofs(case):
    c=case;original_bytes=Path(c.original_choice['path']).read_bytes()
    source=c.restored['original_archive']['source_sha']
    current=dict(c.restored['current'],source_sha=source,job_id=ROLES['produce'],api_job_id=2001,process_identity='4'*64)
    first_metadata=c.bundle('same-source-first',current=current)
    original_history=deepcopy(first_metadata['original_reader_handoff'])
    first=c.run(value=first_metadata,model_ref=_same_source_models(c,current,DAILY,'first-current-models.json'),output='first-same-source')
    at=DAILY+timedelta(minutes=30)
    producer=dict(current,job_id=ROLES['produce'],api_job_id=2001,process_identity='4'*64)
    old_reader=dict(producer,job_id=ROLES['restore'],api_job_id=2002,process_identity='5'*64)
    second_current=dict(current,run_id='12347',api_job_id=2003,process_identity='6'*64)
    second_metadata=c.bundle('same-source-second',first.inputs['choice'],extras={
        'context/canonical_weekly_choice.json':first.document['archive_context']['canonical_weekly_choice'],
        'context/capture_scope.json':first.document['archive_context']['capture_scope']},created=at-timedelta(minutes=2),
        producer=producer,old_reader=old_reader,current=second_current)
    second=c.run(value=second_metadata,at=at,model_ref=_same_source_models(c,second_current,at,'second-current-models.json'),output='second-same-source')
    assert first_metadata['original_reader_handoff']==original_history
    assert first_metadata['current']['run_id']!=first_metadata['original_archive']['run_id']
    assert second_metadata['current']['run_id']!=second_metadata['original_archive']['run_id']==current['run_id']
    assert all(v['current']['source_sha']==v['original_archive']['source_sha']==source for v in (first_metadata,second_metadata))
    assert first.choice.document['choice']==second.choice.document['choice']==c.p.runtime.choice.document['choice']
    assert first.choice.sha256==second.choice.sha256
    assert first.document['capture_scope']!=second.document['capture_scope']
    assert Path(c.original_choice['path']).read_bytes()==original_bytes
    assert not second.document['prospective_grade_evidence']


@pytest.mark.parametrize('failure',['same_run','producer_process','reader_process','reused_api_job'])
def test_same_source_still_requires_new_retained_run_job_and_process(case,failure,monkeypatch):
    c=case;producer=c.restored['original_archive']['producer'];reader=c.restored['original_reader_handoff']['restorer']
    current=dict(c.restored['current'],source_sha=producer['source_sha'])
    if failure=='same_run':current['run_id']=producer['run_id']
    elif failure=='reused_api_job':current['api_job_id']=producer['api_job_id']
    else:current['process_identity']=(producer if failure=='producer_process' else reader)['process_identity']
    value=c.bundle('not-fresh-current',current=current)
    monkeypatch.setattr(m._Metadata,'read',lambda *_args,**_kwargs:pytest.fail('READ_BEFORE_FRESH_IDENTITY'))
    with pytest.raises(m.ResumeError,match='CURRENT_RETAINED_IDENTITY|FRESH_RETAINED_JOB_AND_PROCESS'):
        c.run(value=value,output='rejected-same-source')


def test_cli_prepares_unapproved_contract_and_never_loads_json_authority(tmp_path,capsys):
    path=tmp_path/"contract.json"
    assert cli.main(["contract","--output",str(path)])==0
    assert cp.strict_json(path.read_bytes())["approved"] is False
    assert cli.main(["resume","--execute"])==2
    assert "LIVE_IN_PROCESS_PARENT_AUTHENTICATION_REQUIRED" in capsys.readouterr().out
