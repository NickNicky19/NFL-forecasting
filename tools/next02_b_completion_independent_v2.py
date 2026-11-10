"""Portable entry point for the completed independent completion calculation.

The calculation is unchanged from the retained original. This packaging version
adds explicit input/output arguments; it is not new NFL verification evidence.
Public B packets must match the protocol hashes. Original A evidence still
requires its established owner-local, read-only restoration permission.
"""
import pathlib,sys,json,gzip,hashlib,io,zipfile,math,time,resource,signal,collections,datetime,argparse
from decimal import Decimal,localcontext
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1],help='Authorized A repository and restored source-contract root')
parser.add_argument('--score-v2',type=pathlib.Path,help='Retained corrected V2 score; default is the existing report location')
parser.add_argument('--score-v1',type=pathlib.Path,help='Retained original V1 score; default is the existing report location')
parser.add_argument('--protocol',type=pathlib.Path,help='Bound V2 scoring protocol; default is the existing report location')
parser.add_argument('--b-forecast-cache',type=pathlib.Path,required=True,help='Directory of the eight permitted B forecast packets named by the protocol')
parser.add_argument('--output',type=pathlib.Path,required=True,help='New owner-local receipt path; an existing file is not overwritten')
args=parser.parse_args()
ROOT=args.root.resolve();sys.path.insert(0,str(ROOT))
if args.output.exists():parser.error('output receipt already exists')
CPU=time.process_time();WALL=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(78,80));resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2);signal.alarm(300)
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
P=ROOT/'reports/abc-championship/profile-increment-to-release-01/closure-next-02'
raw=(args.score_v2 or P/'B_COMPLETION_JOIN_RESULTS_V2.json.gz').read_bytes();assert hashlib.sha256(raw).hexdigest()=='1f176b310e93129a70d4dcaccf0a79d2ae9f02d8a48bd9851c83a4c41bd216cc';result=json.loads(gzip.decompress(raw));protocol_raw=(args.protocol or P/'B_COMPLETION_SCORING_GO_V2.json').read_bytes();plan=json.loads(protocol_raw)
assert hashlib.sha256(protocol_raw).hexdigest()==result['protocol_sha256']
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def mask(rows):return sha(encoded(sorted(r['key']for r in rows)))
def finite(v):
 try:return v is not None and not isinstance(v,bool) and math.isfinite(float(v))
 except(TypeError,ValueError):return False
def tm(v):return'LAR'if str(v)=='LA'else str(v)
def choose(p,line):
 if p is None:return None
 a,b=Decimal(str(p)),Decimal(str(line));return'OVER'if a>b else'UNDER'if a<b else'ABSTAIN'
def verdict(side,appearance,y,line):
 if side is None:return'UNAVAILABLE_FORECAST'
 if side=='ABSTAIN':return'ABSTAIN'
 if appearance!='PLAYED':return appearance if appearance in['DNP','PENDING']else'UNKNOWN_PARTICIPATION'
 if y is None:return'MISSING_ACTUAL'
 a,b=Decimal(str(y)),Decimal(str(line))
 if a==b:return'PUSH'
 return'WIN'if(side=='OVER'and a>b)or(side=='UNDER'and a<b)else'LOSS'
errors=[];law_stats=dict(laws=0,exact_line_events=0,moment_max_error=0.,normalization_max_error=0.,tail_monotonicity_checks=0)
bcache={}
for ref in plan['B_forecast_refs']:
 b=(args.b_forecast_cache/ref['id']).read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];packet=json.loads(gzip.decompress(b));assert packet['season']==2026 and packet['week']==ref['week']and packet['original_issuance']is False
 for row in packet['rows']:
  assert row['target']=='pass_cmp'and row['position']=='QB'and row['history_regime']=='H-RECENT'and row['feature_memory']=='2022_EXPANDING'
  assert row['fit_cutoff']<=row['feature_cutoff']and(row.get('latest_source_available')is None or row['latest_source_available']<row['feature_cutoff'])
  k=row['method'],str(row['game_id']),str(row['player_id']);assert k not in bcache;bcache[k]=row
  law=row['law'];assert law['kind']=='leaf_mixture';support=law['support'];weights=law['weights'];assert len(support)==len(weights)>0 and support==sorted(set(support));assert all(finite(y)and y>=0 and y==int(y)for y in support)and all(finite(w)and w>=0 for w in weights);assert abs(math.fsum(weights)-1)<1e-9
  mix=float(law['mixture']);q=0. if law['prior']['kind']=='zero'else float(law['prior']['q']);assert 0<=mix<=1 and 0<=q<1
  with localcontext()as c:
   c.prec=50;d=Decimal;mean=(1-d(str(mix)))*sum(d(str(y))*d(str(w))for y,w in zip(support,weights))+d(str(mix))*d(str(q))/(1-d(str(q)))
  err=abs(float(mean)-row['mean']);law_stats['moment_max_error']=max(law_stats['moment_max_error'],err);assert err<=1e-8*max(1,abs(row['mean']));law_stats['laws']+=1

