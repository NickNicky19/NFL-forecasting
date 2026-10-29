"""One fixed signed-lattice chart CDF, matched to the retained HGB pilot.

All scores are exact multiples of0.02 chartpoints: Z=50*S is a signedinteger.
No2026 actual value is converted until complete model/forecast/CDF assignment
persistence succeeds. Historical inputs/labels and HGB pilot stay unchanged.
"""
from __future__ import annotations
from collections import Counter
import base64,csv,gzip,io,json,math,pickle,copy,time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from next_checkpoint_chart_cdf_contract import (
 ROLES,FEATURES,KEYS,NumericToken,normalized_team,key,require_identity,finite,aware,
 assert_chronology,metric,authenticate,encoded,sha)
from nfl_lab import cdf_engine as engine

VERSION='next-checkpoint-chart-cdf-control-v1'
SCALE=50
LATTICE_EPS=1e-8
CDF_MEDIAN='LEAF_CDF_CHART_MEDIAN_V1'
CDF_MEAN='LEAF_CDF_CHART_MEAN_V1'
PRIOR_MEDIAN='ROLE_LAW_CHART_MEDIAN_V1'
PRIOR_MEAN='ROLE_LAW_CHART_MEAN_V1'
HGB='HGB_CHART_MEDIAN_V1'
POSITION='POSITION_CHART_MEDIAN_2024'
GLOBAL='GLOBAL_CHART_MEDIAN_2024'
POSITION_MEAN='POSITION_CHART_MEAN_2024'
METHODS=[CDF_MEDIAN,CDF_MEAN,PRIOR_MEDIAN,PRIOR_MEAN,HGB,POSITION,GLOBAL,POSITION_MEAN]
TARGET='chart_lattice_002_v1'
PARAMETERS=dict(engine.TREE_PARAMETERS)


def lattice(value):
    z=np.asarray(value,dtype=float)*SCALE
    rounded=np.rint(z)
    if not np.isfinite(z).all() or (np.abs(z-rounded)>LATTICE_EPS).any():
        raise ValueError('chart label violates exact0.02point lattice; no eligibility rounding')
    return rounded.astype(float)


def ident(row):
    return tuple(row['identity'][k] for k in ['season','week','game_id','team','opponent','player_id','season_type'])


def paired(rows,candidate,control,*,loss='MAE'):
    def losses(r,m):
        if loss=='MAE':return abs(r['predictions'][m]-r['actual'])
        if loss=='MSE':return (r['predictions'][m]-r['actual'])**2
        return r['distribution_scores'][m]['CRPS']
    delta=np.asarray([losses(r,candidate)-losses(r,control)for r in rows])
    base=float(np.mean([losses(r,control)for r in rows]));value=float(delta.mean())
    out={'candidate':candidate,'control':control,'loss':loss,'n':len(rows),
        'mean_loss_difference':value,'relative_improvement_percent':-100*value/base if base else None}
    for field in ['game_id','week']:
        groups={}
        for r,d in zip(rows,delta):groups.setdefault(r['identity'][field],[]).append(d)
        values=list(groups.values());n=len(values)
        if n<8:out[field+'_interval']={'state':'UNAVAILABLE_FEWER_THAN8CLUSTERS','clusters':n};continue
        sums=np.asarray([sum(v)for v in values]);sizes=np.asarray([len(v)for v in values]);rng=np.random.default_rng(1703)
        boot=[]
        for _ in range(500):
            draw=rng.integers(0,n,n);boot.append(sums[draw].sum()/sizes[draw].sum())
        out[field+'_interval']={'state':'NOMINAL_EXPOSED_DEVELOPMENT_DIAGNOSTIC','clusters':n,'confidence':.95,
            'replicates':500,'seed':1703,'lower':float(np.quantile(boot,.025)),'upper':float(np.quantile(boot,.975))}
    return out


