"""Separately registered saved-vector comparison with strongest observed controls."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,io,json,math,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-strongest-control-paired-v1'
def enc(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def exact(r):
 p=Path(r['path']);a=p.stat();assert p.is_absolute() and p.resolve()==p and not any(x.is_symlink() for x in [p,*p.parents]);b=p.read_bytes();z=p.stat();assert len(b)==a.st_size==r['bytes']<=8*1024**2 and sha(b)==r['sha256'] and (a.st_dev,a.st_ino,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_mtime_ns);return b
def execute(cfg,go):
 start=time.monotonic();cpu=time.process_time();assert go['state']=='ROOT_AND_INDEPENDENT_GO' and go['registered_by']=='/root' and go['worker_sha256']==sha(Path(__file__).read_bytes()) and go['configuration_sha256']==sha(enc(cfg));assert cfg['version']==VERSION and len(cfg['pairs'])==23 and cfg['uncertainty']=={'replicates':1000,'seed':20261030,'minimum_clusters':2};assert cfg['resources']=={'CPU_seconds':180,'wall_seconds':420,'RSS_bytes':1073741824,'AS_bytes':4294967296,'private_bytes':1048576};assert len({p['pair_id'] for p in cfg['pairs']})==23 and [sum(p['loss']==x for p in cfg['pairs']) for x in ['MAE','MSE','Brier']]==[11,11,1]
 sys.path.insert(0,str(ROOT));import nfl_lab
 assert Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab'
 from tools import category_topfive_matched12_storage_v1 as st
 from nfl_lab.owned_reference_batch import validate_owned_references
 import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 assert sha(Path(st.__file__).read_bytes())==cfg['storage_helper_sha256'];exact(cfg['scorer']);s=importlib.util.spec_from_file_location('strongest_frozen_pair_scorer',cfg['scorer']['path']);scorer=importlib.util.module_from_spec(s);s.loader.exec_module(scorer)
 store,_=st.open_store(ROOT,allocation_sha256=cfg['allocation_sha256'],root_go=st.GO);out=store.forward_root/'research'/cfg['run_id'];assert cfg['run_id'].startswith('matched12-strongest-paired-') and '/' not in cfg['run_id'] and not out.exists();store.register_root(out);used=0;stage='START'
 def put(name,b):
  nonlocal used
  assert used+len(b)+(0 if name=='FAILURE.json' else 32768)<=cfg['resources']['private_bytes'];store.write_bytes(out/name,b);r=store.validate_reference(out/name,sha(b));used+=len(b);return {k:r[k] for k in ['bytes','sha256']}
 put('STARTED.json',enc({'version':VERSION,'state':'REGISTERED_BEFORE_VECTOR_DECODE','worker_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'fits_inference':0}))
 try:
  refs={cfg[k]['path']:cfg[k]['sha256'] for k in ['source_zip','source_terminal']};_,audit=validate_owned_references(store,refs);terminal=json.loads(exact(cfg['source_terminal']));assert terminal['result']=={k:cfg['source_zip'][k] for k in ['bytes','sha256']}
  with zipfile.ZipFile(io.BytesIO(exact(cfg['source_zip']))) as z:
   manifest=json.loads(z.read('MEMBER_MANIFEST.json'));parts={}
   for name,key in [('AGGREGATES.json.gz','aggregate_member'),('PRIMARY_POINTS.parquet','point_member')]:
    b=z.read(name);assert terminal['members'][name]==manifest[name]==cfg[key] and len(b)==cfg[key]['bytes'] and sha(b)==cfg[key]['sha256'];parts[name]=b
  ag=json.loads(gzip.decompress(parts['AGGREGATES.json.gz']));assert ag['state']=='COMPLETED_NORMALIZED_FINALIST_COMPARISON' and sha(enc(ag['scope']))==cfg['scope_sha256'];assert ag['scope']['seasons']==[2026] and ag['scope']['weeks']==list(range(1,8)) and ag['scope']['chart_target_contract']=='nick-chart-ppr-v1';assert ag['headline_numeric']['population']=='PREDECLARED_RELEVANT_PRIMARY_ROLES_ONLY_NO_OUTCOME_FILTER'
  records={(r['target'],r['method'],r['product']):r for r in ag['headline_numeric']['records'] if r['scope']=='PREDECLARED_PRIMARY_COMMON_CORE'};stage='PRIMARY_VECTOR_READ_AFTER_GO';f=pq.read_table(io.BytesIO(parts['PRIMARY_POINTS.parquet']),use_threads=False).to_pandas(use_threads=False);assert not f.duplicated(scorer.KEY+['method','product']).any();results=[];cores={}
  for target in {p['target'] for p in cfg['pairs']}:
   g=f.loc[f.target.eq(target)];assert g.position.isin(cfg['primary_roles'][target]).all();keys=None
   for method,product in ag['scope']['primary_core_outputs'][target]:
    v=g.loc[g.method.eq(method)&g['product'].eq(product)];good=v.participation_state.eq('played')&np.isfinite(v.prediction.to_numpy(float))&np.isfinite(v.actual.to_numpy(float));k=v.loc[good,scorer.KEY];keys=k if keys is None else keys.merge(k,on=scorer.KEY,validate='one_to_one')
   assert keys is not None and len(keys)>0;cores[target]=keys
  stage='EXACT_DECLARED_STRONGEST_CONTROL_PAIRS'
  for p in cfg['pairs']:
   target=p['target'];g=f.loc[f.target.eq(target)];views=[];original=[]
   for name in ['candidate','control']:
    m,k=p[name];r=records[target,m,k];assert r['headline_eligible'] and r['metrics']['scored']==p['expected_core_rows'];cat=ag['catalog'][target][m];assert cat['procedure_version']==p[name+'_parent_version'] and cat.get('product_procedure_versions',{}).get(k,cat['procedure_version'])==p[name+'_output_version'];assert k in cat['products']
    v=g.loc[g.method.eq(m)&g['product'].eq(k)];assert v.procedure_version.eq(cat['procedure_version']).all();v=v.merge(cores[target],on=scorer.KEY,validate='one_to_one');assert len(v)==p['expected_core_rows'] and v.participation_state.eq('played').all() and np.isfinite(v[['prediction','actual']].to_numpy(float)).all();views.append(v);original.append(r['metrics'])
   if p['loss']=='MSE':assert all(x[1] in ['mean','mean_objective_point'] for x in [p['candidate'],p['control']])
   if p['loss']=='Brier':assert target=='anytime_td' and all(v.prediction.between(0,1).all() and v.actual.isin([0,1]).all() for v in views)
   elif p['loss']=='MAE':assert target!='anytime_td'
   result=scorer.paired(*views,p['loss'],cfg['uncertainty']);assert result['paired_rows']==p['expected_core_rows'];metric='MSE' if p['loss']=='Brier' else p['loss']
   for name,m in zip(['candidate','control'],original):assert math.isclose(result[name+'_loss'],m[metric],rel_tol=1e-12,abs_tol=1e-12) and math.isclose(m[metric],p[name+'_registered_loss'],rel_tol=1e-12,abs_tol=1e-12)
   results.append({**p,'matched':result,'candidate_fallback_scored':original[0]['fallback_scored'],'control_fallback_scored':original[1]['fallback_scored']})
  report={'version':VERSION,'state':'COMPLETED_STRONGEST_CONTROL_CACHED_PAIRS','pairs':results,'source_zip_sha256':cfg['source_zip']['sha256'],'source_primary_member_sha256':cfg['point_member']['sha256'],'source_scope_sha256':cfg['scope_sha256'],'owned_input_batch':{'references':len(refs),'full_scans':audit['full_scan_calls']},'fits_inference_forecasts_HTTP':0,'paired_scoring_runs':1,'independent_NFL_outcomes':'Reused original labels, not new observations; overlapping categories/products remain dependent.','selection':'Winners/runners-up development-selected from inspected study; nominal original game/week bootstrap, unadjusted for selection. Not an earlier-frozen prediction-selection policy or deployment.','original_CDF_comparisons':'Preserved unchanged; this separately typed continuation uses stronger applicable controls.','no_rows_dropped_from_predeclared_core':True}
  entries={'AGGREGATES.json.gz':gzip.compress(enc(report),mtime=0),'CONFIGURATION.json.gz':gzip.compress(enc(cfg),mtime=0),'OWNED_INPUT_AUDIT_PRIVATE.json':enc(audit)};entries['MANIFEST.json']=enc({k:{'bytes':len(v),'sha256':sha(v)} for k,v in entries.items()});b=io.BytesIO()
  with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for name,raw in entries.items():z.writestr(name,raw)
  stage='PERSISTENCE';package=put('RESULTS.zip',b.getvalue());before={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};r={'version':VERSION,'state':'COMPLETE_REQUIRES_NO_LATER_FAILURE','package':package,'pairs':len(results),'source_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'actual_before_terminal_write':before,'new_fits_inference':0};done=put('COMPLETE.json',enc(r));actual={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};assert actual['CPU_seconds']<=180 and actual['wall_seconds']<=420 and actual['RSS_bytes']<=1073741824;return {**r,'state':'COMPLETE_STRONGEST_CONTROL_PAIRED_CONTINUATION','actual':actual,'terminal':done,'later_failure_overrides_completion':True}
 except BaseException as e:
  put('FAILURE.json',enc({'version':VERSION,'state':'FAILED_RETAINED','stage':stage,'private_error':str(e),'error_type':type(e).__name__,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start}));raise
def main():
 a=argparse.ArgumentParser();a.add_argument('--plan',type=Path,required=True);a.add_argument('--go',type=Path,required=True);v=a.parse_args();cfg=json.loads(gzip.decompress(v.plan.read_bytes()));go=json.loads(v.go.read_bytes());cap=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(cap['CPU_seconds'],cap['CPU_seconds']+1));resource.setrlimit(resource.RLIMIT_AS,(cap['AS_bytes'],)*2);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('strongest-control paired wall')));signal.alarm(cap['wall_seconds']);sys.addaudithook(lambda e,a:(_ for _ in ()).throw(RuntimeError('cached scoring offline')) if e in ['socket.connect','socket.connect_ex','socket.getaddrinfo'] else None);print(enc(execute(cfg,go)).decode());signal.alarm(0)
if __name__=='__main__':main()
