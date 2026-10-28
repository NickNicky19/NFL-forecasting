"""Dispatch one exact prepared OWNER Root; persist intent before the only POST."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path('/workspace/nfl-system-audit/continuation')
GH = '/workspace/nfl-system-audit/bin/gh'
REPO = 'repos/NickNicky19/NFL-forecasting'


def api(route):
    return json.loads(subprocess.check_output([GH, 'api', '--method', 'GET', route,
        '-H', 'Cache-Control: no-cache']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attempt', type=int, required=True)
    p.add_argument('--kind', choices=['registration', 'first-primary', 'failed-first-recovery', 'continuation'], required=True)
    p.add_argument('--expected-main', required=True)
    args = p.parse_args()
    assert args.attempt >= 25
    label = args.kind+str(args.attempt)
    root_raw = (BASE/('private/weekly-go-'+str(args.attempt)+'.json')).read_bytes()
    root = json.loads(root_raw)
    dispatch_path = BASE/('private/weekly-dispatch-'+str(args.attempt)+'.json')
    dispatch_raw = dispatch_path.read_bytes()
    dispatch = json.loads(dispatch_raw)
    expected_operation = 'CONTROLLER_REGISTRATION' if args.kind == 'registration' else 'RECURRING_CAPTURE'
    assert root['operation'] == expected_operation
    if args.kind == 'failed-first-recovery':
        assert root['effective_epoch']['controller_context']['schema_version'] == 'audit-weekly-owner-failed-first-primary-recovery-v1'
        assert args.attempt == 28
    if args.kind == 'continuation':
        # Normal continuation has its original non-null history checkpoint;
        # it must never reuse either special first-primary recovery claim.
        context = root['effective_epoch']
        assert args.attempt == 30
        assert root['schema_version'] == 'audit-weekly-hosted-v4-root-GO'
        assert context['schema_version'] == 'audit-weekly-recurring-v5-context'
        assert context['controller_context'] is None
        assert isinstance(context['previous_capture'], dict)
        assert set(context['previous_capture']) == {'feed_sha256', 'receipt_sha256'}
        assert isinstance(context['previous_checkpoint'], dict)
        assert set(context['previous_checkpoint']) == {'schema_version', 'path', 'sha256'}
        assert context['previous_checkpoint']['schema_version'] == 'audit-weekly-grade-history-v2-locator-reference'
        assert context['previous_capture'] == {
            'feed_sha256': 'a71202ff804378d9b2343fc502e06ed82d829e53d7dfc57d9459d620abbfc01a',
            'receipt_sha256': '127f8eb72c73fbe9c89dfd3ac5e6e345acb0c449aa78fe4625a9e2a6f74c62b4',
        }
        assert isinstance(root['source_history_binding'], dict)
    assert root_raw == json.dumps(root, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    assert len(root_raw) <= 60 << 10 and len(dispatch_raw) <= 65535
    assert dispatch['ref'] == 'research/weekly-storage-probe-v1'
    assert dispatch['inputs']['inference_builder_go_json'].encode() == root_raw
    assert dispatch['inputs']['inference_builder_go_sha256'] == hashlib.sha256(root_raw).hexdigest()
    assert datetime.fromisoformat(root['issued_at_utc']) <= datetime.now(timezone.utc) < datetime.fromisoformat(root['expires_at_utc'])
    actor = api('user')
    assert (actor['login'], actor['id']) == ('NickNicky19', 208912933)
    for branch, expected in [('main', args.expected_main), ('research/weekly-storage-probe-v1', root['source_sha'])]:
        assert api(REPO+'/git/ref/heads/'+branch)['object']['sha'] == expected
    for status in ('in_progress', 'queued', 'waiting', 'requested', 'pending'):
        runs = api(REPO+'/actions/workflows/lab.yml/runs?status='+status+'&per_page=100')
        assert runs['total_count'] == 0 and runs['workflow_runs'] == [], 'An existing native writer is '+status
    intent = dict(schema_version='audit-create-only-dispatch-intent-v1', attempt=args.attempt,
        created_at_utc=datetime.now(timezone.utc).isoformat(), source_sha=root['source_sha'],
        root_go_sha256=hashlib.sha256(root_raw).hexdigest(), dispatch_sha256=hashlib.sha256(dispatch_raw).hexdigest(),
        operation=root['operation'])
    path = BASE/('private/'+label+'-dispatch-intent.json')
    with path.open('x') as out:
        json.dump(intent, out, indent=2)
    path.chmod(0o600)
    with (BASE/('private/'+label+'-dispatch.stdout')).open('xb') as out, (BASE/('private/'+label+'-dispatch.stderr')).open('xb') as err:
        result = subprocess.run([GH, 'api', '--method', 'POST', REPO+'/actions/workflows/lab.yml/dispatches',
            '--input', str(dispatch_path)], stdout=out, stderr=err)
    for suffix in ('stdout', 'stderr'):
        (BASE/('private/'+label+'-dispatch.'+suffix)).chmod(0o600)
    receipt = dict(state='DISPATCH_ACCEPTED_IDENTIFICATION_PENDING' if result.returncode == 0 else 'DISPATCH_AMBIGUOUS_DO_NOT_RETRY',
        returncode=result.returncode, attempt=args.attempt, created_at_utc=intent['created_at_utc'],
        fits=0, successful_forecast_claimed=False)
    with (BASE/('evidence/'+label+'-dispatch-result.json')).open('x') as out:
        json.dump(receipt, out, indent=2)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
