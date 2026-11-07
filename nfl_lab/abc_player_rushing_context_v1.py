"""A-owned earlier rushing context. Provider location is not a called concept.

No target-game context, participation, realized opportunities or outcomes are read
by augment. Availability admission precedes kickoff-ordered appearance lookback.
"""
from __future__ import annotations
import bisect
from collections import defaultdict
import numpy as np
import pandas as pd

VERSION='A::PCM01-rushing-context-v1'
GROUPS={'location':['left','middle','right','UNKNOWN'],
 'gap':['end','guard','tackle','UNKNOWN'],'down':['1','2','3','4','UNKNOWN'],
 'distance':['short','medium','long','UNKNOWN'],'field':['redzone','backedup','middle','UNKNOWN']}
LABELS=[(k,v)for k,vs in GROUPS.items()for v in vs]
N=len(LABELS)
OWN=['f_pcm_'+k+'_'+v for k,v in LABELS]+['f_pcm_games','f_pcm_carries','f_pcm_age_days',
 'f_pcm_team_run_rate','f_pcm_team_offensive_plays','f_pcm_team_carries',
 'f_pcm_player_ypc','f_pcm_nonpositive','f_pcm_explosive10','f_pcm_firstdown','f_pcm_epapos',
 'f_pcm_kneel_fraction','f_pcm_scramble_fraction']+[
 'f_pcm_team_run_down'+str(i)for i in range(1,5)]+[
 'f_pcm_player_given_run_down'+str(i)for i in range(1,5)]
DEF=['f_pcm_opp_games','f_pcm_opp_age_days','f_pcm_opp_run_residual',
 'f_pcm_opp_yards_residual','f_pcm_opp_nonpositive_residual','f_pcm_opp_explosive_residual',
 'f_pcm_opp_firstdown_residual','f_pcm_opp_epapos_residual']
INTER=['f_pcm_match_down'+str(i)for i in range(1,5)]+[
 'f_pcm_match_location_'+x for x in GROUPS['location']]
METRICS=['yards','nonpositive','explosive10','firstdown','epapos','kneel','scramble']
COLS=['season','season_type','week','game_id','play_id','posteam','defteam','rusher_player_id',
 'rush_attempt','rushing_yards','run_location','run_gap','down','ydstogo','yardline_100',
 'qb_kneel','qb_scramble','qb_spike','two_point_attempt','penalty','play_type','first_down_rush','epa','success']

def counts(df):
    out=np.zeros(N)
    if len(df):
        vals={'location':df.run_location.fillna('UNKNOWN'), 'gap':df.run_gap.fillna('UNKNOWN'),
          'down':df.down.map(lambda x:str(int(x))if pd.notna(x)and x in [1,2,3,4]else'UNKNOWN'),
          'distance':df.ydstogo.map(lambda x:'UNKNOWN'if pd.isna(x)else'short'if x<=2 else'medium'if x<=6 else'long'),
          'field':df.yardline_100.map(lambda x:'UNKNOWN'if pd.isna(x)else'redzone'if x<=20 else'backedup'if x>=80 else'middle')}
        out=np.array([int(vals[k].eq(v).sum())for k,v in LABELS],float)
        for k,vs in GROUPS.items():
            ix=[j for j,(kk,v)in enumerate(LABELS)if kk==k]
            if out[ix].sum()!=len(df):raise ValueError('unregistered context code: '+k)
    return out

def sums(df):
    if not len(df):return np.zeros(7)
    y=df.rushing_yards.to_numpy(float)
    if not np.isfinite(y).all():raise ValueError('missing credited rush yards')
    if not np.isfinite(pd.to_numeric(df.epa,errors='coerce')).all():raise ValueError('missing/nonfinite credited-rush EPA denominator')
    for name in ['first_down_rush','qb_kneel','qb_scramble']:
        if not df[name].isin([0,1]).all():raise ValueError('unqualified binary metric: '+name)
    return np.array([y.sum(),(y<=0).sum(),(y>=10).sum(),df.first_down_rush.eq(1).sum(),
      df.epa.gt(0).sum(),df.qb_kneel.eq(1).sum(),df.qb_scramble.eq(1).sum()],float)

