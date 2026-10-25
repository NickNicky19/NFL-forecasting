"""Metadata-only software correction; no provider/model reads, fits or network.

All input documents/proofs must first be authenticated by the parent's existing
private client. Hashes here bind those documents; they do not grant authority or
prove remote durability. The metadata barrier is an actual owned-CAS write and
readback. A separate qualified restore proof covers effective18 MODELS ONLY.
No remote metadata round trip is required before capture. Remote durability of
the complete captured bundle is checked later by the parent's existing route.
The old generic restore_choices API and all original evidence remain untouched.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import re

from . import weekly_adaptive as selector, weekly_generic_producer as generic
from .state import canonical, digest, now_utc, utc

VERSION = "audit-weekly-correction-epoch-v1"
FAMILIES = {"LAB_CDF": "leaf_cdf_base", "COUNT_A": "count_A", "CATBOOST_MEDIUM": "catboost_medium"}
PIN_PATHS = ("nfl_lab/audit_weekly_epoch_v1.py", "nfl_lab/audit_weekly_origin_v1.py",
    "nfl_lab/weekly_generic_producer.py", "nfl_lab/weekly_adaptive.py")
HASH = re.compile(r"[a-f0-9]{64}\Z")
CAP = 512 << 10
CAS_ROLES = {"EPOCH_METADATA": {"epoch"}, "CHOICE_AND_SELECTED_VERSIONS": {"choice", "selected_versions"}}


class EpochError(ValueError):
    """Fixed ASCII guards only; never include private library/input text."""


def require(condition, code):
    if not condition:
        raise EpochError(code)


def implementation_pins():
    root = Path(__file__).resolve().parents[1]
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in PIN_PATHS}


def _hash(value):
    return type(value) is str and HASH.fullmatch(value) is not None


def _binding(value):
    return (type(value) is dict and set(value) == {"bytes", "sha256"}
            and type(value["bytes"]) is int and 0 <= value["bytes"] <= 1 << 30 and _hash(value["sha256"]))


def _decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= CAP, "BOUNDED_ORIGINAL_CHOICE_BYTES_REQUIRED")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_CHOICE_JSON_KEY")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(EpochError("NONFINITE_CHOICE_JSON")))
    except (ValueError, UnicodeError) as error:
        if isinstance(error, EpochError):
            raise
        raise EpochError("INVALID_ORIGINAL_CHOICE_JSON") from None


def _signature(selections):
    result = []
    for selected in selections:
        members = selected["members"]
        require(type(members) is list and len(members) <= 4
            and len({m["method_id"] for m in members}) == len(members), "UNIQUE_BOUNDED_ORIGINAL_MEMBERS_REQUIRED")
        require(all(type(m["weight"]) in (int, float) and math.isfinite(m["weight"]) and m["weight"] > 0
            for m in members) and (not members or math.isclose(math.fsum(m["weight"] for m in members), 1., abs_tol=1e-12)),
            "ORIGINAL_WEIGHTS_MUST_BE_POSITIVE_AND_SUM_TO_ONE")
        result.append(dict(category=selected["decision"]["category"], state=selected["state"],
            members=[dict(method_id=m["method_id"], weight=m["weight"]) for m in members]))
    return result


def _origin(raw, completion, slate, catalog, policy, history_binding, now):
    require(type(raw) is bytes and 0 < len(raw) <= CAP and type(completion) is dict,
        "EXACT_ORIGINAL_DURABLE_CHOICE_REQUIRED")
    derived=completion.get("schema_version")=="audit-weekly-origin-v1-terminal-witness"
    if derived:
        # The old completion FILE was not archived. A newly created witness
        # authenticates the original source-bound terminal's choice-write
        # event; it never masquerades as that missing physical receipt.
        from .audit_weekly_origin_v1 import validate_terminal_witness
        try:
            persisted=validate_terminal_witness(completion,raw,slate,catalog,policy,now)
        except Exception:
            raise EpochError("SOURCE_BOUND_ORIGINAL_TERMINAL_WITNESS_REQUIRED") from None
    else:
        require(completion.get("schema_version") == generic.VERSION + "-weekly-choice-completion"
            and isinstance(completion.get("choice_binding"), dict)
            and completion["choice_binding"].get("bytes") == len(raw)
            and completion["choice_binding"].get("sha256") == hashlib.sha256(raw).hexdigest()
            and completion.get("original_predeadline_completion") is None, "EXACT_ORIGINAL_DURABLE_CHOICE_REQUIRED")
        persisted=utc(completion["persisted_completed_at"])
    choice = _decode(raw)
    require(type(choice) is dict, "ORIGINAL_CHOICE_OBJECT_REQUIRED")
    require(utc(choice["actual_frozen_at"]) <= persisted < utc(slate["weekly_deadline_utc"])
        and persisted < now and _binding(history_binding), "ORIGINAL_PREDEADLINE_COMPLETION_AND_HISTORY_ANCHOR_REQUIRED")
    try:
        generic.restore_choices(choice, slate=slate, catalog=catalog, policy=policy, selector=selector, now=now)
        selector.Panel(dict(schema_version=selector.VERSION, offers=[], forecasts=[], outcomes=[], decisions=[], weeks=[]), catalog)
    except (KeyError, TypeError, ValueError):
        raise EpochError("ORIGINAL_WEEKLY_CHOICE_CATALOG_POLICY_BINDING_FAILED") from None
    for selected in choice["selections"]:
        require(selected["policy"] == "P2" and selected["implementation_revision"] == selector.IMPLEMENTATION_REVISION
            and selected["decision"]["evidence_lane"] == "original_pregame"
            and selected["state"] in {"SELECTED", "ABSTAIN_NO_ELIGIBLE_PROCEDURE"}
            and bool(selected["members"]) is (selected["state"] == "SELECTED"), "ORIGINAL_LIVE_P2_CHOICE_REQUIRED")
        for member in selected["members"]:
            require(member["method_id"] in catalog["categories"][selected["decision"]["category"]]["eligible_methods"]
                and member["procedure_version"] == catalog["methods"][member["method_id"]]["procedure_version"],
                "ORIGINAL_MEMBER_PROCEDURE_MISMATCH")
    signature = _signature(choice["selections"])
    return deepcopy(dict(choice=choice, completion=completion, slate=slate, catalog=catalog, policy=policy,
        history_binding=history_binding, signature=signature,
        choice_file=dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())))


def _replay(document):
    from .audit_count_checkpoint_v1 import safe_replay_catalog
    try:
        safe_replay_catalog(document)
    except Exception:
        raise EpochError("QUALIFIED_EFFECTIVE18_REPLAY_METADATA_REQUIRED") from None
    return deepcopy(document)


def _new_catalog(origin, replay, registered, controls):
    result = deepcopy(origin["catalog"])
    slots = replay["slots"]
    require(set(result["categories"]) - {"fantasy_ppr"} == {s["target"] for s in slots}
        and set(result["methods"]) <= set(FAMILIES) | {"R0", "RAW"}
        and set(FAMILIES) <= set(result["methods"]), "FIXED_EFFECTIVE_CATEGORY_METHOD_UNIVERSE_REQUIRED")
    require(type(controls) is dict and set(controls) <= set(result["methods"]) & {"R0", "RAW"},
        "ONLY_EXISTING_EXPLICIT_CONTROL_IDS_MAY_BE_REGISTERED")
    for method, spec in controls.items():
        fields = {"procedure_version", "model_versions", "procedure_operational_eligible", "procedure_replay_eligible",
            "role", "training_state", "control_policy_sha256", "control_source_version"}
        require(type(spec) is dict and fields <= set(spec) <= fields | {"event_contract"}
            and _hash(spec["procedure_version"]) and type(spec["model_versions"]) is list
            and 1 <= len(spec["model_versions"]) == len(set(spec["model_versions"])) <= 16
            and all(_hash(v) for v in spec["model_versions"])
            and spec["procedure_operational_eligible"] is True and spec["procedure_replay_eligible"] is False
            and spec["role"] == ("reference" if method == "R0" else "raw_control")
            and spec["training_state"] == "UPSTREAM_TRAINING_UNOBSERVED" and _hash(spec["control_policy_sha256"])
            and type(spec["control_source_version"]) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", spec["control_source_version"]),
            "EXPLICIT_OBSERVED_CONTROL_METADATA_REQUIRED_NO_INVENTED_FIT_CLOCK")
        require(spec.get("event_contract") in (None, selector.ANYTIME_EVENT_CONTRACT), "EXACT_TD_CONTROL_EVENT_REQUIRED")
        result["methods"][method] = deepcopy(spec)
        if method == "R0" and spec.get("event_contract"):
            result["categories"]["anytime_td"]["event_contract"] = spec["event_contract"]
    for method, spec in result["methods"].items():
        spec["registered_at"] = registered
        require(not spec.get("retired_at"), "RETIRED_PROCEDURE_NEEDS_SEPARATE_AUTHORITY")
        if method in FAMILIES:
            rows = [s for s in slots if s["method_id"] == method]
            procedures = {s["procedure_version"] for s in rows}
            require(len(procedures) == 1 and spec["procedure_version"] not in procedures,
                "NEW_EFFECTIVE_PROCEDURE_REQUIRED_NO_SAME_PROCEDURE_EPOCH_RESET")
            spec.update(procedure_version=next(iter(procedures)),
                model_versions=sorted({s["manifest_sha256"] for s in rows}),
                procedure_operational_eligible=True, procedure_replay_eligible=False)
    for target, spec in result["categories"].items():
        if target == "fantasy_ppr":
            continue
        require(set(spec["shortlist"]) == {s["method_id"] for s in slots if s["target"] == target},
            "UNCHANGED_CLOSED_CATEGORY_SHORTLIST_REQUIRED")
    selector.Panel(dict(schema_version=selector.VERSION, offers=[], forecasts=[], outcomes=[], decisions=[], weeks=[]), result)
    return result


@dataclass(frozen=True)
class CorrectionEpoch:
    document: dict
    sha256: str
    origin: dict
    origin_sha256: str

    def verify(self):
        require(digest(self.document) == self.sha256 and digest(self.origin) == self.origin_sha256,
            "CORRECTION_EPOCH_OR_ORIGINALS_CHANGED")
        require(self.document["selection_recipe"]["code_pins"] == implementation_pins(), "EPOCH_IMPLEMENTATION_PINS_CHANGED")


def _prepare(origin, replay, registered, controls):
    catalog = _new_catalog(origin, replay, registered, controls)
    recipe = dict(schema_version=VERSION + "-selection-recipe", code_pins=implementation_pins(),
        original_choice_sha256=origin["choice_file"]["sha256"], members=origin["signature"],
        procedure_catalog_sha256=digest(selector.procedure_catalog(catalog)),
        continuation="SAME_FAMILIES_WEIGHTS_NO_RESELECTION",
        recurring="P2_ALL_RESOLVED_PRIOR_CURRENT_EPOCH_WEEKS", current_values_used=False)
    document = dict(schema_version=VERSION, operation="SOFTWARE_CORRECTION_CONTINUATION",
        registered_at_utc=registered, original=dict(choice_file=origin["choice_file"],
            choice_payload_sha256=digest(origin["choice"]), completion_sha256=digest(origin["completion"]),
            catalog_sha256=digest(origin["catalog"]), slate_sha256=digest(origin["slate"]),
            policy_sha256=digest(origin["policy"]), history_binding=origin["history_binding"]),
        replay_catalog=replay, effective_controls=deepcopy(controls), catalog=catalog, selection_recipe=recipe, fits=0,
        original_evidence_preserved=True, old_procedure_losses_inherited=False, scientific_qualification=False)
    require(len(canonical(document)) <= CAP, "FINITE_CORRECTION_METADATA_REQUIRED")
    return CorrectionEpoch(document, digest(document), origin, digest(origin))


def prepare_epoch(original_choice_bytes, original_completion, original_slate, original_catalog, policy, replay_catalog,
        *, history_binding, effective_controls=None, clock=now_utc):
    """Prepare before current values; registration uses this actual clock."""
    now = utc(clock())
    origin = _origin(original_choice_bytes, original_completion, original_slate, original_catalog, policy, history_binding, now)
    return _prepare(origin, _replay(replay_catalog), now.isoformat(), {} if effective_controls is None else effective_controls)


def restore_epoch(document, original_choice_bytes, original_completion, original_slate, original_catalog, policy,
        *, history_binding, now):
    """Replay authenticated metadata without re-registering its earlier clock."""
    registered = utc(document["registered_at_utc"])
    require(registered <= utc(now), "FUTURE_CORRECTION_REGISTRATION")
    origin = _origin(original_choice_bytes, original_completion, original_slate, original_catalog, policy, history_binding, registered)
    result = _prepare(origin, _replay(document["replay_catalog"]), registered.isoformat(), document["effective_controls"])
    require(result.document == document, "EXACT_ORIGINAL_CORRECTION_METADATA_REQUIRED")
    return result


def owned_cas_readback(storage, bindings, expected, *, scope, written_at, clock=now_utc):
    """Read actual immutable CAS aliases after the existing budgeted writer.

