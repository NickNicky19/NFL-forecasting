"""Late development replay of an accepted earlier Platt curve; never C1.

Only root GO permits frozen parent probability reads. No fitting, outcome reads,
model unpickling, network, live capture or production writes. Original source
files and their native accounting stay intact; newly retained bytes use CAS.
"""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,io,json,os,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-atd-retained-normalized-event-platt-v1'
METHOD='ATD_CDF_RETAINED_PLATT_NLL_IDENTITY01'
PARAM_SHA='80981410dc96c920cdf79fb2e7c3b7d5a0df0edfea4ac9307c99a0ded94fd5a7'
CLASS_SHA='0806235bef8e981ead8bd694dba73430a78628de62f810d3a2846b48028b117b'
CTX=['season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc']
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def exact(r):
 p=Path(r['path']);assert p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in [p,*p.parents]);a=p.stat();assert a.st_size==r['bytes']<=16*1024**2;b=p.read_bytes();z=p.stat();assert len(b)==r['bytes'] and sha(b)==r['sha256'] and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns);return b

def load(r,name):
 exact(r);s=importlib.util.spec_from_file_location(name,r['path']);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def safe(r):return {k:r[k] for k in ['bytes','sha256']}
def parquet(f):
 import pyarrow as pa,pyarrow.parquet as pq
 b=io.BytesIO();pq.write_table(pa.Table.from_pandas(f,preserve_index=False,nthreads=1),b,compression='zstd');return b.getvalue()
def pack(members):
 meta={k:{'bytes':len(v),'sha256':sha(v)} for k,v in members.items()};b=io.BytesIO()
 with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for k,v in {**members,'MEMBER_MANIFEST.json':enc(meta)}.items():z.writestr(k,v)
 return b.getvalue(),meta

def restore_curve(parameter_body,class_module):
 d=json.loads(parameter_body);assert sha(parameter_body)==PARAM_SHA and d['version']=='anytime-calibration-v1-20261025' and d['method']=='platt' and d['audit']['state']=='FITTED' and d['audit']['supported_rows']==10156 and d['audit']['penalty']==.01 and not d['knots'] and not d['values'];return class_module.Calibrator.from_manifest(d)

def transform(curve,p,roles):
 import numpy as np
 p=np.asarray(p,dtype=float);roles=np.asarray(roles);assert p.ndim==roles.ndim==1 and len(p)==len(roles);active=np.isin(roles,['RB','WR','TE']);q=p.copy();q[active]=curve.predict(p[active]);return q,active

