"""Root-GO-only actual line-panel materialization; no outputs written on import.

All NFL source decoding occurs in materialize after exact code/config/source GO.
The caller freezes returned frames through the registered managed private store.
"""
from __future__ import annotations
import hashlib, io, json, zipfile
from pathlib import Path
VERSION='matched12-offer-materialization-v1.1'
ROOT=Path(__file__).resolve().parents[1]
NORMALIZED_COLUMNS={
 'bet_type','source_event_id','book_id','source_player_id','line_type','period','side','line','american_odds',
 'source_team','join_name','source_position','position_group','total_bets_on_event','season','week',
 'source_collection_naive','open_inferred','open_source_book_id','player_id','source_row_number','source_sha256',
 'source_member','target','book_name','book_kind','timing_lane','timing_reason','identity_status','rejection_reasons',
 'american_odds_valid','event_semantics','duplicate_status','duplicate_group','source_eligible_exploratory','cutoff_qualified',
 'team','position','game_id','opponent','kickoff_utc','is_home','source_team_disagrees_with_historical_roster',
 'source_position_disagrees_with_historical_roster'}
SCHEDULE_COLUMNS=['game_id','season','week','game_type','gameday','gametime','away_team','home_team']
IDENTITY_COLUMNS=['player_id','sleeper_id','identity_status']


def validate_schema(names):
 require(set(names)==NORMALIZED_COLUMNS,'normalized exact allowlist changed; no postgame columns admitted')


def require(condition,message):
 if not condition:raise ValueError(message)


def digest(body):return hashlib.sha256(body).hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def read_exact(ref):
 """Canonical nonsymlink, regular file, byte/identity stable readonly source read."""
 p=Path(ref['path']);require(p.is_absolute() and p.resolve()==p,'canonical absolute source required')
 require(not any(x.is_symlink() for x in (p,*p.parents)),'symlink source forbidden')
 before=p.stat();require(p.is_file(),'regular source required')
 if 'blob' in ref:
  blob=Path(ref['blob'])
  require(blob.is_absolute() and blob.resolve()==blob and not any(x.is_symlink() for x in (blob,*blob.parents)),'canonical CAS blob required')
  require(blob.name==ref['sha256'],'CAS blob name/digest binding')
  bs=blob.stat();require((bs.st_dev,bs.st_ino,bs.st_size)==(before.st_dev,before.st_ino,before.st_size),'cache/CAS identity mismatch')
 body=p.read_bytes();after=p.stat()
 require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'source changed during read')
 require(len(body)==ref['bytes'] and digest(body)==ref['sha256'],'source exact bytes/hash mismatch')
 return body


def read_member(ref):
 body=read_exact(ref['container'])
 with zipfile.ZipFile(io.BytesIO(body)) as z:
  info=z.getinfo(ref['member']);require(info.file_size==ref['bytes'] and info.file_size<=16*1024**2,'bounded exact member required')
  raw=z.read(info)
 require(digest(raw)==ref['sha256'],'member hash mismatch')
 return raw


def qualified_schedule(frame):
 """Only declared metadata fields; kickoff derives from original Eastern clock."""
 import pandas as pd
 from nfl_lab.data import _team
 require(set(frame)==set(SCHEDULE_COLUMNS),'schedule projection must be exact metadata schema')
 f=frame.loc[frame.season.eq(2026)&frame.week.isin(range(1,8))&frame.game_type.eq('REG')].copy()
 require(len(f)>0 and not f.game_id.isna().any() and not f.game_id.duplicated().any(),'unique canonical games required')
 for c in ['away_team','home_team']:f[c]=_team(f[c])
 require(not f.home_team.eq(f.away_team).any(),'self opposing schedule')
 local=pd.to_datetime(f.gameday.astype('string')+' '+f.gametime.astype('string'),errors='raise')
 f['kickoff_utc']=local.dt.tz_localize('America/New_York',ambiguous='raise',nonexistent='raise').dt.tz_convert('UTC')
 return f


