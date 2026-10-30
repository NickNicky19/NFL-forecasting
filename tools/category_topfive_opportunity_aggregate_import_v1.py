"""Public aggregate import preparation only: no NFL rows, models, fits or network.

The caller owns review, canonical mutation, publication and remote readback.
All imported runs retain original identities; a reconciliation is not a fit.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

VERSION = 'opportunity-four-aggregate-import-v1'
FOCUS = {'pass_att', 'rush_att', 'rec'}
B246 = 'b246e44b5fa85ea46a0b6294d1347709933a5fb2'
BACKFIELD = 'dab293cb7577c66e33abd29b263ea05abf99a274'
BASE = 'https://github.com/NickNicky19/NFL-forecasting/blob/'
ROUTE = 'Retained owner approved authenticated private restoration; restricted fields are not public.'


def read(path):
    return json.loads(Path(path).read_text())


def url(commit, path):
    return BASE + commit + '/' + path


def short(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def method_id(name):
    return 'm:' + {'FROZEN_CDF_MEAN': 'LEAF_CDF', 'BASE_CDF_CACHED': 'LEAF_CDF',
        'ORDERED_CDF_CACHED': 'ORDERED_CDF',
        'CDF_H3_TIME_WEIGHTED_FIXED365_TRAINING': 'CDF_H3_TIME_WEIGHTED_TRAINING',
        'CDF_MEAN': 'LEAF_CDF', 'CDF_MEDIAN': 'LEAF_CDF',
        'RESPONSE_CDF_MEAN': 'RESPONSE_CDF',
        'COUNT_A_MEAN': 'COUNT_A', 'COUNT_A_CORRECTED_MEAN': 'COUNT_A',
        'COUNT_A_LEGACY_MIXED_POINT_REUSED': 'COUNT_A',
        'CATBOOST_COUNT_MEAN': 'CATBOOST'}.get(name.split(':')[0], name.split(':')[0])


def build(root, history, median_commit=None):
    """Return canonical-shaped fragments; does not write or alter canonical files."""
    root, history = Path(root), Path(history)
    sys.path.insert(0, str(root))
    from nfl_lab.category_topfive_opportunity_registry import SCORE_NAMES, VERSION as SCHEMA, score
    fragment = {k: [] for k in ('methods', 'experiments', 'runs', 'results', 'publications')}
    fragment['schema_version'] = SCHEMA
    methods, experiments = {}, {}
    limits = ['Aggregate import is not a new fit, inference, scoring run or independent NFL outcome.',
        'Original private vectors, labels, artifacts and source rows are not reproduced by this import.',
        'Already exposed reconstruction; original seven-day availability assumption remains.',
        'No matching historical website/R0 or authentic offered-line/price result is invented.',
        'Week 7 remains outside the compatible retained W1-6 main panel.',
        'Publication and fresh-process/off-host restoration are separate checks.',
        'H4 and base-CDF score ties do not establish identical procedures; family padding is prohibited.']
    notes = {'version': VERSION, 'new_fits_forecasts_scores_NFL_decodes_HTTP_CAS': 0,
        'inventory_limits': limits, 'source_receipts': [], 'unavailable_records': [],
        'merge_policy': 'Append IDs only. Preserve existing method/run declarations; root reviews any metadata enrichment.',
        'publication': 'PENDING: caller must push permitted records and independently read them back.'}

    def source(path, commit):
        p = root/path
        data = p.read_bytes()
        notes['source_receipts'].append({'record': url(commit, path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'remote_readback_by_importer': False})
        return json.loads(data), url(commit, path)

    def ensure_method(mid, original, family, definition, ref, details=None):
        if mid in methods:
            return
        methods[mid] = {'method_id': mid, 'original_id': original, 'family': family,
            'procedure_version': 'Original frozen procedure; exact per-result source/version retained',
            'algorithm': definition, 'formula': definition,
            'outputs': [],
            'code': [{'record': ref, 'scope': 'Public scientific definition/configuration; private exact bindings require approved restoration.'}],
            'feature_policy': 'Original earlier-only feature contract; exact group additions and older memory disclosed in linked source.',
            'training_rule': 'Original chronological annual/weekly rule, unchanged by aggregate import.',
            'aliases': [], 'details': details or {}}

    def add_exp(run, mids, ref, state='COMPLETED', history_policy=None, activity=None):
        eid, rid = 'e:' + run, 'r:' + run
        if eid not in experiments:
            experiments[eid] = {'experiment_id': eid, 'request_id': 'owner-opportunity-four-20261029-import-preserved-work',
                'method_ids': sorted(set(mids)), 'hypothesis': 'Preserve original requested comparison and every located result/failure; see original source.',
                'history_policy': history_policy or 'Original procedure; importing aggregates does not select a new history.',
                'sources': [{'record': ref, 'timing': 'Original source and availability contract retained.'}],
                'population': {'record': ref, 'scope': 'Exact original supported player-games; unknown participation is not zero.'},
                'cutoff': 'Original historical/pregame identity as explicitly recorded per result.',
                'budget': {'original_activity': activity or {}, 'new_import_fits': 0, 'consumed_original_allocations': 'PRESERVED_NOT_REFUNDED'},
                'status': state, 'registration': {'record': ref, 'import_registration': 'Retrospective metadata import, not a new predictive launch.'},
                'owner': 'Original NFL-forecasting session; production lease and V2 studies unchanged'}
            fragment['runs'].append({'run_record_id': rid+'@1', 'run_id': rid, 'run_version': 1,
                'supersedes_run_record_id': None, 'experiment_id': eid, 'original_id': run,
                'status': state, 'origin': 'IMPORTED', 'start': {'record': None, 'reason': 'Original native start is not reproduced here.'},
                'finish': {'record': ref}, 'resources': activity or {}, 'software_checks': [],
                'evidence': {'original_record': ref, 'import_only': True}, 'publication_subject': rid})
        else:
            experiments[eid]['method_ids'] = sorted(set(experiments[eid]['method_ids']) | set(mids))
        return rid

    def add_result(run, mid, output, target, year, weeks, metrics, ref, panel,
                   comparator=None, uncertainty=None, adverse=None, validity='VALID', new=False, prefix=''):
    # Unproven panels remain separate.
        planned = metrics.get('planned', metrics.get('population_rows', metrics.get('offered', 0)))
        scored = metrics.get('scored', metrics.get('scored_rows', metrics.get('n', 0)))
        coverage = {'planned': int(planned), 'scored': int(scored),
            'games': metrics.get('games', metrics.get('unique_games', 0)), 'weeks': metrics.get('weeks', metrics.get('unique_weeks', len(weeks)))}
        if output not in {o['output_id'] for o in methods[mid]['outputs']}:
            declaration = {'output_id': output, 'functional': output}
            if output == 'distribution':
                declaration['primary_score'] = 'CRPS'
            if not scored:
                declaration.update(state='UNSUPPORTED_NO_PROCEDURE', reason='Requested output absent; no median/PMF inferred from a point objective.')
            methods[mid]['outputs'].append(declaration)
        aliases = {'MAE': ('MAE', 'mae'), 'MSE': ('MSE',), 'RMSE': ('RMSE', 'rmse'), 'bias': ('bias',),
            'p90_AE': ('p90_AE', 'p90_abs', 'p90'), 'p95_AE': ('p95_AE', 'p95_absolute_error', 'p95_abs', 'p95'),
            'exact_count_rate': ('exact_count_rate', 'exact_integer_match'),
            'strict_error_lt1': ('strict_error_lt1', 'error_strict_lt1', 'error_lt1'),
            'inclusive_error_le1': ('inclusive_error_le1', 'error_inclusive_le1', 'error_le1'),
            'CRPS': ('CRPS',), 'log_loss': ('log_loss',), 'Brier': ('Brier',)}
        scores = {n: score(None, 'Not reported for this exact output and population; no cross-output inference.') for n in SCORE_NAMES}
        for name, keys in aliases.items():
            value = next((metrics[k] for k in keys if metrics.get(k) is not None), None)
            if isinstance(value, dict):
                scores[name] = score(float('inf'), 'Impossible events retained in original paired population.') if value.get('state') == 'POSITIVE_INFINITY' else score(value.get('value'))
            elif value is not None:
                scores[name] = score(value)
        if metrics.get('tolerance') == 1:
            for name, key in [('strict_error_lt1', 'strict_within'), ('inclusive_error_le1', 'inclusive_within')]:
                if metrics.get(key) is not None:
                    scores[name] = score(metrics[key])
        if not scored:
            scores = {n: score(None, 'No supported forecasts for this output; median/PMF not supplied by a point-only count learner.') for n in SCORE_NAMES}
        result_id = 'y:' + prefix + short((run, mid, output, target, year, panel))
        result = {'result_id': result_id, 'run_id': run, 'method_id': mid, 'output_id': output,
            'comparison': {'target': target, 'season': year, 'weeks': list(weeks),
                'population_id': panel+'::'+target, 'outcome_version': panel+'::original-qualified-outcomes',
                'horizon_id': 'original-kickoff-left-limit-not-issued-T90',
                'source_policy_id': 'original-permitted-seven-day-reconstruction',
                'fallback_policy_id': 'Original_registered_fallbacks_full_system_population',
                'evidence_kind': 'current_vintage_reconstruction_exposed_development', 'comparison_set_id': panel},
            'scores': scores, 'coverage': coverage,
            'evidence_label': 'NEW_EXPERIMENT' if new else 'REPORTED_NOT_REPRODUCED', 'validity': validity,
            'missingness': {k: metrics[k] for k in ('outcome_states', 'unknown', 'unknown_participation', 'played_missing', 'played_missing_statistic', 'played_zero', 'played_zero_rows', 'dnp', 'fallbacks', 'fallback_planned', 'fallback_scored', 'fallback_rows', 'fallback_offered', 'scored_fallbacks') if k in metrics},
            'comparator': comparator or {'state': 'See original same-panel controls; no invented website-relative gain.'},
            'uncertainty': uncertainty or {'state': 'Not reported for this exact contrast; source may contain separate paired comparisons.'},
            'adverse': adverse or ['Exposed development; matched current website improvement is not established.'],
            'private_evidence': {'state': 'REDACTED', 'route': ROUTE, 'vectors_reproduced_by_import': False},
            'readiness': 'NOT_NEWLY_OPERATIONALLY_ADMITTED', 'source_record': ref,
            'weekly_and_reproduction_record': ref, 'is_new_fit_or_score_by_import': False}
        fragment['results'].append(result)
        return result

    legacy = read(history/'LEGACY_HISTORY_IMPORTS_V1.json')
    old_methods = {m['method_id']: m for m in legacy['methods']}
    for e in legacy['experiments']:
        records = [r for r in legacy['results'] if r['experiment_id'] == e['experiment_id']]
        mids = []
        for r in records:
            m = old_methods[r['method_id']]
            mid = method_id(m['original_method_id']); mids.append(mid)
            ensure_method(mid, m['original_method_id'], m['family'], m['formula'], e['public_source']['url'],
                {'original_method_metadata': {k: m[k] for k in ('algorithm_parameters', 'history_policy', 'preprocessing', 'procedure_version', 'code_config_boundary') if k in m}})
        rid = add_exp(e['original_run_id'], mids, e['public_source']['url'], history_policy={m: old_methods[r['method_id']]['history_policy'] for m, r in zip(mids, records)}, activity=e['original_activity'])
        for r in records:
            pairs = [p for p in legacy['paired_comparisons'][str(r['evaluation_season'])] if p.get('candidate') == r['original_output_id']]
            contrast = [{k: v for k, v in p.items() if k != 'weekly'} for p in pairs]
            add_result(rid, method_id(r['original_output_id']), 'mean', 'pass_att', r['evaluation_season'], r['evaluation_weeks'], r['scores'], r['public_report']['url'],
                'original-primary-role-'+str(r['evaluation_season'])+'-W1-'+str(max(r['evaluation_weeks'])), comparator={'matched_contrasts': contrast}, adverse=e['limits'])
    for f in legacy['original_failed_attempts']:
        ref = f.get('public_report', {}).get('url', legacy['experiments'][0]['public_source']['url'])
        rid = add_exp(f['attempt_id'], [], ref, state='FAILED', activity={k: f[k] for k in ('new_fits', 'model_loads', 'HTTP', 'resource_use') if k in f})
        experiments['e:'+f['attempt_id']]['failure'] = f['reason']
        notes['unavailable_records'].append({'run_id': rid, 'scores': None, 'reason': f['reason'], 'original_state': 'FAILED_RETAINED'})

    agg_path = 'reports/category-topfive-20261029/public/PUBLIC_RESULTS.json'
    agg, aref = source(agg_path, B246)
    aggregate_run = 'current-category-topfive-aggregate-v1-20261029'
    # History mean outputs already imported from original summaries, not counted twice.
    history_names = {r['original_output_id'] for r in legacy['results']}
    for cat in agg['categories']:
        target = cat['target']
        if target not in FOCUS:
            continue
        families = cat['top_up_to5'] + cat.get('remaining_tested_comparable_families', [])
        for family in families:
            for view in family.get('retained_views', []):
                original = view['method']
                if original in history_names:
                    continue
                functional = 'empirical_point' if ('heuristic' in view['product'] or 'NOT_mean' in view['product']) else ('median' if view['product'] == 'median' else 'mean')
                mid = method_id(original)
                ensure_method(mid, original.split(':')[0], family['family'], family['definition'], aref)
                rid = add_exp(aggregate_run, [mid], aref, activity=agg['activity'])
                met = copy.deepcopy(view['metrics'])
                if view['source'] == 'ordered_analog' and functional == 'mean':
                    # Older error_lt1/error_le1 are MEDIAN diagnostics, not mean metrics.
                    for k in ('error_lt1', 'error_le1', 'strict_error_lt1', 'inclusive_error_le1', 'strict_within', 'inclusive_within'):
                        met.pop(k, None)
                add_result(rid, mid, functional, target, 2026, range(1, 7), met, aref,
                    'original-primary-role-2026-W1-6', adverse=agg['scientific_limits'] + ['Underlying source: '+view['source']+'; '+view['comparison_compatibility']])
    for law in agg['new_methods_distribution_and_mean_metrics']:
        if law['target'] in FOCUS:
            mid = method_id(law['method'])
            rid = add_exp(aggregate_run, [mid], aref, activity=agg['activity'])
            met = {k: v for k, v in law['metrics'].items() if k in ('CRPS', 'log_loss', 'planned', 'scored', 'games', 'weeks', 'outcome_states', 'played_missing', 'fallback_planned', 'fallback_scored')}
            add_result(rid, mid, 'distribution', law['target'], 2026, range(1, 7), met, aref,
                'original-primary-role-2026-W1-6', adverse=['Original law scores retained; no matched base-law improvement inferred.'])

    opath = 'reports/category-topfive-20261029/public/ORDERED_2025_RESULTS.json'
    ordered, oref = source(opath, B246)
    bpath = 'reports/category-topfive-continuation-20261029/public/RESULTS.json'
    backfield, bref = source(bpath, BACKFIELD)
    for doc, ref, run in [(ordered, oref, ordered['version']), (backfield, bref, backfield['version'])]:
        for row in doc['results']:
            for name, products in row['products'].items():
                mid = method_id(name)
                definition = 'Original '+name+'; exact frozen scientific configuration and comparator contracts in linked study.'
                ensure_method(mid, name, name, definition, ref)
                rid = add_exp(run, [mid], ref, history_policy={'training_seasons': doc['training_seasons'], 'rule': 'Frozen annual; original feature updates and cutoff unchanged.'}, activity={k: doc[k] for k in ('new_fits', 'new_trees', 'new_pregame_forecasts', 'usage') if k in doc})
                for functional, met in products.items():
                    if functional not in ('mean', 'median'):
                        continue
                    is_candidate = name in ('ORDERED_CDF', 'BACKFIELD_CDF')
                    uncertainty = {'game': row['game_interval'], 'week': row['week_interval']} if is_candidate and functional == 'median' else None
                    if is_candidate and 'ordered_game_interval' in row:
                        uncertainty = {**(uncertainty or {}), 'versus_ordered': row['ordered_game_interval']}
                    add_result(rid, mid, functional, row['target'], doc['evaluation_season'], doc['weeks'], met, ref,
                        'original-primary-role-'+str(doc['evaluation_season'])+'-W1-'+str(max(doc['weeks'])),
                        comparator={'BASE_median_MAE_delta': row['candidate_minus_control_MAE']} if is_candidate and functional == 'median' else None,
                        uncertainty=uncertainty, adverse=[doc['interpretation']])
                proper = row.get('proper_distribution_secondary', {}).get(name)
                if isinstance(proper, dict):
                    met = dict(products['median']); met.update({k: proper[k] for k in ('CRPS', 'log_loss') if k in proper})
                    for k in ('MAE', 'MSE', 'RMSE', 'bias', 'p90_AE', 'p95_AE', 'strict_error_lt1', 'inclusive_error_le1'):
                        met.pop(k, None)
                    add_result(rid, mid, 'distribution', row['target'], doc['evaluation_season'], doc['weeks'], met, ref,
                        'original-primary-role-'+str(doc['evaluation_season'])+'-W1-'+str(max(doc['weeks'])), adverse=['No matched base full-law rescore; point control does not establish a distribution gain.'])

    # Parent owns median run completion and QA records.
    median = read(history/'MEDIAN_PUBLIC_RESULTS_V1.json')
    mref = url(median_commit, 'reports/category-topfive-opportunity-four-history-20261029/MEDIAN_PUBLIC_RESULTS_V1.json') if median_commit else 'reports/category-topfive-opportunity-four-history-20261029/MEDIAN_PUBLIC_RESULTS_V1.json'
    for name, products in median['metrics'].items():
        mid = method_id(name)
        ensure_method(mid, name, 'Empirical leaf CDF history policy', 'Original retained-law median; exact original mean replay required before freeze.', mref)
        pairs = [p for p in median['paired'] if p['method'] == name and p['functional'] == 'median']
        result = add_result(median['run_id'], mid, 'median', 'pass_att', 2026, range(1, 7), products['median'], mref,
            'original-primary-role-2026-W1-6', comparator={'matched_contrasts': pairs}, uncertainty={'matched_contrasts': pairs},
            adverse=median['limitations'], new=True, prefix='median-')
        result['private_evidence']['manifests'] = median['private_evidence']
        result['independent_QA'] = median['independent_QA']
        result['is_new_fit_or_score_by_import'] = False
    fragment['methods'] = list(methods.values())
    fragment['experiments'] = list(experiments.values())
    fragment['publications'] = [{'publication_id': 'p:'+VERSION,
        'subjects': [x['result_id'] for x in fragment['results']], 'state': 'PUBLICATION_PENDING',
        'commit': None, 'readback_record': None}]
    fragment['import_notes'] = notes
    return fragment


def merge(existing, fragment):
    """Append fragment records without modifying original canonical declarations."""
    out = copy.deepcopy(existing)
    keys = {'methods': 'method_id', 'experiments': 'experiment_id', 'runs': 'run_record_id', 'results': 'result_id', 'publications': 'publication_id'}
    for group, key in keys.items():
        known = {r[key] for r in out[group]}
        for row in fragment[group]:
            if row[key] not in known:
                out[group].append(copy.deepcopy(row)); known.add(row[key])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--history', required=True)
    parser.add_argument('--median-commit')
    parser.add_argument('--out', required=True, help='New review fragment only, never a canonical file.')
    args = parser.parse_args()
    fragment = build(args.root, args.history, args.median_commit)
    from nfl_lab.category_topfive_opportunity_registry import load, validate
    check = validate(merge(load(Path(args.root)/'reports/opportunity-four'), fragment))
    target = Path(args.out)
    if target.exists() or 'reports/opportunity-four' in str(target):
        raise ValueError('Review output must be a new noncanonical file')
    data = (json.dumps(fragment, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if len(data) > 393216:
        raise ValueError('Bounded import fragment exceeds384KiB; no write performed')
    target.write_bytes(data)
    print(json.dumps({'state': 'AGGREGATE_IMPORT_FRAGMENT_PREPARED', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'merged_validation': check, 'NFL_fits_forecasts_scores_models_HTTP_CAS': 0}))


if __name__ == '__main__':
    main()
