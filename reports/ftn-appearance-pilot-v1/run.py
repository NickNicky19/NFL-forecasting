"""Frozen one-asset FTN appearance pilot; approved fixed-game projection only."""
import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

START = time.monotonic()
POLICY_SHA = '88745a729241e30a23aaba34d3893735360b5665e3519ed76c7c25a15c0c1284'
URL = 'https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_2024.parquet'
BUDGETS = {'invocations': 1, 'assets': 1, 'HTTP_transactions_including_redirects': 3,
           'automatic_retries': 0, 'incoming_bytes': 33554432, 'wall_seconds': 60,
           'CPU_seconds': 60, 'combined_RSS_bytes': 268435456, 'numerical_threads': 1,
           'maximum_projected_rows': 10000}
GAME = '2024_01_BAL_KC'
COLUMNS = ['nflverse_game_id', 'play_id', 'players_on_play', 'offense_players',
           'defense_players', 'n_offense', 'n_defense']
ASSET_SHA = '5e8cf1f6a11bb2be573c3db1533c28a5658907302d1ad45ca769a4ca35890d7c'
ASSET_BYTES = 4644767
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
           'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')


def now():
    return datetime.now(timezone.utc).isoformat()


def deadline(signum, frame):
    raise TimeoutError('registered deadline/finalization reserve reached')


def read_bound(binding, limit=131072):
    path = Path(binding['path'])
    if not path.is_absolute() or '..' in path.parts or path.resolve() != path.absolute():
        raise ValueError('canonical static path required')
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError('symlink forbidden')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError('unsafe or oversized frozen static input')
    body = path.read_bytes()
    after = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if (tuple(getattr(before, x) for x in fields) != tuple(getattr(after, x) for x in fields)
            or hashlib.sha256(body).hexdigest() != binding['sha256']):
        raise ValueError('frozen static input changed')
    return body


def preflight(args):
    freeze = json.loads(read_bound({'path': str(args.freeze), 'sha256': args.freeze_sha256}))
    if set(freeze) != {'policy', 'runner', 'storage_source', 'source_policy', 'metadata_result', 'environment', 'cache', 'capture', 'supervisor'}:
        raise ValueError('exact pilot freeze schema required')
    if freeze['policy']['sha256'] != POLICY_SHA or Path(freeze['runner']['path']) != Path(__file__).absolute():
        raise ValueError('policy/runner mismatch')
    read_bound(freeze['runner'])
    read_bound(freeze['storage_source'])
    if freeze['storage_source']['sha256'] != 'ac27a0a09938991e6220d947292fc6a284b2d01dff2a0217fe5656c2643a59ad':
        raise ValueError('unchanged storage required')
    policy = json.loads(read_bound(freeze['policy']))
    if (policy['budgets'] != BUDGETS or policy['asset_url'] != URL
            or policy['projection']['game'] != GAME or policy['projection']['columns'] != COLUMNS
            or policy['projection']['maximum_rows'] != 10000
            or policy['metadata']['asset_id'] != 289570938 or policy['metadata']['release_id'] != 71636554
            or policy['metadata']['bytes'] != ASSET_BYTES or policy['metadata']['declared_sha256'] != ASSET_SHA):
        raise ValueError('fixed pilot scope mismatch')
    if freeze['metadata_result']['sha256'] != policy['metadata']['result_sha256']:
        raise ValueError('actual prior metadata result pin required')
    metadata = json.loads(read_bound(freeze['metadata_result']))
    if (metadata['catalog_sha256'] != policy['metadata']['catalog_sha256']
            or metadata['asset']['id'] != 289570938 or metadata['asset']['size'] != ASSET_BYTES
            or metadata['asset']['browser_download_url'] != URL
            or metadata['asset_declared_digest'] != 'sha256:' + ASSET_SHA):
        raise ValueError('actual frozen catalog identity mismatch')
    if freeze['source_policy']['sha256'] != 'e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441':
        raise ValueError('unchanged quota policy required')
    source_policy = json.loads(read_bound(freeze['source_policy']))
    env = freeze['environment']
    if env['python'] != sys.version or Path(env['executable']).resolve() != Path(sys.executable).resolve():
        raise ValueError('interpreter mismatch')
    if any(os.environ.get(name) != '1' for name in THREADS):
        raise ValueError('one numerical thread required')
    if set(env['packages']) != {'requests', 'urllib3', 'pandas', 'numpy', 'pyarrow'}:
        raise ValueError('exact dependency set required')
    for name, version in env['packages'].items():
        if importlib.metadata.version(name) != version:
            raise ValueError('dependency mismatch')
    base = Path('/workspace/website-methods-research/resumed/ftn-participation-appearance-pilot-v1-20261023')
    if (policy['output'] != str(base) or freeze['capture'] != str(base / 'capture')
            or freeze['supervisor'] != str(base / 'supervisor')):
        raise ValueError('fresh pilot scopes required')
    return freeze, policy, source_policy


