import os,time,resource,signal,json,gzip,hashlib,zipfile,io,math,statistics,collections,struct
from decimal import Decimal
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
resource.setrlimit(resource.RLIMIT_CPU,(88,90));signal.alarm(150)
start=time.monotonic();cpu=time.process_time();ROOT=Path.cwd();OUT=ROOT/'reports/abc-championship/predictive-improvement-01'
from tools import category_topfive_matched12_storage_v1 as st
store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO,readonly=True)
dest=store.forward_root/'research'/'ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2';report=json.loads((OUT/'FULL_BOARD_DIRECT_RESULTS_V1.json').read_bytes())
def readzip(name,expected):
 p=dest/name;store.validate_reference(p,expected['sha256']);assert p.stat().st_size==expected['bytes'];return zipfile.ZipFile(p)
z=readzip('FULL_BOARD_CARRY_GRADE_V1.zip',report['private_grade']);rows=json.loads(gzip.decompress(z.read('GRADE_ROWS.json.gz')))
nz=readzip('NON_RB_CARRY_FORECASTS_V1.zip',report['new_forecasts']);new=json.loads(gzip.decompress(nz.read('FORECASTS.json.gz')));source=json.loads(nz.read('SOURCE.json'))
assert source['new_fits']==0 and source['new_inference_rows']==192 and source['other_roles']=={'QB':80,'WR':16}
admission=json.loads((OUT/'completion-v3/CONTENT_ADMISSION_V3.json').read_bytes());a1ref=next(r for r in admission['models_fresh_process_readback']if r['season']==2026)
assert source['parent_A1_model_sha256']==a1ref['sha256']
bcfg=json.loads((ROOT/'config/category-topfive-backfield-v1.sealed.json').read_bytes());bfr=json.loads((Path(bcfg['native_root'])/'COMPLETE.json').read_bytes())['freeze'];assert source['A0_capsule_sha256']==bfr['sha256']
for zz in [z,nz]:
 for member,ref in json.loads(zz.read('MEMBER_MANIFEST.json')).items():
  raw=zz.read(member);assert len(raw)==ref['bytes']and hashlib.sha256(raw).hexdigest()==ref['sha256']
assert len(rows)==5695 and len(new)==192
import pyarrow.parquet as pq
def auth(ref):
 b=Path(ref['path']).read_bytes();assert len(b)==ref['bytes']and hashlib.sha256(b).hexdigest()==ref['sha256'];return b
cfg=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()))
oz=zipfile.ZipFile(io.BytesIO(auth(cfg['offers'])));offers=pq.read_table(io.BytesIO(oz.read(cfg['offers']['member']))).to_pylist();offers=[r for r in offers if r['target']=='rush_att']
key=lambda r:(r['game_id'],r['player_id']);O={key(r):r for r in offers};assert len(O)==len(offers)==335;assert dict(collections.Counter(r['position']for r in offers))=={'QB':80,'RB':239,'WR':16}
lz=zipfile.ZipFile(io.BytesIO(auth(cfg['qualified_labels'])));labels=pq.read_table(io.BytesIO(lz.read(cfg['qualified_labels']['member']))).to_pylist();L={key(r):r for r in labels if r['target']=='rush_att'}
groups=collections.defaultdict(list);unique=set()
for r in rows:
 o=O[key(r)];assert r['season']==2026 and r['week']==o['week']and r['position']==o['position']and Decimal(str(r['line']))==Decimal(str(o['line']))and r['opportunity_key']==o['opportunity_key']
 kk=(*key(r),r['arm'],r['policy']);assert kk not in unique;unique.add(kk)
 lab=L.get(key(r));v=lab['actual']if lab and lab['participation_state']=='played'and lab['actual']is not None else None
 assert r['actual']==v
 if v is not None:assert v>=0 and v%1==0 and math.isfinite(v)
 side=r['selected_side'];line=Decimal(str(r['line']))
 expected='UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'UNKNOWN_PARTICIPATION'if v is None else'PUSH'if Decimal(str(v))==line else'WIN'if(Decimal(str(v))>line)==(side=='OVER')else'LOSS'
 assert r['status']==expected
 if r['arm']in['A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION']and r['position']!='RB':
  assert side is None and r['status']=='UNAVAILABLE_FORECAST'and r['outside_scope_reason']=='STRUCTURED_MODEL_FIRST_WAVE_RB_ONLY'
 for week in ['ALL',r['week']]:groups[(r['arm'],r['policy'],week)].append(r)
