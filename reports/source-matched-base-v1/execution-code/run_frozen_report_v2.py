"""Report only from immutable scored rows; no source or model access."""
import sys
def deny_socket(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('Frozen reporting is cache-only')
sys.addaudithook(deny_socket)
import hashlib, json, resource, time
from pathlib import Path
import pandas as pd
from threadpoolctl import threadpool_limits
from nfl_lab import source_matched_benchmark as base
from nfl_lab.source_matched_reporting import build_target_report, reporting_header
from nfl_lab.source_matched_report_recovery import no_new_models_or_network, _pin as frozen_pin
from nfl_lab.bernoulli_diagnostics_v2 import canonical_bernoulli_diagnostics
from nfl_lab.operational_sources import load_source_policy
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.reference_runtime import _deadline

START, CPU_START = time.monotonic(), time.process_time()
ROOT = Path(__file__).resolve().parent
freeze = json.loads((ROOT/'FROZEN_REPORT_EXECUTION_FREEZE.json').read_text())
spec = json.loads(Path(freeze['plan_path']).read_text())
policy = json.loads(Path(spec['policy']['path']).read_text())
parent = Path(spec['parent_scored']['path']).parent
original = json.loads(Path(spec['parent_config']['path']).read_text())
storage = OperationalStorage(Path(original['cache']), load_source_policy(original['source_policy']['path']), state=None)
storage.register_root(ROOT)
def check():
    if time.monotonic()-START > 300 or time.process_time()-CPU_START > 450:
        raise RuntimeError('Frozen report resource budget exhausted')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 > 2147483648:
        raise RuntimeError('Frozen report RSS exhausted')
def pin(item):
    frozen_pin(item)
def write(name,value):
    check();storage.atomic_json(ROOT/name,base.clean(value),replace=False)
def frame(name,value):
    check();copy=value.copy();copy.attrs.clear()
    storage.write_dataframe(copy,ROOT/name,index=False,compression='zstd')
def final_static():
    for item in freeze['bindings']:
        pin(item)
if (ROOT/'REPORT_CONSUMED.json').exists():
    raise FileExistsError('Report-only invocation already consumed')
write('REPORT_CONSUMED.json',{'at':base.now(),'execution_freeze_sha256':base.sha(ROOT/'FROZEN_REPORT_EXECUTION_FREEZE.json'),'new_fits_predictions_law_calls_source_label_reads_HTTP':0})
try:
    with _deadline(max(.001,300-(time.monotonic()-START))), threadpool_limits(limits=2), no_new_models_or_network():
        final_static()
        for key, expected in (('parent_config','parent_config_sha256'), ('parent_scored','scored_freeze_sha256'),
                ('parent_forecast_freeze','parent_forecast_freeze_sha256'),
                ('recovery_completion','failed_recovery_completion_sha256'),
                ('recovery_failure','failed_recovery_error_sha256')):
            if spec[key]['sha256'] != policy[expected]:
                raise ValueError('Report registration parent identity differs: '+key)
        validate_owned_references(storage,{spec['parent_scored']['path']:spec['parent_scored']['sha256']})
        scored=json.loads(Path(spec['parent_scored']['path']).read_text())
        if scored['state']!='SCORED_ROWS_FROZEN' or len(scored['slots'])!=216 or len(scored['scored_files'])!=231 or scored['parent_forecast_freeze_sha256']!=policy['parent_forecast_freeze_sha256']:
            raise ValueError('Complete original scored freeze required')
        if sum(s['state']=='COMPLETED' for s in scored['slots'])!=198 or sum(s['target']=='fantasy_ppr' and s['state']=='BLOCKED' for s in scored['slots'])!=18:
            raise ValueError('Original completed and blocked slots differ')
        refs={str(parent/name):scored['bindings'][name] for name in scored['scored_files']}
        refs[spec['parent_scored']['path']]=spec['parent_scored']['sha256']
        if len(spec['prior_paired_files']) != 11:
            raise ValueError('Exactly eleven pre-existing paired files required')
        for item in spec['prior_paired_files']:
            pin(item)
            if Path(item['path']).parent != parent/'private/paired-losses':
                raise ValueError('Prior paired file escaped its frozen namespace')
            refs[item['path']]=item['sha256']
        _,receipt=validate_owned_references(storage,refs);write('owned-input-entry.json',receipt)
        categories=json.loads(Path(original['category_contract']['path']).read_text())['categories']
        for target in base.models.TARGETS:
            categories[target]=base._category(categories,target)
            categories[target]['benchmark_slots']=[{k:s[k] for k in ('year','method','state','reason') if k in s} for s in scored['slots'] if s['target']==target]
        report=reporting_header(replicates=500,seed=1703)
        paired_files=[];view_receipts=[];checks=[]
        for target in base.models.TARGETS:
            check();frames=[]
            selected=[name for name in scored['scored_files'] if Path(name).parts[3]==target]
            for name in selected:
                current=pd.read_parquet(parent/name,columns=list(base.REPORT_FIELDS))
                if target=='anytime_td' and current.method.isin(['leaf_cdf','role_prior']).all():
                    raw=current
                    current,diagnostic=canonical_bernoulli_diagnostics(raw)
                    name_v2='private/diagnostic-views/'+str(Path(name).relative_to('private/scored'))
                    saved=current.copy()
                    for column in ('cdf_actual_below','cdf_actual','crps','log_score'):
                        saved['raw_v1_'+column]=raw[column]
                    frame(name_v2,saved)
                    view_receipts.append({'original_path':name,'original_sha256':scored['bindings'][name],'view_path':name_v2,'view_sha256':base.sha(ROOT/name_v2),'diagnostic':diagnostic})
                frames.append(current)
            if frames:
                rows=pd.concat(frames,ignore_index=True)
            else:
                text={'game_id','player_id','target','method','participation_state','outcome_state','fallback','history_state','position','team','opponent','kickoff_utc','cutoff_utc'}
                rows=pd.DataFrame({name:pd.Series(dtype=bool if name=='primary_role' else object if name in text else float) for name in base.REPORT_FIELDS})
            item,pairs=build_target_report(rows,categories,target=target,replicates=500,seed=1703)
            check();relative=f'private/paired-losses/{target}.parquet';frame(relative,pairs)
            old=parent/relative
            if old.exists():
                if str(old) not in refs:
                    raise ValueError('Prior paired file was not authenticated before reading')
                pd.testing.assert_frame_equal(pairs,pd.read_parquet(old),check_exact=True)
                checks.append({'target':target,'state':'EXACT_PRIOR_PAIRED_ROWS_MATCH','rows':len(pairs),'prior_sha256':base.sha(old)})
            paired_files.append({'target':target,'path':relative,'sha256':base.sha(ROOT/relative),'rows':len(pairs)})
            report['targets'][target]=item
            write(f'private/target-reports/{target}.json',item)
            del frames,rows,pairs
        if len(view_receipts)!=6 or len(checks)!=11:
            raise ValueError('Expected six explicit Bernoulli views and eleven prior paired comparisons')
        write('private/diagnostic-views-manifest.json',{'views':view_receipts})
        write('private/paired-losses-manifest.json',{'files':paired_files,'prior_pair_checks':checks})
        final_static();_,receipt=validate_owned_references(storage,refs);write('owned-input-exit.json',receipt)
        check();write('report.json',{'at':base.now(),'report':report,'evidence':'EXPOSED_SOURCE_MATCHED_DEVELOPMENT; original and first-score recovery FAILED; report-only v2 canonical Bernoulli diagnostic views','policy_sha256':spec['policy']['sha256'],'original_scored_freeze_sha256':spec['parent_scored']['sha256'],'parent_forecast_freeze_sha256':policy['parent_forecast_freeze_sha256'],'view_manifest_sha256':base.sha(ROOT/'private/diagnostic-views-manifest.json'),'paired_manifest_sha256':base.sha(ROOT/'private/paired-losses-manifest.json'),'prior_pair_checks':checks,'new_fits_references_predictions_law_calls_HTTP_source_label_reads':0,'fixed_consumed_estimator_attempts':168,'fixed_consumed_reference_calls':66,'fixed_query_or_law_row_incidences':2302608,'promotion':'NONE'})
except BaseException as error:
    write('REPORT_FAILURE.json',{'at':base.now(),'exception':type(error).__name__,'message':str(error)})
    raise
finally:
    storage.atomic_json(ROOT/'REPORT_FINISHED.json',{'at':base.now(),'state':'COMPLETED' if (ROOT/'report.json').exists() else 'FAILED','inner_wall_seconds':time.monotonic()-START,'inner_CPU_seconds':time.process_time()-CPU_START},replace=False)
print('FROZEN_REPORT_V2_RETURNED',flush=True)
