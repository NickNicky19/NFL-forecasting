"""Independent arithmetic regrade of frozen A rushing forecasts; zero fits/writes.

Source joins follow the pinned contracts. No author scorer, C status/summary,
feature builder or prediction function is imported.
"""
import argparse,collections,csv,datetime,gzip,hashlib,io,json,lzma,math,os,resource,signal,sys,time,zipfile
from decimal import Decimal
from pathlib import Path

ROOT=Path('/workspace/nfl-methods-integration')
NEW=['D0_UNCHANGED_HGB_MAE','D1_HGB_RAW_CONDITIONAL_PROFILE','S0_UNCONDITIONAL_OWN_YPC_FIXED_N','S1_CONDITIONAL_EFFICIENCY_FIXED_N']
CONS=['ALWAYS_OVER','ALWAYS_UNDER']
KEY=['season','week','game_id','player_id']
CTX=['team','opponent','position','kickoff_utc','cutoff_utc']
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def finite(x):return type(x)in[int,float]and math.isfinite(x)
def norm(x):
 s=''if x is None else str(x)
 return s[:-2]if s.endswith('.0')else s
def tm(x):return{'LA':'LAR','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LAR'}.get(x,x)
def key(r):return(int(r['season']),int(r['week']),str(r['game_id']),str(r['player_id']))
def grade(point,side,actual,appearance):
 if side is None:return'UNAVAILABLE_FORECAST'
 if side=='ABSTAIN':return'ABSTAIN'
 if appearance!='PLAYED':return{'DNP':'DNP','PENDING':'PENDING'}.get(appearance,'UNKNOWN_PARTICIPATION')
 if actual is None:return'MISSING_ACTUAL'
 y,l=Decimal(str(actual)),Decimal(str(point))
 if y==l:return'PUSH'
 return'WIN'if((y>l)==(side=='OVER'))else'LOSS'
def side(point,line):
 if not finite(point):return None
 p,l=Decimal(str(point)),Decimal(str(line))
 return'OVER'if p>l else'UNDER'if p<l else'ABSTAIN'
def compatible(f,q,pd):
 if f is None:return'MISSING_FROZEN_FORECAST'
 for c in CTX:
  if c.endswith('_utc'):
   a,b=pd.Timestamp(f.get(c)),pd.Timestamp(q.get(c))
   if pd.isna(a)or pd.isna(b)or a.tzinfo is None or b.tzinfo is None or a!=b:return'EXACT_'+c.upper()+'_MISMATCH_OR_UNKNOWN'
  elif str(f.get(c))!=str(q.get(c)):return'EXACT_'+c.upper()+'_MISMATCH'
 return None
def fb(f):
 if f is None:return'UNAVAILABLE_FORECAST'
 if'fallback'not in f:return'UNRECORDED'
 return'LEARNED_EXPLICIT_NO_FALLBACK'if f['fallback']in[None,'',False,'none']else'FALLBACK:'+str(f['fallback'])
def numeric(rr):
 a=[r for r in rr if finite(r['point'])and r['actual']is not None];ee=[r['point']-r['actual']for r in a];n=len(ee);ae=sorted(map(abs,ee));m=math.fsum(e*e for e in ee)/n if n else None
 return dict(intended=len(rr),available=sum(finite(r['point'])for r in rr),scored=n,unavailable=sum(not finite(r['point'])for r in rr),unknown_outcome=sum(r['actual']is None for r in rr),MAE=math.fsum(ae)/n if n else None,MSE=m,RMSE=math.sqrt(m)if m is not None else None,bias=math.fsum(ee)/n if n else None,absolute_error_p90=ae[min(n-1,math.ceil(.9*n)-1)]if n else None,max_absolute_error=max(ae)if n else None,fallback=dict(collections.Counter(r['fallback_state']for r in rr)),unavailability_reasons=dict(collections.Counter(r['unavailability_reason']for r in rr if r['unavailability_reason'])))
