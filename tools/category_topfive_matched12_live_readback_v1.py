"""Finite production reads only; original issue clocks never altered."""
from pathlib import Path
import collections,datetime,hashlib,json,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
def main():
 begin=time.monotonic();cpu=time.process_time();calls=0
 base='https://nicknicky19.github.io/nicks-expert-nfl-picks/'
 def get(name,cap):
  nonlocal calls
  calls+=1;assert calls<=2
  with urllib.request.urlopen(base+name,timeout=10) as r:b=r.read(cap+1)
  assert 0<len(b)<=cap
  return b
 pointer=get('data/weekly-adaptive-overlay.json',16384);p=json.loads(pointer)
 print(json.dumps({'pointer_keys':list(p),'pointer':p},separators=(',',':')),flush=True)
 name=p.get('path') or p.get('payload_path') or p.get('url')
 if not name:
  digest=p.get('sha256') or p.get('payload_sha256');assert isinstance(digest,str) and len(digest)==64
  name='data/weekly-adaptive/'+digest+'.json'
 assert isinstance(name,str) and name.startswith('data/weekly-adaptive/') and '..' not in name
 body=get(name,3*1024**2);h=hashlib.sha256(body).hexdigest();expected=p.get('sha256') or p.get('payload_sha256')
 assert expected==h;v=json.loads(body);rows=v['rows']
 def count(field):return dict(collections.Counter(str(r.get(field)) for r in rows))
 result={'version':'matched12-readonly-served-audit-v1','state':'ACTUAL_SERVED_POINTER_AND_PAYLOAD_READBACK','at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'at_America_Chicago':datetime.datetime.now(__import__('zoneinfo').ZoneInfo('America/Chicago')).isoformat(),'pointer_sha256':hashlib.sha256(pointer).hexdigest(),'payload_sha256':h,'payload_bytes':len(body),'rows':len(rows),'by_category':count('category'),'products':count('product'),'functional':count('prediction_functional'),'new_MAE_profile_rows':sum(r.get('product')=='stat_point_mae_v2' or r.get('product_version')=='stat_point_mae_v2' for r in rows),'issue_fields':{f:count(f) for f in ['issued_at_utc','forecast_issued_at','issued_at'] if any(f in r for r in rows)},'row_field_names':sorted(set().union(*(set(r) for r in rows))),'HTTP_GETs':calls,'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-begin,'production_writes_inference_capture_deployment':0,'consumer_scope':'Actual served data readback only; not visual DOM or new inference.'}
 out=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/LIVE_READBACK_V1.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,separators=(',',':')))
if __name__=='__main__':main()
