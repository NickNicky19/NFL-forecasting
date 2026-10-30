"""Public-safe append-only opportunity experiment index and comparable rankings.

This module reads aggregate records only. It never acquires data, fits models,
issues forecasts, dispatches jobs or publishes to GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

VERSION = 'opportunity-four-registry-v1'
TARGETS = ('pass_att', 'rush_att', 'rec_tgt', 'rec')
EVIDENCE = {'VERIFIED_FROM_CODE', 'REPRODUCED_FROM_DATA', 'REPORTED_NOT_REPRODUCED', 'NEW_EXPERIMENT', 'UNKNOWN/BLOCKED'}
STATES = {'REGISTERED', 'BLOCKED', 'RUNNING', 'RESUMABLE', 'COMPLETED', 'FAILED', 'INTERRUPTED', 'CANCELED', 'FITTED_NOT_FORECASTED', 'FORECASTED_NOT_SCORED', 'DEFERRED_BY_OWNER_SCOPE_CHANGE'}
COMPARABILITY = ('target', 'season', 'weeks', 'population_id', 'outcome_version', 'horizon_id', 'source_policy_id', 'fallback_policy_id', 'evidence_kind', 'comparison_set_id')
SCORE_NAMES = ('MAE', 'MSE', 'RMSE', 'bias', 'p90_AE', 'p95_AE', 'exact_count_rate', 'strict_error_lt1', 'inclusive_error_le1', 'CRPS', 'log_loss', 'Brier')
REDACTED_ROUTE = 'Retained owner approved authenticated private restoration; restricted fields are not public.'
FORBIDDEN = re.compile(r'/workspace/|/tmp/|sediment://|s3://|gh[pousr]_[A-Za-z0-9]{20,}|sk-proj-[A-Za-z0-9_-]{16,}|ODDS_API_KEY\s*[:=]\s*[A-Za-z0-9]{8,}')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def score(value=None, reason='Not reported or unsupported on this evidence population.'):
    if value is None:
        return {'state': 'UNAVAILABLE', 'value': None, 'reason': reason}
    value = float(value)
    if math.isinf(value):
        return {'state': 'POSITIVE_INFINITY' if value > 0 else 'NEGATIVE_INFINITY', 'value': None, 'reason': reason}
    if not math.isfinite(value):
        raise ValueError('NaN is unavailable with a reason, never a numeric score')
    return {'state': 'FINITE', 'value': value, 'reason': None}


def _unique(records, field):
    values = [r[field] for r in records]
    if any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values):
        raise ValueError('missing/duplicate '+field)
    return {r[field]: r for r in records}


def _required(record, fields, label):
    missing = set(fields)-set(record)
    if missing:
        raise ValueError(label+' missing '+repr(sorted(missing)))


def _safe(value):
    if isinstance(value, str) and FORBIDDEN.search(value):
        raise ValueError('prohibited secret/private location in public record')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('JSON nonfinite numbers must use explicit score states')
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or FORBIDDEN.search(key):
                raise ValueError('prohibited public dictionary key')
            if key.lower() in {'raw_rows', 'private_storage_path', 'player_id', 'player_name', 'secret_value', 'api_key_value', 'odds_api_key', 'api_key', 'access_token', 'client_secret', 'password'}:
                raise ValueError('restricted public field '+key)
            _safe(item)
    if isinstance(value, list):
        for item in value:
            _safe(item)


def validate(registry):
    _safe(registry)
    if registry['schema_version'] != VERSION:
        raise ValueError('registry schema identity required')
    methods = _unique(registry['methods'], 'method_id')
    experiments = _unique(registry['experiments'], 'experiment_id')
    _unique(registry['runs'], 'run_record_id')
    runs = latest_runs(registry['runs'])
    results = _unique(registry['results'], 'result_id')
    publications = _unique(registry['publications'], 'publication_id')
    for method in methods.values():
        _required(method, ('original_id', 'family', 'procedure_version', 'algorithm', 'formula', 'outputs', 'code', 'feature_policy', 'training_rule', 'aliases'), 'method')
        _unique(method['outputs'], 'output_id')
        if 'shortlist_group' in method and (not isinstance(method['shortlist_group'], str) or not method['shortlist_group'] or not method.get('shortlist_group_reason')):
            raise ValueError('related-procedure shortlist group requires an explicit reason')
        for output in method['outputs']:
            functional = output.get('functional')
            if functional not in {'mean', 'median', 'empirical_point', 'distribution', 'probability'}:
                raise ValueError('explicit supported output functional required')
            if functional == 'distribution' and output.get('primary_score') not in {'CRPS', 'log_loss'}:
                raise ValueError('distribution requires declared proper score')
            if functional == 'probability' and output.get('primary_score') not in {'Brier', 'log_loss'}:
                raise ValueError('probability cannot be selected by point MAE')
    for exp in experiments.values():
        _required(exp, ('request_id', 'method_ids', 'hypothesis', 'history_policy', 'sources', 'population', 'cutoff', 'budget', 'status', 'registration', 'owner'), 'experiment')
        if exp['status'] not in STATES or not set(exp['method_ids']) <= set(methods):
            raise ValueError('unregistered experiment state/method')
        if not exp['registration'].get('record'):
            raise ValueError('discoverable registration required')
    for run in registry['runs']:
        _required(run, ('experiment_id', 'original_id', 'status', 'origin', 'start', 'finish', 'resources', 'software_checks', 'evidence', 'publication_subject'), 'run')
        if run['experiment_id'] not in experiments or run['status'] not in STATES or run['origin'] not in {'IMPORTED', 'EXECUTED_HERE'}:
            raise ValueError('run linkage/origin/state invalid')
        if run['origin'] == 'EXECUTED_HERE' and run['status'] not in {'REGISTERED', 'BLOCKED', 'DEFERRED_BY_OWNER_SCOPE_CHANGE'}:
            if not run['start'].get('record'):
                raise ValueError('launched run requires durable start')
            if run['status'] not in {'RUNNING', 'RESUMABLE'} and not run['finish'].get('record'):
                raise ValueError('terminal run requires finish/failure/interruption record')
        if run['origin'] == 'IMPORTED' and not run['evidence'].get('original_record'):
            raise ValueError('imported run needs original identity/source')
    for pub in publications.values():
        _required(pub, ('subjects', 'state', 'commit', 'readback_record'), 'publication')
        if pub['state'] not in {'PUBLICATION_COMPLETE', 'PUBLICATION_PENDING'}:
            raise ValueError('publication state invalid')
        if pub['state'] == 'PUBLICATION_COMPLETE' and not (pub.get('commit') and pub.get('readback_record')):
            raise ValueError('publication complete requires immutable commit and readback evidence')
        if pub['state'] == 'PUBLICATION_COMPLETE' and not re.fullmatch('[0-9a-f]{40}', pub['commit']):
            raise ValueError('publication commit must be an immutable40hexGitidentity')
    populations = {}
    for result in results.values():
        _required(result, ('run_id', 'method_id', 'output_id', 'comparison', 'scores', 'coverage', 'evidence_label', 'validity', 'missingness', 'comparator', 'uncertainty', 'adverse', 'private_evidence', 'readiness', 'source_record'), 'result')
        if result['run_id'] not in runs or result['method_id'] not in methods:
            raise ValueError('result must link to actual run and method')
        if result['method_id'] not in experiments[runs[result['run_id']]['experiment_id']]['method_ids']:
            raise ValueError('result method was not registered for its run')
        if result['output_id'] not in {o['output_id'] for o in methods[result['method_id']]['outputs']}:
            raise ValueError('result output contract not declared by method')
        if result['evidence_label'] not in EVIDENCE or result['validity'] not in {'VALID', 'INVALIDATED', 'UNVERIFIED'}:
            raise ValueError('evidence or validity state invalid')
        _required(result['comparison'], COMPARABILITY, 'comparison')
        if result['comparison']['target'] not in TARGETS:
            raise ValueError('nonfocus new result in four-category result registry')
        if not result['source_record']:
            raise ValueError('original result source required')
        _required(result['scores'], SCORE_NAMES, 'scores')
        for name, item in result['scores'].items():
            state, val = item.get('state'), item.get('value')
            if state == 'FINITE':
                if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                    raise ValueError('finite score must be finite numeric')
                if name != 'bias' and val < 0:
                    raise ValueError('negative loss/rate unsupported')
                if name.endswith('_rate') or name in {'strict_error_lt1', 'inclusive_error_le1'}:
                    if not 0 <= val <= 1:
                        raise ValueError('rate outside [0,1]')
            elif state in {'UNAVAILABLE', 'POSITIVE_INFINITY', 'NEGATIVE_INFINITY'}:
                if val is not None or not item.get('reason'):
                    raise ValueError('missing/nonfinite score needs null and reason')
                if state == 'NEGATIVE_INFINITY':
                    raise ValueError('negative infinite loss not supported')
            else:
                raise ValueError('unsupported score state')
        n = result['coverage'].get('scored')
        planned = result['coverage'].get('planned')
        if isinstance(n, bool) or isinstance(planned, bool) or not isinstance(n, int) or not isinstance(planned, int) or not 0 <= n <= planned:
            raise ValueError('coverage needs integer0<=scored<=planned')
        if any(s['state'] in {'FINITE', 'POSITIVE_INFINITY'} for s in result['scores'].values()) and n <= 0:
            raise ValueError('numeric accuracy needs supported denominator')
        if result['validity'] == 'VALID' and any(s['state'] in {'FINITE', 'POSITIVE_INFINITY'} for s in result['scores'].values()):
            key = json.dumps(result['comparison'], sort_keys=True)
            signature = tuple(result['coverage'].get(x) for x in ('planned', 'scored', 'games', 'weeks'))
            if key in populations and populations[key] != signature:
                raise ValueError('incompatible population/denominators require a separate comparison panel')
            populations[key] = signature
    correction_parents = {}
    for result in results.values():
        parent = result.get('supersedes_result_id')
        if parent:
            if parent == result['result_id'] or parent not in results or not result.get('correction_reason'):
                raise ValueError('correction needs distinct known predecessor and reason')
            old = results[parent]
            if any(result[k] != old[k] for k in ('run_id', 'method_id', 'output_id')) or result['comparison'] != old['comparison']:
                raise ValueError('changed run/product/population requires separately registered comparison, not score correction')
            correction_parents[result['result_id']] = parent
    for start in correction_parents:
        seen = set()
        node = start
        while node in correction_parents:
            if node in seen:
                raise ValueError('cyclic score correction')
            seen.add(node)
            node = correction_parents[node]
    return {'state': 'PASS', 'methods': len(methods), 'experiments': len(experiments), 'runs': len(runs), 'results': len(results), 'publications': len(publications)}


def publication_state(registry, subject):
    records = [p for p in registry['publications'] if subject in p['subjects']]
    return records[-1]['state'] if records else 'PUBLICATION_PENDING'


def latest_runs(records):
    groups = {}
    for record in records:
        groups.setdefault(record['run_id'], []).append(record)
    latest = {}
    terminal = STATES-{'REGISTERED', 'BLOCKED', 'RUNNING', 'RESUMABLE'}
    for run_id, rows in groups.items():
        rows = sorted(rows, key=lambda r: r['run_version'])
        for i, row in enumerate(rows):
            if row['run_version'] != i+1 or row.get('supersedes_run_record_id') != (rows[i-1]['run_record_id'] if i else None):
                raise ValueError('run versions require an unbroken append-only chain')
            if i and rows[i-1]['status'] in terminal and not row.get('correction_reason'):
                raise ValueError('terminal record correction requires a recorded reason')
        latest[run_id] = rows[-1]
    return latest


def leaderboard(registry):
    validate(registry)
    methods = {m['method_id']: m for m in registry['methods']}
    runs = latest_runs(registry['runs'])
    superseded = set()
    by_result = {r['result_id']: r for r in registry['results']}
    for result in registry['results']:
        old = result.get('supersedes_result_id')
        if old:
            if old not in by_result or not result.get('correction_reason'):
                raise ValueError('corrected result needs predecessor and reason')
            superseded.add(old)
    groups = {}
    for r in registry['results']:
        if r['result_id'] in superseded or r['validity'] != 'VALID' or runs[r['run_id']]['status'] != 'COMPLETED':
            continue
        if publication_state(registry, r['result_id']) != 'PUBLICATION_COMPLETE':
            continue
        output = next(o for o in methods[r['method_id']]['outputs'] if o['output_id'] == r['output_id'])
        objectives = [('point_MAE', 'MAE')] if output['functional'] in {'mean', 'median', 'empirical_point'} else [(output.get('primary_score'), output.get('primary_score'))]
        if output['functional'] == 'mean':
            objectives.append(('expected_mean_MSE', 'MSE'))
        for objective, metric in objectives:
            if metric not in r['scores'] or r['scores'][metric]['state'] not in {'FINITE', 'POSITIVE_INFINITY'}:
                continue
            key = json.dumps({'comparison': r['comparison'], 'objective': objective}, sort_keys=True, separators=(',', ':'))
            item = {'method_id': r['method_id'], 'output_id': r['output_id'], 'functional': output['functional'], 'loss': r['scores'][metric]['value'], 'loss_state': r['scores'][metric]['state'], 'result_id': r['result_id'], 'coverage': r['coverage'], 'readiness': r['readiness']}
            group = groups.setdefault(key, {})
            old = group.get(r['method_id'])
            if old is None or _rank(item) < _rank(old):
                group[r['method_id']] = item
    panels = []
    for key, by_method in sorted(groups.items()):
        context = json.loads(key)
        related = {}
        for item in by_method.values():
            method = methods[item['method_id']]
            related.setdefault(method.get('shortlist_group', method['method_id']), []).append(item)
        ranked = []
        for group_id, members in sorted(related.items()):
            members = sorted(members, key=_rank)
            representative = dict(members[0])
            representative.update(shortlist_group=group_id, grouped_method_ids=[m['method_id'] for m in members], grouped_results=members)
            ranked.append(representative)
        ranked.sort(key=_rank)
        panels.append({**context, 'distinct_procedures': len(by_method), 'shortlist_groups': len(ranked), 'top_up_to5': [{**x, 'rank': i+1} for i, x in enumerate(ranked[:5])], 'shortfall_from5': max(0, 5-len(ranked))})
    return {'schema_version': VERSION, 'generated_from': 'METHOD_REGISTRY, EXPERIMENT_REGISTRY, ALL_RESULTS, RUN_EVENTS and PUBLICATION_RECORDS', 'panels': panels, 'scope': list(TARGETS), 'note': 'No mixing of years/populations/horizons/products; mean and median are views of one procedure. No future-readiness inferred from historical rank.'}


def _rank(item):
    return (math.inf if item['loss_state'] == 'POSITIVE_INFINITY' else item['loss'], item['method_id'], item['output_id'])


def load(root):
    root = Path(root)
    names = {'methods': 'METHOD_REGISTRY.json', 'experiments': 'EXPERIMENT_REGISTRY.json', 'results': 'ALL_RESULTS.json', 'publications': 'PUBLICATION_RECORDS.json'}
    registry = {'schema_version': VERSION}
    for key, name in names.items():
        registry[key] = json.loads((root/name).read_text())['records']
    registry['runs'] = [json.loads(x) for x in (root/'RUN_EVENTS.jsonl').read_text().splitlines() if x.strip()]
    return registry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='reports/opportunity-four')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    reg = load(args.root)
    report = validate(reg)
    generated = encoded(leaderboard(reg))
    target = Path(args.root)/'FOUR_CATEGORY_LEADERBOARD.json'
    if args.write:
        target.write_bytes(generated)
    elif target.read_bytes() != generated:
        raise ValueError('leaderboard is stale; regenerate from canonical records')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
