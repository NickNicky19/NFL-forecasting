# Count A original private ingress — actual execution

The original artifact-owning environment has an existing authorized ingress:
`nfl_lab.owner_private_bootstrap.OwnerBootstrapClient`, using the existing
GitHub private draft release **422661769** in `NickNicky19/NFL-forecasting`.
The previous statement that only a genuine Actions writer could establish a
private handoff was incomplete. This explicit owner-origin lane was found and
executed without claiming Actions provenance.

At **2026-11-12 12:26:09 America/Chicago** (**18:26:09 UTC**) the exact delegated,
hash-only owner authorization was posted on the existing PR #1:
https://github.com/NickNicky19/NFL-forecasting/pull/1#issuecomment-6832290866
It claims delegated automated authority and does not claim human review.

The guarded one-shot upload then passed actual owner identity
`NickNicky19` / `208912933`, repository push permission, the fresh unedited
authorization, the original successful three-job qualification, private-draft
checks, exact canary readback and complete asset inventories.

Its first asset POST stopped with **HTTP 401 Unauthorized** at:

`https://uploads.github.com/repos/NickNicky19/NFL-forecasting/releases/422661769/assets?name=manifest-4a09586bed52af27e15cd4a892adc8c51f0b9d4645849c81bbbfab59de157892.json`

The original safe client reports `HTTP_OR_RATE_AMBIGUITY`; the transparent
status observer established that this response was 401, with no rate-limit
header. Fourteen preceding GETs passed. The specific token-versus-managed
credential-forwarding cause is not distinguished by the retained response.
Owner account permissions alone did not establish authentication on the
separate upload host.

Read-only verification after failure found the same **39 assets / 29,605,302
bytes** and no new Count A root or payload asset. No model payload POST was
attempted. No descriptor, native materialization, Count A inference, current
capture or derived feed was produced. The failed operation and reservations
remain retained; there was no automatic retry or safety-guard relaxation.

## Exact user/credential-owner action

The inherited `GH_TOKEN` already authenticates the API controls. The owner of
that **existing Codex/GitHub credential connection** must correct or confirm
its authentication for the exact **GitHub release-asset POST on
`uploads.github.com`** above. Required capability is repository release-asset
write access, corresponding to **Contents: read and write** for
`NickNicky19/NFL-forecasting`. The 401 does not establish that this permission,
rather than managed credential forwarding, is the missing part.

The concrete credential-owner request is: "API requests authenticate as
NickNicky19 / 208912933, but the approved private release-asset POST to
uploads.github.com returns 401. Please verify/correct this existing connection's
upload-host authentication and release-asset write capability, then confirm
that the route is supported." Attach the safe HTTP-status receipt and exact
endpoint above, not private model bytes or credentials. No request has been sent
to an external administrator by this session.

Managed environment documentation supports owner-configured secret bindings
with explicit credential destinations. If an existing approved owner credential
is available that way, its `GH_TOKEN` binding must cover both `api.github.com`
and `uploads.github.com`. The current environment reports no configured secret
or vault binding that this session can select or modify. I have not established
that this inherited managed GitHub connection exposes a self-service upload-host
setting, or that re-entering a credential would fix the failure. Do not create a
new token/account or paste a credential in chat. General network access is
already unrestricted and enforced; no network allowlist change is established
as necessary.

This action targets a demonstrated upload-host authentication failure. It is
not a request for the model files or another historical experiment. A source
owner can then issue a separately authorized continuation with fresh exact
authorization, retaining this consumed failed operation and confirming no
duplicate asset before a further attempt.

## Original-file and runtime boundaries

The original capsule, producer proof and FIT_START remain hash-identical:

| Original | Bytes | SHA-256 |
|---|---:|---|
| Capsule | 399,037 | `5f55367c9f3389dbbe713b1aa95e691e77602cde99bf8e5ff657554a2d5a6a36` |
| Producer proof | 26,032 | `9071f4fd5f81fb7e0514e9f1ac47a93d207fc5b27cda3d8aa7f7ea16d320b45e` |
| FIT_START | 5,968 | `9119320dc53a64c0bca2caebae6b1b416335ae0db38160ffbc23a1e635d2e967` |

Their deterministic opaque transfer bundle is **329,431 bytes**, SHA-256
`dc4c8ded5ae91c9bf9ef28d915a57a1c6a68c819870e0c5512796413dbd31934`.
It was never retained as a replacement model or publicly exported. The private
root manifest is 11,634 bytes, SHA-256
`4a09586bed52af27e15cd4a892adc8c51f0b9d4645849c81bbbfab59de157892`.

The original fourth-peer storage factory initially could not account for four
expired attachment paths. All four archives were recovered byte-for-byte from
existing retained CAS copies into their original paths. The unchanged complete
quota check then passed. No user re-upload is required. The originals, old
ambiguous October failure and its reservations remain preserved.

The present native producer reads already-owned Count A files. It still needs
the scoped source-bound owner-descriptor materialization bridge before genuine
native restore and inference. That bridge is being prepared through normal
protected review; passing its tests does not establish native execution.
The website owner's consumer admission and release remain separate.

Evidence: `ACTUAL_PRIVATE_UPLOAD_FAILURE_V1.json`,
`ORIGINAL_THREE_FREEZE_V1.json`, `OWNER_TRANSFER_INDEPENDENT_REVIEW_V1.json`,
`ORIGINAL_UPLOAD_ACCOUNTING_RECOVERY_V1.json`, and
`ORIGINAL_STORE_POSTRECOVERY_CENSUS_V1.json` in this directory.
