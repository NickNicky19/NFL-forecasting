"""Bounded read-only verification, gated on root's completed freeze notice.

No fits, private writes, source acquisition, author scoring or peer models.
"""
import argparse, collections, datetime, gzip, hashlib, importlib.util, io, json, math, os, resource, signal, sys, time, zipfile
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KEY=['season','week','game_id','player_id']
CTX=['team','opponent','position','kickoff_utc','cutoff_utc']
ARMS=['RB_ONLY_LEAF_BASE','R1_RB_ONLY_LEAF_SUPPORT','R2_RB_ONLY_LEAF_PLAYER_OFFENSE','R3_RB_ONLY_LEAF_DEFENSE']
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def key(r):return(int(r['season']),int(r['week']),str(r['game_id']),str(r['player_id']))
def finite(x):return isinstance(x,(int,float))and not isinstance(x,bool)and math.isfinite(x)
def local(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def prior_cdf(prior,x):
 k=math.floor(x);d=k-int(prior['center']);q=float(prior['q'])
 return q**(-d)/(1+q)if d<0 else 1-q**(d+1)/(1+q)
def cdf(law,x):
 k=math.floor(x);emp=math.fsum(w for n,w in zip(law['support'],law['weights'])if n<=k);b=law['prior_weight']
 return(1-b)*emp+b*prior_cdf(law['prior'],x)
def mean(law):return(1-law['prior_weight'])*math.fsum(n*w for n,w in zip(law['support'],law['weights']))+law['prior_weight']*law['prior']['center']
def median(law):
 lo=min(law['support'][0]-1,law['prior']['center']-1,-1);hi=max(law['support'][-1],law['prior']['center'],1);step=1
 for _ in range(64):
  if cdf(law,lo)<.5 and cdf(law,hi)>=.5:break
  if cdf(law,lo)>=.5:lo-=step
  if cdf(law,hi)<.5:hi+=step
  step*=2
 else:raise AssertionError('independent median bracket exhausted')
 while hi-lo>1:
  mid=lo+(hi-lo)//2
  if cdf(law,mid)>=.5:hi=mid
  else:lo=mid
 return float(hi)
def tails(law,line):
 d=Decimal(str(line));low=int(d.to_integral_value(rounding=ROUND_CEILING))-1;floor=int(d.to_integral_value(rounding=ROUND_FLOOR));u=cdf(law,low);o=1-cdf(law,floor);p=1-u-o
 assert min(u,p,o)>-1e-12 and math.isclose(u+p+o,1.,abs_tol=1e-12)
 if d!=floor:assert abs(p)<1e-12
 return u,max(0.,p),o
def assert_law(law):
 assert law['kind']=='leaf_cdf'and law['prior']['support']=='signed_integer';ss=law['support'];ww=law['weights'];b=law['prior_weight'];q=law['prior']['q'];assert len(ss)==len(ww)>0 and 0<=b<=1 and 0<=q<1
 assert all(finite(x)and int(x)==x for x in ss)and all(l<r for l,r in zip(ss,ss[1:]));assert all(finite(w)and w>=0 for w in ww)and math.isclose(math.fsum(ww),1.,abs_tol=1e-12)
def run(a):
 start,cpu=time.monotonic(),time.process_time()
 assert a.root_notified_complete=='ROOT_NOTIFIED_LEAF_FREEZE_COMPLETE_V1'
 for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
 resource.setrlimit(resource.RLIMIT_CPU,(180,200));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
 def exhausted(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('bounded independent Leaf verification')
 signal.signal(signal.SIGXCPU,exhausted);signal.signal(signal.SIGALRM,exhausted);signal.alarm(540)
 def offline(event,_):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline independent verification')
 sys.addaudithook(offline);sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
 raw=a.receipt.read_bytes();assert sha(raw)==a.receipt_sha256;receipt=json.loads(raw);partial=receipt['state']=='FROZEN_NAMED_THREE_ARMS_DEFENSE_PENDING';active_arms=ARMS[:3]if partial else ARMS
 assert receipt['state']in['FROZEN_FORECASTS_COMPLETE_UNSCORED','FROZEN_NAMED_THREE_ARMS_DEFENSE_PENDING']and receipt['fits_attempted']==receipt['fits_returned']==len(active_arms)and set(receipt['models'])==set(active_arms)
 if not partial:assert receipt['new_fits_in_this_resume']==3 and receipt['restored_models_without_refit']==1
 rawplan=a.protocol.read_bytes();assert sha(rawplan)==a.protocol_sha256;plan=json.loads(rawplan);assert plan['arms']==ARMS
 for p,h in plan['code_sha256'].items():assert sha((ROOT/p).read_bytes())==h
 for p,h in plan['source_configuration_sha256'].items():assert sha((ROOT/p).read_bytes())==h
 import numpy as np,pandas as pd,pyarrow as pa,joblib
 from threadpoolctl import threadpool_limits
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 from nfl_lab import cdf_engine as engine,player_context_rush_efficiency_v1 as core
 increment=local('nfl_lab.profile_increment_a_v2','nfl_lab/profile_increment_a_v2.py');guard=local('nfl_lab.profile_increment_a_storage_v2','nfl_lab/profile_increment_a_storage_v2.py')
 old=local('tools.player_context_completion_efficiency_v1','tools/player_context_completion_efficiency_v1.py');local('tools.abc_a_dynamic_carry_wave_v1','tools/abc_a_dynamic_carry_wave_v1.py')
 from tools import category_topfive_matched12_storage_v1 as storage
 outer,_=storage.open_store(ROOT,allocation_sha256=guard.ALLOCATION,root_go=storage.GO,readonly=True);prior=outer.complete_peer.prior_forward;dest=prior.forward_root/'research'/guard.VERSION
 artifacts={r['id']:r for r in receipt['artifacts']}
 def read(ref):
  if isinstance(ref,str):ref=artifacts[ref]
  p=dest/ref['id'];prior.validate_reference(p,ref['sha256']);b=p.read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
 with outer.transaction():
  prior._refresh();native=prior._scan();statepath=dest/'ALLOCATION_ACCOUNTING_V3.json';prior.validate_reference(statepath);stateraw=statepath.read_bytes();state=json.loads(stateraw);assert state['retained_bytes']==guard.RETAINED and state['peak_bytes']==guard.PEAK
  if state['allocation_sha256']!=plan['allocation']['sha256']:
   ap=dest/'ALLOCATION_CODE_BINDING_AMENDMENT_V4.json';prior.validate_reference(ap);v4=json.loads(ap.read_bytes());assert v4['id']=='HISTORICAL_BOUNDARY_CODE_BINDING_V4'and v4['previous_allocation_sha256']==state['allocation_sha256']
   ap=dest/'ALLOCATION_CODE_BINDING_AMENDMENT_V5.json';prior.validate_reference(ap);amend=json.loads(ap.read_bytes());assert amend['id']=='SAVED_PILOT_RESUME_CODE_BINDING_V5'and amend['new_allocation_sha256']==plan['allocation']['sha256']and amend['previous_allocation_sha256']==v4['new_allocation_sha256']
   for amendment in [v4,amend]:
    assert amendment['accounting_state_sha256']==sha(stateraw)and amendment['policy']=='CODE_BINDING_ONLY_NO_BASELINE_FLOOR_CAP_OR_CONSUMPTION_RESET'
    assert set(amendment['changed_code_sha256'])<={'nfl_lab/profile_increment_a_storage_v2.py','nfl_lab/profile_increment_a_v2.py','tools/profile_increment_a_run_v2.py'}
  baseline=json.loads(gzip.decompress(read(state['baseline_prior_inode_ref'])));assert sum(baseline.values())==state['generation_baseline_prior_bytes']
  sibling=guard.generation_inventory([dest]);owned=sum(size for k,size in sibling.items()if k not in baseline);old_namespace=guard.unique_bytes(prior.forward_root/'research'/guard.OLD_VERSION)
  old_charge=max(old_namespace,state['old_charged_at_registration'],max(0,native['forward_physical_bytes']-state['old_baseline_prior_bytes']-owned));new_charge=max(guard.unique_bytes(dest),max(0,native['forward_physical_bytes']-state['baseline_prior_bytes']))
  assert old_charge<=guard.OLD_RETAINED and new_charge<=guard.RETAINED
  prior._require(guard.PROTECTED_PRIOR+old_charge+guard.PEAK);outer.complete_peer._require(guard.CAPTURE+guard.PEAK);outer._require(guard.PEAK)
  accounting=dict(state='PASS_READONLY_NATIVE_CAPS_AND_INDEPENDENT_CONTENT_GENERATION_ARITHMETIC',old_charged=old_charge,old_cap=guard.OLD_RETAINED,new_charged=new_charge,new_cap=guard.RETAINED,preserved_capture_reserve=guard.CAPTURE,preserved_peak=guard.PEAK)
 frozen=read(receipt['forecasts']);manifest=json.loads(gzip.decompress(frozen));assert receipt['forecasts_format']==manifest['format']=='IMMUTABLE_ORDERED_PART_MANIFEST_V1'and manifest['arm_order']==active_arms and len(manifest['parts'])==len(active_arms)
 if partial:assert manifest['source_fit_protocol_sha256']==a.protocol_sha256 and receipt['completed_arms']==active_arms and receipt['pending_arms']==[ARMS[3]]
 forecasts=[]
 for arm,part in zip(active_arms,manifest['parts']):
  assert part['arm']==arm;rows=json.loads(gzip.decompress(read(part)));assert len(rows)==part['rows']and all(r['arm']==arm for r in rows);forecasts.extend(rows)
 assert len(forecasts)==manifest['rows']==receipt['forecast_rows']and sha(enc(forecasts))==manifest['logical_combined_sha256']
 by={};law_checks=0;maximum_mean_difference=0.
 for r in forecasts:
  k=(r['arm'],key(r));assert k not in by;by[k]=r;law=r['law'];assert_law(law);law_checks+=1
  expected=mean(law);maximum_mean_difference=max(maximum_mean_difference,abs(expected-r['mean']));assert math.isclose(expected,r['mean'],rel_tol=1e-12,abs_tol=1e-10)
  assert int(r['median'])==r['median']and cdf(law,r['median'])>=.5-1e-12 and cdf(law,r['median']-1)<.5+1e-12
  assert r['conditioning']=='CONDITIONAL_ON_PLAYED'and r['original_issued_UTC']is None
  assert pd.Timestamp(r['source_information_max_UTC'])<pd.Timestamp(r['cutoff_utc'])
 assert set(r['arm']for r in forecasts)==set(active_arms)
 qinputs=pd.read_parquet(io.BytesIO(read('QUERY_PROFILE_INPUTS_2026.parquet')));assert len(qinputs)==receipt['query_rows']and not qinputs.duplicated(KEY).any();assert qinputs.position.eq('RB').all()
 assert set(tuple(k)for k in qinputs[KEY].itertuples(index=False,name=None))=={k for arm,k in by if arm==ARMS[0]}
 identities={key(r):r for r in qinputs.to_dict('records')}
 for r in forecasts:
  source_row=identities[key(r)]
  for field in CTX:
   assert pd.Timestamp(r[field])==pd.Timestamp(source_row[field])if field.endswith('_utc')else str(r[field])==str(source_row[field])
  cut,kick=pd.Timestamp(r['cutoff_utc']),pd.Timestamp(r['kickoff_utc']);assert cut<=kick
  if cut==kick:assert r['week']<=7 and r['query_clock_contract']=='HISTORICAL_AT_KICKOFF_RECONSTRUCTION'and r['query_evidence_tier']=='ASOF_AT_KICKOFF_RECONSTRUCTION_NOT_ISSUED_SOURCE_ROW_CONDITIONAL'
  else:assert r['week']==8 and r['query_clock_contract']=='CAPTURED_PRE_KICKOFF_BOARD_RECONSTRUCTION'
 basic=json.loads(gzip.decompress(read('BASIC_PROFILES_AND_COHORTS_2026.json.gz')));assert len(basic)==len(qinputs);assert {key(r)for r in basic}==set(tuple(k)for k in qinputs[KEY].itertuples(index=False,name=None))
 for r in basic:assert not any(k in r for k in ['actual','rush_yd','participation_state','realized'])
 expected_top=set();groups=collections.defaultdict(list);priority=0
 for r in basic:
  cut,kick=pd.Timestamp(r['cutoff_utc']),pd.Timestamp(r['kickoff_utc']);assert cut.tzinfo is not None and cut<=kick
  if cut==kick:assert r['week']<=7 and not r['universe_qualified']and r['query_clock_contract']=='HISTORICAL_AT_KICKOFF_RECONSTRUCTION'and r['query_evidence_tier']=='ASOF_AT_KICKOFF_RECONSTRUCTION_NOT_ISSUED_SOURCE_ROW_CONDITIONAL'
  else:assert r['week']==8 and r['query_clock_contract']=='CAPTURED_PRE_KICKOFF_BOARD_RECONSTRUCTION'
  available=r['reference_available_utc'];valid=available is not None and pd.Timestamp(available)<=cut and finite(r['reference_expected_carries'])and r['reference_expected_carries']>=0 and bool(r['reference_procedure_id'])
  reasons=[]
  if r['universe_qualified']and r['offer_qualified']:reasons.append('QUALIFIED_OFFER')
  if r['universe_qualified']and valid and r['reference_expected_carries']>=5:reasons.append('UNCHANGED_REFERENCE_EXPECTED_CARRIES_AT_LEAST_5')
  if r['universe_qualified']and r['replacement_role_qualified']:
   assert r['replacement_source_id'];reasons.append('SOURCE_SUPPORTED_REPLACEMENT')
  assert r['focus_reasons']==reasons and r['detailed_priority']==bool(reasons)and r['reference_eligible']==valid;priority+=bool(reasons)
  assert r['cohort_state']==('PREGAME_UNIVERSE_ADMITTED'if r['universe_qualified']else'RECONSTRUCTED_OR_UNQUALIFIED_UNIVERSE_BASIC_ONLY')
  if r['universe_qualified']and valid:groups[(r['season'],r['week'],r['kickoff_utc'],r['cutoff_utc'])].append(r)
 for group in groups.values():expected_top.update(key(r)for r in sorted(group,key=lambda r:(-r['reference_expected_carries'],r['player_id'],r['game_id']))[:20])
 assert{key(r)for r in basic if r['top20_workload']}==expected_top
 source_binding=json.loads(read('SOURCE_AND_PROFILE_BINDING.json'));assert source_binding==receipt['source_and_profile_binding'];assert source_binding['current_query_state']=='NOT_EXECUTED_NO_BOUND_CURRENT_PREGAME_QUERY_SOURCE'
 unavailable=json.loads(gzip.decompress(read('UNAVAILABLE_PROFILES_2026_W8.json.gz')));assert len(unavailable)==source_binding['W8']['unavailable_profile_rows']
 snapshots=json.loads(gzip.decompress(read('ALL32_RUSHING_DEFENSE_SNAPSHOTS_2026.json.gz')));cuts=sorted({r['information_cutoff_UTC']for r in snapshots});assert len(snapshots)==32*len(cuts)
 defense_cells=0
 for cut in [cuts[0],cuts[-1]]:
  panel=[r for r in snapshots if r['information_cutoff_UTC']==cut];assert{r['team']for r in panel}==set(increment.TEAMS)
  for r in panel:
   if r['latest_source_available_UTC']is not None:assert pd.Timestamp(r['latest_source_available_UTC'])<pd.Timestamp(cut)
   cells=r['descriptive_cells'];allcells=[c for c in cells if c['context_group']=='ALL']
   if cells:
    assert len(allcells)==1;total=allcells[0]
    for group in ['direction','gap','down_bin','distance','field','rush_kind']:
     pp=[c for c in cells if c['context_group']==group];assert sum(c['attempts']for c in pp)==total['attempts'];assert math.isclose(math.fsum(c['signed_yards']for c in pp),total['signed_yards'],abs_tol=1e-10)
    for c in cells:
     n=c['attempts'];assert n>0 and all(0<=c[k]<=n for k in ['nonpositive_count','explosive10_count','epa_positive_count','first_down_count']);assert math.isclose(c['mean_signed_yards'],c['signed_yards']/n,abs_tol=1e-12);defense_cells+=1
   for c in r['conditional_adjustment']:
    n=c['denominator'];v=c['numerator'];assert n>=0 and math.isclose(c['shrunk_estimate'],v/(n+80),abs_tol=1e-12);assert c['raw_estimate']is None if n==0 else math.isclose(c['raw_estimate'],v/n,abs_tol=1e-12)
 del snapshots
 pilot=json.loads(read('PILOT_RESOURCE_RECEIPT.json'));assert pilot['state']=='FIRST_RETURNED_MODEL_DURABLY_SAVED_READBACK'and pilot['model']==receipt['models'][ARMS[0]]and pilot['model']['bytes']<=plan['resources']['first_model_max_bytes'];assert 0<=pilot['CPU_seconds']<=plan['resources']['CPU_seconds']and 0<=pilot['wall_seconds']<=plan['resources']['wall_seconds']
 # Accepted source and transformations are restored only for deterministic cases.
 old.STATE['source_owner']=outer;data=old.load_inputs(pd);contracts={arm:increment.arm_category(data['category'],'R'+str(i),modeled_roles=['RB'])for i,arm in enumerate(ARMS)};full=data['queries'][2026].copy();w8,_,_=old.week8_queries(data,pd,build_features=True);full=pd.concat([full,w8],ignore_index=True);assert not full.duplicated(KEY).any();fmap={key(r):r for r in full.to_dict('records')}
 picks=[]
 for early in [True,False]:
  pp=[r for r in qinputs.to_dict('records')if(r['week']<=7)==early];pp=sorted(pp,key=lambda r:(float(fmap[key(r)]['f_player_games_prior'])>0,float(r['f_pce_own_carries']),sha(enc(list(key(r))))))
  chosen=pp[:2]+pp[-2:]if early else pp[:1]+pp[-1:]
  for r in chosen:
   if key(r)not in{key(x)for x in picks}:picks.append(r)
 keys={key(r)for r in picks};sample=full.loc[[key(r)in keys for r in full.to_dict('records')]].copy().reset_index(drop=True)
 context=core.EfficiencyContext(data['frames'],data['history']);rebuilt,_=context.augment(sample,rich=False);qmap={key(r):r for r in picks}
 for r in rebuilt.to_dict('records'):
  saved=qmap[key(r)]
  for name in core.EFFICIENCY_FEATURES:assert(pd.isna(r[name])and pd.isna(saved[name]))or math.isclose(r[name],saved[name],rel_tol=1e-12,abs_tol=1e-12)
 for c in core.EFFICIENCY_FEATURES:sample[c]=[qmap[key(r)][c]for r in sample.to_dict('records')]
 del context,data,full,rebuilt
 with zipfile.ZipFile(io.BytesIO(old.pin(old.doc('category-topfive-matched12-all-finalists-grade-v1.json.gz')['offers'])))as z:
  # Filename is read from the already pinned contract, never guessed.
  contract=old.doc('category-topfive-matched12-all-finalists-grade-v1.json.gz')['offers'];offers=pd.read_parquet(io.BytesIO(z.read(contract['member'])),columns=KEY+['target','position','line'])
 line_map=collections.defaultdict(list)
 for r in offers.loc[offers.target.eq('rush_yd')&offers.position.eq('RB')].to_dict('records'):
  if key(r)in keys:line_map[key(r)].append(float(r['line']))
 checks=[];tail_cases=0;loads=0
 def predictions(model,q):
  out={}
  for ix,law,reasons in model.predict_batches(q,batch_size=max(1,len(q))):
   assert law is not None
   for j,pos in enumerate(ix):out[key(q.iloc[int(pos)].to_dict())]=(dict(kind='leaf_cdf',support=law.support.tolist(),weights=law.weights[j].tolist(),prior=vars(law.prior),prior_weight=law.b),str(reasons[j])or None)
  return out
 for index,arm in enumerate(active_arms):
  ref=receipt['models'][arm];body=read(ref);model=joblib.load(io.BytesIO(body));loads+=1;assert isinstance(model,engine.LeafCDFModel)
  assert model.category==contracts[arm]and model.category['modeled_roles']==['RB']and set(model.priors)=={'RB'}and model.design.roles==['RB'];assert model.category['panels']['base']==model.category['panels']['context']==model.design.names
  base_count=len(model.design.names)-len([(),increment.SUPPORT,increment.SUPPORT+increment.PLAYER_OFFENSE,increment.SUPPORT+increment.PLAYER_OFFENSE+increment.DEFENSE][index]);assert base_count>0
  expected_block=list([(),increment.SUPPORT,increment.SUPPORT+increment.PLAYER_OFFENSE,increment.SUPPORT+increment.PLAYER_OFFENSE+increment.DEFENSE][index]);assert model.design.names[base_count:]==expected_block
  assert len(model.forest.estimators_)==32 and model.forest.n_features_in_==2*len(model.design.names)+1;assert model.prior_training_binding.position.eq('RB').all()and model.training_binding.position.eq('RB').all();assert model.audit['training_rows']==source_binding['RB_training_rows'];assert model.audit['modeled_training_rows']==len(model.training_binding)==len(model.prior_training_binding)==model.global_prior.n
  assert model.training_binding.season.lt(2026).all()and(pd.to_datetime(model.training_binding.outcome_available_utc,utc=True)<pd.Timestamp('2026-09-01',tz='UTC')).all()
  labels=sorted(map(float,model.prior_training_binding.rush_yd));assert all(math.isfinite(y)and int(y)==y for y in labels);center=int(labels[(len(labels)-1)//2]);scale=max(1.,math.fsum(abs(y-center)for y in labels)/len(labels));assert model.global_prior.center==center and math.isclose(model.global_prior.q,scale/(1+scale),abs_tol=1e-12)and vars(model.global_prior)==vars(model.priors['RB'])
  used={model.design.names[int(f)//2]for tree in model.forest.estimators_ for f in tree.tree_.feature if 0<=f<2*len(model.design.names)}
  with threadpool_limits(limits=1):
   batch=predictions(model,sample);single={k:v for i in range(len(sample))for k,v in predictions(model,sample.iloc[[i]].reset_index(drop=True)).items()};shuffled=predictions(model,sample.iloc[::-1].reset_index(drop=True));column_shuffled=predictions(model,sample[list(reversed(sample.columns))]);poisoned=predictions(model,sample.assign(actual=999999,rush_yd=-999999,outcome_available_utc=pd.Timestamp('2099-01-01',tz='UTC')))
   designed=model.design.transform(sample);np.testing.assert_array_equal(designed,model.design.transform(sample[list(reversed(sample.columns))]));leaves=model.forest.apply(designed)
  fallback_n=0
  for i,r in enumerate(sample.to_dict('records')):
   k=key(r);law,reason=batch[k];saved=by[(arm,k)];fallback_n+=bool(reason)
   for alternative in [single[k],shuffled[k],column_shuffled[k],poisoned[k]]:
    assert alternative[1]==reason;np.testing.assert_array_equal(alternative[0]['support'],law['support']);np.testing.assert_array_equal(alternative[0]['weights'],law['weights']);assert alternative[0]['prior']==law['prior']and alternative[0]['prior_weight']==law['prior_weight']
   assert reason==saved['fallback'];np.testing.assert_allclose(law['weights'],saved['law']['weights'],rtol=0,atol=1e-12);assert law['support']==saved['law']['support']and law['prior']==saved['law']['prior']and law['prior_weight']==saved['law']['prior_weight']
   if reason:assert reason=='cold_start_role_prior'and law['prior_weight']==1.
   else:
    weights=np.zeros(len(model.support))
    for j,hist in enumerate(model.leaf_histograms):weights+=hist[leaves[i,j]].toarray()[0]
    weights/=len(model.leaf_histograms);np.testing.assert_allclose(weights,law['weights'],rtol=0,atol=1e-12)
   assert math.isclose(mean(law),saved['mean'],rel_tol=1e-12,abs_tol=1e-10)and median(law)==saved['median']
   native=engine.MixtureBatch(law['support'],[law['weights']],engine.SupportPrior(**law['prior']),prior_weight=law['prior_weight'])
   lines=sorted(set(line_map.get(k,[])+[-1.,0.,.5,10.,10.5,100.25]))
   last_u=-1.;last_o=2.
   for line in lines:
    u,p,o=tails(law,line);d=Decimal(str(line));floor=int(d.to_integral_value(rounding=ROUND_FLOOR));lower=int(d.to_integral_value(rounding=ROUND_CEILING))-1;expected_u=float(native.cdf(lower)[0]);expected_o=1-float(native.cdf(floor)[0]);assert math.isclose(u,expected_u,abs_tol=1e-12)and math.isclose(o,expected_o,abs_tol=1e-12);assert u>=last_u-1e-12 and o<=last_o+1e-12;last_u,last_o=u,o;tail_cases+=1
    if d%1==Decimal('.5'):
     if saved['median']>line:assert o>=.5-1e-12
     else:assert u>=.5-1e-12
  checks.append(dict(arm=arm,artifact_sha256=ref['sha256'],cases=len(sample),fallback_cases=fallback_n,numeric_features=len(model.design.names),RB_training_rows=len(model.training_binding),actual_support_split_fields=len(used&set(increment.SUPPORT)),actual_player_split_fields=len(used&set(increment.PLAYER_OFFENSE)),actual_defense_split_fields=len(used&set(increment.DEFENSE)),single_batch_shuffle_column_and_target_mutation='EXACT',saved_laws_and_independent_leaf_histogram_reconstruction='PASS'));del model
 result={'id':'PROFILE-INCREMENT-TO-RELEASE-01-A-INDEPENDENT-LEAF-v1','state':'PASS_FROZEN_LAWS_MODELS_COHORT_AND_PROFILE_CONTRACTS','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'receipt_sha256':a.receipt_sha256,'protocol_sha256':a.protocol_sha256,'code_sha256':sha(Path(__file__).read_bytes()),'forecast_freeze_sha256':sha(frozen),'all_retained_laws_checked':law_checks,'maximum_independent_mean_difference':maximum_mean_difference,'profile_input_parity_cases':len(sample),'cohort_rows':len(basic),'detailed_priority':priority,'top20_workload':len(expected_top),'defense_snapshots':32*len(cuts),'sampled_defense_descriptive_cells':defense_cells,'exact_line_tail_cases':tail_cases,'pilot_resources_and_durable_model_binding':'PASS','native_accounting':accounting,'model_checks':checks,'limits':['Only authenticated own frozen models; no fresh fit or peer model loading.','Profile reconstruction and source admission reuse accepted current-vintage seven-day contracts; they do not authenticate original source vintages.','Raw source/97-feature audit and training-derived profile transforms are not repeated in full.','Cohort formulas independently checked on saved eligible fields; no current-query packet or live qualification is inferred.','Selected source lines and fictional numerical boundaries are both tested; fictional boundaries add zero NFL evidence.'],'activity':{'fits':0,'model_loads':loads,'private_writes':0,'source_HTTP':0,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
 result.update(logical_forecast_rows_sha256=manifest['logical_combined_sha256'],completed_arms=active_arms,pending_arms=[a for a in ARMS if a not in active_arms],owner_resume_new_fits=receipt.get('new_fits_in_this_resume'),owner_restored_models_without_refit=receipt.get('restored_models_without_refit'),original_pilot_cost={'fit_only_CPU_seconds':plan['saved_pilot_resume']['previous_fit_CPU_seconds'],'CPU_including_save_readback':pilot['CPU_seconds'],'wall_including_save_readback':pilot['wall_seconds']})
 if partial:result['state']='PASS_NAMED_THREE_ARM_FREEZE_DEFENSE_UNAVAILABLE_PENDING'
 a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');signal.alarm(0);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root-notified-complete',required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--receipt-sha256',required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--protocol-sha256',required=True);p.add_argument('--output',type=Path,default=Path('reports/abc-championship/profile-increment-to-release-01/INDEPENDENT_PARTIAL_MODEL_CHECK_V1.json'));a=p.parse_args()
 try:run(a)
 except BaseException as e:
  signal.alarm(0);r={'state':'FAILED_INDEPENDENT_LEAF_CHECK_NO_REFIT','error_type':type(e).__name__,'error_sha256':sha(str(e).encode()),'code_sha256':sha(Path(__file__).read_bytes()),'receipt_sha256':a.receipt_sha256,'fits':0,'private_writes':0};a.output.with_name(a.output.stem+'-failure.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');raise
