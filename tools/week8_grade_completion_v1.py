"""Evaluator-only append: immutable R0 evidence, uncertainty and report views."""
from __future__ import annotations
import base64,collections,datetime,gzip,hashlib,io,json,math,random,resource,signal,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def run(payload):
 sys.path.insert(0,str(ROOT));from tools import category_topfive_matched12_storage_v1 as st
 from tools.week8_original_grade_v1_1 import value_grade,instant,finite
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(120,121));signal.alarm(240)
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 root=store.forward_root/'research'/'week8-original-grade-v2-batch-20261102';sourcezip=root/'SOURCES.zip';parent=root/'GRADING_V1_1.zip';store.validate_reference(parent,'22099b3ebb6d6337100a5e38dbb5df5d34266ccda62a1f195af674f015157876')
 with zipfile.ZipFile(parent)as z:
  m=json.loads(z.read('MEMBER_MANIFEST.json'))
  for n,v in m.items():assert sha(z.read(n))==v['sha256'] and len(z.read(n))==v['bytes']
  data=json.loads(gzip.decompress(z.read('SCORECARD.json.gz')));ag=json.loads(z.read('AGGREGATES.json'))
 with zipfile.ZipFile(sourcezip)as z:fixed=json.loads(z.read('archive_pre_first.bin'));late=json.loads(z.read('archive_prior.bin'));current=json.loads(z.read('archive_current.bin'))
 originals=data['decisions'];lookup={}
 for r in data['numerical']:
  key=(r['player_id'],r['game_id'],r['category']);v=(r['actual'],r['status'],r['reason'])
  assert lookup.setdefault(key,v)==v,'Parent outcome-version conflict'
 bodies={};refs=[]
 for source in payload:
  b=base64.b64decode(source['content'])if source['encoding']=='base64'else source['content'].encode();git=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert git==source['git_blob_sha1'];bodies[source['name']]=b;refs.append({k:v for k,v in source.items()if k!='content'}|{'bytes':len(b),'sha256':sha(b)})
 pair=json.loads(bodies['PAIR.json']);native=json.loads(gzip.decompress(bodies['native.json.gz']));r0=native['payload'];assert sha(bodies['native.json.gz'])==pair['original_native_sha256'];assert sha(json.dumps(r0,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==native['payload_sha256'];assert r0['model']=='original_sleeper_matchup_baseline'
 new_decisions=[];new_numeric=[];eligible=0
 for r in r0['rows']:
  assert(r['season'],r['week'])==(2026,8)
  if not instant(r0['forecast_generated_at'])<=instant(r0['captured_at'])<instant(r['kickoff']):continue
  eligible+=1;key=(str(r['player_id']),r['game_id'],r['category']);actual,status,reason=lookup.get(key,(None,'UNRESOLVED','NO_COMPATIBLE_PARENT_OUTCOME'))
  if r['category']=='fpts':continue
  p=r.get('adjusted_projection');base={'group':'FIXED_R0_CAPTURE_20261028T184637Z','player_id':str(r['player_id']),'game_id':r['game_id'],'category':r['category'],'method':r0['model'],'point':p,'actual':actual,'status':status,'reason':reason,'issue_time':r0['forecast_generated_at'],'capture_time':r0['captured_at'],'product':'original_adjusted_empirical_point'}
  if finite(p):new_numeric.append(base)
  if r.get('lean')in('over','under')and r.get('line_from')in('dk','sleeper')and r['category']!='anytime_td':
   d={**base,'side':r['lean'],'line':r['line'],'result':value_grade(r['lean'],actual,r['line'])if status=='SUPPORTED'else status,'cohort':'ALL_RECORDED_LEANS','line_from':r['line_from']};new_decisions.append(d)
   if r.get('top_'+r['lean']):new_decisions.append({**d,'cohort':'ORIGINAL_TOP_PICKS'})
 def interval(rows):
  groups=collections.defaultdict(lambda:[0,0])
  for r in rows:
   if r['result']in('WIN','LOSS'):groups[r['game_id']][r['result']=='LOSS']+=1
  g=list(groups.values());n=len(g)
  if n<2:return {'clusters':n,'lower':None,'upper':None,'reason':'FEWER_THAN_TWO_GAME_CLUSTERS'}
  rng=random.Random(20261102);values=[]
  for _ in range(1000):
   sample=[g[rng.randrange(n)]for _ in range(n)];w=sum(x[0]for x in sample);d=sum(sum(x)for x in sample)
   if d:values.append(w/d)
  values.sort();return {'clusters':n,'lower':values[int(len(values)*.025)],'upper':values[min(len(values)-1,int(len(values)*.975))],'replicates':1000,'seed':20261102,'scope':'Nominalexposedgamecluster sensitivity;oneweek,noselectionadjustedconfirmation'}
 def table(rows):
  result=[]
  for category in sorted({r['category']for r in rows}):
   rs=[r for r in rows if r['category']==category];out={'category':category,'unique_games':len({r['game_id']for r in rs}),'unique_player_games':len({(r['player_id'],r['game_id'])for r in rs})}
   for side in ('over','under'):
    ss=[r for r in rs if r['side']==side];counts=collections.Counter(r['result']for r in ss);n=counts['WIN']+counts['LOSS'];out[side]={'wins':counts['WIN'],'losses':counts['LOSS'],'decided':n,'hit_rate':counts['WIN']/n if n else None,'pending':counts['PENDING'],'unresolved':counts['UNRESOLVED'],'push':counts['PUSH'],'DNP':counts['DNP'],'void':counts['VOID']}
   w=sum(out[s]['wins']for s in ('over','under'));l=sum(out[s]['losses']for s in ('over','under'));out['combined']={'wins':w,'losses':l,'decided':w+l,'hit_rate':w/(w+l)if w+l else None};result.append(out)
  return result
 r0_tables={cohort:table([r for r in new_decisions if r['cohort']==cohort])for cohort in ('ALL_RECORDED_LEANS','ORIGINAL_TOP_PICKS')}
 r0_metrics=[]
 for cat in sorted({r['category']for r in new_numeric}):
  rs=[r for r in new_numeric if r['category']==cat and r['status']=='SUPPORTED'];errs=[r['point']-r['actual']for r in rs];n=len(errs);ab=sorted(map(abs,errs));r0_metrics.append({'category':cat,'scored':n,'planned':sum(r['category']==cat for r in new_numeric),'MAE':sum(ab)/n if n else None,'MSE':sum(e*e for e in errs)/n if n else None,'RMSE':math.sqrt(sum(e*e for e in errs)/n)if n else None,'bias':sum(errs)/n if n else None,'p90_AE':ab[min(n-1,int(.9*n))]if n else None,'p95_AE':ab[min(n-1,int(.95*n))]if n else None})
 groups=['ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF','ARCHIVE_OCT30_RECONCILIATION','RECORDED_SELECTED_RANKING_2026-10-28T22:55:49.911448+00:00','CAPTURED_SELECTED_369fec9caec0']
 uncertainty=[]
 for group in groups:
  for cohort in sorted({r['cohort']for r in originals if r['group']==group}):
   for cat in sorted({r['category']for r in originals if r['group']==group and r['cohort']==cohort}):
    rows=[r for r in originals if(r['group'],r['cohort'],r['category'])==(group,cohort,cat)];uncertainty.append({'group':group,'cohort':cohort,'category':cat,'combined':interval(rows),'over':interval([r for r in rows if r['side']=='over']),'under':interval([r for r in rows if r['side']=='under'])})
 probabilities=[]
 for group in sorted({r['group']for r in data['probabilities']}):
  rows=[r for r in data['probabilities']if r['group']==group and r['status']=='SUPPORTED'];n=len(rows);loss=[];infinite=False
  for r in rows:
   q=r['probability'] if r['actual'] else 1-r['probability']
   if q==0:infinite=True
   else:loss.append(-math.log(q))
  bins=[]
  for i in range(5):
   rs=[r for r in rows if min(4,int(r['probability']*5))==i];bins.append({'lower':i/5,'upper':(i+1)/5,'n':len(rs),'mean_probability':sum(r['probability']for r in rs)/len(rs)if rs else None,'observed_rate':sum(r['actual']for r in rs)/len(rs)if rs else None})
  probabilities.append({'group':group,'scored':n,'Brier':sum(r['Brier']for r in rows)/n if n else None,'log_loss':sum(loss)/n if n and not infinite else None,'log_loss_state':'POSITIVE_INFINITY'if infinite else'FINITE'if n else'UNAVAILABLE','mean_probability':sum(r['probability']for r in rows)/n if n else None,'observed_event_rate':sum(r['actual']for r in rows)/n if n else None,'reliability_bins':bins,'scope':'PlayedfinalRR-TD sparse-providerlabelcontract;nosyntheticnumericpropdistributionorATDoffer'})
 def contracts(a):return {(p['id'],p['game_id'],q['key']):(q.get('line'),q.get('line_from'),q.get('lean'),q.get('adj'))for p in a['players']for q in p['props']}
 reconc=[];base=contracts(fixed)
 for label,a in [('OCT30',late),('CURRENT',current)]:
  v=contracts(a);common=set(v)&set(base);reconc.append({'snapshot':label,'common_player_game_category':len(common),'new_entries':len(set(v)-set(base)),'removed':len(set(base)-set(v)),'changed_contract_or_value':sum(v[k]!=base[k]for k in common),'not_republication_or_same_horizon':True})
 old=json.loads(gzip.decompress((ROOT/'reports/category-topfive-original-leans-release-ou-20261030/ORIGINAL_LEANS_REPORT_V1.json.gz').read_bytes()));oldw=[r for r in old['tables']['weekly']if r['week']==8 and r['cohort']=='ALL_RECORDED_LEANS'];previous={s:{k:sum(r[s][k]for r in oldw)for k in ('hit','miss','decided','pending','unresolved')}for s in('over','under')}
 report={'version':'week8-evaluator-completion-v1','recorded_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'parent_grading_version':'week8-original-grading-v1.1','parent_scorecard_sha256':'22099b3ebb6d6337100a5e38dbb5df5d34266ccda62a1f195af674f015157876','parent_grades_changed':0,'R0_source_refs':refs,'R0_capture':{'model':r0['model'],'code_commit':r0['code_commit'],'issue_UTC':r0['forecast_generated_at'],'capture_UTC':r0['captured_at'],'native_rows':len(r0['rows']),'pregame_rows':eligible,'pair_complete_input_sets_identical':pair['complete_input_sets_identical'],'interpretation':'AuthenticoriginalR0packet,notcurrentclassic;differentinputnormalizationretained;notautomaticscientificorwebsitechampion'},'R0_tables':r0_tables,'R0_numeric':r0_metrics,'uncertainty':uncertainty,'ATD_probability_scores':probabilities,'numeric_offer_probability_scores':None,'numeric_offer_probability_missing_reason':'Noauthenticatedthresholdlawsforthesenumericpoints;ATDeventprobabilityisaseparateproduct','archive_contract_reconciliation':reconc,'previous_partial_Oct30_same_snapshot':previous,'later_grades_for_same_snapshot_group':'ARCHIVE_OCT30_RECONCILIATION;donotcomparetothesmallerfixedpre-firstpopulationasifsamecases','new_fits_model_inference':0}
 members={**bodies,'R0_SCORECARD.json.gz':gzip.compress(enc({'decisions':new_decisions,'numerical':new_numeric}),mtime=0),'COMPLETION.json':enc(report)};members['MANIFEST.json']=enc({n:{'sha256':sha(b),'bytes':len(b)}for n,b in members.items()});buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED)as z:
  for n,b in members.items():z.writestr(n,b)
 b=buf.getvalue();target=root/'COMPLETION_V1.zip';assert not target.exists();store.write_bytes(target,b);v=store.validate_reference(target,sha(b));report['private_manifest']={'artifact_id':'A-WEEK8-EVALUATOR-COMPLETION-V1','bytes':v['bytes'],'sha256':v['sha256'],'R0_decisions':len(new_decisions),'R0_numeric_rows':len(new_numeric),'offhost_restore':'NOT_VERIFIED'};report['CPU_seconds']=time.process_time()-cpu;report['wall_seconds']=time.monotonic()-start
 (ROOT/'reports/week8-original-grading-20261102/REPORT_COMPLETION_V1.json').write_bytes(enc(report));print(json.dumps({'state':'COMPLETE_EVALUATOR_APPEND_PARENT_GRADES_UNCHANGED','R0_decisions':len(new_decisions),'R0_numeric':len(new_numeric),'private_manifest':report['private_manifest'],'CPU_seconds':report['CPU_seconds']}))
if __name__=='__main__':run(json.loads(base64.b64decode(sys.argv[1])))
