"""Synthetic bounded metadata only; no native/GHA/source/model qualification.

Real admission/profile/template functions run. Source kits and typed bootstrap
seals are explicit fixture boundaries, never saved PASS or caller JSON grants.
"""
from copy import deepcopy
import base64
import gzip
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from nfl_lab import audit_weekly_grade_history_v1 as history
from nfl_lab import audit_weekly_template_v1 as template
from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
from nfl_lab import audit_weekly_controller_registration_v1 as registration
from nfl_lab import audit_weekly_controller_v1 as controller
from nfl_lab import audit_weekly_hosted_v1 as hosted
from nfl_lab import weekly_mae_display_profile_v1 as profile
from nfl_lab import private_draft_store as store
from test_audit_weekly_grade_history_v1 import parent_metadata,source_metadata
from test_audit_weekly_source_history_v2 import source_v2_metadata,_source_v2_root_check

SOURCE=Path(hosted.__file__).resolve().parents[1]
REVIEWED_MODULE_BYTES={"nfl_lab/"+m.__name__.rsplit('.',1)[1]+'.py':Path(m.__file__).read_bytes()
    for m in (history,template,bootstrap,registration,profile)}


def source_bytes(name):
    if name in REVIEWED_MODULE_BYTES:return REVIEWED_MODULE_BYTES[name]
    module=sys.modules.get('nfl_lab.'+Path(name).stem) if name.startswith('nfl_lab/') else None
    return Path(module.__file__).read_bytes() if module is not None else (SOURCE/name).read_bytes()


def reseal(x):
    """Fixture commitments only; preserves the exact literal predecessor body."""
    old=x.original;body=history._source_history_unwrap(x.current['source_history_binding'])
    root_sha=store.sha(store.canonical(old));x.receipt.update(root_go_sha256=root_sha,source_sha=old['source_sha'])
    x.locator['cohort'].update(root_go_sha256=root_sha,source_sha=old['source_sha'])
    x.locator['anchor']['receipt_sha256']=store.sha(gzip.compress(store.canonical(x.receipt),mtime=0))
    body['predecessor'].update(root_go_sha256=root_sha,root_static_sha256=template.static_root_sha256(old),
        code_pins_sha256=store.sha(store.canonical(old['code_pins'])),receipt_sha256=x.locator['anchor']['receipt_sha256'],
        locator=dict(path=history.locator_filename(x.locator),sha256=store.sha(gzip.compress(store.canonical(x.locator),mtime=0))))
    body['predecessor_root_schema']=old['schema_version']
    body['predecessor_source_history_sha256']=store.sha(store.canonical(old['source_history_binding']))
    body['pin_overrides']={p:old['code_pins'][p] for p,h in x.current['code_pins'].items() if h!=old['code_pins'][p]}
    x.current['source_history_binding']=history.source_history_envelope(body)
    x.current['prior_capture_qualified_runtime'].update(root_static_sha256=template.static_root_sha256(old),anchor=deepcopy(x.locator['anchor']))
    x.current['effective_epoch'].update(previous_capture=deepcopy(x.locator['anchor']),
        previous_checkpoint=dict(schema_version=history.LOCATOR_REF,**body['predecessor']['locator']))


