"""Retain three exact receipts and restore bound evidence without inference.

Execution requires a published, hash-bound root GO. No model deserialization,
fits, grading, source acquisition, old-namespace writes or registration changes.
"""
from __future__ import annotations
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'A-NEXT02-FRESHNESS-FINAL-RETENTION-v1'
ALLOCATION_PATH = 'reports/abc-championship/profile-increment-to-release-01/closure-next-02/FRESHNESS_NATIVE_ALLOCATION_V1.json'
ALLOCATION_SHA = '3a9997259e71863460921f2beb24b9f85d48602fe0454a50bf0d6428e49cd33e'
GUARD_PATH = 'nfl_lab/profile_freshness_a_storage_v1.py'
GUARD_SHA = '7465a71366716cd7e60c7d55103911e2aa9e143f10d4dc6557473ecb3d8f0bd7'
LIMIT = 512 * 1024
ARMS = ['F0_ORIGINAL_BASE', 'F1_ORIGINAL_PROFILE', 'F2_48H_BASE', 'F3_48H_PROFILE']
WRITES = ['FRESHNESS_EXECUTION_POSTWRITE_RECEIPT_V2.json',
          'FRESHNESS_MODEL_INDEPENDENT_RECEIPT_V2.json',
          'FRESHNESS_ARITHMETIC_INDEPENDENT_RECEIPT_V2.json']

def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

def sha(body):
    return hashlib.sha256(body).hexdigest()

def check(ok, message):
    if not ok:
        raise AssertionError(message)

def document(path, expected):
    body = Path(path).read_bytes()
    check(sha(body) == expected, 'bound document hash differs: ' + Path(path).name)
    return body, json.loads(body)

def unique_artifact(execution, name):
    rows = [ref for ref in execution['artifacts'] if ref['id'] == name]
    check(len(rows) == 1, 'unique immutable execution artifact required: ' + name)
    return rows[0]

def refs_to_restore(plan, execution, scoring):
    retained = {ref['id']: ref for ref in plan['retained_refs']}
    check(len(retained) == len(plan['retained_refs']), 'duplicate original retained IDs')
    refs = [retained[plan['saved_ids'][name]] for name in ('F0_forecasts', 'F1_forecasts')]
    check(all(ref['namespace'] == 'PRIMARY' for ref in refs), 'original output namespace changed')
    refs += [execution['models'][arm] for arm in ARMS[2:]]
    refs += [unique_artifact(execution, 'FORECAST_2026_' + arm + '.json.gz') for arm in ARMS[2:]]
    refs += [unique_artifact(execution, name) for name in (
        'TRAINING_ALIGNED_48H_BASE_AND_PLAYER_PROFILE.parquet',
        'QUERY_ALIGNED_48H_BASE_AND_PLAYER_PROFILE.parquet',
        'ORIGINAL_INPUT_PARITY_V1.json',
        'FRESHNESS_EXECUTION_RECEIPT_V2.json')]
    refs += [execution['prepared_binding'], execution['forecasts']]
    refs += [scoring[name] for name in ('full_score', 'private_view', 'private_player_card')]
    check(len(refs) == len({ref['id'] for ref in refs}), 'duplicate restoration IDs')
    for ref in refs:
        check(set(ref) == {'id', 'namespace', 'bytes', 'sha256'}, 'exact plain immutable member ref required')
        check(type(ref['bytes']) is int and ref['bytes'] >= 0, 'invalid member byte count')
        check(ref['namespace'] in {'PRIMARY', 'FRESHNESS'}, 'unexpected restoration namespace')
    return refs

