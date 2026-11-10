import sys,io,json,gzip,zipfile,hashlib,time,resource
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,'/workspace/nfl-methods-integration')
import numpy as np,pandas as pd,pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
from nfl_lab import abc_player_rushing_context_v1 as author
from tools import abc_a_dynamic_carry_wave_v1 as base
from tools.category_topfive_matched12_storage_v1 import open_store,GO
R=Path('/workspace/nfl-methods-integration');start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(290,300));resource.setrlimit(resource.RLIMIT_AS,(3221225472,)*2)
s,_=open_store(R,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=GO,readonly=True)
b,c,g,fr=base.sources();h=pd.concat([pd.read_parquet(io.BytesIO(base.pin(x)))for x in c['history_sources']],ignore_index=True)
assert not h.duplicated(['game_id','player_id']).any()
for col in ['kickoff_utc','outcome_available_utc']:h[col]=pd.to_datetime(h[col],utc=True)
assert h[['kickoff_utc','outcome_available_utc']].notna().all().all();assert (h.outcome_available_utc==h.kickoff_utc+pd.Timedelta(days=7)).all()
clock={str(k):(v.kickoff_utc.iloc[0],v.outcome_available_utc.iloc[0])for k,v in h.groupby('game_id')}
hby={(str(r.game_id),str(r.player_id)):r for r in h.itertuples()}
d=base.doc('role-count-full-pbp2024-recovery-gate-network-v2.json');refs=[dict(path=str(Path(d['output'])/'FULL_PBP2024.parquet'),bytes=d['asset']['expected_bytes'],sha256=d['asset']['expected_sha256']),base.doc('category-topfive-matched12-current-label-execute-v1.json.gz')['pbp']]
frames=[]
for ref in refs:
 df=pd.read_parquet(io.BytesIO(base.pin(ref)),columns=author.COLS);df=df.loc[df.season_type.eq('REG')&((df.week<=7)|df.season.eq(2024))].copy()
 for col in ['posteam','defteam']:df[col]=df[col].replace({'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'})
 frames.append(df)
pbp=pd.concat(frames,ignore_index=True);assert not pbp.duplicated(['game_id','play_id']).any()
groups={'location':['left','middle','right','UNKNOWN'],'gap':['end','guard','tackle','UNKNOWN'],'down':['1','2','3','4','UNKNOWN'],'distance':['short','medium','long','UNKNOWN'],'field':['redzone','backedup','middle','UNKNOWN']};labels=[(k,v)for k,vs in groups.items()for v in vs];N=len(labels)
def vector(plays):
 out=np.zeros(N)
 for p in plays.itertuples():
  z={'location':'UNKNOWN'if pd.isna(p.run_location)else p.run_location,'gap':'UNKNOWN'if pd.isna(p.run_gap)else p.run_gap,'down':'UNKNOWN'if pd.isna(p.down)else str(int(p.down)),'distance':'UNKNOWN'if pd.isna(p.ydstogo)else'short'if p.ydstogo<=2 else'medium'if p.ydstogo<=6 else'long','field':'UNKNOWN'if pd.isna(p.yardline_100)else'redzone'if p.yardline_100<=20 else'backedup'if p.yardline_100>=80 else'middle'}
  for i,(group,value)in enumerate(labels):out[i]+=z[group]==value
 return out
def metric(plays):
 a=np.zeros(7)
 for p in plays.itertuples():
  assert pd.notna(p.rushing_yards)and np.isfinite(p.rushing_yards)and pd.notna(p.epa)and np.isfinite(p.epa)
  a+=np.array([p.rushing_yards,p.rushing_yards<=0,p.rushing_yards>=10,p.first_down_rush==1,p.epa>0,p.qb_kneel==1,p.qb_scramble==1])
 return a
