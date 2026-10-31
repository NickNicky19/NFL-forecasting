"""ATD-only late-entrant appendix; original global comparison stays immutable.

All inference already frozen. Exact root GO precedes any probabilities/labels.
Same played-conditional event, primary roles, outcomes and issue horizon. No fits.
"""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,io,json,math,os,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-ATD-late-five-cached-score-v1'
NEW='ATD_CDF_RETAINED_PLATT_NLL_IDENTITY01'
CTX=['season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc']
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def exact(r):
 p=Path(r['path']);a=p.stat();assert p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in [p,*p.parents]) and a.st_size==r['bytes']<=16*1024**2;b=p.read_bytes();z=p.stat();assert len(b)==r['bytes'] and sha(b)==r['sha256'] and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns);return b

def load(r,name):
 exact(r);s=importlib.util.spec_from_file_location(name,r['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def safe(r):return {k:r[k] for k in ['bytes','sha256']}
def parquet(f):
 import pyarrow as pa,pyarrow.parquet as pq
 b=io.BytesIO();pq.write_table(pa.Table.from_pandas(f,preserve_index=False,nthreads=1),b,compression='zstd');return b.getvalue()
def pack(m):
 hashes={k:{'bytes':len(v),'sha256':sha(v)} for k,v in m.items()};b=io.BytesIO()
 with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for k,v in {**m,'MEMBER_MANIFEST.json':enc(hashes)}.items():z.writestr(k,v)
 return b.getvalue(),hashes

def execute(cfg,go):
 S=time.monotonic();C=time.process_time();assert go['state']=='ROOT_AND_INDEPENDENT_GO' and go['registered_by']=='/root' and go['worker_sha256']==sha(Path(__file__).read_bytes()) and go['plan_canonical_sha256']==sha(enc(cfg));assert cfg['version']==VERSION and cfg['private_peak_bytes']==1048576 and cfg['external_metadata_charge_bytes']==65536
 for r in cfg['source_pins'].values():exact(r)
 sys.path.insert(0,str(ROOT));import nfl_lab
 from nfl_lab import data,features,cdf_engine
 assert Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab'
 scorer=load(cfg['source_pins']['scorer'],'lateATD_scorer');primary=load(cfg['source_pins']['primary'],'lateATD_primary');helper=load(cfg['source_pins']['storage_helper'],'lateATD_storage');store,_=helper.open_store(ROOT,allocation_sha256=cfg['allocation_sha256'],root_go=helper.GO)
 from nfl_lab.owned_reference_batch import validate_owned_references
 refs={cfg[k]['path']:cfg[k]['sha256'] for k in ['parent_bundle','parent_freeze','new_bundle','new_complete','queries','label_package','label_admission','original_grade_bundle','original_grade_complete']};validate_owned_references(store,refs)
 slug=cfg['run_id'];assert slug.startswith('matched12-atd-late-score-') and '/' not in slug and '..' not in slug;out=store.forward_root/'research'/slug;assert not out.exists();store.register_root(out);written=0;artifacts={}
 def put(name,b,terminal=False):
  nonlocal written
  assert written+len(b)+(0 if terminal else 65536)+cfg['external_metadata_charge_bytes']<=cfg['private_peak_bytes'];store.write_bytes(out/name,b);r=store.validate_reference(out/name,sha(b));written+=len(b);artifacts[name]=safe(r);return r
 put('STARTED.json',enc({'state':'STARTED_BEFORE_CACHED_PROBABILITY_AND_OUTCOME_READ','worker_sha256':go['worker_sha256'],'plan_sha256':go['plan_canonical_sha256'],'fits_transforms_HTTP':0}))
 bodies={}
 def body(r):
  if r['path'] not in bodies:bodies[r['path']]=exact(r)
  return bodies[r['path']]
 def member(r,name,identity):
  with zipfile.ZipFile(io.BytesIO(body(r))) as z:
   n=z.getinfo(name);assert n.file_size==identity['bytes']<=16*1024**2;b=z.read(name)
  assert sha(b)==identity['sha256'];return b
 try:
  import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
  pa.set_cpu_count(1);pa.set_io_thread_count(1)
  fdoc=json.loads(body(cfg['parent_freeze']));assert fdoc['forecast_readback_verified'] and fdoc['bundle']==safe(cfg['parent_bundle']);meta=json.loads(member(cfg['parent_bundle'],'CATALOG_SCOPE.json',fdoc['members']['CATALOG_SCOPE.json']));catalog={'anytime_td':meta['catalog']['anytime_td']};assert {v['shortlist_group'] for v in catalog['anytime_td'].values()}=={'LEAF_CDF','CATBOOST_MEDIUM','EQUAL_CDF_CAT_PROBABILITY','ROLE_LOGISTIC'}
  columns=CTX+['target','method','product','prediction','fallback','output_procedure_version'];raw=member(cfg['parent_bundle'],'FORECASTS.parquet',fdoc['members']['FORECASTS.parquet']);frame=pq.read_table(io.BytesIO(raw),columns=columns,filters=[('target','==','anytime_td')],use_threads=False).to_pandas(use_threads=False)
  terminal=json.loads(body(cfg['new_complete']));assert terminal['state']=='LATE_PLATT_TRANSFER_FROZEN_UNSCORED' and len(terminal['cells'])==1;c=terminal['cells'][0];assert c['state']=='FROZEN_FORECASTS_UNSCORED' and c['target']=='anytime_td' and c['method']==NEW and c['bundle']==safe(cfg['new_bundle']) and c['rows']==4985 and c['actual_transform_rows']==4267 and c['unchanged_parent_role_rows']==718
  wide=pq.read_table(io.BytesIO(member(cfg['new_bundle'],'FORECASTS.parquet',c['members']['FORECASTS.parquet'])),use_threads=False).to_pandas(use_threads=False);assert wide.target.eq('anytime_td').all() and wide.method.eq(NEW).all() and wide.procedure_version.eq(c['procedure_version']).all() and len(wide)==4985
  added=wide[CTX+['fallback']].copy();added['target']='anytime_td';added['method']=NEW;added['product']='probability';added['prediction']=wide.probability;added['output_procedure_version']=wide.procedure_version;added['source_forecast_sha256']=cfg['new_bundle']['sha256'];frame=pd.concat([frame,added],ignore_index=True);assert len(frame)==29910
  catalog['anytime_td'][NEW]={'procedure_id':NEW,'procedure_version':c['procedure_version'],'products':['probability'],'shortlist_group':NEW,'late_development_entrant':True,'original_training':'ACCEPTED_2022_2023_OOF_NOT_REPRODUCED','QB_FB':'UNCHANGED_PARENT_ROLE_FALLBACK'}
  queries=pq.read_table(io.BytesIO(body(cfg['queries'])),use_threads=False).to_pandas(use_threads=False);assert len(queries)==4985
  scope={'panel_id':slug,'seasons':[2026],'weeks':list(range(1,8)),'targets':['anytime_td'],'identity_namespace':'GSIS_CANONICAL_PRIMARY_ROSTER','source_policy_id':cfg['source_policy_id'],'outcome_version':cfg['outcome_version'],'evidence_tier':'LATE_EXPOSED_CURRENT_VINTAGE_HISTORICAL_RECONSTRUCTION','horizon_id':cfg['horizon_id'],'primary_core_outputs':{'anytime_td':[['LEAF_CDF','probability_normalized']]},'reference_output':{'anytime_td':['LEAF_CDF','probability_normalized']}}
  expected=primary.expected_population(queries,catalog,{'anytime_td':['QB','RB','FB','WR','TE']},cfg['horizon_id']);assert len(expected)==4985
  frozen={'FORECASTS.parquet':parquet(frame),'EXPECTED_POPULATION.parquet':parquet(expected),'CATALOG_SCOPE.json':enc({'catalog':catalog,'scope':scope}),'FROZEN_INPUT_BINDINGS.json':enc({'source_sha256':go['worker_sha256'],'plan_sha256':go['plan_canonical_sha256'],'parent_bundle':safe(cfg['parent_bundle']),'new_bundle':safe(cfg['new_bundle']),'labels_not_read':True,'original_global_four_unchanged':True,'prospective_or_untouched_confirmation':False})};b,freeze_members=pack(frozen);freeze_ref=put('SUPPLEMENT_FORECAST_FREEZE.zip',b)
  # Only now open the same admitted outcome package; no new labels or zeros.
  admission=json.loads(body(cfg['label_admission']));assert admission['package']==safe(cfg['label_package']) and admission['members']['QUALIFIED_LABELS.parquet']==cfg['label_member']
  labels=pq.read_table(io.BytesIO(member(cfg['label_package'],'QUALIFIED_LABELS.parquet',cfg['label_member'])),filters=[('target','==','anytime_td')],use_threads=False).to_pandas(use_threads=False);assert len(labels)==4985;frame=primary.attach_labels(frame,labels)
  uncertainty={'replicates':1000,'seed':20261030,'minimum_clusters':2};head,h=primary.primary_numeric(frame,expected,labels,catalog,scope,{'anytime_td':['RB','WR','TE']},uncertainty,scorer);full,p=primary.numeric_all_roles(frame,expected,labels,catalog,scope,uncertainty,scorer)
  for report in [head,full]:report['limitations']=['ATD-only late development appendix; original global four-method study remains unchanged.','Earlier curve applied without refitting/tuning; source timing remains reconstruction, unknown outcomes and parent-role fallbacks retained.']
  main=json.loads(body(cfg['original_grade_complete']));assert main['result']==safe(cfg['original_grade_bundle']);old=json.loads(gzip.decompress(member(cfg['original_grade_bundle'],'AGGREGATES.json.gz',main['members']['AGGREGATES.json.gz'])));checked=0
  for newreport,oldreport in [(head,old['headline_numeric']),(full,old['all_attempted_roles_secondary'])]:
   for r in newreport['records']:
    if r['method']==NEW:continue
    rr=[v for v in oldreport['records'] if v['target']=='anytime_td' and v['method']==r['method'] and v['product']==r['product'] and v['scope']==r['scope']];assert len(rr)==1;a,b=r['metrics'],rr[0]['metrics'];assert a['planned']==b['planned'] and a['scored']==b['scored'];x,y=a['probability_scores']['Brier'],b['probability_scores']['Brier'];assert x==y or x is not None and y is not None and math.isclose(x,y,rel_tol=0,abs_tol=1e-14);checked+=1
  late_core=next(r for r in head['records'] if r['method']==NEW and r['scope']=='PREDECLARED_PRIMARY_COMMON_CORE');assert late_core['joint_finite_played_rows']==2000 and late_core['metrics']['scored']==2000 and late_core['headline_eligible']
  extra=[]
  controls=[['LEAF_CDF','probability_normalized'],['CATBOOST_MEDIUM','probability'],['EQUAL_CDF_CAT_PROBABILITY','probability'],['ROLE_LOGISTIC','probability']]
  for population,points in [('primary_RB_WR_TE',h),('all5_roles_secondary',p)]:
   candidate=points.loc[points.method.eq(NEW)]
   for m,k in controls:extra.append({'population':population,'candidate':NEW,'control':[m,k],'Brier':scorer.paired(candidate,points.loc[points.method.eq(m)&points['product'].eq(k)],'Brier',uncertainty)})
  report={'version':VERSION,'state':'COMPLETE_LATE_ATD_FIVE_PROCEDURE_APPENDIX','catalog':catalog,'scope':scope,'primary':head,'full_secondary':full,'late_vs_each_retained_control':extra,'old_control_records_verified_unchanged':checked,'labels_sha256':cfg['label_member']['sha256'],'forecast_freeze':safe(freeze_ref),'forecast_freeze_members':freeze_members,'counts':{'procedures':5,'probability_output_products':6,'frozen_source_rows':len(frame),'full_expected_output_rows':len(p),'primary_expected_output_rows':len(h),'unique_expected_player_game_opportunities':len(expected),'independent_games':int(expected.game_id.nunique()),'independent_weeks':int(expected.week.nunique()),'new_fits_transforms_models_HTTP':0,'cached_scoring_runs':1},'numeric_MAE_mean_median':'NOT_APPLICABLE_BINARY_EVENT_PROBABILITY','price_EV_or_pregame_claim':False,'probability_release':'SEPARATE_RETAINED_PRODUCTION_OWNER_POLICY_AND_OPERATIONAL_ADMISSION','original_C1_finalist':'NOT_ADMITTED; this is a distinct retained identity01curve transfer'}
  outputs={'AGGREGATES.json.gz':gzip.compress(enc(report),9,mtime=0),'PRIMARY_POINTS.parquet':parquet(h),'ALL_POINTS.parquet':parquet(p),'RUN_STATE.json':enc({'state':'COMPLETE_WHEN_THIS_EXACT_ZIP_IS_OWNED_AND_VERIFIED','worker_sha256':go['worker_sha256'],'plan_sha256':go['plan_canonical_sha256'],'new_fits':0})};b,members=pack(outputs);r=put('RESULTS.zip',b);validate_owned_references(store,refs);store.verify_retained_checkpoint()
  def measured():return {'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
  def within(a):return all(a[k]<=cfg['resources'][k] for k in ['CPU_seconds','wall_seconds','RSS_bytes'])
  actual=measured();assert within(actual),'resource envelope exceeded after result persistence; outputs retained'
  terminal={'state':'COMPLETE_OWNED_LATE_ATD_APPENDIX','version':VERSION,'worker_sha256':go['worker_sha256'],'plan_sha256':go['plan_canonical_sha256'],'result':safe(r),'members':members,'freeze':safe(freeze_ref),'counts':report['counts'],'old_control_records_verified_unchanged':checked,'actual_before_terminal_persistence':actual,'completion_admission':'Exact COMPLETE readback and no FAILURE.json; postterminal resource check required','operational_or_offhost_or_prospective_qualification':False}
  complete_ref=put('COMPLETE.json',enc(terminal),terminal=True)
  actual=measured();assert within(actual),'resource envelope exceeded after terminal persistence; FAILURE overrides COMPLETE'
  return {**terminal,'actual':actual,'complete':safe(complete_ref),'private_new_bytes':written,'postterminal_resource_admission':'PASS_AFTER_DURABLE_COMPLETE_READBACK'}
 except BaseException as error:
  d={'state':'FAILED_RETAINED','version':VERSION,'error_type':type(error).__name__,'error_sha256':sha(str(error).encode()),'artifacts':artifacts,'fits_transforms_HTTP':0,'actual':{'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S}}
  try:put('FAILURE.json',enc({**d,'private_error':str(error)}),terminal=True);d['failure_receipt_retained']=True
  except BaseException:d['failure_receipt_retained']=False
  return d

def main():
 a=argparse.ArgumentParser();a.add_argument('--plan',type=Path,required=True);a.add_argument('--plan-sha256',required=True);a.add_argument('--go',type=Path,required=True);a.add_argument('--go-sha256',required=True);v=a.parse_args()
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 cfg=json.loads(gzip.decompress(exact({'path':str(v.plan),'bytes':v.plan.stat().st_size,'sha256':v.plan_sha256})));go=json.loads(exact({'path':str(v.go),'bytes':v.go.stat().st_size,'sha256':v.go_sha256}));cap=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(cap['CPU_seconds'],cap['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(cap['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ATD appendix wall cap')));signal.alarm(cap['wall_seconds']);sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('No network')) if e in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None);r=execute(cfg,go);print(enc(r).decode(),flush=True);signal.alarm(0)
 if r['state']=='FAILED_RETAINED':raise SystemExit(1)
if __name__=='__main__':main()
