"""Root-GO managed line/point replay; no fit/inference/network/production writes."""
from __future__ import annotations
import argparse,copy,hashlib,importlib.util,io,json,os,resource,signal,sys,time,zipfile
from pathlib import Path

VERSION='matched12-managed-replay-v1'
ROOT=Path(__file__).resolve().parents[1]
AUX_SHA='9e3e060e098acdcac67607a0a0bc0b23c4fa84ecd8716169eca3cff5c2fee8e9'
OFFERS_SHA='381396e53859fab8238a87fb8f516b1676889407be258585d1d251c92dc968b0'
CAP=24*1024**2

def encoded(value):
 def scalar(v):
  if type(v).__module__=='numpy' and hasattr(v,'item'):return v.item()
  raise TypeError('unsupported JSON metadata type '+type(v).__name__)
 return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,default=scalar).encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def exact(ref):
 p=Path(ref['path'])
 if not p.is_absolute() or p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('canonical nonsymlink configuration/source required')
 a=p.stat()
 if a.st_size!=ref['bytes'] or a.st_size>32*1024**2:raise ValueError('declared finite source byte envelope changed')
 b=p.read_bytes();c=p.stat()
 if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(c.st_dev,c.st_ino,c.st_size,c.st_mtime_ns) or sha(b)!=ref['sha256']:raise ValueError('exact configuration/source changed')
 return b
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def safe_ref(ref):return {k:ref[k] for k in ['bytes','sha256']}
def owner_validate(store,ref):
 """Pick the actual namespace owner, never ask the new peer to own old data."""
 path=Path(ref['path']);owners=[]
 for name,obj in [('matched12',store),('complete_peer',store.complete_peer),('prior_forward',store.complete_peer.prior_forward),('legacy',store.legacy)]:
  if any(path.is_relative_to(Path(r)) for r in obj._roots):owners.append((name,obj))
 if len(owners)!=1:raise ValueError('source must have exactly one actual registered private owner')
 name,obj=owners[0];verified=obj.validate_reference(path,ref['sha256'])
 if verified['bytes']!=ref['bytes']:raise ValueError('owned input byte count changed')
 return {'owner':name,**safe_ref(verified)}
def limits():
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='2'
 resource.setrlimit(resource.RLIMIT_CPU,(900,901));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('finite registered replay wall budget')));signal.alarm(1200)
def frame_bytes(frame):
 out=io.BytesIO();frame.to_parquet(out,index=False,compression='zstd');return out.getvalue()

