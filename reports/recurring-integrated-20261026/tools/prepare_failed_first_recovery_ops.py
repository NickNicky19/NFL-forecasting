"""Prepare create-only private Root28 metadata from its registered clean source.

Run from the eventual clean, registered Producer checkout. Preparation uses GET
only; native OwnerRecovery must independently authenticate all original evidence.
--help imports no repository code and performs no input, credential or network IO.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

BASE = Path('/workspace/nfl-system-audit/continuation')
PRIVATE = BASE/'private'
GH = '/workspace/nfl-system-audit/bin/gh'
REPO = 'NickNicky19/NFL-forecasting'
BRANCH = 'research/weekly-storage-probe-v1'
CALENDAR_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
ROOT_CAP, DISPATCH_CAP = 60 << 10, 65535
WEEKLY_DEADLINE = '2026-10-29T18:15:00+00:00'
FIRST = 'audit-weekly-owner-first-future-primary-v1'
RECOVERY = 'audit-weekly-owner-failed-first-primary-recovery-v1'
CONTEXT = 'audit-weekly-recurring-v5-context'
HASH_FIELDS = {'retained_epoch_sha256', 'retained_choice_sha256',
    'retained_root_go_sha256', 'claim_binding_sha256'}
RECOVERY_FIELDS = HASH_FIELDS | {'schema_version', 'failed_root_go_sha256',
    'old_week8_choice_body_missing', 'old_forecast_bodies_missing'}
DIAGNOSTIC = 'EXACT_EXISTING_CLAIM_OWNER_GET_NOT_NEW_NATIVE_AUTHORITY'


class PreparationError(ValueError):
    """A fixed metadata guard failed; private input bodies never enter errors."""


def require(value, code):
    if not value:
        raise PreparationError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def digest(value):
    return sha(canonical(value))


def utc(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    require(isinstance(value, datetime) and value.tzinfo is not None, 'AWARE_ACTUAL_CLOCK_REQUIRED')
    return value.astimezone(timezone.utc)


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'DUPLICATE_METADATA_KEY')
            result[key] = value
        return result
    def nonfinite(_):
        raise PreparationError('NONFINITE_METADATA')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=nonfinite)


def read(path, cap, *, canonical_json=False):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'PLAIN_METADATA_PATH_REQUIRED')
    with path.open('rb') as stream:
        raw = stream.read(cap+1)
    require(0 < len(raw) <= cap, 'BOUNDED_METADATA_INPUT_REQUIRED')
    value = decode(raw)
    require(type(value) is dict and (not canonical_json or canonical(value) == raw), 'CANONICAL_METADATA_REQUIRED')
    return raw, value


def unbase(value, cap):
    require(type(value) is str and 0 < len(value) <= 4*((cap+2)//3), 'BOUNDED_BASE64_METADATA')
    raw = base64.b64decode(value, validate=True)
    require(0 < len(raw) <= cap, 'BOUNDED_BASE64_METADATA')
    return raw


def command(args, *, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=30)
    require(result.returncode == 0, 'READ_ONLY_COMMAND_FAILED')
    require(len(result.stdout) <= 2 << 20, 'BOUNDED_COMMAND_METADATA')
    return result.stdout


def api(route):
    return decode(command([GH, 'api', '--method', 'GET', route, '-H', 'Cache-Control: no-cache']))


def clean_head(source):
    require(not command(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=source), 'CLEAN_PRODUCER_REQUIRED')
    head = command(['git', 'rev-parse', 'HEAD'], cwd=source).decode().strip()
    require(re.fullmatch('[a-f0-9]{40}', head) and head != '679641686337bf48020826754bd6ea6b90f88fb8',
        'NEW_COMBINED_RECOVERY_SOURCE_REQUIRED')
    return head


def load_source(source):
    head = clean_head(source)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source))
    from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
    from nfl_lab import audit_weekly_hosted_v1 as hosted
    from nfl_lab import audit_weekly_operations_v1 as operations
    from nfl_lab import audit_weekly_template_v1 as template
    from nfl_lab.weekly_generic_producer import prepare_slate
    for module in (bootstrap, hosted, operations, template):
        require(Path(module.__file__).resolve().parent == source/'nfl_lab', 'LITERAL_CURRENT_SOURCE_REQUIRED')
    require(getattr(template, 'FAILED_FIRST_RECOVERY', None) == RECOVERY
        and operations.CONTEXT_V5 == CONTEXT and callable(getattr(template, 'failed_first_recovery_root', None)),
        'FINAL_RECOVERY_SCHEMA_REQUIRED')
    return head, bootstrap, hosted, operations, template, prepare_slate


def source_heads(registration, head):
    require(registration['producer']['branch'] == BRANCH and registration['producer']['source_sha'] == head
        and registration['parent']['branch'] == 'main', 'EXACT_REGISTERED_SOURCE_HEADS')
    for role in ('producer', 'parent'):
        spec = registration[role]
        remote = api('repos/'+REPO+'/git/ref/heads/'+spec['branch'])
        require(remote['object']['sha'] == spec['source_sha'], 'REGISTERED_SOURCE_HEAD_MOVED')


def registration_metadata(root_raw, root, record_raw, record, publication, source, head, bootstrap, hosted):
    require(root['schema_version'] == 'audit-weekly-hosted-v3-root-GO'
        and root['operation'] == 'CONTROLLER_REGISTRATION' and root['source_sha'] == head
        and root['code_pins'] == hosted.pins(), 'CURRENT_REGISTERED_ROOT_AND_PINS_REQUIRED')
    require(publication['state'] == 'CREATE_ONLY_V2_REGISTRY_COMMITTED_AND_READ_BACK'
        and publication['path'] == bootstrap.LOCATOR_REGISTRY_PATH
        and publication['record_sha256'] == sha(record_raw), 'EXACT_ROOT27_PUBLICATION_RECEIPT')
    owner = api('user')
    require((owner['login'], owner['id']) == ('NickNicky19', 208912933), 'ACTUAL_OWNER_GET_REQUIRED')
    content = api('repos/'+REPO+'/contents/'+bootstrap.LOCATOR_REGISTRY_PATH+'?ref=lab-state')
    published = base64.b64decode(''.join(content['content'].split()), validate=True)
    require(published == record_raw and record['repository'] == REPO, 'EXACT_CLEARED_ROOT27_RECORD_READBACK')
    reg_raw = unbase(record['registration_base64'], 128 << 10)
    registration = bootstrap.c.registration(reg_raw, sealed_sha256=sha(reg_raw), at=datetime.now(timezone.utc))
    native = bootstrap.safe_seal(unbase(record['native_artifact_zip_base64'], bootstrap.LIMITS['ZIP_bytes']), registry_version=2)
    bootstrap.source_inventories(registration['parent'], registration['producer'], registry_version=2)
    bootstrap._local_pins(registration['producer'], source)
    source_heads(registration, head)
    require(registration['parent']['source_sha'] == root['effective_epoch']['parent_source_sha']
        and native['source_sha'] == head and native['owner_root_go_sha256'] == sha(root_raw)
        and native['owner_root_issued_at_utc'] == root['issued_at_utc'] and native['branch'] == BRANCH
        and native['registration_sha256'] == sha(reg_raw)
        and native['code_pins_sha256'] == digest(registration['producer']['code_pins'])
        and native['workflow_sha256'] == registration['producer']['workflow_sha256']
        and native['registered_at_utc'] == registration['registered_at_utc']
        and native['template_descriptor']['storage_binding_sha256'] == digest(root['qualified_runtime']['binding'])
        and native['static_public_policy_sha256'] == root['publication_registration']['policy_sha256']
        and native['public_root'] is False and native['fits'] == 0, 'SOURCE_AND_NATIVE27_SEAL_BINDING')
    return registration, native


def registration_clocks(root, native, issued):
    value = root['publication_registration']
    packed = unbase(value['policy_gzip_base64'], 48 << 10)
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read((128 << 10)+1)
    require(0 < len(raw) <= 128 << 10 and sha(raw) == value['policy_sha256'], 'EXACT_REGISTERED_POLICY_BYTES')
    policy = decode(raw)
    require(canonical(policy) == raw and policy['source_sha'] == root['source_sha'], 'UNCHANGED_REGISTERED_POLICY')
    clocks = [policy['registered_at_utc'], root['issued_at_utc'], native['writer']['started_at_utc'],
        native['writer']['completed_at_utc'], native['reader']['started_at_utc'], native['reader']['completed_at_utc'],
        native['sealer']['started_at_utc'], native['registered_at_utc'], native['sealer']['completed_at_utc'],
        native['created_at_utc']]
    times = list(map(utc, clocks))
    require(times == sorted(times) and times[-1] < issued, 'NATIVE27_AND_POLICY_PRECEDE_FRESH_ISSUE')


def recovery_root(registration, failed_raw, failed, evidence, pending, schedule, issued, *, policy_sha):
    """Pure metadata transform. No old Root execution check or choice-body read."""
    issued = utc(issued)
    require(issued < utc(WEEKLY_DEADLINE), 'WEEK8_WEEKLY_DEADLINE_ALREADY_PASSED')
    old = failed['effective_epoch']; registered = registration['effective_epoch']
    scope = old['controller_context']; binding = registration['qualified_runtime']['binding']
    require(registered['schema_version'] == 'audit-weekly-controller-registration-v1-context-v4'
        and set(registered) == {'schema_version', 'parent_source_sha', 'parent_code_pins',
            'previous_capture', 'history_protocol', 'pending_post_recovery'},
        'EXACT_SOURCE_REGISTRATION_CONTEXT_REQUIRED')
    require(canonical(failed) == failed_raw and failed['repository'] == REPO
        and failed['operation'] == 'RECURRING_CAPTURE' and failed['approved'] is True
        and failed['schema_version'] == registration['schema_version'] == 'audit-weekly-hosted-v3-root-GO'
        and old['schema_version'] == CONTEXT and set(scope) == HASH_FIELDS | {'schema_version'}
        and scope['schema_version'] == FIRST and old['previous_checkpoint'] is None
        and all(re.fullmatch('[a-f0-9]{64}', str(scope[k])) for k in HASH_FIELDS), 'EXACT_HISTORICAL_ROOT26_SCOPE')
    require(failed['qualified_runtime']['binding'] == binding == evidence['binding']
        and scope['claim_binding_sha256'] == digest(binding)
        and old['previous_capture'] == registered['previous_capture']
        and 'previous_checkpoint' not in registered and utc(failed['issued_at_utc']) < issued,
        'UNCHANGED_COUNT7_ANCHOR_AND_PRIVATE_BINDING')
    failed_sha = sha(failed_raw)
    require(evidence['state'] == DIAGNOSTIC and evidence['original_root_go_sha256'] == failed_sha,
        'HISTORICAL_ROOT26_HASH_MUST_MATCH_OWNER_GET_DIAGNOSTIC')
    matches = [h for h in pending['handoffs'] if h['root_go_sha256'] == failed_sha]
    require(len(pending['handoffs']) == 4 and len(matches) == 1, 'EXACT_FOUR_HANDOFF_PENDING_ROOT26_REQUIRED')
    claim = dict(schema_version=FIRST+'-claim', epoch_sha256=scope['retained_epoch_sha256'],
        stream_id='weekly-corrected-primary-player-game-v1')
    require(evidence['claim_body'] == claim, 'ORIGINAL_STABLE_COUNT7_CLAIM_REQUIRED')
    claim_raw = canonical(claim); manifest = evidence['manifest']; asset = evidence['claim_asset']
    expected = dict(schema_version='weekly-private-restore-manifest-v2',
        payload=dict(schema_version='weekly-private-payload-v2', payload_kind='runtime_manifest', format='json',
            bytes=len(claim_raw), sha256=sha(claim_raw), source_policy_sha256=policy_sha),
        payload_asset_id=asset['id'], payload_name='blob-'+sha(claim_raw)+'.bin',
        producer_process=manifest['producer_process'], binding_sha256=digest(binding),
        writer_run_id=matches[0]['descriptor']['entry']['writer_run_id'])
    require(manifest == expected and re.fullmatch('[a-f0-9]{64}', str(manifest['producer_process'])),
        'ORIGINAL_CLAIM_MANIFEST_DIAGNOSTIC_BINDING')
    for member, body, name in ((asset, claim_raw, 'blob-'+sha(claim_raw)+'.bin'),
            (evidence['manifest_asset'], canonical(manifest), 'manifest-'+digest(manifest)+'.json')):
        require(member['state'] == 'uploaded' and member['name'] == name and member['size'] == len(body)
            and member['digest'] == 'sha256:'+sha(body)
            and any(r['key'] == 'asset:'+name and r['bytes'] == len(body) and r['sha256'] == sha(body)
                for r in pending['pending_reservations']), 'ORIGINAL_CLAIM_POST_PAIR_ACCOUNTED')
    plan = old['plan']; lead = failed['cutoff_lead_seconds']
    require(type(lead) is int and 0 < lead <= 86400 and registration['cutoff_lead_seconds'] == lead,
        'ORIGINAL_CUTOFF_LEAD_MUST_REMAIN_UNCHANGED')
    require(set(plan) == {'kind', 'season', 'week', 'deadline_utc', 'calendar_sha256', 'game_cutoffs'}
        and (plan['kind'], plan['season'], plan['week']) == ('FUTURE_CAPABLE', 2026, 8)
        and len(schedule) == len(plan['game_cutoffs']) == 14
        and len({r['game_id'] for r in schedule}) == 14
        and all((r['season'], r['week'], r['game_type']) == (2026, 8, 'REG') for r in schedule)
        and digest(schedule) == plan['calendar_sha256'], 'EXACT_FRESH_FULL_WEEK8_CALENDAR')
    cutoffs = {r['game_id']:(utc(r['kickoff_utc'])-timedelta(seconds=lead)).isoformat() for r in schedule}
    require(cutoffs == plan['game_cutoffs']
        and utc(plan['deadline_utc']) == min(map(utc, cutoffs.values()))
        and all(issued < utc(cutoffs[r['game_id']]) < utc(r['kickoff_utc']) for r in schedule),
        'ALL_FOURTEEN_ORIGINAL_CUTOFF_STRINGS_MUST_STAY_FUTURE')
    marker = dict(schema_version=RECOVERY, **{k:scope[k] for k in HASH_FIELDS},
        failed_root_go_sha256=failed_sha, old_week8_choice_body_missing=True, old_forecast_bodies_missing=True)
    require(set(marker) == RECOVERY_FIELDS, 'EXACT_EIGHT_RECOVERY_FIELDS')
    root = deepcopy(registration)
    root.update(operation='RECURRING_CAPTURE', issued_at_utc=issued.isoformat(),
        expires_at_utc=(issued+timedelta(hours=1)).isoformat(),
        effective_epoch=dict(schema_version=CONTEXT, controller_context=marker,
            previous_capture=deepcopy(registered['previous_capture']), previous_checkpoint=None,
            plan=deepcopy(plan), pending_post_recovery=deepcopy(registered['pending_post_recovery'])))
    require(root['effective_epoch']['plan'] == old['plan'], 'EXACT_LITERAL_ROOT26_PLAN_PRESERVED')
    return root


def calendar():
    request = Request(CALENDAR_URL, headers={'Cache-Control':'no-cache'}, method='GET')
    with urlopen(request, timeout=30) as response:
        raw = response.read((8 << 20)+1)
        require(response.status == 200 and 0 < len(raw) <= 8 << 20, 'CURRENT_BOUNDED_CALENDAR_GET_REQUIRED')
    return raw, datetime.now(timezone.utc)


def save_private(values, *, directory=PRIVATE):
    """Create only; retain any partial local failure and all prior receipts."""
    directory = Path(directory).absolute()
    require(directory.is_dir() and not any(p.is_symlink() for p in (directory, *directory.parents))
        and directory.stat().st_mode & 0o077 == 0, 'EXISTING_PRIVATE_OUTPUT_DIRECTORY_REQUIRED')
    require(len(values) == 3 and all(Path(name).name == name for name in values), 'THREE_CLOSED_PRIVATE_OUTPUTS')
    require(not any((directory/name).exists() or (directory/name).is_symlink() for name in values), 'CREATE_ONLY_OUTPUT_ALREADY_EXISTS')
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name, body in values.items():
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body); stream.flush(); os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('registration-root', 'record', 'publication-receipt', 'failed-root', 'claim-evidence'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--attempt', type=int, required=True)
    args = parser.parse_args(argv)
    require(args.attempt == 28, 'EXPLICIT_FUTURE_ROOT28_ONLY')
    require(datetime.now(timezone.utc) < utc(WEEKLY_DEADLINE), 'WEEK8_WEEKLY_DEADLINE_ALREADY_PASSED')
    source = Path.cwd().resolve()
    head, bootstrap, hosted, operations, template, prepare_slate = load_source(source)
    root_raw, registration_root = read(args.registration_root, ROOT_CAP, canonical_json=True)
    record_raw, record = read(args.record, 256 << 10, canonical_json=True)
    _, publication = read(args.publication_receipt, 1 << 20)
    failed_raw, failed = read(args.failed_root, ROOT_CAP, canonical_json=True)
    evidence_raw, evidence = read(args.claim_evidence, 256 << 10)
    registered, native = registration_metadata(root_raw, registration_root, record_raw, record,
        publication, source, head, bootstrap, hosted)
    pending = template.pending_recovery(registration_root)
    raw, retrieved = calendar()
    rows = operations.calendar(raw, season=2026, week=8)
    schedule = [{k:r[k] for k in ('season', 'week', 'game_type', 'game_id', 'kickoff_utc')} for r in rows]
    issued = datetime.now(timezone.utc)
    registration_clocks(registration_root, native, issued)
    root = recovery_root(registration_root, failed_raw, failed, evidence, pending, schedule,
        issued, policy_sha=template.POLICY_SHA)
    require(template.static_root_sha256(root) == template.static_root_sha256(registration_root),
        'ONLY_REGISTERED_DYNAMIC_ROOT_FIELDS_MAY_CHANGE')
    slate = prepare_slate(schedule, season=2026, week=8, game_cutoffs=root['effective_epoch']['plan']['game_cutoffs'], now=issued)
    require(slate['elapsed_games'] == 0 and slate['scheduled_games'] == 14
        and issued < utc(slate['weekly_deadline_utc']), 'ACTUAL_FULL_WEEK_DEADLINE_REQUIRED')
    hosted.validate_root(root, now=issued)
    operations.context(root['effective_epoch']); template.failed_first_recovery_root(root)
    encoded = canonical(root); bootstrap._recurring(encoded, bot=False)
    dispatch = canonical(dict(ref=BRANCH, inputs=dict(mode=hosted.MODE,
        inference_builder_go_json=encoded.decode(), inference_builder_go_sha256=sha(encoded))))
    require(len(encoded) <= ROOT_CAP and len(dispatch) <= DISPATCH_CAP, 'UNCHANGED_ROOT_AND_DISPATCH_CAPS')
    require(clean_head(source) == head and root['code_pins'] == hosted.pins(), 'SOURCE_CHANGED_DURING_PREPARATION')
    source_heads(registered, head)
    require(datetime.now(timezone.utc) < utc(WEEKLY_DEADLINE), 'WEEKLY_DEADLINE_PASSED_BEFORE_SAVE')
    marker = root['effective_epoch']['controller_context']
    receipt = dict(schema_version=RECOVERY+'-owner-plan', source_sha=head,
        root_go_sha256=sha(encoded), failed_root_go_sha256=sha(failed_raw),
        registration_root_sha256=sha(root_raw), publication_record_sha256=sha(record_raw),
        claim_diagnostic_sha256=sha(evidence_raw), claim_diagnostic_is_live_authority=False,
        url=CALENDAR_URL, bytes=len(raw), sha256=sha(raw), retrieved_utc=retrieved.isoformat(),
        issued_at_utc=root['issued_at_utc'], expires_at_utc=root['expires_at_utc'],
        full_week=8, games=14, calendar_sha256=root['effective_epoch']['plan']['calendar_sha256'],
        plan_exactly_equals_failed_root=True, cutoff_lead_seconds=root['cutoff_lead_seconds'],
        plan_deadline_utc=root['effective_epoch']['plan']['deadline_utc'],
        weekly_deadline_utc=slate['weekly_deadline_utc'], issuance_deadline_utc=WEEKLY_DEADLINE,
        retained_scope={k:marker[k] for k in HASH_FIELDS}, original_first_claim_retained=True,
        old_week8_choice_body_missing=True, old_forecast_bodies_missing=True,
        old_choice_reconstructed=False, old_capture_qualified=False, native_recovery_authority_minted=False,
        actual_new_forecast_issued=False, historical_scores_or_workloads_used=False,
        new_fits=0, remote_writes=0, dispatches=0)
    save_private({'weekly-go-28.json':encoded, 'weekly-dispatch-28.json':dispatch,
        'ops28-failed-first-recovery-plan-receipt.json':canonical(receipt)})
    print(json.dumps(dict(state='OWNER_FAILED_FIRST_RECOVERY_PREPARED_NO_POST', source_sha=head,
        root_go_sha256=sha(encoded), root_bytes=len(encoded), dispatch_bytes=len(dispatch),
        games=14, plan_exactly_equals_failed_root=True, new_forecasts=0, fits=0, remote_writes=0)))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        reason = str(error) if isinstance(error, PreparationError) else 'SOURCE_OR_INPUT_GUARD_REJECTED'
        print(json.dumps(dict(state='PREPARATION_REJECTED_NO_POST', reason=reason,
            new_forecasts=0, fits=0, remote_writes=0)), file=sys.stderr)
        raise SystemExit(2)
