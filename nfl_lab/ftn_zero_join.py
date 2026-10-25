"""Bounded candidate-zero audit, gated on a frozen forecast/query manifest.

No acquisition, fitting, scoring, label replacement or accepted-data writes.
The pure function accepts already projected frames; run_join is the thin local
reader/writer for a separately registered, fully bound future invocation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import re
import stat
import sys
import time

import numpy as np
import pandas as pd

from .operational_storage import OperationalStorage, _no_symlinks
from .owned_reference_batch import validate_owned_references

VERSION = 'ftn-explicit-zero-join-v1'
GAME = '2024_01_BAL_KC'
QUERY_RELATIVE = 'private/queries/2024.parquet'
GSIS = re.compile(r'^[0-9]{2}-[0-9]{7}$')
CONTEXT = ['game_id', 'season', 'week', 'season_type', 'player_id', 'team', 'opponent_team', 'position']
PRIMITIVES = ['passing_yards', 'passing_tds', 'completions', 'attempts', 'passing_interceptions',
              'rushing_yards', 'carries', 'receptions', 'receiving_yards', 'rushing_tds', 'receiving_tds']
RAW_COLUMNS = CONTEXT + PRIMITIVES
QUERY_COLUMNS = ['season', 'week', 'game_id', 'player_id', 'position', 'team', 'opponent']
HISTORY_COLUMNS = QUERY_COLUMNS + ['official_physical_event', 'participation_state', 'participation_evidence']
APPEARANCE_COLUMNS = ['nflverse_game_id', 'play_id', 'players_on_play', 'offense_players',
                      'defense_players', 'n_offense', 'n_defense']
TARGETS = {
    'pass_yd': (['passing_yards'], ['QB'], 'signed'),
    'pass_td': (['passing_tds'], ['QB'], 'count'),
    'pass_cmp': (['completions'], ['QB'], 'count'),
    'pass_att': (['attempts'], ['QB'], 'count'),
    'pass_int': (['passing_interceptions'], ['QB'], 'count'),
    'rush_yd': (['rushing_yards'], ['RB'], 'signed'),
    'rush_att': (['carries'], ['RB'], 'count'),
    'rec': (['receptions'], ['RB', 'WR', 'TE'], 'count'),
    'rec_yd': (['receiving_yards'], ['RB', 'WR', 'TE'], 'signed'),
    'rush_rec_yd': (['rushing_yards', 'receiving_yards'], ['RB', 'WR', 'TE'], 'sum'),
    'anytime_td': (['rushing_tds', 'receiving_tds'], ['RB', 'WR', 'TE'], 'binary'),
    'fantasy_ppr': ([], ['RB', 'WR', 'TE'], 'blocked'),
}
BUDGETS = {'invocations': 1, 'HTTP': 0, 'automatic_retries': 0, 'wall_seconds': 60,
           'CPU_seconds': 60, 'combined_RSS_bytes': 268435456, 'numerical_threads': 1,
           'raw_rows': 200, 'union_players': 200, 'new_retained_bytes': 4194304}
PINNED = {'source_manifest': '582f34f9c53c98c07a103ca3176f1d08333cb6351cd93cadcfbaf20a67e420d7',
          'raw_statistics': '847569d194ca3d96b5efcf91e6eac5e18780fc47568a713fd545a82d29d155c1',
          'appearance_projection': '4b5946f063050df232973b387c6ef0e61c536a32bc03a35c016a8a3f8de492c0',
          'accepted_metadata': '375dc79b4427db68504553736006af799ef98de880bd69ccb6f95285780a605f',
          'source_policy': 'e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441'}
CODE_FILES = ['nfl_lab/ftn_zero_join.py', 'nfl_lab/operational_storage.py', 'nfl_lab/owned_reference_batch.py']


class JoinNotReady(ValueError):
    """A binding/schema/coverage gate failed; never apply a partial repair."""


def _columns(frame, expected, limit):
    if not isinstance(frame, pd.DataFrame) or frame.columns.duplicated().any() or set(frame.columns) != set(expected):
        raise JoinNotReady('exact approved column schema required')
    if len(frame) > limit:
        raise JoinNotReady('projected row cap')


def _ids(frame):
    values = frame.player_id.tolist()
    if any(not isinstance(x, str) or GSIS.fullmatch(x) is None for x in values):
        raise JoinNotReady('missing/noncanonical identity; no identity repair')
    return set(values)


def _context(frame, raw=False):
    required = ['game_id', 'season', 'week', 'player_id', 'team', 'opponent_team' if raw else 'opponent']
    if raw:
        required.append('season_type')
    if (frame[required].isna().any().any() or not frame.game_id.eq(GAME).all() or not frame.season.eq(2024).all()
            or not frame.week.eq(1).all() or (raw and not frame.season_type.eq('REG').all())):
        raise JoinNotReady('fixed-game context mismatch')
    opponent = 'opponent_team' if raw else 'opponent'
    if not frame.team.isin(['BAL', 'KC']).all() or not frame[opponent].eq(frame.team.map({'BAL': 'KC', 'KC': 'BAL'})).all():
        raise JoinNotReady('fixed-game team/opponent mismatch')
    _ids(frame)


def _list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value) if value.startswith('[') else value.split(';')
        except ValueError as error:
            raise JoinNotReady('unsupported list encoding') from error
    if not isinstance(value, list) or any(not isinstance(x, str) or GSIS.fullmatch(x) is None for x in value):
        raise JoinNotReady('missing/unsupported on-field list; no guessed encoding')
    if len(value) != len(set(value)):
        raise JoinNotReady('duplicate on-field membership')
    return set(value)


def _witnesses(frame):
    _columns(frame, APPEARANCE_COLUMNS, 10000)
    if not frame.nflverse_game_id.eq(GAME).all() or frame.duplicated(['nflverse_game_id', 'play_id']).any():
        raise JoinNotReady('appearance game/key mismatch')
    witnesses = set()
    for row in frame.to_dict('records'):
        play = row['play_id']
        if not _number(play) or play < 0 or play != int(play):
            raise JoinNotReady('invalid appearance play key')
        all_players, offense, defense = (_list(row[x]) for x in ('players_on_play', 'offense_players', 'defense_players'))
        if all_players != offense | defense:
            raise JoinNotReady('on-field union mismatch')
        for field, players in (('n_offense', offense), ('n_defense', defense)):
            count = row[field]
            if not _number(count) or count < 0 or count != int(count) or count != len(players):
                raise JoinNotReady('on-field count mismatch')
        witnesses.update(all_players)
    return witnesses


def _number(value):
    return (not isinstance(value, (bool, np.bool_)) and isinstance(value, (int, float, np.integer, np.floating))
            and math.isfinite(value))


def _target(row, fields, kind):
    if kind == 'blocked':
        return 'BLOCKED_EXACT_PPR', False, ''
    if row is None:
        return 'NO_RAW_STAT_ROW', False, ''
    values = [row[name] for name in fields]
    if any(pd.isna(x) for x in values):
        return 'MISSING_COMPONENT', False, ''
    if any(not _number(x) or (kind in ('count', 'binary') and (x < 0 or x != int(x))) for x in values):
        return 'INVALID_COMPONENT', False, ''
    value = (sum(values) > 0) if kind == 'binary' else sum(values)
    zero = value == 0
    if kind in ('sum', 'binary'):
        reason = 'BOTH_COMPONENTS_ZERO' if all(x == 0 for x in values) else 'SIGNED_CANCELLATION'
        return ('KNOWN_DERIVED_ZERO' if zero else 'KNOWN_DERIVED_NONZERO'), zero, reason if zero else ''
    return ('EXPLICIT_RAW_ZERO' if zero else 'KNOWN_NONZERO'), zero, 'DIRECT_RAW_ZERO' if zero else ''


def _old_support(row):
    if row is None or not isinstance(row['official_physical_event'], (bool, np.bool_)):
        return 'UNRESOLVED'
    if not all(isinstance(row[x], str) for x in ('participation_state', 'participation_evidence')):
        return 'UNRESOLVED'
    if (bool(row['official_physical_event']) and row['participation_state'] == 'played'
            and row['participation_evidence'] == 'positive_official_nfl_physical_event'):
        return 'ALREADY_PLAYED'
    if (not bool(row['official_physical_event']) and row['participation_state'] == 'unknown'
            and row['participation_evidence'] == 'no_game_specific_participation_contract'):
        return 'OLD_UNKNOWN'
    return 'UNRESOLVED'


def _audit_zero_candidates(raw, appearance, accepted, query, *, expected_witnesses=None):
    """Return private per-player/target records and aggregate counts. Inputs unchanged.

    Every valid raw, witness and offered identity enters the outer union. Ambiguous
    raw rows are retained in row coverage and quarantined; none is selected.
    """
    _columns(raw, RAW_COLUMNS, 200)
    _columns(accepted, HISTORY_COLUMNS, 200)
    _columns(query, QUERY_COLUMNS, 200)
    for frame, is_raw in ((raw, True), (accepted, False), (query, False)):
        _context(frame, is_raw)
    if accepted.player_id.duplicated().any() or query.player_id.duplicated().any():
        raise JoinNotReady('ambiguous frozen identity metadata')
    witness = _witnesses(appearance)
    if expected_witnesses is not None and len(witness) != expected_witnesses:
        raise JoinNotReady('witness population changed')
    raw_ids, offered = _ids(raw), _ids(query)
    union = raw_ids | offered | witness
    if len(union) > 200:
        raise JoinNotReady('complete raw/witness/offered union exceeds200')
    raw_groups = {key: value.to_dict('records') for key, value in raw.groupby('player_id', sort=False)}
    old = {row['player_id']: row for row in accepted.to_dict('records')}
    offers = {row['player_id']: row for row in query.to_dict('records')}
    records = []
    context_conflicts = set()
    for player in sorted(union):
        rows, q, h = raw_groups.get(player, []), offers.get(player), old.get(player)
        r = rows[0] if len(rows) == 1 else None
        conflict = False
        if q is not None:
            conflict = h is None or any(not isinstance(q[name], str) or not isinstance(h[name], str)
                or q[name] != h[name] for name in ('position', 'team', 'opponent'))
            if r is not None:
                conflict |= q['team'] != r['team'] or q['opponent'] != r['opponent_team']
        if conflict:
            context_conflicts.add(player)
        prior = _old_support(h)
        position = q['position'] if q is not None else None
        for target, (fields, roles, kind) in TARGETS.items():
            state, zero, zero_kind = _target(r, fields, kind)
            if len(rows) > 1 and kind != 'blocked':
                state, zero, zero_kind = 'AMBIGUOUS_RAW_ROWS', False, ''
            primary = q is not None and isinstance(position, str) and position in roles
            unknown_position = not isinstance(position, str) or not position.strip()
            population = ('NOT_OFFERED' if q is None else 'OFFERED_UNKNOWN_POSITION' if unknown_position
                          else 'PRIMARY_OFFERED' if primary else 'OFFERED_OUTSIDE_PRIMARY')
            eligible = bool(primary and player in witness and zero and not conflict)
            records.append({'player_id': player, 'target': target, 'raw_row_count': len(rows),
                            'has_raw': bool(rows), 'ftn_witness': player in witness, 'offered': q is not None,
                            'position': position, 'population': population, 'context_conflict': bool(conflict),
                            'old_support': prior, 'target_state': state, 'known_zero': bool(zero),
                            'zero_kind': zero_kind, 'candidate_new_support': eligible and prior == 'OLD_UNKNOWN',
                            'already_supported_zero': eligible and prior == 'ALREADY_PLAYED'})
    private = pd.DataFrame(records, columns=['player_id', 'target', 'raw_row_count', 'has_raw', 'ftn_witness',
        'offered', 'position', 'population', 'context_conflict', 'old_support', 'target_state', 'known_zero',
        'zero_kind', 'candidate_new_support', 'already_supported_zero'])
    target_counts = {}
    for target in TARGETS:
        rows = private[private.target.eq(target)]
        groups = {}
        for population in ('PRIMARY_OFFERED', 'OFFERED_OUTSIDE_PRIMARY', 'OFFERED_UNKNOWN_POSITION', 'NOT_OFFERED'):
            selected = rows[rows.population.eq(population)]
            groups[population] = {'players': len(selected), 'target_states': dict(Counter(selected.target_state)),
                'known_zeros': int(selected.known_zero.sum()), 'positive_witnesses': int(selected.ftn_witness.sum()),
                'context_conflicts': int(selected.context_conflict.sum()),
                'candidate_new_support': int(selected.candidate_new_support.sum()),
                'already_supported_zeros': int(selected.already_supported_zero.sum())}
        target_counts[target] = groups
    aggregate = {'schema_version': VERSION, 'fixed_game': GAME, 'state': 'CANDIDATE_AUDIT_ONLY',
        'coverage': {'raw_planned_rows': len(raw), 'raw_unique_players': len(raw_ids),
            'raw_ambiguous_players': sum(len(x) > 1 for x in raw_groups.values()),
            'witness_players': len(witness), 'offered_players': len(offered), 'union_players': len(union),
            'witness_without_raw': len(witness - raw_ids), 'raw_without_witness': len(raw_ids - witness),
            'offered_without_raw_or_witness': len(offered - raw_ids - witness),
            'offered_without_accepted_metadata': len(offered - set(old)), 'context_conflict_players': len(context_conflicts)},
        'targets': target_counts, 'zeros_applied': 0, 'accepted_data_or_source_policy_changed': False,
        'no_complete_DNP_ST_PPR_or_historical_pregame_contract': True}
    return private, aggregate


def audit_zero_candidates(raw, appearance, accepted, query, *, expected_witnesses=None):
    """Audit all planned rows; failure diagnostics preserve input denominators.

    Malformed context or identities fail the whole audit, with no successful
    subset and no imputation. The attached diagnostic contains counts only.
    """
    try:
        return _audit_zero_candidates(raw, appearance, accepted, query,
            expected_witnesses=expected_witnesses)
    except JoinNotReady as error:
        error.diagnostic = {'state': 'NOT_READY', 'reason': str(error), 'planned_rows': {
            name: len(frame) if isinstance(frame, pd.DataFrame) else None
            for name, frame in (('raw', raw), ('appearance', appearance), ('accepted', accepted), ('query', query))},
            'successful_subset_returned': False, 'zeros_applied': 0}
        raise


def validate_global_freeze(freeze, query_sha256):
    """Authenticate the existing screen's exact frozen-query association."""
    if freeze.get('state') != 'GLOBAL_FORECASTS_FROZEN' or freeze.get('bindings', {}).get(QUERY_RELATIVE) != query_sha256:
        raise JoinNotReady('global forecast/query binding not frozen')
    slots = [x for x in freeze.get('slots', []) if x.get('year') == 2024 and x.get('state') == 'PREDICTION_FROZEN']
    if not slots or any(x.get('query') != QUERY_RELATIVE for x in slots):
        raise JoinNotReady('2024 frozen-query slot association missing')


