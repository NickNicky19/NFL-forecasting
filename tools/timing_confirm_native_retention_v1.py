"""Retain the completed B score and verification bytes in the existing A scope."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, os, resource, signal, sys, time, zipfile, io
ROOT=Path(__file__).resolve().parents[1]
VERSION='A-TIMING-CONFIRM-NATIVE-RETENTION-v1'
ATTACH='tools/next02_freshness_model_independent_v2.py'
ATTACH_SHA='025e28ae6b97c8a2c01f735b12c4745865cdc09b6437bc4c97a1fc651500d7e4'
OLD_PLAN='reports/abc-championship/profile-increment-to-release-01/closure-next-02/FRESHNESS_EXECUTION_PROTOCOL_V2.json'
OLD_PLAN_SHA='ac865ba52273e960eafcbbc7689edd6a8f3aeeab324259be3fcbcd0f17854266'
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(v):return(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def bound(path,ref):
 b=Path(path).read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
def main(a):
 start=time.monotonic();cpu=time.process_time();written=[];sys.dont_write_bytecode=True
 resource.setrlimit(resource.RLIMIT_CPU,(280,300));resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,)*2)
 def stop(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('finite timing-confirm retention envelope')
 signal.signal(signal.SIGXCPU,stop);signal.signal(signal.SIGALRM,stop);signal.alarm(880)
 def offline(event,_):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline existing evidence only')
 sys.addaudithook(offline)
 try:
  assert not a.output.exists()
  raw=Path(a.go).read_bytes();assert sha(raw)==a.go_sha256;g=json.loads(raw)
  assert g['version']==VERSION and g['state']=='ROOT_REGISTERED_RETENTION_GO'
  assert g['code_sha256']==sha(Path(__file__).read_bytes())
  assert g['resources']==dict(CPU_seconds=300,wall_seconds=900,RSS_bytes=1536*1024**2)
  assert g['native_write_ids']==['TIMING_CONFIRM_B_CMP_SCORES_V1.json.gz','TIMING_CONFIRM_VERIFICATION_BUNDLE_V1.zip']
  assert g['maximum_new_native_payload_bytes']==1048576 and g['new_fits']==0
  bb=bound(a.b_score,g['B_score']);cb=bound(a.c_score,g['C_score']);cr=bound(a.c_receipt,g['C_receipt']);zb=bound(a.bundle,g['bundle'])
  c=json.loads(cr);assert c['state']=='PASS_C04_EXACT_POINTS_SCORE_AND_NATIVE_READBACK'and c['private_score']['sha256']==sha(cb)
  b=json.loads(__import__('gzip').decompress(bb));assert b['state']=='COMPLETED_OWNER_LOCAL_SAVED_COMPLETION_JOIN'and b['counts']['new_fits']==b['counts']['new_model_inference']==0
  with zipfile.ZipFile(io.BytesIO(zb))as z:
   assert z.namelist()==[r['name']for r in g['bundle_members']]
   for r in g['bundle_members']:
    x=z.read(r['name']);assert len(x)==r['bytes']and sha(x)==r['sha256']
  assert len(bb)+len(zb)<=g['maximum_new_native_payload_bytes']
  assert sha((ROOT/ATTACH).read_bytes())==ATTACH_SHA and sha((ROOT/OLD_PLAN).read_bytes())==OLD_PLAN_SHA
  old_plan=json.loads((ROOT/OLD_PLAN).read_bytes())
  assert sha((ROOT/'nfl_lab/profile_freshness_a_storage_v1.py').read_bytes())==old_plan['code_sha256']['nfl_lab/profile_freshness_a_storage_v1.py']
  sys.path.insert(0,str(ROOT));sp=importlib.util.spec_from_file_location('timing_confirm_retention_attach',ROOT/ATTACH);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
  store=m.readonly_store(old_plan)
  store.reserve(g['maximum_new_native_payload_bytes'])
  written.append(store.put(g['native_write_ids'][0],bb));written.append(store.put(g['native_write_ids'][1],zb))
  refs=written+[c['private_score'],c['private_view']];assert len({r['id']for r in refs})==4
  restored=store.read_many(refs)
  assert restored[written[0]['id']]==bb and restored[written[1]['id']]==zb and restored[c['private_score']['id']]==cb
  storage=store.checkpoint()
  result=dict(version=VERSION,state='PASS_B_C04_SCORES_AND_VERIFICATION_NATIVE_READBACK',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_go_sha256=a.go_sha256,
   newly_retained=written,verified_members=[dict(r,restored_bytes=len(restored[r['id']]),restored_sha256=sha(restored[r['id']]))for r in refs],bundle_members=g['bundle_members'],storage=storage,
   resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
   counts=dict(new_fits=0,new_model_inference=0,new_grades=0,model_loading=0,source_HTTP=0,native_payload_writes=2,old_namespace_writes=0,production_writes=0),limits='Owner-local recovery only; public aggregates do not grant private-row or model access. No external intake or consumer receipt inferred.')
  with a.output.open('xb')as f:f.write(enc(result));f.flush();os.fsync(f.fileno())
  print(json.dumps(dict(state=result['state'],resources=result['resources'],new_payload_bytes=len(bb)+len(zb))))
 except BaseException as e:
  result=dict(version=VERSION,state='FAILED_TIMING_CONFIRM_RETENTION_NO_NEW_GRADING',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),error_type=type(e).__name__,error_sha256=sha(str(e).encode()),newly_retained=written,resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start),new_fits=0,new_grades=0)
  with a.output.with_name(a.output.stem+'-failure.json').open('xb')as f:f.write(enc(result))
  raise
 finally:signal.alarm(0)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['go','b-score','c-score','c-receipt','bundle','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--go-sha256',required=True);main(p.parse_args())
