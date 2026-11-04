"""Paired uncertainty from saved grades; no new predictions or model fits."""
from pathlib import Path
import collections
import datetime
import gzip
import json
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    out = ROOT / 'reports/abc-championship/predictive-improvement-01'
    protocol = json.loads((out / 'FULL_BOARD_UNCERTAINTY_PROTOCOL_V1.json').read_bytes())
    start = time.monotonic()
    cpu = time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
    resource.setrlimit(resource.RLIMIT_AS, (1610612736, 1610612736))
    signal.alarm(150)
    store, _ = open_store(ROOT, allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO, readonly=True)
    ref = json.loads((out / 'FULL_BOARD_DIRECT_RESULTS_V1.json').read_bytes())['private_grade']
    path = store.forward_root / 'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/FULL_BOARD_CARRY_GRADE_V1.zip'
    store.validate_reference(path, ref['sha256'])
    with zipfile.ZipFile(path) as z:
        rows = json.loads(gzip.decompress(z.read('GRADE_ROWS.json.gz')))
    index = {(r['arm'], r['policy'], r['opportunity_key']): r for r in rows}
    if len(index) != len(rows):
        raise ValueError('duplicate method-policy-opportunity')

    def interval(values, cluster):
        groups = collections.defaultdict(list)
        for row in values:
            groups[str(row[cluster])].append(row['delta'])
        keys = sorted(groups)
        sums = np.array([sum(groups[k]) for k in keys])
        counts = np.array([len(groups[k]) for k in keys])
        rng = np.random.default_rng(protocol['seed'])
        draws = rng.integers(len(keys), size=(protocol['replicates'], len(keys)))
        means = sums[draws].sum(1) / counts[draws].sum(1)
        return {'clusters': len(keys), 'low': float(np.quantile(means, .025)),
                'high': float(np.quantile(means, .975))}

    results = []
    for left, lp, right, rp in protocol['pairs']:
        matched = []
        for r in rows:
            if r['arm'] != left or r['policy'] != lp or r['status'] not in ('WIN', 'LOSS'):
                continue
            s = index.get((right, rp, r['opportunity_key']))
            if not s or s['status'] not in ('WIN', 'LOSS'):
                continue
            if any(r[k] != s[k] for k in ['actual', 'line', 'game_id', 'player_id', 'week']):
                raise ValueError('paired identity/outcome/line mismatch')
            matched.append({'game_id': r['game_id'], 'week': r['week'], 'position': r['position'],
                            'left_win': int(r['status'] == 'WIN'), 'right_win': int(s['status'] == 'WIN'),
                            'delta': int(r['status'] == 'WIN') - int(s['status'] == 'WIN'),
                            'disagree': r['selected_side'] != s['selected_side']})
        lw = sum(x['left_win'] for x in matched)
        rw = sum(x['right_win'] for x in matched)
        results.append({'left': left, 'left_policy': lp, 'right': right, 'right_policy': rp,
                        'n': len(matched), 'games': len({x['game_id'] for x in matched}),
                        'left_wins': lw, 'right_wins': rw, 'rate_change': (lw - rw) / len(matched),
                        'disagreements': sum(x['disagree'] for x in matched),
                        'game_CI': interval(matched, 'game_id'), 'week_CI': interval(matched, 'week'),
                        'position_deltas': {p: {'n': sum(x['position'] == p for x in matched),
                                              'additional_wins': sum(x['delta'] for x in matched if x['position'] == p)}
                                            for p in sorted({x['position'] for x in matched})}})
    proper = []
    for metric in ['Brier', 'log_loss']:
        matched = []
        for r in rows:
            if r['arm'] != 'A1_BACKFIELD_CDF_ROLE_INPUTS' or r['policy'] != 'P2_EXACT_LAW' or r['status'] not in ('WIN', 'LOSS'):
                continue
            s = index['A0_BACKFIELD_CDF', 'P2_EXACT_LAW', r['opportunity_key']]
            event = int(r['actual'] > r['line'])
            def loss(q):
                p = q['p_over']
                if metric == 'Brier':
                    return (p - event)**2
                return float(-np.log(max(1e-15, p if event else 1-p)))
            matched.append({'game_id': r['game_id'], 'week': r['week'], 'delta': loss(r) - loss(s)})
        proper.append({'left': 'A1', 'right': 'A0', 'metric': metric, 'n': len(matched),
                       'delta_left_minus_right': sum(x['delta'] for x in matched) / len(matched),
                       'game_CI': interval(matched, 'game_id'), 'week_CI': interval(matched, 'week')})
    result = {'state': 'PASS_PAIRED_SAVED_GRADE_DIAGNOSTIC', 'protocol': 'FULL_BOARD_UNCERTAINTY_PROTOCOL_V1.json',
              'asof_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'selection_pairs': results, 'probability_pairs': proper,
              'limitations': 'Exposed development; seven weeks, candidate multiplicity; descriptive intervals, no fresh holdout or profitability claim.',
              'CPU_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-start,
              'new_fits_inference_private_bytes': 0}
    (out / 'FULL_BOARD_UNCERTAINTY_RESULTS_V1.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
