"""Metadata-only preparation of the finite exposed opportunity study.

Only hashes, Parquet footers and existing manifests are read. No NFL statistic,
participation label, forecast value, fit, score, HTTP or managed write is used.
This builder produces an unsealed template; it cannot authorize execution.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from freeze_direct_booster_frozen_report import basic, full, sha

PARENT = Path('/workspace/website-methods-research/resumed/direct-booster-screen-v1-20261023/DIRECT_BOOSTER_SCREEN_EXECUTION_FREEZE.json')
PARENT_SHA = 'a8b258d68ee6e00707d770d6949e1559d1008fbf3d47bb8e4931b22080a3cec0'
CONTEXT = ('player_id', 'season', 'week', 'game_id', 'position', 'team', 'opponent', 'kickoff_utc', 'cutoff_utc')
FORECAST = ('target', 'method', 'primary_role', 'point', 'mean', 'median', 'probability', 'fallback', 'history_state')
CONTROLS = ('leaf_cdf', 'count_A', 'role_B', 'recent', 'pooled')
MODULES = ('dynamic_opportunity_core', 'dynamic_opportunity_history', 'dynamic_opportunity_history_replay_v2',
           'dynamic_opportunity_source', 'dynamic_opportunity_study', 'dynamic_opportunity_source_helpers',
           'dynamic_opportunity_recovery', 'dynamic_opportunity_backend', 'termination_accounting')


def footer(path):
    import pyarrow.parquet as pq
    file = pq.ParquetFile(path)
    names = list(file.schema_arrow.names)
    if len(names) != len(set(names)):
        raise ValueError('duplicate persisted columns')
    return names, file.metadata.num_rows


def build(root, policy_path, source_path, destination, *, policy_sha256, source_sha256,
          recovery_path=None, recovery_sha256=None):
    root, destination = Path(root).resolve(), Path(destination)
    if sha(policy_path) != policy_sha256 or sha(source_path) != source_sha256 or sha(PARENT) != PARENT_SHA:
        raise ValueError('exact original parent and new metadata policies required')
    policy = json.loads(Path(policy_path).read_text())
    source = json.loads(Path(source_path).read_text())
    if policy['registration_id'] != 'dynamic-opportunity-study-v1-20261023' or policy['state'] != 'PREPARED_NO_INVOCATION':
        raise ValueError('unconsumed finite study policy required')
    if source['state'] != 'DRAFT_NO_EXECUTION' or source['seal'] is not None:
        raise ValueError('source template must remain original and unsealed')
    parent = json.loads(PARENT.read_text())
    spec = dict(policy)
    spec.update(state='UNSEALED_TEMPLATE_NO_EXECUTION', seal=None, categories=None,
        cache='/workspace/website-methods-research/resumed/operational-storage-v2-20261023/cache',
        output='/workspace/website-methods-research/resumed/dynamic-opportunity-study-v1-20261023',
        source_policy=source['source_policy'], source_plan=deepcopy(source),
        source_plan_template=basic(source_path), policy_template=basic(policy_path),
        category_contract=basic(root/'reports/all12-leaf-cdf-v1/method-config.json'),
        control_freeze=source['controls']['scored_freeze'], control_metadata={}, query_metadata={})
    recovery = None
    if recovery_path is not None:
        if not recovery_sha256 or sha(recovery_path) != recovery_sha256:
            raise ValueError('exact separately registered recovery policy required')
        recovery = json.loads(Path(recovery_path).read_text())
        if (recovery['schema_version'] != 'dynamic-opportunity-source-recovery-v2-20261024'
                or recovery['original_registration_id'] != policy['registration_id']
                or recovery['state'] != 'REGISTERED_NO_INVOCATION'):
            raise ValueError('unconsumed explicit recovery envelope required')
        spec.update(recovery_envelope=recovery, recovery_plan=basic(recovery_path), output=recovery['output'])
    for item in source['owned_inputs']:
        if basic(item['path']) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
            raise ValueError('source binding changed')
    contract = json.loads(Path(spec['category_contract']['path']).read_text())
    if spec['category_contract']['sha256'] != '9154f113d75b8b6af3cbc21e0c407e7af4b79b29e53a288d487a2dc868473de4':
        raise ValueError('original twelve-category contract changed')
    spec['categories'] = {target: dict(value, target=target) for target, value in contract['categories'].items()}
    if len(spec['categories']) != 12 or spec['categories']['fantasy_ppr']['state'] == 'READY':
        raise ValueError('twelve explicit categories and blocked exact PPR required')
    if basic(spec['control_freeze']['path']) != spec['control_freeze']:
        raise ValueError('control freeze changed')
    controls = json.loads(Path(spec['control_freeze']['path']).read_text())
    spec['control_freeze_state'] = controls['state']
    owned = {r['path']: dict(r) for r in source['owned_inputs']}
    if recovery is not None:
        reuse = recovery['reuse']
        for item in (reuse['calendar'], *reuse['contexts'].values()):
            if basic(item['path']) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
                raise ValueError('owned reusable context/calendar changed')
            owned[item['path']] = dict(item)
        for item in recovery['previous_receipts']:
            if basic(item['path']) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
                raise ValueError('earlier failed/diagnosis receipt changed')
            if Path(recovery['original_output']) in Path(item['path']).parents:
                owned[item['path']] = dict(item)
    for item in (spec['control_freeze'],):
        owned[item['path']] = item
    for year in (2022, 2023, 2024):
        query = source['queries'][str(year)]
        names, count = footer(query['path'])
        if count != {2022:8686, 2023:8606, 2024:8580}[year] or not set(CONTEXT) <= set(names):
            raise ValueError('original query metadata changed')
        spec['query_metadata'][str(year)] = dict(rows=count, footer_columns=names)
        spec['control_metadata'][str(year)] = {}
        for target in ('rush_att', 'rec', 'rec_yd'):
            spec['control_metadata'][str(year)][target] = {}
            for method in CONTROLS:
                name = f'private/scored/{year}/{target}/{method}/rows.parquet'
                path = Path(source['controls']['root'])/name
                binding = basic(path)
                if name not in controls['scored_files'] or controls['bindings'].get(name) != binding['sha256']:
                    raise ValueError('original control row file not authenticated')
                columns, nrows = footer(path)
                if nrows != count or not (set(CONTEXT)|set(FORECAST)|{'actual', 'participation_state', 'outcome_state'}) <= set(columns):
                    raise ValueError('original control population/schema incomplete')
                if ('season_type' in columns) != ('season_type' in names):
                    raise ValueError('optional persisted period differs')
                meta = dict(binding=binding, rows=nrows, footer_columns=columns,
                    forecast_columns=[n for n in columns if n in (*CONTEXT, 'season_type', *FORECAST)],
                    label_columns=[n for n in columns if n in ('actual', 'participation_state', 'outcome_state',
                        'official_physical_event', 'participation_evidence', 'source_policy', 'stats_observed') or n.startswith('qualified_')])
                spec['control_metadata'][str(year)][target][method] = meta
                owned[str(path)] = binding
    spec['owned_inputs'] = [owned[p] for p in sorted(owned)]
    spec['scorer_sha256'] = sha(root/'nfl_lab/direct_boosters.py')
    spec['pair_scorer_sha256'] = sha(root/'nfl_lab/direct_booster_screen.py')
    if spec['scorer_sha256'] != '475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f' or spec['pair_scorer_sha256'] != 'a47a5a21910a132977bda33ad531ba4c82b24cc9120143d40e3b415f32b84016':
        raise ValueError('unchanged shared scorer required')
    extensions = [dict(module='nfl_lab.'+name, **basic(root/'nfl_lab'/f'{name}.py')) for name in MODULES]
    tools = {key: basic(root/'tools'/name) for key, name in dict(run='run_dynamic_opportunity_study.py',
        supervisor='dynamic_opportunity_study_supervisor.py', builder='freeze_dynamic_opportunity_v1.py',
        report_helpers='direct_booster_frozen_report.py', report_run_helpers='direct_booster_frozen_report_run.py',
        report_supervisor_helpers='direct_booster_frozen_report_supervisor.py',
        offline_import_helpers='offline_report_imports_v1.py',
        binary_run_helpers='direct_xgboost_binary_recovery_run.py', binary_helpers='direct_xgboost_binary_recovery.py',
        metadata_helpers='freeze_direct_booster_frozen_report.py').items()}
    resource_guard = basic(root/'tools/dynamic_history_guard_software_v2.py')
    resource_sampler = basic(root/'tools/raw_orphan_zero_audit_execute_v3.py')
    if resource_guard['sha256'] != 'e893a049a3f10f65ba115c8300caffd4e7ec962415385dd49d3de504ebae3443' or resource_sampler['sha256'] != '0477bd08e36700f27b7d9c356f51fabf1b623a9f63e792581f3a5f6071d177de':
        raise ValueError('accepted resource guard changed')
    paths = set(owned)|{str(p.resolve()) for p in (root/'nfl_lab').glob('*.py')}
    paths |= {str(Path(policy_path).resolve()), str(Path(source_path).resolve()), str(PARENT), spec['category_contract']['path'],
        *(v['path'] for v in tools.values()), resource_guard['path'], resource_sampler['path']}
    paths |= {v['path'] for v in source.values()
              if isinstance(v, dict) and {'path', 'bytes', 'sha256'} <= set(v)}
    if recovery is not None:
        paths |= {str(Path(recovery_path).resolve()), *(item['path'] for item in recovery['previous_receipts'])}
    env = parent['environment']
    if env.get('inventory_path'):
        paths.add(env['inventory_path'])
    freeze = dict(schema_version='dynamic-opportunity-study-v1-execution', state='UNSEALED_TEMPLATE_NO_EXECUTION',
        seal=None, preexec_review='PENDING', code_root=str(root), plan_path=str(Path(policy_path).resolve()),
        plan_sha256=policy_sha256, execution_metadata=spec, extension_modules=extensions, tools=tools,
        resource_guard=resource_guard, resource_sampler=resource_sampler, environment=env,
        bindings=[full(p) for p in sorted(paths)], external_timeout=full('/usr/bin/timeout'),
        parent_execution=basic(PARENT), NFL_values_decoded=0,
        invocation='/usr/bin/timeout --signal=KILL --kill-after=1s 600s <frozen-python> -B <supervisor> --freeze <sealed-freeze> --freeze-sha256 <exact-sha>')
    if recovery is not None:
        body = json.dumps(env, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        freeze.pop('environment')
        freeze['environment_reference'] = dict(**basic(PARENT), json_pointer='/environment',
            environment_sha256=hashlib.sha256(body).hexdigest())
        freeze['external_timeout_seconds'] = recovery['remaining_limits']['wall_seconds']
        freeze['invocation'] = freeze['invocation'].replace(' 600s ', ' ' + str(freeze['external_timeout_seconds']) + 's ')
    if destination.exists() or Path(spec['output']) in destination.parents:
        raise ValueError('fresh preparation destination outside managed output required')
    destination.write_text(json.dumps(freeze, sort_keys=True, indent=2)+'\n')
    return freeze


def main():
    parser = argparse.ArgumentParser()
    for name in ('code-root', 'policy', 'policy-sha256', 'source-plan', 'source-plan-sha256', 'destination'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--recovery-plan'); parser.add_argument('--recovery-plan-sha256')
    args = parser.parse_args()
    freeze = build(args.code_root, args.policy, args.source_plan, args.destination,
        policy_sha256=args.policy_sha256, source_sha256=args.source_plan_sha256,
        recovery_path=args.recovery_plan, recovery_sha256=args.recovery_plan_sha256)
    print(json.dumps(dict(state=freeze['state'], bindings=len(freeze['bindings']),
        destination=args.destination, sha256=sha(args.destination), NFL_values_decoded=0)))


if __name__ == '__main__':
    main()
