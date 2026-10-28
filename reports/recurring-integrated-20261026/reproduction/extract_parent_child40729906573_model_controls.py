"""Owner GET-only extraction of four authenticated control documents.

No weights, provider rows, forecast rows or outcome bodies are decoded.
"""
from pathlib import Path
import base64,gzip,io,json,os,subprocess,sys,hashlib
os.umask(0o077)
sys.path.insert(0,str(Path.cwd()))
from nfl_lab import private_draft_store as s,audit_weekly_archive_v1 as a,owner_bootstrap_bundle as codec
B=Path('/workspace/nfl-system-audit/continuation');P=B/'private';GH='/workspace/nfl-system-audit/bin/gh';OUT=P/'parent-child40729906573-control-metadata-v2';OUT.mkdir(mode=0o700)
calls=[]
def get(route,cap,octet=False):
 assert route.startswith('repos/'+s.REPO+'/')
 cmd=[GH,'api','--method','GET',route]
 if octet:cmd+=['-H','Accept: application/octet-stream']
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
 assert r.returncode==0 and 0<len(r.stdout)<=cap,'BOUNDED_OWNER_GET_FAILED'
 calls.append(dict(route_sha256=s.sha(route.encode()),bytes=len(r.stdout)))
 return r.stdout
def asset(i,name,size,digest):
 route='repos/'+s.REPO+'/releases/assets/'+str(i);m=json.loads(get(route,65536))
 assert (m['id'],m['state'],m['name'],m['size'],m['digest'])==(i,'uploaded',name,size,'sha256:'+digest)
 b=get(route,size,True);assert len(b)==size and s.sha(b)==digest;return b
def payload(d):
 e=d['entry'];m=asset(d['manifest_asset_id'],'manifest-'+d['manifest_sha256']+'.json',d['manifest_bytes'],d['manifest_sha256'])
 assert s.canonical(json.loads(m))==m and json.loads(m)==e
 return asset(e['payload_asset_id'],e['payload_name'],e['payload']['bytes'],e['payload']['sha256'])
names={'context/canonical_weekly_choice.json':'choice','context/epoch.json':'epoch','context/original_catalog.json':'original-catalog','runtime/ARTIFACT_CATALOG.json':'artifact-catalog'}
results={}
for attempt,index_sha,root_sha,run in [(40729906573,'fde369550858b70a2812e9a51f654304f2883210eedc58f59492baeff1e59caa','34743ce66f1c23ac0f45c6a910af734c9084693a2f4b2e314636283e423b58bc','40729906573')]:
 root=json.loads((P/'weekly-go-32.json').read_bytes());binding=root['qualified_runtime']['binding']
 release=json.loads(get('repos/'+s.REPO+'/releases/'+str(binding['release_id']),256<<10));assert release['draft']is True and release['published_at']is None and release['tag_name']==binding['tag_name']
 if attempt==28:raw=(P/'capture28-discovery-original-index.gz').read_bytes()
 else:
  assets=[]
  for page in (1,2):
   part=json.loads(get('repos/'+s.REPO+'/releases/'+str(binding['release_id'])+'/assets?per_page=100&page='+str(page),1<<20));assert isinstance(part,list) and len(part)<=100
   assets+=part
   if len(part)<100:break
  else:raise ValueError('INCOMPLETE_INVENTORY')
  found=[x for x in assets if x['name']=='blob-'+index_sha+'.bin'];assert len(found)==1
  meta=found[0];raw=asset(meta['id'],meta['name'],meta['size'],index_sha)
 assert s.sha(raw)==index_sha
 index=a.unpack(raw,a.INDEX_PLAIN_CAP);assert index['root_go_sha256']==root_sha and index['producer']['run_id']==run and index['archive_state']=='COMPLETE_CAPTURE'
 assert index['runtime_binding_sha256']==hashlib.sha256(json.dumps(binding,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest() and index['source_sha']=='0409a253d6a365c31a2d421941b8ee5f40d6fd02'
 (OUT/f'{attempt}-original-index.gz').write_bytes(raw)
 expected={f['logical_path']:f for f in index['files'] if f['logical_path'] in names};assert set(expected)==set(names)
 kept={}
 for group in index['groups']:
  needed=set(expected)&{f['logical_path']for f in group['files']}
  if not needed:continue
  packed=payload(group['descriptor']);assert len(packed)==group['bytes'] and s.sha(packed)==group['sha256']
  with gzip.GzipFile(fileobj=io.BytesIO(packed))as stream:plain=stream.read(codec.GROUP_JSON+1)
  assert len(plain)==group['inflated_bytes']<=codec.GROUP_JSON
  doc=json.loads(plain);assert doc['schema_version']==codec.VERSION
  for f in doc['files']:
   if f['path']not in needed:continue
   name=f['path'];meta=expected[name];body=base64.b64decode(f['content_b64'],validate=True)
   assert len(body)==f['bytes']==meta['bytes'] and s.sha(body)==f['sha256']==meta['sha256']
   assert name not in kept;kept[name]=json.loads(body);(OUT/f'{attempt}-{names[name]}.json').write_bytes(body)
 assert set(kept)==set(names)
 results[str(attempt)]={k:dict(sha256=expected[k]['sha256'],keys=list(v))for k,v in kept.items()}
 after=json.loads(get('repos/'+s.REPO+'/releases/'+str(binding['release_id']),256<<10));assert after['draft']is True and after['id']==release['id']
print(json.dumps(dict(state='AUTHENTICATED_AUTOMATIC_CHILD_CONTROL_METADATA_EXTRACTED',controls=results,GET_calls=len(calls),forecast_or_outcome_rows_decoded=0,model_weight_decodes=0,new_fits=0,remote_writes=0)))
