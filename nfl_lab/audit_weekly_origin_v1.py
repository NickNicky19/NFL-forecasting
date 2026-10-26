"""GET-only recovery of original78 inputs and source-bound weekly metadata.

Historical configurations are interpretation/pin records, never current
execution authority. Current authority comes only from the parent's new genuine
weekly producer root. Model/candidate/selected/source bodies remain opaque.
No outcome parser, estimator, source acquisition, requalification or append is
called. Import performs no network or credential access.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import base64
import gzip
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

from . import audit_count_requalify_v1 as audit, selected_private_snapshot as snapshot
from . import gha_private_checkpoint as cp, owner_private_bootstrap as owner, private_draft_store as store
from . import weekly_durable_acceptance as acceptance
from .owned_reference_batch import validate_owned_references

VERSION = "audit-weekly-origin-v1"
MODE = "audit-weekly-producer-v1"
SELECTED_RUN = "40135574441"
SELECTED_SOURCE = "93e2019144be7b51248ce548fe247c6dcd949b71"
SELECTED_JOBS = {"producer": ("genuine-hosted-fixed-build-restore-v1", 120996271037),
    "reader": ("genuine-hosted-selected-restore-v1", 120996804742),
    "exporter": ("genuine-hosted-selected-export-v1", 120996934563)}
SELECTED_CONFIG = "config/selected-private-snapshot-v3.json"
SELECTED_CONFIG_SHA = "df70002a97a010165924eed92311cbe6d7c859dc602f12db3f5a8a6afe6f82da"
SELECTED_POLICY_SHA = "0ee3eccf4f0e9ed85ee46c6ba4f6df404459fb4f3cabba469bf6dffd9ee2456c"
SLATE_DERIVATION = "RECONSTRUCTED_FROM_SOURCE_BOUND_CHOICE_AND_FINISHED_NOT_RETAINED_RAW_SLATE"
WITNESS_CAP = 4 << 20
LIMITS = dict(CPU_seconds=120, wall_seconds=180, address_space_bytes=512 << 20,
    global_private_bytes=512 << 20, HTTP_calls=800, input_restore_operations=9, selected_restore_operations=11,
    model_decodes=0, fits=0, requalifications=0, protected_outcome_reads=0, remote_writes=0, source_acquisitions=0)
FILES = ("nfl_lab/audit_weekly_origin_v1.py", "tools/audit_weekly_origin_v1.py", "tests/test_audit_weekly_origin_v1.py",
    "nfl_lab/audit_count_requalify_v1.py", "nfl_lab/selected_private_snapshot.py", "nfl_lab/gha_private_checkpoint.py",
    "nfl_lab/private_draft_store.py", "nfl_lab/private_draft_probe_helpers.py", "nfl_lab/owner_private_bootstrap.py",
    "nfl_lab/owner_bootstrap_bundle.py", "nfl_lab/weekly_durable_acceptance.py", "nfl_lab/operational_storage.py",
    "nfl_lab/owned_reference_batch.py", "nfl_lab/weekly_generic_producer.py", "nfl_lab/weekly_adaptive.py",
    "tools/private_draft_store_v2.py", "config/gha-private-checkpoint-v3.json", SELECTED_CONFIG,
    "config/weekly-initial-continuation-v6-registration.json", "config/operational-source-policy-v2.json",
    "config/private-draft-storage-v2.json", "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json",
    "tools/audit_process_guard_v1.py", ".github/workflows/lab.yml")
REQUEST_KEYS = {"schema_version", "approved", "repository", "code_pins", "limits", "input_plan", "selected_handoff",
    "selected_origin", "historical_config_sha256", "historical_code_sha256", "cache", "state_root", "output"}
AUTHORITY_KEYS = {"schema_version", "phase", "request_sha256", "repository", "owner_root_go_sha256", "owner_root_checked",
    "actual_actions_api_authenticated", "api_job_id", "source_sha", "run_id", "run_attempt", "job_id", "workflow_ref",
    "issued_at_utc", "expires_at_utc", "fits", "remote_writes", "protected_outcome_reads", "public_release"}


def require(value, code):
    if not value:
        raise store.StoreError(code)


def now():
    return datetime.now(timezone.utc)


def pins(root):
    return {name: store.sha(store.read_local(Path(root)/name, 2 << 20)) for name in FILES}


def read_document(path, cap=1 << 20):
    return cp.strict_json(store.read_local(path, cap))


def source_blob(root, source, name):
    require(re.fullmatch(r"[a-f0-9]{40}", source) and not Path(name).is_absolute() and ".." not in Path(name).parts,
        "CLOSED_HISTORICAL_SOURCE_PATH")
    size = subprocess.check_output(["git", "cat-file", "-s", source+":"+name], cwd=root, text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
    require(size.isdigit() and 0 < int(size) <= 2 << 20, "HISTORICAL_CODE_SIZE_BOUND")
    raw = subprocess.check_output(["git", "show", source+":"+name], cwd=root, stderr=subprocess.DEVNULL, timeout=10)
    require(len(raw) == int(size), "HISTORICAL_CODE_SIZE_CHANGED")
    return raw


def input_plan(root):
    """Frozen original parent/scope only; no expired registration validator."""
    config = read_document(Path(root)/"config/gha-private-checkpoint-v3.json")
    parent = read_document(Path(root)/"config/weekly-initial-continuation-v6-registration.json")["parent"]
    require(parent["run_id"] == "40129209279" and parent["source_sha"] == "ec3a3471c58b8729777ffb4825a47ae4af330f6f"
        and parent["producer_job_id"] == "genuine-hosted-fixed-build-v1" and parent["producer_api_job_id"] == 120977111674,
        "FROZEN_ORIGINAL78_PARENT_REQUIRED")
    return dict(parent=parent, checkpoint_config=config, logical_allowlist=audit.logical_scope(config), limits=dict(HTTP_calls=360))


def prepare_request(root, witnessed_handoff, *, cache, state_root, output):
    """Offline code/config and explicit owner metadata only; stays unapproved."""
    raw = source_blob(root, SELECTED_SOURCE, SELECTED_CONFIG)
    require(store.sha(raw) == SELECTED_CONFIG_SHA, "ORIGINAL_SELECTED_CONFIGURATION_HASH")
    config = cp.strict_json(raw)
    historical = {name: store.sha(source_blob(root, SELECTED_SOURCE, name)) for name in config["source_sha256"]}
    require(historical == config["source_sha256"], "ORIGINAL_SELECTED_CODE_PINS")
    historical[SELECTED_CONFIG] = SELECTED_CONFIG_SHA
    return dict(schema_version=VERSION+"-request", approved=False, repository=store.REPO, code_pins=pins(root), limits=dict(LIMITS),
        input_plan=input_plan(root), selected_handoff=deepcopy(witnessed_handoff),
        selected_origin=dict(run_id=SELECTED_RUN, source_sha=SELECTED_SOURCE,
            workflow_ref=input_plan(root)["parent"]["workflow_ref"], jobs={k:dict(job_id=v[0],api_job_id=v[1]) for k,v in SELECTED_JOBS.items()}),
        historical_config_sha256=SELECTED_CONFIG_SHA, historical_code_sha256=historical,
        cache=str(cache), state_root=str(state_root), output=str(output))


def validate_request(request, root):
    p = request
    require(type(p) is dict and set(p) == REQUEST_KEYS and p["schema_version"] == VERSION+"-request"
        and p["approved"] is True and p["repository"] == store.REPO and p["limits"] == LIMITS
        and p["code_pins"] == pins(root) and p["input_plan"] == input_plan(root), "EXACT_SOURCE_BOUND_ORIGIN_REQUEST_REQUIRED")
    o = p["selected_origin"]
    require(o == dict(run_id=SELECTED_RUN, source_sha=SELECTED_SOURCE, workflow_ref=p["input_plan"]["parent"]["workflow_ref"],
        jobs={k:dict(job_id=v[0],api_job_id=v[1]) for k,v in SELECTED_JOBS.items()}), "EXACT_ORIGINAL_SELECTED_THREE_JOB_ORIGIN")
    h = p["selected_handoff"]
    require(type(h) is dict and set(h) == {"schema_version", "runtime_binding", "source_sha", "run_id", "procedure_sha256", "index_descriptor", "witness_descriptor"}
        and h["schema_version"] == snapshot.VERSION+"-handoff" and h["source_sha"] == SELECTED_SOURCE and h["run_id"] == SELECTED_RUN
        and h["procedure_sha256"] == p["historical_config_sha256"] == SELECTED_CONFIG_SHA,
        "PAST_WITNESS_DESCRIPTOR_REQUIRED_NO_APPEND_FALLBACK")
    store.checked_binding(h["runtime_binding"])
    snapshot.descriptor(h["index_descriptor"], "runtime_manifest", h["index_descriptor"]["entry"]["payload"])
    snapshot.descriptor(h["witness_descriptor"], "runtime_manifest", h["witness_descriptor"]["entry"]["payload"])
    config_raw = source_blob(root, SELECTED_SOURCE, SELECTED_CONFIG)
    require(store.sha(config_raw) == SELECTED_CONFIG_SHA and store.read_local(Path(root)/SELECTED_CONFIG, 1 << 20) == config_raw,
        "UNCHANGED_HISTORICAL_SELECTED_CONFIGURATION_REQUIRED")
    config = cp.strict_json(config_raw)
    expected = dict(config["source_sha256"]); expected[SELECTED_CONFIG] = SELECTED_CONFIG_SHA
    require(p["historical_code_sha256"] == expected and all(store.sha(source_blob(root, SELECTED_SOURCE, name)) == value for name,value in expected.items()),
        "OLD_CODE_HASHES_MUST_MATCH_OLD_SOURCE_NOT_CURRENT_SOURCE")
    require(config["produce_job"] == SELECTED_JOBS["producer"][0] and config["restore_job"] == SELECTED_JOBS["reader"][0]
        and config["consume_job"] == SELECTED_JOBS["exporter"][0], "HISTORICAL_SELECTED_JOB_PARAMETERS_REQUIRED")
    return config


def checked_authority(body, expected_sha256, request_sha256, env, root):
    require(0 < len(body) <= 16 << 10 and store.sha(body) == expected_sha256, "EXACT_ORIGIN_NATIVE_AUTHORITY_HASH")
    a = cp.strict_json(body)
    require(store.canonical(a) == body and type(a) is dict and set(a) == AUTHORITY_KEYS
        and a["schema_version"] == VERSION+"-native-authority" and a["phase"] == "origin" and a["request_sha256"] == request_sha256
        and a["repository"] == store.REPO and a["owner_root_checked"] is a["actual_actions_api_authenticated"] is True
        and type(a["api_job_id"]) is int and a["api_job_id"] > 0 and a["source_sha"] == env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA")
        and a["run_id"] == env.get("GITHUB_RUN_ID") and a["run_id"] not in {SELECTED_RUN,"40129209279"}
        and a["source_sha"] not in {SELECTED_SOURCE,"ec3a3471c58b8729777ffb4825a47ae4af330f6f"}
        and type(a["run_attempt"]) is int and a["run_attempt"] == 1
        and a["job_id"] == env.get("GITHUB_JOB") and a["workflow_ref"] == env.get("GITHUB_WORKFLOW_REF")
        and all(type(a[k]) is int and a[k] == 0 for k in ("fits","remote_writes","protected_outcome_reads")) and a["public_release"] is False,
        "CLOSED_FRESH_ORIGIN_NATIVE_AUTHORITY")
    require(store.utc(a["issued_at_utc"]) <= now() < store.utc(a["expires_at_utc"])
        and 0 < (store.utc(a["expires_at_utc"])-store.utc(a["issued_at_utc"])).total_seconds() <= 3600, "FRESH_ORIGIN_AUTHORITY_CLOCK")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == store.REPO
        and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_RUN_ATTEMPT") == "1"
        and env.get("STORE_PERMISSION") == "write",
        "ACTUAL_OWNER_ORIGIN_JOB_REQUIRED")
    event = cp.strict_json(store.read_local(env["GITHUB_EVENT_PATH"],256 << 10))
    text = event.get("inputs",{}).get("inference_builder_go_json","").encode()
    require(text and store.sha(text) == a["owner_root_go_sha256"] == event["inputs"].get("inference_builder_go_sha256")
        and event["inputs"].get("mode") == MODE and event.get("repository",{}).get("full_name") == store.REPO,
        "REAL_NEW_WEEKLY_ROOT_EVENT_REQUIRED")
    from . import audit_weekly_operations_authority_v1 as operations_authority
    operations_authority.child(env,text,root)
    # The parent validates the entire root's closed phase contract. This child
    # independently binds its exact request, source, phase and genuine API job.
    require(subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip() == a["source_sha"], "ACTUAL_ORIGIN_CHECKOUT_SOURCE")
    require(subprocess.check_output(["git","status","--porcelain","--untracked-files=all","--",*FILES],cwd=root,text=True) == "",
        "CLEAN_COMMITTED_ORIGIN_HELPERS_REQUIRED")
    return a


def authenticate_selected_jobs(client, origin, issued_at):
    """Historical run/jobs are explicitly separate from the new authenticated job."""
    base = store.API+"/actions/runs/"+origin["run_id"]
    client.allowed.update((base,base+"/jobs?per_page=100&page=1"))
    run = client.json(base); listing = client.json(base+"/jobs?per_page=100&page=1")
    require(run.get("id") == int(origin["run_id"]) and run.get("head_sha") == origin["source_sha"]
        and run.get("status") == "completed" and run.get("conclusion") == "success" and run.get("event") == "workflow_dispatch"
        and run.get("run_attempt") == 1 and run.get("path") == ".github/workflows/lab.yml"
        and run.get("repository",{}).get("full_name") == store.REPO and run.get("head_repository",{}).get("full_name") == store.REPO,
        "EXACT_COMPLETED_HISTORICAL_SELECTED_RUN_REQUIRED")
    require(type(listing.get("jobs")) is list and listing.get("total_count") == len(listing["jobs"]) <= 100,
        "COMPLETE_HISTORICAL_SELECTED_JOB_LIST")
    evidence = {}
    for role, expected in origin["jobs"].items():
        matches = [j for j in listing["jobs"] if j.get("id") == expected["api_job_id"] and j.get("name") == expected["job_id"]]
        require(len(matches) == 1 and matches[0].get("head_sha") == origin["source_sha"] and matches[0].get("run_id") == int(origin["run_id"])
            and matches[0].get("status") == "completed" and matches[0].get("conclusion") == "success"
            and store.utc(matches[0]["started_at"]) <= store.utc(matches[0]["completed_at"]) <= store.utc(issued_at),
            "ACTUAL_ORIGINAL_SELECTED_JOB_SOURCE_STATUS_AND_CLOCK")
        evidence[role] = dict(repository=store.REPO,run_id=origin["run_id"],source_sha=origin["source_sha"],
            job_id=expected["job_id"],api_job_id=expected["api_job_id"],status="completed",conclusion="success",
            run_attempt=1,run_status="completed",run_conclusion="success",workflow_ref=origin["workflow_ref"],
            started_at=matches[0]["started_at"],completed_at=matches[0]["completed_at"])
    require(store.utc(evidence["producer"]["completed_at"]) <= store.utc(evidence["reader"]["started_at"])
        and store.utc(evidence["reader"]["completed_at"]) <= store.utc(evidence["exporter"]["started_at"]), "HISTORICAL_SELECTED_THREE_JOB_ORDER")
    return evidence


def owned_document(storage, reference, *, cap=2 << 20):
    validate_owned_references(storage,{reference["path"]:reference["sha256"]})
    return cp.strict_json(cp.read_ref(reference,cap))


def original_slate(choice, terminal, historical_config):
    """Explicit derivation from old metadata, never a backdated new choice."""
    decisions = [s["decision"] for s in choice["selections"]]
    require(decisions and all(all(d[k] == decisions[0][k] for k in ("season","week","slate_id","slate_first_kickoff_utc","weekly_decision_cutoff_utc")) for d in decisions),
        "CONSISTENT_ORIGINAL_WEEKLY_SLATE_METADATA_REQUIRED")
    contract = choice["slate_contract"]
    require(contract == terminal["slate_contract"], "ORIGINAL_TERMINAL_SLATE_CONTRACT_MISMATCH")
    leaf = contract
    for _ in range(3):
        if "original_source_slate_contract" not in leaf: break
        leaf = leaf["original_source_slate_contract"]
    remaining, elapsed = leaf["remaining_game_ids"], leaf["elapsed_game_ids"]
    require(type(remaining) is list and type(elapsed) is list and len(remaining) == len(set(remaining)) == 13
        and len(elapsed) == len(set(elapsed)) == 1 and not set(remaining)&set(elapsed), "ORIGINAL_REGISTERED_13_PLUS_1_SLATE_REQUIRED")
    d = decisions[0]
    require((d["season"],d["week"]) == (2026,7) and historical_config["input_cutoff_utc"] == "2026-10-25T00:00:00Z",
        "FROZEN_ORIGINAL_WEEKLY_PERIOD_AND_INPUT_HORIZON")
    return dict(season=d["season"],week=d["week"],season_type="REG",slate_id=d["slate_id"],
        scheduled_first_kickoff_utc=d["slate_first_kickoff_utc"],weekly_deadline_utc=choice["weekly_deadline_utc"],
        game_cutoffs={name:historical_config["input_cutoff_utc"] for name in remaining},
        schedule_identity_sha256=choice["slate_identity"],scheduled_games=14,elapsed_games=1,slate_contract=contract,
        origin_derivation=SLATE_DERIVATION,raw_original_slate_file_retained=False)


def terminal_witness(choice_ref, restored_choice_ref, terminal_ref, restored_terminal_ref, terminal, choice, evidence,
        producer, historical_reader_proof, current_restore_proof, authority, *, created_at, terminal_bytes, index_bytes, handoff,
        policy_bytes, catalog_bytes, past_witness_bytes):
    """New derived evidence; NEVER claims the missing original completion file."""
    require(terminal.get("schema_version") == "weekly-generic-future-producer-v1" and terminal.get("fatal") is None
        and terminal.get("state") in {"LOCAL_FUTURE_SLATE_CAPTURED","PARTIAL_FUTURE_SLATE_RETAINED"}
        and all(evidence[k]["run_id"] == SELECTED_RUN and evidence[k]["source_sha"] == SELECTED_SOURCE
            and evidence[k]["job_id"] == v[0] and evidence[k]["api_job_id"] == v[1] for k,v in SELECTED_JOBS.items()),
        "EXACT_OLD_FINISHED_AND_THREE_REGISTERED_SOURCE_JOBS")
    require((choice_ref["bytes"],choice_ref["sha256"]) == (restored_choice_ref["bytes"],restored_choice_ref["sha256"])
        and (terminal_ref["bytes"],terminal_ref["sha256"]) == (restored_terminal_ref["bytes"],restored_terminal_ref["sha256"])
        and terminal["weekly_choice"] == terminal["decision"] == choice_ref, "ORIGINAL_CHOICE_AND_TERMINAL_PHYSICAL_BINDINGS_REQUIRED")
    persisted = terminal["decision_persist_completed_at"]
    require(store.utc(choice["actual_frozen_at"]) <= store.utc(persisted) < store.utc(choice["weekly_deadline_utc"])
        and store.utc(persisted) <= store.utc(terminal["actual_completed_at"]) <= store.utc(producer["started_at_utc"])
        <= store.utc(producer["created_at_utc"]) <= store.utc(evidence["producer"]["completed_at"])
        <= store.utc(evidence["reader"]["started_at"]) <= store.utc(historical_reader_proof["started_at_utc"])
        <= store.utc(historical_reader_proof["created_at_utc"]) <= store.utc(evidence["reader"]["completed_at"])
        <= store.utc(evidence["exporter"]["started_at"]) <= store.utc(evidence["exporter"]["completed_at"])
        <= store.utc(authority["issued_at_utc"]) <= store.utc(created_at), "CAUSAL_ORIGINAL_TERMINAL_AND_NEW_WITNESS_CLOCKS_REQUIRED")
    require(producer["identity"]["api_job_id"] == evidence["producer"]["api_job_id"]
        and producer["identity"]["run_id"] == SELECTED_RUN and producer["identity"]["source_sha"] == SELECTED_SOURCE
        and producer["identity"]["job_id"] == SELECTED_JOBS["producer"][0] and producer["terminal_sha256"] == terminal_ref["sha256"]
        and store.utc(evidence["producer"]["started_at"]) <= store.utc(producer["started_at_utc"])
        and historical_reader_proof["job"]["api_job_id"] == evidence["reader"]["api_job_id"]
        and historical_reader_proof["run_id"] == evidence["reader"]["run_id"]
        and historical_reader_proof["source_sha"] == evidence["reader"]["source_sha"]
        and current_restore_proof["run_id"] == authority["run_id"] and current_restore_proof["source_sha"] == authority["source_sha"]
        and current_restore_proof["job"]["api_job_id"] == authority["api_job_id"]
        and current_restore_proof["job"]["job_id"] == authority["job_id"]
        and store.utc(authority["issued_at_utc"]) <= store.utc(current_restore_proof["started_at_utc"])
        <= store.utc(current_restore_proof["created_at_utc"]) <= store.utc(created_at)
        and current_restore_proof["run_id"] != historical_reader_proof["run_id"], "HISTORICAL_AND_CURRENT_RESTORE_IDENTITIES_MUST_STAY_SEPARATE")
    require(type(terminal_bytes) is bytes and len(terminal_bytes) == terminal_ref["bytes"]
        and store.sha(terminal_bytes) == terminal_ref["sha256"] and cp.strict_json(terminal_bytes) == terminal,
        "ACTUAL_ORIGINAL_TERMINAL_BYTES_REQUIRED_BEFORE_PROJECTION")
    payload=handoff["index_descriptor"]["entry"]["payload"]
    require(type(index_bytes) is bytes and len(index_bytes) == payload["bytes"] and store.sha(index_bytes) == payload["sha256"],
        "EXACT_ORIGINAL_SNAPSHOT_INDEX_BYTES_REQUIRED")
    index=snapshot.unpack(index_bytes,snapshot.INDEX_CAP)
    require(index["metadata_refs"]["decision"] == choice_ref and index["metadata_refs"]["terminal"] == terminal_ref
        and index["producer_proof"] == producer and index["producer"] == producer["identity"], "INDEX_MUST_BIND_ORIGINAL_TERMINAL_CHOICE_AND_PRODUCER")
    result=dict(schema_version=VERSION+"-terminal-witness",state="DERIVED_SOURCE_BOUND_TERMINAL_WITNESS",created_at_utc=created_at,
        original_completion_file_retained=False,original_choice_binding=choice_ref,restored_choice_binding=restored_choice_ref,
        original_terminal_binding=terminal_ref,restored_terminal_binding=restored_terminal_ref,
        actual_decision_persist_completed_at=persisted,original_terminal_completed_at=terminal["actual_completed_at"],
        original_source_sha=SELECTED_SOURCE,original_run_id=SELECTED_RUN,historical_config_sha256=SELECTED_CONFIG_SHA,
        original_producer=producer["identity"],historical_reader_restore_proof_sha256=store.sha(store.canonical(historical_reader_proof)),
        current_physical_restore_proof_sha256=store.sha(store.canonical(current_restore_proof)),
        genuine_historical_job_evidence_sha256=store.sha(store.canonical(evidence)),
        current_restorer=dict(run_id=authority["run_id"],source_sha=authority["source_sha"],job_id=authority["job_id"],api_job_id=authority["api_job_id"]),
        owner_root_go_sha256=authority["owner_root_go_sha256"],fabricated_original_receipt=False,
        current_authority_issued_at_utc=authority["issued_at_utc"],current_authority_expires_at_utc=authority["expires_at_utc"],
        historical_authentication_scope="COMPLETED_ORIGINAL_RUN_PRODUCER_READER_EXPORTER_ACTIONS_API_GET",
        metadata_proof_scope="SOURCE_BOUND_ORIGINAL_FINISHED_NOT_ORIGINAL_COMPLETION",
        original_slate_derivation=SLATE_DERIVATION,raw_original_slate_file_retained=False,
        terminal_body_utf8=terminal_bytes.decode("utf-8"),snapshot_index_gzip_base64=base64.b64encode(index_bytes).decode("ascii"),
        startup_policy_body_utf8=policy_bytes.decode("utf-8"),procedure_catalog_body_utf8=catalog_bytes.decode("utf-8"),
        historical_witness_gzip_base64=base64.b64encode(past_witness_bytes).decode("ascii"),
        source_handoff=deepcopy(handoff),original_producer_proof=deepcopy(producer),historical_reader_restore_proof=deepcopy(historical_reader_proof),
        current_physical_restore_proof=deepcopy(current_restore_proof),historical_job_api_evidence=deepcopy(evidence))
    require(len(store.canonical(result)) <= WITNESS_CAP,"DERIVED_TERMINAL_WITNESS_METADATA_CAP")
    return result


def _body(raw, reference, cap):
    require(type(reference) is dict and set(reference) == {"path","bytes","sha256"}
        and type(reference["path"]) is str and Path(reference["path"]).is_absolute()
        and type(reference["bytes"]) is int and 0 < reference["bytes"] <= cap
        and type(reference["sha256"]) is str and re.fullmatch("[a-f0-9]{64}",reference["sha256"])
        and type(raw) is bytes and len(raw) == reference["bytes"] and store.sha(raw) == reference["sha256"],
        "EXACT_BOUNDED_ORIGINAL_METADATA_BYTES")
    return cp.strict_json(raw)


def validate_terminal_witness(witness, raw_choice, slate, catalog, policy, now):
    """Return the original decision-write UTC datetime, never a completion.

    No network, private read, model/forecast/outcome decode or clock rewrite.
    Native proof validation reads only the unchanged public store configuration.
    The caller must obtain this witness and its source handoff through the
    parent's authenticated owned route. Hash/proof JSON alone cannot establish
    platform authority. This validator rechecks that authenticated evidence's
    exact byte bindings, native proof shapes, source/API identities and clocks.
    """
    try:
        return _validate_terminal_witness(witness,raw_choice,slate,catalog,policy,now)
    except store.StoreError:
        raise
    except (KeyError,TypeError,ValueError,UnicodeError,OverflowError,OSError):
        raise store.StoreError("INVALID_DERIVED_ORIGIN_WITNESS_METADATA") from None


def _validate_terminal_witness(w, raw_choice, slate, catalog, policy, checked_at):
    require(type(w) is dict and len(store.canonical(w)) <= WITNESS_CAP
        and w.get("schema_version") == VERSION+"-terminal-witness", "TYPED_DERIVED_ORIGIN_WITNESS_REQUIRED")
    require(isinstance(checked_at,datetime) and checked_at.tzinfo is not None
        and store.utc(w["created_at_utc"]) <= checked_at, "ACTUAL_NEW_WITNESS_CREATION_CLOCK_REQUIRED")
    terminal_bytes=w["terminal_body_utf8"].encode("utf-8")
    terminal=_body(terminal_bytes,w["original_terminal_binding"],2 << 20)
    choice=_body(raw_choice,w["original_choice_binding"],512 << 10)
    _body(raw_choice,w["restored_choice_binding"],512 << 10)
    _body(terminal_bytes,w["restored_terminal_binding"],2 << 20)
    h=w["source_handoff"]
    require(type(h) is dict and set(h) == {"schema_version","runtime_binding","source_sha","run_id","procedure_sha256","index_descriptor","witness_descriptor"}
        and h["schema_version"] == snapshot.VERSION+"-handoff" and h["source_sha"] == SELECTED_SOURCE
        and h["run_id"] == SELECTED_RUN and h["procedure_sha256"] == SELECTED_CONFIG_SHA, "SOURCE_BOUND_HISTORICAL_HANDOFF_REQUIRED")
    binding=store.checked_binding(h["runtime_binding"]); binding_sha=store.sha(store.canonical(binding))
    def embedded(name,descriptor):
        text=w[name];require(type(text) is str and len(text) <= 4*snapshot.INDEX_CAP//3+8,"BOUNDED_EMBEDDED_ORIGIN_INDEX")
        raw=base64.b64decode(text,validate=True);p=descriptor["entry"]["payload"]
        snapshot.descriptor(descriptor,"runtime_manifest",p)
        require(0 < len(raw) <= snapshot.INDEX_CAP and len(raw) == p["bytes"] and store.sha(raw) == p["sha256"],
            "EXACT_SOURCE_BOUND_EMBEDDED_INDEX_OR_WITNESS")
        return raw,snapshot.unpack(raw,snapshot.INDEX_CAP)
    index_bytes,index=embedded("snapshot_index_gzip_base64",h["index_descriptor"])
    past_bytes,past=embedded("historical_witness_gzip_base64",h["witness_descriptor"])
    require(set(index) == snapshot.INDEX and index["schema_version"] == snapshot.VERSION
        and index["procedure_sha256"] == SELECTED_CONFIG_SHA and index["source_policy_sha256"] == cp.POLICY_SHA,
        "CLOSED_SOURCE_PINNED_ORIGINAL_INDEX")
    refs=index["metadata_refs"]
    policy_bytes=w["startup_policy_body_utf8"].encode("utf-8");catalog_bytes=w["procedure_catalog_body_utf8"].encode("utf-8")
    require(_body(policy_bytes,refs["startup_policy"],2 << 20) == policy
        and _body(catalog_bytes,refs["procedure_catalog"],2 << 20) == catalog
        and refs["startup_policy"]["sha256"] == SELECTED_POLICY_SHA
        and terminal["startup_policy"] == refs["startup_policy"], "EXACT_ORIGINAL_POLICY_CATALOG_AND_TERMINAL_BINDINGS")
    producer=w["original_producer_proof"];old=w["historical_reader_restore_proof"];physical=w["current_physical_restore_proof"]
    require(set(producer) == acceptance.PACKAGER and producer["schema_version"] == "weekly-selected-packager-provenance-v2"
        and producer["producer_policy_sha256"] == SELECTED_POLICY_SHA and producer["source_policy_sha256"] == cp.POLICY_SHA
        and producer["inference_consumed_ref"] == refs["inference_consumed"]
        and store.utc(producer["inference_consumed_at"]) <= store.utc(terminal["actual_completed_at"]), "ORIGINAL_PACKAGER_SOURCE_PROOF_REQUIRED")
    original=acceptance.identity(producer["identity"])
    selected=index["original_selected"];sd=index["selected_descriptor"]
    snapshot.descriptor(sd,"forecast_batch",selected)
    for d,process in ((h["index_descriptor"],original["process_identity"]),(sd,original["process_identity"]),
            (h["witness_descriptor"],old["process_identity"])):
        require(d["entry"]["writer_run_id"] == SELECTED_RUN and d["entry"]["binding_sha256"] == binding_sha
            and d["entry"]["producer_process"] == process, "SAME_AUTHENTICATED_ORIGINAL_RUNTIME_AND_WRITERS")
    require(type(past) is dict and set(past) == {"schema_version","index_sha256","producer_proof_sha256","restore_proof"}
        and past["schema_version"] == snapshot.VERSION+"-witness" and past["index_sha256"] == store.sha(index_bytes)
        and past["producer_proof_sha256"] == store.sha(store.canonical(producer)) and past["restore_proof"] == old,
        "EXACT_PAST_READER_WITNESS_BYTES_AND_SCOPE")
    require(len({original["process_identity"],old["process_identity"],physical["process_identity"]}) == 3,
        "INDEPENDENT_ORIGINAL_READER_AND_CURRENT_RESTORER")
    verifier=SimpleNamespace(binding=binding,process=store.sha(b"origin-metadata-validator"),
        source_sha=SELECTED_SOURCE,run_id=SELECTED_RUN,job=dict(execution_lane="github_actions",workflow_ref=original["workflow_ref"]))
    for proof in (old,physical):
        store.check_proof(verifier,proof,"restore",same_run=False)
        require(proof["payload_sha256"] == producer["selected_sha256"] == selected["sha256"]
            and proof["bytes"] == producer["bytes"] == selected["bytes"]
            and proof["job"]["workflow_ref"] == original["workflow_ref"], "EXACT_SELECTED_BODY_PROOF_NOT_UNRELATED_DURABILITY")
    require(old["job"]["job_id"] == SELECTED_JOBS["reader"][0],"EXACT_OLD_READER_PROOF_JOB")
    expected=snapshot.required_files(refs,producer,index["candidates"]);observed={}
    require(type(index["groups"]) is list and 0 < len(index["groups"]) <= 8,"FINITE_ORIGINAL_SNAPSHOT_GROUPS")
    for n,g in enumerate(index["groups"]):
        require(set(g) == {"index","bytes","sha256","inflated_bytes","files","descriptor"} and g["index"] == n,
            "CLOSED_ORDERED_ORIGINAL_SNAPSHOT_GROUP")
        e=snapshot.descriptor(g["descriptor"],"runtime_manifest",g)
        require(e["producer_process"] == original["process_identity"] and e["writer_run_id"] == SELECTED_RUN
            and e["binding_sha256"] == binding_sha,"SOURCE_BOUND_ORIGINAL_METADATA_GROUP")
        for item in g["files"]:
            require(item["logical_path"] not in observed and item["required"] is True
                and item["origin"]["source_policy_sha256"] == cp.POLICY_SHA,"CLOSED_ORIGINAL_REQUIRED_FILE_INVENTORY")
            observed[item["logical_path"]]=(item["sha256"],item["bytes"])
    require(observed == expected,"FULL_ORIGINAL18_AND_METADATA_INDEX_NO_OMISSIONS")
    evidence=w["historical_job_api_evidence"]
    require(type(evidence) is dict and set(evidence) == set(SELECTED_JOBS),"EXACT_THREE_ORIGINAL_API_EVIDENCE_ROLES")
    fields={"repository","run_id","source_sha","job_id","api_job_id","status","conclusion","run_attempt","run_status","run_conclusion","workflow_ref","started_at","completed_at"}
    for role, (name,api_id) in SELECTED_JOBS.items():
        row=evidence[role]
        require(type(row) is dict and set(row) == fields and row["repository"] == store.REPO and row["run_id"] == SELECTED_RUN
            and row["source_sha"] == SELECTED_SOURCE and row["job_id"] == name and type(row["api_job_id"]) is int and row["api_job_id"] == api_id
            and type(row["run_attempt"]) is int and row["run_attempt"] == 1 and row["status"] == row["run_status"] == "completed"
            and row["conclusion"] == row["run_conclusion"] == "success" and row["workflow_ref"] == original["workflow_ref"]
            and store.utc(row["started_at"]) <= store.utc(row["completed_at"]),"COMPLETED_EXACT_SOURCE_API_JOB_EVIDENCE")
    current=w["current_restorer"]
    require(set(current) == {"run_id","source_sha","job_id","api_job_id"} and current["run_id"] not in {SELECTED_RUN,"40129209279"}
        and re.fullmatch("[1-9][0-9]{0,19}",current["run_id"]) and re.fullmatch("[a-f0-9]{40}",current["source_sha"])
        and current["source_sha"] not in {SELECTED_SOURCE,"ec3a3471c58b8729777ffb4825a47ae4af330f6f"}
        and current["api_job_id"] not in {v[1] for v in SELECTED_JOBS.values()}
        and re.fullmatch("[a-f0-9]{64}",w["owner_root_go_sha256"]),"DISTINCT_NEW_SOURCE_RUN_JOB_AND_OWNER_ROOT")
    issued=store.utc(w["current_authority_issued_at_utc"]);expires=store.utc(w["current_authority_expires_at_utc"])
    require(issued <= store.utc(w["created_at_utc"]) < expires and 0 < (expires-issued).total_seconds() <= 3600
        and store.utc(evidence["exporter"]["completed_at"]) < issued,"DISTINCT_CURRENT_CREATION_AND_FRESH_RECOVERY_AUTHORITY")
    a=dict(current,issued_at_utc=w["current_authority_issued_at_utc"],expires_at_utc=w["current_authority_expires_at_utc"],owner_root_go_sha256=w["owner_root_go_sha256"])
    rebuilt=terminal_witness(w["original_choice_binding"],w["restored_choice_binding"],w["original_terminal_binding"],w["restored_terminal_binding"],
        terminal,choice,evidence,producer,old,physical,a,created_at=w["created_at_utc"],terminal_bytes=terminal_bytes,index_bytes=index_bytes,handoff=h,
        policy_bytes=policy_bytes,catalog_bytes=catalog_bytes,past_witness_bytes=past_bytes)
    require(rebuilt == w,"EXACT_CLOSED_DERIVED_ORIGIN_WITNESS")
    require(slate == original_slate(choice,terminal,{"input_cutoff_utc":"2026-10-25T00:00:00Z"}),"EXPLICIT_SOURCE_BOUND_RECONSTRUCTED_ORIGINAL_SLATE")
    from . import weekly_generic_producer as generic,weekly_adaptive as selector
    generic.restore_choices(choice,slate=slate,catalog=catalog,policy=policy,selector=selector,now=checked_at)
    return store.utc(terminal["decision_persist_completed_at"])


def source_pairs(plan, checkpoint_receipt, storage):
    names = plan["checkpoint_config"]["source_names"]
    expected = {"nflverse_LICENSE.md","players.parquet","schedules.csv"}|{f"{kind}_{year}.parquet" for kind in ("roster_weekly","stats_player_week") for year in range(2019,2027)}
    require(set(names) == expected and checkpoint_receipt["files"] == 78 and checkpoint_receipt["model_decodes"] == 0,
        "EXACT_ORIGINAL78_SOURCE_HISTORY_SCOPE_REQUIRED")
    mapping = {ref["path"]:ref for ref in checkpoint_receipt["path_mapping"].values()}
    raw = Path(checkpoint_receipt["source_cache"])/"raw"; pairs = {}
    for name,url in names.items():
        body,receipt = mapping[str(raw/name)],mapping[str(raw/(name+".receipt.json"))]
        doc = owned_document(storage,receipt,cap=256 << 10)
        require(doc["url"] == url and doc["sha256"] == body["sha256"] and doc["bytes"] == body["bytes"]
            and doc["status"] in {"acquired","stale_cache"}, "ORIGINAL_SOURCE_RECEIPT_HASH_AND_URL_REQUIRED")
        pairs[name] = dict(body=body,receipt=receipt)
    validate_owned_references(storage,{r["path"]:r["sha256"] for pair in pairs.values() for r in pair.values()})
    mutable = {"schedules.csv","players.parquet","stats_player_week_2026.parquet","roster_weekly_2026.parquet"}
    return pairs,{n:r for n,r in pairs.items() if n not in mutable}


def recover(request, authority, storage, job, env, root, *, transport=None):
    config = validate_request(request,root)
    require(authority["request_sha256"] == store.sha(store.canonical(request)) and authority["source_sha"] == env["GITHUB_SHA"]
        and authority["run_id"] == env["GITHUB_RUN_ID"] and authority["workflow_ref"] == request["input_plan"]["parent"]["workflow_ref"],
        "FRESH_CURRENT_AUTHORITY_AND_ORIGINAL_WORKFLOW_REQUIRED")
    output = Path(request["output"])
    require(not output.exists(), "FRESH_ORIGIN_RECOVERY_ROOT_NO_RETRY")
    with storage.transaction():
        storage._require(1 << 20);storage.register_root(output)
    history_root = output/"original78";history_root.mkdir(mode=0o700)
    context = dict(plan_sha256=store.sha(store.canonical(request["input_plan"])),source_sha=authority["source_sha"],run_id=authority["run_id"],
        output_root=str(history_root),issued_at_utc=authority["issued_at_utc"],rights_review=dict(scope="GET_ONLY_ORIGINAL_OWNED_HISTORY_OPAQUE",
            source_policy_sha256=cp.POLICY_SHA,model_decodes=0,protected_outcome_reads=0,owner_root_go_sha256=authority["owner_root_go_sha256"]))
    selected_output = output/"selected-origin";selected_output.mkdir(mode=0o700)
    journal = selected_output/"journal";journal.mkdir(mode=0o700)
    cp.seed_pending(journal,config["external_pending_reservations"])
    archived = read_document(Path(root)/config["canary_report"])
    handoff = deepcopy(request["selected_handoff"]);witness = handoff.pop("witness_descriptor")
    require(archived["binding"] == handoff["runtime_binding"] and store.sha(store.canonical(archived["binding"])) == config["binding_sha256"]
        and store.sha(store.canonical(archived["qualification"])) == config["qualification_sha256"], "ORIGINAL_QUALIFIED_SELECTED_RUNTIME_REQUIRED")
    owner.archived_qualification(archived["binding"],archived["qualification"])
    clients=[]
    class ReadOnly(store.Client):
        def request(self,url,*,method="GET",**kwargs):
            require(method == "GET" and kwargs.get("data") is None,"ORIGIN_RECOVERY_GET_ONLY")
            return super().request(url,method=method,**kwargs)
        def reserve_post(self,*args,**kwargs):
            raise store.StoreError("ORIGIN_RECOVERY_CANNOT_RESERVE_POST")
    class Factory:
        last=None
        def __call__(self,operation):
            require(operation == "restore" and len(clients) < 11,"ELEVEN_GET_ONLY_SELECTED_RESTORES")
            c=ReadOnly(env.get("GITHUB_TOKEN"),authority["run_id"],journal=journal,source_sha=authority["source_sha"],
                job=job,transport=transport,operation="restore")
            c.authenticate_actions_job();c.bind(handoff["runtime_binding"])
            require(c.job["api_job_id"] == authority["api_job_id"] and c.run_id != SELECTED_RUN,"ACTUAL_NEW_ORIGIN_API_JOB_REQUIRED")
            self.last=c;clients.append(c);return c
    factory=Factory();first=factory("restore")
    evidence=authenticate_selected_jobs(first,request["selected_origin"],authority["issued_at_utc"])
    owner.authenticate_past_run(first,archived["qualification"]);first.inventory();owner.verify_canary(first)
    # Current identity and all three selected predecessors have been verified
    # before either private restore. These are new authority/current API facts,
    # not historical identities relabeled as a running job.
    restored_inputs = audit.restore_checkpoint(request["input_plan"],context,storage,job,env,transport=transport)
    full = owned_document(storage,restored_inputs["checkpoint_receipt"])
    pairs,historical = source_pairs(request["input_plan"],full,storage)
    used=False
    class Restores:
        last=first
        def __call__(self,operation):
            nonlocal used
            require(operation == "restore","NO_SELECTED_WITNESS_APPEND_ALLOWED")
            if not used:used=True;return first
            self.last=factory(operation);return self.last
    historical_config=deepcopy(config);historical_config.update(_sha256=SELECTED_CONFIG_SHA,_qualification=archived["qualification"])
    result=snapshot.restore_snapshot(handoff,Restores(),storage,selected_output,historical_config,
        producer_api_job_id=SELECTED_JOBS["producer"][1],witness=witness,witness_api_job_id=SELECTED_JOBS["reader"][1])
    meta={name:owned_document(storage,result[name]) for name in ("terminal","decision","startup_policy","procedure_catalog","producer_proof","durability","completion","inference_consumed")}
    index=owned_document_gzip(storage,result["selected_snapshot_index"])
    old_proof=meta["durability"]["restore_proof"]
    store.check_proof(factory.last,old_proof,"restore",same_run=False)
    relocated=owned_document(storage,result["selected_relocation"]);physical=relocated["physical_restore_proof"]
    bundle={k:meta[k] for k in ("terminal","completion","inference_consumed","producer_proof","durability")}
    bundle.update(terminal_body_sha256=result["terminal"]["sha256"],inference_consumed_body_sha256=result["inference_consumed"]["sha256"],
        inference_consumed_body_bytes=result["inference_consumed"]["bytes"])
    acceptance.facts(bundle,dict(producer_policy_sha256=config["producer_policy_sha256"],source_policy_sha256=cp.POLICY_SHA))
    original_choice=index["metadata_refs"]["decision"];original_terminal=index["metadata_refs"]["terminal"]
    observation=dict(schema_version=VERSION+"-observed-original-clocks",source_sha=SELECTED_SOURCE,run_id=SELECTED_RUN,
        original_choice_sha256=original_choice["sha256"],original_terminal_sha256=original_terminal["sha256"],
        actual_choice_frozen_at=meta["decision"]["actual_frozen_at"],declared_weekly_deadline=meta["decision"]["weekly_deadline_utc"],
        terminal_decision_persist_completed_at=meta["terminal"]["decision_persist_completed_at"],
        original_producer_completed_at=evidence["producer"]["completed_at"],
        current_observed_at_utc=now().isoformat(),original_completion_file_retained=False,
        independently_authenticated_historical_jobs=True,forecasts=0,fits=0,public_release=False)
    storage.write_bytes(output/"ORIGIN_CLOCK_OBSERVATION.json",store.canonical(observation))
    derived=terminal_witness(original_choice,result["decision"],original_terminal,result["terminal"],meta["terminal"],meta["decision"],evidence,
        meta["producer_proof"],old_proof,physical,authority,created_at=now().isoformat(),
        terminal_bytes=cp.read_ref(result["terminal"],2 << 20),index_bytes=cp.read_ref(result["selected_snapshot_index"],snapshot.INDEX_CAP),
        handoff=request["selected_handoff"],policy_bytes=cp.read_ref(result["startup_policy"],2 << 20),
        catalog_bytes=cp.read_ref(result["procedure_catalog"],2 << 20),
        past_witness_bytes=cp.read_ref(cp.binding(selected_output/"owned/job3-witness.gz"),snapshot.INDEX_CAP))
    derived_slate=original_slate(meta["decision"],meta["terminal"],config)
    from .weekly_generic_producer import restore_choices
    from . import weekly_adaptive
    restore_choices(meta["decision"],slate=derived_slate,catalog=meta["procedure_catalog"],policy=meta["startup_policy"],selector=weekly_adaptive,now=now())
    validate_terminal_witness(derived,cp.read_ref(result["decision"],512 << 10),derived_slate,
        meta["procedure_catalog"],meta["startup_policy"],now())
    def write(name,value):
        path=output/name;storage.write_bytes(path,store.canonical(value));return cp.binding(path)
    api_ref=write("ORIGINAL_SELECTED_API_EVIDENCE.json",evidence)
    witness_ref=write("DERIVED_SOURCE_BOUND_TERMINAL_WITNESS.json",derived)
    slate_ref=write("DERIVED_ORIGINAL_SLATE.json",derived_slate)
    index_ref=result["selected_snapshot_index"]
    calls=restored_inputs["HTTP_calls"]+sum(c.calls for c in clients)
    require(calls <= LIMITS["HTTP_calls"],"ORIGIN_TOTAL_HTTP_LIMIT")
    final=dict(schema_version=VERSION+"-result",state="ORIGINALS_RECOVERED_GET_ONLY",created_at_utc=now().isoformat(),
        current_run_id=authority["run_id"],current_source_sha=authority["source_sha"],owner_root_go_sha256=authority["owner_root_go_sha256"],
        original_choice=result["decision"],original_catalog=result["procedure_catalog"],original_policy=result["startup_policy"],
        original_slate=slate_ref,original_terminal=result["terminal"],original_terminal_witness=witness_ref,original_completion_file_retained=False,
        historical_config_sha256=SELECTED_CONFIG_SHA,historical_source_sha=SELECTED_SOURCE,original_source_pairs=pairs,historical_sources=historical,
        history_binding=dict(bytes=index_ref["bytes"],sha256=index_ref["sha256"]),history_scope="OPAQUE_COMPLETE_ORIGINAL_SELECTED_SNAPSHOT_INDEX_NOT_OUTCOME_GRADES",
        original_selected=result["selected"],original_snapshot_index=index_ref,selected_relocation=result["selected_relocation"],
        historical_job_api_evidence=api_ref,original78_restore=cp.binding(history_root/"RESTORE_RECEIPT.json"),
        selected_physical_restore_proof_sha256=store.sha(store.canonical(physical)),historical_reader_restore_proof_sha256=store.sha(store.canonical(old_proof)),
        opaque_candidates_retained=18,source_history_seasons=list(range(2019,2027)),HTTP_calls=calls,
        fits=0,model_decodes=0,requalifications=0,remote_writes=0,protected_outcome_reads=0,public_release=False)
    write("ORIGIN_RESULT.json",final)
    return final


def owned_document_gzip(storage,reference):
    validate_owned_references(storage,{reference["path"]:reference["sha256"]})
    raw=cp.read_ref(reference,store.ASSET_CAP)
    # Only the closed snapshot INDEX is inflated, never selected/candidate rows.
    return snapshot.unpack(raw,snapshot.INDEX_CAP)