def summary(rr):
 out={}
 for s in['OVER','UNDER','COMBINED']:
  part=[r for r in rr if r['selected_side']in['OVER','UNDER']]if s=='COMBINED'else[r for r in rr if r['selected_side']==s]
  w=sum(r['status']=='WIN'for r in part);l=sum(r['status']=='LOSS'for r in part);out[s]=dict(selected=len(part),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l)if w+l else None)
 out.update(eligible=len(rr),unavailable=sum(r['selected_side']is None for r in rr),abstentions=sum(r['selected_side']=='ABSTAIN'for r in rr),states=dict(collections.Counter(r['status']for r in rr)),games=len({r['game_id']for r in rr}),player_games=len({(r['game_id'],r['player_id'])for r in rr}),weeks=sorted({r['week']for r in rr}),coverage=out['COMBINED']['selected']/len(rr)if rr else None)
 return out
def close(a,b,path=''):
 if isinstance(a,dict):
  assert isinstance(b,dict)and set(a)==set(b),(path,'keys',set(a)^set(b))
  for k,v in a.items():close(v,b[k],path+'/'+k)
 elif isinstance(a,list):
  assert isinstance(b,list)and len(a)==len(b),(path,'listlength')
  for i,(v,w)in enumerate(zip(a,b)):close(v,w,path+'/'+str(i))
 elif isinstance(a,float):assert isinstance(b,(int,float))and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10),(path,a,b)
 else:assert a==b,(path,a,b)
