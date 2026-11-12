"""Typed public projection of the NEW correction-epoch capture contract.

No import performs network, credential, model, outcome or repository operations.
The parent supplies its genuine bounded client after archive.consume. Only the
live verifier can mint acceptance; decoded JSON is never publication authority.
Old generic terminals, policies, durability APIs and website gates stay strict.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime,timezone
import gzip
import io
import math
from pathlib import Path
import re

from . import audit_weekly_archive_v1 as archive, audit_weekly_epoch_v1 as epoch
from . import weekly_public_feed as feed, weekly_website_overlay as overlay
from . import private_draft_store as store, gha_private_checkpoint as cp
from . import weekly_durable_acceptance as old_identity

VERSION="audit-weekly-public-v1"
POLICY="audit-weekly-derived-policy-v3"
AUTHORITY="audit-weekly-publication-authority-v3"
PROJECTION_RULE="DECLARED_EPOCH_METADATA_PROJECTION_ONLY_NO_VALUES_OR_RESELECTION"
PIN_PATHS=("nfl_lab/audit_weekly_public_v1.py","tools/audit_weekly_public_v1.py",
    "nfl_lab/audit_weekly_epoch_v1.py","nfl_lab/audit_weekly_runtime_v1.py","nfl_lab/audit_weekly_archive_v1.py",
    "nfl_lab/weekly_generic_producer.py","nfl_lab/weekly_adaptive.py","nfl_lab/weekly_public_feed.py",
    "nfl_lab/weekly_website_overlay.py","nfl_lab/weekly_private_selected.py","nfl_lab/private_draft_store.py",
    "nfl_lab/audit_reference_capture_v1.py","tools/audit_reference_capture_v1.py")
POLICY_KEYS={"schema_version","state","registration_id","registered_at_utc","authority_kind","human_approval",
    "public_raw_or_model_weights","source_policy_sha256","public_fields","public_roles","expected_categories",
    "rights_authorities","r0_identities","engine_sha256","website_code_sha256","publication_authority","public_ref",
    "source_sha","source_branch","workflow_sha256","jobs","permissions","recipe","producer_policy_sha256",
    "approved_candidates","origin_choice_sha256"}
RECIPE_KEYS={"schema_version","code_pins","epoch_implementation_pins","compatibility_catalog_schema",
    "compatibility_catalog_rule","selected_procedure_algorithm","correction_rule","routine_rule"}
_LIVE=object()


class PublicError(ValueError):pass


def require(value,code):
    if not value:raise PublicError(code)


def pins():
    root=Path(__file__).resolve().parents[1]
    return {p:store.sha(store.read_local(root/p,2 << 20)) for p in PIN_PATHS}


def recipe():
    return dict(schema_version=VERSION+"-registered-recipe",code_pins=pins(),epoch_implementation_pins=epoch.implementation_pins(),
        compatibility_catalog_schema=feed.CATALOG_V2,compatibility_catalog_rule=PROJECTION_RULE,
        selected_procedure_algorithm=epoch.VERSION+"-issued-procedure",
        correction_rule="SAME_FAMILIES_WEIGHTS_NO_RESELECTION",routine_rule="P2_ALL_RESOLVED_PRIOR_CURRENT_EPOCH_WEEKS")


def recipe_commitment(policy):
    """Bind static scope as well as the algorithm; never auto-register policy."""
    return feed.digest({k:policy[k] for k in ("recipe","approved_candidates","origin_choice_sha256",
        "expected_categories","public_roles","source_policy_sha256")})


def policy_template():
    """No approval, current source, rights, R0 or procedure is invented."""
    result=dict(schema_version=POLICY,state="PREPARED_UNREGISTERED",registration_id="weekly-adaptive-release-v1",
        registered_at_utc=None,authority_kind="AUTOMATED_REGISTERED_POLICY",human_approval=False,public_raw_or_model_weights=False,
        source_policy_sha256=cp.POLICY_SHA,public_fields=list(overlay.ROW_FIELDS),
        public_roles={t:None for t in cp.TARGETS},expected_categories=sorted(cp.TARGETS),rights_authorities=[],r0_identities=[],
        engine_sha256={p:None for p in feed.ENGINE_FILES},website_code_sha256={p:None for p in feed.CODE_FILES},
        publication_authority=dict(schema_version=AUTHORITY,state="PREPARED_UNREGISTERED",repository=store.REPO,source_sha=None,
            source_branch=None,workflow_path=".github/workflows/lab.yml",event="workflow_dispatch",export_job=None,run_attempt=1,
            public_ref="lab-state",catalog_schema=feed.CATALOG_V2,catalog_freezer_sha256=pins()["nfl_lab/audit_weekly_public_v1.py"],
            catalog_registration_rule=PROJECTION_RULE,recipe_registration_sha256=None),public_ref="lab-state",source_sha=None,source_branch=None,workflow_sha256=None,
        jobs=dict(produce=None,restore=None,consume=None),permissions={r:dict(contents="write",actions="read") for r in ("produce","restore","consume")},
        recipe=recipe(),producer_policy_sha256=feed.digest(recipe()),approved_candidates=[dict(target=t,family=f,method_id=m,procedure_version=None)
            for t,f,m in cp.JOBS],origin_choice_sha256=None)
    result["producer_policy_sha256"]=recipe_commitment(result)
    result["publication_authority"]["recipe_registration_sha256"]=result["producer_policy_sha256"]
    return result


def policy_check(policy,*,at):
    p=policy
    require(type(p) is dict and set(p)==POLICY_KEYS and p["schema_version"]==POLICY and p["state"]=="ROOT_REGISTERED"
        and p["registration_id"]=="weekly-adaptive-release-v1" and p["authority_kind"]=="AUTOMATED_REGISTERED_POLICY"
        and p["human_approval"] is p["public_raw_or_model_weights"] is False
        and p["source_policy_sha256"]==cp.POLICY_SHA and p["public_fields"]==list(overlay.ROW_FIELDS)
        and p["expected_categories"]==sorted(cp.TARGETS) and set(p["public_roles"])==set(cp.TARGETS),"REGISTERED_NEW_EPOCH_PUBLIC_POLICY_REQUIRED")
    require(feed.utc(p["registered_at_utc"])<=feed.utc(at) and re.fullmatch(r"[a-f0-9]{40}",str(p["source_sha"]))
        and re.fullmatch(r"[A-Za-z0-9_./-]+",str(p["source_branch"]))
        and all(part not in {".","..",""} for part in p["source_branch"].split("/"))
        and feed.h(p["workflow_sha256"]) and feed.h(p["origin_choice_sha256"]),"EXACT_PUBLIC_SOURCE_AND_PRIOR_REGISTRATION")
    require(p["recipe"]==recipe() and set(p["recipe"])==RECIPE_KEYS and p["producer_policy_sha256"]==recipe_commitment(p),"REGISTERED_SOURCE_BOUND_EPOCH_FREEZER_RECIPE")
    require(set(p["jobs"])=={"produce","restore","consume"} and len(set(p["jobs"].values()))==3
        and all(type(v) is str and re.fullmatch(r"[A-Za-z0-9_-]+",v) for v in p["jobs"].values())
        and p["permissions"]=={r:dict(contents="write",actions="read") for r in ("produce","restore","consume")},"REGISTERED_PUBLIC_WORKFLOW_ROLES")
    expected=dict(schema_version=AUTHORITY,state="ROOT_REGISTERED",repository=store.REPO,source_sha=p["source_sha"],source_branch=p["source_branch"],
        workflow_path=".github/workflows/lab.yml",event="workflow_dispatch",export_job=p["jobs"]["consume"],run_attempt=1,public_ref="lab-state",
        catalog_schema=feed.CATALOG_V2,catalog_freezer_sha256=p["recipe"]["code_pins"]["nfl_lab/audit_weekly_public_v1.py"],catalog_registration_rule=PROJECTION_RULE,
        recipe_registration_sha256=p["producer_policy_sha256"])
    require(p["publication_authority"]==expected and p["public_ref"]=="lab-state","DECLARED_NEW_COMPATIBILITY_CATALOG_AUTHORITY")
    candidates=p["approved_candidates"]
    require(type(candidates) is list and len(candidates)==18 and all(set(r)=={"target","family","method_id","procedure_version"}
        and (r["target"],r["family"],r["method_id"])==job and feed.h(r["procedure_version"]) for r,job in zip(candidates,cp.JOBS)),"EXACT_APPROVED18_EFFECTIVE_PROCEDURES_REQUIRED")
    require(p["rights_authorities"] and p["r0_identities"] and all(feed.h(h) for h in p["rights_authorities"]+p["r0_identities"])
        and set(p["engine_sha256"])==feed.ENGINE_FILES and set(p["website_code_sha256"])==feed.CODE_FILES
        and all(feed.h(h) for h in p["website_code_sha256"].values())
        and all(p["engine_sha256"][name]==p["website_code_sha256"][name] for name in feed.ENGINE_FILES),"REGISTERED_RIGHTS_R0_AND_WEBSITE_CODE_REQUIRED")
    require(all(type(roles) is list and roles and len(set(roles))==len(roles) and set(roles)<={"QB","RB","WR","TE"}
        for roles in p["public_roles"].values()),"EXPLICIT_PUBLIC_ROLE_SCOPE")


def rights_gates(policy,rights,r0,board,selected_sha256,*,at):
    """Metadata-only gates, before selected private JSONL is opened."""
    require(type(rights) is dict and rights.get("schema_version")=="weekly-derived-selected-rights-v1"
        and rights.get("state")=="SOURCE_REVIEW_ACCEPTED" and rights.get("authority_kind")=="REGISTERED_SOURCE_RIGHTS_POLICY"
        and rights.get("authority_policy_sha256") in policy["rights_authorities"] and rights.get("selected_sha256")==selected_sha256
        and rights.get("source_policy_sha256")==policy["source_policy_sha256"] and rights.get("scope")=="SELECTED_DERIVED_ONLY"
        and rights.get("public_fields")==list(overlay.ROW_FIELDS) and feed.utc(rights["reviewed_at"])<=feed.utc(at),"SOURCE_RIGHTS_BEFORE_SELECTED_DECODE")
    require(type(r0) is dict and r0.get("schema_version")=="weekly-actual-r0-freeze-v1" and r0.get("state")=="ACTUAL_FIRST_RELEASE_R0_FROZEN"
        and feed.digest(r0) in policy["r0_identities"] and type(r0.get("deployment_id")) is int and r0["deployment_id"]>0
        and re.fullmatch(r"[a-f0-9]{40}",str(r0.get("deployed_source_sha"))) and feed.h(r0.get("visible_board_sha256"))
        and r0.get("engine_sha256")==policy["engine_sha256"] and feed.utc(r0["frozen_at"])<=feed.utc(at),"AUTHENTIC_R0_FREEZE_BEFORE_SELECTED_DECODE")
    require(type(board) is dict and board.get("season") is not None and board.get("week") is not None,"ACTUAL_BOARD_REQUIRED")
    overlay.board_offers(board)


@dataclass(frozen=True)
class CompatibilityCatalog:
    document: dict
    body: bytes
    provenance: dict
    sha256: str

    def verify(self):
        require(self.body==feed.canonical(self.document)+b"\n" and feed.sha(self.body)==self.sha256
            and set(self.document)=={"schema_version","rows","current_values_used","public_policy_registration"}
            and self.document["schema_version"]==feed.CATALOG_V2 and self.document["current_values_used"] is False
            and self.provenance["rule"]==PROJECTION_RULE and self.provenance["generic_terminal_claim"] is False,
            "EXACT_DECLARED_CATALOG_SERIALIZATION")


def compatibility_catalog(storage,source_ref,registered,choice,policy,*,relocated_replays=(),at):
    """Honest current projection of metadata frozen before source/values.

