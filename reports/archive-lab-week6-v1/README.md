# Matched archived Week 6 comparison

New retrospective study `archive-lab-week6-v1-2026-10-22`. Preregistered in `60b9b89` before its 30 fits; producer code `023c5b3`. All 30 trials completed in 91.22 seconds. The original archive is a local pregame capture; remote publication and original provider publication times remain unverified.

The following table uses identical supported player/game outcomes and finite forecasts across all five methods. `Selected` is the fixed method from the earlier development campaign. Larger pairwise website-only populations are retained separately in the JSON report.

| Target | Matched n | Website MAE | Raw MAE | Recent MAE | Pooled MAE | Selected MAE |
|---|---:|---:|---:|---:|---:|---:|
| pass_yd | 27 | 56.6230 | 51.4470 | 46.4646 | 47.9565 | 50.9528 |
| pass_td | 23 | 0.8061 | 0.7509 | 0.6691 | 0.6591 | 0.6557 |
| pass_cmp | 27 | 4.5637 | 4.6030 | 4.9822 | 4.9037 | 4.6174 |
| pass_att | 27 | 7.1459 | 7.0941 | 7.5026 | 7.3371 | 7.2767 |
| pass_int | 15 | 0.6967 | 0.6607 | 0.5828 | 0.6036 | 0.5694 |
| rush_yd | 80 | 18.5063 | 18.3008 | 16.4641 | 16.1470 | 16.9295 |
| rush_att | 58 | 3.8662 | 3.6762 | 4.3012 | 4.0865 | 4.0641 |
| rec | 179 | 1.4961 | 1.4962 | 1.4048 | 1.4024 | 1.4520 |
| rec_yd | 177 | 18.4487 | 18.3964 | 18.8560 | 18.6371 | 18.7778 |
| rush_rec_yd | 46 | 24.0220 | 22.8293 | 23.7273 | 24.4132 | 26.0377 |

On the pairwise website comparison, the fixed selected method had lower MAE in five of ten numeric categories and higher MAE in five. Its passing-yard MAE was 50.9528 versus website 56.6230 on 27 players across 13 games; RMSE was 63.6188 versus 73.7983. Signed bias worsened from -19.0815 to -22.9350 (prediction minus outcome). The paired MAE difference was -5.6702 yards, with descriptive game-cluster 95% interval [-18.0380, 9.1577]. Recent and pooled passing-yard controls had lower MAE than the fixed selected tree on this same week. All methods and losses remain visible; none was retuned or promoted.

This study preserves all 2,083 archived opportunities: 1,399 numeric-category rows, 396 exact-PPR rows with unsupported lab training outcomes, and 288 anytime rows without bound archived probabilities. Every numeric opportunity received each of the three registered lab forecasts, including explicit fallbacks. Thirteen archived category rows across three player-games had unlinked or ambiguous identities. All nine numeric cold rows used saved position priors for recent/pooled, while the nine selected tree/ridge forecasts used fitted context inference. The selected behavior deviates from the registered pure position-prior fallback requirement; see the protocol-deviation addendum. Played missing statistics, unknown participation and supported zero remain distinct. PPR and anytime lab forecasts abstain; saved TD expectations never become probabilities.

Outcome coverage is material: selected-versus-website matched counts are 23 for passing TDs, 15 for interceptions, 180 for receptions, and 47 for combined yards. Missing rare-count fields remain missing, which can select scored cases toward games with recorded events. These subsets do not establish count incidence accuracy or calibration for the full issued population. Five-method coverage is slightly smaller where the original raw point is absent; the report retains the pairwise and total-offered populations.

Training used 64,846 earlier source rows from 2019 through eligible 2026 Weeks 1–5, with one common cutoff of 2026-10-18T10:48:59Z before every included kickoff. Latest admitted label availability was 2026-10-16T00:15:00Z. The unchanged shared feature builder applied the assumed kickoff-plus-seven-day availability rule; known earlier schedule dates remained available for rest calculations while unavailable statistics were masked. Target-game outcomes were blanked before feature construction and inference. Exact current-vintage ID crosswalks were used without name matching; original historic crosswalk availability remains unverified.

The archive week, prior 2022–2025 results and 2026 Week 6 were already exposed. Current-vintage revisions and assumed availability remain reconstruction limitations. All scored comparisons contain one week, so paired week uncertainty is unavailable under the existing eight-week minimum. Game bootstrap intervals are descriptive and do not provide later-week confirmation or a production qualification. Marginal category accuracy also does not establish a coherent joint export.

This is a new lab comparison. The missing original pooled-YPA executable was not reproduced; its reported gain, worse bias and six fallbacks remain separately preserved. The frozen reception experiment was untouched. No Week 8+ outcomes, new data acquisition, website writes, future-window forecasts or production promotion occurred.

The aggregate JSON retains all 30 trial states and metrics, total coverage, five-method common scores, all 60 strict pairwise comparisons, source/config/code hashes and uncertainty limits. Row-level artifacts remain in ignored local storage. Aggregate scores were recomputed from those saved rows without further fitting.

## Protocol deviation

[protocol-deviation.json](protocol-deviation.json) records the executed cold-start behavior. The selected method used context inference on nine numeric rows, comprising three receptions, three receiving-yard, one rushing-attempt, one rushing-yard and one combined-yard row. All nine selected means differed from their saved position priors; recent and pooled matched those priors on all nine rows. Three cold PPR rows and one cold anytime row remained unsupported. The fallback label alone did not enforce the promised policy.

The original report JSON, forecast rows, trial metadata and metrics remain unchanged. No row was removed and no fit, sensitivity run or numerical substitution was performed. The executed results retain this protocol deviation and do not qualify the selected cold-row policy.
