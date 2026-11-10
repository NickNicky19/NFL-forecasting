"""Fictional source-policy regression only; zero NFL observations or fits."""
import hashlib,json,pathlib,time,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np,pandas as pd
from nfl_lab import profile_freshness_a_v1 as t,player_context_completion_features_v1 as f
from nfl_lab.player_context_rush_efficiency_v1 import EfficiencyContext

def main():
    start=time.process_time();checks=[]
    h=pd.DataFrame([dict(season=2026,week=i,game_id='fictional-g'+str(i),player_id='fictional-p',team='T',opponent='O',position='RB',kickoff_utc=pd.Timestamp('2026-09-01',tz='UTC')+pd.Timedelta(days=7*(i-1)),outcome_available_utc=pd.Timestamp('2026-09-01',tz='UTC')+pd.Timedelta(days=7*i),participation_state='played',rush_att=1,rush_yd=y,rec=0,rec_yd=0,rec_tgt=0,is_home=True)for i,y in [(1,10),(2,30)]])
    q=pd.DataFrame([dict(season=2026,week=3,game_id='fictional-g3',player_id='fictional-p',team='T',opponent='O',position='RB',kickoff_utc=pd.Timestamp('2026-09-15',tz='UTC'),cutoff_utc=pd.Timestamp('2026-09-15',tz='UTC'),is_home=True,actual=999,rush_yd=999)])
    a,_=t.rebuild_queries(h,q,f,t.ORIGINAL);b,_=t.rebuild_queries(h,q,f,t.ALTERNATIVE)
    assert a.f_player_rush_yd_mean3.iloc[0]==10 and b.f_player_rush_yd_mean3.iloc[0]==20
    assert a.outcome_available_utc.isna().all() and b.outcome_available_utc.isna().all()
    assert 'rush_yd'not in a and 'actual'not in a
    checks.append('Strict7dayboundary versusregistered48h; no future query outcome required')
    anchor=pd.concat([q[t.KEY+t.CTX],q[t.KEY+t.CTX]],ignore_index=True)
    anchor.loc[1,'player_id']='fictional-other'
    profile=anchor.copy();profile['f_profile_value']=[0.,np.nan]
    aligned=t.align_cached_queries(anchor,profile.iloc[::-1].reset_index(drop=True))
    assert aligned[t.KEY].equals(anchor[t.KEY]) and aligned.f_profile_value.iloc[0]==0 and pd.isna(aligned.f_profile_value.iloc[1])
    for bad in [profile.iloc[:1],pd.concat([profile.iloc[:1],profile.iloc[:1]],ignore_index=True)]:
        try:t.align_cached_queries(anchor,bad)
        except ValueError:pass
        else:raise AssertionError('missing/duplicate cached profile accepted')
    conflict=profile.copy();conflict.loc[0,'team']='OTHER'
    try:t.align_cached_queries(anchor,conflict)
    except ValueError:pass
    else:raise AssertionError('historical-team conflict accepted')
    checks.append('KEY+CTX shuffled row alignment preserves exact zero/null; missing/duplicate/context conflict rejected')
    sameweek=h.iloc[[0]].copy();sameweek['week']=3;sameweek['game_id']='fictional-thursday';sameweek['kickoff_utc']=pd.Timestamp('2026-09-17',tz='UTC');sameweek['outcome_available_utc']=pd.Timestamp('2026-09-24',tz='UTC');sameweek['rush_yd']=13
    sunday=q.copy();sunday['week']=3;sunday['game_id']='fictional-sunday';sunday['team']='NEW';sunday['kickoff_utc']=pd.Timestamp('2026-09-20T17:00:00Z');sunday['cutoff_utc']=sunday.kickoff_utc
    oldsame,_=t.rebuild_queries(sameweek,sunday,f,t.ORIGINAL)
    newsame,_=t.rebuild_queries(sameweek,sunday,f,t.ALTERNATIVE)
    assert oldsame.f_player_games_prior.iloc[0]==0 and pd.isna(oldsame.f_player_rush_yd_mean3.iloc[0])
    assert newsame.f_player_games_prior.iloc[0]==1 and newsame.f_player_rush_yd_mean3.iloc[0]==13
    same7,_=t.retime_history(sameweek,t.ORIGINAL,declared_source_lane=t.ORIGINAL)
    same48,_=t.retime_history(sameweek,t.ALTERNATIVE,declared_source_lane=t.ORIGINAL)
    assert t.ordinary_age_records(same7,sunday)[0]['fields']['rush_yd_last3']['finite_values']==0
    assert t.ordinary_age_records(same48,sunday)[0]['fields']['rush_yd_last3']['finite_values']==1
    checks.append('Same-week Thursday-to-Sunday48h history admitted after teamchange: mean13/prior1;7day remainsNaN/prior0 and actual-consumed age agrees')
    other=h.copy();other['player_id']='fictional-control';other['game_id']=['fictional-other1','fictional-other2'];other['team']='OTHER';other['rush_yd']=[1000,2000]
    multi=pd.concat([h,other],ignore_index=True)
    full,_=t.rebuild_queries(multi,q,f,t.ALTERNATIVE)
    projected,_=t.rebuild_queries(multi,q,f,t.ALTERNATIVE,own_source_projection=True,consumed_columns=t.BASE30)
    assert t.exact_columns(full,projected,t.BASE30)['state']=='PASS_EXACT_NUMERIC_AND_MISSINGNESS'
    try:t.rebuild_queries(multi,q,f,t.ALTERNATIVE,own_source_projection=True,consumed_columns=list(t.BASE30[:-1])+['f_team_rush_att_mean3'])
    except ValueError:pass
    else:raise AssertionError('non-own feature accepted for source projection')
    checks.append('Multiplayer full-versus-own-source projection exact on all30 consumed fields; non-own dependency rejects optimization')



    changed=q.copy();changed['rush_yd']=-10000;changed['actual']=-10000
    c,_=t.rebuild_queries(h,changed,f,t.ALTERNATIVE);assert c.filter(like='f_').equals(b.filter(like='f_'))
    future=h.iloc[[0]].copy();future['game_id']='fictional-future';future['week']=4;future['kickoff_utc']=pd.Timestamp('2026-09-22',tz='UTC');future['outcome_available_utc']=pd.Timestamp('2026-09-29',tz='UTC');future['rush_yd']=1e9
    c,_=t.rebuild_queries(pd.concat([h,future],ignore_index=True),q,f,t.ALTERNATIVE);assert c.filter(like='f_').equals(b.filter(like='f_'))
    checks.append('Future record and target-label mutation do not change earlier base features')
    u=h.copy();u.loc[0,'outcome_available_utc']=pd.NaT;u.loc[1,'outcome_available_utc']=u.loc[1,'kickoff_utc']+pd.Timedelta(days=5)
    u,ua=t.retime_history(u,t.ALTERNATIVE,declared_source_lane=t.ORIGINAL)
    assert pd.isna(u.outcome_available_utc.iloc[0])and u.outcome_available_utc.iloc[1]==u.kickoff_utc.iloc[1]+pd.Timedelta(days=5)
    t.require_policy_history(u,t.ALTERNATIVE)
    try:t.retime_history(u,t.ALTERNATIVE,declared_source_lane=t.ORIGINAL)
    except ValueError:pass
    else:raise AssertionError('double timing transform accepted')
    authentic=h.copy();authentic[t.CLOCK_KIND_FIELD]=["AUTHENTICATED_ORIGINAL_OBSERVATION",t.ORIGINAL]
    preserved,pa=t.retime_history(authentic,t.ALTERNATIVE,declared_source_lane=t.ORIGINAL)
    assert preserved.outcome_available_utc.iloc[0]==h.outcome_available_utc.iloc[0]
    assert preserved.outcome_available_utc.iloc[1]==h.kickoff_utc.iloc[1]+pd.Timedelta(hours=48)
    t.require_policy_history(preserved,t.ALTERNATIVE)
    assert pa['explicitly_authenticated_rows_preserved']==1
    checks.append('Unknown, nonproxy and authenticated-coincident+7 clocks preserved; double application rejected')
    plays=[]
    for i,y in [(1,10),(2,30)]:
        plays.append(dict(season=2026,season_type='REG',week=i,game_id='fictional-g'+str(i),play_id=1,posteam='T',defteam='O',rusher_player_id='fictional-p',rush_attempt=1,two_point_attempt=0,play_type='run',run_location='left',run_gap='guard',down=1,ydstogo=10,yardline_100=50,rushing_yards=y,epa=1.,first_down_rush=1,qb_kneel=0,qb_scramble=0))
    frames=[pd.DataFrame(plays)]
    h7,_=t.retime_history(h,t.ORIGINAL,declared_source_lane=t.ORIGINAL)
    h48,_=t.retime_history(h,t.ALTERNATIVE,declared_source_lane=t.ORIGINAL)
    old=EfficiencyContext(frames,h);s7=t.TimingEfficiencyContext(frames,h7,t.ORIGINAL);s48=t.TimingEfficiencyContext(frames,h48,t.ALTERNATIVE)
    oldv,oldc,_=old.profile('fictional-p','T','O',q.cutoff_utc.iloc[0],8,True)
    v7,c7,_=s7.profile('fictional-p','T','O',q.cutoff_utc.iloc[0],8,True)
    v48,c48,d48=s48.profile('fictional-p','T','O',q.cutoff_utc.iloc[0],8,True)
    assert oldv==v7 and oldc==c7
    assert v7['f_pce_own_games']==1 and v48['f_pce_own_games']==2
    assert d48['source_policy']==t.ALTERNATIVE and d48['authenticated_source_observation']is False
    assert s7.teams['T'][1]['residual'][0,1]!=s48.teams['T'][1]['residual'][0,1]
    checks.append('Old7day constructor/profile exact;48h updates source membership and internal earlier-opponent priors')
    futureplay=frames[0].iloc[[0]].copy();futureplay['game_id']='fictional-future';futureplay['week']=4;futureplay['rushing_yards']=1e9
    futureh=pd.concat([h,future],ignore_index=True);futureh,_=t.retime_history(futureh,t.ALTERNATIVE,declared_source_lane=t.ORIGINAL)
    futurectx=t.TimingEfficiencyContext([pd.concat([frames[0],futureplay],ignore_index=True)],futureh,t.ALTERNATIVE)
    vv,cc,_=futurectx.profile('fictional-p','T','O',q.cutoff_utc.iloc[0],8,True)
    assert vv==v48 and cc==c48
    unseen=s48.profile('unseen','T','O',q.cutoff_utc.iloc[0],8,True)[2]
    assert unseen['state']=='NO_ELIGIBLE_SOURCE_PLAYER_HISTORY'
    assert all(x['raw']is None for x in unseen['tendencies']if x['actor']=='own'and x['metric'].startswith('yards'))
    checks.append('Future contextual rows do not change earlier profiles; unseen history is prior/undefined, not observedzero')
    result=dict(state='PASS_FICTIONAL_SOURCE_POLICY_ONLY',NFL_observations=0,fits=0,model_loads=0,new_private_bytes=0,checks=checks,CPU_seconds=time.process_time()-start)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