def bind_inputs(args):
    go_raw, go = document(args.go, args.go_sha256)
    check(go['version'] == VERSION and go['state'] == 'ROOT_REGISTERED_FINAL_RETENTION_GO', 'published root retention GO required')
    check(go['code_sha256'] == sha(Path(__file__).read_bytes()), 'retention worker source changed')
    check(go['allocation'] == {'path': ALLOCATION_PATH, 'sha256': ALLOCATION_SHA}, 'reviewed allocation binding changed')
    check(go['resources'] == {'CPU_seconds': 220, 'wall_seconds': 600, 'RSS_bytes': 1024**3}, 'retention resource envelope changed')
    check(go['maximum_new_private_bytes'] == LIMIT and go['write_ids'] == WRITES, 'finite exact retention write scope changed')
    specs = [('protocol', args.protocol, args.protocol_sha256),
             ('execution_receipt', args.execution_receipt, args.execution_receipt_sha256),
             ('scoring_receipt', args.scoring_receipt, args.scoring_receipt_sha256),
             ('model_review', args.model_review, args.model_review_sha256),
             ('arithmetic_review', args.arithmetic_review, args.arithmetic_review_sha256)]
    docs, bodies = {}, {}
    for key, path, digest in specs:
        check(go['input_sha256'][key] == digest, 'root input hash binding differs: ' + key)
        bodies[key], docs[key] = document(path, digest)
    p, e, s, m, a = [docs[key] for key in ('protocol', 'execution_receipt', 'scoring_receipt', 'model_review', 'arithmetic_review')]
    check(p['arms'] == ARMS and p['maximum_new_fits'] == 2 and p['allocation'] == go['allocation'], 'two-model procedure binding differs')
    check(e['state'] == 'FROZEN_TWO_NEW_ALIGNED_TIMING_ARMS_AND_TWO_SAVED_BASELINES_UNSCORED', 'unfrozen model execution')
    check(e['fits_attempted'] == e['fits_returned'] == e['new_fits'] == 2, 'completed new model count differs')
    check(e['original_refits'] == e['old_model_loads'] == e['old_model_inference'] == 0, 'old procedure changed')
    check(s['state'] == 'PASS_ALIGNED_TIMING_SCORE_AND_PRIVATE_READBACK', 'completed scoring required')
    check(s['score_sha256'] == s['full_score']['sha256'], 'full-score hash binding differs')
    check(m['state'] == 'PASS_ONLY_NEW_F2_F3_MODEL_AND_INFERENCE_WITH_PRIOR_BASELINE_EVIDENCE_REUSED', 'completed exact model review required')
    check(m['protocol_sha256'] == args.protocol_sha256 and m['receipt_sha256'] == args.execution_receipt_sha256, 'model review version differs')
    check(a['state'] == 'PASS_INDEPENDENT_DECIMAL_ORIGINAL_OFFER_LABEL_AND_PRIMARY_CONTRAST_ARITHMETIC' and a['discrepancies'] == 0, 'completed arithmetic review required')
    check(a['score_sha256'] == s['full_score']['sha256'], 'arithmetic review score differs')
    for arm in ARMS[2:]:
        check(m['results'][arm]['model_sha256'] == e['models'][arm]['sha256'], 'reviewed model binding differs')
        check(m['results'][arm]['forecast_sha256'] == unique_artifact(e, 'FORECAST_2026_' + arm + '.json.gz')['sha256'], 'reviewed law binding differs')
    for path, digest in {**p['code_sha256'], **p['source_configuration_sha256']}.items():
        check(sha((ROOT / path).read_bytes()) == digest, 'bound source/config changed: ' + path)
    writes = dict(zip(WRITES, [bodies['execution_receipt'], bodies['model_review'], bodies['arithmetic_review']]))
    check(sum(map(len, writes.values())) <= LIMIT, 'three-receipt payload exceeds finite reservation')
    return go, docs, writes

def restore_contracts(refs, restored, plan, execution, scoring):
    byid = {ref['id']: ref for ref in refs}
    manifest = json.loads(gzip.decompress(restored[execution['forecasts']['id']]))
    check(manifest['arm_order'] == ARMS and manifest['rows'] == 5456 and len(manifest['parts']) == 4, 'frozen alias manifest differs')
    for arm, part in zip(ARMS, manifest['parts']):
        check(part['procedure_alias'] == arm and part['rows'] == 1364, 'manifest procedure/row binding differs')
        check(part['ref'] == byid[part['ref']['id']], 'restored forecast ref differs from frozen manifest')
    prepared = json.loads(restored[execution['prepared_binding']['id']])
    for key in ('training', 'query'):
        check(prepared[key] == byid[prepared[key]['id']], 'restored prepared-data ref differs')
    parity = json.loads(restored['ORIGINAL_INPUT_PARITY_V1.json'])
    check(parity == execution['original_input_parity'] == prepared['old_parity'], 'original input parity bindings differ')
    native_execution = json.loads(restored['FRESHNESS_EXECUTION_RECEIPT_V2.json'])
    native_ref = byid['FRESHNESS_EXECUTION_RECEIPT_V2.json']
    expected_local = dict(native_execution, artifacts=native_execution['artifacts'] + [native_ref])
    check(expected_local == execution, 'prewrite/postwrite execution receipt relationship differs')
    check(native_ref['bytes'] == 244051 and native_ref['sha256'] == 'd693a9d33c8841fd0c317f21cf4e508c08e4c7de5d75d7a995fccc00b3f71841', 'preserved native prewrite receipt differs')
    check(byid[scoring['full_score']['id']]['sha256'] == scoring['score_sha256'], 'restored common-score binding differs')

