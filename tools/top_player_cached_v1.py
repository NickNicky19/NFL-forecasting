"""Frozen pre-week opportunity cohorts; cached predictions only, no fitting.

This is an exposed historical diagnostic. Ranking is common to every compared
method and is persisted before any target evaluation labels are decoded.
"""
from pathlib import Path
from collections import Counter
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import resource
import signal
import sys
import threading
import time
import zipfile

VERSION = 'top-player-cached-v1-20261028'
MIB = 1024**2
KEY = ['season','week','game_id','player_id','team','opponent']
CONTEXT = KEY + ['position','kickoff_utc','cutoff_utc']
TARGETS = ['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att',
           'rec','rec_yd','rush_rec_yd','anytime_td','chart_ppr']
GROUPS = ['full','top10','top15','top20','rank1_10','rank11_15','rank16_20','remainder','unranked']
CAPS = {'CPU_seconds':120,'wall_seconds':180,'RSS_bytes':768*MIB,'fits':0,'model_loads':0,
        'new_forecast_inference':0,'HTTP':0,'automatic_retries':0,'threads':1,
        'invocations':1,'managed_write_attempts':2,'retained_private_bytes':4*MIB,
        'peak_private_bytes':8*MIB,'native_metadata_bytes':64*1024,
        'safe_aggregate_bytes':1024*1024,'bootstrap_replicates':500,'seed':1703}


def digest(b): return hashlib.sha256(b).hexdigest()


def encoded(x):
    return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def public_aggregate(x):
    """Lossless, deterministic safe-aggregate transport; never a row dataset."""
    raw=encoded(x)
    body=gzip.compress(raw,compresslevel=6,mtime=0)
    return body,{'encoding':'GZIP_UTF8_JSON','uncompressed_bytes':len(raw),
                 'uncompressed_sha256':digest(raw),'compressed_bytes':len(body),
                 'compressed_sha256':digest(body),'all_weekly_group_records_retained':True}


def auth(ref):
    p=Path(ref['path'])
    if not p.is_absolute() or p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('canonical nonsymlink inputs required')
    a=p.stat();b=p.read_bytes();z=p.stat()
    if len(b)!=ref['bytes'] or digest(b)!=ref['sha256'] or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns):
        raise ValueError('input binding changed: '+str(p))
    return b


