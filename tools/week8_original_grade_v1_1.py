"""Grade immutable Week 8 decisions; no fitting or retrospective pick replacement."""
from __future__ import annotations
import collections,datetime,gzip,hashlib,io,json,math,random,resource,signal,statistics,sys,time,zipfile
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
CATS=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','chart_ppr','rec_tgt']
NUMERIC=set(CATS)-{'anytime_td','chart_ppr'}|{'fpts'}
COUNT={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','rec_tgt'}
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def instant(x):
 try:return datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
 except (ValueError,TypeError,AttributeError):return None
def value_grade(side,y,line):
 if side not in ('over','under'):return 'ABSTAIN'
 a,b=Decimal(str(y)),Decimal(str(line))
 return 'PUSH' if a==b else 'WIN' if (a>b if side=='over' else a<b) else 'LOSS'
def run():
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(180,181));resource.setrlimit(resource.RLIMIT_AS,(1024**3,)*2);signal.alarm(360)
 sys.path.insert(0,str(ROOT));from tools import category_topfive_matched12_storage_v1 as st
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 folder=store.forward_root/'research'/'week8-original-grade-v2-batch-20261102'
 receipt=json.loads((ROOT/'reports/week8-original-grading-20261102/SOURCE_CAPTURE_V2.json').read_text());archive=folder/'SOURCES.zip';store.validate_reference(archive,receipt['archive']['sha256'])
 with zipfile.ZipFile(archive) as z:
  manifest=json.loads(z.read('MEMBER_MANIFEST.json'));raw={}
  for n,r in manifest.items():
   b=z.read(n);assert len(b)==r['bytes'] and sha(b)==r['sha256'];raw[n]=b
 def load(name):return json.loads(raw[name+'.bin'])
 assert all(x['status']=='CAPTURED' for x in receipt['refs'] if x['id'] in ['archive_pre_first','espn_finality','sleeper_stats']), 'Required source unavailable; retain failure, no final scoring'
 espn=load('espn_finality');assert espn.get('season',{}).get('year')==2026;assert espn.get('season',{}).get('type')==2;assert espn.get('week',{}).get('number')==8
 fixed=load('archive_pre_first');assert (fixed['season'],fixed['week'])==(2026,8)
 games={g['id']:g for g in fixed['games']};assert len(games)==14
 eventmap={str(e['id']):e for e in espn.get('events',[])};finals={};statuses=[]
 for gid,g in games.items():
  e=eventmap.get(gid);state='UNRESOLVED_EVENT_MISSING';completed=False
  if e:
   comp=e['competitions'][0];teams={('WAS' if t['team']['abbreviation']=='WSH' else t['team']['abbreviation']) for t in comp['competitors']}
   assert teams=={g['home'],g['away']},'Event team identity mismatch'
   status=comp.get('status',e.get('status',{})).get('type',{});completed=status.get('completed') is True and status.get('state')=='post';state='FINAL' if completed else status.get('state','UNKNOWN')
   if completed:finals[gid]=True
  statuses.append({'game_id':gid,'home':g['home'],'away':g['away'],'kickoff_UTC':g['kickoff'],'state':state,'final':completed})
 original=load('sleeper_stats');assert isinstance(original,list),'Unexpected actual-stat source contract'
 stats={};duplicates=[];provider_to_espn={};espn_to_provider={}
 for entry in original:
  assert entry.get('season') in (2026,'2026') and entry.get('week')==8 and entry.get('season_type')=='regular' and entry.get('category')=='stat'
  matched=[gid for gid,g in games.items() if {entry.get('team'),entry.get('opponent')}=={g['home'],g['away']}]
  assert len(matched)==1,'Actual source reciprocal-team identity missing'
  gid=matched[0];provider=str(entry['game_id'])
  assert provider_to_espn.setdefault(provider,gid)==gid and espn_to_provider.setdefault(gid,provider)==provider,'Provider game-ID collision'
  pid=str(entry.get('player_id',''))
  if not pid:continue
  if pid in stats and enc(stats[pid])!=enc(entry):duplicates.append(pid)
  else:stats[pid]=entry
 for pid in duplicates:stats.pop(pid,None)
 assert set(provider_to_espn.values())<=set(finals),'Actual totals include nonfinal game; quarantine before scoring'
 zero_counts=collections.Counter()
 def actual(pid,gid,team,cat):
  if gid not in finals:return None,'PENDING','GAME_NOT_QUALIFIED_FINAL'
  g=games.get(gid)
  if not g or team not in (g['home'],g['away']):return None,'UNRESOLVED','GAME_TEAM_IDENTITY'
  other=g['away'] if team==g['home'] else g['home'];e=stats.get(str(pid))
  if not e:return None,'UNRESOLVED','MISSING_ACTUAL_PLAYER_ROW'
  if e.get('team')!=team or e.get('opponent',e.get('opp'))!=other:return None,'UNRESOLVED','ACTUAL_TEAM_OPPONENT_MISMATCH'
  s=e.get('stats');
  if not isinstance(s,dict):return None,'UNRESOLVED','MISSING_STATISTICS'
  played=finite(s.get('gp')) and s['gp']>0 or finite(s.get('off_snp')) and s['off_snp']>0
  dnp=e.get('participation_status')=='dnp' and bool(e.get('participation_source'))
  if played and dnp:return None,'UNRESOLVED','CONTRADICTORY_PARTICIPATION'
  if dnp:return None,'DNP','ATTRIBUTED_DNP_NOT_ASSUMED_VOID'
  if not played:return None,'UNRESOLVED','UNKNOWN_PARTICIPATION'
  if cat=='chart_ppr':return None,'UNRESOLVED','EXACT_CHART_RARE_COMPONENT_LABELS_UNQUALIFIED'
  keys=['rush_yd','rec_yd'] if cat=='rush_rec_yd' else ['rush_td','rec_td'] if cat=='anytime_td' else ['pts_ppr'] if cat=='fpts' else [cat]
  vals=[];omitted=False
  for key in keys:
   if key in s:
    if not finite(s[key]):return None,'UNRESOLVED','EXPLICIT_NULL_OR_INVALID_STAT'
    vals.append(s[key])
   elif cat=='fpts':return None,'UNRESOLVED','LEGACY_PROVIDER_PPR_UNAVAILABLE'
   else:vals.append(0);omitted=True
  y=sum(vals)
  if cat=='anytime_td':y=int(y>0)
  if cat in COUNT and (y<0 or int(y)!=y):return None,'UNRESOLVED','COUNT_SUPPORT_VIOLATION'
  if omitted:zero_counts[cat]+=1
  return y,'SUPPORTED','COMPACT_PROVIDER_ZERO_AFTER_FINAL_PLAYED_IDENTITY' if omitted else 'EXPLICIT_PROVIDER_STAT'
 records=[];numerical=[];capture_inventory=[]
 def decision(group,cohort,pid,gid,team,cat,side,line,point,method,policy,issue,capture,extra=None):
  y,status,reason=actual(pid,gid,team,cat)
  state=value_grade(side,y,line) if status=='SUPPORTED' and finite(line) else status if status!='SUPPORTED' else 'UNRESOLVED'
  record={'group':group,'cohort':cohort,'season':2026,'week':8,'player_id':str(pid),'game_id':str(gid),'team':team,'category':cat,'side':side,'line':line,'point':point if finite(point) else None,'actual':y,'result':state,'actual_reason':reason,'method':method,'policy':policy,'issue_time':issue,'capture_id':capture,'statistical_direction':None if y is None or not finite(line) else 'EXACT_LINE' if Decimal(str(y))==Decimal(str(line)) else 'ABOVE_LINE' if Decimal(str(y))>Decimal(str(line)) else 'BELOW_LINE','venue_settlement':'UNVERIFIED','absolute_error':abs(point-y) if finite(point) and y is not None else None}
  if extra:record.update(extra)
  records.append(record)
 def point_record(group,pid,gid,team,cat,point,method,product,issue,capture,extra=None):
  y,status,reason=actual(pid,gid,team,cat)
  r={'group':group,'player_id':str(pid),'game_id':str(gid),'team':team,'category':cat,'point':point,'actual':y,'status':status,'reason':reason,'method':method,'product':product,'issue_time':issue,'capture_id':capture}
  if extra:r.update(extra)
  numerical.append(r)
 def archive_decisions(group,a):
  players={p['id']:p for p in a['players']};seen=set()
  for p in a['players']:
   for q in p.get('props',[]):
    cat=q['key'];method=q.get('model_version') or p.get('reference_model') or 'UNKNOWN_LEGACY_ATTRIBUTION';policy=q.get('policy_version') or 'UNKNOWN_ORIGINAL_POLICY_VERSION'
    if finite(q.get('adj')) and not p.get('late') and cat in NUMERIC:point_record(group,p['id'],p['game_id'],p['team'],cat,q['adj'],method,'legacy_adjusted_empirical_point',None,group,{'archive_saved_at':a['saved_at'],'issue_time_reason':'Original model issuance unretained; saved archive exists before first kickoff for fixed primary snapshot'})
    if q.get('lean') not in ('over','under') or q.get('line_from') not in ('dk','sleeper') or cat=='anytime_td':continue
    key=(p['id'],p['game_id'],cat,q['lean'],q.get('line'));assert key not in seen,'Duplicate original lean';seen.add(key)
    decision(group,'ALL_RECORDED_LEANS',p['id'],p['game_id'],p['team'],cat,q['lean'],q.get('line'),q.get('adj'),method,policy,None,group,{'archive_saved_at':a['saved_at'],'issue_time_reason':'Archive existence clock is not original model issuance','line_from':q.get('line_from'),'original_late':bool(p.get('late'))})
    if p.get('late'):records[-1]['result']='EXCLUDED_LATE'
  for side in ('over','under'):
   for rank,q in enumerate(a['picks'].get(side,[]),1):
    p=players.get(q['player_id']);assert p is not None and p['game_id']==q['game_id']
    if q.get('line_from') not in ('dk','sleeper'):continue
    decision(group,'ORIGINAL_TOP_PICKS',p['id'],p['game_id'],p['team'],q['key'],side,q.get('line'),q.get('adj'),q.get('model_version') or p.get('reference_model') or 'UNKNOWN_LEGACY_ATTRIBUTION',q.get('policy_version') or 'UNKNOWN_ORIGINAL_POLICY_VERSION',None,group,{'rank':rank,'archive_saved_at':a['saved_at'],'issue_time_reason':'Archive existence clock is not original model issuance','line_from':q.get('line_from')})
    if p.get('late'):records[-1]['result']='EXCLUDED_LATE'
 archive_decisions('ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF',fixed)
 archive_decisions('ARCHIVE_OCT30_RECONCILIATION',load('archive_prior'))
 archive_decisions('CURRENT_ARCHIVE_SEPARATE_SNAPSHOT',load('archive_current'))
 for ref in receipt['refs']:
  sid=ref['id']
  if ref['status']!='CAPTURED':continue
  if sid.startswith('classic_'):
   container=json.loads(gzip.decompress(raw[sid+'.bin']));d=container['payload'];assert sha(json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==container['payload_sha256'] or sha(enc(d))==container['payload_sha256']
   issue=d['forecast_generated_at'];capt=d['captured_at'];rows=d['rows'];group='CLASSIC_CAPTURE_'+capt+'_'+container['payload_sha256'][:10];valid=0;rejected=0
   for r in rows:
    if r.get('season')!=2026 or r.get('week')!=8 or not instant(issue) or not instant(capt) or not instant(r.get('kickoff')) or not instant(issue)<=instant(capt)<instant(r['kickoff']):rejected+=1;continue
    valid+=1;cat=r['category'];point=r.get('adjusted_projection');method=d['model'];policy='ORIGINAL_CAPTURED_LEAN'
    if finite(point) and cat in NUMERIC:point_record(group,r['player_id'],r['game_id'],r['team'],cat,point,method,'classic_adjusted_empirical_point',issue,sid)
    if r.get('lean') in ('over','under') and r.get('line_from') in ('dk','sleeper') and cat!='anytime_td':
     decision(group,'ALL_RECORDED_LEANS',r['player_id'],r['game_id'],r['team'],cat,r['lean'],r['line'],point,method,policy,issue,sid,{'line_from':r['line_from']})
     assert not (r.get('top_over') and r.get('top_under')),'Contradictory original top flags'
     if r.get('top_'+r['lean']):decision(group,'ORIGINAL_TOP_PICKS',r['player_id'],r['game_id'],r['team'],cat,r['lean'],r['line'],point,method,policy,issue,sid)
   capture_inventory.append({'source':sid,'group':group,'model':d['model'],'issued_UTC':issue,'captured_UTC':capt,'rows':len(rows),'pregame_rows':valid,'rejected_timing_scope_rows':rejected,'games':len({r['game_id']for r in rows}),'actual_source_timing_verified':False,'not_research_primary_assignment':True})
  if sid.startswith('rank_'):
   d=load(sid)
   if (d.get('season'),d.get('week'))!=(2026,8):
    capture_inventory.append({'source':sid,'excluded':True,'reason':'OUTSIDE_2026_WEEK8','season':d.get('season'),'week':d.get('week')});continue
   group='RECORDED_SELECTED_RANKING_'+d['prepared_at'];n=0;late=0
   for side in ('over','under'):
    for rank,r in enumerate(d['picks'].get(side,[]),1):
     gid=r['game_id'];g=games.get(gid);team=next((p['team'] for p in fixed['players'] if p['id']==r['player_id'] and p['game_id']==gid),None)
     decision(group,'ORIGINAL_TOP_PICKS',r['player_id'],gid,team,r['key'],side,r.get('line'),r.get('adj'),r.get('model_version') or 'UNKNOWN',d['policy'].get('version'),None,sid,{'rank':rank,'document_prepared_at':d['prepared_at'],'original_selection_time':r.get('selected_at'),'selection_clock_basis':'Original selected_at if present, else document existence timestamp; neither is model issuance','forecast_source':r.get('forecast_source'),'line_from':r.get('line_from'),'original_selected_row_sha256':r.get('selected_row_sha256')})
     when=instant(r.get('selected_at')) or instant(d['prepared_at'])
     if not g or not when or when>=instant(g['kickoff']):records[-1]['result']='UNQUALIFIED_TIMING';late+=1
     else:n+=1
   capture_inventory.append({'source':sid,'group':group,'policy':d['policy'].get('version'),'rows':sum(len(d['picks'].get(s,[]))for s in ('over','under')),'pregame_selected_at_rows':n,'unqualified_timing_rows':late,'prepared_at':d['prepared_at'],'horizon_rule':'Namedrecordeddocument;notposthocbestissuance'})
 # Saved selected model points; directions below are explicitly new rule replays,
 # outside the original recommendation headline. Different payloads stay separate.
 probability_rows=[];fixed_players={(p['id'],p['game_id']):p for p in fixed['players']}
 offers={(p['id'],p['game_id'],q['key']):q for p in fixed['players'] for q in p['props'] if q.get('line_from')in('dk','sleeper')}
 for ref in receipt['refs']:
  if not ref['id'].startswith('selected_') or ref['status']!='CAPTURED':continue
  d=load(ref['id']);assert (d.get('season'),d.get('week'))==(2026,8);group='CAPTURED_SELECTED_'+ref['id'][9:21];valid=0;missing_identity=0;unqualified=0;offer_matches=0
  for r in d['rows']:
   p=fixed_players.get((r['player_id'],r['game_id']));issue=instant(r.get('issued_at'));persist=instant(r.get('persistence_completed_at'));kick=instant(r.get('kickoff_utc'))
   if not p:missing_identity+=1;continue
   if not issue or not persist or not kick or not issue<=persist<kick:unqualified+=1;continue
   valid+=1;cat=r['category'];point=r['forecast_value'];method='P2_SELECTED:'+r['model_version'];product=r.get('prediction_functional',r['product'])
   if cat in NUMERIC and finite(point):point_record(group,r['player_id'],r['game_id'],p['team'],cat,point,method,product,r['issued_at'],ref['id'],{'procedure_version':r['procedure_version'],'persistence_completed_at':r['persistence_completed_at'],'source_cutoff_field_is_declared_deadline_not_actual_capture':True})
   if cat=='anytime_td' and r['product']=='binary_probability' and finite(point) and 0<=point<=1:
    y,status,reason=actual(r['player_id'],r['game_id'],p['team'],cat);probability_rows.append({'group':group,'method':method,'game_id':r['game_id'],'player_id':r['player_id'],'probability':point,'actual':y,'status':status,'reason':reason,'Brier':(point-y)**2 if y is not None else None})
   q=offers.get((r['player_id'],r['game_id'],cat))
   if q and finite(point) and finite(q.get('line')) and cat!='anytime_td':
    offer_matches+=1;side='over'if Decimal(str(point))>Decimal(str(q['line']))else'under'if Decimal(str(point))<Decimal(str(q['line']))else'abstain'
    decision(group,'RETROSPECTIVE_POINT_DIRECTION_REPLAY',r['player_id'],r['game_id'],p['team'],cat,side,q['line'],point,method,'P1_UNROUNDED_POINT_GT_LT_ORIGINAL_LINE',r['issued_at'],ref['id'],{'procedure_version':r['procedure_version'],'original_website_selection':False,'line_from':q['line_from']})
  capture_inventory.append({'source':ref['id'],'group':group,'rows':len(d['rows']),'qualified_pregame_rows':valid,'missing_frozen_player_identity':missing_identity,'unqualified_clock_rows':unqualified,'matched_original_offers':offer_matches,'new_MAE_profile':False,'not_research_primary_assignment':True})
 # Emit all supported source/score details before any aggregate ranking.
 def summary(rs):
  def side(s):
   rows=[r for r in rs if r['side']==s];c=collections.Counter(r['result']for r in rows);n=c['WIN']+c['LOSS'];return {'wins':c['WIN'],'losses':c['LOSS'],'decided':n,'hit_rate':c['WIN']/n if n else None,'pending':c['PENDING'],'unresolved':sum(v for k,v in c.items() if k in ('UNRESOLVED','UNQUALIFIED_TIMING')),'push':c['PUSH'],'void':c['VOID'],'dnp':c['DNP'],'excluded':c['EXCLUDED_LATE'],'observed':len(rows)}
  o,u=side('over'),side('under');w=o['wins']+u['wins'];l=o['losses']+u['losses'];return {'over':o,'under':u,'combined':{'wins':w,'losses':l,'decided':w+l,'hit_rate':w/(w+l) if w+l else None},'abstentions':sum(r['side']=='abstain' for r in rs),'unique_games':len({r['game_id']for r in rs}),'unique_player_games':len({(r['player_id'],r['game_id'])for r in rs}),'decisive_games':len({r['game_id']for r in rs if r['result']in ('WIN','LOSS')})}
 tables=[]
 for group,cohort in sorted({(r['group'],r['cohort'])for r in records}):
  for cat in CATS:
   rs=[r for r in records if (r['group'],r['cohort'],r['category'])==(group,cohort,cat)]
   if rs or group=='ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF':tables.append({'group':group,'cohort':cohort,'category':cat,**summary(rs),'missing_reason':None if rs else 'TARGET_OFFER_UNAVAILABLE' if cat=='rec_tgt' else 'NO_COMPATIBLE_CHART_OR_EVENT_OFFER' if cat in ('chart_ppr','anytime_td') else 'NO_RECORDED_QUALIFYING_SELECTION'})
 metrics=[]
 for group,method,cat,product in sorted({(r['group'],r['method'],r['category'],r['product'])for r in numerical}):
  allrows=[r for r in numerical if (r['group'],r['method'],r['category'],r['product'])==(group,method,cat,product)];rs=[r for r in allrows if r['status']=='SUPPORTED' and finite(r['point'])];err=[r['point']-r['actual']for r in rs];ab=sorted(abs(e)for e in err);n=len(err)
  metrics.append({'group':group,'method':method,'category':cat,'product':product,'planned':len(allrows),'scored':n,'pending':sum(r['status']=='PENDING'for r in allrows),'unresolved':sum(r['status']=='UNRESOLVED'for r in allrows),'MAE':sum(ab)/n if n else None,'MSE':sum(e*e for e in err)/n if n else None,'RMSE':math.sqrt(sum(e*e for e in err)/n) if n else None,'bias':sum(err)/n if n else None,'p90_AE':ab[min(n-1,int(.9*n))]if n else None,'p95_AE':ab[min(n-1,int(.95*n))]if n else None,'games':len({r['game_id']for r in rs})})
 asof=datetime.datetime.now(datetime.timezone.utc);public={'version':'week8-original-grading-v1.1','grading_timestamp_UTC':asof.isoformat(),'grading_timestamp_America_Chicago':asof.astimezone(ZoneInfo('America/Chicago')).isoformat(),'season':2026,'NFL_week':8,'week_complete':False,'schedule':statuses,'completed_games':len(finals),'expected_games':len(games),'source_receipt':'SOURCE_CAPTURE_V2.json','original_archive_commit':'911a81a31f822de58e0f9c04ded070f8c9752670','original_archive_saved_at':fixed['saved_at'],'tables':tables,'numerical_metrics':metrics,'capture_inventory':capture_inventory,'actual_stats_player_rows':len(stats),'ambiguous_actual_player_rows':len(duplicates),'omitted_zero_uses':dict(zero_counts),'scope':'Originalstoredsides;namedissuancesseparate;statisticaldirectionnotvenueprofit;legacyPPRnotchart;noMAEreleaseclaim','probability_scores':None,'probability_missing_reason':'Separateexact-lawandlabelqualificationrequired;pointforecastsarenotprobabilities','no_new_fits_inference':True,'actual_CPU_seconds_before_persistence':time.process_time()-cpu,'actual_wall_seconds_before_persistence':time.monotonic()-start}
 public['probability_results']=[{'group':group,'method':method,'planned':len(allrows),'scored':len(rs),'Brier':sum(r['Brier']for r in rs)/len(rs)if rs else None,'pending':sum(r['status']=='PENDING'for r in allrows),'unresolved':sum(r['status']=='UNRESOLVED'for r in allrows),'scope':'Played-final sparse-provider RRTD event;no offered ATD price or new probability model'} for group,method in sorted({(r['group'],r['method'])for r in probability_rows}) for allrows in [[r for r in probability_rows if (r['group'],r['method'])==(group,method)]]for rs in [[r for r in allrows if r['status']=='SUPPORTED']]]
 public['provider_game_crosswalk']=[{'provider_game_id':k,'canonical_ESPN_id':v,'season':2026,'week':8}for k,v in sorted(provider_to_espn.items())]
 private={'decisions':records,'numerical':numerical,'probabilities':probability_rows};out=folder/'GRADING_V1_1.zip';assert not out.exists();members={'SCORECARD.json.gz':gzip.compress(enc(private),mtime=0),'AGGREGATES.json':enc(public)};members['MEMBER_MANIFEST.json']=enc({n:{'sha256':sha(b),'bytes':len(b)}for n,b in members.items()});buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED)as z:
  for n,b in members.items():z.writestr(n,b)
 body=buf.getvalue();store.write_bytes(out,body);v=store.validate_reference(out,sha(body));public['private_scorecard_manifest']={'artifact_id':'A-WEEK8-ORIGINAL-GRADE-V1','sha256':v['sha256'],'bytes':v['bytes'],'decision_rows':len(records),'numeric_rows':len(numerical),'offhost_restore':'NOT_VERIFIED'}
 (ROOT/'reports/week8-original-grading-20261102/RESULTS_V1.json').write_bytes(enc(public));print(json.dumps({'state':'COMPLETE_NAMED_ORIGINAL_ARCHIVE_GRADING_PARTIAL_WEEK','completed_games':len(finals),'expected_games':14,'decision_rows':len(records),'numeric_rows':len(numerical),'private_scorecard':public['private_scorecard_manifest'],'CPU_seconds':time.process_time()-cpu}))
if __name__=='__main__':run()
