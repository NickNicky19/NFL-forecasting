"""DRAFT: additive full-law MAE point candidates over the reviewed0409 session.

No import loads a model, acquires sources, fits, captures or admits production.
The owner supplies an authenticated prepared legacy session and an independently
configured admission verifier. JSON supplied by a request is never admission.
This module emits PRIVATE candidates, not durable/public/activated forecasts.

The deterministic second law traversal is intentional: the original session,
model and module globals are never changed. Both traversals are charged to the
owner's separately reviewed finite inference allocation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

from nfl_lab import weekly_future_inference as legacy
from nfl_lab.next_checkpoint_median_policy_v2_view import (
    VERSION as POINT_VERSION, FUNCTIONAL_VERSION, COUNT, SIGNED,
    full_law_functionals,
)
import nfl_lab.next_checkpoint_median_policy_v2_view as point_contract

VERSION = "owned-core-full-law-mae-candidates-v2-draft2"
PROFILE_VERSION = "owned-core-full-law-mae-profile-v2-draft2"
MAX_ROWS, MAX_BATCH = 1000, 256
NUMERIC = (COUNT | SIGNED) - {"nick-chart-ppr-v1"}
REVIEWED_MODEL_PINS = {
    "weekly_future_inference.py": "d84a4de76737252a910ed01b626e17403290277feb894621e625ae0791ccef42",
    "cdf_engine.py": "6a963111f4173a88affe90ca1ce17532cd5eb690a1f28b284e9fa4145eecb214",
    "role_boosting.py": "294e7e588215e7b7e98d6f1fb251eed31420921dff9a59e88434913133dbdf93",
    "direct_boosters.py": "475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f",
    "median_boosting.py": "c5bf8ef481c05027a2a1d4e1d19764920c0820f0614f60736826c17526e7799d",
    "baseline_correction.py": "077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2",
}
CONTRACT_SHA256 = "48cc101e8a2b4288bebc74bc2015d6140f4181e83ebfe3bbd0a3e87603a12ed5"
PROFILE_KEYS = frozenset({"schema_version", "selection_product", "selection_metric",
    "target", "scoring_target", "base_learner_id", "method_id", "artifact",
    "base_procedure_version", "procedure_version", "feature_schema_sha256",
    "public_roles", "registered_at", "owner_admission_receipt_sha256", "adapter_pins"})
CONTEXT_KEYS = frozenset({"cutoff_utc", "weekly_decision_cutoff_utc", "slate_id",
    "source_contract", "evidence_lane", "reference_stream", "query_source_sha256",
    "feature_capture_receipt"})
_ADMITTED = object()
_HASH = re.compile(r"[a-f0-9]{64}\Z")


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


def _clock(value):
    _require(type(value) is str, "EXPLICIT_AWARE_CLOCK_REQUIRED")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("EXPLICIT_AWARE_CLOCK_REQUIRED") from error
    _require(result.tzinfo is not None and result.utcoffset() is not None,
             "EXPLICIT_AWARE_CLOCK_REQUIRED")
    return result


def _identifier(value):
    return (type(value) is str and 0 < len(value) <= 128 and value == value.strip()
            and value.lower() not in {"nan", "nat", "none", "null", "undefined"}
            and all(ord(c) >= 33 and ord(c) != 127 for c in value))


def _reference(value):
    _require(type(value) is dict and set(value) == {"path", "bytes", "sha256"}
             and type(value["path"]) is str and Path(value["path"]).is_absolute()
             and type(value["bytes"]) is int and value["bytes"] > 0
             and _hash(value["sha256"]), "EXACT_OWNED_REFERENCE_REQUIRED")
    return value


def _metadata(session, reference, *, cap=256 << 10):
    _reference(reference)
    _require(reference["bytes"] <= cap, "BOUNDED_METADATA_REQUIRED")
    session._verify([reference])
    with Path(reference["path"]).open("rb") as stream:
        body = stream.read(cap + 1)
    _require(len(body) == reference["bytes"]
             and hashlib.sha256(body).hexdigest() == reference["sha256"],
             "OWNED_METADATA_BYTES_CHANGED")
    def invalid(_):
        raise ValueError("NONFINITE_JSON_FORBIDDEN")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "DUPLICATE_JSON_KEY_FORBIDDEN")
            result[key] = value
        return result
    result = json.loads(body, parse_constant=invalid, object_pairs_hook=unique_object)
    _require(type(result) is dict, "METADATA_OBJECT_REQUIRED")
    return result


def implementation_pins():
    return {"weekly_mae_point_inference_v2_1.py": legacy.sha(__file__),
            "next_checkpoint_median_policy_v2_view.py": legacy.sha(point_contract.__file__)}


def feature_schema(manifest):
    category = manifest["category"]
    return _digest(dict(target=category["target"], support=category["support"],
        features=manifest["features"], modeled_roles=category["modeled_roles"],
        primary_roles=category["primary_roles"], source_contract=manifest["source_contract"]))


def view_procedure(document):
    """Freeze the exact recipe before values; no implicit version registration."""
    return _digest({k: v for k, v in document.items() if k != "procedure_version"})


def _prepared(session, artifact):
    _require(type(session) is legacy.FutureInferenceSession and not session.closed,
             "EXACT_PREPARED_LEGACY_SESSION_REQUIRED")
    _reference(artifact)
    _require(artifact["sha256"] in session.models, "PREPARED_ARTIFACT_REQUIRED")
    manifest, model = session.models[artifact["sha256"]]
    _require(_metadata(session, artifact) == manifest, "PREPARED_MANIFEST_CHANGED")
    _require(legacy.code_pins() == REVIEWED_MODEL_PINS
             and manifest["code_pins"] == REVIEWED_MODEL_PINS
             and manifest["environment"] == legacy.environment(),
             "REVIEWED0409_PREPARED_CODE_ENVIRONMENT_REQUIRED")
    _require(manifest["family"] == "leaf_cdf_base"
             and type(model) is legacy.cdf.LeafCDFModel and model.panel == "base"
             and "predict_batches" not in vars(model)
             and manifest["category"]["target"] in NUMERIC
             and manifest["probability_law"] == "EMPIRICAL_LEAF_PLUS_SUPPORT_PRIOR",
             "EXACT_CORE_NUMERIC_LEAF_MODEL_REQUIRED")
    _require(legacy.model_contract(model, manifest["family"])
             == (manifest["category"], manifest["features"]), "PREPARED_MODEL_SCHEMA_CHANGED")
    _require(_hash(manifest["procedure_version"])
             and _hash(manifest["source_contract"]["source_policy_sha256"])
             and _hash(manifest["source_contract"]["feature_builder_sha256"]),
             "COMPLETE_PREPARED_PROCEDURE_SOURCE_IDENTITIES_REQUIRED")
    _reference(manifest["model"])
    _require(session.refs.get(manifest["model"]["path"]) == manifest["model"],
             "PREPARED_MODEL_BYTES_NOT_AUTHENTICATED")
    session._verify([manifest["model"]])
    return manifest, model


class AdmittedProfile:
    """In-memory owner capability. An incoming JSON profile cannot construct it.

    The verifier is trusted *code configured by the owner entry point*, not a
    value supplied by an incoming request. The draft supplies no default verifier
    and does not implement or claim actual external owner admission.
    """
    __slots__ = ("_body", "_session", "_model", "_verify_owner", "_key")

    def __init__(self, body, session, model, verify_owner, key):
        _require(key is _ADMITTED, "OWNER_ADMISSION_CAPABILITY_REQUIRED")
        self._body, self._session, self._model = body, session, model
        self._verify_owner, self._key = verify_owner, key

    def __reduce__(self):
        raise ValueError("OWNER_ADMISSION_MUST_NOT_BE_SERIALIZED")

    @property
    def document(self):
        return json.loads(self._body)

    @property
    def sha256(self):
        return hashlib.sha256(self._body).hexdigest()

    def verify(self, session):
        _require(self._key is _ADMITTED and session is self._session,
                 "SAME_OWNER_ADMITTED_SESSION_REQUIRED")
        doc = self.document
        manifest, model = _prepared(session, doc["artifact"])
        _require(model is self._model and doc["adapter_pins"] == implementation_pins(),
                 "ADMITTED_MODEL_OR_ADAPTER_CHANGED")
        _require(self._verify_owner(self._body, {"phase": "PROFILE", "artifact": deepcopy(doc["artifact"])}) is None,
                 "INDEPENDENT_OWNER_ADMISSION_REQUIRED")
        return doc, manifest, model

    def verify_snapshot(self, *, source_receipt, feature_capture_receipt,
                        query_projection_sha256, information_cutoff_utc):
        """Owned hashes prove bytes; the real owner separately admits this source."""
        request = dict(phase="CURRENT_SNAPSHOT", point_profile_sha256=self.sha256,
            source_receipt=deepcopy(source_receipt),
            feature_capture_receipt=deepcopy(feature_capture_receipt),
            query_projection_sha256=query_projection_sha256,
            information_cutoff_utc=information_cutoff_utc)
        _require(self._verify_owner(self._body, request) is None,
                 "INDEPENDENT_OWNER_SNAPSHOT_ADMISSION_REQUIRED")


def bind_profile(session, document, *, verify_owner_admission):
    """Owner-only hook AFTER its real policy/lease/restoration checks.

    ``verify_owner_admission`` must independently authenticate the registered
    profile bytes against the actual existing owner policy and admission receipt,
    and return None or raise. There is no JSON/boolean-only admission path. The
    production entry point must never take this callback from a client request.
    """
    _require(callable(verify_owner_admission), "INDEPENDENT_OWNER_VERIFIER_REQUIRED")
    _require(type(document) is dict and set(document) == PROFILE_KEYS,
             "CLOSED_POINT_PROFILE_REQUIRED")
    doc = deepcopy(document)
    manifest, model = _prepared(session, doc["artifact"])
    _require(doc["schema_version"] == PROFILE_VERSION
             and doc["selection_product"] == "stat_point_mae_v2"
             and doc["selection_metric"] == "MAE"
             and doc["target"] == doc["scoring_target"] == manifest["category"]["target"]
             and doc["base_learner_id"] == manifest["method_id"]
             and _identifier(doc["method_id"]) and doc["method_id"] != manifest["method_id"],
             "EXACT_NEW_TYPED_POINT_VIEW_REQUIRED")
    _require(doc["base_procedure_version"] == manifest["procedure_version"]
             and _hash(doc["owner_admission_receipt_sha256"])
             and doc["feature_schema_sha256"] == feature_schema(manifest)
             and doc["adapter_pins"] == implementation_pins()
             and doc["adapter_pins"]["next_checkpoint_median_policy_v2_view.py"] == CONTRACT_SHA256
             and doc["procedure_version"] == view_procedure(doc), "POINT_RECIPE_BINDING_REQUIRED")
    roles = doc["public_roles"]
    _require(type(roles) is list and roles and len(roles) == len(set(roles))
             and all(_identifier(x) for x in roles)
             and set(roles) <= set(manifest["category"]["primary_roles"])
             and set(roles) <= set(manifest["category"]["modeled_roles"]),
             "REGISTERED_PUBLIC_ROLE_SUBSET_REQUIRED")
    _clock(doc["registered_at"])
    body = _canonical(doc)
    _require(verify_owner_admission(body, {"phase": "PROFILE", "artifact": deepcopy(doc["artifact"])}) is None,
             "INDEPENDENT_OWNER_ADMISSION_REQUIRED")
    return AdmittedProfile(body, session, model, verify_owner_admission, _ADMITTED)


def _snapshot(session, frame, manifest, context, source_receipt):
    """Read owned metadata only; legacy prediction still validates all its guards."""
    _require(type(context) is dict and set(context) == CONTEXT_KEYS
             and context["evidence_lane"] == "original_pregame"
             and context["reference_stream"] == "candidate", "EXACT_ORIGINAL_FUTURE_CONTEXT_REQUIRED")
    _require(isinstance(frame, pd.DataFrame) and 0 < len(frame) <= MAX_ROWS,
             "BOUNDED_COMPLETE_QUERY_REQUIRED")
    clean = legacy.query_projection(frame, manifest["features"])
    for row in clean.to_dict("records"):
        _require(all(_identifier(row[n]) for n in
                     ("game_id", "player_id", "team", "opponent", "position")),
                 "FINITE_CANONICAL_QUERY_IDENTITY_REQUIRED")
        _require(type(row["season"]) is int and 1900 <= row["season"] <= 2200
                 and type(row["week"]) is int and 1 <= row["week"] <= 22,
                 "FINITE_CANONICAL_QUERY_IDENTITY_REQUIRED")
        for name in ("kickoff_utc", "cutoff_utc"):
            value = row[name]
            _clock(value.isoformat() if isinstance(value, datetime) else value)
    _require(_identifier(context["slate_id"]) and _hash(context["query_source_sha256"]),
             "EXACT_QUERY_CONTEXT_IDENTITY_REQUIRED")
    source = _metadata(session, source_receipt, cap=2 << 20)
    _require(source["schema_version"] == "audit-weekly-runtime-v1-source"
             and source["state"] == "FRESH_E7_SOURCE_PREPARED"
             and source["fits"] == source["protected_confirmation_reads"] == 0,
             "ACTUAL_OWNED_CURRENT_SOURCE_REQUIRED")
    information = _clock(source["asof_utc"])
    began, finished = map(_clock, (source["actual_source_started_at"], source["actual_completed_at"]))
    _require(began <= information <= finished, "ACTUAL_SOURCE_SNAPSHOT_CLOCKS_REQUIRED")
    capture_ref = context["feature_capture_receipt"]
    capture = _metadata(session, capture_ref)
    _require(capture["schema_version"] == "weekly-feature-capture-v1"
             and capture["source_contract"] == context["source_contract"] == manifest["source_contract"]
             and capture["query_projection_sha256"] == legacy.frame_digest(clean)
             and context["query_source_sha256"] == capture["feature_binding"]["sha256"],
             "EXACT_CURRENT_FEATURE_QUERY_SOURCE_BINDING_REQUIRED")
    feature_time = _clock(capture["feature_persist_completed_at"])
    _require(finished <= feature_time, "FEATURE_CAPTURE_PRECEDES_SOURCE_COMPLETION")
    raw = source["raw"]
    _require(type(raw) is dict and 0 < len(raw) <= 64
             and set(raw) == set(source["manifest"]["source_receipts"]),
             "COMPLETE_CURRENT_SOURCE_REFERENCE_CENSUS_REQUIRED")
    raw_refs = [_reference(x) for x in raw.values()]
    _require(sorted(raw_refs, key=lambda r: r["path"])
             == sorted(capture["source_bindings"], key=lambda r: r["path"]),
             "FEATURE_CAPTURE_DIFFERS_FROM_ACTUAL_SOURCE_SNAPSHOT")
    for name, receipt in source["manifest"]["source_receipts"].items():
        _require(receipt["status"] == "acquired" and receipt["sha256"] == raw[name]["sha256"]
                 and receipt["bytes"] == raw[name]["bytes"]
                 and _clock(receipt["retrieved_utc"]) <= information,
                 "SOURCE_RECEIPT_AFTER_INFORMATION_CUTOFF_OR_DIFFERENT_BYTES")
    refs = [source_receipt, capture_ref, capture["feature_binding"], *raw_refs]
    session._verify(refs)
    if "parent_shared_capture" in capture:
        parent = _metadata(session, capture["parent_shared_capture"])
        _require(parent["feature_binding"] == capture["feature_binding"]
                 and parent["source_bindings"] == capture["source_bindings"]
                 and parent["source_contract"] == capture["source_contract"]
                 and parent["feature_persist_completed_at"] == capture["feature_persist_completed_at"],
                 "ORIGINAL_SHARED_CAPTURE_BINDING_CHANGED")
    deadline = _clock(context["cutoff_utc"])
    _require(feature_time < deadline and information < deadline,
             "SOURCE_OR_FEATURE_CAPTURE_AFTER_ISSUE_DEADLINE")
    for raw_clock in clean.feature_max_source_available_utc:
        if pd.isna(raw_clock):
            continue  # Unchanged legacy check rejects warm unknown availability.
        stamp = raw_clock.isoformat() if isinstance(raw_clock, datetime) else raw_clock
        _require(_clock(stamp) <= information, "FEATURE_AVAILABLE_AFTER_INFORMATION_CUTOFF")
    return clean, source, capture, information, deadline, refs


def _law_values(model, part, legacy_rows, target):
    values, seen = {}, set()
    for positions, law, reasons in model.predict_batches(part, batch_size=256):
        positions = np.asarray(positions)
        _require(positions.ndim == 1 and np.issubdtype(positions.dtype, np.integer)
                 and len(positions) == len(reasons), "COMPLETE_VALID_LAW_POSITIONS_REQUIRED")
        _require(all(0 <= int(i) < len(part) and int(i) not in seen for i in positions)
                 and len(set(map(int, positions))) == len(positions),
                 "DUPLICATE_OR_INVALID_LAW_POSITION")
        extracted = full_law_functionals(law, target=target) if law is not None else None
        _require(extracted is None or len(extracted["median"]) == len(positions),
                 "LAW_POPULATION_DIFFERS_FROM_QUERY")
        for j, raw_position in enumerate(positions):
            i = int(raw_position); seen.add(i); row = legacy_rows[i]
            _require(str(reasons[j]) == row["fallback_reason"], "ORIGINAL_FALLBACK_CHANGED")
            if extracted is None:
                _require(row["forecast_value"] is None, "MISSING_LAW_HAS_LEGACY_VALUE")
                values[i] = None
                continue
            mean, median = extracted["expected_mean"][j], extracted["median"][j]
            old = mean if target in COUNT else median
            _require(type(row["forecast_value"]) in (int, float)
                     and np.asarray([row["forecast_value"]], dtype="<f8").tobytes()
                     == np.asarray([old], dtype="<f8").tobytes(), "LEGACY_FUNCTIONAL_BITS_CHANGED")
            values[i] = dict(median=median, mean=mean,
                proof=dict(extractor_version=FUNCTIONAL_VERSION,
                    cdf_below=extracted["cdf_below_median"][j], cdf_at=extracted["cdf_at_median"][j]))
    _require(seen == set(range(len(part))), "INCOMPLETE_LAW_POPULATION")
    return values


def predict_point_chunks(session, profile, frame, *, context, source_receipt,
                         batch_size=128, clock=legacy.now_utc):
    """Yield complete private candidates; no partial frame becomes qualified.

    Every original legacy source/query/clock/fit validation executes unchanged.
    A second law traversal uses that same feature-only immutable frame. At most
    MAX_ROWS candidates are buffered; no candidate is yielded until full census
    and final file/code/owner validation succeeds. Persistence/publication and
    actual owner authority are independently required after this function.
    """
    _require(type(profile) is AdmittedProfile, "OWNER_ADMISSION_CAPABILITY_REQUIRED")
    _require(type(batch_size) is int and 1 <= batch_size <= MAX_BATCH,
             "BOUNDED_CHUNK_SIZE_REQUIRED")
    doc, manifest, model = profile.verify(session)
    clean, source, capture, information, deadline, refs = _snapshot(
        session, frame, manifest, context, source_receipt)
    _require(_clock(doc["registered_at"]) <= _clock(source["actual_source_started_at"]),
             "POINT_PROFILE_MUST_PRECEDE_CURRENT_SOURCE_OR_VALUES")
    query_sha = legacy.frame_digest(clean)
    profile.verify_snapshot(source_receipt=source_receipt,
        feature_capture_receipt=context["feature_capture_receipt"],
        query_projection_sha256=query_sha, information_cutoff_utc=information.isoformat())
    candidates, offset = [], 0
    for old_rows in session.predict_chunks(doc["artifact"]["sha256"], clean,
            context=deepcopy(context), batch_size=batch_size, clock=clock):
        _require(type(old_rows) is list and old_rows and offset + len(old_rows) <= len(clean),
                 "LEGACY_COMPLETE_CHUNK_CENSUS_REQUIRED")
        part = clean.iloc[offset:offset + len(old_rows)].copy()
        for i, old in enumerate(old_rows):
            query = part.iloc[i]
            _require(all(old[n] == query[n] for n in ("season", "week", "game_id", "player_id", "team", "opponent", "position"))
                     and old["offered_id"] == legacy.digest({**{n: old[n] for n in legacy.cdf.KEYS}, "category": doc["target"]})
                     and old["model_version"] == old["artifact_sha256"] == doc["artifact"]["sha256"]
                     and old["procedure_version"] == doc["base_procedure_version"]
                     and (old["product"], old["prediction_functional"], old["metric"]) == legacy.product(manifest["category"]),
                     "LEGACY_IDENTITY_ARTIFACT_OR_PRODUCT_CHANGED")
        extracted = _law_values(model, part, old_rows, doc["target"])
        issued = clock()
        _require(isinstance(issued, datetime) and issued.tzinfo is not None
                 and information <= issued < deadline
                 and all(_clock(old["issued_at"]) <= issued for old in old_rows),
                 "ACTUAL_POINT_ISSUANCE_MUST_PRECEDE_DEADLINE")
        for i, old in enumerate(old_rows):
            functional = extracted[i]; value = None if functional is None else functional["median"]
            modeled = old["position"] in manifest["category"]["modeled_roles"]
            row = dict(schema_version=POINT_VERSION, candidate_schema=VERSION,
                selection_product="stat_point_mae_v2", selection_metric="MAE",
                target=doc["target"], scoring_target=doc["scoring_target"], category=doc["target"],
                season=old["season"], week=old["week"], game_id=old["game_id"], player_id=old["player_id"],
                team=old["team"], opponent=old["opponent"], position=old["position"],
                offered_id=old["offered_id"], horizon="player_game", slate_id=old["slate_id"],
                base_learner_id=doc["base_learner_id"], method_id=doc["method_id"],
                model_version=doc["artifact"]["sha256"], model_bytes_sha256=manifest["model"]["sha256"],
                procedure_version=doc["procedure_version"], base_procedure_version=doc["base_procedure_version"],
                point_profile_sha256=profile.sha256, owner_admission_receipt_sha256=doc["owner_admission_receipt_sha256"],
                capture_receipt_sha256=None,
                source_policy_sha256=manifest["source_contract"]["source_policy_sha256"],
                source_contract=deepcopy(manifest["source_contract"]), source_receipt=deepcopy(source_receipt),
                feature_capture_receipt=deepcopy(context["feature_capture_receipt"]),
                feature_binding=deepcopy(capture["feature_binding"]), query_projection_sha256=query_sha,
                query_source_sha256=old["query_source_sha256"], information_cutoff_utc=information.isoformat(),
                issue_deadline_utc=deadline.isoformat(), cutoff_utc=deadline.isoformat(),
                issued_at=issued.isoformat(), legacy_issued_at=old["issued_at"], kickoff_utc=old["kickoff_utc"],
                feature_max_source_available_utc=old["feature_max_source_available_utc"],
                forecast_product="point_median", prediction_functional="full_cdf_lower_median",
                forecast_value=value, separate_expected_mean=None if functional is None else functional["mean"],
                functional_proof=None if functional is None else functional["proof"],
                fallback=old["fallback"], fallback_reason=old["fallback_reason"],
                trained_prior_only=bool(old["fallback"] and functional is not None),
                original_contract_version=legacy.VERSION, original_forecast=deepcopy(old),
                consumer_contract_version=POINT_VERSION, evidence_lane="original_pregame",
                complete_query_rows=len(clean), query_row_ordinal=offset + i,
                modeled_role=modeled, public_role=old["position"] in doc["public_roles"],
                operational_eligible=bool(old["operational_eligible"] and modeled and value is not None),
                public_scope_eligible=bool(old["operational_eligible"] and value is not None and old["position"] in doc["public_roles"]),
                conditional_on="played", participation_state="unknown", scientific_qualification=False,
                capture_state="PRIVATE_CANDIDATE_REQUIRES_DURABLE_COMPLETION_AND_RESTORE",
                public_export_authorized=False)
            _require(_clock(row["issue_deadline_utc"]) < _clock(row["kickoff_utc"]),
                     "POINT_DEADLINE_MUST_PRECEDE_KICKOFF")
            row["candidate_sha256"] = _digest(row)
            candidates.append(row)
        offset += len(old_rows)
    _require(offset == len(clean) and len({r["offered_id"] for r in candidates}) == len(clean),
             "INCOMPLETE_OR_DUPLICATE_LEGACY_POPULATION")
    _require(legacy.frame_digest(clean) == query_sha, "QUALIFIED_QUERY_MUTATED")
    profile.verify(session)
    session._verify(refs, force=True)
    for start in range(0, len(candidates), batch_size):
        yield candidates[start:start + batch_size]
