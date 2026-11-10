"""Finish the failed final checkpoint without fits, inference or native writes."""
from pathlib import Path
import argparse, copy, datetime, hashlib, importlib.util, json, os, resource, signal, sys, time
ROOT=Path(__file__).resolve().parents[1]
OLD='tools/next02_freshness_final_retention_v1.py'
OLD_SHA='c2dcd68a8844c35a198d456604bd075e870f2776323a2792d97e9f54ca0dd704'
VERSION='A-NEXT02-FRESHNESS-CHECKPOINT-ONLY-v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def document(p,h):
 b=Path(p).read_bytes();assert sha(b)==h;return json.loads(b)
def main(a):
 cpu=time.process_time();wall=time.monotonic();sys.dont_write_bytecode=True
 resource.setrlimit(resource.RLIMIT_CPU,(230,240));resource.setrlimit(resource.RLIMIT_AS,(1024**3,)*2)
 def stop(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('finite checkpoint-only recovery')
 signal.signal(signal.SIGXCPU,stop);signal.signal(signal.SIGALRM,stop);signal.alarm(590)
 def offline(event,_):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline immutable restoration')
 sys.addaudithook(offline)
 try:
  assert not a.output.exists()
  go=document(a.go,a.go_sha256)
  assert go['version']==VERSION and go['state']=='ROOT_REGISTERED_CHECKPOINT_ONLY_GO'
  assert go['code_sha256']==sha(Path(__file__).read_bytes())
  assert go['resources']==dict(CPU_seconds=240,wall_seconds=600,RSS_bytes=1024**3)
  assert go['native_writes']==0 and go['new_fits']==0
  assert go['prior_go_sha256']==a.prior_go_sha256 and go['failure_sha256']==a.failure_sha256
  failure=document(a.failure,a.failure_sha256)
  assert failure['state']=='FAILED_FINAL_RETENTION_NO_INFERENCE_OR_GRADING' and failure['new_fits']==failure['new_inference']==failure['new_grades']==0
  assert sha((ROOT/OLD).read_bytes())==OLD_SHA
  spec=importlib.util.spec_from_file_location('next02_original_final_retention',ROOT/OLD);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  oldargs=copy.copy(a);oldargs.go=a.prior_go;oldargs.go_sha256=a.prior_go_sha256
  _,docs,writes=m.bind_inputs(oldargs)
  assert len(writes)==3 and sum(map(len,writes.values()))==251167
  refs=m.refs_to_restore(docs['protocol'],docs['execution_receipt'],docs['scoring_receipt'])
  newrefs=failure['newly_retained']
  assert len(refs)==15 and len(newrefs)==3 and set(writes)=={r['id']for r in newrefs}
  assert len({r['id']for r in refs+newrefs})==18
  for r in newrefs:assert r==dict(id=r['id'],namespace='FRESHNESS',bytes=len(writes[r['id']]),sha256=sha(writes[r['id']]))
  sys.path.insert(0,str(ROOT));assert sha((ROOT/m.GUARD_PATH).read_bytes())==m.GUARD_SHA
  reviewer=ROOT/'tools/next02_freshness_model_independent_v2.py'
  assert sha(reviewer.read_bytes())=='025e28ae6b97c8a2c01f735b12c4745865cdc09b6437bc4c97a1fc651500d7e4'
  spec=importlib.util.spec_from_file_location('next02_checkpoint_readonly_attach',reviewer);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
  store=g.readonly_store(docs['protocol'])
  restored=store.read_many(refs+newrefs)
  m.restore_contracts(refs,restored,docs['protocol'],docs['execution_receipt'],docs['scoring_receipt'])
  assert all(restored[n]==b for n,b in writes.items())
  storage=store.checkpoint()
  result=dict(version=VERSION,state='PASS_FINAL_18_MEMBERS_AND_UNCHANGED_CAPS_CHECKPOINT',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_go_sha256=a.go_sha256,prior_failure_sha256=a.failure_sha256,
   restored=[dict(r,restored_bytes=len(restored[r['id']]),restored_sha256=sha(restored[r['id']]))for r in refs+newrefs],storage=storage,
   previous_retention_CPU_seconds=failure['resources']['CPU_seconds'],previous_retention_budget_CPU_seconds=220,previous_budget_overrun_preserved=True,
   resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
   counts=dict(new_fits=0,new_inference=0,new_grades=0,model_deserializations=0,native_writes=0,source_HTTP=0,production_writes=0),limits='Exact owner-local recovery only; not new NFL evidence, C admission or served use.')
  with a.output.open('xb')as f:f.write(enc(result));f.flush();os.fsync(f.fileno())
  print(json.dumps(dict(state=result['state'],members=18,resources=result['resources'])))
 except BaseException as e:
  result=dict(version=VERSION,state='FAILED_CHECKPOINT_ONLY_NO_NATIVE_WRITES',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),error_type=type(e).__name__,error_sha256=sha(str(e).encode()),resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall),new_fits=0,native_writes=0)
  with a.output.with_name(a.output.stem+'-failure.json').open('xb')as f:f.write(enc(result))
  raise
 finally:signal.alarm(0)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['go','prior-go','failure','protocol','execution-receipt','scoring-receipt','model-review','arithmetic-review','output']:p.add_argument('--'+n,type=Path,required=True)
 for n in ['go','prior-go','failure','protocol','execution-receipt','scoring-receipt','model-review','arithmetic-review']:p.add_argument('--'+n+'-sha256',required=True)
 main(p.parse_args())
