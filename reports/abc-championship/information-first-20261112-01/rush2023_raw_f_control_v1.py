"""Append the registered raw-law F control; retain its distinct price-gated view."""
from pathlib import Path
import ast,hashlib,importlib.util,io,json,sys,time,zipfile
ROOT=Path('/workspace/nfl-methods-integration');OUT=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def main():
 begin=time.process_time()
 import numpy as np,pandas as pd
 owner=load(OUT/'rush2023_worker_v1.py','raw_f_owner_helpers')
 assert owner.ref(OUT/'rush2023_worker_v1.py')['sha256']=='3303571c9cb376cf61a5208e28191c2d2c0cf2343d9a3922deeb67802f2e6781'
 proposal=json.loads((OUT/'RUSH2023_PROPOSAL_V1.json').read_bytes())
 for r in proposal['code_bindings']:owner.auth(r)
 sys.path.insert(0,proposal['C_code_directory']);import abc_championship_v2 as common
 aux=load(ROOT/'tools/category_topfive_matched12_aux_runner_v1.py','raw_f_intervals')
 ref=json.loads((OUT/'RUSH2023_COMPLETE_V1.json').read_bytes())['grades']
 with zipfile.ZipFile(io.BytesIO(owner.auth(ref)))as z:
  body=z.read('ROWS.parquet');assert sha(body)=='00863e16ac7fba6b554e714a5bca925f5f1020600fac67dff73afe4b63ed2eb3';f=pd.read_parquet(io.BytesIO(body))
 p=f[['F_under','F_push','F_over']].to_numpy(float);assert np.isfinite(p).all()and(p>=0).all()and np.allclose(p.sum(1),1,atol=1e-10,rtol=0)
 denom=p[:,0]+p[:,2];f['raw_F_side']=np.where(p[:,2]>p[:,0],'over',np.where(p[:,0]>p[:,2],'under','abstain'));f['raw_F_confidence']=np.divide(np.maximum(p[:,0],p[:,2]),denom,out=np.full(len(p),np.nan),where=denom>0)
 tree=ast.parse((ROOT/'tools/category_topfive_matched12_law_outer_v1.py').read_text());fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name=='selectors');outer=next(x for x in fn.body if isinstance(x,ast.For));loop=next(x for x in outer.body if isinstance(x,ast.For)and isinstance(x.target,ast.Name)and x.target.id=='k');code=compile(ast.Module(body=loop.body[:2],type_ignores=[]),'<unchanged registered Top6 AST>','exec')
 def top(g,side,confidence):
  g=g.copy();g['side']=g[side];g['confidence']=g[confidence];ns={'g':g,'k':6,'views':{}};exec(code,ns);return ns['views']['TOP_6_PER_CATEGORY_WEEK']
 def rows(g,field):
  out=[]
  for r in g.to_dict('records'):
   known=r['participation_state']=='played'and pd.notna(r['actual']);s=r[field];side=None if pd.isna(s)or s=='unavailable'else s.upper()
   x={'season':2023,'week':int(r['week']),'game_id':r['game_id'],'player_id':r['player_id'],'selected_side':side,'line':float(r['line']),'actual':float(r['actual'])if known else None,'appearance':'PLAYED'if r['participation_state']=='played'else'UNKNOWN','comparator':'STRICT_OVER_UNDER','status':'UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'UNKNOWN_PARTICIPATION'if not known else'WIN'};x['status']=common.status(x);out.append(x)
  return out
 result={'scope':'Append-only raw savedF-law P2 control; original price-gatedF_probability records preserved','grade_capsule':ref,'rows_member_sha256':sha(body),'code':owner.ref(Path(__file__)),'price_gate_count':int(f.F_probability.isna().sum()),'new_fits_models_inference_private_writes':0,'panels':[]}
 f['gated_confidence']=np.maximum(f.F_probability,1-f.F_probability)
 for name,g in [('2023_W1_9',f[f.week.le(9)]),('2023_FULL_REG',f)]:
  chosen=top(g,'raw_F_side','raw_F_confidence');old=top(g,'F_PROBABILITY','gated_confidence');a=rows(g,'side');b=rows(g,'raw_F_side');ix=[i for i in range(len(a))if a[i]['status']in['WIN','LOSS']and b[i]['status']in['WIN','LOSS']];delta=np.asarray([int(a[i]['status']=='WIN')-int(b[i]['status']=='WIN')for i in ix])
  result['panels'].append({'period':name,'actual_weeks':sorted(map(int,g.week.unique())),'eligible':len(g),'raw_F_own_full_board':common.summary(b),'raw_F_own_Top6':common.summary(rows(chosen,'raw_F_side')),'Top6_membership_changed_from_price_gated':len(set(chosen.offer_id)^set(old.offer_id)),'raw_F_vs_BASE_CDF_median_side_disagreements':int(g.raw_F_side.ne(g.BASE_CDF_MEDIAN).sum()),'candidate_minus_raw_F_wins':int(delta.sum()),'common_decided':len(ix),'paired_game':aux._interval(delta,[a[i]['game_id']for i in ix],{'minimum_clusters':2,'replicates':1000,'seed':20261030}),'paired_week':aux._interval(delta,[a[i]['week']for i in ix],{'minimum_clusters':2,'replicates':1000,'seed':20261030})})
 result['CPU_seconds']=time.process_time()-begin;owner.note('RUSH2023_RAW_F_CONTROL_APPENDIX_V1.json',result)
 print(json.dumps({'state':'APPENDIX_COMPLETE','file':str(OUT/'RUSH2023_RAW_F_CONTROL_APPENDIX_V1.json'),'CPU_seconds':result['CPU_seconds']}))
if __name__=='__main__':main()
