"""One authenticated model restore and bounded retained/current-core parity.

Historical fixtures test the reusable core, not fresh current-source inference.
No refit, original-site write, public row export or retrospective issuance.
"""
from pathlib import Path
import datetime
import gzip
import hashlib
import importlib.util
import io
import json
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT = ROOT/'reports/abc-championship/post-wave-5w-v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def enc(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def main():
    start=time.monotonic();cpu=time.process_time()
    resource.setrlimit(resource.RLIMIT_AS,(2147483648,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(120,121));signal.alarm(150)
    import numpy as np,pandas as pd,pyarrow as pa,joblib,sklearn,scipy
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    from tools.category_topfive_matched12_storage_v1 import open_store,GO
    from nfl_lab import role_boosting as count
    from nfl_lab import count_a_mean_export_adapter_v1 as adapter
    store,_=open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=GO)
    plan=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-freeze-v1_2.json.gz').read_bytes()))
    entry=next(e for e in plan['extra_entries']if e.get('target')=='pass_td'and e.get('method')=='COUNT_A_MEAN')
    def owned(ref):
        p=Path(ref['path']);owners=[s for s in (store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy)if any(p.is_relative_to(r)for r in s._roots)]
        if len(owners)!=1:raise ValueError('exact retained source owner required')
        got=owners[0].validate_reference(p,ref['sha256'])
        if got['bytes']!=ref['bytes']:raise ValueError('retained source size mismatch')
        return p.read_bytes()
    proof=json.loads(owned(entry['producer_proof']));cell=proof
    for k in entry['producer_selector']:cell=cell[k]
    ref=entry['forecast']['container']
    if ref['sha256']!='5f55367c9f3389dbbe713b1aa95e691e77602cde99bf8e5ff657554a2d5a6a36':raise ValueError('wrong requested capsule')
    body=owned(ref)
    with zipfile.ZipFile(io.BytesIO(body))as z:members={n:z.read(n)for n in z.namelist()}
    mm=json.loads(members['MEMBER_MANIFEST.json'])['members']
    for n,r in mm.items():
        if sha(members[n])!=r['sha256']or len(members[n])!=r['bytes']:raise ValueError('member authentication failed')
    if sha(members['MODEL.joblib'])!=adapter.MODEL:raise ValueError('wrong requested model')
    audit=json.loads(members['MODEL_AUDIT.json'])
    relative='pass_td__COUNT_A_MEAN/FIT_START.json'
    fit_ref={**proof['artifacts'][relative],'path':str(Path(entry['producer_proof']['path']).parent/relative)}
    reservation=json.loads(owned(fit_ref));recipe=reservation['recipe'];parent=sha(enc(recipe))
    if parent!=audit['recipe_sha256']or adapter.procedure_version(parent,adapter.MODEL)!=adapter.PROCEDURE:raise ValueError('full mean recipe differs')
    pins=recipe['source_pins'];corrector=ROOT/'tools/modern_count_a_mean_v3.py'
    if sha(corrector.read_bytes())!=pins['mean_corrector']['sha256']:raise ValueError('original mean-corrector source hash differs')
    if audit['parameters']!=count.DESIGN:raise ValueError('original count design changed')
    current={'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pa.__version__,'sklearn':sklearn.__version__,'scipy':scipy.__version__,'joblib':joblib.__version__}
    if any(current[k]!=audit['environment'][k]for k in current):raise ValueError('trusted restoration environment differs')
    spec=importlib.util.spec_from_file_location('retained_count_mean_corrector',corrector);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Mark the single model load before deserialization; preserve a failure if it fails.
    (OUT/'COUNT_A_MODEL_LOAD_STARTED_V3.json').write_text(json.dumps({'state':'AUTHENTICATED_MODEL_LOAD_ATTEMPT','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_sha256':adapter.MODEL,'new_fits':0})+'\n')
    model=joblib.load(io.BytesIO(members['MODEL.joblib']))
    if type(model)is not count.RoleCountBoostingModel or model.category!=audit['category']:raise ValueError('trusted model type/category mismatch')
    if model.prior_training_binding is None or model.training_binding is None:raise ValueError('retained estimator/prior training bindings missing')
    train=recipe['training_cutoff_utc']
    for b in (model.training_binding,model.prior_training_binding):
        clocks=pd.to_datetime(b.outcome_available_utc,utc=True)
        if clocks.isna().any()or(clocks>=pd.Timestamp(train)).any():raise ValueError('training label after historical cutoff')
    fixture=pd.read_parquet(io.BytesIO(members['FIXTURE_FEATURES.parquet']))
    expected=pd.read_parquet(io.BytesIO(members['FIXTURE_EXPECTED.parquet']))
    forecasts=pd.read_parquet(io.BytesIO(members['FORECASTS.parquet']))
    keys=['season','week','game_id','player_id']
    if not forecasts.procedure_version.eq(adapter.PROCEDURE).all()or forecasts.duplicated(keys).any():raise ValueError('retained forecast identity differs')
    original,reasons=model.predict(fixture)
    corrected=module.correct_fallbacks(np,original,reasons,fixture.position.to_numpy(),model.priors,model.global_prior)
    if not np.array_equal(corrected,expected.point.to_numpy(float),equal_nan=True):raise ValueError('native retained fixture mean parity failed')
    if not np.array_equal(np.asarray(reasons,str),expected.fallback.fillna('').astype(str).to_numpy()):raise ValueError('native fallback parity failed')
    from tools import abc_a_dynamic_carry_wave_v1 as original_wave
    _,feature_plan,g,_=original_wave.sources();feature_ref=feature_plan['features']
    full_feature_match=feature_ref['sha256']==audit['query_features']['sha256']
    synthetic=False
    if full_feature_match:
        features=pd.read_parquet(io.BytesIO(owned(feature_ref)))
        features=features.loc[features.position.eq('QB')].copy()
        # Fixed outcome-free sampling: first16 fallback, first16 warm, then
        # earliest remaining identities to64. Never use correctness/outcomes.
        f=forecasts.sort_values(keys,kind='stable');fallback=f.fallback.fillna('').astype(str).ne('')
        chosen=pd.concat([f.loc[fallback].head(16),f.loc[~fallback].head(16),f.head(64)]).drop_duplicates(keys).head(64)
        query=chosen[keys].merge(features,on=keys,how='left',validate='one_to_one')
        if len(query)!=len(chosen)or query.position.isna().any():raise ValueError('historical feature identity join incomplete')
        reference=chosen.set_index(keys)
    else:
        query=fixture.copy();reference=expected.set_index(keys)
    binding={'model_sha256':adapter.MODEL,'parent_procedure_version':parent,'training_cutoff_utc':train}
    typed=adapter.predict_verified_mean(model,query,mean_corrector=module.correct_fallbacks,binding=binding)
    aligned=reference.loc[pd.MultiIndex.from_frame(typed[keys])]
    a=typed.expected_mean.to_numpy(float);b=aligned.point.to_numpy(float)
    if not np.array_equal(a,b,equal_nan=True):raise ValueError('typed adapter differs from retained complete mean procedure')
    finite=np.isfinite(a)&np.isfinite(b)
    if not np.array_equal(a[finite].view(np.uint64),b[finite].view(np.uint64)):raise ValueError('finite mean bits changed')
    if not np.array_equal(typed.fallback_reason.fillna('').astype(str).to_numpy(),aligned.fallback.fillna('').astype(str).to_numpy()):raise ValueError('typed fallback identity changed')
    if typed.probability.notna().any()or typed.EV.notna().any()or typed.issued_at_UTC.notna().any():raise ValueError('invented probability/EV/issuance')
    # Safe public metadata bindings for the existing all-category records.
    bundle_ref=g['frozen_bundle'];frozen=owned(bundle_ref)
    with zipfile.ZipFile(io.BytesIO(frozen))as z:catalog_raw=z.read('CATALOG_SCOPE.json');catalog=json.loads(catalog_raw)
    def bindings(x,trail=()):
        out=[]
        if isinstance(x,dict):
            if 'procedure_version'in x and 'procedure_id'in x:
                out.append({'source_key':list(trail),'procedure_id':x['procedure_id'],'procedure_version':x['procedure_version'],
                            'products':x.get('products',[]),'model_sha256':x.get('model_sha256'),'shortlist_group':x.get('shortlist_group')})
            for k,v in x.items():out+=bindings(v,trail+(k,))
        elif isinstance(x,list):
            for i,v in enumerate(x):out+=bindings(v,trail+(i,))
        return out
    catalog_result={'state':'AUTHENTICATED_EXISTING_METADATA_NOT_NEW_SCORES','source_archive_sha256':bundle_ref['sha256'],
                    'catalog_scope_member_sha256':sha(catalog_raw), 'bindings':bindings(catalog),
                    'limits':'Source key paths identify category/method hierarchy; private locators and all row forecasts excluded.'}
    (OUT/'A_EXISTING_PROCEDURE_BINDINGS_V1.json').write_text(json.dumps(catalog_result,indent=2)+'\n')
    buf=io.BytesIO();typed.to_parquet(buf,index=False)
    archive=store.forward_root/'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/POST_WAVE_COUNT_A_CORE_PARITY_V3.parquet'
    store.write_bytes(archive,buf.getvalue());store.validate_reference(archive,sha(buf.getvalue()));usage=store.verify_retained_checkpoint()
    result={'state':'PASS_EXACT_RETAINED_MODEL_AND_TYPED_CORE_PARITY','asof_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'product':'pass_td__COUNT_A_MEAN','procedure_version':adapter.PROCEDURE,'parent_procedure_version':parent,
        'capsule':{k:ref[k]for k in ['bytes','sha256']},'model_member':mm['MODEL.joblib'],'members':mm,
        'mean_corrector':{'recipe':module.RECIPE,'sha256':sha(corrector.read_bytes()),'source':'tools/modern_count_a_mean_v3.py'},
        'environment':current,'category':audit['category'],'feature_policy':recipe['feature_policy'],
        'training_cutoff_utc':train,'training_max_available_utc':str(max(pd.to_datetime(model.prior_training_binding.outcome_available_utc,utc=True))),
        'training_seasons':sorted(map(int,model.prior_training_binding.season.unique())),
        'original_fit_reservation_UTC':reservation['time_UTC'],'original_fit_completion_UTC':cell.get('fit_actual',{}).get('completed_UTC'),
        'native_fixture_rows':len(fixture),'typed_core_retained_rows':len(typed),'full_feature_hash_matches':full_feature_match,
        'typed_core_fallback_rows':int(typed.fallback_reason.fillna('').astype(str).ne('').sum()),
        'native_mean_column_all_NaN':bool(forecasts['mean'].isna().all()),'native_corrected_point_supported':int(forecasts.point.notna().sum()),
        'warm_and_prior_branch_bitwise_parity':'PASS_ON_SUPPORTED_RETAINED_ROWS; see actual fallback-row count, no inference about untested branches','model_loads':1,'predict_calls':2,'new_fits':0,
        'new_current_query_or_pregame_issuance':0,'current_source_adapter_state':'Arithmetic core verified on retained cases; fresh current SOURCE/feature receipt and owning-producer future query remain NOT_VERIFIED.',
        'public_feed_delivery':'NOT_EXECUTED; no original-site write, scheduler, source-guard or allowlist change.',
        'private_evidence':{'logical_id':'A-COUNT-A-CORE-PARITY-V3','bytes':len(buf.getvalue()),'sha256':sha(buf.getvalue()),'readback':'PASS_OWNER_LOCAL','offhost':'NOT_VERIFIED'},
        'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'retained_headroom_bytes':usage['wave_retained_limit_bytes']-usage['new_peer_physical_bytes']}
    (OUT/'COUNT_A_RESTORE_AND_PARITY_V3.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['state','procedure_version','native_fixture_rows','typed_core_retained_rows','typed_core_fallback_rows','full_feature_hash_matches','CPU_seconds']}))


if __name__=='__main__':
    main()
