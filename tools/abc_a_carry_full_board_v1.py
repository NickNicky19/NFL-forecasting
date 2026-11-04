"""Zero-fit full-board direct-model extension; structured RB scope stays explicit."""
import collections,copy,gzip,io,json,os,sys,time,resource,zipfile
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import abc_a_dynamic_carry_wave_v1 as base
OUT=ROOT/'reports/abc-championship/predictive-improvement-01'
def main():
 import numpy as np,pandas as pd,pyarrow as pa,joblib
 from nfl_lab import abc_dynamic_carry_v1 as core,category_topfive_backfield_v1 as bf
 from tools import category_topfive_matched12_storage_v1 as st
 pa.set_cpu_count(1);pa.set_io_thread_count(1);cpu=time.process_time();wall=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(280,300));resource.setrlimit(resource.RLIMIT_AS,(1610612736,)*2)
 b,c,g,fr=base.sources();store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 dest=store.forward_root/'research'/'ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2'
 with zipfile.ZipFile(io.BytesIO(base.pin(g['offers'])))as z:offers=pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
 offers=offers.loc[offers.target.eq('rush_att')].copy();extra=offers.loc[~offers.position.eq('RB')];keys=set(zip(extra.game_id,extra.player_id));assert len(extra)==96
 q=pd.read_parquet(io.BytesIO(base.pin(c['features'])));q=q.loc[q.position.eq('RB')|pd.Series(list(zip(q.game_id,q.player_id)),index=q.index).isin(keys)].reset_index(drop=True);q['pregame_roster_qualified']=True;q['outcome_available_utc']=pd.NaT
 history=pd.concat([pd.read_parquet(io.BytesIO(base.pin(r)))for r in c['history_sources']],ignore_index=True)
 qb=bf.augment(q,history);qa,aux,params=core.augment(qb,core.compile_history(history));mask=qa.position.ne('RB');qextra=qa.loc[mask].reset_index(drop=True);baseextra=qb.loc[mask].reset_index(drop=True)
 model_ref=json.loads((OUT/'completion-v3/CONTENT_ADMISSION_V3.json').read_text())['models_fresh_process_readback'][1];assert model_ref['season']==2026
 store.validate_reference(dest/model_ref['object_id'],model_ref['sha256']);a1=joblib.load(io.BytesIO((dest/model_ref['object_id']).read_bytes()))
 with zipfile.ZipFile(io.BytesIO(base.pin(fr)))as z:a0=joblib.load(io.BytesIO(z.read('MODELS/rush_att_BACKFIELD.joblib')))
 with joblib.parallel_backend('sequential'):
  forecasts=base.cdf_forecasts(a0,baseextra,'A0_BACKFIELD_CDF',np)+base.cdf_forecasts(a1,qextra,'A1_BACKFIELD_CDF_ROLE_INPUTS',np)
 assert len(forecasts)==192
 payload=base.archive({'FORECASTS.json.gz':gzip.compress(base.enc(forecasts),mtime=0),'SOURCE.json':base.enc({'parent_A1_model_sha256':model_ref['sha256'],'A0_capsule_sha256':fr['sha256'],'new_fits':0,'new_inference_rows':192,'other_roles':extra.position.value_counts().to_dict()})})
 source_path=dest/'NON_RB_CARRY_FORECASTS_V1.zip';store.write_bytes(source_path,payload);store.validate_reference(source_path,base.sha(payload))
 # Only now project outcomes and build full-board decisions.
 with zipfile.ZipFile(dest/'FAILED_PARTIALS_V2.zip')as z:prior=json.loads(gzip.decompress(z.read('FORECAST_PARTIALS.json.gz')))
 full={(r['game_id'],r['player_id'],r['arm']):r for r in prior if r['season']==2026}
 full.update({(r['game_id'],r['player_id'],r['arm']):r for r in forecasts})
 with zipfile.ZipFile(io.BytesIO(base.pin(g['frozen_bundle'])))as z:cached=pd.read_parquet(io.BytesIO(z.read('FORECASTS.parquet')))
 for r in cached.loc[cached.target.eq('rush_att')&cached.method.eq('COUNT_A_MEAN')].to_dict('records'):
  full[(r['game_id'],r['player_id'],'STORED_COUNT_A_MEAN_CONTROL')]={'mean':r['prediction'],'median':None,'law':None,'fallback':r['fallback']}
 with zipfile.ZipFile(io.BytesIO(base.pin(g['qualified_labels'])))as z:labels=pd.read_parquet(io.BytesIO(z.read(g['qualified_labels']['member'])))
 label={(r.game_id,r.player_id):r for r in labels.loc[labels.target.eq('rush_att')].itertuples()}
 sys.path.insert(0,'/tmp/abc-improvement-01/C/src');import abc_championship_v2 as common
 from nfl_lab import cdf_engine as cdf
 arms=['A0_BACKFIELD_CDF','A1_BACKFIELD_CDF_ROLE_INPUTS','A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION','STORED_COUNT_A_MEAN_CONTROL','ALWAYS_OVER','ALWAYS_UNDER'];rows=[]
 for o in offers.to_dict('records'):
  l=label.get((o['game_id'],o['player_id']));y=l.actual if l is not None and l.participation_state=='played'and pd.notna(l.actual)else None
  for arm in arms:
   f=full.get((o['game_id'],o['player_id'],arm));law=f.get('law')if f else None;line=float(o['line']);ps=dict(p_over=None,p_under=None,p_push=None)
   if law:
    if law['kind']=='leaf_cdf':
     batch=cdf.MixtureBatch(np.array(law['support']),np.array([law['weights']]),cdf.SupportPrior(**law['prior']),prior_weight=law['prior_weight']);pu=float(batch.cdf([__import__('math').ceil(line)-1])[0]);po=float(1-batch.cdf([__import__('math').floor(line)])[0]);ps=dict(p_under=pu,p_over=po,p_push=max(0.,1-pu-po))
    else:ps=core.event_probabilities(np.array(law['pmf']),line)
   for policy in(['CONSTANT']if arm.startswith('ALWAYS_')else['P1_MEAN','P1_MEDIAN','P2_EXACT_LAW']):
    point=f.get(policy.removeprefix('P1_').lower())if f and policy.startswith('P1')else None
    side=arm.removeprefix('ALWAYS_')if policy=='CONSTANT'else common.a.point_side(point,line)if policy.startswith('P1')else None if ps['p_over']is None else'ABSTAIN'if abs(ps['p_over']-ps['p_under'])<=1e-12 else'OVER'if ps['p_over']>ps['p_under']else'UNDER'
    if side=='UNAVAILABLE':side=None
    r={'game_id':str(o['game_id']),'player_id':str(o['player_id']),'season':2026,'week':int(o['week']),'position':o['position'],'line':line,'actual':y,'appearance':'PLAYED'if y is not None else'UNKNOWN','status':'UNAVAILABLE_FORECAST'if side is None else'ABSTAIN'if side=='ABSTAIN'else'UNKNOWN_PARTICIPATION'if y is None else'WIN','selected_side':side,'comparator':'STRICT_OVER_UNDER','arm':arm,'policy':policy,'point':point,'opportunity_key':o['opportunity_key'],'fallback':f.get('fallback')if f else None,'outside_scope_reason':'STRUCTURED_MODEL_FIRST_WAVE_RB_ONLY'if not f and arm in ['A2_DYNAMIC_ALLOCATION','S0_RECENCY_ALLOCATION']else None,**ps};r['status']=common.status(r);rows.append(r)
 groups=collections.defaultdict(list)
 for r in rows:
  for week in ['ALL',r['week']]:groups[(r['arm'],r['policy'],week)].append(r)
 scores=[{'arm':a,'policy':p,'week':w,**common.summary(rs)}for(a,p,w),rs in sorted(groups.items(),key=lambda x:str(x[0]))]
 b2=base.archive({'GRADE_ROWS.json.gz':gzip.compress(base.enc(rows),mtime=0)});store.write_bytes(dest/'FULL_BOARD_CARRY_GRADE_V1.zip',b2);store.validate_reference(dest/'FULL_BOARD_CARRY_GRADE_V1.zip',base.sha(b2));usage=store.verify_retained_checkpoint()
 result={'state':'EXECUTED_FULL_BOARD_DIRECT_EXTENSION','new_fits':0,'new_inference_rows':192,'original_RB_rows_reused':True,'expected_offers':len(offers),'positions':offers.position.value_counts().to_dict(),'scores':scores,'new_forecasts':{'sha256':base.sha(payload),'bytes':len(payload),'readback':'PASS'},'private_grade':{'sha256':base.sha(b2),'bytes':len(b2),'readback':'PASS'},'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'retained_headroom_bytes':usage['wave_retained_headroom_bytes'],'evidence':'TIMING_UNVERIFIED_CURRENT_VINTAGE_RECONSTRUCTION_NOT_ORIGINAL_PICK','limitations':['The96extraQB/WRqueries are a laterentrant extension, not an original Week8capture.','A2/S0retain96unavailableforecasts onfull335board; their231decidedRBsubset is not a fullcategorysuccessclaim.']};(OUT/'FULL_BOARD_DIRECT_RESULTS_V1.json').write_bytes(base.enc(result));print(json.dumps([{'arm':r['arm'],'policy':r['policy'],'record':r['COMBINED'],'eligible':r['eligible'],'unavailable':r['unavailable']}for r in scores if r['week']=='ALL']))
if __name__=='__main__':main()