def execute(cfg,go):
 S=time.monotonic();C=time.process_time();assert go['state']=='ROOT_AND_INDEPENDENT_GO' and go['registered_by']=='/root' and go['worker_sha256']==sha(Path(__file__).read_bytes()) and go['plan_canonical_sha256']==sha(enc(cfg));assert cfg['version']==VERSION and cfg['method']==METHOD and cfg['maximum_actual_transform_rows']==4985 and cfg['maximum_new_fit_calls']==0 and cfg['private_peak_bytes']==1048576
 for r in cfg['source_pins'].values():exact(r)
 assert cfg['source_pins']['calibrator']['sha256']==CLASS_SHA and cfg['parameters']['sha256']==PARAM_SHA and cfg['native_hold']['retained_bytes']==3333279 and cfg['native_hold']['files']==84 and cfg['native_hold']['original_cap_bytes']==16777216
 params=exact(cfg['parameters']);proofs={k:exact(v) for k,v in cfg['proofs'].items()}
 # These proofs deliberately do not claim a recovered full execution manifest.
 completion=json.loads(proofs['old_calibration_completion.json']);freeze=json.loads(proofs['old_calibration_freeze.json']);rel='2024/fresh_cdf/platt/calibrator.json';assert completion['bindings'][rel]==freeze['bindings'][rel]==PARAM_SHA and completion['manifest_sha256']==cfg['unrestored_original_execution_manifest_sha256']
 attempt=json.loads(proofs['old_attempt.json']);assert attempt['training_years']==[2022,2023] and attempt['eligible_rows']==10156 and attempt['cutoff_utc']=='2024-09-06T00:20:00+00:00'
 public=json.loads(proofs['accepted_public_results.json']);found=[x for x in public['model_coefficients'] if x['base']=='fresh_cdf' and x['method']=='platt' and x['evaluation_year']==2024];assert len(found)==1 and found[0]['model_manifest_sha256']==PARAM_SHA
 sys.path.insert(0,str(ROOT));import nfl_lab
 from nfl_lab import data,features,cdf_engine
 assert Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab'
 helper=load(cfg['source_pins']['storage_helper'],'retained_atd_store');store,_=helper.open_store(ROOT,allocation_sha256=cfg['allocation_sha256'],root_go=helper.GO)
 from nfl_lab.owned_reference_batch import validate_owned_references
 validate_owned_references(store,{cfg[k]['path']:cfg[k]['sha256'] for k in ['parent_bundle','parent_freeze']})
 out=store.forward_root/'research'/cfg['run_id'];assert cfg['run_id'].startswith('matched12-atd-retained-platt-') and not out.exists() and '/' not in cfg['run_id'] and '..' not in cfg['run_id'];store.register_root(out);written=0;artifacts={}
 def put(name,b,*,terminal=False):
  nonlocal written
  assert written+len(b)+(0 if terminal else 65536)+785+cfg['external_metadata_charge_bytes']<=cfg['private_peak_bytes'];store.write_bytes(out/name,b);r=store.validate_reference(out/name,sha(b));written+=len(b);artifacts[name]=safe(r);return r
 admission={'PARAMETERS.json':params,**proofs,'CALIBRATOR_SOURCE.py':exact(cfg['source_pins']['calibrator']),'CONSUMED.json':enc({'state':'BEFORE_CURRENT_FORECAST_READ','version':VERSION,'cfg_sha256':go['plan_canonical_sha256'],'native_original_held_unchanged':cfg['native_hold'],'new_parameter_copy_bytes':785,'original_execution_manifest_body':'NOT_REPRODUCED','training_claim':'ACCEPTED_ORIGINAL_TRAINING_NOT_REPRODUCED','future_live_operational_admission':False})};b,manifest=pack(admission);put('SOURCE_ADMISSION.zip',b)
 try:
  import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
  pa.set_cpu_count(1);pa.set_io_thread_count(1);parent_doc=json.loads(exact(cfg['parent_freeze']));assert parent_doc['forecast_readback_verified'] is True and parent_doc['bundle']==safe(cfg['parent_bundle'])
  container=exact(cfg['parent_bundle'])
  def member(name):
   with zipfile.ZipFile(io.BytesIO(container)) as z:
    n=z.getinfo(name);assert n.file_size==parent_doc['members'][name]['bytes']<=32*1024**2;b=z.read(name)
   assert sha(b)==parent_doc['members'][name]['sha256'];return b
  catalog=json.loads(member('CATALOG_SCOPE.json'))['catalog']['anytime_td']['LEAF_CDF'];assert catalog['model_sha256']==cfg['parent_model_sha256'] and catalog['product_procedure_versions']['probability_normalized']==cfg['parent_probability_product_version']
  columns=CTX+['target','method','product','prediction','fallback','output_procedure_version'];f=pq.read_table(io.BytesIO(member('FORECASTS.parquet')),columns=columns,filters=[('target','==','anytime_td'),('method','==','LEAF_CDF'),('product','==','probability_normalized')],use_threads=False).to_pandas(use_threads=False);assert len(f)==4985 and f.season.eq(2026).all() and f.week.between(1,7).all() and not f.duplicated(CTX[:4]).any() and f.output_procedure_version.eq(cfg['parent_probability_product_version']).all()
  module=load(cfg['source_pins']['calibrator'],'nfl_lab.retained_atd_curve');curve=restore_curve(params,module);p=f.prediction.to_numpy(float);q,active=transform(curve,p,f.position.to_numpy());assert np.array_equal(np.isnan(q),np.isnan(p)) and ((q[np.isfinite(q)]>=0)&(q[np.isfinite(q)]<=1)).all()
  recipe={'method':METHOD,'version':VERSION,'parent_model_sha256':cfg['parent_model_sha256'],'parent_product_version':cfg['parent_probability_product_version'],'parent_freeze_sha256':cfg['parent_freeze']['sha256'],'parameters_sha256':PARAM_SHA,'source_sha256':CLASS_SHA,'event':'played-conditional rushing-or-receiving touchdown','input':'normalizedBernoulliEventProbability; equivalentfunctionalE[Y], notbitwiseoldforecast','late_development_entrant':True,'calibration_roles':['RB','WR','TE'],'outside_role_behavior':'UNCHANGED_PARENT_WITH_EXPLICIT_ROLE_FALLBACK'};version=sha(enc(recipe));wide=f[CTX+['fallback']].copy();wide['target']='anytime_td';wide['method']=METHOD;wide['procedure_version']=version;wide['probability']=q;wide['parent_probability']=p;wide.loc[~active,'fallback']=wide.loc[~active,'fallback'].fillna('').map(lambda x:(str(x)+'|' if str(x) else '')+'CALIBRATION_ROLE_UNSUPPORTED_PARENT_REFERENCE');wide['parent_product_version']=cfg['parent_probability_product_version'];wide['evidence_tier']='LATE_CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION';wide['original_forecast_issue_time_UTC']=None
  fixture=wide.head(4).copy();slot={'cell_id':'anytime_td__'+METHOD,'target':'anytime_td','method':METHOD,'state':'FROZEN_FORECASTS_UNSCORED','procedure_version':version,'rows':len(wide),'actual_transform_rows':int(active.sum()),'unchanged_parent_role_rows':int((~active).sum()),'new_fits':0,'calibrator_objects_restored':1,'football_model_restorations':0,'parent_missing_probability_rows':int(np.isnan(p).sum()),'fallback_rows':int(wide.fallback.fillna('').ne('').sum()),'future_operational_readiness':'RESEARCH_TRANSFORM_ONLY_PARENT_LIVE_QUERY_ADMISSION_SEPARATE'}
  members={'FORECASTS.parquet':parquet(wide),'REPLAY_FIXTURE.parquet':parquet(fixture),'CELL_STATE.json':enc(slot),'RECIPE.json':enc(recipe)};body,mm=pack(members);br=put('CELL.zip',body);slot['bundle']=safe(br);slot['members']=mm;store.verify_retained_checkpoint();result={'version':VERSION,'state':'LATE_PLATT_TRANSFER_FROZEN_UNSCORED','cells':[slot],'source_admission':artifacts['SOURCE_ADMISSION.zip'],'native_original_hold':cfg['native_hold'],'new_owned_retained_bytes':written,'external_metadata_charge_bytes':cfg['external_metadata_charge_bytes'],'conservative_extra_original_parameter_reserve_bytes':785,'current_outcomes_read_fits_scores_HTTP_production':0,'offhost_restore':'NOT_VERIFIED','old_training':'ACCEPTED_NOT_REPRODUCED','actual':{'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}};assert result['actual']['RSS_bytes']<=cfg['resources']['RSS_bytes'];put('COMPLETE.json',enc(result));store.verify_retained_checkpoint();return result
 except BaseException as error:
  d={'state':'FAILED_RETAINED','version':VERSION,'type':type(error).__name__,'error_sha256':sha(str(error).encode()),'artifacts':artifacts,'new_fits':0,'outcomes_read':0,'actual':{'CPU_seconds':time.process_time()-C,'wall_seconds':time.monotonic()-S}}
  try:put('FAILURE.json',enc({**d,'private_error':str(error)}),terminal=True);d['failure_receipt_retained']=True
  except BaseException:d['failure_receipt_retained']=False;d['unretained_prediction_claim']='NO_RESTORATION_CLAIM_IF_NEW_VECTOR_NOT_FROZEN'
  return d

def main():
 a=argparse.ArgumentParser();a.add_argument('--plan',type=Path,required=True);a.add_argument('--plan-sha256',required=True);a.add_argument('--go',type=Path,required=True);a.add_argument('--go-sha256',required=True);v=a.parse_args()
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 cfg=json.loads(gzip.decompress(exact({'path':str(v.plan),'bytes':v.plan.stat().st_size,'sha256':v.plan_sha256})));go=json.loads(exact({'path':str(v.go),'bytes':v.go.stat().st_size,'sha256':v.go_sha256}));cap=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(cap['CPU_seconds'],cap['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(cap['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Platt transfer wall cap')));signal.alarm(cap['wall_seconds']);sys.addaudithook(lambda event,args:(_ for _ in ()).throw(RuntimeError('No network')) if event in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None);r=execute(cfg,go);print(enc(r).decode(),flush=True);signal.alarm(0)
 if r['state']=='FAILED_RETAINED':raise SystemExit(1)
if __name__=='__main__':main()
