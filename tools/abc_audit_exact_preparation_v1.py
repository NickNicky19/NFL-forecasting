"""Replay the bound historical feature-preparation recipe with repaired inputs.

Model-free, source-only: no new forecast or grade. Preserves all source roster
states and the original per-week preparation, rather than an invented context.
"""
from pathlib import Path
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/audit-remediation-20261105'
KEY = ['season', 'week', 'game_id', 'player_id']


def load(name, path, sha):
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError('pinned source helper changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    started, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (2147483648, 2147483648))
    resource.setrlimit(resource.RLIMIT_CPU, (350, 360))
    signal.alarm(475)
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import nfl_lab
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    pa.set_memory_pool(pa.system_memory_pool())
    raw = (OUT / 'HISTORY_IMPACT_RECEIPT_V6.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != '8dfc96149eac5900b3e7cdfb3df30b857483c293a2c6f7c48468cadf0612b0ed':
        raise ValueError('completed training input proof changed')
    previous = json.loads(raw)
    training = previous['panels'][0]
    for k in ['original_rebuild', 'repair_effect', 'fit_scope_original_rebuild', 'fit_scope_repair_effect']:
        if not training[k]['exact_finite_and_missing_equivalence'] or training[k]['columns'] != 97:
            raise ValueError('training input compatibility not proven')
    for k in ['fit_stored_vs_original_guard_clock', 'fit_original_vs_repaired_guard_clock']:
        if not training[k]['complete'] or training[k]['changed_rows']:
            raise ValueError('training guard compatibility not proven')
    fixed = load('audit_exact_fixed_features', ROOT.parent / 'nfl-audit-remediation-a/nfl_lab/features.py',
        'c3dcc6f3dd3cf019b358ffc86434e2659351c0aeb60c00256ab23be2039a4ade')
    prep = load('audit_exact_original_preparation', ROOT / 'tools/category_topfive_matched12_prepare_v1.py',
        'c199bf566405f0fdb19b2b84c65f31bac931d3df2af8c5e6fad252b4bd3d40ef')
    plan = json.loads(gzip.decompress((ROOT / 'config/category-topfive-matched12-inference-followup-v1.json.gz').read_bytes()))
    if plan['features']['sha256'] != previous['query_input']['sha256']:
        raise ValueError('original query binding differs')
    if [{k: r[k] for k in ['sha256', 'bytes']} for r in plan['history_sources']] != previous['history_sources']:
        raise ValueError('historical source version list differs from training/query proof')
    store, _ = open_store(ROOT, allocation_sha256=
        'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO)

    def owned(ref):
        path = Path(ref['path'])
        owners = [s for s in (store, store.complete_peer, store.complete_peer.prior_forward, store.complete_peer.legacy)
            if any(path.is_relative_to(r) for r in s._roots)]
        if len(owners) != 1 or owners[0].validate_reference(path, ref['sha256'])['bytes'] != ref['bytes']:
            raise ValueError('source owner/hash/size differs')
        return path.read_bytes()

    query = pd.read_parquet(io.BytesIO(owned(plan['features'])))
    saved_cutoff = pd.to_datetime(query.cutoff_utc, utc=True)
    saved_kickoff = pd.to_datetime(query.kickoff_utc, utc=True)
    if saved_cutoff.isna().any() or saved_kickoff.isna().any() or saved_cutoff.gt(saved_kickoff).any():
        raise ValueError('retained query cutoff contract differs')
    parts = [pd.read_parquet(io.BytesIO(owned(r))) for r in plan['history_sources']]
    # Exact registered preparation has no ACT/INA source filter. Unknown past
    # games may consume a slot; target queries remain unknown and never labels.
    metadata = [c for c in query if not c.startswith('f_') and not c.startswith('feature_')
        and c != 'participation_probability_state']
    packet = {'version': prep.VERSION, 'evidence_kind': prep.EVIDENCE, 'queries': query[metadata].copy()}
    authority = {'integrator': '/root', 'numeric_preparation_authorized': True, 'adapter_version': prep.VERSION}

    def clock_guard(frame):
        cutoff = pd.to_datetime(frame.cutoff_utc, utc=True)
        source = pd.to_datetime(frame.feature_max_source_available_utc, utc=True)
        if frame.duplicated(KEY).any() or not frame.participation_state.eq('unknown').all():
            raise ValueError('historical query identity or target participation changed')
        if (source.notna() & source.ge(cutoff)).any():
            raise ValueError('historical source is not earlier than query')

    rebuilt = prep.historical_features(parts, packet, features_module=fixed,
        assert_clock_contract=clock_guard, authority=authority)
    actual = rebuilt['features']
    if not query[KEY].reset_index(drop=True).equals(actual[KEY].reset_index(drop=True)):
        raise ValueError('full original query identities/order differ')
    columns = [c for c in query if c.startswith('f_')]
    if len(columns) != 97 or set(columns) - set(actual):
        raise ValueError('full model feature matrix incomplete')
    changed = np.zeros(len(query), bool)
    details = []
    for col in columns:
        a = pd.to_numeric(query[col], errors='raise').to_numpy(float)
        b = pd.to_numeric(actual[col], errors='raise').to_numpy(float)
        same = (a == b) | (np.isnan(a) & np.isnan(b))
        changed |= ~same
        if (~same).any():
            details.append({'feature': col, 'changed_rows': int((~same).sum())})
    guards = {}
    for col in ['feature_max_source_available_utc', 'feature_max_assumed_history_available_utc']:
        if col not in query or col not in actual:
            raise ValueError('complete retained query guard components required')
        a = pd.to_datetime(query[col], utc=True)
        b = pd.to_datetime(actual[col], utc=True)
        guards[col] = int((~(a.eq(b) | (a.isna() & b.isna()))).sum())
    equivalent = not changed.any() and not any(guards.values())
    result = {'id': 'A-AUDIT-EXACT-HISTORICAL-PREPARATION-v1', 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'EXACT_RETAINED_TRAINING_QUERY_AND_GUARD_EQUIVALENCE' if equivalent else 'EXACT_RECIPE_INPUT_DIFFERENCES_REQUIRE_SCOPED_INFERENCE',
        'source_helper_sha256': 'c199bf566405f0fdb19b2b84c65f31bac931d3df2af8c5e6fad252b4bd3d40ef',
        'repaired_feature_sha256': previous['new_feature_sha256'],
        'retained_query_sha256': plan['features']['sha256'],
        'training_proof_sha256': hashlib.sha256(raw).hexdigest(),
        'query_rows': len(query), 'model_feature_columns': len(columns),
        'changed_rows': int(changed.sum()), 'changed_columns': details, 'guard_changed_rows': guards,
        'actual_weeks': rebuilt['coverage'],
        'by_week': [{'week': int(w), 'query_rows': len(ix), 'changed_rows': int(changed[np.asarray(ix)].sum())}
            for w, ix in query.groupby('week').indices.items()],
        'source_context_correction': 'Use registered full prior raw roster states and per-week target placeholders; previous ACT/INA and all-week query contexts were harness differences, not established saved-forecast contamination.',
        'limits': ['Input equivalence only for these exact retained sources, recipe,97fields and guards.',
            'Declared seven-day reconstruction preserved; no authenticated observation vintage or freshness gain claimed.',
            'Not native Root admission, current-query capture, new football scores or original-site consumer verification.'],
        'model_loads_fits_predict_calls_new_grades': 0,
        'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - started}
    if not equivalent:
        stream = io.BytesIO()
        actual.to_parquet(stream, index=False)
        body = stream.getvalue()
        if len(body) > 524288:
            raise ValueError('bounded corrected-query retention exceeded')
        path = store.forward_root / 'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_EXACT_RECIPE_QUERY_MATRIX_V1.parquet'
        store.write_bytes(path, body)
        ref = store.validate_reference(path, hashlib.sha256(body).hexdigest())
        result['private_evidence'] = {k: ref[k] for k in ['bytes', 'sha256']}
        result['private_evidence']['readback'] = 'PASS_OWNER_LOCAL_OFFHOST_UNVERIFIED'
    store.verify_retained_checkpoint()
    with (OUT / 'EXACT_PREPARATION_RECEIPT_V1.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'actual_weeks'}))
    signal.alarm(0)


if __name__ == '__main__':
    main()
