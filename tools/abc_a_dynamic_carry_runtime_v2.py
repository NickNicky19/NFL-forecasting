"""Separate finite computational continuation. Reuse the completed A0 fit/rows.

Predictive parameters, sources, seeds and arithmetic are unchanged. A sequential
joblib backend avoids the failed second thread-pool creation without raising
the address-space/memory cap. V1 and its spent fit attempts remain immutable.
"""
from __future__ import annotations
import copy,datetime,gzip,hashlib,io,json,os,resource,sys,time,traceback,zipfile
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','ARROW_IO_THREADS']:
    os.environ[key]='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import abc_a_dynamic_carry_wave_v1 as base
OUT=ROOT/'reports/abc-championship/predictive-improvement-01/runtime-v2'
VERSION='ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
PARENT='ABC-PREDICTIVE-IMPROVEMENT-01-A-v1'
ACTUAL={'new_fit_attempts':0,'new_returned_fits':0,'restored_fits':0,'reused_A0_rows':0}
BEGIN_WALL=time.monotonic();BEGIN_CPU=time.process_time()

def main():
    import signal
    resource.setrlimit(resource.RLIMIT_CPU,(1700,1800))
    resource.setrlimit(resource.RLIMIT_AS,(1610612736,)*2)
    def exhausted(*_):raise TimeoutError('finite continuation envelope')
    signal.signal(signal.SIGALRM,exhausted);signal.signal(signal.SIGXCPU,exhausted);signal.alarm(2300)
    import numpy as np,pandas as pd,joblib,pyarrow as pa
    from nfl_lab import cdf_engine as cdf
    from tools import category_topfive_matched12_storage_v1 as st
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    start=time.monotonic();cpu=time.process_time()
    body=(OUT/'PROTOCOL_V1.json').read_bytes();plan=json.loads(body)
    supplied=sys.argv[sys.argv.index('--protocol-sha256')+1]
    if base.sha(body)!=supplied:raise ValueError('continuation protocol hash')
    mode=sys.argv[sys.argv.index('--mode')+1]
    for r in plan['code_bindings']:
        if base.sha((ROOT/r['path']).read_bytes())!=r['sha256']:raise ValueError('continuation source code changed')
    # Route all base helper outputs into the new namespace, preserving V1.
    base.OUT=OUT;base.VERSION=VERSION
    original_note=base.note;original_event=base.event
    def note(name,value):
        value=dict(value)
        if name=='START_V1.json':value.update(new_forest_fit_budget=2,completed_parent_A0_reused=True,original_unused_slot='CLOSED_NOT_RECYCLED')
        if name=='FORECAST_FREEZE_RECEIPT_V1.json':
            value.update(fits=ACTUAL['new_fit_attempts'],trees=32*ACTUAL['new_returned_fits'],
                returned_new_fits=ACTUAL['new_returned_fits'],restored_completed_parent_fits=ACTUAL['restored_fits'],
                reused_parent_A0_prediction_rows=ACTUAL['reused_A0_rows'],
                parent_failed_fit_attempts_preserved=2,cumulative_fit_attempts=2+ACTUAL['new_fit_attempts'],
                cumulative_successfully_returned_forests=1+ACTUAL['new_returned_fits'],
                CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,
                execution_backend='joblib.sequential;unchangedregisteredTREE_PARAMETERS',
                actual_new_CDF_inference_rows=923+1244+1244,
                new_structured_law_rows=2*(923+1244),source_2025_A0_issuance_unchanged=True)
        original_note(name,value)
    def event(kind,**fields):
        if fields.get('arm')=='A0'and fields.get('season')==2025:
            original_event('PARENT_A0_REUSE_'+kind,**{**fields,'new_fit_slot':None,'not_new_fit':True})
        else:
            if 'fit_slot'in fields:fields={**fields,'fit_slot':fields['fit_slot']-1}
            original_event(kind,**fields)
    base.note=note;base.event=event
    if mode=='run':
        store,_=st.open_store(ROOT,allocation_sha256=plan['storage']['allocation_sha256'],root_go=st.GO,readonly=True)
        parent=store.forward_root/'research'/PARENT
        failure_bytes=(OUT.parent/'EXECUTION_FAILURE_V1.json').read_bytes()
        if base.sha(failure_bytes)!=plan['parent_failure_record_sha256']:raise ValueError('parent failure identity changed')
        failure=json.loads(failure_bytes)
        ref=failure['returned_models'][0];assert(ref['season'],ref['arm'])==(2025,'A0')
        if ref['sha256']!=plan['runtime_amendment']['prior_completed_model_sha256']or failure['private_failure']['sha256']!=plan['runtime_amendment']['prior_failure_private_manifest_sha256']:raise ValueError('parent source member binding changed')
        oldmodel=parent/ref['object_id'];store.validate_reference(oldmodel,ref['sha256'])
        restored=joblib.load(io.BytesIO(oldmodel.read_bytes()))
        oldfailure=parent/'FAILED_PARTIALS_V1.zip';store.validate_reference(oldfailure,failure['private_failure']['sha256'])
        with zipfile.ZipFile(oldfailure)as z:cached=json.loads(gzip.decompress(z.read('FORECAST_PARTIALS.json.gz')))
        if len(cached)!=923 or any((r['season'],r['arm'])!=(2025,'A0_BACKFIELD_CDF')for r in cached):raise ValueError('parent completed forecast scope')
        original_fit=cdf.LeafCDFModel.fit
        def fit(cls,train,category,panel):
            names=category['panels'][panel]
            if not any(n.startswith('f_dcarry_')for n in names):
                if ACTUAL['restored_fits'] or not isinstance(restored,cdf.LeafCDFModel):raise ValueError('one authenticated A0 restoration only')
                if int(train.season.max())!=2024 or category!=restored.category or panel!=restored.panel:raise ValueError('parent fit recipe mismatch')
                y=cdf.numeric(train,category['target']);good=(cdf.strings(train,'participation_state')=='played')&cdf.valid_support(y,category['support'])
                modeled=train.loc[good&train.position.isin(category['modeled_roles'])]
                pd.testing.assert_frame_equal(restored.training_binding.reset_index(drop=True),modeled[restored.training_binding.columns].reset_index(drop=True),check_exact=True)
                design=cdf.FixedDesign.fit(modeled,names)
                if design!=restored.design:raise ValueError('parent fitted imputation mismatch')
                ACTUAL['restored_fits']+=1;return restored
            ACTUAL['new_fit_attempts']+=1
            if ACTUAL['new_fit_attempts']>2:raise ValueError('two new fit attempts exhausted')
            model=original_fit(train,category,panel);ACTUAL['new_returned_fits']+=1;return model
        cdf.LeafCDFModel.fit=classmethod(fit)
        original_persist=base.persist_model
        def persist(store,dest,model,year,arm,joblib_module):
            if(year,arm)==(2025,'A0'):
                base.STATE['model_refs'].append({**ref,'source_run_id':PARENT,'reused_not_new_bytes':True})
                event('COMPLETED_MODEL_RESTORED_READBACK',season=year,arm=arm,sha256=ref['sha256'])
                return
            return original_persist(store,dest,model,year,arm,joblib_module)
        base.persist_model=persist
        original_forecasts=base.cdf_forecasts
        def forecasts(model,q,arm,np_module):
            if arm=='A0_BACKFIELD_CDF'and q.season.eq(2025).all():
                expected={tuple(str(q.loc[i,k])for k in base.KEY+base.CTX)for i in q.index}
                got={tuple(str(r[k])for k in base.KEY+base.CTX)for r in cached}
                if expected!=got:raise ValueError('parent forecast context mismatch')
                ACTUAL['reused_A0_rows']=len(cached);return copy.deepcopy(cached)
            return original_forecasts(model,q,arm,np_module)
        base.cdf_forecasts=forecasts
    with joblib.parallel_backend('sequential'):
        base.main()
    (OUT/f'RUNTIME_{mode.upper()}_COUNTERS_V2.json').write_bytes(base.enc({**ACTUAL,'mode':mode,'state':'PASS','CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'predictive_recipe_unchanged':True,'parent_failed_attempts_not_refunded':True}))

if __name__=='__main__':
    try:main()
    except BaseException as e:
        import signal
        soft,hard=resource.getrlimit(resource.RLIMIT_CPU)
        if hard==1800:resource.setrlimit(resource.RLIMIT_CPU,(hard,hard))
        signal.signal(signal.SIGXCPU,signal.SIG_IGN)
        remaining=2400-(time.monotonic()-BEGIN_WALL)
        signal.alarm(max(1,min(90,int(remaining))))
        failure={'state':'FAILED','run_id':VERSION,'error_type':type(e).__name__,'actual_counters':ACTUAL,'phase':base.STATE['phase'],'finished_UTC':base.now(),'no_automatic_retry':True,'parent_evidence_preserved':True}
        if base.STATE.get('store')and base.STATE['destination'].exists():
            try:
                members={'FAILURE.json':base.enc(failure),'TRACEBACK.txt':traceback.format_exc().encode(),'FORECAST_PARTIALS.json.gz':gzip.compress(base.enc(base.STATE['forecasts']),mtime=0)}
                if base.STATE.get('pending_model_bytes'):members['RETURNED_MODEL_WRITE_FAILED.joblib']=base.STATE['pending_model_bytes']
                body=base.archive(members);p=base.STATE['destination']/'FAILED_PARTIALS_V2.zip';base.STATE['store'].write_bytes(p,body);base.STATE['store'].validate_reference(p,base.sha(body));failure['private_failure']={'sha256':base.sha(body),'bytes':len(body),'readback':'PASS'}
            except BaseException as error:failure['retention_error_type']=type(error).__name__
        (OUT/'EXECUTION_FAILURE_V2.json').write_bytes(base.enc(failure));raise
