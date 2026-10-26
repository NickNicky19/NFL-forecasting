"""Live current-job authority for the add-only recurring execution path.

Original owner-only operations keep their original actor contract. A scheduled
BOT is accepted only after the externally registered bootstrap authenticates
this actual root, source, event, parent claim and current API job. No JSON flag,
stored proof or environment actor alone can extend that authority.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from . import private_draft_store as store, gha_private_checkpoint as cp
from . import audit_weekly_controller_v1 as controller
from . import audit_weekly_controller_bootstrap_v1 as bootstrap

VERSION = "audit-weekly-operations-authority-v1"
FILES = ("nfl_lab/audit_weekly_operations_authority_v1.py",
         "tests/test_audit_weekly_operations_authority_v1.py")
_KEY = object()
_ENV = ("GITHUB_RUN_ID", "GITHUB_SHA", "GITHUB_JOB", "GITHUB_WORKFLOW_REF",
        "GITHUB_ACTOR", "GITHUB_ACTOR_ID")


def require(value, code):
    if not value:
        raise store.StoreError(code)


def owner(env):
    return (env.get("GITHUB_ACTOR"), env.get("GITHUB_ACTOR_ID")) == ("NickNicky19", "208912933")


def current(env, root_bytes, source_root, **bootstrap_arguments):
    """Authenticate BEFORE private IO; the caller still checks the full schema.

    Optional callbacks are for the same fixed-route bootstrap verifier. They
    supply raw metadata, never an execution result or an approval flag.
    """
    require(type(root_bytes) is bytes and 0 < len(root_bytes) <= 60 << 10,
            "BOUNDED_ACTUAL_OPERATIONS_ROOT_REQUIRED")
    root = cp.strict_json(root_bytes)
    require(type(root) is dict and root_bytes == store.canonical(root), "CANONICAL_ACTUAL_OPERATIONS_ROOT")
    if root.get("operation") != "RECURRING_CAPTURE":
        require(owner(env), "ORIGINAL_OWNER_ONLY_OPERATION")
        return None
    require("registry_version" not in bootstrap_arguments, "FIXED_OPERATIONS_REGISTRY_VERSION")
    function = bootstrap.authorize_owner if owner(env) else bootstrap.authorize_child
    proof = function(env, Path(source_root), root_bytes, registry_version=2, **bootstrap_arguments)
    _verify(proof, env, root_bytes)
    return proof


def child(env, root_bytes, source_root):
    """Extend a legacy native child only after checking the complete new root."""
    root = cp.strict_json(root_bytes)
    if type(root) is dict and root.get("operation") == "RECURRING_CAPTURE":
        from . import audit_weekly_hosted_v1 as hosted
        hosted.validate_root(root, now=hosted.now_utc())
    return current(env, root_bytes, source_root)


def _verify(proof, env, root_bytes):
    require(type(proof) in {bootstrap.Owner, controller.Proof}, "LIVE_OPERATIONS_BOOTSTRAP_REQUIRED")
    d = proof.document
    require(d.get("source_sha") == env.get("GITHUB_SHA")
            and d.get("run_id") == env.get("GITHUB_RUN_ID")
            and d.get("job_id") == env.get("GITHUB_JOB")
            and d.get("actor") == (controller.OWNER if owner(env) else controller.BOT),
            "EXACT_LIVE_OPERATIONS_SOURCE_RUN_JOB_ACTOR")
    if type(proof) is bootstrap.Owner:
        require(owner(env), "OWNER_PROOF_CANNOT_AUTHORIZE_BOT")
        proof.verify(root_sha256=store.sha(root_bytes))
    else:
        require((env.get("GITHUB_ACTOR"), env.get("GITHUB_ACTOR_ID")) == ("github-actions[bot]", "41898282")
                and d.get("schema_version") == controller.VERSION+"-current-child-proof",
                "ONLY_REGISTERED_CURRENT_CHILD_PROOF")
        proof.verify(registration_sha256=d["registration_sha256"], run_id=d["run_id"],
                     job_id=d["job_id"], root_sha256=store.sha(root_bytes))
        seal = getattr(proof, "bootstrap_seal", None)
        require(type(seal) is bootstrap.Seal, "EXTERNALLY_VERIFIED_CURRENT_BOOTSTRAP_REQUIRED")
        seal.verify()
    return proof


class CurrentClient:
    def __init__(self, client, proof, env, root_bytes, key):
        require(key is _KEY, "LIVE_CURRENT_CLIENT_BINDING_REQUIRED")
        self.client, self.proof, self.root_bytes = client, proof, root_bytes
        self.env = {k:env.get(k) for k in _ENV}
        self.process = store.process_identity()
        self.identity = deepcopy(cp.client_identity(client))

    def verify(self, client):
        require(self.process == store.process_identity() and self.client is client
                and self.identity == cp.client_identity(client), "CURRENT_CLIENT_SCOPE_OR_PROCESS_CHANGED")
        _verify(self.proof, self.env, self.root_bytes)
        if type(self.proof) is controller.Proof:
            bootstrap.authorize_client(self.proof, client, self.env, self.root_bytes)
        require(client.job.get("run_authenticated") is True
                and client.job.get("api_job_id") == self.proof.document["api_job_id"],
                "ACTUAL_AUTHENTICATED_OPERATIONS_CLIENT_REQUIRED")
        return self

    def __reduce__(self):
        raise store.StoreError("LIVE_OPERATIONS_CLIENT_CANNOT_BE_SERIALIZED")


def attach(client, proof, env, root_bytes):
    """Call only AFTER actual client.authenticate_actions_job()."""
    if proof is None:
        require(owner(env), "NO_IMPLICIT_BOT_CLIENT_AUTHORITY")
        return client
    _verify(proof, env, root_bytes)
    binding = CurrentClient(client, proof, env, root_bytes, _KEY).verify(client)
    client._audit_operations_current = binding
    return client


def authorize_client_actor(client, run):
    """For an actual current-run API body, never a historical actor override."""
    actor = run.get("actor", {})
    if actor.get("login") == "NickNicky19" and actor.get("id") == 208912933:
        return True
    binding = getattr(client, "_audit_operations_current", None)
    require(type(binding) is CurrentClient, "LIVE_CURRENT_BOT_CLIENT_REQUIRED")
    binding.verify(client)
    require(type(binding.proof) is controller.Proof and actor.get("login") == "github-actions[bot]"
            and actor.get("id") == 41898282 and run.get("id") == int(client.run_id)
            and run.get("head_sha") == client.source_sha
            and run.get("event") == "workflow_dispatch" and run.get("run_attempt") == 1,
            "ACTUAL_CURRENT_REGISTERED_BOT_RUN_REQUIRED")
    return True
