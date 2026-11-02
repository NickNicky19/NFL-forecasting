"""Project exact method/policy cells from retained grades; no new decisions or data."""
import collections
import csv
import gzip
import hashlib
import io
import json
import resource
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/week8-original-grading-20261102'


def run():
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    cpu = time.process_time()
    binding = json.loads(gzip.decompress((ROOT / 'config/session-ab-private-transport-v1.private.json.gz').read_bytes()))
    base = Path(binding['destination_root']).parent / 'week8-original-grade-v2-batch-20261102'
    source = base / 'READABLE_SCORECARDS_V1.zip'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == 'efbeb957ad1a92e4236d166b6be6f9371c77b0f5909a371c719872d0925fc966'
    with zipfile.ZipFile(source) as archive:
        content = gzip.decompress(archive.read('ORIGINAL_DECISIONS_AND_DIRECTIONS.csv.gz')).decode()
    records = list(csv.DictReader(io.StringIO(content)))
    assert len(records) == 6373
    keys = ['group', 'cohort', 'category', 'method', 'policy']
    assert set(keys + ['result', 'side', 'game_id', 'player_id']) <= set(records[0])
    cells = collections.defaultdict(list)
    for row in records:
        cells[tuple(row[k] for k in keys)].append(row)
    public = []
    for key, rows in sorted(cells.items()):
        result = dict(zip(keys, key))
        result['recorded'] = len(rows)
        for side in ['over', 'under']:
            counts = collections.Counter(r['result'] for r in rows if r['side'] == side)
            decided = counts['WIN'] + counts['LOSS']
            result[side] = {'wins': counts['WIN'], 'losses': counts['LOSS'], 'decided': decided,
                            'hit_rate': counts['WIN'] / decided if decided else None,
                            'missing_rate_reason': None if decided else 'NO_DECIDED_SELECTIONS',
                            'status_counts': dict(sorted(counts.items()))}
        counts = collections.Counter(r['result'] for r in rows)
        result['status_counts'] = dict(sorted(counts.items()))
        result['unique_games'] = len({r['game_id'] for r in rows})
        result['unique_player_games'] = len({(r['game_id'], r['player_id']) for r in rows})
        public.append(result)
    assert sum(r['recorded'] for r in public) == 6373
    output = {'version': 'week8-exact-method-side-projection-v1',
              'parent_readable_sha256': 'efbeb957ad1a92e4236d166b6be6f9371c77b0f5909a371c719872d0925fc966',
              'scope': 'Exact saved method/policy cells. No pooling of snapshots, original picks, Top Picks or retrospective P1.',
              'new_forecasts_or_grades': 0, 'rows': public}
    (REPORT / 'BY_METHOD_CATEGORY_SIDES_V1.json').write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    receipt = {'state': 'PASS_EXISTING_GRADE_PROJECTION_ONLY', 'input_rows': len(records),
               'output_cells': len(public), 'actual_CPU_seconds': time.process_time() - cpu,
               'new_fits_inference_scores_sources': 0, 'new_private_bytes': 0}
    (REPORT / 'METHOD_SIDE_PROJECTION_RECEIPT_V1.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    run()
