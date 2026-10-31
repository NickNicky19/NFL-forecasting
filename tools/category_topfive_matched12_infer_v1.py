"""Fixed-model all7 historical inference, with immutable per-model attempts.

This separately named adapter uses trained future-query parameters, never the
operational issuance path or an old historical query-bound exporter. It does
not fit, acquire data, read evaluation labels, grade or publish to production.
"""
from __future__ import annotations
import argparse,gzip,hashlib,importlib.util,io,json,resource,signal,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-fixed-parameter-historical-inference-v1'
EVIDENCE='CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION'
KEY=['season','week','game_id','player_id']
CONTEXT=['team','opponent','position','kickoff_utc','cutoff_utc']
FAMILIES={'leaf_cdf_base','catboost_medium','count_A'}
ALL_SKILL_ROLES=['QB','RB','FB','WR','TE']
MEAN_RECIPE='count-a-prior-mean-fallback-v2-20261025'
FORBIDDEN={'actual','outcome_state','pass_yd','pass_td','pass_cmp','pass_att','pass_int',
 'rush_yd','rush_att','rec','rec_yd','rush_rec_yd','fantasy_ppr','chart_ppr','anytime_td','rec_tgt'}
def encoded(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m
def metadata_reference(ref):
    p=Path(ref['path'])
    if not p.is_absolute() or p.resolve()!=p or any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('canonical exact metadata reference required')
    b=p.read_bytes()
    if len(b)!=ref['bytes'] or sha(b)!=ref['sha256']:raise ValueError('pinned metadata changed')
    return b

def source_cells():
    """Metadata-only source inspection; does not open stores or load models."""
    p=ROOT/'config/weekly-historical-expansion-v1.json';source=json.loads(p.read_text())
    result=[]
    for old in source['current_2026_artifacts']:
        if old['family'] not in FAMILIES:continue
        manifest=json.loads(metadata_reference(old['artifact']))
        if manifest['category']['target']!=old['target'] or manifest['family']!=old['family']:raise ValueError('original metadata identity mismatch')
        result.append({'cell_id':old['target']+'__'+old['family'], 'target':old['target'],
          'family':old['family'],'manifest':old['artifact'],'model':manifest['model'],
          'procedure_version':manifest['procedure_version'],'roles':manifest['category']['modeled_roles'],
          'query_roles':['QB'] if old['target'].startswith('pass_') else ALL_SKILL_ROLES,
          'primary_roles':manifest['category']['primary_roles'],
          'training_cutoff_utc':manifest['training_cutoff_utc'],
          'training_max_available_utc':manifest['training_max_available_utc'],
          'training_history':'Earlier seasons2019-2025, annual fixed relationship; target-week earlier game histories update only inputs.',
          'source_configuration_sha256':sha(p.read_bytes())})
    return result

def _aware(series,pd):
    for v in series.dropna().unique():
        if pd.Timestamp(v).tzinfo is None:raise ValueError('source timezone unknown')
    return pd.to_datetime(series,utc=True,errors='raise')

def frozen_query(frame,manifest,cell,api,pd,np):
    if FORBIDDEN&set(frame):raise ValueError('target or evaluation outcome column in feature input')
    if frame.duplicated(KEY).any() or frame[KEY].isna().any(axis=None):raise ValueError('nonunique query identity')
    if not frame.season.eq(2026).all() or not frame.week.between(1,7).all():raise ValueError('fixed2026W1-7 only')
    if not frame.participation_state.eq('unknown').all():raise ValueError('query participation cannot be target labels')
    if set(cell['roles'])!=set(manifest['category']['modeled_roles']) or set(cell['primary_roles'])!=set(manifest['category']['primary_roles']):raise ValueError('registered relevant role population changed')
    query_roles=['QB'] if cell['target'].startswith('pass_') else ALL_SKILL_ROLES
    if cell['query_roles']!=query_roles:raise ValueError('registered all-skill-query/primary-role-headline policy changed')
    q=frame.loc[frame.position.isin(cell['query_roles'])].copy().reset_index(drop=True)
    if q.empty:raise ValueError('registered model population empty')
    for col in ['kickoff_utc','cutoff_utc','feature_max_source_available_utc']:q[col]=_aware(q[col],pd)
    if q[['kickoff_utc','cutoff_utc']].isna().any(axis=None) or (q.cutoff_utc>q.kickoff_utc).any():raise ValueError('invalid historical source horizon')
    mx=q.feature_max_source_available_utc
    if (mx.notna()&(mx>=q.cutoff_utc)).any() or (mx.isna()&(pd.to_numeric(q.f_player_games_prior)>0)).any():raise ValueError('future or unknown warm source clock')
    tc=pd.Timestamp(manifest['training_cutoff_utc']);ta=pd.Timestamp(manifest['training_max_available_utc'])
    if tc.tzinfo is None or ta.tzinfo is None or not ta<tc or not (q.cutoff_utc>tc).all():raise ValueError('trained parameters outside historical issue cutoffs')
    if manifest['training_cutoff_utc']!=cell['training_cutoff_utc'] or manifest['training_max_available_utc']!=cell['training_max_available_utc']:raise ValueError('registered training chronology drift')
    clean=api.query_projection(q,manifest['features'])
    return q,clean

def original_outputs(model,manifest,clean,cell,stable_cls,correct_mean,np,pd,check_rss):
    """Original points unchanged; normalized probability is separately typed."""
    target=cell['target'];family=cell['family'];support=manifest['category']['support']
    wide=clean[KEY+CONTEXT].copy();wide['fallback']='UNVISITED'
    for col in ['mean','median','point','legacy_point','probability','normalized_law_probability']:wide[col]=np.nan
    seen=np.zeros(len(clean),bool)
    if family=='leaf_cdf_base':
        for ix,law,reasons in model.predict_batches(clean,batch_size=256):
            if seen[ix].any():raise ValueError('duplicate law output row')
            seen[ix]=True;wide.loc[ix,'fallback']=reasons
            if law is None:continue
            if support=='bernoulli':
                wide.loc[ix,'probability']=law.mean
                corrected=stable_cls.from_batch(law)
                wide.loc[ix,'normalized_law_probability']=1-corrected.cdf(np.zeros(len(ix)))
            else:
                wide.loc[ix,'mean']=law.mean;wide.loc[ix,'median']=law.quantile(.5)
            check_rss()
    else:
        values,reasons=model.predict(clean);seen[:]=True;wide['fallback']=reasons
        if family=='count_A':
            wide['legacy_point']=values
            values=correct_mean(np,values,reasons,clean.position.to_numpy(),model.priors,model.global_prior)
        wide['probability' if support=='bernoulli' else 'point']=values
    if not seen.all():raise ValueError('forecast output population incomplete')
    for col in ['mean','median','point','legacy_point','probability','normalized_law_probability']:
        x=wide[col].to_numpy(float)
        if np.isinf(x).any():raise ValueError('infinite forecast output')
        if support=='count' and (x[np.isfinite(x)]<0).any():raise ValueError('negative count output')
        if col in ['probability','normalized_law_probability'] and ((x[np.isfinite(x)]<0)|(x[np.isfinite(x)]>1)).any():raise ValueError('invalid event probability retained as failure; no clipping')
    wide['target']=target;wide['method']={'leaf_cdf_base':'LEAF_CDF','catboost_medium':'CATBOOST_MEDIUM','count_A':'COUNT_A_MEAN'}[family]
    parent=manifest['procedure_version'];wide['parent_procedure_version']=parent
    wide['procedure_version']=(sha(encoded({'recipe':MEAN_RECIPE,'parent_procedure_version':parent,
        'parent_model_sha256':manifest['model']['sha256']})) if family=='count_A' else parent)
    wide['legacy_point_parent_procedure_version']=parent if family=='count_A' else None
    wide['normalized_law_procedure_version']=(sha(encoded({'law_arithmetic':'normalized-cumulative-mixture-v1-20261025',
        'parent_procedure_version':parent,'parent_model_sha256':manifest['model']['sha256']})) if family=='leaf_cdf_base' else None)
    wide['inference_adapter_version']=VERSION
    wide['primary_role']=wide.position.isin(cell['primary_roles'])
    wide['evidence_tier']=EVIDENCE;wide['original_forecast_issued_at']=None
    wide['point_arithmetic']='ORIGINAL_TRAINED_IMPLEMENTATION_UNCHANGED'
    if family=='count_A':wide['point_arithmetic']='count-a-prior-mean-fallback-v2-20261025; original empirical point separately retained'
    wide['law_arithmetic']='normalized-cumulative-mixture-v1-20261025' if family=='leaf_cdf_base' else 'NONE_POINT_ONLY' if support!='bernoulli' else 'NATIVE_BINARY_EVENT_PROBABILITY'
    return wide

def execute(plan,go):
    """The only actual model-deserialization entry, requiring fresh root GO."""
    start=time.monotonic();cpu=time.process_time();own=sha(Path(__file__).read_bytes())
    if (go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root'
        or go.get('worker_version')!=VERSION or go.get('worker_sha256')!=own
        or go.get('plan_sha256')!=sha(encoded(plan))):raise ValueError('exact root and independent inference GO required')
    if plan['version']!=VERSION or plan['new_fits']!=0 or len(plan['cells'])>19:raise ValueError('first finite retained-parameter control wave only')
    caps=plan['resources'];resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('finite historical inference wall cap')));signal.alarm(caps['wall_seconds'])
    def no_network(event,args):
        if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline retained-parameter inference')
    sys.addaudithook(no_network)
    for name,h in plan['root_code_pins'].items():
        if sha((ROOT/name).read_bytes())!=h:raise ValueError('registered source changed: '+name)
    sys.path.insert(0,str(ROOT))
    import numpy as np,pandas as pd
    from threadpoolctl import threadpool_limits
    from nfl_lab import weekly_future_inference as api
    stref=plan['stable_law_source'];metadata_reference(stref)
    stablemod=load('nfl_lab.threshold_cdf',stref['path'])
    if stablemod.STABLE_MIXTURE_VERSION!='normalized-cumulative-mixture-v1-20261025':raise ValueError('separate corrected probability arithmetic changed')
    meanref=plan['corrected_count_mean_source'];metadata_reference(meanref)
    meanmod=load('matched12_correct_count_mean',meanref['path'])
    helper=load('matched12_inference_storage',ROOT/'tools/category_topfive_matched12_storage_v1.py')
    store,_=helper.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=helper.GO)
    out=store.register_root(store.forward_root/'research'/VERSION)
    write_bytes_charged=16384 # conservative new root/registry/owner control reserve
    def owned(ref):
        p=Path(ref['path']);owners=(store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy)
        matches=[s for s in owners if any(p.is_relative_to(r) for r in s._roots)]
        if len(matches)!=1:raise ValueError('exact retained reference owner not identified')
        got=matches[0].validate_reference(p,ref['sha256'])
        if got['bytes']!=ref['bytes']:raise ValueError('retained reference size changed')
        return got
    def authenticate(refs):return {r['path']:owned(r) for r in refs}
    def check_rss():
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>caps['RSS_bytes']:raise MemoryError('registered inference RSS cap')
    def write(path,raw,*,emergency=False):
        nonlocal write_bytes_charged
        reserve=0 if emergency else 65536
        if write_bytes_charged+len(raw)>caps['maximum_new_private_bytes']-reserve:raise ValueError('finite inclusive wave write envelope exhausted; failure reserve retained')
        write_bytes_charged+=len(raw) # failed attempts remain consumed
        used=store.verify_retained_checkpoint()['new_peer_physical_bytes']
        if used+len(raw)+reserve>100663296:raise ValueError('preserve96MiBretained envelope plusfailure reserve')
        store.write_bytes(path,raw);r=store.validate_reference(path,sha(raw))
        return {'sha256':r['sha256'],'bytes':r['bytes'],'file':str(path.relative_to(out))}
    def journal(name,doc):return write(out/name,encoded(doc),emergency=name.endswith('FAILURE.json'))
    consumed=out/'CONSUMED.json'
    if consumed.exists():raise ValueError('first wave already consumed; explicit recorded continuation required')
    journal('CONSUMED.json',{'state':'STARTED','plan_sha256':go['plan_sha256'],'at_UTC':pd.Timestamp.now(tz='UTC').isoformat(),'new_fits':0})
    owned(plan['features']);owned(plan['source_preparation_receipt'])
    prep=json.loads(Path(plan['source_preparation_receipt']['path']).read_text())
    if prep['state']!='PASS_SOURCE_PREPARATION_ONLY' or prep['outputs']['features']['sha256']!=plan['features']['sha256']:raise ValueError('actual completed primaryfeature freeze required')
    frame=pd.read_parquet(plan['features']['path']);results=[];restorations=0;inference=0
    cell_ids=[c['cell_id'] for c in plan['cells']]
    if len(cell_ids)!=len(set(cell_ids)):raise ValueError('unique preregistered model attempts required')
    for cell in plan['cells']:
        cid=cell['cell_id'];t0=time.monotonic();c0=time.process_time()
        started={'cell_id':cid,'target':cell['target'],'family':cell['family'],'state':'RESTORATION_ATTEMPT_STARTED',
            'manifest_sha256':cell['manifest']['sha256'],'model_sha256':cell['model']['sha256'],
            'features_sha256':plan['features']['sha256'],'at_UTC':pd.Timestamp.now(tz='UTC').isoformat(),'new_fits':0}
        journal(cid+'/STARTED.json',started)
        try:
            owned(cell['manifest']);manifest=json.loads(Path(cell['manifest']['path']).read_text())
            if manifest['family'] not in FAMILIES or manifest['family']!=cell['family'] or manifest['category']['target']!=cell['target'] or manifest['model']!=cell['model'] or manifest['procedure_version']!=cell['procedure_version']:raise ValueError('registered trained procedure identity differs')
            if manifest['dependencies']:raise ValueError('first control wave excludes correction/ordered dependencies')
            for r in manifest['training_sources']:owned(r)
            q,clean=frozen_query(frame,manifest,cell,api,pd,np)
            restorations+=1
            if restorations>caps['maximum_model_restorations']:raise ValueError('finite restoration budget exhausted')
            if inference+len(clean)+4*restorations>caps['maximum_inference_rows']:raise ValueError('finite queryplusfixture inference allocation exhausted')
            with api.FutureInferenceSession(authenticate) as session,threadpool_limits(limits=2):
                session.prepare([cell['manifest']])
                m,model=session.models[cell['manifest']['sha256']]
                inference+=len(clean)
                if inference>caps['maximum_inference_rows']:raise ValueError('finite procedure inference row allocation exhausted')
                wide=original_outputs(model,m,clean,cell,stablemod.StableMixtureBatch,meanmod.correct_fallbacks,np,pd,check_rss)
                buf=io.BytesIO();wide.to_parquet(buf,index=False,compression='zstd')
                forecast=write(out/cid/'FORECASTS.parquet',buf.getvalue())
                replay={'version':VERSION,'target':cell['target'],'family':cell['family'],'manifest':cell['manifest'],
                    'output_procedure_version':str(wide.procedure_version.iloc[0]),'parent_procedure_version':m['procedure_version'],
                    'model':cell['model'],'features':plan['features'],'query_projection_sha256':api.frame_digest(clean),
                    'modeled_roles':cell['roles'],'population_query_roles':cell['query_roles'],'primary_roles':cell['primary_roles'],
                    'point_arithmetic':'Original stored trained implementation; CountAmean fallback separately named withlegacy output retained.',
                    'law_arithmetic':stablemod.STABLE_MIXTURE_VERSION if cell['family']=='leaf_cdf_base' else None,
                    'law_source':stref if cell['family']=='leaf_cdf_base' else None,
                    'complete_distribution_replay':'Retained exact trained forest/histograms/priors plus immutable featureframe, roles and deterministic adapter; no labels needed.',
                    'law_conditioning':'played','no_numeric_law_reason':None if cell['family']=='leaf_cdf_base' else 'Point-only fitted count/yard objective doesnot define aPMF; nativebinary probability remains valid.',
                    'original_issued_at':None,'generated_at_UTC':pd.Timestamp.now(tz='UTC').isoformat(),'evidence_tier':EVIDENCE}
                replayref=journal(cid+'/LAW_REPLAY.json',replay)
            check_rss();store.verify_retained_checkpoint()
            result={'cell_id':cid,'target':cell['target'],'family':cell['family'],'state':'FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED',
                'procedure_version':str(wide.procedure_version.iloc[0]),'parent_procedure_version':manifest['procedure_version'],'manifest_sha256':cell['manifest']['sha256'],
                'model_sha256':cell['model']['sha256'],'features_sha256':plan['features']['sha256'],
                'rows':len(wide),'primary_role_rows':int(wide.primary_role.sum()),'games':int(wide.game_id.nunique()),
                'weeks':sorted(map(int,wide.week.unique())),'fallback_rows':int(wide.fallback.ne('').sum()),
                'available_outputs':{k:int(wide[k].notna().sum()) for k in ['mean','median','point','legacy_point','probability','normalized_law_probability']},
                'forecast':forecast,'law_replay':replayref,'new_fits':0,'model_restorations':1,
                'fixture_replay_charged_upper_bound_rows':4,'actual_fixture_replay_rows':None,
                'fixture_count_reason':'Existing frozen producer bound4; no second deserialization to recount its retained fixture.',
                'CPU_seconds':time.process_time()-c0,'wall_seconds':time.monotonic()-t0}
            journal(cid+'/COMPLETE.json',result);results.append(result)
        except BaseException as exc:
            failure={**started,'state':'FAILED_ATTEMPT_PRESERVED','exception_type':type(exc).__name__,'message':str(exc),
                'CPU_seconds':time.process_time()-c0,'wall_seconds':time.monotonic()-t0}
            journal(cid+'/FAILURE.json',failure);results.append(failure)
            if isinstance(exc,(KeyboardInterrupt,SystemExit,MemoryError,TimeoutError)):raise
    check_rss();usage=store.verify_retained_checkpoint()
    summary={'version':VERSION,'state':'FINITE_WAVE_TERMINAL_WITH_FAILURES' if any(r['state']=='FAILED_ATTEMPT_PRESERVED' for r in results) else 'FINITE_WAVE_FORECASTS_FROZEN_UNSCORED',
        'plan_sha256':go['plan_sha256'],'features_sha256':plan['features']['sha256'],'results':results,
        'new_fits':0,'model_restoration_attempts':restorations,'procedure_query_inference_rows':inference,
        'fixture_replay_charged_upper_bound_rows':4*restorations,
        'inclusive_private_write_bytes_charged':write_bytes_charged,
        'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},
        'new_peer_physical_bytes':usage['new_peer_physical_bytes'],'evidence_tier':EVIDENCE,
        'scoring_runs':0,'evaluation_labels_decoded':0,'original_pregame_forecasts':0,'production_writes':0,'offhost_restoration':'NOT_VERIFIED'}
    journal('TERMINAL.json',summary);store.verify_retained_checkpoint();signal.alarm(0)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--go',type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(json.loads(a.plan.read_text()),json.loads(a.go.read_text())),sort_keys=True,allow_nan=False))
