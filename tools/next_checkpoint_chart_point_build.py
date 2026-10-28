"""One fixed chart-median learner, full-population fallbacks and a frozen grade.

The reused label capsule is tokenized without numeric conversion. 2026 outcome
values are converted only after the inherited CAS freeze callback succeeds.
All periods are exposed reconstructed development evidence, never prospective.
"""
from __future__ import annotations
from collections import Counter
import base64
import csv
import gzip
import io
import json
import math
import pickle
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
from next_checkpoint_chart_ppr_labels import authenticate, encoded, sha

VERSION='next-checkpoint-chart-point-pilot-v1'
ROLES=['QB','RB','FB','WR','TE']
STATS=['pass_yd','pass_td','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_td','rec_td','rec_tgt']
FEATURES=[f'f_player_{s}_mean{w}' for s in STATS for w in (3,8)]+[
    'f_player_games_prior','f_player_play_rate8','f_player_known_participation_n8','f_player_pass_ypa3',
    'f_player_comp_rate3','f_player_rush_ypa3','f_player_rec_ypt3','f_player_rec_catch_rate3','f_rest_days','f_is_home']
PARAMETERS={'max_iter':150,'learning_rate':.05,'max_leaf_nodes':15,'max_depth':3,'min_samples_leaf':30,
    'l2_regularization':10.,'early_stopping':False,'random_state':1702,'loss':'absolute_error'}
KEYS=['game_id','team','player_id']
METHODS=['HGB_CHART_MEDIAN_V1','POSITION_CHART_MEDIAN_2024','GLOBAL_CHART_MEDIAN_2024','POSITION_CHART_MEAN_2024']


class NumericToken(str):
    """A JSON numeric lexeme; no target outcome conversion before freeze."""


def normalized_team(value):
    return {'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'}.get(value,value)


def key(row):
    return row['game_id'], normalized_team(row['team']), row['player_id']


def require_identity(label,source):
    identity=label['identity']
    if (int(identity['season'])!=int(source['season']) or int(identity['week'])!=int(source['week'])
        or normalized_team(identity['opponent'])!=normalized_team(source['opponent'])):
        raise ValueError('feature/label season-week-opponent identity conflict')


def finite(value):
    return value is not None and math.isfinite(float(value))


def scalar(value):
    if pd.isna(value):return None
    if isinstance(value,np.generic):return value.item()
    return value


def aware(value,allow_missing=False):
    if pd.isna(value):
        if allow_missing:return pd.NaT
        raise ValueError('unknown required timing value')
    stamp=pd.Timestamp(value)
    if stamp.tzinfo is None:raise ValueError('explicit source timing must include timezone')
    return stamp.tz_convert('UTC')


def assert_chronology(frame):
    cutoff=frame['cutoff_utc'].map(aware)
    kickoff=frame['kickoff_utc'].map(aware)
    maximum=frame['feature_max_source_available_utc'].map(lambda v:aware(v,True))
    if cutoff.isna().any() or kickoff.isna().any() or (cutoff>kickoff).any() or (maximum.notna()&(maximum>=cutoff)).any():
        raise ValueError('source feature cutoff chronology failed; no subset retry')


def design(frame,medians=None):
    raw=frame[FEATURES].to_numpy(float)
    missing=~np.isfinite(raw)
    if medians is None:
        medians=np.array([np.median(raw[np.isfinite(raw[:,j]),j]) if np.isfinite(raw[:,j]).any() else 0. for j in range(raw.shape[1])])
    filled=np.where(missing,medians[None,:],raw)
    roles=np.stack([frame['position'].eq(role).to_numpy(float) for role in ROLES],axis=1)
    return np.column_stack([filled,missing.astype(float),roles]),medians


def metric(y,p):
    e=np.asarray(p)-np.asarray(y);a=np.abs(e)
    return {'n':len(e),'MAE':float(a.mean()),'MSE':float(np.mean(e*e)),'RMSE':float(np.sqrt(np.mean(e*e))),
        'bias':float(e.mean()),'p90_absolute_error':float(np.quantile(a,.90,method='linear')),
        'p95_absolute_error':float(np.quantile(a,.95,method='linear')),'max_absolute_error':float(a.max()),
        'error_strict_lt1':float(np.mean(a<1)),'error_inclusive_le1':float(np.mean(a<=1)),
        'error_strict_lt5':float(np.mean(a<5)),'error_inclusive_le5':float(np.mean(a<=5))}


