# Source-matched base benchmark: complete aggregate tables

All 2022–2024 data are exposed historical reconstruction. No independent confirmation, qualified winner, historical SITE/raw gain, website change or promotion is claimed. The CDF has lower pooled primary error than median HGB for 10/11 supported targets; combined yards is slightly adverse. All methods, comparators and adverse metrics remain. Exact PPR stays blocked in all 18 annual slots.

Numeric primary error is CDF lower-median MAE versus point heuristics/reference points. TD primary error is Brier of genuine event probabilities. CDF mean errors are separate. Aliases are identical fitted results, not independent replications.

[Full aggregate JSON](aggregate-report.json) copies the entire immutable report tree unchanged: twelve targets, 216 annual slots, annual/pooled primary/all-offered summaries, all 1144 paired contrasts and proper diagnostics. [Pooled matrix](category-status.json) retains every six-method summary, five named CDF point comparisons, full errors/bias/tails and uncertainty at full precision. [Method manifest](method-manifest.json) binds exact source/config/code/parameters. Display tables round only.

## Coverage and field semantics

| Primary population | Offered | Scored supported played |
| --- | ---: | ---: |
| QB passing |4091|1960|
| RB rushing |6235|4558|
| RB/WR/TE receiving, combined, TD |21504|15251|

Use population-specific `summaries.offered_rows` and `scored_rows`. Comparison `offered_rows=25872` and `supported_played_rows=17478` are FULL key-alignment counts before the role filter, not QB/RB/skill primary coverage. Comparison `paired_rows` is the actual filtered cohort: 1960/4558/15251 primary, 17478 all offered. Unknown participation, missing statistics, supported zeros, signed yardage and fallback coverage remain explicit; missing is not zero.

Gain%=100×(control−CDF)/control; positive is lower CDF loss. Bias=prediction−actual. Intervals are CDF−control loss in target units, not gain percentages. Whole-week/game PCG64 bootstrap uses 500 draws, seed 1703, nominal 95% linear percentiles. These exposed-sample intervals do not provide multiplicity-adjusted qualification or player significance. Proper-score gain percentages were not supplied in the frozen record; saved proper losses/deltas/intervals are shown without inventing that field.

## Authoritative resources

| Phase | State | Wall s | CPU s | Peak combined RSS bytes |
| --- | --- | ---: | ---: | ---: |
|original_benchmark|FAILED|1198.815180|1269.298613|760012800|
|first_score_recovery|FAILED|318.121865|331.776467|686161920|
|report_only_v2|COMPLETED|144.954284|151.692386|683474944|
|Sequential sum / maximum phase RSS|Two failures retained; v2 complete|1661.891330|1752.767466|760012800|

Original benchmark: FAILED at its original wall limit after 168 estimator attempts / 66 reference calls, before scoring. First-score recovery: FAILED after freezing 198 main / 33 prior scored files, on a strict anytime-TD CDF endpoint rejection. Report-only v2: COMPLETED using six canonical Bernoulli diagnostic views from exact frozen p and already scored y; four diagnostic fields only. All original probability/point/mean/brier, quantile/variance/context/state bits and raw failures remain. V2 used 0 fits/predictions/model-law calls/HTTP/source/new-label reads. No cap was silently raised/reset and neither failed version was relabeled.

## pass_yd

Unit:yards; support:signed_integer; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=4091; scored=1960; scored players=112, games=815, season-weeks=54; supported zero=110, negative=7. Outcome states:`{"played_nonzero": 1850, "played_zero": 110, "unknown": 2131}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|66.161735|66.161735|7268.887245|85.257769|-0.284184|142.100000|174.000000|355.000000|0|64|
|median_hgb|67.212323|67.212323|7319.463756|85.553865|-1.882682|139.789474|169.704503|345.592046|0|64|
|count_A|67.212323|67.212323|7319.463756|85.553865|-1.882682|139.789474|169.704503|345.592046|0|64|
|role_B|67.212323|67.212323|7319.463756|85.553865|-1.882682|139.789474|169.704503|345.592046|0|64|
|recent|75.693992|75.693992|9222.018300|96.031340|14.202061|168.687354|198.646103|302.864231|0|1537|
|pooled|73.290121|73.290121|8544.823427|92.438214|12.941048|160.861587|183.346752|289.361422|0|862|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|66.161735|67.212323|1.563089|-1.050589|1960|[-1.709982, -0.342315]|[-1.815578, -0.335580]|
|count_A|66.161735|67.212323|1.563089|-1.050589|1960|[-1.709982, -0.342315]|[-1.815578, -0.335580]|
|role_B|66.161735|67.212323|1.563089|-1.050589|1960|[-1.709982, -0.342315]|[-1.815578, -0.335580]|
|recent|66.161735|75.693992|12.593149|-9.532257|1960|[-11.698408, -7.231663]|[-11.882236, -7.402664]|
|pooled|66.161735|73.290121|9.726258|-7.128386|1960|[-9.102476, -5.032490]|[-9.222513, -5.113047]|

Separate CDF mean: MAE=67.289612; MSE=7037.116307; RMSE=83.887522; bias=4.757033; absolute-error p95=164.720087. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|46.434892|59.119016|-12.684123|1960|[-14.294296, -11.104533]|[-14.465064, -10.981511]|
|log_score|6.341148|6.093978|0.247169|1960|[0.152178, 0.347430]|[0.145509, 0.333079]|

CDF diagnostics: CRPS=46.434892; log score=6.341148; infinite log losses=0; central 80% coverage=0.853571; below-p10=0.070918; above-p90=0.075510. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=15580, negative=9. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 1898, "played_zero": 15580, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|7.463726|7.463726|816.498856|28.574444|-0.075237|12.000000|61.000000|355.000000|0|21845|
|median_hgb|7.581540|7.581540|822.170555|28.673517|-0.254495|12.501602|62.512258|345.592046|0|21845|
|count_A|7.581540|7.581540|822.170555|28.673517|-0.254495|12.501602|62.512258|345.592046|0|21845|
|role_B|7.581540|7.581540|822.170555|28.673517|-0.254495|12.501602|62.512258|345.592046|0|21845|
|recent|8.655253|8.655253|1036.297809|32.191580|1.679921|13.190571|68.954499|302.864231|0|4575|
|pooled|8.376534|8.376534|960.690992|30.995016|1.539394|13.687406|67.728019|289.361422|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|7.463726|7.581540|1.553959|-0.117814|17478|[-0.192968, -0.038475]|[-0.203188, -0.037697]|
|count_A|7.463726|7.581540|1.553959|-0.117814|17478|[-0.192968, -0.038475]|[-0.203188, -0.037697]|
|role_B|7.463726|7.581540|1.553959|-0.117814|17478|[-0.192968, -0.038475]|[-0.203188, -0.037697]|
|recent|7.463726|8.655253|13.766518|-1.191527|17478|[-1.441028, -0.939549]|[-1.472582, -0.944371]|
|pooled|7.463726|8.376534|10.897211|-0.912809|17478|[-1.137230, -0.678253]|[-1.154890, -0.680752]|

Separate CDF mean: MAE=7.590207; MSE=790.507836; RMSE=28.115971; bias=0.490089; absolute-error p95=64.902975. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|5.511159|6.933569|-1.422410|17478|[-1.620244, -1.238272]|[-1.630388, -1.212105]|
|log_score|1.717211|1.689493|0.027718|17478|[0.017072, 0.039061]|[0.016439, 0.037268]|

CDF diagnostics: CRPS=5.511159; log score=1.717211; infinite log losses=0; central 80% coverage=0.981176; below-p10=0.008010; above-p90=0.010814. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## pass_td

Unit:events; support:count; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=4091; scored=1960; scored players=112, games=815, season-weeks=54; supported zero=668, negative=0. Outcome states:`{"played_nonzero": 1292, "played_zero": 668, "unknown": 2131}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.770918|0.770918|1.193367|1.092414|-0.168878|2.000000|2.000000|5.000000|0|64|
|median_hgb|0.802692|0.802692|1.221407|1.105173|-0.194652|1.999544|2.000000|4.999976|0|64|
|count_A|0.836635|0.836635|1.075868|1.037241|0.052821|1.619248|1.933091|4.566836|0|64|
|role_B|0.836635|0.836635|1.075868|1.037241|0.052821|1.619248|1.933091|4.566836|0|64|
|recent|0.905698|0.905698|1.218714|1.103954|0.132238|1.630168|2.001251|5.001251|0|1537|
|pooled|0.885352|0.885352|1.160385|1.077212|0.119467|1.609174|1.945190|4.795834|0|862|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.770918|0.802692|3.958406|-0.031774|1960|[-0.055272, -0.010986]|[-0.052879, -0.013298]|
|count_A|0.770918|0.836635|7.854820|-0.065716|1960|[-0.084644, -0.045763]|[-0.083664, -0.048947]|
|role_B|0.770918|0.836635|7.854820|-0.065716|1960|[-0.084644, -0.045763]|[-0.083664, -0.048947]|
|recent|0.770918|0.905698|14.881319|-0.134780|1960|[-0.158789, -0.110669]|[-0.157098, -0.111509]|
|pooled|0.770918|0.885352|12.925168|-0.114433|1960|[-0.138477, -0.090984]|[-0.137582, -0.091012]|

