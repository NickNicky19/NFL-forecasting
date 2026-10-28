"""Join existing genuine-run, anonymous-consumer and browser proofs; no model fit."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import subprocess

os.umask(0o077)
BASE = Path('/workspace/nfl-system-audit/continuation')
E = BASE/'evidence'
P = BASE/'private/consumer32-actual-fresh-board'

def read(path):
    return json.loads(path.read_bytes())

def save(name, value):
    (E/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

export = read(E/'continuation32-export-proof.json')
native = export['native_export']
consumer = read(P/'summary.json')
overlay = read(P/'actual-accepted-overlay.json')
cards = read(P/'actual-card-source-preview.json')
models = read(E/'current-public-reference-fallback-reconciliation-32.json')
browser = read(E/'consumer32-committed-fresh-preview-browser.json')
head = 'e12de4763d048f6dec8e2d6cc0f89f43e18f2736'
assert native['state'] == 'PUBLIC_DERIVED_DELIVERY_COMPLETE'
assert native['source_sha'] == '0409a253d6a365c31a2d421941b8ee5f40d6fd02'
assert native['fits'] == 0 and native['successful_forecast']
assert consumer['state'] == 'AUTOMATED_POLICY_ACCEPTED'
assert 0 < consumer['elapsed_seconds'] < 4
assert len(overlay['rows']) == cards['rows'] == models['public_rows'] == 1960
assert models['all_rows_match_all_chosen_nonreference_component_versions']
assert models['actual_public_rows_using_only_fixed_R0'] == 0
assert browser['preview_source'] == head and browser['expected_preview_rows'] == 1960
assert browser['preview_board_sha256'] == consumer['actual_board_sha256']
for viewport in browser['viewports']:
    assert viewport['identity']['overlay_rows'] == 1960
    assert viewport['identity']['overlay_state'] == 'PROVISIONAL'
    assert not viewport['page_errors'] and not viewport['failed_requests'] and not viewport['failed_http']
network = consumer['network_calls']
assert len(network) == 6
assert network[1]['sha256'] == native['feed_sha256'] == models['feed_sha256']
assert hashlib.sha256((P/'public-network-1.bin').read_bytes()).hexdigest() == native['feed_sha256']
assert hashlib.sha256((P/'public-network-4.bin').read_bytes()).hexdigest() == native['export_receipt_sha256']
count_categories = {'pass_att', 'pass_cmp', 'pass_int', 'pass_td', 'rush_att', 'rec'}
for row in overlay['rows']:
    value = row['forecast_value']
    assert isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if row['category'] in count_categories:
        assert value >= 0 and row['prediction_functional'] == 'expected_mean'
    if row['category'] == 'anytime_td':
        assert 0 <= value <= 1 and row['prediction_functional'] == 'event_probability'

categories = []
# The browser receipt hashes JSON.stringify bytes. Preserve JavaScript number
# serialization (for example 1 versus Python's 1.0) when joining those hashes.
javascript_row_hashes = json.loads(subprocess.check_output(['node', '-e',
    "const fs=require('fs'),c=require('crypto');const d=JSON.parse(fs.readFileSync(process.argv[1]));"
    "process.stdout.write(JSON.stringify(d.rows.map(r=>c.createHash('sha256').update(JSON.stringify(r)).digest('hex'))));",
    str(P/'actual-accepted-overlay.json')], text=True))
assert len(javascript_row_hashes) == len(overlay['rows'])
rows_by_hash = dict(zip(javascript_row_hashes, overlay['rows']))
assert len(rows_by_hash) == len(overlay['rows'])
for case in cards['cases']:
    category = case['category']
    rows = [r for r in overlay['rows'] if r['category'] == category]
    model = next(m for m in models['categories'] if m['category'] == category)
    assert len(rows) == model['rows']
    row = rows_by_hash[case['row_sha256']]
    assert row['category'] == category and row in rows
    assert case['value_and_label_checked'] and case['exact_public_identity_resolved']
    categories.append(dict(category=category, rows=len(rows), chosen_families=model['selected_families'],
        weights=model['weights'], method_id=case['method_id'], model_version=case['model_version'],
        procedure_version=case['procedure_version'], product=case['product'],
        prediction_functional=case['functional'], units=case['rendered_units'],
        public_player_id=row['player_id'], public_game_id=row['game_id'],
        public_row_sha256=case['row_sha256'], rendered_card_sha256=case['card_sha256'],
        issued_at=row['issued_at'], persistence_completed_at=row['persistence_completed_at'],
        source_cutoff_utc=row['source_cutoff_utc'], valid_until_utc=row['valid_until_utc'],
        query_source_sha256=row['query_source_sha256'],
        selected_components_and_display_checked=True,
        real_game_grading='PENDING_FUTURE_GAME; controlled identity/finality/zero/missing tests are separate'))
assert len(categories) == 11
trace = dict(schema_version='actual-current-feed-category-trace-v2',
    observed_at_utc=datetime.now(timezone.utc).isoformat(),
    state='ACTUAL_SOURCE_PREVIEW_CONSUMER_ACCEPTED_NOT_DEPLOYED',
    run=int(native['run_id']), source=native['source_sha'], consumer_head=head,
    feed_sha256=native['feed_sha256'], selected_rows=1960,
    elapsed_seconds=consumer['elapsed_seconds'], network_calls=6,
    board_sha256=consumer['actual_board_sha256'], categories=categories,
    unsupported_exact_research_PPR='No selected research product; declared website reference boundary remains',
    fixed_R0_only_accepted_rows=0, public_only=True, deployed=False,
    functional_categories=dict(Counter(c['prediction_functional'] for c in categories)),
    limitation='Point and probability contracts are checked; these rows do not establish a full predictive distribution, historical accuracy or future outcome grading.')
save('current-category-feed-traces-32.json', trace)
release = dict(schema_version='current32-release-readiness-v1',
    observed_at_utc=trace['observed_at_utc'], state='PARTIAL_PRODUCER_VERIFIED_WEBSITE_READY_NOT_DEPLOYED',
    main='cd51ff289ace3bf14cfb820c139fd823bc330d17', producer=native['source_sha'],
    main_CI=40640349535, producer_CI=40642527286,
    producer_complete_nodes=2503, producer_passed=2502, producer_existing_optional_skip=1,
    native_registration31=40644020277,
    native_registry_commit='4f2cafd906b2d83dd045f48fae61dff5e08d4453',
    capture32=dict(run=int(native['run_id']), jobs=native['jobs'], state=native['state'],
        feed_path='state/'+native['feed_path'], feed_sha256=native['feed_sha256'],
        published_at=native['published_at'], private_candidates=11466,
        private_selected=2956, public_selected=1960, model_pairs=18,
        archive_index_sha256=native['archive_index_sha256'],
        archive_files_sha256=native['archive_files_sha256'],
        reader_witness_sha256=native['reader_witness_sha256'],
        grading_checkpoint=native['grading_checkpoint']),
    consumer=dict(head=head, CI=40648049705, ready=True, stacked_on_PR9=True,
        policy_sha256=consumer['consumer_policy_sha256'], rows=1960,
        elapsed_seconds=consumer['elapsed_seconds'], requests=6,
        chosen_nonreference_identity_check='ALL_1960_PASS',
        exact_committed_source_install_and_browser_preview='PASS',
        viewports=[v['width'] for v in browser['viewports']], deployed=False),
    remaining=['Existing website writer integration, deployment and actual live-selected verification',
        'Parent activation access (403), actual daily route and subsequent recurring execution',
        'Separate Phase2 operating qualification and its remaining deployment race acceptance'],
    original_forecasts_failures_and_losing_weeks_preserved=True,
    new_NFL_fits=0, scientific_qualification=False, accuracy_gain_claim=False)
save('current32-release-readiness.json', release)
print(json.dumps(dict(state=release['state'], rows=1960, categories=11,
    functionals=trace['functional_categories'], real_run=int(native['run_id']), consumer_head=head)))