def paired(rows,control):
    errors=np.array([abs(r['predictions'][METHODS[0]]-r['actual'])-abs(r['predictions'][control]-r['actual']) for r in rows])
    out={'candidate':METHODS[0],'control':control,'primary':'MAE','n':len(rows),'mean_loss_difference':float(errors.mean())}
    baseline=np.mean([abs(r['predictions'][control]-r['actual']) for r in rows])
    out['relative_improvement_percent']=100*(-float(errors.mean()))/baseline if baseline else None
    for cluster in ['game_id','week']:
        groups={}
        for r,d in zip(rows,errors):
            c=r['identity'][cluster];groups.setdefault(c,[]).append(d)
        values=list(groups.values());count=len(values)
        if count<8:out[cluster+'_interval']={'state':'UNAVAILABLE_FEWER_THAN8CLUSTERS','clusters':count};continue
        sums=np.array([sum(v) for v in values]);sizes=np.array([len(v) for v in values]);rng=np.random.default_rng(1703)
        samples=[]
        for _ in range(500):
            draw=rng.integers(0,count,count);samples.append(sums[draw].sum()/sizes[draw].sum())
        out[cluster+'_interval']={'state':'NOMINAL_EXPOSED_DEVELOPMENT_DIAGNOSTIC','clusters':count,'confidence':.95,'replicates':500,'seed':1703,
            'lower':float(np.quantile(samples,.025)),'upper':float(np.quantile(samples,.975))}
    return out


