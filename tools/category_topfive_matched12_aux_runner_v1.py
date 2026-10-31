"""Bounded auxiliary replay of already frozen output rows, never a new fit.

The root integrator supplies exact source/config/offer digests and independently
reviewed GO.  This module opens no private store, acquires no data, and publishes
nothing.  Returned bytes must be persisted through the approved managed writer.
The W1--6 legacy population is not the new roster-defined W1--7 primary panel.
"""
from __future__ import annotations
import argparse,gzip,hashlib,importlib.util,io,json,math,time
from pathlib import Path

VERSION='matched12-auxiliary-runner-v1'
SCORER='category_topfive_matched12_score_v1_2.py'
SCORER_SHA='ab7775aae5a9178ed82d28217510f328d9903ef20633614c9a2c6bed02c67228'
KEY=['target','season','week','game_id','player_id','team','opponent','cutoff_utc','kickoff_utc']
OFFER_KEY=KEY[:-1]
SAFE_OFFER_COLUMNS=set(OFFER_KEY+['line','evidence_tier','primary_offer_policy','statistical_contract',
 'source_sha256','source_kind','source_record_id','book','book_id','jurisdiction','source_week',
 'quote_time','quote_timing_status','capture_time','source_update_time','source_ordinal',
 'price_over','price_under','american_over','american_under','decimal_over','decimal_under',
 'price_status','settlement_contract','market_probability_eligible','EV_eligible','target_contract',
 'kickoff_utc','primary_opportunity_id','opportunity_key','source_stream','source_quote_time','source_collection_naive'])

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def scorer_module():
    path=Path(__file__).with_name(SCORER)
    if digest(path)!=SCORER_SHA:raise ValueError('reviewed scorer source changed')
    spec=importlib.util.spec_from_file_location('matched12_aux_reviewed_scorer',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def _plain(value):
    import numpy as np
    import pandas as pd
    from decimal import Decimal
    if isinstance(value,dict):return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_plain(v) for v in value]
    if isinstance(value,np.generic):return _plain(value.item())
    if isinstance(value,(pd.Timestamp,Decimal)):return str(value)
    if isinstance(value,float) and not math.isfinite(value):
        raise ValueError('nonfinite JSON values require explicit score-state objects')
    return value

