"""Join permitted release metadata; no model, source-vector or outcome decoding.

Run with --core-manifest pointing to the admitted public-safe core JSON. This
does not invoke a forecasting policy or mark an operational gate complete.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

REPORT = 'reports/category-topfive-mae-release-priority-20261030'
CORE = ('pass_yd', 'pass_td', 'pass_cmp', 'pass_att', 'pass_int', 'rush_yd',
        'rush_att', 'rec', 'rec_yd', 'rush_rec_yd')
ALL = CORE + ('nick-chart-ppr-v1', 'anytime_td', 'rec_tgt')
GATES = ('current_source_and_artifact_bindings', 'future_inference',
         'durable_capture_restore', 'registered_product_catalog_epoch_export',
         'consumer_fallback_rollback', 'retained_owner_admission',
         'genuine_capture_and_served_value_readback')


def digest(path):
    body = path.read_bytes()
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def load(path):
    return json.loads(path.read_text())


def compact_best(row):
    best = row['best_observed']
    return {k: best[k] for k in ('method_id', 'output_id', 'functional', 'loss',
            'loss_state', 'coverage', 'result_id', 'readiness')}


def live_row(category, audit, consumer):
    if category not in audit:
        return {'selected_overlay_rows': 0, 'model_versions': [],
            'procedure_versions': [], 'product_functionals': [],
            'sample_public_value': None, 'sample_reason': 'No such selected product in pinned overlay',
            'consumer_function_equal_saved': 0, 'browser_DOM_observed': False}
    a, c = audit[category], consumer[category]
    assert a['selected_rows'] == c['published_rows'] == c['consumer_values_equal_saved']
    assert c['not_displayable'] == 0
    sample = c['sample_public_value']
    # No player/game ID or restricted row is copied into this derived receipt.
    sample = {k: sample[k] for k in ('row_sha256', 'value', 'formatted_text',
                                     'label', 'product', 'functional')}
    return {'selected_overlay_rows': a['selected_rows'],
        'method_ids': a['method_ids']['exact_values'],
        'model_versions': a['model_versions']['exact_values'],
        'procedure_versions': a['procedure_versions']['exact_values'],
        'product_functionals': a['product_functionals'],
        'original_issue_UTC_range': [a['issue_times']['minimum'], a['issue_times']['maximum']],
        'typed_MAE_rows': a['typed_MAE_rows'],
        'separate_expected_mean_rows': a['separate_expected_mean_rows'],
        'consumer_function_equal_saved': c['consumer_values_equal_saved'],
        'consumer_labels': c['labels'], 'sample_public_value': sample,
        'browser_DOM_observed': False}


def build(root, core_path):
    report = root / REPORT
    inputs = {
        REPORT + '/CURRENT_SERVED_AUDIT_V3.json': report / 'CURRENT_SERVED_AUDIT_V3.json',
        REPORT + '/SERVED_CONSUMER_READBACK_V1.json': report / 'SERVED_CONSUMER_READBACK_V1.json',
        REPORT + '/core/CORE_CATEGORY_MANIFEST_V1.json': core_path,
        'reports/opportunity-four/CURRENT_DECISIONS.json': root / 'reports/opportunity-four/CURRENT_DECISIONS.json',
        'reports/opportunity-four/over-under/TRAINING_HISTORY_CORRECTION_V1.json': root / 'reports/opportunity-four/over-under/TRAINING_HISTORY_CORRECTION_V1.json',
        'reports/next-nfl-checkpoint-20261028/NEXT_CURRENT_MAE_DECISION_V2.json': root / 'reports/next-nfl-checkpoint-20261028/NEXT_CURRENT_MAE_DECISION_V2.json',
        REPORT + '/ordered-chart/ORDERED_CHART_ADMISSION_MANIFEST_V1.json': report / 'ordered-chart/ORDERED_CHART_ADMISSION_MANIFEST_V1.json',
    }
    data = {key: load(path) for key, path in inputs.items()}
    audit, consumer = data[REPORT + '/CURRENT_SERVED_AUDIT_V3.json'], data[REPORT + '/SERVED_CONSUMER_READBACK_V1.json']
    core = data[REPORT + '/core/CORE_CATEGORY_MANIFEST_V1.json']
    decisions = data['reports/opportunity-four/CURRENT_DECISIONS.json']
    old = data['reports/next-nfl-checkpoint-20261028/NEXT_CURRENT_MAE_DECISION_V2.json']
    chart = data[REPORT + '/ordered-chart/ORDERED_CHART_ADMISSION_MANIFEST_V1.json']
    by_a, by_c = ({r['category']: r for r in audit['categories']},
                 {r['category']: r for r in consumer['categories']})
    by_core, by_focus = ({r['target']: r for r in core['rows']},
                        {r['category']: r for r in decisions['rows']})
    by_old = {r['target']: r for r in old['categories']}
    assert set(by_core) == set(CORE)
    assert set(by_focus) == {'pass_att', 'rush_att', 'rec_tgt', 'rec'}
    assert audit['payload_sha256'] == consumer['source_pins']['payload_sha256']
    assert audit['rows'] == consumer['rows'] == 1945
    assert consumer['source_values_unchanged'] is True
    rows = []
    for target in ALL:
        r = {'target': target, 'live_incumbent': live_row(target, by_a, by_c),
            'proposed_core_product': None, 'full_focus_research_leader': None,
            'new_product_operational_gates': {g: 'UNVERIFIED_FOR_NEW_PRODUCT' for g in GATES},
            'new_forecasts': 0, 'new_captures': 0, 'new_MAE_values_published': 0,
            'published_new_MAE_values': None,
            'published_new_MAE_values_reason': 'No genuine newly admitted MAE product capture/publication verified; October30 packaging retains October28 issues.',
            'selected_replacement': None,
            'decision': 'KEEP_ACTUAL_INCUMBENT_PENDING_PRODUCT_SPECIFIC_ADMISSION',
            'scientific_qualification': False}
        if target in by_core:
            c = by_core[target]
            p, e = c['core_candidate'], c['reused_core_evidence']
            r['proposed_core_product'] = {
                'method': e['method'], 'family': p['family'],
                'product': p['forecast_product'], 'functional': p['prediction_functional'],
                'selection_product': p['selection_product'], 'metric': 'MAE',
                'MAE': e['MAE'], 'coverage': e['coverage'], 'diagnostics': e['diagnostics'],
                'lab_comparator': e['lab_comparator'],
                'matched_current_website_loss': e['matched_current_website_loss'],
                'matched_website_loss_reason': e['matched_current_website_loss_reason'],
                'evidence': e['evidence'], 'uncertainty': e['uncertainty'],
                'model_member_sha256': p['manifest_declared_model_member']['sha256'],
                'model_hash_evidence': 'Retained manifest claim; no new model-byte restore in this metadata job',
                'original_procedure_sha256': p['original_procedure_version'],
                'new_procedure_sha256': p['new_procedure_version'],
                'current_restored_wrapper_sha256': p['current_restored_wrapper_sha256'],
                'separate_expected_mean': p['separate_expected_mean'],
                'status': p['status'],
                'not_installed_by_base_admission': 'New ordered/backfield/depth variants need distinct bindings; no forced switch.'}
            r['exact_remaining_action'] = 'Retained producer must authenticate current wrapper map and fresh Week8 SOURCE/query/feature-completion receipts; bind selected typed point/catalog/epoch/export; capture/restore before deadline and integrate validated consumer/fallback/rollback.'
            r['schema_blocker'] = 'Existing V1 count schema rejects added median/expected_mean fields; do not weaken it. Register separately typed MAE catalog/export/consumer.'
        if target in by_focus:
            f = by_focus[target]
            r['full_focus_research_leader'] = {
                **compact_best(f), 'panel': f['primary_panel'],
                'training_history_source': 'reports/opportunity-four/over-under/TRAINING_HISTORY_CORRECTION_V1.json',
                'training_history_note': 'Use appended source-inspected correction; older prose in CURRENT_DECISIONS remains visible.',
                'comparator_and_uncertainty': f['strongest_control_and_uncertainty'],
                'website_relative_gain': 'Not established by this reconstructed panel'}
        if target in ('pass_att', 'rush_att', 'rec'):
            r['core_equals_full_focus_research_leader'] = by_core[target]['core_is_latest_research_leader']
        if target in ('rush_att', 'rec'):
            r['new_family_blocker'] = 'Ordered/backfield needs separately admitted export/session/current source and artifact binding; original ordered fit-clock receipt unresolved. Historical score/source API alone is not admission.'
        if target == 'nick-chart-ppr-v1':
            e = by_old['chart_ppr']['leader']
            r['proposed_core_product'] = {'method': e['method'], 'product': 'point_median',
                'functional': 'full_cdf_lower_median', 'target': target, 'MAE': e['metrics']['MAE'],
                'coverage': {k: e['metrics'][k] for k in ('planned', 'scored', 'games', 'weeks')},
                'evidence': 'Existing same-chart 2026W1-6 reconstructed exposed development; no new predictive run',
                'model_sha256': chart['chart_artifact']['model_sha256'],
                'adapter': 'nick-chart-ppr-mae-future-adapter-v1.1',
                'model_hash_evidence': 'Existing retained artifact identity; no current restore in this job'}
            r['live_incumbent']['status'] = 'NO_SELECTED_NICK_CHART_PPR_PRODUCT'
            r['live_incumbent']['legacy_fallback'] = 'Old-site PPR/R0 fallback remains under original identity; exact legacy scoring contract not authenticated here and must not be relabeled nick-chart-ppr-v1.'
            r['live_incumbent']['fallback_count_reference'] = 'Global PPR_or_unsupported_R0=414 is a combined fallback count, not a verified chart forecast count.'
            r['exact_remaining_action'] = 'V1.1 engineering source ready; retained owner must admit current chart inputs/model/source wrapper, fresh-process restoration and genuine future capture, then exact chart consumer/scoring/fallback/rollback migration.'
        if target == 'anytime_td':
            r['decision'] = 'RETAIN_EXISTING_PROBABILITY_PRODUCT_NO_MAE_OR_EV_MIGRATION'
            r['published_new_MAE_values_reason'] = 'MAE display release does not select a new probability law; existing Brier stream stays separate.'
            r['existing_research_context'] = {'method': by_old[target]['leader']['method'],
                'primary': 'Brier', 'loss': by_old[target]['leader']['metrics']['probability_scores']['Brier'],
                'evidence': 'Dated existing 2026W1-6 development panel; not a new fit, current-site victory or release decision',
                'record': 'reports/next-nfl-checkpoint-20261028/NEXT_CURRENT_MAE_DECISION_V2.json'}
            r['exact_remaining_action'] = 'Keep current admitted probability capture/grading; any probability replacement needs its separate product-specific policy and operational qualification.'
        if target == 'rec_tgt':
            r['decision'] = 'NOT_AVAILABLE_LIVE_KEEP_TARGETS_SEPARATE_FROM_RECEPTIONS'
            r['exact_remaining_action'] = 'Admit provider-target source/true-zero definition, exact current model/future wrapper, restoration and separately typed forecast-only targets catalog/display/grading; no incumbent target forecast or qualified market assumed.'
        rows.append(r)
    assert len(rows) == 13 and {r['target'] for r in rows} == set(ALL)
    return {'version': 'mae-category-release-receipt-v1',
        'state': 'RESULT_SAVED_PUBLICATION_PENDING',
        'at_UTC': datetime.now(timezone.utc).isoformat(),
        'source_bindings': {key: digest(path) for key, path in inputs.items()},
        'website_main_commit': consumer['website_main'], 'payload_sha256': audit['payload_sha256'],
        'payload_bytes': audit['payload_bytes'], 'packaged_at': audit['header']['packaged_at'],
        'payload_website_source_sha': audit['header']['website_source_sha'],
        'scope': 'Existing release engineering only; new predictive research still four-category focus',
        'actual_verification': {'saved_rows': 1945, 'consumer_values_equal_saved': 1945,
            'exact_served_consumer_functions_executed': True, 'browser_DOM_observed': False,
            'all_1945_typed_new_MAE_rows': 0, 'original_issues': 'October28 retained, not October30 forecasts',
            'new_fits_models_forecasts_capture_or_deployment_by_this_builder': 0},
        'fallback_counts_as_original_combined_scopes': audit['fallback_counts'],
        'owner': {'retained_lease': 178, 'research_website_writes': False,
            'existing_delivery': 'https://github.com/NickNicky19/NFL-forecasting/pull/1#issuecomment-6527892507',
            'acknowledgement': 'Not observed in latest originalPR1 refresh; delivery is not execution'},
        'source_review': REPORT + '/runtime/INDEPENDENT_SOURCE_REVIEW_V1.json',
        'core_public_source_pins': core['public_sources'],
        'gate_interpretation': 'All new-product operational gates unverified here; source/fictional software PASS does not set a gate true.',
        'scientific_registrations': 'Unchanged; no scientific qualification claimed',
        'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--core-manifest', type=Path, required=True)
    args = parser.parse_args()
    output = build(args.repository_root, args.core_manifest)
    path = args.repository_root / REPORT / 'runtime/CATEGORY_RELEASE_RECEIPT_V1.json'
    path.write_text(json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'record': str(Path(REPORT) / 'runtime' / path.name), **digest(path),
                     'categories': len(output['rows']), 'new_NFL_runs': 0}, sort_keys=True))
