"""Sealed bounded caller for the correction extension and frozen old helpers."""
import os
import sys
from direct_booster_frozen_report_run import arm_parent_death,pin,sha
ARMED_PARENT=None
if __name__=='__main__':
    try:ARMED_PARENT=int(sys.argv[sys.argv.index('--parent-pid')+1])
    except (ValueError,IndexError):raise SystemExit('explicit guarded parent required')
    arm_parent_death(ARMED_PARENT)

import importlib.metadata
import importlib.util
import json
from pathlib import Path
from direct_xgboost_binary_recovery_run import arguments,load

POLICY_SHA256='0e94af3599fb525e933989c6adaa29385f4da6ef13f6cba5258f47d205aea03a'
CORE_SHA256='077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2'


def verify(freeze):
    if freeze['plan_sha256']!=POLICY_SHA256 or sha(freeze['plan_path'])!=POLICY_SHA256:raise ValueError('exact registered correction policy required')
    policy=json.loads(Path(freeze['plan_path']).read_text());spec=freeze['execution_metadata'];budget=policy['budgets']
    if spec['registration_id']!=policy['registration_id'] or spec['budgets']!=budget:raise ValueError('correction registration changed')
    for name,expected in dict(actual_invocations=1,wall_seconds=600,CPU_seconds=600,combined_RSS_bytes=1073741824,
            numerical_threads=2,new_retained_bytes=50331648,shared_retention_bytes=536870912,HTTP=0,
            correction_fit_attempts=44,planned_forecast_row_incidences=569184,forecast_row_incidences=600000,
            per_fit_CPU_seconds=20,per_fit_wall_seconds=20,CDF_refits_model_loads_law_calls=0,automatic_retries=0).items():
        if budget[name]!=expected:raise ValueError('fixed correction resource/search budget changed')
    for key,value in policy.items():
        if spec.get(key)!=value:raise ValueError('registered correction contract changed:'+key)
    bindings={x['path']:x for x in freeze['bindings']}
    if len(bindings)!=len(freeze['bindings']):raise ValueError('duplicate execution binding')
    required={str(p) for p in (Path(freeze['code_root'])/'nfl_lab').glob('*.py')}
    required|={freeze['plan_path'],*(x['path'] for x in freeze['tools'].values()),
        *(v['path'] for v in spec.values() if isinstance(v,dict) and 'path' in v),
        *(v['path'] for v in spec['queries'].values())}
    required|={m['binding']['path'] for year in spec['control_metadata'].values() for target in year.values() for m in target.values()}
    if not required<=set(bindings):raise ValueError('complete correction helper/config/input freeze required')
    for item in freeze['bindings']:pin(item)
    if spec['correction_extension']['sha256']!=CORE_SHA256:raise ValueError('tested correction core changed')
    for name,expected in (('direct_booster_screen.py','a47a5a21910a132977bda33ad531ba4c82b24cc9120143d40e3b415f32b84016'),
            ('direct_boosters.py','475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f')):
        if sha(Path(freeze['code_root'])/'nfl_lab'/name)!=expected:raise ValueError('original aggregation/scoring assembly changed')
    env=freeze['environment']
    if sys.executable!=env['executable'] or sys.version!=env['python'] or not env['file_bindings']:raise ValueError('exact original Python/environment required')
    for item in env['file_bindings']:pin(item)
    for name,version in env['packages'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('frozen dependency changed:'+name)
    if freeze['external_timeout']['path']!='/usr/bin/timeout':raise ValueError('pinned GNU timeout required')
    pin(freeze['external_timeout'])
    return spec


def extension(binding):
    name='nfl_lab.baseline_correction';path=Path(binding['path'])
    if sha(path)!=CORE_SHA256 or binding['sha256']!=CORE_SHA256:raise ValueError('correction extension hash changed')
    if name in sys.modules:
        if Path(sys.modules[name].__file__).resolve()!=path.resolve():raise ValueError('correction extension path collision')
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def main():
    args=arguments()
    if ARMED_PARENT is None or args.parent_pid!=ARMED_PARENT or os.getppid()!=ARMED_PARENT:raise RuntimeError('worker parent-death guard absent')
    def deny(event,values):
        if event.startswith('socket.') or event in {'subprocess.Popen','os.posix_spawn','os.fork','os.forkpty','os.system'}:
            raise RuntimeError('correction worker forbids network/child processes')
    sys.addaudithook(deny)
    freeze=load(args.freeze,args.freeze_sha256);spec=verify(freeze)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS'):os.environ[name]='2'
    sys.path.insert(0,freeze['code_root']);extension(spec['correction_extension'])
    from baseline_correction_orchestrator import run
    run(spec,plan_sha256=freeze['plan_sha256'],final_static=lambda:verify(freeze))
    print(json.dumps(dict(phase='BASELINE_CORRECTION_REPORT_COMPLETE',forecast_files=66,fit_attempts=44,new_HTTP=0)),flush=True)


if __name__=='__main__':main()
