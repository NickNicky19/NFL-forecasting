"""Earlier-only observed backfield competition group, not injury/availability.

The exposure denominator is supported RB credited carries in each earlier
team-game, not independently certified complete team opportunities. Unknown and
played-missing carry records retain explicit missingness; they never become zero.
"""
import numpy as np
import pandas as pd

VERSION='category-topfive-backfield-v1-20261029'
KEYS=['season','week','game_id','player_id']
COLUMNS=[
 'f_backfield_supported_RB_carries_mean3',
 'f_backfield_other_RB_carries_mean3',
 'f_backfield_positive_RB_carriers_mean3',
 'f_backfield_supported_RB_HHI_mean3',
 'f_backfield_player_supported_share_mean3',
 'f_backfield_unknown_RB_rows_mean3',
 'f_backfield_played_missing_RB_rows_mean3',
 'f_backfield_games_n3',
 'f_backfield_latest_game_age_days']

def _utc_known(series):
    if series.isna().any() or any(pd.Timestamp(v).tzinfo is None for v in series):
        raise ValueError('unknown or naive clock is not assigned a timezone')
    return pd.to_datetime(series,utc=True,errors='raise')

def compile_history(history):
    if history.duplicated(['player_id','game_id']).any():raise ValueError('unique source player-games required')
    if not history.participation_state.isin(['played','DNP','unknown']).all():
        raise ValueError('unregistered participation state')
    h=history.copy()
    for c in ['kickoff_utc','outcome_available_utc']:
        h[c]=_utc_known(h[c])
    if not h.outcome_available_utc.gt(h.kickoff_utc).all():raise ValueError('source availability must follow game')
    if h[['team','game_id','player_id','position']].isna().any(axis=None):raise ValueError('historical identity context incomplete')
    h['rush_att']=pd.to_numeric(h.rush_att,errors='coerce')
    valid=h.participation_state.eq('played')&np.isfinite(h.rush_att)
    if (h.loc[valid,'rush_att'].lt(0)|(h.loc[valid,'rush_att']%1).ne(0)).any():raise ValueError('invalid count support')
    h['_good']=valid
    # Team-game timing must be consistent before the availability admission.
    grouped={}
    for (team,game),g in h.groupby(['team','game_id'],sort=False):
        if g.kickoff_utc.nunique()!=1 or g.outcome_available_utc.nunique()!=1:raise ValueError('team game clocks disagree')
        rb=g.loc[g.position.eq('RB')]
        known=rb.loc[rb._good,['player_id','rush_att']]
        vals=known.rush_att.to_numpy(float);total=float(vals.sum()) if len(vals) else np.nan
        shares=vals/total if np.isfinite(total) and total>0 else []
        rec={'kickoff':g.kickoff_utc.iloc[0], 'available':g.outcome_available_utc.iloc[0], 'game_id':str(game),
             'total':total,'positive':float((vals>0).sum()) if len(vals) else np.nan,
             'HHI':float(np.square(shares).sum()) if len(shares) else np.nan,
             'unknown':float(rb.participation_state.eq('unknown').sum()),
             'played_missing':float((rb.participation_state.eq('played')&~rb._good).sum()),
             'players':dict(zip(known.player_id.astype(str),vals))}
        grouped.setdefault(str(team),[]).append(rec)
    for records in grouped.values():records.sort(key=lambda x:(x['kickoff'],x['game_id']))
    return grouped

def merge_compiled(earlier,extra):
    result={}
    for team in set(earlier)|set(extra):
        rows=earlier.get(team,[])+extra.get(team,[])
        if len({r['game_id'] for r in rows})!=len(rows):raise ValueError('compiled historical partitions overlap')
        result[team]=sorted(rows,key=lambda r:(r['kickoff'],r['game_id']))
    return result

