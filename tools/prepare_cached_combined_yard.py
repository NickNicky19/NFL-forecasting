"""Footer/manifest/stat only. Never unpickle, read table rows or invoke science."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def bind(p,digest=None):
    p=Path(p)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=digest or hashlib.sha256(p.read_bytes()).hexdigest())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--source-execution',type=Path,required=True)
    parser.add_argument('--cached-point-execution',type=Path,required=True)
    parser.add_argument('--cached-point-acceptance',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--interpreter',type=Path,default=Path('/workspace/nfl-direct-boosters-venv/bin/python'))
    parser.add_argument('--libc',type=Path,default=Path('/usr/lib/x86_64-linux-gnu/libc.so.6'))
    args=parser.parse_args()
    import pyarrow.parquet as pq
    dest=args.destination;dest.mkdir(mode=0o700,exist_ok=False)
    original=args.source_execution;wave=json.loads(original.read_text());base=Path(wave['output']);done=json.loads((base/'completion.json').read_text());cached=json.loads(args.cached_point_execution.read_text())
    assert wave['source_commit']=='d5583becac164e21dd535551cee2ec414f95a0ff' and done['state']=='COMPLETED'
    refs={};schema={};counts={}
    for year in [2022,2023,2024]:
        for target in ['rush_yd','rec_yd','rush_rec_yd']:
            for name,filename in [('model','leaf_cdf.joblib'),('query','query.parquet'),('forecast','leaf_cdf-forecast.parquet'),('scored','leaf_cdf-scored.parquet')]:
                rel=f'{year}/{target}/{filename}';p=base/rel;refs[f'{year}/{target}/{name}']=bind(p,done['bindings'][rel])
                if p.suffix=='.parquet':
                    metadata=pq.read_metadata(p);fields=pq.read_schema(p).names
                    schema[rel]=dict(rows=metadata.num_rows,columns=fields,row_groups=metadata.num_row_groups,statistics_or_values_read=False)
                    if name=='query':counts[f'{year}/{target}']=metadata.num_rows;assert len([c for c in fields if c.startswith('f_')])==97 and 'actual'not in fields
    for year in [2023,2024]:refs[f'{year}/cat_medium']=cached['inputs'][f'direct/{year}/rush_rec_yd/direct_catboost_medium']
    for key in ['direct_registration','v2_registration','category_contract']:refs[key]=cached['inputs'][key]
    refs['source_execution']=bind(original);refs['source_completion']=bind(base/'completion.json');refs['source_freeze']=bind(base/'forecast-freeze.json');refs['source_feature_equivalence']=bind(base/'approved-feature-equivalence.json');refs['cached_point_acceptance']=bind(args.cached_point_acceptance)
    res=dict(maximum_CPU_seconds=900,maximum_wall_seconds=1200,maximum_RSS_bytes=2147483648,maximum_address_space_bytes=8589934592,maximum_new_retained_bytes=67108864,finalization_reserve_seconds=30,threads=2,base_fits=0,dependence_fits=2,maximum_model_loads=9,HTTP=0,automatic_retries=0,actual_invocations=1)
    spec=dict(registration_id='combined-yard-copula-v1-20261025',state='DRAFT_INACTIVE_PREPARATION_ONLY',seal=None,
        source_period='2022–24 all exposed, current-vintage reconstructed kickoff+7day availability; not confirmation or prospective capture',
        training=dict(year2023=[2022],year2024=[2022,2023],labels='played-supported component labels with outcome_available_utc strictly before first evaluation cutoff',PIT='randomized exact discrete marginal interval, identity-seeded PCG64; exclude numerically unrepresented PIT interval with counts',formula='rho=n/(n+100)*Pearson(ndtri(Urush),ndtri(Urec)); n<2 or zero variance fallback0; no search'),
        evaluation_years=[2023,2024],arms=['independent_sum','shrunk_gaussian_sum'],draws=4096,
        law='Full signed original marginal CDF inverses under independent/Gaussian copula; finite draw empirical approximation of sum, never normal yards or adding medians',
        all_offered='exact combined population; RB with both native qualified marginals informed, every other row uses unchanged direct combined leafCDF law; no favorable intersection',
        qualification='both source-matched97feature rows, exact identity/context/clocks, native empty marginal fallback reasons and available supported law',
        primary='CRPS of4096draw empirical sum approximation vs exact direct combinedCDF; copula vs independence',secondary='own sum medianMAE, analytic sum meanbias, p95, p10/p90 coverage/tails, fixed push mass, zero mass, CDF-at-label calibration; Catmedium literal median-objective pointMAE only',
        joint_log_density='not estimated; no normal approximation or probability floor',push_thresholds=[0,20,40,60,80,100,150,200],
        freezes='2023 forecasts before2023training labels used for2024; both weights/four forecast factors+draw hashes before any evaluation loss; deterministic draw regeneration checked against frozenSHA',
        contrasts=dict(all_offered_pooled=8,all_offered_annual=16,RB_pooled_diagnostic=8,RB_annual_diagnostic=16,bootstrap='shared500PCG64 wholeweek1911/game1912; no row bootstrap'),
        candidate_or_tuning_change=False,automatic_selection_deployment_or_qualification=False,resources=res,
        maximum_draw_row_passes=4*sum(counts[f'{y}/rush_rec_yd']for y in [2023,2024]),maximum_marginal_query_rows=sum(counts.values()),
        maximum_forecast_attempts=4,maximum_dependence_fit_attempts=2,
        thread_environment=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS','VECLIB_MAXIMUM_THREADS'])
    config=ROOT/'config/combined-yard-copula-v1.json';config.write_text(json.dumps(spec,indent=2)+'\n')
    code={str(p.relative_to(ROOT)):bind(p)for p in (ROOT/'nfl_lab').glob('*.py')}
    for name in ['tools/run_cached_combined_yard.py','tools/supervise_cached_combined_yard.py','tools/combined_yard_native_core.py','tools/combined_yard_native_core_env_f2.py','tools/run_threshold_cdf_after_audit.py','tools/prepare_cached_combined_yard.py','tools/ngboost_law_software_v1.py']:code[name]=bind(ROOT/name)
    interp=args.interpreter;iref=bind(interp);iref['resolved_path']=str(interp.resolve())
    manifest=dict(state='DRAFT_INACTIVE_PREPARATION_ONLY',preexec_review='PENDING',seal=None,registration=bind(config),inputs=refs,code=code,
        worker=dict(cwd=str(ROOT),script=bind(ROOT/'tools/run_cached_combined_yard.py'),interpreter=iref),
        versions=wave['environment']['packages']if 'packages'in wave['environment']else {k:v for k,v in wave['environment'].items()if k in ['numpy','pandas','scipy','scikit-learn','joblib','pyarrow','threadpoolctl']},
        output=str(args.output),source_metadata_only=True,libc=bind(args.libc),
        original_source_sha=wave['source_commit'],shared_core_baseline_sha='1ef8e8a4109ebc2c098e6f814d72e7aeb17da66cba31d0dfea809d6ac7d751a6',native_helper_version='combined-yard-native-env-f2-v1',native_helper_binding=code['tools/combined_yard_native_core_env_f2.py'])
    for name,obj in [('EXECUTION-DRAFT.json',manifest),('FOOTER-METADATA.json',schema),('PENDING-GATES.json',dict(state='NO_NUMERICAL_GO',pending=['Independent source/synthetic capability review','Root/reviewer scientific registration seal','Exact final source/software/input/manifest closure review and root seal','Sole recorded rootGO matching final manifest SHA','Separate native-supervised actual allocation; no retries'],models_or_values_decoded=0,source_CAS_HTTP_mutations=0))]:
        (dest/name).write_text(json.dumps(obj,indent=2)+'\n')
    print(json.dumps(dict(manifest=bind(dest/'EXECUTION-DRAFT.json'),registration=bind(config),query_counts=counts,actual_numeric_or_model_reads=0)))

if __name__=='__main__':main()
