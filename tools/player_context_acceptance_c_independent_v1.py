import sys,types,pathlib,gzip,json,hashlib,math,collections
import numpy as np
import pandas as pd
ROOT=pathlib.Path('/tmp/acceptance-c-review')
stub=types.ModuleType('data_v2');stub.DAY=86400;sys.modules['data_v2']=stub
sys.path.insert(0,str(ROOT/'src'))
from context_features_c01 import Context,Prefix,OWN_NAMES

# Source-level synthetic boundary checks, not NFL observations.
c=Context.__new__(Context)
zero=dict(game_id='PAST',team='T',player_id='P',kickoff=0.,available=604800.,targets=0,attempts=40,team_complete=True,receptions_match=True)
c.players=Prefix([zero],'player_id');r=dict(player_id='P',team='T',opponent_team='D',kickoff=1209600.)
v=c.own(r)
assert v[0]==1 and v[1]==0 and v[2]==40 and np.isnan(v[5]) and np.isnan(v[6])
zero_result={'observed_source_output':dict(zip(OWN_NAMES[:7],map(lambda x:None if np.isnan(x) else float(x),v[:7]))),'mathematical_volume_ratios':[0.0,0.0],'interpretation':'DECLARED_COARSENING_NOT_DNP_OR_UNKNOWN_SOURCE'}
c.own=lambda _: np.array([1,1,40,14,0]+[0.]*7+[.75,.25,0,0,0]+[1,0,0,0,0])
d=dict(game_id='PAST',defense='D',kickoff=0.,available=604800.,passing_complete=True,targets=40,attempts=40,depth_n=np.array([20,20,0,0,0]),depth_residual=np.array([6,-6,0,0,0]),down_n=np.array([40,0,0,0,0]),down_residual=np.zeros(5),role_residual=0.)
c.defenses=Prefix([d],'defense');own,opp,inter=c.features(r)
assert abs(inter[0]-.05)<1e-15 and opp[4]==0
interaction={'depth_mix':[.75,.25,0,0,0],'depth_residual':[6,-6,0,0,0],'depth_counts':[20,20,0,0,0],'shrinkage':40,'depth_interaction':float(inter[0]),'aggregate_residual':float(opp[4]),'collapse_to_identical_scalar':False}

# Independent PBP-to-feature reconstruction: only ordinary retained PBP, schedule,
# and bound denominator qualification audit; no owner feature builder invocation.
frames=[pd.read_csv(ROOT/f'sources/player-context-matchup-01/pbp_facts_{y}.csv.xz') for y in [2025,2026]]
pbp=pd.concat(frames,ignore_index=True)
assert not pbp.duplicated(['game_id','play_id']).any()
valid=pbp[(pbp.pass_attempt==1)&(pbp.sack!=1)&(pbp.two_point_attempt!=1)&(pbp.play_deleted!=1)&(pbp.play_type!='no_play')].copy()
g=pd.read_csv(ROOT/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources/schedule.csv')
g['clock']=pd.to_datetime(g.gameday+' '+g.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC')
schedule=g.set_index('game_id').to_dict('index')
qualification={(x['game_id'],x['team']):x['qualified'] for x in json.loads((ROOT/'DENOMINATOR_AUDIT.json').read_text())['team_games']}
features=json.loads(gzip.decompress((ROOT/'artifacts/player-context-matchup-01/v1.1/FEATURE_EXPORT.json.gz').read_bytes()))
offers=json.loads(gzip.decompress((ROOT/'artifacts/player-context-matchup-01/v1.1/EXACT_OFFER_ROWS.json.gz').read_bytes()))
results=[]
for status in ['WIN','LOSS']:
 choices=sorted([x for x in offers if x['method']=='P2' and x['position'] in ['WR','TE'] and x['status']==status],key=lambda x:(x['game_id'],x['player_id']))
 for q in choices:
  f=next(x for x in features if x['game_id']==q['game_id'] and x['player_id']==q['player_id'])
  if f['own'][0]!=8 or f['own'][1]<=0:continue
  cut=pd.Timestamp(f['kickoff_UTC']);hist=valid[valid.receiver_player_id==q['player_id']]
  games=[(k,z) for k,z in hist.groupby('game_id') if k in schedule and schedule[k]['clock']+pd.Timedelta(days=7)<cut]
  games=sorted(games,key=lambda z:(schedule[z[0]]['clock'],z[0]))[-8:]
  games=[(k,z) for k,z in games if z.posteam.iloc[0]==f['team'] and qualification.get((k,f['team']))]
  if len(games)!=8:continue
  rows=pd.concat([z for _,z in games]);n=len(rows);a=sum(len(valid[(valid.game_id==k)&(valid.posteam==f['team'])]) for k,z in games)
  if n!=f['own'][1] or a!=f['own'][2]:continue
  depth=[sum(rows.air_yards<0),sum((rows.air_yards>=0)&(rows.air_yards<10)),sum((rows.air_yards>=10)&(rows.air_yards<20)),sum(rows.air_yards>=20),sum(rows.air_yards.isna())]
  down=[sum(rows.down==i) for i in [1,2,3,4]]+[sum(rows.down.isna())]
  comp=rows.complete_pass==1;knownyac=rows.loc[comp,'yards_after_catch']
  extra=[n/a,n/8,sum(comp)/n,float(rows.air_yards.mean()),float(knownyac.mean()),sum(rows.ydstogo<=3)/n,sum(rows.yardline_100<=20)/n]
  vec=np.array([8,n,a,(cut-schedule[games[-1][0]]['clock']).total_seconds()/86400,0]+extra+list(np.array(depth)/n)+list(np.array(down)/n))
  saved=np.asarray(f['own'],dtype=float); delta=float(np.nanmax(abs(vec-saved)));assert delta<1e-12
  results.append({'game_id':q['game_id'],'player_id':q['player_id'],'team':f['team'],'status':status,'retained_history_games':[k for k,z in games],'latest_game_UTC':schedule[games[-1][0]]['clock'].isoformat(),'source_policy':'CURRENT_REVISED_7DAY_RECONSTRUCTION','max_abs_delta':delta,'targets':n,'team_attempts':a,'limits':'Uses bound published official-count qualification; underlying >1MiB native facts not restored by GitHub connector. Known-zero history/final-label authenticity not independently certified.'});break
assert len(results)==2
out={'zero_context':zero_result,'interaction':interaction,'raw_positive_target_samples':results,'duplicate_raw_plays':0,'raw_rows':len(pbp),'no_new_fits':True,'no_models_loaded':True}
(ROOT/'INDEPENDENT_FEATURE_CHECKS.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
