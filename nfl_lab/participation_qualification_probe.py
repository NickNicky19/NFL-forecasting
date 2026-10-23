"""One terms-only private prerequisite capture; no permission or NFL rows inferred.

V1 has no approved terms hashes. A later separately registered plan can review
the retained document; this invocation cannot fetch a game page or gamebook.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import resource
import signal
import stat
import sys
import time
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

from .operational_storage import OperationalStorage, _no_symlinks, _stamp

VERSION = "participation-qualification-probe-v1"
POLICY_SHA256 = "7a0295511a136149b141ed551e0ec9ec4b7d6e6b7d0f655b8cdb24c1a6dd627b"
SOURCE_POLICY_SHA256 = "e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441"
TERMS_URL = "https://www.nfl.com/legal/terms"
GAME_URL = "https://www.nfl.com/games/lions-at-chiefs-2023-reg-1"
REDIRECT_URLS = (TERMS_URL, TERMS_URL + "/", "https://nfl.com/legal/terms", "https://nfl.com/legal/terms/")
LIMITS = {"invocations": 1, "automatic_retries": 0, "HTTP_transactions_including_redirects": 3,
    "total_body_bytes": 6 * 1024**2, "terms_body_bytes": 1024**2, "HTML_body_bytes": 1024**2,
    "PDF_body_bytes": 4 * 1024**2, "wall_seconds": 60, "CPU_seconds": 60,
    "RSS_bytes": 512 * 1024**2, "threads": 1, "shared_unique_file_bytes": 512 * 1024**2,
    "finalization_reserve_seconds": 3}
PACKAGES = ("requests", "urllib3", "pandas", "numpy")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _absolute(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.resolve() != path.absolute():
        raise ValueError("canonical absolute path required")
    _no_symlinks(path)
    return path


def _read(binding):
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("exact path/hash binding required")
    path = _absolute(binding["path"])
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("frozen input must be regular")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != binding["sha256"] or _stamp(path.lstat()) != _stamp(before):
        raise ValueError("frozen file binding changed")
    return body


def _json(body):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate JSON field")
            value[key] = item
        return value
    def invalid(value):
        raise ValueError("nonfinite JSON literal")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


class _PublicOnlyAuth(AuthBase):
    """Suppress requests' implicit netrc authentication; retain managed proxy/CA."""
    def __call__(self, request):
        return request


class _Budget:
    def __init__(self):
        self.start, self.cpu_start = time.monotonic(), time.process_time()
        self.transactions_consumed = self.transactions_attempted = self.body_bytes = 0

    def usage(self):
        return {"wall_seconds": time.monotonic() - self.start, "CPU_seconds": time.process_time() - self.cpu_start,
            "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "HTTP_transactions_consumed": self.transactions_consumed, "HTTP_transactions_attempted": self.transactions_attempted,
            "identity_encoded_and_decoded_body_bytes_received": self.body_bytes,
            "game_page_HTTP": 0, "PDF_HTTP": 0, "fits_predictions_player_stat_outcome_extractions_scores": 0}

    def check(self):
        used = self.usage()
        if (used["wall_seconds"] >= LIMITS["wall_seconds"] - LIMITS["finalization_reserve_seconds"]
                or used["CPU_seconds"] >= LIMITS["CPU_seconds"] - LIMITS["finalization_reserve_seconds"]
                or used["peak_RSS_bytes"] > LIMITS["RSS_bytes"]):
            raise TimeoutError("probe resource ceiling/finalization reserve reached")


