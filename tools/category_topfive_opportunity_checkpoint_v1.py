"""Reconcile permitted aggregate evidence; never read player vectors or models.

Inputs are authenticated aggregate projections, not original football evidence.
No new fitting, forecast generation, rescoring or production action occurs here.
The calling integrator owns immutable publication and readback separately.
"""
from pathlib import Path
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
import sys


def encoded(x):
    return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repository-root', required=True)
    ap.add_argument('--importer', required=True)
    ap.add_argument('--importer-sha256', required=True)
    ap.add_argument('--history', required=True)
    ap.add_argument('--targets', required=True)
    ap.add_argument('--input-manifest', required=True)
    ap.add_argument('--manifest-sha256', required=True)
    args = ap.parse_args()
    root = Path(args.repository_root)
    sys.path.insert(0, str(root))
    from nfl_lab.category_topfive_opportunity_registry import load, validate, SCORE_NAMES, score
    manifest_bytes = Path(args.input_manifest).read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == args.manifest_sha256
    refs = json.loads(manifest_bytes)['inputs']
    expected = {str(root/p) for p in ['reports/category-topfive-20261029/public/PUBLIC_RESULTS.json', 'reports/category-topfive-20261029/public/ORDERED_2025_RESULTS.json', 'reports/category-topfive-continuation-20261029/public/RESULTS.json', 'reports/opportunity-four/runtime/history-vector-qa-v2/NATIVE/RESULT.json', 'reports/opportunity-four/runtime/target-vector-qa-v1/NATIVE/RESULT.json']}
    expected |= {str(Path(args.history)/p) for p in ['LEGACY_HISTORY_IMPORTS_V1.json', 'MEDIAN_PUBLIC_RESULTS_V1.json']}
    expected.add(str(Path(args.targets)/'PUBLIC_RESULTS_V1.json'))
    assert {r['path'] for r in refs} == expected
    for ref in refs:
        content = Path(ref['path']).read_bytes()
        assert len(content) == ref['bytes'] and hashlib.sha256(content).hexdigest() == ref['sha256']
    history_acceptance = json.loads((root/'reports/opportunity-four/runtime/history-vector-qa-v2/NATIVE/RESULT.json').read_text())
    target_acceptance = json.loads((root/'reports/opportunity-four/runtime/target-vector-qa-v1/NATIVE/RESULT.json').read_text())
    assert history_acceptance['state'] == 'PASS_INDEPENDENT_SAVED_VECTOR_QA'
    assert target_acceptance['state'] == 'PASS_INDEPENDENT_TARGET_SAVED_VECTOR_QA'
    assert history_acceptance['H4_vs_BASE_bit_equality']['all_recorded_functionals_and_fallbacks'] is True
    p = Path(args.importer)
    assert hashlib.sha256(p.read_bytes()).hexdigest() == args.importer_sha256
    spec = importlib.util.spec_from_file_location('opportunity_aggregate_import', p)
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    folder = root/'reports/opportunity-four'
    registry = load(folder)
    assert not registry['results'], 'one recorded canonical import; do not rerun unchanged'
    fragment = importer.build(root, args.history)
    registry = importer.merge(registry, fragment)
    # Metadata enrichment retains the exact initial declaration. It does not
    # change a mathematical procedure, forecast vector or old registration.
    for method in registry['methods']:
        incoming = next((m for m in fragment['methods'] if m['method_id'] == method['method_id']), None)
        if incoming:
            extra = [x for x in incoming['outputs'] if x['output_id'] not in {o['output_id'] for o in method['outputs']}]
            if extra:
                method.setdefault('metadata_history', []).append({'reason': 'Add located original supported output definitions; no procedure change.', 'previous_outputs': copy.deepcopy(method['outputs'])})
                method['outputs'] += extra
        if method['method_id'] in {'m:LEAF_CDF', 'm:CDF_H4_HISTORICAL_RELATION_CURRENT_STATE'}:
            method.update(shortlist_group='base-annual-cdf-reference', shortlist_group_panels=['original-primary-role-2026-W1-6'], shortlist_group_reason='Independent saved-vector QA verifies all515 recorded means/medians/fallbacks identical on this2026panel; original training identities remain distinct, no global model equality claim.')
        if method['method_id'] in {'m:TGT_RECENT3_MEAN', 'm:TGT_RECENT8_MEAN'}:
            method.update(shortlist_group='target-recent-history-controls', shortlist_group_reason='Two declared windows in one simple recent-history family; both results retained without padding the shortlist.')
        if method['method_id'].startswith('m:TGT_'):
            method.setdefault('metadata_history', []).append({'reason': 'Exact portable protocol now published before fit.', 'previous_code': copy.deepcopy(method['code'])})
            method['code'] = [{'record': 'https://github.com/NickNicky19/NFL-forecasting/blob/7395ef22cbad73e4da961ade563baf8636a792d3/config/category-topfive-targets-frozen-v1.science.json', 'scope': 'Exact pre-inference public scientific configuration and portable sources.'}]
    history = json.loads((Path(args.history)/'MEDIAN_PUBLIC_RESULTS_V1.json').read_text())
    targets = json.loads((Path(args.targets)/'PUBLIC_RESULTS_V1.json').read_text())
    for doc, resource_key in [(history, 'usage'), (targets, 'usage')]:
        rid = doc.get('run_id', 'r:'+doc['version'])
        chain = [r for r in registry['runs'] if r['run_id'] == rid]
        old = chain[-1]
        assert old['status'] == 'RUNNING'
        terminal = copy.deepcopy(old)
        terminal.update(run_record_id=rid+'@3', run_version=3, supersedes_run_record_id=old['run_record_id'], status='COMPLETED')
        terminal['finish'] = {'record': 'reports/'+('category-topfive-opportunity-four-history-20261029/MEDIAN_PUBLIC_RESULTS_V1.json' if doc is history else 'category-topfive-opportunity-targets-v1-20261029/PUBLIC_RESULTS_V1.json'), 'at_UTC': doc.get('finished_at_UTC', doc.get('execution_receipt', {}).get('completed_at_UTC')), 'state': doc['state']}
        terminal['resources'] = doc[resource_key]
        registry['runs'].append(terminal)
        exp = next(x for x in registry['experiments'] if x['experiment_id'] == old['experiment_id'])
        exp['previous_status'] = exp['status']; exp['status'] = 'COMPLETED'
    history_qa = 'runtime/history-vector-qa-v2/PUBLIC_RECEIPT.json'
    for row in registry['results']:
        if row['run_id'] == history['run_id']:
            row['independent_QA'] = {'state': 'PASS_SAVED_VECTORS_AND_ARITHMETIC', 'record': history_qa, 'original_QA_v1': 'FAILED_RETAINED reviewer imposed stricter horizon; v2 separately registered. No forecasts changed.'}
    source = 'reports/category-topfive-opportunity-targets-v1-20261029/PUBLIC_RESULTS_V1.json'
    comparison = {'target': 'rec_tgt', 'season': 2026, 'weeks': [1,2,3,4,5,6], 'population_id': 'provider-target-v1-primary-RB-WR-TE-fixed2458', 'outcome_version': 'raw-weekly-target-qualification-v3', 'horizon_id': 'original-kickoff-left-limit-not-issued-T90', 'source_policy_id': 'original-permitted-seven-day-reconstruction', 'fallback_policy_id': 'target-frozen-prior-registered-fullsystem-v1', 'evidence_kind': 'current_vintage_reconstruction_exposed_development', 'comparison_set_id': 'target-frozen2022-2025-2026W1-6-v1'}
    for method, products in targets['primary_results'].items():
        for functional in ['mean', 'median', 'distribution']:
            if functional == 'distribution' and method not in ['TGT_CDF_BASE', 'TGT_ROLE_PRIOR']:
                continue
            if functional == 'median' and method not in ['TGT_CDF_BASE', 'TGT_ROLE_PRIOR']:
                continue
            met = products['mean' if functional == 'distribution' else functional]
            scores = {n: score(None, 'Not supported for this product on these observations.') for n in SCORE_NAMES}
            if functional == 'distribution':
                proper = products['proper']
                scores['CRPS'] = score(proper['CRPS'])
                loss = proper['log_loss']
                scores['log_loss'] = score(float('inf'), 'Impossible event retained with complete denominator.') if loss['state'] == 'POSITIVE_INFINITY' else score(loss['value'])
            else:
                for key in ['MAE','MSE','RMSE','bias','p90_AE','p95_AE','strict_error_lt1','inclusive_error_le1']:
                    scores[key] = score(met[key])
                scores['exact_count_rate'] = score(met['exact_count'], met['exact_count_reason'] or 'Registered integer lower median; no rounding.')
            rid = 'y:targets-v1:'+method+':'+functional
            registry['results'].append({'result_id': rid, 'run_id': 'r:'+targets['version'], 'method_id': 'm:'+method, 'output_id': functional, 'comparison': copy.deepcopy(comparison), 'scores': scores,
                'coverage': {k: met[k] for k in ['planned','scored','games','weeks']},
                'missingness': {k: met[k] for k in ['participation','played_zero','played_missing','fallbacks']},
                'evidence_label': 'NEW_EXPERIMENT', 'validity': 'VALID',
                'comparator': targets['paired_primary_vs_recent8'] if method == 'TGT_CDF_BASE' and functional == 'median' else {'record': source, 'scope': 'Same fixed population; no invented website comparator.'},
                'uncertainty': {'record': source, 'game_week': targets['paired_primary_vs_recent8'] if method == 'TGT_CDF_BASE' and functional == 'median' else None, 'multiplicity': 'Exposed development, finite method selection, nominal intervals; no durable superiority claim.'},
                'adverse': ['CDF median has worse MSE and signed bias than recent8 mean; loss in Week6; strict <1 rate lower. Separate primary/secondary objectives.', 'Original timing reconstruction; historical provider-credit exceptions and Week7 source remain unresolved.'],
                'private_evidence': {'state': 'REDACTED', 'record': 'reports/category-topfive-opportunity-targets-v1-20261029/PUBLIC_EXECUTION_READBACK_V1.json', 'route': 'Retained owner approved authenticated private restoration; restricted fields are not public.'},
                'readiness': 'RESEARCH_RESULT_NOT_OPERATIONALLY_ADMITTED', 'source_record': source,
                'weekly_and_reproduction_record': source, 'independent_QA': {'state': 'PASS_SAVED_VECTORS_AND_ARITHMETIC', 'record': 'runtime/target-vector-qa-v1/PUBLIC_RECEIPT.json', 'limits': 'No model regeneration of CRPS or off-host restore.'}})
    registry['publications'].append({'publication_id': 'p:targets-results-v1', 'subjects': [r['result_id'] for r in registry['results'] if r['comparison']['target'] == 'rec_tgt'], 'state': 'PUBLICATION_PENDING', 'commit': None, 'readback_record': None})
    check = validate(registry)
    # All records append; no earlier result/run is deleted or silently corrected.
    for key, filename in [('methods','METHOD_REGISTRY.json'),('experiments','EXPERIMENT_REGISTRY.json'),('results','ALL_RESULTS.json'),('publications','PUBLICATION_RECORDS.json')]:
        (folder/filename).write_bytes(encoded({'schema_version': registry['schema_version'], 'records': registry[key]}))
    previous = load(folder)['runs']
    known = {r['run_record_id'] for r in previous}
    with (folder/'RUN_EVENTS.jsonl').open('a') as f:
        for r in registry['runs']:
            if r['run_record_id'] not in known:
                f.write(encoded(r).decode())
    (folder/'IMPORT_RECEIPT_V1.json').write_bytes(encoded({'state':'AGGREGATE_IMPORT_COMPLETE_PUBLICATION_PENDING','validation':check,'input_manifest_sha256':args.manifest_sha256,'exact_aggregate_inputs':[{'filename':Path(r['path']).name,'bytes':r['bytes'],'sha256':r['sha256']} for r in refs],'new_import_fits_forecasts_scoring_NFL_decodes_HTTP_CAS':0,'sources':fragment['import_notes'],'limitations':['This is a scoped accessible import, not lifetime-complete recovery.','Point summaries do not establish over/under or EV accuracy.']}))
    print(json.dumps(check))


if __name__ == '__main__':
    main()
