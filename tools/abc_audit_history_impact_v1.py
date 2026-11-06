"""Zero-model audit of exact retained history/feature bytes; no new grades.

Prove original-rebuild parity before attributing a feature change to this fix.
Missing original context remains unresolved rather than silently refitted.
"""
from pathlib import Path
import argparse
import datetime
import gzip
import gc
import hashlib
import importlib.util
import io
import json
import resource
import signal
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/audit-remediation-20261105'
KEY = ['game_id', 'player_id']


def sha(body):
    return hashlib.sha256(body).hexdigest()


def enc(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=int, choices=[1, 2, 3, 4, 5, 6], default=1)
    attempt = parser.parse_args().attempt
    suffix = f'V{attempt}.json'
    start = time.monotonic()
    cpu = time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
    resource.setrlimit(resource.RLIMIT_CPU, (163, 166) if attempt == 6 else ((160, 162) if attempt == 4 else ((152, 155) if attempt == 2 else (225, 240))))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('registered audit wall limit')))
    signal.signal(signal.SIGXCPU, lambda *_: (_ for _ in ()).throw(TimeoutError('registered audit CPU limit')))
    signal.alarm(280 if attempt in [4, 6] else (270 if attempt == 2 else 350))
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import nfl_lab
    from nfl_lab import data
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    if attempt >= 3:
        # Standard bounded allocator, preserving the same address-space cap.
        # The default pool can reserve large virtual arenas under RLIMIT_AS.
        pa.set_memory_pool(pa.system_memory_pool())

    def load(name, path, digest):
        if sha(path.read_bytes()) != digest:
            raise ValueError('reviewed feature source changed')
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    old = load('audit_impact_old_features',
        Path('/tmp') / 'abc-execution-closure02-public/A_bound_features_before.py',
        '2a6acd56fea5f9805f0db8fa0684eaa0c57b3c3a89bf77fdc60e948883a2fec9')
    new = load('audit_impact_fixed_features',
        ROOT.parent / 'nfl-audit-remediation-a/nfl_lab/features.py',
        'c3dcc6f3dd3cf019b358ffc86434e2659351c0aeb60c00256ab23be2039a4ade')
    result = {'id': 'A-AUDIT-HISTORY-IMPACT-v1',
        'started_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'STARTED', 'old_feature_sha256': sha(Path(old.__file__).read_bytes()),
        'new_feature_sha256': sha(Path(new.__file__).read_bytes()),
        'model_loads_fits_prediction_calls_new_grades': 0, 'panels': [],
        'arrow_memory_pool': pa.default_memory_pool().backend_name,
        'phase': 'SOURCE_ATTACH'}
    with (OUT / ('HISTORY_IMPACT_STARTED_' + suffix)).open('xb') as stream:
        stream.write(enc(result))
    try:
        store, _ = open_store(ROOT, allocation_sha256=
            'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO)

        def owned(ref):
            p = Path(ref['path'])
            owners = [owner for owner in (store, store.complete_peer,
                store.complete_peer.prior_forward, store.complete_peer.legacy)
                if any(p.is_relative_to(root) for root in owner._roots)]
            if len(owners) != 1:
                raise ValueError('unique source owner required')
            checked = owners[0].validate_reference(p, ref['sha256'])
            if checked['bytes'] != ref['bytes']:
                raise ValueError('pinned source bytes differ')
            return p.read_bytes()

        training = json.loads((ROOT / 'config/weekly-future-training-v3.json').read_bytes())
        if attempt >= 5 and sha((ROOT / 'nfl_lab/operational_sources.py').read_bytes()) != training['source_contract']['feature_builder_sha256']:
            raise ValueError('Original full operational feature wrapper differs')
        followup = json.loads(gzip.decompress((ROOT /
            'config/category-topfive-matched12-inference-followup-v1.json.gz').read_bytes()))
        train_ref = training['features']
        query_ref = followup['features']
        frozen = json.loads(gzip.decompress((ROOT /
            'config/category-topfive-matched12-all-finalists-freeze-v1_2.json.gz').read_bytes()))
        count_entry = next(r for r in frozen['extra_entries']
            if r.get('target') == 'pass_td' and r.get('method') == 'COUNT_A_MEAN')
        count_capsule = count_entry['forecast']['container']
        with zipfile.ZipFile(io.BytesIO(owned(count_capsule))) as archive:
            audit = json.loads(archive.read('MODEL_AUDIT.json'))
        if (audit['training_features']['sha256'] != train_ref['sha256'] or
                audit['query_features']['sha256'] != query_ref['sha256']):
            raise ValueError('CountA model audit binds different training/query inputs')
        result['CountA_original_model_binding'] = {'capsule_sha256': count_capsule['sha256'],
            'model_member_sha256': audit['model']['sha256'],
            'training_feature_sha256': train_ref['sha256'], 'query_feature_sha256': query_ref['sha256'],
            'scope': 'Exact CountA and this retained source only; no inference that unseen native Root model inputs are identical.'}
        train = pd.read_parquet(io.BytesIO(owned(train_ref)))
        query = history = None

        def census(frame):
            have = 'outcome_available_utc' in frame
            stamps = pd.to_datetime(frame.outcome_available_utc, utc=True) if have else None
            unknown = None if not have else int(stamps.isna().sum())
            eligible = frame if not have else frame.loc[stamps.notna()]
            inversions = {}
            for entity in ['player_id', 'team']:
                count = 0
                if have:
                    for _, group in eligible.groupby(entity, sort=False):
                        group = group.sort_values(['outcome_available_utc', 'kickoff_utc'], kind='stable')
                        times = pd.to_datetime(group.kickoff_utc, utc=True)
                        count += int((times.diff().dropna() < pd.Timedelta(0)).any())
                inversions[entity] = count
            ids = frame.player_id.astype(str)
            return {'rows': len(frame), 'seasons': sorted(map(int, frame.season.dropna().unique())),
                'duplicate_player_games': int(frame.duplicated(KEY).sum()),
                'noncanonical_GSIS_rows': int((~ids.str.fullmatch(r'00-\d{7}')).sum()),
                'whitespace_player_rows': int(ids.ne(ids.str.strip()).sum()),
                'availability_column_present': have, 'explicit_unknown_clock_rows': unknown,
                'clock_dtypes': {name: str(frame[name].dtype) for name in
                    ['kickoff_utc', 'cutoff_utc', 'outcome_available_utc'] if name in frame},
                'known_groups_with_game_time_reversal_under_publication_order': inversions,
                'source_availability': 'Retained declared seven-day reconstruction; not authenticated observation vintage.'}

        if attempt >= 2:
            prior = json.loads((OUT / 'HISTORY_IMPACT_RECEIPT_V1.json').read_bytes())
            if prior['training_input']['sha256'] != train_ref['sha256'] or prior['query_input']['sha256'] != query_ref['sha256']:
                raise ValueError('prior census binds different sources')
            result.update({key: prior[key] for key in ['training_input', 'query_input', 'history_sources', 'raw_history']})
            result['prior_census_reused'] = 'Exact original verified source hashes; failed matrix rebuild is not a completed parity check.'
        else:
            query = pd.read_parquet(io.BytesIO(owned(query_ref)))
            histories = [pd.read_parquet(io.BytesIO(owned(ref))) for ref in followup['history_sources']]
            history = pd.concat(histories, ignore_index=True)
            history = history.loc[history.roster_status.isin(['ACT', 'INA'])].copy()
            result['training_input'] = {'sha256': train_ref['sha256'], 'bytes': train_ref['bytes'], **census(train)}
            result['query_input'] = {'sha256': query_ref['sha256'], 'bytes': query_ref['bytes'], **census(query)}
            result['raw_history'] = census(history)
        result['history_sources'] = [{'sha256': ref['sha256'], 'bytes': ref['bytes']}
            for ref in followup['history_sources']]
        diffs = []

        def compare(left, right, columns, label, mask=None):
            if len(left) != len(right) or not left[KEY].reset_index(drop=True).equals(right[KEY].reset_index(drop=True)):
                raise ValueError('comparison row identities/order differ')
            selected = np.arange(len(left)) if mask is None else np.flatnonzero(np.asarray(mask))
            changed_rows = np.zeros(len(selected), bool)
            details = []
            for name in columns:
                a = pd.to_numeric(left[name], errors='raise').to_numpy(float)
                b = pd.to_numeric(right[name], errors='raise').to_numpy(float)
                if mask is not None:
                    a, b = a[selected], b[selected]
                same = (a == b) | (np.isnan(a) & np.isnan(b))
                changed_rows |= ~same
                if (~same).any():
                    finite = np.isfinite(a) & np.isfinite(b)
                    details.append({'feature': name, 'changed_rows': int((~same).sum()),
                        'max_finite_absolute_difference': float(np.abs(a[finite] - b[finite]).max()) if finite.any() else None})
            if changed_rows.any():
                d = left[KEY + ['season', 'week']].iloc[selected[changed_rows]].copy()
                d['comparison'] = label
                diffs.append(d)
            return {'columns': len(columns), 'changed_rows': int(changed_rows.sum()),
                'changed_columns': details, 'exact_finite_and_missing_equivalence': not changed_rows.any()}

        def clocks(left, right, mask=None):
            name = 'feature_max_source_available_utc'
            if name not in left or name not in right:
                return {'complete': False, 'changed_rows': None,
                    'reason': 'Expected source-guard clock absent.'}
            a = pd.to_datetime(left[name], utc=True)
            b = pd.to_datetime(right[name], utc=True)
            if mask is not None:
                indices = np.flatnonzero(np.asarray(mask))
                a, b = a.iloc[indices].reset_index(drop=True), b.iloc[indices].reset_index(drop=True)
            same = a.eq(b) | (a.isna() & b.isna())
            return {'complete': True, 'changed_rows': int((~same).sum())}

        def raw(frame):
            if attempt >= 5:
                needed = list(dict.fromkeys(KEY + ['season','week','team','opponent','position','kickoff_utc','cutoff_utc','outcome_available_utc','participation_state','is_home'] + old.PLAYER_STATS + ['team_stat_' + name for name in old.TEAM_STATS]))
                return frame.loc[:, [name for name in needed if name in frame]].copy()
            return frame.drop(columns=[c for c in frame if c.startswith('f_') or c == 'feature_max_source_available_utc'])

        def rebuild(module, frame):
            value = module.build_features(raw(frame))
            if attempt >= 5:
                # Original operational_sources.py line496, source hash pinned.
                # Incomplete nonappearance denominator is not a play probability.
                value['f_player_play_rate8'] = np.nan
            return value

        # The original stored training table retains the unfiltered source
        # context. If that assumption fails, original-rebuild parity will fail
        # visibly and no historical/model compatibility is certified.
        result['phase'] = 'TRAINING_OLD_REBUILD'
        before = rebuild(old, train)
        names = [c for c in train if c.startswith('f_') and c in before]
        missing_train = [c for c in train if c.startswith('f_') and c not in before]
        train_old = compare(train, before, names, 'TRAINING_STORED_VS_ORIGINAL_REBUILD')
        result['completed_training_original_rebuild'] = train_old
        if attempt >= 2:
            # Never keep two complete 62k-row feature builds alive at once.
            # This is an in-memory representation only, not a new archive.
            compact = list(dict.fromkeys(KEY + ['season', 'week', 'feature_max_source_available_utc'] + names))
            buffer = io.BytesIO()
            before[compact].to_parquet(buffer, index=False)
            before_bytes = buffer.getvalue()
            del buffer, before
            gc.collect()
            pa.default_memory_pool().release_unused()
        result['phase'] = 'TRAINING_FIXED_REBUILD'
        after = rebuild(new, train)
        result['phase'] = 'TRAINING_MATRIX_COMPARE'
        if attempt >= 2:
            before = pd.read_parquet(io.BytesIO(before_bytes))
            del before_bytes
        train_fixed = compare(before, after, names, 'TRAINING_OLD_VS_REPAIRED')
        result['completed_training_repair_effect'] = train_fixed
        fit_mask = (pd.to_datetime(train.outcome_available_utc, utc=True) < pd.Timestamp(training['training_cutoff_utc']))
        if 'game_type' in train:
            fit_mask &= train.game_type.eq('REG')
        result['phase'] = 'TRAINING_FIT_SCOPE_COLUMNWISE_COMPARE'
        fit_original = compare(train, before, names, 'REGISTERED_EARLIER_FIT_ROWS_STORED_VS_ORIGINAL', fit_mask)
        fit_repair = compare(before, after, names, 'REGISTERED_EARLIER_FIT_ROWS_OLD_VS_REPAIRED', fit_mask)
        fit_original_clock = clocks(train, before, fit_mask)
        fit_repaired_clock = clocks(before, after, fit_mask)
        result['panels'].append({'panel': 'ORIGINAL_TRAINING_FEATURE_TABLE',
            'rows': len(train), 'original_rebuild': train_old, 'repair_effect': train_fixed,
            'missing_expected_feature_columns': missing_train,
            'declared_fit_cutoff': training['training_cutoff_utc'], 'fit_eligible_rows': int(fit_mask.sum()),
            'fit_scope_original_rebuild': fit_original, 'fit_scope_repair_effect': fit_repair,
            'fit_stored_vs_original_guard_clock': fit_original_clock,
            'fit_original_vs_repaired_guard_clock': fit_repaired_clock})
        del before, after
        del train
        result['phase'] = 'QUERY_SOURCE_ASSEMBLY'
        gc.collect()
        pa.default_memory_pool().release_unused()
        if query is None:
            query = pd.read_parquet(io.BytesIO(owned(query_ref)))
            histories = [pd.read_parquet(io.BytesIO(owned(ref))) for ref in followup['history_sources']]
            history = pd.concat(histories, ignore_index=True)
            history = history.loc[history.roster_status.isin(['ACT', 'INA'])].copy()
            del histories
        # Resolve historical target identity by its already retained source row;
        # only absent future contexts are appended, with unknown outcome clocks.
        if history.duplicated(KEY).any() or query.duplicated(KEY).any():
            raise ValueError('source/query duplicate identities need original version resolution')
        qraw = raw(query).copy()
        indexed = history.set_index(KEY, drop=False)
        qindex = pd.MultiIndex.from_frame(qraw[KEY])
        existing = qindex.isin(indexed.index)
        for i in np.flatnonzero(existing):
            key = tuple(qraw.iloc[i][KEY])
            indexed.loc[key, 'cutoff_utc'] = qraw.iloc[i].cutoff_utc
        absent = qraw.loc[~existing].copy()
        absent['outcome_available_utc'] = pd.NaT
        combined = pd.concat([indexed.reset_index(drop=True), absent], ignore_index=True)
        result['phase'] = 'QUERY_OLD_REBUILD'
        before_full = rebuild(old, combined)
        before = before_full.set_index(KEY, drop=False).loc[qindex].reset_index(drop=True)
        del before_full
        gc.collect()
        pa.default_memory_pool().release_unused()
        result['phase'] = 'QUERY_FIXED_REBUILD'
        after_full = rebuild(new, combined)
        after = after_full.set_index(KEY, drop=False).loc[qindex].reset_index(drop=True)
        original = query.reset_index(drop=True)
        names = [c for c in query if c.startswith('f_') and c in before]
        missing_query = [c for c in query if c.startswith('f_') and c not in before]
        query_old = compare(original, before, names, 'QUERY_STORED_VS_ORIGINAL_REBUILD')
        query_fixed = compare(before, after, names, 'QUERY_OLD_VS_REPAIRED')
        original_clock = clocks(original, before)
        repaired_clock = clocks(before, after)
        result['panels'].append({'panel': 'ORIGINAL_2026_W1_W7_QUERY_FEATURE_TABLE',
            'rows': len(query), 'original_rebuild': query_old, 'repair_effect': query_fixed,
            'missing_expected_feature_columns': missing_query,
            'stored_vs_original_guard_clock': original_clock,
            'original_vs_repaired_guard_clock': repaired_clock,
            'weeks': sorted(map(int, query.week.unique()))})
        numeric_compatibility = (not missing_train and not missing_query and
            fit_original['exact_finite_and_missing_equivalence'] and
            fit_repair['exact_finite_and_missing_equivalence'] and
            query_old['exact_finite_and_missing_equivalence'] and
            query_fixed['exact_finite_and_missing_equivalence'])
        guard_parity = all(r['complete'] and r['changed_rows'] == 0 for r in
            [original_clock, repaired_clock, fit_original_clock, fit_repaired_clock])
        compatibility = numeric_compatibility and guard_parity
        result['numeric_matrix_equivalence'] = numeric_compatibility
        result['query_guard_clock_equivalence'] = guard_parity
        result['state'] = 'EXACT_RETAINED_NUMERIC_AND_QUERY_GUARD_EQUIVALENCE_PROVEN' if compatibility else 'IMPACT_MEASURED_NO_AUTOMATIC_MODEL_OR_SCORE_REUSE'
        result['historical_qualification'] = ('No numeric forecast changes implied for these exact authenticated inputs; same deterministic fitted models receive identical numeric matrices. New current-source/profile admission still required.' if compatibility else
            'Original context and/or model input matrix differs. Affected rows retained; correct origin reconstruction/refits/inference must be separately scoped. No whole-repository invalidation or score transfer.')
        if diffs:
            frame = pd.concat(diffs, ignore_index=True)
            stream = io.BytesIO()
            frame.to_parquet(stream, index=False)
            body = stream.getvalue()
            if len(body) > 1048576:
                raise ValueError('private impact evidence exceeds registered1MiB')
            dest = store.forward_root / f'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_HISTORY_IMPACT_V{attempt}.parquet'
            store.write_bytes(dest, body)
            ref = store.validate_reference(dest, sha(body))
            result['private_evidence'] = {'logical_id': 'A-AUDIT-HISTORY-IMPACT-v1',
                'sha256': ref['sha256'], 'bytes': ref['bytes'], 'rows': len(frame),
                'readback': 'PASS_OWNER_LOCAL', 'offhost_restore': 'NOT_VERIFIED'}
        store.verify_retained_checkpoint()
    except BaseException as error:
        result.update(state='FAILED_RETAINED_IMPACT_AUDIT', error_type=type(error).__name__,
            error_sha256=sha(str(error).encode()))
        result['historical_qualification'] = 'Unresolved; no inferred zero effect or automatic reuse.'
        result['failure_stack'] = [{'function': t.name, 'line': t.lineno, 'file': Path(t.filename).name}
            for t in traceback.extract_tb(error.__traceback__)[-8:]]
        if isinstance(error, MemoryError):
            result['allocation_error_detail'] = str(error)[:500] if 'allocate' in str(error).lower() else None
    result.update(completed_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        CPU_seconds=time.process_time() - cpu, wall_seconds=time.monotonic() - start,
        RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    with (OUT / ('HISTORY_IMPACT_RECEIPT_' + suffix)).open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    signal.alarm(0)
    print(json.dumps(result))
    if result['state'].startswith('FAILED'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
