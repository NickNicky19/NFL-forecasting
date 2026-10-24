# Direct comparison with the original website

Experiment `website-direct-leaf-cdf-v1-20261023` completed 22 fixed fits with zero failed fits, 44 scored contrasts and four blocked PPR contrasts. This is a **postgame reconstruction on exposed 2026 Week 6**, not independent confirmation or a newly qualified replacement. All 2,083 original category offers remain in coverage. Scored player-games overlap across categories; they are not independent samples.

## Twelve-category result

Positive percentages mean lower error than the literal original website on the same supported player-games. Numeric primary error is MAE; TD probability uses Brier. Both fixed panels and both method families are retained. Base uses player history; context adds lagged team/opponent and schedule features. The blend was fixed before execution at 50% website + 50% model median (TD uses probabilities); no weight search. Numeric blends are point heuristics, not a claimed predictive law.

| Category | Scored / offered | SITE error | Pure base / context improvement % | Blend base / context improvement % |
|---|---:|---:|---:|---:|
| Passing yards | 27 / 37 | 56.622963 | +8.62 / +13.86 | +8.25 / +10.35 |
| Passing TDs | 27 / 37 | 0.844444 | +16.67 / -0.88 | +8.42 / -0.35 |
| Completions | 27 / 37 | 4.563704 | -5.50 / +0.18 | +0.91 / +4.27 |
| Pass attempts | 27 / 37 | 7.145926 | -3.14 / -1.07 | -0.28 / +1.28 |
| Interceptions | 27 / 37 | 0.663704 | -6.03 / +16.29 | -2.96 / +8.20 |
| Rushing yards | 97 / 137 | 16.390825 | +10.37 / +10.44 | +11.26 / +11.61 |
| Rush attempts | 70 / 100 | 3.383000 | -8.95 / -11.48 | +1.63 / +0.78 |
| Receptions | 258 / 359 | 1.262868 | +0.25 / +0.87 | +0.91 / +1.22 |
| Receiving yards | 258 / 359 | 15.113295 | -1.07 / -1.12 | +2.89 / +3.13 |
| Rush + rec yards | 192 / 259 | 19.601823 | -4.02 / -3.55 | +1.62 / +2.07 |
| Exact offensive PPR | 0 / 396 | unavailable | blocked / blocked | blocked / blocked |
| Anytime rush/rec TD | 249 / 288 | 0.142402 | +3.97 / +3.24 | +3.25 / +2.91 |

All scored categories span one week and 13 games. See [all 48 contrasts](aggregate-report.md) and [machine-readable evidence](aggregate-report.json) for exact SITE/raw/simple cohorts, RMSE, bias, tails, missingness, fallback and probability diagnostics. No confidence interval, significance, winner selection or promotion is asserted.

## Findings and adverse results

- Rushing-yard blends improve MAE, RMSE and bias against SITE, and MAE against raw and the saved simple control on each exact matching cohort. These are promising development results.
- Passing yards improve against SITE, but the base forecasts lose to raw. The context forecast has worse underprediction than SITE. The separate older pooled-YPA reconstruction remains an exposed 20.16% MAE lead with worse bias, not an authenticated reproduction of its missing original runner.
- Passing TDs, attempts and interceptions depend on the panel. The losing panels remain in the table. Interception underprediction worsens; even the context blend slightly worsens RMSE.
- Rush-attempt blends slightly improve SITE MAE but lose to raw, worsen RMSE and increase underprediction. Reception blends improve MAE by about 1% while worsening RMSE and bias.
- Receiving-yard blends reduce MAE against SITE/raw/simple but slightly worsen SITE RMSE and increase underprediction. Combined-yard blends reduce MAE but worsen bias.
- Anytime-TD pure and blend probabilities improve Brier and natural-log loss against SITE and the prior-trained simple control; calibration is not established. There are 249 resolved outcomes, 46 YES/203 NO, and 39 unresolved offers. No raw provider event-probability comparator exists.
- Separately modeled combined means are nonadditive by more than 0.03 yards in 99/100 common triples for both panels. They are not a coherent joint package. There are no expected-completion/attempt violations in either 37-row panel. See [coherence audit](coherence-audit.json).
- Exact PPR remains unscored: 396 offers lack the complete six rare scoring-component bridges. No generic provider PPR label or unknown-to-zero substitution was used.