def module(ref,name):
    auth(ref);spec=importlib.util.spec_from_file_location(name,ref['path']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def teams(s): return s.replace({'LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'})


def main():
    clock,cpu=time.monotonic(),time.process_time()
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--go',required=True);a=parser.parse_args()
    raw=Path(a.plan).read_bytes()
    if digest(raw)!=a.sha256:raise ValueError('exact root plan required')
    plan=json.loads(raw);go=json.loads(Path(a.go).read_bytes())
    if (plan['version']!=VERSION or plan['resources']!=CAPS or plan['state']!='ROOT_AND_REVIEWER_SEALED'
        or plan['execution_authorized'] is not True or plan['review']!='PREEXEC_PASS'
        or go!={'state':'GO','registered_by':'/root','independent_review':'PASS','scope':VERSION,'plan_sha256':a.sha256}):
        raise ValueError('independent root seal and exact GO required before NFL decode')
    if auth(plan['worker'])!=Path(__file__).read_bytes() or not sys.flags.dont_write_bytecode:
        raise ValueError('exact worker and -B required')
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','ARROW_NUM_THREADS','ARROW_IO_THREADS']:os.environ[k]='1'
    attempted=Counter()
    def audit(event,args):
        if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.fork','os.forkpty','os.posix_spawn','os.posix_spawnp'}:
            attempted[event]+=1;raise ValueError('offline child-free cached study')
    sys.addaudithook(audit)
    resource.setrlimit(resource.RLIMIT_CPU,(120,121))
    class Stop(BaseException):pass
    def stop(*args):raise Stop('finite resource allocation consumed')
    signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGXCPU,stop);signal.signal(signal.SIGUSR1,stop);signal.setitimer(signal.ITIMER_REAL,170)
    done=threading.Event()
    def usage():return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-clock,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'CAS_attempts':writes,'fits':0,'model_loads':0,'new_forecast_inference':0,'HTTP':0}
    def check():
        if time.process_time()-cpu>118 or time.monotonic()-clock>170 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>CAPS['RSS_bytes']:raise Stop('finite runtime exhausted')
    def watch():
        while not done.wait(.1):
            try:check()
            except BaseException:os.kill(os.getpid(),signal.SIGUSR1);return
    threading.Thread(target=watch,daemon=True).start()
    native=Path(plan['native_root'])
    if native.exists():raise ValueError('original attempt namespace remains consumed')
    native.mkdir(parents=True);native_bytes=0;writes=0;retained=0;storage=None;references={}
    def note(name,x):
        nonlocal native_bytes
        b=encoded(x)
        if native_bytes+len(b)>CAPS['native_metadata_bytes']:raise ValueError('native metadata cap')
        with (native/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        native_bytes+=len(b)
    note('CONSUMED.json',{'state':'ONE_INVOCATION_CONSUMED_BEFORE_NFL_DECODE','plan_sha256':a.sha256,'resources':CAPS,'prior_attempts_and_caps_unchanged':True})
    try:
        import numpy as np
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        if np.__version__!='2.3.5' or pd.__version__!='2.2.3' or pa.__version__!='23.0.1':raise ValueError('environment differs')
        # Read/authenticate exact registered bytes once; no unregistered paths.
        bodies={k:auth(v) for k,v in plan['inputs'].items()}
        helper=module(plan['storage']['original_helper'],'top_original_store')
        wrapper=module(plan['storage']['helper'],'top_forward_metadata')
        sp=plan['storage'];base=helper.load_frozen(sp['forward_implementation']['path'],sp['legacy_library_root'])
        cls=wrapper.build_storage_class(helper.build_storage_class(base),json.loads(auth(sp['metadata_descriptor'])))
        storage=cls(sp['legacy_cache'],json.loads(auth(sp['market_policy'])),json.loads(auth(sp['legacy_policy'])),json.loads(auth(sp['prior_policy'])))
        destination=Path(plan['output'])
        if destination!=storage.live_root/'research'/VERSION or destination.exists():raise ValueError('fresh registered research namespace required')
        storage.register_root(destination)
        with storage.transaction():storage._refresh();initial_capacity=storage._require(CAPS['peak_private_bytes'])
        def save(name,members):
            nonlocal writes,retained
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                for name_,body in sorted(members.items()):
                    info=zipfile.ZipInfo(name_,date_time=(2026,10,28,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,body)
            b=stream.getvalue();writes+=1
            if (writes>2 or retained+len(b)+256*1024>CAPS['retained_private_bytes']
                    or retained+2*len(b)+256*1024>CAPS['peak_private_bytes']):raise ValueError('fixed complete CAS budget exhausted')
            storage.write_bytes(destination/name,b);ref=storage.validate_reference(destination/name);retained+=len(b)
            back=(destination/name).read_bytes()
            if back!=b:raise ValueError('private CAS readback differs')
            references[name]={'path':str(destination/name),'bytes':len(b),'sha256':digest(b)}
            note(name.replace('.zip','_READBACK.json'),{'state':'EXACT_BYTES_READBACK','reference':references[name],'members':{k:{'bytes':len(v),'sha256':digest(v)} for k,v in members.items()},'usage':usage()})
            return references[name]
        def table(name,columns,member=None,filters=None,clock_qualified=False):
            b=bodies[name]
            if member:
                with zipfile.ZipFile(io.BytesIO(b)) as z:b=z.read(member)
            value=pq.read_table(pa.BufferReader(b),columns=columns,filters=filters,use_threads=False)
            removed=0
            if clock_qualified:
                keys_=zip(value.column('player_id').to_pylist(),value.column('game_id').to_pylist())
                mask=pa.array([(str(x),str(y)) in qualified_clock_keys for x,y in keys_],type=pa.bool_())
                before=len(value);value=value.filter(mask);removed=before-len(value)
            frame=value.to_pandas();frame.attrs['unqualified_clock_rows_removed']=removed
            return frame
        def context(f):
            f=f.copy()
            for col in ['player_id','game_id','team','opponent','position']:
                if f[col].isna().any():raise ValueError('null source identity')
                f[col]=f[col].astype(str)
            f['team']=teams(f.team);f['opponent']=teams(f.opponent)
            f['season']=pd.to_numeric(f.season).astype(int);f['week']=pd.to_numeric(f.week).astype(int)
            if not (f.season.eq(2026)&f.week.between(1,6)).all():raise ValueError('protected or unexpected query period')
            for col in ['kickoff_utc','cutoff_utc']:
                if col in f:f[col]=pd.to_datetime(f[col],utc=True,errors='coerce')
            if f.duplicated(KEY).any():raise ValueError('duplicate canonical opportunity')
            return f
        query=context(table('query',CONTEXT+['feature_max_source_available_utc']))
        if len(query)!=2999 or query.kickoff_utc.isna().any() or query.cutoff_utc.isna().any() or not (query.cutoff_utc<=query.kickoff_utc).all():raise ValueError('full original historical-left-limit query/cutoff contract')
        maxsource=pd.to_datetime(query.feature_max_source_available_utc,utc=True,errors='coerce')
        if (maxsource.notna()&~maxsource.lt(query.cutoff_utc)).any():raise ValueError('future/equal history source clock admitted')
        original_query_clock_census={'queries':len(query),'cutoff_before_kickoff':int(query.cutoff_utc.lt(query.kickoff_utc).sum()),'cutoff_equal_kickoff':int(query.cutoff_utc.eq(query.kickoff_utc).sum()),'claim':'Original current-vintage historical left-limit, NOT genuine originally issued pregame forecasts. Live/capture strict guards unchanged.'}
        projection=module(plan['projection_helper'],'top_json_projection')
        chart_raw=gzip.decompress(bodies['chart_forecast'])
        if len(chart_raw)>16*MIB:raise ValueError('chart expansion cap')
        id_fields={('forecasts','*','identity',k) for k in KEY+['season_type']}|{('forecasts','*',k) for k in ['position','cutoff_utc','kickoff_utc']}
        projected,projection_qa=projection.project(chart_raw,id_fields,maximum_bytes=16*MIB)
        chart_rows=[{**x['identity'],**{k:x[k] for k in ['position','cutoff_utc','kickoff_utc']}} for x in projected['forecasts']]
        chart=context(pd.DataFrame(chart_rows))
        if len(chart)!=2117:raise ValueError('full chart source-listed population')
        # Use a qualified calendar for missing fallback clocks; never replace the
        # forecast's missing clock. Rank deadlines and forecast clocks are distinct.
        cal=pd.read_csv(io.BytesIO(bodies['schedule']),usecols=['game_id','season','week','game_type','gameday','gametime','away_team','home_team'],dtype={'game_id':str})
        cal=cal.loc[cal.season.eq(2026)&cal.week.between(1,6)&cal.game_type.eq('REG')].copy()
        if cal.game_id.duplicated().any():raise ValueError('duplicate schedule identity')
        cal['calendar_kickoff']=pd.to_datetime(cal.gameday+' '+cal.gametime,errors='coerce').dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('UTC')
        calendar=cal.set_index('game_id')
        for f in [query,chart]:
            f['calendar_kickoff']=f.game_id.map(calendar.calendar_kickoff)
            if f.calendar_kickoff.isna().any():raise ValueError('query lacks qualified schedule clock')
            known=f.kickoff_utc.notna()
            if not (f.loc[known,'kickoff_utc']==f.loc[known,'calendar_kickoff']).all():raise ValueError('query/calendar kickoff differs')
            for row in f[KEY].itertuples(index=False):
                event=calendar.loc[row.game_id]
                if row.week!=int(event.week) or {row.team,row.opponent}!={teams(pd.Series([event.home_team])).iloc[0],teams(pd.Series([event.away_team])).iloc[0]}:raise ValueError('calendar game/week/team identity differs')
        history_schema=pq.ParquetFile(pa.BufferReader(bodies['history'])).schema_arrow
        if any(not pa.types.is_timestamp(history_schema.field(k).type) or history_schema.field(k).type.tz!='UTC' for k in ['kickoff_utc','outcome_available_utc']):raise ValueError('qualified Arrow timestamp pushdown schema changed')
        history_clock=table('history',['player_id','game_id','kickoff_utc','outcome_available_utc'])
        # Raw source assumptions are retained; no known publication time fabricated.
        for col in ['kickoff_utc','outcome_available_utc']:history_clock[col]=pd.to_datetime(history_clock[col],utc=True,errors='coerce')
        source_unknown_clock=int((history_clock.kickoff_utc.isna()|history_clock.outcome_available_utc.isna()).sum())
        # Qualify identity-level clocks BEFORE row predicates can hide an
        # unknown/conflicting duplicate. This projection contains no statistics.
        for col in ['player_id','game_id']:history_clock[col]=history_clock[col].astype('string')
        clock_groups=history_clock.groupby(['player_id','game_id'],dropna=False,sort=False).agg(
            rows=('game_id','size'),kickoff_known=('kickoff_utc','count'),available_known=('outcome_available_utc','count'),
            kickoff_distinct=('kickoff_utc','nunique'),available_distinct=('outcome_available_utc','nunique'),
            kickoff=('kickoff_utc','min'),available=('outcome_available_utc','min'))
        valid_identity=clock_groups.index.to_frame(index=False).notna().all(axis=1).to_numpy()
        valid_clock=(valid_identity & clock_groups.kickoff_known.eq(clock_groups.rows).to_numpy()
            & clock_groups.available_known.eq(clock_groups.rows).to_numpy()
            & clock_groups.kickoff_distinct.eq(1).to_numpy() & clock_groups.available_distinct.eq(1).to_numpy()
            & clock_groups.available.ge(clock_groups.kickoff).to_numpy())
        qualified_clock_keys={tuple(str(v) for v in k) for k in clock_groups.index[valid_clock]}
        unqualified_clock_keys=int((~valid_clock).sum())
        rows=[];deadlines={};rank_source_audit=[]
        for week in range(1,7):
            check();q=query.loc[query.week.eq(week)];p=chart.loc[chart.week.eq(week)]
            deadline=min(q.calendar_kickoff.min()-pd.Timedelta(hours=6),q.cutoff_utc.min(),p.cutoff_utc.min())
            if pd.isna(deadline):raise ValueError('unknown shared ranking deadline')
            deadlines[str(week)]=str(deadline)
            # Arrow row predicates expose only legitimate prior opportunity
            # records to Python. Future target values are not projected here.
            history=table('history',['season','week','game_id','player_id','team','opponent','kickoff_utc','outcome_available_utc','participation_state','pass_att','rush_att','rec_tgt'],
                filters=[('kickoff_utc','<',deadline.to_pydatetime()),('outcome_available_utc','<',deadline.to_pydatetime())],clock_qualified=True)
            clock_quarantined_rows=history.attrs['unqualified_clock_rows_removed']
            for col in ['kickoff_utc','outcome_available_utc']:history[col]=pd.to_datetime(history[col],utc=True,errors='coerce')
            if not (history.kickoff_utc.lt(deadline)&history.outcome_available_utc.lt(deadline)).all():raise ValueError('future/unknown ranking source admitted')
            for col in ['player_id','game_id','team','opponent']:history[col]=history[col].astype('string')
            history['team']=teams(history.team);history['opponent']=teams(history.opponent)
            bad_identity=history[['player_id','game_id','team','opponent']].isna().any(axis=1)
            invalid_identity_count=int(bad_identity.sum());history=history.loc[~bad_identity].copy()
            dupcols=['player_id','game_id','kickoff_utc','outcome_available_utc','team','opponent','participation_state','pass_att','rush_att','rec_tgt']
            history=history.drop_duplicates(dupcols)
            conflict=history.duplicated(['player_id','game_id'],keep=False)
            conflicting_slots=int(history.loc[conflict,['player_id','game_id']].drop_duplicates().shape[0])
            # Conflicting values occupy a missing chronological slot; ambiguous
            # clocks stay unavailable rather than becoming a fabricated time.
            if conflict.any():
                def same_known_clock(x):return x.iloc[0] if x.notna().all() and x.nunique()==1 else pd.NaT
                bad=history.loc[conflict].groupby(['player_id','game_id'],sort=False).agg({'kickoff_utc':same_known_clock,'outcome_available_utc':same_known_clock,'season':'max','week':'max','team':'first','opponent':'first'}).reset_index()
                bad['participation_state']='rank_source_conflict'
                for k in ['pass_att','rush_att','rec_tgt']:bad[k]=np.nan
                history=pd.concat([history.loc[~conflict],bad],ignore_index=True)
            eligible=history.loc[history.kickoff_utc.lt(deadline)&history.outcome_available_utc.lt(deadline)].sort_values(['player_id','kickoff_utc','game_id'])
            # Admit by availability first, then recent by actual game chronology.
            slots=eligible.groupby('player_id',sort=False).tail(8)
            grouped={str(k):x for k,x in slots.groupby('player_id',sort=False)}
            rank_source_audit.append({'week':week,'deadline':str(deadline),'eligible_history_rows':len(eligible),'last8_slot_rows':len(slots),'history_unknown_clocks_retained_unavailable':source_unknown_clock,'global_unqualified_clock_keys':unqualified_clock_keys,'clock_quarantined_rows_before_statistic_exposure':clock_quarantined_rows,'invalid_identity_quarantined':invalid_identity_count,'conflicting_slots':conflicting_slots})
            for target in TARGETS:
                entry=plan['categories'][target];pool=(p if target=='chart_ppr' else q).loc[lambda f:f.position.isin(entry['roles'])].copy()
                for role,part in pool.groupby('position',sort=True):
                    values={}
                    family=entry['rank_by_role'][role]
                    fields={'pass_att':['pass_att'],'rush_att':['rush_att'],'rec_tgt':['rec_tgt'],'touches':['rush_att','rec_tgt']}[family]
                    for player in part.player_id.unique():
                        h=grouped.get(player)
                        if h is None:
                            values[player]={'rank_score':None,'rank_history_slots':0,'rank_known_slots':0,'rank_unknown_slots':0,'rank_last_game':None,'rank_max_available':None,'rank_state':'no_available_prior_slots'};continue
                        numeric=h[fields].apply(pd.to_numeric,errors='coerce').to_numpy(float)
                        good=h.participation_state.eq('played').to_numpy()&np.isfinite(numeric).all(axis=1)&(numeric>=0).all(axis=1)&(numeric==np.floor(numeric)).all(axis=1)
                        score=float(numeric[good].sum(axis=1).mean()) if good.any() else None
                        values[player]={'rank_score':score,'rank_history_slots':len(h),'rank_known_slots':int(good.sum()),'rank_unknown_slots':int(h.participation_state.eq('unknown').sum()),'rank_last_game':str(h.kickoff_utc.max()),'rank_max_available':str(h.outcome_available_utc.max()),'rank_state':'supported_prior_opportunity_mean8' if score is not None else 'no_supported_numeric_opportunities'}
                    ranked=sorted((x for x,v in values.items() if v['rank_score'] is not None),key=lambda x:(-values[x]['rank_score'],x))
                    ranks={player:i+1 for i,player in enumerate(ranked)}
                    for row in part.to_dict('records'):
                        rank=ranks.get(row['player_id']);band='remainder' if rank is None or rank>20 else 'rank1_10' if rank<=10 else 'rank11_15' if rank<=15 else 'rank16_20'
                        rows.append({**{k:row[k] for k in CONTEXT},'target':target,'rank_family':family,'rank_deadline':deadline,'rank':rank,'rank_band':band,'forecast_clock_state':'known' if pd.notna(row['cutoff_utc']) and pd.notna(row['kickoff_utc']) else 'original_clock_unknown','calendar_kickoff':row['calendar_kickoff'],**values[row['player_id']]})
        membership=pd.DataFrame(rows)
        if membership.duplicated(['target',*KEY]).any():raise ValueError('duplicate target membership')
        expected=sum(plan['categories'][t]['expected_queries'] for t in TARGETS)
        if len(membership)!=expected:raise ValueError('full category membership differs')
        for target in TARGETS:
            if int(membership.target.eq(target).sum())!=plan['categories'][target]['expected_queries']:raise ValueError('predeclared category population differs')
        buf=io.BytesIO();membership.to_parquet(buf,index=False,compression='zstd')
        frozen=save('MEMBERSHIPS_FROZEN.zip',{'MEMBERSHIPS.parquet':buf.getvalue(),'MANIFEST.json':encoded({'state':'ALL12_COMMON_WEEKLY_MEMBERSHIPS_FROZEN_BEFORE_EVALUATION_LABELS','plan_sha256':a.sha256,'deadlines':deadlines,'rows':len(membership),'rule':plan['ranking'],'input_bindings':plan['inputs'],'rank_source_audit':rank_source_audit,'original_query_clock_census':original_query_clock_census,'target_evaluation_labels_decoded':0,'model_loads':0,'fits':0})})
        # Only now load cached forecast products and target labels.
        predictions=[];labels=[]
        def add_forecast(f,target,method,product,column='point'):
            f=context(f);f=f.loc[f.position.isin(plan['categories'][target]['roles'])].copy()
            if len(f)!=plan['categories'][target]['expected_queries']:raise ValueError('complete model population differs '+target+'/'+method)
            f['prediction']=pd.to_numeric(f[column],errors='coerce');f['method']=method;f['product']=product;f['target']=target
            if not np.isfinite(f.prediction.to_numpy(float)).all():raise ValueError('registered model missing/nonfinite forecast '+target+'/'+method)
            if target=='chart_ppr':source='chart_forecast'
            elif method=='COUNT_A_MEAN':source='count_a_forecast'
            elif method in ['RESPONSE_CDF_MEAN','CATBOOST_COUNT_MEAN']:source='cold_'+target
            elif method=='CATBOOST_MEDIUM':source='original_'+target+'_CAT'
            elif method=='TD_EQUAL_CDF_CAT':source='original_anytime_td_CDF+original_anytime_td_CAT'
            elif method=='LAB_CDF':source='original_'+target+'_CDF'
            elif target in ['pass_td','pass_att','pass_int']:source='count_completion_forecast'
            elif target in ['pass_cmp','rush_att','rec']:source='modern_cdf_forecast'
            else:source='original_'+target+'_CDF'
            f['source_forecast_input']=source
            predictions.append(f[CONTEXT+['prediction','fallback','method','product','target','source_forecast_input']])
        for target in ['pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td']:
            for method in ['CDF','CAT']:
                name='original_'+target+'_'+method
                columns=CONTEXT+['point','fallback']+(['mean','median'] if method=='CDF' else [])
                f=table(name,columns)
                if target=='anytime_td':add_forecast(f,target,'LAB_CDF' if method=='CDF' else 'CATBOOST_MEDIUM','probability')
                elif method=='CDF':
                    add_forecast(f,target,'CDF_MEDIAN','median','median');add_forecast(f,target,'CDF_MEAN','mean','mean')
                else:add_forecast(f,target,'CATBOOST_MEDIUM','median_objective_point')
        with zipfile.ZipFile(io.BytesIO(bodies['count_completion_forecast'])) as z:
            f=pq.read_table(pa.BufferReader(z.read('FORECASTS.parquet')),columns=CONTEXT+['point','fallback','method','target'],use_threads=False).to_pandas()
        f=f.loc[f.season.eq(2026)]
        for target in ['pass_td','pass_att','pass_int']:
            for name,new,prod in [('CDF_LOWER_MEDIAN','CDF_MEDIAN','median'),('CDF_LAW_MEAN_POINT','CDF_MEAN','mean')]:
                add_forecast(f.loc[f.target.eq(target)&f.method.eq(name)],target,new,prod)
        for target in ['pass_cmp','rush_att','rec']:
            f=table('modern_cdf_forecast',CONTEXT+['mean','median','fallback'],member='2026/'+target+'.parquet')
            add_forecast(f,target,'CDF_MEDIAN','median','median');add_forecast(f,target,'CDF_MEAN','mean','mean')
        f=table('count_a_forecast',CONTEXT+['point','fallback','target'],member='FORECASTS.parquet');f=f.loc[f.season.eq(2026)]
        for target in ['rush_att','rec']:add_forecast(f.loc[f.target.eq(target)],target,'COUNT_A_MEAN','mean_objective_point')
        for target in ['pass_td','pass_att','pass_int','pass_cmp','rush_att']:
            f=table('cold_'+target,CONTEXT+['point','fallback'],member=target+'.parquet')
            add_forecast(f,target,'RESPONSE_CDF_MEAN' if target in ['pass_td','pass_att','pass_int'] else 'CATBOOST_COUNT_MEAN','mean' if target in ['pass_td','pass_att','pass_int'] else 'mean_objective_point')
        # The frozen equal blend is reconstructed from exactly its old members;
        # this deterministic alias is one declared procedure, not a new fit.
        a1=next(f for f in predictions if f.target.iloc[0]=='anytime_td' and f.method.iloc[0]=='LAB_CDF')
        a2=next(f for f in predictions if f.target.iloc[0]=='anytime_td' and f.method.iloc[0]=='CATBOOST_MEDIUM')
        blend=a1[CONTEXT+['prediction','fallback']].merge(a2[KEY+['prediction']],on=KEY,validate='one_to_one',suffixes=('_a','_b'))
        blend['point']=.5*blend.prediction_a+.5*blend.prediction_b
        add_forecast(blend,'anytime_td','TD_EQUAL_CDF_CAT','probability')
        chart_fields=id_fields|{('forecasts','*','predictions',k) for k in plan['chart_methods']}|{('forecasts','*','fallback')}
        chart_values=projection.project(chart_raw,chart_fields,maximum_bytes=16*MIB)[0]['forecasts']
        for name,product in plan['chart_methods'].items():
            f=pd.DataFrame([{**r['identity'],**{k:r[k] for k in ['position','cutoff_utc','kickoff_utc']},'point':r['predictions'][name],'fallback':r['fallback'] if name.startswith('LEAF_CDF') or name=='HGB_CHART_MEDIAN_V1' else ''} for r in chart_values])
            add_forecast(f,'chart_ppr',name,product)
        # Labels are reused from already qualified saved studies. No source zero
        # is promoted, and every source's participation state stays explicit.
        for target in ['pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td']:
            f=context(table('outcome_'+target,CONTEXT+['actual','participation_state']))
            f=f.loc[f.position.isin(plan['categories'][target]['roles'])].copy();f['target']=target;labels.append(f[KEY+['target','actual','participation_state']])
        for name,member,targets_ in [('count_completion_grade','GRADED_ROWS.parquet',['pass_td','pass_att','pass_int']),('modern_cdf_grade','GRADED_ROWS.parquet',['pass_cmp','rush_att','rec'])]:
            f=table(name,CONTEXT+['target','actual','participation_state'],member=member);f=f.loc[f.season.eq(2026)&f.target.isin(targets_)]
            for target in targets_:
                x=context(f.loc[f.target.eq(target)].drop_duplicates(KEY+['actual','participation_state']))
                x=x.loc[x.position.isin(plan['categories'][target]['roles'])].copy();x['target']=target;labels.append(x[KEY+['target','actual','participation_state']])
        chart_grade=json.loads(gzip.decompress(bodies['chart_grade']))
        if chart_grade['freeze_sha256']!=plan['inputs']['chart_forecast']['sha256']:raise ValueError('chart grade/freeze binding differs')
        if any(x['outcome_state'] not in ['played_score','played_zero','unknown_participation'] for x in chart_grade['rows']):raise ValueError('unregistered chart source outcome state; no collapse to unknown')
        f=pd.DataFrame([{**x['identity'],'target':'chart_ppr','actual':x['actual'],'participation_state':'played' if x['outcome_state'] in ['played_score','played_zero'] else 'unknown','source_outcome_state':x['outcome_state']} for x in chart_grade['rows']])
        for k in ['team','opponent']:f[k]=teams(f[k])
        labels.append(f[KEY+['target','actual','participation_state','source_outcome_state']])
        label=pd.concat(labels,ignore_index=True)
        label['source_outcome_state']=label.source_outcome_state.where(label.source_outcome_state.notna(),label.participation_state)
        if label.duplicated(['target',*KEY]).any():raise ValueError('conflicting or duplicate label identity')
        unknown_numeric=label.actual.notna()&label.participation_state.ne('played')
        if unknown_numeric.any():raise ValueError('unqualified numeric label state; never fill unknown zero')
        full=pd.concat(predictions,ignore_index=True)
        # Membership is keyed independently of method, on the exact original pool.
        joined=full.merge(membership,on=CONTEXT+['target'],how='left',validate='many_to_one')
        if joined.rank_state.isna().any():raise ValueError('forecast/membership identity-clock mismatch')
        joined=joined.merge(label,on=['target',*KEY],how='left',validate='many_to_one')
        if joined.participation_state.isna().any():raise ValueError('forecast lacks explicit outcome state')
        diagnostics=[];records=[];contrasts=[]
        def masks(ranks):
            finite=np.isfinite(ranks)
            return {'full':np.ones(len(ranks),bool),'top10':finite&(ranks<=10),'top15':finite&(ranks<=15),'top20':finite&(ranks<=20),'rank1_10':finite&(ranks<=10),'rank11_15':finite&(ranks>10)&(ranks<=15),'rank16_20':finite&(ranks>15)&(ranks<=20),'remainder':~finite|(ranks>20),'unranked':~finite}
        def metrics(f,target):
            n=len(f);y=pd.to_numeric(f.actual,errors='coerce').to_numpy(float);p=f.prediction.to_numpy(float);good=f.participation_state.eq('played').to_numpy()&np.isfinite(y)&np.isfinite(p);e=p[good]-y[good];ae=np.abs(e);fallback=f.fallback.fillna('').ne('').to_numpy();tol=1 if target.startswith('pass_') and target!='pass_yd' or target in ['rush_att','rec','chart_ppr'] else 10
            if target=='anytime_td':
                pp=p[good];yy=y[good]
                if not (((pp>=0)&(pp<=1)).all() and np.isin(yy,[0,1]).all()):raise ValueError('invalid binary contract')
                with np.errstate(divide='ignore',invalid='raise'):ll=np.where(yy==1,-np.log(pp),-np.log1p(-pp))
                inf=int(np.isposinf(ll).sum());proper={'Brier':float(np.mean(e*e)) if len(e) else None,'log_loss':{'state':'POSITIVE_INFINITY' if inf else 'FINITE' if len(e) else 'UNAVAILABLE','value':None if inf or not len(e) else float(ll.mean()),'positive_infinite_rows':inf},'reliability':[{'lower':i/10,'upper':(i+1)/10,'n':int(((pp>=i/10)&(pp<((i+1)/10) if i<9 else pp<=1)).sum()),'mean_probability':None,'event_rate':None} for i in range(10)]}
                for i,b in enumerate(proper['reliability']):
                    select=(pp>=i/10)&((pp<(i+1)/10) if i<9 else (pp<=1))
                    if select.any():b.update(mean_probability=float(pp[select].mean()),event_rate=float(yy[select].mean()))
            else:proper=None
            return {'planned':n,'scored':int(good.sum()),'players':int(f.loc[good,'player_id'].nunique()),'players_planned':int(f.player_id.nunique()),'player_weeks_planned':int(f[['player_id','week']].drop_duplicates().shape[0]),'games':int(f.loc[good,'game_id'].nunique()),'weeks':int(f.loc[good,'week'].nunique()),'outcome_states':{str(k):int(v) for k,v in f.participation_state.value_counts(dropna=False).items()},'played_missing':int((f.participation_state.eq('played').to_numpy()&~np.isfinite(y)).sum()),'played_zero':int((good&(y==0)).sum()),'fallback_planned':int(fallback.sum()),'fallback_scored':int((good&fallback).sum()),'rank_unavailable_planned':int(f['rank'].isna().sum()),'original_forecast_clock_unknown':int(f.forecast_clock_state.eq('original_clock_unknown').sum()),'MAE':float(ae.mean()) if len(e) else None,'MSE':float(np.mean(e*e)) if len(e) else None,'RMSE':float(np.sqrt(np.mean(e*e))) if len(e) else None,'bias':float(e.mean()) if len(e) else None,'p90_AE':float(np.quantile(ae,.9)) if len(e) else None,'p95_AE':float(np.quantile(ae,.95)) if len(e) else None,'absolute_error_sum':float(ae.sum()),'tolerance':None if target=='anytime_td' else tol,'strict_within':None if target=='anytime_td' or not len(e) else float((ae<tol).mean()),'inclusive_within':None if target=='anytime_td' or not len(e) else float((ae<=tol).mean()),'probability_scores':proper,'authentic_offer_side_or_close_and_correct':'UNAVAILABLE_NO_MATCHED_AUTHENTIC_LINES','actual_prop_offered_population':'UNAVAILABLE_NOT_GENERIC_QUERY_POOL'}
        def paired(f,control,loss):
            if f.duplicated(KEY).any() or control.duplicated(KEY).any():raise ValueError('duplicate paired source')
            cols=KEY+['prediction','actual','participation_state']
            t=f[cols].merge(control[cols],on=KEY,how='outer',validate='one_to_one',suffixes=('_c','_b'),indicator=True)
            if not t['_merge'].eq('both').all():raise ValueError('candidate missing complete same-group opportunities')
            yc=pd.to_numeric(t.actual_c,errors='coerce').to_numpy(float);yb=pd.to_numeric(t.actual_b,errors='coerce').to_numpy(float)
            good=t.participation_state_c.eq('played').to_numpy()&t.participation_state_b.eq('played').to_numpy()&np.isfinite(yc)&np.isfinite(yb)
            if not np.array_equal(yc[good],yb[good]):raise ValueError('paired actuals differ')
            t=t.loc[good].copy();ec=t.prediction_c.to_numpy()-yc[good];eb=t.prediction_b.to_numpy()-yb[good]
            lc=np.abs(ec) if loss=='MAE' else ec*ec;lb=np.abs(eb) if loss=='MAE' else eb*eb;delta=lc-lb;t['delta']=delta;t['n']=1
            intervals={}
            for cluster in ['game_id','week']:
                g=t.groupby(cluster,sort=True)[['delta','n']].sum().to_numpy(float);k=len(g);ci=None
                if k>=8:
                    index=np.random.default_rng(1703).integers(k,size=(500,k));s=g[index].sum(axis=1);ci=np.quantile(s[:,0]/s[:,1],[.025,.975]).tolist()
                intervals[cluster]={'clusters':k,'interval':ci,'state':'NOMINAL_EXPOSED_DEVELOPMENT' if k>=8 else 'UNAVAILABLE_FEWER_THAN8CLUSTERS'}
            base=float(lb.mean()) if len(lb) else None
            return {'paired_rows':len(t),'candidate_loss':float(lc.mean()) if len(lc) else None,'control_loss':base,'candidate_minus_control':float(delta.mean()) if len(delta) else None,'improvement_percent':None if base is None or base==0 else 100*(base-float(lc.mean()))/base,'intervals':intervals,'replicates':500,'seed':1703}
        for target in TARGETS:
            check();ft=joined.loc[joined.target.eq(target)].copy();entry=plan['categories'][target]
            bymethod={str(k):f for k,f in ft.groupby('method',sort=True)}
            if entry['incumbent'] not in bymethod:raise ValueError('declared comparison reference absent')
            # Original pooled primary population remains separately visible.
            for method,f in bymethod.items():records.append({'target':target,'position':'ALL_ORIGINAL_PRIMARY_ROLES','group':'full','period':'2026_W1_6','method':method,'product':f['product'].iloc[0],'metrics':metrics(f,target)})
            for role,position in ft.groupby('position',sort=True):
                methods={str(k):f.sort_values(KEY).reset_index(drop=True) for k,f in position.groupby('method',sort=True)}
                reference=methods[entry['incumbent']]
                denom={name:metrics(f,target)['absolute_error_sum'] for name,f in methods.items()}
                for group,mask in masks(reference['rank'].to_numpy(float)).items():
                    selected={name:f.loc[mask].copy() for name,f in methods.items()}
                    for name,f in selected.items():
                        value=metrics(f,target);value['share_of_full_position_absolute_error']=None if denom[name]==0 else value['absolute_error_sum']/denom[name]
                        records.append({'target':target,'position':role,'group':group,'period':'2026_W1_6','method':name,'product':f['product'].iloc[0] if len(f) else methods[name]['product'].iloc[0],'metrics':value})
                        for week in range(1,7):
                            records.append({'target':target,'position':role,'group':group,'period':'2026_W'+str(week),'method':name,'product':methods[name]['product'].iloc[0],'metrics':metrics(f.loc[f.week.eq(week)],target)})
                    for name,f in selected.items():
                        if name==entry['incumbent']:continue
                        loss='Brier' if target=='anytime_td' else 'MAE'
                        pair=paired(f,selected[entry['incumbent']],loss)
                        contrasts.append({'target':target,'position':role,'group':group,'candidate':name,'control':entry['incumbent'],'loss':loss,'cross_product_point_diagnostic':methods[name]['product'].iloc[0]!=reference['product'].iloc[0],**pair})
                        if methods[name]['product'].iloc[0].startswith('mean') and reference['product'].iloc[0].startswith('mean'):
                            contrasts.append({'target':target,'position':role,'group':group,'candidate':name,'control':entry['incumbent'],'loss':'MSE','cross_product_point_diagnostic':False,**paired(f,selected[entry['incumbent']],'MSE')})
                for name,f in methods.items():
                    band=masks(f['rank'].to_numpy(float));parts=[metrics(f.loc[band[g]],target) for g in ['rank1_10','rank11_15','rank16_20','remainder']]
                    whole=metrics(f,target)
                    if sum(x['planned'] for x in parts)!=whole['planned'] or sum(x['scored'] for x in parts)!=whole['scored'] or not math.isclose(sum(x['absolute_error_sum'] for x in parts),whole['absolute_error_sum'],rel_tol=1e-12,abs_tol=1e-9):raise ValueError('rank partition loses poor or unknown opportunities')
                diagnostics.append({'target':target,'position':role,'ranked_player_weeks':int(reference.loc[reference['rank'].notna(),['week','player_id']].drop_duplicates().shape[0]),'unranked_query_rows':int(reference['rank'].isna().sum()),'topN_is_player_rank_not_independent_game_count':True,'original_forecast_clock_unknown':int(reference.forecast_clock_state.eq('original_clock_unknown').sum())})
        # Full original primary support must reconcile with earlier admitted panels.
        for target in TARGETS:
            checks_=[r for r in records if r['target']==target and r['position']=='ALL_ORIGINAL_PRIMARY_ROLES']
            for r in checks_:
                if r['metrics']['planned']!=plan['categories'][target]['expected_queries'] or r['metrics']['scored']!=plan['categories'][target]['expected_supported']:raise ValueError('expected complete target support differs: '+target)
        result={'version':VERSION,'state':'TOP_PLAYER_CACHED_COMPARISONS_COMPLETE','membership_freeze':frozen,'plan_sha256':a.sha256,'ranking':plan['ranking'],'scope':plan['scope'],'original_query_clock_census':original_query_clock_census,'records':records,'paired':contrasts,'diagnostics':diagnostics,'usage':usage(),'actual_model_effort':'UNATTESTED','new_predictive_fits':0,'new_model_inference':0,'new_prospective_forecasts':0,'specialized_training_tested':False,'live_selection_or_release':False,'limitations':['Exposed current-vintage historical reconstructions with original assumed seven-day availability, not verified source publication times','Rankings are retrospectively reconstructed from prior slots; not original issued top-player lists','No authentic historical SITE/R0/raw-provider or sportsbook-offered pool/lines/prices in this panel','Mean/median products remain distinct; lower point MAE is not a probability or paper-return result','2025, older-season cohort panels and genuine Week7 cohort analysis remain separate queued work','Chart fallback forecast clocks remain unknown where absent; calendar rank clocks do not fabricate issuance','No new specialization/irreducible-error-floor or deployment claim; uncertainty nominal and unadjusted for prior searches']}
        # Private readable/replayable comparison rows retain exact original
        # predictions and actuals alongside newly frozen cohort membership.
        row_export=joined.copy()
        numeric=pd.to_numeric(row_export.actual,errors='coerce')
        played=row_export.participation_state.eq('played')
        supported=played&numeric.notna()
        row_export['outcome_state']=np.where(supported,np.where(numeric.eq(0),'played_zero','played_score'),np.where(played,'played_missing',np.where(row_export.participation_state.eq('dnp'),'DNP',row_export.participation_state)))
        chart_mask=row_export.target.eq('chart_ppr')
        row_export.loc[chart_mask,'outcome_state']=row_export.loc[chart_mask,'source_outcome_state']
        row_export['signed_error']=np.where(supported,row_export.prediction-numeric,np.nan)
        row_export['absolute_error']=abs(row_export.signed_error)
        row_export['source_label_input']=row_export.target.map(lambda t:'chart_grade' if t=='chart_ppr' else 'count_completion_grade' if t in ['pass_td','pass_att','pass_int'] else 'modern_cdf_grade' if t in ['pass_cmp','rush_att','rec'] else 'outcome_'+t)
        row_export['evidence_lane']='EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION_TOP_GROUP_DIAGNOSTIC'
        stream=io.BytesIO();row_export.to_parquet(stream,index=False,compression='zstd')
        saved=save('GRADE_COMPLETE.zip',{'RESULT.json':encoded(result),'COMPARISON_ROWS.parquet':stream.getvalue(),'SOURCE_VERSIONS.json':encoded({'inputs':plan['inputs'],'membership_freeze':frozen,'semantics':'Original saved points/labels joined with frozen newrankmembership; no newly issuedNFLpredictions. source_forecast_input/source_label_input indexthese immutable inputbindings; blenduses exactlyfixed0.5members.'})})
        safe={'version':VERSION,'state':result['state'],'scope':plan['scope'],'membership_freeze':frozen,'grade':saved,'records':records,'paired':contrasts,'diagnostics':diagnostics,'limitations':result['limitations'],'execution':usage(),'new_predictive_fits':0,'new_model_inference':0}
        body,encoding=public_aggregate(safe)
        if len(body)>CAPS['safe_aggregate_bytes']:raise ValueError('safe aggregate metadata cap')
        public=Path(plan['safe_output']);public.write_bytes(body)
        note('COMPLETE.json',{'state':result['state'],'membership_freeze':frozen,'grade':saved,'usage':usage(),'safe_output':{'path':str(public),'bytes':len(body),'sha256':digest(body),**encoding},'retained_body_bytes':retained,'socket_child_attempts':dict(attempted),'managed_writer':'CLOSED'})
        print(json.dumps({'state':result['state'],'usage':usage(),'safe_output':str(public),'private_capsules':references}))
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL,0)
        failed={'state':'FAILED_ATTEMPT_PRESERVED','plan_sha256':a.sha256,'type':type(error).__name__,'message':str(error)[:500],'usage':usage(),'references':references,'automatic_retry':False}
        note('FAILURE.json',failed)
        if storage is not None and writes<2:
            try:save('FAILURE.zip',{'FAILURE.json':encoded(failed)})
            except BaseException:pass
        raise
    finally:done.set();signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':main()
