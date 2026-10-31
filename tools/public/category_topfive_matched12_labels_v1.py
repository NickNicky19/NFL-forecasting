"""Post-forecast-freeze label qualification; never model inputs or inference.

No NFL rows are decoded on import. Only root's exact GO can materialize sources.
Caller owns source authentication, immutable managed persistence and readback.
"""
from __future__ import annotations
import gzip,hashlib,io,json,math,numbers
from pathlib import Path
VERSION='matched12-current-vintage-labels-v1.1'
ROOT=Path(__file__).resolve().parents[1]
TARGETS=('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','chart_ppr','rec_tgt')
COUNTS={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','rec_tgt','rush_td','rec_td','gp','off_snp'}
KEY=['season','week','game_id','player_id','team','opponent']


def require(ok,message):
 if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def finite(x):return isinstance(x,numbers.Real) and not isinstance(x,bool) and math.isfinite(float(x))


def value(stats,key):
 """Explicit finite source fields only; absence is never a reported zero."""
 if not isinstance(stats,dict) or key not in stats:return None,'MISSING_EXPLICIT_SOURCE_FIELD'
 v=stats[key]
 presence=stats.get('_presence')
 if isinstance(presence,dict) and key in presence.get('invalid_fields',[]):return None,'SOURCE_MARKED_INVALID'
 if v is None or not finite(v):return None,'UNKNOWN_OR_INVALID_SOURCE_VALUE'
 if key in COUNTS and (v<0 or int(v)!=v):return None,'INVALID_NONNEGATIVE_INTEGER_SUPPORT'
 return float(v),'EXPLICIT_REPORTED_ZERO' if v==0 else 'EXPLICIT_REPORTED_VALUE'


def participation(entry):
 if not isinstance(entry,dict):return 'unknown','MISSING_SOURCE_ROW'
 stats=entry.get('stats');stats=stats if isinstance(stats,dict) else {}
 witnesses=[]
 for key in ['gp','off_snp']:
  if key in stats:
   v,reason=value(stats,key)
   if v is None:return 'unknown','INVALID_PARTICIPATION_'+key
   if v>0:witnesses.append(key)
 for key in ['pass_att','pass_cmp','pass_td','pass_int','rush_att','rec_tgt','rec','rush_td','rec_td','pass_yd','rush_yd','rec_yd']:
  v,_=value(stats,key)
  if v is not None and v!=0:witnesses.append('physical_'+key)
 dnp=entry.get('participation_status')=='dnp' and isinstance(entry.get('participation_source'),str) and bool(entry['participation_source'])
 if witnesses and dnp:return 'unknown','CONTRADICTORY_PLAYED_DNP_EVIDENCE'
 if witnesses:return 'played','EXPLICIT_POSITIVE_'+','.join(witnesses)
 if dnp:return 'dnp','ATTRIBUTED_EXPLICIT_DNP'
 return 'unknown','NO_POSITIVE_OR_ATTRIBUTED_DNP_EVIDENCE'


def numerical(stats,target):
 if target=='chart_ppr':return None,'CHART_REQUIRES_EXACT_SIXTEEN_COMPONENT_QUALIFICATION'
 if target=='rush_rec_yd':
  a,ra=value(stats,'rush_yd');b,rb=value(stats,'rec_yd')
  return (a+b,'EXPLICIT_BOTH_SIGNED_YARD_COMPONENTS') if a is not None and b is not None else (None,'MISSING_COMBINED_YARD_COMPONENT:'+ra+':'+rb)
 if target=='anytime_td':
  a,ra=value(stats,'rush_td');b,rb=value(stats,'rec_td')
  if a is not None and a>0 or b is not None and b>0:return 1.,'EXPLICIT_RUSH_OR_RECEIVE_TD_CREDIT'
  if a==0 and b==0:return 0.,'BOTH_EXPLICIT_TD_COMPONENT_ZEROS'
  return None,'ATD_NEGATIVE_EVENT_NOT_PROVED:'+ra+':'+rb
 return value(stats,target)


def team(x):
 from nfl_lab.data import _team
 import pandas as pd
 return _team(pd.Series([x])).iloc[0]


def aware(value):
 import pandas as pd
 stamp=pd.Timestamp(value)
 require(not pd.isna(stamp) and stamp.tzinfo is not None,'explicit aware event clock required')
 return stamp.tz_convert('UTC')


def validate_queries(q,roles_by_target):
 require(set(KEY+['position','kickoff_utc','sleeper_id'])<=set(q),'primary roster query metadata incomplete')
 require(not q.duplicated(KEY[:4]).any(),'duplicate primary query identities')
 require(q.season.eq(2026).all() and q.week.isin(range(1,8)).all(),'fixed2026W1-7 query scope required')
 require(set(roles_by_target)<=set(TARGETS) and roles_by_target,'declared role populations required')
 for target,roles in roles_by_target.items():require(isinstance(roles,list) and roles and set(roles)<={'QB','RB','FB','WR','TE'},'unsupported frozen role population')
 for x in q.kickoff_utc.drop_duplicates():aware(x)


def base_output(q,target,source_sha256,source_version):
 return {**{k:q[k] for k in KEY},'position':q['position'],'kickoff_utc':q['kickoff_utc'],'target':target,
  'actual':None,'participation_state':'unknown','outcome_state':'unknown_participation','label_reason':'NO_QUALIFIED_SOURCE_LABEL',
  'source_sha256':source_sha256,'source_version':source_version,'grading_version':VERSION,
  'evidence_tier':'CURRENT_VINTAGE_POSTGAME_LABEL_RECONSTRUCTION','historical_publication_utc':None,
  'venue_settlement':'UNQUALIFIED_STATISTICAL_LABEL_ONLY'}


def classify(result,pstate,pwhy,numeric,nwhy):
 result['participation_state']=pstate
 result['participation_evidence']=pwhy
 result['label_reason']=nwhy
 if pstate=='dnp':result['outcome_state']='known_dnp';return result
 if pstate!='played':result['outcome_state']='unknown_participation';return result
 result['actual']=numeric
 result['outcome_state']='played_missing' if numeric is None else 'played_zero' if numeric==0 else 'played_nonzero'
 return result


def history_lookup(parts):
 import pandas as pd
 history=pd.concat(parts,ignore_index=True)
 needed=KEY+['position','kickoff_utc','participation_state']
 require(set(needed)<=set(history),'rawhistory label schema incomplete')
 history=history.loc[history.season.eq(2026)&history.week.isin(range(1,7))].copy()
 require(not history.duplicated(KEY[:4]).any(),'overlapping rawhistory labels need explicit reconciliation')
 return {(r['season'],r['week'],r['game_id'],r['player_id']):r for r in history.to_dict('records')}


def history_label(q,target,lookup,source_ref):
 result=base_output(q,target,source_ref['sha256'],source_ref['version'])
 old=lookup.get(tuple(q[k] for k in KEY[:4]))
 if old is None:return result
 if any(team(old[k])!=team(q[k]) for k in ['team','opponent']) or aware(old['kickoff_utc'])!=aware(q['kickoff_utc']):
  result['label_reason']='SOURCE_HISTORY_CONTEXT_CONFLICT';return result
 state={'played':'played','DNP':'dnp','dnp':'dnp','unknown':'unknown'}.get(old['participation_state'])
 require(state is not None,'unregistered original participation state')
 stats={k:v for k,v in old.items() if k in set(TARGETS)|{'rush_td','rec_td'}}
 numeric,reason=numerical(stats,target)
 witness=old.get('participation_evidence')
 if state in ['played','dnp'] and (not isinstance(witness,str) or not witness):
  state='unknown';witness='MISSING_ORIGINAL_PARTICIPATION_WITNESS'
 if state=='dnp' and numeric is not None and numeric!=0:
  state='unknown';witness='CONTRADICTORY_DNP_NONZERO_SOURCE_LABEL'
 return classify(result,state,witness,numeric,reason)


def archive_event_lookup(archive):
 require(archive.get('season')==2026 and archive.get('week')==7,'exactW7 original archive required')
 events={}
 for g in archive.get('games',[]):
  require(g.get('id') not in events,'duplicate original source event')
  events[g['id']]={'home':team(g.get('home')),'away':team(g.get('away')),'kickoff':aware(g.get('kickoff'))}
 return events


def site_label(q,target,stats_by_id,events,source_ref,qualified_finals):
 result=base_output(q,target,source_ref['sha256'],source_ref['version'])
 if q['game_id'] not in qualified_finals:
  result['outcome_state']='pending';result['label_reason']='NO_QUALIFIED_FINALITY_BINDING';return result
 matches=[g for g in events.values() if {g['home'],g['away']}=={team(q['team']),team(q['opponent'])} and g['kickoff']==aware(q['kickoff_utc'])]
 if len(matches)!=1:result['label_reason']='NO_UNIQUE_EXACT_ARCHIVE_EVENT_CONTEXT';return result
 sleeper=q.get('sleeper_id')
 if not isinstance(sleeper,str) or not sleeper.isdigit():result['label_reason']='NO_EXACT_ROSTER_SLEEPER_GSIS_BINDING';return result
 entry=stats_by_id.get(sleeper)
 if not isinstance(entry,dict):result['label_reason']='SOURCE_PLAYER_WEEK_ROW_UNAVAILABLE';return result
 if any(not isinstance(entry.get(k),str) or team(entry[k])!=team(q[j]) for k,j in [('team','team'),('opp','opponent')]):
  result['label_reason']='PROVIDER_TEAM_OPPONENT_CONTEXT_MISSING_OR_CONFLICTING';return result
 if entry.get('pos') is not None and entry['pos']!=q['position']:
  result['label_reason']='PROVIDER_ROSTER_POSITION_CONTEXT_CONFLICT';return result
 stats=entry.get('stats')
 if not isinstance(stats,dict):result['label_reason']='SOURCE_STATS_OBJECT_UNAVAILABLE';return result
 presence=stats.get('_presence')
 if isinstance(presence,dict):
  context=presence.get('source_context');original=presence.get('original_row')
  if isinstance(context,dict) and any(context.get(k)!=v for k,v in [('season',2026),('week',7)]):
   result['label_reason']='ATTRIBUTED_SOURCE_PERIOD_CONTEXT_CONFLICT';return result
  if isinstance(original,dict) and (original.get('player_id')!=sleeper or team(original.get('team'))!=team(q['team']) or team(original.get('opponent'))!=team(q['opponent'])):
   result['label_reason']='ATTRIBUTED_ORIGINAL_ROW_IDENTITY_CONFLICT';return result
 state,witness=participation(entry)
 numeric,reason=numerical(stats,target)
 return classify(result,state,witness,numeric,reason)


def chart_lookup(document):
 require(document.get('target')=='nick-chart-ppr-v1' or document.get('scoring_version')=='nick-chart-ppr-v1','exact chart label capsule target required')
 lookup={}
 for label in document['labels']:
  identity=label['identity']
  if identity['season']!=2026 or identity['week'] not in range(1,7):continue
  require(label['scoring_version']=='nick-chart-ppr-v1','mixed chart scoring targets')
  key=tuple(identity[k] for k in KEY[:4])
  require(key not in lookup,'duplicate original chart label identity')
  lookup[key]=label
 return lookup


def chart_label(q,lookup,source_ref):
 result=base_output(q,'chart_ppr',source_ref['sha256'],source_ref['version'])
 if q['week']==7:result['label_reason']='W7_EXACT_CHART_PBP_RECOVERY_RETURN_CONVERSION_CLASSIFICATION_UNAVAILABLE';return result
 label=lookup.get(tuple(q[k] for k in KEY[:4]))
 if label is None:result['label_reason']='EXACT_CHART_SOURCE_LISTED_LABEL_UNAVAILABLE';return result
 identity=label['identity']
 if any(team(identity[k])!=team(q[k]) for k in ['team','opponent']):result['label_reason']='CHART_LABEL_CONTEXT_CONFLICT';return result
 state=label['state'];pstate='dnp' if state=='known_dnp' else 'played' if state in ['played_missing','played_zero','played_score'] else 'unknown'
 numeric=label.get('value') if state in ['played_zero','played_score'] else None
 if numeric is not None:
  require(finite(numeric) and abs(float(numeric)*50-round(float(numeric)*50))<=1e-8,'exact chart score lattice violated')
  numeric=round(float(numeric)*50)/50
 return classify(result,pstate,label.get('participation_evidence'),numeric,'RETAINED_EXACT_CHART_LABEL:'+state)


def qualify(queries,history_parts,chart_document,site_stats,archive,config):
 """Pure deterministic source qualification on the frozen full query population."""
 import pandas as pd
 roles=config['roles_by_target'];validate_queries(queries,roles)
 history=history_lookup(history_parts);chart=chart_lookup(chart_document) if 'chart_ppr' in roles else {};events=archive_event_lookup(archive)
 finals=set(config['qualified_final_game_ids']);out=[]
 for q in queries.to_dict('records'):
  for target,positions in roles.items():
   if q['position'] not in positions:continue
   if target=='chart_ppr':row=chart_label(q,chart,config['source_versions']['chart'])
   elif q['week']<=6:row=history_label(q,target,history,config['source_versions']['history_week6' if q['week']==6 else 'history'])
   else:row=site_label(q,target,site_stats,events,config['source_versions']['site'],finals)
   out.append(row)
 result=pd.DataFrame(out)
 require(not result.duplicated(KEY[:4]+['target']).any(),'duplicate target qualification rows')
 audit={'version':VERSION,'query_population_rows':len(queries),'qualified_label_opportunities':len(result),
  'coverage':[dict(zip(['week','target','outcome_state','label_reason'],key),rows=int(n)) for key,n in result.groupby(['week','target','outcome_state','label_reason'],dropna=False).size().items()],
  'scored_forecasts':0,'fits':0,'inference':0,'new_HTTP':0,'missing_means_zero':False,'chart_scoring_contract':'nick-chart-ppr-v1' if 'chart_ppr' in roles else None,
  'chart_qualification_state':'REQUESTED' if 'chart_ppr' in roles else 'NOT_REQUESTED_CHART_CAPSULE_NOT_DECODED',
  'W7_chart_dependency':'ActualW7PBP exactcredited return/recovery/2pt/fumble classification; olderPBP stopsW6',
  'site_limits':'Current-vintage provider cache; exactsourcecontext; explicitstatfields only; no archivalpregame/publication claim; no venue settlement qualification'}
 return result,audit


def materialize(config,go):
 """Only callable after root authenticates immutable forecast freeze/readback."""
 require(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root','exactroot/reviewer GO required')
 require(go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('config_sha256')==sha(canonical(config)),'exactworker/config binding required')
 require(go.get('forecast_freeze_sha256')==config['forecast_freeze']['sha256'],'authentic frozen forecast manifest binding required beforelabeldecode')
 import pandas as pd
 from tools.category_topfive_matched12_offer_driver_v1 import read_exact
 freeze=json.loads(read_exact(config['forecast_freeze']))
 require(freeze.get('state')==config['required_forecast_freeze_state'] and freeze.get('forecast_readback_verified') is True,'actual immutable forecast persistence/readback required')
 q=pd.read_parquet(io.BytesIO(read_exact(config['inputs']['queries'])))
 parts=[pd.read_parquet(io.BytesIO(read_exact(config['inputs'][k]))) for k in ['history','week6']]
 chart=json.loads(gzip.decompress(read_exact(config['inputs']['chart']))) if 'chart_ppr' in config['roles_by_target'] else None
 stats=json.loads(read_exact(config['inputs']['site_stats']))
 archive=json.loads(read_exact(config['inputs']['site_archive']))
 return qualify(q,parts,chart,stats,archive,config)


def fictional_checks():
 import pandas as pd
 count=0
 def check(ok):
  nonlocal count
  assert ok;count+=1
 def rejects(fn):
  nonlocal count
  try:fn()
  except ValueError:count+=1
  else:raise AssertionError('invalid fixture accepted')
 check(value({'rec':0},'rec')==(0.,'EXPLICIT_REPORTED_ZERO'))
 check(value({},'rec')[0] is None)
 check(value({'rec':True},'rec')[0] is None)
 check(value({'rec':float('nan')},'rec')[0] is None)
 check(value({'rec':-1},'rec')[0] is None)
 check(value({'rec':1.5},'rec')[0] is None)
 check(value({'rush_yd':-4},'rush_yd')[0]==-4)
 check(numerical({'rush_yd':-4,'rec_yd':10},'rush_rec_yd')[0]==6)
 check(numerical({'rush_yd':0},'rush_rec_yd')[0] is None)
 check(numerical({'pass_td':3},'anytime_td')[0] is None)
 check(numerical({'rush_td':1},'anytime_td')[0]==1)
 check(numerical({'rush_td':0,'rec_td':0},'anytime_td')[0]==0)
 check(numerical({'rush_td':0},'anytime_td')[0] is None)
 check(participation({'stats':{'gp':1}})[0]=='played')
 check(participation({'participation_status':'dnp','participation_source':'fixture'})[0]=='dnp')
 check(participation({'stats':{'gp':1},'participation_status':'dnp','participation_source':'fixture'})[0]=='unknown')
 check(participation({'stats':{'gp':'1'}})[0]=='unknown')
 check(participation({'stats':{'rec':1}})[0]=='played')
 check(participation({'stats':{'rush_yd':-2}})[0]=='played')
 check(participation({'stats':{'rec':1},'participation_status':'dnp','participation_source':'fixture'})[0]=='unknown')
 q=dict(season=2026,week=7,game_id='2026_07_ARI_ATL',player_id='00-1234567',team='ARI',opponent='ATL',position='WR',sleeper_id='1234',kickoff_utc='2026-10-25T17:00:00Z')
 archive=dict(season=2026,week=7,games=[dict(id='401000001',home='ATL',away='ARI',kickoff=q['kickoff_utc'])])
 events=archive_event_lookup(archive);ref={'sha256':'a'*64,'version':'FICTIONAL_ONLY'};finals={q['game_id']}
 entry={'team':'ARI','opp':'ATL','stats':{'gp':1,'rec':0}}
 check(site_label(q,'rec',{'1234':entry},events,ref,finals)['actual']==0)
 check(site_label(q,'rec_tgt',{'1234':entry},events,ref,finals)['outcome_state']=='played_missing')
 check(site_label(q,'rec',{'1234':{**entry,'team':'DAL'}},events,ref,finals)['actual'] is None)
 check(site_label(q,'rec',{'1234':entry},events,ref,set())['outcome_state']=='pending')
 check(site_label(q,'rec',{'1234':{'team':'ARI','opp':'ATL','stats':{'gp':1,'rec':2,'_presence':{'source_context':{'season':2026,'week':6}}}}},events,ref,finals)['actual'] is None)
 old={**q,'week':6,'participation_state':'played','participation_evidence':'positive_official_nfl_physical_event','rec':0}
 history=history_lookup([pd.DataFrame([old])]);q6={**q,'week':6}
 check(history_label(q6,'rec',history,ref)['actual']==0)
 old['participation_state']='unknown';history=history_lookup([pd.DataFrame([old])])
 check(history_label(q6,'rec',history,ref)['actual'] is None)
 label={'identity':{k:q6[k] for k in KEY},'scoring_version':'nick-chart-ppr-v1','state':'played_score','value':-0.02,'participation_evidence':'fictional witness'}
 chart=chart_lookup({'target':'nick-chart-ppr-v1','labels':[label]})
 check(chart_label(q6,chart,ref)['actual']==-0.02)
 check(chart_label(q,chart,ref)['actual'] is None)
 rejects(lambda:chart_lookup({'target':'legacy-ppr','labels':[]}))
 bad={**label,'value':0.01};rejects(lambda:chart_label(q6,chart_lookup({'target':'nick-chart-ppr-v1','labels':[bad]}),ref))
 cfg={'roles_by_target':{'rec':['WR']},'qualified_final_game_ids':[q['game_id']],'source_versions':{k:ref for k in ['history','history_week6','site']}}
 only,audit=qualify(pd.DataFrame([q]),[pd.DataFrame([old])],None,{'1234':entry},archive,cfg)
 check(len(only)==1 and only.actual.iloc[0]==0 and audit['chart_qualification_state']=='NOT_REQUESTED_CHART_CAPSULE_NOT_DECODED')
 return {'fictional_checks_passed':count,'actual_NFL_label_rows_decoded':0,'fits':0,'forecasts':0,'accuracy_comparisons':0}


def finality_configuration():
 """Metadata-only refs already registered by original completedW7qualifications."""
 meta=json.loads((ROOT/'config/week7-monday-qb-final-metadata-v1.json').read_text())
 main=json.loads(Path(meta['main_plan']['path']).read_text())
 parent=json.loads(Path(main['evidence_reuse']['parent_scoring_plan']['path']).read_text())
 technical=json.loads((ROOT/'config/week7-monday-QB-cached-continuation-v2.json').read_text())
 current=json.loads((ROOT/'config/weekly-current-query-v2.json').read_text())
 return {'version':'matched12-finality-lexical-metadata-v1','scoreboard':parent['accepted_capture_artifacts']['ESPN_W7_FINALITY.json.gz'],
  'scoreboard_receipt':parent['accepted_capture_artifacts']['ESPN_W7_FINALITY.receipt.json'],
  'summary':technical['cached_inputs']['ESPN_SUMMARY_401873009.json.gz'],
  'summary_receipt':technical['cached_inputs']['ESPN_SUMMARY_401873009.receipt.json'],'schedule':current['schedule'],
  'projector':{'path':__import__('os').environ['MATCHED12_PROJECTOR_SOURCE_FILE'],'bytes':Path(__import__('os').environ['MATCHED12_PROJECTOR_SOURCE_FILE']).stat().st_size,'sha256':'0d29fd53fb80755248d22177a984df26111044fa1ab3a183f3e8d45c534d1f2d'}}


def finality_metadata(config,go):
 """Lexically decode clocks/status/teams only; skip every score/stat subtree."""
 require(go.get('state')=='ROOT_METADATA_ONLY_GO' and go.get('registered_by')=='/root','bounded rootmetadata GO required')
 require(go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('config_sha256')==sha(canonical(config)),'exactmetadata source/config GO required')
 import importlib.util,pandas as pd
 from tools.category_topfive_matched12_offer_driver_v1 import read_exact,qualified_schedule,SCHEDULE_COLUMNS
 spec=importlib.util.spec_from_file_location('matched12_metadata_projector',config['projector']['path']);module=importlib.util.module_from_spec(spec)
 read_exact(config['projector']);spec.loader.exec_module(module)
 schedule=qualified_schedule(pd.read_csv(io.BytesIO(read_exact(config['schedule'])),usecols=SCHEDULE_COLUMNS))
 schedule=schedule.loc[schedule.week.eq(7)]
 fields=set()
 for p in [('season','year'),('season','type'),('week','number'),('header','id'),('header','season','year'),('header','season','type'),('header','week')]:fields.add(p)
 for base in [('events','*'),('header',)]:
  for name in ['id','date']:fields.add(base+(name,))
  for name in ['id','date']:fields.add(base+('competitions','*',name))
  for name in ['completed','state','name']:fields.add(base+('competitions','*','status','type',name))
  for tail in [('homeAway',),('team','abbreviation')]:fields.add(base+('competitions','*','competitors','*')+tail)
 accepted={};audits=[]
 for kind in ['scoreboard','summary']:
  raw=gzip.decompress(read_exact(config[kind]));receipt=json.loads(read_exact(config[kind+'_receipt']))
  require(receipt.get('status')==200 and receipt.get('complete_HTTP_entity') is True and receipt.get('complete_decoded_body') is True and receipt.get('raw_body_retained') is True,'original complete retainedsource receipt required')
  require(receipt.get('raw_body_archive')==config[kind] and sha(raw)==receipt['sha256'] and len(raw)==receipt['decoded_bytes'],'original rawsource/receipt exactbinding')
  document,audit=module.project(raw,fields,maximum_bytes=2*1024**2)
  period=document if kind=='scoreboard' else document.get('header',{})
  require(period.get('season',{}).get('year')==2026 and period.get('season',{}).get('type')==2,'exact REG2026period required')
  require((period.get('week',{}).get('number') if kind=='scoreboard' else period.get('week'))==7,'exact W7 sourceperiod required')
  events=document.get('events',[]) if kind=='scoreboard' else [period]
  for event in events:
   eid=str(event.get('id'));competitions=event.get('competitions',[])
   if len(competitions)!=1:continue
   c=competitions[0]
   if str(c.get('id'))!=eid:continue
   date=c.get('date',event.get('date'));kickoff=aware(date)
   sides=c.get('competitors',[])
   if len(sides)!=2:continue
   teams={s.get('homeAway'):team(s.get('team',{}).get('abbreviation')) for s in sides}
   if set(teams)!={'home','away'}:continue
   match=schedule.loc[schedule.home_team.eq(teams['home'])&schedule.away_team.eq(teams['away'])&schedule.kickoff_utc.eq(kickoff)]
   if len(match)!=1:continue
   status=c.get('status',{}).get('type',{})
   if status.get('completed') is not True or status.get('state')!='post' or status.get('name') not in ['STATUS_FINAL','STATUS_FINAL_OVERTIME']:continue
   require(aware(receipt['request_started_utc'])>kickoff,'finalstate observedbeforekickoff')
   key=match.iloc[0].game_id;item={'game_id':key,'source_event_id':eid,'kickoff_utc':kickoff.isoformat(),'home':teams['home'],'away':teams['away'],'completed':True,'state':'post','status':status['name']}
   if key in accepted:require(accepted[key]==item,'conflicting exact qualified finalevent context')
   accepted[key]=item
  audits.append({'source':kind,'source_sha256':config[kind]['sha256'],'receipt_sha256':config[kind+'_receipt']['sha256'],**audit})
 return {'version':config['version'],'state':'METADATA_ONLY_QUALIFIED_FINAL_EVENTS','qualified_final_game_ids':sorted(accepted),'events':[accepted[k] for k in sorted(accepted)],'source_projection_audits':audits,'actual_statistical_outcomes_decoded':0,'fits_forecasts_scores_HTTP':0,'expected_W7_schedule_games':len(schedule),'qualified_games':len(accepted),'unqualified_game_ids':sorted(set(schedule.game_id)-set(accepted))}