entries=[];withheld=set();validgames=set()
for (game,team),plays in pbp.groupby(['game_id','posteam'],sort=False):
 if game not in clock:withheld.add(game);continue
 kick,av=clock[game];a=plays.loc[plays.rush_attempt.eq(1)&plays.two_point_attempt.eq(0)];o=plays.loc[plays.two_point_attempt.eq(0)&(plays.play_type.isin(['pass','run','qb_kneel','qb_spike'])|plays.rush_attempt.eq(1))]
 if not len(o):continue
 assert a.rusher_player_id.notna().all();opp=plays.defteam.dropna().unique();assert len(opp)==1
 rec=dict(game=str(game),team=str(team),opponent=str(opp[0]),kick=kick,av=av,n=len(a),op=len(o),mix=vector(a),met=metric(a),dr=np.array([a.down.eq(i).sum()for i in range(1,5)],float),do=np.array([o.down.eq(i).sum()for i in range(1,5)],float),loc=np.array([a.run_location.fillna('UNKNOWN').eq(x).sum()for x in groups['location']],float),players={})
 for player,pp in a.groupby('rusher_player_id'):
  rr=hby.get((str(game),str(player)));assert rr is None or str(rr.team)==str(team)
  rec['players'][str(player)]=dict(game=str(game),team=str(team),kick=kick,av=av,n=len(pp),mix=vector(pp),met=metric(pp),dr=np.array([pp.down.eq(i).sum()for i in range(1,5)],float),role=str(rr.position)if rr is not None else'UNKNOWN',parent=rec)
 entries.append(rec);validgames.add(str(game))
by={(r['game'],r['team']):r for r in entries}
zeros=0;unknowns=0
for r in h.itertuples():
 p=by.get((str(r.game_id),str(r.team)))
 if p is None:continue
 if r.participation_state=='unknown'and pd.isna(r.rush_att):unknowns+=1
 if str(r.player_id)not in p['players']and r.participation_state=='played'and pd.notna(r.rush_att)and r.rush_att==0:
  p['players'][str(r.player_id)]=dict(game=str(r.game_id),team=str(r.team),kick=p['kick'],av=p['av'],n=0,mix=np.zeros(N),met=np.zeros(7),dr=np.zeros(4),role=str(r.position),parent=p);zeros+=1
assert all(sum(p['n']for p in r['players'].values())==r['n']for r in entries)
players=defaultdict(list);teams=defaultdict(list);defenses=defaultdict(list);league=[]
def take(rs,cut,n):return sorted([r for r in rs if r['av']<cut],key=lambda r:(r['kick'],r['game']))[-n:]
for r in sorted(entries,key=lambda x:(x['kick'],x['game'],x['team'])):
 old=take(teams[r['team']],r['kick'],8);lg=take(league,r['kick'],512);n=sum(x['n']for x in old);op=sum(x['op']for x in old);ln=sum(x['n']for x in lg);lo=sum(x['op']for x in lg)
 league_met=sum((x['met']for x in lg),np.zeros(7))/ln if ln else np.array([4.,.4,.1,.25,.4,0.,0.])
 exp=(sum((x['met']for x in old),np.zeros(7))+40*league_met)/(n+40);rate=(n+40*(ln/lo if lo else .45))/(op+40)
 r['r_run']=r['n']-r['op']*rate;r['r_met']=r['met']-r['n']*exp
 dr=sum((x['dr']for x in old),np.zeros(4));do=sum((x['do']for x in old),np.zeros(4));r['r_down']=r['dr']-r['do']*(dr+10*rate)/(do+10)
 priorloc=(sum((x['loc']for x in lg),np.zeros(4))+1)/(ln+4);loc=sum((x['loc']for x in old),np.zeros(4));r['r_loc']=r['loc']-r['n']*(loc+10*priorloc)/(n+10)
 teams[r['team']].append(r);defenses[r['opponent']].append(r);league.append(r)
 for player,p in r['players'].items():players[player].append(p)
