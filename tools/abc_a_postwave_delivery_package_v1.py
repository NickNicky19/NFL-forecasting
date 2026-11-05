"""Prepare public-safe owner instructions and A's scoped post-wave report."""
from pathlib import Path
import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'reports/abc-championship/post-wave-5w-v1'


def main():
    def load(name): return json.loads((P / name).read_bytes())
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    def save(name, doc): (P / name).write_text(json.dumps(doc, indent=2, allow_nan=False) + '\n')
    parity = load('COUNT_A_RESTORE_AND_PARITY_V3.json')
    now = datetime.datetime.now(datetime.timezone.utc)
    package = {
        'id': 'A-COUNT-A-CORRECTED-MEAN-OWNER-PACKAGE-v1', 'prepared_UTC': now.isoformat(),
        'parent_assignment': 'POST-WAVE-5W-v1', 'owner_receipt_reconciled': 'https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/1#issuecomment-6642441018',
        'research_owner': 'Session A', 'execution_owner': 'Existing registered NFL-forecasting producer plus original-site retained owner/lease178',
        'product': 'pass_td__COUNT_A_MEAN', 'procedure_version': parity['procedure_version'], 'parent_procedure_version': parity['parent_procedure_version'],
        'model': parity['model_member'], 'capsule': parity['capsule'], 'mean_corrector': parity['mean_corrector'],
        'original_model_members': parity['members'], 'environment': parity['environment'],
        'original_feature_policy': parity['feature_policy'], 'feature_schema': parity['category'],
        'training_seasons': parity['training_seasons'], 'training_cutoff_UTC': parity['training_cutoff_utc'],
        'training_max_available_UTC': parity['training_max_available_utc'],
        'immutable_original_fit_clocks': {'reserved': parity['original_fit_reservation_UTC'], 'completed': parity['original_fit_completion_UTC']},
        'restoration': {'state': 'VERIFIED_A_OWNER_LOCAL_ONLY', 'binding_receipt': 'COUNT_A_RESTORE_AND_PARITY_V3.json',
            'native_fixture_rows': 4, 'typed_retained_rows': 64, 'fallback_rows': 16, 'finite_float_bits_and_fallbacks': 'PASS',
            'producer_offhost_restore': 'NOT_VERIFIED',
            'approved_resolution': 'Use the retained all-finalists-freeze-v1.2 extra entry target=pass_td/method=COUNT_A_MEAN, producer_selector=cells[0], complete capsule hash above. Authenticate via the existing approved private recovery/store owner. Not in the initial 18-model checkpoint catalog. No new credential or public weights route.'},
        'core': {'source': 'nfl_lab/count_a_mean_export_adapter_v1.py', 'software_version': 'A::count-a-trained-prior-mean-export-core-v1.2',
            'sha256': sha(ROOT / 'nfl_lab/count_a_mean_export_adapter_v1.py'),
            'call': 'predict_verified_mean(authenticated_model, qualified_QB_feature_frame, mean_corrector=original_correct_fallbacks, binding={model_sha256,parent_procedure_version,training_cutoff_utc})',
            'reference_restore_command': 'python -B tools/abc_a_count_a_restore_and_parity_v3.py',
            'reference_command_caveat': 'This is the bounded retained-case owner-local verification command, already completed. Do not rerun for fresh issuance or claim that it authenticates current SOURCE. Integrate the callable into the existing registered producer after source/restoration handover.',
            'no_trailing_newline_hash_encoding': 'Sorted compact UTF8 JSON for original parent/procedure digest; do not add a newline.'},
        'typed_outputs': {'expected_mean': 'Exact corrected native FORECASTS.parquet.point; never native mean (all NaN) or legacy_point (mixed).',
            'selection_point': 'Same unrounded corrected mean, explicitly mean_objective_point; may support only its independently admitted side rule.',
            'median': None, 'probability': None, 'EV': None,
            'origins': ['LEARNED_POISSON_OBJECTIVE_MEAN', 'EXISTING_TRAINED_PRIOR_MEAN', 'INCUMBENT_FALLBACK_REQUIRED'],
            'mean_product_selection': 'This candidate does not automatically replace an independently MSE-selected mean or MAE-selected median. Apply the latest category/product decision separately.'},
        'five_week_check': {'record': 'A_FIVE_WEEK_QUALIFICATION_V3__pass_td.json', 'season': 2026, 'weeks': [1,2,3,4,5,6,7],
            'numerical_projection': 'PASS_FLOOR:241 supported/718 planned; MAE0.8484231619618409; RMSE1.0493045708754531; 477unknown, not zero.',
            'actual_line_P1': 'PASS_FLOOR:142 decided, Over43-31/74, Under44-24/68, combined87-55/142;78games; source/quote timing unverified.',
            'per_category_top6_10_20': 'Separate seven-week policies, retained scores26/41,40/64,73/114; not site cross-category lists.',
            'website_cross_category_Top12': 'NOT_MET:0 scored test weeks for complete substituted site policy. Do not borrow per-category or numerical weeks.',
            'probability_and_EV': 'UNSUPPORTED; point objective alone supplies neither.',
            'scope': 'Exposed historical chronological reconstructions, not authenticated advance selections. Week floor does not establish superiority, source readiness or deployment.'},
        'source_and_clock_requirements': ['Authenticate current SOURCE.json, source-population/query-completion and feature_capture_receipt using the existing owner route and exact source/feature policy.',
            'Resolve actual current NFL week/games/cutoffs at execution; confirm every eligible QB query, including replacements and explicit unknown/abstention/fallback.',
            'Feature maximum source availability must be earlier than cutoff; cutoff must be timezone-aware and no later than kickoff, with model/prior training earlier. The arithmetic core is not an independent freshness attestation.',
            'Bind actual information cutoff separately from issue deadline. computed_at is not issued_at. Stamp true inference/issuance/persistence and expiry in the owning producer after real execution.',
            'Use a versioned permitted derived public wire and exact catalog/model/corrector/source hashes under existing publication review; no protected weights/raw feeds/private locators.',
            'Save original reference/challengers and freeze decisions/offer identity before applicable deadlines; never overwrite or backdate. Forecast-only capture remains useful if real offers fail qualification.'],
        'side_role_ranking': {'role': ['QB'], 'historical_P1': 'unrounded point>original line OVER; <line UNDER; ==line ABSTAIN; statistical threshold separate from venue settlement',
            'classic_margin': 0.15, 'classic_rank_min_line': 0.5, 'classic_gap_scale': 0.6,
            'warning': 'These classic constants do not reproduce the complete incumbent eligibility/best-per-player/cross-category Top12 rule. Keep the incumbent selection policy until its exact replacement has independent five-week and admission evidence. Do not present a mean as a probability.'},
        'fallback_and_rollback': ['Retain trained-prior mean as separately typed fallback with original reason; do not call it learned output.',
            'Unsupported/nonfinite/source-stale/expired/unadmitted rows require correctly identified incumbent fallback or unavailable status, never zero.',
            'Preserve former payload/pointer, model/source identities and issuance; verify rollback restores them without replacing earlier captures.',
            'Original-site owner verifies actual values, labels, sorts and consumer fields; probability/EV ranking remains separately admitted.'],
        'current_route_diagnosis': {'record': 'OBSERVED_OWNER_PRODUCER_STATE_V1.json',
            'lab_state_sha': '275aa84b27c4239d3b2dfea07755734d9db0ac7c',
            'week9_public_feed': 'Absent in scoped public weekly directory, which containsW07,W08,receipts. This is not a missing-model conclusion.',
            'parent_run': 41902139908, 'job': 126827092873,
            'capture_enqueue': 'SKIPPED; observed off-window, no capture started',
            'unaccepted_guards': ['QUALIFIED_HOSTED_HANDOVER_NOT_ACCEPTED','PRIVATE_DURABILITY_NOT_VERIFIED','EXACT_PUBLICATION_REVIEW_ABSENT'],
            'required_owner_action': 'Complete the existing producer handover/durable restoration/publication review with this exact procedure; qualify fresh current sources, run eligible future query and immutable capture, then expose the permitted derived feed. Do not weaken guards or create another pipeline.'},
        'completion_evidence_required': ['Producer receipt names exact procedure/model/corrector/source/feature/slot/catalog hashes and actual run IDs.',
            'Expected/attempted/learned/prior-fallback/incumbent/unavailable query counts; true issue and persistence timestamps, checksum and independent readback.',
            'Versioned published payload and owner consumer acknowledgement, category values/labels/sorts, fallback/expiry/rollback evidence.',
            'Explicit product-specific five-week admission; do not claim new selector or probability qualification.'],
        'states': {'prepared': True, 'A_restored_parity': True, 'public_package_delivered': 'PENDING_PUBLICATION_READBACK',
            'producer_receipt_acknowledged': False, 'fresh_current_query': False, 'new_forecast_captured': False,
            'payload_published': False, 'website_consumed': False},
        'next_action': 'Registered producer receives immutable package and returns a fresh current-source/capture receipt or the exact unmet handover member. Original-site owner separately admits/consumes eligible typed product. No new general permission requested.'}
    save('COUNT_A_OWNER_EXECUTION_PACKAGE_V1.json', package)
    save('PRIVATE_EVIDENCE_MANIFEST_V1.json', {'id': 'A-POSTWAVE-PRIVATE-EVIDENCE-v1', 'route': 'Existing owner-approved protected matched12 store and recovery route; no new shared archive',
        'component': load('ALLOCATION_COMPONENT_RESULTS_V2.json')['private_evidence'],
        'A3_forecasts': load('A3_CONDITIONAL_RESULTS_V1.json')['private_forecasts'], 'A3_grades': load('A3_CONDITIONAL_RESULTS_V1.json')['private_grades'],
        'Count_A_parity': parity['private_evidence'], 'readback': 'PASS_A_OWNER_LOCAL; OFFHOST_NOT_VERIFIED',
        'restrictions': 'No restricted player rows, raw feeds, model weights, secrets or private storage locators in public package.'})
    stats = load('TWELVE_CATEGORY_QUALIFICATION_SUMMARY_V1.json')['records']
    table = '\n'.join('| '+r['category']+' | '+str(r['view_floor_pass'])+'/'+str(r['A_qualification_views'])+' | '+str(r['proper_score_floor_pass'])+'/'+str(r['proper_score_views'])+' | '+r['restriction']+' |' for r in stats)
    report = f'''# Session A — post-wave diagnosis, five-week qualification and delivery

Revision **POST-WAVE-5W-v1**, parent **ABC-PREDICTIVE-IMPROVEMENT-01**. Recorded {now.astimezone(ZoneInfo('America/Chicago')).isoformat()} America/Chicago; {now.isoformat()} UTC. C remains canonical evaluator/table owner. A remains original-site read-only.

## Executed result and decision

The common-case audit closed the accounting question. The single justified A3 mechanism completed **1,672 new historical forecasts, zero optimizer fits**. It improved the losing A2 law but did **not** beat the strong A1 mean or Always-Over. No model was promoted. The original full335 board A0-mean/A1-law tie **174/327** remains separate from the RB239 panel below.

Requested selection period:2026W1–8; **actually scored:W1–7**,239 eligible RB player-games,231 decided,8 participation-unknown,81 games. Actual-line timing unverified; reconstructed rules, not original website recommendations. Each procedure's own sides:

| Procedure / rule | Over W–L/N/% | Under W–L/N/% | Combined W–L/N/% | Coverage / control |
|---|---|---|---|---|
| A3 mean P1 |48–44/92/52.17%|65–74/139/46.76%|113–118/231/48.92%|239/239attempted;A1mean118/231|
| A3 median or same-law P2 |45–40/85/52.94%|69–77/146/47.26%|114–117/231/49.35%|239/239attempted;A2law105/231;AlwaysOver122/231|
| A3 P2 confidence≥0.55 |36–36/72/50.00%|63–72/135/46.67%|99–108/207/47.83%|215selected/239;24abstain;8unknown|

A3-law versus A2-law:+9wins, **+3.90percentage points**, paired game95%interval−3.81to+10.97points. Against Always-Over:−8wins, **−3.46points**, interval−10.86to+4.33points. These exposed comparisons have81game/7weekclusters and multiplicity limitations. No useful90% selective result is established. [All weekly, numerical, paired, probability and Top6/10/20 results](A3_CONDITIONAL_RESULTS_V1.json); TopK remains timing-unverified exploratory, not executable original lists.

Full-board A3 Brier **0.298964**, log loss **0.854018**, both on231 supported decisive half-integer events. Neutral Brier0.25 is better. This binary score must not be mixed with the older law archive's half-three-outcome Brier. Numerical medianMAE:2026W1–7 **3.742321**, compared with unchanged A1 **3.580205** and A0 **3.627986** on586 matching outcomes. 2025W5–8 A3 medianMAE **3.288288**,333/428supported; no claim this is the full2025season. New forecast support, missingness, bias and tails remain in the source report.

## Verified accounting versus hypothesis

On common2026W1–6 cases:513 supported player-games,186team-games/93games. Team-volume bias **+0.724549** carries; contribution to player bias **+0.136111**. Allocation contribution **−3.184813**, net **−3.048702**. 73W7player outcomes lack the compatible all-position team-total source; they remain in the separate numerical evaluation.

Full allocation+other mass is conserved to1.07e−14; zero label conflicts. Share normalization and forecast mass assigned to unresolved roster members explain the accounting pattern, **not a demonstrated injury/DNP causal mechanism**. Postgame substitutions are diagnosis only. [Corrected report V2](ALLOCATION_COMPONENT_RESULTS_V2.json) preserves V1 and discloses its W1–7-versus-commonW1–6 reporting correction.

A3 is a conditional-on-appearance individual marginal using the same raw forward-state share/variance and predicted team exposure, **not a coherent joint finite-team allocation or unconditional participation model**. Exact NB/Beta-binomial summation; no MonteCarlo, offset, new injury rule or future smoothing. Recipe frozen after2025W1–4 diagnosis; later periods were already exposed. [Protocol](A3_CONDITIONAL_EXPOSURE_PROTOCOL_V1.json) · [source bindings](A3_EXECUTION_BINDINGS_V1.json).

## Five-week contribution for C — all twelve categories

[Main qualification index](A_FIVE_WEEK_QUALIFICATION_V3.json) contains731 existing/new product-policy views; [proper-score supplement](A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V2.json) adds69 retained law/probability views. **800views, not800methods or new NFL experiments.** Exact procedure/output/role/policy keys, season/week pairs, counts, source hashes and empty weeks are retained. Probability weekly counts are explicit positive-scored lower bounds where the original archive lacks proper-score weekly partitions.

| Category | Numeric/event/selection view floor pass / examined | Proper-score view floor pass / examined | Limits |
|---|---:|---:|---|
{table}

785/800 views meet the week floor;10 four-week historical views are below the floor, and five nonexistent CountA median/law views are unsupported/N/A. Apply the appended A_FIVE_WEEK_QUALIFICATION_AMENDMENT_V4.json with the base index. This contribution does not import inaccessible B/C rows, qualify source clocks, establish superiority or confer production admission. The C-owned shared table and full2026W1–8/historical championship remain incomplete. Targets stay forecast-only; no targets market invented.

## Count A — executable owner package, not a live release

**pass_td__COUNT_A_MEAN**, exact procedure `{parity['procedure_version']}`. Authenticated complete399,037-byte capsule and298,952-byte model; one trusted load,4nativefixtures plus64retained typed cases,16fallbacks, finite-bit/fallback parityPASS. The corrected value is native`point`; native`mean` is allNaN and`legacy_point` is mixed. [Exact restoration receipt](COUNT_A_RESTORE_AND_PARITY_V3.json).

Seven distinct2026W1–7 scored weeks meet the floor for this exact numerical mean and retained P1 actual-line rule:Over43–31/74,Under44–24/68,combined87–55/142=61.27%,78games. Numerical241/718supported,MAE0.848423,RMSE1.049305;477unknown,notzero. These are separate populations. No law/probability/EV is invented. Per-category Top6/10/20 history does **not** qualify the original site's cross-category Top12 replacement (0testedweeks for that changed complete policy).

[**Owner execution package**](COUNT_A_OWNER_EXECUTION_PACKAGE_V1.json) binds the complete artifact, original mean-corrector, environment, typed corev1.2, source/clock requirements, fallback/rollback, side/ranking limits and required receipts. Historical exact restoration does not reset test weeks. The new missing-kickoff guard changes invalid-input rejection only; valid retained means are unchanged.

The approved lab-state route at275aa84 containsW07,W08,receipts;W09publicfeed is absent. **The model is present in the separate authenticated archive**, so a404was not a missing-model proof. Latest observed parent41902139908/job126827092873 was off-window, capture enqueueSKIPPED,0capture:hosted handover not accepted, private durability not verified, exact publication review absent. A no-op patch alone would not capture anything. [Observed owner/producer state](OBSERVED_OWNER_PRODUCER_STATE_V1.json).

The responsible existing producer must authenticate fresh SOURCE/population/query completion/feature receipt, perform current query, bind catalog/publication review, persist with true issue/source/persistence clocks, then return the derived feed. Original-site owner must acknowledge/admit eligible products and verify actual values/labels/sorts/fallback/rollback. A's local fixture replay is not fresh current inference, off-host restoration or consumer receipt.

## Current operation and next actions

No new genuinely pregame A packet or original-site release occurred. Production main readback remainsaf8bc14; owner reports classic baseline`sleeper-matchup-classic-fg-identity-v1`, ranking`selected-projection-gap-classic-v1`,selected overlayDISABLED_USE_R0,0selected/MAErows. Owner's baseline producer41912247259 and Pages7557787017 are not CountA issuance. Prior immutable forecasts remain intact. No new browser-consumption claim by A.

Next nominal owner schedule:November5,08:06CST/14:06UTC, **configured, not observed execution**. Actual games and cutoffs must be refreshed by the retained producer. Source cutoff is distinct from issue deadline; no backdating or original-assignment replacement.

Next A work remainsW8source/query qualification and historical-origin coverage under finite registrations; reception extension awaits C's qualified target-share component without duplicating it. B owns confidence-ordering/selection; C owns intake/shared table. Independently ready older releases are not delayed by A3,90%aspiration or missing older years.

## Verification, failures and reproducibility

[Independent cached-row/probability checks](INDEPENDENT_A3_COUNT_A_REVIEW_V2.json):1,672forecast/source checks,146numeric summaries,956policy rows,32side summaries; independent quadrature of one winner/loser agrees within5.88e−13. [Synthetic software checks](SOFTWARE_CHECKS_V1.json):16groups,zeroNFLobservations. Neither is a new NFL backtest or hostedCIpass.

Failed source/encoding/schema/import/metadata attempts remain alongside their terminal receipts and spent allocations. The4MiB metadata guard was preserved; unpublished duplicate guidance was moved to the existing separately countedSCOPE entry, leaving the old9bytes headroom unchanged. No unique evidence was deleted. Category gzip partitions bind original JSON bytes/hashes under existing2MiBcompressed/4MiBexpanded per-member checks. [Storage failure/remedy](STORAGE_SCOPE_FAILURE_AND_REPAIR_V1.json).

[Private safe manifest](PRIVATE_EVIDENCE_MANIFEST_V1.json) names owner-local readback and off-host limits; no protected rows/weights/private locators are published. Reproduce only under the same approved source/store contracts. Model source and clocks are not fabricated. Publication, delivery, acknowledgement, admission, capture and served verification remain separate recorded states.
'''
    (P / 'README.md').write_text(report)
    # Add a single obvious entry to the established indexes, preserving history.
    for p, title in [(ROOT / 'reports/abc-championship/README.md', 'Post-wave diagnosis, five-week floor and Count A delivery'),
                     (ROOT / 'reports/opportunity-four/README.md', 'Post-wave diagnosis and product-specific five-week evidence')]:
        link = ('post-wave-5w-v1/README.md' if 'abc-championship' in str(p) else '../abc-championship/post-wave-5w-v1/README.md')
        text = p.read_text()
        if link not in text:
            p.write_text(text + '\n## ' + title + '\n\n[Executed Session A checkpoint and owner package](' + link + '). Earlier elapsed capture windows above are retained historical reports; use this checkpoint for current state.\n')
    print(json.dumps({'owner_package': package['id'], 'state': 'PREPARED_NOT_DELIVERED_OR_CONSUMED', 'report_bytes': len(report.encode())}))


if __name__ == '__main__':
    main()