def storage_for(freeze, policy):
    # Import the exact reviewed helper without requiring the worktree package on PYTHONPATH.
    root = str(Path(freeze['storage_source']['path']).parent.parent)
    sys.path.insert(0, root)
    from nfl_lab.operational_storage import OperationalStorage
    return OperationalStorage(freeze['cache'], policy)


def child_usage():
    return {'wall_seconds': time.monotonic() - START, 'CPU_seconds': time.process_time(),
            'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            'numerical_threads': 1}


def guard():
    used = child_usage()
    if used['wall_seconds'] >= 48 or used['CPU_seconds'] >= 50:
        raise TimeoutError('child resource/finalization reserve')



class NotReady(ValueError):
    pass


def approved_url(url):
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname in ('github.com', 'release-assets.githubusercontent.com')
            and parsed.port in (None, 443) and parsed.username is None and parsed.password is None
            and not parsed.fragment)


def capture_response(storage, output, response, url, number, received_total):
    info = {'transaction': number, 'request_url': url, 'response_url': str(response.url),
            'status_code': int(response.status_code), 'response_headers_utc': now(),
            'headers': {key: response.headers.get(key) for key in ('Content-Type', 'Content-Length',
                        'Content-Encoding', 'Location', 'ETag', 'Last-Modified', 'Date')},
            'body_complete': False, 'received_bytes': 0, 'original_upstream_publication_utc': None}
    if response.url != url:
        raise ValueError('implicit URL change forbidden')
    if (response.headers.get('Content-Encoding') or 'identity').strip().lower() not in ('', 'identity'):
        storage.atomic_json(output / f'private/http/{number:03d}/response.json', info)
        raise NotReady('NONIDENTITY_HTTP_ENCODING')
    length = response.headers.get('Content-Length')
    declared = int(length) if length is not None else None
    if declared is not None and (declared < 0 or declared > 33554432 - received_total):
        storage.atomic_json(output / f'private/http/{number:03d}/response.json', info)
        raise NotReady('ADVERTISED_BODY_EXCEEDS_REMAINING_CAP')
    if response.status_code == 200 and declared != ASSET_BYTES:
        storage.atomic_json(output / f'private/http/{number:03d}/response.json', info)
        raise NotReady('FINAL_ADVERTISED_ASSET_SIZE_MISSING_OR_MISMATCH')
    path = output / f'private/http/{number:03d}/body.bin'
    digest = hashlib.sha256()
    try:
        with storage._open_writer(path, 'wb') as stream:
            while declared is None or info['received_bytes'] < declared:
                guard()
                remaining = 33554432 - received_total - info['received_bytes']
                if remaining <= 0:
                    raise NotReady('BODY_CAP_NO_EXTRA_READ')
                count = min(1048576, remaining, declared - info['received_bytes'] if declared is not None else remaining)
                chunk = response.raw.read(count, decode_content=False)
                if len(chunk) > count:
                    raise ValueError('reader exceeded requested bounded bytes')
                if not chunk:
                    if declared is not None and info['received_bytes'] != declared:
                        raise NotReady('TRUNCATED_BODY')
                    info['body_complete'] = True
                    break
                info['received_bytes'] += len(chunk)
                stream.write(chunk)
                digest.update(chunk)
            else:
                info['body_complete'] = True
    finally:
        if path.exists():
            owned = storage.import_file(path, path)
            info.update(body_path=str(path.relative_to(output)), sha256=owned['sha256'], retained_bytes=owned['bytes'])
            info['retained_hash_matches_read_chunks'] = owned['sha256'] == digest.hexdigest()
        info['capture_finished_utc'] = now()
        storage.atomic_json(output / f'private/http/{number:03d}/response.json', info)
    if info.get('retained_bytes') != info['received_bytes'] or not info.get('retained_hash_matches_read_chunks'):
        raise ValueError('retained/read accounting mismatch')
    return path, info


