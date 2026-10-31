"""Root-GO replay of frozen numeric laws, proper scores and P2 decisions.

No fitting, tuning, new sources, point-to-distribution conversion or production
operation. Params, query features, offers and policies must already be frozen.
These are exposed historical reconstructions, never original pregame picks.
"""
from __future__ import annotations
import argparse,base64,copy,gzip,hashlib,importlib.util,io,json,resource,signal,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-frozen-law-outer-v1.1'
LAW_SHA='2a4754b286a81c44a34d389110624de2a5ccbbf155fd4eb6bcb27bda704d2e21'
KEY=['season','week','game_id','player_id'];CTX=KEY+['team','opponent','position','kickoff_utc','cutoff_utc']
ID=['target']+KEY+['team','opponent'];OFFER=ID+['cutoff_utc']
def enc(x):
 def default(v):
  if hasattr(v,'item'):return v.item()
  raise TypeError(type(v).__name__)
 return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,default=default)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def ref(p):
 p=Path(p);b=p.read_bytes()
 if not p.is_absolute() or p.resolve()!=p or any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('canonical reference required')
 return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def raw(r):
 if ref(r['path'])!={k:r[k] for k in ['path','bytes','sha256']}:raise ValueError('exact bytes changed')
 return Path(r['path']).read_bytes()
def table_bytes(r):
 b=raw(r)
 if r.get('member'):
  with zipfile.ZipFile(io.BytesIO(b)) as z:b=z.read(r['member'])
  if sha(b)!=r['member_sha256']:raise ValueError('exact table member changed')
 return b
def load(name,r):
 raw(r);s=importlib.util.spec_from_file_location(name,r['path']);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def child(root,r):
 p=root/r['file']
 if not p.is_relative_to(root):raise ValueError('relative artifact escaped registered run')
 got=ref(p)
 if any(got[k]!=r[k] for k in ['sha256','bytes']):raise ValueError('retained child differs')
 return got

def fixed_cells(doc):
 """Metadata-only admission of the two separately registered cell formats."""
 version=doc['version']
 if version=='matched12-fixed-completion-v1.1':
  allowed={'pass_cmp','pass_yd','rush_yd','rec_yd','rush_rec_yd'};state='FROZEN_HISTORICAL_FORECASTS_UNSCORED'
  if doc['state'] not in ['FROZEN_FIXED13_FORECASTS_UNSCORED','COMPLETE_WITH_RETAINED_FAILURES']:raise ValueError('fixed13 source has no terminal freeze')
 elif version in ['matched12-chart-event-fixed-completion-v1','matched12-chart-event-fresh-cell-v1.1']:
  allowed={'chart_ppr'};state='FROZEN_FORECASTS_UNSCORED'
  if doc['state'] not in ['FROZEN_THREE_FINALIST_CELLS','TERMINAL_WITH_PRESERVED_FAILURES']:raise ValueError('chart/event source has no terminal freeze')
 else:raise ValueError('unregistered fixed-cell source version')
 return [r for r in doc['cells'] if r['state']==state and r.get('family',r.get('method'))=='RESPONSE_CDF' and r['target'] in allowed]

def prepare_fixed_specs(source):
 terminal=source['terminal'];features=source['features'];run=Path(terminal['path']).parent;doc=json.loads(raw(terminal));result=[]
 if features['sha256']!='5450041c91f3c5dce3a4078c81b861f388e4682dd5cc57d3f1e6b250338f5b0e':raise ValueError('fixed source query frame changed')
 raw(features)
 for r in fixed_cells(doc):
  cid=r['cell_id'];target=r['target'];artifact=child(run,{'file':cid+'/CELL.zip',**r['bundle']});members=r['members']
  forecast={**artifact,'member':'FORECASTS.parquet','member_sha256':members['FORECASTS.parquet']['sha256']}
  with zipfile.ZipFile(io.BytesIO(raw(artifact))) as z:
   for n in ['MODEL.joblib','FORECASTS.parquet']:
    b=z.read(n)
    if len(b)!=members[n]['bytes'] or sha(b)!=members[n]['sha256']:raise ValueError('fixed member hash/size differs')
  roles=['QB'] if target.startswith('pass_') else ['QB','RB','FB','WR','TE']
  primary=['QB'] if target.startswith('pass_') else ['RB'] if target=='rush_yd' else ['RB','WR','TE'] if target in ['rec_yd','rush_rec_yd'] else roles
  result.append({'cell_id':doc['version']+'__'+cid,'source_cell_id':cid,'source_terminal':terminal,'source_format':doc['version'],
   'target':target,'kind':'fixed_cell','artifact':artifact,'member':'MODEL.joblib','inner_sha256':members['MODEL.joblib']['sha256'],
   'features':features,'forecast':forecast,'law_replay':terminal,'replay_binding_kind':'SOURCE_COMPLETE_AND_EXACT_CELL_MEMBERS',
   'methods':['RESPONSE_CDF'],'query_roles':roles,'primary_roles':primary,'scale':50 if target=='chart_ppr' else 1,'expected_query_rows':r.get('forecast_rows',r.get('rows'))})
 return result

