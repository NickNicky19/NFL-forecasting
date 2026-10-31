"""Three predeclared missing finalists; no target-season outcome conversion."""
from pathlib import Path
import collections,gzip,hashlib,io,json,resource,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-chart-event-fresh-cell-v1.1'
SPECS=[('chart_ppr','CATBOOST_MEDIUM'),('chart_ppr','RESPONSE_CDF'),('anytime_td','ROLE_LOGISTIC')]
CHART_GRID=[-250,0,100,200,300,400,500,600,750,1000,1250,1500,2000]
def enc(x):
 def default(v):
  if hasattr(v,'item'):return v.item()
  raise TypeError(type(v).__name__)
 return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,default=default)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def ref(p):
 p=Path(p);b=p.read_bytes();assert p.is_absolute() and p.resolve()==p and not any(z.is_symlink() for z in [p,*p.parents]);return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def raw(r):
 assert ref(r['path'])=={k:r[k] for k in ['path','bytes','sha256']};return Path(r['path']).read_bytes()
def parquet(f):
 import pyarrow as pa,pyarrow.parquet as pq
 b=io.BytesIO();pq.write_table(pa.Table.from_pandas(f,preserve_index=False,nthreads=1),b,compression='zstd');return b.getvalue()
def chart_training(cfg,engine):
 import numpy as np,pandas as pd,pyarrow.parquet as pq
 from tools import next_checkpoint_chart_cdf_contract as old
 # Decode numbers as lexemes; only admitted2024 values below become numbers.
 labels=json.loads(gzip.decompress(raw(cfg['chart_inputs']['chart_labels'])),parse_int=str,parse_float=str)
 assert labels['target']=='nick-chart-ppr-v1' and len(labels['labels'])==14160
 selected=[x for x in labels['labels'] if x['identity']['season']=='2024'];assert len(selected)==5935
 pos=pq.read_table(io.BytesIO(raw(cfg['chart_inputs']['weekly2024'])),columns=['season','week','season_type','game_id','team','opponent_team','player_id','position'],filters=[('season','==',2024),('season_type','==','REG'),('position','in',old.ROLES)],use_threads=False).to_pylist()
 positions={old.key(x):x for x in pos};assert len(positions)==len(pos)==5935
 columns=list(dict.fromkeys(engine.KEYS+['team','opponent','position','kickoff_utc','cutoff_utc','outcome_available_utc','feature_max_source_available_utc']+old.FEATURES))
 features=pq.read_table(io.BytesIO(raw(cfg['chart_inputs']['historical_features'])),columns=columns,filters=[('season','==',2024)],use_threads=False).to_pandas(use_threads=False)
 old.assert_chronology(features);lookup={old.key(x):x for x in features.to_dict('records')};assert len(lookup)==len(features)
 records=[];allvalues=[];allroles=[];missing=collections.Counter();origin=pd.Timestamp('2026-09-01T00:00:00Z')
 for label in selected:
  key=old.key(label['identity']);assert key in positions
  if label['state'] not in ['played_zero','played_score'] or label['value'] is None:missing[label['state']]+=1;continue
  val=float(label['value']);assert np.isfinite(val) and abs(val*50-round(val*50))<=1e-8
  role=positions[key]['position'];allvalues.append(round(val*50));allroles.append(role)
  f=lookup.get(key)
  if f is None:missing['numeric_missing_features']+=1;continue
  old.require_identity(label,f);assert old.aware(f['outcome_available_utc'])<origin
  if pd.isna(f['feature_max_source_available_utc']):missing['numeric_unknown_feature_clock']+=1;continue
  row=dict(f);row.update(position=role,chart_lattice_002_v1=round(val*50),participation_state='played');records.append(row)
 assert len(allvalues)==5589 and len(records)>=60
 train=pd.DataFrame(records);engine.assert_clock_contract(train)
 category={'target':'chart_lattice_002_v1','state':'READY','support':'signed_integer','modeled_roles':old.ROLES,'primary_roles':old.ROLES,'panels':{'base':old.FEATURES,'context':old.FEATURES}}
 return train,category,np.asarray(allvalues,float),np.asarray(allroles),{'year':2024,'planned':5935,'qualified_for_priors':5589,'model_rows':len(train),'missingness':dict(missing),'source_2026_statistics_decoded':0,'target_contract':'nick-chart-ppr-v1','scale':50}
