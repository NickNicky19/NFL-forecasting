V2 is ready for parent source review. It is a new, separate three-path proposal
against generated main `453e7e6e843b0cb1ae611b0925063e0f96c70196` / source
`5e45584460a0f1eb61acf8d0cb50faea6e8a614b`. V1 remains on HOLD and its packet
bytes, baseline failures and 12 downstream regressions remain preserved.

`player-prop-finality-v2.patch` changes only `output/app.js`, `output/index.html`
and `tests/test-ui.cjs`. The index uses the new cache key
`mypicks-player-evidence-v2`. Patch SHA256:
`3506cb626934757ceed52361c0b96cd7c021e0769ffba9e44d8fe14fcbf61796`.
The patch dry-runs successfully against the disposable exact baseline.

The two shared fantasy helpers `current()` and `slpPlayed()` are restored to
their exact original function bytes. Twenty-three original helper/consumer
functions have matching hashes in `EVIDENCE.json`, including fantasy scoring,
player cards, free agents, matchup/start-sit consumers, selected ordering,
game-market finality and its presentation helpers. V1's direct global rewrite
is absent.

The prop-specific correction remains independent: missing requested statistics
are unresolved, explicit played zeros are retained, DNP requires explicit
event-specific evidence, signed yardage and corrections remain meaningful, and
live values never become final wins/losses. New saved picks bind the player,
game, team, kickoff, period and declared source. Old unbound records are retained
unresolved without fabricated historical identity. Rendering leaves storage
bytes alone; explicit add/remove/line edits preserve unchanged record JSON bytes
and target the exact saved record.

The ESPN final-evidence boundary is now mandatory:

| Required provider metadata | Rule |
| --- | --- |
| Summary event ID and competition ID | Both equal the exact board event ID. |
| `header.season.year` | Explicit integer equal to the board season. |
| `header.season.type` | Explicit regular-season value `2`. |
| `header.week` or `header.week.number` | Explicit integer equal to the board week. |
| Competition kickoff `date` | Explicit valid timestamp with timezone, equal to the board kickoff instant. |
| Athlete ID and team | Exact catalog ID and team; no name-only resolution. |
| Final status | Board and summary both report the supported confirmed Final status; contradictory incomplete status rejects. |

Absent, null, malformed or contradictory required scope fields clear the prior
event evidence and leave the final prop result unresolved. Supplying an exact
ID no longer substitutes for absent season/week/kickoff metadata. Two explicitly
supported equivalent kickoff encodings are tested, including a numeric UTC
offset representing the same instant.

This validates source identity/scope, not a provider clock. `observed_at` remains
the browser's local observation time after parsing; it is not represented as a
publication, update, historical availability or sportsbook settlement clock.
Weekly Sleeper data may still supply separately scoped provisional live progress;
it never supplies final prop evidence. A missing final-evidence header is not
replaced by weekly values or zero.

Actual live free-ESPN field support has **not** been verified by this fictional
source exercise. In particular, a free response lacking `header.week` (or any
other required field) will remain unresolved. This packet does not invent those
fields or infer them from an event ID, kickoff or browser clock. Any future
adapter for a different documented provider schema needs its own explicit
source review. Provider calls, paid services, protected-outcome reads and fits
performed here: zero.

The frozen combined test file is self-contained and retains the entire original
17,949-byte `tests/test-ui.cjs` as an unchanged prefix. The v1-only appended
assertion expecting global `current()` to return null was superseded by exact
legacy-helper hash checks, as required by the v2 scope. The strict prop-result
assertions are retained.

| Completed validation | Result |
| --- | --- |
| Original UI checks | 120 pass: 8 helpers, 19 presentation checks, 93 game-market checks. |
| Core prop cases | All 52 pass. |
| Strict provider scope | 23 invalid cases reject as unresolved; 2 valid cases pass. |
| Downstream preservation | All 18 cases match original behavior; zero new regressions. |
| Independent downstream comparison | 18 cases; zero differences from original. |
| Existing game browser matrix | 170 checks / 36 cases pass at 320/390/1280; zero page/console errors. |
| Prop browser matrix | 99 checks / 27 cases pass at those widths; zero page errors. |
| Source and patch | JavaScript syntax passes; exact three-path patch dry-run passes. |

The core baseline failures are retained in `v1-original-before-52.log`. The
v1 scope counterexample fails on missing season in `v1-strict-scope-before.log`;
v2 rejects all 23 invalid scope cases. The 12 v1 fantasy regressions are retained
in `v1-downstream-regressions.json`. One initial independent comparison used
cross-VM object-prototype equality; its failure log is preserved and the final
comparison compares the same plain data across realms. No product assertion or
input population was weakened to correct that harness comparison.

Broader fantasy unknown propagation remains a distinct finding, not a blocker
to this strict prop-specific variant. See `BASELINE_FANTASY_BOUNDARIES.md`. V2
does not claim to repair baseline sparse-score zeros, missing-player DNP text,
or the historical-average-under-Final consumer fallback. It restores the
original shared helper behavior while retaining strict prop-result evidence.

All work stays in this new proposal directory. No website checkout, ref, lease,
protected policy, gate, registration, old forecast or remote was changed.
Parent owns the ordinary source integration, forward app/index bindings in the
existing inventory/policy, normal CI/recovery checks, and any publication. No
deployment or actual provider/operating qualification is claimed here.

Frozen source SHA256 values:

- app: `2287f9f9b9c470e311b68f1b8af11274388f14323717160d01e1d72bd03e8594`
- index: `cc7e76130908ec3936c4fe75fcec1c538d0b012792c24e82686cc7a3fb133143`
- combined tests: `0fa1a53b16431b6a013bea087de9cb04a28004d402c652988dd240a8b547766a`

`EVIDENCE.json` binds source hashes, preserved function hashes, the patch and
the completed receipts. The prototype files are under `prototype/`; all earlier
v1 files remain at their original location.
