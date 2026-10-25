"""Private original-895 R0 execution and exact control bridge; zero lab fits.

The parent authenticates metadata, public Git staging, job authority, previous
state and final remote checkpoint. Local CAS/hash bindings do not grant those
authorities. No import acquires sources or opens cached outcome/model bodies.
"""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

from .state import canonical, digest, now_utc, utc
from .owned_reference_batch import validate_owned_references
from .operational_storage import OperationalStorage
from . import weekly_adaptive as selector

VERSION = 'audit-reference-capture-v1'
SOURCE = '89512ed952308dacc1f6a930915ddbcdccd460d9'
ORIGINAL_MODEL = 'original_sleeper_matchup_baseline'
PROCEDURE = 'original-builder-default-refresh-v1'
R0_IDENTITY = 'a21ccd21ad395da3487c5e084ab2865c54a357a191419cc4da9ce31c19f83660'
ROOT = Path(__file__).resolve().parents[1]
LIMITS = dict(wall_seconds=600, CPU_seconds=300, address_space_bytes=4 << 30,
    requests=512, source_bytes=256 << 20, response_bytes=32 << 20,
    state_bytes=256 << 20, state_files=5000, native_bytes=8 << 20, metadata_bytes=8 << 20,
    native_decoded_bytes=32 << 20, log_bytes=256 << 10, offers=12000, bridge_rows=1000, fits=0)
ENGINE = {
    'pull/build.py': '75bf99c55b5f2561a60a120c82db368ad3b996a8a64e9ab08828b586a9314419',
    'pull/scoring.py': '31672c10d526d591db8951157b0ecd669b4d02b412a75deec337618bff18dab2',
    'pull/matchup.py': '15b1739b203e1757b0ebaefa3a6994034d56bb4a92a9e07572527ef1a90e914c',
    'pull/books.py': '0b89744960136a4f2e594b61e6df754d357706d8c66a8ae359d8eb02bbfa53f8',
    'pull/gamemodel.py': '2a2519a12ad4993da02ae6bdcdb6c86f2b5a6554ce93a702b550ecde17fb7d1f',
    'pull/sources.py': '36555cdbc55d73ba632d5adae1130288f4f532073857c642ac3ebc7e626b0061',
    'pull/news.py': '17ce1b3b6b72694e6b543bd767e287c26a9d1f6dd5dba2de6c873543036842e9'}
ENGINE_BLOBS = {'pull/build.py':'e691985174387ed0dc6ecdda1f35b55c1012499c',
    'pull/matchup.py':'3753d8e252513785dd1b9cf573f7d2616462945e',
    'pull/scoring.py':'0c532e695e7abefc2203f95344218ffc07bb4c0f',
    'pull/books.py':'406c24755aa9823311c01e3116662845854cf393',
    'pull/gamemodel.py':'9c94d3889402c702e6a7ad1d239ea8f4d22b2cdf',
    'pull/sources.py':'99b9029acf9a046a590589f001d99b242cc5576f',
    'pull/news.py':'b29edaa0cfe1df29c3ee4741d63225ab43fa8249'}
SOURCE_FILES = dict(ENGINE, **{'pull/grade.py': 'ca16cd918d3a17a4a5c34be79f22aaaee7ae7babf2ddfb1a45e7fc17f521f105',
    'tools/reliability.py': 'cac8e91d80225f99f03d82bb48bacb287bf4b41f9b3d94a13c9b7571930acc38'})
TEAM_ALIASES = {'WSH': 'WAS', 'LA': 'LAR', 'SD': 'LAC', 'OAK': 'LV'}
COUNTS = {'pass_td', 'pass_cmp', 'pass_att', 'pass_int', 'rush_att', 'rec'}
TARGETS = COUNTS | {'pass_yd', 'rush_yd', 'rec_yd', 'rush_rec_yd', 'anytime_td'}
HOSTS = {'api.sleeper.app', 'site.api.espn.com', 'sports.core.api.espn.com'}


class ReferenceError(ValueError):
    pass


def require(value, code):
    if not value:
        raise ReferenceError(code)


def failure_diagnostic(error, *, stage=None):
    """Closed reason/type and public code locations, never exception values."""
    kind = type(error).__name__
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', kind): kind = 'Exception'
    reason = str(error) if isinstance(error, ReferenceError) else 'ORIGINAL_REFERENCE_WORKER_EXCEPTION'
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', reason): reason = 'ORIGINAL_REFERENCE_WORKER_EXCEPTION'
    frames = []; trace = error.__traceback__
    while trace is not None:
        path = Path(trace.tb_frame.f_code.co_filename).resolve(); name = None
        if path.is_relative_to(ROOT):
            relative = path.relative_to(ROOT)
            if relative.parts[0] in {'nfl_lab', 'tools'} and relative.suffix == '.py': name = relative.as_posix()
        if stage is not None and path.is_relative_to(Path(stage).resolve()):
            relative = path.relative_to(Path(stage).resolve()).as_posix()
            if relative in SOURCE_FILES: name = 'original/' + relative
        if name is not None: frames.append(dict(file=name, line=trace.tb_lineno))
        trace = trace.tb_next
    return dict(reason=reason, error_type=kind, source_frames=frames[-5:])


