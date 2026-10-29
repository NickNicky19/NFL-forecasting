"""Safe published-aggregate reconciliation only; never reads NFL row data/models."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,gzip,math,re
R=Path('/workspace/nfl-methods-integration');O=R/'reports/next-nfl-checkpoint-20261028';A=Path('/workspace/nfl-full-week-method-audit-20261025/reports/full-week-method-audit-20261025')
S={};source_map={};total=0;rows=[];covers=[];covermap={};notes=[];pairs=[]
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def safe(x):
 if isinstance(x,float)and not math.isfinite(x):return 'POSITIVE_INFINITY'if x>0 else'INVALID_NONFINITE'
 if isinstance(x,dict):return{k:safe(v)for k,v in x.items()}
 if isinstance(x,list):return[safe(v)for v in x]
 return x
def load(p):
 global total
 p=Path(p);b=p.read_bytes();total+=len(b)
 if len(S)>=256 or total>100663296:raise ValueError('bounded aggregate input cap')
 sid=source_map.get(str(p))
 if sid is None:
  sid='S'+str(len(S)+1).zfill(3);source_map[str(p)]=sid
  S[sid]={'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'kind':'published_aggregate_or_metadata'}
 if p.suffix=='.gz':return json.loads(gzip.decompress(b)),sid
 if p.suffix in ['.json','.jsonl']:
  return (json.loads(b)if p.suffix=='.json'else[json.loads(l)for l in b.splitlines()if l.strip()]),sid
 return b.decode(),sid
mapping={'abs_p95':'p95','abs_p90':'p90','abs_max':'max_error','mae':'MAE','mse':'MSE','rmse':'RMSE','bias_prediction_minus_actual':'bias','bias_prediction_minus_outcome':'bias','p95':'p95','p95_abs':'p95','p95_absolute_error':'p95','absolute_error_p95':'p95','absolute_error_p90':'p90','p90_abs':'p90','p90_absolute_error':'p90','absolute_error_max':'max_error','maximum_abs':'max_error','max_absolute_error':'max_error','crps':'CRPS','brier':'Brier','log_score':'NLL','log_loss':'NLL','infinite_log_losses':'infinite_NLL'}
keep={'MAE','MSE','RMSE','bias','p95','p90','max_error','CRPS','Brier','NLL','infinite_NLL','MSE_note','interval80_coverage_inclusive','interval80_mean_width','interval80_score','interval_80_coverage','interval_80_mean_width'}
def metrics(m):
 out={}
 for k,v in m.items():
  kk=mapping.get(k,k)
  if kk in keep:out[kk]=safe(v)
 return out
covkeys={'n','rows','offered','scored','offered_rows','scored_rows','population_rows','unique_games','unique_weeks','games','weeks','fallback_rows','fallback_scored','scored_fallbacks','fallback_offered','unknown_participation','played_missing_statistic','played_zero_rows','played_zero','dnp','DNP','supported_played_outcomes','supported','planned','outcome_states','participation'}
def cov(m):
 return{k:safe(v)for k,v in m.items()if k in covkeys and not isinstance(v,list)}
def cid(c):
 key=enc(c)
 if key not in covermap:covermap[key]=len(covers);covers.append(c)
 return covermap[key]
def add(panel,target,method,product,period,m,c,sid,ptr,flags=None):
 mm=metrics(m)
 if not mm:return
 rows.append([panel,target,method,product,str(period),mm,cid(c),sid,ptr,flags or[]])
def assoc(sid,ptr,x):
 # Save only named paired aggregate comparisons, never player records.
 if x:pairs.append({'source':sid,'pointer':ptr,'aggregate':safe(x)})
# Historic original audit: all exact cell variants; merge metric-projection aliases.
p,s=load(A/'PASSING_EVIDENCE.json.gz');dedup={}
for i,r in enumerate(p['parts']['records.json']):
 key=enc([r['cohort'],r['target'],r['method'],r.get('period','panel_specific'),r['product'],r['source_path'],r['metrics'],r['coverage']])
 if key not in dedup:dedup[key]=[r,i,[r['record_id']]]
 else:dedup[key][2].append(r['record_id'])
for r,i,ids in dedup.values():
 mm=dict(r['metrics']);mm[r['metric']]=r['loss']
 add(r['cohort'],r['target'],r['method'],r['product'],r.get('period','panel_specific'),mm,r['coverage'],s,'/parts/records.json/'+str(i),['ids:'+','.join(ids),r.get('eligibility','see originalsource')])
old_passing_counts={'metric_projection_records':len(p['parts']['records.json']),'deduplicated_contexts':len(dedup),'dedup_rule':'same cohort,target,method,period,product,originalsourcepath,fullmetrics,coverage; metric projection aliases retained as IDs; not distinct methods or games'}
p,s=load(A/'SKILL_EVIDENCE.json.gz')
for i,r in enumerate(p['parts']['named-frontiers.json']['all_named_candidate_cells']):
 m={r['metric']:r['loss'],'bias':r.get('bias'),'p95':r.get('p95')}
 add(r['cohort'],r['target'],r['method'],r['product'],'REG2022_24',m,cov(r),s,'/parts/named-frontiers.json/all_named_candidate_cells/'+str(i),['named source:'+r.get('source','')])
p,s=load(A/'PROBABILITY_PPR_EVIDENCE.json.gz')
for i,r in enumerate(p['parts']['TD_TABLES.json']):
 d=r.get('diagnostics')or{};m={'Brier':r.get('Brier'),'NLL':r.get('NLL'),'infinite_NLL':r.get('infinite_log_losses')};m.update(metrics(d.get('point_metrics',{})))
 c={'offered':r.get('offered'),'scored':r.get('scored'),'fallback_rows':r.get('fallbacks'),'outcome_states':d.get('outcome_states',{})}
 add(r['panel'],'anytime_td',r['method'],'event_probability','panel_specific',m,c,s,'/parts/TD_TABLES.json/'+str(i))
# Fresh permitted-source controls + direct learner annual & pooled summaries.
for file,base in [('source-matched-base-v1/aggregate-report.json',True),('direct-booster-screen-v1/aggregate-report.json',False)]:
 x,s=load(R/'reports'/file);ts=x['report']['targets']if base else x['targets']
 for t,body in ts.items():
  if t in ['fpts','fantasy_ppr']:continue
  for j,r in enumerate(body.get('summaries',[])):
   pop=r.get('population','unknown');period=r.get('period','unknown');panel=('source_matched_2022_24_'if base else'direct_screen_2022_24_')+str(pop)
   ptr=('/report'if base else'')+'/targets/'+t+'/summaries/'+str(j)
   method=r['method'];m=r.get('point_metrics')or{};c=cov(r)
   product='event_probability'if t=='anytime_td'else ('legacy_numeric_point_median_fallback'if method in ['count_A','role_B','count_a','count_boosting_A','role_specific_B']else'original_default_point')
   if not base:product='event_probability'if t=='anytime_td'else('Poisson_mean_objective_point'if t in ['pass_att','pass_cmp','pass_td','pass_int','rush_att','rec']else'absolute_error_point')
   add(panel,t,method,product,period,m,c,s,ptr+'/point_metrics')
   law=r.get('cdf_law')or{}
   for tag in ['mean','median']:
    z=law.get(tag)
    if z:
     z=dict(z)
     if tag=='mean'and r.get('cdf_mean_mse')is not None:z['MSE']=r['cdf_mean_mse']
     add(panel,t,method,'law_'+tag,period,z,c,s,ptr+'/cdf_law/'+tag)
   if law.get('distribution'):add(panel,t,method,'full_conditional_law',period,law['distribution'],c,s,ptr+'/cdf_law/distribution')
# Modern already scored lower medians and lawful count means (all complete strata).
x,s=load(R/'reports/modern-cdf-control-completion-v1/PUBLIC_METRICS.json')
for i,r in enumerate(x['summaries']):
 for pop,m in r['strata'].items():
  if pop not in ['primary_role','all_offered']:continue
  product='law_'+r['product']if'CDF'in r['method']else('corrected_mean_fallback_point'if'STORED_PRIOR_MEAN'in r['method']else'legacy_mixed_fallback_point')
  add('modern_REG_'+pop,r['target'],r['method'],product,r['year'],m,cov(m),s,f'/summaries/{i}/strata/{pop}')
assoc(s,'/paired',x.get('paired'))
# Modern new count learners: separate2025/2026.
x,s=load(R/'reports/modern-2026-cold-grade-v2/PUBLIC_METRICS_v2.json')
for i,r in enumerate(x['candidate_summaries']):
 for pop in ['primary_roles','all_offered']:
  add('modern_REG_'+('primary_role'if pop=='primary_roles'else pop),r['target'],r['method'],'law_mean'if'CDF'in r['method']else'Poisson_mean_objective_point',2026,r[pop],cov(r[pop]),s,f'/candidate_summaries/{i}/{pop}')
for i,r in enumerate(x['control_summaries']):
 for pop in ['primary_roles','all_offered']:
  add('modern_REG_'+('primary_role'if pop=='primary_roles'else pop),r['target'],r['method'],'law_mean'if r.get('mean_eligible')and'CDF'in r['method']else'corrected_mean_fallback_point'if r.get('mean_eligible')else'legacy_mixed_fallback_point',2026,r[pop],cov(r[pop]),s,f'/control_summaries/{i}/{pop}')
x,s=load(R/'reports/modern-ten-control-pipeline-v4-restore4-2025/PUBLIC_METRICS_v2.json')
for i,r in enumerate(x['products']):
 target={'Passing touchdowns':'pass_td','Passing attempts':'pass_att','Interceptions thrown':'pass_int','Completions':'pass_cmp'}.get(r.get('category'),r.get('target'))
 if isinstance(r.get('reference_primary'),dict):add('modern_REG_primary_role',target,'MATCHED_CDF_MEAN_REFERENCE','law_mean',2025,r['reference_primary'],cov(r['reference_primary']),s,f'/products/{i}/reference_primary')
 for pop,key in [('primary_role','candidate_primary'),('all_offered','candidate_all_offered')]:
  add('modern_REG_'+pop,target,r['candidate'],'law_mean'if'CDF'in r['candidate']else'Poisson_mean_objective_point',2025,r[key],cov(r[key]),s,f'/products/{i}/{key}')
# Modern archive method points and full ATD law/probability aggregates from priorsafe composite.
x,s=load(O/'TWELVE_CATEGORY_PRODUCT_DECISIONS.json')
for ci,c in enumerate(x['categories']):
 for yr,key in [(2025,'modern_2025'),(2026,'modern_2026_W1_6')]:
  z=c.get(key)or{}
  for i,r in enumerate(z.get('procedures',[])):
   m={**r.get('errors',{}),**r.get('proper_scores',{})}
   add('modern_REG_primary_role',c['target'],r['procedure'],'event_probability',yr,m,cov(r.get('errors',{})),s,f'/categories/{ci}/{key}/procedures/{i}')
# Recovery report is rounded published aggregate; parse all archivedmethod cells not just winners.
text,s=load(R/'reports/modern-report-recovery-v2/PUBLIC_RESULTS.md')
name_map={'Anytime rushing/receiving TD':'anytime_td','Passing attempts':'pass_att','Passing TDs':'pass_td','Interceptions thrown':'pass_int','Passing yards':'pass_yd','Completions':'pass_cmp','Rushing attempts':'rush_att','Rushing yards':'rush_yd','Receptions':'rec','Receiving yards':'rec_yd','Combined yards':'rush_rec_yd'}
for ln,line in enumerate(text.splitlines(),1):
 parts=[v.strip()for v in line.split('|')]
 if len(parts)==11 and parts[1]in ['2025','2026']and parts[2]in name_map:
  yr,t,method,n,mae,rmse,bias,p95,fb=parts[1:10]
  n=int(n);t=name_map[t];product='event_probability'if t=='anytime_td'else('legacy_mixed_fallback_point'if'COUNT_A'in method else'law_mean'if t in ['pass_att','pass_int','pass_td','pass_cmp']else'law_median'if method=='LAB_CDF'else'absolute_error_point')
  offered=1359 if yr=='2025'and n==664 else 515 if yr=='2026'and n==211 else 2079 if yr=='2025'and n==1566 else 668 if yr=='2026'and n==526 else 7271 if yr=='2025'else 2458
  add('modern_REG_primary_role',t,method,product,yr,{'MAE':float(mae),'RMSE':float(rmse),'bias':float(bias),'p95':float(p95)},{'scored':n,'offered':offered,'games':272 if yr=='2025'else 93,'weeks':18 if yr=='2025'else 6,'fallback_scored':int(fb)},s,'/line/'+str(ln),['published6decimalprecision'])
# History procedures same-representation currentseason comparison, and new completed2025slice.
x,s=load(R/'reports/pass-att-common-learner-2026-v5/PUBLIC_METRICS.json')
for method,m in x['metrics'].items():add('common_learner_REG_QB','pass_att',method,'law_mean',2026,m,cov(m)or x['coverage'],s,'/metrics/'+method)
assoc(s,'/paired',x.get('paired'))
x,s=load(O/'WEEK8_COMMON2025_PUBLIC_RESULTS.json')
for method,m in x['summaries'].items():add('common_learner_REG_QB','pass_att',method,'law_mean',2025,m,cov(m),s,'/summaries/'+method)
assoc(s,'/paired',x.get('paired'))
# Every frozen Week7 complete comparison and timing lane is separate.
x,s=load(R/'reports/week7-nonpassing-completion-20261027/PUBLIC_METRICS.json')
for i,r in enumerate(x['exact_common_point_panels']):
 product='event_probability'if r['category']=='anytime_td'else ('captured_count_expected_point'if r['category']in ['rec','rush_att']else'captured_numeric_point')
 panel='Week7_'+r['evidence_lane']+'_'+r['cohort']+'_'+r['population']
 add(panel,r['category'],r['method'],product,2026,r,cov(r),s,'/exact_common_point_panels/'+str(i))
for i,r in enumerate(x['probability_summaries']):
 panel='Week7_'+r['evidence_lane']+'_'+r['offer_kind']+'_'+r['provider']
 add(panel,r['category'],r['method'],'threshold_probability'if r['offer_kind']!='fixed_anytime_event'else'event_probability',2026,r,cov(r),s,'/probability_summaries/'+str(i))
# Original market wave: all products F/FC/FS/M/H/offeringline; point pools andprobabilitypools NEVERmerged.
x,s=load(R/'reports/historical-market-comparison-no2025-v3/PUBLIC_METRICS.json')
for yi,y in enumerate(x['years']):
 for ci,c in enumerate(y['categories']):
  for pool,product in [('point_common_pool','market_empirical_point'),('probability_common_pool','threshold_probability'),('football_probability_standalone','threshold_probability')]:
   z=c.get(pool)or{}
   for j,m in enumerate(z.get('metrics',[])):
    prod=m.get('point_product_semantics',m.get('probability_semantics',product))
    add('market_no2025_'+pool,c['target'],m['arm'],prod,y['season'],m,{'rows':m.get('rows',z.get('rows')),'games':z.get('games'),'weeks':z.get('weeks')},s,f'/years/{yi}/categories/{ci}/{pool}/metrics/{j}')
# Contemporary market samepool +newLAD complete procedures, allweekly kept via source pointers (not duplicatefulltable).
for p in sorted((O/'contemporary').glob('*.json')):
 x,s=load(p)
 for i,m in enumerate(x.get('metrics',[])):
  prod='event_probability'if x['target']=='anytime_td'else('market_line_heuristic'if m['arm']in ['M','OFFERED_LINE_HEURISTIC']else'LAD_objective_empirical_point'if'LAD'in m['arm']else'CDF_point'if m['arm']=='MODERN_CDF'else'L2_empirical_point')
  add('market_contemporary_same_offered_pool',x['target'],m['arm'],prod,x.get('season',2026),m,{'rows':x['rows'],'games':x['games'],'weeks':x['weeks']},s,f'/metrics/{i}')
# Chart firstpilot all4procedures; target is newchart, not oldwebsitePPR.
x,s=load(O/'CONTINUATION_PREREQUISITES_CHART_PILOT_RESULT_V1.json');z=x['safe_aggregate']
for method,m in z['metrics'].items():
 add('chart_2026_REG_W1_6_source_listed','nick-chart-ppr-v1',method,'valid_prior_mean'if method=='POSITION_CHART_MEAN_2024'else'median_objective_point',2026,m,z['query_coverage'],s,'/safe_aggregate/metrics/'+method)
assoc(s,'/safe_aggregate/paired_contrasts',z.get('paired_contrasts'))
# Paper policies are returns, notprobability accuracy; preserve unresolvedstakes.
paper,s=load(R/'reports/historical-market-no2025-v1/PAPER_PUBLIC_RESULTS.json')
paper_summary={'source':s,'season_policy_totals':paper['season_policy_totals'],'category_policy_totals':paper['category_policy_totals'],'qualification':paper['qualification'],'scope':paper['scope'],'uncertainty':paper['uncertainty']}
# Later recovered/qualified standalone evidence; distinct panels retain negativefindings.
for f,panel,year,key in [('accuracy-wave-20261026/NGBOOST_AGGREGATES.json','NGBoost_pilot_2022_QB',2022,'point_metrics'),('forward-evidence-wave-20261026/HIERARCHICAL_AGGREGATES.json','hierarchical_restoration_2022_QB',2022,'point_metrics'),('ftn-source-risk-prior3-v1/aggregate.json','FTN_risk_2023_QB',2023,'metrics')]:
 x,ss=load(R/'reports'/f)
 for method,m in x[key].items():
  c={'scored':m.get('n'),'offered':x.get('offered',x.get('offered_rows')),'games':x.get('games',x.get('offered_games')),'weeks':x.get('weeks',x.get('offered_weeks')),'unknown_participation':x.get('unknown',x.get('unknown_participation',x.get('coverage',{}).get('QB_unknown_participation')))}
  add(panel,'pass_int',method,'law_mean'if method in ['leaf_cdf','distribution_split_cdf','threshold_cdf']else'corrected_mean_fallback_point',year,m,c,ss,'/'+key+'/'+method)
 if 'native_law_secondary'in x:
  z=x['native_law_secondary'];add(panel+'_model_only','pass_int','NGBoost16_native_Poisson','full_conditional_law',year,{'NLL':z['log_loss'],'infinite_NLL':z['positive_infinite']},{'rows':z['denominator']},ss,'/native_law_secondary',['modelonly632;notfullsystem633proper-scorewin'])
# Original2024 repaired-zero85products: allpointproducts restored, originals linkedunchanged.
x,ss=load(R/'reports/accuracy-wave-20261026/RESTORED_2024_AGGREGATES.json')
for i,r in enumerate(x['products']):
 product=('law_mean'if r['point_column']=='mean'and'cdf'in r['method']else'corrected_mean_fallback_point'if r['method']=='count_A_mean_v2'else'law_median'if r['point_column']=='median'else'event_probability'if r['point_column']=='probability'else'Poisson_mean_objective_point'if r['target']in ['pass_td','pass_cmp','pass_att','pass_int','rush_att','rec']else'absolute_error_point')
 add('FTN_2024_zero_restored_cached',r['target'],r['method'],product,2024,r['restored'],{'scored':r['restored'].get('n'),'offered':r.get('finite_offered'),'games':r.get('paired_games'),'weeks':r.get('paired_weeks'),'fallback_offered':r.get('fallback_offered')},ss,'/products/'+str(i)+'/restored')
# Later independentlyPBP-qualified2024table is a differentpopulation, notsamezero repair.
text,ss=load(R/'reports/pbp-2024-qualified-cached-grade-v1-20261027/ALL_PRODUCT_ERRORS.md')
for lineno,line in enumerate(text.splitlines(),1):
 values=[v.strip()for v in line.split('|')]
 if len(values)==10 and values[1]in ['Rush attempts','Receptions'] and values[2]in ['mean','median']:
  t='rush_att'if values[1]=='Rush attempts'else'rec';product='law_'+values[2]if'CDF'in values[3]or values[3]=='Role prior'else'corrected_mean_fallback_point'if'Count A'in values[3]else'Poisson_mean_objective_point'
  m=dict(zip(['MAE','MSE','RMSE','bias'],map(float,values[5:9])))
  add('PBP_2024_qualified_played_zero',t,values[3],product,2024,m,{'scored':int(values[4]),'offered':2047 if t=='rush_att'else 7148,'unknown_participation':384 if t=='rush_att'else 1065,'played_missing_statistic':12 if t=='rush_att'else 24,'games':272,'weeks':18},ss,'/line/'+str(lineno),['published4decimalprecision'])
# AlreadycompletedF1-F3 arehistoryaverages, F4reusedworkload; notsamelearnerCDFexperiment.
text,ss=load(R/'reports/pass-att-four-training-families-v1/PUBLIC_RESULTS.md');year=None
for lineno,line in enumerate(text.splitlines(),1):
 if line=='### 2025':year=2025
 elif line=='### 2026':year=2026
 v=[z.strip()for z in line.split('|')]
 if year and len(v)==9 and v[1].startswith(('F1 ','F2 ','F3 ','F4 ','Recent 3 control','Pooled 8 control','Frozen CDF mean'))and v[2].isdigit():
  m=dict(zip(['MSE','MAE','RMSE','bias','p95'],map(float,v[3:8])))
  add('history_averages_F1F3_reused_workload_F4','pass_att',v[1],'valid_mean_history_recipe',year,m,{'scored':int(v[2]),'offered':1359 if year==2025 else 515,'games':272 if year==2025 else 93,'weeks':18 if year==2025 else 6,'unknown_participation':695 if year==2025 else 304},ss,'/line/'+str(lineno),['published3decimalprecision;F3fixed365notlearneddecay'])
# Latest QBderived-countcreditclosure; originalpositiveonly/savedvintagefindings notoverwritten.
x,ss=load(R/'reports/accuracy-wave-20261026/QB_DERIVED_COUNT_CREDIT_CLOSURE_AGGREGATES.json')
for i,r in enumerate(x['point_summaries']):
 if r.get('category')not in ['pass_yd','pass_td','pass_cmp','pass_att','pass_int']:continue
 panel='QB_W7_creditclosure_'+r['evidence_lane']+'_'+r['cohort']
 add(panel,r['category'],r['method'],'captured_expected_point'if r['category']!='pass_yd'else'captured_numeric_point',2026,r,cov(r),ss,'/point_summaries/'+str(i))
for i,r in enumerate(x['probability_summaries']):
 if r.get('category')not in ['pass_yd','pass_td','pass_cmp','pass_att','pass_int']:continue
 panel='QB_W7_creditclosure_'+r['evidence_lane']+'_'+r['offer_kind']+'_'+r['provider']
 add(panel,r['category'],r['method'],'threshold_probability',2026,r,cov(r),ss,'/probability_summaries/'+str(i))
# Additional exact2025fullResponseCDFpropermetrics, no point-onlylawfabrication.
x,ss=load(R/'reports/modern-ten-control-pipeline-v4-restore4-2025/PUBLIC_METRICS_v2.json')
for i,r in enumerate(x['products']):
 for key in ['proper_distribution_all_supported_offered','proper_distribution_primary']:
  if isinstance(r.get(key),dict):
   target={'Passing touchdowns':'pass_td','Passing attempts':'pass_att','Interceptions thrown':'pass_int','Completions':'pass_cmp'}.get(r.get('category'),r.get('target'))
   add('modern_2025_'+key,target,r['candidate'],'full_conditional_law',2025,r[key],cov(r[key]),ss,'/products/'+str(i)+'/'+key)
# Newrootexecutedstrongsame-chartCDFcontrol; aggregateonly, no row/modeldecode.
chart_path=Path('/workspace/nfl-next-chart-ppr-20261028/reports/next-nfl-checkpoint-chart-ppr-20261028/SAFE_AGGREGATE_CDF_CONTROL_V1.json')
new_chart_summary=None
if chart_path.is_file():
 z,ss=load(chart_path);new_chart_summary=z
 for method,m in z['metrics'].items():
  product='law_mean'if method in ['LEAF_CDF_CHART_MEAN_V1','ROLE_LAW_CHART_MEAN_V1']else'law_median'if method in ['LEAF_CDF_CHART_MEDIAN_V1','ROLE_LAW_CHART_MEDIAN_V1']else'valid_prior_mean'if method=='POSITION_CHART_MEAN_2024'else'median_objective_point'
  add('chart_2026_REG_W1_6_source_listed', 'nick-chart-ppr-v1',method,product,2026,m,z['query_coverage'],ss,'/metrics/'+method)
 for method,m in z['distribution_metrics'].items():
  mm=dict(m);nl=mm.get('negative_log_mass',{});mm['NLL']='POSITIVE_INFINITY'if nl.get('state')=='POSITIVE_INFINITY'else nl.get('value');mm['infinite_NLL']=nl.get('positive_infinite_rows')
  add('chart_2026_REG_W1_6_source_listed','nick-chart-ppr-v1',method,'full_conditional_law',2026,mm,z['query_coverage'],ss,'/distribution_metrics/'+method)
 assoc(ss,'/paired_contrasts',z['paired_contrasts'])
# Exactpublicconfiguration/code identities fromdatedaudit snapshot; learned/privatebodyomissions remainomitted.
audit_manifest,audit_sid=load(A/'SOURCE_MANIFEST.json')
contract_references={'source':audit_sid,'dated_public_snapshot':audit_manifest['public_research_snapshot'],
 'original_public_config_code_sources':[r for r in audit_manifest['sources']if r['publication']=='original-public-source'and(str(r['public_path_or_metadata_kind']).startswith(('config/','nfl_lab/','tools/')))],
 'passing_recipes_pointer':{'source':'S001','pointer':'/parts/RECIPES.json'},
 'skill_config_pointer':{'source':'S002','pointer':'/parts/method-configs.json'},
 'probability_formula_pointer':{'source':'S003','pointer':'/parts/FORMULAS_AND_METHODS.json'},
 'learned_parameter_bodies':'Omitted frompublic aggregate; original privateartifacts retained; not reconstructablefromhashalone.'}
# Families and supersededdatedstatuses; preserve old41recipes.
fam,s=load(A/'METHOD_INVENTORY.json');families=fam['methods']
updates={'ngboost':('COMPLETE_SMALL_INTERCEPTION_PILOT_ONLY','reports/accuracy-wave-20261026/README.md'),'ftn_targeted':('COMPLETE_RISK_FEATURE_COMPARISON_NEGATIVE_OTHER_FTN_UNTESTED','reports/ftn-source-risk-prior3-v1/RESULTS.md'),'dynamic_workload':('COMPLETE_FIXED_NUMERICAL_NEGATIVE_PARENT_RUNTIME_FAILURE_RETAINED','reports/dynamic-workload-fixed-forward-v1/README.md'),'exact_ppr':('OLD_SITE_TARGET_UNSUPPORTED_NEW_CHART_SEPARATE','reports/next-nfl-checkpoint-20261028/CONTINUATION_PREREQUISITES_CHART_PILOT_RESULT_V1.json')}
for f in families:
 if f['id']in updates:f['dated_state']=f['state'];f['state'],f['latest_source']=updates[f['id']]
for id,state,source in [('modern_count_cdf','COMPLETE7RETAINED_LAWS_MEAN_AND_MEDIAN','reports/modern-cdf-control-completion-v1/PUBLIC_METRICS.json'),('modern_counts','COMPLETE9VALID_OF10OPPORTUNITIES_1FAILED','reports/modern-2026-cold-grade-v2/PUBLIC_METRICS_v2.json'),('common_history_2026','COMPLETE17FITS_PRIMARY_MSE_ALL_LOSE_DEPTH_MAE_LOWER','reports/pass-att-common-learner-2026-v5/PUBLIC_METRICS.json'),('common_history_2025','COMPLETE52FITS_H2_MSE_H3_MAE_55NEWOPPORTUNITIES_OLDFAILURES_RETAINED','reports/next-nfl-checkpoint-20261028/WEEK8_COMMON2025_PUBLIC_RESULTS.json'),('chart_ppr_v1','COMPLETE1HGBPOINTFIT_PLUS1STRONGCDF_CONTROL_FIT_FUTURECONSUMER_UNREADY','reports/next-nfl-checkpoint-20261028/CONTINUATION_PREREQUISITES_CHART_PILOT_RESULT_V1.json'),('historical_market_no2025','COMPLETE_TIMING_UNVERIFIED_EXPLORATORY','reports/historical-market-comparison-no2025-v3/PUBLIC_METRICS.json'),('contemporary_L2_LAD_market','COMPLETE_CONTROLLED_NEWER_FOOTBALL_AND_OBJECTIVE_CORRECTIONS','reports/next-nfl-checkpoint-20261028/contemporary'),('Week7_numerical_capture','COMPLETE_AVAILABLE_GENUINE5POINTGAMES_OTHER_TIMING_SEPARATE_NOTFULLWEEK','reports/week7-nonpassing-completion-20261027/PUBLIC_METRICS.json')]:families.append({'id':id,'state':state,'source':source})
# Fullsourceindex and canonicalmetadata: scanalltext/JSONevents, no mutation.
index,idx=load(R/'reports/RESEARCH_INDEX.md');canonical,can=load(R/'execution/ledger.jsonl')
index_links=sorted(set(re.findall(r'\]\(([^)]+)\)',index)))
canonical_events=Counter(str(e.get('event',e.get('type',e.get('state','NO_NAMED_EVENT'))))for e in canonical)
private,prv=load('/workspace/website-methods-research/EXECUTION_LEDGER.json');private_entries=[]
for e in private['entries']:
 p=Path(e['artifact']);v={'event':e['event'],'expected_sha256':e.get('sha256'),'exists':p.is_file()}
 if p.is_file():
  b=p.read_bytes();v.update(bytes=len(b),actual_sha256=hashlib.sha256(b).hexdigest());v['byte_hash_matches']=v['actual_sha256']==e.get('sha256')
 private_entries.append(v)
# Metadata-onlyexplicitper-trialcensus. Neverreadforecast/qualificationrowfiles.
base=Path('/workspace/website-methods-research');paths=sorted(p for p in base.rglob('*')if p.is_file()and p.name in ['events.jsonl','attempt-consumed.json'])
if len(paths)>512 or sum(p.stat().st_size for p in paths)>2097152:raise ValueError('private metadata census cap')
private_files=[];ev=Counter();attempts=Counter();failures=Counter()
for p in paths:
 b=p.read_bytes();vals=[json.loads(l)for l in b.splitlines()if l.strip()]if p.suffix=='.jsonl'else[json.loads(b)]
 ee=Counter(str(v.get('event',v.get('state','unnamed')))for v in vals)
 ev.update(ee)
 if p.name=='attempt-consumed.json':attempts[str(p.parent.relative_to(base))]+=1
 for v in vals:
  name=str(v.get('event',v.get('state','unnamed')))
  if any(z in name.upper()for z in ['FAIL','ERROR','EXHAUST','CONSUMED']):failures[name]+=1
 private_files.append([str(p.relative_to(base)),len(b),hashlib.sha256(b).hexdigest(),dict(ee)])
metadata_census={'index_source':idx,'index_link_count':len(index_links),'index_link_targets':index_links,'canonical_source':can,'canonical_records':len(canonical),'canonical_event_counts':dict(canonical_events),'dated_private_ledger_source':prv,'dated_private_entries':private_entries,'private_named_metadata_files':len(paths),'private_named_metadata_bytes':sum(p.stat().st_size for p in paths),'distinct_consumed_receipt_directories':len(attempts),'event_record_counts_not_independent_fit_counts':dict(ev),'failure_and_consumption_event_counts':dict(failures),'private_named_metadata_manifest_columns':['relative_path','bytes','sha256','event_counts'],'private_named_metadata_manifest':private_files,'private_attempt_census_complete':False,'limit':'Entire explicit named metadata census inspected; arbitrary per-study receipts/results outside these names and unavailable sourceoriginals not exhaustively reconciled. Public ledger is complete only for listed sourcecells, not proof every privateattempt/result ispublic.'}
# Classifyadmissibleoutputcontracts conservatively. Contract changesneednormalrelease.
def meanok(prod,method):
 p=prod.lower();m=method.lower()
 if any(z in p for z in ['legacy','mixed','blend','heuristic','median','literal','offset','l2','lad','market','captured']):return False
 if any(z in p for z in ['law_mean','corrected_mean','poisson_mean','valid_prior_mean','valid_mean_history_recipe','mean_objective_point']):return True
 return False
def metricgroups():
 groups=defaultdict(list)
 for i,r in enumerate(rows):
  panel,t,m,prod,period,mm,cv,src,ptr,fl=r
  for ranking,metric,valid in [('A_numeric_MAE','MAE',t!='anytime_td'),('B_valid_mean_MSE','MSE',meanok(prod,m)),('C_full_law_CRPS','CRPS','law'in prod and'point'not in prod),('C_valid_median_MAE','MAE',prod in ['law_median','law_lower_median','lower_CDF_quantile_median']),('D_event_Brier','Brier',t=='anytime_td'or'probability'in prod)]:
   v=mm.get(metric)
   if valid and isinstance(v,(int,float))and math.isfinite(v):groups[(panel,t,period,ranking,cv)].append((v,i))
 # Coverages are compared byexactregistered populationfields; interningcoverageincludesfallbackswhichcanvary.
 merged=defaultdict(list)
 for (p,t,y,k,cv),v in groups.items():
  c=covers[cv];key=(p,t,y,k,c.get('scored_rows',c.get('scored',c.get('n',c.get('rows')))),c.get('population_rows',c.get('offered',c.get('offered_rows'))),c.get('unique_games',c.get('games')),c.get('unique_weeks',c.get('weeks')))
  merged[key]+=v
 out=[]
 for key,vals in sorted(merged.items(),key=lambda x:str(x[0])):
  vals.sort();v=vals[0][0];out.append([*key,v,[i for value,i in vals if value==v],len(vals)])
 return out
rankings=metricgroups()
# Source/pointerprovenance not row matching: samecounts don'tproveidenticalidentities.
result={'schema_version':'lowest-all-method-safe-aggregate-v1','scope':'Every inspected named aggregatecell incl losses/aliases; no newNFLfit/inference/grading/modeldeserialization; not a universal all-privateattempt proof','actual_agent_model_effort':'UNATTESTED','scientific_limits':['Do not compare errors across distinct panels/products/years/timinglanes/populations.','Chronological reconstructed development remains exposed and timing assumptions remain.','A ranking includes all numericpoints retainingsemanticlabels; B restricts validmeancontracts; C properlaws only; D probability and paperreturns separate.','Equal samplecounts do not independently prove rowidentity compatibility. Source-declared commonpanels retained; no new playerkeyvalidation.','Full calibration, uncertainties and tails remain linked by exactsourcepointer where compactsummary omits them.','No ledger row selects/deploys a method. Production and provisional-policy changes ownedbyroot/integrator.'], 'sources':S,'coverage_records':covers,'records_columns':['panel','target','method','product_contract','period','scores','coverage_id','source_id','source_pointer','limits_or_aliases'],'records':rows,'rankings_columns':['panel','target','period','ranking','scored_rows','offered_rows','games','weeks','lowest_recorded_loss','leader_record_indices','compared_records'],'rankings':rankings,'ranking_comparability':'Only samepanel/target/period/productscore and publishedcoverage grouping. Some panels explicitlypairwise subsets; pointersremainauthority. Never mergepanel minima into universalwinner.','original_passing_projection_deduplication':old_passing_counts,'method_families':families,'method_contract_references':contract_references,'paired_aggregate_references':[{k:v for k,v in p.items()if k!='aggregate'}for p in pairs],'paper_selection':paper_summary,'metadata_census':metadata_census,'missing_cells':[{'target':'pass_td/pass_int','period':2026,'need':'ROOT_SEALED_ZERO_FIT_CACHED_MEDIAN_EXTRACTION','source':'retained2026LAB_CDF.parquet mean/median columns footer-authenticated; parentnumericalworkerownsvalues'},{'target':'pass_att','period':2026,'need':'ROOT_SEALED_RETAINED_LAW_INFERENCE_NO_REFIT','source':'futuretrained leafCDFartifact; originalreconstructedcontrolstoredmeanonly'},{'target':'pass_att/pass_int','period':2025,'need':'ROOT_SEALED_ZERO_FIT_CACHED_MEDIAN_EXTRACTION','source':'retained2025LAB_CDF.parquet median populated'},{'target':'allnumeric','need':'simplemean/median_controls_missing_in_modernpanel','source':'prior/currentmean/medianneedsqualifiedearlier-only calculation; nevertransferoldercontrols'},{'target':'exact_old_website_PPR','need':'UNSUPPORTED_COMPLETE_EXACTLABELS','source':'newchartlabels/models notsameoldwebsitecontract'}],'executed_now':{'metadata_only':True,'new_fits':0,'new_forecasts':0,'new_NFL_scoring_runs':0,'sources':len(S),'read_bytes':total,'row_records':len(rows),'ranking_groups':len(rankings),'metadata_preparation_failures':['onePythonSyntaxErrorbeforeinputs','twoKeyErrorsforoptionalaggregatefields;noNFLdecode','threeprewriteoutputcaprefusals1.89MiB1.28MiB1.09MiB; compactlosslessmetadataencodingresolved;noNFLfitbudgetused']},'publication':'Permittedpublishedaggregatevalues andnon-sensitive metadata; no rawNFLrows, modelparameters, secrets orsourcequotes'}
# Intern repeated labels only; every score and original sourcepointer is retained.
labels={k:[]for k in ['panel','target','method','product','period','source','pointer','flag','ranking']}
label_maps={k:{}for k in labels}
def intern(k,v):
 key=enc(v)
 if key not in label_maps[k]:label_maps[k][key]=len(labels[k]);labels[k].append(v)
 return label_maps[k][key]
compact=[]
for r in rows:
 compact.append([intern('panel',r[0]),intern('target',r[1]),intern('method',r[2]),intern('product',r[3]),intern('period',r[4]),r[5],r[6],intern('source',r[7]),intern('pointer',r[8]),[intern('flag',f)for f in r[9]]])
result['records']=compact
result['rankings']=[[intern('panel',r[0]),intern('target',r[1]),intern('period',r[2]),intern('ranking',r[3]),*r[4:]]for r in rankings]
# Repeated numerical summaries are identities, not separate observations.
metric_values=[];metric_map={}
for r in compact:
 key=enc(r[5])
 if key not in metric_map:metric_map[key]=len(metric_values);metric_values.append(r[5])
 r[5]=metric_map[key]
score_keys=sorted({k for m in metric_values for k in m});result['score_keys']=score_keys
result['score_encoding']='Each score record is list of key-index,value pairs; indices refer score_keys.'
result['score_records']=[[[score_keys.index(k),v]for k,v in m.items()]for m in metric_values]
result['records_columns'][5]='score_record_id'
coverage_keys=sorted({k for c in covers for k in c})
result['coverage_keys']=coverage_keys
result['coverage_records']=[[[coverage_keys.index(k),v]for k,v in c.items()]for c in covers]
result['coverage_encoding']='Each coverage record is list of key-index,value pairs; indices refer coverage_keys.'
pointer_tokens=[];pointer_map={}
def pointer_token(v):
 if v not in pointer_map:pointer_map[v]=len(pointer_tokens);pointer_tokens.append(v)
 return pointer_map[v]
labels['pointer']=[[pointer_token(v)for v in value.split('/')]for value in labels['pointer']]
labels['pointer_tokens']=pointer_tokens
result['pointer_encoding']='Join pointer_tokens indexed by each pointer array with slash to recover original sourcepointer exactly.'
result['label_dictionaries']=labels
result['dictionary_encoding']='Record panel,target,method,product,period,source,pointer and flags index corresponding label_dictionaries arrays; rankings first4fields index panel,target,period,ranking.'
result['metadata_census'].pop('index_link_targets',None)
fullcounts=result['metadata_census'].pop('canonical_event_counts')
result['metadata_census']['canonical_event_counts_sha256']=hashlib.sha256(enc(fullcounts).encode()).hexdigest()
result['metadata_census']['canonical_distinct_event_names']=len(fullcounts)
result['metadata_census']['canonical_most_frequent20_event_counts']=dict(Counter(fullcounts).most_common(20))
manifest=result['metadata_census'].pop('private_named_metadata_manifest')
result['metadata_census']['private_named_metadata_manifest_sha256']=hashlib.sha256(enc(manifest).encode()).hexdigest()
result['metadata_census']['private_named_metadata_directory_counts']=dict(Counter(v[0].split('/')[1]if v[0].startswith('resumed/')else'old_root'for v in manifest))
result['metadata_census']['private_named_metadata_manifest_reproduction']='Regenerate metadata-only filemanifest with this pinned runner; full ordered filehash manifest is hashed rather than publicly duplicating private paths.'
# Reduceonlyduplicatemetadata, neverdroprecordedlosses. Alloriginalreports remainlinked.
body=(enc(safe(result))+'\n').encode()
if len(body)>1048576:
 result['metadata_census'].pop('index_link_targets',None)
 body=(enc(safe(result))+'\n').encode()
if len(body)>1048576:
 print('sizes',json.dumps({k:len(enc(v))for k,v in result.items()}),'rows',len(rows));raise ValueError('outputcapbeforewrite '+str(len(body)))
p=O/'LOWEST_ALL_METHOD_LEDGER_V1.json';p.write_bytes(body)
report=['# All-method comparison ledger — bounded reconciliation','',f'This checkpoint reconciles **{len(rows)} published aggregate procedure/product cells** from **{len(S)} byte-hashed sources**. It runs **zero NFL fits, predictions or new outcome scoring**. Losses, aliases and distinct evidence panels remain separate.','',f'[Complete safe aggregate ledger](LOWEST_ALL_METHOD_LEDGER_V1.json) · SHA256 `{hashlib.sha256(body).hexdigest()}` · {len(body):,} bytes.','', '## Read this correctly','', '- **A: MAE** compares numeric points in category units and preserves each point’s original meaning. A mean can have a lower MAE than another model without becoming a median.', '- **B: MSE/RMSE** admits authentic mean procedures; legacy mixed-fallback points and arithmetic median blends are separate empirical point recipes.', '- **C: Full laws** require a real distribution and declared proper score. Point-only CatBoost/HGB outputs do not receive invented distributions.', '- **D: Probabilities** use Brier/log loss on exact event contracts. Paper returns are separate; low forecast error is not profitable selection.', '- There is no pooled all-years champion table: source populations, labels, horizons and availability differ. A laboratory lead is not a demonstrated current-website win.','', '## Already scored count medians that must stay visible','', '| Season | Category | CDF mean MAE | CDF lower-median MAE |','|---|---|---:|---:|','| 2025 | Passing TDs | 0.884272 | **0.826807** |','| 2025 | Completions | 5.857571 | **5.807229** |','| 2025 | Carries | 3.610262 | **3.408685** |','| 2025 | Receptions | 1.279453 | **1.178659** |','| 2026 W1–6 | Completions | 5.196570 | **5.118483** |','| 2026 W1–6 | Carries | 3.829856 | **3.661597** |','| 2026 W1–6 | Receptions | 1.341470 | **1.252569** |','', 'The above are already executed source results, not newly generated forecasts. Passing TD/attempt/interception missing modern median cells are assigned to a separate parent-controlled zero-refit continuation; this metadata report does not fill them.','', '## Distinct recent-season evidence','', '- **2026 attempts:** depth-added CDF mean has MAE **7.818086**, below Response-CDF mean **7.892962**, but the depth procedure worsens its registered MSE, bias and p95. Do not call it a primary mean-score win.', '- **2025 attempts:** H2 prior-plus-current wins MSE (**120.305733** versus retained CDF **124.098901**); H3 fixed365-day history has the lowest tested history-slice MAE (**8.573752**). Completed 2026 H2 loses; no universal history winner.', '- **2026 receiving yards:** CDF MAE **16.054624** versus CatBoost **16.105430**; 2025 **15.126912** versus **15.146870**. The leads are small and CDF has worse signed underprediction.', '- **2026 combined yards:** CDF MAE **19.925906** versus CatBoost **20.032110**; 2025 **19.585080** versus **19.615066**. Score the total itself; component medians do not generally add.', '- **Anytime TD:** 2026 CatBoost Brier **0.136471970** is lower than CDF **0.136977356** and equal blend **0.136583353**. In 2025 CDF **0.138396228** leads equal blend **0.138445700** and CatBoost **0.138993616**. A 2026 winner is not automatically the provisional policy’s selected winner.', '- **New chart PPR:** one HGB median-objective point fit has MAE **4.702027** versus position median **5.739191** on **1,954/2,117** source-listed 2026 rows, 93 games/six weeks. This is a new chart target, not the old website PPR. Strong same-chart CDF work is a separate execution.','', '## Market and Week 7 panels','', 'The ledger includes football-only, corrected, shrinkage, market-only, offered-line and L2/LAD hybrid results. A market line is retained as a point heuristic rather than an authenticated mean/median/full law. Original no-2025 market work remains timing-unverified exploratory evidence; qualified 2025 football stays permitted. Numerical point common pools and market-probability common pools are separate.','', 'Week 7 genuine pregame, all-timing descriptive and post-start reconstruction panels retain their exact names. The complete saved week is not claimed to be a full-week genuine 3–5-model tournament. Original predictions and actuals stay private; aggregates reference the existing safe scorecard reports.','', '## Private record reconciliation and its exact limit','', f'The dated private execution ledger has **{len(private_entries)} entries**; original referenced bytes were hash-checked where available. The canonical ledger has **{len(canonical)} JSON records** at read. A complete named-file census inspected **{len(paths)}** `events.jsonl` / `attempt-consumed.json` files, **{sum(p.stat().st_size for p in paths):,} bytes**, preserving event/consumption/failure counts and file hashes. These are metadata events, **not a new total of independent fits or football observations**.','', '**Private-attempt census completeness is false.** Arbitrarily named per-study receipts, unavailable original executables and unretained vectors were not independently reconstructed. This publication therefore does not assert that every private attempt or dataset is public. Exact inspected source identities and scope are in the ledger.','', '## Operational meaning','', 'Research rankings do not alter selection, capture or production. Root owns the separately versioned research-informed provisional decision, authentic future artifact admission and actual served readback. Original P2, scientific registrations, failures and all negative weeks remain unchanged.','', '## Strong same-chart CDF follow-up','', 'The separately executed one-fit CDF now has lower-median MAE **4.679406** versus HGB **4.702027** (about **0.48%** lower). The game interval crosses zero; bias and p95 worsen. Its true mean has MSE **41.61016**, and proper-law CRPS is **3.306214** versus role-prior law **4.208508**. These are matched same-chart research results, not a current-website win or a completed future/consumer package. All eight point procedures and two proper-law products are retained in the ledger.','', '## Remaining work','', 'Finish parent’s zero-refit median/simple-control cells; continue qualified role/opportunity/NGS additions within existing finite registrations; admit valid future artifacts and capture genuine original forecasts. Missing prices or one blocked category does not stop supported point research.','']
md='\n'.join(report).encode();assert len(md)<=131072;(O/'LOWEST_ALL_METHOD_COMPARISONS_V1.md').write_bytes(md)
print(json.dumps({'state':'SAFE_AGGREGATE_LEDGER_WRITTEN','bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'records':len(rows),'sources':len(S),'rankings':len(rankings),'private_named_files':len(paths),'MD_bytes':len(md),'new_NFL_work':0}))
