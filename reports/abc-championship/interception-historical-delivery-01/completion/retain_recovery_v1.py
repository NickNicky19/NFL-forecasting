import hashlib,json,gzip,time
from pathlib import Path
p=Path(__file__).with_name('execute_saved_2024_external_read_v1.py')
s=p.read_text();assert hashlib.sha256(p.read_bytes()).hexdigest()=='dcac7c02136aab4eafa40c86710f56dde2485b2a04492bc9654b63fe05b287fe'
go=p.parents[1]/'COMPLETION_RETENTION_RECOVERY_GO_V1.json';g=json.loads(go.read_text());assert g['state']=='GO_DETERMINISTIC_RETENTION_RECOVERY'
old="bounds=dict(continuation['remaining_original_budget']);"
s=s.replace(old,"bounds=dict(continuation['remaining_original_budget']);bounds.update(CPU_seconds=363,wall_seconds=419);")
old="require(metadata_bytes()+65536<bounds['public_task_metadata_bytes'],'Leave bounded task metadata for public report')"
s=s.replace(old,"require(metadata_bytes()<bounds['public_task_metadata_bytes'],'Actual task metadata cap before private retention')")
old="with (HERE/'EXTERNAL_ORIGINAL_ADMISSION_V1.json').open('xb') as f:f.write(encoded(external_admission));f.flush();os.fsync(f.fileno())"
s=s.replace(old,"require((HERE/'EXTERNAL_ORIGINAL_ADMISSION_V1.json').read_bytes()==encoded(external_admission),'Immutable original admission differs')")
a=s.index("    receipt['artifact'].pop('path',None)");b=s.index("    signal.alarm(0)",a)
s=s[:a]+'''    receipt['artifact'].pop('path',None)
    full=gzip.compress(encoded(clean(dict(summaries=summaries,paired=pairs,common_available_summaries=common_summary,source_bindings=safe_bindings))),compresslevel=9,mtime=0)
    small={k:receipt[k] for k in ['id','state','artifact','members','counts','evidence_tier','decision','storage','resources']}
    small['admission']=dict(clock=clock,presence=presence)
    small['primary_totals']=[dict(candidate_id=x['candidate_id'],panel=x['panel'],OVER=x['OVER'],UNDER=x['UNDER'],COMBINED=x['COMBINED'],eligible=x['eligible'],unavailable=x['unavailable'],unknown=x['unknown'],numerical=x['numerical']) for x in summaries if x['week_view']=='ALL' and x['candidate_id'] in ids[:2]]
    small['full_aggregate_receipt']=dict(file='FULL_AGGREGATES_2024_V1.json.gz',bytes=len(full),sha256=digest(full))
    small['recovery_driver_sha256']=digest(DRIVER.read_bytes());small['compiled_source_sha256']=COMPILED_SHA
    public=encoded(clean(small))
    if len(full)+len(public)>20480 or metadata_bytes()+len(full)+len(public)+24576>262144:
        small['full_aggregate_receipt']=dict(storage='PRIVATE_CAS',**receipt['members']['SCOPES_AND_AGGREGATES.json']);public=encoded(clean(small));full=None
    require(len(public)+(len(full) if full else 0)<=20480 and metadata_bytes()+len(public)+(len(full) if full else 0)+24576<=262144,'Actual metadata cap and reserved headroom')
    if full:(HERE/'FULL_AGGREGATES_2024_V1.json.gz').write_bytes(full)
    (HERE/'EXECUTED_2024_V1.json').write_bytes(public)
''' +s[b:]
ns=dict(__file__=str(p),__name__='pinned_retention_recovery',gzip=gzip,DRIVER=Path(__file__),COMPILED_SHA=hashlib.sha256(s.encode()).hexdigest())
exec(compile(s,str(p),'exec'),ns);ns['run']()
