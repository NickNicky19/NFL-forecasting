# Recorded point comparisons with CDF corrections — October 25, 2026

**Independent numerical acceptance: ACCEPTED.**

Two frozen candidate families versus two fixed correction controls: **44 pooled comparisons and 132 annual diagnostics** on exposed REG 2022–2024, **815 games and 54 season-week blocks**. Category rows overlap. The comparison added **zero fits, inference calls, model loads or HTTP requests**. Literal saved predictions were retained.

[All 44 pooled comparisons](pooled-comparisons.csv) · [All 132 annual diagnostics](annual-diagnostics.csv)

Counts compare recorded means using MSE; signed yards compare recorded medians using MAE; anytime TD compares genuine event probabilities using Brier. Units remain separate. Positive percentages below mean lower candidate primary loss against the named correction control. They are descriptive exposed-data differences.

I = fixed intercept correction; C = fixed context correction. Monotone = `threshold_cdf`; response = `distribution_split_cdf`. Percentages are preserved at their original floating-point precision.

| Target | Point product | Scored / offered | Monotone vs I (%) | Monotone vs C (%) | Response vs I (%) | Response vs C (%) |
|---|---|---:|---:|---:|---:|---:|
| pass_yd | Median MAE | 1960 / 4091 | -1.1937352036213045 | -1.1937352036213045 | -0.062462888561591504 | -0.062462888561591504 |
| pass_td | Mean MSE | 1960 / 4091 | -0.973713619773287 | -1.4899313795097207 | +0.5438426815723396 | +0.03538327285689023 |
| pass_cmp | Mean MSE | 1960 / 4091 | -3.832860813945859 | -3.34278076282808 | -0.2567459344904794 | +0.21645523503636543 |
| pass_att | Mean MSE | 1960 / 4091 | -2.367887464765606 | -1.678199199526002 | +0.24061259601952023 | +0.9127264839191651 |
| pass_int | Mean MSE | 1960 / 4091 | -0.7257957542260406 | -0.6608866623071665 | +0.2374624468814696 | +0.3017508019310132 |
| rush_yd | Median MAE | 4558 / 6235 | -3.471333681950164 | -3.471333681950164 | -0.18469275359093193 | -0.18469275359093193 |
| rush_att | Mean MSE | 4558 / 6235 | -3.243394823583728 | -4.00418097199096 | +0.7161175435410316 | -0.015491511566400927 |
| rec | Mean MSE | 15251 / 21504 | -2.101317851734444 | -2.2640133795676847 | +0.3356129178211604 | +0.17680056942368072 |
| rec_yd | Median MAE | 15251 / 21504 | -1.032855952838648 | -1.032855952838648 | +0.09411444316288575 | +0.09411444316288575 |
| rush_rec_yd | Median MAE | 15251 / 21504 | -2.1773637744298653 | -2.1773637744298653 | +0.07733976168125573 | +0.07733976168125573 |
| anytime_td | TD probability Brier | 15251 / 21504 | -0.18542398099866417 | -0.17937347848088891 | -0.0028935213491523854 | +0.0031459575989078842 |
| fantasy_ppr | Exact labels blocked | — | Blocked | Blocked | Blocked | Blocked |

The response method has lower pooled primary point loss for **6 of 11 targets** versus the lower-loss of these two correction controls; the monotone method does so for **0 of 11**. All **22 response week/game 95% intervals** against that stronger correction include zero. The six-target count supplies no best-overall ranking: the separately assessed COUNT_A reception-mean control remains stronger in the broader cached-control comparison.

## Small gains and retained adverse result

- **Response pass_td versus context:** primary loss 1.0619745013505355 versus 1.0623503956897387; change +0.03538327285689023%. Candidate-minus-control week CI [-0.008828033516156197, 0.008644574010731258]; game CI [-0.009230848861384911, 0.007873121590434639]. Candidate/control bias 0.06827012506318142 / 0.03536508275816763; p95 absolute error 1.9212898435315302 / 1.947942793744465.
- **Response pass_att versus intercept:** primary loss 113.9007310602089 versus 114.17545157826838; change +0.24061259601952023%. Candidate-minus-control week CI [-0.8919719407610314, 0.3480630194480758]; game CI [-0.8111592539395946, 0.3290110962121499]. Candidate/control bias 0.5041907741572343 / 0.45915541766570406; p95 absolute error 21.44702593002134 / 21.68900286795597.
- **Response TD alias versus intercept:** primary loss 0.14096923634165753 versus 0.14096515748473085; change -0.0028935213491523854%. Candidate-minus-control week CI [-3.1684909455444856e-05, 4.150351370106451e-05]; game CI [-3.0163167697611364e-05, 3.733347002164227e-05]. Candidate/control bias 0.012781094948786799 / 0.01091471292084775; p95 absolute error 0.8174045774866326 / 0.8190880509323518.

## Interpretation and coverage

The previously reported combined-yard CRPS lead concerns the full predictive distribution. This supplement evaluates saved mean, median and event-probability products against point correction controls; it supplies no CRPS comparison with those controls.

The 22 correction-control annual cells in 2022 retain their original no-earlier-OOF startup aliases. The response anytime-TD candidate retains its unchanged fresh leaf-CDF alias. Per-method fallback populations remain included and may differ. All offered primary-role forecasts and all supported played outcomes are covered. Played zero, unknown participation, DNP, missing outcomes and invalid outcomes remain distinct. No favorable intersections or fallback exclusions were introduced.

The CSVs include primary losses, MAE/MSE/RMSE, signed bias, p95 absolute error, offered/forecast/supported/scored coverage, participation/missingness counts and fallback-stratum losses for both methods. Blank CSV cells mean unavailable/null; literal zero remains zero. Every supplied float retains round-trip precision.

Intervals are nominal descriptive 95% paired diagnostics: **500 PCG64 replicates** for whole season-week clusters (seed **1911**) and whole game clusters (seed **1912**), with linear percentiles. Intervals describe candidate-minus-control loss; negative differences favor the candidate. Annual views retain all three years. No intervals were resampled while formatting this supplement.

Independent numerical review passed **17,597 checks**, including all 44 pooled comparisons, 132 annual diagnostics and 352 week/game intervals (176,000 bootstrap replicates), with **zero mismatches and maximum absolute difference 0.0**. This adds no independent football observations.

Availability remains a current-vintage kickoff-plus-seven-day reconstruction. Historical SITE/R0 forecasts are unavailable for this panel. This comparison supplies no nomination, selection, scientific qualification or deployment approval.

Observed combined comparison resources: **13.636363452 CPU seconds**, **9.300477295008022 wall seconds**, and **247070720 bytes** conservative combined RSS.
