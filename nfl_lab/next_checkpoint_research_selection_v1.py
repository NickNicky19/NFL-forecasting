"""Separately identified research startup and future cumulative selection.

This pure decision layer neither edits the original P2 stream nor issues forecasts.
The production owner must admit its exact configuration and future artifact bindings.
"""
from datetime import datetime
import math

VERSION = 'research-informed-provisional-v1'


def initial_choice(category):
    """Select among compatible ready procedures using the frozen recent rule."""
    current = category['incumbent']
    rows = {r['method']: r for r in category['procedures']}
    if current not in rows:
        raise ValueError('incumbent missing from comparison')
    baseline = rows[current]
    reasons, accepted = {}, []
    for method, row in rows.items():
        why = []
        if row['current_product_ready'] is not True:
            why.append('future_artifact_or_consumer_admission_pending')
        if row['product'] != category['product']:
            why.append('different_forecast_product')
        for season in ['2026', '2025']:
            a, b = row.get(season), baseline.get(season)
            if not a or not b or a['population'] != b['population']:
                why.append('missing_or_incompatible_'+season+'_common_panel')
                continue
            if not math.isfinite(a['loss']) or not math.isfinite(b['loss']):
                why.append('nonfinite_primary_'+season)
                continue
            if method != current and (a['loss'] >= b['loss'] if season=='2026' else a['loss'] > b['loss']):
                why.append('no_strict_2026_gain' if season=='2026' else '2025_regression')
        if method != current and row.get('2026') and baseline.get('2026'):
            a, b = row['2026'], baseline['2026']
            for metric in category['secondary_guards']:
                av, bv = a.get(metric), b.get(metric)
                if (not isinstance(av,(int,float)) or isinstance(av,bool)
                        or not isinstance(bv,(int,float)) or isinstance(bv,bool)
                        or math.isnan(av) or math.isnan(bv)
                        or (metric=='log_loss' and (av<0 or bv<0))
                        or (metric!='log_loss' and (not math.isfinite(av) or not math.isfinite(bv)))):
                    why.append('missing_secondary_'+metric)
                elif (abs(av) if metric=='bias' else av) > (abs(bv) if metric=='bias' else bv):
                    why.append('2026_secondary_regression_'+metric)
        reasons[method] = why
        if method != current and not why:
            accepted.append(method)
    # Incumbent tie priority is implicit: an entrant requires a strict improvement.
    chosen = min(accepted, key=lambda m:(rows[m]['2026']['loss'], m)) if accepted else current
    return {'version':VERSION,'category':category['category'],'product':category['product'],
        'primary':category['primary'],'selected':chosen,'incumbent':current,
        'decision':'REPLACE' if chosen!=current else 'RETAIN', 'candidate_reasons':reasons,
        'evidence_lane':'exposed historical development; not genuine P2 or website-relative confirmation'}


def _clock(value):
    t = datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None:
        raise ValueError('timezone required')
    return t


def cumulative_choice(records, *, methods, current, reference, product, primary,
                      epoch, horizon, category, decision_at, expected_resolved_keys):
    """Future-only common-pool selection for a newly activated epoch.

    Callers provide authenticated resolved loss records and preserve their receipts.
    No historical reconstructed rows or original P2 rows are admitted here.
    Missing model attempts retain the last operational choice rather than rank an
    easier hindsight subset. Producer validation remains a separate prerequisite.
    """
    methods = set(methods)
    if current not in methods or reference not in methods:
        raise ValueError('retain/reference must be in catalog')
    seen, pools = set(), {m:{} for m in methods}
    deadline = _clock(decision_at)
    for row in records:
        if (row['epoch']!=epoch or row['horizon']!=horizon or row['category']!=category
                or row['product']!=product or row['primary']!=primary or row['genuine_pregame'] is not True
                or row['qualified_final_outcome'] is not True):
            raise ValueError('incompatible selection record')
        method, key = row['method'], row['opportunity_key']
        if method not in methods or (method,key) in seen:
            raise ValueError('unexpected or duplicate method opportunity')
        if not (_clock(row['information_cutoff']) <= _clock(row['issued_at'])
                <= _clock(row['issue_deadline']) < _clock(row['kickoff'])):
            raise ValueError('not timely genuine pregame issuance')
        if not (_clock(row['kickoff']) <= _clock(row['resolved_at']) <= deadline):
            raise ValueError('future grading unavailable at decision time')
        loss = row['loss']
        if not isinstance(loss,(int,float)) or isinstance(loss,bool) or math.isnan(loss) or loss<0:
            raise ValueError('invalid loss; positive infinity must be retained')
        seen.add((method,key)); pools[method][key]=loss
    keys = [set(pools[m]) for m in sorted(methods)]
    if not keys or not keys[0]:
        return {'selected':current,'reason':'NO_USABLE_EARLIER_COMMON_EVIDENCE','scores':{}}
    if any(k!=set(expected_resolved_keys) for k in keys):
        return {'selected':current,'reason':'INCOMPLETE_COMMON_COVERAGE_RETAIN','scores':{}}
    scores = {m:math.fsum(pools[m][k] for k in sorted(keys[0]))/len(keys[0]) for m in sorted(methods)}
    best = min(scores.values())
    tied = {m for m in methods if scores[m]==best}
    chosen = current if current in tied else reference if reference in tied else min(tied)
    return {'selected':chosen,'reason':'CUMULATIVE_COMMON_EARLIER_LOSS',
        'scores':scores,'opportunities':len(keys[0]),'epoch':epoch,'horizon':horizon,
        'no_losing_week_removed':True,'scientifically_qualified':False}