def execute(cfg,go):
 start=time.monotonic();cpu=time.process_time()
 assert go['state']=='ROOT_AND_INDEPENDENT_GO' and go['registered_by']=='/root' and go['worker_sha256']==sha(Path(__file__).read_bytes()) and go['plan_sha256']==sha(enc(cfg))
 for r in cfg['source_pins'].values():raw(r)
 import nfl_lab
 assert Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab'
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq,joblib
 from threadpoolctl import threadpool_limits
 from nfl_lab import cdf_engine as engine,direct_boosters as direct
 from nfl_lab.owned_reference_batch import validate_owned_references
 from tools import category_topfive_matched12_fixed_completion_v1_1 as common,category_topfive_matched12_storage_v1 as st
 from sklearn.pipeline import Pipeline
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 pa.set_cpu_count(2);pa.set_io_thread_count(2)
 stable=common.old.install(cfg['source_pins']['threshold'],'nfl_lab.threshold_cdf');response=common.old.install(cfg['source_pins']['response'],'nfl_lab.distribution_split_cdf')
 assert 'chart_lattice_002_v1' not in stable.THRESHOLD_GRIDS
 stable.THRESHOLD_GRIDS['chart_lattice_002_v1']=np.asarray(CHART_GRID,float)
 store,_=st.open_store(ROOT,allocation_sha256=cfg['allocation_sha256'],root_go=st.GO)
 assert cfg['family'] in ['RESPONSE_CDF','ROLE_LOGISTIC'];out=store.forward_root/'research'/(VERSION+'__'+cfg['family']);assert not out.exists();store.register_root(out);written=0;slots=[];fitcalls=0
 def put(name,b):
  nonlocal written
  assert written+len(b)+65536<=cfg['resources']['private_bytes'];store.write_bytes(out/name,b);r=store.validate_reference(out/name,sha(b));written+=len(b);return {k:r[k] for k in ['bytes','sha256']}
 put('STARTED.json',enc({'state':'BEFORE_SOURCE_DECODE','specs':SPECS,'plan_sha256':go['plan_sha256'],'no_refund':True}))
 refs=list(cfg['chart_inputs'].values())+[cfg['training_features'],cfg['query_features']]
 for owner in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]:
  items={r['path']:r['sha256'] for r in refs if any(Path(r['path']).is_relative_to(Path(y)) for y in owner._roots)}
  if items:validate_owned_references(owner,items)
 q=pd.read_parquet(io.BytesIO(raw(cfg['query_features'])));assert len(q)==4985 and q.season.eq(2026).all() and q.week.between(1,7).all() and not q.duplicated(engine.KEYS).any()
 assert not set(['actual','outcome_state','chart_ppr','anytime_td'])&set(q)
 ctx=engine.KEYS+['team','opponent','position','kickoff_utc','cutoff_utc'];train,chartcat,values,roles,chartinfo=chart_training(cfg,engine) if cfg['family']=='RESPONSE_CDF' else (None,None,None,None,None)
 for target,family in [s for s in SPECS if s[1]==cfg['family']]:
  cid=target+'__'+family;slot={'cell_id':cid,'target':target,'method':family,'state':'STARTED'};slots.append(slot);members={}
  abort=False
  def retain_model(model):
   buf=io.BytesIO();joblib.dump(model,buf,compress=3);members['MODEL.joblib']=buf.getvalue()
  try:
   recipe={'version':VERSION,'target':target,'family':family,'source_pins':{k:v['sha256'] for k,v in cfg['source_pins'].items()},'source_training_sha256':cfg['chart_inputs']['chart_labels']['sha256'] if target=='chart_ppr' else cfg['training_features']['sha256'],'chart_grid_ticks':CHART_GRID if family=='RESPONSE_CDF' else None,'parameters':direct.parameters('catboost','medium','signed_integer') if family=='CATBOOST_MEDIUM' else {'trees':engine.TREE_PARAMETERS,'prior_weight':engine.PRIOR_WEIGHT} if family=='RESPONSE_CDF' else {'C':1.,'solver':'lbfgs','max_iter':300,'random_state':1703,'earlier_only_standard_scaler':True}}
   version=sha(enc(recipe));fitcalls+=1;assert fitcalls<=3
   put(cid+'/FIT_START.json',enc({'attempt':fitcalls,'recipe':recipe,'recipe_sha256':version,'time_UTC':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}))
   if target=='chart_ppr':
    if family=='CATBOOST_MEDIUM':model=direct.DirectBoosterModel.fit(train,chartcat,'base',library='catboost',complexity='medium',expected_version='1.2.10',fit_gate=lambda x:None)
    else:model=response.DistributionSplitCDFModel.fit(train,chartcat,'base')
    model.priors={role:engine.SupportPrior.fit(values[roles==role],'signed_integer') for role in sorted(set(roles))};model.global_prior=engine.SupportPrior.fit(values,'signed_integer');model.audit.update(prior_population='All5589qualified2024chartlabels, sameasretainedCDF',chart_training=chartinfo)
    slot['actual_fit_returned']=True;retain_model(model)
    wide=common.old.predictions(model,q,family,stable,None,np)
    for field in ['mean','median','point','legacy_point']:wide[field]=wide[field]/50
    audit=chartinfo
   else:
    cat=cfg['ATD_category'];features=cat['panels']['base'];cols=list(dict.fromkeys(engine.KEYS+['position','participation_state','kickoff_utc','outcome_available_utc','cutoff_utc','feature_max_source_available_utc','anytime_td']+features))
    hist=pq.read_table(io.BytesIO(raw(cfg['training_features'])),columns=cols,filters=[('season','>=',2019),('season','<=',2025)],use_threads=False).to_pandas(use_threads=False)
    assert len(hist)==59842;engine.assert_clock_contract(hist);cut=pd.Timestamp('2026-09-01T00:00:00Z');assert (pd.to_datetime(hist.outcome_available_utc,utc=True)<cut).all()
    good=hist.participation_state.eq('played')&engine.valid_support(engine.numeric(hist,'anytime_td'),'bernoulli');h=hist.loc[good].copy();assert len(h)>60 and h.anytime_td.nunique()==2
    design=engine.FixedDesign.fit(h,features);pipe=Pipeline([('scale',StandardScaler()),('logistic',LogisticRegression(C=1.,solver='lbfgs',max_iter=300,random_state=1703))])
    with threadpool_limits(limits=2):pipe.fit(design.transform(h),h.anytime_td.to_numpy(float))
    prior=h.groupby('position').anytime_td.mean().to_dict();gp=float(h.anytime_td.mean());model={'design':design,'estimator':pipe,'role_priors':prior,'global_prior':gp,'recipe':recipe,'training_source':cfg['training_features']['sha256']}
    slot['actual_fit_returned']=True;retain_model(model)
    probs=pipe.predict_proba(design.transform(q))[:,1];warm=q.f_player_games_prior.gt(0)&q.feature_max_source_available_utc.notna()&q.position.isin(prior)
    fallback=np.where(warm,'','cold_or_unknown_history_role_mean');probs[~warm]=q.loc[~warm,'position'].map(prior).fillna(gp).to_numpy(float)
    wide=q[ctx].copy();wide['probability']=probs;wide['fallback']=fallback;audit={'training_rows':len(h),'training_years':sorted(map(int,h.season.unique())),'target':'anytime_rush_or_receive_TD','new_2026_labels_used':False,'fit_iterations':pipe.named_steps['logistic'].n_iter_.tolist()}
   wide['method']=family;wide['target']=target;wide['procedure_version']=version;wide['evidence_tier']='CURRENT_VINTAGE_TIMING_UNVERIFIED_RECONSTRUCTION';wide['scoring_contract']='nick-chart-ppr-v1' if target=='chart_ppr' else 'rush_or_receive_TD'
   members['FORECASTS.parquet']=parquet(wide);members['AUDIT.json']=enc({'recipe':recipe,'audit':audit,'query_sha256':cfg['query_features']['sha256'],'model_sha256':sha(members['MODEL.joblib']),'genuine_pregame_forecasts':0})
   slot.update(state='FROZEN_FORECASTS_UNSCORED',rows=len(wide),procedure_version=version,fallback_rows=int(wide.fallback.ne('').sum()))
  except BaseException as error:
   slot.update(state='FAILED_ATTEMPT_PRESERVED',error_type=type(error).__name__,error_sha256=sha(str(error).encode()));members['FAILURE.json']=enc({**slot,'private_error':str(error)});abort=isinstance(error,(TimeoutError,MemoryError,SystemExit,KeyboardInterrupt))
  members['CELL_STATE.json']=enc(slot);manifest={k:{'bytes':len(v),'sha256':sha(v)} for k,v in members.items()};members['MEMBER_MANIFEST.json']=enc(manifest);buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
   for name,b in members.items():z.writestr(name,b)
  slot['bundle']=put(cid+'/CELL.zip',buf.getvalue());slot['members']=manifest
  if abort:break
 result={'version':VERSION,'state':'FROZEN_THREE_FINALIST_CELLS' if all(s['state']=='FROZEN_FORECASTS_UNSCORED' for s in slots) else 'TERMINAL_WITH_PRESERVED_FAILURES','logical_fit_calls_consumed':fitcalls,'cells':slots,'source_2026_chart_label_numbers_converted':0,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'genuine_pregame_forecasts_scoring_HTTP_production':0};put('COMPLETE.json',enc(result));store.verify_retained_checkpoint();return result
