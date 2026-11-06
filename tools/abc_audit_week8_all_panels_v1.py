"""Extend the same A-owned W8 source qualification to numerical/board records.

No side, threshold, model output, original grade or Top Picks membership changes.
Retains a private versioned evidence overlay; C remains the common evaluator.
"""
from pathlib import Path
import collections
import datetime
import gzip
import hashlib
import io
import json
import math
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/abc-championship/audit-remediation-20261105'


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def encode(x):
    return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def main():
    started, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (1610612736, 1610612736))
    resource.setrlimit(resource.RLIMIT_CPU, (110, 120))
    signal.alarm(175)
    sys.path.insert(0, str(ROOT))
    import nfl_lab
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    store, _ = open_store(ROOT, allocation_sha256=
        'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO)
    parent_path = OUT / 'A_WEEK8_PRESENCE_QUALIFICATION_V1.json'
    parent = json.loads(parent_path.read_bytes())
    archive = store.forward_root / 'research/week8-original-grade-v2-batch-20261102/A_LOCAL_WEEK8_REGRADING_V2_20261103.zip'
    ref = parent['source_grade_archive']
    got = store.validate_reference(archive, ref['sha256'])
    if got['bytes'] != ref['bytes']:
        raise ValueError('immutable original evidence differs')
    with zipfile.ZipFile(archive) as z:
        members = {name: z.read(name) for name in z.namelist()}
    manifest = json.loads(members['MANIFEST.json'])
    for name, r in manifest.items():
        if len(members[name]) != r['bytes'] or hashlib.sha256(members[name]).hexdigest() != r['sha256']:
            raise ValueError('source/grade member differs')
    rows = json.loads(gzip.decompress(members['GRADED_ROWS.json.gz']))
    report = json.loads(members['REPORT.json'])
    games = report['schedule']
    if len(games) != 14 or not all(g['final'] for g in games):
        raise ValueError('finality differs from frozen outcome version')
    stats, cross, back = {}, {}, {}
    for r in json.loads(members['sleeper_stats.json']):
        if r['season'] not in (2026, '2026') or r['week'] != 8 or r['season_type'] != 'regular' or r['category'] != 'stat':
            raise ValueError('source outcome contract differs')
        matching = [g['game_id'] for g in games if {g['home'], g['away']} == {r['team'], r['opponent']}]
        if len(matching) != 1:
            raise ValueError('ambiguous source event')
        gid = matching[0]
        pg = str(r['game_id'])
        if cross.setdefault(pg, gid) != gid or back.setdefault(gid, pg) != pg:
            raise ValueError('provider event mapping differs')
        key = (str(r['player_id']), gid)
        if key in stats and stats[key] != r:
            raise ValueError('source version conflict')
        stats[key] = r

    def qualify(row, kind):
        original = row['result'] if kind == 'board_comparison' else row['status']
        out = dict(row, original_measurement_state=original, qualified_measurement_state=original)
        keys = ['rush_yd', 'rec_yd'] if row['category'] == 'rush_rec_yd' else \
            ['rush_td', 'rec_td'] if row['category'] == 'anytime_td' else \
            ['pts_ppr'] if row['category'] == 'fpts' else [row['category']]
        source = stats.get((str(row['player_id']), row['game_id']), {})
        if row.get('team') and source and row['team'] != source['team']:
            raise ValueError('forecast/outcome team differs')
        raw = source.get('stats')
        presence = ('MISSING_SOURCE_ROW' if not isinstance(raw, dict) else
            'EXPLICIT_UNKNOWN' if any(k in raw and not finite(raw[k]) for k in keys) else
            'ABSENT_REQUIRED_COMPONENT' if any(k not in raw for k in keys) else
            'EXPLICIT_FINITE_REQUIRED_COMPONENTS')
        out['source_presence'] = presence
        eligible = original in ('WIN', 'LOSS', 'PUSH') if kind == 'board_comparison' else original == 'SUPPORTED'
        if eligible:
            if presence != 'EXPLICIT_FINITE_REQUIRED_COMPONENTS':
                out['qualified_measurement_state'] = 'MISSING_ACTUAL'
            else:
                actual = sum(raw[k] for k in keys)
                if row['category'] == 'anytime_td':
                    actual = int(actual > 0)
                if not finite(row.get('actual')) or row['actual'] != actual:
                    raise ValueError('retained actual differs from explicit source')
        out['qualified_absolute_error'] = None
        out['qualified_squared_error'] = None
        out['qualified_signed_error'] = None
        if kind == 'numerical' and out['qualified_measurement_state'] == 'SUPPORTED' and finite(row.get('point')):
            err = row['point'] - row['actual']
            out.update(qualified_absolute_error=abs(err), qualified_squared_error=err * err,
                qualified_signed_error=err)
        return out

    all_rows, summaries = {}, []
    for kind in ['numerical', 'board_comparison']:
        original = rows[kind]
        identities = [(r['group'], str(r['player_id']), r['game_id'], r['category']) for r in original]
        if len(identities) != len(set(identities)):
            raise ValueError('duplicate fixed method/player/game/category opportunity')
        qualified = [qualify(r, kind) for r in original]
        all_rows[kind] = qualified
        for group, category in sorted({(r['group'], r['category']) for r in qualified}):
            rr = [r for r in qualified if (r['group'], r['category']) == (group, category)]
            base = {'kind': kind, 'group': group, 'category': category, 'issued_or_board_rows': len(rr),
                'games': len({r['game_id'] for r in rr}), 'player_games': len({(r['player_id'], r['game_id']) for r in rr}),
                'original_states': dict(collections.Counter(r['original_measurement_state'] for r in rr)),
                'qualified_states': dict(collections.Counter(r['qualified_measurement_state'] for r in rr)),
                'transitions': [{'from': a, 'to': b, 'rows': n} for (a, b), n in sorted(collections.Counter(
                    (r['original_measurement_state'], r['qualified_measurement_state']) for r in rr).items())]}
            if kind == 'board_comparison':
                base['sides'] = {}
                for side in ['over', 'under', 'combined']:
                    ss = rr if side == 'combined' else [r for r in rr if r['side'] == side]
                    c = collections.Counter(r['qualified_measurement_state'] for r in ss)
                    n = c['WIN'] + c['LOSS']
                    base['sides'][side] = {'selected': len(ss), 'wins': c['WIN'], 'losses': c['LOSS'],
                        'decided': n, 'hit_rate': c['WIN'] / n if n else None, 'states': dict(c)}
            else:
                valid = [r for r in rr if r['qualified_absolute_error'] is not None]
                old = [r for r in rr if r['original_measurement_state'] == 'SUPPORTED' and finite(r.get('point')) and finite(r.get('actual'))]
                n = len(valid)
                base['numerical'] = {'original_scored': len(old), 'qualified_scored': n,
                    'MAE': math.fsum(r['qualified_absolute_error'] for r in valid) / n if n else None,
                    'MSE': math.fsum(r['qualified_squared_error'] for r in valid) / n if n else None,
                    'RMSE': math.sqrt(math.fsum(r['qualified_squared_error'] for r in valid) / n) if n else None,
                    'signed_bias': math.fsum(r['qualified_signed_error'] for r in valid) / n if n else None,
                    'original_MAE': math.fsum(abs(r['point'] - r['actual']) for r in old) / len(old) if old else None}
            summaries.append(base)
    # The immutable original member already retains identities, values, sides
    # and grades. Store lossless qualification deltas by bound member ordinal,
    # rather than duplicating those restricted originals in a larger archive.
    overlay = {'version': 'A-W8-MEASUREMENT-OVERLAY-v1', 'source_archive': ref,
        'source_member': manifest['GRADED_ROWS.json.gz'],
        'row_overlays': {kind: [dict(member_row=i, **{k: r[k] for k in
            ['original_measurement_state', 'qualified_measurement_state', 'source_presence',
             'qualified_absolute_error', 'qualified_squared_error', 'qualified_signed_error']})
            for i, r in enumerate(rr)] for kind, rr in all_rows.items()}}
    body = gzip.compress(encode(overlay), mtime=0)
    if len(body) > 524288:
        raise ValueError('private overlay retention limit exceeded')
    dest = store.forward_root / 'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_WEEK8_MEASUREMENT_OVERLAY_V1.json.gz'
    store.write_bytes(dest, body)
    private = store.validate_reference(dest, hashlib.sha256(body).hexdigest())
    store.verify_retained_checkpoint()
    result = {'id': 'A-W8-ALL-PANELS-MEASUREMENT-QUALIFICATION-v1',
        'state': 'APPENDED_MEASUREMENT_QUALIFICATION_NOT_FORECAST_OR_POLICY_CHANGE',
        'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'parent_original_decisions_receipt_sha256': hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        'source_grade_archive': ref, 'frozen_outcome_asof_UTC': report['asof_UTC'],
        'private_overlay': {k: private[k] for k in ['bytes', 'sha256']},
        'private_readback': 'PASS_OWNER_LOCAL_OFFHOST_UNVERIFIED',
        'row_counts': {kind: len(rr) for kind, rr in all_rows.items()}, 'summaries': summaries,
        'new_fits_model_forecasts_side_rules_threshold_grader_changes': 0,
        'limitations': ['Absent-metric completeness not verified in bound records; not a claim absent true value was nonzero.',
            'Original grades and predictions remain intact. A more selective denominator is not predictive improvement.',
            'Source issue vintage and bookmaker settlement remain as originally recorded, not newly authenticated.',
            'One frozen Week8 outcome source, not a refresh of subsequent statistic corrections or five-week qualification.'],
        'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - started}
    (OUT / 'A_WEEK8_ALL_PANELS_QUALIFICATION_V1.json').write_bytes(encode(result))
    print(json.dumps({'state': result['state'], 'row_counts': result['row_counts'],
        'summaries': len(summaries), 'private_overlay': result['private_overlay'], 'CPU_seconds': result['CPU_seconds']}))
    signal.alarm(0)


if __name__ == '__main__':
    main()
