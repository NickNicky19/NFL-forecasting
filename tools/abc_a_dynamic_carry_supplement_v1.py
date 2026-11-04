"""Coverage, same-law point tradeoffs, proper-score uncertainty, private CSV."""
import collections,csv,gzip,io,json,math,os,sys,time,resource,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import abc_a_dynamic_carry_wave_v1 as base
OUT=ROOT/'reports/abc-championship/predictive-improvement-01';V3=OUT/'completion-v3'
def main():
 import numpy as np,pandas as pd,pyarrow as pa
 from tools import category_topfive_matched12_storage_v1 as st
 pa.set_cpu_count(1);pa.set_io_thread_count(1);cpu=time.process_time();wall=time.monotonic()
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 d=store.forward_root/'research'/'ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2';receipt=json.loads((V3/'SCORING_RECEIPT_V1.json').read_text());store.validate_reference(d/'GRADED_SCORECARD_V1.zip',receipt['sha256'])
 with zipfile.ZipFile(d/'GRADED_SCORECARD_V1.zip')as z:numeric=json.loads(gzip.decompress(z.read('NUMERICAL_ROWS.json.gz')));rows=json.loads(gzip.decompress(z.read('OFFER_GRADE_ROWS.json.gz')))
 lookup={(r['season'],r['game_id'],r['player_id'],r['arm']):r for r in numeric};index={(r['arm'],r['policy'],r['opportunity_key']):r for r in rows}
 coverage=[];offered=[];trade=[]
 for arm in sorted({r['arm']for r in rows}):
  for policy in ['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW','P2_EXACT_LAW_CONF55']:
   rr=[r for r in rows if r['arm']==arm and r['policy']==policy];dec=[r for r in rr if r['status']in ['WIN','LOSS']];fb=[r for r in dec if r['fallback']];non=[r for r in dec if not r['fallback']]
   coverage.append({'arm':arm,'policy':policy,'eligible':len(rr),'selected':sum(r['selected_side']in ['OVER','UNDER']for r in rr),'decided':len(dec),'unavailable':sum(r['status']=='UNAVAILABLE_FORECAST'for r in rr),'abstentions':sum(r['status']=='ABSTAIN'for r in rr),'unknown':sum(r['status']=='UNKNOWN_PARTICIPATION'for r in rr),'fallback_decided':len(fb),'fallback_wins':sum(r['status']=='WIN'for r in fb),'nonfallback_decided':len(non),'nonfallback_wins':sum(r['status']=='WIN'for r in non)})
   if not policy.startswith('P1'):continue
   good=[r for r in rr if r['appearance']=='PLAYED'and r['actual']is not None and r['point']is not None];err=np.array([r['point']-r['actual']for r in good]);ae=np.abs(err)
   offered.append({'arm':arm,'policy':policy,'eligible':len(rr),'scored':len(good),'MAE':float(ae.mean())if len(ae)else None,'RMSE':float(np.sqrt(np.mean(err**2)))if len(ae)else None,'bias':float(err.mean())if len(ae)else None,'strict_lt1':int((ae<1).sum()),'inclusive_le1':int((ae<=1).sum()),'p95_AE':float(np.quantile(ae,.95))if len(ae)else None,'point_rounding':'NONE'})
  mm=[]
  for r in rows:
   if r['arm']!=arm or r['policy']!='P1_MEAN'or r['status']not in ['WIN','LOSS']:continue
   s=index.get((arm,'P1_MEDIAN',r['opportunity_key']))
   if s and s['status']in ['WIN','LOSS']and r['selected_side']!=s['selected_side']:mm.append((r,s))
  trade.append({'arm':arm,'mean_median_disagreements':len(mm),'mean_correct_when_disagree':sum(r['status']=='WIN'for r,s in mm),'median_correct_when_disagree':sum(s['status']=='WIN'for r,s in mm),'interpretation':'Different products of same law; mean direction need not match more-likely side.'})
 def ci(rr,key):
  grouped=collections.defaultdict(list)
  for r in rr:grouped[str(r[key])].append(r['delta'])
  if len(grouped)<2:return {'clusters':len(grouped),'low':None,'high':None}
  vals=list(grouped.values());s=np.array([sum(x)for x in vals]);n=np.array([len(x)for x in vals]);rng=np.random.default_rng(1703);ix=rng.integers(len(vals),size=(1000,len(vals)));x=s[ix].sum(1)/n[ix].sum(1);return {'clusters':len(vals),'low':float(np.quantile(x,.025)),'high':float(np.quantile(x,.975))}
 paired=[]
 for left,right in [('A1_BACKFIELD_CDF_ROLE_INPUTS','A0_BACKFIELD_CDF'),('A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION')]+[(a,'NEUTRAL_50_50')for a in ['A0_BACKFIELD_CDF','A1_BACKFIELD_CDF_ROLE_INPUTS','A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION']]:
  rr=[]
  for r in rows:
   if r['arm']!=left or r['policy']!='P2_EXACT_LAW'or r['actual']is None or r['appearance']!='PLAYED'or r['p_over']is None or r['line']%1!=.5:continue
   s=index.get((right,'P2_EXACT_LAW',r['opportunity_key']))if right!='NEUTRAL_50_50'else None
   if right!='NEUTRAL_50_50'and(s is None or s['p_over']is None):continue
   y=int(r['actual']>r['line']);lb=(r['p_over']-y)**2;rb=(s['p_over']-y)**2 if s else .25
   rr.append({'game_id':r['game_id'],'week':r['week'],'delta':lb-rb})
  paired.append({'left':left,'right':right,'n':len(rr),'Brier_change_left_minus_right':sum(r['delta']for r in rr)/len(rr)if rr else None,'game_CI':ci(rr,'game_id'),'week_CI':ci(rr,'week')})
 _,_,g,_=base.sources()
 with zipfile.ZipFile(io.BytesIO(base.pin(g['offers'])))as z:offers=pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
 offers=offers.loc[offers.target.eq('rush_att')&offers.position.eq('RB')];offer={r['opportunity_key']:r for r in offers.to_dict('records')}
 source=[]
 for (week,stream),gg in offers.groupby(['week','source_stream']):source.append({'week':int(week),'source_stream':stream,'offers':len(gg),'listed_two_sided_numeric_prices':int(gg.valid_two_sided_prices.sum()),'qualified_pregame_market_probabilities':int(gg.market_probability_eligible.sum()),'quote_timing_states':gg.quote_timing_status.fillna('MISSING').value_counts().to_dict(),'venue_settlement_states':gg.venue_settlement_status.fillna('MISSING').value_counts().to_dict()})
 fields=['season','week','game_id','player_id','arm','policy','evidence','point','mean','median','p_over','p_under','p_push','original_line','selected_side','actual','absolute_error','statistical_result','venue_settlement','book_id','original_price','quote_time','quote_timing_status','source_stream','information_cutoff','source_max','generation_UTC','original_issue_UTC','fallback','source_forecast_sha256']
 text=io.StringIO();writer=csv.DictWriter(text,fieldnames=fields);writer.writeheader()
 for r in rows:
  if r['arm'].startswith('ALWAYS_'):continue
  f=lookup.get((r['season'],r['game_id'],r['player_id'],r['arm']),{});o=offer[r['opportunity_key']];price=o['decimal_over']if r['selected_side']=='OVER'else o['decimal_under']if r['selected_side']=='UNDER'else None
  writer.writerow({'season':r['season'],'week':r['week'],'game_id':r['game_id'],'player_id':r['player_id'],'arm':r['arm'],'policy':r['policy'],'evidence':'RETROSPECTIVE_TIMING_UNVERIFIED_RULE_REPLAY','point':r['point'],'mean':f.get('mean'),'median':f.get('median'),'p_over':r['p_over'],'p_under':r['p_under'],'p_push':r['p_push'],'original_line':r['line'],'selected_side':r['selected_side'],'actual':r['actual'],'absolute_error':abs(r['point']-r['actual'])if r['point']is not None and r['actual']is not None else None,'statistical_result':r['status'],'venue_settlement':'UNRESOLVED_CONTRACT_NOT_VERIFIED','book_id':o['book_id']if pd.notna(o['book_id'])else None,'original_price':float(price)if price is not None and pd.notna(price)else None,'quote_time':str(o['source_quote_time'])if pd.notna(o['source_quote_time'])else None,'quote_timing_status':o['quote_timing_status'],'source_stream':o['source_stream'],'information_cutoff':f.get('cutoff_utc'),'source_max':f.get('source_information_max_UTC'),'generation_UTC':f.get('generation_UTC'),'original_issue_UTC':f.get('original_issued_UTC'),'fallback':r['fallback'],'source_forecast_sha256':f['full_law_reference']['artifact_sha256']if f.get('full_law_reference')else None})
 b=gzip.compress(text.getvalue().encode(),mtime=0);path=d/'PREDICTIONS_ACTUALS_AND_DIRECTIONS_V1.csv.gz';store.write_bytes(path,b);store.validate_reference(path,base.sha(b));usage=store.verify_retained_checkpoint()
 report={'state':'EXECUTED_FROM_SAVED_ROWS_NO_FITS','coverage_and_fallback':coverage,'offered_point_errors':offered,'same_model_mean_median_tradeoffs':trade,'paired_full_board_Brier':paired,'offer_source_readiness':source,'private_readable_scorecard':{'artifact_id':'A-DYNAMIC-CARRY-READABLE-DIRECTIONS-V1','sha256':base.sha(b),'bytes':len(b),'rows':sum(not r['arm'].startswith('ALWAYS_')for r in rows),'readback':'PASS_APPROVED_STORE','offhost':'NOT_VERIFIED'},'resources':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'new_fits':0,'new_inference':0},'retained_headroom_bytes':usage['wave_retained_headroom_bytes'],'limits':['Listed prices remain quote/settlement-unqualified; no EV/ROI inference.','BinaryBrier is not interchangeable with three-state sumBrier.','Own Over/Under pools differ; no retrospective side-splicing.']}
 (OUT/'SUPPLEMENTAL_RESULTS_V1.json').write_bytes(base.enc(report));print(json.dumps({'state':'PASS','private_readable_rows':report['private_readable_scorecard']['rows'],'private_bytes':len(b),'new_fits':0}))
if __name__=='__main__':main()
