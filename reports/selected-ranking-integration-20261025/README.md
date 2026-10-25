# Selected forecasts: Top Picks and sorting are live

**Integration completed and verified on the live website. Forecast-method research remains paused.**

Open [Props](https://nicknicky19.github.io/nicks-expert-nfl-picks/#/props) and refresh
the page. Top Overs and Top Unders now use the saved selected forecasts where
available. Each card labels its selected mean/median or its R0 fallback.

The sort menu includes:

- **New forecasts: biggest gap** — the default, using fixed category-scaled gaps.
- **New forecast: highest** — after selecting a numeric category.
- **New TD probability: highest** — after selecting Anytime TD.
- Explicit R0, live-points and name alternatives.

The current snapshot has **12 Overs and 12 Unders: 22 selected forecasts and two
explicit R0 fallbacks**. All 12 Unders and 10 Overs use selected forecasts.
There are 1,754 selected forecast rows across 11 categories; exact PPR retains R0.
Point gaps are descriptive rankings, not calibrated over/under probabilities.

## Source, hosted execution and actual live checks

- Functional integration: [PR #4](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/4),
  head `05b6634dac7cabe20af76c83e851e1d5b372a484`. Its original release evidence is retained.
- Final caption/cache correction: [PR #5](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/5),
  reviewed head `6760671e0aa6c32defcf21ac7ab767d07d1842d5`.
- Actual build source: `a2047854bece90ba354f7e379846cafc499fa7d6`;
  generated-data commit: `89512ed952308dacc1f6a930915ddbcdccd460d9`.
- [Final source CI](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40147531656)
  and the [existing updater/Pages run](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40147684042)
  succeeded. The first Pages deployment succeeded; no alternate scheduler was created.
- Selections were prepared **2026-10-25 00:42:03.959673 UTC** and durably completed
  **00:42:04.119160 UTC**, before every retained kickoff. Earliest kickoff is 13:30 UTC.
- Actual live DOM checks verified the new default, three sort modes against the
  independently computed first ten players, selected forecasts/leans, and the
  corrected My Picks caption through real controls. The temporary local selection
  was removed. No forecast data or fixtures were injected.
- The live page passed at **320, 390 and 1280 pixels**, with no page overflow or
  JavaScript errors. All nine captured assets matched reviewed/recorded hashes.
  TLS remained enabled; no provider requests were permitted during verification.
- Genuine issued inputs reproduced the selection artifact **byte for byte**.
  Missing-companion fallback and restoration passed in an isolated copy. This
  was not a production rollback.

[Machine-readable public release evidence](PUBLIC_RELEASE.json) contains the
exact public commits, runs, hashes, counts and verification limits. Detailed
internal receipts and the expanded internal ledger remain private.

## Checks and boundaries

The final source passed 113 Python tests, 37 cross-language/application checks,
27 overlay checks and 27 existing UI checks. Fictional actual-render browser
checks passed 53 new-ranking and 100 primary-display checks. Independent read-only
review accepted the source, exact policy bindings and actual live evidence.
These are software/operational checks, not additional NFL accuracy observations.

Original R0 forecasts, picks, archives and historical grades remain separate.
The Record page explicitly identifies the R0 history. Original H3, RB and
receptions registrations/gates are unchanged. Existing website scheduling is
unchanged; the next configured daily run is 2026-10-25 13:06 UTC, still pending
until observed. Actual future kickoff freezing and grading remain pending until
those events occur. Exact-PPR labels and broader lab weekly-training/selection
handover remain separate outstanding work.

No new forecasting method was fitted or qualified by this integration. No new
website-relative accuracy gain is asserted. Further forecasting research stays
paused as the owner requested.