def sha(raw): return hashlib.sha256(raw).hexdigest()
def stamp(): return datetime.now(timezone.utc).isoformat()
def finite(v): return type(v) in (int, float) and math.isfinite(v)
def hashed(v): return type(v) is str and re.fullmatch('[a-f0-9]{64}', v) is not None
def team(v): return TEAM_ALIASES.get(v, v)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'DUPLICATE_REFERENCE_JSON_KEY'); result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ReferenceError('NONFINITE_REFERENCE_JSON')))


def binding(path):
    path = Path(path).absolute()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path.read_bytes()))


def read_owned(storage, ref, *, raw=False):
    require(type(ref) is dict and set(ref) == {'path', 'bytes', 'sha256'} and type(ref['bytes']) is int
        and 0 <= ref['bytes'] <= LIMITS['metadata_bytes'] and hashed(ref['sha256']), 'BOUNDED_OWNED_REFERENCE_REQUIRED')
    validate_owned_references(storage, {ref['path']: ref['sha256']})
    body = Path(ref['path']).read_bytes()
    require(len(body) == ref['bytes'] and sha(body) == ref['sha256'], 'OWNED_REFERENCE_CHANGED')
    return body if raw else decode(body)


def write(storage, path, value):
    body = canonical(value); require(len(body) <= LIMITS['metadata_bytes'], 'REFERENCE_METADATA_BOUND')
    storage.write_bytes(path, body)
    return binding(path)


def source_pins():
    return {name: sha((ROOT / name).read_bytes()) for name in
        ('nfl_lab/audit_reference_capture_v1.py', 'tools/audit_reference_capture_v1.py', 'tools/audit_process_guard_v1.py', 'config/website-baseline-v1.json')}


def control_spec():
    """Register this exact observed control before current values; no fit clock."""
    policy = decode((ROOT / 'config/website-baseline-v1.json').read_bytes())
    require(policy['repo'] == 'NickNicky19/nicks-expert-nfl-picks' and policy['raw_redistribution'] is False
        and policy['engine_blobs'] == ENGINE_BLOBS, 'PRESERVED_ORIGINAL_BASELINE_POLICY_REQUIRED')
    definition = dict(schema_version=VERSION + '-original-definition', source=SOURCE, model=ORIGINAL_MODEL,
        procedure=PROCEDURE, source_files=SOURCE_FILES, frozen_R0_identity_sha256=R0_IDENTITY,
        original_baseline_policy_sha256=digest(policy), td_source_units='td_chance:FRACTION_0_1; not expected TD count')
    model_version = digest(definition)
    policy_sha = digest(dict(definition=definition, code_pins=source_pins(), limits=LIMITS, team_aliases=TEAM_ALIASES))
    return dict(procedure_version=digest(dict(schema_version=VERSION + '-control-procedure', policy_sha256=policy_sha)),
        model_versions=[model_version], procedure_operational_eligible=True, procedure_replay_eligible=False,
        role='reference', training_state='UPSTREAM_TRAINING_UNOBSERVED', control_policy_sha256=policy_sha,
        control_source_version='website895-original-default-refresh-v1', event_contract=selector.ANYTIME_EVENT_CONTRACT)


def _git(repository, *args):
    # No lock, replacement objects, lazy fetch, remote access or Git writes.
    return subprocess.check_output(['git', '--no-replace-objects', '-c', 'remote.origin.promisor=false', '-C', str(repository), *args],
        env={'PATH': os.environ.get('PATH', os.defpath), 'LANG': 'C.UTF-8', 'GIT_OPTIONAL_LOCKS': '0',
             'GIT_NO_LAZY_FETCH': '1', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}, timeout=30)


def original_sources(repository):
    result = {}
    for name, expected in SOURCE_FILES.items():
        oid = _git(repository, 'rev-parse', SOURCE + ':' + name).decode().strip()
        raw = _git(repository, 'cat-file', 'blob', oid)
        require(len(raw) <= 2 << 20 and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid
            and sha(raw) == expected, 'EXACT_ORIGINAL_895_PUBLIC_SOURCE_REQUIRED')
        result[name] = raw
    return result


def _state_name(name):
    path = PurePosixPath(name)
    return (type(name) is str and path.as_posix() == name and not path.is_absolute() and '..' not in path.parts
        and name.startswith(('data/cache/', 'output/data/')) and 'stat-keys-fgm-v1' not in path.parts)


def _bootstrap(storage, stage, repository):
    """Only actual GHA uses original data objects. Tests substitute fictional data."""
    entries = _git(repository, 'ls-tree', '-r', '-l', '-z', SOURCE, '--', 'data/cache', 'output/data').split(b'\0')
    selected = []; total = 0
    for entry in entries:
        if not entry: continue
        meta, name = entry.split(b'\t', 1); mode, kind, oid, size = meta.decode().split(); name = name.decode()
        total += int(size)
        require(mode == '100644' and kind == 'blob' and _state_name(name) and int(size) <= LIMITS['response_bytes']
            and total <= LIMITS['state_bytes'] and len(selected) < LIMITS['state_files'], 'ORIGINAL_BOOTSTRAP_STATE_BOUND')
        selected.append((name, oid, int(size)))
    require(selected, 'ORIGINAL_PUBLIC_BOOTSTRAP_OBJECTS_REQUIRED')
    for name, oid, size in selected:
        raw = _git(repository, 'cat-file', 'blob', oid)
        require(len(raw) == size and hashlib.sha1(b'blob ' + str(size).encode() + b'\0' + raw).hexdigest() == oid, 'BOOTSTRAP_OBJECT_CHANGED')
        storage.write_bytes(stage / name, raw)


