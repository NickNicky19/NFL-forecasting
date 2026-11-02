"""Actual installed Runtime/CLI with explicit numerical/native API mocks.

All data/artifacts are fictional. Real owned storage, query/receipt handling,
legacy assembly and installed MAE hooks execute. No real fitted model, provider,
native qualification or actual source/model admission is claimed.
"""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from nfl_lab import weekly_mae_point_inference_v2_1 as point
from nfl_lab import stat_point_mae_public_v2_2 as public
from nfl_lab import weekly_mae_display_profile_v1 as display_profile
from nfl_lab import weekly_mae_display_runtime_v1 as display
from nfl_lab import audit_weekly_runtime_v1 as original,weekly_future_inference as future
from nfl_lab import audit_weekly_hosted_v1 as hosted
from tools import audit_weekly_runtime_v1 as cli
import test_audit_weekly_runtime_v1 as legacy_tests
from test_audit_weekly_runtime_v1 import packet,staged

SOURCE=Path(original.__file__).resolve().parents[1]

# Metadata-only projection of the authenticated retained transport manifests
# 6b45a765..., 33a4f1aa..., 1d2eaf28.... No private locator, model payload,
# player or outcome record is included. These expected values are independent
# of the source registration. The research package used different originals.
RETAINED_CORE3_PROVENANCE = {
    'pass_yd': {
        'training_frame_sha256':'d6021e7d506461715c46e9bcbda424cf3dc90cead95beadde5fdfe04076db9bb',
        'original_manifest_sha256':'437706f085f8c2f92e8eedbf45c79203eca69b3edd02d400c82b23927e5ff43e',
        'original_model_sha256':'6c477157cfec0caadfcd2ff90acb919593d3ed67ef5ff1103001c25b4e431c3e'},
    'pass_int': {
        'training_frame_sha256':'d6021e7d506461715c46e9bcbda424cf3dc90cead95beadde5fdfe04076db9bb',
        'original_manifest_sha256':'990dd4ff3fdc990590119d73c80e1471ad1ea690ab5cff7bd3b2fbca8b30dbfa',
        'original_model_sha256':'8a492f6609b1887619e8237346730dbff8848370b634303a51c0d099c78bb4d6'},
    'rush_rec_yd': {
        'training_frame_sha256':'d6021e7d506461715c46e9bcbda424cf3dc90cead95beadde5fdfe04076db9bb',
        'original_manifest_sha256':'438a9c6de5f16914e127f7d1d168f1f1777dc0cffc7c622f10589392ba51a455',
        'original_model_sha256':'8ae6a335b3a37a4d120d1ecb396b97824921b450d2d4dd3e9951a484306bd7e1'},
}
RESEARCH_CORE3_PROVENANCE = {
    'pass_yd': {
        'training_frame_sha256':'467e9bf5475425de26aa48e4289c22116dba8585ee7ee236c499b57cd13c560e',
        'original_manifest_sha256':'14c3da8aff3a8f2a958f75d45cdcd4cc99d28ea4fd82a3d1eeb272a206352bdd',
        'original_model_sha256':'dffd0a2f82dd8f542177f666c0dc9f4a1c15942e885fd82eb25b6b1ee6b8a0b4'},
    'pass_int': {
        'training_frame_sha256':'467e9bf5475425de26aa48e4289c22116dba8585ee7ee236c499b57cd13c560e',
        'original_manifest_sha256':'49e02be68349b82302f53a6bea2352fbceaa4429b74f2ecdef1a374108e226cd',
        'original_model_sha256':'3d8436e467c77531a7928eb788caba2231d82b518517453b53cc13e99f4bae47'},
    'rush_rec_yd': {
        'training_frame_sha256':'467e9bf5475425de26aa48e4289c22116dba8585ee7ee236c499b57cd13c560e',
        'original_manifest_sha256':'220fc5c49c037caa55dd593dd005bc74c63427f17bd39d36848a90d5174b4062',
        'original_model_sha256':'14d9781edf4d54b7bd668e75e0c790cae018b182b52f75e420128da88ac13459'},
}


@pytest.fixture(autouse=True)
def synthetic_numerical_readiness(monkeypatch):
    # Explicit environment/BLAS readiness boundary double; actual Runtime is
    # never replaced and this suite does not claim numerical runtime readiness.
    monkeypatch.setattr(original.numerical,'loaded',lambda *_:None)


