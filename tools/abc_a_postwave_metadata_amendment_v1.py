"""Append two independent-review metadata corrections without new NFL scoring."""
from pathlib import Path
import datetime
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab.opportunity_registry_storage_v1 import read_document, pack_bytes
P = ROOT / 'reports/abc-championship/post-wave-5w-v1'


def main():
    proper = read_document(P / 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V1.json')
    corrected = json.loads(json.dumps(proper))
    for r in corrected['records']:
        if r['kind'] == 'distribution_scores':
            r.pop('probability_score_contract')
            r['distribution_score_contract'] = 'CRPS and negative_log_pmf on the original target support/scoring lattice. Not an actual-line Brier score.'
    corrected['id'] = 'A-PROPER-SCORE-FIVE-WEEK-SUPPLEMENT-v2'
    corrected['supersedes'] = {'path': 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V1.json', 'sha256': hashlib.sha256((P / 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V1.json').read_bytes()).hexdigest(),
                              'reason': 'Distribution-score entries wrongly inherited a probability-contract label; retained metrics, counts, week qualification and original records are unchanged.'}
    pack_bytes(P / 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V2.json', (json.dumps(corrected, indent=2) + '\n').encode())
    index = json.loads((P / 'A_FIVE_WEEK_QUALIFICATION_V3.json').read_bytes())
    unsupported = []; below = []
    for part in index['parts']:
        for r in read_document(P / part['entry'])['records']:
            if r['five_week_floor'] != 'PASS':
                if r['completed_scored_week_count'] == 0:
                    if r['method_alias'] != 'STORED_COUNT_A_MEAN_CONTROL':
                        raise ValueError('unexpected unsupported output; inspect rather than infer')
                    unsupported.append({'key_sha256': r['key_sha256'], 'key': r['key'], 'source_alias': r['method_alias'],
                        'effective_output_support': 'UNSUPPORTED_OUTPUT_NO_FORECAST_OR_SCORE', 'effective_five_week_floor': 'NOT_APPLICABLE',
                        'reason': 'Retained CountA control is mean-only; no median or probability law is invented from it. Zero-output views remain auditable, not tested candidates.'})
                else:
                    below.append({'key_sha256': r['key_sha256'], 'scored_weeks': r['completed_scored_weeks']})
    if len(unsupported) != 5 or len(below) != 10:
        raise ValueError('reviewer nonpassing-view partition differs')
    amendment = {'id': 'A-FIVE-WEEK-QUALIFICATION-AMENDMENT-v4', 'asof_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'base_index': {'path': 'A_FIVE_WEEK_QUALIFICATION_V3.json', 'sha256': hashlib.sha256((P / 'A_FIVE_WEEK_QUALIFICATION_V3.json').read_bytes()).hexdigest()},
        'corrections': unsupported, 'four_week_historical_views': below,
        'combined_main_and_proper_views': {'examined': 800, 'floor_pass': 785, 'below_floor_four_weeks': 10, 'unsupported_output_not_applicable': 5},
        'proper_score_current': 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V2.json',
        'evidence_change': 'Metadata classification/contract labels only; zero fits, inference, grading changes or new NFL outcomes. Original V1/V3 bytes remain.',
        'coordinator': 'C owns shared qualification/admission. Apply this amendment with the exact base, not as a separate championship.'}
    (P / 'A_FIVE_WEEK_QUALIFICATION_AMENDMENT_V4.json').write_text(json.dumps(amendment, indent=2) + '\n')
    report = (P / 'README.md').read_text()
    report = report.replace('A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V1.json', 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V2.json')
    report = report.replace('785/800 views meet the week floor;15 four-week historical carry views do not.',
        '785/800 views meet the week floor; **10 four-week historical views are below the floor, and five nonexistent CountA median/law views are unsupported/N/A**. [Mandatory metadata amendment](A_FIVE_WEEK_QUALIFICATION_AMENDMENT_V4.json) preserves the base index and prevents interpreting these zero-output audit views as tested products.')
    (P / 'README.md').write_text(report)
    receipt = {'id': 'A-POSTWAVE-FINAL-METADATA-REVIEW-v1', 'reviewer': '/root/postwave_readonly_verifier',
        'state': 'SCOPED_METADATA_CORRECTIONS_APPENDED_NO_SCORE_CHANGE', 'measured_CPU_seconds': 0.154594788,
        'unmeasured_initial_index_shape_reads': 'Not asserted zero; no private/model/scoring reads.',
        'checks': ['731+69=800views;785pass,10fourweek,5unsupported', 'all12 category summaries', 'CountA six exact procedure/product/policy views each7weeks; siteTop12 zero', 'corev1.2 hash matches package', 'A3 losses and no current capture/promotion/consumer claim'],
        'corrections': ['Distribution-score CRPS/log-PMF contract labelled separately from half-three-outcome Brier', 'Five zero-output CountA median/law audit views marked unsupported, not four-week tests'],
        'new_NFL_fits_inference_scoring': 0}
    (P / 'FINAL_METADATA_REVIEW_V1.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(amendment['combined_main_and_proper_views']))


if __name__ == '__main__':
    main()
