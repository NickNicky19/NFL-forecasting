> V1 is HELD for confirmed downstream regressions. The separately reviewed narrow [V2 package](v2/README.md) restores all shared fantasy helpers to exact Main bytes, passes expanded tests, and does not claim the wider baseline fantasy debt is repaired. Do not integrate the v1 patch below.

The three-path main-site prototype is ready for review. It is based on generated
main `453e7e6e843b0cb1ae611b0925063e0f96c70196`, whose source is
`5e45584460a0f1eb61acf8d0cb50faea6e8a614b`. The baseline app and index exactly
match the previously retained TLS/Git-byte-verified served files. No website
checkout, ref, lease, protected policy, registration or remote was written.

Apply `player-prop-finality-v1.patch` against that baseline. Its only paths are
`output/app.js`, `output/index.html`, and `tests/test-ui.cjs`. The index changes
only the app cache key to `mypicks-player-evidence-v1`. Patch SHA256:
`b3302defec8d58a6a241c2a00d93a6c196f1e1173cb4934e384ff5cc2d55ed29`.
`patch --dry-run -p1` succeeds in the disposable original-source copy.

| Actual baseline defect | Fictional reproduction | Prototype behavior |
| --- | --- | --- |
| `current()` returns empty stats when unavailable, `statValue()` supplies zero, and missing final rows become DNP when a feed/box request succeeded. | Missing row, empty box, healthy feed without player, injury/INA, gp=0, missing/invalid yardage. | Unavailable remains unresolved. A requested field must be present and numeric. A real played zero remains zero. DNP needs an explicit event-specific `didNotPlay === true`, a confirmed final, and no conflicting participation. |
| `propStatus()` treats every `post` state as final; it can use stale weekly stats and name-linked ESPN rows. Completed-game polling stops after a cached final. | Postponed/canceled/suspended; scoreboard Final with still-live summary; wrong event/athlete/team/season; late prior-period response; later stat correction. | Final comparisons require matching event, exact athlete ID/team, period context and confirmed Final markers in both scoreboard and summary. New invalid/missing summaries clear the earlier event value. Final summaries refresh through the existing browser poller, allowing corrections. |
| Saved props contain no game binding. `minePick`, replacements and line edits select by player/category/current week and can follow a changed board identity. | Legacy unbound pick, changed game/team/kickoff/source/period, duplicate logical selections, add and line-edit/reload. | New picks save explicit game/team/kickoff/period/source bindings. Legacy unbound records remain unresolved; no game ID is backfilled. Rendering preserves the full storage string. Explicit edits preserve unchanged records' original JSON bytes and address the exact record index. |

The served source already keeps live overs provisional; that specific defect
does not reproduce on this baseline. The prototype preserves it. Confirmed
integer equality is a push, signed yardage is retained, and later source
corrections recompute results against the saved personal line.

Validation is complete and remains fictional:

- Original source fails 47 of the 52 new cases. The prototype passes all 52.
  Earlier intermediate failures and their logs remain retained.
- The entire 17,949-byte original `tests/test-ui.cjs` is an unchanged prefix.
  All 120 checks reported by that original file pass: 8 helpers, 19 presentation
  checks, and 93 game-market checks. No original assertion was removed or edited.
- The existing game browser harness passes 170 checks / 36 cases at widths
  320, 390 and 1280, with zero page or console errors.
- New player-prop browser fixtures pass 99 checks / 27 cases at those same
  widths, including actual delegated add clicks, actual input change events,
  localStorage writes/reload, exact legacy record bytes, no page overflow, live
  corrections, missing data, and played-zero pushes. Page errors: zero.
- JavaScript syntax passes. Eleven preserved application functions have exact
  matching source hashes in `EVIDENCE.json`, including `gameBetStatus`,
  `gameBetLabel`, `resBadge`, `progress`, the selected ranking policy/forecast/gap
  functions, `displayedProps`, `filteredPlayers`, and the original stat accessor.
- Browser requests outside loopback were intercepted. Provider requests,
  protected-outcome reads, fits and website writes: zero. These cases establish
  functional behavior with fictional inputs, not live provider finality or venue
  settlement. The screenshots include a clearly fictional test-only add button.

The comparison boundary is deliberately explicit. Combined categories require
both component fields; missing components are not padded with zeros. Fantasy
point props remain unresolved when the existing event adapter lacks complete
game-specific scoring evidence. Weekly Sleeper values can provide provisional
live progress, never the final result. Missing athlete IDs or positive
participation evidence also produce unresolved results. Old unbound picks can
still have their personal line explicitly edited or be explicitly removed;
their historical identity is never invented.

This is the separable main variant, not the complete Phase 2 historical grader,
strategy/accuracy, paper-builder or production-evidence integration. Existing
forecast engines and selected ordering functions retain their original source.
The patch does not change scientific gates or existing issued forecasts.

Parent integration still requires the normal owner source lease/permission,
the forward app/index bindings in the existing 22-file inventory and protected
publication policy, and the normal CI/source/recovery/deployment checks. Those
protected files are intentionally absent from this patch. No current-main or
live deployment success is claimed for the prototype.

The primary review files are `prototype/output/app.js`,
`prototype/output/index.html`, `prototype/tests/test-ui.cjs`,
`player-prop-finality-v1.patch`, and `EVIDENCE.json`. Exact baseline hashes and
source identities are in `BASELINE.json`. Before/after source results are in
`before-prop-regressions-frozen.log` and `after-prop-regressions-frozen.log`.
Final browser receipts are `browser-game-preservation-results-final.json` and
`browser-prop-results-final.json`; screenshots are under the corresponding
`browser-*-screenshots-final` directories.
