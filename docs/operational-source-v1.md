# Permitted operational history v1

`nfl_lab.operational_sources` supplies the existing lab's operational reference
methods with a separate permitted history. It reuses the frozen normalizer,
participation qualifier and feature builder. It performs no fitting or scoring.

The policy is `config/operational-source-policy-v1.json`. Its exact file hash,
canonical content hash, adapter/shared transform hashes, original source/receipt
hashes, subset hashes and qualified training-view hash bind each snapshot.
Old source caches and frozen study outputs are never changed.

```python
policy = load_source_policy(policy_path)
receipt = acquire_operational_history(cache, seasons, policy, actual_asof,
    source_cache=prior_cache, allowed_periods={2025: list(range(1, 19)), 2026: [1, 2, 3, 4, 5]})
history = load_operational_history(cache, seasons, policy, actual_asof,
    allowed_periods={2025: list(range(1, 19)), 2026: [1, 2, 3, 4, 5]})
training_features = build_operational_features(history, policy=policy)
query_features = build_operational_features(history, policy=policy, queries=queries)
```

`source_cache` is optional, cache-only adoption of exact whitelisted raw files
whose body, URL, receipt and retrieval clock verify. Without it, acquisition
uses the existing bounded downloader inside a new per-day source namespace;
each allowed URL is reused that UTC day. Neither history nor identity loading
acquires data. All season restrictions must be explicit when `allowed_periods`
is supplied, and restrictions can only narrow calendar eligibility.

Schedule reading selects metadata columns and excludes results. A REG week is
eligible only when its latest scheduled kickoff plus seven days is strictly
earlier than the actual asof clock. These exact season/week filters and REG
predicates enter parquet reads before statistics or roster values decode.
Players contribute only GSIS identity and display name; an unused missing PFR
column exists solely for the unchanged shared loader's schema. No PFR values,
snaps, NGS, news, odds or old processed tables are read.

Snapshots live at `cache/operational-source-v1/<policy hash>/<asof>/<snapshot hash>`.
`sources/` holds immutable copied bodies and their authentic original receipts.
`raw/` holds separate transformed views with `subset-manifest.json`; original
receipts are never relabeled as receipts for derived bytes. Symlinks and any
unexpected derived raw/source artifact fail closed. A failed stage retains a
private `FAILURE.json` and cannot resolve as a completed snapshot. The adapter
enforces the private byte ceiling without deleting earlier evidence.
Each asof currently retains copied bodies and subsets. Repeated versions can
reach that ceiling; acquisition then abstains explicitly. This version does
not claim unbounded retention across seasons or silently delete frozen evidence.

The shared loader's unqualified intermediate stays private in staging and is
replaced by qualified history before publication. Positive finite official
physical action counts or finite signed nonzero production establish playing.
Explicit supported zero and negative yards survive. Missing statistics,
zero-only rows and ACT/INA listings retain unknown participation and rolling
slots. No arbitrary DNP is introduced. Exact website PPR and participation
probability remain unavailable under their incomplete source contracts.

Returned frames carry `attrs['operational_manifest']`. `source_receipts` maps
original filenames to original upstream receipts for grading. Source/history
hashes are separately identified. The feature helper verifies the unchanged
qualified frame, returns all training rows or only the supplied query rows,
blanks query outcomes and records `feature_view_sha256`. Features use strictly
earlier eligible outcomes. Snapshot asof and every original source retrieval
clock must precede or equal a live query cutoff. Source captures during HTTP
acquisition may follow its starting asof clock; this does not backdate their
observation. Future actual-asof requests are rejected.

Loaders normally require the exact request. `latest=True` explicitly enables
read-only grading lookup of the latest matching existing snapshot at or before
the grading clock; `resolve_operational_snapshot` exposes that manifest alone.
For grading, the existing snapshot can contain a superset of requested seasons
or a narrower qualified period. The returned manifest and panel retain the
actual snapshot seasons and effective periods, so absent outcomes remain gaps.
Neither route falls back to the legacy cache. Current receipt time and assumed
historical availability remain distinct: these are current-vintage
reconstructions, never authenticated historical pregame snapshots.

The fictional fixtures cover predicates, protected future rows, REG/POST,
whole-week cutoff, January rollover, zero/missing/signed values, unknown slots,
PPR and participation blocking, identity, immutable restart, receipt/subset
separation, code/view bindings, forbidden files, symlinks and retention.
