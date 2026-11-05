"""Import retained proper-score week support; no new scoring or model use."""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.dont_write_bytecode = True
OUT = ROOT / 'reports/abc-championship/post-wave-5w-v1'


def main():
    start = time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    resource.setrlimit(resource.RLIMIT_AS, (1610612736,) * 2)
    signal.alarm(90)
    from nfl_lab.product_test_week_floor_v1 import evaluate
    from nfl_lab.opportunity_registry_storage_v1 import pack_bytes, read_document
    from tools.category_topfive_matched12_storage_v1 import open_store, GO
    store, _ = open_store(ROOT, allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26', root_go=GO, readonly=True)
    path = store.forward_root / 'research/matched12-law-all-finalists-v1-1-20261031/AGGREGATES.json.gz'
    digest = 'e7438e27d078daa8aceda5528a1f74cde59cf5db00cb81160ea735e05350c715'
    store.validate_reference(path, digest)
    law = json.loads(gzip.decompress(path.read_bytes()))
    bindings = json.loads((OUT / 'A_EXISTING_PROCEDURE_BINDINGS_V1.json').read_bytes())['bindings']
    lookup = {(b['source_key'][1], b['source_key'][2]): b for b in bindings if b['source_key'][0] == 'catalog'}
    records = []
    for kind in ('distribution_scores', 'probability_scores'):
        for row in law[kind]:
            target, method = row['target'], row['method']
            if (target, method) not in lookup:
                raise ValueError('missing exact procedure binding')
            arm = row.get('arm', 'SAVED_FULL_LAW')
            key = {'procedure_version': lookup[target, method]['procedure_version'] + ';' + law['version'] + ';' + arm,
                   'target': target, 'output': arm,
                   'role_scope': row.get('primary_roles', {}).get('role_scope', 'Original bound law score population; see retained native aggregate'),
                   'selection_policy': 'PROPER_DISTRIBUTION_SCORE' if kind == 'distribution_scores' else 'PROPER_EXACT_LINE_PROBABILITY_SCORE',
                   'history_rule': 'Original exact annual-origin model/source contract; no new fit, repair or updated source vintage.'}
            metrics = row['primary_roles'] if kind == 'distribution_scores' else row['metrics']
            if kind == 'distribution_scores':
                weeks = row['weekly']
                proof = 'Exact retained weekly proper-distribution scored counts.'
                wk = [{'season': 2026, 'week': int(w['week']), 'scored_eligible_cases': int(w['metrics']['scored']),
                       'completed_outcomes': int(w['metrics']['scored']) > 0, 'key': key} for w in weeks]
            else:
                same = [r for r in law['selection_policies'] if r['target'] == target and r['method'] == method and r['arm'] == arm and r['policy'] == 'FULL_BOARD']
                if len(same) != 1:
                    # Missing weekly provenance is explicit, never guessed from the requested period.
                    wk = []
                    proof = 'Weekly probability partitions absent and no exact matching full-board policy located.'
                else:
                    wk = []
                    for w in same[0]['weekly']:
                        m = w['metrics']; n = int(m['over']['decided'] + m['under']['decided'])
                        wk.append({'season': 2026, 'week': int(w['week']), 'scored_eligible_cases': n, 'completed_outcomes': n > 0, 'key': key})
                    proof = 'Positive decided valid-law cases under identical arm FULL_BOARD prove a lower bound on scored probability weeks. Tied valid laws may add cases; a sub-five lower bound is NOT_ESTABLISHED, not proof of zero law support.'
            result = evaluate(key, wk)
            if kind == 'probability_scores' and result['five_week_floor'] != 'PASS':
                result['five_week_floor'] = 'NOT_ESTABLISHED'
            records.append({**result, 'method_alias': method, 'kind': kind, 'retained_metrics': metrics,
                            'weekly_score_support': [{k: v for k, v in w.items() if k != 'key'} for w in wk],
                            'proof': proof, 'evidence_tier': 'EXPOSED_CHRONOLOGICAL_RECONSTRUCTION; actual-line clocks unverified',
                            'probability_score_contract': 'HALF_THREE_OUTCOME_BRIER; not interchangeable with a binary Brier or neutral 0.25 scale',
                            'source_aggregate_sha256': digest, 'operational_export': 'Not inferred from historical scores or five-week floor.'})
    payload = {'id': 'A-PROPER-SCORE-FIVE-WEEK-SUPPLEMENT-v1', 'coordinator': 'C; A contribution only',
               'asof_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'records': records,
               'new_fits_forecasts_scores_NFL_weeks': 0, 'CPU_seconds': time.process_time() - start}
    file = OUT / 'A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V1.json'
    pack_bytes(file, (json.dumps(payload, indent=2, allow_nan=False) + '\n').encode())
    if read_document(file) != payload:
        raise ValueError('supplement readback differs')
    print(json.dumps({'records': len(records), 'floor_pass': sum(r['five_week_floor'] == 'PASS' for r in records),
                      'CPU_seconds': time.process_time() - start}))


if __name__ == '__main__':
    main()
