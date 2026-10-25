# Exact 484d prop adaptation hunks

- `output/app.js` `@@ -28,6 +28,9 @@ const S = {`: Separate exact prop evidence from the accepted Phase 2 final-outcome and fantasy caches.

- `output/app.js` `@@ -948,12 +951,124 @@ function pv(p, prop) {`: Require exact provider event/athlete/team/REG-season/week/timezone kickoff and confirmed finality; retain identity-checked Phase 2 outcomes as authoritative, with strict raw-event fallback and separate fantasy scoring.

- `output/app.js` `@@ -964,6 +1079,9 @@ function propStatus(p, key, line, dir) {`: Require exact provider event/athlete/team/REG-season/week/timezone kickoff and confirmed finality; retain identity-checked Phase 2 outcomes as authoritative, with strict raw-event fallback and separate fantasy scoring.

- `output/app.js` `@@ -1109,15 +1227,20 @@ function liveLineText(p, key, line) {`: Bind asynchronous provider responses to the captured current board, refresh current-week finals for corrections, and keep completed past-week caching.

- `output/app.js` `@@ -1126,23 +1249,26 @@ async function pollSleeper() {`: Bind asynchronous provider responses to the captured current board, refresh current-week finals for corrections, and keep completed past-week caching.

- `output/app.js` `@@ -1261,12 +1387,13 @@ async function liveTick() {`: Bind asynchronous provider responses to the captured current board, refresh current-week finals for corrections, and keep completed past-week caching.

- `output/app.js` `@@ -1350,7 +1477,12 @@ globalThis.addEventListener("weekly-adaptive-overlay-ready", () => startWeeklyOv`: Reset prop evidence per board; clear weekly live caches on period changes so an old player row cannot supply a new week.

- `output/app.js` `@@ -5359,19 +5491,55 @@ function setCompare(slot, id) {`: Bind newly saved props to the player/game/team/athlete/period/source/kickoff. Preserve unbound records and unchanged JSON object bytes through explicit edits, including edits to co-stored game selections.

- `output/app.js` `@@ -5388,7 +5556,7 @@ function toggleGame(gid, market, side, line, odds) {`: Bind newly saved props to the player/game/team/athlete/period/source/kickoff. Preserve unbound records and unchanged JSON object bytes through explicit edits, including edits to co-stored game selections.

- `output/app.js` `@@ -5448,7 +5616,7 @@ function renderMine() {`: Preserve the exact current My Picks game-row renderer, unsupported-collection guard, non-current-period controls and summary. Retain unknown props unresolved; edit/remove the exact saved record by index.

- `output/app.js` `@@ -5463,9 +5631,9 @@ function renderMine() {`: Preserve the exact current My Picks game-row renderer, unsupported-collection guard, non-current-period controls and summary. Retain unknown props unresolved; edit/remove the exact saved record by index.

- `output/app.js` `@@ -5505,19 +5673,26 @@ function renderMine() {`: Preserve the exact current My Picks game-row renderer, unsupported-collection guard, non-current-period controls and summary. Retain unknown props unresolved; edit/remove the exact saved record by index.

- `output/app.js` `@@ -5860,8 +6035,10 @@ document.addEventListener("click", (e) => {`: Use exact saved-record indices and strict finite personal-line parsing. Clear-finished cannot treat unbound legacy props as qualified finals. Preserve other record bytes.

- `output/app.js` `@@ -5872,8 +6049,8 @@ document.addEventListener("click", (e) => {`: Use exact saved-record indices and strict finite personal-line parsing. Clear-finished cannot treat unbound legacy props as qualified finals. Preserve other record bytes.

- `output/app.js` `@@ -5992,11 +6169,17 @@ document.addEventListener("change", (e) => {`: Use exact saved-record indices and strict finite personal-line parsing. Clear-finished cannot treat unbound legacy props as qualified finals. Preserve other record bytes.

- `output/index.html` `@@ -90,7 +90,7 @@`: Advance only the existing Phase 2 app cache key; retain the complete 484d HTML structure and other script versions.

- `tests/test-ui.cjs` `@@ -734,3 +734,352 @@ print(json.dumps(project_accuracy(reports)))`;`: Retain the complete current 484d UI test file as an unchanged prefix. Append the original 52-case population, 23 invalid/2 positive scope cases and 14 explicit Phase 2 composition cases.

