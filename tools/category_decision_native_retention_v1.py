"""Retain this completed A comparison in the existing reviewed native allocation."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,importlib.util,io,json,os,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def main(a):
 start=time.monotonic();cpu=time.process_time();written=[];sys.dont_write_bytecode=True
 resource.setrlimit(resource.RLIMIT_CPU,(280,300));resource.setrlimit(resource.RLIMIT_AS,(1610612736,)*2);signal.alarm(880)
 def offline(event,_):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline retained comparison only')
 sys.addaudithook(offline)
 try:
  assert not a.output.exists();b=a.go.read_bytes();assert sha(b)==a.go_sha256;g=json.loads(b)
  assert g['state']=='ROOT_REGISTERED_CATEGORY_RESULT_RETENTION_GO'and g['code_sha256']==sha(Path(__file__).read_bytes())
  assert g['resources']==dict(CPU_seconds=300,wall_seconds=900,RSS_bytes=1610612736)
  assert g['write_ids']==['CATEGORY_DECISION_POINT_SCORES_V1.json.gz','CATEGORY_DECISION_VERIFICATION_V1.zip']and g['maximum_new_payload_bytes']==1048576
  bodies=[]
  for p,r in [(a.score,g['score']),(a.bundle,g['bundle'])]:
   x=p.read_bytes();assert len(x)==r['bytes']and sha(x)==r['sha256'];bodies.append(x)
  x=json.loads(gzip.decompress(bodies[0]));assert x['state']=='COMPLETED_A_SAVED_POINT_ANNUAL_COMMON_COMPARISONS'
  assert x['summary_cells']==1782 and x['paired_cells']==768 and len(x['aggregate_parity'])==474 and all(p['match']for p in x['aggregate_parity'])
  assert x['counts']==dict(new_fits=0,new_model_inference=0,new_source_collection=0,native_writes=0,production_writes=0)
  with zipfile.ZipFile(io.BytesIO(bodies[1]))as z:
   assert z.namelist()==[r['name']for r in g['bundle_members']]
   for r in g['bundle_members']:
    x=z.read(r['name']);assert len(x)==r['bytes']and sha(x)==r['sha256']
  assert sum(map(len,bodies))<=g['maximum_new_payload_bytes']
  for p,h in g['source_code_sha256'].items():assert sha((ROOT/p).read_bytes())==h
  old=json.loads((ROOT/g['old_plan']['path']).read_bytes());assert sha((ROOT/g['old_plan']['path']).read_bytes())==g['old_plan']['sha256']
  assert sha((ROOT/'nfl_lab/profile_freshness_a_storage_v1.py').read_bytes())==old['code_sha256']['nfl_lab/profile_freshness_a_storage_v1.py']
  sys.path.insert(0,str(ROOT));p=ROOT/'tools/next02_freshness_model_independent_v2.py';s=importlib.util.spec_from_file_location('category_result_native_attach',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);store=m.readonly_store(old)
  store.reserve(g['maximum_new_payload_bytes'])
  for name,body in zip(g['write_ids'],bodies):written.append(store.put(name,body))
  back=store.read_many(written)
  assert all(back[r['id']]==body for r,body in zip(written,bodies));storage=store.checkpoint()
  out=dict(id='A-CATEGORY-DECISION-NATIVE-RETENTION-v1',state='PASS_COMPLETE_POINT_RESULT_AND_VERIFICATION_NATIVE_READBACK',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_go_sha256=a.go_sha256,newly_retained=written,actual_readback=[dict(r,restored_bytes=len(back[r['id']]),restored_sha256=sha(back[r['id']]))for r in written],bundle_members=g['bundle_members'],storage=storage,resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),new_fits=0,new_model_inference=0,new_grades=0,old_namespace_writes=0,production_writes=0)
  with a.output.open('x')as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  print(json.dumps(dict(state=out['state'],resources=out['resources'],new_payload_bytes=sum(map(len,bodies)))))
 except BaseException as e:
  out=dict(state='FAILED_CATEGORY_RESULT_RETENTION',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),error_type=type(e).__name__,error_sha256=sha(str(e).encode()),newly_retained=written,CPU_seconds=time.process_time()-cpu,new_fits=0,new_grades=0)
  with a.output.with_name('NATIVE_RETENTION_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json').open('x')as f:json.dump(out,f,sort_keys=True);f.write('\n')
  raise
 finally:signal.alarm(0)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['go','score','bundle','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--go-sha256',required=True);main(p.parse_args())
