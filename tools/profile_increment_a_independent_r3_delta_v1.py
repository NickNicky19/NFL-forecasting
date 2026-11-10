"""Verify only the newly finished R3 state; reuse accepted three-arm evidence."""
import argparse,datetime,gzip,hashlib,importlib.util,io,json,math,os,resource,signal,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARMS=['RB_ONLY_LEAF_BASE','R1_RB_ONLY_LEAF_SUPPORT','R2_RB_ONLY_LEAF_PLAYER_OFFENSE','R3_RB_ONLY_LEAF_DEFENSE']
KEY=['season','week','game_id','player_id'];CTX=['team','opponent','position','kickoff_utc','cutoff_utc']
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def key(r):return(int(r['season']),int(r['week']),str(r['game_id']),str(r['player_id']))
def local(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def run(a):
 assert a.root_notified_complete=='ROOT_NOTIFIED_R3_COMPLETE_FREEZE_V1';started,cpu=time.monotonic(),time.process_time()
 for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
 resource.setrlimit(resource.RLIMIT_CPU,(60,70));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
 def limit(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('remaining independent R3 model allowance')
 signal.signal(signal.SIGXCPU,limit);signal.signal(signal.SIGALRM,limit);signal.alarm(360)
 sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
 def document(path,digest):
  b=path.read_bytes();assert sha(b)==digest;return json.loads(b)
 receipt=document(a.receipt,a.receipt_sha256);assert receipt['state']=='FROZEN_FORECASTS_COMPLETE_UNSCORED'and receipt['fits_attempted']==receipt['fits_returned']==4 and receipt['new_fits_this_supplement']==1 and receipt['reused_models_without_refit_or_inference']==3
 previous=document(a.previous_model_review,a.previous_model_review_sha256);assert previous['state']=='PASS_NAMED_THREE_ARM_FREEZE_DEFENSE_UNAVAILABLE_PENDING'and previous['activity']['fits']==0
 partial=document(a.partial_receipt,a.partial_receipt_sha256);assert partial['state']=='FROZEN_NAMED_THREE_ARMS_DEFENSE_PENDING'and partial['completed_arms']==ARMS[:3]
 assert previous['receipt_sha256']==a.partial_receipt_sha256 and enc(receipt['source_and_profile_binding'])==enc(partial['source_and_profile_binding'])
 plan=document(a.protocol,a.protocol_sha256);assert plan['maximum_new_fits']==1 and plan['remaining_global_fit_slot']==4
 for p,d in plan['code_sha256'].items():assert sha((ROOT/p).read_bytes())==d
 for p,d in plan['source_configuration_sha256'].items():assert sha((ROOT/p).read_bytes())==d
 import numpy as np,pandas as pd,pyarrow as pa,joblib
 from threadpoolctl import threadpool_limits
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 from nfl_lab import cdf_engine as engine
 increment=local('nfl_lab.profile_increment_a_v2','nfl_lab/profile_increment_a_v2.py')
 helperpath=ROOT/'tools/profile_increment_a_independent_leaf_v4.py';assert sha(helperpath.read_bytes())=='899c34b1b6f0a6025724de68fef46fe502ff5dc711f0428e9da6c16bb2c6f5a3';maths=local('independent_previous_leaf_helpers','tools/profile_increment_a_independent_leaf_v4.py')
 child=local('nfl_lab.profile_increment_a_def_remainder_storage_v1','nfl_lab/profile_increment_a_def_remainder_storage_v1.py');h=child.helpers(ROOT);outer,prior=child.attach(ROOT)
 primary=prior.forward_root/'research'/child.PRIMARY;remainder=prior.forward_root/'research'/child.VERSION;legacy=prior.forward_root/'research'/child.OLD
 def read(ref,default='PRIMARY'):
  namespace=ref.get('namespace',default);assert namespace in ['PRIMARY','DEF_REMAINDER'];name=Path(ref['id']);assert not name.is_absolute()and'..'not in name.parts;p=(primary if namespace=='PRIMARY'else remainder)/name;prior.validate_reference(p,ref['sha256']);b=p.read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
 def state(path):prior.validate_reference(path);return json.loads(path.read_bytes())
 with outer.transaction():
  ps=state(primary/'ALLOCATION_ACCOUNTING_V3.json');old=state(legacy/'ALLOCATION_STATE.json');cs=state(remainder/'ALLOCATION_STATE.json');assert cs['allocation_sha256']==plan['allocation']['sha256']and ps['retained_bytes']==16*1024**2 and old['retained_bytes']==8*1024**2 and cs['retained_bytes']==8*1024**2
  pb=json.loads(gzip.decompress(read(ps['baseline_prior_inode_ref'])));cb=json.loads(gzip.decompress(read(cs['baseline_ref'],'DEF_REMAINDER')));native=prior._scan();pg=h.generation_inventory([primary]);cg=h.generation_inventory([remainder]);po={k:v for k,v in pg.items()if k not in pb};co={k:v for k,v in cg.items()if k not in cb};union=dict(po)
  for k,v in co.items():assert k not in union or union[k]==v;union[k]=v
  physical=native['forward_physical_bytes'];oc=max(h.unique_bytes(legacy),ps['old_charged_at_registration'],max(0,physical-old['baseline_prior_bytes']-sum(union.values())));pc=max(h.unique_bytes(primary),cs['primary_charge_floor_bytes'],max(0,physical-ps['baseline_prior_bytes']-sum(co.values())));cc=max(h.unique_bytes(remainder),max(0,physical-cs['baseline_prior_bytes']))
  assert oc<=8*1024**2 and pc<=16*1024**2 and cc<=8*1024**2;prior._require(child.PROTECTED_PRIOR+oc+child.PRIMARY_RETAINED+child.PEAK);outer.complete_peer._require(child.CAPTURE)
  accounting=dict(old8_charged=oc,primary16_charged=pc,supplement8_charged=cc,union_owned_bytes=sum(union.values()),capture_reserved=child.CAPTURE,primary_reserved=child.PRIMARY_RETAINED)
 pmanifest=json.loads(gzip.decompress(read(partial['forecasts'])));manifest_body=read(receipt['forecasts'],'DEF_REMAINDER');manifest=json.loads(gzip.decompress(manifest_body));assert manifest['arm_order']==ARMS and len(manifest['parts'])==4 and manifest['format']=='IMMUTABLE_ORDERED_PART_MANIFEST_V1'
 old_hash=hashlib.sha256();full_hash=hashlib.sha256();old_hash.update(b'[');full_hash.update(b'[');r0=None;newrows=None
 for i,part in enumerate(manifest['parts']):
  assert part['arm']==ARMS[i]
  if i<3:
   expected=pmanifest['parts'][i];assert all(part[k]==expected[k]for k in ['id','bytes','sha256','rows','arm'])and part['namespace']=='PRIMARY';assert all(receipt['models'][ARMS[i]][k]==partial['models'][ARMS[i]][k]for k in ['id','bytes','sha256'])
  body=gzip.decompress(read(part));assert body.startswith(b'[')and body.endswith(b']\n')
  if i:full_hash.update(b',')
  full_hash.update(body[1:-2])
  if i<3:
   if i:old_hash.update(b',')
   old_hash.update(body[1:-2])
  if i==0:r0=json.loads(body)
  if i==3:newrows=json.loads(body);assert len(newrows)==part['rows']==1364
 old_hash.update(b']\n');full_hash.update(b']\n');assert old_hash.hexdigest()==pmanifest['logical_combined_sha256']==previous['logical_forecast_rows_sha256'];assert full_hash.hexdigest()==manifest['logical_combined_sha256']and manifest['rows']==receipt['forecast_rows']==5456
 refs={r['id']:r for r in receipt['artifacts']};base=pd.read_parquet(io.BytesIO(read(refs['QUERY_BASE_INPUTS_RECOVERED_V5.parquet'])));pce=pd.read_parquet(io.BytesIO(read(refs['QUERY_PROFILE_INPUTS_2026.parquet'])))
 for frame in [base,pce]:
  for c in ['kickoff_utc','cutoff_utc']:frame[c]=pd.to_datetime(frame[c],utc=True)
 q=base.merge(pce,on=KEY+CTX,how='inner',sort=False,validate='one_to_one');assert len(q)==1364 and not q.duplicated(KEY).any()and q.position.eq('RB').all();qm={key(r):r for r in q.to_dict('records')};new={key(r):r for r in newrows};oldmap={key(r):r for r in r0};assert set(qm)==set(new)==set(oldmap)
 fallback0={k for k,r in oldmap.items()if r['fallback']not in[None,'',False,'none']};fallback3={k for k,r in new.items()if r['fallback']not in[None,'',False,'none']};assert fallback0==fallback3
 for k in fallback3:assert new[k]['fallback']==oldmap[k]['fallback']and new[k]['mean']==oldmap[k]['mean']and new[k]['median']==oldmap[k]['median']and enc(new[k]['law'])==enc(oldmap[k]['law'])
 maxmean=0.
 for k,r in new.items():
  assert r['arm']==ARMS[3]and r['target']=='rush_yd'and r['original_issued_UTC']is None;maths.assert_law(r['law']);expected=maths.mean(r['law']);maxmean=max(maxmean,abs(expected-r['mean']));assert math.isclose(expected,r['mean'],rel_tol=1e-12,abs_tol=1e-10)and maths.cdf(r['law'],r['median'])>=.5-1e-12 and maths.cdf(r['law'],r['median']-1)<.5+1e-12
  for c in CTX:assert pd.Timestamp(r[c])==pd.Timestamp(qm[k][c])if c.endswith('_utc')else str(r[c])==str(qm[k][c])
  assert pd.Timestamp(r['source_information_max_UTC'])<pd.Timestamp(r['cutoff_utc'])
 chosen=[]
 for early in [True,False]:
  rr=sorted([r for r in q.to_dict('records')if(r['week']<=7)==early],key=lambda r:(float(r['f_player_games_prior'])>0,float(r['f_pce_own_carries']),sha(enc(list(key(r))))));pick=rr[:2]+rr[-2:]if early else rr[:1]+rr[-1:]
  for r in pick:
   if key(r)not in{key(x)for x in chosen}:chosen.append(r)
 sample=pd.DataFrame(chosen).reset_index(drop=True);model_ref=receipt['models'][ARMS[3]];model=joblib.load(io.BytesIO(read(model_ref,'DEF_REMAINDER')));assert isinstance(model,engine.LeafCDFModel);recovery=json.loads(read(refs['QUERY_RECOVERY_BINDING_V5.json']))if'QUERY_RECOVERY_BINDING_V5.json'in refs else None
 base_names=list(base.columns[base.columns.str.startswith('f_')]);base_names=[c for c in base_names if c not in increment.SUPPORT+increment.PLAYER_OFFENSE+increment.DEFENSE+increment.INTERACTIONS]
 expected=(recovery['original_base_columns']if recovery else base_names)+list(increment.SUPPORT+increment.PLAYER_OFFENSE+increment.DEFENSE);assert model.design.names==expected==model.category['panels']['base']==model.category['panels']['context']and model.category['modeled_roles']==['RB']and model.design.roles==['RB'];assert len(model.forest.estimators_)==32 and model.forest.n_features_in_==2*len(expected)+1
 training=model.training_binding;assert training.position.eq('RB').all()and training.season.lt(2026).all()and len(training)==model.audit['modeled_training_rows']==10527 and(pd.to_datetime(training.outcome_available_utc,utc=True)<pd.Timestamp('2026-09-01',tz='UTC')).all();assert set(model.priors)=={'RB'}and vars(model.priors['RB'])==vars(model.global_prior)
 def predict(frame):
  result={}
  for ix,law,reasons in model.predict_batches(frame,batch_size=max(1,len(frame))):
   for j,pos in enumerate(ix):result[key(frame.iloc[int(pos)].to_dict())]=(dict(kind='leaf_cdf',support=law.support.tolist(),weights=law.weights[j].tolist(),prior=vars(law.prior),prior_weight=law.b),str(reasons[j])or None)
  return result
 with threadpool_limits(limits=1):
  batch=predict(sample);single={k:v for i in range(len(sample))for k,v in predict(sample.iloc[[i]].reset_index(drop=True)).items()};shuffle=predict(sample.iloc[::-1].reset_index(drop=True));columns=predict(sample[list(reversed(sample.columns))]);poison=predict(sample.assign(actual=999999,rush_yd=-999999,outcome_available_utc=pd.Timestamp('2099-01-01',tz='UTC')));leaves=model.forest.apply(model.design.transform(sample))
 tailchecks=0
 for i,r in enumerate(sample.to_dict('records')):
  k=key(r);law,reason=batch[k]
  for other in [single[k],shuffle[k],columns[k],poison[k]]:assert enc(other)==enc(batch[k])
  assert enc(law)==enc(new[k]['law'])and reason==new[k]['fallback'];assert math.isclose(maths.mean(law),new[k]['mean'],rel_tol=1e-12,abs_tol=1e-10)and maths.median(law)==new[k]['median']
  if not reason:
   weights=np.zeros(len(model.support))
   for j,hist in enumerate(model.leaf_histograms):weights+=hist[leaves[i,j]].toarray()[0]
   weights/=len(model.leaf_histograms);np.testing.assert_allclose(weights,law['weights'],rtol=0,atol=1e-12)
  native=engine.MixtureBatch(law['support'],[law['weights']],engine.SupportPrior(**law['prior']),prior_weight=law['prior_weight'])
  for line in [-1.,0.,.5,10.,10.5,100.25]:
   u,p,o=maths.tails(law,line);assert math.isclose(u,float(native.cdf(math.ceil(line)-1)[0]),abs_tol=1e-12)and math.isclose(o,1-float(native.cdf(math.floor(line))[0]),abs_tol=1e-12);tailchecks+=1
 used={expected[int(f)//2]for t in model.forest.estimators_ for f in t.tree_.feature if 0<=f<2*len(expected)}
 result={'id':'PROFILE-INCREMENT-A-INDEPENDENT-R3-DELTA-v1','state':'PASS_ONLY_NEW_R3_MODEL_AND_COMPLETION_WITH_PRIOR_THREE_ACCEPTANCE_REUSED','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'receipt_sha256':a.receipt_sha256,'protocol_sha256':a.protocol_sha256,'code_sha256':sha(Path(__file__).read_bytes()),'reused_partial_model_review_sha256':a.previous_model_review_sha256,'reused_partial_receipt_sha256':a.partial_receipt_sha256,'old_three_model_and_part_hashes':'UNCHANGED','old_three_logical_rows_sha256':old_hash.hexdigest(),'complete_logical_rows_sha256':full_hash.hexdigest(),'R3_laws_checked':len(new),'maximum_independent_mean_difference':maxmean,'new_R3_case_checks':len(sample),'fallback_case_checks':sum(bool(v[1])for v in batch.values()),'tail_boundary_checks':tailchecks,'all_fallback_identities_and_outputs_equal_R0':True,'fallback_rows':len(fallback3),'recorded_input_split_fields':dict(support=len(used&set(increment.SUPPORT)),player=len(used&set(increment.PLAYER_OFFENSE)),defense=len(used&set(increment.DEFENSE))),'native_accounting':accounting,'limits':['Only newR3model deserialized/inferred; earlier three models/source profiles/fits not repeated.','Prior source-vintage, historical-universe and seven-day timing limits retained. No fresh-fit reproduction, current-query or deployment claim.','Numerical boundary fixtures add zeroNFL observations; actual offered-line regrade remains separate.'],'activity':{'fits':0,'model_loads':1,'old_model_loads':0,'raw_profile_reconstructions':0,'private_writes':0,'source_HTTP':0,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
 a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');signal.alarm(0);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root-notified-complete',required=True)
 for name in ['receipt','protocol','partial-receipt','previous-model-review','output']:p.add_argument('--'+name,type=Path,required=True)
 for name in ['receipt-sha256','protocol-sha256','partial-receipt-sha256','previous-model-review-sha256']:p.add_argument('--'+name,required=True)
 a=p.parse_args()
 try:run(a)
 except BaseException as e:
  signal.alarm(0);r={'state':'FAILED_R3_DELTA_NO_REFIT','error_type':type(e).__name__,'error_sha256':sha(str(e).encode()),'code_sha256':sha(Path(__file__).read_bytes()),'receipt_sha256':a.receipt_sha256,'fits':0,'private_writes':0};a.output.with_name(a.output.stem+'-failure.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');raise
