"""DRAFT optional core3 display capture. No public export or ranking selection.

NativeContext is minted only by the existing CLI after its real native Root/API/
source checks. BoundDisplay derives its verifier from that context and the actual
backend restored catalog. Request JSON cannot supply an admission callback.
"""
from copy import deepcopy
from pathlib import Path
import json
import re

from nfl_lab import audit_weekly_runtime_v1 as runtime
from nfl_lab import weekly_future_inference as future, weekly_current_inference as current
from nfl_lab import private_draft_store as private, audit_weekly_operations_authority_v1 as operations
from nfl_lab import weekly_mae_point_inference_v2_1 as point
from nfl_lab import stat_point_mae_public_v2_2 as public

VERSION = "weekly-mae-display-runtime-v1"
MAX_CANDIDATE_JSONL_BYTES = 4 << 20
MAX_METADATA_BYTES = 64 << 10
from nfl_lab.weekly_mae_display_profile_v1 import (
    ROOT_V5, REQUEST_V2, REGISTRATION_PATH, TARGETS, HELPERS, CHANGED_LEGACY_PATHS,
    pins, validate_root_extension,
)
_NATIVE = object()


def require(ok, code):
    runtime.require(ok, code)


class NativeContext:
    def __init__(self, authority, root_bytes, proof, env, source_root, key):
        require(key is _NATIVE, "CHECKED_NATIVE_ROOT_CONTEXT_REQUIRED")
        self.authority, self.root_bytes = deepcopy(authority), root_bytes
        self.root, self.proof, self.env = public.strict_json(root_bytes), proof, dict(env)
        self.source_root, self.process = Path(source_root), private.process_identity()
        self.root_sha256 = private.sha(root_bytes)
        self.config = validate_root_extension(self.root, self.source_root)
        self.registration_ref = deepcopy(self.root["mae_registration"])
        self.verify()

    def __reduce__(self):
        raise runtime.RuntimeErrorCode("NATIVE_MAE_CONTEXT_NOT_SERIALIZABLE")

    def verify(self):
        require(self.process == private.process_identity() and private.sha(self.root_bytes) == self.root_sha256
            and self.authority["owner_root_go_sha256"] == self.root_sha256
            and self.authority["source_sha"] == self.root["source_sha"]
            and runtime.utc(self.root["issued_at_utc"]) <= runtime.now_utc() < runtime.utc(self.root["expires_at_utc"]),
            "CURRENT_NATIVE_MAE_ROOT_OR_CLOCK_CHANGED")
        require(self.proof is not None, "LIVE_ROOT_V5_OPERATIONS_PROOF_REQUIRED")
        operations._verify(self.proof, self.env, self.root_bytes)
        require(validate_root_extension(self.root, self.source_root) == self.config, "REGISTERED_MAE_SOURCE_CHANGED")


def checked_context(authority, root_bytes, proof, env, source_root):
    """Internal CLI hook ONLY after context's existing native/API/clean checks."""
    return NativeContext(authority, root_bytes, proof, env, source_root, _NATIVE)


def validate_bridge(bridge, features, binding):
    """Use the actual exact_bridge result; never infer one ID namespace from another."""
    canonical, website, result = set(), set(), {}
    for q in features[future.cdf.KEYS].to_dict("records"):
        key = tuple(q[k] for k in future.cdf.KEYS)
        require(key in bridge and key not in canonical, "UNIQUE_COMPLETE_CANONICAL_MAE_BRIDGE")
        item = bridge[key]
        require(item["gsis_game_id"] == q["game_id"] and item["gsis_id"] == q["player_id"]
            and item["website_player_id"] == item["sleeper_id"]
            and all(type(item[k]) is str and item[k] for k in ("website_game_id", "sleeper_id"))
            and item["identity_binding_sha256"] == runtime.digest({k:v for k,v in item.items() if k != "identity_binding_sha256"}),
            "EXACT_SOURCE_CANONICAL_WEBSITE_BRIDGE_REQUIRED")
        web = (item["website_game_id"], item["sleeper_id"])
        require(web not in website, "DUPLICATE_WEBSITE_MAE_BRIDGE")
        canonical.add(key); website.add(web)
        result[key] = dict(website_game_id=item["website_game_id"], sleeper_id=item["sleeper_id"],
            identity_bridge_sha256=binding["sha256"], identity_binding_sha256=item["identity_binding_sha256"])
    return result


