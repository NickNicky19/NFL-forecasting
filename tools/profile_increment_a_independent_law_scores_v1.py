"""Independent frozen-row regrade. No author scorer/common-helper invocation.

Reuses only the immutable *independent reviewer's* previously checked raw-source
reconstruction block, bound by its exact SHA. New laws, choices, scores and
paired arithmetic below are separately calculated from retained evidence.
"""
import argparse,collections,datetime,gzip,hashlib,importlib.util,io,json,lzma,math,os,resource,signal,sys,time,zipfile
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
from pathlib import Path
ROOT=Path('/workspace/nfl-methods-integration')
OLD_CODE_SHA='5164e99c62993a6b2556971bdd61e8d44b05f0686715a1c21c551376e3d4b536'
OLD_NEW=['D0_UNCHANGED_HGB_MAE','D1_HGB_RAW_CONDITIONAL_PROFILE','S0_UNCONDITIONAL_OWN_YPC_FIXED_N','S1_CONDITIONAL_EFFICIENCY_FIXED_N']
CONS=['ALWAYS_OVER','ALWAYS_UNDER'];PREV='EARLIER_RB_ROLE_EXACT_LINE_PREVALENCE_P2'
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def local(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def run(a):
 started,cpu=time.monotonic(),time.process_time();assert a.root_notified_complete=='ROOT_NOTIFIED_NEW_LAW_SCORE_COMPLETE_V1'
 for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
 assert 30<=a.CPU_limit<=200;resource.setrlimit(resource.RLIMIT_CPU,(a.CPU_limit-15,a.CPU_limit));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
 def limit(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('bounded independent new-law score review')
 signal.signal(signal.SIGXCPU,limit);signal.signal(signal.SIGALRM,limit);signal.alarm(540)
 sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
 raw=a.scores.read_bytes();assert sha(raw)==a.scores_sha256;scores=json.loads(gzip.decompress(raw)if a.scores.suffix=='.gz'else raw);assert scores['state']=='FROZEN_POINT_AND_EXACT_LINE_LAW_SCORING_COMPLETE'
 rawplan=a.protocol.read_bytes();assert sha(rawplan)==scores['protocol_sha256'];plan=json.loads(rawplan)
 older=ROOT/'tools/profile_increment_a_independent_scores_v1.py';assert sha(older.read_bytes())==OLD_CODE_SHA;h=local('independent_old_score_math',older)
 import numpy as np,pandas as pd,pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 from tools import category_topfive_matched12_storage_v1 as storage
 outer,_=storage.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=storage.GO,readonly=True);prior=outer.complete_peer.prior_forward
 newdest=prior.forward_root/'research/PROFILE-INCREMENT-TO-RELEASE-01-A-v2';olddest=prior.forward_root/'research/PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1'
 def read(ref,new=True):
  p=(newdest if new else olddest)/ref['id'];prior.validate_reference(p,ref['sha256']);b=p.read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
 view=json.loads(lzma.decompress(read(scores['private_scorecard_view'])));assert view['protocol_sha256']==scores['protocol_sha256'];assert view['execution_receipt_sha256']==scores['execution_receipt_sha256']and view['old_execution_receipt_sha256']==scores['old_execution_receipt_sha256']
 refs=view['source_refs'];assert{k:r['sha256']for k,r in refs.items()}==scores['source_sha256']
 def source(name):
  r=refs[name];b=Path(r['path']).read_bytes();assert len(b)==r['bytes']and sha(b)==r['sha256'];return b
 newrows=json.loads(gzip.decompress(read(view['frozen_forecasts'])));newmap={(r['arm'],h.key(r)):r for r in newrows};assert len(newmap)==len(newrows)
 oldrows=json.loads(gzip.decompress(read(view['old_frozen_forecasts'],False)));oldmap={(r['arm'],h.key(r)):r for r in oldrows if r['season']==2026}
 cohorts={h.key(r):r for r in json.loads(gzip.decompress(read(view['cohort_reference'])))};qprofile=pd.read_parquet(io.BytesIO(read(view['query_profile_input_reference'])));support={h.key(r):bool(r['f_pce_own_supported']>0)for r in qprofile.to_dict('records')}
 cand=scores['candidate_ids'];newcand=[c for c in cand if '::'in c];saved=[c for c in cand if c.startswith('SAVED_')];arms=sorted({c.split('::')[0]for c in newcand});assert len(newcand)==12 and len(saved)==7 and len(cand)==26
 # Reuse exact already-reviewed independent RAW reconstruction only, excluding
 # its old candidate scoring. It reconstructs metric presence and source IDs.
 code=older.read_text();prefix=code[code.index(' def zipped_frame(name):'):code.index(' broad={c:[]for c in cand}')]
 prefix=prefix.replace("assert len(queries)==2289 and unmapped==2","assert len(queries)==expected_query_count and unmapped==2")
 env=dict(vars(h));env.update(pd=pd,np=np,io=io,zipfile=zipfile,json=json,gzip=gzip,csv=__import__('csv'),refs=refs,source=source,saved=saved,fm=oldmap,NEW=OLD_NEW,view=dict(view,query_references=[view['query_reference']]),native=lambda r:read(r,False),scores=scores,a=a,expected_query_count=len(cohorts)+2)
 exec(compile('def restore():\n'+prefix+'\n return queries,label,spec,unmapped,excl\n','<pinned-independent-raw-reconstruction>','exec'),env)
 queries,labels,spec,unmapped,excluded=env['restore']();assert len(spec)==len({s[2]for s in spec})
 histories=[];seen=set()
 for name in sorted(n for n in refs if n.startswith('history_')):
  f=pd.read_parquet(io.BytesIO(source(name)));assert f.outcome_available_utc.notna().all()
  for r in f.loc[f.position.eq('RB')&f.participation_state.eq('played')&f.stats_observed.eq(True)].to_dict('records'):
   k=h.key(r);assert k not in seen;seen.add(k);clock=pd.Timestamp(r['outcome_available_utc']);assert clock.tzinfo is not None
   if h.finite(r.get('rush_yd')):histories.append((clock,str(r['game_id']),float(r['rush_yd'])))
 def lawprobs(law,line):
  assert law['kind']=='leaf_cdf'and law['prior']['support']=='signed_integer';d=Decimal(str(line));fl=int(d.to_integral_value(rounding=ROUND_FLOOR));lo=int(d.to_integral_value(rounding=ROUND_CEILING))-1;b=law['prior_weight'];q=law['prior']['q'];center=law['prior']['center']
  def C(k):
   p=q**(center-k)/(1+q)if k<center else 1-q**(k-center+1)/(1+q)
   return(1-b)*math.fsum(w for y,w in zip(law['support'],law['weights'])if y<=k)+b*p
  u,o=C(lo),1-C(fl);p=C(fl)-C(fl-1)if d==fl else 0.;assert min(u,o,p)>-1e-12 and math.isclose(u+o+p,1.,abs_tol=1e-10);return(u,p,o)
 def resolve(c,q,line=None):
  k=h.key(q)
  if q.get('identity_reason')is not None:return None,None,q['identity_reason'],'UNAVAILABLE_FORECAST'
  if c in CONS:return None,None,None,'CONSTANT_NOT_NUMERICAL'
  if c==PREV:
   if line is None:return None,None,'PREVALENCE_HAS_NO_NUMERICAL_POINT','NOT_NUMERICAL'
   cut=pd.Timestamp(q.get('cutoff_utc'));prev=[y for clock,game,y in histories if cut is not pd.NaT and clock<cut and game!=q['game_id']]
   if not prev:return None,None,'NO_ELIGIBLE_EARLIER_ROLE_LABELS','UNAVAILABLE_REFERENCE'
   n=len(prev);integer=Decimal(str(line))%1==0;den=n+(3 if integer else 2);p=((sum(y<line for y in prev)+1)/den,(sum(y==line for y in prev)+1)/den if integer else 0.,(sum(y>line for y in prev)+1)/den);return None,p,None,'EARLIER_ROLE_PREVALENCE_NOT_LEARNED_MODEL'
  if c in newcand:
   arm,prod=c.split('::');f=newmap.get((arm,k));why=h.compatible(f,q,pd)
   if why:return None,None,why,'UNAVAILABLE_FORECAST'
   point=f['mean']if prod=='MEAN_P1'else f['median']if prod=='MEDIAN_P1'else None;return point,lawprobs(f['law'],line)if line is not None else None,None,h.fb(f)
  f=oldmap.get((c,k));why=h.compatible(f,q,pd);return(f.get('point')if why is None else None),None,why,h.fb(f)if f else'UNAVAILABLE_FORECAST'
 def cohort(k):return['ALL_ELIGIBLE']+(['DETAILED_PRIORITY']if cohorts.get(k,{}).get('detailed_priority')else[])+(['WORKLOAD_TOP20']if cohorts.get(k,{}).get('top20_workload')else[])+(['PBP_OWN_SUPPORTED']if support.get(k)else[])
 board={c:[]for c in cand};broad={c:[]for c in cand};membership=[]
 for k,q in queries.items():
  y,p=labels.get(k,(None,'UNKNOWN'))
  for c in cand:
   point,_,why,fb=resolve(c,q);broad[c].append(dict(season=k[0],week=k[1],game_id=k[2],player_id=k[3],opportunity_key=sha(enc(list(k))),point=point,actual=y,appearance=p,unavailability_reason=why,fallback_state=fb,cohorts=cohort(k)))
 for q,line,op,(y,p),source_name,tier in spec:
  k=h.key(q)
  for c in cand:
   point,probs,why,fb=resolve(c,q,line);selected=c.removeprefix('ALWAYS_')if c in CONS else('OVER'if probs[2]>probs[0]else'UNDER'if probs[0]>probs[2]else'ABSTAIN')if c.endswith('P2')and probs is not None else None if c.endswith('P2')else h.side(point,line);status=h.grade(line,selected,y,p);u,push,o=probs if probs is not None else(None,None,None)
   r=dict(season=k[0],week=k[1],game_id=k[2],player_id=k[3],opportunity_key=op,point=point,actual=y,appearance=p,unavailability_reason=why,fallback_state=fb,cohorts=cohort(k),selected_side=selected,status=status,line=line,source_panel=source_name,evidence_tier=tier,p_under=u,p_push=push,p_over=o);board[c].append(r);membership.append([c,op,point,u,push,o,selected,status,why,fb])
 core=set.intersection(*[{r['opportunity_key']for r in board[c]if r['selected_side']is not None}for c in newcand]);coreb=set.intersection(*[{r['opportunity_key']for r in broad[c]if h.finite(r['point'])}for c in newcand if not c.endswith('P2')]);assert sha(enc(sorted(core)))==scores['common_new_core_mask_sha256']==view['common_new_core_mask_sha256'];assert sha(enc(sorted(membership)))==view['complete_decision_membership_sha256']
 for records,pool in [(board,core),(broad,coreb)]:
  for rows in records.values():
   for r in rows:
    if r['opportunity_key']in pool:r['cohorts'].append('STABLE_NEW_CORE')
 def num(c,rr):return dict(state='N/A_NO_NUMERICAL_POINT_PRODUCT',intended=len(rr),scored=0,MAE=None,MSE=None,RMSE=None,bias=None)if c in CONS or c.endswith('P2')else h.numeric(rr)
 def probability(rr):
  qualified=[r for r in rr if r['p_over']is not None and r['appearance']=='PLAYED'and r['actual']is not None];binary=[];multi=[];logs=[];inf=0
  for r in qualified:
   y,line=r['actual'],r['line'];t=[int(y<line),int(y==line),int(y>line)];p=[r['p_under'],r['p_push'],r['p_over']];binary.append((p[2]-t[2])**2);multi.append(math.fsum((x-z)**2 for x,z in zip(p,t)));assigned=p[t.index(1)]
   if assigned<=0:inf+=1
   else:logs.append(-math.log(assigned))
  return dict(qualified_law_outcomes=len(qualified),decisive_law_outcomes=sum(r['actual']!=r['line']for r in qualified),binary_Over_event_Brier=math.fsum(binary)/len(binary)if binary else None,three_class_Brier_sum=math.fsum(multi)/len(multi)if multi else None,three_class_log_loss=math.fsum(logs)/len(logs)if logs and not inf else None,infinite_log_loss_cases=inf,finite_three_class_log_loss_mean=math.fsum(logs)/len(logs)if logs else None)
 periods={'W1_W7':range(1,8),'W8_REFERENCE_ONLY':[8],'W1_W8_PARTIAL_ACTUAL':range(1,9)};summary_n=0
 for s in scores['summaries']:
  c=s['candidate_id'];rows=broad[c]if s['population']=='BROAD_QUERIES'else board[c];rr=[r for r in rows if r['week']in periods[s['period']]and s['cohort']in r['cohorts']]
  if s['population']=='RETAINED_THRESHOLD_BOARD':
   rr=[r for r in rr if(s['source_panel']=='ALL'or r['source_panel']==s['source_panel'])and(s['week_view']=='ALL'or r['week']==s['week_view'])]
   for k,v in h.summary(rr).items():h.close(v,s[k],k)
   aw=sorted({r['week']for r in rr if r['status']in['WIN','LOSS','PUSH']and r['evidence_tier']=='ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED'});assert aw==s['actual_recorded_line_scored_weeks']and s['five_actual_week_duration_floor']==(len(aw)>=5)
   for k,v in probability(rr).items():h.close(v,s['probability'][k],'probability/'+k)
  h.close(num(c,rr),s['numerical'],'numerical');summary_n+=1
 def interval(pp,fn):
  gs=collections.defaultdict(list);ws=collections.defaultdict(list)
  for l,r in pp:gs[l['game_id']].append(fn(l,r));ws[(l['season'],l['week'])].append(fn(l,r))
  def boot(group):
   if len(group)<2:return None
   values=[group[k]for k in sorted(group)];nums=np.array([math.fsum(v)for v in values]);dens=np.array([len(v)for v in values]);ix=np.random.default_rng(20261110).integers(0,len(values),(500,len(values)));sim=nums[ix].sum(axis=1)/dens[ix].sum(axis=1);return list(map(float,np.quantile(sim,[.025,.975])))
  return dict(game_clusters=len(gs),week_clusters=len(ws),game_interval95=boot(gs),week_interval95=boot(ws))
 pair_n=0
 for s in scores['paired']:
  def take(c):return[r for r in board[c]if r['week']in periods[s['period']]and s['cohort']in r['cohorts']and(s['source_panel']=='ALL'or r['source_panel']==s['source_panel'])]
  left,right=take(s['left']),take(s['right']);rm={r['opportunity_key']:r for r in right};pp=[(l,rm[l['opportunity_key']])for l in left if l['opportunity_key']in rm];dd=[(l,r)for l,r in pp if l['status']in['WIN','LOSS']and r['status']in['WIN','LOSS']];nn=[(l,r)for l,r in pp if h.finite(l['point'])and h.finite(r['point'])and l['actual']is not None and r['actual']is not None];pw=[(l,r)for l,r in pp if l['p_over']is not None and r['p_over']is not None and l['appearance']=='PLAYED'and l['actual']is not None]
  diff=lambda l,r:int(l['status']=='WIN')-int(r['status']=='WIN');err=lambda l,r:abs(l['point']-l['actual'])-abs(r['point']-r['actual']);brier=lambda l,r:(l['p_over']-int(l['actual']>l['line']))**2-(r['p_over']-int(r['actual']>r['line']))**2
  mine=dict(common_decided=len(dd),left_wins=sum(l['status']=='WIN'for l,r in dd),right_wins=sum(r['status']=='WIN'for l,r in dd),accuracy_change=math.fsum(diff(l,r)for l,r in dd)/len(dd)if dd else None,side_disagreements=sum(l['selected_side']!=r['selected_side']for l,r in dd),decision_uncertainty=interval(dd,diff),common_numerical=len(nn),MAE_change=math.fsum(err(l,r)for l,r in nn)/len(nn)if nn else None,MAE_change_uncertainty=interval(nn,err),decided_mask_sha256=sha(enc(sorted(l['opportunity_key']for l,r in dd))),numerical_mask_sha256=sha(enc(sorted(l['opportunity_key']for l,r in nn))))
  for k,v in mine.items():h.close(v,s[k],'paired/'+k)
  uncertainty=interval(pw,brier);pm=dict(common_probability_events=len(pw),binary_Over_event_Brier_change=math.fsum(brier(l,r)for l,r in pw)/len(pw)if pw else None,game_interval95=uncertainty['game_interval95'],week_interval95=uncertainty['week_interval95'])
  for k,v in pm.items():h.close(v,s['probability'][k],'paired_probability/'+k)
  pair_n+=1
 result={'id':'PROFILE-INCREMENT-A-INDEPENDENT-LAW-SCORE-v1','state':'PASS_INDEPENDENT_NEW_LAW_ROWS_SIDES_COUNTS_PROBABILITY_PAIRS_AND_MASKS','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'score_sha256':a.scores_sha256,'code_sha256':sha(Path(__file__).read_bytes()),'reused_independent_raw_source_code_sha256':OLD_CODE_SHA,'summary_cells':summary_n,'paired_cells':pair_n,'candidate_views':len(cand),'board_opportunities':len(spec),'query_rows':len(queries),'W8_unmapped':unmapped,'W8_exclusions':dict(excluded),'membership_sha256':sha(enc(sorted(membership))),'discrepancies':0,'limits':['Accepted source contracts/current-vintage availability remain inherited; actual source vintage not created by regrade.','Common whole-week summary intervals are not repeated; all paired game/week500 intervals independently recomputed.','No model inference, fit reproduction, current-query packet, selection upgrade or deployment inferred.'],'resources':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'activity':{'fits':0,'model_loads':0,'inference':0,'private_writes':0,'source_HTTP':0}}
 a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');signal.alarm(0);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root-notified-complete',required=True);p.add_argument('--scores',type=Path,required=True);p.add_argument('--scores-sha256',required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--CPU-limit',dest='CPU_limit',type=int,default=150);p.add_argument('--output',type=Path,default=Path('/tmp/profile-increment-independent-law-score-review-v1.json'));a=p.parse_args()
 try:run(a)
 except BaseException as e:
  signal.alarm(0);r={'state':'FAILED_INDEPENDENT_LAW_SCORE_NO_REFIT','error_type':type(e).__name__,'error_sha256':sha(str(e).encode()),'code_sha256':sha(Path(__file__).read_bytes()),'score_sha256':a.scores_sha256,'fits':0,'private_writes':0};a.output.with_name(a.output.stem+'-failure.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');raise