print('RAW_INDEPENDENT_AGGREGATION_READY',len(entries),flush=True)
def feature(player,team,opp,cut):
 pp=take(players[player],cut,4);tt=take(teams[team],cut,8);dd=take(defenses[opp],cut,8);ll=take(league,cut,512);rb=[p for t in ll for p in t['players'].values()if p['role']=='RB'];den=sum(p['n']for p in rb);prior=sum((p['mix']for p in rb),np.zeros(N))
 for name,vs in groups.items():
  ix=[i for i,(k,v)in enumerate(labels)if k==name];prior[ix]=(prior[ix]+1)/(den+len(vs))
 n=sum(p['n']for p in pp);mix=(sum((p['mix']for p in pp),np.zeros(N))+10*prior)/(n+10);f={'f_pcm_'+k+'_'+v:float(mix[i])for i,(k,v)in enumerate(labels)}
 f.update(f_pcm_games=len(pp),f_pcm_carries=n,f_pcm_age_days=(cut-max(p['kick']for p in pp)).total_seconds()/86400 if pp else np.nan)
 tn=sum(t['n']for t in tt);to=sum(t['op']for t in tt);f.update(f_pcm_team_run_rate=tn/to if to else np.nan,f_pcm_team_offensive_plays=to/len(tt)if tt else np.nan,f_pcm_team_carries=tn/len(tt)if tt else np.nan)
 m=sum((p['met']for p in pp),np.zeros(7))/n if n else np.full(7,np.nan)
 for name,val in zip(['f_pcm_player_ypc','f_pcm_nonpositive','f_pcm_explosive10','f_pcm_firstdown','f_pcm_epapos','f_pcm_kneel_fraction','f_pcm_scramble_fraction'],m):f[name]=float(val)
 tr=sum((t['dr']for t in tt),np.zeros(4));tot=sum((t['do']for t in tt),np.zeros(4));own=sum((p['dr']for p in pp),np.zeros(4));pt=sum((p['parent']['dr']for p in pp),np.zeros(4))
 for i in range(4):f['f_pcm_team_run_down'+str(i+1)]=tr[i]/tot[i]if tot[i]else np.nan;f['f_pcm_player_given_run_down'+str(i+1)]=own[i]/pt[i]if pt[i]else np.nan
 nd=sum(t['n']for t in dd);od=sum(t['op']for t in dd);res=sum((t['r_met']for t in dd),np.zeros(7))/(nd+40)
 f.update(f_pcm_opp_games=len(dd),f_pcm_opp_age_days=(cut-max(t['kick']for t in dd)).total_seconds()/86400 if dd else np.nan,f_pcm_opp_run_residual=sum(t['r_run']for t in dd)/(od+100))
 for name,val in zip(['f_pcm_opp_yards_residual','f_pcm_opp_nonpositive_residual','f_pcm_opp_explosive_residual','f_pcm_opp_firstdown_residual','f_pcm_opp_epapos_residual'],res):f[name]=float(val)
 downres=sum((t['r_down']for t in dd),np.zeros(4))/(sum((t['do']for t in dd),np.zeros(4))+30);locres=sum((t['r_loc']for t in dd),np.zeros(4))/(nd+40)
 for i in range(4):f['f_pcm_match_down'+str(i+1)]=f['f_pcm_down_'+str(i+1)]*downres[i]
 for i,name in enumerate(groups['location']):f['f_pcm_match_location_'+name]=f['f_pcm_location_'+name]*locres[i]
 return f,dict(player_slots=len(pp),team_slots=len(tt),defense_slots=len(dd),latest_prior=max((p['kick']for p in pp),default=None),latest_source=max((t['av']for t in pp+tt+dd+ll),default=None))
