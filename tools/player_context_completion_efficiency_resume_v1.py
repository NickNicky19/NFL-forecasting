"""Resume frozen conditional-efficiency inference after the clock serializer error.

No fit, tuning, label grading, source acquisition or original issuance. All five
returned states and the first failure remain immutable. Only S0/S1 rows are new.
Execution requires root's published exact plan and explicit external GO receipt.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/player-context-completion-decision-01'
sys.path.insert(0, str(ROOT))
VERSION = 'A-efficiency-inference-resume-v1'
PARENT = 'PLAYER-CONTEXT-COMPLETION-DECISION-01-A-efficiency-v1'
ERROR_SHA = '11c62d927031b2a38fcafb876fbd44802ff1685968df1d26e35ca5332e5090ca'
PARTIAL_SHA = '0a61804b2d938695cea098867433db19f2aa35738a28e1a8fa05706d686fb713'
COMPLETE_MODEL_SHA = '96a944fefa621d138a0277a8cd0f481cce5052315936a50b88c321068aa7d2b7'
MODEL_PINS = {
    'MODEL_2025_D0_UNCHANGED_HGB_MAE.joblib': '1f89ea4c7256e408978b1a1320681e9c44b691d31207acd24f92b975a572ddde',
    'MODEL_2025_D1_HGB_RAW_CONDITIONAL_PROFILE.joblib': '663a0b56429569b464b24799782c4bd942ba927f4895e1f6d8ead0ff261d2bc5',
    'MODEL_2026_D1_HGB_RAW_CONDITIONAL_PROFILE.joblib': '5872def1b9dfcc216e2fdcc93a43f8b3eb4b70bb308c09f59fdb95dee14cc26d',
    'MODEL_S1_YARDS_RETURNED.joblib': '0da5d57cd2145917d5e57a462be5031090a6ab49aebcc6114559ac31a86679b6',
    'MODEL_S1_COMPLETE_RETURNED.joblib': COMPLETE_MODEL_SHA,
}
KEY = ['season', 'week', 'game_id', 'player_id']
CTX = ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']
ARMS = ['S1_CONDITIONAL_EFFICIENCY_FIXED_N', 'S0_UNCONDITIONAL_OWN_YPC_FIXED_N']
STATE = {'phase': 'NOT_STARTED', 'artifacts': [], 'rows': [], 'diagnostics': []}


def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def check(value, message):
    if not value:
        raise ValueError(message)


def pin(ref):
    body = Path(ref['path']).read_bytes()
    check(len(body) == ref['bytes'] and sha(body) == ref['sha256'], 'exact local metadata binding differs')
    return body


def authorize(args):
    planraw = args.plan.read_bytes()
    check(sha(planraw) == args.plan_sha256, 'root recovery protocol changed')
    goraw = args.go.read_bytes()
    check(sha(goraw) == args.go_sha256, 'root recovery GO changed')
    plan, go = json.loads(planraw), json.loads(goraw)
    check(plan['version'] == VERSION and plan['assignment_id'] == 'PLAYER-CONTEXT-COMPLETION-DECISION-01', 'wrong recovery scope')
    check(plan['new_fits'] == 0 and plan['new_scoring'] == 0 and plan['new_source_HTTP'] == 0, 'inference-only recovery required')
    check(go.get('state') == 'ROOT_AND_INDEPENDENT_GO' and go.get('registered_by') == '/root'
          and go.get('protocol_sha256') == args.plan_sha256, 'explicit exact root recovery GO required')
    publication = json.loads(pin(go['publication_ref']))
    check(publication['state'] == 'PUBLICATION_COMPLETE', 'published recovery readback required')
    own = str(Path(__file__).resolve().relative_to(ROOT))
    check(own in plan['code_sha256'], 'executing recovery code must be bound')
    for p, digest in plan['code_sha256'].items():
        check(sha((ROOT / p).read_bytes()) == digest, 'registered recovery code differs')
    for p, digest in plan['source_configuration_sha256'].items():
        check(sha((ROOT / p).read_bytes()) == digest, 'original source configuration differs')
    r = plan['resources']
    check(100 < r['CPU_seconds'] <= 1100 and 60 < r['wall_seconds'] <= 1800
          and r['RSS_bytes'] == 3 * 1024**3 and r['failure_reserve_bytes'] == 1024**2,
          'exact finite recovery envelope required')
    return plan, planraw


def latest_aware(values, pd):
    """Parse each supplied clock separately, never infer/fill an unknown clock."""
    result = []
    for value in values:
        if value is None:
            continue
        stamp = pd.Timestamp(value)
        if pd.isna(stamp):
            continue
        check(stamp.tzinfo is not None, 'source clock must be timezone-aware')
        result.append(stamp.tz_convert('UTC'))
    return max(result) if result else None


def run(plan, planraw, plan_sha):
    start, cpu = time.monotonic(), time.process_time()
    started = now()
    from tools import player_context_completion_efficiency_v1 as engine
    np, pd = engine.runtime(plan['resources']['CPU_seconds'], plan['resources']['wall_seconds'])
    import joblib
    from threadpoolctl import threadpool_limits
    from nfl_lab import cdf_engine as cdf, player_context_rush_efficiency_v1 as core
    from nfl_lab import player_context_completion_storage_v1 as guard
    failure_raw = pin(plan['failure_receipt'])
    failure = json.loads(failure_raw)
    check(failure['state'] == 'FAILED_RETAINED_NO_AUTOMATIC_REFIT' and failure['version'] == PARENT
          and failure['fits_attempted'] == failure['fits_returned'] == 5
          and failure['error_type'] == 'ValueError' and failure['error_sha256'] == ERROR_SHA,
          'only the exact retained five-fit clock failure can resume')
    oldrefs = {r['id']: r for r in failure['artifacts']}
    check(len(oldrefs) == len(failure['artifacts']), 'duplicate original artifact IDs')
    check(oldrefs['FORECAST_PARTIALS_FAILURE.json.gz']['sha256'] == PARTIAL_SHA
          and oldrefs['MODEL_S1_COMPLETE_RETURNED.joblib']['sha256'] == COMPLETE_MODEL_SHA,
          'original retained output/model identities changed')
    check(all(oldrefs.get(name, {}).get('sha256') == digest for name, digest in MODEL_PINS.items()),
          'all five exact returned optimizer states must remain bound before inference')
    store = guard.CompletionStore(ROOT, Path(plan['allocation']['path']), plan['allocation']['sha256'], root_go=guard.GO)
    STATE.update(store=store, phase='RETAINED_MODEL_AND_SOURCE_ADMISSION')

    def read_old(name):
        ref = oldrefs[name]
        body = store.read(name, ref['sha256'])
        check(len(body) == ref['bytes'], 'retained original artifact size differs')
        return body

    def put(name, body, failure_body=False):
        if not failure_body:
            store.reserve(len(body) + plan['resources']['failure_reserve_bytes'])
        ref = store.put(name, body)
        STATE['artifacts'].append(ref)
        return ref

    try:
        # A tiny immutable control, before any model decode and with no fits,
        # does not require a model/failure pre-reservation. Native put still
        # enforces every original fresh admission, write and checksum guard.
        # The exact recovery plan is publicly bound; the original private plan
        # remains retained. Large outputs keep their full 1MiB reserve below.
        with store.outer.transaction():
            check(not (store.destination/'RECOVERY_CONSUMED_V1.json').exists(),
                  'recovery already consumed; no automatic inference retry')
            consumed = store.put('RECOVERY_CONSUMED_V1.json', enc(dict(version=VERSION, UTC=started,
                protocol_sha256=plan_sha, parent_failure_sha256=sha(failure_raw), new_fits=0,
                state='INFERENCE_RECOVERY_CONSUMED_BEFORE_MODEL_DECODE')))
            STATE['artifacts'].append(consumed)
        original_plan_raw = read_old('PRIVATE_EXECUTION_PLAN.json')
        original_plan = json.loads(original_plan_raw)
        check(sha(original_plan_raw) == '71e3122782231f69bfaf039a859acddec127055c9bf88eb239c2822449b14fcb',
              'exact original recipe must be reused')
        for p, digest in original_plan['code_sha256'].items():
            check(sha((ROOT / p).read_bytes()) == digest, 'original executing recipe changed')
        oldrows = json.loads(gzip.decompress(read_old('FORECAST_PARTIALS_FAILURE.json.gz')))
        check(all(r['arm'] not in ARMS for r in oldrows), 'completed original structured rows must be reused separately')
        check(all(r['target'] == 'rush_yd' and r['position'] == 'RB' for r in oldrows), 'original output target/role changed')
        admission = json.loads(read_old('SOURCE_ADMISSION.json'))
        data = engine.load_inputs(pd)
        ctx = core.EfficiencyContext(data['frames'], data['history'])
        queries = data['queries']
        laws, law_coverage = engine.cached_laws(queries)
        w8, w8_census, _ = engine.week8_queries(data, pd, build_features=True)
        check(w8 is not None and len(w8) == 120 and w8_census['captured_rb_rows'] == 122,
              'original Week8 query coverage differs')
        nmodel = joblib.load(io.BytesIO(engine.pin(original_plan['week8_count_model'])))
        check(isinstance(nmodel, cdf.LeafCDFModel), 'authenticated own fixed-N model type differs')
        with threadpool_limits(limits=1):
            for ix, law, reasons in nmodel.predict_batches(w8, batch_size=128):
                for j, pos in enumerate(ix):
                    r = w8.iloc[pos]
                    laws[tuple(r[k] for k in KEY)] = dict(law=dict(kind='leaf_cdf', support=law.support.tolist(),
                        weights=law.weights[j].tolist(), prior=vars(law.prior), prior_weight=law.b),
                        source_forecast_sha256=original_plan['week8_count_model']['sha256'],
                        source_information_max_UTC=str(r.feature_max_source_available_utc))
        del nmodel
        queries[2026] = pd.concat([queries[2026], w8], ignore_index=True)
        for year, q in queries.items():
            retained = json.loads(gzip.decompress(read_old(f'QUERY_IDENTITIES_{year}.json.gz')))
            expected = [{k: int(getattr(r, k)) if k in ('season', 'week') else str(getattr(r, k))
                         for k in KEY + CTX} for r in q.itertuples()]
            check(enc(expected) == enc(retained), 'regenerated query identity/horizon differs from frozen original')
            check(len(q) == {2025: 923, 2026: 1364}[year], 'original intended query count differs')
        model = joblib.load(io.BytesIO(read_old('MODEL_S1_COMPLETE_RETURNED.joblib')))
        check(isinstance(model, core.ConditionalCarryModel) and model.yards is not None and model.success is not None,
              'exact returned complete conditional model required')
        STATE['phase'] = 'STRUCTURED_INFERENCE_WITH_CORRECT_CLOCK_SERIALIZATION'
        for year, q in queries.items():
            with threadpool_limits(limits=1):
                for r in q.itertuples():
                    fixed = laws[tuple(getattr(r, k) for k in KEY)]
                    prediction = core.integrated_point(model, ctx, r, fixed['law'])
                    context_clock = prediction['source_information_max_utc']
                    full_clock = latest_aware([context_clock, r.feature_max_source_available_utc,
                                             fixed.get('source_information_max_UTC')], pd)
                    cutoff = pd.Timestamp(r.cutoff_utc)
                    check(cutoff.tzinfo is not None and (full_clock is None or full_clock < cutoff),
                          'full-system source clock is not strictly earlier than cutoff')
                    prediction.update(context_information_max_utc=context_clock,
                        fixed_n_information_max_utc=fixed.get('source_information_max_UTC'),
                        source_information_max_utc=full_clock.isoformat() if full_clock is not None else None)
                    identity = {k: int(getattr(r, k)) if k in ('season', 'week') else str(getattr(r, k)) for k in KEY + CTX}
                    generation = now()
                    for arm, field in zip(ARMS, ['point', 'no_context_fixed_n_point']):
                        STATE['rows'].append(dict(**identity, arm=arm, target='rush_yd', point=prediction[field],
                            probability=None, outcome_law=None,
                            point_semantics=prediction['point_semantics'] if arm.startswith('S1') else 'FIXED_N_MEAN_TIMES_SHRUNK_EARLIER_OWN_YPC',
                            source_information_max_utc=prediction['source_information_max_utc'],
                            fixed_n_source_sha256=engine.LAW_REF['sha256'] if r.week <= 7 or year == 2025 else original_plan['week8_count_model']['sha256'],
                            generation_UTC=generation, original_issued_UTC=None, execution_kind='RETROSPECTIVE_INFERENCE_RECOVERY'))
                    STATE['diagnostics'].append(dict(**identity, **prediction, generation_UTC=generation, original_issued_UTC=None))
        check(len(STATE['rows']) == 4574 and len(STATE['diagnostics']) == 2287, 'complete recovered coverage required')
        seen = set()
        for row in oldrows + STATE['rows']:
            k = (row['arm'], *(row[x] for x in KEY))
            check(k not in seen, 'recovered output duplicates an original forecast')
            seen.add(k)
        STATE['phase'] = 'IMMUTABLE_RECOVERED_FORECAST_PERSISTENCE'
        frozen_body = gzip.compress(enc(oldrows + STATE['rows']), mtime=0)
        frozen = put('ALL_FORECASTS_BEFORE_LABELS_RECOVERED_V1.json.gz', frozen_body)
        check(store.read(frozen['id'], frozen['sha256']) == frozen_body, 'recovered vector durable readback differs')
        frozen_readback_UTC = now()
        diagnostics = put('DIAGNOSTICS_RECOVERED_V1.json.gz', gzip.compress(enc(STATE['diagnostics']), mtime=0))
        check(store.read(diagnostics['id'], diagnostics['sha256']) == gzip.compress(enc(STATE['diagnostics']), mtime=0),
              'recovered diagnostic readback differs')
        models = {name: oldrefs[file] for name, file in {
            '2025_D0_UNCHANGED_HGB_MAE': 'MODEL_2025_D0_UNCHANGED_HGB_MAE.joblib',
            '2025_D1_HGB_RAW_CONDITIONAL_PROFILE': 'MODEL_2025_D1_HGB_RAW_CONDITIONAL_PROFILE.joblib',
            '2026_D1_HGB_RAW_CONDITIONAL_PROFILE': 'MODEL_2026_D1_HGB_RAW_CONDITIONAL_PROFILE.joblib',
            'S1_YARDS': 'MODEL_S1_YARDS_RETURNED.joblib', 'S1_COMPLETE': 'MODEL_S1_COMPLETE_RETURNED.joblib'}.items()}
        models['2026_D0_UNCHANGED_HGB_MAE'] = engine.safe(engine.HGB_REF)
        receipt = dict(version=PARENT, state='FROZEN_FORECASTS_COMPLETE_UNSCORED', UTC=now(),
            fits_attempted=5, fits_returned=5, models=models, forecasts=frozen,
            forecast_rows=len(oldrows)+len(STATE['rows']), profile_rows=2289,
            artifacts=failure['artifacts']+STATE['artifacts'], week8=admission['week8'],
            counts=dict(new_source_HTTP=0, new_scoring=0, new_original_issuances=0, production_writes=0,
                        recovery_new_fits=0, recovery_fixed_N_player_games=120,
                        recovery_new_structured_player_games=2287, recovery_new_structured_output_rows=4574),
            recovery=dict(version=VERSION, protocol_sha256=plan_sha, parent_failure_sha256=sha(failure_raw),
                parent_failure_preserved=True, parent_error_sha256=ERROR_SHA,
                change='Parse each supplied aware clock independently before maximum; no feature/law/model/point-equation change',
                original_models_refitted=0, original_partial_vector_sha256=PARTIAL_SHA,
                original_forecast_rows_preserved=len(oldrows), started_UTC=started,
                frozen_native_readback_UTC=frozen_readback_UTC, actual_completion_UTC=now()),
            resources=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start,
                           RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
            original_resource_status='Original failure receipt did not retain CPU/wall counters; no invented aggregate total',
            storage=store.checkpoint(), lookback_selection='INCOMPLETE_FIXED8',
            evidence='CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION;NOT_ORIGINAL_ISSUANCE')
        put('EXECUTION_RECEIPT_RECOVERED_V1.json', enc(receipt))
        check(not (OUT/'EFFICIENCY_EXECUTION_RECEIPT_V1.json').exists(), 'original completed receipt must not be overwritten')
        with (OUT/'EFFICIENCY_EXECUTION_RECEIPT_V1.json').open('xb') as handle:
            handle.write(enc(receipt)); handle.flush(); os.fsync(handle.fileno())
        signal.alarm(0)
        print(json.dumps(dict(state=receipt['state'], recovery=VERSION, new_fits=0,
            new_structured_rows=4574, receipt='EFFICIENCY_EXECUTION_RECEIPT_V1.json')))
    except BaseException as error:
        signal.alarm(0)
        failure_record = dict(version=VERSION, state='RECOVERY_FAILED_RETAINED_NO_REFIT', UTC=now(),
            phase=STATE['phase'], error_type=type(error).__name__, error_sha256=sha(str(error).encode()),
            fits_attempted=0, fits_returned=0, original_fits_preserved=5, artifacts=STATE['artifacts'],
            automatic_retry=False)
        try:
            put('RECOVERY_FAILURE_PRIVATE_V1.json', enc(dict(**failure_record, traceback=traceback.format_exc())), True)
            put('RECOVERY_STRUCTURED_PARTIALS_V1.json.gz', gzip.compress(enc(STATE['rows']), mtime=0), True)
            failure_record['storage'] = store.checkpoint()
        except BaseException as retention_error:
            failure_record['failure_retention_error_type'] = type(retention_error).__name__
        path = OUT/'EFFICIENCY_RECOVERY_FAILURE_V1.json'
        with path.open('xb') as handle:
            handle.write(enc(failure_record)); handle.flush(); os.fsync(handle.fileno())
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--go', type=Path, required=True)
    parser.add_argument('--go-sha256', required=True)
    args = parser.parse_args()
    plan, raw = authorize(args)
    run(plan, raw, args.plan_sha256)


if __name__ == '__main__':
    main()
