# Independent anytime-TD calibration acceptance

PASS:168946 checks, zero mismatches. All16saved calibrators,33summaries and144fixed contrasts verified without refitting. All288interval slots checked:276finite intervals (138000replicates) and12explicit undefined slots from genuine infinite loss.

Pooled2023–2024:10157supported binary outcomes among14282offered rows;4101unknown participation and24played-missing labels remain. Both bases retain366offered fallback rows. Zero calibration fallback does not imply improved calibration.

| Base | Method | Brier | Delta vs own base | Infinite log losses |
|---|---|---:|---:|---:|
| fresh_cdf | intercept | 0.141437085 | +0.000416072 | 0 |
| fresh_cdf | platt | 0.141134319 | +0.000113306 | 0 |
| fresh_cdf | beta | 0.141152159 | +0.000131146 | 0 |
| fresh_cdf | isotonic | 0.141426164 | +0.000405151 | 2 |
| catboost_medium | intercept | 0.141094170 | +0.000273425 | 0 |
| catboost_medium | platt | 0.141028145 | +0.000207399 | 0 |
| catboost_medium | beta | 0.141026949 | +0.000206203 | 0 |
| catboost_medium | isotonic | 0.141168936 | +0.000348191 | 0 |

Unchanged bases: freshCDF Brier0.141021013; CatBoostmedium0.140820746. Every calibrated pooled Brier is worse than both bases. FreshCDF Platt/beta2023gains reverse2024. FreshCDFisotonic retains two infinite log losses; no clipping or row deletion. FreshCDFintercept/isotonic pooled harm intervals are abovezero for both unadjusted clusterings. The upper extreme tail has no supported forecasts≥.9.

The independent single review used14.476868699CPU seconds,10.181319968wall seconds and195870720bytes conservative combined RSS; all owned processes reaped. No fits, base-model loads, acquisition, HTTP, new football sample or production change. Saved logistic projected-gradient maximum6.0163e-8 and isotonic KKT residual maximum1.2418e-13 passed.

This is exposed historical evidence. Fixed-procedure intervals do not establish a selected winner or scientific qualification.
