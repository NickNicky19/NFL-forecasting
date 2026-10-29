"""Generate new median outputs from authenticated retained history models.

No fitting, source acquisition or feature rebuilding. Every original mean must
replay bit-for-bit before the new median vector can freeze. Target outcomes are
decoded only after that complete vector and its source identities read back.
"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.metadata,importlib.util,io,json,os,re,resource,signal,sys,time,zipfile

VERSION='opportunity-four-history-medians-v1-20261029'
KEYS=['season','week','game_id','player_id']
CONTEXT=['team','opponent','position','kickoff_utc','cutoff_utc']
METHODS={
 'CURRENT_ONLY':'CDF_H1_CURRENT_SEASON_TRAINING',
 'PRIOR_PLUS_CURRENT':'CDF_H2_PRIOR_PLUS_CURRENT_TRAINING',
 'TIME_WEIGHTED':'CDF_H3_TIME_WEIGHTED_TRAINING',
 'HISTORICAL_RELATION_CURRENT_STATE':'CDF_H4_HISTORICAL_RELATION_CURRENT_STATE',
 'HISTORICAL_RELATION_CURRENT_STATE_PLUS_ROLE':'CDF_H4_PLUS_TIMESTAMPED_DEPTH'}
CAPS={'CPU_seconds':90,'wall_seconds':150,'RSS_bytes':1024**3,'new_fits':0,
      'model_capsules':19,'model_loads':19,'new_median_rows':2575,
      'law_replay_query_rows':2575,'managed_write_attempts':3,
      'retained_private_bytes':16*1024**2,'peak_private_bytes':32*1024**2,
      'native_metadata_bytes':65536,'public_aggregate_bytes':196608,
      'bootstrap_replicates':500,'seed':1703,'HTTP':0,'automatic_retries':0}

def sha(body):return hashlib.sha256(body).hexdigest()
def encoded(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def auth(ref):
    p=Path(ref['path']);assert p.resolve()==p and not p.is_symlink()
    b=p.read_bytes();assert len(b)==ref['bytes'] and sha(b)==ref['sha256'];return b
def module(ref,name):
    auth(ref);s=importlib.util.spec_from_file_location(name,ref['path']);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
    a=argparse.ArgumentParser();a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--go',required=True);a=a.parse_args()
    body=Path(a.plan).read_bytes();assert sha(body)==a.sha256;p=json.loads(body)
    assert p['version']==VERSION and p['state']=='ROOT_AND_REVIEWER_SEALED' and p['execution_authorized'] is True and p['resources']==CAPS
    assert json.loads(Path(a.go).read_bytes())=={'state':'GO','root':'/root','independent_review':'PASS','scope':VERSION,'plan_sha256':a.sha256,'previous_managed_writer_closed':True}
    assert sys.flags.dont_write_bytecode
    for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
    for ref in p['source_pins'].values():auth(ref)
    inputs={k:auth(v) for k,v in p['inputs'].items()}
    native=Path(p['native_root']);assert not native.exists();native.mkdir(parents=True)
    cpu=time.process_time();wall=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(90,91))
    class Stop(BaseException):pass
    def stop(*unused):raise Stop('finite median extraction allocation consumed')
    signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGXCPU,stop);signal.setitimer(signal.ITIMER_REAL,145)
    blocked=[];writes=[];model_loads=law_rows=law_calls=0;store=None
    def deny(event,args):
        if event.startswith('socket.') or event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn']:
            blocked.append(event);raise Stop('offline childfree median extraction required')
    sys.addaudithook(deny)
    def usage():return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'model_loads':model_loads,'law_replay_query_rows':law_rows,'law_calls':law_calls,'new_fits':0,'new_mean_forecasts':0,'CAS_attempts':len(writes),'HTTP':0,'blocked_calls':blocked}
    def note(name,value):
        b=encoded(value);assert sum(f.stat().st_size for f in native.iterdir())+len(b)<=65536
        with (native/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    def check(retention_only=False):
        u=usage();assert u['CPU_seconds']<(89 if retention_only else 84) and u['wall_seconds']<(149 if retention_only else 145) and u['RSS_bytes']<=CAPS['RSS_bytes'] and (not blocked or retention_only)
    started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()
    note('CONSUMED.json',{'state':'ONE_EXTRACTION_ATTEMPT_CONSUMED','started_at_UTC':started_UTC,'experiment_id':'e:'+VERSION,'run_id':'r:'+VERSION,'plan_sha256':a.sha256,'resources':CAPS,'all_original_fits_budgets_preserved':True,'original_median_vectors_retained':False})
    try:
        protocol=json.loads(auth(p['public_protocol']))
        assert protocol['state']=='PUBLICATION_COMPLETE' and protocol['experiment_id']=='e:'+VERSION and protocol['run_id']=='r:'+VERSION
        assert re.fullmatch('[0-9a-f]{40}',protocol['commit']) and isinstance(protocol['readback_ref'],str)
        assert protocol['readback_ref'].startswith('https://github.com/NickNicky19/NFL-forecasting/blob/'+protocol['commit']+'/'),'authenticated root protocol readback must precede inference'
        import ctypes,threadpoolctl
        libc=Path(p['source_pins']['libc']['path']);assert Path(threadpoolctl.__file__).resolve()==Path(p['source_pins']['threadpoolctl']['path'])
        mapped={str(Path(z[5]).resolve()) for line in Path('/proc/self/maps').read_text().splitlines() if len(z:=line.split())==6 and z[5].startswith('/')}
        assert str(libc) in mapped and hasattr(os,'RTLD_NOLOAD');handle=ctypes.CDLL(str(libc),mode=os.RTLD_NOLOAD)
        oldhandle=threadpoolctl.ThreadpoolController._system_libraries.get('libc');assert oldhandle is None or oldhandle._handle==handle._handle
        threadpoolctl.ThreadpoolController._system_libraries['libc']=handle
        import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq,joblib
        from sklearn.ensemble import ExtraTreesRegressor
        for name,version in p['environment'].items():assert importlib.metadata.version(name)==version
        pa.set_cpu_count(1);pa.set_io_thread_count(1);sys.path.insert(0,p['worktree'])
        from nfl_lab import cdf_engine as cdf
        assert Path(cdf.__file__).resolve()==Path(p['source_pins']['cdf_engine']['path'])
        def no_fit(*args,**kwargs):raise Stop('ZERO_REFITS_MEDIAN_OUTPUT_CONTINUATION')
        ExtraTreesRegressor.fit=no_fit;cdf.LeafCDFModel.fit=classmethod(no_fit)
        sp=p['storage'];old=module(sp['original_helper'],'median_market');wrap=module(sp['helper'],'median_prior_meta')
        base=old.load_frozen(sp['forward_implementation']['path'],sp['legacy_library_root'])
        prior=wrap.build_storage_class(old.build_storage_class(base),json.loads(auth(sp['prior_metadata_descriptor'])))
        extension=module(sp['forward_metadata_helper'],'median_new_meta');cls=extension.build_storage_class(prior,json.loads(auth(sp['metadata_descriptor'])))
        store=cls(sp['legacy_cache'],json.loads(auth(sp['market_policy'])),json.loads(auth(sp['legacy_policy'])),json.loads(auth(sp['prior_policy'])))
        output=Path(p['output']);assert output==store.live_root/'research'/VERSION and not output.exists();store.register_root(output)
        with store.transaction():store._refresh();store._require(CAPS['peak_private_bytes'])
        from nfl_lab.owned_reference_batch import validate_owned_references
        owned_inputs=[p['inputs'][k] for k in ['query','original_forecast_freeze','original_grade','cached_base_cdf','original_control_freeze']]+list(p['model_capsules'].values())+[p['empty_initial_fallback']]
        ownership=[]
        def reference_owner(path):
            path=Path(path)
            if path.is_relative_to(store.forward_root):return store
            if path.is_relative_to(store.prior_forward.forward_root):return store.prior_forward
            return store.legacy
        for owner in [store.legacy,store.prior_forward,store]:
            refs={ref['path']:ref['sha256'] for ref in owned_inputs if reference_owner(ref['path']) is owner}
            if refs:
                checked,proof=validate_owned_references(owner,refs)
                assert set(checked)==set(refs)
                ownership.append({'validated_references':len(checked),'full_scan_calls':proof['full_scan_calls'],'lock_scope':proof['lock_scope'],'complete_proof_sha256':sha(encoded(proof)),'complete_proof_bytes':len(encoded(proof))})
        def save(name,members,retention_only=False):
            assert not retention_only or name=='FAILED.zip';check(retention_only=retention_only);assert len(writes)<3
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as z:
                for key,value in sorted(members.items()):z.writestr(key,value)
            b=stream.getvalue();retained=sum(x['bytes'] for x in writes)
            assert len(b)<=8*1024**2 and retained+len(b)+65536<=CAPS['retained_private_bytes'] and retained+2*len(b)+65536<=CAPS['peak_private_bytes']
            ref={'path':str(output/name),'bytes':len(b),'sha256':sha(b)};writes.append(ref);store.write_bytes(output/name,b)
            actual=store.validate_reference(output/name);assert all(actual[k]==ref[k] for k in ['path','bytes','sha256']) and (output/name).read_bytes()==b
            with zipfile.ZipFile(output/name) as z:assert set(z.namelist())==set(members) and all(z.read(k)==v for k,v in members.items())
            note(name.replace('.zip','_READBACK.json'),{'state':'PASS_CAPSULE_AND_INNER_BYTES','reference':ref,'members':{k:{'bytes':len(v),'sha256':sha(v)} for k,v in members.items()},'usage':usage()});return ref
        def parquet(f):
            f=f.copy();f.attrs.clear();stream=pa.BufferOutputStream();pq.write_table(pa.Table.from_pandas(f,preserve_index=False),stream,compression='zstd');return stream.getvalue().to_pybytes()
        save('EXTRACTION_CONSUMED.zip',{'CONSUMED.json':encoded({'plan_sha256':a.sha256,'new_fits':0,'max_retained_models':19,'max_new_medians':2575,'target_labels_decoded':False})})
        oldplan=json.loads(inputs['original_plan']);assert oldplan['version']==p['original_run_id']
        assert sha(inputs['original_plan'])==p['original_plan_sha256']
        with zipfile.ZipFile(io.BytesIO(inputs['original_forecast_freeze'])) as z:
            manifest=json.loads(z.read('MANIFEST.json'));oldbody=z.read('FORECASTS.parquet');rolebody=z.read('ROLE_QUERY_AUDIT.parquet')
        assert manifest['plan_sha256']==p['original_plan_sha256'] and manifest['model_capsules']==p['model_capsules'] and len(manifest['model_capsules'])==19
        assert manifest['forecast_member']=={'bytes':len(oldbody),'sha256':sha(oldbody)} and manifest['complete_evaluation_labels_decoded']==0
        original=pq.read_table(pa.BufferReader(oldbody),use_threads=False).to_pandas();assert len(original)==2575 and not original.duplicated(KEYS+['method']).any()
        fields=list(dict.fromkeys(KEYS+CONTEXT+['outcome_available_utc','feature_max_source_available_utc','is_home']+p['features']))
        query=pq.read_table(pa.BufferReader(inputs['query']),columns=fields,filters=[('season','=',2026),('position','=','QB'),('week','>=',1),('week','<=',6)],use_threads=False).to_pandas().reset_index(drop=True)
        query['participation_state']='unknown';assert len(query)==515 and query.game_id.nunique()==93 and not query.duplicated(KEYS).any();cdf.assert_clock_contract(query)
        rolecols=KEYS+CONTEXT+p['role_features']+['role_vendor_load_dt','role_known','role_clock_kind','role_publication_time']
        role=pq.read_table(pa.BufferReader(rolebody),columns=rolecols,use_threads=False).to_pandas();assert len(role)==515 and not role.duplicated(KEYS).any()
        for col in CONTEXT:assert query[col].astype(str).equals(role[col].astype(str))
        assert query[KEYS].equals(role[KEYS]);rclock=pd.to_datetime(role.role_vendor_load_dt,utc=True)
        assert (rclock.isna()|(rclock<=pd.to_datetime(query.cutoff_utc,utc=True))).all(),'preserve original inclusive vendor-load-clock rule; publicationunknown'
        cached_plan=json.loads(inputs['cached_base_scientific_plan'])
        with zipfile.ZipFile(io.BytesIO(inputs['original_control_freeze'])) as z:
            control_manifest=json.loads(z.read('MANIFEST.json'))
        assert cached_plan['inputs']['artifact_2026_att']==control_manifest['model_manifest'],'original model source binding differs'
        with zipfile.ZipFile(io.BytesIO(inputs['cached_base_cdf'])) as z:
            cachebytes=z.read('FORECASTS.parquet');cachemanifest=json.loads(z.read('MANIFEST.json'))
        assert cachemanifest['plan_sha256']==sha(inputs['cached_base_scientific_plan'])
        cached=pq.read_table(pa.BufferReader(cachebytes),columns=KEYS+CONTEXT+['point','fallback','method','target'],filters=[('season','=',2026),('target','=','pass_att'),('method','in',['CDF_LOWER_MEDIAN','CDF_LAW_MEAN_POINT'])],use_threads=False).to_pandas()
        assert len(cached)==1030 and set(cached.method)=={'CDF_LOWER_MEDIAN','CDF_LAW_MEAN_POINT'}
        meanrows=cached.loc[cached.method.eq('CDF_LAW_MEAN_POINT')].drop(columns=['method','target']).rename(columns={'point':'mean'})
        medianrows=cached.loc[cached.method.eq('CDF_LOWER_MEDIAN'),KEYS+['point','fallback']].rename(columns={'point':'median','fallback':'median_fallback'})
        basepoints=query[KEYS].merge(meanrows,on=KEYS,validate='one_to_one',how='left').merge(medianrows,on=KEYS,validate='one_to_one',how='left')
        assert basepoints.fallback.fillna('').equals(basepoints.median_fallback.fillna(''));basepoints=basepoints.drop(columns='median_fallback')
        assert len(basepoints)==515 and basepoints[['mean','median']].notna().all(axis=None)
        for col in CONTEXT:assert query[col].astype(str).equals(basepoints[col].astype(str))
        original_by_method={name:query[KEYS].merge(f,on=KEYS,validate='one_to_one',how='left') for name,f in original.groupby('method',sort=False)}
        assert set(original_by_method)==set(METHODS.values())
        for f in original_by_method.values():
            assert len(f)==515 and f.point.notna().all()
            for col in CONTEXT:assert query[col].astype(str).equals(f[col].astype(str))
        model_cache={};audit_proofs={};mean_parity=0;outputs=[]
        for policy,method in METHODS.items():
            f=query[KEYS+CONTEXT].copy();f['method']=method;f['mean']=original_by_method[method].point.to_numpy();f['median']=np.nan;f['fallback']=''
            for week in range(1,7):
                pos=np.flatnonzero(query.week.eq(week).to_numpy());view=query.iloc[pos].copy();fit_cutoff=pd.to_datetime(view.cutoff_utc,utc=True).min()
                role_model=policy.endswith('_PLUS_ROLE')
                slot=('2026-HISTORICAL_RELATION_CURRENT_STATE-ROLE-ANNUAL' if role_model else '2026-HISTORICAL_RELATION_CURRENT_STATE-ANNUAL' if policy=='HISTORICAL_RELATION_CURRENT_STATE' else f'2026-{policy}-W{week:02}')
                if role_model:
                    for col in p['role_features']:view[col]=role.iloc[pos][col].to_numpy()
                if slot=='2026-CURRENT_ONLY-W01':
                    expected=manifest['empty_initial_fallback_receipts'][slot];assert expected==p['empty_initial_fallback'];receipt=json.loads(auth(expected));assert receipt['eligible_training_rows']==0 and receipt['forest_fit_attempts']==0
                    fallback=True;model=None
                else:
                    if slot not in audit_proofs:
                        raw=auth(p['model_capsules'][slot])
                        with zipfile.ZipFile(io.BytesIO(raw)) as z:
                            assert set(z.namelist())=={'MODEL.joblib','TRAINING_BINDING.parquet','FIT_AUDIT.json'}
                            audit=json.loads(z.read('FIT_AUDIT.json'));mb=z.read('MODEL.joblib');tb=z.read('TRAINING_BINDING.parquet')
                        assert audit['slot']['id']==slot and audit['retention']['model_member']=={'bytes':len(mb),'sha256':sha(mb)} and audit['retention']['training_binding_member']=={'bytes':len(tb),'sha256':sha(tb)}
                        assert pd.Timestamp(audit['fit_cutoff_utc'])<=fit_cutoff
                        av=audit['maximum_training_label_available_utc'];assert av is None or pd.Timestamp(av)<pd.Timestamp(audit['fit_cutoff_utc'])
                        audit_proofs[slot]=audit
                        if not (policy=='CURRENT_ONLY' and audit['audit']['supported_played_training_rows']<60):
                            model_loads+=1;assert model_loads<=19;model=joblib.load(io.BytesIO(mb));assert type(model) is cdf.LeafCDFModel and model.panel=='base' and model.category['target']=='pass_att' and model.category['support']=='count'
                            assert model.category['panels']['base']==p['features']+(p['role_features'] if role_model else []) and model.audit==audit['audit'];model_cache[slot]=model
                    audit=audit_proofs[slot];fallback=policy=='CURRENT_ONLY' and audit['audit']['supported_played_training_rows']<60;model=model_cache.get(slot)
                means=np.full(len(view),np.nan);medians=np.full(len(view),np.nan);why=np.full(len(view),'',dtype=object)
                if fallback:
                    means[:]=basepoints.iloc[pos]['mean'].to_numpy();medians[:]=basepoints.iloc[pos]['median'].to_numpy();why[:]='under60_current_season_training_frozen_CDF_reference'
                else:
                    assert model is not None
                    # Preserve the original cut-group and batch ordering exactly.
                    for limit,ix in view.groupby('cutoff_utc',sort=False).indices.items():
                        ix=np.asarray(ix);part=view.iloc[ix].copy();law_calls+=1;law_rows+=len(part);assert law_rows<=2575
                        for bi,law,reasons in model.predict_batches(part,batch_size=256):
                            assert law is not None;means[ix[bi]]=law.mean;medians[ix[bi]]=law.quantile(.5);why[ix[bi]]=reasons
                assert np.isfinite(means).all() and np.isfinite(medians).all() and (medians>=0).all() and (medians==np.floor(medians)).all()
                expected_mean=original_by_method[method].iloc[pos].point.to_numpy(float)
                assert np.array_equal(means.astype(np.float64).view(np.uint64),expected_mean.astype(np.float64).view(np.uint64)),'originalmeanbitreplay mismatch; stop instead of silently accepting'
                assert np.array_equal(why.astype(str),original_by_method[method].iloc[pos].fallback.fillna('').astype(str).to_numpy()),'originalfallback routing differs'
                mean_parity+=len(view);f.loc[pos,'median']=medians;f.loc[pos,'fallback']=why
            outputs.append(f)
        assert mean_parity==2575 and len(audit_proofs)==19 and model_loads<=19
        f=basepoints.copy();f['method']='BASE_CDF_CACHED';outputs.append(f)
        frozen=pd.concat(outputs,ignore_index=True);assert len(frozen)==3090 and not frozen.duplicated(KEYS+['method']).any()
        frozen['output_version']=VERSION;frozen['new_median_output']=frozen.method.ne('BASE_CDF_CACHED')
        frozen['reconstruction_generated_at_UTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        freeze=save('MEDIAN_FORECAST_FREEZE.zip',{'FORECASTS.parquet':parquet(frozen),'QUERY.parquet':parquet(query),'ROLE_QUERY.parquet':parquet(role),'MODEL_AUDITS.json':encoded(audit_proofs),'PLAN.json':body,'OWNERSHIP.json':encoded(ownership),'MEAN_REPLAY.json':encoded({'rows':mean_parity,'all_bit_identical':True,'original_mean_outputs_not_replaced':True,'new_medians':2575})})
        # Evaluation labels are first decoded after complete immutable forecast readback.
        with zipfile.ZipFile(io.BytesIO(inputs['original_grade'])) as z:
            oldgrade=pq.read_table(pa.BufferReader(z.read('GRADED_ROWS.parquet')),columns=KEYS+CONTEXT+['method','actual','participation_state'],use_threads=False).to_pandas()
        labels=oldgrade.loc[oldgrade.method.eq('FROZEN_CDF_MEAN')].reset_index(drop=True)
        labels=query[KEYS].merge(labels,on=KEYS,how='left',validate='one_to_one');assert len(labels)==515
        for col in CONTEXT:assert query[col].astype(str).equals(labels[col].astype(str))
        assert labels.participation_state.value_counts().to_dict()=={'unknown':304,'played':211}
        assert labels.loc[labels.participation_state.ne('played'),'actual'].isna().all() and labels.loc[labels.participation_state.eq('played'),'actual'].notna().all()
        assert (labels.loc[labels.participation_state.eq('played'),'actual']==0).sum()==6
        graded=frozen.merge(labels[KEYS+['actual','participation_state']],on=KEYS,validate='many_to_one',how='left')
        pd.testing.assert_frame_equal(graded[list(frozen)],frozen,check_exact=True)
        def metric(t,col):
            good=t.participation_state.eq('played')&t.actual.notna()&t[col].notna();y=t.loc[good,'actual'].to_numpy(float);v=t.loc[good,col].to_numpy(float);e=v-y;ae=np.abs(e)
            assert cdf.valid_support(y,'count').all()
            return {'planned':len(t),'scored':len(y),'unknown':int(t.participation_state.eq('unknown').sum()),'played_zero':int((y==0).sum()),'fallbacks':int(t.fallback.fillna('').ne('').sum()),'scored_fallbacks':int((good&t.fallback.fillna('').ne('')).sum()),'games':int(t.loc[good,'game_id'].nunique()),'weeks':int(t.loc[good,'week'].nunique()),'MAE':float(ae.mean()),'MSE':float((e*e).mean()),'RMSE':float(np.sqrt((e*e).mean())),'bias':float(e.mean()),'p90_AE':float(np.quantile(ae,.9)),'p95_AE':float(np.quantile(ae,.95)),'strict_error_lt1':float((ae<1).mean()),'inclusive_error_le1':float((ae<=1).mean()),'exact_integer_match':float((v==y).mean()) if (v==np.floor(v)).all() else None,'exact_integer_match_reason':None if (v==np.floor(v)).all() else 'fractional_mean_without_registered_discrete_rounding_rule','rounding':'none'}
        metrics={str(m):{prod:metric(t,prod) for prod in ['mean','median']} for m,t in graded.groupby('method',sort=True)}
        contrasts=[]
        for method in METHODS.values():
            for functional in ['mean','median']:
                joined=graded.loc[graded.method.isin([method,'BASE_CDF_CACHED'])].pivot(index=KEYS,columns='method',values=functional)
                actual=labels.set_index(KEYS).actual;d=((joined[method]-actual).abs()-(joined['BASE_CDF_CACHED']-actual).abs()).dropna().reset_index(name='delta');d['n']=1
                intervals={}
                for cluster in ['game_id','week']:
                    values=d.groupby(cluster,sort=True)[['delta','n']].sum().to_numpy(float);n=len(values);ci=None
                    if n>=8:
                        ix=np.random.default_rng(1703).integers(n,size=(500,n));sim=values[ix].sum(axis=1);ci=np.quantile(sim[:,0]/sim[:,1],[.025,.975]).tolist()
                    intervals[cluster]={'clusters':n,'nominal95_interval':ci,'reason':None if ci is not None else 'fewer_than8clusters'}
                contrasts.append({'method':method,'functional':functional,'comparator':'BASE_CDF_CACHED','paired_rows':len(d),'candidate_minus_control_MAE':float(d.delta.mean()),'relative_improvement_percent':100*(metrics['BASE_CDF_CACHED'][functional]['MAE']-metrics[method][functional]['MAE'])/metrics['BASE_CDF_CACHED'][functional]['MAE'],'intervals':intervals,'multiplicity':'nominal descriptive10productcontrasts; selectedminimum notscientificqualification'})
        result={'version':VERSION,'state':'NEW_MEDIAN_OUTPUT_COMPARISON_COMPLETE','new_fits':0,'new_median_forecast_rows':2575,'replayed_original_mean_rows':mean_parity,'cached_base_rows':515,'saved_method_rows':3090,'primary':'median_MAE; allvalidmeans separately retained forpointMAE','metrics':metrics,'paired':contrasts,'weekly':{str(week):{str(m):{prod:metric(t,prod) for prod in ['mean','median']} for m,t in g.groupby('method',sort=True)} for week,g in graded.groupby('week',sort=True)},'coverage':{'plannedQB':515,'supported':211,'unknown':304,'played_zero':6,'games':93,'weeks':6,'targetscope_requested':'2026W1-7','week7':'NOT_IN_RETAINED_SAME_SOURCE_QUERIES; separate feature/population/label admission required'},'new_pregame_capture_admission_deployment':0,'proper_probabilities_and_OverUnder_EV':None,'unsupported_probability_reason':'This output continuation extracts points; no authentic matched offeredpool/prices or probabilitycomparison','evidence':'Exposed2026W1-6 current-vintage reconstruction, old7day availability and original role vendorload clocks preserved; no currentwebsitegain or originalmedianvector reproduction claim','fallback':'H1under60 uses originalfallbackCDF median/mean fromauthenticatedcachedlaw functionals; no inventedprior','oldmean_contract':'All2575 replayedmeanbits andfallbackreasons unchanged; meansnotrelabeledmedians','freeze':freeze,'usage_before_grade':usage()}
        grade=save('MEDIAN_GRADE_COMPLETE.zip',{'RESULT.json':encoded(result),'GRADED_ROWS.parquet':parquet(graded),'SOURCE_BINDINGS.json':encoded(p['inputs'])})
        check();note('COMPLETE.json',{'state':result['state'],'started_at_UTC':started_UTC,'finished_at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'experiment_id':'e:'+VERSION,'run_id':'r:'+VERSION,'freeze':freeze,'grade':grade,'usage':usage(),'managed_writer':'CLOSED'})
        data=encoded({**result,'grade':grade,'usage':usage()});assert len(data)<=CAPS['public_aggregate_bytes'];Path(p['result']).write_bytes(data)
        print(json.dumps({'state':result['state'],'new_fits':0,'primary_MAE':{m:v['median']['MAE'] for m,v in metrics.items()},'usage':usage(),'freeze':freeze,'grade':grade}))
    except BaseException as exc:
        record={'state':'MEDIAN_OUTPUT_ATTEMPT_FAILED_RETAINED','started_at_UTC':started_UTC,'finished_at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'experiment_id':'e:'+VERSION,'run_id':'r:'+VERSION,'type':type(exc).__name__,'error':str(exc),'usage':usage(),'automatic_retry':False};note('FAILED.json',record)
        if store is not None and len(writes)<3 and 'save' in locals():
            try:
                members={'FAILED.json':encoded(record),'PLAN.json':body}
                if 'freeze' in locals():
                    members['COMPLETED_FREEZE_REFERENCE.json']=encoded(freeze)
                    if 'graded' in locals():members['GRADED_ROWS_PARTIAL.parquet']=parquet(graded)
                    if 'result' in locals():members['RESULT_PARTIAL.json']=encoded(result)
                    elif 'metrics' in locals():members['METRICS_PARTIAL.json']=encoded(metrics)
                else:
                    if 'outputs' in locals() and outputs:members['PARTIAL_MEDIAN_FORECASTS.parquet']=parquet(pd.concat(outputs,ignore_index=True))
                    if 'f' in locals() and hasattr(f,'columns') and 'median' in f:members['PARTIAL_ACTIVE_METHOD.parquet']=parquet(f)
                    if 'view' in locals() and 'means' in locals() and 'medians' in locals():
                        active=view[KEYS+CONTEXT].copy();active['partial_mean_replay']=means;active['partial_new_median']=medians
                        active['method']=method;members['PARTIAL_ACTIVE_VECTORS.parquet']=parquet(active)
                save('FAILED.zip',members,retention_only=True)
            except BaseException as retention:note('FAILURE_RETENTION.json',{'type':type(retention).__name__,'error':str(retention)})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

if __name__=='__main__':main()
