"""Paired diagnostic analysis of immutable A carry rows using pinned C summaries."""
from __future__ import annotations
import collections,gzip,hashlib,io,json,math,os,resource,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import abc_a_dynamic_carry_wave_v1 as base
OUT=ROOT/'reports/abc-championship/predictive-improvement-01'
V2=OUT/'runtime-v2';RUN='ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'

def main():
    begin=time.monotonic();cpu=time.process_time()
    import numpy as np,pandas as pd
    from tools import category_topfive_matched12_storage_v1 as st
    cache=Path(os.environ.get('ABC_C_CODE_CACHE','/tmp/abc-improvement-01/C/src'))
    bound=json.loads((V2/'PROTOCOL_V1.json').read_text())
    for ref in bound['C_bound_code']:
        if base.sha((cache/Path(ref['path']).name).read_bytes())!=ref['sha256']:raise ValueError('C evaluator binding')
    sys.path.insert(0,str(cache));import abc_championship_v2 as common
    resource.setrlimit(resource.RLIMIT_CPU,(240,241))
    store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
    destination=store.forward_root/'research'/RUN
    receipt=json.loads((OUT/'completion-v3/SCORING_RECEIPT_V1.json').read_text());path=destination/'GRADED_SCORECARD_V1.zip';store.validate_reference(path,receipt['sha256'])
    with zipfile.ZipFile(path)as z:
        numeric=json.loads(gzip.decompress(z.read('NUMERICAL_ROWS.json.gz')))
        rows=json.loads(gzip.decompress(z.read('OFFER_GRADE_ROWS.json.gz')))
    def interval(items,value,key):
        groups=collections.defaultdict(list)
        for r in items:groups[str(r[key])].append(value(r))
        clusters=list(groups);sums=np.array([sum(groups[x])for x in clusters]);counts=np.array([len(groups[x])for x in clusters])
        if len(clusters)<2:return {'clusters':len(clusters),'low':None,'high':None,'reason':'Fewer_than2clusters'}
        rng=np.random.default_rng(1703);ix=rng.integers(len(clusters),size=(1000,len(clusters)));values=sums[ix].sum(1)/counts[ix].sum(1)
        return {'clusters':len(clusters),'low':float(np.quantile(values,.025)),'high':float(np.quantile(values,.975)),'seed':1703,'bootstrap':1000}
    pairs=[];nindex={(r['season'],r['game_id'],r['player_id'],r['arm']):r for r in numeric}
    comparisons=[('A1_BACKFIELD_CDF_ROLE_INPUTS','A0_BACKFIELD_CDF'),('A2_DYNAMIC_ALLOCATION','A0_BACKFIELD_CDF'),('A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION'),('S0_RECENCY_ALLOCATION','A0_BACKFIELD_CDF'),('STORED_COUNT_A_MEAN_CONTROL','A0_BACKFIELD_CDF'),('A1_BACKFIELD_CDF_ROLE_INPUTS','STORED_COUNT_A_MEAN_CONTROL'),('A2_DYNAMIC_ALLOCATION','STORED_COUNT_A_MEAN_CONTROL')]
    for year in [2025,2026]:
        for left,right in comparisons:
            for product in ['mean','median']:
                matched=[]
                for r in numeric:
                    if r['season']!=year or r['arm']!=left or r['actual']is None or r.get(product)is None:continue
                    s=nindex.get((year,r['game_id'],r['player_id'],right))
                    if not s or s['actual']is None or s.get(product)is None:continue
                    if r['actual']!=s['actual']or r['outcome_version']!=s['outcome_version']:raise ValueError('numeric label mismatch')
                    matched.append({'game_id':r['game_id'],'week':r['week'],'left_AE':abs(r[product]-r['actual']),'right_AE':abs(s[product]-s['actual'])})
                if not matched:continue
                for week in ['ALL']+sorted({r['week']for r in matched}):
                    rr=[r for r in matched if week=='ALL'or r['week']==week];delta=lambda r:r['left_AE']-r['right_AE']
                    pairs.append({'season':year,'week':week,'left':left,'right':right,'product':product,'n':len(rr),'games':len({r['game_id']for r in rr}),'left_MAE':sum(r['left_AE']for r in rr)/len(rr),'right_MAE':sum(r['right_AE']for r in rr)/len(rr),'MAE_delta_left_minus_right':sum(delta(r)for r in rr)/len(rr),'game_CI':interval(rr,delta,'game_id'),'week_CI':interval(rr,delta,'week')})
    sindex={(r['arm'],r['policy'],r['opportunity_key']):r for r in rows};spairs=[]
    policies=['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW','P2_EXACT_LAW_CONF55']
    for left,right in comparisons+[(a,c)for a in ['A0_BACKFIELD_CDF','A1_BACKFIELD_CDF_ROLE_INPUTS','A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION']for c in ['ALWAYS_OVER','ALWAYS_UNDER']]:
        for policy in policies:
            matched=[]
            for r in rows:
                if r['arm']!=left or r['policy']!=policy or r['status']not in ['WIN','LOSS']:continue
                control_policy='CONSTANT'if right.startswith('ALWAYS_')else'P1_MEAN'if right=='STORED_COUNT_A_MEAN_CONTROL'else policy
                s=sindex.get((right,control_policy,r['opportunity_key']))
                if not s or s['status']not in ['WIN','LOSS']:continue
                if r['actual']!=s['actual']or r['line']!=s['line']:raise ValueError('selection label/line mismatch')
                matched.append({'game_id':r['game_id'],'week':r['week'],'source_stream':r['source_stream'],'left_win':int(r['status']=='WIN'),'right_win':int(s['status']=='WIN'),'disagree':r['selected_side']!=s['selected_side']})
            if not matched:continue
            for week in ['ALL']+sorted({r['week']for r in matched}):
                rr=[r for r in matched if week=='ALL'or r['week']==week];delta=lambda r:r['left_win']-r['right_win'];lw=sum(r['left_win']for r in rr);rw=sum(r['right_win']for r in rr);dd=[r for r in rr if r['disagree']]
                spairs.append({'left':left,'right':right,'policy':policy,'right_policy':control_policy,'week':week,'n':len(rr),'games':len({r['game_id']for r in rr}),'left_wins':lw,'right_wins':rw,'additional_wins_left':lw-rw,'rate_change_left':(lw-rw)/len(rr),'disagreements':len(dd),'left_wins_when_disagree':sum(r['left_win']for r in dd),'right_wins_when_disagree':sum(r['right_win']for r in dd),'game_CI':interval(rr,delta,'game_id'),'week_CI':interval(rr,delta,'week')})
    # Canonical scorer in distinct source strata, with all operational rows.
    sg=collections.defaultdict(list)
    for r in rows:
        if common.status(r)!=r['status']:raise ValueError('saved status differs from bound scorer')
        sg[(r['source_stream'],r['arm'],r['policy'])].append(r)
    strata=[{'source_stream':s,'arm':a,'policy':p,**common.summary(rs)}for(s,a,p),rs in sorted(sg.items())]
    # Same frozen per-category/week TopK rules, honestly last-available diagnostics.
    top_rows=[];top_summary=[];topgroup=collections.defaultdict(list)
    for r in rows:
        if r['policy']not in ['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW']or r['selected_side']not in ['OVER','UNDER']:continue
        score=abs(r['point']-r['line'])if r['policy'].startswith('P1')else max(r['p_over'],r['p_under'])
        topgroup[(r['arm'],r['policy'],r['week'])].append((score,r))
    for (arm,policy,week),rs in sorted(topgroup.items()):
        ranked=sorted(rs,key=lambda x:(-x[0],x[1]['opportunity_key']))
        for k in [6,10,20]:
            chosen=[dict(r,rank=i+1,ranking_score=float(score),K=k,ranking_scope='category_week_last_available_diagnostic')for i,(score,r)in enumerate(ranked[:k])]
            top_rows+=chosen;top_summary.append({'arm':arm,'policy':policy,'week':week,'K':k,'eligible_board':len(rs),'timing_status':'UNVERIFIED_NOT_EXECUTABLE_FIXED_WEEKLY_LIST',**common.summary(chosen)})
    for arm,policy,k in sorted({(r['arm'],r['policy'],r['K'])for r in top_rows}):
        chosen=[r for r in top_rows if(r['arm'],r['policy'],r['K'])==(arm,policy,k)]
        top_summary.append({'arm':arm,'policy':policy,'week':'ALL','K':k,'timing_status':'UNVERIFIED_NOT_EXECUTABLE_FIXED_WEEKLY_LIST',**common.summary(chosen)})
    # Volume labels come from all-position provider totals, never supported RB sum.
    b,c,g,fr=base.sources();history=pd.concat([pd.read_parquet(io.BytesIO(base.pin(r)))for r in c['history_sources']],ignore_index=True)
    actual_total=history.groupby(['season','game_id','team']).team_stat_rush_att.first().to_dict()
    volumes={}
    for r in numeric:
        if r['arm']!='A2_DYNAMIC_ALLOCATION':continue
        key=(r['season'],r['game_id'],r['team']);law=r['law'];mu=law['shape']/law['rate'];y=actual_total.get(key)
        if key in volumes:
            if volumes[key]['mean']!=mu:raise ValueError('duplicate conflicting volume')
            continue
        volumes[key]={'season':r['season'],'week':r['week'],'game_id':r['game_id'],'team':r['team'],'mean':mu,'actual':float(y)if y is not None and pd.notna(y)else None,'missing_reason':None if y is not None and pd.notna(y)else'NO_QUALIFIED_ALL_POSITION_TEAM_TOTAL_FOR_THIS_GAME'}
    volume_summary=[]
    for year in [2025,2026]:
        rs=[r for r in volumes.values()if r['season']==year]
        for week in ['ALL']+sorted({r['week']for r in rs}):
            rr=[r for r in rs if week=='ALL'or r['week']==week];gg=[r for r in rr if r['actual']is not None];err=np.array([r['mean']-r['actual']for r in gg])
            volume_summary.append({'season':year,'week':week,'expected_team_games':len(rr),'scored_team_games':len(gg),'missing':len(rr)-len(gg),'MAE':float(np.abs(err).mean())if len(err)else None,'RMSE':float(np.sqrt(np.mean(err**2)))if len(err)else None,'bias':float(err.mean())if len(err)else None,'independence':'One shared volume forecast; not duplicated for A2/S0 or individual players.'})
    # Proper scores from full retained laws, no selected-row filtering.
    proper=[]
    for arm in sorted({r['arm']for r in rows}):
        rr=[r for r in rows if r['arm']==arm and r['policy']=='P2_EXACT_LAW'and r['p_over']is not None and r['appearance']=='PLAYED'and r['actual']is not None]
        if not rr:continue
        bs=[];logs=[]
        for r in rr:
            event='p_over'if r['actual']>r['line']else'p_under'if r['actual']<r['line']else'p_push';prob=r[event]
            bs.append(sum((r[p]-int(p==event))**2 for p in ['p_under','p_push','p_over']));logs.append(-math.log(prob)if prob>0 else math.inf)
        proper.append({'arm':arm,'n':len(rr),'three_state_Brier_sum':float(np.mean(bs)),'logloss':float(np.mean(logs))if all(math.isfinite(x)for x in logs)else None,'logloss_state':'FINITE'if all(math.isfinite(x)for x in logs)else'POSITIVE_INFINITY','binary_neutral_not_same_scale':True,'probability_ties_preserved':True})
    payload=base.archive({'TOPK_DIAGNOSTIC_MEMBERSHIP.json.gz':gzip.compress(base.enc(top_rows),mtime=0),'TEAM_VOLUME_FORECAST_ACTUALS.json.gz':gzip.compress(base.enc(list(volumes.values())),mtime=0)})
    if len(payload)>1048576:raise ValueError('analysis1MiBreservation')
    path=destination/'MATCHED_ANALYSIS_SCORECARD_V1.zip';store.write_bytes(path,payload);store.validate_reference(path,base.sha(payload));store.verify_retained_checkpoint()
    report={'analysis_id':'A-DYNAMIC-CARRY-MATCHED-ANALYSIS-v1','state':'EXECUTED','numeric_paired':pairs,'selection_paired':spairs,'source_strata':strata,'topK_diagnostics':top_summary,'volume_scores':volume_summary,'full_board_three_state_probability':proper,'private_manifest':{'artifact_id':'A-DYNAMIC-CARRY-MATCHED-ANALYSIS-V1','sha256':base.sha(payload),'bytes':len(payload),'readback':'PASS_APPROVED_STORE','offhost':'NOT_VERIFIED'},'resources':{'new_fits':0,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'limitations':['Exposed historical development, not original-issued or fresh prospective evidence.','TopK future-in-week inputs and quote simultaneity are unqualified; no90%validation or paperprofit claim.','No2025offered-line panel; historical numerical results remain separate.','All newAresults remain owner-local, not automatically C-admitted or live.']}
    (OUT/'MATCHED_ANALYSIS_RESULTS_V1.json').write_bytes(base.enc(report));print(json.dumps({'numeric_paired':len(pairs),'selection_paired':len(spairs),'source_strata':len(strata),'TopK_cells':len(top_summary),'volume_cells':len(volume_summary),'new_fits':0}))

if __name__=='__main__':main()
