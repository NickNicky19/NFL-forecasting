# Fixed 80% CQR-style interval experiment V1

Status: **CODE/DRAFT ONLY; no software checks or NFL numerical run executed.**
This is one queued bounded interval experiment. The dynamic-opportunity
comparison remains the primary work packet. The integrator owns registration,
execution, storage and the execution ledger.

## Exact experiment

Version `cdf-split-cqr-80-v1-20261024`. Use the existing permitted-source,
source-matched **base leaf CDF** saved p10/p90, source population and original
fallbacks. Do not refit, select another CDF panel, optimize a coverage level,
change points, reconstruct a new predictive law, or tune by the interval result.

One radius per target and block: 2022 calibration -> 2023 evaluation; 2023
calibration -> 2024 evaluation. Ten targets are pass_yd, pass_td, pass_cmp,
pass_att, pass_int, rush_yd, rush_att, rec, rec_yd, rush_rec_yd. Thus there are
**20 planned radii, one configuration, zero new base fits/inferences**. Exact PPR
remains label-blocked. Anytime-TD remains a probability product, without this
interval experiment. All years are exposed; none is fresh confirmation.

Calibration uses the original category's primary-role population and unchanged
`nfl_lab.cdf_evaluation._observed` supported-played flag, which includes supported
zero outcomes. The core rejects a flag inconsistent with that existing rule.
DNP, unknown participation, missing/invalid outcomes and missing intervals remain
separate exclusions. Nonprimary roles remain planned offers and receive the same
target-level radius for separately reported all-offered diagnostics; no coverage
claim for that population is asserted.
The retained source's participation coverage remains incomplete; this procedure
neither restores unknown played-zero players nor turns a statistical zero into
independent appearance evidence.

For each admitted earlier OOS player-game compute
`s=max(saved_p10-actual, actual-saved_p90)`. With alpha=.2, use exact integer
`k=ceil(4*(n+1)/5)` and the kth smallest score without interpolation. The frozen
radius is `r=max(0,s[k])`. If k>n (including n<4), retain the original interval
with `UNCALIBRATED_FALLBACK_INSUFFICIENT_N`; never use infinity or assert coverage.
The candidate is `[p10-r,p90+r]`, with the lower endpoint floored at zero for
count targets only. Signed yards keep negative endpoints. There is no endpoint
rounding, negative-radius shrinkage or empty-interval repair. Missing base
endpoints abstain, retaining that offer. Invalid present endpoints/order fail.
Original means, medians, p10/p90, fallback reasons and clocks remain unchanged.

The source-matched base learner was refit annually. This is a chronological
**CQR-style upper-order-statistic experiment over OOS outputs**, rather than the
classical exchangeable calibration sample for one fixed fitted base model.
Dependence, annual refitting, role drift and reconstructed availability prevent
an asserted finite-sample or player-specific coverage guarantee.

## Chronology and immutable phase boundaries

1. Authenticate exact owned source policy, qualification policy, CDF forecast
   and scored freezes, original query clocks, code/environment and row identity.
   Before label access verify all prerequisites and compute the storage estimate.
2. Read prediction/clock projections for all three years; preserve original
   cutoff<=kickoff reconstruction clocks. Never relabel these as pregame issuance.
3. Read only 2022 calibration outcomes/participation. Admit a calibration outcome
   only when its original outcome-availability time is **strictly earlier** than
   the earliest original 2023 query cutoff. Freeze all ten 2022 radii; issue and
   persist all original 2023 candidate offers before opening any 2023 outcome.
4. Attach original 2023 saved labels for evaluation and its later calibration
   role. Freeze ten 2023 radii using the same strict availability rule against
   the earliest 2024 query cutoff; persist all original 2024 intervals before
   opening 2024 labels.
5. Score frozen intervals once, retaining missing/fallback opportunities. No
   prospective forecasts, later results, raw source statistics or new source
   acquisition are needed. A missing prerequisite blocks the affected cell;
   all other fixed cells continue without invented data.

## Exact metadata/footer prerequisites still unmet

No private control/source body or footer was opened for this code packet.
The public source-matched code declares p10/p90 and the original comparator
registration identifies the recovery namespace; this does **not** authenticate
every saved column, clock, label or original model training boundary.