bindings maps the closed scope's roles to {path,bytes,sha256}; expected maps the
same roles to their metadata documents. No write, HTTP or model read occurs.
The receipt intentionally contains no path and claims no remote durability.
"""
    from .owned_reference_batch import validate_owned_references
    require(scope in CAS_ROLES and set(bindings) == set(expected) == CAS_ROLES[scope], "CLOSED_CAS_METADATA_SCOPE_REQUIRED")
    start = utc(clock())
    require(utc(written_at) <= start, "CAS_WRITE_MUST_PRECEDE_READBACK")
    for reference in bindings.values():
        require(type(reference) is dict and set(reference) == {"path", "bytes", "sha256"}
            and type(reference["path"]) is str and Path(reference["path"]).is_absolute()
            and type(reference["bytes"]) is int and 0 < reference["bytes"] <= CAP and _hash(reference["sha256"]),
            "CLOSED_BOUNDED_CAS_METADATA_BINDING_REQUIRED")
    try:
        owned, validation = validate_owned_references(storage, {r["path"]: r["sha256"] for r in bindings.values()})
        rows = []
        for role, reference in sorted(bindings.items()):
            require(owned[reference["path"]]["bytes"] == reference["bytes"], "CAS_METADATA_SIZE_CHANGED")
            raw = Path(reference["path"]).read_bytes()
            require(len(raw) == reference["bytes"] and hashlib.sha256(raw).hexdigest() == reference["sha256"], "CAS_METADATA_READBACK_CHANGED")
            value = _decode(raw)
            require(value == expected[role], "CAS_METADATA_PAYLOAD_CHANGED")
            rows.append(dict(role=role, binding={k: reference[k] for k in ("bytes", "sha256")}, payload_sha256=digest(value)))
        end = utc(clock())
        require(start <= end, "CAS_READBACK_CLOCK_REVERSED")
        return dict(schema_version=VERSION + "-owned-cas-readback", scope=scope,
            owner_identity_sha256=digest(dict(control_root=str(storage.control_root))),
            owned_validation_sha256=digest(validation), write_completed_at=utc(written_at).isoformat(),
            readback_started_at=start.isoformat(), readback_completed_at=end.isoformat(), documents=rows,
            remote_durability_qualified=False)
    except EpochError:
        raise
    except Exception:
        raise EpochError("ACTUAL_OWNED_CAS_METADATA_READBACK_REQUIRED") from None


def _cas(receipt, scope, expected, earliest, now):
    fields = {"schema_version", "scope", "owner_identity_sha256", "owned_validation_sha256", "write_completed_at",
        "readback_started_at", "readback_completed_at", "documents", "remote_durability_qualified"}
    require(type(receipt) is dict and set(receipt) == fields and receipt["schema_version"] == VERSION + "-owned-cas-readback"
        and receipt["scope"] == scope and receipt["remote_durability_qualified"] is False
        and all(_hash(receipt[k]) for k in ("owner_identity_sha256", "owned_validation_sha256"))
        and type(receipt["documents"]) is list and len(receipt["documents"]) == len(expected), "EXACT_LOCAL_CAS_READBACK_RECEIPT_REQUIRED")
    require(len({r["role"] for r in receipt["documents"]}) == len(expected)
        and {r["role"] for r in receipt["documents"]} == set(expected), "COMPLETE_LOCAL_CAS_METADATA_ROLES_REQUIRED")
    for row in receipt["documents"]:
        require(set(row) == {"role", "binding", "payload_sha256"} and _binding(row["binding"])
            and 0 < row["binding"]["bytes"] <= CAP and row["payload_sha256"] == expected[row["role"]],
            "EXACT_LOCAL_CAS_METADATA_PAYLOAD_REQUIRED")
    require(utc(earliest) <= utc(receipt["write_completed_at"]) <= utc(receipt["readback_started_at"])
        <= utc(receipt["readback_completed_at"]) < now, "LOCAL_CAS_METADATA_MUST_BE_WRITTEN_AND_READ_BEFORE_USE")


def _artifact_proof(proof, replay_sha256):
    require(type(proof) is dict and set(proof) == {"scope", "proof_sha256", "replay_catalog_sha256", "model_pairs"}
        and proof["scope"] == "EFFECTIVE18_MODELS_ONLY" and _hash(proof["proof_sha256"])
        and proof["replay_catalog_sha256"] == replay_sha256 and type(proof["model_pairs"]) is int and proof["model_pairs"] == 18,
        "QUALIFIED_ARTIFACT_PROOF_SCOPE_IS_MODELS_ONLY")


@dataclass(frozen=True)
class RegisteredEpoch:
    epoch: CorrectionEpoch
    completion: dict
    completion_sha256: str

    def verify(self, now):
        self.epoch.verify()
        require(digest(self.completion) == self.completion_sha256, "EPOCH_REGISTRATION_COMPLETION_CHANGED")
        _completion(self.epoch, self.completion, utc(now))


def _completion(epoch, receipt, now):
    require(type(receipt) is dict and set(receipt) == {"schema_version", "epoch_sha256", "catalog_sha256",
        "selection_recipe_sha256", "persisted_completed_at", "owner_registration_sha256", "qualified_artifact_restore",
        "metadata_cas_readback", "metadata_remote_durability_qualified", "current_values_used", "fits"}
        and receipt["schema_version"] == VERSION + "-registration-completion"
        and receipt["epoch_sha256"] == epoch.sha256 and receipt["catalog_sha256"] == digest(epoch.document["catalog"])
        and receipt["selection_recipe_sha256"] == digest(epoch.document["selection_recipe"])
        and _hash(receipt["owner_registration_sha256"]) and receipt["metadata_remote_durability_qualified"] is False
        and receipt["current_values_used"] is False and type(receipt["fits"]) is int and receipt["fits"] == 0,
        "EXACT_AUTHENTICATED_EPOCH_COMPLETION_REQUIRED")
    _cas(receipt["metadata_cas_readback"], "EPOCH_METADATA", {"epoch": epoch.sha256}, epoch.document["registered_at_utc"], now)
    _artifact_proof(receipt["qualified_artifact_restore"], digest(epoch.document["replay_catalog"]))
    require(receipt["persisted_completed_at"] == receipt["metadata_cas_readback"]["readback_completed_at"],
        "EPOCH_COMPLETION_IS_LOCAL_CAS_READBACK_TIME")


def bind_registration(epoch, completion, *, now):
    require(type(epoch) is CorrectionEpoch, "TYPED_CORRECTION_EPOCH_REQUIRED")
    epoch.verify(); _completion(epoch, completion, utc(now))
    return RegisteredEpoch(epoch, deepcopy(completion), digest(completion))


def artifact_catalog(epoch, *relocated_replays):
    """Same model/procedure, new path SHA: union versions, retain every old one."""
    epoch.verify()
    require(len(relocated_replays) <= 8, "FINITE_RELOCATION_CATALOG_REQUIRED")
    originals = epoch.document["replay_catalog"]["slots"]
    catalog = deepcopy(epoch.document["catalog"])
    versions = {(s["target"], s["method_id"]): {s["manifest_sha256"]} for s in originals}
    proofs = [digest(epoch.document["replay_catalog"])]
    for supplied in relocated_replays:
        replay = _replay(supplied); proofs.append(digest(replay))
        for old, new in zip(originals, replay["slots"]):
            require(all(old[k] == new[k] for k in ("target", "family", "method_id", "procedure_version",
                "model_sha256", "transport_manifest_sha256")), "RELOCATION_MUST_PRESERVE_EFFECTIVE_MODEL_AND_PROCEDURE")
            versions[old["target"], old["method_id"]].add(new["manifest_sha256"])
            catalog["methods"][old["method_id"]]["model_versions"].append(new["manifest_sha256"])
    for spec in catalog["methods"].values():
        spec["model_versions"] = sorted(set(spec["model_versions"]))
        require(len(spec["model_versions"]) <= 256, "FINITE_EPOCH_ARTIFACT_VERSIONS_REQUIRED")
    return dict(schema_version=VERSION + "-artifact-catalog", epoch_sha256=epoch.sha256, catalog=catalog,
        replay_catalog_sha256=proofs, slots=[dict(target=t, method_id=m, manifest_versions=sorted(v)) for (t, m), v in sorted(versions.items())])


def _artifacts(epoch, replays):
    result = artifact_catalog(epoch, *replays)
    require(digest(selector.procedure_catalog(result["catalog"])) == digest(selector.procedure_catalog(epoch.document["catalog"])),
        "RELOCATION_CHANGED_EPOCH_PROCEDURE_CATALOG")
    return result


def _p2_members(selected, panel, policy):
    """Validate restored recipes without reading current values or reselecting."""
    members, state = selected.get("members"), selected.get("state")
    require(type(members) is list and len(members) <= 2 and type(state) is str
        and state in {"SELECTED", "ABSTAIN_NO_ELIGIBLE_PROCEDURE"}
        and bool(members) is (state == "SELECTED"), "CLOSED_P2_MEMBER_STATE_REQUIRED")
    if not members:
        return  # Preserving an earlier abstention does not select newly available procedures.
    decision = selected["decision"]; target = decision["category"]
    category = panel.categories[target]
    universe = category.get("eligible_methods", [category["reference_id"], *category["shortlist"]])
    names = []
    for member in members:
        require(type(member) is dict and set(member) == {"method_id", "procedure_version", "choice_eligible", "weight"}
            and type(member["method_id"]) is str and member["method_id"] in panel.methods
            and member["method_id"] in universe and type(member["procedure_version"]) is str and bool(member["procedure_version"])
            and member["procedure_version"] == panel.methods[member["method_id"]]["procedure_version"]
            and type(member["choice_eligible"]) is bool
            and member["choice_eligible"] is panel.procedure_available(member["method_id"], decision)
            and type(member["weight"]) in (int, float) and math.isfinite(member["weight"])
            and member["weight"] > 0, "CLOSED_P2_MEMBER_CONTRACT_REQUIRED")
        names.append(member["method_id"])
    require(len(set(names)) == len(names), "UNIQUE_P2_MEMBERS_REQUIRED")
    if len(members) == 1:
        require(members[0]["weight"] == 1 and members[0]["choice_eligible"] is True,
            "P2_SINGLETON_MUST_HAVE_UNIT_WEIGHT_AND_BE_ELIGIBLE")
    else:
        configured = next((c for c in policy["categories"] if c["category"] == target), {})
        require(target == "anytime_td" and configured.get("startup_method_id") == "TD_EQUAL_CDF_CAT"
            and policy.get("TD_EQUAL_CDF_CAT", {}).get("members") == {"LAB_CDF": .5, "CATBOOST_MEDIUM": .5}
            and names == ["LAB_CDF", "CATBOOST_MEDIUM"] and all(m["weight"] == .5 for m in members),
            "ONLY_REGISTERED_EQUAL_TD_PAIR_IS_A_P2_BLEND")


@dataclass(frozen=True)
class EpochChoice:
    document: dict
    sha256: str

    def verify(self, registered, now):
        registered.verify(now)
        fields = {"schema_version", "mode", "epoch_sha256", "registration_completion_sha256", "slate", "choice", "current_values_used"}
        routine = {"retained_history_sha256", "resolved_history_view_sha256", "resolved_prior_keys", "legacy_history_binding"}
        require(set(self.document) == (fields | routine if self.document.get("mode") == "ROUTINE_P2_CURRENT_EPOCH" else fields),
            "CLOSED_EPOCH_CHOICE_METADATA_REQUIRED")
        require(digest(self.document) == self.sha256 and self.document["epoch_sha256"] == registered.epoch.sha256
            and self.document["schema_version"] == VERSION + "-choice"
            and self.document["mode"] in {"SOFTWARE_CORRECTION_CONTINUATION", "ROUTINE_P2_CURRENT_EPOCH"}
            and self.document["registration_completion_sha256"] == registered.completion_sha256,
            "EPOCH_CHOICE_CHANGED_OR_DIFFERENT_EPOCH")
        frozen = utc(self.document["choice"]["actual_frozen_at"])
        require(utc(registered.completion["persisted_completed_at"]) < frozen <= utc(now)
            and frozen < utc(self.document["slate"]["scheduled_first_kickoff_utc"]), "HONEST_NEW_CHOICE_CLOCK_REQUIRED")
        if self.document["mode"] == "SOFTWARE_CORRECTION_CONTINUATION":
            require(_signature(self.document["choice"]["selections"]) == registered.epoch.origin["signature"],
                "CONTINUATION_CANNOT_CHANGE_FAMILIES_OR_WEIGHTS")
        require(self.document["current_values_used"] is False, "CHOICE_MUST_PRECEDE_CURRENT_VALUES")
        selections = self.document["choice"]["selections"]
        expected = {r["category"] for r in registered.epoch.origin["signature"]}
        require(len(selections) == len(expected) and {r["decision"]["category"] for r in selections} == expected,
            "COMPLETE_EPOCH_CHOICE_CATEGORIES_REQUIRED")
        panel = selector.Panel(dict(schema_version=selector.VERSION, offers=[], forecasts=[], outcomes=[], decisions=[], weeks=[]),
            registered.epoch.document["catalog"])
        for selected in self.document["choice"]["selections"]:
            require(selected["catalog_sha256"] == digest(selector.procedure_catalog(registered.epoch.document["catalog"]))
                and selected["correction_epoch_sha256"] == registered.epoch.sha256,
                "CHOICE_MUST_BIND_EFFECTIVE_EPOCH_PROCEDURES")
            decision = selected["decision"]
            slate = self.document["slate"]
            require(selected["policy"] == "P2" and selected["implementation_revision"] == selector.IMPLEMENTATION_REVISION
                and decision["evidence_lane"] == "original_pregame" and decision["horizon"] == "player_game"
                and all(decision[k] == slate[k] for k in ("season", "week", "slate_id"))
                and utc(decision["weekly_decision_cutoff_utc"]) == frozen
                and utc(decision["slate_first_kickoff_utc"]) == utc(slate["scheduled_first_kickoff_utc"]),
                "EPOCH_CHOICE_PERIOD_AND_ACTUAL_CLOCKS_REQUIRED")
            _p2_members(selected, panel, registered.epoch.origin["policy"])
            for member in selected["members"]:
                require(member["procedure_version"] == registered.epoch.document["catalog"]["methods"][member["method_id"]]["procedure_version"],
                    "EFFECTIVE_MEMBER_PROCEDURE_CHANGED")


def continue_week(registered, schedule, game_cutoffs, *, clock=now_utc):
    """Keep original weekly families/weights; honest late remaining-game capture."""
    now = utc(clock()); registered.verify(now)
    epoch, origin = registered.epoch, registered.epoch.origin
    old = origin["slate"]
    slate = generic.prepare_slate(schedule, season=old["season"], week=old["week"], game_cutoffs=game_cutoffs, now=now)
    require(slate["schedule_identity_sha256"] == old["schedule_identity_sha256"]
        and set(game_cutoffs) <= set(old["game_cutoffs"]), "ORIGINAL_FULL_SCHEDULE_AND_REMAINING_GAMES_REQUIRED")
    first = min(utc(r["kickoff_utc"]) for r in schedule if r["game_id"] in game_cutoffs
        and r["season"] == old["season"] and r["week"] == old["week"])
    contract = dict(schema_version=VERSION + "-remaining-slate", kind="SOFTWARE_CORRECTION_CONTINUATION",
        epoch_sha256=epoch.sha256, original_slate_sha256=digest(old), original_choice_sha256=origin["choice_file"]["sha256"],
        full_week_first_kickoff_utc=slate["scheduled_first_kickoff_utc"], full_week_deadline_utc=slate["weekly_deadline_utc"],
        original_weekly_deadline_utc=old["weekly_deadline_utc"], registered_at_utc=epoch.document["registered_at_utc"],
        actual_continued_at=now.isoformat(), late_capture=now >= utc(old["weekly_deadline_utc"]))
    slate.update(slate_id=old["slate_id"], scheduled_first_kickoff_utc=first.isoformat(), slate_contract=contract)
    selections = []
    for original in origin["choice"]["selections"]:
        selected = deepcopy(original)
        selected.update(catalog_sha256=digest(selector.procedure_catalog(epoch.document["catalog"])),
            correction_epoch_sha256=epoch.sha256, evidence=dict(reason="SOFTWARE_CORRECTION_CONTINUATION_NO_RESELECTION",
                original_selection_sha256=digest(original), inherited_procedure_losses=False, current_values_used=False))
        selected["decision"].update(weekly_decision_cutoff_utc=now.isoformat(), slate_first_kickoff_utc=first.isoformat(), slate_contract=contract)
        for member in selected["members"]:
            spec = epoch.document["catalog"]["methods"][member["method_id"]]
            member.update(procedure_version=spec["procedure_version"], choice_eligible=spec.get("procedure_operational_eligible") is True)
        selections.append(selected)
    choice = dict(schema_version=VERSION + "-continued-weekly-choice", actual_frozen_at=now.isoformat(), selections=selections,
        original_choice_sha256=origin["choice_file"]["sha256"], policy_sha256=digest(origin["policy"]))
    document = dict(schema_version=VERSION + "-choice", mode="SOFTWARE_CORRECTION_CONTINUATION", epoch_sha256=epoch.sha256,
        registration_completion_sha256=registered.completion_sha256, slate=slate, choice=choice, current_values_used=False)
    result = EpochChoice(document, digest(document)); result.verify(registered, now)
    return result


def selected_versions(registered, choice, *, relocated_replays=(), now):
    choice.verify(registered, now)
    epoch = registered.epoch; artifacts = _artifacts(epoch, relocated_replays); catalog = artifacts["catalog"]
    slots = {(r["target"], r["method_id"]): r["manifest_versions"] for r in artifacts["slots"]}
    rows = []
    for selected in choice.document["choice"]["selections"]:
        target = selected["decision"]["category"]; reference = catalog["categories"][target]["reference_id"]
        options = []
        for member in selected["members"]:
            method = member["method_id"]
            pairs = [(method, v) for v in slots.get((target, method), catalog["methods"][method]["model_versions"])]
            pairs += [(reference, v) for v in slots.get((target, reference), catalog["methods"][reference]["model_versions"])]
            options.append(list(dict.fromkeys(pairs)))
        require(all(len(option) <= 16 for option in options), "FINITE_PER_MEMBER_EPOCH_VERSION_ALLOWLIST")
        procedure = digest(dict(schema_version=VERSION + "-issued-procedure", epoch_sha256=epoch.sha256,
            selection_recipe_sha256=digest(epoch.document["selection_recipe"]), category=target, members=selected["members"]))
        for combination in product(*options) if options else ():
            require(len(rows) < 256, "FINITE_SELECTED_EPOCH_VERSION_ALLOWLIST")
            rows.append(dict(category=target, method_id="P2_SELECTED", procedure_version=procedure,
                model_version=digest([(m, v, c["weight"]) for (m, v), c in zip(combination, selected["members"])])))
    return dict(schema_version=VERSION + "-selected-version-catalog", epoch_sha256=epoch.sha256, choice_sha256=choice.sha256,
        artifact_catalog_sha256=digest(artifacts), catalog_sha256=digest(catalog), rows=rows, current_values_used=False)


@dataclass(frozen=True)
class CapturePermit:
    document: dict
    sha256: str

    def verify(self):
        fields = {"schema_version", "epoch_sha256", "choice_sha256", "selected_versions_sha256", "catalog_sha256",
            "metadata_completion_sha256", "actual_capture_authorized_at", "qualified_artifact_restore_proof_sha256",
            "metadata_cas_readback_sha256", "metadata_remote_durability_qualified", "captured_bundle_remote_durability_qualified",
            "game_cutoffs", "fits", "reselect"}
        document = self.document
        require(type(document) is dict and set(document) == fields
            and document["schema_version"] == VERSION + "-capture-permit"
            and all(_hash(document[k]) for k in fields if k.endswith("_sha256"))
            and type(document["fits"]) is int and document["fits"] == 0
            and document["reselect"] is False and document["metadata_remote_durability_qualified"] is False
            and document["captured_bundle_remote_durability_qualified"] is False,
            "CLOSED_COMPLETE_EPOCH_CAPTURE_PERMIT_REQUIRED")
        cutoffs = document["game_cutoffs"]
        require(type(cutoffs) is dict and 0 < len(cutoffs) <= 32
            and all(type(g) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", g) for g in cutoffs),
            "CLOSED_EPOCH_CAPTURE_GAME_CUTOFFS_REQUIRED")
        def clock(value):
            require(type(value) is str and 0 < len(value) <= 40, "TYPED_EPOCH_CAPTURE_PERMIT_CLOCK_REQUIRED")
            try:
                return utc(value)
            except (ValueError, TypeError, OverflowError):
                raise EpochError("INVALID_EPOCH_CAPTURE_PERMIT_CLOCK") from None
        authorized = clock(document["actual_capture_authorized_at"])
        require(all(authorized < clock(cutoff) for cutoff in cutoffs.values()), "FUTURE_EPOCH_CAPTURE_CUTOFFS_REQUIRED")
        require(_hash(self.sha256) and digest(document) == self.sha256, "EPOCH_CAPTURE_PERMIT_CHANGED")


def authorize_capture(registered, choice, completion, *, relocated_replays=(), clock=now_utc):
    """Local owned-CAS metadata barrier; model proof is separate, no remote wait."""
    now = utc(clock()); choice.verify(registered, now)
    versions = selected_versions(registered, choice, relocated_replays=relocated_replays, now=now)
    require(type(completion) is dict and set(completion) == {"schema_version", "choice_sha256", "catalog_sha256",
        "selected_versions_sha256", "persisted_completed_at", "qualified_artifact_restore", "metadata_cas_readback",
        "metadata_remote_durability_qualified", "current_values_used"}
        and completion["schema_version"] == VERSION + "-choice-completion" and completion["choice_sha256"] == choice.sha256
        and completion["catalog_sha256"] == versions["catalog_sha256"]
        and completion["selected_versions_sha256"] == digest(versions) and completion["current_values_used"] is False
        and completion["metadata_remote_durability_qualified"] is False, "EXACT_PERSISTED_CHOICE_AND_VERSION_CATALOG_REQUIRED")
    _cas(completion["metadata_cas_readback"], "CHOICE_AND_SELECTED_VERSIONS", {"choice": choice.sha256, "selected_versions": digest(versions)},
        choice.document["choice"]["actual_frozen_at"], now)
    current_replay = relocated_replays[-1] if relocated_replays else registered.epoch.document["replay_catalog"]
    _artifact_proof(completion["qualified_artifact_restore"], digest(current_replay))
    require(completion["persisted_completed_at"] == completion["metadata_cas_readback"]["readback_completed_at"],
        "CHOICE_COMPLETION_IS_LOCAL_CAS_READBACK_TIME")
    require(utc(choice.document["choice"]["actual_frozen_at"]) <= utc(completion["persisted_completed_at"]) < now
        < min(map(utc, choice.document["slate"]["game_cutoffs"].values())), "ACTUAL_CAPTURE_MUST_FOLLOW_DURABLE_METADATA_AND_PRECEDE_CUTOFFS")
    document = dict(schema_version=VERSION + "-capture-permit", epoch_sha256=registered.epoch.sha256,
        choice_sha256=choice.sha256, selected_versions_sha256=digest(versions), catalog_sha256=versions["catalog_sha256"],
        metadata_completion_sha256=digest(completion), actual_capture_authorized_at=now.isoformat(),
        qualified_artifact_restore_proof_sha256=completion["qualified_artifact_restore"]["proof_sha256"],
        metadata_cas_readback_sha256=digest(completion["metadata_cas_readback"]), metadata_remote_durability_qualified=False,
        captured_bundle_remote_durability_qualified=False, game_cutoffs=deepcopy(choice.document["slate"]["game_cutoffs"]), fits=0, reselect=False)
    permit = CapturePermit(document, digest(document))
    permit.verify()
    return permit


def validate_materialization(permit, *, source_started_at, source_completed_at, issued_at, game_id):
    require(type(permit) is CapturePermit, "TYPED_EPOCH_CAPTURE_PERMIT_REQUIRED")
    permit.verify(); permit = permit.document
    require(permit.get("schema_version") == VERSION + "-capture-permit" and type(permit["fits"]) is int and permit["fits"] == 0
        and permit["reselect"] is False and permit["metadata_remote_durability_qualified"] is False
        and permit["captured_bundle_remote_durability_qualified"] is False,
        "CLOSED_EPOCH_CAPTURE_PERMIT_REQUIRED")
    require(game_id in permit["game_cutoffs"] and utc(permit["actual_capture_authorized_at"]) <= utc(source_started_at)
        <= utc(source_completed_at) <= utc(issued_at) < utc(permit["game_cutoffs"][game_id]),
        "HONEST_CURRENT_CAPTURE_AND_ISSUANCE_CLOCKS_REQUIRED")


def select_next_week(registered, history, slate, previous_choice, *, relocated_replays=(), clock=now_utc):
    """Existing P2 on every resolved prior current-epoch slate, no old losses.