@pytest.fixture
def v5_case(source_v2_metadata,tmp_path,monkeypatch,request):
    x=source_v2_metadata;x.legacy=deepcopy(x);kind=getattr(request,'param','v4')
    # Fictional predecessor/current Roots retain the same six real reviewed
    # model code identities. Only fixture commitments are resealed below.
    for name,digest in profile.REVIEWED_MODEL_PINS.items():
        x.original["code_pins"]["nfl_lab/"+name]=digest
        x.current["code_pins"]["nfl_lab/"+name]=digest
    inner=history._source_history_unwrap(x.original["source_history_binding"])
    prior_pins=dict(x.original["code_pins"]);prior_pins.update(inner["pin_overrides"])
    inner["predecessor"]["code_pins_sha256"]=store.sha(store.canonical(prior_pins))
    x.original["source_history_binding"]=history.source_history_envelope(inner)
    if kind=='v5':
        x.original['schema_version']=template.ROOT_V5
        x.original['mae_helper_pins']={p:store.sha(('FICTIONAL_OLD_HELPER:'+p).encode()) for p in profile.HELPERS}
        x.original['mae_registration']=dict(path=profile.REGISTRATION_PATH,bytes=512,
            sha256=x.original['mae_helper_pins'][profile.REGISTRATION_PATH])
        inner=history._source_history_unwrap(x.original['source_history_binding'])
        inner.update(schema_version=history.SOURCE_HISTORY_BINDING_V2,predecessor_root_schema=history.ROOT_V4,
            predecessor_source_history_sha256=store.sha(b'FICTIONAL_IMMEDIATE_INNER_COMMITMENT'))
        x.original['source_history_binding']=history.source_history_envelope(inner)
    x.current['schema_version']=template.ROOT_V5
    kit=tmp_path/'fictional-public-source';kit.mkdir()
    cfg=profile.strict_json((SOURCE/profile.REGISTRATION_PATH).read_bytes())
    for name in set(profile.HELPERS)|set(profile.CHANGED_LEGACY_PATHS):
        path=kit/name;path.parent.mkdir(parents=True,exist_ok=True)
        if name!=profile.REGISTRATION_PATH:path.write_bytes(source_bytes(name))
    for name in profile.CHANGED_LEGACY_PATHS:x.current['code_pins'][name]=profile.file_sha(kit/name)
    before=dict(x.current['code_pins'])
    changed={p:dict(before_sha256=x.original['code_pins'][p],after_sha256=x.current['code_pins'][p]) for p in profile.CHANGED_LEGACY_PATHS}
    for name,delta in changed.items():before[name]=delta['before_sha256']
    cfg['mae_runtime_pin_profile'].update(changed_paths=changed,
        reviewed_before_inventory_sha256=profile.sha(profile.canonical(before)),
        reviewed_after_inventory_sha256=profile.sha(profile.canonical(x.current['code_pins'])))
    raw=profile.canonical(cfg);(kit/profile.REGISTRATION_PATH).write_bytes(raw)
    x.current['mae_helper_pins']=profile.pins(kit)
    x.current['mae_registration']=dict(path=profile.REGISTRATION_PATH,bytes=len(raw),sha256=store.sha(raw))
    x.kit=kit;x.cfg=cfg
    # Explicit source-root fixture; validator code itself is never replaced.
    monkeypatch.setattr(history,'__file__',str(kit/'nfl_lab/audit_weekly_grade_history_v1.py'))
    monkeypatch.setattr(template,'__file__',str(kit/'nfl_lab/audit_weekly_template_v1.py'))
    reseal(x)
    assert profile.validate_root_extension(x.current,kit)==cfg
    return x


@pytest.mark.parametrize('v5_case',['v4','v5'],indirect=True)
def test_v4_v5_immediate_native_preimage_metadata_preserves_every_old_byte(v5_case):
    x=v5_case;before=store.canonical(x.original)
    assert _source_v2_root_check(x)['root_go'] is x.original
    assert _source_v2_root_check(x,static=True)['root_go'] is x.original
    assert store.canonical(x.original)==before


@pytest.mark.parametrize("path",["nfl_lab/audit_weekly_runtime_v1.py","tools/audit_weekly_runtime_v1.py",
    "tools/audit_weekly_archive_v1.py","nfl_lab/audit_weekly_delivery_v1.py"])
def test_runtime_override_requires_root_v5_and_exact_full_registered_profile(v5_case,path):
    x=v5_case
    assert path in profile.CHANGED_LEGACY_PATHS
    assert history.validate_source_history_binding(x.current)['pin_overrides'][path]==x.original['code_pins'][path]
    x.current['schema_version']=template.ROOT_V4
    del x.current['mae_registration'];del x.current['mae_helper_pins']
    with pytest.raises(history.HistoryError,match='ONLY_CHANGED_SOURCE_HISTORY_ORCHESTRATION_PIN_OVERRIDES'):
        history.validate_source_history_binding(x.current)


