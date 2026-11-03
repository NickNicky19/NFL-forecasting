"""Independent local A/C replay; public outputs only, no shared-championship claim."""
import collections,csv,datetime,gzip,hashlib,io,json,math,random,urllib.request,zipfile
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/abc-championship'
def main():
 binding=json.loads(gzip.decompress((ROOT/'config/session-ab-private-transport-v1.private.json.gz').read_bytes()));base=Path(binding['destination_root']).parent/'week8-original-grade-v2-batch-20261102'
 def read(file,digest,member,compressed=False):
  b=(base/file).read_bytes();assert hashlib.sha256(b).hexdigest()==digest
  with zipfile.ZipFile(io.BytesIO(b))as z:v=z.read(member)
  return json.loads(gzip.decompress(v)if compressed else v)
 a=read('SOURCES.zip','6290b6a501ac5adf33ce693c2c4dc92d5f371ffdc3e6c6ba1da83ca6d1b623c5','archive_pre_first.bin')
 aa=read('GRADING_V1_1.zip','22099b3ebb6d6337100a5e38dbb5df5d34266ccda62a1f195af674f015157876','SCORECARD.json.gz',True)
 rr=read('COMPLETION_V1.zip','bac6a5f39739517502ffe5ced5a33587a3f3bd5a84307ca18cfef08aa4c55493','R0_SCORECARD.json.gz',True)
 cb=Path('/tmp/abc-discovery-20261103/C_ROWS.csv.gz').read_bytes();assert hashlib.sha256(cb).hexdigest()=='c1a027df3e6a1252f0844379fbdad046be0243087f7598d3adeb7727395847da'
 c=list(csv.DictReader(io.StringIO(gzip.decompress(cb).decode())))
 def key(name,gid,team):return(name.casefold().strip(),str(gid),team)
 players={key(p['name'],p['game_id'],p['team']):p for p in a['players']};assert len(players)==len(a['players'])
 av={g:{(r['player_id'],r['game_id'],r['category']):r for r in aa['numerical']+rr['numerical']if r['group']==g}for g in ['FIXED_R0_CAPTURE_20261028T184637Z','CAPTURED_SELECTED_369fec9caec0']}
 board={}
 for p in a['players']:
  if p.get('late'):continue
  for q in p['props']:
   if q.get('line_from')in('dk','sleeper')and isinstance(q.get('line'),(int,float)):
    k=(str(p['id']),p['game_id'],q['key']);assert k not in board;board[k]=q['line']
 exclusions=collections.Counter();rows=[];cross={};seen=set();games={g['id']:g for g in a['games']};contradictions=[]
 for r in c:
  if r['category']in('fpts','anytime_td'):continue
  p=players.get(key(r['name'],r['espn_event_id'],r['team']))
  if not p:exclusions['NO_EXACT_NAME_EVENT_TEAM_JOIN']+=1;continue
  if p['pos']!=r['position']or p['opp']!=r['opponent_team']:exclusions['POSITION_OR_OPPONENT_MISMATCH']+=1;continue
  assert cross.setdefault(r['player_id'],p['id'])==p['id'];k=(str(p['id']),p['game_id'],r['category']);assert k not in seen;seen.add(k)
  if k not in board:exclusions['NO_COMPATIBLE_ORIGINAL_LINE']+=1;continue
  if any(k not in v for v in av.values()):exclusions['A_FORECAST_UNAVAILABLE']+=1;continue
  if r['state']!='GRADED_PLAYED' or r['actual']=='':exclusions['C_UNKNOWN_OR_PENDING_ACTUAL']+=1;continue
  y=float(r['actual']);values=[v[k]for v in av.values()]
  if any(v['status']=='SUPPORTED'and float(v['actual'])!=y for v in values):contradictions.append(k);continue
  if not (datetime.datetime.fromisoformat(r['generated_UTC'].replace('Z','+00:00'))<datetime.datetime.fromisoformat(games[k[1]]['kickoff'].replace('Z','+00:00'))):exclusions['C_FORECAST_NOT_PREGAME']+=1;continue
  values={'A_R0_POINT':values[0]['point'],'A_CAPTURED_SELECTED_POINT':values[1]['point'],'C_CAPTURED_MEDIAN':float(r['median']),'C_CAPTURED_MEAN':float(r['mean'])}
  for method,f in values.items():
   line=board[k];side='over'if f>line else'under'if f<line else None;grade='ABSTAIN'if side is None else'PUSH'if y==line else'WIN'if((y>line)==(side=='over'))else'LOSS';rows.append({'method':method,'category':k[2],'game':k[1],'opportunity':k,'side':side,'grade':grade,'point':f,'actual':y,'line':line})
  for method,side in [('ALWAYS_OVER','over'),('ALWAYS_UNDER','under')]:rows.append({'method':method,'category':k[2],'game':k[1],'opportunity':k,'side':side,'grade':'PUSH'if y==board[k]else'WIN'if((y>board[k])==(side=='over'))else'LOSS','point':None,'actual':y,'line':board[k]})
 out=[]
 for cat in sorted({r['category']for r in rows}):
  for method in sorted({r['method']for r in rows}):
   rs=[r for r in rows if r['category']==cat and r['method']==method];n=len(rs);cell={'category':cat,'procedure_output_rule':method,'eligible_common':n,'selected':sum(r['side']is not None for r in rs),'games':len({r['game']for r in rs}),'player_games':n}
   for side in ('over','under','combined'):
    ss=rs if side=='combined'else[r for r in rs if r['side']==side];co=collections.Counter(r['grade']for r in ss);d=co['WIN']+co['LOSS'];cell[side]={'wins':co['WIN'],'losses':co['LOSS'],'decided':d,'rate':co['WIN']/d if d else None,'states':dict(co)}
   err=[r['point']-r['actual']for r in rs if r['point']is not None];cell['MAE']=sum(map(abs,err))/len(err)if err else None;cell['RMSE']=math.sqrt(sum(e*e for e in err)/len(err))if err else None
   out.append(cell)
 # Independent direct boolean partitions reproduce retained grade counts.
 for q in out:
  rs=[r for r in rows if(r['category'],r['method'])==(q['category'],q['procedure_output_rule'])]
  wins=sum((r['side']=='over'and r['actual']>r['line'])or(r['side']=='under'and r['actual']<r['line'])for r in rs);assert wins==q['combined']['wins']
 pairs=[]
 for cat in sorted({r['category']for r in rows}):
  control={r['opportunity']:r for r in rows if r['category']==cat and r['method']=='ALWAYS_UNDER'}
  for method in ['A_R0_POINT','A_CAPTURED_SELECTED_POINT','C_CAPTURED_MEDIAN','C_CAPTURED_MEAN']:
   rs=[r for r in rows if r['category']==cat and r['method']==method];dec=[r for r in rs if r['grade']in('WIN','LOSS')];gs=collections.defaultdict(list)
   for r in dec:gs[r['game']].append(int(r['grade']=='WIN')-int(control[r['opportunity']]['grade']=='WIN'))
   rng=random.Random(20261103);vv=list(gs.values());sample=[]
   for _ in range(1000):
    t=[vv[rng.randrange(len(vv))]for _ in vv];flat=[v for a in t for v in a]
    if flat:sample.append(sum(flat)/len(flat))
   sample.sort();pairs.append({'category':cat,'method':method,'control':'ALWAYS_UNDER','paired_decided':len(dec),'accuracy_change':sum(sum(v)for v in vv)/len(dec)if dec else None,'game_bootstrap95':[sample[25],sample[975]]if len(sample)==1000 else None,'scope':'Nominal one-week exposed sensitivity; selection maxima unadjusted'})
 with urllib.request.urlopen('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week=8&dates=2026',timeout=30)as f:b=f.read(2097152)
 es=json.loads(b);assert es['week']['number']==8 and es['season']['year']==2026;final=sum(e.get('status',{}).get('type',{}).get('completed')is True for e in es['events']);now=datetime.datetime.now(datetime.timezone.utc)
 result={'version':'A-C-LOCAL-ZERO-REFIT-v1','shared_championship':False,'period_id':'2026_W8_C_CAPTURE_OVERLAP_ONLY','canonical_parity':'NOT_ESTABLISHED_C_V2_PROTOCOL_UNPUBLISHED_AT_CHECK','A_commit':'5e6464ba0f2da95647ba302e78f6f08cf05c3e68','C_commit':'2d684f22830b817669ecf89f46eb6fdcace8335b','C_artifact_sha256':hashlib.sha256(cb).hexdigest(),'asof_UTC':now.isoformat(),'asof_America_Chicago':now.astimezone(ZoneInfo('America/Chicago')).isoformat(),'schedule_games':len(es['events']),'schedule_final_games':final,'source_scope':'C immutable graded outcomes, not refreshed full-week A outcomes','rows':out,'paired_changes':pairs,'identity_exclusions':dict(exclusions),'outcome_conflicts_excluded':len(contradictions),'identity_rule':'Exact unique full name + ESPN event + historical team; same position and reciprocal opponent; one-to-one GSIS-to-Sleeper mapping; no fuzzy joins','identity_crosswalk_players':len(cross),'private_pair_rows_published':0,'new_fits_inference':0,'reproduction':'Existing approved private A capsules plus public immutable C csv.gz; public scorer deterministic; private pair scorecard not retained because write guard failed','limits':['LOCAL timing-unverified original-line replay; no shared parity or venue/ROI claim','C mean/median outputs one procedure, not two independent learners','C subset based on positively evidenced participation; unresolved issued rows remain excluded and counted','Different issue clocks/information tiers; complete-system descriptive comparison','Week8 only; no eight-week/historical/TopK or adaptive selector completion']}
 (OUT/'LOCAL_A_C_RESULTS_V1.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'matched_opportunities':len(rows)//6,'method_output_cells':len(out),'final_games_now':final,'conflicts':len(contradictions),'exclusions':dict(exclusions)}))
if __name__=='__main__':main()
