"""Project already graded safe aggregates into readable tables; no new scores."""
from pathlib import Path
import csv,gzip,hashlib,io,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 from tools import category_topfive_matched12_storage_v1 as st
 p=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()))
 r=Path(st.prepare(ROOT)['allocation']['store_policy']['storage']['forward_root'])/'research'/p['run_id']/'RESULTS.zip'
 assert hashlib.sha256(r.read_bytes()).hexdigest()=='5e30c74d98b07acc76cd54a7731570f4f9e4b5843c970a69ae30996cea00fe77'
 with zipfile.ZipFile(r) as z:aggregate=z.read('AGGREGATES.json.gz')
 assert hashlib.sha256(aggregate).hexdigest()=='2275410cce9a7ae7937f3b03ffc0e264534a4b55c09ab93fe9b7f2f15fcfee5c'
 doc=json.loads(gzip.decompress(aggregate));head=doc['headline_numeric'];catalog=doc['catalog'];full={(x['target'],x['method'],x['product']):x for x in head['records'] if x['scope']=='FULL_REGISTERED_METHOD_POPULATION'}
 pairs={(x['target'],*x['candidate']):x['primary'] for x in head['pairwise']}
 side={(x['target'],x['method'],x['product']):x['metrics'] for x in doc['recorded_line_point_decisions']['records'] if x['policy']=='FULL_PRIMARY_ROSTER_INTERSECTION_RECORDED_BOARD'}
 out=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030';numeric=[];directions=[];weekly=[]
 for x in head['records']:
  if x['scope']!='PREDECLARED_PRIMARY_COMMON_CORE':continue
  key=x['target'],x['method'],x['product'];m=x['metrics'];f=full[key]['metrics'];pair=pairs.get(key,{});ints=pair.get('intervals',{})
  entry={'category':key[0],'method':key[1],'product':key[2],'procedure_version':catalog[key[0]][key[1]].get('product_procedure_versions',{}).get(key[2],catalog[key[0]][key[1]]['procedure_version']),'procedure_group':catalog[key[0]][key[1]]['shortlist_group'],'headline_eligible':x['headline_eligible'],'same_core_scored':m['scored'],'full_planned':f['planned'],'full_scored':f['scored'],'full_unknown_participation':f['unknown_participation'],'full_played_missing':f['played_missing'],'full_missing_predictions':f['missing_prediction'],'full_fallback_scored':f['fallback_scored'],'MAE':m.get('MAE'),'MSE_or_ATD_Brier':m.get('MSE'),'RMSE':m.get('RMSE'),'bias':m.get('bias'),'p90_AE':m.get('p90_AE'),'p95_AE':m.get('p95_AE'),'paired_control_loss':pair.get('control_loss'),'candidate_minus_CDF_control':pair.get('candidate_minus_control'),'improvement_percent_vs_named_CDF_NOT_SITE':pair.get('improvement_percent'),'game_CI_lower':ints.get('game_id',{}).get('lower'),'game_CI_upper':ints.get('game_id',{}).get('upper'),'week_CI_lower':ints.get('week',{}).get('lower'),'week_CI_upper':ints.get('week',{}).get('upper'),'evidence':'EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION_2026_REG_W1_7'};numeric.append(entry)
  s=side.get(key)
  if s:
   d={k:entry[k] for k in ['category','method','product','procedure_version','headline_eligible']};d.update(opportunities=s['opportunities'],games=s['games'],weeks=','.join(map(str,s['weeks'])),no_lean=s['no_lean'],missing_offer_or_prediction=s['missing_offer_or_prediction'],unknown_participation=s['unknown_participation_rows'],played_missing=s['played_missing_outcome_rows'])
   for a in ['over','under']:
    for k in ['wins','losses','decided','hit_rate','pushes','DNP','unresolved']:d[a+'_'+k]=s[a][k]
   d.update(total_correct=s['correct'],total_decided=s['decided'],hit_rate=s['hit_rate'],MAE_on_offered_pool=s['MAE_on_supported_offered_point_rows'],settlement='STATISTICAL_DIRECTION_NOT_VENUE_SETTLEMENT',quote_timing='UNVERIFIED',prices_and_ROI='NOT_SCORED_HERE');directions.append(d)
 for x in doc['recorded_line_point_decisions']['records']:
  if x['policy']!='FULL_PRIMARY_ROSTER_INTERSECTION_RECORDED_BOARD':continue
  for w in x['weekly']:
   m=w['metrics'];row={'category':x['target'],'method':x['method'],'product':x['product'],'week':w['week'],'opportunities':m['opportunities'],'MAE_offered':m['MAE_on_supported_offered_point_rows'],'no_lean':m['no_lean'],'correct':m['correct'],'decided':m['decided']}
   for a in ['over','under']:
    for k in ['wins','losses','decided','hit_rate','pushes','DNP','unresolved']:row[a+'_'+k]=m[a][k]
   weekly.append(row)
 def text_csv(rows):
  b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);return b.getvalue()
 for name,rows in [('POINT_PRODUCTS_W1_7.csv',numeric),('EACH_POINT_PRODUCTS_OWN_OVER_UNDER_W1_7.csv',directions)]:
  path=out/name;assert not path.exists();path.write_text(text_csv(rows))
 path=out/'EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz';assert not path.exists();path.write_bytes(gzip.compress(text_csv(weekly).encode(),mtime=0))
 ranks=[]
 for target in sorted(catalog):
  eligible=[x for x in numeric if x['category']==target and x['headline_eligible'] and x['MAE'] is not None];groups={}
  for x in eligible:
   g=x['procedure_group'];previous=groups.get(g)
   if previous is None or (x['MAE'],x['method'],x['product'])<(previous['MAE'],previous['method'],previous['product']):groups[g]=x
  for i,x in enumerate(sorted(groups.values(),key=lambda x:(x['MAE'],x['method'],x['product']))):ranks.append({'rank':i+1,**x})
 path=out/'RESEARCH_POINT_PROCEDURE_RANKING_W1_7.csv';assert not path.exists();path.write_text(text_csv(ranks))
 summary=[]
 for target in sorted(catalog):
  eligible=[x for x in numeric if x['category']==target and x['headline_eligible']];point=[x for x in eligible if x['MAE'] is not None];prob=[x for x in eligible if target=='anytime_td'];best=min(point,key=lambda x:x['MAE']) if point else min(prob,key=lambda x:x['MSE_or_ATD_Brier'])
  mean=[x for x in eligible if x['product'] in ['mean','mean_objective_point']];s=side.get((target,best['method'],best['product']));leader=dict(best);leader['best_mean']=min(mean,key=lambda x:x['MSE_or_ATD_Brier']) if mean else None;leader['own_P1_sides']=s
  for a in ['over','under']:
   rows=[x for x in directions if x['category']==target and x[a+'_decided']>0];leader['observed_'+a+'_leader']=max(rows,key=lambda x:(x[a+'_hit_rate'],x[a+'_decided'])) if rows else None
  summary.append(leader)
 path=out/'OBSERVED_OBJECTIVE_LEADERS_POINT_V1.json.gz';assert not path.exists();path.write_bytes(gzip.compress(json.dumps({'state':'OBSERVED_DEVELOPMENT_LEADERS_NOT_RELEASE_DECISION','point':summary,'scope':'2026REGW1-7 samefrozenquery/labelcore; sourcequote timingunverified; counts not independentacrossproducts','probability_law_ranking':'Separatecompletedlawcomparison, pendingindependentQA','source_result_sha256':'5e30c74d98b07acc76cd54a7731570f4f9e4b5843c970a69ae30996cea00fe77'},separators=(',',':'),allow_nan=False).encode(),mtime=0))
 print(json.dumps({'point_product_rows':len(numeric),'own_side_rows':len(directions),'weekly_side_rows':len(weekly),'procedure_rank_rows':len(ranks),'source_scoring_runs_newly_created':0}))
if __name__=='__main__':main()
