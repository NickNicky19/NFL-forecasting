"""Preserve original grades; scoped availability repair and C outcome-only expansion."""
import collections,csv,gzip,hashlib,importlib.util,io,json,resource,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'reports/abc-championship';O=P/'reconciliation-v1'
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 resource.setrlimit(resource.RLIMIT_CPU,(300,301));cpu=time.process_time();O.mkdir(exist_ok=True)
 old=json.loads((P/'A_ON_C_BOUND_OFFERS_UNCERTAINTY_APPEND_V1.json').read_text());private_a=load('abc_a_common_offer_state_correction_v2').main(return_private=True);new=json.loads((O/'A_ON_C_BOUND_OFFERS_STATE_CORRECTED_V2.json').read_text());index={(r['category'],r['procedure_id'],r['week_view']):r for r in old['scores']};changes=[]
 for r in new['scores']:
  before=index[(r['category'],r['procedure_id'],r['week_view'])]
  for k in ['OVER','UNDER','COMBINED']:assert before[k]==r[k], 'Decided/side counts must not change'
  for k in ['eligible','unavailable','abstentions','games','player_games','coverage']:assert before[k]==r[k]
  assert r['states'].get('UNAVAILABLE_FORECAST',0)==r['unavailable']
  assert r['states'].get('ABSTAIN',0)==r['abstentions']
  assert r['COMBINED']['selected']+r['unavailable']+r['abstentions']==r['eligible']
  if before['states']!=r['states']:changes.append({'category':r['category'],'procedure_id':r['procedure_id'],'week_view':r['week_view'],'before_states':before['states'],'after_states':r['states'],'unavailable_forecasts':r['unavailable'],'selected':r['COMBINED']['selected'],'decided':r['COMBINED']['decided']})
 assert len(changes)==80
 oldpairs={(r['category'],r['procedure_id'],r['control']):r for r in old['paired']}
 for r in new['paired']:
  before=oldpairs[(r['category'],r['procedure_id'],r['control'])]
  for k in ['common_decided','A_wins','control_wins','win_change','side_disagreements','mask_sha256']:assert before[k]==r[k]
 trace={'state':'CONFIRMED_AND_CORRECTED_SELECTED_OUTCOME_STATE_INHERITANCE','original_source_commit':'88dac5da1b261ae6f521d3f23c83b2f95fc364bd','original_file':'A_ON_C_BOUND_OFFERS_UNCERTAINTY_APPEND_V1.json','new_file':'reconciliation-v1/A_ON_C_BOUND_OFFERS_STATE_CORRECTED_V2.json','affected_aggregate_views':len(changes),'source_unique_model_offer_state_changes':new['changed_selected_state_incidents'],'decided_WL_side_counts_changed':0,'paired_count_or_mask_changes':0,'original_C_and_A_forecasts_changed':0,'original_scoring_file_preserved':True,'cause':'A point exists and selects side, but copied C baseline status was UNAVAILABLE_FORECAST when labels unresolved. C status correctly preserved that input state. A adapter now sets forecast availability from A and missing-outcome state from participation before invoking unchanged C scorer.','changes':changes,'limits':'Aggregate-view counts include ALL and weekly views, not80independentNFLoutcomes.'}
 (O/'AVAILABILITY_CORRECTION_TRACE_V1.json').write_text(json.dumps(trace,indent=2)+'\n')
 def csvrows(b):return list(csv.DictReader(io.StringIO(gzip.decompress(b).decode())))
 a=Path('/tmp/abc-discovery-20261103/C_ROWS.csv.gz').read_bytes();b=Path('/tmp/abc-reconcile-20261104/C_C_expanded.csv.gz').read_bytes();assert hashlib.sha256(a).hexdigest()=='c1a027df3e6a1252f0844379fbdad046be0243087f7598d3adeb7727395847da';assert hashlib.sha256(b).hexdigest()=='92c0882f45bfa7c4d8ab2f97ab830d830fcf36b344ec93636b23f989ebe6fa2d';oldc=csvrows(a);newc=csvrows(b);oldi={r['forecast_id']:r for r in oldc};assert len(oldi)==len(oldc)==len(newc)==2513
 fields=['forecast_id','run_id','game_id','espn_event_id','player_id','name','position','team','opponent_team','category','kickoff_UTC','mean','median','p05','p95','event_probability','model_id','model_SHA256','scoring_contract_id','information_cutoff_UTC','generated_UTC'];added=0
 for r in newc:
  q=oldi[r['forecast_id']];assert all(r[k]==q[k]for k in fields),'Forecast changed in proposed outcome-only packet'
  if q['state']=='GRADED_PLAYED':assert r['actual']==q['actual'],'Previously supported outcome changed'
  if q['state']!='GRADED_PLAYED'and r['state']=='GRADED_PLAYED':added+=1
 assert added==91
 private_w8=load('abc_a_c_week8_outcome_expansion_v2').main(return_private=True);expanded=json.loads((O/'A_C_WEEK8_EXPANDED_V2.json').read_text());oldpilot=json.loads((P/'LOCAL_A_C_RESULTS_V1.json').read_text());old_n=next(r['eligible_common']for r in oldpilot['rows']if r['category']=='pass_yd'and r['procedure_output_rule']=='A_R0_POINT');summary={'state':'PASS_ORIGINAL_FORECASTS_AND_PRIOR_SUPPORTED_OUTCOMES_UNCHANGED','C_original_rows':2513,'forecast_fields_checked':fields,'new_C_scalar_grades':91,'C_final_graded':sum(r['state']=='GRADED_PLAYED'for r in newc),'C_unknown':sum(r['state']=='UNKNOWN'for r in newc),'C_pending':sum(r['state']=='PENDING'for r in newc),'old_A_C_matched_offers':sum(r['eligible_common']for r in oldpilot['rows']if r['procedure_output_rule']=='A_R0_POINT'),'new_A_C_matched_offers':len(private_w8)//6,'old_source_sha256':hashlib.sha256(a).hexdigest(),'expanded_source_sha256':hashlib.sha256(b).hexdigest(),'C_commit':'39b98567cc11835363e91c6a2b504bf9cae1f17a','new_forecasts_fits':0,'scope':'New outcome-only version; old344casepilot preserved; no91offer equivalence assumption'};(O/'C_WEEK8_EXPANSION_VERIFICATION_V1.json').write_text(json.dumps(summary,indent=2)+'\n')
 # Retain minimal A private replay evidence in the existing managed namespace, under original caps.
 sys.path.insert(0,str(ROOT));from tools import category_topfive_matched12_storage_v1 as st
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 members={'CORRECTED_A_ON_C_JOIN_ROWS.json.gz':gzip.compress(json.dumps(private_a,separators=(',',':'),allow_nan=False).encode(),mtime=0),'EXPANDED_W8_POINT_ROWS.json.gz':gzip.compress(json.dumps(private_w8,separators=(',',':'),allow_nan=False).encode(),mtime=0)};members['MEMBER_MANIFEST.json']=json.dumps({k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}for k,v in members.items()},sort_keys=True).encode();buffer=io.BytesIO()
 with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED)as z:
  for k,v in members.items():z.writestr(k,v)
 body=buffer.getvalue();assert len(body)<2097152;target=store.forward_root/'research'/'week8-original-grade-v2-batch-20261102'/'A_RECONCILIATION_20261104_V1.zip';assert not target.exists();store.write_bytes(target,body);store.validate_reference(target,hashlib.sha256(body).hexdigest());usage=store.verify_retained_checkpoint()
 receipt={'state':'PASS_MANAGED_PRIVATE_READBACK_AND_UNCHANGED_RETAINED_CAPS','artifact_id':'A-RECONCILIATION-20261104-V1','sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'corrected_join_rows':len(private_a),'expanded_point_view_rows':len(private_w8),'source_independent_NFL_rows_not_view_count':True,'offhost_restore':'NOT_VERIFIED','CPU_seconds':time.process_time()-cpu,'accounting':{k:v for k,v in usage.items()if k.endswith('_bytes')and isinstance(v,int)}};(O/'PRIVATE_READBACK_RECEIPT_V1.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'affected_views':80,'old_W8_offers':summary['old_A_C_matched_offers'],'new_W8_offers':summary['new_A_C_matched_offers'],'C_new_grades':91,'private_bytes':len(body),'CPU_seconds':receipt['CPU_seconds']}))
if __name__=='__main__':main()
