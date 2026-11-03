"""Owner-local use of pinned C scorer; independent partitions and saved-year replay."""
import collections,datetime,gzip,hashlib,importlib,json,math,resource,sys,time,zipfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/abc-championship';CACHE=Path('/tmp/abc-period-continuation-20261103');CP=CACHE/'C'
def dump(n,d):(OUT/n).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def main():
 resource.setrlimit(resource.RLIMIT_CPU,(600,601));cpu=time.process_time();sys.path.insert(0,str(CP/'src'));common=importlib.import_module('abc_championship_v2')
 pointer=json.loads((CACHE/'C_POINTER.json').read_text());assert hashlib.sha256((CP/pointer['protocol']['path']).read_bytes()).hexdigest()=='fa19581487519a854948269bc1ce328cbbcdc734afee2464f1ff778d1ff241a1'
 # Verify consolidated C independently: grade via Decimal comparisons, then partition.
 bindings=json.loads((CP/'reports/abc-championship/C_INPUT_BINDINGS.json').read_text());raw=[]
 for d in bindings['datasets']:
  b=(CP/d['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==d['SHA256'];j=json.loads(gzip.decompress(b)if d['path'].endswith('.gz')else b);raw.extend(j['rows'])
 versions={};corrections=0
 for r in raw:
  old=versions.get(r['record_id'])
  if old and old!=r:assert r['supersedes_grade_id']==old['grade_id'];corrections+=1
  versions[r['record_id']]=r
 first={}
 for r in versions.values():
  k=common.a.snapshot_key(r);clock=r.get('selection_server_UTC')if r['evidence_tier']in['GENUINE_PROSPECTIVE_W8_PLUS','ORIGINAL_AUTHENTICATED_PREGAME']else r['decision_UTC'];rank=(clock,r['scoring_snapshot_id']);old=first.get(k)
  if old is None or rank<old[0]:first[k]=(rank,r)
 retained=[r for rank,r in first.values()];primary=[r for r in retained if r['venue']=='pinnacle'and r['season']==2026 and r['week']<=8];bad=[]
 for r in primary:
  if r['status']not in('WIN','LOSS','PUSH'):continue
  y=Decimal(str(r['actual']));line=Decimal(str(r['line']));side=r['selected_side'];win=(y>=line)==(side=='OVER')if r['comparator']=='AT_LEAST'else y==1 if r['comparator']=='AT_LEAST_ONE_RUSH_REC_TD'else(y>line)==(side=='OVER');expected='PUSH'if r['comparator']=='STRICT_OVER_UNDER'and y==line else'WIN'if win else'LOSS'
  if expected!=r['status']:bad.append(r['record_id'])
 assert not bad
 published=json.loads((CP/'reports/abc-championship/SCORES-v2-C-1.json').read_text());checked=0
 for s in published:
  rs=[r for r in primary if r['category']==s['category']and common.procedure(r)==s['procedure_id']and(s['week_view']=='ALL'or str(r['week'])==s['week_view'])]
  for side in ['OVER','UNDER','COMBINED']:
   ss=[r for r in rs if r['selected_side']in('OVER','UNDER','YES')]if side=='COMBINED'else[r for r in rs if r['selected_side']==side or(side=='OVER'and r['selected_side']=='YES')];co=collections.Counter(r['status']for r in ss);n=co['WIN']+co['LOSS'];v=s[side]
   assert v['selected']==len(ss)and v['decided']==n and v['wins']==(co['WIN']if n else None)and v['losses']==(co['LOSS']if n else None);checked+=1
  assert len(rs)==s['eligible']
 dump('C_CANONICAL_INDEPENDENT_CHECK_V1.json',{'state':'PASS_REPRESENTATIVE_SCOPE_ALL_PUBLISHED_SIDE_PARTITIONS','protocol_id':pointer['protocol_id'],'C_commit':'ac9cb1000bcb8f1197505b68ccfe246ea61bbafe','protocol_sha256':pointer['protocol']['SHA256'],'primary_method_rows':len(primary),'source_rows':len(raw),'corrections_applied':corrections,'side_partitions_checked':checked,'published_cells':len(published),'grade_mismatches':0,'limits':'Independent A arithmetic on retained C rows and published masks; not re-inference, full rights re-audit or A/B row admission. No separate canonical grader created.'})
 # B original-selected board control: sum only one ALL/week/original partition.
 bs=json.loads((CACHE/'B_SCORES.json').read_text());bs=[r for r in bs if r.get('procedure_id')=='B:WEBSITE:original'and r.get('strategy')=='original'and r.get('cohort_id')=='ALL'and r.get('week')==8 and r.get('side')in('over','under')and not r.get('season_alias_of_week_view')];co={s:{k:sum(r['selection_metrics'][k]for r in bs if r['side']==s)for k in ['WIN','LOSS']}for s in ['over','under']};n=sum(sum(v.values())for v in co.values());original=sum(v['WIN']for v in co.values());under=co['over']['LOSS']+co['under']['WIN'];assert(n,original,under)==(415,205,224)
 dump('B_ORIGINAL_ALWAYS_UNDER_CHECK_V1.json',{'state':'PASS_AGGREGATE_ARITHMETIC_NOT_PRIVATE_ROW_VERIFICATION','source_commit':'a1a50abe6c5d542dfa75c987231717eca98c57ab','source_sha256':'e73a780f93afdfef2dfd37caa8f5e1ad12b94403103ace20f33ed2e9d9570c17','category_side_cells':len(bs),'original_sides':co,'original':{'wins':original,'losses':n-original,'decided':n,'rate':original/n},'always_under':{'wins':under,'losses':n-under,'decided':n,'rate':under/n},'paired_win_change':under-original,'percentage_points':100*(under-original)/n,'scope':'Original selected pool only; no common-board, causal Under rule or profit claim; underlying private identities not independently restored.'})
 # A history: exact retained forecasts/decisions, now new period masks through pinned common summary.
 reg=json.loads((ROOT/'config/category-topfive-opportunity-ou-technical-v2.sealed.json').read_text());cap=Path(reg['output'])/'GRADE_COMPLETE.zip';b=cap.read_bytes();assert hashlib.sha256(b).hexdigest()=='1040e07a1cef102b1f9487f824ff03131899d528f740f30f644fe0249f12e7cd'
 with zipfile.ZipFile(cap)as z:old=[json.loads(l)for l in gzip.decompress(z.read('grade.jsonl.gz')).splitlines()]
 normalized=[];new_disagreements=0
 for r in old:
  side=r['selected_side'];why=r['abstention_reason'];sel=side.upper()if side else None if why and why.startswith('MISSING')else'ABSTAIN';played=r['participation_state']=='played'and r['actual']is not None;appearance='PLAYED'if played else'UNKNOWN';state='UNAVAILABLE_FORECAST'if sel is None else'ABSTAIN'if sel=='ABSTAIN'else'UNKNOWN_PARTICIPATION'if not played else'PUSH'if r['actual']==r['line']else'WIN'if r['direction_result']=='CORRECT'else'LOSS';nr={'selected_side':sel,'actual':r['actual'],'status':state,'appearance':appearance,'comparator':'STRICT_OVER_UNDER','line':r['line'],'game_id':r['game_id'],'player_id':r['player_id'],'season':r['season'],'week':r['week'],'category':r['target'],'procedure_id':'A::opportunity-four-ou-v1::'+r['procedure'],'record_id':r['opportunity_id'],'point':r['point'],'book_id':r['book_id']}
  assert common.status(nr)==state
  if played and sel in('OVER','UNDER'):
   independent='PUSH'if Decimal(str(r['actual']))==Decimal(str(r['line']))else'WIN'if((Decimal(str(r['actual']))>Decimal(str(r['line'])))==(sel=='OVER'))else'LOSS';assert state==independent
  normalized.append(nr)
 groups=collections.defaultdict(list)
 for r in normalized:
  labels=[('E1_PARTIAL_2026_W1_5',2026,1,8),('E3_2024_W1_8',2024,1,8),('E4_2024_FULL_REG',2024,1,18)]
  for label,year,lo,hi in labels:
   if r['season']==year and lo<=r['week']<=hi:groups[(label,r['category'],r['procedure_id'],'ALL')].append(r)
  groups[('WEEKLY_'+str(r['season']),r['category'],r['procedure_id'],str(r['week']))].append(r)
 scores=[]
 for (period,cat,procedure,week),rs in sorted(groups.items()):
  sm=common.summary(rs);assert sm['COMBINED']['decided']==sm['OVER']['decided']+sm['UNDER']['decided'];scores.append({'period_id':period,'category':cat,'procedure_id':procedure,'week_view':week,'requested_weeks':list(range(1,19))if period=='E4_2024_FULL_REG'else list(range(1,9)),'actual_weeks':sorted({r['week']for r in rs}),'history':'Retained F model-year2024 trained through2023; corrections/calibrations earlier-only as original saved procedure; no new refit or vintage upgrade','evidence_tier':'TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC','source_panel':'A original fixed representative-book68/69/79 priority; separate from C Pinnacle primary','admission':'OWNER_LOCAL_COMMON_FUNCTION_SCORED;C_ADMISSION_NOT_OBSERVED',**sm})
 dump('A_HISTORICAL_COMMON_SCORER_V1.json',{'protocol_id':pointer['protocol_id'],'scorer_SHA256':pointer['scorer']['SHA256'],'new_fits_inference':0,'input_rows':len(old),'source_sha256':hashlib.sha256(b).hexdigest(),'scores':scores,'scope':'New period/common-scorer evaluation of retained A decisions, not new forecasts or new NFL observations. E3/E4 only2024; E1actualW1-5; no unsupported2022/23/25 pool. Probability definitions and price policies not changed.','private_rows_published':0})
 dump('PERIOD_EXECUTION_RECEIPT_V1.json',{'state':'COMMON_FUNCTION_OWNER_LOCAL_SCORING_AND_INDEPENDENT_CHECK_COMPLETE','C_side_cells':checked,'B_original_pool':n,'A_retained_decisions_regraded_through_common_function':len(old),'A_new_period_week_cells':len(scores),'CPU_seconds':time.process_time()-cpu,'new_fits_inference':0,'shared_new_admission':'NOT_OBSERVED; only C can update canonical admission ledger','new_ABC_matched_rows':0})
 print(json.dumps({'C_side_cells':checked,'B_original_pool':n,'A_input_rows':len(old),'A_period_week_cells':len(scores),'CPU_seconds':time.process_time()-cpu}))
if __name__=='__main__':main()
