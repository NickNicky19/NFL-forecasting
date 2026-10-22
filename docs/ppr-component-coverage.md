# Exact PPR source coverage audit

The new `ppr_sources` module preserves the pinned scoring contract and does not
change training labels, frozen forecasts, grades, models or the execution ledger.
The strict scorer needs eighteen explicit components. Generic `pts_ppr` or
`fantasy_points_ppr` totals are never substituted.

`nflverse_components(stats)` extracts twelve compatible, explicit common fields
from the modern NFLverse weekly schema. `sleeper_components(stats)` passes through
only explicit source fields, including rare events when present. Both return
component values, per-component coverage, missing/invalid reasons and an exact
score only when every component is justified. Missing/null is unknown; explicit
numeric zero is known. Nonfinite values, booleans and fractional observed event
counts are invalid. Signed yardage remains supported. Identity/game binding must
still be supplied by the shared loader and grading contract.

| Pinned component | NFLverse source field or unresolved bridge |
| --- | --- |
| `pass_yd` | Explicit `passing_yards` |
| `pass_td` | Explicit `passing_tds` |
| `pass_int` | Explicit `passing_interceptions` |
| `pass_2pt` | Explicit `passing_2pt_conversions` |
| `rush_yd` | Explicit `rushing_yards` |
| `rush_td` | Explicit `rushing_tds` |
| `rush_2pt` | Explicit `rushing_2pt_conversions` |
| `rec` | Explicit `receptions` |
| `rec_yd` | Explicit `receiving_yards` |
| `rec_td` | Explicit `receiving_tds` |
| `rec_2pt` | Explicit `receiving_2pt_conversions` |
| `fum_lost` | Explicit modern `fumbles_lost_total`, across every phase |
| `st_td` | Candidate `special_teams_tds`; full Sleeper ST-player equivalence unqualified |
| `st_fum_rec` | NFL PBP special-teams/recovery fields exist; Sleeper credit bridge unqualified |
| `st_ff` | NFL PBP phase/forced-fumble IDs exist; Sleeper credit bridge unqualified |
| `fum_rec_td` | Candidate `fumble_recovery_tds`; joint defensive-credit exception unresolved |
| `idp_blk_kick` | NFL block/PBP blocker fields exist; Sleeper IDP credit bridge unqualified |
| `idp_fum_rec` | Opponent recovery does not authenticate the Sleeper defensive-credit flag |

Sleeper's official support states that fumble and fumble-lost deductions apply
during **any** type of play, including special teams. An offense-only sum of sack,
rush and receiving fumbles lost is therefore not a replacement for the modern
all-phase field. Its special-teams documentation distinguishes individual player
credits from team-defense credits. The cached public API guide and support pages
did not establish an omitted-stat-key-is-zero contract or the exact IDP/ST
classification needed here.

The fumble exception remains nonlinear: when `idp_fum_rec` is positive the pinned
scorer removes all `fum_rec_td` points. Knowing a fumble-return TD without its
defensive-credit flag cannot justify an exact PPR outcome. NFL opponent recovery,
special-teams phase and player position do not silently establish that flag.

## Real source checks

The coverage audit used existing 2023 NFLverse weekly data, the already exposed
2026 Week 6 Sleeper cache, and one new completed 2023 PBP file. No Week 8 or later
2026 outcomes were acquired or inspected. It performed no fitting, outcome
grading, model selection or predictive comparison.

The weekly NFLverse sample contains 6,173 offensive skill-player statistical
rows. The Sleeper sample contains 369 players with explicit played evidence.
Every one of the eighteen Sleeper components has zero explicit-zero values in
that sample; omitted fields remain unknown. The rare `st_fum_rec`, `st_ff` and
`idp_blk_kick` fields each appear once with a nonzero value. Neither source
currently supplies a fully qualified eighteen-component row through this
adapter, so exact PPR training outcomes remain null.

The 2023 PBP asset has 49,665 rows over 285 games and no duplicate game/play IDs.
After excluding administrative, nullified and deleted rows, 43,658 rows have
explicit fumble/forced-fumble/punt-block and special-teams flags. There are 665
fumble plays, including ninety on special teams; 31 special-teams forced-fumble
plays have primary player IDs. All 33 blocked-kick plays have a blocker ID. Four
lost fumbles without recoverer IDs went out of bounds, so they are not missing
defensive-player credits. The 37 apparent missing live-play flags found during
inspection were all nullified `no_play` penalty rows and are excluded.

These checks establish useful NFL event evidence. They do not independently
prove complete authoritative game coverage, original historical publication or
Sleeper's special-teams/IDP credit rules. The adapter therefore leaves the six
rare bridges unresolved and does not generate event-absence zeros.

`audit_pbp_event_coverage` reports missing flags, attribution gaps and unknown
deletion status explicitly. `audit_cached_coverage` verifies cache hashes before
reading sources and produces only aggregate coverage. The reviewed aggregate
receipt is [ppr-2026-10-22.json](../reports/source-coverage/ppr-2026-10-22.json).
Raw source rows remain ignored locally.

Three new public source families were bounded below fifty MiB each: NFLverse PBP
(20,770,088 cached bytes, including release metadata), nflfastR field documentation
(68,865 bytes), and official Sleeper documentation (334,354 bytes). The PBP asset
SHA-256 is `bd3484731408def6b0ec93225bba2bd7b2c65769ca707a2b9444d891abdc6776`.
Exact URLs, source hashes, retrieval clocks, file-vintage headers and documentation
findings are in the receipt. Upstream rights remain separate; acquisition does
not authorize raw or row-level redistribution.

All data are current-vintage reconstructions. Retrieval and HTTP file-vintage
times do not authenticate original weekly publication or correction ordering.
No performance gain or exact-PPR source completion is claimed. A future complete
credit bridge or provider sparse-zero contract needs its own evidence and
registered study before it changes training or prospective operation.
