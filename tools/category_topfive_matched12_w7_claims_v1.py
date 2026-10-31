import gzip,hashlib,json,math,re
from pathlib import Path
VERSION='matched12-w7-qualified-claim-supplement-v1'
PASS={'pass_yd','pass_td','pass_cmp','pass_att','pass_int'}
NON={'rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td'}
COUNTS={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','anytime_td'}
WITNESS={'POSITIVE_PASS_ATTEMPTS','POSITIVE_PASSING_SACKS_TAKEN','SAME_ATHLETE_POSITIVE_RUSH_OR_RECEPTION','PRIOR_CANONICAL_PLAYED','EXPLICIT_ACTIVITY_COUNT_YARDS_OR_TD'}
KEY=['season','week','game_id','player_id','team','opponent','target']
def require(x,s):
 if not x:raise ValueError(s)
def sha(b):return hashlib.sha256(b).hexdigest()
def encode(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def team(x):return {'WSH':'WAS','LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'}.get(x,x)
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def decode(body,ref):
 require(len(body)==ref['bytes'] and sha(body)==ref['sha256'],'SOURCE_BYTES_CHANGED')
 return json.loads(gzip.decompress(body) if ref.get('gzip',True) else body)
def oldkey(c):return (c.get('original_game_id'),c.get('player_id'),c.get('target'))
def qualify(c,packet,kind,q,events):
 if c.get('period')!='REG':return 'PERIOD_UNQUALIFIED'
 if c.get('participation_state')!='played':return 'NO_PLAYED_PROOF'
 value=c.get('actual');target=c.get('target')
 if not finite(value) or target in COUNTS and (value<0 or int(value)!=value) or target=='anytime_td' and value not in [0,1]:return 'INVALID_TARGET_SUPPORT'
 if target not in (PASS if kind=='QB' else NON):return 'TARGET_UNADMITTED'
 if re.fullmatch('00-[0-9]{7}',str(c.get('player_id'))) is None:return 'NON_GSIS'
 event=events.get(c.get('original_game_id'))
 if event is None or str(c.get('game_id'))!='espn:'+str(event['source_event_id']) or str(c.get('source_finality_event'))!=str(event['source_event_id']):return 'FINAL_EVENT_CONFLICT'
 import pandas as pd
 clock=pd.Timestamp(q['kickoff_utc']);observed=pd.Timestamp(c.get('observed_at'))
 if pd.isna(clock) or clock.tzinfo is None or clock!=pd.Timestamp(event['kickoff_utc']):return 'KICKOFF_CONFLICT'
 if pd.isna(observed) or observed.tzinfo is None or observed<=clock:return 'OBSERVATION_CLOCK_UNQUALIFIED'
 src=packet.get('source_refs',{}).get(str(event['source_event_id']),{});src=src.get('body',src)
 if c.get('source_archive')!=src or re.fullmatch('[0-9a-f]{64}',str(src.get('sha256'))) is None:return 'SOURCE_ARCHIVE_CONFLICT'
 if c.get('sleeper_id')!=q['sleeper_id'] or team(c.get('team'))!=team(q['team']) or {team(q['team']),team(q['opponent'])}!={team(event['home']),team(event['away'])}:return 'IDENTITY_CONFLICT'
 if c.get('source_participation_evidence') not in WITNESS:return 'NO_PHYSICAL_WITNESS'
 if re.fullmatch('[0-9a-f]{64}',str(c.get('identity_binding_sha256'))) is None or re.fullmatch('[0-9a-f]{64}',str(c.get('source_sha256'))) is None:return 'NO_SOURCE_BINDING'
 if kind=='QB':
  receipt=packet.get('source_receipts',{}).get(str(event['source_event_id']),{})
  if receipt.get('sha256')!=c['source_sha256'] or not all(receipt.get(x) is True for x in ['complete_HTTP_entity','complete_decoded_body','raw_body_retained']):return 'SOURCE_RECEIPT_UNQUALIFIED'
  if c.get('source')!='ESPN_FINAL_INDIVIDUAL_PASSING_TABLE_V1' or c.get('scoring_id')!='NFL_PASSING_BOX_SCORE' or not isinstance(c.get('source_explicit_display'),str) or not c['source_explicit_display'] or not c.get('source_coordinate'):return 'NO_PASSING_DISPLAY'
 else:
  if c.get('source')!='ESPN_FINAL_NONPASSING_TABLES_V1' or c.get('scoring_id')!='NFL_RUSH_RECEIVE_BOX_SCORE_V1':return 'NO_NONPASSING_SOURCE'
  evidence=c.get('source_value_evidence');coords=c.get('source_coordinates',[])
  if target=='anytime_td':
   if value==1:
    if evidence!='POSITIVE_EXPLICIT_RUSH_OR_RECEIVING_TD' or not coords:return 'ATD_POSITIVE_UNPROVED'
   elif evidence=='TWO_EXPLICIT_TD_ZEROS':
    if len(coords)!=2:return 'ATD_ZERO_COORDS_MISSING'
   elif evidence=='FULL_INDIVIDUAL_TD_CREDIT_EXHAUSTION':
    proofs=[p for p in packet.get('credit_exhaustion_proofs',[]) if str(p.get('event'))==str(event['source_event_id']) and team(p.get('team'))==team(q['team']) and p.get('source_sha256')==c['source_sha256']]
    if len(proofs)!=2 or {p.get('kind') for p in proofs if p.get('complete_individual_credit') is True}!={'rushing','receiving'} or len(c.get('source_credit_proof_coordinates',[]))<2 or not all(x in [p.get('coordinate') for p in proofs] for x in c['source_credit_proof_coordinates']):return 'ATD_EXHAUSTION_UNQUALIFIED'
   else:return 'ATD_ZERO_UNPROVED'
  elif target=='rush_rec_yd':
   if evidence!='TWO_EXPLICIT_COMPONENTS' or len(coords)!=2:return 'COMBINED_UNPROVED'
  elif evidence!='EXPLICIT_INDIVIDUAL_TABLE' or not coords:return 'STAT_NOT_EXPLICIT'
 return None
def supplement(strict,queries,finality,packets,config):
 import pandas as pd
 require(not {'prediction','point','mean','median','absolute_error'}&set(strict),'LABELS_ONLY')
 require(not strict.duplicated(KEY).any(),'DUPLICATE_LABELS')
 q=queries.loc[queries.season.eq(2026)&queries.week.eq(7)].copy()
 require(not q.duplicated(['game_id','player_id']).any(),'DUPLICATE_QUERY')
 lookup={(r['game_id'],r['player_id']):r for r in q.to_dict('records')};events={e['game_id']:e for e in finality['events'] if e['completed'] is True and e['state']=='post'}
 require(len(events)==14,'FOURTEEN_FINAL_GAMES_REQUIRED')
 claims={};blocked=set();rejected=[];evidence=[]
 for name,spec in config['packets'].items():
  packet=packets[name]
  for field in ['conflicting_new_claims','conflicts','numeric_or_participation_conflicts']:
   for conflict in packet.get(field,[]):
    c=conflict.get('claim',conflict.get('new_source_claim',conflict))
    if c.get('original_game_id'):blocked.add(oldkey(c))
    elif 'key' in conflict:
     pid,gid,target=conflict['key'];mapped=[g for g,e in events.items() if 'espn:'+str(e['source_event_id'])==gid]
     for g in mapped:blocked.add((g,pid,target))
  for c in packet.get(spec['claim_field'],[]):
   key=oldkey(c);query=lookup.get(key[:2])
   try:reason='OUTSIDE_QUERY' if query is None else qualify(c,packet,spec['kind'],query,events)
   except (ValueError,TypeError,KeyError):reason='MALFORMED_SOURCE_CLAIM'
   item={'packet':name,'packet_sha256':spec['sha256'],'claim':c,'reason':reason};evidence.append(item)
   if reason:rejected.append(item);continue
   claims.setdefault(key,[]).append(c)
 result=strict.copy();result['prior_source_sha256']=result.get('source_sha256');actions={};covered=set()
 for i,row in result.loc[result.season.eq(2026)&result.week.eq(7)].iterrows():
  key=(row.game_id,row.player_id,row.target);cs=claims.get(key,[])
  if not cs and key not in blocked:continue
  covered.add(key);values={c['actual'] for c in cs};conflict=key in blocked or len(values)>1 or row.participation_state in ['dnp','DNP']
  if finite(row.actual) and values and row.actual not in values:conflict=True
  if conflict:
   result.at[i,'actual']=float('nan');result.at[i,'participation_state']='unknown';result.at[i,'outcome_state']='unknown_participation';action='SOURCE_CONFLICT'
  elif cs:
   value=cs[0]['actual'];action='SOURCE_CORROBORATION' if finite(row.actual) else 'SOURCE_SUPPLEMENT'
   result.at[i,'actual']=value;result.at[i,'participation_state']='played';result.at[i,'outcome_state']='played_zero' if value==0 else 'played_nonzero'
  else:continue
  result.at[i,'label_reason']=action;result.at[i,'grading_version']=VERSION;result.at[i,'source_version']=VERSION+':COMPOSITE';result.at[i,'source_sha256']=sha(encode({'prior':str(row.get('source_sha256')),'packets':sorted(v['sha256'] for v in config['packets'].values())}));actions[(row.target,action)]=actions.get((row.target,action),0)+1
 require(len(result)==len(strict) and result[KEY].equals(strict[KEY]),'POPULATION_CHANGED')
 return result,{'version':VERSION,'newlabelversion':True,'actions':[{'target':t,'action':a,'rows':n} for (t,a),n in actions.items()],'accepted_claim_keys':len(claims),'rejected_claims':len(rejected),'packet_conflicting_keys':len(blocked),'unchanged_population_rows':len(result),'Thursday_401873010':'No old13gameclaims assumed; strictcachefields only','fits_HTTP_inference':0},evidence
def execute(strict,queries,packet_bytes,finality_bytes,freeze_bytes,config,go):
 require(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root' and go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('config_sha256')==sha(encode(config)),'EXACT_GO_REQUIRED')
 freeze=decode(freeze_bytes,config['forecast_freeze']);require(freeze.get('forecast_readback_verified') is True and freeze.get('state')==config['required_forecast_freeze_state'],'FORECAST_FREEZE_REQUIRED')
 for spec in config['packets'].values():require(spec['kind'] in ['QB','NON'] and spec.get('qualification_complete') is True and re.fullmatch('[0-9a-f]{64}',str(spec.get('completion_receipt_sha256'))) is not None,'ORIGINAL_COMPLETION_ADMISSION_REQUIRED')
 finality=decode(finality_bytes,config['finality']);packets={name:decode(packet_bytes[name],spec) for name,spec in config['packets'].items()}
 return supplement(strict,queries,finality,packets,config)
