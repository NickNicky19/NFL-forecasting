"""One exact recovery of four approved original upload anchors; no guard change."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,resource,signal,time
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def plain(p):
 assert p.is_absolute() and all(not q.is_symlink()for q in (p,*p.parents))
def main(a):
 start=time.monotonic();cpu=time.process_time()
 resource.setrlimit(resource.RLIMIT_CPU,(19,20));resource.setrlimit(resource.RLIMIT_AS,(536870912,)*2);signal.alarm(55)
 raw=a.go.read_bytes();assert sha(raw)==a.go_sha256;g=json.loads(raw)
 assert g['state']=='ROOT_REGISTERED_EXACT_ANCHOR_RECOVERY_GO'and g['code_sha256']==sha(Path(__file__).read_bytes())
 assert g['copy_bytes_max']==17649073 and g['new_models_fits_sources']==0
 assert not a.output.exists()
 p=ROOT/'config/next-checkpoint-ordered-capacity-v2.json';assert sha(p.read_bytes())==g['plan_sha256'];ref=json.loads(p.read_bytes())['storage']['market_policy']
 b=Path(ref['path']).read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];policy=json.loads(b)
 forward=Path(policy['store_policy']['storage']['forward_root']);outer=json.loads((forward/'state/historical-market-outer-policy.json').read_bytes());assert outer['outer_policy']==policy
 refs=policy['uploaded_archive_originals'];assert len(refs)==4 and sum(r['bytes']for r in refs)==17649073
 assert sorted((r['bytes'],r['sha256'])for r in refs)==sorted((r['bytes'],r['sha256'])for r in g['files'])
 result=[]
 for r in refs:
  dst=Path(r['path']);src=forward/'operational-forward-storage-v3/blobs/sha256'/r['sha256'];plain(src);plain(dst)
  before=src.stat();assert src.is_file()and before.st_size==r['bytes']and digest(src)==r['sha256'];after=src.stat()
  assert tuple(getattr(before,k)for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink'])==tuple(getattr(after,k)for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink'])
  # Source may have the already-authorized two managed links. Preserve it.
  if dst.exists():assert dst.stat().st_nlink==1 and dst.stat().st_size==r['bytes']and digest(dst)==r['sha256']
  else:
   dst.parent.mkdir(parents=True,exist_ok=True)
   with dst.open('xb')as f,src.open('rb')as origin:
    os.chmod(dst,0o600)
    for block in iter(lambda:origin.read(1048576),b''):f.write(block)
    f.flush();os.fsync(f.fileno())
   directory=os.open(dst.parent,os.O_RDONLY);os.fsync(directory);os.close(directory)
  assert dst.stat().st_nlink==1 and dst.stat().st_size==r['bytes']and digest(dst)==r['sha256']
  result.append(dict(name=dst.name,bytes=r['bytes'],sha256=r['sha256'],readback='PASS',source_retained=True,destination_nlink=1))
 out=dict(id='A-CATEGORY-DECISION-EXACT-ANCHOR-RECOVERY-v1',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),state='EXACT_APPROVED_ANCHORS_RESTORED_AND_READ_BACK',files=result,unchanged_original_external_bytes=17649073,cap_or_guard_changes=0,new_collection_models_fits_decodes=0,root_go_sha256=a.go_sha256,resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
 with a.output.open('x')as f:json.dump(out,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 signal.alarm(0);print(json.dumps(out))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--go',type=Path,required=True);p.add_argument('--go-sha256',required=True);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
