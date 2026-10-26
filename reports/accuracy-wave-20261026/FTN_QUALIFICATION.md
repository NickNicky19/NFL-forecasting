# FTN 2022/2023 actual values and joins — October 26, 2026

This is an **executed source qualification**, not a forecasting-accuracy experiment. It used retained FTN charting and PBP projections, the independent saved schedule and retained model-history identity columns. **Zero HTTP, fits, model inference, accuracy comparisons or new features.** The completed 2024 census was reused as context and was not rerun.

Attribution: FTN Data via nflverse (retained CC-BY-SA-4.0 declaration); PBP via nflverse/nflfastR (separate retained CC-BY-4.0 declaration and underlying rights). Restricted raw feeds remain private.

## Actual coverage

|Season|FTN rows|PBP rows|Scheduled REG games|Matched context-qualified play keys|FTN only|PBP only|
|---|---:|---:|---:|---:|---:|---:|
|2022|41,643|47,157|271|39,742|0|4,816|
|2023|48,225|47,399|272|44,061|1,964|816|

Both sources represent every game in their independent scheduled REG frame. This is not proof every relevant play or player is complete. Raw key duplicates and invalid key rows were zero in both sources. Context quarantine retains **1,901/2,200** FTN rows outside the saved REG calendar and **2,599/2,522** PBP REG/team-context conflicts. Their causes are not guessed or silently repaired.

The year-aware wrapper reuses the exact frozen 2024 F1 integer/key, team-alias, source-attempt, nonspike-risk and receiver-event predicates. Raw duplicate membership is decided before filtering; no first-row deduplication, fuzzy identity or implicit null-to-false conversion occurs.

## Actual charting values on declared denominators

|Season|Interception-worthy true / source risk opportunities|Catchable true / source receiver events|Drops true / same receiver events|Throwaways true / source risk opportunities|
|---|---:|---:|---:|---:|
|2022|928 / 17,783|13,389 / 17,121|674 / 17,121|658 / 17,783|
|2023|723 / 18,007|12,924 / 17,298|696 / 17,298|707 / 18,007|

All four selected flags were actual booleans with **zero null or invalid values** in these two raw files. Every qualified denominator opportunity had a charted known flag. Those are observed counts, not filled zeros or a rule that missing charting means false.

The independent PBP frame also retains **1,047/1,068** unknown source-defined true-attempt states; risk has **1,046/1,068** unknowns and receiver-event eligibility **1,708/1,777**. Missing, penalty, disposition and context uncertainty remain outside the known denominator. This conservative source-defined denominator has **not** earned equivalence to official attempts, credited targets or nullified-play settlement.

Raw-file frequencies, denominator-specific frequencies and uncharted/unmatched coverage remain different quantities. These rates are descriptive charting statistics, not player interception probabilities or evidence that adding the fields improves predictions.

## Player identity compatibility

On context-qualified PBP rows with a publisher GSIS-formatted passer ID, **19,445/19,455** (2022) and **19,800/19,807** (2023) match the retained same-season/week/game/team model-history identity panel. Receiver matches are **17,381/17,391** and **17,549/17,558**. Seven unmatched passer IDs and seven/nine unmatched receiver IDs remain unresolved by season; no names are guessed.

This checks actual join compatibility. It does not reproduce the publisher release's conversion/lookup build, independently certify all canonical GSIS membership, or establish a complete played-zero population. Null passer/receiver fields on other play types are retained separately, not classified as missing QB participation. Non-QB passing and receiver positions remain visible in aggregate role counts.

## Timing: a concrete limit

For the retained 2022 file, `date_pulled` ranges **September 6–October 10, 2024**. For 2023, every retained value is **September 6, 2024**. All valid REG values follow the games, and all precede their recorded October 25, 2026 first local captures. The first-observed freeze's year, byte count, local hash, path and capture clock were authenticated.

**These are refresh/capture records, not original publication times.** Local byte hashes provide replay identity; the original upstream checksum for these two first-observed assets remains unavailable. This packet neither invents 48-hour historical availability nor permits retrospective charting to masquerade as archived in-season information.

## Result and next use

The retained values, source-defined denominators and matched-player facts are now measured. Official ID-build, target/attempt/nullification equivalence and original-publication gates remain unqualified; source policy and production were not changed. A later feature study must declare its exact compatible subset, unknown-feature fallback and current-vintage reconstruction lane, and compare all candidate/control forecasts on the same offered population. No fit or accuracy gain is supplied here.

The actual worker used **19.373 CPU / 19.268 wall seconds**, peak RSS **278,126,592 bytes**, within 45 CPU / 90 wall / 384 MiB. The compressed proof is **2,573 bytes**; all new retained artifacts total **2,821 bytes**, below the unchanged **8,192-byte** allocation and shared 512 MiB cap. No evidence was deleted. Proof SHA-256: `e78a64fecba954ee6e918e1eccd570f05a0d6088d2c844226121742e4d000e50`.

Independent post-execution review: **PASS**. The separate reviewer decoded each retained asset once and reproduced all value, key/context, flag-denominator, player-compatibility, timestamp and missing-game counts. Exact source/code/CAS identities and the 2,821-byte retained total passed. Review added no accuracy experiment or football observation. [Aggregate proof and all counts](FTN_AGGREGATES.json). Public outputs contain no raw feed, player/game/play keys, row-level data, fitted artifact or private path.
