"""Complete the missing 2025 BASE law comparator without refitting ORDERED.

Full original 2025 query contexts are inferred in the exact original cutoff,
role, warm-state and inner256 partitions. Primary roles are extracted afterward.
Original points, labels and ORDERED proper-score vectors stay unchanged.
"""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,io,json,math,os,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='opportunity-2025-base-ordered-proper-completion-v2-original-partition'
KEY=['season','week','game_id','player_id']
TARGETS=('rush_att','rec')
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def need(x,m):
 if not x:raise ValueError(m)
def exact(r):
 p=Path(r['path']);a=p.stat();need(p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in [p,*p.parents]),'canonical exact source required');need(a.st_size==r['bytes']<=16*1024**2,'source size differs');b=p.read_bytes();z=p.stat();need(sha(b)==r['sha256'] and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns),'source bytes changed');return b
def safe(r):return {k:r[k] for k in ['bytes','sha256']}
def pack(entries):
 b=io.BytesIO();manifest={k:{'bytes':len(v),'sha256':sha(v)} for k,v in entries.items()}
 with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for k,v in {**entries,'MEMBER_MANIFEST.json':enc(manifest)}.items():z.writestr(k,v)
 return b.getvalue(),manifest
def parquet(f):
 import pyarrow as pa,pyarrow.parquet as pq
 b=io.BytesIO();pq.write_table(pa.Table.from_pandas(f,preserve_index=False,nthreads=1),b,compression='zstd');return b.getvalue()
