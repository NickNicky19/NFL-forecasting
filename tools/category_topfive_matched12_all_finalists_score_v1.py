"""Normalize frozen finalist outputs, freeze their union, then grade one label version.

No fitting, model loading, inference, network or production writes. Mean/median
outputs remain separate products; reconstructed decisions stay reconstructed.
"""
from __future__ import annotations
import argparse,copy,gzip,hashlib,importlib.util,io,json,os,resource,signal,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-all-finalists-normalization-score-v1'
CONTEXT=['season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc']
KEY=['target']+CONTEXT[:6]+CONTEXT[7:]
FINAL_STATES={'FROZEN_HISTORICAL_FORECASTS_NO_SCORES','FROZEN_HISTORICAL_FORECASTS_UNSCORED','FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED','FROZEN_FORECASTS_UNSCORED'}
FAILED_STATES={'FAILED_RETAINED','FAILED_ATTEMPT_PRESERVED','FAILED_OR_INTERRUPTED_RETAINED'}

def encoded(x):
 import numpy as np,pandas as pd
 from decimal import Decimal
 def scalar(v):
  if isinstance(v,np.generic):return v.item()
  if isinstance(v,(pd.Timestamp,Decimal)):return str(v)
  raise TypeError(type(v).__name__)
 return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,default=scalar).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def exact(r):
 p=Path(r['path'])
 if not p.is_absolute() or p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('canonical input required')
 a=p.stat()
 if a.st_size!=r['bytes'] or a.st_size>64*1024**2:raise ValueError('finite input size changed')
 b=p.read_bytes();z=p.stat()
 if sha(b)!=r['sha256'] or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns):raise ValueError('input bytes/identity changed')
 return b