def install_display(p,monkeypatch,*,retained_provenance=None,registration_overrides=None):
    cfg=public.strict_json((SOURCE/display.REGISTRATION_PATH).read_bytes())
    # Explicit synthetic restored-catalog metadata. Current files are opaque test
    # artifacts from the original fixture; no real fitted object is decoded.
    for c in cfg['categories']:
        if registration_overrides is not None:
            c.update(registration_overrides.get(c['target'],{}))
        provenance=c if retained_provenance is None else retained_provenance[c['target']]
        record=next(r for r in p.runtime.records if r['manifest']['category']['target']==c['target'] and r['manifest']['method_id']=='LAB_CDF')
        m=record['manifest']
        # The existing legacy fixture intentionally uses fictional opaque
        # artifact identities. Bind the synthetic registered source to those
        # identities instead of claiming they are the actual retained core.
        slot=next(s for s in p.runtime.replay['slots'] if s['target']==c['target'] and s['method_id']=='LAB_CDF')
        origin=next(s for s in p.runtime.restored['origin']['replay_catalog']['slots'] if s['target']==c['target'] and s['method_id']=='LAB_CDF')
        c.update(effective_model_sha256=slot['model_sha256'],effective_base_procedure_version=slot['procedure_version'],
            effective_transport_manifest_sha256=slot['transport_manifest_sha256'],effective_verified_reader_manifest_sha256=origin['manifest_sha256'])
        m.update(code_pins=point.REVIEWED_MODEL_PINS,features=c['features'],training_frame_sha256=provenance['training_frame_sha256'],
            training_cutoff_utc=c['training_cutoff_utc'],training_max_available_utc=c['training_max_available_utc'],
            requalification=dict(original_manifest={'sha256':provenance['original_manifest_sha256']},
                original_model={'sha256':provenance['original_model_sha256']},original_procedure_version=c['original_procedure_version'],
                fits=0,parameters_retrained=False,original_replay_preserved=True))
        m['category'].update(modeled_roles=c['modeled_roles'],primary_roles=c['public_roles'])
        p.manifests[record['binding']['sha256']].update(deepcopy(m))
    feature_builder=future.build_future_features
    def features(*args,**kwargs):
        result=feature_builder(*args,**kwargs)
        for c in cfg['categories']:
            for name in c['features']:
                if name not in result:result[name]=0.
        return result
    monkeypatch.setattr(future,'build_future_features',features)
    # Use the complete installed 128-pin inventory and finalized profile.
    # Only category artifact identities are fictionalized above; no source
    # profile path/hash inventory or validator result is synthesized.
    inventory=hosted.pins()
    assert len(inventory)==128
    assert set(inventory)==set(hosted.PINS)
    assert all(future.sha(SOURCE/'nfl_lab'/name)==digest for name,digest in point.REVIEWED_MODEL_PINS.items())
    kit=p.root/'synthetic-public-source'
    for name in sorted(set(hosted.PINS)|set(display.HELPERS)):
        dest=kit/name;dest.parent.mkdir(parents=True,exist_ok=True)
        source=SOURCE/name
        dest.write_bytes(display.private.canonical(cfg) if name==display.REGISTRATION_PATH else source.read_bytes())
    now=p.clock();root=dict(schema_version=display.ROOT_V5,source_sha='b'*40,source_config=p.runtime.config,
        code_pins=inventory,issued_at_utc=now.isoformat(),expires_at_utc=(now+timedelta(hours=1)).isoformat(),
        mae_helper_pins=display.pins(kit),mae_registration=dict(path=display.REGISTRATION_PATH,
            bytes=(kit/display.REGISTRATION_PATH).stat().st_size,sha256=future.sha(kit/display.REGISTRATION_PATH)))
    assert display_profile.validate_root_extension(root,kit)==cfg
    root_bytes=display.private.canonical(root);proof=object()
    def live_proof(actual,env,body):
        assert actual is proof and body==root_bytes  # Explicit external live-API boundary mock.
    monkeypatch.setattr(display.operations,'_verify',live_proof)
    monkeypatch.setattr(display.runtime,'now_utc',p.clock)
    owner=display.checked_context(dict(owner_root_go_sha256=display.private.sha(root_bytes),source_sha='b'*40),
        root_bytes,proof,{},kit)
    p.runtime._mae=display.BoundDisplay(p.runtime,owner)
    calls=[]
    def bind(session,doc,*,verify_owner_admission):
        assert getattr(verify_owner_admission,'__self__',None) is p.runtime._mae
        verify_owner_admission(point._canonical(doc),dict(phase='PROFILE',artifact=doc['artifact']))
        return deepcopy(doc)
    def predict(session,doc,frame,*,context,source_receipt,batch_size,clock):
        # Exercise unchanged legacy source/fit/query/clock checks on this new
        # call. Its numerical values are the original fixture's explicit mock.
        qsha=future.frame_digest(frame)
        source=original.read_owned(p.storage,source_receipt)
        p.runtime._mae._verify_profile(point._canonical(doc),dict(phase='CURRENT_SNAPSHOT',
            point_profile_sha256=point._digest(doc),source_receipt=source_receipt,
            feature_capture_receipt=context['feature_capture_receipt'],query_projection_sha256=qsha,
            information_cutoff_utc=original.utc(source['asof_utc']).isoformat()))
        calls.append(doc['target'])
        for chunk in session.predict_chunks(doc['artifact']['sha256'],frame,context=context,batch_size=batch_size,clock=clock):
            rows=[]
            for old in chunk:
                candidate=dict(old,target=doc['target'],scoring_target=doc['target'],selection_product='stat_point_mae_v2',
                    selection_metric='MAE',forecast_product='point_median',prediction_functional='full_cdf_lower_median',
                    issue_deadline_utc=old['cutoff_utc'],information_cutoff_utc=source['asof_utc'],
                    point_profile_sha256=point._digest(doc),original_forecast=deepcopy(old),
                    test_evidence='FICTIONAL_NUMERICAL_DOUBLE_NOT_A_REAL_LAW')
                candidate['candidate_sha256']=point._digest(candidate);rows.append(candidate)
            yield rows
    monkeypatch.setattr(display.point,'bind_profile',bind)
    monkeypatch.setattr(display.point,'predict_point_chunks',predict)
    return owner,calls


