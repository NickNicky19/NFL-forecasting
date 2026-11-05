"""A's qualification contribution from authenticated existing aggregates.

C owns the shared table. No new grader, fits, model inference or NFL evidence.
"""
from pathlib import Path
import collections
import datetime
import gzip
import hashlib
import io
import json
import resource
import signal
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
OUT=ROOT/'reports/abc-championship/post-wave-5w-v1'


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    begin=time.monotonic();cpu=time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(60,61));resource.setrlimit(resource.RLIMIT_AS,(1610612736,)*2);signal.alarm(90)
    from tools.category_topfive_matched12_storage_v1 import open_store,GO
    from nfl_lab.product_test_week_floor_v1 import evaluate
    store,_=open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=GO,readonly=True)
    cfg=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()))
    path=store.forward_root/'research'/cfg['run_id']/'RESULTS.zip'
    digest='5e30c74d98b07acc76cd54a7731570f4f9e4b5843c970a69ae30996cea00fe77'
    store.validate_reference(path,digest)
    with zipfile.ZipFile(path)as z:raw=z.read('AGGREGATES.json.gz')
    if sha(raw)!='2275410cce9a7ae7937f3b03ffc0e264534a4b55c09ab93fe9b7f2f15fcfee5c':raise ValueError('original all-category aggregate changed')
    document=json.loads(gzip.decompress(raw));catalog=document['catalog']
    oldfreeze=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-freeze-v1_2.json.gz').read_bytes()))
    roles=oldfreeze['primary_roles_by_target']
    contributions=[]
    def identity(target,method,product,policy,role_scope,version):
        return {'procedure_version':version,'target':target,'output':product,'role_scope':role_scope,
                'selection_policy':policy,'history_rule':'Original bound annual/earlier-only procedure; exact per-method code/history retained in original catalog/source manifests.'}
    def append(key,source,weekly,*,metric,metrics,evidence,method):
        records=[{'key':key,'season':int(w['season']),'week':int(w['week']),
                  'completed_outcomes':w['scored']>0,'scored_eligible_cases':int(w['scored'])}for w in weekly]
        result=evaluate(key,records)
        contributions.append({**result,'session':'A','method_alias':method,'evidence_tier':evidence,
            'metric':metric,'retained_aggregate_metrics':{k:metrics[k]for k in ['planned','scored','games','weeks','MAE','MSE','RMSE','bias','p95_AE','p95_absolute_error','opportunities','decided','correct','hit_rate','no_lean','abstain','missing_law','missing_prediction_rows','unknown_participation_rows','over','under','OVER','UNDER','COMBINED','eligible','unavailable','abstentions','states','coverage']if k in metrics},'source':source,'weekly_support':weekly,
            'chronology':'Original earlier-only forecast origin/feature contracts preserved; current-vintage and quote-time uncertainty remains. CountA exact model training cutoff/parity independently verified this wave.',
            'source_vintage_quote_timing_limits':'Retrospective reconstruction, not original issued website selections. Week floor does not remove source uncertainty.',
            'export_status':'Public aggregate contribution; private raw bytes remain owner-controlled; current producer and website admission separate.'})
    for record in document['headline_numeric']['records']:
        if record['scope']!='FULL_REGISTERED_METHOD_POPULATION':continue
        target,method,product=record['target'],record['method'],record['product'];meta=catalog[target][method]
        version=meta.get('product_procedure_versions',{}).get(product,meta['procedure_version'])
        weekly=[]
        for w in record.get('weekly',[]):
            m=w['metrics'];weekly.append({'season':2026,'week':int(w['week']),'scored':int(m['scored']),
                'planned':m.get('planned'),'games':m.get('games'),'unknown_participation':m.get('unknown_participation'),
                'missing_prediction':m.get('missing_prediction'),'fallback_scored':m.get('fallback_scored'),
                'MAE':m.get('MAE'),'MSE_or_event_Brier':m.get('MSE')})
        for objective in ['EVENT_PROBABILITY']if target=='anytime_td'else['NUMERIC_MAE']+(['EXPECTED_MEAN_MSE']if product in ['mean','mean_objective_point']else[]):
            key=identity(target,method,product,objective,roles[target],version)
            append(key,'Original RESULTS.zip/headline_numeric FULL_REGISTERED_METHOD_POPULATION primary-role-filtered by primary_numeric()',weekly,
                metric='Brier'if objective=='EVENT_PROBABILITY'else'MSE'if objective=='EXPECTED_MEAN_MSE'else'MAE',
                metrics=record['metrics'],evidence='EXPOSED_CURRENT_VINTAGE_CHRONOLOGICAL_RECONSTRUCTION',method=method)
    for record in document['recorded_line_point_decisions']['records']:
        target,method,product,policy=record['target'],record['method'],record['product'],record['policy'];meta=catalog[target][method]
        version=meta.get('product_procedure_versions',{}).get(product,meta['procedure_version'])
        weekly=[]
        for w in record['weekly']:
            m=w['metrics'];weekly.append({'season':2026,'week':int(w['week']),'scored':int(m.get('decided',m.get('over',{}).get('decided',0)+m.get('under',{}).get('decided',0))),
                'eligible_or_opportunities':m.get('opportunities'),'games':m.get('games'),'correct':m.get('correct'),
                'over':m.get('over'),'under':m.get('under'),'no_lean':m.get('no_lean'),
                'unknown_participation':m.get('unknown_participation_rows'),'fallback_rows':m.get('fallback_rows')})
        # The original point offering panel includes explicit role exceptions;
        # do not relabel the full offered population RB-only.
        offered_roles='ORIGINAL_RECORDED_OFFERED_PLAYER_POOL; QBpassing; rushing includes QB/RB/WR; receiving source-eligible roles; exact role exceptions retained.'
        if target.startswith('pass_'):offered_roles=['QB']
        key=identity(target,method,product,policy,offered_roles,version)
        append(key,'Original RESULTS.zip/recorded_line_point_decisions/'+policy,weekly,metric='statistical_decisive_hit_rate',
            metrics=record['metrics'],evidence='TIMING_UNVERIFIED_RECONSTRUCTED_ACTUAL_LINE_DECISIONS_NOT_ORIGINAL_PICKS',method=method)
    # Reuse actual retained law/event/selection aggregates as distinct products.
    # A point view alone never confers probability qualification.
    law_path=store.forward_root/'research/matched12-law-all-finalists-v1-1-20261031/AGGREGATES.json.gz'
    law_sha='e7438e27d078daa8aceda5528a1f74cde59cf5db00cb81160ea735e05350c715'
    store.validate_reference(law_path,law_sha)
    law=json.loads(gzip.decompress(law_path.read_bytes()))
    for record in law['selection_policies']:
        target,method,arm,policy=record['target'],record['method'],record['arm'],record['policy']
        if method not in catalog.get(target,{}) or policy.startswith('ALWAYS_'):continue
        version=catalog[target][method]['procedure_version']+';'+law['version']+';'+arm
        weekly=[]
        for w in record['weekly']:
            m=w['metrics'];weekly.append({'season':2026,'week':int(w['week']),'scored':int(m.get('decided',m.get('over',{}).get('decided',0)+m.get('under',{}).get('decided',0))),
                'eligible_or_opportunities':m.get('opportunities'),'games':m.get('games'),
                'correct':m.get('correct'),'over':m.get('over'),'under':m.get('under'),
                'missing_law':m.get('missing_law'),'abstain':m.get('abstain')})
        key=identity(target,method,arm,'P2_EXACT_LINE::'+policy,
                     ['QB']if target.startswith('pass_')else'ORIGINAL_RECORDED_OFFERED_PLAYER_POOL_WITH_ROLE_EXCEPTIONS',version)
        append(key,'Retained law aggregate '+law_sha+'/selection_policies',weekly,metric='statistical_decisive_hit_rate',
            metrics=record['metrics'],evidence='TIMING_UNVERIFIED_RECONSTRUCTED_ACTUAL_LINE_PROBABILITY_POLICY',method=method)
    # Add the separately executed carry wave on its exact RB population, not
    # borrowed base-model weeks or the old mixed-position board.
    old=ROOT/'reports/abc-championship/predictive-improvement-01'
    for filename,fields in [(old/'completion-v3/NUMERICAL_RESULTS_V1.json',None),(OUT/'A3_CONDITIONAL_RESULTS_V1.json','numerical_results')]:
        doc=json.loads(filename.read_bytes());rows=doc[fields]if fields else doc['scores']
        group=collections.defaultdict(list)
        for row in rows:group[row['season'],row['arm'],row['product']].append(row)
        for (year,arm,product),rr in group.items():
            weekly=[{'season':year,'week':int(r['week']),'scored':r['scored'],'planned':r.get('expected'),
                     'games':r.get('games'),'MAE':r.get('MAE'),'MSE_or_event_Brier':r.get('MSE')}for r in rr if r['week']!='ALL']
            full=next((r for r in rr if r['week']=='ALL'),{})
            version=(doc.get('procedure_version')if arm=='A3_CONDITIONAL_PLAYED_EXPOSURE'else'ABC-PREDICTIVE-IMPROVEMENT-01-A-v1::'+arm)
            key=identity('rush_att',arm,product,'NUMERIC_MAE',['RB'],version)
            append(key,str(filename.relative_to(ROOT)),weekly,metric='MAE',metrics=full,
                   evidence='EXPOSED_EARLIER_ONLY_RAW_ROLE_STATE_RECONSTRUCTION',method=arm)
    wave=json.loads((old/'completion-v3/ACTUAL_LINE_RESULTS_V1.json').read_bytes())
    a3=json.loads((OUT/'A3_CONDITIONAL_RESULTS_V1.json').read_bytes())
    # Discover original native key by the retained report structure.
    original=wave.get('scores',wave.get('results',[]))
    if not original:
        for value in wave.values():
            if isinstance(value,list)and value and isinstance(value[0],dict)and'policy'in value[0]and'COMBINED'in value[0]:original=value;break
    if not original:raise ValueError('original RB selection summaries not located')
    for rows,version_override,source in [(original,None,'Original carry RB239 actual-line report'),(a3['actual_line_results'],a3['procedure_version'],'A3_CONDITIONAL_RESULTS_V1.json')]:
        group=collections.defaultdict(list)
        for row in rows:group[row['arm'],row['policy']].append(row)
        for (arm,policy),rr in group.items():
            version=version_override or'ABC-PREDICTIVE-IMPROVEMENT-01-A-v1::'+arm
            weekly=[{'season':2026,'week':int(r['week']),'scored':r['COMBINED']['decided'],'selected':r['COMBINED']['selected'],
                     'eligible':r['eligible'],'games':r['games'],'over':r['OVER'],'under':r['UNDER'],
                     'states':r['states'],'unavailable':r['unavailable']}for r in rr if r['week']!='ALL']
            full=next(r for r in rr if r['week']=='ALL');key=identity('rush_att',arm,'mean'if policy=='P1_MEAN'else'median'if policy=='P1_MEDIAN'else'exact_line_probability',policy,['RB'],version)
            append(key,source,weekly,metric='statistical_decisive_hit_rate',metrics=full,
                evidence='TIMING_UNVERIFIED_RECONSTRUCTED_ACTUAL_LINE_DECISIONS',method=arm)
    result={'id':'A-POST-WAVE-5W-QUALIFICATION-CONTRIBUTION-v3','coordinator':'C; this is A contribution, not a second shared master table',
        'asof_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'minimum_distinct_completed_test_weeks':5,
        'original_aggregate_archive_sha256':digest,'source_records':len(contributions),'records':contributions,
        'retained_law_aggregate_sha256':law_sha,
        'explicit_gaps':[
            {'cell':'Original-site cross-category scaled Top12 with CountA replacement','five_week_floor':'NOT_MET','scored_weeks':0,'reason':'Per-category full-board/Top6/10/20 rules do not reproduce the complete original-site eligibility/best-per-player/side/scaled ranking. Exact original historical baseline/source board not established.'},
            {'cell':'Non-count-A numeric point implies actual-line probability','five_week_floor':'NOT_ESTABLISHED','reason':'No probabilities inferred from numeric mean/median. Additional exact-law studies must be imported under their own bound events/policies.'},
            {'cell':'2022-2025 exact candidates beyond located sources','five_week_floor':'NOT_INFERRED','reason':'Canonical historical work continues; training years are not test years. This contribution reuses named accessible records only.'},
            {'cell':'Receiving targets offered market','five_week_floor':'NOT_APPLICABLE','reason':'Forecast-only product; TARGET_OFFER_UNAVAILABLE. Existing target numerical records preserved, not retested or assigned fabricated offers.'}],
        'new_fits_forecasts_scores_NFL_weeks':0,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin}
    from nfl_lab.opportunity_registry_storage_v1 import pack_bytes
    parts=[]
    from nfl_lab.opportunity_registry_storage_v1 import read_document
    for target in sorted({r['key']['target']for r in contributions}):
        rr=[r for r in contributions if r['key']['target']==target]
        name='A_FIVE_WEEK_QUALIFICATION_V3__'+target+'.json'
        payload={'id':result['id'],'category':target,'records':rr,'source_aggregate_sha256':digest}
        ref=pack_bytes(OUT/name,(json.dumps(payload,indent=2,allow_nan=False)+'\n').encode())
        if read_document(OUT/name)!=payload:raise ValueError('qualification partition readback mismatch')
        parts.append({'category':target,'entry':name,'entry_sha256':sha((OUT/name).read_bytes()),'records':len(rr),'five_week_floor_pass':sum(r['five_week_floor']=='PASS'for r in rr),'payload':ref})
    index={k:v for k,v in result.items()if k!='records'}
    index.update(records_encoding='LOSSLESS_SAME_DIRECTORY_CATEGORY_PARTITIONS_V1',parts=parts,
        instructions='Read each entry with nfl_lab.opportunity_registry_storage_v1.read_document or verify/decompress its member. Every record retained; no NFL observations or independent learners implied by the view count.',
        shared_table_owner='C; this index is only A contribution.',
        aliases='A0_BACKFIELD_CDF reuses BACKFIELD_CDF; STORED_COUNT_A_MEAN_CONTROL reuses original COUNT_A_MEAN. Mean/median/policy views are not independent model families; never add their weeks or counts.',
        scope_limit='This export enumerates named accessible primary/current and carry-wave records. Other historical/source/recovery cells remain explicitly open in the canonical C and A task ledgers.')
    (OUT/'A_FIVE_WEEK_QUALIFICATION_V3.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({'records':len(contributions),'floor_pass':sum(r['five_week_floor']=='PASS'for r in contributions),
        'count_A_pass_td':[{'policy':r['key']['selection_policy'],'output':r['key']['output'],'weeks':r['completed_scored_week_count']}for r in contributions if r['key']['target']=='pass_td'and r['method_alias']=='COUNT_A_MEAN'],
        'CPU_seconds':result['CPU_seconds']}))


if __name__=='__main__':main()