def execute(cfg,go):
 S=time.monotonic();C=time.process_time();model_loads=model_load_attempts=query_passes=query_completed=fixture_rows=0;stage='EXACT_BINDINGS'
 need(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root' and go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('configuration_sha256')==sha(enc(cfg)),'exact root and independent GO required')
 need(cfg['version']==VERSION and cfg['new_fits']==0 and cfg['maximum_model_loads']==2 and cfg['maximum_query_law_rows']==40000,'finite scientific contract changed')
 for r in cfg['source_pins'].values():exact(r)
 sys.path.insert(0,str(ROOT));import nfl_lab
 need(Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab','root package binding differs')
 from tools import category_topfive_matched12_storage_v1 as storage
 from tools import category_topfive_matched12_law_scores_v1 as losses
 from nfl_lab.owned_reference_batch import validate_owned_references
 # Reuse the accepted original no-child bootstrap. RTLD_NOLOAD attaches only
 # the already mapped libc; it does not permit ldconfig or other child probes.
 import ctypes,threadpoolctl
 libc=Path(cfg['source_pins']['libc']['path']);need(Path(threadpoolctl.__file__).resolve()==Path(cfg['source_pins']['threadpoolctl']['path']),'threadpool source binding differs')
 mapped={str(Path(z[5]).resolve()) for line in Path('/proc/self/maps').read_text().splitlines() if len(z:=line.split())==6 and z[5].startswith('/')}
 need(str(libc) in mapped and hasattr(os,'RTLD_NOLOAD'),'accepted libc is not already mapped')
 handle=ctypes.CDLL(str(libc),mode=os.RTLD_NOLOAD);previous=threadpoolctl.ThreadpoolController._system_libraries.get('libc');need(previous is None or previous._handle==handle._handle,'threadpool libc handle differs');threadpoolctl.ThreadpoolController._system_libraries['libc']=handle
 from nfl_lab import cdf_engine as cdf,weekly_future_inference as future
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq,joblib
 from sklearn.ensemble import ExtraTreesRegressor
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 def reject_fit(*a,**k):raise RuntimeError('NO_NEW_FIT_IN_PROPER_SCORE_COMPLETION')
 ExtraTreesRegressor.fit=reject_fit;cdf.LeafCDFModel.fit=classmethod(reject_fit);cdf.FixedDesign.fit=classmethod(reject_fit)
 store,_=storage.open_store(ROOT,allocation_sha256=cfg['allocation_sha256'],root_go=storage.GO,readonly=True)
 refs=list(cfg['owned_inputs'].values());unique={r['path']:r for r in refs};seen=set();owned=[]
 for owner in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]:
  items={r['path']:r['sha256'] for r in unique.values() if any(Path(r['path']).is_relative_to(Path(x)) for x in owner._roots)}
  need(not seen.intersection(items),'ambiguous original owner')
  if items:
   got,a=validate_owned_references(owner,items);seen.update(got);owned.append({'references':len(got),'full_scans':a['full_scan_calls']})
 need(seen==set(unique),'all inputs require original managed ownership')
 slug=cfg['run_id'];need(slug.startswith('matched12-2025-base-ordered-proper-v2-') and '/' not in slug and '..' not in slug,'fresh historical namespace required');out=store.forward_root/'research'/slug;need(not out.exists(),'consumed execution must not rerun');store.register_root(out);used=0;artifacts={}
 def put(name,body,terminal=False):
  nonlocal used
  need(used+len(body)+cfg['external_metadata_charge_bytes']+(0 if terminal else 262144)<=cfg['private_retained_bytes'],'complete evidence allocation exhausted')
  store.write_bytes(out/name,body);used+=len(body);r=store.validate_reference(out/name,sha(body));artifacts[name]=safe(r);return safe(r)
 def actual():return {'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'BASE_model_load_attempts':model_load_attempts,'restored_BASE_models':model_loads,'query_law_rows_attempted':query_passes,'query_law_rows_completed':query_completed,'fixture_query_rows_attempted':fixture_rows,'new_fits':0,'new_ORDERED_inference':0,'HTTP':0}
 def resources():
  a=actual();need(all(a[k]<=cfg['resources'][k] for k in ['CPU_seconds','wall_seconds','RSS_bytes']) and query_passes+fixture_rows<=cfg['maximum_query_law_rows'] and model_loads<=2,'resource envelope exceeded; retained evidence remains');return a
 put('STARTED.json',enc({'state':'STARTED_BEFORE_QUERY_AND_OUTCOME_DECODE','version':VERSION,'worker_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'resources':cfg['resources'],'new_fits':0}))
 put('CONFIGURATION.json',enc(cfg))
 pending_replay=pending_scores=None
 bodies={}
 def member(source,name):
  r=cfg['owned_inputs'][source]
  if source not in bodies:bodies[source]=exact(r)
  with zipfile.ZipFile(io.BytesIO(bodies[source])) as z:
   need(len(z.namelist())==len(set(z.namelist())),'ambiguous source zip members');m=cfg['members'][source][name];need(z.getinfo(name).file_size==m['bytes']<=16*1024**2,'member size differs');b=z.read(name)
  need(sha(b)==m['sha256'],'member hash differs');return b
 def table(b):return pq.read_table(io.BytesIO(b),use_threads=False).to_pandas(use_threads=False)
 def clocks(f,columns):
  for c in columns:
   for value in f[c].dropna().unique():
    t=pd.Timestamp(value);need(t.tzinfo is not None and t.utcoffset() is not None,'naive clock must not become a fabricated UTC clock')
   f[c]=pd.to_datetime(f[c],utc=True,errors='raise')
  return f
 def aligned(a,b):
  need(not a.duplicated(KEY).any() and not b.duplicated(KEY).any(),'duplicate original opportunity');x=a.merge(b,on=KEY,how='outer',validate='one_to_one',suffixes=('_a','_b'),indicator=True);need(x._merge.eq('both').all(),'original comparison population differs');return x
 try:
  spec=importlib.util.spec_from_file_location('original_modern_CDF_completion',cfg['source_pins']['original_CDF_completion']['path']);original_CDF=importlib.util.module_from_spec(spec);spec.loader.exec_module(original_CDF)
  stage='ORIGINAL_SOURCE_AND_QUERY_METADATA'
  original_plan=json.loads(member('original_freeze','PLAN.json'));need(sha(enc(original_plan))==cfg['original_plan_canonical_sha256'],'original scientific plan differs')
  proof=json.loads(member('original_freeze','TRAINING_SOURCE_PROOF.json'));need(proof['expected_training_frame_sha256']==cfg['training_frame_sha256'] and proof['train_years']==list(range(2019,2025)) and proof['training_cutoff_utc']==cfg['training_cutoff_utc'] and pd.Timestamp(proof['training_max_available_utc'])<pd.Timestamp(cfg['training_cutoff_utc']),'earlier-only training provenance differs')
  audits=json.loads(member('original_freeze','MODEL_AUDITS.json'));query=table(member('original_freeze','PREPARED_QUERY.parquet'));frozen=table(member('original_freeze','FORECASTS.parquet'));clocks(query,['kickoff_utc','cutoff_utc','feature_max_source_available_utc']);clocks(frozen,['kickoff_utc','cutoff_utc'])
  need(len(query)==8701 and query.season.eq(2025).all() and set(query.week)==set(range(1,19)) and query.game_id.nunique()==272 and not query.duplicated(KEY).any(),'original complete query population differs');need((query.cutoff_utc<=query.kickoff_utc).all() and (query.feature_max_source_available_utc.isna()|(query.feature_max_source_available_utc<=query.cutoff_utc)).all(),'source feature freshness violation')
  models={};prepared={};replays=[];manifest_summaries={}
  stage='TWO_EARLIER_FOLD_BASE_MODEL_RESTORATIONS'
  for target in TARGETS:
   for name in ['model_'+target,'manifest_'+target]:need(original_plan['inputs'][name]==cfg['owned_inputs'][name],'input differs from original completed study')
   manifest=json.loads(exact(cfg['owned_inputs']['manifest_'+target]));need(manifest['schema_version']==future.VERSION and manifest['artifact_kind']=='TRAINED_FUTURE_QUERY_NOT_HISTORICAL_REPLAY' and manifest['family']=='leaf_cdf_base' and manifest['category']['target']==target and manifest['category']['support']=='count','wrong original BASE contract');need(manifest['model']==cfg['owned_inputs']['model_'+target] and manifest['environment']==future.environment() and manifest['code_pins']==future.code_pins(),'trained code/environment/model binding differs');need(manifest['training_cutoff_utc']==cfg['training_cutoff_utc'] and manifest['training_frame_sha256']==cfg['training_frame_sha256'] and pd.Timestamp(manifest['training_max_available_utc'])<pd.Timestamp(cfg['training_cutoff_utc']),'wrong earlier fold')
   model_load_attempts+=1;bundle=joblib.load(io.BytesIO(exact(cfg['owned_inputs']['model_'+target])));model_loads+=1;model=bundle['model'];need(future.model_contract(model,'leaf_cdf_base')==(manifest['category'],manifest['features']) and model.audit==audits[target]['BASE_CDF_CACHED']['audit'],'model schema/audit differs');need(model.forest.get_params()['n_jobs']==2,'original forest thread policy changed');need(future.frame_digest(bundle['fixture'])==manifest['replay_fixture_sha256'],'fixture source differs');fixture_rows+=len(bundle['fixture']);resources();bits=future.prediction_bits(model,'leaf_cdf_base',bundle['fixture']);need(bits==bundle['expected_bits'] and future.digest(bits)==manifest['replay_bits_sha256'],'exact original future fixture bits differ')
   columns=cfg['query_columns'][target];need(columns==list(dict.fromkeys(KEY+original_CDF.CONTEXT+['feature_max_source_available_utc']+manifest['features'])) and set(columns).isdisjoint(original_CDF.FORBIDDEN),'original predictor column contract differs')
   q=pq.read_table(io.BytesIO(exact(cfg['owned_inputs']['query'])),columns=columns,use_threads=False).to_pandas(use_threads=False).reset_index(drop=True);clocks(q,['kickoff_utc','cutoff_utc','feature_max_source_available_utc']);need(len(q)==8701 and q[KEY].equals(query[KEY]),'original complete query identities differ')
   warm=cdf.numeric(q,'f_player_games_prior')>0;available=q.feature_max_source_available_utc
   need(not (available.isna().to_numpy()&warm).any() and not (available.notna()&~available.lt(q.cutoff_utc)).any(),'original strict source freshness contract differs')
   for c in KEY+original_CDF.CONTEXT:need(q[c].equals(query[c]),'original raw/prepared context differs: '+c)
   for c in manifest['features']:need(np.array_equal(pd.to_numeric(q[c],errors='coerce').to_numpy(float),pd.to_numeric(query[c],errors='coerce').to_numpy(float),equal_nan=True),'original raw/prepared feature differs: '+c)
   need(int(q.position.isin(cfg['primary_roles'][target]).sum())==cfg['expected'][target]['planned'],'primary membership differs')
   base=frozen.loc[frozen.target.eq(target)&frozen.method.eq('BASE_CDF_CACHED')].copy();base=q[KEY].merge(base,on=KEY,validate='one_to_one');need(len(base)==len(q),'frozen BASE coverage differs')
   replay=q[KEY+original_CDF.CONTEXT].copy()
   for c in ['mean','median','derived_p10','derived_p90','derived_variance']:replay[c]=np.nan
   replay['fallback']='unvisited';replay['query_pass_completed']=False;pending_replay=(target,replay)
   delegated_CDF_calls=0;cutoff_groups=law_batches=0
   for cutoff,selected in q.groupby('cutoff_utc',sort=False):
    cutoff_groups+=1;query_passes+=len(selected);resources()
    for indices,law,fallback in model.predict_batches(selected,batch_size=256):
     positions=selected.index.to_numpy()[indices];need(not replay.loc[positions,'query_pass_completed'].any(),'duplicate law assignment');law_batches+=1;replay.loc[positions,'fallback']=fallback
     if law is not None:
      counter={};mean,median,calls=original_CDF.full_law_products(np,law,counter);delegated_CDF_calls+=calls;replay.loc[positions,'mean']=mean;replay.loc[positions,'median']=median
      replay.loc[positions,'derived_p10']=law.quantile(.1);replay.loc[positions,'derived_p90']=law.quantile(.9);replay.loc[positions,'derived_variance']=law.variance
     replay.loc[positions,'query_pass_completed']=True
    query_completed+=len(selected)
   need(replay.query_pass_completed.all(),'law omitted original query rows')
   diagnostics={}
   for c in ['mean','median']:
    a,b=replay[c].to_numpy(float),base[c].to_numpy(float);finite=np.isfinite(a)&np.isfinite(b);same_nan=np.isnan(a)&np.isnan(b);same_bits=np.zeros(len(a),bool);same_bits[finite]=a[finite].view(np.uint64)==b[finite].view(np.uint64);good=same_nan|same_bits
    diagnostics[c]={'mismatched_rows':int((~good).sum()),'matched_finite_rows':int(finite.sum()),'max_absolute_difference':float(np.max(np.abs(a[finite]-b[finite]))) if finite.any() else None,'max_ULP_difference':int(np.max(np.maximum(a[finite].view(np.uint64),b[finite].view(np.uint64))-np.minimum(a[finite].view(np.uint64),b[finite].view(np.uint64)))) if finite.any() and (a[finite]>=0).all() and (b[finite]>=0).all() else None}
    replay['original_reference_'+c]=base[c].to_numpy()
   diagnostics['fallback_mismatches']=int((replay.fallback.fillna('').astype(str)!=base.fallback.fillna('').astype(str)).sum());diagnostics['original_optional_products']={c:'UNAVAILABLE_NAN_PLACEHOLDER_NOT_REPRODUCED' if base[c].isna().all() else 'RETAINED_VALUES_REQUIRE_SEPARATE_GUARD' for c in ['p10','p90','variance']};diagnostics['new_derived_products']='derived_p10/derived_p90/derived_variance are new law summaries, not original captured values';diagnostics['partition']={'original_cutoff_group_sort':False,'roles_and_warm_state':'unchanged model.predict_batches','inner_batch_size':256,'full_query_rows':len(q),'cutoff_groups':cutoff_groups,'law_batches':law_batches,'delegated_CDF_calls':delegated_CDF_calls}
   body,member_hashes=pack({'BASE_POINT_REPLAY.parquet':parquet(replay),'OUTCOME_BLIND_DIAGNOSTICS.json':enc(diagnostics),'METHOD_BINDING.json':enc({'target':target,'model':safe(cfg['owned_inputs']['model_'+target]),'original_partition_source':safe(cfg['source_pins']['original_CDF_completion']),'labels_read':False,'new_fit':0})});point_ref=put('BASE_REPLAY_'+target+'.zip',body);pending_replay=None
   # Persist the produced vector, context and diagnostics BEFORE identity asserts.
   for c in ['mean','median']:need(diagnostics[c]['mismatched_rows']==0,'exact original partition BASE point bits differ: '+target+'/'+c)
   need(diagnostics['fallback_mismatches']==0,'saved BASE fallback differs')
   for c in ['p10','p90','variance']:need(base[c].isna().all(),'unexpected retained optional product: register its exact comparison before proceeding')
   models[target]=model;prepared[target]=(q,base,replay);manifest_summaries[target]={'model':safe(cfg['owned_inputs']['model_'+target]),'procedure_version':manifest['procedure_version'],'training_frame_sha256':manifest['training_frame_sha256'],'fit_clock_status':manifest['fit_clock_status'],'fixture_rows':len(bundle['fixture']),'original_mean_median_fallback_bits_equal':True,'derived_optional_products':'NEW_LAW_SUMMARIES_NOT_ORIGINAL_CAPTURE','point_replay':point_ref,'point_replay_members':member_hashes,'diagnostics':diagnostics}

  resources();put('BEFORE_OUTCOME_REPLAY.json',enc({'source_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'original_freeze':safe(cfg['owned_inputs']['original_freeze']),'base_models':manifest_summaries,'roles':cfg['primary_roles'],'labels_read':False,'new_fit_or_ORDERED_inference':0}))
  stage='SAME_ORIGINAL_LABELS_AND_REUSED_ORDERED_LAWS'
  old=table(member('original_grade','GRADED_ROWS.parquet'));clocks(old,['kickoff_utc','cutoff_utc']);need(len(old)==52206 and old.season.eq(2025).all(),'original grade scope differs');old_result=json.loads(member('original_grade','RESULT.json'));need(old_result['all_original_point_columns_bit_identical'] and old_result['evaluation_season']==2025,'original grade not admitted');scores=[];reports=[]
  def intervals(delta,groups):
   labels=np.asarray(groups.astype(str));blocks={v:np.flatnonzero(labels==v) for v in sorted(set(labels))};n=len(blocks)
   if n<2:return {'state':'UNAVAILABLE_FEWER_THAN_TWO_CLUSTERS','clusters':n}
   sums=np.asarray([float(np.sum(delta[v])) for v in blocks.values()]);sizes=np.asarray([len(v) for v in blocks.values()]);rng=np.random.default_rng(cfg['uncertainty']['seed']);values=[]
   for _ in range(cfg['uncertainty']['replicates']):
    take=rng.integers(0,n,n);values.append(float(sums[take].sum()/sizes[take].sum()))
   return {'state':'NOMINAL_EXPOSED_DEVELOPMENT','clusters':n,'seed':cfg['uncertainty']['seed'],'replicates':len(values),'lower':float(np.quantile(values,.025)),'upper':float(np.quantile(values,.975)),'two_target_Bonferroni_lower':float(np.quantile(values,.0125)),'two_target_Bonferroni_upper':float(np.quantile(values,.9875))}
  for target in TARGETS:
   stage='BASE_PROPER_SCORE_'+target;q,base,replay=prepared[target];g=old.loc[old.target.eq(target)&old.method.eq('BASE_CDF_CACHED')].copy();g=q[KEY].merge(g,on=KEY,validate='one_to_one');candidate=old.loc[old.target.eq(target)&old.method.eq('ORDERED_CDF')].copy();candidate=q[KEY].merge(candidate,on=KEY,validate='one_to_one');need(len(g)==len(candidate)==len(q),'grade coverage differs');need(g.participation_state.equals(candidate.participation_state) and np.array_equal(g.actual.to_numpy(float),candidate.actual.to_numpy(float),equal_nan=True),'candidate/control labels differ');need(not (g.participation_state.ne('played')&g.actual.notna()).any(),'unknown participation became zero')
   old_candidate=frozen.loc[frozen.target.eq(target)&frozen.method.eq('ORDERED_CDF')].copy();old_candidate=q[KEY].merge(old_candidate,on=KEY,validate='one_to_one')
   for c in ['mean','median','p10','p90','variance']:
    need(np.array_equal(base[c].to_numpy(float),g[c].to_numpy(float),equal_nan=True),'old BASE point changed while grading');need(np.array_equal(old_candidate[c].to_numpy(float),candidate[c].to_numpy(float),equal_nan=True),'old ORDERED point changed while grading')
   for original,graded in [(base,g),(old_candidate,candidate)]:
    need(original.fallback.fillna('').astype(str).equals(graded.fallback.fillna('').astype(str)),'original fallback changed while grading')
    for c in ['team','opponent','position','kickoff_utc','cutoff_utc']:need(q[c].equals(graded[c]) and original[c].equals(graded[c]),'original context differs: '+c)
   frame=q.copy();frame[target]=g.actual.to_numpy();frame['participation_state']=g.participation_state.to_numpy();scored=g.copy();scored['proper_query_pass_completed']=False
   for c in ['derived_p10','derived_p90','derived_variance']:scored[c]=replay[c].to_numpy()
   pending_scores=(target,scored)
   for cutoff,selected in frame.groupby('cutoff_utc',sort=False):
    query_passes+=len(selected);resources();fragment=cdf.score_frozen_rows(models[target],selected,g.loc[selected.index]);query_completed+=len(selected)
    for c in ['crps','log_score','cdf_actual','cdf_actual_below']:scored.loc[selected.index,c]=fragment[c].to_numpy()
    scored.loc[selected.index,'proper_query_pass_completed']=True
   body,score_members=pack({'BASE_PROPER_SCORES.parquet':parquet(scored),'SOURCE_BINDING.json':enc({'target':target,'model':safe(cfg['owned_inputs']['model_'+target]),'original_partition_source':safe(cfg['source_pins']['original_CDF_completion']),'new_fit':0,'source_primary_roles':cfg['primary_roles'][target]})});put('BASE_PROPER_'+target+'.zip',body);pending_scores=None
   need(scored.proper_query_pass_completed.all(),'proper-law pass missed source context')
   supported=g.participation_state.eq('played')&np.isfinite(g.actual.to_numpy(float));primary=q.position.isin(cfg['primary_roles'][target]);good=supported&primary;need(int(good.sum())==cfg['expected'][target]['supported'] and int(primary.sum())==cfg['expected'][target]['planned'],'original primary supported cohort differs');need(int(supported.sum())==cfg['expected_all_roles'][target]['supported'],'original all-role coverage differs');need(cdf.valid_support(g.loc[supported,'actual'].to_numpy(float),'count').all(),'invalid official count support');need(np.isfinite(scored.loc[supported,'crps']).all() and np.isfinite(candidate.loc[supported,'crps']).all(),'missing proper-score coverage cannot shrink cohort')
   for f,m in [(scored,'BASE_CDF_CACHED'),(candidate,'ORDERED_CDF')]:f['is_primary_evaluation_row']=f.position.isin(cfg['primary_roles'][target]).to_numpy();f['comparison_method']=m;f['comparison_version']=VERSION;scores.append(f)
   def summary(a,b):
    ca,co=np.asarray(a,float),np.asarray(b,float);delta=ca-co;answer={'paired':losses.paired_summary(ca,co),'improvement_percent':100*(float(co.mean())-float(ca.mean()))/float(co.mean()) if np.isfinite(ca).all() and np.isfinite(co).all() and float(co.mean()) else None}
    answer['intervals']={k:intervals(delta,g.loc[good,k]) for k in ['game_id','week']} if np.isfinite(delta).all() else {'state':'UNAVAILABLE_NONFINITE_PAIRED_DIFFERENCE_NO_ROWS_DROPPED'};return answer
   crps=summary(candidate.loc[good,'crps'],scored.loc[good,'crps']);nll=summary(candidate.loc[good,'log_score'],scored.loc[good,'log_score']);weekly=[]
   for week in range(1,19):
    take=good&g.week.eq(week);weekly.append({'week':week,'planned':int((g.week.eq(week)&primary).sum()),'supported':int(take.sum()),'ORDERED_CRPS':losses.loss_summary(candidate.loc[take,'crps']),'BASE_CRPS':losses.loss_summary(scored.loc[take,'crps']),'ORDERED_NLL':losses.loss_summary(candidate.loc[take,'log_score']),'BASE_NLL':losses.loss_summary(scored.loc[take,'log_score'])})
   reports.append({'target':target,'primary':'CRPS','population':{'planned':int(primary.sum()),'supported':int(good.sum()),'states':g.loc[primary,'participation_state'].value_counts().to_dict(),'played_missing':int((primary&g.participation_state.eq('played')&g.actual.isna()).sum()),'played_zero':int((good&g.actual.eq(0)).sum()),'games':int(q.loc[primary,'game_id'].nunique()),'weeks':int(q.loc[primary,'week'].nunique()),'BASE_fallback_planned':int(g.loc[primary,'fallback'].fillna('').ne('').sum()),'ORDERED_fallback_planned':int(candidate.loc[primary,'fallback'].fillna('').ne('').sum()),'inferred_full_original_context_rows':len(q),'secondary_all_role_supported':int(supported.sum())},'ORDERED_minus_BASE_CRPS':crps,'ORDERED_minus_BASE_NLL':nll,'weekly':weekly,'original_MAE_mean_results':'REUSED_UNCHANGED_FROM_ORIGINAL_2025_COMPLETED_STUDY_NOT_NEW_POINT_RESEARCH'})
  resources();stage='RESULT_PERSISTENCE';aggregate={'version':VERSION,'state':'COMPLETE_NEW_MATCHED_PROPER_SCORE_COMPARISON','training_seasons':list(range(2019,2025)),'evaluation':{'season':2025,'phase':'REG','weeks':list(range(1,19))},'products':{'primary':'FULL_COUNT_LAW_CRPS','secondary':'NEGATIVE_LOG_PMF_WITH_IMPOSSIBLE_EVENTS_RETAINED','offered_threshold_probabilities':'UNAVAILABLE_NO_QUALIFIED_2025_OFFERS_IN_THIS_WAVE'},'results':reports,'base_model_bindings':manifest_summaries,'source_freeze':safe(cfg['owned_inputs']['original_freeze']),'source_grade':safe(cfg['owned_inputs']['original_grade']),'reused_ORDERED_proper_rows':6861,'scientific_evidence':'EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION_ORIGINAL_SEVEN_DAY_ASSUMPTION','new_fits':0,'new_ORDERED_restoration_or_inference':0,'new_genuine_pregame_capture_or_release':0,'uncertainty':cfg['uncertainty'],'limitations':['Original incomplete participation and unknown-label contract preserved; this is not a current-source label repair.','No historical quote-time, price, EV, profit, website-relative or scientific-confirmation claim.','Original missing fit clocks are not invented; this laboratory replay does not pass future production admission.'],'actual_before_persistence':actual(),'owned_authentication':owned}
  body,members=pack({'AGGREGATES.json.gz':gzip.compress(enc(aggregate),mtime=0),'ALL_ORIGINAL_CONTEXT_LAW_SCORECARD.parquet':parquet(pd.concat(scores,ignore_index=True)),'RUN_STATE.json':enc({'worker_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'new_fits':0,'source_scores_reused_not_recreated':True})});result=put('RESULTS.zip',body);a=resources();receipt={'version':VERSION,'state':'COMPLETE_OWNED_NEW_2025_PROPER_SCORE_COMPARISON','result':result,'members':members,'actual_before_terminal':a,'source_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'new_fits':0,'offhost_restoration':'NOT_VERIFIED','production':'READ_ONLY_NO_RELEASE'};complete=put('COMPLETE.json',enc(receipt),terminal=True);a=resources();return {**receipt,'complete':complete,'actual':a,'postterminal_resource_admission':'PASS_AFTER_EXACT_MANAGED_READBACK','private_new_bytes':used}
 except BaseException as error:
  # Preserve every available produced vector even if a parity/score check fails.
  retained_pending={}
  for kind,pending in [('POINT_REPLAY',pending_replay),('PROPER_SCORES',pending_scores)]:
   if pending is not None:
    target,frame=pending
    try:
     body,_=pack({'AVAILABLE_'+kind+'.parquet':parquet(frame),'PARTIAL_STATE.json':enc({'target':target,'stage':stage,'completed_flag':'query_pass_completed' if kind=='POINT_REPLAY' else 'proper_query_pass_completed','helper_internal_unreturned_partial':'NOT_RECOVERED_OR_CLAIMED'})});retained_pending[kind]=put('FAILED_AVAILABLE_'+kind+'_'+target+'.zip',body)
    except BaseException as retention_error:retained_pending[kind]={'state':'NOT_RETAINED','error_type':type(retention_error).__name__}
  failure={'pending_output_retention':retained_pending,'version':VERSION,'state':'FAILED_RETAINED_NO_REFIT','stage':stage,'error_type':type(error).__name__,'error_sha256':sha(str(error).encode()),'private_error':str(error),'artifacts':artifacts,'actual':actual()}
  put('FAILURE.json',enc(failure),terminal=True);raise
def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--go',type=Path,required=True);p.add_argument('--go-sha256',required=True);a=p.parse_args()
 for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 cfg=json.loads(gzip.decompress(exact({'path':str(a.plan),'bytes':a.plan.stat().st_size,'sha256':a.plan_sha256})));go=json.loads(exact({'path':str(a.go),'bytes':a.go.stat().st_size,'sha256':a.go_sha256}));cap=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(cap['CPU_seconds'],cap['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(cap['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('finite historical completion wall limit')));signal.alarm(cap['wall_seconds']);sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('offline child-free research')) if e in ['socket.connect','socket.connect_ex','socket.getaddrinfo','subprocess.Popen','os.system','os.fork','os.posix_spawn'] else None);r=execute(cfg,go);print(enc(r).decode(),flush=True);signal.alarm(0)
if __name__=='__main__':main()