# Only the original A source helpers admit the original immutable bytes.
from tools import category_topfive_matched12_storage_v1 as original_storage
from tools import abc_a_dynamic_carry_wave_v1 as original_sources
store,_=original_storage.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=original_storage.GO,readonly=True)
_,_,g,_=original_sources.sources()
assert all(g[k]['sha256']==h for k,h in result['A_source_sha256'].items())
def member(key):
 with zipfile.ZipFile(io.BytesIO(original_sources.pin(g[key])))as z:return z.read(g[key]['member'])
offers=pd.read_parquet(io.BytesIO(member('offers')));labels=pd.read_parquet(io.BytesIO(member('qualified_labels')))
with zipfile.ZipFile(io.BytesIO(original_sources.pin(g['frozen_bundle'])))as z:
 bb=z.read('FORECASTS.parquet');assert sha(bb)==result['A_member_sha256'];af=pd.read_parquet(io.BytesIO(bb),columns=['target','season','week','method','product','game_id','player_id','position','team','opponent','kickoff_utc','cutoff_utc','prediction','fallback'])
select=lambda f:f.loc[f.target.eq('pass_cmp')&f.season.eq(2026)&f.week.between(1,7)].copy()
board=select(offers);labels=select(labels);af=select(af);assert len(board)==144 and not board.duplicated(['game_id','player_id']).any();assert not labels.duplicated(['game_id','player_id']).any();labelmap={(str(r['game_id']),str(r['player_id'])):r for r in labels.to_dict('records')}
aproducts={f'A::{m}::{p}':(m,p)for m,p in plan['A_products']};amap={cid:{(str(r['game_id']),str(r['player_id'])):r for r in af.loc[af.method.eq(m)&af['product'].eq(p)].to_dict('records')}for cid,(m,p)in aproducts.items()}
NAMESPACE='B-QB-OPPORTUNITY-PROFILE-INCREMENT-v1:';vectors={cid:[]for cid in plan['candidate_ids']};strict=set();shared=set();conflicts=collections.Counter();aliases=[]
def compatible(r,o,b=False,normalize=True):
 if r is None:return False
 if r['position']!=o['position']:return False
 canon=tm if normalize else str
 if any(canon(r[k])!=canon(o[k])for k in['team','opponent']):return False
 for key in['kickoff_utc','cutoff_utc']:
  actual=pd.Timestamp(r['feature_cutoff'],unit='s',tz='UTC')if b else pd.Timestamp(r[key]);target=pd.Timestamp(o[key])
  if actual.tzinfo is None or target.tzinfo is None or actual!=target:return False
 return True
def event(law,line):
 ys,ws=law['support'],law['weights'];b=float(law['mixture']);q=0. if law['prior']['kind']=='zero'else float(law['prior']['q'])
 def prefix(k):return 0. if k<0 else(1-b)*math.fsum(w for y,w in zip(ys,ws)if y<=k)+b*(1-q**(k+1))
 under=prefix(math.ceil(line)-1);over=1-prefix(math.floor(line));push=prefix(int(line))-prefix(int(line)-1)if line==int(line)else 0.
 assert min(under,over,push)>=-1e-10 and max(under,over,push)<=1+1e-10;law_stats['normalization_max_error']=max(law_stats['normalization_max_error'],abs(under+over+push-1));assert abs(under+over+push-1)<1e-9
 assert prefix(math.floor(line)-1)<=prefix(math.floor(line))+1e-12<=prefix(math.floor(line)+1)+1e-12;law_stats['tail_monotonicity_checks']+=1;law_stats['exact_line_events']+=1
 return tuple(max(0.,v)for v in[under,push,over])