def _read(binding):
    if not isinstance(binding, dict) or set(binding) != {'path', 'sha256', 'bytes'}:
        raise JoinNotReady('exact path/hash/size binding required')
    if (not isinstance(binding['path'], str) or not isinstance(binding['sha256'], str)
            or re.fullmatch(r'[0-9a-f]{64}', binding['sha256']) is None
            or type(binding['bytes']) is not int or binding['bytes'] < 0):
        raise JoinNotReady('unbound input')
    path = Path(binding['path'])
    if not path.is_absolute() or '..' in path.parts or path.resolve() != path.absolute():
        raise JoinNotReady('canonical absolute input path required')
    _no_symlinks(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != binding['bytes']:
        raise JoinNotReady('bound regular input required')
    body = path.read_bytes()
    after = path.stat()
    if (before.st_size != binding['bytes'] or len(body) != binding['bytes']
            or (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) !=
               (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
            or hashlib.sha256(body).hexdigest() != binding['sha256']):
        raise JoinNotReady('frozen input changed')
    return body


def _json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise JoinNotReady('duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise JoinNotReady('nonfinite JSON number')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


def _fixed_table(path, columns, game_column='game_id', limit=200):
    import pyarrow as pa
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    schema = pq.ParquetFile(path).schema_arrow
    if not set(columns).issubset(schema.names):
        raise JoinNotReady('registered source columns absent; no fallback')
    dataset = ds.dataset(path, format=ds.ParquetFileFormat(
        default_fragment_scan_options=ds.ParquetFragmentScanOptions(pre_buffer=False)))
    predicate = ds.field(game_column) == GAME
    count = dataset.count_rows(filter=predicate, use_threads=False)
    if count > limit or (count == 0 and game_column == 'nflverse_game_id'):
        raise JoinNotReady('fixed-game materialization cap/missing appearance')
    scanner = dataset.scanner(columns=columns, filter=predicate, batch_size=200,
        use_threads=False, batch_readahead=1, fragment_readahead=1)
    table = scanner.to_table()
    if table.num_rows != count:
        raise JoinNotReady('fixed predicate changed during read')
    return table


def run_join(execution_config, config_sha256):
    """Sole future bound invocation. Root owns the whole-job60/60/256MiB guard."""
    started, cpu_started = time.monotonic(), time.process_time()
    path = Path(execution_config)
    _no_symlinks(path)
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > 1048576:
        raise JoinNotReady('bounded regular execution config required')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != config_sha256:
        raise JoinNotReady('execution config hash mismatch')
    spec = _json(body)
    required = {'schema_version', 'state', 'budgets', 'cache', 'output', 'screen_output',
        'global_forecast_freeze', 'screen_query', *PINNED, 'code_sha256', 'environment'}
    if set(spec) != required or spec['schema_version'] != VERSION or spec['state'] != 'BOUND_READY' or spec['budgets'] != BUDGETS:
        raise JoinNotReady('unbound template or incorrect finite execution schema')
    root = Path(__file__).resolve().parent.parent
    if set(spec['code_sha256']) != set(CODE_FILES):
        raise JoinNotReady('exact caller/storage code pins required')
    for name, digest in spec['code_sha256'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise JoinNotReady('frozen code changed')
    env = spec['environment']
    if env['python'] != sys.version or Path(env['executable']).resolve() != Path(sys.executable).resolve():
        raise JoinNotReady('interpreter mismatch')
    import os
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        if os.environ.get(name) != '1':
            raise JoinNotReady('one numerical thread required')
    if set(env['packages']) != {'pandas', 'numpy', 'pyarrow'}:
        raise JoinNotReady('exact dependency pins required')
    for name, version in env['packages'].items():
        if importlib.metadata.version(name) != version:
            raise JoinNotReady('dependency mismatch')
    for name, digest in PINNED.items():
        if spec[name]['sha256'] != digest:
            raise JoinNotReady('original accepted input binding changed')
    freeze = _json(_read(spec['global_forecast_freeze']))
    validate_global_freeze(freeze, spec['screen_query']['sha256'])
    parent = Path(spec['screen_output'])
    if (Path(spec['global_forecast_freeze']['path']) != parent / 'forecast-freeze.json'
            or Path(spec['screen_query']['path']) != parent / QUERY_RELATIVE):
        raise JoinNotReady('exact saved screen query path required')
    manifest = _json(_read(spec['source_manifest']))
    source = manifest['sources']['stats_player_week_2024.parquet']
    if source['sha256'] != spec['raw_statistics']['sha256'] or source['bytes'] != spec['raw_statistics']['bytes']:
        raise JoinNotReady('raw statistics/source manifest mismatch')
    policy = _json(_read(spec['source_policy']))
    storage = OperationalStorage(spec['cache'], policy)
    inputs = ['global_forecast_freeze', 'screen_query', 'source_manifest', 'raw_statistics', 'appearance_projection', 'accepted_metadata']
    references, receipt = validate_owned_references(storage, {spec[x]['path']: spec[x]['sha256'] for x in inputs})
    for name in inputs:
        if references[str(Path(spec[name]['path']))]['bytes'] != spec[name]['bytes']:
            raise JoinNotReady('owned input byte size mismatch')
    output = Path(spec['output'])
    _no_symlinks(output)
    if (not output.is_absolute() or '..' in output.parts or output.resolve() != output.absolute()
            or output.exists() or storage.cache == output or storage.cache in output.parents or output in storage.cache.parents):
        raise JoinNotReady('fresh separate output scope required')
    storage.register_root(output)
    retained = 0
    def publish_json(name, value, *, final=False):
        nonlocal retained
        serialized = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        if retained + len(serialized) > BUDGETS['new_retained_bytes'] - (0 if final else 8192):
            raise JoinNotReady('private output byte cap')
        storage.write_bytes(output / name, serialized)
        retained += len(serialized)
    publish_json('JOIN_CONSUMED.json', {'version': VERSION, 'config_sha256': config_sha256,
        'consumed_utc': datetime.now(timezone.utc).isoformat(), 'invocations': 1, 'HTTP': 0})
    def guard():
        if time.monotonic() - started >= 54 or time.process_time() - cpu_started >= 54:
            raise TimeoutError('join audit finalization reserve')
    def publish_table(name, table):
        nonlocal retained
        import pyarrow.parquet as pq
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression='zstd')
        serialized = buffer.getvalue()
        if retained + len(serialized) > BUDGETS['new_retained_bytes'] - 8192:
            raise JoinNotReady('private output byte cap')
        storage.write_bytes(output / name, serialized)
        retained += len(serialized)
    terminal_state = 'FAILED'
    planned_rows = {}
    try:
        guard()
        app_table = _fixed_table(spec['appearance_projection']['path'], APPEARANCE_COLUMNS, 'nflverse_game_id', 10000)
        app = app_table.to_pandas(types_mapper=pd.ArrowDtype)
        planned_rows['appearance'] = len(app)
        if len(app) != 163 or len(_witnesses(app)) != 92:
            raise JoinNotReady('accepted163-play/92-witness population changed')
        old_table = _fixed_table(spec['accepted_metadata']['path'], HISTORY_COLUMNS)
        query_table = _fixed_table(spec['screen_query']['path'], QUERY_COLUMNS)
        context_table = _fixed_table(spec['raw_statistics']['path'], CONTEXT)
        planned_rows.update(accepted=old_table.num_rows, query=query_table.num_rows, raw=context_table.num_rows)
        context, query = context_table.to_pandas(types_mapper=pd.ArrowDtype), query_table.to_pandas(types_mapper=pd.ArrowDtype)
        _context(context, True)
        _context(query)
        if len(_ids(context) | _ids(query) | _witnesses(app)) > 200:
            raise JoinNotReady('complete union cap before primitive-stat values')
        guard()
        raw_table = _fixed_table(spec['raw_statistics']['path'], RAW_COLUMNS)
        if raw_table.num_rows == 0:
            raise JoinNotReady('exact raw game ID absent; no guessed fallback')
        publish_table('private/raw-projection.parquet', raw_table)
        guard()
        records, aggregate = audit_zero_candidates(raw_table.to_pandas(types_mapper=pd.ArrowDtype), app,
            old_table.to_pandas(types_mapper=pd.ArrowDtype), query, expected_witnesses=92)
        import pyarrow as pa
        publish_table('private/candidate-records.parquet', pa.Table.from_pandas(records, preserve_index=False))
        guard()
        _, exit_receipt = validate_owned_references(storage, {spec[x]['path']: spec[x]['sha256'] for x in inputs})
        if hashlib.sha256(path.read_bytes()).hexdigest() != config_sha256:
            raise JoinNotReady('execution config changed during audit')
        for name, digest in spec['code_sha256'].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
                raise JoinNotReady('frozen code changed during audit')
        _read(spec['source_policy'])
        aggregate.update(config_sha256=config_sha256, input_sha256s={x: spec[x]['sha256'] for x in inputs},
            global_forecasts_frozen=True, HTTP=0, usage_before_report_write={'wall_seconds': time.monotonic() - started,
            'CPU_seconds': time.process_time() - cpu_started, 'numerical_threads': 1})
        guard()
        publish_json('aggregate.json', aggregate)
        publish_json('reference-validation.json', {'before_decode': receipt, 'after_decode': exit_receipt})
        terminal_state = 'CANDIDATE_AUDIT_ONLY'
        return aggregate
    except BaseException as error:
        terminal_state = 'NOT_READY' if isinstance(error, JoinNotReady) else 'FAILED'
        publish_json('JOIN_FAILURE.json', {'error_type': type(error).__name__,
            'state': 'NOT_READY' if isinstance(error, JoinNotReady) else 'FAILED', 'HTTP': 0,
            'automatic_retry': False, 'wall_seconds': time.monotonic() - started,
            'CPU_seconds': time.process_time() - cpu_started,
            'diagnostic': getattr(error, 'diagnostic', {'planned_rows': planned_rows,
                'successful_subset_returned': False, 'reason': str(error)})}, final=True)
        raise
    finally:
        publish_json('JOIN_FINISHED.json', {'state': terminal_state, 'config_sha256': config_sha256,
            'wall_seconds_before_final_write': time.monotonic() - started,
            'CPU_seconds_before_final_write': time.process_time() - cpu_started,
            'retained_bytes_before_final_write': retained, 'HTTP': 0, 'automatic_retry': False}, final=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args(argv)
    result = run_join(args.config, args.config_sha256)
    print(json.dumps({'state': result['state'], 'coverage': result['coverage']}, allow_nan=False))


if __name__ == '__main__':
    main()
