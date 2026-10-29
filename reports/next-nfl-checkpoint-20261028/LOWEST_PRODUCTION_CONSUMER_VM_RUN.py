from pathlib import Path
import datetime,hashlib,json,resource,signal,subprocess,time,urllib.request
root=Path('/workspace/nfl-methods-integration/reports/next-nfl-checkpoint-20261028');raw=(root/'LOWEST_PRODUCTION_CONSUMER_VM_PLAN_V1.json').read_bytes();assert hashlib.sha256(raw).hexdigest()=='1f110612a7146fd9394f0a8f3fea21b465c4de4d2b2c6192bb614095853f90a5';plan=json.loads(raw)
start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(15,16));signal.signal(signal.SIGALRM,lambda *a:(_ for _ in()).throw(TimeoutError('30sconsumer')));signal.alarm(30);base='https://nicknicky19.github.io/nicks-expert-nfl-picks/';refs=[];total=0

def fetch(path,label,text=False):
 global total
 assert '..'not in Path(path).parts and not path.startswith('/')
 with urllib.request.urlopen(base+path,timeout=6)as f:b=f.read(6*1024**2+1)
 total+=len(b);assert len(b)<=6*1024**2 and total<=10*1024**2 and len(refs)<10
 refs.append({'path':path,'label':label,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()});return b.decode()if text else json.loads(b)
try:
 app=fetch('app.js','app',True);assert refs[-1]['sha256']==plan['expected_app_sha256'];helper=fetch('weekly-adaptive-overlay.js','helper',True);board=fetch('data/week.json','board');boardsha=refs[-1]['sha256'];ptr=fetch('data/weekly-adaptive-overlay.json','overlaypointer');paths=[x for x in ptr.values()if isinstance(x,str)and x.startswith('data/weekly-adaptive/')and x.endswith('.json')];assert len(paths)==1;overlay=fetch(paths[0],'overlay');assert refs[-1]['sha256']==plan['expected_overlay_sha256']
 rankptr=fetch('data/weekly-selected-rankings.json','rankingpointer');rank=fetch('data/'+rankptr['path'],'ranking');assert refs[-1]['sha256']==rankptr['sha256'];html=fetch('index.html','html',True);assert 'app.js'in html and 'weekly-adaptive-overlay.js'in html
 payload={'app':app,'helper':helper,'board':board,'board_sha256':boardsha,'overlay':overlay,'ranking_pointer':rankptr,'ranking':rank,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()};code=root/'LOWEST_PRODUCTION_CONSUMER_VM_CODE.cjs'
 result=subprocess.run(['node',str(code)],input=json.dumps(payload),capture_output=True,text=True,timeout=max(1,28-(time.monotonic()-start)));assert len(result.stdout.encode())+len(result.stderr.encode())<=65536
 if result.returncode:raise ValueError('ConsumerVMfailed: '+result.stderr[:5000])
 v=json.loads(result.stdout);child=resource.getrusage(resource.RUSAGE_CHILDREN);own=resource.getrusage(resource.RUSAGE_SELF);use={'CPU_seconds':time.process_time()-cpu+child.ru_utime+child.ru_stime,'wall_seconds':time.monotonic()-start,'combined_peak_RSS_upper_bound_bytes':(own.ru_maxrss+child.ru_maxrss)*1024};assert use['CPU_seconds']<=15 and use['wall_seconds']<=30 and use['combined_peak_RSS_upper_bound_bytes']<=256*1024**2
 out={'schema_version':'lowest-production-real-consumer-vm-v1','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':hashlib.sha256(raw).hexdigest(),'code_sha256':hashlib.sha256(code.read_bytes()).hexdigest(),'refs':refs,'results':v,'runtime':use,'HTTP_GETs':len(refs),'bytes_read':total,'raw_bodies_saved':False,'production_writes_fits_accuracy_scoring_secret_reads_OddsAPIcalls':0};(root/'LOWEST_PRODUCTION_CONSUMER_VM_RESULT_V1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,sort_keys=True))
except BaseException as e:
 (root/'LOWEST_PRODUCTION_CONSUMER_VM_FAILURE_V1.json').write_text(json.dumps({'error':str(e),'type':type(e).__name__,'refs':refs,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'raw_bodies_saved':False},indent=2)+'\n');raise
finally:signal.alarm(0)
