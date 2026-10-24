# Direct CPU boosters: capability v1

One authorized software invocation completed. All nine deterministic fictional
fits passed. No NFL feature, model, forecast, outcome, or score was decoded or
used. These checks establish API availability and support behavior, not predictive
gain, calibration, full distributions, or production readiness.

## Installed versions and native products

The separate environment is `/workspace/nfl-direct-boosters-venv`; the original
`/workspace/nfl-venv` remains unchanged. A plain-path `.pth` inherits its frozen
packages through the requested system-site-packages environment.

| Package | Version | Count mean | Signed median | Binary probability |
| --- | --- | --- | --- | --- |
| xgboost-cpu | 3.4.1 | `XGBRegressor(objective="count:poisson").predict` | `objective="reg:quantileerror", quantile_alpha=.5` | `XGBClassifier(objective="binary:logistic").predict_proba[:,1]` |
| lightgbm | 4.7.0 | `LGBMRegressor(objective="poisson").predict` | `objective="quantile", alpha=.5` | `LGBMClassifier(objective="binary").predict_proba[:,1]` |
| catboost | 1.2.10 | `CatBoostRegressor(loss_function="Poisson").predict(prediction_type="Exponent")` | `loss_function="Quantile:alpha=0.5"` | `CatBoostClassifier(loss_function="Logloss").predict_proba[:,1]` |

Every fit used eight trees, depth two, seed 1751, CPU execution and two threads;
the exact additional native parameters are in the manifest. Each fit consumed
its attempt before fitting, without validation selection, early stopping or
retry. Outputs had 64 finite values, nonnegative count means, probabilities in
`[0,1]`, and both signs exercised for signed medians. A Poisson training objective
does not by itself produce a calibrated Poisson forecast law.

Required absent CPU dependencies were graphviz 0.21, plotly 7.1.0 and narwhals
2.27.1. No CUDA/NCCL/GPU dependency was installed. CatBoost's standard wheel is
used explicitly with `task_type="CPU"`; this is not a claim that its binary
contains no GPU-capable code.

Inherited versions stayed numpy 2.3.5, pandas 2.2.3, scipy 1.17.0,
scikit-learn 1.8.0, joblib 1.5.3, threadpoolctl 3.6.0, matplotlib 3.10.8,
six 1.17.0 and packaging 26.3. The complete inherited/installed distribution
inventory, metadata hashes and paths are retained privately.

## Provenance and limits

The highest compatible stable, non-yanked CPU release was selected from actual
public PyPI metadata, independent of NFL performance. Each version, URL, size,
SHA256 and returned license metadata was saved before its wheel download.
Downloads retained the inherited proxy/CA, used no credentials, redirects or
automatic retries, and verified advertised bytes and hashes. Installation used
only the verified local wheels with `--no-index --no-deps` in the new environment.

There were 12 HTTP transactions, 116,631,542 wheel bytes and 2,297,857 metadata
bytes. No failure or second compatibility version was needed. The observed
supervised invocation used 73.8561 seconds wall, 134.4539 CPU seconds,
384,454,656 bytes peak sampled combined RSS and 480,031,759 bytes retained
software/environment space. RSS was sampled at 50 ms; wall accounting begins
after standard-library imports, with an independent external 240-second ceiling.
All limits were satisfied. A separate, zero-HTTP/zero-fit software metadata/report
collection used 10.8661 seconds wall and 7.6889 CPU seconds.

LightGBM's PyPI JSON license fields were null. Its verified wheel contains the
MIT license, retained with its hash. XGBoost declares Apache-2.0 and CatBoost's
advertised metadata states Apache License, Version 2.0. Actual dependency license
metadata and available wheel license records are in the manifest; missing fields
were not filled with guesses.

Metadata, wheel pins, logs, smoke receipts and license/environment inventories
are retained under the unchanged shared 512 MiB data quota. Software wheels and
the new environment use their separate 2 GiB software cap. The software allowance
does not apply to NFL data or fitted research artifacts.

## Reproducibility and next boundary

See [the exact manifest](../reports/direct-boosters-capability-v1/manifest.json)
and [execution freeze](../config/direct-boosters-capability-execution-v1.json).
The reviewed runner and independent supervisor retain the single-consumption
marker and refuse an existing environment or software namespace. They are
evidence for this completed invocation, not a command to restart it.

A real-data six-pipeline screen requires its own exact code/input/environment,
comparators, products, finite fit/resource budgets and independent review before
its first NFL fit. No screen, promotion, scheduler, default, website, hosted
activation, or old source-binding changes are included here. NGBoost and the
other requested families remain later, separately bounded experiments.
