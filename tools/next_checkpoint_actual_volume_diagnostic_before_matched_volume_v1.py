"""Two fixed postgame exposure diagnostics. These are not pregame forecasts."""
from pathlib import Path
import argparse,hashlib,importlib.util,io,json,os,resource,sys,time,zipfile

VERSION='actual-volume-diagnostic-v1'
KEY=['season','week','game_id','player_id']
CONTEXT=['team','opponent','position','kickoff_utc','cutoff_utc']


def hashed(ref):
    b=Path(ref['path']).read_bytes()
    assert len(b)==ref['bytes'] and hashlib.sha256(b).hexdigest()==ref['sha256']
    return b


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--go',required=True);a=parser.parse_args()
    b=Path(a.plan).read_bytes();assert hashlib.sha256(b).hexdigest()==a.sha256
    plan=json.loads(b);go=json.loads(Path(a.go).read_text())
    assert plan['state']=='ROOT_AND_REVIEWER_SEALED' and plan['execution_authorized'] is True
    assert go=={'state':'GO','root':'/root','scope':'POSTGAME_VOLUME_DIAGNOSTIC_NOT_FORECAST','plan_sha256':a.sha256,'independent_review':'PASS','previous_managed_writer_closed':True}
    assert plan['resources']=={'CPU_seconds':180,'wall_seconds':240,'RSS_bytes':805306368,'fits':0,'model_loads':0,'new_pregame_forecasts':0,'HTTP':0,'CAS_attempts_including_failure':2,'retained_bytes':4194304,'peak_bytes':8388608,'bootstrap_replicates':500,'seed':1703}
    assert hashed(plan['worker'])==Path(__file__).read_bytes()
    for ref in plan['inputs'].values():hashed(ref)
    for ref in plan['storage'].values():
        if isinstance(ref,dict) and 'path'in ref:hashed(ref)
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
    blocked={'network':0,'children':0}
    def guard(event,args):
        if event.startswith('socket.'):
            blocked['network']+=1;raise RuntimeError('offline diagnostic')
        if event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn']:
            blocked['children']+=1;raise RuntimeError('child-free diagnostic')
    sys.addaudithook(guard);resource.setrlimit(resource.RLIMIT_CPU,(180,181))
    started=time.monotonic();cpu=time.process_time();native=Path(plan['native'])
    assert not native.exists(),'one invocation; failure must be versioned'
    native.mkdir(parents=True)
    def write(name,d):
        b=(json.dumps(d,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();assert len(b)<65536
        with (native/name).open('xb') as f:f.write(b)
    def usage():return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'CAS_attempts':len(writes),'blocked_attempts':blocked}
    writes=[];store=None
    write('CONSUMED.json',{'state':'ONE_DIAGNOSTIC_INVOCATION_CONSUMED','plan_sha256':a.sha256,'fits':0,'new_forecast_issuance':0,'resources':plan['resources']})
    def check():
        u=usage();assert u['CPU_seconds']<178 and u['wall_seconds']<238 and u['RSS_bytes']<=805306368 and not any(blocked.values())
    try:
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        assert np.__version__=='2.3.5' and pd.__version__=='2.2.3' and pa.__version__=='23.0.1'
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        sp=plan['storage'];old=module(sp['original_helper']['path'],'volume_original_store');wrap=module(sp['helper']['path'],'volume_metadata')
        base=old.load_frozen(sp['forward_implementation']['path'],sp['legacy_library_root'])
        cls=wrap.build_storage_class(old.build_storage_class(base),json.loads(hashed(sp['metadata_descriptor'])))
        store=cls(sp['legacy_cache'],json.loads(hashed(sp['market_policy'])),json.loads(hashed(sp['legacy_policy'])),json.loads(hashed(sp['prior_policy'])))
        output=Path(plan['output']);assert output==store.live_root/'research'/VERSION and not output.exists()
        store.register_root(output)
        with store.transaction():store._refresh();store._require(8388608)
        def save(name,members):
            check();assert len(writes)<2
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                for k,v in members.items():z.writestr(k,v)
            body=stream.getvalue();retained=sum(x['bytes'] for x in writes)
            assert len(body)<=2097152 and retained+len(body)+262144<=4194304 and retained+2*len(body)+262144<=8388608
            # Count an attempted immutable CAS write before invoking the old writer.
            ref={'path':str(output/name),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()};writes.append(ref)
            store.write_bytes(output/name,body)
            checked=store.validate_reference(output/name)
            assert all(checked[k]==ref[k] for k in ['path','bytes','sha256'])
            assert (output/name).read_bytes()==body
            with zipfile.ZipFile(output/name) as z:
                assert set(z.namelist())==set(members) and all(z.read(k)==v for k,v in members.items())
            write(name.replace('.zip','_READBACK.json'),{'state':'EXACT_BYTES_READBACK_PASS','binding':ref})
            return ref
        def encoded(d):return (json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        def parquet(frame):
            sink=pa.BufferOutputStream();pq.write_table(pa.Table.from_pandas(frame,preserve_index=False),sink,compression='zstd');return sink.getvalue().to_pybytes()
        def table(name,columns,role=None):
            return pq.read_table(pa.BufferReader(hashed(plan['inputs'][name])),columns=columns,filters=[('position','=',role)] if role else None,use_threads=False).to_pandas()
        def context(f):
            f=f.copy()
            for k in ['season','week']:f[k]=f[k].astype(int)
            for k in ['game_id','player_id','team','opponent','position']:f[k]=f[k].astype(str)
            for k in ['kickoff_utc','cutoff_utc']:f[k]=pd.to_datetime(f[k],utc=True,errors='raise')
            assert not f.duplicated(KEY).any() and f.season.eq(2026).all() and f.week.between(1,6).all()
            assert f.cutoff_utc.notna().all() and f.kickoff_utc.notna().all() and (f.cutoff_utc<f.kickoff_utc).all()
            return f
        frames=[]
        for target,role,rate,ncol,expected in [('pass_yd','QB','f_player_pass_ypa3','f_player_pass_att_n3',515),('rush_yd','RB','f_player_rush_ypa3','f_player_rush_att_n3',668)]:
            cols=KEY+CONTEXT+['feature_max_source_available_utc',rate,ncol]
            q=context(table('query',cols,role));assert len(q)==expected
            f=context(table('forecast_'+target,KEY+CONTEXT+['median','fallback'],role))
            joined=q.merge(f,on=KEY+CONTEXT,how='left',validate='one_to_one',indicator=True)
            assert len(joined)==expected and joined['_merge'].eq('both').all() and np.isfinite(joined['median']).all()
            joined=joined.drop(columns='_merge').rename(columns={'median':'control_point',rate:'fixed_prior_rate',ncol:'prior_slot_numeric_count'})
            known=pd.to_datetime(joined.feature_max_source_available_utc,utc=True,errors='coerce')
            # Unknown max source time stays unknown; it cannot qualify a prior rate.
            joined['prior_rate_admitted']=known.notna() & (known<joined.cutoff_utc) & joined.prior_slot_numeric_count.gt(0) & np.isfinite(joined.fixed_prior_rate)
            joined['target']=target;frames.append(joined)
        frozen=pd.concat(frames,ignore_index=True)
        freeze=save('RECIPE_AND_FROZEN_CONTROLS.zip',{'CONTROLS_AND_PRIORS.parquet':parquet(frozen),'CONTRACT.json':encoded({'plan_sha256':a.sha256,'target_population':'1183 original2026primary query rows; no participation filtering','formula':'actual supported target-game attempts/carries times fixed pregame prior3YPA; unchanged control if rate/volume unsupported','lane':'POSTGAME_DIAGNOSTIC_NOT_FORECAST; actual volume is target-game outcome information','primary':'MAE','source_assumption':'Original seven-day/current-vintage reconstruction retained; no actual production timing bug asserted'})})
        assert len(frozen)==1183
        # Outcome decoding begins only after diagnostic recipe, old points and prior inputs are frozen.
        import gzip
        qual=json.loads(gzip.decompress(hashed(plan['inputs']['qualified_QB'])),parse_int=str,parse_float=str)['qualification']['records']
        qrows=frozen[frozen.target.eq('pass_yd')]
        qkeys={tuple(row[k] for k in KEY):row for row in qrows.to_dict('records')}
        mapped={}
        for z in qual:
            if z['target'] not in ['pass_yd','pass_att']:continue
            k=(int(z['season']),int(z['week']),str(z['game_id']),str(z['player_id']))
            if k not in qkeys:continue
            assert (k,z['target']) not in mapped
            expected=qkeys[k]
            assert z['team']==expected['team'] and z['opponent']==expected['opponent'] and pd.Timestamp(z['kickoff_utc'])==expected['kickoff_utc']
            mapped[k,z['target']]=z
        labels=[]
        for k,row in qkeys.items():
            y=mapped.get((k,'pass_yd'));v=mapped.get((k,'pass_att'))
            state=y['participation_state'] if y else 'unknown'
            assert state in ['played','unknown']
            actual=float(y['actual']) if y and y['actual'] is not None and state=='played' else None
            volume=float(v['actual']) if v and v['actual'] is not None and v['participation_state']=='played' else None
            labels.append({**{k:row[k] for k in KEY+CONTEXT},'target':'pass_yd','participation_state':state,'actual':actual,'actual_volume':volume,'volume_source':'qualified_QB_pass_att','raw_unqualified_value_quarantined':False})
        y=context(table('outcome_rush_yd',KEY+CONTEXT+['participation_state','actual'],'RB'))
        v=context(table('outcome_rush_att',KEY+CONTEXT+['participation_state','actual'],'RB')).rename(columns={'actual':'actual_volume','participation_state':'volume_participation'})
        rv=y.merge(v,on=KEY+CONTEXT,how='left',validate='one_to_one',indicator=True);assert len(rv)==668 and rv['_merge'].eq('both').all()
        rv['raw_unqualified_value_quarantined']=rv.actual.notna() & rv.participation_state.ne('played')
        rv.loc[rv.participation_state.ne('played'),'actual']=np.nan
        rv.loc[rv.volume_participation.ne('played'),'actual_volume']=np.nan
        rv['target']='rush_yd';rv['volume_source']='original_qualified_RB_rush_att';labels+=rv[KEY+CONTEXT+['target','participation_state','actual','actual_volume','volume_source','raw_unqualified_value_quarantined']].to_dict('records')
        graded=frozen.merge(pd.DataFrame(labels),on=KEY+CONTEXT+['target'],how='left',validate='one_to_one')
        assert len(graded)==1183 and graded.participation_state.notna().all()
        for target,expected in [('pass_yd',211),('rush_yd',526)]:
            part=graded[graded.target.eq(target)];assert int((part.participation_state.eq('played') & part.actual.notna()).sum())==expected
        supported=graded.participation_state.eq('played') & np.isfinite(graded.actual)
        volume_ok=np.isfinite(graded.actual_volume) & graded.actual_volume.ge(0) & graded.actual_volume.eq(np.floor(graded.actual_volume))
        use=supported & graded.prior_rate_admitted & volume_ok
        graded['diagnostic_point']=graded.control_point
        graded.loc[use,'diagnostic_point']=graded.loc[use,'actual_volume']*graded.loc[use,'fixed_prior_rate']
        graded['diagnostic_applied']=use;graded['diagnostic_fallback_reason']=np.select([~supported,~graded.prior_rate_admitted,~volume_ok],['target_unresolved_keep_control','prior_not_admitted_keep_control','volume_unresolved_keep_control'],default='')
        def metric(part,col):
            good=part.participation_state.eq('played') & np.isfinite(part.actual)
            e=part.loc[good,col].to_numpy(float)-part.loc[good,'actual'].to_numpy(float);a=np.abs(e)
            return {'planned':len(part),'scored':len(e),'games':int(part.loc[good,'game_id'].nunique()),'weeks':int(part.loc[good,'week'].nunique()),'players':int(part.loc[good,'player_id'].nunique()),'unknown':int(part.participation_state.eq('unknown').sum()),'played_missing':int((part.participation_state.eq('played') & part.actual.isna()).sum()),'MAE':float(a.mean()),'MSE':float((e*e).mean()),'RMSE':float(np.sqrt((e*e).mean())),'bias':float(e.mean()),'p95_absolute_error':float(np.quantile(a,.95)),'error_lt10':float((a<10).mean()),'error_le10':float((a<=10).mean())}
        def paired(part,cluster):
            part=part.loc[part.participation_state.eq('played') & np.isfinite(part.actual)].copy()
            part['delta']=abs(part.diagnostic_point-part.actual)-abs(part.control_point-part.actual);part['n']=1
            z=part.groupby(cluster,sort=True)[['delta','n']].sum().to_numpy(float);n=len(z);ci=None
            if n>=8:
                ids=np.random.default_rng(1703).integers(n,size=(500,n));draw=z[ids].sum(axis=1);ci=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()
            return {'delta_diagnostic_minus_control':float(part.delta.mean()),'paired_rows':len(part),'clusters':n,'nominal95_interval':ci,'replicates':500,'seed':1703,'minimum_clusters':8}
        results=[]
        for target,part in graded.groupby('target',sort=True):
            control=metric(part,'control_point');diagnostic=metric(part,'diagnostic_point')
            row={'target':target,'control':'original source-matched LeafCDFmedian','control_metrics':control,'postgame_actual_volume_diagnostic_metrics':diagnostic,'signed_MAE_improvement_percent':100*(control['MAE']-diagnostic['MAE'])/control['MAE'] if control['MAE'] else None,'actual_volume_used_scored':int(part.diagnostic_applied.sum()),'unchanged_control_fallbacks':int((~part.diagnostic_applied).sum()),'original_model_fallbacks':int(part.fallback.fillna('').ne('').sum()),'zero_volume_nonzero_target_rows':int((part.actual_volume.eq(0)&part.actual.notna()&part.actual.ne(0)).sum()),'game_interval':paired(part,'game_id'),'week_interval':paired(part,'week'),'weekly':{str(w):{'control':metric(t,'control_point'),'diagnostic':metric(t,'diagnostic_point')} for w,t in part.groupby('week')},'strata':{}}
            for name,mask in [('diagnostic_applied',part.diagnostic_applied),('unchanged_control_fallback',~part.diagnostic_applied),('supported_zero_exposure',part.actual_volume.eq(0))]:
                sub=part.loc[mask];n=int((sub.participation_state.eq('played')&sub.actual.notna()).sum())
                row['strata'][name]={'planned':len(sub),'scored':n} if n==0 else {'control':metric(sub,'control_point'),'diagnostic':metric(sub,'diagnostic_point')}
            results.append(row)
        result={'version':VERSION,'state':'POSTGAME_DIAGNOSTIC_COMPLETE_NOT_FORECAST','freeze':freeze,'results':results,'actual_backend':'UNATTESTED','new_predictive_fits':0,'new_pregame_forecasts':0,'new_market_or_probability_claim':False,'uses_actual_target_game_volume':True,'interpretation':'A difference diagnoses sensitivity to supplied realized volume under a fixed earlier rate. It is neither achievable pregame performance, a causal decomposition nor an irreducible error floor. Missing source inputs preserve registered control fallback.','source_timing':'Original assumed7day/currentvintage source policy; no live production timing conclusion','usage_before_final_write':usage()}
        grade=save('POSTGAME_DIAGNOSTIC_GRADE.zip',{'RESULT.json':encoded(result),'DIAGNOSTIC_ROWS.parquet':parquet(graded)})
        check();write('SUCCESS.json',{'state':result['state'],'freeze':freeze,'grade':grade,'usage':usage()})
        public=Path(plan['public_result']);assert not public.exists();public.write_bytes(encoded({**result,'grade':grade,'final_usage':usage()}))
        print(json.dumps({'state':result['state'],'results':[{k:v for k,v in x.items() if k in ['target','control_metrics','postgame_actual_volume_diagnostic_metrics','signed_MAE_improvement_percent','actual_volume_used_scored','game_interval']} for x in results],'usage':usage()}))
    except BaseException as error:
        record={'state':'DIAGNOSTIC_FAILURE_PRESERVED','error_type':type(error).__name__,'error':str(error),'usage':usage(),'new_pregame_forecasts':0,'fits':0,'automatic_retry':False}
        write('FAILURE.json',record)
        if store is not None and len(writes)<2:
            try:save('FAILURE.zip',{'FAILURE.json':(json.dumps(record,sort_keys=True)+'\n').encode()})
            except BaseException as retention:write('FAILURE_RETENTION.json',{'type':type(retention).__name__,'error':str(retention)})
        raise


if __name__=='__main__':main()
