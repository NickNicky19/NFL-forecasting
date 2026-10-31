"""Conditional reuse or necessary fixed HGB cells; no execution on import.

Historical 2026 query inference only. No scoring, target-week labels, network,
operational exporter, production change or claimed prospective issuance.
"""
from __future__ import annotations
import argparse,copy,hashlib,importlib.util,io,json,os,resource,signal,sys,time
from pathlib import Path

VERSION='matched12-missing-hgb-cells-v1'
ROOT=Path(__file__).resolve().parents[1]
TARGETS=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rec','rec_yd','rush_rec_yd']
HGB_SHA='c5bf8ef481c05027a2a1d4e1d19764920c0820f0614f60736826c17526e7799d'
KEY=['season','week','game_id','player_id']
CAP=16*1024**2

def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(x):
 def scalar(v):
  if type(v).__module__=='numpy' and hasattr(v,'item'):return v.item()
  raise TypeError('unsupported metadata type '+type(v).__name__)
 return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,default=scalar).encode()
def exact(ref):
 p=Path(ref['path'])
 if not p.is_absolute() or p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('canonical nonsymlink source required')
 a=p.stat()
 if a.st_size!=ref['bytes'] or a.st_size>32*1024**2:raise ValueError('finite exact source size changed')
 body=p.read_bytes();b=p.stat()
 if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns) or sha(body)!=ref['sha256']:raise ValueError('source hash/identity changed')
 return body
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def safe(ref):return {k:ref[k] for k in ['bytes','sha256']}
def owner_validate(store,ref):
 p=Path(ref['path']);owners=[]
 for name,s in [('matched12',store),('complete_peer',store.complete_peer),('prior_forward',store.complete_peer.prior_forward),('legacy',store.legacy)]:
  if any(p.is_relative_to(Path(r)) for r in s._roots):owners.append((name,s))
 if len(owners)!=1:raise ValueError('exactly one actual registered input owner required')
 name,s=owners[0];v=s.validate_reference(p,ref['sha256'])
 if v['bytes']!=ref['bytes']:raise ValueError('owned source size changed')
 return {'owner':name,**safe(v)}
def aware_clock(series):
 import pandas as pd
 for v in series.dropna().drop_duplicates():
  if pd.Timestamp(v).tzinfo is None:raise ValueError('unknown source timezone cannot become fabricated UTC')
 return pd.to_datetime(series,utc=True,errors='raise')
def ordered(frame):return frame.sort_values(['kickoff_utc','game_id','player_id'],kind='stable').reset_index(drop=True)
def matrix_equal(a,b,columns):
 """Exact numeric representation used by FixedDesign, with explicit NaN equality."""
 import numpy as np
 import pandas as pd
 if len(a)!=len(b):return False
 a=ordered(a);b=ordered(b)
 for c in columns:
  if c not in a or c not in b:return False
  if c.startswith('f_') or c in TARGETS:
   if not np.array_equal(pd.to_numeric(a[c],errors='coerce').to_numpy(float),pd.to_numeric(b[c],errors='coerce').to_numpy(float),equal_nan=True):return False
  elif c.endswith('_utc'):
   if not aware_clock(a[c]).reset_index(drop=True).equals(aware_clock(b[c]).reset_index(drop=True)):return False
  elif not a[c].fillna('<NULL>').astype(str).reset_index(drop=True).equals(b[c].fillna('<NULL>').astype(str).reset_index(drop=True)):return False
 return True
def frame_bytes(f):
 b=io.BytesIO();f.to_parquet(b,index=False,compression='zstd');return b.getvalue()
def runtime_limits():
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 resource.setrlimit(resource.RLIMIT_CPU,(1800,1801));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('finite HGB subwave wall budget')));signal.alarm(2400)
 def no_network(event,args):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('zero network HGB source/inference wave')
 sys.addaudithook(no_network)

