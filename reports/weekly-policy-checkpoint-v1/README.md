# Weekly policy checkpoint: twelve categories

**Completed aggregate checkpoint, 2026-10-24. Exposed historical reconstruction; no fresh confirmation, live selection, or publication.**

All 11 supported categories completed P0–P4 over **REG 2022–2024, 54 season-week blocks and 815 games**: 2,970 weekly policy results. Exact PPR remains blocked. Historical reference is **LAB_CDF**, with no authentic contemporaneous SITE/live_R0/raw comparator. The old 854-game/postseason panel and exposed 2026 Week 6 website studies are separate; they are not pooled into these rankings.

The lowest observed policy improves on LAB_CDF in seven categories and on the strongest fixed replay-catalog member in six. These are descriptive minima after looking at the exposed sample, not an optimal model or future-performance guarantee. Receptions illustrate the difference: P2 beats CDF but still loses fixed Count A. No registration/default was changed by this report.

## All policy losses and fixed controls

Lower is better. Count targets use expected-mean **MSE** (squared target units); signed yards use point **MAE** (yards); anytime rush/receive TD uses genuine probability **Brier**. Exact losses, optional count RMSE displays, all 44 paired comparisons and 88 interval views are in [aggregate.json](aggregate.json). Different target units are never averaged.

| Target | Primary | Scored n | P0 LAB_CDF | P1 | P2 | P3 | P4 | Strongest fixed replay member | Lowest policy |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| pass_yd | point_mae | 1,960 | 66.16173469 | 66.66941236 | 66.21615902 | 66.28498609 | 66.12044852 | CDF 66.16173469 | P4 |
| pass_td | point_mse | 1,960 | 1.06824166 | 1.07482469 | 1.07220331 | 1.07018054 | 1.07156786 | CDF 1.06824166 | P0 |
| pass_cmp | point_mse | 1,960 | 51.37535676 | 51.74366340 | 51.64478443 | 51.86699400 | 51.49733703 | CDF 51.37535676 | P0 |
| pass_att | point_mse | 1,960 | 114.20693762 | 113.96346761 | 114.05014961 | 114.28940566 | 113.87577075 | CDF 114.20693762 | P4 |
| pass_int | point_mse | 1,960 | 0.67906633 | 0.69504557 | 0.68075325 | 0.68013198 | 0.68345850 | CDF 0.67906633 | P0 |
| rush_yd | point_mae | 4,558 | 19.71895568 | 19.73932893 | 19.72088969 | 19.73105221 | 19.74407795 | CDF 19.71895568 | P0 |
| rush_att | point_mse | 4,558 | 24.29274701 | 24.12372266 | 24.03521881 | 24.06866258 | 23.94856377 | Count_A 24.02464184 | P4 |
| rec | point_mse | 15,251 | 3.26820150 | 3.24755874 | 3.24565683 | 3.24854887 | 3.24753392 | Count_A 3.24391917 | P2 |
| rec_yd | point_mae | 15,251 | 16.37243459 | 16.35588141 | 16.35774261 | 16.35562954 | 16.34294697 | CatMedium 16.34339800 | P4 |
| rush_rec_yd | point_mae | 15,251 | 21.02570323 | 21.02199926 | 21.00347917 | 20.99636531 | 20.96611282 | CatMedium 20.98392514 | P4 |
| anytime_td | brier | 15,251 | 0.14096924 | 0.14090132 | 0.14085824 | 0.14074318 | 0.14064701 | CatMedium 0.14076309 | P4 |
| fantasy_ppr | BLOCKED | 0 qualified labels | — | — | — | — | — | No qualified label contract | None |

Fixed catalog: LAB_CDF and CatBoost medium for all 11, plus Count A for six counts. Count A is a genuine Poisson-objective point estimator, not a fitted predictive count law. The frozen historical catalog excludes six small-correction jobs without an authentic generation/model witness. Their previously completed public results still matter: passing-TD context correction MSE **1.0623503956897387** beats every policy above; passing-attempt intercept correction MSE **114.17545157826838** is beaten by P4. These are separate fixed-frontier comparisons, not retroactive entrants.

| Target | Lowest-policy improvement vs CDF | vs strongest fixed replay member | vs prior fixed frontier incl corrections |
|---|---:|---:|---:|
| pass_yd | +0.0624% | +0.0624% | +0.0624% |
| pass_td | +0.0000% | +0.0000% | -0.5546% |
| pass_cmp | +0.0000% | +0.0000% | +0.0000% |
| pass_att | +0.2900% | +0.2900% | +0.2625% |
| pass_int | +0.0000% | +0.0000% | +0.0000% |
| rush_yd | +0.0000% | +0.0000% | +0.0000% |
| rush_att | +1.4168% | +0.3167% | +0.3167% |
| rec | +0.6898% | -0.0536% | -0.0536% |
| rec_yd | +0.1801% | +0.0028% | +0.0028% |
| rush_rec_yd | +0.2834% | +0.0849% | +0.0849% |
| anytime_td | +0.2286% | +0.0825% | +0.0825% |