Separate CDF mean: MAE=0.834684; MSE=1.068242; RMSE=1.033558; bias=0.063993; absolute-error p95=1.947512. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.537217|0.623075|-0.085859|1960|[-0.098339, -0.073260]|[-0.098547, -0.072582]|
|log_score|1.332312|1.501224|-0.168912|1960|[-0.189912, -0.147476]|[-0.191016, -0.146203]|

CDF diagnostics: CRPS=0.537217; log score=1.332312; infinite log losses=0; central 80% coverage=0.953061; below-p10=0.000000; above-p90=0.046939. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=16169, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 1309, "played_zero": 16169, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.087424|0.087424|0.134798|0.367149|-0.019911|0.000000|1.000000|5.000000|0|21845|
|median_hgb|0.090987|0.090987|0.137942|0.371406|-0.022801|0.000024|0.999544|4.999976|0|21845|
|count_A|0.094794|0.094794|0.121622|0.348743|0.004951|0.216066|0.770240|4.566836|0|21845|
|role_B|0.094794|0.094794|0.121622|0.348743|0.004951|0.216066|0.770240|4.566836|0|21845|
|recent|0.103907|0.103907|0.137741|0.371134|0.015227|0.174860|0.979050|5.001251|0|4575|
|pooled|0.101612|0.101612|0.131159|0.362159|0.013800|0.180958|0.950594|4.795834|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.087424|0.090987|3.916090|-0.003563|17478|[-0.006184, -0.001217]|[-0.005982, -0.001487]|
|count_A|0.087424|0.094794|7.774224|-0.007369|17478|[-0.009542, -0.005086]|[-0.009378, -0.005475]|
|role_B|0.087424|0.094794|7.774224|-0.007369|17478|[-0.009542, -0.005086]|[-0.009378, -0.005475]|
|recent|0.087424|0.103907|15.863355|-0.016483|17478|[-0.019379, -0.013785]|[-0.019191, -0.013754]|
|pooled|0.087424|0.101612|13.962895|-0.014188|17478|[-0.017054, -0.011522]|[-0.016795, -0.011408]|

Separate CDF mean: MAE=0.138871; MSE=0.122889; RMSE=0.350555; bias=0.050597; absolute-error p95=0.765839. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.063142|0.072770|-0.009628|17478|[-0.011036, -0.008235]|[-0.011108, -0.008088]|
|log_score|0.195687|0.214629|-0.018942|17478|[-0.021280, -0.016610]|[-0.021468, -0.016409]|

CDF diagnostics: CRPS=0.063142; log score=0.195687; infinite log losses=0; central 80% coverage=0.993764; below-p10=0.000000; above-p90=0.006236. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## pass_cmp

