# Annual source helper: prepared, not executed

`nfl_lab/dynamic_opportunity_source_helpers.py` is a separate new file outside
the nine bindings of the accepted twelve-contract software packet. It has only
been syntax-parsed, not imported, tested or run on NFL values. Original tested
source/study/core/fixtures/harness/policy bytes remain unchanged. The concrete
backend and CLI are the runtime owner's separate files; there is one loader,
storage, evaluator and orchestration route.

## Concrete API

`AnnualInputs(projection, calendar, plan, replay_policy)` uses the authenticated
`ProjectionSource`; it opens no files and performs no independent acquisition.

- `prepare(year, query_rows, query_reference, prior_kinds)` forms task/role priors
  at that year's earliest original cutoff from earlier seasons only, then caches
  both task requests at each monotonically advancing same-cutoff batch.
- The return has `priors[task][role]` as typed core Prior,
  `simple_role_means[task][role]`, fixed `efficiency_priors[role]` where declared,
  and source/support/invalid-prior audits. Invalid global priors admit no numeric
  sufficient observations and require fallback; no raw outcome is changed.
- `requests_for_year(year, task)` preserves all original query order/ordinals.
  Offers are generated once over the full annual context before grouping.
- `efficiency_for_request(year, request)` caches the same fixed catch/YPT
  conversion for dynamic and static target propagation. It uses only the exact
  selected slots, qualified playing and explicit equal raw/normalized fields.
  Signed and zero-target lateral yards remain legal. Unknowns supply no update.
- `factored_requests(year, task)` returns flat `records`, separate reusable
  `tables` (offer/spell/query-reference/history-slot/core-query/proxy/slot-audit/
  request-tail), and small replay manifests. Table references are integers,
  avoiding repeated hash-heavy per-slot JSON. The backend can persist tables
  using the original managed Parquet writer and bind their exact hashes.
- `restore_factored_requests(packet)` is the pure lossless codec inverse; it
  reconstructs original requests, static digests and every missing/fallback
  state without source reads or new forecasts. Its consumer acceptance is part
  of the pending combined backend packet, not the earlier twelve checks.
- `release_requests(year)` releases only memory after the backend has frozen
  all same-year packages. It never deletes retained source/evidence bytes.

Only individual membership/history lookups use player indices, retaining every
team/status conflict for each requested player. Raw proxy rows remain **all
positions/all players**, including orphan IDs. No individual-player filter can
alter the recorded denominator. Both tasks are prepared while the source moves
forward once; a second task never rewinds the source clock.

For 2020/2021 development, the concrete backend must freeze both annual forecast
sets before accessing selection-role outcomes. Complete 2021 outcomes may be
admitted at the earliest 2022 query cutoff before selection; this admits no
2022 statistics under strict seven-day availability. Final outcome scoring
still requires the global 2022–2024 forecast freeze. A derived development-year
context needs its own persisted query reference/ordinal binding, not a filtered
ordinal mislabeled as an original full-file row.

The root's 48 MiB/shared512 MiB actual proposal, 54 packages, 600k forecast rows,
600 wall/CPU seconds, exact prior-vector and phase limits remain pending combined
backend/source/environment review and GO. No actual fits, NFL values, models,
tests, HTTP, CAS or source-policy activation occurred for this helper.
