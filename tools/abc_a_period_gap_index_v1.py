"""Source-specific W1-8 gaps; import reported metadata without claiming row access."""
import collections,csv,gzip,hashlib,io,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/abc-championship';CACHE=Path('/tmp/abc-period-continuation-20261103')
def main():
 rows=[]
 def add(session,source,cat,method,product,week,state,n,games,ref,next_action):rows.append({'session':session,'source_panel':source,'category':cat,'method_or_procedure':method,'product':product,'season':2026,'week':week,'state':state,'reported_offer_rows':n,'reported_games':games,'source_reference':ref,'next_action':next_action,'owner':session,'shared_admission':'NOT_OBSERVED'if session in('A','B')else'C_OWN_ROWS_ONLY'})
 src=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz';data=list(csv.DictReader(io.StringIO(gzip.decompress(src.read_bytes()).decode())));lookup={(r['category'],r['method'],r['product'],int(r['week'])):r for r in data}
 combos=sorted({k[:3]for k in lookup})
 for cat,method,product in combos:
  for week in range(1,9):
   r=lookup.get((cat,method,product,week));n=int(float(r['opportunities']))if r else 0
   add('A','A_ARCHIVE_REPRESENTATIVE_BOOK_RECONSTRUCTION',cat,method,product,week,'COMPLETED_LOCAL_TIMING_UNVERIFIED_NOT_COMMON_MASK'if n else'NO_LINES_IN_THIS_FROZEN_OFFER_SOURCE'if week<=7 else'NEW_METHOD_NOT_CAPTURED_W8',n,None,'reports/category-topfive-matched-all12-w1w7-20261030/EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz','Bind A records to C source-specific manifest; source timing remains diagnostic'if n else'Qualify retained original website boards separately for W6-7; do not substitute synthetic thresholds'if week<=7 else'Preserve missed original issuance; new retrospective inference needs own origin contract')
 hist=json.loads((OUT/'A_HISTORICAL_COMMON_SCORER_V1.json').read_text())['scores']
 for cat,method in sorted({(r['category'],r['procedure_id'])for r in hist}):
  for week in range(1,9):
   m=next((r for r in hist if r['period_id']=='WEEKLY_2026'and r['category']==cat and r['procedure_id']==method and r['week_view']==str(week)),None)
   add('A','A_RETAINED_OU_SOURCE_SPECIFIC_COMMON_FUNCTION',cat,method,'REGISTERED_POINT_OR_PROBABILITY',week,'COMMON_FUNCTION_OWNER_LOCAL_COMPLETED_PENDING_C_ADMISSION'if m else'HISTORICAL_LINES_MISSING_THIS_ARCHIVE_PERIOD',m['eligible']if m else 0,m['games']if m else None,'reports/abc-championship/A_HISTORICAL_COMMON_SCORER_V1.json','C intake owner-local outputs and verify bound source/mask; A forecasts already retained'if m else'A obtain qualified existing full-board lines beyond sourceW5; archive does not supply W6-8')
 b=json.loads((CACHE/'existing_exact_cell_grid.json').read_text());seen=set()
 for r in b:
  if r['season']!=2026:continue
  k=(r['target'],r['procedure_id'],r['product_id'],r['history_regime'],r['horizon']);
  if k in seen:continue
  seen.add(k);same=[q for q in b if q['season']==2026 and (q['target'],q['procedure_id'],q['product_id'],q['history_regime'],q['horizon'])==k]
  for week in range(1,9):
   candidates=[q for q in same if week in q['weeks']];n=max((q.get('P1_rows',0)or 0 for q in candidates),default=0);state=('B_REPORTED_W7_THRESHOLD_REPLAY_ONLY'if week==7 and any(q.get('P1_state')=='PARTIAL_W7_ADMITTED_RECONSTRUCTION'for q in candidates)else'B_NUMERIC_FIT_REQUIRED'if candidates and all(q['state']=='FIT_REQUIRED'for q in candidates)else'B_NO_WEEKLY_THRESHOLD_EVIDENCE_IN_PERIOD_GRID')if candidates else'NO_CELL_IN_PUBLISHED_B_GRID';add('B','B_EXACT_IMPLEMENTED_GRID_REPORTED_NOT_REPRODUCED',r['target'],r['procedure_id']+'::'+r['history_regime'],r['product_id'],week,state,None,None,'08fa2ea888620f5587ed5618dfc0e239be82a664:reports/completion-20261031g/roster/finite-v2/FINITE_RECIPE_CATEGORY_PERIOD_PRODUCT_GRID.json','B supplies actual weekly mask/retained rows or runs C-bound owner-local score; period membership alone is not weekly offer evidence')
 roster=json.loads((CACHE/'C/reports/abc-championship/METHOD_ROSTER-v2-C-1.json').read_text());scores=json.loads((CACHE/'C/reports/abc-championship/SCORES-v2-C-1.json').read_text())
 for r in roster:
  for cat in r['categories']:
   for week in range(1,9):
    q=next((x for x in scores if x['category']==cat and x['procedure_id']==r['procedure_id']and x['week_view']==str(week)),None)
    add('C','C_BOUND_PINNACLE_PRIMARY',cat,r['procedure_id'],r['output_type'],week,'COMPLETED_C_CANONICAL_INDEPENDENT_A_ARITHMETIC_CHECKED'if q else'NO_LINES_IN_C_PUBLISHED_PRIMARY_PANEL',q['eligible']if q else 0,q['games']if q else None,'ac9cb1000bcb8f1197505b68ccfe246ea61bbafe:reports/abc-championship/SCORES-v2-C-1.json','C continue owned source expansion; source-qualified A/B boards remain distinct admissible panels'if not q else'C preserve correction/mask identities; A verification available')
 # Explicit status for all twelve including absent market categories.
 allcats=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','chart_ppr']
 for cat in allcats:
  if any(r['category']==cat and r['session']=='C'for r in rows):continue
  for week in range(1,9):add('C','C_BOUND_PINNACLE_PRIMARY',cat,'C_REGISTERED_CATEGORY_NO_ACTUAL_LINE_CELL','N/A',week,'CATEGORY_HAS_NO_QUALIFIED_LINE_IN_C_PANEL',0,None,'C_CURRENT_PROTOCOL/SOURCE_COVERAGE.csv','C source task; preserve forecast-only outcomes separately')
 fields=list(rows[0]);s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(rows);b=gzip.compress(s.getvalue().encode(),mtime=0);(OUT/'WEEK_BY_WEEK_GAP_TABLE_V1.csv.gz').write_bytes(b)
 summary={'state':'SOURCE_SPECIFIC_DISCOVERABLE_GAPS_NOT_ALL_WORLD_ABSENCE','rows':len(rows),'SHA256':hashlib.sha256(b).hexdigest(),'compressed_bytes':len(b),'by_session_state':dict(collections.Counter(r['session']+'|'+r['state']for r in rows)),'B_week_count_limit':'B P1_rows is reported period-level repeated only as metadata; never sum these values across this weekly gap grid or call them weekly scored counts. Actual B original W8 source separately verified.','historical_cells':{'A_2024_W1_8_and_FULL_REG_three_count_targets':'EXECUTED_COMMON_FUNCTION_OWNER_LOCAL;14savedprocedures, exact rows retained','A_2026_W1_5_three_count_targets':'EXECUTED_COMMON_FUNCTION_OWNER_LOCAL;separate source-specific panel','2022_2023':'Archives retained; exact current-finalist origin artifacts/cutoff-qualified reconstruction need qualification; do not use through2023/2025 models in their training years','2025':'Qualified football studies retained; original odds file exclusion not reversed; no qualified matching quote cells identified in permitted export','2026_W6_W7':'Named numerical forecasts retained; original website leans exist separately; full relevant-board threshold joins still missing from archive panel','2026_W8':'All14games final; A authentic original-capture grading updated; C olderW8outcome overlap still separate, not silently expanded','pooled_equal_season':'NOT_EXECUTED because requested identical season set unsupported; no missing-year deletion'},'next_fit_authority':'Necessary historical-origin fits remain authorized, but require exact missing origin/input/version and finite fit protocol; no blanket zero-fit prohibition.'};(OUT/'WEEK_GAP_SUMMARY_V1.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'gap_rows':len(rows),'compressed_bytes':len(b)}))
if __name__=='__main__':main()
