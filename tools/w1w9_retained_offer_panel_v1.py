"""Offline reconstruction of the existing B W5--9 retained QB offer panel.

Root owns source admission, immutable caching, storage accounting and scoring.
This adapter reads only root-bound caches, performs no grading or model work,
and never accesses a network or infers an identity from a player name.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import datetime
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'A-W1W9-B-NATIVE-CMP-SOURCE-PANEL-v1'
PHASE = 'ROOT_ADMISSION'
WEEKS = (5, 6, 7, 8, 9)
EXPECTED_CMP = {5: 28, 6: 28, 7: 28, 8: 28, 9: 30}
PROVIDERS = {'dk': 'DRAFTKINGS_VIA_ESPN_PROVIDER_100', 'sleeper': 'SLEEPER_PICKS'}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(ref, *, max_bytes=16 * 1024**2):
    if 'stored_encoding' in ref:
        from tools.w1w9_source_cache_v1 import original
        body = original(ref)
        require(len(body) <= max_bytes, 'Decoded original input reservation exceeded')
        return body
    path = Path(ref['path'])
    require(path.is_absolute() and path.resolve() == path and not any(p.is_symlink() for p in (path, *path.parents)),
            'Canonical nonsymlink admitted input required')
    before = path.stat()
    require(before.st_size == ref['bytes'] and before.st_size <= max_bytes, 'Bound input size differs')
    body = path.read_bytes()
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Bound input changed during read')
    require(sha(body) == ref['sha256'], 'Bound input hash differs')
    return body


def document(ref):
    body = bound(ref)
    if body.startswith(b'\x1f\x8b'):
        body = gzip.decompress(body)
    require(len(body) <= 64 * 1024**2, 'Decoded document reservation exceeded')
    return json.loads(body)


def records(ref):
    fmt = ref.get('format', 'json')
    if fmt in ('json', 'json.gz'):
        value = document(ref)
        if isinstance(value, list):
            return value
        key = ref.get('rows_key', 'rows')
        require(isinstance(value, dict) and isinstance(value.get(key), list), 'Declared rows array unavailable')
        return value[key]
    body = bound(ref)
    if fmt == 'parquet':
        import pandas as pd
        frame = pd.read_parquet(io.BytesIO(body))
        return json.loads(frame.to_json(orient='records'))
    if fmt in ('csv', 'csv.gz'):
        if fmt.endswith('.gz'):
            body = gzip.decompress(body)
        return list(csv.DictReader(io.StringIO(body.decode())))
    raise ValueError('Unregistered record format')


def team(value):
    # Existing qualified 2026 Rams alias only; never rewrite a canonical game ID.
    return 'LAR' if value == 'LA' else value


def stamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return datetime.datetime.fromtimestamp(value, datetime.timezone.utc)
    require(isinstance(value, str), 'Explicit clock required')
    result = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Unknown or naive clock cannot be authenticated')
    return result.astimezone(datetime.timezone.utc)


def number(value, *, count=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if count and (value < 0 or value != int(value)):
        return None
    return int(value) if count else value


def immutable(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def identity_maps(ref):
    """Reuse A's exact registry conflict rules; only ID columns are consumed."""
    import pandas as pd
    from nfl_lab.query_identity import _registry
    from nfl_lab.weekly_current_query import _gsis, _sleeper
    raw = records(ref)
    kind = ref.get('kind', 'IDENTITY_REGISTRY')
    require(kind in ('IDENTITY_REGISTRY', 'ROSTER_IDS', 'FROZEN_QUERY_IDS'),
            'Explicit identity source contract required')
    if kind == 'FROZEN_QUERY_IDS':
        require(ref.get('original_sha256', ref.get('sha256')) ==
                '94c8746a2287d680bef096d7b2bde843c1528d5250d1d1bb9658e46a2c81daed',
                'FROZEN_QUERY_IDS is scoped to the exact prior A qualified-query artifact')
    result, receipts = {}, {}
    for week in WEEKS:
        selected = []
        for row in raw:
            if kind in ('ROSTER_IDS', 'FROZEN_QUERY_IDS'):
                # Identity-only historical roster prefix; never a playing/role filter.
                if int(row['season']) != 2026 or (kind=='ROSTER_IDS' and int(row['week']) > week):
                    continue
                player_field = 'gsis_id' if kind=='ROSTER_IDS' else 'player_id'
                player, sleeper = _gsis(row.get(player_field)), _sleeper(row.get('sleeper_id'))
                if kind == 'FROZEN_QUERY_IDS':
                    require(player is not None and sleeper is not None,
                            'Bound frozen query identity contains an unqualified ID')
                if player is None or sleeper is None:
                    continue
                state = 'source_exact_binding'
            else:
                player, sleeper = _gsis(row.get('player_id')), _sleeper(row.get('sleeper_id'))
                state = row.get('identity_status')
                require(state in ('source_exact_binding', 'ambiguous_source_binding', 'no_sleeper_binding'),
                        'Identity registry status is not qualified')
            selected.append(dict(player_id=player, sleeper_id=sleeper, identity_status=state))
        frame = pd.DataFrame(selected, columns=['player_id', 'sleeper_id', 'identity_status'])
        _, mapping, quarantined, summary = _registry(frame)
        result[week] = (mapping, quarantined)
        receipts[str(week)] = summary
    return result, receipts


