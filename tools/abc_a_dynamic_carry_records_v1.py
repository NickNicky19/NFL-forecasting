"""Generate canonical records/readable tables from retained aggregate results."""
import csv,datetime,hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'reports/abc-championship/predictive-improvement-01';R=ROOT/'reports/opportunity-four'
sys.path.insert(0,str(ROOT))
from nfl_lab.opportunity_registry_storage_v1 import read_document,write_document
def load(p):return read_document(p)
def write(p,d):write_document(p,d)
def score(x=None,reason='Unsupported for this product/panel; see linked native record.'):
 return {'state':'FINITE','value':x,'reason':None}if x is not None else{'state':'UNAVAILABLE','value':None,'reason':reason}
def main():
 import sys
 sys.path.insert(0,str(ROOT));from nfl_lab.category_topfive_opportunity_registry import SCORE_NAMES
 num=load(O/'completion-v3/NUMERICAL_RESULTS_V1.json')['scores'];rb=load(O/'completion-v3/ACTUAL_LINE_RESULTS_V1.json');full=load(O/'FULL_BOARD_DIRECT_RESULTS_V1.json');pairs=load(O/'MATCHED_ANALYSIS_RESULTS_V1.json');sup=load(O/'SUPPLEMENTAL_RESULTS_V1.json')
 mapping={'A0_BACKFIELD_CDF':'m:BACKFIELD_CDF','A1_BACKFIELD_CDF_ROLE_INPUTS':'m:A_DYNAMIC_ROLE_CDF_V1','A2_DYNAMIC_ALLOCATION':'m:A_DYNAMIC_ALLOCATION_V1','S0_RECENCY_ALLOCATION':'m:A_RECENCY_ALLOCATION_V1','STORED_COUNT_A_MEAN_CONTROL':'m:COUNT_A','ALWAYS_OVER':'m:ABC_ALWAYS_OVER','ALWAYS_UNDER':'m:ABC_ALWAYS_UNDER'}
 methods=load(R/'METHOD_REGISTRY.json');byid={m['method_id']:m for m in methods['records']}
 for mid in ['m:BACKFIELD_CDF','m:COUNT_A']:
  if 'exact_line_probability'not in [x['output_id']for x in byid[mid]['outputs']]:byid[mid]['outputs'].append({'output_id':'exact_line_probability','functional':'probability','primary_score':'Brier',**({'state':'UNSUPPORTED_NO_PROCEDURE','reason':'No distribution is invented from CountAmean.'}if mid=='m:COUNT_A'else{'state':'RETAINED_LAW_NEW_EXACT_LINE_SCORE_VIEW'})})
 for side in ['OVER','UNDER']:
  mid='m:ABC_ALWAYS_'+side
  if mid not in byid:
   m={'method_id':mid,'original_id':'ALWAYS_'+side,'family':'Deterministic selection control; not learned model','procedure_version':'ABC-ACTUAL-PROP-CHAMPIONSHIP-v2-C-1','algorithm':'Select constant supported side','formula':'Always select '+side+' at same original line; unknown outcomes remainunknown.','outputs':[],'selection_outputs':[{'type':'DIRECTION_SELECTION','side':side}],'code':[{'record':'../abc-championship/predictive-improvement-01/PROTOCOL_V1.json','scope':'Predeclared common controls; zero footballfits'}],'feature_policy':'Same eligible offers/outcomes; no playercontext, probability or numeric point invented.','training_rule':'NOT_APPLICABLE','aliases':[],'procedure_kind':'CONTROL_NOT_FORECAST_LEARNER'};methods['records'].append(m);byid[mid]=m
 write(R/'METHOD_REGISTRY.json',methods)
 experiments=load(R/'EXPERIMENT_REGISTRY.json');exp=next(e for e in experiments['records']if e['experiment_id']=='e:ABC-PREDICTIVE-IMPROVEMENT-01-A-v1');exp['method_ids']=sorted(set(exp['method_ids'])|set(mapping.values()));exp['status']='COMPLETED';exp['completion_scope']='Named bounded wave only:2026W1-7 and2025W1-8numerical; actual-line2026W1-7full335direct/RB239structured. W8, olderoriginfits, authenticcapture/production remainopen.';exp['artifacts']=['../abc-championship/predictive-improvement-01/README.md','ABC_DYNAMIC_CARRY_SELECTION_RESULTS_V1.json','../abc-championship/predictive-improvement-01/completion-v3/NUMERICAL_RESULTS_V1.json','../abc-championship/predictive-improvement-01/FULL_BOARD_DIRECT_RESULTS_V1.json'];write(R/'EXPERIMENT_REGISTRY.json',experiments)
 # Preserve failed parent runs; scoring is a separately completed zero-fit run.
 runid='r:ABC-A-dynamic-carry-scoring-v3';events=[json.loads(x)for x in(R/'RUN_EVENTS.jsonl').read_text().splitlines()if x]
 def addrun(r):
  if r['run_record_id']not in {x['run_record_id']for x in events}:
   events.append(r)
   with(R/'RUN_EVENTS.jsonl').open('a')as f:f.write(json.dumps(r)+'\n')
 def event(ident,status,start,finish,resources,version=1,parent=None):
  return {'run_record_id':ident+'@'+str(version),'run_id':ident,'run_version':version,'supersedes_run_record_id':parent,'experiment_id':exp['experiment_id'],'original_id':ident,'status':status,'origin':'EXECUTED_HERE','start':{'record':start},'finish':{'record':finish},'resources':resources,'software_checks':['../abc-championship/predictive-improvement-01/INDEPENDENT_RESULT_VERIFICATION_V1.json'],'evidence':{'label':'REPRODUCED_FROM_DATA','original_record':finish},'publication_subject':'p:ABC-A-dynamic-carry-v1'}
 addrun(event('r:ABC-A-dynamic-carry-runtime-v2','FAILED','../abc-championship/predictive-improvement-01/runtime-v2/START_V1.json','../abc-championship/predictive-improvement-01/runtime-v2/EXECUTION_FAILURE_V2.json',{'new_fit_attempts':2,'returned_fits':2,'saved_forecast_rows':9912,'newly_inferred_rows':7745,'CPU_seconds':None,'CPU_missing_reason':'V2failurehandler omitted total counters; not zero, original1800cap retained.'},2,'r:ABC-A-dynamic-carry-runtime-v2@1'))
 addrun(event(runid,'COMPLETED','../abc-championship/predictive-improvement-01/COMPLETION_REGISTRATION_V3.json','../abc-championship/predictive-improvement-01/completion-v3/COMPLETION_COUNTERS_V3.json',{'new_fits':0,'new_inference':0,'reused_saved_forecasts':9912,'numeric_cells':152,'selection_cells':176,'CPU_seconds':84.333699889}))
 addrun(event('r:ABC-A-dynamic-carry-matched-analysis-v1','COMPLETED','../abc-championship/predictive-improvement-01/ANALYSIS_PROTOCOL_V1.json','../abc-championship/predictive-improvement-01/MATCHED_ANALYSIS_RESULTS_V1.json',pairs['resources']))
 addrun(event('r:ABC-A-dynamic-carry-supplement-v1','COMPLETED','../abc-championship/predictive-improvement-01/SUPPLEMENTAL_PROTOCOL_V1.json','../abc-championship/predictive-improvement-01/SUPPLEMENTAL_RESULTS_V1.json',sup['resources']))
 addrun(event('r:ABC-A-carry-full-board-extension-v1','COMPLETED','../abc-championship/predictive-improvement-01/FULL_BOARD_EXTENSION_PROTOCOL_V1.json','../abc-championship/predictive-improvement-01/FULL_BOARD_DIRECT_RESULTS_V1.json',{'new_fits':0,'new_inference':192,'CPU_seconds':full['CPU_seconds'],'wall_seconds':full['wall_seconds'],'RSS_bytes':full['RSS_bytes']}))
 addrun(event('r:ABC-A-independent-verification-output-v1','RESUMABLE','../abc-championship/predictive-improvement-01/INDEPENDENT_RESULT_VERIFICATION_V1.json','../abc-championship/predictive-improvement-01/INDEPENDENT_RESULT_VERIFICATION_V1.json',{'new_fits':0,'CPU_seconds':None,'CPU_bound':180,'state':'OUTPUT_UNAVAILABLE_NOT_REFUNDED'}))
 addrun(event('r:ABC-A-independent-verification-captured-v2','COMPLETED','../abc-championship/predictive-improvement-01/INDEPENDENT_RESULT_VERIFICATION_V1.json','../abc-championship/predictive-improvement-01/INDEPENDENT_RESULT_VERIFICATION_V1.json',{'new_fits':0,'new_inference':0,'CPU_seconds':31.011,'wall_seconds':31.012}))
 results=load(R/'ALL_RESULTS.json');known={r['result_id']for r in results['records']};newids=[];subject='p:ABC-A-dynamic-carry-v1'
 comparison=lambda season,weeks,pop,kind:{'target':'rush_att','season':season,'weeks':weeks,'population_id':pop,'outcome_version':'qualified-matched12-2026-v1'if season==2026 else'accepted-provider-history-2025-current-vintage','horizon_id':'HISTORICAL_LEFT_LIMIT_KICKOFF_RECONSTRUCTION','source_policy_id':'CURRENT_VINTAGE_SEVEN_DAY_HISTORY_RECONSTRUCTION','fallback_policy_id':'REGISTERED_COMPLETE_SYSTEM_PER_METHOD_FALLBACKS','evidence_kind':'EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION','comparison_set_id':kind+'-'+str(season)+'-'+','.join(map(str,weeks))}
 def common_record(rid,method,output,comp,scores,cov,source):
  return {'result_id':rid,'run_id':runid,'method_id':method,'output_id':output,'comparison':comp,'scores':scores,'coverage':cov,'evidence_label':'NEW_EXPERIMENT','validity':'VALID','missingness':{'reason':'Unknown participation/missing statistics notzero; unsupportedoutputs null.'},'comparator':{'method':'m:BACKFIELD_CDF','scope':'Exact same declared population/product; constants andCountA in linked selectiontable'},'uncertainty':{'record':'../abc-championship/predictive-improvement-01/MATCHED_ANALYSIS_RESULTS_V1.json','clusters':'game/week','exposed_development':True},'adverse':['Structuredallocation loses; A1changes reverse byseason/population; no claim ofpermanentwinner.'],'private_evidence':{'manifest_id':'A-DYNAMIC-CARRY-SCORECARD-V1','forecast_artifact_sha256':'91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208','route':'Retained owner approved authenticated private restoration; restricted fields are not public.','offhost_restore':'NOT_VERIFIED'},'readiness':{'research':'SCORED_RECONSTRUCTION','future_query':'NOT_QUALIFIED','operational_admission':'NOT_VERIFIED','capture':'NO_NEW_PREGAME_CAPTURE','live':'NO_NEW_A_RELEASE'},'source_record':source,'publication_subject':subject}
 for i,r in enumerate(num):
  weeks=r['actual_weeks']if r['week']=='ALL'else[r['week']];rid=f"v:ABC-A-dcarry:num:{r['season']}:{r['arm']}:{r['product']}:{r['week']}";n=r['scored'];ss={k:score()for k in SCORE_NAMES}
  for k in ['MAE','MSE','RMSE','bias']:ss[k]=score(r[k],r.get('null_score_reason')or'No supported point product.')
  ss['p95_AE']=score(r['p95_absolute_error']);ss['strict_error_lt1']=score(r['strict_lt1']/n if n else None);ss['inclusive_error_le1']=score(r['inclusive_le1']/n if n else None);ss['exact_count_rate']=score(r['exact_unrounded']/n if n and r['product']=='median'else None,'No registered rounded integer recipe for fractional mean.')
  record=common_record(rid,mapping[r['arm']],r['product'],comparison(r['season'],weeks,'RB_ROSTER_'+str(r['expected']),'A_DYNAMIC_CARRY_ROSTER'),ss,{'planned':r['expected'],'scored':n,'games':r['games'],'weeks':len(weeks)},f'../abc-championship/predictive-improvement-01/completion-v3/NUMERICAL_RESULTS_V1.json#/scores/{i}')
  record['missingness'].update(outcome_states=r['outcome_states'],unsupported_product_rows=r['unsupported_product_rows']);record['validity']='UNVERIFIED'if not n else'VALID'
  if rid not in known:results['records'].append(record);newids.append(rid);known.add(rid)
 for i,r in enumerate(rb['full_board_probability_scores']):
  week=r['week'];weeks=list(range(1,8))if week=='ALL'else[week];rid=f"v:ABC-A-dcarry:prob:2026:{r['arm']}:{week}";ss={k:score()for k in SCORE_NAMES};ss['Brier']=score(r['Brier'],'Point-only CountA has no supportedlaw.');ss['log_loss']=score(r['logloss'],'Point-only CountA has no supportedlaw.');eligible=next(s['eligible']for s in rb['scores']if s['arm']==r['arm']and s['policy']=='P2_EXACT_LAW'and s['week']==week)
  record=common_record(rid,mapping[r['arm']],'exact_line_probability',comparison(2026,weeks,'RB_ORIGINAL_LINE_HALF_INTEGER','A_DYNAMIC_CARRY_RB_OFFERS'),ss,{'planned':eligible,'scored':r['scored'],'games':next(s['games']for s in rb['scores']if s['arm']==r['arm']and s['policy']=='P2_EXACT_LAW'and s['week']==week),'weeks':len(weeks)},f'../abc-championship/predictive-improvement-01/completion-v3/ACTUAL_LINE_RESULTS_V1.json#/full_board_probability_scores/{i}')
  if not r['scored']:record['validity']='UNVERIFIED'
  record['calibration']=r['reliability'];record['adverse'].append('AllsupportedRB laws lose neutralbinary Brier0.25.')
  if rid not in known:results['records'].append(record);newids.append(rid);known.add(rid)
 write(R/'ALL_RESULTS.json',results)
 selection=[]
 for panel,data in [('RB_239',rb['scores']),('QB_RB_WR_335',full['scores'])]:
  for i,r in enumerate(data):
   selection.append({'result_id':f"ou:ABC-A-dcarry:{panel}:{r['arm']}:{r['policy']}:{r['week']}",'run_id':'r:ABC-A-carry-full-board-extension-v1'if panel.endswith('335')else runid,'method_id':mapping[r['arm']],'procedure_id':'A::ABC-PREDICTIVE-IMPROVEMENT-01::'+r['arm']+'::'+r['policy'],'category':'rush_att','period_id':'2026_W1_W7_'+panel,'requested_period':'2026_W1_W8','actual_weeks':r['weeks'],'history':'2019-2025fixedCDF; earlier7daystate; CountA originalretained history, notnewfit','original_decision':False,'panel':panel,'score':r,'state':'COMPLETED_CURRENT_VINTAGE_TIMING_UNVERIFIED_DIAGNOSTIC','source_record':'../abc-championship/predictive-improvement-01/'+('FULL_BOARD_DIRECT_RESULTS_V1.json'if panel.endswith('335')else'completion-v3/ACTUAL_LINE_RESULTS_V1.json')})
 assert len({r['result_id']for r in selection})==len(selection)
 for r in selection:
  for side in ['OVER','UNDER','COMBINED']:
   s=r['score'][side]
   if s['decided']:assert s['wins']+s['losses']==s['decided']and abs(s['rate']-s['wins']/s['decided'])<1e-12
   else:assert s['rate']is None
 write(R/'ABC_DYNAMIC_CARRY_SELECTION_RESULTS_V1.json',{'schema':'opportunity-four-linked-selection-artifact-v1','parent_experiment':exp['experiment_id'],'parent_method_registry':'METHOD_REGISTRY.json','records':selection,'full_probability':'../abc-championship/predictive-improvement-01/INDEPENDENT_FULL_BOARD_VERIFICATION_V1.json','controls_not_forecast_probabilities':True})
 pubs=load(R/'PUBLICATION_RECORDS.json');entry={'publication_id':'pub:ABC-A-dynamic-carry-results-v1','subjects':[subject,*newids],'state':'PUBLICATION_PENDING','commit':None,'readback_record':None}
 if entry['publication_id']not in{x['publication_id']for x in pubs['records']}:pubs['records'].append(entry)
 write(R/'PUBLICATION_RECORDS.json',pubs)
 # Flat direct tables are generated, never hand-entered minima.
 flat=[]
 for panel,data in [('RB',rb['scores']),('FULL',full['scores'])]:
  for r in data:
   out={'population':panel,'method':r['arm'],'policy':r['policy'],'week':r['week'],'eligible':r['eligible'],'selected':r['COMBINED']['selected'],'unavailable':r['unavailable'],'games':r['games']}
   for side in ['OVER','UNDER','COMBINED']:
    for k in ['wins','losses','decided','rate']:out[side.lower()+'_'+k]=r[side][k]
   flat.append(out)
 with(O/'EACH_METHOD_OWN_SIDES_BY_WEEK_V1.csv').open('w',newline='')as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 with(O/'NUMERICAL_BY_SEASON_WEEK_V1.csv').open('w',newline='')as f:
  fields=['season','week','arm','product','expected','scored','MAE','MSE','RMSE','bias','p95_absolute_error','strict_lt1','inclusive_le1'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(num)
 print(json.dumps({'new_native_result_records':len(newids),'linked_selection_records':len(selection),'new_fits':0,'publication':'PENDING_REMOTE_READBACK'}))
if __name__=='__main__':main()
