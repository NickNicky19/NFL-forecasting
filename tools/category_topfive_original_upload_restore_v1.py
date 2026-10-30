"""Restore disappeared original inputs from verified retained bytes; no policy edits."""
import hashlib,json,os,pathlib,resource,signal,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(10,11));signal.alarm(30)
    plan=json.loads((ROOT/'config/next-checkpoint-ordered-capacity-v2.json').read_text())['storage']
    ref=plan['market_policy'];b=pathlib.Path(ref['path']).read_bytes();assert len(b)==ref['bytes'] and hashlib.sha256(b).hexdigest()==ref['sha256']
    policy=json.loads(b);forward=pathlib.Path(policy['store_policy']['storage']['forward_root'])
    outer=json.loads((forward/'state/historical-market-outer-policy.json').read_text());assert outer['outer_policy']==policy
    refs=policy['uploaded_archive_originals'];assert len(refs)==4 and sum(r['bytes'] for r in refs)==17649073
    result=[]
    for r in refs:
        dst=pathlib.Path(r['path']);src=forward/'operational-forward-storage-v3/blobs/sha256'/r['sha256']
        assert src.is_file() and not src.is_symlink() and src.stat().st_size==r['bytes'] and digest(src)==r['sha256']
        assert dst.is_absolute() and all(not p.is_symlink() for p in (dst,*dst.parents))
        if dst.exists():assert dst.stat().st_nlink==1 and dst.stat().st_size==r['bytes'] and digest(dst)==r['sha256']
        else:
            dst.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix='.original-restore-',dir=dst.parent)
            # A failed partial remains visible; never delete unique failure evidence.
            with os.fdopen(fd,'wb') as f,src.open('rb') as origin:
                for block in iter(lambda:origin.read(1<<20),b''):f.write(block)
                f.flush();os.fsync(f.fileno())
            tmp=pathlib.Path(tmp);assert tmp.stat().st_size==r['bytes'] and digest(tmp)==r['sha256']
            os.chmod(tmp,0o600);os.link(tmp,dst,follow_symlinks=False);tmp.unlink()
            directory=os.open(dst.parent,os.O_RDONLY);os.fsync(directory);os.close(directory)
        assert dst.stat().st_nlink==1 and digest(dst)==r['sha256']
        result.append({'bytes':r['bytes'],'sha256':r['sha256'],'restored_exact_original_destination':True,'source_retained':True,'destination_nlink':1})
    signal.alarm(0)
    out={'version':'original-upload-byte-restoration-v1','state':'PASS','original_external_bytes_restored':17649073,'unchanged_frozen_policy':True,'new_sources_or_outcome_decodes':0,'files':result,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start}}
    target=ROOT/'reports/category-topfive-original-leans-release-ou-20261030/UPLOAD_RESTORATION_V1.json'
    with target.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps(out))
if __name__=='__main__':main()