q=pd.read_parquet(io.BytesIO(base.pin(c['features'])));q=q.loc[q.position.eq('RB')].copy();q['cutoff_utc']=pd.to_datetime(q.cutoff_utc,utc=True);q=q.set_index(base.KEY,drop=False)
features=s.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-v1/CONTEXT_FEATURES.parquet';fb=features.read_bytes();assert hashlib.sha256(fb).hexdigest()=='d61b578e15515fbf600dacdfcf0b1c87c384917cd591857197c2e867816c97dc';table=pd.read_parquet(io.BytesIO(fb)).set_index(base.KEY)
score=s.forward_root/'research/PLAYER-CONTEXT-MATCHUP-01-A-completion-v4/GRADED_SCORECARD_V1.zip';raw=score.read_bytes();assert hashlib.sha256(raw).hexdigest()=='d2c980a3bc87093ffa38246b70a4faf4c3493c31e85753f826ede05b79f56343'
with zipfile.ZipFile(io.BytesIO(raw))as zz:sd=json.loads(zz.read('RELATIONAL_SCORECARD.json'))
g=next(x for x in sd['decision_groups']if x['arm']=='E0_A1_UNCHANGED'and x['policy']=='P2_EXACT_LAW');picks=[]
for src in ['ANNUAL_NAMED_NJ','SITE_RECORDED_DK_JURISDICTION_UNKNOWN']:
 for status in ['WIN','LOSS','UNKNOWN_PARTICIPATION']:
  candidates=[]
  for i,oi in enumerate(g['opportunities']):
   o=sd['offer_universe'][oi]
   if o['source_stream']==src and g['status'][i]==status:candidates.append((o['season'],o['week'],o['game_id'],o['player_id']))
  if candidates:picks.append((src+':'+status,sorted(candidates)[0]))
cold=q.loc[q.f_player_games_prior.eq(0)].sort_index();assert len(cold);picks.append(('COLD_QUERY',tuple(cold.iloc[0][k]for k in base.KEY)))
zero=[]
for k,r in q.iterrows():
 hh=hby.get((str(r.game_id),str(r.player_id)))
 if hh is not None and hh.participation_state=='played'and pd.notna(hh.rush_att)and hh.rush_att==0:zero.append(k)
if zero:picks.append(('KNOWN_ZERO_TARGET',sorted(zero)[0]))
checks=[];mismatches=[];maxdiff=0
for case,k in picks:
 r=q.loc[k];f,details=feature(str(r.player_id),str(r.team),str(r.opponent),r.cutoff_utc);saved=table.loc[k]
 for name,val in f.items():
  got=float(saved[name])
  if pd.isna(val)and pd.isna(got):continue
  diff=abs(float(val)-got);maxdiff=max(maxdiff,diff)
  if not np.isclose(val,got,rtol=0,atol=1e-12):mismatches.append(dict(case=case,field=name,difference=diff))
 checks.append(dict(case=case,key_sha256=hashlib.sha256(json.dumps(list(k),default=str).encode()).hexdigest(),fields=len(f),prior_player_slots=details['player_slots'],prior_team_slots=details['team_slots'],prior_defense_slots=details['defense_slots'],latest_prior_lt_cutoff=details['latest_prior']is None or details['latest_prior']<r.cutoff_utc,latest_source_lt_cutoff=details['latest_source']is None or details['latest_source']<r.cutoff_utc))
print(json.dumps(dict(state='PASS_INDEPENDENT_RAW_NFL_FEATURE_RECONSTRUCTION'if not mismatches else'FAIL',cases=checks,mismatches=mismatches,max_absolute_difference=maxdiff,unique_source_plays=len(pbp),independent_team_records=len(entries),withheld_source_games=len(withheld),observed_zero_appearances_added=zeros,unknown_history_rows_not_manufactured_aszeros=unknowns,source_hashes=[x['sha256']for x in refs],saved_feature_sha256=hashlib.sha256(fb).hexdigest(),CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,limits='Representativefeaturechecks only; no modeldeserialization/refit/forecastgeneration or independentNFLlabelqualification; no authenticatedhistoricavailability claim')))
