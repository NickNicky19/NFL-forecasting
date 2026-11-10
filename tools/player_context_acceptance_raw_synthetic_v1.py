import sys,json,math,copy
from pathlib import Path
sys.path.insert(0,'/workspace/nfl-methods-integration')
import pandas as pd,numpy as np
from nfl_lab.abc_player_rushing_context_v1 import Context,OWN,DEF,INTER
from fractions import Fraction as F
rows=[];history=[]
for week,day,plays in [(1,'2024-09-01',[(1,'run','P1',-2,'left',0),(1,'pass',None,None,None,0),(2,'pass',None,None,None,0)]),(2,'2024-09-09',[(2,'run','P1',10,'right',1),(1,'run','P2',0,'middle',0),(2,'pass',None,None,None,0),(3,'pass',None,None,None,0)])]:
 game='SYN_'+str(week);kick=pd.Timestamp(day,tz='UTC')
 counts={p:0 for p in ['P1','P2','ZERO']}
 for i,(down,typ,player,y,loc,fd)in enumerate(plays):
  if player:counts[player]+=1
  rows.append(dict(season=2024,season_type='REG',week=week,game_id=game,play_id=i+1,posteam='AAA',defteam='BBB',rusher_player_id=player,rush_attempt=int(typ=='run'),rushing_yards=y,run_location=loc,run_gap=None,down=down,ydstogo=2,yardline_100=20,qb_kneel=0,qb_scramble=0,qb_spike=0,two_point_attempt=0,penalty=0,play_type=typ,first_down_rush=fd,epa=(1 if y and y>0 else -1),success=int(bool(y and y>0))))
 for p,n in counts.items():history.append(dict(season=2024,week=week,game_id=game,player_id=p,team='AAA',position='RB',kickoff_utc=kick,outcome_available_utc=kick+pd.Timedelta(days=7),participation_state='played',rush_att=n))
 history.append(dict(season=2024,week=week,game_id=game,player_id='UNKNOWN',team='AAA',position='RB',kickoff_utc=kick,outcome_available_utc=kick+pd.Timedelta(days=7),participation_state='unknown',rush_att=np.nan))
pbp=pd.DataFrame(rows);h=pd.DataFrame(history);cut=pd.Timestamp('2024-09-30',tz='UTC');c=Context([pbp],h);f,clock=c.features('P1','AAA','BBB',cut,4)
expected={'f_pcm_games':2,'f_pcm_carries':2,'f_pcm_team_run_rate':3/7,'f_pcm_team_run_down1':2/3,'f_pcm_team_run_down2':1/3,'f_pcm_player_given_run_down1':1/2,'f_pcm_player_given_run_down2':1,'f_pcm_player_ypc':4,'f_pcm_nonpositive':.5,'f_pcm_firstdown':.5,'f_pcm_epapos':.5,'f_pcm_explosive10':.5,'f_pcm_location_left':float(F(1,1)+10*F(2,7))/12,'f_pcm_location_middle':float(10*F(2,7))/12,'f_pcm_location_right':float(1+10*F(2,7))/12,'f_pcm_location_UNKNOWN':float(10*F(1,7))/12}
for k,v in expected.items():assert math.isclose(f[k],v,abs_tol=1e-12),(k,f[k],v)
# Zero is admitted only through explicit weekly played-zero, unknown not manufactured.
assert 'ZERO' in c.players and len(c.players['ZERO'])==2 and all(r['attempts']==0 for r in c.players['ZERO'])
assert 'UNKNOWN' not in c.players
locdef=[float(F(-7,44*43)),float(F(17,44*43)),float(F(17,44*43)),float(F(-27,44*43))]
for i,name in enumerate(['left','middle','right','UNKNOWN']):assert math.isclose(f['f_pcm_match_location_'+name],f['f_pcm_location_'+name]*locdef[i],abs_tol=1e-12)
assert max(locdef)-min(locdef)>0
# Adding future plays/history cannot affect prior feature, even after source values change.
future=pbp.copy();future['game_id']='SYN_FUTURE';future['week']=3;future['play_id']=np.arange(1,len(future)+1);future['rushing_yards']=999;fh=h.loc[h.week.eq(1)].copy();fh['game_id']='SYN_FUTURE';fh['week']=3;fh['kickoff_utc']=pd.Timestamp('2024-10-01',tz='UTC');fh['outcome_available_utc']=pd.Timestamp('2024-10-08',tz='UTC')
c2=Context([pd.concat([pbp,future],ignore_index=True)],pd.concat([h,fh],ignore_index=True));f2,_=c2.features('P1','AAA','BBB',cut,4)
for k in f:assert (pd.isna(f[k])and pd.isna(f2[k]))or f[k]==f2[k],k
failures={}
for name,pp,hh in [('duplicate_play',pd.concat([pbp,pbp.iloc[:1]],ignore_index=True),h),('unknown_availability',pbp,h.assign(outcome_available_utc=pd.NaT)),('missing_rush_EPA',pbp.assign(epa=np.nan),h)]:
 try:Context([pp],hh)
 except ValueError as e:failures[name]=str(e)
 else:raise AssertionError('gatefailed:'+name)
out={'state':'PASS_SYNTHETIC_RAW_SEMANTICS_ONLY_NOT_NFL_EVIDENCE','checked_quantities':len(expected),'denominators':{k:expected[k]for k in ['f_pcm_team_run_down1','f_pcm_player_given_run_down1','f_pcm_team_run_down2','f_pcm_player_given_run_down2']},'known_zero_retained':True,'unknown_not_zero':True,'future_raw_records_mutation_invariant':True,'gates':failures,'location_defense_residuals':locdef,'player_location_mix':[f['f_pcm_location_'+x]for x in ['left','middle','right','UNKNOWN']],'interaction_products':[f['f_pcm_match_location_'+x]for x in ['left','middle','right','UNKNOWN']],'interactions_identical_scalar_collapse':False,'interpretation':'location response is offense-adjusted carry-location-share residual, not direction-conditioned yards/success; down response is run-rate residual not conditional efficiency'}
print(json.dumps(out))
