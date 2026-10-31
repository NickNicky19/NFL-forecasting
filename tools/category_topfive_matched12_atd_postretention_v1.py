"""Independently admit retained ATD arithmetic after a resource-failed run.

No refit, forecast, probability transform or bootstrap is performed. The failed
source execution never becomes passed; a new receipt admits only saved outputs.
"""
from pathlib import Path
import argparse,gzip,hashlib,io,json,math,os,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-ATD-postretention-admission-v1'
KEY=['target','season','week','game_id','player_id','team','opponent','cutoff_utc','kickoff_utc']
NEW='ATD_CDF_RETAINED_PLATT_NLL_IDENTITY01'
def enc(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def need(value,message):
 if not value:raise ValueError(message)
def exact(ref):
 p=Path(ref['path']);a=p.stat();need(p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in [p,*p.parents]),'canonical source required');need(a.st_size==ref['bytes']<=16*1024**2,'source size differs');b=p.read_bytes();z=p.stat();need(len(b)==ref['bytes'] and sha(b)==ref['sha256'] and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns),'source identity changed');return b
def safe(r):return {k:r[k] for k in ['bytes','sha256']}
def unpack(raw):
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  names=z.namelist();need(len(names)==len(set(names))<=8,'ambiguous package members');m=json.loads(z.read('MEMBER_MANIFEST.json'));need(set(names)==set(m)|{'MEMBER_MANIFEST.json'},'unmanifested package member');out={}
  for k,r in m.items():
   need(z.getinfo(k).file_size==r['bytes']<=16*1024**2,'member size differs');b=z.read(k);need(sha(b)==r['sha256'],'member hash differs');out[k]=b
 return out,m
def same(a,b):
 if a is None or b is None:return a is b
 if isinstance(a,(int,float)) and isinstance(b,(int,float)):return math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-13)
 return a==b

