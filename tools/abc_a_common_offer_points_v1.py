"""Owner-local A forecasts on C's bound exact offers; no refits or new grader."""
import collections,datetime,gzip,hashlib,io,json,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CACHE=Path('/tmp/abc-period-continuation-20261103');OUT=ROOT/'reports/abc-championship'
def main():
 import pyarrow.parquet as pq
 sys.path.insert(0,str(CACHE/'C/src'));import abc_championship_v2 as c
 cpu=time.process_time();bindings=json.loads((CACHE/'C/reports/abc-championship/C_INPUT_BINDINGS.json').read_text());versions={}
 for d in bindings['datasets']:
  b=(CACHE/'C'/d['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==d['SHA256'];j=json.loads(gzip.decompress(b)if d['path'].endswith('.gz')else b)
  for r in j['rows']:versions[r['record_id']]=r
 first={}
 for r in versions.values():
  k=c.a.snapshot_key(r);rank=(r['decision_UTC'],r['scoring_snapshot_id']);old=first.get(k)
  if old is None or rank<old[0]:first[k]=(rank,r)
 primary=[r for _,r in first.values()if r['venue']=='pinnacle'and r['season']==2026 and r['week']in(2,3)and r['comparator']=='STRICT_OVER_UNDER'];byoffer=collections.defaultdict(dict)
 for r in primary:byoffer[r['offer_id']][r['method_id']]=r
 cfg=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()));ref=cfg['frozen_bundle'];raw=Path(ref['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256']
 with zipfile.ZipFile(io.BytesIO(raw))as z:pred=pq.read_table(io.BytesIO(z.read('FORECASTS.parquet'))).to_pylist()
 cats={r['category']for r in primary};models=sorted({(r['target'],r['method'],r['product'],r['output_procedure_version'])for r in pred if r['target']in cats and r['week']in(2,3)})
 lookup={}
 for r in pred:
  if r['week']not in(2,3)or r['target']not in cats:continue
  k=(r['game_id'],r['player_id'],r['target'],r['method'],r['product']);old=lookup.get(k)
  assert old is None or old==r;lookup[k]=r
 groups=collections.defaultdict(list);paired=collections.defaultdict(list);reasons=collections.Counter();matched=0
 for oid,off in byoffer.items():
  original=next(iter(off.values()));cat=original['category']
  for target,method,product,version in models:
   if cat!=target:continue
   key=(original['game_id'],original['player_id'],cat,method,product);point=lookup.get(key);reason=None
   if point is None:reason='NO_MATCHING_A_ORIGIN_FORECAST'
   elif point['position']!=original['position']:reason='POSITION_MISMATCH'
   elif cat.startswith('rush_')and point['position']!='RB':reason='A_RB_PRIMARY_CONTRACT_NOT_QB'
   elif point['team']!=original.get('team')and original.get('team')is not None:reason='HISTORICAL_TEAM_MISMATCH'
   if reason:reasons[reason]+=1
   r=dict(original);r['procedure_id']='A::'+version+'::'+method+'::'+product;r['point']=point['prediction']if point is not None and not reason else None;r['selected_side']=c.a.point_side(r['point'],r['line']);r['selected_side']=None if r['selected_side']=='UNAVAILABLE'else r['selected_side']
   if r['selected_side']is None:r['status']='UNAVAILABLE_FORECAST'
   elif r['selected_side']=='ABSTAIN':r['status']='ABSTAIN'
   else:r['status']=c.status(r)
   if not reason:matched+=1
   for w in ('ALL',str(r['week'])):groups[(cat,r['procedure_id'],w)].append(r)
   for control in ['P1_MEDIAN','P1_MEAN','P2_LAW','P3_DIRECT','ALWAYS_OVER','ALWAYS_UNDER','EARLIER_PREVALENCE_V8']:
    q=off.get(control)
    if q is not None and r['status']in('WIN','LOSS')and q['status']in('WIN','LOSS'):paired[(cat,r['procedure_id'],control)].append((r,q))
 scores=[]
 for (cat,method,w),rows in groups.items():scores.append({'category':cat,'procedure_id':method,'period_id':'E1_PARTIAL_C_PINNACLE_W2_W3','actual_weeks':sorted({r['week']for r in rows}),'week_view':w,'source_evidence':'TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC;A_current-vintage_chronological_7day_reconstruction','source_forecast_sha256':ref['sha256'],'C_registered_core_manifest_SHA256':'15c5c843e7e3075723247584699e0f721c960664b762dd7c736b45667447969a','admission':'OWNER_LOCAL_SCORED_C_ADMISSION_NOT_OBSERVED',**c.summary(rows)})
 contrasts=[]
 for (cat,method,control),rs in paired.items():contrasts.append({'category':cat,'procedure_id':method,'control':'C::'+control,'common_decided':len(rs),'A_wins':sum(a['status']=='WIN'for a,b in rs),'control_wins':sum(b['status']=='WIN'for a,b in rs),'win_change':sum(int(a['status']=='WIN')-int(b['status']=='WIN')for a,b in rs),'side_disagreements':sum(a['selected_side']!=b['selected_side']for a,b in rs),'mask_sha256':hashlib.sha256(json.dumps(sorted(a['offer_id']for a,b in rs)).encode()).hexdigest()})
 result={'state':'OWNER_LOCAL_A_C_BOUND_OFFERS_SCORED','C_protocol_id':'ABC-ACTUAL-PROP-CHAMPIONSHIP-v2-C-1','C_commit':'ac9cb1000bcb8f1197505b68ccfe246ea61bbafe','shared_admission':'NOT_OBSERVED','new_fits_inference':0,'A_saved_forecast_rows':len(pred),'C_unique_offer_board':len(byoffer),'A_successful_offer_output_joins':matched,'reasons':dict(reasons),'scores':scores,'paired':contrasts,'CPU_seconds':time.process_time()-cpu,'limits':['A/C procedures differ in source vintage, cutoff assumption and role contracts; complete-system diagnostic, no learner-only causation','A rows remain private; this reproducible owner-local report does not itself establish C admission or independent cross-session private restoration','No new probabilities inferred from points; exact A laws at C offered thresholds remain unscored','PinnacleW2-3 does not replace A source-specific W1-5/W8 panels or full eight-week request']}
 (OUT/'A_ON_C_BOUND_OFFERS_V1.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k]for k in ['state','C_unique_offer_board','A_successful_offer_output_joins','reasons','CPU_seconds']}));print('cells',len(scores),'pairs',len(contrasts))
if __name__=='__main__':main()
