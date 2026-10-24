# Explicit-zero audit: completed, no new support

The first numerical source audit completed under executor V3 and unchanged
numeric core/config V2. It retained all **67 raw records**, **97 identified
union members × 12 targets = 1,164 opportunity records**, and twelve separate
unidentified-record opportunities. There were **zero new support candidates
for every target**. No labels were applied and no forecasts or scores changed.

| Original primary population | Offered opportunities | Already supported zeros | New support |
| --- | ---: | ---: | ---: |
| pass_yd / pass_td / pass_cmp / pass_att, each | 4 | 0 | 0 |
| pass_int | 4 | 1 | 0 |
| rush_yd / rush_att, each, RB only | 7 | 1 | 0 |
| rec / rec_yd, each | 27 | 5 | 0 |
| rush_rec_yd | 27 | 3 | 0 |
| anytime_td | 27 | 14 | 0 |
| Exact website PPR | 27 | Blocked | 0 |

These category opportunities overlap; they are not new independent games or
additional supported players. The original 31 offered players and all 92 FTN
positive witnesses remain. Eleven offered players lack an identified raw record;
five lack both raw match and witness. Missing rows/statistics remain unknown.
FTN absence establishes no DNP; explicit zeros already supported by other
physical activity do not become new labels merely because FTN also sees them.

The [full aggregate](aggregate.json) preserves outside-population, unoffered,
unknown and orphan coverage for all twelve targets. Reason flags overlap.
Its nested `coverage` object is copied from the structural predecessor: the
predecessor field mentioning zero primitive reads is **not** the current audit's
read count. The current audit projected all 19 registered columns, including
eleven statistics; it applied zero labels. Do not rewrite the original aggregate.

## Execution and acceptance

The [actual execution](actual-execution.json) succeeded in both sequential
phases. Before its own supervisor receipt write: 27.549684 wall seconds,
28.343463 CPU seconds, 187,633,664 bytes sampled combined peak RSS. The tool's
after-receipt observation was 32.179284 wall and 32.963463 CPU seconds.
Sampling can miss transients. The original 60-second wall/CPU, 256 MiB combined
RSS with 240 MiB sampled stop, one-thread and 1 MiB output limits were retained.

[Independent acceptance](actual-review.json) checked saved aggregate/manifest
arithmetic, hashes, owned aliases and receipts only. It did not requery source
rows or independently reproduce primitive-stat arithmetic. Its metadata marker
parsing error and correction are retained. No tests or source audit were rerun.

The [V2 execution failure](../raw-orphan-zero-audit-v2/failed-run/JOB_FINISHED.json)
occurred before any source query. Its exact cause remains unknown. V3 used the
previously accepted known-child terminal-state sampler and safe diagnostics;
success does not establish that the earlier cause was reproduced or proved.

This result closes this narrow explicit-zero audit. It establishes neither a
complete participant census, new historical availability, exact PPR labels nor
forecast improvement. A qualified alternative such as complete event-credit
aggregation requires its own source/crediting contract. Independent modeling
and reporting work continues.