def test_actual_legacy_prepare_source_capture_infer_adds_display_sibling_only(packet,monkeypatch):
    p=packet;owner,calls=install_display(p,monkeypatch)
    prepared,source,_=staged(p)
    before=original.read_owned(p.storage,prepared)
    catalog=original.read_owned(p.storage,future.binding(Path(prepared['path']).parent/'mae-display/PROFILE_CATALOG.json'))
    assert catalog['prepared']==prepared and catalog['current_values_used'] is False
    observed=[];method=display.BoundDisplay.capture
    def checked(self,*args):
        output=args[9]  # each optional category now creates its own session.
        assert (Path(output)/'FINISHED.json').is_file()
        assert (Path(output)/'EXPORT_INPUTS.json').is_file()
        files=[x for x in Path(output).rglob('*') if x.is_file() and
            (x.name.endswith('.jsonl.gz') or x.name.endswith('.completion.json'))]
        snapshot={str(x):future.sha(x) for x in files}
        result=method(self,*args)
        assert all(future.sha(name)==value for name,value in snapshot.items())
        observed.append(len(snapshot))
        return result
    monkeypatch.setattr(display.BoundDisplay,'capture',checked)
    terminal_ref=p.runtime.infer(prepared,source,p.root/'runtime')
    result=original.read_owned(p.storage,terminal_ref)
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'
    assert result['model_pairs']==18 and set(calls)==set(display.TARGETS)
    assert observed and observed[0]>=38  #18candidate + selected bodies and completion receipts.
    side=original.read_owned(p.storage,future.binding(p.root/'runtime/mae-display/FINISHED.json'))
    assert side['state']=='PRIVATE_DISPLAY_CAPTURE_COMPLETE'
    assert [s['target'] for s in side['statuses']]==list(display.TARGETS)
    assert side['legacy_selected']==result['selected'] and side['extra_traversal_rows_reserved']==2*3*result['query_rows']
    assert side['legacy_prediction_rows']+side['extra_traversal_rows_reserved']<=original.LIMITS['prediction_rows']
    plan=p.runtime._mae.archive_file_debit
    assert len(plan['exact_new_aliases'])==plan['projection_descriptors']+14
    assert plan['fixed_runtime_aliases']==12 and plan['prepared_catalog_aliases']==2
    assert plan['known_local_plus_new_files']<=512
    rows=legacy_tests.rows(result['selected']['binding'])
    assert rows and all(r['method_id']=='P2_SELECTED' for r in rows)
    assert all('MAE_DISPLAY' not in json.dumps(r) for r in rows)
    wrapped=legacy_tests.rows(side['statuses'][0]['persistence']['binding'])
    assert wrapped and wrapped[0]['candidate_sha256']==wrapped[0]['candidate']['candidate_sha256']
    assert wrapped[0]['public_identity']['website_game_id']!=wrapped[0]['candidate']['game_id']