def summary_nll(values):
    a=np.asarray(values,dtype=float)
    if np.isnan(a).any() or np.isneginf(a).any():raise ValueError('invalid negative logmass')
    n=int(np.isposinf(a).sum())
    return {'state':'POSITIVE_INFINITY' if n else 'FINITE','positive_infinite_rows':n,
            'value':None if n else float(a.mean())}


def build(plan_bytes,go,freeze,progress):
    plan=json.loads(plan_bytes)
    if (plan['version']!=VERSION or plan['state']!='ROOT_AND_INDEPENDENT_SEALED'
        or plan['execution_authorized'] is not True or plan['independent_review']!='PASS'
        or plan['root_registration']['registered_by']!='/root'
        or go['state']!='ROOT_AND_INDEPENDENT_GO' or go['plan_sha256']!=sha(plan_bytes)
        or go['registered_by']!='/root' or go['independent_review']!='PASS'
        or plan['features']!=FEATURES or plan['tree_parameters']!=PARAMETERS
        or plan['score_lattice_scale']!=SCALE or plan['lattice_tolerance']!=LATTICE_EPS):
        raise ValueError('exact new chart CDF seal required')
    if len(FEATURES)!=32 or any('snap' in f or 'fantasy_ppr'in f for f in FEATURES):
        raise ValueError('same32non-snap/non-old-PPRfeatures required')
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
    old_freeze=json.loads(gzip.decompress(bodies['original_HGB_forecasts']))
    if (old_freeze['target']!='nick-chart-ppr-v1' or old_freeze['source_label_capsule_sha256']!=old_hash
        or old_freeze['features']!=FEATURES or len(old_freeze['forecasts'])!=2117):
        raise ValueError('retained HGB target/source/feature/fullpopulation differs')
    old_by={ident(r):r for r in old_freeze['forecasts']}
    if len(old_by)!=2117:raise ValueError('duplicate original HGB forecast identities')
    qrows=[];frozen=[];fallbacks=Counter()
    for k,r in query_labels.items():
        identity={kk:(int(v)if kk in ['season','week']else v)for kk,v in r['identity'].items()}
        role=positions[2026][k]['position'];q=qlookup.get(k)
        if q is not None:require_identity(r,q)
        reason=''
        if q is None:reason='missing_feature_query_position_prior'
        elif pd.isna(q.get('feature_max_source_available_utc')):reason='unknown_feature_clock_position_prior'
        elif not finite(q.get('f_player_games_prior')) or float(q['f_player_games_prior'])<=0:reason='cold_or_unknown_history_position_prior'
        if role not in priors:reason='unseen_role_global_prior'
        qr=dict(q)if q is not None else {f:float('nan')for f in FEATURES}
        qr.update(position=role);qrows.append(qr)
        previous=old_by.get(tuple(identity[k]for k in ['season','week','game_id','team','opponent','player_id','season_type']))
        if previous is None or previous['position']!=role or previous['fallback']!=reason:
            raise ValueError('full same HGB identity/position/fallback eligibility mismatch')
        row={'identity':identity,'position':role,'predictions':dict(previous['predictions']),
            'fallback':reason,'feature_query_available':q is not None,
            'cutoff_utc':str(q['cutoff_utc'])if q else None,'kickoff_utc':str(q['kickoff_utc'])if q else None,
            'source_feature_max_utc':str(q['feature_max_source_available_utc'])if q and pd.notna(q['feature_max_source_available_utc'])else None}
        def comparable_clock(value):
            if value is None or value=='NaT' or pd.isna(value):return None
            return aware(value)
        if any(comparable_clock(row[k])!=comparable_clock(previous[k])for k in ['cutoff_utc','kickoff_utc','source_feature_max_utc']):
            raise ValueError('same HGB information-horizon mismatch')
        if reason:fallbacks[reason]+=1
        frozen.append(row)
    if old_freeze['training']['model_rows']!=len(modeled) or old_freeze['fallbacks']!=dict(fallbacks):
        raise ValueError('same retained HGB model-training/fallback population differs')
    modeltrain=pd.DataFrame(modeled)
    modeltrain[TARGET]=lattice(modeltrain['_chart_y'].to_numpy(float))
    modeltrain['participation_state']='played'
    category={'target':TARGET,'state':'READY','support':'signed_integer','modeled_roles':ROLES,
        'primary_roles':ROLES,'panels':{'base':FEATURES,'context':FEATURES}}
    engine.assert_clock_contract(modeltrain)
    progress['fit_attempts']+=1
    model=engine.LeafCDFModel.fit(modeltrain,category,'base')
    if model.forest is None or len(model.forest.estimators_)!=32:raise ValueError('one complete32tree forest required')
    progress['completed_fits']+=1;progress['fitted_trees']=32
    # Forest uses feature-admitted rows; proper priors use ALL5589 complete
    # qualified2024 labels, matching the HGB prior information population.
    all_z=lattice(train_values)
    model.global_prior=engine.SupportPrior.fit(all_z,'signed_integer')
    model.priors={role:engine.SupportPrior.fit(all_z[np.asarray(train_roles)==role],'signed_integer')for role in sorted(set(train_roles))}
    prior_binding=[]
    for k,value,role in zip(eligible,train_values,train_roles):
        identity=train_labels[k]['identity'];cal=schedules[identity['game_id']]
        prior_binding.append({'season':2024,'week':int(identity['week']),'game_id':identity['game_id'],
            'player_id':identity['player_id'],'position':role,'kickoff_utc':str(cal['kickoff_utc']),
            'outcome_available_utc':str(aware(cal['kickoff_utc'])+pd.Timedelta(days=7)),
            'availability_state':'HISTORICAL_KICKOFF_PLUS_7DAY_ASSUMPTION_NOT_VERIFIED_PUBLICATION',
            TARGET:float(lattice([value])[0])})
    if len(prior_binding)!=5589:raise ValueError('all qualified prior labels must be retained')
    model.prior_training_binding=pd.DataFrame(prior_binding)
    model.audit.update(prior_training_rows=5589,prior_population='allcompletequalified2024includingfeaturemissing',
        role_priors={k:vars(v)for k,v in model.priors.items()},global_prior=vars(model.global_prior))
    qframe=pd.DataFrame(qrows)
    # One query apply. Exact memberships and fitted histograms are retained so
    # post-freeze proper scoring uses the original laws, never outcome-refitted laws.
    progress['model_prediction_calls']+=1
    with engine.threadpool_limits(limits=2):
        leaf_ids=model.forest.apply(model.design.transform(qframe)).astype(np.int32)
    law_batches=[]
    roles=qframe.position.to_numpy()
    for role in sorted(set(roles)):
        prior=model.priors.get(role,model.global_prior)
        if prior is None:raise ValueError('complete role/globalprior needed')
        for is_fallback in [False,True]:
            indices=np.asarray([i for i,r in enumerate(frozen)if r['position']==role and bool(r['fallback'])==is_fallback],dtype=int)
            for start in range(0,len(indices),128):
                batch=indices[start:start+128]
                if is_fallback:
                    law=engine.MixtureBatch(np.array([0.]),np.ones((len(batch),1)),prior,prior_weight=1.)
                else:
                    weights=np.zeros((len(batch),len(model.support)))
                    for j,hist in enumerate(model.leaf_histograms):weights+=hist[leaf_ids[batch,j]].toarray()
                    law=engine.MixtureBatch(model.support,weights/32,prior)
                priorlaw=engine.MixtureBatch(np.array([0.]),np.ones((len(batch),1)),prior,prior_weight=1.)
                law_batches.append((batch,law,priorlaw))
                for name,values in [(CDF_MEDIAN,law.quantile(.5)/SCALE),(CDF_MEAN,law.mean/SCALE),
                        (PRIOR_MEDIAN,priorlaw.quantile(.5)/SCALE),(PRIOR_MEAN,priorlaw.mean/SCALE)]:
                    for i,value in zip(batch,values):frozen[int(i)]['predictions'][name]=float(value)
                lo,hi=law.quantile(.1)/SCALE,law.quantile(.9)/SCALE
                plo,phi=priorlaw.quantile(.1)/SCALE,priorlaw.quantile(.9)/SCALE
                for j,i in enumerate(batch):
                    frozen[int(i)]['distribution_intervals']={'LEAF_CDF':{'p10':float(lo[j]),'p90':float(hi[j])},
                        'ROLE_PRIOR':{'p10':float(plo[j]),'p90':float(phi[j])}}
    if len(frozen)!=2117 or any(set(r['predictions'])!=set(METHODS)or not all(math.isfinite(v)for v in r['predictions'].values())for r in frozen):
        raise ValueError('complete finite samepopulation point vectors required')
    slim=copy.copy(model);slim.training_binding=slim.prior_training_binding=slim.training_leaf_ids=None
    modelbytes=pickle.dumps(slim,protocol=5)
    bindings=modeltrain[['season','week','game_id','player_id','position','kickoff_utc','cutoff_utc','outcome_available_utc','feature_max_source_available_utc',TARGET]].copy()
    for col in ['kickoff_utc','cutoff_utc','outcome_available_utc','feature_max_source_available_utc']:bindings[col]=bindings[col].astype(str)
    freeze_doc={'version':VERSION,'state':'COMPLETE_CDF_MODEL_LAW_ASSIGNMENTS_AND_POINTS_FROZEN_BEFORE_EVAL_NUMERIC_CONVERSION',
        'target':'nick-chart-ppr-v1','plan_sha256':sha(plan_bytes),'source_label_capsule_sha256':old_hash,
        'old_HGB_forecasts_sha256':plan['inputs']['original_HGB_forecasts']['sha256'],
        'training':{'season':2024,'planned':5935,'supported_numeric':5589,'model_rows':len(modeled),'missingness':dict(counts)},
        'features':FEATURES,'tree_parameters':PARAMETERS,'fitted_tree_count':32,
        'category':category,'score_lattice_scale':SCALE,'lattice_tolerance':LATTICE_EPS,
        'prior_weight':engine.PRIOR_WEIGHT,'fitted_model_pickle_base64':base64.b64encode(modelbytes).decode(),
        'fitted_model_sha256':sha(modelbytes),'training_binding':bindings.to_dict('records'),'prior_training_binding':prior_binding,
        'query_leaf_ids':{'dtype':'int32','shape':list(leaf_ids.shape),'bytes_base64':base64.b64encode(leaf_ids.tobytes()).decode()},
        'forecasts':frozen,'fallbacks':dict(fallbacks),
        'CDF_contract':'S=Z/50; fullsignedintegerZ law;0.02pointlattice;95%empiricalleaf+5%roleprior;100%roleprioronregisteredcoldfallback',
        'mean_contract':'Exactmeanofretainedcorrespondinglaw; notHGBpoint ormedianfallback',
        'median_contract':'Lower0.5quantileofretainedlaw; coldCDFprior-median maydifferfromHGBempiricalmedianfallback',
        'position_semantics':'originalcurrent-vintageweeklyposition;notarchivedinjury/asofrolefacts',
        'evidence_lane':'exposed_current_vintage_7day_assumption_reconstruction_not_prospective'}
    fb=gzip.compress(encoded(freeze_doc),mtime=0)
    if len(fb)>plan['resources']['single_gzip_cap_bytes']:raise ValueError('completeCDFmodel/forecastcapsule cap exceeded')
    frozen_ref=freeze('FORECASTS_FROZEN.json.gz',fb);progress['durably_frozen_forecast_rows']=len(frozen)
    # First actual2026 numeric outcome access occurs only here after exact CAS readback.
    progress['scoring_runs_started']+=1
    old_grade=json.loads(gzip.decompress(bodies['original_HGB_grades']))
    if old_grade['freeze_sha256']!=plan['inputs']['original_HGB_forecasts']['sha256']:
        raise ValueError('original HGB grade/freeze binding differs')
    old_graded={ident(r):r for r in old_grade['rows']}
    rows=[];states=Counter()
    for f in frozen:
        label=query_labels[key(f['identity'])];state=label['state'];states[state]+=1
        actual=float(label['value'])if label['value']is not None and state in ['played_score','played_zero']else None
        if actual is not None:lattice([actual])
        previous=old_graded.get(ident(f))
        if previous is None or previous['actual']!=actual or previous['outcome_state']!=state:
            raise ValueError('matched oldHGB actual/participation conflicts')
        row={**f,'actual':actual,'outcome_state':state,
            'errors':{m:f['predictions'][m]-actual if actual is not None else None for m in METHODS},
            'distribution_scores':{}}
        rows.append(row)
    for indices,law,priorlaw in law_batches:
        selected=np.asarray([j for j,i in enumerate(indices)if rows[int(i)]['actual']is not None],dtype=int)
        if not len(selected):continue
        chosen=indices[selected];y=lattice([rows[int(i)]['actual']for i in chosen])
        for name,original in [('LEAF_CDF',law),('ROLE_PRIOR',priorlaw)]:
            retainedlaw=engine.MixtureBatch(original.support,original.weights[selected],original.prior,prior_weight=original.b)
            crps=retainedlaw.crps(y)/SCALE;nll=-retainedlaw.logpmf(y)
            for i,c,n in zip(chosen,crps,nll):
                if math.isnan(n)or n==-math.inf:raise ValueError('invalid proper logmass')
                rows[int(i)]['distribution_scores'][name]={'CRPS':float(c),'negative_log_mass':float(n)if math.isfinite(n)else 'POSITIVE_INFINITY'}
    scored=[r for r in rows if r['actual']is not None]
    if len(scored)!=1954 or states['unknown_participation']!=163:raise ValueError('same fullplanned/supported population differs')
    def scores(part):return {m:metric([r['actual']for r in part],[r['predictions'][m]for r in part])for m in METHODS}
    metrics=scores(scored)
    distribution={}
    for name in ['LEAF_CDF','ROLE_PRIOR']:
        vals=[r['distribution_scores'][name]for r in scored]
        nll=[v['negative_log_mass']if v['negative_log_mass']!='POSITIVE_INFINITY'else math.inf for v in vals]
        lo=np.asarray([r['distribution_intervals'][name]['p10']for r in scored]);hi=np.asarray([r['distribution_intervals'][name]['p90']for r in scored]);ys=np.asarray([r['actual']for r in scored])
        distribution[name]={'n':len(vals),'CRPS':float(np.mean([v['CRPS']for v in vals])),
            'negative_log_mass':summary_nll(nll),'interval80_coverage_inclusive':float(np.mean((ys>=lo)&(ys<=hi))),
            'interval80_mean_width':float(np.mean(hi-lo)),
            'interval80_score':float(np.mean(hi-lo+10*np.maximum(lo-ys,0)+10*np.maximum(ys-hi,0)))}
    contrasts=[paired(scored,CDF_MEDIAN,m)for m in [HGB,POSITION,GLOBAL]]
    contrasts+=[paired(scored,CDF_MEAN,POSITION_MEAN,loss='MSE'),paired(scored,'LEAF_CDF','ROLE_PRIOR',loss='CRPS')]
    weekly={};by_role={};slices={}
    for week in range(1,7):
        part=[r for r in rows if r['identity']['week']==week];good=[r for r in part if r['actual']is not None]
        weekly[str(week)]={'planned':len(part),'scored':len(good),'outcome_states':dict(Counter(r['outcome_state']for r in part)),'metrics':scores(good)if good else {}}
    for role in ROLES:
        good=[r for r in scored if r['position']==role]
        if good:by_role[role]=scores(good)
    for name,fallback in [('model_only',False),('fallback_only',True)]:
        part=[r for r in rows if bool(r['fallback'])==fallback];good=[r for r in part if r['actual']is not None]
        slices[name]={'planned':len(part),'scored':len(good),'outcome_states':dict(Counter(r['outcome_state']for r in part)),'metrics':scores(good)if good else {}}
    card=io.StringIO();writer=csv.writer(card,lineterminator='\n')
    writer.writerow(['season','week','game_id','player_id','team','opponent','position','method','prediction_chart_points','actual_chart_points','signed_error','absolute_error','outcome_state','fallback','cutoff_utc','kickoff_utc','evidence_lane'])
    for r in rows:
        i=r['identity']
        for m in METHODS:
            e=r['errors'][m];writer.writerow([i['season'],i['week'],i['game_id'],i['player_id'],i['team'],i['opponent'],r['position'],m,r['predictions'][m],r['actual'],e,abs(e)if e is not None else None,r['outcome_state'],r['fallback']if m in METHODS[:2]else '',r['cutoff_utc'],r['kickoff_utc'],'exposed_current_vintage_reconstruction'])
    csv_text=card.getvalue()
    grade={'version':VERSION,'target':'nick-chart-ppr-v1','plan_sha256':sha(plan_bytes),'freeze_sha256':sha(fb),'rows':rows,
        'metrics':metrics,'distribution_metrics':distribution,'paired_contrasts':contrasts,'weekly':weekly,'role_metrics':by_role,'coverage_slices':slices,
        'private_scorecard_csv_utf8':csv_text,'private_scorecard_rows':len(rows)*len(METHODS),'private_scorecard_sha256':sha(csv_text.encode())}
    payload=gzip.compress(encoded(grade),mtime=0)
    if len(payload)>plan['resources']['single_gzip_cap_bytes']:raise ValueError('completeCDFgrades cap exceeded')
    summary={'version':VERSION,'state':'ONE_CHART_CDF_FIT_MATCHED_HGB_POINT_AND_PRIOR_LAW_COMPARISON_COMPLETE',
        'target':'nick-chart-ppr-v1','plan_sha256':sha(plan_bytes),'fits':1,'trees':32,'evidence_lane':freeze_doc['evidence_lane'],
        'training':freeze_doc['training'],'forecast_rows':2117,'method_forecast_values':2117*len(METHODS),
        'query_coverage':{'planned':2117,'scored':1954,'games':len({r['identity']['game_id']for r in rows}),'scored_games':len({r['identity']['game_id']for r in scored}),
            'weeks':6,'outcome_states':dict(states),'fallbacks':dict(fallbacks),'model_points':sum(not r['fallback']for r in rows)},
        'metrics':metrics,'distribution_metrics':distribution,'paired_contrasts':contrasts,'weekly':weekly,'role_metrics':by_role,'coverage_slices':slices,
        'score_lattice_scale':SCALE,'law_support':'signedintegerZ/50 (0.02chartpointlattice); no nonnegative clipping',
        'fitted_model_sha256':sha(modelbytes),'freeze_capsule_sha256':sha(fb),'freeze_capsule_bytes':len(fb),'score_capsule_sha256':sha(payload),'score_capsule_bytes':len(payload),
        'private_scorecard_rows':len(rows)*len(METHODS),'private_scorecard_sha256':sha(csv_text.encode()),
        'old_HGB_forecasts_sha256':plan['inputs']['original_HGB_forecasts']['sha256'],
        'new_live_use':False,'prospective':False,'website_relative_improvement':'UNAVAILABLE_DIFFERENT_OLD_SITE_TARGET',
        'CDF_calibration':'80percentintervalcoverage/width/score diagnostics; no guarantee or completed broadcalibration',
        'limitations':['fixedoneCDFnotsearchedglobalbest','2024trainingmissinglabelsretainednotzeroimputed','qualified2025footballmayoccurinlagged2026features','exposedcurrentvintage7dayavailabilityassumption',
            'CDFrole-priorcoldmedianmaydifferfromHGBempiricalpositionmedian:separateslicesretained','oldHGBpointdoesnotsupplyCDFscore','fiveprespecifiedcontrastsnominaldevelopmentintervals','notWeek8pregame/futurequeryorconsumerqualified']}
    progress['completed_scoring_runs']+=1
    return payload,summary