def football_indexes(ref):
    rows = records(ref)
    labels, games = {}, {}
    by_game = defaultdict(list)
    for row in rows:
        if row.get('season') != 2026 or row.get('week') not in WEEKS:
            continue
        require(isinstance(row.get('game_id'), str) and isinstance(row.get('player_id'), str),
                'Canonical football IDs unavailable')
        key = row['game_id'], row['player_id']
        require(key not in labels, 'Duplicate canonical football outcome key')
        labels[key] = row
        by_game[row['game_id']].append(row)
    for gid, rr in by_game.items():
        weeks = {r['week'] for r in rr}
        clocks = {stamp(r['kickoff']).isoformat() for r in rr}
        pairs = {frozenset((team(r['team']), team(r['opponent']))) for r in rr}
        require(len(weeks) == len(clocks) == len(pairs) == 1, 'Conflicting football game identity')
        require(len(next(iter(pairs))) == 2, 'Opposing teams must differ')
        games[gid] = dict(week=next(iter(weeks)), kickoff=next(iter(clocks)), teams=next(iter(pairs)))
    return labels, games


def qualified_actual(label, source, kickoff):
    """Explicit credit and physical appearance are separate requirements."""
    if label is None:
        return None, 'UNKNOWN_PARTICIPATION', 'MISSING_CANONICAL_OUTCOME_ROW'
    if label.get('position') != 'QB':
        return None, 'UNKNOWN_PARTICIPATION', 'LABEL_ROLE_MISMATCH'
    if any(team(label.get(k)) != team(source.get(k)) for k in ('team', 'opponent')):
        return None, 'UNKNOWN_PARTICIPATION', 'LABEL_TEAM_OPPONENT_MISMATCH'
    if stamp(label['kickoff']) != kickoff:
        return None, 'UNKNOWN_PARTICIPATION', 'LABEL_KICKOFF_MISMATCH'
    state = label.get('label_status')
    if state in ('DNP', 'VERIFIED_DNP'):
        return None, 'DNP', 'EXPLICIT_QUALIFIED_DNP'
    physical = label.get('physical_participation') is True
    if not physical:
        return None, 'UNKNOWN_PARTICIPATION', 'PHYSICAL_APPEARANCE_UNQUALIFIED'
    if 'official_completions' not in label:
        return None, 'PLAYED', 'ABSENT_OFFICIAL_COMPLETIONS'
    actual = number(label['official_completions'], count=True)
    if actual is None:
        return None, 'PLAYED', 'NULL_OR_INVALID_OFFICIAL_COMPLETIONS'
    return actual, 'PLAYED', 'EXPLICIT_REPORTED_ZERO' if actual == 0 else 'EXPLICIT_REPORTED_VALUE'


def canonical_game_state(assignment, source_game, football_games, week):
    """Independently check an existing mapping; never select a source by labels."""
    gid = assignment.get('canonical_game_id')
    fact = football_games.get(gid)
    if fact is None:
        return 'UNVERIFIED_INDEPENDENT_CANONICAL_GAME'
    require(fact['week'] == week and stamp(fact['kickoff']) == stamp(assignment['kickoff_UTC'])
            and fact['teams'] == frozenset((team(source_game['home']), team(source_game['away']))),
            'Published source assignment conflicts with independent canonical game metadata')
    return 'PASS_INDEPENDENT_WEEK_KICKOFF_OPPONENTS'


def offer_identity(row):
    # Exact public B iterator identity; source ordinals are not join identities.
    return tuple(str(row[k]) if k == 'line' else row.get(k)
                 for k in ('game_id', 'player_id', 'target', 'line', 'line_from', 'source_head', 'source_server_clock'))


