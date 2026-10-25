# Report continuation V2: retained actual failure

The zero-fit reporting continuation failed at the private paired-loss write because its fixed 16 MiB new-retention admission rejected the next body. The supervisor did not stop it for CPU, memory or wall time. This does not change the original correction study’s separate CPU-limit failure.

The completed reports and frozen forecasts/outcomes remain retained. No model was refitted, no forecast was regenerated, no outcome joined, and no source acquired by this reporting pass. The continuation took 113.859 wall seconds and 134.843 CPU seconds; sampled combined peak RSS was 634,159,104 bytes. Charged new CAS bytes at termination were 16,054,118 of 16,777,216; an attempted next body was rejected before write.

The original V2 invocation is consumed and remains FAILED. A separate completion requires an inventory of exact surviving artifacts and its own finite registration, preserving all completed bytes and scientific rules.

[Actual receipts](baseline-correction-report-v2/failed-run/)
