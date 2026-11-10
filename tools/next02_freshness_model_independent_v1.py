"""Bounded independent check of the TWO new A aligned-48h Leaf artifacts.

Import and --synthetic-only never open native data or models. Actual execution
requires a completed, hash-bound root freeze. No fit, native put, old-model load,
peer-model load, HTTP, scoring, or publication is implemented here.
"""
from __future__ import annotations
import argparse
import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'PROFILE-INCREMENT-CLOSURE-AND-NEXT-02-A-FRESHNESS-v1'
ARMS = ['F0_ORIGINAL_BASE', 'F1_ORIGINAL_PROFILE', 'F2_48H_BASE', 'F3_48H_PROFILE']
KEY = ['season', 'week', 'game_id', 'player_id']
CTX = ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']
BASE_STATS = ('rush_att', 'rush_yd', 'rec_tgt', 'rec', 'rec_yd', 'offense_snaps')
BASE30 = ['f_player_' + stat + '_' + kind + str(win)
          for stat in BASE_STATS for win in (3, 8) for kind in ('mean', 'n')] + [
    'f_player_games_prior', 'f_player_play_rate8', 'f_player_known_participation_n8',
    'f_player_rush_ypa3', 'f_player_rec_ypt3', 'f_player_rec_catch_rate3']

def enc(x):
    return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

def sha(body):
    return hashlib.sha256(body).hexdigest()

def check(condition, message):
    if not condition:
        raise AssertionError(message)

def identity(row):
    return (int(row['season']), int(row['week']), str(row['game_id']), str(row['player_id']))

def identity_sha(row):
    return sha(enc(list(identity(row))))

def document(path, digest):
    body = Path(path).read_bytes()
    check(sha(body) == digest, 'public document hash differs: ' + Path(path).name)
    return json.loads(body)

