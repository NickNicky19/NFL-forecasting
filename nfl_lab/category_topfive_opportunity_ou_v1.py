"""Decimal comparisons for original numeric offers; no I/O, models or fitting.

Decimal(str(value)) preserves the stored decimal representation, not an
unrecorded higher-precision bookmaker value. Never round or epsilon-tie a side.
Statistical direction and assumed/qualified contract settlement are separate.
"""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, localcontext
import math
import random

VERSION = 'opportunity-four-ou-zero-refit-v1-20261030'
TARGETS = ('pass_att', 'rush_att', 'rec', 'rec_tgt')
TOL = Decimal('0.000000000002')


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def probability(value):
    p = number(value)
    return p if p is not None and 0 <= p <= 1 else None


def point_side(point, line):
    p, threshold = number(point), number(line)
    if p is None or threshold is None:
        return None, 'MISSING_OR_INVALID_POINT_OR_LINE'
    return ('over', None) if p > threshold else ('under', None) if p < threshold else (None, 'POINT_EQUALS_LINE_ABSTAIN')


def conditional_side(p_over):
    p = probability(p_over)
    if p is None:
        return None, 'MISSING_OR_INVALID_CONDITIONAL_PROBABILITY'
    return ('over', None) if p > Decimal('.5') else ('under', None) if p < Decimal('.5') else (None, 'EQUAL_CONDITIONAL_PROBABILITIES_ABSTAIN')


def law(p_over, p_under, p_push):
    values = [probability(x) for x in (p_over, p_under, p_push)]
    if any(p is None for p in values) or abs(sum(values)-1) > TOL:
        return None
    return dict(zip(('over', 'under', 'push'), values))


def law_side(p_over, p_under, p_push):
    p = law(p_over, p_under, p_push)
    if p is None:
        return None, 'MISSING_OR_INVALID_AUTHENTICATED_FULL_LAW'
    if p['over']+p['under'] == 0:
        return None, 'ZERO_DECISIVE_MASS_ABSTAIN'
    return ('over', None) if p['over'] > p['under'] else ('under', None) if p['over'] < p['under'] else (None, 'EQUAL_LAW_SIDE_MASSES_ABSTAIN')


def statistic_event(actual, line, outcome_state):
    """Played-zero is valid; DNP/unknown/missing never become a count zero."""
    if outcome_state != 'supported_played':
        return None
    actual, line = number(actual), number(line)
    if actual is None or line is None or actual < 0 or actual != actual.to_integral_value():
        raise ValueError('Supported four-category outcomes must be explicit nonnegative integer counts')
    return 'over' if actual > line else 'under' if actual < line else 'push'


def log_score(p):
    p = probability(p)
    if p is None:
        return {'state': 'UNAVAILABLE', 'value': None}
    if p == 0:
        return {'state': 'POSITIVE_INFINITY', 'value': None}
    with localcontext() as context:
        context.prec = 40
        return {'state': 'FINITE', 'value': float(-p.ln())}


def grade(decision, actual, state):
    """A frozen decision supplies side and probability semantics explicitly."""
    result = dict(decision)
    event = statistic_event(actual, decision['line'], state)
    result.update(actual=None if number(actual) is None else str(number(actual)),
        outcome_state=state, actual_direction=event, direction_result='UNRESOLVED',
        point_absolute_error=None, point_squared_error=None, point_signed_error=None,
        strict_error_lt1=None, inclusive_error_le1=None, close_and_correct=None,
        Brier=None, log_loss={'state': 'UNAVAILABLE', 'value': None}, full_statistic_Brier=None)
    side = decision['selected_side']
    result['book_settlement_status']='ABSTAIN' if side is None else 'PENDING' if state in ('pending','PENDING') else 'UNRESOLVED'
    if event is not None:
        result['direction_result'] = 'ABSTAIN' if side is None else 'PUSH_STATISTIC' if event == 'push' else 'CORRECT' if event == side else 'INCORRECT'
        point = number(decision.get('point'))
        if point is not None:
            error = point-number(actual); absolute = abs(error)
            result.update(point_absolute_error=str(absolute), point_squared_error=str(error*error), point_signed_error=str(error),
                strict_error_lt1=absolute < 1, inclusive_error_le1=absolute <= 1,
                close_and_correct=(absolute < 1 and result['direction_result'] == 'CORRECT'))
        p = probability(decision.get('conditional_p_over'))
        if p is not None and event != 'push':
            y = Decimal(int(event == 'over'))
            result['Brier'] = str((p-y)**2)
            result['log_loss'] = log_score(p if y else 1-p)
        full = law(*[decision.get('p_'+s) for s in ('over', 'under', 'push')])
        if full is not None:
            result['full_statistic_Brier'] = str(sum((full[s]-int(event == s))**2 for s in full))
            result['full_statistic_log_loss'] = log_score(full[event])
    return result