def test_root_v5_cannot_use_v1_history(v5_case):
    x=v5_case;body=history._source_history_unwrap(x.current['source_history_binding'])
    body['schema_version']=history.SOURCE_HISTORY_BINDING
    for name in ('predecessor_root_schema','predecessor_source_history_sha256'):del body[name]
    # Remove new-only overrides so rejection exercises the explicit V5 enum.
    body['pin_overrides']={p:h for p,h in body['pin_overrides'].items() if p not in history._MAE_RUNTIME_OVERRIDE_PATHS}
    x.current['source_history_binding']=history.source_history_envelope(body)
    with pytest.raises(history.HistoryError,match='MAE_ROOT_REQUIRES_EXPLICIT_V2'):
        history.validate_source_history_binding(x.current)


@pytest.mark.parametrize('damage',['runtime_before','missing_helper','registration_hash','model_pin','target_source','saved_pass'])
def test_current_profile_source_model_and_caller_json_changes_reject(v5_case,damage):
    x=v5_case;body=history._source_history_unwrap(x.current['source_history_binding'])
    if damage=='runtime_before':body['pin_overrides']['nfl_lab/audit_weekly_runtime_v1.py']='0'*64
    elif damage=='missing_helper':del x.current['mae_helper_pins'][profile.HELPERS[0]]
    elif damage=='registration_hash':x.current['mae_registration']['sha256']='0'*64
    elif damage=='model_pin':x.current['code_pins']['nfl_lab/weekly_future_inference.py']='0'*64
    elif damage=='target_source':x.current['source_sha']='0'*40
    else:x.current['source_history_binding']={'saved_PASS':True}
    if damage!='saved_pass':x.current['source_history_binding']=history.source_history_envelope(body)
    with pytest.raises((history.HistoryError,ValueError)):_source_v2_root_check(x)


@pytest.mark.parametrize('v5_case',['v5'],indirect=True)
def test_prior_v5_inner_is_structural_only_after_exact_preimage(v5_case,monkeypatch):
    x=v5_case;events=[];actual=profile.prior_extension_metadata
    def structural(root):
        assert store.sha(store.canonical(root))==history._source_history_unwrap(x.current['source_history_binding'])['predecessor']['root_go_sha256']
        events.append('authenticated-preimage');return actual(root)
    monkeypatch.setattr(profile,'prior_extension_metadata',structural)
    assert _source_v2_root_check(x)['root_go'] is x.original
    assert events==['authenticated-preimage']
    x.original['owner_authorization']='CALLER_REWRITE'
    events.clear()
    with pytest.raises(history.HistoryError):_source_v2_root_check(x)
    assert not events


@pytest.mark.parametrize('v5_case',['v5'],indirect=True)
def test_corrupt_inner_transport_rejects_even_when_outer_fixture_commitment_is_resealed(v5_case):
    x=v5_case;x.original['source_history_binding']['gzip_base64']='NOT_BASE64'
    reseal(x)
    with pytest.raises(history.HistoryError,match='INVALID_SOURCE_HISTORY_TRANSPORT'):_source_v2_root_check(x)


def test_parent_metadata_does_not_grant_producer_actual_byte_validation(v5_case):
    x=v5_case;path=x.kit/profile.HELPERS[0];path.write_bytes(b'FICTIONAL_CHANGED_PRODUCER_HELPER')
    assert profile.validate_metadata(x.current,x.kit)==x.cfg
    with pytest.raises(ValueError,match='EXACT_ACTUAL_PRODUCER_MAE_HELPER_BYTES'):
        profile.validate_root_extension(x.current,x.kit)