Positive percentages mean lower error; negative percentages mean worse. Fixed-member comparisons use the recovered matched aggregate controls; the 44 bootstrap comparisons are specifically P1–P4 versus P0, not versus the retrospectively strongest fixed member. Equal sample size alone would not establish matching rows.

## Policies, products and chronology

- **P0:** fixed LAB_CDF reference.
- **P1:** exactly the latest completed eligible graded week; retain current if tied best, then reference, then stable ID.
- **P2:** season-cumulative comparable prior evidence, preserving negative weeks and requiring entrant overlap.
- **P3:** nested earlier-only weekly simulations over half-life {1,4} weeks × switch margin {0,.005}; deterministic startup decay 4/margin 0 when inner evidence is insufficient.
- **P4:** frozen equal weights over the registered shortlist, with per-member reference fallback and no hindsight reweighting. Its signed-yard output is **point_blend**, an arithmetic average of median points, **not an intended median or mixture median**. Binary averaging remains a valid Bernoulli probability; no full-CDF blend was evaluated.

All original earlier-only feature/training rules remain. Weekly procedure choices precede the first schedule kickoff by 6 hours; authentic cached per-game cutoffs are unchanged, including kickoff equality only under the explicitly reconstructed-kickoff horizon. Current-vintage replay availability at kickoff+48h, weekly completion at the last kickoff+48h and assumed finality at the last kickoff+12h are declared assumptions. They are not upstream publication/finality witnesses. Actual 2026 catalog/forecast-freeze timestamps are retained, not relabelled historical issuance.

## Bias, tails and coverage

The next table reports only P0 and the lowest observed policy, because those are the secondary summaries in the supplied aggregate. Bias is prediction minus actual; tail is 95th-percentile absolute error. Neither secondary quantity replaces the registered primary. For example, P4 reduces anytime-TD Brier but worsens its p95 error; reception and combined-yard tails also worsen. Passing-yard blend bias worsens slightly despite lower MAE.

| Target | Bias P0 → lowest policy | p95 absolute error P0 → lowest policy | Offered / scored | Unknown participation | Played missing/unsupported | Fallback | Played zero |
|---|---:|---:|---:|---:|---:|---:|---:|
| pass_yd | -0.284184 → -0.291004 | 174.000000 → 169.054540 | 4,091 / 1,960 | 2,131 | 0 | 64 | 110 |
| pass_td | 0.063993 → 0.063993 | 1.947512 → 1.947512 | 4,091 / 1,960 | 2,131 | 0 | 64 | 668 |
| pass_cmp | 0.174540 → 0.174540 | 14.132859 → 14.132859 | 4,091 / 1,960 | 2,131 | 0 | 64 | 110 |
| pass_att | 0.474992 → -0.017428 | 21.689003 → 21.184290 | 4,091 / 1,960 | 2,131 | 0 | 64 | 79 |
| pass_int | 0.012315 → 0.012315 | 1.462396 → 1.462396 | 4,091 / 1,960 | 2,131 | 0 | 64 | 1,096 |
| rush_yd | -6.760641 → -6.760641 | 62.000000 → 62.000000 | 6,235 / 4,558 | 1,665 | 12 | 157 | 739 |
| rush_att | 0.109633 → 0.099598 | 9.995893 → 10.086335 | 6,235 / 4,558 | 1,665 | 12 | 157 | 682 |
| rec | 0.053270 → 0.032303 | 3.672779 → 3.691718 | 21,504 / 15,251 | 6,229 | 24 | 545 | 3,786 |
| rec_yd | -5.756213 → -5.600049 | 54.000000 → 54.137940 | 21,504 / 15,251 | 6,229 | 24 | 545 | 3,884 |
| rush_rec_yd | -6.415383 → -6.214534 | 64.000000 → 64.040433 | 21,504 / 15,251 | 6,229 | 24 | 545 | 2,519 |
| anytime_td | 0.012781 → 0.010706 | 0.817405 → 0.820439 | 21,504 / 15,251 | 6,229 | 24 | 545 | 12,339 |

All offers and negative weeks remain. The paired summaries report zero missing-grade and known-DNP rows, and zero candidate/P0 missing points on their paired view. This does **not** prove zero fallback: reference fallback supplies valid points. Unknown participation and unsupported played labels are unscored, never filled with zero. The authenticated existing grade-coverage export confirms all five policies forecast every offered row, with zero abstentions. Fallback counts are 64 for each QB category, 157 for each RB category and 545 for each broad skill category; they are identical across P0–P4 and are included in the scores. The table also preserves category-specific observed played zeros; scored played-zero counts are identical here. Counts are not added across policies as new observations.

## Uncertainty is conditional and descriptive

