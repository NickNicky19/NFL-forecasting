"""RootV5-only point capture restore and native-owner public projection.

No model import, network, fit, caller-supplied acceptance callback or new store.
V1 paths/wires stay closed. Every available point byte is archived, while only
complete independently restored categories can supply point-display rows.
"""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zlib

from . import stat_point_mae_public_v2_2 as wire
from . import weekly_mae_display_profile_v1 as metadata

VERSION = "weekly-mae-display-archive-v1"
ROOT_V5 = metadata.ROOT_V5
REQUEST_V2 = "audit-weekly-archive-v2-display-request"
TARGETS = metadata.TARGETS
PREPARED = ("PROFILE_CATALOG.json", "CATALOG_COMPLETION.json")
RUNTIME = frozenset({"CATALOG_BINDING.json", "SOURCE_REGISTRY.json", "FINISHED.json"}
    | {f"{folder}/{target}{suffix}" for target in TARGETS
       for folder, suffix in (("candidates", ".jsonl.gz"),
                              ("candidates", ".jsonl.completion.json"), ("status", ".json"))})
POINT_PREFIX = "public/stat-point-mae-v1"
RECEIPT_VERSION = "weekly-mae-display-public-receipt-v1"
SCOPE = "DISPLAY_ONLY_INCUMBENT_RANKING_UNCHANGED"
MAX_ROWS, MAX_LINE, MAX_INFLATED = 1000, 64 << 10, 16 << 20
ENVELOPE_KEYS = frozenset("schema_version candidate public_identity candidate_sha256 cutoff_utc operational_eligible legacy_ranking_policy_unchanged envelope_sha256".split())
STATUS_KEYS = frozenset("target state failure expected_rows issued_rows persistence traversal_rows_requested traversal_rows_reserved artifact profile_sha256".split())
PROFILE_KEYS = frozenset("schema_version selection_product selection_metric target scoring_target base_learner_id method_id artifact base_procedure_version procedure_version feature_schema_sha256 public_roles registered_at owner_admission_receipt_sha256 adapter_pins".split())
RECEIPT_KEYS = frozenset("schema_version scope state source_sha source_branch run_id run_attempt root_go_sha256 profile_registration_sha256 helper_inventory_sha256 point_policy_sha256 source_policy_sha256 workflow_sha256 jobs archive_index_sha256 archive_files_sha256 reader_witness_sha256 producer_proof_sha256 restorer_proof_sha256 exporter_proofs_sha256 prevalue_catalog_sha256 catalog_completion_sha256 runtime_source_registry_sha256 identity_bridge_sha256 runtime_terminal_sha256 legacy_selected_sha256 legacy_feed_sha256 catalog_sha256 source_registry_sha256 candidates_sha256 captures_sha256 readback_sha256 categories unavailable created_at verified_at persistence_completed_at_upper_bound readback_completed_at fits raw_or_models_public probability_policy_change ranking_policy_change owner_export_receipt_sha256 feed_sha256 feed_bytes rows".split())
_PROFILE = object()


def require(ok, code):
    if not ok:
        raise ValueError(code)


def sha(body): return hashlib.sha256(body).hexdigest()
def digest(value): return wire.candidate_digest(value)
def safe_reason(error, fallback="DISPLAY_CAPTURE_INVALID_RETAINED"):
    text = str(error)
    return text if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", text) else fallback


class DisplayProfile:
    """Checked source metadata, never a serialized public acceptance grant."""
    def __init__(self, root, root_sha256, source_root, key):
        require(key is _PROFILE, "CHECKED_ROOT_V5_DISPLAY_PROFILE_REQUIRED")
        self.root, self.root_sha256, self.source_root = deepcopy(root), root_sha256, Path(source_root)
        self.config = metadata.validate_root_extension(self.root, self.source_root)
        self._config_sha256 = digest(self.config)
        self.verify()

    def __reduce__(self): raise TypeError("DISPLAY_PROFILE_MUST_NOT_BE_SERIALIZED")

    def verify(self):
        require(type(self.root) is dict and digest(self.root) == self.root_sha256
            and self.root.get("approved") is True and self.root.get("schema_version") == ROOT_V5
            and metadata.validate_root_extension(self.root, self.source_root) == self.config
            and digest(self.config) == self._config_sha256,
            "EXACT_SOURCE_BOUND_ROOT_V5_DISPLAY_PROFILE_REQUIRED")


def checked_profile(root, root_sha256, source_root):
    """Called after the existing native Root/Actions authority guard."""
    return DisplayProfile(root, root_sha256, source_root, _PROFILE)


def allowed_runtime_name(name):
    return name.startswith("mae-display/") and (name[12:] in RUNTIME
        or re.fullmatch(r"views/[0-9]{1,2}/projections/[a-f0-9]{64}\.json", name[12:]) is not None)


def point_policy():
    return dict(schema_version=VERSION + "-publication-policy", scope=SCOPE, targets=list(TARGETS),
        feed_schema=wire.FEED, receipt_schema=RECEIPT_VERSION, public_fields=sorted(wire.ROW_KEYS),
        public_receipt_fields=sorted(RECEIPT_KEYS), forecast_product="point_median",prediction_functional="full_cdf_lower_median",
        separate_expected_mean="ORIGINAL_FULL_LAW_EXPECTED_MEAN",
        capture_body_binding="ACTUAL_CATEGORY_JSONL_GZIP_SHA256",capture_receipt_binding="ACTUAL_ORIGINAL_CATEGORY_COMPLETION_SHA256",
        persistence_clock="MAX_LOCAL_COMPLETION_ARCHIVE_INDEX_CREATED_PRODUCER_JOB_COMPLETED_UPPER_BOUND",
        readback_clock="MAX_READER_WITNESS_EXPORTER_RESTORE_PROOF_NATIVE_ACCEPTANCE",unavailable_rule="NO_ELIGIBLE_PUBLIC_ROWS_ONLY",
        public_prefix=POINT_PREFIX, public_destination="lab-state", fits=0,
        probability_policy_change=False, ranking_policy_change=False,
        immutable_atomic_pair=True, complete_category_readback=True,
        persisted_before_original_deadline=True, retained_capture_preserves_original_clocks=True)


def read_bounded(path, cap):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), "DISPLAY_SOURCE_SYMLINK")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_size <= cap,
            "BOUNDED_REGULAR_DISPLAY_FILE_REQUIRED")
        with os.fdopen(fd, "rb", closefd=False) as stream: body = stream.read(cap + 1)
    finally:
        os.close(fd)
    require(len(body) <= cap, "DISPLAY_FILE_BOUND_EXCEEDED")
    return body