def run(a):
 start,cpu=time.monotonic(),time.process_time()
 for n in['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
 resource.setrlimit(resource.RLIMIT_CPU,(250,300));resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,)*2)
 def limit(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('registered independent arithmetic check')
 signal.signal(signal.SIGXCPU,limit);signal.signal(signal.SIGALRM,limit);signal.alarm(540)
 assert a.root_notified_complete=='ROOT_NOTIFIED_SCORE_COMPLETION_V1'
 raw=a.scores.read_bytes();assert sha(raw)==a.scores_sha256;scores=json.loads(raw);assert scores['state']=='FROZEN_POINT_SCORING_COMPLETE'
 import numpy as np,pandas as pd,pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool());sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
 import nfl_lab
 from tools import category_topfive_matched12_storage_v1 as storage
 outer,_=storage.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=storage.GO,readonly=True)
 prior=outer.complete_peer.prior_forward;dest=prior.forward_root/'research/PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1'
 def native(ref):
  p=dest/ref['id'];prior.validate_reference(p,ref['sha256']);b=p.read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
 view=json.loads(lzma.decompress(native(scores['private_scorecard_view'])));assert view['protocol_sha256']==scores['protocol_sha256'];assert view['execution_receipt_sha256']==scores['execution_receipt_sha256']
 refs=view['source_refs']
 def source(name):
  ref=refs[name];b=Path(ref['path']).read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
 assert{n:r['sha256']for n,r in refs.items()}==scores['source_sha256']
 frozen=json.loads(gzip.decompress(native(view['frozen_forecasts'])));fm={}
 for f in frozen:
  k=(f['arm'],key(f));assert k not in fm;fm[k]=f
 cand=scores['candidate_ids'];assert cand[:4]==NEW and cand[-2:]==CONS and len(cand)==13;saved=cand[4:-2]
 def zipped_frame(name):
  with zipfile.ZipFile(io.BytesIO(source(name)))as z:return pd.read_parquet(io.BytesIO(z.read(refs[name]['member'])))
 offers=zipped_frame('A_offers');labels=zipped_frame('A_labels')
 with zipfile.ZipFile(io.BytesIO(source('A_saved')))as z:controls=pd.read_parquet(io.BytesIO(z.read('FORECASTS.parquet')))
 ctable={}
 for f in controls.loc[controls.target.eq('rush_yd')&controls.position.eq('RB')].to_dict('records'):ctable[('SAVED_'+f['method']+'__'+f['product'],key(f))]=f
 for(arm,k),r in fm.items():
  f=ctable.get((arm,k))if arm in saved else ctable.get(('SAVED_HGB_MAE_DIRECT__mae_objective_point',k))if arm==NEW[0]and k[0]==2026 and k[1]<=7 else None
  if f is not None:
   assert float(f['prediction'])==r['point']
   if'fallback'in f:r['fallback']=None if pd.isna(f['fallback'])else f['fallback']
 label={}
 for r in labels.loc[labels.target.eq('rush_yd')&labels.season.eq(2026)&labels.week.between(1,7)].to_dict('records'):
  k=key(r);assert k not in label;s=str(r.get('participation_state','unknown')).lower();p='PENDING'if r.get('outcome_state')=='pending'else'DNP'if s=='dnp'else'PLAYED'if s=='played'else'UNKNOWN';ok=p=='PLAYED'and finite(r.get('actual'))and r.get('label_reason')in['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE']and bool(r.get('participation_evidence'));label[k]=(float(r['actual'])if ok else None,p)
 for name in['history_0','history_1']:
  h=pd.read_parquet(io.BytesIO(source(name)));h=h.loc[h.season.eq(2025)&h.week.between(1,8)&h.position.eq('RB')]
  for r in h.to_dict('records'):
   k=key(r);assert k not in label;s=str(r.get('participation_state','unknown')).lower();ok=s=='played'and r.get('stats_observed')is True and finite(r.get('rush_yd'));label[k]=(float(r['rush_yd'])if ok else None,'DNP'if s=='dnp'else'PLAYED'if s=='played'else'UNKNOWN')
 with zipfile.ZipFile(io.BytesIO(source('W8_sources')))as z:original=json.loads(z.read('archive_pre_first.bin'))
 with zipfile.ZipFile(io.BytesIO(source('W8_graded')))as z:
  parts={n:z.read(n)for n in z.namelist()}
 for n,r in json.loads(parts['MANIFEST.json']).items():assert sha(parts[n])==r['sha256']and len(parts[n])==r['bytes']
 report=json.loads(parts['REPORT.json']);grades=json.loads(gzip.decompress(parts['GRADED_ROWS.json.gz']));ov=json.loads(gzip.decompress(source('W8_overlay')));assert len(report['schedule'])==14 and all(g['final']for g in report['schedule'])
 sched=list(csv.DictReader(io.StringIO(source('W8_schedule').decode())));sched={norm(r['espn']):r for r in sched if r['season']=='2026'and r['week']=='8'and r['game_type']=='REG'and r['espn']};boardgames={norm(g['id']):g for g in original['games']}
 ids=collections.defaultdict(set)
 for r in pd.read_parquet(io.BytesIO(source('W8_feature_identity')),columns=['sleeper_id','player_id']).itertuples():
  if pd.notna(r.sleeper_id)and pd.notna(r.player_id):ids[norm(r.sleeper_id)].add(str(r.player_id))
 native_labels={};presence={}
 for s in json.loads(parts['sleeper_stats.json']):
  assert s['season']in[2026,'2026']and s['week']==8 and s['season_type']=='regular'and s['category']=='stat';matches=[g['game_id']for g in report['schedule']if{tm(g['home']),tm(g['away'])}=={tm(s['team']),tm(s['opponent'])}];assert len(matches)==1;k=(norm(s['player_id']),norm(matches[0]));raw=s.get('stats');pr='MISSING_SOURCE_ROW'if not isinstance(raw,dict)else'ABSENT_REQUIRED_COMPONENT'if'rush_yd'not in raw else'EXPLICIT_UNKNOWN'if not finite(raw['rush_yd'])else'EXPLICIT_FINITE_REQUIRED_COMPONENTS';played=isinstance(raw,dict)and((finite(raw.get('gp'))and raw['gp']>0)or(finite(raw.get('off_snp'))and raw['off_snp']>0));native_labels[k]=(float(raw['rush_yd'])if played and pr=='EXPLICIT_FINITE_REQUIRED_COMPONENTS'else None,'PLAYED'if played else'UNKNOWN');presence[k]=pr
 for i,r in enumerate(grades['numerical']):
  oo=ov['row_overlays']['numerical'][i];assert oo['member_row']==i and oo['original_measurement_state']==r['status']
  if r['category']=='rush_yd':
   k=(norm(r['player_id']),norm(r['game_id']));y,p=native_labels.get(k,(None,'UNKNOWN'));assert oo['source_presence']==presence.get(k,'MISSING_SOURCE_ROW')and(oo['qualified_measurement_state']=='SUPPORTED')==(y is not None);assert y is None or r['actual']==y
 queries={}
 for ref in view['query_references']:
  for q in json.loads(gzip.decompress(native(ref))):assert key(q)not in queries;queries[key(q)]=q
 w8spec=[];excl=collections.Counter();unmapped=0
 for p in original['players']:
  if p['pos']!='RB':continue
  sid,ev=norm(p['id']),norm(p['game_id']);g=sched.get(ev);ps=ids.get(sid,set());reason=None if g is not None and len(ps)==1 else'UNAVAILABLE_CANONICAL_EVENT_OR_PLAYER';q=dict(season=2026,week=8,game_id=g['game_id']if g else'UNMAPPED_EVENT:'+ev,player_id=next(iter(ps))if len(ps)==1 else'UNMAPPED_SLEEPER:'+sid,team=tm(p['team']),opponent=tm(p['opp']),position='RB',kickoff_utc=boardgames[ev]['kickoff']if ev in boardgames else None,cutoff_utc=original['saved_at'],identity_reason=reason)
  if g is not None:assert{q['team'],q['opponent']}=={tm(g['home_team']),tm(g['away_team'])}
  yy=native_labels.get((sid,ev),(None,'UNKNOWN'));k=key(q)
  if reason:assert k not in queries;queries[k]=q;unmapped+=1
  else:assert k in queries and compatible(queries[k],q,pd)is None
  label[k]=yy
  for prop in p['props']:
   if prop['key']!='rush_yd':continue
   if p.get('late'):excl['ORIGINAL_LATE_PLAYER_RUSH_YD_THRESHOLD']+=1;continue
   if prop.get('line_from')not in['dk','sleeper']:excl['GENERATED_OURS_REFERENCE_THRESHOLD'if prop.get('line_from')=='ours'else'UNKNOWN_OR_UNAPPROVED_LINE_SOURCE']+=1;continue
   if not finite(prop.get('line')):excl['NO_FINITE_ORIGINAL_RECORDED_RUSH_YD_THRESHOLD']+=1;continue
   op=sha(enc([2026,8,ev,sid,'rush_yd',prop.get('line_from'),str(prop['line'])]));w8spec.append((q,float(prop['line']),op,yy,'W8_SITE_REFERENCE_THRESHOLD_DIAGNOSTIC','SITE_REFERENCE_THRESHOLD_DIAGNOSTIC'))
 assert len(queries)==2289 and unmapped==2
 protocol=json.loads(a.protocol.read_bytes());assert sha(a.protocol.read_bytes())==scores['protocol_sha256'];actual_panels=set(protocol['actual_recorded_source_panels']);spec=[]
 for o in offers.loc[offers.target.eq('rush_yd')&offers.position.eq('RB')&offers.season.eq(2026)&offers.week.between(1,7)].to_dict('records'):
  source_name=str(o['source_stream']);tier='ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED'if source_name in actual_panels else'SOURCE_OFFER_STATUS_UNVERIFIED_DIAGNOSTIC';spec.append((o,float(o['line']),str(o['opportunity_key']),label.get(key(o),(None,'UNKNOWN')),source_name,tier))
 spec+=w8spec;assert len({x[2]for x in spec})==len(spec)
 broad={c:[]for c in cand};board={c:[]for c in cand};membership=[]
 def resolve(c,q):
  if c in CONS:return None,None,'CONSTANT_NOT_NUMERICAL'
  if c in saved and(int(q['season'])!=2026 or not 1<=int(q['week'])<=7):return None,'OUTSIDE_RETAINED_SAVED_2026_W1_W7_SOURCE_SCOPE','OUTSIDE_SOURCE_SCOPE'
  if q.get('identity_reason')is not None:return None,str(q['identity_reason']),'UNAVAILABLE_CANONICAL_IDENTITY'
  f=fm.get((c,key(q)));why=compatible(f,q,pd);point=float(f['point'])if why is None and finite(f.get('point'))else None
  if why is None and point is None:why='FROZEN_POINT_UNAVAILABLE'
  return point,why,fb(f)
 for k,q in queries.items():
  y,p=label.get(k,(None,'UNKNOWN'));op=sha(enc(list(k)))
  for c in cand:
   value,why,f=resolve(c,q);broad[c].append(dict(season=k[0],week=k[1],game_id=k[2],player_id=k[3],opportunity_key=op,point=value,actual=y,appearance=p,unavailability_reason=why,fallback_state=f))
 for q,line,op,(y,p),source_name,tier in spec:
  for c in cand:
   value,why,f=resolve(c,q);s=c.removeprefix('ALWAYS_')if c in CONS else side(value,line);status=grade(line,s,y,p);r=dict(season=int(q['season']),week=int(q['week']),game_id=str(q['game_id']),player_id=str(q['player_id']),opportunity_key=op,point=value,actual=y,appearance=p,unavailability_reason=why,fallback_state=f,selected_side=s,status=status,source_panel=source_name,evidence_tier=tier);board[c].append(r);membership.append([c,op,value,y,p,s,status,why,f])
 cb=set.intersection(*[{r['opportunity_key']for r in broad[c]if finite(r['point'])}for c in NEW]);co=set.intersection(*[{r['opportunity_key']for r in board[c]if r['selected_side']is not None}for c in NEW]);assert sha(enc(sorted(cb)))==scores['core_masks']['broad']and sha(enc(sorted(co)))==scores['core_masks']['board'];assert sha(enc(sorted(membership)))==view['decision_membership_sha256']
 periods={'W1_W8':range(1,9),'W1_W7':range(1,8),'W8_SEPARATE':[8]};ncheck=0
 for s in scores['summaries']:
  c=s['candidate_id'];weeks=[s['week_view']]if s['period']=='SINGLE_WEEK'else list(periods[s['period']]);data=broad[c]if s['population']=='BROAD_DECLARED_QUERIES'else board[c];core=cb if s['population']=='BROAD_DECLARED_QUERIES'else co
  rr=[r for r in data if r['season']==s['season']and r['week']in weeks and(s['view']=='FULL_INTENDED'or r['opportunity_key']in core)]
  if s['population']=='ORIGINAL_RETAINED_THRESHOLD_BOARD':
   rr=[r for r in rr if(s['source_panel']=='ALL'or r['source_panel']==s['source_panel'])and(s['week_view']=='ALL'or r['week']==s['week_view'])];mine=summary(rr)
   for k,v in mine.items():close(v,s[k],k)
   aw=sorted({r['week']for r in rr if r['status']in['WIN','LOSS','PUSH']and r['evidence_tier']=='ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED'});close(aw,s['actual_recorded_line_scored_weeks'],'actualweeks');assert s['five_actual_week_duration_floor']==(len(aw)>=5)
  close(numeric(rr),s['numerical'],'numerical');ncheck+=1
 def mask(rr):return sha(enc(sorted(r['opportunity_key']for r in rr)))
 def intervals(pp,fn):
  gs=collections.defaultdict(list);ws=collections.defaultdict(list)
  for l,r in pp:gs[l['game_id']].append(fn(l,r));ws[(l['season'],l['week'])].append(fn(l,r))
  def boot(groups):
   if len(groups)<2:return None
   values=[groups[k]for k in sorted(groups)];nums=np.array([math.fsum(v)for v in values]);dens=np.array([len(v)for v in values]);ix=np.random.default_rng(20261110).integers(0,len(values),(500,len(values)));sim=nums[ix].sum(axis=1)/dens[ix].sum(axis=1);return list(map(float,np.quantile(sim,[.025,.975])))
  return dict(game_clusters=len(gs),week_clusters=len(ws),game_interval95=boot(gs),week_interval95=boot(ws))
 pcheck=0
 for s in scores['paired']:
  data=broad if s['population']=='BROAD_DECLARED_QUERIES'else board;core=cb if data is broad else co;weeks=periods[s['period']];rmap={r['opportunity_key']:r for r in data[s['right']]if r['season']==s['season']and r['week']in weeks and(s['view']=='FULL_INTENDED'or r['opportunity_key']in core)and(s['source_panel']=='ALL'or r['source_panel']==s['source_panel'])};pp=[(r,rmap[r['opportunity_key']])for r in data[s['left']]if r['opportunity_key']in rmap and r['season']==s['season']and r['week']in weeks and(s['view']=='FULL_INTENDED'or r['opportunity_key']in core)and(s['source_panel']=='ALL'or r['source_panel']==s['source_panel'])];nn=[(l,r)for l,r in pp if finite(l['point'])and finite(r['point'])and l['actual']is not None and r['actual']is not None];dd=[]if data is broad else[(l,r)for l,r in pp if l['status']in['WIN','LOSS']and r['status']in['WIN','LOSS']];w1=sum(l['status']=='WIN'for l,r in dd);w2=sum(r['status']=='WIN'for l,r in dd)
  mine=dict(common_decided=len(dd),left_wins=w1,right_wins=w2,accuracy_change=(w1-w2)/len(dd)if dd else None,side_disagreements=sum(l['selected_side']!=r['selected_side']for l,r in dd),decision_uncertainty=intervals(dd,lambda l,r:int(l['status']=='WIN')-int(r['status']=='WIN')),common_numerical=len(nn),MAE_change=math.fsum(abs(l['point']-l['actual'])-abs(r['point']-r['actual'])for l,r in nn)/len(nn)if nn else None,MAE_change_uncertainty=intervals(nn,lambda l,r:abs(l['point']-l['actual'])-abs(r['point']-r['actual'])),decided_mask_sha256=mask([l for l,r in dd]),numerical_mask_sha256=mask([l for l,r in nn]))
  for k,v in mine.items():close(v,s[k],'paired/'+k)
  pcheck+=1
 result={'id':'PROFILE-INCREMENT-TO-RELEASE-01-A-INDEPENDENT-SAVED-SCORE-v1','state':'PASS_INDEPENDENT_ROWS_COUNTS_NUMERICAL_PAIRS_AND_MASKS','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'score_SHA256':a.scores_sha256,'code_SHA256':sha(Path(__file__).read_bytes()),'summary_cells_checked':ncheck,'paired_cells_checked':pcheck,'candidate_views':len(cand),'intended_query_rows':len(queries),'board_opportunities':len(spec),'W8_reference_threshold_rows':len(w8spec),'W8_actual_prop_qualification':0,'W8_unmapped_canonical_profiles':unmapped,'W8_exclusions':dict(excl),'membership_SHA256':sha(enc(sorted(membership))),'discrepancies':0,'scope':'All canonical summarysidecounts/states/coverage+numericalerrors, ownmask+allpairedchanges/gameweek500intervals independently reconstructed from immutable vectors/source contracts; no author scorer/common helper or model inference','limits':['Legacy source admission manifests and explicit reported-label contracts inherited; source historical-vintage authenticity not created by independent arithmetic.','Whole-week summary interval implementation is not re-executed; all paired game/week intervals independently reproduced.','Stat-row reconstructed population and W8 reference-only source boundaries remain. No NFL fit/accuracy improvement or live admission inferred.'],'resources':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'activity':{'fits':0,'model_loads':0,'inference':0,'private_writes':0,'source_HTTP':0}}
 a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');signal.alarm(0);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root-notified-complete',required=True);p.add_argument('--scores',type=Path,required=True);p.add_argument('--scores-sha256',required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('/tmp/increment-independent-score-review-v1.json'));a=p.parse_args()
 try:run(a)
 except BaseException as e:
  signal.alarm(0);f={'state':'FAILED_INDEPENDENT_SCORE_CHECK_NO_REFIT','error_type':type(e).__name__,'error_sha256':sha(str(e).encode()),'code_sha256':sha(Path(__file__).read_bytes()),'scores_sha256':a.scores_sha256,'fits':0,'private_writes':0};a.output.with_name(a.output.stem+'-failure.json').write_text(json.dumps(f,indent=2)+'\n');raise
