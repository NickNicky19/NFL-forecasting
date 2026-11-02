"""Serialize already graded rows to private readable CSV and close accounting."""
import csv,gzip,hashlib,io,json,resource,signal,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def run():
 sys.path.insert(0,str(ROOT));from tools import category_topfive_matched12_storage_v1 as st
 resource.setrlimit(resource.RLIMIT_CPU,(120,121));signal.alarm(240);cpu=time.process_time();store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 root=store.forward_root/'research'/'week8-original-grade-v2-batch-20261102'
 def get(name,digest,member):
  store.validate_reference(root/name,digest)
  with zipfile.ZipFile(root/name)as z:return json.loads(gzip.decompress(z.read(member)))
 main=get('GRADING_V1_1.zip','22099b3ebb6d6337100a5e38dbb5df5d34266ccda62a1f195af674f015157876','SCORECARD.json.gz');r0=get('COMPLETION_V1.zip','bac6a5f39739517502ffe5ced5a33587a3f3bd5a84307ca18cfef08aa4c55493','R0_SCORECARD.json.gz')
 with zipfile.ZipFile(root/'SOURCES.zip')as z:
  a=json.loads(z.read('archive_pre_first.bin'));new=json.loads(z.read('archive_current.bin'))
 names={p['id']:p['name']for p in a['players']};names.update({p['id']:p['name']for p in new['players']});games={g['id']:g['kickoff']for g in a['games']}
 fields=['group','cohort','game_id','kickoff_UTC','player_id','player','category','method','product','policy','point','line','side','actual','absolute_error','squared_error','result','status','reason','actual_reason','issue_time','archive_saved_at','capture_time','capture_id','line_from','price','quote_time','venue_settlement','original_website_selection','procedure_version']
 def serialize(rows):
  out=io.StringIO(newline='');w=csv.DictWriter(out,fields,extrasaction='ignore');w.writeheader()
  for row in rows:
   r=dict(row);r['player']=names.get(r['player_id'],'UNKNOWN_IDENTITY');r['kickoff_UTC']=games.get(r['game_id']);p,y=r.get('point'),r.get('actual')
   if type(p)in(int,float)and type(y)in(int,float):r.update(absolute_error=abs(p-y),squared_error=(p-y)**2)
   w.writerow(r)
  return gzip.compress(out.getvalue().encode(),mtime=0)
 rows=main['decisions']+r0['decisions'];nums=main['numerical']+r0['numerical'];members={'ORIGINAL_DECISIONS_AND_DIRECTIONS.csv.gz':serialize(rows),'PREDICTIONS_AND_ACTUALS.csv.gz':serialize(nums),'PROBABILITIES_AND_ACTUALS.json.gz':gzip.compress(enc(main['probabilities']),mtime=0)};members['MANIFEST.json']=enc({n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}for n,b in members.items()});out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)as z:
  for n,b in members.items():z.writestr(n,b)
 data=out.getvalue();target=root/'READABLE_SCORECARDS_V1.zip';assert not target.exists();store.write_bytes(target,data);v=store.validate_reference(target,hashlib.sha256(data).hexdigest())
 with zipfile.ZipFile(target)as z:
  assert z.testzip()is None
  for n,b in members.items():assert z.read(n)==b
 usage=store.verify_retained_checkpoint();metadata=sum(p.stat().st_size for p in (ROOT/'reports/week8-original-grading-20261102').rglob('*')if p.is_file())+sum(p.stat().st_size for p in (ROOT/'tools').glob('week8*.py'))+sum(p.stat().st_size for p in (ROOT/'config').glob('week8*.json'))+65536
 assert metadata<=1048576 and usage['new_peer_physical_bytes']+metadata<=usage['wave_retained_limit_bytes'] and usage['matched12_complete_accounted_bytes']+metadata<=usage['matched12_complete_limit_bytes']
 result={'state':'PASS_PRIVATE_READABLE_SCORECARD_READBACK_AND_COMPLETE_ACCOUNTING','artifact_id':'A-WEEK8-READABLE-SCORECARDS-V1','bytes':v['bytes'],'sha256':v['sha256'],'decision_output_rows':len(rows),'numeric_output_rows':len(nums),'probability_output_rows':len(main['probabilities']),'independent_NFL_games_graded':13,'repeated_snapshots_not_independent_observations':True,'usage':{k:v for k,v in usage.items()if k.endswith('_bytes')and type(v)is int},'current_wave_metadata_with_future65536reserve_bytes':metadata,'conservative_complete_accounted_bytes':usage['matched12_complete_accounted_bytes']+metadata,'original_limits_reservations':'UNCHANGED;old80MiBupcomingreservepreserved','offhost_restore':'NOT_VERIFIED','actual_CPU_seconds':time.process_time()-cpu,'CSV_rules':'Originalvaluesunrounded;nullfieldsblank;providerzero/unknownreasonsretained;eachsourceissuanceseparate;oldPPRnotchart'}
 (ROOT/'reports/week8-original-grading-20261102/READABLE_AND_STORAGE_RECEIPT_V1.json').write_bytes(enc(result));print(json.dumps(result))
if __name__=='__main__':run()
