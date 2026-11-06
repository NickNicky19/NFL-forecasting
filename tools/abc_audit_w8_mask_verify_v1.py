"""Verify corrected A W8 comparison masks and paired controls, without regrading."""
from pathlib import Path
import collections
import datetime
import gzip
import hashlib
import io
import json
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/audit-remediation-20261105'


def encode(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def main():
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (1610612736, 1610612736))
    resource.setrlimit(resource.RLIMIT_CPU, (85, 90))
    signal.alarm(115)
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import nfl_lab
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    store, _ = open_store(ROOT, allocation_sha256=
        'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO, readonly=True)
    archive = store.forward_root / 'research/week8-original-grade-v2-batch-20261102/A_LOCAL_WEEK8_REGRADING_V2_20261103.zip'
    store.validate_reference(archive, 'be9c13b0f42f5e164b29d00cce69fbe1c30acce703d1b33a8103a057888ac2c1')
    overlay = store.forward_root / 'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_WEEK8_MEASUREMENT_OVERLAY_V1.json.gz'
    store.validate_reference(overlay, '2f8df2a10dcbba9074a04e9d2477fb76490311e2fedcbf70fa54c17dfec1f5fa')
    delta = json.loads(gzip.decompress(overlay.read_bytes()))
    with zipfile.ZipFile(archive) as z:
        data = z.read('GRADED_ROWS.json.gz')
    if hashlib.sha256(data).hexdigest() != delta['source_member']['sha256']:
        raise ValueError('original row member differs')
    old = json.loads(gzip.decompress(data))['board_comparison']
    edits = delta['row_overlays']['board_comparison']
    if len(old) != len(edits):
        raise ValueError('overlay cardinality differs')
    groups = collections.defaultdict(dict)
    for i, (r, e) in enumerate(zip(old, edits)):
        if e['member_row'] != i or e['original_measurement_state'] != r['result']:
            raise ValueError('overlay row binding differs')
        key = (str(r['player_id']), r['game_id'], r['category'], r['line'])
        if key in groups[r['group']]:
            raise ValueError('duplicate opportunity')
        groups[r['group']][key] = dict(r, qualified=e['qualified_measurement_state'])
    control = groups['CONTROL_ALWAYS_OVER']
    keys = set(control)
    if len(keys) != 484 or len(groups) != 4 or any(set(v) != keys for v in groups.values()):
        raise ValueError('common original board identity differs')
    for key in keys:
        a = control[key]
        if any(v[key]['actual'] != a['actual'] for v in groups.values()):
            # Missing actuals are JSON null, never NaN or an invented zero.
            raise ValueError('common outcome versions differ')
    panels, pairs = [], []
    for name, rows in groups.items():
        decided = {k for k, r in rows.items() if r['qualified'] in ('WIN', 'LOSS')}
        panels.append({'procedure': name, 'eligible': len(keys),
            'selected_sides': sum(r['side'] in ('over', 'under') for r in rows.values()),
            'abstentions': sum(r['qualified'] == 'ABSTAIN' for r in rows.values()),
            'decided': len(decided),
            'opportunity_identity_sha256': hashlib.sha256(encode(sorted(keys))).hexdigest(),
            'decided_mask_sha256': hashlib.sha256(encode(sorted(decided))).hexdigest()})
        if name.startswith('CONTROL_'):
            continue
        common = sorted(decided & {k for k, r in control.items() if r['qualified'] in ('WIN', 'LOSS')})
        for category in ['ALL_NUMERIC'] + sorted({k[2] for k in common}):
            kk = common if category == 'ALL_NUMERIC' else [k for k in common if k[2] == category]
            by_game = collections.defaultdict(lambda: [0, 0, 0])
            for k in kk:
                by_game[k[1]][0] += rows[k]['qualified'] == 'WIN'
                by_game[k[1]][1] += control[k]['qualified'] == 'WIN'
                by_game[k[1]][2] += 1
            sums = np.asarray(list(by_game.values()), dtype=float)
            n = len(kk)
            draws = np.random.default_rng(1701).integers(0, len(sums), size=(5000, len(sums)))
            totals = sums[draws].sum(axis=1)
            differences = (totals[:, 0] - totals[:, 1]) / totals[:, 2]
            wins = sum(rows[k]['qualified'] == 'WIN' for k in kk)
            cwins = sum(control[k]['qualified'] == 'WIN' for k in kk)
            pairs.append({'procedure': name, 'control': 'CONTROL_ALWAYS_OVER', 'category': category,
                'common_decided': n, 'games': len(by_game), 'wins': wins, 'losses': n - wins,
                'control_wins': cwins, 'control_losses': n - cwins,
                'win_difference': wins - cwins, 'hit_rate_difference': (wins - cwins) / n,
                'game_bootstrap_95_sensitivity': np.quantile(differences, [.025, .975]).tolist(),
                'evidence': 'ONE_EXPOSED_WEEK_TIMING_UNVERIFIED_ACTUAL_LINES;NOT_FUTURE_POLICY_OR_PROFIT'})
    result = {'id': 'A-W8-CORRECTED-MASK-VERIFICATION-v1',
        'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'COMMON_BOARD_OUTCOME_AND_CORRECTED_MASKS_VERIFIED',
        'scoring': 'Uses retained original grades plus presence overlay, no new threshold grader or changed sides.',
        'panels': panels, 'matched_controls': pairs,
        'bootstrap': {'draws': 5000, 'seed': 1701, 'clusters': 'games',
            'qualification': 'Descriptive sensitivity; one week, exposed selected procedures, multiplicity unadjusted.'},
        'new_NFL_forecasts_fits_grades_or_private_bytes': 0,
        'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - start}
    with (OUT / 'A_WEEK8_CORRECTED_MASK_VERIFICATION_V1.json').open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({**{k: v for k, v in result.items() if k not in ['matched_controls']},
        'headline': [r for r in pairs if r['category'] == 'ALL_NUMERIC']}))
    signal.alarm(0)


if __name__ == '__main__':
    main()
