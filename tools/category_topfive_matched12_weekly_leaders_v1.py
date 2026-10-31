"""Project descriptive weekly leaders from completed scores, never a policy backtest."""
from pathlib import Path
import csv,gzip,io,json
from tools.category_topfive_matched12_publication_payload_v2 import private_aggregate
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030'
def main():
 raw=list(csv.DictReader(io.StringIO(gzip.decompress((P/'WEEKLY_POINT_PRODUCTS_W1_7.csv.gz').read_bytes()).decode())))
 rows=[]
 for target in sorted({r['category'] for r in raw}):
  if target=='anytime_td':continue
  for week in range(1,8):
   candidates=[r for r in raw if r['category']==target and int(r['week'])==week and r['full7_headline_eligible']=='True' and r['MAE']]
   if not candidates:continue
   r=min(candidates,key=lambda r:(float(r['MAE']),r['method'],r['product']));rows.append({'category':target,'week':week,'method':r['method'],'product':r['product'],'score':'MAE','value':float(r['MAE']),'scored_player_games':int(r['scored']),'evidence':'EXPOSED_RECONSTRUCTION_DESCRIPTIVE_WEEKLY_WINNER_NOT_ADVANCE_POLICY'})
 a=json.loads(gzip.decompress(private_aggregate('atd')))
 for week in range(1,8):
  candidates=[(r,w['metrics']) for r in a['primary']['records'] if r['scope']=='FULL_REGISTERED_METHOD_POPULATION' and r['product']!='probability_raw' for w in r['weekly'] if w['week']==week and w['metrics']['probability_scores']['Brier'] is not None]
  r,m=min(candidates,key=lambda x:(x[1]['probability_scores']['Brier'],x[0]['method']));rows.append({'category':'anytime_td','week':week,'method':r['method'],'product':r['product'],'score':'Brier','value':m['probability_scores']['Brier'],'scored_player_games':m['scored'],'evidence':'LATE_FIFTH_INCLUDED_EXPOSED_DESCRIPTIVE_NOT_ORIGINAL_FROZEN_FIVE'})
 b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);dest=P/'WEEKLY_OBSERVED_LEADERS_V1.csv';assert not dest.exists();dest.write_text(b.getvalue())
 p=P/'README.md';t=p.read_text();t+='\n## Descriptive weekly leaders\n\n[Week-by-week lowest observed errors](WEEKLY_OBSERVED_LEADERS_V1.csv) lists all twelve categories over Weeks 1–7, using the same frozen role populations and supported output definitions. It includes sample sizes and exact products. These are hindsight weekly winners, not forecasts of which method would win, not the policy’s actual advance choices and not a deployable weekly switching backtest. Tied minima remain tied numerically; the CSV uses a deterministic method-name tie display.\n';p.write_text(t)
 print(json.dumps({'weekly_leader_rows':len(rows),'new_fits_forecasts_scoring':0,'week7':[r for r in rows if r['week']==7]}))
if __name__=='__main__':main()