def project_and_audit(storage, output, path):
    # Only authenticated file bytes reach this function. No pandas/NFL loaders.
    import math
    import re
    from collections import Counter
    import pyarrow as pa
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    guard()
    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    present = [name for name in COLUMNS if name in schema.names]
    schema_info = {'file_rows_metadata': parquet.metadata.num_rows,
                   'row_groups_metadata': parquet.metadata.num_row_groups,
                   'all_field_names_metadata': schema.names,
                   'approved_present_types': {name: str(schema.field(name).type) for name in present},
                   'approved_missing_columns': [name for name in COLUMNS if name not in present]}
    storage.atomic_json(output / 'private/schema.json', schema_info)
    summary = {key: value for key, value in schema_info.items() if key != 'all_field_names_metadata'}
    if 'nflverse_game_id' not in present or 'play_id' not in present:
        return {'state': 'NOT_READY_REQUIRED_KEYS_MISSING', 'schema': summary, 'projected_rows': 0}
    game_type = schema.field('nflverse_game_id').type
    if pa.types.is_dictionary(game_type):
        game_type = game_type.value_type
    if not (pa.types.is_string(game_type) or pa.types.is_large_string(game_type)):
        return {'state': 'NOT_READY_GAME_FILTER_TYPE', 'schema': summary, 'projected_rows': 0}
    play_type = schema.field('play_id').type
    if not (pa.types.is_integer(play_type) or pa.types.is_floating(play_type)):
        return {'state': 'NOT_READY_PLAY_KEY_TYPE', 'schema': summary, 'projected_rows': 0}
    del parquet
    fragment_options = ds.ParquetFragmentScanOptions(pre_buffer=False)
    dataset = ds.dataset(path, format=ds.ParquetFileFormat(default_fragment_scan_options=fragment_options))
    predicate = ds.field('nflverse_game_id') == GAME
    # Count the exact predicate with only its game-key dependency before any
    # player-list output materialization; never over-read a final 512-row batch
    # past the registered 10,000-row projection cap.
    expected_rows = dataset.count_rows(filter=predicate, use_threads=False)
    if expected_rows > 10000:
        return {'state': 'NOT_READY_PROJECTED_ROW_CAP', 'schema': summary,
                'fixed_game_row_count': expected_rows, 'maximum_rows': 10000,
                'player_list_output_rows_materialized': 0}
    if expected_rows == 0:
        return {'state': 'NOT_READY_FIXED_GAME_ABSENT', 'schema': summary, 'projected_rows': 0}
    scanner = dataset.scanner(columns=present, filter=ds.field('nflverse_game_id') == GAME,
                              batch_size=512, use_threads=False, batch_readahead=1, fragment_readahead=1)
    batches, count = [], 0
    for batch in scanner.to_batches():
        guard()
        count += batch.num_rows
        if count > 10000:
            return {'state': 'NOT_READY_PROJECTED_ROW_CAP', 'schema': summary,
                    'projected_rows_before_limit': count - batch.num_rows, 'maximum_rows': 10000}
        if batch.num_rows:
            batches.append(batch)
    if not batches:
        return {'state': 'NOT_READY_FIXED_GAME_ABSENT', 'schema': summary, 'projected_rows': 0}
    if count != expected_rows:
        raise ValueError('exact predicate count changed during immutable projection')
    table = pa.Table.from_batches(batches).replace_schema_metadata({
        b'policy_sha256': POLICY_SHA.encode(), b'source_sha256': ASSET_SHA.encode(),
        b'evidence_lane': b'PRIVATE_RETROSPECTIVE_APPROVED_FIXED_GAME_PROJECTION'})
    if table.column_names != present or any(x not in COLUMNS for x in table.column_names):
        raise ValueError('unapproved projection column')
    guard()
    buffer = pa.BufferOutputStream()
    pq.write_table(table, buffer, compression='zstd', use_dictionary=True)
    encoded = buffer.getvalue().to_pybytes()
    storage.write_bytes(output / 'private/projected.parquet', encoded)
    owned_projection = {'sha256': hashlib.sha256(encoded).hexdigest(), 'bytes': len(encoded)}
    # Preregistered finite recognizers; no player-ID repair or delimiter guessing.
    # Strings: exact semicolon-separated canonical GSIS IDs or explicit JSON list.
    gsis = re.compile(r'^[0-9]{2}-[0-9]{7}$')

    def parse_list(value):
        if value is None:
            return None, 'MISSING'
        if isinstance(value, list):
            parsed, encoding = value, 'ARROW_LIST'
        elif isinstance(value, str) and value.startswith('['):
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                return None, 'UNSUPPORTED_ENCODING'
            encoding = 'EXPLICIT_JSON_ARRAY'
        elif isinstance(value, str) and value:
            parsed, encoding = value.split(';'), 'EXACT_SEMICOLON_IDS'
        elif value == '':
            return None, 'EMPTY_STRING_UNRESOLVED'
        else:
            return None, 'UNSUPPORTED_ENCODING'
        if not isinstance(parsed, list) or any(not isinstance(x, str) or not gsis.fullmatch(x) for x in parsed):
            return None, 'UNSUPPORTED_ENCODING_OR_NONCANONICAL_ID'
        return parsed, encoding

    fields = [x for x in ('players_on_play', 'offense_players', 'defense_players') if x in present]
    field_stats = {name: {'encoding_counts': Counter(), 'rows_with_supported_lists': 0,
                         'rows_with_missing_or_unresolved_lists': 0, 'duplicate_membership_rows': 0,
                         'membership_count': 0, 'unique_positive_witnesses': 0} for name in fields}
    witnesses = {name: set() for name in fields}
    keys = set()
    duplicate_keys = invalid_keys = wrong_game = unsupported = union_matches = union_comparable = 0
    count_checks = {name: {'compared_rows': 0, 'matched_rows': 0, 'missing_or_unresolved_rows': 0,
                           'invalid_count_rows': 0} for name in ('offense', 'defense')}
    for batch in table.to_batches(max_chunksize=512):
        guard()
        for row in batch.to_pylist():
            if row['nflverse_game_id'] != GAME:
                wrong_game += 1
            play = row['play_id']
            if (isinstance(play, bool) or not isinstance(play, (int, float))
                    or not math.isfinite(play) or play < 0 or play != int(play)):
                invalid_keys += 1
            else:
                key = (row['nflverse_game_id'], play)
                duplicate_keys += key in keys
                keys.add(key)
            parsed = {}
            for field in fields:
                values, encoding = parse_list(row[field])
                parsed[field] = values
                stats = field_stats[field]
                stats['encoding_counts'][encoding] += 1
                if values is None:
                    stats['rows_with_missing_or_unresolved_lists'] += 1
                    unsupported += encoding not in ('MISSING', 'EMPTY_STRING_UNRESOLVED')
                else:
                    stats['rows_with_supported_lists'] += 1
                    stats['membership_count'] += len(values)
                    stats['duplicate_membership_rows'] += len(set(values)) != len(values)
                    witnesses[field].update(values)
            if all(name in parsed and parsed[name] is not None for name in ('players_on_play', 'offense_players', 'defense_players')):
                union_comparable += 1
                union_matches += set(parsed['players_on_play']) == set(parsed['offense_players']) | set(parsed['defense_players'])
            for side in ('offense', 'defense'):
                stats = count_checks[side]
                values = parsed.get(side + '_players')
                value = row.get('n_' + side)
                if values is None or value is None:
                    stats['missing_or_unresolved_rows'] += 1
                elif (isinstance(value, bool) or not isinstance(value, (int, float))
                      or not math.isfinite(value) or value < 0 or value != int(value)):
                    stats['invalid_count_rows'] += 1
                else:
                    stats['compared_rows'] += 1
                    stats['matched_rows'] += len(values) == value
    for field, stats in field_stats.items():
        stats['encoding_counts'] = dict(stats['encoding_counts'])
        stats['unique_positive_witnesses'] = len(witnesses[field])
    any_positive = len(set().union(*witnesses.values())) if witnesses else 0
    inconsistent_counts = any(x['invalid_count_rows'] or x['compared_rows'] != x['matched_rows'] for x in count_checks.values())
    duplicate_memberships = any(x['duplicate_membership_rows'] for x in field_stats.values())
    union_discrepancy = union_comparable != union_matches
    ready = (bool(fields) and any_positive > 0 and not (unsupported or invalid_keys or duplicate_keys
             or wrong_game or inconsistent_counts or duplicate_memberships or union_discrepancy))
    return {'state': 'PROJECTED_POSITIVE_WITNESS_SCHEMA_AUDIT' if ready else 'NOT_READY_KEYS_OR_LIST_ENCODING',
            'schema': summary, 'projected_rows': count, 'projected_columns': present,
            'projection_sha256': owned_projection['sha256'], 'projection_bytes': owned_projection['bytes'],
            'game_predicate': GAME, 'predicate_before_output_batch_materialization': True,
            'maximum_output_batch_rows': 512, 'use_threads': False,
            'unique_game_play_keys': len(keys), 'duplicate_game_play_keys': duplicate_keys,
            'invalid_play_keys': invalid_keys, 'wrong_game_rows': wrong_game,
            'unsupported_list_rows_across_fields': unsupported, 'list_fields': field_stats,
            'unique_positive_witnesses_across_supported_fields': any_positive,
            'players_on_play_union_comparable_rows': union_comparable,
            'players_on_play_union_matching_rows': union_matches,
            'offense_defense_count_consistency': count_checks,
            'full_special_teams_game_coverage_or_DNP_established': False,
            'missing_statistics_filled_or_zeros_restored': 0}


