# Cached combined yard dependence challenger

Preparation only; no NFL model or table values were opened. The saved leafCDF
class exposes its actual empirical support, normalized histogram, full signed
support prior and forecast-only `predict_batches` interface. Saved point
forecasts alone cannot supply these laws.

The two registered couplings use the same fixed rushing/receiving laws:
independence and one pooled randomized-PIT Gaussian copula correlation shrunk
by n/(n+100). No parameter search or marginal refit is allowed. Earlier2022OOF
labels train2023dependence; earlier2022+2023OOF labels train2024dependence,
subject to strict availability before the first evaluation cutoff.

Each informed RB receives4096 deterministic coherent sum draws. Quantiles
invert the full marginal mixtures, including signed geometric-prior tails.
The empirical sum approximates the underlying copula sum; its exact empirical
CRPS reuses the existing mixture engine. It is not an exact convolution or new
NFL evidence. Sum medians come from the sum distribution. Analytic marginal
means add. Joint log density is unavailable and is never invented or floored.

The complete offered combined population is retained. Non-RB, unavailable and
fallback component laws use the frozen direct combined leafCDF, with explicit
reason counts. RB diagnostics are separate. Direct combinedCDF is the proper
distribution comparator; verified Catmedium is a literal point comparator.
No website-relative, originalR0, prospective or confirmation claim follows.

Both coefficients and four annual forecast factors/draw digests freeze before
any evaluation scoring. Scoring regenerates only identical deterministic draws
and rejects digest changes. This avoids storing raw draws beyond the64MiB cap.
The proposed allocation is900CPU/1200wall,2GiB RSS, two numerical threads,
zero base fits, at most nine retained-model loads and two dependence fits.

The private metadata builder reads only manifests, stat and Parquet footers.
Its inert packet needs independent source/capability review, root/reviewer
registration and manifest seals, exact final closure review and sole rootGO.
The fresh stdlib parent uses the study-local `combined-yard-native-env-f2-v1`
derivative. Its only core change from c57 is adding `VECLIB_MAXIMUM_THREADS=2`
to the six forwarded caps; no general environment forwarding is added. The
original shared c57 and local baseline remain byte-identical to SHA256
`1ef8e8a4109ebc2c098e6f814d72e7aeb17da66cba31d0dfea809d6ac7d751a6`.
The derived helper has its own hash and explicit manifest identity. Source,
masks, clocks, all97features and row/label/finite coverage gates remain.

Synthetic checks cover full signed-tail inverse bounds, exact discrete laws,
coherent/reproducible correlated sums, fixed shrink/fallback, empirical CRPS,
the median-addition counterexample and the entire fictional artifact runner.
F2 also checks all seven caps in a fresh native child, and verifies that removing
VECLIB makes the real worker refuse before creating output. F1 libc refusal
checks remain in place. These software checks establish no football accuracy.