def eligible(records,cutoff,window):
    # Explicit unknown clock is never filled. Last games chosen by game time.
    return sorted((r for r in records if pd.notna(r['available'])and r['available']<cutoff),
                  key=lambda r:(r['kickoff'],r['game']))[-window:]

class Context:
    def __init__(self,frames,history):
        self.players=defaultdict(list);self.teams=defaultdict(list);self.defenses=defaultdict(list)
        self.league=[];self.source_games=[];self.component_rows=[];self._league_cache={};self.withheld_future_source_games=set()
        if history.duplicated(['game_id','player_id']).any() or history[['game_id','player_id','team']].isna().any(axis=None):
            raise ValueError('missing or duplicate canonical historical identity')
        for _,gg in history.groupby('game_id',sort=False):
            for name in ['kickoff_utc','outcome_available_utc']:
                values=pd.to_datetime(gg[name],utc=True,errors='coerce')
                if values.isna().any()or values.nunique()!=1:raise ValueError('conflicting or explicitly unknown context clock: '+name)
            if pd.to_datetime(gg.outcome_available_utc,utc=True).iloc[0]!=pd.to_datetime(gg.kickoff_utc,utc=True).iloc[0]+pd.Timedelta(days=7):
                raise ValueError('history does not match declared reconstructed seven-day source policy')
        clocks=history.groupby('game_id').agg(kickoff=('kickoff_utc','first'),available=('outcome_available_utc','first'))
        clocks['kickoff']=pd.to_datetime(clocks.kickoff,utc=True,errors='raise')
        clocks['available']=pd.to_datetime(clocks.available,utc=True,errors='coerce')
        hmap={(str(r.game_id),str(r.player_id)):r for r in history.itertuples()}
        entries=[];seen=set()
        for frame in frames:
            frame=frame.copy()
            # Existing nfl_lab.data._team canonical identity policy; exact alias,
            # never name fuzzing or today's roster for a historical game.
            for name in ['posteam','defteam']:
                frame[name]=frame[name].replace({'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'})
            if not frame.season_type.eq('REG').all()or frame[['game_id','play_id']].isna().any(axis=None):raise ValueError('REG identity boundary')
            keys=list(zip(frame.game_id.astype(str),frame.play_id.astype(str)))
            if len(set(keys))!=len(keys)or seen.intersection(keys):raise ValueError('duplicate source play including non-carry denominator')
            seen.update(keys)
            for name,lo,hi in [('down',1,4),('ydstogo',0,100),('yardline_100',0,100)]:
                vv=pd.to_numeric(frame[name],errors='coerce');known=frame[name].notna()
                if (known&(~np.isfinite(vv)|~vv.between(lo,hi))).any():raise ValueError('invalid observed context support: '+name)
            for (game,team),g in frame.groupby(['game_id','posteam'],sort=False):
                if pd.isna(team):continue
                if game not in clocks.index:
                    # W7 target rows need no known-outcome clock. Their PBP is
                    # deliberately outside the retained W1-6 history admission.
                    if g.season.eq(2026).all()and g.week.eq(7).all():
                        self.withheld_future_source_games.add(str(game));continue
                    raise ValueError('source game missing declared history identity')
                clock=clocks.loc[game]
                if pd.isna(clock.available)or clock.available<=clock.kickoff:raise ValueError('invalid retained history clock')
                a=g.loc[g.rush_attempt.eq(1)&g.two_point_attempt.eq(0)]
                o=g.loc[g.two_point_attempt.eq(0)&(g.play_type.isin(['pass','run','qb_kneel','qb_spike'])|g.rush_attempt.eq(1))]
                if o.empty:continue
                defender=g.defteam.dropna().unique()
                if len(defender)!=1:raise ValueError('ambiguous historical defense')
                # No-play/nullifier and penalties follow official credited flag, not convenience filtering.
                r=dict(game=str(game),team=str(team),opponent=str(defender[0]),kickoff=clock.kickoff,
                  available=clock.available,season=int(g.season.iloc[0]),week=int(g.week.iloc[0]),
                  attempts=len(a),offensive=len(o),mix=counts(a),metrics=sums(a),
                  down_runs=np.array([a.down.eq(i).sum()for i in range(1,5)],float),
                  down_opps=np.array([o.down.eq(i).sum()for i in range(1,5)],float),
                  location_runs=np.array([a.run_location.fillna('UNKNOWN').eq(x).sum()for x in GROUPS['location']],float))
                playercounts=a.groupby('rusher_player_id',dropna=False).size().to_dict()
                r['players']={}
                for player,ap in a.groupby('rusher_player_id',dropna=False):
                    if pd.isna(player):raise ValueError('unknown rusher bucket must be explicitly supported')
                    h=hmap.get((str(game),str(player)))
                    if h is not None and str(h.team)!=str(team):raise ValueError('historical player-team identity mismatch')
                    role=str(h.position)if h is not None else'UNKNOWN'
                    pr={**{k:r[k]for k in ['game','team','opponent','kickoff','available','season','week']},
                      'attempts':len(ap),'mix':counts(ap),'metrics':sums(ap),'role':role,
                      'down_runs':np.array([ap.down.eq(i).sum()for i in range(1,5)],float),'team_record':r}
                    r['players'][str(player)]=pr
                if sum(x['attempts']for x in r['players'].values())!=r['attempts']:raise ValueError('nonconserving credited source')
                entries.append(r)
        # Add supported played-zero appearances; never manufacture unknown/DNP zeros.
        bygame={(r['game'],r['team']):r for r in entries}
        for h in history.itertuples():
            r=bygame.get((str(h.game_id),str(h.team)))
            if r is None or str(h.player_id)in r['players']or h.participation_state!='played' or pd.isna(h.rush_att)or h.rush_att!=0:continue
            r['players'][str(h.player_id)]={**{k:r[k]for k in ['game','team','opponent','kickoff','available','season','week']},
              'attempts':0,'mix':np.zeros(N),'metrics':np.zeros(7),'role':str(h.position),'down_runs':np.zeros(4),'team_record':r}
        for r in sorted(entries,key=lambda x:(x['kickoff'],x['game'],x['team'])):
            old=eligible(self.teams[r['team']],r['kickoff'],8)
            # Historical opponent residual is relative to that offense's EARLIER history.
            n=sum(x['attempts']for x in old);op=sum(x['offensive']for x in old)
            league=eligible(self.league,r['kickoff'],512)
            ln=sum(x['attempts']for x in league);lop=sum(x['offensive']for x in league)
            lmetric=sum((x['metrics']for x in league),np.zeros(7))/ln if ln else np.array([4.,.4,.1,.25,.4,0.,0.])
            lm=sum((x['metrics']for x in old),np.zeros(7))
            expected=(lm+40*lmetric)/(n+40)
            rate=(n+40*((ln/lop)if lop else .45))/(op+40)
            r['run_residual']=r['attempts']-r['offensive']*rate
            r['metric_residual']=r['metrics']-r['attempts']*expected
            do=sum((x['down_opps']for x in old),np.zeros(4));dr=sum((x['down_runs']for x in old),np.zeros(4))
            r['down_residual']=r['down_runs']-r['down_opps']*(dr+10*rate)/(do+10)
            loc=sum((x['location_runs']for x in old),np.zeros(4));priorloc=sum((x['location_runs']for x in league),np.zeros(4))
            priorloc=(priorloc+1)/(ln+4)
            r['location_residual']=r['location_runs']-r['attempts']*(loc+10*priorloc)/(n+10)
            self.teams[r['team']].append(r);self.defenses[r['opponent']].append(r);self.league.append(r)
            self.source_games.append(r)
            for player,p in r['players'].items():self.players[player].append(p)

    def features(self,player,team,opponent,cutoff,window=8):
        pr=eligible(self.players.get(str(player),[]),cutoff,window)
        tr=eligible(self.teams.get(str(team),[]),cutoff,8)
        dr=eligible(self.defenses.get(str(opponent),[]),cutoff,8)
        if cutoff not in self._league_cache:
            league=eligible(self.league,cutoff,512)
            # A role-only prior; no future labels, opponent identity or participation.
            rb=[p for r in league for p in r['players'].values()if p['role']=='RB']
            denom=sum(p['attempts']for p in rb)
            prior=sum((p['mix']for p in rb),np.zeros(N))
            for group,values in GROUPS.items():
                ix=[j for j,(k,v)in enumerate(LABELS)if k==group]
                prior[ix]=(prior[ix]+1)/(denom+len(values))
            self._league_cache[cutoff]=(prior,max((r['available']for r in league),default=pd.NaT))
        prior,league_clock=self._league_cache[cutoff]
        num=sum(p['attempts']for p in pr);mi=sum((p['mix']for p in pr),np.zeros(N))
        mix=(mi+10*prior)/(num+10)
        f=dict(zip(OWN[:N],mix));f.update(f_pcm_games=len(pr),f_pcm_carries=num,
          f_pcm_age_days=(cutoff-max(p['kickoff']for p in pr)).total_seconds()/86400 if pr else np.nan)
        nt=sum(r['attempts']for r in tr);ot=sum(r['offensive']for r in tr)
        f.update(f_pcm_team_run_rate=nt/ot if ot else np.nan,
          f_pcm_team_offensive_plays=ot/len(tr)if tr else np.nan,f_pcm_team_carries=nt/len(tr)if tr else np.nan)
        met=sum((p['metrics']for p in pr),np.zeros(7))/num if num else np.full(7,np.nan)
        for name,value in zip(['f_pcm_player_ypc','f_pcm_nonpositive','f_pcm_explosive10','f_pcm_firstdown','f_pcm_epapos','f_pcm_kneel_fraction','f_pcm_scramble_fraction'],met):f[name]=float(value)
        downruns=sum((r['down_runs']for r in tr),np.zeros(4));downopps=sum((r['down_opps']for r in tr),np.zeros(4))
        ownruns=sum((p['down_runs']for p in pr),np.zeros(4));ownteam=sum((p['team_record']['down_runs']for p in pr),np.zeros(4))
        for j in range(4):
            f['f_pcm_team_run_down'+str(j+1)]=float(downruns[j]/downopps[j])if downopps[j]else np.nan
            f['f_pcm_player_given_run_down'+str(j+1)]=float(ownruns[j]/ownteam[j])if ownteam[j]else np.nan
        nd=sum(r['attempts']for r in dr);od=sum(r['offensive']for r in dr)
        residual=sum((r['metric_residual']for r in dr),np.zeros(7))/(nd+40)
        f.update(f_pcm_opp_games=len(dr),f_pcm_opp_age_days=(cutoff-max(r['kickoff']for r in dr)).total_seconds()/86400 if dr else np.nan,
          f_pcm_opp_run_residual=sum(r['run_residual']for r in dr)/(od+100),
          **dict(zip(DEF[3:],residual[:5])))
        downres=sum((r['down_residual']for r in dr),np.zeros(4))/(sum((r['down_opps']for r in dr),np.zeros(4))+30)
        locres=sum((r['location_residual']for r in dr),np.zeros(4))/(nd+40)
        for j in range(4):f[INTER[j]]=f['f_pcm_down_'+str(j+1)]*float(downres[j])
        for j,name in enumerate(GROUPS['location']):f[INTER[j+4]]=f['f_pcm_location_'+name]*float(locres[j])
        used=pr+tr+dr
        clock=max([r['available']for r in used]+([league_clock]if pd.notna(league_clock)else[]),default=pd.NaT)
        return f,clock

    def augment(self,frame,window=8):
        result=frame.copy();fs=[];clocks=[];cache={}
        for r in result.itertuples():
            cut=pd.to_datetime(r.cutoff_utc,utc=True)
            key=(str(r.player_id),str(r.team),str(r.opponent),cut)
            if key not in cache:cache[key]=self.features(*key,window=window)
            f,c=cache[key];fs.append(f);clocks.append(c)
        add=pd.DataFrame(fs,index=result.index)
        result=pd.concat([result,add],axis=1)
        old=pd.to_datetime(result.feature_max_source_available_utc,utc=True)
        new=pd.to_datetime(pd.Series(clocks,index=result.index),utc=True)
        result['feature_max_source_available_utc']=pd.concat([old,new],axis=1).max(axis=1)
        if (result.feature_max_source_available_utc>=pd.to_datetime(result.cutoff_utc,utc=True)).any():raise ValueError('context chronology')
        return result