def execute(plan,go):
 started=time.monotonic();cpu=time.process_time()
 if (go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root' or go.get('worker_version')!=VERSION
  or go.get('worker_sha256')!=sha(Path(__file__).read_bytes()) or go.get('plan_canonical_sha256')!=sha(encoded(plan))):raise ValueError('separate exact source/matrix/restoration/fit root GO required')
 if plan['version']!=VERSION or [x['target'] for x in plan['cells']]!=TARGETS or len(plan['cells'])!=9:raise ValueError('only nine fixed registered HGB cells authorized')
 if plan['private_peak_bytes']!=CAP or plan['maximum_fits']!=9 or plan['maximum_restorations']!=9:raise ValueError('finite conditional budgets differ')
 for name,ref in plan['source_pins'].items():exact(ref)
 if plan['source_pins']['median_boosting']['sha256']!=HGB_SHA:raise ValueError('unchanged existing HGB recipe required')
 # Bind this repository's model classes before the retained storage helper can
 # put an older library directory ahead of it on sys.path.
 sys.path.insert(0,str(ROOT));import nfl_lab
 from nfl_lab import cdf_engine as cdf,median_boosting as hgb
 helper=load(plan['source_pins']['storage_helper']['path'],'matched12_hgb_storage')
 store,prepared=helper.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=helper.GO)
 with store.transaction():store._refresh();before=store._require(0)
 baseline=before['new_peer_physical_bytes'];slug=plan['output_slug']
 if not slug.startswith('matched12-hgb-') or '/' in slug or '..' in slug:raise ValueError('controlled finite fresh namespace required')
 out=store.forward_root/'research'/slug
 if out.exists():raise ValueError('consumed run exists; do not retry, overwrite or refund')
 out=store.register_root(out);refs={};written=0;fits=0;restores=0;fitted_estimators=0;forecast_rows=0;states=[]
 def put(name,body):
  nonlocal written
  if written+len(body)+65536>CAP:raise MemoryError('all retained model/forecast/receipt/failure bytes exceed subwave peak')
  store.write_bytes(out/name,body);r=store.validate_reference(out/name,sha(body));written+=len(body);refs[name]=r;return r
 def tick():return __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
 put('CONSUMED.json',encoded({'version':VERSION,'run_id':plan['run_id'],'state':'CONSUMED_BEFORE_TRAINING_QUERY_MODEL_DECODE','time_UTC':tick(),'plan_canonical_sha256':sha(encoded(plan)),'maximum_new_fit_calls':9,'maximum_model_restorations':9,'preserve_prior_budgets':True}))
 try:
  auth={k:owner_validate(store,plan[k]) for k in ['training_features','old_training_features','query_features','schedule','old_registry']}
  old_registry=json.loads(exact(plan['old_registry']))
  if old_registry['inputs']['training_features']!=plan['old_training_features']:raise ValueError('old original registry/source lineage differs')
  config=json.loads(exact(plan['categories']));categories={t:dict(config['categories'][t],target=t) for t in TARGETS}
  for c in categories.values():cdf.validate_category(c)
  import numpy as np,pandas as pd,pyarrow.parquet as pq,joblib,sklearn,scipy,threadpoolctl
  cut=pd.Timestamp(plan['training_cutoff_utc'])
  if cut.tzinfo is None or cut!=pd.Timestamp('2026-09-01T00:00:00Z'):raise ValueError('frozen pre2026 annual cutoff required')
  schedule=pd.read_csv(io.BytesIO(exact(plan['schedule'])),usecols=['season','game_id','game_type'])
  if schedule.game_id.isna().any() or schedule.game_id.duplicated().any():raise ValueError('unique schedule identities required')
  regular=set(schedule.loc[schedule.season.between(2019,2025)&schedule.game_type.eq('REG'),'game_id'])
  context=KEY+['team','opponent','position','kickoff_utc','cutoff_utc','outcome_available_utc','feature_max_source_available_utc','participation_state']
  feature_names=sorted({f for c in categories.values() for f in c['panels']['base']})
  columns=list(dict.fromkeys(context+TARGETS+['rush_att']+feature_names))
  def read_history(ref):
   raw=exact(ref);schema=pq.ParquetFile(io.BytesIO(raw)).schema_arrow
   for c in ['kickoff_utc','cutoff_utc','outcome_available_utc','feature_max_source_available_utc']:
    if not str(schema.field(c).type).endswith('tz=UTC]'):raise ValueError('history aware clock schema changed')
   return pq.read_table(io.BytesIO(raw),columns=columns,filters=[('season','>=',2019),('season','<=',2025)],use_threads=False).to_pandas()
  raw=read_history(plan['training_features']);old=read_history(plan['old_training_features'])
  def admit(f):
   k=aware_clock(f.kickoff_utc);a=aware_clock(f.outcome_available_utc)
   mask=f.game_id.isin(regular)&a.notna()&(a<cut)&k.notna()&(k<cut)
   return ordered(f.loc[mask].copy()),{'source_2019_2025_rows':len(f),'REG_before_cutoff_rows':int(mask.sum()),'nonREG_or_unmapped_rows':int((~f.game_id.isin(regular)).sum()),'unknown_availability_rows':int(a.isna().sum()),'not_earlier_kickoff_or_availability_rows':int((~(k.notna()&a.notna()&(k<cut)&(a<cut))).sum())}
  train,admission=admit(raw);old_eligible,old_admission=admit(old)
  if not len(train):raise ValueError('no admitted training rows')
  cdf.assert_clock_contract(train)
  query_columns=KEY+['team','opponent','position','kickoff_utc','cutoff_utc','feature_max_source_available_utc']+feature_names
  schema=pq.ParquetFile(io.BytesIO(exact(plan['query_features']))).schema_arrow
  query_columns=[c for c in dict.fromkeys(query_columns) if c in schema.names]
  query=pq.read_table(io.BytesIO(exact(plan['query_features'])),columns=query_columns,use_threads=False).to_pandas()
  if not (query.season.eq(2026)&query.week.between(1,7)).all() or query[KEY].isna().any(axis=None) or query.duplicated(KEY).any():raise ValueError('complete unique fixed2026W1-7 query population required')
  for c in ['kickoff_utc','cutoff_utc','feature_max_source_available_utc']:query[c]=aware_clock(query[c])
  if query.cutoff_utc.isna().any() or (query.cutoff_utc<cut).any() or (query.cutoff_utc>query.kickoff_utc).any():raise ValueError('query cutoff incompatible with annual training')
  bad=query.feature_max_source_available_utc.notna()&(query.feature_max_source_available_utc>=query.cutoff_utc)
  if bad.any():raise ValueError('query feature chronology violation')
  query['participation_state']='unknown';query['outcome_available_utc']=pd.NaT
  cdf.assert_clock_contract(query)
  versions={'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':__import__('pyarrow').__version__,'sklearn':sklearn.__version__,'scipy':scipy.__version__,'joblib':joblib.__version__,'threadpoolctl':threadpoolctl.__version__}
  for package,value in plan['expected_environment'].items():
   if versions.get(package)!=value:raise ValueError('exact existing runtime differs: '+package)
  put('SOURCE_ADMISSION.json',encoded({'inputs':auth,'accepted':admission,'old':old_admission,'training_seasons':sorted(map(int,train.season.unique())),'max_training_available_UTC':aware_clock(train.outcome_available_utc).max().isoformat(),'query_rows':len(query),'query_targets_decoded':False,'environment':versions,'original_seven_day_assumption':'PRESERVED_NOT_REPAIRED_BY_THIS_WAVE'}))
  for cell in plan['cells']:
   target=cell['target'];category=categories[target];slot={'target':target,'method':'HGB_MAE_DIRECT','cell_id':cell['cell_id'],'state':'STARTED','fit_call_consumed':False,'actual_estimator_fitted':False};states.append(slot)
   put(target+'/CELL_START.json',encoded({**slot,'time_UTC':tick(),'source_training_sha256':plan['training_features']['sha256'],'original_model_source_sha256':plan['old_training_features']['sha256']}))
   try:
    cdf.assert_composite_contract(train,category)
    owner_validate(store,cell['retained_manifest']);old_manifest=json.loads(exact(cell['retained_manifest']))
    if old_manifest['sha256']!=cell['retained_model']['sha256'] or old_manifest['category']!=category or old_manifest['panel']!='base' or old_manifest['audit']['design']['parameters']!=hgb.PARAMETERS:raise ValueError('old method/configuration identity differs')
    used=list(dict.fromkeys(context+[target]+category['panels']['base']))
    eligible_old_all=len(old)==len(old_eligible)
    same=eligible_old_all and matrix_equal(train,old,used)
    comparison={'state':'EXACT_QUALIFIED_MATRIX_MATCH' if same else 'DIFFERENT_TRAINING_POPULATION_OR_MODEL_USED_VALUES','old_full_source_eligible_for_new_REG_cutoff':eligible_old_all,'accepted_rows':len(train),'old_full_rows':len(old),'old_qualified_rows':len(old_eligible),'columns':used,'target':target,'new_fits':0,'source_inputs_identical_bytes':plan['training_features']['sha256']==plan['old_training_features']['sha256']}
    put(target+'/SOURCE_EQUIVALENCE.json',encoded(comparison))
    if same:
     owner_validate(store,cell['retained_model']);restores+=1
     if restores>9:raise RuntimeError('restoration allocation exhausted')
     put(target+'/RESTORE_START.json',encoded({'state':'MODEL_RESTORATION_ATTEMPT_CONSUMED','attempt':restores,'artifact':safe(cell['retained_model']),'time_UTC':tick()}))
     model=joblib.load(io.BytesIO(exact(cell['retained_model'])))
     if type(model) is not hgb.MedianBoostingModel or model.category!=category or model.panel!='base':raise ValueError('restored model typed/configuration identity mismatch')
     binding=model.prior_training_binding
     supported=train.loc[train.participation_state.eq('played')&cdf.valid_support(cdf.numeric(train,target),category['support'])]
     if binding is None or not matrix_equal(supported,binding,list(binding)):raise ValueError('retained actual training binding differs from admitted source')
     modeled=supported.loc[supported.position.isin(category['modeled_roles'])];modeled_binding=model.training_binding
     if modeled_binding is None or not matrix_equal(modeled,modeled_binding,list(modeled_binding)):raise ValueError('retained actual estimator binding differs from admitted source')
     if not binding.season.between(2019,2025).all() or not binding.game_id.isin(regular).all() or not (aware_clock(binding.outcome_available_utc)<cut).all():raise ValueError('retained actual binding violates season/period/cutoff')
     source='AUTHENTICATED_RETAINED_HGB_EQUIVALENT_SOURCE';model_ref=cell['retained_model']
    else:
     fits+=1
     if fits>9:raise RuntimeError('new fit allocation exhausted; no refund')
     slot['fit_call_consumed']=True
     slot['stage']='MODEL_FITTING'
     put(target+'/FIT_START.json',encoded({'state':'NEW_FIT_CALL_CONSUMED_BEFORE_FIT','attempt':fits,'time_UTC':tick(),'category':category,'parameters':hgb.PARAMETERS,'seed':1702,'threads':2,'training_cutoff_UTC':cut.isoformat()}))
     model=hgb.MedianBoostingModel.fit(train,category,'base')
     slot['actual_estimator_fitted']=model.audit.get('fit_state')=='FITTED';fitted_estimators+=int(slot['actual_estimator_fitted'])
     slot['stage']='MODEL_PERSISTENCE'
     buffer=io.BytesIO();joblib.dump(model,buffer,compress=3);model_ref=put(target+'/MODEL.joblib',buffer.getvalue());source='NEW_ACCEPTED_REG_SOURCE_HGB'
    q=query.loc[query.position.eq('QB') if target.startswith('pass_') else query.position.isin(['QB','RB','FB','WR','TE'])].copy()
    if not len(q):raise ValueError('no declared relevant query population')
    slot['stage']='HISTORICAL_QUERY_INFERENCE'
    frozen=hgb.prediction_rows(model,q);frozen['method']='HGB_MAE_DIRECT';frozen['product']='mae_objective_point';frozen['original_method_version']=hgb.VERSION
    procedure=sha(encoded({'family':'HGB_MAE_DIRECT','parameters':hgb.PARAMETERS,'source_training':plan['training_features']['sha256'],'category':category,'training_cutoff':cut.isoformat(),'source_policy':plan['source_policy_id']}))
    frozen['procedure_version']=procedure;frozen['issue_UTC']=tick();frozen['model_sha256']=model_ref['sha256'];frozen['source_policy_id']=plan['source_policy_id'];frozen['evidence_tier']='CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION'
    fref=put(target+'/FORECASTS.parquet',frame_bytes(frozen));forecast_rows+=len(frozen)
    slot.update(state='FROZEN_HISTORICAL_FORECASTS_NO_SCORES',source=source,procedure_version=procedure,forecasts=len(frozen),fallbacks=int(frozen.fallback.fillna('').ne('').sum()),model=safe(model_ref),forecast=safe(fref),training_binding_rows=len(model.prior_training_binding) if model.prior_training_binding is not None else 0,training_max_available_UTC=aware_clock(train.outcome_available_utc).max().isoformat(),fit_state=model.audit.get('fit_state'))
    put(target+'/MODEL_AUDIT.json',encoded({'category':category,'panel':'base','audit':model.audit,'source':source,'model':safe(model_ref),'accepted_training_source':safe(plan['training_features']),'retained_original_training_source':safe(plan['old_training_features']),'configuration_sha256':sha(encoded(category)),'environment':versions,'output_contract':'MAE_OBJECTIVE_POINT_HEURISTIC; NOT_EXPECTED_MEAN,INTEGER_LAW_MEDIAN,PMF_OR_THRESHOLD_PROBABILITY','restoration_of_new_artifact':'NOT_YET_FRESH_PROCESS_VERIFIED'}))
    put(target+'/CELL_COMPLETE.json',encoded(slot));del model
   except BaseException as error:
    slot.update(state='FAILED_OR_INTERRUPTED_RETAINED',error_type=type(error).__name__,error_sha256=sha(str(error).encode()))
    put(target+'/CELL_FAILURE.json',encoded({**slot,'private_error':str(error),'time_UTC':tick()}))
    if isinstance(error,(KeyboardInterrupt,SystemExit,TimeoutError)):raise
  usage=store.verify_retained_checkpoint()
  if usage['new_peer_physical_bytes']-baseline>CAP:raise MemoryError('actual private checkpoint peak exceeded')
  result={'version':VERSION,'run_id':plan['run_id'],'state':'COMPLETED_WITH_RETAINED_FAILURES' if any(s['state'].startswith('FAILED') for s in states) else 'FROZEN_PREDICTIONS_COMPLETE_UNSCORED','cells':states,'new_fit_calls_consumed':fits,'actual_fitted_estimators':fitted_estimators,'model_restorations_attempted':restores,'forecast_output_rows':forecast_rows,'new_scoring_runs':0,'source_admission':{'accepted':admission,'old':old_admission},'private_artifacts':{k:safe(v) for k,v in refs.items()},'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'local_retained_checkpoint':'PASS','offhost_and_fresh_process_restore':'NOT_VERIFIED','production_and_genuine_pregame_capture':'NONE','source_policy_id':plan['source_policy_id'],'limitations':['All2026W1-7 predictions are new historical reconstruction, not original issuance.','Old source/evidence preserved; mismatched training matrices use separately identified accepted-REG-source fits.','Conditional-on-played output has no numeric distribution or prop-probability contract.','Original seven-day availability assumption remains an assumption.']}
  put('COMPLETE.json',encoded(result));store.verify_retained_checkpoint();return result
 except BaseException as error:
  failure={'version':VERSION,'run_id':plan['run_id'],'state':'WAVE_FAILED_RETAINED','error_type':type(error).__name__,'error_sha256':sha(str(error).encode()),'new_fit_calls_consumed':fits,'actual_fitted_estimators':fitted_estimators,'model_restorations_attempted':restores,'cells':states,'forecast_output_rows':forecast_rows}
  try:put('WAVE_FAILURE.json',encoded({**failure,'private_error':str(error)}));store.verify_retained_checkpoint()
  except BaseException:pass
  return failure

def fictional_checks():
 import pandas as pd
 f=pd.DataFrame([{'season':2020,'week':1,'game_id':'FICTION','player_id':'FICTION','kickoff_utc':'2020-09-01T00:00:00Z','position':'RB','participation_state':'played','rec':0.,'f_prior':float('nan')}])
 assert matrix_equal(f,f.copy(),KEY+['position','participation_state','rec','f_prior']);n=1
 b=f.copy();b['rec']=1.;assert not matrix_equal(f,b,KEY+['rec']);n+=1
 b=f.copy();b['participation_state']='unknown';assert not matrix_equal(f,b,KEY+['participation_state']);n+=1
 try:execute({}, {})
 except ValueError as e:assert str(e).startswith('separate exact source');n+=1
 else:raise AssertionError('missing GO opened source')
 return {'state':'PASS','fictional_checks':n,'NFL_row_decodes':0,'fits':0,'model_restorations':0,'inference':0,'store_opens':0}

def configuration_from_registered_inputs(old_registry_ref):
 """Metadata-only private plan builder. Caller persists privately, never publics refs."""
 import importlib.metadata as metadata
 def ref(path):
  p=Path(path);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
 old=json.loads(exact(old_registry_ref));oldroot=Path(old_registry_ref['path']).parent
 current=json.loads((ROOT/'config/category-topfive-matched12-inference-v1.json').read_text())
 training=json.loads((ROOT/'config/weekly-future-training-v3.json').read_text())
 cells=[]
 for target in TARGETS:
  parent=oldroot/'trials'/target/'base'/'website_week6'/'model';mf=ref(parent/'manifest.json');m=json.loads(exact(mf));artifact=parent/m['artifact']
  cells.append({'target':target,'cell_id':target+'__HGB_MAE_DIRECT_ACCEPTED_REG_V1','retained_manifest':mf,'retained_model':{'path':str(artifact),'bytes':artifact.stat().st_size,'sha256':m['sha256']}})
 pins={name:ref(ROOT/path) for name,path in {'worker':'tools/category_topfive_matched12_missing_fit_v1.py','storage_helper':'tools/category_topfive_matched12_storage_v1.py','storage_module':'nfl_lab/category_topfive_matched12_storage_v1.py','median_boosting':'nfl_lab/median_boosting.py','cdf_engine':'nfl_lab/cdf_engine.py','data':'nfl_lab/data.py'}.items()}
 return {'version':VERSION,'run_id':'MATCHED12-HGB-CONDITIONAL-SOURCE-V1','output_slug':'matched12-hgb-conditional-v1','allocation_sha256':current['allocation_sha256'],'private_peak_bytes':CAP,'maximum_fits':9,'maximum_restorations':9,
  'training_features':training['features'],'old_training_features':old['inputs']['training_features'],'old_registry':old_registry_ref,'query_features':current['features'],'schedule':training['schedule'],'categories':training['categories'],'source_pins':pins,'cells':cells,'training_cutoff_utc':'2026-09-01T00:00:00Z',
  'source_policy_id':'MATCHED12_ACCEPTED_2019_2025_REG_AND_QUALIFIED_RECENT_HISTORY_C_STREAM_V1','expected_environment':{k:metadata.version(k) for k in ['numpy','pandas','pyarrow','scipy','joblib','threadpoolctl']}|{'sklearn':metadata.version('scikit-learn')},
  'authority':'Separately reviewed rootGO required for actual matrix source decode, conditionalrestoration and necessaryfixedfits. All prior spentfits/failures intact. Historical query inference only; no labels/scoring/HTTP/production.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--fictional-check',action='store_true');ap.add_argument('--plan',type=Path);ap.add_argument('--plan-sha256');ap.add_argument('--go',type=Path);ap.add_argument('--go-sha256');a=ap.parse_args();sys.dont_write_bytecode=True
 if a.fictional_check:print(encoded(fictional_checks()).decode());return
 if None in [a.plan,a.plan_sha256,a.go,a.go_sha256]:ap.error('exact plan and GO required')
 runtime_limits();p=json.loads(exact({'path':str(a.plan),'bytes':a.plan.stat().st_size,'sha256':a.plan_sha256}));g=json.loads(exact({'path':str(a.go),'bytes':a.go.stat().st_size,'sha256':a.go_sha256}));r=execute(p,g);print(encoded(r).decode(),flush=True);signal.alarm(0)
 if r['state'] in ['WAVE_FAILED_RETAINED','COMPLETED_WITH_RETAINED_FAILURES']:raise SystemExit(1)
if __name__=='__main__':main()
