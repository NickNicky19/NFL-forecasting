"""Real old-pin sidecar/parts/snapshot semantics, fictional native transports.

Only Owner/Seal/current-job and source-profile qualification are labeled native
fixture boundaries. No history reader, handoff, snapshot/durability function is
mocked. The two original public Git source bodies are exact0409 bytes.
"""
import base64
from copy import deepcopy
from datetime import timedelta
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import socket
from types import MethodType,SimpleNamespace

import pytest
from nfl_lab import audit_weekly_controller_v1 as c
from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
from nfl_lab import audit_weekly_grade_history_v1 as history
from nfl_lab import audit_weekly_grade_v1 as grade
from nfl_lab import audit_weekly_grade_checkpoint_v1 as checkpoint
from nfl_lab import audit_weekly_template_v1 as template
from nfl_lab import private_draft_store as store,state,gha_private_checkpoint as cp
from nfl_lab import weekly_mae_display_profile_v1 as profile
import test_audit_weekly_grade_history_v1 as old
from test_audit_weekly_source_history_v2 import _source_v2_retime

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=json.loads((Path(__file__).parent/'fixtures/weekly_v5_history_original_source_2pins.json').read_bytes())
ORIGINAL={n:gzip.decompress(base64.b64decode(v['gzip_base64'])) for n,v in PUBLIC['files'].items()}
assert all(store.sha(b)==PUBLIC['files'][n]['sha256'] and len(b)==PUBLIC['files'][n]['bytes'] for n,b in ORIGINAL.items())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *_:pytest.fail('REAL_NETWORK_FORBIDDEN'))