def decimal_from_american(american):
    value = number(american)
    if value is None or abs(value) < 100 or abs(value) >= 10000:
        return None
    return 1+value/100 if value > 0 else 1+100/abs(value)


def estimated_ev(p_win, p_loss, decimal_odds):
    win, loss, odds = probability(p_win), probability(p_loss), number(decimal_odds)
    if win is None or loss is None or win+loss > 1+TOL or odds is None or odds <= 1:
        return None
    return win*(odds-1)-loss


def assumed_settlement(side, actual, line, state, decimal_odds, contract):
    if contract != 'EXPLORATORY_ASSUMED_REFUND_PUSH_VOID_ACTUAL_BOOK_UNQUALIFIED':
        return None, 'UNQUALIFIED_SETTLEMENT_CONTRACT'
    odds = number(decimal_odds)
    if side not in ('over', 'under') or odds is None or odds <= 1:
        return None, 'MISSING_OR_INVALID_SIDE_PRICE'
    if state == 'known_DNP_void':
        return Decimal(0), 'assumed_DNP_void_refund'
    event = statistic_event(actual, line, state)
    if event is None:
        return None, 'unknown_ungraded'
    if event == 'push':
        return Decimal(0), 'assumed_push_refund'
    return (odds-1, 'assumed_win') if event == side else (Decimal(-1), 'assumed_loss')


def summarize(rows):
    """Coverage and direction denominators are explicit; no generic accuracy."""
    counts = Counter(r['direction_result'] for r in rows)
    decisive = counts['CORRECT']+counts['INCORRECT']
    valid = [r for r in rows if r['actual_direction'] is not None]
    errors = [number(r['point_absolute_error']) for r in valid if r['point_absolute_error'] is not None]
    brier = [number(r['Brier']) for r in valid if r['Brier'] is not None]
    full = [number(r['full_statistic_Brier']) for r in valid if r['full_statistic_Brier'] is not None]
    logs = [r['log_loss'] for r in valid if r['log_loss']['state'] != 'UNAVAILABLE']
    infinite = sum(p['state'] == 'POSITIVE_INFINITY' for p in logs)
    full_logs=[r['full_statistic_log_loss'] for r in valid if 'full_statistic_log_loss' in r]
    full_infinite=sum(p['state']=='POSITIVE_INFINITY' for p in full_logs)
    def mean(values):
        return float(sum(values)/len(values)) if values else None
    result = {'offered_decisions': len(rows), 'supported_statistic_rows': len(valid), 'counts': dict(counts),
        'selected_sides': dict(Counter(r['selected_side'] or 'abstain' for r in rows)),
        'correct_over_decisive_selected': counts['CORRECT']/decisive if decisive else None,
        'decisive_selected_denominator': decisive, 'selection_coverage': sum(r['selected_side'] is not None for r in rows)/len(rows) if rows else None,
        'outcome_states': dict(Counter(r['outcome_state'] for r in rows)),
        'point_MAE': mean(errors), 'point_rows': len(errors),
        'Brier_decisive': mean(brier), 'Brier_rows': len(brier), 'full_statistic_Brier': mean(full), 'full_statistic_Brier_rows': len(full),
        'log_loss_decisive': {'state': 'POSITIVE_INFINITY' if infinite else 'FINITE' if logs else 'UNAVAILABLE',
            'value': None if infinite or not logs else sum(p['value'] for p in logs)/len(logs), 'denominator': len(logs), 'impossible_events': infinite},
        'full_statistic_log_loss': {'state':'POSITIVE_INFINITY' if full_infinite else 'FINITE' if full_logs else 'UNAVAILABLE',
            'value':None if full_infinite or not full_logs else sum(p['value'] for p in full_logs)/len(full_logs),'denominator':len(full_logs),'impossible_events':full_infinite},
        'games': len({r['game_id'] for r in valid}), 'weeks': len({r['week'] for r in valid})}
    point_rows=[r for r in valid if r['point_absolute_error'] is not None]
    result.update(point_MSE=mean([number(r['point_squared_error']) for r in point_rows]),
        point_bias=mean([number(r['point_signed_error']) for r in point_rows]),
        strict_error_lt1=sum(r['strict_error_lt1'] is True for r in point_rows)/len(point_rows) if point_rows else None,
        inclusive_error_le1=sum(r['inclusive_error_le1'] is True for r in point_rows)/len(point_rows) if point_rows else None,
        close_and_correct_strict_rate=sum(r['close_and_correct'] is True for r in point_rows)/len(point_rows) if point_rows else None)
    result['by_selected_side'] = {side: {'selected': sum(r['selected_side'] == side for r in rows),
        'correct': sum(r['selected_side'] == side and r['direction_result'] == 'CORRECT' for r in rows),
        'incorrect':sum(r['selected_side']==side and r['direction_result']=='INCORRECT' for r in rows),
        'statistic_push':sum(r['selected_side']==side and r['direction_result']=='PUSH_STATISTIC' for r in rows),
        'unresolved':sum(r['selected_side']==side and r['direction_result']=='UNRESOLVED' for r in rows),
        'decisive': sum(r['selected_side'] == side and r['direction_result'] in ('CORRECT', 'INCORRECT') for r in rows),
        'book_settlement_counts':{name:sum(r['selected_side']==side and r.get('book_settlement_status','UNRESOLVED')==name for r in rows) for name in ('WIN','LOSS','PUSH','VOID','PENDING','UNRESOLVED','ABSTAIN')}} for side in ('over', 'under')}
    result['statistical_status_counts']={name:counts.get(name,0) for name in ('CORRECT','INCORRECT','PUSH_STATISTIC','ABSTAIN','UNRESOLVED')}
    book=Counter(r.get('book_settlement_status','ABSTAIN' if r['selected_side'] is None else 'UNRESOLVED') for r in rows)
    result['book_settlement_counts']={name:book.get(name,0) for name in ('WIN','LOSS','PUSH','VOID','PENDING','UNRESOLVED','ABSTAIN')}
    return result


