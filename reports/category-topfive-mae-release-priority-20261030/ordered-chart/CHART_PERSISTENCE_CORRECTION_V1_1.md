# Chart point adapter V1.1: actual persistence before the deadline

This correction preserves the original V1 source, protocol and twelve-case PASS
receipt. V1 checked issue clocks and an independently trusted capture identity,
but did not explicitly require the actual persistence completion to precede the
deadline. V1 was never admitted, captured or deployed.

The new source is `nfl_lab/category_topfive_chart_mae_future_v1_1.py`, adapter
version `nick-chart-ppr-mae-future-adapter-v1.1`. The original genuine-law
extraction, separate mean, immutable candidate digest and consumer checks remain.
The finalizer additionally requires the independently trusted capture receipt to
contain:

- `state == 'FROZEN_AND_READ_BACK'`;
- `horizon == 'player_game'`;
- timezone-aware clocks with
  `issued_at <= persistence_completed_at < issue_deadline_utc`;
- `readback_completed_at >= persistence_completed_at`.

Readback may occur after the deadline. It is not made into a new predeadline
capture gate. The actual frozen bytes must already have been persisted before
the deadline; later readback cannot recover a late or missed original capture.
The existing consumer still requires
`information_cutoff_utc <= issued_at < issue_deadline_utc < kickoff_utc`.

The returned view preserves capture state and actual persistence/readback
timestamps alongside the original chart contract and separately retained mean.
This does not claim a website publication time or actual visible pregame use;
those must be verified independently by the retained owner.

Four new fictional cases passed once: valid timed capture with preserved mean
and readback after deadline; persistence at deadline rejected; malformed or
unreadback receipt rejected; wrong horizon rejected. Actual usage:
**1.144814 CPU seconds, 1.149632 wall seconds, 164,274,176 bytes RSS**.

The new forward software allocation was 10 CPU seconds, 15 wall seconds,
320 MiB RSS and 32 KiB of new source/metadata. No NFL source, model
deserialization, fit, forecast, genuine capture, HTTP, CAS or deployment ran.
The original V1 budget and evidence remain consumed and intact.

Current-source admission, approved model restoration, real future-query
inference, original capture and consumer/publication/rollback checks remain
unexecuted owner gates. A source helper and synthetic PASS do not satisfy them.