def local(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def prior_cdf(prior, threshold):
    """Independent closed form for the signed discrete-Laplace role prior."""
    check(prior['support'] == 'signed_integer', 'wrong prior support')
    d = math.floor(threshold) - int(prior['center'])
    q = float(prior['q'])
    return q ** (-d) / (1 + q) if d < 0 else 1 - q ** (d + 1) / (1 + q)

def cdf(law, threshold):
    empirical = math.fsum(float(w) for y, w in zip(law['support'], law['weights'])
                          if float(y) <= math.floor(threshold))
    b = float(law['prior_weight'])
    return (1 - b) * empirical + b * prior_cdf(law['prior'], threshold)

def mean(law):
    b = float(law['prior_weight'])
    return (1 - b) * math.fsum(float(y) * float(w) for y, w in
                              zip(law['support'], law['weights'])) + b * law['prior']['center']

def median(law):
    lo, hi = -1, 1
    while cdf(law, lo) >= .5:
        lo *= 2
    while cdf(law, hi) < .5:
        hi *= 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if cdf(law, mid) >= .5:
            hi = mid
        else:
            lo = mid
    return hi

def tails(law, line):
    d = Decimal(str(line))
    below = int(d.to_integral_value(rounding=ROUND_CEILING)) - 1
    at = int(d.to_integral_value(rounding=ROUND_FLOOR))
    under, over = cdf(law, below), 1 - cdf(law, at)
    return under, max(0., 1 - under - over), over

def assert_law(law):
    support, weights, prior = law['support'], law['weights'], law['prior']
    check(law['kind'] == 'leaf_cdf' and len(support) == len(weights) > 0, 'law schema')
    check(all(math.isfinite(float(y)) and float(y).is_integer() for y in support), 'noninteger support')
    check(all(float(a) < float(b) for a, b in zip(support, support[1:])), 'support order/duplicates')
    check(all(math.isfinite(float(w)) and float(w) >= 0 for w in weights), 'invalid mass')
    check(math.isclose(math.fsum(weights), 1., abs_tol=1e-12), 'mass not normalized')
    check(0 <= law['prior_weight'] <= 1 and prior['support'] == 'signed_integer', 'mixture support')
    check(0 <= prior['q'] < 1 and isinstance(prior['center'], int), 'invalid role prior')

def synthetic_checks():
    law = dict(kind='leaf_cdf', support=[-3., 0., 5.], weights=[.2, .5, .3],
               prior=dict(support='signed_integer', center=1, q=.5, p=0., n=20), prior_weight=.2)
    assert_law(law)
    check(math.isclose(mean(law), .92, abs_tol=1e-14), 'fictional exact mean')
    check(median(law) == 0, 'fictional lower median')
    integer = tails(law, 0)
    half = tails(law, .5)
    check(math.isclose(integer[1], .4 + .2 / 6, abs_tol=1e-14), 'integer push boundary')
    check(abs(half[1]) < 1e-14 and math.isclose(sum(half), 1., abs_tol=1e-14), 'half-line boundary')
    bad = dict(law, weights=[.2, .5, .4])
    try:
        assert_law(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError('bad normalization must fail')
    return dict(state='PASS_FICTIONAL_MATH_FIXTURES_ONLY', NFL_observations=0,
                model_loads=0, source_reads=0, native_reads=0, fits=0)

def readonly_store(plan):
    """Attach ONLY an already created allocation; never call its constructor."""
    guard = local('nfl_lab.next02_independent_freshness_guard', 'nfl_lab/profile_freshness_a_storage_v1.py')
    allocation = document(ROOT / plan['allocation']['path'], plan['allocation']['sha256'])
    check(allocation['version'] == VERSION and allocation['state'] == 'ROOT_AND_INDEPENDENT_REVIEWED_ALLOCATION',
          'unreviewed allocation')
    obj = guard.FreshnessStore.__new__(guard.FreshnessStore)
    obj.root, obj.plan, obj.oldguard = ROOT, allocation, guard.bound_older(ROOT)
    o = obj.oldguard
    obj.h = o.helpers(ROOT)
    obj.outer, obj.prior = o.attach(ROOT)
    obj.primary = obj.prior.forward_root / 'research' / o.PRIMARY
    obj.old = obj.prior.forward_root / 'research' / o.OLD
    obj.remainder = obj.prior.forward_root / 'research' / o.VERSION
    obj.destination = obj.prior.forward_root / 'research' / VERSION
    with obj.outer.transaction():
        obj._load_older()
        path = obj.destination / 'ALLOCATION_STATE.json'
        check(path.exists(), 'freshness allocation absent; verifier cannot initialize it')
        state = o.native_json(obj.prior, path)
        check(state['version'] == VERSION and state['allocation_sha256'] == plan['allocation']['sha256'],
              'existing allocation binding differs')
        check(state['older_state_hashes'] == obj.older_state_hashes, 'older accounting changed')
        check(state['retained_bytes'] == 16 * 1024**2 and state['peak_bytes'] == 20 * 1024**2,
              'freshness caps changed')
        obj.baseline = state['baseline_prior_bytes']
        obj.fb = obj._baseline(obj.destination, state['baseline_ref'])
        check(sum(obj.fb.values()) == obj.baseline, 'native physical baseline mismatch')
        obj._admit(0)
    return obj

def select_cases(query):
    """Freeze six identities from inputs only, before reading forecast/model bytes."""
    records = query.to_dict('records')
    selected, rules = [], []
    def add(rows, rule):
        for row in rows:
            if identity(row) not in {identity(r) for r in selected}:
                selected.append(row); rules.append(rule); return
    def num(row, name):
        value = float(row.get(name, float('nan')))
        return value if math.isfinite(value) else -1.
    add(sorted(records, key=lambda r: (num(r, 'f_player_games_prior'), identity_sha(r))), 'minimum-own-history')
    add(sorted(records, key=lambda r: (-num(r, 'f_player_games_prior'), identity_sha(r))), 'maximum-own-history')
    add(sorted(records, key=lambda r: (num(r, 'f_pce_own_carries'), identity_sha(r))), 'minimum-profile-carry-support')
    add(sorted(records, key=lambda r: (-num(r, 'f_pce_own_carries'), identity_sha(r))), 'maximum-profile-carry-support')
    add(sorted(records, key=lambda r: (str(r['cutoff_utc']), identity_sha(r))), 'earliest-cutoff')
    add(sorted(records, key=lambda r: (str(r['cutoff_utc']), identity_sha(r)), reverse=True), 'latest-cutoff')
    check(len(selected) == 6, 'six distinct input-only cases required')
    return selected, [dict(identity_sha256=identity_sha(r), rule=rule)
                      for r, rule in zip(selected, rules)]

def hand_source_checks(query, store, pd, pq):
    """Three projected raw-history checks; no author feature builder is used."""
    config = ROOT / 'config/category-topfive-matched12-inference-followup-v1.json.gz'
    body = config.read_bytes()
    spec = json.loads(gzip.decompress(body))
    frames, source_refs = [], []
    for ref in spec['history_sources']:
        if 'path' in ref:
            path = Path(ref['path'])
        else:
            part = Path(ref['relative_path'])
            check(not part.is_absolute() and '..' not in part.parts, 'invalid approved source member')
            path = store.prior.forward_root / part
            store.prior.validate_reference(path, ref['sha256'])
        raw = path.read_bytes()
        check(len(raw) == ref['bytes'] and sha(raw) == ref['sha256'], 'raw history source hash')
        schema = pq.ParquetFile(io.BytesIO(raw)).schema_arrow.names
        want = KEY + ['kickoff_utc', 'outcome_available_utc', 'availability_clock_kind',
                      'participation_state'] + list(BASE_STATS)
        frames.append(pd.read_parquet(io.BytesIO(raw), columns=[n for n in want if n in schema]))
        source_refs.append({k: ref[k] for k in ('bytes', 'sha256')})
    history = pd.concat(frames, ignore_index=True)
    for stat in BASE_STATS:
        if stat not in history:
            # Absence remains unavailable, as in the declared feature contract.
            history[stat] = float('nan')
    check(not history.duplicated(['game_id', 'player_id']).any(), 'raw-history identity overlap')
    check((history.season.lt(2026) | history.season.eq(2026) & history.week.le(6)).all(), 'raw history horizon')
    original = pd.to_datetime(history.outcome_available_utc, utc=True)
    game = pd.to_datetime(history.kickoff_utc, utc=True)
    kind = history.availability_clock_kind.fillna('UNKNOWN').astype(str) if 'availability_clock_kind' in history else pd.Series('RECONSTRUCTED_KICKOFF_PLUS_7_DAYS', index=history.index)
    allowed = {'RECONSTRUCTED_KICKOFF_PLUS_7_DAYS', 'AUTHENTICATED_ORIGINAL_OBSERVATION',
               'AUTHENTICATED_CORRECTION_OBSERVATION', 'UNVERIFIED_VERSION_CLOCK', 'UNKNOWN'}
    check(kind.isin(allowed).all(), 'unmapped raw clock kind')
    proxy = original.notna() & original.eq(game + pd.Timedelta(days=7)) & kind.eq('RECONSTRUCTED_KICKOFF_PLUS_7_DAYS')
    history['_available'] = original.where(~proxy, game + pd.Timedelta(hours=48))
    history['_kickoff'] = game
    chosen, _ = select_cases(query)
    # No outcome or comparative result determines these three input cases.
    examples = [chosen[0], chosen[1], chosen[-1]]
    result = []
    for row in examples:
        cut = pd.Timestamp(row['cutoff_utc'])
        target_games = set(query.loc[query.cutoff_utc.eq(cut), 'game_id'].astype(str))
        prior = history.loc[history.player_id.astype(str).eq(str(row['player_id'])) &
                            history._available.notna() & history._available.lt(cut) &
                            history._kickoff.lt(cut) & ~history.game_id.astype(str).isin(target_games)].copy()
        prior = prior.sort_values(['_kickoff', 'game_id', 'player_id'], kind='stable')
        check(float(row['f_player_games_prior']) == len(prior), 'hand-count own-history admission')
        checked = 1
        for stat in BASE_STATS:
            for win in (3, 8):
                vals = pd.to_numeric(prior.tail(win)[stat], errors='coerce').to_numpy(float)
                finite = [float(v) for v in vals if math.isfinite(float(v))]
                expected_mean = math.fsum(finite) / len(finite) if finite else float('nan')
                actual = float(row['f_player_' + stat + '_mean' + str(win)])
                check((math.isnan(actual) and math.isnan(expected_mean)) or math.isclose(actual, expected_mean, abs_tol=1e-9), 'hand-filter source mean')
                check(float(row['f_player_' + stat + '_n' + str(win)]) == len(finite), 'hand-filter source support')
                checked += 2
        check(math.isnan(float(row['f_player_play_rate8'])), 'undefined appearance denominator must stay unavailable')
        result.append(dict(identity_sha256=identity_sha(row), fields_checked=checked,
                           admitted_prior_games=len(prior), latest_prior_game_UTC=None if prior.empty else prior._kickoff.max().isoformat(),
                           latest_reconstructed_available_UTC=None if prior.empty else prior._available.max().isoformat()))
    return dict(state='PASS_THREE_INDEPENDENT_RAW_OWN_PLAYER_BASE_EXAMPLES', examples=result,
                source_configuration_sha256=sha(body), source_refs=source_refs,
                policy='RECONSTRUCTED_48H_SENSITIVITY_NOT_AUTHENTICATED_OBSERVATION',
                excludes=['No full PBP/context profile reconstruction', 'No target outcomes or offered-line scoring'])

def run(args):
    check(args.root_notified_complete == 'ROOT_NOTIFIED_TWO_ALIGNED_48H_MODELS_COMPLETE', 'completed root freeze GO required')
    started, cpu = time.monotonic(), time.process_time()
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    resource.setrlimit(resource.RLIMIT_CPU, (190, 200))
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3,) * 2)
    def exhausted(signum, _frame):
        if signum == signal.SIGXCPU:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise TimeoutError('independent freshness allowance 200CPU/600wall/3GiB')
    signal.signal(signal.SIGXCPU, exhausted); signal.signal(signal.SIGALRM, exhausted); signal.alarm(590)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    def no_network(event, _args):
        if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'}:
            raise RuntimeError('zero-network independent artifact verification')
    sys.addaudithook(no_network)
    plan = document(args.protocol, args.protocol_sha256)
    go = document(args.root_go, args.root_go_sha256)
    receipt = document(args.receipt, args.receipt_sha256)
    prior_review = document(args.previous_model_review, args.previous_model_review_sha256)
    check(go['state'] == 'ROOT_AND_INDEPENDENT_GO' and go['protocol_sha256'] == args.protocol_sha256, 'root published fit gate differs')
    check(plan['version'] == VERSION and plan['maximum_new_fits'] == 2 and plan['arms'] == ARMS, 'exact two-arm plan differs')
    check(receipt['state'] == 'FROZEN_TWO_NEW_ALIGNED_TIMING_ARMS_AND_TWO_SAVED_BASELINES_UNSCORED', 'incomplete model freeze')
    check(receipt['fits_attempted'] == receipt['fits_returned'] == receipt['new_fits'] == 2, 'two completed new fits required')
    check(receipt['original_refits'] == receipt['old_model_loads'] == receipt['old_model_inference'] == 0, 'old model rerun forbidden')
    check(receipt['query_rows'] == 1364 and receipt['forecast_rows'] == 5456 and receipt['intended_rows'] == 1366, 'fixed universe differs')
    check(prior_review['state'] == 'PASS_NAMED_THREE_ARM_FREEZE_DEFENSE_UNAVAILABLE_PENDING' and
          prior_review['activity']['fits'] == 0, 'prior accepted verification identity')
    for path, digest in {**plan['code_sha256'], **plan['source_configuration_sha256']}.items():
        check(sha((ROOT / path).read_bytes()) == digest, 'executing source/config changed: ' + path)
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import joblib
    from threadpoolctl import threadpool_limits
    pa.set_cpu_count(1); pa.set_io_thread_count(1); pa.set_memory_pool(pa.system_memory_pool())
    from nfl_lab import cdf_engine as engine
    increment = local('nfl_lab.next02_independent_profile_names', 'nfl_lab/profile_increment_a_v2.py')
    store = readonly_store(plan)
    def read(ref):
        return store.read_many([ref])[ref['id']]
    prepared = json.loads(read(receipt['prepared_binding']))
    old_parity = json.loads(read(receipt['original_input_parity']))
    check(old_parity['state'] == 'PASS_ORIGINAL_BASE_AND_QUERY_PROFILE_PARITY', 'old numerical input parity not complete')
    check(prepared['query_rows'] == 1364 and prepared['withheld_source_games'] == 14, 'source membership changed')
    train = pd.read_parquet(io.BytesIO(read(prepared['training'])))
    query = pd.read_parquet(io.BytesIO(read(prepared['query'])))
    for frame in (train, query):
        for name in ('kickoff_utc', 'cutoff_utc', 'outcome_available_utc', 'feature_max_source_available_utc'):
            frame[name] = pd.to_datetime(frame[name], utc=True)
        check(not frame.duplicated(KEY).any() and frame.position.eq('RB').all(), 'identity/role duplicate')
        clock = frame.feature_max_source_available_utc
        check((clock.isna() | clock.lt(frame.cutoff_utc)).all(), 'nonprior transform guard')
    check(len(train) == 14644 and len(query) == 1364 and train.season.lt(2026).all(), 'training/query size or year')
    check(train.outcome_available_utc.notna().all() and train.outcome_available_utc.lt(pd.Timestamp('2026-09-01', tz='UTC')).all(), 'training label cutoff')
    check(query.outcome_available_utc.isna().all() and query.participation_state.eq('unknown').all(), 'future query outcome availability')
    check(not set(('actual', 'rush_yd', 'rush_att', 'point', 'prediction')) & set(query), 'query contains target output')
    profile = list(increment.SUPPORT + increment.PLAYER_OFFENSE)
    check(len(BASE30) == 30 and len(profile) == 98, 'feature count contract')
    sample_rows, selection_receipt = select_cases(query)
    sample = pd.DataFrame(sample_rows).reset_index(drop=True)
    # This input selection is fixed before the first forecast law/model is read.
    case_commitment = sha(enc(selection_receipt))
    source_receipt = hand_source_checks(query, store, pd, pq) if args.raw_source_examples else dict(state='UNKNOWN_NOT_REQUESTED', scope='Independent raw-source examples not executed')
    manifest = json.loads(gzip.decompress(read(receipt['forecasts'])))
    check(manifest['format'] == 'IMMUTABLE_ALIAS_PART_MANIFEST_V1' and manifest['arm_order'] == ARMS, 'manifest type/order')
    check(manifest['rows'] == 5456 and len(manifest['parts']) == 4, 'manifest rows/parts')
    retained = {r['id']: r for r in plan['retained_refs']}
    for i, saved in enumerate(('F0_forecasts', 'F1_forecasts')):
        part = manifest['parts'][i]
        check(part['ref'] == retained[plan['saved_ids'][saved]] and part['reuse'] == 'EXACT_RETAINED_OUTPUT_NO_NEW_INFERENCE', 'old forecast byte binding changed')
    y = pd.to_numeric(train.rush_yd, errors='coerce').to_numpy(float)
    good = train.participation_state.eq('played').to_numpy() & np.isfinite(y) & (y == np.floor(y))
    modeled = train.loc[good].copy()
    check(len(modeled) == 10527, 'modeled training label count')
    results = {}
    for arm, part in zip(ARMS[2:], manifest['parts'][2:]):
        check(part['procedure_alias'] == arm and part['rows'] == 1364, 'new forecast arm')
        rows = json.loads(gzip.decompress(read(part['ref'])))
        saved = {identity(r): r for r in rows}
        check(len(rows) == len(saved) == 1364 and set(saved) == set(map(identity, query.to_dict('records'))), 'forecast/query identities')
        max_mean_error = 0.
        for row in rows:
            check(row['arm'] == arm and row['target'] == 'rush_yd' and row['original_issued_UTC'] is None, 'forecast typed provenance')
            check(row['conditioning'] == 'CONDITIONAL_ON_PLAYED' and row['reconstruction'] == 'KICKOFF_PLUS_48H_RECONSTRUCTED_SENSITIVITY', 'forecast conditioning/timing')
            law = row['law']; assert_law(law)
            difference = abs(mean(law) - row['mean']); max_mean_error = max(max_mean_error, difference)
            check(math.isclose(mean(law), row['mean'], rel_tol=1e-12, abs_tol=1e-10), 'independent law mean')
            check(cdf(law, row['median']) >= .5 - 1e-12 and cdf(law, row['median'] - 1) < .5 + 1e-12, 'lower median boundary')
            check(pd.Timestamp(row['source_information_max_UTC']) < pd.Timestamp(row['cutoff_utc']), 'forecast guard cutoff')
        model = joblib.load(io.BytesIO(read(receipt['models'][arm])))
        check(isinstance(model, engine.LeafCDFModel), 'owned expected model class')
        names = BASE30 + (profile if arm == ARMS[3] else [])
        check(model.design.names == names == model.category['panels']['base'] == model.category['panels']['context'], 'model training feature order')
        check(model.category['modeled_roles'] == model.design.roles == ['RB'], 'model role contract')
        check(len(model.forest.estimators_) == 32 and model.forest.n_features_in_ == len(names) * 2 + 1, 'fixed learner geometry')
        check(model.audit['training_rows'] == 14644 and model.audit['supported_played_training_rows'] == model.audit['modeled_training_rows'] == 10527, 'model fit audit population')
        binding = model.training_binding.reset_index(drop=True)
        for name in binding:
            expected = modeled[name].reset_index(drop=True)
            left = binding[name]
            if name.endswith('_utc'):
                left, expected = pd.to_datetime(left, utc=True), pd.to_datetime(expected, utc=True)
            check(((left == expected) | (left.isna() & expected.isna())).all(), 'model training identity/label order: ' + name)
        check(set(model.priors) == {'RB'} and vars(model.priors['RB']) == vars(model.global_prior), 'role prior population')
        independent_design = []
        for name, retained_median in zip(names, model.design.medians):
            values = pd.to_numeric(modeled[name], errors='coerce').to_numpy(float)
            finite = values[np.isfinite(values)]
            expected_median = float(np.median(finite)) if len(finite) else 0.
            check(retained_median == expected_median, 'imputation fitted on wrong population')
            vals = pd.to_numeric(sample[name], errors='coerce').to_numpy(float)
            missing = ~np.isfinite(vals)
            independent_design.extend([np.where(missing, retained_median, vals), missing.astype(float)])
        independent_design.append(np.ones(len(sample)))
        design = np.column_stack(independent_design).astype(np.float32)
        np.testing.assert_array_equal(design, model.design.transform(sample))
        def predict(frame, obj=model, batch_size=None):
            result = {}
            for indices, law, reasons in obj.predict_batches(frame, batch_size=batch_size or len(frame)):
                for j, position in enumerate(indices):
                    result[identity(frame.iloc[int(position)].to_dict())] = (
                        dict(kind='leaf_cdf', support=law.support.tolist(), weights=law.weights[j].tolist(),
                             prior=vars(law.prior), prior_weight=law.b), str(reasons[j]) or None)
            return result
        with threadpool_limits(limits=1):
            batch = predict(sample)
            single = {k: v for i in range(len(sample)) for k, v in
                      predict(sample.iloc[[i]].reset_index(drop=True)).items()}
            shuffled = predict(sample.iloc[::-1].reset_index(drop=True))
            columns = predict(sample[list(reversed(sample.columns))])
            poisoned = predict(sample.assign(actual=999999, rush_yd=-999999, rush_att=999999,
                                              participation_state='DNP', outcome_available_utc=pd.Timestamp('2099-01-01', tz='UTC')))
            restored_stream = io.BytesIO(); joblib.dump(model, restored_stream, compress=('xz', 3))
            restored = joblib.load(io.BytesIO(restored_stream.getvalue()))
            roundtrip = predict(sample, obj=restored)
            leaves = model.forest.apply(design)
        tailchecks = 0
        for i, row in enumerate(sample_rows):
            k = identity(row); law, reason = batch[k]
            for other in (single[k], shuffled[k], columns[k], poisoned[k], roundtrip[k]):
                check(enc(other) == enc(batch[k]), 'inference identity/batch/order/target poison/restore mismatch')
            check(enc(law) == enc(saved[k]['law']) and reason == saved[k]['fallback'], 'saved/restored inference mismatch')
            check(median(law) == saved[k]['median'], 'independent exact lower median')
            if not reason:
                weights = np.zeros(len(model.support))
                for j, histogram in enumerate(model.leaf_histograms):
                    weights += histogram[leaves[i, j]].toarray()[0]
                weights /= len(model.leaf_histograms)
                np.testing.assert_allclose(weights, law['weights'], rtol=0, atol=1e-12)
            native = engine.MixtureBatch(law['support'], [law['weights']], engine.SupportPrior(**law['prior']), prior_weight=law['prior_weight'])
            previous_over = 1.
            for line in (-100., -1., 0., .5, 10., 10.5, 100.25, 10000.):
                under, push, over = tails(law, line)
                check(min(under, push, over) >= -1e-12 and math.isclose(under + push + over, 1., abs_tol=1e-12), 'event law normalization')
                check(over <= previous_over + 1e-12, 'threshold monotonicity'); previous_over = over
                check(math.isclose(under, float(native.cdf(math.ceil(line) - 1)[0]), abs_tol=1e-12), 'Under event tail')
                check(math.isclose(over, 1 - float(native.cdf(math.floor(line))[0]), abs_tol=1e-12), 'Over event tail')
                if not float(line).is_integer():
                    check(abs(push) < 1e-12, 'noninteger signed-integer push')
                tailchecks += 1
        fallback_checks = []
        for label, altered, expected in (
                ('missing-history-field', sample.drop(columns='f_player_games_prior'), 'cold_start_role_prior'),
                ('zero-history', sample.assign(f_player_games_prior=0.), 'cold_start_role_prior'),
                ('unknown-role', sample.assign(position='UNSEEN_ROLE'), 'global_prior_unknown_role')):
            output = predict(altered)
            check(all(reason == expected and law['prior_weight'] == 1. for law, reason in output.values()), 'fallback contract: ' + label)
            fallback_checks.append(dict(fixture=label, cases=len(output), reason=expected))
        missing = sample.drop(columns=names[0]); nonfinite = sample.assign(**{names[0]: float('inf')})
        absent_predictions, nonfinite_predictions = predict(missing), predict(nonfinite)
        check(set(absent_predictions) == set(nonfinite_predictions) and
              all(enc(absent_predictions[k]) == enc(nonfinite_predictions[k]) for k in absent_predictions),
              'absent/nonfinite feature imputation')
        used = {names[int(f) // 2] for tree in model.forest.estimators_ for f in tree.tree_.feature if 0 <= f < 2 * len(names)}
        results[arm] = dict(laws_checked=len(rows), case_checks=6, case_commitment_sha256=case_commitment,
                           maximum_independent_mean_difference=max_mean_error, tail_boundary_checks=tailchecks,
                           fallback_fixtures=fallback_checks, input_design_fields=len(names),
                           recorded_split_fields=dict(base=len(used & set(BASE30)), profile=len(used & set(profile))),
                           input_medians_and_training_binding='EXACT_SAVED_ALIGNED_TRAINING_POPULATION_AND_ORDER',
                           model_sha256=receipt['models'][arm]['sha256'], forecast_sha256=part['ref']['sha256'])
        del model, restored
    result = dict(id=VERSION + '::INDEPENDENT_TWO_MODEL_VERIFICATION-v1',
                  state='PASS_ONLY_NEW_F2_F3_MODEL_AND_INFERENCE_WITH_PRIOR_BASELINE_EVIDENCE_REUSED',
                  UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), protocol_sha256=args.protocol_sha256,
                  root_go_sha256=args.root_go_sha256, receipt_sha256=args.receipt_sha256,
                  code_sha256=sha(Path(__file__).read_bytes()), reused_prior_review_sha256=args.previous_model_review_sha256,
                  selection=selection_receipt, selection_before_model_and_law_access=True, results=results,
                  independent_raw_source_examples=source_receipt, native_accounting=store.checkpoint(),
                  environment=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__,
                                   pyarrow=pa.__version__, joblib=joblib.__version__),
                  limitations=['No new fit or fresh-fit reproduction; two trusted owned saved models only.',
                               'F0/F1 old models not loaded or inferred; accepted receipt and retained law bindings reused.',
                               'Seven-day versus 48h is reconstructed timing sensitivity, not authenticated historical source availability.',
                               'No full PBP/profile re-audit; prior scoped source-future fixture receipts remain separate.',
                               'No offered-line grading, new NFL observations, current capture, probability calibration or deployment claim.'],
                  activity=dict(fits=0, model_artifacts_loaded=2, in_memory_roundtrips=2, old_model_loads=0,
                                private_writes=0, source_HTTP=0, CPU_seconds=time.process_time() - cpu,
                                wall_seconds=time.monotonic() - started,
                                RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024))
    with args.output.open('xb') as handle:
        handle.write(enc(result))
    signal.alarm(0)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--synthetic-only', action='store_true')
    parser.add_argument('--raw-source-examples', action='store_true')
    parser.add_argument('--root-notified-complete')
    for name in ('protocol', 'root-go', 'receipt', 'previous-model-review', 'output'):
        parser.add_argument('--' + name, type=Path)
    for name in ('protocol-sha256', 'root-go-sha256', 'receipt-sha256', 'previous-model-review-sha256'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if args.synthetic_only:
        print(json.dumps(synthetic_checks(), sort_keys=True))
    else:
        required = ('root_notified_complete', 'protocol', 'protocol_sha256', 'root_go', 'root_go_sha256',
                    'receipt', 'receipt_sha256', 'previous_model_review', 'previous_model_review_sha256', 'output')
        check(all(getattr(args, name) for name in required), 'all exact freeze/hash arguments are required')
        try:
            run(args)
        except BaseException as error:
            signal.alarm(0)
            failure = dict(state='FAILED_INDEPENDENT_NEW_F2_F3_NO_REFIT', error_type=type(error).__name__,
                           error_sha256=sha(str(error).encode()), receipt_sha256=args.receipt_sha256,
                           code_sha256=sha(Path(__file__).read_bytes()), fits=0, private_writes=0)
            with args.output.with_name(args.output.stem + '-failure.json').open('xb') as handle:
                handle.write(enc(failure))
            raise