def static_document(x,parent_metadata):
    root=deepcopy(x.current);root.update(approved=False,repository=store.REPO,mode='audit-weekly-producer-v1',
        single_writer_group='nfl-lab-single-writer',workflow_ref=store.REPO+'/.github/workflows/lab.yml@refs/heads/fictional',
        retained_registration=dict(schema_version='audit-count-retained-v1-registration',approved=True,maximum_new_fits=0,
            public_release=False,origin=dict(replay_catalog=dict(slots=[dict(target=t,family=f,method_id=m,
                procedure_version='1'*64,model_sha256='2'*64,manifest_sha256='3'*64,transport_manifest_sha256='4'*64) for t,f,m in template.JOBS]))))
    for name in template.DYNAMIC_FIELDS-{'approved'}:root[name]=None
    policy=store.canonical(dict(fictional_public_policy=True))
    root['publication_registration'].update(policy_sha256=store.sha(policy),
        policy_gzip_base64=base64.b64encode(gzip.compress(policy,mtime=0)).decode())
    body=history._source_history_unwrap(root['source_history_binding'])
    body['target_policy_sha256']=root['publication_registration']['policy_sha256']
    root['source_history_binding']=history.source_history_envelope(body)
    receipt=parent_metadata['receipt']
    ready=dict(source_sha=root['source_sha'],branch='fictional',run_id=receipt['run_id'],workflow_sha256=root['code_pins'][controller.WORKFLOW],
        jobs=deepcopy(receipt['jobs']),receipt_sha256='a'*64,receipt_body_sha256='b'*64,
        receipt_bindings={k:receipt[k] for k in controller.RECEIPT_HASH_KEYS})
    return dict(schema_version=template.STATIC_V5,source_sha=root['source_sha'],code_pins=deepcopy(root['code_pins']),readiness=ready,root_template=root)


def fixture_seal(document,parent_pins):
    """Explicit trusted-native bootstrap boundary double; no API grant claim."""
    plain=store.canonical(document);descriptor=b'FICTIONAL_EXACT_DESCRIPTOR';binding=b'FICTIONAL_EXACT_BINDING'
    p=store.canonical(dict(parent=dict(code_pins=parent_pins),producer=dict(source_sha=document['source_sha'],code_pins=document['code_pins'])))
    d=dict(template_bytes=len(plain),template_sha256=store.sha(plain),private_descriptor_sha256=store.sha(descriptor),storage_binding_sha256=store.sha(binding))
    seal=bootstrap.Seal(p,d,{'fictional_native_boundary':True},SimpleNamespace(budget=lambda:None),bootstrap._KEY)
    return seal,plain,descriptor,binding


@pytest.mark.parametrize('wrong',[None,'missing','profile','registration'])
def test_actual_plain_parent_path_binds_two_independent_main_metadata_pins(v5_case,parent_metadata,wrong):
    x=v5_case;doc=static_document(x,parent_metadata)
    assert template.prepare(doc).document==doc
    pins={p:x.current['mae_helper_pins'][p] for p in bootstrap.PARENT_MAE_METADATA_PINS}
    if wrong=='missing':pins.clear()
    elif wrong=='profile':pins['nfl_lab/weekly_mae_display_profile_v1.py']='0'*64
    elif wrong=='registration':pins[profile.REGISTRATION_PATH]='0'*64
    args=fixture_seal(doc,pins)
    if wrong is None:assert bootstrap.verify_private_template(*args)==doc
    else:
        with pytest.raises(bootstrap.BootstrapError,match='EXACT_V5_PARENT_METADATA_SOURCE_COMMITMENTS'):
            bootstrap.verify_private_template(*args)
    with pytest.raises(bootstrap.BootstrapError,match='LIVE_BOOTSTRAP_REQUIRED'):
        bootstrap.verify_private_template({'saved_PASS':True},*args[1:])


def test_compressed_parent_path_keeps_metadata_only_template_validation(v5_case,parent_metadata,monkeypatch):
    x=v5_case;doc=static_document(x,parent_metadata);prepared=template.prepare(doc)
    pins={p:x.current['mae_helper_pins'][p] for p in bootstrap.PARENT_MAE_METADATA_PINS}
    seal,*_=fixture_seal(doc,pins)
    loc=dict(template_seal=dict(template_sha256=store.sha(prepared.plain),template_bytes=len(prepared.plain),
        descriptor=dict(entry=dict(payload=dict(bytes=len(prepared.body),sha256=store.sha(prepared.body))))))
    # The external native locator authentication is an explicit fixture seam.
    monkeypatch.setattr(bootstrap.Seal,'locators',property(lambda _:loc))
    assert bootstrap.verify_template_payload(seal,prepared.body).document==doc


