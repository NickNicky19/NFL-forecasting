"""Independent cached-row arithmetic review. Prepare only until explicit root GO.

No campaign evaluator, fitting, inference, calibration fitting, resampling,
source acquisition or managed writes. Recomputes the already frozen statistic.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path('/workspace/nfl-methods-integration')
OUTPUT = Path('/workspace/website-methods-research/resumed/cdf-split-cqr-80-v1-20261024')
FREEZE = OUTPUT / 'CONFORMAL_INTERVAL_EXECUTION_FREEZE.json'
FREEZE_SHA = '459832bc62fb01e2982a80e6343e87c2f9ebf930f489f1d0541c0bda460b8c47'
DESTINATION = Path('/tmp/conformal-interval-v1-independent-review')
TARGETS = ('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd')
COUNTS = {'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec'}
CONTEXT = ['season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc']
KEYS = ['season','week','game_id','player_id']
VERSION = 'cdf-split-cqr-80-v1-20261024'
CAPS = ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS',
        'VECLIB_MAXIMUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-sha256', required=True)
    parser.add_argument('--terminal-sha256', required=True)
    args = parser.parse_args()
    if sha(FREEZE) != FREEZE_SHA:
        raise ValueError('exact accepted CQR freeze required')
    if any(os.environ.get(k) != '2' for k in CAPS) or not sys.dont_write_bytecode:
        raise ValueError('clean Python-B and all seven caps2 required')
    if DESTINATION.exists():
        raise ValueError('sole review invocation already consumed')
    DESTINATION.mkdir(mode=0o700)
    (DESTINATION/'CONSUMED.json').write_text('{"invocations":1,"automatic_retries":0}\n')
    resource.setrlimit(resource.RLIMIT_CPU, (59,59))
    start, cpu = time.monotonic(), time.process_time()
    checks = []
    counters = dict(semantic_row_incidences=0, saved_CDF_files=0, query_files=0,
        interval_files=0, radii=0, annual_population_cells=0, pooled_population_cells=0,
        bootstrap_resamples=0, campaign_evaluator_calls=0, fits_models_inference_source_HTTP_CAS=0,
        denied_effects=0)
    stage = 'metadata'
    receipt = dict(schema_version='cdf-cqr-independent-cached-row-review-v1', checks=checks, counters=counters)

    def guard():
        if (time.monotonic()-start >= 57 or time.process_time()-cpu >= 57
                or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 >= 512*1024**2):
            raise RuntimeError('independent review resource cap')

    def check(ok, label):
        guard()
        checks.append(dict(check=label,PASS=bool(ok)))
        if not ok:
            raise AssertionError(label)

    def json_read(path):
        return json.loads(Path(path).read_text())

    def number_equal(actual, expected):
        if expected is None:
            return actual is None
        return (type(actual) in (int,float) and math.isfinite(actual)
            and math.isclose(actual,float(expected),rel_tol=1e-12,abs_tol=1e-12))

    def float_check(actual, expected, label):
        check(number_equal(actual,expected),label)

    def timeout(*_):
        raise TimeoutError('independent review60s')

    signal.signal(signal.SIGALRM,timeout)
    signal.setitimer(signal.ITIMER_REAL,58)
    try:
        frozen = json_read(FREEZE)
        spec = frozen['execution_metadata']
        allowed = {str(FREEZE),str(OUTPUT/'report.json'),str(OUTPUT/'SUPERVISOR_TERMINAL.json')}
        allowed.update(ref['path'] for ref in spec['queries'].values())
        allowed.update(ref['path'] for by_target in spec['cdf'].values() for ref in by_target.values())
        # Hash-only output authentication includes subgroup bodies; they are never decoded.
        output_prefix = str(OUTPUT)+'/'

        def audit(event, values):
            forbidden = event.startswith(('socket.','subprocess.')) or event in {
                'os.system','os.fork','os.forkpty','os.exec','os.posix_spawn','pty.spawn'}
            if event == 'open' and values and isinstance(values[0],(str,bytes,os.PathLike)):
                path = os.fsdecode(values[0])
                if '/workspace/website-methods-research/' in path:
                    forbidden |= path not in allowed and not path.startswith(output_prefix)
                forbidden |= path.endswith(('.joblib','.pkl','.pickle','.csv'))
                # Private paths are never writable, even when admitted as read inputs.
                if '/workspace/website-methods-research/' in path:
                    mode = values[1] if len(values)>1 else None
                    flags = values[2] if len(values)>2 else 0
                    forbidden |= (isinstance(mode,str) and any(c in mode for c in 'wax+'))
                    forbidden |= isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if forbidden:
                counters['denied_effects'] += 1
                raise RuntimeError('independent review forbidden effect')

        sys.addaudithook(audit)
        sys.path.insert(0,str(ROOT/'tools'))
        # Only the previously pinned dependency-import context is imported.
        from offline_report_imports_v1 import offline_dependency_imports
        with offline_dependency_imports():
            import numpy as np
            import pandas as pd
            import pyarrow as pa
        pa.set_cpu_count(2);pa.set_io_thread_count(2)
        report_path, terminal_path = OUTPUT/'report.json',OUTPUT/'SUPERVISOR_TERMINAL.json'
        check(sha(report_path)==args.report_sha256,'exact completed report digest')
        check(sha(terminal_path)==args.terminal_sha256,'exact completed outer terminal digest')
        report,terminal = json_read(report_path),json_read(terminal_path)
        check(terminal['state']=='COMPLETE' and terminal['returncode']==0 and terminal['limit_reason'] is None,
            'original guarded interval campaign actually complete')
        check(report['state']=='COMPLETE' and report['version']==VERSION and report['radii']==20,
            'complete fixed twenty-radius report')
        check(report['original_points_laws_sources_unchanged'] is True
            and report['new_base_fits_predictions_models_sources_HTTP']==0
            and report['confirmation_or_coverage_guarantee'] is False,'interval-only exposed/no-confirmation claims')
        for relative,expected in report['frozen_bindings'].items():
            path = OUTPUT/relative
            check(path.resolve()==path and OUTPUT in path.parents and sha(path)==expected,
                'frozen output hash: '+relative)

        def read_rows(ref, columns, kind):
            guard()
            check(sha(ref['path'])==ref['sha256'],'original input digest: '+kind)
            frame = pd.read_parquet(ref['path'],columns=columns,use_threads=False)
            check(len(frame)==ref['rows'],'full offered row inventory: '+kind)
            counters['semantic_row_incidences'] += len(frame)
            check(counters['semantic_row_incidences']<600000,'finite semantic incidence budget')
            guard()
            return frame

        queries,frames = {},{}
        for year in (2022,2023,2024):
            stage='query-'+str(year)
            ref=spec['queries'][str(year)]
            cols=[*CONTEXT,'outcome_available_utc']+(['season_type'] if 'season_type' in ref['columns'] else [])
            q=read_rows(ref,cols,stage)
            check(not q.duplicated(KEYS).any() and q.season.eq(year).all(),'query identity/year '+str(year))
            check((q.cutoff_utc<=q.kickoff_utc).all(),'original replay cutoff<=kickoff '+str(year))
            queries[year]=q;counters['query_files']+=1
            for target in TARGETS:
                stage='saved-'+str(year)+'-'+target
                ref=spec['cdf'][str(year)][target]
                cols=[*CONTEXT,'target','method','primary_role','fallback','history_state','p10','p90',
                    'actual','participation_state','outcome_state']
                if 'season_type' in ref['columns']:cols.append('season_type')
                frame=read_rows(ref,cols,stage)
                pd.testing.assert_frame_equal(q[CONTEXT].reset_index(drop=True),
                    frame[CONTEXT].reset_index(drop=True),check_dtype=True,check_exact=True)
                check(frame.target.eq(target).all() and frame.method.eq('leaf_cdf').all(),stage+' exact target/method')
                check(not frame.duplicated(KEYS).any(),stage+' no duplicate player-games')
                if 'season_type' in q:
                    pd.testing.assert_series_equal(q.season_type,frame.season_type,check_dtype=True,check_exact=True)
                check(np.array_equal(frame.primary_role.to_numpy(),frame.position.isin(
                    spec['categories'][target]['primary_roles']).to_numpy()),stage+' unchanged primary roles')
                frames[year,target]=frame;counters['saved_CDF_files']+=1

        def observed(frame,target):
            y=frame.actual.to_numpy(dtype=float)
            valid=np.isfinite(y)&(y==np.floor(y))
            if target in COUNTS:valid &= y>=0
            return frame.participation_state.eq('played').to_numpy()&valid

        radii={}
        for year in (2023,2024):
            prior=year-1;start_time=queries[year].cutoff_utc.min()
            for target in TARGETS:
                stage='radius-'+str(year)+'-'+target
                saved=json_read(OUTPUT/f'private/radii/{year}/{target}.json')
                a=frames[prior,target];q=queries[prior]
                y=a.actual.to_numpy(dtype=float);lo=a.p10.to_numpy(dtype=float);hi=a.p90.to_numpy(dtype=float)
                eligibility=observed(a,target);primary=a.primary_role.to_numpy(dtype=bool)
                available=q.outcome_available_utc;has_available=available.notna().to_numpy()
                time_ok=(available<start_time).to_numpy()
                base=eligibility&primary
                check((available.loc[base&has_available]>=q.kickoff_utc.loc[base&has_available]).all(),
                    stage+' source availability not before game')
                before_bounds=base&has_available&time_ok
                check(not (before_bounds&(np.isinf(lo)|np.isinf(hi))).any(),stage+' valid present endpoints')
                bounds=np.isfinite(lo)&np.isfinite(hi)
                check(not (before_bounds&bounds&(lo>hi)).any(),stage+' ordered admitted endpoints')
                if target in COUNTS:check(not (before_bounds&bounds&(lo<0)).any(),stage+' admitted count support')
                admitted=before_bounds&bounds;n=int(admitted.sum());rank=(4*(n+1)+4)//5
                raw=np.maximum(lo[admitted]-y[admitted],y[admitted]-hi[admitted])
                radius=max(0.,float(np.sort(raw)[rank-1])) if rank<=n else None
                exclusions=Counter()
                exclusions['unsupported_or_not_played']=int((~eligibility).sum())
                exclusions['outside_fixed_primary_role_calibration_population']=int((eligibility&~primary).sum())
                exclusions['missing_original_outcome_availability']=int((base&~has_available).sum())
                exclusions['outcome_not_available_strictly_before_evaluation']=int((base&has_available&~time_ok).sum())
                exclusions['missing_saved_interval']=int((before_bounds&~bounds).sum())
                exclusions={k:v for k,v in exclusions.items() if v}
                check(saved['version']==VERSION and saved['target']==target and saved['alpha']==.2
                    and saved['calibration_season']==prior and saved['evaluation_season']==year
                    and pd.Timestamp(saved['evaluation_start_utc'])==start_time,stage+' exact timing/identity')
                check(saved['radius']==radius and saved['admitted_calibration_rows']==n
                    and saved['order_statistic_rank']==rank and saved['planned_calibration_rows']==len(a),stage+' exact radius/rank/n')
                check(saved['excluded']==exclusions and saved['all_input_rows_accounted'] is True
                    and n+sum(exclusions.values())==len(a),stage+' full calibration coverage')
                check(saved['supported_played_zero_rows']==int((admitted&(y==0)).sum())
                    and saved['negative_outcome_rows']==int((admitted&(y<0)).sum())
                    and saved['admitted_original_fallback_rows']==sum(bool(v) for v in a.loc[admitted,'fallback']),
                    stage+' zeros/signed/fallbacks')
                identities=[[int(v[0]),int(v[1]),v[2],v[3]] for v in a.loc[admitted,KEYS].itertuples(index=False,name=None)]
                check(saved['admitted_identity_sha256']==canonical_digest(identities)
                    and saved['binding_sha256']==canonical_digest(spec['core_binding']),stage+' admitted population/provenance digest')
                check(saved['state']==('RADIUS_FROZEN' if radius is not None else
                    'UNCALIBRATED_FALLBACK_INSUFFICIENT_N'),stage+' fixed insufficient-n fallback')
                radii[year,target]=saved;counters['radii']+=1

        intervals={}
        reverse={0:'RADIUS_FROZEN',1:'UNCALIBRATED_FALLBACK_INSUFFICIENT_N',2:'ABSTAIN_MISSING_BASE_INTERVAL'}
        for year in (2023,2024):
            frozen_year=json_read(OUTPUT/f'INTERVALS_FROZEN_{year}.json')
            check(set(frozen_year['targets'])==set(TARGETS) and frozen_year['all_original_offers_retained'] is True,
                'allten persisted interval year freeze '+str(year))
            for target in TARGETS:
                stage='interval-'+str(year)+'-'+target
                rel=f'private/intervals/{year}/{target}.parquet'
                a=frames[year,target];q=queries[year]
                z=pd.read_parquet(OUTPUT/rel,use_threads=False)
                counters['semantic_row_incidences']+=len(z);counters['interval_files']+=1
                check(counters['semantic_row_incidences']<600000 and len(z)==len(a),stage+' all offers/rowcap')
                check(list(z.columns)==['ordinal','interval_lower','interval_upper','status']
                    and np.array_equal(z.ordinal.to_numpy(),np.arange(len(a))),stage+' compact schema/ordinals')
                lo=a.p10.to_numpy(dtype=float);hi=a.p90.to_numpy(dtype=float);r=radii[year,target]
                check(not(np.isinf(lo)|np.isinf(hi)).any(),stage+' no invalid present infinity')
                bounds=np.isfinite(lo)&np.isfinite(hi)
                check(not(bounds&(lo>hi)).any(),stage+' original endpoint order')
                if target in COUNTS:check(not(bounds&(lo<0)).any(),stage+' original count support')
                lower,upper=np.full(len(a),np.nan),np.full(len(a),np.nan)
                lower[bounds],upper[bounds]=lo[bounds],hi[bounds]
                if r['radius'] is not None:
                    lower[bounds]-=r['radius'];upper[bounds]+=r['radius']
                    if target in COUNTS:lower[bounds]=np.maximum(0.,lower[bounds])
                status=np.where(bounds,0 if r['radius'] is not None else 1,2)
                check(np.array_equal(z.interval_lower.to_numpy(dtype=float),lower,equal_nan=True)
                    and np.array_equal(z.interval_upper.to_numpy(dtype=float),upper,equal_nan=True)
                    and np.array_equal(z.status.to_numpy(),status),stage+' exact independently recomputed bounds/status')
                check(frozen_year['bindings'][rel]==report['frozen_bindings'][rel]
                    and frozen_year['bindings'][f'private/radii/{year}/{target}.json']==report['frozen_bindings'][f'private/radii/{year}/{target}.json'],
                    stage+' immutable radius/interval gate bindings')
                intervals[year,target]=z

        def verify_bootstrap(frame,mask,cell,cluster,label):
            selected=frame.loc[mask]
            keys=['season','week'] if cluster=='week' else ['season','game_id']
            clusters=len(selected[keys].drop_duplicates())
            check(cell['cluster']==cluster and cell['paired_rows']==int(mask.sum()) and cell['clusters']==clusters
                and cell['replicates']==500 and cell['seed']==1703 and cell['generator']=='PCG64'
                and cell['percentile_method']=='linear' and cell['level']==.95,label+' metadata/membership only')
            check(cell['state']==('DESCRIPTIVE' if clusters>=8 else 'N/A'),label+' cluster minimum')
            if clusters>=8:
                check(isinstance(cell['interval'],list) and len(cell['interval'])==2
                    and all(type(x) in (int,float) and math.isfinite(x) for x in cell['interval'])
                    and cell['interval'][0]<=cell['interval'][1],label+' finite ordered saved interval')
            else:check(cell['interval'] is None,label+' no invented small-cluster interval')

        def verify_report(frame,target,rep,label):
            y=frame.actual.to_numpy(dtype=float);lo=frame.p10.to_numpy(dtype=float);hi=frame.p90.to_numpy(dtype=float)
            lower=frame.interval_lower.to_numpy(dtype=float);upper=frame.interval_upper.to_numpy(dtype=float)
            observed_mask=observed(frame,target)
            good=observed_mask&np.isfinite(lo)&np.isfinite(hi)
            check(np.array_equal(good,observed_mask&np.isfinite(lower)&np.isfinite(upper)),label+' identical supported common cohort')
            check(rep['target']==target and rep['version']==VERSION and rep['alpha']==.2,label+' product/target')
            check(rep['outcome_states']==frame.outcome_state.value_counts(dropna=False).to_dict()
                and rep['interval_states']==frame.interval_status.value_counts(dropna=False).to_dict()
                and rep['original_fallbacks']==frame.fallback.value_counts(dropna=False).to_dict(),label+' complete state/fallback counts')
            populations={x['population']:x for x in rep['reports']}
            check(set(populations)=={'all_offered','primary_roles'},label+' both populations')
            control={'width':hi-lo,'covered':((y>=lo)&(y<=hi)).astype(float),
                'interval_score':(hi-lo)+10*(np.maximum(0.,lo-y)+np.maximum(0.,y-hi))}
            candidate={'width':upper-lower,'covered':((y>=lower)&(y<=upper)).astype(float),
                'interval_score':(upper-lower)+10*(np.maximum(0.,lower-y)+np.maximum(0.,y-upper))}
            for population,mask in [('all_offered',good),('primary_roles',good&frame.primary_role.to_numpy(dtype=bool))]:
                x=populations[population];n=int(mask.sum())
                check(x['paired_rows']==n and x['planned_rows']==(len(frame) if population=='all_offered' else int(frame.primary_role.sum())),label+' '+population+' planned/paired')
                check(x['supported_played_zero_rows']==int((mask&(y==0)).sum())
                    and x['negative_outcome_rows']==int((mask&(y<0)).sum()),label+' '+population+' supported zero/signed')
                for metric in ('interval_score','width','covered'):
                    a,b=control[metric],candidate[metric];m=x['metrics'][metric]
                    float_check(m['candidate'],float(b[mask].mean()) if n else None,label+' '+population+' '+metric+' candidate')
                    float_check(m['saved_cdf'],float(a[mask].mean()) if n else None,label+' '+population+' '+metric+' control')
                    float_check(m['mean_delta'],float((b-a)[mask].mean()) if n else None,label+' '+population+' '+metric+' paired delta')
                    for cluster in ('week','game'):verify_bootstrap(frame,mask,m[cluster],cluster,label+' '+population+' '+metric+' '+cluster)
                for which,a,b in [('lower_miss_frequency',y<lo,y<lower),('upper_miss_frequency',y>hi,y>upper)]:
                    float_check(x[which]['saved_cdf'],float(a[mask].mean()) if n else None,label+' '+population+' '+which+' control')
                    float_check(x[which]['candidate'],float(b[mask].mean()) if n else None,label+' '+population+' '+which+' candidate')

        compared={}
        report_index={(x['evaluation_year'],x['target']):x for x in report['reports']}
        check(len(report_index)==len(report['reports'])==20,'all20 annual report identities')
        for year in (2023,2024):
            for target in TARGETS:
                stage='annual-'+str(year)+'-'+target
                frame=frames[year,target].copy();z=intervals[year,target]
                frame['interval_lower']=z.interval_lower.to_numpy();frame['interval_upper']=z.interval_upper.to_numpy()
                frame['interval_status']=z.status.map(reverse)
                annual=json_read(OUTPUT/f'reports/{year}/{target}.json')
                check(annual==report_index[year,target],stage+' exact file-to-main aggregate transfer')
                verify_report(frame,target,annual,stage)
                compared[year,target]=frame;counters['annual_population_cells']+=2
        check(set(report['pooled_exposed_reports'])==set(TARGETS),'allten pooled report targets')
        for target in TARGETS:
            stage='pooled-'+target
            frame=pd.concat([compared[year,target] for year in (2023,2024)],ignore_index=True)
            pooled=json_read(OUTPUT/f'reports/pooled/{target}.json')
            check(pooled==report['pooled_exposed_reports'][target],stage+' exact file-to-main aggregate transfer')
            verify_report(frame,target,pooled,stage);counters['pooled_population_cells']+=2
        check(set(report['matrix'])==set(TARGETS)|{'fantasy_ppr','anytime_td'},'explicit complete twelve-category matrix')
        check(report['matrix']['fantasy_ppr']['state']=='BLOCKED_EXACT_LABEL_CONTRACT'
            and report['matrix']['anytime_td']['state']=='NOT_AN_INTERVAL_TARGET_RETAINED_PROBABILITY_REFERENCE',
            'PPR/TD reference states not invented interval improvements')
        for target in TARGETS:
            x=report['matrix'][target]
            check(x['state']=='EXPOSED_INTERVAL_COMPARISON_COMPLETE' and x['point_change'] is False
                and x['confirmation'] is False and x['release_ready'] is False,'matrix honest interval-only status '+target)
        check(counters['radii']==20 and counters['interval_files']==20 and counters['saved_CDF_files']==30
            and counters['query_files']==3 and counters['annual_population_cells']==40
            and counters['pooled_population_cells']==20,'fixed all20 radii/all60 population cells accounted')
        check(counters['denied_effects']==0,'no forbidden effects attempted')
        receipt.update(state='PASS',report_sha256=args.report_sha256,terminal_sha256=args.terminal_sha256,
            freeze_sha256=FREEZE_SHA, scope='Independent cached-row arithmetic; same exposed NFL observations, zero new confirmation.',
            limitations=['Original source acquisition/participation completeness not requalified.',
                'Saved bootstrap metadata, paired membership and finite interval shape checked; no bootstrap resampling or interval endpoint reproduction.',
                'Private subgroup bodies authenticated by frozen hash only, not semantically recomputed or exported.',
                'Float aggregates compared at fixed rel_tol=abs_tol=1e-12; exact rank/radius/bounds/status equality required.',
                'No claim of point forecast improvement, arbitrary prop probabilities, conformal coverage guarantee, independent confirmation or release readiness.'])
    except BaseException as error:
        receipt.update(state='FAILED',failure_stage=stage,error_type=type(error).__name__,
            failure_detail='No raw exception text/rows/identities exported; preserve this terminal without automatic retry.')
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        receipt.update(wall_seconds_before_receipt_write=time.monotonic()-start,
            CPU_seconds_before_receipt_write=time.process_time()-cpu,
            process_highwater_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            limits=dict(wall_CPU_seconds=60,RSS_bytes=536870912,threads=2,semantic_row_cap=600000),
            resource_scope='Single process highwater/checkpoints plus external native60s; not continuous RSS certification.')
        result=(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        if len(result)>1048576:raise RuntimeError('bounded review receipt exceeds1MiB')
        path=DESTINATION/'RECEIPT.json';path.write_bytes(result)
        print(json.dumps(dict(state=receipt['state'],receipt=str(path),sha256=hashlib.sha256(result).hexdigest(),
            bytes=len(result),checks=len(checks),counters=counters,
            failure_stage=receipt.get('failure_stage'),error_type=receipt.get('error_type')),sort_keys=True))
    return 0 if receipt['state']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
