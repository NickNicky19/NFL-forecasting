# Discrete threshold verification against the actual current functions

**Result:** the supported numerical paths passed. No threshold-grading defect was confirmed. This is one software suite on fictional inputs, not 26 NFL observations, new forecasts, market settlement or deployment.

Website source: `1ec93e068a91abd51c990937d1019e4a831694b4`. The retained `pull/build.py`, `pull/grade.py`, `pull/scoring.py` and `tools/weekly_adaptive_overlay.py` exactly match the current Git blobs. The current ranking source and browser functions were fetched separately; their full-file and extracted-function identities are in the [execution receipt](THRESHOLD_REAL_PATH_RESULTS_V1_2.json).

## What actually executed

The suite ran the original `player_props` and `apply_book` function bodies, the full current `weekly_selected_rankings.prepare`/`validate_item` functions with the actual overlay validator, and the actual `grade_week`/`_prop_result`/`result` bodies. It separately ran the actual browser `selectedPropGap`, `propStatus` and their dependencies in Node.

The fixtures use the original reference-point fallback. Synthetic publication hashes are fixture inputs; this does not qualify publication, new MAE admission, model restoration or a real source. Unneeded producer imports and the network-producing build entry point were not executed. No readiness guard was weakened.

| Threshold and actuals | Sides tested | Cases | Python/browser results |
|---|---|---:|---|
| Passing TDs 1.5; actual 0, 1, 2, 3 | Over and Under | 8 | Strict comparison passed; no equality at a half-integer |
| Receptions 4.5; actual 4, 5 | Over and Under | 4 | Passed |
| Completions 19.5; actual 19, 20 | Over and Under | 4 | Passed |
| Passing attempts 29.5; actual 29, 30 | Over and Under | 4 | Passed |
| Receptions 5.0; actual 5 | Over and Under | 2 | Statistical push; venue treatment remains separate |
| Signed rushing yards −1.5; actual −3, −1 | Over and Under | 4 | All-lean/browser grading passed; existing Top Pick minimum-line rule correctly excludes these fixtures |

The 26 Python cases and matching 26 browser cases concern the **same fictional inputs**. They are not 52 independent outcomes. The expected TD point **1.88 stays 1.88** through producer, side selection and grading inputs. It is neither an actual count of 2 nor an Over probability. DNP and unknown participation remain separate from a supported played zero.

## Distribution and chart checks

Six threshold-arithmetic cases used the actual `SupportPrior.cdf/logpmf` implementation with an explicitly declared fictional geometric count prior (`q=0.6`, conditional on played). No distribution was inferred from a point forecast. Over + Under + Push sums to one, threshold ordering is coherent, half-integer push mass is zero, and integer-line push mass is retained. The count-support validator rejects 1.88 as a count outcome. These are arithmetic checks, not probability-accuracy measurements.

The exact `nick-chart-ppr-v1` scorer returned **1.94** for explicitly supplied fictional integer component credits and signed yardage. Three generic numeric-grader cases passed without integer coercion. **The full chart producer/catalog/saved-pick browser path remains unadmitted.** The current browser deliberately reports a saved fantasy-points pick as unresolved when complete scoring/source evidence is unavailable. Legacy PPR was not relabeled as chart PPR.

## Execution and preserved failures

Two original harness attempts remain failed and visible: [attempt 1](FAILURE_V1.json) omitted the grader's `RESULTS` constant from its extracted-function namespace; [attempt 2](FAILURE_V1_1.json) omitted repository `PYTHONPATH` before importing the research chart scorer. Neither is a production grading defect. The original worker stays byte-identical; small versioned launchers document the correction and preserve original starts/failures.

The [separate runtime continuation](RUNTIME_CONTINUATION_V1_2.json) used one additional authorized attempt, **1.7615 CPU seconds, 1.0337 wall seconds and 129,187,840 bytes peak RSS**. It completed the complete saved suite. Original budgets and failed attempts were not reset. Source acquisition used two read-only GitHub requests; execution used zero HTTP calls, NFL fits, model inference, forecasts, captures, private-store writes or deployments.

Reproduce with the pinned current website source checkout:

```sh
PYTHONPATH=. python -B tools/category_topfive_original_threshold_runtime_v1_2.py \
  --website-root <qualified-read-only-website-checkout> \
  --report-root <fresh-copy-of-threshold-fixture-directory>
```

Copy the two public source snapshots into that fresh fixture directory first. Existing results are immutable and are not overwritten. Source mismatch fails before numerical cases execute.
