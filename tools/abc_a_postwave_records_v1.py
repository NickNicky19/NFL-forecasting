"""Link completed owner-local post-wave results into A's canonical indexes.

Aggregate metadata only. No source acquisition, models, inference or scoring.
"""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab.opportunity_registry_storage_v1 import read_document, write_document
from nfl_lab.category_topfive_opportunity_registry import SCORE_NAMES, score

P = ROOT / 'reports/abc-championship/post-wave-5w-v1'
R = ROOT / 'reports/opportunity-four'
REL = '../abc-championship/post-wave-5w-v1/'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
MID = 'm:A_CONDITIONAL_PLAYED_CARRY_V1'
EXP = 'e:A-POST-WAVE-CONDITIONAL-CARRY-v1'
ADMIN = 'e:A-POST-WAVE-DIAG-RESTORE-QUALIFICATION-v1'
RUN = 'r:A-POST-WAVE-CONDITIONAL-CARRY-v1'
SUBJECT = 'p:A-POST-WAVE-5W-v1'


def load(path):
    return read_document(path)


def write(path, doc):
    write_document(path, doc)


def append_unique(doc, field, row):
    if row[field] not in {r[field] for r in doc['records']}:
        doc['records'].append(row)


def main():
    a3 = load(P / 'A3_CONDITIONAL_RESULTS_V1.json')
    parity = load(P / 'COUNT_A_RESTORE_AND_PARITY_V3.json')
    q = load(P / 'A_FIVE_WEEK_QUALIFICATION_V3.json')
    proper = load(P / 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V1.json')
    methods = load(R / 'METHOD_REGISTRY.json')
    append_unique(methods, 'method_id', {
        'method_id': MID, 'original_id': 'A3_CONDITIONAL_PLAYED_EXPOSURE',
        'family': 'Conditional exposure marginal; Beta share and uncertain team carries',
        'procedure_version': a3['procedure_version'],
        'algorithm': 'Exact negative-binomial team exposure mixed with Beta-binomial individual share; no joint allocation claim.',
        'formula': 'P(Y=y)=sum_n P(N=n)*BetaBinomial(y;n,alpha,beta); E[Y]=E[N]*raw_forward_filtered_share. No cross-roster normalization conditional on appearance.',
        'outputs': [{'output_id': 'mean', 'functional': 'mean', 'primary_score': 'MAE'},
                    {'output_id': 'median', 'functional': 'median', 'primary_score': 'MAE'},
                    {'output_id': 'exact_line_probability', 'functional': 'probability', 'primary_score': 'Brier'}],
        'code': [{'record': 'nfl_lab/abc_conditional_carry_v1.py', 'sha256': hashlib.sha256((ROOT / 'nfl_lab/abc_conditional_carry_v1.py').read_bytes()).hexdigest()}],
        'feature_policy': 'Same earlier-only raw forward-state share/variance and predicted team exposure as A2; no new injury/snaps/routes feature. C target-share remains C-owned.',
        'training_rule': 'Frozen analytic policy after 2025W1-4 component diagnosis; annual earlier-only state updates. 2025W5-8 and 2026W1-7 already exposed development reconstructions.',
        'aliases': [], 'readiness': 'Historical inference scored; not production admitted; no new genuine pregame packet.'})
    write(R / 'METHOD_REGISTRY.json', methods)

    exps = load(R / 'EXPERIMENT_REGISTRY.json')
    for ident, mids, hypothesis, registration, budget in [
        (EXP, [MID, 'm:BACKFIELD_CDF', 'm:A_DYNAMIC_ROLE_CDF_V1', 'm:A_DYNAMIC_ALLOCATION_V1', 'm:A_RECENCY_ALLOCATION_V1', 'm:COUNT_A'],
         'Conditional-on-appearance individual role marginals avoid normalization over an uncertain future roster; compare unchanged same-input A2 plus strong A0/A1/CountA controls, not a bias offset.',
         'A3_CONDITIONAL_EXPOSURE_PROTOCOL_V1.json', {'CPU_seconds': 480, 'wall_seconds': 600, 'AS_bytes': 1610612736, 'new_private_bytes': 2097152, 'new_optimizer_fits': 0, 'HTTP': 0, 'Monte_Carlo': 0}),
        (ADMIN, ['m:COUNT_A', 'm:A_DYNAMIC_ALLOCATION_V1'],
         'Authenticate existing component accounting, exact CountA restoration and product-specific scored-week provenance; do not count software checks/metadata imports as new NFL tests.',
         'EXECUTION_REGISTRATION_V1.json', {'record': REL + 'EXECUTION_REGISTRATION_V1.json', 'technical_continuations': 'Individually registered files preserve each failed attempt and spent allocation.'})]:
        append_unique(exps, 'experiment_id', {'experiment_id': ident, 'request_id': 'POST-WAVE-5W-v1', 'method_ids': mids,
            'hypothesis': hypothesis, 'history_policy': 'Exact original annual model/earlier-only feature history; no refitting or current-vintage promotion of source clocks.',
            'sources': [REL + 'A3_EXECUTION_BINDINGS_V1.json', REL + 'A_EXISTING_PROCEDURE_BINDINGS_V1.json'],
            'population': 'RB carry study; CountA pass_td QB typed mean. Each source report retains its own full/matched/fallback population.',
            'cutoff': 'Registered historical source cutoffs; fresh current source NOT_VERIFIED.', 'budget': budget,
            'status': 'COMPLETED', 'registration': {'record': REL + registration}, 'owner': 'Session A; existing producer/website owner retains current-source/publication authority',
            'completion_scope': 'Named finite owner-local work only; current capture, admission, full W1-8 and older-history closure remain independent and incomplete.'})
    write(R / 'EXPERIMENT_REGISTRY.json', exps)

    events = [json.loads(s) for s in (R / 'RUN_EVENTS.jsonl').read_text().splitlines() if s]
    def run(ident, experiment, status, start, finish, resources):
        row = {'run_record_id': ident + '@1', 'run_id': ident, 'run_version': 1, 'supersedes_run_record_id': None,
               'experiment_id': experiment, 'original_id': ident, 'status': status, 'origin': 'EXECUTED_HERE',
               'start': {'record': REL + start}, 'finish': {'record': REL + finish}, 'resources': resources,
               'software_checks': [REL + 'SOFTWARE_CHECKS_V1.json', REL + 'INDEPENDENT_A3_COUNT_A_REVIEW_V2.json'],
               'evidence': {'label': 'REPRODUCED_FROM_DATA', 'original_record': REL + finish}, 'publication_subject': SUBJECT}
        if row['run_record_id'] not in {x['run_record_id'] for x in events}:
            with (R / 'RUN_EVENTS.jsonl').open('a') as f:
                f.write(json.dumps(row) + '\n')
            events.append(row)
    run(RUN, EXP, 'COMPLETED', 'A3_CONDITIONAL_EXPOSURE_PROTOCOL_V1.json', 'A3_CONDITIONAL_RESULTS_V1.json',
        {'CPU_seconds': a3['CPU_seconds'], 'new_optimizer_fits': 0, 'new_historical_forecast_rows': 1672, 'new_genuine_pregame_capture': 0})
    run('r:A-POST-WAVE-COMPONENT-v1', ADMIN, 'COMPLETED', 'EXECUTION_REGISTRATION_V1.json', 'ALLOCATION_COMPONENT_RESULTS_V2.json', {'new_fits_inference': 0, 'CPU_seconds': load(P / 'ALLOCATION_COMPONENT_RESULTS_V2.json')['CPU_seconds']})
    run('r:A-COUNT-A-RESTORE-v3', ADMIN, 'COMPLETED', 'COUNT_A_RESTORE_REGISTRATION_V3.json', 'COUNT_A_RESTORE_AND_PARITY_V3.json', {'CPU_seconds': parity['CPU_seconds'], 'trusted_model_loads': 1, 'predict_calls': 2, 'retained_rows': 68, 'fresh_current_inference': 0})
    run('r:A-POST-WAVE-QUALIFICATION-v4', ADMIN, 'COMPLETED', 'FIVE_WEEK_EXTRACTION_REGISTRATION_V4.json', 'QUALIFICATION_RUNTIME_V4.json', load(P / 'QUALIFICATION_RUNTIME_V4.json'))
    run('r:A-POST-WAVE-PROPER-WEEK-IMPORT-v1', ADMIN, 'COMPLETED', 'PROPER_SCORE_WEEK_IMPORT_REGISTRATION_V1.json', 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V1.json', {'CPU_seconds': proper['CPU_seconds'], 'new_NFL_fits_forecasts_scoring': 0})
    failures = [f for f in P.glob('*FAILURE*.json')]
    for f in failures:
        run('r:A-POST-WAVE-' + f.stem, ADMIN, 'FAILED', 'EXECUTION_REGISTRATION_V1.json', f.name,
            {'resource_receipt': REL + f.name, 'unknown_cost_is_not_zero': True, 'new_NFL_fit_claim': 0})

    results = load(R / 'ALL_RESULTS.json'); newids = []
    for i, r in enumerate(a3['numerical_results']):
        if r['arm'] != 'A3_CONDITIONAL_PLAYED_EXPOSURE' or r['week'] != 'ALL':
            continue
        rid = f"v:A-POST-WAVE-A3:{r['season']}:{r['product']}:ALL"
        ss = {s: score() for s in SCORE_NAMES}
        for s in ('MAE', 'MSE', 'RMSE', 'bias'):
            ss[s] = score(r[s])
        ss['p95_AE'] = score(r['p95_absolute_error'])
        ss['strict_error_lt1'] = score(r['strict_error_lt1'] / r['scored'])
        ss['inclusive_error_le1'] = score(r['inclusive_error_le1'] / r['scored'])
        ss['exact_count_rate'] = score(r['exact_unrounded'] / r['scored']) if r['product'] == 'median' else score(None, 'Fractional means are not rounded into an exact-count recipe.')
        rec = {'result_id': rid, 'run_id': RUN, 'method_id': MID, 'output_id': r['product'],
            'comparison': {'target': 'rush_att', 'season': r['season'], 'weeks': r['actual_weeks'],
                'population_id': 'A_POSTWAVE_RB_' + str(r['expected']), 'outcome_version': 'Original bound carry scorecard current-vintage labels',
                'horizon_id': 'HISTORICAL_LEFT_LIMIT_KICKOFF_RECONSTRUCTION', 'source_policy_id': 'CURRENT_VINTAGE_SEVEN_DAY_HISTORY_RECONSTRUCTION',
                'fallback_policy_id': 'UNCHANGED_REGISTERED_EXPOSURE_STATE_FALLBACKS', 'evidence_kind': 'EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION',
                'comparison_set_id': 'A3_MATCHED_SAME_RB_ROSTER_' + str(r['season']) + '_' + ','.join(map(str, r['actual_weeks']))},
            'scores': ss, 'coverage': {'planned': r['expected'], 'scored': r['scored'], 'games': r['games'], 'weeks': len(r['actual_weeks'])},
            'evidence_label': 'NEW_EXPERIMENT', 'validity': 'VALID', 'missingness': {'unknown_outcomes': r['unknown_outcomes'], 'reason': 'Unknown participation is not a zero or DNP.'},
            'comparator': {'method': 'm:A_DYNAMIC_ROLE_CDF_V1', 'record': REL + 'A3_CONDITIONAL_RESULTS_V1.json', 'scope': 'Retained A0/A1/A2/S0/CountA on identical rows; always-side controls for actual-line comparison.'},
            'uncertainty': {'record': REL + 'A3_CONDITIONAL_RESULTS_V1.json', 'kind': 'paired game/week clustered, exposed development'},
            'adverse': ['A3 reduces signed underprediction but loses MAE to strong direct control. Actual-line law loses to A1 mean and Always-Over; Brier loses to neutral0.25. No promotion.'],
            'private_evidence': {'manifest_id': 'A-POST-WAVE-A3-V1', 'forecasts': a3['private_forecasts'], 'grades': a3['private_grades'], 'route': 'Retained owner approved authenticated private restoration; restricted fields are not public.', 'offhost_restore': 'NOT_VERIFIED'},
            'readiness': {'research': 'SCORED_HISTORICAL_RECONSTRUCTION', 'future': 'NOT_ADMITTED', 'primary_eligibility': 'Five-week floor alone does not show superiority or operational readiness.', 'live': 'NO_NEW_A_RELEASE'},
            'source_record': REL + f'A3_CONDITIONAL_RESULTS_V1.json#/numerical_results/{i}', 'publication_subject': SUBJECT}
        append_unique(results, 'result_id', rec); newids.append(rid)
    # Exact probability score is a distinct supported output, not inferred from a mean.
    rid = 'v:A-POST-WAVE-A3:2026:exact_line_probability:ALL'
    template = dict(next(r for r in results['records'] if r['result_id'] == 'v:A-POST-WAVE-A3:2026:mean:ALL'))
    ss = {s: score() for s in SCORE_NAMES}
    ss['Brier'] = score(a3['full_board_probability']['Brier']); ss['log_loss'] = score(a3['full_board_probability']['log_loss'])
    template.update(result_id=rid, output_id='exact_line_probability', scores=ss,
        coverage={'planned': 239, 'scored': 231, 'games': 81, 'weeks': 7},
        comparison={**template['comparison'], 'population_id': 'RB239_ORIGINAL_HALF_INTEGER_OFFERS', 'comparison_set_id': 'A3_RB239_ACTUAL_LINE_FULL_LAW'},
        missingness={'unknown_participation': 8, 'reason': 'Full law score includes all supported decisive events, not only high-confidence selections.'},
        source_record=REL + 'A3_CONDITIONAL_RESULTS_V1.json#/full_board_probability')
    append_unique(results, 'result_id', template); newids.append(rid)
    write(R / 'ALL_RESULTS.json', results)
    pubs = load(R / 'PUBLICATION_RECORDS.json')
    append_unique(pubs, 'publication_id', {'publication_id': 'pub:A-POST-WAVE-5W-v1', 'subjects': [SUBJECT, *newids], 'state': 'PUBLICATION_PENDING', 'commit': None, 'readback_record': None})
    write(R / 'PUBLICATION_RECORDS.json', pubs)
    software = load(R / 'SOFTWARE_TESTS.json')
    check = {'id': 'A_POSTWAVE_TYPED_MEAN_AND_FIVE_WEEK_V1', 'command': 'python -B tools/abc_a_postwave_software_checks_v1.py', 'state': 'PASS', 'record': REL + 'SOFTWARE_CHECKS_V1.json', 'kind': 'Local synthetic software checks, zero new NFL evidence or hosted CI claim.'}
    if check['id'] not in {r.get('id') for r in software['runs']}:
        software['runs'].append(check)
    write(R / 'SOFTWARE_TESTS.json', software)

    stats = []
    for part in q['parts']:
        rows = load(P / part['entry'])['records']
        pr = [r for r in proper['records'] if r['key']['target'] == part['category']]
        stats.append({'category': part['category'], 'A_qualification_views': len(rows), 'view_floor_pass': sum(r['five_week_floor'] == 'PASS' for r in rows),
                      'proper_score_views': len(pr), 'proper_score_floor_pass': sum(r['five_week_floor'] == 'PASS' for r in pr),
                      'current_season_test_weeks': [1, 2, 3, 4, 5, 6, 7], 'new_current_capture_or_release': 0,
                      'restriction': 'AnytimeTD event only, no actual offered No market' if part['category'] == 'anytime_td' else 'Exact chart numerical/law only, no same-chart offer' if part['category'] == 'chart_ppr' else 'Timing-unverified actual-line/chronological evidence; see exact product/policy/role key. Not a C admission.'})
    write(P / 'TWELVE_CATEGORY_QUALIFICATION_SUMMARY_V1.json', {'id': 'A-POSTWAVE-ALL12-STATUS-v1', 'asof_UTC': NOW, 'records': stats, 'no_inflated_counts': 'Views are not independent models or additional NFL outcomes; each exact product/policy is evaluated separately. All original historical/Week8 coverage gaps remain.', 'targets': 'Forecast-only remains separately tracked; no offered market invented.'})
    tasks = {'task_id': 'A-POST-WAVE-5W-v1', 'at_UTC': NOW, 'state': 'FINITE_WAVE_EXECUTED_PUBLICATION_PENDING',
             'next_owner_actions': {'A': 'Finish immutable publication/readback and deliver exact CountA package through own PR1; preserve W8/historical and roster/source closure queue.',
                 'registered_producer': 'Restore exact corrected CountA capsule, qualify fresh current SOURCE/features, current query, immutable persistence and registered catalog/publication route; address observed hosted guard reasons without bypass.',
                 'original_site_owner_lease178': 'Acknowledge package, independently admit eligible product, verify typed consumption/fallback/rollback; do not infer cross-category Top12 qualification or probability quality.',
                 'C': 'Read actual A export; validate/import 800 product/policy/proper-score views and new A3 loss with matching masks, record actual admission; C owns shared table.',
                 'B': 'Retains confidence-ordering/selection diagnosis and recovery ownership; no duplicate B fits.'},
             'remaining': ['2026W8 new-carry input/query qualification', 'Named historical-origin carry fits for2022-24 require existing finite preparation/retention sizing', 'Exact source/offer/period coverage closure in common championship', 'C-owned qualified receiving target-share export required only for reception extension'],
             'production': 'A remains read-only. Zero new current capture or deployment. Older independently ready releases remain with owner.'}
    with (R / 'TASK_LEDGER.jsonl').open('a') as f:
        f.write(json.dumps(tasks) + '\n')
    print(json.dumps({'new_method': MID, 'linked_cumulative_results': len(newids), 'native_all_week_results': REL + 'A3_CONDITIONAL_RESULTS_V1.json', 'all12_categories': len(stats), 'qualification_views': q['source_records'] + len(proper['records'])}))


if __name__ == '__main__':
    main()
