"""Current-vintage NFLverse W1--7 labels on a previously frozen roster universe.

No action occurs on import. Root verifies owned source references and persists
returned labels/evidence through the existing managed store. Not a fit, forecast,
new scheduler, original pregame archive, sportsbook settlement or deployment.
"""
from __future__ import annotations
import hashlib,importlib.util,io,json,math,numbers,sys
from pathlib import Path
VERSION='matched12-current-nflverse-W1-W7-labels-v1'
ROOT=Path(__file__).resolve().parents[1]
KEY=['season','week','game_id','player_id']
MAP={'pass_yd':'passing_yards','pass_td':'passing_tds','pass_cmp':'completions','pass_att':'attempts','pass_int':'passing_interceptions','rush_yd':'rushing_yards','rush_att':'carries','rec':'receptions','rec_yd':'receiving_yards','rec_tgt':'targets'}
COUNT={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','rec_tgt','rush_td','rec_td'}
ALL=set(MAP)|{'rush_rec_yd','anytime_td','chart_ppr'}
META=['player_id','game_id','team','opponent_team','position','season','week','season_type']
ACTIVITY=['attempts','completions','carries','targets','receptions','passing_tds','rushing_tds','receiving_tds','passing_2pt_conversions','rushing_2pt_conversions','receiving_2pt_conversions','kickoff_returns','punt_returns']
PREDICATE=[('season','==',2026),('season_type','==','REG'),('week','>=',1),('week','<=',7)]
GENERATOR='0ccd41c78355ee89c08929c79e81dac75b4d3f7b22d691cddd4f7f875acfac28'


def require(ok,message):
 if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def team(x):return {'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV','WSH':'WAS'}.get(x,x)
def finite(x):return isinstance(x,numbers.Real) and not isinstance(x,bool) and math.isfinite(float(x))


def supported(stats,field,count=False):
 if field not in stats or stats[field] is None:return None,'MISSING_EXPLICIT_SOURCE_FIELD'
 x=stats[field]
 if not finite(x):return None,'UNKNOWN_OR_INVALID_SOURCE_VALUE'
 if count and (x<0 or int(x)!=x):return None,'INVALID_COUNT_SUPPORT'
 return float(x),'EXPLICIT_REPORTED_ZERO' if x==0 else 'EXPLICIT_REPORTED_VALUE'


def numeric(stats,target):
 if target in MAP:return supported(stats,MAP[target],target in COUNT)
 if target=='rush_rec_yd':
  r,rr=supported(stats,'rushing_yards');c,rc=supported(stats,'receiving_yards')
  return (r+c,'EXPLICIT_BOTH_SIGNED_COMPONENTS') if r is not None and c is not None else (None,'MISSING_COMBINED_COMPONENT:'+rr+':'+rc)
 if target=='anytime_td':
  r,rr=supported(stats,'rushing_tds',True);c,rc=supported(stats,'receiving_tds',True)
  if r is not None and r>0 or c is not None and c>0:return 1.,'EXPLICIT_RUSH_OR_RECEIVE_TD'
  if r==0 and c==0:return 0.,'BOTH_EXPLICIT_TD_COMPONENT_ZEROS'
  return None,'ATD_NEGATIVE_NOT_PROVED:'+rr+':'+rc
 return None,'EXACT_CHART_COMPONENT_PATH_REQUIRED'


def participation(stats,key,actors,scorers,old):
 state,witness=old.participation(stats,key in actors)
 if state=='played':return state,witness
 if state=='dnp':return state,witness
 if key in scorers:return 'played','QUALIFIED_NONDELETED_NONNULLIFIED_PBP_TD_SCORER'
 if any((v:=supported(stats,f)[0]) is not None and v!=0 for f in ['passing_yards','rushing_yards','receiving_yards']):return 'played','EXPLICIT_NONZERO_SIGNED_OFFICIAL_YARD_CREDIT'
 return 'unknown','NO_INDEPENDENT_PHYSICAL_PARTICIPATION_EVIDENCE'


def label(q,target,state,witness,value,reason,config):
 return {**{k:q[k] for k in KEY},'team':q['team'],'opponent':q['opponent'],'position':q['position'],'kickoff_utc':q['kickoff_utc'],
  'target':target,'actual':value if state=='played' else None,'participation_state':state,'participation_evidence':witness,
  'outcome_state':'known_dnp' if state=='dnp' else 'unknown_participation' if state!='played' else 'played_missing' if value is None else 'played_zero' if value==0 else 'played_nonzero',
  'label_reason':reason,'grading_version':VERSION,'source_sha256':config['weekly']['sha256'],'PBP_source_sha256':config['pbp']['sha256'],
  'source_version':'NFLVERSE_CURRENT_VINTAGE_CAPTURE_2026_10_31;EXPLICIT_WEEKLY_STATISTICS_AND_QUALIFIED_PBP',
  'evidence_tier':'CURRENT_VINTAGE_POSTGAME_LABEL_RECONSTRUCTION','historical_publication_utc':None,'venue_settlement':'UNQUALIFIED_STATISTICAL_LABEL_ONLY'}


def qualify(queries,weekly,pbp,roles,config,old,chart):
 """Pure scientific function; exact current source data only after root GO."""
 import pandas as pd
 require(set(roles)<=ALL and roles,'unsupported/unregistered target list')
 require(set(KEY+['team','opponent','position','kickoff_utc'])<=set(queries),'complete source-only roster queries required')
 require(not queries.duplicated(KEY).any(),'duplicate query identity')
 require(queries.season.eq(2026).all() and queries.week.between(1,7).all(),'queries outside fixed2026W1-7')
 require(not {'actual','prediction','absolute_error'}&set(queries),'outcome/forecast columns forbidden in query input')
 require(weekly.season.eq(2026).all() and weekly.week.between(1,7).all() and weekly.season_type.eq('REG').all(),'weekly source predicate violation')
 require(set(weekly.player_id)<=set(queries.player_id),'weekly source outside frozen query identities')
 # Original raw sources are immutable. Canonical franchise aliases affect joins
 # only and are explicitly versioned; no names/current-team guesses are used.
 import pyarrow as pa,pyarrow.compute as pc
 for c in ['posteam','defteam','td_team']:
  arr=pbp.column(c)
  for a,b in {'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV','WSH':'WAS'}.items():arr=pc.if_else(pc.equal(arr,a),pa.scalar(b,type=arr.type),arr)
  pbp=pbp.set_column(pbp.schema.get_field_index(c),c,arr)
 touchdowns,actors=old.pbp_inventory(pbp)
 grouped={}
 for row in weekly.to_dict('records'):
  k=(row['season'],row['week'],row['game_id'],row['player_id']);grouped.setdefault(k,[]).append(row)
 outputs=[];proofs=[];position_mismatch=0;weekly_missing=0;duplicate_queries=0;pending=0
 finals=set(config['qualified_final_game_ids'])
 zero_contract={'version':'nflverse-chart-broad-zero-v1','qualification_id':'generator-'+GENERATOR,'present_group_complete':True,
  'return_superset_contains_all_three_classes':True,'recovery_superset_includes_lateral_td_recipients':True}
 for q in queries.to_dict('records'):
  key=tuple(q[k] for k in KEY);members=grouped.get(key,[]);s=members[0] if len(members)==1 else {}
  witness_key=(q['game_id'],team(q['team']),q['player_id'])
  if q['game_id'] not in finals:
   state,witness='unknown','NO_QUALIFIED_FINAL_GAME_BINDING';pending+=1
  elif len(members)>1:
   state,witness='unknown','DUPLICATE_SOURCE_ROWS_UNRESOLVED';duplicate_queries+=1;s={}
  elif not members:
   state,witness=participation({},witness_key,actors,touchdowns,old);weekly_missing+=1
  elif team(s.get('team'))!=team(q['team']) or team(s.get('opponent_team'))!=team(q['opponent']):
   state,witness='unknown','CANONICAL_SOURCE_TEAM_OPPONENT_CONFLICT';s={}
  else:
   position_mismatch+=s.get('position')!=q['position']
   state,witness=participation(s,witness_key,actors,touchdowns,old)
  chart_value=None;chart_reason='CHART_NOT_REQUESTED';bundle=None
  if 'chart_ppr' in roles and q['position'] in roles['chart_ppr']:
   if s and state=='played':
    rare,diagnostics=old.rare_classification(s,touchdowns.get(witness_key,[]))
    for item in rare.values():item['qualification_id']=item['qualification_id'].replace('PBP2024-','MATCHED12_PBP2026_W1_W7_')
    bundle=chart.nflverse_components(s,source_ref={'sha256':config['weekly']['sha256'],'qualification_id':VERSION},broad_zero_contract=zero_contract,event_components=rare)
    identity={**{k:q[k] for k in KEY},'team':q['team'],'opponent':q['opponent'],'season_type':'REG'}
    observation=chart.label_observation(bundle,identity=identity,participation='played',participation_evidence=witness)
    chart_value=observation['value'];chart_reason='EXACT_CHART_'+observation['state']
    if chart_value is not None:require(abs(chart_value*50-round(chart_value*50))<=1e-8,'chart lattice violation')
    proofs.append({'key':identity,'missing_components':observation['missing_components'],'invalid_components':observation['invalid_components'],
     'rare_diagnostics':diagnostics,'components':observation['components'],'coverage':observation['coverage'],
     'rare_source_events':touchdowns.get(witness_key,[]) if diagnostics or finite(s.get('fumble_recovery_tds')) and s['fumble_recovery_tds']>0 or finite(s.get('special_teams_tds')) and s['special_teams_tds']>0 else []})
   else:chart_reason='CHART_SOURCE_OR_PLAYED_PROOF_UNAVAILABLE'
  for target,positions in roles.items():
   if q['position'] not in positions:continue
   value,reason=(chart_value,chart_reason) if target=='chart_ppr' else numeric(s,target)
   item=label(q,target,state,witness,value,reason,config)
   if witness=='NO_QUALIFIED_FINAL_GAME_BINDING':item['outcome_state']='pending'
   outputs.append(item)
 result=pd.DataFrame(outputs)
 require(not result.duplicated(KEY+['target']).any(),'duplicate qualified outcome keys')
 audit={'version':VERSION,'state':'NEW_CURRENT_SOURCE_LABELS_NOT_PREDICTIVE_SCORES','queries':len(queries),'query_games':int(queries.game_id.nunique()),
  'source_weekly_rows_after_predicate':len(weekly),'source_PBP_rows_after_predicate':len(pbp),'output_target_opportunities':len(result),
  'weekly_missing_query_rows':weekly_missing,'source_duplicate_query_rows':duplicate_queries,'unfinalized_query_rows':pending,
  'weekly_position_disagreements_retained_without_population_change':int(position_mismatch),
  'coverage':[dict(zip(['week','target','outcome_state','label_reason'],key),rows=int(n)) for key,n in result.groupby(['week','target','outcome_state','label_reason'],dropna=False).size().items()],
  'source_zeros':'Explicitweeklyfields only, after positivephysicalplayingproof; no absent-row or rosterstatus zero/DNP',
  'chart':'nick-chart-ppr-v1 exactsixteenprimitives; originalgeneratorbroadzero taxonomy; qualifiedPBPrareclasses, positiveunresolved staymissing',
  'source_vintage':'Current2026-10-31 release, notauthentic historicalpregame; applysameversiontoallarms; priorlabels unchanged',
  'fits_forecasts_scoring_HTTP':0,'weeks_admitted':[1,2,3,4,5,6,7],'protected_later_periods_admitted':False}
 return result,audit,proofs


def load_source(ref,name):
 from tools.category_topfive_matched12_offer_driver_v1 import read_exact
 read_exact(ref);spec=importlib.util.spec_from_file_location(name,ref['path']);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def materialize(config,go):
 require(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root','exactroot/independentsourcequalification GO required')
 require(go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('config_sha256')==sha(encoded(config)),'exact current-labelworker/config binding')
 from tools.category_topfive_matched12_offer_driver_v1 import read_exact
 for ref in config['source_pins'].values():read_exact(ref)
 # All required model/product freezes must be authenticated before raw labels.
 frozen=[]
 for spec in config['forecast_freezes']:
  doc=json.loads(read_exact(spec['reference']));require(doc.get('forecast_readback_verified') is True and doc.get('state')==spec['required_state'],'model forecasts not immutably frozen/read back');frozen.append(doc)
 if 'chart_ppr' in config['roles_by_target']:
  require(any(x.get('chart_target_contract')=='nick-chart-ppr-v1' for x in frozen),'exact chart forecast freeze required')
 sys.path.insert(0,str(ROOT));import nfl_lab
 require(Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab','root source package required')
 chart=load_source(config['source_pins']['chart_components'],'nfl_lab.next_checkpoint_chart_ppr');old=load_source(config['source_pins']['chart_label_helpers'],'matched12_current_chart_helpers')
 require(chart.SCORING_VERSION=='nick-chart-ppr-v1','wrong chart contract')
 require(sha(read_exact(config['generator_source']))==GENERATOR,'existing exact generator taxonomy proof required')
 import pandas as pd,pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 require(any(x.get('source_queries_sha256')==config['queries']['sha256'] for x in frozen),'frozen rosterquery binding required')
 qcols=KEY+['team','opponent','position','kickoff_utc','cutoff_utc']
 queries=pq.read_table(io.BytesIO(read_exact(config['queries'])),columns=qcols,use_threads=False).to_pandas(use_threads=False)
 require(len(queries)==4985 and queries.game_id.nunique()==107,'fixed original rosteruniverse changed')
 raw_weekly=read_exact(config['weekly']);raw_pbp=read_exact(config['pbp'])
 wf=pq.ParquetFile(io.BytesIO(raw_weekly));pf=pq.ParquetFile(io.BytesIO(raw_pbp))
 require(wf.metadata.num_rows<=10000 and pf.metadata.num_rows<=25000,'finite source row envelope')
 wcols=list(dict.fromkeys(META+list(MAP.values())+list(chart.NFL_FIELDS.values())+ACTIVITY+['fumble_recovery_tds','special_teams_tds']))
 pcols=list(dict.fromkeys(['season','week','season_type']+old.PBP_COLUMNS))
 require(set(wcols)<=set(wf.schema_arrow.names) and set(pcols)<=set(pf.schema_arrow.names),'source dictionary columns incomplete')
 predicate=PREDICATE
 # Arrow admission happens before Python values/pandas; never decode later
 # periods into semantic rows and discard them afterward.
 wt=pq.read_table(io.BytesIO(raw_weekly),columns=wcols,filters=predicate+[('player_id','in',queries.player_id.unique().tolist())],use_threads=False)
 pt=pq.read_table(io.BytesIO(raw_pbp),columns=pcols,filters=predicate+[('game_id','in',queries.game_id.unique().tolist())],use_threads=False)
 for table in [wt,pt]:
  require(set(table.column('season').to_pylist())=={2026} and set(table.column('season_type').to_pylist())=={'REG'} and set(table.column('week').to_pylist())<=set(range(1,8)),'protected period escapedArrowadmission')
 return qualify(queries,wt.to_pandas(use_threads=False),pt,config['roles_by_target'],config,old,chart)