Unit:events; support:count; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=4091; scored=1960; scored players=112, games=815, season-weeks=54; supported zero=110, negative=0. Outcome states:`{"played_nonzero": 1850, "played_zero": 110, "unknown": 2131}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|5.659694|5.659694|54.222959|7.363624|-0.342347|12.000000|16.000000|28.000000|0|64|
|median_hgb|5.688640|5.688640|53.405686|7.307919|-0.191124|11.971153|14.882262|25.579972|0|64|
|count_A|5.773800|5.773800|52.341814|7.234764|-0.160619|11.782415|14.232006|27.536036|0|64|
|role_B|5.773800|5.773800|52.341814|7.234764|-0.160619|11.782415|14.232006|27.536036|0|64|
|recent|6.381988|6.381988|66.867949|8.177282|1.085329|14.471077|17.448592|23.442371|0|1537|
|pooled|6.200277|6.200277|62.052372|7.877333|0.973864|13.678688|16.041381|21.365926|0|862|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|5.659694|5.688640|0.508847|-0.028946|1960|[-0.089715, 0.033783]|[-0.087241, 0.023603]|
|count_A|5.659694|5.773800|1.976267|-0.114106|1960|[-0.201260, -0.014020]|[-0.193981, -0.027274]|
|role_B|5.659694|5.773800|1.976267|-0.114106|1960|[-0.201260, -0.014020]|[-0.193981, -0.027274]|
|recent|5.659694|6.381988|11.317692|-0.722294|1960|[-0.929484, -0.516306]|[-0.934078, -0.510454]|
|pooled|5.659694|6.200277|8.718695|-0.540583|1960|[-0.729927, -0.354022]|[-0.719955, -0.346665]|

Separate CDF mean: MAE=5.728550; MSE=51.375357; RMSE=7.167660; bias=0.174540; absolute-error p95=14.132859. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|3.954383|6.068924|-2.114540|1960|[-2.269188, -1.970051]|[-2.244131, -1.984916]|
|log_score|3.303539|3.909821|-0.606282|1960|[-0.656415, -0.559685]|[-0.649065, -0.565550]|

CDF diagnostics: CRPS=3.954383; log score=3.303539; infinite log losses=0; central 80% coverage=0.880612; below-p10=0.051020; above-p90=0.068367. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=15580, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 1898, "played_zero": 15580, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.637773|0.637773|6.084392|2.466656|-0.041481|1.000000|5.000000|28.000000|0|21845|
|median_hgb|0.641019|0.641019|5.992742|2.448008|-0.024522|1.000000|5.216872|25.579972|0|21845|
|count_A|0.650569|0.650569|5.873438|2.423518|-0.021102|1.045849|5.524455|27.536036|0|21845|
|role_B|0.650569|0.650569|5.873438|2.423518|-0.021102|1.045849|5.524455|27.536036|0|21845|
|recent|0.727424|0.727424|7.506767|2.739848|0.127910|0.998978|5.649810|23.442371|0|4575|
|pooled|0.706493|0.706493|6.969739|2.640026|0.115517|1.063756|5.626480|21.365926|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.637773|0.641019|0.506395|-0.003246|17478|[-0.010086, 0.003780]|[-0.009797, 0.002632]|
|count_A|0.637773|0.650569|1.966881|-0.012796|17478|[-0.022470, -0.001570]|[-0.021853, -0.003014]|
|role_B|0.637773|0.650569|1.966881|-0.012796|17478|[-0.022470, -0.001570]|[-0.021853, -0.003014]|
|recent|0.637773|0.727424|12.324421|-0.089651|17478|[-0.113371, -0.066965]|[-0.113976, -0.064969]|
|pooled|0.637773|0.706493|9.726849|-0.068719|17478|[-0.089679, -0.048120]|[-0.089342, -0.046821]|

Separate CDF mean: MAE=0.689673; MSE=5.766974; RMSE=2.401453; bias=0.060937; absolute-error p95=5.452593. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.448297|0.685424|-0.237127|17478|[-0.254214, -0.222777]|[-0.251513, -0.223315]|
|log_score|0.423233|0.491222|-0.067989|17478|[-0.073286, -0.063361]|[-0.072319, -0.063674]|

CDF diagnostics: CRPS=0.448297; log score=0.423233; infinite log losses=0; central 80% coverage=0.983865; below-p10=0.005721; above-p90=0.010413. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## pass_att

Unit:events; support:count; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=4091; scored=1960; scored players=112, games=815, season-weeks=54; supported zero=79, negative=0. Outcome states:`{"played_nonzero": 1881, "played_zero": 79, "unknown": 2131}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|8.257653|8.257653|120.467857|10.975785|-0.364796|19.000000|24.000000|48.000000|0|64|
|median_hgb|8.305521|8.305521|117.802618|10.853691|-0.082158|17.990418|22.521705|44.721998|0|64|
|count_A|8.440997|8.440997|116.614818|10.798834|-0.076942|17.695042|21.671884|44.438872|0|64|
|role_B|8.440997|8.440997|116.614818|10.798834|-0.076942|17.695042|21.671884|44.438872|0|64|
|recent|9.339737|9.339737|148.053635|12.167729|1.653572|21.714094|26.813922|36.174940|0|1537|
|pooled|9.064974|9.064974|138.666385|11.775669|1.479082|20.870640|24.899920|33.499956|0|862|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|8.257653|8.305521|0.576344|-0.047868|1960|[-0.146433, 0.052368]|[-0.152984, 0.036300]|
|count_A|8.257653|8.440997|2.172067|-0.183344|1960|[-0.316065, -0.034828]|[-0.315116, -0.050145]|
|role_B|8.257653|8.440997|2.172067|-0.183344|1960|[-0.316065, -0.034828]|[-0.315116, -0.050145]|
|recent|8.257653|9.339737|11.585807|-1.082084|1960|[-1.398166, -0.760426]|[-1.390172, -0.785208]|
|pooled|8.257653|9.064974|8.905934|-0.807321|1960|[-1.107550, -0.510473]|[-1.076148, -0.538403]|

Separate CDF mean: MAE=8.380001; MSE=114.206938; RMSE=10.686765; bias=0.474992; absolute-error p95=21.689003. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|5.791433|9.126381|-3.334948|1960|[-3.560412, -3.106770]|[-3.551344, -3.125980]|
|log_score|3.694316|4.336097|-0.641780|1960|[-0.695917, -0.588673]|[-0.692860, -0.591106]|

CDF diagnostics: CRPS=5.791433; log score=3.694316; infinite log losses=0; central 80% coverage=0.872449; below-p10=0.061224; above-p90=0.066327. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=15511, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 1967, "played_zero": 15511, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.931743|0.931743|13.517164|3.676570|-0.046630|1.000000|7.000000|48.000000|0|21845|
|median_hgb|0.937111|0.937111|13.218282|3.635696|-0.014935|1.396826|7.178685|44.721998|0|21845|
|count_A|0.952303|0.952303|13.085081|3.617331|-0.014350|1.391067|7.813086|44.438872|0|21845|
|role_B|0.952303|0.952303|13.085081|3.617331|-0.014350|1.391067|7.813086|44.438872|0|21845|
|recent|1.067220|1.067220|16.623446|4.077186|0.195109|1.528635|8.045576|36.174940|0|4575|
|pooled|1.035965|1.035965|15.581452|3.947335|0.175980|1.352455|7.900764|33.499956|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.931743|0.937111|0.572825|-0.005368|17478|[-0.016421, 0.005920]|[-0.017234, 0.004058]|
|count_A|0.931743|0.952303|2.159017|-0.020560|17478|[-0.035442, -0.003915]|[-0.035376, -0.005656]|
|role_B|0.931743|0.952303|2.159017|-0.020560|17478|[-0.035442, -0.003915]|[-0.035376, -0.005656]|
|recent|0.931743|1.067220|12.694413|-0.135477|17478|[-0.171084, -0.099598]|[-0.169756, -0.100799]|
|pooled|0.931743|1.035965|10.060399|-0.104222|17478|[-0.136798, -0.071115]|[-0.135234, -0.073203]|

Separate CDF mean: MAE=0.992271; MSE=12.816988; RMSE=3.580082; bias=0.094896; absolute-error p95=7.701786. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.656983|1.030968|-0.373984|17478|[-0.398990, -0.350788]|[-0.396786, -0.353523]|
|log_score|0.477180|0.549150|-0.071970|17478|[-0.077543, -0.066472]|[-0.077649, -0.066885]|

