"""Locate the exact QB/RB boundary behind old mixed-board carry totals."""
import collections,gzip,io,json,sys,zipfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import abc_a_dynamic_carry_wave_v1 as base
def main():
 import pandas as pd
 sys.path.insert(0,'/tmp/abc-improvement-01/C/src');import abc_championship_v2 as c
 b,follow,g,fr=base.sources();freeze=base.doc('category-topfive-matched12-all-finalists-freeze-v1_2.json.gz')
 ref=next(r['forecast']for r in freeze['extra_entries']if r.get('method')=='BACKFIELD_CDF')
 pred=pd.read_parquet(io.BytesIO(base.pin(ref)));pf={(str(r.game_id),str(r.player_id)):r for r in pred.itertuples()}
 with zipfile.ZipFile(io.BytesIO(base.pin(g['offers'])))as z:offers=pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
 with zipfile.ZipFile(io.BytesIO(base.pin(g['qualified_labels'])))as z:labels=pd.read_parquet(io.BytesIO(z.read(g['qualified_labels']['member'])))
 lf={(str(r.game_id),str(r.player_id)):r for r in labels.loc[labels.target.eq('rush_att')].itertuples()}
 rows=[]
 for o in offers.loc[offers.target.eq('rush_att')].to_dict('records'):
  f=pf.get((str(o['game_id']),str(o['player_id'])));l=lf.get((str(o['game_id']),str(o['player_id'])));y=l.actual if l is not None and l.participation_state=='played'and pd.notna(l.actual)else None
  for product in ['mean','median']:
   value=getattr(f,product,None)if f else None;side=c.a.point_side(value,o['line']);side=None if side=='UNAVAILABLE'else side
   r={'game_id':str(o['game_id']),'player_id':str(o['player_id']),'season':int(o['season']),'week':int(o['week']),'selected_side':side,'appearance':'PLAYED'if y is not None else'UNKNOWN','actual':y,'line':float(o['line']),'status':'UNAVAILABLE_FORECAST'if side is None else'UNKNOWN_PARTICIPATION'if y is None else'WIN','comparator':'STRICT_OVER_UNDER','position':o['position'],'product':product};r['status']=c.status(r);rows.append(r)
 scores=[]
 for product in ['mean','median']:
  for role in ['ALL']+sorted({r['position']for r in rows}):
   rr=[r for r in rows if r['product']==product and(role=='ALL'or r['position']==role)]
   scores.append({'method':'BACKFIELD_CDF','product':product,'position_view':role,**c.summary(rr)})
 report={'state':'EXECUTED_POPULATION_CONTRACT_CLARIFICATION','new_fits_inference':0,'source_offer_sha256':g['offers']['sha256'],'source_prediction_sha256':ref['sha256'],'source_outcome_sha256':g['qualified_labels']['sha256'],'scores':scores,'correction':'The retained335opportunity carry board includes96QB and239RB rows. Any RB-only description of that full board is superseded; original scores remain for actual mixedpopulation. This wave explicitly tests239RB opportunities. Do not compare the two unpaired headline rates.','unaffected':'Original W1-6 Backfield668planned/526supported RB numerical study and its original registration are not changed by this offering-panel metadata clarification.','C_admission':'PENDING_C_REVIEW; AdoesnoteditCcanonicalreport.'}
 Path('reports/abc-championship/predictive-improvement-01/POPULATION_CONTRACT_RECONCILIATION_V1.json').write_bytes(base.enc(report));print(json.dumps([{'product':r['product'],'role':r['position_view'],'eligible':r['eligible'],'wins':r['COMBINED']['wins'],'decided':r['COMBINED']['decided']}for r in scores]))
if __name__=='__main__':main()
