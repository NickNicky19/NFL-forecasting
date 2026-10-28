"""One fresh byte/metadata-only readback; no storage constructor or writes."""
import argparse, hashlib, importlib.util, json, os, resource, signal, sys, time, zipfile
from pathlib import Path

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def auth(ref):
    p=Path(ref['path'])
    if p.resolve()!=p or any(x.is_symlink() for x in [p,*p.parents]) or p.stat().st_size!=ref['bytes'] or sha(p)!=ref['sha256']:raise ValueError('immutable metadata/reference differs')
    if 'blob' in ref and not p.samefile(ref['blob']):raise ValueError('CAS alias inode differs')
    return p

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--go',required=True);a=ap.parse_args()
    raw=Path(a.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.sha256:raise ValueError('exact read-only plan required')
    p=json.loads(raw)
    if p['state']!='ROOT_AND_REVIEWER_SEALED' or json.loads(Path(a.go).read_bytes())!={'state':'GO','root':'/root','independent_review':'PASS','plan_sha256':a.sha256,'scope':'ONE_FRESH_READONLY_FINAL_MARKET_STORAGE_CHECK'}:raise ValueError('exact read-only root/reviewer admission required')
    output=Path(p['output']);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('one invocation only; previous evidence retained')
    caps=p['resources'];resource.setrlimit(resource.RLIMIT_CPU,(60,61));sys.dont_write_bytecode=True
    signal.signal(signal.SIGALRM,lambda *x:(_ for _ in ()).throw(TimeoutError('90s read-only wall cap')))
    signal.signal(signal.SIGXCPU,lambda *x:(_ for _ in ()).throw(TimeoutError('60s read-only CPU cap')))
    signal.alarm(90);started,cpu=time.monotonic(),time.process_time();result={'state':'FAILED_FRESH_READBACK_NO_RETRY','plan_sha256':a.sha256}
    def check():
        if time.process_time()-cpu>60 or time.monotonic()-started>90 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>384*1024**2:raise RuntimeError('finite read-only resource cap')
    try:
        for r in p['pins'].values():auth(r)
        s=p['storage'];helper_path=auth(s['helper']);spec=importlib.util.spec_from_file_location('frozen_final_market_reader',helper_path);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        market_policy=json.loads(auth(s['market_policy']).read_bytes());prior_policy=json.loads(auth(s['prior_policy']).read_bytes());legacy_policy=json.loads(auth(s['legacy_policy']).read_bytes())
        # Hash all original controls before any store attachment. Existing helper
        # uses __new__ only; neither its constructor nor a writer is invoked.
        controls=[Path(x) for x in p['controls']];before={str(x):sha(x) for x in controls};lock_stamp=Path(p['lock']).stat();lock_id=[lock_stamp.st_dev,lock_stamp.st_ino]
        base=helper.load_frozen(str(auth(s['forward_implementation'])),s['legacy_library_root'])
        prior=helper.attach_readonly_forward(base,s['legacy_cache'],prior_policy,legacy_policy)
        attached=helper.attach_readonly_forward(base,s['legacy_cache'],market_policy['store_policy'],legacy_policy)
        cls=helper.build_storage_class(base);store=cls.__new__(cls);store.__dict__.update(attached.__dict__)
        store.prior_forward=prior;store.global_limit_bytes=base._limit(market_policy['global_limit_bytes'],helper.MAX_GLOBAL_BYTES);store.market_limit_bytes=base._limit(market_policy['store_policy']['storage']['limit_bytes'],helper.MAX_MARKET_BYTES)
        store.external_inputs=market_policy['uploaded_archive_originals'];store.metadata_reserve_bytes=market_policy['working_metadata_reserve_bytes'];store.metadata_scopes=market_policy['working_metadata_scopes'];store._external_verified={};store._initializing_outer=False
        store._outer_descriptor_path=Path(market_policy['store_policy']['storage']['forward_root'])/'state/historical-market-outer-policy.json'
        store._outer_descriptor_bytes=base.legacy._encoded({'version':helper.VERSION,'outer_policy':market_policy,'prior_forward_policy':prior_policy,'legacy_policy':legacy_policy})
        store._verify_outer_descriptor();entry=store.snapshot();check()
        validated={};member_count=0;member_bytes=0
        def cas(ref):
            path=auth(ref);key=str(path)
            if key not in validated:
                got=store.validate_reference(path,expected_sha256=ref['sha256'])
                if any(got[k]!=ref[k] for k in ['path','bytes','sha256']):raise ValueError('actual CAS reference differs')
                validated[key]={'bytes':got['bytes'],'sha256':got['sha256']}
            check();return path
        def zip_hashes(container,members):
            nonlocal member_count,member_bytes
            with zipfile.ZipFile(cas(container)) as archive:
                if len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('duplicate ZIP member identity')
                if set(archive.namelist())!={r['member'] for r in members}:raise ValueError('complete ZIP member set differs')
                for r in members:
                    if archive.namelist().count(r['member'])!=1 or archive.getinfo(r['member']).file_size!=r['bytes']:raise ValueError('ZIP member size/identity differs')
                    with archive.open(r['member']) as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
                    if actual!=r['sha256']:raise ValueError('ZIP member hash differs')
                    member_count+=1;member_bytes+=r['bytes'];check()
        capture=json.loads(cas(p['source_capture_manifest']).read_bytes())
        if capture['excluded_seasons']!=[2025]:raise ValueError('source capture scope differs')
        for c in capture['containers']:
            auth(c['original']);expected=[r for r in capture['members'] if r['container_sha256']==c['retained']['sha256']];zip_hashes(c['retained'],expected)
        normalized={}
        for r in p['normalized_receipts']:
            meta=json.loads(auth(r).read_bytes());container=meta['capsule_reference'];members=[{'member':x['zip_member'],'bytes':x['bytes'],'sha256':x['sha256']} for x in meta['source_references']]
            zip_hashes(container,members);normalized[container['sha256']]=len(members)
        main=json.loads(auth(p['main_terminal']).read_bytes())
        for kind in ['forecasts','scores']:
            refs=list(main[kind].values());zip_hashes(refs[0]['container'],refs)
        paper=json.loads(auth(p['paper_member_bindings']).read_bytes());zip_hashes(paper['container'],paper['members'])
        final=store.snapshot();check();after={str(x):sha(x) for x in controls}
        if before!=after:raise ValueError('old or new storage controls changed')
        now=Path(p['lock']).stat()
        if lock_id!=[now.st_dev,now.st_ino]:raise ValueError('shared lock identity changed')
        numeric={k:v for k,v in final.items() if isinstance(v,(int,float,str))}
        result.update(state='FRESH_PROCESS_LOCAL_STORAGE_AND_CAPSULE_READBACK_PASS',inventory=numeric,
            headroom_bytes={'legacy':final['legacy_limit_bytes']-final['legacy_physical_bytes'],'prior_forward':final['prior_forward_limit_bytes']-final['prior_forward_physical_bytes'],'market':final['market_limit_bytes']-final['market_accounted_bytes'],'global':final['global_limit_bytes']-final['global_accounted_bytes'],'working_metadata_before_receipt':final['working_metadata_reserved_bytes']-final['working_metadata_actual_bytes']},
            control_hashes=before,old_and_new_controls_unchanged=True,shared_lock_identity=lock_id,validated_CAS_references=list(validated.values()),
            source_ZIP_containers=len(capture['containers']),source_original_members=len(capture['members']),normalized_capsules=len(normalized),normalized_members=sum(normalized.values()),
            main_capsules=2,paper_capsules=1,verified_ZIP_members=member_count,verified_uncompressed_member_bytes=member_bytes,
            managed_writes=0,constructors_called=0,registries_created=0,NFL_tables_decoded=0,fits=0,scores=0,models=0,HTTP=0,
            restoration_scope='LOCAL_FRESH_PROCESS_ONLY',offhost_restoration='UNPROVEN',old_caps_and_future_reservations_unchanged=True,
            metadata_receipt_budget=16000,metadata_snapshot_excludes_this_receipt=True,metadata_after_receipt_upper_bound=final['working_metadata_actual_bytes']+16000,
            metadata_headroom_after_receipt_lower_bound=final['working_metadata_reserved_bytes']-final['working_metadata_actual_bytes']-16000)
    except BaseException as error:result['error_type']=type(error).__name__;result['error']=str(error)[:500]
    finally:
        signal.alarm(0);result['CPU_seconds']=time.process_time()-cpu;result['wall_seconds']=time.monotonic()-started;result['RSS_peak_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        body=(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
        if len(body)>16000:raise RuntimeError('working receipt exceeds allocated16000bytes')
        with output.open('xb') as stream:stream.write(body)
        print(json.dumps({'state':result['state'],'receipt':str(output),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'CPU_seconds':result['CPU_seconds'],'wall_seconds':result['wall_seconds'],'RSS_peak_bytes':result['RSS_peak_bytes']}))
    if result['state']!='FRESH_PROCESS_LOCAL_STORAGE_AND_CAPSULE_READBACK_PASS':raise SystemExit(1)

if __name__=='__main__':main()