CDF diagnostics: CRPS=0.656983; log score=0.477180; infinite log losses=0; central 80% coverage=0.980776; below-p10=0.006866; above-p90=0.012358. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## pass_int

Unit:events; support:count; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=4091; scored=1960; scored players=112, games=815, season-weeks=54; supported zero=1096, negative=0. Outcome states:`{"played_nonzero": 864, "played_zero": 1096, "unknown": 2131}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.623980|0.623980|1.010714|1.005343|-0.477041|2.000000|2.000000|5.000000|0|64|
|median_hgb|0.626786|0.626786|1.080738|1.039585|-0.618116|2.000000|2.000000|5.000000|0|64|
|count_A|0.679580|0.679580|0.691930|0.831823|-0.004294|1.320013|1.506134|4.467792|0|64|
|role_B|0.679580|0.679580|0.691930|0.831823|-0.004294|1.320013|1.506134|4.467792|0|64|
|recent|0.703312|0.703312|0.734077|0.856783|0.022007|1.339080|1.508621|4.672414|0|1537|
|pooled|0.696207|0.696207|0.714000|0.844985|0.018167|1.338558|1.523768|4.440318|0|862|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.623980|0.626786|0.447682|-0.002806|1960|[-0.021355, 0.015568]|[-0.020909, 0.014089]|
|count_A|0.623980|0.679580|8.181575|-0.055600|1960|[-0.081913, -0.022719]|[-0.081527, -0.030438]|
|role_B|0.623980|0.679580|8.181575|-0.055600|1960|[-0.081913, -0.022719]|[-0.081527, -0.030438]|
|recent|0.623980|0.703312|11.279827|-0.079332|1960|[-0.107047, -0.046904]|[-0.108197, -0.053488]|
|pooled|0.623980|0.696207|10.374386|-0.072227|1960|[-0.098824, -0.039541]|[-0.100250, -0.046668]|

Separate CDF mean: MAE=0.680493; MSE=0.679066; RMSE=0.824055; bias=0.012315; absolute-error p95=1.462396. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.403393|0.412760|-0.009367|1960|[-0.013356, -0.005051]|[-0.013924, -0.005215]|
|log_score|1.053329|1.084559|-0.031230|1960|[-0.041766, -0.021499]|[-0.042227, -0.020153]|

CDF diagnostics: CRPS=0.403393; log score=1.053329; infinite log losses=0; central 80% coverage=0.951020; below-p10=0.000000; above-p90=0.048980. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=16607, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 871, "played_zero": 16607, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.070374|0.070374|0.113743|0.337258|-0.053896|0.000000|1.000000|5.000000|0|21845|
|median_hgb|0.070689|0.070689|0.121595|0.348705|-0.069717|0.000000|0.574738|5.000000|0|21845|
|count_A|0.076609|0.076609|0.077994|0.279275|-0.000882|0.267543|0.624479|4.467792|0|21845|
|role_B|0.076609|0.076609|0.077994|0.279275|-0.000882|0.267543|0.624479|4.467792|0|21845|
|recent|0.079931|0.079931|0.082754|0.287670|0.002728|0.327586|0.657326|4.672414|0|4575|
|pooled|0.079140|0.079140|0.080509|0.283740|0.002304|0.286472|0.636605|4.440318|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.070374|0.070689|0.445146|-0.000315|17478|[-0.002407, 0.001739]|[-0.002343, 0.001581]|
|count_A|0.070374|0.076609|8.138803|-0.006235|17478|[-0.009196, -0.002551]|[-0.009246, -0.003399]|
|role_B|0.070374|0.076609|8.138803|-0.006235|17478|[-0.009196, -0.002551]|[-0.009246, -0.003399]|
|recent|0.070374|0.079931|11.956328|-0.009557|17478|[-0.012691, -0.005946]|[-0.012928, -0.006624]|
|pooled|0.070374|0.079140|11.076820|-0.008766|17478|[-0.011779, -0.005121]|[-0.011980, -0.005850]|

Separate CDF mean: MAE=0.121065; MSE=0.078731; RMSE=0.280591; bias=0.045373; absolute-error p95=0.665796. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.047617|0.048668|-0.001050|17478|[-0.001508, -0.000569]|[-0.001556, -0.000587]|
|log_score|0.162659|0.166162|-0.003502|17478|[-0.004653, -0.002401]|[-0.004736, -0.002252]|

CDF diagnostics: CRPS=0.047617; log score=0.162659; infinite log losses=0; central 80% coverage=0.994107; below-p10=0.000000; above-p90=0.005893. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## rush_yd

Unit:yards; support:signed_integer; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=6235; scored=4558; scored players=225, games=815, season-weeks=54; supported zero=739, negative=82. Outcome states:`{"played_missing_statistic": 12, "played_nonzero": 3819, "played_zero": 739, "unknown": 1665}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|19.718956|19.718956|860.075691|29.327047|-6.760641|46.000000|62.000000|193.000000|0|157|
|median_hgb|33.534226|33.534226|2414.323168|49.135763|-32.981790|86.000000|106.150000|255.000000|0|157|
|count_A|33.534226|33.534226|2414.323168|49.135763|-32.981790|86.000000|106.150000|255.000000|0|157|
|role_B|19.839430|19.839430|868.347254|29.467732|-6.541290|46.927052|62.741955|191.422778|0|157|
|recent|23.611234|23.611234|939.011943|30.643302|1.079901|44.943561|60.702267|181.031418|0|803|
|pooled|22.964732|22.964732|892.596329|29.876351|1.600275|43.607307|59.673500|170.455870|0|411|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|19.718956|33.534226|41.197522|-13.815270|4558|[-14.407087, -13.266869]|[-14.342583, -13.271454]|
|count_A|19.718956|33.534226|41.197522|-13.815270|4558|[-14.407087, -13.266869]|[-14.342583, -13.271454]|
|role_B|19.718956|19.839430|0.607247|-0.120474|4558|[-0.201266, -0.035915]|[-0.210986, -0.027942]|
|recent|19.718956|23.611234|16.484858|-3.892278|4558|[-4.277409, -3.459766]|[-4.225578, -3.572945]|
|pooled|19.718956|22.964732|14.133743|-3.245776|4558|[-3.583831, -2.905823]|[-3.529561, -2.950725]|

Separate CDF mean: MAE=20.758880; MSE=815.802732; RMSE=28.562261; bias=-0.172270; absolute-error p95=58.841243. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|14.103730|19.918118|-5.814388|4558|[-6.188099, -5.448360]|[-6.139863, -5.471289]|
|log_score|4.265611|4.992802|-0.727191|4558|[-0.777367, -0.669380]|[-0.766358, -0.683592]|

