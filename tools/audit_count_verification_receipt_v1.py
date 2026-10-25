"""Publish one closed engineering-verification check after genuine restoration.

No models, fixtures, predictions, outcomes or private paths enter the payload.
Only the existing public-safe replay catalog and exact identity/control hashes
are published. The fixed one-shot POST has durable local intent and no retry.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab import audit_count_checkpoint_v1 as checkpoint, audit_count_requalify_v1 as audit
from nfl_lab import gha_private_checkpoint as cp, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_count_hosted_v1 as hosted
from tools.private_draft_store_v2 import actions_context, limits

VERSION = "audit-count-verification-receipt-v1"
SELF_PIN = "tools/audit_count_verification_receipt_v1.py"
ENDPOINT = store.API + "/check-runs"
NAME = "Effective model restoration"
TITLE = "18 effective models restored and replayed"
RESTORE_STEP = "Restore and replay the complete new effective model checkpoint"
BODY_CAP = 24 << 10
RESPONSE_CAP = 128 << 10
RESTORED_CAP = 256 << 10
PUBLIC_KEYS = {"schema_version", "repository", "source_sha", "run_id", "run_attempt", "reader_job_id",
               "reader_api_job_id", "root_go_sha256", "restored_control_sha256", "replay_catalog_sha256",
               "replay_catalog", "model_pairs", "fits", "model_artifact_durability", "successful_forecast",
               "scientific_qualification", "public_release"}


class Quiet:
    def write(self, value):
        return len(value)

    def flush(self):
        pass


def require(value, code):
    if not value:
        raise store.StoreError(code)


class CheckClient(store.Client):
    """Narrow extension for the one authorized, fixed repository Checks POST."""
    def reserve_post(self, url, key, body, *, name=None):
        require(url == ENDPOINT and key == "verification-check:" + self.run_id + ":1" and name is None
                and type(body) is bytes and 0 < len(body) <= BODY_CAP and url not in self.posts,
                "EXACT_VERIFICATION_CHECK_POST_REQUIRED")
        self.reserve(key, body, name=None)  # O_EXCL + fsync; never cleared/reused.
        self.posts[url] = store.sha(body)


def owned_json(storage, path, cap):
    reference = storage.validate_reference(path)
    require(0 < reference["bytes"] <= cap, "BOUNDED_OWNED_VERIFICATION_CONTROL")
    body = store.read_local(path, cap)
    require(len(body) == reference["bytes"] and store.sha(body) == reference["sha256"], "VERIFICATION_CONTROL_HASH")
    return cp.strict_json(body), body, reference


def verify_actual_reader(client, restored):
    jobs = client.json(client.allow(client.path("/actions/runs/" + client.run_id + "/jobs?per_page=100&page=1")))
    require(type(jobs) is dict and type(jobs.get("jobs")) is list
            and jobs.get("total_count") == len(jobs["jobs"]) <= 100, "COMPLETE_VERIFICATION_ACTIONS_JOBS")
    readers = [j for j in jobs["jobs"] if j.get("id") == client.job["api_job_id"]
               and j.get("name") == checkpoint.READER_JOB and j.get("head_sha") == client.source_sha
               and j.get("run_id") == int(client.run_id) and j.get("status") == "in_progress"]
    require(len(readers) == 1 and type(readers[0].get("steps")) is list
            and len(readers[0]["steps"]) <= 128, "GENUINE_VERIFICATION_READER_REQUIRED")
    steps = [step for step in readers[0]["steps"] if step.get("name") == RESTORE_STEP]
    require(len(steps) == 1 and steps[0].get("status") == "completed" and steps[0].get("conclusion") == "success"
            and store.utc(steps[0]["started_at"]) <= store.utc(steps[0]["completed_at"])
            <= store.utc(client.started_at), "ACTUAL_SUCCESSFUL_RESTORE_STEP_REQUIRED")
    producer = restored["original_producer"]
    writers = [j for j in jobs["jobs"] if j.get("id") == producer["api_job_id"]]
    require(len(writers) == 1 and writers[0].get("name") == checkpoint.WRITER_JOB
            and writers[0].get("head_sha") == client.source_sha and writers[0].get("run_id") == int(client.run_id)
            and writers[0].get("status") == "completed" and writers[0].get("conclusion") == "success"
            and store.utc(writers[0]["completed_at"]) <= store.utc(readers[0]["started_at"]),
            "ACTUAL_SUCCESSFUL_VERIFICATION_PRODUCER_REQUIRED")


def verified_payload(storage, base, client, root_sha):
    catalog, catalog_bytes, _ = owned_json(storage, base / "REPLAY_CATALOG.json", 16 << 10)
    restored, _, restored_ref = owned_json(storage, base / "RESTORED.json", RESTORED_CAP)
    safe_catalog = checkpoint.safe_replay_catalog(catalog)
    require(catalog_bytes == safe_catalog and restored["replay_catalog"] == catalog
            and restored["replay_catalog_sha256"] == store.sha(safe_catalog)
            and catalog["source_sha"] == client.source_sha and catalog["run_id"] == client.run_id,
            "EXACT_OWNED_REPLAY_CATALOG_REQUIRED")
    require(restored["schema_version"] == checkpoint.VERSION + "-restore"
            and restored["state"] == "EFFECTIVE18_RESTORED_AND_LOADER_REPLAYED"
            and type(restored["model_pairs"]) is int and restored["model_pairs"] == 18
            and type(restored["files"]) is int and restored["files"] == 38
            and type(restored["fits"]) is int and restored["fits"] == 0
            and restored["fresh_process_replay"] is True and restored["model_artifact_durability"] is True
            and all(restored[k] is False for k in ("successful_forecast", "scientific_qualification",
                "public_release", "private_durability_qualified"))
            and restored["root_go_sha256"] == root_sha
            and store.utc(restored["actual_completed_at"]) <= store.utc(client.started_at),
            "ACTUAL_COMPLETE_MODEL_RESTORATION_REQUIRED")
    reader, producer = restored["reader"], restored["original_producer"]
    for identity, label in ((reader, checkpoint.READER_JOB), (producer, checkpoint.WRITER_JOB)):
        require(type(identity) is dict and set(identity) == checkpoint.PRODUCER_KEYS
                and identity["execution_lane"] == "github_actions" and identity["repository"] == store.REPO
                and identity["run_id"] == client.run_id and type(identity["run_attempt"]) is int and identity["run_attempt"] == 1
                and identity["source_sha"] == client.source_sha and identity["job_id"] == label
                and identity["workflow_ref"] == client.job["workflow_ref"] and identity["permission"] == "write"
                and type(identity["api_job_id"]) is int and identity["api_job_id"] > 0
                and type(identity["process_identity"]) is str and store.HASH.fullmatch(identity["process_identity"]),
                "EXACT_VERIFICATION_PRODUCER_READER_IDENTITY")
    require(reader["api_job_id"] == client.job["api_job_id"] != producer["api_job_id"]
            and len({reader["process_identity"], producer["process_identity"], client.process}) == 3,
            "INDEPENDENT_VERIFICATION_PROCESS_REQUIRED")
    require(type(restored["models"]) is list and len(restored["models"]) == 18
            and all(ref["sha256"] == slot["manifest_sha256"] for ref, slot in zip(restored["models"], catalog["slots"])),
            "COMPLETE_RESTORED_CATALOG_BINDING")
    groups, proofs = restored["group_sha256"], restored["proofs"]
    require(type(groups) is list and 0 < len(groups) <= checkpoint.MAX_GROUPS
            and all(type(value) is str and store.HASH.fullmatch(value) for value in [restored["index_sha256"], *groups])
            and type(proofs) is list and len(proofs) == len(groups) + 1, "COMPLETE_VERIFICATION_RESTORE_PROOFS")
    for proof, digest in zip(proofs, [restored["index_sha256"], *groups]):
        store.check_proof(client, proof, "restore")
        require(proof["payload_sha256"] == digest and proof["process_identity"] == reader["process_identity"]
                and proof["job"]["api_job_id"] == reader["api_job_id"] and proof["job"]["job_id"] == checkpoint.READER_JOB,
                "EXACT_GENUINE_READER_RESTORE_PROOF")
    verify_actual_reader(client, restored)
    public = dict(schema_version=VERSION, repository=store.REPO, source_sha=client.source_sha, run_id=client.run_id,
        run_attempt=1, reader_job_id=checkpoint.READER_JOB, reader_api_job_id=client.job["api_job_id"], root_go_sha256=root_sha,
        restored_control_sha256=restored_ref["sha256"], replay_catalog_sha256=store.sha(safe_catalog), replay_catalog=catalog,
        model_pairs=18, fits=0, model_artifact_durability=True, successful_forecast=False,
        scientific_qualification=False, public_release=False)
    require(set(public) == PUBLIC_KEYS, "CLOSED_PUBLIC_VERIFICATION_RECEIPT")
    summary = store.canonical(public)
    require(not any(marker in summary for marker in (b"https://", b"/tmp/", b"/workspace/", b"/home/", b"ghs_",
                b"content_b64", b"float64_hex", b"fixture", b"prediction")), "HASH_ONLY_PUBLIC_AUDIT_METADATA")
    payload = dict(name=NAME, head_sha=client.source_sha, status="completed", conclusion="success",
                   external_id=client.run_id + ":1", output=dict(title=TITLE, summary=summary.decode()))
    body = store.canonical(payload)
    require(len(body) <= BODY_CAP, "VERIFICATION_PAYLOAD_24K_CAP")
    return payload, body


def response(client, url, *, method="GET", data=None):
    status, headers, body = client.request(url, method=method, data=data, cap=RESPONSE_CAP)
    require(status == (201 if method == "POST" else 200)
            and headers.get("x-ratelimit-remaining") != "0" and "retry-after" not in headers,
            "VERIFICATION_HTTP_OR_RATE_AMBIGUITY")
    return cp.strict_json(body)


def check_response(document, payload, check_id=None):
    require(type(document) is dict and type(document.get("id")) is int and 0 < document["id"] < 10**20,
            "EXACT_VERIFICATION_CHECK_ID")
    check_id = document["id"] if check_id is None else check_id
    require(document["id"] == check_id and document.get("url") == ENDPOINT + "/" + str(check_id)
            and all(document.get(key) == payload[key] for key in ("name", "head_sha", "status", "conclusion", "external_id"))
            and type(document.get("output")) is dict
            and document["output"].get("title") == payload["output"]["title"]
            and document["output"].get("summary") == payload["output"]["summary"], "EXACT_VERIFICATION_CHECK_READBACK")
    return check_id


def run(env, *, transport=None):
    root_body = env.get("AUDIT_COUNT_ROOT_GO_JSON", "").encode()
    root_sha = env.get("AUDIT_COUNT_ROOT_GO_SHA256", "")
    require(0 < len(root_body) <= 16384, "BOUNDED_VERIFICATION_ROOT_GO")
    root_go = hosted.checked_root(root_body, root_sha, env)
    require(root_go["helper_sha256"].get(SELF_PIN) == store.sha(store.read_local(ROOT / SELF_PIN, 2 << 20)),
            "VERIFICATION_HELPER_MUST_BE_OWNER_PINNED")
    require(env.get("GITHUB_JOB") == checkpoint.READER_JOB, "GENUINE_VERIFICATION_READER_JOB_ONLY")
    job = actions_context(env, "write")
    root = store.parents_safe(env["RUNNER_TEMP"]) / (audit.VERSION + "-" + env["GITHUB_RUN_ID"])
    require((root / "cache/operational-storage-v2/registry.json").is_file(), "EXISTING_OWNED_READER_STORE_REQUIRED")
    base = root / "effective-checkpoint-restore"
    output = base / VERSION
    require(not output.exists(), "VERIFICATION_ALREADY_ATTEMPTED_NO_RETRY")
    # The actual reader's existing private journal is required, not recreated.
    client = CheckClient(env.get("GITHUB_TOKEN"), env["GITHUB_RUN_ID"], journal=root / "private-journal",
                        source_sha=env["GITHUB_SHA"], job=job, operation=VERSION, transport=transport)
    client.authenticate_actions_job()  # Real current run/source/job before private controls.
    archived = cp.strict_json(store.read_local(ROOT / "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json", store.META_CAP))
    client.bind(archived["binding"])
    policy_body = store.read_local(ROOT / "config/operational-source-policy-v2.json", 1 << 20)
    require(store.sha(policy_body) == cp.POLICY_SHA, "EXACT_VERIFICATION_SOURCE_POLICY")
    storage = OperationalStorage(root / "cache", cp.strict_json(policy_body), state=root / "state")
    with storage.transaction():
        payload, body = verified_payload(storage, base, client, root_sha)
        require(datetime.now(timezone.utc) < store.utc(root_go["expires_at_utc"]), "VERIFICATION_ROOT_GO_EXPIRED")
        storage._require(len(body) + 16384)
        storage.register_root(output)
        storage.write_bytes(output / "PAYLOAD.json", body)
        storage.write_bytes(output / "POST_INTENT.json", store.canonical(dict(schema_version=VERSION + "-POST-intent",
            endpoint=ENDPOINT, name=NAME, head_sha=client.source_sha, external_id=payload["external_id"],
            bytes=len(body), body_sha256=store.sha(body), automatic_retries=0)))
        try:
            client.reserve_post(ENDPOINT, "verification-check:" + client.run_id + ":1", body)
            require(datetime.now(timezone.utc) < store.utc(root_go["expires_at_utc"]), "VERIFICATION_ROOT_GO_EXPIRED")
            posted = response(client, ENDPOINT, method="POST", data=body)
            check_id = check_response(posted, payload)
            url = ENDPOINT + "/" + str(check_id)
            client.allowed.add(url)  # Fixed repository and positive returned ID only.
            check_response(response(client, url), payload, check_id)
            result = dict(check_run_id=check_id, body_sha256=store.sha(body))
            storage.write_bytes(output / "READBACK_VERIFIED.json", store.canonical(result))
            return result
        except BaseException:
            try:
                storage.write_bytes(output / "POST_FAILED_OR_AMBIGUOUS.json", store.canonical(dict(
                    schema_version=VERSION + "-unverified", body_sha256=store.sha(body), automatic_retries=0)))
            except Exception:
                pass
            raise


def main(argv=None, *, environ=None, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print('{"check_run_id":null,"body_sha256":null}')
        return 2
    try:
        limits()
        with redirect_stdout(Quiet()), redirect_stderr(Quiet()):
            result = run(os.environ if environ is None else environ, transport=transport)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print('{"check_run_id":null,"body_sha256":null}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
