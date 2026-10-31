"""Compare completed aggregate P1/P2 policies, preserving capacity and population."""
from pathlib import Path
import csv,gzip,hashlib,io,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import nfl_lab
from tools import category_topfive_matched12_storage_v1 as st
OUT=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/probability-projection'
def sha(b):return hashlib.sha256(b).hexdigest()
def csv_gz(rows):
 b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(rows);return gzip.compress(b.getvalue().encode(),mtime=0)
def normalize(target,method,product,track,policy,m,weekly,version,full_n,complete):
 p='TOP_'+policy.split('_')[1] if policy.startswith('TOP_') else 'ABSTAIN_0_55' if policy.startswith('ABSTAIN_') else 'FULL_BOARD'
 def selected(x):return x['opportunities']-x.get('no_lean',x.get('abstain',0))-x.get('missing_offer_or_prediction',x.get('missing_law',0))
 over,under=m['over'],m['under'];n=over['decided']+under['decided'];wins=over['wins']+under['wins'];cap=','.join(str(selected(weekly.get(w,{'opportunities':0}))) for w in range(1,8));ci=m.get('hit_rate_intervals',{})
 r=dict(category=target,track=track,method=method,product=product,procedure_version=version,policy=p,source_policy=policy,full_board_offers=full_n,selected_opportunities=selected(m),capacity_by_week=cap,correct=wins,decided=n,hit_rate=wins/n if n else None,full7_method_eligible=complete,games=m.get('independent_decided_games',m.get('games')),game_CI_lower=ci.get('game_id',{}).get('lower'),game_CI_upper=ci.get('game_id',{}).get('upper'),week_CI_lower=ci.get('week',{}).get('lower'),week_CI_upper=ci.get('week',{}).get('upper'),no_lean=m.get('no_lean',m.get('abstain',0)),missing_prediction=m.get('missing_offer_or_prediction',m.get('missing_law',0)))
 for side,a in [('over',over),('under',under)]:
  for k in ['wins','losses','decided','hit_rate','DNP','unresolved']:r[side+'_'+k]=a.get(k)
  r[side+'_pushes']=a.get('pushes',a.get('push',0))
 return r
