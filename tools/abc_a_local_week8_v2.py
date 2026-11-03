"""Append finality-bound grades and local exact-board controls; never a shared scorer."""
import collections, datetime, gzip, hashlib, io, json, math, resource, signal, sys, time, urllib.request, zipfile
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/abc-championship'
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
 resource.setrlimit(resource.RLIMIT_CPU,(300,301));signal.alarm(600);cpu=time.process_time()
 sys.path.insert(0,str(ROOT))
 from tools import category_topfive_matched12_storage_v1 as storage
 from tools.week8_original_grade_v1_1 import value_grade,finite
 store,_=storage.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=storage.GO)
 base=store.forward_root/'research'/'week8-original-grade-v2-batch-20261102'
 def restored(name,sha,member):
  store.validate_reference(base/name,sha)
  with zipfile.ZipFile(base/name)as z:return z.read(member)
 fixed=json.loads(restored('SOURCES.zip','6290b6a501ac5adf33ce693c2c4dc92d5f371ffdc3e6c6ba1da83ca6d1b623c5','archive_pre_first.bin'))
 parent=json.loads(gzip.decompress(restored('GRADING_V1_1.zip','22099b3ebb6d6337100a5e38dbb5df5d34266ccda62a1f195af674f015157876','SCORECARD.json.gz')))
 r0=json.loads(gzip.decompress(restored('COMPLETION_V1.zip','bac6a5f39739517502ffe5ced5a33587a3f3bd5a84307ca18cfef08aa4c55493','R0_SCORECARD.json.gz')))
 fresh={};refs=[]
 sources=json.loads((ROOT/'config/week8-original-grade-capture-v2.json').read_text())['sources']
 for r in sources:
  if r['id']not in ('espn_finality','sleeper_stats'):continue
  with urllib.request.urlopen(r['url'],timeout=30)as response:b=response.read(2097153)
  assert len(b)<=2097152
  fresh[r['id']]=b;refs.append({'id':r['id'],'url':r['url'],'sha256':digest(b),'bytes':len(b),'received_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 espn=json.loads(fresh['espn_finality']);assert espn['season']['year']==2026 and espn['season']['type']==2 and espn['week']['number']==8
 games={g['id']:g for g in fixed['games']};events={str(e['id']):e for e in espn['events']};final=set();schedule=[]
 for gid,g in games.items():
  event=events.get(gid);comp=event['competitions'][0]if event else None
  if comp:
   teams={t['team']['abbreviation'].replace('WSH','WAS')for t in comp['competitors']};assert teams=={g['home'],g['away']}
   s=comp.get('status',event.get('status',{}))['type'];done=s.get('completed')is True and s.get('state')=='post'
  else:done=False
  if done:final.add(gid)
  schedule.append({'game_id':gid,'home':g['home'],'away':g['away'],'final':done})
 stats={};cross={};back={}
 for e in json.loads(fresh['sleeper_stats']):
  assert e['season']in(2026,'2026')and e['week']==8 and e['season_type']=='regular'and e['category']=='stat'
  ids=[gid for gid,g in games.items()if {g['home'],g['away']}=={e.get('team'),e.get('opponent')}];assert len(ids)==1
  gid=ids[0];pg=str(e['game_id']);assert cross.setdefault(pg,gid)==gid and back.setdefault(gid,pg)==pg
  key=(str(e['player_id']),gid);assert key not in stats or stats[key]==e;stats[key]=e
 counts={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','rec_tgt'}
 def outcome(r):
  gid=r['game_id'];pid=str(r['player_id']);cat=r['category']
  if gid not in final:return None,'PENDING','GAME_NOT_FINAL'
  e=stats.get((pid,gid))
  if not e:return None,'UNRESOLVED','MISSING_ACTUAL_PLAYER_ROW'
  if r.get('team')and e['team']!=r['team']:return None,'UNRESOLVED','TEAM_MISMATCH'
  s=e.get('stats',{});played=(finite(s.get('gp'))and s['gp']>0)or(finite(s.get('off_snp'))and s['off_snp']>0)
  if not played:return None,'UNRESOLVED','UNKNOWN_PARTICIPATION'
  if cat=='chart_ppr':return None,'UNRESOLVED','EXACT_CHART_COMPONENTS_UNQUALIFIED'
  keys=['rush_yd','rec_yd']if cat=='rush_rec_yd'else['rush_td','rec_td']if cat=='anytime_td'else['pts_ppr']if cat=='fpts'else[cat]
  if any(k in s and not finite(s[k])for k in keys):return None,'UNRESOLVED','EXPLICIT_NULL_OR_INVALID_STAT'
  if cat=='fpts'and keys[0]not in s:return None,'UNRESOLVED','LEGACY_PPR_MISSING'
  omitted=any(k not in s for k in keys);y=sum(s.get(k,0)for k in keys)
  if cat=='anytime_td':y=int(y>0)
  if cat in counts:assert y>=0 and int(y)==y
  return y,'SUPPORTED','COMPACT_PROVIDER_ZERO_AFTER_FINAL_PLAYED_IDENTITY'if omitted else'EXPLICIT_PROVIDER_STAT'
 def append_grade(r):
  a,s,reason=outcome(r);n={**r,'actual':a,'status':s,'reason':reason}
  if 'side'in r:n['result']=value_grade(r['side'],a,r['line'])if s=='SUPPORTED'else s
  return n
 original=parent['decisions']+r0['decisions'];graded=[append_grade(r)for r in original]
 numeric=[append_grade(r)for r in parent['numerical']+r0['numerical']]
 def summarize(rows):
  out=[]
  for category in sorted({r['category']for r in rows}):
   rs=[r for r in rows if r['category']==category];d={'category':category,'selected':len(rs),'games':len({r['game_id']for r in rs}),'player_games':len({(r['player_id'],r['game_id'])for r in rs})}
   for side in ('over','under','combined'):
    ss=rs if side=='combined'else[r for r in rs if r['side']==side];c=collections.Counter(r['result']for r in ss);n=c['WIN']+c['LOSS'];d[side]={'wins':c['WIN'],'losses':c['LOSS'],'decided':n,'rate':c['WIN']/n if n else None,'states':dict(c)}
   out.append(d)
  return out
 headlines={}
 for group,cohort in [('ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF','ALL_RECORDED_LEANS'),('ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF','ORIGINAL_TOP_PICKS'),('RECORDED_SELECTED_RANKING_2026-10-28T22:55:49.911448+00:00','ORIGINAL_TOP_PICKS')]:
  headlines[group+'|'+cohort]=summarize([r for r in graded if r['group']==group and r['cohort']==cohort])
 # Full original eligible board, including originally unselected offers. No outcome-based offer selection.
 board={}
 for p in fixed['players']:
  for q in p['props']:
   if q.get('line_from')not in('dk','sleeper')or not finite(q.get('line'))or p.get('late'):continue
   k=(str(p['id']),p['game_id'],q['key']);assert k not in board;board[k]={'player_id':k[0],'game_id':k[1],'category':k[2],'team':p['team'],'line':q['line'],'line_from':q['line_from']}
 groups=['FIXED_R0_CAPTURE_20261028T184637Z','CAPTURED_SELECTED_369fec9caec0'];vectors={g:{(r['player_id'],r['game_id'],r['category']):r for r in numeric if r['group']==g}for g in groups}
 core=sorted(set(board)&set(vectors[groups[0]])&set(vectors[groups[1]]));decisions=[];comparison=[]
 for k in core:
  r=board[k];y,status,reason=outcome(r)
  for g in groups+['CONTROL_ALWAYS_OVER','CONTROL_ALWAYS_UNDER']:
   point=vectors[g][k]['point']if g in vectors else None
   side=('over'if g.endswith('OVER')else'under')if g not in vectors else'over'if point>r['line']else'under'if point<r['line']else None
   decisions.append({**r,'group':g,'point':point,'side':side,'actual':y,'status':status,'result':value_grade(side,y,r['line'])if status=='SUPPORTED'else status,'reason':reason})
 for g in groups+['CONTROL_ALWAYS_OVER','CONTROL_ALWAYS_UNDER']:
  comparison.extend(dict(r,procedure_id=g)for r in summarize([r for r in decisions if r['group']==g]))
 now=datetime.datetime.now(datetime.timezone.utc);report={'version':'A-LOCAL-W8-EXACT-BOARD-v2','common_championship':False,'canonical_parity':'AWAITING_C_V2_PROTOCOL_AND_ADMISSION','period_id':'2026_W8_ONLY','asof_UTC':now.isoformat(),'asof_America_Chicago':now.astimezone(ZoneInfo('America/Chicago')).isoformat(),'final_games':len(final),'expected_games':len(games),'schedule':schedule,'sources':refs,'headlines':headlines,'local_matched_results':comparison,'common_outer_offers':len(core),'common_opportunity_keys_independent_of_model':True,'new_fits_inference':0,'grade_status_changes':sum(a.get('result')!=b.get('result')for a,b in zip(original,graded)),'limits':['Actual full saved board; original quote timestamp/venue settlement unverified','R0 and selected issues differ105minutes; complete-system descriptive comparison, not isolated learner or shared horizon parity','No W1-7/W8 concatenated original pregame claim','No P2 law manufactured; ATD/PPR actual offers unavailable','Nominal week8-only cluster uncertainty; not multiweek confirmation']}
 members={**{k+'.json':v for k,v in fresh.items()},'GRADED_ROWS.json.gz':gzip.compress(enc({'decisions':graded,'numerical':numeric,'board_comparison':decisions}),mtime=0),'REPORT.json':enc(report)}
 members['MANIFEST.json']=enc({n:{'sha256':digest(b),'bytes':len(b)}for n,b in members.items()});buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED)as z:
  for n,b in members.items():z.writestr(n,b)
 data=buf.getvalue();assert len(data)<4194304;target=base/'A_LOCAL_WEEK8_REGRADING_V2_20261103.zip';assert not target.exists();store.write_bytes(target,data);store.validate_reference(target,digest(data))
 report['private_evidence']={'artifact_id':'A-LOCAL-W8-REGRADING-V2-20261103','sha256':digest(data),'bytes':len(data),'readback':'PASS_SAME_STORE','offhost_restore':'NOT_VERIFIED','route':'Existing approved A private owner-controlled restoration; no shared-public row export'};report['CPU_seconds']=time.process_time()-cpu
 (OUT/'LOCAL_WEEK8_RESULTS_V2.json').write_bytes(enc(report));print(json.dumps({'state':'COMPLETE_LOCAL_ONLY','final_games':len(final),'core_offers':len(core),'CPU_seconds':report['CPU_seconds'],'artifact':report['private_evidence']}))
if __name__=='__main__':main()