def prepare_specs(fixed_runs=()):
 """Metadata and opaque member hashing only; no model or table decoding."""
 helper=load('law_plan_storage',ref(ROOT/'tools/category_topfive_matched12_storage_v1.py'))
 root=Path(helper.prepare(ROOT)['allocation']['store_policy']['storage']['forward_root'])/'research'
 specs=[]
 for version in ['matched12-fixed-parameter-historical-inference-v1','matched12-followup-fixed-parameter-inference-v1']:
  run=root/version;terminal=ref(run/'TERMINAL.json');doc=json.loads(raw(terminal))
  for result in doc['results']:
   cid=result['cell_id'];target=result['target']
   if result['state']!='FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED' or target=='anytime_td':continue
   if version.startswith('matched12-fixed-') and result['family']!='leaf_cdf_base':continue
   if version.startswith('matched12-followup-') and ('CATBOOST' in cid or 'HGB' in cid):continue
   receipt=child(run,result['law_replay']);r=json.loads(raw(receipt));forecast=child(run,result['forecast'])
   if 'family' in r:
    kind='future';artifact=r['model'];member=None;manifest=r['manifest'];features=r['features']
    methods=['LEAF_CDF'];roles=r['population_query_roles'];primary=r['primary_roles'];scale=1
    inner_sha=artifact['sha256']
   else:
    artifact=r['artifact'];member=r['member'];manifest=None;features=child(run,r['features']);scale=r['scoring_scale']
    roles=['QB'] if target.startswith('pass_') else ['QB','RB','FB','WR','TE']
    primary=['QB'] if target.startswith('pass_') else ['RB'] if target in ['rush_yd','rush_att'] else ['RB','WR','TE'] if target in ['rec','rec_yd','rush_rec_yd'] else roles
    methods=result['methods']
    if scale==50:
     kind='chart_pickle';inner_sha=r['model_sha256']
    else:
     kind='bundle' if 'RESPONSE_CDF' in cid else 'plain'
     with zipfile.ZipFile(io.BytesIO(raw(artifact))) as z:inner_sha=sha(z.read(member))
   specs.append({'cell_id':version+'__'+cid,'target':target,'kind':kind,'artifact':artifact,'member':member,
    'inner_sha256':inner_sha,'future_manifest':manifest,'features':features,'forecast':forecast,'law_replay':receipt,
    'source_terminal':terminal,'source_cell_id':cid,'methods':methods,'query_roles':roles,'primary_roles':primary,'scale':scale})
 for source in fixed_runs:specs.extend(prepare_fixed_specs(source))
 identities=[(s['target'],m) for s in specs for m in s['methods']]
 if len(set(identities))!=len(identities):raise ValueError('duplicate target/procedure law specs')
 return specs

def subset(law,ix):
 r=copy.copy(law)
 for k in ['weights','cumulative','weighted_cumulative']:setattr(r,k,getattr(law,k)[ix])
 return r
def missing_law_offers(rows,offers,np):
 f=rows.merge(offers,on=OFFER,how='inner',validate='one_to_one',suffixes=('','_offer'));result=[]
 for arm in ['FOOTBALL','SHRINK_0_5']:
  v=f.copy();v['arm']=arm
  for c in ['p_under','p_push','p_over','log_p_under','log_p_push','log_p_over','confidence','Brier','log_loss','event_index']:v[c]=np.nan
  from decimal import Decimal
  valid=v.participation_state.eq('played')&v.actual.notna();v.loc[valid,'event_index']=[0 if Decimal(str(y))<Decimal(str(L)) else 2 if Decimal(str(y))>Decimal(str(L)) else 1 for y,L in v.loc[valid,['actual','line']].to_numpy()]
  v['side']=v['side55']='unavailable';v['result']=v['result55']=np.where(v.participation_state.isin(['DNP','dnp']),'DNP','UNRESOLVED');result.append(v)
 return result
def side_summary(f):
 out={'opportunities':len(f),'unique_player_games':len(f[KEY].drop_duplicates()),'games':int(f.game_id.nunique()),'weeks':sorted(map(int,f.week.unique())),'participation_states':f.participation_state.fillna('unknown').value_counts().to_dict()}
 for side in ['over','under']:
  v=f.loc[f.side.eq(side)];c=v.result.value_counts();w=int(c.get('WIN',0));l=int(c.get('LOSS',0))
  out[side]={'wins':w,'losses':l,'decided':w+l,'hit_rate':w/(w+l) if w+l else None,
    'push':int(c.get('PUSH',0)),'DNP':int(c.get('DNP',0)),'unresolved':int(c.get('UNRESOLVED',0))}
 out['abstain']=int(f.side.eq('abstain').sum());out['missing_law']=int(f.side.eq('unavailable').sum())
 out['venue_settlement']='NOT_INFERRED_FROM_STATISTICAL_DIRECTION';return out