def _permit(value, slate, control, now):
    if hasattr(value, 'document'):
        value.verify(); value = value.document
    keys = {'schema_version', 'epoch_sha256', 'choice_sha256', 'selected_versions_sha256', 'catalog_sha256',
        'metadata_completion_sha256', 'actual_capture_authorized_at', 'qualified_artifact_restore_proof_sha256',
        'metadata_cas_readback_sha256', 'metadata_remote_durability_qualified', 'captured_bundle_remote_durability_qualified',
        'game_cutoffs', 'fits', 'reselect'}
    require(type(value) is dict and set(value) == keys
        and value['schema_version'] == 'audit-weekly-correction-epoch-v1-capture-permit'
        and all(hashed(value[k]) for k in keys if k.endswith('_sha256'))
        and value['metadata_remote_durability_qualified'] is False and value['captured_bundle_remote_durability_qualified'] is False
        and type(value['fits']) is int and value['fits'] == 0 and value['reselect'] is False
        and value['game_cutoffs'] == slate['game_cutoffs'], 'COMPLETE_REGISTERED_SHARED_CUTOFF_PERMIT_REQUIRED')
    require(type(control) is dict and set(control) == set(control_spec()) | {'registered_at'}
        and {k: v for k, v in control.items() if k != 'registered_at'} == control_spec()
        and utc(control['registered_at']) < utc(value['actual_capture_authorized_at']) <= now
        < min(map(utc, slate['game_cutoffs'].values())), 'ACTUAL_R0_CONTROL_REGISTRATION_BEFORE_ACQUISITION_REQUIRED')
    return value


def _bridge(offers, bridge, slate):
    require(type(offers) is list and 0 < len(offers) <= LIMITS['offers'] and type(bridge) is list
        and 0 < len(bridge) <= LIMITS['bridge_rows'], 'BOUNDED_EXPLICIT_OFFER_AND_IDENTITY_CENSUS_REQUIRED')
    index = {}; sleepers = {}; games = {}; website_games = {}
    for item in bridge:
        require(type(item) is dict and set(item) == {'gsis_id','gsis_game_id','sleeper_id','website_player_id','website_game_id',
            'team','opponent','kickoff_utc','query_source_sha256','schedule_source_sha256','identity_bridge_kind',
            'actual_visible_board_compatibility','identity_binding_sha256'}
            and item['identity_bridge_kind'] == 'EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES'
            and hashed(item['query_source_sha256']) and hashed(item['schedule_source_sha256'])
            and digest({k: v for k, v in item.items() if k != 'identity_binding_sha256'}) == item['identity_binding_sha256']
            and type(item['gsis_id']) is str and re.fullmatch(r'[0-9]{2}-[0-9]{7}', item['gsis_id'])
            and item['sleeper_id'] == item['website_player_id'] and type(item['sleeper_id']) is str
            and re.fullmatch(r'[1-9][0-9]*', item['sleeper_id']) and type(item['website_game_id']) is str
            and re.fullmatch(r'[1-9][0-9]*', item['website_game_id']), 'EXACT_CANONICAL_GSIS_SLEEPER_ESPN_BRIDGE_REQUIRED')
        key = item['gsis_game_id'], item['gsis_id']
        require(key not in index and item['sleeper_id'] not in sleepers, 'DUPLICATE_OR_CONFLICTING_REFERENCE_IDENTITIES')
        require(games.get(key[0], item['website_game_id']) == item['website_game_id']
            and website_games.get(item['website_game_id'], key[0]) == key[0], 'AMBIGUOUS_REFERENCE_GAME_BRIDGE')
        index[key] = item; sleepers[item['sleeper_id']] = key
        games[key[0]] = item['website_game_id']; website_games[item['website_game_id']] = key[0]
    seen = set()
    for offer in offers:
        require(type(offer) is dict and set(offer) == {'offered_id','category','season','week','slate_id','horizon',
            'position','team','opponent','kickoff_utc','cutoff_utc','player_id','game_id'}, 'CLOSED_REFERENCE_OFFER_METADATA_REQUIRED')
        key = offer['game_id'], offer['player_id']; item = index.get(key)
        require(item is not None and offer['offered_id'] == selector.offered_id(offer) and offer['offered_id'] not in seen
            and offer['category'] in TARGETS and offer['horizon'] == 'player_game'
            and (offer['season'], offer['week'], offer['slate_id']) == (slate['season'], slate['week'], slate['slate_id'])
            and team(offer['team']) == team(item['team']) and team(offer['opponent']) == team(item['opponent'])
            and utc(offer['kickoff_utc']) == utc(item['kickoff_utc'])
            and offer['cutoff_utc'] == slate['game_cutoffs'][offer['game_id']]
            and utc(offer['cutoff_utc']) < utc(offer['kickoff_utc']), 'REFERENCE_OFFER_BRIDGE_OR_REGISTERED_CUTOFF_CONFLICT')
        seen.add(offer['offered_id'])
    require({o['game_id'] for o in offers} == set(slate['game_cutoffs']), 'NO_FUTURE_GAME_COVERAGE_CUT')
    return index


