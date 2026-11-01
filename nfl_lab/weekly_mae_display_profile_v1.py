"""Stdlib-only RootV5 display source/profile checks; no private/model imports.

Metadata jobs authenticate fixed public source bytes. Numerical admission stays
inside the native runtime helper after unchanged owner/API/source validation.
"""
from pathlib import Path
import hashlib
import json
import re

REVIEWED_MODEL_PINS = {'weekly_future_inference.py': 'd84a4de76737252a910ed01b626e17403290277feb894621e625ae0791ccef42', 'cdf_engine.py': '6a963111f4173a88affe90ca1ce17532cd5eb690a1f28b284e9fa4145eecb214', 'role_boosting.py': '294e7e588215e7b7e98d6f1fb251eed31420921dff9a59e88434913133dbdf93', 'direct_boosters.py': '475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f', 'median_boosting.py': 'c5bf8ef481c05027a2a1d4e1d19764920c0820f0614f60736826c17526e7799d', 'baseline_correction.py': '077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2'}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def sha(body): return hashlib.sha256(body).hexdigest()
def h(value): return type(value) is str and re.fullmatch("[a-f0-9]{64}",value) is not None

def bounded_read(path, limit):
    with Path(path).open("rb") as stream: body=stream.read(limit+1)
    if not 0 < len(body) <= limit: raise ValueError("BOUNDED_PUBLIC_MAE_SOURCE_REQUIRED")
    return body

def file_sha(path): return sha(bounded_read(path,2 << 20))

def strict_json(body):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError("DUPLICATE_JSON_KEY")
            result[key]=value
        return result
    def invalid(_): raise ValueError("NONFINITE_JSON")
    return json.loads(body,object_pairs_hook=pairs,parse_constant=invalid)

ROOT_V5 = "audit-weekly-hosted-v5-root-GO"
REQUEST_V2 = "audit-weekly-runtime-v2-display-request"
REGISTRATION_PATH = "config/weekly-mae-display-core3-v1.json"
TARGETS = ("pass_yd", "pass_int", "rush_rec_yd")
HELPERS = ("nfl_lab/weekly_mae_display_runtime_v1.py", "nfl_lab/weekly_mae_display_profile_v1.py", "nfl_lab/weekly_mae_point_inference_v2_1.py",
           "nfl_lab/stat_point_mae_public_v2_2.py", "nfl_lab/next_checkpoint_median_policy_v2_view.py",
           "nfl_lab/weekly_mae_display_archive_v1.py", "nfl_lab/stat-point-mae-public-v2-2.js", "tools/persist_state.py",
           REGISTRATION_PATH)
CONFIG_KEYS = {"schema_version", "scope", "selection_product", "selection_metric", "targets",
    "source_evidence", "categories", "new_fits", "probability_policy_change", "ranking_policy_change", "public_export_authorized",
    "mae_runtime_pin_profile"}
CHANGED_LEGACY_PATHS = frozenset({
    'nfl_lab/audit_weekly_controller_v1.py',
    'nfl_lab/audit_weekly_archive_v1.py',
    'nfl_lab/audit_weekly_controller_bootstrap_v1.py',
    'nfl_lab/audit_weekly_controller_registration_v1.py',
    'nfl_lab/audit_weekly_delivery_v1.py',
    'nfl_lab/audit_weekly_grade_history_v1.py',
    'nfl_lab/audit_weekly_hosted_v1.py',
    'nfl_lab/audit_weekly_runtime_v1.py',
    'nfl_lab/audit_weekly_template_v1.py',
    'tests/test_audit_weekly_archive_v1.py',
    'tests/test_audit_weekly_controller_bootstrap_v1.py',
    'tests/test_audit_weekly_grade_checkpoint_v1.py',
    'tests/test_audit_weekly_grade_history_v1.py',
    'tests/test_audit_weekly_hosted_v1.py',
    'tools/audit_weekly_archive_v1.py',
    'tools/audit_weekly_runtime_v1.py',
})

CATEGORY_KEYS = {"effective_model_sha256", "effective_base_procedure_version", "effective_transport_manifest_sha256",
    "effective_verified_reader_manifest_sha256", "target", "family", "base_learner_id", "support", "modeled_roles", "public_roles",
    "original_manifest_sha256", "original_model_sha256", "original_procedure_version", "training_frame_sha256",
    "training_cutoff_utc", "training_max_available_utc", "source_contract", "features"}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def pins(source_root):
    return {p: file_sha(Path(source_root)/p) for p in HELPERS}


