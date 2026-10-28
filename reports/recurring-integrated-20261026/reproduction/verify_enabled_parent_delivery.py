"""Independent joins/calculations over authenticated metadata and public outputs."""
from collections import Counter
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
import gzip
import hashlib
import json
import math
import os
import subprocess

os.umask(0o077)
B=Path('/workspace/nfl-system-audit/continuation')
D=B/'private/parent-child40729906573-actual-consumer'
M=B/'private/parent-child40729906573-control-metadata-v2'
OLD=B/'private/actual32-model-metadata-reconciliation'
def read(path): return json.loads(path.read_bytes())
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def save(name,value): (B/'evidence'/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

parent=read(B/'evidence/parent40729788942-original-result.json')
producer=read(B/'evidence/parent-child40729906573-producer-proof.json')
reader=read(B/'evidence/parent-child40729906573-reader-proof.json')
export=read(B/'evidence/parent-child40729906573-export-proof.json')['native_export']
summary=read(D/'summary.json')
overlay=read(D/'actual-accepted-overlay.json')
cards=read(D/'actual-card-source-preview.json')
browser=read(B/'evidence/parent-child40729906573-committed-preview-browser.json')
receipt_raw=(D/'public-network-4.bin').read_bytes()
receipt=json.loads(gzip.decompress(receipt_raw))
feed_raw=(D/'public-network-1.bin').read_bytes()
feed=json.loads(feed_raw)
assert hashlib.sha256(feed_raw).hexdigest()==export['feed_sha256']
assert hashlib.sha256(receipt_raw).hexdigest()==export['export_receipt_sha256']
assert receipt['root_go_sha256']==parent['root_go_sha256']=='34743ce66f1c23ac0f45c6a910af734c9084693a2f4b2e314636283e423b58bc'
assert parent['dispatches']==1 and parent['dispatch_http_status']==204 and parent['fits']==0
assert receipt['run_id']==export['run_id']=='40729906573'
assert export['source_sha']=='0409a253d6a365c31a2d421941b8ee5f40d6fd02'
assert export['state']=='PUBLIC_DERIVED_DELIVERY_COMPLETE' and export['successful_forecast']
assert summary['state']=='AUTOMATED_POLICY_ACCEPTED' and summary['elapsed_seconds']<4
assert len(summary['network_calls'])==6
assert summary['preview_source']=='e12de4763d048f6dec8e2d6cc0f89f43e18f2736'
assert len(overlay['rows'])==cards['rows']==1951
assert reader['states'][0]['state']=='PRIVATE_CAPTURE_RESTORED'
assert producer['states'][0]['fits']==export['fits']==0

choice_raw=(M/'40729906573-choice.json').read_bytes()
epoch_raw=(M/'40729906573-epoch.json').read_bytes()
original_raw=(M/'40729906573-original-catalog.json').read_bytes()
assert choice_raw==(OLD/'32-choice.json').read_bytes()
assert epoch_raw==(OLD/'32-epoch.json').read_bytes()
assert original_raw==(OLD/'32-original-catalog.json').read_bytes()
assert hashlib.sha256(choice_raw).hexdigest()==export['choice_sha256']
assert hashlib.sha256(epoch_raw).hexdigest()==export['epoch_sha256']
choice=json.loads(choice_raw)
catalog=read(M/'40729906573-artifact-catalog.json')
old_catalog=read(OLD/'32-artifact-catalog.json')
assert catalog['catalog']['categories']==old_catalog['catalog']['categories']
assert catalog['catalog']['methods']['R0']==old_catalog['catalog']['methods']['R0']
reference=read(B/'evidence/current-public-reference-fallback-reconciliation-32.json')['fixed_R0_model_version']
slots={(x['target'],x['method_id']):x['manifest_versions'] for x in catalog['slots']}
old_slots={(x['target'],x['method_id']):x['manifest_versions'] for x in old_catalog['slots']}
assert set(slots)==set(old_slots) and len(slots)==18
for key,versions in slots.items():
    assert len(versions)==len(set(versions))==2
    assert len(set(versions)&set(old_slots[key]))==1
for method,metadata in catalog['catalog']['methods'].items():
    previous=old_catalog['catalog']['methods'][method]
    assert {k:v for k,v in metadata.items() if k!='model_versions'}=={k:v for k,v in previous.items() if k!='model_versions'}

javascript_hashes=json.loads(subprocess.check_output(['node','-e',
    "const fs=require('fs'),c=require('crypto'),d=JSON.parse(fs.readFileSync(process.argv[1]));process.stdout.write(JSON.stringify(d.rows.map(r=>c.createHash('sha256').update(JSON.stringify(r)).digest('hex'))));",str(D/'actual-accepted-overlay.json')],text=True))
rows_by_hash=dict(zip(javascript_hashes,overlay['rows']));assert len(rows_by_hash)==1951
counts=Counter(r['category'] for r in overlay['rows'])
assert len(counts)==11 and 'fantasy_ppr' not in counts
selected_models={}
categories=[]
all_reference={reference,digest([['R0',reference,1.0]])}
for selection in choice['choice']['selections']:
    category=selection['decision']['category']
    members=selection['members']
    assert all(m['method_id']!='R0' for m in members)
    allowed={digest([[member['method_id'],version,member['weight']] for member,version in zip(members,versions)])
        for versions in product(*(slots[(category,m['method_id'])] for m in members))}
    all_reference.add(digest([['R0',reference,m['weight']] for m in members]))
    rows=[r for r in overlay['rows'] if r['category']==category]
    assert rows and all(r['model_version'] in allowed for r in rows)
    case=next(x for x in cards['cases'] if x['category']==category)
    assert case['value_and_label_checked'] and case['exact_public_identity_resolved']
    row=rows_by_hash[case['row_sha256']];assert row['category']==category
    selected_models[category]=sorted({r['model_version'] for r in rows})
    categories.append(dict(category=category,rows=len(rows),families=[m['method_id'] for m in members],
        weights=[m['weight'] for m in members],model_versions=selected_models[category],
        functional=case['functional'],product=case['product'],units=case['rendered_units'],
        procedure_version=case['procedure_version'],public_row_sha256=case['row_sha256'],
        card_sha256=case['card_sha256'],public_player_id=row['player_id'],public_game_id=row['game_id'],
        query_source_sha256=row['query_source_sha256'],issued_at=row['issued_at'],
        persistence_completed_at=row['persistence_completed_at'],source_cutoff_utc=row['source_cutoff_utc'],
        valid_until_utc=row['valid_until_utc'],real_game_grading='PENDING_FUTURE_GAME; controlled zero/missing/finality tests are separate',
        chosen_nonreference_components_verified=True))
assert len(categories)==11
reference_rows=sum(r['model_version'] in all_reference for r in overlay['rows'])
assert reference_rows==0
for row in overlay['rows']:
    value=row['forecast_value']
    assert isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    if row['prediction_functional']=='event_probability': assert 0<=value<=1
    if row['prediction_functional']=='expected_mean': assert value>=0
functionals=dict(Counter(c['functional'] for c in categories))
assert functionals=={'intended_median':4,'expected_mean':6,'event_probability':1}

assert browser['preview_source']==summary['preview_source']
assert browser['preview_board_sha256']==summary['actual_board_sha256']
assert [v['width'] for v in browser['viewports']]==[1280,390,320]
for v in browser['viewports']:
    assert v['identity']['overlay_rows']==1951 and v['identity']['overlay_state']=='PROVISIONAL'
    assert len(v['categories'])==12 and sum(c['selected_present'] for c in v['categories'])==11
    assert v['empty_search'] and len(v['routes'])==10 and all(x['content'] for x in v['routes'])
    assert v['refresh']['props_loaded'] and v['refresh']['hash']=='#/props'
    assert v['refresh']['document']<=v['width']
    assert not v['page_errors'] and not v['failed_requests'] and not v['failed_http']

now=datetime.now(timezone.utc).isoformat()
model_proof=dict(schema_version='automatic-child-independent-model-reconciliation-v1',observed_at_utc=now,
    run=40729906573,feed_sha256=export['feed_sha256'],public_rows=1951,
    all_rows_match_chosen_nonreference_components=True,reference_only_rows=0,
    independent_calculation='Standalone hashlib SHA256 of canonical JSON [[method_id, authenticated manifest version, frozen weight], ...]; production model/hash/catalog helpers are not called.',
    original_choice_epoch_catalog_bytes_preserved=True,fixed_R0_metadata_preserved=True,
    slots_with_preserved_original_and_new_relocated_version=18,categories=categories,
    private_forecast_or_outcome_rows_decoded=0,model_weight_decodes=0,new_NFL_fits=0,
    limitation='The authenticated catalog and native restoration bind model identity. This does not independently rerun old warm predictions or establish forecasting accuracy.')
save('parent-child40729906573-model-reconciliation.json',model_proof)
release=dict(schema_version='enabled-parent-full-delivery-verification-v1',observed_at_utc=now,
    state='PARENT_CAPTURE_RESTORE_GRADE_EXPORT_AND_PREVIEW_CONSUMER_VERIFIED',
    main='cd51ff289ace3bf14cfb820c139fd823bc330d17',producer=export['source_sha'],
    parent_run=40729788942,child_run=40729906573,parent_claim_commit=parent['claim_commit_sha'],
    root_go_sha256=parent['root_go_sha256'],jobs=export['jobs'],
    public_feed_path='state/'+export['feed_path'],feed_sha256=export['feed_sha256'],published_at=export['published_at'],
    export_receipt_sha256=export['export_receipt_sha256'],grading_checkpoint=export['grading_checkpoint'],
    reader_witness_sha256=export['reader_witness_sha256'],archive_index_sha256=export['archive_index_sha256'],
    archive_files_sha256=export['archive_files_sha256'],counts=producer['states'][0],
    public_rows=1951,public_coverage=feed.get('coverage'),
    consumer=dict(source=summary['preview_source'],policy_sha256=summary['consumer_policy_sha256'],
        elapsed_seconds=summary['elapsed_seconds'],requests=6,rows=1951,categories=dict(counts),
        chosen_nonreference_rows=1951,R0_only_rows=0,category_functionals=functionals,
        board_sha256=summary['actual_board_sha256'],installed_on_live_website=False),
    exact_source_installed_preview_browser='PASS_1280_390_320_12FILTERS_10ROUTES_REFRESH_EMPTY_NO_ERRORS_OR_OVERFLOW',
    automatic_Parent_dispatch_verified=True,actual_scheduled_trigger_after_enable_observed=False,
    website_PR9_or_PR10_merged=False,website_new_deployment_verified=False,
    new_NFL_fits=0,scientific_qualification=False,accuracy_gain_claim=False,
    original_forecasts_failures_losing_weeks_and_registrations_preserved=True,
    remaining=['Existing website owner integrates/releases ready PR9 and current PR10, then actual live selected-feed/grading verification',
        'Next configured scheduled Parent window:2026-10-29T12:36UTC; future trigger and weekly decision not yet observed',
        'Previously documented horizon/source-timing/private-accuracy/PPR/Phase2 operating limits remain'])
save('enabled-parent40729788942-full-delivery-verification.json',release)
print(json.dumps(dict(state=release['state'],public_rows=1951,categories=11,R0_only_rows=0,
    consumer_seconds=summary['elapsed_seconds'],functionals=functionals,browser='PASS',website_deployed=False)))
