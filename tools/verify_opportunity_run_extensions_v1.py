"""Public-metadata reader fixtures only; zero NFL rows, fits or inference."""
import copy,hashlib,json,tempfile
from pathlib import Path
from nfl_lab.category_topfive_opportunity_registry import run_records

def main():
 checks=[]
 with tempfile.TemporaryDirectory(prefix='run-extension-check-')as d:
  root=Path(d);base=b'{"run_record_id":"a"}\n';(root/'RUN_EVENTS.jsonl').write_bytes(base)
  assert run_records(root)==[{'run_record_id':'a'}];checks.append('legacy baseline unchanged')
  new=b'{"run_record_id":"b"}\n';(root/'PUBLIC_V1.jsonl').write_bytes(new)
  doc={'version':'opportunity-public-run-extensions-v1','base':{'bytes':len(base),'sha256':hashlib.sha256(base).hexdigest(),'record_count':1},'members':[{'file':'PUBLIC_V1.jsonl','bytes':len(new),'sha256':hashlib.sha256(new).hexdigest(),'record_count':1}]}
  index=root/'RUN_EVENT_EXTENSIONS.json';index.write_text(json.dumps(doc));assert run_records(root)==[{'run_record_id':'a'},{'run_record_id':'b'}];assert(root/'RUN_EVENTS.jsonl').read_bytes()==base;checks.append('ordered exact extension; base bytes preserved')
  variants=[]
  for label,field,value in [('bad digest','sha256','0'*64),('bad byte count','bytes',len(new)+1),('bad row count','record_count',2),('path traversal','file','../PUBLIC_V1.jsonl')]:
   z=copy.deepcopy(doc);z['members'][0][field]=value;variants.append((label,z))
  z=copy.deepcopy(doc);z['members'].append(dict(z['members'][0]));variants.append(('duplicate member',z))
  z=copy.deepcopy(doc);z['base']['sha256']='0'*64;variants.append(('changed base',z))
  for label,z in variants:
   index.write_text(json.dumps(z))
   try:run_records(root)
   except ValueError:checks.append(label+' rejected')
   else:raise AssertionError(label)
 print(json.dumps({'state':'PASS','checks':checks,'NFL_observations':0}))

if __name__=='__main__':main()