def probability_summary(f,loss):
 scored=f.loc[f.score_state.eq('SCORED')];result={'planned':len(f),'scored':len(scored),'games':int(scored.game_id.nunique()),'weeks':sorted(map(int,scored.week.unique())),'states':f.score_state.value_counts().to_dict()}
 if 'Brier' in f:
  result.update(primary='HALF_THREE_OUTCOME_BRIER',Brier=loss.loss_summary(scored.Brier.to_numpy()),log_loss=loss.loss_summary(scored.log_loss.to_numpy()))
  result['over_reliability']=[]
  for i in range(10):
   g=scored.loc[scored.p_over.ge(i/10)&(scored.p_over.lt((i+1)/10) if i<9 else scored.p_over.le(1))]
   result['over_reliability'].append({'lower':i/10,'upper':(i+1)/10,'n':len(g),'predicted':float(g.p_over.mean()) if len(g) else None,'observed':float(g.event_index.eq(2).mean()) if len(g) else None})
 else:
  result.update(primary='CRPS',CRPS=loss.loss_summary(scored.CRPS.to_numpy()),negative_log_pmf=loss.loss_summary(scored.negative_log_pmf.to_numpy()))
  result['interval80_coverage']=float((scored.actual.ge(scored.p10)&scored.actual.le(scored.p90)).mean()) if len(scored) else None
  result['mid_PIT_outside_unit_interval']=int((~scored.mid_PIT.between(0,1)).sum())
 return result
def selectors(frame,uncertainty,interval):
 summaries=[]
 for (target,method,arm),g in frame.groupby(['target','method','arm'],sort=True):
  views={'FULL_BOARD':g,'ABSTAIN_CONFIDENCE_0_55':g.assign(side=g.side55,result=g.result55)}
  for side,event in [('over',2),('under',0)]:
   c=g.copy();c['side']=side;c['result']=__import__('numpy').where(c.participation_state.isin(['DNP','dnp']),'DNP',__import__('numpy').where(c.event_index.isna(),'UNRESOLVED',__import__('numpy').where(c.event_index.eq(1),'PUSH',__import__('numpy').where(c.event_index.eq(event),'WIN','LOSS'))));views['ALWAYS_'+side.upper()]=c
  for k in [6,10,20]:
   rank=g.loc[g.side.isin(['over','under'])].sort_values(['week','confidence','game_id','player_id'],ascending=[True,False,True,True],kind='stable')
   views['TOP_'+str(k)+'_PER_CATEGORY_WEEK']=rank.groupby('week',group_keys=False).head(k)
  for policy,v in views.items():
   met=side_summary(v);dec=v.loc[v.result.isin(['WIN','LOSS'])]
   met['hit_rate_intervals']={c:interval(dec.result.eq('WIN').to_numpy(float),dec[c],uncertainty) for c in ['game_id','week']}
   summaries.append({'target':target,'method':method,'arm':arm,'policy':policy,'metrics':met,
    'weekly':[{'week':int(w),'metrics':side_summary(v.loc[v.week.eq(w)])} for w in sorted(g.week.unique())]})
 return summaries
def paired(records,value,reference,loss,uncertainty,interval):
 comparisons=[]
 for identity,g in records.groupby(['target','method']+(['arm'] if 'arm' in records else []),sort=True):
  target,method=identity[:2]
  control=records.loc[records.target.eq(target)&records.method.eq(reference.get(target,'LEAF_CDF'))]
  if len(identity)>2:control=control.loc[control.arm.eq(identity[2])]
  a=g.loc[g.score_state.eq('SCORED')];b=control.loc[control.score_state.eq('SCORED')]
  keys=ID+['cutoff_utc']+(['offer_id','arm'] if 'offer_id' in g else [])
  j=a[keys+[value]].merge(b[keys+[value]],on=keys,validate='one_to_one',suffixes=('_a','_b'))
  x,y=j[value+'_a'].to_numpy(float),j[value+'_b'].to_numpy(float);r=loss.paired_summary(x,y)
  if __import__('numpy').isfinite(x).all() and __import__('numpy').isfinite(y).all():r['intervals']={c:interval(x-y,j[c],uncertainty) for c in ['game_id','week']}
  else:r['intervals']={'state':'UNAVAILABLE_NONFINITE_LOSSES_RETAINED'}
  comparisons.append({'target':target,'method':method,'arm':identity[2] if len(identity)>2 else None,'reference':reference.get(target,'LEAF_CDF'),'metric':value,'matched':r})
 return comparisons

