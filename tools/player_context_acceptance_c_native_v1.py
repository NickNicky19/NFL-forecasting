import json,gzip,pathlib,math,collections,hashlib
import pandas as pd
import numpy as np
R=pathlib.Path('/tmp/acceptance-c-review')
source=R/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources'
facts=pd.read_csv(source/'facts.csv.gz');schedule=pd.read_csv(source/'schedule.csv')
schedule['clock']=pd.to_datetime(schedule.gameday+' '+schedule.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC');gs=schedule.set_index('game_id').to_dict('index')
physical=['attempts','carries','targets','receptions','sacks_suffered','passing_tds','rushing_tds','receiving_tds','passing_2pt_conversions','rushing_2pt_conversions','receiving_2pt_conversions','kickoff_returns','punt_returns','special_teams_tds']
facts['played']=(facts[physical].fillna(0)>0).any(axis=1)|(facts[['passing_yards','rushing_yards','receiving_yards']].fillna(0)!=0).any(axis=1)
native={(x['game_id'],x['player_id']):x for x in facts.to_dict('records')}
offers=json.loads(gzip.decompress((R/'artifacts/player-context-matchup-01/v1.1/EXACT_OFFER_ROWS.json.gz').read_bytes()))
known=[x for x in offers if x['method']=='P2' and x['position'] in ['WR','TE'] and x['actual'] is not None]
matches=0;issues=[]
for x in known:
 n=native.get((x['game_id'],x['player_id']));g=gs[x['game_id']]
 if n and n['played'] and math.isfinite(n['receptions']) and pd.notna(g['home_score']) and pd.notna(g['away_score']) and n['receptions']==x['actual']:matches+=1
 else:issues.append(hashlib.sha256((x['game_id']+'|'+x['player_id']).encode()).hexdigest())
pbp=pd.concat([pd.read_csv(R/f'sources/player-context-matchup-01/pbp_facts_{y}.csv.xz') for y in [2025,2026]],ignore_index=True)
valid=pbp[(pbp.pass_attempt==1)&(pbp.sack!=1)&(pbp.two_point_attempt!=1)&(pbp.play_deleted!=1)&(pbp.play_type!='no_play')]
audit=json.loads((R/'DENOMINATOR_AUDIT.json').read_text());qualified={(q['game_id'],q['team']):q['qualified'] for q in audit['team_games']}
raw=[]
for (gid,team),plays in valid.groupby(['game_id','posteam']):
 if gid not in gs:continue
 groupfacts=facts[(facts.game_id==gid)&(facts.team==team)]
 att=groupfacts.attempts.sum();cmp=groupfacts.completions.sum();targ=groupfacts.targets.sum();allfinite=groupfacts[['attempts','completions','targets']].notna().all().all()
 q=bool(allfinite and len(plays)==att and (plays.complete_pass==1).sum()==cmp and plays.receiver_player_id.notna().sum()==targ)
 if q != bool(qualified.get((gid,team),False)):raise AssertionError('QUALIFICATION_DISCREPANCY')
 observed=set()
 for pid,z in plays[plays.receiver_player_id.notna()].groupby('receiver_player_id'):
  observed.add(pid);n=native.get((gid,pid));matched=bool(n and n['played'] and n['receptions']==(z.complete_pass==1).sum())
  raw.append(dict(game_id=gid,player_id=pid,team=team,clock=gs[gid]['clock'],q=q,matched=matched,targets=len(z),attempts=len(plays)))
 for n in groupfacts[groupfacts.position.isin(['RB','WR','TE'])].to_dict('records'):
  if n['player_id'] not in observed and n['played'] and n['targets']==0 and n['receptions']==0:
   raw.append(dict(game_id=gid,player_id=n['player_id'],team=team,clock=gs[gid]['clock'],q=q,matched=True,targets=0,attempts=len(plays)))
features=json.loads(gzip.decompress((R/'artifacts/player-context-matchup-01/v1.1/FEATURE_EXPORT.json.gz').read_bytes()))
zero=[]
for f in sorted(features,key=lambda x:(x['origin'],x['game_id'],x['player_id'])):
 if not(f['own'][0]>0 and f['own'][1]==0 and f['own'][2]>0):continue
 cut=pd.Timestamp(f['kickoff_UTC']);rs=sorted([x for x in raw if x['player_id']==f['player_id'] and x['clock']+pd.Timedelta(days=7)<cut],key=lambda x:(x['clock'],x['game_id']))[-8:]
 rs=[x for x in rs if x['team']==f['team'] and x['q'] and x['matched']]
 actual=[len(rs),sum(x['targets'] for x in rs),sum(x['attempts'] for x in rs)]
 assert actual==f['own'][:3]
 zero.append({'case_SHA256':hashlib.sha256((f['game_id']+'|'+f['player_id']).encode()).hexdigest(),'raw_known_zero_games':len(rs),'targets':actual[1],'qualified_team_attempts':actual[2],'saved_derived_volume_ratios':f['own'][5:7],'mathematical_ratios':[0.0,0.0]})
 if len(zero)==2:break
out={'qualified_teamgame_flags_reconstructed':len(qualified),'qualification_discrepancies':0,'WRTE_P2_scored_actual_matches':matches,'scored_actual_checked':len(known),'actual_discrepancy_case_digests':issues,'known_zero_raw_reconstructions':zero,'limitations':'Current revised native source proves retained-source consistency, not authenticated historical availability or independent official-source truth.'}
(R/'INDEPENDENT_NATIVE_SEMANTICS.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
