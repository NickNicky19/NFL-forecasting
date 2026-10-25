# Fixed anytime-TD calibration — October 25, 2026

**Completed and independently accepted: 16 calibrator fits, zero base-model
fits. Every one of the eight fixed base/method combinations worsens pooled
Brier versus both unchanged bases.** No calibration lead or policy selection
follows.

[Accepted aggregate results](PUBLIC_RESULTS.json) ·
[Independent acceptance summary](INDEPENDENT_ACCEPTANCE.md) ·
[Fixed design/registration snapshot](../../config/anytime-calibration-v1-preparation.json) ·
[Exact calibrator source](../../nfl_lab/anytime_calibration.py) ·
[Curated fictional source-only checks](../../tests/test_anytime_calibration.py) ·
[Source/publication provenance](PROVENANCE.json)

## Population and chronology

This is a distinct **REG 2023–2024 evaluation**, with **10,157 supported binary
outcomes / 14,282 offered rows**, 544 games and 36 season-week blocks. It is not
the three-year, 15,251-outcome point/CDF panel. The event is rushing-or-receiving
TD among RB/WR/TE players, conditional on playing; no participation probability
was learned. Unknown participation (4,101), played-missing labels (24) and all
366 offered base-fallback rows remain explicit. No DNP rows occur in this
matched sample; that does not establish a complete DNP census.

The fixed bases are the corrected fresh leaf CDF and archived CatBoost medium.
Base forecasts are annual out-of-fit predictions, trained through the previous
year. Calibration uses 2022 for 2023 evaluation and 2022–2023 for 2024 evaluation.
Only supported labels with known availability strictly before the earliest
evaluation cutoff may train a calibrator. All 2023 models/predictions freeze
before 2023 labels enter 2024 calibration; all 16 models and all predictions
freeze before evaluation scoring. Missing clocks/labels are not zero-filled.
No 2025+ or protected future labels were read.

## Fixed methods and result

Four global monotone recipes were fixed for each base: intercept-only logit
shift, nonnegative-slope Platt, nonnegative-parameter beta and increasing
isotonic PAVA. There was one attempt per method/base/horizon, no parameter
search or retry, and no calibration fallback. The logistic objective is mean
NLL plus 0.01/2 identity-slope shrinkage, with an unpenalized intercept and a
200-iteration limit. The archived design specifies minimum class support,
chronology, source matching and exact endpoint conventions.

| Base | Unchanged Brier | Intercept | Platt | Beta | Isotonic |
|---|---:|---:|---:|---:|---:|
| Fresh CDF | 0.141021013 | 0.141437085 | 0.141134319 | 0.141152159 | 0.141426164 |
| CatBoost medium | 0.140820746 | 0.141094170 | 0.141028145 | 0.141026949 | 0.141168936 |

Lower is better. Small fresh-CDF Platt/beta Brier improvements in 2023 reverse
in 2024; all eight recipes worsen 2024 and pooled Brier versus their own base.
All beat the weaker pooled event-rate control, which does not establish an
improvement over either forecasting base. Fresh-CDF Platt/beta pooled NLL is
slightly lower than its own base, but the registered primary is Brier.

Fresh-CDF isotonic produces **two genuine positive-infinite log losses in
2023**, retained in the pooled result. No probability clipping or affected-row
deletion is used; finite paired NLL intervals are undefined for those views.
Fresh-CDF intercept/isotonic pooled Brier harm intervals are above zero for
both clusterings, with descriptive, unadjusted interpretation. No supported
evaluation forecast is at or above 0.9, so that extreme upper tail is untested.

## Acceptance and reproducibility limits

Independent review passed **168,946 checks, zero mismatches**: all 16 saved
calibrators replayed, 33 summaries, 144 fixed metric/period/control contrasts,
276 finite intervals (138,000 draws) and 12 explicit nonfinite interval slots.
The review fitted no models and adds no new football observations. Both 500-draw
whole-week and whole-game interval views are nominal, exposed-development
diagnostics, not simultaneous scientific qualification.

The exact calibrator module and prepared design are public. Its shared numeric,
support, alignment and bootstrap dependencies already exist in this repository;
package dependencies are in the existing lockfile. The design's prepared-state
field is retained as historical source, not current execution status. The public
test file is an explicitly curated five-check fictional derivative: private
controller/freeze fixtures are excluded. The focused public derivative passed **five checks in 1.42 seconds**
(pytest time); its process used 2.517698 CPU / 2.165190 wall seconds and
180,649,984 bytes peak child RSS. No broader local suite was rerun. The original six-check source hash and derivative hash are in
provenance.

This package does not publish the private executor/controller manifests,
row-level probabilities/labels/features, fitted isotonic knot maps, full base
model artifacts or private locators. Public aggregate source identities and
coefficient metadata support inspection but do not supply the bytes needed to
reproduce original row-level scoring. The accepted result packet remains
byte-identical to the independently reviewed safe successor.

Observed execution used 24.536802479 CPU / 15.267301713 wall seconds and a
288,575,488-byte conservative combined RSS bound; HTTP and base refits were zero.
No SITE/R0 gain, future issuance, entrant, selected/deployed/live-verified
candidate or scientific qualification is claimed. Current-source/artifact,
future-query replay/restoration and consumer acceptance still belong to the
incumbent owner; original registrations, scheduler and deployment sequence stay
unchanged. There is no inherited eight-week prerequisite for the provisional
track.