def archive_file_debit(features, records, output):
    """Exact new alias cohort plus known local originals, before new laws.

    Later R0/context members remain unknown here. The final archive must still
    authenticate/count/encode its complete graph before any remote append.
    """
    from nfl_lab import audit_weekly_archive_v1 as archive
    from nfl_lab.operational_storage import _OWNER
    require((archive.MAX_FILES,archive.MAX_GROUPS,archive.codec.MAX_FILES) == (512,8,64),
        "UNCHANGED_ARCHIVE_FILE_AND_GROUP_CAPS_REQUIRED")
    planned = {"prepared/mae-display/PROFILE_CATALOG.json", "prepared/mae-display/CATALOG_COMPLETION.json"}
    planned.update("runtime/mae-display/"+name for name in ("SOURCE_REGISTRY.json","CATALOG_BINDING.json","FINISHED.json"))
    for target in TARGETS:
        planned.update("runtime/mae-display/"+name for name in (
            "status/"+target+".json","candidates/"+target+".jsonl.gz","candidates/"+target+".jsonl.completion.json"))
    descriptors = set()
    for ordinal,_ in enumerate(features.groupby("cutoff_utc",sort=False)):
        for record in records:
            key = runtime.digest(dict(features=record["manifest"]["features"],eligible_roles=record["eligible_roles"]))
            descriptors.add("runtime/mae-display/views/"+str(ordinal)+"/projections/"+key+".json")
        require(len(descriptors)+len(planned) <= archive.MAX_FILES, "MAE_DESCRIPTOR_ARCHIVE_FILE_ALLOCATION_EXHAUSTED")
    planned.update(descriptors)
    known = {"runtime/FINISHED.json","runtime/EXPORT_INPUTS.json"}
    for path in Path(output).rglob("*"):
        if path.is_file() and path.name != _OWNER:
            name = path.relative_to(output).as_posix()
            require(not name.startswith("mae-display/"), "NO_PREEXISTING_DISPLAY_ALIASES")
            known.add("runtime/"+name)
            require(len(known|planned) <= min(archive.MAX_FILES,archive.MAX_GROUPS*archive.codec.MAX_FILES),
                "KNOWN_CAPTURE_PLUS_MAE_ARCHIVE_FILE_ALLOCATION_EXHAUSTED")
    return dict(exact_new_aliases=sorted(planned),projection_descriptors=len(descriptors),
        fixed_runtime_aliases=12,prepared_catalog_aliases=2,known_local_plus_new_files=len(known|planned),
        later_R0_and_context_count="UNKNOWN_FINAL_FULL_ARCHIVE_CENSUS_STILL_REQUIRED")


class DisplaySink:
    """One owned sink/budget; preserve legacy's control reserve and final tail.

    Display controls have their own bounded allowance inside the existing cap.
    Neither a display FINISHED basename nor a failed body may spend legacy's
    reserved capacity. Global physical quota is checked under the same lock.
    """
    LEGACY_TAIL = 64 << 10
    CONTROL_LIMIT = 128 << 10

    def __init__(self, parent, folder):
        self.parent, self.folder, self.control_bytes = parent, Path(folder), 0

    def write_bytes(self, path, body):
        path, body = Path(path), bytes(body)
        require(path.is_relative_to(self.folder), "DISPLAY_OUTPUT_OUTSIDE_OWNED_SIBLING")
        require(len(body) <= (MAX_CANDIDATE_JSONL_BYTES if path.name.endswith(".jsonl.gz") else MAX_METADATA_BYTES),
            "BOUNDED_DISPLAY_SERIALIZED_FILE_REQUIRED")
        control = path == self.folder/"FINISHED.json" or path.parent == self.folder/"status"
        reserve = self.LEGACY_TAIL + (0 if control else self.CONTROL_LIMIT)
        with self.parent.storage.transaction():
            require(not control or self.control_bytes+len(body) <= self.CONTROL_LIMIT,
                "DISPLAY_CONTROL_ALLOCATION_EXHAUSTED")
            require(self.parent.used()+len(body)+self.parent.RESERVE+reserve <= self.parent.maximum,
                "DISPLAY_PRESERVES_LEGACY_OUTPUT_RESERVE")
            usage = self.parent.storage.snapshot()
            require(usage["physical_bytes"]+len(body)+reserve <= usage["limit_bytes"],
                "DISPLAY_PRESERVES_LEGACY_GLOBAL_RESERVE")
            self.parent.write_bytes(path, body)
            if control: self.control_bytes += len(body)