def main():
 root=Path(st.prepare(ROOT)['allocation']['store_policy']['storage']['forward_root']);plan=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()))
 with zipfile.ZipFile(root/'research'/plan['run_id']/'RESULTS.zip') as z:body=z.read('AGGREGATES.json.gz')
 assert sha(body)=='2275410cce9a7ae7937f3b03ffc0e264534a4b55c09ab93fe9b7f2f15fcfee5c';a=json.loads(gzip.decompress(body));point_plan=plan;plan=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-law-all-finalists-v1_1.json.gz').read_bytes()));assert all(point_plan['offers'][k]==plan['offers'][k] for k in ['sha256','member','member_sha256']),'different primary offer-source contract';b=(root/'research'/plan['run_id']/'AGGREGATES.json.gz').read_bytes();assert sha(b)=='e7438e27d078daa8aceda5528a1f74cde59cf5db00cb81160ea735e05350c715';law=json.loads(gzip.decompress(b))
 eligible={(x['target'],x['method'],x['product']):x['headline_eligible'] for x in a['headline_numeric']['records'] if x['scope']=='PREDECLARED_PRIMARY_COMMON_CORE'};point=a['recorded_line_point_decisions'];full={(x['target'],x['method'],x['product']):x for x in point['records'] if x['policy']=='FULL_PRIMARY_ROSTER_INTERSECTION_RECORDED_BOARD'};rows=[]
 for x in point['records']:
  key=x['target'],x['method'],x['product'];base=full[key]['metrics'];v=a['catalog'][x['target']][x['method']];version=v.get('product_procedure_versions',{}).get(x['product'],v['procedure_version']);complete=eligible.get(key,False) and base['weeks']==list(range(1,8)) and base['missing_prediction_rows']==0
  rows.append(normalize(*key,'P1_POINT_GAP',x['policy'],x['metrics'],{int(w['week']):w['metrics'] for w in x['weekly']},version,base['opportunities'],complete))
 p2full={(x['target'],x['method'],x['arm']):x for x in law['selection_policies'] if x['policy']=='FULL_BOARD'}
 for x in law['selection_policies']:
  if x['policy'].startswith('ALWAYS_'):continue
  key=x['target'],x['method'],x['arm'];base=p2full[key]['metrics'];v=a['catalog'][x['target']][x['method']];version=v['procedure_version']+';'+law['version']+';'+x['arm'];complete=base['weeks']==list(range(1,8)) and base['missing_law']==0
  rows.append(normalize(*key,'P2_THRESHOLD_PROBABILITY',x['policy'],x['metrics'],{int(w['week']):w['metrics'] for w in x['weekly']},version,base['opportunities'],complete))
 # One always-side benchmark per category, independent of a fitted model.
 for x in point['always_side_controls']:
  m=x['metrics'];row=normalize(x['target'],x['control'],'CONSTANT_SIDE_NO_PROBABILITY','CONTROL',x['control'],m,{},'ORIGINAL_REGISTERED_ALWAYS_SIDE',m['opportunities'],m['weeks']==list(range(1,8)));row['capacity_by_week']='CONTROL_FULL_POOL';rows.append(row)
 base_pools={}
 for r in rows:
  if r['track']=='CONTROL':base_pools.setdefault(r['category'],set()).add((r['full_board_offers'],r['decided']))
 assert all(len(v)==1 for v in base_pools.values()),'inconsistent always-side pool'
 # No raw-row joining or rescore: identical registered source board/query policy;
 # distinct selected sets are explicitly not paired accuracy observations.
 groups={}
 for r in rows:
  if not r['full7_method_eligible'] or not r['decided'] or r['track']=='CONTROL':continue
  key=(r['category'],r['policy'],r['full_board_offers'],r['capacity_by_week'],r['decided'],r['over_pushes']+r['under_pushes'],r['over_unresolved']+r['under_unresolved'])
  groups.setdefault(key,[]).append(r)
 leaders=[]
 for key,values in sorted(groups.items()):
  best=max(values,key=lambda x:(x['hit_rate'],x['correct'],x['track']=='P1_POINT_GAP',x['method'],x['product']));ties=[x['track']+':'+x['method']+':'+x['product'] for x in values if x['hit_rate']==best['hit_rate']];leaders.append({**best,'tied_observed_leaders':' | '.join(ties),'competing_product_policies':len(values),'comparison':'EQUAL_REGISTERED_CAPACITY_AND_DECIDED_COUNT_NOT_IDENTICAL_SELECTED_CASES'})
 controls=[x for x in rows if x['track']=='CONTROL'];complete=[]
 for t in sorted(base_pools):
  pool,n=next(iter(base_pools[t]));c=[x for x in rows if x['category']==t and x['full7_method_eligible'] and x['policy']=='FULL_BOARD' and x['full_board_offers']==pool and x['selected_opportunities']==pool and x['decided']==n]
  if c:
   best=max(c,key=lambda x:(x['hit_rate'],x['correct'],x['track']=='CONTROL',x['method'],x['product']));complete.append({**best,'tied_observed_leaders':' | '.join(x['track']+':'+x['method']+':'+x['product'] for x in c if x['hit_rate']==best['hit_rate']),'competing_full_coverage_product_policies':len(c)})
 outputs={'COMPLETE_POLICY_CAPACITY_LEADERS_V1.csv.gz':csv_gz(leaders),'COMPLETE_POLICY_FULL_COVERAGE_AND_CONTROLS_V1.csv.gz':csv_gz(complete+controls)}
 text=['## Complete selection policies: P1 points versus P2 probabilities','','This is a pure projection of completed exposed 2026 Weeks 1–7 aggregates, not a new forecast, scored experiment or deployed strategy. P1 and P2 use the full recorded board intersected with their registered roster queries, including offered role exceptions. This differs from the numerical-MAE primary-position population and the new flat control’s separately reported primary-role subset.','','The equal-capacity table groups by category, policy, original full-board pool, the seven weekly selection counts, decisive count, pushes and unresolved outcomes. Equal capacity does **not** mean identical selected players; the conditional percentages are descriptive, not a new paired accuracy test. Existing source comparisons/uncertainty remain available. Partial Depth-CDF Weeks 1–6 is excluded from full-seven-week leaders.','','| Category | Highest observed full-coverage policy (including always-side controls) | Correct / decided | Own Over | Own Under |','|---|---|---:|---:|---:|']
 for x in complete:text.append('| '+x['category']+' | '+x['track']+' '+x['method']+' '+x['product']+' | '+str(x['correct'])+'/'+str(x['decided'])+' | '+str(x['over_wins'])+'/'+str(x['over_decided'])+' | '+str(x['under_wins'])+'/'+str(x['under_decided'])+' |')
 text+=['','[Every observed leader within equal capacity](COMPLETE_POLICY_CAPACITY_LEADERS_V1.csv.gz) separates full board, Top 6, Top 10, Top 20 and the P2 0.55 abstaining rule. P1 ranks unrounded absolute point gap; P2 ranks frozen decisive-side probability. These ranking mechanisms remain different. A P1 0.55 probability rule is unsupported; points do not imply probabilities. The earlier IQR abstention input was unavailable, so no substitute was fabricated.','','[Full-coverage leaders and the complete always-Over/always-Under controls](COMPLETE_POLICY_FULL_COVERAGE_AND_CONTROLS_V1.csv.gz) show every denominator. Full coverage here means all registered offered opportunities selected, with the same decisive count as the always-side controls; policies with abstention are preserved in their separate capacity groups, not discarded. Models may still use registered fallbacks.','','The maximum is selected descriptively after examining this development panel. It is not an earlier-trained selector, is not a proposal to stitch the best Over and Under models together, and is not a production policy decision. Ties and small samples remain visible. No venue settlement, prices, paper return or profitability is inferred. Anytime TD has a separate binary event contract; chart-PPR and targets have no compatible ordinary offered board. Their statistical/probability research remains separate.','','All complete policy records and their weekly counts remain in the immutable source aggregates. No original forecasts, lines, selected sides, model identities or rules changed.']
 outputs['COMPLETE_POLICY_COMPARISON_V1.md']=('\n'.join(text)+'\n').encode();sizes={k:len(v) for k,v in outputs.items()};print(json.dumps({'output_bytes':sum(sizes.values()),'source_bytes':Path(__file__).stat().st_size,'files':sizes,'all_policy_outputs_compared':len(rows),'equal_capacity_leaders':len(leaders),'full_coverage_leaders':len(complete)}));assert Path(__file__).stat().st_size+sum(sizes.values())+4096<=40960,'root-approved40KiB total completion bound'
 if '--write' in sys.argv:
  for name,b in outputs.items():p=OUT/name;assert not p.exists();p.write_bytes(b)
  receipt={'version':'complete-policy-aggregate-projection-v1','state':'COMPLETE_AGGREGATE_PROJECTION_PUBLICATION_PENDING','source_sha256':sha(Path(__file__).read_bytes()),'source_main_aggregate_sha256':'2275410cce9a7ae7937f3b03ffc0e264534a4b55c09ab93fe9b7f2f15fcfee5c','source_law_aggregate_sha256':'e7438e27d078daa8aceda5528a1f74cde59cf5db00cb81160ea735e05350c715','outputs':{k:{'bytes':len(v),'sha256':sha(v)} for k,v in outputs.items()},'existing_product_policy_rows_projected':len(rows),'equal_capacity_strata':len(leaders),'new_fits_inference_scoring_or_bootstrap':0,'interpretation':'Descriptive maxima across exposed existing procedures, not new advance selector or production release'};(OUT/'COMPLETE_POLICY_RECEIPT_V1.json').write_text(json.dumps(receipt,separators=(',',':'))+'\n')
if __name__=='__main__':main()