def counts(rs,side):
 s=[r for r in rs if r['selected_side']in['OVER','UNDER']]if side=='COMBINED'else[r for r in rs if r['selected_side']==side];w=sum(r['status']=='WIN'for r in s);l=sum(r['status']=='LOSS'for r in s)
 return dict(selected=len(s),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l)if w+l else None)
for s in report['scores']:
 rs=groups[(s['arm'],s['policy'],s['week'])]
 for side in ['OVER','UNDER','COMBINED']:assert counts(rs,side)==s[side]
 assert len(rs)==s['eligible']and sum(r['selected_side']is None for r in rs)==s['unavailable']and sum(r['selected_side']=='ABSTAIN'for r in rs)==s['abstentions']and dict(collections.Counter(r['status']for r in rs))==s['states']
# Check only newly extended rows against old controls; prior RB test is not repeated.
fr=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-freeze-v1_2.json.gz').read_bytes()));oldref=next(r['forecast']for r in fr['extra_entries']if r.get('method')=='BACKFIELD_CDF');oldrows=pq.read_table(io.BytesIO(auth(oldref))).to_pylist();OLD={key(r):r for r in oldrows}
exact=0;context=0
for r in new:
 assert r['position']in['QB','WR'];o=O[key(r)];assert o['position']==r['position']
 from datetime import datetime
 assert datetime.fromisoformat(r['cutoff_utc'])<=datetime.fromisoformat(r['kickoff_utc']);clock=r.get('source_information_max_UTC');assert clock not in[None,'NaT']and datetime.fromisoformat(clock)<datetime.fromisoformat(r['cutoff_utc'])
 if r['arm']=='A0_BACKFIELD_CDF':
  old=OLD[key(r)]
  for name in ['mean','median']:assert struct.pack('>d',float(r[name]))==struct.pack('>d',float(old[name]));exact+=1
  for name in ['season','week','team','opponent','position']:assert str(r[name])==str(old[name])
  for name in ['cutoff_utc','kickoff_utc']:assert datetime.fromisoformat(r[name])==old[name]
  context+=1
# Reused RB rows stay identical in relevant grading fields, without rescoring them.
rr=json.loads((OUT/'completion-v3/SCORING_RECEIPT_V1.json').read_bytes());rz=readzip('GRADED_SCORECARD_V1.zip',rr);oldgrades=json.loads(gzip.decompress(rz.read('OFFER_GRADE_ROWS.json.gz')));R={(*key(r),r['arm'],r['policy']):r for r in oldgrades};reused=0
for r in rows:
 if r['position']!='RB':continue
 old=R[(*key(r),r['arm'],r['policy'])]
 for field in ['line','actual','appearance','status','selected_side','point','p_under','p_push','p_over','fallback']:assert r[field]==old[field]
 reused+=1
# Proper probabilities over all supported outcomes, independent of side selection.
proper=[];mass_checks=0
for (arm,policy,week),rs in groups.items():
 if policy!='P2_EXACT_LAW':continue
 available=[r for r in rs if r['p_over']is not None]
 for r in available:
  assert abs(r['p_over']+r['p_under']+r['p_push']-1)<1e-10 and min(r['p_over'],r['p_under'],r['p_push'])>=0
  if Decimal(str(r['line']))%1==Decimal('.5'):assert abs(r['p_push'])<1e-12
  if week=='ALL':mass_checks+=1
 good=[r for r in available if r['actual']is not None and Decimal(str(r['line']))%1==Decimal('.5')]
 bs=statistics.fmean((r['p_over']-int(Decimal(str(r['actual']))>Decimal(str(r['line']))))**2 for r in good)if good else None
 ll=statistics.fmean(-math.log(r['p_over']if Decimal(str(r['actual']))>Decimal(str(r['line']))else r['p_under'])for r in good)if good else None
 proper.append(dict(arm=arm,week=week,eligible=len(rs),probability_available=len(available),scored=len(good),Brier=bs,logloss=ll,neutral_Brier=.25 if good else None,games=len({r['game_id']for r in good})))
assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=1073741824
print(json.dumps({'state':'PASS_INDEPENDENT_FULL_BOARD_EXTENSION','rows':len(rows),'unique_offers':len(O),'positions':dict(collections.Counter(r['position']for r in offers)),'score_cells_verified':len(report['scores']),'cumulative_views':sum(r['week']=='ALL'for r in report['scores']),'A0_extra_contexts_replayed_exact':context,'A0_extra_point_values_bitwise_equal':exact,'new_forecast_source_clocks_checked':len(new),'unchanged_RB_grade_rows':reused,'probability_mass_checks':mass_checks,'full_board_probability_ALL':[r for r in proper if r['week']=='ALL'],'new_fits_inference':0,'private_writes':0,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}))
