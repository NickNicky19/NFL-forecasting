"""Build a strict public-safe Git payload; private configs and row vectors stay private."""
from pathlib import Path
import argparse,base64,gzip,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
P='reports/session-a-b-matched-20261031'
BAD=re.compile(r'[/]workspace/|[/]resumed/|[/]tmp/|[/]home/runner/|s3[:]//|gh[pousr]_[A-Za-z0-9]{20,}|sk-proj-[A-Za-z0-9_-]{16,}|"player_id"\s*:\s*"00-')
CANONICAL=['EXPERIMENT_REGISTRY.json','README.md','SCOPE.md','RUN_EVENTS.jsonl','TASK_LEDGER.jsonl','SOFTWARE_TESTS.json']
def digest(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def build():
 files=[p for p in (ROOT/P).iterdir() if p.is_file() and not p.name.startswith('.') and not p.name.startswith(('PUBLICATION_MANIFEST','PUBLICATION_PAYLOAD','PUBLICATION_READBACK'))]
 files += list((ROOT/'tools').glob('session_ab_*.py'))
 files += [ROOT/'reports/opportunity-four'/n for n in CANONICAL]
 out={}
 for p in files:
  if p.suffix not in ['.py','.md','.json','.jsonl','.js','.gz']:continue
  assert '.private.' not in p.name
  b=p.read_bytes();text=gzip.decompress(b).decode() if b[:2]==b'\x1f\x8b' else b.decode();assert not BAD.search(text),'private content in '+p.name
  if b[:2]!=b'\x1f\x8b' and p.suffix in ['.json','.jsonl']:
   for s in text.splitlines() if p.suffix=='.jsonl' else [text]:
    json.loads(s,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
  out[str(p.relative_to(ROOT))]=b
 assert sum(map(len,out.values()))<=3*1024**2
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['manifest','texts','chunk'],required=True);ap.add_argument('--path');ap.add_argument('--sha256');ap.add_argument('--offset',type=int,default=0);ap.add_argument('--length',type=int,default=49152);a=ap.parse_args();files=build()
 if a.mode=='manifest':print(json.dumps({'files':[{'path':p,'bytes':len(b),'sha256':digest(b),'git_blob_sha1':blob(b),'kind':'binary' if b[:2]==b'\x1f\x8b' else 'text'} for p,b in sorted(files.items())],'public_bytes':sum(map(len,files.values()))},separators=(',',':')))
 elif a.mode=='texts':print(json.dumps([{'path':p,'mode':'100644','type':'blob','content':b.decode()} for p,b in sorted(files.items()) if b[:2]!=b'\x1f\x8b'],separators=(',',':')))
 else:
  b=files[a.path];assert digest(b)==a.sha256;print(base64.b64encode(b[a.offset:a.offset+a.length]).decode())
if __name__=='__main__':main()
