"""Independent verification of C03 cached-point grading; source IO only is reused.

No author grader, summary, pair or public-join function is invoked. This is a
bounded acceptance calculation, not another canonical NFL evaluator.
"""
from pathlib import Path
from decimal import Decimal
from collections import Counter,defaultdict
import argparse,datetime,gzip,hashlib,io,json,lzma,math,os,resource,signal,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
SCORE_SHA='f50f710c41de70e6ff4998f701e259ef532a5cf3c99d3ac7f3be9bfb6e1035e8'
PROTOCOL_SHA='4b106539ca2b8c1f7c6bbf365ad8590327261b0471627d7ad84a4756c99d8f83'
SRC_SHA='0a374a147bdad11bf3226265894b00b39928903f62740e0a4d2344f91eeb8497'
R0_SHA='05a6b8bbad28ce7978c59f1ae026d6fb61fed964db724f41be253e4606119ccc'
BASE=ROOT/'reports/abc-championship/profile-increment-to-release-01/closure-next-02'
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def yes(v,m):
 if not v:raise AssertionError(m)
def finite(v):return type(v)in[int,float]and math.isfinite(v)
def read(p,h):
 b=Path(p).read_bytes();yes(sha(b)==h,'Exact immutable source hash differs');return b
def tm(v):return{'LA':'LAR','WSH':'WAS','STL':'LAR','SD':'LAC','OAK':'LV'}.get(str(v),str(v))
def clock(v,pd):
 t=pd.Timestamp(v);return None if pd.isna(t)or t.tzinfo is None else t.tz_convert('UTC')
def side(p,l):
 if p is None:return None
 a,b=Decimal(str(p)),Decimal(str(l));return'OVER'if a>b else'UNDER'if a<b else'ABSTAIN'
def status(r):
 s=r['selected_side']
 if s is None:return'UNAVAILABLE_FORECAST'
 if s=='ABSTAIN':return'ABSTAIN'
 if r['appearance']!='PLAYED':return{'DNP':'DNP','PENDING':'PENDING'}.get(r['appearance'],'UNKNOWN_PARTICIPATION')
 if r['actual']is None:return'MISSING_ACTUAL'
 a,b=Decimal(str(r['actual'])),Decimal(str(r['line']))
 return'PUSH'if a==b else'WIN'if(a>b)==(s=='OVER')else'LOSS'
def mask(rr):return sha(enc(sorted(r['opportunity_key']for r in rr)))
def numeric(rr):
 e=[Decimal(str(r['point']))-Decimal(str(r['actual']))for r in rr if r['point']is not None and r['appearance']=='PLAYED'and r['actual']is not None];n=len(e);ae=sorted(map(abs,e));mse=sum((v*v for v in e),Decimal(0))/n if n else None
 return dict(scored=n,MAE=float(sum(ae,Decimal(0))/n)if n else None,MSE=float(mse)if n else None,RMSE=math.sqrt(float(mse))if n else None,bias=float(sum(e,Decimal(0))/n)if n else None,absolute_error_p90_nearest_rank=float(ae[max(0,math.ceil(.9*n)-1)])if n else None,max_absolute_error=float(max(ae))if n else None)
def scalar_eq(a,b,where):
 if a is None or b is None:yes(a is b,'Null mismatch '+where)
 elif isinstance(a,(int,float))and isinstance(b,(int,float)):yes(abs(a-b)<=1e-10*max(1,abs(a),abs(b)),'Numeric mismatch '+where)
 else:yes(a==b,'Value mismatch '+where)
def interval(groups,np):
 if len(groups)<2:return None
 arr=np.asarray([groups[k]for k in sorted(groups)],dtype=float);rng=np.random.default_rng(20261110);ix=rng.integers(0,len(arr),(500,len(arr)));draw=arr[ix];return list(map(float,np.quantile(draw[:,:,0].sum(axis=1)/draw[:,:,1].sum(axis=1),[.025,.975])))
