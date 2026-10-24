"""Closed inference diagnostics: no exception text, paths, rows or model values."""
import json
import hashlib
import os

VERSION = "weekly-inference-diagnostics-v1"
PHASES = frozenset({"PRECHECK", "PLAN_PIN", "PLAN_VALIDATE", "ENVIRONMENT", "RESOURCE_GUARDS", "CODE_PINS",
    "INTERPRETER", "ADAPTER_PLAN", "SAMPLER", "NUMERICAL_IMPORTS", "BACKEND_INIT", "OUTPUT_ADMISSION", "OWNED_AUTH",
    "CATALOG", "SCHEDULE_CLOCKS", "SLATE", "INITIAL_METADATA", "INITIAL_CONSUME", "CHOICE", "MODEL_CENSUS",
    "SOURCE_ADOPTION", "SOURCE_LOAD", "QUERY_BUILD", "FEATURES", "FEATURE_PERSIST", "MODEL_LOAD", "CANDIDATES",
    "SELECTED", "SELECTED_PERSIST", "TERMINAL", "EXPORT_HANDOFF", "COMPLETE"})
ERROR_TYPES = frozenset({"ValueError", "TypeError", "KeyError", "AttributeError", "RuntimeError", "MemoryError", "TimeoutError",
    "OSError", "FileNotFoundError", "PermissionError", "ImportError", "ModuleNotFoundError", "StorageQuotaError", "StorageIntegrityError",
    "StoreError", "PacketGuardError", "JSONDecodeError", "ParserError", "AccountingFailure", "SystemExit", "KeyboardInterrupt"})
GUARDS = {
    "finite additional retained source/query allocation exhausted": "STUDY_RETAINED_BYTES_EXHAUSTED",
    "incoming bytes exceed shared operational quota before write; evidence preserved": "GLOBAL_STORAGE_QUOTA",
    "honest elapsed/remaining kickoff census differs": "ACTUAL_REMAINING_CENSUS",
    "full original fourteen-game schedule required": "ORIGINAL14_SCHEDULE_REQUIRED",
    "sealed recovery metadata differs from actual schedule": "SEALED_RECOVERY_SCHEDULE_MISMATCH",
    "sealed full schedule/clock/slate differs from actual schedule": "SEALED_SLATE_MISMATCH",
    "one-time recovery registration already consumed; no new namespace retry": "RECOVERY_ALREADY_CONSUMED",
    "duplicate authenticated path": "DUPLICATE_AUTHENTICATED_PATH",
    "owned source/artifact binding mismatch": "OWNED_BINDING_MISMATCH",
    "immutable regular owned file required": "IMMUTABLE_OWNED_FILE_REQUIRED",
    "source/inference/persistence deadline elapsed": "INPUT_CUTOFF_EXPIRED",
    "all source/model/catalog bytes must be sealed owned inputs": "OWNED_INPUT_CENSUS",
    "frozen model/procedure/source catalog mismatch": "MODEL_SOURCE_CATALOG_MISMATCH",
    "new initial build/source/fit clocks must actually follow registration": "ORIGINAL_FIT_CLOCKS",
    "fresh initial current-source receipts must follow registration": "ORIGINAL_SOURCE_CLOCKS",
    "missing/stale/future source receipt; use reference/abstention, never relabel cache as fresh": "SOURCE_FRESHNESS",
    "source receipt retrieved after supplied actual asof": "SOURCE_RECEIPT_AFTER_ASOF",
    "source changed during immutable copy": "SOURCE_CHANGED_DURING_ADOPTION",
    "forbidden/unexpected raw artifact before shared normalizer": "RAW_SOURCE_WHITELIST",
    "unchanged physical RSS stop margin": "PHYSICAL_RSS_STOP",
    "finite producer finalization CPU reserve": "CPU_FINALIZATION_RESERVE",
    "whole future producer wall allocation exhausted": "WALL_BUDGET",
    "this source-adoption producer forbids HTTP and children": "NETWORK_OR_CHILD_FORBIDDEN",
    "exact numerical environment required before imports": "NUMERICAL_STARTUP",
    "frozen source changed": "CODE_OR_CONTROL_PIN_CHANGED",
    "PINNED_LIBC_NOT_ALREADY_LOADED": "PINNED_LIBC_NOT_ALREADY_LOADED",
    "WALL_GUARD_REQUIRED": "WALL_GUARD_REQUIRED",
}
_phase = "PRECHECK"


def checkpoint(phase):
    global _phase
    if type(phase) is not str or phase not in PHASES:
        raise ValueError("UNREGISTERED_INFERENCE_DIAGNOSTIC_PHASE")
    _phase = phase
    print(json.dumps(dict(schema_version=VERSION, state="INFERENCE_CHECKPOINT", phase=phase), sort_keys=True), flush=True)


def safe_failure(error=None, *, record=None):
    if record is None:
        name = type(error).__name__
        reason = str(error) if error is not None else ""
    else:
        name = record.get("type") if type(record) is dict else None
        reason = record.get("reason") if type(record) is dict else None
    return dict(error_type=name if type(name) is str and name in ERROR_TYPES else "UNLISTED_ERROR_TYPE",
        guard_code=GUARDS.get(reason, "UNLISTED_ERROR_CODE") if type(reason) is str else "UNLISTED_ERROR_CODE",
        message_fingerprint=hashlib.sha256(reason.encode()).hexdigest() if type(reason) is str else None)


def summary(*, state="FAILED_RETAINED", error=None, result=None, resources=None):
    record=(result or {}).get("fatal") or (result or {}).get("handoff_failure")
    failure = safe_failure(error) if error is not None else (safe_failure(record=record) if record else None)
    failed_phase=(result or {}).get("safe_diagnostic",{}).get("phase",_phase) if record else _phase
    return dict(schema_version=VERSION, state=state, phase=failed_phase, failure=failure,
        CPU_seconds=(resources or {}).get("CPU_seconds"), wall_seconds=(resources or {}).get("wall_seconds"),
        RSS_bytes=(resources or {}).get("RSS_bytes"), HTTP=0, fits=0, scores=0,
        candidate_rows=(result or {}).get("candidate_capture", {}).get("prediction_rows"),
        selected_rows=(result or {}).get("selected", {}).get("rows"),
        forecast_counters_attestation="TRUSTED_TERMINAL_AGGREGATES" if result and result.get("selected") else "UNKNOWN_NO_TRUSTED_CAPTURE_TERMINAL",
        public_export_authorized=False, private_remote_durability="NOT_ESTABLISHED")


def publish(document):
    """Emit only the closed safe document and its exact step-output binding."""
    import hashlib
    encoded=json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    print(encoded, flush=True)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write("diagnostic_json="+encoded+"\ndiagnostic_sha256="+hashlib.sha256(encoded.encode()).hexdigest()+"\n")
