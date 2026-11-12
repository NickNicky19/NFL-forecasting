"""Root-sealed zero-fit completion of the retained, unexecuted scoring tail."""
from pathlib import Path
import ast, hashlib, importlib.util, io, json, os, resource, signal, sys, time, traceback, types, zipfile

OUT=Path(__file__).resolve().parent
def digest(b):return hashlib.sha256(b).hexdigest()
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 go=json.loads((OUT/'RUSH_SAVED_SCORING_GO_V1.json').read_bytes())
 assert go['state'].startswith('GO')and go['root']=='/root'
 assert not(OUT/'RUSH_SAVED_SCORING_STARTED_V1.json').exists()
 cpu=time.process_time();start=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(108,109))
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('remaining228second wall envelope')));signal.alarm(218)
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
 old=module(OUT/'rush_historical_worker_v1.py','retained_rush_failed_worker')
 binding=json.loads((OUT/'RUSH_PREFIT_BINDINGS_V1.json').read_bytes());old.auth(binding['worker'])
 for r in binding['code']:old.auth(r)
 failure=json.loads((OUT/'RUSH_FAILED_V1.json').read_bytes());prior=failure['usage']
 assert prior['fits']==1 and prior['CPU_seconds']<132 and prior['wall_seconds']<132
 old.note('RUSH_SAVED_SCORING_STARTED_V1.json',{'state':'ONE_ZERO_FIT_SCORING_ATTEMPT_CONSUMED','worker':old.ref(Path(__file__)),'GO':old.ref(OUT/'RUSH_SAVED_SCORING_GO_V1.json'),'failed_source_preserved':binding['worker'],'new_fits_model_loads_inference':0,'remaining_CPU_seconds':108,'remaining_wall_seconds':228})
 writes=list(prior['private_writes'])
 def usage():
  return {'CPU_seconds':prior['CPU_seconds']+time.process_time()-cpu,'wall_seconds':prior['wall_seconds']+time.monotonic()-start,'RSS_bytes':max(prior['RSS_bytes'],resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),'fits':1,'new_fits':0,'new_model_loads':0,'new_inference':0,'scoring_continuation_CPU':time.process_time()-cpu,'scoring_continuation_wall':time.monotonic()-start,'private_writes':writes,'HTTP':0,'retries':0}
 try:
  import numpy as np,pandas as pd,pyarrow as pa
  pa.set_cpu_count(1);pa.set_io_thread_count(1)
  sys.path.insert(0,str(old.ROOT));sys.path.insert(0,str(OUT/'completion/C_code'))
  from nfl_lab import data
  import abc_championship_v2 as common
  loss=module(old.ROOT/'tools/category_topfive_matched12_law_scores_v1.py','rush_saved_loss')
  aux=module(old.ROOT/'tools/category_topfive_matched12_aux_runner_v1.py','rush_saved_aux')
  factory=module(old.ROOT/'tools/category_topfive_original_leans_private_freeze_v1_1.py','rush_saved_factory')
  helper=module(old.ROOT/'tools/category_topfive_matched12_storage_v1.py','rush_saved_full_store')
  fourth,_=helper.open_store(old.ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=helper.GO,readonly=True)
  third=factory.storage(old.ROOT)
  model_ref=json.loads((OUT/'RUSH_MODEL_READBACK_V1.json').read_bytes())['reference']
  frozen_ref=json.loads((OUT/'RUSH_FORECAST_FREEZE_V1.json').read_bytes())['reference']
  with zipfile.ZipFile(io.BytesIO(old.auth(model_ref)))as z:audit=json.loads(z.read('BINDING.json'))['audit']
  with zipfile.ZipFile(io.BytesIO(old.auth(frozen_ref)))as z:
   offers=pd.read_parquet(io.BytesIO(z.read('OFFERS.parquet'))).rename(columns={'side':'source_offered_side'})
   pred=pd.read_parquet(io.BytesIO(z.read('FORECASTS.parquet')))
  assert'side'not in offers and'side'in pred and len(offers)==1140 and len(pred)==1139
  refs=binding['sources'];source_bytes={k:old.auth(refs[k])for k in ['labels','explicit_2024_stat_presence']}
  with zipfile.ZipFile(io.BytesIO(old.auth(refs['retained_offer_forecast_container'])))as z:retained=pd.read_parquet(io.BytesIO(z.read('EVALUATION_FORECASTS.parquet')))
  destination=Path(frozen_ref['path']).parent
  def put(name,body):
   assert name=='GRADES.zip'and not(destination/name).exists()
   assert sum(x['bytes']for x in writes)+len(body)+65536<=old.CAP
   r={'path':str(destination/name),'bytes':len(body),'sha256':digest(body)};writes.append(r)
   with third.transaction():
    fourth._refresh();fourth._require(old.PEAK+old.META);third._refresh();third._require(old.RESERVE+old.PEAK+old.META)
    third.write_bytes(destination/name,body);v=third.validate_reference(destination/name,r['sha256']);assert all(v[k]==r[k]for k in r)
    assert(destination/name).read_bytes()==body
    fourth._refresh();fourth._require(old.META);third._refresh();third._require(old.RESERVE+old.META)
   return r
  def parq(f):
   f=f.copy();f.attrs.clear();s=io.BytesIO();f.to_parquet(s,index=False,compression='zstd');return s.getvalue()
  def cap(members):
   s=io.BytesIO()
   with zipfile.ZipFile(s,'w',compression=zipfile.ZIP_STORED)as z:
    for n,b in sorted(members.items()):z.writestr(n,b)
   return s.getvalue()
  tree=ast.parse(Path(binding['worker']['path']).read_text());main_node=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name=='main');block=next(x for x in main_node.body if isinstance(x,ast.Try)).body
  at=next(i for i,x in enumerate(block)if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='labels'for t in x.targets))
  class CountOnly(ast.NodeTransformer):
   def visit_Call(self,node):
    if isinstance(node.func,ast.Name)and node.func.id=='len'and len(node.args)==1 and isinstance(node.args[0],ast.Name)and node.args[0].id=='train':return ast.copy_location(ast.Constant(value=int(audit['training_rows'])),node)
    return self.generic_visit(node)
  tail=ast.fix_missing_locations(CountOnly().visit(ast.Module(body=block[at:],type_ignores=[])))
  namespace=vars(old).copy();namespace.update(locals());namespace.update({'source_refs':refs,'model':types.SimpleNamespace(audit=audit),'pins':binding['code'],'usage':usage,'put':put,'parq':parq,'cap':cap})
  exec(compile(tail,'<authenticated unexecuted scoring tail; training count from saved audit>','exec'),namespace)
 except BaseException as exc:
  old.note('RUSH_SAVED_SCORING_FAILED_V1.json',{'state':'FAILED_ZERO_FIT_PRESERVED','error':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'usage':usage()});raise
 finally:signal.alarm(0)

if __name__=='__main__':main()
