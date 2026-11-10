"""Two aligned-timing RB Leaf fits; cached F0/F1 remain unchanged.

Offline source reconstruction, exact baseline preconditions, then F2/F3 fits
with returned states persisted before inference. No scoring or live capture.
"""
from __future__ import annotations
import argparse, datetime, gzip, hashlib, importlib.util, io, json, os
from pathlib import Path
import resource, signal, sys, time, traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
VERSION='PROFILE-INCREMENT-CLOSURE-AND-NEXT-02-A-FRESHNESS-v1'
KEY=['season','week','game_id','player_id']
CTX=['team','opponent','position','kickoff_utc','cutoff_utc']
ARMS=['F0_ORIGINAL_BASE','F1_ORIGINAL_PROFILE','F2_48H_BASE','F3_48H_PROFILE']
STATE=dict(phase='NOT_STARTED',fits_attempted=0,fits_returned=0,fit_CPU_seconds=0.,artifacts=[])

def enc(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def check(ok,message):
    if not ok:raise ValueError(message)
def local(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def document(path,expected):
    b=Path(path).read_bytes();check(sha(b)==expected,'bound public document changed');return b,json.loads(b)

def authorize(args):
    raw,p=document(args.protocol,args.protocol_sha256)
    _,g=document(args.root_go,args.root_go_sha256)
    _,publication=document(args.publication_receipt,args.publication_receipt_sha256)
    check(p.get('version')==VERSION and p.get('state')=='ROOT_REGISTERED_EXECUTION_GO','explicit finite freshness protocol required')
    check(p.get('arms')==ARMS and p.get('maximum_new_fits')==2 and p.get('seasons')==[2026],'two annual-origin fit scope changed')
    check(p.get('alternative_policy')=='KICKOFF_PLUS_48H_RECONSTRUCTED_SENSITIVITY','registered timing alternative changed')
    check(g.get('state')=='ROOT_AND_INDEPENDENT_GO'and g.get('protocol_sha256')==args.protocol_sha256,'root and independent exact GO required')
    check(publication.get('state')=='PUBLICATION_COMPLETE','actual publication/readback required before execution')
    for path,expected in p['code_sha256'].items():check(sha((ROOT/path).read_bytes())==expected,'bound source changed: '+path)
    for path,expected in p['source_configuration_sha256'].items():check(sha((ROOT/path).read_bytes())==expected,'bound source configuration changed')
    check(p['resources']['CPU_seconds']==1600 and p['resources']['wall_seconds']==3600 and p['resources']['RSS_bytes']==3*1024**3,'registered runtime envelope changed')
    check(p.get('query_projection')=='OWN_BASE30_WITH_EXACT_PREFIT_PARITY_OR_FULL_SOURCE','explicit output-preserving source projection contract required')
    check(p['resources'].get('pre_fit_CPU_reserve_seconds')==400,'measured pipeline requires declared400CPU fit/persistence reserve')
    STATE['protocol_raw']=raw
    return p

def runtime(plan):
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='2'
    resource.setrlimit(resource.RLIMIT_CPU,(1480,1600));resource.setrlimit(resource.RLIMIT_AS,(plan['resources']['RSS_bytes'],)*2)
    def stop(signum,_):
        if signum==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
        raise TimeoutError('finite aligned-timing package; final failure retention reserve')
    signal.signal(signal.SIGXCPU,stop);signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGTERM,stop);signal.alarm(3480)
    def offline(event,_args):
        if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline retained-source package')
    sys.addaudithook(offline)
    import numpy as np,pandas as pd,pyarrow as pa
    pa.set_cpu_count(2);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
    return np,pd

def run(plan,args):
    np,pd=runtime(plan);import joblib
    from threadpoolctl import threadpool_limits
    import pyarrow.parquet as pq
    start=time.monotonic();cpu=time.process_time()
    guard=local('nfl_lab.profile_freshness_active_storage_v1','nfl_lab/profile_freshness_a_storage_v1.py')
    timing=local('nfl_lab.profile_freshness_active_v1','nfl_lab/profile_freshness_a_v1.py')
    features=local('nfl_lab.profile_freshness_repaired_features_v1','nfl_lab/player_context_completion_features_v1.py')
    increment=local('nfl_lab.profile_freshness_existing_blocks_v1','nfl_lab/profile_increment_a_v2.py')
    core=local('nfl_lab.profile_freshness_existing_efficiency_v1','nfl_lab/player_context_rush_efficiency_v1.py')
    cdf=local('nfl_lab.cdf_engine','nfl_lab/cdf_engine.py')
    old=local('tools.profile_freshness_source_owner_v1','tools/player_context_completion_efficiency_v1.py')
    carry=local('tools.profile_freshness_existing_prediction_adapter_v1','tools/abc_a_dynamic_carry_wave_v1.py')
    store=guard.FreshnessStore(ROOT,ROOT/plan['allocation']['path'],plan['allocation']['sha256'],root_go=guard.GO)
    STATE['store']=store
    def put(name,body,failure=False):
        r=store.put(name,body,failure=failure);STATE['artifacts'].append(r);return r
    def parquet(frame):
        b=io.BytesIO();frame.to_parquet(b,index=False);return b.getvalue()
    try:
        check(not(store.destination/'CONSUMED_FRESHNESS_EXECUTION_V1.json').exists(),'package already consumed; no automatic rerun')
        put('CONSUMED_FRESHNESS_EXECUTION_V1.json',enc(dict(version=VERSION,UTC=now(),maximum_new_fits=2,original_fits_reused=2,policy=timing.ALTERNATIVE)))
        put('PRIVATE_EXECUTION_PROTOCOL.json',STATE.pop('protocol_raw'))
        STATE['phase']='EXACT_SAVED_BASELINE_INPUT_READBACK'
        refs=plan['retained_refs'];bodies=store.read_many(refs);byid={r['id']:r for r in refs}
        def saved(name):
            ref=plan['saved_ids'][name];check(ref in byid,'required saved input not in reviewed references');return bodies[ref]
        qbase=pd.read_parquet(io.BytesIO(saved('query_base')))
        qpce=pd.read_parquet(io.BytesIO(saved('query_profile')))
        source_binding=json.loads(saved('source_binding'))
        check(len(qbase)==1364 and len(qpce)==1364 and not qbase.duplicated(KEY).any(),'saved query population changed')
        for f in [qbase,qpce]:
            for name in ['kickoff_utc','cutoff_utc']:f[name]=timing.aware(f[name])
        qpce=timing.align_cached_queries(qbase,qpce)
        # Read old forecast bytes without model deserialization or re-inference.
        parts=[]
        for alias,key,oldarm in [(ARMS[0],'F0_forecasts','RB_ONLY_LEAF_BASE'),(ARMS[1],'F1_forecasts','R2_RB_ONLY_LEAF_PLAYER_OFFENSE')]:
            raw=saved(key);rows=json.loads(gzip.decompress(raw));check(len(rows)==1364 and all(r['arm']==oldarm for r in rows),'reused procedure/row scope differs')
            check(len({tuple(r[k]for k in KEY)for r in rows})==1364 and {tuple(r[k]for k in KEY)for r in rows}==set(map(tuple,qbase[KEY].to_numpy())),'reused baseline query identities differ')
            parts.append(dict(ref=byid[plan['saved_ids'][key]],procedure_alias=alias,original_arm=oldarm,rows=len(rows),reuse='EXACT_RETAINED_OUTPUT_NO_NEW_INFERENCE'))
        STATE['phase']='BOUND_EXISTING_FOOTBALL_INPUTS'
        old.STATE['source_owner']=store.prior
        data=old.load_inputs(pd);audit=old.audited_feature_binding(data)
        check(audit==source_binding['audit'],'source-matched corrected-adapter evidence differs')
        check([old.safe(r)for r in data['pbp_refs']]==source_binding['pbp'],'PBP sources changed')
        base_columns=list(data['category']['panels']['base']);profile_columns=list(increment.SUPPORT+increment.PLAYER_OFFENSE)
        check(len(base_columns)==30 and len(profile_columns)==98,'existing method/profile block changed')
        cached_train=increment.rb_training_population(data['train'])
        cached_train=cached_train.loc[cached_train.season.lt(2026)&timing.aware(cached_train.outcome_available_utc).lt(pd.Timestamp('2026-09-01',tz='UTC'))].copy().reset_index(drop=True)
        check(len(cached_train)==14644,'fixed RB training population changed')
        # Full raw warm context, including allowed POST history, is rebuilt before
        # selecting the old exact REG/RB fit rows. Dropping POST first is invalid.
        raw_full_bytes=old.pin(data['hgb_plan']['training_features'])
        schema=pq.ParquetFile(io.BytesIO(raw_full_bytes)).schema_arrow.names
        wanted=list(dict.fromkeys(KEY+CTX+['season_type','game_type','participation_state','outcome_available_utc','is_home',timing.CLOCK_KIND_FIELD]+features.PLAYER_STATS+['team_stat_'+n for n in features.TEAM_STATS]))
        raw_full=pd.read_parquet(io.BytesIO(raw_full_bytes),columns=[n for n in wanted if n in schema]);del raw_full_bytes
        check(len(raw_full)==62388,'complete original training/warm context changed')
        history=data['history'].copy()
        for name in ['kickoff_utc','outcome_available_utc']:history[name]=timing.aware(history[name])
        STATE['phase']='OLD_POLICY_NUMERIC_PARITY_NOT_MODEL_RERUN'
        old_train,old_train_policy=timing.rebuild_training(raw_full,cached_train,features,timing.ORIGINAL)
        train_parity=timing.exact_columns(cached_train,old_train,base_columns)
        old_query,old_query_policy=timing.rebuild_queries(history,qbase,features,timing.ORIGINAL)
        query_parity=timing.exact_columns(qbase,old_query,base_columns)
        for v in [train_parity,query_parity]:check(v['state']=='PASS_EXACT_NUMERIC_AND_MISSINGNESS','original base features do not reconstruct exactly')
        def clock_parity(left,right):
            a=timing.aware(left);b=timing.aware(right)
            return int((~(a.eq(b)|(a.isna()&b.isna()))).sum())
        guard_parity=dict(training_base=clock_parity(cached_train.feature_max_source_available_utc,old_train.feature_max_source_available_utc),
            query_base=clock_parity(qbase.base_feature_clock,old_query.feature_max_source_available_utc))
        check(not any(guard_parity.values()),'original base source guards do not reconstruct exactly')
        hist7,_=timing.retime_history(history,timing.ORIGINAL,declared_source_lane=timing.ORIGINAL)
        context7=timing.TimingEfficiencyContext(data['frames'],hist7,timing.ORIGINAL)
        old_aug,_=context7.augment(old_query,rich=False)
        pce_parity=timing.exact_columns(qpce,old_aug,profile_columns)
        check(pce_parity['state']=='PASS_EXACT_NUMERIC_AND_MISSINGNESS','old complete query profile block changed')
        guard_parity['query_profile_union']=clock_parity(qpce.feature_max_source_available_utc,old_aug.feature_max_source_available_utc)
        check(not guard_parity['query_profile_union'],'original profile source guard changed')
        # Old training PCE was not retained. Compare deterministic ordinary,
        # sparse and cold contexts to the unchanged old constructor; do not
        # claim nonexistent full saved-training PCE byte parity.
        reference=core.EfficiencyContext(data['frames'],history)
        chosen=[]
        for predicate in [old_train.f_player_games_prior.eq(0),old_train.f_player_games_prior.between(1,2),old_train.f_player_games_prior.ge(3)]:
            sample=old_train.loc[predicate].sort_values(KEY,kind='stable')
            if len(sample):chosen.append(sample.iloc[0])
        chosen.append(old_train.sort_values(KEY,kind='stable').iloc[-1]);case_results=[]
        for r in chosen:
            a,ac,_=reference.profile(r.player_id,r.team,r.opponent,r.cutoff_utc,8,False)
            b,bc,_=context7.profile(r.player_id,r.team,r.opponent,r.cutoff_utc,8,False)
            check(all(a[n]==b[n]for n in profile_columns),'old/new seven-day contextual constructor differs')
            check((pd.isna(ac)and pd.isna(bc))or ac==bc,'old/new source maximum differs')
            case_results.append(dict(identity_sha256=sha(enc({k:int(r[k])if k in {'season','week'}else str(r[k])for k in KEY})),fields=len(profile_columns),state='EXACT'))
        ages7=dict(ordinary=timing.ordinary_age_records(hist7,old_query),profile=timing.age_records(context7,old_query))
        old_age_ref=put('SOURCE_AGE_7DAY_PRIVATE_V1.json.gz',gzip.compress(enc(ages7),mtime=0))
        old_public_age=dict(ordinary=timing.age_summary(ages7['ordinary'],'ordinary'),profile=timing.age_summary(ages7['profile'],'profile'))
        parity=dict(state='PASS_ORIGINAL_BASE_AND_QUERY_PROFILE_PARITY',training_base=train_parity,query_base=query_parity,query_profile=pce_parity,training_profile_cases=case_results,source_guard_parity=guard_parity,
            limitation='Full original training PCE matrix was not retained; no byte parity is invented. Existing profile functions and checked source constructor retained; no old model refit/inference.',old_training_policy=old_train_policy,old_query_policy=old_query_policy)
        put('ORIGINAL_INPUT_PARITY_V1.json',enc(parity))
        # Preserve model-fit labels separately from the feature rebuild and free
        # large old-policy matrices before the alternative construction.
        del reference,context7,old_aug,old_train,hist7,ages7
        import gc;gc.collect()
        STATE['phase']='ALIGNED_48H_TRAINING_AND_QUERY_REBUILD'
        train,train_policy=timing.rebuild_training(raw_full,cached_train,features,timing.ALTERNATIVE)
        # Exact source projection is permitted only for the frozen own-player
        # dependency whitelist, never a training/population/cohort restriction.
        projection_used=tuple(base_columns)==timing.BASE30
        projection_checks=[];case_rate=[]
        fixed_cuts=sorted(qbase.cutoff_utc.unique())
        if projection_used:
            for cut in list(dict.fromkeys([fixed_cuts[0],fixed_cuts[-1]])):
                case=qbase.loc[qbase.cutoff_utc.eq(cut)].copy().reset_index(drop=True)
                beg=time.process_time();full,_=timing.rebuild_queries(history,case,features,timing.ALTERNATIVE)
                full_cpu=time.process_time()-beg
                beg=time.process_time();projected,_=timing.rebuild_queries(history,case,features,timing.ALTERNATIVE,
                    own_source_projection=True,consumed_columns=base_columns)
                projected_cpu=time.process_time()-beg
                parity_case=timing.exact_columns(full,projected,base_columns)
                projection_checks.append(dict(cutoff_utc=pd.Timestamp(cut).isoformat(),query_rows=len(case),
                    full_CPU_seconds=full_cpu,projected_CPU_seconds=projected_cpu,parity=parity_case,
                    meaning='Same source/learner inputs; unconsumed global guard is separately conservative, not actual own-player feature age'))
                case_rate.append(projected_cpu/max(1,len(case)))
                if parity_case['state']!='PASS_EXACT_NUMERIC_AND_MISSINGNESS':projection_used=False
                del full,projected
        STATE['query_progress']=[]
        def query_progress(event):
            event=dict(event);remaining=event['total_batches']-event['batch_index']
            if event['batch_index']==1:
                estimate=max(event['CPU_seconds']*remaining,(max(case_rate)if case_rate else 0.)*len(qbase))
                event.update(observed_process_CPU_seconds=time.process_time(),estimated_remaining_query_CPU_seconds=estimate,
                    remaining_fit_preparation_and_persistence_reserve_CPU_seconds=plan['resources']['pre_fit_CPU_reserve_seconds'],
                    forecast='First-batch/source-only estimate, not measured complete runtime')
                STATE['query_progress'].append(event)
                if time.process_time()+estimate+plan['resources']['pre_fit_CPU_reserve_seconds']>1480:
                    raise TimeoutError('first-cutoff measured estimate cannot safely leave the registered prefit reserve')
            else:STATE['query_progress'].append(event)
        query,query_policy=timing.rebuild_queries(history,qbase,features,timing.ALTERNATIVE,progress=query_progress,
            own_source_projection=projection_used,consumed_columns=base_columns)
        hist48,history_policy=timing.retime_history(history,timing.ALTERNATIVE,declared_source_lane=timing.ORIGINAL)
        context48=timing.TimingEfficiencyContext(data['frames'],hist48,timing.ALTERNATIVE)
        check(len(context48.accepted.withheld_future_source_games)==14,'missing W7 source identities/clocks must remain withheld')
        train,_=context48.augment(train,rich=False);query,_=context48.augment(query,rich=False)
        check(len(train)==14644 and len(query)==1364,'aligned population changed')
        check(train[KEY].reset_index(drop=True).equals(cached_train[KEY].reset_index(drop=True)),'fixed training row order changed')
        check(train[['rush_yd','participation_state']].reset_index(drop=True).equals(cached_train[['rush_yd','participation_state']].reset_index(drop=True)),'training labels/participation changed beyond timing')
        check(query.outcome_available_utc.isna().all()and query.participation_state.eq('unknown').all(),'future target outcome entered inference')
        check(not any(n in query and query[n].notna().any()for n in ['rush_yd','rush_att','actual','point','prediction']),'target-game value entered features')
        train_columns=KEY+CTX+['rush_yd','participation_state','outcome_available_utc','feature_max_source_available_utc']+base_columns+profile_columns
        query_columns=KEY+CTX+['participation_state','outcome_available_utc','feature_max_source_available_utc','query_clock_contract','query_evidence_tier']+base_columns+profile_columns
        train_ref=put('TRAINING_ALIGNED_48H_BASE_AND_PLAYER_PROFILE.parquet',parquet(train[list(dict.fromkeys(train_columns))]))
        query_ref=put('QUERY_ALIGNED_48H_BASE_AND_PLAYER_PROFILE.parquet',parquet(query[list(dict.fromkeys(query_columns))]))
        ages48=dict(ordinary=timing.ordinary_age_records(hist48,query),profile=timing.age_records(context48,query))
        new_age_ref=put('SOURCE_AGE_48H_PRIVATE_V1.json.gz',gzip.compress(enc(ages48),mtime=0))
        new_public_age=dict(ordinary=timing.age_summary(ages48['ordinary'],'ordinary'),profile=timing.age_summary(ages48['profile'],'profile'))
        offered=None
        if plan.get('offered_identities_ref'):
            ref=plan['offered_identities_ref'];raw=store.read(ref['id'],ref['sha256'],namespace=ref['namespace'])
            check(len(raw)==ref['bytes'],'offered identity metadata size differs');m=json.loads(raw)
            offered={tuple(r[k]for k in KEY)for r in m['player_games']}
            check(len(offered)==m['unique_player_games'],'offered identity membership duplicate/unbound')
        public_ages=dict(id=VERSION+'::SOURCE_AGE_DIAGNOSIS',authentic_observation_clocks=False,population='same original query universe; broader source-row reconstruction, not a current roster',
            old7=old_public_age,alternative48=new_public_age,offered_scope='SOURCE_IDENTITY_NOT_SUPPLIED'if offered is None else 'FIXED_BOUND_OFFERED_PLAYER_GAMES_NO_OUTCOMES',
            offered_old7=None,
            offered_alternative48=None if offered is None else dict(ordinary=timing.age_summary(ages48['ordinary'],'ordinary',offered),profile=timing.age_summary(ages48['profile'],'profile',offered)))
        # Old age bytes are recoverable; if offered metadata is present, restore
        # only that small audit, never model or target labels.
        if offered is not None:
            old_ages=json.loads(gzip.decompress(store.read(old_age_ref['id'],old_age_ref['sha256'])))
            public_ages['offered_old7']=dict(ordinary=timing.age_summary(old_ages['ordinary'],'ordinary',offered),profile=timing.age_summary(old_ages['profile'],'profile',offered))
        public_age_ref=put('SOURCE_AGE_AGGREGATES_V1.json',enc(public_ages))
        binding=put('ALIGNED_PREPARATION_BINDING_V1.json',enc(dict(version=VERSION,UTC=now(),source_binding=source_binding,source_audit=audit,
            old_parity=parity,training=train_ref,query=query_ref,old_age=old_age_ref,alternative_age=new_age_ref,age_aggregates=public_age_ref,
            own_base_source_projection=projection_used,projection_prefit_cases=projection_checks,query_batch_resources=STATE['query_progress'],
            policy=dict(training=train_policy,query=query_policy,context=history_policy),withheld_source_games=14,
            learner='same fixed RB Leaf-CDF; base30 or base30+9support+89player/offense; no newdefense/interactions/role/gate/tuning',
            query_rows=1364,intended_rows=1366,two_unmapped_W8_identities='Original unavailable profiles preserved; never invented new identities')))
        check(time.process_time()+plan['resources']['pre_fit_CPU_reserve_seconds']<1480,'aligned preparation complete; insufficient remaining measured fit/persistence reserve, no fits consumed')
        STATE['phase']='TWO_REGISTERED_FITS'
        models={};fit_resources={}
        for fit_slot,(arm,block)in enumerate([(ARMS[2],'R0'),(ARMS[3],'R2')],1):
            category=increment.arm_category(data['category'],block,modeled_roles=['RB'])
            store.reserve(plan['resources']['model_reservation_bytes'])
            put('FIT_'+str(fit_slot)+'_CONSUMED.json',enc(dict(UTC=now(),arm=arm,fit_slot=fit_slot,maximum_new_fits=2,no_retry=True)))
            STATE['fits_attempted']+=1;beg=time.process_time()
            with threadpool_limits(limits=2):model=cdf.LeafCDFModel.fit(train,category,'base')
            used=time.process_time()-beg;STATE['fit_CPU_seconds']+=used;STATE['fits_returned']+=1;STATE['pending_model']=model
            stream=io.BytesIO();joblib.dump(model,stream,compress=('xz',3));STATE['pending_model_bytes']=stream.getvalue()
            model_ref=put('MODEL_2026_'+arm+'.joblib',STATE['pending_model_bytes'])
            store.read(model_ref['id'],model_ref['sha256']);STATE.pop('pending_model',None);STATE.pop('pending_model_bytes',None)
            models[arm]=model_ref;fit_resources[arm]=dict(fit_CPU_seconds=used,supported_played_training_rows=model.audit['supported_played_training_rows'],modeled_training_rows=model.audit['modeled_training_rows'])
            check(model.audit['training_rows']==14644 and model.audit['modeled_training_rows']==10527,'training target/role population differs')
            check(STATE['fit_CPU_seconds']<=1200,'fit-only ceiling exceeded; returned model already retained')
            STATE['phase']='INFERENCE_'+arm
            rows=carry.cdf_forecasts(model,query,arm,np)
            for row in rows:
                row.update(target='rush_yd',point_semantics='EXACT_LAW_MEAN_AND_LOWER_MEDIAN_SEPARATE',conditioning='CONDITIONAL_ON_PLAYED',original_issued_UTC=None,
                    reconstruction=timing.ALTERNATIVE,probability_admission='UNVALIDATED_LAW_NOT_CALIBRATED_CONFIDENCE',source_clock_semantics='CONSERVATIVE_TRANSFORM_GUARD; actual consumed own/base/profile ages retained separately')
            forecast=put('FORECAST_2026_'+arm+'.json.gz',gzip.compress(enc(rows),mtime=0))
            parts.append(dict(ref=forecast,procedure_alias=arm,original_arm=arm,rows=len(rows),reuse='NEW_ALIGNED_POLICY_FIT_AND_INFERENCE'))
        manifest=dict(format='IMMUTABLE_ALIAS_PART_MANIFEST_V1',version=VERSION,arm_order=ARMS,parts=parts,rows=5456,query_rows=1364,
            note='F0/F1 refer to exact old PRIMARY bytes unchanged; aliases are provenance, not a new forecast. F2/F3 are new reconstructed48h outputs; not genuine historical issue.')
        frozen=put('ALL_FOUR_TIMING_FORECAST_PARTS_BEFORE_GRADING_V1.json.gz',gzip.compress(enc(manifest),mtime=0))
        receipt=dict(version=VERSION,state='FROZEN_TWO_NEW_ALIGNED_TIMING_ARMS_AND_TWO_SAVED_BASELINES_UNSCORED',UTC=now(),fits_attempted=STATE['fits_attempted'],fits_returned=STATE['fits_returned'],
            new_fits=2,original_refits=0,old_model_loads=0,old_model_inference=0,models=models,fit_resources=fit_resources,forecasts=frozen,forecast_rows=5456,query_rows=1364,intended_rows=1366,
            prepared_binding=binding,original_input_parity=parity,source_age_aggregates=public_ages,artifacts=STATE['artifacts'],scoring='NOT_EXECUTED_SEPARATE_PINNED_COMMON_SCORER_STAGE',
            current_packet='NONE_HISTORICAL_RECONSTRUCTION_ONLY',resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,fit_CPU_seconds=STATE['fit_CPU_seconds']),
            storage=store.checkpoint(),counts=dict(new_source_HTTP=0,new_current_captures=0,new_grades=0,production_writes=0,unsafe_peer_models_loaded=0))
        put('FRESHNESS_EXECUTION_RECEIPT_V1.json',enc(receipt))
        with args.public_receipt.open('xb')as f:f.write(enc(receipt));f.flush();os.fsync(f.fileno())
        print(json.dumps(dict(state=receipt['state'],forecasts=frozen,new_fits=2,old_refits=0,new_grades=0)))
    except BaseException as error:
        failure=dict(version=VERSION,state='FAILED_WITH_NO_AUTOMATIC_RETRY',UTC=now(),phase=STATE['phase'],fits_attempted=STATE['fits_attempted'],fits_returned=STATE['fits_returned'],fit_CPU_seconds=STATE['fit_CPU_seconds'],
            error_type=type(error).__name__,error_sha256=sha(str(error).encode()),artifacts=STATE['artifacts'],query_batch_resources=STATE.get('query_progress',[]),CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start)
        if STATE.get('pending_model')is not None:
            try:
                if 'pending_model_bytes'not in STATE:
                    b=io.BytesIO();joblib.dump(STATE['pending_model'],b,compress=('xz',3));STATE['pending_model_bytes']=b.getvalue()
                put('RETURNED_MODEL_FAILURE.joblib',STATE['pending_model_bytes'],failure=True)
            except BaseException as e:failure['returned_model_retention_error_type']=type(e).__name__
        try:put('FAILURE_PRIVATE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json',enc(dict(failure,traceback=traceback.format_exc())),failure=True)
        finally:print(json.dumps(failure))
        raise
    finally:signal.alarm(0)

def main():
    p=argparse.ArgumentParser()
    for n in ['protocol','root-go','publication-receipt','public-receipt']:p.add_argument('--'+n,type=Path,required=True)
    for n in ['protocol-sha256','root-go-sha256','publication-receipt-sha256']:p.add_argument('--'+n,required=True)
    a=p.parse_args();check(not a.public_receipt.exists(),'immutable public receipt exists');run(authorize(a),a)
if __name__=='__main__':main()
