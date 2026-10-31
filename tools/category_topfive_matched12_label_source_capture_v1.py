"""Two finite permitted NFLverse downloads; metadata only, no outcome decoding."""
import hashlib,importlib.util,io,json,resource,signal,sys,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-current-label-source-capture-v1'
JOBS=[('weekly','https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.parquet',4*1024**2),
 ('pbp','https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.parquet',16*1024**2)]
def run():
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(180,181))
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('finite source-capture wall cap')));signal.alarm(300)
 sys.path.insert(0,str(ROOT));import nfl_lab
 spec=importlib.util.spec_from_file_location('matched12_label_source_store',ROOT/'tools/category_topfive_matched12_storage_v1.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 store,_=helper.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=helper.GO)
 output=store.forward_root/'research'/VERSION
 if output.exists():raise ValueError('single consumed source capture must not be overwritten')
 store.register_root(output);store.atomic_json(output/'CONSUMED.json',{'version':VERSION,'requests':2,'body_limit_bytes':20*1024**2,'numeric_outcome_decodes':0,'protected_outcomes':'NO_STATISTICAL_COLUMNS_DECODED; laterreaderrequires2026REGweek<=7predicate','new_fits':0})
 results=[]
 for name,url,cap in JOBS:
  event={'source':name,'original_url':url,'captured_UTC':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
  try:
   request=urllib.request.Request(url,headers={'User-Agent':'NFL-research-bounded-label-capture/1'})
   with urllib.request.urlopen(request,timeout=30) as response:
    event['HTTP_status']=response.status
    event['headers']={k:response.headers.get(k) for k in ['Content-Type','Content-Length','ETag','Last-Modified']}
    raw=response.read(cap+1)
   if len(raw)>cap:
    raw=raw[:cap];event['state']='FAILED_BODY_CAP_PARTIAL_RETAINED'
   else:event['state']='RAW_BODY_CAPTURED_SCHEMA_PENDING'
   destination=output/(name+'.parquet' if raw[:4]==b'PAR1' and raw[-4:]==b'PAR1' else name+'.response.bin')
   store.write_bytes(destination,raw);ref=store.validate_reference(destination,hashlib.sha256(raw).hexdigest());event['artifact']={'file':destination.name,'bytes':ref['bytes'],'sha256':ref['sha256']}
   if event['state']=='RAW_BODY_CAPTURED_SCHEMA_PENDING':
    if destination.suffix!='.parquet':raise ValueError('response is not a Parquet container')
    import pyarrow.parquet as pq
    footer=pq.ParquetFile(io.BytesIO(raw));event['parquet_metadata']={'rows':footer.metadata.num_rows,'columns':len(footer.schema_arrow),'row_groups':footer.metadata.num_row_groups,'column_names':footer.schema_arrow.names}
    event['state']='PASS_RAW_LOCAL_READBACK_METADATA_ONLY'
  except BaseException as exc:
   event.update(state='FAILED_ATTEMPT_RETAINED',error_type=type(exc).__name__,error_message_sha256=hashlib.sha256(str(exc).encode()).hexdigest())
   if isinstance(exc,urllib.error.HTTPError):event['HTTP_status']=exc.code
  results.append(event);store.atomic_json(output/(name+'_RECEIPT.json'),event)
 store.verify_retained_checkpoint();result={'version':VERSION,'sources':results,'HTTP_requests_attempted':len(results),'statistical_outcome_decodes':0,'NFL_fits_forecasts_scoring':0,'new_key_spending_production_actions':0,'offhost_restoration':'NOT_VERIFIED','actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
 store.atomic_json(output/'COMPLETE.json',result);store.verify_retained_checkpoint();signal.alarm(0);return result
if __name__=='__main__':print(json.dumps(run(),sort_keys=True,allow_nan=False))
