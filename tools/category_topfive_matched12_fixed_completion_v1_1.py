"""Storage-only continuation: one durable reservation and one immutable cell ZIP."""
from __future__ import annotations
import argparse,gzip,hashlib,io,json,os,resource,signal,sys,time,types,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-fixed-completion-v1.1'
archive=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/fitting/FIXED13_SOURCE_V1.py.gz'
raw=archive.read_bytes()
if hashlib.sha256(raw).hexdigest()!='42c2167de38968ae915b64e966d55869d921e9dceea59878773d6ce2a8cd4d94':raise ValueError('frozen V1 source archive changed')
source=gzip.decompress(raw)
if hashlib.sha256(source).hexdigest()!='956eef8e397beda947902efe95eaaffa079b896401e45b7a2c9e166f85b750a9':raise ValueError('exact original V1 source changed')
old=types.ModuleType('matched12_frozen_unexecuted_fixed13_v1');old.__file__=str(ROOT/'tools/category_topfive_matched12_fixed_completion_v1.py')
exec(compile(source,old.__file__,'exec'),old.__dict__)
sha,encoded,exact,load,safe,own,parquet=old.sha,old.encoded,old.exact,old.load,old.safe,old.own,old.parquet
SPEC=old.SPEC

def read_owned(store,ref):
 if 'container' not in ref:own(store,ref);return exact(ref)
 own(store,ref['container'])
 with zipfile.ZipFile(io.BytesIO(exact(ref['container']))) as z:
  info=z.getinfo(ref['member'])
  if info.file_size!=ref['bytes'] or info.file_size>24*1024**2:raise ValueError('bounded exact artifact member required')
  b=z.read(info)
 if sha(b)!=ref['sha256']:raise ValueError('artifact member changed')
 return b

