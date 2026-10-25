import hashlib,importlib.util,io,json,os,resource,signal,sys,time,unittest
from pathlib import Path
START=time.monotonic()
resource.setrlimit(resource.RLIMIT_CPU,(120,120))
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('fictional wall cap')))
signal.alarm(120)
freeze=Path('/tmp/raw-zero-guard-v3-fictional-freeze-v2.json')
pins=json.loads(freeze.read_text());root=Path('/workspace/nfl-methods-integration')
for name,item in pins.items():
    p=Path(name) if name.startswith('/') else root/name
    assert p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['SHA256']
denied=[]
def audit(event,args):
    if event.startswith('socket.') or event in {'subprocess.Popen','os.posix_spawn','os.fork','os.forkpty','os.system'}:
        denied.append(event);raise RuntimeError('fictional network/process forbidden')
    if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
        p=os.fsdecode(args[0])
        if '/website-methods-research/' in p or p.endswith(('.parquet','.json.gz','.joblib','.pickle')):
            denied.append('NFL/model open');raise RuntimeError('fictional NFL/model semantic read forbidden')
sys.addaudithook(audit)
spec=importlib.util.spec_from_file_location('zero_guard_contracts',root/'tests/test_raw_orphan_zero_audit_guard_v3.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
suite=unittest.defaultTestLoader.loadTestsFromModule(module);assert suite.countTestCases()==12
log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
receipt={'state':'PASS' if result.wasSuccessful() else 'FAILED','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'denied_effects':denied,'NFL_semantic_reads_fits_predictions_HTTP_worker_children':0,'wall_seconds':time.monotonic()-START,'CPU_seconds':time.process_time(),'single_process_ru_maxrss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'freeze_SHA256':hashlib.sha256(freeze.read_bytes()).hexdigest(),'new_invocations':1,'log':log.getvalue()}
if receipt['wall_seconds']>=120 or receipt['CPU_seconds']>=120 or receipt['single_process_ru_maxrss_bytes']>=268435456:receipt['state']='FAILED_RESOURCE'
with Path('/tmp/raw-zero-guard-v3-fictional-result.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='log'}),flush=True)
raise SystemExit(0 if receipt['state']=='PASS' else 1)