def validate_metadata(root, source_root):
    require(root.get("schema_version") == ROOT_V5 and set(root.get("mae_helper_pins", {})) == set(HELPERS)
        and all(h(v) for v in root["mae_helper_pins"].values()), "EXACT_ROOT_V5_MAE_HELPER_PINS")
    ref = root["mae_registration"]
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
        and ref["path"] == REGISTRATION_PATH and type(ref["bytes"]) is int and 0 < ref["bytes"] <= 60 << 10
        and ref["sha256"] == root["mae_helper_pins"][REGISTRATION_PATH], "EXACT_PUBLIC_MAE_REGISTRATION_REFERENCE")
    body = bounded_read(Path(source_root)/REGISTRATION_PATH, 60 << 10)
    require(len(body) == ref["bytes"] and sha(body) == ref["sha256"], "EXACT_PUBLIC_MAE_REGISTRATION_BYTES")
    cfg = strict_json(body)
    require(type(cfg) is dict and set(cfg) == CONFIG_KEYS
        and cfg["schema_version"] == "weekly-mae-display-core3-source-registration-v1"
        and cfg["scope"] == "DISPLAY_ONLY_INCUMBENT_RANKING_UNCHANGED"
        and cfg["selection_product"] == "stat_point_mae_v2" and cfg["selection_metric"] == "MAE"
        and cfg["targets"] == list(TARGETS) and cfg["new_fits"] == 0
        and cfg["probability_policy_change"] is cfg["ranking_policy_change"] is cfg["public_export_authorized"] is False,
        "CLOSED_CORE3_DISPLAY_REGISTRATION")
    require([c["target"] for c in cfg["categories"]] == list(TARGETS)
        and all(type(c) is dict and set(c) == CATEGORY_KEYS for c in cfg["categories"]), "EXACT_THREE_CORE_CATEGORIES")
    profile = cfg["mae_runtime_pin_profile"]
    require(type(profile) is dict and set(profile) == {"schema_version", "scope", "reviewed_before_inventory_sha256",
        "reviewed_after_inventory_sha256", "legacy_pin_count", "changed_paths", "model_pins", "extra_traversal_debit"}
        and profile["schema_version"] == "weekly-mae-display-runtime-pin-profile-v1"
        and profile["scope"] == "ROOT_V5_DISPLAY_ONLY_NOT_V1_HISTORY_OVERRIDE"
        and profile["legacy_pin_count"] == len(root["code_pins"]) == 128
        and profile["model_pins"] == REVIEWED_MODEL_PINS
        and set(profile["changed_paths"]) == CHANGED_LEGACY_PATHS
        and sha(canonical(root["code_pins"])) == profile["reviewed_after_inventory_sha256"]
        and profile["extra_traversal_debit"] == dict(per_model_query_rows=2,targets=list(TARGETS),
            total_prediction_row_cap=18000,fits=0), "CLOSED_MAE_ONLY_RUNTIME_PIN_PROFILE")
    before = dict(root["code_pins"])
    for name, delta in profile["changed_paths"].items():
        require(type(delta) is dict and set(delta) == {"before_sha256","after_sha256"}
            and h(delta["before_sha256"]) and h(delta["after_sha256"])
            and delta["before_sha256"] != delta["after_sha256"]
            and root["code_pins"][name] == delta["after_sha256"],
            "EXACT_REVIEWED_MAE_RUNTIME_PIN_DIFFERENCE")
        before[name] = delta["before_sha256"]
    require(sha(canonical(before)) == profile["reviewed_before_inventory_sha256"],
        "UNCHANGED_OTHER_LEGACY_PINS_REQUIRED")
    return cfg



def validate_root_extension(root, source_root):
    """Producer-only fresh actual-byte qualification, never a Parent shortcut."""
    require(type(root.get("code_pins")) is dict and len(REVIEWED_MODEL_PINS)==6
        and all(root["code_pins"].get("nfl_lab/"+name)==digest for name,digest in REVIEWED_MODEL_PINS.items()),
        "EXACT_ORIGINAL_SIX_MODEL_CODE_ROOT_PINS")
    cfg=validate_metadata(root,source_root)
    require(root["mae_helper_pins"]==pins(source_root),"EXACT_ACTUAL_PRODUCER_MAE_HELPER_BYTES")
    for name,delta in cfg["mae_runtime_pin_profile"]["changed_paths"].items():
        require(file_sha(Path(source_root)/name)==delta["after_sha256"],"EXACT_ACTUAL_PRODUCER_MAE_LEGACY_BYTES")
    return cfg


def prior_extension_metadata(root):
    """Shape only, after an independently authenticated native Root preimage.

    This never verifies current source, admits a model, or grants execution.
    The old source/config/helper hashes remain their original commitments.
    """
    require(root.get("schema_version")==ROOT_V5 and type(root.get("mae_helper_pins")) is dict
        and set(root["mae_helper_pins"])==set(HELPERS) and all(h(v) for v in root["mae_helper_pins"].values()),
        "CLOSED_ORIGINAL_MAE_HELPER_COMMITMENTS")
    ref=root.get("mae_registration")
    require(type(ref) is dict and set(ref)=={"path","bytes","sha256"} and ref["path"]==REGISTRATION_PATH
        and type(ref["bytes"]) is int and 0<ref["bytes"]<=60<<10
        and ref["sha256"]==root["mae_helper_pins"][REGISTRATION_PATH],"CLOSED_ORIGINAL_MAE_REGISTRATION_COMMITMENT")
