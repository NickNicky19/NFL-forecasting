"""Bounded A-owned cache/retention adapter for the existing common comparison.

Public immutable exports are retained losslessly in an original-byte ZIP.
This is a one-time approved-source read, not a new collector or scheduler.
Original storage classes, caps, permanent lock and future reserve are unchanged.
"""
from pathlib import Path
import argparse, datetime, functools, gzip, hashlib, io, json, os, re
import resource, signal, subprocess, sys, time, urllib.request, zipfile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'reports/abc-championship/w1w9-comparison-closure-01'
ID = 'ABC-W1W9-COMPARISON-CLOSURE-01-A'
FUTURE, PEAK, META, LIMIT = 83886080, 12582912, 1048576, 12582912


def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@functools.lru_cache(maxsize=2)
def container(path, digest, size):
    p=Path(path)
    if p.is_symlink() or p.stat().st_size!=size: raise ValueError('Cache container identity differs')
    body=p.read_bytes()
    if sha(body)!=digest: raise ValueError('Cache container bytes differ')
    return body


def original(ref):
    """Return exactly the admitted original bytes; do not normalize their text."""
    kind=ref.get('stored_encoding')
    if kind:
        body=container(ref['path'],ref['stored_sha256'],ref['stored_bytes'])
        if kind=='zip_member_original_bytes':
            with zipfile.ZipFile(io.BytesIO(body)) as z: body=z.read(ref['member'])
        elif kind=='gzip_original_bytes': body=gzip.decompress(body)
        elif kind!='identity': raise ValueError('Unsupported lossless cache representation')
        digest,size=ref['original_sha256'],ref['original_bytes']
    else:
        p=Path(ref['path'])
        if p.is_symlink(): raise ValueError('Original reference is a symlink')
        body=p.read_bytes();digest,size=ref['sha256'],ref['bytes']
    if len(body)!=size or sha(body)!=digest: raise ValueError('Original source binding differs')
    git=ref.get('git_blob_sha1')
    if git and hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()!=git:
        raise ValueError('Original Git blob binding differs')
    return body


def stores():
    sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
    from tools.wave_close_source_admission_v1 import stores as old
    return old()