The legacy schema name describes only the declared four-field wire encoding.
It does not claim an old generic terminal, old freezer execution or old proof.
"""
    policy_check(policy,at=at)
    require(type(registered) is epoch.RegisteredEpoch and type(choice) is epoch.EpochChoice,"TYPED_REGISTERED_EPOCH_AND_CHOICE_REQUIRED")
    choice.verify(registered,feed.utc(at))
    require(registered.epoch.origin["choice_file"]["sha256"]==policy["origin_choice_sha256"],"PRESERVED_ORIGINAL_DURABLE_CHOICE_REQUIRED")
    expected=epoch.selected_versions(registered,choice,relocated_replays=relocated_replays,now=feed.utc(at))
    body=archive.read_owned(storage,source_ref,256 << 10,raw=True);source=cp.strict_json(body)
    require(source==expected and body==store.canonical(source),"EXACT_NEW_PREVALUE_EPOCH_CATALOG")
    slots=registered.epoch.document["replay_catalog"]["slots"]
    require(all(all(slot[k]==approved[k] for k in ("target","family","method_id","procedure_version"))
        for slot,approved in zip(slots,policy["approved_candidates"])),"APPROVED_EFFECTIVE18_COUNT_PROCEDURES_REQUIRED")
    rows=source["rows"]
    require(type(rows) is list and 0<len(rows)<=256 and all(set(r)=={"category","method_id","procedure_version","model_version"}
        and r["category"] in policy["expected_categories"] and r["method_id"]=="P2_SELECTED"
        and feed.h(r["procedure_version"]) and feed.h(r["model_version"]) for r in rows)
        and {r["category"] for r in rows}==set(policy["expected_categories"]),"COMPLETE_CLOSED_DYNAMIC_SELECTED_RECIPE_CATALOG")
    document=dict(schema_version=feed.CATALOG_V2,rows=deepcopy(rows),current_values_used=False,
        public_policy_registration="REQUIRED_SEPARATELY; not automatic approval")
    encoded=feed.canonical(document)+b"\n"
    provenance=dict(schema_version=VERSION+"-catalog-projection",rule=PROJECTION_RULE,source_catalog=source_ref,
        source_schema=source["schema_version"],epoch_sha256=registered.epoch.sha256,choice_sha256=choice.sha256,
        projection_created_at=at,current_values_used=False,generic_terminal_claim=False,
        freezer_sha256=policy["publication_authority"]["catalog_freezer_sha256"])
    result=CompatibilityCatalog(document,encoded,provenance,feed.sha(encoded));result.verify();return result


class LiveAcceptance:
    def __init__(self,record,inputs,key):
        require(key is _LIVE,"LIVE_API_VERIFIER_REQUIRED")
        self.record=deepcopy(record);self.inputs=inputs
        self._record_sha256=feed.digest(record)
        self._input_sha256=feed.digest({k:v for k,v in inputs.items() if k!="storage" and k!="catalog"})
    def __reduce__(self):raise PublicError("LIVE_ACCEPTANCE_MUST_NOT_BE_SERIALIZED")
    def verify(self):
        require(feed.digest(self.record)==self._record_sha256 and self._input_sha256==feed.digest({k:v for k,v in self.inputs.items()
            if k!="storage" and k!="catalog"}),"LIVE_ACCEPTANCE_OR_INPUTS_CHANGED")
        self.inputs["catalog"].verify()
        require(self.inputs["catalog"].sha256==self.record["compatibility_catalog_sha256"]
            and self.inputs["catalog"].provenance["source_catalog"]["sha256"]==self.record["source_catalog_sha256"],"LIVE_CATALOG_PROJECTION_CHANGED")


def verify_live(client,consumed,package,policy,rights,r0,board,registered,choice,*,storage,pending_census,at,board_body):
    """Use the parent's actual bounded GET client; injected HTTP in tests only.