def execute(plan,go):
 start=time.monotonic();cpu=time.process_time()
 if go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root' or go.get('worker_sha256')!=sha(Path(__file__).read_bytes()) or go.get('plan_sha256')!=sha(enc(plan)):raise ValueError('exact law replay root/reviewer GO required')
 caps=plan['resources'];resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1));signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('finite law replay wall cap')));signal.alarm(caps['wall_seconds'])
 def offline(e,a):
  if e in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline frozen law replay')
 sys.addaudithook(offline);sys.path.insert(0,str(ROOT))
 for r in plan['source_pins'].values():raw(r)
 if plan['source_pins']['loss']['sha256']!=LAW_SHA:raise ValueError('reviewed exact law helper changed')
 import numpy as np,pandas as pd,joblib
 from threadpoolctl import threadpool_limits
 from nfl_lab import cdf_engine as engine,weekly_future_inference as api,next_checkpoint_chart_cdf_inference as chart
 from nfl_lab.owned_reference_batch import validate_owned_references
 if api.environment()!=plan['environment']:raise ValueError('model dependency versions changed')
 loss=load('law_outer_scores',plan['source_pins']['loss']);aux=load('law_outer_auxiliary',plan['source_pins']['auxiliary'])
 stable=load('nfl_lab.threshold_cdf',plan['source_pins']['threshold']).StableMixtureBatch
 response=load('nfl_lab.distribution_split_cdf',plan['source_pins']['response']).DistributionSplitCDFModel
 helper=load('law_outer_storage',plan['source_pins']['storage'])
 store,_=helper.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=helper.GO)
 out=store.forward_root/'research'/plan['run_id']
 if not plan['run_id'].startswith('matched12-law-') or '/' in plan['run_id'] or out.exists():raise ValueError('fresh law replay namespace required')
 store.register_root(out);used=16384;refs={}
 def put(name,body):
  nonlocal used
  reserve=0 if name.endswith('FAILURE.json') else 65536
  if used+len(body)+reserve>caps['private_bytes']:raise ValueError('finite law evidence allocation exhausted')
  usage=store.verify_retained_checkpoint()
  if usage['new_peer_physical_bytes']+len(body)+reserve>100663296:raise ValueError('complete retained envelope exhausted')
  used+=len(body);p=out/name;store.write_bytes(p,body);got=store.validate_reference(p,sha(body));refs[name]={'bytes':got['bytes'],'sha256':got['sha256']};return refs[name]
 put('STARTED.json',enc({'state':'STARTED_BEFORE_LABEL_READ','version':VERSION,'plan_sha256':go['plan_sha256'],'fits':0,'new_original_pregame_forecasts':0}))
 allrefs=[plan['labels']]+([plan['offers']] if plan.get('offers') else [])
 for s in plan['specs']:
  allrefs += [s[k] for k in ['artifact','features','forecast','law_replay','source_terminal']]
  if s.get('future_manifest'):allrefs.append(s['future_manifest'])
 unique={r['path']:r for r in allrefs};stamps={};checked={}
 def stamp(p):
  st=Path(p).lstat();return (st.st_dev,st.st_ino,st.st_size,st.st_mode,st.st_mtime_ns,st.st_ctime_ns)
 def bulk():
  groups={}
  for r in unique.values():
   p=Path(r['path']);owners=[o for o in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy] if any(p.is_relative_to(q) for q in o._roots)]
   if len(owners)!=1:raise ValueError('exact original owner unknown')
   groups.setdefault(owners[0],[]).append(r)
  receipts=[]
  for owner,items in groups.items():
   found,receipt=validate_owned_references(owner,{r['path']:r['sha256'] for r in items});receipts.append(receipt)
   for r in items:
    if found[r['path']]['bytes']!=r['bytes']:raise ValueError('owned reference size mismatch')
    checked[r['path']]=found[r['path']];stamps[r['path']]=stamp(r['path'])
  return receipts
 def owned(r):
  p=r['path']
  if p not in checked or any(checked[p][k]!=r[k] for k in ['path','bytes','sha256']) or stamp(p)!=stamps[p]:raise ValueError('batch-authenticated source changed')
  return checked[p]
 put('OWNED_START.json',enc(bulk()))
 # The complete distribution is frozen by these already retained parameters,
 # inputs and deterministic law/side policy; not a newly issued pregame bet.
 put('FROZEN_EVALUATION_BINDINGS.json',enc({'specs':plan['specs'],'labels_sha256':plan['labels']['sha256'],'offers_sha256':plan['offers']['sha256'] if plan.get('offers') else None,'decision_policy':'P2 higher decisive-side probability, exact ties abstain; .55 control; Top6/10/20 frozen confidence ranking; shrink.5 threshold-only','historical_evidence':'EXPOSED_DEVELOPMENT_NOT_CONFIRMATION'}))
 labels=pd.read_parquet(io.BytesIO(table_bytes(plan['labels'])));labelcols=ID+['actual','participation_state']
 labels=labels[labelcols].drop_duplicates()
 if labels.duplicated(ID).any():raise ValueError('outcome versions conflict')
 if not labels.participation_state.isin(['played','unknown','DNP','dnp']).all():raise ValueError('explicit participation vocabulary required')
 if (labels.actual.notna()&~labels.participation_state.eq('played')).any():raise ValueError('unknown/DNP is not a scored zero')
 offers=pd.read_parquet(io.BytesIO(table_bytes(plan['offers']))) if plan.get('offers') else None
 if offers is not None:
  if offers.duplicated(OFFER).any():raise ValueError('multiple primary offers per football opportunity')
  offers=offers.copy();offers['cutoff_utc']=pd.to_datetime(offers.cutoff_utc,utc=True);offers['offer_id']=np.arange(len(offers))
 numerical=[];offered=[];completed=[];restores=0;query_rows=0;coverage=[]
 def serialize(table):
  f=table.copy()
  if 'line' in f:f['line']=f.line.map(str)
  b=io.BytesIO();f.to_parquet(b,index=False,compression='zstd');return b.getvalue()
 def grade(side,y,L,state):
  if side=='abstain':return 'ABSTAIN'
  if side=='unavailable':return 'UNRESOLVED'
  if state in ['DNP','dnp']:return 'DNP'
  if state!='played' or not np.isfinite(y):return 'UNRESOLVED'
  from decimal import Decimal
  a,b=Decimal(str(y)),Decimal(str(L))
  return 'PUSH' if a==b else 'WIN' if (a>b if side=='over' else a<b) else 'LOSS'
 for spec in plan['specs']:
  cid=spec['cell_id'];q=None;put(cid+'/STARTED.json',enc({'state':'MODEL_RESTORATION_ATTEMPT_STARTED','artifact_sha256':spec['artifact']['sha256'],'features_sha256':spec['features']['sha256'],'new_fits':0}))
  try:
   for k in ['artifact','features','forecast','law_replay','source_terminal']:owned(spec[k])
   terminal=json.loads(raw(spec['source_terminal']))
   if spec['kind']=='fixed_cell':
    sr=next(r for r in fixed_cells(terminal) if r['cell_id']==spec['source_cell_id'])
    if terminal['version']!=spec['source_format'] or sr['target']!=spec['target'] or sr['bundle']['sha256']!=spec['artifact']['sha256'] or sr['bundle']['bytes']!=spec['artifact']['bytes'] or sr['members'][spec['member']]['sha256']!=spec['inner_sha256'] or sr['members']['FORECASTS.parquet']['sha256']!=spec['forecast']['member_sha256']:raise ValueError('fixed-cell terminal/member chain differs')
    if spec['forecast']['sha256']!=spec['artifact']['sha256'] or spec['forecast'].get('member')!='FORECASTS.parquet' or spec['member']!='MODEL.joblib':raise ValueError('fixed-cell forecast/model container differs')
   else:
    sr=next(r for r in terminal['results'] if r['cell_id']==spec['source_cell_id'])
    if sr['state']!='FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED' or sr['forecast']['sha256']!=spec['forecast']['sha256']:raise ValueError('original forecast terminal chain differs')
   q=pd.read_parquet(io.BytesIO(raw(spec['features'])))
   q=q.loc[q.position.isin(spec['query_roles'])].copy().reset_index(drop=True)
   if q.duplicated(KEY).any() or not q.season.eq(2026).all() or not q.week.between(1,7).all():raise ValueError('query population/historical scope changed')
   for k in ['kickoff_utc','cutoff_utc','feature_max_source_available_utc']:
    for v in q[k].dropna().unique():
     if pd.Timestamp(v).tzinfo is None:raise ValueError('source timezone unknown')
    q[k]=pd.to_datetime(q[k],utc=True)
   if (q.cutoff_utc>q.kickoff_utc).any() or (q.feature_max_source_available_utc.notna()&(q.feature_max_source_available_utc>=q.cutoff_utc)).any():raise ValueError('query source chronology violation')
   original=pd.read_parquet(io.BytesIO(table_bytes(spec['forecast'])))
   q=q.rename(columns={'participation_state':'query_participation_state'});q['target']=spec['target'];q=q.merge(labels,on=ID,how='left',validate='one_to_one',indicator=True)
   q['label_qualification']=np.where(q['_merge'].eq('both'),'RETAINED_LABEL','LABEL_UNAVAILABLE');q['participation_state']=q.participation_state.fillna('unknown');q=q.drop(columns='_merge');restores+=1;query_rows+=len(q)
   if restores>caps['model_restorations'] or query_rows>caps['query_law_rows']:raise ValueError('finite law replay budget exhausted')
   blob=raw(spec['artifact']);session=None
   if spec['kind']=='future':
    owned(spec['future_manifest']);session=api.FutureInferenceSession(lambda items:{r['path']:owned(r) for r in items})
    session.prepare([spec['future_manifest']]);manifest,model=session.models[spec['future_manifest']['sha256']]
   else:
    if spec['kind']=='chart_pickle':
     doc=json.loads(gzip.decompress(blob),parse_int=str,parse_float=str);inner=base64.b64decode(doc['fitted_model_pickle_base64'],validate=True)
    else:
     with zipfile.ZipFile(io.BytesIO(blob)) as z:inner=z.read(spec['member'])
    if sha(inner)!=spec['inner_sha256']:raise ValueError('exact model member differs')
    if spec['kind']=='chart_pickle':model=chart.load_reviewed_model(inner,expected_sha256=spec['inner_sha256'])
    else:
     obj=joblib.load(io.BytesIO(inner));model=obj['model'] if spec['kind']=='bundle' else obj
   expected_type=response if 'RESPONSE_CDF' in cid else engine.LeafCDFModel
   if type(model) is not expected_type or model.category['support']=='bernoulli':raise ValueError('wrong numeric law model class')
   variants={m:[] for m in spec['methods']};eventvariants={m:[] for m in spec['methods']}
   # Model sees only its trained prefixed feature columns, never joined labels.
   query=q.drop(columns=['actual','participation_state','target','label_qualification']).rename(columns={'query_participation_state':'participation_state'})
   with threadpool_limits(limits=2):
    for ix,batch,reasons in model.predict_batches(query,batch_size=128):
     for method in spec['methods']:
      rows=q.iloc[ix].drop(columns=[c for c in q if c.startswith('f_')]).copy().reset_index(drop=True);rows['method']=method;rows['primary_role']=rows.position.isin(spec['primary_roles']);rows['fallback']=reasons
      rows['score_state']=np.where(rows.participation_state.isin(['DNP','dnp']),'DNP',np.where(rows.participation_state.ne('played'),'UNKNOWN',np.where(rows.actual.isna(),'PLAYED_MISSING','SCORED')))
      for c in ['CRPS','negative_log_pmf','p10','p90','mid_PIT']:rows[c]=np.nan
      if batch is None:
       rows['score_state']='MISSING_LAW';variants[method].append(rows)
       if offers is not None:
        eventvariants[method].extend(missing_law_offers(rows,offers,np))
       continue
      prior=method=='CHART_ROLE_LAW'
      law=stable([0.],np.ones((len(ix),1)),batch.prior,prior_weight=1.) if prior else stable.from_batch(batch)
      good=rows.score_state.eq('SCORED').to_numpy();at=np.flatnonzero(good)
      rows['p10']=law.quantile(.1)/spec['scale'];rows['p90']=law.quantile(.9)/spec['scale']
      if len(at):
       scored=loss.numeric_scores(subset(law,at),rows.actual.to_numpy(float)[at],scale=spec['scale'],contract='nick-chart-ppr-v1' if spec['scale']==50 else None)
       rows.loc[at,'CRPS']=scored['CRPS'];rows.loc[at,'negative_log_pmf']=scored['negative_log_pmf']
       z=np.rint(rows.actual.to_numpy(float)[at]*spec['scale']);lo,_=loss.law_logtails(subset(law,at),z-1)
       rows.loc[at,'mid_PIT']=np.exp(lo)+.5*np.exp(loss.law_logpmf(subset(law,at),z))
      variants[method].append(rows)
      if offers is None:continue
      f=rows.merge(offers,on=OFFER,how='inner',validate='one_to_one',suffixes=('','_offer'))
      if f.empty:continue
      if spec['scale']==50:
       if 'target_contract' not in f or not f.target_contract.eq('nick-chart-ppr-v1').all():raise ValueError('old PPR offer is not exact chart contract')
      by={tuple(r):i for i,r in enumerate(rows[KEY].to_numpy())};positions=np.asarray([by[tuple(r)] for r in f[KEY].to_numpy()])
      events=loss.threshold_probabilities(subset(law,positions),f.line.to_numpy(),scale=spec['scale'],contract='nick-chart-ppr-v1' if spec['scale']==50 else None)
      for arm,e in [('FOOTBALL',events),('SHRINK_0_5',loss.shrink_control(events))]:
       v=f.copy();v['arm']=arm;p=e['probabilities'];lp=e['log_probabilities'];v['p_under'],v['p_push'],v['p_over']=p.T
       for n,a in enumerate(['under','push','over']):v['log_p_'+a]=lp[:,n]
       selected=loss.select_sides(e);abstain=loss.select_sides(e,minimum_confidence=.55)
       v['side']=selected['side'];v['side55']=abstain['side'];v['confidence']=selected['decisive_confidence'];v['Brier']=np.nan;v['log_loss']=np.nan;v['event_index']=np.nan
       good=v.score_state.eq('SCORED').to_numpy();at=np.flatnonzero(good)
       if len(at):
        es={**e,'probabilities':p[at],'log_probabilities':lp[at],'line_ticks':e['line_ticks'][at]}
        s=loss.threshold_scores(es,v.actual.to_numpy(float)[at]);v.loc[at,'Brier']=s['Brier'];v.loc[at,'log_loss']=s['log_loss'];v.loc[at,'event_index']=s['event_index']
       for field,sidefield in [('result','side'),('result55','side55')]:v[field]=[grade(r[sidefield],r['actual'],r['line'],r['participation_state']) for r in v.to_dict('records')]
       eventvariants[method].append(v)
   if session is not None:session.close()
   entries={};cellrows=[];cellevents=[]
   for method,parts in variants.items():
    f=pd.concat(parts,ignore_index=True)
    old=original.loc[original.method.eq(method)]
    if len(old)!=len(q) or set(map(tuple,old[KEY].to_numpy()))!=set(map(tuple,q[KEY].to_numpy())):raise ValueError('frozen original forecast coverage differs')
    cellrows.append(f)
    if eventvariants[method]:g=pd.concat(eventvariants[method],ignore_index=True);cellevents.append(g)
   entries['DISTRIBUTION_SCORECARD.parquet']=serialize(pd.concat(cellrows,ignore_index=True))
   if cellevents:entries['OFFER_PROBABILITY_SCORECARD.parquet']=serialize(pd.concat(cellevents,ignore_index=True))
   entries['MANIFEST.json']=enc({'version':VERSION,'spec':spec,'law_helper_sha256':LAW_SHA,'law_arithmetic':'normalized-cumulative-mixture-v1-20261025','threshold_primary':'HALF_THREE_OUTCOME_BRIER','statement':'All predictions and decisions reconstructed from earlier frozen parameters/inputs; no original pregame issuance or venue return inferred.'})
   b=io.BytesIO()
   with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_STORED) as z:
    for n,v in entries.items():z.writestr(n,v)
   artifact=put(cid+'/SCORE_PACKAGE.zip',b.getvalue());numerical.extend(cellrows);offered.extend(cellevents)
   if offers is not None:
    board=offers.loc[offers.target.eq(spec['target'])];match=board.merge(q[OFFER],on=OFFER,how='left',validate='one_to_one',indicator=True)
    coverage.append({'cell_id':cid,'primary_offer_pool':len(board),'within_query':int(match['_merge'].eq('both').sum()),'outside_query':int(match['_merge'].ne('both').sum()),'queries_without_offer':len(q)-int(match['_merge'].eq('both').sum())})
   completed.append({'cell_id':cid,'state':'SCORED_FROZEN_LAW','artifact':artifact,'query_rows':len(q),'methods':spec['methods']})
  except BaseException as exc:
   failed={'cell_id':cid,'state':'FAILED_CELL_NO_SUCCESS_INFERRED','expected_queries':len(q) if q is not None else spec.get('expected_query_rows'),'query_count_reason':None if q is not None or 'expected_query_rows' in spec else 'FAILURE_BEFORE_QUERY_DECODE','expected_offer_rows':int(offers.target.eq(spec['target']).sum()) if offers is not None else None,'offer_count_reason':None if offers is not None else 'NO_SUPPORTED_OFFER_INPUT'};coverage.append(failed)
   failure={'cell_id':cid,'state':'FAILED_ATTEMPT_RETAINED','coverage':failed,'exception_type':type(exc).__name__,'private_message':str(exc)}
   put(cid+'/FAILURE.json',enc(failure));completed.append({k:v for k,v in failure.items() if k!='private_message'})
   if isinstance(exc,(TimeoutError,MemoryError,KeyboardInterrupt,SystemExit)):raise
 allnum=pd.concat(numerical,ignore_index=True) if numerical else pd.DataFrame();allevents=pd.concat(offered,ignore_index=True) if offered else pd.DataFrame()
 summaries=[]
 if len(allnum):
  for (t,m),f in allnum.groupby(['target','method']):
   p=f.loc[f.primary_role];summaries.append({'target':t,'method':m,'primary_roles':probability_summary(p,loss),'all_attempts_secondary':probability_summary(f,loss),'weekly':[{'week':int(w),'metrics':probability_summary(p.loc[p.week.eq(w)],loss)} for w in sorted(f.week.unique())]})
 prob=[]
 if len(allevents):
  for (t,m,a),f in allevents.groupby(['target','method','arm']):prob.append({'target':t,'method':m,'arm':a,'metrics':probability_summary(f,loss)})
 reference={'chart_ppr':'CHART_LEAF_CDF'}
 report={'version':VERSION,'state':'COMPLETED_WITH_RETAINED_FAILURES' if any(c['state']=='FAILED_ATTEMPT_RETAINED' for c in completed) else 'COMPLETED_FROZEN_LAW_COMPARISON','cells':completed,'distribution_scores':summaries,'probability_scores':prob,
  'distribution_pairwise':paired(allnum.loc[allnum.primary_role],'CRPS',reference,loss,plan['uncertainty'],aux._interval) if len(allnum) else [],
  'probability_pairwise':paired(allevents,'Brier',reference,loss,plan['uncertainty'],aux._interval) if len(allevents) else [],
  'selection_policies':selectors(allevents,plan['uncertainty'],aux._interval) if len(allevents) else [],'price_EV':'UNSUPPORTED_NOT_INFERRED','ATD':'Existing separate binary Brier analysis unchanged; numeric helpers reject ATD.',
  'offer_coverage':coverage,'new_fits':0,'model_restorations':restores,'query_law_rows':query_rows,'fixture_row_upper_bound':4*sum(s['kind']=='future' for s in plan['specs']),'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},
  'scope':'2026W1-7 fixed exposed development; depthW7 missing, chart/label restrictions explicit; no site-relative or genuinepregame gain fabricated.','missing_lines':'No actual line means ordinary distribution scoring only.','paper_returns':None,'production_changes':0}
 if report['actual']['RSS_bytes']>caps['RSS_bytes']:raise MemoryError('law replay RSS cap')
 put('OWNED_END.json',enc(bulk()));put('AGGREGATES.json.gz',gzip.compress(enc(report),mtime=0));store.verify_retained_checkpoint();signal.alarm(0);return report

