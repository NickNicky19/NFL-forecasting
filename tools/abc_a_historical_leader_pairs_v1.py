"""Paired controls for exposed raw historical maxima, not a selected future policy."""
import collections,gzip,hashlib,json,random,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'reports/abc-championship'
def main():
 cfg=json.loads((ROOT/'config/category-topfive-opportunity-ou-technical-v2.sealed.json').read_text());file=Path(cfg['output'])/'GRADE_COMPLETE.zip';assert hashlib.sha256(file.read_bytes()).hexdigest()=='1040e07a1cef102b1f9487f824ff03131899d528f740f30f644fe0249f12e7cd'
 with zipfile.ZipFile(file)as z:old=[json.loads(l)for l in gzip.decompress(z.read('grade.jsonl.gz')).splitlines()]
 scores=json.loads((P/'A_HISTORICAL_COMMON_SCORER_V1.json').read_text())['scores'];out=[]
 for per,year,hi in [('E1_PARTIAL_2026_W1_5',2026,8),('E3_2024_W1_8',2024,8),('E4_2024_FULL_REG',2024,18)]:
  for cat in ['pass_att','rush_att','rec']:
   ss=[r for r in scores if r['period_id']==per and r['category']==cat and r['COMBINED']['decided']];leader=max(ss,key=lambda r:r['COMBINED']['rate']);method=leader['procedure_id'].split('::')[-1];pool=[r for r in old if r['target']==cat and r['season']==year and r['week']<=hi];index={(r['procedure'],r['opportunity_id']):r for r in pool};selected=[r for r in pool if r['procedure']==method and r['direction_result']in('CORRECT','INCORRECT')]
   for control in ['ALWAYS_OVER','ALWAYS_UNDER','P1_F','P2_F_FULL']:
    if control==method:continue
    pairs=[(r,index[(control,r['opportunity_id'])])for r in selected if(control,r['opportunity_id'])in index and index[(control,r['opportunity_id'])]['direction_result']in('CORRECT','INCORRECT')];n=len(pairs);gg=collections.defaultdict(lambda:[0,0]);wins=sum(a['direction_result']=='CORRECT'for a,b in pairs);cwins=sum(b['direction_result']=='CORRECT'for a,b in pairs)
    for a,b in pairs:gg[a['week']][0]+=int(a['direction_result']=='CORRECT')-int(b['direction_result']=='CORRECT');gg[a['week']][1]+=1
    vals=list(gg.values());boot=[];rng=random.Random(20261103)
    if vals:
     for _ in range(1000):
      sample=[vals[rng.randrange(len(vals))]for _ in vals];boot.append(sum(t[0]for t in sample)/sum(t[1]for t in sample))
     boot.sort()
    out.append({'period_id':per,'category':cat,'observed_raw_leader':method,'control':control,'outer_eligible':leader['eligible'],'leader_selected':leader['COMBINED']['selected'],'leader_total_decided':leader['COMBINED']['decided'],'pair_decided':n,'leader_wins_on_pairs':wins,'control_wins_on_pairs':cwins,'win_change':wins-cwins,'accuracy_change':(wins-cwins)/n if n else None,'week_cluster_count':len(gg),'nominal_paired_week_bootstrap95':[boot[25],boot[975]]if boot else None,'scope':'Exposed rawmax diagnostic on same selected opportunities; not learned routing, no selection/multiplicity adjustment; fewweekclusters weak.'})
 (P/'HISTORICAL_LEADER_CONTROL_PAIRS_V1.json').write_text(json.dumps(out,indent=2)+'\n');print('paired_control_cells',len(out))
if __name__=='__main__':main()