## Source and timing limits

Original comparator bytes are the authenticated pregame receipt (`de853188…db80`) and board (`1d29f934…939b`), captured 2026-10-18T10:48:59Z. Upstream publication time is unverified. Models use the unchanged registered 32-tree empirical-leaf CDF with full-support priors, fit once per target/panel on retained 2019–2025 data. The source is current revised history, using an assumed seven-day availability lag. Query features combine retained 2019–2025 history with 2026 Weeks 1–5 only; no Week 6 outcomes enter features. Zeros, DNP and unknown participation remain distinct.

**The candidate has reconstructed revised prior statistics and roster evidence while SITE is an original captured issuance. Revision/roster advantages remain possible. This comparison cannot prove contemporaneous pregame superiority.** All retained years and this week are exposed. V1 compact-history inputs remain preserved but unused; V2 was selected for source completeness before the new fits.

## Runnable artifacts and decision

Code: `nfl_lab/website_cdf.py`, `website_cdf_features_v2.py`, `website_cdf_evaluation.py`, `cdf_engine.py`. The saved original training/query inputs, 22 model/parameter/leaf manifests, pure/blend forecasts, qualified outcomes, row deltas and source correction lineage remain private. Public JSON contains source/code/model hashes, feature panels, environment/dependency versions and the model parameter schema without raw/player/training-label rows. Input/output and failure contracts are enforced by the cited code and fictional fixtures.

```sh
python -m nfl_lab.website_cdf run SEALED_REGISTRY.json NEW_SEALED_OUTPUT_DIRECTORY
python -m nfl_lab.website_cdf_export COMPLETED_RUN NEW_EXPORT_DIRECTORY --completion-sha256 SHA256
```

The runner validates the exact reviewed registry, source/code hashes and create-only output path; it freezes all model/forecast bytes before one score phase. Reusing RUN_01 is rejected. Failures consume budget. Replay requires matching private inputs/model bytes and the recorded runtime; fictional schema/scoring/replay tests establish software behavior, not NFL accuracy. Integration checks: 454 passed in 25.58 seconds; four separate fictional exporter checks passed.

Actual run: 94.80 seconds wall, 134.75 CPU seconds, peak sampled trial process-group RSS 717,336,576 bytes, about 52.15 MB private outputs. Bounds: 22 fits, two threads, 1,200 wall/1,800 CPU seconds, 2 GiB RSS, 512 MiB output, one scoring pass. Independent read-only review checked all 48 slots, 384 paired entries, 242 frozen bindings, the sole scoring phase and exact coherence arithmetic.

Actual source/evaluator/reviewer workers were requested through accepted tool arguments as `gpt-6.1-sol`, reasoning `xhigh`. Independent backend attestation and the integrator's runtime model setting are unavailable. One integrator, shared source/evaluator and a separate read-only reviewer used isolated worktrees, with at most four concurrent agents including the integrator.

No website default, model registry or scheduler is changed. Next evidence needed is genuinely later, same-cutoff original SITE/raw/candidate recording under a separately frozen confirmation contract, with eligible sparse players, complete coverage and the applicable category gates. These results do not select a panel or promote a candidate. Existing lab operations and pending confirmation are separate; frozen rec-half-adjustment-v1 and Weeks 7–14 remain unchanged.

Preserved earlier evidence: [historical CDF study](../all12-leaf-cdf-v1/README.md), [original methods scorecard](../methods-resumption-20261022/website-comparison.md). Historical gains against a pooled control are not transferred to the website comparison. Rollback: retain these immutable evidence files; revert only the opt-in lab implementation commit if needed, preserving all old outputs, experiment IDs and default settings.