Before actual execution, bind the 30 exact saved leaf_CDF cell files for
2022/2023/2024 x ten targets through the owned scored-freeze manifest, plus the
original three query-context files and their forecast-freeze ownership.
Expected path form in the source-matched recovery namespace:
`private/scored/{year}/{target}/leaf_cdf/rows.parquet`. Resolve exact paths and
SHA256/bytes from the actual immutable manifest; do not infer existence by path.

Footer-only admission must establish unique field names and compatible types:

- Saved CDF forecast projection: original keys season/week/game_id/player_id;
  target, method, team, opponent, position, cutoff_utc, kickoff_utc, primary_role,
  fallback, p10, p90. No actual/participation in an issuance projection.
- Later saved label projection: original keys and actual, participation_state,
  outcome_state. No provider/PPR proxy or positive-only label qualification.
- Original query projection: the same keys/context plus outcome_available_utc;
  query cutoffs and kickoff must match saved CDF rows exactly, with no coercive
  identity repair. `outcome_available_utc` is not part of the declared normalized
  CDF report fields and must come from the authenticated original query chain.
- Authenticate exact training audits/model manifests proving earlier-only OOS
  base outputs; model unpickling is forbidden. A report/hash alone cannot prove
  unseen original artifacts or upstream publication times.

Rowcounts must reconcile the entire original offer inventory for each file.
All ten target files per year must match the same original ordered query keys;
duplicates/context conflicts fail. The expected historical query counts from
the existing registered source-matched study are 8686/8606/8580; actual footer
counts and provenance must be authenticated before relying on those counts.
No original full data file is copied or publicly redistributed.

## Metrics, uncertainty, retention and decisions

Primary: paired **80% interval score**, lower better:
`(upper-lower)+10*(lower-y)*I(y<lower)+10*(y-upper)*I(y>upper)`.
Report width, inclusive coverage, lower/upper misses, original fallback/missing
coverage, zeros and signed outcomes separately.
Report both primary-role and all-offered populations, each annual block, and the
pooled exposed years. Higher coverage alone is not a win; widening mechanically
raises it. MAE/RMSE point changes are not claimed because points are unchanged.
The finite packet reports the two population aggregates, each annual block and
their pooled result. Compact private subgroup tables cover player, position,
team, opponent, history state and original fallback, including planned/paired
counts and missing/unknown/DNP states. These are descriptive dependent slices,
not additional observations or independently qualified small-group gains.
Game/week paired uncertainty applies to the main population comparisons.

The interval adapter reuses existing `_observed` eligibility and unchanged
`source_matched_reporting._bootstrap`: 500 PCG64 seed1703 whole-week and game
paired sums/counts, nominal95% linear-percentile intervals, N/A below8 clusters.
Apply it to explicitly named interval-score, width and coverage deltas. No
individual-row resampling, probabilities from these intervals, universal
exchangeability guarantee or multiplicity-adjusted confirmation claim.
All20 planned cells and adverse results remain visible. No live replacement or
nominee can be earned by this exposed interval packet alone.

Actual proposed one-shot budget: 300wall/CPU seconds, 512MiB, two numerical
threads, 16MiB new private artifacts within unchanged global512MiB, zero HTTP,
model fits/inference, source acquisition, retries or scheduler changes. Reserve
40s metadata/read/retention preflight, 40s radius+prediction freeze, 40s original
label attachment, 140s metrics/uncertainty/report, 20s final persistence and20s
terminal failure reserve. All phases share the total cap.

Retain compact ordinal/lower/upper/status outputs per target-year with exact
query and original label bindings; source rows, points and outcomes are reused
by immutable references. Paired losses are reproducible views of those frozen
rows, rather than duplicate arrays. Before semantic reads, require a conservative
whole-packet estimate (including registration, radii, outputs, reports, receipts
and attempted-allocation reserves) to fit both16MiB and current global headroom.
Never delete old failed evidence or relax a quota after seeing numerical results.
The actual guarded driver, full environment/owned freeze and independent PREEXEC
remain prerequisites; this core/protocol is not an operational invocation.
