"""Read retained C-graded rows; source partitions and paired analysis, zero fits."""
from __future__ import annotations
import collections,gzip,hashlib,io,json,lzma,os,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'reports/abc-championship/player-context-matchup-01'
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
    for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[n]='1'
    import numpy as np
    from nfl_lab import cdf_engine
    from tools import category_topfive_matched12_storage_v1 as st,abc_a_dynamic_carry_wave_v1 as base
    s,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO,readonly=True)
    report=json.loads((OUT/'completion-v4/SCORING_RECEIPT_V1.json').read_bytes());root=s.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-completion-v4'
    raw=base.pin({'path':str(root/'GRADED_SCORECARD_V1.zip'),'bytes':report['bytes'],'sha256':report['sha256']})
    with zipfile.ZipFile(io.BytesIO(raw))as z:
        body=z.read('RELATIONAL_SCORECARD.json');mm=json.loads(z.read('MEMBER_MANIFEST.json'))['RELATIONAL_SCORECARD.json']
    assert len(body)==mm['bytes']and sha(body)==mm['sha256'];d=json.loads(body)
    rows=[]
    for g in d['decision_groups']:
        for i,j in enumerate(g['opportunities']):
            r={**d['offer_universe'][j],'arm':g['arm'],'policy':g['policy']}
            r.update({f:g[f][i]for f in ['selected_side','status','point','fallback','unavailability_reason','p_under','p_push','p_over']});rows.append(r)
    assert len(rows)==9082
    plan=json.loads((OUT/'completion-v4/PROTOCOL_V4.json').read_bytes())
    cache=Path('/tmp/abc-improvement-01/C/src')
    for ref in plan['C_bound_code']:assert sha((cache/Path(ref['path']).name).read_bytes())==ref['sha256']
    sys.path.insert(0,str(cache));import abc_championship_v2 as common
    forecasts=[]
    root3=s.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-runtime-v3'
    sourceplan=json.loads((OUT/'completion-v4/PROTOCOL_V4.json').read_bytes())
    for ref in sourceplan['retained_v3_forecasts']:
        forecasts+=json.loads(lzma.decompress(base.pin({'path':str(root3/ref['id']),**{k:ref[k]for k in ['bytes','sha256']}})))
    for name in ['FORECAST_P2.json.xz','FORECAST_P3.json.xz']:
        rr=json.loads((OUT/'completion-v4/EXECUTION_RECEIPT_V4.json').read_bytes());ref=next(x for x in rr['private_artifacts']if x['id']==name)
        forecasts+=json.loads(lzma.decompress(base.pin({'path':str(root/name),**{k:ref[k]for k in ['bytes','sha256']}})))
    old=s.forward_root/'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
    with zipfile.ZipFile(io.BytesIO(base.pin({'path':str(old/'FAILED_PARTIALS_V2.zip'),'bytes':4829248,'sha256':'91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208'})))as z:cached=json.loads(gzip.decompress(z.read('FORECAST_PARTIALS.json.gz')))
    for src,arm in [('A1_BACKFIELD_CDF_ROLE_INPUTS','E0_A1_UNCHANGED'),('A0_BACKFIELD_CDF','S_DIRECT_BACKFIELD_UNCHANGED')]:forecasts +=[dict(r,arm=arm)for r in cached if r['season']==2026 and r['arm']==src]
    a3=json.loads((ROOT/'reports/abc-championship/post-wave-5w-v1/A3_FORECAST_FREEZE_V1.json').read_bytes())
    a3rows=json.loads(gzip.decompress(base.pin({'path':str(old/'POST_WAVE_A3_FORECASTS_V1.json.gz'),'bytes':a3['bytes'],'sha256':a3['sha256']})))['forecasts']
    forecasts +=[dict(r,arm='S_STRUCTURED_A3_UNCHANGED')for r in a3rows if r['season']==2026]
    key=lambda r:(r['season'],r['week'],r['game_id'],r['player_id'])
    fmap={(r['arm'],key(r)):r for r in forecasts};actual={tuple(k):a for k,a in zip(d['numeric_keys'],d['numeric_actuals'])}
    assert len(forecasts)==len(fmap)==11196
    groups=collections.defaultdict(list)
    for r in rows:groups[(r['arm'],r['policy'])].append(r)
    headline=[];panels=[]
    for(ap,rs)in sorted(groups.items()):
        arm,policy=ap
        for panel,rr in [('ALL_MIXED_SOURCE_W1_7',rs),('ANNUAL_NJ_W1_5',[r for r in rs if r['source_stream']=='ANNUAL_NAMED_NJ']),('SITE_RECORDED_DK_W6_7',[r for r in rs if r['source_stream'].startswith('SITE_')])]:
            rec=dict(arm=arm,policy=policy,panel=panel,**common.summary(rr))
            rec['fallback_selected']=sum(r['fallback']is not None and r['selected_side']in['OVER','UNDER']for r in rr)
            rec['fallback_decided']=sum(r['fallback']is not None and r['status']in['WIN','LOSS']for r in rr)
            rec['actually_scored_weeks']=sorted({r['week']for r in rr if r['status']in['WIN','LOSS','PUSH']})
            rec['five_week_floor_met']=len(rec['actually_scored_weeks'])>=5
            rec['floor_is_not_admission']=True;panels.append(rec)
            primary=policy=='CONSTANT'if arm.startswith('ALWAYS_')else policy=='P2_EXACT_LAW'if arm.startswith(('E0_','E1_','S_'))else policy=='P1_OTHER_POINT'
            if primary and panel=='ALL_MIXED_SOURCE_W1_7':headline.append(rec)
    def paired(a,pa,b,pb):
        aa={r['opportunity_key']:r for r in groups[(a,pa)]};bb={r['opportunity_key']:r for r in groups[(b,pb)]}
        kk=sorted(k for k in aa.keys()&bb.keys()if aa[k]['status']in['WIN','LOSS']and bb[k]['status']in['WIN','LOSS'])
        diff=np.array([int(aa[k]['status']=='WIN')-int(bb[k]['status']=='WIN')for k in kk]);bygame=collections.defaultdict(list);byweek=collections.defaultdict(list)
        for k,x in zip(kk,diff):bygame[aa[k]['game_id']].append(int(x));byweek[(aa[k]['season'],aa[k]['week'])].append(int(x))
        intervals={}
        for name,clusters in [('game',bygame),('season_week',byweek)]:
            totals=np.array([[sum(v),len(v)]for v in clusters.values()]);rng=np.random.default_rng(1701)
            boot=totals[rng.integers(len(totals),size=(500,len(totals)))].sum(axis=1);rates=boot[:,0]/boot[:,1]
            intervals[name]=dict(clusters=len(totals),low=float(np.quantile(rates,.025)),high=float(np.quantile(rates,.975)))
        return dict(candidate=a,candidate_policy=pa,control=b,control_policy=pb,paired_decided=len(kk),
          candidate_wins=sum(aa[k]['status']=='WIN'for k in kk),control_wins=sum(bb[k]['status']=='WIN'for k in kk),
          win_difference=int(diff.sum()),rate_difference=float(diff.mean()),disagreements=int((diff!=0).sum()),
          candidate_only_correct=int((diff>0).sum()),control_only_correct=int((diff<0).sum()),
          uncertainty=intervals,bootstrap_replicates=500,exposed_unadjusted=True)
    pairs=[paired('E1_OWN_CONTEXT','P2_EXACT_LAW','E0_A1_UNCHANGED','P2_EXACT_LAW'),
      paired('P1_POOLED_RIDGE','P1_OTHER_POINT','R1_OWN_CONTEXT_RIDGE','P1_OTHER_POINT'),
      paired('R3_CONTEXT_INTERACTION_RIDGE','P1_OTHER_POINT','P1_POOLED_RIDGE','P1_OTHER_POINT'),
      paired('P2_PARTIAL_PLAYER_TEAM_RIDGE','P1_OTHER_POINT','P1_POOLED_RIDGE','P1_OTHER_POINT'),
      paired('P3_PLAYER_ONLY_8_WITH_P1_FALLBACK','P1_OTHER_POINT','P1_POOLED_RIDGE','P1_OTHER_POINT')]
    for rec in headline:
        if not rec['arm'].startswith('ALWAYS_'):
            controls=[paired(rec['arm'],rec['policy'],c,'CONSTANT')for c in ['ALWAYS_OVER','ALWAYS_UNDER']]
            strongest=max(controls,key=lambda r:r['control_wins']);rec['strongest_matched_constant']=strongest;pairs+=controls
    player_summaries=[];fallback_summaries=[]
    for arm in sorted({r['arm']for r in forecasts}):
        rs=[r for r in forecasts if r['arm']==arm];scored=[r for r in rs if actual[key(r)]['actual']is not None]
        perplayer=collections.defaultdict(list)
        for r in scored:perplayer[r['player_id']].append(abs(r['mean']-actual[key(r)]['actual']))
        player_summaries.append(dict(arm=arm,scored=len(scored),players=len(perplayer),opportunity_weighted_MAE=float(np.mean([x for v in perplayer.values()for x in v])),equal_player_MAE=float(np.mean([np.mean(v)for v in perplayer.values()])),
          support_player_counts={band:sum(lo<=len(v)<=hi for v in perplayer.values())for band,lo,hi in [('1_2',1,2),('3_4',3,4),('5_plus',5,100)]},
          per_player_details='RESTRICTED_REPRODUCIBLE_FROM_RETAINED_SCORECARD_AND_FROZEN_FORECASTS'))
        fallback_summaries.append(dict(arm=arm,query_rows=len(rs),fallback_queries=sum(r.get('fallback')is not None for r in rs),scored=len(scored),fallback_scored=sum(r.get('fallback')is not None for r in scored)))
    numericals=json.loads((OUT/'completion-v4/NUMERICAL_RESULTS_V1.json').read_bytes())['scores']
    def npair(a,b,product):
        rs=[r for r in forecasts if r['arm']==a and actual[key(r)]['actual']is not None];deltas=[];games=collections.defaultdict(list)
        for r in rs:
            y=actual[key(r)]['actual'];v=abs(r[product]-y)-abs(fmap[(b,key(r))][product]-y);deltas.append(v);games[r['game_id']].append(v)
        t=np.array([[sum(v),len(v)]for v in games.values()]);rng=np.random.default_rng(1701);z=t[rng.integers(len(t),size=(500,len(t)))].sum(axis=1)
        return dict(candidate=a,control=b,product=product,paired=len(rs),games=len(t),MAE_difference=float(np.mean(deltas)),game_bootstrap95=[float(x)for x in np.quantile(z[:,0]/z[:,1],[.025,.975])])
    summary=dict(state='EXECUTED_OWNER_LOCAL_C_SCORED_NOT_SHARED_ADMITTED',category='rush_att',role='RB',requested_period='2026W1-8',actual_weeks=list(range(1,8)),headline=headline,
      numerical_pairs=[npair('E1_OWN_CONTEXT','E0_A1_UNCHANGED',x)for x in ['mean','median']],
      five_week='Seven supported retrospectively scored season-weeks for full-board products; gate-specific counted separately. Duration alone not promotion.',
      learned_fallback=fallback_summaries,equal_player=player_summaries,
      limitations=['239recoverable original thresholds across81games; not every offeredNFLplayer.1244queries across107games,586supported numerical outcomes.',
        'AnnualNJW1-5 and site-labelledDKW6-7 retained as separate source partitions. Quote clocks/jurisdiction/venue settlement unverified; no authenticated pregame or ROIclaim.',
        '2025contextPBP missing; sourceage and partial role/context support limit transfer. All inspected periods exposed;500bootstrap sensitivity unadjusted for search/selection.',
        'No newQB/WR study or Cshared admission inferred. All12championship/historical tasks remain queued. No current-query capture or production switch.'])
    (OUT/'SUMMARY_V1.json').write_bytes(enc(summary));(OUT/'SOURCE_PANEL_RESULTS_V1.json').write_bytes(enc({'scores':panels}));(OUT/'PAIRED_COMPARISONS_V1.json').write_bytes(enc({'comparisons':pairs}))
    print(json.dumps({'headline':[(r['arm'],r['COMBINED']['wins'],r['COMBINED']['decided'])for r in headline],'numerical_pairs':summary['numerical_pairs'],'controlled_pairs':pairs[:5]}),flush=True)
if __name__=='__main__':main()
