"""Private metadata/plan builder; never load football rows or run models.

``--write-audits`` creates the two private source metadata records. The separate
``--write-plan`` action is reserved for an explicit integrator request after the
implementation is available. Every output is atomic and create-only. No seal,
campaign launch, outcome parsing, fitting, prediction, scoring or ledger write
is implemented here.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


PARENT_ROOT = Path("/workspace/website-methods-research/resumed/median-boosting-20261023")
PARENT_REGISTRY = PARENT_ROOT / "SEALED_REGISTRY.json"
PARENT_SHA256 = "49ea230f4a54e523faed757f77239c17e1829c7ed7350d8b44f2025c425a9256"
FREEZE_SHA256 = "507d07c5dfb0dc130d631fe3c70baf99949e7e6e272ea420e24aef029837c424"
DEFAULT_ROOT = Path("/workspace/nfl-methods-integration")
DEFAULT_PACKET = Path("/workspace/website-methods-research/resumed/role-count-20261023")
PERIODS = ["2022", "2023", "2024", "website_week6"]
COUNT_TARGETS = ["pass_td", "pass_cmp", "pass_att", "pass_int", "rush_att", "rec"]


def digest(path: Path) -> str:
    """Opaque-byte digest only; never interpret forecast or outcome values."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bind(path: Path) -> dict:
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def canonical_sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def atomic_create_json(destination: Path, value) -> dict:
    """Publish complete JSON without replacing an existing destination."""
    body = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name("." + destination.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return bind(destination)


def load_parent() -> tuple[dict, dict]:
    if digest(PARENT_REGISTRY) != PARENT_SHA256:
        raise ValueError("parent sealed registry bytes changed")
    parent = json.loads(PARENT_REGISTRY.read_text())
    freeze_path = PARENT_ROOT / "RUN_01/forecast-freeze.json"
    if digest(freeze_path) != FREEZE_SHA256:
        raise ValueError("parent global forecast freeze bytes changed")
    freeze = json.loads(freeze_path.read_text())
    if parent["state"] != "SEALED_ROOT_AND_REVIEWER":
        raise ValueError("parent must remain sealed")
    if parent["periods"] != PERIODS or len(parent["categories"]) != 12:
        raise ValueError("parent periods/category slots changed")
    if sum(x["state"] == "READY" for x in parent["categories"].values()) != 11:
        raise ValueError("eleven supported targets and blocked exact PPR required")
    return parent, freeze


def old_base_forecasts(parent: dict, freeze: dict) -> dict:
    result = {}
    for target, category in parent["categories"].items():
        if category["state"] != "READY":
            continue
        result[target] = {}
        for period in PERIODS:
            relative = f"trials/{target}/base/{period}/candidate-frozen.parquet"
            path = PARENT_ROOT / "RUN_01" / relative
            # The point bytes were checked in the initial read-only preflight.
            # Rebinding forecasts is metadata work and reads no outcome labels.
            binding = bind(path)
            if binding["sha256"] != freeze["bindings"][relative]:
                raise ValueError("parent base forecast differs from global freeze: " + relative)
            result[target][period] = binding
    if sum(len(x) for x in result.values()) != 44:
        raise ValueError("exactly 44 old base forecast bindings required")
    return result


def source_metadata(parent: dict, freeze: dict, integration_root: Path) -> tuple[dict, dict]:
    proof_path = PARENT_ROOT / "permitted-source/source-proof.json"
    proof = json.loads(proof_path.read_text())
    outcome_proof_path = PARENT_ROOT / "CLEAN_OUTCOME_PROOF_V2.json"
    outcome_proof = json.loads(outcome_proof_path.read_text())
    bridge_path = integration_root / "reports/source-policy-20261023/ppr-w6-positive-bridge.json"
    bridge = json.loads(bridge_path.read_text())
    ppr_prior_path = Path("/workspace/website-methods-research/resumed/all-categories-20261023/categories/fantasy_ppr/source-contract-result.json")
    ppr_prior = json.loads(ppr_prior_path.read_text())
    old_base = old_base_forecasts(parent, freeze)
    controls = [b for target in parent["saved_controls"].values() for panel in target.values()
                for period in panel.values() for b in period.values()]
    source = {
        "version": "role-count-reused-source-audit-v1-20261023",
        "state": "EXISTING_PACKET_METADATA_ONLY_NO_NEW_NUMERIC_EXECUTION",
        "parent_boosting_registry": bind(PARENT_REGISTRY),
        "parent_forecast_freeze": bind(PARENT_ROOT / "RUN_01/forecast-freeze.json"),
        "source_contract": copy.deepcopy(parent["source_contract"]),
        "inputs": copy.deepcopy(parent["inputs"]),
        "source_proof": bind(proof_path), "clean_outcome_proof": bind(outcome_proof_path),
        "study_source_relation": "Exactly the parent HGB NFL-only training/query/outcome packet; source constant for new learner comparisons against old HGB. Older CDF/recent/pooled comparator source differences still use the retained strict quarantine evaluator.",
        "no_new_data_pipeline": True,
        "no_new_acquisition": True, "no_new_outcome_values_read": True,
        "new_models_predictions_scores": 0,
        "historical": {
            "rows": proof["training_rows"], "seasons": proof["training_seasons"],
            "participation": proof["training_participation"],
            "annual_evaluation": {
                "2022": {"training_rows": 26488, "offered_rows": 9108, "played": 6112, "unknown": 2996},
                "2023": {"training_rows": 35596, "offered_rows": 9020, "played": 6090, "unknown": 2930},
                "2024": {"training_rows": 44616, "offered_rows": 9000, "played": 6125, "unknown": 2875}},
            "annual_counts_authority": "Existing parent training-gate JSON plus initial read-only source preflight; not new scoring.",
            "schema_observed_in_initial_preflight": {"rows": 62746, "columns": 142, "numeric_feature_columns": 97},
            "per_year_features": "No separate clean files: shared load_prediction_inputs filters the one bound feature file and projects identity/context/clocks/f_* at Parquet read, excluding evaluation labels."},
        "week6": {
            "contexts": proof["query_rows"], "original_offers": proof["all_original_offers"],
            "exact_gsis_bindings": proof["exact_gsis_bindings"], "cold_contexts": proof["unlinked_cold"],
            "prior_source_weeks": proof["query_prior_weeks"],
            "query_schema_observed_in_initial_preflight": {"rows": 396, "columns": 116, "numeric_feature_columns": 97},
            "outcome_rows": outcome_proof["original_rows"], "qualified_rows": outcome_proof["qualified_rows"],
            "by_target": outcome_proof["by_target"],
            "original_cutoff": "2026-10-18T10:48:59+00:00"},
        "category_contracts": {
            target: {"unchanged_parent_subtree_sha256": canonical_sha256(category),
                     "state": category["state"], "modeled_roles": category["modeled_roles"],
                     "primary_roles": category["primary_roles"]}
            for target, category in parent["categories"].items()},
        "category_contract_sha256_encoding": "UTF-8 json.dumps(sort_keys=True,separators=(',',':'),allow_nan=False)",
        "old_base_forecasts": old_base,
        "retained_saved_controls": {"bindings": len(controls), "canonical_bindings_sha256": canonical_sha256(parent["saved_controls"]),
                                    "authority": "Parent saved_controls contains every exact path/hash; all 220 matched initial read-only preflight."},
        "initial_preflight_hash_audit": {"inputs": 4, "saved_controls": 220, "old_HGB_base_forecasts": 44, "mismatches": 0},
        "source_qualification": copy.deepcopy(parent["source_qualification"]),
        "qualification": "Positive attributed NFL physical events establish played. Row existence, ACT/INA, penalties and zero-only rows do not establish appearance or DNP. Unknown slots, explicit played zeros, played missing statistics and all original offers remain intact. Snap feature means are missing and counts zero; no PFR snap input or derived participation is permitted.",
        "timing": "All 2019-2025 and 2026 W6 are exposed. Current-vintage reconstruction and assumed seven-day historical availability; no authenticated original publication or correction order. W6 features use W1-5 only; outcomes remain separately bound W6 REG. No W7+ values are read.",
    }
    ppr = {
        "version": "role-count-exact-ppr-retained-block-v1-20261023",
        "state": parent["categories"]["fantasy_ppr"]["state"],
        "all_historical_contexts_retained": proof["training_rows"],
        "qualified_historical_labels": 0,
        "all_original_week6_offers_retained": outcome_proof["by_target"]["fantasy_ppr"]["offered"],
        "qualified_week6_labels": outcome_proof["by_target"]["fantasy_ppr"]["qualified"],
        "blocked_new_packages": 8,
        "exact_scoring_contract": copy.deepcopy(parent["categories"]["fantasy_ppr"]["outcome_contract"]),
        "prior_source_contract_result": bind(ppr_prior_path),
        "remaining_rare_credit_gaps": ppr_prior["remaining_gaps"],
        "sparse_zero_contract": ppr_prior["sparse_zero_contract"],
        "already_completed_one_time_W6_bridge": bind(bridge_path),
        "bridge_summary": {"all_original_offers": bridge["planned_original_PPR_opportunities"],
                           "coverage": bridge["coverage"],
                           "qualified_exact_subset_rows": bridge["qualified_exact_subset_rows"],
                           "result": bridge["result"]},
        "decision": "Keep all exact-PPR slots blocked. Positive NFL event agreement does not establish the full provider-credit/omitted-zero contract. No generic fantasy total, missing-to-zero conversion or event-selected subset is allowed.",
        "source_hunt_repeated": False, "new_source_requests": 0,
        "new_outcome_values_read": False, "new_fits_predictions_scores": 0,
    }
    return source, ppr


def load_implementation(integration_root: Path):
    """Load definitions only after explicit plan-creation authorization."""
    sys.path.insert(0, str(integration_root))
    engine = importlib.import_module("nfl_lab.role_boosting")
    campaign = importlib.import_module("nfl_lab.role_boosting_campaign")
    for module, name in [(engine, "role_boosting.py"), (campaign, "role_boosting_campaign.py")]:
        if Path(module.__file__).resolve() != integration_root / "nfl_lab" / name:
            raise ValueError("implementation imported from unexpected worktree")
    if list(campaign.PERIODS) != PERIODS:
        raise ValueError("new implementation periods changed")
    if campaign.LIMITS["maximum_candidate_fit_attempts"] != 136:
        raise ValueError("explicit 136-estimator amendment required")
    return engine, campaign


def build_plan(parent: dict, freeze: dict, integration_root: Path, packet: Path) -> dict:
    engine, campaign = load_implementation(integration_root)
    config_path = integration_root / "config/role-count-research.json"
    config = json.loads(config_path.read_text())
    if config["registration_id"] != engine.VERSION or config["periods"] != PERIODS:
        raise ValueError("root predeclared config and implementation disagree")
    for name in ["SOURCE_AUDIT.json", "EXACT_PPR_BLOCK.json"]:
        if not (packet / "source-owner" / name).is_file():
            raise ValueError("source audit record must precede plan creation")
    plan = copy.deepcopy(parent)
    plan.pop("seal", None)
    plan.update(
        registration_id=engine.VERSION,
        state="FINAL_PLAN_FOR_READ_ONLY_PRECLEAR_NO_REAL_FITS",
        created_at=datetime.now(timezone.utc).isoformat(),
        integration_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=integration_root, text=True).strip(),
        parent_boosting_registry=bind(PARENT_REGISTRY),
        parent_forecast_freeze=bind(PARENT_ROOT / "RUN_01/forecast-freeze.json"),
        old_base_forecasts=old_base_forecasts(parent, freeze),
        model_design=copy.deepcopy(engine.DESIGN), variants=list(engine.VARIANTS),
        periods=list(campaign.PERIODS), budgets=copy.deepcopy(campaign.LIMITS),
        comparisons=copy.deepcopy(campaign.COMPARISONS),
        ensemble_design={"enabled": False, "additional_fits": 0, "weight_search": "none"},
        output_directory=str(packet / "RUN_01"),
        hypothesis=config["hypothesis"],
        study_source_relation="same_exact_parent_hgb_input_packet",
        source_comparison_attribution="Source constant against the parent HGB: same four exact approved NFL-only input bindings. New procedure differences are count Poisson loss/log link versus L1/identity/clamp and role-stratified training/preprocessing. Older CDF/recent/pooled comparisons retain their separate source-change qualification and quarantine. source_packet_mode is solely the inherited old-secondary-control evaluator marker.",
        source_packet_mode="joint_learner_source_reconstruction",
        old_control_source_packet_mode="joint_learner_source_reconstruction",
        panel="base",
        training_design="Reuse unchanged shared chronological loaders: 2022 trains2019-2021;2023 trains2019-2022;2024 trains2019-2023;W6 trains2019-2025 before original earliest cutoff. Keep original modeled roles. Priors use all supported training rows once. B fits separate FixedDesign/imputation and estimator within each original modeled role; singleton passing role aliases A. Minimum60 supported rows,leaf30. All-zero count groups and single-class binary groups use fixed prior without epsilon or pseudolabels. Nonmodeled/cold/unseen roles preserve inherited role/global prior routing.",
        planned_counts={"total_target_variant_period_packages": 96, "new_model_packages": 48,
                        "reused_alias_packages": 40, "blocked_PPR_packages": 8,
                        "maximum_estimator_fit_attempts": 136,
                        "A_count_fit_attempts": 24, "B_skill_role_fit_attempts": 100,
                        "B_binary_role_fit_attempts": 12,
                        "main_primary_contrasts": 48, "ready_main_primary_contrasts": 44,
                        "blocked_main_primary_PPR_contrasts": 4,
                        "new_blends": 0, "new_features": 0, "score_passes": 1},
        cumulative_budget_amendment=copy.deepcopy(config["cumulative_budget_amendment"]),
        primary_contract="Pool historical2022-2024 paired ROWS before losses: each unchanged category.primary_roles versus frozen old HGB base is primary; mandatory all-offered view retained without outcome/usage selection. W6 primary all original offers versus literal original SITE on exact compatible pairs. Numeric pointMAE and genuine anytimeTD Brier. Each CDF/recent/pooled/raw/simple/control comparison reports its own exact eligible cohort and denominator; no transfer of aggregate error or selection of a better variant.",
        uncertainty="500 fixed-seed game/week clustered historical paired bootstrap replicates, nominal95% unadjusted descriptive intervals. All searches/adaptation/exposure disclosed. No W6 interval, significance, familywise qualification, untouched confirmation or promotion claim.",
        secondary_metrics=["MSE", "RMSE", "signed_bias_prediction_minus_actual", "p95_absolute_error", "coverage", "fallback", "binary_log_loss_without_clipping", "binary_reliability"],
        coherence_diagnostics="Descriptive completions-versus-attempt points and direct combined-yard-versus-rush/receiving component points on common compatible triples only. Retain missing components; never create a new summed candidate, sum-gain claim, joint predictive law or inherited combined gain.",
        exposure="All2019-2025 and2026W6 outcomes and prior forecast losses/source coverage are already exposed and inspected. This is adaptive, chronological reconstructed development with postgame current-vintage inputs and assumed7day historical availability, not prospective issuance, verified original-asof evidence or untouched confirmation. Original SITE vintage/revision advantages remain disclosed.",
        operational_semantics="Numeric outputs are point heuristics, not a numeric predictive law or asserted integer-law median/conditional-mean forecast. Genuine binary probabilities retain proper Brier/logloss. All new/aliased forecasts freeze globally before the sole outcome phase. No blends,newfeatures,newcapture,sourcehunt,epsilon,probability clipping or adaptive refits. PPR remains blocked and every offer/unknown/playedzero/missingstat remains in coverage.",
        stopping="One create-only RUN_01; at most136 new estimator attempts across96 packages. Every failed attempt remains consumed; aliases consume no estimator fit. No retry, extension, tuning, alternate source/window/topology or winning-category selection after new errors. Resource caps preserve all unrun/blocked slots and reporting reserve.",
        promotion="No production/default/website change or activation, public raw feed, scheduler/recorder change, source acquisition, keys, paid service or promotion. Preserve original rec-half hash/registration/Weeks7-14, original H3 evidence/missing-runner status/adverse bias, original RB proposal, all prior failures and spent budgets.",
    )
    old_names = [Path(b["path"]).name for b in parent["code_bindings"]]
    code_paths = [integration_root / "nfl_lab" / name for name in old_names]
    code_paths += [integration_root / "nfl_lab/role_boosting.py", integration_root / "nfl_lab/role_boosting_campaign.py",
                   integration_root / "nfl_lab/role_boosting_export.py", integration_root / "nfl_lab/website_cdf_export.py", config_path]
    plan["code_bindings"] = [bind(p) for p in code_paths]
    for binding in parent["code_bindings"]:
        current = next(x for x in plan["code_bindings"] if Path(x["path"]).name == Path(binding["path"]).name)
        if current["sha256"] != binding["sha256"]:
            raise ValueError("retained shared source/model/evaluator code changed: " + current["path"])
    prereqs = {b["path"]: b for b in parent["prerequisite_bindings"]}
    # The later H3 contract legitimately updated dependency declarations.
    # Preserve the parent registry as evidence, but authenticate the manifest
    # actually used by this new study instead of inheriting its stale digest.
    environment_path = integration_root / "pyproject.toml"
    prior_environment = copy.deepcopy(prereqs.get(str(environment_path)))
    prereqs[str(environment_path)] = bind(environment_path)
    plan["environment_manifest_version"] = {
        "prior_study_binding": prior_environment,
        "current_study_binding": copy.deepcopy(prereqs[str(environment_path)]),
        "reason": "Existing H3 point-contract dependency declarations; no package installation or change to frozen parent evidence",
    }
    for path in [Path(__file__).resolve(), PARENT_ROOT / "RUN_01/forecast-freeze.json",
                 packet / "source-owner/SOURCE_AUDIT.json", packet / "source-owner/EXACT_PPR_BLOCK.json"]:
        prereqs[str(path)] = bind(path)
    for name in ["test_role_boosting.py", "test_role_boosting_campaign.py", "test_role_boosting_export.py"]:
        path = integration_root / "tests" / name
        if path.is_file():
            prereqs[str(path)] = bind(path)
    plan["prerequisite_bindings"] = list(prereqs.values())
    plan["source_audit"] = bind(packet / "source-owner/SOURCE_AUDIT.json")
    plan["exact_PPR_block"] = bind(packet / "source-owner/EXACT_PPR_BLOCK.json")
    plan["source_qualification"] = {
        **copy.deepcopy(parent["source_qualification"]),
        "current_study_relation": plan["study_source_relation"],
        "current_study_attribution": plan["source_comparison_attribution"],
        "source_coverage_previously_inspected": True,
        "new_source_requests": 0,
    }
    plan["prior_search_and_exposure"] = {
        **copy.deepcopy(parent["prior_search_and_exposure"]),
        "prior_successful_fit_lower_bound": 632,
        "count_authority": "Integrator predeclared config; audited lower bound, not exact lifetime total.",
        "parent_88_fit_budget_spent": True,
        "budgets": "Prior632 successful-fit lower bound and old88-fit study remain spent; new136 maximum estimator attempts,96 packages48new40aliases8PPRblocked; no blends/features/search or adaptive refits.",
        "source_constant_comparison": plan["source_comparison_attribution"],
    }
    plan["actual_workers"] = {
        "integrator": "/root", "shared_source": "/root/all12_source_owner",
        "shared_model_evaluator": "/root/role_boosting_implementer",
        "preliminary_design_reviewer": "/root/role_study_reviewer",
        "separate_read_only_reviewer": "/root/role_study_final_reviewer",
        "explicit_accepted_worker_spawn_arguments": {"model": "gpt-6.1-sol", "reasoning_effort": "xhigh", "backend_attestation": False},
        "maximum_concurrent_including_root": 4,
        "actual_runtime_model_setting": "Not independently exposed to source builder; no inference from requested settings.",
        "all12_prior_category_owner_contracts": "Retained byte-equivalent JSON subtrees in parent registry; no category contract or primary role changes.",
    }
    if plan["categories"] != parent["categories"] or plan["inputs"] != parent["inputs"]:
        raise ValueError("unchanged category/input packet invariant failed")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integration-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-audits", action="store_true")
    action.add_argument("--write-plan", action="store_true", help="Only after explicit integrator request; does not seal or launch")
    args = parser.parse_args()
    root, packet = args.integration_root.resolve(), args.packet.resolve()
    parent, freeze = load_parent()
    if args.write_audits:
        source, ppr = source_metadata(parent, freeze, root)
        outputs = [atomic_create_json(packet / "source-owner/SOURCE_AUDIT.json", source),
                   atomic_create_json(packet / "source-owner/EXACT_PPR_BLOCK.json", ppr)]
    else:
        outputs = [atomic_create_json(packet / "PLAN_FOR_REVIEW.json", build_plan(parent, freeze, root, packet))]
    print(json.dumps({"outputs": outputs, "new_fits_predictions_scores": 0}, allow_nan=False))


if __name__ == "__main__":
    main()
