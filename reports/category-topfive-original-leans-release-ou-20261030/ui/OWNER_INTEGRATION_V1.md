# Additive original recorded lean reporting module

This is a prepared integration package, **not a website mutation, capture or deployment**. The retained production owner performs reviewed website changes and live readback. The research-generated data must retain original recommendations and grading provenance; this renderer creates no sides or results.

## Files and data contract

- Copy `tools/category_topfive_original_side_report_v1.js` to website `output/original-side-record.js` through its existing build/export workflow. Its public API is `NflOriginalSideRecord.mount(element, report)`.
- Export the approved root aggregate as `output/data/original_recorded_leans_report.json`, version `original-recorded-leans-report-v1`. It must contain independently separated `cumulative`, `weekly` and `by_version` tables. No private row-level sources belong in this aggregate.
- Every row retains category, cohort, season/week, model/policy, provenance/evidence tier, coverage and separate Over/Under status counts. An unavailable hit rate is null. The renderer rejects a rate inconsistent with hits / (hits + misses).
- `ALL_RECORDED_LEANS` and `ORIGINAL_TOP_PICKS` are distinct populations. No current engine identity can supply missing historical attribution. Keep original reference-model fields where present, including sparse per-pick fields.

## Minimal owner patch

Reconcile these insertions against current reviewed Main; the dated source inspected here is not proof that those line numbers remain current.

1. In `output/index.html`, load the new module before `app.js`, alongside `reliability-ui.js`. Use a versioned asset name/query according to existing cache policy.

```html
<script src="original-side-record.js?v=original-side-record-renderer-v1"></script>
```

2. Beside the existing `S.track` data load, read the new reviewed aggregate. Failure must leave the existing record page working and must not substitute reconstructed research results.

```js
try {
  S.originalSideRecord = await getJSON(`data/original_recorded_leans_report.json?t=${Date.now()}`);
  globalThis.NflOriginalSideRecord?.validate(S.originalSideRecord);
} catch {
  S.originalSideRecord = null;
}
```

3. Retain the original Track Record content and append a dedicated container when rendering that page. After assigning the page HTML, mount the module. Keep its returned disposer and call it before the next page render if the same element is reused.

```js
const historyHost = document.createElement("div");
historyHost.id = "original-recorded-side-history";
document.querySelector("#main").append(historyHost);
if (S.originalSideRecord && globalThis.NflOriginalSideRecord) {
  try {
    S.originalSideRecordDispose = NflOriginalSideRecord.mount(historyHost, S.originalSideRecord);
  } catch {
    historyHost.textContent = "Original category-by-side history is unavailable: its reporting contract did not validate.";
  }
} else {
  historyHost.textContent = "Original category-by-side history has not been published. Existing recorded results remain below their original labels.";
}
```

The existing `renderRecord()` currently returns early if legacy `S.track` is absent in the inspected source. Mount this new section on **both** paths so the new report does not depend on a legacy record being available.

4. Replace historical headings whose R0/classic identity is chosen from **current** `S.data.execution_model`. For old rows lacking authenticated per-record identity, use a neutral heading such as `Earlier recorded forecasts — provenance shown per record`. Preserve the original aggregate and original issued reports. Never relabel the entire inherited history R0, current-baseline or selected-research from the currently deployed engine.

5. Keep the current projection-gap controls labeled as projection-gap. This package adds no probability or EV ranking. Unsupported probabilities/prices remain missing; the historical rate is never copied into a player confidence field. Probability/EV activation requires a distinct reviewed selection-policy release.

## Required owner verification

- Run normal current source/schema/UI checks and the separately recorded fictional module fixtures.
- Compare the published aggregate hash with the served response and verify the module asset's exact bytes.
- In an actual browser, check category, cohort, side, model and weekly/cumulative filters; visible sample counts, partial weeks and unresolved states; unknown historical attribution; and no per-player probability inferred from the table.
- Confirm the legacy record page and ranking controls still work when the new report is absent, malformed or rolled back. Rollback removes only the additive report/module integration, never the historical archives or original recommendation receipts.
- Return actual source/build/deployment IDs and live DOM/value readback. A prepared module or fictional checks are not live verification.

## Evidence boundaries

The existing `reports/opportunity-four/over-under/OVER_UNDER_RESULTS.json` is timing-unverified reconstructed research, not the original website record. Its actual bookmaker settlements remain unresolved and it cannot be substituted for this original-side history.

The original selected-ranking companion supplies original selected sides, lines, model/product and policy receipt chains. Ordinary archived leans must use saved `prop.lean`, not recomputation from today's forecast. Dated archives may lack provenance or original per-row clocks. Preserve those gaps. A later archive save clock is not automatically original issuance.
