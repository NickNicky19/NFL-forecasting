# Frozen grading partition wire and native capacity evidence

This is the original, locally verified four-file partition implementation based on `810be9b1f55bb90f9683bb510d49db954b2e4aa8`. It is **not integrated Ops readiness**, a genuine Actions qualification, cross-source history migration, or a registry/seal activation.

`REPORT.json` is copied byte-for-byte from the pre-commit freeze (SHA-256 `170ce39208acb2e28930a4340388011ee0ab26c2d2253ededae3b47224bb2a81`). Its `commits: 0` and local `/tmp` paths describe that historical freeze. The four committed source/test hashes are recorded there. `SHA256SUMS.json` authenticates each copied evidence file.

- Original two-full-capture rejection: 107,881,965 decoded bytes exceeded the unchanged 64 MiB v1 guard; no snapshot was written (`before.log`).
- Related checks: 136 passed. The remaining full two-capture native node ran separately and passed, giving 137 total cases; exact selection is retained in `remaining-tests-command.json`.
- Two disjoint fictional games each retain 18,000 candidate and 5,000 R0 forecasts, 5,000 selected rows, and 5,000 opportunities. No real provider/outcome/model data or NFL fit was used.
- Separate cold native writer and reader installed the original 512 MiB address-space, 120 CPU-second, and 180 wall-second limits. Writer: 51.98 CPU seconds, 475,795,456 peak AS bytes, 39 calls. Reader: 12.33 CPU seconds, 128,372,736 peak AS bytes, 33 GET-only calls. The fictional runtime occupied 4,161,883 bytes. Exact final cumulative transfer counters were not printed by this initial probe; the original store's 40 MiB transfer guard remained enforced.
- Native part locators and data are not in this public evidence directory. The implementation places them only inside the private native root. Original rows, canonical logical hashes, corrections, old availability proofs, and losing weeks remain intact.

The report deliberately retains the outstanding integration gates: the worker's duplicate pre-authentication causes a minimum 41-call writer; append authentication needs the explicit local-root/native-root binding; Ops/history validators need explicit v2 evidence handling. Subsequent call-budget work must keep all live Root/source/API checks, fresh rechecks, reservations, draft checks, and original resource/quota limits. Same-source history is the supported interface; cross-source upgrade remains unqualified.