@pytest.mark.parametrize('damage',[None,'missing','profile','registration'])
def test_v5_registration_binds_parent_metadata_before_any_private_create(v5_case,damage):
    root=deepcopy(v5_case.current)
    parent_pins={p:root['code_pins'][p] for p in bootstrap.PARENT_EXECUTABLE_PINS}
    parent_pins.update({p:root['mae_helper_pins'][p] for p in bootstrap.PARENT_MAE_METADATA_PINS})
    if damage=='missing':del parent_pins[profile.REGISTRATION_PATH]
    elif damage=='profile':parent_pins['nfl_lab/weekly_mae_display_profile_v1.py']='0'*64
    elif damage=='registration':parent_pins[profile.REGISTRATION_PATH]='0'*64
    root['effective_epoch']=dict(schema_version=registration.HISTORY_CONTEXT_SCHEMA,parent_source_sha='a'*40,
        parent_code_pins=parent_pins,previous_capture=deepcopy(v5_case.locator['anchor']),history_protocol=history.LOCATOR_VERSION)
    if damage is None:
        parent,producer=registration._source_specs(root)
        assert parent['source_sha']!=producer['source_sha']
        assert len(producer['code_pins'])==128
        assert all(parent['code_pins'][p]==root['mae_helper_pins'][p] for p in bootstrap.PARENT_MAE_METADATA_PINS)
    else:
        with pytest.raises(registration.RegistrationError,match='EXACT_V5_PARENT_METADATA_PINS_BEFORE_PRIVATE_CREATE'):
            registration._source_specs(root)