def _reader(snapshot, path):
    items = {f["logical_path"]: f for f in snapshot["files"]}
    require(len(items) == len(snapshot["files"]), "UNIQUE_DISPLAY_CAPTURE_CENSUS_REQUIRED")
    def body(name, cap=256 << 10):
        require(name in items, "DISPLAY_REQUIRED_ALIAS_MISSING")
        raw = read_bounded(path(name), cap)
        require(len(raw) == items[name]["bytes"] and sha(raw) == items[name]["sha256"],
            "DISPLAY_ARCHIVED_PHYSICAL_HASH_MISMATCH")
        return raw
    def doc(name, cap=256 << 10): return wire.strict_json(body(name, cap))
    def matches(ref, name):
        return (type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
            and name in items and ref["bytes"] == items[name]["bytes"] and ref["sha256"] == items[name]["sha256"])
    return items, body, doc, matches


def _rows(raw):
    require(0 < len(raw) <= 4 << 20, "BOUNDED_COMPLETE_POINT_GZIP_REQUIRED")
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    plain = inflater.decompress(raw, MAX_INFLATED + 1)
    require(inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail
        and len(plain) <= MAX_INFLATED and plain.endswith(b"\n"), "EXACT_SINGLE_BOUNDED_POINT_GZIP_REQUIRED")
    lines = plain.splitlines(keepends=True)
    require(0 < len(lines) <= MAX_ROWS and all(0 < len(line) <= MAX_LINE and line.endswith(b"\n") for line in lines),
        "COMPLETE_BOUNDED_POINT_ROW_STREAM_REQUIRED")
    return [(wire.strict_json(line), sha(line)) for line in lines]


