The strict v2 prop fix does not repair the older global fantasy-presence and
unknown-propagation behavior. This remains separate from its readiness claim.

Original `current()` / `slpPlayed()` are restored exactly. Therefore K/DEF and
rare-event observations retain their original values rather than being discarded
by v1's narrower participation filter. The 18 direct downstream probes match
the baseline, including positive points, real zero controls and negative points.

The following pre-existing limitations remain:

- The original helper treats points=0 alone as participation and can infer DNP
  from a missing final row when the feed/box request succeeded. The strict new
  prop-result path bypasses it and leaves such cases unresolved.
- Sparse scoring still fills absent components with zero. For example, GP-only
  skill data can compute zero, and GP-only DEF data without allowance fields can
  compute 10 from zero-default tiers. These are preserved baseline deficiencies,
  not newly qualified outcomes.
- `weekPts` and matchup consumers coerce missing live points to zero. This needs
  a broader explicit unknown-propagation design before claiming complete fantasy
  data correctness.
- The original `playerCard` consumer has a historical-average fallback while its
  label is selected independently from game state. If its `current()` contract
  supplies null for a final game, the consumer can display an average such as
  the fictional 8.25 under “Final.” V1's global change newly exposed that path
  for valid K/DEF/rare records. V2 restores the old helper behavior; it does not
  change or advertise a repair of this baseline consumer fallback. The function
  itself is byte-identical to the original.
- Free-agent presentation can use “did not play” when current data is absent.
  No new DNP authority is established by preserving that existing expression.

A future fantasy-wide correction needs positive participation evidence across
all supported positions/events and explicit unknown propagation through scores,
aggregates and labels. Synthetic GP, inferred DNP, or missing-to-zero filling
would not be a valid repair. This work deliberately does not rewrite that wider
pipeline or alter its scoring/model policies.
