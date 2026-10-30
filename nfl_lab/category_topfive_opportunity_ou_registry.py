"""Public aggregate/link validation; no private rows, fitting or selection."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path

PROCEDURES = {
    **{f'P1_{x}': 'P1_POINT_DIRECTION_V1' for x in ['F', 'FC', 'M', 'H', 'OFFERED_LINE']},
    **{f'P2_CONDITIONAL_{x}': 'P2_CONDITIONAL_V1' for x in ['F', 'FC', 'FS', 'M', 'H']},
    'P2_F_FULL': 'P2_F_FULL_THRESHOLD_V1',
    'ALWAYS_OVER': 'ALWAYS_OVER_UNDER_CONTROLS',
    'ALWAYS_UNDER': 'ALWAYS_OVER_UNDER_CONTROLS',
    'P50_DECISIVE_CONTROL': 'CONSTANT_HALF_PROBABILITY_CONTROL',
}
STATS = ('CORRECT', 'INCORRECT', 'PUSH_STATISTIC', 'ABSTAIN', 'UNRESOLVED')
BOOKS = ('WIN', 'LOSS', 'PUSH', 'VOID', 'PENDING', 'UNRESOLVED', 'ABSTAIN')
POOLS = ('FULL_CANONICAL', 'P1_COMMON_ORIGINAL_OFFER_RULE', 'P2_COMMON_ORIGINAL_OFFER_RULE')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def count(value):
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, 'nonnegative integer count required')
    return value


def validate(aggregate, policy, index, registry):
    """Validate every aggregate's denominators and exact run/policy linkage."""
    from nfl_lab.category_topfive_opportunity_registry import _safe
    for document in [aggregate, policy, index]:
        _safe(document)
    require(index['run_id'] in {x['run_id'] for x in registry['runs']}, 'missing canonical run')
    latest = next(x for x in reversed(registry['runs']) if x['run_id'] == index['run_id'])
    require(latest['status'] == 'COMPLETED', 'linked scoring run is not completed')
    require(index['experiment_id'] == latest['experiment_id'], 'wrong experiment')
    require(index['evidence_tier'] == 'DESCRIPTIVE_TIMING_UNVERIFIED_RECONSTRUCTION', 'unqualified evidence upgrade')
    require(set(PROCEDURES.values()) <= {x['policy_id'] for x in policy['rules']}, 'unregistered side policy')
    require(aggregate['activity']['new_fits'] == aggregate['activity']['new_statistic_forecasts'] == aggregate['activity']['new_pregame_capture'] == 0, 'rescoring is not a new fit/capture')
    seen = set()
    for row in aggregate['summaries']:
        token = tuple(row[x] for x in ['season', 'target', 'pool', 'procedure', 'period'])
        require(token not in seen, 'duplicate summary identity'); seen.add(token)
        require(row['target'] in ['pass_att', 'rush_att', 'rec'], 'unqualified target market')
        require(row['season'] in [2024, 2026], 'wrong/excluded season')
        require(row['procedure'] in PROCEDURES, 'unregistered procedure')
        require(row['pool'] in POOLS and row['period'] == 'SEASON', 'unknown pool or period')
        n = count(row['offered_decisions']); supported = count(row['supported_statistic_rows'])
        require(supported <= n, 'supported exceeds offered')
        require(set(row['statistical_status_counts']) == set(STATS), 'missing statistical states')
        require(set(row['book_settlement_counts']) == set(BOOKS), 'missing settlement states')
        require(sum(count(v) for v in row['statistical_status_counts'].values()) == n, 'statistic denominator')
        require(sum(count(v) for v in row['book_settlement_counts'].values()) == n, 'settlement denominator')
        require(all(row['book_settlement_counts'][x] == 0 for x in ['WIN', 'LOSS', 'PUSH', 'VOID']), 'unqualified bookmaker settlement')
        s = row['statistical_status_counts']; decisive = s['CORRECT'] + s['INCORRECT']
        require(n - s['UNRESOLVED'] == supported, 'supported/status population mismatch')
        require(row['decisive_selected_denominator'] == decisive, 'wrong hit denominator')
        expected = s['CORRECT'] / decisive if decisive else None
        require(row['correct_over_decisive_selected'] == expected, 'wrong/null hit rate')
        require(set(row['by_selected_side']) == {'over', 'under'}, 'unknown/missing side')
        require(set(row['selected_sides']) <= {'over', 'under', 'abstain'}, 'unknown selected side')
        require(sum(count(v) for v in row['selected_sides'].values()) == n, 'selected sides population')
        for side in ['over', 'under']:
            x = row['by_selected_side'][side]
            require(sum(count(x[k]) for k in ['correct', 'incorrect', 'statistic_push', 'unresolved']) == count(x['selected']), 'side denominator')
            require(count(x['decisive']) == x['correct'] + x['incorrect'], 'side decisive denominator')
            require(x['selected'] == row['selected_sides'].get(side, 0), 'side/top selected mismatch')
            require(set(x['book_settlement_counts']) == set(BOOKS), 'missing side settlement states')
            require(sum(count(v) for v in x['book_settlement_counts'].values()) == x['selected'], 'side settlement denominator')
            require(all(x['book_settlement_counts'][k] == 0 for k in ['WIN', 'LOSS', 'PUSH', 'VOID', 'ABSTAIN']), 'unqualified side bookmaker settlement')
        for side_key, stat_key in [('correct', 'CORRECT'), ('incorrect', 'INCORRECT'), ('statistic_push', 'PUSH_STATISTIC')]:
            require(sum(x[side_key] for x in row['by_selected_side'].values()) == s[stat_key], 'side/status count mismatch')
        require(s['ABSTAIN'] <= row['selected_sides'].get('abstain', 0), 'known abstentions exceed selected abstentions')
        require(sum(x['unresolved'] for x in row['by_selected_side'].values()) <= s['UNRESOLVED'], 'selected unresolved exceeds population')
        for k in BOOKS:
            expected = sum(x['book_settlement_counts'][k] for x in row['by_selected_side'].values())
            if k == 'ABSTAIN': expected += row['selected_sides'].get('abstain', 0)
            require(expected == row['book_settlement_counts'][k], 'side/top settlement mismatch')
        for metric, denominator in [('point_MAE', 'point_rows'), ('point_MSE', 'point_rows'), ('Brier_decisive', 'Brier_rows'), ('full_statistic_Brier', 'full_statistic_Brier_rows')]:
            d = count(row[denominator]); v = row[metric]
            require(d <= supported, 'metric exceeds supported population')
            require((d == 0 and v is None) or (d > 0 and isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0), 'missing/invalid metric')
            if metric == 'Brier_decisive' and v is not None: require(v <= 1, 'binary Brier outside support')
            if metric == 'full_statistic_Brier' and v is not None: require(v <= 2, 'multiclass Brier outside support')
        for name in ['strict_error_lt1', 'inclusive_error_le1', 'close_and_correct_strict_rate']:
            v = row[name]
            require((row['point_rows'] == 0 and v is None) or (row['point_rows'] > 0 and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1), 'invalid tolerance rate')
        for metric in ['log_loss_decisive', 'full_statistic_log_loss']:
            x = row[metric]; d = count(x['denominator']); impossible = count(x['impossible_events'])
            require(impossible <= d <= supported, 'log loss denominator')
            require(d == row['Brier_rows' if metric == 'log_loss_decisive' else 'full_statistic_Brier_rows'], 'proper scores use different populations')
            require((d == 0 and x['state'] == 'UNAVAILABLE' and x['value'] is None) or
                    (d > 0 and impossible > 0 and x['state'] == 'POSITIVE_INFINITY' and x['value'] is None) or
                    (d > 0 and impossible == 0 and x['state'] == 'FINITE' and isinstance(x['value'], (float, int)) and not isinstance(x['value'], bool) and math.isfinite(x['value']) and x['value'] >= 0), 'infinity/empty log loss state')
    require(len(seen) == index['season_summaries'], 'missing aggregate summaries')
    require(len(aggregate['weekly']['rows']) == index['weekly_rows'], 'missing weekly summaries')
    require(len(aggregate['paired_contrasts']) == index['paired_contrasts'], 'missing paired contrasts')
    weekly_seen = set()
    require(aggregate['weekly']['columns'] == ['season', 'target', 'common_pool', 'procedure', 'week', 'offered', 'correct', 'incorrect', 'statistic_push', 'abstain', 'unresolved', 'point_MAE', 'decisive_Brier', 'Brier_rows', 'games'], 'wrong weekly schema')
    for row in aggregate['weekly']['rows']:
        require(len(row) == 15, 'wrong weekly row width')
        token = tuple(row[:5]); require(token not in weekly_seen, 'duplicate weekly identity'); weekly_seen.add(token)
        year, target, pool, proc, week = token
        require(year in [2024, 2026] and target in ['pass_att', 'rush_att', 'rec'] and pool in ['P1', 'P2'] and proc in PROCEDURES and 1 <= count(week) <= (5 if year == 2026 else 18), 'wrong weekly identity')
        require(sum(count(v) for v in row[6:11]) == count(row[5]), 'weekly status denominator')
        require(count(row[13]) <= row[5] - row[10] - row[8] and count(row[14]) <= row[5], 'weekly scoring denominator')
        require(row[5] != row[10] or row[11] is None, 'weekly point score without supported labels')
        for v in row[11:13]: require(v is None or (isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0), 'weekly invalid score')
        require((row[13] == 0 and row[12] is None) or (row[13] > 0 and row[12] is not None and row[12] <= 1), 'weekly probability score')
    paired_seen = set()
    for row in aggregate['paired_contrasts']:
        token = tuple(row[k] for k in ['season', 'target', 'pool', 'candidate', 'control'])
        require(token not in paired_seen, 'duplicate paired identity'); paired_seen.add(token)
        require(token[0] in [2024, 2026] and token[1] in ['pass_att', 'rush_att', 'rec'] and token[2] in POOLS and token[3] in PROCEDURES and token[4] in PROCEDURES, 'wrong paired identity')
        for name in ['game', 'week']:
            x = row[name]; count(x['paired_rows']); count(x['clusters'])
            require(x['clusters'] <= x['paired_rows'], 'paired clusters exceed rows')
            require(x['paired_rows'] != 0 or (x['clusters'] == 0 and x['candidate_minus_control'] is None and x['nominal95_interval'] is None), 'empty pair needs null score/interval')
            require(x['candidate_minus_control'] is None or (isinstance(x['candidate_minus_control'], (float, int)) and not isinstance(x['candidate_minus_control'], bool) and math.isfinite(x['candidate_minus_control'])), 'invalid paired delta')
    require(all(x['actual_book_settlement'] == 'UNQUALIFIED' and x['new_selection'] is False for x in aggregate['original_paper_exploratory']), 'paper evidence upgrade')
    return {'season_summaries': len(seen), 'weekly_rows': len(aggregate['weekly']['rows']), 'paired_contrasts': len(aggregate['paired_contrasts']), 'private_player_rows_read': 0, 'state': 'PASS_PUBLIC_LINKS_AND_AGGREGATE_DENOMINATORS'}