def fictional_checks():
 import numpy as np,pandas as pd
 loss=load('law_outer_fixture_loss',ref(ROOT/'tools/category_topfive_matched12_law_scores_v1.py'))
 p=np.array([[.5,0,.5],[.46,0,.54]])
 with np.errstate(divide='ignore'):events={'support':'count','log_probabilities':np.log(p)}
 assert loss.select_sides(events)['side'].tolist()==['abstain','over']
 assert loss.select_sides(events,minimum_confidence=.55)['side'].tolist()==['abstain','abstain']
 rows=pd.DataFrame([dict(target='rec',season=2026,week=1,game_id='FICTION',player_id=str(i),team='F',opponent='G',cutoff_utc='2026-01-01T00:00:00Z',participation_state=s,actual=0. if i==0 else np.nan,score_state='MISSING_LAW',method='FICT') for i,s in enumerate(['played','unknown','DNP'])])
 offers=rows[OFFER].copy();offers['line']=4.5
 f=pd.concat(missing_law_offers(rows,offers,np),ignore_index=True)
 assert len(f)==6 and f.p_over.isna().all() and f.side.eq('unavailable').all()
 u={'seed':17,'replicates':4,'minimum_clusters':2};reports=selectors(f,u,lambda x,g,u:{'clusters':len(set(g))})
 full=[r for r in reports if r['policy']=='FULL_BOARD']
 assert len(full)==2 and all(r['metrics']['missing_law']==3 and r['metrics']['participation_states']=={'played':1,'unknown':1,'DNP':1} for r in full)
 always=[r for r in reports if r['policy']=='ALWAYS_UNDER']
 assert all(r['metrics']['under']['wins']==1 and r['metrics']['under']['DNP']==1 for r in always)
 return {'state':'PASS_FICTIONAL_ONLY','cases':2,'checks':['P2 exact tie and frozen .55 abstention','Missing law preserves all offers and participation, controls grade supported actuals'],'NFL_models_labels_inference':0}