The root composes consume and this verifier in the SAME exporter process. No
serialized acceptance or substitute process identity is accepted.
"""
    policy_check(policy,at=at)
    require(type(consumed) is dict and consumed.get("schema_version")==archive.VERSION+"-restored"
        and consumed.get("state")=="PRIVATE_CAPTURE_EXPORT_INPUTS_VERIFIED" and consumed.get("captured_bundle_hashes_restored") is True
        and consumed.get("scope_qualified_for_publication") is consumed.get("public_export_authorized") is False
        and consumed["archive"]["archive_state"]=="COMPLETE_CAPTURE" and consumed["validation"]["qualified_selected"] is True,
        "GENUINE_COMPLETE_ARCHIVE_CONSUME_REQUIRED")
    aliases=consumed["aliases"]
    policy_ref=aliases.get("context/public_policy.json")
    require(type(policy_ref) is dict and archive.read_owned(storage,policy_ref,128 << 10)==policy,
        "EXACT_ARCHIVED_PREVALUES_PUBLIC_POLICY_REQUIRED")
    selected=aliases["runtime/selected.jsonl.gz"]
    rights_gates(policy,rights,r0,board,selected["sha256"],at=at)
    current_board=aliases.get("r0/original_board.json")
    require(type(current_board) is dict and type(board_body) is bytes and 0<len(board_body)<=feed.MAX_BYTES
        and cp.strict_json(board_body)==board and feed.sha(board_body)==current_board["sha256"] and len(board_body)==current_board["bytes"]
        and archive.read_owned(storage,current_board,feed.MAX_BYTES,raw=True)==board_body,"EXACT_ARCHIVED_CURRENT_ORIGINAL_R0_BOARD_BYTES")
    require((board["season"],board["week"])==(choice.document["slate"]["season"],choice.document["slate"]["week"]),"CURRENT_BOARD_MUST_MATCH_NEW_SLATE")
    archive.checked(client,policy["jobs"]["consume"])
    actual=cp.client_identity(client)
    require(actual==consumed["current"] and client.source_sha==policy["source_sha"]
        and client.job["workflow_ref"]==store.REPO+"/.github/workflows/lab.yml@refs/heads/"+policy["source_branch"]
        and consumed["archive"]["jobs"]==policy["jobs"],"SAME_ACTUAL_EXPORTER_PROCESS_SOURCE_AND_WORKFLOW")
    jobs=archive.jobs_for(client)
    producer_job=archive.predecessor(client,consumed["archive"]["producer"],jobs)
    reader_job=archive.predecessor(client,consumed["restorer_witness"]["restorer"],jobs)
    current_jobs=[j for j in jobs if j.get("id")==actual["api_job_id"]]
    require(len(current_jobs)==1 and current_jobs[0].get("status")=="in_progress" and current_jobs[0].get("conclusion") is None
        and feed.utc(reader_job["completed_at"])<=feed.utc(current_jobs[0]["started_at"])<=feed.utc(at),"ACTUAL_EXPORT_JOB_AFTER_COMPLETED_READER")
    archive.authenticate_qualification(client,package,pending_census)
    require(client.binding==consumed["archive"]["runtime_binding"],"EXACT_ARCHIVE_CANARY_RUNTIME")
    for proof in consumed["restorer_witness"]["proofs"]:store.check_proof(client,proof,"restore")
    require(consumed["exporter_proofs"] and all(p["process_identity"]==client.process and p["run_id"]==client.run_id
        and p["source_sha"]==client.source_sha and p["job"]["api_job_id"]==client.job["api_job_id"]
        and p["phase"]=="restore" and p["exact_readback"] is p["separate_process"] is True for p in consumed["exporter_proofs"]),
        "ACTUAL_CURRENT_ARCHIVE_EXPORTER_PROOFS_REQUIRED")
    # Fixed source-bound workflow route, authenticated automatically by Client.
    url=store.API+"/contents/.github/workflows/lab.yml?ref="+client.source_sha
    client.allowed.add(url);workflow=client.json(url)
    require(workflow.get("type")=="file" and workflow.get("path")==".github/workflows/lab.yml" and workflow.get("encoding")=="base64","ACTUAL_PUBLIC_WORKFLOW_BYTES")
    raw=base64.b64decode(workflow["content"].replace("\n",""),validate=True)
    require(len(raw)<=128 << 10 and feed.sha(raw)==policy["workflow_sha256"],"EXACT_REGISTERED_PUBLIC_WORKFLOW_SOURCE")
    meta=lambda n:archive.read_owned(storage,aliases[n],2 << 20)
    reference=meta("r0/CAPTURE_COMPLETE.json");worker=meta("r0/WORKER_COMPLETE.json");reference_prepared=meta("r0/prepared.json")
    require(reference["schema_version"]=="audit-reference-capture-v1-capture" and reference["state"]=="ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE"
        and reference["original_board"]["sha256"]==current_board["sha256"]==worker["board"]["sha256"]
        and reference["native"]["sha256"]==aliases["r0/original-native.json.gz"]["sha256"]==worker["native"]["sha256"]
        and reference_prepared["permit"]["epoch_sha256"]==registered.epoch.sha256
        and reference_prepared["permit"]["choice_sha256"]==choice.sha256
        and worker["fixed_original_default_refresh"] is True
        and feed.utc(reference_prepared["permit"]["actual_capture_authorized_at"])<=feed.utc(worker["actual_source_completed_at"])
        <=feed.utc(worker["actual_native_observed_at"])<=feed.utc(worker["actual_completed_at"])
        <=feed.utc(consumed["producer_proof"]["actual_started_at"]),"QUALIFIED_CURRENT_REFERENCE_SOURCE_PROOF_AND_CLOCKS")
    for cutoff in choice.document["slate"]["game_cutoffs"].values():
        require(feed.utc(worker["actual_completed_at"])<feed.utc(cutoff),"CURRENT_REFERENCE_MUST_BE_CAPTURED_BEFORE_INPUT_CUTOFFS")
    terminal=meta("runtime/FINISHED.json");completion=meta("runtime/selected.jsonl.completion.json")
    # The NEW archive's exact owned index is metadata, not a generic terminal.
    # Its creation precedes append; the genuine producer job's completion is a
    # conservative persisted-by upper bound, never a fabricated POST clock.
    index_ref=consumed.get("index_ref")
    if index_ref is None:
        index_ref=cp.binding(Path(aliases["runtime/selected.jsonl.gz"]["path"]).parents[2]/"owned-downloads/index.gz")
    index_bytes=archive.read_owned(storage,index_ref,archive.INDEX_CAP,raw=True)
    require(feed.sha(index_bytes)==consumed["index_sha256"]==consumed["archive"]["index_descriptor"]["entry"]["payload"]["sha256"],
        "EXACT_OWNED_ARCHIVE_INDEX_DURABILITY_CLOCK")
    archive_index=archive.unpack(index_bytes,archive.INDEX_PLAIN_CAP)
    require(archive_index["schema_version"]==archive.VERSION+"-index" and archive_index["producer_proof"]==consumed["producer_proof"],"ACTUAL_ARCHIVE_INDEX_PRODUCER_PROOF")
    durability_clocks=dict(local_completed_at=completion["completed_at"],archive_index_created_at=archive_index["created_at"],
        producer_job_completed_at_upper_bound=producer_job["completed_at"],restorer_witness_completed_at=consumed["restorer_witness"]["actual_completed_at"],
        exporter_restore_proof_created_at=max((r["created_at_utc"] for r in consumed["exporter_proofs"]),key=feed.utc))
    durable_completed_at=max(durability_clocks.values(),key=feed.utc)
    require(feed.utc(durable_completed_at)<=feed.utc(at),"ACTUAL_DURABILITY_KNOWN_BEFORE_LIVE_VERIFICATION")
    candidates=meta("runtime/CANDIDATES.json");slots=candidates["slots"]
    require(len(slots)==18 and {(r["target"],r["method_id"]) for r in slots}=={(t,m) for t,_,m in cp.JOBS}
        and all(r["state"]=="CAPTURED" and r["failure"] is None and r["attempt_qualified"] is True
            and r["expected_rows"]==r["issued_rows"]==r["persistence"]["rows"] and not r["unissued_offered_ids"] for r in slots)
        and sum(r["issued_rows"] for r in slots)==terminal["prediction_rows"]<=18000,"ALL18_COMPLETE_CANDIDATE_CENSUS_BEFORE_VALUES")
    from .weekly_private_selected import identity_map
    identity_map(meta("runtime/IDENTITY_BRIDGE.json"))
    source=meta("context/source.json");choice_completion=meta("prepared/choice_completion.json")
    require(terminal["schema_version"]==archive.RUNTIME+"-result" and terminal["state"]=="PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE"
        and terminal["selected"]==completion and completion["state"]=="PERSISTED" and completion["binding"]["sha256"]==selected["sha256"]
        and completion["binding"]["bytes"]==selected["bytes"] and completion["rows"]<=5000
        and feed.utc(policy["registered_at_utc"])<=feed.utc(source["actual_source_started_at"])
        and feed.utc(choice_completion["persisted_completed_at"])<feed.utc(source["actual_source_started_at"])
        <=feed.utc(source["actual_completed_at"])<=feed.utc(terminal["actual_completed_at"])<=feed.utc(at),"REGISTERED_POLICY_AND_CATALOG_BEFORE_VALUES")
    require(feed.utc(terminal["actual_completed_at"])<=feed.utc(consumed["producer_proof"]["actual_started_at"]),"CAPTURE_COMPLETED_BEFORE_GENUINE_ARCHIVE_PRODUCER")
    replay=meta("prepared/relocated_replay.json")
    catalog=compatibility_catalog(storage,aliases["runtime/SELECTED_VERSION_CATALOG.json"],registered,choice,policy,
        relocated_replays=(replay,),at=at)
    require(terminal["epoch_sha256"]==registered.epoch.sha256 and terminal["choice_sha256"]==choice.sha256
        and choice_completion["selected_versions_sha256"]==aliases["runtime/SELECTED_VERSION_CATALOG.json"]["sha256"],"ARCHIVED_EPOCH_CHOICE_AND_PREVALUES_CATALOG_BINDING")
    verified_at=datetime.now(timezone.utc).isoformat()
    require(feed.utc(at)<=feed.utc(verified_at),"LIVE_VERIFICATION_COMPLETION_CLOCK")
    record=dict(schema_version=VERSION+"-live-acceptance",authority_kind="ROOT_APPROVED_PROCEDURE_VERIFIED",accepted_at=verified_at,
        policy_sha256=feed.digest(policy),archive_index_sha256=consumed["index_sha256"],archive_files_sha256=consumed["files_sha256"],
        producer=consumed["archive"]["producer"],restorer=consumed["restorer_witness"]["restorer"],exporter=actual,
        producer_proof_sha256=feed.digest(consumed["producer_proof"]),restorer_proof_sha256=feed.digest(consumed["restorer_witness"]),
        exporter_proofs_sha256=feed.digest(consumed["exporter_proofs"]),qualification_sha256=feed.digest(package["qualification"]),
        workflow_sha256=feed.sha(raw),selected_body_sha256=selected["sha256"],selected_bytes=selected["bytes"],
        prevalues_public_policy_sha256=policy_ref["sha256"],
        current_board_sha256=current_board["sha256"],current_reference_capture_sha256=aliases["r0/CAPTURE_COMPLETE.json"]["sha256"],
        durable_completed_at=durable_completed_at,durability_clocks=durability_clocks,
        source_catalog_sha256=aliases["runtime/SELECTED_VERSION_CATALOG.json"]["sha256"],compatibility_catalog_sha256=catalog.sha256,
        raw_or_models_public=False,scientific_qualification=False)
    inputs=dict(storage=storage,catalog=catalog,policy=deepcopy(policy),rights=deepcopy(rights),r0=deepcopy(r0),board=deepcopy(board),
        terminal=terminal,completion=completion,aliases=deepcopy(aliases),choice=deepcopy(choice.document),source=source,
        reference_methods={t:registered.epoch.document["catalog"]["categories"][t]["reference_id"] for t in cp.TARGETS},
        durable_completed_at=durable_completed_at)
    return LiveAcceptance(record,inputs,_LIVE)


def export(live,*,at):
    """Project only existing public fields; private rows/flags are untouched."""
    require(type(live) is LiveAcceptance,"IN_MEMORY_LIVE_ACCEPTANCE_REQUIRED")
    live.verify();p=live.inputs;policy=p["policy"];policy_check(policy,at=at)
    require(feed.utc(live.record["accepted_at"])<=feed.utc(at),"PUBLIC_EXPORT_CLOCK")
    completion=p["completion"];selected=p["aliases"]["runtime/selected.jsonl.gz"]
    rights_gates(policy,p["rights"],p["r0"],p["board"],selected["sha256"],at=at)
    # No selected byte is opened until ALL live/source/rights/R0/canary/catalog
    # gates above and in verify_live have passed.
    body=archive.read_owned(p["storage"],selected,8 << 20,raw=True)
    rows=[];semantic=0
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        while True:
            line=stream.readline(32769)
            if not line:break
            semantic+=len(line)
            require(len(line)<=32768 and line.endswith(b"\n") and semantic<=64 << 20 and len(rows)<5000,"FINITE_SELECTED_PRIVATE_STREAM")
            rows.append(cp.strict_json(line))
    require(type(rows) is list and len(rows)==completion["rows"]<=5000,"COMPLETE_SELECTED_PRIVATE_ROW_COUNT")
    bridge_doc=archive.read_owned(p["storage"],p["aliases"]["runtime/IDENTITY_BRIDGE.json"],2 << 20)
    from .weekly_private_selected import identity_map
    bridge=identity_map(bridge_doc);offers=overlay.board_offers(p["board"])
    catalog=p["catalog"].document
    allowed={(r["category"],r["method_id"],r["procedure_version"],r["model_version"]) for r in catalog["rows"]}
    choices={s["decision"]["category"]:s for s in p["choice"]["choice"]["selections"]}
    result=[];counts={};seen=set()
    def fallback(reason):counts[reason]=counts.get(reason,0)+1
    local_completed=completion["completed_at"];persisted=p["durable_completed_at"]
    for source in rows:
        require(type(source) is dict and not {"actual","label","loss","brier","crps","log_score"}&set(source),"OUTCOME_OR_SCORE_FIELDS_FORBIDDEN")
        require(source["evidence_lane"]=="original_pregame" and source["source_policy_sha256"]==policy["source_policy_sha256"]
            and source["correction_epoch_sha256"]==p["terminal"]["epoch_sha256"] and source["scientific_qualification"] is False
            and source["public_export_authorized"] is False,"ORIGINAL_NEW_EPOCH_PRIVATE_ROW_REQUIRED")
        require(feed.utc(source["source_capture_completed_at"])<=feed.utc(source["issued_at"])<=feed.utc(local_completed)
            <=feed.utc(source["source_cutoff_utc"])<feed.utc(source["kickoff_utc"])
            and source["source_cutoff_utc"]==source["cutoff_utc"],"ORIGINAL_PERSISTENCE_AND_INPUT_CUTOFF_NOT_REPAIRABLE")
        original=bridge.get((source["game_id"],source["player_id"]))
        require(original is not None and all(source.get(k)==v for k,v in original.items()),"EXACT_SOURCE_IDENTITY_BRIDGE")
        require(source["category"] in overlay.PRODUCTS and (source["product"],source["prediction_functional"])==overlay.PRODUCTS[source["category"]],"NO_PPR_OR_PRODUCT_CONVERSION")
        value=source["forecast_value"]
        require(value is None or type(value) in (int,float) and math.isfinite(value)
            and (source["category"] not in overlay.COUNTS or value>=0)
            and (source["category"]!="anytime_td" or 0<=value<=1),"EXACT_FINITE_SUPPORTED_SELECTED_POINT")
        if source["operational_eligible"] is not True or value is None or source.get("position") not in policy["public_roles"][source["category"]]:
            fallback("private_ineligible_R0");continue
        if feed.utc(persisted)>feed.utc(source["source_cutoff_utc"]):
            fallback("private_ineligible_R0");continue
        require((source["category"],source["method_id"],source["procedure_version"],source["model_version"]) in allowed,"DECLARED_DYNAMIC_SELECTED_RECIPE_REQUIRED")
        members=choices[source["category"]]["members"];components=source["components"]
        require(len(components)==len(members) and all(c["weight"]==m["weight"] and c["method_id"] in {m["method_id"],p["reference_methods"][source["category"]]}
            for c,m in zip(components,members)) and math.fsum(c["weight"]*c["value"] for c in components)==value
            and feed.digest([(c["method_id"],c["model_version"],c["weight"]) for c in components])==source["model_version"],
            "PRESERVED_FROZEN_FAMILIES_WEIGHTS_AND_COMPONENT_VALUES")
        row={k:source[k] for k in overlay.ROW_FIELDS if k in source}
        row.update(player_id=source["website_player_id"],game_id=source["website_game_id"],persistence_completed_at=persisted,
            valid_until_utc=source.get("valid_until_utc",source["kickoff_utc"]))
        require(set(row)==set(overlay.ROW_FIELDS),"ONLY_EXISTING_PUBLIC_ROW_FIELDS")
        key=overlay.key(row);require(key not in seen,"DUPLICATE_SELECTED_PUBLIC_IDENTITY");seen.add(key)
        if key not in offers:fallback("outside_board_R0");continue
        player,game,_=offers[key]
        require((source["season"],source["week"])==(p["board"]["season"],p["board"]["week"])
            and source["team"]==player["team"] and source["opponent"]==player["opp"],"EXACT_CURRENT_BOARD_TEAM_GAME_MEMBERSHIP")
        if player.get("pos",player.get("position"))!=source["position"]:fallback("private_ineligible_R0");continue
        if game.get("state")!="pre" or feed.utc(source["kickoff_utc"])<=feed.utc(at):fallback("started_R0");continue
        overlay.validate_row(dict(row,first_prepared_at=at),offers)
        result.append(row)
    require(result,"NO_ELIGIBLE_DERIVED_PUBLIC_ROWS")
    publication=feed.publication_metadata_v2(policy,live.record,dict(completion=completion),catalog,p["catalog"].body)
    document=dict(schema_version=feed.VERSION_V2,state="DERIVED_SELECTED_ONLY",season=p["board"]["season"],week=p["board"]["week"],
        created_at=at,expires_at=max((r["valid_until_utc"] for r in result),key=feed.utc),producer_policy_sha256=policy["producer_policy_sha256"],
        rights_authority_sha256=p["rights"]["authority_policy_sha256"],rights_receipt_sha256=feed.digest(p["rights"]),
        durability_receipt_sha256=feed.digest(live.record),r0_identity_sha256=feed.digest(p["r0"]),identity_scope_sha256=feed.identity_scope(result,p["board"]),
        rows=result,coverage=dict(private_selected_rows=len(rows),public_rows=len(result),fallback_counts=counts),
        publication=publication,publication_sha256=feed.digest(publication))
    require(set(document)==feed.META_FIELDS|{"publication","publication_sha256"} and len(feed.canonical(document))<=feed.MAX_BYTES,"CLOSED_V2_PUBLIC_FEED_SIZE_AND_FIELDS")
    return document
