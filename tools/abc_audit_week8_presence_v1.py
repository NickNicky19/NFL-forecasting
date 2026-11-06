"""Append measurement qualification to fixed A Week8 decisions; no new picks.

Original sides/lines/predictions/grades remain immutable. Explicit finite zeros
stay valid. A missing metric needs its own completeness contract, not just GP.
This is A's contribution to C, not another threshold grader or scheduler.
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
PANELS = [('ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF', 'ALL_RECORDED_LEANS'),
    ('ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF', 'ORIGINAL_TOP_PICKS'),
    ('RECORDED_SELECTED_RANKING_2026-10-28T22:55:49.911448+00:00', 'ORIGINAL_TOP_PICKS')]


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def main():
    start = time.monotonic()
    cpu = time.process_time()
    resource.setrlimit(resource.RLIMIT_AS, (1610612736, 1610612736))
    resource.setrlimit(resource.RLIMIT_CPU, (110, 120))
    signal.alarm(170)
    sys.path.insert(0, str(ROOT))
    import nfl_lab
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    store, _ = open_store(ROOT, allocation_sha256=
        'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO, readonly=True)
    expected = json.loads((ROOT / 'reports/abc-championship/LOCAL_WEEK8_RESULTS_V2.json').read_bytes())
    ref = expected['private_evidence']
    archive = store.forward_root / 'research/week8-original-grade-v2-batch-20261102/A_LOCAL_WEEK8_REGRADING_V2_20261103.zip'
    got = store.validate_reference(archive, ref['sha256'])
    if got['bytes'] != ref['bytes']:
        raise ValueError('original final regrade artifact differs')
    with zipfile.ZipFile(archive) as z:
        members = {name: z.read(name) for name in z.namelist()}
    manifest = json.loads(members['MANIFEST.json'])
    for name, r in manifest.items():
        if len(members[name]) != r['bytes'] or hashlib.sha256(members[name]).hexdigest() != r['sha256']:
            raise ValueError('source/grade member differs')
    original = json.loads(gzip.decompress(members['GRADED_ROWS.json.gz']))
    source = json.loads(members['sleeper_stats.json'])
    report = json.loads(members['REPORT.json'])
    games = report['schedule']
    if len(games) != 14 or not all(r['final'] for r in games):
        raise ValueError('original outcome finality not established')
    stats, cross, back = {}, {}, {}
    for row in source:
        if (row['season'] not in (2026, '2026') or row['week'] != 8
                or row['season_type'] != 'regular' or row['category'] != 'stat'):
            raise ValueError('retained source season/week/stat contract differs')
        matching = [g['game_id'] for g in games if {g['home'], g['away']} == {row['team'], row['opponent']}]
        if len(matching) != 1:
            raise ValueError('source game identity ambiguous')
        provider_game = str(row['game_id'])
        if (cross.setdefault(provider_game, matching[0]) != matching[0]
                or back.setdefault(matching[0], provider_game) != provider_game):
            raise ValueError('reciprocal provider game mapping differs')
        key = (str(row['player_id']), matching[0])
        if key in stats and stats[key] != row:
            raise ValueError('source player/game versions need resolution')
        stats[key] = row
    outcomes = []
    transitions = collections.Counter()
    for row in original['decisions']:
        if (row['group'], row.get('cohort')) not in PANELS:
            continue
        cat = row['category']
        required = ['rush_yd', 'rec_yd'] if cat == 'rush_rec_yd' else \
            ['rush_td', 'rec_td'] if cat == 'anytime_td' else ['pts_ppr'] if cat == 'fpts' else [cat]
        source_row = stats.get((str(row['player_id']), row['game_id']), {})
        raw = source_row.get('stats')
        if row.get('team') and source_row and row['team'] != source_row['team']:
            raise ValueError('retained decision and source team differ')
        prior = row['result']
        new = prior
        reason = 'ORIGINAL_NONDECIDED_STATE_PRESERVED'
        presence = ('MISSING_SOURCE_ROW' if not isinstance(raw, dict) else
            'EXPLICIT_UNKNOWN' if any(name in raw and not finite(raw[name]) for name in required) else
            'ABSENT_REQUIRED_COMPONENT' if any(name not in raw for name in required) else
            'EXPLICIT_FINITE_REQUIRED_COMPONENTS')
        explicit_zero = False
        if prior in ['WIN', 'LOSS', 'PUSH']:
            if not isinstance(raw, dict):
                new, reason, presence = 'MISSING_ACTUAL', 'SOURCE_STAT_ROW_UNAVAILABLE', 'MISSING_SOURCE_ROW'
            elif any(name in raw and not finite(raw[name]) for name in required):
                new, reason, presence = 'MISSING_ACTUAL', 'EXPLICIT_NULL_OR_NONFINITE_REQUIRED_METRIC', 'EXPLICIT_UNKNOWN'
            elif any(name not in raw for name in required):
                new, reason, presence = 'MISSING_ACTUAL', 'ABSENT_METRIC_WITHOUT_VERIFIED_COMPLETENESS_CONTRACT', 'ABSENT_REQUIRED_COMPONENT'
            else:
                presence = 'EXPLICIT_FINITE_REQUIRED_COMPONENTS'
                explicit_zero = any(raw[name] == 0 for name in required)
                source_actual = sum(raw[name] for name in required)
                if cat == 'anytime_td':
                    source_actual = int(source_actual > 0)
                if not finite(row.get('actual')) or row['actual'] != source_actual:
                    raise ValueError('retained grade actual differs from explicit source components')
                reason = 'EXPLICIT_SOURCE_ACTUAL_RECONCILED_ORIGINAL_GRADE_RETAINED'
        outcomes.append({**row, 'original_grade': prior, 'qualified_grade': new,
            'measurement_reason': reason, 'source_presence': presence,
            'contains_explicit_zero_component': explicit_zero})
        transitions[(row['group'], row.get('cohort'), prior, new)] += 1
    population = []
    for panel, expected_count in zip(PANELS, [325, 24, 24]):
        selected = [r for r in outcomes if (r['group'], r.get('cohort')) == panel]
        keys = [(str(r['player_id']), r['game_id'], r['category']) for r in selected]
        if len(selected) != expected_count or len(keys) != len(set(keys)):
            raise ValueError('frozen panel count or opportunity uniqueness differs')
        identity = sorted((str(r['player_id']), r['game_id'], r['category'], r['line'], r['side'])
            for r in selected)
        population.append({'group': panel[0], 'cohort': panel[1], 'rows': len(selected),
            'frozen_identity_line_side_sha256': hashlib.sha256(json.dumps(identity,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()})
    tables = []
    for group, cohort in PANELS:
        rows = [r for r in outcomes if (r['group'], r.get('cohort')) == (group, cohort)]
        categories = sorted({r['category'] for r in rows})
        for category in categories + ['ALL_NUMERIC']:
            selected = rows if category == 'ALL_NUMERIC' else [r for r in rows if r['category'] == category]
            sides = {}
            for side in ['over', 'under', 'combined']:
                ss = selected if side == 'combined' else [r for r in selected if r['side'] == side]
                old = collections.Counter(r['original_grade'] for r in ss)
                new = collections.Counter(r['qualified_grade'] for r in ss)
                denominator = new['WIN'] + new['LOSS']
                sides[side] = {'selected': len(ss), 'original_states': dict(old),
                    'wins': new['WIN'], 'losses': new['LOSS'], 'decided': denominator,
                    'hit_rate': new['WIN'] / denominator if denominator else None,
                    'states': dict(new), 'explicit_zero_component_rows_retained': sum(
                        r['contains_explicit_zero_component'] for r in ss),
                    'source_presence': dict(collections.Counter(r['source_presence'] for r in ss))}
            tables.append({'group': group, 'cohort': cohort, 'category': category,
                'games': len({r['game_id'] for r in selected}),
                'player_games': len({(r['player_id'], r['game_id']) for r in selected}), 'sides': sides})
    output = {'id': 'A-W8-METRIC-PRESENCE-QUALIFICATION-v1',
        'at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'APPENDED_SOURCE_PRESENCE_QUALIFICATION_FIXED_ORIGINAL_DECISIONS',
        'audit_sha256': '720b464f8077d3a483a4a73245690071866b7757fb6d20763c2ea8d931061795',
        'source_grade_archive': {k: ref[k] for k in ['bytes', 'sha256']},
        'retained_source_member': manifest['sleeper_stats.json'],
        'retained_grade_member': manifest['GRADED_ROWS.json.gz'],
        'outcome_asof_UTC': report['asof_UTC'], 'NFL_week': 8, 'season': 2026,
        'final_games': 14, 'selected_rows_inspected': len(outcomes), 'frozen_populations': population,
        'completeness_contract': 'NOT_VERIFIED_FOR_ABSENT_METRICS; participation alone does not establish a missing field is zero.',
        'source_presence_restoration': 'Actual retained direct Sleeper source response, before website compaction; member hash/readback verified.',
        'transitions': [{'group': g, 'cohort': c, 'from': a, 'to': b, 'rows': n}
            for (g, c, a, b), n in sorted(transitions.items())], 'tables': tables,
        'new_model_fits_forecasts_threshold_choices_or_grade_overwrites': 0,
        'limits': ['This appends a stricter measurement-qualification version, not proof an absent true statistic was nonzero.',
            'No count is called confirmed false wins; unsupported old grades are separated from supported explicit finite grades.',
            'Original lines, sides, points, TopPicks membership and all earlier grades remain unchanged.',
            'A single final Week8source version is not a multiweek validation; laterstatcorrections require a separate version.',
            'Venue settlement/ROI remain unverified; no DNP/void inferred from missing actuals.',
            'No new parallel threshold grader: explicit actuals reconciled and original grades reused; metric-evidence qualification appended.'],
        'CPU_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - start}
    with (OUT / 'A_WEEK8_PRESENCE_QUALIFICATION_V1.json').open('x') as f:
        json.dump(output, f, indent=2)
        f.write('\n')
    print(json.dumps({'state': output['state'], 'selected_rows': len(outcomes),
        'totals': [r for r in tables if r['category'] == 'ALL_NUMERIC'], 'CPU_seconds': output['CPU_seconds']}))
    signal.alarm(0)


if __name__ == '__main__':
    main()
