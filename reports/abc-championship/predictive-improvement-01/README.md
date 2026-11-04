# Session A: targeted carry improvement results

Assignment **ABC-PREDICTIVE-IMPROVEMENT-01**. Checkpoint: **November 04, 2026, 03:36 PM CST** (2026-11-04T21:36:04.539712+00:00).

**The new information produced small numerical gains, but did not beat the strongest complete direction procedure. The structured allocation challenger lost.** This is an executed A contribution; the all-category, all-period A/B/C championship remains incomplete. C remains coordinator.

## 1. Full recovered carry board

Requested: 2026 Weeks 1–8. **Actually scored: Weeks 1–7, 335 offers, 327 decided outcomes, eight unknown participation cases, 81 games.** The board contains **239 RB, 80 QB and 16 WR** offers. Every direct procedure below attempted the same board.

These are current-vintage, timing-unverified reconstructions at retained thresholds. They are statistical directions, not original recommendations or verified bookmaker settlements.

| Procedure and output rule | Over W–L / N / rate | Under W–L / N / rate | Combined W–L / N / rate | Eligible / selected / unavailable |
|---|---:|---:|---:|---:|
| A0_BACKFIELD_CDF / P1_MEAN | 70–60 / 130 / 53.85% | 104–93 / 197 / 52.79% | 174–153 / 327 / 53.21% | 335 / 335 / 0 |
| A1_BACKFIELD_CDF_ROLE_INPUTS / P1_MEAN | 70–61 / 131 / 53.44% | 103–93 / 196 / 52.55% | 173–154 / 327 / 52.91% | 335 / 335 / 0 |
| A0_BACKFIELD_CDF / P2_EXACT_LAW | 44–44 / 88 / 50.00% | 120–119 / 239 / 50.21% | 164–163 / 327 / 50.15% | 335 / 335 / 0 |
| A1_BACKFIELD_CDF_ROLE_INPUTS / P2_EXACT_LAW | 49–39 / 88 / 55.68% | 125–114 / 239 / 52.30% | 174–153 / 327 / 53.21% | 335 / 335 / 0 |
| STORED_COUNT_A_MEAN_CONTROL / P1_MEAN | 71–63 / 134 / 52.99% | 101–92 / 193 / 52.33% | 172–155 / 327 / 52.60% | 335 / 335 / 0 |
| ALWAYS_OVER / CONSTANT | 163–164 / 327 / 49.85% | N/A | 163–164 / 327 / 49.85% | 335 / 335 / 0 |
| ALWAYS_UNDER / CONSTANT | N/A | 164–163 / 327 / 50.15% | 164–163 / 327 / 50.15% | 335 / 335 / 0 |

**Observed complete-procedure tie:** A0 mean direction and A1 exact-law direction each scored **174/327**. A1 mean direction lost one decision to A0 mean. A1 law direction gained ten decisions against A0 law, but tied the stronger mean-direction reference.

The highest own Over rate here is **A1 law: 49/88, 55.68%**. The highest own Under rate is **A0 mean: 104/197, 52.79%**. They selected different pools. They were not combined into a router.

A0 is the unchanged Backfield CDF. A1 uses the same learner, labels, imputation and tree settings, with 12 additional forward role/opportunity features. Count A is a retained point-only control; no probabilities were fabricated for it. Means and medians are separate outputs of one fitted procedure.

## 2. Structured model: separate RB comparison

A2 propagates uncertain provider team carries through a forward role state and finite allocation. S0 uses the same volume law and allocation inputs with ordinary recency weighting. Both support **239/335 offers**; the other 96 remain unavailable. Their 231 decided RB outcomes must not be ranked as complete 335-offer results.

| Procedure and output rule | Over W–L / N / rate | Under W–L / N / rate | Combined W–L / N / rate | Eligible / selected / unavailable |
|---|---:|---:|---:|---:|
| A0_BACKFIELD_CDF / P1_MEAN | 48–43 / 91 / 52.75% | 66–74 / 140 / 47.14% | 114–117 / 231 / 49.35% | 239 / 239 / 0 |
| A1_BACKFIELD_CDF_ROLE_INPUTS / P1_MEAN | 51–42 / 93 / 54.84% | 67–71 / 138 / 48.55% | 118–113 / 231 / 51.08% | 239 / 239 / 0 |
| A2_DYNAMIC_ALLOCATION / P1_MEAN | 8–14 / 22 / 36.36% | 95–114 / 209 / 45.45% | 103–128 / 231 / 44.59% | 239 / 239 / 0 |
| S0_RECENCY_ALLOCATION / P1_MEAN | 8–11 / 19 / 42.11% | 98–114 / 212 / 46.23% | 106–125 / 231 / 45.89% | 239 / 239 / 0 |
| A2_DYNAMIC_ALLOCATION / P2_EXACT_LAW | 6–10 / 16 / 37.50% | 99–116 / 215 / 46.05% | 105–126 / 231 / 45.45% | 239 / 239 / 0 |
| S0_RECENCY_ALLOCATION / P2_EXACT_LAW | 4–8 / 12 / 33.33% | 101–118 / 219 / 46.12% | 105–126 / 231 / 45.45% | 239 / 239 / 0 |
| ALWAYS_OVER / CONSTANT | 122–109 / 231 / 52.81% | N/A | 122–109 / 231 / 52.81% | 239 / 239 / 0 |

