"""Run only after the root's explicit completion notification; no fits/writes."""
import argparse,collections,datetime,gzip,hashlib,io,json,lzma,math,os,resource,signal,sys,time
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def cli():
 p=argparse.ArgumentParser();p.add_argument('--root-notified-complete',required=True,choices=['ROOT_NOTIFIED_COMPLETION_V1']);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--receipt-sha256',required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--output',type=Path,default=Path('/tmp/completion-efficiency-independent-runtime-review.json'));return p.parse_args()

def run(a):
 for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
 resource.setrlimit(resource.RLIMIT_CPU,(250,300));resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,)*2)
 def exhausted(signum,_frame):
  if signum==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('root separately registered independent audit envelope')
 signal.signal(signal.SIGXCPU,exhausted);signal.signal(signal.SIGALRM,exhausted);signal.alarm(540)
 root=Path('/workspace/nfl-methods-integration');sys.path.insert(0,str(root));sys.dont_write_bytecode=True
 start=time.monotonic();cpu=time.process_time()
 raw=a.receipt.read_bytes();assert sha(raw)==a.receipt_sha256;receipt=json.loads(raw);assert receipt['state']=='FROZEN_FORECASTS_COMPLETE_UNSCORED'
 assert receipt['fits_attempted']==5 and receipt['fits_returned']==5
 import numpy as np,pandas as pd,pyarrow as pa,joblib
 from threadpoolctl import threadpool_limits
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 # Own classes are imported before the frozen storage package is attached.
 from nfl_lab import cdf_engine as cdf,median_boosting as hgb,abc_dynamic_carry_v1,abc_player_rushing_context_v1,player_context_rush_efficiency_v1 as core,player_context_completion_features_v1,category_topfive_backfield_v1
 from tools import category_topfive_matched12_storage_v1 as storage,player_context_completion_efficiency_v1 as producer
 outer,_=storage.open_store(root,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=storage.GO,readonly=True)
 prior=outer.complete_peer.prior_forward;dest=prior.forward_root/'research/PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1'
 artifacts={r['id']:r for r in receipt['artifacts']}
 def read(name,override=None):
  r=override if override is not None else artifacts[name];p=dest/name;prior.validate_reference(p,r['sha256']);b=p.read_bytes();assert len(b)==r['bytes']and sha(b)==r['sha256'];return b
 planraw=read('PRIVATE_EXECUTION_PLAN.json');assert sha(planraw)==a.plan_sha256;plan=json.loads(planraw)
 for p,h in plan['code_sha256'].items():assert sha((root/p).read_bytes())==h
 for p,h in plan['source_configuration_sha256'].items():assert sha((root/p).read_bytes())==h
 frozen=read(receipt['forecasts']['id'],receipt['forecasts']);forecasts=json.loads(gzip.decompress(frozen));assert len(forecasts)==receipt['forecast_rows']
 assert all(x.get('probability')is None and x.get('outcome_law')is None for x in forecasts)
 # Independent closed form: geometric tail moment is q**a*(a+q/(1-q)).
 def independent_moments(law):
  atoms=list(zip(law['support'],law['weights']));b=law['prior_weight'];q=law['prior']['q']
  tail=lambda k:q**k*(k+q/(1-q));ranges=[(0,0),(1,4),(5,9),(10,19),(20,None)];out=[]
  for lo,hi in ranges:
   empirical=math.fsum(float(n)*float(w)for n,w in atoms if n>=lo and(hi is None or n<=hi));geo=0. if hi==0 else tail(lo)-(tail(hi+1)if hi is not None else 0.)
   out.append((1-b)*empirical+b*geo)
  return out,(1-b)*math.fsum(float(n)*float(w)for n,w in atoms)+b*q/(1-q)
 synthetic=0;moment_max=0.
 for q in [.1,.8,.997]:
  for b in [0.,.01,.5,1.]:
   support=[0,1,4,5,9,10,19,20,55,10000];weights=[(i+1)/55 for i in range(10)];law=dict(kind='leaf_cdf',support=support,weights=weights,prior=dict(support='count',q=q),prior_weight=b)
   expected,mean=independent_moments(law);got,gm=core.carry_bucket_moments(law);np.testing.assert_allclose(got,expected,rtol=1e-11,atol=1e-10);assert math.isclose(gm,mean,rel_tol=1e-12);assert math.isclose(sum(expected),mean,rel_tol=1e-12);moment_max=max(moment_max,float(np.max(np.abs(got-np.asarray(expected)))));synthetic+=1
 class SyntheticContext:
  def profile(self,*args):return{'f_pce_own_yards':-2.},pd.Timestamp('2024-01-01',tz='UTC'),None
  def mixture(self,*args):return{('middle','guard','1','long'):1.},dict(bucket='synthetic',own_carries=0,team_rb_carries=0,league_rb_carries=0,state='DECLARED_FICTIONAL_CASE',contexts=1)
 class SyntheticNegativeModel:
  def predict_many(self,features,contexts):return np.full(len(contexts),-3.),np.full(len(contexts),.25)
 row=type('FictionalQuery',(),dict(player_id='fiction',team='AAA',opponent='BBB',cutoff_utc=pd.Timestamp('2024-02-01',tz='UTC')))();law=dict(kind='leaf_cdf',support=[0,4],weights=[.5,.5],prior=dict(support='count',q=.8),prior_weight=.2)
 negative=core.integrated_point(SyntheticNegativeModel(),SyntheticContext(),row,law);assert negative['point']<0 and math.isclose(negative['point'],-3*negative['fixed_n_mean'],abs_tol=1e-12);assert negative['probability']is None and negative['outcome_law']is None
 # Load already approved immutable football source, without rebuilding97 features.
 producer.STATE['source_owner']=outer;data=producer.load_inputs(pd);ctx=core.EfficiencyContext(data['frames'],data['history']);expected_training={}
 for year in [2025,2026]:
  tr=data['train'];mask=tr.season.lt(year)&(pd.to_datetime(tr.outcome_available_utc,utc=True)<pd.Timestamp(str(year)+'-09-01',tz='UTC'));supported=tr.loc[mask&tr.participation_state.eq('played')&cdf.valid_support(cdf.numeric(tr,'rush_yd'),'signed_integer')];expected_training[year]=(len(supported),int(supported.position.isin(data['category']['modeled_roles']).sum()))
 del data['train'],data['oldtrain'],data['history'];laws,_=producer.cached_laws(data['queries'])
 selected={};profile_packet_checks=[]
 def decode_selected(packet,p):
  out=dict(p['identity']);rows=[]
  for d,values in zip(packet['definitions'],p['values']):
   r=dict(d['constants'])
   for k,v in zip(d['fields'],values):r[k]=p['clocks'][v]if k.endswith('_clock')and v is not None else v
   rows.append(r)
  out['tendencies']=rows;return out
 for year in [2025,2026]:
  body=read('PROFILES_%d.json.xz'%year);packet=json.loads(lzma.decompress(body));assert packet['codec']=='LOSSLESS_PROFILE_SCHEMA_CLOCK_FACTORIZATION_V1'
  eligible=[p for p in packet['profiles']if int(p['identity']['week'])<=7];ordered=sorted(eligible,key=lambda p:(int(p['identity']['eligible_player_carries']),sha(enc([p['identity']['game_id'],p['identity']['player_id']]))))
  # No target outcome or forecast value participates in deterministic case choice.
  picks=[]
  for pp in ordered[:2]+ordered[-2:]:
   k=(int(pp['identity']['season']),int(pp['identity']['week']),pp['identity']['game_id'],pp['identity']['player_id'])
   if k not in {x[0]for x in picks}:picks.append((k,decode_selected(packet,pp)))
  selected[year]=picks
  clock_count=0
  for pp in packet['profiles']:
   cut=pd.Timestamp(pp['identity']['cutoff_utc']);used=pp['identity']['source_information_max_utc']
   if used is not None:assert pd.Timestamp(used)<cut
   for clock in pp['clocks']:assert pd.Timestamp(clock)<cut;clock_count+=1
  profile_packet_checks.append(dict(season=year,profiles=len(packet['profiles']),selected_cases=len(picks),eligible_clock_values_checked=clock_count));del packet
 # Reconstruct only selected raw profiles/feature rows, never all training features.
 qcases={};profile_exact=0
 for year,picks in selected.items():
  keys={k for k,p in picks};q=data['queries'][year];positions=[i for i,r in enumerate(q.itertuples())if(int(r.season),int(r.week),str(r.game_id),str(r.player_id))in keys];small=q.iloc[positions].copy().reset_index(drop=True);aug,profiles=ctx.augment(small,rich=True)
  wanted={k:p for k,p in picks}
  for p in profiles:
   k=(int(p['season']),int(p['week']),p['game_id'],p['player_id']);assert enc(p)==enc(wanted[k]);profile_exact+=1
  qcases[year]=aug
 # Recompute raw-to-profile numerators/denominators and nested shrinkage.
 # Source admission/game membership is the already accepted manifest; no cached
 # aggregate/context/efficiency fields enter these independent sums.
 raw_frames=[]
 for frame in data['frames']:
  ff=frame.loc[frame.rush_attempt.eq(1)&frame.two_point_attempt.eq(0),['game_id','play_id','posteam','rusher_player_id','run_location','rushing_yards','epa','first_down_rush']].copy()
  ff['posteam']=ff.posteam.replace({'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'})
  ff['game_id']=ff.game_id.astype(str);ff['rusher_player_id']=ff.rusher_player_id.astype(str);raw_frames.append(ff)
 raw_plays=pd.concat(raw_frames,ignore_index=True)
 assert not raw_plays.duplicated(['game_id','play_id']).any()
 raw_plays['direction']=raw_plays.run_location.fillna('UNKNOWN').astype(str)
 def prior_records(records,cut,window):
  return sorted((r for r in records if pd.notna(r['available'])and pd.Timestamp(r['available'])<cut),key=lambda r:(r['kickoff'],r['game']))[-window:]
 raw_feature_cases=[];raw_boundary_counts=collections.Counter()
 for year,picks in selected.items():
  # Largest earlier carry support among the already frozen deterministic cases;
  # no target result or forecast accuracy enters this selection.
  candidate=max(picks,key=lambda pair:(pair[1]['eligible_player_carries'],sha(enc(list(pair[0])))))
  k,profile=candidate;cut=pd.Timestamp(profile['cutoff_utc']);player=k[3];tm=profile['historical_team']
  own_records=prior_records(ctx.players.get(player,[]),cut,8);team_records=prior_records(ctx.teams.get(tm,[]),cut,8);league_records=prior_records(ctx.league,cut,512)
  own_keys={(r['game'],r['player'])for r in own_records};team_keys={(r['game'],r['team'])for r in team_records}
  league_rb_keys={(p['game'],p['player'])for r in league_records for p in r['players'].values()if p['role']=='RB'}
  pair_plays=list(zip(raw_plays.game_id,raw_plays.rusher_player_id));pair_team=list(zip(raw_plays.game_id,raw_plays.posteam))
  own=raw_plays.loc[[kk in own_keys for kk in pair_plays]];teams=raw_plays.loc[[kk in team_keys for kk in pair_team]];league_rb=raw_plays.loc[[kk in league_rb_keys for kk in pair_plays]]
  directions=['left','middle','right','UNKNOWN'];counts={v:int(own.direction.eq(v).sum())for v in directions};value=max(directions,key=lambda v:(counts[v],v))
  cell=lambda f:f.loc[f.direction.eq(value)]
  sums=[]
  for frame in (own,teams,league_rb):
   rr=cell(frame);assert rr.rushing_yards.notna().all()and np.isfinite(rr.rushing_yards.to_numpy(float)).all();sums.append((len(rr),math.fsum(map(float,rr.rushing_yards))))
  (pn,py),(tn,ty),(ln,ly)=sums
  league_mean=(ly+40.*4.)/(ln+40.);team_mean=(ty+40.*league_mean)/(tn+40.);player_mean=(py+20.*team_mean)/(pn+20.)
  tendency=next(t for t in profile['tendencies']if t['actor']=='own'and t['group']=='direction'and t['value']==value and t['metric']=='yards')
  assert tendency['denominator']==pn and math.isclose(tendency['numerator'],py,abs_tol=1e-12)
  assert (tendency['raw']is None and pn==0)or math.isclose(tendency['raw'],py/pn,rel_tol=1e-12,abs_tol=1e-12)
  assert math.isclose(tendency['shrunk'],player_mean,rel_tol=1e-12,abs_tol=1e-12)
  # Actual signed-play boundary fixtures remain hash commitments in this public
  # aggregate; raw source plays/identities are never copied into the receipt.
  boundary={}
  for sign,test in [('negative',lambda y:y<0),('zero',lambda y:y==0),('positive',lambda y:y>0)]:
   eligible=own.loc[own.rushing_yards.map(test)]
   if len(eligible):
    fixture=min((str(r.game_id),str(r.play_id),str(r.rusher_player_id))for r in eligible.itertuples());boundary[sign]={'state':'SOURCE_PRESENT','case_sha256':sha(enc(list(fixture)))};raw_boundary_counts[sign]+=1
   else:boundary[sign]={'state':'NO_SUPPORTED_SOURCE_CASE_IN_THIS_PRIOR_PANEL'}
  raw_feature_cases.append({'season':year,'profile_case_sha256':sha(enc(list(k))),'direction':value,'admitted_prior_game_membership':'Existing source-qualified manifest, independently availability-filtered and game-time ordered','raw_play_numerator_denominator':'EXACT','nested_league_team_player_shrinkage':'EXACT','equation':'L=(sumLeagueY+40*4)/(nLeague+40);T=(sumTeamY+40*L)/(nTeam+40);P=(sumOwnY+20*T)/(nOwn+20)','source_clock_before_cutoff':all(pd.Timestamp(r['available'])<cut for r in own_records+team_records+league_records),'signed_boundary_cases':boundary,'known_zero_not_inferred_from_missing':True})
 del raw_plays,raw_frames
 def independent_predict(model,q):
  values=[];reasons=[]
  for r in q.itertuples():
   role=str(r.position);prior_model=model.priors.get(role,model.global_prior);reason='';point=hgb.prior_point(prior_model)
   if role not in model.category['modeled_roles']:reason='nonmodeled_role_prior'
   elif model.estimator is None:reason='insufficient_modeled_training_role_prior'
   elif not math.isfinite(float(r.f_player_games_prior))or r.f_player_games_prior<=0:reason='cold_start_role_prior'
   if role not in model.priors:reason='global_prior_unknown_role'
   values.append(point);reasons.append(reason)
  warm=[i for i,x in enumerate(reasons)if x=='']
  if warm:
   with threadpool_limits(limits=1):y=model.estimator.predict(model.design.transform(q.iloc[warm]))
   for i,v in zip(warm,y):values[i]=float(v)
  return np.asarray(values),reasons
 direct_checks=[];model_loads=0
 for year in [2025,2026]:
  name='MODEL_%d_D1_HGB_RAW_CONDITIONAL_PROFILE.joblib'%year;b=read(name);model=joblib.load(io.BytesIO(b));model_loads+=1;assert isinstance(model,hgb.MedianBoostingModel)
  names=model.design.names;expected=data['category']['panels']['base']+core.EFFICIENCY_FEATURES;assert names==expected;assert len(core.EFFICIENCY_FEATURES)==142 and len(core.PROFILE_ONLY_FEATURES)==26;assert not set(core.PROFILE_ONLY_FEATURES).intersection(names)
  assert model.estimator.n_features_in_==2*len(names)+len(model.design.roles);assert len(model.training_binding)==model.audit['modeled_training_rows']==expected_training[year][1];assert len(model.prior_training_binding)==model.audit['supported_played_training_rows']==expected_training[year][0];assert model.estimator.n_iter_==hgb.PARAMETERS['max_iter']
  q=qcases[year];batch,fb=independent_predict(model,q);single=np.asarray([independent_predict(model,q.iloc[[i]])[0][0]for i in range(len(q))]);np.testing.assert_array_equal(batch,single)
  perm=np.arange(len(q))[::-1];shuffled,_=independent_predict(model,q.iloc[perm]);np.testing.assert_array_equal(batch,shuffled[np.argsort(perm)])
  saved={(int(r['season']),int(r['week']),r['game_id'],r['player_id']):r for r in forecasts if r['arm']=='D1_HGB_RAW_CONDITIONAL_PROFILE'and r['season']==year}
  for j,r in enumerate(q.itertuples()):
   k=(int(r.season),int(r.week),str(r.game_id),str(r.player_id));assert float(batch[j])==saved[k]['point'];assert(fb[j]or None)==saved[k]['fallback'];assert pd.Timestamp(saved[k]['source_information_max_utc'])<pd.Timestamp(r.cutoff_utc)
  used_indices={int(n['feature_idx'])for tree in model.estimator._predictors for predictor in tree for n in predictor.nodes if not n['is_leaf']};used_raw={names[i//2]for i in used_indices if i<2*len(names)}
  direct_checks.append(dict(season=year,artifact_sha256=sha(b),cases=len(q),conditional_raw_fields_used_in_tree_splits=len(set(core.EFFICIENCY_FEATURES)&used_raw),numeric_design_fields=len(names),consumed_profile_fields=142,excluded_profile_only_fields=26,transformed_features=int(model.estimator.n_features_in_),modeled_training_rows=len(model.training_binding),supported_training_rows=len(model.prior_training_binding),fitted_iterations=int(model.estimator.n_iter_),fallback_cases=sum(bool(x)for x in fb),ordinary_estimator_cases=sum(not x for x in fb),single_batch_shuffle_saved_points='EXACT',case_commitment_sha256=sha(enc(q[producer.KEY].to_dict('records')))));del model
 # Authenticated own conditional model; only returned state, never a new fit.
 name='MODEL_S1_COMPLETE_RETURNED.joblib';b=read(name);model=joblib.load(io.BytesIO(b));model_loads+=1;assert isinstance(model,core.ConditionalCarryModel)
 audit=model.audit;training_records=[r for records in ctx.players.values()for r in records if r['season']==2024 and r['role']=='RB'and r['attempts']];assert sum(r['attempts']for r in training_records)==audit['credited_rb_carries'];assert sum(len(r['cells'])for r in training_records)==audit['cell_rows'];rbkeys={(r['game'],r['player'])for r in training_records};p24=data['frames'][0];credited=p24.loc[p24.rush_attempt.eq(1)&p24.two_point_attempt.eq(0)];negative_training_carries=sum(float(r.rushing_yards)<0 for r in credited.itertuples()if(str(r.game_id),str(r.rusher_player_id))in rbkeys);assert negative_training_carries>0;assert audit['season']==2024 and int(round(float(model.scaler.n_samples_seen_)))==audit['credited_rb_carries'];assert model.scaler.n_features_in_==model.yards.n_features_in_==model.success.n_features_in_==59
 ridge_n=[int(x)for x in np.atleast_1d(model.yards.n_iter_)];logistic_n=[int(x)for x in np.atleast_1d(model.success.n_iter_)];converged=all(x<model.yards.max_iter for x in ridge_n)and all(x<model.success.max_iter for x in logistic_n);assert np.isfinite(model.yards.coef_).all()and np.isfinite(model.success.coef_).all();assert set(model.success.classes_)=={0,1}
 structured_checks=[];real_moments=0
 for year,q in qcases.items():
  saved={(int(r['season']),int(r['week']),r['game_id'],r['player_id']):r for r in forecasts if r['arm']=='S1_CONDITIONAL_EFFICIENCY_FIXED_N'and r['season']==year}
  for r in q.itertuples():
   key=tuple(getattr(r,k)for k in producer.KEY);fixed=laws[key];law=fixed['law'];expected,mean=independent_moments(law);actual,am=core.carry_bucket_moments(law);np.testing.assert_allclose(actual,expected,rtol=1e-11,atol=1e-10);assert math.isclose(sum(expected),mean,rel_tol=1e-12);real_moments+=1
   f,clock,_=ctx.profile(r.player_id,r.team,r.opponent,r.cutoff_utc,rich=False);mix,_=ctx.mixture(r.player_id,r.team,r.opponent,r.cutoff_utc,1);contexts=[(c,1)for c in sorted(mix)[:4]]
   with threadpool_limits(limits=1):
    yy,pp=model.predict_many(f,contexts);singles=[model.predict(f,c,n)for c,n in contexts];rev_y,rev_p=model.predict_many(f,list(reversed(contexts)));prediction=core.integrated_point(model,ctx,r,law)
   np.testing.assert_allclose(yy,[x[0]for x in singles],rtol=1e-12,atol=1e-12);np.testing.assert_allclose(pp,[x[1]for x in singles],rtol=1e-12,atol=1e-12);np.testing.assert_allclose(yy,rev_y[::-1],rtol=1e-12,atol=1e-12);np.testing.assert_allclose(pp,rev_p[::-1],rtol=1e-12,atol=1e-12)
   sk=(int(r.season),int(r.week),str(r.game_id),str(r.player_id));assert math.isclose(prediction['point'],saved[sk]['point'],rel_tol=1e-12,abs_tol=1e-10);assert pd.Timestamp(saved[sk]['source_information_max_utc'])<pd.Timestamp(r.cutoff_utc)
   structured_checks.append(dict(season=year,case_sha256=sha(enc(list(key))),contexts=len(contexts),clock_before_cutoff=True,point_parity=True,moment_conservation=True))
 r={'id':'PLAYER-CONTEXT-COMPLETION-DECISION-01-A-EFFICIENCY-INDEPENDENT-RUNTIME-REVIEW-v2','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':'PASS_OWN_MODEL_PROFILE_AND_MOMENT_PARITY'if converged else'PARITY_PASS_CONVERGENCE_REQUIRES_REVIEW','execution_receipt_SHA256':a.receipt_sha256,'private_execution_plan_SHA256':sha(planraw),'forecast_freeze_SHA256':sha(frozen),'reviewer_code_SHA256':sha(Path(__file__).read_bytes()),'synthetic_software_only':{'moment_laws_checked':synthetic,'independent_tail_formula':'q**k*(k+q/(1-q)); finitebucket differences plus empirical atoms','maximum_absolute_moment_difference':moment_max,'signed_negative_expected_total_preserved':True,'new_football_accuracy_observations':0},'profiles':{'packet_checks':profile_packet_checks,'selected_raw_profile_exact_reconstructions':profile_exact,'no_target_outcome_case_selection':True,'independent_raw_play_worked_cases':raw_feature_cases,'signed_boundary_source_panels':dict(raw_boundary_counts),'raw_scope':'Raw signed-yard numerator/denominator and three-level shrinkage independently recomputed on existing source-qualified prior-game manifest; no full admission97feature audit repeated'},'direct_model_checks':direct_checks,'conditional_model':{'artifact_SHA256':sha(b),'design_features':59,'training_season':audit['season'],'credited_rb_carries':audit['credited_rb_carries'],'training_cell_rows':audit['cell_rows'],'negative_signed_2024_RB_training_carries':negative_training_carries,'Ridge_iterations':ridge_n,'Ridge_max_iter':model.yards.max_iter,'Logistic_iterations':logistic_n,'Logistic_max_iter':model.success.max_iter,'iteration_limits_not_reached':converged,'real_count_laws_checked':real_moments,'case_checks':structured_checks},'limits':['Only authenticated own returned models were deserialized; no peer models.','Deterministic parity cases cover selected ordinary/sparse2025 and2026W1-7 queries; raw signed-yard numerator/shrinkage checks inherit the accepted game-admission manifest. Prior97feature/timeaudit stands. W8 feature path is not re-audited here.','Moment/signed fixtures are fictional software checks, not NFL evidence. Iteration counters belowcaps show recorded optimizertermination, not an independent mathematical optimalityproof.','No scoring, comparison gains, new forecasts issued, offhost restoration or live qualification claimed.'],'budget':{'CPU_soft_seconds':250,'CPU_hard_seconds':300,'wall_signal_seconds':540,'total_wall_ceiling_seconds':600,'AS_bytes':1610612736,'parent_amendment':'POSTEXEC_CHECK_BUDGET_V1'},'reviewer_activity':{'new_fits':0,'model_loads':model_loads,'verified_own_model_inference_only':True,'private_writes':0,'registry_writes':0,'source_acquisitions':0,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
 a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'state':r['state'],'receipt':str(a.output),'synthetic_laws':synthetic,'real_laws':real_moments,'profile_parity_cases':profile_exact,'model_loads':model_loads,'actual':r['reviewer_activity']},sort_keys=True))
if __name__=='__main__':
 a=cli()
 try:run(a)
 except BaseException as error:
  signal.alarm(0)
  failure={'id':'PLAYER-CONTEXT-COMPLETION-DECISION-01-A-EFFICIENCY-INDEPENDENT-RUNTIME-REVIEW-v2','state':'FAILED_CHECK_NOT_A_FORECAST_REFIT','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error_type':type(error).__name__,'error_sha256':sha(str(error).encode()),'receipt_sha256':a.receipt_sha256,'private_plan_sha256':a.plan_sha256,'reviewer_code_sha256':sha(Path(__file__).read_bytes()),'new_fits':0,'private_writes':0,'automatic_refit':False}
  a.output.with_name(a.output.stem+'-failure.json').write_text(json.dumps(failure,indent=2,sort_keys=True)+'\n')
  raise

