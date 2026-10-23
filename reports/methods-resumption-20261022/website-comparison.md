# Website-relative results from the retained Week 6 cohort

This is an aggregate summary of the latest fixed, indexed candidate per category.
It does not pick a new winner from every attempted model. The underlying source
is the original locally captured 2026 Week 6 website baseline; this table makes
no claim about a changed current website version. No new forecasts or outcome
scores were generated to make this summary.

Positive change means lower error: `100 × (website error − candidate error) / website error`.
Numerical rows use MAE in the target’s units. Anytime TD uses Brier score.
The percentages are error reductions, not percentages of predictions correct.
Matched counts use the fixed common-comparator cohort. Remaining offered rows
can lack a comparator or a supported outcome; they are not all missing outcomes.

| Category | Matched / offered | Website error | Candidate error | Error reduction |
|---|---:|---:|---:|---:|
| Passing yards | 27 / 37 | 56.622963 | 45.205603 | +20.16% |
| Passing TDs | 27 / 37 | 0.844444 | 0.850900 | -0.76% |
| Completions | 27 / 37 | 4.563704 | 4.417158 | +3.21% |
| Pass attempts (generic tree) | 27 / 37 | 7.145926 | 7.276708 | -1.83% |
| Interceptions thrown | 27 / 37 | 0.663704 | 0.639315 | +3.67% |
| Rushing yards (generic tree) | 95 / 137 | 16.703263 | 15.892196 | +4.86% |
| Rush attempts (generic tree) | 68 / 100 | 3.467647 | 3.885357 | -12.05% |
| Receptions (generic ridge) | 249 / 359 | 1.300321 | 1.348898 | -3.74% |
| Receiving yards | 249 / 359 | 15.614538 | 15.513290 | +0.65% |
| Rushing + receiving yards | 187 / 259 | 20.070107 | 20.020267 | +0.25% |
| Exact website offensive PPR | N/A / 396 | N/A | N/A | N/A |
| Anytime rush/receive TD probability | 249 / 288 | 0.142402 | 0.149185 | -4.76% |

Six categories have lower primary error, five have higher error, and PPR has no
qualified outcome comparison in this packet. Errors across different units and
overlapping category rows cannot be pooled into one overall gain. All eleven
accuracy comparisons span the same 13-game, one-week exposed cohort. These
results have not qualified a default replacement.

## Findings that affect the decision

- Passing yards: MAE improves 20.16%, from 56.622963 to 45.205603 yards,
  but signed bias worsens from −19.081481 to −24.072824. Original candidate
  runner/history manifests remain missing; the new reconstruction is separate.
- Completions: MAE improves 3.21%, but RMSE worsens 2.78%; bias and large
  misses worsen.
- Rushing yards: this generic tree leads website, raw and simple controls
  descriptively, but its historical bias gate and cold-context protocol deviation
  prevent qualification.
- Interceptions: the 3.67% website-relative MAE gain is only 0.16% versus raw;
  raw has better RMSE and supported zero-event errors worsen.
- Receiving and combined yards: the small website gains lose to raw Sleeper.
- Receptions: the generic ridge comparison is separate from the frozen
  `rec-half-adjustment-v1` registration and Weeks 7–14 window. No backfill,
  restart or confirmed win is implied.
- Pass attempts: the generic tree row is separate from the original workload-v1
  candidate’s mixed results, historical simple-control gain and retained failures.
- Exact PPR: 315/315 retained projection arithmetic checks passed. Those are
  component parity checks, with zero new qualified outcome scores.

Full method, coverage, tail and bias details remain in [the category index](category-status.json).
The separate [historical passing diagnostic](history-passing.json) has no archived
website comparator; its H8-versus-H3 improvement is not a website-relative gain.