def interval_eq(a,b,where):
 if a is None or b is None:yes(a is b,'Interval-null mismatch '+where)
 else:
  for x,y in zip(a,b):scalar_eq(x,y,where)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--c-points',type=Path,required=True,help='Exact permitted C03 public point packet')
 parser.add_argument('--r0-points',type=Path,required=True,help='Exact permitted original C baseline point packet')
 parser.add_argument('--rb-offered-metadata',type=Path,required=True,help='Owner-local outcome-free RB metadata destination; an existing file must match')
 parser.add_argument('--output',type=Path,required=True,help='New independent receipt path; preserve original receipts')
 args=parser.parse_args()
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(80,80));resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2);signal.alarm(300)
 for k in['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
 sys.path.insert(0,str(ROOT));import numpy as np;import pandas as pd;import pyarrow as pa;import pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
 score_raw=read(BASE/'C03_RECEPTION_SCORES_V1.json.gz',SCORE_SHA);result=json.loads(gzip.decompress(score_raw));plan=json.loads(read(BASE/'C03_RECEPTION_SCORING_GO_V1.json',PROTOCOL_SHA))
 for p,h in plan['code_sha256'].items():read(ROOT/p,h)
 c_body=read(args.c_points,SRC_SHA);c=json.loads(lzma.decompress(c_body));r0=json.loads(gzip.decompress(read(args.r0_points,R0_SHA)))
 old_raw=read(ROOT/plan['prior_results']['path'],plan['prior_results']['sha256']);prior=json.loads(old_raw);yes(enc(result['summaries'][:768])==enc(prior['summaries']),'Old768 cells changed')
 # Only this established source restoration helper is reused. No grading or
 # summary/join calculation is called from the original or C03 authors.
 from tools import player_context_completion_reception_v1 as source_io
 _,refs,board,af,_,fixed,_=source_io.restore(pd)
 yes(len(board)==733 and len(fixed)==667,'Original population changed');yes(mask([dict(opportunity_key=b['opportunity'])for b in board])==plan['outer733_mask_sha256'],'Outer mask differs');yes(sha(enc(sorted(fixed)))==plan['fixed667_mask_sha256'],'Fixed mask differs')
 with zipfile.ZipFile(io.BytesIO(source_io.read_ref(refs['offers'])))as z:offers=pq.read_table(io.BytesIO(z.read(refs['offers']['member']))).to_pandas()
 # Reuse this same offers read for a separate outcome-free rushing metadata
 # cache requested by the integrator. Never serialize quote/actual/name fields.
 rb=offers.loc[offers.target.eq('rush_yd')&offers.position.eq('RB')&offers.season.eq(2026)&offers.week.between(1,7)]
 keys=['season','week','game_id','player_id'];rr=rb[keys].drop_duplicates().sort_values(keys).to_dict('records');yes(len(rr)==291 and len(rb)==291,'RB metadata universe differs')
 panels={str(panel):g[keys].drop_duplicates().sort_values(keys).to_dict('records')for panel,g in rb.groupby('source_stream')};yes(len(panels.get('ANNUAL_NAMED_NJ',[]))==183,'RB annual metadata differs')
 meta=dict(player_games=rr,unique_player_games=len(rr),source_sha256=refs['offers']['sha256'],panels=panels);mraw=enc(meta);yes(len(mraw)<=65536,'RB cache exceeds64KiB')
 path=args.rb_offered_metadata
 if path.exists():yes(path.read_bytes()==mraw,'Existing RB metadata differs')
 else:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb')as f:f.write(mraw)
 with zipfile.ZipFile(io.BytesIO(source_io.read_ref(refs['qualified_labels'])))as z:labels=pq.read_table(io.BytesIO(z.read(refs['qualified_labels']['member']))).to_pandas()
 offers=offers.loc[offers.target.eq('rec')&offers.position.isin(['WR','TE'])&offers.season.eq(2026)&offers.week.between(1,7)];om={str(r.opportunity_key):r for r in offers.itertuples()};yes(len(om)==733,'Offer identities differ')
 labels=labels.loc[labels.target.eq('rec')&labels.season.eq(2026)&labels.week.between(1,7)];lm={(str(r.game_id),str(r.player_id)):r for r in labels.itertuples()}
 for b in board:
  o=om[b['opportunity']];yes((str(o.game_id),str(o.player_id),int(o.week),str(o.line))==(b['game'],b['player'],b['week'],b['original_line_exact_text']),'Original line/identity differs');l=lm.get((b['game'],b['player']));part=getattr(l,'participation_state',None);appearance='PENDING'if getattr(l,'outcome_state',None)=='pending'else'DNP'if str(part).lower()=='dnp'else'PLAYED'if part=='played'else'UNKNOWN';value=getattr(l,'actual',None);actual=float(value)if appearance=='PLAYED'and finite(value)and value>=0 and value==int(value)else None
  yes((appearance,actual)==(b['appearance'],b['actual']),'Independent label/presence differs')
  if actual is not None:yes(l.label_reason in['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE']and bool(l.participation_evidence),'Unsupported outcome')
 oldmap={(r['game_id'],r['player_id']):r for r in r0['rows']};slots={int(r['slot'].rsplit('W',1)[1]):r for r in r0['slots']};newmap={(r['procedure'].rsplit('::',1)[1],r['game_id'],r['player_id']):r for r in c['rows']if r['season']==2026 and 1<=r['week']<=7};new_ids=[f'C-RECEIVING-PROFILE-INCREMENT-v2::{a}::{p}'for a in['R1','R2','R3']for p in['MEAN','MEDIAN']];reason={};supported={}
 for b in board:
  o=om[b['opportunity']];f=oldmap.get((b['game'],b['player']));g=r0['games'].get(b['game']);slot=slots[b['week']];why=None
  if f is None:why='NO_RETAINED_C_LEAF_POINT'
  elif f['position']!=b['position']:why='EXACT_ROLE_MISMATCH'
  elif int(f['week'])!=b['week']or g is None or int(g['week'])!=b['week']:why='EXACT_GAME_WEEK_MISMATCH'
  elif tm(f['team'])!=tm(o.team)or tm(f['opponent'])!=tm(o.opponent):why='EXACT_HISTORICAL_TEAM_OPPONENT_MISMATCH'
  else:
   a=clock(o.kickoff_utc,pd);d=clock(o.cutoff_utc,pd);cg=clock(g['kickoff_UTC'],pd);cc=clock(g['as_of_UTC'],pd);origin=clock(slot['origin_UTC'],pd);latest=pd.to_datetime(slot['latest_training_available'],unit='s',utc=True)if finite(slot.get('latest_training_available'))else None
   if any(v is None for v in[a,d,cg,cc,origin,latest]):why='UNQUALIFIED_C_OR_A_CLOCK'
   elif not(a==cg and d==cc and origin<=cc and latest<origin):why='INCOMPATIBLE_INFORMATION_HORIZON_OR_TRAINING_ORIGIN'
  reason[b['opportunity']]=why;supported[b['opportunity']]=f if why is None else None
 yes(sum(v is not None for v in supported.values())==678,'Baseline availability differs')
 # Reconstruct every old contender from its permitted retained source rows.
 vectors={};amap={}
 for cid,(method,product)in zip(source_io.A_IDS,source_io.A_PRODUCTS):amap[cid]={(str(r.game_id),str(r.player_id)):r for r in af.loc[af.method.eq(method)&af['product'].eq(product)].itertuples()}
 r0ids=['C::C-ALL12-LAW-THRESHOLD-v2.1::rec::H-MULTI::P2_LEAF::E0_OP::'+p for p in['MEAN_POINT_DIRECTION','MEDIAN_POINT_DIRECTION']]
 for cid in plan['candidate_ids']:
  vv=[]
  for b in board:
   k=(b['game'],b['player']);point=None;fallback=None;why=None;covered=None;imputed=None
   if cid in new_ids:
    arm,product=cid.split('::')[-2:];why=reason[b['opportunity']];f=newmap.get((arm,*k))if why is None else None
    if f is not None:
     yes(f['role']==b['position']and f['week']==b['week']and tm(f['team'])==tm(om[b['opportunity']].team)and tm(f['opponent'])==tm(om[b['opportunity']].opponent),'New forecast identity/context differs');point=float(f[product.lower()]);fallback=f['hard_fallback'];covered=f['profile_covered'];imputed=f['any_imputed']
   elif cid in r0ids:
    f=supported[b['opportunity']];why=reason[b['opportunity']];point=None if f is None else float(f['mean'if cid==r0ids[0]else'median']);fallback=f['fallback']if f else None
   elif cid in amap:
    f=amap[cid].get(k)
    if f is None:why='MISSING_RETAINED_A_POINT'
    elif str(f.position)!=b['position']:why='POSITION_CONTRACT_MISMATCH'
    elif finite(f.prediction):point=float(f.prediction)
   elif cid in source_io.C_IDS:
    j=source_io.C_IDS.index(cid);point=b['points'][j];fallback=b['fallbacks'][j];why=b['unavailability_reasons'][j]
   elif not cid.startswith('ALWAYS_'):raise AssertionError('Unexpected candidate')
   selected=cid.removeprefix('ALWAYS_')if cid.startswith('ALWAYS_')else side(point,b['original_line_exact_text']);r=dict(season=2026,week=b['week'],game_id=b['game'],player_id=b['player'],opportunity_key=b['opportunity'],source_panel=b['source_panel'],line=b['original_line_exact_text'],actual=b['actual'],appearance=b['appearance'],point=point,selected_side=selected,fallback=fallback,why=why,profile_covered=covered,any_imputed=imputed);r['status']=status(r);vv.append(r)
  vectors[cid]=vv
 discrepancies=[];cells=0;knownzero=0;coverage={}
 for expected in result['summaries'][768:]:
  cid=expected['candidate_id'];yes(cid in new_ids,'Unexpected new candidate');rr=[r for r in vectors[cid]if(expected['view']=='FULL_A733'or r['opportunity_key']in fixed)and(expected['source_panel']=='ALL'or r['source_panel']==expected['source_panel'])and(expected['week_view']=='ALL'or r['week']==expected['week_view'])];cells+=1
  for label in['OVER','UNDER','COMBINED']:
   ss=[r for r in rr if r['selected_side']in['OVER','UNDER']]if label=='COMBINED'else[r for r in rr if r['selected_side']==label];counts=Counter(r['status']for r in ss);w,l=counts['WIN'],counts['LOSS'];own=dict(selected=len(ss),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l)if w+l else None)
   for k,v in own.items():scalar_eq(v,expected[label][k],cid+label+k)
  states=dict(Counter(r['status']for r in rr));yes(states==expected['states'],'State partition differs');yes(len(rr)==expected['eligible']and sum(r['selected_side']is None for r in rr)==expected['unavailable']and sum(r['selected_side']=='ABSTAIN'for r in rr)==expected['abstentions'],'Coverage partition differs')
  yes(len({r['game_id']for r in rr})==expected['games']and len({(r['game_id'],r['player_id'])for r in rr})==expected['player_games'],'Game counts differ')
  yes(dict(Counter(r['appearance']for r in rr))==expected['outer_appearance_states'],'Participation partitions differ');yes(dict(Counter(r['why']for r in rr if r['why']))==expected['unavailable_reasons'],'Missing reasons differ')
  yes(sum(r['fallback']not in[None,False,'']for r in rr)==expected['fallback_outputs']and sum(r['profile_covered']is True for r in rr)==expected['profile_covered_outputs']and sum(r['any_imputed']is True for r in rr)==expected['any_imputed_outputs'],'Support/fallback contribution differs')
  for k,v in numeric(rr).items():scalar_eq(v,expected['numerical'][k],cid+k)
  if expected['view']=='FULL_A733'and expected['source_panel']=='ALL'and expected['week_view']=='ALL':coverage[cid]=dict(eligible=len(rr),decided=expected['COMBINED']['decided'],selected=expected['COMBINED']['selected'],unknown=states.get('UNKNOWN_PARTICIPATION',0),unavailable=states.get('UNAVAILABLE_FORECAST',0),fallback=expected['fallback_outputs'],known_zero_outcomes=sum(r['actual']==0 and r['appearance']=='PLAYED'for r in rr))
 yes(cells==288,'Wrong new summary count')
 pairs=0
 for expected in result['paired']:
  view,panel=expected['view'],expected['source_panel'];v={c:[r for r in vectors[c]if(view=='FULL_A733'or r['opportunity_key']in fixed)and(panel=='ALL'or r['source_panel']==panel)]for c in[expected['left'],expected['right']]};left=v[expected['left']];right={r['opportunity_key']:r for r in v[expected['right']]};matched=[(a,right[a['opportunity_key']])for a in left];dec=[(a,b)for a,b in matched if a['status']in['WIN','LOSS']and b['status']in['WIN','LOSS']];games=defaultdict(lambda:[0.,0.]);weeks=defaultdict(lambda:[0.,0.])
  for a,b in dec:
   d=int(a['status']=='WIN')-int(b['status']=='WIN');games[a['game_id']][0]+=d;games[a['game_id']][1]+=1;weeks[a['week']][0]+=d;weeks[a['week']][1]+=1
  own=dict(common_decided=len(dec),left_wins=sum(a['status']=='WIN'for a,b in dec),right_wins=sum(b['status']=='WIN'for a,b in dec),win_change=sum(int(a['status']=='WIN')-int(b['status']=='WIN')for a,b in dec),side_disagreements=sum(a['selected_side']!=b['selected_side']for a,b in dec),game_clusters=len(games),week_clusters=len(weeks),common_mask_sha256=mask([a for a,b in dec]))
  for k,v in own.items():scalar_eq(v,expected[k],k)
  interval_eq(interval(games,np),expected['paired_accuracy_change_interval95'],'game interval');interval_eq(interval(weeks,np),expected['paired_accuracy_week_interval95'],'week interval')
  numeric_pairs=[(a,b)for a,b in matched if a['point']is not None and b['point']is not None and a['appearance']=='PLAYED'and a['actual']is not None];g=defaultdict(lambda:[0.,0.]);dd=[]
  for a,b in numeric_pairs:
   yes(a['actual']==b['actual']and a['appearance']==b['appearance'],'Pair outcomes differ');d=float(abs(Decimal(str(a['point']))-Decimal(str(a['actual'])))-abs(Decimal(str(b['point']))-Decimal(str(b['actual']))));dd.append(d);g[a['game_id']][0]+=d;g[a['game_id']][1]+=1
  e=expected['numerical_paired'];scalar_eq(len(dd),e['common_cases'],'numeric pair count');scalar_eq(math.fsum(dd)/len(dd)if dd else None,e['MAE_change'],'pairedMAE');scalar_eq(mask([a for a,b in numeric_pairs]),e['common_mask_sha256'],'numeric mask');interval_eq(interval(g,np),e['game_interval95'],'numeric game interval');pairs+=1
 yes(pairs==600,'Wrong pair count')
 out=dict(id='A-NEXT02-C03-INDEPENDENT-DECIMAL-REVIEW-v1',state='PASS_NEW288_SUMMARIES_600_PAIRS_WITH_SOURCE_MASKS',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),score_sha256=SCORE_SHA,protocol_sha256=PROTOCOL_SHA,code_sha256=sha(Path(__file__).read_bytes()),public_point_source_sha256=SRC_SHA,R0_point_source_sha256=R0_SHA,summary_cells_checked=cells,paired_cells_checked=pairs,old_summary_cells_reused_exactly=768,coverage=coverage,discrepancies=0,RB_offered_metadata_cache=dict(logical_id=path.name,bytes=len(mraw),sha256=sha(mraw),player_games=meta['unique_player_games'],annual_player_games=len(panels['ANNUAL_NAMED_NJ']),contains_lines_or_outcomes=False),activity=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_fits=0,new_model_inference=0,model_loading=0,native_writes=0,source_collection=0),scope='Independent withinA, author-separated Decimal side/grade/numerical calculations and separately vectorized500game/week intervals. Only established OLD source IO helper reused, not C03/base grade/summary/join/pair functions.',limits=['No model restoration/freshfit/rawplay feature review or authenticated historical vintage proof.','Point-only export supplies no probability/confidence/EV.','C/Bactualpeeracknowledgment/consumeruse not inferred; thisiswithinA independentverification.','Fixed667 is declared prior decided mask; full733 preserves all unavailable/unknowncases.'])
 q=args.output;yes(not q.exists(),'Immutable independentreceipt exists');q.write_bytes(enc(out));signal.alarm(0);print(json.dumps(dict(state=out['state'],receipt=q.name,bytes=q.stat().st_size,sha256=sha(q.read_bytes()),resources=out['activity'],RB_metadata=out['RB_offered_metadata_cache'])))
if __name__=='__main__':main()