def test_mae_category_failure_preserves_known_siblings_and_legacy_selected(packet,monkeypatch):
    p=packet;install_display(p,monkeypatch);prepared,source,_=staged(p)
    original_predict=display.point.predict_point_chunks
    def fail_int(session,doc,*args,**kwargs):
        if doc['target']=='pass_int':raise ValueError('FICTIONAL_INT_SLOT_FAILED')
        yield from original_predict(session,doc,*args,**kwargs)
    monkeypatch.setattr(display.point,'predict_point_chunks',fail_int)
    result=original.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'runtime'))
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'
    side=original.read_owned(p.storage,future.binding(p.root/'runtime/mae-display/FINISHED.json'))
    assert side['state']=='PARTIAL_DISPLAY_CAPTURE_RETAINED'
    assert [s['state'] for s in side['statuses']]==['CAPTURED','FAILED_RETAINED','CAPTURED']
    assert result['selected']['state']=='PERSISTED'


def test_display_output_capacity_failure_keeps_original_legacy_control_reserve(packet,monkeypatch):
    p=packet;install_display(p,monkeypatch);prepared,source,_=staged(p)
    # Synthetic exhausted optional data allocation; terminal controls continue
    # within the original namespace/global ceiling, without changing a cap.
    monkeypatch.setattr(display.DisplaySink,'CONTROL_LIMIT',original.LIMITS['new_bytes'])
    result=original.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'runtime'))
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'
    assert result['selected']['state']=='PERSISTED'
    side=original.read_owned(p.storage,future.binding(p.root/'runtime/mae-display/FINISHED.json'))
    assert side['state']=='FAILED_DISPLAY_CAPTURE_RETAINED'
    assert side['reason']=='DISPLAY_PRESERVES_LEGACY_OUTPUT_RESERVE'
    assert (p.root/'runtime/EXPORT_INPUTS.json').is_file()


def test_actual_config_lineage_mismatch_is_rejected_before_private_source_values(packet,monkeypatch):
    p=packet;owner,_=install_display(p,monkeypatch)
    r=next(r for r in p.runtime.records if r['manifest']['category']['target']=='pass_int' and r['manifest']['method_id']=='LAB_CDF')
    r['manifest']['requalification']['original_model']['sha256']='0'*64
    with pytest.raises(original.RuntimeErrorCode,match='ACTUAL_CORE_EFFECTIVE_ORIGINAL_MAPPING'):
        display.BoundDisplay(p.runtime,owner)
    assert p.loads==[] and p.feature_calls==[] and p.requests==[]


def test_retained_core3_provenance_passes_actual_guard_without_loading_models(packet,monkeypatch):
    p=packet;owner,_=install_display(p,monkeypatch,retained_provenance=RETAINED_CORE3_PROVENANCE)
    # The existing fixture uses fictional effective weights and a synthetic
    # live native/API proof. Its full source-kit hash/profile checks and the
    # real BoundDisplay guard run; no actual native/model admission is claimed.
    assert type(owner) is display.NativeContext
    assert set(p.runtime._mae.profiles)==set(RETAINED_CORE3_PROVENANCE)
    for c in owner.config['categories']:
        expected=RETAINED_CORE3_PROVENANCE[c['target']]
        assert {k:c[k] for k in expected}==expected
    assert p.loads==[] and p.feature_calls==[] and p.requests==[]


def test_mixed_research_originals_fail_actual_retained_guard(packet,monkeypatch):
    p=packet
    with pytest.raises(original.RuntimeErrorCode,match='^ACTUAL_CORE_EFFECTIVE_ORIGINAL_MAPPING_REQUIRED$'):
        install_display(p,monkeypatch,retained_provenance=RETAINED_CORE3_PROVENANCE,
            registration_overrides=RESEARCH_CORE3_PROVENANCE)
    assert p.loads==[] and p.feature_calls==[] and p.requests==[]


@pytest.mark.parametrize('target,field',[(t,k) for t,v in RETAINED_CORE3_PROVENANCE.items() for k in v])
def test_each_research_identity_reversion_fails_actual_guard(packet,monkeypatch,target,field):
    p=packet;overrides={target:{field:RESEARCH_CORE3_PROVENANCE[target][field]}}
    with pytest.raises(original.RuntimeErrorCode,match='^ACTUAL_CORE_EFFECTIVE_ORIGINAL_MAPPING_REQUIRED$'):
        install_display(p,monkeypatch,retained_provenance=RETAINED_CORE3_PROVENANCE,
            registration_overrides=overrides)
    assert p.loads==[] and p.feature_calls==[] and p.requests==[]


