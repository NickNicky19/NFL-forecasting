# FTN charting schema capability — October 25, 2026

**Executed and independently accepted: source bytes and nine-field schema only.**
This is a data prerequisite, with zero new forecasting fits, predictions, scores
or claimed gains. The 48,031 count is file-footer rows, not independent NFL
forecast observations, verified unique plays, player-games or training examples.

[Exact schema and aggregate acceptance](aggregate.json)

## What ran

The fixed public asset named `ftn_charting_2024.parquet` (asset 288253518) was
retrieved once under this new bounded version, using two HTTP transactions and
563,180 incoming bytes. Its SHA-256 is
`9396c95effac1a81cc30efcf9c4c87ab89855548ae605404318ae949d4356119`.
Full size/hash authentication preceded footer parsing. All nine required fields
have compatible types; every field is nullable. The file reports 48,031 rows
and one row group. No row values, min/max statistics, other field inventory,
player mappings or play-by-play joins were read. Actual season/game coverage
and key uniqueness remain unverified.

| Required field | Actual Arrow type | Nullable |
|---|---|---|
| nflverse_game_id | string | Yes |
| nflverse_play_id | int32 | Yes |
| season | int32 | Yes |
| week | int32 | Yes |
| is_interception_worthy | bool | Yes |
| is_catchable_ball | bool | Yes |
| is_drop | bool | Yes |
| is_throw_away | bool | Yes |
| date_pulled | timestamp[us, tz=UTC] | Yes |

## Preserved failure and technical change

The earlier streaming pilot reached its CPU limit after a partial capture. It
accepted no schema. Its 56.918857 CPU seconds, failure evidence and consumed
4 MiB attempt allowance remain retained. The new version buffered at most
1 MiB in memory and published each response once through the unchanged private
storage writer, reducing repeated quota scans. It retained TLS, proxy/CA,
manual redirect, fixed asset/hash, no-retry and shared 512 MiB CAS checks.

The new invocation used 47.512679 CPU seconds and 34.638283 wall seconds, within
its separately recorded 60 CPU / 60 wall / 256 MiB RSS / 4 MiB attempted
retention allowance. Verified conservative attempted retention is 704,551 bytes,
including the 64 KiB terminal lane. An operator supplied a wrong CLI digest
before launch; the immutable verifier refused it before source activity. Only
the parameter was corrected. No frozen file or check was changed.

Independent acceptance authenticated the final binary and its readonly CAS
inode, the nine-field footer, transaction/accounting records and completed
terminal acknowledgement. Null process counters remain unknown; the retained
source reap record reports return code zero, and the recorded process IDs were
absent at review. A metadata acknowledgement is kept distinct from source or
forecast quality. Fictional software tests add no football evidence.

## Rights, timing and next dependency

Attribution is FTN Data via nflverse. The cached source-specific loader records
CC BY-SA 4.0; its exact document bytes were authenticated. The older document
commit/root association remains unresolved. No public raw-feed redistribution
or operational source-policy activation occurred.

`date_pulled` is a retrieval field, not authenticated original publication time.
No historical issue-time or in-season availability claim follows from this
file. Nullable booleans are not automatically false. The next bounded task is
to qualify the game/play-to-player crosswalk, value and denominator semantics,
coverage and availability lane before a targeted interception-worthy-pass or
catch-quality ablation. Historical reconstructed research remains separate from
genuine pregame capture. No website model or scientific registration changed.