CDF diagnostics: CRPS=14.103730; log score=4.265611; infinite log losses=0; central 80% coverage=0.861562; below-p10=0.050680; above-p90=0.087758. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=10893, negative=468. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 6585, "played_zero": 10893, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|7.026090|7.026090|273.452569|16.536401|-2.886257|23.000000|37.000000|193.000000|0|611|
|median_hgb|10.650239|10.650239|679.648435|26.070068|-9.669687|37.933184|64.000000|255.000000|0|611|
|count_A|10.650239|10.650239|679.648435|26.070068|-9.669687|37.933184|64.000000|255.000000|0|611|
|role_B|7.077939|7.077939|275.758666|16.605983|-2.695101|23.000000|36.853479|191.422778|0|611|
|recent|8.602295|8.602295|294.971494|17.174734|0.254133|25.392631|34.891742|181.031418|0|4575|
|pooled|8.369191|8.369191|280.070752|16.735315|0.429270|24.862707|34.259728|170.455870|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|7.026090|10.650239|34.028804|-3.624149|17478|[-3.770256, -3.490932]|[-3.755925, -3.483563]|
|count_A|7.026090|10.650239|34.028804|-3.624149|17478|[-3.770256, -3.490932]|[-3.755925, -3.483563]|
|role_B|7.026090|7.077939|0.732543|-0.051849|17478|[-0.083548, -0.020128]|[-0.086031, -0.021944]|
|recent|7.026090|8.602295|18.323072|-1.576205|17478|[-1.679819, -1.462289]|[-1.672692, -1.475859]|
|pooled|7.026090|8.369191|16.048162|-1.343101|17478|[-1.434961, -1.244288]|[-1.430840, -1.251324]|

Separate CDF mean: MAE=7.642722; MSE=257.065889; RMSE=16.033274; bias=-0.141143; absolute-error p95=35.120435. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|5.128620|7.198880|-2.070260|17478|[-2.188355, -1.956968]|[-2.172864, -1.962008]|
|log_score|1.978879|2.918722|-0.939843|17478|[-0.966531, -0.913226]|[-0.964878, -0.917451]|

CDF diagnostics: CRPS=5.128620; log score=1.978879; infinite log losses=0; central 80% coverage=0.903536; below-p10=0.028951; above-p90=0.067513. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## rush_att

