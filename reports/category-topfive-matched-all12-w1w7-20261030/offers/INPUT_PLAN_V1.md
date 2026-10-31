# Input plan — matched twelve-category line-only panel

Status: **source preparation only; no actual offer rows decoded or scored here.**

## Annual input

Reuse the authenticated `offers_2026.parquet` normalized member. Its safe reference is in the existing `source-normalization-v3.json`; authenticate outer CAS ownership, full container SHA and inner member SHA before decoding under root's GO. Preserve the old failed source-normalization receipt and all rejected ordinals. The source covers Weeks1–5 only and has no authenticated quote clock or venue rules.

`prepare_annual_line_only` preserves all nonprice rejection reasons. Invalid/missing American odds alone no longer block a finite statistical threshold. The old `pair_and_canonicalize` is not altered or falsely claimed to run unchanged: this new line-only canonicalizer reuses its outcome-free coherence helper and explicitly retains unpriced and suspect-price diagnostics.

## Site W4–7 input and identity proof

Use full original `players[].props[]`, not `lean` or `picks` membership. Root must supply a source-only binding frame with the exact `SITE_BINDING_COLUMNS` schema. Its canonical table-JSON SHA is an explicit input binding. The frame must derive from:

1. The existing authenticated three-column GSIS/Sleeper identity registry and `source-qualified-query-identity-v1` adapter.
2. A qualified original ESPN/source-event to canonical-game schedule crosswalk, with its own full SHA.
3. Exact historical team/opponent/position and timezone-aware kickoff agreement.

The loader does not create those bindings from names. Duplicate/conflicting source identity groups abstain; original context is never rewritten. The source `late` flag is retained but does not remove retrospective lines. Every excluded prop keeps its source player/prop ordinal and rejection reason.

Recorded DK thresholds form the site primary fallback. Sleeper thresholds are separate contest evidence; site-generated thresholds do not enter. Neither source label proves a sportsbook quote, price or settlement contract. All site line clocks remain timing-unverified.

## Shared board

`combine_source_fallback` selects annual when available, then recorded DK at the same model-independent opportunity key. No candidate-specific line choice is permitted. Preserve all secondary books, alternate lines and contest thresholds in separate frames. Report coverage by source, week, category and timing/contract tier. The point and probability procedures receive the same primary lines; missing prices do not block statistical directions, while missing lines remain unavailable.

No PPR or target offer is fabricated. ATD source offers are kept as event records separate from numeric lines. The model's full population and numerical scores continue when actual offers are missing.
