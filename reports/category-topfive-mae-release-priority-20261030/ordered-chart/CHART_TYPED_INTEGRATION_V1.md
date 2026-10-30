# Chart-PPR typed point adapter: implementation and remaining admission

The new source is `nfl_lab/category_topfive_chart_mae_future_v1.py`, version
`nick-chart-ppr-mae-future-adapter-v1`. It preserves the original chart predictor,
historical replay API, exact model and scoring formula.

## Two stages

1. `predict_chart_candidates(model, queries, *, binding, trusted_binding,
   trusted_model_sha256)` observes each **original** law returned during one
   unchanged `chart.predict_reviewed` traversal. It calls
   `full_law_functionals(law, target='nick-chart-ppr-v1')` on the genuine integer
   law, proves `F(m-1)<0.5<=F(m)`, then retains median and mean divided by 50.
   It does not construct a distribution from p10/p90 or scalar forecasts and
   does not invoke a second forest traversal. Output candidates have no claim of
   issuance or persistence.
2. `captured_chart_point(candidate, *, trusted_binding, capture_receipt,
   trusted_capture_receipt)` requires the independently trusted original capture
   record to match the candidate digest, full identity, target, source/model/
   procedure, cutoff and kickoff. Only then does the existing `consumer_view`
   validate clocks and format the selected median, separate expected mean and
   truthful fallback identity. The expected receipt must come from the existing
   private restoration route, not a request's self-asserted hash.

The model must first be restored and loaded through the existing reviewed loader
using its independently approved digest. The wrapper's model-shape checks do
not replace this requirement. Source-policy hashes authenticate named contracts,
not historical publication truth or current freshness.

The caller supplies a current admitted binding containing adapter/target, model,
procedure, source-policy and feature-schema hashes, plus the truthful source-
availability policy. `feature_schema_sha256()` binds the exact 32 features,
identity/clocks, five roles and scale 50. Historical source-policy binding is not
silently reused as current admission.

## What actually ran

Twelve new fictional cases passed once under a separately recorded allowance:
**1.524466 CPU seconds, 1.548539 wall seconds, 164,061,184 bytes peak RSS**.
No NFL sources, NFL model deserialization, fits, forecast capture, HTTP or CAS
writes occurred. The fixture uses synthetic 2099 identities, an unfitted model-
shaped shell and the real `MixtureBatch` distribution implementation. It verifies
actual brackets, signed scale, distinct preserved mean, one traversal, wrong
model/source, equal/future clocks, true prior fallback, frozen-byte tampering,
capture identity, late issuance, missing capture proof and old-PPR rejection.

The original 128 MiB proposal was never executed; a 320 MiB continuation was
authorized before testing because unchanged chart imports load SciPy/sklearn.
The actual result is software evidence, not a new NFL accuracy comparison.

## Existing trusted model and completed work

The retained chart model digest is
`dee275647336f34b0a96fdfad0b7b349c8c1df9e83fd4ce8fa53608ff621e877`.
Its original model/forecast capsule is 698,121 bytes, digest
`063ba204d555313c59c1aae18717fc6642791371da28e7455dc79234ac385925`.
The capsule's `fitted_model_pickle_base64` is private; do not publish it.
The owner authenticates the capsule and decoded model bytes before loading.

The earlier technical adapter replay already reproduced all 2,117 original
queries' mean/median/p10/p90 and fallbacks exactly. The new fictional cases do
not rerun that comparison. The historical same-chart CDF median MAE was
4.679406 on 1,954 supported outcomes; that is exposed development evidence,
not a live website-relative gain or new score from this wave.

## Remaining owner gates

- Admit an actual future identity, roster and qualified source/feature snapshot.
  Keep unknown clocks and prior-only fallback explicit. Conditional-on-played
  forecasts do not imply a learned DNP probability.
- Restore the approved model and binding in the retained producer; verify real
  current-query inference, replay, complete population, bounded resources and
  fresh-process persistence/restoration.
- Freeze the exact chart candidates and issue/capture receipts before the
  actual horizon; use the finalizer only after readback.
- Register the chart scoring target and typed consumer. Keep old-site PPR
  fallback visibly identified as a different contract; never relabel it or fill
  missing chart primitives with zero. Preserve rollback and original history.
- Verify actual published values, chart label, sorting and fallback on the live
  consumer. The source helper and passing fixtures are not admission/deployment.

The direct chart model does not need future target-game rare-event outcomes
before initial issuance. Remaining historical participation/rare-event label
qualification and later grading must continue under their own dependencies;
do not create a new blanket label-completion or eight-week delay for otherwise
valid future direct-model inference.
