"""Audit pre-identity archive denominator and compare existing source-specific views."""
import collections,csv,gzip,hashlib,io,json,math,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/abc-championship/reconciliation-v1'
def main():
 r=json.loads((OUT/'W6_W7_RECORDED_THRESHOLD_RESULTS_V1.json').read_text());b=json.loads(gzip.decompress((ROOT/'config/session-ab-private-transport-v1.private.json.gz').read_bytes()));base=Path(b['destination_root']).parent/'week8-original-grade-v2-batch-20261102';src=base/'A_W6_W7_RECORDED_THRESHOLD_REPLAY_V1.zip';assert hashlib.sha256(src.read_bytes()).hexdigest()==r['private_evidence']['sha256'];cfg=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()));expected=collections.Counter()
 with zipfile.ZipFile(src)as z:
  for week in (6,7):
   a=json.loads(z.read(f'archive_w{week}.json'))
   for p in a['players']:
    for q in p['props']:
     cat=q['key'];line=q.get('line')
     if cat in cfg['primary_roles_by_target']and cat not in('anytime_td','chart_ppr')and p['pos']in cfg['primary_roles_by_target'][cat]and q.get('line_from')in('dk','sleeper')and isinstance(line,(int,float))and math.isfinite(line):expected[(week,cat)]+=1
 oldfile=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz';old=list(csv.DictReader(io.StringIO(gzip.decompress(oldfile.read_bytes()).decode())));comparisons=[]
 for cat in sorted({x['category']for x in r['scores']}):
  for week in (6,7):
   before=next((x for x in old if x['category']==cat and x['method']=='LEAF_CDF'and x['product']=='median'and x['week']==str(week)),None);after=next(x for x in r['scores']if x['category']==cat and'LEAF_CDF::median'in x['procedure_id']and x['week_view']==str(week));comparisons.append({'week':week,'category':cat,'archive_eligible_before_identity':expected[(week,cat)],'new_identity_qualified_offers':after['eligible'],'identity_excluded_offers':expected[(week,cat)]-after['eligible'],'prior_source_eligible':int(before['opportunities'])if before else None,'prior_source_wins':int(before['correct'])if before else None,'prior_source_decided':int(before['decided'])if before else None,'new_source_wins':after['COMBINED']['wins'],'new_source_decided':after['COMBINED']['decided']})
 out={'state':'PASS_DENOMINATOR_AND_PRIOR_WEEK_SCOPE_CHECK','archive_eligible_before_identity':sum(expected.values()),'identity_qualified_thresholds':r['unique_recorded_thresholds'],'prior_A_own_side_table_actual_weeks':sorted({int(x['week'])for x in old if float(x['opportunities'])>0}),'new_weeks_claim':False,'scope':'W6/W7 already exist in older A W1-7 source-specific results. This new replay uses different archived boards and explicit historical IDs; changes are not accuracy improvements on identical populations or newly covered NFL weeks. Unqualified identities stay in outer coverage accounting.','comparisons':comparisons};(OUT/'W6_W7_OUTER_COVERAGE_AND_SOURCE_RECONCILIATION_V1.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k]for k in ['archive_eligible_before_identity','identity_qualified_thresholds','new_weeks_claim']}))
if __name__=='__main__':main()