Unit:events; support:count; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=6235; scored=4558; scored players=225, games=815, season-weeks=54; supported zero=682, negative=0. Outcome states:`{"played_missing_statistic": 12, "played_nonzero": 3876, "played_zero": 682, "unknown": 1665}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|3.544976|3.544976|24.609478|4.960794|-0.872751|8.000000|11.000000|26.000000|0|157|
|median_hgb|7.748355|7.748355|108.991005|10.439876|-7.659719|18.000000|21.000000|37.000000|0|157|
|count_A|3.711640|3.711640|24.024642|4.901494|0.098769|8.057272|10.090216|24.903273|0|157|
|role_B|3.709749|3.709749|24.036670|4.902721|0.160095|8.048519|10.175436|24.722512|0|157|
|recent|4.489937|4.489937|30.695706|5.540371|0.226700|8.216244|10.798105|26.661280|0|803|
|pooled|4.298479|4.298479|28.543647|5.342626|0.312547|8.055147|10.323902|26.970215|0|411|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|3.544976|7.748355|54.248662|-4.203379|4558|[-4.306473, -4.091129]|[-4.318730, -4.090134]|
|count_A|3.544976|3.711640|4.490304|-0.166664|4558|[-0.204773, -0.128848]|[-0.199370, -0.136051]|
|role_B|3.544976|3.709749|4.441632|-0.164773|4558|[-0.201828, -0.128629]|[-0.197891, -0.133119]|
|recent|3.544976|4.489937|21.046197|-0.944961|4558|[-1.033152, -0.847526]|[-1.012314, -0.865400]|
|pooled|3.544976|4.298479|17.529538|-0.753504|4558|[-0.827821, -0.680245]|[-0.817319, -0.685033]|

Separate CDF mean: MAE=3.779546; MSE=24.292747; RMSE=4.928767; bias=0.109633; absolute-error p95=9.995893. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|2.544588|3.905821|-1.361234|4558|[-1.421794, -1.290080]|[-1.421690, -1.289005]|
|log_score|2.701405|3.109369|-0.407964|4558|[-0.428653, -0.382836]|[-0.426951, -0.385948]|

CDF diagnostics: CRPS=2.544588; log score=2.701405; infinite log losses=0; central 80% coverage=0.888986; below-p10=0.035323; above-p90=0.075691. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=10702, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 6776, "played_zero": 10702, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|1.221879|1.221879|7.303811|2.702556|-0.366289|4.000000|6.000000|26.000000|0|611|
|median_hgb|2.517851|2.517851|31.154766|5.581645|-2.494622|9.000000|14.000000|37.000000|0|611|
|count_A|1.316462|1.316462|7.094672|2.663583|0.031504|4.058793|6.149200|24.903273|0|611|
|role_B|1.307807|1.307807|7.092304|2.663138|0.034671|4.120465|6.142000|24.722512|0|611|
|recent|1.544155|1.544155|8.955477|2.992570|0.052086|4.869033|6.731774|26.661280|0|4575|
|pooled|1.483270|1.483270|8.322166|2.884817|0.080018|4.731774|6.488074|26.970215|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|1.221879|2.517851|51.471357|-1.295972|17478|[-1.319895, -1.266197]|[-1.324986, -1.264591]|
|count_A|1.221879|1.316462|7.184608|-0.094583|17478|[-0.104778, -0.083949]|[-0.103792, -0.086209]|
|role_B|1.221879|1.307807|6.570404|-0.085928|17478|[-0.096420, -0.074897]|[-0.096260, -0.076342]|
|recent|1.221879|1.544155|20.870694|-0.322276|17478|[-0.345349, -0.296750]|[-0.343464, -0.299347]|
|pooled|1.221879|1.483270|17.622649|-0.261392|17478|[-0.282816, -0.240730]|[-0.279590, -0.242189]|

Separate CDF mean: MAE=1.331616; MSE=7.147073; RMSE=2.673401; bias=0.027035; absolute-error p95=6.159687. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.881701|1.297970|-0.416269|17478|[-0.434656, -0.393725]|[-0.433734, -0.397421]|
|log_score|1.167989|1.367262|-0.199273|17478|[-0.210027, -0.188306]|[-0.211136, -0.188761]|

CDF diagnostics: CRPS=0.881701; log score=1.167989; infinite log losses=0; central 80% coverage=0.936148; below-p10=0.010985; above-p90=0.052866. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## rec

Unit:events; support:count; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=21504; scored=15251; scored players=752, games=815, season-weeks=54; supported zero=3786, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 11465, "played_zero": 3786, "unknown": 6229}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|1.281359|1.281359|3.441217|1.855052|-0.336634|3.000000|4.000000|13.000000|0|545|
|median_hgb|1.313432|1.313432|3.449934|1.857400|-0.313524|2.999948|3.998504|13.005653|0|545|
|count_A|1.343527|1.343527|3.243919|1.801088|0.005482|2.836283|3.709394|13.000000|0|545|
|role_B|1.351850|1.351850|3.309283|1.819144|-0.004705|2.864845|3.756315|13.490200|0|545|
|recent|1.516684|1.516684|3.808877|1.951634|0.112601|2.856152|3.786540|13.429272|0|3023|
|pooled|1.463300|1.463300|3.556550|1.885882|0.120029|2.821874|3.653970|12.227645|0|1571|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|1.281359|1.313432|2.441946|-0.032073|15251|[-0.038272, -0.026556]|[-0.038051, -0.025794]|
|count_A|1.281359|1.343527|4.627273|-0.062169|15251|[-0.070543, -0.053834]|[-0.068973, -0.055479]|
|role_B|1.281359|1.351850|5.214443|-0.070491|15251|[-0.079813, -0.062188]|[-0.078343, -0.061990]|
|recent|1.281359|1.516684|15.515795|-0.235326|15251|[-0.248173, -0.221084]|[-0.246448, -0.222871]|
|pooled|1.281359|1.463300|12.433640|-0.181941|15251|[-0.195026, -0.169566]|[-0.191907, -0.170047]|

Separate CDF mean: MAE=1.361985; MSE=3.268201; RMSE=1.807817; bias=0.053270; absolute-error p95=3.672779. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.911299|1.193559|-0.282260|15251|[-0.296845, -0.267772]|[-0.293351, -0.270927]|
|log_score|1.755107|2.001445|-0.246338|15251|[-0.258233, -0.234367]|[-0.254784, -0.237841]|

CDF diagnostics: CRPS=0.911299; log score=1.755107; infinite log losses=0; central 80% coverage=0.923677; below-p10=0.015015; above-p90=0.061307. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=5869, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 11609, "played_zero": 5869, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|1.130049|1.130049|3.020311|1.737904|-0.298490|3.000000|4.000000|13.000000|0|611|
|median_hgb|1.158593|1.158593|3.026287|1.739623|-0.274831|2.973425|3.896855|13.005653|0|611|
|count_A|1.187011|1.187011|2.845713|1.686924|0.006293|2.688840|3.528762|13.000000|0|611|
|role_B|1.193909|1.193909|2.904218|1.704177|-0.002892|2.714214|3.606949|13.490200|0|611|
|recent|1.337439|1.337439|3.339100|1.827321|0.098211|2.775893|3.622871|13.429272|0|4575|
|pooled|1.290536|1.290536|3.118386|1.765895|0.104720|2.695584|3.464662|12.227645|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|1.130049|1.158593|2.463659|-0.028544|17478|[-0.034159, -0.023590]|[-0.033741, -0.022831]|
|count_A|1.130049|1.187011|4.798741|-0.056962|17478|[-0.064271, -0.049863]|[-0.063008, -0.051055]|
|role_B|1.130049|1.193909|5.348825|-0.063860|17478|[-0.072129, -0.056216]|[-0.070838, -0.056067]|
|recent|1.130049|1.337439|15.506455|-0.207389|17478|[-0.218498, -0.194865]|[-0.217311, -0.196444]|
|pooled|1.130049|1.290536|12.435681|-0.160487|17478|[-0.171499, -0.149884]|[-0.169405, -0.149831]|

Separate CDF mean: MAE=1.202924; MSE=2.867421; RMSE=1.693346; bias=0.049308; absolute-error p95=3.501678. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.803474|1.050278|-0.246804|17478|[-0.259688, -0.233770]|[-0.256465, -0.236558]|
|log_score|1.555497|1.773452|-0.217956|17478|[-0.229021, -0.206953]|[-0.225509, -0.210008]|

CDF diagnostics: CRPS=0.803474; log score=1.555497; infinite log losses=0; central 80% coverage=0.931972; below-p10=0.013102; above-p90=0.054926. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## rec_yd

Unit:yards; support:signed_integer; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=21504; scored=15251; scored players=752, games=815, season-weeks=54; supported zero=3884, negative=175. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 11367, "played_zero": 3884, "unknown": 6229}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|16.372435|16.372435|631.854567|25.136718|-5.756213|40.000000|54.000000|211.000000|0|545|
|median_hgb|16.408038|16.408038|633.778497|25.174958|-5.679058|39.757079|54.271026|212.736684|0|545|
|count_A|16.408038|16.408038|633.778497|25.174958|-5.679058|39.757079|54.271026|212.736684|0|545|
|role_B|16.401693|16.401693|626.201430|25.024017|-5.165740|39.402298|53.953291|210.095098|0|545|
|recent|19.403504|19.403504|687.904222|26.227928|1.527135|38.133245|52.973742|226.021935|0|3023|
|pooled|18.730916|18.730916|641.307681|25.324053|1.584992|37.222255|50.332014|212.145078|0|1571|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|16.372435|16.408038|0.216987|-0.035603|15251|[-0.069991, -0.001896]|[-0.074325, 0.005283]|
|count_A|16.372435|16.408038|0.216987|-0.035603|15251|[-0.069991, -0.001896]|[-0.074325, 0.005283]|
|role_B|16.372435|16.401693|0.178386|-0.029258|15251|[-0.060887, 0.006109]|[-0.068857, 0.003966]|
|recent|16.372435|19.403504|15.621249|-3.031070|15251|[-3.183343, -2.845080]|[-3.181435, -2.872603]|
|pooled|16.372435|18.730916|12.591384|-2.358482|15251|[-2.490466, -2.214650]|[-2.494227, -2.221665]|

Separate CDF mean: MAE=17.403218; MSE=598.598775; RMSE=24.466278; bias=0.251925; absolute-error p95=50.504618. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|11.672987|15.172788|-3.499801|15251|[-3.679157, -3.306836]|[-3.658977, -3.335858]|
|log_score|3.790373|4.654354|-0.863981|15251|[-0.892918, -0.828156]|[-0.887721, -0.839578]|

CDF diagnostics: CRPS=11.672987; log score=3.790373; infinite log losses=0; central 80% coverage=0.882958; below-p10=0.031342; above-p90=0.085699. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=5966, negative=189. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 11512, "played_zero": 5966, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|14.384598|14.384598|553.238014|23.521012|-5.081703|37.000000|51.000000|211.000000|0|611|
|median_hgb|14.420610|14.420610|554.794977|23.554086|-4.987574|37.044174|51.229076|212.736684|0|611|
|count_A|14.420610|14.420610|554.794977|23.554086|-4.987574|37.044174|51.229076|212.736684|0|611|
|role_B|14.411101|14.411101|548.613439|23.422499|-4.593189|36.964893|51.109421|210.095098|0|611|
|recent|17.054871|17.054871|601.991928|24.535524|1.335774|35.914462|49.699295|226.021935|0|4575|
|pooled|16.462942|16.462942|561.233375|23.690365|1.386166|35.622798|47.343658|212.145078|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|14.384598|14.420610|0.249725|-0.036012|17478|[-0.068857, -0.007216]|[-0.069856, 0.001103]|
|count_A|14.384598|14.420610|0.249725|-0.036012|17478|[-0.068857, -0.007216]|[-0.069856, 0.001103]|
|role_B|14.384598|14.411101|0.183908|-0.026503|17478|[-0.053161, 0.006926]|[-0.060098, 0.002413]|
|recent|14.384598|17.054871|15.656954|-2.670273|17478|[-2.797574, -2.509808]|[-2.805774, -2.531101]|
|pooled|14.384598|16.462942|12.624377|-2.078344|17478|[-2.192077, -1.953323]|[-2.195186, -1.954569]|

Separate CDF mean: MAE=15.311218; MSE=524.010439; RMSE=22.891274; bias=0.241132; absolute-error p95=48.111939. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|10.260043|13.363853|-3.103810|17478|[-3.257932, -2.933694]|[-3.241231, -2.962432]|
|log_score|3.357969|4.241880|-0.883911|17478|[-0.909357, -0.852516]|[-0.905637, -0.863155]|

CDF diagnostics: CRPS=10.260043; log score=3.357969; infinite log losses=0; central 80% coverage=0.895354; below-p10=0.028150; above-p90=0.076496. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## rush_rec_yd

Unit:yards; support:signed_integer; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=21504; scored=15251; scored players=752, games=815, season-weeks=54; supported zero=2519, negative=157. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 12732, "played_zero": 2519, "unknown": 6229}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|21.025703|21.025703|923.310144|30.386019|-6.415383|49.000000|64.000000|216.000000|0|545|
|median_hgb|21.019873|21.019873|922.637259|30.374945|-6.036182|48.428289|64.282872|224.284904|0|545|
|count_A|21.019873|21.019873|922.637259|30.374945|-6.036182|48.428289|64.282872|224.284904|0|545|
|role_B|21.023832|21.023832|918.149040|30.300974|-5.863786|48.602063|64.219009|211.637318|0|545|
|recent|24.858443|24.858443|1030.631684|32.103453|1.871526|46.917099|62.320432|238.525816|0|3023|
|pooled|23.979368|23.979368|963.627612|31.042352|2.112045|45.935861|60.718728|212.148063|0|1571|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|21.025703|21.019873|-0.027737|0.005830|15251|[-0.056165, 0.060183]|[-0.050211, 0.061624]|
|count_A|21.025703|21.019873|-0.027737|0.005830|15251|[-0.056165, 0.060183]|[-0.050211, 0.061624]|
|role_B|21.025703|21.023832|-0.008900|0.001871|15251|[-0.056224, 0.057267]|[-0.054706, 0.051171]|
|recent|21.025703|24.858443|15.418260|-3.832739|15251|[-4.037486, -3.591441]|[-4.037125, -3.610120]|
|pooled|21.025703|23.979368|12.317525|-2.953665|15251|[-3.118924, -2.764790]|[-3.119256, -2.767110]|

Separate CDF mean: MAE=22.113671; MSE=884.074688; RMSE=29.733393; bias=0.398512; absolute-error p95=59.929591. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|14.946435|20.054270|-5.107835|15251|[-5.343148, -4.849660]|[-5.291180, -4.901524]|
|log_score|4.278519|4.992181|-0.713662|15251|[-0.744949, -0.678752]|[-0.738310, -0.687848]|

CDF diagnostics: CRPS=14.946435; log score=4.278519; infinite log losses=0; central 80% coverage=0.877582; below-p10=0.040588; above-p90=0.081831. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=2925, negative=392. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 14553, "played_zero": 2925, "unknown": 8370}`.

