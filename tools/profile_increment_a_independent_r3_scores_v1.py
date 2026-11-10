"""Independent frozen-row regrade. No author scorer/common-helper invocation.

Reuses only the immutable *independent reviewer's* previously checked raw-source
reconstruction block, bound by its exact SHA. New laws, choices, scores and
paired arithmetic below are separately calculated from retained evidence.
"""
import argparse,collections,datetime,gzip,hashlib,importlib.util,io,json,lzma,math,os,resource,signal,sys,time,zipfile
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD_CODE_SHA='5164e99c62993a6b2556971bdd61e8d44b05f0686715a1c21c551376e3d4b536'
OLD_NEW=['D0_UNCHANGED_HGB_MAE','D1_HGB_RAW_CONDITIONAL_PROFILE','S0_UNCONDITIONAL_OWN_YPC_FIXED_N','S1_CONDITIONAL_EFFICIENCY_FIXED_N']
CONS=['ALWAYS_OVER','ALWAYS_UNDER'];PREV='EARLIER_RB_ROLE_EXACT_LINE_PREVALENCE_P2'
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def local(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def provenance(row):
 state=row.get('fallback_state','UNRECORDED')
 if not isinstance(state,str):return'UNRECORDED'
 if state=='LEARNED_EXPLICIT_NO_FALLBACK':return'RECORDED_LEARNED'
 if state.startswith('FALLBACK:'):return'RECORDED_FALLBACK'
 if state in ['UNAVAILABLE_FORECAST','UNAVAILABLE_CANONICAL_IDENTITY','UNAVAILABLE_REFERENCE','OUTSIDE_SOURCE_SCOPE']:return'UNAVAILABLE'
 if state in ['CONSTANT_NOT_NUMERICAL','EARLIER_ROLE_PREVALENCE_NOT_LEARNED_MODEL','NOT_NUMERICAL']:return'REFERENCE'
 return'UNRECORDED'
def fixed_coverage_audit(board,broad,candidates,periods,h,np,interval,num):
 """Attribution only; does not select/filter a forecasting policy."""
 classes=['RECORDED_LEARNED','RECORDED_FALLBACK','UNRECORDED','UNAVAILABLE','REFERENCE']
 summaries=[];broad_summaries=[];pairs=[]
 def summary(rows):
  result=h.summary(rows);result['provenance_counts']={g:sum(provenance(r)==g for r in rows)for g in classes};assert sum(result['provenance_counts'].values())==len(rows)
  result['recorded_fallback_reasons']=dict(collections.Counter(r['fallback_state']for r in rows if provenance(r)=='RECORDED_FALLBACK'))
  result['PBP_support_cross_tab']=[dict(provenance=g,PBP_OWN_SUPPORTED=bool(s),eligible=sum(provenance(r)==g and('PBP_OWN_SUPPORTED'in r['cohorts'])==s for r in rows))for g in classes for s in [False,True]]
  return result
 def impact(pp):
  decided=[(l,r)for l,r in pp if l['status']in['WIN','LOSS']and r['status']in['WIN','LOSS']];numeric=[(l,r)for l,r in pp if h.finite(l['point'])and h.finite(r['point'])and l['actual']is not None and r['actual']is not None]
  delta=lambda l,r:int(l['status']=='WIN')-int(r['status']=='WIN');w1=sum(l['status']=='WIN'for l,r in decided);w2=sum(r['status']=='WIN'for l,r in decided)
  output_changed=lambda l,r:((h.finite(l['point'])and h.finite(r['point'])and l['point']!=r['point'])or(l['p_over']is not None and r['p_over']is not None and any(l[k]!=r[k]for k in ['p_under','p_push','p_over'])))
  return dict(common_eligible=len(pp),left_own=summary([l for l,r in pp]),right_own=summary([r for l,r in pp]),common_decided=len(decided),left_wins=w1,right_wins=w2,paired_net_wins=w1-w2,accuracy_change=(w1-w2)/len(decided)if decided else None,decision_uncertainty=interval(decided,delta),common_numerical=len(numeric),MAE_change=math.fsum(abs(l['point']-l['actual'])-abs(r['point']-r['actual'])for l,r in numeric)/len(numeric)if numeric else None,left_only_decided=sum(l['status']in['WIN','LOSS']and r['status']not in['WIN','LOSS']for l,r in pp),right_only_decided=sum(r['status']in['WIN','LOSS']and l['status']not in['WIN','LOSS']for l,r in pp),learned_gate_changes=sum((provenance(l)=='RECORDED_LEARNED')!=(provenance(r)=='RECORDED_LEARNED')for l,r in pp),fallback_gate_changes=sum((provenance(l)=='RECORDED_FALLBACK')!=(provenance(r)=='RECORDED_FALLBACK')for l,r in pp),fallback_reason_changes=sum(l['fallback_state']!=r['fallback_state']for l,r in pp),both_fallback_output_changes=sum(output_changed(l,r)for l,r in pp if provenance(l)==provenance(r)=='RECORDED_FALLBACK'),both_fallback_side_changes=sum(l['selected_side']!=r['selected_side']for l,r in pp if provenance(l)==provenance(r)=='RECORDED_FALLBACK'),common_eligible_mask_sha256=sha(enc(sorted(l['opportunity_key']for l,r in pp))),common_decided_mask_sha256=sha(enc(sorted(l['opportunity_key']for l,r in decided))))
 arms=['RB_ONLY_LEAF_BASE','R1_RB_ONLY_LEAF_SUPPORT','R2_RB_ONLY_LEAF_PLAYER_OFFENSE','R3_RB_ONLY_LEAF_DEFENSE']
 for period,weeks in periods.items():
  panels=['ALL']+sorted({r['source_panel']for rows in board.values()for r in rows if r['week']in weeks})
  for c in candidates:
   full=[r for r in broad[c]if r['week']in weeks];broad_summaries.append(dict(period=period,candidate_id=c,provenance_counts={g:sum(provenance(r)==g for r in full)for g in classes},full_system_numerical=num(c,full),group_numerical={g:num(c,[r for r in full if provenance(r)==g])for g in classes if any(provenance(r)==g for r in full)}))
   for panel in panels:
    full=[r for r in board[c]if r['week']in weeks and(panel=='ALL'or r['source_panel']==panel)]
    summaries.append(dict(period=period,source_panel=panel,candidate_id=c,full_system=summary(full),own_side_groups={g:summary([r for r in full if provenance(r)==g])for g in classes if any(provenance(r)==g for r in full)}))
  for product in ['MEAN_P1','MEDIAN_P1','EXACT_LINE_P2']:
   for left,right in [(arms[3]+'::'+product,arms[2]+'::'+product)]:
    for panel in panels:
     aa=[r for r in board[left]if r['week']in weeks and(panel=='ALL'or r['source_panel']==panel)];bb={r['opportunity_key']:r for r in board[right]if r['week']in weeks and(panel=='ALL'or r['source_panel']==panel)};pp=[(l,bb[l['opportunity_key']])for l in aa if l['opportunity_key']in bb];full=impact(pp);ll=[(l,r)for l,r in pp if provenance(l)==provenance(r)=='RECORDED_LEARNED'];groups=collections.defaultdict(list)
     for l,r in pp:groups[provenance(l)+'->'+provenance(r)].append((l,r))
     transitions={name:impact(rows)for name,rows in sorted(groups.items())};assert sum(v['paired_net_wins']for v in transitions.values())==full['paired_net_wins']and sum(v['common_decided']for v in transitions.values())==full['common_decided']
     observed=all(any(provenance(r)in['RECORDED_LEARNED','RECORDED_FALLBACK']for r in rows)for rows in [aa,list(bb.values())])
     pairs.append(dict(period=period,source_panel=panel,left=left,right=right,comparison_state='RECORDED_MODEL_OUTPUTS_CHECKED'if observed else'UNAVAILABLE_PROCEDURE_COVERAGE_ONLY_NOT_A_LEARNED_GATE_OR_SKILL_TEST',full_system=full,recorded_learned_learned=impact(ll),provenance_transitions=transitions,paired_gain_reconciles_as_sum_of_disjoint_win_counts=True))
 return dict(id='FIXED_EXECUTION_PROVENANCE_ATTRIBUTION_v1',scope='Same full eligible boards and immutable decisions; coverage attribution only, never a new selector, primary recommendation or filtered qualification. PBP_OWN_SUPPORTED is a separate input-support cross-tab, not learned-only.',group_definitions={'RECORDED_LEARNED':'Explicit retained no-fallback marker; no inference from PBP support or successful outcomes.','RECORDED_FALLBACK':'Explicit recorded fallback reason.','UNRECORDED':'No qualified explicit learned/fallback provenance; never silently called learned.','UNAVAILABLE':'Recorded technical/source/identity unavailability.','REFERENCE':'Declared constant-side or earlier-role statistical control.'},own_side_records=summaries,broad_numerical_records=broad_summaries,paired_attribution_records=pairs,rate_warning='Own/paired/subgroup rates retain their own denominators. Only disjoint paired win-count changes are summed; percentages are not summed or averaged.',new_NFL_observations=0,new_selection_policies=0)
def run(a):
 started,cpu=time.monotonic(),time.process_time();assert a.root_notified_complete=='ROOT_NOTIFIED_FULL_FOUR_SCORE_COMPLETE_V1'
 for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
 assert 30<=a.CPU_limit<=120;resource.setrlimit(resource.RLIMIT_CPU,(a.CPU_limit-15,a.CPU_limit));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
 def limit(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('bounded independent new-law score review')
 signal.signal(signal.SIGXCPU,limit);signal.signal(signal.SIGALRM,limit);signal.alarm(540)
 sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
 raw=a.scores.read_bytes();assert sha(raw)==a.scores_sha256;scores=json.loads(gzip.decompress(raw)if a.scores.suffix=='.gz'else raw);assert scores['state']in['FROZEN_POINT_AND_EXACT_LINE_LAW_SCORING_COMPLETE','FROZEN_NAMED_THREE_ARMS_SCORING_COMPLETE_DEFENSE_PENDING']
 rawplan=a.protocol.read_bytes();assert sha(rawplan)==scores['protocol_sha256'];plan=json.loads(rawplan);assert scores['candidate_ids']==plan['candidate_ids'];er=plan['execution_receipt'];eraw=Path(er['path']).read_bytes();assert len(eraw)==er['bytes']and sha(eraw)==er['sha256']==scores['execution_receipt_sha256'];execution=json.loads(eraw);partial=execution['state']=='FROZEN_NAMED_THREE_ARMS_DEFENSE_PENDING';assert execution['state']in['FROZEN_FORECASTS_COMPLETE_UNSCORED','FROZEN_NAMED_THREE_ARMS_DEFENSE_PENDING']
 assert scores['state']==('FROZEN_NAMED_THREE_ARMS_SCORING_COMPLETE_DEFENSE_PENDING'if partial else'FROZEN_POINT_AND_EXACT_LINE_LAW_SCORING_COMPLETE')
 assert not partial and execution['new_fits_this_supplement']==1 and execution['reused_models_without_refit_or_inference']==3
 pr=a.previous_scores.read_bytes();assert sha(pr)==a.previous_scores_sha256;prior_scores=json.loads(gzip.decompress(pr));pp=a.previous_review.read_bytes();assert sha(pp)==a.previous_review_sha256;prior_review=json.loads(pp);assert prior_review['state']=='PASS_NAMED_THREE_ARM_SCORES_DEFENSE_RESOURCE_PENDING'and prior_review['score_sha256']==a.previous_scores_sha256 and prior_review['discrepancies']==0
 assert prior_scores['source_sha256']==scores['source_sha256']and prior_scores['candidate_ids']==scores['candidate_ids']and prior_scores['common_new_core_mask_sha256']==scores['common_new_core_mask_sha256']
 R3='R3_RB_ONLY_LEAF_DEFENSE::'
 def isnew(r):return r.get('candidate_id','').startswith(R3)or any(r.get(k,'').startswith(R3)for k in['left','right'])
 def sk(r):return tuple(str(r.get(k))for k in['period','cohort','candidate_id','population','source_panel','week_view'])
 def pk(r):return tuple(str(r.get(k))for k in['period','cohort','source_panel','left','right'])
 sm={sk(r):r for r in scores['summaries']};pm={pk(r):r for r in scores['paired']};reused_s=reused_p=0
 for r in prior_scores['summaries']:
  if not isnew(r):assert enc(r)==enc(sm[sk(r)]);reused_s+=1
 for r in prior_scores['paired']:
  if not isnew(r):assert enc(r)==enc(pm[pk(r)]);reused_p+=1
 assert scores['prior_partial_parity']['state']=='PASS_UNCHANGED_COMPARABLE_OLD_CELLS'and scores['prior_partial_parity']['mismatch_count']==0

 older=ROOT/'tools/profile_increment_a_independent_scores_v1.py';assert sha(older.read_bytes())==OLD_CODE_SHA;h=local('independent_old_score_math',older)
 import numpy as np,pandas as pd,pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 from tools import category_topfive_matched12_storage_v1 as storage
 outer,_=storage.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=storage.GO,readonly=True);prior=outer.complete_peer.prior_forward
 newdest=prior.forward_root/'research/PROFILE-INCREMENT-TO-RELEASE-01-A-v2';childdest=prior.forward_root/'research/PROFILE-INCREMENT-TO-RELEASE-01-A-v2-def-remainder-v1';olddest=prior.forward_root/'research/PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1'
 def read(ref,new=True):
  namespace=ref.get('namespace','PRIMARY');assert namespace in['PRIMARY','DEF_REMAINDER'];p=((newdest if namespace=='PRIMARY'else childdest)if new else olddest)/ref['id'];prior.validate_reference(p,ref['sha256']);b=p.read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
 view=json.loads(lzma.decompress(read(scores['private_scorecard_view'])));assert view['protocol_sha256']==scores['protocol_sha256'];assert view['execution_receipt_sha256']==scores['execution_receipt_sha256']and view['old_execution_receipt_sha256']==scores['old_execution_receipt_sha256']
 refs=view['source_refs'];assert{k:r['sha256']for k,r in refs.items()}==scores['source_sha256']
 def source(name):
  r=refs[name];b=Path(r['path']).read_bytes();assert len(b)==r['bytes']and sha(b)==r['sha256'];return b
 manifest=json.loads(gzip.decompress(read(view['frozen_forecasts'])));expected_arm_order=list(dict.fromkeys(c.split('::')[0]for c in scores['candidate_ids']if '::'in c));active_arms=expected_arm_order[:3]if partial else expected_arm_order;assert manifest['format']=='IMMUTABLE_ORDERED_PART_MANIFEST_V1'and len(manifest['parts'])==len(manifest['arm_order'])==len(active_arms)and manifest['arm_order']==active_arms
 newrows=[]
 for arm,part in zip(manifest['arm_order'],manifest['parts']):
  assert part['arm']==arm;rows=json.loads(gzip.decompress(read(part)));assert len(rows)==part['rows']and all(r['arm']==arm for r in rows);newrows.extend(rows)
 assert len(newrows)==manifest['rows']and sha(enc(newrows))==manifest['logical_combined_sha256'];newmap={(r['arm'],h.key(r)):r for r in newrows};assert len(newmap)==len(newrows)
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
  if c in newcand and c.split('::')[0]not in active_arms:return None,None,'RESOURCE_PENDING','UNAVAILABLE_FORECAST'
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
 core_candidates=[c for c in newcand if c.split('::')[0]in active_arms];core=set.intersection(*[{r['opportunity_key']for r in board[c]if r['selected_side']is not None}for c in core_candidates]);coreb=set.intersection(*[{r['opportunity_key']for r in broad[c]if h.finite(r['point'])}for c in core_candidates if not c.endswith('P2')]);assert sha(enc(sorted(core)))==scores['common_new_core_mask_sha256']==view['common_new_core_mask_sha256'];assert sha(enc(sorted(membership)))==view['complete_decision_membership_sha256']
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
  if not isnew(s):continue
  c=s['candidate_id'];rows=broad[c]if s['population']=='BROAD_QUERIES'else board[c];rr=[r for r in rows if r['week']in periods[s['period']]and s['cohort']in r['cohorts']]
  assert s['execution_state']==('RESOURCE_PENDING'if c in newcand and c.split('::')[0]not in active_arms else'FROZEN_OR_CONTROL')
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
  if not isnew(s):continue
  assert s['execution_state']==('RESOURCE_PENDING'if any(c in newcand and c.split('::')[0]not in active_arms for c in [s['left'],s['right']])else'SCORING_EXECUTED')
  def take(c):return[r for r in board[c]if r['week']in periods[s['period']]and s['cohort']in r['cohorts']and(s['source_panel']=='ALL'or r['source_panel']==s['source_panel'])]
  left,right=take(s['left']),take(s['right']);rm={r['opportunity_key']:r for r in right};pp=[(l,rm[l['opportunity_key']])for l in left if l['opportunity_key']in rm];dd=[(l,r)for l,r in pp if l['status']in['WIN','LOSS']and r['status']in['WIN','LOSS']];nn=[(l,r)for l,r in pp if h.finite(l['point'])and h.finite(r['point'])and l['actual']is not None and r['actual']is not None];pw=[(l,r)for l,r in pp if l['p_over']is not None and r['p_over']is not None and l['appearance']=='PLAYED'and l['actual']is not None]
  diff=lambda l,r:int(l['status']=='WIN')-int(r['status']=='WIN');err=lambda l,r:abs(l['point']-l['actual'])-abs(r['point']-r['actual']);brier=lambda l,r:(l['p_over']-int(l['actual']>l['line']))**2-(r['p_over']-int(r['actual']>r['line']))**2
  mine=dict(common_decided=len(dd),left_wins=sum(l['status']=='WIN'for l,r in dd),right_wins=sum(r['status']=='WIN'for l,r in dd),accuracy_change=math.fsum(diff(l,r)for l,r in dd)/len(dd)if dd else None,side_disagreements=sum(l['selected_side']!=r['selected_side']for l,r in dd),decision_uncertainty=interval(dd,diff),common_numerical=len(nn),MAE_change=math.fsum(err(l,r)for l,r in nn)/len(nn)if nn else None,MAE_change_uncertainty=interval(nn,err),decided_mask_sha256=sha(enc(sorted(l['opportunity_key']for l,r in dd))),numerical_mask_sha256=sha(enc(sorted(l['opportunity_key']for l,r in nn))))
  for k,v in mine.items():h.close(v,s[k],'paired/'+k)
  uncertainty=interval(pw,brier);pm=dict(common_probability_events=len(pw),binary_Over_event_Brier_change=math.fsum(brier(l,r)for l,r in pw)/len(pw)if pw else None,game_interval95=uncertainty['game_interval95'],week_interval95=uncertainty['week_interval95'])
  for k,v in pm.items():h.close(v,s['probability'][k],'paired_probability/'+k)
  pair_n+=1
 coverage=fixed_coverage_audit(board,broad,[c for c in cand if c.startswith(R3)],periods,h,np,interval,num)
 # Independently check the additive descriptive player card from the same
 # reconstructed rows; no author diagnostic function or new model is called.
 player=scores.get('per_player_diagnostics');player_checked=0;player_pairs_checked=0
 if player is not None:
  assert player['state']=='RETAINED_PROTECTED_CARD_AND_PUBLIC_AGGREGATES'and player['public_player_ids_or_rows']is False
  card=json.loads(gzip.decompress(read(player['private_scorecard'])));columns=card['columns'];private={tuple(row[:3]):dict(zip(columns,row))for row in card['rows']};assert len(private)==len(card['rows'])
  players=sorted({r['player_id']for rows in broad.values()for r in rows}|{r['player_id']for rows in board.values()for r in rows});assert player['global_player_count']==len(players)and player['protected_record_count']==len(private)==len(players)*len(cand)*5
  panels=[('W1_W7_MIXED_THRESHOLDS',False,lambda r:r['week']in range(1,8)),('ANNUAL_W1_W5',False,lambda r:r['week']in range(1,6)and r['source_panel']=='ANNUAL_NAMED_NJ'),('W8_REFERENCE_ONLY',False,lambda r:r['week']==8),('BROAD_NUMERICAL_W1_W7',True,lambda r:r['week']in range(1,8)),('BROAD_NUMERICAL_W8',True,lambda r:r['week']==8)]
  public={(r['panel'],r['candidate_id']):r for r in player['summary']};publicpair={(r['panel'],r['left'],r['right']):r for r in player['paired_player_counts']};assert len(public)==26*5 and len(publicpair)==99*5
  def ss(rr):
   o={}
   for side in['OVER','UNDER','COMBINED']:
    rows=[r for r in rr if r['selected_side']in['OVER','UNDER']]if side=='COMBINED'else[r for r in rr if r['selected_side']==side];w=sum(r['status']=='WIN'for r in rows);l=sum(r['status']=='LOSS'for r in rows);o[side]=dict(selected=len(rows),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l)if w+l else None)
   return o
  def supportbin(n):return'0'if n==0 else'1'if n==1 else'2'if n==2 else'3-4'if n<=4 else'5-7'if n<=7 else'8+'
  for panel,isb,pred in panels:
   grouped={}
   for c in cand:
    rows=[r for r in(broad if isb else board)[c]if pred(r)];by=collections.defaultdict(list)
    for r in rows:by[r['player_id']].append(r)
    grouped[c]=by;nums=[];sides=[];supports=collections.Counter()
    for pl in players:
     rr=by[pl];nn=num(c,rr);sv=None if isb else ss(rr);nums.append(nn);sides.append(sv);n=nn['scored']if isb else sv['COMBINED']['decided'];supports[supportbin(n)]+=1;expected=dict(panel=panel,candidate_id=c,player_id=pl,eligible=len(rr),unique_games=len({r['game_id']for r in rr}),appearance_counts=dict(collections.Counter(r['appearance']for r in rr)),canonical_status_counts=None if isb else dict(collections.Counter(r['status']for r in rr)),own_sides_OVER_UNDER_COMBINED=None if isb else[[sv[side][k]for k in card['side_columns']]for side in['OVER','UNDER','COMBINED']],numerical=[nn.get(k)for k in card['numerical_columns']],numerical_state=nn.get('state','POINT_PRODUCT'),fallback_counts=dict(collections.Counter(r['fallback_state']for r in rr)),unavailability_reasons=dict(collections.Counter(r['unavailability_reason']for r in rr if r['unavailability_reason'])))
     h.close(expected,private[(panel,c,pl)],'per_player_card');player_checked+=1
    rate=None if isb else{side:dict(players_with_decisions=sum(v[side]['decided']>0 for v in sides),mean_player_hit_rate=math.fsum(v[side]['rate']for v in sides if v[side]['decided'])/sum(v[side]['decided']>0 for v in sides)if any(v[side]['decided']for v in sides)else None)for side in['OVER','UNDER','COMBINED']}
    numeric={metric:math.fsum(v[metric]for v in nums if v.get(metric)is not None)/sum(v.get(metric)is not None for v in nums)if any(v.get(metric)is not None for v in nums)else None for metric in['MAE','MSE','bias']}
    mine=dict(eligible_players_in_global_declared_universe=len(players),players_with_panel_rows=sum(bool(by[pl])for pl in players),players_with_numerical_scores=sum(v['scored']>0 for v in nums),support_kind='numerical_scored'if isb else'own_combined_decided',support_distribution=dict(supports),equal_player_sides=rate,opportunity_weighted_sides=None if isb else ss(rows),equal_player_numerical=numeric,opportunity_weighted_numerical=num(c,rows))
    for k,v in mine.items():h.close(v,public[(panel,c)][k],'player_public/'+k)
   for left,right in plan['paired_candidate_ids']:
    dc=collections.Counter();nc=collections.Counter();dn=delta=nn=0;de=[];ne=[];allerr=[]
    for pl in players:
     aa=grouped[left][pl];bb={r['opportunity_key']:r for r in grouped[right][pl]};pp=[(a,bb[a['opportunity_key']])for a in aa if a['opportunity_key']in bb];dd=[]if isb else[(a,b)for a,b in pp if a['status']in['WIN','LOSS']and b['status']in['WIN','LOSS']]
     if dd:
      d=sum(int(a['status']=='WIN')-int(b['status']=='WIN')for a,b in dd);dc['left_more_correct'if d>0 else'right_more_correct'if d<0 else'tied']+=1;dn+=len(dd);delta+=d;de.append(d/len(dd))
     else:dc['no_common_decisions']+=1
     ee=[abs(a['point']-a['actual'])-abs(b['point']-b['actual'])for a,b in pp if h.finite(a['point'])and h.finite(b['point'])and a['actual']is not None and b['actual']is not None]
     if ee:
      e=math.fsum(ee)/len(ee);nc['left_lower_MAE'if e<0 else'right_lower_MAE'if e>0 else'tied']+=1;nn+=len(ee);allerr.extend(ee);ne.append(e)
     else:nc['no_common_numeric_scores']+=1
    mine=dict(global_players=len(players),direction_player_counts=dict(dc),common_decided_opportunities=dn,opportunity_weighted_accuracy_change=delta/dn if dn else None,equal_player_accuracy_change=math.fsum(de)/len(de)if de else None,numerical_player_counts=dict(nc),common_numerical_opportunities=nn,opportunity_weighted_MAE_change=math.fsum(allerr)/nn if nn else None,equal_player_MAE_change=math.fsum(ne)/len(ne)if ne else None)
    for k,v in mine.items():h.close(v,publicpair[(panel,left,right)][k],'player_pair/'+k)
    player_pairs_checked+=1

 result={'id':'PROFILE-INCREMENT-A-INDEPENDENT-R3-LAW-SCORE-DELTA-v1','state':'PASS_NEW_R3_ROWS_AND_PAIRS_PRIOR_THREE_CELLS_REUSED','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'score_sha256':a.scores_sha256,'code_sha256':sha(Path(__file__).read_bytes()),'reused_independent_raw_source_code_sha256':OLD_CODE_SHA,'new_R3_summary_cells':summary_n,'new_R3_paired_cells':pair_n,'old_summary_cells_reused_exactly':reused_s,'old_paired_cells_reused_exactly':reused_p,'prior_independent_review_sha256':a.previous_review_sha256,'prior_score_sha256':a.previous_scores_sha256,'candidate_views':len(cand),'board_opportunities':len(spec),'query_rows':len(queries),'W8_unmapped':unmapped,'W8_exclusions':dict(excluded),'membership_sha256':sha(enc(sorted(membership))),'discrepancies':0,'limits':['Accepted source contracts/current-vintage availability remain inherited; actual source vintage not created by regrade.','Old three-arm cells reused by exact serialized parity, backed by prior independent PASS; only R3 paired game/week500 intervals recomputed. Common whole-week summary intervals not repeated.','No model inference, fit reproduction, current-query packet, selection upgrade or deployment inferred.'],'resources':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'activity':{'fits':0,'model_loads':0,'inference':0,'private_writes':0,'source_HTTP':0}}
 result['coverage_attribution_audit']=coverage;result['new_descriptive_player_checks']=dict(protected_rows=player_checked,public_summary_cells=130 if player_checked else 0,public_paired_cells=player_pairs_checked,no_player_router=True)
 result.update(completed_arms=active_arms,pending_arms=[arm for arm in expected_arm_order if arm not in active_arms],core_scope='FIXED_COMPLETED_ARM_CORE_NOT_ALL_DECLARED_METHODS'if partial else'ALL_FOUR_COMPLETED_ARMS')
 result.update(resource_pending_summary_records=sum(s['execution_state']=='RESOURCE_PENDING'for s in scores['summaries']),resource_pending_pair_records=sum(s['execution_state']=='RESOURCE_PENDING'for s in scores['paired']),executed_pair_records=sum(s['execution_state']=='SCORING_EXECUTED'for s in scores['paired']))
 if partial:result['state']='PASS_NAMED_THREE_ARM_SCORES_DEFENSE_RESOURCE_PENDING'
 a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');signal.alarm(0);print(json.dumps({k:v for k,v in result.items()if k!='coverage_attribution_audit'}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root-notified-complete',required=True);p.add_argument('--scores',type=Path,required=True);p.add_argument('--scores-sha256',required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--CPU-limit',dest='CPU_limit',type=int,default=120);p.add_argument('--previous-scores',type=Path,required=True);p.add_argument('--previous-scores-sha256',required=True);p.add_argument('--previous-review',type=Path,required=True);p.add_argument('--previous-review-sha256',required=True);p.add_argument('--output',type=Path,default=Path('reports/abc-championship/profile-increment-to-release-01/INDEPENDENT_R3_SCORE_DELTA_V1.json'));a=p.parse_args()
 try:run(a)
 except BaseException as e:
  signal.alarm(0);r={'state':'FAILED_INDEPENDENT_LAW_SCORE_NO_REFIT','error_type':type(e).__name__,'error_sha256':sha(str(e).encode()),'code_sha256':sha(Path(__file__).read_bytes()),'score_sha256':a.scores_sha256,'fits':0,'private_writes':0};a.output.with_name(a.output.stem+'-failure.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');raise