On RBs, A1 mean gained **4/231, +1.73 percentage points**, versus A0 mean; the paired game interval was **−2.03 to +6.01 points**. Always-Over still won four more. A2 law tied recency direction and its mean lost three decisions to recency. A2 improved proper probability loss against that weaker structured control, but remained much worse than the CDF controls.

The [population correction](POPULATION_CONTRACT_RECONCILIATION_V2.json) reproduces the old mixed A0 mean total: **46 QB wins + 114 RB wins + 14 WR wins = 174**. The old 335-offer score stays intact; its RB-only description is superseded. The earlier 526-outcome RB numerical study is unchanged.

## 3. Numerical accuracy and history

The numerical panel is separate: **1,244 roster RB queries, 586 supported outcomes, 658 unknown/missing cases, 107 games** in 2026 Weeks 1–7. The 2025 check has **923 queries, 700 supported outcomes and 121 games** in Weeks 1–8. No missing statistic became zero.

| Procedure | 2026 mean MAE | 2026 median MAE | 2026 mean RMSE | 2025 median MAE |
|---|---:|---:|---:|---:|
| A0_BACKFIELD_CDF | 3.732204 | 3.627986 | 4.874174 | 3.260000 |
| A1_BACKFIELD_CDF_ROLE_INPUTS | 3.686916 | 3.580205 | 4.855573 | 3.274286 |
| A2_DYNAMIC_ALLOCATION | 4.548631 | 4.709898 | 6.261530 | 3.702857 |
| S0_RECENCY_ALLOCATION | 4.817309 | 4.901024 | 6.656783 | 3.757143 |
| STORED_COUNT_A_MEAN_CONTROL | 3.821099 | N/A | 4.976096 | N/A |

A1 median reduced 2026 MAE by **0.047782 carries**; paired game interval **−0.121212 to +0.029469**. In 2025 it worsened MAE by **0.014286**. Both intervals include no change. A2 had severe underprediction: 2026 mean bias **−3.139933**, versus A1 **−0.182046**.

The 2025 models train only through 2024; the 2026 models train through 2025. Both retain the established 2019 warm-start history and original seven-day availability assumption. State features update forward only. This is not a completed CURRENT/RECENT/MULTI history tournament.

On the offered RB subset, A1 **mean** MAE was 4.278004 versus **median** 4.350649. The same model's mean and median disagreed on 21 decisions: mean won 13, median eight. Lower display MAE does not establish a better side rule.

## 4. Probability and the 90% aspiration

Full-board binary Brier: **A0 0.264806; A1 0.266243; neutral 0.25**. A1 worsened full-board log loss too: **0.736492 versus 0.730459**. RB-only A1 Brier improved slightly, showing why population boundaries matter. A2 and S0 RB Briers were **0.411792 and 0.450579**. All tested laws lost to neutral on their matching binary masks.

The existing 55% confidence replay selected 184/239 RB offers and won **87/178 decided, 48.88%**. The best cumulative Top-6 diagnostic was **25/42, 59.52%**. Week 4 contains raw 6/6 maxima. Those small exposed lists lack qualified simultaneous quote availability; they are not issued tickets or evidence of a useful 90% policy. **TARGET_NOT_ESTABLISHED.** B retains the learned selective-policy work.

165 of 239 RB offers have listed two-sided numeric prices, but **zero** have qualified pregame quote and settlement support in this panel. Missing prices did not block direction scoring. No profitability or EV result is claimed.

## 5. What ran and what was saved

- **Three successful CDF fits across four attempts**, with one thread-pool fit failure retained. The completed 2025 control was reused, not refit.
- A separate runtime completed both A1 fits, then failed its bundle-size guard. Its full forecast rows and models were preserved. A separate **zero-fit content admission and scoring** step reused those exact bytes; both failed runs remain failed.
- **10,104 retained procedure/player-game records** include 192 later non-RB inferences and 1,244 reused Count A controls. Different outputs and repeated scoring views are not independent NFL outcomes.
- Independent calculations checked **152 numerical cells, 176 RB side cells and 136 full-board side cells**, plus original identities, lines, labels, clocks, a real exact-law integral and the extra control replays. [Verification](INDEPENDENT_FULL_BOARD_VERIFICATION_V1.json) · [Exact verification source](../../../tools/abc_a_independent_full_board_verification_v1.py).
- Full law bytes, models and readable scorecards remain in the approved private store with hashes and fresh-process readback. **Off-host restoration is not verified.**

The model uses total credited team carries, an explicit other/unresolved bucket and conditional-on-appearance laws. It does not separate designed runs, scrambles and kneels or invent full/limited injury probabilities. Exact summation required no Monte Carlo. The [technical receipt](TECHNICAL_RECEIPT_V1.md) preserves numerical precision, volume errors, fallback counts, all failures and reproduction limits.

