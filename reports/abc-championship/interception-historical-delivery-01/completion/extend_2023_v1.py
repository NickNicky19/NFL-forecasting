import ast,hashlib,json
from pathlib import Path
h=Path(__file__).parent;q=h/'PROPOSED_2023_BINDINGS_V1.json';d=json.loads(q.read_text());g=json.loads((h.parent/'COMPLETION_2023_GO_V1.json').read_text());assert g['state']=='GO_2023_ZERO_FIT'
assert hashlib.sha256(q.read_bytes()).hexdigest()=='204088a4fb14b601188454f269d6f006274acfaae975b70082e34286d3f2899d'
p=h/'retain_recovery_v1.py';assert hashlib.sha256(p.read_bytes()).hexdigest()=='78f813602261b349301c734a024a4c8c08fd191522862405245e0bbcf180a8af'
n={'__file__':str(p)};exec(p.read_text().split('ns=dict(')[0],n);s=n['s'];t=ast.parse(s);a=next(x for x in ast.walk(t) if isinstance(x,ast.Assign) and any(isinstance(y,ast.Name) and y.id=='source_refs' for y in x.targets));old=eval(compile(ast.Expression(a.value),'refs','eval'),{'PRIVATE_BASE':Path(d['private_prefix'])})
s=s.replace('2024','2023').replace('execute_saved_2023_v1.py','execute_saved_2024_v1.py').replace('FAILED_2023_V1.json','FAILED_2024_V1.json').replace('FAILED_2023_TECHNICAL_V1.json','FAILED_2024_TECHNICAL_V1.json')
for k,(p,z) in old.items():s=s.replace(z,d['sources'][k]['sha256'])
for a,b in [('source-normalization-v3.zip','source-normalization-v4-2023.zip'),('5514422','5475841'),('CPU_seconds=363,wall_seconds=419','CPU_seconds=250,wall_seconds=300'),('private_retained_bytes=1048576','private_retained_bytes=951812'),('847569d194ca3d96b5efcf91e6eac5e18780fc47568a713fd545a82d29d155c1',d['sources']['raw_stats']['sha256']),('2d8a3ba8512d4a830ab2d00962955b9bab2cb4ebbd241cd4781556c3605cb30a',d['offer_member']['sha256'])]:s=s.replace(a,b)
a=s.index("    require((HERE/'EXTERNAL_ORIGINAL_ADMISSION");b=s.index('\n',a);s=s[:a]+"    require(all(bindings[k]['sha256']==D['sources'][k]['sha256'] and bindings[k]['bytes']==D['sources'][k]['bytes'] and bindings[k]['path']==str(PRIVATE_BASE/D['sources'][k]['path']) for k in external_keys),'2023 external pins')\n    bindings['2023_GO']=ref(TASK/'COMPLETION_2023_GO_V1.json');bindings['2023_proposal']=ref(HERE/'PROPOSED_2023_BINDINGS_V1.json')"+s[b:]
a=s.index("    receipt['artifact'].pop");b=s.index('    signal.alarm(0)',a)
s=s[:a]+'''    receipt['artifact'].pop('path',None)
    v=dict(artifact=receipt['artifact'],rows_sha=receipt['members']['JOINT_ROWS.parquet']['sha256'],scope_sha=receipt['members']['SCOPES_AND_AGGREGATES.json']['sha256'],counts=receipt['counts'],resources=receipt['resources'],ids=ids[:2])
    v['primary']=[[x['panel'],ids.index(x['candidate_id']),*[x[y][z] for y in ['OVER','UNDER','COMBINED'] for z in ['wins','losses']],x['numerical']['MAE']] for x in summaries if x['week_view']=='ALL' and x['candidate_id'] in ids[:2]]
    v['compiled_sha']=COMPILED_SHA
    public=encoded(clean(v));require(len(public)<=1300 and metadata_bytes()+len(public)+5120<=262144,'Metadata cap/root reserve')
    (HERE/'EXECUTED_2023_V1.json').write_bytes(public)
'''+s[b:]
n.update(__name__='extension_2023',__file__=str(h/'execute_saved_2024_external_read_v1.py'),D=d,DRIVER=Path(__file__),COMPILED_SHA=hashlib.sha256(s.encode()).hexdigest());exec(compile(s,'2023extension','exec'),n);n['run']()