def fingerprint(rows):
    keys = [offer_identity(r) for r in rows]
    if any(any(v is None for v in key) for key in keys):
        return None
    require(len(keys) == len(set(keys)), 'Duplicate native source identity')
    # B's commitment uses compact JSON without a trailing newline.
    return sha(json.dumps(sorted(keys), separators=(',', ':')).encode())


def reconstruct(plan):
    global PHASE
    PHASE = 'BOUND_METADATA_AND_IDENTITY'
    manifest = document(plan['source_manifest'])
    require(manifest['id'] == 'A_READONLY_B_NATIVE_COMPLETION_PUBLIC_SOURCE_RECONCILIATION_v1',
            'Exact source manifest required')
    ids, identity_receipts = identity_maps(plan['identity'])
    labels, game_index = football_indexes(plan['football'])
    bound_snapshots = {(int(ref['week']), str(ref['snapshot_id'])): ref for ref in plan['snapshots']}
    expected_identities = {int(q['week']): q['offer_identity_sha256']
                           for q in manifest['native_142_contract']['original_W5_W8_sources']}
    expected_identities[9] = manifest['source_panels'][-1]['full_cmp_att_offer_identity_sha256']
    output, identities, traces, rejects = [], defaultdict(list), [], Counter()
    PHASE = 'SOURCE_SELECTED_EXTERNAL_QB_MARKETS'
    for panel in manifest['source_panels']:
        week = panel['week']
        snapshot_specs = panel.get('snapshots') or [dict(panel['snapshot'], id=0,
            source_server_clock=panel['source_server_clock'], server_run_id=panel['retention_run'])]
        if week <= 8:
            assignments = [dict(zip(panel['assignment_columns'], values)) for values in panel['assignment_rows']]
            assignment_by_snapshot = defaultdict(list)
            for a in assignments:
                assignment_by_snapshot[str(a['snapshot_id'])].append(a)
        else:
            assignment_by_snapshot = {'0': []}
        for spec in snapshot_specs:
            sid = str(spec['id'])
            ref = bound_snapshots.get((week, sid))
            require(ref is not None, 'An exact source-selected archive is not cached')
            raw = bound(ref)
            require(ref['commit'] == spec['commit'], 'Source head differs')
            require(len(raw) == spec['bytes'], 'Source archive byte count differs')
            if spec.get('sha256'):
                require(sha(raw) == spec['sha256'], 'Original source SHA256 differs')
            git_sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            require(git_sha == spec['git_blob_sha1'], 'Original immutable Git blob differs')
            board = json.loads(raw)
            require(board['season'] == 2026 and board['week'] == week, 'Archive period differs')
            require(isinstance(board.get('players'), list) and isinstance(board.get('games'), list),
                    'Original archive board schema unavailable')
            game_rows = {str(g['id']): g for g in board['games']}
            require(len(game_rows) == len(board['games']), 'Duplicate source event ID')
            selected = {str(a['source_ESPN_event_id']): a for a in assignment_by_snapshot[sid]}
            if week == 9:
                for event, g in game_rows.items():
                    kickoff = stamp(g['kickoff'])
                    pair = frozenset((team(g['home']), team(g['away'])))
                    matches = [gid for gid, fact in game_index.items() if fact['week'] == 9
                               and stamp(fact['kickoff']) == kickoff and fact['teams'] == pair]
                    selected[event] = dict(canonical_game_id=matches[0] if len(matches) == 1 else None,
                        source_ESPN_event_id=event, kickoff_UTC=kickoff.isoformat(),
                        T90_UTC=(kickoff-datetime.timedelta(minutes=90)).isoformat(),
                        snapshot_id=0, source_window_closed=None,
                        game_identity_state='EXACT_KICKOFF_AND_OPPOSING_TEAMS' if len(matches)==1
                                            else 'UNRESOLVED_CANONICAL_GAME')
            snapshot_rows = 0
            for pi, player in enumerate(board['players']):
                if player.get('pos') != 'QB':
                    continue
                event = str(player.get('game_id'))
                if event not in selected:
                    continue
                a = selected[event]
                require(event in game_rows, 'Selected source game metadata missing')
                g = game_rows[event]
                kickoff = stamp(a['kickoff_UTC'])
                require(stamp(g['kickoff']) == kickoff, 'Selected game kickoff differs')
                game_identity_state = (canonical_game_state(a, g, game_index, week) if week <= 8 else
                                       a.get('game_identity_state', 'UNRESOLVED_CANONICAL_GAME'))
                require(stamp(spec['source_server_clock']) <= stamp(a['T90_UTC']),
                        'Published source retention violates its own T90 bound')
                require(team(player.get('team')) in (team(g['home']), team(g['away'])),
                        'Source player team is outside its event')
                from nfl_lab.weekly_current_query import _sleeper
                source_pid = _sleeper(player.get('id'))
                mapping, quarantined = ids[week]
                canonical = mapping.get(source_pid)
                identity_state = ('EXACT_SOURCE_ID_BINDING' if canonical else
                                  'AMBIGUOUS_SOURCE_ID' if source_pid in quarantined else
                                  'UNRESOLVED_SOURCE_PLAYER_ID')
                for qi, prop in enumerate(player.get('props', [])):
                    target = prop.get('key')
                    if target not in ('pass_cmp', 'pass_att'):
                        continue
                    if prop.get('line_from') not in PROVIDERS:
                        rejects[str(target)+':GENERATED_OR_UNQUALIFIED_LINE'] += 1
                        continue
                    line = number(prop.get('line'))
                    identity_row = dict(game_id=a.get('canonical_game_id'), player_id=canonical,
                        target=target, line=line, line_from=prop['line_from'],
                        source_head=spec['commit'], source_server_clock=spec['source_server_clock'])
                    identities[week].append(identity_row)
                    if target != 'pass_cmp':
                        continue
                    opponent = g['away'] if team(player['team']) == team(g['home']) else g['home']
                    source = dict(team=player['team'], opponent=opponent)
                    key = a.get('canonical_game_id'), canonical
                    actual, appearance, support = qualified_actual(labels.get(key), source, kickoff)
                    row = dict(season=2026, week=week, category='pass_cmp', **identity_row,
                        source_game_id=event, source_player_id=source_pid, position='QB',
                        team=team(player['team']), opponent=team(opponent),
                        source_player_index=pi, source_prop_index=qi,
                        source_archive_sha256=sha(raw), source_git_blob_sha1=git_sha,
                        source_server_run_id=spec.get('server_run_id'),
                        kickoff_utc=kickoff.isoformat(), cutoff_utc=kickoff.isoformat(),
                        source_T90_deadline=a['T90_UTC'], source_window_closed=a.get('source_window_closed'),
                        source_marked_late=player.get('late'), identity_state=identity_state,
                        source_game_identity_state=game_identity_state,
                        book=PROVIDERS[prop['line_from']], main_alternate_status='UNKNOWN',
                        original_bookmaker_quote_clock=None, quote_timing_status='UNVERIFIED',
                        quote_age=None, venue_settlement_status='UNRESOLVED_CONTRACT',
                        comparator='STRICT_OVER_UNDER', period='FULL_GAME_INCLUDING_OVERTIME',
                        source_original_side=prop.get('lean'), source_adjusted_point=number(prop.get('adj')),
                        source_raw_point=number(prop.get('proj')), appearance=appearance, actual=actual,
                        label_reason=support, outcome_field='official_completions',
                        football_outcome_source_sha256=plan['football'].get('original_sha256',plan['football'].get('sha256')),
                        target_parity=labels.get(key, {}).get('target_parity'),
                        eligible_retained_line=line is not None,
                        evidence_tier='RETAINED_EXTERNAL_PROVIDER_LINE_TIMING_UNVERIFIED_CURRENT_VINTAGE_DIAGNOSTIC',
                        source_horizon='PER_GAME_T90_SOURCE_ASSIGNMENT' if week<9 else 'FIXED_PRE_FIRST_T90_SOURCE',
                        forecast_comparison_horizon='LEFT_LIMIT_KICKOFF_RECONSTRUCTION_NOT_ORIGINAL_ISSUANCE')
                    row['opportunity_key'] = sha(encoded([2026,week,event,source_pid,target,
                        str(prop.get('line')),prop['line_from'],spec['commit'],spec['source_server_clock']]))
                    output.append(row)
                    snapshot_rows += 1
            traces.append(dict(week=week,snapshot_id=sid,commit=spec['commit'],
                               bytes=len(raw),sha256=sha(raw),git_blob_sha1=git_sha,CMP_rows=snapshot_rows))
    PHASE = 'NATIVE_PANEL_IDENTITY_AND_COMPLETENESS_RECEIPT'
    require(len({r['opportunity_key'] for r in output}) == len(output), 'Duplicate full source opportunity')
    coverage=[]
    for week in WEEKS:
        rr=[r for r in output if r['week']==week]
        got=fingerprint(identities[week])
        coverage.append(dict(week=week,expected_CMP=EXPECTED_CMP[week],source_CMP_rows=len(rr),
            expected_native_CMP_ATT_identity_sha256=expected_identities[week],
            actual_native_CMP_ATT_identity_sha256=got,
            native_identity_parity=got==expected_identities[week],
            canonical_games=len({r['game_id'] for r in rr if r['game_id']}),
            source_games=len({r['source_game_id'] for r in rr}),
            source_CMP_ATT_rows=len(identities[week]),
            identity_states=dict(Counter(r['identity_state'] for r in rr)),
            independent_game_identity_states=dict(Counter(r['source_game_identity_state'] for r in rr)),
            appearance_states=dict(Counter(r['appearance'] for r in rr)),
            outcome_states=dict(Counter(r['label_reason'] for r in rr)),
            missing_lines=sum(not r['eligible_retained_line'] for r in rr),
            source_window_closed=dict(Counter(str(r['source_window_closed']) for r in rr))))
    complete=(all(r['source_CMP_rows']==r['expected_CMP'] and r['native_identity_parity']
                  and not r['missing_lines'] for r in coverage)
              and all(r['source_game_identity_state'] in
                      ('PASS_INDEPENDENT_WEEK_KICKOFF_OPPONENTS', 'EXACT_KICKOFF_AND_OPPOSING_TEAMS')
                      for r in output))
    output.sort(key=lambda r:(r['week'],r['kickoff_utc'],r['source_game_id'],r['source_player_id'] or '',r['opportunity_key']))
    result=dict(id=VERSION,state='PASS_EXACT_NATIVE_SOURCE_MEMBERSHIP_RECONSTRUCTION' if complete
                else 'PARTIAL_SOURCE_OR_IDENTITY_DEPENDENCY_BLOCKED',rows=output,
                source_CMP_ATT_identities={str(k):v for k,v in identities.items()},coverage=coverage,
                source_receipts=traces,identity_registry_receipts=identity_receipts,
                exclusions=dict(rejects),source_manifest_sha256=plan['source_manifest'].get('original_sha256',plan['source_manifest'].get('sha256')),
                identity_source_sha256=plan['identity'].get('original_sha256',plan['identity'].get('sha256')),
                football_source_sha256=plan['football'].get('original_sha256',plan['football'].get('sha256')),
                counts=dict(new_fits=0,new_inference=0,new_scores=0,network_calls=0,original_issued_picks=0))
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--plan-sha256',required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--receipt',type=Path,required=True)
    args=ap.parse_args()
    raw=args.plan.read_bytes()
    require(sha(raw)==args.plan_sha256,'Exact root source GO required')
    plan=json.loads(raw)
    require(plan['id']==VERSION and plan['state']=='ROOT_SOURCE_GO' and plan['registered_by']=='/root',
            'Root source reconstruction authority required')
    require(sha(Path(__file__).read_bytes())==plan['adapter_sha256'],'Source adapter differs')
    for path,digest in plan['helper_sha256'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Existing identity helper differs')
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(ROOT))
    resource.setrlimit(resource.RLIMIT_CPU,(90,120))
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Finite source reconstruction wall limit')))
    signal.alarm(180)
    def offline(event,_):
        if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo'):
            raise RuntimeError('Root-bound offline source cache only')
    sys.addaudithook(offline)
    result=reconstruct(plan)
    body=gzip.compress(encoded(result),mtime=0)
    require(len(body)<=2*1024**2,'Private source-panel output reservation exceeded')
    immutable(args.output,body)
    public={k:v for k,v in result.items() if k not in ('rows','source_CMP_ATT_identities')}
    public.update(private_panel_bytes=len(body),private_panel_sha256=sha(body),
                  plan_sha256=args.plan_sha256,CPU_seconds=resource.getrusage(resource.RUSAGE_SELF).ru_utime+
                  resource.getrusage(resource.RUSAGE_SELF).ru_stime,
                  RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    receipt=encoded(public)
    require(len(receipt)<=65536,'Public source receipt reservation exceeded')
    immutable(args.receipt,receipt)
    signal.alarm(0)
    print(json.dumps({k:public[k] for k in ('state','private_panel_bytes','private_panel_sha256')}))


if __name__=='__main__':
    try:
        main()
    except BaseException as error:
        signal.alarm(0)
        print(json.dumps(dict(id=VERSION,state='FAILED_NO_AUTOMATIC_RETRY',phase=PHASE,
            error_type=type(error).__name__,error_sha256=sha(str(error).encode()),
            new_fits=0,new_inference=0,new_scores=0,network_calls=0)))
        raise
