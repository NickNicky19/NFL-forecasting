"""Batch only missing read-only sources; preserve original bounded failures."""
from __future__ import annotations
import datetime,gzip,hashlib,io,json,resource,signal,sys,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def run():
 sys.path.insert(0,str(ROOT));from tools import category_topfive_matched12_storage_v1 as st
 resource.setrlimit(resource.RLIMIT_CPU,(300,301));resource.setrlimit(resource.RLIMIT_AS,(1024**3,)*2);signal.alarm(600)
 start=time.monotonic();cpu=time.process_time();c=json.loads((ROOT/'config/week8-original-grade-capture-v2.json').read_text())
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 old=store.forward_root/'research'/'week8-original-grade-v1-20261102';out=store.forward_root/'research'/'week8-original-grade-v2-batch-20261102'
 assert not out.exists();store.register_root(out)
 refs=[];members={};network_bytes=0;requests=0
 for spec in c['sources']:
  reused=False;candidate=old/'sources'/(spec['id']+'.bin');b=None
  if candidate.is_file() and spec.get('git_blob_sha1'):
   saved=candidate.read_bytes();actual=hashlib.sha1(b'blob '+str(len(saved)).encode()+b'\0'+saved).hexdigest()
   if actual==spec['git_blob_sha1']:
    store.validate_reference(candidate,sha(saved));b=saved;reused=True
  before=datetime.datetime.now(datetime.timezone.utc).isoformat()
  try:
   if b is None:
    requests+=1;request=urllib.request.Request(spec['url'],headers={'User-Agent':'NFL-forecasting Session A Week8 original-grading'})
    with urllib.request.urlopen(request,timeout=35) as response:b=response.read(c['source_bytes_limit']+1)
    network_bytes+=len(b);assert network_bytes<=c['source_bytes_limit']
   git=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
   if spec.get('git_blob_sha1'):assert git==spec['git_blob_sha1'], 'Pinned Git source mismatch'
   members[spec['id']+'.bin']=b
   refs.append({**spec,'status':'CAPTURED','bytes':len(b),'sha256':sha(b),'git_blob_sha1':git,'reused_prior_download':reused,'readback_or_capture_started_UTC':before,'readback_or_capture_completed_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
  except Exception as e:refs.append({**spec,'status':'FAILED','error':type(e).__name__,'detail':'Seeprivateboundedsourcefailure;noautomaticfallbackorzero','at_UTC':before})
  print(json.dumps({'source':spec['id'],'status':refs[-1]['status'],'reused':reused,'bytes':refs[-1].get('bytes')}),flush=True)
 receipt={'version':'week8-source-capture-batch-v2','refs':refs,'state':'COMPLETE_SOURCE_CAPTURE_WITH_EXPLICIT_FAILURES','new_network_requests':requests,'new_network_bytes':network_bytes,'reused_exact_prior_sources':sum(x.get('reused_prior_download',False)for x in refs),'new_fits_inference':0}
 members['SOURCE_RECEIPT.json']=enc(receipt);members['MEMBER_MANIFEST.json']=enc({n:{'bytes':len(b),'sha256':sha(b)}for n,b in members.items()})
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,b in members.items():z.writestr(n,b)
 body=buf.getvalue();assert len(body)+sum(p.stat().st_size for p in old.rglob('*') if p.is_file())+8*1024**2<=c['private_retained_limit']
 store.write_bytes(out/'SOURCES.zip',body);v=store.validate_reference(out/'SOURCES.zip',sha(body))
 with zipfile.ZipFile(out/'SOURCES.zip') as z:
  assert z.testzip() is None
  for n,b in members.items():assert z.read(n)==b
 safe={**receipt,'archive':{'artifact_id':'A-WEEK8-GRADE-SOURCES-V2',**{k:v[k]for k in ('bytes','sha256')}},'actual_CPU_seconds':time.process_time()-cpu,'actual_wall_seconds':time.monotonic()-start,'private_member_count':len(members),'offhost_restore':'NOT_VERIFIED'}
 store.write_bytes(out/'COMPLETE.json',enc(safe));(ROOT/'reports/week8-original-grading-20261102/SOURCE_CAPTURE_V2.json').write_bytes(enc(safe));print(json.dumps({'state':safe['state'],'refs':len(refs),'failures':sum(x['status']=='FAILED'for x in refs),'archive':safe['archive'],'CPU_seconds':safe['actual_CPU_seconds']}))
if __name__=='__main__':run()
