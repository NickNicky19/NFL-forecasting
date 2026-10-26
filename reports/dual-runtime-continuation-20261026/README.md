# Qualified runtime continuation

This correction separates the namespace used for new writes from the explicitly
sealed namespace containing the prior capture. The old store was observed at
115/128 assets; a fresh registration and minimum complete operation require at
least 16 additional assets. Old stores, original receipts and failures remain.
No cap is raised and no history is deleted to obtain space.

Root `audit-weekly-hosted-v3-root-GO` and private static template V3 add one
closed `prior_capture_qualified_runtime` record. It contains the original
qualified package, its original pending census, an exact feed/receipt anchor,
and, for non-null old checkpoints, the sealed original static Root hash.
The current qualified package and current census authorize all new writes and
capacity admission. The old package permits only GET recovery of the exact
registered capture/history. There is no namespace search or retry fallback.

Checkpoint selection matches both binding and package hashes. Original reader
proofs, Root preimages, known-by clocks, job/source identities and all snapshot
parts remain checked. Same-source and helper-pin restrictions remain strict;
this is not an implicit adapter for checkpoints issued by a different code
source. Initial original COUNT7 recovery still uses its separately qualified
historical-capture path and a null prior grading checkpoint.

The Parent uses a separate GET-only client for prior history, on its existing
aggregate HTTP/transfer ledger and unchanged live authority/cadence guards.
Writes, claims, failures, capture archives and new grading checkpoints use only
the current namespace. The original V2 Root/template/native protocol remains
supported. Native SAFE_SEAL/locator transport and all three-job proof rules are
unchanged. Exactly the original five Root fields remain dynamic.

Local checks before integration: 474 producer checks passed; after moving the
metadata-only test fixture builders into an existing shared test file, 221
Main bootstrap/Parent checks passed. A targeted producer replay also checks the
shared fixture change. The two stores' full multipart history was actually
restored, appended into the distinct current store and read by a separate
client using fictional HTTP. Capture recovery also ran in a fresh subprocess
under the unchanged 180s wall /120s CPU /512MiB address-space limits: 105 original
files restored; 146 GETs of the 640 limit. Invalid anchors/packages/census had
zero private GETs. These are software checks, not genuine Actions execution or
forecast-accuracy evidence.

The separate Main source contains only the existing shared template, Parent and
history metadata modules and two existing shared test files. Producer numerical
helpers, model artifacts and scoring procedures are unchanged. New runtime pin
paths are not introduced. A retained real-metadata size projection was 51,156
bytes of the 61,440-byte Root cap with 128/128 pins; only a final genuinely
qualified package can establish the actual Root and dispatch sizes.

Deployment readiness still requires: normal exact-source CI/review/integration,
current global reservation and pending census, a genuine qualified new namespace,
final-source three-job registration and create-only native record, then an actual
successful capture/grading/export plus fresh-process restoration. The current
registered-builder public slot has not been populated by this local patch.
Existing activation gates remain in force. No scheduler, retired ticker, source
freshness rule, scientific registration, model fit or paid service is changed.

The supported continuation is explicit and bounded. A later full store requires
another qualified owner rotation and registration under the existing workflow;
unbounded automatic rollover and arbitrary cross-source history are not claimed.
Daily cadence does not satisfy every per-game T24/T6/T90 capture horizon. Missing
captures remain missing, and old issuance/availability clocks are never backdated.