def build(plan_bytes,go,freeze,progress):
    plan=json.loads(plan_bytes)
    if (plan['version']!=VERSION or plan['state']!='ROOT_AND_INDEPENDENT_SEALED'
        or plan['execution_authorized'] is not True or plan['independent_review']!='PASS'
        or plan['root_registration']['registered_by']!='/root'
        or go['state']!='ROOT_AND_INDEPENDENT_GO' or go['plan_sha256']!=sha(plan_bytes)
        or go['registered_by']!='/root' or go['independent_review']!='PASS'
        or plan['features']!=FEATURES or plan['parameters']!=PARAMETERS):raise ValueError('exact new chart point seal required')
    if len(FEATURES)!=32 or any('snap' in f or 'fantasy_ppr' in f for f in FEATURES):raise ValueError('exact32non-snap/non-old-PPRfeatures required')
    bodies={name:authenticate(ref)[0] for name,ref in plan['inputs'].items()}
    if sum(map(len,bodies.values()))>plan['resources']['maximum_input_bytes']:raise ValueError('source byte cap')
    labels=json.loads(gzip.decompress(bodies['chart_labels']),parse_int=NumericToken,parse_float=NumericToken)
    if labels['target']!='nick-chart-ppr-v1' or len(labels['labels'])!=14160:raise ValueError('complete exact chart labels required')
    old_hash=plan['inputs']['chart_labels']['sha256']
    train_labels={};query_labels={}
    for r in labels['labels']:
        identity=r['identity'];season=int(identity['season'])
        if season in (2024,2026):
            k=key(identity);store=train_labels if season==2024 else query_labels
            if k in store:raise ValueError('duplicate complete label key')
            store[k]=r
    if len(train_labels)!=5935 or len(query_labels)!=2117:raise ValueError('full declared population differs')
    # Position/identity metadata only, never target statistics, from original
    # source-listed weekly population. Preserve role even when feature query absent.
    positions={}
    for season in (2024,2026):
        pos=pq.read_table(io.BytesIO(bodies['weekly'+str(season)]),columns=['game_id','team','player_id','position','season','week','season_type'],
            filters=[('season','==',season),('season_type','==','REG'),('position','in',ROLES)]+([('week','<=',6)] if season==2026 else [])).to_pylist()
        store={key(r):r for r in pos}
        expected=train_labels if season==2024 else query_labels
        if len(store)!=len(pos) or set(store)!=set(expected):raise ValueError('complete source position/label population mismatch')
        positions[season]=store
    columns=list(dict.fromkeys([*KEYS,'position','season','week','opponent','kickoff_utc','cutoff_utc','feature_max_source_available_utc','outcome_available_utc',*FEATURES]))
    training=pq.read_table(io.BytesIO(bodies['historical_features']),columns=columns,filters=[('season','==',2024)]).to_pandas()
    queries=pq.read_table(io.BytesIO(bodies['query2026']),columns=columns,filters=[('season','==',2026),('week','<=',6)]).to_pandas()
    for f in [training,queries]:
        if f.duplicated(KEYS).any():raise ValueError('duplicate source features key')
        assert_chronology(f)
    origin=pd.Timestamp('2026-09-01T00:00:00Z')
    if (queries['cutoff_utc'].map(aware)<origin).any():raise ValueError('2026query precedes fixedtrainingorigin')
    tlookup={key(r):r for r in training.to_dict('records')};qlookup={key(r):r for r in queries.to_dict('records')}
    if len(tlookup)!=len(training) or len(qlookup)!=len(queries):raise ValueError('canonical-team alias collapsed distinct source feature rows')
    # Complete2024 label timing uses the SAME declared kickoff+7day historical
    # assumption. This is not a known upstream publication timestamp. No fallback
    # invented kickoff is permitted, including label rows without feature queries.
    calendar=pd.read_csv(io.BytesIO(bodies['schedule_metadata']),usecols=['game_id','season','week','game_type','gameday','gametime','away_team','home_team'])
    calendar=calendar[calendar['season'].eq(2024)&calendar['game_type'].eq('REG')]
    if calendar['game_id'].duplicated().any():raise ValueError('duplicate training game schedule identity')
    naive=pd.to_datetime(calendar['gameday']+' '+calendar['gametime'],errors='coerce')
    calendar['kickoff_utc']=naive.dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('UTC')
    schedules={r['game_id']:r for r in calendar.to_dict('records')}
    for k,r in train_labels.items():
        identity=r['identity'];cal=schedules.get(identity['game_id'])
        if cal is None or pd.isna(cal['kickoff_utc']) or int(identity['week'])!=int(cal['week']):raise ValueError('training label lacks exact known schedule binding')
        team=normalized_team(identity['team']);opponent=normalized_team(identity['opponent'])
        if {team,opponent}!={normalized_team(cal['away_team']),normalized_team(cal['home_team'])}:raise ValueError('training label calendar team/opponent mismatch')
        if aware(cal['kickoff_utc'])+pd.Timedelta(days=7)>=origin:raise ValueError('assumed training label timing reachesforecastorigin')
    eligible=[];train_values=[];train_roles=[];modeled=[];counts=Counter()
    for k,r in train_labels.items():
        counts['planned']+=1
        if r['state'] not in ['played_score','played_zero'] or r['value'] is None:counts[r['state']]+=1;continue
        value=float(r['value'])
        if not math.isfinite(value):raise ValueError('nonfinite admitted training score')
        role=positions[2024][k]['position'];train_values.append(value);train_roles.append(role);eligible.append(k)
        if k in tlookup:
            require_identity(r,tlookup[k])
            f=dict(tlookup[k])
            if aware(f['outcome_available_utc'])>=origin:raise ValueError('used training feature label clock is not prior')
            if pd.isna(f['feature_max_source_available_utc']):counts['numeric_training_unknown_feature_clock_prior_only']+=1
            else:
                f['position']=role;f['_chart_y']=value;modeled.append(f)
        else:counts['numeric_training_missing_features']+=1
    if len(eligible)!=5589 or len(modeled)<60:raise ValueError('exact qualified training population/fittable schema differs')
    priors={role:{'median':float(np.median([v for v,p in zip(train_values,train_roles) if p==role])),
                  'mean':float(np.mean([v for v,p in zip(train_values,train_roles) if p==role]))}
            for role in ROLES if role in train_roles}
    global_prior={'median':float(np.median(train_values)),'mean':float(np.mean(train_values))}
    modeltrain=pd.DataFrame(modeled);x,medians=design(modeltrain)
    progress['fit_attempts']+=1
    with threadpool_limits(limits=1):model=HistGradientBoostingRegressor(**PARAMETERS).fit(x,modeltrain['_chart_y'].to_numpy(float))
    progress['completed_fits']+=1
    trained_pickle=pickle.dumps({'estimator':model,'features':FEATURES,'medians':medians,'roles':ROLES,'priors':priors,'global_prior':global_prior,
        'parameters':PARAMETERS,'target':'nick-chart-ppr-v1','forecast_contract':'MAE_objective_point_no_distribution'},protocol=5)
    frozen=[];warm_features=[];warm_indices=[];fallbacks=Counter()
    for k,r in query_labels.items():
        identity={kk:(int(v) if kk in ['season','week'] else v) for kk,v in r['identity'].items()}
        role=positions[2026][k]['position'];p=priors.get(role,global_prior);q=qlookup.get(k)
        if q is not None:require_identity(r,q)
        reason=''
        if q is None:reason='missing_feature_query_position_prior'
        elif pd.isna(q.get('feature_max_source_available_utc')):reason='unknown_feature_clock_position_prior'
        elif not finite(q.get('f_player_games_prior')) or float(q['f_player_games_prior'])<=0:reason='cold_or_unknown_history_position_prior'
        if role not in priors:reason='unseen_role_global_prior'
        forecasts={METHODS[0]:p['median'],METHODS[1]:p['median'],METHODS[2]:global_prior['median'],METHODS[3]:p['mean']}
        row={'identity':identity,'position':role,'predictions':forecasts,'fallback':reason,
            'feature_query_available':q is not None,'cutoff_utc':str(q['cutoff_utc']) if q else None,
            'kickoff_utc':str(q['kickoff_utc']) if q else None,
            'source_feature_max_utc':str(q['feature_max_source_available_utc']) if q and pd.notna(q['feature_max_source_available_utc']) else None}
        if reason:fallbacks[reason]+=1
        else:
            q=dict(q);q['position']=role;warm_features.append(q);warm_indices.append(len(frozen))
        frozen.append(row)
    if warm_features:
        xx,_=design(pd.DataFrame(warm_features),medians)
        progress['model_prediction_calls']+=1
        with threadpool_limits(limits=1):pred=model.predict(xx)
        if not np.isfinite(pred).all():raise ValueError('nonfinite model forecast')
        for index,p in zip(warm_indices,pred):frozen[index]['predictions'][METHODS[0]]=float(p)
    if len(frozen)!=2117:raise ValueError('complete planned query predictions required')
    freeze_doc={'version':VERSION,'state':'RECONSTRUCTED_FORECASTS_FROZEN_BEFORE_EVAL_NUMERIC_CONVERSION',
        'target':'nick-chart-ppr-v1','plan_sha256':sha(plan_bytes),'source_label_capsule_sha256':old_hash,
        'training':{'season':2024,'planned':5935,'supported_numeric':5589,'model_rows':len(modeled),'missingness':dict(counts)},
        'priors':priors,'global_prior':global_prior,'features':FEATURES,'imputation_medians':medians.tolist(),'training_label_timing_policy':'exact2024REGschedulekickoffAmericaNewYork+7dayASSUMPTION_notknownpublication',
        'fitted_model_pickle_base64':base64.b64encode(trained_pickle).decode(),'fitted_model_sha256':sha(trained_pickle),
        'fitted_iterations':int(model.n_iter_),'forecasts':frozen,'fallbacks':dict(fallbacks),
        'functional_contracts':{METHODS[0]:'MAE_objective_point_no_distribution',METHODS[1]:'empirical_position_median',
            METHODS[2]:'empirical_global_median',METHODS[3]:'position_conditional_mean_control'},
        'evidence_lane':'exposed_current_vintage_7day_assumption_reconstruction_not_prospective'}
    freeze_body=gzip.compress(encoded(freeze_doc),mtime=0)
    if len(freeze_body)>plan['resources']['single_gzip_cap_bytes']:raise ValueError('complete frozen model/forecasts exceed cap')
    frozen_ref=freeze('FORECASTS_FROZEN.json.gz',freeze_body)
    progress['durably_frozen_forecast_rows']=len(frozen)
    # No2026 target-value conversion or numeric scoring occurred above this line.
    progress['scoring_runs_started']+=1
    rows=[];states=Counter();weekly={};rolemetrics={};known=0
    for f in frozen:
        label=query_labels[key(f['identity'])];state=label['state'];states[state]+=1
        actual=float(label['value']) if label['value'] is not None and state in ['played_score','played_zero'] else None
        if actual is not None and not math.isfinite(actual):raise ValueError('invalid admitted query score')
        row={**f,'outcome_state':state,'actual':actual,'errors':{m:(f['predictions'][m]-actual if actual is not None else None) for m in METHODS}}
        rows.append(row)
    scored=[r for r in rows if r['actual'] is not None]
    if len(scored)!=1954 or states['unknown_participation']!=163:raise ValueError('declared supported query population changed')
    def scores(part):return {m:metric([r['actual'] for r in part],[r['predictions'][m] for r in part]) for m in METHODS}
    for week in sorted({r['identity']['week'] for r in rows}):
        part=[r for r in rows if r['identity']['week']==week];good=[r for r in part if r['actual'] is not None]
        weekly[str(week)]={'planned':len(part),'scored':len(good),'outcome_states':dict(Counter(r['outcome_state'] for r in part)),'metrics':scores(good) if good else {}}
    for role in ROLES:
        part=[r for r in scored if r['position']==role]
        if part:rolemetrics[role]=scores(part)
    coverage_slices={}
    for name,predicate in [('model_only',lambda r:not r['fallback']),('fallback_only',lambda r:bool(r['fallback']))]:
        planned=[r for r in rows if predicate(r)];good=[r for r in planned if r['actual'] is not None]
        coverage_slices[name]={'planned':len(planned),'scored':len(good),
            'outcome_states':dict(Counter(r['outcome_state'] for r in planned)),'metrics':scores(good) if good else {}}
    metrics=scores(scored);contrasts=[paired(scored,m) for m in [METHODS[1],METHODS[2]]]
    scorecard=io.StringIO()
    writer=csv.writer(scorecard,lineterminator='\n')
    writer.writerow(['season','week','game_id','player_id','team','opponent','position','method','product',
        'prediction','actual_chart_points','signed_error','absolute_error','outcome_state','cutoff_utc',
        'kickoff_utc','feature_max_utc','fallback','evidence_lane'])
    for r in rows:
        i=r['identity']
        for method in METHODS:
            err=r['errors'][method]
            writer.writerow([i['season'],i['week'],i['game_id'],i['player_id'],i['team'],i['opponent'],r['position'],method,
                freeze_doc['functional_contracts'][method],r['predictions'][method],r['actual'],err,
                abs(err) if err is not None else None,r['outcome_state'],r['cutoff_utc'],r['kickoff_utc'],
                r['source_feature_max_utc'],r['fallback'] if method==METHODS[0] else 'training_only_control',
                'exposed_current_vintage_reconstruction_not_original_pregame'])
    csv_text=scorecard.getvalue()
    score_doc={'version':VERSION,'target':'nick-chart-ppr-v1','plan_sha256':sha(plan_bytes),'freeze_sha256':sha(freeze_body),
        'rows':rows,'metrics':metrics,'weekly':weekly,'role_metrics':rolemetrics,'coverage_slices':coverage_slices,'paired_contrasts':contrasts,
        'private_scorecard_csv_utf8':csv_text,'private_scorecard_rows':len(rows)*len(METHODS),
        'private_scorecard_sha256':sha(csv_text.encode())}
    score_body=gzip.compress(encoded(score_doc),mtime=0)
    if len(score_body)>plan['resources']['single_gzip_cap_bytes']:raise ValueError('complete grade exceeds cap')
    summary={'version':VERSION,'state':'ONE_CHART_MEDIAN_FIT_AND_EXPOSED_2026_EVALUATION_COMPLETE','target':'nick-chart-ppr-v1',
        'plan_sha256':sha(plan_bytes),'fits':1,'fitted_iterations':int(model.n_iter_),'model_sha256':sha(trained_pickle),
        'forecast_rows':len(frozen),'method_forecast_values':len(frozen)*len(METHODS),'training':freeze_doc['training'],
        'seasons':{'train':[2024],'evaluation':[2026],'2026_weeks':sorted({r['identity']['week'] for r in rows})},
        'query_coverage':{'planned':2117,'scored':1954,'games':len({r['identity']['game_id'] for r in rows}),
            'scored_games':len({r['identity']['game_id'] for r in scored}),'outcome_states':dict(states),
            'feature_queries_available':sum(r['feature_query_available'] for r in rows),'model_forecasts':len(warm_indices),'fallbacks':dict(fallbacks)},
        'metrics':metrics,'weekly':weekly,'role_metrics':rolemetrics,'coverage_slices':coverage_slices,'paired_contrasts':contrasts,
        'freeze_capsule_sha256':sha(freeze_body),'freeze_capsule_bytes':len(freeze_body),'score_capsule_sha256':sha(score_body),'score_capsule_bytes':len(score_body),'private_scorecard_rows':len(rows)*len(METHODS),'private_scorecard_sha256':sha(csv_text.encode()),
        'new_live_use':False,'prospective':False,'distribution_or_prop_probabilities':'UNAVAILABLE_POINT_ONLY',
        'same_chart_website_reference':'UNAVAILABLE_OLD_SITE_CONTRACT_NOT_SUBSTITUTED','position_semantics':'qualifiedweeklysourcecurrent-vintageposition,notarchivedasofinjuryorrolefacts',
        'limitations':['onefixedHGBchallenger notexhaustivebest','2024trainingmissinglabels retainedcoverage,notzeroimputed','2025PPRlabelsnottrained;2025footballmayappear lagged2026features','exposedcurrentvintage7dayavailabilityassumption','source-listedpopulationnotofferedcompleteboard','rolepositionscurrentvintage;nonews/injuryadaptation','nominalpairedintervalsnotindependentconfirmation','nocoherentjointlaw/componentexpectationmodel','notoperationallyqualifiedorfuturepregameissued']}
    progress['completed_scoring_runs']+=1
    return score_body,summary
