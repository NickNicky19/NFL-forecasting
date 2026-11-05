"""Owner's five-week primary-product floor, not a ranking or scientific gate.

Sessions supply provenance-bound scored week records. This helper neither
authenticates sources nor turns retrospective evidence into pregame evidence.
"""
from __future__ import annotations
import collections
import hashlib
import json

VERSION = 'POST-WAVE-5W-v1'
KEYS = ('procedure_version','target','output','role_scope','selection_policy','history_rule')


def canonical_key(key):
    if any(k not in key or key[k] is None for k in KEYS):
        raise ValueError('exact procedure/target/output/role/policy/history key required')
    return json.dumps({k:key[k] for k in KEYS},sort_keys=True,separators=(',',':'))


def evaluate(key, week_records):
    expected = canonical_key(key)
    weeks = {}
    excluded = []
    for row in week_records:
        if canonical_key(row['key']) != expected:
            excluded.append('DIFFERENT_PROCEDURE_PRODUCT_ROLE_OR_POLICY')
            continue
        season, week = row['season'], row['week']
        if type(season) is not int or type(week) is not int or not 1 <= week <= 18:
            raise ValueError('regular-season integer season/week required')
        scored = row['scored_eligible_cases']
        if type(scored) is not int or scored < 0:
            raise ValueError('supported nonnegative scored count required')
        ident = season,week
        previous=weeks.get(ident)
        # Multiple batches/folds/views in one week never create more weeks.
        state='SCORED' if row.get('completed_outcomes') is True and scored>0 else 'EMPTY_OR_UNRESOLVED'
        if previous is None or state=='SCORED':
            weeks[ident]={'season':season,'week':week,'state':state}
    supported=sorted(k for k,v in weeks.items()if v['state']=='SCORED')
    empty=sorted(k for k,v in weeks.items()if v['state']!='SCORED')
    byseason=collections.defaultdict(list)
    for season,week in supported:byseason[str(season)].append(week)
    return {'rule_version':VERSION,'key':key,'key_sha256':hashlib.sha256(expected.encode()).hexdigest(),
            'completed_scored_weeks':[{'season':y,'week':w}for y,w in supported],
            'completed_scored_week_count':len(supported),
            'attempted_empty_or_unresolved_weeks':[{'season':y,'week':w}for y,w in empty],
            'per_season_scored_weeks':dict(byseason),
            'five_week_floor':'PASS'if len(supported)>=5 else'NOT_MET',
            'excluded_different_key_records':len(excluded),
            'operational_admission':'NOT_ESTABLISHED_BY_WEEK_COUNT',
            'superiority_adequate_support_fresh_pregame':'NOT_ESTABLISHED_BY_WEEK_COUNT'}


def require_primary(key,week_records):
    result=evaluate(key,week_records)
    if result['five_week_floor']!='PASS':
        raise ValueError('Primary replacement blocked: fewer than five distinct completed scored test weeks for this exact product/policy')
    return result