@contextmanager
def _deadline(seconds):
    def expired(signum, frame):
        raise TimeoutError("terms capture wall deadline reached")
    previous = signal.signal(signal.SIGALRM, expired)
    old = signal.setitimer(signal.ITIMER_REAL, max(.001, seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old)
        signal.signal(signal.SIGALRM, previous)


def _preflight(spec):
    required = {"registration_id", "status", "implementation_policy", "source_policy", "cache", "output", "terms_url", "game_url",
        "approved_rights_sha256", "allowed_terms_redirect_urls", "budgets", "code_sha256", "environment", "prior_capture_review"}
    if set(spec) != required or spec["registration_id"] != VERSION or spec["status"] != "PREPARED_UNEXECUTED":
        raise ValueError("exact v1 probe execution schema required")
    if (spec["budgets"] != LIMITS or spec["terms_url"] != TERMS_URL or spec["game_url"] != GAME_URL
            or spec["approved_rights_sha256"] != [] or spec["allowed_terms_redirect_urls"] != list(REDIRECT_URLS)):
        raise ValueError("fixed terms-only v1 scope required; rights clearance needs a later version")
    if spec["implementation_policy"]["sha256"] != POLICY_SHA256 or spec["source_policy"]["sha256"] != SOURCE_POLICY_SHA256:
        raise ValueError("frozen implementation and existing storage/source policy required")
    policy = _json(_read(spec["implementation_policy"]))
    if policy["budgets"]["HTTP_transactions_including_redirects"] != 3 or policy["budgets"]["wall_seconds"] != 60:
        raise ValueError("implementation policy mismatch")
    source_policy = _json(_read(spec["source_policy"]))
    if source_policy["storage"]["limit_bytes"] != LIMITS["shared_unique_file_bytes"] or source_policy["namespaces"]["private_retention_bytes"] != LIMITS["shared_unique_file_bytes"]:
        raise ValueError("unchanged shared 512MiB quota required")
    root = Path(__file__).resolve().parent.parent
    if set(spec["code_sha256"]) != {"nfl_lab/participation_qualification_probe.py", "nfl_lab/operational_storage.py"}:
        raise ValueError("probe and unchanged storage source pins required")
    for name, digest in spec["code_sha256"].items():
        _read({"path": str(root / name), "sha256": digest})
    env = spec["environment"]
    if env["python"] != sys.version or Path(env["executable"]).resolve() != Path(sys.executable).resolve() or env["threads"] != 1 or set(env["packages"]) != set(PACKAGES):
        raise ValueError("exact one-thread interpreter/dependencies required")
    for name in PACKAGES:
        if importlib.metadata.version(name) != env["packages"][name]:
            raise ValueError("dependency differs: " + name)
    if spec["prior_capture_review"]["state"] != "NO_IDENTICAL_INDEXED_CAPTURE_IN_PREVIOUS_BOUNDED_REVIEW":
        raise ValueError("prior duplicate review required; do not repeat census")
    cache, output = _absolute(spec["cache"]), _absolute(spec["output"])
    if cache == output or cache in output.parents or output in cache.parents:
        raise ValueError("fresh capture output must be separate from cache")
    return source_policy, output


def _capture_response(storage, output, response, budget, transaction, url):
    info = {"transaction": transaction, "request_url": url, "response_url": str(response.url),
        "status_code": int(response.status_code), "capture_started_utc": _now(), "bytes": 0, "received_body_bytes": 0,
        "headers": {name: response.headers.get(name) for name in ("Content-Type", "Content-Length", "Content-Encoding", "Location", "ETag", "Last-Modified", "Date")},
        "original_publication_utc": None, "rights": "UNKNOWN", "body_complete": False}
    encoding = (response.headers.get("Content-Encoding") or "identity").strip().lower()
    if encoding not in {"", "identity"}:
        return {**info, "stop_reason": "NONIDENTITY_ENCODING_NOT_CONSUMED", "capture_finished_utc": _now()}
    available = min(LIMITS["terms_body_bytes"] - budget.body_bytes, LIMITS["total_body_bytes"] - budget.body_bytes)
    length = response.headers.get("Content-Length")
    try:
        declared = int(length) if length is not None else None
    except (ValueError, TypeError):
        return {**info, "stop_reason": "INVALID_CONTENT_LENGTH", "capture_finished_utc": _now()}
    if declared is not None and (declared < 0 or declared > available):
        return {**info, "stop_reason": "DECLARED_BODY_EXCEEDS_REMAINING_CAP", "capture_finished_utc": _now()}
    body_path = output / f"private/http/{transaction:03d}/body.bin"
    digest = hashlib.sha256()
    transport_error = None
    try:
        with storage._open_writer(body_path, "wb") as stream:
            while declared is None or info["bytes"] < declared:
                budget.check()
                remaining = min(LIMITS["terms_body_bytes"] - budget.body_bytes, LIMITS["total_body_bytes"] - budget.body_bytes)
                if remaining <= 0:
                    info["stop_reason"] = "BODY_CAP_BOUNDARY_NO_EXTRA_READ"
                    break
                count = min(64 * 1024, remaining, declared - info["bytes"] if declared is not None else remaining)
                chunk = response.raw.read(count, decode_content=False)
                if len(chunk) > count:
                    raise ValueError("HTTP reader violated bounded read size")
                if not chunk:
                    info["body_complete"] = declared is None or info["bytes"] == declared
                    if not info["body_complete"]:
                        info["stop_reason"] = "TRUNCATED_DECLARED_BODY"
                    break
                budget.body_bytes += len(chunk)
                info["received_body_bytes"] += len(chunk)
                # Every retained chunk passes unchanged quota preflight before write.
                stream.write(chunk)
                digest.update(chunk)
                info["bytes"] += len(chunk)
            else:
                info["body_complete"] = True
    except BaseException as error:
        transport_error = error
        info["stop_reason"] = type(error).__name__
    finally:
        if body_path.exists():
            # Preserve partials too; old owned staging promotion avoids a second
            # full body allocation/temporary inode and retains immutable bytes.
            owned = storage.import_file(body_path, body_path)
            info.update(body_path=str(body_path.relative_to(output)), sha256=owned["sha256"], retained_bytes=owned["bytes"])
        info["capture_finished_utc"] = _now()
    if info.get("retained_bytes", 0) != info["bytes"]:
        info["stop_reason"] = "PARTIAL_WRITE_ACCOUNTING_DIFFERENCE"
    info["raw_bytes_hash_matches_counted_chunks"] = info.get("sha256") == digest.hexdigest()
    if transport_error is not None:
        info["transport_error_type"] = type(transport_error).__name__
        raise _CaptureFailure(info) from transport_error
    return info


class _CaptureFailure(RuntimeError):
    def __init__(self, receipt):
        super().__init__("capture failed; bounded partial evidence retained")
        self.receipt = receipt


def run_probe(execution_config, config_sha256):
    """Perform the sole explicitly authorized terms-only bounded invocation."""
    budget = _Budget()
    config_binding = {"path": str(_absolute(execution_config)), "sha256": config_sha256}
    spec = _json(_read(config_binding))
    policy, output = _preflight(spec)
    budget.check()
    storage = OperationalStorage(spec["cache"], policy)
    with storage._locked():
        storage._refresh()
        storage._scan()
        if output.exists():
            raise RuntimeError("probe output already exists; no invocation retry")
        storage.register_root(output)
        storage.atomic_json(output / "PROBE_CONSUMED.json", {"version": VERSION, "config_sha256": config_sha256,
            "policy_sha256": POLICY_SHA256, "consumed_utc": _now(), "invocations": 1, "rights": "UNKNOWN"})
    # Release the reservation flock before networking; every stream/write/import
    # still takes the unchanged quota flock. This lets the outer supervisor write
    # its own logs and enforce the full process deadline without waiting on HTTP.
    result, succeeded = None, False
    try:
        transactions, visited, url = [], set(), TERMS_URL
        remaining = LIMITS["wall_seconds"] - LIMITS["finalization_reserve_seconds"] - budget.usage()["wall_seconds"]
        with _deadline(remaining):
            while True:
                budget.check()
                if url in visited:
                    stop = "REDIRECT_LOOP_NO_REPEAT_REQUEST"
                    break
                if budget.transactions_consumed >= LIMITS["HTTP_transactions_including_redirects"]:
                    stop = "HTTP_TRANSACTION_LIMIT"
                    break
                if budget.body_bytes >= LIMITS["terms_body_bytes"]:
                    stop = "TERMS_BODY_CAP_NO_FURTHER_REQUEST"
                    break
                if url not in REDIRECT_URLS:
                    stop = "REDIRECT_OUTSIDE_EXACT_LEGAL_URL_ALLOWLIST"
                    break
                visited.add(url)
                budget.transactions_consumed += 1
                number = budget.transactions_consumed
                request_path = output / f"private/http/{number:03d}/request-consumed.json"
                storage.atomic_json(request_path, {"transaction": number, "url": url, "started_utc": _now(),
                    "automatic_retries": 0, "allow_redirects": False})
                budget.check()
                budget.transactions_attempted += 1
                remaining = max(.001, LIMITS["wall_seconds"] - LIMITS["finalization_reserve_seconds"] - budget.usage()["wall_seconds"])
                try:
                    with requests.Session() as session:
                        session.mount("https://", HTTPAdapter(max_retries=0))
                        with session.get(url, stream=True, allow_redirects=False, verify=True, auth=_PublicOnlyAuth(),
                                timeout=(min(5., remaining), min(10., remaining)),
                                headers={"Accept-Encoding": "identity", "User-Agent": "NFLForecastingSourceQualification/1.0 (private documentation probe)"}) as response:
                            captured = _capture_response(storage, output, response, budget, number, url)
                except _CaptureFailure as error:
                    storage.atomic_json(output / f"private/http/{number:03d}/response-receipt.json", error.receipt)
                    raise
                storage.atomic_json(output / f"private/http/{number:03d}/response-receipt.json", captured)
                transactions.append(captured)
                if not captured["body_complete"]:
                    stop = captured.get("stop_reason", "INCOMPLETE_HTTP_BODY")
                    break
                status = captured["status_code"]
                if status in (301, 302, 303, 307, 308):
                    location = captured["headers"]["Location"]
                    if not location:
                        stop = "REDIRECT_LOCATION_MISSING"
                        break
                    url = urljoin(url, location)
                    continue
                stop = "TERMS_CAPTURED_RIGHTS_UNKNOWN" if status == 200 else "HTTP_STATUS_NOT_200"
                break
        _read(config_binding)
        _preflight(spec)
        budget.check()
        result = {"version": VERSION, "config_sha256": config_sha256, "policy_sha256": POLICY_SHA256,
            "state": "TERMINAL_RIGHTS_UNKNOWN", "stop_reason": stop, "rights": "UNKNOWN",
            "rights_basis": "No exact reviewed document-hash clearance exists; successful public access is not permission",
            "transactions": transactions, "usage": budget.usage(), "finished_utc": _now(),
            "game_page": "NOT_REQUESTED", "PDF": "NOT_REQUESTED", "schema_headings": "NOT_INSPECTED",
            "new_participation_zero_DNP_PPR_or_historical_availability_claims": 0,
            "next_step": "Separate review of retained terms; any cleared acquisition requires a new versioned plan, never a retry"}
        storage.atomic_json(output / "result.json", result)
        succeeded = True
        return result
    except BaseException as error:
        storage.atomic_json(output / "PROBE_FAILURE.json", {"exception": type(error).__name__, "usage": budget.usage(),
            "rights": "UNKNOWN", "finished_utc": _now(), "partial_evidence_preserved": True, "automatic_retry": False})
        raise
    finally:
        storage.atomic_json(output / "PROBE_FINISHED.json", {"state": "COMPLETED_UNKNOWN" if succeeded else "FAILED",
            "rights": "UNKNOWN", "usage": budget.usage(), "finished_utc": _now()})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args(argv)
    result = run_probe(args.config, args.config_sha256)
    print(json.dumps({"state": result["state"], "stop_reason": result["stop_reason"], "usage": result["usage"]}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