def prepare_reference(storage, output, *, repository, permit, slate, control, offers, bridge, previous_state=None,
        previous_state_aliases=None, clock=now_utc):
    """Owned metadata before R0 acquisition; parent authenticates all inputs."""
    now = utc(clock()); permit = _permit(permit, slate, control, now); _bridge(offers, bridge, slate)
    require(type(slate['season']) is int and 2000 <= slate['season'] <= 2200 and type(slate['week']) is int
        and 1 <= slate['week'] <= 18 and slate['season_type'] == 'REG', 'EXPLICIT_REFERENCE_REG_PERIOD_REQUIRED')
    sources = original_sources(repository)  # Code only; no cache/model/outcome bodies.
    output = Path(output).absolute(); require(not output.exists(), 'FRESH_REFERENCE_ATTEMPT_REQUIRED')
    output = storage.register_root(output)
    stage = storage.register_root(output / 'worker')
    for name, raw in sources.items(): storage.write_bytes(stage / name, raw)
    if previous_state is None:
        require(previous_state_aliases is None, 'RESTORED_CACHE_ALIASES_REQUIRE_ORIGINAL_STATE')
        _bootstrap(storage, stage, repository)
    else:
        previous = read_owned(storage, previous_state)
        require(previous['schema_version'] == VERSION + '-state' and previous['source'] == SOURCE
            and previous['procedure'] == PROCEDURE and previous['model'] == ORIGINAL_MODEL
            and previous['frozen_R0_identity_sha256'] == R0_IDENTITY and previous['source_files'] == SOURCE_FILES,
            'PRESERVED_ORIGINAL_R0_STATE_REQUIRED_NOT_CURRENT_BASELINE')
        files = previous['files']; require(type(files) is dict and 0 < len(files) <= LIMITS['state_files'], 'REFERENCE_STATE_FILE_BOUND')
        if previous_state_aliases is not None:
            require(type(previous_state_aliases) is dict and set(previous_state_aliases) == set(files)
                and all(type(v) is dict and set(v) == {'path','bytes','sha256'}
                    and v['bytes'] == files[name]['bytes'] and v['sha256'] == files[name]['sha256']
                    for name,v in previous_state_aliases.items()), 'COMPLETE_HASH_IDENTICAL_ORIGINAL_STATE_ALIASES_REQUIRED')
            files = previous_state_aliases
        require(sum(v['bytes'] for v in files.values()) <= LIMITS['state_bytes'], 'REFERENCE_STATE_BYTE_BOUND')
        owned, _ = validate_owned_references(storage, {v['path']: v['sha256'] for v in files.values()})
        require(all(type(v['bytes']) is int and v['bytes'] >= 0 and owned[v['path']]['bytes'] == v['bytes'] for v in files.values()),
            'ORIGINAL_STATE_PHYSICAL_BYTE_BINDING_CHANGED')
        for name, ref in files.items():
            require(_state_name(name), 'ORIGINAL_STATE_PATH_SCOPE')
            storage.import_file(ref['path'], stage / name, expected_sha256=ref['sha256'])
    board = stage / 'output/data/week.json'
    require(not board.exists() or decode(board.read_bytes()).get('execution_model') is None, 'CORRECTED_BASELINE_CANNOT_SEED_ORIGINAL_R0')
    document = dict(schema_version=VERSION + '-prepared', source=SOURCE, source_files=SOURCE_FILES,
        code_pins=source_pins(), limits=LIMITS, actual_prepared_at=now.isoformat(), output=str(output), worker=str(stage),
        permit=permit, slate=slate, control=control, offers=offers, bridge=bridge, previous_state=previous_state,
        previous_state_aliases=previous_state_aliases,
        frozen_R0_identity_sha256=R0_IDENTITY, bootstrap='PUBLIC_895_OBJECTS' if previous_state is None else 'PRIOR_OWNED_ORIGINAL_STATE',
        current_values_used=False, fits=0, metadata_remote_durability_qualified=False, public_release=False)
    return write(storage, output / 'PREPARED.json', document)


def _files(stage):
    result = {}; total = 0
    for lane in ('data/cache', 'output/data'):
        for path in sorted((stage / lane).rglob('*')):
            require(not path.is_symlink(), 'ORIGINAL_STATE_SYMLINK')
            if not path.is_file(): continue
            name = path.relative_to(stage).as_posix(); size = path.stat().st_size; total += size
            require(_state_name(name) and len(result) < LIMITS['state_files'] and total <= LIMITS['state_bytes']
                and size <= LIMITS['response_bytes'], 'ORIGINAL_STATE_BOUND_NO_TRUNCATION')
            result[name] = binding(path)
    require(result, 'ORIGINAL_STATE_FILES_REQUIRED')
    return result