@pytest.fixture(scope='module')
def old_pin_seed(tmp_path_factory):
    # Only minting fictional ORIGINAL metadata uses its original public pin
    # inventory. Every patched pin function is restored before the new reader.
    gp=grade.pins();hp=checkpoint.pins()
    gp['nfl_lab/audit_weekly_retained_v1.py']=PUBLIC['files']['nfl_lab/audit_weekly_retained_v1.py']['sha256']
    hp['tests/test_audit_weekly_grade_checkpoint_v1.py']=PUBLIC['files']['tests/test_audit_weekly_grade_checkpoint_v1.py']['sha256']
    with pytest.MonkeyPatch.context() as m:
        m.setattr(grade,'pins',lambda:deepcopy(gp));m.setattr(checkpoint,'pins',lambda:deepcopy(hp))
        seed=old.original_seed.__wrapped__(tmp_path_factory)
        seed['sources'].update({n:base64.b64encode(b).decode() for n,b in ORIGINAL.items()})
        actual_grade=grade.grade;actual_parts=grade._write_snapshot_v2
        def split(storage,output,document,*,part_bytes=None):
            size=sum(len(b) for b in grade._canonical_chunks(document))
            return actual_parts(storage,output,document,part_bytes=min(64<<20,(size+1)//2))
        def multipart(*a,**kw):kw.setdefault('wire_version',2);return actual_grade(*a,**kw)
        m.setattr(grade,'grade',multipart);m.setattr(grade,'_write_snapshot_v2',split)
        slots=[dict(target=a,family=b,method_id=d,procedure_version='1'*64,model_sha256='2'*64,
            manifest_sha256='3'*64,transport_manifest_sha256='4'*64) for a,b,d in template.JOBS]
        static=dict(repository=store.REPO,mode=c.MODE,single_writer_group=c.GROUP,
            workflow_ref=seed['sidecar']['workflow_ref'],retained_registration=dict(
                schema_version='audit-count-retained-v1-registration',approved=True,maximum_new_fits=0,public_release=False,
                origin=dict(replay_catalog=dict(slots=slots))))
        result=old.locator_seed.__wrapped__(tmp_path_factory.mktemp('old-v4-pinned-history'),seed,m,
            source_transition=True,closed_v4=True,root_static=static,historical_bot=True)
        result['sources'].update({n:base64.b64encode(b).decode() for n,b in ORIGINAL.items()})
    assert set(n for n,h in result['sidecar']['grade_code_pins'].items() if h!=grade.pins()[n])=={'nfl_lab/audit_weekly_retained_v1.py'}
    assert set(n for n,h in result['sidecar']['checkpoint_helper_sha256'].items() if h!=checkpoint.pins()[n])=={'tests/test_audit_weekly_grade_checkpoint_v1.py'}
    return result


def _native_owner(context,root,receipt,tmp_path,monkeypatch):
    """Synthetic current Owner/Seal, never an actual native admission."""
    import test_audit_weekly_controller_v1 as fixture
    native=tmp_path/'native-registration';native.mkdir()
    x=fixture.system.__wrapped__(native);p=deepcopy(x.p)
    p['registered_at_utc']=(state.utc(root['issued_at_utc'])-timedelta(hours=1)).isoformat()
    p['producer'].update(source_sha=root['source_sha'],branch='fictional',code_pins=deepcopy(root['code_pins']),
        workflow_sha256=root['code_pins']['.github/workflows/lab.yml'])
    encoded=gzip.compress(store.canonical(receipt),mtime=0)
    ready=dict(source_sha=receipt['source_sha'],branch='fictional',run_id=receipt['run_id'],workflow_sha256=receipt['workflow_sha256'],
        jobs=deepcopy(receipt['jobs']),receipt_sha256=store.sha(encoded),receipt_body_sha256=store.sha(store.canonical(receipt)),
        receipt_bindings={n:receipt[n] for n in c.RECEIPT_HASH_KEYS})
    p['readiness']=ready
    body=history._source_history_unwrap(root['source_history_binding']);a=deepcopy(c.V5_HISTORICAL_AUTHORITY)
    a.update({n:receipt[n] for n in ('source_sha','run_id','root_go_sha256','workflow_sha256','jobs')})
    a.update(branch='fictional',receipt_sha256=ready['receipt_sha256'],receipt_body_sha256=ready['receipt_body_sha256'],
        root_static_sha256=body['predecessor']['root_static_sha256'],code_pins_sha256=body['predecessor']['code_pins_sha256'],
        source_history_binding_sha256=body['predecessor_source_history_sha256'])
    monkeypatch.setattr(c,'V5_HISTORICAL_AUTHORITY',a)
    p=c.historical_v5_registration(root,p);reg=store.canonical(p);c.registration(reg,sealed_sha256=store.sha(reg),at=history.now())
    fixed=deepcopy(root);fixed['approved']=False
    for n in template.DYNAMIC_FIELDS-{'approved'}:fixed[n]=None
    prepared=template.prepare(dict(schema_version=template.STATIC_V5,source_sha=root['source_sha'],code_pins=root['code_pins'],
        readiness=ready,root_template=fixed))
    seal=object.__new__(bootstrap.Seal);seal.registration_bytes=reg;seal.registration_sha256=store.sha(reg)
    seal.document=dict(owner_registration_completed_at=p['registered_at_utc'],static_public_policy_sha256=root['publication_registration']['policy_sha256'])
    seal.template_descriptor=dict(template_sha256=store.sha(prepared.plain),template_bytes=len(prepared.plain))
    seal.verify=MethodType(lambda self:self,seal)
    proof=object.__new__(bootstrap.Owner);proof.bootstrap_seal=seal
    proof.document=dict(actor=deepcopy(c.OWNER),registration_sha256=seal.registration_sha256,
        source_sha=root['source_sha'],run_id=context.client.run_id,job_id=context.client.job['job_id'],api_job_id=context.client.job['api_job_id'],
        root_go_sha256=context.root_sha256)
    def verify(self,*,root_sha256):assert root_sha256==context.root_sha256;return self
    proof.verify=MethodType(verify,proof);context.proof=proof
    return SimpleNamespace(p=p,proof=proof,seal=seal)


@pytest.fixture
def pinned_case(old_pin_seed,tmp_path,monkeypatch):
    seed=deepcopy(old_pin_seed);x=old.source_transition_case(tmp_path/'reader',seed,monkeypatch,runtime_transition='DUAL_RUNTIME_ROTATE')
    root=x.context.go;root['schema_version']=history.ROOT_V5
    policy=store.canonical(dict(source_sha=root['source_sha'],registered_at_utc=root['issued_at_utc'],fictional_static_metadata=True))
    root['publication_registration'].update(policy_sha256=store.sha(policy),policy_gzip_base64=base64.b64encode(gzip.compress(policy,mtime=0)).decode())
    root['code_pins'].update(grade.pins());root['code_pins'].update(checkpoint.pins())
    for n in history.LOCATOR_HELPERS:root['code_pins'][n]=store.sha((ROOT/n).read_bytes())
    body=history._source_history_unwrap(root['source_history_binding'])
    body.update(schema_version=history.SOURCE_HISTORY_BINDING_V2,target_policy_sha256=root['publication_registration']['policy_sha256'],predecessor_root_schema=history.ROOT_V4,
        predecessor_source_history_sha256=store.sha(store.canonical(seed['original_root']['source_history_binding'])),
        pin_overrides={n:h for n,h in seed['original_root']['code_pins'].items() if h!=root['code_pins'][n]})
    root['source_history_binding']=history.source_history_envelope(body)
    _source_v2_retime(root['qualified_runtime'],(state.utc(root['issued_at_utc'])-timedelta(hours=1)).isoformat())
    root['mae_helper_pins']={n:store.sha(('FICTIONAL_SOURCE:'+n).encode()) for n in profile.HELPERS}
    root['mae_registration']=dict(path=profile.REGISTRATION_PATH,bytes=512,sha256=root['mae_helper_pins'][profile.REGISTRATION_PATH])
    declared={n:dict(before_sha256=h,after_sha256=root['code_pins'][n]) for n,h in body['pin_overrides'].items()}
    # Explicit existing incomplete Root/source qualification fixture boundary;
    # no runtime grant or expected history pins are supplied by this callback.
    monkeypatch.setattr(profile,'validate_metadata',lambda *_:dict(mae_runtime_pin_profile=dict(changed_paths=declared)))
    x.context.root_sha256=store.sha(store.canonical(root));x.native=_native_owner(x.context,root,seed['receipt'],tmp_path,monkeypatch)
    x.root_before=store.canonical(root);return x


def test_real_two_old_pins_restore_all_parts_snapshot_durability_and_old_digest(pinned_case):
    x=pinned_case
    with pytest.raises(history.HistoryError,match='SAME_CODE_CLOSED_HISTORY_SIDECAR_REQUIRED'):history._sidecar(x.seed['sidecar'])
    with pytest.raises(checkpoint.CheckpointError,match='CLOSED_EXACT_GRADING_CHECKPOINT_HANDOFF'):
        checkpoint.safe_handoff(x.seed['sidecar']['checkpoint_handoff'])
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert grade._digest(result.durable.document)==x.seed['durable_sha256']
    assert result.durable.document['code_pins']==x.seed['sidecar']['grade_code_pins']!=grade.pins()
    assert result.durable.document['known_versions']==x.seed['known_versions']
    assert result.durable.document['known_weeks']==x.seed['known_weeks']
    assert result.proof['original_grade_read_proof']==x.seed['sidecar']['grade_read_proof']
    assert len(result.proof['native_part_recovery']['parts'])==2
    assert result.proof['current']['source_sha']==x.context.go['source_sha']!=x.seed['source']
    assert all(r.method=='GET' and r.data is None for r in x.calls)
    assert store.canonical(x.context.go)==x.root_before
    # Persisted durable wire preserves the old document and pin inventory too.
    decoded=grade._load_snapshot(x.storage,result.binding)
    assert grade._digest(decoded)==x.seed['durable_sha256'] and decoded['code_pins']==x.seed['sidecar']['grade_code_pins']


def scope_arguments(x):
    packed=cp.read_ref(x.sidecar,64<<10);receipt=cp.read_ref(x.receipt,64<<10)
    wrapper=history.metadata_document(packed);value=history.metadata_document(receipt)
    package,_=template.checkpoint_runtime(x.context.go,wrapper['sidecar']['checkpoint_handoff'])
    pins=history.source_history_scope(x.context.go,value,locator=wrapper,locator_sha256=store.sha(packed))
    return [x.context,packed,receipt,wrapper,value,package,pins,history._PINNED_V5_KEY]


@pytest.mark.parametrize('damage,reason',[
    ('JSON-context','LIVE_EXACT_V5_PINNED_HISTORY_CONTEXT_REQUIRED'),
    ('missing-owner','LIVE_EXACT_V5_PINNED_HISTORY_CONTEXT_REQUIRED'),
    ('bot-current','EXACT_V5_OWNER_HISTORY_ROOT_REQUIRED'),
    ('V4-root','EXACT_V5_OWNER_HISTORY_ROOT_REQUIRED'),
    ('parent-context','EXACT_V5_OWNER_HISTORY_ROOT_REQUIRED'),
    ('current-root','EXACT_V5_OWNER_HISTORY_ROOT_REQUIRED'),
    ('locator-bytes','EXACT_V5_HISTORY_ORIGINAL_PUBLIC_BYTES'),
    ('receipt-bytes','EXACT_V5_HISTORY_ORIGINAL_PUBLIC_BYTES'),
    ('locator-value','EXACT_V5_HISTORY_ORIGINAL_PUBLIC_BYTES'),
    ('receipt-value','EXACT_V5_HISTORY_ORIGINAL_PUBLIC_BYTES'),
    ('full-pin-map','EXACT_V5_HISTORY_ORIGINAL_FULL_PIN_INVENTORY'),
    ('package','SOURCE_HISTORY_DISCOVERY_ORIGINAL_RUNTIME'),
    ('math-kernel','UNCHANGED_ORIGINAL_V5_GRADING_AND_CHECKPOINT_KERNELS'),
])
def test_closed_v5_context_and_original_source_bindings_reject_before_private_GET(pinned_case,monkeypatch,damage,reason):
    x=pinned_case;a=scope_arguments(x);before=len(x.calls)
    if damage=='JSON-context':a[0]={'approved':True}
    elif damage=='missing-owner':x.context.proof=None
    elif damage=='bot-current':x.context.proof.document['actor']=deepcopy(c.BOT)
    elif damage=='V4-root':x.context.go['schema_version']=history.ROOT_V4
    elif damage=='parent-context':x.context.go['effective_epoch']['controller_context']={}
    elif damage=='current-root':x.context.root_sha256='0'*64
    elif damage=='locator-bytes':a[1]=gzip.compress(b'{}',mtime=0)
    elif damage=='receipt-bytes':a[2]=gzip.compress(b'{}',mtime=0)
    elif damage=='locator-value':a[3]['sidecar']['checkpoint_helper_sha256']['tests/test_audit_weekly_grade_checkpoint_v1.py']='0'*64
    elif damage=='receipt-value':a[4]['policy_sha256']='0'*64
    elif damage=='full-pin-map':a[6]['nfl_lab/audit_weekly_retained_v1.py']='0'*64
    elif damage=='package':a[5]['runtime_id']='0'*32
    else:
        current=grade.pins();current['nfl_lab/audit_weekly_grade_v1.py']='0'*64
        monkeypatch.setattr(grade,'pins',lambda:current)
    expected=store.StoreError if damage=='package' else history.HistoryError
    with pytest.raises(expected,match=reason):history._PinnedV5History(*a)
    assert len(x.calls)==before


def metadata_jobs(x):
    response=x.api(SimpleNamespace(method='GET',data=None,full_url=store.API+'/actions/runs/'+x.seed['old_run']+'/jobs?per_page=100&page=1'),20)
    jobs=json.loads(response.body)['jobs'];refs=x.seed['receipt']['jobs']
    return {role:next(j for j in jobs if j['id']==ref['api_job_id']) for role,ref in refs.items()}


def test_live_scope_rejects_metadata_mutation_serialization_and_cross_process_reuse(pinned_case,monkeypatch):
    x=pinned_case;scope=history._PinnedV5History(*scope_arguments(x));jobs=metadata_jobs(x)
    bad=deepcopy(jobs);bad['restore']['conclusion']='failure'
    with pytest.raises(history.HistoryError,match='SUCCESSFUL_PARENT_HISTORY_API_JOB_METADATA'):scope.metadata(bad)
    with pytest.raises(history.HistoryError,match='LIVE_V5_ORIGINAL_METADATA_BEFORE_HANDOFF_USE'):
        scope.handoff(x.seed['sidecar']['checkpoint_handoff'])
    scope.metadata(jobs);scope.verify()
    with pytest.raises(history.HistoryError,match='V5_PINNED_HISTORY_CANNOT_BE_SERIALIZED'):pickle.dumps(scope)
    with pytest.raises(history.HistoryError,match='LIVE_V5_PINNED_HISTORY_SCOPE_REQUIRED'):
        history._restore_pinned_v5_snapshot({},x.storage,{},None,authenticate=None,at=history.now())
    with pytest.raises(history.HistoryError,match='ACTUAL_V5_NATIVE_ROOT_BEFORE_SNAPSHOT_DECODE'):
        history._restore_pinned_v5_snapshot(scope,x.storage,{},None,authenticate=None,at=history.now())
    for field,value in [('pins',dict(scope.pins,**{'nfl_lab/audit_weekly_retained_v1.py':'0'*64})),
        ('current',dict(scope.current,run_id='999999')),('_metadata',{}),('_native','0'*64),('process','0'*64)]:
        saved=getattr(scope,field);setattr(scope,field,value)
        with pytest.raises(history.HistoryError,match='V5_PINNED_HISTORY_SCOPE_CHANGED_OR_FOREIGN_PROCESS'):scope.verify()
        setattr(scope,field,saved);scope.verify()
    with monkeypatch.context() as m:
        m.setattr(history,'now',lambda:state.utc(x.context.go['expires_at_utc']))
        with pytest.raises(history.HistoryError,match='V5_PINNED_HISTORY_SCOPE_CHANGED_OR_FOREIGN_PROCESS'):scope.verify()
    scope.verify()


@pytest.mark.parametrize('field',['source_sha','run_id','root_go_sha256','receipt_sha256','code_pins_sha256','source_history_binding'])
def test_no_other_predecessor_or_implicit_v1_can_enter_closed_reader(pinned_case,field):
    x=pinned_case;a=scope_arguments(x);root=x.context.go;body=history._source_history_unwrap(root['source_history_binding'])
    if field=='source_history_binding':
        body['schema_version']=history.SOURCE_HISTORY_BINDING
        del body['predecessor_root_schema'];del body['predecessor_source_history_sha256']
        body['pin_overrides']={n:h for n,h in body['pin_overrides'].items() if n not in history._MAE_RUNTIME_OVERRIDE_PATHS}
    else:body['predecessor'][field]='0'*40 if field=='source_sha' else '999999' if field=='run_id' else '0'*64
    if field=='run_id':
        parts=body['predecessor']['locator']['path'].split('--');parts[1]=body['predecessor']['run_id']
        body['predecessor']['locator']['path']='--'.join(parts)
    root['source_history_binding']=history.source_history_envelope(body)
    # Explicit synthetic current-owner boundary, re-bound only to exercise the
    # independent exact historical authority rather than the earlier Root hash.
    x.context.root_sha256=store.sha(store.canonical(root));before=len(x.calls)
    with pytest.raises(c.ControllerError,match='EXACT_V5_SOURCE_HISTORY_HISTORICAL_BOT_PREIMAGE'):history._PinnedV5History(*a)
    assert len(x.calls)==before


@pytest.mark.parametrize('damage,reason',[
    ('actor','EXACT_V5_ORIGINAL_BOT_HISTORY_RUN_REQUIRED'),
    ('trigger-missing','EXACT_V5_ORIGINAL_BOT_HISTORY_RUN_REQUIRED'),
    ('trigger-owner','ORIGINAL_COMPLETED_HISTORY_DELIVERY_RUN_REQUIRED')])
def test_fresh_original_bot_run_and_trigger_are_required_before_private_read(pinned_case,damage,reason):
    from test_private_draft_store_v2 import Response
    x=pinned_case;transport=x.api;url=store.API+'/actions/runs/'+x.seed['old_run']
    def changed(request,timeout):
        result=transport(request,timeout)
        if request.full_url==url:
            run=json.loads(result.body)
            if damage=='actor':run['actor']=deepcopy(c.OWNER);run['triggering_actor']=deepcopy(c.OWNER)
            elif damage=='trigger-missing':del run['triggering_actor']
            else:run['triggering_actor']=deepcopy(c.OWNER)
            return Response(run)
        return result
    x.context.client.transport=changed
    with pytest.raises(history.HistoryError,match=reason):history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=changed)
    assert not any('/releases/' in q.full_url for q in x.calls)


def test_snapshot_adapter_preserves_owned_alias_checks_after_real_native_root_read(pinned_case,tmp_path):
    from nfl_lab.operational_storage import StorageIntegrityError
    x=pinned_case;scope=history._PinnedV5History(*scope_arguments(x));scope.metadata(metadata_jobs(x))
    h=x.seed['sidecar']['checkpoint_handoff'];client=history._client(x.context,'restore',x.api,package=scope.package)
    # Real mocked transport/descriptor/manifest/payload GETs and native proof.
    destination=tmp_path/'reader/again-SNAPSHOT.json.gz';proof=store.restore(client,h['descriptor'],destination)
    owned=tmp_path/'reader/again-owned-SNAPSHOT.json.gz';x.storage.import_file(destination,owned,expected_sha256=h['body_sha256'])
    ref=cp.binding(owned);scope.native(ref,proof,client)
    assert scope._native==state.digest(ref)
    foreign=tmp_path/'outside-owned-storage.json.gz';foreign.write_bytes(owned.read_bytes());bad=cp.binding(foreign)
    # A valid body/native read does not confer ownership on a foreign alias.
    scope.native(bad,proof,client)
    registered=history._registered(x.context,x.storage)
    with pytest.raises(StorageIntegrityError,match='unregistered operational write destination'):
        history._restore_pinned_v5_snapshot(scope,x.storage,bad,registered,authenticate=lambda _:True,at=history.now())
    assert foreign.read_bytes()==owned.read_bytes() and all(q.method=='GET' for q in x.calls)


def test_later_same_source_v5_history_keeps_original_default_reader(tmp_path_factory,tmp_path,monkeypatch):
    # No historical Owner capability is available; a same-source V5 read must
    # continue through the unchanged same-code/handoff/snapshot path.
    monkeypatch.setattr(profile,'validate_metadata',lambda *_:dict(mae_runtime_pin_profile=dict(changed_paths={})))
    seed=old.original_seed.__wrapped__(tmp_path_factory)
    helpers={n:store.sha(('FICTIONAL_SAME_SOURCE:'+n).encode()) for n in profile.HELPERS}
    slots=[dict(target=a,family=b,method_id=d,procedure_version='1'*64,model_sha256='2'*64,
        manifest_sha256='3'*64,transport_manifest_sha256='4'*64) for a,b,d in template.JOBS]
    static=dict(repository=store.REPO,mode=c.MODE,single_writer_group=c.GROUP,workflow_ref=seed['sidecar']['workflow_ref'],
        mae_helper_pins=helpers,mae_registration=dict(path=profile.REGISTRATION_PATH,bytes=512,sha256=helpers[profile.REGISTRATION_PATH]),
        retained_registration=dict(schema_version='audit-count-retained-v1-registration',approved=True,maximum_new_fits=0,
            public_release=False,origin=dict(replay_catalog=dict(slots=slots))))
    minted=old.locator_seed.__wrapped__(tmp_path/'same-source-writer',seed,monkeypatch,
        source_transition=True,closed_v5=True,root_static=static)
    x=old.locator_recovery_case(tmp_path/'same-source-reader',minted,monkeypatch)
    x.context.go['effective_epoch']['previous_capture']=deepcopy(minted['locator']['anchor'])
    assert x.context.proof is None and x.context.go['source_sha']==minted['sidecar']['source_sha']
    result=history.restore_previous(x.context,x.storage,x.sidecar,x.receipt,transport=x.api)
    assert grade._digest(result.durable.document)==minted['durable_sha256']
    assert result.durable.document['code_pins']==grade.pins()
    assert result.proof['original_grade_read_proof']==minted['sidecar']['grade_read_proof']
    assert all(q.method=='GET' for q in x.calls)