def execute(plan,go):
 """Caller has authenticated both JSON files and reviewed this exact worker."""
 start=time.monotonic();cpu=time.process_time()
 if (go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root'
  or go.get('worker_version')!=VERSION or go.get('worker_sha256')!=sha(Path(__file__).read_bytes())
  or go.get('plan_canonical_sha256')!=sha(encoded(plan))):raise ValueError('exact outer root/independent GO required')
 if plan['version']!=VERSION or plan['private_peak_bytes']!=CAP or plan['safe_aggregate_cap_bytes']!=196608:raise ValueError('separately versioned finite forward bounds required')
 if not plan.get('aggregate_cap_amendment'):raise ValueError('old unexecuted64KiB limit must be explicitly superseded, not silently edited')
 expected={'aux':AUX_SHA,'offers':OFFERS_SHA}
 for k,ref in plan['source_pins'].items():
  exact(ref)
  if k in expected and ref['sha256']!=expected[k]:raise ValueError('reviewed inner source version differs')
 for key in ['storage_helper','aux','offers','scorer']:
  if key not in plan['source_pins']:raise ValueError('missing exact executable source pin')
 aux_cfg=json.loads(exact(plan['auxiliary_configuration']));aux_cfg=copy.deepcopy(aux_cfg)
 aux_cfg['resources']['maximum_safe_aggregate_compressed_bytes']=196608
 if sha(encoded(aux_cfg))!=plan['effective_aux_configuration_canonical_sha256']:raise ValueError('effective prospective auxiliary amendment digest mismatch')
 offer_cfg=json.loads(exact(plan['offer_configuration']));read_go=json.loads(exact(plan['decoder_GO']))
 if not plan['output_slug'].startswith('matched12-replay-') or '/' in plan['output_slug'] or '..' in plan['output_slug']:raise ValueError('fresh single controlled output namespace required')
 storage=load(plan['source_pins']['storage_helper']['path'],'matched12_replay_storage')
 store,prepared=storage.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=storage.GO)
 with store.transaction():store._refresh();initial=store._require(0)
 baseline=initial['new_peer_physical_bytes'];out=store.forward_root/'research'/plan['output_slug']
 if out.exists():raise ValueError('run already exists; preserve consumed attempt and never retry/overwrite')
 output=store.register_root(out);refs={};written_upper=0
 def put(name,body):
  nonlocal written_upper
  if written_upper+len(body)+65536>CAP:raise MemoryError('complete serialized wave peak budget exhausted; preserve prior evidence')
  store.write_bytes(output/name,body);r=store.validate_reference(output/name,sha(body));written_upper+=len(body);refs[name]=r;return r
 consumed={'version':VERSION,'run_id':plan['run_id'],'state':'CONSUMED_BEFORE_NFL_SOURCE_DECODE','clock_UTC':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
  'plan_canonical_sha256':sha(encoded(plan)),'worker_sha256':go['worker_sha256'],'resources':{'CPU_seconds':900,'wall_seconds':1200,'RSS_bytes':2*1024**3,'private_peak_bytes':CAP,'threads':2,'fits':0,'restorations':0,'HTTP':0}}
 put('CONSUMED.json',encoded(consumed))
 try:
  auth={}
  refs_to_validate={'annual':offer_cfg['annual']['container'],'schedule':offer_cfg['schedule'],'identity':offer_cfg['identity'],'cached_points':plan['cached_points']}
  refs_to_validate.update({'site_'+str(i):r for i,r in enumerate(offer_cfg.get('site_archives',[]))})
  for k,r in refs_to_validate.items():auth[k]=owner_validate(store,r)
  offers=load(plan['source_pins']['offers']['path'],'matched12_replay_offers')
  sys.path.insert(0,str(ROOT))
  offer_go={'state':'ROOT_AND_INDEPENDENT_GO','registered_by':'/root','worker_sha256':OFFERS_SHA,'config_sha256':sha(encoded(offer_cfg)),'derived_under_reviewed_outer_GO':go['worker_sha256']}
  result=offers.materialize(offer_cfg,offer_go)
  import pandas as pd
  entries={};manifest={}
  def keep(name,frame):
   body=frame_bytes(frame);entries[name]=body;manifest[name]={'rows':len(frame),'bytes':len(body),'sha256':sha(body)}
  keep('PRIMARY_FULL.parquet',result['primary'])
  for k,v in result['annual'].items():
   if isinstance(v,pd.DataFrame):keep('ANNUAL_'+k+'.parquet',v)
  for i,item in enumerate(result['site']):
   for k,v in item.items():
    if isinstance(v,pd.DataFrame):keep('SITE_'+str(i)+'_'+k+'.parquet',v)
  projection=offers.scoring_projection(result['primary']);scope=aux_cfg['scope']
  eligible=projection.season.isin(scope['seasons'])&projection.week.isin(scope['weeks'])&projection.target.isin(scope['targets'])
  omitted=projection.loc[~eligible]
  result['audit']['outside_auxiliary_scope']=[dict(zip(['target','season','week'],k),rows=int(n)) for k,n in omitted.groupby(['target','season','week']).size().items()]
  member='PRIMARY_SCORING_LEGACY_W1_6.parquet';keep(member,projection.loc[eligible].copy())
  entries['AUDIT.json']=encoded(result['audit']);entries['SOURCE_CONFIG.json']=encoded(offer_cfg)
  entries['MANIFEST.json']=encoded({'version':VERSION,'frames':manifest,'input_authentication':auth,'original_sources':'Exact original source containers remain retained by their original owners.'})
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
   for name,body in entries.items():z.writestr(name,body)
  if len(buf.getvalue())+65536>CAP:raise MemoryError('prepared frame/rejection capsule exceeds complete registered peak')
  freeze=put('PREPARED_OFFERS.zip',buf.getvalue())
  offer_ref={**freeze,'member':member,'member_sha256':manifest[member]['sha256']}
  aux=load(plan['source_pins']['aux']['path'],'matched12_replay_aux')
  aux_go={'state':'ROOT_AND_INDEPENDENT_GO','registered_by':'/root','worker_version':aux.VERSION,'worker_sha256':AUX_SHA,
   'configuration_sha256':sha(encoded(aux_cfg)),'input_sha256':plan['cached_points']['sha256'],'offer_input_sha256':freeze['sha256'],'derived_under_reviewed_outer_GO':go['worker_sha256']}
  put('DERIVED_EXACT_INNER_GO.json',encoded({'offer':offer_go,'auxiliary':aux_go,'effective_auxiliary_configuration':aux_cfg}))
  scored,bundle=aux.execute_bound(plan['cached_points'],aux_cfg,aux_go,read_go,offer_ref)
  for name,body in bundle.items():put(name,body)
  usage=store.verify_retained_checkpoint()
  if usage['new_peer_physical_bytes']-baseline>CAP:raise MemoryError('actual complete wave retained/peak allocation exceeded')
  safe={'version':VERSION,'run_id':plan['run_id'],'state':'PASS_LOCAL_FRESH_PROCESS_RESTORE_PENDING','new_fits':0,'model_restorations':0,'new_model_inference':0,'new_forecasts':0,'cached_scoring_runs':1,
   'worker_sha256':go['worker_sha256'],'plan_canonical_sha256':sha(encoded(plan)),'source_pins':{k:safe_ref(v) for k,v in plan['source_pins'].items()},
   'input_authentication':auth,'offer_preparation_audit':result['audit'],'effective_aux_configuration_canonical_sha256':sha(encoded(aux_cfg)),
   'aggregate_cap_amendment':plan['aggregate_cap_amendment'],'execution_counters':scored['execution_counters'],
   'side_state':scored['side_comparison']['state'],'captured_original_offers':scored['side_comparison']['offer_rows'],
   'offer_output_rows':scored['side_comparison']['offered_output_rows'],'outside_legacy_offers':scored['side_comparison']['recorded_offers_outside_legacy_expected_query_population'],
   'artifacts':{k:safe_ref(v) for k,v in refs.items()},'private_paths':'REDACTED_APPROVED_PRIVATE_ROUTE','offhost_restore':'NOT_VERIFIED',
   'retained_wave_checkpoint':'PASS','private_physical_delta_bytes_before_final_receipt':usage['new_peer_physical_bytes']-baseline,
   'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},
   'limitations':scored['limitations']+['Actual side replay covers legacy expected queries intersected with recovered recorded lines, not the new all-roster W1-7 primary.','No live deployment, new pregame capture, exact-line probability law restoration, EV or venue settlement is claimed.']}
  put('RESULT_RECEIPT.json',encoded(safe));store.verify_retained_checkpoint()
  return safe
 except BaseException as error:
  failure={'version':VERSION,'run_id':plan['run_id'],'state':'FAILED_OR_INTERRUPTED_EVIDENCE_RETAINED','error_type':type(error).__name__,
   'error_message_sha256':sha(str(error).encode()),'reason':'Full exact error text retained privately; paths/secrets are not printed.',
   'private_error':str(error),'retained_artifacts':{k:safe_ref(v) for k,v in refs.items()},'new_fits':0,'new_model_inference':0,'original_sources_preserved':True}
  try:put('FAILURE.json',encoded(failure));store.verify_retained_checkpoint()
  except BaseException:pass
  return {k:v for k,v in failure.items() if k!='private_error'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--plan-sha256',required=True);ap.add_argument('--go',type=Path,required=True);ap.add_argument('--go-sha256',required=True);a=ap.parse_args()
 limits();sys.dont_write_bytecode=True
 p=json.loads(exact({'path':str(a.plan),'bytes':a.plan.stat().st_size,'sha256':a.plan_sha256}));g=json.loads(exact({'path':str(a.go),'bytes':a.go.stat().st_size,'sha256':a.go_sha256}))
 result=execute(p,g);print(encoded(result).decode(),flush=True);signal.alarm(0)
 if result['state'].startswith('FAILED'):raise SystemExit(1)
if __name__=='__main__':main()