def inspect_capture(snapshot, path, profile):
    """Pure bounded readback. Invalid optional data grants no capability.

    The summary is deterministic across producer, reader and exporter. Original
    FAILED_RETAINED statuses and all partial bodies remain in the archive.
    """
    require(type(profile) is DisplayProfile, "TYPED_ROOT_V5_DISPLAY_PROFILE_REQUIRED")
    profile.verify()
    items, body, doc, matches = _reader(snapshot, path)
    observed = sorted(n for n in items if n.startswith(("runtime/mae-display/", "prepared/mae-display/")))
    require(all((n.startswith("runtime/") and allowed_runtime_name(n[8:]))
        or n in {"prepared/mae-display/" + p for p in PREPARED} for n in observed),
        "CLOSED_ROOT_V5_DISPLAY_ALIAS_SCOPE")
    summary = dict(schema_version=VERSION + "-validation", root_go_sha256=profile.root_sha256,
        registration_sha256=profile.root["mae_registration"]["sha256"], observed=observed,
        missing=sorted(({"runtime/mae-display/" + n for n in RUNTIME}
            | {"prepared/mae-display/" + n for n in PREPARED}) - set(observed)),
        state="MAE_UNAVAILABLE", reason=None, targets=[], eligible_rows=0, public_export_authorized=False)
    captures = {}
    result = dict(summary=summary, captures=captures)
    try:
        catalog = doc("prepared/mae-display/PROFILE_CATALOG.json")
        completion = doc("prepared/mae-display/CATALOG_COMPLETION.json")
        source = doc("context/source.json", 2 << 20)
        feature = doc("runtime/features.capture.json", 2 << 20)
        choice = doc("runtime/WEEKLY_CHOICE.json", 2 << 20)
        replay = doc("prepared/relocated_replay.json", 2 << 20)
        epoch = doc("context/epoch.json", 2 << 20)
        bridge = doc("runtime/IDENTITY_BRIDGE.json", 2 << 20)
        require(set(catalog) == {"schema_version", "scope", "root_go_sha256", "registration", "prepared", "profiles", "current_values_used", "created_at", "public_export_authorized"}
            and catalog["schema_version"] == "weekly-mae-display-runtime-v1-prevalue-catalog"
            and catalog["scope"] == SCOPE and catalog["root_go_sha256"] == profile.root_sha256
            and catalog["registration"] == profile.root["mae_registration"]
            and matches(catalog["prepared"], "context/prepared.json")
            and catalog["current_values_used"] is catalog["public_export_authorized"] is False
            and set(catalog["profiles"]) == set(TARGETS), "EXACT_PREVALUE_DISPLAY_CATALOG_REQUIRED")
        require(set(completion) == {"schema_version", "catalog", "completed_at", "current_values_used", "root_go_sha256"}
            and completion["schema_version"] == "weekly-mae-display-runtime-v1-catalog-completion"
            and completion["root_go_sha256"] == profile.root_sha256 and completion["current_values_used"] is False
            and matches(completion["catalog"], "prepared/mae-display/PROFILE_CATALOG.json")
            and wire.clock(profile.root["issued_at_utc"]) <= wire.clock(catalog["created_at"])
            <= wire.clock(completion["completed_at"]) <= wire.clock(source["actual_source_started_at"]),
            "POINT_CATALOG_OWNED_COMPLETION_BEFORE_SOURCE_REQUIRED")
        registry = doc("runtime/mae-display/SOURCE_REGISTRY.json")
        require(set(registry) == {"schema_version", "root_go_sha256", "created_before_point_values", "registered_at", "records"}
            and registry["schema_version"] == "weekly-mae-display-runtime-v1-source-registry"
            and registry["root_go_sha256"] == profile.root_sha256 and registry["created_before_point_values"] is True,
            "EXACT_PREVALUE_RUNTIME_SOURCE_REGISTRY_REQUIRED")
        wire.validate_registry(dict(schema_version=wire.REGISTRY, registered_at=registry["registered_at"],
            owner_admission_receipt_sha256=profile.root_sha256, records=registry["records"]))
        binding = doc("runtime/mae-display/CATALOG_BINDING.json")
        require(set(binding) == {"catalog", "completion", "root_go_sha256"} and binding["root_go_sha256"] == profile.root_sha256
            and matches(binding["catalog"], "prepared/mae-display/PROFILE_CATALOG.json")
            and matches(binding["completion"], "prepared/mae-display/CATALOG_COMPLETION.json"),
            "SAME_POINT_CATALOG_BINDING_REQUIRED")
        terminal = doc("runtime/mae-display/FINISHED.json")
        require(terminal["schema_version"] == "weekly-mae-display-runtime-v1-result"
            and terminal["state"] in {"PRIVATE_DISPLAY_CAPTURE_COMPLETE", "PARTIAL_DISPLAY_CAPTURE_RETAINED", "FAILED_DISPLAY_CAPTURE_RETAINED"}
            and terminal["root_go_sha256"] == profile.root_sha256 and terminal["display_only"] is True
            and terminal["public_export_authorized"] is False and type(terminal["statuses"]) is list
            and len(terminal["statuses"]) <= len(TARGETS)
            and [s["target"] for s in terminal["statuses"]] == list(TARGETS)[:len(terminal["statuses"])],
            "CLOSED_ORIGINAL_POINT_TERMINAL_REQUIRED")
        legacy = doc("runtime/FINISHED.json")
        require(type(snapshot["census"].get("actual_collected_at")) is str,
            "POINT_TERMINAL_REQUIRES_ACTUAL_COLLECTION_CLOCK")
        collected_at=wire.clock(snapshot["census"]["actual_collected_at"])
        proof=snapshot.get("producer_proof")
        require(snapshot.get("schema_version")!="audit-weekly-archive-v1-index" or type(proof) is dict,
            "POINT_TERMINAL_REQUIRES_NATIVE_PRODUCER_CLOCK")
        upper=collected_at
        if proof is not None:
            require(type(proof) is dict and type(proof.get("actual_started_at")) is str,
                "POINT_TERMINAL_REQUIRES_NATIVE_PRODUCER_CLOCK")
            upper=min(upper,wire.clock(proof["actual_started_at"]))
        require(terminal["legacy_selected"] == legacy["selected"]
            and wire.clock(source["actual_completed_at"]) <= wire.clock(legacy["selected"]["completed_at"])
            <= wire.clock(legacy["actual_completed_at"]) <= wire.clock(registry["registered_at"])
            <= wire.clock(terminal["actual_completed_at"]) <= upper,
            "POINT_TERMINAL_MUST_FOLLOW_LEGACY_AND_PRECEDE_ARCHIVE")
        if terminal["state"] == "FAILED_DISPLAY_CAPTURE_RETAINED":
            require(set(terminal)=={"schema_version","state","reason","root_go_sha256","statuses","legacy_selected","actual_completed_at","display_only","public_export_authorized"}
                and type(terminal["reason"]) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",terminal["reason"]),
                "EXACT_FAILED_POINT_TERMINAL_REQUIRED")
        else:
            require((terminal["state"] == "PRIVATE_DISPLAY_CAPTURE_COMPLETE") is all(s["state"] == "CAPTURED" and s["failure"] is None for s in terminal["statuses"]),
                "POINT_TERMINAL_MUST_REPORT_ORIGINAL_CATEGORY_FAILURES")
            require(set(terminal) == {"schema_version", "state", "root_go_sha256", "source", "feature_capture", "identity_bridge", "prevalue_catalog", "source_registry", "statuses", "legacy_selected", "legacy_statuses_sha256", "legacy_prediction_rows", "extra_traversal_rows_reserved", "actual_completed_at", "display_only", "ranking_policy_change", "probability_policy_change", "public_export_authorized", "independent_archive_restore"}
                and [s["target"] for s in terminal["statuses"]] == list(TARGETS)
                and terminal["legacy_statuses_sha256"] == wire.digest(doc("runtime/CANDIDATES.json")["slots"])
                and terminal["legacy_prediction_rows"] == legacy["prediction_rows"]
                and terminal["ranking_policy_change"] is terminal["probability_policy_change"] is False
                and terminal["independent_archive_restore"] == "REQUIRED"
                and all(matches(terminal[k], n) for k, n in (("source", "context/source.json"),
                    ("feature_capture", "runtime/features.capture.json"), ("identity_bridge", "runtime/IDENTITY_BRIDGE.json"),
                    ("prevalue_catalog", "prepared/mae-display/PROFILE_CATALOG.json"), ("source_registry", "runtime/mae-display/SOURCE_REGISTRY.json"))),
                "EXACT_POINT_TERMINAL_SOURCE_AND_UNCHANGED_LEGACY_BINDINGS")
            require(type(terminal["extra_traversal_rows_reserved"]) is int
                and terminal["extra_traversal_rows_reserved"] == sum(s["traversal_rows_reserved"] for s in terminal["statuses"])
                and terminal["legacy_prediction_rows"] + terminal["extra_traversal_rows_reserved"] <= 18000,
                "UNCHANGED_ALL_MODEL_TRAVERSAL_BUDGET_REQUIRED")
        identities = {}
        web = set()
        require(bridge["schema_version"] == "audit-weekly-runtime-v1-identity" and bridge["name_matching"] is False,
            "ORIGINAL_EXACT_POINT_IDENTITY_BRIDGE_REQUIRED")
        for identity in bridge["identities"]:
            key = identity["gsis_game_id"], identity["gsis_id"]
            website = identity["website_game_id"], identity["sleeper_id"]
            require(key not in identities and website not in web
                and identity["sleeper_id"] == identity["website_player_id"]
                and identity["query_source_sha256"] == items["runtime/queries.parquet"]["sha256"]
                and all(wire.ident(x) for x in key + website)
                and identity["identity_binding_sha256"] == wire.digest({k:v for k,v in identity.items() if k != "identity_binding_sha256"}),
                "UNIQUE_COMPLETE_CANONICAL_WEBSITE_POINT_BRIDGE_REQUIRED")
            identities[key] = identity; web.add(website)
        require(0 < len(identities) <= MAX_ROWS, "BOUNDED_COMPLETE_POINT_IDENTITY_POPULATION_REQUIRED")
        projections = {}; projection_sizes = {}
        for name in observed:
            if "/views/" not in name: continue
            projection = doc(name)
            require(matches(projection["parent_shared_capture"], "runtime/features.capture.json")
                and matches(projection["feature_binding"], "runtime/features.parquet")
                and projection["source_contract"] == feature["source_contract"],
                "POINT_VIEW_MUST_BIND_ORIGINAL_SHARED_FEATURE_CAPTURE")
            projections[items[name]["sha256"]] = projection
            projection_sizes[items[name]["sha256"]] = items[name]["bytes"]
        result.update(catalog=catalog, completion=completion, registry=registry, terminal=terminal,
            source=source, feature=feature, choice=choice, items=items)
        for target in TARGETS:
            entry = dict(target=target, state="MAE_UNAVAILABLE", original_state=None, reason="POINT_STATUS_UNAVAILABLE", rows=0, eligible_rows=0)
            summary["targets"].append(entry)
            try:
                status = doc(f"runtime/mae-display/status/{target}.json", 64 << 10)
                require(set(status) == STATUS_KEYS and status["target"] == target and status in terminal["statuses"]
                    and status["state"] in {"CAPTURED", "FAILED_RETAINED"}, "EXACT_ORIGINAL_POINT_CATEGORY_STATUS_REQUIRED")
                entry["original_state"] = status["state"]
                if status["state"] == "FAILED_RETAINED":
                    require(type(status["failure"]) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", status["failure"]), "SAFE_FAILED_POINT_STATUS_REQUIRED")
                    entry.update(state="FAILED_RETAINED", reason=status["failure"])
                    continue
                cfg = next(c for c in profile.config["categories"] if c["target"] == target)
                p = catalog["profiles"][target]
                slot = next(s for s in replay["slots"] if s["target"] == target and s["method_id"] == "LAB_CDF")
                origin = next(s for s in epoch["replay_catalog"]["slots"] if s["target"] == target and s["method_id"] == "LAB_CDF")
                require(set(p) == PROFILE_KEYS and p["schema_version"] == "owned-core-full-law-mae-profile-v2-draft2"
                    and p["target"] == p["scoring_target"] == target and p["base_learner_id"] == "LAB_CDF"
                    and p["selection_product"] == wire.PRODUCT and p["selection_metric"] == wire.METRIC
                    and p["method_id"] == "MAE_DISPLAY_LEAF_" + target and p["artifact"] == status["artifact"]
                    and p["artifact"]["sha256"] == slot["manifest_sha256"]
                    and p["base_procedure_version"] == slot["procedure_version"] == cfg["effective_base_procedure_version"]
                    and slot["model_sha256"] == origin["model_sha256"] == cfg["effective_model_sha256"]
                    and slot["transport_manifest_sha256"] == cfg["effective_transport_manifest_sha256"]
                    and origin["manifest_sha256"] == cfg["effective_verified_reader_manifest_sha256"]
                    and origin["procedure_version"] == cfg["effective_base_procedure_version"]
                    and p["adapter_pins"] == {Path(n).name:profile.root["mae_helper_pins"][n] for n in
                        ("nfl_lab/weekly_mae_point_inference_v2_1.py","nfl_lab/next_checkpoint_median_policy_v2_view.py")}
                    and p["public_roles"] == cfg["public_roles"]
                    and p["owner_admission_receipt_sha256"] == profile.root_sha256
                    and p["registered_at"] == profile.root["issued_at_utc"]
                    and p["procedure_version"] == digest({k:v for k,v in p.items() if k != "procedure_version"})
                    and status["profile_sha256"] == digest(p), "POINT_PROFILE_MUST_BIND_ACTUAL_PREPARED_CORE_ARTIFACT")
                receipt = doc(f"runtime/mae-display/candidates/{target}.jsonl.completion.json", 64 << 10)
                require(set(receipt)=={"schema_version","state","binding","rows","persist_started_at","completed_at","private_only","remote_durability","scientific_qualification"}
                    and status["failure"] is None and status["persistence"] == receipt
                    and receipt["schema_version"] == "weekly-adaptive-release-v1-future-inference-persistence" and receipt["state"] == "PERSISTED"
                    and receipt["private_only"] is True and receipt["remote_durability"] == "NOT_ESTABLISHED"
                    and receipt["scientific_qualification"] is False
                    and type(status["expected_rows"]) is int and status["expected_rows"] == status["issued_rows"] == receipt["rows"] == len(identities)
                    and status["traversal_rows_requested"] == status["traversal_rows_reserved"] == 2 * receipt["rows"]
                    and matches(receipt["binding"], f"runtime/mae-display/candidates/{target}.jsonl.gz")
                    and wire.clock(receipt["persist_started_at"]) <= wire.clock(receipt["completed_at"])
                    <= wire.clock(terminal["actual_completed_at"]), "COMPLETE_ORIGINAL_POINT_CATEGORY_PERSISTENCE_REQUIRED")
                rows = _rows(body(f"runtime/mae-display/candidates/{target}.jsonl.gz", 4 << 20))
                seen = set(); admitted = []
                for envelope, line_sha in rows:
                    c = envelope["candidate"]
                    key = c["game_id"], c["player_id"]
                    require(set(envelope) == ENVELOPE_KEYS and envelope["schema_version"] == "weekly-mae-display-runtime-v1-identity-envelope"
                        and envelope["envelope_sha256"] == wire.digest({k:v for k,v in envelope.items() if k != "envelope_sha256"})
                        and envelope["candidate_sha256"] == c["candidate_sha256"] == digest({k:v for k,v in c.items() if k != "candidate_sha256"})
                        and envelope["legacy_ranking_policy_unchanged"] is True and key in identities and key not in seen
                        and envelope["cutoff_utc"] == c["issue_deadline_utc"] and envelope["operational_eligible"] is c["operational_eligible"],
                        "EXACT_COMPLETE_IMMUTABLE_POINT_ENVELOPE_REQUIRED")
                    identity = identities[key]
                    public_identity = dict(website_game_id=identity["website_game_id"], sleeper_id=identity["sleeper_id"],
                        identity_bridge_sha256=items["runtime/IDENTITY_BRIDGE.json"]["sha256"], identity_binding_sha256=identity["identity_binding_sha256"])
                    require(envelope["public_identity"] == public_identity and c["team"] == identity["team"]
                        and c["opponent"] == identity["opponent"] and wire.clock(c["kickoff_utc"]) == wire.clock(identity["kickoff_utc"])
                        and (c["season"], c["week"]) == (choice["slate"]["season"], choice["slate"]["week"])
                        and c["schema_version"] == c["consumer_contract_version"] == "stat-point-mae-v2"
                        and c["candidate_schema"] == wire.CANDIDATE_SCHEMA
                        and c["selection_product"] == wire.PRODUCT and c["selection_metric"] == wire.METRIC
                        and c["evidence_lane"] == "original_pregame" and c["conditional_on"] == "played"
                        and c["participation_state"] == "unknown" and c["public_export_authorized"] is c["scientific_qualification"] is False
                        and not {"outcome","actual","label","loss"}&set(c)
                        and c["target"] == c["scoring_target"] == c["category"] == target
                        and c["offered_id"] == wire.digest(dict(season=c["season"], week=c["week"], game_id=c["game_id"], player_id=c["player_id"], category=target))
                        and c["base_learner_id"] == p["base_learner_id"] and c["method_id"] == p["method_id"]
                        and c["model_version"] == p["artifact"]["sha256"]
                        and c["owner_admission_receipt_sha256"] == profile.root_sha256
                        and c["model_bytes_sha256"] == slot["model_sha256"]
                        and c["procedure_version"] == p["procedure_version"] and c["base_procedure_version"] == p["base_procedure_version"]
                        and c["point_profile_sha256"] == digest(p) and c["source_contract"] == cfg["source_contract"]
                        and c["source_policy_sha256"] == cfg["source_contract"]["source_policy_sha256"]
                        and c["source_receipt"] == terminal.get("source", c["source_receipt"])
                        and matches(c["source_receipt"], "context/source.json")
                        and matches(c["feature_binding"], "runtime/features.parquet")
                        and c["feature_capture_receipt"]["sha256"] in projections,
                        "EXACT_POINT_MODEL_SOURCE_PROFILE_AND_BRIDGE_REQUIRED")
                    old=c["original_forecast"]
                    require(all(old[k]==c[k] for k in ("season","week","game_id","player_id","team","opponent","position","offered_id","horizon","slate_id","source_policy_sha256","query_source_sha256","kickoff_utc"))
                        and old["model_version"]==old["artifact_sha256"]==c["model_version"]
                        and old["method_id"]==p["base_learner_id"] and old["procedure_version"]==p["base_procedure_version"]
                        and old["product"]=="point_mean" and old["prediction_functional"]=="expected_mean"
                        and old["evidence_lane"]=="original_pregame" and old["scientific_qualification"] is False
                        and old["issued_at"]==c["legacy_issued_at"] and wire.clock(old["issued_at"])<=wire.clock(c["issued_at"]),
                        "ORIGINAL_LEGACY_POINT_IDENTITY_AND_FUNCTIONAL_MUST_BE_PRESERVED")
                    projection = projections[c["feature_capture_receipt"]["sha256"]]
                    require(set(c["feature_capture_receipt"])=={"path","bytes","sha256"}
                        and c["feature_capture_receipt"]["bytes"]==projection_sizes[c["feature_capture_receipt"]["sha256"]]
                        and projection["query_projection_sha256"] == c["query_projection_sha256"]
                        and wire.clock(feature["feature_persist_completed_at"])<=wire.clock(projection["projection_descriptor_started_at"])
                        <=wire.clock(registry["registered_at"])
                        and projection["projection_features"] == cfg["features"]
                        and c["original_forecast"]["source_capture_completed_at"] == feature["feature_persist_completed_at"]
                        and wire.clock(source["asof_utc"]) == wire.clock(c["information_cutoff_utc"])
                        and c["query_source_sha256"] == items["runtime/features.parquet"]["sha256"]
                        and wire.clock(c["information_cutoff_utc"]) <= wire.clock(feature["feature_persist_completed_at"])
                        <= wire.clock(registry["registered_at"]) <= wire.clock(c["issued_at"])
                        <= wire.clock(receipt["completed_at"]) < wire.clock(c["issue_deadline_utc"])
                        == wire.clock(choice["slate"]["game_cutoffs"][c["game_id"]]) < wire.clock(c["kickoff_utc"]),
                        "ORIGINAL_POINT_ISSUE_SOURCE_AND_PERSISTENCE_CLOCKS_REQUIRED")
                    expected_source = {k:c[k] for k in wire.SOURCE_KEYS if k in c}
                    expected_source.update(source_contract_sha256=wire.digest(c["source_contract"]), source_receipt_sha256=c["source_receipt"]["sha256"],
                        feature_capture_receipt_sha256=c["feature_capture_receipt"]["sha256"], feature_binding_sha256=c["feature_binding"]["sha256"],
                        feature_capture_completed_at=feature["feature_persist_completed_at"], public_roles=p["public_roles"],
                        identity_bridge_sha256=public_identity["identity_bridge_sha256"])
                    require(expected_source in registry["records"], "POINT_SOURCE_SNAPSHOT_NOT_REGISTERED_BEFORE_VALUES")
                    seen.add(key)
                    require(all(type(c[k]) is bool for k in ("public_scope_eligible","operational_eligible","fallback","trained_prior_only")),
                        "EXACT_POINT_ELIGIBILITY_FLAGS_REQUIRED")
                    if c["public_scope_eligible"] is True and c["operational_eligible"] is True:
                        require(c["position"] in p["public_roles"] and c["position"] in cfg["modeled_roles"]
                            and c["forecast_product"] == "point_median" and c["prediction_functional"] == "full_cdf_lower_median"
                            and wire.finite(c["separate_expected_mean"]) and c["separate_expected_mean"]==old["forecast_value"] and type(c["fallback_reason"]) is str
                            and len(c["fallback_reason"]) <= 500 and (bool(c["fallback_reason"]) is c["fallback"])
                            and (not c["trained_prior_only"] or c["fallback"]), "POINT_PUBLIC_ROLE_OR_FUNCTIONAL_NOT_REGISTERED")
                        # Pure formatting/functional validation grants no owner capability.
                        wire.consumer_view(dict(c,capture_receipt_sha256=line_sha,mean_eligible=True))
                        admitted.append(dict(candidate=c, identity=public_identity, line_sha256=line_sha, persistence=receipt))
                require(seen == set(identities) and len(rows) == receipt["rows"], "NO_DROPPED_POINT_CATEGORY_POPULATION")
                captures[target] = admitted
                entry.update(state="RESTORED_COMPLETE_CATEGORY", reason=None, rows=len(rows), eligible_rows=len(admitted))
            except Exception as error:
                entry.update(state="INVALID_CAPTURE_RETAINED", reason=safe_reason(error))
        summary["eligible_rows"] = sum(s["eligible_rows"] for s in summary["targets"])
        summary["state"] = "POINT_CATEGORIES_RESTORED" if summary["eligible_rows"] else "MAE_UNAVAILABLE"
    except Exception as error:
        summary["reason"] = safe_reason(error)
    return result


def validate_capture(snapshot, path, profile):
    return inspect_capture(snapshot, path, profile)["summary"]


def _public_entry(c, profile):
    entry = {k:c[k] for k in wire.ENTRY_KEYS if k in c}
    entry.update(artifact_sha256=c["model_version"], source_contract_sha256=wire.digest(c["source_contract"]),
        public_roles=profile["public_roles"])
    return entry


def native_export(live, client, consumed, profile, *, legacy_feed_sha256, created_at):
    """Derive all wire verifiers from the actual same-process native acceptance.

    No caller callback or flag can mint registry/catalog/capture capabilities.
    This method performs only exact owned reads; transport already happened in
    the existing qualified archive consumer and live API verifier.
    """
    from . import audit_weekly_public_v1 as public, audit_weekly_archive_v1 as archive
    from . import gha_private_checkpoint as cp, private_draft_store as store
    require(type(live) is public.LiveAcceptance and type(profile) is DisplayProfile,
        "ACTUAL_NATIVE_LIVE_POINT_ACCEPTANCE_REQUIRED")
    live.verify(); profile.verify()
    actual = cp.client_identity(client)
    require(isinstance(client, archive.Client) and client.readonly is True
        and actual == live.record["exporter"] == consumed["current"]
        and client.source_sha == profile.root["source_sha"] == live.inputs["policy"]["source_sha"]
        and client.run_id == consumed["archive"]["run_id"] and consumed["archive"]["root_go_sha256"] == profile.root_sha256
        and consumed["archive"]["source_sha"] == profile.root["source_sha"]
        and consumed["archive"]["jobs"] == live.inputs["policy"]["jobs"]
        and consumed["aliases"] == live.inputs["aliases"] and consumed["validation"]["qualified_selected"] is True
        and profile.root.get("publication") is True, "SAME_NATIVE_EXPORTER_ROOT_ARCHIVE_AND_LEGACY_ACCEPTANCE_REQUIRED")
    storage = live.inputs["storage"]; aliases = consumed["aliases"]
    index_ref = consumed.get("index_ref") or cp.binding(Path(aliases["runtime/selected.jsonl.gz"]["path"]).parents[2]/"owned-downloads/index.gz")
    encoded = archive.read_owned(storage, index_ref, archive.INDEX_CAP, raw=True)
    require(sha(encoded) == consumed["index_sha256"] == live.record["archive_index_sha256"], "NATIVE_POINT_ARCHIVE_INDEX_READBACK_REQUIRED")
    snapshot = archive.unpack(encoded, archive.INDEX_PLAIN_CAP)
    require(snapshot["files_sha256"] == consumed["files_sha256"] == live.record["archive_files_sha256"]
        and snapshot["root_go_sha256"] == profile.root_sha256 and snapshot["producer_proof"] == consumed["producer_proof"],
        "NATIVE_POINT_INDEX_FULL_FILE_AND_PRODUCER_BINDINGS_REQUIRED")
    from .owned_reference_batch import validate_owned_references
    validate_owned_references(storage,{ref["path"]:ref["sha256"] for ref in aliases.values()})
    inspected = inspect_capture(snapshot, lambda n:Path(aliases[n]["path"]), profile)
    require(inspected["summary"] == consumed["validation"].get("mae_display"), "INDEPENDENT_POINT_RESTORER_EXPORTER_VALIDATION_MUST_MATCH")
    readback = max((live.record["accepted_at"], live.record["durability_clocks"]["restorer_witness_completed_at"],
        live.record["durability_clocks"]["exporter_restore_proof_created_at"]), key=wire.clock)
    require(wire.clock(readback) <= wire.clock(created_at), "ACTUAL_POINT_READBACK_PRECEDES_PUBLIC_EXPORT")
    available = []; unavailable = deepcopy(inspected["summary"]["targets"])
    durable_upper = []
    for target, rows in inspected["captures"].items():
        kept = 0
        for row in rows:
            persisted = max((row["persistence"]["completed_at"], live.record["durability_clocks"]["archive_index_created_at"],
                live.record["durability_clocks"]["producer_job_completed_at_upper_bound"]), key=wire.clock)
            if wire.clock(persisted) >= wire.clock(row["candidate"]["issue_deadline_utc"]): continue
            require(wire.clock(persisted) <= wire.clock(readback), "NATIVE_POINT_PERSISTENCE_PRECEDES_READBACK")
            row["persisted_upper_bound"] = persisted; available.append(row); durable_upper.append(persisted); kept += 1
        status = next(s for s in unavailable if s["target"] == target)
        status["eligible_rows"] = kept
        if not kept:
            status.update(state="MAE_UNAVAILABLE",reason="ARCHIVE_DURABILITY_NOT_PROVEN_BEFORE_ORIGINAL_DEADLINE" if rows else "NO_ELIGIBLE_REGISTERED_PUBLIC_SCOPE_ROWS")
    base = dict(schema_version=VERSION + "-unavailable", state="MAE_UNAVAILABLE", root_go_sha256=profile.root_sha256,
        source_sha=client.source_sha, run_id=client.run_id, reason=inspected["summary"]["reason"], targets=unavailable,
        archive_index_sha256=live.record["archive_index_sha256"], archive_files_sha256=live.record["archive_files_sha256"],
        verified_at=live.record["accepted_at"], fits=0, model_adoption=False, ranking_policy_change=False, probability_policy_change=False)
    if not available: return dict(document=None, receipt=base, private_readback=None)
    catalog = inspected["catalog"]; registry = inspected["registry"]
    selected_targets = sorted({r["candidate"]["target"] for r in available})
    entries = []
    for target in selected_targets:
        selected = [r for r in available if r["candidate"]["target"] == target]
        entry = _public_entry(selected[0]["candidate"], catalog["profiles"][target])
        require(all(_public_entry(r["candidate"], catalog["profiles"][target]) == entry for r in selected), "ONE_PREDECLARED_POINT_PROFILE_PER_CATEGORY_REQUIRED")
        entries.append(entry)
    keys = {(r["candidate"]["target"],r["candidate"]["query_projection_sha256"]) for r in available}
    source_records = [s for s in registry["records"] if (s["target"],s["query_projection_sha256"]) in keys]
    public_registry = dict(schema_version=wire.REGISTRY, registered_at=registry["registered_at"],
        owner_admission_receipt_sha256=profile.root_sha256, records=source_records)
    public_catalog = dict(schema_version=wire.CATALOG, selection_product=wire.PRODUCT, selection_metric=wire.METRIC,
        registered_at=catalog["created_at"], owner_admission_receipt_sha256=profile.root_sha256, entries=entries)
    def verify_registry(kind, raw):
        require(kind == "SOURCE_REGISTRY" and raw == wire.canonical(public_registry), "NATIVE_POINT_REGISTRY_BYTES_CHANGED")
    def verify_catalog(kind, raw):
        require(kind == "CATALOG" and raw == wire.canonical(public_catalog), "NATIVE_POINT_CATALOG_BYTES_CHANGED")
    registry_cap = wire.admit_registry(public_registry, verify_owner_registry=verify_registry)
    catalog_cap = wire.admit_catalog(public_catalog, registry_cap, verify_owner_catalog=verify_catalog)
    receipts = []; captures = []
    for row in available:
        c = row["candidate"]
        receipt = dict(schema_version=wire.CAPTURE, state="FROZEN_AND_READ_BACK", horizon="player_game",
            candidate_sha256=c["candidate_sha256"], capture_body_sha256=inspected["items"]["runtime/mae-display/candidates/"+c["target"]+".jsonl.gz"]["sha256"],
            selection_sha256=inspected["items"]["prepared/mae-display/PROFILE_CATALOG.json"]["sha256"],
            identity={k:c[k] for k in ("season","week","game_id","player_id","target")}, source_registry_sha256=registry_cap.sha256,
            persistence_completed_at=row["persisted_upper_bound"], readback_completed_at=readback,
            **row["identity"], **{k:c[k] for k in ("model_version","procedure_version","point_profile_sha256","source_policy_sha256",
                "query_projection_sha256","information_cutoff_utc","issued_at","issue_deadline_utc","kickoff_utc","team","opponent")})
        receipt["capture_receipt_sha256"] = inspected["items"]["runtime/mae-display/candidates/"+c["target"]+".jsonl.completion.json"]["sha256"]
        expected = wire.canonical(receipt)
        def verify_capture(raw, candidate_sha, catalog_sha, registry_sha, *, expected=expected, csha=c["candidate_sha256"]):
            require(raw == expected and candidate_sha == csha and catalog_sha == catalog_cap.sha256 and registry_sha == registry_cap.sha256,
                "NATIVE_POINT_CAPTURE_READBACK_BYTES_CHANGED")
        captures.append(wire.finalize_capture(c, receipt, catalog_cap, registry_cap, verify_owner_capture=verify_capture))
        receipts.append(receipt)
    readback_evidence = dict(schema_version=VERSION + "-native-readback", root_go_sha256=profile.root_sha256,
        archive_index_sha256=consumed["index_sha256"], archive_files_sha256=consumed["files_sha256"],
        reader_witness_sha256=consumed["witness_descriptor"]["entry"]["payload"]["sha256"],
        exporter_proofs_sha256=live.record["exporter_proofs_sha256"], captures=receipts)
    jobs = {role:dict(job_id=live.record[key]["job_id"],api_job_id=live.record[key]["api_job_id"])
        for role,key in (("produce","producer"),("restore","restorer"),("consume","exporter"))}
    items = inspected["items"]
    public_receipt = dict(schema_version=RECEIPT_VERSION, scope=SCOPE, state="POINT_SUBSET_VERIFIED",
        source_sha=client.source_sha, source_branch=live.inputs["policy"]["source_branch"], run_id=client.run_id, run_attempt=1,
        root_go_sha256=profile.root_sha256, profile_registration_sha256=profile.root["mae_registration"]["sha256"],
        helper_inventory_sha256=digest(profile.root["mae_helper_pins"]), point_policy_sha256=wire.digest(point_policy()),
        source_policy_sha256=live.inputs["policy"]["source_policy_sha256"], workflow_sha256=live.record["workflow_sha256"], jobs=jobs,
        archive_index_sha256=consumed["index_sha256"], archive_files_sha256=consumed["files_sha256"],
        reader_witness_sha256=readback_evidence["reader_witness_sha256"],
        **{k:live.record[k] for k in ("producer_proof_sha256","restorer_proof_sha256","exporter_proofs_sha256")},
        prevalue_catalog_sha256=items["prepared/mae-display/PROFILE_CATALOG.json"]["sha256"],
        catalog_completion_sha256=items["prepared/mae-display/CATALOG_COMPLETION.json"]["sha256"],
        runtime_source_registry_sha256=items["runtime/mae-display/SOURCE_REGISTRY.json"]["sha256"],
        identity_bridge_sha256=items["runtime/IDENTITY_BRIDGE.json"]["sha256"], runtime_terminal_sha256=items["runtime/mae-display/FINISHED.json"]["sha256"],
        legacy_selected_sha256=live.record["selected_body_sha256"], legacy_feed_sha256=legacy_feed_sha256,
        catalog_sha256=catalog_cap.sha256, source_registry_sha256=registry_cap.sha256,
        candidates_sha256=wire.digest({n:{k:f[k] for k in ("bytes","sha256")} for n,f in items.items()
            if n.startswith("runtime/mae-display/candidates/")}), captures_sha256=wire.digest(receipts), readback_sha256=wire.digest(readback_evidence),
        categories=selected_targets, unavailable=[s for s in unavailable if s["eligible_rows"]==0], created_at=created_at, verified_at=live.record["accepted_at"],
        persistence_completed_at_upper_bound=max(durable_upper,key=wire.clock), readback_completed_at=readback,
        fits=0, raw_or_models_public=False, probability_policy_change=False, ranking_policy_change=False)
    owner_export = wire.digest(public_receipt)
    def verify_export(raw, catalog_sha, registry_sha):
        expected_rows = [deepcopy(c.document) for c in captures]
        for r in expected_rows:
            if wire.clock(created_at) >= wire.clock(r["kickoff_utc"]): r["retained_capture"] = True
        value = wire.strict_json(raw)
        require(catalog_sha == catalog_cap.sha256 and registry_sha == registry_cap.sha256
            and value["rows"] == expected_rows and value["owner_export_receipt_sha256"] == owner_export
            and value["created_at"] == created_at, "NATIVE_POINT_EXPORT_BYTES_CHANGED")
    document = wire.export_feed(captures, catalog_cap, registry_cap, created_at=created_at,
        owner_export_receipt_sha256=owner_export, verify_owner_export=verify_export)
    live.verify(); profile.verify()
    require(cp.client_identity(client)==actual,"POINT_NATIVE_EXPORTER_PROCESS_CHANGED")
    public_receipt.update(owner_export_receipt_sha256=owner_export, feed_sha256=sha(wire.canonical(document)),
        feed_bytes=len(wire.canonical(document)), rows=len(document["rows"]))
    validate_public_pair(wire.canonical(document), gzip.compress(wire.canonical(public_receipt),mtime=0))
    return dict(document=document, receipt=public_receipt, private_readback=readback_evidence)


def public_names(files):
    require(type(files) is dict and len(files) == 2, "EXACT_POINT_PUBLIC_PAIR_REQUIRED")
    feeds = [n for n in files if re.fullmatch(POINT_PREFIX + r"/\d{4}-W(?:0[1-9]|1\d|2[0-2])/\d{8}T\d{6}\.\d{6}Z--[a-f0-9]{64}\.json", n)]
    receipts = [n for n in files if re.fullmatch(POINT_PREFIX + r"/receipts/[a-f0-9]{64}\.json\.gz", n)]
    require(len(feeds) == len(receipts) == 1 and all(wire.h(h) for h in files.values())
        and Path(feeds[0]).stem.split("--")[1] == Path(receipts[0]).name[:-8], "CLOSED_COHERENT_POINT_PUBLIC_PAIR_PATHS_REQUIRED")
    return feeds[0], receipts[0]


def validate_public_pair(body, encoded):
    document = wire.strict_json(body); wire.validate_feed(document)
    require(body == wire.canonical(document) and 0 < len(encoded) <= 64 << 10, "EXACT_BOUNDED_POINT_PUBLIC_BYTES_REQUIRED")
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS); raw = inflater.decompress(encoded,(64 << 10)+1)
    require(inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail and len(raw) <= 64 << 10,
        "EXACT_SINGLE_POINT_PUBLIC_RECEIPT_GZIP_REQUIRED")
    r = wire.strict_json(raw)
    require(raw == wire.canonical(r) and set(r) == RECEIPT_KEYS and r["schema_version"] == RECEIPT_VERSION
        and r["scope"] == SCOPE and r["state"] == "POINT_SUBSET_VERIFIED"
        and r["point_policy_sha256"] == wire.digest(point_policy())
        and all(wire.h(v) for k,v in r.items() if k.endswith("sha256"))
        and re.fullmatch(r"[a-f0-9]{40}",r["source_sha"]) and re.fullmatch(r"[1-9][0-9]{0,19}",r["run_id"])
        and type(r["run_attempt"]) is int and r["run_attempt"] == 1 and r["fits"] == 0
        and r["raw_or_models_public"] is r["probability_policy_change"] is r["ranking_policy_change"] is False
        and r["feed_sha256"] == sha(body) and r["feed_bytes"] == len(body) and r["rows"] == len(document["rows"])
        and r["categories"] == sorted({row["target"] for row in document["rows"]}) and set(r["categories"]) <= set(TARGETS)
        and r["catalog_sha256"] == document["catalog_sha256"] and r["source_registry_sha256"] == document["source_registry_sha256"]
        and r["owner_export_receipt_sha256"] == document["owner_export_receipt_sha256"]
        and r["owner_export_receipt_sha256"] == wire.digest({k:v for k,v in r.items() if k not in {"owner_export_receipt_sha256","feed_sha256","feed_bytes","rows"}})
        and r["created_at"] == document["created_at"]
        and all(row["source_policy_sha256"] == r["source_policy_sha256"] and row["forecast_product"]=="point_median"
            and row["prediction_functional"]=="full_cdf_lower_median" for row in document["rows"])
        and type(r["source_branch"]) is str and re.fullmatch(r"[A-Za-z0-9_./-]{1,160}",r["source_branch"])
        and not any(p in {"",".",".."} for p in r["source_branch"].split("/"))
        and type(r["unavailable"]) is list and len(r["unavailable"]) <= len(TARGETS)
        and all(type(s) is dict and set(s)=={"target","state","original_state","reason","rows","eligible_rows"}
            and s["target"] in TARGETS and s["state"] in {"MAE_UNAVAILABLE","FAILED_RETAINED","INVALID_CAPTURE_RETAINED","RESTORED_COMPLETE_CATEGORY"}
            and s["original_state"] in {None,"CAPTURED","FAILED_RETAINED"}
            and (s["reason"] is None or type(s["reason"]) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}",s["reason"]))
            and type(s["rows"]) is type(s["eligible_rows"]) is int and 0<=s["eligible_rows"]<=s["rows"]<=MAX_ROWS
            for s in r["unavailable"])
        and set(r["jobs"]) == {"produce","restore","consume"}
        and len({v["job_id"] for v in r["jobs"].values()}) == 3
        and all(set(v) == {"job_id","api_job_id"} and type(v["job_id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,100}",v["job_id"])
            and type(v["api_job_id"]) is int and v["api_job_id"] > 0 for v in r["jobs"].values()),
        "CLOSED_NATIVE_POINT_PUBLIC_RECEIPT_REQUIRED")
    require(wire.clock(r["persistence_completed_at_upper_bound"]) <= wire.clock(r["readback_completed_at"])
        <= wire.clock(r["verified_at"]) <= wire.clock(r["created_at"]), "POINT_RECEIPT_ACTUAL_DURABILITY_READBACK_CLOCKS_REQUIRED")
    return document, r


def write_pair(storage, state, exported):
    """Owned immutable preparation only; persist_state makes the coherent commit."""
    from . import audit_weekly_archive_v1 as archive, gha_private_checkpoint as cp
    document, receipt = exported["document"], exported["receipt"]
    require(document is not None, "NONEMPTY_NATIVE_POINT_FEED_REQUIRED")
    body = wire.canonical(document); encoded = gzip.compress(wire.canonical(receipt),mtime=0)
    validate_public_pair(body, encoded)
    stamp = wire.clock(document["created_at"]).strftime("%Y%m%dT%H%M%S.%fZ")
    feed = f"{POINT_PREFIX}/{document['season']}-W{document['week']:02d}/{stamp}--{sha(body)}.json"
    receipt_name = f"{POINT_PREFIX}/receipts/{sha(body)}.json.gz"
    payloads = {feed:body, receipt_name:encoded}; files = {n:sha(b) for n,b in payloads.items()}
    public_names(files)
    with storage.transaction(): storage._require(sum(len(b) for b in payloads.values()) + (64 << 10))
    for name,payload in payloads.items(): storage.write_bytes(Path(state)/name,payload)
    saved = [archive.read_owned(storage,cp.binding(Path(state)/name),wire.MAX_BYTES if name == feed else 64 << 10,raw=True) for name in (feed,receipt_name)]
    require(saved == [body,encoded], "POINT_PUBLIC_PAIR_EXACT_OWNED_READBACK_REQUIRED")
    return files