for o in board.to_dict('records'):
 k=str(o['game_id']),str(o['player_id']);key=str(o['opportunity_key']);line=float(o['line']);assert o['position']=='QB';lab=labelmap.get(k);appearance='UNKNOWN';actual=None
 if lab is not None:
  appearance='PENDING'if lab.get('outcome_state')=='pending'else'DNP'if str(lab.get('participation_state')).lower()=='dnp'else'PLAYED'if lab.get('participation_state')=='played'else'UNKNOWN'
  if appearance=='PLAYED'and finite(lab.get('actual'))and float(lab['actual'])>=0 and float(lab['actual']).is_integer():
   actual=float(lab['actual']);assert lab['label_reason']in['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE']and bool(lab['participation_evidence'])
 br={a:bcache.get((a,*k))for a in ['R0','R1','R2','R3']}
 if all(compatible(r,o,True)for r in br.values()):shared.add(key)
 if all(compatible(r,o,True,False)for r in br.values()):strict.add(key)
 if key in shared and key not in strict:aliases.append(key)
 for arm,r in br.items():
  if r is not None and actual is not None and finite(r.get('actual'))and float(r['actual'])!=actual:conflicts[arm]+=1
 for cid in vectors:
  point=None;prob=None;fallback=None;nohistory=False
  if cid in aproducts:
   r=amap[cid].get(k)
   if compatible(r,o)and finite(r.get('prediction')):point=float(r['prediction']);fallback=None if pd.isna(r['fallback'])else str(r['fallback'])
   side=choose(point,line)
  elif cid.startswith(NAMESPACE):
   arm,product=cid[len(NAMESPACE):].split('::');r=br[arm];side=None
   if compatible(r,o,True):
    assert r['week']==o['week'];prob=event(r['law'],line);point=None if product=='P2'else r[product];side=('OVER'if prob[2]>prob[0]else'UNDER'if prob[0]>prob[2]else'ABSTAIN')if product=='P2'else choose(point,line);fallback=r.get('fallback');nohistory=r.get('own_prior_games')==0
  else:side=cid.removeprefix('ALWAYS_')
  vectors[cid].append(dict(key=key,game=str(o['game_id']),player=str(o['player_id']),week=int(o['week']),panel=str(o['source_stream']),line=line,actual=actual,appearance=appearance,point=point,side=side,status=verdict(side,appearance,actual,line),prob=prob,fallback=fallback,nohistory=nohistory))
assert len(strict)==133 and len(shared)==144 and len(aliases)==11
assert mask([dict(key=k)for k in shared])==result['shared_B_mask_sha256'];assert dict(conflicts)==result['B_cached_actual_disagreements']
views={'FULL_A_BOARD':set(str(k)for k in board.opportunity_key),'SHARED_ALL_FOUR_B_ARMS':shared,'NEWLY_QUALIFIED_ALIAS_ROWS':shared-strict}
allcount=0;sidechecks=0;probchecks=0;numchecks=0;lawsidechecks=0
def close(a,b,tol=1e-10):return(a is None and b is None)or(a is not None and b is not None and abs(float(a)-float(b))<=tol)
for reported in result['summaries']:
 cid=reported['candidate_id'];rs=[r for r in vectors[cid]if r['key']in views[reported['view']]and(reported['source_panel']=='ALL'or r['panel']==reported['source_panel'])and(reported['week_view']=='ALL'or r['week']==reported['week_view'])]
 assert len(rs)==reported['eligible']and len({r['game']for r in rs})==reported['games'];assert mask(rs)==reported['eligible_mask_sha256'];assert mask([r for r in rs if r['status']in['WIN','LOSS']])==reported['decided_mask_sha256'];counts=dict(collections.Counter(r['status']for r in rs));assert counts==reported['states']
 for side,label in[('OVER','OVER'),('UNDER','UNDER'),(None,'COMBINED')]:
  group=[r for r in rs if r['side']in['OVER','UNDER']and(side is None or r['side']==side)];w=sum(r['status']=='WIN'for r in group);l=sum(r['status']=='LOSS'for r in group);n=w+l;z=reported[label]
  assert z['selected']==len(group)and z['decided']==n and z['wins']==(w if n else None)and z['losses']==(l if n else None)and close(z['rate'],w/n if n else None);sidechecks+=1
 nr=[r for r in rs if r['appearance']=='PLAYED'and r['actual']is not None and r['point']is not None];e=[r['point']-r['actual']for r in nr];assert len(e)==reported['numerical']['scored']
 for name,calc in [('MAE',math.fsum(map(abs,e))/len(e)if e else None),('MSE',math.fsum(v*v for v in e)/len(e)if e else None),('bias',math.fsum(e)/len(e)if e else None)]:assert close(reported['numerical'][name],calc);numchecks+=1
 pr=[r for r in rs if r['appearance']=='PLAYED'and r['actual']is not None and r['prob']is not None];assert len(pr)==reported['probability']['events'];briers=[(r['prob'][2]-float(r['actual']>r['line']))**2 for r in pr];assert close(reported['probability']['Brier'],math.fsum(briers)/len(pr)if pr else None);probchecks+=1
 for r in pr:
  if cid.endswith('::P2'):assert r['side']==('OVER'if r['prob'][2]>r['prob'][0]else'UNDER'if r['prob'][0]>r['prob'][2]else'ABSTAIN');lawsidechecks+=1
 allcount+=1
