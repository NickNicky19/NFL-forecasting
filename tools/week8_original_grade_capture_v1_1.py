"""Bounded read-only Week 8 evidence capture into the existing A store."""
from __future__ import annotations
import datetime, hashlib, json, resource, signal, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def enc(x): return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def execute():
 import urllib.request
 from tools import category_topfive_matched12_storage_v1 as st
 resource.setrlimit(resource.RLIMIT_CPU,(240,241)); resource.setrlimit(resource.RLIMIT_AS,(1024**3,)*2)
 signal.alarm(900); start=time.monotonic(); cpu=time.process_time()
 c=json.loads((ROOT/'config/week8-original-grade-capture-v1.json').read_text())
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 before=store.verify_retained_checkpoint(); assert before['wave_retained_headroom_bytes']>=c['private_retained_limit']
 out=store.forward_root/'research'/'week8-original-grade-v1-20261102';assert not out.exists();store.register_root(out)
 store.write_bytes(out/'STARTED.json',enc({'state':'STARTED_READ_ONLY_SOURCE_CAPTURE','protocol_sha256':sha((ROOT/'reports/week8-original-grading-20261102/PROTOCOL_V1.json').read_bytes()),'at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_fits':0}))
 request_headers={'User-Agent':'NFL-forecasting Session A original Week8 research grading'}
 refs=[]; total=0
 for spec in c['sources']:
  t=datetime.datetime.now(datetime.timezone.utc).isoformat()
  try:
   request=urllib.request.Request(spec['url'],headers=request_headers)
   with urllib.request.urlopen(request,timeout=35) as response:
    b=response.read(c['source_bytes_limit']+1)
   assert len(b)<=c['source_bytes_limit']
   total+=len(b);assert total<=c['source_bytes_limit']
   git=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
   if spec.get('git_blob_sha1'):assert git==spec['git_blob_sha1'], 'Pinned Git source mismatch: '+spec['id']
   assert sum(x.get('bytes',0) for x in refs)+len(b)+1048576<=c['private_retained_limit']
   path=out/'sources'/(spec['id']+'.bin');store.write_bytes(path,b);v=store.validate_reference(path,sha(b))
   refs.append({**spec,'bytes':len(b),'sha256':v['sha256'],'actual_git_blob_sha1':git,'request_started_UTC':t,'captured_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'CAPTURED'})
  except Exception as e:
   refs.append({**spec,'status':'FAILED','request_started_UTC':t,'error':type(e).__name__+':'+str(e)[:250]})
  print(json.dumps({'source':spec['id'],'status':refs[-1]['status'],'bytes':refs[-1].get('bytes')}),flush=True)
 receipt={'state':'SOURCE_CAPTURE_COMPLETED_WITH_EXPLICIT_FAILURES','refs':refs,'total_source_bytes':total,'new_fits_inference':0,'actual_CPU_seconds':time.process_time()-cpu,'actual_wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'store_usage_before':{k:v for k,v in before.items() if k.endswith('_bytes') and type(v)is int}}
 store.write_bytes(out/'SOURCE_RECEIPT.json',enc(receipt));store.validate_reference(out/'SOURCE_RECEIPT.json',sha(enc(receipt)))
 safe={**receipt,'source_read_count':len(refs),'qualified_NFL_grades':0,'private_root':'EXISTING_APPROVED_A_STORE_LOCATOR_REDACTED'}
 (ROOT/'reports/week8-original-grading-20261102/SOURCE_CAPTURE_V1.json').write_bytes(enc(safe))
 print(json.dumps({'state':receipt['state'],'sources':len(refs),'failures':sum(x['status']=='FAILED' for x in refs),'bytes':total,'CPU_seconds':receipt['actual_CPU_seconds']}))
if __name__=='__main__':
 sys.path.insert(0,str(ROOT));execute()