def capacity(full, third):
    full._refresh();a=full._require(PEAK+META)
    third._refresh();b=third._require(FUTURE+PEAK+META)
    keys={'matched12_complete_accounted_bytes','matched12_complete_limit_bytes',
          'forward_physical_bytes','market_accounted_bytes','market_limit_bytes',
          'working_metadata_actual_bytes','working_metadata_reserved_bytes',
          'category_topfive_metadata_actual_bytes','category_topfive_metadata_reserved_bytes',
          'next_metadata_actual_bytes','next_metadata_reserved_bytes',
          'legacy_physical_bytes','legacy_limit_bytes','prior_forward_physical_bytes','prior_forward_limit_bytes'}
    safe=lambda x:{k:v for k,v in x.items() if k in keys}
    return {'complete':safe(a),'market':safe(b)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['admit','cache','execute'])
    ap.add_argument('--plan',type=Path);ap.add_argument('--plan-sha256')
    ap.add_argument('--publication-commit');ap.add_argument('--stage',choices=['panel','comparison'])
    ap.add_argument('--attempt',type=int,choices=[1,2],default=1)
    args=ap.parse_args();start=time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU,(880,900))
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Finite root source/retention operation')))
    signal.alarm(1800)
    full,third,prepared=stores();ns=third.state_root/'research/w1w9-comparison-closure-01'
    with full.transaction():
        before=capacity(full,third)
        admission=REPORT/'SOURCE_ADMISSION_PUBLIC_V1.json'
        baseline=(json.loads(admission.read_bytes())['baseline_forward_physical_bytes']
                  if admission.exists() else before['market']['forward_physical_bytes'])
        used=lambda:third._scan()['forward_physical_bytes']-baseline
        def put(path,body):
            if used()+len(body)+16384>LIMIT: raise ValueError('Declared task retention envelope exceeded before write')
            third.write_bytes(path,body);return third.validate_reference(path,sha(body))
        public={'id':ID,'mode':args.mode,'UTC':now(),'before':before}
        if args.mode=='admit':
            from tools.abc_a_dynamic_carry_wave_v1 import sources
            from tools.category_topfive_matched12_replay_v1_2 import owner_validate
            _,c,g,_=sources()
            refs={k:g[k] for k in ['offers','qualified_labels','frozen_bundle','queries']}
            refs['features']=c['features']
            for i,ref in enumerate(c['history_sources']):refs['history'+str(i)]=ref
            prior=third.state_root/'research/wave-close-next-comparison-20261114-01/retained-attempt3/PRIVATE_VECTORS.json.gz'
            refs['prior_completion_vectors']={'path':str(prior),'bytes':135299,'sha256':'b7612b58b75cd21a3fd03ce8834bcf3fd69f459cf25bb9b3cfb6fed171640a54'}
            admitted={}
            for name,ref in refs.items():
                owner=owner_validate(full,ref);original(ref)
                admitted[name]={**ref,'owner_validation':owner}
            third.register_root(ns)
            private={'id':ID,'state':'PASS_EXISTING_ORIGINAL_OWNER_SOURCE_VALIDATION','UTC':now(),
                     'A_sources':admitted,'all_old_caps_and_reserves_preserved':True}
            proof=put(ns/'A_SOURCE_REFS.json',enc(private))
            public.update(state=private['state'],source_receipt={k:proof[k] for k in ['bytes','sha256']},
                source_owners={k:v['owner_validation'] for k,v in admitted.items()},
                baseline_forward_physical_bytes=baseline,allocation_sha256=prepared['allocation_sha256'])
        else:
            raw=args.plan.read_bytes()
            if sha(raw)!=args.plan_sha256:raise ValueError('Exact root plan differs')
            plan=json.loads(gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw)
            if plan['id']!=ID or plan['registered_by']!='/root':raise ValueError('Root plan required')
            if not args.publication_commit or not re.fullmatch('[0-9a-f]{40}',args.publication_commit):raise ValueError('Published readback commit required')
            for path,digest in plan['code_sha256'].items():
                if sha((ROOT/path).read_bytes())!=digest:raise ValueError('Executing code differs: '+path)
            for path,digest in plan['metadata_sha256'].items():
                if sha((ROOT/path).read_bytes())!=digest:raise ValueError('Frozen metadata differs: '+path)
            if args.mode=='cache':
                if plan['state']!='ROOT_FROZEN_SOURCE_QUALIFICATION_GO':raise ValueError('Source qualification GO required')
                third.validate_reference(ns/'A_SOURCE_REFS.json',plan['A_source_receipt_sha256'])
                refs=plan['sources']
                if not 0<len(refs)<=160 or len({r['id'] for r in refs})!=len(refs):raise ValueError('Bounded unique source IDs required')
                if sum(r['bytes'] for r in refs)>48*1024**2:raise ValueError('Original-byte input envelope exceeded')
                for ref in refs:
                    if not re.fullmatch('[A-Za-z0-9_-]{1,120}',ref['id']) or not 0<ref['bytes']<=8*1024**2:raise ValueError('Invalid source member/size')
                    if not (ref.get('sha256') or ref.get('git_blob_sha1')):raise ValueError('Original hash required')
                    if ref.get('sha256') and not re.fullmatch('[0-9a-f]{64}',ref['sha256']):raise ValueError('Invalid original SHA256')
                    if ref.get('git_blob_sha1') and not re.fullmatch('[0-9a-f]{40}',ref['git_blob_sha1']):raise ValueError('Invalid Git blob SHA1')
                    if ref['repository'] not in ['NickNicky19/nicks-expert-nfl-picks','NickNicky19/NFL-forecasting-V2','NickNicky19/NFL-forecasting-NGS-C'] or not re.fullmatch('[0-9a-f]{40}',ref['commit']) or Path(ref['path']).is_absolute() or '..' in Path(ref['path']).parts:raise ValueError('Unregistered immutable source route')
                buffer=io.BytesIO();proofs={};duplicates={};gets=0
                try:
                    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
                        for ref in refs:
                            sid=ref['id'];key=ref.get('sha256') or ref.get('git_blob_sha1')
                            if key in duplicates:
                                previous=proofs[duplicates[key]]
                                if previous['original_bytes']!=ref['bytes'] or (ref.get('sha256') and previous['original_sha256']!=ref['sha256']) or (ref.get('git_blob_sha1') and previous['git_blob_sha1']!=ref['git_blob_sha1']):raise ValueError('Duplicate-content source binding differs')
                                proofs[sid]={**previous,'id':sid,'source_repository':ref['repository'],'source_commit':ref['commit'],'source_path':ref['path'],'route':'SAME_ORIGINAL_CONTENT_REUSE','same_original_content_as':duplicates[key]}
                                continue
                            expected=ref.get('sha256');blob=third.blob_root/expected if expected else None
                            if blob is not None and blob.exists():
                                body=blob.read_bytes();route='EXISTING_OWNED_CAS_EXACT_BYTES'
                            else:
                                repo=ref['repository'];commit=ref['commit'];path=ref['path']
                                if repo not in ['NickNicky19/nicks-expert-nfl-picks','NickNicky19/NFL-forecasting-V2','NickNicky19/NFL-forecasting-NGS-C'] or not re.fullmatch('[0-9a-f]{40}',commit) or '..' in Path(path).parts:raise ValueError('Unregistered source route')
                                url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+path
                                request=urllib.request.Request(url,headers={'User-Agent':'A-existing-immutable-export-readback/1'})
                                remaining=1200-(time.monotonic()-start)
                                if remaining<=0:raise TimeoutError('Bounded source read window exhausted')
                                with urllib.request.urlopen(request,timeout=min(30,remaining)) as response:
                                    if response.status!=200 or response.url!=url:raise ValueError('Original immutable source route differs')
                                    body=response.read(ref['bytes']+1)
                                gets+=1;route='IMMUTABLE_PUBLIC_EXPORT_GET'
                            git=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
                            if len(body)!=ref['bytes'] or (expected and sha(body)!=expected) or (ref.get('git_blob_sha1') and git!=ref['git_blob_sha1']):raise ValueError('Original source byte/hash mismatch: '+sid)
                            member='original/'+sid
                            item=zipfile.ZipInfo(member,date_time=(1980,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o444<<16
                            archive.writestr(item,body)
                            proofs[sid]={'id':sid,'member':member,'stored_encoding':'zip_member_original_bytes','original_bytes':len(body),'original_sha256':sha(body),'git_blob_sha1':git,'source_repository':ref['repository'],'source_commit':ref['commit'],'source_path':ref['path'],'retrieved_UTC':now(),'route':route}
                            duplicates[key]=sid
                    packed=buffer.getvalue();cache=put(ns/'SOURCE_CACHE_V1.zip',packed)
                    for proof in proofs.values():
                        proof.update(path=cache['path'],stored_bytes=cache['bytes'],stored_sha256=cache['sha256'])
                        original(proof)
                    manifest={'id':ID,'state':'PASS_EXACT_ORIGINAL_BYTE_CACHE_READBACK','UTC':now(),'refs':proofs}
                    mref=put(ns/'SOURCE_CACHE_REFS.json',enc(manifest))
                    public.update(state=manifest['state'],source_refs=len(proofs),unique_originals=len(duplicates),public_GETs=gets,
                        original_decoded_bytes=sum(v['original_bytes'] for v in proofs.values()),
                        cache={k:cache[k] for k in ['bytes','sha256']},source_receipt={k:mref[k] for k in ['bytes','sha256']},
                        lossless='Every original SHA256/Gitblob/bytecount verified after container restoration; no historical source-clock authentication implied')
                except BaseException as error:
                    partial=buffer.getvalue()
                    if partial:put(ns/'FAILED_SOURCE_CACHE_PARTIAL.zip',partial)
                    put(ns/'FAILED_SOURCE_CACHE.json',enc({'state':'FAILED_NO_AUTOMATIC_RETRY','UTC':now(),'error_type':type(error).__name__,'error_sha256':sha(str(error).encode()),'completed_source_ids':list(proofs)}))
                    raise
            else:
                if plan['state']!='ROOT_REGISTERED_COMPARISON_GO':raise ValueError('Comparison GO required')
                if args.attempt==2:
                    recovery=plan['recovery'][args.stage]
                    previous=REPORT/('EXECUTION_'+args.stage+'_V1.json')
                    if recovery['authorized_by']!='/root' or sha(previous.read_bytes())!=recovery['prior_execution_receipt_sha256'] or json.loads(previous.read_bytes())['state']!='FAILED_RETAINED_NO_AUTOMATIC_RETRY':raise ValueError('Exact prior failure and root continuation required')
                task=plan['executions'][args.stage]
                if task['script'] not in ['tools/w1w9_retained_offer_panel_v1.py','tools/w1w9_saved_comparison_v1.py']:raise ValueError('Unexpected execution owner')
                reserve=task['maximum_staged_output_bytes']+task['maximum_log_bytes']+65536
                if used()+2*reserve>LIMIT:raise ValueError('Declared child staging/CAS/control reservation exceeds task cap')
                suffix='' if args.attempt==1 else '-attempt2'
                stage=ns/('stage-'+args.stage+suffix);stage.mkdir(mode=0o700,parents=True,exist_ok=False)
                values={'namespace':str(ns),'stage':str(stage),'root':str(ROOT)}
                command=[sys.executable,'-B',str(ROOT/task['script'])]+[v.format(**values) for v in task['args']]
                try:child=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=task['wall_seconds'])
                except subprocess.TimeoutExpired as error:child=subprocess.CompletedProcess(command,124,error.stdout or b'',error.stderr or b'')
                put(ns/(args.stage+suffix+'-stdout.txt'),child.stdout);put(ns/(args.stage+suffix+'-stderr.txt'),child.stderr)
                retained={}
                for source in sorted(stage.iterdir()):
                    if not source.is_file() or source.is_symlink():raise ValueError('Unexpected stage file')
                    body=source.read_bytes();target=ns/('retained-'+args.stage+suffix)/source.name;ref=put(target,body)
                    retained[source.name]={k:ref[k] for k in ['bytes','sha256']}
                    if source.read_bytes()!=target.read_bytes():raise ValueError('Staging duplicate differs')
                    source.unlink()
                public.update(state='PASS_EXECUTED_AND_DURABLY_RETAINED' if child.returncode==0 else 'FAILED_RETAINED_NO_AUTOMATIC_RETRY',
                              returncode=child.returncode,refs=retained,source_GETs=0,new_fits=0)
                print(child.stdout.decode(errors='replace'))
                if child.returncode:print(child.stderr.decode(errors='replace')[-4000:])
            public.update(plan_sha256=args.plan_sha256,publication_commit=args.publication_commit)
        actual=used()
        if not 0<=actual<=LIMIT:raise ValueError('Complete new retained task cap exceeded')
        public.update(after=capacity(full,third),task_private_actual_bytes=actual,task_private_limit_bytes=LIMIT,
                      old_future_reserve_bytes=FUTURE,all_four_metadata_reserves_bytes=META,peak_reserved_bytes=PEAK,
                      wall_seconds=time.monotonic()-start,all_old_caps_unchanged=True)
        name={'admit':'SOURCE_ADMISSION_PUBLIC_V1.json','cache':'SOURCE_CACHE_READBACK_V1.json','execute':'EXECUTION_'+str(args.stage)+'_V'+str(args.attempt)+'.json'}[args.mode]
        with (REPORT/name).open('xb') as h:h.write(enc(public));h.flush();os.fsync(h.fileno())
        signal.alarm(0)
        print(json.dumps({'state':public['state'],'report':name,'private_bytes':actual,'wall_seconds':public['wall_seconds']}))


if __name__=='__main__':
    try:main()
    except BaseException as error:
        receipt={'state':'FAILED_ROOT_OPERATION_NO_AUTOMATIC_RETRY','UTC':now(),'error_type':type(error).__name__,'error_sha256':sha(str(error).encode())}
        p=REPORT/('ROOT_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        with p.open('xb') as h:h.write(enc(receipt));h.flush();os.fsync(h.fileno())
        raise
