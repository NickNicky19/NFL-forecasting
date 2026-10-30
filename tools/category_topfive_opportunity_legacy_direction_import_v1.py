"""Copy completed Week6 aggregate direction evidence without regrading NFL rows.

Original three-way confusion and source semantics stay intact. This is not new
P1 abstention scoring, an originally saved recommendation, or a new NFL fit.
"""
from pathlib import Path
import argparse
import hashlib
import json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    body = Path(a.source).read_bytes()
    assert hashlib.sha256(body).hexdigest() == a.sha256
    output = Path(a.out)
    assert not output.exists(), 'one metadata import, do not repeat unchanged'
    source = json.loads(body)
    records = []
    for old in source['grouped_summaries']:
        if old['target'] not in {'pass_att', 'rush_att', 'rec'} or old['field'] != 'line_from':
            continue
        if old['group'] not in {'dk', 'sleeper'}:
            continue
        confusion = old['confusion_three_way']
        records.append({'target': old['target'], 'method_original_id': old['method'],
            'line_source': old['group'],
            'line_semantics': 'Website-recorded DraftKings-attributed provider threshold; upstream quote clock not authenticated.' if old['group'] == 'dk' else 'Sleeper contest threshold; not authenticated sportsbook price or payout.',
            'offered': old['offered_rows'], 'scored': old['scored_rows'],
            'games': old['games'], 'weeks': old['weeks'],
            'reported_point_MAE': old['point_mae'],
            'reported_original_three_way_correct': old['three_way_correct_rows'],
            'reported_original_three_way_rate': old['three_way_accuracy'],
            'original_confusion': confusion,
            'over_correct_reported_cell': confusion['over']['over'],
            'over_incorrect_reported_cell': confusion['over']['under'],
            'over_exact_line_reported_cell': confusion['over']['equal'],
            'under_correct_reported_cell': confusion['under']['under'],
            'under_incorrect_reported_cell': confusion['under']['over'],
            'under_exact_line_reported_cell': confusion['under']['equal'],
            'forecast_equal_original_class': confusion['equal'],
            'point_side_semantics': 'Original fixed point-minus-line class, not proof of a saved website recommendation. Original equality class retained; not silently converted into new P1 decisions.',
            'coverage': {k: old[k] for k in ['eligibility_states', 'participation_states', 'quarantine_states', 'line_clock_vs_cutoff', 'line_clock_vs_kickoff', 'forecast_clock_vs_kickoff']},
            'probability_prices_settlement_returns': {'value': None, 'reason': 'Not supported by this completed point-direction packet.'},
            'evidence_label': 'REPORTED_NOT_REPRODUCED'})
    result = {'version': 'opportunity-four-legacy-week6-direction-import-v1',
        'original_registration': source['registration_id'],
        'season': 2026, 'week': 6, 'source_sha256': a.sha256,
        'source_record': 'reports/recorded-thresholds-v1/aggregate-report.json',
        'original_source_report': 'reports/recorded-thresholds-v1/README.md',
        'records': records, 'source_rows_models_fits_forecasts_grades_read_or_created': 0,
        'scope': 'Only published aggregate cells copied. No private rows restored or independently regraded.',
        'targets_market': 'TARGET_OFFER_UNAVAILABLE',
        'limits': ['Already exposed Week6 evidence; older models and website computation, not current website.',
                   'DraftKings-attributed and Sleeper contest thresholds remain separate.',
                   'Synthetic ours thresholds excluded here and preserved in original packet.',
                   'No new P1/P2/P3 selection comparison, price-qualified return, or paired row uncertainty is inferred.']}
    output.write_text(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n')
    print(json.dumps({'state': 'IMPORTED_REPORTED_AGGREGATES_ONLY', 'records': len(records), 'new_fits_forecasts_NFL_rows': 0}))


if __name__ == '__main__':
    main()
