"""One portable, bounded NEW target-CDF experiment; all bindings are in CLI plan.

The protocol must be publicly registered before execution. Restricted paths,
sources, storage descriptors and observed vectors never appear in this source.
One CDF fit supports its separately labeled mean, median and full-law products.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import resource
import signal
import sys
import time
import zipfile

VERSION='opportunity-four-targets-frozen-v1-20261029'
KEYS=['season','week','game_id','player_id']
CONTEXT=['team','opponent','position','kickoff_utc','cutoff_utc']
MIB=1024**2
CAPS={'CPU_seconds':180,'wall_seconds':270,'RSS_bytes':1024*MIB,'fits':1,'trees':32,'original_model_loads':0,'HTTP':0,'automatic_retries':0,'managed_write_attempts':3,'retained_private_bytes':16*MIB,'peak_private_bytes':32*MIB,'native_metadata_bytes':64*1024,'public_aggregate_bytes':192*1024,'bootstrap_replicates':500,'seed':1703}


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def auth(ref):
    path=Path(ref['path'])
    assert path.is_absolute() and path.resolve()==path and not path.is_symlink()
    body=path.read_bytes()
    assert len(body)==ref['bytes'] and digest(body)==ref['sha256']
    return body


def module(ref,name):
    auth(ref)
    spec=importlib.util.spec_from_file_location(name,ref['path'])
    value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value
    spec.loader.exec_module(value)
    return value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--go',required=True)
    args=parser.parse_args()
    body=Path(args.plan).read_bytes()
    assert digest(body)==args.sha256
    plan=json.loads(body)
    assert plan['version']==VERSION and plan['state']=='ROOT_AND_REVIEWER_SEALED' and plan['execution_authorized'] is True and plan['resources']==CAPS
    assert json.loads(Path(args.go).read_bytes())=={'state':'GO','root':'/root','independent_review':'PASS','scope':VERSION,'plan_sha256':args.sha256,'previous_managed_writer_closed':True}
    protocol=plan['public_protocol']
    assert len(protocol['commit'])==40 and all(c in '0123456789abcdef' for c in protocol['commit'])
    assert protocol['remote_readback']=='PASS' and protocol['run_id']==VERSION
    assert sys.flags.dont_write_bytecode
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
        os.environ[name]='1'
    for ref in plan['source_pins'].values():
        auth(ref)
    inputs={name:auth(ref) for name,ref in plan['inputs'].items()}
    qualification=json.loads(inputs['qualification'])
    assert qualification['state']=='PROVIDER_REPORTED_TARGET_LABEL_QUALIFICATION_COMPLETE'
    native=Path(plan['native_root'])
    assert not native.exists()
    native.mkdir(parents=True)
    begun,cpu=time.monotonic(),time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(180,181))
    class Stop(BaseException):
        pass
    def expired(*unused):
        raise Stop('finite target pilot budget consumed')
    signal.signal(signal.SIGALRM,expired)
    signal.signal(signal.SIGXCPU,expired)
    signal.setitimer(signal.ITIMER_REAL,260)
    blocked=[]
    def deny(event,unused):
        if event.startswith('socket.') or event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn']:
            blocked.append(event)
            raise Stop('offline child-free pilot')
    sys.addaudithook(deny)
    writes=[]
    fit_attempts=fit_entries=returned_fits=law_passes=law_rows=0
    store=None
    def usage():
        return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begun,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'fit_attempts':fit_attempts,'actual_forest_fit_entries':fit_entries,'returned_fits':returned_fits,'trees_returned':32*returned_fits,'original_model_loads':0,'law_scoring_passes':law_passes,'law_scoring_query_rows':law_rows,'CAS_attempts':len(writes),'HTTP':0,'blocked_calls':blocked}
    def note(name,value):
        value=encoded(value)
        assert sum(p.stat().st_size for p in native.iterdir())+len(value)<=CAPS['native_metadata_bytes']
        with (native/name).open('xb') as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    def check(retention_only=False):
        actual=usage()
        assert actual['CPU_seconds']<(178 if retention_only else 170) and actual['wall_seconds']<(268 if retention_only else 260) and actual['RSS_bytes']<=CAPS['RSS_bytes'] and (not blocked or retention_only)
    note('CONSUMED.json',{'state':'ONE_INVOCATION_ONE_NEW_TARGET_CDF_FIT_CONSUMED','plan_sha256':args.sha256,'protocol':protocol,'resources':CAPS,'original_allocations_refunded':False})
    try:
        # Reuse the audited RTLD_NOLOAD bootstrap; no subprocess exception.
        import ctypes
        import threadpoolctl
        libc=Path(plan['source_pins']['libc']['path'])
        assert Path(threadpoolctl.__file__).resolve()==Path(plan['source_pins']['threadpoolctl']['path'])
        mapped={str(Path(parts[5]).resolve()) for line in Path('/proc/self/maps').read_text().splitlines() if len(parts:=line.split())==6 and parts[5].startswith('/')}
        assert str(libc) in mapped and hasattr(os,'RTLD_NOLOAD')
        handle=ctypes.CDLL(str(libc),mode=os.RTLD_NOLOAD)
        previous=threadpoolctl.ThreadpoolController._system_libraries.get('libc')
        assert previous is None or previous._handle==handle._handle
        threadpoolctl.ThreadpoolController._system_libraries['libc']=handle
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.dataset as ds
        import joblib
        from sklearn.ensemble import ExtraTreesRegressor
        for name,expected in plan['environment'].items():
            assert importlib.metadata.version(name)==expected
        pa.set_cpu_count(1)
        pa.set_io_thread_count(1)
        sys.path.insert(0,plan['worktree'])
        from nfl_lab import cdf_engine as cdf
        from nfl_lab import weekly_future_inference as future
        from nfl_lab import category_topfive_targets_product_v1 as product
        assert cdf.TREE_PARAMETERS==plan['tree_parameters'] and cdf.PRIOR_WEIGHT==.05
        assert plan['category']['target']==product.TARGET=='rec_tgt'
        note('FICTIONAL_CHECKS.json',product.check_fictional())
        sp=plan['storage']
        original_store=module(sp['original_helper'],'target_original_store')
        metadata=module(sp['helper'],'target_prior_metadata')
        base=original_store.load_frozen(sp['forward_implementation']['path'],sp['legacy_library_root'])
        prior=metadata.build_storage_class(original_store.build_storage_class(base),json.loads(auth(sp['prior_metadata_descriptor'])))
        extension=module(sp['forward_metadata_helper'],'target_new_metadata')
        cls=extension.build_storage_class(prior,json.loads(auth(sp['metadata_descriptor'])))
        store=cls(sp['legacy_cache'],json.loads(auth(sp['market_policy'])),json.loads(auth(sp['legacy_policy'])),json.loads(auth(sp['prior_policy'])))
        output=Path(plan['output'])
        assert output==store.live_root/'research'/VERSION and not output.exists()
        store.register_root(output)
        with store.transaction():
            store._refresh()
            store._require(CAPS['peak_private_bytes'])
        def save(name,members,retention_only=False):
            assert not retention_only or name=='FAILED.zip'
            check(retention_only=retention_only)
            assert len(writes)<3
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
                for key,value in sorted(members.items()):
                    archive.writestr(key,value)
            value=stream.getvalue()
            retained=sum(ref['bytes'] for ref in writes)
            assert len(value)<=12*MIB and retained+len(value)+65536<=16*MIB and retained+2*len(value)+65536<=32*MIB
            reference={'path':str(output/name),'bytes':len(value),'sha256':digest(value)}
            writes.append(reference)
            store.write_bytes(output/name,value)
            observed=store.validate_reference(output/name)
            assert all(observed[key]==reference[key] for key in ['path','bytes','sha256']) and (output/name).read_bytes()==value
            with zipfile.ZipFile(output/name) as archive:
                assert set(archive.namelist())==set(members) and all(archive.read(key)==content for key,content in members.items())
            note(name.replace('.zip','_READBACK.json'),{'state':'EXACT_CAPSULE_AND_MEMBER_READBACK_PASS','reference':reference,'members':{key:{'bytes':len(value),'sha256':digest(value)} for key,value in members.items()},'usage':usage()})
            return reference
        def parquet(frame):
            frame=frame.copy()
            frame.attrs.clear()
            stream=pa.BufferOutputStream()
            pq.write_table(pa.Table.from_pandas(frame,preserve_index=False),stream,compression='zstd')
            return stream.getvalue().to_pybytes()
        save('FIT_OPPORTUNITIES_CONSUMED.zip',{'CONSUMED.json':encoded({'fits':1,'trees':32,'model_loads':0,'plan_sha256':args.sha256,'training_values_decoded':False,'protocol':protocol})})
        schedule=pd.read_csv(io.BytesIO(inputs['schedule']),usecols=['season','week','game_id','game_type'])
        assert not schedule.game_id.duplicated().any()
        regular=set(schedule.loc[schedule.game_type.eq('REG'),'game_id'].astype(str))
        category=copy.deepcopy(plan['category'])
        base_features=category['panels']['base']
        assert category['panels']['context']==base_features
        dataset=ds.dataset(plan['inputs']['features']['path'],format='parquet')
        cutoff=pd.Timestamp(plan['training_cutoff_utc'])
        # This is a separately identified new-target reconstruction. Project
        # only the active target, fixed features and required temporal context;
        # unused nonfocus target labels need not be decoded for a new model.
        training_columns=list(dict.fromkeys(KEYS+CONTEXT+['participation_state','outcome_available_utc','feature_max_source_available_utc','f_player_games_prior','rec_tgt']+base_features))
        train=dataset.to_table(columns=training_columns,filter=(ds.field('season')>=2022)&(ds.field('season')<=2025)&ds.field('game_id').isin(list(regular))&(ds.field('outcome_available_utc')<cutoff.to_pydatetime())&(ds.field('kickoff_utc')<cutoff.to_pydatetime()),use_threads=False).to_pandas()
        assert not train.duplicated(KEYS).any()
        assert train.participation_state.isin(['played','DNP','unknown']).fillna(False).all()
        training_values=pd.to_numeric(train.rec_tgt,errors='coerce')
        training_finite=np.isfinite(training_values)
        assert not (training_finite & train.participation_state.ne('played')).any()
        assert cdf.valid_support(training_values[training_finite],'count').all()
        assert set(train.season.unique())=={2022,2023,2024,2025}
        cdf.assert_clock_contract(train)
        new_training_digest=future.frame_digest(train)
        query_columns=list(dict.fromkeys(KEYS+CONTEXT+['outcome_available_utc','feature_max_source_available_utc','f_player_games_prior']+base_features))
        query=pq.read_table(pa.BufferReader(inputs['query']),columns=query_columns,use_threads=False).to_pandas()
        query['participation_state']='unknown'
        assert len(query)==2999 and not query.duplicated(KEYS).any() and query.season.eq(2026).all() and query.week.between(1,6).all() and query.game_id.astype(str).isin(regular).all()
        assert 'rec_tgt' not in query
        cdf.assert_clock_contract(query)
        original_fit=ExtraTreesRegressor.fit
        def counted_fit(estimator,*fit_args,**fit_kwargs):
            nonlocal fit_entries
            fit_entries+=1
            assert fit_entries<=1
            return original_fit(estimator,*fit_args,**fit_kwargs)
        ExtraTreesRegressor.fit=counted_fit
        fit_attempts+=1
        model=cdf.LeafCDFModel.fit(train,category,'base')
        assert model.forest is not None
        returned_fits+=1
        model_stream=io.BytesIO()
        joblib.dump(model,model_stream,compress=3)
        members={'MODELS/rec_tgt_CDF_BASE.joblib':model_stream.getvalue()}
        new=cdf.prediction_rows(model,query,score=False)
        new['method']='TGT_CDF_BASE'
        new['point_semantics']='full_count_law_with_separate_lower_median_and_mean'
        prior_rows=cdf.prediction_rows(model,query,score=False,prior_only=True)
        prior_rows['method']='TGT_ROLE_PRIOR'
        prior_rows['point_semantics']='training_position_geometric_support_prior_with_mean_floor0.05'
        recent3=product.recent_mean_rows(model,query,3)
        recent8=product.recent_mean_rows(model,query,8)
        frozen=pd.concat([new,prior_rows,recent3,recent8],ignore_index=True)
        frozen=frozen.drop(columns=[name for name in ['actual','participation_state','outcome_state','crps','log_score','cdf_actual','cdf_actual_below','brier'] if name in frozen])
        assert len(frozen)==11996 and not frozen.duplicated(KEYS+['target','method']).any() and set(frozen.method)==set(product.METHODS)
        assert (fit_attempts,fit_entries,returned_fits)==(1,1,1)
        def reject(*unused,**unused_kw):
            raise Stop('NO_REFIT_AFTER_FREEZE')
        ExtraTreesRegressor.fit=reject
        cdf.LeafCDFModel.fit=classmethod(reject)
        source_proof={'new_training_digest':new_training_digest,'new_training_rows':len(train),'seasons':[2022,2023,2024,2025],'projection':'Authenticated retained accepted-feature source; only active rec_tgt target, fixed base features and required context. No unused nonfocus target labels decoded. Exact source-row order retained; unknown neverzero.','new_source_matched_reconstruction':True,'training_columns':training_columns}
        members.update({'PREPARED_TRAIN.parquet':parquet(train),'PREPARED_QUERY.parquet':parquet(query),'FORECASTS.parquet':parquet(frozen),'MODEL_AUDIT.json':encoded(model.audit),'SOURCE_PROOF.json':encoded(source_proof),'PLAN.json':body})
        freeze=save('FORECASTS_MODELS.zip',members)
        frozen_columns=list(frozen.columns)
        point_columns=[name for name in ['mean','median','point','p10','p90','variance'] if name in frozen]
        point_bits=frozen[point_columns].to_numpy(dtype=np.float64).view(np.uint64).copy()
        # Evaluation target values are projected only after the exact global
        # model/forecast freeze. Label qualification was exposed development.
        labels=pq.read_table(pa.BufferReader(inputs['query']),columns=KEYS+CONTEXT+['participation_state','rec_tgt','stats_observed','official_physical_event'],use_threads=False).to_pandas()
        assert labels[KEYS].reset_index(drop=True).equals(query[KEYS].reset_index(drop=True))
        labels=labels.rename(columns={'rec_tgt':'actual'})
        labels.loc[labels.participation_state.ne('played'),'actual']=np.nan
        finite=labels.participation_state.eq('played')&np.isfinite(pd.to_numeric(labels.actual,errors='coerce'))
        assert cdf.valid_support(labels.loc[finite,'actual'],'count').all()
        assert labels.participation_state.isin(['played','DNP','unknown']).fillna(False).all()
        assert labels.loc[finite,'stats_observed'].eq(True).fillna(False).all() and labels.loc[finite,'official_physical_event'].eq(True).fillna(False).all()
        graded=frozen.merge(labels[KEYS+['actual','participation_state']],on=KEYS,validate='many_to_one')
        for name in ['crps','log_score','cdf_actual','cdf_actual_below','brier']:
            graded[name]=np.nan
        for method,prior_only in [('TGT_CDF_BASE',False),('TGT_ROLE_PRIOR',True)]:
            q=query.copy()
            q['rec_tgt']=labels.actual.to_numpy()
            q['participation_state']=labels.participation_state.to_numpy()
            mask=graded.method.eq(method)
            f=graded.loc[mask].reset_index(drop=True)
            law_passes+=1
            law_rows+=len(q)
            assert law_passes<=2 and law_rows<=5998
            score=cdf.score_frozen_rows(model,q,f,prior_only=prior_only)
            for name in ['crps','log_score','cdf_actual','cdf_actual_below']:
                graded.loc[mask,name]=score[name].to_numpy()
        pd.testing.assert_frame_equal(graded[frozen_columns],frozen,check_exact=True)
        assert np.array_equal(graded[point_columns].to_numpy(dtype=np.float64).view(np.uint64),point_bits)
        def summaries(frame):
            output={}
            for method,rows in frame.groupby('method',sort=True):
                output[method]={'mean':product.metric(rows,'mean'),'median':product.metric(rows,'median',integer_point=True)}
                if method in ['TGT_CDF_BASE','TGT_ROLE_PRIOR']:
                    output[method]['proper']=product.proper(rows)
                else:
                    output[method]['proper']={'CRPS':None,'log_loss':None,'reason':'POINT_ONLY_UNAUTHENTICATED_DISTRIBUTION'}
            return output
        primary=graded.loc[graded.position.isin(product.PRIMARY_ROLES)]
        primary_summary=summaries(primary)
        assert primary_summary['TGT_CDF_BASE']['median']['planned']==qualification['evaluation']['primary_RB_WR_TE']['planned']
        assert primary_summary['TGT_CDF_BASE']['median']['scored']==qualification['evaluation']['primary_RB_WR_TE']['supported']
        result={'version':VERSION,'state':'NEW_TARGET_CDF_BASELINE_COMPARISON_COMPLETE','product':'rec_tgt_nflverse_weekly_v1','public_protocol':protocol,'new_fits':1,'new_trees':32,'original_model_loads':0,'new_forecast_rows':11996,'new_CDF_query_rows':2999,'unique_query_player_games':2999,'method_families':{'CDF':['TGT_CDF_BASE'],'training_position_prior':['TGT_ROLE_PRIOR'],'recent_history_mean':['TGT_RECENT3_MEAN','TGT_RECENT8_MEAN']},'training':{'seasons':[2022,2023,2024,2025],'cutoff_utc':plan['training_cutoff_utc'],'rows':len(train),'rule':'FROZEN_PRESEASON_2022_2025; no within2026refits; not weeklyH-MULTI','feature_memory':'Existingrepresentation permits older2019–2021 history in features; not strictcurrentseason information'},'evaluation':{'season':2026,'intended_weeks':list(range(1,8)),'supported_weeks':list(range(1,7)),'games':93,'week7':'MISSING_COMPATIBLE_QUERY_AND_TARGET_LABEL_SOURCE; plannedgap retained before outcomes','evidence':'EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION; original7dayassumption preserved; not authenticpregame'},'primary_roles':product.PRIMARY_ROLES,'primary':'Point-displayMAE; CDFactual lowercountmedian vs predeclaredrecent8unroundedmean; everycompatiblemean/median retained separately','primary_results':primary_summary,'all_role_operational_coverage':summaries(graded),'weekly':{str(week):summaries(rows) for week,rows in primary.groupby('week',sort=True)},'paired_primary_vs_recent8':{'game':product.paired(primary,'TGT_RECENT8_MEAN',cluster='game_id'),'week':product.paired(primary,'TGT_RECENT8_MEAN',cluster='week')},'probability_offer_EV_metrics':{'value':None,'reason':'NO_AUTHENTICATED_TARGET_OFFERS_PRICE_SETTLEMENT_OR_PREGAME_SELECTIONS'},'website_comparison':{'value':None,'reason':'NO_WEBSITE_TARGET_FORECAST_PRODUCT'},'exact_credit_exceptions':'Provider-reported weeklytargets; historicalbuilderbinding/nullified/two-point exclusions notfullyverified; not operationaltargetcontract','forecast_columns_unchanged_by_grading':True,'new_genuine_pregame_capture':0,'operational_admission_deployment':False,'proper_scores':'CDF/priorlaws proper scores secondary; no calibratedthresholdclaim','usage_before_grade':usage()}
        grade=save('GRADE_COMPLETE.zip',{'RESULT.json':encoded(result),'GRADED_ROWS.parquet':parquet(graded),'SOURCE_BINDINGS.json':encoded(plan['inputs'])})
        check()
        note('COMPLETE.json',{'state':result['state'],'freeze':freeze,'grade':grade,'usage':usage(),'managed_writer':'CLOSED'})
        public={**result,'freeze':freeze,'grade':grade,'usage':usage()}
        target=Path(plan['private_result_metadata'])
        assert not target.exists()
        value=encoded(public)
        assert len(value)<=CAPS['public_aggregate_bytes']
        target.write_bytes(value)
        print(json.dumps({'state':result['state'],'primary_results':{method:{'mean_MAE':values['mean']['MAE'],'median_MAE':values['median']['MAE']} for method,values in primary_summary.items()},'primary_comparison':result['paired_primary_vs_recent8'],'usage':usage(),'freeze':freeze,'grade':grade}))
    except BaseException as error:
        record={'state':'TARGET_PILOT_FAILURE_PRESERVED','type':type(error).__name__,'error':str(error),'usage':usage(),'automatic_retry':False}
        note('FAILED.json',record)
        if store is not None and len(writes)<3 and 'save' in locals():
            try:
                partial={'FAILED.json':encoded(record),'PARTIAL_STATUS.json':encoded({'state':'PARTIAL_NOT_COMPLETE_COMPARISON','returned_fits':returned_fits,'original_budget_not_refunded':True})}
                partial.update(locals().get('members',{}))
                if 'freeze' in locals():
                    partial={'FAILED.json':encoded(record),'COMPLETED_FREEZE_REFERENCE.json':encoded(freeze)}
                    if 'graded' in locals():
                        partial['PARTIAL_GRADED_ROWS.parquet']=parquet(graded)
                    if 'result' in locals():
                        partial['PARTIAL_RESULT.json']=encoded(result)
                else:
                    if 'frozen' in locals():
                        partial['PARTIAL_FORECASTS.parquet']=parquet(frozen)
                    if 'query' in locals():
                        partial['PREPARED_QUERY.parquet']=parquet(query)
                    if 'train' in locals():
                        partial['PREPARED_TRAIN.parquet']=parquet(train)
                save('FAILED.zip',partial,retention_only=True)
            except BaseException as retention:
                note('FAILURE_RETENTION.json',{'type':type(retention).__name__,'error':str(retention)})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':
    main()