@pytest.mark.parametrize('target',tuple(RETAINED_CORE3_PROVENANCE))
@pytest.mark.parametrize('binding',('effective_weights','effective_procedure','verified_origin','transport'))
def test_retained_identity_correction_preserves_effective_binding_rejections(packet,monkeypatch,target,binding):
    p=packet;owner,_=install_display(p,monkeypatch,retained_provenance=RETAINED_CORE3_PROVENANCE)
    record=next(r for r in p.runtime.records if r['manifest']['category']['target']==target and r['manifest']['method_id']=='LAB_CDF')
    slot=next(s for s in p.runtime.replay['slots'] if s['target']==target and s['method_id']=='LAB_CDF')
    origin=next(s for s in p.runtime.restored['origin']['replay_catalog']['slots'] if s['target']==target and s['method_id']=='LAB_CDF')
    if binding=='effective_weights':record['manifest']['model']['sha256']='0'*64
    elif binding=='effective_procedure':record['manifest']['procedure_version']='0'*64
    elif binding=='verified_origin':origin['manifest_sha256']='0'*64
    else:slot['transport_manifest_sha256']='0'*64
    with pytest.raises(original.RuntimeErrorCode,match='^ACTUAL_CORE_EFFECTIVE_ORIGINAL_MAPPING_REQUIRED$'):
        display.BoundDisplay(p.runtime,owner)
    assert p.loads==[] and p.feature_calls==[] and p.requests==[]


def test_default_has_no_display_sidecar(packet):
    p=packet;assert p.runtime._mae is None
    prepared,source,_=staged(p)
    result=original.read_owned(p.storage,p.runtime.infer(prepared,source,p.root/'runtime'))
    assert result['state']=='PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'
    assert not (p.root/'runtime/mae-display').exists()


def test_exact_new_projection_count_stops_before_point_traversal_if_slots_cannot_fit(tmp_path):
    import pandas as pd
    # Only fictional cutoff metadata is needed to count the new descriptor
    # cohort; no model law, source values, file bodies or native grant is used.
    frame=pd.DataFrame(dict(cutoff_utc=pd.date_range('2099-01-01',periods=600,tz='UTC'),position=['QB']*600))
    records=[dict(manifest=dict(features=['f_'+t]),eligible_roles=['QB']) for t in display.TARGETS]
    with pytest.raises(original.RuntimeErrorCode,match='MAE_DESCRIPTOR_ARCHIVE_FILE_ALLOCATION_EXHAUSTED'):
        display.archive_file_debit(frame,records,tmp_path)
    frame=frame.iloc[:7]
    plan=display.archive_file_debit(frame,records,tmp_path)
    assert plan['projection_descriptors']==21 and len(plan['exact_new_aliases'])==35
    assert plan['later_R0_and_context_count']=='UNKNOWN_FINAL_FULL_ARCHIVE_CENSUS_STILL_REQUIRED'


def test_closed_v2_cli_request_is_native_bound_and_old_request_stays_strict(packet,monkeypatch):
    p=packet;owner,_=install_display(p,monkeypatch)
    monkeypatch.setattr(cli,'context',lambda *_:owner)
    def invoke(request):
        body=display.private.canonical(request);path=p.root/'synthetic-request.json'
        path.write_bytes(body)
        return cli.execute(SimpleNamespace(phase='prepare',request=path,request_sha256=display.private.sha(body)),{})
    old=cli.template();old['approved']=True
    v2=dict(old,schema_version=display.REQUEST_V2,mae_registration=owner.registration_ref)
    # A valid typed request passes the new gate and reaches the unchanged next
    # startup-environment gate, before any private model/source/epoch read.
    with pytest.raises(original.RuntimeErrorCode,match='EXACT_NUMERICAL_STARTUP_ENVIRONMENT'):
        invoke(v2)
    with pytest.raises(original.RuntimeErrorCode,match='SAME_NATIVE_ROOT_MAE_REGISTRATION'):
        invoke(old)
    with pytest.raises(original.RuntimeErrorCode,match='SEALED_EXACT_RUNTIME_REQUEST'):
        invoke(dict(v2,caller_verifier=True))
    monkeypatch.setattr(cli,'context',lambda *_:{'synthetic_legacy_authority':True})
    with pytest.raises(original.RuntimeErrorCode,match='SEALED_EXACT_RUNTIME_REQUEST'):
        invoke(v2)
    with pytest.raises(original.RuntimeErrorCode,match='EXACT_NUMERICAL_STARTUP_ENVIRONMENT'):
        invoke(old)
    assert p.loads==[] and p.feature_calls==[] and p.requests==[]