There are **44** exposed policy/category comparisons (P1–P4 vs P0 across 11 targets), each with week and game cluster views: **88 nominal 95% intervals**, 500 whole-cluster replicates, PCG64, seed 1703, linear percentile endpoints. They condition on the already computed frozen policy sequence; no model refits or policy reselection occur in the bootstrap. They are neither familywise nor winner-selection adjusted and do not establish selected-winner or future-confirmation proof. All 44 comparisons, including losses and intervals crossing zero, remain in the JSON. Repeated policies/fits/bootstrap draws add no NFL games.

## What actually ran, and what remains proposed

The [twelve-category scientific matrix](scientific-matrix.json) records completed study families per target and the [research index](../RESEARCH_INDEX.md) links their original formulas, configurations, results and failures. All 11 had source-matched base comparisons, direct XGB/LightGBM/CatBoost settings, both conservative corrections and this P0–P4 replay. Six XGBoost binary outputs were technically recovered without new fits. Original direct/correction registrations nominated none. These historical decisions do not impose an old eight-week prerequisite on the separately authorized provisional release track.

| Target | Base/direct/corrections | Separate 80% interval study | P0–P4 replay | NGBoost NFL screen | New future fits |
|---|---|---|---|---|---:|
| pass_yd | Done | Done; unchanged | 54 weeks complete | Unrun | 2 |
| pass_td | Done | Done; unchanged | 54 weeks complete | Unrun | 1 |
| pass_cmp | Done | Done; unchanged | 54 weeks complete | Unrun | 1 |
| pass_att | Done | Done; unchanged | 54 weeks complete | Unrun | 1 |
| pass_int | Done | Done; unchanged | 54 weeks complete | Unrun | 1 |
| rush_yd | Done | Done; unchanged | 54 weeks complete | Unrun | 2 |
| rush_att | Done | Done; unchanged | 54 weeks complete | Unrun | 2 |
| rec | Done | Done; unchanged | 54 weeks complete | Unrun | 2 |
| rec_yd | Done | Done; unchanged | 54 weeks complete | Unrun | 2 |
| rush_rec_yd | Done | Done; unchanged | 54 weeks complete | Unrun | 2 |
| anytime_td | Done | Not interval target | 54 weeks complete | Unrun | 2 |
| fantasy_ppr | Blocked | Blocked | Blocked | Blocked slots | 0 |

“Done” means executed, not scientifically qualified; each original study retains its own cohort and gates. All twelve categories remain scientifically unqualified in this checkpoint. Future fits are a separate runtime inventory, not historical accuracy observations.

Ten numeric categories completed the separate fixed 80% conformal interval study: 20 radii selected zero expansion, with unchanged interval scores on 544 games / 36 blocks in 2023–2024. Anytime TD was not an interval target; PPR was blocked. That is not a new point-ranking result. The proposed NGBoost NFL screen remains unrun (66 supported annual-setting attempts plus six blocked PPR slots); eight software law methods passing inside a failed inventory packet do not count as NFL fits. Dynamic workload retained 24 development packages but has no completed accuracy report in the inspected index. No unrun family is described as tested.

The integrator separately reports **18 new future estimator fits** across the 11 supported categories (11 CDF, 2 Count A (rushing attempts/receptions), 5 CatBoost medium (four yardage targets/anytime TD)), with artifact restoration work. Those are training/runtime evidence, not observed future accuracy and not this replay. **At least 1,196 lifetime NFL estimator fitting attempts** are established by the previous 1,178 lower bound plus those 18; the exact lifetime total remains unknown. Do not sum overlapping historical trial tables, reference calls, closed-form priors, bootstrap replicates, software tests or this zero-fit replay into another total.

## Completion and retained failure lineage

The exact root-supplied completion manifest and receipt were authenticated by metadata-only reads. The replay is COMPLETE_DEVELOPMENT_REPLAY: seven earlier immutable category checkpoints were reused without recomputation and four were completed in the compact continuation. The earlier run remains FAILED at its 8 MiB retention ceiling; its 600 CPU / 285 wall reservation remains conservatively charged, without refund.

Continuation actual CPU was 161.396173822 s, inner runtime wall 161.157735916 s, outer supervisor wall 163.803648272 s and peak RSS 596,279,296 bytes. Total old+new retained output was 7,143,668 bytes. Distinct clock scopes are labelled; the continuation allocation was 180 CPU / 240 wall, with lineage ceilings 780 CPU / 525 wall. This is a computational completion, not extra scientific search, acquisition, fitting or confirmation. Private category/manifest paths, row identities and artifact hashes are withheld from this public package. Only hashes of the three aggregate reporting inputs are retained.

This checkpoint author read aggregate JSON, public indexed reports and completion metadata only. No NFL row or model was decoded, no tests/fits/network ran, no ledger was edited and no output was published. Requested model GPT-6.1 Sol / xhigh; actual backend UNATTESTED.

Inventory correction: the first checkpoint draft misassigned six Count A / one CatBoost fits. Authenticated successful training slots establish eleven CDF / two Count A / five CatBoost. The total eighteen and all historical scores are unchanged.
