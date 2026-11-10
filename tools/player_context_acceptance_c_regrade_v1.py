"""Independent raw-row C v1.1 arithmetic, not the author's scorer."""
import collections,gzip,hashlib,json,math,pathlib,sys
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parent
p=ROOT/'artifacts/player-context-matchup-01/v1.1/EXACT_OFFER_ROWS.json.gz'
body=p.read_bytes();assert hashlib.sha256(body).hexdigest()=='09259b7a64a00a283147601cbde6cc10edb0119b8baad465b61cdc49951ea994'
rows=json.loads(gzip.decompress(body));out={}
for method in sorted({r['method'] for r in rows}):
 z=[r for r in rows if r['method']==method and r['position'] in ['WR','TE']]
 assert len({r['offer_id'] for r in z})==len(z)
 counts=collections.Counter();proper=[];mismatches=0
 for r in z:
  p=r['probabilities']
  if p is not None:
   assert all(math.isfinite(v) and 0<=v<=1 for v in p.values()) and abs(sum(p.values())-1)<1e-12
  if r['actual'] is None or r['appearance']!='PLAYED':continue
  actual,line=Decimal(str(r['actual'])),Decimal(str(r['line']))
  event='over' if actual>line else 'under' if actual<line else 'push'
  grade='PUSH' if event=='push' else 'WIN' if r['selected_side'].lower()==event else 'LOSS'
  mismatches+=grade!=r['status'];counts[(r['selected_side'],grade)]+=1
  if p is not None:proper.append(sum((p[k]-int(k==event))**2 for k in ['under','push','over'])/2)
 assert mismatches==0
 out[method]={'eligible':len(z),'states':dict(collections.Counter(r['status'] for r in z)),
  'OVER':{'wins':counts[('OVER','WIN')],'losses':counts[('OVER','LOSS')]},
  'UNDER':{'wins':counts[('UNDER','WIN')],'losses':counts[('UNDER','LOSS')]},
  'Brier':sum(proper)/len(proper) if proper else None,'grade_mismatches':mismatches,
  'scored_weeks':sorted({r['week'] for r in z if r['status'] in ['WIN','LOSS']}),
  'fallback_outputs':sum(bool(r['fallback']) for r in z)}
result={'source_SHA256':hashlib.sha256(body).hexdigest(),'recomputed':out,'new_fits':0,'author_scorer_invoked':False}
(ROOT/'INDEPENDENT_REGRADING_REPRODUCED.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
