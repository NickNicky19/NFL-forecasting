# Ordered carries/receptions: exact owner integration seam

This is source-level preparation, not admission, inference, capture or deployment.
The original base-only guard remains unchanged.

## Retained procedure and artifact

The separately versioned future adapter is
`nfl_lab/category_topfive_ordered_future_v1.py`, version
`ordered-cdf-future-query-adapter-v1`, SHA-256
`c33801ffb53e30a0a8041b32c877ce04e5b3eee380000638e9cba959895f43c4`.
Its unchanged ordered-feature dependency is `nfl_lab/ordered_recent_v1.py`,
SHA-256 `d7266d47462865d832079bde1a5ff757e217c6c6297e76028398a97100ef3d0e`.

The actual retained 2026 model capsule is `FORECASTS_MODELS.zip`, 8,277,946 bytes,
SHA-256 `8cbd202d3a4f45b782187996736155db38711b9d8e041223dadaeb2b50c921c2`.
It contains:

| Target | Original member | Bytes | SHA-256 |
|---|---|---:|---|
| Receptions | `MODELS/rec_ORDERED.joblib` | 2,525,704 | `718a0cd0e4ae1e69f1b70c37c7814e9d1c7b3897c4d2bb31fad4a67aa83129aa` |
| Carries | `MODELS/rush_att_ORDERED.joblib` | 2,191,280 | `0e88d674bde0bd62187c19cb87cba3071ac608465b28cf4a52134b1cea440dc3` |

These identities come from the original retained readback receipt, not a new
model restore in this wave. The 2025 evaluation model must not replace them.
The inspected training view is 2019–2025 regular season, not 2022–2025.

## Why the current generic route rejects it

`weekly_future_inference.model_contract` correctly requires `panel == 'base'`
for the existing `leaf_cdf_base` family. Ordered models are context-panel models
with exact base-plus-four-game features. They cannot be admitted by relabeling
the family or removing this guard.

The route also affects `export_trained_artifact`, `_points`,
`FutureInferenceSession.prepare` and `predict_chunks`. Its future artifact is a
bundle with authenticated model, fixture, replay bits, environment and code pins;
the research capsule is not that bundle. Changing one family string is
insufficient.

## Minimal separately versioned owner route

1. Restore the exact capsule and members through existing private ownership,
   quota, lock and readback controls. Verify training/source/preprocessing
   identity; retain the original models without refitting.
2. Add an explicit new family such as `ordered_cdf_v1` through the normal reviewed
   entrant path. Its model-contract function calls the existing
   `validate_binding(binding, trusted_binding=...)` and checks:
   - target is `rush_att` or `rec`, support is count, panel is context;
   - `panels['context'] == base_features + ordered.columns(target)`;
   - exact artifact, procedure, source and computed feature-schema hashes;
   - trusted model restoration and original fit/training evidence.
   Every old family still dispatches to the unchanged original contract.
3. Supply a qualified base query and already admitted history projection to
   `prepare_future_queries`. Admit source availability first, then order by game
   chronology. Preserve DNP/unknown slots and actual clock uncertainty. Do not
   create live publication clocks from the historical seven-day assumption.
4. Invoke `predict_prepared_batches` and exhaust its generator. At each genuine
   law, extract the actual lower median and separately retained mean with the
   existing `full_law_functionals`. Keep complete laws and current means and
   probabilities under their own identities. New point-MAE selection is separate.
5. Use a separately versioned owned future exporter/session or reviewed extension
   that retains the original authenticated training, source, artifact, fixture,
   replay, environment, clock and complete-population requirements. Do not
   disguise the historical capsule as an already qualified future bundle.
6. Freeze candidate and actual issue/capture metadata before the registered
   deadline. After durable readback, emit the typed `stat_point_mae_v2` row and
   validate its consumer, selected-point sorting, fallback and rollback.

## Exact clock translation

The old `predict_chunks` contract uses `cutoff_utc` as an issue deadline:
`issued_at < cutoff_utc`. The new point consumer distinguishes actual information
cutoff from issue deadline:

`information_cutoff_utc <= issued_at < issue_deadline_utc < kickoff_utc`.

Do **not** copy the old deadline into the new information-cutoff field. Bind the
actual admitted source snapshot/feature-capture cutoff separately, with every
feature's maximum available clock no later than that cutoff. No invented clock
or successful page build supplies this evidence.

## Fit-clock evidence limitation

The original ordered runner stores category, panel, audit and training cutoff in
`MODEL_AUDITS.json`; inspected code does not attach `weekly_fit_receipt` with
per-fit start/completion. The generic future exporter marks a missing receipt
`LEGACY_UNAVAILABLE_NOT_OPERATIONALLY_READY`, and its operational predictor
requires actual fit clocks. Do not invent those times from run start or mtime.

Locate any original authentic fit-call receipt first. Otherwise admit a distinct
historically trained entrant only under an explicit reviewed evidence contract
that uses authenticated artifact-existence/capture bounds and verified training
and source cutoffs, stating that exact fit-call clocks are unavailable. This
does not modify the generic guard, backfill a fit receipt or satisfy an old
scientific registration. It is not a reason to refit an unchanged study merely
to manufacture historical clocks.

Current-source admission, future export/session binding, real restoration and
capture are still unexecuted. The retained owner controls these actions. The
latest backfield-information carry model remains a separate research candidate;
ordered admission does not force it to replace a stronger policy-selected method.