class _Observations:
    """Cover all original Session aliases and redirects; no response-body copy."""
    def __init__(self, storage, root, cutoff):
        self.storage, self.root, self.cutoff = storage, root, utc(cutoff)
        self.lock = threading.RLock(); self.count = self.total = self.sends = 0; self.fatal = False; self.ends = []

    def check(self, method, url):
        parsed = urlsplit(url)
        valid = (str(method).upper() == 'GET' and parsed.scheme in {'http', 'https'}
            and parsed.hostname in HOSTS and not parsed.username and not parsed.password and not parsed.port
            and now_utc() < self.cutoff)
        if not valid:
            self.fatal = True; raise ReferenceError('ORIGINAL_PUBLIC_SOURCE_SCOPE_OR_CUTOFF')

    def __enter__(self):
        import requests
        self.cls = requests.sessions.Session
        self.original_request, self.original_send = self.cls.request, self.cls.send
        observer = self
        def send(session, request, **kwargs):
            observer.check(request.method, request.url)
            with observer.lock:
                observer.sends += 1
                if observer.sends > LIMITS['requests']:
                    observer.fatal = True; raise ReferenceError('ORIGINAL_WIRE_REQUEST_BOUND')
            return observer.original_send(session, request, **kwargs)
        def request(session, method, url, **kwargs):
            observer.check(method, url)
            with observer.lock:
                observer.count += 1; number = observer.count
                if number > LIMITS['requests']:
                    observer.fatal = True; raise ReferenceError('ORIGINAL_SOURCE_REQUEST_BOUND')
            started = stamp(); key = dict(method=str(method).upper(), url=url, params=kwargs.get('params'))
            write(observer.storage, observer.root / f'{number:04d}-BEGIN.json', dict(schema_version=VERSION+'-source-start',
                request_sha256=digest(key), host=urlsplit(url).hostname, started_at=started))
            record = dict(schema_version=VERSION+'-source-observation', request_sha256=digest(key),
                started_at=started, completed_at=None, status='FAILED', bytes=None, payload_sha256=None)
            try:
                response = observer.original_request(session, method, url, **kwargs)
                body = canonical(response.json())
                with observer.lock:
                    observer.total += len(body)
                    if len(body) > LIMITS['response_bytes'] or observer.total > LIMITS['source_bytes']:
                        observer.fatal = True; raise ReferenceError('ORIGINAL_SOURCE_BYTE_BOUND')
                record.update(status='OBSERVED' if 200 <= getattr(response, 'status_code', 200) < 300 else 'HTTP_ERROR',
                    bytes=len(body), payload_sha256=sha(body))
                observer.check(method, url)
                return response
            finally:
                record['completed_at'] = stamp()
                ref = write(observer.storage, observer.root / f'{number:04d}-END.json', record)
                with observer.lock: observer.ends.append(ref)
        self.cls.request, self.cls.send = request, send
        return self

    def __exit__(self, *args):
        self.cls.request, self.cls.send = self.original_request, self.original_send


class _Log(io.StringIO):
    def write(self, text):
        require(len(self.getvalue().encode()) + len(text.encode()) <= LIMITS['log_bytes'], 'PRIVATE_REFERENCE_LOG_BOUND')
        return super().write(text)