def execute(cfg,go):
 started=time.monotonic();cpu=time.process_time()
 need(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root' and go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('configuration_sha256')==sha(enc(cfg)),'exact root/reviewer GO required')
 need(cfg['version']==VERSION and cfg['resources']=={'CPU_seconds':180,'wall_seconds':420,'AS_bytes':4294967296,'RSS_bytes':2147483648} and cfg['private_peak_bytes']==1048576,'registered finite admission envelope changed')
 sys.path.insert(0,str(ROOT));import nfl_lab
 need(Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab','root package binding required')
 from tools import category_topfive_matched12_storage_v1 as storage
 from nfl_lab.owned_reference_batch import validate_owned_references
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 original_cfg=json.loads(gzip.decompress(exact(cfg['original_configuration'])));source_go=json.loads(exact(cfg['original_GO']))
 need(source_go['worker_sha256']==cfg['original_worker_sha256'] and source_go['plan_canonical_sha256']==sha(enc(original_cfg))==cfg['original_canonical_configuration_sha256'],'failed source/configuration GO chain differs')
 failure=json.loads(exact(cfg['original_failure_record']));need(failure['state']=='CPU_LIMIT_TERMINATED_EXIT152_EVIDENCE_RETAINED' and failure['CPU_limit_consumed_seconds']==120,'original failed status must stay failed')
 source_dir=Path(cfg['result']['path']).parent;need(not (source_dir/'COMPLETE.json').exists(),'unexpected completion added to resource-failed source')
 store,_=storage.open_store(ROOT,allocation_sha256=original_cfg['allocation_sha256'],root_go=storage.GO,readonly=True)
 original_keys=['parent_bundle','parent_freeze','new_bundle','new_complete','queries','label_package','label_admission','original_grade_bundle','original_grade_complete']
 refs={original_cfg[k]['path']:original_cfg[k]['sha256'] for k in original_keys}
 refs.update({cfg[k]['path']:cfg[k]['sha256'] for k in ['result','forecast_freeze','source_started']})
 # One fresh owned batch; its unchanged implementation scans at entry and exit.
 # No redundant post-scoring batch or verify_retained_checkpoint is performed.
 _,audit=validate_owned_references(store,refs)
 slug=cfg['run_id'];need(slug.startswith('matched12-atd-postretention-') and '/' not in slug and '..' not in slug,'new admission namespace required');out=store.forward_root/'research'/slug;need(not out.exists(),'consumed admission attempt cannot rerun');store.register_root(out);used=0
 def put(name,body,terminal=False):
  nonlocal used
  need(used+len(body)+cfg['external_metadata_charge_bytes']+(0 if terminal else 65536)<=cfg['private_peak_bytes'],'private admission evidence envelope exhausted')
  store.write_bytes(out/name,body);used+=len(body);r=store.validate_reference(out/name,sha(body));return safe(r)
 put('STARTED.json',enc({'state':'STARTED_NEW_POSTRETENTION_ADMISSION_BEFORE_CACHED_OUTCOME_READ','source_result_sha256':cfg['result']['sha256'],'worker_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'original_execution_state':failure['state'],'new_fits_inference_transforms_bootstrap_HTTP':0}))
 try:
  source_started=json.loads(exact(cfg['source_started']));need(source_started['worker_sha256']==cfg['original_worker_sha256'] and source_started['plan_sha256']==cfg['original_canonical_configuration_sha256'],'original STARTED source/config binding differs')
  parts,members=unpack(exact(cfg['result']));frozen,frozen_members=unpack(exact(cfg['forecast_freeze']));run=json.loads(parts['RUN_STATE.json']);need(run['worker_sha256']==cfg['original_worker_sha256'] and run['plan_sha256']==cfg['original_canonical_configuration_sha256'],'saved result producer differs')
  bindings=json.loads(frozen['FROZEN_INPUT_BINDINGS.json']);need(bindings['source_sha256']==cfg['original_worker_sha256'] and bindings['plan_sha256']==cfg['original_canonical_configuration_sha256'] and bindings['original_global_four_unchanged'] and bindings['labels_not_read'],'supplement freeze chain differs')
  report=json.loads(gzip.decompress(parts['AGGREGATES.json.gz']));need(report['version']=='matched12-ATD-late-five-cached-score-v1' and report['state']=='COMPLETE_LATE_ATD_FIVE_PROCEDURE_APPENDIX','saved calculation state differs');need(report['forecast_freeze']==safe(cfg['forecast_freeze']) and report['forecast_freeze_members']==frozen_members,'result/freeze content chain differs')
  report_scope=report['scope'];need(report_scope['seasons']==[2026] and report_scope['weeks']==list(range(1,8)) and report_scope['targets']==['anytime_td'] and report['labels_sha256']==original_cfg['label_member']['sha256'],'evaluation scope/outcome version differs')
  def table(b):return pq.read_table(io.BytesIO(b),use_threads=False).to_pandas(use_threads=False)
  primary=table(parts['PRIMARY_POINTS.parquet']);full=table(parts['ALL_POINTS.parquet']);forecasts=table(frozen['FORECASTS.parquet']);expected=table(frozen['EXPECTED_POPULATION.parquet'])
  for f in [primary,full,forecasts,expected]:
   need(f.target.eq('anytime_td').all() and f.season.eq(2026).all() and f.week.between(1,7).all(),'outside fixed target/season/week scope')
   for c in ['cutoff_utc','kickoff_utc']:f[c]=pd.to_datetime(f[c],utc=True,errors='raise')
  need(len(primary)==25602 and len(full)==29910 and len(forecasts)==29910 and len(expected)==4985,'saved complete population count differs')
  need(primary.position.isin(['RB','WR','TE']).all() and full.position.isin(['QB','RB','FB','WR','TE']).all(),'role scope differs')
  need(expected.game_id.nunique()==107 and expected.week.nunique()==7 and not expected.duplicated(KEY).any(),'expected games/weeks/opportunities differ')
  joint=KEY+['method','product'];need(not full.duplicated(joint).any() and not primary.duplicated(joint).any() and not forecasts.duplicated(joint).any(),'duplicate output opportunity')
  matches=full.merge(forecasts[joint+['prediction']],on=joint,how='outer',suffixes=('','_frozen'),indicator=True,validate='one_to_one');need(matches._merge.eq('both').all() and np.array_equal(matches.prediction.to_numpy(float),matches.prediction_frozen.to_numpy(float),equal_nan=True),'graded predictions changed from frozen vectors')
  h=primary.merge(full[joint+['prediction','actual','participation_state']],on=joint,how='left',validate='one_to_one',suffixes=('','_all'));need(np.array_equal(h.prediction.to_numpy(float),h.prediction_all.to_numpy(float),equal_nan=True) and np.array_equal(h.actual.to_numpy(float),h.actual_all.to_numpy(float),equal_nan=True) and h.participation_state.eq(h.participation_state_all).all(),'primary/full values differ')
  method_groups={v['shortlist_group'] for v in report['catalog']['anytime_td'].values()};need(len(method_groups)==5 and NEW in method_groups,'five distinct procedures required')
  def metric(v,claim):
   p=v.prediction.to_numpy(float);y=v.actual.to_numpy(float);state=v.participation_state.fillna('unknown');need(state.isin(['played','unknown','dnp']).all(),'unregistered participation state');good=state.eq('played').to_numpy()&np.isfinite(p)&np.isfinite(y);fb=v.fallback.fillna('').astype(str).ne('').to_numpy();pp,yy=p[good],y[good];need(((pp>=0)&(pp<=1)).all() and np.isin(yy,[0,1]).all(),'invalid binary values');need(not (state.ne('played').to_numpy()&np.isfinite(y)).any(),'unknown participation became a numeric outcome')
   counts={'planned':len(v),'scored':int(good.sum()),'missing_prediction':int((~np.isfinite(p)).sum()),'unknown_participation':int(state.eq('unknown').sum()),'played_missing':int((state.eq('played').to_numpy()&~np.isfinite(y)).sum()),'DNP':int(state.eq('dnp').sum()),'fallback_planned':int(fb.sum()),'fallback_scored':int((fb&good).sum()),'played_zero':int((good&(y==0)).sum()),'games':int(v.loc[good,'game_id'].nunique()),'weeks':int(v.loc[good,'week'].nunique())}
   need(all(claim[k]==n for k,n in counts.items()),'probability count or coverage differs');prob=claim['probability_scores'];brier=float(np.mean((pp-yy)**2)) if len(pp) else None;need(same(prob['Brier'],brier) and same(claim['MSE'],brier),'binary Brier arithmetic differs');need(all(claim[k] is None for k in ['MAE','RMSE','bias','p90_AE','p95_AE']),'ATD incorrectly ranked as numeric point')
   if len(pp):
    with np.errstate(divide='ignore',invalid='raise'):ll=np.where(yy==1,-np.log(pp),-np.log1p(-pp))
    inf=int(np.isposinf(ll).sum());loss=prob['log_loss'];need(loss['state']==('POSITIVE_INFINITY' if inf else 'FINITE') and loss['positive_infinite_rows']==inf and same(loss['value'],None if inf else float(ll.mean())),'log loss or impossible-event population differs');need(same(claim['probability_bias'],float((pp-yy).mean())),'probability bias differs')
    for i,c in enumerate(prob['reliability']):
     take=(pp>=i/10)&((pp<(i+1)/10) if i<9 else pp<=1);need(c['n']==int(take.sum()) and same(c['mean_probability'],float(pp[take].mean()) if take.any() else None) and same(c['event_rate'],float(yy[take].mean()) if take.any() else None),'reliability bin differs')
   else:need(prob['log_loss']['state']=='UNAVAILABLE','missing score must remain unavailable')
   return {'n':len(pp),'Brier':brier,'log_loss':prob['log_loss']}
  checks=weekly_checks=0;methods=[]
  for name,frame in [('primary',primary),('full_secondary',full)]:
   groups={k:v for k,v in frame.groupby(['method','product'],sort=False)};base=groups[('LEAF_CDF','probability_normalized')];valid=base.participation_state.eq('played')&np.isfinite(base.prediction.to_numpy(float))&np.isfinite(base.actual.to_numpy(float));core=base.loc[valid,KEY]
   need(len(core)==(2000 if name=='primary' else 2241),'common support count changed')
   for r in report[name]['records']:
    v=groups[(r['method'],r['product'])]
    if r['scope']=='PREDECLARED_PRIMARY_COMMON_CORE':v=v.merge(core,on=KEY,validate='one_to_one');need(r['joint_finite_played_rows']==len(core) and r['headline_eligible'],'core eligibility differs')
    else:need(r['scope']=='FULL_REGISTERED_METHOD_POPULATION','unknown score scope')
    result=metric(v,r['metrics']);checks+=1
    if name=='primary' and r['scope']=='PREDECLARED_PRIMARY_COMMON_CORE':methods.append({'method':r['method'],'product':r['product'],**result})
    for w in r.get('weekly',[]):metric(v.loc[v.week.eq(w['week'])],w['metrics']);weekly_checks+=1
  paired_checks=0
  def check_pair(frame,candidate,control,claim):
   left=frame.loc[frame.method.eq(candidate[0])&frame['product'].eq(candidate[1]),KEY+['prediction','actual','participation_state']];right=frame.loc[frame.method.eq(control[0])&frame['product'].eq(control[1]),KEY+['prediction','actual','participation_state']];j=left.merge(right,on=KEY,suffixes=('_a','_b'),validate='one_to_one');take=j.participation_state_a.eq('played')&j.participation_state_b.eq('played')&np.isfinite(j[['prediction_a','prediction_b','actual_a','actual_b']].to_numpy(float)).all(axis=1);j=j.loc[take];need(np.array_equal(j.actual_a.to_numpy(),j.actual_b.to_numpy()),'paired outcomes differ');ca=(j.prediction_a-j.actual_a)**2;co=(j.prediction_b-j.actual_b)**2;diff=ca-co;need(claim['paired_rows']==len(j) and same(claim['candidate_loss'],float(ca.mean())) and same(claim['control_loss'],float(co.mean())) and same(claim['candidate_minus_control'],float(diff.mean())),'paired Brier arithmetic differs');need(same(claim['improvement_percent'],100*(float(co.mean())-float(ca.mean()))/float(co.mean()) if float(co.mean()) else None),'relative difference differs')
   for c in ['game_id','week']:
    x=claim['intervals'][c];need(x['clusters']==j[c].astype(str).nunique(),'paired cluster count differs')
    if x['clusters']>=2:need(x['replicates']==1000 and x['seed']==20261030 and math.isfinite(x['lower']) and math.isfinite(x['upper']) and x['lower']<=x['upper'],'stored bootstrap metadata differs')
  for name,frame in [('primary',primary),('full_secondary',full)]:
   for r in report[name]['pairwise']:check_pair(frame,r['candidate'],r['reference'],r['primary']);paired_checks+=1
  for r in report['late_vs_each_retained_control']:check_pair(primary if r['population']=='primary_RB_WR_TE' else full,[NEW,'probability'],r['control'],r['Brier']);paired_checks+=1
  # Reconcile the same old-control Brier/count records with the immutable global comparison.
  old_complete=json.loads(exact(original_cfg['original_grade_complete']));need(old_complete['result']==safe(original_cfg['original_grade_bundle']),'old global terminal changed')
  with zipfile.ZipFile(io.BytesIO(exact(original_cfg['original_grade_bundle']))) as z:
   raw=z.read('AGGREGATES.json.gz');identity=old_complete['members']['AGGREGATES.json.gz'];need(len(raw)==identity['bytes'] and sha(raw)==identity['sha256'],'old aggregate hash differs');old=json.loads(gzip.decompress(raw))
  preserved=0
  for new_name,old_name in [('primary','headline_numeric'),('full_secondary','all_attempted_roles_secondary')]:
   for r in report[new_name]['records']:
    if r['method']==NEW:continue
    found=[x for x in old[old_name]['records'] if x['target']=='anytime_td' and all(x[k]==r[k] for k in ['method','product','scope'])];need(len(found)==1,'old control record missing');m=found[0]['metrics'];need(m['planned']==r['metrics']['planned'] and m['scored']==r['metrics']['scored'] and same(m['probability_scores']['Brier'],r['metrics']['probability_scores']['Brier']),'original control score changed');preserved+=1
  need(preserved==report['old_control_records_verified_unchanged'],'old-control verification count differs')
  actual={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};need(all(actual[k]<=cfg['resources'][k] for k in ['CPU_seconds','wall_seconds','RSS_bytes']),'admission resource envelope exceeded')
  receipt={'version':VERSION,'state':'POSTRETENTION_CACHED_OUTPUTS_ADMITTED_ORIGINAL_EXECUTION_REMAINS_RESOURCE_FAILED','original_execution_state':failure['state'],'original_CPU_charge_preserved':120,'source_result':safe(cfg['result']),'source_forecast_freeze':safe(cfg['forecast_freeze']),'worker_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'independent_cached_checks':{'metric_records':checks,'weekly_records':weekly_checks,'paired_records':paired_checks,'old_control_records_unchanged':preserved,'full_output_rows':len(full),'primary_output_rows':len(primary),'same_primary_supported_player_games':2000,'same_secondary_supported_player_games':2241,'games':107,'weeks':7,'source_freeze_predictions_exact':True,'all_package_members_exact':True},'primary_observed_probability_results':methods,'owned_authentication':{'references':len(refs),'full_scans':audit['full_scan_calls'],'scope':'One unchanged fresh owned batch; no duplicate batch/end inventory'},'actual_before_terminal':actual,'new_fits_inference_probability_transforms_bootstrap_HTTP':0,'limitations':['Independent cached arithmetic/admission, not a completed original run or new forecast.','Bootstrap endpoints not resimulated; only paired point scores and cluster metadata checked.','Older Platt training acceptance remains not independently reproduced; no new parameter/source qualification.','Late exposed reconstruction, not original frozen five or genuine pregame evidence; no market/EV/live claim.']}
  complete=put('COMPLETE.json',enc(receipt),terminal=True);actual={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};need(all(actual[k]<=cfg['resources'][k] for k in ['CPU_seconds','wall_seconds','RSS_bytes']),'postterminal resource failure overrides admission')
  return {**receipt,'complete':complete,'actual':actual,'postterminal_resource_admission':'PASS_AFTER_DURABLE_RECEIPT_READBACK','private_new_bytes':used}
 except BaseException as error:
  failure={'version':VERSION,'state':'FAILED_NEW_ADMISSION_ORIGINAL_OUTPUTS_UNCHANGED','error_type':type(error).__name__,'error_sha256':sha(str(error).encode()),'private_error':str(error),'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started},'new_fits_inference_transforms_bootstrap_HTTP':0}
  put('FAILURE.json',enc(failure),terminal=True);raise

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--plan-sha256',required=True);parser.add_argument('--go',type=Path,required=True);parser.add_argument('--go-sha256',required=True);args=parser.parse_args()
 for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 cfg=json.loads(gzip.decompress(exact({'path':str(args.plan),'bytes':args.plan.stat().st_size,'sha256':args.plan_sha256})));go=json.loads(exact({'path':str(args.go),'bytes':args.go.stat().st_size,'sha256':args.go_sha256}));caps=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(caps['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('postretention admission wall budget')));signal.alarm(caps['wall_seconds']);sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('offline admission only')) if e in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None);result=execute(cfg,go);print(enc(result).decode(),flush=True);signal.alarm(0)
if __name__=='__main__':main()
