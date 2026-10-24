"""Prepare a compact, nonexecutable interval freeze from accepted metadata.

Run only in a separately authorized metadata packet. No Parquet decode, base
model, storage/CAS write, calibration or experiment invocation occurs here.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

from freeze_direct_booster_frozen_report import full as pin, sha

ROOT = Path(__file__).resolve().parents[1]

METADATA_SHA256 = '7ee59681b6cf117ec7578d64efe76b0d03a36b28337ede1aa80702191149ce16'
PARENT_SHA256 = 'a8b258d68ee6e00707d770d6949e1559d1008fbf3d47bb8e4931b22080a3cec0'
TARGETS = ('pass_yd', 'pass_td', 'pass_cmp', 'pass_att', 'pass_int',
    'rush_yd', 'rush_att', 'rec', 'rec_yd', 'rush_rec_yd')
YEARS = (2022, 2023, 2024)
MANAGED = Path('/workspace/website-methods-research/resumed')


def accepted(reference):
    """Hash-only acceptance of an existing metadata-bound file."""
    current = pin(reference['path'])
    if any(current[key] != reference[key] for key in ('path', 'sha256', 'bytes')):
        raise ValueError('accepted interval metadata/input changed: '+reference['path'])
    return current


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--draft', required=True)
    parser.add_argument('--metadata', default='/tmp/conformal-interval-v1-input-metadata/RECEIPT.json')
    args = parser.parse_args()
    metadata_ref = pin(args.metadata)
    if metadata_ref['sha256'] != METADATA_SHA256:
        raise ValueError('accepted sole footer/hash inventory required')
    metadata = json.loads(Path(args.metadata).read_text())
    if (metadata['state'] != 'METADATA_ONLY_COMPLETE' or metadata['denied_effects']
        or metadata['NFL_row_groups_decoded'] != 0 or metadata['calibrations_tests_fits_HTTP_CAS_writes'] != 0
        or metadata['model_reads'] != 0 or len(metadata['cdf_files']) != 30 or len(metadata['queries']) != 3
        or len(metadata['training_audits']) != 30 or len(metadata['partition_audits']) != 3):
        raise ValueError('complete thirty-CDF/three-query metadata prerequisite required')
    policy_path = ROOT/'config/conformal-interval-v1.json'
    policy = json.loads(policy_path.read_text())
    accepted(policy['category_contract'])
    categories_ref = accepted(dict(policy['category_contract'], path=str(ROOT/'reports/all12-leaf-cdf-v1/method-config.json')))
    categories = json.loads(Path(categories_ref['path']).read_text())['categories']
    targets = tuple(policy['targets'])
    if targets != TARGETS or policy['registration_id'] != 'cdf-split-cqr-80-v1-20261024':
        raise ValueError('exact ten-target registered interval policy required')
    for relative, reference in policy['code_bindings'].items():
        accepted(dict(reference, path=str(ROOT/relative)))
    cdf = {str(year):{target:next(r for r in metadata['cdf_files'] if r['year'] == year and r['target'] == target)
        for target in targets} for year in YEARS}
    queries = {str(r['year']):r for r in metadata['queries']}
    if (set(queries) != {str(year) for year in YEARS}
        or {(r['year'], r['target']) for r in metadata['cdf_files']} != {(year,target) for year in YEARS for target in targets}
        or {(r['year'], r['target']) for r in metadata['training_audits']} != {(year,target) for year in YEARS for target in targets}
        or {r['year'] for r in metadata['partition_audits']} != set(YEARS)):
        raise ValueError('one exact inventory entry per fixed year/target required')
    for reference in (*metadata['cdf_files'], *metadata['queries']):
        if (reference['duplicate_column_names'] or reference['missing_required']
            or reference['rows'] != reference['expected_original_rows']
            or reference['row_values_or_column_statistics_read'] is not False):
            raise ValueError('accepted footer schema or original offered population is incomplete')
    projected_rows = sum(r['rows'] for r in metadata['queries']) + 2*sum(r['rows'] for r in metadata['cdf_files'])
    if projected_rows != 543312 or projected_rows > policy['budgets']['semantic_projection_row_cap']:
        raise ValueError('exact bounded interval projection inventory required')
    originals = [r for r in metadata['inputs'] if '/workspace/website-methods-research/' in r['path']]
    owned = [*originals, *metadata['cdf_files'], *metadata['queries'], *metadata['training_audits'], *metadata['partition_audits']]
    if len({r['path'] for r in owned}) != len(owned):
        raise ValueError('duplicate owned interval input path')
    owned_pins = {ref['path']:accepted(ref) for ref in owned}
    for ref in metadata['inputs']:
        accepted(ref)
    for key in ('source_policy', 'source_manifest', 'scored_freeze'):
        accepted(policy[key])
    direct = json.loads((ROOT/'config/direct-booster-report-recovery-v1.json').read_text())
    environment_path = Path(direct['original_output'])/'DIRECT_BOOSTER_SCREEN_EXECUTION_FREEZE.json'
    environment = pin(environment_path)
    if environment['sha256'] != PARENT_SHA256 or environment['sha256'] != direct['required_inputs']['original_execution_freeze']:
        raise ValueError('exact original DIRECT environment pointer required')
    parent = json.loads(environment_path.read_text())
    env = parent['environment']
    if (sys.executable != env['executable'] or sys.version != env['python']
        or len(env['file_bindings']) != 14946 or len(env['packages']) != 36
        or sha(env['inventory_path']) != env['inventory_sha256']):
        raise ValueError('original complete Python/environment inventory unavailable or changed')
    if any(importlib.metadata.version(name) != version for name,version in env['packages'].items()):
        raise ValueError('original dependency metadata changed')
    for ref in parent['environment']['file_bindings']:
        if pin(ref['path']) != ref:
            raise ValueError('original environment file differs')
    source = policy['source_policy']
    qualification = next(r for r in metadata['inputs'] if r['path'].endswith('permitted_source_features.py'))
    freezer_inputs = [policy_path, args.metadata, source['path'], qualification['path'],
        ROOT/'reports/all12-leaf-cdf-v1/method-config.json', environment_path, env['inventory_path'],
        ROOT/'config/direct-booster-report-recovery-v1.json',
        *[r['path'] for r in metadata['inputs']]]
    helper_names = ('conformal_interval_guard_v1.py', 'freeze_conformal_interval_v1.py',
        'offline_report_imports_v1.py', 'direct_xgboost_binary_recovery.py', 'direct_booster_frozen_report.py',
        'direct_booster_frozen_report_run.py', 'review_direct_booster_screen_guard_v4.py',
        'freeze_direct_booster_frozen_report.py')
    code = [*sorted((ROOT/'nfl_lab').glob('*.py')), *[ROOT/'tools'/name for name in helper_names], *freezer_inputs]
    code_refs = dict(owned_pins)
    for path in code:
        code_refs[str(Path(path))] = pin(path)
    libc = [Path(line.split()[-1]) for line in Path('/proc/self/maps').read_text().splitlines()
        if len(line.split()) >= 6 and line.split()[-1].endswith('/libc.so.6')]
    if len(set(libc)) != 1:
        raise ValueError('one already loaded libc required; no process discovery')
    base = next(r for r in originals if '/source-matched-base-' in r['path'])
    scored = next(r for r in originals if r['path'].endswith('/scored-freeze.json'))
    query = next(r for r in originals if '/direct-booster-screen-' in r['path'])
    spec = dict(registration_id=policy['registration_id'], state='UNSEALED_NOT_AUTHORIZED',
        cache='/workspace/website-methods-research/resumed/operational-storage-v2-20261023/cache',
        output='/workspace/website-methods-research/resumed/cdf-split-cqr-80-v1-20261024',
        source_policy=source, owned_inputs=[{k:r[k] for k in ('path','sha256','bytes')} for r in owned],
        queries=queries, cdf=cdf, categories={t:categories[t] for t in targets},
        partition_audits={str(r['year']):r for r in metadata['partition_audits']},
        accepted_metadata=metadata_ref, semantic_projection_rows=projected_rows,
        training_audits={str(year):{target:next(r for r in metadata['training_audits'] if r['year'] == year and r['target'] == target)
            for target in targets} for year in YEARS},
        core_binding=dict(source_policy_sha256=source['sha256'], qualification_policy_sha256=qualification['sha256'],
            forecast_freeze_sha256=base['sha256'], scored_freeze_sha256=scored['sha256'], query_freeze_sha256=query['sha256'],
            qualifier_code_sha256=pin(ROOT/'nfl_lab/cdf_evaluation.py')['sha256'], base_method='leaf_cdf',
            qualifier='nfl_lab.cdf_evaluation._observed', base_out_of_sample=True, evidence_lane='EXPOSED_HISTORICAL_RECONSTRUCTION'))
    packet = dict(schema_version='conformal-interval-execution-v1', state='DRAFT_REVIEW_REQUIRED',
        seal=dict(integrator='ROOT_MUST_SEAL', reviewer='INDEPENDENT_REVIEW_REQUIRED'), preexec_review='PENDING',
        code_root=str(ROOT), policy=pin(policy_path), execution_metadata=spec,
        parent_environment=environment, python_binary=pin(Path(sys.executable).resolve()),
        external_timeout=pin('/usr/bin/timeout'), sampler=pin(ROOT/'tools/review_direct_booster_screen_guard_v4.py'),
        libc=pin(libc[0]), bindings=list(code_refs.values()),
        limits=dict(wall_seconds=300, CPU_seconds=300, combined_RSS_bytes=536870912, numerical_threads=2,
            new_retained_bytes=16777216, shared_retention_bytes=536870912, workers=1, worker_children=0,
            HTTP=0, base_fits_predictions_models_sources=0, retries=0),
        requested_model='GPT-6.1 Sol Extra High', actual_backend='UNATTESTED')
    for key in ('parent_environment', 'python_binary', 'external_timeout', 'sampler', 'libc', 'policy'):
        reference = packet[key]
        code_refs[reference['path']] = reference
    packet['bindings'] = [code_refs[path] for path in sorted(code_refs)]
    packet['invocation'] = ('/usr/bin/timeout --signal=KILL 300s '+env['executable']+' -B '
        +str(ROOT/'tools/conformal_interval_guard_v1.py')
        +' --freeze <root-owned-sealed-freeze> --freeze-sha256 <exact-sha>')
    destination = Path(args.draft)
    if (not destination.is_absolute() or destination.parent.resolve() != destination.parent
        or any(p.is_symlink() for p in destination.parents) or destination.exists()
        or MANAGED == destination or MANAGED in destination.parents
        or (Path(spec['output'])/'CONSUMED.json').exists()
        or (Path(spec['output'])/'SUPERVISOR_TERMINAL.json').exists()):
        raise ValueError('fresh unconsumed draft outside all managed roots required')
    with destination.open('x') as stream:
        stream.write(json.dumps(packet, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps(dict(draft=pin(destination), owned_inputs=len(owned), environment_files=len(parent['environment']['file_bindings']),
        environment_payload='fully verified/pinned original DIRECT freeze pointer; no duplicated inventory',
        new_NFL_values_calibrations_tests_models_CAS_HTTP=0)))


if __name__ == '__main__':
    main()
