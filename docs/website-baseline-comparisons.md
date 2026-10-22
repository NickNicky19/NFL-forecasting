# Website comparisons and prospective source bindings

The lab has a new matched retrospective comparison in
`reports/archive-lab-week6-v1/`. It reuses actual archived website and
site-extracted Sleeper points. It is one already-exposed week, with
current-vintage reconstructed inputs; it establishes no future advantage.
All methods, coverage losses and protocol deviations remain visible.

## Future comparisons in the existing daily workflow

`config/website-baseline-v1.json` registers the forward comparison protocol.
`nfl_lab.website_baselines` reads the website's current GitHub commit, complete
source tree, board and matching metadata. The seven engine blob identities must
match the pinned original website engine. Data bytes must match the immutable
commit's blob IDs and SHA-256 receipts. A changed engine requires another
registered comparison version. This lab never invokes or edits the website.

The website snapshot must be observed before a **new lab forecast's original
feature cutoff**, be no more than 120 minutes old at that cutoff, and agree with
the independent NFL schedule, player ID, position, team, opponent and kickoff.
Only rows in that intake's newly persisted lab batch may acquire a comparator.
Later retries cannot attach a fresh website point to an earlier frozen lab
forecast. Unsupported website inputs never stop the football forecast pipeline.

The public `lab-state` branch stores only identities, source/point digests,
immutable GitHub references, original lab-row digests and clocks. It does not
copy numeric provider/website points or raw source bodies. Separate completion
and verified remote-readback receipts must both precede kickoff, for the lab
forecast and its comparator binding. Hash references do not guarantee upstream
retention: later grading must recover and reverify the exact same immutable
source bytes, code manifest and point digests or abstain.

`raw_sleeper` means the literal rounded `prop.proj` extracted by the website;
it is not the full-precision original provider feed. `pinned_website` means the
literal `prop.adj`, including its separately marked historical-average fallback.
A missing raw projection never becomes zero. Anytime TD uses only an explicit
website `td_chance` with a finite nonnegative expected-count input; the count
itself is not a probability. No native raw Sleeper TD probability is invented.
PPR website display points do not authenticate missing exact PPR outcomes.

Replay grades both forecasts on identical resolved player/game/target outcomes.
Unknown participation, known DNP, missing statistics and disputed identities stay
separate. Scalar baselines get point metrics; actual TD probabilities can receive
Brier/log scores and calibration summaries. Paired game and week diagnostics use
the common evaluator, a bounded 500-replicate bootstrap and a conservative
240-comparison family. Adaptive repeated looks and finite-bootstrap tails remain
exploratory; these comparisons do not automatically promote any model.

Sources are cached once per immutable version within a workspace. Grading
deduplicates recovery of a source within the run, limits new recovery launches
to 120 seconds/128 snapshots and bounds source JSON reads to 512 MiB, including
failed validation attempts. Cached failures count toward the attempt limit.
Existing HTTP timeouts/retries and the workflow job limit still apply. Budget
skips are explicit and cannot masquerade as full coverage. Private derived row
files have a 256 MiB cap including incoming serialized bytes; evidence is not deleted to fit a new
run. The durable derived-state cap remains 200 MiB.

The initial 24,288 forecasts predate this protocol and receive no retroactive
website binding. The source intake report records a real, fresh read-only
website snapshot; preparation alone is not a qualified paired capture.
