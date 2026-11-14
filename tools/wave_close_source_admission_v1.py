"""Root-only bounded admission/retention for one saved-output comparison.

Uses the original storage classes and permanent lock; no model loading,
credential access, private upload, new collector or quota-policy changes.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, os, subprocess, sys, time, urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/abc-championship/wave-close-next-comparison-20261114-01'
ID = 'A-B-FTN-COMPLETION-W1-W4-SAVED-JOIN-v1'
PEAK, META, FUTURE = 8388608, 786432, 83886080
TASK_LIMIT = 2097152


def encode(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def safe(usage):
    return {k: v for k, v in usage.items() if isinstance(v, int) and ('bytes' in k or 'limit' in k)}


def stores():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    from tools import category_topfive_matched12_storage_v1 as fourth
    from tools.category_topfive_original_leans_private_freeze_v1_1 import storage
    prepared = fourth.prepare(ROOT)
    full, _ = fourth.open_store(ROOT, allocation_sha256=prepared['allocation_sha256'],
                               root_go=fourth.GO, readonly=True)
    # Original authenticated writer, not a modified readonly peer.
    third = storage(ROOT)
    return full, third, prepared


def capacity(full, third):
    full._refresh()
    outer = full._require(PEAK + META)
    third._refresh()
    market = third._require(FUTURE + PEAK + META)
    return {'complete': safe(outer), 'market': safe(market)}


def retained(third, baseline):
    """Count actual unique physical growth, including CAS and registry overhead."""
    actual = third._scan()['forward_physical_bytes'] - baseline
    assert 0 <= actual <= TASK_LIMIT, 'New task physical retention envelope exceeded'
    return actual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['admit', 'cache', 'execute'])
    ap.add_argument('--go', type=Path)
    ap.add_argument('--go-sha256')
    ap.add_argument('--publication-commit')
    args = ap.parse_args()
    start = time.monotonic()
    full, third, prepared = stores()
    namespace = third.state_root / 'research/wave-close-next-comparison-20261114-01'
    public = {'id': ID, 'UTC': utc(), 'mode': args.mode}
    with full.transaction():
        before = capacity(full, third)
        prior = REPORT / 'SOURCE_ADMISSION_PUBLIC_V1.json'
        baseline = (json.loads(prior.read_bytes())['before']['market']['forward_physical_bytes']
                    if prior.exists() else before['market']['forward_physical_bytes'])
        if args.mode == 'admit':
            from tools.abc_a_dynamic_carry_wave_v1 import sources
            from tools.category_topfive_matched12_replay_v1_2 import owner_validate
            refs = sources()[2]
            admitted = {}
            for name in ['offers', 'qualified_labels', 'frozen_bundle']:
                owner = owner_validate(full, refs[name])
                body = Path(refs[name]['path']).read_bytes()
                assert digest(body) == refs[name]['sha256'] and len(body) == refs[name]['bytes']
                admitted[name] = dict(path=refs[name]['path'], bytes=len(body),
                                      sha256=digest(body), owner_validation=owner)
            access = dict(state='PASS_EXISTING_A_SOURCE_OWNER_VALIDATION_AND_READBACK',
                id=ID, worker_id=ID, registered_by='/root', UTC=utc(),
                complete_peer_census_verified=True, all_old_caps_and_reserves_preserved=True,
                permitted_original_owners=sorted({v['owner_validation']['owner'] for v in admitted.values()}),
                sources=admitted, storage_allocation_sha256=prepared['allocation_sha256'])
            third.register_root(namespace)
            path = namespace / 'SOURCE_ACCESS_RECEIPT.json'
            third.write_bytes(path, encode(access))
            ref = third.validate_reference(path, digest(encode(access)))
            public.update(state=access['state'], receipt={k:ref[k] for k in ['bytes','sha256']},
                source_owners={k:v['owner_validation'] for k,v in admitted.items()},
                storage_allocation_sha256=prepared['allocation_sha256'])
        else:
            raw = args.go.read_bytes()
            assert digest(raw) == args.go_sha256
            plan = json.loads(raw)
            assert plan['id'] == ID and plan['state'] == 'ROOT_REGISTERED_SCORING_GO'
            assert args.publication_commit and len(args.publication_commit) == 40
            receipt = namespace / 'SOURCE_ACCESS_RECEIPT.json'
            third.validate_reference(receipt, plan['source_access_receipt_sha256'])
            if args.mode == 'cache':
                # Native CAS streaming is unavailable through the metadata connector.
                # Exactly four immutable public derivative GETs, no raw FTN acquisition.
                proofs = []
                for ref in plan['B_forecast_refs']:
                    target = namespace / 'B_cache' / ref['id']
                    assert not target.exists(), 'Existing cache must be reused, not reacquired'
                    request = urllib.request.Request(ref['retrieval_url'], headers={'User-Agent':'A-existing-export-readback/1'})
                    with urllib.request.urlopen(request, timeout=30) as response:
                        assert response.status == 200 and response.url == ref['retrieval_url']
                        body = response.read(ref['bytes'] + 1)
                    assert len(body) == ref['bytes'] and digest(body) == ref['sha256']
                    third.write_bytes(target, body)
                    proof = third.validate_reference(target, ref['sha256'])
                    proofs.append(dict(id=ref['id'], bytes=proof['bytes'], sha256=proof['sha256'], observed_UTC=utc()))
                public.update(state='PASS_EXACT_IMMUTABLE_B_DERIVED_EXPORT_CACHE', refs=proofs,
                              public_derivative_GETs=4, raw_feed_collection=0)
            else:
                c_cache = ROOT / 'reports/abc-championship/interception-historical-delivery-01/completion/C_code'
                stage = namespace / 'staging'
                stage.mkdir(mode=0o700, parents=True, exist_ok=False)
                command = [sys.executable, '-B', str(ROOT/'tools/wave_close_b_ftn_completion_join_v1.py'),
                    '--protocol', str(args.go), '--protocol-sha256', args.go_sha256,
                    '--source-receipt', str(receipt), '--b-cache', str(namespace/'B_cache'),
                    '--c-cache', str(c_cache), '--output', str(stage/'AGGREGATES.json.gz'),
                    '--private-vectors', str(stage/'PRIVATE_VECTORS.json.gz')]
                # Cache + two512KiB files +64KiB logs and16KiB receipt/control
                # reserve remain below the original2MiB task cap before execution.
                assert (retained(third, baseline) + 2*524288 + 65536 + 16384 <= TASK_LIMIT)
                try:
                    child = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=600)
                except subprocess.TimeoutExpired as error:
                    child = subprocess.CompletedProcess(command, 124, error.stdout or b'', error.stderr or b'')
                    third.write_bytes(namespace/'WORKER_TIMEOUT.json', encode(dict(
                        state='FAILED_WALL_TIMEOUT_NO_AUTOMATIC_RETRY', UTC=utc(), timeout_seconds=600)))
                # Keep every failure/log as well as successful complete vectors.
                third.write_bytes(namespace/'WORKER_STDOUT.txt', child.stdout)
                third.write_bytes(namespace/'WORKER_STDERR.txt', child.stderr)
                proofs = {}
                for source in sorted(stage.iterdir()):
                    assert source.is_file() and not source.is_symlink()
                    body = source.read_bytes()
                    target = namespace/'retained'/source.name
                    third.write_bytes(target, body)
                    proof = third.validate_reference(target, digest(body))
                    proofs[source.name] = {k:proof[k] for k in ['bytes','sha256']}
                    # Remove only the identical temporary duplicate after CAS readback.
                    assert source.read_bytes() == target.read_bytes()
                    source.unlink()
                public.update(state='PASS_EXECUTED_AND_DURABLY_RETAINED' if child.returncode == 0
                              else 'FAILED_RETAINED_NO_AUTOMATIC_RETRY', returncode=child.returncode,
                    refs=proofs, new_fits=0, new_model_inference=0, source_GETs=0)
                print(child.stdout.decode(errors='replace'))
                if child.returncode:
                    print(child.stderr.decode(errors='replace')[-5000:])
            public.update(protocol_sha256=args.go_sha256, preregistration_commit=args.publication_commit)
        actual = retained(third, baseline)
        after = capacity(full, third)
        public.update(before=before, after=after, wall_seconds=time.monotonic()-start,
                      preserved_upcoming_bytes=FUTURE, all_three_metadata_reserves_bytes=META,
                      peak_reserved_bytes=PEAK, original_caps_unchanged=True)
        public.update(task_retained_actual_bytes=actual, task_retained_limit_bytes=TASK_LIMIT,
                      task_retention_includes='Unique new private bytes, CAS/control growth, inputs, outputs, logs and failures')
        name = {'admit':'SOURCE_ADMISSION_PUBLIC_V1.json','cache':'B_EXPORT_CACHE_READBACK_V1.json',
                'execute':'NATIVE_PRIVATE_RETENTION_V1.json'}[args.mode]
        report_path = REPORT/name
        with report_path.open('xb') as handle:
            handle.write(encode(public));handle.flush();os.fsync(handle.fileno())
        print(json.dumps({'state':public['state'], 'report':str(report_path.relative_to(ROOT)),
                          'sha256':digest(encode(public)), 'wall_seconds':public['wall_seconds']}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        # Preserve admission/cache failures even if constructing the original
        # store fails. No automatic retry and no raw source/credential logging.
        body = encode(dict(state='FAILED_ROOT_OPERATION_NO_AUTOMATIC_RETRY', UTC=utc(),
            mode=sys.argv[1] if len(sys.argv)>1 else None, error_type=type(error).__name__,
            error_sha256=digest(str(error).encode())))
        path = REPORT / ('ROOT_FAILURE_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        with path.open('xb') as handle:
            handle.write(body);handle.flush();os.fsync(handle.fileno())
        raise
