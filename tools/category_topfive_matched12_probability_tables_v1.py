"""Public aggregate projection only: no football rows, fits, inference or new scoring."""
from pathlib import Path
import csv,gzip,hashlib,io,json,sys,zipfile,datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));import nfl_lab
from tools import category_topfive_matched12_storage_v1 as st
OUT=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/probability-projection'
def sha(b):return hashlib.sha256(b).hexdigest()
def loadgz(p):return json.loads(gzip.decompress(p.read_bytes()))
def csvzip(rows):
 keys=list(dict.fromkeys(k for r in rows for k in r));s=io.StringIO();w=csv.DictWriter(s,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows(rows);return gzip.compress(s.getvalue().encode(),mtime=0)
def fields(loss,prefix):
 if loss is None:return {prefix:None,prefix+'_state':'UNAVAILABLE'}
 return {prefix:loss.get('value'),prefix+'_state':loss.get('state'),prefix+'_n':loss.get('n'),prefix+'_positive_infinite_rows':loss.get('positive_infinite_rows',0)}
def weeks(v):return ','.join(map(str,v)) if isinstance(v,list) else str(v)
def sidefields(m):
 r={}
 for side in ['over','under']:
  a=m.get(side,{})
  for k in ['wins','losses','decided','hit_rate','DNP','unresolved']:r[side+'_'+k]=a.get(k)
  # An explicit saved status counter defines missing keys as zero occurrences.
  if 'all_statuses' in a:
   for key,state in [('DNP','DNP'),('unresolved','UNRESOLVED')]:r[side+'_'+key]=a['all_statuses'].get(state,0)
  r[side+'_pushes']=a.get('push',a.get('pushes',a.get('all_statuses',{}).get('PUSH',0) if 'all_statuses' in a else None))
 return r
def main():
 root=Path(st.prepare(ROOT)['allocation']['store_policy']['storage']['forward_root'])
 plan=loadgz(ROOT/'config/category-topfive-matched12-law-all-finalists-v1_1.json.gz')
 raw=(root/'research'/plan['run_id']/'AGGREGATES.json.gz').read_bytes();assert sha(raw)=='e7438e27d078daa8aceda5528a1f74cde59cf5db00cb81160ea735e05350c715';law=json.loads(gzip.decompress(raw))
 path=root/'research/matched12-exploratory-conditional-score-v1-1-20261031/SCORE_PACKAGE.zip';assert sha(path.read_bytes())=='25ef0445269af2a6134d16839c4f1a01e154e2c4dd1a57a9fc96ca3858b0a8b9'
 with zipfile.ZipFile(path) as z:market=json.loads(gzip.decompress(z.read('AGGREGATES.json.gz')))
 plan=loadgz(ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz')
 with zipfile.ZipFile(root/'research'/plan['run_id']/'RESULTS.zip') as z:
  body=z.read('AGGREGATES.json.gz');assert sha(body)=='2275410cce9a7ae7937f3b03ffc0e264534a4b55c09ab93fe9b7f2f15fcfee5c';point=json.loads(gzip.decompress(body))
 dist=[];prob=[];selection=[];mh=[];pairs=[]
 for x in law['distribution_scores']:
  for scope,m in [('PRIMARY_ROLES',x['primary_roles']),('ALL_ATTEMPTS_SECONDARY',x['all_attempts_secondary'])]:
   dist.append(dict(category=x['target'],method=x['method'],scope=scope,season=2026,weeks=weeks(m['weeks']),planned=m['planned'],scored=m['scored'],games=m['games'],interval80_coverage=m.get('interval80_coverage'),**fields(m['CRPS'],'CRPS'),**fields(m['negative_log_pmf'],'negative_log_pmf')))
 for x in law['probability_scores']:
  m=x['metrics'];prob.append(dict(category=x['target'],method=x['method'],arm=x['arm'],contract='HALF_SUM_THREE_OUTCOME_UNDER_PUSH_OVER_BRIER',weeks=weeks(m['weeks']),planned=m['planned'],scored=m['scored'],games=m['games'],**fields(m['Brier'],'Brier'),**fields(m['log_loss'],'log_loss')))
 for x in point['headline_numeric']['records']:
  if x['target']!='anytime_td' or x['scope']!='PREDECLARED_PRIMARY_COMMON_CORE' or x['product']=='probability_raw':continue
  m=x['metrics'];p=m['probability_scores'];prob.append(dict(category='anytime_td',method=x['method'],arm=x['product'],contract='BINARY_ANYTIME_RUSH_OR_RECEIVING_TD_BRIER',weeks='1,2,3,4,5,6,7',planned=m['planned'],scored=m['scored'],games=m['games'],Brier=p['Brier'],Brier_state='FINITE' if p['Brier'] is not None else 'UNAVAILABLE',Brier_n=m['scored'],Brier_positive_infinite_rows=0,**fields(p['log_loss'],'log_loss')))
 for x in law['selection_policies']:
  m=x['metrics'];o=m['over'];u=m['under'];n=o['decided']+u['decided'];w=o['wins']+u['wins']
  selection.append(dict(category=x['target'],method=x['method'],arm=x['arm'],policy=x['policy'],weeks=weeks(m['weeks']),offered_pool=m['opportunities'],unique_player_games=m['unique_player_games'],games=m['games'],decided=n,correct=w,hit_rate=w/n if n else None,abstain=m['abstain'],missing_law=m['missing_law'],**sidefields(m)))
 for x in market['fullboard_method_summaries']:
  # Cumulative full and same-prediction-pool views. The immutable source retains every weekly view.
  p=x['probability']
  for item in x['policies']:
   m=item['metrics'];mh.append(dict(category=x['target'],comparison_id=x['comparison_id'],arm=x['arm'],scope=x['scope'],policy=item['policy'],weeks=weeks(p['weeks']),offered_pool=m['offered_pool'],prediction_eligible=m['prediction_eligible'],selected=m['selected'],decided=m['decided'],correct=m['counts'].get('WIN',0),hit_rate=m['hit_rate'],coverage=m['coverage'],unresolved=m['counts'].get('UNRESOLVED',0),push=m['counts'].get('PUSH',0),DNP=m['counts'].get('DNP',0),Brier_all_pool=p['Brier']['value'],Brier_all_pool_state=p['Brier']['state'],Brier_all_pool_n=p['Brier']['n'],log_loss_all_pool=p['log_loss']['value'],log_loss_all_pool_state=p['log_loss']['state'],**sidefields(m)))
 for x in market['matched_control_comparisons']:
  for pair in x['pairwise']:
   m=pair['metrics'];b=m['Brier'];iv=b['intervals'];pairs.append(dict(category=x['target'],comparison_id=x['comparison_id'],candidate=pair['candidate'],control=pair['control'],pre_outcome_common_F_M_H=x['common_F_M_H_before_outcomes'],matched_prediction_rows=m['matched_prediction_rows'],matched_decisive=m['matched_decisive'],games=m['games'],week_clusters=m['weeks'],candidate_Brier=b['candidate']['value'],control_Brier=b['control']['value'],delta_state=b['candidate_minus_control']['state'],candidate_minus_control=b['candidate_minus_control'].get('value'),game_CI_lower=iv.get('game_id',{}).get('lower'),game_CI_upper=iv.get('game_id',{}).get('upper'),week_CI_lower=iv.get('week',{}).get('lower'),week_CI_upper=iv.get('week',{}).get('upper')))
 outputs={
  'DISTRIBUTION_PRODUCTS_W1_7.csv.gz':csvzip(dist),
  'PROBABILITY_PRODUCTS_W1_7.csv.gz':csvzip(prob),
  'FOOTBALL_PROBABILITY_SELECTIONS_W1_7.csv.gz':csvzip(selection),
  'EXPLORATORY_MARKET_SELECTIONS_W1_7.csv.gz':csvzip(mh),
  'EXPLORATORY_MARKET_PAIRED_BRIER_W1_7.csv.gz':csvzip(pairs),
  'LINE_AS_POINT_HEURISTIC_W1_7.csv.gz':csvzip(market['line_as_point']['results'])}
 # This is a projection, not a second predictive experiment or independent score recomputation.
 assert len(dist)==50 and len(prob)==48 and len(selection)==308
 summary=[]
 for target in sorted({x['target'] for x in law['distribution_scores']}):
  d=[x for x in dist if x['category']==target and x['scope']=='PRIMARY_ROLES' and x['weeks']=='1,2,3,4,5,6,7' and x['CRPS_state']=='FINITE'];p=[x for x in prob if x['category']==target and x['weeks']=='1,2,3,4,5,6,7' and x['Brier_state']=='FINITE'];s=[x for x in selection if x['category']==target and x['weeks']=='1,2,3,4,5,6,7' and x['policy']=='FULL_BOARD' and x['decided']]
  summary.append({'category':target,'CRPS_leader':min(d,key=lambda v:v['CRPS']) if d else None,'football_threshold_Brier_leader':min([x for x in p if x['arm']=='FOOTBALL'],key=lambda v:v['Brier'],default=None),'shrink_threshold_Brier_leader':min([x for x in p if x['arm']=='SHRINK_0_5'],key=lambda v:v['Brier'],default=None),'fullboard_probability_direction_observed_leader':max(s,key=lambda v:(v['hit_rate'],v['decided'])) if s else None})
 atd=[x for x in prob if x['category']=='anytime_td'];summary.append({'category':'anytime_td','Brier_leader_original_four':min(atd,key=lambda v:v['Brier']),'late_fifth':'SEPARATE_PENDING_OR_LATER_APPENDIX; original four unchanged','numeric_MAE':'NOT_APPLICABLE'})
 note={'version':'probability-aggregate-projection-v1','state':'PURE_PROJECTION_OF_COMPLETED_SCORES_NOT_NEW_SCORING','source_law_aggregate_sha256':'e7438e27d078daa8aceda5528a1f74cde59cf5db00cb81160ea735e05350c715','source_market_package_sha256':'25ef0445269af2a6134d16839c4f1a01e154e2c4dd1a57a9fc96ca3858b0a8b9','new_fits_inference_scoring_or_HTTP':0,'limitations':['Exposed current-vintage reconstruction; original seven-day timing assumption preserved.','Numeric law CRPS, half-three-outcome threshold Brier, conditional binary market Brier and binary ATD Brier are different products/scores.','DepthATT only Weeks1-6; excluded from full7 observed leader projection.','Conditional Over/Under subsets differ across procedures; no stitched hindsight strategy.','M/H quote timing and venue settlement unqualified; no authentic pregame, EV, ROI or live ranking activation.','Weekly and full uncertainty/reliability remain in source immutable aggregates, not removed.','Observed leaders are descriptive; no production selection or scientific qualification.'],'ATD_projection_audit':'Existing point projector had latent MAE-preference branch, but original ATD MAE=null and actual leader was correctly chosen by Brier. This projector explicitly forces ATD Brier; no score/leader correction or invalidation.','leaders':summary}
 outputs['OBSERVED_PROBABILITY_LEADERS_V1.json.gz']=gzip.compress(json.dumps(note,separators=(',',':'),allow_nan=False).encode(),mtime=0)
 sizes={k:len(v) for k,v in outputs.items()};total=sum(sizes.values());print(json.dumps({'prepared_output_bytes':total,'files':sizes,'rows':{'distribution':len(dist),'probability':len(prob),'law_selections':len(selection),'market_selections':len(mh),'market_pairs':len(pairs)}}))
 if '--write' not in sys.argv:return
 assert total+Path(__file__).stat().st_size+2048<=73728,'root-approved72KiB source/output/receipt allocation'
 OUT.mkdir(exist_ok=True)
 protocol={'version':'probability-projection-execution-v1','state':'ROOT_APPROVED_AGGREGATE_PROJECTION_ONLY','registered_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'allocation':'Prospective72KiB source+outputs under matched12 metadataV1.7; original30KiBestimate preserved','maximum_bytes':73728,'source_bytes':Path(__file__).stat().st_size,'prepared_output_bytes':total,'new_fits_inference_scoring_HTTP':0,'source_summaries_previously_inspected':True}
 protocol_path=OUT/'PROJECTION_EXECUTION_V1.json';assert not protocol_path.exists();protocol_path.write_text(json.dumps(protocol,separators=(',',':'))+'\n')
 for name,body in outputs.items():
  target=OUT/name;assert not target.exists();target.write_bytes(body)
 receipt={'version':note['version'],'state':'AGGREGATE_PROJECTION_SAVED_PUBLICATION_PENDING','source_sha256':sha(Path(__file__).read_bytes()),'outputs':{k:{'bytes':len(v),'sha256':sha(v)} for k,v in outputs.items()},'new_fits_scoring':0}
 (OUT/'PROJECTION_RECEIPT_V1.json').write_text(json.dumps(receipt,separators=(',',':'))+'\n')
if __name__=='__main__':main()