def worker(request_path, expected_sha256):
    """Internal isolated process: exact original builder, default refresh only."""
    request_path = Path(request_path)
    require(not request_path.is_symlink() and request_path.stat().st_size <= 64 << 10, 'BOUNDED_REFERENCE_WORKER_REQUEST')
    raw = request_path.read_bytes(); require(sha(raw) == expected_sha256, 'EXACT_REFERENCE_WORKER_REQUEST')
    request = decode(raw)
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['CPU_seconds'], LIMITS['CPU_seconds']))
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'], LIMITS['address_space_bytes']))
    storage = OperationalStorage(request['cache'], {'storage': {'version': 'operational-storage-v2', 'limit_bytes': request['limit_bytes']},
        'namespaces': {'private_retention_bytes': request['limit_bytes']}})
    read_owned(storage, binding(request_path))
    p = read_owned(storage, request['prepared']); output = Path(p['output']); stage = Path(p['worker'])
    require(p['code_pins'] == source_pins() and p['source_files'] == SOURCE_FILES and p['limits'] == LIMITS,
        'REFERENCE_WORKER_CODE_OR_LIMITS_CHANGED')
    for name, expected in SOURCE_FILES.items():
        require(sha((stage/name).read_bytes()) == expected, 'CORRECTED_OR_UNPINNED_CODE_CANNOT_RUN_AS_R0')
    _permit(p['permit'], p['slate'], p['control'], now_utc())
    sys.path[:0] = [str(stage/'pull'), str(stage/'tools')]
    os.environ['GITHUB_SHA'] = SOURCE
    import build
    import reliability
    hashes = reliability.engine_hashes(stage)
    require(hashes == ENGINE, 'ORIGINAL_NATIVE_ENGINE_IDENTITY_REQUIRED')
    cutoff = min(map(utc, p['slate']['game_cutoffs'].values()))
    log = _Log(); events = []; original_stats = build.week_stats
    def stats(season, week, refresh):
        events.append(dict(season=season, week=week, refresh=refresh,
            cache_hit=(build.CACHE/f'stats_{season}_{week:02d}.json').exists() and not refresh))
        return original_stats(season, week, refresh)
    build.week_stats = stats
    try:
        with _Observations(storage, output/'source-observations', cutoff) as observations:
            with redirect_stdout(log), redirect_stderr(log), storage.capture_writes([stage]):
                build.run()  # Exact deployed original default, never refresh_all=True.
            require(not observations.fatal and now_utc() < cutoff, 'REFERENCE_SOURCE_SCOPE_OR_CUTOFF_FAILED')
        source_finished = stamp()
        board = reliability.load_json(stage/'output/data/week.json'); meta = reliability.load_json(stage/'output/data/meta.json')
        require((board['season'], board['week']) == (p['slate']['season'], p['slate']['week'])
            and 'execution_model' not in board, 'ORIGINAL_CURRENT_PERIOD_REQUIRED_NOT_CORRECTED_BASELINE')
        observed = now_utc(); reliability.validate(board, meta, observed)
        payload = reliability.make_payload(board, observed, hashes, 'live')
        expected = gzip.compress(reliability.canonical(dict(payload=payload, payload_sha256=reliability.digest(payload))), mtime=0)
        require(len(expected) <= LIMITS['native_bytes'], 'FULL_ORIGINAL_NATIVE_BOUND_NO_ROW_TRUNCATION')
        # The old atomic serializer writes inside the registered private root.
        # Reserve its temporary/final native bytes before invoking it unchanged.
        with storage.transaction():
            storage._require(2 * len(expected) + (64 << 10))
            native, health = reliability.capture(board, meta, stage, observed, hashes, mode='live')
            require(native.read_bytes() == expected, 'FULL_ORIGINAL_NATIVE_BYTES_CHANGED')
            native_ref = storage.import_file(native, output/'native/original-native.json.gz', expected_sha256=sha(expected))
        native_persisted = stamp()
        write(storage, output/'PRIVATE_BUILDER_LOG.json', dict(schema_version=VERSION+'-private-log', text=log.getvalue(), public_release=False))
        files = _files(stage)
        validate_owned_references(storage, {v['path']:v['sha256'] for v in files.values()})
        state = dict(schema_version=VERSION+'-state', source=SOURCE, procedure=PROCEDURE, model=ORIGINAL_MODEL,
            frozen_R0_identity_sha256=R0_IDENTITY, source_files=SOURCE_FILES, files=files,
            previous_state=p['previous_state'], actual_completed_at=stamp(), native_sha256=sha(expected), fits=0, public_release=False)
        state_ref = write(storage, output/'ORIGINAL_R0_STATE.json', state)
        result = dict(schema_version=VERSION+'-worker', state='ORIGINAL_R0_DEFAULT_PROCEDURE_CAPTURED',
            native={k: native_ref[k] for k in ('path','bytes','sha256')}, board=binding(stage/'output/data/week.json'),
            meta=binding(stage/'output/data/meta.json'), next_state=state_ref, native_rows=len(payload['rows']),
            actual_source_completed_at=source_finished,
            actual_native_captured_at=payload['captured_at'], actual_completed_at=stamp(), source_requests=observations.count,
            actual_native_observed_at=observed.isoformat(),
            actual_native_persist_completed_at=native_persisted,
            source_wire_requests=observations.sends,
            observed_canonical_source_bytes=observations.total, source_observations=observations.ends, cache_events=events,
            upstream_publication_times='NOT_INFERRED',
            fixed_original_default_refresh=True, metadata_remote_durability_qualified=False, fits=0, public_release=False)
        write(storage, output/'WORKER_COMPLETE.json', result)
    except BaseException as error:
        write(storage, output/'WORKER_FAILED.json', dict(schema_version=VERSION, state='FAILED_PARTIAL_ORIGINAL_R0_RETAINED',
            actual_failed_at=stamp(), successful_forecast=False, fits=0, public_release=False,
            diagnostic=failure_diagnostic(error, stage=stage)))
        raise
    finally:
        build.week_stats = original_stats