def main(args):
    started, cpu = time.monotonic(), time.process_time()
    sys.dont_write_bytecode = True
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    resource.setrlimit(resource.RLIMIT_CPU, (210, 220))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3,) * 2)
    def exhausted(signum, _frame):
        if signum == signal.SIGXCPU:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise TimeoutError('bounded final retention 220CPU/600wall/1GiB')
    signal.signal(signal.SIGXCPU, exhausted); signal.signal(signal.SIGALRM, exhausted); signal.alarm(590)
    def offline(event, _arguments):
        if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'}:
            raise RuntimeError('offline retained evidence only')
    sys.addaudithook(offline)
    written = []
    try:
        check(not args.output.exists(), 'immutable final receipt already exists')
        go, docs, writes = bind_inputs(args)
        check(sha((ROOT / GUARD_PATH).read_bytes()) == GUARD_SHA, 'reviewed storage guard changed')
        sys.path.insert(0, str(ROOT))
        spec = importlib.util.spec_from_file_location('nfl_lab.next02_final_retention_storage', ROOT / GUARD_PATH)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        store = module.FreshnessStore(ROOT, ROOT / ALLOCATION_PATH, ALLOCATION_SHA, root_go=module.GO)
        p, e, s = [docs[name] for name in ('protocol', 'execution_receipt', 'scoring_receipt')]
        refs = refs_to_restore(p, e, s)
        restored = store.read_many(refs)
        check(set(restored) == {ref['id'] for ref in refs}, 'incomplete restored member set')
        restore_contracts(refs, restored, p, e, s)
        restoration = [dict(ref, restored_bytes=len(restored[ref['id']]), restored_sha256=sha(restored[ref['id']])) for ref in refs]
        store.reserve(LIMIT)  # Existing two-MiB failure reserve remains required.
        for name in WRITES:
            written.append(store.put(name, writes[name]))
        readback = store.read_many(written)
        check(all(readback[name] == body for name, body in writes.items()), 'new exact receipt readback differs')
        result = dict(version=VERSION, state='PASS_FINAL_EVIDENCE_AND_THREE_RECEIPTS_NATIVE_READBACK',
                      UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      code_sha256=sha(Path(__file__).read_bytes()), root_go_sha256=args.go_sha256,
                      restored=restoration, newly_retained=written,
                      new_payload_bytes=sum(map(len, writes.values())), maximum_new_private_bytes=LIMIT,
                      prewrite_postwrite_receipts='BOTH_EXACT_VERSIONS_PRESERVED_DISTINCTLY',
                      storage=store.checkpoint(),
                      resources=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started,
                                     RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
                      counts=dict(new_fits=0, model_deserializations=0, new_inference=0, new_grades=0,
                                  source_HTTP=0, production_writes=0, old_namespace_writes=0),
                      limits=['Hash restoration and metadata binding only; no new NFL observations or predictive gain.',
                              'This receipt is owner-local evidence, not external C admission or website consumption.'])
        with args.output.open('xb') as handle:
            handle.write(enc(result)); handle.flush(); os.fsync(handle.fileno())
        signal.alarm(0)
        print(json.dumps(dict(state=result['state'], restored_members=len(refs), new_receipts=len(written), resources=result['resources'])))
    except BaseException as error:
        signal.alarm(0)
        failure = dict(version=VERSION, state='FAILED_FINAL_RETENTION_NO_INFERENCE_OR_GRADING',
                       UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       code_sha256=sha(Path(__file__).read_bytes()), root_go_sha256=args.go_sha256,
                       error_type=type(error).__name__, error_sha256=sha(str(error).encode()),
                       newly_retained=written,
                       resources=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started,
                                      RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
                       new_fits=0, new_inference=0, new_grades=0)
        with args.output.with_name(args.output.stem+'-failure.json').open('xb') as handle:
            handle.write(enc(failure))
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('go', 'protocol', 'execution-receipt', 'scoring-receipt', 'model-review', 'arithmetic-review', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('go', 'protocol', 'execution-receipt', 'scoring-receipt', 'model-review', 'arithmetic-review'):
        parser.add_argument('--'+name+'-sha256', required=True)
    main(parser.parse_args())