def augment_from_compiled(frame,grouped):
    if frame.duplicated(KEYS).any():raise ValueError('unique query player-games required')
    if set(COLUMNS)&set(frame):raise ValueError('new information must not overwrite existing features')
    q=frame.copy().reset_index(drop=True);limits=_utc_known(q.cutoff_utc)
    if limits.isna().any() or q[['team','player_id']].isna().any(axis=None):raise ValueError('query cutoff/identity required')
    out=np.full((len(q),len(COLUMNS)),np.nan);cache={};source_clocks=[]
    for i,(team,player) in enumerate(zip(q.team.astype(str),q.player_id.astype(str))):
        limit=limits.iloc[i];key=(team,limit.value)
        if key not in cache:cache[key]=[r for r in grouped.get(team,[]) if r['available']<limit and r['kickoff']<limit][-3:]
        old=cache[key];out[i,7]=len(old);source_clocks.append(max((r['available'] for r in old),default=pd.NaT))
        if not old:continue
        def mean(values):
            a=np.asarray(values,dtype=float);return float(a[np.isfinite(a)].mean()) if np.isfinite(a).any() else np.nan
        # Explicitly exclude the query player's own count from competitors.
        others=[sum(v for p,v in r['players'].items() if p!=player) if any(p!=player for p in r['players']) else np.nan for r in old]
        ownshares=[r['players'][player]/r['total'] if player in r['players'] and np.isfinite(r['total']) and r['total']>0 else np.nan for r in old]
        out[i,:7]=[mean([r['total'] for r in old]),mean(others),mean([r['positive'] for r in old]),mean([r['HHI'] for r in old]),mean(ownshares),mean([r['unknown'] for r in old]),mean([r['played_missing'] for r in old])]
        out[i,8]=(limit-old[-1]['kickoff']).total_seconds()/86400
    for j,name in enumerate(COLUMNS):q[name]=out[:,j]
    q['backfield_feature_max_available_utc']=pd.to_datetime(source_clocks,utc=True)
    original=pd.to_datetime(q.feature_max_source_available_utc,utc=True,errors='raise')
    q['feature_max_source_available_utc']=pd.to_datetime([max(a,b) if pd.notna(a) and pd.notna(b) else (a if pd.notna(a) else b) for a,b in zip(original,source_clocks)],utc=True)
    if (q.backfield_feature_max_available_utc.notna()&q.backfield_feature_max_available_utc.ge(limits)).any():raise ValueError('new feature source must be strictly earlier')
    return q

def augment(frame,history):
    return augment_from_compiled(frame,compile_history(history))

def check_fictional():
    h=pd.DataFrame([
      dict(player_id='p',game_id='a',team='T',position='RB',kickoff_utc='2020-01-01T00:00:00Z',outcome_available_utc='2020-01-02T00:00:00Z',participation_state='played',rush_att=10),
      dict(player_id='other',game_id='a',team='T',position='RB',kickoff_utc='2020-01-01T00:00:00Z',outcome_available_utc='2020-01-02T00:00:00Z',participation_state='played',rush_att=5),
      dict(player_id='unknown',game_id='a',team='T',position='RB',kickoff_utc='2020-01-01T00:00:00Z',outcome_available_utc='2020-01-02T00:00:00Z',participation_state='unknown',rush_att=99),
      dict(player_id='p',game_id='future',team='T',position='RB',kickoff_utc='2020-01-03T00:00:00Z',outcome_available_utc='2020-01-09T00:00:00Z',participation_state='played',rush_att=99)])
    q=pd.DataFrame([dict(season=2020,week=2,game_id='q',player_id='p',team='T',cutoff_utc='2020-01-05T00:00:00Z',feature_max_source_available_utc='2020-01-01T00:00:00Z',base=123)])
    x=augment(q,h)
    assert x[COLUMNS].iloc[0].tolist()==[15.,5.,2.,(10/15)**2+(5/15)**2,10/15,1.,0.,1.,4.]
    assert x.base.iloc[0]==123 and set(q).issubset(x)
    changed=h.copy();changed.loc[changed.player_id.eq('unknown'),'rush_att']=np.nan
    assert augment(q,changed)[COLUMNS].equals(x[COLUMNS])
    changed=h.copy();changed.loc[changed.game_id.eq('future'),'rush_att']=12345
    assert augment(q,changed)[COLUMNS].equals(x[COLUMNS])
    changed=q.copy();changed.cutoff_utc='2020-01-02T00:00:00Z'
    y=augment(changed,h);assert y.f_backfield_games_n3.iloc[0]==0 and y[COLUMNS[:7]].isna().all(axis=None)
    assert x.backfield_feature_max_available_utc.iloc[0]==pd.Timestamp('2020-01-02T00:00:00Z')
    assert x.feature_max_source_available_utc.iloc[0]==pd.Timestamp('2020-01-02T00:00:00Z')
    for bad in [None,'2020-01-02T00:00:00']:
        broken=h.copy();broken.loc[0,'outcome_available_utc']=bad
        try:augment(q,broken)
        except ValueError:pass
        else:raise AssertionError('unknown/naive source time admitted')
    return {'state':'PASS','fictional_checks':11,'NFL_observations':0}