def bridge_control_rows(p, board, native_raw, source_receipt_sha256, source_completed_at, native_observed_at, issued_at):
    """Pure identity bridge. No fitting, replacement values or false medians."""
    index = _bridge(p['offers'], p['bridge'], p['slate'])
    require(len(native_raw) <= LIMITS['native_bytes'], 'FULL_ORIGINAL_NATIVE_BOUND')
    with gzip.GzipFile(fileobj=io.BytesIO(native_raw), mode='rb') as stream:
        decoded = stream.read(LIMITS['native_decoded_bytes'] + 1)
    require(len(decoded) <= LIMITS['native_decoded_bytes'], 'NATIVE_DECODED_BOUND')
    envelope = decode(decoded); payload = envelope['payload']
    require(envelope['payload_sha256'] == digest(payload) and payload['schema_version'] == 'baseline-capture-v1'
        and payload['model'] == ORIGINAL_MODEL and payload['engine_files'] == ENGINE and payload['engine_sha256'] == digest(ENGINE)
        and payload['code_commit'] == SOURCE and payload['mode'] == 'live' and payload['input_sha256'] == digest(board)
        and 'execution_model' not in board and (board['season'], board['week']) == (p['slate']['season'], p['slate']['week']),
        'EXACT_ORIGINAL_NATIVE_BOARD_PAIR_REQUIRED')
    native = {}; players = {}; games = {}
    for g in board['games']:
        require(g['id'] not in games, 'DUPLICATE_ORIGINAL_GAME'); games[g['id']] = g
    for player in board['players']:
        require(player['id'] not in players, 'DUPLICATE_ORIGINAL_PLAYER'); players[player['id']] = player
    for row in payload['rows']:
        key = row['game_id'], row['player_id'], row['category']
        require(key not in native, 'DUPLICATE_ORIGINAL_NATIVE_OPPORTUNITY'); native[key] = row
    require(utc(p['permit']['actual_capture_authorized_at']) <= utc(source_completed_at) <= utc(native_observed_at)
        <= utc(issued_at) < min(map(utc,p['slate']['game_cutoffs'].values()))
        and 0 <= (utc(native_observed_at)-utc(payload['captured_at'])).total_seconds() < 1,
        'HONEST_REFERENCE_CAPTURE_AND_ISSUANCE_CLOCKS_REQUIRED')
    result = []; unavailable = []
    for offer in p['offers']:
        item = index[offer['game_id'], offer['player_id']]; sid, gid = item['sleeper_id'], item['website_game_id']
        row = native.get((gid,sid,offer['category'])); player = players.get(sid); reason = None; value = None
        if player is None:
            reason = 'ORIGINAL_R0_PLAYER_UNAVAILABLE'
        else:
            game = games.get(player['game_id'])
            require(player['game_id'] == gid and game is not None and team(player['team']) == team(item['team'])
                and utc(game['kickoff']) == utc(item['kickoff_utc'])
                and {team(game['home']), team(game['away'])} == {team(item['team']), team(item['opponent'])},
                'ORIGINAL_R0_EXACT_IDENTITY_CONFLICT_NO_FUZZY_MATCH')
            # The separately acquired R0 roster can disagree with the frozen
            # query's role. Preserve that opportunity as unavailable; never
            # relabel a WR prediction as an RB control or invent zero. Other
            # exact identities remain usable under their unchanged procedure.
            if player['pos'] != offer['position']:
                reason = 'ORIGINAL_R0_POSITION_CONFLICT_UNAVAILABLE'
            elif row is None or game['state'] != 'pre' or player.get('late'):
                reason = 'ORIGINAL_R0_OPPORTUNITY_UNAVAILABLE'
            elif offer['category'] == 'anytime_td':
                props = [prop for prop in player['props'] if prop['key'] == 'anytime_td']
                require(len(props) == 1, 'ORIGINAL_TD_PROP_IDENTITY')
                prop = props[0]
                # 895 stores a fraction, not the display percent. Native raw
                # TD projection is an expected count and is never substituted.
                if (finite(prop.get('proj')) and prop['proj'] >= 0 and finite(prop.get('td_chance'))
                    and 0 <= prop['td_chance'] <= 1 and row['raw_projection'] == prop['proj']):
                    value = prop['td_chance']
                else: reason = 'SAVED_ORIGINAL_TD_EVENT_PROBABILITY_UNAVAILABLE'
            elif finite(row['adjusted_projection']) and (offer['category'] not in COUNTS or row['adjusted_projection'] >= 0):
                value = row['adjusted_projection']
            else: reason = 'ORIGINAL_R0_VALUE_UNAVAILABLE'
        binary = offer['category'] == 'anytime_td'
        control = dict(offer, method_id='R0', procedure_version=p['control']['procedure_version'],
            model_version=p['control']['model_versions'][0], forecast_value=value,
            product='binary_probability' if binary else 'point_legacy', prediction_functional='event_probability' if binary else 'legacy_unknown',
            evidence_lane='original_pregame', reference_stream='live_R0', operational_eligible=value is not None,
            training_state='UPSTREAM_TRAINING_UNOBSERVED', control_policy_sha256=p['control']['control_policy_sha256'],
            control_source_version=p['control']['control_source_version'], source_receipt_sha256=source_receipt_sha256,
            source_capture_completed_at=source_completed_at, issued_at=issued_at, correction_epoch_sha256=p['permit']['epoch_sha256'],
            saved_event_probability=binary and value is not None, event_contract=selector.ANYTIME_EVENT_CONTRACT if binary else None,
            original_native_sha256=sha(native_raw), original_native_captured_at=payload['captured_at'],
            actual_reference_observed_at=native_observed_at,
            original_board_payload_sha256=digest(board),
            observed_value_field='original_board.td_chance' if binary else 'original_native.adjusted_projection',
            original_probability_units='fraction_0_1' if binary else None,
            original_R0_identity_sha256=R0_IDENTITY, original_source=SOURCE, original_procedure=PROCEDURE,
            identity_binding_sha256=item['identity_binding_sha256'], fits=0, public_release=False,
            state='CAPTURED' if value is not None else 'UNAVAILABLE', unavailable_reason=reason)
        result.append(control)
        if reason: unavailable.append(dict(offered_id=offer['offered_id'], reason=reason))
    require(len(result) == len(p['offers']), 'REFERENCE_CENSUS_NO_DROPPED_HARD_ROWS')
    return result, unavailable