|Method|Primary MAE|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|19.743792|19.743792|844.875615|29.066744|-6.309418|46.000000|62.000000|216.000000|0|611|
|median_hgb|19.739697|19.739697|842.416679|29.024415|-5.787784|46.325547|61.517232|224.284904|0|611|
|count_A|19.739697|19.739697|842.416679|29.024415|-5.787784|46.325547|61.517232|224.284904|0|611|
|role_B|19.731813|19.731813|837.687303|28.942828|-5.612335|46.406973|61.615829|211.637318|0|611|
|recent|23.289355|23.289355|938.643217|30.637285|1.589907|45.612490|59.780228|238.525816|0|4575|
|pooled|22.468695|22.468695|877.968436|29.630532|1.815436|43.935861|57.672739|212.148063|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|19.743792|19.739697|-0.020744|0.004095|17478|[-0.057548, 0.054178]|[-0.048495, 0.055414]|
|count_A|19.743792|19.739697|-0.020744|0.004095|17478|[-0.057548, 0.054178]|[-0.048495, 0.055414]|
|role_B|19.743792|19.731813|-0.060708|0.011979|17478|[-0.039192, 0.063532]|[-0.045052, 0.060683]|
|recent|19.743792|23.289355|15.223963|-3.545563|17478|[-3.731206, -3.331920]|[-3.720323, -3.355367]|
|pooled|19.743792|22.468695|12.127553|-2.724903|17478|[-2.871602, -2.541903]|[-2.873482, -2.559974]|

Separate CDF mean: MAE=20.807018; MSE=806.877684; RMSE=28.405592; bias=0.375330; absolute-error p95=58.040456. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|14.054173|18.842795|-4.788623|17478|[-5.002992, -4.551573]|[-4.965032, -4.594355]|
|log_score|4.204407|4.900782|-0.696376|17478|[-0.723794, -0.663752]|[-0.720349, -0.674112]|

CDF diagnostics: CRPS=14.054173; log score=4.204407; infinite log losses=0; central 80% coverage=0.871896; below-p10=0.044856; above-p90=0.083248. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

## fantasy_ppr

Unit:fantasy points; support:fractional_ppr; state:BLOCKED_EXACT_PPR.

All six methods × three years are `BLOCKED_EXACT_PPR`; no error, mean, comparison or winner.

|Method|State|
|---|---|
|leaf_cdf|BLOCKED_EXACT_PPR|
|median_hgb|BLOCKED_EXACT_PPR|
|count_A|BLOCKED_EXACT_PPR|
|role_B|BLOCKED_EXACT_PPR|
|recent|BLOCKED_EXACT_PPR|
|pooled|BLOCKED_EXACT_PPR|

## anytime_td