def execute(p,go):
 start=time.monotonic();cpu=time.process_time()
 if go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root' or go.get('worker_version')!=VERSION or go.get('worker_sha256')!=sha(Path(__file__).read_bytes()) or go.get('plan_canonical_sha256')!=sha(encoded(p)):raise ValueError('exact independent root GO required')
 if p['version']!=VERSION or [(c['family'],c['target']) for c in p['cells']]!=SPEC or p['maximum_fit_calls']!=13 or p['private_peak_bytes']!=24*1024**2:raise ValueError('unchanged fixed13 finite scope required')
 if not p.get('storage_amendment'):raise ValueError('prospective storage-only amendment required')
 for ref in p['source_pins'].values():exact(ref)
 base=json.loads(exact(p['base_training_plan']));sys.path.insert(0,str(ROOT));import nfl_lab
 if Path(nfl_lab.__file__).resolve().parent!=ROOT/'nfl_lab':raise ValueError('wrong model package')
 from nfl_lab import cdf_engine as cdf,role_boosting as count,direct_boosters as direct
 stable=old.install(p['source_pins']['threshold'],'nfl_lab.threshold_cdf');response=old.install(p['source_pins']['response'],'nfl_lab.distribution_split_cdf')
 meanfix=load(p['source_pins']['mean_corrector']['path'],'fixed13_mean_corrector')
 helper=load(p['source_pins']['storage_helper']['path'],'fixed13_storage');store,_=helper.open_store(ROOT,allocation_sha256=base['allocation_sha256'],root_go=helper.GO)
 with store.transaction():store._refresh();entry=store._require(0)
 slug=p['output_slug']
 if not slug.startswith('matched12-fixed13-') or '/' in slug or '..' in slug:raise ValueError('fresh namespace required')
 out=store.forward_root/'research'/slug
 if out.exists():raise ValueError('consumed run exists')
 out=store.register_root(out);refs={};written=0;calls=0;callbacks=0;fitted=0;restores=0;generated=0;persisted=0;failed_preserved=0;slots=[]
 def put(name,body):
  nonlocal written
  if written+len(body)+65536>p['private_peak_bytes']:raise MemoryError('complete private peak exhausted')
  store.write_bytes(out/name,body);r=store.validate_reference(out/name,sha(body));refs[name]=r;written+=len(body);return r
 def now():return __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
 put('CONSUMED.json',encoded({'version':VERSION,'run_id':p['run_id'],'state':'BEFORE_NFL_SOURCE_OR_MODEL_DECODE','time_UTC':now(),'plan_sha256':go['plan_canonical_sha256'],'maximum_fit_calls':13,'storage_amendment':p['storage_amendment'],'no_spent_budget_reset':True}))
 try:
  import numpy as np,pandas as pd,pyarrow as pa,joblib,sklearn,scipy,importlib.metadata as metadata
  pa.set_cpu_count(2);pa.set_io_thread_count(2)
  auth={k:own(store,base[k]) for k in ['training_features','query_features','schedule']}
  d=json.loads(exact(base['categories']));cats={t:dict(d['categories'][t],target=t) for _,t in SPEC}
  for c in cats.values():cdf.validate_category(c)
  versions={'numpy':np.__version__,'pandas':pd.__version__,'pyarrow':pa.__version__,'sklearn':sklearn.__version__,'scipy':scipy.__version__,'joblib':joblib.__version__,'catboost':metadata.version('catboost')}
  if any(versions.get(k)!=v for k,v in p['expected_environment'].items()):raise ValueError('runtime changed')
  train,query,admission=old.inputs(p,base,cats,cdf)
  put('SOURCE_ADMISSION.json',encoded({'inputs':auth,'admission':admission,'environment':versions,'reuse_review':p['reuse_review'],'availability':'Original7day assumption unresolved; existing feature chronology version retained.'}))
  for cell in p['cells']:
   family,target=cell['family'],cell['target'];cat=cats[target];cid=cell['cell_id'];slot={'cell_id':cid,'target':target,'family':family,'state':'STARTED','fit_call_consumed':False,'optimizer_start_state':'NOT_OBSERVED'};slots.append(slot)
   members={};native_events=[];model=None
   try:
    cdf.assert_composite_contract(train,cat)
    params=(count.DESIGN if family=='COUNT_A_MEAN' else direct.parameters('catboost','medium',cat['support']) if family=='CATBOOST_MEDIUM' else {'tree_parameters':cdf.TREE_PARAMETERS,'prior_weight':cdf.PRIOR_WEIGHT,'threshold_grid':list(stable.THRESHOLD_GRIDS[target]),'split':'sqrt(trapezoid_weight)*1[Y<=threshold]'})
    recipe={'family':family,'category':cat,'parameters':params,'training_features':safe(base['training_features']),'training_cutoff_utc':base['training_cutoff_utc'],'feature_policy':base['source_policy_id'],'source_pins':{k:safe(v) for k,v in p['source_pins'].items()}}
    parent=sha(encoded(recipe));fit_start=time.monotonic();fit_cpu=time.process_time()
    if cell.get('reuse'):
     r=cell['reuse'];rm=json.loads(read_owned(store,r['manifest']))
     if rm['recipe_sha256']!=parent or rm['category']!=cat or rm['training_features']!=safe(base['training_features']):raise ValueError('reuse incompatible; no silent refit')
     restores+=1
     if restores>p['maximum_restorations']:raise ValueError('restoration cap')
     put(cid+'/RESTORE_START.json',encoded({'attempt':restores,'time_UTC':now(),'model':safe(r['model'])}));model_bytes=read_owned(store,r['model']);members['MODEL.joblib']=model_bytes;model=joblib.load(io.BytesIO(model_bytes))
     cls=count.RoleCountBoostingModel if family=='COUNT_A_MEAN' else direct.DirectBoosterModel if family=='CATBOOST_MEDIUM' else response.DistributionSplitCDFModel
     if type(model) is not cls or model.category!=cat:raise ValueError('reused model identity differs')
     b=model.prior_training_binding;good=train.participation_state.eq('played')&cdf.valid_support(cdf.numeric(train,target),cat['support'])
     if b is None or not old.macro.ordered(train.loc[good,list(b)]).equals(old.macro.ordered(b)):raise ValueError('actual training binding differs')
    else:
     calls+=1
     if calls>13:raise ValueError('fit allocation consumed')
     slot['fit_call_consumed']=True;slot['stage']='MODEL_FIT'
     reservation={'attempt':calls,'cell_id':cid,'time_UTC':now(),'recipe_sha256':parent,'recipe':recipe,'actual_optimizer_start':'UNKNOWN_UNTIL_CALLBACK_OR_RETURN'}
     fr=put(cid+'/FIT_START.json',encoded(reservation));slot['fit_reservation_sha256']=fr['sha256']
     def gate(info):
      nonlocal callbacks
      if native_events or not slot['fit_call_consumed'] or sha(encoded(reservation))!=fr['sha256']:raise ValueError('missing or duplicate durable fit reservation')
      callbacks+=1
      if callbacks>13:raise ValueError('native attempt allocation consumed')
      native_events.append({'time_UTC':now(),'info':info,'meaning':'ATTEMPT_GATE_BEFORE_NATIVE_FIT_NOT_EXACT_OPTIMIZER_ENTRY'});slot['native_attempt_gate_observed']=True
     if family=='COUNT_A_MEAN':model=count.RoleCountBoostingModel.fit(train,cat,'A',before_fit=gate)
     elif family=='CATBOOST_MEDIUM':model=direct.DirectBoosterModel.fit(train,cat,'base',library='catboost',complexity='medium',expected_version=versions['catboost'],fit_gate=gate)
     else:model=response.DistributionSplitCDFModel.fit(train,cat,'base')
     completed=bool(model.estimators) if family=='COUNT_A_MEAN' else model.estimator is not None if family=='CATBOOST_MEDIUM' else model.forest is not None
     fitted+=int(completed);slot.update(actual_estimator_fitted=completed,optimizer_start_state='CONFIRMED_BY_FITTED_RETURN' if completed else 'NOT_STARTED_EXPLICIT_FALLBACK',fit_actual={'CPU_seconds':time.process_time()-fit_cpu,'wall_seconds':time.monotonic()-fit_start,'completed_UTC':now()})
     slot['stage']='MODEL_SERIALIZATION';buf=io.BytesIO();joblib.dump(model,buf,compress=3);model_bytes=buf.getvalue();members['MODEL.joblib']=model_bytes
    if model.panel!='base' or family=='COUNT_A_MEAN' and model.variant!='A':raise ValueError('feature/variant identity changed')
    if family=='CATBOOST_MEDIUM' and (model.library!='catboost' or model.complexity!='medium' or model.package_version!=versions['catboost'] or model.audit['parameters']!=params):raise ValueError('native configuration differs')
    if family=='RESPONSE_CDF' and model.audit.get('split_thresholds')!=list(stable.THRESHOLD_GRIDS[target]):raise ValueError('response grid differs')
    members['MODEL.joblib']=model_bytes;mref={'member':'MODEL.joblib','bytes':len(model_bytes),'sha256':sha(model_bytes)}
    q=query.loc[query.position.eq('QB') if target.startswith('pass_') else query.position.isin(['QB','RB','FB','WR','TE'])].copy().reset_index(drop=True)
    slot['stage']='HISTORICAL_INFERENCE';wide=old.predictions(model,q,family,stable,meanfix,np);generated+=len(wide);slot['forecast_rows_generated']=len(wide)
    version=sha(encoded({'recipe':meanfix.RECIPE,'parent_procedure_version':parent,'parent_model_sha256':mref['sha256']})) if family=='COUNT_A_MEAN' else parent
    wide['target']=target;wide['method']=family;wide['procedure_version']=version;wide['parent_procedure_version']=parent;wide['issue_UTC']=now();wide['model_sha256']=mref['sha256'];wide['evidence_tier']='CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION'
    members['FORECASTS.parquet']=parquet(wide)
    warm=q.position.isin(cat['modeled_roles'])&q.f_player_games_prior.gt(0)
    fixture=pd.concat([q.head(2),q.loc[warm].head(2),q.head(4)]).drop_duplicates(cdf.KEYS).head(4)
    members['FIXTURE_FEATURES.parquet']=parquet(fixture);members['FIXTURE_EXPECTED.parquet']=parquet(wide.loc[fixture.index])
    members['MODEL_AUDIT.json']=encoded({'recipe_sha256':parent,'category':cat,'family':family,'training_features':safe(base['training_features']),'query_features':safe(base['query_features']),'model':mref,'audit':model.audit,'parameters':params,'environment':versions,'native_attempt_events':native_events,'fixture_policy':'first2 plus first2warmmodeled then fill first4; no outcomes; expected outputs subset of original full inference','fixture_compare_fields':['mean','median','point','legacy_point','probability','normalized_law_probability','fallback'],'fixture_extra_inference_rows':0,'output_contract':'Response normalized law means/medians; CountA intendedmean point and separatelegacy; CatPoissonpoint; no inventedPMF.'})
    slot.update(state='FROZEN_HISTORICAL_FORECASTS_UNSCORED',procedure_version=version,model=mref,forecast_rows=len(wide),fixture_rows=len(fixture),fallback_rows=int(wide.fallback.fillna('').ne('').sum()),games=int(wide.game_id.nunique()),weeks=sorted(map(int,wide.week.unique())))
    members['CELL_COMPLETE.json']=encoded(slot)
    manifest={k:{'bytes':len(v),'sha256':sha(v)} for k,v in members.items()};members['MEMBER_MANIFEST.json']=encoded({'format':'fixed13-cell-zip-v1.1','members':manifest,'old_algorithm_parameters_unchanged':True})
    slot['stage']='ATOMIC_CELL_BUNDLE_PUBLICATION';buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
     for name,body in members.items():z.writestr(name,body)
    bundle=put(cid+'/CELL.zip',buf.getvalue());slot['bundle']=safe(bundle);slot['members']=manifest;persisted+=len(wide);del model,members
   except BaseException as error:
    slot.update(state='FAILED_RETAINED',error_type=type(error).__name__,error_sha256=sha(str(error).encode()))
    if slot['optimizer_start_state']=='NOT_OBSERVED':slot['optimizer_start_state']='UNKNOWN_WITHIN_FAILED_METHOD' if slot['fit_call_consumed'] else 'NOT_STARTED'
    failure={**slot,'native_attempt_events':native_events,'private_error':str(error),'available_members':{k:safe({'bytes':len(v),'sha256':sha(v)}) for k,v in members.items()}}
    if model is not None:members['FAILED_MODEL_AUDIT.json']=encoded({'audit':getattr(model,'audit',None),'category':getattr(model,'category',None)})
    members['FAILURE.json']=encoded(failure)
    try:
     members['MEMBER_MANIFEST.json']=encoded({k:{'bytes':len(v),'sha256':sha(v)} for k,v in members.items()});failed=io.BytesIO()
     with zipfile.ZipFile(failed,'w',compression=zipfile.ZIP_STORED) as z:
      for name,body in members.items():z.writestr(name,body)
     slot['failure_bundle']=safe(put(cid+'/FAILURE_CELL.zip',failed.getvalue()));slot['failure_retention']='AVAILABLE_PARAMETERS_AND_VECTORS_RETAINED_NOT_QUALIFIED';failed_preserved+=slot.get('forecast_rows_generated',0) if 'FORECASTS.parquet' in members else 0
    except BaseException as retain_error:
     slot['failure_retention']='PARAMETERS_OR_VECTORS_UNRETAINED_NO_RESTORATION_CLAIM';slot['retention_error_type']=type(retain_error).__name__
     put(cid+'/FAILURE.json',encoded({**failure,'failure_retention':slot['failure_retention'],'retention_error_type':type(retain_error).__name__}))
    if isinstance(error,(TimeoutError,SystemExit,KeyboardInterrupt)):raise
  usage=store.verify_retained_checkpoint()
  if usage['new_peer_physical_bytes']-entry['new_peer_physical_bytes']>p['private_peak_bytes']:raise MemoryError('actual retained wave cap')
  result={'version':VERSION,'run_id':p['run_id'],'state':'COMPLETE_WITH_RETAINED_FAILURES' if any(c['state']=='FAILED_RETAINED' for c in slots) else 'FROZEN_FIXED13_FORECASTS_UNSCORED','cells':slots,'logical_fit_calls_consumed':calls,'native_attempt_callbacks_observed':callbacks,'actual_optimizer_starts_confirmed_by_fitted_return':fitted,'actual_estimators_fitted':fitted,'model_restoration_attempts':restores,'forecast_rows_generated':generated,'forecast_rows_persisted':persisted,'forecast_rows_persisted_failed':failed_preserved,'fixture_extra_inference_rows':0,'scores_HTTP_production_pregame_capture':0,'sources':admission,'artifacts':{k:safe(v) for k,v in refs.items()},'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'fresh_process_and_offhost_restore':'NOT_VERIFIED'}
  put('COMPLETE.json',encoded(result));store.verify_retained_checkpoint();return result
 except BaseException as e:
  fail={'state':'FAILED_WAVE_RETAINED','run_id':p['run_id'],'error_type':type(e).__name__,'error_sha256':sha(str(e).encode()),'logical_fit_calls_consumed':calls,'native_attempt_callbacks_observed':callbacks,'actual_estimators_fitted':fitted,'cells':slots}
  try:put('FAILURE.json',encoded({**fail,'private_error':str(e)}))
  except BaseException:pass
  return fail

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--plan-sha256',required=True);ap.add_argument('--go',type=Path,required=True);ap.add_argument('--go-sha256',required=True);a=ap.parse_args();sys.dont_write_bytecode=True
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 resource.setrlimit(resource.RLIMIT_CPU,(2200,2201));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('fixed13 wall cap')));signal.alarm(3000)
 sys.addaudithook(lambda event,args:(_ for _ in ()).throw(RuntimeError('zero network fixed13')) if event in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None)
 p=json.loads(exact({'path':str(a.plan),'bytes':a.plan.stat().st_size,'sha256':a.plan_sha256}));go=json.loads(exact({'path':str(a.go),'bytes':a.go.stat().st_size,'sha256':a.go_sha256}));r=execute(p,go);print(encoded(r).decode(),flush=True);signal.alarm(0)
 if r['state']!='FROZEN_FIXED13_FORECASTS_UNSCORED':raise SystemExit(1)
if __name__=='__main__':main()
