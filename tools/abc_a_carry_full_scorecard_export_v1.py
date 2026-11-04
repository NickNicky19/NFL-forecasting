"""Format saved full-board grades into a private CSV; no inference or scoring."""
import csv,gzip,io,json,sys,zipfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import abc_a_dynamic_carry_wave_v1 as base
def main():
 from tools import category_topfive_matched12_storage_v1 as st
 import pandas as pd,pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1);start=time.monotonic();cpu=time.process_time();O=ROOT/'reports/abc-championship/predictive-improvement-01';r=json.loads((O/'FULL_BOARD_DIRECT_RESULTS_V1.json').read_text());store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO);d=store.forward_root/'research'/'ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
 store.validate_reference(d/'FULL_BOARD_CARRY_GRADE_V1.zip',r['private_grade']['sha256'])
 with zipfile.ZipFile(d/'FULL_BOARD_CARRY_GRADE_V1.zip')as z:rows=json.loads(gzip.decompress(z.read('GRADE_ROWS.json.gz')))
 receipt=json.loads((O/'completion-v3/SCORING_RECEIPT_V1.json').read_text());store.validate_reference(d/'GRADED_SCORECARD_V1.zip',receipt['sha256'])
 with zipfile.ZipFile(d/'GRADED_SCORECARD_V1.zip')as z:numeric=json.loads(gzip.decompress(z.read('NUMERICAL_ROWS.json.gz')))
 store.validate_reference(d/'NON_RB_CARRY_FORECASTS_V1.zip',r['new_forecasts']['sha256'])
 with zipfile.ZipFile(d/'NON_RB_CARRY_FORECASTS_V1.zip')as z:numeric+=json.loads(gzip.decompress(z.read('FORECASTS.json.gz')))
 key=lambda r:(r.get('season',2026),r['game_id'],r['player_id'],r['arm']);f={key(q):q for q in numeric};means={(q['game_id'],q['player_id'],q['arm']):q['point']for q in rows if q['policy']=='P1_MEAN'}
 _,_,g,_=base.sources()
 with zipfile.ZipFile(io.BytesIO(base.pin(g['offers'])))as z:offers=pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
 offers={q['opportunity_key']:q for q in offers.loc[offers.target.eq('rush_att')].to_dict('records')}
 cols=['season','week','game_id','player_id','position','procedure','policy','evidence','mean','median','point','line','side','actual','absolute_error','p_over','p_under','p_push','statistical_result','venue_settlement','book_id','listed_decimal_price','quote_time','quote_timing_status','information_cutoff','generation_UTC','source_max_UTC','fallback','unavailable_reason']
 out=io.StringIO();w=csv.DictWriter(out,fieldnames=cols);w.writeheader()
 for q in rows:
  a=f.get(key(q),{});offer=offers[q['opportunity_key']];price=offer['decimal_over']if q['selected_side']=='OVER'else offer['decimal_under']if q['selected_side']=='UNDER'else None
  w.writerow({'season':2026,'week':q['week'],'game_id':q['game_id'],'player_id':q['player_id'],'position':q['position'],'procedure':'A::ABC-PREDICTIVE-IMPROVEMENT-01::'+q['arm'],'policy':q['policy'],'evidence':'CURRENT_VINTAGE_TIMING_UNVERIFIED_RULE_REPLAY','mean':a.get('mean',means.get((q['game_id'],q['player_id'],q['arm']))),'median':a.get('median'),'point':q['point'],'line':q['line'],'side':q['selected_side'],'actual':q['actual'],'absolute_error':abs(q['point']-q['actual'])if q['point']is not None and q['actual']is not None else None,'p_over':q['p_over'],'p_under':q['p_under'],'p_push':q['p_push'],'statistical_result':q['status'],'venue_settlement':'UNRESOLVED_CONTRACT_NOT_VERIFIED','book_id':offer['book_id']if pd.notna(offer['book_id'])else None,'listed_decimal_price':float(price)if price is not None and pd.notna(price)else None,'quote_time':str(offer['source_quote_time'])if pd.notna(offer['source_quote_time'])else None,'quote_timing_status':offer['quote_timing_status'],'information_cutoff':a.get('cutoff_utc'),'generation_UTC':a.get('generation_UTC'),'source_max_UTC':a.get('source_information_max_UTC'),'fallback':q['fallback'],'unavailable_reason':q['outside_scope_reason']or('POINT_ONLY_CONTROL_NO_REQUESTED_OUTPUT'if q['selected_side']is None else None)})
 b=gzip.compress(out.getvalue().encode(),mtime=0);p=d/'FULL_BOARD_PREDICTIONS_ACTUALS_DIRECTIONS_V1.csv.gz';store.write_bytes(p,b);store.validate_reference(p,base.sha(b));store.verify_retained_checkpoint();receipt={'state':'PASS_SAVED_ROWS_FORMATTED_NOT_NEW_SCORES','artifact_id':'A-FULL-BOARD-READABLE-SCORECARD-V1','rows':len(rows),'bytes':len(b),'sha256':base.sha(b),'readback':'PASS_APPROVED_PRIVATE_STORE','offhost_restore':'NOT_VERIFIED','new_fits_inference_scoring':0,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start};(O/'FULL_BOARD_READABLE_SCORECARD_RECEIPT_V1.json').write_bytes(base.enc(receipt));print(json.dumps(receipt))
if __name__=='__main__':main()