Unit:probability; support:bernoulli; state:EXPOSED_DEVELOPMENT_DIAGNOSTIC.

### primary_roles

Offered=21504; scored=15251; scored players=752, games=815, season-weeks=54; supported zero=12339, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 2912, "played_zero": 12339, "unknown": 6229}`.

|Method|Primary Brier|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.140969|0.291583|0.140969|0.375459|0.012781|0.736045|0.817405|0.976274|0|545|
|median_hgb|0.141177|0.288220|0.141177|0.375735|0.009573|0.739126|0.821397|0.971430|0|545|
|count_A|0.141177|0.288220|0.141177|0.375735|0.009573|0.739126|0.821397|0.971430|0|545|
|role_B|0.141565|0.287808|0.141565|0.376252|0.009581|0.733545|0.827194|0.982622|0|545|
|recent|0.151567|0.298931|0.151567|0.389317|0.014004|0.739381|0.878983|0.918412|0|3023|
|pooled|0.146460|0.296168|0.146460|0.382701|0.013764|0.753064|0.846165|0.937240|0|1571|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.140969|0.141177|0.147074|-0.000208|15251|[-0.000630, 0.000194]|[-0.000636, 0.000169]|
|count_A|0.140969|0.141177|0.147074|-0.000208|15251|[-0.000630, 0.000194]|[-0.000636, 0.000169]|
|role_B|0.140969|0.141565|0.421057|-0.000596|15251|[-0.001086, -0.000160]|[-0.001085, -0.000076]|
|recent|0.140969|0.151567|6.992385|-0.010598|15251|[-0.011781, -0.009470]|[-0.011968, -0.009262]|
|pooled|0.140969|0.146460|3.748973|-0.005491|15251|[-0.006340, -0.004567]|[-0.006458, -0.004501]|

Separate CDF mean: MAE=0.291583; MSE=0.140969; RMSE=0.375459; bias=0.012781; absolute-error p95=0.817405. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.140969|0.153607|-0.012637|15251|[-0.014061, -0.011230]|[-0.014012, -0.011358]|
|log_score|0.445680|0.484773|-0.039094|15251|[-0.043029, -0.034685]|[-0.042968, -0.035378]|

CDF diagnostics: CRPS=0.140969; log score=0.445680; infinite log losses=0; central 80% coverage=0.993181; below-p10=0.000000; above-p90=0.006819. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

Binary probabilities are not clipped. Contrary 0/1 log losses retain explicit infinity/counts; reliability deciles and all-method log-loss states remain in JSON.

### all_offered

Offered=25872; scored=17478; scored players=875, games=815, season-weeks=54; supported zero=14267, negative=0. Outcome states:`{"played_missing_statistic": 24, "played_nonzero": 3211, "played_zero": 14267, "unknown": 8370}`.

|Method|Primary Brier|MAE|MSE|RMSE|Bias|Abs p90|Abs p95|Abs max|Missing points|Fallback rows|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|leaf_cdf|0.137774|0.283672|0.137774|0.371180|0.010783|0.744264|0.843118|0.976274|0|4913|
|median_hgb|0.137956|0.280739|0.137956|0.371424|0.007984|0.748628|0.843179|0.971430|0|4913|
|count_A|0.137956|0.280739|0.137956|0.371424|0.007984|0.748628|0.843179|0.971430|0|4913|
|role_B|0.138295|0.280379|0.138295|0.371880|0.007991|0.744657|0.852457|0.982622|0|4913|
|recent|0.146506|0.288498|0.146506|0.382762|0.012204|0.739381|0.878983|0.966292|0|4575|
|pooled|0.142013|0.286266|0.142013|0.376846|0.011972|0.753064|0.848819|0.971574|0|2435|

|CDF comparator|CDF loss|Control loss|Gain%|CDF−control|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---:|---|---|
|median_hgb|0.137774|0.137956|0.131331|-0.000181|17478|[-0.000551, 0.000169]|[-0.000555, 0.000148]|
|count_A|0.137774|0.137956|0.131331|-0.000181|17478|[-0.000551, 0.000169]|[-0.000555, 0.000148]|
|role_B|0.137774|0.138295|0.376097|-0.000520|17478|[-0.000947, -0.000140]|[-0.000947, -0.000066]|
|recent|0.137774|0.146506|5.960130|-0.008732|17478|[-0.009848, -0.007584]|[-0.009992, -0.007470]|
|pooled|0.137774|0.142013|2.984364|-0.004238|17478|[-0.005114, -0.003199]|[-0.005183, -0.003259]|

Separate CDF mean: MAE=0.283672; MSE=0.137774; RMSE=0.371180; bias=0.010783; absolute-error p95=0.843118. Numeric primary remains the lower median.

|Proper CDF vs role prior|CDF loss|Prior loss|CDF−prior|Paired rows|Week 95% delta|Game 95% delta|
|---|---:|---:|---:|---:|---|---|
|crps|0.137774|0.148801|-0.011027|17478|[-0.012270, -0.009783]|[-0.012233, -0.009910]|
|log_score|0.438946|0.473058|-0.034113|17478|[-0.037576, -0.030272]|[-0.037489, -0.030849]|

CDF diagnostics: CRPS=0.137774; log score=0.438946; infinite log losses=0; central 80% coverage=0.992791; below-p10=0.000000; above-p90=0.007209. Full PIT/brackets/reliability/atom masses remain in JSON. Valid law does not establish calibration; selected-line/push evaluation is unavailable without recorded offers.

Binary probabilities are not clipped. Contrary 0/1 log losses retain explicit infinity/counts; reliability deciles and all-method log-loss states remain in JSON.

## Adverse results, aliases and limits

Combined-yard primary CDF MAE=21.025703, HGB=21.019873; gain=-0.027737% (adverse). The count_A alias repeats that result; role_B also narrowly beats CDF. No winner is selected.

Rare interceptions: CDF lower-median MAE=0.623980 vs HGB=0.626786, but median RMSE=1.005343, bias=-0.477041. The distinct CDF mean has MAE=0.680493, RMSE=0.824055, bias=0.012315. A median-MAE gain does not imply a better RMSE/bias; all metrics remain visible.

Noncount count_A aliases the NEW same-source median-HGB output; singleton passing role_B aliases same-source count_A. Equal numbers are not independent replications. Base-only source-matched methods are the primary comparison here; older source-dependent results are not recycled controls.

Source limitations remain: current-vintage reconstruction, assumed seven-day historical availability, positive-action-only participation and an incomplete appearance denominator. Historical SITE/raw forecasts and authenticated pregame injury/news panels are unavailable; no prospective confirmation is added. All weights, training bindings, empirical supports, source/feature/query/player/game rows, forecasts/outcomes and private paired losses stay private. Hash identities do not release their bytes. Supplemental player/team/opponent aggregation is separately registered and supplies no new predictive evidence.