def test_root_v5_profile_is_metadata_only_and_source_pin_delta_is_closed(packet,monkeypatch):
    p=packet;owner,_=install_display(p,monkeypatch)
    script=r'''
import importlib.abc,json,sys
class BlockModels(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'numpy','pandas','scipy','sklearn','catboost','joblib'} or (name.startswith('nfl_lab.') and name!='nfl_lab.weekly_mae_display_profile_v1'):
   raise AssertionError('MODEL_IMPORT_BLOCKED:'+name)
sys.meta_path.insert(0,BlockModels());sys.path.insert(0,sys.argv[1])
from nfl_lab import weekly_mae_display_profile_v1 as metadata
root=json.load(sys.stdin);cfg=metadata.validate_root_extension(root,sys.argv[2])
assert cfg['targets']==['pass_yd','pass_int','rush_rec_yd']
assert len(root['code_pins'])==128 and set(root['mae_helper_pins'])==set(metadata.HELPERS)
assert not any(k.split('.')[0] in {'numpy','pandas','scipy','sklearn','catboost','joblib'} for k in sys.modules)
assert {k for k in sys.modules if k=='nfl_lab' or k.startswith('nfl_lab.')} == {'nfl_lab','nfl_lab.weekly_mae_display_profile_v1'}
print('stdlib-only exact source/profile closure')
'''
    result=subprocess.run([sys.executable,'-I','-S','-B','-c',script,str(SOURCE),str(owner.source_root)],
        input=owner.root_bytes.decode(),text=True,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
    wrong=deepcopy(owner.root);wrong['code_pins']['nfl_lab/weekly_future_inference.py']='0'*64
    with pytest.raises(ValueError,match='EXACT_ORIGINAL_SIX_MODEL_CODE_ROOT_PINS'):
        display_profile.validate_root_extension(wrong,owner.source_root)
    assert p.loads==[] and p.feature_calls==[] and p.requests==[]


def test_provider_period_source_change_is_exact_v5_only():
    from hashlib import sha256
    from nfl_lab import audit_weekly_grade_history_v1 as history
    name="nfl_lab/audit_weekly_provider_v1.py"
    cfg=json.loads((SOURCE/display_profile.REGISTRATION_PATH).read_bytes())
    root=dict(schema_version=display_profile.ROOT_V5,code_pins=hosted.pins(),
        mae_helper_pins=display_profile.pins(SOURCE),mae_registration=dict(
            path=display_profile.REGISTRATION_PATH,bytes=(SOURCE/display_profile.REGISTRATION_PATH).stat().st_size,
            sha256=sha256((SOURCE/display_profile.REGISTRATION_PATH).read_bytes()).hexdigest()))
    display_profile.validate_root_extension(root,SOURCE)
    delta=cfg["mae_runtime_pin_profile"]["changed_paths"][name]
    assert delta["before_sha256"] == "ffbe666b1838998282286ad68640255962f2c047c800b64f9f476a161a3b900b"
    assert delta["after_sha256"] == sha256((SOURCE/name).read_bytes()).hexdigest()
    assert name in history._MAE_RUNTIME_OVERRIDE_PATHS
    assert name not in history.SOURCE_HISTORY_PIN_OVERRIDES
    legacy=dict(schema_version=history.ROOT_V4,code_pins={name:delta["after_sha256"]})
    with pytest.raises(history.HistoryError,match="ONLY_CHANGED_SOURCE_HISTORY_ORCHESTRATION_PIN_OVERRIDES"):
        history._source_history_pins(legacy,dict(pin_overrides={name:delta["before_sha256"]}))
    wrong=deepcopy(root);wrong["code_pins"][name]="0"*64
    with pytest.raises(ValueError,match="CLOSED_MAE_ONLY_RUNTIME_PIN_PROFILE"):
        display_profile.validate_root_extension(wrong,SOURCE)


def local_infer_context(packet, monkeypatch, *, before_mint=None, actor='owner'):
    """Real Owner/Seal/Metadata predicates; synthetic native inputs/counters.

    The retained runtime fixture still mocks numerical objects and remote API
    authentication. This fixture does NOT replace operations._verify: it tests
    the actual resource/integrity boundary that those old mocks could not see.
    """
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    real_verify = display.operations._verify
    old, _ = install_display(packet, monkeypatch)
    monkeypatch.setattr(display.operations, '_verify', real_verify)
    state = dict(wall=0., cpu=0., rss=128 << 20, timer=420.,
        cpu_limit=(300,300), as_limit=(4 << 30,4 << 30), handler=display.signal.SIG_DFL)
    monkeypatch.setattr(bootstrap.time, 'monotonic', lambda: state['wall'])
    monkeypatch.setattr(bootstrap.time, 'process_time', lambda: state['cpu'])
    monkeypatch.setattr(bootstrap.resource, 'getrusage', lambda *_: SimpleNamespace(ru_maxrss=state['rss']//1024))
    monkeypatch.setattr(display.resource, 'getrlimit', lambda which: state['cpu_limit'] if which==display.resource.RLIMIT_CPU else state['as_limit'])
    monkeypatch.setattr(display.signal, 'getitimer', lambda *_: (state['timer'],0.))
    monkeypatch.setattr(display.signal, 'getsignal', lambda *_: state['handler'])
    root=deepcopy(old.root)
    workflow='NickNicky19/NFL-forecasting/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1'
    root['workflow_ref']=workflow;raw=display.private.canonical(root);root_hash=display.private.sha(raw)
    env=dict(GITHUB_REPOSITORY=display.private.REPO,GITHUB_RUN_ID='123456',GITHUB_SHA=root['source_sha'],
        GITHUB_JOB='audit-weekly-produce-v1',GITHUB_WORKFLOW_REF=workflow,GITHUB_ACTOR='NickNicky19',
        GITHUB_ACTOR_ID='208912933',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1')
    api=bootstrap.Metadata(env,lambda *_:pytest.fail('OFFLINE_SCOPE_MUST_NOT_REQUEST_HTTP'))
    seal=bootstrap.Seal(b'{"fictional_registration":true}',{},dict(fictional_native_inputs=True),api,
        bootstrap._KEY,registry_version=2,locator_bytes=b'{"fictional_locator":true}')
    document=dict(source_sha=root['source_sha'],run_id=env['GITHUB_RUN_ID'],job_id=env['GITHUB_JOB'],
        api_job_id=101,actor=deepcopy(display.operations.controller.OWNER),root_go_sha256=root_hash,
        registration_sha256=seal.registration_sha256)
    proof=bootstrap.Owner(document,seal,bootstrap._KEY)
    if actor=='bot':
        env.update(GITHUB_ACTOR='github-actions[bot]',GITHUB_ACTOR_ID='41898282')
        document.update(actor=deepcopy(display.operations.controller.BOT),
            schema_version=display.operations.controller.VERSION+'-current-child-proof')
        proof=display.operations.controller.Proof(document,display.operations.controller._KEY)
        proof.bootstrap_seal=seal
    authority=dict(schema_version=original.VERSION+'-native-authority',phase='infer',request_sha256='e'*64,
        owner_root_go_sha256=root_hash,repository=display.private.REPO,source_sha=root['source_sha'],
        run_id=env['GITHUB_RUN_ID'],run_attempt=1,job_id=env['GITHUB_JOB'],workflow_ref=workflow,api_job_id=101,
        issued_at_utc=root['issued_at_utc'],expires_at_utc=root['expires_at_utc'],
        actual_actions_api_authenticated=True,owner_root_checked=True,fits=0,public_release=False)
    if before_mint is not None:before_mint(state)
    context=display.checked_context(authority,raw,proof,env,old.source_root)
    return context,state,proof,api


@pytest.mark.parametrize('actor',['owner','bot'])
@pytest.mark.parametrize('counter',['cpu','rss'])
def test_local_infer_survives_numerical_work_without_extending_metadata_authority(packet,monkeypatch,counter,actor):
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    context,state,proof,api=local_infer_context(packet,monkeypatch,actor=actor)
    state.update(wall=100.,timer=320.)
    state[counter]=130. if counter=='cpu' else 600 << 20
    with pytest.raises(bootstrap.BootstrapError,match='BOOTSTRAP_SHARED_NATIVE_BUDGET'):
        display.operations._verify(proof,context.env,context.root_bytes)
    assert context.verify() is None
    assert api.calls==[]
    # A local numerical capability never becomes a private/API client proof.
    with pytest.raises(display.private.StoreError,match='LIVE_OPERATIONS_BOOTSTRAP_REQUIRED'):
        display.operations._verify(context._infer_local,context.env,context.root_bytes)
    import pickle
    with pytest.raises(ValueError,match='INFER_LOCAL_AUTHORITY_NOT_SERIALIZABLE'):
        pickle.dumps(context._infer_local)


@pytest.mark.parametrize('change',[
    dict(cpu=301.),dict(rss=(1 << 30)-(32 << 20)),dict(wall=421.),dict(timer=0.),
    dict(timer=421.),dict(cpu_limit=(400,400)),dict(as_limit=(8 << 30,8 << 30)),dict(handler=lambda *_:None)])
def test_local_infer_retains_every_existing_numerical_envelope(packet,monkeypatch,change):
    context,state,_,_=local_infer_context(packet,monkeypatch);state.update(change)
    with pytest.raises(ValueError,match='EXISTING_INFER_NUMERICAL_ENVELOPE_REQUIRED'):
        context.verify()


@pytest.mark.parametrize('counter',['cpu','rss','wall'])
def test_expired_metadata_cannot_mint_a_local_capability(packet,monkeypatch,counter):
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    def before(state):state[counter]={'cpu':130.,'rss':600 << 20,'wall':181.}[counter]
    with pytest.raises(bootstrap.BootstrapError,match='BOOTSTRAP_SHARED_NATIVE_BUDGET'):
        local_infer_context(packet,monkeypatch,before_mint=before)


@pytest.mark.parametrize('field',['phase','request_sha256','source_sha','api_job_id'])
def test_local_infer_rejects_changed_authority(packet,monkeypatch,field):
    context,_,_,_=local_infer_context(packet,monkeypatch)
    context.authority[field]='different'
    expected='CURRENT_NATIVE_MAE_ROOT_OR_CLOCK_CHANGED' if field=='source_sha' else 'NATIVE_MAE_AUTHORITY_CHANGED'
    with pytest.raises(ValueError,match=expected):
        context.verify()


@pytest.mark.parametrize('kind',['root','proof','seal','env','source_root','caps','root_bytes'])
def test_local_infer_rejects_mutable_aliases_and_scope_substitution(packet,monkeypatch,kind):
    context,_,proof,_=local_infer_context(packet,monkeypatch)
    if kind=='root':context.root['source_config']['fictional_change']=True
    elif kind=='proof':proof.document['api_job_id']=202
    elif kind=='seal':proof.bootstrap_seal.document['changed']=True
    elif kind=='env':context.env['GITHUB_RUN_ID']='123457'
    elif kind=='source_root':context.source_root=context.source_root.parent
    elif kind=='caps':context._infer_local.caps['CPU_seconds']=400
    else:context.root_bytes+=b' '
    with pytest.raises(ValueError):context.verify()


def test_local_infer_cannot_borrow_another_process_or_expired_root(packet,monkeypatch):
    context,_,_,_=local_infer_context(packet,monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(display.private,'process_identity',lambda:'another-process')
        with pytest.raises(ValueError,match='CURRENT_NATIVE_MAE_ROOT_OR_CLOCK_CHANGED'):
            context.verify()
    monkeypatch.setattr(display.runtime,'now_utc',lambda:display.runtime.utc(context.root['expires_at_utc']))
    with pytest.raises(ValueError,match='CURRENT_NATIVE_MAE_ROOT_OR_CLOCK_CHANGED'):
        context.verify()


@pytest.mark.parametrize('name',['nfl_lab/weekly_source_read_batch.py','nfl_lab/weekly_mae_display_runtime_v1.py'])
def test_local_infer_rehashes_actual_same_size_restored_mtime_source_and_helpers(packet,monkeypatch,name):
    import os
    context,_,_,_=local_infer_context(packet,monkeypatch);path=context.source_root/name
    before=path.read_bytes();stamp=path.stat();after=(b'!' if before[:1]!=b'!' else b'#')+before[1:]
    path.write_bytes(after);os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    assert path.stat().st_size==len(before) and path.stat().st_mtime_ns==stamp.st_mtime_ns
    with pytest.raises(ValueError,match='INFER_ACTUAL_SOURCE_CLOSURE_CHANGED'):
        context.verify()


@pytest.mark.parametrize('replacement',[None,SimpleNamespace(verify=lambda *_:None)])
def test_initialized_infer_requires_its_actual_private_capability(packet,monkeypatch,replacement):
    context,_,_,_=local_infer_context(packet,monkeypatch)
    context._infer_local=replacement
    with pytest.raises(ValueError,match='ACTUAL_PRIVATE_INFER_LOCAL_AUTHORITY_REQUIRED'):
        context.verify()


def test_valid_capability_cannot_be_borrowed_from_another_context(packet,monkeypatch):
    first,_,_,_=local_infer_context(packet,monkeypatch)
    second,_,_,_=local_infer_context(packet,monkeypatch)
    first._infer_local=second._infer_local
    with pytest.raises(ValueError,match='INFER_LOCAL_SCOPE_OR_PROCESS_CHANGED'):
        first.verify()
