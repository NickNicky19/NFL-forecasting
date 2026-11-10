"""Project authenticated aggregate score cells to portable public plaintext.

No grader, prediction, fit, source-row reader, model loader or native-store
adapter is imported. Every exported metric is copied from the bound full score.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,math
from pathlib import Path

VERSION='A-NEXT02-ALIGNED-TIMING-PUBLIC-AGGREGATES-v1'
SOURCE_STATE='FROZEN_ALIGNED_TIMING_POINT_AND_LAW_SCORING_COMPLETE'
LIMIT=60*1024
ARMS=['F0_ORIGINAL_BASE','F1_ORIGINAL_PROFILE','F2_48H_BASE','F3_48H_PROFILE']
PRODUCTS=['MEAN_P1','MEDIAN_P1','EXACT_LINE_P2']
PRIMARY={(ARMS[i]+'::'+p,ARMS[j]+'::'+p)for p in PRODUCTS for i,j in[(1,0),(2,0),(3,2),(3,1)]}
FORBIDDEN={'player_id','player_ids','player_name','game_id','team','opponent','opportunity_key','opportunity_id','actual','point','line','law','weights','support','source_refs','forecast_rows','model','models','path'}
NUMERIC=['state','intended','available','scored','unavailable','unknown_outcome','MAE','MSE','RMSE','bias','absolute_error_p90','max_absolute_error','fallback','unavailability_reasons']
PROBABILITY=['qualified_law_outcomes','decisive_law_outcomes','binary_Over_event_Brier','binary_event_contract','three_class_Brier_sum','three_class_log_loss','infinite_log_loss_cases','finite_three_class_log_loss_mean','selected_probability_not_validated_confidence','state']
SUMMARY_FIELDS=['period','cohort','candidate_id','execution_state','population','source_panel','week_view','eligible','unavailable','abstentions','states','games','player_games','weeks','uncertainty','coverage','actual_recorded_line_scored_weeks','five_actual_week_duration_floor','diagnostic_scored_weeks','evidence_tiers','admission']
PAIR_FIELDS=['period','cohort','source_panel','left','right','execution_state','common_decided','left_wins','right_wins','accuracy_change','side_disagreements','decision_uncertainty','common_numerical','MAE_change','MAE_change_uncertainty','decided_mask_sha256','numerical_mask_sha256']
PAIR_PROBABILITY=['common_probability_events','binary_Over_event_Brier_change','game_interval95','week_interval95','event_conditioning']
FALLBACK_FIELDS=['panel','left','right','group','cases','unique_games','left_status_counts','right_status_counts','common_decided','left_wins','right_wins','accuracy_change','common_numerical','MAE_change','common_probability_events','Brier_change','full_mask_sha256']

def sha(body):return hashlib.sha256(body).hexdigest()
def encoded(value):return(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def check(ok,message):
    if not ok:raise ValueError(message)
def public(value):
    """Fail on accidental row/locator content; never silently redact score cells."""
    if isinstance(value,dict):
        for k,v in value.items():
            check(k not in FORBIDDEN,'row/source field is outside public aggregate schema')
            public(k);public(v)
    elif isinstance(value,list):
        for v in value:public(v)
    elif isinstance(value,str):
        check(not value.startswith('/')and'://'not in value and'\\\\'not in value,'absolute locator is outside public schema')
    elif isinstance(value,float):check(math.isfinite(value),'nonfinite public aggregate')
    else:check(value is None or isinstance(value,(int,bool)),'unsupported public value')
    return value

def selected(row,fields):return{k:row.get(k)for k in fields}
def summary(row):
    out=dict(category='rush_yd',role='RB',requested_period='2026_W1_W8',**selected(row,SUMMARY_FIELDS))
    for side in ['OVER','UNDER','COMBINED']:
        for field in ['selected','wins','losses','decided','rate']:
            out[side.lower()+'_'+field]=row.get(side,{}).get(field)
    for field in NUMERIC:out['numerical_'+field]=row.get('numerical',{}).get(field)
    for field in PROBABILITY:out['probability_'+field]=row.get('probability',{}).get(field)
    return public(out)

def pair(row):
    out=dict(category='rush_yd',role='RB',primary_contrast=(row['left'],row['right'])in PRIMARY,**selected(row,PAIR_FIELDS))
    for field in PAIR_PROBABILITY:out['probability_'+field]=row.get('probability',{}).get(field)
    return public(out)

def fallback(row):return public(dict(category='rush_yd',role='RB',**selected(row,FALLBACK_FIELDS)))

def render(rows,fields):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader()
    for row in rows:
        writer.writerow({k:json.dumps(row.get(k),sort_keys=True,separators=(',',':'),allow_nan=False)if isinstance(row.get(k),(dict,list))else row.get(k)for k in fields})
    return stream.getvalue().encode()

def emit(destination,stem,rows,files):
    if not rows:return
    fields=list(rows[0]);check(all(list(r)==fields for r in rows),'aggregate CSV field order differs')
    chunk=[];number=1
    def write(part,num):
        body=render(part,fields);check(len(body)<=LIMIT,'one aggregate cell exceeds fixed shard limit')
        name=f'{stem}_{num:03d}.csv';(destination/name).write_bytes(body)
        files.append(dict(path=name,rows=len(part),bytes=len(body),sha256=sha(body)))
    for row in rows:
        if chunk and len(render(chunk+[row],fields))>LIMIT:write(chunk,number);number+=1;chunk=[]
        chunk.append(row)
    if chunk:write(chunk,number)

def export(raw,expected,destination):
    check(len(expected)==64 and all(x in'0123456789abcdef'for x in expected),'exact lowercase source digest required')
    check(sha(raw)==expected,'bound full-score bytes changed')
    decoded=gzip.decompress(raw)if raw[:2]==b'\x1f\x8b'else raw
    result=json.loads(decoded)
    check(result['state']==SOURCE_STATE and result['score_scope_version']=='ALIGNED_TIMING_FOUR_ALIASES_V1','wrong completed aggregate score scope')
    check(result['completed_arms']==ARMS and result['pending_arms']==[],'all four completed aliases required')
    seen={(r['left'],r['right'])for r in result['paired']};check(PRIMARY<=seen,'missing required primary contrast product')
    ss=[summary(r)for r in result['summaries']];pp=[pair(r)for r in result['paired']]
    ff=[fallback(r)for r in result['fallback_attribution']['records']]
    check(not destination.exists(),'immutable public export directory already exists');destination.mkdir(parents=True)
    files=[];emit(destination,'ALL_SUMMARIES',ss,files);emit(destination,'ALL_MATCHED_PAIRS',pp,files);emit(destination,'PRIMARY_FALLBACK_TRANSITIONS',ff,files)
    manifest=dict(id=VERSION,state='PLAINTEXT_AGGREGATE_PROJECTION_COMPLETE',source_fullscore_sha256=expected,source_fullscore_bytes=len(raw),source_decoded_sha256=sha(decoded),source_decoded_bytes=len(decoded),source_protocol_sha256=result['protocol_sha256'],source_execution_receipt_sha256=result['execution_receipt_sha256'],source_summary_cells=len(result['summaries']),exported_summary_cells=len(ss),source_paired_cells=len(result['paired']),exported_paired_cells=len(pp),source_fallback_transition_cells=len(result['fallback_attribution']['records']),exported_fallback_transition_cells=len(ff),required_primary_product_contrasts=12,exported_primary_pair_cells=sum(r['primary_contrast']for r in pp),files=files,aggregate_rows=sum(f['rows']for f in files),maximum_data_shard_bytes=LIMIT,no_outcome_based_omission=True,public_player_game_offer_rows=0,new_fits=0,new_inference=0,new_grading=0,new_probability_or_score_calculations=0,source_rows_or_model_reads=0,scope='Every supplied summary, every registered paired cell, and every supplied full-system/learned/fallback transition, without score-dependent filtering. Broad numerical summaries retain only their actual supplied cumulative scope; no weekly numerical cells are invented.',limits=['W1-5 retained actual thresholds remain quote-time-unverified','W6-7 site thresholds retain their separate unqualified diagnostic tier','W8 reference thresholds do not add an actual-offer week','Reconstructed48h timing is not authenticated source availability','Five-week duration is not primary admission, Top Picks qualification, current delivery or a probability-confidence claim','Views overlap; do not pool cumulative, weekly, source or cohort copies as independent selections'])
    (destination/'MANIFEST_V1.json').write_bytes(encoded(manifest))
    (destination/'INDEX.csv').write_bytes(render(files,['path','rows','bytes','sha256']))
    (destination/'README.md').write_text('''# Aligned timing — copied aggregate cells

These plaintext files project the exact hash-bound completed score. They perform no grading, probability calculation, inference or fitting. Every summary and paired cell is retained, including weekly panels, unavailable outputs, empty cohorts and losses. Primary contrasts and descriptive learned/fallback transitions are identified separately.

F0/F1 reuse their original saved forecasts. F2/F3 are separately fitted under the reconstructed 48-hour sensitivity. This does not authenticate historical availability. Annual actual thresholds, site diagnostics and Week 8 reference thresholds remain separate. Numerical, direction and probability products do not borrow one another's qualification. Rates are fractions; empty CSV values represent N/A/null, while observed numeric zero remains zero.

No source, forecast, player, game, offer or model rows are exported. Splitting uses a fixed 60 KiB size limit, never outcomes. MANIFEST_V1.json binds the full source bytes and every exported file. INDEX.csv gives readable file mappings. Overlapping views are not additional independent football evidence.
''')
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--score',type=Path,required=True)
    parser.add_argument('--score-sha256',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();m=export(args.score.read_bytes(),args.score_sha256,args.output_dir)
    print(json.dumps(dict(state=m['state'],source_fullscore_sha256=m['source_fullscore_sha256'],data_files=len(m['files']),aggregate_rows=m['aggregate_rows'])))
if __name__=='__main__':main()
