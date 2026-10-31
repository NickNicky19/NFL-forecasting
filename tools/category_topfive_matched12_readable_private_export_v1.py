"""Lossless readable CSV export of already graded private scorecards; no new scores."""
import gzip,hashlib,io,json,os,resource,signal,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_lab
from tools import category_topfive_matched12_storage_v1 as st
def enc(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);resource.setrlimit(resource.RLIMIT_CPU,(120,121));signal.alarm(300)
 import pyarrow.parquet as pq
 from nfl_lab.owned_reference_batch import validate_owned_references
 p=json.loads(gzip.decompress((ROOT/'config/category-topfive-matched12-all-finalists-grade-v1.json.gz').read_bytes()))
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 src=store.forward_root/'research'/p['run_id']/'RESULTS.zip'
 source_sha='5e30c74d98b07acc76cd54a7731570f4f9e4b5843c970a69ae30996cea00fe77'
 validate_owned_references(store,{str(src):source_sha})
 out=store.forward_root/'research/matched12-readable-private-scorecard-v1-20261031';assert not out.exists();store.register_root(out)
 reg={'version':'matched12-readable-private-scorecard-v1','state':'REGISTERED_EXPORT_ONLY',
  'source_package_sha256':source_sha,'CPU_limit':120,'wall_limit':300,'RSS_limit':2*1024**3,
  'private_peak_limit':16*1024**2,'completion_forward_CPU_allocation':'120fromunusedsame3600pool; originalcaps/failures unchanged',
  'new_fits_inference_scoring_HTTP':0,'public_row_redistribution':False}
 public=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030'
 (public/'READABLE_EXPORT_REGISTRATION_V1.json').write_bytes(enc(reg));store.write_bytes(out/'STARTED.json',enc(reg))
 entries={};counts={}
 with zipfile.ZipFile(src) as z:
  for member,name in [('PRIMARY_POINTS.parquet','PREDICTIONS_AND_ACTUALS.csv'),('DIRECTIONS.parquet','PREDICTIONS_ACTUALS_LINES_AND_DIRECTIONS.csv')]:
   frame=pq.read_table(io.BytesIO(z.read(member)),use_threads=False).to_pandas(use_threads=False)
   entries[name]=frame.to_csv(index=False,float_format='%.17g',lineterminator='\n').encode();counts[name]=len(frame)
 entries['READ_ME.txt']=b'PRIVATE RESTRICTED RESEARCH SCORECARD. Reconstructed 2026 REG Weeks1-7; not original website recommendations. Forecasts retain unrounded values. Unknown participation is not zero. Statistical threshold correctness is not venue settlement. Quote timing unverified; no prices or profitability claimed. Repeated procedures/products are not independent football outcomes. Preserve source/model/version and grading columns. Open CSVs in a spreadsheet after approved private restoration.\n'
 entries['MANIFEST.json']=enc({k:{'bytes':len(v),'sha256':sha(v),'rows':counts.get(k)} for k,v in entries.items()})
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,raw in entries.items():z.writestr(name,raw)
 body=b.getvalue();assert len(body)<16*1024**2-65536;store.write_bytes(out/'READABLE_SCORECARD.zip',body)
 ref=store.validate_reference(out/'READABLE_SCORECARD.zip',sha(body))
 with zipfile.ZipFile((out/'READABLE_SCORECARD.zip')) as z:
  for name,raw in entries.items():assert z.read(name)==raw
 actual={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
 assert actual['CPU_seconds']<=120 and actual['wall_seconds']<=300 and actual['RSS_bytes']<=2*1024**3
 receipt={'version':reg['version'],'state':'PRIVATE_READABLE_EXPORT_SAVED_AND_EXACT_READBACK','artifact':{k:ref[k] for k in ['bytes','sha256']},'rows':counts,'actual':actual,'source_result_sha256':source_sha,'offhost_restoration':'OWNER_ROUTE_REQUIRED_NOT_VERIFIED','new_fits_inference_scoring_HTTP':0}
 store.write_bytes(out/'COMPLETE.json',enc(receipt));(public/'READABLE_PRIVATE_SCORECARD_V1.json').write_bytes(enc(receipt));print(json.dumps(receipt));signal.alarm(0)
if __name__=='__main__':main()
