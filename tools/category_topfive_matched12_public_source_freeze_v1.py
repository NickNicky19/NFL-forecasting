"""Receive exact public Git bodies through stdin; freeze in existing private CAS.

No HTTP, credentials, statistical decoding or model work. Source values never
appear in stdout. Caller supplies exactly the three registered original blobs.
"""
import hashlib,importlib.util,json,resource,signal,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=[('SITE_ARCHIVE_W6.json','a9ed6c7e9704bb0987d57bc033964362f8dcb137',349156),
 ('SITE_ARCHIVE_W7.json','bc0e0e69e23d686ce1081bc7f2b5ce5bdf3b8588',355241),
 ('SITE_ACTUALS_W7.json','ca299a9b470fe3a28441b03dd00ab9e16fbdde12',63956)]
def main():
    start,cpu=time.monotonic(),time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(300,301));signal.alarm(600)
    if sys.stdin.isatty():
        import termios
        attr=termios.tcgetattr(sys.stdin);attr[3]&=~(termios.ECHO|termios.ICANON);termios.tcsetattr(sys.stdin,termios.TCSANOW,attr)
    print('READY_EXACT_PUBLIC_GIT_INPUTS',flush=True)
    bodies=[]
    for name,gitsha,n in SOURCES:
        line=sys.stdin.buffer.readline(2*1024**2)
        obj=json.loads(line);raw=obj['content'].encode('utf-8')
        if obj['name']!=name or len(raw)!=n or hashlib.sha1(b'blob '+str(n).encode()+b'\0'+raw).hexdigest()!=gitsha:
            raise ValueError('exact original public Git body mismatch')
        bodies.append((name,gitsha,raw))
    spec=importlib.util.spec_from_file_location('matched12_source_freeze_storage',ROOT/'tools/category_topfive_matched12_storage_v1.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    store,_=helper.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=helper.GO)
    output=store.register_root(store.forward_root/'research'/'public-git-sources-v1')
    refs=[]
    for name,gitsha,raw in bodies:
        path=output/name;store.write_bytes(path,raw)
        ref=store.validate_reference(path,hashlib.sha256(raw).hexdigest())
        refs.append({'file':name,'git_blob':gitsha,'bytes':ref['bytes'],'sha256':ref['sha256']})
    store.verify_retained_checkpoint()
    print(json.dumps({'state':'PASS_EXACT_GIT_BODIES_PRIVATE_LOCAL_CAS_READBACK','source_commit':'1ec93e068a91abd51c990937d1019e4a831694b4',
        'sources':refs,'offhost_restoration':'NOT_VERIFIED','NFL_statistical_decodes_fits_inference_scoring':0,
        'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,
            'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}},sort_keys=True),flush=True)
if __name__=='__main__':main()
