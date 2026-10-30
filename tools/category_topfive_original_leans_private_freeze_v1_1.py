"""Runtime v1.1: identical accounting/write path, explicit 120CPU/180wall continuation."""
import argparse,hashlib,importlib.util,json,os,pathlib,resource,signal,sys,time

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def storage(root):
    plan=json.loads((root/'config/category-topfive-opportunity-over-under-capacity-v3.json').read_text())
    sp=json.loads((root/plan['storage_base_plan']).read_text())['storage']
    for name,ref in sp.items():
        if isinstance(ref,dict) and 'sha256' in ref and name!='metadata_descriptor':
            content=pathlib.Path(ref['path']).read_bytes()
            assert len(content)==ref['bytes'] and hashlib.sha256(content).hexdigest()==ref['sha256'],name
    old=load(sp['original_helper']['path'],'original_leans_market')
    wrap=load(sp['helper']['path'],'original_leans_prior')
    top=load(root/'nfl_lab/category_topfive_storage_v1.py','original_leans_topfive')
    base=old.load_frozen(sp['forward_implementation']['path'],sp['legacy_library_root'])
    prior=wrap.build_storage_class(old.build_storage_class(base),json.loads((root/plan['old_metadata_descriptor']).read_text()))
    cls=top.build_storage_class(prior,json.loads((root/plan['topfive_metadata_descriptor']).read_text()))
    return cls(sp['legacy_cache'],json.loads(pathlib.Path(sp['market_policy']['path']).read_text()),json.loads(pathlib.Path(sp['legacy_policy']['path']).read_text()),json.loads(pathlib.Path(sp['prior_policy']['path']).read_text()))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--mode',choices=['freeze','readback'],required=True);ap.add_argument('--sha256');args=ap.parse_args()
    root=pathlib.Path(args.root);plan=json.loads((root/'config/category-topfive-original-leans-private-freeze-v1.json').read_text())
    begin=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(120,121));resource.setrlimit(resource.RLIMIT_AS,(plan['runtime']['RSS_bytes'],)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('finite private evidence operation')));signal.alarm(180)
    store=storage(root);namespace=store.state_root/plan['new_namespace'];target=namespace/'scorecard.json'
    if args.mode=='freeze':
        import tty
        tty.setraw(sys.stdin.fileno())
        print('READY_PRIVATE_STREAM',flush=True)
        header=b''
        while not header.endswith(b'\n'):
            part=os.read(sys.stdin.fileno(),1)
            if not part:raise EOFError('missing stream header')
            header+=part
        length=int(header)
        if not 0<length<plan['retained_bytes']:raise ValueError('scorecard retained envelope exceeded')
        chunks=[];remaining=length
        while remaining:
            block=os.read(sys.stdin.fileno(),min(remaining,65536))
            if not block:raise EOFError('incomplete private stream')
            chunks.append(block);remaining-=len(block)
        body=b''.join(chunks);rows=json.loads(body)
        assert isinstance(rows,list) and len(rows)==2286
        digest=hashlib.sha256(body).hexdigest()
        with store.transaction():
            store._refresh();before=store._require(plan['preserved_upcoming_peak_reservation_bytes']+plan['peak_additional_bytes'])
            store.register_root(namespace);store.write_bytes(target,body)
            ref=store.validate_reference(target,digest);after=store._scan()
    else:
        if not args.sha256 or len(args.sha256)!=64:raise ValueError('exact prior digest required')
        with store.transaction():
            ref=store.validate_reference(target,args.sha256);body=target.read_bytes();rows=json.loads(body);after=store._scan()
        assert len(rows)==2286
        digest=hashlib.sha256(body).hexdigest();before=None
    safe=lambda u:{k:v for k,v in u.items() if (k.endswith('_bytes') or k.endswith('_limit_bytes')) and isinstance(v,int)} if u else None
    result={'version':'original-leans-private-evidence-v1','mode':args.mode,'state':'PASS_LOCAL_IMMUTABLE_'+args.mode.upper(),'evidence_id':'original-recorded-leans-20261030-v1/scorecard','sha256':digest,'bytes':ref['bytes'],'rows':len(rows),'before':safe(before),'after':safe(after),'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'offhost_restoration':'NOT_VERIFIED_RETAINED_OWNER_REQUIRED','new_fits_forecasts_capture_deployment':0}
    signal.alarm(0);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