assert allcount==1782
old=json.loads(gzip.decompress((args.score_v1 or P/'B_COMPLETION_JOIN_RESULTS_V1.json.gz').read_bytes()));oldchecks=0
for s in old['summaries']:
 if s['view']!='SHARED_ALL_FOUR_B_ARMS'or not s['candidate_id'].startswith(NAMESPACE):continue
 rs=[r for r in vectors[s['candidate_id']]if r['key']in strict and(s['source_panel']=='ALL'or r['panel']==s['source_panel'])and(s['week_view']=='ALL'or r['week']==s['week_view'])]
 assert s['states']==dict(collections.Counter(r['status']for r in rs));oldchecks+=1
out=dict(id='A-NEXT02-B-COMPLETION-INDEPENDENT-CALCULATION-v1',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),state='PASS_INDEPENDENT_ORIGINAL_SOURCE_DECIMAL_AND_LAW_ARITHMETIC',score_sha256=sha(raw),protocol_sha256=sha(protocol_raw),source_masks=dict(full144=144,strict_preserved133=133,new_alias11=11,annual_offers=int(sum(r=='ANNUAL_NAMED_NJ'for r in board.source_stream)),site_diagnostic_offers=int(sum(r=='SITE_RECORDED_DK_JURISDICTION_UNKNOWN'for r in board.source_stream))),summary_cells=allcount,side_partitions_checked=sidechecks,numerical_metrics_checked=numchecks,probability_Brier_cells_checked=probchecks,exact_P2_side_cells=lawsidechecks,old_B133_summary_cells_reconciled=oldchecks,law_checks=law_stats,cached_actual_conflicts=dict(conflicts),discrepancies=0,calculation='Original immutable A bytes admitted via original source helpers; no B scorer, Bgrade/probability helper or Csummary function called. Decimal original points/thresholds/labels; ownPMF/geometric-law calculation and aggregate loops.',limits=['No fresh fit or model inference/reconstruction; prior approvedrawfeatureaudit reused','No1359bootstrapintervalsrepeated; identities/sourceclocks/masks/sidepartitions/numeric/probabilityarithmetic covered','Source/vintage/quote clocks remain retrospectivelyunverified; no originalissue/currentpacket/EV/TopPicks/release claim','WithinAseparatecalculationpath, not an externalB/Csessionreceipt'],activity=dict(CPU_seconds=time.process_time()-CPU,wall_seconds=time.monotonic()-WALL,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_fits=0,new_inference=0,native_writes=0,external_HTTP=0))
output=args.output
with output.open('x')as handle:handle.write(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(state=out['state'],bytes=output.stat().st_size,sha256=sha(output.read_bytes()),counts=dict(summaries=allcount,sides=sidechecks,numeric=numchecks,Brier=probchecks),resources=out['activity'])))