def generated(aggregate):
    """Native-unit/proper-score ranks only; different selected pools never rank together."""
    panels = []
    for season in [2024, 2026]:
        for target in ['pass_att', 'rush_att', 'rec']:
            for pool, metric, denominator in [('P1_COMMON_ORIGINAL_OFFER_RULE', 'point_MAE', 'point_rows'), ('P2_COMMON_ORIGINAL_OFFER_RULE', 'Brier_decisive', 'Brier_rows')]:
                rows = [r for r in aggregate['summaries'] if r['period'] == 'SEASON' and r['season'] == season and r['target'] == target and r['pool'] == pool and r[metric] is not None]
                require(not rows or len({r[denominator] for r in rows}) == 1, 'ranking requires a common denominator; row identity independently checked in private QA')
                panels.append({'season': season, 'target': target, 'pool': pool, 'metric': metric, 'rows': rows[0][denominator] if rows else 0,
                               'ranked': [{'rank': i + 1, 'procedure': r['procedure'], 'loss': r[metric]} for i, r in enumerate(sorted(rows, key=lambda r: (r[metric], r['procedure'])))],
                               'limit': 'Original matched offers; current website not in this panel. Hit-rate winner not inferred across differently selected rows.'})
    output = io.StringIO(newline='')
    fields = ['season', 'category', 'pool', 'procedure', 'side', 'selected', 'correct', 'incorrect', 'statistic_push', 'unresolved', 'decisive', 'decisive_hit_rate', 'book_WIN', 'book_LOSS', 'book_PUSH', 'book_VOID', 'book_PENDING', 'book_UNRESOLVED', 'book_ABSTAIN']
    writer = csv.DictWriter(output, fields); writer.writeheader()
    for row in aggregate['summaries']:
        for side, x in row['by_selected_side'].items():
            writer.writerow({'season': row['season'], 'category': row['target'], 'pool': row['pool'], 'procedure': row['procedure'], 'side': side,
                             **{k: x[k] for k in ['selected', 'correct', 'incorrect', 'statistic_push', 'unresolved', 'decisive']},
                             'decisive_hit_rate': x['correct'] / x['decisive'] if x['decisive'] else '',
                             **{'book_' + k: v for k, v in x['book_settlement_counts'].items()}})
    return {'evidence': 'TIMING_UNVERIFIED_HISTORICAL_RESEARCH_NOT_LIVE_QUALIFICATION', 'panels': panels}, output.getvalue().encode()


def validate_root(root, registry, write=False):
    root = Path(root); folder = root/'over-under'
    index_file = folder/'RESULT_INDEX.json'
    if not index_file.exists():
        return {'state': 'NO_OU_RESULT_EXTENSION'}
    index = json.loads(index_file.read_bytes()); body = (folder/'OVER_UNDER_RESULTS.json').read_bytes()
    require(hashlib.sha256(body).hexdigest() == index['aggregate_sha256'], 'aggregate binding mismatch')
    aggregate = json.loads(body); policy = json.loads((folder/'OVER_UNDER_POLICY_REGISTRY.json').read_bytes())
    report = validate(aggregate, policy, index, registry)
    leaders, side_csv = generated(aggregate)
    outputs = {folder/'GENERATED_PRODUCT_LEADERS.json': (json.dumps(leaders, sort_keys=True, indent=2, allow_nan=False)+'\n').encode(), folder/'CORRECT_INCORRECT_BY_SIDE.csv': side_csv}
    for path, data in outputs.items():
        if write:
            path.write_bytes(data)
        else:
            require(path.read_bytes() == data, 'stale generated O/U output')
    return report
