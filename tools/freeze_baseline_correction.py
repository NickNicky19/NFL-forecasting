"""Metadata-only, unsealed correction inventory; no parquet value decoding."""
import argparse
import json
from pathlib import Path
from freeze_direct_booster_frozen_report import basic,full,sha

POLICY_SHA256='0e94af3599fb525e933989c6adaa29385f4da6ef13f6cba5258f47d205aea03a'
CONTEXT=('player_id','season','week','game_id','position','team','opponent','kickoff_utc','cutoff_utc')
FORECAST=('target','method','primary_role','point','mean','median','probability','fallback','history_state')
CONTROLS=('leaf_cdf','count_A','role_B','recent','pooled')


def footer(path):
    import pyarrow.parquet as pq
    file=pq.ParquetFile(path)
    return list(file.schema_arrow.names),file.metadata.num_rows


def build(policy_path,destination):
    if sha(policy_path)!=POLICY_SHA256:raise ValueError('exact preregistered correction policy required')
    policy=json.loads(Path(policy_path).read_text());spec=dict(policy)
    parent_root=Path(policy['parent_forecast_freeze']['path']).parent
    parent_execution=parent_root/'DIRECT_BOOSTER_SCREEN_EXECUTION_FREEZE.json'
    old=json.loads(parent_execution.read_text())
    if old['code_root']!=policy['code_root'] or old['plan_sha256']!=policy['parent_science_registration']['sha256']:
        raise ValueError('original helper/environment provenance changed')
    for name in ('parent_forecast_freeze','parent_science_registration','control_scored_freeze','category_contract','source_policy','source_manifest'):
        if basic(policy[name]['path'])!=policy[name]:raise ValueError('immutable source metadata changed:'+name)
    controls=json.loads(Path(policy['control_scored_freeze']['path']).read_text())
    category=json.loads(Path(policy['category_contract']['path']).read_text())['categories']
    if len(category)!=12 or category['fantasy_ppr']['state']=='READY':raise ValueError('all12/exactPPRblocked required')
    spec.update(parent_execution_freeze=basic(parent_execution),loaded_libc=None,query_metadata={},control_metadata={})
    libc={Path(line.split()[-1]).resolve() for line in Path('/proc/self/maps').read_text().splitlines()
        if len(line.split())>=6 and line.split()[-1].endswith('/libc.so.6')}
    if len(libc)!=1:raise ValueError('one already-loaded libc required')
    spec['loaded_libc']=basic(next(iter(libc)))
    paths={str(p) for p in (Path(policy['code_root'])/'nfl_lab').glob('*.py')}
    for year in (2022,2023,2024):
        query=policy['queries'][str(year)]
        if basic(query['path'])!=query:raise ValueError('original query changed')
        names,count=footer(query['path'])
        projected=[n for n in names if n in (*CONTEXT,'season_type','feature_max_source_available_utc') or n.startswith('f_')]
        if len(names)!=len(set(names)) or not set(CONTEXT)<=set(projected) or 'feature_max_source_available_utc' not in projected:
            raise ValueError('complete unique original query context/clocks required')
        if count!={2022:8686,2023:8606,2024:8580}[year]:raise ValueError('original offered population changed')
        spec['query_metadata'][str(year)]=dict(rows=count,projected_columns=projected,footer_columns=names)
        spec['control_metadata'][str(year)]={};paths.add(query['path'])
        for target in category:
            if target=='fantasy_ppr':continue
            spec['control_metadata'][str(year)][target]={}
            for method in CONTROLS:
                name=f'private/scored/{year}/{target}/{method}/rows.parquet'
                path=Path(policy['control_root'])/name
                if name not in controls['scored_files'] or sha(path)!=controls['bindings'].get(name):
                    raise ValueError('exact frozen scored control required')
                binding=basic(path);names,nrows=footer(path)
                if len(names)!=len(set(names)) or nrows!=count:raise ValueError('control schema/rows differ')
                meta=dict(binding=binding,rows=nrows,footer_columns=names)
                if method=='leaf_cdf':
                    needed=set(CONTEXT)|set(FORECAST)|{'actual','participation_state','outcome_state'}
                    if not needed<=set(names):raise ValueError('original CDF baseline/label contract incomplete')
                    meta['forecast_columns']=[n for n in names if n in (*CONTEXT,'season_type',*FORECAST)]
                    meta['label_columns']=[n for n in names if n in ('actual','participation_state','outcome_state',
                        'official_physical_event','participation_evidence','source_policy','stats_observed') or n.startswith('qualified_')]
                    if ('season_type' in spec['query_metadata'][str(year)]['projected_columns'])!=('season_type' in names):
                        raise ValueError('optional season_type present on only one side')
                spec['control_metadata'][str(year)][target][method]=meta;paths.add(str(path))
    tools_root=Path(__file__).resolve().parent
    names=dict(orchestrator='baseline_correction_orchestrator.py',run='baseline_correction_run.py',
        supervisor='baseline_correction_supervisor.py',builder='freeze_baseline_correction.py',
        reviewed_binary_helpers='direct_xgboost_binary_recovery.py',
        reviewed_binary_run='direct_xgboost_binary_recovery_run.py',
        reviewed_report_helpers='direct_booster_frozen_report.py',
        reviewed_report_run='direct_booster_frozen_report_run.py',
        reviewed_report_supervisor='direct_booster_frozen_report_supervisor.py',
        reviewed_report_builder='freeze_direct_booster_frozen_report.py')
    tools={key:basic(tools_root/name) for key,name in names.items()}
    extension=basic(tools_root.parent/'nfl_lab/baseline_correction.py')
    if extension['sha256']!='077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2':
        raise ValueError('tested correction core changed')
    spec['correction_extension']=extension
    paths|={str(Path(policy_path).resolve()),*(x['path'] for x in tools.values()),
        *(v['path'] for v in spec.values() if isinstance(v,dict) and 'path' in v)}
    if old['environment'].get('inventory_path'):paths.add(old['environment']['inventory_path'])
    freeze=dict(state='UNSEALED_TEMPLATE_NO_EXECUTION',seal=None,preexec_review='PENDING',code_root=policy['code_root'],
        plan_path=str(Path(policy_path).resolve()),plan_sha256=POLICY_SHA256,tools=tools,execution_metadata=spec,
        environment=old['environment'],bindings=[full(p) for p in sorted(paths)],external_timeout=full('/usr/bin/timeout'),
        invocation='/usr/bin/timeout --signal=KILL --kill-after=1s 600s <frozen-python> -B <supervisor> --freeze <sealed-owned-freeze> --freeze-sha256 <exact-sha>')
    destination=Path(destination)
    if destination.exists() or Path(policy['output']) in destination.parents:raise ValueError('unused template path outside managed roots required')
    destination.write_text(json.dumps(freeze,sort_keys=True,indent=2)+'\n')
    return freeze


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--policy',required=True)
    parser.add_argument('--policy-sha256',required=True);parser.add_argument('--destination',required=True)
    args=parser.parse_args()
    if args.policy_sha256!=POLICY_SHA256:raise ValueError('exact registered policy hash required')
    freeze=build(args.policy,args.destination)
    print(json.dumps(dict(state=freeze['state'],path=args.destination,sha256=sha(args.destination),bindings=len(freeze['bindings']),NFL_values_decoded=0)))


if __name__=='__main__':main()
