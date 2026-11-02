"""Score existing immutable points on exact common outcomes; preserve horizon tiers."""
import collections,gzip,hashlib,json,random,resource,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run():
 resource.setrlimit(resource.RLIMIT_CPU,(30,31));cpu=time.process_time()
 binding=json.loads(gzip.decompress((ROOT/'config/session-ab-private-transport-v1.private.json.gz').read_bytes()));base=Path(binding['destination_root']).parent/'week8-original-grade-v2-batch-20261102'
 def read(name,digest,member):
  b=(base/name).read_bytes();assert hashlib.sha256(b).hexdigest()==digest
  with zipfile.ZipFile(base/name)as z:return json.loads(gzip.decompress(z.read(member)))
 parent=read('GRADING_V1_1.zip','22099b3ebb6d6337100a5e38dbb5df5d34266ccda62a1f195af674f015157876','SCORECARD.json.gz')['numerical']
 r0=read('COMPLETION_V1.zip','bac6a5f39739517502ffe5ced5a33587a3f3bd5a84307ca18cfef08aa4c55493','R0_SCORECARD.json.gz')['numerical']
 r0={ (r['player_id'],r['game_id'],r['category']):r for r in r0 if r['status']=='SUPPORTED'}
 controls=['CLASSIC_CAPTURE_2026-10-28T18:46:39Z_65878902c6','CAPTURED_SELECTED_369fec9caec0'];out=[]
 for control in controls:
  vectors={(r['player_id'],r['game_id'],r['category']):r for r in parent if r['group']==control and r['status']=='SUPPORTED'}
  for cat in sorted({k[2]for k in r0}&{k[2]for k in vectors}):
   keys=sorted(k for k in r0 if k in vectors and k[2]==cat);n=len(keys)
   if not n:continue
   aa=[r0[k]for k in keys];bb=[vectors[k]for k in keys];assert all(a['actual']==b['actual']for a,b in zip(aa,bb))
   da=[abs(a['point']-a['actual'])for a in aa];db=[abs(b['point']-b['actual'])for b in bb];groups=collections.defaultdict(lambda:[0.,0])
   for a,x,y in zip(aa,da,db):groups[a['game_id']][0]+=y-x;groups[a['game_id']][1]+=1
   gg=list(groups.values());rng=random.Random(20261102);s=[]
   for _ in range(1000):
    t=[gg[rng.randrange(len(gg))]for _ in gg];s.append(sum(x[0]for x in t)/sum(x[1]for x in t))
   s.sort();ma=sum(da)/n;mb=sum(db)/n
   out.append({'category':cat,'other_group':control,'paired_rows':n,'games':len(gg),'R0_MAE':ma,'other_MAE':mb,'other_minus_R0_MAE':mb-ma,'other_relative_MAE_gain_percent':100*(ma-mb)/ma if ma else None,'game_interval_other_minus_R0':[s[25],s[975]],'point_values_identical':all(a['point']==b['point']for a,b in zip(aa,bb)),'other_product':sorted({b['product']for b in bb}),'R0_issue_UTC':'2026-10-28T18:46:25Z','other_issue_UTC_range':sorted({b['issue_time']for b in bb})[::max(1,len({b['issue_time']for b in bb})-1)],'horizon_tier':'NEAR_SYNCHRONOUS_PRODUCER_PAIR_INPUT_NORMALIZATION_DIFFERS'if control.startswith('CLASSIC')else'DIFFERENT_ISSUE_HORIZON_DESCRIPTIVE_ONLY_NOT_HEADLINE'})
 result={'state':'COMPLETE_MATCHED_POINT_EVALUATION_NO_FORECAST_CHANGES','results':out,'CPU_seconds':time.process_time()-cpu,'new_fits_inference':0,'nominal_uncertainty':'1000gameclusterreplicatesseed20261102;oneexposedweek,noclaimofscientificqualification','new_independent_NFL_games':0}
 (ROOT/'reports/week8-original-grading-20261102/MATCHED_POINT_RESULTS_V1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':run()