def worker(args):
    resource.setrlimit(resource.RLIMIT_CPU, (52, 52))
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 48 - (time.monotonic() - START)))
    freeze, policy, source_policy = preflight(args)
    import requests
    from requests.adapters import HTTPAdapter
    from requests.auth import AuthBase
    from urllib.parse import urljoin

    class PublicAuth(AuthBase):
        def __call__(self, request):
            return request

    storage = storage_for(freeze, source_policy)
    output = Path(freeze['capture'])
    with storage._locked():
        storage._refresh()
        storage._scan()
        if output.exists():
            raise RuntimeError('pilot capture already consumed; no retry')
        storage.register_root(output)
        storage.atomic_json(output / 'PILOT_CONSUMED.json', {'policy_sha256': POLICY_SHA,
            'freeze_sha256': args.freeze_sha256, 'consumed_utc': now(), 'invocations': 1,
            'automatic_retries': 0, 'source_sha256': ASSET_SHA, 'fixed_game': GAME})
    attempted = received_total = 0
    succeeded = False
    transactions, visited, url = [], set(), URL
    try:
        while True:
            guard()
            if attempted >= 3:
                raise NotReady('HTTP_TRANSACTION_CAP')
            if url in visited or not approved_url(url):
                raise NotReady('REDIRECT_LOOP_OR_UNAPPROVED_HTTPS_HOST')
            visited.add(url)
            number = attempted + 1
            storage.atomic_json(output / f'private/http/{number:03d}/request-consumed.json', {
                'url': url, 'started_utc': now(), 'transaction': number, 'allow_redirects': False,
                'automatic_retries': 0, 'TLS_verify': True, 'accept_encoding': 'identity',
                'authentication': 'public no-op; suppress implicit netrc'})
            guard()
            attempted += 1
            with requests.Session() as session:
                session.mount('https://', HTTPAdapter(max_retries=0))
                with session.get(url, stream=True, allow_redirects=False, verify=True,
                                 auth=PublicAuth(), timeout=(5, 10), headers={
                                     'Accept-Encoding': 'identity',
                                     'User-Agent': 'NFLForecastingSourceQualification/1.0 (fixed FTN appearance pilot)'}) as response:
                    path, info = capture_response(storage, output, response, url, number, received_total)
            received_total += info['received_bytes']
            transactions.append(info)
            if info['status_code'] in (301, 302, 303, 307, 308):
                location = info['headers']['Location']
                if not location:
                    raise NotReady('REDIRECT_LOCATION_MISSING')
                url = urljoin(url, location)
                continue
            if info['status_code'] != 200 or not info['body_complete']:
                raise NotReady('FINAL_STATUS_OR_BODY_INCOMPLETE')
            if info['retained_bytes'] != ASSET_BYTES or info['sha256'] != ASSET_SHA:
                raise NotReady('ASSET_SIZE_OR_CATALOG_DIGEST_MISMATCH_NO_DECODE')
            source = {'sha256': info['sha256'], 'bytes': info['retained_bytes'],
                      'body_path': info['body_path'], 'authenticated_before_any_Parquet_decode': True}
            break
        guard()
        audit = project_and_audit(storage, output, path)
        result = {'registration_id': policy['registration_id'], 'policy_sha256': POLICY_SHA,
                  'freeze_sha256': args.freeze_sha256, 'source': source, 'audit': audit,
                  'HTTP_transactions_attempted': attempted, 'incoming_bytes_including_redirect_bodies': received_total,
                  'automatic_retries': 0, 'source_license': 'CC-BY-SA4.0; FTN Data via nflverse',
                  'document_commit_root_association': 'UNRESOLVED as previously disclosed',
                  'evidence_lane': 'RETROSPECTIVE_PRIVATE_APPEARANCE_SCHEMA_PILOT',
                  'not_historical_pregame_availability': True, 'original_upstream_publication_utc': None,
                  'no_names_statistics_outcomes_roster_join_models_scores': True,
                  'no_source_policy_or_existing_population_change': True,
                  'exact_PPR_or_complete_participation_panel_established': False,
                  'usage_before_result_write': child_usage(), 'finished_utc': now()}
        guard()
        storage.atomic_json(output / 'result.json', result)
        succeeded = True
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except BaseException as error:
        # Partial response receipts retain their own received/retained counts even
        # when a failing current transaction did not return to this accumulator.
        storage.atomic_json(output / 'PILOT_FAILURE.json', {'exception_type': type(error).__name__,
            'reason': str(error) if isinstance(error, NotReady) else 'TECHNICAL_FAILURE_NO_RETRY',
            'policy_sha256': POLICY_SHA, 'HTTP_transactions_attempted': attempted,
            'completed_transaction_incoming_bytes': received_total,
            'current_transaction_partial_accounting': 'see per-response receipt if created',
            'usage_before_failure_write': child_usage(), 'finished_utc': now(), 'automatic_retry': False})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        storage.atomic_json(output / 'PILOT_FINISHED.json', {'state': 'COMPLETED' if succeeded else 'FAILED',
            'HTTP_transactions_attempted': attempted, 'completed_transaction_incoming_bytes': received_total,
            'usage_before_finished_write': child_usage(), 'finished_utc': now()})
        print(json.dumps({'child_final_observed_usage': child_usage(),
                          'result_sha256': hashlib.sha256((output / 'result.json').read_bytes()).hexdigest() if succeeded else None}, sort_keys=True))


