"""Source-specific recorded-threshold replay using pinned C scorer and saved A rows."""
import collections,csv,datetime,gzip,hashlib,io,json,math,subprocess,sys,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/abc-championship/reconciliation-v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def normid(v):
 if v is None:return ''
 s=str(v);return s[:-2]if s.endswith('.0')else s

def team(v):return {'LA':'LAR','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LAR'}.get(v,v)
def main():
 import pyarrow.parquet as pq
 cpu=time.process_time();sys.path.insert(0,'/tmp/abc-period-continuation-20261103/C/src');import abc_championship_v2 as c
 r=subprocess.run(['gh','api','repos/NickNicky19/nicks-expert-nfl-picks/commits/main','--jq','.sha'],capture_output=True,text=True,timeout=25);assert r.returncode==0;commit=r.stdout.strip();sources={};archives={};receipts=[]
 for week in (6,7):
  path=f'output/data/archive/2026_w{week:02d}.json';url=f'https://raw.githubusercontent.com/NickNicky19/nicks-expert-nfl-picks/{commit}/{path}'
  try:
   with urllib.request.urlopen(url,timeout=25)as response:b=response.read(1048577)
   assert len(b)<=1048576;j=json.loads(b);assert(j['season'],j['week'])==(2026,week);sources[f'archive_w{week}.json']=b;archives[week]=j;receipts.append({'week':week,'path':path,'commit':commit,'sha256':sha(b),'bytes':len(b),'archive_saved_at':j.get('saved_at'),'players':len(j['players']),'games':len(j['games']),'state':'CAPTURED_RECORDED_THRESHOLDS_QUOTE_LINEAGE_UNVERIFIED'})
  except urllib.error.HTTPError as e:receipts.append({'week':week,'path':path,'commit':commit,'state':'SOURCE_HTTP_FAILURE','HTTP_status':e.code})
 if not archives:
  (OUT/'W6_W7_SOURCE_DISPOSITION_V1.json').write_text(json.dumps({'sources':receipts,'state':'NO_AVAILABLE_ARCHIVE_NO_SCORES'},indent=2)+'\n');return
 cfg=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()));prep=json.loads((ROOT/'config/category-topfive-matched12-primary-preparation-v1.json').read_text())['inputs']
 def authenticated(ref):
  b=Path(ref['path']).read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return b
 roster=pq.read_table(io.BytesIO(authenticated(prep['roster']))).to_pylist();schedules=list(csv.DictReader(io.StringIO(authenticated(prep['schedule']).decode())))
 map_player=collections.defaultdict(set)
 for p in roster:
  if p['season']==2026 and p['week']in(6,7)and p.get('sleeper_id')and p.get('gsis_id'):map_player[(p['week'],team(p['team']),normid(p['sleeper_id']))].add(p['gsis_id'])
 map_game={}
 for g in schedules:
  if g['season']=='2026'and g['game_type']=='REG'and g['week']in('6','7')and g['espn']:
   k=(int(g['week']),normid(g['espn']));assert k not in map_game;map_game[k]=g
 with zipfile.ZipFile(io.BytesIO(authenticated(cfg['frozen_bundle'])))as z:pred=pq.read_table(io.BytesIO(z.read('FORECASTS.parquet'))).to_pylist()
 with zipfile.ZipFile(io.BytesIO(authenticated(cfg['qualified_labels'])))as z:label=pq.read_table(io.BytesIO(z.read(cfg['qualified_labels']['member']))).to_pylist()
 pf={(r['game_id'],r['player_id'],r['target'],r['method'],r['product']):r for r in pred if r['week']in(6,7)};lab={(r['game_id'],r['player_id'],r['target']):r for r in label if r['week']in(6,7)};models=collections.defaultdict(set)
 for r in pred:
  if r['week']in(6,7)and r['target']not in('anytime_td','chart_ppr'):models[r['target']].add((r['method'],r['product'],r['output_procedure_version']))
 rows=[];source_counts=collections.Counter();excluded=collections.Counter();seen=set()
 for week,a in archives.items():
  ag={g['id']:g for g in a['games']}
  for p in a['players']:
   gid=normid(p['game_id']);g=map_game.get((week,gid));ids=map_player.get((week,team(p['team']),normid(p['id'])),set())
   if not g or team(p['team'])not in(team(g['home_team']),team(g['away_team'])):
    excluded['GAME_IDENTITY']+=1;continue
   if len(ids)!=1:excluded['NO_UNIQUE_HISTORICAL_ID_CROSSWALK']+=1;continue
   pid=next(iter(ids));game=g['game_id']
   for q in p['props']:
    cat=q['key'];line=q.get('line')
    if cat not in models:continue
    if q.get('line_from')not in('dk','sleeper')or not isinstance(line,(int,float))or not math.isfinite(line):excluded['NO_RECORDED_LINE']+=1;continue
    if p['pos']not in cfg['primary_roles_by_target'].get(cat,[]):excluded['OUTSIDE_DECLARED_ROLE']+=1;continue
    key=(week,game,pid,cat);assert key not in seen;seen.add(key);source_counts[f"{week}|{cat}|{q['line_from']}"]+=1
    actual=lab.get((game,pid,cat));supported=actual is not None and actual['participation_state']=='played'and actual['outcome_state']in('played_zero','played_nonzero')and actual['actual']is not None and math.isfinite(actual['actual']);y=actual['actual']if supported else None
    for method,product,version in sorted(models[cat])+[('ALWAYS_OVER','control','always-side-v1'),('ALWAYS_UNDER','control','always-side-v1')]:
     f=pf.get((game,pid,cat,method,product));value=f['prediction']if f and math.isfinite(f['prediction'])else None
     side=('OVER'if method=='ALWAYS_OVER'else'UNDER')if method.startswith('ALWAYS_')else c.a.point_side(value,line);side=None if side=='UNAVAILABLE'else side
     status='UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'UNKNOWN_PARTICIPATION'if not supported else'WIN'
     rr={'game_id':game,'player_id':pid,'category':cat,'season':2026,'week':week,'line':line,'actual':y,'appearance':'PLAYED'if supported else'UNKNOWN','selected_side':side,'status':status,'comparator':'STRICT_OVER_UNDER'};rr['status']=c.status(rr)
     rr.update(procedure_id='A::'+version+'::'+method+'::'+product,point=value,original_recorded_side=q.get('lean'),source_line_from=q['line_from'],source_archive_sha256=next(r['sha256']for r in receipts if r['week']==week),A_source_forecast_sha256=f.get('source_forecast_sha256')if f else None,A_fallback=f.get('fallback')if f else None);rows.append(rr)
 groups=collections.defaultdict(list)
 for r in rows:
  for week in ('ALL',str(r['week'])):groups[(r['category'],r['procedure_id'],week)].append(r)
 scores=[]
 for (cat,method,week),rs in sorted(groups.items()):scores.append({'category':cat,'procedure_id':method,'period_id':'A_RECORDED_WEBSITE_THRESHOLDS_W6_W7_V1','week_view':week,'actual_weeks':sorted({r['week']for r in rs}),'requested_weeks':list(range(1,9)),'evidence_tier':'TIMING_AND_BOOKMAKER_SEMANTICS_UNVERIFIED_RECORDED_THRESHOLD_DIAGNOSTIC',**c.summary(rs)})
 report={'state':'EXECUTED_RECORDED_THRESHOLD_DIAGNOSTIC_NOT_AUTHENTICATED_BOOKMARKET','C_protocol':'ABC-ACTUAL-PROP-CHAMPIONSHIP-v2-C-1','C_scorer_sha256':'2ba450f91bb5fac869ce3adde031099390ec70408a91204653869032b49b2bce','sources':receipts,'roster_crosswalk_sha256':prep['roster']['sha256'],'schedule_crosswalk_sha256':prep['schedule']['sha256'],'forecast_capsule_sha256':cfg['frozen_bundle']['sha256'],'label_capsule_sha256':cfg['qualified_labels']['sha256'],'new_fits_inference':0,'unique_recorded_thresholds':len(seen),'source_counts':dict(source_counts),'exclusions':dict(excluded),'scores':scores,'limits':['Archive saved clocks are not quote or original model issuance clocks. dk/sleeper labels do not authenticate bookmaker offers; settlement/prices unavailable.','Full retained board includes originally unselected props; point-rule replay not original selected recommendations.','Expected source-board population includes unresolved/missing forecasts; role and historicalID exclusions explicit.','Separate named W6-W7 diagnostic; no pooling into an authenticated8week or same-horizon actual-prop panel.']}
 sys.path.insert(0,str(ROOT));from tools import category_topfive_matched12_storage_v1 as st
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO);members={**sources,'GRADE_ROWS.json.gz':gzip.compress(json.dumps(rows,separators=(',',':'),allow_nan=False).encode(),mtime=0)};members['MANIFEST.json']=json.dumps({k:{'bytes':len(v),'sha256':sha(v)}for k,v in members.items()},sort_keys=True).encode();buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED)as z:
  for k,v in members.items():z.writestr(k,v)
 b=buf.getvalue();assert len(b)<1048576;target=store.forward_root/'research'/'week8-original-grade-v2-batch-20261102'/'A_W6_W7_RECORDED_THRESHOLD_REPLAY_V1.zip';assert not target.exists();store.write_bytes(target,b);store.validate_reference(target,sha(b));usage=store.verify_retained_checkpoint();report['private_evidence']={'artifact_id':'A-W6-W7-RECORDED-THRESHOLD-REPLAY-V1','sha256':sha(b),'bytes':len(b),'readback':'PASS_SAME_STORE','offhost_restore':'NOT_VERIFIED'};report['CPU_seconds']=time.process_time()-cpu;(OUT/'W6_W7_RECORDED_THRESHOLD_RESULTS_V1.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'weeks':list(archives),'unique_thresholds':len(seen),'method_week_cells':len(scores),'private_bytes':len(b),'CPU_seconds':report['CPU_seconds']}))
if __name__=='__main__':main()