def verify_annual_context(rows,schedule):
 """Consistency check; not independent validation of upstream source event IDs."""
 import pandas as pd
 sides=[]
 for own,other in [('home_team','away_team'),('away_team','home_team')]:
  side=schedule[['season','week','game_id','kickoff_utc',own,other]].rename(columns={own:'team',other:'opponent'});sides.append(side)
 context=pd.concat(sides,ignore_index=True)
 require(not context.duplicated(['season','game_id','team']).any(),'ambiguous canonical schedule context')
 f=rows.copy();f['source_week_preserved']=f.week
 linked=f.merge(context,on=['season','game_id','team'],how='left',suffixes=('','_canonical'),validate='many_to_one')
 # Rejected/unbound normalizer records remain rejected, not rescued by this check.
 bound=linked.identity_status.eq('source_gsis_exact_historical_roster_schedule')
 for value in linked.loc[bound,'kickoff_utc'].dropna().drop_duplicates():
  require(pd.Timestamp(value).tzinfo is not None,'known annual kickoff cannot acquire fabricated timezone')
 clocks=pd.to_datetime(linked.kickoff_utc,utc=True,errors='raise')
 same=linked.week.eq(linked.week_canonical)&linked.opponent.eq(linked.opponent_canonical)&clocks.eq(linked.kickoff_utc_canonical)
 bad=bound&~same
 require(not bad.any(),'canonical source-week/game/team/kickoff mismatch; separate event repair required')
 # Do not send derived fields to the immutable input API.
 return rows,{'canonical_bound_rows_checked':int(bound.sum()),'canonical_context_mismatches':int(bad.sum()),
 'source_event_identity':'SOURCE_WEEK_GSIS_ROSTER_SCHEDULE_BINDING_NOT_INDEPENDENT_EVENT_CROSSWALK'}


def site_bindings(archive,registry,schedule,identity_sha256):
 """Source-only exact registry identity + unique team/opponent/kickoff event join."""
 import pandas as pd
 from nfl_lab.query_identity import resolve_query_identities,VERSION as ID_VERSION,RESOLVED
 from nfl_lab.data import _team
 mappings=[];bad=[]
 for ordinal,g in enumerate(archive.get('games',[])):
  k=pd.Timestamp(g.get('kickoff'))
  if pd.isna(k) or k.tzinfo is None:bad.append((ordinal,'UNKNOWN_KICKOFF_TIMEZONE'));continue
  home=_team(pd.Series([g.get('home')])).iloc[0];away=_team(pd.Series([g.get('away')])).iloc[0]
  match=schedule.loc[schedule.week.eq(archive['week'])&schedule.home_team.eq(home)&schedule.away_team.eq(away)&schedule.kickoff_utc.eq(k)]
  if len(match)!=1:bad.append((ordinal,'NO_UNIQUE_EXACT_EVENT_CONTEXT'));continue
  item=match.iloc[0]
  mappings.append(dict(source_game_id=g['id'],game_id=item.game_id,season=2026,week=int(item.week),kickoff_utc=item.kickoff_utc.isoformat(),home_team=home,away_team=away))
 events=pd.DataFrame(mappings)
 if len(events):require(not events.source_game_id.duplicated().any(),'duplicate exact source event')
 event_sha=digest(events.to_json(orient='table',date_format='iso',index=False,force_ascii=True).encode())
 queries=[];original=[]
 for p in archive.get('players',[]):
  if not isinstance(p.get('id'),str) or not p['id'].isdigit():continue
  matches=events.loc[events.source_game_id.eq(p.get('game_id'))] if len(events) else events
  if len(matches)!=1:continue
  g=matches.iloc[0];team=p.get('team');opp=p.get('opp')
  # Preserve source context and reject aliases unless source already canonical.
  if {team,opp}!={g.home_team,g.away_team} or team==opp:continue
  queries.append(dict(season=2026,week=archive['week'],game_id=g.game_id,player_id='sleeper:'+p['id'],team=team,opponent=opp,
   position=p.get('pos'),kickoff_utc=g.kickoff_utc,cutoff_utc=g.kickoff_utc,outcome_available_utc=None,participation_state='unknown'))
  original.append(dict(source_game_id=p['game_id'],source_player_id=p['id']))
 columns=['season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc','outcome_available_utc','participation_state']
 q=pd.DataFrame(queries,columns=columns)
 if len(q):resolved,receipt=resolve_query_identities(q,registry,identity_sha256=identity_sha256)
 else:resolved=q;receipt={'input_rows':0,'registry_verified_or_resolved_rows':0}
 out=[]
 for i,r in enumerate(resolved.itertuples()):
  if r.identity_resolution_state not in RESOLVED:continue
  out.append(dict(season=2026,week=archive['week'],**original[i],game_id=r.game_id,player_id=r.player_id,team=r.team,
   opponent=r.opponent,position=r.position,kickoff_utc=r.kickoff_utc,identity_resolution_state=r.identity_resolution_state,
   identity_source_sha256=identity_sha256,identity_adapter_version=ID_VERSION,event_crosswalk_sha256=event_sha))
 from tools.category_topfive_matched12_offers_v1 import SITE_BINDING_COLUMNS
 b=pd.DataFrame(out,columns=sorted(SITE_BINDING_COLUMNS))
 return b,{'identity':receipt,'event_crosswalk_sha256':event_sha,'event_rows':len(events),'unresolved_events':len(bad),
 'source_players':len(archive.get('players',[])),'bound_source_players':len(b),'team_alias_policy':'EXACT_CANONICAL_SOURCE_CONTEXT_ONLY_NO_REWRITE'}


