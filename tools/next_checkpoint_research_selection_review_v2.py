"""Reproducible safe-aggregate initialization plus fictional selector checks."""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path('/workspace/nfl-methods-integration')
OUT = ROOT/'reports/next-nfl-checkpoint-20261028'


def main():
    cfg = json.loads((ROOT/'config/next-checkpoint-research-informed-provisional-v1.json').read_text())
    spec=importlib.util.spec_from_file_location('new_selector', ROOT/'nfl_lab/next_checkpoint_research_selection_v1.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    ledger_path=OUT/'LOWEST_ALL_METHOD_LEDGER_V1.json'
    raw=ledger_path.read_bytes(); ledger=json.loads(raw); d=ledger['label_dictionaries']
    # V1 correctly refused an abbreviated ATD aggregate without game/week counts.
    # Recover these fields from the already published exact source, never guess.
    atd_path=ROOT/'reports/modern-anytime-equal-blend-v1/PUBLIC_METRICS.json'
    atd_bytes=atd_path.read_bytes()
    assert hashlib.sha256(atd_bytes).hexdigest()=='3ca09d01a0d4483e119a368e681616b1684f7b04c9e4cd2c894bf9a649e297df'
    atd_source=json.loads(atd_bytes)
    decoded=[]
    for i,r in enumerate(ledger['records']):
        if d['panel'][r[0]]!='modern_REG_primary_role': continue
        decoded.append({'category':d['target'][r[1]],'method':d['method'][r[2]],
            'product':d['product'][r[3]],'year':d['period'][r[4]],'record':i,
            'scores':{ledger['score_keys'][k]:v for k,v in ledger['score_records'][r[5]]},
            'coverage':{ledger['coverage_keys'][k]:v for k,v in ledger['coverage_records'][r[6]]}})
    def scores(cat,year,names,primary,product):
        allowed={'point_median':{'law_median','law_lower_median','absolute_error_point'},
                 'point_mean':{'law_mean','Poisson_mean_objective_point','corrected_mean_fallback_point'},
                 'binary_probability':{'event_probability'}}[product]
        for name in names:
            match=[r for r in decoded if r['category']==cat and r['year']==year and r['method']==name
                   and r['scores'].get(primary) is not None and r['product'] in allowed]
            if match:
                r=match[0]; s=r['scores'];cov=r['coverage']
                atd_log=None
                if cat=='anytime_td':
                    original=[a for a in atd_source['summaries'] if str(a['year'])==year and a['method']==name]
                    assert len(original)==1
                    original=original[0]['strata']['primary_role']
                    assert original['proper_probability_scores']['brier']==s['Brier'] and original['bias']==s['bias']
                    for key,value in cov.items():
                        if key in original: assert original[key]==value
                    cov=original
                    atd_log=original['proper_probability_scores']['log_score']
                role='QB' if cat.startswith('pass_') else 'RB' if cat in ['rush_yd','rush_att'] else 'skill'
                expected={'2025':{'QB':(664,1359),'RB':(1566,2079),'skill':(5295,7271)},
                          '2026':{'QB':(211,515),'RB':(526,668),'skill':(1849,2458)}}[year][role]
                aliases=[(['n','scored','scored_rows','supported_played_outcomes'],expected[0]),
                         (['offered','planned','offered_rows','population_rows'],expected[1]),
                         (['games','unique_games'],272 if year=='2025' else 93),
                         (['weeks','unique_weeks'],18 if year=='2025' else 6)]
                for keys,value in aliases:
                    present=[cov[k] for k in keys if cov.get(k) is not None]
                    if not present or any(x!=value for x in present):
                        raise ValueError('missing/incompatible source-declared modern coverage: '+str((cat,year,name,keys,present)))
                return {'loss':s[primary],'MAE':s.get('MAE'),'MSE':s.get('MSE'),
                    'RMSE':s.get('RMSE'),'bias':s.get('bias'),'p95':s.get('p95'),
                    'log_loss':atd_log if cat=='anytime_td' else s.get('NLL'),'population':f'modern-{year}-{cat}-primary-role-original-query',
                    'ledger_record':r['record'],'coverage':cov,'original_product_tag':r['product'],
                    'common_panel_authority':'Named source-matched annual query/control contracts and prior row QA; normalized matching counts alone are not new independent identity proof.',
                    'precision':'Source precision retained; report-only six-decimal cells are not recovered full precision.'}
        return None
    catalog=json.loads((ROOT/'config/weekly-provisional-live-policy-v1.json').read_text())['categories']
    decisions=[]; evidence=[]
    for c in catalog:
        target=c['category']; current=c['startup_method_id']
        if target=='fantasy_ppr':
            decisions.append({'category':target,'selected':'R0_UNCHANGED','decision':'RETAIN',
                'reason':'Old website PPR exact label target unsupported; new chart is a separate unadmitted consumer product.'});continue
        product=c['output'];primary=c['primary_metric'];procedures=[]
        wanted=['LAB_CDF']
        if target in ['pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td']: wanted.append('CATBOOST_MEDIUM')
        if target in ['rush_att','rec']: wanted.append('COUNT_A')
        if target in ['pass_td','pass_att','pass_int']: wanted.append('RESPONSE_CDF_MEAN')
        if target in ['pass_cmp','rush_att']: wanted.append('CATBOOST_COUNT_MEAN')
        if target=='anytime_td': wanted.append('TD_EQUAL_CDF_CAT')
        for name in wanted:
            if name=='COUNT_A': names=['COUNT_A_STORED_PRIOR_MEAN_V2_REUSED']
            elif name=='RESPONSE_CDF_MEAN': names=['ANNUAL_RESPONSE_CDF_STABLE_MEAN_V1','Response CDF mean']
            elif name=='CATBOOST_COUNT_MEAN': names=['ANNUAL_CATBOOST_MEDIUM_POISSON_MEAN_V1','CatBoost medium mean']
            elif name=='TD_EQUAL_CDF_CAT': names=['TD_EQUAL_CDF_CAT_CACHED_MODERN_RECONSTRUCTION_V1']
            elif name=='LAB_CDF' and product=='point_mean':
                names=['RETAINED_ANNUAL_CDF_LAW_MEAN_V1','FROZEN_SOURCE_MATCHED_ANNUAL_CDF_MEAN','MATCHED_CDF_MEAN_REFERENCE','LAB_CDF']
            else: names=[name]
            row={'method':name,'product':product,'current_product_ready':name not in ['RESPONSE_CDF_MEAN','CATBOOST_COUNT_MEAN']}
            for year in ['2025','2026']: row[year]=scores(target,year,names,primary,product)
            procedures.append(row)
        item={'category':target,'product':product,'primary':primary,'incumbent':current,
              'secondary_guards':['bias','log_loss'] if target=='anytime_td' else ['bias','p95'],
              'procedures':procedures}
        evidence.append(item);decisions.append(module.initial_choice(item))
    # Fictional checks: product/readiness/corroboration/secondary/ties are explicit.
    ex={'category':'fictional','product':'point_median','primary':'MAE','incumbent':'A',
        'secondary_guards':['bias','p95'],'procedures':[
        {'method':m,'product':'point_median','current_product_ready':True,
         '2026':{'loss':v,'bias':0,'p95':3,'population':'x'},
         '2025':{'loss':v,'population':'y'}} for m,v in [('A',2.),('B',1.)]]}
    assert module.initial_choice(ex)['selected']=='B'
    for mutation in ['tie','bad2025','bias','tail','unready','product','missing','nan_bias']:
        t=json.loads(json.dumps(ex)); r=t['procedures'][1]
        if mutation=='tie': r['2026']['loss']=2.
        if mutation=='bad2025': r['2025']['loss']=3.
        if mutation=='bias': r['2026']['bias']=-1.
        if mutation=='tail': r['2026']['p95']=4.
        if mutation=='unready': r['current_product_ready']=False
        if mutation=='product': r['product']='point_mean'
        if mutation=='missing': r['2025']=None
        if mutation=='nan_bias': r['2026']['bias']=float('nan')
        assert module.initial_choice(t)['selected']=='A'
    row={'epoch':'new','horizon':'h','category':'fictional','product':'point_mean','primary':'MSE',
        'genuine_pregame':True,'qualified_final_outcome':True,'information_cutoff':'2026-01-01T00:00Z',
        'issued_at':'2026-01-01T00:01Z','issue_deadline':'2026-01-01T00:02Z',
        'kickoff':'2026-01-01T00:03Z','resolved_at':'2026-01-01T03:00Z',
        'method':'A','opportunity_key':'one','loss':2.}
    kw=dict(methods=['A','B','R0'],current='A',reference='R0',product='point_mean',primary='MSE',
        epoch='new',horizon='h',category='fictional',decision_at='2026-01-02T00:00Z',expected_resolved_keys=['one'])
    records=[dict(row,method=m,loss=v) for m,v in [('A',2.),('B',1.),('R0',3.)]]
    assert module.cumulative_choice(records,**kw)['selected']=='B'
    assert module.cumulative_choice(records[:2],**kw)['selected']=='A'
    assert module.cumulative_choice([],**kw)['selected']=='A'
    inf=[dict(r,loss=float('inf') if r['method']=='B' else 2.) for r in records]
    assert module.cumulative_choice(inf,**kw)['selected']=='A'
    for change in [dict(genuine_pregame=False),dict(genuine_pregame='yes'),dict(qualified_final_outcome=False),dict(loss=True),
                   dict(epoch='old'),dict(issued_at='2026-01-01T00:04Z'),dict(resolved_at='2027-01-01T00:00Z')]:
        try: module.cumulative_choice([dict(records[0],**change),*records[1:]],**kw)
        except ValueError: pass
        else: raise AssertionError('invalid fictional evidence accepted')
    result={'schema_version':'research-informed-provisional-initialization-v1','state':'SAFE_AGGREGATE_EXECUTED_FICTIONAL_SELECTOR_PASS',
        'configuration':cfg,'aggregate_ledger_sha256':hashlib.sha256(raw).hexdigest(),'decisions':decisions,'evidence':evidence,
        'metadata_repair':'V1 abbreviated-ATD-coverage refusal retained; V2 authenticates original published287153-byte report3ca09d... for exact game/week counts and logloss, with unchanged score/coverage reconciliation.',
        'new_NFL_fits_or_forecasts_or_grades':0,'live_activation':False,'original_P2_unchanged':True,
        'interpretation':'A retained choice can be policy-justified while a different point has lower observed MAE. Current product contracts and operational admission remain distinct from research ranks.',
        'next_owner_action':'Review/admit exact separately versioned configuration/adapter in existing producer; new epoch and pre-value future capture assignment before activation. No historical forecast rewrite or duplicate scheduler.'}
    out=OUT/'LOWEST_RESEARCH_INFORMED_SELECTION_V1.json'
    body=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode(); assert len(body)<65536
    out.write_bytes(body)
    print(json.dumps({'decisions':[{k:r.get(k) for k in ['category','selected','decision']} for r in decisions],
                      'path':str(out),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}))


if __name__=='__main__': main()
