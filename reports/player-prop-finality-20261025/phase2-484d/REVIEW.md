# Strict propV2 adapted to Phase 2 484d — public-safe audit share

State: **AUDIT PREVIEW ONLY, NOT FINAL ACCEPTANCE**. The website source was
`484dbeff5c3fb34673380bf52b0f30ee0354a521`. The source worktree and the active
external writer were left unchanged. This package contains source changes,
source hashes and compact fictional-test evidence only. No commit, push,
coordination comment, provider collection, protected 2026 outcome access, new
fit or deployment is part of this handoff. Original audit artifacts remain
intact outside this package.

## Exact adaptation and alternative boundary

`player-prop-phase2-484d.patch.gz` contains exactly the 52,033-byte adapted patch.
Its decompressed SHA256 is
`a533ac8872b008389bcbfffbd4dee2cc8262cde59346b1b6ac36065e0c6d6ce9`.
Gzip uses compression level 9, mtime 0 and no embedded filename. Its compressed
hash and the complete file inventory are in `MANIFEST.json`.

The patch changes only `output/app.js`, `output/index.html` and
`tests/test-ui.cjs`, in 17 explained hunks. Exact 484d before/after hashes are
recorded in the manifest. Patch application and independent three-file
reconstruction matched the preview bytes.

The original Main V2 package remains the separate alternative in `../v2/`:
generated Main `453e7e6e843b0cb1ae611b0925063e0f96c70196`, source
`5e45584460a0f1eb61acf8d0cb50faea6e8a614b`, patch SHA256
`3506cb626934757ceed52361c0b96cd7c021e0769ffba9e44d8fe14fcbf61796`.
Its original patch fails the check against 484d. This package ports its strict
prop evidence contract onto the actual Phase 2 source. Use the variant whose
exact source preimages match; the Main app is not a Phase 2 replacement.

## Preserved behavior and explicit source precedence

All 264 unaffected named functions and all other 153 copied source/config/test
paths remain byte-identical. Presence, fantasy scoring, Classic FG, ranking,
reporting and paper-ticket helpers remain unchanged. The current My Picks
game-row renderer is byte-identical. The complete 58,905-byte original current
UI test file is retained as an unchanged prefix.

Current Phase 2 identity-checked public outcomes keep their authority. A
matching final, pending, conflicting or unresolved public record is not bypassed
by raw ESPN data. Strict event evidence supplies the fallback when that outcome
key is absent. A public final remains authoritative when raw event data disagree;
corrections must advance through the existing Phase 2 publication path. Fantasy
points retain their separate presence-aware scoring path.

Raw prop evidence requires matching event/competition/athlete/team, integer REG
season/week, explicit timezone kickoff and confirmed finality. Missing scope
clears prior event evidence. New saved selections bind player/game/team/athlete,
kickoff, period and source. Legacy unbound selections remain stored and
unresolved. Explicit edits target the exact saved record and preserve every
unchanged object's JSON bytes. Reads/renders never migrate saved selections.

## Preview results

- Original current UI suite: pass; original assertion population retained.
- Core props: 52 pass; the actual 484d baseline had 11 failures in those 52 cases.
- Strict scope: 23 invalid cases reject and 2 positive cases pass.
- Phase 2 composition: 14 cases pass. About: 20 assertions pass.
- Independent downstream comparison: 18 cases, no differences.
- Relevant Python suites: 115 scorecard + 11 accuracy + 24 rankings = 150 pass
  on each source snapshot.
- Chromium: 99 prop checks, 170 game-market checks and 106 current primary
  forecast checks pass at 320/390/1280. No actual provider requests were sent.
- JavaScript syntax, compile, whitespace, adapted patch check and exact
  reconstruction pass. The packaging check also uses `--whitespace=error`.

The 52-case port pins the actual 484d helper hashes and maps one older V2 live
label to the existing Phase 2 `above` label while retaining its value/finality
assertions. The strict-scope harness includes the separate event-status helper.
The 14 new composition cases explicitly cover the merged authority, storage,
async and fantasy boundaries. Compact logs and JSON evidence are included.

## Remaining validation and conflicts

No textual hunk conflict remains against the exact 484d preimages. Active-owner
source review, actual combined CI and complete release-artifact verification
remain outstanding; these preview checks are not final acceptance.

The complete presentation browser test fails on both data-excluding snapshots
because the fictional board lacks its expected real leading props. The complete
grading browser test times out on both snapshots waiting for the saved-report
DOM. The focused selected-browser entrypoint returns
`USE_ACTUAL_RELEASE_ARTIFACT_CHECKS`; no passing check is inferred from it.

The initial full backend baseline ran 1,162 tests with 9 failures and 200 errors
before the audit copy had the required historical Git source objects. A retry
with isolated source history was stopped at the 600-second audit budget. These
are not a full-suite PASS or a verdict about the website source. Full failure
and partial logs are retained outside this public package. The directly
relevant 150 tests passed on both snapshots; backend code and policies are
unchanged.

An existing fantasy presentation limitation remains: explicitly missing scoring
fields can yield a null numerical value with a provisional `below` label. That
exact baseline behavior is preserved and tested. Raw ESPN `observed_at` remains
local browser time, not authenticated publication time or venue settlement.

## Read-only reproduction check

Run from a clean website checkout at the exact source commit. Set `PACKAGE_DIR`
to this package's directory. The following checks the patch without applying it:

```sh
test "$(git rev-parse HEAD)" = "484dbeff5c3fb34673380bf52b0f30ee0354a521"
gzip -dc "$PACKAGE_DIR/player-prop-phase2-484d.patch.gz" \
  | git apply --check --whitespace=error -
```

Verify the decompressed patch hash separately:

```sh
gzip -dc "$PACKAGE_DIR/player-prop-phase2-484d.patch.gz" | sha256sum
```

The expected value is the `a533ac...` hash above. The package contains no
source checkout or provider dataset. Actual combined tests belong to the
active owner's integration checkout and normal CI.
