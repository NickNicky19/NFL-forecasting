"""Prepare permitted aggregate/code Git payloads in memory, never private row vectors."""
from pathlib import Path
import argparse,base64,gzip,hashlib,io,json,re,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];P='reports/category-topfive-matched-all12-w1w7-20261030';R=ROOT/P
BAD=re.compile(r'[/]workspace/|[/]resumed|[/]tmp/|s3[:]//|gh[pousr]_[A-Za-z0-9]{20,}|sk-proj-[A-Za-z0-9_-]{16,}')
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def enc(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def build():
 old={x['path']:x['sha256'] for x in json.loads((R/'PUBLICATION_ALLOWLIST_ACTUAL_V1.json').read_bytes())['files']};texts={};binaries={};archive={};excluded=[]
 candidates=[p for p in R.rglob('*') if p.is_file()]+list((ROOT/'tools').glob('category_topfive_matched12*.py'))
 candidates += [ROOT/'reports/opportunity-four'/n for n in ['README.md','EXPERIMENT_REGISTRY.json','RUN_EVENTS.jsonl','TASK_LEDGER.jsonl']]
 candidates += list((ROOT/'config').glob('category-topfive-matched12-metadata-forward*.json'))+[ROOT/'config/category-topfive-matched12-completion-forward-v1_1.json',ROOT/'config/category-topfive-matched12-final-evidence-completion-v1_2.json']
 for f in candidates:
  path=str(f.relative_to(ROOT));raw=f.read_bytes()
  if f.name.startswith(('PUBLICATION_PAYLOAD_','PUBLICATION_MANIFEST_V2','PUBLICATION_READBACK_V2')):continue
  if old.get(path)==sha(raw):continue
  if f.suffix not in {'.md','.json','.jsonl','.csv','.py','.patch','.gz'}:continue
  try:decoded=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw;text=decoded.decode()
  except (OSError,UnicodeDecodeError):continue
  if BAD.search(text):excluded.append({'path':path,'bytes':len(raw),'sha256':sha(raw),'reason':'PRIVATE_LOCATORS_OR_BOUND_CODE_REMAIN_PRIVATE; PUBLIC_PORTABLE_COPY_OR_HASH_MANIFEST_SEPARATE'});continue
  if raw[:2]==b'\x1f\x8b':
   if f.name in {'POINT_PRODUCTS_W1_7.csv.gz','EACH_POINT_PRODUCTS_OWN_OVER_UNDER_W1_7.csv.gz','RESEARCH_POINT_PROCEDURE_RANKING_W1_7.csv.gz','WEEKLY_POINT_PRODUCTS_W1_7.csv.gz'}:texts[path[:-3]]=decoded
   elif 'probability-projection/' in path or f.name in {'CATEGORY_RELEASE_MANIFEST_V2.json.gz','EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz'}:binaries[path]=raw
   else:archive[path]=raw
  else:texts[path]=raw
 archive[P+'/EXCLUDED_PRIVATE_BINDINGS_V2.json']=enc({'state':'HASH_ONLY_PRIVATE_EVIDENCE_BOUNDARIES','excluded':excluded})
 if archive:
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for name,raw in sorted(archive.items()):
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
  binaries[P+'/EXECUTION_EVIDENCE_V2.zip']=b.getvalue()
 return texts,binaries,excluded
def private_aggregate(kind):
 sys.path.insert(0,str(ROOT));import nfl_lab
 from tools import category_topfive_matched12_storage_v1 as st
 f=Path(st.prepare(ROOT)['allocation']['store_policy']['storage']['forward_root'])
 if kind=='main':
  p=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()));path=f/'research'/p['run_id']/'RESULTS.zip';expected='5e30c74d98b07acc76cd54a7731570f4f9e4b5843c970a69ae30996cea00fe77';member='AGGREGATES.json.gz'
 elif kind=='market':path=f/'research/matched12-exploratory-conditional-score-v1-1-20261031/SCORE_PACKAGE.zip';expected='25ef0445269af2a6134d16839c4f1a01e154e2c4dd1a57a9fc96ca3858b0a8b9';member='AGGREGATES.json.gz'
 elif kind=='law':
  path=f/'research/matched12-law-all-finalists-v1-1-20261031/AGGREGATES.json.gz';b=path.read_bytes();assert sha(b)=='e7438e27d078daa8aceda5528a1f74cde59cf5db00cb81160ea735e05350c715';return b
 elif kind=='atd':
  cfg=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-atd-postretention-v1.json.gz').read_bytes()));admission=json.loads((f/'research'/cfg['run_id']/'COMPLETE.json').read_bytes());assert admission['state']=='POSTRETENTION_CACHED_OUTPUTS_ADMITTED_ORIGINAL_EXECUTION_REMAINS_RESOURCE_FAILED';assert admission['source_result']=={k:cfg['result'][k] for k in ['bytes','sha256']};path=Path(cfg['result']['path']);expected=cfg['result']['sha256'];member='AGGREGATES.json.gz'
 else:raise ValueError('unregistered aggregate')
 b=path.read_bytes();assert sha(b)==expected
 with zipfile.ZipFile(io.BytesIO(b)) as z:return z.read(member)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['manifest','texts','chunk'],required=True);ap.add_argument('--path');ap.add_argument('--offset',type=int,default=0);ap.add_argument('--length',type=int,default=196608);ap.add_argument('--expected-sha256');a=ap.parse_args()
 t,b,e=build()
 for name,kind in [('ALL_FINALISTS_AGGREGATES_V1.json.gz','main'),('LAW_AGGREGATES_V1.json.gz','law'),('EXPLORATORY_MARKET_AGGREGATES_V1.json.gz','market'),('ATD_LATE_AGGREGATES_V1.json.gz','atd')]:
  raw=private_aggregate(kind);assert not BAD.search(gzip.decompress(raw).decode());b[P+'/'+name]=raw
 if a.mode=='manifest':
  rows=[{'path':p,'bytes':len(raw),'sha256':sha(raw),'git_blob_sha1':blob(raw),'kind':'text' if p in t else 'binary'} for p,raw in sorted({**t,**b}.items())]
  print(json.dumps({'files':rows,'total_bytes':sum(x['bytes'] for x in rows),'excluded_private_files':len(e)},separators=(',',':')))
 elif a.mode=='texts':print(json.dumps([{'path':p,'mode':'100644','type':'blob','content':raw.decode()} for p,raw in sorted(t.items())],separators=(',',':')))
 else:
  raw=b[a.path];assert sha(raw)==a.expected_sha256;print(base64.b64encode(raw[a.offset:a.offset+a.length]).decode())
if __name__=='__main__':main()