def add_scoring_contract(frame):
 f=frame.copy()
 if not len(f):return f
 f['cutoff_utc']=f.kickoff_utc
 f['evidence_tier']='TIMING_UNVERIFIED_RETROSPECTIVE_LINES'
 f['primary_offer_policy']='matched12-line-only-primary-v1-20261030:ANNUAL_THEN_RECORDED_DK_SOURCE_FALLBACK'
 f['statistical_contract']='EXACT_SUPPORTED_STATISTIC_VS_RECORDED_THRESHOLD;VENUE_SETTLEMENT_UNQUALIFIED'
 return f


def materialize(config,go):
 """Actual NFL preparation. Root caller must journal start, retain all frames."""
 import pandas as pd
 import pyarrow.parquet as pq
 from tools import category_topfive_matched12_offers_v1 as policy
 require(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root','fresh root and independent GO required')
 require(go.get('worker_sha256')==digest(Path(__file__).read_bytes()) and go.get('config_sha256')==digest(canonical(config)),'exact outer worker/config GO required')
 require(config['version']==VERSION,'wrong outer source version')
 require(digest((ROOT/'tools/category_topfive_matched12_offers_v1.py').read_bytes())==config['policy_sha256'],'frozen offer policy changed')
 annual_body=read_member(config['annual']);schema=pq.ParquetFile(io.BytesIO(annual_body)).schema_arrow
 validate_schema(schema.names)
 rows=pq.read_table(io.BytesIO(annual_body),use_threads=False).to_pandas()
 require(len(rows)<=100000,'finite annual source row envelope exceeded')
 schedule=qualified_schedule(pd.read_csv(io.BytesIO(read_exact(config['schedule'])),usecols=SCHEDULE_COLUMNS))
 rows,context_audit=verify_annual_context(rows,schedule)
 annual=policy.prepare_annual_line_only(rows,admitted_source_sha256s=set(config['admitted_original_sha256s']))
 site_results=[]
 if config.get('site_archives'):
  registry=pq.read_table(io.BytesIO(read_exact(config['identity'])),columns=IDENTITY_COLUMNS,use_threads=False).to_pandas()
  for ref in config['site_archives']:
   body=read_exact(ref);archive=json.loads(body);bindings,audit=site_bindings(archive,registry,schedule,config['identity']['sha256'])
   binding_sha=digest(bindings.to_json(orient='table',date_format='iso',index=False,force_ascii=True).encode())
   result=policy.prepare_site_line_only(archive,bindings,expected_binding_sha256=binding_sha,source_sha256=ref['sha256'])
   result['binding_frame']=bindings;result['binding_audit']=audit;site_results.append(result)
 site=pd.concat([x['primary_dk'] for x in site_results],ignore_index=True) if site_results else pd.DataFrame()
 primary=add_scoring_contract(policy.combine_source_fallback(annual['primary'],site))
 audit={'version':VERSION,'input_annual_member_sha256':config['annual']['sha256'],'annual':annual['audit'],'context':context_audit,
  'site':[dict(x['audit'],binding=x['binding_audit']) for x in site_results],
  'primary_rows':len(primary),'primary_unique_games':int(primary.game_id.nunique()) if len(primary) else 0,
  'coverage':[dict(zip(['week','target','source_stream'],key),rows=int(n)) for key,n in primary.groupby(['week','target','source_stream'],dropna=False).size().items()] if len(primary) else [],
  'site_archives_missing':config.get('missing_site_archives',[]),'new_fits':0,'new_model_inference':0,'new_accuracy_scores':0,
  'prices':'SOURCE_VALUES_RETAINED_BUT_MARKET_EV_AND_SETTLEMENT_UNQUALIFIED','line_event_identity_limit':context_audit['source_event_identity']}
 return {'primary':primary,'annual':annual,'site':site_results,'audit':audit}


def fictional_checks():
 import pandas as pd
 from tools.category_topfive_matched12_offers_v1 import prepare_site_line_only
 count=0
 def reject(fn):
  nonlocal count
  try:fn()
  except ValueError:count+=1
  else:raise AssertionError('fictional invalid condition accepted')
 validate_schema(NORMALIZED_COLUMNS);count+=1
 reject(lambda:validate_schema(NORMALIZED_COLUMNS|{'net_units'}))
 raw=pd.DataFrame([dict(game_id='2026_06_A_B',season=2026,week=6,game_type='REG',gameday='2026-10-18',gametime='13:00',away_team='ARI',home_team='ATL')])
 schedule=qualified_schedule(raw)
 assert schedule.iloc[0].kickoff_utc.isoformat()=='2026-10-18T17:00:00+00:00';count+=1
 reject(lambda:qualified_schedule(pd.concat([raw,raw])))
 row=dict(season=2026,week=6,game_id='2026_06_A_B',team='ARI',opponent='ATL',kickoff_utc='2026-10-18T17:00:00+00:00',identity_status='source_gsis_exact_historical_roster_schedule')
 _,receipt=verify_annual_context(pd.DataFrame([row]),schedule);assert receipt['canonical_bound_rows_checked']==1;count+=1
 reject(lambda:verify_annual_context(pd.DataFrame([{**row,'week':5}]),schedule))
 reject(lambda:verify_annual_context(pd.DataFrame([{**row,'kickoff_utc':'2026-10-18T17:00:00'}]),schedule))
 identity='a'*64
 registry=pd.DataFrame([dict(player_id='00-1234567',sleeper_id='1234',identity_status='source_exact_binding')])
 archive=dict(season=2026,week=6,saved_at=None,games=[dict(id='401000000',home='ATL',away='ARI',kickoff='2026-10-18T17:00:00+00:00')],
 players=[dict(id='1234',game_id='401000000',team='ARI',opp='ATL',pos='WR',late=True,props=[dict(key='rec',line=4.5,line_from='dk',lean=None)])])
 bindings,audit=site_bindings(archive,registry,schedule,identity)
 assert len(bindings)==1 and audit['bound_source_players']==1;count+=1
 h=digest(bindings.to_json(orient='table',date_format='iso',index=False,force_ascii=True).encode())
 result=prepare_site_line_only(archive,bindings,expected_binding_sha256=h,source_sha256='b'*64)
 assert len(result['primary_dk'])==1 and result['audit']['late_flag_used_to_remove_lines'] is False;count+=1
 scored=add_scoring_contract(result['primary_dk'])
 assert scored.iloc[0].cutoff_utc==scored.iloc[0].kickoff_utc and scored.iloc[0].source_quote_time is None;count+=1
 reject(lambda:prepare_site_line_only(archive,bindings,expected_binding_sha256='c'*64,source_sha256='b'*64))
 return {'fictional_checks_passed':count,'NFL_source_decodes':0,'fits':0,'model_inference':0,'accuracy_scores':0}


def configuration_from_registered_inputs(site_refs=None):
 """Build private runtime refs; publish only safe hashes/selectors, never paths."""
 old=json.loads((ROOT/'config/historical-market-comparison-no2025-v1.sealed.json').read_text())
 annual=next(x for x in old['normalized_market_inputs'] if x['season']==2026)
 current=json.loads((ROOT/'config/weekly-current-query-v2.json').read_text())
 schedule=current['schedule'];base=Path(schedule['path']).parent.parent
 identity=base/'processed/identity.parquet'
 return {'version':VERSION,'policy_sha256':digest((ROOT/'tools/category_topfive_matched12_offers_v1.py').read_bytes()),
  'annual':annual,'schedule':schedule,
  'admitted_original_sha256s':['10c73a3cb010922ce5cdd2c5458d5ce405a03c9a3f027a388b2cd9f123757b4b'],
  'identity':{'path':str(identity),'bytes':536303,'sha256':'504eab204149ecd645e918c474cfa32dca78b2fc05f572cbafbb254e9b6dfffa'},
  'site_archives':site_refs or [],'missing_site_archives':[] if site_refs else ['W4','W5','W6','W7']}


def scoring_projection(frame):
 """Narrow outerallowlist; keep source/timing strata, never fake prices/probs."""
 f=frame.copy()
 if not len(f):return f
 f['jurisdiction']=f.source_stream.map(lambda x:'NJ' if x=='ANNUAL_NAMED_NJ' else 'UNKNOWN')
 keep=['target','season','week','game_id','player_id','team','opponent','cutoff_utc','line','evidence_tier',
  'primary_offer_policy','statistical_contract','source_stream','book_id','source_sha256','source_quote_time',
  'source_collection_naive','quote_timing_status','jurisdiction','kickoff_utc','opportunity_key']
 return f.reindex(columns=keep)
