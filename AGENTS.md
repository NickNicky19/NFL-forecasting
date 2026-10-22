# Lab execution rules

The owner's 2026-10-22 task authorizes implementation, permitted free acquisition,
experiments, merges and free automation only in NickNicky19/NFL-forecasting.
NickNicky19/nicks-expert-nfl-picks is a pinned read-only reference. Never write,
deploy, disable, or alter its scheduling. Do not read ODDS_API_KEY or call paid
services. No new credentials, public raw-feed redistribution, or always-on LLM.

Use one integrator and isolated worktrees. At most four concurrent agents,
including integrator. Category owners share one data contract and evaluator.
A separate reviewer reads only. Actual agent/model settings must be recorded;
do not claim a setting based only on the requested setting.

Only the integrator appends `execution/ledger.jsonl`. Preserve failed trials,
frozen forecasts and evidence. Missing values are not zeros. Distinguish known
DNP, played zero, missing outcome, and unknown participation. No historical
availability claims based on download time. Never label reconstructed history
as prospective evidence. Do not open future confirmation outcomes while tuning.

Run the schema, leakage, scoring, replay and scheduler tests for relevant changes.
Use finite preregistered budgets in config/research.json. No promotions without
the registered evidence gates. A lack of qualified winners is a valid result.
