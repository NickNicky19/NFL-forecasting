"""Research-only existing response/role/chart restoration; no fits, grading or issuance."""
from __future__ import annotations
import argparse,base64,gzip,hashlib,importlib.util,io,json,pickle,resource,signal,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-followup-fixed-parameter-inference-v1'
EVIDENCE='CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION'
KEY=['season','week','game_id','player_id'];CONTEXT=['team','opponent','position','kickoff_utc','cutoff_utc']
ROLES=['QB','RB','FB','WR','TE']
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def load(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def reference(p):
    p=Path(p);b=p.read_bytes()
    if p.resolve()!=p or any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('canonical source required')
    return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def read(ref):
    p=Path(ref['path']);r=reference(p)
    if r!=ref:raise ValueError('exact source binding changed')
    return p.read_bytes()
def meta(ref):return json.loads(read(ref))

def prepare_cells():
    """Only retained metadata/container qualification; no model loading."""
    cells=[];old=json.loads((ROOT/'config/modern-2026-cold-grade-v2.sealed.json').read_text())
    for target,item in old['cells'].items():
        terminal=meta(item['terminal']);artifact=terminal['model']
        with zipfile.ZipFile(io.BytesIO(read(artifact))) as z:m=json.loads(z.read('MANIFEST.json'))
        witness=old['annual']['2026']['targets'][target]['original_CDF_manifest'];w=meta(witness)
        if m['source_training_frame_sha256']!=w['training_frame_sha256'] or m['training_cutoff_utc']!=w['training_cutoff_utc']:raise ValueError('cold source training/clock witness mismatch')
        family='RESPONSE_CDF' if m['family']=='response_cdf' else 'CATBOOST_MEDIUM'
        cells.append({'cell_id':target+'__'+family,'target':target,'kind':'cold_response' if family=='RESPONSE_CDF' else 'cold_cat',
          'method':family,'artifact':artifact,'member':'MODEL.joblib','metadata_member':'MANIFEST.json','chain':item['terminal'],
          'witness':witness,'category':m['category'],'panel':'base','training_cutoff_utc':m['training_cutoff_utc'],
          'training_max_available_utc':w['training_max_available_utc'],'weeks':list(range(1,8)),'augmenter':None})
    op=json.loads((ROOT/'config/next-checkpoint-ordered-scoring-v3.sealed.json').read_text())
    artifact=op['frozen_forecasts']
    with zipfile.ZipFile(io.BytesIO(read(artifact))) as z:audits=json.loads(z.read('MODEL_AUDITS.json'))
    for target in ['rush_att','rec']:
        a=audits[target]['ORDERED_CDF'];cells.append({'cell_id':target+'__ORDERED_CDF','target':target,'kind':'context_cdf','method':'ORDERED_CDF',
          'artifact':artifact,'member':'MODELS/'+target+'_ORDERED.joblib','metadata_member':'MODEL_AUDITS.json',
          'category':a['category'],'panel':a['panel'],'audit':a['audit'],'training_cutoff_utc':a['training_cutoff_utc'],
          'training_max_available_utc':None,'weeks':list(range(1,8)),'augmenter':'ordered'})
    rpath=Path(json.loads((ROOT/'config/category-topfive-backfield-v1.sealed.json').read_text())['public_result'])
    chain=reference(rpath);artifact=meta(chain)['freeze']
    with zipfile.ZipFile(io.BytesIO(read(artifact))) as z:a=json.loads(z.read('MODEL_AUDITS.json'))['rush_att']['BACKFIELD_CDF']
    cells.append({'cell_id':'rush_att__BACKFIELD_CDF','target':'rush_att','kind':'context_cdf','method':'BACKFIELD_CDF','artifact':artifact,
      'chain':chain,'member':'MODELS/rush_att_BACKFIELD.joblib','metadata_member':'MODEL_AUDITS.json','category':a['category'],'panel':a['panel'],
      'audit':a['audit'],'training_cutoff_utc':a['training_cutoff_utc'],'training_max_available_utc':None,'weeks':list(range(1,8)),'augmenter':'backfield'})
    depth_config=Path(__import__('os').environ['MATCHED12_DEPTH_CONTROL_FILE'])
    dp=json.loads(depth_config.read_text());glob=reference(Path(dp['output'])/'GLOBAL_FORECAST_FREEZE.json');fr=meta(glob)['years']['2026']
    with zipfile.ZipFile(io.BytesIO(read(fr))) as z:fm=json.loads(z.read('MANIFEST.json'))
    artifact=fm['model_capsules']['2026-HISTORICAL_RELATION_CURRENT_STATE-ROLE-ANNUAL']
    with zipfile.ZipFile(io.BytesIO(read(artifact))) as z:a=json.loads(z.read('FIT_AUDIT.json'))
    cells.append({'cell_id':'pass_att__DEPTH_CDF_W1_6','target':'pass_att','kind':'depth_cdf','method':'DEPTH_CDF','artifact':artifact,
      'member':'MODEL.joblib','metadata_member':'FIT_AUDIT.json','chain':fr,'category':None,'panel':'base','audit':a['audit'],
      'training_cutoff_utc':a['fit_cutoff_utc'],'training_max_available_utc':a['maximum_training_label_available_utc'],
      'weeks':list(range(1,7)),'augmenter':'depth','depth_sources':{k:dp['inputs'][k] for k in ['role_source_2026','role_bridge','role_qualification']},
      'depth_helper':dp['role_helper'],'W7_blocker':'Pinned role selector rejectsW7; no current depth backfill or original guard relaxation.'})
    cp=json.loads((ROOT/'config/next-checkpoint-chart-cdf-control-v1.sealed.json').read_text())
    chart=reference(Path(cp['output'])/'FORECASTS_FROZEN.json.gz')
    expected=json.loads((ROOT/'config/next-checkpoint-chart-cdf-adapter-replay-v1.sealed.json').read_text())['inputs']['frozen_model_and_predictions']
    if chart!=expected:raise ValueError('chart canonical freeze differs')
    hgb=cp['inputs']['original_HGB_forecasts']
    for kind,artifact,method in [('chart_cdf',chart,'CHART_LEAF_CDF'),('chart_hgb',hgb,'CHART_HGB')]:
        doc=json.loads(gzip.decompress(read(artifact)),parse_float=str,parse_int=str)
        raw=base64.b64decode(doc['fitted_model_pickle_base64'],validate=True)
        if sha(raw)!=doc['fitted_model_sha256']:raise ValueError('trusted chart parameter identity mismatch')
        cells.append({'cell_id':'chart_ppr__'+method,'target':'chart_ppr','kind':kind,'method':method,'artifact':artifact,
          'model_sha256':doc['fitted_model_sha256'],'weeks':list(range(1,8)),'augmenter':None,'training_cutoff_utc':'2026-09-01T00:00:00+00:00',
          'training_max_available_utc':None,'clock_witness':chart,'chart_training_season':2024})
    return cells

def clock_guard(frame,pd):
    if set(KEY+CONTEXT+['feature_max_source_available_utc','participation_state'])-set(frame):raise ValueError('historical query context missing')
    if frame.duplicated(KEY).any() or not frame.participation_state.eq('unknown').all():raise ValueError('outcome-blind unique queries required')
    for c in ['kickoff_utc','cutoff_utc','feature_max_source_available_utc']:
        for v in frame[c].dropna().unique():
            if pd.Timestamp(v).tzinfo is None:raise ValueError('unknown source timezone')
        frame[c]=pd.to_datetime(frame[c],utc=True)
    if frame[['kickoff_utc','cutoff_utc']].isna().any(axis=None) or (frame.cutoff_utc>frame.kickoff_utc).any():raise ValueError('invalid historical horizon')
    s=frame.feature_max_source_available_utc
    if (s.notna()&(s>=frame.cutoff_utc)).any():raise ValueError('future feature source')
    return frame

def augment_history(q,kind,plan,owned,pd,modules):
    """Strict cutoff pushdown, with the pinned backfield static-prefix cache."""
    fields=KEY+['team','position','kickoff_utc','outcome_available_utc','participation_state','rush_att','rec','rec_tgt']
    def earlier(limit,lower=None):
        parts=[]
        for ref in plan['history_sources']:
            owned(ref);pred=[('kickoff_utc','<',limit),('outcome_available_utc','<',limit)]
            if lower is not None:pred.append(('outcome_available_utc','>=',lower))
            h=pd.read_parquet(ref['path'],columns=fields,filters=pred)
            ko=pd.to_datetime(h.kickoff_utc,utc=True);av=pd.to_datetime(h.outcome_available_utc,utc=True)
            if av.isna().any() or (av>=limit).any() or not av.eq(ko+pd.Timedelta(days=7)).all():raise ValueError('strict original7day source lane changed')
            parts.append(h)
        h=pd.concat(parts,ignore_index=True)
        if h.duplicated(['game_id','player_id']).any():raise ValueError('history partitions overlap')
        return h
    first=q.cutoff_utc.min();common=earlier(first) if kind=='backfield' else None
    prefix=modules[kind].compile_history(common) if common is not None else None
    chunks=[];audits=[]
    for cutoff,positions in q.groupby('cutoff_utc',sort=False).groups.items():
        h=earlier(cutoff,first if kind=='backfield' else None)
        before=q.loc[positions].copy().reset_index(drop=True)
        if kind=='backfield':
            grouped=modules[kind].merge_compiled(prefix,modules[kind].compile_history(h))
            after=modules[kind].augment_from_compiled(before,grouped)
        else:after=modules[kind].augment(before,h)
        for col in before:
            if kind=='backfield' and col=='feature_max_source_available_utc':continue
            if not after[col].equals(before[col]):raise ValueError('augmentation changed base input '+col)
        after['_original_row']=positions;chunks.append(after)
        audits.append({'cutoff':str(cutoff),'query_rows':len(before),'eligible_history_rows':len(h)+(len(common) if common is not None else 0),'source_policy':'Strict earlieravailability+kickoff projection; original7day assumption; staticprefix compiledonce.'})
    return pd.concat(chunks,ignore_index=True).sort_values('_original_row').drop(columns='_original_row').reset_index(drop=True),audits

def depth_features(q,cell,owned,pd,selector):
    # This pinned selector is intentionally NOT extended to W7.
    for r in cell['depth_sources'].values():owned(r)
    doc=json.loads(gzip.decompress(Path(cell['depth_sources']['role_source_2026']['path']).read_bytes()))
    source=doc['rows'] if isinstance(doc,dict) and 'rows' in doc else doc['source_rows'] if isinstance(doc,dict) and 'source_rows' in doc else doc
    bridge=pd.read_parquet(cell['depth_sources']['role_bridge']['path'],columns=['gsis_id','espn_id']).to_dict('records')
    projected=q[list(selector.QUERY_COLUMNS)].to_dict('records')
    selected=selector.select_roles(source,projected,bridge,maximum_age_hours=None)
    if len(selected)!=len(q):raise ValueError('depth selector population changed')
    values=[]
    for row in selected:
        values.append([row['role_rank'],row['role_starter'],row['role_group_size'],row['role_age_hours'],0.] if row['role_known'] else [float('nan')]*4+[1.])
    names=['f_role_depth_rank','f_role_depth_starter','f_role_depth_group_size','f_role_depth_age_hours','f_role_depth_missing']
    q=q.copy()
    for i,n in enumerate(names):q[n]=[v[i] for v in values]
    q['depth_information_clock_state']='RECONSTRUCTED_VENDOR_LOAD_CLOCK_NOT_AUTHENTIC_PUBLICATION'
    return q,[{'week7':'BLOCKED_PINNED_SELECTOR_SCOPE','known_roles':sum(r['role_known'] for r in selected),'planned':len(selected)}]

def law_outputs(model,q,method,np,scale=1,stable_cls=None,prior_only=False,stable_points=False):
    r=q[KEY+CONTEXT].copy();r['mean']=np.nan;r['median']=np.nan;r['point']=np.nan;r['fallback']='UNVISITED';seen=np.zeros(len(q),bool)
    for ix,law,reasons in model.predict_batches(q,batch_size=128,prior_only=prior_only):
        if seen[ix].any():raise ValueError('duplicate output');
        seen[ix]=True;r.loc[ix,'fallback']=reasons
        if law is None:continue
        pointlaw=stable_cls.from_batch(law) if stable_points else law
        r.loc[ix,'mean']=pointlaw.mean/scale;r.loc[ix,'median']=pointlaw.quantile(.5)/scale
    if not seen.all() or np.isinf(r[['mean','median','point']].to_numpy(float)).any():raise ValueError('invalid/incomplete restored law output')
    r['method']=method;r['law_scale']=scale;r['law_conditioning']='played'
    return r

def predict_chart_hgb(bundle,q,np):
    features=bundle['features'];medians=np.asarray(bundle['medians']);priors=bundle['priors'];glob=bundle['global_prior']
    r=q[KEY+CONTEXT].copy();r['mean']=np.nan;r['median']=np.nan;r['point']=np.nan;r['fallback']=''
    for i,row in q.iterrows():
        why=''
        if row['feature_max_source_available_utc'] is None or str(row['feature_max_source_available_utc'])=='NaT':why='unknown_feature_clock_position_prior'
        elif not np.isfinite(float(row['f_player_games_prior'])) or float(row['f_player_games_prior'])<=0:why='cold_or_unknown_history_position_prior'
        if row['position'] not in priors:why='unseen_role_global_prior'
        r.at[i,'fallback']=why;r.at[i,'point']=priors.get(row['position'],glob)['median']
    warm=r.fallback.eq('');f=q.loc[warm]
    if len(f):
        raw=f[features].to_numpy(float);missing=~np.isfinite(raw)
        x=np.column_stack([np.where(missing,medians[None,:],raw),missing.astype(float),
            np.stack([f.position.eq(role).to_numpy(float) for role in bundle['roles']],axis=1)])
        r.loc[warm,'point']=bundle['estimator'].predict(x)
    if not np.isfinite(r.point.to_numpy(float)).all():raise ValueError('nonfinite chart HGB point')
    r['method']='CHART_HGB';r['law_scale']=None;r['law_conditioning']='NONE_POINT_ONLY'
    return r

def execute(plan,go):
    start=time.monotonic();cpu=time.process_time()
    if go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('registered_by')!='/root' or go.get('worker_version')!=VERSION or go.get('worker_sha256')!=sha(Path(__file__).read_bytes()) or go.get('plan_sha256')!=sha(enc(plan)):raise ValueError('exact independently reviewed root GO required')
    caps=plan['resources']
    if plan['new_fits']!=0 or len(plan['cells'])>12:raise ValueError('finite retained-model wave only')
    resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1));signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('followup wall cap')));signal.alarm(caps['wall_seconds'])
    def offline(e,a):
        if e in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline retained models only')
    sys.addaudithook(offline)
    for n,h in plan['root_code_pins'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('root code changed '+n)
    sys.path.insert(0,str(ROOT));import numpy as np,pandas as pd,joblib
    from threadpoolctl import threadpool_limits
    from nfl_lab import cdf_engine as engine,direct_boosters as direct,next_checkpoint_chart_cdf_inference as chart
    from nfl_lab.weekly_future_inference import environment
    if environment()!=plan['environment']:raise ValueError('original model dependency versions differ')
    modules={}
    module_names=['threshold_cdf','distribution_split_cdf']+[n for n in plan['source_modules'] if n not in ['threshold_cdf','distribution_split_cdf']]
    for name in module_names:
        r=plan['source_modules'][name]
        read(r);modules[name]=load('nfl_lab.'+name if name in ['threshold_cdf','distribution_split_cdf'] else 'matched12_followup_'+name,r['path'])
    stable=modules['threshold_cdf'].StableMixtureBatch
    helper=load('matched12_followup_storage',ROOT/'tools/category_topfive_matched12_storage_v1.py')
    store,_=helper.open_store(ROOT,allocation_sha256=plan['allocation_sha256'],root_go=helper.GO)
    out=store.register_root(store.forward_root/'research'/VERSION);charged=16384
    from nfl_lab.owned_reference_batch import validate_owned_references
    checked={};stamps={}
    def owner(ref):
        p=Path(ref['path']);peers=[store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]
        matches=[s for s in peers if any(p.is_relative_to(r) for r in s._roots)]
        if len(matches)!=1:raise ValueError('exact evidence owner unknown')
        return matches[0]
    def stamp(path):
        st=Path(path).lstat()
        return (st.st_dev,st.st_ino,st.st_size,st.st_mode,st.st_mtime_ns,st.st_ctime_ns)
    def owned(ref):
        p=ref['path']
        if p not in checked or any(checked[p][k]!=ref[k] for k in ['path','bytes','sha256']) or stamp(p)!=stamps[p]:raise ValueError('batch-authenticated retained reference changed')
        return checked[p]
    def write(name,body):
        nonlocal charged
        reserve=0 if name.endswith('FAILURE.json') else 65536
        if charged+len(body)+reserve>caps['maximum_new_private_bytes']:raise ValueError('inclusive followup write envelope exhausted')
        used=store.verify_retained_checkpoint()['new_peer_physical_bytes']
        if used+len(body)+reserve>100663296:raise ValueError('complete96MiBretained envelope exhausted')
        charged+=len(body);p=out/name;store.write_bytes(p,body);r=store.validate_reference(p,sha(body))
        return {'file':name,'sha256':r['sha256'],'bytes':r['bytes']}
    def journal(name,doc):return write(name,enc(doc))
    if (out/'CONSUMED.json').exists():raise ValueError('followup already consumed; preserve original attempt')
    journal('CONSUMED.json',{'state':'STARTED','plan_sha256':go['plan_sha256'],'at_UTC':pd.Timestamp.now(tz='UTC').isoformat(),'new_fits':0})
    refs=[plan['features'],*plan.get('history_sources',[])]
    for c in plan['cells']:
        refs+=[c['artifact']]
        refs+=[c[k] for k in ['chain','witness','clock_witness'] if c.get(k)]
        refs+=list(c.get('depth_sources',{}).values())
    unique={}
    for r in refs:
        if r['path'] in unique and unique[r['path']]!=r:raise ValueError('conflicting original reference bindings')
        unique[r['path']]=r
    def bulk(phase):
        groups={}
        for r in unique.values():groups.setdefault(owner(r),[]).append(r)
        receipts=[]
        for peer,items in groups.items():
            found,receipt=validate_owned_references(peer,{r['path']:r['sha256'] for r in items})
            for r in items:
                got=found[r['path']]
                if got['bytes']!=r['bytes']:raise ValueError('batch reference size changed')
                checked[r['path']]=got;stamps[r['path']]=stamp(r['path'])
            receipts.append(receipt)
        return journal('OWNED_REFERENCE_BATCH_'+phase+'.json',{'version':'owned-reference-batch-v1','owner_groups':len(groups),'exact_receipts':receipts})
    batch_start=bulk('START')
    owned(plan['features']);frame=clock_guard(pd.read_parquet(plan['features']['path']),pd)
    results=[];restores=0;rows=0
    for cell in plan['cells']:
        cid=cell['cell_id'];journal(cid+'/STARTED.json',{'state':'RESTORATION_ATTEMPT_STARTED','cell_id':cid,'artifact_sha256':cell['artifact']['sha256'],'new_fits':0})
        try:
            owned(cell['artifact'])
            if cell.get('chain'):owned(cell['chain'])
            q=frame.loc[frame.week.isin(cell['weeks']) & (frame.position.eq('QB') if cell['target'].startswith('pass_') else frame.position.isin(ROLES))].copy().reset_index(drop=True)
            audits=[]
            if cell['augmenter'] in ['ordered','backfield']:q,audits=augment_history(q,cell['augmenter'],plan,owned,pd,modules)
            elif cell['augmenter']=='depth':q,audits=depth_features(q,cell,owned,pd,modules['depth'])
            q=clock_guard(q,pd);tc=pd.Timestamp(cell['training_cutoff_utc'])
            if tc.tzinfo is None or (q.cutoff_utc<tc).any():raise ValueError('parameter information horizon follows query')
            if cell.get('training_max_available_utc') and not pd.Timestamp(cell['training_max_available_utc'])<min(tc,q.cutoff_utc.min()):raise ValueError('training source not strictly earlier')
            restores+=1;rows+=len(q)*(2 if cell['kind']=='chart_cdf' else 1)+4
            if restores>caps['maximum_model_restorations'] or rows>caps['maximum_inference_rows']:raise ValueError('finite restore/inference allocation exhausted')
            artifact=read(cell['artifact']);kind=cell['kind'];doc=None;bundle=None;model=None
            with threadpool_limits(limits=2):
                if kind in ['cold_response','cold_cat','context_cdf','depth_cdf']:
                    with zipfile.ZipFile(io.BytesIO(artifact)) as z:
                        inner=z.read(cell['member'])
                        if len(inner)>16*1024**2:raise ValueError('bounded model member exceeded')
                        obj=joblib.load(io.BytesIO(inner))
                    model=obj['model'] if kind.startswith('cold_') else obj
                    expected_type=modules['distribution_split_cdf'].DistributionSplitCDFModel if kind=='cold_response' else direct.DirectBoosterModel if kind=='cold_cat' else engine.LeafCDFModel
                    if type(model) is not expected_type:raise ValueError('exact frozen model class differs')
                    if cell['category'] is not None and model.category!=cell['category']:raise ValueError('frozen category differs')
                    if model.panel!=cell['panel']:raise ValueError('frozen feature panel differs')
                    if kind in ['context_cdf','depth_cdf'] and model.audit!=cell['audit']:raise ValueError('original fitted audit differs')
                    if kind=='context_cdf':
                        binding=model.prior_training_binding
                        if binding is None or not (pd.to_datetime(binding.outcome_available_utc,utc=True)<min(tc,q.cutoff_utc.min())).all():raise ValueError('retained prior training clock unavailable or later')
                    if kind.startswith('cold_'):
                        fixture=obj['fixture'];old=obj['expected']
                        replay=law_outputs(model,fixture,'fixture',np,stable_cls=stable,stable_points=True) if kind=='cold_response' else None
                        if kind=='cold_cat':values,why=model.predict(fixture)
                        else:values,why=replay['mean'].to_numpy(float),replay.fallback.to_numpy()
                        if not np.array_equal(np.asarray(values).view(np.uint64),old.point.to_numpy(float).view(np.uint64)) or list(why)!=old.fallback.tolist():raise ValueError('original saved fixture bits/fallback changed')
                    output=(law_outputs(model,q,cell['method'],np,stable_cls=stable,stable_points=kind=='cold_response') if kind!='cold_cat' else None)
                    if kind=='cold_cat':
                        values,why=model.predict(q);output=q[KEY+CONTEXT].copy();output['point']=values;output['mean']=np.nan;output['median']=np.nan;output['fallback']=why;output['method']=cell['method'];output['law_conditioning']='NONE_POINT_ONLY'
                else:
                    doc=json.loads(gzip.decompress(artifact),parse_float=str,parse_int=str)
                    if doc['target']!='nick-chart-ppr-v1' or int(doc['training']['season'])!=2024:raise ValueError('exact chart scoring/training contract required')
                    raw=base64.b64decode(doc['fitted_model_pickle_base64'],validate=True)
                    if sha(raw)!=cell['model_sha256'] or sha(raw)!=doc['fitted_model_sha256']:raise ValueError('trusted chart pickle identity differs')
                    owned(cell['clock_witness']);cw=json.loads(gzip.decompress(read(cell['clock_witness'])),parse_float=str,parse_int=str)
                    priorclock=pd.to_datetime([r['outcome_available_utc'] for r in cw['prior_training_binding']],utc=True)
                    if not len(priorclock) or priorclock.isna().any() or not (priorclock<min(tc,q.cutoff_utc.min())).all():raise ValueError('chart prior training not earlier')
                    if kind=='chart_hgb':
                        if cw['old_HGB_forecasts_sha256']!=cell['artifact']['sha256']:raise ValueError('chart HGB clock/source witness not linked')
                        bundle=pickle.loads(raw)
                        if bundle['target']!='nick-chart-ppr-v1' or bundle['features']!=chart.FEATURES or bundle['roles']!=ROLES:raise ValueError('chart HGB schema differs')
                        with threadpool_limits(limits=1):output=predict_chart_hgb(bundle,q,np)
                    elif kind=='chart_cdf':
                        model=chart.load_reviewed_model(raw,expected_sha256=cell['model_sha256']);records=[]
                        for at in range(0,len(q),4096):records+=chart.predict_reviewed(model,q.iloc[at:at+4096],source_policy_sha256=plan['historical_source_policy_sha256'],expected_source_policy_sha256=plan['historical_source_policy_sha256'])
                        output=q[KEY+CONTEXT].copy();output['mean']=[r['mean'] for r in records];output['median']=[r['median'] for r in records];output['point']=np.nan;output['fallback']=[r['fallback'] for r in records];output['method']='CHART_LEAF_CDF';output['law_scale']=50;output['law_conditioning']='played'
                        role=law_outputs(model,q,'CHART_ROLE_LAW',np,scale=50,prior_only=True)
                        output=pd.concat([output,role],ignore_index=True)
                    else:raise ValueError('unsupported retained format')
            output['target']=cell['target'];output['primary_role']=output.position.isin(cell.get('primary_roles',model.category['primary_roles'] if model is not None else ROLES))
            output['evidence_tier']=EVIDENCE;output['original_forecast_issued_at']=None
            output['model_artifact_sha256']=cell['artifact']['sha256'];output['source_features_sha256']=plan['features']['sha256']
            output['procedure_version']=sha(enc({'original_artifact':cell['artifact']['sha256'],'method':cell['method'],'source_adapter':VERSION,'augmentation':cell['augmenter']}))
            if cell['kind']=='chart_cdf':
                mask=output.method.eq('CHART_ROLE_LAW');output.loc[mask,'procedure_version']=sha(enc({'original_artifact':cell['artifact']['sha256'],'method':'CHART_ROLE_LAW','source_adapter':VERSION}))
            buf=io.BytesIO();q.to_parquet(buf,index=False,compression='zstd');features=write(cid+'/INFERENCE_FEATURES.parquet',buf.getvalue())
            buf=io.BytesIO();output.to_parquet(buf,index=False,compression='zstd');forecast=write(cid+'/FORECASTS.parquet',buf.getvalue())
            replay={'cell_id':cid,'artifact':cell['artifact'],'member':cell.get('member'),'features':features,
                'model_sha256':cell.get('model_sha256'),'source_modules':plan['source_modules'],'augmentation_audits':audits,
                'point_arithmetic':'Original fixed implementation; responseoriginalmeanusesexistingStableMixture arithmetic; chartZ/50 exactly.',
                'probability_arithmetic':'Separate normalized-cumulative-mixture-v1 law fromsamefittedparameters; no line-probability/EVclaim inthisfreeze.',
                'chart_contract':'nick-chart-ppr-v1' if cell['target']=='chart_ppr' else None,'scoring_scale':50 if cell['target']=='chart_ppr' else 1,
                'scope_weeks':cell['weeks'],'original_issue':None,'generated_UTC':pd.Timestamp.now(tz='UTC').isoformat(),'operational_admission':False}
            law=journal(cid+'/LAW_REPLAY.json',replay)
            result={'cell_id':cid,'target':cell['target'],'state':'FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED','rows':len(output),'query_rows':len(q),'games':int(q.game_id.nunique()),'weeks':cell['weeks'],'forecast':forecast,'features':features,'law_replay':law,'methods':sorted(output.method.unique()),'new_fits':0}
            journal(cid+'/COMPLETE.json',result);results.append(result)
        except BaseException as exc:
            failure={'cell_id':cid,'state':'FAILED_ATTEMPT_PRESERVED','exception_type':type(exc).__name__,'message':str(exc),'new_fits':0}
            journal(cid+'/FAILURE.json',failure);results.append(failure)
            if isinstance(exc,(KeyboardInterrupt,SystemExit,TimeoutError,MemoryError)):raise
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>caps['RSS_bytes']:raise MemoryError('followup RSS cap')
    batch_end=bulk('END')
    usage=store.verify_retained_checkpoint();result={'version':VERSION,'state':'FINITE_FOLLOWUP_TERMINAL','results':results,'new_fits':0,'model_restoration_attempts':restores,'query_plus_fixture_rows_charged':rows,'inclusive_private_write_bytes':charged,'reference_batch_start':batch_start,'reference_batch_end':batch_end,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'new_peer_physical_bytes':usage['new_peer_physical_bytes'],'scoring_runs':0,'production_writes':0,'offhost_restoration':'NOT_VERIFIED'}
    journal('TERMINAL.json',result);store.verify_retained_checkpoint();signal.alarm(0);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--go',type=Path,required=True);a=p.parse_args()
    print(json.dumps(execute(json.loads(a.plan.read_text()),json.loads(a.go.read_text())),sort_keys=True,allow_nan=False))
