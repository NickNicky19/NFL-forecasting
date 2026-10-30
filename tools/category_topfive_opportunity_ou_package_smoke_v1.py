"""One authenticated package-import smoke; no store initialization or NFL data."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,signal,sys,time
VERSION='opportunity-four-ou-package-smoke-v1-20261030'
def auth(ref):
    p=Path(ref['path']);assert p.resolve()==p and not p.is_symlink();b=p.read_bytes();assert len(b)==ref['bytes'] and hashlib.sha256(b).hexdigest()==ref['sha256'];return b
def load(ref,name):
    auth(ref);s=importlib.util.spec_from_file_location(name,ref['path']);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--go',required=True);a=p.parse_args()
    b=Path(a.plan).read_bytes();assert hashlib.sha256(b).hexdigest()==a.sha256;plan=json.loads(b)
    assert plan['version']==VERSION and plan['resources']=={'CPU_seconds':5,'wall_seconds':10,'RSS_bytes':134217728,'NFL_rows':0,'store_initializations':0,'CAS':0,'HTTP':0,'attempts':1}
    assert json.loads(Path(a.go).read_text())=={'state':'GO','root':'/root','scope':VERSION,'plan_sha256':a.sha256}
    assert sys.flags.dont_write_bytecode
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
    resource.setrlimit(resource.RLIMIT_CPU,(5,6));signal.signal(signal.SIGALRM,lambda *x:(_ for _ in ()).throw(TimeoutError('package smoke budget')));signal.alarm(10)
    start=time.monotonic();cpu=time.process_time();out=Path(plan['output']);assert not out.exists();out.mkdir(parents=True)
    (out/'CONSUMED.json').write_text(json.dumps({'state':'ONE_PACKAGE_SMOKE_ATTEMPT_CONSUMED','plan_sha256':a.sha256})+'\n')
    try:
        def deny(event,unused):
            if event.startswith('socket.') or event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn','pickle.find_class']:raise RuntimeError('offline child-free no-model smoke')
        sys.addaudithook(deny)
        for ref in plan['source_pins'].values():auth(ref)
        old=load(plan['source_pins']['original_helper'],'ou_smoke_market')
        old.load_frozen(plan['source_pins']['forward_implementation']['path'],plan['legacy_library_root'])
        legacy=sys.modules['nfl_lab.operational_storage'];package=sys.modules['nfl_lab']
        assert Path(legacy.__file__).resolve()==Path(plan['source_pins']['legacy_operational_storage']['path']) and Path(package.__file__).resolve()==Path(plan['source_pins']['legacy_package_init']['path'])
        before=(len(legacy._CAPTURES),len(legacy._THREAD_LOCKS),len(legacy._THREAD_CONTEXTS))
        owned=load(plan['source_pins']['owned_reference_batch'],'nfl_lab.owned_reference_batch')
        assert owned.__package__=='nfl_lab' and owned.OperationalStorage is legacy.OperationalStorage and callable(owned.validate_owned_references)
        assert before==(len(legacy._CAPTURES),len(legacy._THREAD_LOCKS),len(legacy._THREAD_CONTEXTS))
        u={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024};assert u['CPU_seconds']<=5 and u['wall_seconds']<=10 and u['RSS_bytes']<=134217728
        result={'state':'PASS','kind':'AUTHENTICATED_PACKAGE_IMPORT_ONLY','package_context':'nfl_lab','shared_legacy_OperationalStorage_class':True,'source_pins':{k:{'bytes':r['bytes'],'sha256':r['sha256']} for k,r in plan['source_pins'].items()},'NFL_rows_fits_forecasts_grades_models_stores_HTTP_CAS':0,'usage':u}
        (out/'RESULT.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
    except BaseException as e:
        (out/'FAILED.json').write_text(json.dumps({'state':'FAILED_PACKAGE_SMOKE_PRESERVED','error':type(e).__name__+':'+str(e),'NFL_rows':0,'CAS':0})+'\n');raise
    finally:signal.alarm(0)
if __name__=='__main__':main()
