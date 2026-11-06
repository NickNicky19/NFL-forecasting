"""Authenticate and census existing full-board replay inputs; do not rank picks.

The original-site owner executes the only complete changed-policy replay.
This reads existing immutable private evidence without refitting/repackaging it.
"""
from pathlib import Path
import collections
import argparse
import csv
import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/execution-closure-02'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scope-census', action='store_true')
    args = parser.parse_args()
    start = time.monotonic()
    cpu = time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (1610612736, 1610612736))
    resource.setrlimit(resource.RLIMIT_CPU, (67, 69) if args.scope_census else (105, 108))
    signal.alarm(170)
    sys.path.insert(0, str(ROOT))
    import nfl_lab
    from nfl_lab.owned_reference_batch import validate_owned_references
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    store, _ = open_store(ROOT, allocation_sha256=
        'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO, readonly=True)
    original_receipt = json.loads((ROOT /
        'reports/category-topfive-matched-all12-w1w7-20261030/READABLE_PRIVATE_SCORECARD_V1.json').read_bytes())
    reference = original_receipt['artifact']
    archive_path = store.forward_root / 'research/matched12-readable-private-scorecard-v1-20261031/READABLE_SCORECARD.zip'
    validate_owned_references(store, {str(archive_path): reference['sha256']})
    if archive_path.stat().st_size != reference['bytes']:
        raise ValueError('original readable full-board source size differs')
    if args.scope_census:
        def finite(text):
            try:
                return bool(text) and Decimal(text).is_finite()
            except InvalidOperation:
                return False
        seen = set()
        position_counts = collections.Counter()
        no_line = set()
        status = collections.Counter()
        with zipfile.ZipFile(archive_path) as archive:
            with archive.open('PREDICTIONS_ACTUALS_LINES_AND_DIRECTIONS.csv') as stream:
                rows = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8', newline=''))
                for row in rows:
                    key = tuple(row[k] for k in ['target', 'season', 'week', 'game_id', 'player_id'])
                    if not finite(row['line']):
                        no_line.add(key)
                        continue
                    key += (row['line'], row['horizon_id'], row['book_id'])
                    if key not in seen:
                        seen.add(key)
                        position_counts[(row['target'], row['position'])] += 1
                    status[(row['target'], row['method'], row['product'], row['position'],
                        'FINITE_OUTPUT' if finite(row['prediction']) else 'UNAVAILABLE_OUTPUT',
                        bool(row['fallback']))] += 1
        result = {'id': 'A-CLOSURE02-EXISTING-FULL-BOARD-ROLE-CENSUS-v2',
            'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'archive': reference, 'state': 'EXACT_RETAINED_SCOPE_COUNT_NO_GRADING_OR_SELECTION',
            'unique_valid_line_book_horizon_opportunities': len(seen),
            'unique_target_player_games_without_line': len(no_line),
            'role_scope': [{'category': t, 'position': p, 'unique_offers': n}
                for (t, p), n in sorted(position_counts.items())],
            'candidate_output_census': [{'category': t, 'method': m, 'output': o,
                'position': p, 'state': s, 'fallback_flag': f, 'rows': n}
                for (t, m, o, p, s, f), n in sorted(status.items())],
            'new_fits_inference_scores_selection_replays': 0,
            'limits': ['Counts existing finite original lines; no outcome accessed for a decision or grade.',
                'All-role offer population, role-restricted model population and supported-output coverage remain separate.',
                'This verifies existing inputs for the sole website-owner replay; not its execution or qualification.'],
            'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - start,
            'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        with (OUT / 'FULL_BOARD_ROLE_SCOPE_CENSUS_V2.json').open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps({k: result[k] for k in ['state', 'unique_valid_line_book_horizon_opportunities',
            'unique_target_player_games_without_line', 'role_scope', 'CPU_seconds']}))
        signal.alarm(0)
        return
    counts = []
    with zipfile.ZipFile(archive_path) as archive:
        members = json.loads(archive.read('MANIFEST.json'))
        for name in ['PREDICTIONS_AND_ACTUALS.csv', 'PREDICTIONS_ACTUALS_LINES_AND_DIRECTIONS.csv']:
            digest = hashlib.sha256()
            number_bytes = 0
            with archive.open(name) as stream:
                while True:
                    block = stream.read(1048576)
                    if not block:
                        break
                    digest.update(block)
                    number_bytes += len(block)
            if digest.hexdigest() != members[name]['sha256'] or number_bytes != members[name]['bytes']:
                raise ValueError('original CSV member bytes differ')
            category = collections.Counter()
            week = collections.Counter()
            opportunities = set()
            with archive.open(name) as binary:
                rows = csv.DictReader(io.TextIOWrapper(binary, encoding='utf-8', newline=''))
                columns = rows.fieldnames
                needed = {'target', 'season', 'week', 'game_id', 'player_id'}
                if not needed <= set(columns):
                    raise ValueError('private replay identities incomplete')
                n = 0
                for row in rows:
                    # Census only. No outcome values, winning sides or ranking.
                    n += 1
                    category[row['target']] += 1
                    week[(row['season'], row['week'])] += 1
                    key = tuple(row[k] for k in ['target', 'season', 'week', 'game_id', 'player_id'])
                    if 'line' in row:
                        key += (row['line'],)
                    opportunities.add(key)
            if n != original_receipt['rows'][name]:
                raise ValueError('original full-board row count differs')
            counts.append({'member': name, **members[name], 'actual_rows': n,
                'columns': columns, 'category_rows': dict(category),
                'season_week_rows': [{'season': int(y), 'week': int(w), 'rows': c}
                    for (y, w), c in sorted(week.items())],
                'unique_opportunity_keys': len(opportunities),
                'key': 'target/season/week/game/player, plus exact saved line when present; not a deduplicated selector eligibility decision'})
    result = {'id': 'A-CLOSURE02-EXISTING-FULL-BOARD-INPUTS-v1',
        'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'EXISTING_BYTES_AUTHENTICATED_AND_CENSUSED_NO_NEW_EXPORT_OR_REPLAY',
        'archive': reference, 'members': counts,
        'source_result_sha256': original_receipt['source_result_sha256'],
        'retrieval': 'Existing A approved owner-controlled archive restoration; logical object matched12-readable-private-scorecard-v1-20261031/READABLE_SCORECARD.zip. Physical private locator redacted.',
        'transfer': 'PREPARED_EXISTING_OBJECT; no receiver restoration or usable cross-owner transport acknowledged.',
        'replay_owner': 'Retained original-site owner; C remains common evaluation coordinator.',
        'new_fits_inference_scoring_selection_replay': 0,
        'new_private_objects': 0, 'private_row_publication': False,
        'limits': ['2026 W1-7 reconstructions, including unknowns and full supported candidate board; not original website recommendations.',
            'Quote-time and venue settlement remain unqualified; original as-issued timing cannot be reconstructed by this census.',
            'Exact proposed category mapping, real site eligibility/line precedence/best-per-player/normalization/side capacities/ties/fallback/expiry and incumbent board must be supplied by the single replay owner.',
            'Seven-week component forecasts do not qualify a changed cross-category Top Picks policy; the exact owner replay is still unexecuted here.',
            'No assumption that another session can access this local store or a public hash can restore its private rows.'],
        'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - start,
        'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    with (OUT / 'FULL_BOARD_REPLAY_INPUT_RECEIPT_V1.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ['state', 'archive', 'new_private_objects', 'CPU_seconds', 'wall_seconds']}))
    signal.alarm(0)


if __name__ == '__main__':
    main()