## 6. Recommendations, capture and actual live state

**Display research candidate:** A1 median for the evaluated RB population. Its current model is bound in the [owner-review package](CATEGORY_RELEASE_RECOMMENDATION_V1.json). Current-source inference, private restoration, typed wrapper/catalog/consumer checks, fallback, rollback and owner admission remain unverified. Expected means remain independently selected. This wave supports no automatic probability, selection or EV release.

The existing prepared `stat_point_mae_v2` package remains independent. The retained owner can advance operationally eligible categories through its existing provisional policy. No new eight-week, full-history or profitability wait is introduced.

Latest served readback, **November 4 at 3:55 p.m. CST**: Week 9 selected overlay **DISABLED_USE_R0**, zero selected rows; payload SHA **f65e8f94329048ab8b087949a577368d45f112b5b77cc0faa871a08241d44dac**. That fallback label does not establish the underlying legacy model's exact identity or browser DOM values. **No A model was deployed and no new genuine pregame capture was made in this wave.** Existing original forecasts remain preserved.

The [existing owner delivery](https://github.com/NickNicky19/NFL-forecasting/pull/1#issuecomment-6533786373) is delivery, not verified execution acknowledgement. The outstanding owner action is to execute research commit **341742de83975264a07d035d4b6289e57c2ec1e9**, file `reports/category-topfive-mae-release-priority-20261030/OWNER_EXECUTION_V1.json`, under retained lease 178: restore the named checkpoint and assignments, authenticate current bindings, admit ready typed products, capture before their actual current deadlines, publish and verify served values. New A1 artifacts require their own approved restoration; they are not in that older checkpoint.

## 7. Coverage closure and ownership

| Category | This wave / remaining responsibility |
|---|---|
| Passing yards | Earlier evidence retained; no new A fit; C coordinates remaining comparable period cells. |
| Passing TDs | B owns probability/selectivity improvement; A grades and evidence remain preserved. |
| Completions | Prior diagnoses retained; no new A fit or release. |
| Passing attempts | A/B history and coverage cells remain; no duplicate B recovery or probability fit. |
| Interceptions | Prior count/probability studies retained; no new A fit. |
| Rushing yards | QB/RB populations stay separate; no new A fit. |
| Rushing attempts | This executed wave; W8 and older historical-origin extensions remain. |
| Receptions | C owns target-share inputs, B owns selection; A conversion extension needs a qualified C export. |
| Receiving yards | Prior procedures and adverse controls retained; no new A fit. |
| Rush + receiving yards | No carry gain transferred to this product. |
| Anytime TD | No qualified matching offered-event panel here; existing probability product unchanged. |
| Exact chart PPR | Same-chart offers and operational admission remain separate; legacy fantasy is not relabeled. |

Receiving targets remain an additional forecast-only product; no targets market was invented. C remains the only consolidated benchmark coordinator. These new A artifacts await C's actual intake; public publication is not admission or raw-row parity.

Next A work: qualify the W8 historical query and complete past team totals, then reuse the retained 2026 models; register the supported 2022–2024 origin fits with retention sizing before execution. Original roles/NGS/FTN, history, TabICLv2, chronological TabR, relevance and audit tasks remain resumable under their existing ownership.

[Weekly method/side CSV](EACH_METHOD_OWN_SIDES_BY_WEEK_V1.csv) · [Season/week numerical CSV](NUMERICAL_BY_SEASON_WEEK_V1.csv) · [Canonical results](../../opportunity-four/ALL_RESULTS.json) · [Canonical linked side records](../../opportunity-four/ABC_DYNAMIC_CARRY_SELECTION_RESULTS_V1.json) · [Paired losses, uncertainty and Top-K](MATCHED_ANALYSIS_RESULTS_V1.json) · [Manifest for C](CURRENT_ARTIFACTS_FOR_C_V1.json).

## Storage and final scorecard receipt

The full **5,695-row private scorecard** is saved and read back: SHA-256 `3e5b1b86986c090bd21711003c2114d1aac2163deec522258c71bb2c9ca26a5e`, 135,260 compressed bytes. It formats existing grades and adds no fit, inference or score. Off-host restoration remains unverified. The first CSV attempt failed at the metadata guard; that failure and a 4.792-second measured CPU-budget overrun on the retry remain visible.

Lossless, content-addressed compression of two public aggregate registries saved **1,954,012 bytes** in the same accounted scope. Every original uncompressed byte and all 280 results/312 selection records remain recoverable through the canonical indexes. The eight-MiB guard and all prior caps were preserved. [Storage proof](REGISTRY_STORAGE_RECEIPT_V1.json) · [CSV receipt](FULL_BOARD_READABLE_SCORECARD_RECEIPT_V1.json) · [Resource adverse receipt](FULL_BOARD_CSV_RESOURCE_ADVERSE_V1.json).