def _encode_json(value):return json.dumps(_plain(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def _interval(values,groups,uncertainty):
    """Same frozen cluster bootstrap, vectorized to honor the finite CPU budget."""
    import numpy as np
    blocks={}
    for group,value in zip(groups,values):blocks.setdefault(str(group),[]).append(float(value))
    n=len(blocks)
    if n<uncertainty['minimum_clusters']:return {'state':'UNAVAILABLE_FEWER_THAN_REGISTERED_CLUSTERS','clusters':n}
    sums=np.asarray([sum(v) for v in blocks.values()]);sizes=np.asarray([len(v) for v in blocks.values()]);rng=np.random.default_rng(uncertainty['seed'])
    take=rng.integers(0,n,(uncertainty['replicates'],n));sample=sums[take].sum(axis=1)/sizes[take].sum(axis=1)
    return {'state':'NOMINAL_EXPOSED_DEVELOPMENT_UNADJUSTED','clusters':n,'lower':float(np.quantile(sample,.025)),'upper':float(np.quantile(sample,.975)),'replicates':uncertainty['replicates'],'seed':uncertainty['seed']}

def expected_population(frame,cfg,scorer):
    """Union only registered saved identities; never filter by prediction/outcome."""
    f=scorer.normalize(frame,cfg['scope'],cfg['catalog'])
    context=KEY+['position']
    e=f[context].drop_duplicates().reset_index(drop=True)
    base=['target','season','week','game_id','player_id']
    if e.duplicated(base).any():raise ValueError('ambiguous saved opportunity context')
    counts=e.groupby('target').size().to_dict()
    if counts!={k:int(v) for k,v in cfg['scope']['expected_rows_by_target'].items()}:
        raise ValueError('legacy complete population differs from frozen expected target counts')
    labels=f[base+['actual','participation_state']].drop_duplicates()
    if labels.duplicated(base).any():raise ValueError('original saved canonical labels disagree')
    labels['horizon_id']=cfg['scope']['horizon_id']
    return e,labels

def _summary(view,scorer,uncertainty,*,target):
    import numpy as np
    out=scorer.summarize_sides(view)
    decided=view.statistical_result.isin(['WIN','LOSS'])
    good=view.loc[decided];correct=good.statistical_result.eq('WIN').to_numpy(float)
    out.update(opportunities=len(view),unique_player_games=int(view[['game_id','player_id']].drop_duplicates().shape[0]),
        games=int(view.game_id.nunique()),weeks=sorted(map(int,view.week.unique())),
        correct=int(correct.sum()),decided=len(good),hit_rate=float(correct.mean()) if len(good) else None,
        independent_decided_games=int(good.game_id.nunique()),independent_decided_weeks=int(good.week.nunique()))
    out['hit_rate_intervals']={c:_interval(correct,good[c],uncertainty) for c in ['game_id','week']}
    for side in ['over','under']:
        sub=good.loc[good.selected_side.eq(side)];hits=sub.statistical_result.eq('WIN').to_numpy(float)
        out[side]['hit_rate_intervals']={c:_interval(hits,sub[c],uncertainty) for c in ['game_id','week']}
    p=view.prediction.to_numpy(float);y=view.actual.to_numpy(float)
    finite=np.isfinite(p)&np.isfinite(y)&view.participation_state.eq('played').to_numpy()
    ae=np.abs(p-y);tolerance=1 if target in scorer.COUNT or target=='chart_ppr' else 10
    close=finite&(ae<tolerance);inclusive=finite&(ae<=tolerance);wins=view.statistical_result.eq('WIN').to_numpy()
    out['precision']={'tolerance':tolerance,'denominator_supported_point_outcomes':int(finite.sum()),
      'strict_close':int(close.sum()),'inclusive_close':int(inclusive.sum()),
      'strict_close_and_correct':int((close&wins).sum()),'inclusive_close_and_correct':int((inclusive&wins).sum()),
      'close_and_correct_denominator_decisive_selected':int(decided.sum()),
      'strict_close_and_correct_rate':float((close&wins).sum()/decided.sum()) if decided.any() else None,
      'inclusive_close_and_correct_rate':float((inclusive&wins).sum()/decided.sum()) if decided.any() else None}
    out['MAE_on_supported_offered_point_rows']=float(ae[finite].mean()) if finite.any() else None
    out['supported_point_outcome_rows']=int(finite.sum())
    out['missing_prediction_rows']=int((~np.isfinite(p)).sum())
    out['unknown_participation_rows']=int(view.participation_state.eq('unknown').sum())
    out['played_missing_outcome_rows']=int((view.participation_state.eq('played').to_numpy()&~np.isfinite(y)).sum())
    out['fallback_rows']=int(view.fallback.fillna('').astype(str).ne('').sum())
    stratum_fields=[c for c in ['source_stream','quote_timing_status','evidence_tier_offer'] if c in view]
    out['source_timing_strata']=[]
    if stratum_fields:
        for identity,g in view.groupby(stratum_fields,dropna=False,sort=True):
            values=identity if isinstance(identity,tuple) else (identity,)
            out['source_timing_strata'].append({'identity':{c:None if str(v)=='nan' else str(v) for c,v in zip(stratum_fields,values)},'opportunities':len(g),'statistical_sides':scorer.summarize_sides(g)})
    out['probability_scores']=None;out['probability_reason']='SAVED_POINT_ROWS_DO_NOT_CONTAIN_AN_EXACT_LINE_OUTCOME_LAW'
    out['paper_return']=None;out['paper_return_reason']='NO_AUTHENTICATED_PRICE_AND_VENUE_SETTLEMENT_PACKAGE_ADMITTED_TO_THIS_REPLAY'
    return out

def validate_offers(offers,scope):
    extra=set(offers)-SAFE_OFFER_COLUMNS
    if extra:raise ValueError('offered feature table contains unadmitted fields: '+','.join(sorted(extra)))
    needed=set(OFFER_KEY+['line','evidence_tier','primary_offer_policy','statistical_contract'])
    if not needed<=set(offers):raise ValueError('primary offered board incomplete')
    if offers.target.isin(['anytime_td','rec_tgt']).any():raise ValueError('ATD/targets cannot become ordinary numeric actual-prop lines')
    if offers.target.eq('chart_ppr').any():
        if 'target_contract' not in offers or not offers.loc[offers.target.eq('chart_ppr'),'target_contract'].eq('nick-chart-ppr-v1').all():raise ValueError('legacy PPR line is not chart PPR')
    if not offers.season.isin(scope['seasons']).all() or not offers.week.isin(scope['weeks']).all():raise ValueError('offer outside fixed auxiliary scope')
    if offers.duplicated(OFFER_KEY).any():raise ValueError('multiple primary offers per model-independent opportunity')
    return offers

def _pair_choices(a,b,scorer,uncertainty):
    import numpy as np
    cols=OFFER_KEY+['selected_side','statistical_result']
    t=a[cols].merge(b[cols],on=OFFER_KEY,validate='one_to_one',suffixes=('_a','_b'))
    decisive=t.statistical_result_a.isin(['WIN','LOSS'])&t.statistical_result_b.isin(['WIN','LOSS'])
    result={}
    for name,mask in [('all_joint_decisive',decisive),('disagreements_joint_decisive',decisive&t.selected_side_a.ne(t.selected_side_b))]:
        s=t.loc[mask];ca=s.statistical_result_a.eq('WIN').to_numpy(float);cb=s.statistical_result_b.eq('WIN').to_numpy(float)
        result[name]={'rows':len(s),'candidate_correct':int(ca.sum()),'control_correct':int(cb.sum()),
          'candidate_minus_control_hit_rate':float(np.mean(ca-cb)) if len(s) else None,
          'intervals':{c:_interval(ca-cb,s[c],uncertainty) for c in ['game_id','week']}}
    return result

def side_replay(points,offers,cfg,scorer):
    import pandas as pd
    points=points.loc[~points.target.eq('anytime_td')].copy()
    offers=validate_offers(offers.copy(),cfg['scope'])
    offers['cutoff_utc']=scorer._clock(offers.cutoff_utc)
    expected=points[OFFER_KEY].drop_duplicates()
    census=offers.merge(expected,on=OFFER_KEY,how='left',validate='one_to_one',indicator=True)
    outside=census.loc[census['_merge'].eq('left_only')]
    outside_counts=[dict(zip(['target','season','week'],key),offer_rows=int(n)) for key,n in outside.groupby(['target','season','week'],sort=True).size().items()]
    contract={'identity_namespace':cfg['scope']['identity_namespace'],'forecast_identity_namespace':cfg['scope']['identity_namespace']}
    joined=scorer.point_sides(points,offers,contract)
    joined['decision_policy']='P1_UNROUNDED_POINT_DIRECTION_V1'
    joined['decision_evidence']='RECONSTRUCTED_DECISION_FROM_FROZEN_POINT_AND_ORIGINAL_RECORDED_LINE'
    joined['venue_settlement']='UNAVAILABLE_NOT_INFERRED_FROM_STATISTICAL_DIRECTION'
    # Missing offers remain visible in full expected outputs. Full board below
    # comprises only independently selected original offers, never model picks.
    offered=joined.loc[joined.line.notna()].copy();records=[];pairs=[];controls=[]
    for (target,season,method,product),view in offered.groupby(['target','season','method','product'],sort=True):
        ref=cfg['scope']['reference_output'][target]
        policies={'LEGACY_EXPECTED_QUERY_INTERSECTION_RECORDED_OFFER_BOARD':view}
        for cap in [6,10,20]:
            # No outcome, result or accuracy participates in eligibility/ranking.
            q=view.loc[view.selected_side.isin(['over','under'])].copy()
            q['rank_gap']=(q.prediction.astype(float)-q.line.astype(float)).abs()
            q=q.sort_values(['week','rank_gap','game_id','player_id'],ascending=[True,False,True,True],kind='stable')
            policies['TOP_'+str(cap)+'_NATIVE_POINT_GAP_PER_CATEGORY_WEEK']=q.groupby('week',sort=True,group_keys=False).head(cap)
        for policy,v in policies.items():
            records.append({'target':target,'season':int(season),'method':method,'product':product,'policy':policy,
              'scope':'LEGACY_EXPECTED_QUERY_INTERSECTION_RECORDED_OFFER_BOARD_AUXILIARY_W1_6','eligible_legacy_query_offer_intersection_rows':len(view),'metrics':_summary(v,scorer,cfg['uncertainty'],target=target),
              'weekly':[{'week':int(w),'eligible_legacy_query_offer_intersection_rows':int(view.week.eq(w).sum()),'metrics':_summary(v.loc[v.week.eq(w)],scorer,cfg['uncertainty'],target=target)} for w in sorted(view.week.unique())]})
        control=offered.loc[offered.target.eq(target)&offered.season.eq(season)&offered.method.eq(ref[0])&offered['product'].eq(ref[1])]
        pairs.append({'target':target,'season':int(season),'candidate':[method,product],'reference':ref,
            'choices':_pair_choices(view,control,scorer,cfg['uncertainty'])})
    # Always-side controls use the same line board, source outcomes, and one
    # model-independent opportunity, not repeated output copies.
    base=offered.drop_duplicates(OFFER_KEY).copy()
    for side in ['over','under']:
        c=base.copy();c['prediction']=c.line.astype(float)+(1 if side=='over' else -1)
        c=scorer.point_sides(c.drop(columns=[x for x in offers if x not in OFFER_KEY and x in c]),offers,contract)
        for (target,season),v in c.groupby(['target','season'],sort=True):
            m=_summary(v,scorer,cfg['uncertainty'],target=target)
            m['MAE_on_supported_offered_point_rows']=None;m['point_reason']='Always-side control is not a numerical forecast.';m['precision']=None
            controls.append({'target':target,'season':int(season),'control':'ALWAYS_'+side.upper(),'metrics':m})
    report={'state':'COMPLETED_RECONSTRUCTED_POINT_SIDE_REPLAY' if len(offers) else 'COMPLETED_ZERO_QUALIFIED_OFFER_JOIN_NO_SIDE_SCORES','records':records,'paired_choices':pairs,'always_side_controls':controls,
      'offer_rows':len(offers),'offered_output_rows':len(offered),'full_expected_output_rows':len(joined),
      'missing_offer_output_rows':int(joined.line.isna().sum()),
      'recorded_offers_outside_legacy_expected_query_population':{'offer_rows':len(outside),'by_target_season_week':outside_counts,'reason':'The old saved forecast population does not cover the full recoverable offering board; those original offers remain retained, not silently dropped or treated as prediction failures for an unregistered old population.'},
      'headline_population':'Legacy expected-query population intersected with the recovered recorded offering board, not all recoverable offers and not the new W1-7 primary roster population.',
      'abstaining_policy':{'state':'UNAVAILABLE','reason':'FROZEN_EARLIER_TRAINING_CATEGORY_IQR_NOT_IN_THIS_CAPTURE; no replacement threshold chosen after outcomes.'},
      'probability_track':{'state':'UNAVAILABLE_FROM_POINT_ONLY_CAPTURE','next':'Restore authenticated saved full laws and compute exact-line probabilities; do not infer a law from a mean/median.'},
      'price_track':{'state':'UNAVAILABLE','reason':'Price and venue settlement qualification is separate from statistical side grades.'},
      'limitations':['These are newly reconstructed decisions, not original website recommendations.','Conditional Over and Under hit rates refer to methods own selected subsets.','Top-N gap ranks are per-category/week; gaps in different native units are never pooled.','Unknown quote clocks remain explicit source tiers.','All uncertainty is descriptive exposed-development uncertainty, not selected-winner confirmation.']}
    return report,joined

def run_arrays(frame,cfg,offers=None):
    """Pure numerical worker; caller is responsible for exact GO before real rows."""
    scorer=scorer_module();e,o=expected_population(frame,cfg,scorer)
    report,points=scorer.score_panel(frame,cfg['scope'],cfg['catalog'],cfg['uncertainty'],expected_roster=e,outcomes=o)
    report['worker_version']=VERSION
    report['population_admission']={'expected_rows_by_target':e.groupby('target').size().to_dict(),'rule':'Complete union of original captured query identities, checked against predeclared counts; no prediction/outcome eligibility filtering.'}
    if offers is None:
        report['side_comparison']={'state':'NOT_EXECUTED_MISSING_ADMITTED_COMMON_ORIGINAL_OFFER_PANEL'};sides=None
    else:report['side_comparison'],sides=side_replay(points,offers,cfg,scorer)
    report['execution_counters']={'new_fits':0,'new_model_inference':0,'new_forecasts':0,'cached_scoring_runs':1,'forecast_output_rows_materialized':len(points),'unique_player_game_target_opportunities':len(e),'independent_game_clusters':int(e.game_id.nunique()),'independent_week_clusters':int(e.week.nunique())}
    return report,points,sides

def _frozen_bundle(frame,cfg,go,offers=None):
    """Exact driver/config/offer GO and bounded replay; no filesystem writes."""
    if go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root' or go.get('worker_version')!=VERSION or go.get('worker_sha256')!=digest(__file__):raise ValueError('exact auxiliary execution GO required')
    if go.get('configuration_sha256')!=hashlib.sha256(_encode_json(cfg)).hexdigest():raise ValueError('effective configuration changed')
    if go.get('input_sha256')!='b58155f0868d45c1359a7bb9bdc2dd9aafcb7bafbda2cbe6d06ae6c2131fb481':raise ValueError('original full captured table required')
    if offers is not None and not go.get('offer_input_sha256'):raise ValueError('original common offer input binding required')
    report,points,sides=run_arrays(frame,cfg,offers)
    public=gzip.compress(_encode_json(report),compresslevel=9,mtime=0)
    if len(public)>cfg['resources']['maximum_safe_aggregate_compressed_bytes']:raise ValueError('safe aggregate compressed budget exceeded')
    bundle={'AGGREGATES.json.gz':public}
    for name,table in [('POINT_OUTPUT_SCORECARD.parquet',points),('POINT_SIDE_SCORECARD.parquet',sides)]:
        if table is None:continue
        table=table.copy()
        # Parquet decimals come from exact original lines; preserve their text.
        for key in ['line']:
            if key in table:table[key]=table[key].map(lambda x:None if x is None or str(x)=='nan' else str(x))
        buf=io.BytesIO();table.to_parquet(buf,index=False,compression='zstd');bundle[name]=buf.getvalue()
    if sum(map(len,bundle.values()))>cfg['resources']['maximum_private_new_bytes']:raise ValueError('registered immutable output bundle budget exceeded')
    report['bundle_manifest']={k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in bundle.items()}
    return report,bundle

def read_offer_table(ref):
    """Authenticated already prepared primary panel, never a new quote source."""
    import zipfile
    import pyarrow.parquet as pq
    path=Path(ref['path'])
    if not path.is_absolute() or path.resolve()!=path or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('canonical nonsymlink primary offer input required')
    before=path.stat()
    if before.st_size!=ref['bytes'] or before.st_size>32*1024**2:raise ValueError('finite primary offer input cap or declared byte count exceeded before read')
    raw=path.read_bytes();after=path.stat()
    if len(raw)>32*1024**2 or len(raw)!=ref['bytes'] or hashlib.sha256(raw).hexdigest()!=ref['sha256'] or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('prepared primary offer binding changed')
    if ref.get('member'):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            info=archive.getinfo(ref['member'])
            if info.file_size>16*1024**2:raise ValueError('finite primary offer member cap exceeded')
            raw=archive.read(info)
        if hashlib.sha256(raw).hexdigest()!=ref['member_sha256']:raise ValueError('prepared primary offer member changed')
    result=pq.read_table(io.BytesIO(raw),use_threads=False).to_pandas()
    if len(result)>50000:raise ValueError('primary unique offer cap exceeded')
    return result

def execute_bound(ref,cfg,go,read_go,offer_ref=None):
    """Only real-data entry: exact admitted inputs are decoded after fresh GO."""
    if go.get('worker_sha256')!=digest(__file__) or go.get('worker_version')!=VERSION or go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root':raise ValueError('exact auxiliary execution GO required before source decode')
    if go.get('configuration_sha256')!=hashlib.sha256(_encode_json(cfg)).hexdigest():raise ValueError('configuration mismatch before source decode')
    if ref.get('sha256')!=go.get('input_sha256'):raise ValueError('cached table source differs from execution GO')
    if (offer_ref is None)!=(go.get('offer_input_sha256') is None):raise ValueError('offer presence differs from exact execution GO')
    if offer_ref is not None and offer_ref['sha256']!=go['offer_input_sha256']:raise ValueError('prepared primary offer source differs from exact GO')
    scorer=scorer_module();frame=scorer.read_cached_table(ref,read_go)
    offers=read_offer_table(offer_ref) if offer_ref is not None else None
    return _frozen_bundle(frame,cfg,go,offers)

def fictional_checks():
    import pandas as pd
    import numpy as np
    scorer=scorer_module();now='2026-09-10T00:00:00+00:00';rows=[]
    for week,y in [(1,4),(2,5)]:
        for method,product,p in [('CDF_MEDIAN','median',4.),('CDF_MEAN','mean',4.5),('COUNT_A_MEAN','mean_objective_point',5.)]:
            rows.append(dict(target='rec',season=2026,week=week,game_id='fiction-'+str(week),player_id='fiction-player',team='AAA',opponent='BBB',position='WR',cutoff_utc=now,kickoff_utc=now,method=method,product=product,prediction=p,actual=float(y),participation_state='played',fallback=''))
    frame=pd.DataFrame(rows)
    cfg={'scope':{'targets':['rec'],'seasons':[2026],'weeks':[1,2],'identity_namespace':'FICTIONAL','source_policy_id':'FICTIONAL','outcome_version':'FICTIONAL','evidence_tier':'FICTIONAL_ONLY','horizon_id':'FICTIONAL','expected_rows_by_target':{'rec':2},'primary_core_outputs':{'rec':[['CDF_MEDIAN','median'],['COUNT_A_MEAN','mean_objective_point']]},'reference_output':{'rec':['CDF_MEAN','mean']}},'catalog':{'rec':{m:{'procedure_id':m,'procedure_version':'FICTIONAL','products':[p]} for m,p in [('CDF_MEDIAN','median'),('CDF_MEAN','mean'),('COUNT_A_MEAN','mean_objective_point')]}},'uncertainty':{'replicates':30,'seed':7,'minimum_clusters':2}}
    offers=frame.loc[frame.method.eq('CDF_MEDIAN'),OFFER_KEY].copy();offers['line']=4.5;offers['evidence_tier']='FICTIONAL_ONLY';offers['primary_offer_policy']='FICTIONAL';offers['statistical_contract']='STATISTICAL_ONLY'
    offers['opportunity_key']=['fiction-'+str(w) for w in offers.week]
    result,points,sides=run_arrays(frame,cfg,offers);checks=[]
    def ok(name,value):
        if not value:raise AssertionError(name)
        checks.append(name)
    ok('full population retained',len(points)==6)
    ok('one original board faced by each output',len(sides)==6)
    ok('unrounded fractional equality abstains',sides.loc[sides.method.eq('CDF_MEAN'),'selected_side'].eq('abstain').all())
    ok('actual count half-line no push',not sides.statistical_result.eq('PUSH').any())
    med=sides.loc[sides.method.eq('CDF_MEDIAN')];ok('median under correct and wrong',list(med.statistical_result)==['WIN','LOSS'])
    ok('always controls same independent board',len(result['side_comparison']['always_side_controls'])==2)
    ok('topN separate native policy',len(result['side_comparison']['records'])==12)
    ok('no probability fabrication',result['side_comparison']['probability_track']['state']=='UNAVAILABLE_FROM_POINT_ONLY_CAPTURE')
    extra=offers.iloc[[0]].copy();extra['player_id']='fiction-outside-legacy';extra['opportunity_key']='fiction-outside-legacy'
    r,_,_=run_arrays(frame,cfg,pd.concat([offers,extra],ignore_index=True))
    ok('offers outside legacy population separately counted',r['side_comparison']['recorded_offers_outside_legacy_expected_query_population']['offer_rows']==1)
    ok('vectorized bootstrap exact registered scalar replay',_interval([1,0,1],['a','b','a'],cfg['uncertainty'])==scorer._bootstrap([1,0,1],['a','b','a'],7,30,2))
    missing=frame.loc[~(frame.method.eq('COUNT_A_MEAN')&frame.week.eq(2))].copy();r,p,s=run_arrays(missing,cfg,None)
    ok('missing output materialized',len(p)==6 and p.prediction.isna().sum()==1)
    ok('no missing line converted to side',r['side_comparison']['state'].startswith('NOT_EXECUTED'))
    bad=offers.copy();bad['margin']=0
    try:validate_offers(bad,cfg['scope'])
    except ValueError:checks.append('postgame offer field rejected')
    else:raise AssertionError('postgame allowlist')
    bad=frame.copy();bad.loc[0,'actual']=100
    try:expected_population(bad,cfg,scorer)
    except ValueError:checks.append('cross-method outcome conflict rejected')
    else:raise AssertionError('outcome conflict')
    badcfg=json.loads(json.dumps(cfg));badcfg['scope']['expected_rows_by_target']['rec']=3
    try:expected_population(frame,badcfg,scorer)
    except ValueError:checks.append('fixed expected count mismatch rejected')
    else:raise AssertionError('expected counts')
    return {'state':'PASS','fictional_cases':len(checks),'checks':checks,'actual_NFL_rows_decoded':0,'new_fits':0,'new_inference':0,'scope':'Fictional scorer/outer contract checks only, not NFL accuracy evidence.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fictional-check',action='store_true');args=parser.parse_args()
    if not args.fictional_check:parser.error('Actual execution is root-orchestrated after exact GO; this CLI only runs fictional checks.')
    start=time.monotonic();cpu=time.process_time();r=fictional_checks();r.update(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,worker_sha256=digest(__file__))
    print(json.dumps(r,sort_keys=True))
