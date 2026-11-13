# Executed 2023 Backfield-CDF validation

The supported 2023 extension did **not establish a direction or Top-6 upgrade**. One earlier-origin fit used the unchanged recipe and 2019–2022 training. All returned parameters, forecasts and grades were captured and hash-read back.

Requested W1–9 is **PARTIAL: W6–9 only**. The source has no compatible W1–5 boards; these are missing evidence, not zero-selection weeks. The supported full-REG panel is W6–18: 560 offered player-games across 168 games, comprising 402 RB and 158 QB opportunities. Mainline flags and original quote clocks are unverified.

| Product | Actual weeks | Own Over W–L | Own Under W–L | Combined | Selected / board |
|---|---|---:|---:|---:|---:|
| Backfield P2 Top-6, early | 6–9 | N/A | 12–12 | 12–12, 50.00% | 24 / 155 |
| Backfield P2 Top-6, supported REG | 6–18 | 3–4 | 32–39 | 35–43, 44.87% | 78 / 560 |
| Raw baseline CDF P2, own Top-6 | 6–18 | 3–6 | 32–37 | 35–43, 44.87% | 78 / 560 |
| Backfield P2, full board | 6–18 | 80–73 | 209–196 | 289–269, 51.79% | 560 / 560 |
| Raw baseline CDF P2, full board | 6–18 | 76–64 | 218–200 | 294–264, 52.69% | 560 / 560 |

Full-board results retain two unknown-participation outcomes. The candidate made no fallback forecasts in this panel. W16 and W18 each lost 1–5. On its selected cases, the candidate's sides equal the original CDF mean/median sides. Same-case constant controls scored 42–36 Always-Over and 36–42 Always-Under. No side inversion or threshold change was applied.

Mean MAE decreased from 3.73677 to 3.70212 carries on the same 558 supported offered cases; this small numerical effect does not establish an O/U improvement. Selected probability quality was poor: Brier 0.37769 and log loss 1.04664. Historical hit rates are not per-pick confidence.

The retained `F_probability` product masks one price-unqualified row despite finite raw law probabilities. Its original scores remain preserved. The separately named `F_RAW_LAW_P2_V1` control uses the registered raw Under/Over rule; its Top-6 membership is unchanged. Its complete full-board sides equal the baseline CDF median. Candidate minus raw-baseline wins is −5; the paired week interval includes zero.

Disposition: close this exact recipe as an unsupported direction/Top-6 upgrade; retain the small numerical effect as inconclusive research evidence. No new primary product, current-query handoff or website activation is justified here.

The independent review reproduced the earliest supported W6 membership and Under 2–4 record, checked all 41 probability rows, and verified representative raw statistics, known zero and unknown states. Source-presence validation confirmed 3,554 explicit raw zero labels and no unsupported zero fills. New-model first-30 imputation values, role/global priors and training counts matched the original baseline.

Receipts: `RUSH2023_COMPLETE_V1.json`, `RUSH2023_HISTORICAL_RESULTS_V1.json.gz`, and `RUSH2023_RAW_F_CONTROL_APPENDIX_V1.json.gz`. Private model, forecast and grade capsule hashes are recorded there. Main execution used one fit, 156.31 CPU seconds, 155.57 wall seconds and 594.6 MB peak RSS; the append-only control clarification used 0.972 CPU seconds and no fit, model load, forecast or private write. This is exposed, current-vintage, seven-day reconstructed evidence, not original pregame issuance, authenticated weekly-board timing, venue settlement or live-site verification.