history is an authenticated complete snapshot. Old history remains separately
hash-anchored. Pending slates/revisions remain in that snapshot, not in this
causal view. Every new row carries correction_epoch_sha256 at issuance/grade.
"""
    now = utc(clock()); previous_choice.verify(registered, now)
    epoch = registered.epoch; catalog = _artifacts(epoch, relocated_replays)["catalog"]
    require(type(history) is dict and set(history) == {"schema_version", "epoch_sha256", "legacy_history_binding", "bundle"}
        and history["schema_version"] == VERSION + "-history" and history["epoch_sha256"] == epoch.sha256
        and history["legacy_history_binding"] == epoch.origin["history_binding"], "EXACT_CURRENT_EPOCH_AND_PRESERVED_LEGACY_HISTORY_REQUIRED")
    bundle = history["bundle"]
    require(set(bundle) == {"schema_version", "offers", "forecasts", "outcomes", "decisions", "weeks"}
        and bundle["schema_version"] == selector.VERSION, "CLOSED_CURRENT_EPOCH_HISTORY_BUNDLE_REQUIRED")
    require(slate["season"] == epoch.origin["slate"]["season"] and epoch.origin["slate"]["week"] < slate["week"] <= 18
        and previous_choice.document["slate"]["week"] < slate["week"], "LATER_SAME_SEASON_REG_WEEK_REQUIRED")
    registered_at = utc(epoch.document["registered_at_utc"])
    key = lambda row: (row["category"], row["season"], row["week"], row["slate_id"])
    offers = {o["offered_id"]: o for o in bundle["offers"]}
    require(len(offers) == len(bundle["offers"]), "DUPLICATE_EPOCH_HISTORY_OFFERS")
    for kind in ("offers", "forecasts", "outcomes", "decisions", "weeks"):
        require(all(r.get("correction_epoch_sha256") == epoch.sha256 for r in bundle[kind]), "UNSCOPED_OR_OLD_EPOCH_HISTORY_FORBIDDEN")
    for offer in bundle["offers"]:
        require(offer["season"] == slate["season"] and epoch.origin["slate"]["week"] <= offer["week"] < slate["week"]
            and registered_at < utc(offer["cutoff_utc"]), "ONLY_PRIOR_CURRENT_EPOCH_OFFER_CLOCKS_ALLOWED")
    for row in bundle["forecasts"]:
        require(registered_at < utc(row["issued_at"]) and registered_at <= utc(row["source_capture_completed_at"])
            and row["evidence_lane"] == "original_pregame", "OLD_OR_RECONSTRUCTED_FORECASTS_CANNOT_ENTER_CORRECTED_EPOCH")
    for row in bundle["outcomes"]:
        require(registered_at <= utc(row["available_at"]), "OLD_OUTCOMES_CANNOT_BE_RELABELED_AS_EPOCH_EVIDENCE")
    decisions = {key(d): d for d in bundle["decisions"]}
    require(len(decisions) == len(bundle["decisions"]), "DUPLICATE_EPOCH_HISTORY_DECISIONS")
    for row in [*bundle["decisions"], *bundle["weeks"]]:
        require(row["season"] == slate["season"] and epoch.origin["slate"]["week"] <= row["week"] < slate["week"],
            "ONLY_PRIOR_CURRENT_EPOCH_SLATES_ALLOWED")
    for week in bundle["weeks"]:
        decision = decisions.get(key(week))
        require(decision is not None and registered_at < utc(week["weekly_decision_cutoff_utc"])
            and all(week[k] == decision[k] for k in ("weekly_decision_cutoff_utc", "slate_first_kickoff_utc")),
            "EPOCH_HISTORY_MUST_KEEP_ACTUAL_FROZEN_DECISION_CLOCKS")
    # Validate the complete retained snapshot before copying its resolved view.
    # The temporary Panel is released before the second bounded projection.
    selector.Panel(bundle, catalog)
    eligible = {key(w) for w in bundle["weeks"] if utc(w["completed_at"]) <= utc(w["grade_completed_at"]) < now}
    view = dict(schema_version=selector.VERSION,
        offers=[deepcopy(r) for r in bundle["offers"] if key(r) in eligible],
        forecasts=[deepcopy(r) for r in bundle["forecasts"] if r["offered_id"] in offers and key(offers[r["offered_id"]]) in eligible],
        outcomes=[deepcopy(r) for r in bundle["outcomes"] if r["offered_id"] in offers
            and key(offers[r["offered_id"]]) in eligible and utc(r["available_at"]) < now],
        decisions=[deepcopy(r) for r in bundle["decisions"] if key(r) in eligible],
        weeks=[deepcopy(r) for r in bundle["weeks"] if key(r) in eligible])
    choice = generic.freeze_choices(selector, view, catalog, epoch.origin["policy"], slate,
        actual_choice_at=now, prior_choices=previous_choice.document["choice"]["selections"])
    for selected in choice["selections"]:
        selected["correction_epoch_sha256"] = epoch.sha256
    document = dict(schema_version=VERSION + "-choice", mode="ROUTINE_P2_CURRENT_EPOCH", epoch_sha256=epoch.sha256,
        registration_completion_sha256=registered.completion_sha256, slate=deepcopy(slate), choice=choice, current_values_used=False,
        retained_history_sha256=digest(history), resolved_history_view_sha256=digest(view),
        resolved_prior_keys=[list(k) for k in sorted(eligible)], legacy_history_binding=deepcopy(epoch.origin["history_binding"]))
    result = EpochChoice(document, digest(document)); result.verify(registered, now)
    return result