def fixed_format_checks(fresh_only=False):
 import tempfile
 checks=[]
 with tempfile.TemporaryDirectory(prefix='matched12-fictional-formats-') as temp:
  for version,state,cellstate,target,familykey in [('matched12-fixed-completion-v1.1','FROZEN_FIXED13_FORECASTS_UNSCORED','FROZEN_HISTORICAL_FORECASTS_UNSCORED','pass_cmp','family'),('matched12-chart-event-fixed-completion-v1','FROZEN_THREE_FINALIST_CELLS','FROZEN_FORECASTS_UNSCORED','chart_ppr','method'),('matched12-chart-event-fresh-cell-v1.1','FROZEN_THREE_FINALIST_CELLS','FROZEN_FORECASTS_UNSCORED','chart_ppr','method')]:
   if fresh_only and version!='matched12-chart-event-fresh-cell-v1.1':continue
   row={'cell_id':target+'__RESPONSE_CDF','target':target,'state':cellstate,familykey:'RESPONSE_CDF'}
   doc={'version':version,'state':state,'cells':[row,{**row,'state':'FAILED_ATTEMPT_PRESERVED'},{**row,familykey:'CATBOOST_MEDIUM'}]}
   assert fixed_cells(doc)==[row]
   body=io.BytesIO()
   with zipfile.ZipFile(body,'w') as z:z.writestr('FORECASTS.parquet',b'FICTIONAL_OPAQUE_NOT_NFL')
   p=Path(temp)/('cell'+str(len(checks))+'.zip');p.write_bytes(body.getvalue());r={**ref(p),'member':'FORECASTS.parquet','member_sha256':sha(b'FICTIONAL_OPAQUE_NOT_NFL')}
   assert table_bytes(r)==b'FICTIONAL_OPAQUE_NOT_NFL'
   checks.append(version+' metadata membership and exact opaque member')
 return {'state':'PASS_FICTIONAL_METADATA_ONLY','cases':len(checks),'checks':checks,'NFL_models_labels_forecasts_decoded':0}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--go',type=Path,required=True);a=p.parse_args()
 print(json.dumps(execute(json.loads(a.plan.read_text()),json.loads(a.go.read_text())),sort_keys=True,allow_nan=False))