def load(r,name):
 exact(r);s=importlib.util.spec_from_file_location(name,r['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def safe(r):return {k:r[k] for k in ['bytes','sha256']}
def physical(r):return r['container'] if 'container' in r else {k:r[k] for k in ['path','bytes','sha256']}
def selected(d,path):
 for key in path:
  if not isinstance(key,(str,int)) or isinstance(key,bool):raise ValueError('explicit metadata selector required')
  d=d[key]
 return d
def same(a,b):return a.get('sha256')==b['sha256'] and a.get('bytes')==b['bytes']

def prove_entry(e,doc):
 """Exact producer status and raw/member binding, independent of score values."""
 c=selected(doc,e['producer_selector'])
 if c.get('state') not in FINAL_STATES|FAILED_STATES:raise ValueError('running/unresolved producer cannot be graded')
 if c.get('target')!=e['target'] or c.get('cell_id')!=e['producer_cell_id']:raise ValueError('producer cell attribution differs')
 if e['state']=='FAILED':
  if c['state'] not in FAILED_STATES:raise ValueError('failure metadata differs')
  return
 if c['state'] not in FINAL_STATES:raise ValueError('failed producer cannot be successful forecast')
 r=e['forecast']
 if 'container' in r:
  if not same(c.get('bundle',{}),r['container']):raise ValueError('producer cell ZIP differs')
  member=c.get('members',{}).get(r['member'],{})
  if not same(member,r):raise ValueError('producer member differs')
 elif not same(c.get('forecast',{}),r):raise ValueError('producer raw forecast differs')

def canonical_clocks(frame):
 import pandas as pd
 f=frame.copy()
 for c in ['kickoff_utc','cutoff_utc']:
  if c in f:
   if any(pd.Timestamp(x).tzinfo is None for x in f.loc[f[c].notna(),c].drop_duplicates()):raise ValueError('naive canonical clock cannot acquire timezone')
   f[c]=pd.to_datetime(f[c],utc=True,errors='raise')
 return f

def normalize_extra(w,e):
 """Only predeclared metadata/method/period filters; never loss-based filtering."""
 import numpy as np,pandas as pd
 if not set(CONTEXT+['method','procedure_version','fallback'])<=set(w):raise ValueError('frozen output schema incomplete')
 if 'actual' in w and pd.to_numeric(w.actual,errors='coerce').notna().any():raise ValueError('source contains evaluation outcomes; pregrade output required')
 w=canonical_clocks(w.loc[w.method.eq(e['source_method'])])
 if 'target' in w and not w.target.eq(e['target']).all():raise ValueError('forecast target differs')
 if w.empty or w.duplicated(CONTEXT[:4]).any():raise ValueError('empty/duplicate forecast source')
 if not (w.season.eq(2026)&w.week.isin(e['weeks'])).all():raise ValueError('forecast scope outside registered weeks')
 if e['target']=='chart_ppr' and e.get('scoring_contract')!='nick-chart-ppr-v1':raise ValueError('old PPR cannot become chart PPR')
 version_column=e.get('version_column','procedure_version')
 if version_column not in w:raise ValueError('declared output version column missing')
 versions=w[version_column].drop_duplicates().tolist()
 if len(versions)!=1 or not isinstance(versions[0],str) or not versions[0]:raise ValueError('one exact captured procedure version required')
 version=versions[0]
 if e.get('procedure_version') and e['procedure_version']!=version:raise ValueError('declared procedure version differs')
 if len(e['products'])!=len(set(e['products'])) or not e['products']:raise ValueError('declared product mapping required')
 parts=[]
 for product,column in e['products'].items():
  if column not in w:raise ValueError('declared output missing')
  if e['target']=='anytime_td' and product!='probability':raise ValueError('ATD is an event probability, not numeric point')
  f=w[CONTEXT+['fallback']].copy();f['target']=e['target'];f['method']=e['method'];f['product']=product;f['prediction']=pd.to_numeric(w[column],errors='raise')
  if np.isinf(f.prediction.to_numpy(float)).any():raise ValueError('infinite forecast output')
  if e['target']=='anytime_td' and ((f.prediction<0)|(f.prediction>1)).any():raise ValueError('invalid ATD probability')
  f['output_procedure_version']=version;f['source_forecast_sha256']=physical(e['forecast'])['sha256'];f['source_forecast_member_sha256']=e['forecast'].get('sha256') if 'container' in e['forecast'] else None
  f['source_information_policy']=e['information_policy'];f['source_issue_time_UTC']=e.get('source_issue_time_UTC');parts.append(f)
 return pd.concat(parts,ignore_index=True),version

def point_blends(frame,catalog,specs):
 import pandas as pd,numpy as np
 frame=canonical_clocks(frame);parts=[frame]
 for spec in specs:
  target=spec['target'];method=spec['method'];parents=spec['parents'];weights=np.asarray(spec['weights'],float)
  if target=='anytime_td' or len(parents)!=len(weights) or (weights<0).any() or abs(weights.sum()-1)>1e-12:raise ValueError('declared numeric point blend required')
  if method in catalog.get(target,{}):raise ValueError('blend duplicates procedure')
  joined=None;versions=[]
  for i,(parent,product) in enumerate(parents):
   x=frame.loc[frame.target.eq(target)&frame.method.eq(parent)&frame['product'].eq(product)]
   if x.empty:raise ValueError('blend parent absent; do not substitute after outcomes')
   versions.append(catalog[target][parent]['procedure_version'])
   x=x[CONTEXT+['prediction','fallback']].rename(columns={'prediction':'p'+str(i),'fallback':'f'+str(i)})
   joined=x if joined is None else joined.merge(x,on=CONTEXT,how='outer',validate='one_to_one')
  f=joined[CONTEXT].copy();array=joined[['p'+str(i) for i in range(len(parents))]].to_numpy(float);good=np.isfinite(array).all(1)
  f['prediction']=np.where(good,array@weights,np.nan);f['fallback']='';f.loc[~good,'fallback']='MISSING_REGISTERED_BLEND_PARENT'
  for i in range(len(parents)):
   bad=joined['f'+str(i)].fillna('').astype(str).ne('');f.loc[bad&good,'fallback']='REGISTERED_PARENT_FALLBACK'
  version=sha(encoded({'recipe':'fixed_declared_point_average_not_mixture_median','parents':parents,'versions':versions,'weights':weights.tolist()}));f['target']=target;f['method']=method;f['product']='empirical_point_blend';f['output_procedure_version']=version;f['source_information_policy']='EXACT_REGISTERED_PARENT_OUTPUTS';f['source_forecast_sha256']=None
  catalog.setdefault(target,{})[method]={'procedure_id':method,'procedure_version':version,'products':['empirical_point_blend'],'shortlist_group':method,'not_independent_support_of_parents':True};parts.append(f)
 return pd.concat(parts,ignore_index=True)

def make_scope(catalog,p):
 core={};refs={}
 for t in catalog:
  m='CHART_LEAF_CDF' if t=='chart_ppr' else p.get('extra_anchor_methods',{}).get(t,'LEAF_CDF')
  products=['probability_normalized'] if t=='anytime_td' else ['mean','median']
  if m not in catalog[t] or not set(products)<=set(catalog[t][m]['products']):raise ValueError('registered strong source-compatible anchor missing: '+t)
  core[t]=[[m,k] for k in products];refs[t]=[m,products[-1]]
 return {'panel_id':p['run_id'],'seasons':[2026],'weeks':list(range(1,8)),'targets':list(catalog),'identity_namespace':'GSIS_CANONICAL_PRIMARY_ROSTER','source_policy_id':p['source_policy_id'],'outcome_version':p['outcome_version'],'evidence_tier':'CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION','horizon_id':p['horizon_id'],'chart_target_contract':'nick-chart-ppr-v1','primary_core_outputs':core,'reference_output':refs}

def mean_comparisons(points,catalog,controls,scorer,uncertainty):
 rows=[]
 for t,methods in catalog.items():
  if t=='anytime_td':continue
  ref=controls[t];control=points.loc[points.target.eq(t)&points.method.eq(ref[0])&points['product'].eq(ref[1])]
  if control.empty or ref[1] not in ['mean','mean_objective_point']:raise ValueError('declared expected-product reference unavailable')
  for (m,k),v in points.loc[points.target.eq(t)&points['product'].isin(['mean','mean_objective_point'])].groupby(['method','product']):
   rows.append({'target':t,'candidate':[m,k],'reference':ref,'matched_MSE':scorer.paired(v,control,'MSE',uncertainty)})
 return rows

def execute(p,go):
 start=time.monotonic();cpu=time.process_time()
 if go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root' or go.get('worker_sha256')!=sha(Path(__file__).read_bytes()) or go.get('plan_canonical_sha256')!=sha(encoded(p)):raise ValueError('exact root/independent scoring GO required')
 if p['version']!=VERSION:raise ValueError('wrong normalized comparison version')
 for r in p['source_pins'].values():exact(r)
 sys.path.insert(0,str(ROOT));import nfl_lab
 from nfl_lab import data,features,cdf_engine
 if Path(nfl_lab.__file__).resolve().parent!=ROOT/'nfl_lab':raise ValueError('root package required before storage')
 scorer=load(p['source_pins']['scorer'],'allfinal_score');primary=load(p['source_pins']['primary'],'allfinal_primary');aux=load(p['source_pins']['aux'],'allfinal_aux')
 storage=load(p['source_pins']['storage_helper'],'allfinal_storage');store,_=storage.open_store(ROOT,allocation_sha256=p['allocation_sha256'],root_go=storage.GO)
 from nfl_lab.owned_reference_batch import validate_owned_references
 owners=[store,store.complete_peer,store.complete_peer.prior_forward,store.legacy]
 # Original entry/exit quota scans per owner authenticate every alias/body.
 mode=p['execution_mode']
 if mode not in ['FREEZE_ONLY','GRADE_FROZEN']:raise ValueError('explicit finite execution phase required')
 incoming=[p['queries']]
 if mode=='FREEZE_ONLY':
  incoming += [p[k] for k in ['base_flat','base_catalog','base_freeze']]
  for e in p['extra_entries']:
   incoming.append(e['producer_proof'])
   if e['state']=='AVAILABLE':incoming.append(e['forecast'])
 else:
  incoming += [p[k] for k in ['frozen_bundle','frozen_manifest','qualified_labels','label_admission']]
  if p.get('offers'):incoming.append(p['offers'])
 refs={}
 for r in map(physical,incoming):
  if r['path'] in refs and refs[r['path']]!=r:raise ValueError('contradictory input reference')
  refs[r['path']]=r
 groups={i:{} for i in range(len(owners))}
 for path,r in refs.items():
  matches=[i for i,o in enumerate(owners) if any(Path(path).is_relative_to(Path(x)) for x in o._roots)]
  if len(matches)!=1:raise ValueError('one actual source owner required')
  groups[matches[0]][path]=r['sha256']
 auth=[]
 for i,mapping in groups.items():
  if mapping:
   verified,audit=validate_owned_references(owners[i],mapping)
   for path,r in verified.items():
    if r['bytes']!=refs[path]['bytes']:raise ValueError('owned input byte count changed')
   auth.append({'owner_index':i,'references':len(verified),'full_scans':audit['full_scan_calls']})
 bodies={}
 def read(r):
  source=physical(r);key=source['path']
  if key not in bodies:bodies[key]=exact(source)
  b=bodies[key]
  if 'member' not in r:return b
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   info=z.getinfo(r['member'])
   expected=r['bytes'] if 'container' in r else r.get('member_bytes',info.file_size)
   if info.file_size!=expected or info.file_size>32*1024**2:raise ValueError('finite exact member required')
   body=z.read(info)
  if sha(body)!=(r['sha256'] if 'container' in r else r['member_sha256']):raise ValueError('member hash differs')
  return body
 def document(r):
  body=read(r);return json.loads(gzip.decompress(body) if r.get('gzip',False) else body)
 def table(r):
  import pyarrow.parquet as pq
  return pq.read_table(io.BytesIO(read(r)),use_threads=False).to_pandas(use_threads=False)
 slug=p['run_id']
 if not slug.startswith('matched12-all-finalists-') or '/' in slug or '..' in slug:raise ValueError('new scoring namespace required')
 out=store.forward_root/'research'/slug
 if out.exists():raise ValueError('consumed scoring attempt exists')
 store.register_root(out);written=0;artifacts={};caps=p['resources']
 def put(name,body):
  nonlocal written
  if written+len(body)+65536>caps['private_peak_bytes']:raise MemoryError('complete scoring peak exhausted')
  store.write_bytes(out/name,body);ref=store.validate_reference(out/name,sha(body));artifacts[name]=safe(ref);written+=len(body);return ref
 def pack(entries):
  manifest={k:{'bytes':len(v),'sha256':sha(v)} for k,v in entries.items()};entries={**entries,'MEMBER_MANIFEST.json':encoded(manifest)};b=io.BytesIO()
  with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_STORED) as z:
   for k,v in entries.items():z.writestr(k,v)
  return b.getvalue(),manifest
 put('CONSUMED.json',encoded({'state':'BEFORE_FORECAST_OR_LABEL_DECODE','version':VERSION,'plan_sha256':go['plan_canonical_sha256'],'fits_inference_model_restorations_HTTP':0,'input_authentication':auth}))
 try:
  import numpy as np,pandas as pd
  queries=table(p['queries'])
  if mode=='FREEZE_ONLY':
   freeze=document(p['base_freeze'])
   if freeze.get('forecast_readback_verified') is not True:raise ValueError('original base forecasts lack authenticated freeze')
   base=document(p['base_catalog']);catalog=copy.deepcopy(base['catalog']);frame=canonical_clocks(table(p['base_flat']))
   if 'actual' in frame:raise ValueError('base must be original pre-label flattened forecasts')
   for target,g in frame.groupby('target'):
    for method,q in g.groupby('method'):
     if method not in catalog.get(target,{}) or not set(q['product'])<=set(catalog[target][method]['products']):raise ValueError('base catalog identity mismatch')
   frames=[frame];failures=[];source_census=[]
   for e in p['extra_entries']:
    prove_entry(e,document(e['producer_proof']));target=e['target'];method=e['method']
    if method in catalog.get(target,{}):raise ValueError('duplicate procedure; aliases need reconciliation')
    version=e.get('procedure_version')
    if e['state']=='AVAILABLE':
     f,version=normalize_extra(table(e['forecast']),e);frames.append(f);source_census.append({'target':target,'method':method,'rows':len(f),'games':int(f.game_id.nunique()),'weeks':sorted(map(int,f.week.unique())),'source':safe(physical(e['forecast']))})
    elif e['state']=='FAILED':
     if not version:raise ValueError('failed procedure identity missing')
     failures.append({'target':target,'method':method,'reason':e['failure_reason'],'forecast':None})
    else:raise ValueError('running sources cannot silently disappear')
    catalog.setdefault(target,{})[method]={'procedure_id':method,'procedure_version':version,'products':list(e['products']),'shortlist_group':e['shortlist_group'],'information_policy':e['information_policy']}
   frame=pd.concat(frames,ignore_index=True);original_rows=len(frame);frame=point_blends(frame,catalog,p['fixed_point_blends']);derived_rows=len(frame)-original_rows;scope=make_scope(catalog,p)
   mean_controls={t:p.get('expected_mean_controls',{}).get(t,[scope['primary_core_outputs'][t][0][0],'mean']) for t in catalog if t!='anytime_td'}
   for t,(m,k) in mean_controls.items():
    if m not in catalog[t] or k not in catalog[t][m]['products'] or k not in ['mean','mean_objective_point']:raise ValueError('freeze a supported expected-product comparator')
   if frame.duplicated(KEY+['method','product']).any():raise ValueError('duplicate normalized output')
   expected=primary.expected_population(queries,catalog,p['query_roles_by_target'],p['horizon_id'])
   if len(frame)>caps['maximum_output_rows']:raise ValueError('finite normalized row ceiling')
   before={'FORECASTS.parquet':primary_parquet(frame),'EXPECTED_POPULATION.parquet':primary_parquet(expected),'CATALOG_SCOPE.json':encoded({'catalog':catalog,'scope':scope,'source_census':source_census,'failed_entries':failures,'primary_roles':p['primary_roles_by_target'],'query_roles':p['query_roles_by_target'],'derived_blend_rows':derived_rows,'expected_mean_controls':mean_controls})}
   body,before_members=pack(before);fref=put('ALL_FORECASTS_BEFORE_LABELS.zip',body)
   fdoc={'state':'ALL_DECLARED_FINALIST_OUTPUTS_FROZEN_BEFORE_THIS_LABEL_READ','forecast_readback_verified':True,'bundle':safe(fref),'members':before_members,'source_census':source_census,'failed_entries':failures,'evaluation_exposed':True,'original_pregame_issuance':False,'source_queries_sha256':p['queries']['sha256'],'chart_target_contract':'nick-chart-ppr-v1' if 'chart_ppr' in catalog else None,'source_output_rows':len(frame),'derived_blend_rows':derived_rows}
   freeref=put('FORECAST_FREEZE.json',encoded(fdoc));store.verify_retained_checkpoint()
   result={'state':'FROZEN_AWAITING_SEPARATE_LABEL_AND_SCORING_GO','version':VERSION,'forecast_freeze':safe(freeref),'bundle':safe(fref),'members':before_members,'source_output_rows':len(frame),'derived_blend_rows':derived_rows,'fits_inference_model_restorations_labels_scores':0,'artifacts':artifacts,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
   put('COMPLETE.json',encoded(result));store.verify_retained_checkpoint();return result
  fdoc=document(p['frozen_manifest'])
  if fdoc.get('forecast_readback_verified') is not True or not same(fdoc['bundle'],p['frozen_bundle']) or fdoc['source_queries_sha256']!=p['queries']['sha256']:raise ValueError('global frozen input/query binding differs')
  def frozen_member(name):
   r={'container':p['frozen_bundle'],'member':name,**fdoc['members'][name]};return r
  frozen=document(frozen_member('CATALOG_SCOPE.json'));catalog=frozen['catalog'];scope=frozen['scope'];source_census=frozen['source_census'];failures=frozen['failed_entries'];derived_rows=frozen['derived_blend_rows']
  if p['primary_roles_by_target']!=frozen['primary_roles'] or p['query_roles_by_target']!=frozen['query_roles']:raise ValueError('pregame-defined populations cannot change at grading')
  scope['panel_id']=p['run_id'];scope['outcome_version']=p['outcome_version'];frame=table(frozen_member('FORECASTS.parquet'));expected=table(frozen_member('EXPECTED_POPULATION.parquet'))
  # A label qualification is reused/versioned, never inferred from predictions.
  admission=document(p['label_admission'])
  label_claim=selected(admission,p['label_admission_selector'])
  if not same(label_claim,p['qualified_labels']):raise ValueError('canonical qualified label admission differs')
  labels=table(p['qualified_labels']);frame=primary.attach_labels(frame,labels)
  headline,head_points=primary.primary_numeric(frame,expected,labels,catalog,scope,p['primary_roles_by_target'],p['uncertainty'],scorer)
  allroles,all_points=primary.numeric_all_roles(frame,expected,labels,catalog,scope,p['uncertainty'],scorer)
  sides={'state':'NO_RECORDED_LINES_ADMITTED'};side_rows=None
  if p.get('offers'):
   offer_api=load(p['source_pins']['offer_driver'],'allfinal_offers');offers=offer_api.scoring_projection(table(p['offers']));sides,side_rows=primary.primary_side_replay(all_points,offers,p,scope,scorer,aux)
  headline['limitations']=['All declared frozen finalists on the same fixed2026W1-7 primary roles and labels; source timing remains reconstruction.','Missing outputs/outcomes remain explicit; partial candidates cannot claim a complete-panel rank.']
  headline['expected_product_MSE_comparisons']=mean_comparisons(head_points,catalog,frozen['expected_mean_controls'],scorer,p['uncertainty'])
  leaders=[]
  for target in catalog:
   valid=[r for r in headline['records'] if r['target']==target and r['scope']=='PREDECLARED_PRIMARY_COMMON_CORE' and r.get('headline_eligible')]
   point=[r for r in valid if r['metrics']['MAE'] is not None];prob=[r for r in valid if target=='anytime_td' and r['metrics'].get('probability_scores',{}).get('Brier') is not None]
   mean=[r for r in valid if r['product'] in ['mean','mean_objective_point'] and r['metrics']['MSE'] is not None]
   def lowest(rows,key):
    if not rows:return None
    r=min(rows,key=lambda r:(key(r),r['method'],r['product']));return {'method':r['method'],'product':r['product'],'loss':key(r),'scored':r['metrics']['scored'],'status':'OBSERVED_EXPOSED_DEVELOPMENT_NOT_RELEASE_DECISION'}
   leaders.append({'target':target,'lowest_MAE':lowest(point,lambda r:r['metrics']['MAE']),'lowest_expected_product_MSE':lowest(mean,lambda r:r['metrics']['MSE']),'lowest_ATD_Brier':lowest(prob,lambda r:r['metrics']['probability_scores']['Brier']),'procedures':len({v['shortlist_group'] for v in catalog[target].values()}),'website_procedure':'UNVERIFIED_BY_THIS_RESEARCH_COMPARISON','operational_admission':'SEPARATE_RETAINED_OWNER_ACTION'})
  report={'version':VERSION,'state':'COMPLETED_NORMALIZED_FINALIST_COMPARISON','run_id':p['run_id'],'scope':scope,'headline_numeric':headline,'all_attempted_roles_secondary':allroles,'recorded_line_point_decisions':sides,'observed_leaders':leaders,'catalog':catalog,'source_census':source_census,'failed_entries':failures,'counts':{'new_fits':0,'new_model_inference':0,'new_forecasts_from_model':0,'derived_blend_rows_already_frozen':derived_rows,'scoring_runs':1,'source_output_rows':len(frame),'materialized_all_output_rows':len(all_points),'query_rows':len(queries),'independent_games':int(queries.game_id.nunique()),'independent_weeks':int(queries.week.nunique())},'limitations':['Same exposed2026W1-7 cases; older and genuinely pregame panels remain separate.','Missing outputs materialized; partial-week candidates cannot win a complete core panel.','Point-only candidates have no invented PMF/probability orEV.','Numeric-MAE leaders do not select probability/EV rankings or establish live deployment.','Full offering board intersects declared queries; original website leans/TopPicks remain a different evidence table.','Five procedure groups can share trained components; outputs are not independent NFL observations.']}
  aggregate=gzip.compress(encoded(report),9,mtime=0)
  if len(aggregate)>caps['aggregate_compressed_bytes']:raise MemoryError('aggregate forward cap exhausted')
  outputs={'PRIMARY_POINTS.parquet':primary_parquet(head_points),'ALL_POINTS.parquet':primary_parquet(all_points),'AGGREGATES.json.gz':aggregate}
  if side_rows is not None:outputs['DIRECTIONS.parquet']=primary_parquet(side_rows)
  body,members=pack(outputs);result_ref=put('RESULTS.zip',body);store.verify_retained_checkpoint()
  result={'version':VERSION,'state':'COMPLETE_LOCAL_OWNED_READBACK_FRESH_PROCESS_QA_PENDING','result':safe(result_ref),'members':members,'artifacts':artifacts,'counts':report['counts'],'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'offhost_restore':'NOT_VERIFIED','production_changes':0}
  put('COMPLETE.json',encoded(result));store.verify_retained_checkpoint();return result
 except BaseException as e:
  failure={'version':VERSION,'run_id':p['run_id'],'state':'FAILED_RETAINED','error_type':type(e).__name__,'error_sha256':sha(str(e).encode()),'artifacts':artifacts,'fits_inference_models_HTTP':0,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start}}
  try:put('FAILURE.json',encoded({**failure,'private_error':str(e)}))
  except BaseException:pass
  return failure

def primary_parquet(frame):
 import pyarrow as pa,pyarrow.parquet as pq
 f=canonical_clocks(frame)
 if 'line' in f:f['line']=f.line.map(lambda x:None if x is None or str(x)=='nan' else str(x))
 b=io.BytesIO();pq.write_table(pa.Table.from_pandas(f,preserve_index=False,nthreads=1),b,compression='zstd');return b.getvalue()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--plan-sha256',required=True);ap.add_argument('--go',type=Path,required=True);ap.add_argument('--go-sha256',required=True);a=ap.parse_args();sys.dont_write_bytecode=True
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 p=json.loads(gzip.decompress(exact({'path':str(a.plan),'bytes':a.plan.stat().st_size,'sha256':a.plan_sha256})));go=json.loads(exact({'path':str(a.go),'bytes':a.go.stat().st_size,'sha256':a.go_sha256}));caps=p['resources']
 resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(caps['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('allfinal scoring wall cap')));signal.alarm(caps['wall_seconds'])
 sys.addaudithook(lambda event,args:(_ for _ in ()).throw(RuntimeError('zero network scoring')) if event in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None)
 import pyarrow as pa
 pa.set_cpu_count(2);pa.set_io_thread_count(2);r=execute(p,go);print(encoded(r).decode(),flush=True);signal.alarm(0)
 if r['state']=='FAILED_RETAINED':raise SystemExit(1)
if __name__=='__main__':main()
