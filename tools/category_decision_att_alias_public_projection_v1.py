"""Project an existing aggregate ATT receipt; never fit, infer, grade or read native data."""
import csv,gzip,hashlib,io,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/abc-championship/category-decision-release-01'
SOURCE=OUT/'B_ATT_ALIAS_RESULTS_V2.json.gz'
EXPECTED='0dc195065ad35a0aabd3e0dec89514ca3ba6a857e9327c25078d04f59280eafb'
CAP=60*1024

def sha(b):return hashlib.sha256(b).hexdigest()
def rawjson(j):return (json.dumps(j,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def cell(x):
    if x is None:return ''
    if isinstance(x,(dict,list)):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
    return x
def save(name,b):
    p=OUT/name
    if p.exists() and p.read_bytes()!=b:raise ValueError('existing projection differs: '+name)
    p.write_bytes(b)
    return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=sha(b))
def csv_parts(prefix,rows):
    columns=list(dict.fromkeys(k for row in rows for k in row));header=io.StringIO(newline='');csv.writer(header,lineterminator='\n').writerow(columns);head=header.getvalue().encode()
    parts=[];body=head;count=0
    for row in rows:
        buf=io.StringIO(newline='');csv.writer(buf,lineterminator='\n').writerow([cell(row.get(k))for k in columns]);line=buf.getvalue().encode()
        if len(body)+len(line)>CAP:
            parts.append(dict(save(f'{prefix}_PART{len(parts)+1:02}.csv',body),rows=count));body=head;count=0
        if len(head)+len(line)>CAP:raise ValueError('one projected row exceeds cap')
        body+=line;count+=1
    parts.append(dict(save(f'{prefix}_PART{len(parts)+1:02}.csv',body),rows=count))
    return parts
def summary_row(s):
    r={k:s[k]for k in ['view','source_panel','week_view','candidate_id','category','actual_scored_weeks','weeks','games','player_games','eligible','unavailable','coverage','abstentions','fallback_outputs']}
    for side in ['OVER','UNDER','COMBINED']:
        for k in ['selected','wins','losses','decided','rate']:r[side+'_'+k]=s[side][k]
    for k in ['states','outer_outcomes','forecast_outcome_cross_counts','unavailable_reasons']:r[k]=s[k]
    for k,v in s['numerical_same_offer_mask'].items():r['numerical_'+k]=v
    for k,v in s['uncertainty'].items():r['uncertainty_'+k]=v
    for k in ['eligible_mask_sha256','decided_mask_sha256']:r[k]=s[k]
    return r

def main():
    b=SOURCE.read_bytes()
    if len(b)!=17143 or sha(b)!=EXPECTED:raise ValueError('bound aggregate differs')
    j=json.loads(gzip.decompress(b))
    if len(j['summaries'])!=324 or len(j['paired'])!=50:raise ValueError('aggregate scope differs')
    files=csv_parts('B_ATT_ALIAS_SUMMARIES_V2',[summary_row(s)for s in j['summaries']])
    files+=csv_parts('B_ATT_ALIAS_PAIRS_V2',j['paired'])
    aliases={k:j[k]for k in ['version','UTC','state','old_result','old81_mask_sha256','full87_mask_sha256','membership_sha256','original81_summary_cells_reproduced','original81_paired_cells_reproduced','unchanged_full87_A_control_summary_cells_reproduced','newly_available_B_point_outputs','B_output_products_unchanged','newly_observed_games_weeks','counts','resources','runtime','root_protocol_sha256','evidence_tier']}
    aliases.update(source_aggregate_sha256=EXPECTED,alias_cases=[{k:x[k]for k in ['case_sha256','week','old_reason','new_state']}for x in j['newly_qualified_physical_cases']],scope='Only six previously unavailable 2026 LA/LAR team-identity cases; no model/point/line/outcome/clock/decision change; coverage correction is not learned-skill improvement.')
    files.append(save('B_ATT_ALIAS_CASE_HASH_RECEIPT_V2.json',rawjson(aliases)))
    full=[s for s in j['summaries']if s['view']=='FULL_A_BOARD_ALIAS_QUALIFIED87'and s['source_panel']=='ALL'and s['week_view']=='ALL']
    old=[s for s in j['summaries']if s['view']=='ORIGINAL_STRICT_B81'and s['source_panel']=='ALL'and s['week_view']=='ALL']
    med='B-player-context-matchup-01-v1:COMMON_EXPOSURE::lower_median'
    strongest=[s for s in full if not s['candidate_id'].startswith('ALWAYS_')and s['COMBINED']['wins']==44]
    if [s['candidate_id']for s in strongest]!=[med]:raise ValueError('headline must use actual aggregate')
    headline=dict(version='NFL-CATEGORY-DECISION-AND-RELEASE-01-B-ATT-ALIAS-PUBLIC-PROJECTION-v1',source_aggregate_sha256=EXPECTED,source_result_version=j['version'],source_UTC=j['UTC'],category='pass_att',period='2026 W1-W5; W6-W8 empty in this exact source',evidence_tier=j['evidence_tier'],best_observed_nonconstant=med,strongest_observed_control='ALWAYS_OVER',full87=full,original81=old,paired=[p for p in j['paired']if p['view']=='FULL_A_BOARD_ALIAS_QUALIFIED87'and(p['left']==med or p['right']==med)],coverage_change='Six previously unavailable physical cases; 12 point outputs across two unchanged B products, no new observed NFL games/weeks.',decision='NO_QUALIFIED_REPLACEMENT_ESTABLISHED_BY_THIS_PANEL',reason='B lower median 44/87 is one above strongest A 43/87 and two below always-Over 46/87; paired intervals cross zero. Duration five weeks does not admit quote timing, current-query readiness, probability, Top Picks or website use.',production='NO_CHANGE; actual website owner retains release authority',activity='Projection of saved aggregate only; no grading/scoring, fit, inference or native read.')
    files.append(save('B_ATT_ALIAS_HEADLINE_V2.json',rawjson(headline)))
    text='''# ATT identity coverage correction — executed result

The same saved B lower-median procedure scored **44–43/87 (50.57%)** on A's retained 2026 Weeks 1–5 actual-line board. It is the highest observed nonconstant procedure in this named panel. Its own Over record is **4–1/5** and Under record **40–42/82**; the small Over subset is not category-wide 80% accuracy.

The strongest A Count A point/mean and B mean each scored **43–44/87**. Always-Over scored **46–41/87**. The lower median's one-decision gain over B mean has a game-cluster interval of **−4.40 to +7.23 percentage points**; its two-decision loss to always-Over has **−20.13 to +15.03 points**. These exposed five-week comparisons do not establish replacement superiority.

All nine procedures retain their own sides, numerical errors, fallback and missingness records in the CSVs. B lower-median offered-player MAE is **7.391 attempts**, versus **6.831** for B mean and **6.501** for A HGB. All 87 outcomes are decided, with zero unavailable outputs, unknown outcomes, abstentions or fallback flags in this exact expanded panel. These are source flags, not a new independent fit verification.

Six LA/LAR identity cases became available; LAC and every other contract remained unchanged. Original 81-case summaries and pairs reproduced exactly, as did all unchanged A/control 87-case summaries. This is a coverage correction, not a measured gain in learned-model skill. No new NFL games or weeks were observed, and no model was fit or inferred.

The evidence remains reconstructed, quote-timing-unverified actual-line diagnostics. Weeks 6–8 are explicitly empty for this source; their CSV cells remain N/A. Five scored weeks meet duration only. **No replacement admission, probability/EV claim, Top Picks qualification or website activation follows.** The original result remains preserved.
'''
    files.append(save('B_ATT_ALIAS_RESULT_V2.md',text.encode()))
    manifest=dict(version='NFL-CATEGORY-DECISION-AND-RELEASE-01-B-ATT-ALIAS-PUBLIC-MANIFEST-v1',source=dict(path=str(SOURCE.relative_to(ROOT)),bytes=len(b),sha256=EXPECTED),projection_code=dict(path=str(Path(__file__).relative_to(ROOT)),sha256=sha(Path(__file__).read_bytes())),source_UTC=j['UTC'],summary_rows=324,paired_rows=50,alias_physical_cases=6,CSV_part_cap_bytes=CAP,CSV_null_contract='Empty cell is JSON null/N/A; integer zero is retained. Nested states and exact masks are copied, not regraded. ALL and ANNUAL_NAMED_NJ are duplicate views of one source, not independent evidence.',preserved_views=['ORIGINAL_STRICT_B81','FULL_A_BOARD_ALIAS_QUALIFIED87'],week_views=['ALL',1,2,3,4,5,6,7,8],files=files,new_fits=0,new_inference=0,new_scoring=0,native_reads=0,production_changes=0,scope='Existing aggregate projection only; retain original81 versus expanded87, source rights, timing/selection limits and all empty W6-W8 cells.')
    f=save('B_ATT_ALIAS_PUBLIC_MANIFEST_V2.json',rawjson(manifest));print(json.dumps(dict(manifest=f,files=len(files),summary_rows=324,paired_rows=50,max_CSV_bytes=max(x['bytes']for x in files if x['path'].endswith('.csv')),headline_text_bytes=len(text.encode()),new_scoring=0)))

if __name__=='__main__':main()
