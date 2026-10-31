"""Root-managed qualification after actual global forecast freeze; no fitting."""
from pathlib import Path
import gzip,hashlib,io,json,math,resource,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def evidence(x):
 if isinstance(x,float) and not math.isfinite(x):return {'source_state':'nonfinite','representation':repr(x)}
 if isinstance(x,dict):return {k:evidence(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [evidence(v) for v in x]
 if hasattr(x,'item'):return evidence(x.item())
 return x
def encoded(x):return json.dumps(evidence(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def run(global_freeze):
 begin=time.monotonic();cpu=time.process_time()
 import nfl_lab
 from nfl_lab.owned_reference_batch import validate_owned_references
 from tools import category_topfive_matched12_storage_v1 as st,category_topfive_matched12_current_labels_v1 as worker
 import pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 cfgraw=(store.forward_root/'research/matched12-current-label-configuration-v1-2/CONFIG.json.gz').read_bytes();assert sha(cfgraw)=='d0254cc60783d38f9c7f5b3efc7de7e8d0d725dbc0b119f7afb8571b75d0ac5b'
 canonical=gzip.decompress(cfgraw);assert sha(canonical)=='24ff61bbc28f333ffcaec370a77a3bf6e982bc9d80642811a2f2b4ada3ef2202';cfg=json.loads(canonical)
 assert sha(Path(worker.__file__).read_bytes())=='81080392d40c7c4f773dddb382c612a6945943b8b69002df15eaabda2c4721a5'
 cfg['raw_source_capture_receipt_sha256']=sha((ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/labels/ACTUAL_NEW_SOURCE_NETWORK_V1_1.json').read_bytes())
 cfg['forecast_freezes'].append(global_freeze);cfg['run_id']='matched12-current-qualified-label-package-v1-20261031'
 cfg['resources']={'CPU_seconds':240,'wall_seconds':420,'RSS_bytes':2147483648,'AS_bytes':4294967296,'private_bytes':8388608,'NFL_fits':0,'HTTP':0}
 assert len(cfg['qualified_final_game_ids'])==107
 refs=[cfg[k] for k in ['queries','weekly','pbp']]+[x['reference'] for x in cfg['forecast_freezes']]
 seen=set()
 for owner in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]:
  items={r['path']:r['sha256'] for r in refs if any(Path(r['path']).is_relative_to(Path(x)) for x in owner._roots)}
  assert not seen.intersection(items)
  if items:validate_owned_references(owner,items);seen.update(items)
 assert seen=={r['path'] for r in refs}
 for r in [cfg['generator_source'],*cfg['source_pins'].values()]:
  b=Path(r['path']).read_bytes();assert len(b)==r['bytes'] and sha(b)==r['sha256']
 raw=worker.encoded(cfg);go={'state':'ROOT_AND_INDEPENDENT_GO','registered_by':'/root','worker_sha256':'81080392d40c7c4f773dddb382c612a6945943b8b69002df15eaabda2c4721a5','config_sha256':sha(raw)}
 conf=ROOT/'config/category-topfive-matched12-current-label-execute-v1.json.gz';assert not conf.exists();conf.write_bytes(gzip.compress(raw,mtime=0))
 (ROOT/'config/category-topfive-matched12-current-label-execute-GO-v1.json').write_bytes(encoded(go))
 out=store.forward_root/'research'/cfg['run_id'];assert not out.exists();store.register_root(out)
 store.write_bytes(out/'STARTED.json',encoded({'state':'BEFORE_ANY_NEW_SOURCE_LABEL_DECODE','configuration_sha256':sha(raw),'worker_sha256':go['worker_sha256'],'actual_global_forecast_freeze_sha256':global_freeze['reference']['sha256'],'source_window':'2026REGW1-7ONLY','fits_HTTP':0}))
 try:
  labels,audit,proofs=worker.materialize(cfg,go)
  buf=io.BytesIO();pq.write_table(pa.Table.from_pandas(labels,preserve_index=False,nthreads=1),buf,compression='zstd')
  entries={'QUALIFIED_LABELS.parquet':buf.getvalue(),'AUDIT.json':encoded(audit),'CHART_COMPONENT_PROOFS.json.gz':gzip.compress(encoded(proofs),mtime=0)}
  manifest={k:{'bytes':len(v),'sha256':sha(v)} for k,v in entries.items()};entries['MEMBER_MANIFEST.json']=encoded(manifest);buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
   for name,b in entries.items():z.writestr(name,b)
  body=buf.getvalue();assert len(body)+65536<=cfg['resources']['private_bytes'];store.write_bytes(out/'LABEL_PACKAGE.zip',body);checked=store.validate_reference(out/'LABEL_PACKAGE.zip',sha(body))
  with zipfile.ZipFile(io.BytesIO(Path(checked['path']).read_bytes())) as z:
   for name,claim in manifest.items():assert sha(z.read(name))==claim['sha256'] and len(z.read(name))==claim['bytes']
  assert len(labels)==43470 and not labels.duplicated(['target','season','week','game_id','player_id']).any()
  assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=cfg['resources']['RSS_bytes']
  result={'version':'matched12-current-qualified-label-package-v1','state':'COMPLETE_CURRENT_SOURCE_LABELS_QUALIFIED_NOT_FORECAST_SCORES','package':{k:checked[k] for k in ['bytes','sha256']},'members':manifest,'label_opportunities':len(labels),'rows_by_target_state':labels.groupby(['target','outcome_state']).size().reset_index(name='rows').to_dict('records'),'source_queries':4985,'games':107,'weeks':7,'new_NFL_fits_forecasts_scoring_HTTP':0,'source_2026_week8_semantic_rows_admitted':0,'audit':audit,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'offhost_restore':'NOT_VERIFIED'}
  store.write_bytes(out/'COMPLETE.json',encoded(result));store.verify_retained_checkpoint();return result
 except BaseException as err:
  result={'state':'FAILED_LABEL_QUALIFICATION_PRESERVED','error_type':type(err).__name__,'error_sha256':sha(str(err).encode()),'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'fits_forecasts_HTTP':0}
  store.write_bytes(out/'FAILURE.json',encoded({**result,'private_error':str(err)}));store.verify_retained_checkpoint();return result
