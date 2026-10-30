"""Metadata-only release audit; never imports NFL/model or inference libraries.

The original-manifest directory is supplied by the approved private route. Its
JSON is projected to public-safe identities; private paths and fitted bytes are
never exported. No source or forecast value, model file, or outcome is read.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import time

TARGETS = ("pass_yd", "pass_td", "pass_cmp", "pass_att", "pass_int", "rush_yd",
           "rush_att", "rec", "rec_yd", "rush_rec_yd")
PUBLIC_SOURCES = (
    "docs/NEXT_CHECKPOINT_MEDIAN_POLICY_V2_CONSUMER.md",
    "config/next-checkpoint-median-policy-v2.json",
    "config/weekly-catalog-contract-v1.json",
    "nfl_lab/next_checkpoint_median_policy_v2.py",
    "nfl_lab/next_checkpoint_median_policy_v2_view.py",
    "nfl_lab/weekly_future_inference.py",
    "nfl_lab/weekly_generic_producer.py",
    "nfl_lab/weekly_private_selected.py",
    "nfl_lab/weekly_public_feed.py",
    "reports/next-nfl-checkpoint-20261028/NEXT_CURRENT_MAE_DECISION_V2.json",
    "reports/category-topfive-20261029/public/POINT_POLICY_DECISIONS.json",
    "reports/next-nfl-checkpoint-20261028/LOWEST_PRODUCTION_OWNER_CATALOG_DRAFT_V1.json",
    "reports/category-topfive-continuation-20261029/public/OWNER_ACTIONS.json",
    "reports/category-topfive-20261029/runtime/RUNTIME_CATEGORY_CENSUS_TECHNICAL_V2_RESULT.json",
    "reports/opportunity-four/CURRENT_DECISIONS.json",
    "reports/opportunity-four/over-under/runtime/FINAL_RUNTIME_DELTA_V3.json",
    "reports/next-nfl-median-policy-v2-20261028/SOFTWARE_V1/SOFTWARE_COMPLETE.json",
)


def read(path):
    body = path.read_bytes()
    return json.loads(body), {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--public-root", required=True, type=Path)
    cli.add_argument("--original-manifest-root", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    cpu, wall = time.process_time(), time.monotonic()
    root = args.public_root
    docs, pins = {}, {}
    for rel in PUBLIC_SOURCES:
        docs[rel], pins[rel] = read(root / rel) if rel.endswith(".json") else (None, {
            "bytes": (root / rel).stat().st_size,
            "sha256": hashlib.sha256((root / rel).read_bytes()).hexdigest()})
    config = docs["config/next-checkpoint-median-policy-v2.json"]
    configs = {r["target"]: r for r in config["categories"]}
    initial = {r["target"]: r for r in docs[
        "reports/next-nfl-checkpoint-20261028/NEXT_CURRENT_MAE_DECISION_V2.json"]["categories"]}
    latest = {r["category"]: r for r in docs["reports/opportunity-four/CURRENT_DECISIONS.json"]["rows"]}
    census = docs["reports/category-topfive-20261029/runtime/RUNTIME_CATEGORY_CENSUS_TECHNICAL_V2_RESULT.json"]
    live = {r["category"]: r for r in census["by_category_method_product"]}
    draft = {r["category"]: r for r in docs[
        "reports/next-nfl-checkpoint-20261028/LOWEST_PRODUCTION_OWNER_CATALOG_DRAFT_V1.json"]["rows"]}
    rows = []
    for target in TARGETS:
        source, metadata = read(args.original_manifest_root / target / "leaf_cdf_base" / "future-inference.json")
        expected = configs[target]["cdf_basis_original_future_manifest_version"]
        if metadata["sha256"] != expected or source["category"]["target"] != target:
            raise ValueError("Original metadata differs from prepared V2 context; preserve and investigate")
        basis = initial[target]
        if basis["leader"]["method"] != "CDF_MEDIAN":
            raise ValueError("Unexpected original core-CDF point context; no inferred score")
        research = latest.get(target, {}).get("best_observed")
        row = {
            "target": target,
            "support": source["category"]["support"],
            "modeled_roles_original_manifest": source["category"]["modeled_roles"],
            "core_candidate": {
                "base_learner_id": "LAB_CDF", "family": "leaf_cdf_base",
                "selection_product": "stat_point_mae_v2", "selection_metric": "MAE",
                "forecast_product": "point_median", "prediction_functional": "full_cdf_lower_median",
                "display_label": "Selected median", "separate_expected_mean": "law.mean; unchanged mean contract",
                "new_procedure_version": None,
                "new_procedure_reason": "Retained owner must freeze exact adapter/model/source/output binding before values",
                "original_manifest": metadata,
                "original_manifest_is_current_restored_wrapper": False,
                "original_procedure_version": source["procedure_version"],
                "manifest_declared_model_member": {
                    "member_name": "trained.joblib", "bytes": source["model"]["bytes"],
                    "sha256": source["model"]["sha256"],
                    "verification": "JSON_DECLARED_ONLY_MODEL_BYTES_NOT_READ_OR_LOADED_THIS_AUDIT"},
                "source_contract": source["source_contract"],
                "trained_code_pins": source["code_pins"], "trained_environment": source["environment"],
                "feature_names": source["features"],
                "training_cutoff_utc": source["training_cutoff_utc"],
                "training_max_available_utc": source["training_max_available_utc"],
                "training_frame_sha256": source["training_frame_sha256"],
                "fit_receipt": source["fit_receipt"],
                "replay_fixture_sha256": source["replay_fixture_sha256"],
                "legacy_point_replay_bits_sha256": source["replay_bits_sha256"],
                "stored_law_kind": source["probability_law"],
                "model_fallback": source["fallback"],
                "current_restored_wrapper_sha256": None,
                "current_wrapper_reason": "OWNER_AUTHENTICATION_REQUIRED; original metadata is not current restore proof",
                "status": "PREPARED_NOT_OPERATIONALLY_ADMITTED_AS_STAT_POINT_MAE_V2",
            },
            "reused_core_evidence": {
                "evidence": "2026_REG_W1_6_current_vintage_reconstruction_exposed_development",
                "method": basis["leader"]["method"], "MAE": basis["leader"]["metrics"]["MAE"],
                "coverage": {k: basis["leader"]["metrics"][k] for k in
                    ("planned", "scored", "games", "weeks", "played_missing", "played_zero", "outcome_states")},
                "diagnostics": {k: basis["leader"]["metrics"][k] for k in ("MSE", "RMSE", "bias", "p90_AE", "p95_AE")},
                "lab_comparator": {"method": basis["lab_comparator"]["method"],
                    "MAE": basis["lab_comparator"]["metrics"]["MAE"]},
                "matched_current_website_loss": None,
                "matched_current_website_loss_reason": "Authentic matching historical current-site forecasts absent in this panel",
                "uncertainty": "Retain original linked study intervals; none newly calculated in this metadata audit",
                "new_fits_forecasts_or_scoring": 0,
            },
            "latest_focus_research_leader": research,
            "core_is_latest_research_leader": research is None or research["method_id"] in {
                "m:LEAF_CDF", "m:CDF_H4_HISTORICAL_RELATION_CURRENT_STATE"},
            "latest_research_leader_note": "Ordered/backfield/timestamped-depth are separately bound procedures; core admission does not install them",
            "actual_prior_display_snapshot": {
                **{k: live[target][k] for k in ("method_id", "model_version", "procedure_version", "product", "prediction_functional", "rows")},
                "family": draft[target]["selected_families"],
                "observed_at_UTC": census["observed_at_UTC"],
                "payload_sha256": census["source_sha256"], "not_a_current_network_read": True,
                "on_new_product_failure": "Retain this original typed contract/identity or actual later legitimate incumbent; do not label it median",
            },
            "operational_gates": {k: {"state": "UNVERIFIED_FOR_NEW_PRODUCT", "owner": owner}
                for k, owner in (
                    ("current_source_and_artifact_bindings", "retained producer owner"),
                    ("future_inference_and_new_median_replay", "research prepares bounded validation; retained producer owns current execution"),
                    ("durable_capture_restore", "retained producer owner in approved Actions/GO environment"),
                    ("typed_catalog_epoch_export_scope", "retained research/producer integrator plus website owner"),
                    ("consumer_fallback_rollback", "retained website production owner"),
                    ("retained_owner_admission", "retained producer and website production owner"),
                    ("genuine_capture_and_served_value_readback", "retained producer issues; read-only researcher may verify publication"))},
        }
        rows.append(row)
    receipt = {
        "schema_version": "mae-core-release-metadata-audit-v1", "state": "PREPARED_BINDINGS_AND_GATES_NOT_ADMISSION",
        "started_at_UTC": started, "completed_at_UTC": datetime.now(timezone.utc).isoformat(),
        "authority": "category-topfive-mae-release-priority-v1; existing core product integration, not new nonfocus predictive research",
        "public_sources": pins, "rows": rows,
        "all_ten_original_manifest_metadata_match_prepared_config": True,
        "model_member_hashes_are_manifest_claims_not_fresh_model_byte_verification": True,
        "missing_current_owner_wrapper_map_is_not_proof_original_models_are_missing": True,
        "unchanged_products": ["separate expected means", "full original laws", "anytime-TD Brier stream", "prop probability/EV ranking", "historical picks"],
        "separate_admissions": {"ordered_backfield_depth": "not installed by base-core admission", "nick-chart-ppr-v1": "separate owner package and source/consumer gates", "rec_tgt": "separate forecast-only product; no incumbent in legacy site"},
        "resource_scope": {"CPU_seconds_generator_only": time.process_time()-cpu,
            "wall_seconds_generator_only": time.monotonic()-wall,
            "RSS_bytes_generator_peak": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            "fits": 0, "model_files_read_or_loaded": 0, "NFL_numeric_decodes": 0,
            "new_forecasts": 0, "new_scores": 0, "software_test_invocations": 0, "HTTP": 0,
            "CAS": 0, "website_writes": 0, "canonical_registry_writes": 0},
        "publication_state": "RESULT_SAVED_PUBLICATION_PENDING",
        "private_route": "Existing approved owner-controlled restoration; no private destination published",
    }
    body = (json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()
    if len(body) > 98304:
        raise ValueError("metadata-only manifest exceeds its finite output cap")
    if b"/workspace" in body or b"/tmp/" in body:
        raise ValueError("private absolute path leaked into public projection")
    with args.output.open("xb") as out:
        out.write(body)
    print(json.dumps({"state": receipt["state"], "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
        "original_manifest_count": len(rows), "new_fits_forecasts_scores": 0}))


if __name__ == "__main__":
    main()
