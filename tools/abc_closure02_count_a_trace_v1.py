"""Only the remaining retained Count A ordering and consumed-history checks.

No fitting, current-source inference, publication, selection replay or issuance.
The earlier native/64-row restoration proof remains a separate completed check.
"""
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import io
import json
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/execution-closure-02'
KEY = ['season', 'week', 'game_id', 'player_id']
STATE = {'model_loads': 0, 'predict_calls': 0, 'new_fits': 0,
         'current_query_inference': 0, 'new_issued_forecasts': 0}


def save_new(name, obj):
    with (OUT / name).open('xb') as stream:
        stream.write(enc(obj))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def enc(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=int, choices=[1, 2, 3], default=1)
    attempt = parser.parse_args().attempt
    suffix = f'V{attempt}.json'
    started = time.monotonic()
    cpu = time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
    # Two pre-model attempts consumed14.874CPU seconds; retain both debits.
    cpu_limits = (153, 155) if attempt == 3 else ((160, 162) if attempt == 2 else (170, 180))
    resource.setrlimit(resource.RLIMIT_CPU, cpu_limits)
    signal.alarm(230)
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import joblib
    import sklearn
    import scipy
    from nfl_lab import role_boosting as count
    from nfl_lab import count_a_mean_export_adapter_v1 as adapter
    from nfl_lab import features as feature_code
    from tools import abc_a_dynamic_carry_wave_v1 as old_wave
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    save_new('COUNT_A_MISSING_TRACE_STARTED_' + suffix, {
        **STATE, 'UTC': stamp(), 'tool_sha256': sha(Path(__file__).read_bytes()),
        'registration': 'EXECUTION_REGISTRATION_V1.json:A-CLOSURE02-MISSING-PARITY',
        'scope': 'Retained cases only; reuse earlier restore proof.'})
    try:
        store, _ = open_store(ROOT, allocation_sha256=
            'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO)

        def owned(ref):
            path = Path(ref['path'])
            owners = [owner for owner in (store, store.complete_peer,
                store.complete_peer.prior_forward, store.complete_peer.legacy)
                if any(path.is_relative_to(root) for root in owner._roots)]
            if len(owners) != 1:
                raise ValueError('exact retained owner required')
            got = owners[0].validate_reference(path, ref['sha256'])
            if got['bytes'] != ref['bytes']:
                raise ValueError('retained source size mismatch')
            return path.read_bytes()

        plan = json.loads(gzip.decompress((ROOT /
            'config/category-topfive-matched12-all-finalists-freeze-v1_2.json.gz').read_bytes()))
        entry = next(row for row in plan['extra_entries']
            if row.get('target') == 'pass_td' and row.get('method') == 'COUNT_A_MEAN')
        proof = json.loads(owned(entry['producer_proof']))
        capsule = entry['forecast']['container']
        if capsule['sha256'] != '5f55367c9f3389dbbe713b1aa95e691e77602cde99bf8e5ff657554a2d5a6a36':
            raise ValueError('different capsule')
        with zipfile.ZipFile(io.BytesIO(owned(capsule))) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        for name, ref in json.loads(members['MEMBER_MANIFEST.json'])['members'].items():
            if sha(members[name]) != ref['sha256'] or len(members[name]) != ref['bytes']:
                raise ValueError('member binding failed')
        if sha(members['MODEL.joblib']) != adapter.MODEL:
            raise ValueError('different model')
        fit_name = 'pass_td__COUNT_A_MEAN/FIT_START.json'
        fit_ref = {**proof['artifacts'][fit_name],
            'path': str(Path(entry['producer_proof']['path']).parent / fit_name)}
        recipe = json.loads(owned(fit_ref))['recipe']
        parent = sha(enc(recipe))
        if adapter.procedure_version(parent, adapter.MODEL) != adapter.PROCEDURE:
            raise ValueError('different complete procedure')
        corrector = ROOT / 'tools/modern_count_a_mean_v3.py'
        if sha(corrector.read_bytes()) != recipe['source_pins']['mean_corrector']['sha256']:
            raise ValueError('different original mean-corrector')
        audit = json.loads(members['MODEL_AUDIT.json'])
        environment = {'numpy': np.__version__, 'pandas': pd.__version__,
            'pyarrow': pa.__version__, 'sklearn': sklearn.__version__,
            'scipy': scipy.__version__, 'joblib': joblib.__version__}
        if any(value != audit['environment'][name] for name, value in environment.items()):
            raise ValueError('trusted restoration environment changed')
        _, feature_plan, _, _ = old_wave.sources()
        feature_ref = feature_plan['features']
        if feature_ref['sha256'] != audit['query_features']['sha256']:
            raise ValueError('not the original consumed feature table')
        features = pd.read_parquet(io.BytesIO(owned(feature_ref)))
        forecasts = pd.read_parquet(io.BytesIO(members['FORECASTS.parquet']))
        ordered = forecasts.sort_values(KEY, kind='stable')
        fallback = ordered.fallback.fillna('').astype(str).ne('')
        # Predeclared outcome-free choices: first two fallback, first two warm,
        # then first two latest-week warm identities. No accuracy/label access.
        latest = int(ordered.week.max())
        chosen = pd.concat([ordered.loc[fallback].head(2), ordered.loc[~fallback].head(2),
            ordered.loc[(~fallback) & ordered.week.eq(latest)].head(2)]).drop_duplicates(KEY)
        if len(chosen) != 6:
            raise ValueError('predeclared six-case diagnostic unavailable')
        query = chosen[KEY].merge(features, on=KEY, how='left', validate='one_to_one')
        if not query.position.eq('QB').all():
            raise ValueError('query identity/population mismatch')
        history = pd.concat([pd.read_parquet(io.BytesIO(owned(ref)))
            for ref in feature_plan['history_sources']], ignore_index=True)
        history = history.loc[history.roster_status.isin(['ACT', 'INA'])].copy()
        for name in ['kickoff_utc', 'outcome_available_utc']:
            history[name] = pd.to_datetime(history[name], utc=True)
        if history.duplicated(['game_id', 'player_id']).any():
            raise ValueError('history identity ambiguous')
        trace = []
        checks = []
        for row in query.itertuples():
            cutoff = pd.Timestamp(row.cutoff_utc)
            player = history.loc[history.player_id.eq(row.player_id)].sort_values(
                ['outcome_available_utc', 'kickoff_utc'], kind='stable')
            eligible = player.loc[player.outcome_available_utc.lt(cutoff)]
            if len(eligible) != int(row.f_player_games_prior):
                raise ValueError('actual prior-player row census differs from consumed feature')
            record = {name: getattr(row, name) for name in KEY}
            record.update(cutoff_UTC=str(cutoff),
                latest_actual_consumed_prior_game=None if eligible.empty else str(eligible.iloc[-1].game_id),
                latest_actual_consumed_prior_available_UTC=None if eligible.empty else str(eligible.iloc[-1].outcome_available_utc),
                source_eligible_rows=len(eligible), windows=[])
            for window in (3, 8):
                tail = eligible.tail(window)
                stats = {}
                for target in ['pass_td', 'pass_att', 'pass_cmp', 'pass_yd']:
                    values = pd.to_numeric(tail[target], errors='coerce').to_numpy(float)
                    finite = np.isfinite(values)
                    actual = float(values[finite].mean()) if finite.any() else np.nan
                    consumed = float(getattr(row, f'f_player_{target}_mean{window}'))
                    number = float(getattr(row, f'f_player_{target}_n{window}'))
                    if int(finite.sum()) != number or not np.isclose(actual, consumed,
                            rtol=1e-12, atol=1e-12, equal_nan=True):
                        raise ValueError('direct consumed prior-window reconciliation failed')
                    stats[target] = {'n': int(finite.sum()),
                        'direct_mean': actual if np.isfinite(actual) else None,
                        'consumed_mean': consumed if np.isfinite(consumed) else None}
                    checks.append((window, target))
                record['windows'].append({'window': window,
                    'game_ids': tail.game_id.astype(str).tolist(),
                    'available_UTC': tail.outcome_available_utc.astype(str).tolist(),
                    'participation': tail.participation_state.astype(str).tolist(), 'statistics': stats})
            trace.append(record)
        # Independent future-row mutation of lookup inputs: later labels cannot
        # change the earlier query's windows. This is not a full source audit.
        original = feature_code._lookup_windows(history, query, 'player_id', ['pass_td', 'pass_att'])
        changed = history.copy()
        # One cutoff at a time, because the six historical origins differ.
        mutation_checks = 0
        for row_index in range(len(query)):
            one = query.iloc[[row_index]].reset_index(drop=True)
            future = changed.outcome_available_utc.ge(pd.Timestamp(one.cutoff_utc.iloc[0]))
            altered = changed.copy()
            altered.loc[future, ['pass_td', 'pass_att']] = 1000000.
            got = feature_code._lookup_windows(altered, one, 'player_id', ['pass_td', 'pass_att'])
            for key in original:
                if not np.allclose(got[key], original[key][[row_index]], equal_nan=True):
                    raise ValueError('future-label mutation changed earlier window')
            mutation_checks += 1
        spec = importlib.util.spec_from_file_location('closure02_count_mean_corrector', corrector)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        STATE['model_loads'] = 1
        save_new('COUNT_A_MODEL_LOAD_STARTED_' + suffix, {**STATE, 'UTC': stamp(),
            'model_sha256': adapter.MODEL, 'capsule_sha256': capsule['sha256']})
        model = joblib.load(io.BytesIO(members['MODEL.joblib']))
        if type(model) is not count.RoleCountBoostingModel or model.category['target'] != 'pass_td':
            raise ValueError('trusted estimator class/category differs')
        binding = {'model_sha256': adapter.MODEL, 'parent_procedure_version': parent,
            'training_cutoff_utc': recipe['training_cutoff_utc']}

        def predict(frame):
            STATE['predict_calls'] += 1
            return adapter.predict_verified_mean(model, frame,
                mean_corrector=module.correct_fallbacks, binding=binding)

        batch = predict(query)
        reverse = predict(query.iloc[::-1].reset_index(drop=True)).iloc[::-1].reset_index(drop=True)
        singles = pd.concat([predict(query.iloc[[i]].reset_index(drop=True))
            for i in range(len(query))], ignore_index=True)
        reference = chosen.set_index(KEY).loc[pd.MultiIndex.from_frame(batch[KEY])]
        for other in [reverse, singles]:
            if not batch[KEY].equals(other[KEY]):
                raise ValueError('prediction identities/order changed')
            for name in ['expected_mean', 'selection_point', 'legacy_point_for_audit_only']:
                a = batch[name].to_numpy(float)
                b = other[name].to_numpy(float)
                if not np.array_equal(a, b, equal_nan=True):
                    raise ValueError('batch/single/order arithmetic differs')
                finite = np.isfinite(a) & np.isfinite(b)
                if not np.array_equal(a[finite].view(np.uint64), b[finite].view(np.uint64)):
                    raise ValueError('batch/single/order finite bits differ')
            if not batch.fallback_reason.fillna('').equals(other.fallback_reason.fillna('')):
                raise ValueError('batch/single/order fallback provenance differs')
        if not np.array_equal(batch.expected_mean.to_numpy(float), reference.point.to_numpy(float), equal_nan=True):
            raise ValueError('complete corrected mean changed from retained original')
        if batch.probability.notna().any() or batch.EV.notna().any() or batch.issued_at_UTC.notna().any():
            raise ValueError('diagnostic fabricated issuance/probability/value')
        private = enc({'schema': 'A-CLOSURE02-COUNT-A-TRACE-v1', 'procedure': adapter.PROCEDURE,
            'trace': trace, 'outputs': json.loads(batch.to_json(orient='records', date_format='iso'))})
        if len(private) > 262144:
            raise ValueError('registered diagnostic retention cap exceeded')
        destination = store.forward_root / ('research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/COUNT_A_CONSUMED_TRACE_' + suffix)
        store.write_bytes(destination, private)
        ref = store.validate_reference(destination, sha(private))
        usage = store.verify_retained_checkpoint()
        receipt = {'state': 'PASS_REMAINING_RETAINED_ORDER_AND_CONSUMED_HISTORY_CHECKS',
            'UTC': stamp(), **STATE, 'procedure': adapter.PROCEDURE,
            'model_sha256': adapter.MODEL, 'capsule_sha256': capsule['sha256'],
            'mean_corrector_sha256': sha(corrector.read_bytes()),
            'adapter_sha256': sha((ROOT / 'nfl_lab/count_a_mean_export_adapter_v1.py').read_bytes()),
            'feature_lookup_source_sha256': sha((ROOT / 'nfl_lab/features.py').read_bytes()),
            'environment': environment, 'retained_query_rows': len(query),
            'diagnostic_output_instances': len(query) * 3,
            'warm_rows': int(batch.fallback_reason.fillna('').eq('').sum()),
            'trained_prior_mean_rows': int(batch.fallback_reason.fillna('').ne('').sum()),
            'batch_single_reverse_finite_bit_and_fallback_parity': 'PASS',
            'original_corrected_point_parity': 'PASS',
            'direct_player_stat_window_checks': len(checks),
            'future_label_mutation_queries': mutation_checks,
            'history_policy': 'Original roster-eligible last3/8 rows, strict availability<cutoff; unknown rows consume slots.',
            'source_vintage': 'Original kickoff+7day reconstruction assumption, not authenticated publication vintages.',
            'feature_max_clock_limit': 'Player/team/opponent/league maximum is not the last consumed player game; exact player games retained privately.',
            'source_hashes': [{'sha256': r['sha256'], 'bytes': r['bytes']}
                for r in [feature_ref] + feature_plan['history_sources']],
            'private_evidence': {'logical_id': 'A-CLOSURE02-COUNT-A-CONSUMED-TRACE-v1',
                'sha256': ref['sha256'], 'bytes': ref['bytes'], 'local_readback': 'PASS',
                'offhost_restore': 'NOT_VERIFIED'},
            'retained_headroom_bytes': usage['wave_retained_limit_bytes'] - usage['new_peer_physical_bytes'],
            'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - started,
            'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            'closed_original_restore_repeated': False,
            'scope_limits': ['Not fresh current-source qualification or current-query inference.',
                'Representative player windows only, not full feature re-inference.',
                'No new fit, selection rule, football score, capture, producer handover, publication or consumer admission.']}
        save_new('COUNT_A_MISSING_TRACE_RECEIPT_' + suffix, receipt)
        print(json.dumps({name: receipt[name] for name in ['state', 'retained_query_rows',
            'predict_calls', 'direct_player_stat_window_checks', 'CPU_seconds', 'wall_seconds']}))
    except BaseException as error:
        receipt = {'state': 'FAILED_RETAINED_DIAGNOSTIC', 'UTC': stamp(), **STATE,
            'error_type': type(error).__name__, 'error_sha256': sha(str(error).encode()),
            'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - started}
        save_new('COUNT_A_MISSING_TRACE_FAILURE_' + suffix, receipt)
        print(json.dumps(receipt))
        raise
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    main()