@pytest.mark.parametrize('mae',[False,True])
def test_cold_main_packages_preserve_v4_and_add_only_two_v5_metadata_dependencies(source_v2_metadata,v5_case,parent_metadata,tmp_path,mae):
    x=v5_case if mae else v5_case.legacy
    main=tmp_path/'cold-main';names=bootstrap.PARENT_EXECUTABLE_MAE_PINS if mae else bootstrap.PARENT_EXECUTABLE_PINS
    assert bootstrap.PARENT_EXECUTABLE_MAE_PINS-bootstrap.PARENT_EXECUTABLE_PINS==bootstrap.PARENT_MAE_METADATA_PINS
    for name in set(names)|{'nfl_lab/__init__.py'}:
        dest=main/name;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((x.kit/name).read_bytes() if mae and name in bootstrap.PARENT_MAE_METADATA_PINS else source_bytes(name))
    assert not (main/'nfl_lab/audit_weekly_runtime_v1.py').exists()
    assert (main/'nfl_lab/weekly_mae_display_profile_v1.py').exists() is mae
    data=dict(current=x.current,original=x.original,locator=x.locator,jobs=x.jobs,at=x.at)
    if mae:data['document']=static_document(x,parent_metadata)
    script='''import sys,json,importlib.abc,socket
sys.path.insert(0,sys.argv[1])
class DenyProducer(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'numpy','scipy','pandas','sklearn','catboost','joblib'} or name in {'nfl_lab.audit_weekly_runtime_v1','nfl_lab.weekly_mae_display_runtime_v1','nfl_lab.weekly_mae_point_inference_v2_1','nfl_lab.audit_weekly_grade_v1','nfl_lab.audit_private_rotation_v1'}:raise AssertionError('PRODUCER_IMPORT_FORBIDDEN:'+name)
sys.meta_path.insert(0,DenyProducer())
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN'))
from nfl_lab import audit_weekly_grade_history_v1 as h,audit_weekly_template_v1 as t
x=json.load(sys.stdin);binding=h.validate_source_history_binding(x['current'])
h._root_envelope(dict(root_go=x['original'],planning=x['locator']['planning']),x['locator'],x['jobs'],code_pins=x['original']['code_pins'],static_root=x['current'],at=x['at'],locator_sha256=binding['predecessor']['locator']['sha256'])
if 'document' in x:t.prepare(x['document'])
else:assert 'nfl_lab.weekly_mae_display_profile_v1' not in sys.modules
print('COLD_MAIN_METADATA_OK')
'''
    result=subprocess.run([sys.executable,'-I','-B','-c',script,str(main)],input=json.dumps(data),text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='COLD_MAIN_METADATA_OK'


SEVEN_V5_CANDIDATES=frozenset({"nfl_lab/audit_weekly_retained_v1.py","nfl_lab/audit_weekly_controller_v1.py",
    "nfl_lab/audit_weekly_runtime_v1.py","tools/audit_weekly_runtime_v1.py",
    "tools/audit_weekly_archive_v1.py","nfl_lab/audit_weekly_delivery_v1.py","tools/persist_state.py"})


def test_v5_candidate_set_is_exact_and_v1_v4_whitelist_does_not_grow():
    assert history._MAE_RUNTIME_OVERRIDE_PATHS==SEVEN_V5_CANDIDATES
    assert not (SEVEN_V5_CANDIDATES & history.SOURCE_HISTORY_PIN_OVERRIDES)
    assert 'nfl_lab/weekly_future_inference.py' not in history.SOURCE_HISTORY_PIN_OVERRIDES


@pytest.mark.parametrize('path',sorted(SEVEN_V5_CANDIDATES-{'tools/persist_state.py'}))
def test_each_present_v5_override_requires_exact_registered_before_hash(v5_case,path):
    x=v5_case;body=history._source_history_unwrap(x.current['source_history_binding'])
    body['pin_overrides'][path]='0'*64
    x.current['source_history_binding']=history.source_history_envelope(body)
    with pytest.raises(history.HistoryError,match='EXACT_MAE_ONLY_PREDECESSOR_RUNTIME_PIN_OVERRIDE'):
        history.validate_source_history_binding(x.current)


def test_persist_state_cannot_be_invented_inside_original128(v5_case):
    x=v5_case;path='tools/persist_state.py'
    assert path not in x.current['code_pins'] and path not in x.original['code_pins']
    assert path not in profile.CHANGED_LEGACY_PATHS
    body=history._source_history_unwrap(x.current['source_history_binding'])
    body['pin_overrides'][path]=store.sha(b'CALLER_INVENTED_LEGACY_PERSIST_STATE')
    x.current['source_history_binding']=history.source_history_envelope(body)
    with pytest.raises(history.HistoryError):history.validate_source_history_binding(x.current)
    x.current['code_pins'][path]=body['pin_overrides'][path]
    with pytest.raises((history.HistoryError,ValueError)):history.validate_source_history_binding(x.current)


def rewrite_fixture_profile(x):
    """Explicit source metadata fixture; never an owner/native grant."""
    cfg=deepcopy(x.cfg);before=dict(x.current['code_pins'])
    for name,delta in cfg['mae_runtime_pin_profile']['changed_paths'].items():before[name]=delta['before_sha256']
    cfg['mae_runtime_pin_profile'].update(reviewed_before_inventory_sha256=profile.sha(profile.canonical(before)),
        reviewed_after_inventory_sha256=profile.sha(profile.canonical(x.current['code_pins'])))
    raw=profile.canonical(cfg);(x.kit/profile.REGISTRATION_PATH).write_bytes(raw)
    x.current['mae_helper_pins'][profile.REGISTRATION_PATH]=store.sha(raw)
    x.current['mae_registration'].update(bytes=len(raw),sha256=store.sha(raw));x.cfg=cfg


@pytest.mark.parametrize('name',sorted(profile.REVIEWED_MODEL_PINS))
def test_all_six_model_root_pins_reject_even_if_source_profile_is_consistently_rebound(v5_case,name):
    x=v5_case;x.current['code_pins']['nfl_lab/'+name]='0'*64
    rewrite_fixture_profile(x)
    # Parent can check sealed source metadata without a Producer import, but
    # that metadata path never grants numerical/model execution authority.
    assert profile.validate_metadata(x.current,x.kit)==x.cfg
    with pytest.raises(ValueError,match='EXACT_ORIGINAL_SIX_MODEL_CODE_ROOT_PINS'):
        profile.validate_root_extension(x.current,x.kit)


def test_undeclared_source_path_cannot_gain_v5_override_authority(v5_case):
    body=history._source_history_unwrap(v5_case.current['source_history_binding'])
    body['pin_overrides']['nfl_lab/weekly_current_query.py']='0'*64
    with pytest.raises(history.HistoryError,match='ONLY_SOURCE_HISTORY_ORCHESTRATION_PIN_OVERRIDES'):
        history.source_history_envelope(body)
