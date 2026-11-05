"""One saved-state conditional-exposure continuation with immutable forecasts.

No original forecasts/grades are altered. All periods remain research-exposed.
"""
from pathlib import Path
import collections
import datetime
import gzip
import hashlib
import io
import json
import math
import os
import resource
import signal
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
OUT=ROOT/'reports/abc-championship/post-wave-5w-v1'
ARM='A3_CONDITIONAL_PLAYED_EXPOSURE'


def enc(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    begin=time.monotonic();cpu=time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(480,481));resource.setrlimit(resource.RLIMIT_AS,(1610612736,)*2);signal.alarm(600)
    import numpy as np,pandas as pd
    from nfl_lab import abc_conditional_carry_v1 as core,abc_dynamic_carry_v1 as oldcore
    from tools.category_topfive_matched12_storage_v1 import open_store,GO
    protocol=json.loads((OUT/'A3_CONDITIONAL_EXPOSURE_PROTOCOL_V1.json').read_bytes())
    execution=json.loads((OUT/'A3_EXECUTION_BINDINGS_V1.json').read_bytes())
    for ref in execution['source_bindings']:
        if sha((ROOT/ref['path']).read_bytes())!=ref['sha256']:raise ValueError('registered A3 source changed')
    cache=Path(os.environ['ABC_C_CODE_CACHE'])
    for ref in execution['C_bound_code']:
        if sha((cache/Path(ref['path']).name).read_bytes())!=ref['sha256']:raise ValueError('bound C scorer/dependency differs')
    sys.path.insert(0,str(cache));import abc_championship_v2 as common
    store,_=open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=GO)
    destination=store.forward_root/'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
    oldref=json.loads((ROOT/'reports/abc-championship/predictive-improvement-01/completion-v3/SCORING_RECEIPT_V1.json').read_bytes())
    oldpath=destination/'GRADED_SCORECARD_V1.zip';store.validate_reference(oldpath,oldref['sha256'])
    with zipfile.ZipFile(oldpath)as z:
        retained=json.loads(gzip.decompress(z.read('NUMERICAL_ROWS.json.gz')))
        oldgrades=json.loads(gzip.decompress(z.read('OFFER_GRADE_ROWS.json.gz')))
    forecast_path=destination/'POST_WAVE_A3_FORECASTS_V1.json.gz'
    if forecast_path.exists():raise ValueError('immutable A3 forecasts exist; do not rerun unchanged')
    key=lambda r:(r['season'],r['game_id'],r['player_id'])
    eligible=lambda r:r['week'] in protocol['evaluation'].get(str(r['season']),[])
    states=[r for r in retained if r['arm']=='A2_DYNAMIC_ALLOCATION'and eligible(r)]
    forecasts=[];clipped=0;max_mass=0.;max_mean=0.;checks=0
    identity=['season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc','source_information_max_UTC','fallback']
    version=sha(enc({'procedure':core.VERSION,'source_bindings':execution['source_bindings'],
                     'training_rule':'Original earlier-only annual raw state parameters; fixed saved states, no new fit',
                     'formula':protocol['law']}))
    for state in states:
        source=pd.Timestamp(state['source_information_max_UTC']);cutoff=pd.Timestamp(state['cutoff_utc'])
        if source.tzinfo is None or cutoff.tzinfo is None or not source<cutoff:raise ValueError('future/unknown A3 state clock')
        params,law=core.predict(state['law'])
        # Positive control for cohort/outcome isolation uses copied dictionaries,
        # never target-game outcomes in the callable's four allowed inputs.
        probe={**state['law'],'actual':-999999,'other_probability':.999,'other_weight':99999,'cohort_size':99999}
        if core.parameters(probe)!=params:raise ValueError('unrelated cohort/outcome changed A3 parameters')
        mass=law['pmf'];error=abs(float(mass.sum())-1);me=abs(float(np.arange(len(mass))@mass)-law['mean'])
        if error>1e-10 or me>1e-7 or (mass<0).any():raise ValueError('A3 marginal invalid')
        clipped+=int(params['moment_concentration_clipped']);max_mass=max(max_mass,error);max_mean=max(max_mean,me);checks+=1
        r={k:state[k]for k in identity};r.update(arm=ARM,procedure_version=version,mean=law['mean'],median=law['median'],
            generation_UTC=now(),original_issued_UTC=None,law={**params,'pmf':mass.tolist(),'omitted_mass_bound':law['omitted_mass_bound']})
        forecasts.append(r)
    raw=gzip.compress(enc({'state':'FROZEN_NEW_HISTORICAL_FORECASTS_NOT_PREGAME','forecasts':forecasts,
        'procedure_version':version,'original_state_archive_sha256':oldref['sha256']}),mtime=0)
    if len(raw)>1600000:raise ValueError('A3 forecast allocation exceeds retained envelope')
    store.write_bytes(forecast_path,raw);store.validate_reference(forecast_path,sha(raw))
    (OUT/'A3_FORECAST_FREEZE_V1.json').write_text(json.dumps({'state':'IMMUTABLE_READBACK_BEFORE_NEW_GRADING','procedure_version':version,
        'rows':len(forecasts),'bytes':len(raw),'sha256':sha(raw),'persisted_UTC':now(),'new_optimizer_fits':0,
        'generation_is_historical_reconstruction':True,'original_pregame_capture':False},indent=2)+'\n')
    # Outcomes are joined only after the new forecast freeze. They were already
    # exposed in the prior programme; this is not an untouched holdout claim.
    truth={key(r):r for r in retained if r['arm']=='A2_DYNAMIC_ALLOCATION'and eligible(r)}
    numeric=[]
    for f in forecasts:
        t=truth[key(f)];numeric.append({**f,**{k:t[k]for k in ['actual','participation','outcome_state','outcome_version']}})
    controls=[r for r in retained if eligible(r)and r['arm']!='STORED_COUNT_A_MEAN_CONTROL']
    numeric_all=numeric+controls+[r for r in retained if eligible(r)and r['arm']=='STORED_COUNT_A_MEAN_CONTROL']
    def numeric_summary(rows,product):
        valid=[r for r in rows if r['actual']is not None and r.get(product)is not None]
        e=np.array([r[product]-r['actual']for r in valid]);ae=np.abs(e)
        return {'expected':len(rows),'scored':len(valid),'unknown_outcomes':sum(r['actual']is None for r in rows),
            'unsupported_output_rows':sum(r.get(product)is None for r in rows),'games':len({r['game_id']for r in valid}),
            'MAE':float(ae.mean())if len(e)else None,'MSE':float((e*e).mean())if len(e)else None,
            'RMSE':float(np.sqrt((e*e).mean()))if len(e)else None,'bias':float(e.mean())if len(e)else None,
            'p95_absolute_error':float(np.quantile(ae,.95))if len(e)else None,
            'strict_error_lt1':int((ae<1).sum()),'inclusive_error_le1':int((ae<=1).sum()),'exact_unrounded':int((ae==0).sum())}
    numeric_results=[]
    for year in [2025,2026]:
        for arm in sorted({r['arm']for r in numeric_all if r['season']==year}):
            rr=[r for r in numeric_all if r['season']==year and r['arm']==arm]
            for week in ['ALL']+sorted({r['week']for r in rr}):
                rows=[r for r in rr if week=='ALL'or r['week']==week]
                for product in ['mean','median']:
                    numeric_results.append({'season':year,'week':week,'actual_weeks':sorted({r['week']for r in rows}),
                        'arm':arm,'product':product,**numeric_summary(rows,product)})
    fidx={key(r):r for r in numeric}
    board=[r for r in oldgrades if r['arm']=='A0_BACKFIELD_CDF'and r['policy']=='P1_MEAN']
    if len(board)!=239:raise ValueError('frozen primary RB board differs')
    grades=[];same_law=0
    for original in board:
        f=fidx.get(key(original))
        if f is None:raise ValueError('new method omitted an eligible offered RB')
        line=original['line'];ps=oldcore.event_probabilities(np.asarray(f['law']['pmf']),line)
        probside='ABSTAIN'if abs(ps['p_over']-ps['p_under'])<=1e-12 else'OVER'if ps['p_over']>ps['p_under']else'UNDER'
        if line%1==.5:
            median_side=common.a.point_side(f['median'],line)
            if probside!='ABSTAIN'and median_side!=probside:raise ValueError('same-law median/probability direction mismatch')
            same_law+=1
        for policy in ['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW','P2_EXACT_LAW_CONF55']:
            point=f['mean'if policy=='P1_MEAN'else'median']if policy.startswith('P1')else None
            side=common.a.point_side(point,line)if policy.startswith('P1')else probside
            if policy=='P2_EXACT_LAW_CONF55'and max(ps['p_over'],ps['p_under'])<.55:side='ABSTAIN'
            r={**original,'arm':ARM,'policy':policy,'point':point,'selected_side':side,'fallback':f['fallback'],**ps}
            if side=='ABSTAIN':r['status']='ABSTAIN'
            r['status']=common.status(r);grades.append(r)
    summaries=[]
    for policy in ['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW','P2_EXACT_LAW_CONF55']:
        for week in ['ALL']+list(range(1,8)):
            rr=[r for r in grades if r['policy']==policy and(week=='ALL'or r['week']==week)]
            summaries.append({'arm':ARM,'policy':policy,'week':week,**common.summary(rr)})
    proper_rows=[r for r in grades if r['policy']=='P2_EXACT_LAW'and r['appearance']=='PLAYED'and r['actual']is not None]
    log_scores=[-math.log(p)if p>0 else math.inf for r in proper_rows for p in [r['p_over']if r['actual']>r['line']else r['p_under']]]
    log_loss=float(np.mean(log_scores))
    proper={'n':len(proper_rows),'Brier':float(np.mean([(r['p_over']-int(r['actual']>r['line']))**2 for r in proper_rows])),
            'log_loss':log_loss if math.isfinite(log_loss)else None,
            'log_loss_state':'FINITE'if math.isfinite(log_loss)else'POSITIVE_INFINITY',
            'log_loss_reason':None if math.isfinite(log_loss)else'Actual event assigned zero probability; no probability floor inserted.',
            'neutral_half_integer_Brier':.25,'conditioning':'Known played, decisive halfinteger events; all supported probabilities, not only selected highconfidence picks.'}
    oldidx={(r['arm'],r['policy'],r['opportunity_key']):r for r in oldgrades}
    def interval(rr,cluster):
        grouped=collections.defaultdict(list)
        for r in rr:grouped[str(r[cluster])].append(r['delta'])
        keys=sorted(grouped);sums=np.array([sum(grouped[k])for k in keys]);counts=np.array([len(grouped[k])for k in keys]);rng=np.random.default_rng(1703)
        ix=rng.integers(len(keys),size=(1000,len(keys)));values=sums[ix].sum(1)/counts[ix].sum(1)
        return {'clusters':len(keys),'low':float(np.quantile(values,.025)),'high':float(np.quantile(values,.975))}
    paired=[]
    for policy in ['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW']:
        for arm in ['A0_BACKFIELD_CDF','A1_BACKFIELD_CDF_ROLE_INPUTS','A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION','STORED_COUNT_A_MEAN_CONTROL','ALWAYS_OVER','ALWAYS_UNDER']:
            cp='CONSTANT'if arm.startswith('ALWAYS_')else'P1_MEAN'if arm=='STORED_COUNT_A_MEAN_CONTROL'else policy
            rr=[]
            for r in grades:
                if r['policy']!=policy or r['status']not in ['WIN','LOSS']:continue
                s=oldidx.get((arm,cp,r['opportunity_key']))
                if not s or s['status']not in ['WIN','LOSS']:continue
                if r['actual']!=s['actual']or r['line']!=s['line']:raise ValueError('paired actual/line differs')
                rr.append({'game_id':r['game_id'],'week':r['week'],'delta':int(r['status']=='WIN')-int(s['status']=='WIN'),
                           'left_win':int(r['status']=='WIN'),'right_win':int(s['status']=='WIN')})
            paired.append({'left':ARM,'left_policy':policy,'right':arm,'right_policy':cp,'n':len(rr),
                'left_wins':sum(r['left_win']for r in rr),'right_wins':sum(r['right_win']for r in rr),
                'rate_change':sum(r['delta']for r in rr)/len(rr),'game_CI':interval(rr,'game_id'),'week_CI':interval(rr,'week')})
    top=[]
    for policy in ['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW']:
        selected=[]
        for week in range(1,8):
            rr=[r for r in grades if r['policy']==policy and r['week']==week and r['selected_side']in['OVER','UNDER']]
            ranked=sorted(rr,key=lambda r:(-(abs(r['point']-r['line'])if policy.startswith('P1')else max(r['p_over'],r['p_under'])),r['opportunity_key']))
            for K in [6,10,20]:
                chosen=ranked[:K];selected.extend([(K,r)for r in chosen]);top.append({'policy':policy,'week':week,'K_per_category_week':K,**common.summary(chosen)})
        for K in [6,10,20]:top.append({'policy':policy,'week':'ALL','K_per_category_week':K,**common.summary([r for k,r in selected if k==K])})
    factored=[{**r,'law':{k:v for k,v in r['law'].items()if k!='pmf'},
               'full_law_reference':{'forecast_archive_sha256':sha(raw),'key':list(key(r))}}for r in numeric]
    grade_raw=gzip.compress(enc({'numeric':factored,'actual_line_grades':grades,'original_output_versions_unchanged':True}),mtime=0)
    if len(raw)+len(grade_raw)>2097152:raise ValueError('inclusive A3 forecast/grade budget exceeded')
    grade_path=destination/'POST_WAVE_A3_GRADED_V1.json.gz';store.write_bytes(grade_path,grade_raw);store.validate_reference(grade_path,sha(grade_raw));usage=store.verify_retained_checkpoint()
    result={'state':'COMPLETED_ONE_NEW_CONDITIONAL_MECHANISM','procedure_version':version,'procedure':core.VERSION,
        'new_inferred_forecast_rows':len(forecasts),'new_optimizer_fits':0,'new_genuine_pregame_captures':0,
        'evaluation':protocol['evaluation'],'numerical_results':numeric_results,'actual_line_results':summaries,
        'full_board_probability':proper,'paired_selection':paired,'TopK_timing_unverified_diagnostics':top,
        'numerical_checks':{'new_marginals':checks,'clipped_Beta_moment_concentrations':clipped,'maximum_mass_error':max_mass,
            'maximum_numerical_mean_error':max_mean,'same_law_halfinteger_checks':same_law,'MC_draws':0,'cohort_and_outcome_input_invariance':'PASS'},
        'private_forecasts':{'sha256':sha(raw),'bytes':len(raw)},'private_grades':{'sha256':sha(grade_raw),'bytes':len(grade_raw)},
        'private_readback':'PASS_OWNER_LOCAL','offhost_restore':'NOT_VERIFIED','ninety_percent_target':'NOT_ESTABLISHED; no learned gate fitted',
        'evidence':'EXPOSED_CURRENT_VINTAGE_CHRONOLOGICAL_RECONSTRUCTION;actual_lines_quote_and_settlement_timing_unverified',
        'not_joint':'Individual conditional-on-appearance Beta moment projection; no finite joint allocation, unconditional participation or parlay probability claim.',
        'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'retained_headroom_bytes':usage['wave_retained_limit_bytes']-usage['new_peer_physical_bytes']}
    (OUT/'A3_CONDITIONAL_RESULTS_V1.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'state':result['state'],'new_forecasts':len(forecasts),'procedure_version':version,'CPU_seconds':result['CPU_seconds'],
        'full_board_probability':proper,'actual_line_ALL':[r for r in summaries if r['week']=='ALL']}))


if __name__=='__main__':main()
