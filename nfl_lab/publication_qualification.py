"""Opt-in private publication views; no outcomes, rehydration or scoring.

This prepares an input boundary. Existing consumers are deliberately not wired
to it, and remote readback remains the original publisher's attestation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess

from . import publication_scope
from .state import digest, records, utc

VERSION = "scoped-publication-qualification-v1"
QUALIFICATION_POLICY_SHA256 = "0f400a19d4f02abe129dc340f116940434881092ac7e29574daab2349c881263"
POINT_SHADOW = "fixed_opportunity_rate_point; mean_or_median_unverified"


def _sha(value):
    return isinstance(value, str) and publication_scope.SHA256.fullmatch(value) is not None


def _opportunity(row):
    fields = ("player_id", "game_id", "target", "model_id")
    return tuple(row[k] for k in fields) if all(isinstance(row.get(k), str) and row[k] for k in fields) else None


def _index(state, kind, field):
    result = defaultdict(list)
    for receipt in records(state, kind):
        result[receipt.get(field)].append(receipt)
    return result


class _Views:
    def __init__(self, root, state, scopes, policy):
        if not _sha(policy) or not isinstance(scopes, dict):
            raise ValueError("explicit policy SHA256 and original scope mapping required")
        self.root, self.state, self.scopes, self.policy = root, state, scopes, policy
        self.scope_cache = {}
        self.reasons = Counter()
        self.receipt_reasons = Counter()
        self.legacy = Counter()
        self.offered = Counter()
        self.qualified = Counter()

    def scope(self, scope_sha):
        if scope_sha not in self.scope_cache:
            envelope = self.scopes.get(scope_sha)
            if envelope is None:
                return None
            if not isinstance(envelope, dict) or digest(envelope) != scope_sha:
                raise ValueError("original scope digest mismatch")
            selected = publication_scope.verify_committed_scope(
                self.root, self.state, commit=envelope.get("commit"), scope=envelope,
                policy_sha256=self.policy)
            self.scope_cache[scope_sha] = (deepcopy(envelope), {
                (kind, key): (document, evidence) for kind, key, document, evidence in selected})
        return self.scope_cache[scope_sha]

    def publication(self, kind, key, document, candidates):
        field = "batch" if kind == "forecasts" else "snapshot"
        valid, contradiction = [], False
        for receipt in candidates:
            if receipt.get("publication_scope_schema") != publication_scope.SCHEMA:
                self.legacy[kind] += 1
                continue
            try:
                if (receipt.get(field) != key or ("snapshot" if field == "batch" else "batch") in receipt
                        or receipt.get("state_path") != f"{kind}/{key}.json.gz"
                        or not _sha(receipt.get("file_sha256"))
                        or not _sha(receipt.get("publication_scope_sha256"))
                        or not isinstance(receipt.get("commit"), str)
                        or publication_scope.COMMIT.fullmatch(receipt["commit"]) is None
                        or receipt.get("verified_remote_commit") != receipt["commit"]
                        or not isinstance(receipt.get("git_blob_oid"), str)
                        or publication_scope.COMMIT.fullmatch(receipt["git_blob_oid"]) is None):
                    raise ValueError("receipt identity")
                proof = self.scope(receipt["publication_scope_sha256"])
                if proof is None:
                    self.receipt_reasons["SCOPE_EVIDENCE_UNAVAILABLE"] += 1
                    continue
                envelope, selected = proof
                entry = selected.get((kind, key))
                if (envelope["commit"] != receipt["commit"]
                        or envelope["verified_remote_commit"] != receipt["verified_remote_commit"]
                        or entry is None or entry[0] != document
                        or any(receipt.get(k) != v for k, v in entry[1].items())):
                    raise ValueError("receipt committed scope")
                observed = utc(receipt["observed_remote_readback_at"])
                timely = sum(utc(r["kickoff_utc"]) > observed for r in document["rows"])
                if (any(type(receipt.get(k)) is not int for k in ("timely_rows", "late_rows"))
                        or receipt["timely_rows"] != timely
                        or receipt["late_rows"] != len(document["rows"]) - timely):
                    raise ValueError("publication counters")
                valid.append((observed, digest(receipt), receipt))
            except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
                contradiction = True
                self.receipt_reasons["INVALID_SCOPED_PUBLICATION_EVIDENCE"] += 1
        if contradiction:
            return None, "CONTRADICTORY_PUBLICATION_EVIDENCE"
        if not valid:
            return None, ("SCOPE_EVIDENCE_UNAVAILABLE" if any(
                r.get("publication_scope_schema") == publication_scope.SCHEMA for r in candidates)
                else "NO_SCOPED_PUBLICATION")
        observed, receipt_sha, receipt = min(valid, key=lambda x: (x[0], x[1]))
        return {"observed_remote_readback_at": observed.isoformat(),
                "publication_receipt_sha256": receipt_sha,
                "publication_scope_sha256": receipt["publication_scope_sha256"],
                "commit": receipt["commit"], "state_path": receipt["state_path"],
                "file_sha256": receipt["file_sha256"], "git_blob_oid": receipt["git_blob_oid"]}, None

    def persistence(self, key, document, candidates):
        if not candidates:
            return None, "PERSISTENCE_EVIDENCE_UNAVAILABLE"
        if len({digest(r) for r in candidates}) != 1:
            return None, "CONTRADICTORY_PERSISTENCE_EVIDENCE"
        receipt = candidates[0]
        try:
            start, complete = utc(document["persist_started_at"]), utc(receipt["completed_at"])
            late = sorted({r["game_id"] for r in document["rows"] if utc(r["kickoff_utc"]) <= complete})
            if start > complete or receipt.get("late_games") != late:
                raise ValueError("persistence clock/counter mismatch")
            return {"persist_started_at": start.isoformat(), "completed_at": complete.isoformat(),
                    "persistence_receipt_sha256": digest(receipt)}, None
        except (ValueError, TypeError, KeyError):
            return None, "INVALID_PERSISTENCE_EVIDENCE"

    def documents(self, kind, documents=None):
        web = kind == "website_bindings"
        field = "snapshot" if web else "batch"
        persistence = _index(self.state, "website_persistence" if web else "persistence", field)
        publication = _index(self.state, "website_publication" if web else "publication", field)
        for document in records(self.state, kind) if documents is None else documents:
            key = digest(document)
            rows = document.get("rows")
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ValueError("immutable document requires row dictionaries")
            self.offered[kind] += len(rows)
            proof, reason = self.publication(kind, key, document, publication.get(key, []))
            persistence_proof, persistence_reason = self.persistence(key, document, persistence.get(key, []))
            reason = reason or persistence_reason
            expected_schema = "website-point-bindings-v1" if web else "lab-forecast-batch-v1"
            if document.get("schema_version") != expected_schema:
                reason = "INVALID_DOCUMENT_SCHEMA"
            if reason:
                self.reasons[reason] += len(rows)
                continue
            if utc(persistence_proof["completed_at"]) > utc(proof["observed_remote_readback_at"]):
                self.reasons["PUBLICATION_BEFORE_PERSISTENCE"] += len(rows)
                continue
            yield key, document, {**persistence_proof, **proof}

    def forecasts(self):
        # Index every original capture, including unqualified/legacy batches,
        # before filtering. A later publication cannot replace that opportunity.
        documents = list(records(self.state, "forecasts"))
        identities = Counter()
        for document in documents:
            rows = document.get("rows")
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ValueError("immutable document requires row dictionaries")
            identities.update(_opportunity(row) for row in rows)
        result = []
        for key, document, proof in self.documents("forecasts", documents):
            seen = Counter(digest(row) for row in document["rows"])
            for row in document["rows"]:
                try:
                    if row.get("prediction_functional") == POINT_SHADOW:
                        reason = "POINT_SHADOW_UNQUALIFIED"
                    elif (row.get("code_integrity") != "pre_post_source_digest_required"
                          or not _sha(row.get("code_sha256")) or not _sha(row.get("input_sha256"))):
                        reason = "SOURCE_INTEGRITY_UNAVAILABLE"
                    elif seen[digest(row)] != 1 or _opportunity(row) is None or identities[_opportunity(row)] != 1:
                        reason = "CONTRADICTORY_ROW_IDENTITY"
                    elif not (utc(row["feature_cutoff_utc"]) <= utc(row["issued_at"])
                              <= utc(proof["persist_started_at"]) <= utc(proof["completed_at"])
                              <= utc(proof["observed_remote_readback_at"]) < utc(row["kickoff_utc"])):
                        reason = "INCONSISTENT_OR_LATE_CLOCK_CHAIN"
                    else:
                        reason = None
                except (ValueError, KeyError, TypeError):
                    reason = "INVALID_CAPTURE_METADATA"
                if reason:
                    self.reasons[reason] += 1
                else:
                    result.append({"batch_sha256": key, "row_sha256": digest(row),
                                   "row": deepcopy(row), "qualification": deepcopy(proof)})
                    self.qualified["forecasts"] += 1
        return result

    def receipt(self):
        return {"schema_version": VERSION, "qualification_policy_sha256": QUALIFICATION_POLICY_SHA256,
                "expected_source_policy_sha256": self.policy,
                "qualifier_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "commit_verifier_code_sha256": hashlib.sha256(Path(publication_scope.__file__).read_bytes()).hexdigest(),
                "offered_rows": dict(sorted(self.offered.items())),
                "qualified_rows": dict(sorted(self.qualified.items())),
                "unqualified_row_reasons": dict(sorted(self.reasons.items())),
                "receipt_reasons": dict(sorted(self.receipt_reasons.items())),
                "legacy_receipts_unqualified": dict(sorted(self.legacy.items())),
                "status": "PREPARED_OPT_IN_LAYER_NOT_ACTIVE_CONSUMER_REPAIR",
                "scientific_confirmation": "NOT_DETERMINED_BY_PUBLICATION_QUALIFICATION"}


def qualified_forecast_view(root, state, scope_evidence, expected_policy_sha256):
    """Return (copied private qualified forecast entries, aggregate receipt)."""
    views = _Views(root, state, scope_evidence, expected_policy_sha256)
    return views.forecasts(), views.receipt()


def qualified_website_view(root, state, scope_evidence, expected_policy_sha256):
    """Prove both binding and lab row before any future caller rehydration."""
    views = _Views(root, state, scope_evidence, expected_policy_sha256)
    lab = {(r["batch_sha256"], r["row_sha256"]): r for r in views.forecasts()}
    result = []
    for key, document, proof in views.documents("website_bindings"):
        identities = Counter((r.get("lab_forecast_sha256"), r.get("method")) for r in document["rows"])
        for binding in document["rows"]:
            entry = lab.get((document.get("lab_batch"), binding.get("lab_forecast_sha256")))
            reason = "LINKED_LAB_ROW_UNQUALIFIED"
            if entry is not None:
                row, lab_proof = entry["row"], entry["qualification"]
                try:
                    same = all(binding[k] == row[k] for k in (
                        "season", "week", "period", "scoring_id", "game_id", "sleeper_id",
                        "target", "team", "opponent", "position", "kickoff_utc"))
                    same = same and all(binding[k] == row[v] for k, v in {
                        "lab_player_id": "player_id", "lab_model_id": "model_id",
                        "lab_issued_at": "issued_at", "lab_feature_cutoff_utc": "feature_cutoff_utc"}.items())
                    header = document["header"]
                    if (not same or binding.get("method") not in {"raw_sleeper", "pinned_website"}
                            or not _sha(binding.get("value_sha256"))
                            or identities[(binding.get("lab_forecast_sha256"), binding.get("method"))] != 1
                            or any(header[k] != row[k] for k in ("season", "week"))):
                        reason = "CONTRADICTORY_WEBSITE_LINK"
                    elif not (utc(header["generated_at"]) <= utc(header["observed_at"])
                              <= utc(row["feature_cutoff_utc"]) <= utc(row["issued_at"])
                              <= utc(lab_proof["persist_started_at"]) <= utc(lab_proof["completed_at"])
                              <= utc(proof["persist_started_at"]) <= utc(proof["completed_at"])
                              <= utc(proof["observed_remote_readback_at"]) < utc(row["kickoff_utc"])):
                        reason = "INCONSISTENT_OR_LATE_WEBSITE_CLOCK_CHAIN"
                    else:
                        reason = None
                except (ValueError, KeyError, TypeError):
                    reason = "INVALID_WEBSITE_CAPTURE_METADATA"
            if reason:
                views.reasons[reason] += 1
            else:
                result.append({"snapshot_sha256": key, "binding_sha256": digest(binding),
                               "binding": deepcopy(binding), "lab_forecast": deepcopy(entry),
                               "qualification": deepcopy(proof)})
                views.qualified["website_bindings"] += 1
    return result, views.receipt()
