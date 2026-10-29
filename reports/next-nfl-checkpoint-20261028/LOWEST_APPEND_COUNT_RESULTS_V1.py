"""Append only new permitted aggregates; original41source/census records stay fixed."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,math
O=Path('/workspace/nfl-methods-integration/reports/next-nfl-checkpoint-20261028');P=O/'COUNT_MEDIAN_V1/PUBLIC_RESULTS.json'
def enc(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(b):return hashlib.sha256(b).hexdigest()
p=O/'LOWEST_ALL_METHOD_LEDGER_V1.json';before=p.read_bytes();assert sha(before)=='f85f686f4766cfd02963e91f8ad0472b6c611fcbfe9a0410818ecec88c268ba6';x=json.loads(before);original_sources=enc(x['sources']);original_census=enc(x['metadata_census']);assert len(x['sources'])==41
b=P.read_bytes();assert sha(b)=='e33ad250a148dda085a43de022722ca44d70aaad494cc6f076588980dc36478f';wrapper=json.loads(b);study=wrapper['scientific_result'];assert len(study['cells'])==5 and study['new_predictive_fits']==0 and sum(len(c['summaries'])for c in study['cells'])==22
sid='S042';x['sources'][sid]={'path':str(P),'bytes':len(b),'sha256':sha(b),'kind':'published_aggregate_or_metadata'}
d=x['label_dictionaries']
def intern(k,v):
 if v not in d[k]:d[k].append(v)
 return d[k].index(v)
def pointer(v):
 a=[intern('pointer_tokens',z)for z in v.split('/')]
 if a not in d['pointer']:d['pointer'].append(a)
 return d['pointer'].index(a)
def score(m):
 mapping={'p95_absolute_error':'p95','p90_absolute_error':'p90','error_lt_1':'error_strict_lt1','error_le_1':'error_inclusive_le1'}
 out={mapping.get(k,k):v for k,v in m.items()if k in ['MAE','MSE','RMSE','bias','p90_absolute_error','p95_absolute_error','error_lt_1','error_le_1']}
 out={k:v for k,v in out.items()if v is not None};z=[]
 for k,v in out.items():
  if k not in x['score_keys']:x['score_keys'].append(k)
  z.append([x['score_keys'].index(k),v])
 if z not in x['score_records']:x['score_records'].append(z)
 return x['score_records'].index(z)
def coverage(m):
 keys=['offered_rows','scored_rows','games','weeks','fallback_rows','scored_fallback_rows','played_missing_rows','played_zero_rows','participation_states'];z=[]
 for k in keys:
  if k not in m:continue
  if k not in x['coverage_keys']:x['coverage_keys'].append(k)
  z.append([x['coverage_keys'].index(k),m[k]])
 if z not in x['coverage_records']:x['coverage_records'].append(z)
 return x['coverage_records'].index(z)
added=[]
for i,c in enumerate(study['cells']):
 for method,m in c['summaries'].items():
  product='law_median'if method=='CDF_LOWER_MEDIAN'else'law_mean'if method=='CDF_LAW_MEAN_POINT'else'literal_zero_interception_point_NOT_probability'if method.startswith('ZERO_')else'recent_history_point_heuristic_CDF_mean_fallback'
  flag='existing_CDF_law_projection_or_reconstruction_no_new_fit'if method.startswith('CDF_')else'new_point_control_zero_fit_no_probability_claim'
  row=[intern('panel','modern_REG_primary_role'),intern('target',c['target']),intern('method',method),intern('product',product),intern('period',str(c['year'])),score(m),coverage(m),intern('source',sid),pointer(f'/scientific_result/cells/{i}/summaries/{method}'),[intern('flag',flag)]];x['records'].append(row);added.append(len(x['records'])-1)
  # Sourceexactmeanvector andlabelbindings alsoadmitATTmedian intoexisting history-core panel.
  if c['year']==2026 and c['target']=='pass_att'and method=='CDF_LOWER_MEDIAN':
   alias=list(row);alias[0]=intern('panel','common_learner_REG_QB');alias[9]=[intern('flag','same_vector_dual_declared_panels_not_additional_fit_or_football_observations')];x['records'].append(alias);added.append(len(x['records'])-1)
 x['paired_aggregate_references'].append({'source':sid,'pointer':f'/scientific_result/cells/{i}/paired_against_CDF_mean'})
# Add exact independentchartQA receipt asnewsource, notnewscientificobservation.
q=O/'LOWEST_CHART_CDF_ACCEPTANCE_RESULT_V1.json';qb=q.read_bytes();qa=json.loads(qb);assert qa['state']=='PASS'and sha(qb)=='b2cecd14a308c1c20576c687d9ee4a2dbba06a65486537fcf9dc586522bf8caf';x['sources']['S043']={'path':str(q),'bytes':len(qb),'sha256':sha(qb),'kind':'independent_frozen_law_arithmetic_acceptance'}
x['independent_chart_acceptance']={'source':'S043','state':'PASS','scalar_checks':68654,'maximum_independent_CRPS_discrepancy':qa['maximum_absolute_discrepancies']['independent_CRPS'],'model_loads':1,'new_fits_query_inference_HTTP_CAS':0,'scope':'Retained-law independentCDFsum/geometrictail andaggregatearithmetic;notindependentNFLsourceorprospectiveconfirmation.'}
x['method_families'].append({'id':'modern_count_median_completion','state':'COMPLETE5CELLS22PROCEDURESUMMARIES_4CACHEDPROJECTIONS_1RETAINEDLAWQUERY_0FITS','source':str(P),'limits':'PointMAE products; no thresholdprobability/newSITEwin/medianconsumeradmission.'})
for z in x['missing_cells']:
 if z.get('target')in ['pass_td/pass_int','pass_att/pass_int']or(z.get('target')=='pass_att'and z.get('period')==2026):z['need']='COMPLETE_ZERO_FIT_COUNT_MEDIAN_WAVE';z['source']=sid
x['continuation_append']={'version':'lowest-all-method-count-append-v1','original_ledger_sha256':sha(before),'preserved_original_sources':41,'preserved_original_metadata_census':True,'new_sources':2,'new_category_year_cells':5,'new_procedure_summary_cells':22,'additional_panel_alias_records':1,'new_predictive_fits_in_count_study':0,'cached_rescoring_cells':4,'retained_model_query_cells':1,'this_append_NFL_row_decodes_fits_inference_scoring':0,'count_QA_reference':'LOWEST_COUNT_MEDIAN_NUMERICAL_ACCEPTANCE_V1.json (root-owned)'}
# Recomputeaggregateonlyranks fromexistingdata plusnewcells, no source/ledger/filesystem census rerun.
def scores(r):return{x['score_keys'][k]:v for k,v in x['score_records'][r[5]]}
def covers(r):return{x['coverage_keys'][k]:v for k,v in x['coverage_records'][r[6]]}
def meanok(prod):
 if any(v in prod.lower()for v in ['legacy','mixed','blend','heuristic','median','literal','offset','l2','lad','market','captured']):return False
 return any(v in prod.lower()for v in ['law_mean','corrected_mean','poisson_mean','valid_prior_mean','valid_mean_history_recipe','mean_objective_point'])
groups=defaultdict(list)
for i,r in enumerate(x['records']):
 panel,target,prod,period=d['panel'][r[0]],d['target'][r[1]],d['product'][r[3]],d['period'][r[4]];m=scores(r);cv=covers(r)
 for name,metric,valid in [('A_numeric_MAE','MAE',target!='anytime_td'),('B_valid_mean_MSE','MSE',meanok(prod)),('C_full_law_CRPS','CRPS','law'in prod and'point'not in prod),('C_valid_median_MAE','MAE',prod in ['law_median','law_lower_median','lower_CDF_quantile_median']),('D_event_Brier','Brier',target=='anytime_td'or'probability'in prod)]:
  value=m.get(metric)
  if valid and isinstance(value,(float,int))and math.isfinite(value):
   key=(panel,target,period,name,cv.get('scored_rows',cv.get('scored',cv.get('n',cv.get('rows')))),cv.get('population_rows',cv.get('offered',cv.get('offered_rows'))),cv.get('unique_games',cv.get('games')),cv.get('unique_weeks',cv.get('weeks')));groups[key].append((value,i))
rank=[]
for k,v in sorted(groups.items(),key=lambda z:str(z[0])):
 v.sort();minimum=v[0][0];rank.append([intern('panel',k[0]),intern('target',k[1]),intern('period',k[2]),intern('ranking',k[3]),*k[4:],minimum,[i for val,i in v if val==minimum],len(v)])
x['rankings']=rank;x['executed_now']['row_records']=len(x['records']);x['executed_now']['ranking_groups']=len(rank);x['executed_now']['sources']=len(x['sources']);require_original={k:v for k,v in x['sources'].items()if k not in ['S042','S043']};assert enc(require_original)==original_sources and enc(x['metadata_census'])==original_census
contracts=x['method_contract_references'];configrefs=contracts.pop('original_public_config_code_sources');contracts['exact_public_config_code_identity_pointer']={'source':contracts['source'],'pointer':'/sources','filter':'publication==original-public-source and path starts config/,nfl_lab/,tools/','records':len(configrefs),'canonical_list_sha256':sha(enc(configrefs).encode())};body=(enc(x)+'\n').encode();assert len(body)<=1048576;p.write_bytes(body)
md=O/'LOWEST_ALL_METHOD_COMPARISONS_V1.md';text=md.read_text();text=text.replace('**4,809 published','**4,832 published').replace('**41 byte-hashed','**43 byte-hashed').replace('f85f686f4766cfd02963e91f8ad0472b6c611fcbfe9a0410818ecec88c268ba6',sha(body)).replace('1,018,683 bytes',f'{len(body):,} bytes')
text=text.replace('Passing TD/attempt/interception missing modern median cells are assigned to a separate parent-controlled zero-refit continuation; this metadata report does not fill them.','The five missing modern passing TD/attempt/interception median cells are now complete in a separate root-executed zero-fit continuation. They add22 procedure summaries, including all losing simple controls; one2026attempt-median record is also an explicit duplicate panel alias, not another fit or observation.')
append='''\n## Newly completed count-point cells\n\n| Season | Category | CDF lower-median MAE | CDF law-mean MAE |\n|---|---|---:|---:|\n| 2025 | Passing attempts | **8.643072** | 8.663631 |\n| 2025 | Interceptions | **0.549699** | 0.640959 |\n| 2026 W1–6 | Passing TDs | **0.824645** | 0.878612 |\n| 2026 W1–6 | Passing attempts | **7.772512** | 7.898497 |\n| 2026 W1–6 | Interceptions | **0.601896** | 0.628663 |\n\nThese are compatible lower-MAE points from retained laws, not newly demonstrated probability improvements or website wins. The2025history H3 mean point still has lower MAE8.573752 than the2025CDF median. The2026CDF attempt median is lower-MAE than the depth mean point7.818086. Zero-interception point controls lose to theCDF medians in both seasons; a zero point is not a zero event probability. Mean/MSE leaders remain separately identified.\n\nIndependent chart numerical acceptance checked68,654scalars using one trusted model load and no forest queries/fits. Its CDF-sumCRPS with analytic infinite tails differs from the original moment-formula scores by at most7.35e-14. All frozen point values, supported outcomes, bootstrap contrasts and private scorecard rows passed. This verifies retained evidence arithmetic, not independent NFL source truth.\n'''
text=text.replace('Finish parent’s zero-refit median/simple-control cells;','Continue missing product-specific strong controls;');text+=append;md.write_text(text)
print(json.dumps({'state':'APPENDED_NEW_AGGREGATES_ONLY','bytes':len(body),'sha256':sha(body),'records':len(x['records']),'sources':len(x['sources']),'rank_groups':len(rank),'count_summaries':22,'new_NFL_row_decodes_fits_inference_scoring':0,'original41sources_and_metadata_census_unchanged':True}))