def capture_reference(storage, prepared_ref):
    """One isolated attempt; owned state survives, parent handles remote proof."""
    p = read_owned(storage, prepared_ref); output = Path(p['output'])
    require(p['schema_version'] == VERSION+'-prepared' and p['code_pins'] == source_pins() and p['limits'] == LIMITS,
        'EXACT_PREPARED_REFERENCE_SOURCE_REQUIRED')
    _permit(p['permit'], p['slate'], p['control'], now_utc())
    require(not (output/'CONSUMED.json').exists(), 'REFERENCE_ATTEMPT_ALREADY_CONSUMED_NO_RETRY')
    write(storage, output/'CONSUMED.json', dict(schema_version=VERSION, actual_started_at=stamp(), fits=0))
    request = write(storage, output/'WORKER_REQUEST.json', dict(schema_version=VERSION+'-worker-request',
        prepared=prepared_ref, cache=str(storage.cache), limit_bytes=storage.limit_bytes))
    seconds = min(LIMITS['wall_seconds'], (min(map(utc,p['slate']['game_cutoffs'].values()))-now_utc()).total_seconds())
    require(seconds > 0, 'REFERENCE_CUTOFF_ELAPSED')
    try:
        # This worker runs only public fixed-source code. Do not forward store
        # or optional-service credentials; filtering names never reads them.
        def allowed_env(key):
            return key not in {'GITHUB_TOKEN','GH_TOKEN','ODDS_API_KEY'} and not key.startswith('AWS_') and not key.endswith(('_TOKEN','_SECRET','_API_KEY'))
        child_env={key:os.environ[key] for key in os.environ if allowed_env(key)}
        child_env['AUDIT_WEEKLY_PARENT_PID']=str(os.getpid())
        process = subprocess.run([sys.executable,'-B',str(ROOT/'tools/audit_reference_capture_v1.py'),
            '--worker',request['path'],'--worker-sha256',request['sha256']], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=seconds, check=False, env=child_env)
        # Keep actual returned pipe bytes before interpreting success/failure.
        # These private files are never printed or included in public exports.
        # An over-cap pipe remains an explicit unqualified failure, not a
        # truncated diagnostic presented as complete original evidence.
        pipes = {}
        for name, body in (('stdout', process.stdout), ('stderr', process.stderr)):
            require(type(body) is bytes and len(body) <= LIMITS['log_bytes'], 'ORIGINAL_REFERENCE_WORKER_PIPE_BOUND')
            storage.write_bytes(output/('WORKER.'+name), body)
            pipes[name] = binding(output/('WORKER.'+name))
        write(storage, output/'WORKER_EXIT.json', dict(schema_version=VERSION+'-worker-exit',
            exit_code=process.returncode, actual_observed_at=stamp(), **pipes,
            successful_forecast=False, fits=0, public_release=False))
        if process.returncode:
            reason = 'ISOLATED_ORIGINAL_R0_WORKER_FAILED'
            failed = output/'WORKER_FAILED.json'
            if failed.is_file():
                status = read_owned(storage, binding(failed)); diagnostic = status.get('diagnostic', {})
                code = diagnostic.get('reason')
                if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code): reason = code
            raise ReferenceError(reason)
        result = read_owned(storage, binding(output/'WORKER_COMPLETE.json'))
        board = read_owned(storage, result['board']); native = read_owned(storage, result['native'], raw=True)
        issued = stamp()
        rows, unavailable = bridge_control_rows(p, board, native, digest(result), result['actual_source_completed_at'],
            result['actual_native_observed_at'], issued)
        forecasts = write(storage, output/'R0_CONTROL_FORECAST_ROWS.json', dict(schema_version=VERSION+'-controls',
            rows=rows, unavailable=unavailable, offered_rows=len(p['offers']), available_rows=len(rows)-len(unavailable),
            actual_issued_at=issued, fits=0, public_release=False))
        persisted = stamp()
        require(utc(persisted) < min(map(utc,p['slate']['game_cutoffs'].values())),
            'REFERENCE_CONTROL_PERSISTENCE_MISSED_CUTOFF')
        completion = write(storage, output/'R0_CONTROL_COMPLETION.json', dict(schema_version=VERSION+'-control-completion',
            forecast_binding=forecasts, actual_issued_at=issued, body_persist_completed_at=persisted,
            source_receipt_sha256=digest(result), original_native_persist_completed_at=result['actual_native_persist_completed_at'],
            remote_durability_qualified=False, fits=0, public_release=False))
        return write(storage, output/'CAPTURE_COMPLETE.json', dict(schema_version=VERSION+'-capture',
            state='ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE', prepared=prepared_ref, native=result['native'],
            original_board=result['board'], next_state=result['next_state'], control_forecast_rows=forecasts,
            control_completion=completion,
            available_rows=len(rows)-len(unavailable), unavailable_rows=len(unavailable), original_native_rows=result['native_rows'],
            actual_completed_at=stamp(), fixed_original_default_refresh=True, fits=0, new_scheduler=False,
            actual_actions_api_authenticated=False, remote_durability_qualified=False, public_release=False))
    except BaseException:
        write(storage, output/'CAPTURE_FAILED.json', dict(schema_version=VERSION, state='FAILED_PRIVATE_REFERENCE_ATTEMPT_RETAINED',
            actual_failed_at=stamp(), successful_forecast=False, fits=0, public_release=False))
        raise