def paired(left, right, loss='direction', cluster='game_id'):
    """Matched loss differences; abstentions/pushes are coverage, not losses."""
    a = {r['opportunity_id']: r for r in left}; b = {r['opportunity_id']: r for r in right}
    pairs = []
    for key in sorted(set(a)&set(b)):
        x, y = a[key], b[key]
        if (x['line'], x['actual'], x['outcome_state']) != (y['line'], y['actual'], y['outcome_state']):
            raise ValueError('Paired forecasts must share exact line and outcome version')
        if loss == 'direction':
            if any(r['direction_result'] not in ('CORRECT', 'INCORRECT') for r in (x, y)):
                continue
            delta = int(x['direction_result'] == 'INCORRECT')-int(y['direction_result'] == 'INCORRECT')
        elif loss == 'Brier':
            if x['Brier'] is None or y['Brier'] is None:
                continue
            delta = float(number(x['Brier'])-number(y['Brier']))
        else:
            raise ValueError('Unregistered paired loss')
        pairs.append((str(x[cluster]), delta))
    groups = defaultdict(lambda: [0., 0])
    for key, delta in pairs:
        groups[key][0] += delta; groups[key][1] += 1
    result = {'loss': loss, 'paired_rows': len(pairs), 'clusters': len(groups), 'cluster': cluster,
        'candidate_minus_control': sum(p[1] for p in pairs)/len(pairs) if pairs else None,
        'nominal95_interval': None, 'replicates': 500, 'seed': 1703,
        'state': 'UNAVAILABLE_FEWER_THAN8CLUSTERS' if len(groups) < 8 else 'EXPOSED_DEVELOPMENT_PAIRED_CLUSTER_BOOTSTRAP'}
    if len(groups) >= 8:
        items = list(groups.values()); rng = random.Random(1703); samples = []
        for _ in range(500):
            choices = rng.choices(items, k=len(items)); samples.append(sum(v[0] for v in choices)/sum(v[1] for v in choices))
        samples.sort()
        def quantile(q):
            index = (len(samples)-1)*q; low = math.floor(index); high = math.ceil(index)
            return samples[low]+(samples[high]-samples[low])*(index-low)
        result['nominal95_interval'] = [quantile(.025), quantile(.975)]
    return result