class BoundDisplay:
    def __init__(self, backend, native):
        require(type(native) is NativeContext, "ACTUAL_NATIVE_MAE_CONTEXT_REQUIRED")
        native.verify()
        self.backend, self.native = backend, native
        require(backend.config == native.root["source_config"], "SAME_ROOT_SOURCE_CONFIG_REQUIRED")
        self.records = {}
        slots = {(s["target"],s["method_id"]):s for s in backend.replay["slots"]}
        originals = {(s["target"],s["method_id"]):s for s in backend.restored["origin"]["replay_catalog"]["slots"]}
        for c in native.config["categories"]:
            matches = [r for r in backend.records if r["manifest"]["category"]["target"] == c["target"]
                       and r["manifest"]["method_id"] == "LAB_CDF"]
            require(len(matches) == 1, "EXACT_RESTORED_CORE_DISPLAY_SLOT_REQUIRED")
            record = matches[0]; m = record["manifest"]; old = m.get("requalification", {})
            slot = slots[c["target"], "LAB_CDF"]
            origin = originals[c["target"], "LAB_CDF"]
            require(m["family"] == c["family"] == "leaf_cdf_base" and m["method_id"] == c["base_learner_id"]
                and m["code_pins"] == point.REVIEWED_MODEL_PINS and m["source_contract"] == c["source_contract"]
                and m["features"] == c["features"] and m["training_frame_sha256"] == c["training_frame_sha256"]
                and m["training_cutoff_utc"] == c["training_cutoff_utc"]
                and m["training_max_available_utc"] == c["training_max_available_utc"]
                and m["category"]["support"] == c["support"] and m["category"]["modeled_roles"] == c["modeled_roles"]
                and set(c["public_roles"]) <= set(m["category"]["primary_roles"])
                and old.get("original_manifest", {}).get("sha256") == c["original_manifest_sha256"]
                and old.get("original_model", {}).get("sha256") == c["original_model_sha256"]
                and old.get("original_procedure_version") == c["original_procedure_version"]
                and old.get("fits") == 0 and old.get("parameters_retrained") is False
                and old.get("original_replay_preserved") is True
                and m["procedure_version"] == c["effective_base_procedure_version"]
                and m["model"]["sha256"] == c["effective_model_sha256"]
                and origin["manifest_sha256"] == c["effective_verified_reader_manifest_sha256"]
                and origin["model_sha256"] == c["effective_model_sha256"]
                and origin["procedure_version"] == c["effective_base_procedure_version"]
                and slot["transport_manifest_sha256"] == c["effective_transport_manifest_sha256"]
                and slot["manifest_sha256"] == record["binding"]["sha256"]
                and slot["model_sha256"] == m["model"]["sha256"] and slot["procedure_version"] == m["procedure_version"],
                "ACTUAL_CORE_EFFECTIVE_ORIGINAL_MAPPING_REQUIRED")
            self.records[c["target"]] = record
        self.profiles = {}
        for c in native.config["categories"]:
            r = self.records[c["target"]]; m = r["manifest"]
            doc = dict(schema_version=point.PROFILE_VERSION, selection_product="stat_point_mae_v2", selection_metric="MAE",
                target=c["target"], scoring_target=c["target"], base_learner_id="LAB_CDF",
                method_id="MAE_DISPLAY_LEAF_" + c["target"], artifact=r["binding"],
                base_procedure_version=m["procedure_version"], procedure_version="", feature_schema_sha256=point.feature_schema(m),
                public_roles=c["public_roles"], registered_at=native.root["issued_at_utc"],
                owner_admission_receipt_sha256=native.root_sha256, adapter_pins=point.implementation_pins())
            doc["procedure_version"] = point.view_procedure(doc); self.profiles[c["target"]] = doc
        self.snapshots = {}

    def prepare(self, output, prepared_ref):
        self.native.verify()
        storage = self.backend.storage
        doc = dict(schema_version=VERSION+"-prevalue-catalog", scope="DISPLAY_ONLY_INCUMBENT_RANKING_UNCHANGED",
            root_go_sha256=self.native.root_sha256, registration=self.native.registration_ref,
            prepared=prepared_ref, profiles=self.profiles, current_values_used=False,
            created_at=self.backend.clock().isoformat(), public_export_authorized=False)
        require(len(runtime.canonical(doc)) <= MAX_METADATA_BYTES, "BOUNDED_PREVALUE_MAE_CATALOG_REQUIRED")
        ref = runtime.write(storage, Path(output)/"mae-display"/"PROFILE_CATALOG.json", doc)
        require(runtime.read_owned(storage, ref) == doc, "ACTUAL_MAE_CATALOG_OWNED_READBACK")
        completion = dict(schema_version=VERSION+"-catalog-completion", catalog=ref,
            completed_at=self.backend.clock().isoformat(), current_values_used=False, root_go_sha256=self.native.root_sha256)
        require(len(runtime.canonical(completion)) <= MAX_METADATA_BYTES, "BOUNDED_MAE_CATALOG_COMPLETION_REQUIRED")
        runtime.write(storage, Path(output)/"mae-display"/"CATALOG_COMPLETION.json", completion)

    def _verify_profile(self, body, request):
        self.native.verify()
        doc = public.strict_json(body)
        require(doc == self.profiles.get(doc.get("target")), "EXACT_NATIVE_PREVALUE_POINT_PROFILE_REQUIRED")
        if request.get("phase") == "PROFILE":
            require(request == dict(phase="PROFILE", artifact=doc["artifact"]), "SAME_ACTUAL_PREPARED_CORE_ARTIFACT")
        else:
            require(request.get("phase") == "CURRENT_SNAPSHOT"
                and request == self.snapshots.get((doc["target"],request.get("query_projection_sha256"))),
                "EXACT_NATIVE_CURRENT_MAE_SNAPSHOT_REQUIRED")

    def capture(self, features, capture, capture_ref, source, source_ref, prepared_ref,
                bridge, bridge_ref, sink, output, legacy_receipt, legacy_statuses):
        """After legacy finalization; each category owns its strict session scope."""
        b = self.backend; folder = Path(output)/"mae-display"; statuses = []; charged = 0
        sink = DisplaySink(sink, folder)
        root = self.native.root_sha256
        def write(name, value): return runtime.write(sink, folder/name, value)
        try:
            self.native.verify()
            catalog_folder = Path(prepared_ref["path"]).parent/"mae-display"
            catalog_ref = future.binding(catalog_folder/"PROFILE_CATALOG.json")
            completion_ref = future.binding(catalog_folder/"CATALOG_COMPLETION.json")
            catalog = runtime.read_owned(b.storage, catalog_ref); done = runtime.read_owned(b.storage, completion_ref)
            require(catalog["profiles"] == self.profiles and catalog["root_go_sha256"] == root
                and catalog["prepared"] == prepared_ref and done["catalog"] == catalog_ref
                and runtime.utc(done["completed_at"]) <= runtime.utc(source["actual_source_started_at"]),
                "GENUINE_PREVALUE_DISPLAY_CATALOG_REQUIRED")
            require(runtime.read_owned(b.storage, source_ref) == source, "SAME_ACTUAL_RUNTIME_SOURCE_RECEIPT")
            identities = validate_bridge(bridge, features, bridge_ref)
            # The existing whole-child wall ceiling provides a conservative
            # remaining-time bound. A display attempt cannot consume legacy's
            # already-captured rows or extend any input deadline.
            require((min(map(runtime.utc,b.choice.document["slate"]["game_cutoffs"].values()))-b.clock()).total_seconds()
                > runtime.LIMITS["wall_seconds"] + 1, "DISPLAY_DEADLINE_SLACK_UNAVAILABLE")
            records = [dict(self.records[t],eligible_roles=sorted(set(features.position))) for t in TARGETS]
            self.archive_file_debit = archive_file_debit(features, records, output)
            groups = []
            for ordinal,(cutoff,frame) in enumerate(features.groupby("cutoff_utc",sort=False)):
                views,keys = current.projection_receipts(records,frame,capture,capture_ref,storage=sink,
                    output=folder/"views"/str(ordinal),clock=b.clock)
                groups.append((cutoff,views,keys))
            registry_records = []
            for target in TARGETS:
                r = self.records[target]; profile = self.profiles[target]
                for cutoff,views,keys in groups:
                    view = views[keys[r["binding"]["sha256"]]]
                    qsha = future.frame_digest(view["view"])
                    self.snapshots[target,qsha] = dict(phase="CURRENT_SNAPSHOT", point_profile_sha256=point._digest(profile),
                        source_receipt=source_ref, feature_capture_receipt=view["binding"], query_projection_sha256=qsha,
                        information_cutoff_utc=runtime.utc(source["asof_utc"]).isoformat())
                    registry_records.append(dict(target=target,model_version=r["binding"]["sha256"],
                        procedure_version=profile["procedure_version"],point_profile_sha256=point._digest(profile),
                        source_policy_sha256=b.contract["source_policy_sha256"],source_contract_sha256=public.digest(b.contract),
                        source_receipt_sha256=source_ref["sha256"],feature_capture_receipt_sha256=view["binding"]["sha256"],
                        feature_binding_sha256=capture["feature_binding"]["sha256"],query_projection_sha256=qsha,
                        query_source_sha256=capture["feature_binding"]["sha256"],information_cutoff_utc=runtime.utc(source["asof_utc"]).isoformat(),
                        feature_capture_completed_at=capture["feature_persist_completed_at"],public_roles=profile["public_roles"],
                        identity_bridge_sha256=bridge_ref["sha256"]))
            registry_ref = write("SOURCE_REGISTRY.json",dict(schema_version=VERSION+"-source-registry",
                root_go_sha256=root,created_before_point_values=True,registered_at=b.clock().isoformat(),records=registry_records))
            write("CATALOG_BINDING.json",dict(catalog=catalog_ref,completion=completion_ref,root_go_sha256=root))
            legacy_rows = sum(s["expected_rows"] for s in legacy_statuses)
            for target in TARGETS:
                record = self.records[target]; rows = []; raw_bytes = 0; failure = None; receipt = None
                expected = len(features); reserved = 0; session = None; admitted = None
                try:
                    require(legacy_rows+charged+2*expected <= runtime.LIMITS["prediction_rows"], "UNCHANGED_ROW_ALLOCATION_EXHAUSTED")
                    reserved = 2*expected; charged += reserved
                    # At most three additional one-model decodes and exact
                    # fixture replay qualifications, sequentially, with no
                    # retry or new model slot. Native CPU/wall/memory caps and
                    # the18000 current-query traversal cap remain unchanged.
                    session = future.FutureInferenceSession.from_storage(b.storage)
                    session.prepare([record["binding"]])
                    admitted = point.bind_profile(session,self.profiles[target],verify_owner_admission=self._verify_profile)
                    for cutoff,views,keys in groups:
                        view = views[keys[record["binding"]["sha256"]]]
                        context = dict(cutoff_utc=runtime.utc(cutoff).isoformat(),weekly_decision_cutoff_utc=b.choice.document["choice"]["actual_frozen_at"],
                            slate_id=b.choice.document["slate"]["slate_id"],source_contract=b.contract,evidence_lane="original_pregame",
                            reference_stream="candidate",query_source_sha256=capture["feature_binding"]["sha256"],feature_capture_receipt=view["binding"])
                        for chunk in point.predict_point_chunks(session,admitted,view["view"],context=context,
                                source_receipt=source_ref,batch_size=128,clock=b.clock):
                            for candidate in chunk:
                                key = tuple(candidate[k] for k in future.cdf.KEYS)
                                wrapper = dict(schema_version=VERSION+"-identity-envelope",candidate=candidate,
                                    public_identity=identities[key],candidate_sha256=candidate["candidate_sha256"],
                                    cutoff_utc=candidate["issue_deadline_utc"],operational_eligible=candidate["operational_eligible"],
                                    legacy_ranking_policy_unchanged=True)
                                wrapper["envelope_sha256"] = runtime.digest(wrapper)
                                raw_bytes += len(private.canonical(wrapper))+1
                                require(raw_bytes <= MAX_CANDIDATE_JSONL_BYTES, "BOUNDED_DISPLAY_INFLATED_JSONL_REQUIRED")
                                rows.append(wrapper)
                    require(len(rows) == expected and len({w["candidate"]["offered_id"] for w in rows}) == expected,
                        "COMPLETE_MAE_CATEGORY_POPULATION_REQUIRED")
                except Exception as error:
                    text = str(error); failure = text if re.fullmatch("[A-Z][A-Z0-9_]{0,95}",text) else "MAE_CATEGORY_FAILED_RETAINED"
                finally:
                    if session is not None:
                        try: session.close()
                        except Exception:
                            # A close failure is a category failure. Never
                            # discard refs, mark a failed close successful, or
                            # allow that session to service another category.
                            failure = "MAE_CATEGORY_SESSION_CLOSE_FAILED"
                    admitted = None; session = None
                if failure is None:
                    try:
                        receipt = future.persist_policy_inputs(folder/"candidates"/(target+".jsonl.gz"),[rows],storage=sink,
                            max_serialized_bytes=MAX_CANDIDATE_JSONL_BYTES,clock=b.clock)
                    except Exception as error:
                        text = str(error); failure = text if re.fullmatch("[A-Z][A-Z0-9_]{0,95}",text) else "MAE_CATEGORY_FAILED_RETAINED"
                        completed = folder/"candidates"/(target+".jsonl.completion.json")
                        if completed.is_file(): receipt = runtime.read_owned(b.storage,future.binding(completed))
                status = dict(target=target,state="CAPTURED" if failure is None else "FAILED_RETAINED",failure=failure,
                    expected_rows=expected,issued_rows=len(rows),persistence=receipt,
                    traversal_rows_requested=2*expected,traversal_rows_reserved=reserved,
                    artifact=record["binding"],profile_sha256=point._digest(self.profiles[target]))
                statuses.append(status)
                write("status/"+target+".json",status)
            terminal = dict(schema_version=VERSION+"-result",state="PRIVATE_DISPLAY_CAPTURE_COMPLETE" if all(s["failure"] is None for s in statuses) else "PARTIAL_DISPLAY_CAPTURE_RETAINED",
                root_go_sha256=root,source=source_ref,feature_capture=capture_ref,identity_bridge=bridge_ref,
                prevalue_catalog=catalog_ref,source_registry=registry_ref,statuses=statuses,
                legacy_selected=legacy_receipt,legacy_statuses_sha256=runtime.digest(legacy_statuses),
                legacy_prediction_rows=legacy_rows,extra_traversal_rows_reserved=charged,
                actual_completed_at=b.clock().isoformat(),display_only=True,ranking_policy_change=False,
                probability_policy_change=False,public_export_authorized=False,independent_archive_restore="REQUIRED")
        except Exception as error:
            text = str(error)
            terminal = dict(schema_version=VERSION+"-result",state="FAILED_DISPLAY_CAPTURE_RETAINED",
                reason=text if re.fullmatch("[A-Z][A-Z0-9_]{0,95}",text) else "DISPLAY_CAPTURE_FAILED_RETAINED",
                root_go_sha256=root,statuses=statuses,legacy_selected=legacy_receipt,
                actual_completed_at=b.clock().isoformat(),display_only=True,public_export_authorized=False)
        # A failure to retain the optional terminal grants no point capability.
        # Known bytes remain immutable, while old candidate/selected controls
        # retain their original reserve and are allowed to finish normally.
        try: return write("FINISHED.json",terminal)
        except Exception: return None