def tree_usage(pid):
    todo, seen, rss, cpu = [pid], set(), 0, 0.
    ticks = os.sysconf('SC_CLK_TCK')
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            status = Path(f'/proc/{current}/status').read_text()
            rss += next((int(line.split()[1]) * 1024 for line in status.splitlines() if line.startswith('VmRSS:')), 0)
            raw = Path(f'/proc/{current}/stat').read_text()
            fields = raw[raw.rfind(')') + 2:].split()
            cpu += (int(fields[11]) + int(fields[12])) / ticks
            for task in Path(f'/proc/{current}/task').iterdir():
                todo.extend(int(x) for x in (task / 'children').read_text().split())
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return rss, cpu


def supervisor(args):
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 59 - (time.monotonic() - START)))
    freeze, policy, source_policy = preflight(args)
    if Path(freeze['capture']).exists() or Path(freeze['supervisor']).exists():
        raise RuntimeError('pilot scope exists; no invocation retry')
    parent_pid = os.getpid()

    def orphan_guard():
        if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError('cannot establish orphan death signal')
        if os.getppid() != parent_pid:
            os.kill(os.getpid(), signal.SIGKILL)

    child, peak, stop = None, 0, None
    try:
        child = subprocess.Popen([sys.executable, __file__, '--freeze', str(args.freeze),
                                  '--freeze-sha256', args.freeze_sha256, '--worker'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=os.environ.copy(), preexec_fn=orphan_guard)
        while child.poll() is None:
            rss, cpu = tree_usage(os.getpid())
            peak = max(peak, rss)
            if rss > 268435456:
                stop = 'COMBINED_RSS_CAP'
            elif cpu >= 54:
                stop = 'COMBINED_CPU_RESERVE'
            elif time.monotonic() - START >= 53:
                stop = 'CHILD_WALL_RESERVE'
            if stop:
                child.kill()
                break
            time.sleep(.01)
        stdout, stderr = child.communicate(timeout=1)
        returncode = child.returncode
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=1)
    storage = storage_for(freeze, source_policy)  # Child is gone before pandas import.
    output = Path(freeze['supervisor'])
    if output.exists():
        raise RuntimeError('supervisor namespace exists; no retry')
    storage.register_root(output)
    peak = max(peak, tree_usage(os.getpid())[0])
    child_used = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {
        'policy_sha256': POLICY_SHA, 'freeze_sha256': args.freeze_sha256,
        'runner_sha256': freeze['runner']['sha256'], 'child_returncode': returncode,
        'stop_reason': stop, 'child_stdout_metadata': stdout.decode()[:20000],
        'child_stderr_failure': stderr.decode()[:5000], 'combined_RSS_peak_sampled_bytes': peak,
        'RSS_poll_seconds': .01, 'combined_CPU_seconds_before_receipt_write': time.process_time() + child_used.ru_utime + child_used.ru_stime,
        'wall_seconds_before_receipt_write': time.monotonic() - START,
        'independent_external_wall_seconds': 60, 'child_deadline_seconds': 48,
        'orphan_guard': 'PDEATHSIG SIGKILL', 'numerical_threads': 1,
        'asset_and_projection_counts': 'see child audit/transport receipts; authorized asset may be downloaded',
        'unapproved_names_statistics_outcomes_models_reads': 0, 'finished_utc': now()}
    if peak > 268435456 or receipt['combined_CPU_seconds_before_receipt_write'] >= 60 or receipt['wall_seconds_before_receipt_write'] >= 59:
        raise TimeoutError('finalization resource limit')
    storage.atomic_json(output / 'outer-receipt.json', receipt)
    print(stdout.decode(), end='')
    print(json.dumps({
        'outer_receipt_path': str(output / 'outer-receipt.json'),
        'outer_receipt_sha256': hashlib.sha256((output / 'outer-receipt.json').read_bytes()).hexdigest(),
        'child_returncode': returncode, 'stop_reason': stop,
        'owner_tool_observed_wall_seconds_after_receipt_write': time.monotonic() - START,
        'owner_tool_observed_combined_CPU_seconds_after_receipt_write': time.process_time() + child_used.ru_utime + child_used.ru_stime,
        'combined_RSS_peak_sampled_bytes': max(peak, tree_usage(os.getpid())[0]),
        'asset_and_projection_counts': 'see child audit/transport receipts',
        'unapproved_names_statistics_outcomes_models_reads': 0}, sort_keys=True))
    if stderr:
        print('Child failure retained privately; no retry')
    signal.setitimer(signal.ITIMER_REAL, 0)
    return 0 if returncode == 0 and stop is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--freeze-sha256', required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return 0
    return supervisor(args)


if __name__ == '__main__':
    raise SystemExit(main())
