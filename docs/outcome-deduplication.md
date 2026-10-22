# Outcome receipt deduplication

For observations without a known source publication clock, the grading writer
deduplicates player/game/target/source, participation and actual value, retaining
separate scoring/period bindings where present. Whole-feed and status-body
hashes, retrieval clocks and unrelated finality changes do not create another
unchanged target observation. The first immutable receipt, its source-body hash
and its original observed clock remain intact. Source versions continue to be
recorded in input manifests.

Missing played statistics, supported zero, unknown participation, DNP and
different source origins remain distinct. A later retrieval never establishes
publication or correction order. Different values without authoritative clocks
remain quarantined by the existing outcome resolver.

Authoritative known-clock observations retain the existing full-version rule:
only the same exact version/timestamp (apart from retrieval time) is deduplicated.
This deliberately preserves repeated values, A→B→A reversions and late-arriving
versions such as B(t2) after A(t3). It also retains distinct body versions at the
same known clock. Compressing these rows solely by value could erase ordering
evidence. Their storage still counts toward the existing 200 MiB cap; no mutable
clock index, evidence deletion, budget increase or resolver-rule change is used.
