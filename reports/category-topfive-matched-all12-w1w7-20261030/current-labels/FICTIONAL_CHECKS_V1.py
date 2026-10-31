"""Synthetic source-qualification cases only; no NFL source rows are opened."""
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tools import category_topfive_matched12_current_labels_v1 as new
from tools import next_checkpoint_chart_ppr_labels as old
from nfl_lab import next_checkpoint_chart_ppr as chart

def run():
 n=[]
 def ok(name,condition):
  assert condition,name;n.append(name)
 def rejects(name,fn):
  try:fn()
  except ValueError:n.append(name)
  else:raise AssertionError(name)
 q=pd.DataFrame([dict(season=2026,week=7,game_id='FICT1',player_id='00-000000'+str(i),team='AAA',opponent='BBB',position=pos,kickoff_utc='2026-10-25T17:00:00Z') for i,pos in enumerate(['QB','RB','WR','TE'],1)])
 fields=set(new.MAP.values())|set(chart.NFL_FIELDS.values())|set(new.ACTIVITY)|{'fumble_recovery_tds','special_teams_tds'}
 rows=[]
 for r in q.to_dict('records'):
  s={k:0 for k in fields};s.update({k:r[k] for k in new.KEY+['team','position']});s['opponent_team']='BBB';s['season_type']='REG'
  if r['position']=='QB':s.update(attempts=1,passing_yards=-2)
  if r['position']=='RB':s['carries']=1
  if r['position']=='WR':s['targets']=1
  rows.append(s)
 weekly=pd.DataFrame(rows)
 schema=pa.schema([(k,pa.string() if k in ['game_id','posteam','defteam','td_team','td_player_id','play_type','fumble_recovery_1_player_id','fumble_recovery_2_player_id','passer_player_id','rusher_player_id','receiver_player_id'] else pa.float64()) for k in old.PBP_COLUMNS])
 empty=pa.Table.from_pylist([],schema=schema)
 cfg={'weekly':{'sha256':'a'*64},'pbp':{'sha256':'b'*64},'qualified_final_game_ids':['FICT1']}
 roles={t:['QB'] if t.startswith('pass_') else ['QB','RB','FB','WR','TE'] for t in new.ALL}
 def qualify(w=weekly,p=empty,c=cfg):return new.qualify(q,w,p,roles,c,old,chart)
 result,audit,proof=qualify()
 def row(target,pos,r=result):return r.loc[r.target.eq(target)&r.position.eq(pos)].iloc[0]
 ok('explicitplayedpassingTDzero',row('pass_td','QB').actual==0)
 ok('explicitplayedinterceptionzero',row('pass_int','QB').actual==0)
 ok('negativeofficialyardsretained',row('pass_yd','QB').actual==-2)
 ok('playedreceptionzerofrompositivetarget',row('rec','WR').actual==0)
 ok('playedtargetcountindependentproduct',row('rec_tgt','WR').actual==1)
 ok('zero-onlyrowdoesnotproveplayed',row('rec','TE').participation_state=='unknown' and pd.isna(row('rec','TE').actual))
 ok('chartnegativeexactcontract',row('chart_ppr','QB').actual==-.08)
 w=weekly.copy();w.loc[w.position.eq('WR'),'receptions']=None;r,_,_=qualify(w)
 ok('explicitunknownnotzero',pd.isna(row('rec','WR',r).actual) and row('rec','WR',r).outcome_state=='played_missing')
 w=weekly.copy();w.loc[w.position.eq('QB'),'passing_interceptions']=-1;r,_,_=qualify(w)
 ok('invalidcountnotgradedzero',pd.isna(row('pass_int','QB',r).actual))
 w=weekly.copy();w.loc[w.position.eq('QB'),'fumbles_lost_total']=1;r,_,_=qualify(w)
 ok('chartuniquefumbleminusone',abs(row('chart_ppr','QB',r).actual+1.08)<1e-12)
 w=weekly.copy();w.loc[w.position.eq('QB'),'passing_tds']=1;r,_,_=qualify(w)
 ok('passingTDnotATDevent',row('anytime_td','QB',r).actual==0)
 w=weekly.copy();w.loc[w.position.eq('QB'),'fumble_recovery_tds']=1;r,_,_=qualify(w)
 ok('unreconciledrarepositivechartmissing',pd.isna(row('chart_ppr','QB',r).actual))
 w=weekly.copy();w.loc[w.position.eq('QB'),'fumble_recovery_tds']=None;r,_,_=qualify(w)
 ok('nullablebroadcountnotfalse',pd.isna(row('chart_ppr','QB',r).actual))
 r,_,_=qualify(pd.concat([weekly,weekly.iloc[[0]]],ignore_index=True))
 ok('duplicatedsourcequarantinednotselected',row('pass_att','QB',r).participation_state=='unknown')
 event={k:None for k in old.PBP_COLUMNS};event.update(game_id='FICT1',play_id=1.,posteam='AAA',defteam='BBB',play_deleted=0.,play_type='pass',two_point_attempt=0.,touchdown=0.,passer_player_id='00-0000003')
 pbp=pa.Table.from_pylist([event],schema=schema)
 r,_,_=qualify(weekly.loc[weekly.position.ne('WR')],pbp)
 ok('PBPactorprovesplayednotmissingstat-zero',row('rec','WR',r).participation_state=='played' and pd.isna(row('rec','WR',r).actual))
 r,_,_=qualify(c={**cfg,'qualified_final_game_ids':[]})
 ok('unfinalizedoutcomespending',r.outcome_state.eq('pending').all())
 rejects('laterweeksemanticrowsrejected',lambda:qualify(weekly.assign(week=8)))
 table=pa.table({'season':[2026,2026],'season_type':['REG','REG'],'week':[7,8],'fictional_stat':[3,999]});buf=io.BytesIO();pq.write_table(table,buf)
 filtered=pq.read_table(io.BytesIO(buf.getvalue()),columns=table.column_names,filters=new.PREDICATE,use_threads=False)
 ok('ArrowpredicatebeforePythonoutcomes',filtered.column('week').to_pylist()==[7] and filtered.column('fictional_stat').to_pylist()==[3])
 rejects('noGOdoesnotopenanysource',lambda:new.materialize({},{}))
 ok('unchangedfullquerytargetpopulation',len(result)==len(qualify(weekly.assign(receptions=None))[0]))
 return {'state':'PASS_FICTIONAL_SOURCE_ONLY','checks':len(n),'cases':n,'actual_NFL_source_rows_decoded':0,'fits_forecasts_HTTP':0}
if __name__=='__main__':print(run())
